#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接创建 prompt_templates 表
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:password@localhost:5432/novel_agent"

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def create_table():
    engine = create_async_engine(os.getenv("DATABASE_URL"))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 检查表是否存在
        try:
            result = await session.execute(text("SELECT 1 FROM prompt_templates LIMIT 1"))
            print("✅ prompt_templates 表已存在")
            return
        except Exception as e:
            if "does not exist" in str(e):
                print("⚠️  表不存在，开始创建...")
            else:
                print(f"❌ 错误：{e}")
                return
        
        # 创建表
        create_table_sql = """
        CREATE TABLE prompt_templates (
            id UUID PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            name VARCHAR(200) NOT NULL,
            tagline VARCHAR(300) NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR(50) NOT NULL,
            sub_category VARCHAR(50),
            tags JSON NOT NULL DEFAULT '[]',
            content TEXT NOT NULL,
            variables JSON NOT NULL DEFAULT '[]',
            use_count INTEGER NOT NULL DEFAULT 0,
            is_system BOOLEAN NOT NULL DEFAULT false,
            is_active BOOLEAN NOT NULL DEFAULT true,
            user_id UUID,
            recommended_scenes JSON NOT NULL DEFAULT '[]',
            difficulty_level VARCHAR(20) NOT NULL DEFAULT 'intermediate'
        )
        """
        
        await session.execute(text(create_table_sql))
        
        # 创建索引
        await session.execute(text("CREATE INDEX ix_prompt_templates_category ON prompt_templates(category)"))
        await session.execute(text("CREATE INDEX ix_prompt_templates_is_system ON prompt_templates(is_system)"))
        await session.execute(text("CREATE INDEX ix_prompt_templates_name_search ON prompt_templates(name)"))
        
        await session.commit()
        
        print("✅ prompt_templates 表创建成功！")

if __name__ == "__main__":
    asyncio.run(create_table())
