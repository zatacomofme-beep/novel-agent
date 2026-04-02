#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 API 端点，查看 500 错误详情
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:password@localhost:5432/novel_agent"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from services.prompt_template_service import PromptTemplateService

async def test_list_api():
    engine = create_async_engine(os.getenv("DATABASE_URL"))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    service = PromptTemplateService()
    
    try:
        async with async_session() as session:
            # 完全模拟 API 调用
            templates, total, categories = await service.list_templates(
                session=session,
                category=None,
                search=None,
                tags=None,
                difficulty=None,
                user_id=None,
                page=1,
                page_size=20
            )
            
            print(f"✅ 调用成功！")
            print(f"   templates 数量：{len(templates)}")
            print(f"   total: {total}")
            print(f"   categories: {categories}")
            
            # 检查返回的模板对象
            if templates:
                print(f"\n   第一个模板的属性:")
                t = templates[0]
                for attr in dir(t):
                    if not attr.startswith('_'):
                        try:
                            val = getattr(t, attr)
                            if not callable(val):
                                print(f"     {attr}: {type(val).__name__}")
                        except:
                            pass
    except Exception as e:
        print(f"❌ 错误：{e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_list_api())
