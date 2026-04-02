from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.open_thread import (
    OpenThread,
    OpenThreadHistory,
    ThreadStatus,
    EntityType,
)
from models.chapter import Chapter


SUSPENSE_PATTERNS = [
    re.compile(r"总觉得.*不简单", re.IGNORECASE),
    re.compile(r"有种?.*预感", re.IGNORECASE),
    re.compile(r"事情.*没.*结束", re.IGNORECASE),
    re.compile(r"这个?.*秘密", re.IGNORECASE),
    re.compile(r"终有一天", re.IGNORECASE),
    re.compile(r"迟早.*会", re.IGNORECASE),
    re.compile(r"三天后|七天后|一个月后", re.IGNORECASE),
    re.compile(r"没有.*想到.*这样", re.IGNORECASE),
    re.compile(r"后来.*才知道", re.IGNORECASE),
    re.compile(r"这就是.*伏笔", re.IGNORECASE),
]

ITEM_ANOMALY_PATTERNS = [
    re.compile(r"带血", re.IGNORECASE),
    re.compile(r"来历不明", re.IGNORECASE),
    re.compile(r"莫名.*出现", re.IGNORECASE),
    re.compile(r"丢失.*东西", re.IGNORECASE),
    re.compile(r"神秘.*符号", re.IGNORECASE),
    re.compile(r"不属于.*这里", re.IGNORECASE),
]

RELATIONSHIP_HINT_PATTERNS = [
    re.compile(r"眼神.*有些.*奇怪", re.IGNORECASE),
    re.compile(r"看.*的眼神.*不对劲", re.IGNORECASE),
    re.compile(r"他们.*之间.*似乎", re.IGNORECASE),
    re.compile(r"某种.*联系", re.IGNORECASE),
    re.compile(r"很久以前.*就认识", re.IGNORECASE),
]


class ForeshadowingLifecycleService:
    def __init__(self) -> None:
        pass

    async def scan_and_plant(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        chapter_num: int,
        content: str,
    ) -> list[OpenThread]:
        threads = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            entity_type, entity_ref, tags = self._detect_entity(line)
            if entity_type:
                thread = OpenThread(
                    project_id=project_id,
                    planted_chapter=chapter_num,
                    entity_ref=entity_ref,
                    entity_type=entity_type,
                    potential_tags=tags,
                    planted_content=line,
                    status=ThreadStatus.OPEN,
                    payoff_priority=0.3,
                )
                session.add(thread)
                threads.append(thread)

        await session.flush()

        for thread in threads:
            await self._record_history(
                session,
                thread.id,
                chapter_num,
                "planted",
                note=f"自动识别埋入: {thread.entity_ref[:50]}",
            )

        return threads

    def _detect_entity(
        self,
        line: str,
    ) -> tuple[Optional[str], Optional[str], list[str]]:
        for pattern in ITEM_ANOMALY_PATTERNS:
            if pattern.search(line):
                words = line.split()
                entity_ref = " ".join(words[:8]) if words else line[:50]
                tags = ["悬念", "物品异常"]
                return EntityType.ITEM, entity_ref, tags

        for pattern in SUSPENSE_PATTERNS:
            if pattern.search(line):
                tags = ["悬念句"]
                if "后" in line:
                    tags.append("时序伏笔")
                words = line.split()
                entity_ref = " ".join(words[:6]) if words else line[:50]
                return EntityType.EVENT, entity_ref, tags

        for pattern in RELATIONSHIP_HINT_PATTERNS:
            if pattern.search(line):
                tags = ["关系暗示"]
                words = line.split()
                entity_ref = " ".join(words[:6]) if words else line[:50]
                return EntityType.RELATIONSHIP, entity_ref, tags

        return None, None, []

    async def get_active_threads(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        chapter_num: int,
        lookback: int = 10,
    ) -> list[OpenThread]:
        min_chapter = max(1, chapter_num - lookback)
        statement = (
            select(OpenThread)
            .where(
                OpenThread.project_id == project_id,
                OpenThread.status.in_([ThreadStatus.OPEN, ThreadStatus.TRACKING]),
                OpenThread.planted_chapter >= min_chapter,
                OpenThread.planted_chapter <= chapter_num,
            )
            .order_by(OpenThread.payoff_priority.desc())
        )
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def bump_tracking_threads(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        chapter_num: int,
    ) -> None:
        statement = (
            update(OpenThread)
            .where(
                OpenThread.project_id == project_id,
                OpenThread.status == ThreadStatus.TRACKING,
            )
            .values(
                last_tracked_chapter=chapter_num,
                payoff_priority=OpenThread.payoff_priority + 0.05,
            )
        )
        await session.execute(statement)
        await session.flush()

    async def get_resolution_candidates(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        current_chapter: int,
    ) -> list[OpenThread]:
        statement = (
            select(OpenThread)
            .where(
                OpenThread.project_id == project_id,
                OpenThread.status.in_([
                    ThreadStatus.TRACKING,
                    ThreadStatus.RESOLUTION_PENDING,
                ]),
            )
            .order_by(OpenThread.payoff_priority.desc())
            .limit(5)
        )
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def mark_for_resolution(
        self,
        session: AsyncSession,
        thread_id: uuid.UUID,
        chapter: int,
    ) -> None:
        thread: OpenThread | None = await session.get(OpenThread, thread_id)
        if not thread:
            return

        old_status = thread.status
        thread.mark_resolution_pending(chapter)
        thread.payoff_priority = 1.0

        await self._record_history(
            session,
            thread_id,
            chapter,
            "resolution_marked",
            old_status=old_status,
            new_status=ThreadStatus.RESOLUTION_PENDING,
            note=f"Architect 标记待回收",
        )
        await session.flush()

    async def resolve(
        self,
        session: AsyncSession,
        thread_id: uuid.UUID,
        chapter: int,
        summary: str,
    ) -> None:
        thread: OpenThread | None = await session.get(OpenThread, thread_id)
        if not thread:
            return

        old_status = thread.status
        thread.mark_resolved(summary)
        thread.payoff_chapter = chapter

        await self._record_history(
            session,
            thread_id,
            chapter,
            "resolved",
            old_status=old_status,
            new_status=ThreadStatus.RESOLVED,
            note=summary[:100],
        )
        await session.flush()

    async def abandon(
        self,
        session: AsyncSession,
        thread_id: uuid.UUID,
        reason: str,
    ) -> None:
        thread: OpenThread | None = await session.get(OpenThread, thread_id)
        if not thread:
            return

        old_status = thread.status
        thread.mark_abandoned(reason)

        await self._record_history(
            session,
            thread_id,
            thread.last_tracked_chapter or thread.planted_chapter,
            "abandoned",
            old_status=old_status,
            new_status=ThreadStatus.ABANDONED,
            note=reason,
        )
        await session.flush()

    async def list_project_threads(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        status: str | None = None,
    ) -> list[OpenThread]:
        statement = select(OpenThread).where(OpenThread.project_id == project_id)
        if status:
            statement = statement.where(OpenThread.status == status)
        statement = statement.order_by(OpenThread.planted_chapter.desc())
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def get_thread_stats(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
    ) -> dict[str, Any]:
        statement = (
            select(OpenThread.status, func.count(OpenThread.id))
            .where(OpenThread.project_id == project_id)
            .group_by(OpenThread.status)
        )
        result = await session.execute(statement)
        rows = result.all()

        stats = {
            ThreadStatus.OPEN: 0,
            ThreadStatus.TRACKING: 0,
            ThreadStatus.RESOLUTION_PENDING: 0,
            ThreadStatus.RESOLVED: 0,
            ThreadStatus.ABANDONED: 0,
        }
        for status_val, count in rows:
            if status_val in stats:
                stats[status_val] = count

        total = sum(stats.values())
        resolved_rate = (
            stats[ThreadStatus.RESOLVED] / total * 100 if total > 0 else 0
        )

        return {
            **stats,
            "total": total,
            "resolved_rate_pct": round(resolved_rate, 1),
        }

    async def _record_history(
        self,
        session: AsyncSession,
        thread_id: uuid.UUID,
        chapter: int,
        event_type: str,
        old_status: str | None = None,
        new_status: str | None = None,
        note: str | None = None,
    ) -> None:
        history = OpenThreadHistory(
            thread_id=thread_id,
            chapter=chapter,
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            note=note,
        )
        session.add(history)


foreshadowing_lifecycle_service = ForeshadowingLifecycleService()
