from __future__ import annotations

import logging
import os
import warnings


os.environ.setdefault("LOG_LEVEL", "ERROR")
os.environ.setdefault("APP_DEBUG", "false")


for logger_name in (
    "api.main",
    "asyncio",
    "celery",
    "celery.app.trace",
    "httpcore",
    "httpx",
    "neo4j",
    "openai",
    "realtime.task_events",
):
    logging.getLogger(logger_name).setLevel(logging.ERROR)

warnings.filterwarnings(
    "ignore",
    category=ResourceWarning,
    message=r"unclosed transport .*",
)
warnings.filterwarnings(
    "ignore",
    category=ResourceWarning,
    message=r"unclosed <socket\.socket .*",
)
