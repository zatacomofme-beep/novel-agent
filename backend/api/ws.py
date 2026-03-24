from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
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
