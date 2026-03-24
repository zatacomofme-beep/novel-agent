from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class StoryAgentSpec:
    name: str
    role: str
    priority: int
    system_prompt_template: str
    tools: list[str]
    output_format: dict[str, Any]


def build_story_agent_specs() -> dict[str, StoryAgentSpec]:
    return {
        "guardian": StoryAgentSpec(
            name="Guardian_Agent",
            role="设定守护Agent",
            priority=1,
            system_prompt_template=(
                "你是网文创作系统中的 Guardian_Agent。"
                "你的唯一职责是守住红线：禁止幻觉、禁止 OOC、禁止世界规则违背、禁止时间线自相矛盾。"
                "你只能基于人物库、伏笔库、物品库、世界规则库、时间线地图库、三级大纲库作判断。"
                "发现问题时必须指出冲突点、证据、风险等级和最小修复方案。"
            ),
            tools=[
                "CharacterDB",
                "ForeshadowDB",
                "ItemDB",
                "WorldDB",
                "TimelineMapDB",
                "OutlineDB",
                "ChromaSearch",
            ],
            output_format={
                "summary": "string",
                "issues": [
                    {
                        "severity": "critical|high|medium|low",
                        "title": "string",
                        "detail": "string",
                        "source": "guardian",
                        "suggestion": "string",
                    }
                ],
                "proposed_actions": ["string"],
            },
        ),
        "logic_debunker": StoryAgentSpec(
            name="Logic_Debunker_Agent",
            role="逻辑杠精Agent",
            priority=2,
            system_prompt_template=(
                "你是 Logic_Debunker_Agent。"
                "你的任务不是写得漂亮，而是把剧情推演到极限，专找战力崩坏、时间线断裂、伏笔回收失衡、因果链空洞。"
                "所有质疑都必须明确指出在哪个章节阶段会炸。"
            ),
            tools=[
                "CharacterDB",
                "ForeshadowDB",
                "ItemDB",
                "WorldDB",
                "TimelineMapDB",
                "OutlineDB",
                "ChromaSearch",
            ],
            output_format={
                "summary": "string",
                "issues": ["同 Guardian 输出协议"],
                "proposed_actions": ["string"],
            },
        ),
        "commercial": StoryAgentSpec(
            name="Commercial_Expert_Agent",
            role="商业化专家Agent",
            priority=3,
            system_prompt_template=(
                "你是 Commercial_Expert_Agent。"
                "你负责提升网文商业表现：爽点密度、节奏、章末钩子、平台适配、读者追更欲。"
                "在任何建议中都不能破坏一级大纲和设定红线。"
            ),
            tools=["OutlineDB", "爆款模板库", "ChromaSearch"],
            output_format={
                "summary": "string",
                "issues": ["节奏风险、钩子不足、爽点断层等问题"],
                "proposed_actions": ["string"],
            },
        ),
        "style_guardian": StoryAgentSpec(
            name="Style_Guardian_Agent",
            role="文风守护Agent",
            priority=4,
            system_prompt_template=(
                "你是 Style_Guardian_Agent。"
                "你必须维护写手自己的语言习惯、句式节奏、叙述距离和情绪表达。"
                "你可以优化文本，但不能把稿子改成陌生人的声音。"
            ),
            tools=["WriterStyleProfile", "StyleSampleMemory"],
            output_format={
                "summary": "string",
                "issues": ["文风偏移、口吻不稳、信息密度失衡"],
                "proposed_actions": ["string"],
            },
        ),
        "anchor": StoryAgentSpec(
            name="Anchor_Agent",
            role="剧情锚定Agent",
            priority=5,
            system_prompt_template=(
                "你是 Anchor_Agent。"
                "你负责把章节沉淀为结构化总结，并抽取必须回写知识库的增量。"
                "你的输出必须可直接进入章节总结库和知识库更新清单。"
            ),
            tools=[
                "ChapterSummaryDB",
                "CharacterDB",
                "ForeshadowDB",
                "ItemDB",
                "WorldDB",
                "TimelineMapDB",
                "OutlineDB",
            ],
            output_format={
                "summary": "string",
                "chapter_summary": "dict",
                "kb_updates": ["dict"],
            },
        ),
        "arbitrator": StoryAgentSpec(
            name="Arbitrator_Agent",
            role="终局仲裁Agent",
            priority=0,
            system_prompt_template=(
                "你是 Arbitrator_Agent。"
                "你的职责是收敛争议，统一结论，输出唯一执行方案。"
                "如果 Guardian 与商业优化发生冲突，你永远优先保障设定一致性，再寻找商业化补救。"
            ),
            tools=["AllAgentOutputs"],
            output_format={
                "summary": "string",
                "issues": ["最终保留的问题"],
                "proposed_actions": ["统一修改方案"],
                "consensus": "bool",
            },
        ),
    }


STORY_AGENT_SPECS = build_story_agent_specs()


def build_agent_report(
    agent_key: str,
    *,
    summary: str,
    issues: list[dict[str, Any]] | None = None,
    proposed_actions: list[str] | None = None,
    raw_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = STORY_AGENT_SPECS[agent_key]
    return {
        "agent_name": spec.name,
        "role": spec.role,
        "priority": spec.priority,
        "summary": summary,
        "issues": issues or [],
        "proposed_actions": proposed_actions or [],
        "raw_output": raw_output or {
            "system_prompt_template": spec.system_prompt_template,
            "tools": spec.tools,
            "output_format": spec.output_format,
        },
    }


def export_agent_specs() -> list[dict[str, Any]]:
    return [asdict(spec) for spec in STORY_AGENT_SPECS.values()]
