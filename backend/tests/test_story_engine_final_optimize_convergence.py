from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agents.story_agents import build_agent_report
from services.story_engine_workflow_service import run_final_optimize


def _build_round_result(
    *,
    final_draft: str,
    guardian_issues: list[dict],
    logic_issues: list[dict],
    commercial_issues: list[dict],
    style_issues: list[dict],
) -> dict:
    return {
        "guardian_report": build_agent_report(
            "guardian",
            summary="guardian",
            issues=guardian_issues,
            proposed_actions=[item.get("suggestion", "") for item in guardian_issues if item.get("suggestion")],
        ),
        "logic_report": build_agent_report(
            "logic_debunker",
            summary="logic",
            issues=logic_issues,
            proposed_actions=[item.get("suggestion", "") for item in logic_issues if item.get("suggestion")],
        ),
        "commercial_report": build_agent_report(
            "commercial",
            summary="commercial",
            issues=commercial_issues,
            proposed_actions=[item.get("suggestion", "") for item in commercial_issues if item.get("suggestion")],
        ),
        "style_report": build_agent_report(
            "style_guardian",
            summary="style",
            issues=style_issues,
            proposed_actions=[item.get("suggestion", "") for item in style_issues if item.get("suggestion")],
        ),
        "anchor_payload": {
            "chapter_summary": {
                "content": "本章完成了一次关键收口，人物关系和风险边界都更清晰了。",
                "core_progress": ["主角完成一次关键判断。"],
                "character_changes": [],
                "foreshadow_updates": [],
                "kb_update_suggestions": [],
            },
            "kb_updates": [],
        },
        "final_package": {
            "final_draft": final_draft,
            "revision_notes": ["补强关键冲突的因果。"],
            "arbitrator_report": build_agent_report(
                "arbitrator",
                summary="arbitrator",
                issues=guardian_issues + logic_issues + commercial_issues + style_issues,
                proposed_actions=["继续收口。"],
                raw_output={"consensus": False},
            ),
        },
    }


class StoryEngineFinalOptimizeConvergenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_optimize_runs_multiple_rounds_until_clean(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        round_one_issue = {
            "severity": "high",
            "title": "角色动机断裂",
            "detail": "主角突然转向，前文刺激还不够。",
            "source": "guardian",
            "suggestion": "补一个明确触发点。",
        }

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={"guardian": {"model": "gpt-5.4", "reasoning_effort": "high"}},
        ), patch(
            "services.story_engine_workflow_service._run_final_verify_once",
            AsyncMock(
                side_effect=[
                    _build_round_result(
                        final_draft="第一轮优化稿",
                        guardian_issues=[round_one_issue],
                        logic_issues=[],
                        commercial_issues=[],
                        style_issues=[],
                    ),
                    _build_round_result(
                        final_draft="第二轮优化稿",
                        guardian_issues=[],
                        logic_issues=[],
                        commercial_issues=[],
                        style_issues=[],
                    ),
                ]
            ),
        ), patch(
            "services.story_engine_workflow_service._upsert_chapter_summary",
            AsyncMock(
                return_value={
                    "summary_id": uuid4(),
                    "project_id": project_id,
                    "chapter_number": 8,
                    "content": "本章完成了一次关键收口，人物关系和风险边界都更清晰了。",
                    "core_progress": ["主角完成一次关键判断。"],
                    "character_changes": [],
                    "foreshadow_updates": [],
                    "kb_update_suggestions": [],
                    "version": 1,
                    "created_at": "2026-03-24T00:00:00Z",
                    "updated_at": "2026-03-24T00:00:00Z",
                }
            ),
        ):
            result = await run_final_optimize(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_number=8,
                chapter_title="夜潮反咬",
                draft_text="原稿",
                style_sample="样文",
            )

        self.assertEqual(result["final_draft"], "第二轮优化稿")
        self.assertEqual(result["consensus_rounds"], 2)
        self.assertTrue(result["consensus_reached"])
        self.assertTrue(result["ready_for_publish"])
        self.assertEqual(result["remaining_issue_count"], 0)
        self.assertIn("已经收口 2 轮", result["quality_summary"])

    async def test_final_optimize_marks_needs_attention_when_issue_stabilizes(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        persistent_issue = {
            "severity": "medium",
            "title": "章末钩子偏弱",
            "detail": "最后一行还没形成追读抓手。",
            "source": "commercial",
            "suggestion": "补一个信息反转。",
        }

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={"guardian": {"model": "gpt-5.4", "reasoning_effort": "high"}},
        ), patch(
            "services.story_engine_workflow_service._run_final_verify_once",
            AsyncMock(
                side_effect=[
                    _build_round_result(
                        final_draft="第一轮优化稿",
                        guardian_issues=[],
                        logic_issues=[],
                        commercial_issues=[persistent_issue],
                        style_issues=[],
                    ),
                    _build_round_result(
                        final_draft="第二轮优化稿",
                        guardian_issues=[],
                        logic_issues=[],
                        commercial_issues=[persistent_issue],
                        style_issues=[],
                    ),
                ]
            ),
        ), patch(
            "services.story_engine_workflow_service._upsert_chapter_summary",
            AsyncMock(
                return_value={
                    "summary_id": uuid4(),
                    "project_id": project_id,
                    "chapter_number": 8,
                    "content": "本章完成了一次关键收口，人物关系和风险边界都更清晰了。",
                    "core_progress": ["主角完成一次关键判断。"],
                    "character_changes": [],
                    "foreshadow_updates": [],
                    "kb_update_suggestions": [],
                    "version": 1,
                    "created_at": "2026-03-24T00:00:00Z",
                    "updated_at": "2026-03-24T00:00:00Z",
                }
            ),
        ):
            result = await run_final_optimize(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_number=8,
                chapter_title="夜潮反咬",
                draft_text="原稿",
                style_sample="样文",
            )

        self.assertEqual(result["consensus_rounds"], 2)
        self.assertFalse(result["consensus_reached"])
        self.assertFalse(result["ready_for_publish"])
        self.assertEqual(result["remaining_issue_count"], 1)
        self.assertIn("还剩 1 个问题", result["quality_summary"])
