#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试模板服务是否正确加载
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:password@localhost:5432/novel_agent"

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.prompt_template import PromptTemplate
from services.prompt_template_service import PromptTemplateService, SYSTEM_TEMPLATES

async def test_templates():
    print("=" * 60)
    print("测试模板服务")
    print("=" * 60)
    
    # 1. 检查 SYSTEM_TEMPLATES
    print(f"\n1. SYSTEM_TEMPLATES 数量：{len(SYSTEM_TEMPLATES)}")
    print(f"   前 3 套模板:")
    for i, t in enumerate(SYSTEM_TEMPLATES[:3], 1):
        print(f"   {i}. {t['name']}")
    
    # 2. 检查数据库
    print("\n2. 检查数据库中的模板...")
    engine = create_async_engine(os.getenv("DATABASE_URL"))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 检查表是否存在
        from sqlalchemy import text
        try:
            result = await session.execute(text("SELECT COUNT(*) FROM prompt_templates"))
            count = result.scalar()
            print(f"   数据库中共有 {count} 套模板")
        except Exception as e:
            print(f"   ❌ 错误：{e}")
            return
        
        # 检查系统模板
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.is_system == True).limit(5)
        )
        templates = result.scalars().all()
        if templates:
            print(f"   系统模板前 3 套:")
            for i, t in enumerate(templates[:3], 1):
                print(f"   {i}. {t.name}")
        else:
            print(f"   ⚠️  数据库中没有系统模板")
    
    # 3. 测试服务方法
    print("\n3. 测试服务方法...")
    service = PromptTemplateService()
    async with async_session() as session:
        templates, total, categories = await service.list_templates(
            session=session,
            user_id=None,
            page=1,
            page_size=20
        )
        print(f"   服务返回：{len(templates)} 套模板，共 {total} 套")
        print(f"   分类：{categories}")
        if templates:
            print(f"   前 3 套:")
            for i, t in enumerate(templates[:3], 1):
                print(f"   {i}. {t.name}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_templates())
