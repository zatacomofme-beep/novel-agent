from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models.project import Project
from schemas.project import ProjectEntityGenerationDispatchRead


SUPPORTED_ENTITY_GENERATION_TYPES = frozenset(
    {
        "characters",
        "supporting",
        "items",
        "locations",
        "factions",
        "plot_threads",
    }
)


async def dispatch_project_entity_generation(
    session: AsyncSession,
    project: Project,
    *,
    actor_user_id: UUID,
    generation_type: str,
    payload: Any,
) -> ProjectEntityGenerationDispatchRead:
    if generation_type not in SUPPORTED_ENTITY_GENERATION_TYPES:
        raise AppError(
            code="project.entity_generation_type_unsupported",
            message="Unsupported entity generation type.",
            status_code=400,
        )

    from tasks.entity_generation import (
        dispatch_entity_generation_task,
        enqueue_entity_generation_task,
    )

    if hasattr(payload, "model_dump"):
        payload_data = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        payload_data = payload
    else:
        raise AppError(
            code="project.entity_generation_payload_invalid",
            message="Entity generation payload is invalid.",
            status_code=400,
        )

    task_state = await enqueue_entity_generation_task(
        str(project.id),
        str(actor_user_id),
        generation_type,
        payload_data,
    )
    task_state = await dispatch_entity_generation_task(
        task_id=task_state.task_id,
        project_id=str(project.id),
        user_id=str(actor_user_id),
        generation_type=generation_type,
    )
    return ProjectEntityGenerationDispatchRead(
        generation_type=generation_type,
        task_id=task_state.task_id,
        task_status=task_state.status,
        task=task_state,
    )
