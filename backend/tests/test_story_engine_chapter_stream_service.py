from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from services.story_engine_workflow_service import (
    _build_stream_context,
    _compose_stream_paragraph,
    run_chapter_stream_generate,
)


def _mock_generation(
    text: str,
    *,
    provider: str = "mock",
    model: str = "mock-model",
    used_fallback: bool = False,
    metadata: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        content=text,
        provider=provider,
        model=model,
        used_fallback=used_fallback,
        metadata=metadata or {},
    )


class StoryEngineChapterStreamServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_pause_event_contains_resume_metadata(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        generate_mock = AsyncMock(return_value=_mock_generation("第一段正文"))

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.build_workspace",
            AsyncMock(
                return_value={
                    "characters": [],
                    "items": [],
                    "world_rules": [],
                    "foreshadows": [],
                }
            ),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={},
        ), patch(
            "services.story_engine_workflow_service._resolve_stream_outline_text",
            AsyncMock(return_value="开场推进\n结尾钩子"),
        ), patch(
            "services.story_engine_workflow_service._build_stream_beats",
            return_value=["开场推进", "结尾钩子"],
        ), patch(
            "services.story_engine_workflow_service.generate_story_stream_paragraph",
            generate_mock,
        ), patch(
            "services.story_engine_workflow_service.run_realtime_guard",
            AsyncMock(
                return_value={
                    "passed": False,
                    "should_pause": True,
                    "alerts": [
                        {
                            "severity": "high",
                            "title": "人设冲突",
                            "detail": "主角明明怕水，这里却毫无迟疑地跳海。",
                            "source": "guardian",
                            "suggestion": "补出迟疑和代价。",
                        }
                    ],
                    "repair_options": ["补出主角对水的本能恐惧，再安排他硬着头皮下水。"],
                    "arbitration_note": "这一处如果不修，后面的人设会直接崩。",
                }
            ),
        ):
            events: list[dict] = []
            async for event in run_chapter_stream_generate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_number=7,
                chapter_title="海上夜奔",
                outline_id=None,
                current_outline="开场推进\n结尾钩子",
                recent_chapters=[],
                existing_text="",
                style_sample=None,
                target_word_count=2400,
                target_paragraph_count=2,
            ):
                events.append(event)

        guard_event = next(item for item in events if item["event"] == "guard")
        self.assertEqual(guard_event["paragraph_index"], 1)
        self.assertEqual(guard_event["paragraph_total"], 2)
        self.assertEqual(guard_event["metadata"]["paused_at_paragraph"], 1)
        self.assertEqual(guard_event["metadata"]["next_paragraph_index"], 2)
        self.assertEqual(guard_event["metadata"]["current_beat"], "开场推进")
        self.assertEqual(guard_event["metadata"]["remaining_beats"], ["结尾钩子"])
        self.assertEqual(
            guard_event["guard_result"]["repair_options"],
            ["补出主角对水的本能恐惧，再安排他硬着头皮下水。"],
        )

    async def test_resume_rewrites_latest_paragraph_and_continues_from_next_beat(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        generate_mock = AsyncMock(
            side_effect=[
                _mock_generation("修正版第二段"),
                _mock_generation("第三段正文"),
            ]
        )
        guard_mock = AsyncMock(
            side_effect=[
                {
                    "passed": True,
                    "should_pause": False,
                    "alerts": [],
                    "repair_options": [],
                    "arbitration_note": None,
                },
                {
                    "passed": True,
                    "should_pause": False,
                    "alerts": [],
                    "repair_options": [],
                    "arbitration_note": None,
                },
            ]
        )

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.build_workspace",
            AsyncMock(
                return_value={
                    "characters": [],
                    "items": [],
                    "world_rules": [],
                    "foreshadows": [],
                }
            ),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={},
        ), patch(
            "services.story_engine_workflow_service._resolve_stream_outline_text",
            AsyncMock(return_value="第一段推进\n第二段推进\n第三段推进"),
        ), patch(
            "services.story_engine_workflow_service._build_stream_beats",
            return_value=["第一段推进", "第二段推进", "第三段推进"],
        ), patch(
            "services.story_engine_workflow_service.generate_story_stream_paragraph",
            generate_mock,
        ), patch(
            "services.story_engine_workflow_service.run_realtime_guard",
            guard_mock,
        ):
            events: list[dict] = []
            async for event in run_chapter_stream_generate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_number=7,
                chapter_title="海上夜奔",
                outline_id=None,
                current_outline="第一段推进\n第二段推进\n第三段推进",
                recent_chapters=[],
                existing_text="第一段旧稿\n\n第二段旧稿",
                style_sample=None,
                target_word_count=2400,
                target_paragraph_count=3,
                resume_from_paragraph=3,
                repair_instruction="把主角怕水的迟疑和代价写回来",
                rewrite_latest_paragraph=True,
            ):
                events.append(event)

        start_event = next(item for item in events if item["event"] == "start")
        chunk_event = next(item for item in events if item["event"] == "chunk")
        done_event = next(item for item in events if item["event"] == "done")

        self.assertEqual(start_event["metadata"]["status"], "resumed")
        self.assertEqual(start_event["metadata"]["rewritten_paragraph_index"], 2)
        self.assertIn("修正版第二段", start_event["text"])
        self.assertNotIn("第二段旧稿", start_event["text"])
        self.assertEqual(chunk_event["paragraph_index"], 3)
        self.assertIn("第三段正文", chunk_event["text"])
        self.assertTrue(done_event["metadata"]["resume_mode"])

        self.assertEqual(generate_mock.await_args_list[0].kwargs["paragraph_index"], 2)
        self.assertEqual(
            generate_mock.await_args_list[0].kwargs["repair_instruction"],
            "把主角怕水的迟疑和代价写回来",
        )
        self.assertEqual(generate_mock.await_args_list[1].kwargs["paragraph_index"], 3)
        self.assertEqual(
            generate_mock.await_args_list[1].kwargs["draft_text"],
            "第一段旧稿\n\n修正版第二段",
        )
        self.assertEqual(guard_mock.await_args_list[0].kwargs["latest_paragraph"], "修正版第二段")
        self.assertEqual(guard_mock.await_args_list[1].kwargs["latest_paragraph"], "第三段正文")

    async def test_done_event_summarizes_provider_and_fallback_usage(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        generate_mock = AsyncMock(
            side_effect=[
                _mock_generation(
                    "第一段正文",
                    provider="openai-compatible",
                    model="deepseek-v3.2",
                    metadata={
                        "stream_selected_role": "commercial",
                        "stream_failover_triggered": True,
                        "stream_failover_attempts": [
                            {
                                "role": "stream_writer",
                                "model": "gpt-5.4",
                                "selected_provider": "openai-compatible",
                                "error_type": "auth",
                                "status_code": 403,
                                "message": "user quota is not enough",
                            }
                        ],
                    },
                ),
                _mock_generation(
                    "第二段正文",
                    provider="local-fallback",
                    model="heuristic-v1",
                    used_fallback=True,
                    metadata={
                        "stream_selected_role": "style_guardian",
                        "stream_failover_triggered": True,
                        "stream_failover_attempts": [
                            {
                                "role": "stream_writer",
                                "model": "gpt-5.4",
                                "selected_provider": "openai-compatible",
                                "error_type": "rate_limit",
                                "status_code": 429,
                                "message": "too many requests",
                            },
                            {
                                "role": "commercial",
                                "model": "deepseek-v3.2",
                                "selected_provider": "openai-compatible",
                                "error_type": "provider_unavailable",
                                "status_code": 503,
                                "message": "service unavailable",
                            },
                        ],
                    },
                ),
            ]
        )
        guard_mock = AsyncMock(
            return_value={
                "passed": True,
                "should_pause": False,
                "alerts": [],
                "repair_options": [],
                "arbitration_note": None,
            }
        )

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.build_workspace",
            AsyncMock(
                return_value={
                    "characters": [],
                    "items": [],
                    "world_rules": [],
                    "foreshadows": [],
                }
            ),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={},
        ), patch(
            "services.story_engine_workflow_service._resolve_stream_outline_text",
            AsyncMock(return_value="第一段推进\n第二段推进"),
        ), patch(
            "services.story_engine_workflow_service._build_stream_beats",
            return_value=["第一段推进", "第二段推进"],
        ), patch(
            "services.story_engine_workflow_service.generate_story_stream_paragraph",
            generate_mock,
        ), patch(
            "services.story_engine_workflow_service.run_realtime_guard",
            guard_mock,
        ):
            events: list[dict] = []
            async for event in run_chapter_stream_generate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_number=7,
                chapter_title="海上夜奔",
                outline_id=None,
                current_outline="第一段推进\n第二段推进",
                recent_chapters=[],
                existing_text="",
                style_sample=None,
                target_word_count=2400,
                target_paragraph_count=2,
            ):
                events.append(event)

        chunk_event = next(item for item in events if item["event"] == "chunk")
        done_event = next(item for item in events if item["event"] == "done")

        self.assertTrue(chunk_event["metadata"]["failover_triggered"])
        self.assertEqual(chunk_event["metadata"]["selected_role"], "commercial")
        self.assertEqual(
            chunk_event["metadata"]["failover_attempts"][0]["model"],
            "gpt-5.4",
        )
        self.assertTrue(done_event["metadata"]["any_fallback"])
        self.assertEqual(done_event["metadata"]["fallback_paragraphs"], [2])
        self.assertEqual(done_event["metadata"]["failover_paragraphs"], [1, 2])
        self.assertEqual(
            done_event["metadata"]["provider_model_pairs"],
            ["openai-compatible:deepseek-v3.2", "local-fallback:heuristic-v1"],
        )
        self.assertEqual(
            done_event["metadata"]["models_used"],
            ["deepseek-v3.2", "heuristic-v1"],
        )
        self.assertEqual(len(done_event["metadata"]["failover_details"]), 2)

    def test_compose_stream_paragraph_avoids_repeated_padding_sentence(self) -> None:
        workspace = {
            "characters": [
                SimpleNamespace(name="陆沉"),
                SimpleNamespace(name="顾七"),
                SimpleNamespace(name="沈絮"),
            ],
            "items": [SimpleNamespace(name="镇潮玉")],
            "world_rules": [SimpleNamespace(rule_name="代价规则")],
            "foreshadows": [SimpleNamespace(content="海面下方像是有什么东西睁开了眼")],
        }
        paragraph = _compose_stream_paragraph(
            beat="逼主角在众人面前表态并接下危险任务",
            paragraph_index=2,
            paragraph_total=4,
            target_word_count=2400,
            existing_text="第一段旧稿",
            style_hint={"sentence_rhythm": "medium", "dialogue_density": "medium"},
            stream_context=_build_stream_context(
                workspace=workspace,
                recent_chapters=["上一章里他刚刚暴露自己怕水。"],
                chapter_number=7,
                chapter_title="海上夜奔",
            ),
            repair_instruction="补出主角怕水却不得不硬上的迟疑和代价",
        )

        self.assertGreater(len(paragraph), 160)
        self.assertNotIn(
            "他知道这一步不能写成侥幸，所以每个动作都必须带着理由和代价。他知道这一步不能写成侥幸",
            paragraph,
        )
        self.assertLessEqual(paragraph.count("每个动作都必须带着理由和代价"), 1)

    def test_build_stream_context_prefers_protagonist_and_antagonist_markers(self) -> None:
        context = _build_stream_context(
            workspace={
                "characters": [
                    SimpleNamespace(name="宿敌"),
                    SimpleNamespace(name="主角"),
                    SimpleNamespace(name="盟友"),
                ],
                "items": [],
                "world_rules": [],
                "foreshadows": [],
            },
            recent_chapters=[],
            chapter_number=1,
            chapter_title="第一章",
        )

        self.assertEqual(context["lead_name"], "主角")
        self.assertEqual(context["foil_name"], "宿敌")
        self.assertEqual(context["support_name"], "盟友")
