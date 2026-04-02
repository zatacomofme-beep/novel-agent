from __future__ import annotations

from typing import Any, Optional

from core.config import get_settings


class LangSmithTracer:
    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = getattr(settings, "langsmith_enabled", False)
        self._api_key = getattr(settings, "langsmith_api_key", None)
        self._project = getattr(settings, "langsmith_project", "novel-agent")
        self._client: Any | None = None

    def _get_client(self) -> Any | None:
        if not self._enabled or not self._api_key:
            return None
        if self._client is not None:
            return self._client
        try:
            from langsmith import Client
            self._client = Client(
                api_key=self._api_key,
                project_name=self._project,
            )
            return self._client
        except Exception:
            return None

    def trace_run(
        self,
        name: str,
        inputs: dict[str, Any],
        *,
        run_type: str = "chain",
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any | None:
        client = self._get_client()
        if not client:
            return None
        try:
            from langsmith.run_trees import RunTree
            run = RunTree(
                name=name,
                inputs=inputs,
                run_type=run_type,
                metadata=metadata,
                tags=tags,
                client=client,
            )
            return run
        except Exception:
            return None

    def end_run(
        self,
        run: Any,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if run is None:
            return
        try:
            if error:
                run.end(error=error)
            else:
                run.end(outputs=outputs or {})
        except Exception:
            pass

    def create_feedback(
        self,
        run_id: str,
        key: str,
        score: float,
        comment: str | None = None,
    ) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            client.create_feedback(
                run_id=run_id,
                key=key,
                score=score,
                comment=comment,
            )
            return True
        except Exception:
            return False


lang_smith_tracer = LangSmithTracer()
