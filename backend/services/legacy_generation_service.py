from __future__ import annotations

"""Compatibility surface for the legacy chapter generation pipeline.

Current product mainline uses Story Engine workflows. This module keeps the
older generation pipeline behind an explicit legacy service boundary so call
sites do not depend on the implementation module directly.
"""

from services.generation_service import (
    StoryBibleIntegrityError,
    build_generation_payload,
    run_generation_pipeline,
)

__all__ = [
    "StoryBibleIntegrityError",
    "build_generation_payload",
    "run_generation_pipeline",
]
