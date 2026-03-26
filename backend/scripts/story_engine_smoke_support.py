from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
DEFAULT_PASSWORD = "StoryEngineSmoke123"
DEFAULT_WORKFLOW_READ_TIMEOUT = 900.0
DEFAULT_STREAM_TIMEOUT = 240.0
DEFAULT_EMAIL_PREFIX = "story-engine-smoke"

SCENARIO_MAINLINE = "mainline"
SCENARIO_BRANCH_SCOPE = "branch-scope"
SCENARIO_CLOUD_DRAFT = "cloud-draft"
SCENARIO_ALL = "all"
SCENARIO_CHOICES = (
    SCENARIO_MAINLINE,
    SCENARIO_BRANCH_SCOPE,
    SCENARIO_CLOUD_DRAFT,
    SCENARIO_ALL,
)
EXECUTABLE_SCENARIOS = (
    SCENARIO_MAINLINE,
    SCENARIO_BRANCH_SCOPE,
    SCENARIO_CLOUD_DRAFT,
)

FIXED_OUTLINE_IDEA = (
    "主角林澈出身没落宗门，被当成弃子。"
    "他每次越级爆发都必须付出真实代价，代价会逐步逼出身世秘密。"
    "第一卷目标是先活下来，再在压制中完成第一波反击，并埋下宿敌线和身世线。"
)
FIXED_STYLE_SAMPLE = (
    "夜风压着屋檐往下坠，街面上连一盏敢亮到最后的灯都没有。"
    "他把手按在门框上，指节因为太用力而发白，却还是没让自己退半步。"
)
FIXED_FINAL_STYLE_SAMPLE = (
    "风压一寸寸落下来，像有人把整条街的呼吸都按进了泥里。"
    "他没说话，只把肩膀往前送了半步，像是要替自己把退路堵死。"
)
FIXED_BRANCH_LOCATION_NAME = "镜城"


class SmokeAssertionError(AssertionError):
    """烟雾测试内部断言失败。"""


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeAssertionError(message)


def build_smoke_email(
    prefix: str | None = None,
    *,
    now: datetime | None = None,
) -> str:
    raw_prefix = (prefix or DEFAULT_EMAIL_PREFIX).strip()
    normalized_prefix = raw_prefix or DEFAULT_EMAIL_PREFIX
    timestamp = (now or datetime.now()).strftime("%Y%m%d%H%M%S")
    return f"{normalized_prefix}-{timestamp}@example.com"


def resolve_selected_scenarios(scenario: str) -> list[str]:
    if scenario == SCENARIO_ALL:
        return list(EXECUTABLE_SCENARIOS)
    ensure(scenario in SCENARIO_CHOICES, f"未知 smoke 场景：{scenario}")
    return [scenario]


def write_summary_file(summary: dict[str, Any], path: str | None) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def assert_mainline_summary(summary: dict[str, Any], *, expect_final: bool = True) -> None:
    outline = dict(summary.get("outline") or {})
    guard = dict(summary.get("guard") or {})
    stream = dict(summary.get("stream") or {})
    chapter = dict(summary.get("chapter") or {})
    next_chapter = dict(summary.get("next_chapter") or {})
    final_optimize = summary.get("final_optimize")

    ensure(int(outline.get("level_1_count") or 0) >= 1, "主链 smoke 未生成一级大纲。")
    ensure(int(outline.get("level_2_count") or 0) >= 1, "主链 smoke 未生成二级大纲。")
    ensure(int(outline.get("level_3_count") or 0) >= 1, "主链 smoke 未生成三级大纲。")
    ensure(int(outline.get("workflow_event_count") or 0) >= 3, "大纲流程时间线过短。")

    ensure(bool(guard.get("should_pause")), "实时守护没有在固定违规文本上暂停。")
    ensure(int(guard.get("alert_count") or 0) >= 1, "实时守护没有返回任何提醒。")

    final_event = dict(stream.get("final_event") or {})
    ensure(int(stream.get("event_count") or 0) >= 3, "流式正文事件数过少。")
    ensure(str(final_event.get("event")) == "done", "流式正文没有正常结束。")
    ensure(int(stream.get("draft_length") or 0) >= 120, "生成正文长度过短。")

    ensure(bool(chapter.get("chapter_id")), "主链 smoke 没有落成正式章节。")
    ensure(str(chapter.get("status") or "").strip() in {"writing", "final"}, "章节状态异常。")
    ensure(int(chapter.get("current_version_number") or 0) >= 1, "章节版本号异常。")

    if expect_final:
        ensure(isinstance(final_optimize, dict), "主链 smoke 缺少终稿收口结果。")
        final_payload = dict(final_optimize or {})
        ensure(int(final_payload.get("final_draft_length") or 0) >= 120, "终稿长度过短。")
        ensure(bool(final_payload.get("chapter_summary_id")), "终稿收口没有返回章节总结。")
        ensure(
            int(final_payload.get("workflow_event_count") or 0) >= 5,
            "终稿收口流程时间线过短。",
        )
        ensure(str(chapter.get("status") or "").strip() == "final", "章节没有成功标记为终稿。")
        ensure(int(next_chapter.get("chapter_number") or 0) == 2, "终稿后没有准备好下一章。")
    else:
        ensure(int(next_chapter.get("chapter_number") or 0) >= 1, "未能拿到下一章候选。")


def assert_branch_scope_summary(summary: dict[str, Any]) -> None:
    ensure(bool(summary.get("default_branch_id")), "缺少默认分线。")
    ensure(bool(summary.get("new_branch_id")), "支线创建失败。")
    ensure(bool(summary.get("new_volume_id")), "分卷创建失败。")
    ensure(
        str(summary.get("new_branch_id")) != str(summary.get("default_branch_id")),
        "新分线和默认分线意外相同。",
    )

    branch_chapter_numbers = [int(item) for item in list(summary.get("branch_chapter_numbers") or [])]
    default_chapter_numbers = [int(item) for item in list(summary.get("default_chapter_numbers") or [])]
    ensure(7 in branch_chapter_numbers, "支线章节没有成功写入支线作用域。")
    ensure(7 not in default_chapter_numbers, "支线章节泄漏到了默认主线。")

    branch_location_names = [str(item) for item in list(summary.get("branch_location_names") or [])]
    default_location_names = [str(item) for item in list(summary.get("default_location_names") or [])]
    ensure(FIXED_BRANCH_LOCATION_NAME in branch_location_names, "支线设定没有写入分线圣经。")
    ensure(FIXED_BRANCH_LOCATION_NAME not in default_location_names, "支线设定泄漏到了项目主圣经。")


def assert_cloud_draft_summary(summary: dict[str, Any]) -> None:
    ensure(bool(summary.get("draft_snapshot_id")), "云端续写稿没有成功写入。")
    ensure(int(summary.get("listed_count_after_upsert") or 0) >= 1, "写入后没有列出续写稿。")
    ensure(bool(summary.get("detail_matches")), "读取回来的续写稿内容不一致。")
    ensure(bool(summary.get("deleted")), "云端续写稿没有成功删除。")
    ensure(
        bool(summary.get("deleted_absent_from_list")),
        "删除后续写稿仍然出现在列表里。",
    )


def assert_scenario_summary(
    scenario: str,
    summary: dict[str, Any],
    *,
    expect_final: bool = True,
) -> None:
    if scenario == SCENARIO_MAINLINE:
        assert_mainline_summary(summary, expect_final=expect_final)
        return
    if scenario == SCENARIO_BRANCH_SCOPE:
        assert_branch_scope_summary(summary)
        return
    if scenario == SCENARIO_CLOUD_DRAFT:
        assert_cloud_draft_summary(summary)
        return
    raise SmokeAssertionError(f"未知 smoke 场景：{scenario}")
