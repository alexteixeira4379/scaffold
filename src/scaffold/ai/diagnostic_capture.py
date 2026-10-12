"""Opt-in request capture scoped to one application task; never emits payloads to stdout."""

from contextvars import ContextVar

capture = ContextVar("application_ai_capture", default=None)


def emit(name, **fields):
    observer = capture.get()
    if observer is not None:
        observer.record(name, **fields)
