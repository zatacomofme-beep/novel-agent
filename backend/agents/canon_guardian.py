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
        constraint_texts = payload.get("constraint_texts") or []

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

        if constraint_texts:
            constraint_violations = self._check_constraint_compliance(
                content=content,
                constraint_texts=constraint_texts,
            )
            if constraint_violations:
                canon_issues["constraint_violations"] = constraint_violations
                existing_blocking = canon_issues.get("blocking_issue_count", 0)
                canon_issues["blocking_issue_count"] = existing_blocking + len(
                    [v for v in constraint_violations if v.get("severity") == "error"]
                )

        return AgentResponse(
            success=True,
            data={
                "canon_report": canon_issues,
            },
            confidence=0.9 if canon_issues.get("blocking_issue_count", 0) == 0 else 0.82,
            reasoning="先对章节中的人物、关系、物品、时间线与伏笔做规范校验，再对照事前注入的设定约束逐条验收，把结果交给后续评审与辩论流程。",
        )

    def _check_constraint_compliance(
        self,
        content: str,
        constraint_texts: list[str],
    ) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []
        content_lower = content.lower()
        for constraint_text in constraint_texts:
            key_terms = self._extract_key_terms(constraint_text)
            if not key_terms:
                continue
            mentioned_terms = [t for t in key_terms if t.lower() in content_lower]
            if not mentioned_terms:
                continue
            negation_indicators = ["不", "非", "未", "禁止", "不可", "不得", "无法", "无"]
            has_negation_prefix = any(
                constraint_text.startswith(neg) for neg in negation_indicators
            )
            if has_negation_prefix:
                for term in mentioned_terms:
                    term_idx = content_lower.find(term.lower())
                    if term_idx >= 0:
                        window = content[max(0, term_idx - 10):term_idx + len(term) + 10].lower()
                        negated_in_content = any(neg in window for neg in negation_indicators)
                        if not negated_in_content:
                            violations.append({
                                "dimension": "constraint_violation",
                                "severity": "warning",
                                "message": f"约束「{constraint_text[:80]}」可能被违反：内容中提到了「{term}」但未体现否定约束",
                                "constraint": constraint_text,
                            })
            status_indicators = ["状态为", "阶段为", "关系是", "持有者为"]
            for indicator in status_indicators:
                if indicator in constraint_text:
                    violations.append({
                        "dimension": "constraint_check",
                        "severity": "info",
                        "message": f"约束「{constraint_text[:80]}」涉及的角色/物品已在内容中出现，请人工确认一致性",
                        "constraint": constraint_text,
                    })
                    break
        return violations

    @staticmethod
    def _extract_key_terms(text: str) -> list[str]:
        import re
        bracket_terms = re.findall(r"[「『]([^」』]+)[」』]", text)
        if bracket_terms:
            return bracket_terms
        terms: list[str] = []
        for segment in re.split(r"[，。、：；\s]+", text):
            segment = segment.strip()
            if len(segment) >= 2 and not segment.startswith(("必须", "禁止", "不可", "不得")):
                terms.append(segment)
        return terms[:5]

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
