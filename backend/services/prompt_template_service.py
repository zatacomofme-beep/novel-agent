from __future__ import annotations
import uuid
import json
from pathlib import Path
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.prompt_template import PromptTemplate

# 从 JSON 文件加载模板数据（非硬编码）
TEMPLATE_DATA_FILE = Path(__file__).parent.parent / "data" / "templates_24.json"
with open(TEMPLATE_DATA_FILE, "r", encoding="utf-8") as f:
    SYSTEM_TEMPLATES = json.load(f)


class PromptTemplateService:

    CATEGORIES = [
        "世界观构建",
        "角色塑造",
        "情节设计",
        "打斗战斗",
        "情感描写",
        "升级进化",
        "伏笔悬念",
        "章尾钩子",
        "起承转合",
        "场景转换",
        "高潮设计",
        "结局收束",
    ]

    async def list_templates(
        self,
        session: AsyncSession,
        category: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[list[str]] = None,
        difficulty: Optional[str] = None,
        is_system: Optional[bool] = None,
        user_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PromptTemplate], int, list[str]]:
        await self._ensure_system_templates_seeded(session)

        stmt = select(PromptTemplate).where(PromptTemplate.is_active == True)

        if category:
            stmt = stmt.where(PromptTemplate.category == category)
        if difficulty:
            stmt = stmt.where(PromptTemplate.difficulty_level == difficulty)
        if is_system is not None:
            stmt = stmt.where(PromptTemplate.is_system == is_system)
        if user_id is not None:
            stmt = stmt.where(
                or_(
                    PromptTemplate.is_system == True,
                    PromptTemplate.user_id == user_id,
                )
            )
        else:
            stmt = stmt.where(PromptTemplate.is_system == True)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    PromptTemplate.name.ilike(search_pattern),
                    PromptTemplate.tagline.ilike(search_pattern),
                    PromptTemplate.description.ilike(search_pattern),
                )
            )
        if tags:
            for tag in tags:
                stmt = stmt.where(PromptTemplate.tags.contains([tag]))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(PromptTemplate.use_count.desc(), PromptTemplate.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await session.execute(stmt)
        templates = result.scalars().all()

        return list(templates), total, self.CATEGORIES

    async def get_template(
        self,
        session: AsyncSession,
        template_id: uuid.UUID,
    ) -> Optional[PromptTemplate]:
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def create_template(
        self,
        session: AsyncSession,
        data: dict,
        user_id: uuid.UUID,
    ) -> PromptTemplate:
        template = PromptTemplate(
            user_id=user_id,
            is_system=False,
            **data,
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        return template

    async def increment_use_count(
        self,
        session: AsyncSession,
        template_id: uuid.UUID,
    ) -> None:
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template:
            template.use_count += 1
            await session.commit()

    async def _ensure_system_templates_seeded(self, session: AsyncSession) -> None:
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.is_system == True).limit(1)
        )
        if result.scalar_one_or_none():
            return

        for template_data in SYSTEM_TEMPLATES:
            template = PromptTemplate(is_system=True, **template_data)
            session.add(template)
        await session.commit()

    async def get_system_templates_for_seed(self) -> list[dict]:
        return SYSTEM_TEMPLATES

    async def recommend_templates(
        self,
        session: AsyncSession,
        project_id: str,
        chapter_id: Optional[str] = None,
        chapter_content: Optional[str] = None,
        context: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> list[PromptTemplate]:
        """智能推荐模板 - 基于章节内容、项目信息等"""
        from sqlalchemy import text
        
        # 基础查询：获取所有活跃模板
        await self._ensure_system_templates_seeded(session)
        
        stmt = select(PromptTemplate).where(
            PromptTemplate.is_active == True
        )
        
        # 如果有用户 ID，同时获取系统模板和用户自定义模板
        if user_id:
            stmt = stmt.where(
                or_(
                    PromptTemplate.is_system == True,
                    PromptTemplate.user_id == user_id,
                )
            )
        else:
            stmt = stmt.where(PromptTemplate.is_system == True)
        
        # 按使用次数排序作为基础推荐
        stmt = stmt.order_by(PromptTemplate.use_count.desc())
        
        result = await session.execute(stmt)
        all_templates = result.scalars().all()
        
        # 如果没有章节内容，返回最常用的模板
        if not chapter_content and not context:
            return all_templates[:5]
        
        # 基于内容进行简单匹配推荐
        scored_templates = []
        content_lower = (chapter_content or "").lower() + " " + (context or "").lower()
        
        for template in all_templates:
            score = 0
            
            # 类别匹配
            if template.category.lower() in content_lower:
                score += 10
            
            # 标签匹配
            for tag in template.tags:
                if tag.lower() in content_lower:
                    score += 5
            
            # 推荐场景匹配
            for scene in template.recommended_scenes:
                if scene.lower() in content_lower:
                    score += 3
            
            # 名称和简介匹配
            if template.name.lower() in content_lower or template.tagline.lower() in content_lower:
                score += 8
            
            # 内容关键词匹配
            template_content_lower = template.content.lower()
            for keyword in ["描写", "模板", "技巧", "结构"]:
                if keyword in content_lower and keyword in template_content_lower:
                    score += 2
            
            scored_templates.append((score, template))
        
        # 按分数排序
        scored_templates.sort(key=lambda x: x[0], reverse=True)
        
        # 返回前 5 个推荐模板
        return [t for _, t in scored_templates[:5]]

