from __future__ import annotations

import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_GENERATION_IMPORT_FILES = {
    Path("services/legacy_generation_service.py"),
}

ALLOWED_CHAPTER_TASK_IMPORT_FILES = {
    Path("services/legacy_generation_dispatch_service.py"),
}

ALLOWED_LEGACY_PROJECT_GENERATION_IMPORT_FILES = {
    Path("api/v1/projects.py"),
    Path("services/legacy_project_generation_service.py"),
}

ALLOWED_COORDINATOR_IMPORT_FILES = {
    Path("agents/coordinator.py"),
    Path("services/generation_service.py"),
}


def _backend_python_files() -> list[Path]:
    files: list[Path] = []
    for path in BACKEND_ROOT.rglob("*.py"):
        relative = path.relative_to(BACKEND_ROOT)
        if "tests" in relative.parts:
            continue
        if "__pycache__" in relative.parts:
            continue
        files.append(relative)
    return files


class LegacyGenerationArchitectureGuardTests(unittest.TestCase):
    def test_only_compat_layer_imports_generation_service_directly(self) -> None:
        offenders: list[str] = []
        for relative in _backend_python_files():
            if relative in ALLOWED_GENERATION_IMPORT_FILES:
                continue
            content = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
            if (
                "from services.generation_service import" in content
                or "import services.generation_service" in content
            ):
                offenders.append(str(relative))

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Direct imports of services.generation_service are only allowed "
                f"in compatibility modules. Offenders: {offenders}"
            ),
        )

    def test_only_compat_dispatch_layer_imports_chapter_generation_task_directly(self) -> None:
        offenders: list[str] = []
        for relative in _backend_python_files():
            if relative in ALLOWED_CHAPTER_TASK_IMPORT_FILES:
                continue
            content = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
            if (
                "from tasks.chapter_generation import" in content
                or "import tasks.chapter_generation" in content
            ):
                offenders.append(str(relative))

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Direct imports of tasks.chapter_generation are only allowed "
                f"in compatibility dispatch modules. Offenders: {offenders}"
            ),
        )

    def test_only_legacy_entrypoints_import_project_generation_dispatch(self) -> None:
        offenders: list[str] = []
        for relative in _backend_python_files():
            if relative in ALLOWED_LEGACY_PROJECT_GENERATION_IMPORT_FILES:
                continue
            content = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
            if "from services.project_generation_service import dispatch_next_project_chapter_generation" in content:
                offenders.append(str(relative))

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Direct imports of project_generation_service.dispatch_next_project_chapter_generation "
                f"are not allowed outside legacy boundaries. Offenders: {offenders}"
            ),
        )

    def test_only_legacy_entrypoints_import_legacy_project_generation_service(self) -> None:
        offenders: list[str] = []
        for relative in _backend_python_files():
            if relative in ALLOWED_LEGACY_PROJECT_GENERATION_IMPORT_FILES:
                continue
            content = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
            if "from services.legacy_project_generation_service import" in content:
                offenders.append(str(relative))

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Direct imports of legacy_project_generation_service are only allowed "
                f"at the legacy project entry boundary. Offenders: {offenders}"
            ),
        )

    def test_only_legacy_generation_core_imports_coordinator_directly(self) -> None:
        offenders: list[str] = []
        for relative in _backend_python_files():
            if relative in ALLOWED_COORDINATOR_IMPORT_FILES:
                continue
            content = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
            if (
                "from agents.coordinator import" in content
                or "CoordinatorAgent(" in content
            ):
                offenders.append(str(relative))

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Direct coordinator usage is only allowed inside legacy generation core. "
                f"Offenders: {offenders}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
