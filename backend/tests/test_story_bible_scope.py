from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from core.errors import AppError
from memory.story_bible import load_story_bible_context
from services.project_service import (
    StoryBibleResolution,
    canonicalize_story_bible_branch_payload,
    _persist_branch_story_bible_sections,
    build_story_bible_branch_delta_payload,
    build_public_story_bible_sections,
    build_story_bible_section_override_details,
    build_story_bible_scope,
    calculate_story_bible_override_counts,
    combine_public_story_bible_world_settings,
    delete_story_bible_section_item,
    merge_story_bible_sections,
    resolve_story_bible_resolution,
    serialize_story_bible_chapter_summaries,
    serialize_story_bible_sections,
    upsert_story_bible_section_item,
)


def make_project():
    project_id = uuid4()
    main_branch = SimpleNamespace(
        id=uuid4(),
        source_branch_id=None,
        key="main",
        title="主线",
    )
    alt_branch = SimpleNamespace(
        id=uuid4(),
        source_branch_id=main_branch.id,
        key="alt",
        title="假如线",
    )
    deep_branch = SimpleNamespace(
        id=uuid4(),
        source_branch_id=alt_branch.id,
        key="deep",
        title="深潜线",
    )
    volume = SimpleNamespace(
        id=uuid4(),
        volume_number=1,
        title="第一卷",
    )
    character_id = uuid4()
    plot_thread_id = uuid4()
    return SimpleNamespace(
        id=project_id,
        title="潮声之城",
        genre="悬疑",
        theme="记忆与代价",
        tone="压抑",
        status="draft",
        characters=[
            SimpleNamespace(
                id=character_id,
                name="林澈",
                data={"status": "alive"},
                version=1,
                created_chapter=1,
            )
        ],
        world_settings=[
            SimpleNamespace(
                id=uuid4(),
                key="rule-1",
                title="潮汐法则",
                data={"cost": "memory"},
                version=1,
            )
        ],
        locations=[
            SimpleNamespace(
                id=uuid4(),
                name="雾港",
                data={"required_keywords": ["海雾"]},
                version=1,
            )
        ],
        plot_threads=[
            SimpleNamespace(
                id=plot_thread_id,
                title="潮门潜入",
                status="active",
                importance=1,
                data={"target": "钟塔"},
            )
        ],
        foreshadowing_items=[
            SimpleNamespace(
                id=uuid4(),
                content="黑钟会响两次",
                planted_chapter=2,
                payoff_chapter=8,
                status="pending",
                importance=2,
            )
        ],
        timeline_events=[
            SimpleNamespace(
                id=uuid4(),
                chapter_number=6,
                title="钟塔坍塌",
                data={"impact": "high"},
            )
        ],
        chapters=[
            SimpleNamespace(
                id=uuid4(),
                volume_id=volume.id,
                volume=volume,
                branch_id=main_branch.id,
                branch=main_branch,
                chapter_number=1,
                title="潮门初开",
                status="draft",
                word_count=1200,
            ),
            SimpleNamespace(
                id=uuid4(),
                volume_id=volume.id,
                volume=volume,
                branch_id=alt_branch.id,
                branch=alt_branch,
                chapter_number=1,
                title="假如线开端",
                status="writing",
                word_count=900,
            ),
            SimpleNamespace(
                id=uuid4(),
                volume_id=volume.id,
                volume=volume,
                branch_id=main_branch.id,
                branch=main_branch,
                chapter_number=2,
                title="黑钟回响",
                status="review",
                word_count=1500,
            ),
            SimpleNamespace(
                id=uuid4(),
                volume_id=volume.id,
                volume=volume,
                branch_id=deep_branch.id,
                branch=deep_branch,
                chapter_number=2,
                title="深潜入港",
                status="draft",
                word_count=1100,
            ),
        ],
        branches=[main_branch, alt_branch, deep_branch],
        _ids=SimpleNamespace(
            character_id=character_id,
            plot_thread_id=plot_thread_id,
            main_branch_id=main_branch.id,
            alt_branch_id=alt_branch.id,
            deep_branch_id=deep_branch.id,
        ),
    )


class StoryBibleScopeTests(unittest.TestCase):
    def test_upsert_story_bible_section_item_updates_matching_entity(self) -> None:
        first_character_id = str(uuid4())
        second_character_id = str(uuid4())
        rows = [
            {
                "id": first_character_id,
                "name": "林澈",
                "data": {"status": "alive"},
                "version": 1,
                "created_chapter": 1,
            },
            {
                "id": second_character_id,
                "name": "沈岚",
                "data": {"status": "alive"},
                "version": 1,
                "created_chapter": 2,
            },
        ]

        updated_rows = upsert_story_bible_section_item(
            rows,
            section_key="characters",
            item_payload={
                "id": first_character_id,
                "name": "林澈",
                "data": {"status": "missing"},
                "version": 2,
                "created_chapter": 1,
            },
        )

        self.assertEqual(len(updated_rows), 2)
        self.assertEqual(updated_rows[0]["data"]["status"], "missing")
        self.assertEqual(updated_rows[0]["version"], 2)
        self.assertEqual(updated_rows[1], rows[1])

    def test_upsert_story_bible_section_item_appends_new_entity(self) -> None:
        existing_id = str(uuid4())
        new_id = str(uuid4())
        rows = [
            {
                "id": existing_id,
                "name": "林澈",
                "data": {"status": "alive"},
                "version": 1,
                "created_chapter": 1,
            }
        ]

        updated_rows = upsert_story_bible_section_item(
            rows,
            section_key="characters",
            item_payload={
                "id": new_id,
                "name": "沈岚",
                "data": {"status": "alive"},
                "version": 1,
                "created_chapter": 2,
            },
        )

        self.assertEqual(len(updated_rows), 2)
        self.assertEqual(updated_rows[0]["id"], existing_id)
        self.assertEqual(updated_rows[1]["id"], new_id)

    def test_delete_story_bible_section_item_removes_matching_entity(self) -> None:
        first_character_id = str(uuid4())
        second_character_id = str(uuid4())
        rows = [
            {
                "id": first_character_id,
                "name": "林澈",
                "data": {"status": "alive"},
                "version": 1,
                "created_chapter": 1,
            },
            {
                "id": second_character_id,
                "name": "沈岚",
                "data": {"status": "alive"},
                "version": 1,
                "created_chapter": 2,
            },
        ]

        updated_rows = delete_story_bible_section_item(
            rows,
            section_key="characters",
            entity_key=f"id:{second_character_id}",
        )

        self.assertEqual(len(updated_rows), 1)
        self.assertEqual(updated_rows[0]["id"], first_character_id)

    def test_upsert_story_bible_section_item_supports_public_items_section(self) -> None:
        rows = [
            {
                "key": "item:mirror",
                "name": "回潮镜片",
                "type": "artifact",
                "rarity": "rare",
                "description": "能折返一段记忆",
                "effects": ["回溯"],
                "owner": "林澈",
                "location": "雾港",
                "status": "sealed",
                "introduced_chapter": 3,
                "forbidden_holders": ["沈岚"],
                "version": 1,
            }
        ]

        updated_rows = upsert_story_bible_section_item(
            rows,
            section_key="items",
            item_payload={
                "key": "item:mirror",
                "name": "回潮镜片",
                "type": "artifact",
                "rarity": "legendary",
                "description": "能折返一段记忆",
                "effects": ["回溯", "折光"],
                "owner": "林澈",
                "location": "雾港",
                "status": "sealed",
                "introduced_chapter": 3,
                "forbidden_holders": ["沈岚"],
                "version": 2,
            },
        )

        self.assertEqual(len(updated_rows), 1)
        self.assertEqual(updated_rows[0]["rarity"], "legendary")
        self.assertEqual(updated_rows[0]["version"], 2)

    def test_build_public_story_bible_sections_splits_virtual_world_setting_wrappers(self) -> None:
        sections = {
            "characters": [],
            "world_settings": [
                {
                    "id": "rule-1",
                    "key": "rule-1",
                    "title": "潮汐法则",
                    "data": {"cost": "memory"},
                    "version": 1,
                },
                {
                    "id": "item-1",
                    "key": "item:mirror",
                    "title": "回潮镜片",
                    "data": {
                        "entity_type": "item",
                        "item_type": "artifact",
                        "description": "能折返一段记忆",
                        "owner": "林澈",
                        "location": "雾港",
                        "status": "sealed",
                        "introduced_chapter": 3,
                        "forbidden_holders": ["沈岚"],
                        "items": [
                            {
                                "name": "回潮镜片",
                                "type": "artifact",
                                "rarity": "rare",
                                "effects": ["回溯"],
                            }
                        ],
                    },
                    "version": 2,
                },
                {
                    "id": "faction-1",
                    "key": "faction:tide",
                    "title": "潮汐会",
                    "data": {
                        "entity_type": "faction",
                        "name": "潮汐会",
                        "faction_type": "cult",
                        "scale": "city",
                        "description": "守望钟塔的人",
                        "goals": "封存深潮",
                        "leader": "钟守人",
                        "members": ["守钟者"],
                        "territory": "雾港钟塔",
                        "resources": ["钟塔", "密卷"],
                        "ideology": "以遗忘换秩序",
                    },
                    "version": 3,
                },
            ],
            "locations": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }

        public_sections = build_public_story_bible_sections(sections)

        self.assertEqual(len(public_sections["world_settings"]), 1)
        self.assertEqual(public_sections["world_settings"][0]["key"], "rule-1")
        self.assertEqual(public_sections["items"][0]["key"], "item:mirror")
        self.assertEqual(public_sections["items"][0]["owner"], "林澈")
        self.assertEqual(public_sections["factions"][0]["key"], "faction:tide")
        self.assertEqual(public_sections["factions"][0]["leader"], "钟守人")

    def test_combine_public_story_bible_world_settings_round_trips_virtual_sections(self) -> None:
        combined = combine_public_story_bible_world_settings(
            [
                {
                    "key": "rule-1",
                    "title": "潮汐法则",
                    "data": {"cost": "memory"},
                    "version": 1,
                }
            ],
            items=[
                {
                    "key": "item:mirror",
                    "name": "回潮镜片",
                    "type": "artifact",
                    "rarity": "rare",
                    "description": "能折返一段记忆",
                    "effects": ["回溯"],
                    "owner": "林澈",
                    "location": "雾港",
                    "status": "sealed",
                    "introduced_chapter": 3,
                    "forbidden_holders": ["沈岚"],
                    "version": 2,
                }
            ],
            factions=[
                {
                    "key": "faction:tide",
                    "name": "潮汐会",
                    "type": "cult",
                    "scale": "city",
                    "description": "守望钟塔的人",
                    "goals": "封存深潮",
                    "leader": "钟守人",
                    "members": ["守钟者"],
                    "territory": "雾港钟塔",
                    "resources": ["钟塔", "密卷"],
                    "ideology": "以遗忘换秩序",
                    "version": 3,
                }
            ],
        )

        public_sections = build_public_story_bible_sections(
            {
                "characters": [],
                "world_settings": combined,
                "locations": [],
                "plot_threads": [],
                "foreshadowing": [],
                "timeline_events": [],
            }
        )

        self.assertEqual(len(combined), 3)
        self.assertEqual(public_sections["world_settings"][0]["key"], "rule-1")
        self.assertEqual(public_sections["items"][0]["key"], "item:mirror")
        self.assertEqual(public_sections["factions"][0]["key"], "faction:tide")

    def test_build_public_story_bible_sections_prefers_native_rows_over_legacy_wrappers(self) -> None:
        sections = {
            "characters": [],
            "world_settings": [
                {
                    "key": "item:mirror",
                    "title": "回潮镜片",
                    "data": {
                        "entity_type": "item",
                        "item_type": "artifact",
                        "owner": "林澈",
                        "items": [
                            {
                                "name": "回潮镜片",
                                "type": "artifact",
                                "owner": "林澈",
                            }
                        ],
                    },
                    "version": 1,
                },
                {
                    "key": "faction:tide",
                    "title": "潮汐会",
                    "data": {
                        "entity_type": "faction",
                        "name": "潮汐会",
                        "faction_type": "cult",
                        "leader": "钟守人",
                    },
                    "version": 1,
                },
            ],
            "items": [
                {
                    "key": "item:mirror",
                    "name": "回潮镜片",
                    "type": "artifact",
                    "owner": "沈岚",
                    "effects": ["折光"],
                    "forbidden_holders": [],
                    "version": 3,
                }
            ],
            "factions": [
                {
                    "key": "faction:tide",
                    "name": "潮汐会",
                    "type": "cult",
                    "leader": "沈岚",
                    "members": [],
                    "resources": [],
                    "version": 2,
                }
            ],
            "locations": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }

        public_sections = build_public_story_bible_sections(sections)

        self.assertEqual(public_sections["items"][0]["owner"], "沈岚")
        self.assertEqual(public_sections["items"][0]["version"], 3)
        self.assertEqual(public_sections["factions"][0]["leader"], "沈岚")
        self.assertEqual(public_sections["factions"][0]["version"], 2)

    def test_canonicalize_story_bible_branch_payload_rewrites_legacy_wrapper_sections(self) -> None:
        base_sections = {
            "characters": [],
            "world_settings": [
                {
                    "key": "rule-1",
                    "title": "潮汐法则",
                    "data": {"cost": "memory"},
                    "version": 1,
                }
            ],
            "items": [],
            "factions": [],
            "locations": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }
        legacy_payload = {
            "world_settings": combine_public_story_bible_world_settings(
                base_sections["world_settings"],
                items=[
                    {
                        "key": "item:mirror",
                        "name": "回潮镜片",
                        "type": "artifact",
                        "owner": "林澈",
                        "effects": ["折光"],
                        "forbidden_holders": [],
                        "version": 2,
                    }
                ],
                factions=[
                    {
                        "key": "faction:tide",
                        "name": "潮汐会",
                        "type": "cult",
                        "leader": "钟守人",
                        "members": [],
                        "resources": [],
                        "version": 1,
                    }
                ],
            )
        }

        canonical_payload = canonicalize_story_bible_branch_payload(
            base_sections,
            legacy_payload,
        )
        merged_sections = merge_story_bible_sections(
            base_sections,
            branch_story_bible_payload=canonical_payload,
        )

        self.assertNotIn("world_settings", canonical_payload)
        self.assertIn("items", canonical_payload)
        self.assertIn("factions", canonical_payload)
        self.assertEqual(merged_sections["world_settings"][0]["key"], "rule-1")
        self.assertEqual(merged_sections["items"][0]["key"], "item:mirror")
        self.assertEqual(merged_sections["factions"][0]["key"], "faction:tide")

    def test_serialize_project_story_bible_sections_keeps_native_items_and_factions_separate(self) -> None:
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
                forbidden_holders=["沈岚"],
                version=2,
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
                resources=["钟塔", "密卷"],
                ideology="以遗忘换秩序",
                version=1,
            )
        ]

        sections = serialize_story_bible_sections(project)

        self.assertEqual(len(sections["world_settings"]), 1)
        self.assertEqual(sections["world_settings"][0]["key"], "rule-1")
        self.assertEqual(sections["items"][0]["key"], "item:mirror")
        self.assertEqual(sections["items"][0]["type"], "artifact")
        self.assertEqual(sections["factions"][0]["key"], "faction:tide")
        self.assertEqual(sections["factions"][0]["type"], "cult")

    def test_merge_story_bible_sections_reads_legacy_world_setting_payload_into_native_sections(self) -> None:
        base_sections = {
            "characters": [],
            "world_settings": [
                {
                    "key": "rule-1",
                    "title": "潮汐法则",
                    "data": {"cost": "memory"},
                    "version": 1,
                }
            ],
            "items": [
                {
                    "key": "item:mirror",
                    "name": "回潮镜片",
                    "type": "artifact",
                    "rarity": "rare",
                    "description": "能折返一段记忆",
                    "effects": ["回溯"],
                    "owner": "林澈",
                    "location": "雾港",
                    "status": "sealed",
                    "introduced_chapter": 3,
                    "forbidden_holders": [],
                    "version": 1,
                }
            ],
            "factions": [],
            "locations": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }
        legacy_payload = {
            "world_settings": combine_public_story_bible_world_settings(
                [
                    {
                        "key": "rule-1",
                        "title": "潮汐法则",
                        "data": {"cost": "memory"},
                        "version": 1,
                    }
                ],
                items=[
                    {
                        "key": "item:mirror",
                        "name": "回潮镜片",
                        "type": "artifact",
                        "rarity": "legendary",
                        "description": "能折返一段记忆",
                        "effects": ["回溯", "折光"],
                        "owner": "林澈",
                        "location": "雾港",
                        "status": "sealed",
                        "introduced_chapter": 3,
                        "forbidden_holders": [],
                        "version": 2,
                    }
                ],
                factions=[
                    {
                        "key": "faction:tide",
                        "name": "潮汐会",
                        "type": "cult",
                        "scale": "city",
                        "description": "守望钟塔的人",
                        "goals": "封存深潮",
                        "leader": "钟守人",
                        "members": ["守钟者"],
                        "territory": "雾港钟塔",
                        "resources": ["钟塔", "密卷"],
                        "ideology": "以遗忘换秩序",
                        "version": 1,
                    }
                ],
            )
        }

        merged = merge_story_bible_sections(
            base_sections,
            branch_story_bible_payload=legacy_payload,
        )

        self.assertEqual(merged["world_settings"][0]["key"], "rule-1")
        self.assertEqual(merged["items"][0]["key"], "item:mirror")
        self.assertEqual(merged["items"][0]["rarity"], "legendary")
        self.assertEqual(merged["factions"][0]["key"], "faction:tide")

    def test_branch_delta_payload_tracks_entity_level_changes(self) -> None:
        project = make_project()
        base_sections = serialize_story_bible_sections(project)
        current_sections = serialize_story_bible_sections(project)
        current_sections["characters"][0]["data"]["status"] = "dead"

        payload = build_story_bible_branch_delta_payload(
            base_sections,
            current_sections,
        )
        merged_sections = merge_story_bible_sections(
            base_sections,
            branch_story_bible_payload=payload,
        )

        self.assertIn("characters", payload)
        self.assertNotIn("locations", payload)
        self.assertEqual(payload["characters"]["mode"], "patch")
        self.assertNotIn("upserts", payload["characters"])
        self.assertEqual(len(payload["characters"]["patches"]), 1)
        self.assertEqual(
            payload["characters"]["patches"][0]["entity_key"],
            f'id:{base_sections["characters"][0]["id"]}',
        )
        self.assertEqual(
            payload["characters"]["patches"][0]["changes"],
            {"data": {"status": "dead"}},
        )
        self.assertEqual(merged_sections, current_sections)

    def test_branch_delta_payload_tracks_field_removal_with_patch(self) -> None:
        project = make_project()
        base_sections = serialize_story_bible_sections(project)
        current_sections = serialize_story_bible_sections(project)
        current_sections["characters"][0]["data"] = {}

        payload = build_story_bible_branch_delta_payload(
            base_sections,
            current_sections,
        )
        merged_sections = merge_story_bible_sections(
            base_sections,
            branch_story_bible_payload=payload,
        )

        self.assertEqual(payload["characters"]["mode"], "patch")
        self.assertEqual(len(payload["characters"]["patches"]), 1)
        self.assertEqual(
            payload["characters"]["patches"][0]["remove_fields"],
            ["data.status"],
        )
        self.assertEqual(merged_sections, current_sections)

    def test_branch_delta_payload_tracks_entity_removal(self) -> None:
        project = make_project()
        base_sections = serialize_story_bible_sections(project)
        current_sections = serialize_story_bible_sections(project)
        current_sections["foreshadowing"] = []

        payload = build_story_bible_branch_delta_payload(
            base_sections,
            current_sections,
        )
        merged_sections = merge_story_bible_sections(
            base_sections,
            branch_story_bible_payload=payload,
        )

        self.assertEqual(payload["foreshadowing"]["mode"], "patch")
        self.assertEqual(
            payload["foreshadowing"]["deletes"],
            [f'id:{base_sections["foreshadowing"][0]["id"]}'],
        )
        self.assertEqual(payload["foreshadowing"]["order"], [])
        self.assertEqual(merged_sections["foreshadowing"], [])

    def test_branch_sections_override_project_base_per_section(self) -> None:
        project = make_project()

        sections = serialize_story_bible_sections(
            project,
            branch_story_bible_payload={
                "characters": [
                    {
                        "id": "branch-char",
                        "name": "林澈",
                        "data": {"status": "dead"},
                        "version": 2,
                        "created_chapter": 1,
                    }
                ],
                "plot_threads": [
                    {
                        "id": "branch-thread",
                        "title": "林澈已坠海",
                        "status": "resolved",
                        "importance": 2,
                        "data": {},
                    }
                ],
            },
        )

        self.assertEqual(sections["characters"][0]["data"]["status"], "dead")
        self.assertEqual(sections["plot_threads"][0]["status"], "resolved")
        self.assertEqual(sections["locations"][0]["name"], "雾港")
        self.assertEqual(sections["timeline_events"][0]["title"], "钟塔坍塌")

    def test_scope_exposes_entity_level_override_details(self) -> None:
        branch = SimpleNamespace(
            id=uuid4(),
            key="deep",
            title="深潜线",
        )
        base_branch = SimpleNamespace(
            id=uuid4(),
            key="alt",
            title="假如线",
        )
        base_sections = {
            "characters": [
                {
                    "id": "char-1",
                    "name": "林澈",
                    "data": {"status": "alive"},
                    "version": 1,
                    "created_chapter": 1,
                }
            ],
            "world_settings": [],
            "locations": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }
        current_sections = {
            **base_sections,
            "characters": [
                {
                    "id": "char-1",
                    "name": "林澈",
                    "data": {"status": "missing"},
                    "version": 1,
                    "created_chapter": 1,
                }
            ],
        }

        scope = build_story_bible_scope(
            StoryBibleResolution(
                branch=branch,
                branch_story_bible=SimpleNamespace(payload={}),
                base_scope_kind="branch",
                base_branch=base_branch,
                sections=current_sections,
                base_sections=base_sections,
                section_override_counts={"characters": 1},
            )
        )

        self.assertEqual(len(scope.section_override_details), 1)
        self.assertEqual(scope.section_override_details[0].section_key, "characters")
        self.assertEqual(scope.section_override_details[0].item_count, 1)
        self.assertEqual(scope.section_override_details[0].items[0].entity_label, "林澈")
        self.assertEqual(scope.section_override_details[0].items[0].operation, "updated")
        self.assertEqual(
            scope.section_override_details[0].items[0].changed_fields,
            ["data.status"],
        )

    def test_scope_splits_virtual_item_and_faction_overrides_from_world_settings(self) -> None:
        branch = SimpleNamespace(
            id=uuid4(),
            key="deep",
            title="深潜线",
        )
        base_sections = {
            "characters": [],
            "world_settings": combine_public_story_bible_world_settings(
                [
                    {
                        "key": "rule-1",
                        "title": "潮汐法则",
                        "data": {"cost": "memory"},
                        "version": 1,
                    }
                ],
                items=[
                    {
                        "key": "item:mirror",
                        "name": "回潮镜片",
                        "type": "artifact",
                        "rarity": "rare",
                        "description": "能折返一段记忆",
                        "effects": ["回溯"],
                        "owner": "林澈",
                        "location": "雾港",
                        "status": "sealed",
                        "introduced_chapter": 3,
                        "forbidden_holders": [],
                        "version": 1,
                    }
                ],
                factions=[],
            ),
            "locations": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }
        current_sections = {
            **base_sections,
            "world_settings": combine_public_story_bible_world_settings(
                [
                    {
                        "key": "rule-1",
                        "title": "潮汐法则",
                        "data": {"cost": "memory"},
                        "version": 1,
                    }
                ],
                items=[
                    {
                        "key": "item:mirror",
                        "name": "回潮镜片",
                        "type": "artifact",
                        "rarity": "legendary",
                        "description": "能折返一段记忆",
                        "effects": ["回溯", "折光"],
                        "owner": "林澈",
                        "location": "雾港",
                        "status": "sealed",
                        "introduced_chapter": 3,
                        "forbidden_holders": [],
                        "version": 2,
                    }
                ],
                factions=[
                    {
                        "key": "faction:tide",
                        "name": "潮汐会",
                        "type": "cult",
                        "scale": "city",
                        "description": "守望钟塔的人",
                        "goals": "封存深潮",
                        "leader": "钟守人",
                        "members": ["守钟者"],
                        "territory": "雾港钟塔",
                        "resources": ["钟塔", "密卷"],
                        "ideology": "以遗忘换秩序",
                        "version": 1,
                    }
                ],
            ),
        }

        scope = build_story_bible_scope(
            StoryBibleResolution(
                branch=branch,
                branch_story_bible=SimpleNamespace(payload={}),
                base_scope_kind="project",
                base_branch=None,
                sections=current_sections,
                base_sections=base_sections,
                section_override_counts={"world_settings": 2},
            )
        )

        self.assertEqual(scope.changed_sections, ["factions", "items"])
        self.assertEqual(scope.section_override_counts, {"items": 1, "factions": 1})
        self.assertEqual(
            [item.section_key for item in scope.section_override_details],
            ["items", "factions"],
        )

    def test_reorder_only_change_counts_as_override(self) -> None:
        base_sections = {
            "characters": [],
            "world_settings": [],
            "locations": [
                {"id": "loc-1", "name": "雾港", "data": {}, "version": 1},
                {"id": "loc-2", "name": "钟塔", "data": {}, "version": 1},
            ],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }
        current_sections = {
            **base_sections,
            "locations": [
                {"id": "loc-2", "name": "钟塔", "data": {}, "version": 1},
                {"id": "loc-1", "name": "雾港", "data": {}, "version": 1},
            ],
        }

        counts = calculate_story_bible_override_counts(
            base_sections,
            current_sections,
        )
        details = build_story_bible_section_override_details(
            base_sections,
            current_sections,
        )

        self.assertEqual(counts, {"locations": 1})
        self.assertEqual(details[0]["section_key"], "locations")
        self.assertEqual(details[0]["items"][0]["operation"], "reordered")
        self.assertEqual(details[0]["items"][0]["changed_fields"], ["order"])

    def test_branch_chapter_summaries_only_include_current_branch(self) -> None:
        project = make_project()
        main_branch = project.branches[0]

        summaries = serialize_story_bible_chapter_summaries(
            project,
            branch=main_branch,
        )

        self.assertEqual(len(summaries), 2)
        self.assertEqual([item["chapter_number"] for item in summaries], [1, 2])
        self.assertTrue(all(item["branch_key"] == "main" for item in summaries))

    def test_scope_flags_project_inheritance_when_branch_snapshot_missing(self) -> None:
        branch = SimpleNamespace(
            id=uuid4(),
            key="alt",
            title="假如线",
        )

        scope = build_story_bible_scope(
            StoryBibleResolution(
                branch=branch,
                branch_story_bible=None,
                base_scope_kind="project",
                base_branch=None,
                sections={},
                base_sections={},
                section_override_counts={},
            )
        )

        self.assertEqual(scope.scope_kind, "branch")
        self.assertEqual(scope.branch_key, "alt")
        self.assertTrue(scope.inherits_from_project)
        self.assertFalse(scope.has_snapshot)

    def test_scope_tracks_parent_branch_base_metadata(self) -> None:
        branch = SimpleNamespace(
            id=uuid4(),
            key="deep",
            title="深潜线",
        )
        base_branch = SimpleNamespace(
            id=uuid4(),
            key="alt",
            title="假如线",
        )
        base_sections = {
            "characters": [
                {
                    "id": "char-1",
                    "name": "林澈",
                    "data": {"status": "alive"},
                    "version": 1,
                    "created_chapter": 1,
                }
            ],
            "world_settings": [],
            "locations": [],
            "plot_threads": [
                {
                    "id": "thread-1",
                    "title": "潮门潜入",
                    "status": "active",
                    "importance": 1,
                    "data": {"target": "钟塔"},
                }
            ],
            "foreshadowing": [],
            "timeline_events": [],
        }
        current_sections = {
            **base_sections,
            "characters": [
                {
                    "id": "char-1",
                    "name": "林澈",
                    "data": {"status": "missing"},
                    "version": 1,
                    "created_chapter": 1,
                }
            ],
            "plot_threads": [
                {
                    "id": "thread-1",
                    "title": "潮门潜入",
                    "status": "resolved",
                    "importance": 1,
                    "data": {"target": "钟塔"},
                }
            ],
        }

        scope = build_story_bible_scope(
            StoryBibleResolution(
                branch=branch,
                branch_story_bible=SimpleNamespace(payload={}),
                base_scope_kind="branch",
                base_branch=base_branch,
                sections=current_sections,
                base_sections=base_sections,
                section_override_counts={"plot_threads": 1, "characters": 2},
            )
        )

        self.assertEqual(scope.base_scope_kind, "branch")
        self.assertEqual(scope.base_branch_key, "alt")
        self.assertEqual(scope.changed_sections, ["characters", "plot_threads"])
        self.assertEqual(scope.total_override_count, 2)
        self.assertFalse(scope.inherits_from_project)


class StoryBibleResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolution_raises_when_branch_id_is_not_in_project(self) -> None:
        project = make_project()

        with self.assertRaises(AppError) as raised:
            await resolve_story_bible_resolution(
                session=SimpleNamespace(),
                project=project,
                branch_id=uuid4(),
            )

        self.assertEqual(raised.exception.code, "project.branch_not_found")

    async def test_persist_branch_sections_deletes_snapshot_when_effective_scope_matches_base(
        self,
    ) -> None:
        project = make_project()
        branch = project.branches[1]
        base_sections = serialize_story_bible_sections(project)
        existing_snapshot = SimpleNamespace(payload={"characters": {"mode": "patch"}})

        class FakeSession:
            def __init__(self) -> None:
                self.added: list[object] = []
                self.deleted: list[object] = []

            def add(self, value: object) -> None:
                self.added.append(value)

            async def delete(self, value: object) -> None:
                self.deleted.append(value)

        session = FakeSession()

        await _persist_branch_story_bible_sections(
            session,
            project=project,
            branch=branch,
            branch_story_bible=existing_snapshot,
            base_sections=base_sections,
            current_sections=base_sections,
        )

        self.assertEqual(session.added, [])
        self.assertEqual(session.deleted, [existing_snapshot])

    async def test_resolution_uses_parent_branch_effective_truth_as_base(self) -> None:
        project = make_project()
        alt_branch = project.branches[1]
        deep_branch = project.branches[2]
        project_sections = serialize_story_bible_sections(project)

        alt_sections = serialize_story_bible_sections(project)
        alt_sections["characters"][0]["data"]["status"] = "dead"

        deep_sections = serialize_story_bible_sections(project)
        deep_sections["characters"][0]["data"]["status"] = "dead"
        deep_sections["plot_threads"][0]["status"] = "resolved"

        snapshots = {
            alt_branch.id: build_story_bible_branch_delta_payload(
                project_sections,
                alt_sections,
            ),
            deep_branch.id: build_story_bible_branch_delta_payload(
                alt_sections,
                deep_sections,
            ),
        }

        async def fake_get_project_branch_story_bible(session, project_id, branch_id):
            payload = snapshots.get(branch_id)
            if payload is None:
                return None
            return SimpleNamespace(payload=payload)

        with patch(
            "services.project_service.get_project_branch_story_bible",
            new=fake_get_project_branch_story_bible,
        ):
            resolution = await resolve_story_bible_resolution(
                session=SimpleNamespace(),
                project=project,
                branch_id=deep_branch.id,
            )

        self.assertEqual(resolution.base_scope_kind, "branch")
        self.assertEqual(resolution.base_branch.id, alt_branch.id)
        self.assertEqual(resolution.sections["characters"][0]["data"]["status"], "dead")
        self.assertEqual(resolution.sections["plot_threads"][0]["status"], "resolved")
        self.assertEqual(resolution.section_override_counts, {"plot_threads": 1})

    async def test_load_story_bible_context_carries_scope_metadata(self) -> None:
        project = make_project()
        deep_branch = project.branches[2]
        alt_branch = project.branches[1]
        sections = serialize_story_bible_sections(
            project,
            branch_story_bible_payload={
                "characters": {
                    "mode": "patch",
                    "patches": [
                        {
                            "entity_key": f"id:{project._ids.character_id}",
                            "changes": {"data": {"status": "missing"}},
                        }
                    ],
                },
            },
        )
        sections["world_settings"] = combine_public_story_bible_world_settings(
            sections["world_settings"],
            items=[
                {
                    "key": "item:mirror",
                    "name": "回潮镜片",
                    "type": "artifact",
                    "rarity": "rare",
                    "description": "能折返一段记忆",
                    "effects": ["回溯"],
                    "owner": "林澈",
                    "location": "雾港",
                    "status": "sealed",
                    "introduced_chapter": 3,
                    "forbidden_holders": ["沈岚"],
                    "version": 2,
                }
            ],
            factions=[
                {
                    "key": "faction:tide",
                    "name": "潮汐会",
                    "type": "cult",
                    "scale": "city",
                    "description": "守望钟塔的人",
                    "goals": "封存深潮",
                    "leader": "钟守人",
                    "members": ["守钟者"],
                    "territory": "雾港钟塔",
                    "resources": ["钟塔", "密卷"],
                    "ideology": "以遗忘换秩序",
                    "version": 3,
                }
            ],
        )
        resolution = StoryBibleResolution(
            branch=deep_branch,
            branch_story_bible=SimpleNamespace(payload={}),
            base_scope_kind="branch",
            base_branch=alt_branch,
            sections=sections,
            base_sections=serialize_story_bible_sections(project),
            section_override_counts={"characters": 1},
        )

        async def fake_get_owned_project(*args, **kwargs):
            return project

        async def fake_resolve_story_bible_resolution(*args, **kwargs):
            return resolution

        with patch("memory.story_bible.get_owned_project", new=fake_get_owned_project):
            with patch(
                "memory.story_bible.resolve_story_bible_resolution",
                new=fake_resolve_story_bible_resolution,
            ):
                context = await load_story_bible_context(
                    session=SimpleNamespace(),
                    project_id=project.id,
                    user_id=uuid4(),
                    branch_id=deep_branch.id,
                )

        self.assertEqual(context.scope_kind, "branch")
        self.assertEqual(context.base_scope_kind, "branch")
        self.assertEqual(context.base_branch_key, "alt")
        self.assertTrue(context.has_snapshot)
        self.assertEqual(context.changed_sections, ["characters", "factions", "items"])
        self.assertEqual(
            context.section_override_counts,
            {"characters": 1, "factions": 1, "items": 1},
        )
        self.assertEqual(context.total_override_count, 3)
        self.assertEqual(context.characters[0]["data"]["status"], "missing")
        self.assertEqual(context.world_settings[0]["key"], "rule-1")
        self.assertEqual(context.items[0]["key"], "item:mirror")
        self.assertEqual(context.factions[0]["key"], "faction:tide")
        self.assertEqual(len(context.chapter_summaries), 1)
        self.assertEqual(context.chapter_summaries[0]["branch_key"], "deep")

    async def test_load_story_bible_context_raises_when_branch_id_is_not_in_project(self) -> None:
        project = make_project()

        async def fake_get_owned_project(*args, **kwargs):
            return project

        with patch("memory.story_bible.get_owned_project", new=fake_get_owned_project):
            with self.assertRaises(AppError) as raised:
                await load_story_bible_context(
                    session=SimpleNamespace(),
                    project_id=project.id,
                    user_id=uuid4(),
                    branch_id=uuid4(),
                )

        self.assertEqual(raised.exception.code, "project.branch_not_found")


if __name__ == "__main__":
    unittest.main()
