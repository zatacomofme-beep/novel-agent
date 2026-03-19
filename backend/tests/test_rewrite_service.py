from __future__ import annotations

import unittest
from types import SimpleNamespace

from services.rewrite_service import (
    _build_selection_rewrite_prompt,
    _fallback_rewrite,
    _normalize_rewritten_text,
    _replace_selection,
)


class RewriteServiceTests(unittest.TestCase):
    def test_replace_selection_swaps_target_fragment(self) -> None:
        updated = _replace_selection(
            "甲看着门。乙没有动。",
            start=0,
            end=5,
            replacement="甲盯住门缝。",
        )

        self.assertEqual(updated, "甲盯住门缝。乙没有动。")

    def test_normalize_rewritten_text_strips_wrapper_prefix(self) -> None:
        normalized = _normalize_rewritten_text(
            "改写后：\n“她没有回头，只把呼吸压得更低。”",
            "原文",
        )

        self.assertEqual(normalized, "她没有回头，只把呼吸压得更低。")

    def test_build_prompt_includes_style_and_comment_context(self) -> None:
        prompt = _build_selection_rewrite_prompt(
            chapter=SimpleNamespace(chapter_number=7, title="潮门"),
            original_text="她把手按在门上，没有立刻推开。",
            instruction="增强张力和身体反应",
            style_guidance="风格偏好：文风=冷峻锋利。",
            story_bible=SimpleNamespace(
                title="海潮归航",
                genre="奇幻",
                theme="归乡",
                tone="克制",
                characters=[{"name": "林澈"}],
                plot_threads=[{"title": "潮门潜入"}],
            ),
            content="前文片段她停在门前。她把手按在门上，没有立刻推开。后文片段脚步声已经到了转角。",
            selection_start=8,
            selection_end=24,
            related_comments=["这里还缺一点身体反应。"],
        )

        self.assertIn("风格指导=风格偏好：文风=冷峻锋利。", prompt)
        self.assertIn("相关批注=", prompt)
        self.assertIn("这里还缺一点身体反应。", prompt)
        self.assertIn("待改写片段=她把手按在门上，没有立刻推开。", prompt)

    def test_fallback_rewrite_reacts_to_instruction_keywords(self) -> None:
        rewritten = _fallback_rewrite(
            original_text="她有些迟疑，然后往前走了一步",
            instruction="更简洁，增强张力和情绪",
            style_guidance="文风=冷峻锋利",
            related_comments=["把动作压得更紧。"],
        )

        self.assertIn("空气骤然绷紧", rewritten)
        self.assertIn("那点迟疑没有说出口", rewritten)
        self.assertNotIn("有些", rewritten)


if __name__ == "__main__":
    unittest.main()
