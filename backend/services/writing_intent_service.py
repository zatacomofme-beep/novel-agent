from __future__ import annotations

import json
import logging
from uuid import UUID

from agents.model_gateway import GenerationRequest, model_gateway
from models.chapter import Chapter
from schemas.chapter import ChapterRead
from services.chapter_service import update_chapter
from services.project_service import PROJECT_PERMISSION_EDIT, get_owned_chapter
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

WRITING_INTENT_SYSTEM_PROMPT = """你是一位资深的小说写作策划师，代号Architect-Writing。

你的任务是为一本书的某个章节制定写作计划（Writing Intent）。

工作流程：
1. 根据提供的大纲（outline）和上下文，理解这一章节的核心目的
2. 提炼本章的核心写作目标：用100-300字描述这一章打算怎么写
3. 说明本章的：主线推进、关键场景、情感节奏、预期爽点

输出格式（纯文本）：
## 章节写作意图
[100-300字的章节写作计划]

## 本章重点
- [关键场景1]
- [关键场景2]
- [情感节奏]
- [预期效果]

保持专业、简洁、有洞察力的风格。"""

WRITING_INTENT_USER_PROMPT = """## 项目信息
标题：{title}
类型：{genre}
主题：{theme}
基调：{tone}

## 章节信息
章节号：第{chapter_number}章
章节标题：{chapter_title}

## 大纲
{outline}

## 前文概要
{previous_summary}

请制定本章的写作意图。"""


async def generate_writing_intent(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
) -> str:
    """
    为指定章节生成写作意图（100-300字）
    返回生成的写作意图文本
    """
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )

    outline = chapter.outline if isinstance(chapter.outline, dict) else {}
    outline_str = json.dumps(outline, ensure_ascii=False, indent=2) if outline else "无"

    project = await session.get("Project", chapter.project_id)
    title = project.title if project else "未命名"
    genre = project.genre or ""
    theme = project.theme or ""
    tone = project.tone or ""

    user_prompt = WRITING_INTENT_USER_PROMPT.format(
        title=title,
        genre=genre,
        theme=theme,
        tone=tone,
        chapter_number=chapter.chapter_number,
        chapter_title=chapter.title or "无标题",
        outline=outline_str,
        previous_summary="暂无前文概要",
    )

    request = GenerationRequest(
        task_name="writing_intent_generation",
        prompt=user_prompt,
        system_prompt=WRITING_INTENT_SYSTEM_PROMPT,
        model="gemini-3.1-pro-preview",
        temperature=0.7,
        max_tokens=1500,
    )

    def fallback() -> str:
        return """## 章节写作意图
本章将围绕主线剧情推进，重点描写关键场景。
情感节奏将从前期的紧张铺垫逐步转向后期的爆发。
预期效果是让读者感受到主角的成长与突破。

## 本章重点
- 关键场景：主角面临挑战
- 情感节奏：紧张到释放
- 预期效果：爽点突出"""

    try:
        result = await model_gateway.generate_text(request, fallback=fallback)
        await _save_writing_intent(session, chapter, result.content)
        return result.content
    except Exception as e:
        logger.error("Writing intent generation failed for chapter %s: %s", chapter_id, e)
        return fallback()


async def approve_writing_intent(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
) -> ChapterRead:
    """
    用户确认写作意图，更新 chapter 状态，返回更新后的 chapter
    """
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    if not chapter.writing_intent:
        raise ValueError("No writing intent to approve")

    chapter.writing_intent_approved = True
    await session.commit()
    await session.refresh(chapter)
    return ChapterRead.model_validate(chapter)


async def update_writing_intent(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
    new_intent: str,
) -> ChapterRead:
    """
    用户修改写作意图，重新保存
    """
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    chapter.writing_intent = new_intent
    chapter.writing_intent_approved = False
    await session.commit()
    await session.refresh(chapter)
    return ChapterRead.model_validate(chapter)


async def _save_writing_intent(
    session: AsyncSession,
    chapter: Chapter,
    intent: str,
) -> None:
    chapter.writing_intent = intent
    chapter.writing_intent_approved = False
    await session.commit()
