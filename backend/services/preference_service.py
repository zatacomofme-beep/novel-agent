from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models.preference_observation import PreferenceObservation
from models.user_preference import UserPreference
from schemas.preferences import (
    ActiveStyleTemplateRead,
    PreferenceLearningSignal,
    PreferenceLearningSnapshot,
    StyleTemplateRead,
    UserPreferenceRead,
    UserPreferenceUpdate,
)


DEFAULT_PREFERENCE_VALUES: dict[str, Any] = {
    "active_template_key": None,
    "prose_style": "precise",
    "narrative_mode": "close_third",
    "pacing_preference": "balanced",
    "dialogue_preference": "balanced",
    "tension_preference": "balanced",
    "sensory_density": "focused",
    "favored_elements": [],
    "banned_patterns": [],
    "custom_style_notes": None,
}

STYLE_OPTION_LABELS = {
    "prose_style": {
        "precise": "精确克制",
        "lyrical": "抒情流动",
        "sharp": "冷峻锋利",
    },
    "narrative_mode": {
        "close_third": "贴身第三人称",
        "omniscient": "多点俯瞰",
        "first_person": "第一人称",
    },
    "pacing_preference": {
        "fast": "快推进",
        "balanced": "均衡推进",
        "slow_burn": "慢燃积压",
    },
    "dialogue_preference": {
        "dialogue_forward": "对话驱动",
        "balanced": "对话叙述平衡",
        "narration_heavy": "叙述主导",
    },
    "tension_preference": {
        "restrained": "克制蓄压",
        "balanced": "张弛平衡",
        "high_tension": "高压逼近",
    },
    "sensory_density": {
        "minimal": "稀疏点染",
        "focused": "重点感官锚点",
        "immersive": "沉浸式细节",
    },
}

FIELD_LABELS = {
    "prose_style": "文风",
    "narrative_mode": "叙事视角",
    "pacing_preference": "节奏",
    "dialogue_preference": "对话比例",
    "tension_preference": "张力",
    "sensory_density": "感官密度",
}

STYLE_TEMPLATE_APPLY_MODES = ("replace", "fill_defaults")

STYLE_TEMPLATES: dict[str, dict[str, Any]] = {
    "cold_thriller": {
        "name": "冷锋追缉",
        "tagline": "短句推进，压迫感优先。",
        "description": "适合悬疑、犯罪、追逃或高压潜入叙事，强调动作链和信息控制。",
        "category": "悬疑 / 追缉",
        "recommended_for": ["悬疑", "犯罪", "谍战"],
        "preferences": {
            "prose_style": "sharp",
            "narrative_mode": "close_third",
            "pacing_preference": "fast",
            "dialogue_preference": "balanced",
            "tension_preference": "high_tension",
            "sensory_density": "focused",
            "favored_elements": ["动作链", "环境压迫", "潜台词"],
            "banned_patterns": ["总结式结尾", "解释性说教"],
            "custom_style_notes": "信息只给一半，悬念靠动作与环境压力推进。",
        },
    },
    "lyrical_romance": {
        "name": "潮汐情书",
        "tagline": "抒情流动，情绪缓慢升温。",
        "description": "适合言情、都市关系或带诗性氛围的成长叙事，强调情绪涌动和感官细节。",
        "category": "情感 / 抒情",
        "recommended_for": ["言情", "都市", "成长"],
        "preferences": {
            "prose_style": "lyrical",
            "narrative_mode": "first_person",
            "pacing_preference": "slow_burn",
            "dialogue_preference": "balanced",
            "tension_preference": "restrained",
            "sensory_density": "immersive",
            "favored_elements": ["身体反应", "感官锚点", "潜台词"],
            "banned_patterns": ["硬转折", "直白说教"],
            "custom_style_notes": "情绪不要一次说透，让触感、停顿和视线交换承担含义。",
        },
    },
    "epic_chronicle": {
        "name": "群像史诗",
        "tagline": "多线并进，格局与事件同样重要。",
        "description": "适合奇幻、历史、群像长篇或卷本叙事，强调世界规模、线索推进与多视角统筹。",
        "category": "史诗 / 群像",
        "recommended_for": ["奇幻", "历史", "群像"],
        "preferences": {
            "prose_style": "precise",
            "narrative_mode": "omniscient",
            "pacing_preference": "balanced",
            "dialogue_preference": "narration_heavy",
            "tension_preference": "balanced",
            "sensory_density": "focused",
            "favored_elements": ["世界细节", "多线并进", "伏笔回响"],
            "banned_patterns": ["单点情绪泛滥", "机械重复说明"],
            "custom_style_notes": "保持大局清晰，每章推进局部冲突，同时给出更大的版图回声。",
        },
    },
    "intimate_psychology": {
        "name": "贴身心理刀锋",
        "tagline": "近距离内心审视，裂痕感强。",
        "description": "适合心理悬疑、人物成长或关系解剖，强调自我感知、压抑和逐层暴露。",
        "category": "心理 / 人物",
        "recommended_for": ["心理", "成长", "关系"],
        "preferences": {
            "prose_style": "precise",
            "narrative_mode": "close_third",
            "pacing_preference": "slow_burn",
            "dialogue_preference": "narration_heavy",
            "tension_preference": "balanced",
            "sensory_density": "immersive",
            "favored_elements": ["内心独白", "身体反应", "潜台词"],
            "banned_patterns": ["外放式喊口号", "总结人物动机"],
            "custom_style_notes": "人物变化要从微小失衡里长出来，不要用旁白替角色解释自己。",
        },
    },
    "dialogue_mystery": {
        "name": "对白迷局",
        "tagline": "靠对话拆线索，语言本身带刀。",
        "description": "适合本格推理、室内博弈或群体对话戏，强调对白控制、错位信息和潜台词。",
        "category": "推理 / 对话",
        "recommended_for": ["推理", "本格", "群戏"],
        "preferences": {
            "prose_style": "sharp",
            "narrative_mode": "close_third",
            "pacing_preference": "balanced",
            "dialogue_preference": "dialogue_forward",
            "tension_preference": "high_tension",
            "sensory_density": "minimal",
            "favored_elements": ["对话推进", "潜台词", "错位信息"],
            "banned_patterns": ["长段旁白解释", "直接公布谜底"],
            "custom_style_notes": "让对白承担攻防，不要急着替读者解释谁在撒谎。",
        },
    },
}

CONFIGURABLE_FIELDS = (
    "prose_style",
    "narrative_mode",
    "pacing_preference",
    "dialogue_preference",
    "tension_preference",
    "sensory_density",
    "favored_elements",
    "banned_patterns",
    "custom_style_notes",
)

OBSERVABLE_STYLE_FIELDS = (
    "prose_style",
    "narrative_mode",
    "pacing_preference",
    "dialogue_preference",
    "tension_preference",
    "sensory_density",
)

OBSERVATION_SOURCE_WEIGHTS = {
    "chapter_create": 0.8,
    "manual_update": 1.0,
    "rollback": 1.15,
}

MIN_OBSERVATION_CHARACTERS = 120
MIN_MANUAL_CHANGE_RATIO = 0.08
MAX_OBSERVATION_SNAPSHOT = 12

FIRST_PERSON_MARKERS = ("我", "我们", "咱", "I ", " my ", " me ")
THIRD_PERSON_MARKERS = ("他", "她", "他们", "她们", "He ", "She ", " they ")
OMNISCIENT_MARKERS = (
    "与此同时",
    "另一边",
    "无人知道",
    "所有人都",
    "整个城市",
    "城里",
    "Everyone",
)
SENSORY_MARKERS = (
    "看",
    "听",
    "闻",
    "触",
    "冷",
    "热",
    "潮",
    "痛",
    "亮",
    "暗",
    "味",
    "气息",
    "呼吸",
    "心跳",
    "光",
    "shadow",
    "smell",
    "taste",
    "sound",
)
ACTION_MARKERS = (
    "冲",
    "跑",
    "抓",
    "推",
    "拉",
    "撞",
    "躲",
    "追",
    "拔",
    "挥",
    "转身",
    "闯",
    "rush",
    "run",
    "grab",
    "turn",
)
TENSION_MARKERS = (
    "骤然",
    "猛地",
    "压住",
    "危险",
    "失控",
    "颤",
    "枪",
    "血",
    "窒息",
    "逼近",
    "刺痛",
    "panic",
    "blood",
    "danger",
)
INTERNALITY_MARKERS = (
    "想",
    "记得",
    "意识到",
    "忽然明白",
    "心里",
    "觉得",
    "怀疑",
    "知道",
    "remembered",
    "thought",
    "realized",
)
ENVIRONMENT_MARKERS = (
    "风",
    "雨",
    "雾",
    "夜",
    "墙",
    "街",
    "灯",
    "潮气",
    "空气",
    "门",
    "窗",
    "sea",
    "street",
    "room",
)
BODY_MARKERS = (
    "手指",
    "喉咙",
    "肩",
    "背",
    "额头",
    "指尖",
    "掌心",
    "脊背",
    "body",
    "breath",
    "skin",
)
SUBTEXT_MARKERS = (
    "沉默",
    "顿了顿",
    "没说",
    "欲言又止",
    "只是看着",
    "停了一秒",
    "silence",
    "paused",
)


async def get_or_create_user_preference(
    session: AsyncSession,
    user_id: UUID,
) -> UserPreference:
    result = await session.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    preference = result.scalar_one_or_none()
    if preference is not None:
        return preference

    preference = UserPreference(user_id=user_id, **DEFAULT_PREFERENCE_VALUES)
    session.add(preference)
    await session.commit()
    await session.refresh(preference)
    return preference


async def update_user_preference(
    session: AsyncSession,
    preference: UserPreference,
    payload: UserPreferenceUpdate,
) -> UserPreference:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(preference, field, value)
    await session.commit()
    await session.refresh(preference)
    return preference


async def record_preference_observation(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: Optional[UUID],
    chapter_id: Optional[UUID],
    source_type: str,
    content: str,
    change_reason: Optional[str] = None,
    previous_content: Optional[str] = None,
) -> Optional[PreferenceObservation]:
    normalized_content = (content or "").strip()
    if _visible_character_count(normalized_content) < MIN_OBSERVATION_CHARACTERS:
        return None

    change_ratio = _content_change_ratio(previous_content, normalized_content)
    if (
        source_type == "manual_update"
        and previous_content is not None
        and change_ratio < MIN_MANUAL_CHANGE_RATIO
    ):
        return None

    inferred = infer_preference_observation(normalized_content)
    observed_preferences = inferred["observed_preferences"]
    favored_elements = inferred["favored_elements"]
    content_metrics = dict(inferred["content_metrics"])
    content_metrics["change_ratio"] = change_ratio

    if not observed_preferences and not favored_elements:
        return None

    observation = PreferenceObservation(
        user_id=user_id,
        project_id=project_id,
        chapter_id=chapter_id,
        source_type=source_type,
        change_reason=change_reason,
        observed_preferences=observed_preferences,
        favored_elements=favored_elements,
        content_metrics=content_metrics,
        confidence_score=_mean(
            [
                float(item.get("confidence", 0))
                for item in observed_preferences.values()
                if isinstance(item, dict)
            ]
        ),
    )
    session.add(observation)
    await session.commit()
    await session.refresh(observation)
    return observation


async def get_preference_learning_snapshot(
    session: AsyncSession,
    user_id: UUID,
) -> PreferenceLearningSnapshot:
    result = await session.execute(
        select(PreferenceObservation)
        .where(PreferenceObservation.user_id == user_id)
        .order_by(PreferenceObservation.created_at.desc())
        .limit(MAX_OBSERVATION_SNAPSHOT)
    )
    observations = list(result.scalars().all())
    return build_preference_learning_snapshot(observations)


def list_style_templates(
    active_template_key: Optional[str] = None,
) -> list[StyleTemplateRead]:
    return [
        _to_style_template_read(key, template, active_template_key == key)
        for key, template in STYLE_TEMPLATES.items()
    ]


def get_active_style_template(
    preference_like: Any,
) -> Optional[ActiveStyleTemplateRead]:
    template_key = _get_value(preference_like, "active_template_key", None)
    if not template_key:
        return None
    template = STYLE_TEMPLATES.get(str(template_key))
    if template is None:
        return None
    return ActiveStyleTemplateRead(
        key=str(template_key),
        name=str(template["name"]),
        tagline=str(template["tagline"]),
    )


def apply_style_template_values(
    preference_like: Any,
    template_key: str,
    *,
    mode: str = "replace",
) -> dict[str, Any]:
    template = _get_style_template_definition(template_key)
    if mode not in STYLE_TEMPLATE_APPLY_MODES:
        raise AppError(
            code="preference.template_mode_invalid",
            message="Unsupported template apply mode.",
            status_code=400,
            metadata={"mode": mode},
        )

    current_payload = serialize_user_preference(preference_like)
    updated_payload = dict(current_payload)
    for field, template_value in template["preferences"].items():
        if mode == "replace" or _should_fill_template_default(
            field,
            current_payload.get(field),
        ):
            updated_payload[field] = _clone_template_value(template_value)

    updated_payload["active_template_key"] = template_key
    return updated_payload


async def apply_style_template(
    session: AsyncSession,
    preference: UserPreference,
    template_key: str,
    *,
    mode: str = "replace",
) -> UserPreference:
    updated_payload = apply_style_template_values(
        preference,
        template_key,
        mode=mode,
    )
    for field, value in updated_payload.items():
        setattr(preference, field, value)
    await session.commit()
    await session.refresh(preference)
    return preference


async def clear_active_style_template(
    session: AsyncSession,
    preference: UserPreference,
) -> UserPreference:
    preference.active_template_key = None
    await session.commit()
    await session.refresh(preference)
    return preference


def serialize_user_preference(preference_like: Any) -> dict[str, Any]:
    return {
        key: _get_value(preference_like, key, default)
        for key, default in DEFAULT_PREFERENCE_VALUES.items()
    }


def calculate_preference_completion(preference_like: Any) -> float:
    configured = 0
    for field in CONFIGURABLE_FIELDS:
        value = _get_value(preference_like, field, DEFAULT_PREFERENCE_VALUES.get(field))
        default = DEFAULT_PREFERENCE_VALUES.get(field)
        if isinstance(value, list):
            if value:
                configured += 1
        elif field == "custom_style_notes":
            if isinstance(value, str) and value.strip():
                configured += 1
        elif value != default:
            configured += 1
    return round(configured / len(CONFIGURABLE_FIELDS), 2)


def build_style_guidance(
    preference_like: Any,
    learning_snapshot: Optional[PreferenceLearningSnapshot] = None,
) -> str:
    payload = serialize_user_preference(preference_like)
    segments = [
        f"文风={_option_label('prose_style', payload['prose_style'])}",
        f"叙事视角={_option_label('narrative_mode', payload['narrative_mode'])}",
        f"节奏={_option_label('pacing_preference', payload['pacing_preference'])}",
        f"对话比例={_option_label('dialogue_preference', payload['dialogue_preference'])}",
        f"张力={_option_label('tension_preference', payload['tension_preference'])}",
        f"感官密度={_option_label('sensory_density', payload['sensory_density'])}",
    ]

    guidance = ""
    active_template = get_active_style_template(preference_like)
    if active_template is not None:
        guidance += f"当前风格模板={active_template.name}。"
    guidance += "风格偏好：" + "；".join(segments) + "。"
    favored_elements = payload.get("favored_elements") or []
    banned_patterns = payload.get("banned_patterns") or []
    custom_style_notes = payload.get("custom_style_notes")

    if favored_elements:
        guidance += f"优先保留这些元素：{', '.join(favored_elements[:4])}。"
    if banned_patterns:
        guidance += f"尽量避免这些表达或套路：{', '.join(banned_patterns[:4])}。"
    if isinstance(custom_style_notes, str) and custom_style_notes.strip():
        guidance += f"额外说明：{custom_style_notes.strip()}。"
    if (
        learning_snapshot is not None
        and learning_snapshot.observation_count > 0
        and learning_snapshot.summary
    ):
        guidance += f"隐式学习信号：{learning_snapshot.summary}"
    return guidance


def resolve_generation_preference_payload(
    preference_like: Any,
    learning_snapshot: Optional[PreferenceLearningSnapshot] = None,
) -> dict[str, Any]:
    payload = serialize_user_preference(preference_like)
    if learning_snapshot is None or learning_snapshot.observation_count < 2:
        return payload

    stable_map = {
        signal.field: signal
        for signal in learning_snapshot.stable_preferences
        if signal.confidence >= 0.72 and signal.source_count >= 2
    }
    for field in OBSERVABLE_STYLE_FIELDS:
        signal = stable_map.get(field)
        if signal is None:
            continue
        if payload.get(field) == DEFAULT_PREFERENCE_VALUES.get(field):
            payload[field] = signal.value

    if not payload["favored_elements"] and learning_snapshot.favored_elements:
        payload["favored_elements"] = list(learning_snapshot.favored_elements[:4])
    return payload


def to_user_preference_read(
    preference: UserPreference,
    learning_snapshot: Optional[PreferenceLearningSnapshot] = None,
) -> UserPreferenceRead:
    snapshot = learning_snapshot or empty_preference_learning_snapshot()
    payload = serialize_user_preference(preference)
    return UserPreferenceRead(
        id=preference.id,
        user_id=preference.user_id,
        updated_at=preference.updated_at,
        completion_score=calculate_preference_completion(preference),
        learning_snapshot=snapshot,
        active_template=get_active_style_template(preference),
        **payload,
    )


def empty_preference_learning_snapshot() -> PreferenceLearningSnapshot:
    return PreferenceLearningSnapshot(
        observation_count=0,
        last_observed_at=None,
        source_breakdown={},
        stable_preferences=[],
        favored_elements=[],
        summary=None,
    )


def build_preference_learning_snapshot(
    observations: list[Any],
) -> PreferenceLearningSnapshot:
    if not observations:
        return empty_preference_learning_snapshot()

    field_weights: dict[str, Counter[str]] = {
        field: Counter() for field in OBSERVABLE_STYLE_FIELDS
    }
    field_support_counts: Counter[tuple[str, str]] = Counter()
    favored_elements: Counter[str] = Counter()
    source_breakdown: Counter[str] = Counter()
    last_observed_at = None

    for observation in observations:
        source_type = str(_get_value(observation, "source_type", "manual_update"))
        source_breakdown[source_type] += 1
        last_observed_at = _newer_datetime(
            last_observed_at,
            _get_value(observation, "created_at", None),
        )
        source_weight = OBSERVATION_SOURCE_WEIGHTS.get(source_type, 1.0)
        observed_preferences = _get_value(observation, "observed_preferences", {}) or {}

        for field in OBSERVABLE_STYLE_FIELDS:
            item = observed_preferences.get(field)
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            confidence = float(item.get("confidence", 0) or 0)
            if not value or confidence <= 0:
                continue

            field_weights[field][str(value)] += round(confidence * source_weight, 4)
            if confidence >= 0.55:
                field_support_counts[(field, str(value))] += 1

        for element in _get_value(observation, "favored_elements", []) or []:
            favored_elements[str(element)] += source_weight

    minimum_sources = 1 if len(observations) == 1 else 2
    stable_preferences: list[PreferenceLearningSignal] = []
    for field, value_weights in field_weights.items():
        if not value_weights:
            continue

        best_value, best_weight = value_weights.most_common(1)[0]
        total_weight = float(sum(value_weights.values()))
        confidence = round(best_weight / total_weight, 2) if total_weight else 0.0
        source_count = int(field_support_counts[(field, best_value)])

        if source_count < minimum_sources or confidence < 0.58:
            continue

        stable_preferences.append(
            PreferenceLearningSignal(
                field=field,
                value=best_value,
                confidence=confidence,
                source_count=source_count,
            )
        )

    stable_preferences.sort(
        key=lambda item: (item.confidence, item.source_count),
        reverse=True,
    )
    favored_element_list = [
        value
        for value, weight in favored_elements.most_common(4)
        if weight >= (1.0 if len(observations) == 1 else 1.5)
    ]

    snapshot = PreferenceLearningSnapshot(
        observation_count=len(observations),
        last_observed_at=last_observed_at,
        source_breakdown=dict(source_breakdown),
        stable_preferences=stable_preferences,
        favored_elements=favored_element_list,
        summary=_build_learning_summary(
            observation_count=len(observations),
            stable_preferences=stable_preferences,
            favored_elements=favored_element_list,
        ),
    )
    return snapshot


def infer_preference_observation(content: str) -> dict[str, Any]:
    metrics = _extract_content_metrics(content)
    observed_preferences = {
        "narrative_mode": _infer_narrative_mode(metrics),
        "dialogue_preference": _infer_dialogue_preference(metrics),
        "sensory_density": _infer_sensory_density(metrics),
        "tension_preference": _infer_tension_preference(metrics),
        "pacing_preference": _infer_pacing_preference(metrics),
        "prose_style": _infer_prose_style(metrics),
    }
    favored_elements = _infer_favored_elements(metrics)
    return {
        "observed_preferences": {
            field: value
            for field, value in observed_preferences.items()
            if value is not None
        },
        "favored_elements": favored_elements,
        "content_metrics": metrics,
    }


def _extract_content_metrics(content: str) -> dict[str, Any]:
    paragraphs = [item for item in _split_paragraphs(content) if item]
    sentences = [item for item in _split_sentences(content) if item]
    char_count = _visible_character_count(content)
    paragraph_count = len(paragraphs)
    sentence_count = len(sentences)

    dialogue_chars = _estimate_dialogue_chars(paragraphs)
    sensory_hits = _count_markers(content, SENSORY_MARKERS)
    action_hits = _count_markers(content, ACTION_MARKERS)
    tension_hits = _count_markers(content, TENSION_MARKERS)
    first_person_hits = _count_markers(content, FIRST_PERSON_MARKERS)
    third_person_hits = _count_markers(content, THIRD_PERSON_MARKERS)
    omniscient_hits = _count_markers(content, OMNISCIENT_MARKERS)
    internality_hits = _count_markers(content, INTERNALITY_MARKERS)
    environment_hits = _count_markers(content, ENVIRONMENT_MARKERS)
    body_hits = _count_markers(content, BODY_MARKERS)
    subtext_hits = _count_markers(content, SUBTEXT_MARKERS)

    avg_sentence_chars = round(char_count / max(sentence_count, 1), 2)
    avg_paragraph_chars = round(char_count / max(paragraph_count, 1), 2)
    dialogue_ratio = round(dialogue_chars / max(char_count, 1), 4)
    sensory_ratio = round(sensory_hits / max(sentence_count, 1), 4)
    tension_ratio = round(tension_hits / max(sentence_count, 1), 4)
    action_ratio = round(action_hits / max(sentence_count, 1), 4)

    return {
        "character_count": char_count,
        "paragraph_count": paragraph_count,
        "sentence_count": sentence_count,
        "avg_sentence_chars": avg_sentence_chars,
        "avg_paragraph_chars": avg_paragraph_chars,
        "dialogue_ratio": dialogue_ratio,
        "sensory_hits": sensory_hits,
        "sensory_ratio": sensory_ratio,
        "tension_hits": tension_hits,
        "tension_ratio": tension_ratio,
        "action_hits": action_hits,
        "action_ratio": action_ratio,
        "first_person_hits": first_person_hits,
        "third_person_hits": third_person_hits,
        "omniscient_hits": omniscient_hits,
        "internality_hits": internality_hits,
        "environment_hits": environment_hits,
        "body_hits": body_hits,
        "subtext_hits": subtext_hits,
    }


def _infer_narrative_mode(metrics: dict[str, Any]) -> Optional[dict[str, Any]]:
    first_person_hits = int(metrics["first_person_hits"])
    third_person_hits = int(metrics["third_person_hits"])
    omniscient_hits = int(metrics["omniscient_hits"])

    if first_person_hits >= max(4, third_person_hits + 2):
        return {"value": "first_person", "confidence": _bounded_confidence(0.7 + first_person_hits * 0.03)}
    if omniscient_hits >= 2:
        return {"value": "omniscient", "confidence": _bounded_confidence(0.64 + omniscient_hits * 0.05)}
    if third_person_hits >= 2 or int(metrics["internality_hits"]) >= 2:
        return {"value": "close_third", "confidence": 0.62}
    return None


def _infer_dialogue_preference(metrics: dict[str, Any]) -> dict[str, Any]:
    dialogue_ratio = float(metrics["dialogue_ratio"])
    if dialogue_ratio >= 0.32:
        return {
            "value": "dialogue_forward",
            "confidence": _bounded_confidence(0.62 + (dialogue_ratio - 0.32) * 1.2),
        }
    if dialogue_ratio <= 0.16:
        return {
            "value": "narration_heavy",
            "confidence": _bounded_confidence(0.62 + (0.16 - dialogue_ratio) * 1.5),
        }
    return {
        "value": "balanced",
        "confidence": _bounded_confidence(0.58 + (0.12 - abs(dialogue_ratio - 0.29))),
    }


def _infer_sensory_density(metrics: dict[str, Any]) -> dict[str, Any]:
    sensory_ratio = float(metrics["sensory_ratio"])
    if sensory_ratio >= 1.2:
        return {
            "value": "immersive",
            "confidence": _bounded_confidence(0.64 + (sensory_ratio - 1.2) * 0.08),
        }
    if sensory_ratio <= 0.35:
        return {
            "value": "minimal",
            "confidence": _bounded_confidence(0.6 + (0.35 - sensory_ratio) * 0.25),
        }
    return {"value": "focused", "confidence": 0.6}


def _infer_tension_preference(metrics: dict[str, Any]) -> dict[str, Any]:
    tension_ratio = float(metrics["tension_ratio"])
    action_ratio = float(metrics["action_ratio"])
    if tension_ratio >= 0.7 or (tension_ratio >= 0.45 and action_ratio >= 0.45):
        return {
            "value": "high_tension",
            "confidence": _bounded_confidence(0.66 + tension_ratio * 0.18),
        }
    if tension_ratio <= 0.12 and action_ratio <= 0.18:
        return {"value": "restrained", "confidence": 0.62}
    return {"value": "balanced", "confidence": 0.58}


def _infer_pacing_preference(metrics: dict[str, Any]) -> dict[str, Any]:
    avg_paragraph_chars = float(metrics["avg_paragraph_chars"])
    dialogue_ratio = float(metrics["dialogue_ratio"])
    action_ratio = float(metrics["action_ratio"])
    sensory_ratio = float(metrics["sensory_ratio"])

    if avg_paragraph_chars <= 82 and (dialogue_ratio >= 0.32 or action_ratio >= 0.42):
        return {"value": "fast", "confidence": 0.66}
    if avg_paragraph_chars >= 150 and sensory_ratio >= 0.85:
        return {"value": "slow_burn", "confidence": 0.68}
    return {"value": "balanced", "confidence": 0.58}


def _infer_prose_style(metrics: dict[str, Any]) -> dict[str, Any]:
    avg_sentence_chars = float(metrics["avg_sentence_chars"])
    sensory_ratio = float(metrics["sensory_ratio"])
    tension_ratio = float(metrics["tension_ratio"])

    if avg_sentence_chars >= 32 and sensory_ratio >= 1.0:
        return {"value": "lyrical", "confidence": 0.68}
    if avg_sentence_chars <= 18 and tension_ratio >= 0.45:
        return {"value": "sharp", "confidence": 0.68}
    return {"value": "precise", "confidence": 0.6}


def _infer_favored_elements(metrics: dict[str, Any]) -> list[str]:
    favored_elements: list[str] = []
    if float(metrics["dialogue_ratio"]) >= 0.3:
        favored_elements.append("对话推进")
    if int(metrics["action_hits"]) >= 4:
        favored_elements.append("动作链")
    if int(metrics["internality_hits"]) >= 4:
        favored_elements.append("内心独白")
    if int(metrics["sensory_hits"]) >= 5:
        favored_elements.append("感官锚点")
    if int(metrics["environment_hits"]) >= 4:
        favored_elements.append("环境压迫")
    if int(metrics["body_hits"]) >= 4:
        favored_elements.append("身体反应")
    if int(metrics["subtext_hits"]) >= 3:
        favored_elements.append("潜台词")
    return favored_elements


def _build_learning_summary(
    *,
    observation_count: int,
    stable_preferences: list[PreferenceLearningSignal],
    favored_elements: list[str],
) -> Optional[str]:
    if not stable_preferences and not favored_elements:
        return None

    segments = [f"来自最近 {observation_count} 次人工内容变更"]
    if stable_preferences:
        signal_text = "；".join(
            [
                f"{FIELD_LABELS.get(signal.field, signal.field)}={_option_label(signal.field, signal.value)}"
                for signal in stable_preferences[:3]
            ]
        )
        segments.append(f"稳定信号：{signal_text}")
    if favored_elements:
        segments.append(f"高频保留元素：{', '.join(favored_elements[:4])}")
    return "。".join(segments) + "。"


def _to_style_template_read(
    template_key: str,
    template: dict[str, Any],
    is_active: bool,
) -> StyleTemplateRead:
    preferences = template["preferences"]
    return StyleTemplateRead(
        key=template_key,
        name=str(template["name"]),
        tagline=str(template["tagline"]),
        description=str(template["description"]),
        category=str(template["category"]),
        recommended_for=list(template.get("recommended_for", [])),
        prose_style=str(preferences["prose_style"]),
        narrative_mode=str(preferences["narrative_mode"]),
        pacing_preference=str(preferences["pacing_preference"]),
        dialogue_preference=str(preferences["dialogue_preference"]),
        tension_preference=str(preferences["tension_preference"]),
        sensory_density=str(preferences["sensory_density"]),
        favored_elements=list(preferences.get("favored_elements", [])),
        banned_patterns=list(preferences.get("banned_patterns", [])),
        custom_style_notes=preferences.get("custom_style_notes"),
        is_active=is_active,
    )


def _get_style_template_definition(template_key: str) -> dict[str, Any]:
    template = STYLE_TEMPLATES.get(template_key)
    if template is None:
        raise AppError(
            code="preference.template_not_found",
            message="Style template not found.",
            status_code=404,
            metadata={"template_key": template_key},
        )
    return template


def _should_fill_template_default(field: str, value: Any) -> bool:
    default = DEFAULT_PREFERENCE_VALUES.get(field)
    if isinstance(value, list):
        return not value
    if field == "custom_style_notes":
        return not isinstance(value, str) or not value.strip()
    return value == default


def _clone_template_value(value: Any) -> Any:
    return deepcopy(value)


def _count_markers(content: str, markers: tuple[str, ...]) -> int:
    lowered = f" {content.lower()} "
    count = 0
    for marker in markers:
        count += lowered.count(marker.lower())
    return count


def _visible_character_count(content: str) -> int:
    return len(re.sub(r"\s+", "", content))


def _split_paragraphs(content: str) -> list[str]:
    return [item.strip() for item in content.splitlines() if item.strip()]


def _split_sentences(content: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[。！？!?；;\n]+", content)
        if item.strip()
    ]


def _estimate_dialogue_chars(paragraphs: list[str]) -> int:
    total = 0
    for paragraph in paragraphs:
        if any(token in paragraph for token in ('"', "“", "”", "「", "」", "『", "』")):
            total += len(paragraph)
            continue
        if re.match(r"^[^。！？!?]{1,12}[：:]", paragraph):
            total += len(paragraph)
    return total


def _content_change_ratio(
    previous_content: Optional[str],
    current_content: str,
) -> float:
    if previous_content is None:
        return 1.0

    previous_normalized = _normalize_text(previous_content)
    current_normalized = _normalize_text(current_content)
    if not previous_normalized:
        return 1.0
    if previous_normalized == current_normalized:
        return 0.0

    similarity = SequenceMatcher(
        a=previous_normalized[:6000],
        b=current_normalized[:6000],
    ).ratio()
    return round(1 - similarity, 4)


def _normalize_text(content: str) -> str:
    return re.sub(r"\s+", "", content or "")


def _option_label(field: str, value: str) -> str:
    return STYLE_OPTION_LABELS.get(field, {}).get(value, value)


def _bounded_confidence(value: float) -> float:
    return round(max(0.45, min(value, 0.95)), 2)


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _get_value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _newer_datetime(current: Any, candidate: Any) -> Any:
    if current is None:
        return candidate
    if candidate is None:
        return current
    return candidate if candidate > current else current
