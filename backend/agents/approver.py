from __future__ import annotations

from typing import Any

from bus.protocol import AgentResponse
from agents.model_gateway import GenerationRequest, model_gateway

from agents.base import AgentRunContext, BaseAgent


class ApproverAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="approver", role="final_reviewer")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        outline: dict[str, Any] = payload["outline"]
        final_review: dict[str, Any] = payload["final_review"]
        initial_review: dict[str, Any] = payload["initial_review"]
        revision_plan: dict[str, Any] = payload.get("revision_plan") or {}

        approval = self._build_approval(
            outline=outline,
            final_review=final_review,
            initial_review=initial_review,
            revision_plan=revision_plan,
        )
        generation = await model_gateway.generate_text(
            GenerationRequest(
                task_name="approver.final_review",
                prompt=(
                    f"Outline={outline} | InitialReview={initial_review} | "
                    f"FinalReview={final_review} | RevisionPlan={revision_plan} | "
                    f"Approval={approval}"
                ),
                metadata={"agent": self.name},
            ),
            fallback=lambda: self._approval_summary(approval),
        )

        approval["summary"] = generation.content
        approval["generation"] = {
            "provider": generation.provider,
            "model": generation.model,
            "used_fallback": generation.used_fallback,
            "metadata": generation.metadata,
        }

        return AgentResponse(
            success=True,
            data={
                "approval": approval,
                "generation": approval["generation"],
            },
            confidence=0.81,
            reasoning="以章节目标、初评/复评结果和修订计划为依据，判断本章是否达到可进入 review/final 的门槛。",
        )

    def _build_approval(
        self,
        *,
        outline: dict[str, Any],
        final_review: dict[str, Any],
        initial_review: dict[str, Any],
        revision_plan: dict[str, Any],
    ) -> dict[str, Any]:
        final_score = float(final_review.get("overall_score") or 0.0)
        final_issues = [
            issue for issue in final_review.get("issues", []) if isinstance(issue, dict)
        ]
        high_issues = [
            issue for issue in final_issues if str(issue.get("severity")) == "high"
        ]
        approved = final_score >= 0.75 and not final_review.get("needs_revision") and not high_issues

        improvements = max(
            0.0,
            float(final_review.get("overall_score") or 0.0)
            - float(initial_review.get("overall_score") or 0.0),
        )

        return {
            "approved": approved,
            "target": outline.get("objective"),
            "final_score": final_score,
            "score_delta": improvements,
            "blocking_issues": [
                {
                    "dimension": issue.get("dimension"),
                    "severity": issue.get("severity"),
                    "message": issue.get("message"),
                }
                for issue in high_issues[:4]
            ],
            "release_recommendation": (
                "可进入 review 阶段"
                if approved
                else "建议继续修订后再进入 review/final"
            ),
            "revision_plan_steps": len(revision_plan.get("priorities", []))
            if isinstance(revision_plan.get("priorities"), list)
            else 0,
        }

    def _approval_summary(self, approval: dict[str, Any]) -> str:
        if approval["approved"]:
            return (
                f"终审通过：本章已基本实现“{approval.get('target')}”，"
                f"综合评分提升 {approval.get('score_delta', 0.0):.2f}，可以进入 review 阶段。"
            )
        return (
            f"终审未通过：本章距离“{approval.get('target')}”还有明显差距，"
            "仍存在高优先级问题，建议继续修订。"
        )
