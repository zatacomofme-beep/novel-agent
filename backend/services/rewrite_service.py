from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.model_gateway import GenerationRequest, model_gateway
from core.errors import AppError
from memory.story_bible import load_story_bible_context
from models.chapter_comment import ChapterComment
from schemas.chapter import (
    ChapterRead,
    ChapterSelectionRewriteRequest,
    ChapterSelectionRewriteResponse,
    ChapterUpdate,
)
from services.chapter_service import get_owned_chapter, update_chapter
from services.preference_service import (
    build_style_guidance,
    get_or_create_user_preference,
    get_preference_learning_snapshot,
    resolve_generation_preference_payload,
)
from services.project_service import PROJECT_PERMISSION_EDIT


async def rewrite_chapter_selection(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
    payload: ChapterSelectionRewriteRequest,
) -> ChapterSelectionRewriteResponse:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    content = chapter.content or ""
    original_text = _slice_selection(
        content,
        start=payload.selection_start,
        end=payload.selection_end,
    )
    preference = await get_or_create_user_preference(session, user_id)
    learning_snapshot = await get_preference_learning_snapshot(session, user_id)
    style_preferences = resolve_generation_preference_payload(
        preference,
        learning_snapshot,
    )
    style_guidance = build_style_guidance(style_preferences, learning_snapshot)
    story_bible = await load_story_bible_context(
        session,
        chapter.project_id,
        user_id,
        branch_id=chapter.branch_id,
    )
    related_comments = await _load_overlapping_comments(
        session,
        chapter_id=chapter.id,
        selection_start=payload.selection_start,
        selection_end=payload.selection_end,
    )
    prompt = _build_selection_rewrite_prompt(
        chapter=chapter,
        original_text=original_text,
        instruction=payload.instruction,
        style_guidance=style_guidance,
        story_bible=story_bible,
        content=content,
        selection_start=payload.selection_start,
        selection_end=payload.selection_end,
        related_comments=related_comments,
    )
    generation = await model_gateway.generate_text(
        GenerationRequest(
            task_name="chapter.partial_rewrite",
            system_prompt=(
                "你是长篇小说修订编辑。"
                "只输出改写后的片段文本，不要解释、不要加标题、不要加引号。"
            ),
            prompt=prompt,
            temperature=0.55,
            max_tokens=900,
            metadata={
                "chapter_id": str(chapter.id),
                "project_id": str(chapter.project_id),
                "selection_start": payload.selection_start,
                "selection_end": payload.selection_end,
                "related_comment_count": len(related_comments),
            },
        ),
        fallback=lambda: _fallback_rewrite(
            original_text=original_text,
            instruction=payload.instruction,
            style_guidance=style_guidance,
            related_comments=related_comments,
        ),
    )
    rewritten_text = _normalize_rewritten_text(generation.content, original_text)
    updated_content = _replace_selection(
        content,
        start=payload.selection_start,
        end=payload.selection_end,
        replacement=rewritten_text,
    )
    change_reason = _build_change_reason(payload.instruction)
    updated_chapter = await update_chapter(
        session,
        chapter,
        ChapterUpdate(
            content=updated_content,
            change_reason=change_reason,
            create_version=payload.create_version,
        ),
        preference_learning_user_id=user_id,
        preference_learning_source="partial_rewrite",
    )
    return ChapterSelectionRewriteResponse(
        chapter=ChapterRead.model_validate(updated_chapter),
        selection_start=payload.selection_start,
        selection_end=payload.selection_end,
        rewritten_selection_end=payload.selection_start + len(rewritten_text),
        original_text=original_text,
        rewritten_text=rewritten_text,
        instruction=payload.instruction.strip(),
        change_reason=change_reason,
        related_comment_count=len(related_comments),
        generation={
            "provider": generation.provider,
            "model": generation.model,
            "used_fallback": generation.used_fallback,
            "metadata": generation.metadata,
        },
    )


def _build_selection_rewrite_prompt(
    *,
    chapter,
    original_text: str,
    instruction: str,
    style_guidance: str,
    story_bible,
    content: str,
    selection_start: int,
    selection_end: int,
    related_comments: list[str],
) -> str:
    before_context = content[max(0, selection_start - 180):selection_start].strip()
    after_context = content[selection_end:selection_end + 180].strip()
    character_names = ", ".join(item.get("name", "") for item in story_bible.characters[:6] if item.get("name"))
    plot_threads = ", ".join(item.get("title", "") for item in story_bible.plot_threads[:5] if item.get("title"))
    comment_block = "\n".join(f"- {item}" for item in related_comments[:4]) or "- 无"
    return (
        f"项目={story_bible.title}\n"
        f"体裁={story_bible.genre or '-'}\n"
        f"主题={story_bible.theme or '-'}\n"
        f"语气={story_bible.tone or '-'}\n"
        f"章节={getattr(chapter, 'chapter_number', '-')}"
        f" / {getattr(chapter, 'title', None) or '未命名章节'}\n"
        f"角色锚点={character_names or '-'}\n"
        f"剧情线={plot_threads or '-'}\n"
        f"风格指导={style_guidance}\n"
        f"重写目标={instruction.strip()}\n"
        f"选区前文={before_context or '-'}\n"
        f"待改写片段={original_text}\n"
        f"选区后文={after_context or '-'}\n"
        f"相关批注=\n{comment_block}\n"
        "要求：\n"
        "1. 只输出改写后的片段。\n"
        "2. 保持原有事实、视角、时态和事件顺序不乱。\n"
        "3. 与上下文自然衔接，不要改写选区外内容。\n"
        "4. 如果批注与指令冲突，优先满足指令并尽量兼容批注。\n"
    )


def _slice_selection(content: str, *, start: int, end: int) -> str:
    _validate_selection(content, start=start, end=end)
    return content[start:end]


def _replace_selection(
    content: str,
    *,
    start: int,
    end: int,
    replacement: str,
) -> str:
    _validate_selection(content, start=start, end=end)
    return f"{content[:start]}{replacement}{content[end:]}"


def _normalize_rewritten_text(text: str, original_text: str) -> str:
    candidate = (text or "").strip()
    if not candidate:
        return original_text

    if candidate.startswith("```"):
        lines = [line for line in candidate.splitlines() if not line.startswith("```")]
        candidate = "\n".join(lines).strip()

    for prefix in (
        "改写后：",
        "改写如下：",
        "重写后：",
        "重写片段：",
        "片段：",
        "输出：",
    ):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):].strip()

    if candidate.startswith(("“", "\"")) and candidate.endswith(("”", "\"")):
        candidate = candidate[1:-1].strip()

    return candidate or original_text


def _build_change_reason(instruction: str) -> str:
    compact_instruction = " ".join(instruction.strip().split())
    shortened = compact_instruction[:72]
    return f"Partial rewrite: {shortened}"


def _fallback_rewrite(
    *,
    original_text: str,
    instruction: str,
    style_guidance: str,
    related_comments: list[str],
) -> str:
    rewritten = original_text.strip()
    instruction_text = instruction.strip()
    if "简洁" in instruction_text:
        for filler in ("有些", "似乎", "仿佛", "其实", "开始", "然后"):
            rewritten = rewritten.replace(filler, "")
    if "张力" in instruction_text or "紧张" in instruction_text:
        rewritten = rewritten.replace("然后", "").replace("于是", "")
        if not rewritten.endswith(("。", "！", "？")):
            rewritten += "。"
        rewritten += "空气骤然绷紧，谁也不敢先动。"
    if "情绪" in instruction_text or "细腻" in instruction_text:
        rewritten += "那点迟疑没有说出口，只在呼吸里停了一瞬。"
    if "对话" in instruction_text and "“" not in rewritten:
        rewritten += "“先别急，”她压低声音说。"
    if related_comments:
        rewritten += f"她记起刚才最刺耳的那句提醒：{related_comments[0][:24]}。"
    if "sharp" in style_guidance or "冷峻锋利" in style_guidance:
        rewritten = rewritten.replace("非常", "").replace("十分", "")
    return rewritten or original_text


async def _load_overlapping_comments(
    session: AsyncSession,
    *,
    chapter_id: UUID,
    selection_start: int,
    selection_end: int,
) -> list[str]:
    result = await session.execute(
        select(ChapterComment)
        .where(
            ChapterComment.chapter_id == chapter_id,
            ChapterComment.status == "open",
        )
        .order_by(ChapterComment.created_at.desc())
    )
    comments = list(result.scalars().all())
    matched: list[str] = []
    for comment in comments:
        start = getattr(comment, "selection_start", None)
        end = getattr(comment, "selection_end", None)
        if start is None or end is None:
            continue
        if _ranges_overlap(
            selection_start,
            selection_end,
            int(start),
            int(end),
        ):
            body = str(getattr(comment, "body", "")).strip()
            if body:
                matched.append(body)
    return matched


def _ranges_overlap(
    left_start: int,
    left_end: int,
    right_start: int,
    right_end: int,
) -> bool:
    return left_start < right_end and right_start < left_end


def _validate_selection(content: str, *, start: int, end: int) -> None:
    if start < 0 or end <= start or end > len(content):
        raise AppError(
            code="chapter.selection_invalid",
            message="Selected range is invalid.",
            status_code=400,
        )
    if not content[start:end].strip():
        raise AppError(
            code="chapter.selection_empty",
            message="Selected text cannot be empty.",
            status_code=400,
        )
