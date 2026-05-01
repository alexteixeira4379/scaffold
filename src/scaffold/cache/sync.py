from __future__ import annotations

import atexit
import asyncio
import threading
from collections.abc import Awaitable
from concurrent.futures import Future
from typing import TypeVar


T = TypeVar("T")


class _BackgroundLoopRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

    def run(self, coro: Awaitable[T]) -> T:
        loop = self._ensure_loop()
        future: Future[T] = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def close(self) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
            if loop is None or loop.is_closed():
                self._loop = None
                self._thread = None
                return
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=1.0)

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None and not self._loop.is_closed():
                return self._loop
            self._ready.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        self._ready.wait()
        if self._loop is None:
            raise RuntimeError("background event loop failed to start")
        return self._loop

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()
        loop.close()
        self._loop = None


_background_runner = _BackgroundLoopRunner()
atexit.register(_background_runner.close)


def run_sync(coro: Awaitable[T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _background_runner.run(coro)
    return _background_runner.run(coro)
