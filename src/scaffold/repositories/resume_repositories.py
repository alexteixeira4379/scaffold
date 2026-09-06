from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from scaffold.models.resume.resume_profiles import ResumeProfile
from scaffold.models.resume.resume_profile_experiences import ResumeProfileExperience
from scaffold.models.resume.resume_profile_education import ResumeProfileEducation
from scaffold.models.resume.resume_profile_languages import ResumeProfileLanguage
from scaffold.models.resume.resume_profile_credentials import ResumeProfileCredential
from scaffold.models.resume.resume_profile_volunteer_entries import ResumeProfileVolunteerEntry
from scaffold.models.resume.resume_profile_references import ResumeProfileReference

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
        self,
        session: AsyncSession,
        session_id: int,
        step_id: int,
        repeat_index: int | None = None,
    ) -> ResumeBuildAnswer | None:
        return await self.first_where(
            session,
            ResumeBuildAnswer.session_id == session_id,
            ResumeBuildAnswer.step_id == step_id,
            ResumeBuildAnswer.repeat_index == repeat_index,
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


class ResumeProfileRepository(AsyncRepository[ResumeProfile]):
    def __init__(self) -> None:
        super().__init__(ResumeProfile)

    async def get_by_candidate_id(self, session: AsyncSession, candidate_id: int) -> ResumeProfile | None:
        return await self.first_where(session, ResumeProfile.candidate_id == candidate_id)


class ResumeProfileExperienceRepository(AsyncRepository[ResumeProfileExperience]):
    def __init__(self) -> None:
        super().__init__(ResumeProfileExperience)

    async def list_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> list[ResumeProfileExperience]:
        return await self.list_where(
            session,
            ResumeProfileExperience.resume_profile_id == resume_profile_id,
            order_by=(ResumeProfileExperience.order_index,),
        )

    async def delete_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> None:
        await session.execute(delete(ResumeProfileExperience).where(ResumeProfileExperience.resume_profile_id == resume_profile_id))


class ResumeProfileEducationRepository(AsyncRepository[ResumeProfileEducation]):
    def __init__(self) -> None:
        super().__init__(ResumeProfileEducation)

    async def list_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> list[ResumeProfileEducation]:
        return await self.list_where(
            session,
            ResumeProfileEducation.resume_profile_id == resume_profile_id,
            order_by=(ResumeProfileEducation.order_index,),
        )

    async def delete_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> None:
        await session.execute(delete(ResumeProfileEducation).where(ResumeProfileEducation.resume_profile_id == resume_profile_id))


class ResumeProfileLanguageRepository(AsyncRepository[ResumeProfileLanguage]):
    def __init__(self) -> None:
        super().__init__(ResumeProfileLanguage)

    async def list_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> list[ResumeProfileLanguage]:
        return await self.list_where(
            session,
            ResumeProfileLanguage.resume_profile_id == resume_profile_id,
            order_by=(ResumeProfileLanguage.order_index,),
        )

    async def delete_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> None:
        await session.execute(delete(ResumeProfileLanguage).where(ResumeProfileLanguage.resume_profile_id == resume_profile_id))


class ResumeProfileCredentialRepository(AsyncRepository[ResumeProfileCredential]):
    def __init__(self) -> None:
        super().__init__(ResumeProfileCredential)

    async def list_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> list[ResumeProfileCredential]:
        return await self.list_where(
            session,
            ResumeProfileCredential.resume_profile_id == resume_profile_id,
            order_by=(ResumeProfileCredential.order_index,),
        )

    async def delete_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> None:
        await session.execute(delete(ResumeProfileCredential).where(ResumeProfileCredential.resume_profile_id == resume_profile_id))


class ResumeProfileVolunteerEntryRepository(AsyncRepository[ResumeProfileVolunteerEntry]):
    def __init__(self) -> None:
        super().__init__(ResumeProfileVolunteerEntry)

    async def list_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> list[ResumeProfileVolunteerEntry]:
        return await self.list_where(
            session,
            ResumeProfileVolunteerEntry.resume_profile_id == resume_profile_id,
            order_by=(ResumeProfileVolunteerEntry.order_index,),
        )

    async def delete_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> None:
        await session.execute(delete(ResumeProfileVolunteerEntry).where(ResumeProfileVolunteerEntry.resume_profile_id == resume_profile_id))


class ResumeProfileReferenceRepository(AsyncRepository[ResumeProfileReference]):
    def __init__(self) -> None:
        super().__init__(ResumeProfileReference)

    async def list_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> list[ResumeProfileReference]:
        return await self.list_where(
            session,
            ResumeProfileReference.resume_profile_id == resume_profile_id,
            order_by=(ResumeProfileReference.order_index,),
        )

    async def delete_by_profile_id(self, session: AsyncSession, resume_profile_id: int) -> None:
        await session.execute(delete(ResumeProfileReference).where(ResumeProfileReference.resume_profile_id == resume_profile_id))


resume_profile_repository = ResumeProfileRepository()
resume_profile_experience_repository = ResumeProfileExperienceRepository()
resume_profile_education_repository = ResumeProfileEducationRepository()
resume_profile_language_repository = ResumeProfileLanguageRepository()
resume_profile_credential_repository = ResumeProfileCredentialRepository()
resume_profile_volunteer_entry_repository = ResumeProfileVolunteerEntryRepository()
resume_profile_reference_repository = ResumeProfileReferenceRepository()
resume_build_session_repository = ResumeBuildSessionRepository()
resume_build_step_repository = ResumeBuildStepRepository()
resume_build_answer_repository = ResumeBuildAnswerRepository()
resume_version_repository = ResumeVersionRepository()
cover_letter_version_repository = CoverLetterVersionRepository()
