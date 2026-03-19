from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field
from enum import Enum

from bus.protocol import AgentResponse
from agents.model_gateway import GenerationRequest, model_gateway

from agents.base import AgentRunContext, BaseAgent


class DebatePosition(str, Enum):
    ARCHITECT = "architect"
    CRITIC = "critic"
    NEUTRAL = "neutral"


@dataclass
class DebateRound:
    round_number: int
    position: DebatePosition
    argument: str
    counter_arguments: list[str] = field(default_factory=list)
    resolution: str | None = None
    winner: DebatePosition | None = None


class DebateAgent(BaseAgent):
    def __init__(
        self,
        max_rounds: int = 3,
        min_confidence_threshold: float = 0.3,
    ) -> None:
        super().__init__(name="debate", role="revision_strategist")
        self.max_rounds = max_rounds
        self.min_confidence_threshold = min_confidence_threshold

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        review: dict[str, Any] = payload["review"]
        chapter_plan: dict[str, Any] = payload["chapter_plan"]
        context_brief: dict[str, Any] = payload["context_brief"]
        current_content: str = payload.get("content", "")

        issues = [
            issue
            for issue in review.get("issues", [])
            if isinstance(issue, dict)
        ]

        if not issues:
            return AgentResponse(
                success=True,
                data={
                    "revision_plan": None,
                    "debate_summary": None,
                    "rounds": [],
                    "final_verdict": "no_issues",
                },
                confidence=1.0,
                reasoning="没有问题需要辩论",
            )

        revision_plan = self._build_revision_plan(
            issues=issues,
            chapter_plan=chapter_plan,
            context_brief=context_brief,
        )

        rounds = self._conduct_debate_rounds(
            issues=issues,
            revision_plan=revision_plan,
            chapter_plan=chapter_plan,
            context_brief=context_brief,
            current_content=current_content,
        )

        final_verdict = self._determine_final_verdict(rounds, review)

        debate_summary = self._build_debate_summary(
            review=review,
            revision_plan=revision_plan,
            chapter_plan=chapter_plan,
            rounds=rounds,
            final_verdict=final_verdict,
        )

        return AgentResponse(
            success=True,
            data={
                "revision_plan": revision_plan,
                "debate_summary": debate_summary,
                "rounds": [r.__dict__ for r in rounds],
                "final_verdict": final_verdict,
                "generation": debate_summary.get("generation"),
            },
            confidence=self._calculate_debate_confidence(rounds),
            reasoning=f"完成 {len(rounds)} 轮辩论，最终判定: {final_verdict}",
        )

    def _conduct_debate_rounds(
        self,
        issues: list[dict[str, Any]],
        revision_plan: dict[str, Any],
        chapter_plan: dict[str, Any],
        context_brief: dict[str, Any],
        current_content: str,
    ) -> list[DebateRound]:
        rounds: list[DebateRound] = []
        remaining_issues = list(issues)
        current_revision_plan = dict(revision_plan)

        for round_num in range(1, self.max_rounds + 1):
            position = DebatePosition.ARCHITECT if round_num % 2 == 1 else DebatePosition.CRITIC

            round_args = self._generate_debate_arguments(
                issues=remaining_issues,
                revision_plan=current_revision_plan,
                chapter_plan=chapter_plan,
                context_brief=context_brief,
                position=position,
                round_number=round_num,
            )

            counter_args = []
            if round_num > 1:
                counter_args = self._generate_counter_arguments(
                    previous_round=rounds[-1],
                    position=position,
                    chapter_plan=chapter_plan,
                )

            resolution, winner = self._resolve_round(
                architect_args=round_args if position == DebatePosition.ARCHITECT else counter_args,
                critic_args=round_args if position == DebatePosition.CRITIC else counter_args,
                revision_plan=current_revision_plan,
                chapter_plan=chapter_plan,
            )

            round_obj = DebateRound(
                round_number=round_num,
                position=position,
                argument=round_args,
                counter_arguments=counter_args,
                resolution=resolution,
                winner=winner,
            )
            rounds.append(round_obj)

            if winner == DebatePosition.NEUTRAL or round_num >= 2:
                break

            current_revision_plan = self._update_revision_plan(
                current_revision_plan,
                winner,
                round_args,
                resolution,
            )

        return rounds

    def _generate_debate_arguments(
        self,
        issues: list[dict[str, Any]],
        revision_plan: dict[str, Any],
        chapter_plan: dict[str, Any],
        context_brief: dict[str, Any],
        position: DebatePosition,
        round_number: int,
    ) -> str:
        title = chapter_plan.get("title", "当前章节")
        objective = chapter_plan.get("objective", "推进主线")

        if position == DebatePosition.ARCHITECT:
            prompt = self._architect_prompt(
                title=title,
                objective=objective,
                issues=issues,
                round_number=round_number,
            )
        else:
            prompt = self._critic_prompt(
                title=title,
                objective=objective,
                issues=issues,
                revision_plan=revision_plan,
                round_number=round_number,
            )

        generation = model_gateway.generate_text_sync(
            GenerationRequest(
                task_name=f"debate.position_{position.value}",
                prompt=prompt,
                metadata={"agent": self.name, "position": position.value},
            ),
            fallback=lambda: self._fallback_argument(position, objective, issues),
        )

        return generation.content

    def _architect_prompt(
        self,
        title: str,
        objective: str,
        issues: list[dict[str, Any]],
        round_number: int,
    ) -> str:
        return f"""作为架构师 Agent，你需要为第 {round_number} 轮辩论辩护。

章节：《{title}》
章节目标：{objective}

需要处理的问题：
{self._format_issues(issues)}

你的立场是：优先守住章节目标，不要为了修补问题而稀释本章的核心推进。

请给出你的辩论论据，说明为什么某些问题应该优先处理，某些问题可以在后续章节处理。
"""

    def _critic_prompt(
        self,
        title: str,
        objective: str,
        issues: list[dict[str, Any]],
        revision_plan: dict[str, Any],
        round_number: int,
    ) -> str:
        priorities = revision_plan.get("focus_dimensions", [])
        return f"""作为批判家 Agent，你需要为第 {round_number} 轮辩论辩护。

章节：《{title}》
章节目标：{objective}

已确定的重点维度：{', '.join(priorities)}

需要处理的问题：
{self._format_issues(issues)}

你的立场是：优先处理会暴露 AI 痕迹、削弱一致性或让情节失焦的问题。

请给出你的辩论论据，说明为什么这些维度的问题必须在本章解决。
"""

    def _generate_counter_arguments(
        self,
        previous_round: DebateRound,
        position: DebatePosition,
        chapter_plan: dict[str, Any],
    ) -> list[str]:
        objective = chapter_plan.get("objective", "推进主线")

        if position == DebatePosition.ARCHITECT:
            return [
                f"章节目标“{objective}”必须保持，不能被问题修复冲淡",
                "过度修改会导致情节偏离原有方向",
                "部分问题可以在下一章自然解决",
            ]
        else:
            return [
                "AI 痕迹问题会在读者阅读时立即暴露",
                "一致性问题是不可接受的硬伤",
                "情节失焦会让读者困惑",
            ]

    def _resolve_round(
        self,
        architect_args: str,
        critic_args: str,
        revision_plan: dict[str, Any],
        chapter_plan: dict[str, Any],
    ) -> tuple[str, DebatePosition]:
        objective = chapter_plan.get("objective", "推进主线")
        priorities = revision_plan.get("priorities", [])

        high_severity_issues = [p for p in priorities if p.get("severity") == "high"]

        if high_severity_issues:
            ai_taste_issues = [
                p for p in high_severity_issues
                if p.get("dimension") == "ai_taste_score"
            ]
            if ai_taste_issues:
                return (
                    f"AI 痕迹问题必须优先解决，这是读者最直接感知的问题",
                    DebatePosition.CRITIC,
                )

            consistency_issues = [
                p for p in high_severity_issues
                if "consistency" in p.get("dimension", "")
            ]
            if consistency_issues:
                return (
                    f"一致性问题是根本性错误，必须在本章修复",
                    DebatePosition.CRITIC,
                )

        return (
            f"章节目标“{objective}”与问题修复需要平衡，优先保证主线推进",
            DebatePosition.ARCHITECT,
        )

    def _determine_final_verdict(
        self,
        rounds: list[DebateRound],
        review: dict[str, Any],
    ) -> str:
        if not rounds:
            return "no_issues"

        critic_wins = sum(1 for r in rounds if r.winner == DebatePosition.CRITIC)
        architect_wins = sum(1 for r in rounds if r.winner == DebatePosition.ARCHITECT)

        if critic_wins > architect_wins:
            ai_taste = review.get("ai_taste_score", 1.0)
            if ai_taste < self.min_confidence_threshold:
                return "needs_significant_revision"
            return "needs_minor_revision"
        elif architect_wins > critic_wins:
            return "preserve_chapter_direction"
        else:
            return "balanced_revision"

    def _update_revision_plan(
        self,
        current_plan: dict[str, Any],
        winner: DebatePosition,
        arguments: str,
        resolution: str,
    ) -> dict[str, Any]:
        updated_plan = dict(current_plan)

        if winner == DebatePosition.CRITIC:
            priorities = updated_plan.get("priorities", [])
            for p in priorities:
                if p.get("dimension") == "ai_taste_score":
                    p["priority_boost"] = True
                    p["resolution_note"] = f"AI 痕迹问题优先解决: {resolution}"
                elif p.get("severity") == "high":
                    p["must_resolve"] = True
        else:
            priorities = updated_plan.get("priorities", [])
            for p in priorities:
                if p.get("severity") == "low":
                    p["defer_to_next_chapter"] = True

        updated_plan["last_resolution"] = resolution
        return updated_plan

    def _build_debate_summary(
        self,
        review: dict[str, Any],
        revision_plan: dict[str, Any],
        chapter_plan: dict[str, Any],
        rounds: list[DebateRound],
        final_verdict: str,
    ) -> dict[str, Any]:
        round_summaries = []
        for r in rounds:
            round_summaries.append({
                "round": r.round_number,
                "position": r.position.value,
                "argument_preview": r.argument[:100] + "..." if len(r.argument) > 100 else r.argument,
                "resolution": r.resolution,
                "winner": r.winner.value if r.winner else None,
            })

        generation = model_gateway.generate_text_sync(
            GenerationRequest(
                task_name="debate.summary",
                prompt=f"""总结以下辩论回合，为编辑生成一份清晰的修订指南。

章节目标：{chapter_plan.get('objective')}
最终判定：{final_verdict}
辩论回合：{round_summaries}

请生成一份简洁的修订指南，包含：
1. 需要优先处理的问题
2. 修订的具体方向
3. 如何验证修订是否成功
""",
                metadata={"agent": self.name},
            ),
            fallback=lambda: self._fallback_summary(chapter_plan, revision_plan, final_verdict),
        )

        return {
            "summary": generation.content,
            "round_count": len(rounds),
            "round_summaries": round_summaries,
            "final_verdict": final_verdict,
            "architect_position": revision_plan.get("architect_position", ""),
            "critic_position": revision_plan.get("critic_position", ""),
            "resolution": revision_plan.get("resolution", ""),
            "generation": {
                "provider": getattr(generation, "provider", None),
                "model": getattr(generation, "model", None),
                "used_fallback": getattr(generation, "used_fallback", False),
                "metadata": getattr(generation, "metadata", {}),
            },
        }

    def _calculate_debate_confidence(self, rounds: list[DebateRound]) -> float:
        if not rounds:
            return 1.0

        winner_count = sum(1 for r in rounds if r.winner is not None)
        if winner_count == 0:
            return 0.5

        consensus_score = sum(
            1 for i in range(len(rounds) - 1)
            if rounds[i].winner == rounds[i + 1].winner
        ) / max(len(rounds) - 1, 1)

        return 0.5 + (consensus_score * 0.3) + (min(len(rounds), 3) * 0.05)

    def _format_issues(self, issues: list[dict[str, Any]]) -> str:
        return "\n".join(
            f"- [{issue.get('severity', 'unknown')}] {issue.get('dimension', 'unknown')}: {issue.get('message', '')}"
            for issue in issues
        )

    def _build_revision_plan(
        self,
        issues: list[dict[str, Any]],
        chapter_plan: dict[str, Any],
        context_brief: dict[str, Any],
    ) -> dict[str, Any]:
        title = chapter_plan.get("title") or "当前章节"
        objective = chapter_plan.get("objective") or "推进主线"
        characters = context_brief.get("characters") or ["主角"]
        locations = context_brief.get("locations") or ["当前场景"]

        priorities: list[dict[str, Any]] = []
        focus_dimensions: list[str] = []
        for issue in issues:
            dimension = str(issue.get("dimension") or "unknown")
            focus_dimensions.append(dimension)
            priorities.append(
                {
                    "dimension": dimension,
                    "severity": issue.get("severity") or "medium",
                    "problem": issue.get("message") or "",
                    "action": self._recommend_action(
                        dimension=dimension,
                        objective=objective,
                        protagonist=characters[0],
                        location=locations[0],
                    ),
                    "acceptance_criteria": self._acceptance_criteria(
                        dimension=dimension,
                        objective=objective,
                    ),
                }
            )

        ordered_priorities = sorted(
            priorities,
            key=lambda item: {"high": 0, "medium": 1, "low": 2}.get(
                str(item["severity"]),
                3,
            ),
        )
        focus_dimensions = list(dict.fromkeys(focus_dimensions))

        return {
            "chapter_title": title,
            "objective": objective,
            "focus_dimensions": focus_dimensions,
            "priorities": ordered_priorities,
            "architect_position": f"优先守住章节目标「{objective}」，不要为修补问题而稀释本章推进。",
            "critic_position": "优先处理会暴露 AI 痕迹、削弱一致性或让情节失焦的问题。",
            "resolution": "先修高严重度问题，再压低 AI 痕迹，最后只做不改变主线的节奏微调。",
        }

    def _recommend_action(
        self,
        *,
        dimension: str,
        objective: str,
        protagonist: str,
        location: str,
    ) -> str:
        mapping = {
            "ai_taste_score": "调整连接词、句长和重复表达，让语言更像人工修稿而不是一次性生成。",
            "plot_tightness": f"补入推动「{objective}」的动作节点，删掉只解释不推进的段落。",
            "sentence_variation": "打破过于均匀的句式节奏，加入长短句切换和更具体的停顿。",
            "character_consistency": f"让叙事重新贴近 {protagonist} 的判断、动机和即时反应。",
            "world_consistency": f"补足 {location} 的环境约束、物理细节和世界规则回扣。",
            "logic_coherence": "明确因果链，补齐前后动作之间缺失的推导或触发条件。",
            "timeline_consistency": "校正时间顺序、回忆插入点和事件先后关系。",
        }
        return mapping.get(
            dimension,
            f"围绕「{objective}」收束表达，确保这一维的问题被具体改写而不是被解释带过。",
        )

    def _acceptance_criteria(
        self,
        *,
        dimension: str,
        objective: str,
    ) -> str:
        mapping = {
            "ai_taste_score": "删除明显模板化连接词，段落节奏不再整齐到机械。",
            "plot_tightness": f"读完后能明确感到本章把「{objective}」向前推进了一步。",
            "sentence_variation": "相邻段落在长短句和信息密度上有明显差异。",
            "character_consistency": "人物反应与既有人设一致，不出现动机突变。",
            "world_consistency": "设定约束被自然带出，不与既有世界规则冲突。",
            "logic_coherence": "主要行为都有可理解的动因与结果。",
            "timeline_consistency": "事件前后顺序和章节时间锚点一致。",
        }
        return mapping.get(
            dimension,
            "修订后这一问题不再成为读者第一眼能察觉的结构性瑕疵。",
        )

    def _fallback_argument(
        self,
        position: DebatePosition,
        objective: str,
        issues: list[dict[str, Any]],
    ) -> str:
        if position == DebatePosition.ARCHITECT:
            return f"章节目标「{objective}」必须保持，高严重度问题优先处理，但不应为了修复而破坏主线节奏。"
        else:
            return f"AI 痕迹、一致性问题是必须修复的，因为这些是读者最直接感知的质量问题。"

    def _fallback_summary(
        self,
        chapter_plan: dict[str, Any],
        revision_plan: dict[str, Any],
        final_verdict: str,
    ) -> str:
        priorities = revision_plan.get("priorities", [])[:3]
        priority_text = "、".join(p.get("dimension", "") for p in priorities)
        return f"辩论完成。章节目标「{chapter_plan.get('objective')}」保持，最终判定: {final_verdict}。重点处理: {priority_text}。"


def run_debate_sync(
    context: AgentRunContext,
    payload: dict[str, Any],
    max_rounds: int = 3,
    min_confidence_threshold: float = 0.3,
) -> AgentResponse:
    agent = DebateAgent(
        max_rounds=max_rounds,
        min_confidence_threshold=min_confidence_threshold,
    )
    import asyncio
    return asyncio.get_event_loop().run_until_complete(agent.run(context, payload))
