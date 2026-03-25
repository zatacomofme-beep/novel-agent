from __future__ import annotations

import asyncio
from typing import Any

from openai import AsyncOpenAI

from core.config import get_settings


async def main() -> None:
    settings = get_settings()
    api_key = settings.model_gateway_api_key or settings.openai_api_key
    if not api_key:
        raise SystemExit("缺少 MODEL_GATEWAY_API_KEY / OPENAI_API_KEY，无法校验模型。")

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if settings.model_gateway_base_url:
        client_kwargs["base_url"] = settings.model_gateway_base_url
    client = AsyncOpenAI(**client_kwargs)

    models_response = await client.models.list()
    available = {item.id for item in models_response.data}

    required = [
        settings.story_engine_outline_model,
        settings.story_engine_guardian_model,
        settings.story_engine_logic_model,
        settings.story_engine_commercial_model,
        settings.story_engine_style_model,
        settings.story_engine_anchor_model,
        settings.story_engine_arbitrator_model,
        settings.story_engine_stream_model,
    ]
    deduplicated = list(dict.fromkeys(required))

    print("当前网关基址：", settings.model_gateway_base_url or "OpenAI 官方默认")
    print("待校验模型：")
    for model_name in deduplicated:
        if model_name in available:
            print(f"  [OK] {model_name}")
        else:
            print(f"  [MISS] {model_name}")


if __name__ == "__main__":
    asyncio.run(main())
