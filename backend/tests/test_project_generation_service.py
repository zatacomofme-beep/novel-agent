from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from memory.story_bible import StoryBibleContext
from services.legacy_project_generation_service import (
    dispatch_next_project_chapter_generation,
)
from services.project_generation_service import (
    _ResolvedNextChapterCandidate,
    preview_next_project_chapter_candidate,
    propose_story_bible_updates_from_generation,
)
from tasks.schemas import TaskState


def make_project():
    project_id = uuid4()
    branch_id = uuid4()
    volume_id = uuid4()
    branch = SimpleNamespace(
        id=branch_id,
        project_id=project_id,
        source_branch_id=None,
        key="main",
        title="主线",
        description=None,
        status="active",
        is_default=True,
        created_at=None,
    )
    volume = SimpleNamespace(
        id=volume_id,
        project_id=project_id,
        volume_number=1,
        title="第一卷：潮痕初启",
        summary=None,
        status="planning",
    )
    project = SimpleNamespace(
        id=project_id,
        user_id=uuid4(),
        title="潮痕之城",
        genre="悬疑奇幻",
        theme="记忆与代价",
        tone="压抑克制",
        status="draft",
        access_role="owner",
        owner_email="owner@example.com",
        collaborator_count=0,
        has_bootstrap_profile=True,
        has_novel_blueprint=True,
        bootstrap_profile={
            "genre": "悬疑奇幻",
            "theme": "记忆与代价",
            "tone": "压抑克制",
            "protagonist_name": "林澈",
            "protagonist_summary": "在失序边缘追查真相的调查员。",
            "world_background": "城市会把记忆切成潮痕。",
            "core_story": "主角追查一桩失踪案，却发现整座城都在主动抹去真相。",
            "novel_style": "都市悬疑奇幻",
            "prose_style": "冷峻、克制、贴身第三人称",
            "target_total_words": 120000,
            "target_chapter_words": 2500,
            "planned_chapter_count": 12,
        },
        novel_blueprint={
            "premise": "主角被卷入城市记忆潮痕的谜局。",
            "story_engine": "每次追查真相都会改写人物关系与风险等级。",
            "opening_hook": "一份失而复得的旧档案。",
            "writing_rules": ["每章必须推进事件"],
            "cast": [
                {"name": "林澈", "role": "protagonist"},
                {"name": "沈岚", "role": "supporting"},
            ],
            "plot_threads": [
                {
                    "title": "潮痕疑案",
                    "summary": "主线谜案",
                    "scope": "main",
                    "focus_characters": ["林澈"],
                    "planned_turns": ["线索出现", "局势升级"],
                }
            ],
            "foreshadowing": [],
            "timeline_beats": [],
            "volume_plans": [
                {
                    "volume_number": 1,
                    "title": "第一卷：潮痕初启",
                    "summary": "第一阶段",
                    "narrative_goal": "打破秩序",
                    "planned_chapter_count": 6,
                }
            ],
            "chapter_blueprints": [
                {
                    "volume_number": 1,
                    "chapter_number": 1,
                    "title": "第1章：失衡档案",
                    "objective": "让林澈接触失衡事件",
                    "summary": "档案意外回流，主角被迫入局。",
                    "expected_word_count": 2500,
                    "focus_characters": ["林澈"],
                    "key_locations": ["雾港档案馆"],
                    "plot_thread_titles": ["潮痕疑案"],
                    "foreshadowing_to_plant": ["档案被改写过"],
                },
                {
                    "volume_number": 1,
                    "chapter_number": 2,
                    "title": "第2章：失真回廊",
                    "objective": "追查第一条伪证来源",
                    "summary": "林澈进入回廊寻找伪证来源。",
                    "expected_word_count": 2500,
                    "focus_characters": ["林澈", "沈岚"],
                    "key_locations": ["失真回廊"],
                    "plot_thread_titles": ["潮痕疑案"],
                    "foreshadowing_to_plant": [],
                },
            ],
        },
        branches=[branch],
        volumes=[volume],
        collaborators=[],
        chapters=[],
        user=SimpleNamespace(email="owner@example.com"),
    )
    return project, branch, volume


class ProjectGenerationServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_preview_next_project_chapter_candidate_prefers_existing_blank_chapter(self) -> None:
        project, branch, volume = make_project()
        chapter_id = uuid4()
        project.chapters = [
            SimpleNamespace(
                id=chapter_id,
                project_id=project.id,
                volume_id=volume.id,
                branch_id=branch.id,
                chapter_number=1,
                title=None,
                content="",
                outline=None,
                status="draft",
            )
        ]

        candidate = preview_next_project_chapter_candidate(project, branch_id=branch.id)

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.chapter_id, chapter_id)
        self.assertEqual(candidate.chapter_number, 1)
        self.assertEqual(candidate.title, "第1章：失衡档案")
        self.assertEqual(candidate.generation_mode, "existing_draft")
        self.assertTrue(candidate.based_on_blueprint)

    def test_preview_next_project_chapter_candidate_continues_after_blueprint(self) -> None:
        project, branch, volume = make_project()
        project.chapters = [
            SimpleNamespace(
                id=uuid4(),
                project_id=project.id,
                volume_id=volume.id,
                branch_id=branch.id,
                chapter_number=1,
                title="第1章：失衡档案",
                content="已有正文",
                outline={"title": "第1章：失衡档案"},
                status="review",
            ),
            SimpleNamespace(
                id=uuid4(),
                project_id=project.id,
                volume_id=volume.id,
                branch_id=branch.id,
                chapter_number=2,
                title="第2章：失真回廊",
                content="已有正文",
                outline={"title": "第2章：失真回廊"},
                status="review",
            ),
        ]

        candidate = preview_next_project_chapter_candidate(project, branch_id=branch.id)

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.chapter_number, 3)
        self.assertEqual(candidate.generation_mode, "dynamic_continuation")
        self.assertTrue(candidate.based_on_blueprint)
        self.assertIn("第3章", candidate.title or "")

    async def test_dispatch_next_project_chapter_generation_returns_created_task(self) -> None:
        project, branch, volume = make_project()
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=project.id,
            volume_id=volume.id,
            branch_id=branch.id,
            chapter_number=2,
            title="第2章：失真回廊",
            content="",
            outline={"title": "第2章：失真回廊"},
            status="draft",
        )
        candidate = _ResolvedNextChapterCandidate(
            chapter=chapter,
            chapter_number=2,
            title="第2章：失真回廊",
            branch=branch,
            volume=volume,
            generation_mode="existing_draft",
            based_on_blueprint=True,
            outline_seed={"title": "第2章：失真回廊"},
        )
        session = SimpleNamespace()

        with patch(
            "services.legacy_project_generation_service._resolve_next_project_chapter_candidate",
            return_value=candidate,
        ), patch(
            "services.legacy_project_generation_service._materialize_candidate_chapter",
            AsyncMock(return_value=chapter),
        ), patch(
            "services.legacy_project_generation_service.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ), patch(
            "services.legacy_generation_dispatch_service.dispatch_legacy_generation_for_chapter",
            AsyncMock(
                return_value=TaskState(
                    task_id="task-1",
                    task_type="chapter_generation",
                    status="queued",
                    progress=5,
                    message="dispatched",
                    result={"dispatch_strategy": "celery"},
                )
            ),
        ):
            result = await dispatch_next_project_chapter_generation(
                session,
                project,
                actor_user_id=project.user_id,
                branch_id=branch.id,
            )

        self.assertEqual(result.chapter.id, chapter.id)
        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(result.next_chapter.chapter_number, 2)
        self.assertEqual(result.task.status, "queued")

    async def test_propose_story_bible_updates_from_generation_emits_pending_changes(self) -> None:
        project, branch, volume = make_project()
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=project.id,
            volume_id=volume.id,
            branch_id=branch.id,
            chapter_number=2,
            title="第2章：失真回廊",
        )
        story_bible = StoryBibleContext(
            project_id=project.id,
            title=project.title,
            genre=project.genre,
            theme=project.theme,
            tone=project.tone,
            status=project.status,
            branch_id=branch.id,
            branch_title=branch.title,
            branch_key=branch.key,
            characters=[
                {
                    "id": str(uuid4()),
                    "name": "林澈",
                    "data": {},
                    "version": 1,
                    "created_chapter": 1,
                }
            ],
            world_settings=[],
            items=[],
            factions=[],
            locations=[
                {
                    "id": str(uuid4()),
                    "name": "失真回廊",
                    "data": {},
                    "version": 1,
                }
            ],
            plot_threads=[
                {
                    "id": str(uuid4()),
                    "title": "潮痕疑案",
                    "status": "planned",
                    "importance": 1,
                    "data": {},
                }
            ],
            foreshadowing=[],
            timeline_events=[],
            chapter_summaries=[],
        )
        session = SimpleNamespace(
            commit=AsyncMock(),
            execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        )
        captured_triggers: list[str] = []

        async def fake_auto_trigger(*args, **kwargs):
            captured_triggers.append(kwargs["trigger_type"])
            return SimpleNamespace(
                id=uuid4(),
                changed_section=kwargs["trigger_type"],
            )

        with patch(
            "services.project_generation_service.auto_trigger_story_bible_change",
            AsyncMock(side_effect=fake_auto_trigger),
        ):
            proposals = await propose_story_bible_updates_from_generation(
                session,
                project=project,
                chapter=chapter,
                story_bible=story_bible,
                chapter_outline_seed={
                    "title": "第2章：失真回廊",
                    "objective": "追查第一条伪证来源",
                    "summary": "林澈进入回廊寻找伪证来源。",
                    "focus_characters": ["林澈"],
                    "key_locations": ["失真回廊"],
                    "plot_thread_titles": ["潮痕疑案"],
                    "foreshadowing_to_plant": ["回廊里有人先来过"],
                },
                final_outline={
                    "title": "第2章：失真回廊",
                    "objective": "追查第一条伪证来源",
                },
            )

        self.assertEqual(len(proposals), 5)
        self.assertEqual(
            captured_triggers,
            [
                "character_level_up",
                "location_status_changed",
                "plot_thread_progressed",
                "foreshadowing_fulfilled",
                "timeline_event_occurred",
            ],
        )
        session.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
