from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from services.dashboard_service import (
    build_dashboard_overview_payload,
    build_project_quality_trend_payload,
)


class DashboardServiceTests(unittest.TestCase):
    def test_build_dashboard_overview_payload_aggregates_workspace_metrics(self) -> None:
        project_id = uuid4()
        chapter_one = SimpleNamespace(
            id=uuid4(),
            chapter_number=1,
            title="第一章",
            status="review",
            word_count=1800,
            quality_metrics={"overall_score": 0.82, "ai_taste_score": 0.21},
            updated_at=datetime.now(timezone.utc),
        )
        chapter_two = SimpleNamespace(
            id=uuid4(),
            chapter_number=2,
            title="第二章",
            status="writing",
            word_count=1500,
            quality_metrics={"overall_score": 0.68, "ai_taste_score": 0.39},
            updated_at=datetime.now(timezone.utc),
        )
        overview = build_dashboard_overview_payload(
            projects=[
                SimpleNamespace(
                    id=project_id,
                    title="雾港",
                    genre="悬疑",
                    status="writing",
                    bootstrap_profile={"genre": "悬疑"},
                    novel_blueprint={"premise": "海雾谋杀"},
                    updated_at=datetime.now(timezone.utc),
                    chapters=[chapter_one, chapter_two],
                )
            ],
            active_tasks=[
                SimpleNamespace(
                    task_id="task-1",
                    task_type="chapter_generation",
                    status="running",
                    progress=70,
                    message="Working",
                    project_id=project_id,
                    chapter_id=uuid4(),
                    updated_at=datetime.now(timezone.utc),
                )
            ],
            recent_tasks=[
                SimpleNamespace(
                    task_id="task-2",
                    task_type="chapter_generation",
                    status="succeeded",
                    progress=100,
                    message="Chapter ready",
                    project_id=project_id,
                    chapter_id=chapter_two.id,
                    chapter=chapter_two,
                    updated_at=datetime.now(timezone.utc),
                )
            ],
            preference_profile=SimpleNamespace(
                id=uuid4(),
                user_id=uuid4(),
                prose_style="sharp",
                narrative_mode="close_third",
                pacing_preference="fast",
                dialogue_preference="balanced",
                tension_preference="high_tension",
                sensory_density="focused",
                favored_elements=["动作链"],
                banned_patterns=[],
                custom_style_notes=None,
                updated_at=datetime.now(timezone.utc),
            ),
        )

        self.assertEqual(overview["total_projects"], 1)
        self.assertEqual(overview["total_chapters"], 2)
        self.assertEqual(overview["total_words"], 3300)
        self.assertEqual(overview["active_task_count"], 1)
        self.assertEqual(overview["review_ready_chapters"], 1)
        self.assertEqual(overview["chapters_by_status"]["review"], 1)
        self.assertEqual(overview["chapters_by_status"]["writing"], 1)
        self.assertAlmostEqual(overview["average_overall_score"], 0.75, places=2)
        self.assertAlmostEqual(overview["average_ai_taste_score"], 0.30, places=2)
        self.assertEqual(overview["project_summaries"][0]["risk_chapter_count"], 1)
        self.assertEqual(overview["project_summaries"][0]["active_task_count"], 1)
        self.assertEqual(overview["project_summaries"][0]["trend_direction"], "declining")
        self.assertAlmostEqual(overview["project_summaries"][0]["score_delta"], -0.14, places=2)
        self.assertEqual(overview["project_summaries"][0]["access_role"], "owner")
        self.assertEqual(overview["project_summaries"][0]["collaborator_count"], 0)
        self.assertTrue(overview["project_summaries"][0]["has_bootstrap_profile"])
        self.assertTrue(overview["project_summaries"][0]["has_novel_blueprint"])
        self.assertEqual(len(overview["project_quality_trends"]), 1)
        self.assertEqual(
            overview["project_quality_trends"][0]["chapter_points"][0]["chapter_number"],
            1,
        )
        self.assertEqual(overview["project_quality_trends"][0]["visible_chapter_count"], 2)
        self.assertEqual(overview["project_quality_trends"][0]["access_role"], "owner")
        self.assertAlmostEqual(
            overview["project_quality_trends"][0]["average_overall_score"],
            0.75,
            places=2,
        )
        self.assertEqual(
            overview["project_quality_trends"][0]["status_breakdown"]["review"],
            1,
        )
        self.assertEqual(overview["recent_tasks"][0]["chapter_number"], 2)

    def test_build_project_quality_trend_payload_reports_direction_and_risks(self) -> None:
        payload = build_project_quality_trend_payload(
            SimpleNamespace(
                id=uuid4(),
                title="雾港",
                status="writing",
                updated_at=datetime.now(timezone.utc),
                chapters=[
                    SimpleNamespace(
                        id=uuid4(),
                        chapter_number=1,
                        title="第一章",
                        status="review",
                        word_count=1800,
                        quality_metrics={"overall_score": 0.62, "ai_taste_score": 0.41},
                        updated_at=datetime.now(timezone.utc),
                    ),
                    SimpleNamespace(
                        id=uuid4(),
                        chapter_number=2,
                        title="第二章",
                        status="review",
                        word_count=2100,
                        quality_metrics={"overall_score": 0.78, "ai_taste_score": 0.29},
                        updated_at=datetime.now(timezone.utc),
                    ),
                    SimpleNamespace(
                        id=uuid4(),
                        chapter_number=3,
                        title="第三章",
                        status="final",
                        word_count=2300,
                        quality_metrics={"overall_score": 0.84, "ai_taste_score": 0.19},
                        updated_at=datetime.now(timezone.utc),
                    ),
                ],
            )
        )

        self.assertEqual(payload["trend_direction"], "improving")
        self.assertAlmostEqual(payload["score_delta"], 0.22, places=2)
        self.assertAlmostEqual(payload["ai_taste_delta"], -0.22, places=2)
        self.assertEqual(payload["latest_overall_score"], 0.84)
        self.assertEqual(payload["risk_chapter_numbers"], [1])
        self.assertAlmostEqual(payload["coverage_ratio"], 1.0, places=2)
        self.assertEqual(payload["visible_chapter_count"], 3)
        self.assertAlmostEqual(payload["average_overall_score"], 0.7467, places=3)
        self.assertAlmostEqual(payload["average_ai_taste_score"], 0.2967, places=3)
        self.assertEqual(payload["review_ready_chapters"], 3)
        self.assertEqual(payload["final_chapters"], 1)
        self.assertEqual(payload["range_start_chapter_number"], 1)
        self.assertEqual(payload["range_end_chapter_number"], 3)
        self.assertEqual(payload["strongest_chapter"]["chapter_number"], 3)
        self.assertEqual(payload["weakest_chapter"]["chapter_number"], 1)
        self.assertEqual(payload["access_role"], "owner")
        self.assertEqual(payload["collaborator_count"], 0)

    def test_build_project_quality_trend_payload_honors_chapter_limit(self) -> None:
        payload = build_project_quality_trend_payload(
            SimpleNamespace(
                id=uuid4(),
                title="雾港",
                status="writing",
                updated_at=datetime.now(timezone.utc),
                chapters=[
                    SimpleNamespace(
                        id=uuid4(),
                        chapter_number=1,
                        title="第一章",
                        status="draft",
                        word_count=1000,
                        quality_metrics={"overall_score": 0.61, "ai_taste_score": 0.4},
                        updated_at=datetime.now(timezone.utc),
                    ),
                    SimpleNamespace(
                        id=uuid4(),
                        chapter_number=2,
                        title="第二章",
                        status="review",
                        word_count=1200,
                        quality_metrics={"overall_score": 0.72, "ai_taste_score": 0.31},
                        updated_at=datetime.now(timezone.utc),
                    ),
                    SimpleNamespace(
                        id=uuid4(),
                        chapter_number=3,
                        title="第三章",
                        status="final",
                        word_count=1500,
                        quality_metrics={"overall_score": 0.88, "ai_taste_score": 0.18},
                        updated_at=datetime.now(timezone.utc),
                    ),
                ],
            ),
            chapter_limit=2,
        )

        self.assertEqual(payload["visible_chapter_count"], 2)
        self.assertEqual(payload["range_start_chapter_number"], 2)
        self.assertEqual(payload["range_end_chapter_number"], 3)
        self.assertEqual([point["chapter_number"] for point in payload["chapter_points"]], [2, 3])
