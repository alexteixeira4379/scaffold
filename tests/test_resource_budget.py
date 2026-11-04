"""Real Redis admission tests; point TEST_SECURITY_REDIS_URL at an isolated Redis."""
import os
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from redis.asyncio import Redis

from scaffold.security.budget import BudgetPolicy, budget_keys, consume_budget, resource_budget


@pytest.fixture
async def budget_redis(monkeypatch):
    url = os.getenv("TEST_SECURITY_REDIS_URL")
    if not url:
        pytest.skip("TEST_SECURITY_REDIS_URL required for isolated Redis admission tests")
    monkeypatch.setenv("CACHE_URL", url)
    scope = "test-" + uuid4().hex
    async with Redis.from_url(url, decode_responses=True) as client:
        await client.ping()
        yield scope, client
        keys = [key async for key in client.scan_iter(match=budget_keys(scope, "x")[0].split('actor:')[0] + '*')]
        if keys:
            await client.delete(*keys)


@pytest.mark.asyncio
async def test_global_budget_cannot_be_reset_by_rotating_actor(budget_redis):
    scope, client = budget_redis
    policy = replace(BudgetPolicy(), global_limit=2, actor_limit=2)
    await consume_budget(scope, "actor-a", policy=policy)
    await consume_budget(scope, "actor-b", policy=policy)
    with pytest.raises(HTTPException) as error:
        await consume_budget(scope, "actor-c", policy=policy)
    assert error.value.status_code == 429
    assert int(error.value.headers['Retry-After']) > 0


@pytest.mark.asyncio
async def test_concurrency_lease_released_and_queue_execution_not_double_charged(budget_redis):
    scope, client = budget_redis
    policy = replace(BudgetPolicy(), actor_concurrency=1)
    await consume_budget(scope, "actor", policy=policy)
    async with resource_budget(scope, "actor", units=0, policy=policy):
        with pytest.raises(HTTPException) as error:
            async with resource_budget(scope, "actor", units=0, policy=policy):
                pytest.fail("Second overlapping execution admitted")
        assert error.value.status_code == 429
        assert await client.get(budget_keys(scope, "actor")[0]) == '1'
    async with resource_budget(scope, "actor", units=0, policy=policy):
        assert await client.zcard(budget_keys(scope, "actor")[4]) == 1
    assert await client.zcard(budget_keys(scope, "actor")[4]) == 0


@pytest.mark.asyncio
async def test_unavailable_quota_backend_fails_closed(monkeypatch):
    monkeypatch.setenv("CACHE_URL", "redis://127.0.0.1:1/0")
    with pytest.raises(HTTPException) as error:
        await consume_budget("test-unavailable", "actor")
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_zero_unit_admission_without_lease_rejected(budget_redis):
    scope, client = budget_redis
    with pytest.raises(HTTPException) as error:
        await consume_budget(scope, "actor", units=0)
    assert error.value.status_code == 503
    assert await client.get(budget_keys(scope, "actor")[0]) is None
