from __future__ import annotations

from typing import Any

from bus.protocol import AgentResponse
from canon.service import validate_story_canon
from memory.story_bible import StoryBibleContext

from agents.base import AgentRunContext, BaseAgent


class CanonGuardianAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="canon_guardian", role="continuity_validator")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        story_bible: StoryBibleContext = payload["story_bible"]
        content: str = payload["content"]
        chapter_number = int(payload.get("chapter_number") or 1)
        chapter_title = payload.get("chapter_title")
        project_id = payload.get("project_id")

        report = validate_story_canon(
            story_bible,
            content=content,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
        )

        canon_issues = report.model_dump()
        if project_id:
            causal_warnings = await self._check_causal_graph(
                project_id=project_id,
                chapter_number=chapter_number,
                content=content,
            )
            if causal_warnings:
                canon_issues["causal_warnings"] = causal_warnings

        return AgentResponse(
            success=True,
            data={
                "canon_report": canon_issues,
            },
            confidence=0.9 if report.blocking_issue_count == 0 else 0.82,
            reasoning="先对章节中的人物、关系、物品、时间线与伏笔做规范校验，再把结果交给后续评审与辩论流程。",
        )

    async def _check_causal_graph(
        self,
        project_id: str,
        chapter_number: int,
        content: str,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        from services.neo4j_service import neo4j_service
        warnings: list[dict[str, Any]] = []

        try:
            unresolved = await neo4j_service.get_unresolved_foreshadowing(
                project_id=project_id,
                before_chapter=chapter_number,
            )
            for item in unresolved:
                warnings.append({
                    "dimension": "foreshadow_payoff",
                    "severity": "warning",
                    "message": f"伏笔 \"{item.get('name', '?')}\" 尚未回收",
                    "node_id": item.get("id"),
                    "planted_chapter": item.get("chapter"),
                })
        except Exception:
            pass

        return warnings
