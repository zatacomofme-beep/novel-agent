from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory.l2_episodic import ChapterEpisode
from memory.l3_long_term import KnowledgeEntry, KnowledgeType, l3_long_term_memory


COMPRESSION_THRESHOLD_CHAPTERS = 20
COMPRESSION_TRIGGER_CHAPTERS = 15


class SemanticCompressionService:
    def __init__(self, project_id: UUID, session: AsyncSession) -> None:
        self.project_id = project_id
        self.session = session
        self.l3 = l3_long_term_memory

    async def get_chapters_needing_compression(self, current_chapter: int) -> list[int]:
        compression_cutoff = current_chapter - COMPRESSION_THRESHOLD_CHAPTERS
        result = await self.session.execute(
            select(ChapterEpisode.chapter_number)
            .where(
                ChapterEpisode.project_id == self.project_id,
                ChapterEpisode.chapter_number < compression_cutoff,
            )
            .order_by(ChapterEpisode.chapter_number.desc())
            .limit(COMPRESSION_TRIGGER_CHAPTERS)
        )
        return [row[0] for row in result.all()]

    async def compress_chapters(
        self,
        chapter_numbers: list[int],
        force: bool = False,
    ) -> list[KnowledgeEntry]:
        if not chapter_numbers and not force:
            return []

        result = await self.session.execute(
            select(ChapterEpisode)
            .where(
                ChapterEpisode.project_id == self.project_id,
                ChapterEpisode.chapter_number.in_(chapter_numbers),
            )
            .order_by(ChapterEpisode.chapter_number)
        )
        episodes = list(result.scalars().all())

        if not episodes:
            return []

        compressed: list[KnowledgeEntry] = []

        for arc_chunk in self._group_into_arcs(episodes):
            arc_summary = self._build_arc_summary(arc_chunk)
            arc_hash = hashlib.md5(arc_summary.encode()).hexdigest()[:16]
            chapter_min = min(e.chapter_number for e in arc_chunk)
            chapter_max = max(e.chapter_number for e in arc_chunk)
            entry = KnowledgeEntry(
                id=UUID(hashlib.md5(f"{arc_hash}_arc".encode()).hexdigest()[:16].__add__("00000000")),
                knowledge_type=KnowledgeType.PLOT_HISTORY,
                title=f"Arc 压缩: 第{chapter_min}-{chapter_max}章",
                content=arc_summary,
                chapter_number=chapter_max,
                importance=0.7,
                tags=["compressed_arc", f"chapters_{chapter_min}_{chapter_max}"],
                metadata={
                    "episode_count": len(arc_chunk),
                    "chapter_range": [e.chapter_number for e in arc_chunk],
                    "content_hash": arc_hash,
                    "characters": list({c for e in arc_chunk for c in e.characters}),
                    "themes": list({t for e in arc_chunk for t in e.themes}),
                    "emotional_tone": self._dominant_tone(arc_chunk),
                },
            )
            self.l3.store(entry)
            compressed.append(entry)

        for ep in episodes:
            ep.importance_score = 0.3
        await self.session.flush()
        return compressed

    def _group_into_arcs(
        self, episodes: list[ChapterEpisode]
    ) -> list[list[ChapterEpisode]]:
        arcs: list[list[ChapterEpisode]] = []
        current_arc: list[ChapterEpisode] = []
        current_theme: str | None = None

        for ep in episodes:
            ep_theme = ep.themes[0] if ep.themes else None
            if current_theme is None:
                current_theme = ep_theme
            elif ep_theme != current_theme and current_arc:
                arcs.append(current_arc)
                current_arc = []
                current_theme = ep_theme
            current_arc.append(ep)

        if current_arc:
            arcs.append(current_arc)
        return arcs

    def _build_arc_summary(self, episodes: list[ChapterEpisode]) -> str:
        if not episodes:
            return ""
        sorted_eps = sorted(episodes, key=lambda e: e.chapter_number)
        lines = [f"【情节压缩摘要 · 第{sorted_eps[0].chapter_number}-{sorted_eps[-1].chapter_number}章】"]
        for ep in sorted_eps:
            key_events_str = "；".join(ep.key_events) if ep.key_events else "（无关键事件）"
            lines.append(f"第{ep.chapter_number}章: {ep.summary} | 关键事件: {key_events_str}")
        all_characters: list[str] = []
        for ep in sorted_eps:
            for c in ep.characters:
                if c not in all_characters:
                    all_characters.append(c)
        if all_characters:
            lines.append(f"主要角色: {', '.join(all_characters[:8])}")
        return "\n".join(lines)

    def _dominant_tone(self, episodes: list[ChapterEpisode]) -> str:
        from collections import Counter
        tones = [ep.emotional_tone for ep in episodes if ep.emotional_tone]
        if not tones:
            return "neutral"
        counter = Counter(tones)
        return counter.most_common(1)[0][0]

    async def should_compress(self, current_chapter: int) -> bool:
        chapters_behind = current_chapter - COMPRESSION_TRIGGER_CHAPTERS
        result = await self.session.execute(
            select(ChapterEpisode.chapter_number)
            .where(
                ChapterEpisode.project_id == self.project_id,
                ChapterEpisode.chapter_number < chapters_behind,
                ChapterEpisode.importance_score > 0.5,
            )
        )
        return len(result.all()) >= 5

    async def get_compression_report(self) -> dict[str, Any]:
        result = await self.session.execute(
            select(ChapterEpisode)
            .where(ChapterEpisode.project_id == self.project_id)
            .order_by(ChapterEpisode.chapter_number)
        )
        all_episodes = list(result.scalars().all())
        low_importance = [e for e in all_episodes if e.importance_score < 0.5]
        return {
            "total_episodes": len(all_episodes),
            "compressed_episodes": len(low_importance),
            "active_episodes": len(all_episodes) - len(low_importance),
            "compression_candidate_count": len(
                await self.get_chapters_needing_compression(
                    max((e.chapter_number for e in all_episodes), default=0)
                )
            ),
        }
