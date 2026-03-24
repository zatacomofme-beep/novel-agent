from __future__ import annotations

from typing import Any

from canon.service import (
    calculate_canon_penalty,
    count_blocking_canon_issues,
    extract_canon_issue_payloads,
)
from bus.protocol import AgentResponse
from core.config import get_settings
from evaluation.evaluator import evaluate_chapter_text
from memory.story_bible import StoryBibleContext

from agents.base import AgentRunContext, BaseAgent


class CriticAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="critic", role="quality_reviewer")
        settings = get_settings()
        self.min_overall_score_threshold = settings.revision_min_overall_score_threshold
        self.max_ai_taste_score_threshold = settings.revision_max_ai_taste_score_threshold

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        story_bible: StoryBibleContext = payload["story_bible"]
        content: str = payload["content"]
        canon_report = payload.get("canon_report")
        integrity_report = payload.get("story_bible_integrity_report")
        truth_layer_context = payload.get("truth_layer_context")
        metrics, heuristic_issues, summary = evaluate_chapter_text(content, story_bible)
        canon_issues = extract_canon_issue_payloads(canon_report)
        blocking_canon_issue_count = count_blocking_canon_issues(canon_issues)
        integrity_issue_count = (
            int(integrity_report.get("issue_count"))
            if isinstance(integrity_report, dict)
            and isinstance(integrity_report.get("issue_count"), (int, float))
            else 0
        )
        integrity_blocking_issue_count = (
            int(integrity_report.get("blocking_issue_count"))
            if isinstance(integrity_report, dict)
            and isinstance(integrity_report.get("blocking_issue_count"), (int, float))
            else 0
        )
        overall_score = max(
            0.0,
            min(
                1.0,
                metrics.calculate_overall_score() - calculate_canon_penalty(canon_issues),
            ),
        )
        issues = [*heuristic_issues, *canon_issues]
        if isinstance(integrity_report, dict) and integrity_report.get("summary"):
            summary = f"{summary} {integrity_report['summary']}"
        if isinstance(canon_report, dict) and canon_report.get("summary"):
            summary = f"{summary} {canon_report['summary']}"

        return AgentResponse(
            success=True,
            data={
                "metrics": metrics.model_dump(),
                "issues": issues,
                "summary": summary,
                "overall_score": overall_score,
                "heuristic_overall_score": metrics.calculate_overall_score(),
                "ai_taste_score": metrics.ai_taste_score,
                "story_bible_integrity_issue_count": integrity_issue_count,
                "story_bible_integrity_blocking_issue_count": integrity_blocking_issue_count,
                "story_bible_integrity_report": (
                    integrity_report if isinstance(integrity_report, dict) else None
                ),
                "canon_issue_count": len(canon_issues),
                "canon_blocking_issue_count": blocking_canon_issue_count,
                "canon_report": canon_report if isinstance(canon_report, dict) else None,
                "truth_layer_context": (
                    truth_layer_context if isinstance(truth_layer_context, dict) else None
                ),
                "needs_revision": (
                    overall_score < self.min_overall_score_threshold
                    or metrics.ai_taste_score > self.max_ai_taste_score_threshold
                    or integrity_blocking_issue_count > 0
                    or blocking_canon_issue_count > 0
                ),
            },
            confidence=0.84,
            reasoning="先吸收规范事实校验结果，再用启发式评估器检查本章在一致性、语言变化、AI 痕迹和叙事密度上的基础质量。",
        )
