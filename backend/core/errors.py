from __future__ import annotations

from typing import Any
from typing import Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable application error code.")
    message: str = Field(description="Human readable error message.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.metadata = metadata or {}
