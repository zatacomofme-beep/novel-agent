from __future__ import annotations

"""Legacy coordinator implementation.

This agent remains only to support the compatibility generation pipeline.
New product behavior should be implemented in Story Engine workflows instead of
expanding this orchestrator.
"""

import asyncio
from typing import Any

from bus.protocol import AgentResponse
from core.config import get_settings

from agents.architect import ArchitectAgent
from agents.approver import ApproverAgent
from agents.base import AgentRunContext, BaseAgent
from agents.beta_reader import BetaReaderAgent
from agents.canon_guardian import CanonGuardianAgent
from agents.chaos_agent import ChaosAgent
from agents.critic import CriticAgent
from agents.debate import DebateAgent
from agents.editor import EditorAgent
from agents.librarian import LibrarianAgent
from agents.linguistic_checker import LinguisticCheckerAgent
from agents.writer import WriterAgent
from services.truth_layer_service import build_truth_layer_context


class CoordinatorAgent(BaseAgent):
    def __init__(
        self,
        max_revision_rounds: int | None = None,
        min_ai_taste_threshold: float | None = None,
    ) -> None:
        super().__init__(name="coordinator", role="orchestrator")
        settings = get_settings()
        self.max_revision_rounds = max_revision_rounds or settings.coordinator_max_revision_rounds
        self.min_ai_taste_threshold = min_ai_taste_threshold or 0.3
        self.critic_score_threshold = settings.revision_min_overall_score_threshold
        self.critic_ai_taste_threshold = settings.revision_max_ai_taste_score_threshold
        self.librarian = LibrarianAgent()
        self.architect = ArchitectAgent()
        self.writer = WriterAgent()
        self.canon_guardian = CanonGuardianAgent()
        self.critic = CriticAgent()
        self.debate = DebateAgent(
            max_rounds=self.max_revision_rounds,
            min_confidence_threshold=self.min_ai_taste_threshold,
        )
        self.editor = EditorAgent()
        self.approver = ApproverAgent()
        self.linguistic_checker = LinguisticCheckerAgent()
        self.beta_reader = BetaReaderAgent()
        self.chaos_agent = ChaosAgent()

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

        open_threads = payload.get("open_threads", [])
        if open_threads:
            context_brief = {**context_brief, "open_threads": open_threads}

        social_topology = payload.get("social_topology", {})
        if social_topology:
            context_brief = {**context_brief, "social_topology": social_topology}

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
                "resume_from": payload.get("resume_from"),
            },
        )
        if not writer_response.success:
            return writer_response

        content = writer_response.data["content"]
        outline = writer_response.data["outline"]

        beta_response = await self.beta_reader.run(
            context,
            {
                "content": content,
                "genre": payload.get("genre", "general"),
                "target_audience": payload.get("target_audience", "adult"),
                "tension_data": payload.get("tension_data", {}),
                "beta_history": payload.get("beta_history", []),
                "persona_archetype": payload.get("persona_archetype", "idealist"),
                "chapter_number": payload.get("chapter_number"),
            },
        )
        beta_feedback = beta_response.data if beta_response.success else {}
        integrity_report = (
            payload.get("story_bible_integrity_report")
            if isinstance(payload.get("story_bible_integrity_report"), dict)
            else None
        )

        pre_canon_response = await self.canon_guardian.run(
            context,
            {
                "story_bible": payload["story_bible"],
                "content": content,
                "chapter_number": payload.get("chapter_number"),
                "chapter_title": payload.get("chapter_title"),
                "project_id": payload.get("project_id"),
                "constraint_texts": payload.get("constraint_texts") or [],
            },
        )
        if pre_canon_response.success and isinstance(pre_canon_response.data, dict):
            pre_canon_report = pre_canon_response.data.get("canon_report", {})
            pre_blocking = pre_canon_report.get("blocking_issue_count", 0) if isinstance(pre_canon_report, dict) else 0
            if pre_blocking > 0:
                pre_truth_layer_context = build_truth_layer_context(
                    integrity_report=integrity_report,
                    canon_report=pre_canon_report if isinstance(pre_canon_report, dict) else None,
                )
                pre_review = {
                    "needs_revision": True,
                    "issues": pre_canon_report.get("issues", []) if isinstance(pre_canon_report, dict) else [],
                    "ai_taste_score": 0.3,
                    "overall_score": 0.3,
                }
                return AgentResponse(
                    success=True,
                    data={
                        "content": content,
                        "final_review": pre_review,
                        "initial_review": pre_review,
                        "final_canon_report": pre_canon_report,
                        "initial_canon_report": pre_canon_report,
                        "rounds_completed": 0,
                        "truth_layer_context": pre_truth_layer_context,
                        "initial_truth_layer_context": pre_truth_layer_context,
                        "final_truth_layer_context": pre_truth_layer_context,
                        "revision_plans": [],
                        "debate_summaries": [],
                        "revision_focus": [],
                        "revised": False,
                    },
                    confidence=0.3,
                    reasoning="Canon pre-check caught blocking issues before revision loop",
                )

        revision_loop_result = await self._run_revision_loop(
            context=context,
            payload=payload,
            initial_content=content,
            chapter_plan=chapter_plan,
            context_brief=context_brief,
            context_bundle=context_bundle,
            integrity_report=integrity_report,
            beta_feedback=beta_feedback,
        )

        content = revision_loop_result["content"]
        final_review = revision_loop_result["final_review"]
        initial_review = revision_loop_result["initial_review"]
        final_canon_report = revision_loop_result["final_canon_report"]
        initial_canon_report = revision_loop_result["initial_canon_report"]
        initial_truth_layer_context = revision_loop_result["initial_truth_layer_context"]
        final_truth_layer_context = revision_loop_result["final_truth_layer_context"]
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
                "final_canon_report": final_canon_report,
                "final_truth_layer_context": final_truth_layer_context,
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
                    "source": item.get("source"),
                    "action_scope": item.get("action_scope"),
                    "plugin_key": item.get("plugin_key"),
                    "code": item.get("code"),
                    "fix_hint": item.get("fix_hint"),
                    "entity_labels": item.get("entity_labels", []),
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
                "canon_report": final_canon_report,
                "initial_canon_report": initial_canon_report,
                "story_bible_integrity_report": integrity_report,
                "truth_layer_context": final_truth_layer_context,
                "initial_truth_layer_context": initial_truth_layer_context,
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
            confidence=0.92 - (0.05 * min(revision_rounds_completed, 3)),
            reasoning=f"协调 librarian、writer、canon_guardian、critic 等角色，形成 {revision_rounds_completed} 轮可追踪的章节生成、自检与规范校验流程。",
        )

    async def _run_revision_loop(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
        initial_content: str,
        chapter_plan: dict[str, Any],
        context_brief: dict[str, Any],
        context_bundle: dict[str, Any],
        integrity_report: dict[str, Any] | None,
        beta_feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        content = initial_content
        all_debate_summaries: list[dict[str, Any]] = []
        all_revision_plans: list[dict[str, Any]] = []
        rounds_completed = 0
        current_revision_plan: dict[str, Any] | None = None

        initial_review = None
        final_review = None
        initial_canon_report = None
        final_canon_report = None
        initial_truth_layer_context = build_truth_layer_context(
            integrity_report=integrity_report,
            canon_report=None,
        )
        final_truth_layer_context = initial_truth_layer_context
        chaos_data: dict[str, Any] = {}
        tension_data: dict[str, Any] = {}

        for round_num in range(1, self.max_revision_rounds + 1):
            revision_plan: dict[str, Any] | None = None
            debate_summary: dict[str, Any] | None = None
            canon_response = await self.canon_guardian.run(
                context,
                {
                    "story_bible": payload["story_bible"],
                    "content": content,
                    "chapter_number": payload["chapter_number"],
                    "chapter_title": payload.get("chapter_title"),
                    "constraint_texts": payload.get("constraint_texts") or [],
                },
            )
            canon_report = (
                canon_response.data.get("canon_report")
                if canon_response.success and isinstance(canon_response.data, dict)
                else self._empty_canon_report(payload)
            )
            final_canon_report = canon_report
            round_truth_layer_context = build_truth_layer_context(
                integrity_report=integrity_report,
                canon_report=canon_report,
            )
            final_truth_layer_context = round_truth_layer_context
            critic_response = await self.critic.run(
                context,
                {
                    "story_bible": payload["story_bible"],
                    "content": content,
                    "story_bible_integrity_report": integrity_report,
                    "canon_report": canon_report,
                    "truth_layer_context": round_truth_layer_context,
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
                initial_canon_report = canon_report
                initial_truth_layer_context = round_truth_layer_context

            if not review.get("needs_revision", False):
                final_review = review
                final_truth_layer_context = round_truth_layer_context
                break

            ai_taste_score = review.get("ai_taste_score", 1.0)
            if ai_taste_score >= (1.0 - self.min_ai_taste_threshold):
                final_review = review
                final_truth_layer_context = round_truth_layer_context
                break

            debate_response = await self.debate.run(
                context,
                {
                    "review": review,
                    "chapter_plan": chapter_plan,
                    "context_brief": context_brief,
                    "content": content,
                    "story_bible_integrity_report": integrity_report,
                    "canon_report": canon_report,
                    "truth_layer_context": round_truth_layer_context,
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
                    "canon_report": canon_report,
                    "truth_layer_context": round_truth_layer_context,
                    "debate_summary": debate_summary,
                    "revision_round": round_num,
                    "chaos_interventions": review.get("chaos_interventions", []),
                    "beta_feedback": beta_feedback,
                },
            )
            if not editor_response.success:
                final_review = review
                break

            content = editor_response.data["content"]
            current_revision_plan = revision_plan

            if round_num == 1:
                characters = context_brief.get("characters", [])
                if characters:
                    linguistic_response = await self.linguistic_checker.run(
                        context,
                        {
                            "content": content,
                            "characters": characters,
                            "profiles": context_brief.get("linguistic_profiles", []),
                        },
                    )
                    if linguistic_response.success and linguistic_response.data:
                        linguistic_issues = linguistic_response.data.get("issues", [])
                        if linguistic_issues:
                            review["issues"].extend(linguistic_issues)
                            review["linguistic_issues"] = linguistic_issues

                chaos_response = await self.chaos_agent.run(
                    context,
                    {
                        "content": content,
                        "chapter_plan": chapter_plan,
                        "existing_threads": context_brief.get("open_threads", []),
                        "characters": characters,
                        "story_bible": payload.get("story_bible", {}),
                    },
                )
                if chaos_response.success and chaos_response.data:
                    chaos_data = chaos_response.data
                    review["chaos_interventions"] = chaos_data.get("chaos_interventions", [])

                from services.tension_sensor_service import tension_sensor_service
                tension_score = tension_sensor_service.compute_tension_from_text(content)
                tension_data = {
                    "tension_score": tension_score,
                    "tension_level": tension_sensor_service.classify_tension_level(tension_score),
                    "chaos_score": chaos_data.get("overall_chaos_score", 0.5),
                }

            rounds_completed += 1

            if debate_data.get("final_verdict") == "no_issues":
                break

        if final_review is None:
            final_review = initial_review
        if final_canon_report is None:
            final_canon_report = initial_canon_report or self._empty_canon_report(payload)

        return {
            "content": content,
            "final_review": final_review,
            "initial_review": initial_review,
            "final_canon_report": final_canon_report,
            "initial_canon_report": initial_canon_report or final_canon_report,
            "debate_summaries": all_debate_summaries,
            "revision_plans": all_revision_plans,
            "rounds_completed": rounds_completed,
            "initial_truth_layer_context": initial_truth_layer_context,
            "final_truth_layer_context": final_truth_layer_context,
            "chaos_data": chaos_data,
            "tension_data": tension_data,
        }

    def _empty_canon_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "chapter_number": int(payload.get("chapter_number") or 1),
            "chapter_title": payload.get("chapter_title"),
            "issue_count": 0,
            "blocking_issue_count": 0,
            "plugin_breakdown": {},
            "referenced_entities": [],
            "issues": [],
            "summary": "Canon 校验未产生结构化结果，当前回合按无阻断问题处理。",
        }
