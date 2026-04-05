from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import LEGACY_CHAPTER_SUNSET, app


class LegacyChapterDeprecationHeaderTests(unittest.TestCase):
    def test_legacy_chapter_routes_include_deprecation_headers(self) -> None:
        chapter_id = "00000000-0000-0000-0000-000000000001"
        with TestClient(app) as client:
            response = client.get(f"/api/v1/chapters/{chapter_id}")

        self.assertIn(response.status_code, {401, 403, 404})
        self.assertEqual(response.headers.get("Deprecation"), "true")
        self.assertEqual(response.headers.get("Sunset"), LEGACY_CHAPTER_SUNSET)

    def test_project_scoped_routes_do_not_include_legacy_deprecation_headers(self) -> None:
        project_id = "00000000-0000-0000-0000-000000000002"
        with TestClient(app) as client:
            response = client.get(f"/api/v1/projects/{project_id}/chapters")

        self.assertIn(response.status_code, {401, 403, 404})
        self.assertIsNone(response.headers.get("Deprecation"))
        self.assertIsNone(response.headers.get("Sunset"))

    def test_legacy_chapter_routes_return_410_when_mode_is_gone(self) -> None:
        chapter_id = "00000000-0000-0000-0000-000000000003"
        with patch("api.main._legacy_chapter_routes_mode", return_value="gone"):
            with TestClient(app) as client:
                response = client.get(f"/api/v1/chapters/{chapter_id}")

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.headers.get("Deprecation"), "true")
        self.assertEqual(response.headers.get("Sunset"), LEGACY_CHAPTER_SUNSET)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "chapter.legacy_endpoint_gone")
        self.assertIn("story-engine chapter routes", payload["error"]["message"])

    def test_project_scoped_routes_not_blocked_when_mode_is_gone(self) -> None:
        project_id = "00000000-0000-0000-0000-000000000004"
        with patch("api.main._legacy_chapter_routes_mode", return_value="gone"):
            with TestClient(app) as client:
                response = client.get(f"/api/v1/projects/{project_id}/chapters")

        self.assertIn(response.status_code, {401, 403, 404})
        self.assertIsNone(response.headers.get("Deprecation"))
        self.assertIsNone(response.headers.get("Sunset"))


if __name__ == "__main__":
    unittest.main()
