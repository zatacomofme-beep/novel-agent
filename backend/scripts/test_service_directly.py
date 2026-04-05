#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试模板服务
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/novel_agent"),
)

from services.prompt_template_service import PromptTemplateService
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def test_service():
    engine = create_async_engine(os.getenv("DATABASE_URL"))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    service = PromptTemplateService()
    
    async with async_session() as session:
        # 测试 list_templates
        templates, total, categories = await service.list_templates(
            session=session,
            user_id=None,
            page=1,
            page_size=20
        )
        
        print(f"✅ 服务调用成功！")
        print(f"   模板总数：{total}")
        print(f"   返回模板数：{len(templates)}")
        print(f"   分类：{categories}")
        
        if templates:
            print(f"\n   前 5 套模板:")
            for i, t in enumerate(templates[:5], 1):
                print(f"   {i}. {t.name} - {t.tagline}")
                print(f"      分类：{t.category}, 难度：{t.difficulty_level}")

asyncio.run(test_service())
