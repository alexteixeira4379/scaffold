"""Atomic shared admission for Browserless sessions and account isolation."""

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

from scaffold.messaging.processing import InfrastructureUnavailable

logger = logging.getLogger(__name__)


class AdmissionUnavailable(InfrastructureUnavailable):
    pass


@dataclass
class SlotLease:
    owner: str = ""
    remote_opened: bool = False
    remote_closed: bool = False


class SlotAdmission:
    def __init__(
        self,
        cache,
        *,
        key: str,
        limit: int,
        ttl_s: int = 360,
        acquire_timeout_s: float = 15.0,
        owns_cache: bool = False,
        max_browser_session_s: int | None = None,
    ):
        if not key or limit <= 0 or ttl_s <= 0 or acquire_timeout_s <= 0:
            raise ValueError("invalid slot admission configuration")
        if max_browser_session_s is not None and ttl_s < max_browser_session_s + 30:
            raise ValueError("slot_ttl_must_outlive_browser_session_and_cleanup_margin")
        self.cache, self.key, self.limit = cache, key, limit
        self.ttl_s, self.acquire_timeout_s, self.owns_cache = ttl_s, acquire_timeout_s, owns_cache
        self.max_browser_session_s = max_browser_session_s
        self.backend_timeout_s = min(5.0, ttl_s / 2)

    @asynccontextmanager
    async def lease(self):
        owner = str(uuid4())
        connected = acquired = False
        stop = asyncio.Event()
        lease_lost = asyncio.Event()
        owner_task = asyncio.current_task()
        renew_task = None
        slot = SlotLease(owner=owner)
        try:
            if self.owns_cache:
                await asyncio.wait_for(self.cache.connect(), timeout=self.backend_timeout_s)
                connected = True
            deadline = asyncio.get_running_loop().time() + self.acquire_timeout_s
            while not acquired:
                try:
                    acquired = await asyncio.wait_for(
                        self.cache.acquire_pool_slot(self.key, owner, self.limit, self.ttl_s),
                        timeout=self.backend_timeout_s,
                    )
                except Exception as exc:
                    raise AdmissionUnavailable("slot_backend_unavailable") from exc
                if acquired:
                    break
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise AdmissionUnavailable("slot_capacity_exhausted")
                await asyncio.sleep(min(remaining, random.uniform(0.1, 0.3)))
            renew_task = asyncio.create_task(self._renew(owner, stop, lease_lost, owner_task))
            try:
                yield slot
            except asyncio.CancelledError:
                if lease_lost.is_set():
                    raise AdmissionUnavailable("slot_lease_lost") from None
                raise
            if lease_lost.is_set():
                raise AdmissionUnavailable("slot_lease_lost")
        finally:
            stop.set()
            if renew_task is not None:
                renew_task.cancel()
                try:
                    await renew_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.warning("slot_renewal_failed key=%s", self.key, exc_info=True)
            if acquired and (not slot.remote_opened or slot.remote_closed):
                try:
                    await asyncio.wait_for(
                        self.cache.release_pool_slot(self.key, owner),
                        timeout=self.backend_timeout_s,
                    )
                except Exception:
                    logger.warning("slot_release_failed key=%s", self.key, exc_info=True)
            elif acquired:
                logger.error(
                    "remote_browser_close_unverified key=%s owner=%s; holding slot until bounded server timeout",
                    self.key,
                    owner,
                )
            if connected:
                try:
                    await asyncio.wait_for(self.cache.close(), timeout=self.backend_timeout_s)
                except Exception:
                    logger.warning("slot_cache_close_failed key=%s", self.key, exc_info=True)

    async def _renew(
        self,
        owner: str,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
        owner_task: asyncio.Task | None,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=min(30, self.ttl_s / 3))
            except TimeoutError:
                try:
                    renewed = await asyncio.wait_for(
                        self.cache.renew_pool_slot(self.key, owner, self.ttl_s),
                        timeout=self.backend_timeout_s,
                    )
                except Exception:
                    logger.exception("slot_renewal_failed key=%s", self.key)
                    lease_lost.set()
                    if owner_task is not None:
                        owner_task.cancel()
                    return
                if not renewed:
                    logger.error("slot_lease_lost key=%s", self.key)
                    lease_lost.set()
                    if owner_task is not None:
                        owner_task.cancel()
                    return
