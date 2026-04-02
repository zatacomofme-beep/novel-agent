from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.profile import get_db_session, get_current_user
from schemas.prompt_template import (
    PromptTemplateRead,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateListResponse,
    PromptTemplateApplyRequest,
    PromptTemplateApplyResponse,
    PromptTemplateRecommendRequest,
    PromptTemplateRecommendResponse,
)
from services.prompt_template_service import PromptTemplateService
from models.user import User

router = APIRouter()


@router.get("", response_model=PromptTemplateListResponse)
async def list_prompt_templates(
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    tags: Optional[str] = Query(default=None),
    difficulty: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    tag_list = tags.split(",") if tags else None
    service = PromptTemplateService()
    templates, total, categories = await service.list_templates(
        session=session,
        category=category,
        search=search,
        tags=tag_list,
        difficulty=difficulty,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return PromptTemplateListResponse(
        templates=[PromptTemplateRead.model_validate(t) for t in templates],
        total=total,
        categories=categories,
    )


@router.get("/categories", response_model=list[str])
async def list_categories():
    return PromptTemplateService.CATEGORIES


@router.get("/{template_id}", response_model=PromptTemplateRead)
async def get_prompt_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = PromptTemplateService()
    template = await service.get_template(session, template_id)
    if not template:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Template not found")
    return PromptTemplateRead.model_validate(template)


@router.post("", response_model=PromptTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_prompt_template(
    data: PromptTemplateCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = PromptTemplateService()
    template = await service.create_template(
        session, data.model_dump(), current_user.id
    )
    return PromptTemplateRead.model_validate(template)


@router.post("/{template_id}/use", status_code=status.HTTP_204_NO_CONTENT)
async def use_prompt_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = PromptTemplateService()
    await service.increment_use_count(session, template_id)


@router.post("/{template_id}/apply", response_model=PromptTemplateApplyResponse)
async def apply_prompt_template(
    template_id: UUID,
    request: PromptTemplateApplyRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """应用模板到指定章节，自动填充变量"""
    from fastapi import HTTPException
    from services.prompt_template_service import PromptTemplateService
    
    service = PromptTemplateService()
    template = await service.get_template(session, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 填充变量
    content = template.content
    for var in template.variables:
        var_value = request.variables.get(var.name, f"[{var.name}]")
        content = content.replace(f"{{{var.name}}}", var_value)
    
    # 递增使用次数
    await service.increment_use_count(session, template_id)
    
    return PromptTemplateApplyResponse(
        success=True,
        content=content,
        chapter_id=request.chapter_id,
        message="模板已应用，请根据需要调整内容"
    )


@router.post("/recommend", response_model=PromptTemplateRecommendResponse)
async def recommend_prompt_templates(
    request: PromptTemplateRecommendRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """智能推荐模板 - 根据章节内容、项目类型等信息推荐相关模板"""
    from services.prompt_template_service import PromptTemplateService
    
    service = PromptTemplateService()
    
    # 基于章节内容、项目信息等推荐模板
    templates = await service.recommend_templates(
        session=session,
        project_id=request.project_id,
        chapter_id=request.chapter_id,
        chapter_content=request.chapter_content,
        context=request.context,
        user_id=current_user.id,
    )
    
    # 生成推荐理由
    reason = None
    if templates:
        categories = list(set(t.category for t in templates[:3]))
        reason = f"根据您的创作进度和当前章节内容，为您推荐 {len(templates)} 个相关模板，主要涉及：{', '.join(categories)}"
    
    return PromptTemplateRecommendResponse(
        templates=[PromptTemplateRead.model_validate(t) for t in templates],
        reason=reason,
    )
