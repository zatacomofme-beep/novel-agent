from __future__ import annotations

import os
from typing import Any

try:
    from langchain_core import tracing
    from langchain_core.tracer_session import LensSession
    _LANGSMITH_AVAILABLE = True
except ImportError:
    _LANGSMITH_AVAILABLE = False
    LensSession = object


_tracer: Any = None
_current_session: Any = None


def get_tracer() -> Any | None:
    global _tracer
    if not _LANGSMITH_AVAILABLE:
        return None
    if _tracer is not None:
        return _tracer

    langchain_api_key = os.environ.get("LANGSMITH_API_KEY")
    langchain_project = os.environ.get("LANGSMITH_PROJECT", "novel-agent")

    if not langchain_api_key:
        return None

    try:
        from langchain_core.tracing import LangChainTracer
        _tracer = LangChainTracer(
            project_name=langchain_project,
            tenant_id=langchain_api_key,
        )
        return _tracer
    except Exception:
        return None


def start_session(session_name: str | None = None) -> Any | None:
    global _current_session
    if not _LANGSMITH_AVAILABLE:
        return None
    tracer = get_tracer()
    if tracer is None:
        return None
    try:
        _current_session = LensSession(
            tracer=tracer,
            session_name=session_name or "default",
        )
        return _current_session
    except Exception:
        return None


def end_session() -> None:
    global _current_session
    _current_session = None


def trace_agent_run(
    agent_name: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> None:
    tracer = get_tracer()
    if tracer is None:
        return
    try:
        span_data = {
            "agent": agent_name,
            "input": input_data,
            "output": output_data,
            "tags": tags or [],
        }
        tracer.on_span_end(span_data)
    except Exception:
        pass


def trace_generation(
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    duration_ms: float,
    task_name: str,
) -> None:
    tracer = get_tracer()
    if tracer is None:
        return
    try:
        span_data = {
            "type": "generation",
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_dollars": cost,
            "duration_ms": duration_ms,
            "task_name": task_name,
        }
        tracer.on_span_end(span_data)
    except Exception:
        pass
