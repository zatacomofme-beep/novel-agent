from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from canon.base import CanonIntegrityReport, CanonIssue, CanonValidationReport
from evaluation.metrics import QualityMetrics
from memory.story_bible import StoryBibleContext
from services.evaluation_service import evaluate_existing_chapter


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def commit(self) -> None:
        self.commit_count += 1


class EvaluationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_evaluation_persists_canon_report_and_adjusts_score(self) -> None:
        session = FakeSession()
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            branch_id=uuid4(),
            chapter_number=5,
            title="回潮",
            content="林舟在尚未登场的章节里突然现身。",
            quality_metrics=None,
        )
        story_bible = StoryBibleContext(
            project_id=chapter.project_id,
            title="雾港",
            genre="悬疑",
            theme="代价",
            tone="压抑",
            status="draft",
            branch_id=chapter.branch_id,
            branch_title="假如线",
            branch_key="alt",
            scope_kind="branch",
            base_scope_kind="project",
            has_snapshot=True,
            changed_sections=["characters"],
            section_override_counts={"characters": 1},
            total_override_count=1,
            characters=[],
            world_settings=[],
            locations=[],
            plot_threads=[],
            foreshadowing=[],
            timeline_events=[],
            chapter_summaries=[],
        )
        metrics = QualityMetrics(
            fluency=0.84,
            vocabulary_richness=0.79,
            sentence_variation=0.76,
            plot_tightness=0.72,
            conflict_intensity=0.68,
            suspense=0.74,
            character_consistency=0.82,
            world_consistency=0.8,
            logic_coherence=0.78,
            timeline_consistency=0.83,
            emotional_resonance=0.71,
            imagery=0.69,
            dialogue_quality=0.73,
            theme_depth=0.75,
            ai_taste_score=0.14,
        )
        canon_report = CanonValidationReport(
            chapter_number=chapter.chapter_number,
            chapter_title=chapter.title,
            issue_count=1,
            blocking_issue_count=1,
            plugin_breakdown={"character": 1},
            referenced_entities=[],
            issues=[
                CanonIssue(
                    plugin_key="character",
                    code="character.before_introduction",
                    dimension="canon.character_introduction",
                    severity="high",
                    blocking=True,
                    message="林舟尚未在既定章节中登场。",
                    fix_hint="把这次出现改成间接提及，或提前补足正式登场章节。",
                )
            ],
            summary="Canon 校验发现 1 个问题，其中 1 个会阻断后续修订判断。",
        )
        integrity_report = CanonIntegrityReport(
            issue_count=2,
            blocking_issue_count=1,
            plugin_breakdown={"story_bible": 2},
            issues=[
                CanonIssue(
                    plugin_key="story_bible",
                    code="story_bible.missing_character_anchor",
                    dimension="story_bible_integrity.character",
                    severity="high",
                    blocking=True,
                    message="林舟缺少稳定的出场锚点，后续章节引用会失真。",
                    fix_hint="先补足角色锚点字段，再继续章节修订。",
                )
            ],
            summary="Story Bible 自校验发现 2 个问题，其中 1 个会阻断后续章节校验。",
        )

        async def fake_load_story_bible_context(*args, **kwargs):
            return story_bible

        with patch(
            "services.evaluation_service.load_story_bible_context",
            new=fake_load_story_bible_context,
        ):
            with patch(
                "services.evaluation_service.evaluate_chapter_text",
                return_value=(
                    metrics,
                    [
                        {
                            "dimension": "plot_tightness",
                            "severity": "medium",
                            "message": "中段张力略有下滑。",
                        }
                    ],
                    "启发式评估认为节奏仍有收紧空间。",
                ),
            ):
                with patch(
                    "services.evaluation_service.validate_story_bible_integrity",
                    return_value=integrity_report,
                ):
                    with patch(
                        "services.evaluation_service.validate_story_canon",
                        return_value=canon_report,
                    ):
                        report = await evaluate_existing_chapter(
                            session,
                            chapter,
                            user_id=uuid4(),
                        )

        self.assertEqual(session.commit_count, 1)
        self.assertEqual(len(session.added), 1)
        self.assertAlmostEqual(
            report.heuristic_overall_score,
            metrics.calculate_overall_score(),
            places=6,
        )
        self.assertLess(report.overall_score, report.heuristic_overall_score)
        self.assertEqual(report.story_bible_integrity_issue_count, 2)
        self.assertEqual(report.story_bible_integrity_blocking_issue_count, 1)
        self.assertIsNotNone(report.story_bible_integrity_report)
        self.assertEqual(report.canon_issue_count, 1)
        self.assertEqual(report.canon_blocking_issue_count, 1)
        self.assertIsNotNone(report.canon_report)
        self.assertEqual(len(report.issues), 3)
        self.assertEqual(report.issues[0].source, "heuristic")
        self.assertEqual(report.issues[1].source, "story_bible_integrity")
        self.assertTrue(report.issues[1].blocking)
        self.assertEqual(report.issues[2].source, "canon")
        self.assertTrue(report.issues[2].blocking)
        self.assertIn("Story Bible 自校验发现 2 个问题", report.summary)
        self.assertIn("Canon 校验发现 1 个问题", report.summary)
        self.assertEqual(report.context_snapshot["scope_kind"], "branch")
        self.assertEqual(report.context_snapshot["branch_key"], "alt")
        self.assertEqual(report.context_snapshot["total_override_count"], 1)
        self.assertEqual(chapter.quality_metrics["story_bible_integrity_issue_count"], 2)
        self.assertEqual(
            chapter.quality_metrics["story_bible_integrity_blocking_issue_count"],
            1,
        )
        self.assertEqual(
            chapter.quality_metrics["story_bible_integrity_report"]["issues"][0]["code"],
            "story_bible.missing_character_anchor",
        )
        self.assertEqual(chapter.quality_metrics["canon_issue_count"], 1)
        self.assertEqual(chapter.quality_metrics["canon_blocking_issue_count"], 1)
        self.assertEqual(chapter.quality_metrics["evaluation_status"], "fresh")
        self.assertIsNone(chapter.quality_metrics["evaluation_stale_reason"])
        self.assertIn("evaluation_updated_at", chapter.quality_metrics)
        self.assertEqual(session.added[0].metrics["story_bible_integrity_issue_count"], 2)
        self.assertEqual(
            session.added[0].metrics["story_bible_integrity_blocking_issue_count"],
            1,
        )
        self.assertEqual(
            chapter.quality_metrics["canon_report"]["issues"][0]["code"],
            "character.before_introduction",
        )
        self.assertEqual(
            session.added[0].metrics["canon_report"]["blocking_issue_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
