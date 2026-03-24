from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Iterable, Optional

from schemas.quality import ChapterQualityMetricsSnapshot


CHECKPOINT_STATUS_PENDING = "pending"
CHECKPOINT_STATUS_APPROVED = "approved"
CHECKPOINT_STATUS_REJECTED = "rejected"
CHECKPOINT_STATUS_CANCELLED = "cancelled"
REVIEW_VERDICT_APPROVED = "approved"
REVIEW_VERDICT_CHANGES_REQUESTED = "changes_requested"
REVIEW_VERDICT_BLOCKED = "blocked"
FINAL_GATE_STATUS_READY = "ready"
FINAL_GATE_STATUS_BLOCKED_PENDING = "blocked_pending"
FINAL_GATE_STATUS_BLOCKED_REJECTED = "blocked_rejected"
FINAL_GATE_STATUS_BLOCKED_CHECKPOINT = "blocked_checkpoint"
FINAL_GATE_STATUS_BLOCKED_REVIEW = "blocked_review"
FINAL_GATE_STATUS_BLOCKED_EVALUATION = "blocked_evaluation"
FINAL_GATE_STATUS_BLOCKED_INTEGRITY = "blocked_integrity"
FINAL_GATE_STATUS_BLOCKED_CANON = "blocked_canon"
CHAPTER_STATUS_FINAL = "final"
CHAPTER_STATUS_REVIEW = "review"
QUALITY_METRICS_EVALUATION_STATUS_FRESH = "fresh"
QUALITY_METRICS_EVALUATION_STATUS_STALE = "stale"
QUALITY_METRICS_EVALUATION_STATUS_MISSING = "missing"


@dataclass(frozen=True)
class ChapterGateSummary:
    current_version_number: int = 1
    pending_checkpoint_count: int = 0
    rejected_checkpoint_count: int = 0
    checkpoint_gate_blocked: bool = False
    checkpoint_gate_stale: bool = False
    latest_checkpoint_version_number: Optional[int] = None
    latest_checkpoint_stale_reason: Optional[str] = None
    latest_checkpoint_status: Optional[str] = None
    latest_checkpoint_title: Optional[str] = None
    latest_review_version_number: Optional[int] = None
    latest_review_verdict: Optional[str] = None
    latest_review_summary: Optional[str] = None
    review_gate_blocked: bool = False
    review_gate_stale: bool = False
    latest_review_stale_reason: Optional[str] = None
    evaluation_gate_blocked: bool = False
    latest_evaluation_status: str = QUALITY_METRICS_EVALUATION_STATUS_MISSING
    latest_evaluation_stale_reason: Optional[str] = None
    integrity_gate_blocked: bool = False
    latest_story_bible_integrity_issue_count: int = 0
    latest_story_bible_integrity_blocking_issue_count: int = 0
    latest_story_bible_integrity_summary: Optional[str] = None
    canon_gate_blocked: bool = False
    latest_canon_issue_count: int = 0
    latest_canon_blocking_issue_count: int = 0
    latest_canon_summary: Optional[str] = None
    final_ready: bool = True
    final_gate_status: str = FINAL_GATE_STATUS_READY
    final_gate_reason: Optional[str] = None


def summarize_chapter_gate(
    checkpoints: Optional[Iterable[object]],
    decisions: Optional[Iterable[object]] = None,
    *,
    quality_metrics: Optional[object] = None,
    current_version_number: Optional[int] = None,
) -> ChapterGateSummary:
    ordered_checkpoints = sorted(
        list(checkpoints or []),
        key=lambda item: (
            getattr(item, "created_at", None) is not None,
            getattr(item, "created_at", None),
        ),
        reverse=True,
    )
    ordered_decisions = sorted(
        list(decisions or []),
        key=lambda item: (
            getattr(item, "created_at", None) is not None,
            getattr(item, "created_at", None),
        ),
        reverse=True,
    )
    latest_checkpoint = ordered_checkpoints[0] if ordered_checkpoints else None
    latest_decision = ordered_decisions[0] if ordered_decisions else None
    latest_checkpoint_version_number = _object_int(
        latest_checkpoint,
        "chapter_version_number",
    )
    latest_review_version_number = _object_int(
        latest_decision,
        "chapter_version_number",
    )
    resolved_current_version_number = _resolve_current_version_number(
        current_version_number,
        latest_checkpoint_version_number=latest_checkpoint_version_number,
        latest_review_version_number=latest_review_version_number,
    )
    latest_review_verdict = getattr(latest_decision, "verdict", None)
    latest_review_summary = getattr(latest_decision, "summary", None)
    checkpoint_gate_stale = (
        latest_checkpoint_version_number is not None
        and latest_checkpoint_version_number < resolved_current_version_number
    )
    latest_checkpoint_stale_reason = (
        _build_checkpoint_stale_reason(
            current_version_number=resolved_current_version_number,
            latest_checkpoint_version_number=latest_checkpoint_version_number,
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
        )
        if checkpoint_gate_stale
        else None
    )
    review_gate_stale = (
        latest_review_version_number is not None
        and latest_review_version_number < resolved_current_version_number
    )
    latest_review_stale_reason = (
        _build_review_stale_reason(
            current_version_number=resolved_current_version_number,
            latest_review_version_number=latest_review_version_number,
            summary=latest_review_summary,
        )
        if review_gate_stale
        else None
    )
    quality_snapshot = ChapterQualityMetricsSnapshot.from_payload(quality_metrics)
    latest_evaluation_status, latest_evaluation_stale_reason = (
        resolve_quality_metrics_evaluation_status(quality_snapshot)
    )
    latest_story_bible_integrity_issue_count = (
        quality_snapshot.story_bible_integrity_issue_count
    )
    latest_story_bible_integrity_blocking_issue_count = (
        quality_snapshot.story_bible_integrity_blocking_issue_count
    )
    latest_story_bible_integrity_summary = quality_snapshot.story_bible_integrity_summary
    integrity_metric_kwargs = {
        "latest_story_bible_integrity_issue_count": latest_story_bible_integrity_issue_count,
        "latest_story_bible_integrity_blocking_issue_count": (
            latest_story_bible_integrity_blocking_issue_count
        ),
        "latest_story_bible_integrity_summary": latest_story_bible_integrity_summary,
    }
    latest_canon_issue_count = quality_snapshot.canon_issue_count
    latest_canon_blocking_issue_count = quality_snapshot.canon_blocking_issue_count
    latest_canon_summary = quality_snapshot.canon_summary
    pending_count = sum(
        1
        for item in ordered_checkpoints
        if getattr(item, "status", None) == CHECKPOINT_STATUS_PENDING
    )
    rejected_count = sum(
        1
        for item in ordered_checkpoints
        if getattr(item, "status", None) == CHECKPOINT_STATUS_REJECTED
    )

    if rejected_count > 0:
        return ChapterGateSummary(
            current_version_number=resolved_current_version_number,
            pending_checkpoint_count=pending_count,
            rejected_checkpoint_count=rejected_count,
            checkpoint_gate_blocked=True,
            checkpoint_gate_stale=checkpoint_gate_stale,
            latest_checkpoint_version_number=latest_checkpoint_version_number,
            latest_checkpoint_stale_reason=latest_checkpoint_stale_reason,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_version_number=latest_review_version_number,
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            review_gate_stale=review_gate_stale,
            latest_review_stale_reason=latest_review_stale_reason,
            latest_evaluation_status=latest_evaluation_status,
            latest_evaluation_stale_reason=latest_evaluation_stale_reason,
            **integrity_metric_kwargs,
            latest_canon_issue_count=latest_canon_issue_count,
            latest_canon_blocking_issue_count=latest_canon_blocking_issue_count,
            latest_canon_summary=latest_canon_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_REJECTED,
            final_gate_reason=_build_rejected_reason(
                rejected_count,
                latest_checkpoint_stale_reason,
            ),
        )

    if pending_count > 0:
        return ChapterGateSummary(
            current_version_number=resolved_current_version_number,
            pending_checkpoint_count=pending_count,
            rejected_checkpoint_count=rejected_count,
            checkpoint_gate_blocked=True,
            checkpoint_gate_stale=checkpoint_gate_stale,
            latest_checkpoint_version_number=latest_checkpoint_version_number,
            latest_checkpoint_stale_reason=latest_checkpoint_stale_reason,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_version_number=latest_review_version_number,
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            review_gate_stale=review_gate_stale,
            latest_review_stale_reason=latest_review_stale_reason,
            latest_evaluation_status=latest_evaluation_status,
            latest_evaluation_stale_reason=latest_evaluation_stale_reason,
            **integrity_metric_kwargs,
            latest_canon_issue_count=latest_canon_issue_count,
            latest_canon_blocking_issue_count=latest_canon_blocking_issue_count,
            latest_canon_summary=latest_canon_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_PENDING,
            final_gate_reason=_build_pending_reason(
                pending_count,
                latest_checkpoint_stale_reason,
            ),
        )

    if review_gate_stale:
        return ChapterGateSummary(
            current_version_number=resolved_current_version_number,
            pending_checkpoint_count=0,
            rejected_checkpoint_count=0,
            checkpoint_gate_stale=checkpoint_gate_stale,
            latest_checkpoint_version_number=latest_checkpoint_version_number,
            latest_checkpoint_stale_reason=latest_checkpoint_stale_reason,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_version_number=latest_review_version_number,
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            review_gate_blocked=True,
            review_gate_stale=True,
            latest_review_stale_reason=latest_review_stale_reason,
            latest_evaluation_status=latest_evaluation_status,
            latest_evaluation_stale_reason=latest_evaluation_stale_reason,
            **integrity_metric_kwargs,
            latest_canon_issue_count=latest_canon_issue_count,
            latest_canon_blocking_issue_count=latest_canon_blocking_issue_count,
            latest_canon_summary=latest_canon_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_REVIEW,
            final_gate_reason=latest_review_stale_reason,
        )

    if review_verdict_blocks_final(latest_review_verdict):
        return ChapterGateSummary(
            current_version_number=resolved_current_version_number,
            pending_checkpoint_count=0,
            rejected_checkpoint_count=0,
            checkpoint_gate_stale=checkpoint_gate_stale,
            latest_checkpoint_version_number=latest_checkpoint_version_number,
            latest_checkpoint_stale_reason=latest_checkpoint_stale_reason,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_version_number=latest_review_version_number,
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            review_gate_blocked=True,
            review_gate_stale=review_gate_stale,
            latest_review_stale_reason=latest_review_stale_reason,
            latest_evaluation_status=latest_evaluation_status,
            latest_evaluation_stale_reason=latest_evaluation_stale_reason,
            **integrity_metric_kwargs,
            latest_canon_issue_count=latest_canon_issue_count,
            latest_canon_blocking_issue_count=latest_canon_blocking_issue_count,
            latest_canon_summary=latest_canon_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_REVIEW,
            final_gate_reason=_build_review_reason(
                latest_review_verdict,
                latest_review_summary,
            ),
        )

    if checkpoint_gate_stale:
        return ChapterGateSummary(
            current_version_number=resolved_current_version_number,
            pending_checkpoint_count=0,
            rejected_checkpoint_count=0,
            checkpoint_gate_blocked=True,
            checkpoint_gate_stale=True,
            latest_checkpoint_version_number=latest_checkpoint_version_number,
            latest_checkpoint_stale_reason=latest_checkpoint_stale_reason,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_version_number=latest_review_version_number,
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            review_gate_stale=review_gate_stale,
            latest_review_stale_reason=latest_review_stale_reason,
            latest_evaluation_status=latest_evaluation_status,
            latest_evaluation_stale_reason=latest_evaluation_stale_reason,
            **integrity_metric_kwargs,
            latest_canon_issue_count=latest_canon_issue_count,
            latest_canon_blocking_issue_count=latest_canon_blocking_issue_count,
            latest_canon_summary=latest_canon_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_CHECKPOINT,
            final_gate_reason=latest_checkpoint_stale_reason,
        )

    if latest_evaluation_status != QUALITY_METRICS_EVALUATION_STATUS_FRESH:
        return ChapterGateSummary(
            current_version_number=resolved_current_version_number,
            pending_checkpoint_count=0,
            rejected_checkpoint_count=0,
            checkpoint_gate_stale=checkpoint_gate_stale,
            latest_checkpoint_version_number=latest_checkpoint_version_number,
            latest_checkpoint_stale_reason=latest_checkpoint_stale_reason,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_version_number=latest_review_version_number,
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            review_gate_stale=review_gate_stale,
            latest_review_stale_reason=latest_review_stale_reason,
            evaluation_gate_blocked=True,
            latest_evaluation_status=latest_evaluation_status,
            latest_evaluation_stale_reason=latest_evaluation_stale_reason,
            **integrity_metric_kwargs,
            latest_canon_issue_count=latest_canon_issue_count,
            latest_canon_blocking_issue_count=latest_canon_blocking_issue_count,
            latest_canon_summary=latest_canon_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_EVALUATION,
            final_gate_reason=_build_evaluation_reason(
                latest_evaluation_status,
                latest_evaluation_stale_reason,
            ),
        )

    if latest_story_bible_integrity_blocking_issue_count > 0:
        return ChapterGateSummary(
            current_version_number=resolved_current_version_number,
            pending_checkpoint_count=0,
            rejected_checkpoint_count=0,
            checkpoint_gate_stale=checkpoint_gate_stale,
            latest_checkpoint_version_number=latest_checkpoint_version_number,
            latest_checkpoint_stale_reason=latest_checkpoint_stale_reason,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_version_number=latest_review_version_number,
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            review_gate_stale=review_gate_stale,
            latest_review_stale_reason=latest_review_stale_reason,
            latest_evaluation_status=latest_evaluation_status,
            latest_evaluation_stale_reason=latest_evaluation_stale_reason,
            integrity_gate_blocked=True,
            **integrity_metric_kwargs,
            latest_canon_issue_count=latest_canon_issue_count,
            latest_canon_blocking_issue_count=latest_canon_blocking_issue_count,
            latest_canon_summary=latest_canon_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_INTEGRITY,
            final_gate_reason=_build_story_bible_integrity_reason(
                latest_story_bible_integrity_blocking_issue_count,
                latest_story_bible_integrity_summary,
            ),
        )

    if latest_canon_blocking_issue_count > 0:
        return ChapterGateSummary(
            current_version_number=resolved_current_version_number,
            pending_checkpoint_count=0,
            rejected_checkpoint_count=0,
            checkpoint_gate_stale=checkpoint_gate_stale,
            latest_checkpoint_version_number=latest_checkpoint_version_number,
            latest_checkpoint_stale_reason=latest_checkpoint_stale_reason,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_version_number=latest_review_version_number,
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            review_gate_stale=review_gate_stale,
            latest_review_stale_reason=latest_review_stale_reason,
            latest_evaluation_status=latest_evaluation_status,
            latest_evaluation_stale_reason=latest_evaluation_stale_reason,
            canon_gate_blocked=True,
            **integrity_metric_kwargs,
            latest_canon_issue_count=latest_canon_issue_count,
            latest_canon_blocking_issue_count=latest_canon_blocking_issue_count,
            latest_canon_summary=latest_canon_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_CANON,
            final_gate_reason=_build_canon_reason(
                latest_canon_blocking_issue_count,
                latest_canon_summary,
            ),
        )

    return ChapterGateSummary(
        current_version_number=resolved_current_version_number,
        pending_checkpoint_count=0,
        rejected_checkpoint_count=0,
        checkpoint_gate_stale=checkpoint_gate_stale,
        latest_checkpoint_version_number=latest_checkpoint_version_number,
        latest_checkpoint_stale_reason=latest_checkpoint_stale_reason,
        latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
        latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
        latest_review_version_number=latest_review_version_number,
        latest_review_verdict=latest_review_verdict,
        latest_review_summary=latest_review_summary,
        review_gate_stale=review_gate_stale,
        latest_review_stale_reason=latest_review_stale_reason,
        latest_evaluation_status=latest_evaluation_status,
        latest_evaluation_stale_reason=latest_evaluation_stale_reason,
        **integrity_metric_kwargs,
        latest_canon_issue_count=latest_canon_issue_count,
        latest_canon_blocking_issue_count=latest_canon_blocking_issue_count,
        latest_canon_summary=latest_canon_summary,
        final_ready=True,
        final_gate_status=FINAL_GATE_STATUS_READY,
        final_gate_reason=(
            "All checkpoints are resolved and the latest review decision is not blocking."
            if ordered_checkpoints or ordered_decisions
            else "No checkpoint blocks final status."
        ),
    )


def apply_chapter_gate_metadata(chapter) -> ChapterGateSummary:
    summary = summarize_chapter_gate(
        getattr(chapter, "checkpoints", None),
        getattr(chapter, "review_decisions", None),
        quality_metrics=getattr(chapter, "quality_metrics", None),
        current_version_number=getattr(chapter, "current_version_number", None),
    )
    chapter.current_version_number = summary.current_version_number
    chapter.pending_checkpoint_count = summary.pending_checkpoint_count
    chapter.rejected_checkpoint_count = summary.rejected_checkpoint_count
    chapter.checkpoint_gate_blocked = summary.checkpoint_gate_blocked
    chapter.checkpoint_gate_stale = summary.checkpoint_gate_stale
    chapter.latest_checkpoint_version_number = summary.latest_checkpoint_version_number
    chapter.latest_checkpoint_stale_reason = summary.latest_checkpoint_stale_reason
    chapter.latest_checkpoint_status = summary.latest_checkpoint_status
    chapter.latest_checkpoint_title = summary.latest_checkpoint_title
    chapter.latest_review_version_number = summary.latest_review_version_number
    chapter.latest_review_verdict = summary.latest_review_verdict
    chapter.latest_review_summary = summary.latest_review_summary
    chapter.review_gate_blocked = summary.review_gate_blocked
    chapter.review_gate_stale = summary.review_gate_stale
    chapter.latest_review_stale_reason = summary.latest_review_stale_reason
    chapter.evaluation_gate_blocked = summary.evaluation_gate_blocked
    chapter.latest_evaluation_status = summary.latest_evaluation_status
    chapter.latest_evaluation_stale_reason = summary.latest_evaluation_stale_reason
    chapter.integrity_gate_blocked = summary.integrity_gate_blocked
    chapter.latest_story_bible_integrity_issue_count = (
        summary.latest_story_bible_integrity_issue_count
    )
    chapter.latest_story_bible_integrity_blocking_issue_count = (
        summary.latest_story_bible_integrity_blocking_issue_count
    )
    chapter.latest_story_bible_integrity_summary = summary.latest_story_bible_integrity_summary
    chapter.canon_gate_blocked = summary.canon_gate_blocked
    chapter.latest_canon_issue_count = summary.latest_canon_issue_count
    chapter.latest_canon_blocking_issue_count = summary.latest_canon_blocking_issue_count
    chapter.latest_canon_summary = summary.latest_canon_summary
    chapter.final_ready = summary.final_ready
    chapter.final_gate_status = summary.final_gate_status
    chapter.final_gate_reason = summary.final_gate_reason
    return summary


def apply_chapter_gate_metadata_many(chapters: Iterable[object]) -> None:
    for chapter in chapters:
        apply_chapter_gate_metadata(chapter)


def checkpoint_status_blocks_final(status: Optional[str]) -> bool:
    return status in {
        CHECKPOINT_STATUS_PENDING,
        CHECKPOINT_STATUS_REJECTED,
    }


def should_downgrade_final_chapter_for_checkpoint(
    *,
    chapter_status: Optional[str],
    checkpoint_status: Optional[str],
) -> bool:
    return (
        chapter_status == CHAPTER_STATUS_FINAL
        and checkpoint_status_blocks_final(checkpoint_status)
    )


def review_verdict_blocks_final(verdict: Optional[str]) -> bool:
    return verdict in {
        REVIEW_VERDICT_CHANGES_REQUESTED,
        REVIEW_VERDICT_BLOCKED,
    }


def should_downgrade_final_chapter_for_review_decision(
    *,
    chapter_status: Optional[str],
    verdict: Optional[str],
) -> bool:
    return chapter_status == CHAPTER_STATUS_FINAL and review_verdict_blocks_final(verdict)


def _build_pending_reason(count: int, stale_reason: Optional[str] = None) -> str:
    if count == 1:
        base = "There is 1 pending checkpoint blocking final status."
    else:
        base = f"There are {count} pending checkpoints blocking final status."
    if stale_reason:
        return f"{base} {stale_reason}"
    return base


def _build_rejected_reason(count: int, stale_reason: Optional[str] = None) -> str:
    if count == 1:
        base = "There is 1 rejected checkpoint blocking final status."
    else:
        base = f"There are {count} rejected checkpoints blocking final status."
    if stale_reason:
        return f"{base} {stale_reason}"
    return base


def _build_review_reason(verdict: Optional[str], summary: Optional[str]) -> str:
    if verdict == REVIEW_VERDICT_BLOCKED:
        base = "The latest review decision blocks final status."
    else:
        base = "The latest review decision requires changes before final status."
    if summary:
        return f"{base} {summary}"
    return base


def _build_evaluation_reason(status: str, stale_reason: Optional[str]) -> str:
    if status == QUALITY_METRICS_EVALUATION_STATUS_STALE:
        base = "The latest chapter evaluation is outdated and must be rerun before final status."
    else:
        base = "This chapter needs a fresh evaluation before it can enter final status."
    if stale_reason:
        return f"{base} {stale_reason}"
    return base


def _build_story_bible_integrity_reason(
    blocking_issue_count: int,
    summary: Optional[str],
) -> str:
    if blocking_issue_count == 1:
        base = "The latest Story Bible integrity check reports 1 blocking truth-layer issue."
    else:
        base = (
            "The latest Story Bible integrity check reports "
            f"{blocking_issue_count} blocking truth-layer issues."
        )
    if summary:
        return f"{base} {summary}"
    return base


def _build_review_stale_reason(
    *,
    current_version_number: int,
    latest_review_version_number: Optional[int],
    summary: Optional[str],
) -> str:
    reviewed_version = latest_review_version_number or 1
    base = (
        "The latest review decision applies to "
        f"chapter version {reviewed_version}, but the current chapter is at version "
        f"{current_version_number}. A fresh review decision is required before final status."
    )
    if summary:
        return f"{base} Latest review summary: {summary}"
    return base


def _build_checkpoint_stale_reason(
    *,
    current_version_number: int,
    latest_checkpoint_version_number: Optional[int],
    latest_checkpoint_title: Optional[str],
    latest_checkpoint_status: Optional[str],
) -> str:
    checkpoint_version = latest_checkpoint_version_number or 1
    checkpoint_label = latest_checkpoint_title or "The latest checkpoint"
    if latest_checkpoint_status:
        checkpoint_label = (
            f'{checkpoint_label} ({latest_checkpoint_status})'
        )
    return (
        f'{checkpoint_label} applies to chapter version {checkpoint_version}, '
        f"but the current chapter is at version {current_version_number}. "
        "Reconfirm the checkpoint before final status."
    )


def _build_canon_reason(blocking_issue_count: int, summary: Optional[str]) -> str:
    if blocking_issue_count == 1:
        base = "The latest canon evaluation reports 1 blocking continuity issue."
    else:
        base = (
            "The latest canon evaluation reports "
            f"{blocking_issue_count} blocking continuity issues."
        )
    if summary:
        return f"{base} {summary}"
    return base


def mark_quality_metrics_fresh(quality_metrics: Optional[object]) -> dict:
    next_quality_metrics = ChapterQualityMetricsSnapshot.from_payload(
        quality_metrics,
    ).model_copy(
        update={
            "evaluation_status": QUALITY_METRICS_EVALUATION_STATUS_FRESH,
            "evaluation_stale_reason": None,
            "evaluation_updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    payload = next_quality_metrics.to_payload()
    payload["evaluation_stale_reason"] = None
    return payload


def mark_quality_metrics_stale(
    quality_metrics: Optional[object],
    *,
    reason: str,
) -> dict:
    next_quality_metrics = ChapterQualityMetricsSnapshot.from_payload(
        quality_metrics,
    ).model_copy(
        update={
            "evaluation_status": QUALITY_METRICS_EVALUATION_STATUS_STALE,
            "evaluation_stale_reason": reason,
        }
    )
    return next_quality_metrics.to_payload()


def resolve_quality_metrics_evaluation_status(
    quality_metrics: Optional[object],
) -> tuple[str, Optional[str]]:
    snapshot = ChapterQualityMetricsSnapshot.from_payload(quality_metrics)
    status = (
        snapshot.evaluation_status.strip()
        if isinstance(snapshot.evaluation_status, str) and snapshot.evaluation_status.strip()
        else None
    )
    stale_reason = (
        snapshot.evaluation_stale_reason.strip()
        if isinstance(snapshot.evaluation_stale_reason, str)
        and snapshot.evaluation_stale_reason.strip()
        else None
    )
    has_evaluation_payload = snapshot.has_evaluation_payload()
    extra_payload = snapshot.model_extra or {}

    if status == QUALITY_METRICS_EVALUATION_STATUS_STALE or bool(
        extra_payload.get("evaluation_stale")
    ):
        return (
            QUALITY_METRICS_EVALUATION_STATUS_STALE,
            stale_reason or "The chapter changed after the latest evaluation.",
        )
    if status == QUALITY_METRICS_EVALUATION_STATUS_FRESH:
        return QUALITY_METRICS_EVALUATION_STATUS_FRESH, None
    if has_evaluation_payload:
        return QUALITY_METRICS_EVALUATION_STATUS_FRESH, None
    return QUALITY_METRICS_EVALUATION_STATUS_MISSING, None


def _object_int(item: object | None, attr: str) -> Optional[int]:
    if item is None:
        return None
    value = getattr(item, attr, None)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _resolve_current_version_number(
    current_version_number: Optional[int],
    *,
    latest_checkpoint_version_number: Optional[int],
    latest_review_version_number: Optional[int],
) -> int:
    if isinstance(current_version_number, (int, float)) and int(current_version_number) > 0:
        return int(current_version_number)
    return max(
        int(latest_checkpoint_version_number or 0),
        int(latest_review_version_number or 0),
        1,
    )
