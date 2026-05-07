from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex

from scaffold.models.job.job_professional_entities import JobProfessionalEntity
from scaffold.models.job.jobs import Job
from scaffold.repositories.job_repositories import JobProfessionalEntityRepository


def test_jobs_url_hash_has_unique_index() -> None:
    url_hash_index = next(index for index in Job.__table__.indexes if index.name == "ix_jobs_url_hash")

    compiled = str(CreateIndex(url_hash_index).compile(dialect=mysql.dialect()))

    assert url_hash_index.unique is True
    assert "CREATE UNIQUE INDEX ix_jobs_url_hash" in compiled
    assert "url_hash" in compiled


def test_jobs_url_hash_lookup_compiles_for_mysql() -> None:
    stmt = select(Job).where(Job.url_hash == "abc123").limit(1)

    compiled = str(stmt.compile(dialect=mysql.dialect()))

    assert "jobs.url_hash" in compiled


def test_job_professional_entities_list_by_job_id_compiles_for_mysql() -> None:
    stmt = (
        select(JobProfessionalEntity)
        .where(JobProfessionalEntity.job_id == 42)
        .order_by(JobProfessionalEntity.id)
    )

    compiled = str(stmt.compile(dialect=mysql.dialect()))

    assert "job_professional_entities.job_id" in compiled
    assert "ORDER BY job_professional_entities.id" in compiled


async def test_job_professional_entity_repository_list_by_job_id_uses_default_order() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    repository = JobProfessionalEntityRepository()
    await repository.list_by_job_id(session, 42)

    compiled = str(session.execute.await_args.args[0].compile(dialect=mysql.dialect()))
    assert "job_professional_entities.job_id" in compiled
    assert "ORDER BY job_professional_entities.id" in compiled
