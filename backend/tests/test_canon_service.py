from __future__ import annotations

import unittest
from uuid import uuid4

from canon.service import (
    build_canon_snapshot_payload,
    validate_story_bible_integrity,
    validate_story_canon,
)
from memory.story_bible import StoryBibleContext


class CanonServiceTests(unittest.TestCase):
    def _base_context(self) -> StoryBibleContext:
        return StoryBibleContext(
            project_id=uuid4(),
            title="雾港",
            genre="悬疑",
            theme="信任",
            tone="压抑",
            status="draft",
            characters=[],
            world_settings=[],
            items=[],
            factions=[],
            locations=[],
            plot_threads=[],
            foreshadowing=[],
            timeline_events=[],
            chapter_summaries=[],
        )

    def test_flags_character_before_introduction(self) -> None:
        context = self._base_context()
        context.characters = [
            {
                "id": str(uuid4()),
                "name": "林舟",
                "data": {},
                "version": 1,
                "created_chapter": 5,
            }
        ]

        report = validate_story_canon(
            context,
            content="林舟推门走进来，像从未离开过一样。",
            chapter_number=3,
            chapter_title="回潮",
        )

        self.assertEqual(report.issue_count, 1)
        self.assertEqual(report.blocking_issue_count, 1)
        self.assertEqual(report.issues[0].code, "character.before_introduction")

    def test_flags_enemy_relationship_written_as_friendship(self) -> None:
        context = self._base_context()
        context.characters = [
            {
                "id": str(uuid4()),
                "name": "林舟",
                "data": {
                    "relationships": [
                        {"target": "沈岚", "status": "enemy"},
                    ]
                },
                "version": 1,
                "created_chapter": 1,
            },
            {
                "id": str(uuid4()),
                "name": "沈岚",
                "data": {},
                "version": 1,
                "created_chapter": 1,
            },
        ]

        report = validate_story_canon(
            context,
            content="林舟和沈岚像朋友一样并肩站着，谁也没有提防谁。",
            chapter_number=6,
            chapter_title="对峙",
        )

        self.assertGreaterEqual(report.issue_count, 1)
        self.assertEqual(report.issues[0].dimension, "canon.relationship_state")

    def test_flags_destroyed_item_still_in_use(self) -> None:
        context = self._base_context()
        context.items = [
            {
                "key": "item:black-key",
                "name": "黑钥匙",
                "status": "destroyed",
                "owner": "林舟",
                "location": None,
                "introduced_chapter": 1,
                "forbidden_holders": [],
                "version": 1,
            }
        ]

        report = validate_story_canon(
            context,
            content="她拿起黑钥匙，用力插进门锁里。",
            chapter_number=7,
            chapter_title="暗门",
        )

        self.assertEqual(report.blocking_issue_count, 1)
        self.assertEqual(report.issues[0].code, "item.unusable_state")

    def test_flags_future_timeline_event_reference(self) -> None:
        context = self._base_context()
        context.timeline_events = [
            {
                "id": str(uuid4()),
                "chapter_number": 9,
                "title": "雾港爆炸",
                "data": {},
            }
        ]

        report = validate_story_canon(
            context,
            content="所有人都知道雾港爆炸会在今夜发生。",
            chapter_number=6,
            chapter_title="预兆",
        )

        self.assertEqual(report.blocking_issue_count, 1)
        self.assertEqual(report.issues[0].dimension, "canon.timeline_order")

    def test_builds_canon_snapshot_payload_grouped_by_plugin(self) -> None:
        context = self._base_context()
        context.characters = [
            {
                "id": str(uuid4()),
                "name": "林舟",
                "data": {
                    "status": "alive",
                    "relationships": [
                        {"target": "沈岚", "status": "enemy"},
                    ],
                    "items": [
                        {"name": "黑钥匙", "status": "active"},
                    ],
                },
                "version": 1,
                "created_chapter": 1,
            },
            {
                "id": str(uuid4()),
                "name": "沈岚",
                "data": {},
                "version": 1,
                "created_chapter": 1,
            },
        ]
        context.items = [
            {
                "key": "item:black-key",
                "name": "黑钥匙",
                "status": "active",
                "owner": "林舟",
                "location": None,
                "introduced_chapter": 1,
                "forbidden_holders": [],
                "version": 1,
            },
            {
                "key": "item:tide-lamp",
                "name": "潮灯",
                "status": "sealed",
                "owner": None,
                "location": "雾港",
                "introduced_chapter": 1,
                "forbidden_holders": [],
                "version": 1,
            },
        ]
        context.factions = [
            {
                "key": "faction:black-bell",
                "name": "黑钟会",
                "type": "cult",
                "description": "钟塔之下的旧组织",
                "leader": "沈岚",
                "members": ["林舟"],
                "territory": "雾港",
                "resources": ["钟塔", "密卷"],
                "ideology": "以遗忘换秩序",
                "version": 1,
            }
        ]
        context.locations = [
            {
                "id": str(uuid4()),
                "name": "雾港",
                "data": {},
                "version": 1,
            }
        ]
        context.world_settings = [
            {
                "id": str(uuid4()),
                "key": "rule-1",
                "title": "潮汐法则",
                "data": {"required_keywords": ["海雾"]},
                "version": 1,
            }
        ]
        context.timeline_events = [
            {
                "id": str(uuid4()),
                "chapter_number": 9,
                "title": "雾港爆炸",
                "data": {},
            }
        ]
        context.foreshadowing = [
            {
                "id": str(uuid4()),
                "content": "黑钟会响两次。",
                "planted_chapter": 2,
                "payoff_chapter": 8,
                "status": "pending",
                "importance": 2,
            }
        ]

        payload = build_canon_snapshot_payload(context)
        plugin_snapshots = {
            item["plugin_key"]: item
            for item in payload["plugin_snapshots"]
        }

        self.assertEqual(payload["total_entity_count"], 10)
        self.assertEqual(plugin_snapshots["character"]["entity_count"], 2)
        self.assertEqual(plugin_snapshots["relationship"]["entity_count"], 1)
        self.assertEqual(plugin_snapshots["item"]["entity_count"], 2)
        self.assertEqual(plugin_snapshots["faction"]["entity_count"], 1)
        self.assertEqual(plugin_snapshots["location"]["entity_count"], 1)
        self.assertEqual(plugin_snapshots["world_rule"]["entity_count"], 1)
        self.assertEqual(plugin_snapshots["timeline"]["entity_count"], 1)
        self.assertEqual(plugin_snapshots["foreshadow"]["entity_count"], 1)
        self.assertIn("integrity_report", payload)
        self.assertEqual(payload["integrity_report"]["issue_count"], 0)
        relationship = plugin_snapshots["relationship"]["entities"][0]
        self.assertEqual(relationship["label"], "林舟->沈岚")
        item_labels = {
            entity["label"]
            for entity in plugin_snapshots["item"]["entities"]
        }
        self.assertEqual(item_labels, {"潮灯", "黑钥匙"})
        self.assertEqual(
            plugin_snapshots["faction"]["entities"][0]["label"],
            "黑钟会",
        )

    def test_story_bible_integrity_flags_unknown_relationship_target(self) -> None:
        context = self._base_context()
        context.characters = [
            {
                "id": str(uuid4()),
                "name": "林舟",
                "data": {
                    "relationships": [
                        {"target": "不存在的人", "status": "ally"},
                    ]
                },
                "version": 1,
                "created_chapter": 1,
            }
        ]

        report = validate_story_bible_integrity(context)

        self.assertEqual(report.issue_count, 1)
        self.assertEqual(report.blocking_issue_count, 1)
        self.assertEqual(report.issues[0].code, "relationship.unknown_character")

    def test_story_bible_integrity_flags_unknown_item_owner(self) -> None:
        context = self._base_context()
        context.items = [
            {
                "key": "item:black-key",
                "name": "黑钥匙",
                "owner": "失踪者",
                "location": None,
                "status": "active",
                "introduced_chapter": 1,
                "forbidden_holders": [],
                "version": 1,
            }
        ]

        report = validate_story_bible_integrity(context)
        issue_codes = {issue.code for issue in report.issues}

        self.assertIn("item.unknown_owner", issue_codes)

    def test_story_bible_integrity_flags_unknown_faction_leader(self) -> None:
        context = self._base_context()
        context.locations = [
            {
                "id": str(uuid4()),
                "name": "雾港",
                "data": {},
                "version": 1,
            }
        ]
        context.factions = [
            {
                "key": "faction:black-bell",
                "name": "黑钟会",
                "type": "cult",
                "leader": "失踪者",
                "members": ["林舟"],
                "territory": "雾港",
                "resources": [],
                "ideology": "以遗忘换秩序",
                "version": 1,
            }
        ]

        report = validate_story_bible_integrity(context)
        issue_codes = {issue.code for issue in report.issues}

        self.assertIn("faction.unknown_leader", issue_codes)

    def test_story_bible_integrity_flags_foreshadow_payoff_before_planting(self) -> None:
        context = self._base_context()
        context.foreshadowing = [
            {
                "id": str(uuid4()),
                "content": "黑钟会响两次。",
                "planted_chapter": 8,
                "payoff_chapter": 4,
                "status": "pending",
                "importance": 2,
            }
        ]

        report = validate_story_bible_integrity(context)

        self.assertEqual(report.issue_count, 1)
        self.assertEqual(report.blocking_issue_count, 1)
        self.assertEqual(report.issues[0].code, "foreshadow.invalid_payoff_order")

    def test_story_bible_integrity_flags_alias_conflict_inside_same_plugin(self) -> None:
        context = self._base_context()
        context.characters = [
            {
                "id": str(uuid4()),
                "name": "林舟",
                "data": {"aliases": ["小舟"]},
                "version": 1,
                "created_chapter": 1,
            },
            {
                "id": str(uuid4()),
                "name": "林周",
                "data": {"aliases": ["小舟"]},
                "version": 1,
                "created_chapter": 1,
            },
        ]

        report = validate_story_bible_integrity(context)

        self.assertEqual(report.issue_count, 1)
        self.assertEqual(report.blocking_issue_count, 0)
        self.assertEqual(report.issues[0].code, "entity.alias_conflict")
