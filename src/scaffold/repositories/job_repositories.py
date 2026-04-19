from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.job.job_applications import JobApplication
from scaffold.models.job.job_discovery_sources import JobDiscoverySource
from scaffold.models.job.job_events import JobEvent
from scaffold.models.job.job_raw_payloads import JobRawPayload
from scaffold.models.job.job_routing_keywords import JobRoutingKeyword
from scaffold.models.job.jobs import Job

from scaffold.repositories.base import AsyncRepository


class JobRepository(AsyncRepository[Job]):
    def __init__(self) -> None:
        super().__init__(Job)

    async def get_by_job_discovery_source_and_external_id(
        self,
        session: AsyncSession,
        job_discovery_source_id: int,
        external_job_id: str,
    ) -> Job | None:
        return await self.first_where(
            session,
            Job.job_discovery_source_id == job_discovery_source_id,
            Job.external_job_id == external_job_id,
        )

    async def list_by_company_id(
        self,
        session: AsyncSession,
        company_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Job]:
        return await self.list_where(
            session,
            Job.company_id == company_id,
            order_by=(Job.id.desc(),),
            limit=limit,
            offset=offset,
        )

    async def list_by_status(
        self,
        session: AsyncSession,
        status: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Job]:
        return await self.list_where(
            session,
            Job.status == status,
            order_by=(Job.id.desc(),),
            limit=limit,
            offset=offset,
        )


class JobDiscoverySourceRepository(AsyncRepository[JobDiscoverySource]):
    def __init__(self) -> None:
        super().__init__(JobDiscoverySource)

    async def get_by_code(self, session: AsyncSession, code: str) -> JobDiscoverySource | None:
        return await self.first_where(session, JobDiscoverySource.code == code)


class JobEventRepository(AsyncRepository[JobEvent]):
    def __init__(self) -> None:
        super().__init__(JobEvent)

    async def list_by_job_id(
        self,
        session: AsyncSession,
        job_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobEvent]:
        return await self.list_where(
            session,
            JobEvent.job_id == job_id,
            order_by=(JobEvent.id.desc(),),
            limit=limit,
            offset=offset,
        )


class JobApplicationRepository(AsyncRepository[JobApplication]):
    def __init__(self) -> None:
        super().__init__(JobApplication)

    async def get_by_job_match_id(self, session: AsyncSession, job_match_id: int) -> JobApplication | None:
        return await self.first_where(session, JobApplication.job_match_id == job_match_id)

    async def list_by_status(
        self,
        session: AsyncSession,
        status: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobApplication]:
        return await self.list_where(
            session,
            JobApplication.status == status,
            order_by=(JobApplication.id.desc(),),
            limit=limit,
            offset=offset,
        )


class JobRawPayloadRepository(AsyncRepository[JobRawPayload]):
    def __init__(self) -> None:
        super().__init__(JobRawPayload)

    async def list_by_job_id(
        self,
        session: AsyncSession,
        job_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobRawPayload]:
        return await self.list_where(
            session,
            JobRawPayload.job_id == job_id,
            order_by=(JobRawPayload.id.desc(),),
            limit=limit,
            offset=offset,
        )


class JobRoutingKeywordRepository(AsyncRepository[JobRoutingKeyword]):
    def __init__(self) -> None:
        super().__init__(JobRoutingKeyword)

    async def list_by_job_id(
        self,
        session: AsyncSession,
        job_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobRoutingKeyword]:
        return await self.list_where(
            session,
            JobRoutingKeyword.job_id == job_id,
            order_by=(JobRoutingKeyword.id,),
            limit=limit,
            offset=offset,
        )


job_repository = JobRepository()
job_discovery_source_repository = JobDiscoverySourceRepository()
job_event_repository = JobEventRepository()
job_application_repository = JobApplicationRepository()
job_raw_payload_repository = JobRawPayloadRepository()
job_routing_keyword_repository = JobRoutingKeywordRepository()
