import pytest

from scaffold.ai import AIClient, ResponseMode
from scaffold.ai.contracts import ChatMessage
from scaffold.config import AIProvider, Settings


@pytest.mark.asyncio
async def test_ai_client_memory_basic_text() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@127.0.0.1:3306/db",
            "ai_provider": AIProvider.MEMORY,
        },
    )
    client = AIClient.from_settings(settings)
    out = await client.basic("hello", ResponseMode.TEXT)
    assert out.as_text().startswith("[memory:basic]")
    assert "hello" in out.as_text()


@pytest.mark.asyncio
async def test_ai_client_memory_basic_json() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@127.0.0.1:3306/db",
            "ai_provider": AIProvider.MEMORY,
        },
    )
    client = AIClient.from_settings(settings)
    out = await client.basic("ping", ResponseMode.JSON)
    data = out.as_json()
    assert data.get("ok") is True
    assert data.get("echo") == "ping"


@pytest.mark.asyncio
async def test_ai_client_custom_messages() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@127.0.0.1:3306/db",
            "ai_provider": AIProvider.MEMORY,
        },
    )
    client = AIClient.from_settings(settings)
    msgs = [
        ChatMessage(role="system", content="You are terse."),
        ChatMessage(role="user", content="first"),
    ]
    out = await client.intermediate("", ResponseMode.TEXT, messages=msgs)
    assert "first" in out.as_text()
