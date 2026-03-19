from __future__ import annotations

from typing import Any

from bus.protocol import AgentResponse

from agents.architect import ArchitectAgent
from agents.approver import ApproverAgent
from agents.base import AgentRunContext, BaseAgent
from agents.critic import CriticAgent
from agents.debate import DebateAgent
from agents.editor import EditorAgent
from agents.librarian import LibrarianAgent
from agents.writer import WriterAgent


class CoordinatorAgent(BaseAgent):
    DEFAULT_MAX_REVISION_ROUNDS = 2
    DEFAULT_MIN_AI_TASTE_THRESHOLD = 0.3

    def __init__(
        self,
        max_revision_rounds: int | None = None,
        min_ai_taste_threshold: float | None = None,
    ) -> None:
        super().__init__(name="coordinator", role="orchestrator")
        self.librarian = LibrarianAgent()
        self.architect = ArchitectAgent()
        self.writer = WriterAgent()
        self.critic = CriticAgent()
        self.debate = DebateAgent(
            max_rounds=max_revision_rounds or self.DEFAULT_MAX_REVISION_ROUNDS,
            min_confidence_threshold=min_ai_taste_threshold or self.DEFAULT_MIN_AI_TASTE_THRESHOLD,
        )
        self.editor = EditorAgent()
        self.approver = ApproverAgent()
        self.max_revision_rounds = max_revision_rounds or self.DEFAULT_MAX_REVISION_ROUNDS
        self.min_ai_taste_threshold = min_ai_taste_threshold or self.DEFAULT_MIN_AI_TASTE_THRESHOLD

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        librarian_response = await self.librarian.run(
            context,
            {
                "story_bible": payload["story_bible"],
                "chapter_number": payload["chapter_number"],
                "chapter_title": payload.get("chapter_title"),
            },
        )
        if not librarian_response.success:
            return librarian_response

        context_brief = librarian_response.data["context_brief"]
        context_bundle = librarian_response.data["context_bundle"]
        architect_response = await self.architect.run(
            context,
            {
                **payload,
                "context_brief": context_brief,
                "context_bundle": context_bundle,
            },
        )
        if not architect_response.success:
            return architect_response

        chapter_plan = architect_response.data["chapter_plan"]
        writer_response = await self.writer.run(
            context,
            {
                **payload,
                "context_brief": context_brief,
                "context_bundle": context_bundle,
                "chapter_plan": chapter_plan,
            },
        )
        if not writer_response.success:
            return writer_response

        content = writer_response.data["content"]
        outline = writer_response.data["outline"]

        revision_loop_result = await self._run_revision_loop(
            context=context,
            payload=payload,
            initial_content=content,
            chapter_plan=chapter_plan,
            context_brief=context_brief,
            context_bundle=context_bundle,
        )

        content = revision_loop_result["content"]
        final_review = revision_loop_result["final_review"]
        initial_review = revision_loop_result["initial_review"]
        all_debate_summaries = revision_loop_result["debate_summaries"]
        all_revision_plans = revision_loop_result["revision_plans"]
        revision_rounds_completed = revision_loop_result["rounds_completed"]
        was_revised = revision_rounds_completed > 0

        approver_response = await self.approver.run(
            context,
            {
                "outline": outline,
                "initial_review": initial_review,
                "final_review": final_review,
                "revision_plan": all_revision_plans[-1] if all_revision_plans else {},
                "content": content,
                "revision_rounds": revision_rounds_completed,
                "debate_summaries": all_debate_summaries,
            },
        )
        if not approver_response.success:
            return approver_response
        approval = approver_response.data["approval"]

        revision_focus = []
        if all_revision_plans:
            latest_plan = all_revision_plans[-1]
            revision_focus = [
                {
                    "dimension": item.get("dimension"),
                    "severity": item.get("severity"),
                    "message": item.get("problem"),
                    "action": item.get("action"),
                    "acceptance_criteria": item.get("acceptance_criteria"),
                }
                for item in latest_plan.get("priorities", [])
                if isinstance(item, dict)
            ]

        return AgentResponse(
            success=True,
            data={
                "outline": outline,
                "content": content,
                "review": final_review,
                "initial_review": initial_review,
                "final_review": final_review,
                "revision_focus": revision_focus,
                "revision_plan": all_revision_plans[-1] if all_revision_plans else None,
                "revision_plans": all_revision_plans,
                "debate_summary": all_debate_summaries[-1] if all_debate_summaries else None,
                "debate_summaries": all_debate_summaries,
                "approval": approval,
                "context_brief": context_brief,
                "context_bundle": context_bundle,
                "revised": was_revised,
                "revision_rounds_completed": revision_rounds_completed,
                "trace": context.trace,
            },
            confidence=0.79 + (0.05 * min(revision_rounds_completed, 3)),
            reasoning=f"协调 librarian、writer、critic 三个角色，形成 {revision_rounds_completed} 轮可追踪的章节生成与自检流程。",
        )

    async def _run_revision_loop(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
        initial_content: str,
        chapter_plan: dict[str, Any],
        context_brief: dict[str, Any],
        context_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        content = initial_content
        all_debate_summaries: list[dict[str, Any]] = []
        all_revision_plans: list[dict[str, Any]] = []
        rounds_completed = 0
        current_revision_plan: dict[str, Any] | None = None

        initial_review = None
        final_review = None

        for round_num in range(1, self.max_revision_rounds + 2):
            critic_response = await self.critic.run(
                context,
                {
                    "story_bible": payload["story_bible"],
                    "content": content,
                    "revision_context": {
                        "round": round_num,
                        "previous_revision_plan": current_revision_plan,
                    },
                },
            )
            if not critic_response.success:
                final_review = critic_response.data
                break

            review = critic_response.data

            if round_num == 1:
                initial_review = review

            if not review.get("needs_revision", False):
                final_review = review
                break

            ai_taste_score = review.get("ai_taste_score", 1.0)
            if ai_taste_score >= (1.0 - self.min_ai_taste_threshold):
                final_review = review
                break

            if round_num > self.max_revision_rounds:
                final_review = review
                break

            debate_response = await self.debate.run(
                context,
                {
                    "review": review,
                    "chapter_plan": chapter_plan,
                    "context_brief": context_brief,
                    "content": content,
                    "round_number": round_num,
                    "previous_debate_summaries": all_debate_summaries,
                },
            )
            if not debate_response.success:
                final_review = review
                break

            debate_data = debate_response.data
            revision_plan = debate_data.get("revision_plan")
            debate_summary = debate_data.get("debate_summary")

            if revision_plan:
                all_revision_plans.append(revision_plan)
            if debate_summary:
                all_debate_summaries.append(debate_summary)

            editor_response = await self.editor.run(
                context,
                {
                    "content": content,
                    "issues": review.get("issues", []),
                    "context_brief": context_brief,
                    "context_bundle": context_bundle,
                    "revision_plan": revision_plan,
                    "style_guidance": payload.get("style_guidance"),
                    "style_preferences": payload.get("style_preferences"),
                    "debate_summary": debate_summary,
                    "revision_round": round_num,
                },
            )
            if not editor_response.success:
                final_review = review
                break

            content = editor_response.data["content"]
            current_revision_plan = revision_plan
            rounds_completed += 1

            if debate_data.get("final_verdict") == "no_issues":
                break

        if final_review is None:
            final_review = initial_review

        return {
            "content": content,
            "final_review": final_review,
            "initial_review": initial_review,
            "debate_summaries": all_debate_summaries,
            "revision_plans": all_revision_plans,
            "rounds_completed": rounds_completed,
        }
