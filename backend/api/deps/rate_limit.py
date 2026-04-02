from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.rate_limit import get_rate_limiter, RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter()


async def rate_limit_dependency(
    request: Request,
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    client_ip = request.client.host if request.client else "unknown"

    user_id = getattr(request.state, "user_id", None)
    if user_id:
        identifier = f"user:{user_id}"
    else:
        identifier = f"ip:{client_ip}"

    allowed, info = await rate_limiter.check_rate_limit(identifier)

    request.state.rate_limit_info = info

    if not allowed:
        logger.warning(
            "rate_limit_exceeded",
            extra={
                "identifier": identifier,
                "limit": info["limit"],
                "remaining": info["remaining"],
            },
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limit_exceeded",
                "message": "Too many requests. Please try again later.",
                "metadata": {
                    "limit": info["limit"],
                    "retry_after": info["retry_after"],
                },
            },
            headers={"Retry-After": str(info["retry_after"])},
        )


RateLimitDep = Annotated[None, Depends(rate_limit_dependency)]
