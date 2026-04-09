"""
Unified facade for Story Engine workflow operations.

This module serves as the public API entry point for all Story Engine workflows.
The actual implementations are delegated to:

- ``story_engine_workflows.outline_stress``   — outline stress testing
- ``story_engine_workflows.realtime_guard``    — real-time draft guarding
- ``story_engine_workflows.knowledge_guard``   — story bible change guarding
- ``story_engine_workflows.final_optimize``    — final chapter optimization
- ``story_engine_workflow_service_legacy``     — chapter stream generation
  (not yet migrated to the new workflow sub-package)
"""

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
