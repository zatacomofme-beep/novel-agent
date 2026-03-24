from __future__ import annotations

from typing import Any, Optional


TRUTH_LAYER_STATUS_HEALTHY = "healthy"
TRUTH_LAYER_STATUS_DEGRADED = "degraded"
TRUTH_LAYER_STATUS_BLOCKED = "blocked"
STORY_BIBLE_SOURCE = "story_bible_integrity"
CANON_SOURCE = "canon"
ACTION_SCOPE_STORY_BIBLE = "story_bible"
ACTION_SCOPE_CHAPTER_CONTENT = "chapter_content"


def build_truth_layer_context(
    *,
    integrity_report: Optional[dict[str, Any]] = None,
    canon_report: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    integrity = _build_report_section(
        report=integrity_report,
        source=STORY_BIBLE_SOURCE,
        action_scope=ACTION_SCOPE_STORY_BIBLE,
    )
    canon = _build_report_section(
        report=canon_report,
        source=CANON_SOURCE,
        action_scope=ACTION_SCOPE_CHAPTER_CONTENT,
        include_referenced_entities=True,
    )

    blocking_sources: list[str] = []
    if integrity["blocking_issue_count"] > 0:
        blocking_sources.append(STORY_BIBLE_SOURCE)
    if canon["blocking_issue_count"] > 0:
        blocking_sources.append(CANON_SOURCE)

    total_issue_count = int(integrity["issue_count"]) + int(canon["issue_count"])
    total_blocking_issue_count = int(integrity["blocking_issue_count"]) + int(
        canon["blocking_issue_count"]
    )
    status = _resolve_truth_layer_status(
        total_issue_count=total_issue_count,
        total_blocking_issue_count=total_blocking_issue_count,
    )

    priority_findings = sorted(
        [*integrity["top_issues"], *canon["top_issues"]],
        key=_finding_sort_key,
    )[:6]
    chapter_revision_targets = [
        finding
        for finding in priority_findings
        if finding.get("action_scope") == ACTION_SCOPE_CHAPTER_CONTENT
    ]
    story_bible_followups = [
        finding
        for finding in priority_findings
        if finding.get("action_scope") == ACTION_SCOPE_STORY_BIBLE
    ]

    return {
        "status": status,
        "blocking": bool(blocking_sources),
        "blocking_sources": blocking_sources,
        "total_issue_count": total_issue_count,
        "total_blocking_issue_count": total_blocking_issue_count,
        "summary": _build_truth_layer_summary(
            status=status,
            blocking_sources=blocking_sources,
            integrity_summary=integrity.get("summary"),
            canon_summary=canon.get("summary"),
        ),
        "blocking_policy": {
            "generation_preflight_blocks_on_story_bible_integrity": True,
            "final_gate_blocks_on_story_bible_integrity": True,
            "final_gate_blocks_on_canon": True,
        },
        "integrity": integrity,
        "canon": canon,
        "priority_findings": priority_findings,
        "chapter_revision_targets": chapter_revision_targets,
        "story_bible_followups": story_bible_followups,
    }


def _build_report_section(
    *,
    report: Optional[dict[str, Any]],
    source: str,
    action_scope: str,
    include_referenced_entities: bool = False,
) -> dict[str, Any]:
    payload = report if isinstance(report, dict) else {}
    top_issues = [
        _project_issue(
            issue=item,
            source=source,
            action_scope=action_scope,
        )
        for item in payload.get("issues", [])
        if isinstance(item, dict)
    ]
    top_issues = sorted(top_issues, key=_finding_sort_key)[:4]

    referenced_entities: list[dict[str, Any]] = []
    if include_referenced_entities:
        referenced_entities = [
            {
                "plugin_key": item.get("plugin_key"),
                "entity_type": item.get("entity_type"),
                "entity_id": item.get("entity_id"),
                "label": item.get("label"),
            }
            for item in payload.get("referenced_entities", [])
            if isinstance(item, dict)
        ][:8]

    plugin_breakdown = payload.get("plugin_breakdown")
    return {
        "source": source,
        "issue_count": _safe_int(payload.get("issue_count")),
        "blocking_issue_count": _safe_int(payload.get("blocking_issue_count")),
        "summary": payload.get("summary") if isinstance(payload.get("summary"), str) else None,
        "plugin_breakdown": plugin_breakdown if isinstance(plugin_breakdown, dict) else {},
        "top_issues": top_issues,
        "referenced_entities": referenced_entities,
    }


def _project_issue(
    *,
    issue: dict[str, Any],
    source: str,
    action_scope: str,
) -> dict[str, Any]:
    entity_labels = [
        str(item.get("label"))
        for item in issue.get("entity_refs", [])
        if isinstance(item, dict) and item.get("label") is not None
    ]
    return {
        "source": source,
        "action_scope": action_scope,
        "plugin_key": issue.get("plugin_key"),
        "code": issue.get("code"),
        "dimension": issue.get("dimension"),
        "severity": issue.get("severity") or "medium",
        "blocking": bool(issue.get("blocking")),
        "message": issue.get("message") or "",
        "fix_hint": issue.get("fix_hint"),
        "evidence_text": issue.get("evidence_text"),
        "entity_labels": entity_labels,
    }


def _resolve_truth_layer_status(
    *,
    total_issue_count: int,
    total_blocking_issue_count: int,
) -> str:
    if total_blocking_issue_count > 0:
        return TRUTH_LAYER_STATUS_BLOCKED
    if total_issue_count > 0:
        return TRUTH_LAYER_STATUS_DEGRADED
    return TRUTH_LAYER_STATUS_HEALTHY


def _build_truth_layer_summary(
    *,
    status: str,
    blocking_sources: list[str],
    integrity_summary: Optional[str],
    canon_summary: Optional[str],
) -> str:
    if status == TRUTH_LAYER_STATUS_BLOCKED:
        joined_sources = ", ".join(blocking_sources) if blocking_sources else "truth layer"
        base = f"Truth layer is blocked by: {joined_sources}."
    elif status == TRUTH_LAYER_STATUS_DEGRADED:
        base = "Truth layer has non-blocking continuity warnings."
    else:
        base = "Truth layer is healthy for this round."

    detail_parts = [
        part
        for part in (integrity_summary, canon_summary)
        if isinstance(part, str) and part.strip()
    ]
    if detail_parts:
        return f"{base} {' '.join(detail_parts)}"
    return base


def _finding_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    severity = str(item.get("severity") or "medium")
    severity_rank = {"high": 0, "medium": 1, "low": 2}.get(severity, 3)
    return (
        0 if bool(item.get("blocking")) else 1,
        severity_rank,
        str(item.get("dimension") or item.get("code") or ""),
    )


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 0
