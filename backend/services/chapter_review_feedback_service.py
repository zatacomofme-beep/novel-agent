from __future__ import annotations

from uuid import UUID

from agents.model_gateway import GenerationRequest, model_gateway
from models.chapter import Chapter
from schemas.chapter import ChapterRead
from services.chapter_service import get_owned_chapter
from services.project_service import PROJECT_PERMISSION_EDIT
from sqlalchemy.ext.asyncio import AsyncSession


REVIEW_FEEDBACK_SYSTEM_PROMPT = """你是一位专业的小说编辑，代号Editor-Feedback。

用户刚刚阅读了AI生成的章节内容，并提供了反馈意见。你的任务是：

1. 深度理解用户的反馈内容
2. 总结反馈的核心要点（换位思考、情节、节奏、文笔等）
3. 生成一个明确的修改指令，用于指导AI重新生成

输出格式（Markdown）：

## 反馈理解
[简要总结用户的反馈要点]

## 修改指令
[明确的修改要求，100-200字，说明需要修改什么、如何修改]

## 优先级
- P0（必须修改）：
- P1（建议修改）：

保持专业、精准、有建设性的风格。"""

REVIEW_FEEDBACK_USER_PROMPT = """## 章节信息
章节号：第{chapter_number}章
章节标题：{title}

## 章节内容
{content}

## 用户反馈
{feedback}

请按指定格式输出。"""


async def generate_review_feedback(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
    user_feedback: str,
) -> str:
    """
    基于用户反馈生成修改指令
    """
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )

    content = chapter.content or ""
    truncated_content = content[:8000] if len(content) > 8000 else content

    user_prompt = REVIEW_FEEDBACK_USER_PROMPT.format(
        chapter_number=chapter.chapter_number,
        title=chapter.title or "无标题",
        content=truncated_content,
        feedback=user_feedback,
    )

    request = GenerationRequest(
        task_name="review_feedback_processing",
        prompt=user_prompt,
        system_prompt=REVIEW_FEEDBACK_SYSTEM_PROMPT,
        model="gemini-3.1-pro-preview",
        temperature=0.5,
        max_tokens=2000,
    )

    def fallback() -> str:
        return """## 反馈理解
用户提供了修改反馈。

## 修改指令
请根据用户反馈进行修改。
- 优先处理用户明确指出的问题
- 保持章节整体结构不变
- 确保修改后逻辑连贯

## 优先级
- P0：用户明确指出的错误
- P1：用户体验相关的问题
"""

    try:
        result = await model_gateway.generate_text(request, fallback=fallback)
        return result.content
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Review feedback processing failed: {e}")
        return fallback()


async def regenerate_chapter_with_feedback(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
    user_feedback: str,
) -> ChapterRead:
    """
    基于用户反馈重新生成章节
    返回更新后的 chapter
    """
    from tasks.chapter_generation import dispatch_generation_task, enqueue_chapter_generation_task
    from services.generation_service import build_generation_payload

    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )

    processed_feedback = await generate_review_feedback(
        session, chapter_id, user_id, user_feedback
    )

    payload = await build_generation_payload(session, chapter.id, user_id)
    payload["user_feedback"] = processed_feedback

    task_state = await enqueue_chapter_generation_task(
        str(chapter.id),
        str(user_id),
        str(chapter.project_id),
        payload,
    )
    task_state = await dispatch_generation_task(
        task_id=task_state.task_id,
        chapter_id=str(chapter.id),
        project_id=str(chapter.project_id),
        user_id=str(user_id),
    )

    await session.refresh(chapter)
    return ChapterRead.model_validate(chapter)
