from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar, cast

from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from scaffold.base import CoreBase

ModelT = TypeVar("ModelT", bound=CoreBase)


class AsyncRepository(Generic[ModelT]):
    def __init__(self, model: type[ModelT]) -> None:
        self._model = model

    @property
    def model(self) -> type[ModelT]:
        return self._model

    def _id_column(self) -> ColumnElement[Any]:
        return cast(ColumnElement[Any], getattr(self._model, "id"))

    async def get(self, session: AsyncSession, id_: int) -> ModelT | None:
        return await session.get(self._model, id_)

    async def list_by_ids(self, session: AsyncSession, ids: Sequence[int]) -> list[ModelT]:
        if not ids:
            return []
        stmt = select(self._model).where(self._id_column().in_(tuple(ids)))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def first_where(self, session: AsyncSession, *criteria: Any) -> ModelT | None:
        stmt = select(self._model).where(*criteria).limit(1)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def list_where(
        self,
        session: AsyncSession,
        *criteria: Any,
        order_by: Any = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ModelT]:
        stmt = select(self._model).where(*criteria)
        if order_by:
            stmt = stmt.order_by(*order_by)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, session: AsyncSession, entity: ModelT) -> ModelT:
        session.add(entity)
        await session.flush()
        return entity

    async def add_all(self, session: AsyncSession, entities: Sequence[ModelT]) -> None:
        session.add_all(entities)
        await session.flush()

    async def delete(self, session: AsyncSession, entity: ModelT) -> None:
        await session.delete(entity)

    async def delete_by_id(self, session: AsyncSession, id_: int) -> bool:
        stmt = delete(self._model).where(self._id_column() == id_)
        result: Any = await session.execute(stmt)
        rowcount = result.rowcount
        return rowcount is not None and rowcount > 0
