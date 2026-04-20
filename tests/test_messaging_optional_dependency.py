import builtins

import pytest

from scaffold.messaging import rabbitmq, sync


def _block_aio_pika_import(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name == "aio_pika":
            raise ModuleNotFoundError("No module named 'aio_pika'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_rabbitmq_dependency_error_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_aio_pika_import(monkeypatch)

    with pytest.raises(RuntimeError, match=r"Install scaffold\[messaging\]"):
        rabbitmq._import_aio_pika()


def test_sync_dependency_error_is_explicit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _block_aio_pika_import(monkeypatch)

    with pytest.raises(SystemExit, match="1"):
        sync._import_aio_pika()

    captured = capsys.readouterr()
    assert "Install scaffold[messaging]" in captured.err
