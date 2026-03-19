from __future__ import annotations

from typing import Any

from bus.protocol import AgentResponse
from agents.model_gateway import GenerationRequest, model_gateway

from agents.base import AgentRunContext, BaseAgent


class ArchitectAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="architect", role="chapter_planner")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        chapter_number = payload["chapter_number"]
        chapter_title = payload.get("chapter_title") or f"第 {chapter_number} 章"
        context_brief = payload["context_brief"]
        style_guidance = payload.get("style_guidance") or ""
        style_preferences = payload.get("style_preferences") or {}
        characters = context_brief.get("characters") or ["主角"]
        locations = context_brief.get("locations") or ["未知地点"]
        plot_threads = context_brief.get("active_plot_threads") or ["主线推进"]
        pacing_preference = str(style_preferences.get("pacing_preference") or "balanced")
        dialogue_preference = str(style_preferences.get("dialogue_preference") or "balanced")
        tension_preference = str(style_preferences.get("tension_preference") or "balanced")
        narrative_mode = str(style_preferences.get("narrative_mode") or "close_third")

        generation = await model_gateway.generate_text(
            GenerationRequest(
                task_name="architect.plan",
                prompt=(
                    f"Project={payload.get('project_title')} | Chapter={chapter_number} | "
                    f"Characters={characters} | Locations={locations} | PlotThreads={plot_threads} | "
                    f"StyleGuidance={style_guidance}"
                ),
                metadata={"agent": self.name},
            ),
            fallback=lambda: f"plan:{chapter_title}",
        )
        chapter_plan = {
            "chapter_number": chapter_number,
            "title": chapter_title,
            "objective": f"推动 {plot_threads[0]}，同时让 {characters[0]} 面对更尖锐的代价。",
            "opening": self._opening_focus(locations[0], pacing_preference, narrative_mode),
            "middle": self._middle_focus(characters[0], dialogue_preference),
            "ending": self._ending_focus(tension_preference),
            "emotion_curve": self._emotion_curve(tension_preference),
            "style_guidance": style_guidance,
            "generation": {
                "provider": generation.provider,
                "model": generation.model,
                "used_fallback": generation.used_fallback,
                "metadata": generation.metadata,
            },
        }

        return AgentResponse(
            success=True,
            data={
                "chapter_plan": chapter_plan,
                "generation": chapter_plan["generation"],
            },
            confidence=0.85,
            reasoning="根据章节编号和上下文摘要先确定本章目标、节奏和收束方式，避免写作阶段直接失焦。",
        )

    def _opening_focus(
        self,
        location: str,
        pacing_preference: str,
        narrative_mode: str,
    ) -> str:
        mode_prefix = {
            "first_person": "用第一人称贴身进入人物知觉，",
            "omniscient": "用更高位的俯瞰视角同时照见多方动机，",
        }.get(narrative_mode, "用贴身第三人称压紧人物当下判断，")

        if pacing_preference == "fast":
            return f"{mode_prefix}在 {location} 尽快抛出任务和阻力。"
        if pacing_preference == "slow_burn":
            return f"{mode_prefix}在 {location} 先铺开不安与潜在失衡，再推入任务。"
        return f"{mode_prefix}在 {location} 建立场面与即时任务压力。"

    def _middle_focus(self, character: str, dialogue_preference: str) -> str:
        if dialogue_preference == "dialogue_forward":
            return f"通过 {character} 与关键对手的对话交锋逼出信息、立场和代价。"
        if dialogue_preference == "narration_heavy":
            return f"以 {character} 的观察、判断和动作链条把情节推向失衡点。"
        return f"通过 {character} 的决断、对话与阻力把情节推向失衡点。"

    def _ending_focus(self, tension_preference: str) -> str:
        if tension_preference == "high_tension":
            return "让局面在高压下骤然收束，并留下立刻逼近下一章的悬念。"
        if tension_preference == "restrained":
            return "以克制的余震收束局部结果，让后果在静默中继续扩散。"
        return "在解决局部问题的同时留下新的悬念。"

    def _emotion_curve(self, tension_preference: str) -> list[str]:
        if tension_preference == "high_tension":
            return ["压抑", "逼近", "爆裂", "悬吊"]
        if tension_preference == "restrained":
            return ["冷静", "渗压", "失衡", "余震"]
        return ["克制", "逼近", "冲撞", "余震"]
