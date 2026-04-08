from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from schemas.project import (
    CharacterGenerationRequest,
    CharacterGenerationResponse,
    FactionGenerationRequest,
    FactionGenerationResponse,
    ItemGenerationRequest,
    ItemGenerationResponse,
    LocationGenerationRequest,
    LocationGenerationResponse,
    PlotThreadGenerationRequest,
    PlotThreadGenerationResponse,
    ProjectEntityGenerationDispatchRead,
)
from services.entity_generation_service import (
    generate_characters as generate_character_candidates,
    generate_factions as generate_faction_candidates,
    generate_items as generate_item_candidates,
    generate_locations as generate_location_candidates,
    generate_plot_threads as generate_plot_thread_candidates,
)
from services.project_entity_generation_service import dispatch_project_entity_generation
from services.project_service import get_owned_project, PROJECT_PERMISSION_EDIT


router = APIRouter(tags=["projects-generation"])


def _as_supporting_character_payload(
    payload: CharacterGenerationRequest,
) -> CharacterGenerationRequest:
    return payload.model_copy(update={"character_type": "supporting"})


@router.post(
    "/{project_id}/generations/characters",
    response_model=CharacterGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_characters(
    project_id: UUID,
    payload: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CharacterGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_character_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/supporting",
    response_model=CharacterGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_supporting_characters(
    project_id: UUID,
    payload: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CharacterGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_character_candidates(
        session,
        project_id,
        current_user.id,
        _as_supporting_character_payload(payload),
    )


@router.post(
    "/{project_id}/generations/characters/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_character_generation(
    project_id: UUID,
    payload: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="characters",
        payload=payload,
    )


@router.post(
    "/{project_id}/generations/supporting/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_supporting_generation(
    project_id: UUID,
    payload: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="supporting",
        payload=_as_supporting_character_payload(payload),
    )


@router.post(
    "/{project_id}/generations/items",
    response_model=ItemGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_items(
    project_id: UUID,
    payload: ItemGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ItemGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_item_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/items/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_item_generation(
    project_id: UUID,
    payload: ItemGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="items",
        payload=payload,
    )


@router.post(
    "/{project_id}/generations/locations",
    response_model=LocationGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_locations(
    project_id: UUID,
    payload: LocationGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LocationGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_location_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/locations/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_location_generation(
    project_id: UUID,
    payload: LocationGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="locations",
        payload=payload,
    )


@router.post(
    "/{project_id}/generations/factions",
    response_model=FactionGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_factions(
    project_id: UUID,
    payload: FactionGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FactionGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_faction_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/factions/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_faction_generation(
    project_id: UUID,
    payload: FactionGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="factions",
        payload=payload,
    )


@router.post(
    "/{project_id}/generations/plot-threads",
    response_model=PlotThreadGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_plot_threads(
    project_id: UUID,
    payload: PlotThreadGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PlotThreadGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_plot_thread_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/plot-threads/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_plot_thread_generation(
    project_id: UUID,
    payload: PlotThreadGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="plot_threads",
        payload=payload,
    )
