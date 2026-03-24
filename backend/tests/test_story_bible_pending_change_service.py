from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from core.errors import AppError
from models.story_bible_version import (
    StoryBibleChangeSource,
    StoryBibleChangeType,
    StoryBiblePendingChangeStatus,
    StoryBibleSection,
)
from schemas.story_bible_version import StoryBiblePendingChangeCreate
from services.story_bible_version_service import (
    _extract_pending_entity_key,
    _extract_pending_item_payload,
    _select_pending_item_candidate,
    approve_pending_change,
    auto_trigger_story_bible_change,
    create_pending_change,
    get_pending_changes,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value


class _CollectionResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _CountResult:
    def __init__(self, count: int, legacy_values: list[object] | None = None):
        self._count = count
        self._legacy_values = legacy_values or []

    def scalar_one(self):
        return self._count

    def scalars(self):
        return self

    def all(self):
        return self._legacy_values


class StoryBiblePendingChangeServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_pending_item_payload_selects_matching_entity_from_section_list(self) -> None:
        target_id = str(uuid4())
        pending = SimpleNamespace(
            changed_entity_key=f"id:{target_id}",
            changed_section=StoryBibleSection.CHARACTERS.value,
            new_value={
                "characters": [
                    {
                        "id": str(uuid4()),
                        "name": "沈岚",
                        "data": {"status": "alive"},
                    },
                    {
                        "id": target_id,
                        "name": "林澈",
                        "data": {"status": "missing"},
                    },
                ]
            },
        )

        payload = _extract_pending_item_payload(pending)

        self.assertEqual(payload["id"], target_id)
        self.assertEqual(payload["name"], "林澈")
        self.assertEqual(payload["data"]["status"], "missing")

    def test_extract_pending_entity_key_falls_back_to_old_value_identity(self) -> None:
        pending = SimpleNamespace(
            changed_entity_key=None,
            changed_section=StoryBibleSection.WORLD_SETTINGS.value,
            old_value={
                "world_settings": [
                    {
                        "key": "rule-1",
                        "title": "潮汐法则",
                        "data": {"cost": "memory"},
                    }
                ]
            },
            new_value=None,
        )

        entity_key = _extract_pending_entity_key(pending)

        self.assertEqual(entity_key, "key:rule-1")

    def test_select_pending_item_candidate_requires_identity_when_multiple_rows_exist(self) -> None:
        selected = _select_pending_item_candidate(
            [
                {"id": str(uuid4()), "name": "甲"},
                {"id": str(uuid4()), "name": "乙"},
            ],
            entity_key=None,
        )

        self.assertIsNone(selected)

    async def test_approve_pending_change_marks_status_after_project_lookup(self) -> None:
        change_id = uuid4()
        project_id = uuid4()
        branch_id = uuid4()
        user_id = uuid4()
        pending = SimpleNamespace(
            id=change_id,
            project_id=project_id,
            branch_id=branch_id,
            status=StoryBiblePendingChangeStatus.PENDING.value,
            change_type=StoryBibleChangeType.UPDATED.value,
            changed_section=StoryBibleSection.CHARACTERS.value,
            changed_entity_key="id:hero-1",
            old_value=None,
            new_value={
                "item": {
                    "id": "hero-1",
                    "name": "林澈",
                    "data": {"status": "alive"},
                }
            },
            reason="Auto-triggered by chapter review",
            approved_by=None,
            approved_at=None,
        )
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(pending)
        project = SimpleNamespace(id=project_id)

        async def fake_get_owned_project(*args, **kwargs):
            self.assertEqual(
                pending.status,
                StoryBiblePendingChangeStatus.PENDING.value,
            )
            return project

        async def fake_apply_pending_change(*args, **kwargs):
            self.assertEqual(
                pending.status,
                StoryBiblePendingChangeStatus.APPROVED.value,
            )

        with (
            patch(
                "services.story_bible_version_service.get_owned_project",
                new=AsyncMock(side_effect=fake_get_owned_project),
            ),
            patch(
                "services.story_bible_version_service._apply_pending_change",
                new=AsyncMock(side_effect=fake_apply_pending_change),
            ),
        ):
            result = await approve_pending_change(
                session,
                change_id,
                user_id,
                "Looks good",
            )

        self.assertIs(result, pending)
        self.assertEqual(pending.status, StoryBiblePendingChangeStatus.APPROVED.value)
        self.assertEqual(pending.approved_by, user_id)
        self.assertIsNotNone(pending.approved_at)
        self.assertIn("Approval note: Looks good", pending.reason)
        session.refresh.assert_awaited_once_with(pending)

    async def test_auto_trigger_story_bible_change_marks_auto_trigger_source(self) -> None:
        session = SimpleNamespace(add=Mock(), flush=AsyncMock())

        pending = await auto_trigger_story_bible_change(
            session,
            uuid4(),
            uuid4(),
            trigger_type="plot_thread_progressed",
            entity_key="title:镜海疑云",
            reason="Plot thread status changed after chapter review",
            agent_name="canon_guardian",
        )

        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertEqual(
            pending.change_source,
            StoryBibleChangeSource.AUTO_TRIGGER.value,
        )
        self.assertEqual(
            pending.changed_section,
            StoryBibleSection.PLOT_THREADS.value,
        )
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    async def test_create_pending_change_raises_when_branch_is_not_in_project(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(None)
        project_id = uuid4()
        branch_id = uuid4()

        with self.assertRaises(AppError) as raised:
            await create_pending_change(
                session,
                project_id,
                branch_id,
                StoryBiblePendingChangeCreate(
                    project_id=project_id,
                    branch_id=branch_id,
                    change_type=StoryBibleChangeType.UPDATED,
                    change_source=StoryBibleChangeSource.USER,
                    changed_section=StoryBibleSection.CHARACTERS,
                    changed_entity_key="id:hero-1",
                    new_value={"item": {"id": "hero-1", "name": "林澈"}},
                ),
            )

        self.assertEqual(raised.exception.code, "project.branch_not_found")

    async def test_create_pending_change_raises_when_request_project_id_mismatches(self) -> None:
        session = AsyncMock()

        with self.assertRaises(AppError) as raised:
            await create_pending_change(
                session,
                uuid4(),
                uuid4(),
                StoryBiblePendingChangeCreate(
                    project_id=uuid4(),
                    branch_id=uuid4(),
                    change_type=StoryBibleChangeType.UPDATED,
                    change_source=StoryBibleChangeSource.USER,
                    changed_section=StoryBibleSection.CHARACTERS,
                    changed_entity_key="id:hero-1",
                    new_value={"item": {"id": "hero-1", "name": "林澈"}},
                ),
            )

        self.assertEqual(raised.exception.code, "story_bible.project_mismatch")
        session.execute.assert_not_called()

    async def test_get_pending_changes_uses_filtered_count(self) -> None:
        project_id = uuid4()
        branch_id = uuid4()
        now = datetime.now(timezone.utc)
        pending = SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            branch_id=branch_id,
            status=StoryBiblePendingChangeStatus.PENDING.value,
            change_type=StoryBibleChangeType.UPDATED.value,
            change_source=StoryBibleChangeSource.AUTO_TRIGGER.value,
            changed_section=StoryBibleSection.ITEMS.value,
            changed_entity_id=None,
            changed_entity_key="key:item:tide-lamp",
            old_value=None,
            new_value={"item": {"key": "item:tide-lamp", "name": "潮灯"}},
            reason="Auto-triggered by continuity check",
            triggered_by_chapter_id=None,
            proposed_by_agent="canon_guardian",
            approved_by=None,
            approved_at=None,
            rejected_by=None,
            rejected_at=None,
            rejection_reason=None,
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        session = AsyncMock()
        session.execute.side_effect = [
            _ScalarResult(branch_id),
            _CollectionResult([pending]),
            _CountResult(1, legacy_values=[pending, pending, pending]),
        ]

        result = await get_pending_changes(session, project_id, branch_id)

        self.assertEqual(result.total, 1)
        self.assertEqual(result.pending_count, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].change_source, StoryBibleChangeSource.AUTO_TRIGGER)

    async def test_get_pending_changes_raises_when_branch_is_not_in_project(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(None)

        with self.assertRaises(AppError) as raised:
            await get_pending_changes(
                session,
                uuid4(),
                uuid4(),
            )

        self.assertEqual(raised.exception.code, "project.branch_not_found")
