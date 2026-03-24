from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8010/api/v1"
DEFAULT_PASSWORD = "StoryEngineSmoke123"


def _build_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _build_email() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"story-engine-smoke-{timestamp}@example.com"


async def _register_and_login(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, Any]:
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    return response.json()


async def _create_project(
    client: httpx.AsyncClient,
    *,
    token: str,
) -> dict[str, Any]:
    response = await client.post(
        "/projects",
        headers=_build_headers(token),
        json={
            "title": f"联调烟雾测试项目-{datetime.now().strftime('%H%M%S')}",
            "genre": "玄幻",
            "theme": "代价与成长",
            "tone": "热血压迫感",
            "status": "draft",
        },
    )
    response.raise_for_status()
    return response.json()


async def _bulk_import_template(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
) -> dict[str, Any]:
    response = await client.post(
        f"/projects/{project_id}/story-engine/imports/bulk",
        headers=_build_headers(token),
        json={
            "template_key": "xuanhuan_upgrade",
            "replace_existing_sections": [],
        },
    )
    response.raise_for_status()
    return response.json()


async def _load_workspace(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
) -> dict[str, Any]:
    response = await client.get(
        f"/projects/{project_id}/story-engine/workspace",
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
    # 这里故意塞入模板里负面清单中的关键词，验证硬规则与实时仲裁都能被触发。
    draft_text = (
        "主角眼前一黑，下一瞬却毫无代价开挂，硬生生把本不可能赢的局面翻了过来。"
        "大战后秒恢复，连半点反噬都没有，仿佛之前所有代价规则都只是摆设。"
    )
    response = await client.post(
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
) -> dict[str, Any]:
    payload = {
        "chapter_number": 1,
        "chapter_title": "第一章：开局吃亏",
        "outline_id": outline_id,
        "current_outline": current_outline,
        "recent_chapters": [],
        "existing_text": "",
        "style_sample": (
            "夜风压着屋檐往下坠，街面上连一盏敢亮到最后的灯都没有。"
            "他把手按在门框上，指节因为太用力而发白，却还是没让自己退半步。"
        ),
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
    }


async def _run_final_optimize(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    token: str,
    draft_text: str,
) -> dict[str, Any]:
    response = await client.post(
        f"/projects/{project_id}/story-engine/workflows/final-optimize",
        headers=_build_headers(token),
        json={
            "chapter_number": 1,
            "chapter_title": "第一章：开局吃亏",
            "draft_text": draft_text,
            "style_sample": (
                "风压一寸寸落下来，像有人把整条街的呼吸都按进了泥里。"
                "他没说话，只把肩膀往前送了半步，像是要替自己把退路堵死。"
            ),
        },
    )
    response.raise_for_status()
    return response.json()


async def main() -> int:
    base_url = os.getenv("STORY_ENGINE_SMOKE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    password = os.getenv("STORY_ENGINE_SMOKE_PASSWORD", DEFAULT_PASSWORD)
    skip_final = os.getenv("STORY_ENGINE_SMOKE_SKIP_FINAL", "").lower() in {"1", "true", "yes"}
    email = _build_email()

    timeout = httpx.Timeout(connect=20.0, read=240.0, write=60.0, pool=60.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        print(f"[1/6] 准备注册测试账号: {email}")
        auth_payload = await _register_and_login(client, email=email, password=password)
        token = str(auth_payload["access_token"])

        print("[2/6] 创建测试项目")
        project = await _create_project(client, token=token)
        project_id = str(project["id"])

        print("[3/6] 导入玄幻升级流模板")
        import_result = await _bulk_import_template(client, project_id=project_id, token=token)

        print("[4/6] 拉取工作区并定位章纲")
        workspace = await _load_workspace(client, project_id=project_id, token=token)
        level_3_outlines = [item for item in workspace.get("outlines", []) if item.get("level") == "level_3"]
        current_outline = level_3_outlines[0] if level_3_outlines else None

        print("[5/6] 执行实时守护烟雾测试")
        guard_result = await _run_realtime_guard(
            client,
            project_id=project_id,
            token=token,
            outline_id=current_outline.get("outline_id") if current_outline else None,
            current_outline=current_outline.get("content") if current_outline else None,
        )

        print("[6/6] 执行流式章节生成烟雾测试")
        stream_result = await _run_stream_generation(
            client,
            project_id=project_id,
            token=token,
            outline_id=current_outline.get("outline_id") if current_outline else None,
            current_outline=current_outline.get("content") if current_outline else None,
        )

        final_result: dict[str, Any] | None = None
        if not skip_final and stream_result.get("draft_text"):
            print("[7/7] 执行终稿优化烟雾测试")
            final_result = await _run_final_optimize(
                client,
                project_id=project_id,
                token=token,
                draft_text=str(stream_result["draft_text"]),
            )

    summary = {
        "base_url": base_url,
        "project_id": project_id,
        "imported_counts": import_result.get("imported_counts"),
        "guard": {
            "passed": guard_result.get("passed"),
            "should_pause": guard_result.get("should_pause"),
            "alert_count": len(guard_result.get("alerts") or []),
            "first_alert": (guard_result.get("alerts") or [None])[0],
            "repair_options": guard_result.get("repair_options") or [],
        },
        "stream": {
            "elapsed_seconds": stream_result.get("elapsed_seconds"),
            "event_count": stream_result.get("event_count"),
            "final_event": stream_result.get("final_event"),
            "draft_length": len(stream_result.get("draft_text") or ""),
        },
        "final_optimize": (
            {
                "revision_note_count": len(final_result.get("revision_notes") or []),
                "final_draft_length": len(final_result.get("final_draft") or ""),
                "summary_excerpt": str((final_result.get("chapter_summary") or {}).get("content") or "")[:120],
            }
            if final_result
            else None
        ),
    }
    print("\n===== Story Engine Live Smoke Summary =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except httpx.HTTPStatusError as exc:
        print(f"HTTP 错误: {exc.response.status_code} {exc.response.text[:500]}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:  # pragma: no cover - 运行期诊断脚本
        print(f"执行失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
