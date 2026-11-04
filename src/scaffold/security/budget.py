"""Atomic weighted budgets and renewable admission leases for external resources.

Every key of one scope shares a Redis Cluster slot. Failed external operations
still consume budget; retries cannot turn failures into free resource use.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import HTTPException
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

RESERVE = """
local now=tonumber(ARGV[1]); local units=tonumber(ARGV[2])
local limits={tonumber(ARGV[3]),tonumber(ARGV[4]),tonumber(ARGV[5]),tonumber(ARGV[6])}
if units>0 then
 for i=1,4 do
  if tonumber(redis.call('GET',KEYS[i]) or '0')+units>limits[i] then
   return {0,math.max(1,redis.call('TTL',KEYS[i]))}
  end
 end
end
for i=5,6 do redis.call('ZREMRANGEBYSCORE',KEYS[i],'-inf',now) end
if ARGV[7]~='' then
 if redis.call('ZCARD',KEYS[5])>=tonumber(ARGV[8]) or redis.call('ZCARD',KEYS[6])>=tonumber(ARGV[9]) then return {0,2} end
end
if units>0 then
 for i=1,4 do
  local n=redis.call('INCRBY',KEYS[i],units)
  if n==units then redis.call('EXPIRE',KEYS[i],i<=2 and tonumber(ARGV[10]) or 60) end
 end
end
if ARGV[7]~='' then
 for i=5,6 do
  redis.call('ZADD',KEYS[i],now+tonumber(ARGV[11]),ARGV[7]); redis.call('EXPIRE',KEYS[i],tonumber(ARGV[11])*2)
 end
end
return {1,redis.call('TTL',KEYS[1])}
"""
RENEW = """
for i=1,2 do if not redis.call('ZSCORE',KEYS[i],ARGV[1]) then return 0 end end
for i=1,2 do redis.call('ZADD',KEYS[i],tonumber(ARGV[2])+tonumber(ARGV[3]),ARGV[1]);redis.call('EXPIRE',KEYS[i],tonumber(ARGV[3])*2) end
return 1
"""
RELEASE = "for i=1,2 do redis.call('ZREM',KEYS[i],ARGV[1]) end; return 1"


@dataclass(frozen=True)
class BudgetPolicy:
    actor_limit: int = 60
    global_limit: int = 3000
    actor_burst: int = 30
    global_burst: int = 120
    actor_concurrency: int = 2
    global_concurrency: int = 8
    window_seconds: int = 86400
    lease_seconds: int = 90
    timeout_seconds: int = 180

    @classmethod
    def load(cls, scope: str) -> BudgetPolicy:
        prefix = 'SECURITY_' + scope.upper().replace('-', '_') + '_'
        defaults = {
            "resume-anonymous": cls(actor_limit=20, global_limit=200, actor_burst=5, global_burst=20, actor_concurrency=1, global_concurrency=3, timeout_seconds=120),
            "billing-write": cls(actor_limit=20, global_limit=1000, actor_burst=5, global_burst=50, timeout_seconds=60),
            "billing-read": cls(actor_limit=120, global_limit=10000, actor_burst=20, global_burst=200, timeout_seconds=30),
            "whatsapp-media": cls(actor_limit=10, global_limit=500, actor_burst=2, global_burst=20,
                                  actor_concurrency=1, global_concurrency=3, timeout_seconds=100),
        }.get(scope, cls())
        values = {name: int(os.getenv(prefix + name.upper(), str(getattr(defaults, name))))
                  for name in cls.__dataclass_fields__}
        if any(v < 1 for v in values.values()) or values['lease_seconds'] < 6:
            raise ValueError('Invalid resource budget configuration')
        return cls(**values)


def budget_client():
    url = os.environ.get('CACHE_URL') or os.environ.get('REDIS_URL')
    if not url:
        raise RuntimeError('Resource budget storage unavailable')
    return Redis.from_url(url, decode_responses=True, socket_connect_timeout=3, socket_timeout=3)


def budget_keys(scope: str, identity: str) -> list[str]:
    scope_hash = hashlib.sha256(scope.encode()).hexdigest()[:24]
    actor_hash = hashlib.sha256(identity.encode()).hexdigest()
    prefix = 'security:budget:{' + scope_hash + '}:'
    return [prefix + 'actor:' + actor_hash, prefix + 'global',
            prefix + 'actor-burst:' + actor_hash, prefix + 'global-burst',
            prefix + 'actor-running:' + actor_hash, prefix + 'global-running']


async def _reserve(client, scope, identity, units, token, policy):
    if (not identity or not isinstance(units, int) or isinstance(units, bool)
            or units < 0 or (units == 0 and not token)):
        raise ValueError('Invalid resource reservation')
    keys = budget_keys(scope, identity)
    # Redis TIME avoids disagreements among replica clocks.
    seconds, micros = await client.time()
    allowed, retry = await client.eval(
        RESERVE, 6, *keys, float(seconds) + float(micros) / 1_000_000, units,
        policy.actor_limit, policy.global_limit, policy.actor_burst, policy.global_burst,
        token, policy.actor_concurrency, policy.global_concurrency,
        policy.window_seconds, policy.lease_seconds)
    if not allowed:
        raise HTTPException(429, 'Limite temporário de processamento atingido. Tente novamente mais tarde.',
                            headers={'Retry-After': str(max(1, retry))})
    return keys


async def consume_budget(scope: str, identity: str, *, units: int = 1, policy: BudgetPolicy | None = None):
    """Reserve before durable queue admission; concurrency is owned by the consumer."""
    try:
        policy = policy or BudgetPolicy.load(scope)
        async with budget_client() as client:
            await _reserve(client, scope, identity, units, '', policy)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning('resource_budget_unavailable scope=%s type=%s', scope, type(exc).__name__)
        raise HTTPException(503, 'Controle de processamento temporariamente indisponível.') from exc


@asynccontextmanager
async def resource_budget(scope: str, identity: str, *, units: int = 1, policy: BudgetPolicy | None = None):
    """Charge admission and retain a distributed lease for the entire bounded call.

    units=0 acquires only a concurrency lease when a durable queue admission
    has already charged this operation's quota. consume_budget never permits zero.
    If renewal fails, cancel the protected operation immediately instead of allowing
    processing to outlive an expired lease. The reservation is never refunded.
    """
    client = None
    renewer = None
    keys = None
    token = secrets.token_hex(16)
    lost = False
    parent = asyncio.current_task()
    async def renew():
        nonlocal lost
        try:
            while True:
                await asyncio.sleep(policy.lease_seconds / 3)
                seconds, micros = await client.time()
                ok = await client.eval(RENEW, 2, *keys[4:], token,
                                       float(seconds) + float(micros) / 1_000_000, policy.lease_seconds)
                if not ok:
                    raise RuntimeError('Resource lease lost')
        except asyncio.CancelledError:
            raise
        except Exception:
            lost = True
            parent.cancel()
    try:
        policy = policy or BudgetPolicy.load(scope)
        client = budget_client()
        keys = await _reserve(client, scope, identity, units, token, policy)
        renewer = asyncio.create_task(renew())
        try:
            async with asyncio.timeout(policy.timeout_seconds):
                yield
        except asyncio.CancelledError:
            if lost:
                raise HTTPException(503, 'Controle de processamento temporariamente indisponível.') from None
            raise
        except TimeoutError:
            raise HTTPException(504, 'O processamento excedeu o tempo permitido.') from None
    except HTTPException:
        raise
    except Exception as exc:
        # Exceptions from protected business code must retain their original type.
        if keys is not None:
            raise
        logger.warning('resource_budget_unavailable scope=%s type=%s', scope, type(exc).__name__)
        raise HTTPException(503, 'Controle de processamento temporariamente indisponível.') from exc
    finally:
        if renewer:
            renewer.cancel()
            await asyncio.gather(renewer, return_exceptions=True)
        if client:
            try:
                if keys:
                    await client.eval(RELEASE, 2, *keys[4:], token)
            except Exception:
                logger.warning('resource_budget_release_pending scope=%s', scope)
            finally:
                await client.aclose()
