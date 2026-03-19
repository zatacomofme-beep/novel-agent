from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from services.project_service import build_project_structure_payload


def make_project():
    project_id = uuid4()
    volume_one = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        volume_number=1,
        title="第一卷",
        summary=None,
        status="writing",
    )
    volume_two = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        volume_number=2,
        title="第二卷",
        summary="第二卷摘要",
        status="planning",
    )
    main_branch = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        source_branch_id=None,
        key="main",
        title="主线",
        description=None,
        status="active",
        is_default=True,
        created_at=datetime(2026, 3, 18, 12, 0, 0),
    )
    side_branch = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        source_branch_id=main_branch.id,
        key="alt",
        title="支线",
        description="备用分支",
        status="active",
        is_default=False,
        created_at=datetime(2026, 3, 18, 12, 30, 0),
    )
    return SimpleNamespace(
        id=project_id,
        user_id=uuid4(),
        title="海潮归航",
        genre="奇幻",
        theme="归乡",
        tone="克制",
        status="draft",
        volumes=[volume_two, volume_one],
        branches=[side_branch, main_branch],
        chapters=[
            SimpleNamespace(
                id=uuid4(),
                project_id=project_id,
                volume_id=volume_one.id,
                branch_id=main_branch.id,
                chapter_number=1,
                title="潮门初开",
                status="draft",
                word_count=1200,
            ),
            SimpleNamespace(
                id=uuid4(),
                project_id=project_id,
                volume_id=volume_one.id,
                branch_id=main_branch.id,
                chapter_number=2,
                title="雾岸",
                status="review",
                word_count=1800,
            ),
            SimpleNamespace(
                id=uuid4(),
                project_id=project_id,
                volume_id=volume_two.id,
                branch_id=side_branch.id,
                chapter_number=1,
                title="回声支线",
                status="writing",
                word_count=900,
            ),
        ],
    )


class ProjectStructureServiceTests(unittest.TestCase):
    def test_build_project_structure_payload_counts_chapters_and_defaults(self) -> None:
        payload = build_project_structure_payload(make_project())

        self.assertEqual(payload.default_volume_id, payload.volumes[0].id)
        self.assertEqual(payload.default_branch_id, payload.branches[0].id)
        self.assertEqual(payload.volumes[0].title, "第一卷")
        self.assertEqual(payload.volumes[0].chapter_count, 2)
        self.assertTrue(payload.volumes[0].is_default)
        self.assertEqual(payload.volumes[1].chapter_count, 1)
        self.assertEqual(payload.branches[0].key, "main")
        self.assertTrue(payload.branches[0].is_default)
        self.assertEqual(payload.branches[0].chapter_count, 2)
        self.assertEqual(payload.branches[1].chapter_count, 1)
