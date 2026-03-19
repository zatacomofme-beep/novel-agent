from __future__ import annotations

import re
from typing import Any
from typing import Optional

from evaluation.ai_detection import (
    calculate_ai_taste_score,
    burstiness_score,
    sentence_variation_score,
    split_paragraphs,
    split_sentences,
)
from evaluation.consistency import evaluate_consistency
from evaluation.metrics import QualityMetrics
from memory.story_bible import StoryBibleContext


def evaluate_chapter_text(
    text: str,
    context: StoryBibleContext,
) -> tuple[QualityMetrics, list[dict[str, Any]], str]:
    stripped = text.strip()
    sentences = split_sentences(stripped)
    paragraphs = split_paragraphs(stripped)
    sentence_lengths = [len(sentence) for sentence in sentences] or [0]
    avg_sentence_length = sum(sentence_lengths) / max(1, len(sentence_lengths))
    unique_chars_ratio = _unique_ratio(stripped)
    dialogue_count = stripped.count("“") + stripped.count("\"")
    suspense_markers = sum(stripped.count(marker) for marker in ["?", "？", "忽然", "却", "但是"])
    conflict_markers = sum(
        stripped.count(marker) for marker in ["冲突", "争执", "愤怒", "失控", "危险", "对抗"]
    )
    emotional_markers = sum(
        stripped.count(marker) for marker in ["心", "痛", "爱", "恐惧", "悲伤", "喜悦"]
    )
    imagery_markers = sum(
        stripped.count(marker) for marker in ["光", "影", "风", "雨", "夜", "火", "雾"]
    )

    ai_taste_score, flagged_words = calculate_ai_taste_score(stripped)
    variation_score = sentence_variation_score(stripped)
    burst_score = burstiness_score(stripped)
    consistency_scores, consistency_issues = evaluate_consistency(stripped, context)

    metrics = QualityMetrics(
        fluency=_score_range(avg_sentence_length, 12, 38),
        vocabulary_richness=max(0.2, min(1.0, unique_chars_ratio * 2.6)),
        sentence_variation=variation_score,
        plot_tightness=max(0.3, min(1.0, len(paragraphs) / 8)),
        conflict_intensity=max(0.2, min(1.0, conflict_markers / 8)),
        suspense=max(0.2, min(1.0, suspense_markers / 8)),
        character_consistency=consistency_scores["character_consistency"],
        world_consistency=consistency_scores["world_consistency"],
        logic_coherence=consistency_scores["logic_coherence"],
        timeline_consistency=consistency_scores["timeline_consistency"],
        emotional_resonance=max(0.2, min(1.0, emotional_markers / 10)),
        imagery=max(0.2, min(1.0, imagery_markers / 12)),
        dialogue_quality=max(0.2, min(1.0, dialogue_count / 12)),
        theme_depth=max(0.25, min(1.0, _theme_overlap(stripped, context.theme) + 0.35)),
        ai_taste_score=ai_taste_score,
    )

    issues = list(consistency_issues)
    if flagged_words:
        issues.append(
            {
                "dimension": "ai_taste_score",
                "severity": "medium",
                "message": f"检测到 AI 高频词：{', '.join(flagged_words)}",
            }
        )
    if len(stripped) < 500:
        issues.append(
            {
                "dimension": "plot_tightness",
                "severity": "high",
                "message": "章节内容过短，当前更接近提纲或片段，尚不足以进行稳定发布级评估。",
            }
        )
    if burst_score < 0.45:
        issues.append(
            {
                "dimension": "sentence_variation",
                "severity": "medium",
                "message": "段落长度分布过于均匀，文本突发性不足。",
            }
        )

    summary = _build_summary(metrics, issues)
    return metrics, issues, summary


def _unique_ratio(text: str) -> float:
    normalized = re.sub(r"\s+", "", text)
    if not normalized:
        return 0.0
    return len(set(normalized)) / len(normalized)


def _score_range(value: float, lower: float, upper: float) -> float:
    if lower <= value <= upper:
        return 1.0
    if value < lower:
        return max(0.2, value / lower)
    return max(0.2, 1.0 - ((value - upper) / max(upper, 1.0)))


def _theme_overlap(text: str, theme: Optional[str]) -> float:
    if not theme:
        return 0.2
    tokens = [token.strip() for token in re.split(r"[\s,，。；;]+", theme) if token.strip()]
    if not tokens:
        return 0.2
    hits = sum(1 for token in tokens if token in text)
    return min(0.65, hits / max(1, len(tokens)))


def _build_summary(metrics: QualityMetrics, issues: list[dict[str, Any]]) -> str:
    overall = metrics.calculate_overall_score()
    if overall >= 0.85 and metrics.ai_taste_score <= 0.2:
        return "文本已接近发布级，主要问题集中在局部细节而非结构性缺陷。"
    if overall >= 0.75:
        return "文本达到审核级，但仍需要针对一致性或语言突发性做进一步打磨。"
    if issues:
        return "当前文本仍处于草稿级，建议先解决高严重度问题，再进入润色流程。"
    return "当前文本已完成基础评估，但尚缺少足够信息形成稳定高分判断。"
