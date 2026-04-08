from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def _extract_json_from_text(text: str) -> str | None:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    if text.startswith("[") and text.endswith("]"):
        return text

    pattern = r"\{[\s\S]*\}"
    match = re.search(pattern, text)
    if match:
        return match.group(0)

    array_pattern = r"\[[\s\S]*\]"
    arr_match = re.search(array_pattern, text)
    if arr_match:
        return arr_match.group(0)

    return None


def validate_agent_output(
    raw_output: str | dict[str, Any] | list[Any],
    schema_class: type[T],
    *,
    agent_name: str = "unknown",
    strict: bool = False,
) -> T:
    if isinstance(raw_output, (dict, list)):
        data = raw_output
    else:
        json_str = _extract_json_from_text(raw_output)
        if json_str is None:
            raise AgentOutputValidationError(
                agent_name=agent_name,
                reason="no_valid_json_found",
                detail="Could not extract JSON from model output text.",
                raw_preview=raw_output[:200],
            )
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise AgentOutputValidationError(
                agent_name=agent_name,
                reason="json_parse_error",
                detail=str(exc),
                raw_preview=json_str[:200],
            ) from exc

    try:
        if isinstance(data, list):
            return schema_class.model_validate({"items": data})
        return schema_class.model_validate(data)
    except ValidationError as exc:
        error_count = exc.error_count()
        first_errors = [e["msg"] for e in exc.errors()[:5]]
        raise AgentOutputValidationError(
            agent_name=agent_name,
            reason="schema_validation_failed",
            detail=f"{error_count} validation error(s): {'; '.join(first_errors)}",
            error_fields=[e["loc"][-1] for e in exc.errors() if e.get("loc")],
            raw_preview=(
                json.dumps(data, ensure_ascii=False)[:200]
                if isinstance(data, dict)
                else str(data)[:200]
            ),
        ) from exc


def safe_validate_agent_output(
    raw_output: str | dict[str, Any] | list[Any],
    schema_class: type[T],
    *,
    agent_name: str = "unknown",
) -> tuple[T | None, AgentOutputValidationError | None]:
    try:
        result = validate_agent_output(raw_output, schema_class, agent_name=agent_name)
        return result, None
    except AgentOutputValidationError as exc:
        logger.warning(
            "agent_output_validation_failed",
            extra={
                "agent": agent_name,
                "reason": exc.reason,
                "detail": exc.detail,
            },
        )
        return None, exc


class AgentOutputValidationError(Exception):
    def __init__(
        self,
        *,
        agent_name: str,
        reason: str,
        detail: str,
        error_fields: list[str] | None = None,
        raw_preview: str | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.reason = reason
        self.detail = detail
        self.error_fields = error_fields or []
        self.raw_preview = raw_preview
        super().__init__(f"[{agent_name}] {reason}: {detail}")
