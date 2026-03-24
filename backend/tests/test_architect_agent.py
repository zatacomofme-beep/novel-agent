from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agents.architect import ArchitectAgent
from agents.base import AgentRunContext
from agents.model_gateway import GenerationResult


class ArchitectAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_handles_string_context_and_includes_project_blueprint_prompt(
        self,
    ) -> None:
        agent = ArchitectAgent()
        context = AgentRunContext(
            chapter_id=str(uuid4()),
            project_id=str(uuid4()),
            task_id=str(uuid4()),
            payload={},
        )
        captured_prompt: dict[str, str] = {}

        async def fake_generate(request, fallback):
            captured_prompt["value"] = request.prompt
            return GenerationResult(
                content=(
                    '{"chapter_number":3,"title":"第3章：夜渡","objective":"让主角确认交易背后另有操盘者",'
                    '"opening":"以夜渡开场","middle":"通过交易冲突逼近真相","ending":"在余震中抛出新线索",'
                    '"emotion_curve":["压抑","逼近","冲撞","余震"],'
                    '"key_scenes":["夜渡交易","对手摊牌"],'
                    '"character_arcs":["林舟开始怀疑盟友"]}'
                ),
                provider="test-provider",
                model="test-model",
            )

        with patch(
            "agents.architect.model_gateway.generate_text",
            AsyncMock(side_effect=fake_generate),
        ):
            response = await agent._run(
                context,
                {
                    "chapter_number": 3,
                    "chapter_title": "第3章：夜渡",
                    "project_title": "夜潮城",
                    "context_brief": {
                        "characters": ["林舟", "顾沉"],
                        "locations": ["雾港码头"],
                        "active_plot_threads": ["黑市交易"],
                        "timeline_beats": ["暴雨夜的失踪案"],
                        "foreshadowing_items": ["消失的船票"],
                    },
                    "style_guidance": "强调代价感和持续推进。",
                    "style_preferences": {
                        "narrative_mode": "close_third",
                        "pacing_preference": "balanced",
                        "dialogue_preference": "dialogue_forward",
                        "tension_preference": "high_tension",
                    },
                    "project_bootstrap_profile": {
                        "protagonist_name": "林舟",
                        "core_story": "林舟被迫追查父亲失踪案真相。",
                        "novel_style": "都市悬疑成长",
                    },
                    "novel_blueprint": {
                        "premise": "一个底层少年被卷入黑市交易和旧案真相。",
                        "story_engine": "每次追查都会改写人物关系和危险等级。",
                        "writing_rules": ["每章必须推进事件"],
                        "plot_threads": [{"title": "父亲失踪案"}],
                    },
                    "chapter_outline_seed": {
                        "title": "第3章：夜渡",
                        "objective": "确认黑市交易和父亲旧案的关联",
                        "summary": "林舟在码头夜渡中被迫与旧识交易。",
                        "focus_characters": ["林舟", "顾沉"],
                    },
                },
            )

        self.assertTrue(response.success)
        prompt = captured_prompt["value"]
        self.assertIn("项目启动设定", prompt)
        self.assertIn("项目蓝图", prompt)
        self.assertIn("当前章节蓝图种子", prompt)
        self.assertIn("确认黑市交易和父亲旧案的关联", prompt)
        self.assertIn("父亲失踪案", prompt)
        self.assertEqual(
            response.data["chapter_plan"]["objective"],
            "让主角确认交易背后另有操盘者",
        )

    async def test_run_uses_chapter_seed_when_generated_plan_is_invalid(self) -> None:
        agent = ArchitectAgent()
        context = AgentRunContext(
            chapter_id=str(uuid4()),
            project_id=str(uuid4()),
            task_id=str(uuid4()),
            payload={},
        )

        with patch(
            "agents.architect.model_gateway.generate_text",
            AsyncMock(
                return_value=GenerationResult(
                    content="invalid-plan",
                    provider="test-provider",
                    model="test-model",
                )
            ),
        ):
            response = await agent._run(
                context,
                {
                    "chapter_number": 5,
                    "chapter_title": "第5章：雨幕回声",
                    "project_title": "夜潮城",
                    "context_brief": {
                        "characters": ["林舟"],
                        "locations": ["旧港仓库"],
                        "active_plot_threads": ["旧案追查"],
                        "timeline_beats": [],
                        "foreshadowing_items": [],
                    },
                    "style_guidance": "保持悬疑压迫感。",
                    "style_preferences": {
                        "narrative_mode": "close_third",
                        "pacing_preference": "slow_burn",
                        "dialogue_preference": "balanced",
                        "tension_preference": "restrained",
                    },
                    "chapter_outline_seed": {
                        "title": "第5章：雨幕回声",
                        "objective": "让林舟确认仓库里留下的证据来自熟人",
                        "summary": "林舟冒雨回到旧港仓库，在蛛丝马迹里确认背叛者身份。",
                        "focus_characters": ["林舟"],
                        "plot_thread_titles": ["旧案追查"],
                    },
                },
            )

        self.assertTrue(response.success)
        chapter_plan = response.data["chapter_plan"]
        self.assertEqual(chapter_plan["title"], "第5章：雨幕回声")
        self.assertEqual(
            chapter_plan["objective"],
            "让林舟确认仓库里留下的证据来自熟人",
        )
        self.assertTrue(chapter_plan["key_scenes"])
        self.assertIn("蛛丝马迹", chapter_plan["key_scenes"][1])


if __name__ == "__main__":
    unittest.main()
