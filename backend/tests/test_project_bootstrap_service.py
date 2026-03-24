from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from memory.story_bible import StoryBibleContext
from services.project_bootstrap_service import (
    generate_project_blueprint,
    get_project_bootstrap_state,
)


def make_story_bible(project_id, branch_id) -> StoryBibleContext:
    return StoryBibleContext(
        project_id=project_id,
        title="潮痕之城",
        genre="悬疑奇幻",
        theme="记忆与代价",
        tone="压抑克制",
        status="draft",
        branch_id=branch_id,
        branch_title="主线",
        branch_key="main",
        scope_kind="branch",
        base_scope_kind="project",
        has_snapshot=True,
        changed_sections=[],
        section_override_counts={},
        total_override_count=0,
        characters=[
            {
                "id": str(uuid4()),
                "name": "林澈",
                "data": {"role": "protagonist"},
                "version": 1,
                "created_chapter": 1,
            }
        ],
        world_settings=[],
        items=[],
        factions=[],
        locations=[],
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
        title="第一卷",
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
        has_novel_blueprint=False,
        bootstrap_profile={
            "genre": "悬疑奇幻",
            "theme": "记忆与代价",
            "tone": "压抑克制",
            "protagonist_name": "林澈",
            "protagonist_summary": "在失序边缘追查真相的调查员。",
            "supporting_cast": [
                {
                    "name": "沈岚",
                    "role": "supporting",
                    "summary": "与主角立场微妙的关键配角。",
                }
            ],
            "world_background": "城市会把记忆切成潮痕，越追查真相越容易失去自身。",
            "core_story": "主角追查一桩失踪案，却发现整座城都在主动抹去真相。",
            "novel_style": "都市悬疑奇幻",
            "prose_style": "冷峻、克制、贴身第三人称",
            "target_total_words": 120000,
            "target_chapter_words": 2500,
            "planned_chapter_count": 12,
        },
        novel_blueprint=None,
        branches=[branch],
        volumes=[volume],
        collaborators=[],
        chapters=[],
        user=SimpleNamespace(email="owner@example.com"),
    )
    return project, branch, volume


class ProjectBootstrapServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_project_bootstrap_state_reads_profile_and_story_counts(self) -> None:
        project, branch, _volume = make_project()
        project.novel_blueprint = {
            "premise": "主角被卷入更大骗局。",
            "story_engine": "每次调查都会撕开新的代价。",
            "opening_hook": "一份失而复得的档案。",
            "writing_rules": ["每章推进事件"],
            "cast": [{"name": "林澈", "role": "protagonist"}],
            "plot_threads": [{"title": "潮痕疑案", "summary": "主线", "scope": "main"}],
            "foreshadowing": [],
            "timeline_beats": [],
            "volume_plans": [
                {
                    "volume_number": 1,
                    "title": "第一卷：风暴初启",
                    "summary": "开局",
                    "narrative_goal": "打破秩序",
                    "planned_chapter_count": 6,
                }
            ],
            "chapter_blueprints": [
                {
                    "volume_number": 1,
                    "chapter_number": 1,
                    "title": "第1章：失衡",
                    "objective": "打破日常",
                    "summary": "开局",
                    "focus_characters": ["林澈"],
                    "key_locations": ["主场景"],
                    "plot_thread_titles": ["潮痕疑案"],
                    "foreshadowing_to_plant": [],
                }
            ],
        }
        project.has_novel_blueprint = True

        with patch(
            "services.project_bootstrap_service.load_story_bible_context",
            AsyncMock(return_value=make_story_bible(project.id, branch.id)),
        ):
            state = await get_project_bootstrap_state(
                SimpleNamespace(),
                project,
                actor_user_id=project.user_id,
                branch_id=branch.id,
            )

        self.assertEqual(state.profile.protagonist_name, "林澈")
        self.assertIsNotNone(state.blueprint)
        self.assertEqual(state.story_state.character_count, 1)
        self.assertEqual(state.story_state.plot_thread_count, 1)
        self.assertEqual(state.story_state.chapter_blueprint_count, 1)

    async def test_generate_project_blueprint_falls_back_and_persists_project_state(self) -> None:
        project, branch, _volume = make_project()
        session = SimpleNamespace(
            add=MagicMock(),
            flush=AsyncMock(),
            commit=AsyncMock(),
        )

        with patch(
            "services.project_bootstrap_service.load_story_bible_context",
            AsyncMock(return_value=make_story_bible(project.id, branch.id)),
        ), patch(
            "services.project_bootstrap_service.model_gateway.generate_text",
            AsyncMock(return_value=SimpleNamespace(content="not valid json")),
        ), patch(
            "services.project_bootstrap_service.replace_story_bible",
            AsyncMock(),
        ), patch(
            "services.project_bootstrap_service.get_owned_project",
            AsyncMock(return_value=project),
        ):
            state = await generate_project_blueprint(
                session,
                project,
                actor_user_id=project.user_id,
                branch_id=branch.id,
                create_missing_chapters=False,
            )

        self.assertIsNotNone(project.novel_blueprint)
        self.assertEqual(state.profile.target_chapter_words, 2500)
        self.assertIsNotNone(state.blueprint)
        self.assertGreater(len(state.blueprint.chapter_blueprints), 0)
        self.assertEqual(state.story_state.branch_id, branch.id)


if __name__ == "__main__":
    unittest.main()
