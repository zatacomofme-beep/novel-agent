from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from core.errors import AppError
from services.project_service import (
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_EVALUATE,
    PROJECT_ROLE_EDITOR,
    PROJECT_ROLE_REVIEWER,
    PROJECT_ROLE_VIEWER,
    _assert_project_permission,
    build_project_collaboration_payload,
)


class ProjectCollaborationServiceTests(unittest.TestCase):
    def test_build_project_collaboration_payload_includes_owner_and_members(self) -> None:
        project_id = uuid4()
        owner_id = uuid4()
        editor_id = uuid4()
        reviewer_id = uuid4()
        payload = build_project_collaboration_payload(
            SimpleNamespace(
                id=project_id,
                user_id=owner_id,
                title="雾港",
                genre="悬疑",
                theme=None,
                tone=None,
                status="writing",
                access_role="owner",
                owner_email="owner@example.com",
                collaborator_count=2,
                user=SimpleNamespace(email="owner@example.com"),
                collaborators=[
                    SimpleNamespace(
                        id=uuid4(),
                        project_id=project_id,
                        user_id=editor_id,
                        added_by_user_id=owner_id,
                        role="editor",
                        created_at=datetime.now(timezone.utc),
                        user=SimpleNamespace(email="editor@example.com"),
                    ),
                    SimpleNamespace(
                        id=uuid4(),
                        project_id=project_id,
                        user_id=reviewer_id,
                        added_by_user_id=owner_id,
                        role="reviewer",
                        created_at=datetime.now(timezone.utc),
                        user=SimpleNamespace(email="reviewer@example.com"),
                    ),
                ],
            ),
            "owner",
        )

        self.assertEqual(payload.current_role, "owner")
        self.assertEqual(payload.project.owner_email, "owner@example.com")
        self.assertEqual(payload.project.collaborator_count, 2)
        self.assertEqual(len(payload.members), 3)
        self.assertTrue(payload.members[0].is_owner)
        self.assertEqual(payload.members[0].email, "owner@example.com")
        self.assertEqual(payload.members[1].role, "editor")
        self.assertEqual(payload.members[2].role, "reviewer")

    def test_permission_matrix_allows_reviewer_evaluate_but_blocks_edit(self) -> None:
        _assert_project_permission(PROJECT_ROLE_REVIEWER, PROJECT_PERMISSION_EVALUATE)
        _assert_project_permission(PROJECT_ROLE_EDITOR, PROJECT_PERMISSION_EDIT)
        with self.assertRaises(AppError):
            _assert_project_permission(PROJECT_ROLE_VIEWER, PROJECT_PERMISSION_EDIT)
