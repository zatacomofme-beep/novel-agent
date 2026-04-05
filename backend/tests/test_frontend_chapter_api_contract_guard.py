from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = REPO_ROOT / "frontend"

SOURCE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
IGNORE_PATH_PARTS = {
    "node_modules",
    ".next",
    "dist",
    "coverage",
    "test-results",
}

LEGACY_CHAPTER_ROUTE_PREFIX = "/api/v1/chapters/"
EXPECTED_STORY_ENGINE_ROUTE_SEGMENT = "/api/v1/projects/"


def _frontend_source_files() -> list[Path]:
    files: list[Path] = []
    for path in FRONTEND_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(FRONTEND_ROOT)
        if any(part in IGNORE_PATH_PARTS for part in relative.parts):
            continue
        if path.suffix not in SOURCE_EXTENSIONS:
            continue
        files.append(relative)
    return files


class FrontendChapterApiContractGuardTests(unittest.TestCase):
    def test_frontend_does_not_call_legacy_chapter_routes(self) -> None:
        offenders: list[str] = []
        for relative in _frontend_source_files():
            content = (FRONTEND_ROOT / relative).read_text(encoding="utf-8")
            if LEGACY_CHAPTER_ROUTE_PREFIX in content:
                offenders.append(str(relative))

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Frontend should not call deprecated /api/v1/chapters/* routes. "
                f"Use project-scoped Story Engine chapter routes ({EXPECTED_STORY_ENGINE_ROUTE_SEGMENT}"
                "{projectId}/story-engine/chapters/*). Offenders: "
                f"{offenders}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
