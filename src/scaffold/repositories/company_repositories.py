from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.company.companies import Company
from scaffold.models.company.company_domains import CompanyDomain
from scaffold.models.company.company_events import CompanyEvent

from scaffold.repositories.base import AsyncRepository


class CompanyRepository(AsyncRepository[Company]):
    def __init__(self) -> None:
        super().__init__(Company)

    async def list_by_display_name_ilike(
        self,
        session: AsyncSession,
        pattern: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Company]:
        stmt = select(Company).where(Company.display_name.ilike(pattern))
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())


class CompanyDomainRepository(AsyncRepository[CompanyDomain]):
    def __init__(self) -> None:
        super().__init__(CompanyDomain)

    async def get_by_domain_lower(self, session: AsyncSession, domain: str) -> CompanyDomain | None:
        stmt = select(CompanyDomain).where(func.lower(CompanyDomain.domain) == domain.lower()).limit(1)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def list_by_company_id(
        self,
        session: AsyncSession,
        company_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CompanyDomain]:
        return await self.list_where(
            session,
            CompanyDomain.company_id == company_id,
            order_by=(CompanyDomain.id,),
            limit=limit,
            offset=offset,
        )


class CompanyEventRepository(AsyncRepository[CompanyEvent]):
    def __init__(self) -> None:
        super().__init__(CompanyEvent)

    async def list_by_company_id(
        self,
        session: AsyncSession,
        company_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CompanyEvent]:
        return await self.list_where(
            session,
            CompanyEvent.company_id == company_id,
            order_by=(CompanyEvent.id.desc(),),
            limit=limit,
            offset=offset,
        )


company_repository = CompanyRepository()
company_domain_repository = CompanyDomainRepository()
company_event_repository = CompanyEventRepository()
