from __future__ import annotations

from typing import Any, Optional
from uuid import UUID
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from services.story_engine_workflows.outline_stress import (
    run_outline_stress_test,
)
from services.story_engine_workflows.realtime_guard import (
    run_realtime_guard,
)
from services.story_engine_workflows.knowledge_guard import (
    run_story_knowledge_guard,
    run_story_bulk_import_guard,
    _STORY_KNOWLEDGE_SECTION_LABELS,
    _STORY_KNOWLEDGE_ID_FIELDS,
    _STORY_KNOWLEDGE_PRIMARY_LABEL_FIELDS,
    _serialize_story_api_entities,
    _read_story_knowledge_value,
    _read_story_knowledge_dict,
    _serialize_story_knowledge_item,
    _story_knowledge_json_snippet,
    _compact_prompt_text,
    _build_agent_report_prompt_snapshot,
    _truncate_deliberation_text,
    _format_deliberation_actor_label,
    _build_deliberation_entry_from_report,
    _normalize_story_knowledge_text,
    _get_story_knowledge_workspace_items,
    _resolve_story_knowledge_workspace_identity,
    _resolve_story_knowledge_item_label,
    _find_story_knowledge_item_in_workspace,
    _build_story_knowledge_issue,
    _build_story_knowledge_guard_fallback_issues,
    _build_story_knowledge_delete_guard_issues,
    _collect_story_knowledge_references,
    _build_story_knowledge_guard_context_text,
    _build_story_bulk_import_guard_fallback_issues,
    _build_story_bulk_import_guard_context_text,
    _build_story_bulk_import_payload_snapshot,
)
from services.story_engine_workflows.final_optimize import (
    run_final_optimize,
    list_story_engine_agent_specs,
    load_story_engine_workspace,
)

__all__ = [
    "run_outline_stress_test",
    "run_realtime_guard",
    "run_story_knowledge_guard",
    "run_story_bulk_import_guard",
    "run_chapter_stream_generate",
    "run_final_optimize",
    "list_story_engine_agent_specs",
    "load_story_engine_workspace",
]

_STORY_ENGINE_READ_SCHEMAS = {
    "characters": None,
    "foreshadows": None,
    "items": None,
    "world_rules": None,
    "timeline_events": None,
    "outlines": None,
}


async def run_chapter_stream_generate(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID] = None,
    chapter_id: Optional[UUID] = None,
    chapter_number: int,
    chapter_title: Optional[str],
    outline_id: Optional[UUID],
    current_outline: Optional[str],
    recent_chapters: list[str],
    existing_text: str,
    style_sample: Optional[str],
    target_word_count: int,
    target_paragraph_count: int,
    resume_from_paragraph: Optional[int] = None,
    repair_instruction: Optional[str] = None,
    rewrite_latest_paragraph: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    from services.story_engine_workflow_service_legacy import run_chapter_stream_generate as _legacy_run
    async for chunk in _legacy_run(
        session=session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
        chapter_id=chapter_id,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        outline_id=outline_id,
        current_outline=current_outline,
        recent_chapters=recent_chapters,
        existing_text=existing_text,
        style_sample=style_sample,
        target_word_count=target_word_count,
        target_paragraph_count=target_paragraph_count,
        resume_from_paragraph=resume_from_paragraph,
        repair_instruction=repair_instruction,
        rewrite_latest_paragraph=rewrite_latest_paragraph,
    ):
        yield chunk