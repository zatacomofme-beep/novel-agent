from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from realtime.task_events import TaskEventBroker
from tasks.schemas import TaskState


class FakeRedisClient:
    def __init__(self) -> None:
        self.closed = False

    async def ping(self) -> None:
        raise ConnectionError("redis offline")

    async def aclose(self) -> None:
        self.closed = True


class TaskEventBrokerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_degrades_when_redis_is_unavailable(self) -> None:
        broker = TaskEventBroker()
        fake_client = FakeRedisClient()

        with patch("realtime.task_events.redis_asyncio.from_url", return_value=fake_client):
            await broker.start()

        self.assertTrue(broker._running)
        self.assertFalse(broker._remote_enabled)
        self.assertIsNone(broker._redis)
        self.assertTrue(fake_client.closed)

        await broker.stop()

    async def test_subscribe_all_receives_published_state(self) -> None:
        broker = TaskEventBroker()
        queue = await broker.subscribe_all()
        state = TaskState(
            task_id="task-broadcast-1",
            task_type="story_engine.outline_stress_test",
            status="running",
            progress=42,
            message="outline in progress",
        )

        broker.publish(state)

        received = await asyncio.wait_for(queue.get(), timeout=0.2)
        self.assertEqual(received.task_id, state.task_id)
        self.assertEqual(received.progress, state.progress)

        await broker.unsubscribe_all(queue)
