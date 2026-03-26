from __future__ import annotations

import unittest
from datetime import datetime

from scripts.story_engine_smoke_support import (
    DEFAULT_EMAIL_PREFIX,
    FIXED_BRANCH_LOCATION_NAME,
    SCENARIO_ALL,
    SCENARIO_BRANCH_SCOPE,
    SCENARIO_CLOUD_DRAFT,
    SCENARIO_MAINLINE,
    SmokeAssertionError,
    assert_branch_scope_summary,
    assert_cloud_draft_summary,
    assert_mainline_summary,
    build_smoke_email,
    resolve_selected_scenarios,
)


class StoryEngineLiveSmokeAssertionsTests(unittest.TestCase):
    def test_build_smoke_email_uses_custom_prefix(self) -> None:
        email = build_smoke_email("novel-smoke", now=datetime(2026, 3, 26, 8, 9, 10))
        self.assertEqual(email, "novel-smoke-20260326080910@example.com")

    def test_build_smoke_email_falls_back_to_default_prefix(self) -> None:
        email = build_smoke_email("   ", now=datetime(2026, 3, 26, 8, 9, 10))
        self.assertEqual(email, f"{DEFAULT_EMAIL_PREFIX}-20260326080910@example.com")

    def test_resolve_selected_scenarios_expands_all(self) -> None:
        self.assertEqual(
            resolve_selected_scenarios(SCENARIO_ALL),
            [SCENARIO_MAINLINE, SCENARIO_BRANCH_SCOPE, SCENARIO_CLOUD_DRAFT],
        )

    def test_resolve_selected_scenarios_keeps_single_scenario(self) -> None:
        self.assertEqual(resolve_selected_scenarios(SCENARIO_BRANCH_SCOPE), [SCENARIO_BRANCH_SCOPE])

    def test_resolve_selected_scenarios_raises_for_unknown_scenario(self) -> None:
        with self.assertRaises(SmokeAssertionError):
            resolve_selected_scenarios("unknown")

    def test_mainline_summary_passes_with_expected_fields(self) -> None:
        summary = {
            "outline": {
                "level_1_count": 1,
                "level_2_count": 2,
                "level_3_count": 3,
                "workflow_event_count": 9,
            },
            "guard": {
                "should_pause": True,
                "alert_count": 2,
            },
            "stream": {
                "event_count": 6,
                "final_event": {"event": "done"},
                "draft_length": 680,
            },
            "chapter": {
                "chapter_id": "chapter-1",
                "status": "final",
                "current_version_number": 2,
            },
            "final_optimize": {
                "final_draft_length": 720,
                "chapter_summary_id": "summary-1",
                "workflow_event_count": 12,
            },
            "next_chapter": {
                "chapter_number": 2,
            },
        }

        assert_mainline_summary(summary)

    def test_mainline_summary_raises_when_guard_does_not_pause(self) -> None:
        summary = {
            "outline": {
                "level_1_count": 1,
                "level_2_count": 1,
                "level_3_count": 1,
                "workflow_event_count": 4,
            },
            "guard": {
                "should_pause": False,
                "alert_count": 0,
            },
            "stream": {
                "event_count": 4,
                "final_event": {"event": "done"},
                "draft_length": 300,
            },
            "chapter": {
                "chapter_id": "chapter-1",
                "status": "final",
                "current_version_number": 1,
            },
            "final_optimize": {
                "final_draft_length": 320,
                "chapter_summary_id": "summary-1",
                "workflow_event_count": 8,
            },
            "next_chapter": {
                "chapter_number": 2,
            },
        }

        with self.assertRaises(SmokeAssertionError):
            assert_mainline_summary(summary)

    def test_branch_scope_summary_passes_with_isolated_branch_data(self) -> None:
        summary = {
            "default_branch_id": "branch-default",
            "new_branch_id": "branch-side",
            "new_volume_id": "volume-side",
            "branch_chapter_numbers": [7],
            "default_chapter_numbers": [1, 2],
            "branch_location_names": [FIXED_BRANCH_LOCATION_NAME],
            "default_location_names": ["主城"],
        }

        assert_branch_scope_summary(summary)

    def test_branch_scope_summary_raises_when_branch_data_leaks(self) -> None:
        summary = {
            "default_branch_id": "branch-default",
            "new_branch_id": "branch-side",
            "new_volume_id": "volume-side",
            "branch_chapter_numbers": [7],
            "default_chapter_numbers": [1, 7],
            "branch_location_names": [FIXED_BRANCH_LOCATION_NAME],
            "default_location_names": [FIXED_BRANCH_LOCATION_NAME],
        }

        with self.assertRaises(SmokeAssertionError):
            assert_branch_scope_summary(summary)

    def test_cloud_draft_summary_passes_after_cleanup(self) -> None:
        summary = {
            "draft_snapshot_id": "draft-1",
            "listed_count_after_upsert": 1,
            "detail_matches": True,
            "deleted": True,
            "deleted_absent_from_list": True,
        }

        assert_cloud_draft_summary(summary)

    def test_cloud_draft_summary_raises_when_delete_does_not_take_effect(self) -> None:
        summary = {
            "draft_snapshot_id": "draft-1",
            "listed_count_after_upsert": 1,
            "detail_matches": True,
            "deleted": True,
            "deleted_absent_from_list": False,
        }

        with self.assertRaises(SmokeAssertionError):
            assert_cloud_draft_summary(summary)
