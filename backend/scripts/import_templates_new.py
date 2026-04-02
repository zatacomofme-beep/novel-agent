#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入新的19个模板到数据库
"""
import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/novel_agent"

async def import_templates():
    # 连接数据库
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 读取新模板
        templates_file = Path(__file__).parent.parent / "data" / "templates_20_new.json"
        with open(templates_file, 'r', encoding='utf-8') as f:
            templates = json.load(f)

        print(f"📦 开始导入 {len(templates)} 个新模板...")

        now = datetime.utcnow()

        for i, template in enumerate(templates, 1):
            # 检查是否已存在同名模板
            result = await session.execute(
                text("SELECT id FROM prompt_templates WHERE name = :name"),
                {"name": template["name"]}
            )
            existing = result.fetchone()

            if existing:
                print(f"   ⏭️  跳过已存在: {template['name']}")
                continue

            # 生成 UUID 并插入新模板
            template_id = str(uuid.uuid4())
            await session.execute(
                text("""
                    INSERT INTO prompt_templates (
                        id, name, tagline, description, category, sub_category,
                        tags, content, variables, recommended_scenes,
                        difficulty_level, use_count, is_system, is_active,
                        created_at, updated_at
                    ) VALUES (
                        :id, :name, :tagline, :description, :category, :sub_category,
                        :tags, :content, :variables, :recommended_scenes,
                        :difficulty_level, 0, true, true,
                        :created_at, :updated_at
                    )
                """),
                {
                    "id": template_id,
                    "name": template["name"],
                    "tagline": template["tagline"],
                    "description": template["description"],
                    "category": template["category"],
                    "sub_category": template.get("sub_category", ""),
                    "tags": json.dumps(template.get("tags", [])),
                    "content": template["content"],
                    "variables": json.dumps(template.get("variables", [])),
                    "recommended_scenes": json.dumps(template.get("recommended_scenes", [])),
                    "difficulty_level": template.get("difficulty_level", "intermediate"),
                    "created_at": now,
                    "updated_at": now,
                }
            )
            print(f"   ✅ [{i}/{len(templates)}] 导入: {template['name']}")

        await session.commit()

    await engine.dispose()
    print(f"\n🎉 导入完成！")

if __name__ == "__main__":
    asyncio.run(import_templates())
