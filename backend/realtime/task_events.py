from __future__ import annotations

import asyncio
from collections import defaultdict
import json
from typing import Optional
from uuid import uuid4

from redis import asyncio as redis_asyncio

from core.config import get_settings
from core.logging import get_logger

from tasks.schemas import TaskState


logger = get_logger(__name__)


class TaskEventBroker:
    def __init__(self) -> None:
        self._task_subscribers: dict[str, set[asyncio.Queue[TaskState]]] = defaultdict(set)
        self._broadcast_subscribers: set[asyncio.Queue[TaskState]] = set()
        self._redis: Optional[redis_asyncio.Redis] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._running = False
        self._remote_enabled = False
        self._instance_id = str(uuid4())
        self._settings = get_settings()

    async def subscribe(self, task_id: str) -> asyncio.Queue[TaskState]:
        queue: asyncio.Queue[TaskState] = asyncio.Queue()
        self._task_subscribers[task_id].add(queue)
        return queue

    async def unsubscribe(self, task_id: str, queue: asyncio.Queue[TaskState]) -> None:
        subscribers = self._task_subscribers.get(task_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._task_subscribers.pop(task_id, None)

    async def subscribe_all(self) -> asyncio.Queue[TaskState]:
        queue: asyncio.Queue[TaskState] = asyncio.Queue()
        self._broadcast_subscribers.add(queue)
        return queue

    async def unsubscribe_all(self, queue: asyncio.Queue[TaskState]) -> None:
        self._broadcast_subscribers.discard(queue)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._redis = redis_asyncio.from_url(
            self._settings.redis_url,
            decode_responses=True,
        )
        try:
            await self._redis.ping()
        except Exception as exc:
            logger.warning(
                "task_event_broker_redis_unavailable",
                extra={"error": str(exc)},
            )
            await self._disable_remote()
            return

        self._remote_enabled = True
        self._listener_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        self._running = False
        self._remote_enabled = False
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning(
                    "task_event_broker_listener_shutdown_error",
                    extra={"error": str(exc)},
                )
            self._listener_task = None
        if self._redis is not None:
            await self._close_async_resource(self._redis)
            self._redis = None

    def publish(self, state: TaskState) -> None:
        self._publish_local(state)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._redis is not None and self._running and self._remote_enabled:
            loop.create_task(self._publish_remote(state))

    def _publish_local(self, state: TaskState) -> None:
        subscribers = set(self._task_subscribers.get(state.task_id, set()))
        subscribers.update(self._broadcast_subscribers)
        for queue in list(subscribers):
            try:
                queue.put_nowait(state)
            except asyncio.QueueFull:
                continue

    async def _publish_remote(self, state: TaskState) -> None:
        if self._redis is None:
            return
        payload = json.dumps(
            {
                "instance_id": self._instance_id,
                "state": state.model_dump(mode="json"),
            }
        )
        try:
            await self._redis.publish(self._channel_name(state.task_id), payload)
        except Exception as exc:
            logger.warning(
                "task_event_broker_publish_failed",
                extra={"error": str(exc), "task_id": state.task_id},
            )
            await self._disable_remote()

    async def _listen(self) -> None:
        if self._redis is None:
            return

        pubsub = self._redis.pubsub()
        try:
            await pubsub.psubscribe(self._pattern())
            while self._running and self._remote_enabled:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if not message:
                    await asyncio.sleep(0.05)
                    continue
                data = message.get("data")
                if not data:
                    continue
                payload = json.loads(data)
                if payload.get("instance_id") == self._instance_id:
                    continue
                state = TaskState(**payload["state"])
                self._publish_local(state)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "task_event_broker_listener_failed",
                extra={"error": str(exc)},
            )
            await self._disable_remote()
        finally:
            await self._close_async_resource(pubsub)

    def _channel_name(self, task_id: str) -> str:
        return f"{self._settings.redis_task_events_channel_prefix}:{task_id}"

    def _pattern(self) -> str:
        return f"{self._settings.redis_task_events_channel_prefix}:*"

    async def _close_async_resource(self, resource) -> None:
        close_fn = getattr(resource, "aclose", None) or getattr(resource, "close", None)
        if close_fn is None:
            return
        result = close_fn()
        if asyncio.iscoroutine(result):
            await result

    async def _disable_remote(self) -> None:
        self._remote_enabled = False
        if self._redis is not None:
            await self._close_async_resource(self._redis)
            self._redis = None


task_event_broker = TaskEventBroker()
