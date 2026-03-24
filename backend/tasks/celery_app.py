from __future__ import annotations

from typing import Any, Callable

try:
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - 本地缺 celery 时走轻量兜底
    class _LocalTaskWrapper:
        def __init__(self, func: Callable[..., Any]) -> None:
            self._func = func
            self.__name__ = getattr(func, "__name__", "local_task")
            self.__doc__ = getattr(func, "__doc__", None)

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self._func(*args, **kwargs)

        def apply_async(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Celery is not installed in the current environment.")

    class Celery:  # type: ignore[override]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.conf: dict[str, Any] = {}

        def task(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], _LocalTaskWrapper]:
            def decorator(func: Callable[..., Any]) -> _LocalTaskWrapper:
                return _LocalTaskWrapper(func)

            return decorator

from core.config import get_settings


settings = get_settings()

celery_app = Celery(
    "long_novel_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
