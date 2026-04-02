#!/usr/bin/env python3
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/novel_agent"

async def check():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'prompt_templates'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()
        print("表结构:")
        for col in columns:
            print(f"  {col[0]:20} | {col[1]:20} | nullable={col[2]} | default={col[3]}")

    await engine.dispose()

asyncio.run(check())
