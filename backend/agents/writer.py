from __future__ import annotations

from typing import Any, Callable, Optional

from bus.protocol import AgentResponse
from agents.model_gateway import GenerationRequest, model_gateway

from agents.base import AgentRunContext, BaseAgent


class WriterAgent(BaseAgent):
    DEFAULT_SEGMENTS = 4

    def __init__(self) -> None:
        super().__init__(name="writer", role="draft_author")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        chapter_number = payload["chapter_number"]
        chapter_plan = payload["chapter_plan"]
        chapter_title = chapter_plan["title"]
        project_title = payload["project_title"]
        genre = payload.get("genre") or "长篇小说"
        tone = payload.get("tone") or "克制、具体、富于画面"
        context_brief = payload["context_brief"]
        style_guidance = payload.get("style_guidance") or ""
        style_preferences = payload.get("style_preferences") or {}
        resume_from: Optional[dict[str, Any]] = payload.get("resume_from")
        save_checkpoint: Optional[Callable[..., Any]] = payload.get("save_checkpoint")
        segments_total = payload.get("segments_total", self.DEFAULT_SEGMENTS)

        segments_completed = 0
        accumulated_content = ""

        if resume_from:
            accumulated_content = resume_from.get("generated_content", "")
            segments_completed = resume_from.get("segments_completed", 0)

        segment_prompts = self._build_segment_prompts(
            chapter_plan=chapter_plan,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            project_title=project_title,
            genre=genre,
            tone=tone,
            context_brief=context_brief,
            style_guidance=style_guidance,
            style_preferences=style_preferences,
            segments_total=segments_total,
        )

        for seg_idx in range(segments_completed, segments_total):
            segment_prompt = segment_prompts[seg_idx]
            if accumulated_content and seg_idx > 0:
                segment_prompt = (
                    f"承接此前已完成的内容：\n\n{accumulated_content}\n\n"
                    f"请继续撰写下一部分，保持相同的叙事语气和风格。\n\n"
                    f"{segment_prompt}"
                )

            generation = await model_gateway.generate_text(
                GenerationRequest(
                    task_name=f"writer.draft.segment.{seg_idx + 1}",
                    prompt=segment_prompt,
                    metadata={"agent": self.name, "segment": seg_idx + 1},
                ),
                fallback=lambda cp=chapter_plan, cn=chapter_number, ct=chapter_title,
                           pt=project_title, g=genre, t=tone,
                           cb=context_brief, sp=style_preferences:
                          WriterAgent._build_segment_content_static(
                              cp, cn, ct, pt, g, t, cb, sp,
                          ),
            )
            segment_content = generation.content.strip()
            accumulated_content = f"{accumulated_content}\n\n{segment_content}".strip()

            if save_checkpoint:
                await save_checkpoint(
                    chapter_id=payload.get("chapter_id"),
                    user_id=payload.get("user_id"),
                    chapter_version_number=payload.get("chapter_version_number", 1),
                    title=chapter_title,
                    generation_payload={
                        "chapter_plan": chapter_plan,
                        "genre": genre,
                        "tone": tone,
                        "context_brief": context_brief,
                        "style_preferences": style_preferences,
                        "segments_total": segments_total,
                    },
                    generated_content=accumulated_content,
                    progress=int(((seg_idx + 1) / segments_total) * 100),
                    segments_completed=seg_idx + 1,
                    segments_total=segments_total,
                )

        return AgentResponse(
            success=True,
            data={
                "outline": chapter_plan,
                "content": accumulated_content,
                "generation": {
                    "provider": generation.provider,
                    "model": generation.model,
                    "used_fallback": generation.used_fallback,
                    "metadata": generation.metadata,
                },
            },
            confidence=0.74,
            reasoning="基于章节规划和 Story Bible 摘要生成正文草稿，优先保证本章目标、场景锚点和情绪曲线可读。",
        )

    def _build_segment_prompts(
        self,
        *,
        chapter_plan: dict[str, Any],
        chapter_number: int,
        chapter_title: str,
        project_title: str,
        genre: str,
        tone: str,
        context_brief: dict[str, Any],
        style_guidance: str,
        style_preferences: dict[str, Any],
        segments_total: int,
    ) -> list[str]:
        characters = context_brief.get("characters") or ["主角"]
        locations = context_brief.get("locations") or ["未知地点"]
        plot_threads = context_brief.get("active_plot_threads") or ["主线推进"]
        objective = chapter_plan.get("objective", "推进故事")
        narrative_mode = str(style_preferences.get("narrative_mode") or "close_third")
        pacing = str(style_preferences.get("pacing_preference") or "balanced")
        sensory = str(style_preferences.get("sensory_density") or "focused")
        seg_prompts = []
        seg_labels = ["开篇", "发展", "高潮", "收尾"]
        for i in range(segments_total):
            label = seg_labels[i] if i < len(seg_labels) else f"第{i + 1}部分"
            seg_prompts.append(
                f"Project={project_title} | Chapter={chapter_number} | Title={chapter_title}\n"
                f"Genre={genre} | Tone={tone} | Segment={label} ({i + 1}/{segments_total})\n"
                f"NarrativeMode={narrative_mode} | Pacing={pacing} | Sensory={sensory}\n"
                f"Characters={characters} | Location={locations[0]}\n"
                f"PlotThread={plot_threads[0]}\n"
                f"ChapterObjective={objective}\n"
                f"Plan={chapter_plan}\n"
                f"StyleGuidance={style_guidance}"
            )
        return seg_prompts

    def _build_segment_content(
        self,
        chapter_plan: dict[str, Any],
        chapter_number: int,
        chapter_title: str,
        project_title: str,
        genre: str,
        tone: str,
        context_brief: dict[str, Any],
        style_preferences: dict[str, Any],
    ) -> str:
        characters = context_brief.get("characters") or ["主角"]
        locations = context_brief.get("locations") or ["未知地点"]
        narrative_mode = str(style_preferences.get("narrative_mode") or "close_third")
        sensory = str(style_preferences.get("sensory_density") or "focused")
        atmosphere = {
            "minimal": "光线和风声都被压到最低，只留下最必要的危险信号。",
            "immersive": "潮气、锈味和墙面回音一层层压上来，场景先于人物开口。",
        }.get(sensory, "空气里的细节保持节制，但足够让危险感先一步落地。")

        if narrative_mode == "first_person":
            return (
                f"{chapter_title}\n\n"
                f"我在《{project_title}》的第 {chapter_number} 章回到{locations[0]}。"
                f"{atmosphere}{genre}故事惯有的压力正沿着视线边缘逼近。"
                f"我知道这一章真正要解决的是：{chapter_plan.get('objective', '推进主线')}"
            )
        if narrative_mode == "omniscient":
            return (
                f"{chapter_title}\n\n"
                f"在《{project_title}》的第 {chapter_number} 章，{locations[0]} 比任何人物都更早意识到局势将要失衡。"
                f"{atmosphere}{characters[0]}只是第一个被推上台面的承压者。"
            )
        return (
            f"{chapter_title}\n\n"
            f"在《{project_title}》的第 {chapter_number} 章里，{characters[0]}回到{locations[0]}。"
            f"{atmosphere}{genre}故事惯有的危险感贴着墙面缓慢游走。"
            f"叙事语气保持{tone}，每个细节都在逼近本章的核心目标：{chapter_plan.get('objective', '推进主线')}"
        )

    @staticmethod
    def _build_segment_content_static(
        chapter_plan: dict[str, Any],
        chapter_number: int,
        chapter_title: str,
        project_title: str,
        genre: str,
        tone: str,
        context_brief: dict[str, Any],
        style_preferences: dict[str, Any],
    ) -> str:
        characters = context_brief.get("characters") or ["主角"]
        locations = context_brief.get("locations") or ["未知地点"]
        narrative_mode = str(style_preferences.get("narrative_mode") or "close_third")
        sensory = str(style_preferences.get("sensory_density") or "focused")
        atmosphere = {
            "minimal": "光线和风声都被压到最低，只留下最必要的危险信号。",
            "immersive": "潮气、锈味和墙面回音一层层压上来，场景先于人物开口。",
        }.get(sensory, "空气里的细节保持节制，但足够让危险感先一步落地。")

        if narrative_mode == "first_person":
            return (
                f"{chapter_title}\n\n"
                f"我在《{project_title}》的第 {chapter_number} 章回到{locations[0]}。"
                f"{atmosphere}{genre}故事惯有的压力正沿着视线边缘逼近。"
                f"我知道这一章真正要解决的是：{chapter_plan.get('objective', '推进主线')}"
            )
        if narrative_mode == "omniscient":
            return (
                f"{chapter_title}\n\n"
                f"在《{project_title}》的第 {chapter_number} 章，{locations[0]} 比任何人物都更早意识到局势将要失衡。"
                f"{atmosphere}{characters[0]}只是第一个被推上台面的承压者。"
            )
        return (
            f"{chapter_title}\n\n"
            f"在《{project_title}》的第 {chapter_number} 章里，{characters[0]}回到{locations[0]}。"
            f"{atmosphere}{genre}故事惯有的危险感贴着墙面缓慢游走。"
            f"叙事语气保持{tone}，每个细节都在逼近本章的核心目标：{chapter_plan.get('objective', '推进主线')}"
        )

    def _build_content(
        self,
        *,
        chapter_number: int,
        chapter_title: str,
        project_title: str,
        genre: str,
        tone: str,
        context_brief: dict[str, Any],
        chapter_plan: dict[str, Any],
        style_preferences: dict[str, Any],
    ) -> str:
        characters = context_brief.get("characters") or ["主角"]
        locations = context_brief.get("locations") or ["未知地点"]
        plot_threads = context_brief.get("active_plot_threads") or ["主线推进"]
        foreshadowing = context_brief.get("foreshadowing_items") or []
        timeline_beats = context_brief.get("timeline_beats") or []
        favored_elements = style_preferences.get("favored_elements") or []
        narrative_mode = str(style_preferences.get("narrative_mode") or "close_third")
        pacing_preference = str(style_preferences.get("pacing_preference") or "balanced")
        dialogue_preference = str(style_preferences.get("dialogue_preference") or "balanced")
        sensory_density = str(style_preferences.get("sensory_density") or "focused")
        tension_preference = str(style_preferences.get("tension_preference") or "balanced")

        opening = self._opening(
            chapter_title=chapter_title,
            project_title=project_title,
            chapter_number=chapter_number,
            protagonist=characters[0],
            location=locations[0],
            genre=genre,
            tone=tone,
            objective=chapter_plan["objective"],
            narrative_mode=narrative_mode,
            sensory_density=sensory_density,
        )

        middle = self._middle(
            protagonist=characters[0],
            plot_thread=plot_threads[0],
            pacing_preference=pacing_preference,
            dialogue_preference=dialogue_preference,
        )

        support = ""
        if len(characters) > 1:
            support += (
                f"\n\n{characters[1]}的出现让冲突更具层次。"
                f"两人的判断并不完全一致，对话因此带出更真实的摩擦。"
            )
        if timeline_beats:
            support += (
                f"\n\n这一章也悄悄呼应了先前的时间线节点“{timeline_beats[0]}”，"
                "让事件推进不只是眼前的动作，而是此前伏线的延伸。"
            )
        if foreshadowing:
            support += (
                f"\n\n文本还回扣了早先埋下的线索：“{foreshadowing[0]}”。"
                "它不必立刻兑现，但足够让读者意识到事情并未结束。"
            )
        if favored_elements:
            support += (
                f"\n\n这一版刻意强化“{favored_elements[0]}”这一偏好元素，"
                "让章节不只推进信息，也留下更鲜明的触感和记忆点。"
            )

        ending = self._ending(
            protagonist=characters[0],
            tension_preference=tension_preference,
            narrative_mode=narrative_mode,
        )

        return opening + middle + support + ending

    def _opening(
        self,
        *,
        chapter_title: str,
        project_title: str,
        chapter_number: int,
        protagonist: str,
        location: str,
        genre: str,
        tone: str,
        objective: str,
        narrative_mode: str,
        sensory_density: str,
    ) -> str:
        atmosphere = {
            "minimal": "光线和风声都被压到最低，只留下最必要的危险信号。",
            "immersive": "潮气、锈味和墙面回音一层层压上来，场景先于人物开口。",
        }.get(sensory_density, "空气里的细节保持节制，但足够让危险感先一步落地。")

        if narrative_mode == "first_person":
            return (
                f"{chapter_title}\n\n"
                f"我在《{project_title}》的第 {chapter_number} 章回到{location}。"
                f"{atmosphere}{genre}故事惯有的压力正沿着视线边缘逼近。"
                f"叙事语气保持{tone}，我知道这一章真正要解决的是：{objective}"
            )
        if narrative_mode == "omniscient":
            return (
                f"{chapter_title}\n\n"
                f"在《{project_title}》的第 {chapter_number} 章，{location} 比任何人物都更早意识到局势将要失衡。"
                f"{atmosphere}{protagonist}只是第一个被推上台面的承压者。"
                f"叙事语气保持{tone}，所有细节都在逼近本章目标：{objective}"
            )
        return (
            f"{chapter_title}\n\n"
            f"在《{project_title}》的第 {chapter_number} 章里，{protagonist}回到{location}。"
            f"{atmosphere}{genre}故事惯有的危险感贴着墙面缓慢游走。"
            f"叙事语气保持{tone}，每个细节都在逼近本章的核心目标：{objective}"
        )

    def _middle(
        self,
        *,
        protagonist: str,
        plot_thread: str,
        pacing_preference: str,
        dialogue_preference: str,
    ) -> str:
        if pacing_preference == "fast":
            middle = (
                f"\n\n本章中段围绕“{plot_thread}”直接推进。"
                f"{protagonist}几乎没有缓冲时间，只能在连续动作里迅速判断、迅速失手、再迅速补位。"
            )
        elif pacing_preference == "slow_burn":
            middle = (
                f"\n\n本章中段围绕“{plot_thread}”缓慢收紧。"
                f"{protagonist}先确认每一道细小偏差，再意识到所有偏差正在指向同一处失衡。"
            )
        else:
            middle = (
                f"\n\n本章中段围绕“{plot_thread}”展开。"
                f"{protagonist}试图把局面拉回可控范围，但周围的信息并不愿意配合。"
            )

        if dialogue_preference == "dialogue_forward":
            middle += (
                "\n\n“你现在才来，不是为了帮我吧？”"
                "\n“我来是为了确认，你到底还敢不敢继续走下去。”"
            )
        elif dialogue_preference == "narration_heavy":
            middle += "\n\n这一段更依赖动作观察和内在判断，而不是密集对话来解释局势。"
        else:
            middle += "\n\n动作与对话交替推进，让局势变化不只是说明，而是现场发生的事。"
        return middle

    def _ending(
        self,
        *,
        protagonist: str,
        tension_preference: str,
        narrative_mode: str,
    ) -> str:
        if narrative_mode == "first_person":
            subject = "我"
        else:
            subject = protagonist

        if tension_preference == "high_tension":
            return (
                "\n\n结尾不给人物留下喘息。"
                f"{subject}刚刚看清代价，新的威胁就已经逼到眼前，章节必须在最危险的一步前骤停。"
            )
        if tension_preference == "restrained":
            return (
                "\n\n结尾并不制造外放的爆点。"
                f"{subject}只是勉强确认了后果的轮廓，真正沉重的部分会在下一章慢慢显形。"
            )
        return (
            "\n\n结尾并不提供彻底的答案。"
            f"{subject}只是勉强看清了代价，真正的后果还要在下一章落下。"
            "于是章节收束时既保留情绪余震，也给后续推进留下了悬念。"
        )
