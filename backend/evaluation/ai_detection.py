from __future__ import annotations

import re


AI_WORDS = [
    "令人不禁",
    "宛如",
    "总之",
    "可以说",
    "值得注意的是",
    "综上所述",
    "显而易见",
]


def split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[。！？!?]+", text) if item.strip()]


def split_paragraphs(text: str) -> list[str]:
    return [item.strip() for item in text.splitlines() if item.strip()]


def detect_ai_words(text: str) -> list[str]:
    return [word for word in AI_WORDS if word in text]


def sentence_variation_score(text: str) -> float:
    sentences = split_sentences(text)
    lengths = [len(sentence) for sentence in sentences]
    if len(lengths) < 2:
        return 0.3

    mean = sum(lengths) / len(lengths)
    variance = sum((value - mean) ** 2 for value in lengths) / len(lengths)
    std_dev = variance ** 0.5

    if 15 <= std_dev <= 40:
        return 1.0
    if std_dev < 15:
        return max(0.0, std_dev / 15)
    return max(0.0, 1.0 - (std_dev - 40) / 40)


def burstiness_score(text: str) -> float:
    paragraphs = split_paragraphs(text)
    lengths = [len(paragraph) for paragraph in paragraphs]
    if len(lengths) < 2:
        return 0.3

    mean = sum(lengths) / len(lengths)
    if mean <= 0:
        return 0.0

    variance = sum((value - mean) ** 2 for value in lengths) / len(lengths)
    std_dev = variance ** 0.5
    coefficient = std_dev / mean

    if 0.5 <= coefficient <= 1.5:
        return 1.0
    if coefficient < 0.5:
        return max(0.0, coefficient / 0.5)
    return max(0.0, 1.0 - (coefficient - 1.5) / 1.5)


def calculate_ai_taste_score(text: str) -> tuple[float, list[str]]:
    flagged_words = detect_ai_words(text)
    variation = sentence_variation_score(text)
    burstiness = burstiness_score(text)

    word_penalty = min(0.4, len(flagged_words) * 0.08)
    variation_penalty = (1.0 - variation) * 0.25
    burstiness_penalty = (1.0 - burstiness) * 0.25
    short_text_penalty = 0.15 if len(text.strip()) < 500 else 0.0

    score = min(
        1.0,
        0.1 + word_penalty + variation_penalty + burstiness_penalty + short_text_penalty,
    )
    return score, flagged_words
