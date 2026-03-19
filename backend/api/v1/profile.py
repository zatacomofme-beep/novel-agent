from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from schemas.preferences import (
    StyleTemplateApplyRequest,
    StyleTemplateRead,
    UserPreferenceRead,
    UserPreferenceUpdate,
)
from services.preference_service import (
    apply_style_template,
    clear_active_style_template,
    get_preference_learning_snapshot,
    get_or_create_user_preference,
    list_style_templates,
    to_user_preference_read,
    update_user_preference,
)


router = APIRouter()


@router.get("/preferences", response_model=UserPreferenceRead)
async def preference_detail(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferenceRead:
    preference = await get_or_create_user_preference(session, current_user.id)
    learning_snapshot = await get_preference_learning_snapshot(session, current_user.id)
    return to_user_preference_read(preference, learning_snapshot)


@router.patch("/preferences", response_model=UserPreferenceRead)
async def preference_patch(
    payload: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferenceRead:
    preference = await get_or_create_user_preference(session, current_user.id)
    updated = await update_user_preference(session, preference, payload)
    learning_snapshot = await get_preference_learning_snapshot(session, current_user.id)
    return to_user_preference_read(updated, learning_snapshot)


@router.get("/style-templates", response_model=list[StyleTemplateRead])
async def style_template_list(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StyleTemplateRead]:
    preference = await get_or_create_user_preference(session, current_user.id)
    return list_style_templates(preference.active_template_key)


@router.post("/style-templates/{template_key}/apply", response_model=UserPreferenceRead)
async def style_template_apply(
    template_key: str,
    payload: StyleTemplateApplyRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferenceRead:
    preference = await get_or_create_user_preference(session, current_user.id)
    updated = await apply_style_template(
        session,
        preference,
        template_key,
        mode=payload.mode,
    )
    learning_snapshot = await get_preference_learning_snapshot(session, current_user.id)
    return to_user_preference_read(updated, learning_snapshot)


@router.delete("/style-templates/active", response_model=UserPreferenceRead)
async def style_template_clear_active(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferenceRead:
    preference = await get_or_create_user_preference(session, current_user.id)
    updated = await clear_active_style_template(session, preference)
    learning_snapshot = await get_preference_learning_snapshot(session, current_user.id)
    return to_user_preference_read(updated, learning_snapshot)
