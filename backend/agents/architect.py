from __future__ import annotations

from typing import Any

from bus.protocol import AgentResponse
from agents.model_gateway import GenerationRequest, model_gateway

from agents.base import AgentRunContext, BaseAgent


CHAPTER_PLAN_TEMPLATE = """你是长篇小说章节架构师。请为以下章节制定结构化写作计划。

## 项目信息
- 项目标题：{project_title}
- 章节编号：第 {chapter_number} 章
- 章节标题：{chapter_title}

## 项目启动设定
{bootstrap_profile_text}

## 项目蓝图
{project_blueprint_text}

## 当前章节蓝图种子
{chapter_seed_text}

## 角色信息
{characters_text}

## 地点信息
{locations_text}

## 活跃情节线
{plot_threads_text}

## 时间线节点
{timeline_beats_text}

## 活跃伏笔追踪（Open Threads）
{open_threads_text}

## 风格指导
{style_guidance}

## 风格偏好
- 叙事视角：{narrative_mode}
- 节奏偏好：{pacing_preference}
- 对话倾向：{dialogue_preference}
- 张力偏好：{tension_preference}

请以 JSON 格式输出章节计划，包含以下字段：
{{
  "chapter_number": 数字,
  "title": "字符串",
  "objective": "本章核心目标，50字以内",
  "opening": "开场策略，30字以内",
  "middle": "中段策略，30字以内",
  "ending": "收尾策略，30字以内",
  "emotion_curve": ["情感曲线词1", "情感曲线词2", "情感曲线词3", "情感曲线词4"],
  "key_scenes": ["关键场景1", "关键场景2"],
  "character_arcs": ["角色弧光1", "角色弧光2"]
}}
"""


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
        project_title = payload.get("project_title") or "未命名项目"
        context_brief = payload["context_brief"]
        style_guidance = payload.get("style_guidance") or "无特殊风格指导"
        style_preferences = payload.get("style_preferences") or {}
        project_bootstrap_profile = (
            payload.get("project_bootstrap_profile")
            if isinstance(payload.get("project_bootstrap_profile"), dict)
            else {}
        )
        novel_blueprint = (
            payload.get("novel_blueprint")
            if isinstance(payload.get("novel_blueprint"), dict)
            else {}
        )
        chapter_outline_seed = (
            payload.get("chapter_outline_seed")
            if isinstance(payload.get("chapter_outline_seed"), dict)
            else {}
        )

        characters = context_brief.get("characters") or []
        locations = context_brief.get("locations") or []
        plot_threads = context_brief.get("active_plot_threads") or []
        timeline_beats = context_brief.get("timeline_beats") or []
        foreshadowing = context_brief.get("foreshadowing_items") or []
        open_threads = context_brief.get("open_threads") or []

        characters_text = self._format_named_entries(
            characters,
            label_keys=("name", "title"),
            detail_keys=("description", "summary", "role", "conflict"),
            default="- 主角（未命名）",
            limit=6,
        )
        locations_text = self._format_named_entries(
            locations,
            label_keys=("name", "title"),
            detail_keys=("description", "summary", "type"),
            default="- 主场（未命名）",
            limit=4,
        )
        plot_threads_text = self._format_named_entries(
            plot_threads,
            label_keys=("title", "name"),
            detail_keys=("summary", "scope"),
            default="- 主线推进",
            limit=4,
        )
        timeline_beats_text = self._format_named_entries(
            timeline_beats,
            label_keys=("title", "name"),
            detail_keys=("phase", "summary"),
            default="- 暂无时间线节点",
            limit=4,
        )
        foreshadowing_text = self._format_named_entries(
            foreshadowing,
            label_keys=("title", "content", "name"),
            detail_keys=("summary", "status"),
            default="- 暂无伏笔",
            limit=3,
        )

        open_threads_text = self._format_open_threads(open_threads)

        pacing_preference = str(style_preferences.get("pacing_preference") or "balanced")
        dialogue_preference = str(style_preferences.get("dialogue_preference") or "balanced")
        tension_preference = str(style_preferences.get("tension_preference") or "balanced")
        narrative_mode = str(style_preferences.get("narrative_mode") or "close_third")

        narrative_mode_display = {
            "first_person": "第一人称",
            "omniscient": "全知视角",
            "close_third": "贴身第三人称",
        }.get(narrative_mode, "贴身第三人称")

        pacing_display = {
            "fast": "快节奏",
            "slow_burn": "慢热",
            "balanced": "均衡",
        }.get(pacing_preference, "均衡")

        tension_display = {
            "high_tension": "高张力",
            "restrained": "克制隐忍",
            "balanced": "均衡",
        }.get(tension_preference, "均衡")

        prompt = CHAPTER_PLAN_TEMPLATE.format(
            project_title=project_title,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            bootstrap_profile_text=self._build_bootstrap_profile_text(project_bootstrap_profile),
            project_blueprint_text=self._build_project_blueprint_text(novel_blueprint),
            chapter_seed_text=self._build_chapter_seed_text(chapter_outline_seed),
            characters_text=characters_text,
            locations_text=locations_text,
            plot_threads_text=plot_threads_text,
            timeline_beats_text=timeline_beats_text,
            open_threads_text=open_threads_text,
            style_guidance=style_guidance,
            narrative_mode=narrative_mode_display,
            pacing_preference=pacing_display,
            dialogue_preference=self._dialogue_preference_display(dialogue_preference),
            tension_preference=tension_display,
        )

        generation = await model_gateway.generate_text(
            GenerationRequest(
                task_name="architect.plan",
                prompt=prompt,
                metadata={"agent": self.name},
            ),
            fallback=lambda: self._build_fallback_plan(
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                characters=characters,
                locations=locations,
                plot_threads=plot_threads,
                chapter_outline_seed=chapter_outline_seed,
                pacing_preference=pacing_preference,
                dialogue_preference=dialogue_preference,
                tension_preference=tension_preference,
                narrative_mode=narrative_mode,
            ),
        )

        chapter_plan = self._parse_generated_plan(
            generation.content,
            chapter_number,
            chapter_title,
            characters=characters,
            locations=locations,
            plot_threads=plot_threads,
            chapter_outline_seed=chapter_outline_seed,
            pacing_preference=pacing_preference,
            dialogue_preference=dialogue_preference,
            tension_preference=tension_preference,
            narrative_mode=narrative_mode,
        )
        chapter_plan["generation"] = {
            "provider": generation.provider,
            "model": generation.model,
            "used_fallback": generation.used_fallback,
            "metadata": generation.metadata,
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

    def _parse_generated_plan(
        self,
        content: str,
        chapter_number: int,
        chapter_title: str,
        *,
        characters: list[Any],
        locations: list[Any],
        plot_threads: list[Any],
        chapter_outline_seed: dict[str, Any],
        pacing_preference: str,
        dialogue_preference: str,
        tension_preference: str,
        narrative_mode: str,
    ) -> dict[str, Any]:
        import json
        import re

        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                if not isinstance(parsed, dict):
                    raise ValueError("Generated plan is not a JSON object.")
                return self._validate_and_fill_plan(
                    parsed,
                    chapter_number,
                    chapter_title,
                    chapter_outline_seed=chapter_outline_seed,
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        return self._build_fallback_plan(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            characters=characters,
            locations=locations,
            plot_threads=plot_threads,
            chapter_outline_seed=chapter_outline_seed,
            pacing_preference=pacing_preference,
            dialogue_preference=dialogue_preference,
            tension_preference=tension_preference,
            narrative_mode=narrative_mode,
        )

    def _validate_and_fill_plan(
        self,
        parsed: dict[str, Any],
        chapter_number: int,
        chapter_title: str,
        *,
        chapter_outline_seed: dict[str, Any],
    ) -> dict[str, Any]:
        seed_objective = str(chapter_outline_seed.get("objective") or "").strip()
        required_fields = ["objective", "opening", "middle", "ending", "emotion_curve"]
        for field in required_fields:
            if field == "objective" and seed_objective and not parsed.get(field):
                parsed[field] = seed_objective
                continue
            if field not in parsed or not parsed[field]:
                raise ValueError(f"Missing or empty field: {field}")

        if not isinstance(parsed.get("emotion_curve"), list) or len(parsed["emotion_curve"]) < 3:
            parsed["emotion_curve"] = ["克制", "逼近", "冲撞", "余震"]

        key_scenes = parsed.get("key_scenes", [])
        if not isinstance(key_scenes, list):
            key_scenes = []
        if not key_scenes:
            key_scenes = self._seed_key_scenes(chapter_outline_seed)

        character_arcs = parsed.get("character_arcs", [])
        if not isinstance(character_arcs, list):
            character_arcs = []
        if not character_arcs:
            character_arcs = self._seed_character_arcs(chapter_outline_seed)

        return {
            "chapter_number": int(parsed.get("chapter_number", chapter_number)),
            "title": str(parsed.get("title", chapter_title)),
            "objective": str(parsed["objective"]),
            "opening": str(parsed["opening"]),
            "middle": str(parsed["middle"]),
            "ending": str(parsed["ending"]),
            "emotion_curve": parsed["emotion_curve"][:4],
            "key_scenes": [str(item) for item in key_scenes[:3]],
            "character_arcs": [str(item) for item in character_arcs[:2]],
        }

    def _build_fallback_plan(
        self,
        *,
        chapter_number: int,
        chapter_title: str,
        characters: list[Any],
        locations: list[Any],
        plot_threads: list[Any],
        chapter_outline_seed: dict[str, Any],
        pacing_preference: str,
        dialogue_preference: str,
        tension_preference: str,
        narrative_mode: str,
    ) -> dict[str, Any]:
        seed_title = str(chapter_outline_seed.get("title") or "").strip()
        seed_objective = str(chapter_outline_seed.get("objective") or "").strip()
        seed_summary = str(chapter_outline_seed.get("summary") or "").strip()

        seed_focus_characters = chapter_outline_seed.get("focus_characters")
        seed_locations = chapter_outline_seed.get("key_locations")
        seed_plot_threads = chapter_outline_seed.get("plot_thread_titles")

        main_character = self._first_label(seed_focus_characters) or self._first_label(characters) or "主角"
        main_location = self._first_label(seed_locations) or self._first_label(locations) or "主场"
        main_plot_thread = self._first_label(seed_plot_threads) or self._first_label(plot_threads) or "主线推进"

        return {
            "chapter_number": chapter_number,
            "title": seed_title or chapter_title,
            "objective": seed_objective
            or f"推动 {main_plot_thread}，同时让 {main_character} 面对更尖锐的代价。",
            "opening": self._opening_focus(main_location, pacing_preference, narrative_mode),
            "middle": self._middle_focus(main_character, dialogue_preference),
            "ending": self._ending_focus(tension_preference),
            "emotion_curve": self._emotion_curve(tension_preference),
            "key_scenes": self._seed_key_scenes(chapter_outline_seed, fallback_summary=seed_summary),
            "character_arcs": self._seed_character_arcs(chapter_outline_seed, main_character=main_character),
        }

    def _format_named_entries(
        self,
        items: list[Any],
        *,
        label_keys: tuple[str, ...],
        detail_keys: tuple[str, ...],
        default: str,
        limit: int,
    ) -> str:
        lines: list[str] = []
        for item in items[:limit]:
            label = self._label_from_item(item, label_keys)
            detail = self._detail_from_item(item, detail_keys)
            if label and detail:
                lines.append(f"- {label}: {detail}")
            elif label:
                lines.append(f"- {label}")
        return "\n".join(lines) or default

    def _build_bootstrap_profile_text(self, profile: dict[str, Any]) -> str:
        if not profile:
            return "- 暂无项目启动设定。"

        lines: list[str] = []
        protagonist_name = str(profile.get("protagonist_name") or "").strip()
        protagonist_summary = str(profile.get("protagonist_summary") or "").strip()
        supporting_cast = profile.get("supporting_cast")
        world_background = str(profile.get("world_background") or "").strip()
        core_story = str(profile.get("core_story") or "").strip()
        novel_style = str(profile.get("novel_style") or "").strip()
        prose_style = str(profile.get("prose_style") or "").strip()
        target_chapter_words = profile.get("target_chapter_words")
        special_requirements = str(profile.get("special_requirements") or "").strip()

        if protagonist_name or protagonist_summary:
            protagonist_line = protagonist_name or "主角未命名"
            if protagonist_summary:
                protagonist_line += f" / {protagonist_summary[:80]}"
            lines.append(f"- 主角：{protagonist_line}")
        if isinstance(supporting_cast, list) and supporting_cast:
            cast_labels = [
                self._label_from_item(item, ("name", "title"))
                for item in supporting_cast[:4]
            ]
            cast_labels = [label for label in cast_labels if label]
            if cast_labels:
                lines.append(f"- 关键配角：{'、'.join(cast_labels)}")
        if world_background:
            lines.append(f"- 世界背景：{world_background[:120]}")
        if core_story:
            lines.append(f"- 核心故事：{core_story[:120]}")
        if novel_style:
            lines.append(f"- 小说风格：{novel_style[:80]}")
        if prose_style:
            lines.append(f"- 行文风格：{prose_style[:80]}")
        if isinstance(target_chapter_words, int) and target_chapter_words > 0:
            lines.append(f"- 单章目标字数：约 {target_chapter_words}")
        if special_requirements:
            lines.append(f"- 特殊要求：{special_requirements[:120]}")
        return "\n".join(lines) or "- 暂无项目启动设定。"

    def _build_project_blueprint_text(self, blueprint: dict[str, Any]) -> str:
        if not blueprint:
            return "- 暂无项目蓝图。"

        lines: list[str] = []
        premise = str(blueprint.get("premise") or "").strip()
        story_engine = str(blueprint.get("story_engine") or "").strip()
        opening_hook = str(blueprint.get("opening_hook") or "").strip()
        writing_rules = blueprint.get("writing_rules")
        cast = blueprint.get("cast")
        plot_threads = blueprint.get("plot_threads")

        if premise:
            lines.append(f"- 故事命题：{premise[:120]}")
        if story_engine:
            lines.append(f"- 推进引擎：{story_engine[:120]}")
        if opening_hook:
            lines.append(f"- 开篇抓手：{opening_hook[:120]}")
        if isinstance(writing_rules, list) and writing_rules:
            rule_text = "；".join(str(item).strip() for item in writing_rules[:4] if str(item).strip())
            if rule_text:
                lines.append(f"- 写作规则：{rule_text}")
        if isinstance(cast, list) and cast:
            cast_labels = [self._label_from_item(item, ("name", "title")) for item in cast[:5]]
            cast_labels = [label for label in cast_labels if label]
            if cast_labels:
                lines.append(f"- 蓝图角色：{'、'.join(cast_labels)}")
        if isinstance(plot_threads, list) and plot_threads:
            thread_labels = [self._label_from_item(item, ("title", "name")) for item in plot_threads[:4]]
            thread_labels = [label for label in thread_labels if label]
            if thread_labels:
                lines.append(f"- 蓝图剧情线：{'、'.join(thread_labels)}")
        return "\n".join(lines) or "- 暂无项目蓝图。"

    def _build_chapter_seed_text(self, chapter_outline_seed: dict[str, Any]) -> str:
        if not chapter_outline_seed:
            return "- 暂无章节蓝图种子。"

        lines: list[str] = []
        title = str(chapter_outline_seed.get("title") or "").strip()
        objective = str(chapter_outline_seed.get("objective") or "").strip()
        summary = str(chapter_outline_seed.get("summary") or "").strip()
        expected_word_count = chapter_outline_seed.get("expected_word_count")
        focus_characters = chapter_outline_seed.get("focus_characters")
        key_locations = chapter_outline_seed.get("key_locations")
        plot_thread_titles = chapter_outline_seed.get("plot_thread_titles")
        foreshadowing_to_plant = chapter_outline_seed.get("foreshadowing_to_plant")

        if title:
            lines.append(f"- 种子标题：{title}")
        if objective:
            lines.append(f"- 本章目标：{objective[:120]}")
        if summary:
            lines.append(f"- 本章摘要：{summary[:120]}")
        if isinstance(expected_word_count, int) and expected_word_count > 0:
            lines.append(f"- 期望字数：约 {expected_word_count}")
        focus_text = self._join_labels(focus_characters)
        if focus_text:
            lines.append(f"- 聚焦人物：{focus_text}")
        location_text = self._join_labels(key_locations)
        if location_text:
            lines.append(f"- 关键地点：{location_text}")
        plot_text = self._join_labels(plot_thread_titles)
        if plot_text:
            lines.append(f"- 关联剧情线：{plot_text}")
        foreshadow_text = self._join_labels(foreshadowing_to_plant)
        if foreshadow_text:
            lines.append(f"- 待埋伏笔：{foreshadow_text}")
        return "\n".join(lines) or "- 暂无章节蓝图种子。"

    def _dialogue_preference_display(self, dialogue_preference: str) -> str:
        return {
            "dialogue_forward": "对话驱动",
            "narration_heavy": "叙述主导",
            "balanced": "均衡",
        }.get(dialogue_preference, "均衡")

    def _format_open_threads(self, open_threads: list[Any]) -> str:
        if not open_threads:
            return "- 暂无活跃伏笔"
        lines = []
        for t in open_threads[:5]:
            if isinstance(t, dict):
                entity_ref = str(t.get("entity_ref", ""))[:40]
                chapter = t.get("planted_chapter", "?")
                status = t.get("status", "open")
                priority = t.get("payoff_priority", 0.0)
                tags = ", ".join(t.get("potential_tags", [])[:2])
                lines.append(
                    f"- 【第{chapter}章】{entity_ref} "
                    f"[优先级:{priority:.1f}] [标签:{tags}] "
                    f"[状态:{status}]"
                )
            else:
                lines.append(f"- 伏笔: {str(t)[:40]}")
        return "\n".join(lines) if lines else "- 暂无活跃伏笔"

    def _label_from_item(
        self,
        item: Any,
        label_keys: tuple[str, ...] = ("name", "title", "content"),
    ) -> str:
        if isinstance(item, str):
            return item.strip()[:60]
        if not isinstance(item, dict):
            return ""
        for key in label_keys:
            value = item.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text[:60]
        return ""

    def _detail_from_item(
        self,
        item: Any,
        detail_keys: tuple[str, ...],
    ) -> str:
        if not isinstance(item, dict):
            return ""
        for key in detail_keys:
            value = item.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text[:80]
        return ""

    def _first_label(self, items: Any) -> str:
        if not isinstance(items, list) or not items:
            return ""
        return self._label_from_item(items[0])

    def _join_labels(self, items: Any, *, limit: int = 4) -> str:
        if not isinstance(items, list):
            return ""
        labels = [self._label_from_item(item) for item in items[:limit]]
        labels = [label for label in labels if label]
        return "、".join(labels)

    def _seed_key_scenes(
        self,
        chapter_outline_seed: dict[str, Any],
        *,
        fallback_summary: str = "",
    ) -> list[str]:
        scenes: list[str] = []
        objective = str(chapter_outline_seed.get("objective") or "").strip()
        summary = str(chapter_outline_seed.get("summary") or fallback_summary).strip()
        plot_thread = self._join_labels(chapter_outline_seed.get("plot_thread_titles"), limit=2)
        if objective:
            scenes.append(f"围绕“{objective}”触发本章主要行动。")
        if summary:
            scenes.append(summary[:80])
        if plot_thread:
            scenes.append(f"同步推进 {plot_thread}。")
        return scenes[:3]

    def _seed_character_arcs(
        self,
        chapter_outline_seed: dict[str, Any],
        *,
        main_character: str = "",
    ) -> list[str]:
        focus_characters = chapter_outline_seed.get("focus_characters")
        labels = []
        if isinstance(focus_characters, list):
            labels = [
                self._label_from_item(item)
                for item in focus_characters[:2]
            ]
            labels = [label for label in labels if label]
        if not labels and main_character:
            labels = [main_character]
        return [f"{name} 必须为本章推进做出带代价的选择。" for name in labels[:2]]

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
