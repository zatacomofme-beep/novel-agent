from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db_session, get_current_user
from schemas.preferences import StylePresetAssetCreate, StylePresetAssetRead
from services.style_analysis_service import (
    analyze_style_from_text,
    analyze_style_from_image,
    StyleAnalysisResult,
)
from services.preference_service import (
    create_style_preset_asset,
    get_user_creative_asset_library,
)
from models.user import User

router = APIRouter()


@dataclass
class StyleAnalysisResponse:
    writing_style: str
    tone_and_mood: str
    sentence_structure: str
    vocabulary_and_expression: str
    pacing_and_rhythm: str
    emotional_depth: str
    dialogue_style: str
    narrative_perspective: str
    tension_and_conflict: str
    genre_characteristics: str
    strengths: list[str]
    weaknesses: list[str]
    recommended_style_tags: list[str]

    @classmethod
    def from_result(cls, result: StyleAnalysisResult) -> "StyleAnalysisResponse":
        return cls(
            writing_style=result.writing_style,
            tone_and_mood=result.tone_and_mood,
            sentence_structure=result.sentence_structure,
            vocabulary_and_expression=result.vocabulary_and_expression,
            pacing_and_rhythm=result.pacing_and_rhythm,
            emotional_depth=result.emotional_depth,
            dialogue_style=result.dialogue_style,
            narrative_perspective=result.narrative_perspective,
            tension_and_conflict=result.tension_and_conflict,
            genre_characteristics=result.genre_characteristics,
            strengths=result.strengths,
            weaknesses=result.weaknesses,
            recommended_style_tags=result.recommended_style_tags,
        )


class SaveTemplateRequest(BaseModel):
    name: str
    style_data: StyleAnalysisResponse


@router.get("/analysis-result")
async def get_analysis_result_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "writing_style": {"type": "string", "description": "文风总体描述"},
            "tone_and_mood": {"type": "string", "description": "语气与情绪描述"},
            "sentence_structure": {"type": "string", "description": "句式结构分析"},
            "vocabulary_and_expression": {"type": "string", "description": "词汇与表达分析"},
            "pacing_and_rhythm": {"type": "string", "description": "节奏与韵律分析"},
            "emotional_depth": {"type": "string", "description": "情感深度分析"},
            "dialogue_style": {"type": "string", "description": "对话风格分析"},
            "narrative_perspective": {"type": "string", "description": "叙事视角分析"},
            "tension_and_conflict": {"type": "string", "description": "张力与冲突分析"},
            "genre_characteristics": {"type": "string", "description": "类型特征分析"},
            "strengths": {"type": "array", "items": {"type": "string"}, "description": "优点列表"},
            "weaknesses": {"type": "array", "items": {"type": "string"}, "description": "缺点列表"},
            "recommended_style_tags": {"type": "array", "items": {"type": "string"}, "description": "推荐风格标签"},
        },
    }


@router.post("/analyze-text")
async def analyze_text(
    text: str = Form(..., max_length=30000),
    current_user: User = Depends(get_current_user),
) -> StyleAnalysisResponse:
    if len(text.strip()) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "text_too_short", "message": "文本内容至少需要100个字"},
        )

    result = await analyze_style_from_text(text)
    return StyleAnalysisResponse.from_result(result)


@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> StyleAnalysisResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_file_type", "message": "只支持图片文件"},
        )

    import base64
    contents = await file.read()

    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "file_too_large", "message": "图片大小不能超过10MB"},
        )

    image_base64 = base64.b64encode(contents).decode()
    media_type = file.content_type or "image/jpeg"

    result = await analyze_style_from_image(image_base64, media_type)
    return StyleAnalysisResponse.from_result(result)


@router.post("/save-template", response_model=StylePresetAssetRead)
async def save_as_template(
    request: SaveTemplateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StylePresetAssetRead:
    template_data = StylePresetAssetCreate(
        title=request.name,
        tagline=", ".join(request.style_data.recommended_style_tags[:5]) if request.style_data.recommended_style_tags else None,
        description=request.style_data.writing_style,
        tags=request.style_data.recommended_style_tags,
        prose_style=_infer_prose_style(request.style_data.sentence_structure, request.style_data.vocabulary_and_expression),
        narrative_mode=_infer_narrative_mode(request.style_data.narrative_perspective),
        pacing_preference=_infer_pacing(request.style_data.pacing_and_rhythm),
        dialogue_preference=_infer_dialogue(request.style_data.dialogue_style),
        tension_preference=_infer_tension(request.style_data.tension_and_conflict),
        sensory_density=_infer_sensory(request.style_data.emotional_depth),
        favored_elements=request.style_data.strengths,
        banned_patterns=request.style_data.weaknesses,
        custom_style_notes=f"语气情绪: {request.style_data.tone_and_mood}\n类型特征: {request.style_data.genre_characteristics}",
    )

    return await create_style_preset_asset(session, user_id=current_user.id, payload=template_data)


def _infer_prose_style(sentence_structure: str, vocabulary: str) -> str:
    text = f"{sentence_structure} {vocabulary}".lower()
    if "短句" in text or "简洁" in text:
        return "简洁干脆"
    if "长句" in text or "华丽" in text:
        return "细腻华丽"
    return "均衡"


def _infer_narrative_mode(perspective: str) -> str:
    text = perspective.lower()
    if "第一人称" in text:
        return "first_person"
    if "第三人称" in text:
        return "third_person"
    if "全知" in text:
        return "omniscient"
    return "close_third"


def _infer_pacing(pacing: str) -> str:
    text = pacing.lower()
    if "快" in text:
        return "fast"
    if "慢" in text:
        return "slow"
    return "balanced"


def _infer_dialogue(dialogue: str) -> str:
    text = dialogue.lower()
    if "多" in text:
        return "high"
    if "少" in text:
        return "low"
    return "balanced"


def _infer_tension(tension: str) -> str:
    text = tension.lower()
    if "强" in text:
        return "high"
    if "弱" in text:
        return "low"
    return "balanced"


def _infer_sensory(emotional_depth: str) -> str:
    text = emotional_depth.lower()
    if "强" in text or "深" in text:
        return "intense"
    if "弱" in text or "淡" in text:
        return "subtle"
    return "focused"
