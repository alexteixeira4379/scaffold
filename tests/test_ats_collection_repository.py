"""Real MySQL tests using an isolated disposable ATS_COLLECTION_TEST_URL."""
import importlib.util
import os
from datetime import datetime, timedelta, timezone
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, MetaData, text, DefaultClause
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from scaffold.models.ats.ats_providers import AtsProvider as Provider
from scaffold.models.ats.ats_discovery_sources import AtsDiscoverySource as Source
from scaffold.models.ats.ats_provider_schedules import AtsProviderSchedule as Schedule
from scaffold.models.ats.ats_collection_runs import AtsCollectionRun as Run
from scaffold.repositories.ats_collection_repository import AtsCollectionRepository, LeaseLostError

URL = os.getenv("ATS_COLLECTION_TEST_URL")
pytestmark = pytest.mark.skipif(not URL, reason="requires isolated MySQL ATS_COLLECTION_TEST_URL")
NOW = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)

@pytest.fixture
def schema():
    engine = create_engine(URL.replace("+asyncmy", "+pymysql"))
    metadata = MetaData()
    for table in (Provider.__table__, Source.__table__, Schedule.__table__):
        table.to_metadata(metadata)
    for table in metadata.tables.values():
        if "active" in table.c: table.c.active.server_default = DefaultClause(text("1"))
    source_table = metadata.tables[Source.__tablename__]
    source_table.c.checkpoint_value.server_default = DefaultClause(text("(JSON_OBJECT())"))
    for index in list(source_table.indexes):
        if index.name == "ix_ats_collection_due": source_table.indexes.remove(index)
    for column in list(source_table.columns):
        if column.name.startswith("collection_") or column.name in ("last_attempt_at", "next_collection_at"):
            source_table._columns.remove(column)
    with engine.begin() as c:
        Run.__table__.drop(c, checkfirst=True)
        metadata.drop_all(c)
        metadata.create_all(c)
        path = os.path.join(os.path.dirname(__file__), "../migrations/core/versions/0048_ats_collection_cycles.py")
        spec = importlib.util.spec_from_file_location("ats_revision", path)
        revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(revision)
        with Operations.context(MigrationContext.configure(c)): revision.upgrade()
    yield
    with engine.begin() as c:
        Run.__table__.drop(c)
        Source.__table__.drop(c)
        Schedule.__table__.drop(c)
        Provider.__table__.drop(c)
    engine.dispose()

async def seed(session):
    session.add_all([Provider(id=1, code="demo", name="Demo", kind="ats", active=True),
                     Provider(id=2, code="disabled", name="Disabled", kind="ats", active=False)])
    await session.flush()
    for id_, provider, active, qualified in [(1,1,True,"qualified"),(2,1,True,"qualified"),
        (3,1,False,"qualified"),(4,2,True,"qualified"),(5,1,True,"excluded_demo")]:
        session.add(Source(id=id_, ats_provider_id=provider, code=f"s{id_}", name="test", kind="ats",
                           active=active, qualification_status=qualified, checkpoint_value={}))
    await session.commit()

@pytest.mark.asyncio
async def test_claim_skip_locked_and_fenced_expiration(schema):
    engine = create_async_engine(URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = AtsCollectionRepository()
    async with factory() as session: await seed(session)
    args = dict(provider_codes=("demo", "disabled"), now=NOW, lease_seconds=60)
    async with factory() as one, factory() as two:
        first = await repo.claim(one, **args)
        second = await repo.claim(two, **args)
        assert first[0].id == 1 and second[0].id == 2
        await one.commit()
        await two.commit()
    async with factory() as session:
        assert await repo.claim(session, **args) is None
        await session.commit()
    async with factory() as session:
        renewed = await repo.claim(session, **{**args, "now": NOW + timedelta(seconds=61)})
        await session.commit()
    assert renewed[0].id == 1 and renewed[2] != first[2]
    async with factory() as session:
        with pytest.raises(LeaseLostError):
            await repo.save_batch(session, source_id=1, cycle_id=first[0].collection_cycle_id,
                                  token=first[2], checkpoint={"bad": True}, observed=1, published=1,
                                  now=NOW + timedelta(seconds=62))
        await session.rollback()
    async with factory() as session:
        assert (await session.get(Source, 1)).checkpoint_value == {}
        assert (await session.get(Run, first[0].collection_cycle_id)).attempts == 2
    await engine.dispose()

@pytest.mark.asyncio
async def test_checkpoint_failure_and_completion_separate(schema):
    engine = create_async_engine(URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = AtsCollectionRepository()
    async with factory() as session:
        await seed(session)
        source, _, token = await repo.claim(session, provider_codes=("demo",), now=NOW, lease_seconds=60)
        await session.commit()
        key = dict(source_id=source.id, cycle_id=source.collection_cycle_id, token=token)
        checkpoint = {"version": 1, "provider": "demo", "state": {"cursor": "opaque"}}
        await repo.save_batch(session, **key, checkpoint=checkpoint, observed=10, published=10, now=NOW)
        await session.commit()
        await repo.release(session, **key, now=NOW, status="retry", next_at=NOW+timedelta(seconds=30),
                           failures=1, error_category="TimeoutError", observed=2, published=1)
        await session.commit()
    async with factory() as session:
        saved = await session.get(Source, 1)
        assert saved.checkpoint_value == checkpoint
        assert saved.last_attempt_at is not None and saved.last_collected_at is None
        run = await session.get(Run, source.collection_cycle_id)
        assert (run.batches, run.observed, run.published, run.errors) == (1,12,11,1)
        assert await repo.claim(session, provider_codes=("unimplemented",), now=NOW, lease_seconds=60) is None
    await engine.dispose()
