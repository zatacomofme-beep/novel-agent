from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from core.config import Settings, get_settings


class CircuitBreakerReason:
    EXCEEDED_BUDGET = "exceeded_budget"
    LOOP_DETECTED = "loop_detected"


@dataclass
class CircuitBreakerResult:
    should_break: bool
    reason: str | None
    current_spend: float
    budget: float
    tokens_used: int = 0
    loop_count: int = 0


@dataclass
class TokenRecord:
    chapter_id: str
    tokens_used: int
    cost: float
    timestamp: datetime


class TokenCircuitBreaker:
    DEFAULT_CHAPTER_BUDGET = 2.0
    DEFAULT_LOOP_THRESHOLD_TOKENS = 5000
    DEFAULT_LOOP_COUNT_TRIGGER = 3

    def __init__(
        self,
        chapter_budget: float | None = None,
        loop_threshold_tokens: int | None = None,
        loop_count_trigger: int | None = None,
    ) -> None:
        settings = get_settings()
        self.chapter_budget = chapter_budget or getattr(
            settings, "token_circuit_budget", self.DEFAULT_CHAPTER_BUDGET
        )
        self.loop_threshold_tokens = (
            loop_threshold_tokens or self.DEFAULT_LOOP_THRESHOLD_TOKENS
        )
        self.loop_count_trigger = loop_count_trigger or self.DEFAULT_LOOP_COUNT_TRIGGER

        self._spend: dict[str, float] = {}
        self._is_open: dict[str, bool] = {}
        self._retry_count: dict[str, int] = {}
        self._high_token_rounds: dict[str, int] = {}
        self._records: dict[str, list[TokenRecord]] = {}

    def check_and_record(
        self,
        chapter_id: str,
        tokens_used: int,
        cost: float,
    ) -> CircuitBreakerResult:
        if self._is_open.get(chapter_id):
            return CircuitBreakerResult(
                should_break=True,
                reason="circuit_already_open",
                current_spend=self._spend.get(chapter_id, 0.0),
                budget=self.chapter_budget,
                tokens_used=tokens_used,
                loop_count=self._retry_count.get(chapter_id, 0),
            )

        self._spend[chapter_id] = (
            self._spend.get(chapter_id, 0.0) + cost
        )

        if self._spend[chapter_id] > self.chapter_budget:
            self._is_open[chapter_id] = True
            return CircuitBreakerResult(
                should_break=True,
                reason=CircuitBreakerReason.EXCEEDED_BUDGET,
                current_spend=self._spend[chapter_id],
                budget=self.chapter_budget,
                tokens_used=tokens_used,
                loop_count=self._retry_count.get(chapter_id, 0),
            )

        if tokens_used > self.loop_threshold_tokens:
            self._high_token_rounds[chapter_id] = (
                self._high_token_rounds.get(chapter_id, 0) + 1
            )
            if self._high_token_rounds[chapter_id] >= self.loop_count_trigger:
                self._is_open[chapter_id] = True
                self._retry_count[chapter_id] = self._high_token_rounds[chapter_id]
                return CircuitBreakerResult(
                    should_break=True,
                    reason=CircuitBreakerReason.LOOP_DETECTED,
                    current_spend=self._spend[chapter_id],
                    budget=self.chapter_budget,
                    tokens_used=tokens_used,
                    loop_count=self._retry_count[chapter_id],
                )

        self._records.setdefault(chapter_id, []).append(
            TokenRecord(
                chapter_id=chapter_id,
                tokens_used=tokens_used,
                cost=cost,
                timestamp=datetime.now(timezone.utc),
            )
        )

        return CircuitBreakerResult(
            should_break=False,
            reason=None,
            current_spend=self._spend[chapter_id],
            budget=self.chapter_budget,
            tokens_used=tokens_used,
            loop_count=self._retry_count.get(chapter_id, 0),
        )

    def get_report(self, chapter_id: str) -> dict[str, Any]:
        spend = self._spend.get(chapter_id, 0.0)
        utilization = (spend / self.chapter_budget * 100) if self.chapter_budget > 0 else 0
        return {
            "chapter_id": chapter_id,
            "spent": round(spend, 4),
            "budget": self.chapter_budget,
            "utilization_pct": round(utilization, 1),
            "status": "open" if self._is_open.get(chapter_id) else "closed",
            "high_token_rounds": self._high_token_rounds.get(chapter_id, 0),
            "records": [
                {
                    "tokens": r.tokens_used,
                    "cost": round(r.cost, 4),
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in self._records.get(chapter_id, [])
            ],
        }

    def reset(self, chapter_id: str) -> None:
        self._spend.pop(chapter_id, None)
        self._is_open.pop(chapter_id, None)
        self._retry_count.pop(chapter_id, None)
        self._high_token_rounds.pop(chapter_id, None)
        self._records.pop(chapter_id, None)

    def reset_all(self) -> None:
        self._spend.clear()
        self._is_open.clear()
        self._retry_count.clear()
        self._high_token_rounds.clear()
        self._records.clear()


token_circuit_breaker = TokenCircuitBreaker()
