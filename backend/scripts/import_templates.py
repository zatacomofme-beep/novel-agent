#!/usr/bin/env python3
"""
从 JSON 文件导入模板到数据库
模板数据存储在 JSON 文件中，不是硬编码！
"""
import asyncio
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/novel_agent")

async def import_templates():
    """从 JSON 文件导入模板到数据库"""
    # 读取 JSON 文件
    json_path = Path(__file__).parent.parent / "data" / "templates_24.json"
    with open(json_path, "r", encoding="utf-8") as f:
        templates_data = json.load(f)
    
    print(f"📂 从 JSON 文件加载了 {len(templates_data)} 套模板")
    
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 检查是否已有系统模板
        from models.prompt_template import PromptTemplate
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.is_system == True).limit(1)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"⚠️  数据库已有系统模板 ({existing.name})，跳过导入")
            print("💡 如需重新导入，请先清空数据库中的 prompt_templates 表")
            return
        
        # 导入所有模板
        print(f"🚀 开始导入 {len(templates_data)} 套模板到数据库...")
        
        for i, template_data in enumerate(templates_data, 1):
            template = PromptTemplate(
                is_system=True,
                is_active=True,
                **template_data,
            )
            session.add(template)
            print(f"  ✅ [{i}/{len(templates_data)}] {template_data['name']}")
        
        await session.commit()
        print(f"\n🎉 成功导入 {len(templates_data)} 套模板到数据库！")
        print("💡 现在可以访问 http://localhost:3000/dashboard/prompt-templates 查看模板")

if __name__ == "__main__":
    asyncio.run(import_templates())
