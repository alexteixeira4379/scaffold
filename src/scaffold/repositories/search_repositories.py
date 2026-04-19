from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.search.search_checkpoints import SearchCheckpoint
from scaffold.models.search.search_definitions import SearchDefinition
from scaffold.models.search.search_runs import SearchRun
from scaffold.models.search.search_templates import SearchTemplate

from scaffold.repositories.base import AsyncRepository


class SearchTemplateRepository(AsyncRepository[SearchTemplate]):
    def __init__(self) -> None:
        super().__init__(SearchTemplate)

    async def list_active(
        self,
        session: AsyncSession,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[SearchTemplate]:
        return await self.list_where(
            session,
            SearchTemplate.active.is_(True),
            order_by=(SearchTemplate.id,),
            limit=limit,
            offset=offset,
        )


class SearchDefinitionRepository(AsyncRepository[SearchDefinition]):
    def __init__(self) -> None:
        super().__init__(SearchDefinition)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        active_only: bool = False,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[SearchDefinition]:
        criteria = [SearchDefinition.candidate_id == candidate_id]
        if active_only:
            criteria.append(SearchDefinition.active.is_(True))
        return await self.list_where(
            session,
            *criteria,
            order_by=(SearchDefinition.priority, SearchDefinition.id),
            limit=limit,
            offset=offset,
        )

    async def list_by_job_discovery_source_id(
        self,
        session: AsyncSession,
        job_discovery_source_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[SearchDefinition]:
        return await self.list_where(
            session,
            SearchDefinition.job_discovery_source_id == job_discovery_source_id,
            order_by=(SearchDefinition.id,),
            limit=limit,
            offset=offset,
        )


class SearchRunRepository(AsyncRepository[SearchRun]):
    def __init__(self) -> None:
        super().__init__(SearchRun)

    async def list_by_search_definition_id(
        self,
        session: AsyncSession,
        search_definition_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[SearchRun]:
        return await self.list_where(
            session,
            SearchRun.search_definition_id == search_definition_id,
            order_by=(SearchRun.id.desc(),),
            limit=limit,
            offset=offset,
        )


class SearchCheckpointRepository(AsyncRepository[SearchCheckpoint]):
    def __init__(self) -> None:
        super().__init__(SearchCheckpoint)

    async def get_by_definition_and_key(
        self, session: AsyncSession, search_definition_id: int, checkpoint_key: str
    ) -> SearchCheckpoint | None:
        return await self.first_where(
            session,
            SearchCheckpoint.search_definition_id == search_definition_id,
            SearchCheckpoint.checkpoint_key == checkpoint_key,
        )

    async def list_by_search_definition_id(
        self,
        session: AsyncSession,
        search_definition_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[SearchCheckpoint]:
        return await self.list_where(
            session,
            SearchCheckpoint.search_definition_id == search_definition_id,
            order_by=(SearchCheckpoint.id.desc(),),
            limit=limit,
            offset=offset,
        )


search_template_repository = SearchTemplateRepository()
search_definition_repository = SearchDefinitionRepository()
search_run_repository = SearchRunRepository()
search_checkpoint_repository = SearchCheckpointRepository()
