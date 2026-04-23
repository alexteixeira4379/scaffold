from __future__ import annotations

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.ats.ats_discovery_sources import AtsDiscoverySource
from scaffold.models.ats.ats_provider_configs import AtsProviderConfig
from scaffold.models.ats.ats_provider_domains import AtsProviderDomain
from scaffold.models.ats.ats_provider_rules import AtsProviderRule
from scaffold.models.ats.ats_provider_schedules import AtsProviderSchedule
from scaffold.models.ats.ats_providers import AtsProvider

from scaffold.repositories.base import AsyncRepository


def _last_collected_at_order_by() -> tuple[object, object, object]:
    return (
        case((AtsDiscoverySource.last_collected_at.is_(None), 0), else_=1),
        AtsDiscoverySource.last_collected_at.asc(),
        AtsDiscoverySource.code,
    )


class AtsDiscoverySourceRepository(AsyncRepository[AtsDiscoverySource]):
    def __init__(self) -> None:
        super().__init__(AtsDiscoverySource)

    async def get_by_code(self, session: AsyncSession, code: str) -> AtsDiscoverySource | None:
        return await self.first_where(session, AtsDiscoverySource.code == code)

    async def list_by_ats_provider_id(
        self,
        session: AsyncSession,
        ats_provider_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AtsDiscoverySource]:
        return await self.list_where(
            session,
            AtsDiscoverySource.ats_provider_id == ats_provider_id,
            order_by=_last_collected_at_order_by(),
            limit=limit,
            offset=offset,
        )

    async def list_active(
        self,
        session: AsyncSession,
        *,
        ats_provider_id: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AtsDiscoverySource]:
        criteria = [AtsDiscoverySource.active.is_(True)]
        if ats_provider_id is not None:
            criteria.append(AtsDiscoverySource.ats_provider_id == ats_provider_id)

        return await self.list_where(
            session,
            *criteria,
            order_by=_last_collected_at_order_by(),
            limit=limit,
            offset=offset,
        )

    async def list_ready(
        self,
        session: AsyncSession,
        *,
        default_interval_seconds: int = 1800,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AtsDiscoverySource]:
        effective_interval = func.coalesce(AtsProviderSchedule.interval_seconds, default_interval_seconds)
        cutoff = func.timestampadd(text("SECOND"), -effective_interval, func.now())

        stmt = (
            select(AtsDiscoverySource)
            .outerjoin(
                AtsProviderSchedule,
                (AtsProviderSchedule.ats_provider_id == AtsDiscoverySource.ats_provider_id)
                & AtsProviderSchedule.active.is_(True),
            )
            .where(AtsDiscoverySource.active.is_(True))
            .where(
                AtsDiscoverySource.last_collected_at.is_(None)
                | (AtsDiscoverySource.last_collected_at <= cutoff)
            )
            .order_by(*_last_collected_at_order_by())
        )

        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_next_to_collect(
        self,
        session: AsyncSession,
        *,
        ats_provider_id: int | None = None,
    ) -> AtsDiscoverySource | None:
        criteria = [AtsDiscoverySource.active.is_(True)]
        if ats_provider_id is not None:
            criteria.append(AtsDiscoverySource.ats_provider_id == ats_provider_id)

        sources = await self.list_where(
            session,
            *criteria,
            order_by=_last_collected_at_order_by(),
            limit=1,
        )
        return sources[0] if sources else None

    async def list_never_collected(
        self,
        session: AsyncSession,
        *,
        ats_provider_id: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AtsDiscoverySource]:
        criteria = [
            AtsDiscoverySource.active.is_(True),
            AtsDiscoverySource.last_collected_at.is_(None),
        ]
        if ats_provider_id is not None:
            criteria.append(AtsDiscoverySource.ats_provider_id == ats_provider_id)

        return await self.list_where(
            session,
            *criteria,
            order_by=(AtsDiscoverySource.code,),
            limit=limit,
            offset=offset,
        )


class AtsProviderRepository(AsyncRepository[AtsProvider]):
    def __init__(self) -> None:
        super().__init__(AtsProvider)

    async def get_by_code(self, session: AsyncSession, code: str) -> AtsProvider | None:
        return await self.first_where(session, AtsProvider.code == code)

    async def list_active(
        self,
        session: AsyncSession,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AtsProvider]:
        return await self.list_where(
            session,
            AtsProvider.active.is_(True),
            order_by=(AtsProvider.code,),
            limit=limit,
            offset=offset,
        )


class AtsProviderConfigRepository(AsyncRepository[AtsProviderConfig]):
    def __init__(self) -> None:
        super().__init__(AtsProviderConfig)

    async def list_by_ats_provider_id(
        self,
        session: AsyncSession,
        ats_provider_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AtsProviderConfig]:
        return await self.list_where(
            session,
            AtsProviderConfig.ats_provider_id == ats_provider_id,
            order_by=(AtsProviderConfig.id,),
            limit=limit,
            offset=offset,
        )


class AtsProviderDomainRepository(AsyncRepository[AtsProviderDomain]):
    def __init__(self) -> None:
        super().__init__(AtsProviderDomain)

    async def list_by_ats_provider_id(
        self,
        session: AsyncSession,
        ats_provider_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AtsProviderDomain]:
        return await self.list_where(
            session,
            AtsProviderDomain.ats_provider_id == ats_provider_id,
            order_by=(AtsProviderDomain.id,),
            limit=limit,
            offset=offset,
        )


class AtsProviderRuleRepository(AsyncRepository[AtsProviderRule]):
    def __init__(self) -> None:
        super().__init__(AtsProviderRule)

    async def list_by_ats_provider_id(
        self,
        session: AsyncSession,
        ats_provider_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AtsProviderRule]:
        return await self.list_where(
            session,
            AtsProviderRule.ats_provider_id == ats_provider_id,
            order_by=(AtsProviderRule.priority, AtsProviderRule.id),
            limit=limit,
            offset=offset,
        )


class AtsProviderScheduleRepository(AsyncRepository[AtsProviderSchedule]):
    def __init__(self) -> None:
        super().__init__(AtsProviderSchedule)

    async def get_by_ats_provider_id(
        self, session: AsyncSession, ats_provider_id: int
    ) -> AtsProviderSchedule | None:
        return await self.first_where(
            session, AtsProviderSchedule.ats_provider_id == ats_provider_id
        )

    async def list_active(
        self,
        session: AsyncSession,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AtsProviderSchedule]:
        return await self.list_where(
            session,
            AtsProviderSchedule.active.is_(True),
            order_by=(AtsProviderSchedule.ats_provider_id,),
            limit=limit,
            offset=offset,
        )


ats_discovery_source_repository = AtsDiscoverySourceRepository()
ats_provider_repository = AtsProviderRepository()
ats_provider_config_repository = AtsProviderConfigRepository()
ats_provider_domain_repository = AtsProviderDomainRepository()
ats_provider_rule_repository = AtsProviderRuleRepository()
ats_provider_schedule_repository = AtsProviderScheduleRepository()
