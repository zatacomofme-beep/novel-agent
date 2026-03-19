from __future__ import annotations

import uuid
from typing import Optional
from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class AsyncRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get(self, entity_id: uuid.UUID) -> Optional[ModelT]:
        return await self.session.get(self.model, entity_id)

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        statement: Optional[Select[tuple[ModelT]]] = None,
    ) -> list[ModelT]:
        query = statement or select(self.model).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
