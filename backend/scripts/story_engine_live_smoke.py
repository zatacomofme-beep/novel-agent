from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import httpx

try:
    from scripts.story_engine_smoke_support import (
        DEFAULT_BASE_URL,
        DEFAULT_EMAIL_PREFIX,
        DEFAULT_PASSWORD,
        DEFAULT_STREAM_TIMEOUT,
        DEFAULT_WORKFLOW_READ_TIMEOUT,
        FIXED_BRANCH_LOCATION_NAME,
        FIXED_FINAL_STYLE_SAMPLE,
        FIXED_OUTLINE_IDEA,
        FIXED_STYLE_SAMPLE,
        SCENARIO_ALL,
        SCENARIO_BRANCH_SCOPE,
        SCENARIO_CHOICES,
        SCENARIO_CLOUD_DRAFT,
        SCENARIO_MAINLINE,
        SmokeAssertionError,
        assert_branch_scope_summary,
        assert_cloud_draft_summary,
        assert_mainline_summary,
        build_smoke_email,
        ensure,
        resolve_selected_scenarios,
        write_summary_file,
    )
except ModuleNotFoundError:  # pragma: no cover - 兼容直接执行脚本
    from story_engine_smoke_support import (
        DEFAULT_BASE_URL,
        DEFAULT_EMAIL_PREFIX,
        DEFAULT_PASSWORD,
        DEFAULT_STREAM_TIMEOUT,
        DEFAULT_WORKFLOW_READ_TIMEOUT,
        FIXED_BRANCH_LOCATION_NAME,
        FIXED_FINAL_STYLE_SAMPLE,
        FIXED_OUTLINE_IDEA,
        FIXED_STYLE_SAMPLE,
        SCENARIO_ALL,
        SCENARIO_BRANCH_SCOPE,
        SCENARIO_CHOICES,
        SCENARIO_CLOUD_DRAFT,
        SCENARIO_MAINLINE,
        SmokeAssertionError,
        assert_branch_scope_summary,
        assert_cloud_draft_summary,
        assert_mainline_summary,
        build_smoke_email,
        ensure,
        resolve_selected_scenarios,
        write_summary_file,
    )

RETRYABLE_REQUEST_ERRORS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


def _build_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

def _print_step(message: str) -> None:
    print(f"[smoke] {message}")


def _ensure(condition: bool, message: str) -> None:
    ensure(condition, message)


def _build_chapter_outline_payload(outline: dict[str, Any] | None) -> dict[str, Any] | None:
    if not outline:
        return None
    return {
        "outline_id": outline.get("outline_id"),
        "parent_id": outline.get("parent_id"),
        "level": outline.get("level"),
        "title": outline.get("title"),
        "content": outline.get("content"),
        "status": outline.get("status"),
        "version": outline.get("version"),
        "node_order": outline.get("node_order"),
        "locked": outline.get("locked"),
    }


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    retries: int = 3,
    **kwargs: Any,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return await client.request(method, path, **kwargs)
        except RETRYABLE_REQUEST_ERRORS as exc:
            last_error = exc
            if attempt >= retries:
                raise
            await asyncio.sleep(1.5 * attempt)
    if last_error is not None:
        raise last_error
    raise RuntimeError("request retry failed unexpectedly")


async def _register_and_login(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "POST",
        "/auth/register",
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    return response.json()


async def _create_project(
    client: httpx.AsyncClient,
    *,
    token: str,
    suffix: str,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "POST",
        "/projects",
        headers=_build_headers(token),
        json={
            "title": f"联调烟雾测试项目-{suffix}",
            "genre": "玄幻",
            "theme": "代价与成长",
            "tone": "热血压迫感",
            "status": "draft",
        },
    )
    response.raise_for_status()
    return response.json()


async def _load_structure(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "GET",
        f"/projects/{project_id}/structure",
        headers=_build_headers(token),
    )
    response.raise_for_status()
    return response.json()


async def _run_outline_stress(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    workflow_read_timeout: float,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "POST",
        f"/projects/{project_id}/story-engine/workflows/outline-stress-test",
        headers=_build_headers(token),
        json={
            "idea": FIXED_OUTLINE_IDEA,
            "genre": "玄幻",
            "tone": "热血压迫感",
            "target_chapter_count": 12,
            "target_total_words": 120000,
            "source_material": None,
            "source_material_name": None,
        },
        timeout=httpx.Timeout(
            connect=20.0,
            read=workflow_read_timeout,
            write=60.0,
            pool=60.0,
        ),
    )
    response.raise_for_status()
    return response.json()


async def _bulk_import_template(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    workflow_read_timeout: float,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "POST",
        f"/projects/{project_id}/story-engine/imports/bulk",
        headers=_build_headers(token),
        json={
            "template_key": "xuanhuan_upgrade",
            "replace_existing_sections": [],
        },
        timeout=httpx.Timeout(
            connect=20.0,
            read=workflow_read_timeout,
            write=60.0,
            pool=60.0,
        ),
    )
    response.raise_for_status()
    return response.json()


async def _load_workspace(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    branch_id: str | None = None,
) -> dict[str, Any]:
    path = f"/projects/{project_id}/story-engine/workspace"
    if branch_id:
        path = f"{path}?branch_id={branch_id}"
    response = await _request_with_retry(
        client,
        "GET",
        path,
        headers=_build_headers(token),
    )
    response.raise_for_status()
    return response.json()


async def _run_realtime_guard(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    outline_id: str | None,
    current_outline: str | None,
) -> dict[str, Any]:
    draft_text = (
        "主角眼前一黑，下一瞬却毫无代价开挂，硬生生把本不可能赢的局面翻了过来。"
        "大战后秒恢复，连半点反噬都没有，仿佛之前所有代价规则都只是摆设。"
    )
    response = await _request_with_retry(
        client,
        "POST",
        f"/projects/{project_id}/story-engine/workflows/realtime-guard",
        headers=_build_headers(token),
        json={
            "chapter_number": 1,
            "chapter_title": "第一章：开局吃亏",
            "outline_id": outline_id,
            "current_outline": current_outline,
            "recent_chapters": [],
            "draft_text": draft_text,
            "latest_paragraph": draft_text,
        },
    )
    response.raise_for_status()
    return response.json()


async def _run_stream_generation(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    outline_id: str | None,
    current_outline: str | None,
    stream_timeout: float,
) -> dict[str, Any]:
    payload = {
        "chapter_number": 1,
        "chapter_title": "第一章：开局吃亏",
        "outline_id": outline_id,
        "current_outline": current_outline,
        "recent_chapters": [],
        "existing_text": "",
        "style_sample": FIXED_STYLE_SAMPLE,
        "target_word_count": 1200,
        "target_paragraph_count": 4,
    }
    events: list[dict[str, Any]] = []
    started_at = time.perf_counter()
    async with client.stream(
        "POST",
        f"/projects/{project_id}/story-engine/workflows/chapter-stream",
        headers=_build_headers(token),
        json=payload,
        timeout=httpx.Timeout(
            connect=20.0,
            read=stream_timeout,
            write=60.0,
            pool=60.0,
        ),
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            raw = line.strip()
            if not raw:
                continue
            events.append(json.loads(raw))
    elapsed = round(time.perf_counter() - started_at, 2)
    final_event = events[-1] if events else {}
    latest_text = ""
    for item in reversed(events):
        if item.get("text"):
            latest_text = str(item["text"])
            break
    return {
        "elapsed_seconds": elapsed,
        "event_count": len(events),
        "final_event": final_event,
        "draft_text": latest_text,
        "workflow_timeline": (final_event.get("metadata") or {}).get("workflow_timeline") or [],
    }


async def _create_chapter(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    branch_id: str | None,
    volume_id: str | None,
    chapter_number: int,
    title: str,
    content: str,
    outline: dict[str, Any] | None,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "POST",
        f"/projects/{project_id}/chapters",
        headers=_build_headers(token),
        json={
            "chapter_number": chapter_number,
            "branch_id": branch_id,
            "volume_id": volume_id,
            "title": title,
            "content": content,
            "outline": _build_chapter_outline_payload(outline),
            "status": "writing" if content.strip() else "draft",
            "change_reason": "Created from story-engine live smoke",
        },
    )
    response.raise_for_status()
    return response.json()


async def _update_chapter_content(
    client: httpx.AsyncClient,
    *,
    chapter_id: str,
    token: str,
    content: str,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "PATCH",
        f"/chapters/{chapter_id}",
        headers=_build_headers(token),
        json={
            "content": content,
            "change_reason": "Updated from story-engine live smoke",
            "create_version": True,
        },
    )
    response.raise_for_status()
    return response.json()


async def _mark_chapter_final(
    client: httpx.AsyncClient,
    *,
    chapter_id: str,
    token: str,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "PATCH",
        f"/chapters/{chapter_id}",
        headers=_build_headers(token),
        json={
            "status": "final",
            "change_reason": "Marked as final from story-engine live smoke",
            "create_version": False,
        },
    )
    response.raise_for_status()
    return response.json()


async def _run_final_optimize(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    chapter_id: str | None,
    draft_text: str,
    workflow_read_timeout: float,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "POST",
        f"/projects/{project_id}/story-engine/workflows/final-optimize",
        headers=_build_headers(token),
        json={
            "chapter_id": chapter_id,
            "chapter_number": 1,
            "chapter_title": "第一章：开局吃亏",
            "draft_text": draft_text,
            "style_sample": FIXED_FINAL_STYLE_SAMPLE,
        },
        timeout=httpx.Timeout(
            connect=20.0,
            read=workflow_read_timeout,
            write=60.0,
            pool=60.0,
        ),
    )
    response.raise_for_status()
    return response.json()


async def _resolve_first_kb_suggestion(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    chapter_summary: dict[str, Any],
    kb_update_list: list[dict[str, Any]],
) -> dict[str, Any] | None:
    summary_id = chapter_summary.get("summary_id")
    if not summary_id:
        return None

    first_suggestion = next(
        (
            item
            for item in kb_update_list
            if str(item.get("suggestion_id") or "").strip()
            and str(item.get("status") or "pending") == "pending"
        ),
        None,
    )
    if first_suggestion is None:
        return None

    suggestion_id = str(first_suggestion["suggestion_id"])
    for action in ("apply", "ignore"):
        response = await _request_with_retry(
            client,
            "POST",
            f"/projects/{project_id}/story-engine/chapter-summaries/{summary_id}/kb-updates/{suggestion_id}",
            headers=_build_headers(token),
            json={"action": action},
        )
        if response.is_success:
            return response.json()
        if response.status_code not in {400, 409, 422}:
            response.raise_for_status()
    return None


async def _load_bootstrap(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    branch_id: str | None = None,
) -> dict[str, Any]:
    path = f"/projects/{project_id}/bootstrap"
    if branch_id:
        path = f"{path}?branch_id={branch_id}"
    response = await _request_with_retry(
        client,
        "GET",
        path,
        headers=_build_headers(token),
    )
    response.raise_for_status()
    return response.json()


async def _create_branch(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    title: str,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "POST",
        f"/projects/{project_id}/branches",
        headers=_build_headers(token),
        json={
            "title": title,
            "description": "烟雾测试支线",
            "status": "active",
            "copy_chapters": False,
            "is_default": False,
        },
    )
    response.raise_for_status()
    return response.json()


async def _create_volume(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    title: str,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "POST",
        f"/projects/{project_id}/volumes",
        headers=_build_headers(token),
        json={
            "title": title,
            "summary": "烟雾测试卷",
            "status": "planning",
        },
    )
    response.raise_for_status()
    return response.json()


async def _load_story_bible(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    branch_id: str | None = None,
) -> dict[str, Any]:
    path = f"/projects/{project_id}/bible"
    if branch_id:
        path = f"{path}?branch_id={branch_id}"
    response = await _request_with_retry(
        client,
        "GET",
        path,
        headers=_build_headers(token),
    )
    response.raise_for_status()
    return response.json()


async def _upsert_story_bible_branch_location(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    branch_id: str,
    location_name: str,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "POST",
        f"/projects/{project_id}/bible/item?branch_id={branch_id}",
        headers=_build_headers(token),
        json={
            "section_key": "locations",
            "item": {
                "name": location_name,
                "data": {
                    "description": "支线专用地点",
                    "features": ["只在支线出现"],
                },
                "version": 1,
            },
        },
    )
    response.raise_for_status()
    return response.json()


async def _list_chapters(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    branch_id: str | None = None,
    volume_id: str | None = None,
) -> list[dict[str, Any]]:
    query_parts: list[str] = []
    if branch_id:
        query_parts.append(f"branch_id={branch_id}")
    if volume_id:
        query_parts.append(f"volume_id={volume_id}")
    query_text = f"?{'&'.join(query_parts)}" if query_parts else ""
    response = await _request_with_retry(
        client,
        "GET",
        f"/projects/{project_id}/chapters{query_text}",
        headers=_build_headers(token),
    )
    response.raise_for_status()
    return response.json()


async def _upsert_cloud_draft(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    branch_id: str | None,
    volume_id: str | None,
    chapter_number: int,
    chapter_title: str,
    draft_text: str,
) -> dict[str, Any]:
    response = await _request_with_retry(
        client,
        "PUT",
        f"/projects/{project_id}/story-engine/cloud-drafts/current",
        headers=_build_headers(token),
        json={
            "branch_id": branch_id,
            "volume_id": volume_id,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "draft_text": draft_text,
            "outline_id": None,
            "source_chapter_id": None,
            "source_version_number": None,
        },
    )
    response.raise_for_status()
    return response.json()


async def _list_cloud_drafts(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
) -> list[dict[str, Any]]:
    response = await _request_with_retry(
        client,
        "GET",
        f"/projects/{project_id}/story-engine/cloud-drafts",
        headers=_build_headers(token),
    )
    response.raise_for_status()
    return response.json()


async def _get_cloud_draft_detail(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    draft_snapshot_id: str,
) -> dict[str, Any] | None:
    response = await _request_with_retry(
        client,
        "GET",
        f"/projects/{project_id}/story-engine/cloud-drafts/{draft_snapshot_id}",
        headers=_build_headers(token),
    )
    response.raise_for_status()
    return response.json()


async def _delete_cloud_draft(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    draft_snapshot_id: str,
) -> None:
    response = await _request_with_retry(
        client,
        "DELETE",
        f"/projects/{project_id}/story-engine/cloud-drafts/{draft_snapshot_id}",
        headers=_build_headers(token),
    )
    response.raise_for_status()


async def _run_mainline_scenario(
    client: httpx.AsyncClient,
    *,
    token: str,
    suffix: str,
    workflow_read_timeout: float,
    stream_timeout: float,
    skip_final: bool,
) -> dict[str, Any]:
    _print_step("mainline: 创建项目")
    project = await _create_project(client, token=token, suffix=f"{suffix}-mainline")
    project_id = str(project["id"])
    structure = await _load_structure(client, project_id=project_id, token=token)
    default_branch_id = structure.get("default_branch_id")
    default_volume_id = structure.get("default_volume_id")

    _print_step("mainline: 生成三级大纲")
    outline_result = await _run_outline_stress(
        client,
        project_id=project_id,
        token=token,
        workflow_read_timeout=workflow_read_timeout,
    )
    level_3_outlines = sorted(
        list(outline_result.get("editable_level_3_outlines") or []),
        key=lambda item: int(item.get("node_order") or 1),
    )
    current_outline = level_3_outlines[0] if level_3_outlines else None

    _print_step("mainline: 触发实时守护")
    guard_result = await _run_realtime_guard(
        client,
        project_id=project_id,
        token=token,
        outline_id=current_outline.get("outline_id") if current_outline else None,
        current_outline=current_outline.get("content") if current_outline else None,
    )

    _print_step("mainline: 生成正文")
    stream_result = await _run_stream_generation(
        client,
        project_id=project_id,
        token=token,
        outline_id=current_outline.get("outline_id") if current_outline else None,
        current_outline=current_outline.get("content") if current_outline else None,
        stream_timeout=stream_timeout,
    )

    _print_step("mainline: 落正式章节")
    created_chapter = await _create_chapter(
        client,
        project_id=project_id,
        token=token,
        branch_id=str(default_branch_id) if default_branch_id else None,
        volume_id=str(default_volume_id) if default_volume_id else None,
        chapter_number=1,
        title=str(current_outline.get("title") or "第一章：开局吃亏") if current_outline else "第一章：开局吃亏",
        content=str(stream_result.get("draft_text") or ""),
        outline=current_outline,
    )

    final_result: dict[str, Any] | None = None
    resolved_suggestion: dict[str, Any] | None = None
    chapter_after_finalize = created_chapter
    next_chapter = {}

    if not skip_final:
        _print_step("mainline: 终稿收口")
        final_result = await _run_final_optimize(
            client,
            project_id=project_id,
            token=token,
            chapter_id=str(created_chapter["id"]),
            draft_text=str(stream_result.get("draft_text") or ""),
            workflow_read_timeout=workflow_read_timeout,
        )
        if str(final_result.get("final_draft") or "").strip():
            chapter_after_finalize = await _update_chapter_content(
                client,
                chapter_id=str(created_chapter["id"]),
                token=token,
                content=str(final_result["final_draft"]),
            )
        resolved_suggestion = await _resolve_first_kb_suggestion(
            client,
            project_id=project_id,
            token=token,
            chapter_summary=dict(final_result.get("chapter_summary") or {}),
            kb_update_list=list(final_result.get("kb_update_list") or []),
        )

        _print_step("mainline: 标记终稿并读取下一章")
        chapter_after_finalize = await _mark_chapter_final(
            client,
            chapter_id=str(created_chapter["id"]),
            token=token,
        )
        bootstrap_state = await _load_bootstrap(client, project_id=project_id, token=token)
        next_chapter = dict(bootstrap_state.get("next_chapter") or {})
    else:
        bootstrap_state = await _load_bootstrap(client, project_id=project_id, token=token)
        next_chapter = dict(bootstrap_state.get("next_chapter") or {})

    summary = {
        "scenario": SCENARIO_MAINLINE,
        "project_id": project_id,
        "outline": {
            "level_1_count": len(outline_result.get("locked_level_1_outlines") or []),
            "level_2_count": len(outline_result.get("editable_level_2_outlines") or []),
            "level_3_count": len(level_3_outlines),
            "risk_count": len(outline_result.get("risk_report") or []),
            "workflow_event_count": len(outline_result.get("workflow_timeline") or []),
        },
        "guard": {
            "passed": guard_result.get("passed"),
            "should_pause": guard_result.get("should_pause"),
            "alert_count": len(guard_result.get("alerts") or []),
            "repair_option_count": len(guard_result.get("repair_options") or []),
        },
        "stream": {
            "elapsed_seconds": stream_result.get("elapsed_seconds"),
            "event_count": stream_result.get("event_count"),
            "final_event": stream_result.get("final_event"),
            "draft_length": len(str(stream_result.get("draft_text") or "")),
        },
        "chapter": {
            "chapter_id": chapter_after_finalize.get("id"),
            "status": chapter_after_finalize.get("status"),
            "current_version_number": chapter_after_finalize.get("current_version_number"),
            "word_count": chapter_after_finalize.get("word_count"),
        },
        "final_optimize": (
            {
                "revision_note_count": len(final_result.get("revision_notes") or []),
                "final_draft_length": len(str(final_result.get("final_draft") or "")),
                "chapter_summary_id": (final_result.get("chapter_summary") or {}).get("summary_id"),
                "kb_update_count": len(final_result.get("kb_update_list") or []),
                "resolved_suggestion_status": (
                    (resolved_suggestion.get("resolved_suggestion") or {}).get("status")
                    if resolved_suggestion
                    else None
                ),
                "workflow_event_count": len(final_result.get("workflow_timeline") or []),
            }
            if final_result
            else None
        ),
        "next_chapter": {
            "chapter_number": next_chapter.get("chapter_number"),
            "title": next_chapter.get("title"),
            "generation_mode": next_chapter.get("generation_mode"),
        },
    }
    assert_mainline_summary(summary, expect_final=not skip_final)
    return summary


async def _run_branch_scope_scenario(
    client: httpx.AsyncClient,
    *,
    token: str,
    suffix: str,
) -> dict[str, Any]:
    _print_step("branch-scope: 创建项目")
    project = await _create_project(client, token=token, suffix=f"{suffix}-branch")
    project_id = str(project["id"])
    base_structure = await _load_structure(client, project_id=project_id, token=token)
    default_branch_id = str(base_structure.get("default_branch_id") or "")

    _print_step("branch-scope: 创建分线")
    branch_structure = await _create_branch(
        client,
        project_id=project_id,
        token=token,
        title="黑化线",
    )
    new_branch = next(
        (item for item in branch_structure.get("branches") or [] if item.get("title") == "黑化线"),
        None,
    )
    _ensure(new_branch is not None, "烟雾测试分线未出现在结构返回里。")
    new_branch_id = str(new_branch["id"])

    _print_step("branch-scope: 创建分卷")
    volume_structure = await _create_volume(
        client,
        project_id=project_id,
        token=token,
        title="支线卷",
    )
    new_volume = next(
        (item for item in volume_structure.get("volumes") or [] if item.get("title") == "支线卷"),
        None,
    )
    _ensure(new_volume is not None, "烟雾测试分卷未出现在结构返回里。")
    new_volume_id = str(new_volume["id"])

    _print_step("branch-scope: 创建支线章节")
    await _create_chapter(
        client,
        project_id=project_id,
        token=token,
        branch_id=new_branch_id,
        volume_id=new_volume_id,
        chapter_number=7,
        title="第七章：支线试写",
        content="这是黑化线里的专属章节，用来验证分线章节不会串回默认主线。",
        outline=None,
    )

    _print_step("branch-scope: 写入支线设定")
    await _upsert_story_bible_branch_location(
        client,
        project_id=project_id,
        token=token,
        branch_id=new_branch_id,
        location_name=FIXED_BRANCH_LOCATION_NAME,
    )

    branch_bible = await _load_story_bible(
        client,
        project_id=project_id,
        token=token,
        branch_id=new_branch_id,
    )
    default_bible = await _load_story_bible(client, project_id=project_id, token=token)
    branch_chapters = await _list_chapters(
        client,
        project_id=project_id,
        token=token,
        branch_id=new_branch_id,
        volume_id=new_volume_id,
    )
    default_chapters = await _list_chapters(
        client,
        project_id=project_id,
        token=token,
        branch_id=default_branch_id or None,
    )

    summary = {
        "scenario": SCENARIO_BRANCH_SCOPE,
        "project_id": project_id,
        "default_branch_id": default_branch_id,
        "new_branch_id": new_branch_id,
        "new_volume_id": new_volume_id,
        "branch_chapter_numbers": [item.get("chapter_number") for item in branch_chapters],
        "default_chapter_numbers": [item.get("chapter_number") for item in default_chapters],
        "branch_location_names": [
            str(item.get("name") or "")
            for item in branch_bible.get("locations") or []
        ],
        "default_location_names": [
            str(item.get("name") or "")
            for item in default_bible.get("locations") or []
        ],
    }
    assert_branch_scope_summary(summary)
    return summary


async def _run_cloud_draft_scenario(
    client: httpx.AsyncClient,
    *,
    token: str,
    suffix: str,
) -> dict[str, Any]:
    _print_step("cloud-draft: 创建项目")
    project = await _create_project(client, token=token, suffix=f"{suffix}-cloud")
    project_id = str(project["id"])
    structure = await _load_structure(client, project_id=project_id, token=token)
    default_branch_id = structure.get("default_branch_id")
    default_volume_id = structure.get("default_volume_id")

    _print_step("cloud-draft: 写入云端续写稿")
    created_draft = await _upsert_cloud_draft(
        client,
        project_id=project_id,
        token=token,
        branch_id=str(default_branch_id) if default_branch_id else None,
        volume_id=str(default_volume_id) if default_volume_id else None,
        chapter_number=1,
        chapter_title="第一章：云端续写",
        draft_text="这是云端续写稿，用来验证跨设备续写的保存、读取和删除流程。",
    )
    listed_after_upsert = await _list_cloud_drafts(client, project_id=project_id, token=token)
    fetched_detail = await _get_cloud_draft_detail(
        client,
        project_id=project_id,
        token=token,
        draft_snapshot_id=str(created_draft["draft_snapshot_id"]),
    )

    _print_step("cloud-draft: 删除云端续写稿")
    await _delete_cloud_draft(
        client,
        project_id=project_id,
        token=token,
        draft_snapshot_id=str(created_draft["draft_snapshot_id"]),
    )
    listed_after_delete = await _list_cloud_drafts(client, project_id=project_id, token=token)

    summary = {
        "scenario": SCENARIO_CLOUD_DRAFT,
        "project_id": project_id,
        "draft_snapshot_id": created_draft.get("draft_snapshot_id"),
        "listed_count_after_upsert": len(listed_after_upsert),
        "detail_matches": (
            str((fetched_detail or {}).get("draft_text") or "") == str(created_draft.get("draft_text") or "")
        ),
        "deleted": True,
        "deleted_absent_from_list": all(
            str(item.get("draft_snapshot_id")) != str(created_draft.get("draft_snapshot_id"))
            for item in listed_after_delete
        ),
    }
    assert_cloud_draft_summary(summary)
    return summary


async def _run_selected_scenarios(
    *,
    base_url: str,
    password: str,
    scenario: str,
    email_prefix: str,
    workflow_read_timeout: float,
    stream_timeout: float,
    skip_final: bool,
) -> dict[str, Any]:
    selected_scenarios = resolve_selected_scenarios(scenario)
    email = build_smoke_email(email_prefix)
    timeout = httpx.Timeout(connect=20.0, read=240.0, write=60.0, pool=60.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        _print_step(f"准备注册测试账号: {email}")
        auth_payload = await _register_and_login(client, email=email, password=password)
        token = str(auth_payload["access_token"])
        suffix = datetime.now().strftime("%H%M%S")

        results: dict[str, Any] = {}
        if SCENARIO_MAINLINE in selected_scenarios:
            results[SCENARIO_MAINLINE] = await _run_mainline_scenario(
                client,
                token=token,
                suffix=suffix,
                workflow_read_timeout=workflow_read_timeout,
                stream_timeout=stream_timeout,
                skip_final=skip_final,
            )
        if SCENARIO_BRANCH_SCOPE in selected_scenarios:
            results[SCENARIO_BRANCH_SCOPE] = await _run_branch_scope_scenario(
                client,
                token=token,
                suffix=suffix,
            )
        if SCENARIO_CLOUD_DRAFT in selected_scenarios:
            results[SCENARIO_CLOUD_DRAFT] = await _run_cloud_draft_scenario(
                client,
                token=token,
                suffix=suffix,
            )

    return {
        "base_url": base_url,
        "scenario": scenario,
        "account_email": email,
        "results": results,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Story Engine 主链 live smoke 脚本。",
    )
    parser.add_argument(
        "--scenario",
        default=SCENARIO_ALL,
        choices=SCENARIO_CHOICES,
        help="要执行的 smoke 场景。",
    )
    parser.add_argument(
        "--skip-final",
        action="store_true",
        help="跳过 mainline 场景里的终稿收口。",
    )
    parser.add_argument(
        "--email-prefix",
        default=None,
        help="测试账号邮箱前缀；默认读取 STORY_ENGINE_SMOKE_EMAIL_PREFIX，未设置时回退到固定前缀。",
    )
    parser.add_argument(
        "--summary-file",
        default=None,
        help="可选：把 smoke 总结结果写入指定 JSON 文件。",
    )
    return parser


async def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    base_url = os.getenv("STORY_ENGINE_SMOKE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    password = os.getenv("STORY_ENGINE_SMOKE_PASSWORD", DEFAULT_PASSWORD)
    workflow_read_timeout = float(
        os.getenv("STORY_ENGINE_SMOKE_WORKFLOW_READ_TIMEOUT", str(DEFAULT_WORKFLOW_READ_TIMEOUT))
    )
    stream_timeout = float(
        os.getenv("STORY_ENGINE_SMOKE_STREAM_TIMEOUT", str(DEFAULT_STREAM_TIMEOUT))
    )
    email_prefix = (
        args.email_prefix
        or os.getenv("STORY_ENGINE_SMOKE_EMAIL_PREFIX")
        or DEFAULT_EMAIL_PREFIX
    )
    skip_final = args.skip_final or os.getenv("STORY_ENGINE_SMOKE_SKIP_FINAL", "").lower() in {
        "1",
        "true",
        "yes",
    }

    summary = await _run_selected_scenarios(
        base_url=base_url,
        password=password,
        scenario=args.scenario,
        email_prefix=email_prefix,
        workflow_read_timeout=workflow_read_timeout,
        stream_timeout=stream_timeout,
        skip_final=skip_final,
    )
    write_summary_file(summary, args.summary_file)

    print("\n===== Story Engine Live Smoke Summary =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except httpx.HTTPStatusError as exc:
        print(f"HTTP 错误: {exc.response.status_code} {exc.response.text[:500]}", file=sys.stderr)
        raise SystemExit(1)
    except SmokeAssertionError as exc:
        print(f"断言失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:  # pragma: no cover - 运行期诊断脚本
        print(
            f"执行失败: {type(exc).__name__} {repr(exc)}",
            file=sys.stderr,
        )
        raise SystemExit(1)
