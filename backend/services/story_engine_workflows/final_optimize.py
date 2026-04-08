from __future__ import annotations

from typing import Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from services.story_engine_workflow_service_legacy import (
    run_final_optimize as _legacy_run_final_optimize,
    list_story_engine_agent_specs as _legacy_list_specs,
    load_story_engine_workspace as _legacy_load_workspace,
)


async def run_final_optimize(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID] = None,
    chapter_id: Optional[UUID] = None,
    chapter_number: int,
    chapter_title: Optional[str],
    draft_text: str,
    style_sample: Optional[str],
    workflow_id: str | None = None,
) -> dict[str, Any]:
    return await _legacy_run_final_optimize(
        session=session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
        chapter_id=chapter_id,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        draft_text=draft_text,
        style_sample=style_sample,
        workflow_id=workflow_id,
    )


def list_story_engine_agent_specs() -> list[dict[str, Any]]:
    return _legacy_list_specs()


async def load_story_engine_workspace(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID] = None,
) -> dict[str, Any]:
    return await _legacy_load_workspace(
        session=session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
    )