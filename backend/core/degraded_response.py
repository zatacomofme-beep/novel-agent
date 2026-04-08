from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class DegradedResponse(Generic[T]):
    value: T | None
    degraded: bool = True
    reason: str | None = None
    source_service: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_degraded(self) -> bool:
        return self.degraded

    @property
    def is_empty(self) -> bool:
        if self.value is None:
            return True
        if isinstance(self.value, (list, dict, str)):
            return len(self.value) == 0
        return False

    @classmethod
    def ok(cls, value: T, *, source: str = "unknown") -> DegradedResponse[T]:
        return cls(value=value, degraded=False, source_service=source)

    @classmethod
    def empty(cls, *, source: str, reason: str = "service_unavailable") -> DegradedResponse[T]:
        return cls(value=None, degraded=True, source_service=source, reason=reason)

    @classmethod
    def fallback(
        cls,
        fallback_value: T,
        *,
        source: str,
        reason: str = "degraded_with_fallback",
    ) -> DegradedResponse[T]:
        return cls(
            value=fallback_value,
            degraded=True,
            source_service=source,
            reason=reason,
        )

    def unwrap(self) -> T:
        if self.value is None:
            raise ValueError(
                f"DegradedResponse is None (service={self.source_service}, reason={self.reason})"
            )
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value if self.value is not None else default

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "degraded": self.degraded,
            "reason": self.reason,
            "source_service": self.source_service,
            "timestamp": self.timestamp.isoformat(),
        }
