from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from services.export_service import (
    build_chapter_export_filename,
    build_export_response,
    build_project_export_filename,
    render_chapter_export,
    render_project_export,
)


def make_project():
    return SimpleNamespace(
        title="Star Harbor",
        status="draft",
        genre="科幻",
        theme="归航与记忆",
        tone="克制",
        characters=[SimpleNamespace(name="Lin")],
        world_settings=[SimpleNamespace(title="Moon Oath")],
        locations=[SimpleNamespace(name="Harbor")],
        plot_threads=[SimpleNamespace(title="Find the map")],
        foreshadowing_items=[SimpleNamespace(content="The bell will ring twice.")],
        timeline_events=[SimpleNamespace(title="Arrival")],
        chapters=[
            SimpleNamespace(
                chapter_number=2,
                title="Fog Harbor",
                status="review",
                word_count=1234,
                content="A misty harbor scene.",
                outline={"objective": "Arrive"},
            ),
            SimpleNamespace(
                chapter_number=1,
                title="Departure",
                status="draft",
                word_count=980,
                content="Departure scene.",
                outline=None,
            ),
        ],
    )


def make_structured_project():
    project_id = uuid4()
    volume_one = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        volume_number=1,
        title="潮雾开港",
        summary="第一卷摘要",
        status="writing",
    )
    volume_two = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        volume_number=2,
        title="深海回声",
        summary="第二卷摘要",
        status="planning",
    )
    main_branch = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        source_branch_id=None,
        key="main",
        title="主线",
        description="标准叙事分支",
        status="active",
        is_default=True,
    )
    side_branch = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        source_branch_id=main_branch.id,
        key="alt-route",
        title="岔路线",
        description="偏离主线的改写",
        status="active",
        is_default=False,
    )
    return SimpleNamespace(
        title="Star Harbor",
        status="draft",
        genre="科幻",
        theme="归航与记忆",
        tone="克制",
        characters=[SimpleNamespace(name="Lin")],
        world_settings=[SimpleNamespace(title="Moon Oath")],
        locations=[SimpleNamespace(name="Harbor")],
        plot_threads=[SimpleNamespace(title="Find the map")],
        foreshadowing_items=[SimpleNamespace(content="The bell will ring twice.")],
        timeline_events=[SimpleNamespace(title="Arrival")],
        volumes=[volume_one, volume_two],
        branches=[main_branch, side_branch],
        chapters=[
            SimpleNamespace(
                chapter_number=2,
                title="Fog Harbor",
                status="review",
                word_count=1234,
                content="A misty harbor scene.",
                outline={"objective": "Arrive"},
                volume_id=volume_one.id,
                branch_id=main_branch.id,
                volume=volume_one,
                branch=main_branch,
            ),
            SimpleNamespace(
                chapter_number=1,
                title="Departure",
                status="draft",
                word_count=980,
                content="Departure scene.",
                outline=None,
                volume_id=volume_one.id,
                branch_id=main_branch.id,
                volume=volume_one,
                branch=main_branch,
            ),
            SimpleNamespace(
                chapter_number=1,
                title="Split Tide",
                status="writing",
                word_count=1400,
                content="An alternate route opens.",
                outline=None,
                volume_id=volume_two.id,
                branch_id=side_branch.id,
                volume=volume_two,
                branch=side_branch,
            ),
        ],
    )


def make_checkpointed_chapter():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        chapter_number=3,
        title="Gate Chapter",
        status="review",
        word_count=1600,
        content="Checkpoint heavy scene.",
        outline={"objective": "Pass the gate"},
        checkpoints=[
            SimpleNamespace(
                status="pending",
                title="Plot twist gate",
                checkpoint_type="story_turn",
                decision_note=None,
                created_at=now,
            ),
            SimpleNamespace(
                status="approved",
                title="Quality gate",
                checkpoint_type="quality_gate",
                decision_note="Looks good.",
                created_at=now.replace(microsecond=0),
            ),
        ],
        review_decisions=[
            SimpleNamespace(
                verdict="changes_requested",
                summary="结尾力度还不够。",
                created_at=now,
            )
        ],
    )


def make_canon_blocked_chapter():
    return SimpleNamespace(
        chapter_number=4,
        title="Canon Blocked",
        status="review",
        word_count=1800,
        content="Continuity risk scene.",
        outline={"objective": "Keep the canon stable"},
        quality_metrics={
            "evaluation_status": "fresh",
            "canon_issue_count": 2,
            "canon_blocking_issue_count": 1,
            "canon_summary": "Canon 校验发现 2 个问题，其中 1 个会阻断后续修订判断。",
        },
        checkpoints=[],
        review_decisions=[],
    )


def make_integrity_blocked_chapter():
    return SimpleNamespace(
        chapter_number=4,
        title="Integrity Blocked",
        status="review",
        word_count=1800,
        content="Truth layer risk scene.",
        outline={"objective": "Repair the truth layer"},
        quality_metrics={
            "evaluation_status": "fresh",
            "story_bible_integrity_issue_count": 3,
            "story_bible_integrity_blocking_issue_count": 2,
            "story_bible_integrity_summary": (
                "Story Bible 自校验发现 3 个问题，其中 2 个会阻断后续章节校验。"
            ),
        },
        checkpoints=[],
        review_decisions=[],
    )


def make_evaluation_blocked_chapter():
    return SimpleNamespace(
        chapter_number=5,
        title="Needs Recheck",
        status="review",
        word_count=1500,
        content="Recently edited scene.",
        outline={"objective": "Preserve continuity"},
        quality_metrics={
            "evaluation_status": "stale",
            "evaluation_stale_reason": "The chapter content changed after the latest evaluation.",
        },
        checkpoints=[],
        review_decisions=[],
    )


def make_checkpoint_stale_chapter():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        chapter_number=6,
        title="Checkpoint Recheck",
        status="review",
        word_count=1500,
        content="Recheck this scene.",
        outline={"objective": "Reconfirm the turn"},
        current_version_number=4,
        quality_metrics={
            "evaluation_status": "fresh",
        },
        checkpoints=[
            SimpleNamespace(
                status="approved",
                title="Story turn gate",
                checkpoint_type="story_turn",
                chapter_version_number=3,
                decision_note="旧版本已通过。",
                created_at=now,
            )
        ],
        review_decisions=[],
    )


class ExportServiceTests(unittest.TestCase):
    def test_render_project_markdown_contains_story_bible_and_sorted_chapters(self) -> None:
        project = make_project()

        content = render_project_export(project=project, export_format="md")

        self.assertIn("# Star Harbor", content)
        self.assertIn("## Story Bible", content)
        self.assertIn("### Characters", content)
        self.assertLess(content.index("### Chapter 1: Departure"), content.index("### Chapter 2: Fog Harbor"))

    def test_render_project_markdown_splits_virtual_item_and_faction_sections(self) -> None:
        project = make_project()
        project.world_settings = [
            SimpleNamespace(title="Moon Oath", key="rule-1", data={"cost": "memory"}),
            SimpleNamespace(
                title="Tide Lamp",
                key="item:tide-lamp",
                data={"entity_type": "item", "name": "Tide Lamp"},
            ),
            SimpleNamespace(
                title="Bell Keepers",
                key="faction:bell-keepers",
                data={"entity_type": "faction", "name": "Bell Keepers"},
            ),
        ]

        content = render_project_export(project=project, export_format="md")

        self.assertIn("### Items", content)
        self.assertIn("### Factions", content)
        self.assertIn("- Tide Lamp", content)
        self.assertIn("- Bell Keepers", content)
        self.assertEqual(content.count("- Moon Oath"), 1)

    def test_render_chapter_text_contains_outline_and_content(self) -> None:
        chapter = make_project().chapters[0]

        content = render_chapter_export(
            project_title="Star Harbor",
            chapter=chapter,
            export_format="txt",
        )

        self.assertIn("PROJECT: Star Harbor", content)
        self.assertIn("OUTLINE", content)
        self.assertIn('"objective": "Arrive"', content)
        self.assertIn("A misty harbor scene.", content)

    def test_build_export_response_sets_download_headers(self) -> None:
        response = build_export_response(
            content="hello",
            filename="星海归途.md",
        )

        disposition = response.headers["content-disposition"]
        self.assertIn("attachment;", disposition)
        self.assertIn("filename*=", disposition)

    def test_build_export_filenames(self) -> None:
        chapter = make_project().chapters[0]

        self.assertEqual(build_project_export_filename("Star Harbor", "md"), "star-harbor.md")
        self.assertEqual(
            build_chapter_export_filename("Star Harbor", chapter, "txt"),
            "star-harbor-chapter-002-fog-harbor.txt",
        )

    def test_render_project_markdown_groups_by_branch_and_volume(self) -> None:
        project = make_structured_project()

        content = render_project_export(project=project, export_format="md")

        self.assertIn("### Branch: 主线", content)
        self.assertIn("#### Volume 1: 潮雾开港", content)
        self.assertIn("### Branch: 岔路线", content)
        self.assertIn("#### Volume 2: 深海回声", content)
        self.assertLess(
            content.index("##### Chapter 1: Departure"),
            content.index("##### Chapter 2: Fog Harbor"),
        )

    def test_render_chapter_markdown_contains_branch_and_volume_metadata(self) -> None:
        chapter = make_structured_project().chapters[0]

        content = render_chapter_export(
            project_title="Star Harbor",
            chapter=chapter,
            export_format="md",
        )

        self.assertIn("- Branch: 主线", content)
        self.assertIn("- Branch Key: main", content)
        self.assertIn("- Volume Number: 1", content)
        self.assertIn("- Volume: 潮雾开港", content)

    def test_build_chapter_filename_uses_branch_and_volume_when_available(self) -> None:
        chapter = make_structured_project().chapters[0]

        self.assertEqual(
            build_chapter_export_filename("Star Harbor", chapter, "txt"),
            "star-harbor-main-v01-chapter-002-fog-harbor.txt",
        )

    def test_render_chapter_export_includes_gate_summary_and_checkpoints(self) -> None:
        chapter = make_checkpointed_chapter()

        content = render_chapter_export(
            project_title="Star Harbor",
            chapter=chapter,
            export_format="md",
        )

        self.assertIn("- Final Gate: blocked_pending", content)
        self.assertIn("- Pending Checkpoints: 1", content)
        self.assertIn("- Latest Checkpoint: Plot twist gate (pending)", content)
        self.assertIn("- Latest Review Verdict: changes_requested", content)
        self.assertIn("- Latest Review Summary: 结尾力度还不够。", content)
        self.assertIn("## Checkpoints", content)
        self.assertIn("[pending] Plot twist gate", content)

    def test_render_project_export_includes_checkpoint_summary(self) -> None:
        project = make_project()
        project.chapters.append(make_checkpointed_chapter())

        content = render_project_export(project=project, export_format="txt")

        self.assertIn("FINAL GATE: blocked_pending", content)
        self.assertIn("PENDING CHECKPOINTS: 1", content)
        self.assertIn("LATEST REVIEW VERDICT: changes_requested", content)
        self.assertIn("CHECKPOINTS:", content)
        self.assertIn("[pending] | Plot twist gate | TYPE=story_turn", content)

    def test_render_chapter_export_includes_canon_gate_summary(self) -> None:
        chapter = make_canon_blocked_chapter()

        content = render_chapter_export(
            project_title="Star Harbor",
            chapter=chapter,
            export_format="txt",
        )

        self.assertIn("FINAL GATE: blocked_canon", content)
        self.assertIn("GATE REASON:", content)
        self.assertIn("blocking continuity issue", content)

    def test_render_chapter_export_includes_integrity_gate_summary(self) -> None:
        chapter = make_integrity_blocked_chapter()

        content = render_chapter_export(
            project_title="Star Harbor",
            chapter=chapter,
            export_format="txt",
        )

        self.assertIn("FINAL GATE: blocked_integrity", content)
        self.assertIn("GATE REASON:", content)
        self.assertIn("truth-layer issues", content)

    def test_render_chapter_export_includes_evaluation_gate_summary(self) -> None:
        chapter = make_evaluation_blocked_chapter()

        content = render_chapter_export(
            project_title="Star Harbor",
            chapter=chapter,
            export_format="txt",
        )

        self.assertIn("FINAL GATE: blocked_evaluation", content)
        self.assertIn("GATE REASON:", content)
        self.assertIn("outdated", content)

    def test_render_chapter_export_includes_checkpoint_recheck_summary(self) -> None:
        chapter = make_checkpoint_stale_chapter()

        content = render_chapter_export(
            project_title="Star Harbor",
            chapter=chapter,
            export_format="txt",
        )

        self.assertIn("FINAL GATE: blocked_checkpoint", content)
        self.assertIn("GATE REASON:", content)
        self.assertIn("version 3", content)
        self.assertIn("version 4", content)
