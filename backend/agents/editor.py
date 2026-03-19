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

        generation = await model_gateway.generate_text(
            GenerationRequest(
                task_name="editor.revise",
                prompt=(
                    f"Issues={issues} | Context={context_brief} | "
                    f"RevisionPlan={revision_plan} | StyleGuidance={style_guidance}"
                ),
                metadata={"agent": self.name},
            ),
            fallback=lambda: self._fallback_revision(
                content,
                issues,
                context_brief,
                revision_plan,
                style_preferences,
            ),
        )
        revised = generation.content

        return AgentResponse(
            success=True,
            data={
                "content": revised,
                "applied_revision_plan": revision_plan,
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
    ) -> str:
        revised = content
        priorities = revision_plan.get("priorities")
        banned_patterns = style_preferences.get("banned_patterns") or []
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
        for pattern in banned_patterns[:5]:
            if isinstance(pattern, str) and pattern.strip():
                revised = revised.replace(pattern.strip(), "")
        return revised
