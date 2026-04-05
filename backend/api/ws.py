from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from core.security import decode_access_token
from db.session import AsyncSessionLocal
from realtime.task_events import task_event_broker
from services.project_service import PROJECT_PERMISSION_READ, get_owned_project
from services.task_service import get_task_run_by_task_id
from tasks.state_store import task_state_store


router = APIRouter()
AUTH_MESSAGE_TIMEOUT_SECONDS = 5
AUTH_TOKEN_KEY = "novel_agent_token"


def verify_ws_token(token: str) -> str | None:
    try:
        payload = decode_access_token(token)
        return payload.get("sub")
    except Exception:
        return None


async def receive_ws_token(websocket: WebSocket) -> str | None:
    try:
        payload = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=AUTH_MESSAGE_TIMEOUT_SECONDS,
        )
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError, TypeError):
        return None

    if not isinstance(payload, dict) or payload.get("type") != "auth":
        return None

    token = payload.get("token")
    if not isinstance(token, str):
        return None
    token = token.strip()
    return token or None


async def verify_task_access(task_id: str, user_id: str, session: AsyncSession) -> bool:
    task_run = await get_task_run_by_task_id(session, task_id)
    if task_run is None:
        return False

    project_id = getattr(task_run, "project_id", None)
    if project_id is not None:
        try:
            await get_owned_project(
                session,
                project_id,
                UUID(user_id),
                permission=PROJECT_PERMISSION_READ,
            )
            return True
        except (AppError, ValueError):
            return False

    return str(getattr(task_run, "user_id", "")) == user_id


async def verify_project_access(project_id: UUID, user_id: str, session: AsyncSession) -> bool:
    try:
        await get_owned_project(
            session,
            project_id,
            UUID(user_id),
            permission=PROJECT_PERMISSION_READ,
        )
        return True
    except (AppError, ValueError):
        return False


def _normalize_task_ids(task_ids: list[str]) -> set[str]:
    normalized: set[str] = set()
    for task_id in task_ids:
        value = task_id.strip()
        if value:
            normalized.add(value)
    return normalized


async def verify_task_event_subscription_access(
    *,
    task_ids: set[str],
    project_ids: set[UUID],
    user_id: str,
    session: AsyncSession,
) -> bool:
    for task_id in task_ids:
        if not await verify_task_access(task_id, user_id, session):
            return False
    for project_id in project_ids:
        if not await verify_project_access(project_id, user_id, session):
            return False
    return True


@router.websocket("/tasks/{task_id}")
async def task_updates(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()

    token = websocket.cookies.get(AUTH_TOKEN_KEY)
    if not token:
        token = await receive_ws_token(websocket)

    user_id = verify_ws_token(token) if token else None
    if user_id is None:
        await websocket.close(code=4001)
        return

    async with AsyncSessionLocal() as session:
        has_access = await verify_task_access(task_id, user_id, session)
    if not has_access:
        await websocket.close(code=4003)
        return

    queue = await task_event_broker.subscribe(task_id)

    current_state = task_state_store.get(task_id)
    if current_state is not None:
        await websocket.send_json(current_state.model_dump(mode="json"))

    try:
        while True:
            state = await queue.get()
            await websocket.send_json(state.model_dump(mode="json"))
    except (WebSocketDisconnect, asyncio.CancelledError):
        await task_event_broker.unsubscribe(task_id, queue)


@router.websocket("/task-events")
async def task_events(
    websocket: WebSocket,
    project_id: list[UUID] = Query(default=[]),
    task_id: list[str] = Query(default=[]),
) -> None:
    await websocket.accept()

    token = websocket.cookies.get(AUTH_TOKEN_KEY)
    if not token:
        token = await receive_ws_token(websocket)

    user_id = verify_ws_token(token) if token else None
    if user_id is None:
        await websocket.close(code=4001)
        return

    normalized_task_ids = _normalize_task_ids(task_id)
    normalized_project_ids = set(project_id)
    normalized_project_id_strings = {str(item) for item in normalized_project_ids}
    if not normalized_task_ids and not normalized_project_ids:
        await websocket.close(code=4400)
        return

    async with AsyncSessionLocal() as session:
        has_access = await verify_task_event_subscription_access(
            task_ids=normalized_task_ids,
            project_ids=normalized_project_ids,
            user_id=user_id,
            session=session,
        )
    if not has_access:
        await websocket.close(code=4003)
        return

    queue = await task_event_broker.subscribe_all()

    try:
        await websocket.send_json(
            {
                "type": "subscribed",
                "task_ids": sorted(normalized_task_ids),
                "project_ids": sorted(normalized_project_id_strings),
            }
        )

        for subscribed_task_id in sorted(normalized_task_ids):
            current_state = task_state_store.get(subscribed_task_id)
            if current_state is None:
                continue
            await websocket.send_json(
                {
                    "type": "task_state",
                    "task": current_state.model_dump(mode="json"),
                }
            )

        while True:
            state = await queue.get()
            state_project_id = str(state.project_id) if state.project_id is not None else None
            match_task = state.task_id in normalized_task_ids
            match_project = (
                state_project_id is not None
                and state_project_id in normalized_project_id_strings
            )
            if not match_task and not match_project:
                continue
            await websocket.send_json(
                {
                    "type": "task_state",
                    "task": state.model_dump(mode="json"),
                }
            )
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await task_event_broker.unsubscribe_all(queue)
