from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.search.job_collection_checkpoints import JobCollectionCheckpoint
from scaffold.models.search.job_collection_definitions import JobCollectionDefinition
from scaffold.models.search.job_collection_runs import JobCollectionRun

from scaffold.repositories.base import AsyncRepository


class JobCollectionDefinitionRepository(AsyncRepository[JobCollectionDefinition]):
    def __init__(self) -> None:
        super().__init__(JobCollectionDefinition)

    async def list_active(
        self,
        session: AsyncSession,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobCollectionDefinition]:
        return await self.list_where(
            session,
            JobCollectionDefinition.active.is_(True),
            order_by=(JobCollectionDefinition.priority, JobCollectionDefinition.id),
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
    ) -> list[JobCollectionDefinition]:
        return await self.list_where(
            session,
            JobCollectionDefinition.job_discovery_source_id == job_discovery_source_id,
            order_by=(JobCollectionDefinition.priority, JobCollectionDefinition.id),
            limit=limit,
            offset=offset,
        )


class JobCollectionRunRepository(AsyncRepository[JobCollectionRun]):
    def __init__(self) -> None:
        super().__init__(JobCollectionRun)

    async def list_by_job_collection_definition_id(
        self,
        session: AsyncSession,
        job_collection_definition_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobCollectionRun]:
        return await self.list_where(
            session,
            JobCollectionRun.job_collection_definition_id == job_collection_definition_id,
            order_by=(JobCollectionRun.id.desc(),),
            limit=limit,
            offset=offset,
        )


class JobCollectionCheckpointRepository(AsyncRepository[JobCollectionCheckpoint]):
    def __init__(self) -> None:
        super().__init__(JobCollectionCheckpoint)

    async def get_by_definition_and_key(
        self,
        session: AsyncSession,
        job_collection_definition_id: int,
        checkpoint_key: str,
    ) -> JobCollectionCheckpoint | None:
        return await self.first_where(
            session,
            JobCollectionCheckpoint.job_collection_definition_id == job_collection_definition_id,
            JobCollectionCheckpoint.checkpoint_key == checkpoint_key,
        )

    async def list_by_job_collection_definition_id(
        self,
        session: AsyncSession,
        job_collection_definition_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobCollectionCheckpoint]:
        return await self.list_where(
            session,
            JobCollectionCheckpoint.job_collection_definition_id == job_collection_definition_id,
            order_by=(JobCollectionCheckpoint.id.desc(),),
            limit=limit,
            offset=offset,
        )


job_collection_definition_repository = JobCollectionDefinitionRepository()
job_collection_run_repository = JobCollectionRunRepository()
job_collection_checkpoint_repository = JobCollectionCheckpointRepository()
