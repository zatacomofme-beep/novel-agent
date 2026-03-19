from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


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
FINAL_GATE_STATUS_BLOCKED_REVIEW = "blocked_review"
CHAPTER_STATUS_FINAL = "final"
CHAPTER_STATUS_REVIEW = "review"


@dataclass(frozen=True)
class ChapterGateSummary:
    pending_checkpoint_count: int = 0
    rejected_checkpoint_count: int = 0
    latest_checkpoint_status: Optional[str] = None
    latest_checkpoint_title: Optional[str] = None
    latest_review_verdict: Optional[str] = None
    latest_review_summary: Optional[str] = None
    review_gate_blocked: bool = False
    final_ready: bool = True
    final_gate_status: str = FINAL_GATE_STATUS_READY
    final_gate_reason: Optional[str] = None


def summarize_chapter_gate(
    checkpoints: Optional[Iterable[object]],
    decisions: Optional[Iterable[object]] = None,
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
    latest_review_verdict = getattr(latest_decision, "verdict", None)
    latest_review_summary = getattr(latest_decision, "summary", None)
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
            pending_checkpoint_count=pending_count,
            rejected_checkpoint_count=rejected_count,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_REJECTED,
            final_gate_reason=_build_rejected_reason(rejected_count),
        )

    if pending_count > 0:
        return ChapterGateSummary(
            pending_checkpoint_count=pending_count,
            rejected_checkpoint_count=rejected_count,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_PENDING,
            final_gate_reason=_build_pending_reason(pending_count),
        )

    if review_verdict_blocks_final(latest_review_verdict):
        return ChapterGateSummary(
            pending_checkpoint_count=0,
            rejected_checkpoint_count=0,
            latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
            latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
            latest_review_verdict=latest_review_verdict,
            latest_review_summary=latest_review_summary,
            review_gate_blocked=True,
            final_ready=False,
            final_gate_status=FINAL_GATE_STATUS_BLOCKED_REVIEW,
            final_gate_reason=_build_review_reason(
                latest_review_verdict,
                latest_review_summary,
            ),
        )

    return ChapterGateSummary(
        pending_checkpoint_count=0,
        rejected_checkpoint_count=0,
        latest_checkpoint_status=getattr(latest_checkpoint, "status", None),
        latest_checkpoint_title=getattr(latest_checkpoint, "title", None),
        latest_review_verdict=latest_review_verdict,
        latest_review_summary=latest_review_summary,
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
    )
    chapter.pending_checkpoint_count = summary.pending_checkpoint_count
    chapter.rejected_checkpoint_count = summary.rejected_checkpoint_count
    chapter.latest_checkpoint_status = summary.latest_checkpoint_status
    chapter.latest_checkpoint_title = summary.latest_checkpoint_title
    chapter.latest_review_verdict = summary.latest_review_verdict
    chapter.latest_review_summary = summary.latest_review_summary
    chapter.review_gate_blocked = summary.review_gate_blocked
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


def _build_pending_reason(count: int) -> str:
    if count == 1:
        return "There is 1 pending checkpoint blocking final status."
    return f"There are {count} pending checkpoints blocking final status."


def _build_rejected_reason(count: int) -> str:
    if count == 1:
        return "There is 1 rejected checkpoint blocking final status."
    return f"There are {count} rejected checkpoints blocking final status."


def _build_review_reason(verdict: Optional[str], summary: Optional[str]) -> str:
    if verdict == REVIEW_VERDICT_BLOCKED:
        base = "The latest review decision blocks final status."
    else:
        base = "The latest review decision requires changes before final status."
    if summary:
        return f"{base} {summary}"
    return base
