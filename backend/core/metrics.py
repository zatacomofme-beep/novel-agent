from __future__ import annotations

import time
from typing import Callable

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, REGISTRY, CollectorRegistry
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = Info = object


def _no_op(counter_name: str, description: str):
    class NoOpMetric:
        def labels(self, **kwargs): return self
        def inc(self, n=1): pass
        def observe(self, n: float) -> None: pass
        def set(self, n: float) -> None: pass
    return NoOpMetric()


class MetricsRegistry:
    _instance: MetricsRegistry | None = None

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}
        self._gauges: dict[str, Gauge] = {}

        if _PROMETHEUS_AVAILABLE:
            self._registry: CollectorRegistry | None = REGISTRY
            self.Info("novel_agent_info").info({"version": "2.0.0"})
        else:
            self._registry = None

    @classmethod
    def get_instance(cls) -> MetricsRegistry:
        if cls._instance is None:
            cls._instance = MetricsRegistry()
        return cls._instance

    def counter(self, name: str, description: str, labels: dict[str, str] | None = None) -> Counter:
        if name in self._counters:
            return self._counters[name]
        if not _PROMETHEUS_AVAILABLE:
            c = _no_op(name, description)
            self._counters[name] = c
            return c
        c = Counter(name, description, labels and list(labels.keys()), self._registry)
        self._counters[name] = c
        return c

    def histogram(self, name: str, description: str, buckets: list[float] | None = None) -> Histogram:
        if name in self._histograms:
            return self._histograms[name]
        if not _PROMETHEUS_AVAILABLE:
            h = _no_op(name, description)
            self._histograms[name] = h
            return h
        h = Histogram(name, description, buckets=buckets or Histogram.DEFAULT_BUCKETS, registry=self._registry)
        self._histograms[name] = h
        return h

    def gauge(self, name: str, description: str, labels: dict[str, str] | None = None) -> Gauge:
        if name in self._gauges:
            return self._gauges[name]
        if not _PROMETHEUS_AVAILABLE:
            g = _no_op(name, description)
            self._gauges[name] = g
            return g
        g = Gauge(name, description, labels and list(labels.keys()), self._registry)
        self._gauges[name] = g
        return g


registry = MetricsRegistry.get_instance()

CHAPTER_GENERATED = registry.counter(
    "novel_agent_chapter_generated_total",
    "Total chapters generated",
    {"status": "success|error|timeout"},
)
CHAPTER_GENERATION_TIME = registry.histogram(
    "novel_agent_chapter_generation_seconds",
    "Chapter generation duration in seconds",
)
TOKEN_USED = registry.counter(
    "novel_agent_tokens_used_total",
    "Total tokens used",
    {"agent": "writer|editor|critic|architect|debate|approver"},
)
TOKEN_COST = registry.counter(
    "novel_agent_token_cost_dollars",
    "Total token cost in dollars",
    {"agent": "writer|editor|critic|architect"},
)
ACTIVE_SESSIONS = registry.gauge(
    "novel_agent_active_sessions",
    "Number of active generation sessions",
)
REVISION_ROUNDS = registry.counter(
    "novel_agent_revision_rounds_total",
    "Total revision rounds completed",
)
CANON_BLOCKING_ISSUES = registry.counter(
    "novel_agent_canon_blocking_issues_total",
    "Total canon blocking issues found",
)
CIRCUIT_BREAKER_OPEN = registry.counter(
    "novel_agent_circuit_breaker_opens_total",
    "Total circuit breaker opens",
    {"reason": "budget|loop"},
)


def track_generation_time(agent_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                CHAPTER_GENERATION_TIME.observe(elapsed)
        return wrapper
    return decorator
