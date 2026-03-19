from __future__ import annotations

from typing import Any

from memory.story_bible import StoryBibleContext


def evaluate_consistency(
    text: str,
    context: StoryBibleContext,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    lowered = text.lower()
    issues: list[dict[str, Any]] = []

    character_hits = sum(
        1
        for character in context.characters
        if character["name"] and character["name"].lower() in lowered
    )
    world_hits = sum(
        1
        for item in context.world_settings
        if item["title"] and item["title"].lower() in lowered
    )
    timeline_hits = sum(
        1
        for item in context.timeline_events
        if item["title"] and item["title"].lower() in lowered
    )

    character_score = min(1.0, 0.55 + character_hits * 0.08)
    world_score = min(1.0, 0.55 + world_hits * 0.10)
    timeline_score = min(1.0, 0.60 + timeline_hits * 0.08)
    logic_score = 0.72 if len(text.strip()) >= 500 else 0.58

    if context.characters and character_hits == 0:
        issues.append(
            {
                "dimension": "character_consistency",
                "severity": "medium",
                "message": "文本未明显引用已登记人物，可能缺少设定回扣。",
            }
        )
    if context.world_settings and world_hits == 0:
        issues.append(
            {
                "dimension": "world_consistency",
                "severity": "medium",
                "message": "文本未明显回扣世界设定，世界观锚点偏弱。",
            }
        )
    if len(text.strip()) < 500:
        issues.append(
            {
                "dimension": "logic_coherence",
                "severity": "high",
                "message": "正文过短，逻辑与叙事信息不足，难以形成稳定评估。",
            }
        )

    return (
        {
            "character_consistency": character_score,
            "world_consistency": world_score,
            "logic_coherence": logic_score,
            "timeline_consistency": timeline_score,
        },
        issues,
    )
