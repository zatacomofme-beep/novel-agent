from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.timeline_event import TimelineEvent


class TimeOrderType(str, Enum):
    CHRONOLOGICAL = "chronological"
    FLASHBACK = "flashback"
    FLASHFORWARD = "flashforward"
    SIMULTANEOUS = "simultaneous"


@dataclass
class TimeAnchor:
    chapter_number: int
    story_date: datetime | None
    relative_days: float | None
    description: str


@dataclass
class TemporalViolation:
    violation_type: str
    chapter_number: int
    description: str
    severity: str
    related_events: list[str] = field(default_factory=list)


@dataclass
class TemporalValidationResult:
    is_valid: bool
    order_type: TimeOrderType
    violations: list[TemporalViolation]
    anchors: list[TimeAnchor]
    consistency_score: float


DURATION_PATTERN = re.compile(
    r"(\d+)\s*(?:天|日|周|星期|月|年|小时|分钟|秒|刻钟|季|个时辰)"
)
PAST_MARKERS = {"过去", "曾经", "以前", "当年", "那时", "回忆", "倒叙", "追溯"}
FUTURE_MARKERS = {"未来", "将来", "日后", "此后", "几年后", "数月后", "插叙"}


class TemporalLogicEngine:
    def __init__(self, project_id: UUID, session: AsyncSession) -> None:
        self.project_id = project_id
        self.session = session
        self._anchors: dict[int, TimeAnchor] = {}
        self._narrative_order: list[int] = []

    async def load_timeline_events(self) -> list[TimelineEvent]:
        result = await self.session.execute(
            select(TimelineEvent)
            .where(TimelineEvent.project_id == self.project_id)
            .order_by(TimelineEvent.chapter_number)
        )
        return list(result.scalars().all())

    def parse_relative_time(self, text: str) -> float | None:
        match = DURATION_PATTERN.search(text)
        if not match:
            return None
        amount = int(match.group(1))
        unit = match.group(2)
        unit_map = {
            "秒": 1 / 86400,
            "分钟": 1 / 1440,
            "小时": 1 / 24,
            "刻钟": 1 / 96,
            "天": 1,
            "日": 1,
            "周": 7,
            "星期": 7,
            "月": 30,
            "季": 90,
            "年": 365,
            "个时辰": 2,
        }
        return amount * unit_map.get(unit, 0)

    def detect_time_order(
        self,
        chapter_number: int,
        content: str,
        prev_chapter: int | None,
    ) -> TimeOrderType:
        if prev_chapter is None:
            return TimeOrderType.CHRONOLOGICAL
        past_count = sum(1 for marker in PAST_MARKERS if marker in content)
        future_count = sum(1 for marker in FUTURE_MARKERS if marker in content)
        if past_count > future_count:
            return TimeOrderType.FLASHBACK
        if future_count > past_count:
            return TimeOrderType.FLASHFORWARD
        return TimeOrderType.CHRONOLOGICAL

    async def validate_chapter_temporal_consistency(
        self,
        chapter_number: int,
        content: str,
        prev_chapter_number: int | None,
    ) -> TemporalValidationResult:
        violations: list[TemporalViolation] = []
        anchors: list[TimeAnchor] = []
        order_type = self.detect_time_order(chapter_number, content, prev_chapter_number)

        duration = self.parse_relative_time(content)
        if duration is not None:
            anchor = TimeAnchor(
                chapter_number=chapter_number,
                story_date=None,
                relative_days=duration,
                description="章节内提及时间跨度",
            )
            anchors.append(anchor)
            self._anchors[chapter_number] = anchor

        if order_type == TimeOrderType.FLASHBACK:
            prev_anchor = self._anchors.get(prev_chapter_number)
            if prev_anchor and prev_anchor.story_date is None and prev_anchor.relative_days is not None:
                violations.append(
                    TemporalViolation(
                        violation_type="flashback_requires_anchor",
                        chapter_number=chapter_number,
                        description="倒叙章节需要锚定的时间基准点",
                        severity="warning",
                        related_events=[f"chapter_{prev_chapter_number}"],
                    )
                )

        if prev_chapter_number is not None:
            prev_anchor = self._anchors.get(prev_chapter_number)
            curr_anchor = self._anchors.get(chapter_number)
            if prev_anchor and curr_anchor and prev_anchor.relative_days and curr_anchor.relative_days:
                delta = curr_anchor.relative_days - prev_anchor.relative_days
                if delta < 0 and order_type != TimeOrderType.FLASHBACK:
                    violations.append(
                        TemporalViolation(
                            violation_type="negative_time_regression",
                            chapter_number=chapter_number,
                            description=f"时间倒退了 {-delta:.0f} 天但未标记为倒叙",
                            severity="error",
                            related_events=[f"chapter_{prev_chapter_number}"],
                        )
                    )

        consistency_score = max(0.0, 1.0 - len(violations) * 0.2)
        return TemporalValidationResult(
            is_valid=len([v for v in violations if v.severity == "error"]) == 0,
            order_type=order_type,
            violations=violations,
            anchors=anchors,
            consistency_score=consistency_score,
        )

    async def set_story_start_date(self, chapter_number: int, story_date: datetime) -> None:
        anchor = TimeAnchor(
            chapter_number=chapter_number,
            story_date=story_date,
            relative_days=0.0,
            description="故事起始时间",
        )
        self._anchors[chapter_number] = anchor

    async def validate_duration_claim(
        self,
        claim_text: str,
        from_chapter: int,
        to_chapter: int,
    ) -> TemporalViolation | None:
        days_claimed = self.parse_relative_time(claim_text)
        if days_claimed is None:
            return None

        from_anchor = self._anchors.get(from_chapter)
        to_anchor = self._anchors.get(to_chapter)
        if from_anchor is None or to_anchor is None:
            return None

        if from_anchor.story_date and to_anchor.story_date:
            actual_days = (to_anchor.story_date - from_anchor.story_date).days
            if abs(actual_days - days_claimed) > days_claimed * 0.2:
                return TemporalViolation(
                    violation_type="duration_mismatch",
                    chapter_number=to_chapter,
                    description=f"声称过了 {days_claimed:.0f} 天，实际应为 {actual_days:.0f} 天（误差超过 20%）",
                    severity="warning",
                    related_events=[f"chapter_{from_chapter}", f"chapter_{to_chapter}"],
                )
        return None

    async def get_temporal_report(self) -> dict[str, Any]:
        anchors_sorted = sorted(self._anchors.items(), key=lambda x: x[0])
        flashforward_count = sum(
            1 for a in self._anchors.values() if a.relative_days and a.relative_days < 0
        )
        return {
            "total_anchors": len(self._anchors),
            "anchors_by_chapter": {
                ch: {"days": a.relative_days, "desc": a.description}
                for ch, a in anchors_sorted
            },
            "flashforward_count": flashforward_count,
            "has_start_anchor": any(a.story_date is not None for a in self._anchors.values()),
        }
