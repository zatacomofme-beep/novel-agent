from __future__ import annotations

from typing import Any

from bus.protocol import AgentResponse
from agents.model_gateway import GenerationRequest, model_gateway

from agents.base import AgentRunContext, BaseAgent


class EditorAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="editor", role="revision_editor")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        content: str = payload["content"]
        issues: list[dict[str, Any]] = payload["issues"]
        context_brief: dict[str, Any] = payload["context_brief"]
        revision_plan: dict[str, Any] = payload.get("revision_plan") or {}
        style_guidance = payload.get("style_guidance") or ""
        style_preferences = payload.get("style_preferences") or {}
        truth_layer_context = payload.get("truth_layer_context") or {}
        chaos_interventions: list[dict[str, Any]] = payload.get("chaos_interventions") or []

        generation = await model_gateway.generate_text(
            GenerationRequest(
                task_name="editor.revise",
                prompt=(
                    f"Issues={issues} | Context={context_brief} | "
                    f"RevisionPlan={revision_plan} | TruthLayer={truth_layer_context} | "
                    f"StyleGuidance={style_guidance} | "
                    f"ChaosInterventions={chaos_interventions}"
                ),
                metadata={"agent": self.name},
            ),
            fallback=lambda: self._fallback_revision(
                content,
                issues,
                context_brief,
                revision_plan,
                style_preferences,
                truth_layer_context,
                chaos_interventions,
            ),
        )
        revised = generation.content

        return AgentResponse(
            success=True,
            data={
                "content": revised,
                "applied_revision_plan": revision_plan,
                "chaos_interventions_applied": [
                    {"type": i.get("type"), "location": i.get("location"), "description": i.get("description")}
                    for i in chaos_interventions
                    if i.get("canon_safe", False) is True
                ],
                "generation": {
                    "provider": generation.provider,
                    "model": generation.model,
                    "used_fallback": generation.used_fallback,
                    "metadata": generation.metadata,
                },
            },
            confidence=0.71,
            reasoning="基于批判结果做一轮结构化修订，优先处理设定回扣、AI 痕迹和节奏松散问题。",
        )

    def _fallback_revision(
        self,
        content: str,
        issues: list[dict[str, Any]],
        context_brief: dict[str, Any],
        revision_plan: dict[str, Any],
        style_preferences: dict[str, Any],
        truth_layer_context: dict[str, Any],
        chaos_interventions: list[dict[str, Any]] | None = None,
    ) -> str:
        revised = content
        priorities = revision_plan.get("priorities")
        banned_patterns = style_preferences.get("banned_patterns") or []
        chapter_revision_targets = truth_layer_context.get("chapter_revision_targets") or []
        story_bible_followups = truth_layer_context.get("story_bible_followups") or []
        safe_interventions = [
            i for i in (chaos_interventions or [])
            if i.get("canon_safe", False) is True
        ]
        if safe_interventions:
            intervention_notes = [
                f"[{i.get('type','unknown')} at {i.get('location','?')}] {i.get('description','')}"
                for i in safe_interventions[:3]
            ]
            revised += "\n\n编辑注（Chaos 干预）:" + " ".join(intervention_notes)
        if isinstance(priorities, list):
            for priority in priorities[:3]:
                if not isinstance(priority, dict):
                    continue
                action = priority.get("action")
                if action:
                    revised += f"\n\n修订计划：{action}"
        if any(issue["dimension"] == "character_consistency" for issue in issues):
            characters = context_brief.get("characters") or []
            if characters:
                revised += (
                    f"\n\n编辑注：补回人物锚点，让叙事重新贴近 {characters[0]} 的即时感受与判断。"
                )
        if any(issue["dimension"] == "world_consistency" for issue in issues):
            locations = context_brief.get("locations") or []
            if locations:
                revised += (
                    f"\n\n编辑注：补入 {locations[0]} 的环境约束和物理细节，强化世界规则存在感。"
                )
        if any(issue["dimension"] == "ai_taste_score" for issue in issues):
            revised = revised.replace("如果说", "到了这一步，").replace("因此", "于是")
            revised += "\n\n编辑注：局部调整连接词和句长，削弱过于均匀的生成痕迹。"
        if any(issue["dimension"] == "plot_tightness" for issue in issues):
            revised += "\n\n编辑注：补上动作推进句，避免章节停留在说明而非事件中。"
        if isinstance(chapter_revision_targets, list):
            for target in chapter_revision_targets[:2]:
                if not isinstance(target, dict):
                    continue
                hint = target.get("fix_hint") or target.get("message")
                if hint:
                    revised += f"\n\n编辑注：连续性修订重点：{hint}"
        if isinstance(story_bible_followups, list) and story_bible_followups:
            followup_notes = [
                str(item.get("fix_hint") or item.get("message") or "").strip()
                for item in story_bible_followups[:2]
                if isinstance(item, dict)
            ]
            followup_notes = [note for note in followup_notes if note]
            if followup_notes:
                revised += (
                    "\n\n编辑注：以下问题需要先回写 Story Bible 基座，再决定是否继续强修正文："
                    f"{'；'.join(followup_notes)}。"
                )
        for pattern in banned_patterns[:5]:
            if isinstance(pattern, str) and pattern.strip():
                revised = revised.replace(pattern.strip(), "")
        return revised
