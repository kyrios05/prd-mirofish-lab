from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.config import settings
from app.services.openai_llm_service import OpenAILLMService


async def test_text_and_streaming_requests_send_the_configured_high_effort(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-only")
    monkeypatch.setattr(settings, "openai_model", "gpt-6.1-terra")
    monkeypatch.setattr(settings, "openai_reasoning_effort", "high")
    service = OpenAILLMService()

    async def events():
        yield SimpleNamespace(type="response.output_text.delta", delta="connected")

    create = AsyncMock(side_effect=[SimpleNamespace(output_text="connected"), events()])
    service._client = SimpleNamespace(responses=SimpleNamespace(create=create))
    assert await service.chat([{"role": "user", "content": "Check."}]) == "connected"
    tokens = [item async for item in service.stream_chat([{"role": "user", "content": "Check."}])]
    assert tokens == [{"content": "connected"}]
    assert create.await_count == 2
    for call in create.await_args_list:
        assert call.kwargs["model"] == "gpt-6.1-terra"
        assert call.kwargs["reasoning"] == {"effort": "high"}
