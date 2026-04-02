from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from services.captcha_store import generate_and_store_captcha


router = APIRouter()


class CaptchaResponse(BaseModel):
    session_id: str
    image: str


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha() -> CaptchaResponse:
    session_id, image = generate_and_store_captcha()
    return CaptchaResponse(session_id=session_id, image=image)
