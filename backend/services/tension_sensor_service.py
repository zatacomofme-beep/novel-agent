from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TensionSensorService:
    async def analyze_chapter_tension(
        self,
        session: AsyncSession,
        project_id: UUID,
        chapter_id: UUID,
        chapter_number: int,
        content: str,
    ) -> dict:
        score = self.compute_tension_from_text(content)
        level = self.classify_tension_level(score)
        return {
            "chapter_id": str(chapter_id),
            "project_id": str(project_id),
            "chapter_number": chapter_number,
            "tension_score": score,
            "tension_level": level,
            "tension_curve": self.build_tension_curve(self._split_scenes(content)),
        }

    async def get_chapter_profile(
        self,
        session: AsyncSession,
        chapter_id: UUID,
    ) -> dict | None:
        from models.tension_sensor import ChapterTensionProfile
        result = await session.execute(
            select(ChapterTensionProfile).where(
                ChapterTensionProfile.chapter_id == chapter_id
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None
        return {
            "avg_tension": profile.avg_tension,
            "peak_tension": profile.peak_tension,
            "tension_trend": profile.tension_trend,
        }

    async def list_project_profiles(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> list[dict]:
        from models.tension_sensor import ChapterTensionProfile
        result = await session.execute(
            select(ChapterTensionProfile)
            .where(ChapterTensionProfile.project_id == project_id)
            .order_by(ChapterTensionProfile.chapter_number)
        )
        profiles = result.scalars().all()
        return [
            {
                "chapter_id": str(p.chapter_id),
                "avg_tension": p.avg_tension,
                "peak_tension": p.peak_tension,
                "tension_trend": p.tension_trend,
            }
            for p in profiles
        ]

    def _split_scenes(self, content: str) -> list[dict]:
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        return [{"content": p, "summary": p[:80]} for p in paragraphs]

    def compute_tension_from_text(self, text: str) -> float:
        tension_indicators = [
            "suddenly", "unexpectedly", "burst", "crash", "screamed",
            "panic", "fear", "danger", "threat", "attack", "blood",
            "death", "kill", "love", "passion", "betrayal", "secret",
            "reveal", "confrontation", "argument", "running", "chase",
        ]
        lower_text = text.lower()
        count = sum(1 for word in tension_indicators if word in lower_text)
        words = len(text.split())
        density = count / max(words, 1) * 100
        return min(density / 10.0, 1.0)

    def classify_tension_level(self, score: float) -> str:
        if score < 0.25:
            return "low"
        elif score < 0.5:
            return "moderate"
        elif score < 0.75:
            return "high"
        return "critical"

    def build_tension_curve(
        self,
        scenes: list[dict],
    ) -> list[dict]:
        curve = []
        for i, scene in enumerate(scenes):
            scene_text = scene.get("content", "")
            score = self.compute_tension_from_text(scene_text)
            curve.append({
                "scene_index": i,
                "tension_score": score,
                "tension_level": self.classify_tension_level(score),
                "scene_summary": scene.get("summary", "")[:100],
            })
        return curve


tension_sensor_service = TensionSensorService()
