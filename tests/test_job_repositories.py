from sqlalchemy import select
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex

from scaffold.models.job.jobs import Job


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
