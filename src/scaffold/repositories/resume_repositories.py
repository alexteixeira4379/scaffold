from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.resume.cover_letter_versions import CoverLetterVersion
from scaffold.models.resume.resume_build_answers import ResumeBuildAnswer
from scaffold.models.resume.resume_build_sessions import ResumeBuildSession
from scaffold.models.resume.resume_build_steps import ResumeBuildStep
from scaffold.models.resume.resume_versions import ResumeVersion

from scaffold.repositories.base import AsyncRepository


class ResumeBuildSessionRepository(AsyncRepository[ResumeBuildSession]):
    def __init__(self) -> None:
        super().__init__(ResumeBuildSession)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ResumeBuildSession]:
        return await self.list_where(
            session,
            ResumeBuildSession.candidate_id == candidate_id,
            order_by=(ResumeBuildSession.id.desc(),),
            limit=limit,
            offset=offset,
        )


class ResumeBuildStepRepository(AsyncRepository[ResumeBuildStep]):
    def __init__(self) -> None:
        super().__init__(ResumeBuildStep)

    async def get_by_step_key(self, session: AsyncSession, step_key: str) -> ResumeBuildStep | None:
        return await self.first_where(session, ResumeBuildStep.step_key == step_key)

    async def list_active_ordered(
        self,
        session: AsyncSession,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ResumeBuildStep]:
        return await self.list_where(
            session,
            ResumeBuildStep.active.is_(True),
            order_by=(ResumeBuildStep.step_order, ResumeBuildStep.id),
            limit=limit,
            offset=offset,
        )


class ResumeBuildAnswerRepository(AsyncRepository[ResumeBuildAnswer]):
    def __init__(self) -> None:
        super().__init__(ResumeBuildAnswer)

    async def get_by_session_and_step(
        self, session: AsyncSession, session_id: int, step_id: int
    ) -> ResumeBuildAnswer | None:
        return await self.first_where(
            session,
            ResumeBuildAnswer.session_id == session_id,
            ResumeBuildAnswer.step_id == step_id,
        )

    async def list_by_session_id(
        self,
        session: AsyncSession,
        session_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ResumeBuildAnswer]:
        return await self.list_where(
            session,
            ResumeBuildAnswer.session_id == session_id,
            order_by=(ResumeBuildAnswer.id,),
            limit=limit,
            offset=offset,
        )


class ResumeVersionRepository(AsyncRepository[ResumeVersion]):
    def __init__(self) -> None:
        super().__init__(ResumeVersion)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ResumeVersion]:
        return await self.list_where(
            session,
            ResumeVersion.candidate_id == candidate_id,
            order_by=(ResumeVersion.version_number.desc(),),
            limit=limit,
            offset=offset,
        )


class CoverLetterVersionRepository(AsyncRepository[CoverLetterVersion]):
    def __init__(self) -> None:
        super().__init__(CoverLetterVersion)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CoverLetterVersion]:
        return await self.list_where(
            session,
            CoverLetterVersion.candidate_id == candidate_id,
            order_by=(CoverLetterVersion.id.desc(),),
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
    ) -> list[CoverLetterVersion]:
        return await self.list_where(
            session,
            CoverLetterVersion.job_id == job_id,
            order_by=(CoverLetterVersion.id.desc(),),
            limit=limit,
            offset=offset,
        )


resume_build_session_repository = ResumeBuildSessionRepository()
resume_build_step_repository = ResumeBuildStepRepository()
resume_build_answer_repository = ResumeBuildAnswerRepository()
resume_version_repository = ResumeVersionRepository()
cover_letter_version_repository = CoverLetterVersionRepository()
