from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.application.application_artifacts import ApplicationArtifact
from scaffold.models.application.application_domain_rules import ApplicationDomainRule
from scaffold.models.application.application_events import ApplicationEvent
from scaffold.models.application.application_failures import ApplicationFailure
from scaffold.models.application.application_messages import ApplicationMessage
from scaffold.models.application.application_runs import ApplicationRun
from scaffold.models.application.application_sessions import ApplicationSession
from scaffold.models.application.application_steps import ApplicationStep

from scaffold.repositories.base import AsyncRepository


class ApplicationSessionRepository(AsyncRepository[ApplicationSession]):
    def __init__(self) -> None:
        super().__init__(ApplicationSession)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ApplicationSession]:
        return await self.list_where(
            session,
            ApplicationSession.candidate_id == candidate_id,
            order_by=(ApplicationSession.id.desc(),),
            limit=limit,
            offset=offset,
        )


class ApplicationRunRepository(AsyncRepository[ApplicationRun]):
    def __init__(self) -> None:
        super().__init__(ApplicationRun)

    async def list_by_job_application_id(
        self,
        session: AsyncSession,
        job_application_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ApplicationRun]:
        return await self.list_where(
            session,
            ApplicationRun.job_application_id == job_application_id,
            order_by=(ApplicationRun.id.desc(),),
            limit=limit,
            offset=offset,
        )


class ApplicationStepRepository(AsyncRepository[ApplicationStep]):
    def __init__(self) -> None:
        super().__init__(ApplicationStep)

    async def list_by_application_run_id(
        self,
        session: AsyncSession,
        application_run_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ApplicationStep]:
        return await self.list_where(
            session,
            ApplicationStep.application_run_id == application_run_id,
            order_by=(ApplicationStep.step_order, ApplicationStep.id),
            limit=limit,
            offset=offset,
        )


class ApplicationEventRepository(AsyncRepository[ApplicationEvent]):
    def __init__(self) -> None:
        super().__init__(ApplicationEvent)

    async def list_by_job_application_id(
        self,
        session: AsyncSession,
        job_application_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ApplicationEvent]:
        return await self.list_where(
            session,
            ApplicationEvent.job_application_id == job_application_id,
            order_by=(ApplicationEvent.id.desc(),),
            limit=limit,
            offset=offset,
        )


class ApplicationArtifactRepository(AsyncRepository[ApplicationArtifact]):
    def __init__(self) -> None:
        super().__init__(ApplicationArtifact)

    async def list_by_job_application_id(
        self,
        session: AsyncSession,
        job_application_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ApplicationArtifact]:
        return await self.list_where(
            session,
            ApplicationArtifact.job_application_id == job_application_id,
            order_by=(ApplicationArtifact.id.desc(),),
            limit=limit,
            offset=offset,
        )


class ApplicationFailureRepository(AsyncRepository[ApplicationFailure]):
    def __init__(self) -> None:
        super().__init__(ApplicationFailure)

    async def list_by_job_application_id(
        self,
        session: AsyncSession,
        job_application_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ApplicationFailure]:
        return await self.list_where(
            session,
            ApplicationFailure.job_application_id == job_application_id,
            order_by=(ApplicationFailure.id.desc(),),
            limit=limit,
            offset=offset,
        )


class ApplicationMessageRepository(AsyncRepository[ApplicationMessage]):
    def __init__(self) -> None:
        super().__init__(ApplicationMessage)

    async def list_by_job_application_id(
        self,
        session: AsyncSession,
        job_application_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ApplicationMessage]:
        return await self.list_where(
            session,
            ApplicationMessage.job_application_id == job_application_id,
            order_by=(ApplicationMessage.id.desc(),),
            limit=limit,
            offset=offset,
        )


class ApplicationDomainRuleRepository(AsyncRepository[ApplicationDomainRule]):
    def __init__(self) -> None:
        super().__init__(ApplicationDomainRule)

    async def get_by_domain_rule_type_key(
        self,
        session: AsyncSession,
        domain: str,
        rule_type: str,
        rule_key: str,
    ) -> ApplicationDomainRule | None:
        return await self.first_where(
            session,
            ApplicationDomainRule.domain == domain,
            ApplicationDomainRule.rule_type == rule_type,
            ApplicationDomainRule.rule_key == rule_key,
        )


application_session_repository = ApplicationSessionRepository()
application_run_repository = ApplicationRunRepository()
application_step_repository = ApplicationStepRepository()
application_event_repository = ApplicationEventRepository()
application_artifact_repository = ApplicationArtifactRepository()
application_failure_repository = ApplicationFailureRepository()
application_message_repository = ApplicationMessageRepository()
application_domain_rule_repository = ApplicationDomainRuleRepository()
