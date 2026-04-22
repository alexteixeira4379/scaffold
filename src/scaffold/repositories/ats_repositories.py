from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.ats.ats_discovery_sources import AtsDiscoverySource
from scaffold.models.ats.ats_provider_configs import AtsProviderConfig
from scaffold.models.ats.ats_provider_domains import AtsProviderDomain
from scaffold.models.ats.ats_provider_rules import AtsProviderRule
from scaffold.models.ats.ats_providers import AtsProvider

from scaffold.repositories.base import AsyncRepository


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
            order_by=(
                AtsDiscoverySource.last_collected_at.asc().nullsfirst(),
                AtsDiscoverySource.code,
            ),
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
            order_by=(
                AtsDiscoverySource.last_collected_at.asc().nullsfirst(),
                AtsDiscoverySource.code,
            ),
            limit=limit,
            offset=offset,
        )

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
            order_by=(
                AtsDiscoverySource.last_collected_at.asc().nullsfirst(),
                AtsDiscoverySource.code,
            ),
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


ats_discovery_source_repository = AtsDiscoverySourceRepository()
ats_provider_repository = AtsProviderRepository()
ats_provider_config_repository = AtsProviderConfigRepository()
ats_provider_domain_repository = AtsProviderDomainRepository()
ats_provider_rule_repository = AtsProviderRuleRepository()
