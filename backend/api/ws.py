from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from realtime.task_events import task_event_broker
from tasks.state_store import task_state_store


router = APIRouter()


@router.websocket("/tasks/{task_id}")
async def task_updates(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
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
