from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.main import app


class AppSmokeTests(unittest.TestCase):
    def test_health_and_ready_endpoints_boot_without_redis(self) -> None:
        with TestClient(app) as client:
            root_response = client.get("/")
            health_response = client.get("/health")
            ready_response = client.get("/ready")

        self.assertEqual(root_response.status_code, 200)
        self.assertEqual(root_response.json()["status"], "bootstrapping")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json(), {"status": "ok"})
        self.assertEqual(ready_response.status_code, 200)
        self.assertEqual(ready_response.json()["api_prefix"], "/api/v1")
