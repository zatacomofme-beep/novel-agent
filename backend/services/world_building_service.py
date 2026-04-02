from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from agents.model_gateway import GenerationRequest, GenerationResult, model_gateway
from models.project import Project
from models.world_building_session import WorldBuildingSession
from schemas.world_building import (
    WorldBuildingSessionRead,
    WorldBuildingStartResponse,
    WorldBuildingStepResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession


STEPS = [
    {
        "step": 1,
        "key": "world_base",
        "title": "世界基底",
        "initial_question": "请问，这是一个什么样的世界？",
        "can_skip": False,
    },
    {
        "step": 2,
        "key": "physical_world",
        "title": "物理世界",
        "initial_question": "这个世界的物理法则和自然环境有什么特别之处？",
        "can_skip": False,
    },
    {
        "step": 3,
        "key": "power_system",
        "title": "力量体系",
        "initial_question": "这个世界存在什么样的力量体系或超凡能力？",
        "can_skip": False,
    },
    {
        "step": 4,
        "key": "society",
        "title": "社会结构",
        "initial_question": "这个世界的社会结构、势力划分和主要矛盾是什么？",
        "can_skip": False,
    },
    {
        "step": 5,
        "key": "protagonist",
        "title": "主角定位",
        "initial_question": "你的主角是什么人？有什么独特之处？",
        "can_skip": False,
    },
    {
        "step": 6,
        "key": "core_conflict",
        "title": "核心冲突",
        "initial_question": "故事的核心冲突是什么？主角面临的主要挑战是什么？",
        "can_skip": False,
    },
    {
        "step": 7,
        "key": "world_details",
        "title": "世界细节",
        "initial_question": "还有什么想要补充的世界设定吗？如历史、文化、地理等。",
        "can_skip": True,
    },
    {
        "step": 8,
        "key": "style_preference",
        "title": "风格偏好",
        "initial_question": "你希望故事的整体风格是什么样的？轻松、压抑、热血？",
        "can_skip": True,
    },
]


STEP_SYSTEM_PROMPTS = {
    1: """你是一位白金级网文作者，写过上百部畅销网文，熟悉玄幻、仙侠、都市、穿越等各类网文套路与写作节奏。

用户要写一本小说，但世界观还没定。你需要：
1. 深度理解用户描述的世界雏形——是什么类型的世界、核心卖点是什么
2. 用网文作者的直觉补充世界设定中的空白，让世界更有张力和吸引力
3. 追问 2-3 个能加深世界深度、让故事更精彩的关键问题

追问要具体有深度，能激发用户的想象力。不要问过于宽泛的问题，要问能直接转化成精彩情节的问题。

输出格式（Markdown）：
## 世界基底
[用网文语言描述这个世界，要有画面感和吸引力]

## 追问
[2-3个具体有深度的问题，帮助用户完善这个世界]""",

    2: """你是一位白金级网文作者，写过上百部畅销网文，熟悉玄幻、仙侠、都市、穿越等各类网文套路与写作节奏。

用户已经描述了世界基底，现在追问这个世界的物理法则和自然环境。你需要：
1. 从网文角度分析这个世界的物理环境有什么看点
2. 时间、空间、自然法则等设定是否能制造冲突和爽点
3. 追问 1-2 个能加深世界物理层面深度的问题

输出格式（Markdown）：
## 物理世界
[用网文语言描述这个世界的物理环境，要有画面感]

## 追问
[1-2个关于物理环境的问题，让设定转化为故事情节]""",

    3: """你是一位白金级网文作者，写过上百部畅销网文，熟悉玄幻、仙侠、都市、穿越等各类网文套路与写作节奏。

用户已经描述了世界基底，现在追问力量体系。力量体系是网文最核心的看点之一，你需要：
1. 分析什么样的力量体系最能让读者兴奋、最有爽感
2. 力量从何而来、如何修炼、代价是什么
3. 追问 1-2 个能让力量体系更有张力的关键问题

输出格式（Markdown）：
## 力量体系
[描述这个世界的力量体系，用网文语言讲清楚设定]

## 追问
[1-2个关于力量体系的问题，让设定转化为战斗爽点]""",

    4: """你是一位白金级网文作者，写过上百部畅销网文，熟悉玄幻、仙侠、都市、穿越等各类网文套路与写作节奏。

用户已经描述了世界和力量体系，现在追问社会结构。网文里的势力关系是剧情推进的核心，你需要：
1. 分析主要势力、门派、种族之间的格局
2. 势力之间的矛盾和利益冲突是什么
3. 追问 1-2 个能让势力关系更有戏剧性的关键问题

输出格式（Markdown）：
## 社会结构
[用网文语言描述这个世界的主要势力格局和关系]

## 追问
[1-2个关于势力格局的问题，让设定转化为派系争斗]""",

    5: """你是一位白金级网文作者，写过上百部畅销网文，熟悉玄幻、仙侠、都市、穿越等各类网文套路与写作节奏。

用户已经描述了世界，现在追问主角定位。主角是网文的灵魂，你需要：
1. 分析最适合这个世界的男主角/女主角类型（废物流、逆袭流、热血流、苟道流？）
2. 主角的初始处境和核心优势是什么
3. 追问 1-2 个能让主角更有记忆点、故事更有张力的关键问题

输出格式（Markdown）：
## 主角定位
[用网文语言描述这个世界的男主角/女主角设定]

## 追问
[1-2个关于主角设定的问题，让角色更立体更有爽感]""",

    6: """你是一位白金级网文作者，写过上百部畅销网文，熟悉玄幻、仙侠、都市、穿越等各类网文套路与写作节奏。

用户已经描述了世界、力量体系、社会和主角，现在追问核心冲突。冲突是故事的核心张力，你需要：
1. 分析这个世界最核心的主线冲突是什么
2. 主角要对抗的主要矛盾和对手是谁
3. 追问 1-2 个能让故事主线更有爆发力的关键问题

输出格式（Markdown）：
## 核心冲突
[用网文语言描述这个故事最核心的冲突和看点]

## 追问
[1-2个关于核心冲突的问题，让主线更有爆发力]""",

    7: """你是一位白金级网文作者，写过上百部畅销网文，熟悉玄幻、仙侠、都市、穿越等各类网文套路与写作节奏。

用户已经完成了主要设定，现在是可选的细节补充环节。你需要：
1. 简要总结用户已经确定的设定框架
2. 询问用户是否要补充历史背景、地理细节、文化特色、特殊种族、神器法宝等额外设定
3. 如果补充，这些设定能为故事增加什么看点

输出格式（Markdown）：
## 设定总结
[简要总结已确定的框架]

## 细节补充
[询问用户是否想要补充额外设定，如历史、地理、文化、种族、法宝等]""",

    8: """你是一位白金级网文作者，写过上百部畅销网文，熟悉玄幻、仙侠、都市、穿越等各类网文套路与写作节奏。

用户已经完成了主要世界观设定，现在是风格确认环节。你需要：
1. 根据用户前面的回答，推断这本小说的整体风格和核心卖点
2. 确认用户对节奏、基调、爽点类型的偏好
3. 给出你对这个故事风格的建议

输出格式（Markdown）：
## 风格推断
[你根据前面的设定推断的故事风格和核心卖点]

## 风格确认
[询问用户对节奏、情感基调、爽点类型的偏好]""",
}


def _get_step_config(step: int) -> dict:
    return next((s for s in STEPS if s["step"] == step), STEPS[0])


@dataclass
class WorldBuildingContext:
    session: WorldBuildingSession
    step: int
    step_title: str
    model_summary: str
    model_expansion: str
    is_awaiting_follow_up: bool
    can_skip: bool
    is_complete: bool


class WorldBuildingService:

    async def start_session(
        self,
        session: AsyncSession,
        project: Project,
        user_id: UUID,
        initial_idea: str,
    ) -> WorldBuildingStartResponse:
        existing = await session.execute(
            select(WorldBuildingSession).where(
                WorldBuildingSession.project_id == project.id,
                WorldBuildingSession.user_id == user_id,
                WorldBuildingSession.status == "in_progress",
            )
        )
        existing_session = existing.scalar_one_or_none()
        if existing_session:
            step_1_config = _get_step_config(1)
            return WorldBuildingStartResponse(
                session=WorldBuildingSessionRead.model_validate(existing_session),
                first_question=step_1_config["initial_question"],
                step=existing_session.current_step,
                step_title=step_1_config["title"],
            )

        new_session = WorldBuildingSession(
            project_id=project.id,
            user_id=user_id,
            current_step=1,
            last_active_step=1,
            session_data={"initial_idea": initial_idea},
            status="in_progress",
            completed_steps=[],
        )
        session.add(new_session)
        await session.commit()
        await session.refresh(new_session)

        step_1_config = _get_step_config(1)
        return WorldBuildingStartResponse(
            session=WorldBuildingSessionRead.model_validate(new_session),
            first_question=step_1_config["initial_question"],
            step=1,
            step_title=step_1_config["title"],
        )

    async def process_step(
        self,
        session: AsyncSession,
        session_id: UUID,
        user_id: UUID,
        user_input: str,
        skip_to_next: bool = False,
    ) -> WorldBuildingStepResponse:
        result = await session.execute(
            select(WorldBuildingSession).where(
                WorldBuildingSession.id == session_id,
                WorldBuildingSession.user_id == user_id,
            )
        )
        wb_session = result.scalar_one_or_none()
        if not wb_session:
            raise ValueError("Session not found")

        current_step = wb_session.current_step
        step_config = _get_step_config(current_step)

        if skip_to_next and step_config.get("can_skip"):
            return await self._advance_to_next_step(session, wb_session, user_input)

        step_key = f"step_{current_step}"
        session_data = dict(wb_session.session_data)

        if step_key not in session_data:
            session_data[step_key] = {}

        session_data[step_key]["user_input"] = user_input

        model_response = await self._generate_step_response(
            current_step, user_input, session_data
        )

        session_data[step_key]["model_summary"] = model_response.get("summary", "")
        session_data[step_key]["model_expansion"] = model_response.get("expansion", "")

        if model_response.get("needs_follow_up"):
            session_data[step_key]["follow_up_input"] = ""
            wb_session.session_data = session_data
            wb_session.last_active_step = current_step
            await session.commit()

            return WorldBuildingStepResponse(
                step=current_step,
                step_title=step_config["title"],
                model_summary=model_response.get("summary", ""),
                model_expansion=model_response.get("expansion", ""),
                is_awaiting_follow_up=True,
                suggested_next_step=current_step,
                can_skip=step_config.get("can_skip", False),
                is_complete=False,
            )
        else:
            if current_step not in wb_session.completed_steps:
                wb_session.completed_steps = wb_session.completed_steps + [current_step]

            next_step = current_step + 1 if current_step < 8 else current_step
            is_complete = current_step == 8

            if not is_complete:
                wb_session.current_step = next_step
                wb_session.last_active_step = next_step
            else:
                wb_session.status = "completed"
                wb_session.session_data = session_data
                await session.commit()
                
                success = await self._trigger_blueprint_generation(session, wb_session, user_id)
                if not success:
                    wb_session.status = "failed"
                    await session.commit()
                
                next_step_config = _get_step_config(next_step)
                return WorldBuildingStepResponse(
                    step=current_step,
                    step_title=step_config["title"],
                    model_summary=model_response.get("summary", ""),
                    model_expansion=model_response.get("expansion", ""),
                    is_awaiting_follow_up=False,
                    suggested_next_step=next_step,
                    can_skip=step_config.get("can_skip", False),
                    is_complete=is_complete,
                    generation_failed=not success,
                )

    async def _trigger_blueprint_generation(
        self,
        session: AsyncSession,
        wb_session: WorldBuildingSession,
        user_id: UUID,
    ) -> bool:
        """Trigger blueprint generation after world-building completion.
        
        Returns:
            True if successful, False if failed.
        """
        from services.project_bootstrap_service import generate_project_blueprint
        from models.project import Project
        from sqlalchemy import select

        result = await session.execute(
            select(Project).where(Project.id == wb_session.project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            return False

        session_data = wb_session.session_data
        world_summary = self._compile_world_summary(session_data)

        step5 = session_data.get("step_5", {})
        protagonist_raw = step5.get("user_input", "") if isinstance(step5, dict) else ""
        protagonist_name = protagonist_raw.strip().split("\n")[0][:100] if protagonist_raw.strip() else ""

        existing = project.bootstrap_profile if isinstance(project.bootstrap_profile, dict) else {}
        project.bootstrap_profile = {
            **existing,
            "core_story": session_data.get("initial_idea", ""),
            "world_background": world_summary,  # Use world_background for schema compatibility
            "world_summary": world_summary,  # Keep world_summary for backward compatibility
            "step_data": session_data,
            "planned_chapter_count": existing.get("planned_chapter_count") or 120,
        }
        if protagonist_name and not existing.get("protagonist_name"):
            project.bootstrap_profile["protagonist_name"] = protagonist_name
        if protagonist_raw and not existing.get("protagonist_summary"):
            project.bootstrap_profile["protagonist_summary"] = protagonist_raw.strip()
        
        try:
            await generate_project_blueprint(session, project.id, user_id)
            await session.commit()
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(f"Blueprint generation failed for project {project.id}: {e}")
            await session.rollback()
            wb_session.status = "in_progress"
            wb_session.current_step = 8
            wb_session.last_active_step = 8
            await session.commit()
            return False

    def _compile_world_summary(self, session_data: dict) -> str:
        summary_parts = []
        for step_num in range(1, 9):
            step_key = f"step_{step_num}"
            if step_key in session_data:
                step_info = session_data[step_key]
                step_config = _get_step_config(step_num)
                user_input = step_info.get("user_input", "")
                if user_input and not step_info.get("skipped"):
                    summary_parts.append(f"【{step_config['title']}】{user_input}")
        return "\n\n".join(summary_parts)

    async def _generate_step_response(
        self,
        step: int,
        user_input: str,
        session_data: dict,
    ) -> dict:
        system_prompt = STEP_SYSTEM_PROMPTS.get(
            step, STEP_SYSTEM_PROMPTS.get(1, "")
        )

        context_parts = []
        if "initial_idea" in session_data:
            context_parts.append(f"用户初始想法：{session_data['initial_idea']}")

        for s in range(1, step):
            step_key = f"step_{s}"
            if step_key in session_data:
                step_info = session_data[step_key]
                step_config = _get_step_config(s)
                context_parts.append(
                    f"【{step_config['title']}】用户：{step_info.get('user_input', '')}"
                )
                if step_info.get("model_summary"):
                    context_parts.append(f"AI总结：{step_info.get('model_summary', '')}")

        context_str = "\n\n".join(context_parts)

        user_prompt = f"""## 历史上下文
{context_str}

## 当前输入
用户回答：{user_input}

请按指定格式输出。"""

        request = GenerationRequest(
            task_name=f"world_building_step_{step}",
            prompt=user_prompt,
            system_prompt=system_prompt,
            model="gemini-3.1-pro-preview",
            temperature=0.7,
            max_tokens=2000,
        )

        def fallback() -> str:
            return json.dumps({
                "summary": "【Fallback模式】AI服务暂时不可用，请稍后再试。",
                "expansion": "请描述你想要的世界特征，我会帮你完善设定。",
                "needs_follow_up": True,
            })

        try:
            result = await model_gateway.generate_text(request, fallback=fallback)
            return self._parse_model_response(result.content)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(f"World building step {step} failed: {e}")
            return {
                "summary": "处理过程中出现错误，请稍后再试。",
                "expansion": "请描述你想要的世界特征。",
                "needs_follow_up": True,
            }

    async def process_step_stream(
        self,
        session: AsyncSession,
        session_id: UUID,
        user_id: UUID,
        user_input: str,
        skip_to_next: bool = False,
    ):
        result = await session.execute(
            select(WorldBuildingSession).where(
                WorldBuildingSession.id == session_id,
                WorldBuildingSession.user_id == user_id,
            )
        )
        wb_session = result.scalar_one_or_none()
        if not wb_session:
            raise ValueError("Session not found")

        current_step = wb_session.current_step
        step_config = _get_step_config(current_step)

        if skip_to_next and step_config.get("can_skip"):
            async for event in self._stream_advance_to_next_step(session, wb_session, user_id):
                yield event
            return

        step_key = f"step_{current_step}"
        session_data = dict(wb_session.session_data)
        if step_key not in session_data:
            session_data[step_key] = {}
        session_data[step_key]["user_input"] = user_input

        yield {
            "event": "start",
            "step": current_step,
            "step_title": step_config["title"],
            "is_awaiting_follow_up": False,
            "can_skip": step_config.get("can_skip", False),
            "suggested_next_step": current_step,
            "is_complete": False,
            "model_summary": "",
        }

        summary_buffer = ""
        expansion_buffer = ""
        needs_follow_up = True

        async for chunk in self._stream_step_response(current_step, user_input, session_data):
            if "error" in chunk:
                yield {**chunk, "event": "error"}
                return

            delta = chunk.get("content", "")
            if delta:
                summary_buffer += delta
                yield {
                    "event": "chunk",
                    "delta": delta,
                    "model_summary": summary_buffer,
                }

            if chunk.get("finish_reason") and chunk.get("_accumulated"):
                full_text = chunk["_accumulated"]
                parsed = self._parse_model_response(full_text)
                summary_buffer = parsed.get("summary", summary_buffer)
                expansion_buffer = parsed.get("expansion", "")
                needs_follow_up = parsed.get("needs_follow_up", True)

        session_data[step_key]["model_summary"] = summary_buffer
        session_data[step_key]["model_expansion"] = expansion_buffer

        if needs_follow_up:
            session_data[step_key]["follow_up_input"] = ""
            wb_session.session_data = session_data
            wb_session.last_active_step = current_step
            await session.commit()

            yield {
                "event": "done",
                "step": current_step,
                "step_title": step_config["title"],
                "model_summary": summary_buffer,
                "model_expansion": expansion_buffer,
                "is_awaiting_follow_up": True,
                "can_skip": step_config.get("can_skip", False),
                "suggested_next_step": current_step,
                "is_complete": False,
            }
        else:
            if current_step not in wb_session.completed_steps:
                wb_session.completed_steps = wb_session.completed_steps + [current_step]

            next_step = current_step + 1 if current_step < 8 else current_step
            is_complete = current_step == 8

            if not is_complete:
                wb_session.current_step = next_step
                wb_session.last_active_step = next_step
                await session.commit()
            else:
                wb_session.status = "completed"
                wb_session.session_data = session_data
                await session.commit()
                
                success = await self._trigger_blueprint_generation(session, wb_session, user_id)
                if not success:
                    wb_session.status = "failed"
                    await session.commit()

            if is_complete:
                wb_session.session_data = session_data
                await session.commit()

            yield {
                "event": "done",
                "step": current_step,
                "step_title": step_config["title"],
                "model_summary": summary_buffer,
                "model_expansion": expansion_buffer,
                "is_awaiting_follow_up": False,
                "can_skip": step_config.get("can_skip", False),
                "suggested_next_step": next_step,
                "is_complete": is_complete,
                "generation_failed": is_complete and not success,
            }

    async def _stream_step_response(
        self,
        step: int,
        user_input: str,
        session_data: dict,
    ):
        system_prompt = STEP_SYSTEM_PROMPTS.get(
            step, STEP_SYSTEM_PROMPTS.get(1, "")
        )

        context_parts = []
        if "initial_idea" in session_data:
            context_parts.append(f"用户初始想法：{session_data['initial_idea']}")

        for s in range(1, step):
            step_key = f"step_{s}"
            if step_key in session_data:
                step_info = session_data[step_key]
                step_config = _get_step_config(s)
                context_parts.append(
                    f"【{step_config['title']}】用户：{step_info.get('user_input', '')}"
                )
                if step_info.get("model_summary"):
                    context_parts.append(f"AI总结：{step_info.get('model_summary', '')}")

        context_str = "\n\n".join(context_parts)

        user_prompt = f"""## 历史上下文
{context_str}

## 当前输入
用户回答：{user_input}

请按指定格式输出。"""

        request = GenerationRequest(
            task_name=f"world_building_step_{step}",
            prompt=user_prompt,
            system_prompt=system_prompt,
            model="gemini-3.1-pro-preview",
            temperature=0.7,
            max_tokens=2000,
        )

        try:
            async for chunk in model_gateway.stream_text(request):
                yield chunk
        except Exception as e:
            yield {"error": str(e)}

    async def _stream_advance_to_next_step(
        self,
        session: AsyncSession,
        wb_session: WorldBuildingSession,
        user_id: UUID,
    ):
        current_step = wb_session.current_step
        step_config = _get_step_config(current_step)

        step_key = f"step_{current_step}"
        session_data = dict(wb_session.session_data)
        session_data[step_key] = session_data.get(step_key, {})
        session_data[step_key]["skipped"] = True

        if current_step not in wb_session.completed_steps:
            wb_session.completed_steps = wb_session.completed_steps + [current_step]

        next_step = current_step + 1 if current_step < 8 else current_step
        is_complete = current_step == 8

        if not is_complete:
            wb_session.current_step = next_step
            wb_session.last_active_step = next_step
        else:
            wb_session.status = "completed"
            wb_session.session_data = session_data
            await session.commit()
            
            success = await self._trigger_blueprint_generation(session, wb_session, user_id)
            if not success:
                wb_session.status = "failed"
                await session.commit()

        if is_complete:
            wb_session.session_data = session_data
            await session.commit()

        yield {
            "event": "done",
            "step": current_step,
            "step_title": step_config["title"],
            "model_summary": "",
            "model_expansion": "",
            "is_awaiting_follow_up": False,
            "can_skip": step_config.get("can_skip", False),
            "suggested_next_step": next_step,
            "is_complete": is_complete,
            "generation_failed": is_complete and not success,
        }

    def _parse_model_response(self, content: str) -> dict:
        try:
            summary = ""
            expansion = ""
            needs_follow_up = True

            lines = content.split("\n")
            current_section = None
            section_content = []

            for line in lines:
                if "## " in line:
                    if current_section == "summary" and section_content:
                        summary = "\n".join(section_content).strip()
                    elif current_section == "expansion" and section_content:
                        expansion = "\n".join(section_content).strip()
                    section_content = []
                    if "总结" in line.lower() or "理解" in line.lower():
                        current_section = "summary"
                    elif "追问" in line.lower() or "询问" in line.lower() or "确认" in line.lower():
                        current_section = "expansion"
                else:
                    section_content.append(line)

            if current_section == "summary" and section_content:
                summary = "\n".join(section_content).strip()
            elif current_section == "expansion" and section_content:
                expansion = "\n".join(section_content).strip()

            if not expansion and summary:
                needs_follow_up = False

            return {
                "summary": summary or content[:500],
                "expansion": expansion or "",
                "needs_follow_up": needs_follow_up,
            }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Model response parsing failed: {e}")
            return {
                "summary": content[:500] if content else "解析失败",
                "expansion": "",
                "needs_follow_up": True,
            }

    async def _advance_to_next_step(
        self,
        session: AsyncSession,
        wb_session: WorldBuildingSession,
        user_input: str,
    ) -> WorldBuildingStepResponse:
        current_step = wb_session.current_step
        step_config = _get_step_config(current_step)

        step_key = f"step_{current_step}"
        session_data = dict(wb_session.session_data)
        session_data[step_key] = session_data.get(step_key, {})
        session_data[step_key]["user_input"] = user_input
        session_data[step_key]["skipped"] = True

        if current_step not in wb_session.completed_steps:
            wb_session.completed_steps = wb_session.completed_steps + [current_step]

        next_step = current_step + 1 if current_step < 8 else current_step
        is_complete = current_step == 8

        if not is_complete:
            wb_session.current_step = next_step
            wb_session.last_active_step = next_step
        else:
            wb_session.status = "completed"
            wb_session.session_data = session_data
            await session.commit()
            
            success = await self._trigger_blueprint_generation(session, wb_session, user_id)
            if not success:
                wb_session.status = "failed"
                await session.commit()
                return WorldBuildingStepResponse(
                    step=current_step,
                    step_title=step_config["title"],
                    model_summary="",
                    model_expansion="",
                    is_awaiting_follow_up=False,
                    suggested_next_step=8,
                    can_skip=step_config.get("can_skip", False),
                    is_complete=True,
                    generation_failed=True,
                )

        if is_complete:
            wb_session.session_data = session_data
        
        wb_session.session_data = session_data
        await session.commit()

        next_step_config = _get_step_config(next_step)
        return WorldBuildingStepResponse(
            step=current_step,
            step_title=step_config["title"],
            model_summary="",
            model_expansion="",
            is_awaiting_follow_up=False,
            suggested_next_step=next_step,
            can_skip=step_config.get("can_skip", False),
            is_complete=is_complete,
        )

    async def get_session(
        self,
        session: AsyncSession,
        session_id: UUID,
        user_id: UUID,
    ) -> WorldBuildingSessionRead:
        result = await session.execute(
            select(WorldBuildingSession).where(
                WorldBuildingSession.id == session_id,
                WorldBuildingSession.user_id == user_id,
            )
        )
        wb_session = result.scalar_one_or_none()
        if not wb_session:
            raise ValueError("Session not found")
        return WorldBuildingSessionRead.model_validate(wb_session)

    async def get_current_session(
        self,
        session: AsyncSession,
        project_id: UUID,
        user_id: UUID,
    ) -> Optional[WorldBuildingSessionRead]:
        result = await session.execute(
            select(WorldBuildingSession).where(
                WorldBuildingSession.project_id == project_id,
                WorldBuildingSession.user_id == user_id,
                WorldBuildingSession.status == "in_progress",
            )
        )
        wb_session = result.scalar_one_or_none()
        if not wb_session:
            return None
        return WorldBuildingSessionRead.model_validate(wb_session)

    async def list_sessions(
        self,
        session: AsyncSession,
        project_id: UUID,
        user_id: UUID,
        status: Optional[str] = None,
    ) -> list[WorldBuildingSessionRead]:
        stmt = select(WorldBuildingSession).where(
            WorldBuildingSession.project_id == project_id,
            WorldBuildingSession.user_id == user_id,
        )
        if status:
            stmt = stmt.where(WorldBuildingSession.status == status)
        stmt = stmt.order_by(WorldBuildingSession.created_at.desc())
        result = await session.execute(stmt)
        sessions = result.scalars().all()
        return [WorldBuildingSessionRead.model_validate(s) for s in sessions]


from sqlalchemy import select
