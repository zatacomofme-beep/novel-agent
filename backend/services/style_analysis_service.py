from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from agents.model_gateway import GenerationRequest, GenerationResult, model_gateway
from core.config import get_settings


@dataclass
class StyleAnalysisResult:
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
    raw_json: str


SYSTEM_PROMPT = """你是一位专业的网文风格分析师。你的任务是对用户提供的文本样本进行深度风格分析，并输出一份结构化的风格特征报告。

分析维度：
1. 文风特征（句式、用词、修辞风格）
2. 语气与情绪（整体基调、情感色彩）
3. 句式结构（长短句比例、句型变化）
4. 词汇与表达（高频词汇类型、用语习惯）
5. 节奏与韵律（段落节奏、阅读体验）
6. 情感深度（情感表达方式、共鸣感）
7. 对话风格（对话比例、人物说话特点）
8. 叙事视角（人称、视角稳定性）
9. 张力与冲突（冲突构建方式、悬念设置）
10. 类型特征（所属网文类型的典型特征）

请严格按照以下JSON格式输出，不要添加任何额外解释：
{
    "writing_style": "文风总体描述",
    "tone_and_mood": "语气与情绪描述",
    "sentence_structure": "句式结构分析",
    "vocabulary_and_expression": "词汇与表达分析",
    "pacing_and_rhythm": "节奏与韵律分析",
    "emotional_depth": "情感深度分析",
    "dialogue_style": "对话风格分析",
    "narrative_perspective": "叙事视角分析",
    "tension_and_conflict": "张力与冲突分析",
    "genre_characteristics": "类型特征分析",
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["缺点1", "缺点2"],
    "recommended_style_tags": ["标签1", "标签2", "标签3"]
}"""

TEXT_ANALYSIS_PROMPT = """请分析以下文本样本的风格特征：

{text_content}

注意：只输出JSON，不要添加任何解释或前缀。"""

IMAGE_ANALYSIS_PROMPT = """请分析这张图片中的文本风格特征。如果图片中包含小说/文章内容，请直接分析；如果包含其他内容（如截图、表格等），请描述你看到的内容并尝试提取文字进行分析。

注意：只输出JSON，不要添加任何解释或前缀。"""


async def analyze_style_from_text(
    text: str,
    model: Optional[str] = None,
) -> StyleAnalysisResult:
    settings = get_settings()
    target_model = model or "gemini-3.1-pro-preview"

    request = GenerationRequest(
        task_name="style_analysis_text",
        prompt=TEXT_ANALYSIS_PROMPT.format(text_content=text[:15000]),
        system_prompt=SYSTEM_PROMPT,
        model=target_model,
        temperature=0.3,
        max_tokens=4000,
    )

    def fallback() -> str:
        return json.dumps({
            "writing_style": "本地Fallback模式，无法进行真实分析",
            "tone_and_mood": "N/A",
            "sentence_structure": "N/A",
            "vocabulary_and_expression": "N/A",
            "pacing_and_rhythm": "N/A",
            "emotional_depth": "N/A",
            "dialogue_style": "N/A",
            "narrative_perspective": "N/A",
            "tension_and_conflict": "N/A",
            "genre_characteristics": "N/A",
            "strengths": [],
            "weaknesses": ["服务暂不可用"],
            "recommended_style_tags": [],
        })

    result = await model_gateway.generate_text(request, fallback=fallback)
    return _parse_analysis_result(result.content, result)


async def analyze_style_from_image(
    image_base64: str,
    media_type: str = "image/jpeg",
    model: Optional[str] = None,
) -> StyleAnalysisResult:
    target_model = model or "gemini-3.1-pro-preview"

    request = GenerationRequest(
        task_name="style_analysis_image",
        prompt=IMAGE_ANALYSIS_PROMPT,
        system_prompt=SYSTEM_PROMPT,
        model=target_model,
        temperature=0.3,
        max_tokens=4000,
        image_base64=image_base64,
        image_media_type=media_type,
    )

    def fallback() -> str:
        return json.dumps({
            "writing_style": "本地Fallback模式，无法进行真实分析",
            "tone_and_mood": "N/A",
            "sentence_structure": "N/A",
            "vocabulary_and_expression": "N/A",
            "pacing_and_rhythm": "N/A",
            "emotional_depth": "N/A",
            "dialogue_style": "N/A",
            "narrative_perspective": "N/A",
            "tension_and_conflict": "N/A",
            "genre_characteristics": "N/A",
            "strengths": [],
            "weaknesses": ["服务暂不可用"],
            "recommended_style_tags": [],
        })

    result = await model_gateway.generate_text(request, fallback=fallback)
    return _parse_analysis_result(result.content, result)


def _parse_analysis_result(content: str, result: GenerationResult) -> StyleAnalysisResult:
    try:
        content_clean = content.strip()
        if content_clean.startswith("```json"):
            content_clean = content_clean[7:]
        if content_clean.startswith("```"):
            content_clean = content_clean[3:]
        if content_clean.endswith("```"):
            content_clean = content_clean[:-3]
        content_clean = content_clean.strip()

        data = json.loads(content_clean)
        return StyleAnalysisResult(
            writing_style=data.get("writing_style", ""),
            tone_and_mood=data.get("tone_and_mood", ""),
            sentence_structure=data.get("sentence_structure", ""),
            vocabulary_and_expression=data.get("vocabulary_and_expression", ""),
            pacing_and_rhythm=data.get("pacing_and_rhythm", ""),
            emotional_depth=data.get("emotional_depth", ""),
            dialogue_style=data.get("dialogue_style", ""),
            narrative_perspective=data.get("narrative_perspective", ""),
            tension_and_conflict=data.get("tension_and_conflict", ""),
            genre_characteristics=data.get("genre_characteristics", ""),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            recommended_style_tags=data.get("recommended_style_tags", []),
            raw_json=content_clean,
        )
    except json.JSONDecodeError:
        return StyleAnalysisResult(
            writing_style="解析失败",
            tone_and_mood="",
            sentence_structure="",
            vocabulary_and_expression="",
            pacing_and_rhythm="",
            emotional_depth="",
            dialogue_style="",
            narrative_perspective="",
            tension_and_conflict="",
            genre_characteristics="",
            strengths=[],
            weaknesses=["JSON解析失败，请检查模型输出格式"],
            recommended_style_tags=[],
            raw_json=content,
        )
