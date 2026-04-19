from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.job.job_match_evaluations import JobMatchEvaluation
from scaffold.models.job.job_match_events import JobMatchEvent
from scaffold.models.job.job_match_scores import JobMatchScore
from scaffold.models.job.job_matches import JobMatch

from scaffold.repositories.base import AsyncRepository


class JobMatchRepository(AsyncRepository[JobMatch]):
    def __init__(self) -> None:
        super().__init__(JobMatch)

    async def get_by_candidate_and_job(
        self, session: AsyncSession, candidate_id: int, job_id: int
    ) -> JobMatch | None:
        return await self.first_where(
            session,
            JobMatch.candidate_id == candidate_id,
            JobMatch.job_id == job_id,
        )

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobMatch]:
        return await self.list_where(
            session,
            JobMatch.candidate_id == candidate_id,
            order_by=(JobMatch.id.desc(),),
            limit=limit,
            offset=offset,
        )

    async def list_by_job_id(
        self,
        session: AsyncSession,
        job_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobMatch]:
        return await self.list_where(
            session,
            JobMatch.job_id == job_id,
            order_by=(JobMatch.id.desc(),),
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
    ) -> list[JobMatch]:
        return await self.list_where(
            session,
            JobMatch.status == status,
            order_by=(JobMatch.id.desc(),),
            limit=limit,
            offset=offset,
        )


class JobMatchScoreRepository(AsyncRepository[JobMatchScore]):
    def __init__(self) -> None:
        super().__init__(JobMatchScore)

    async def get_by_job_match_and_dimension(
        self, session: AsyncSession, job_match_id: int, dimension: str
    ) -> JobMatchScore | None:
        return await self.first_where(
            session,
            JobMatchScore.job_match_id == job_match_id,
            JobMatchScore.dimension == dimension,
        )

    async def list_by_job_match_id(
        self,
        session: AsyncSession,
        job_match_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobMatchScore]:
        return await self.list_where(
            session,
            JobMatchScore.job_match_id == job_match_id,
            order_by=(JobMatchScore.dimension,),
            limit=limit,
            offset=offset,
        )


class JobMatchEvaluationRepository(AsyncRepository[JobMatchEvaluation]):
    def __init__(self) -> None:
        super().__init__(JobMatchEvaluation)

    async def list_by_job_match_id(
        self,
        session: AsyncSession,
        job_match_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobMatchEvaluation]:
        return await self.list_where(
            session,
            JobMatchEvaluation.job_match_id == job_match_id,
            order_by=(JobMatchEvaluation.id.desc(),),
            limit=limit,
            offset=offset,
        )


class JobMatchEventRepository(AsyncRepository[JobMatchEvent]):
    def __init__(self) -> None:
        super().__init__(JobMatchEvent)

    async def list_by_job_match_id(
        self,
        session: AsyncSession,
        job_match_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[JobMatchEvent]:
        return await self.list_where(
            session,
            JobMatchEvent.job_match_id == job_match_id,
            order_by=(JobMatchEvent.id.desc(),),
            limit=limit,
            offset=offset,
        )


job_match_repository = JobMatchRepository()
job_match_score_repository = JobMatchScoreRepository()
job_match_evaluation_repository = JobMatchEvaluationRepository()
job_match_event_repository = JobMatchEventRepository()
