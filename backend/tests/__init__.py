from __future__ import annotations

import logging
import warnings


for logger_name in ("asyncio", "httpcore", "httpx", "neo4j", "openai"):
    logging.getLogger(logger_name).setLevel(logging.WARNING)

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
