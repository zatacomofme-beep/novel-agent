from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from core.errors import AppError
from models.story_bible_version import StoryBibleChangeType, StoryBibleSection
from schemas.story_bible_version import ConflictCheckRequest, StoryBibleRollbackRequest
from services.story_bible_version_service import (
    approve_pending_change,
    check_conflict,
    get_story_bible_versions,
    reject_pending_change,
    rollback_story_bible,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class StoryBibleVersionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_rollback_story_bible_restores_branch_snapshot_and_records_version(self) -> None:
        project_id = uuid4()
        branch_id = uuid4()
        descendant_branch_id = uuid4()
        user_id = uuid4()
        target_version_id = uuid4()
        current_snapshot = {"characters": [{"id": "hero-2", "name": "沈岚"}]}
        target_snapshot = {"characters": [{"id": "hero-1", "name": "林澈"}]}
        branch = SimpleNamespace(id=branch_id, title="主线", source_branch_id=None)
        descendant_branch = SimpleNamespace(
            id=descendant_branch_id,
            title="支线",
            source_branch_id=branch_id,
        )
        project = SimpleNamespace(id=project_id, branches=[branch, descendant_branch])
        target_version = SimpleNamespace(
            id=target_version_id,
            project_id=project_id,
            branch_id=branch_id,
            version_number=3,
            changed_section=StoryBibleSection.CHARACTERS.value,
            snapshot=target_snapshot,
        )
        branch_story_bible = SimpleNamespace(payload=current_snapshot.copy())
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(target_version)
        created_version = SimpleNamespace(id=uuid4())

        with (
            patch(
                "services.story_bible_version_service.get_project_branch_story_bible",
                new=AsyncMock(return_value=branch_story_bible),
            ),
            patch(
                "services.story_bible_version_service.create_story_bible_version",
                new=AsyncMock(return_value=created_version),
            ) as mocked_create_story_bible_version,
            patch(
                "services.story_bible_version_service._invalidate_story_bible_related_chapter_evaluations",
                new=AsyncMock(),
            ) as mocked_invalidate,
        ):
            result = await rollback_story_bible(
                session,
                project,
                branch_id,
                StoryBibleRollbackRequest(
                    target_version_id=target_version_id,
                    reason="恢复到稳定版本",
                ),
                user_id,
            )

        self.assertIs(result, created_version)
        self.assertEqual(branch_story_bible.payload, target_snapshot)

        create_kwargs = mocked_create_story_bible_version.await_args.kwargs
        self.assertEqual(create_kwargs["project_id"], project_id)
        self.assertEqual(create_kwargs["branch_id"], branch_id)
        self.assertEqual(create_kwargs["change_type"], StoryBibleChangeType.UPDATED)
        self.assertEqual(create_kwargs["changed_section"], StoryBibleSection.CHARACTERS)
        self.assertEqual(create_kwargs["old_value"], current_snapshot)
        self.assertEqual(create_kwargs["new_value"], target_snapshot)
        self.assertEqual(create_kwargs["snapshot"], target_snapshot)
        self.assertEqual(create_kwargs["created_by"], user_id)
        self.assertIn("Rollback to version 3", create_kwargs["note"])

        invalidate_kwargs = mocked_invalidate.await_args.kwargs
        self.assertEqual(
            invalidate_kwargs["branch_ids"],
            {branch_id, descendant_branch_id},
        )
        self.assertIn("rolled back", invalidate_kwargs["reason"])

    async def test_rollback_story_bible_deletes_branch_snapshot_when_target_is_empty(self) -> None:
        project_id = uuid4()
        branch_id = uuid4()
        user_id = uuid4()
        target_version_id = uuid4()
        branch = SimpleNamespace(id=branch_id, title="主线", source_branch_id=None)
        project = SimpleNamespace(id=project_id, branches=[branch])
        target_version = SimpleNamespace(
            id=target_version_id,
            project_id=project_id,
            branch_id=branch_id,
            version_number=4,
            changed_section=StoryBibleSection.WORLD_SETTINGS.value,
            snapshot={},
        )
        branch_story_bible = SimpleNamespace(
            payload={"world_settings": [{"key": "rule-1", "title": "代价"}]}
        )
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(target_version)

        with (
            patch(
                "services.story_bible_version_service.get_project_branch_story_bible",
                new=AsyncMock(return_value=branch_story_bible),
            ),
            patch(
                "services.story_bible_version_service.create_story_bible_version",
                new=AsyncMock(return_value=SimpleNamespace(id=uuid4())),
            ) as mocked_create_story_bible_version,
            patch(
                "services.story_bible_version_service._invalidate_story_bible_related_chapter_evaluations",
                new=AsyncMock(),
            ),
        ):
            await rollback_story_bible(
                session,
                project,
                branch_id,
                StoryBibleRollbackRequest(target_version_id=target_version_id),
                user_id,
            )

        session.delete.assert_awaited_once_with(branch_story_bible)
        create_kwargs = mocked_create_story_bible_version.await_args.kwargs
        self.assertEqual(create_kwargs["change_type"], StoryBibleChangeType.REMOVED)
        self.assertEqual(create_kwargs["snapshot"], {})

    async def test_rollback_story_bible_raises_app_error_when_target_version_is_missing(self) -> None:
        project = SimpleNamespace(
            id=uuid4(),
            branches=[SimpleNamespace(id=uuid4(), title="主线", source_branch_id=None)],
        )
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(None)

        with self.assertRaises(AppError) as raised:
            await rollback_story_bible(
                session,
                project,
                project.branches[0].id,
                StoryBibleRollbackRequest(target_version_id=uuid4()),
                uuid4(),
            )

        self.assertEqual(raised.exception.code, "story_bible.version_not_found")

    async def test_approve_pending_change_raises_app_error_when_missing(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(None)

        with self.assertRaises(AppError) as raised:
            await approve_pending_change(
                session,
                uuid4(),
                uuid4(),
            )

        self.assertEqual(raised.exception.code, "story_bible.pending_change_not_found")

    async def test_approve_pending_change_raises_when_project_scope_mismatches(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(None)

        with self.assertRaises(AppError) as raised:
            await approve_pending_change(
                session,
                uuid4(),
                uuid4(),
                expected_project_id=uuid4(),
            )

        self.assertEqual(raised.exception.code, "story_bible.pending_change_not_found")

    async def test_reject_pending_change_raises_app_error_when_missing(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(None)

        with self.assertRaises(AppError) as raised:
            await reject_pending_change(
                session,
                uuid4(),
                uuid4(),
                "Not acceptable",
            )

        self.assertEqual(raised.exception.code, "story_bible.pending_change_not_found")

    async def test_get_story_bible_versions_raises_when_branch_is_not_in_project(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(None)

        with self.assertRaises(AppError) as raised:
            await get_story_bible_versions(
                session,
                uuid4(),
                uuid4(),
            )

        self.assertEqual(raised.exception.code, "project.branch_not_found")

    async def test_check_conflict_uses_branch_scoped_story_bible_sections(self) -> None:
        branch_id = uuid4()
        project = SimpleNamespace(
            id=uuid4(),
            branches=[SimpleNamespace(id=branch_id, title="支线", source_branch_id=None)],
        )
        branch_sections = {
            "characters": [],
            "world_settings": [
                {
                    "key": "item:tide-lamp",
                    "title": "潮灯",
                    "data": {
                        "entity_type": "item",
                        "item_type": "artifact",
                        "owner": "沈岚",
                        "status": "sealed",
                        "items": [
                            {
                                "name": "潮灯",
                                "owner": "沈岚",
                                "status": "sealed",
                            }
                        ],
                    },
                    "version": 2,
                }
            ],
            "locations": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }
        resolution = SimpleNamespace(sections=branch_sections)

        with patch(
            "services.story_bible_version_service.resolve_story_bible_resolution",
            new=AsyncMock(return_value=resolution),
        ) as mocked_resolve:
            result = await check_conflict(
                AsyncMock(),
                project,
                ConflictCheckRequest(
                    section=StoryBibleSection.ITEMS,
                    entity_key="key:item:tide-lamp",
                    proposed_value={"owner": "林澈"},
                ),
                branch_id=branch_id,
            )

        self.assertTrue(result.has_conflict)
        self.assertEqual(result.conflicting_items[0]["existing_value"], "沈岚")
        self.assertEqual(result.conflicting_items[0]["proposed_value"], "林澈")
        self.assertEqual(mocked_resolve.await_args.kwargs["branch_id"], branch_id)


if __name__ == "__main__":
    unittest.main()
