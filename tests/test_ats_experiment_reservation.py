"""Reservation durability and fencing using a disposable in-memory database."""
from datetime import datetime, timedelta
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from scaffold.models.ats.ats_providers import AtsProvider as Provider
from scaffold.models.ats.ats_discovery_sources import AtsDiscoverySource as Source
from scaffold.repositories.ats_collection_repository import AtsCollectionRepository, LeaseLostError


@pytest.mark.asyncio
async def test_provider_lifetime_budget_survives_changed_config_channel_and_session():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Provider.__table__.create(c))
        await conn.run_sync(lambda c: Source.__table__.create(c))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 10, 3, 12)
    async with factory.begin() as session:
        session.add(Provider(id=1, code='quickin', name='Quickin', kind='ats'))
        for id, tenant in [(1, 'n5x'), (2, 'other')]:
            session.add(Source(id=id, ats_provider_id=1, code=tenant, name=tenant, kind='ats',
                base_url=f'https://jobs.quickin.io/{tenant}', collection_lease_token='token',
                collection_lease_until=now + timedelta(minutes=5), checkpoint_value={},
                discovery_metadata={'preserved': True}))
    repo = AtsCollectionRepository()
    args = dict(source_id=1, token='token', now=now, provider_code='quickin', experiment_id='pilot', candidate_id=42, job_url='https://jobs.quickin.io/n5x/jobs/123')
    async with factory.begin() as session:
        assert await repo.reserve_experiment(session, **args)
    async with factory.begin() as session:
        assert not await repo.reserve_experiment(session, **{**args, 'experiment_id': 'changed', 'job_url': 'another'})
    async with factory.begin() as session:
        assert not await repo.reserve_experiment(session, **{**args, 'source_id': 2})
        source = await session.get(Source, 1)
        assert source.discovery_metadata['preserved'] is True
        assert source.discovery_metadata['bounded_experiment']['reserved'] is True
    async with factory.begin() as session:
        with pytest.raises(LeaseLostError):
            await repo.reserve_experiment(session, **{**args, 'token': 'stale'})
    await engine.dispose()
