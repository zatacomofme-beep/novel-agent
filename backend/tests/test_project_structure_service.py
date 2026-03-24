from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from services.project_service import (
    _branch_and_descendant_ids,
    build_project_stats_payload,
    build_project_structure_payload,
)


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
        characters=[],
        world_settings=[],
        locations=[],
        plot_threads=[],
        foreshadowing_items=[],
        timeline_events=[],
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

    def test_branch_and_descendant_ids_collects_full_subtree(self) -> None:
        project = make_project()
        deep_branch = SimpleNamespace(
            id=uuid4(),
            project_id=project.id,
            source_branch_id=project.branches[1].id,
            key="deep",
            title="深层分支",
            description=None,
            status="active",
            is_default=False,
            created_at=datetime(2026, 3, 18, 13, 0, 0),
        )
        project.branches.append(deep_branch)

        affected = _branch_and_descendant_ids(project.branches, project.branches[1].id)

        self.assertEqual(
            affected,
            {project.branches[1].id, project.branches[0].id, deep_branch.id},
        )

    def test_build_project_stats_payload_counts_items_and_factions_from_wrappers(self) -> None:
        project = make_project()
        project.world_settings = [
            SimpleNamespace(
                id=uuid4(),
                key="item:moon-key",
                title="月匙",
                data={
                    "entity_type": "item",
                    "item_type": "artifact",
                    "items": [
                        {
                            "name": "月匙",
                            "type": "artifact",
                        }
                    ],
                },
                version=1,
            ),
            SimpleNamespace(
                id=uuid4(),
                key="faction:harbor-watch",
                title="海港守望",
                data={
                    "entity_type": "faction",
                    "name": "海港守望",
                    "faction_type": "military",
                },
                version=1,
            ),
            SimpleNamespace(
                id=uuid4(),
                key="weather",
                title="潮汐气候",
                data={"summary": "海潮异常"},
                version=1,
            ),
        ]

        stats = build_project_stats_payload(project)

        self.assertEqual(stats["total_word_count"], 3900)
        self.assertEqual(stats["chapter_count"], 3)
        self.assertEqual(stats["character_count"], 0)
        self.assertEqual(stats["item_count"], 1)
        self.assertEqual(stats["faction_count"], 1)
        self.assertEqual(stats["location_count"], 0)
        self.assertEqual(stats["plot_thread_count"], 0)
        self.assertEqual(stats["volume_count"], 2)
        self.assertEqual(stats["branch_count"], 2)

    def test_build_project_stats_payload_counts_native_items_and_factions(self) -> None:
        project = make_project()
        project.items = [
            SimpleNamespace(
                id=uuid4(),
                key="item:mirror",
                name="回潮镜片",
                item_type="artifact",
                rarity="rare",
                description="能折返一段记忆",
                effects=["回溯"],
                owner="林澈",
                location="雾港",
                status="sealed",
                introduced_chapter=3,
                forbidden_holders=[],
                version=1,
            )
        ]
        project.factions = [
            SimpleNamespace(
                id=uuid4(),
                key="faction:tide",
                name="潮汐会",
                faction_type="cult",
                scale="city",
                description="守望钟塔的人",
                goals="封存深潮",
                leader="钟守人",
                members=["守钟者"],
                territory="雾港钟塔",
                resources=["钟塔"],
                ideology="以遗忘换秩序",
                version=1,
            )
        ]

        stats = build_project_stats_payload(project)

        self.assertEqual(stats["item_count"], 1)
        self.assertEqual(stats["faction_count"], 1)
