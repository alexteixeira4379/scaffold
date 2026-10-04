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


@pytest.mark.asyncio
async def test_exact_grant_allocates_third_slot_once_and_preserves_history():
    from scaffold.repositories.ats_experiment_budget import grant_additional, locked_budget
    engine=create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Provider.__table__.create(c))
        await conn.run_sync(lambda c: Source.__table__.create(c))
    factory=async_sessionmaker(engine,expire_on_commit=False)
    now=datetime(2026,10,4,12)
    urls=['https://loft.teamtailor.com/jobs/6596760-senior-software-engineer-ai',
          'https://jobs.quickin.io/globalti/jobs/6abe9ea55087e300138b17fa',
          'https://arvo.teamtailor.com/jobs/8194021-sr-staff-data-engineer']
    async with factory.begin() as s:
        for id,code in [(1,'inhire'),(2,'teamtailor'),(3,'quickin')]:
            s.add(Provider(id=id,code=code,name=code,kind='ats'))
        for id,pid,base in [(1,2,'https://loft.teamtailor.com'),(2,3,'https://jobs.quickin.io/globalti'),(3,2,'https://arvo.teamtailor.com'),(4,1,'https://lyncas.inhire.app')]:
            s.add(Source(id=id,ats_provider_id=pid,code=str(id),name=str(id),kind='ats',base_url=base,
                qualification_status='qualified',collection_lease_token='lease',collection_lease_until=now+timedelta(minutes=5),checkpoint_value={},discovery_metadata={'other':True}))
    repo=AtsCollectionRepository()
    async def reserve(s,source_id,provider,url,**overrides):
        args=dict(source_id=source_id,token='lease',now=now,provider_code=provider,
                  experiment_id='original',candidate_id=42,job_url=url)
        return await repo.reserve_experiment(s,**{**args,**overrides})
    async with factory.begin() as s:
        assert await reserve(s,1,'teamtailor',urls[0])
        assert await reserve(s,2,'quickin',urls[1])
        (await s.get(Source,3)).collection_lease_until=None
    args=dict(source_id=3,experiment_id='original',candidate_id=42,job_url=urls[2],
              grant_id='grant-third',reason='Explicit pilot continuation',previous_urls=urls[:2],now=now)
    async with factory.begin() as s:
        before=(await s.get(Source,1)).discovery_metadata.copy()
        for changes in ({'candidate_id':99}, {'experiment_id':'renamed'},
                        {'previous_urls':[urls[0],urls[2]]}, {'source_id':1}):
            with pytest.raises(ValueError):
                await grant_additional(s,**{**args,**changes},apply=True)
        assert (await grant_additional(s,**args))['status']=='planned'
        assert (await s.get(Source,3)).discovery_metadata=={'other':True}
        assert (await grant_additional(s,**args,apply=True))['status']=='allocated'
    async with factory.begin() as s:
        assert (await grant_additional(s,**args,apply=True))['status']=='already_allocated'
        with pytest.raises(ValueError,match='changed'):
            await grant_additional(s,**{**args,'reason':'different'},apply=True)
        (await s.get(Source,3)).collection_lease_until=now+timedelta(minutes=5)
    async with factory.begin() as s:
        assert not await reserve(s,4,'inhire','https://lyncas.inhire.app/vagas/00000000-0000-0000-0000-000000000001')
        assert not await reserve(s,3,'teamtailor',urls[2],experiment_id='renamed')
        assert await reserve(s,3,'teamtailor',urls[2])
    async with factory.begin() as s:
        assert not await reserve(s,3,'teamtailor',urls[2])
        assert not await reserve(s,1,'teamtailor',urls[0])
        assert not await reserve(s,4,'inhire','https://lyncas.inhire.app/vagas/00000000-0000-0000-0000-000000000002',experiment_id='other',candidate_id=99)
        assert (await s.get(Source,1)).discovery_metadata==before
        codes,reservations,grants=await locked_budget(s)
        assert len(reservations)==3 and len(grants)==1 and grants[urls[2]]['consumed']
        assert (await grant_additional(s,**args,apply=True))['status']=='already_allocated'
        source=await s.get(Source,3)
        metadata=dict(source.discovery_metadata)
        metadata['bounded_experiment']={**metadata['bounded_experiment'],'candidate_id':99}
        source.discovery_metadata=metadata
        await s.flush()
        with pytest.raises(ValueError,match='history_mismatch'):
            await locked_budget(s)
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('metadata', [{'bounded_experiment':{}}, {'bounded_experiment_grant':{}}, []])
async def test_unknown_or_malformed_budget_fails_closed(metadata):
    from scaffold.repositories.ats_experiment_budget import locked_budget
    engine=create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Provider.__table__.create(c))
        await conn.run_sync(lambda c: Source.__table__.create(c))
    factory=async_sessionmaker(engine)
    async with factory.begin() as s:
        s.add(Provider(id=1,code='teamtailor',name='TT',kind='ats'))
        s.add(Source(id=1,ats_provider_id=1,code='one',name='One',kind='ats',base_url='https://loft.teamtailor.com',checkpoint_value={},discovery_metadata=metadata))
    async with factory.begin() as s:
        with pytest.raises(ValueError,match='malformed'):
            await locked_budget(s)
    await engine.dispose()


@pytest.mark.asyncio
async def test_over_100_sources_never_silently_ignores_budget_rows():
    from scaffold.repositories.ats_experiment_budget import locked_budget
    engine=create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Provider.__table__.create(c))
        await conn.run_sync(lambda c: Source.__table__.create(c))
    factory=async_sessionmaker(engine)
    async with factory.begin() as s:
        s.add(Provider(id=1,code='inhire',name='Inhire',kind='ats'))
        for i in range(101):
            s.add(Source(id=i+1,ats_provider_id=1,code=str(i),name=str(i),kind='ats',base_url=f'https://tenant{i}.inhire.app',checkpoint_value={}))
    async with factory.begin() as s:
        with pytest.raises(ValueError,match='source_limit_exceeded_100'):
            await locked_budget(s)
    await engine.dispose()


@pytest.mark.asyncio
async def test_provider_locks_use_individual_primary_keys_in_fixed_order():
    from types import SimpleNamespace
    from sqlalchemy.dialects import mysql
    from scaffold.repositories.ats_experiment_budget import locked_budget
    class Session:
        def __init__(self): self.locks=[]
        async def scalars(self, stmt):
            return SimpleNamespace(all=lambda:[SimpleNamespace(id=9,code='teamtailor'),SimpleNamespace(id=3,code='inhire'),SimpleNamespace(id=7,code='quickin')])
        async def scalar(self, stmt):
            q=stmt.compile(dialect=mysql.dialect())
            assert 'FOR UPDATE' in str(q) and 'ats_providers.id =' in str(q)
            self.locks.append(q.params['id_1'])
        async def execute(self, stmt):
            q=stmt.compile(dialect=mysql.dialect())
            assert 'ats_provider_id IN' in str(q) and 101 in q.params.values() and 'FOR UPDATE' in str(q)
            return SimpleNamespace(all=lambda:[])
    session=Session()
    await locked_budget(session)
    assert session.locks==[3,7,9]
