"""
Generic async CRUD repository. All domain repositories inherit from this.
"""
from __future__ import annotations

import uuid
from typing import Generic, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model_class: type[ModelT]) -> None:
        self._session = session
        self._model_class = model_class

    async def get_by_id(self, id: uuid.UUID) -> ModelT | None:
        return await self._session.get(self._model_class, id)

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        stmt = select(self._model_class).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, **kwargs: object) -> ModelT:
        instance = self._model_class(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def update(self, instance: ModelT, **kwargs: object) -> ModelT:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self._session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self._session.delete(instance)
        await self._session.flush()
