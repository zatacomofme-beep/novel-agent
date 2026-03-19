from __future__ import annotations

import unittest
from unittest.mock import patch

from realtime.task_events import TaskEventBroker


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
