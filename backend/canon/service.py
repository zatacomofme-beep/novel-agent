from __future__ import annotations

from collections import Counter
from typing import Any
from typing import Optional
from typing import Union

from canon.base import (
    CanonEntity,
    CanonIntegrityReport,
    CanonIssue,
    CanonPluginRegistry,
    CanonSnapshot,
    CanonValidationReport,
    entity_ref,
    normalize_alias,
)
from canon.plugins import canon_plugin_registry
from memory.story_bible import StoryBibleContext


def compile_story_canon_snapshot(
    story_bible: StoryBibleContext,
    *,
    chapter_number: int = 0,
    chapter_title: str | None = None,
    registry: CanonPluginRegistry | None = None,
) -> CanonSnapshot:
    plugin_registry = registry or canon_plugin_registry
    return plugin_registry.compile_snapshot(
        story_bible,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
    )


def build_canon_snapshot_payload(
    story_bible: StoryBibleContext,
    *,
    chapter_number: int = 0,
    chapter_title: str | None = None,
    registry: CanonPluginRegistry | None = None,
) -> dict[str, Any]:
    plugin_registry = registry or canon_plugin_registry
    snapshot = compile_story_canon_snapshot(
        story_bible,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        registry=plugin_registry,
    )
    plugin_snapshots: list[dict[str, Any]] = []
    total_entity_count = 0
    for plugin in plugin_registry.plugins:
        entities = sorted(
            snapshot.get_entities(plugin.key),
            key=_entity_sort_key,
        )
        total_entity_count += len(entities)
        plugin_snapshots.append(
            {
                "plugin_key": plugin.key,
                "entity_type": plugin.entity_type,
                "entity_count": len(entities),
                "entities": [_serialize_canon_entity(entity) for entity in entities],
            }
        )
    return {
        "plugin_snapshots": plugin_snapshots,
        "total_entity_count": total_entity_count,
        "integrity_report": validate_story_bible_integrity(
            story_bible,
            registry=plugin_registry,
        ).model_dump(mode="json"),
    }


def validate_story_canon(
    story_bible: StoryBibleContext,
    *,
    content: str,
    chapter_number: int,
    chapter_title: str | None,
    registry: CanonPluginRegistry | None = None,
) -> CanonValidationReport:
    plugin_registry = registry or canon_plugin_registry
    snapshot = plugin_registry.compile_snapshot(
        story_bible,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
    )
    issues: list[CanonIssue] = []
    for plugin in plugin_registry.plugins:
        issues.extend(plugin.validate(snapshot, content))

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    issues.sort(
        key=lambda issue: (
            0 if issue.blocking else 1,
            severity_rank.get(issue.severity, 3),
            issue.plugin_key,
            issue.code,
        )
    )
    blocking_issue_count = sum(1 for issue in issues if issue.blocking)
    plugin_breakdown = Counter(issue.plugin_key for issue in issues)
    referenced_entities = [entity_ref(entity) for entity in snapshot.mentioned_entities(content)]
    summary = _build_summary(
        issue_count=len(issues),
        blocking_issue_count=blocking_issue_count,
        plugin_breakdown=plugin_breakdown,
    )
    return CanonValidationReport(
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        issue_count=len(issues),
        blocking_issue_count=blocking_issue_count,
        plugin_breakdown=dict(plugin_breakdown),
        referenced_entities=referenced_entities,
        issues=issues,
        summary=summary,
    )


def validate_story_bible_integrity(
    story_bible: StoryBibleContext,
    *,
    registry: CanonPluginRegistry | None = None,
) -> CanonIntegrityReport:
    plugin_registry = registry or canon_plugin_registry
    snapshot = plugin_registry.compile_snapshot(
        story_bible,
        chapter_number=0,
        chapter_title=None,
    )
    issues: list[CanonIssue] = []
    for plugin in plugin_registry.plugins:
        validator = getattr(plugin, "validate_snapshot", None)
        if callable(validator):
            issues.extend(validator(snapshot))
    issues.extend(_build_alias_conflict_issues(snapshot))

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    issues.sort(
        key=lambda issue: (
            0 if issue.blocking else 1,
            severity_rank.get(issue.severity, 3),
            issue.plugin_key,
            issue.code,
        )
    )
    blocking_issue_count = sum(1 for issue in issues if issue.blocking)
    plugin_breakdown = Counter(issue.plugin_key for issue in issues)
    return CanonIntegrityReport(
        issue_count=len(issues),
        blocking_issue_count=blocking_issue_count,
        plugin_breakdown=dict(plugin_breakdown),
        issues=issues,
        summary=_build_integrity_summary(
            issue_count=len(issues),
            blocking_issue_count=blocking_issue_count,
            plugin_breakdown=plugin_breakdown,
        ),
    )


def _serialize_canon_entity(entity: CanonEntity) -> dict[str, Any]:
    return {
        "plugin_key": entity.plugin_key,
        "entity_type": entity.entity_type,
        "entity_id": entity.entity_id,
        "label": entity.label,
        "aliases": sorted(entity.aliases),
        "data": dict(entity.data),
        "source_payload": dict(entity.source_payload),
    }


def _entity_sort_key(entity: CanonEntity) -> tuple[str, str, str]:
    return (
        str(entity.label or ""),
        str(entity.entity_id or ""),
        str(entity.entity_type or ""),
    )


def extract_canon_issue_payloads(
    report: Optional[Union[CanonValidationReport, dict[str, Any]]],
) -> list[dict[str, Any]]:
    if isinstance(report, CanonValidationReport):
        return [issue.model_dump(mode="json") for issue in report.issues]
    if not isinstance(report, dict):
        return []
    issues = report.get("issues")
    if not isinstance(issues, list):
        return []
    return [issue for issue in issues if isinstance(issue, dict)]


def count_blocking_canon_issues(issue_payloads: list[dict[str, Any]]) -> int:
    return sum(1 for issue in issue_payloads if bool(issue.get("blocking")))


def calculate_canon_penalty(issue_payloads: list[dict[str, Any]]) -> float:
    penalty = 0.0
    for issue in issue_payloads:
        if bool(issue.get("blocking")):
            penalty += 0.08
            continue
        severity = str(issue.get("severity") or "medium")
        if severity == "high":
            penalty += 0.05
        elif severity == "medium":
            penalty += 0.03
        else:
            penalty += 0.015
    return min(0.32, penalty)


def _build_summary(
    *,
    issue_count: int,
    blocking_issue_count: int,
    plugin_breakdown: Counter[str],
) -> str:
    if issue_count == 0:
        return "Canon 校验通过，当前章节没有发现连续性或规范事实层面的明显冲突。"

    dominant = ", ".join(
        f"{plugin_key}:{count}"
        for plugin_key, count in plugin_breakdown.most_common(3)
    )
    if blocking_issue_count > 0:
        return (
            f"Canon 校验发现 {issue_count} 个问题，其中 {blocking_issue_count} 个会阻断后续修订判断。"
            f" 主要集中在 {dominant}。"
        )
    return (
        f"Canon 校验发现 {issue_count} 个非阻断问题。"
        f" 主要集中在 {dominant}。"
    )


def _build_integrity_summary(
    *,
    issue_count: int,
    blocking_issue_count: int,
    plugin_breakdown: Counter[str],
) -> str:
    if issue_count == 0:
        return "Story Bible 规范层结构自洽，当前没有发现坏引用、坏时序或实体身份冲突。"

    dominant = ", ".join(
        f"{plugin_key}:{count}"
        for plugin_key, count in plugin_breakdown.most_common(3)
    )
    if blocking_issue_count > 0:
        return (
            f"Story Bible 自校验发现 {issue_count} 个问题，其中 {blocking_issue_count} 个会破坏规范真相层。"
            f" 主要集中在 {dominant}。"
        )
    return (
        f"Story Bible 自校验发现 {issue_count} 个非阻断问题。"
        f" 主要集中在 {dominant}。"
    )


def _build_alias_conflict_issues(snapshot: CanonSnapshot) -> list[CanonIssue]:
    issues: list[CanonIssue] = []
    for plugin_key, entities in snapshot.entities_by_plugin.items():
        alias_buckets: dict[str, list[CanonEntity]] = {}
        for entity in entities:
            for alias in entity.aliases:
                normalized = normalize_alias(alias)
                if not normalized:
                    continue
                bucket = alias_buckets.setdefault(normalized, [])
                if entity not in bucket:
                    bucket.append(entity)

        for normalized_alias, matched_entities in alias_buckets.items():
            unique_entities = {
                (entity.plugin_key, entity.entity_id): entity
                for entity in matched_entities
            }
            if len(unique_entities) < 2:
                continue
            entities_for_issue = list(unique_entities.values())
            labels = "、".join(entity.label for entity in entities_for_issue[:4])
            issues.append(
                CanonIssue(
                    plugin_key=plugin_key,
                    code="entity.alias_conflict",
                    dimension="canon.entity_identity",
                    severity="medium",
                    blocking=False,
                    message=(
                        f"同一类规范实体共享别名“{normalized_alias}”，后续文本匹配可能出现歧义。"
                    ),
                    expected="同类实体的核心名字/别名尽量保持唯一。",
                    actual=labels,
                    fix_hint="为实体补充更可区分的别名，或移除重复别名。",
                    entity_refs=[entity_ref(entity) for entity in entities_for_issue],
                    metadata={"alias": normalized_alias},
                )
            )
    return issues
