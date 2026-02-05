from __future__ import annotations

import json
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest

from treehouse.llm.ollama_provider import OllamaProvider
from treehouse.llm.provider import LLMConnectionError, LLMRequest, LLMResponseError


def test_build_payload_includes_options():
    provider = OllamaProvider(model="test-model")
    request = LLMRequest(
        prompt="hi",
        system_prompt="system",
        max_tokens=50,
        temperature=0.3,
        stop_sequences=["STOP"],
        json_mode=True,
    )

    payload = provider._build_payload(request)
    assert payload["model"] == "test-model"
    assert payload["system"] == "system"
    assert payload["format"] == "json"
    assert payload["options"]["temperature"] == 0.3
    assert payload["options"]["num_predict"] == 50
    assert payload["options"]["stop"] == ["STOP"]


@pytest.mark.asyncio
async def test_complete_parses_response(monkeypatch):
    provider = OllamaProvider(model="test-model")

    def fake_send(_):
        return {
            "response": "ok",
            "prompt_eval_count": 2,
            "eval_count": 3,
            "model": "test-model",
        }

    monkeypatch.setattr(provider, "_send_request", fake_send)

    response = await provider.complete(LLMRequest(prompt="hi"))
    assert response.content == "ok"
    assert response.tokens_used["total"] == 5
    assert response.model == "test-model"
    assert response.cost == 0.0


@pytest.mark.asyncio
async def test_complete_raises_connection_error(monkeypatch):
    provider = OllamaProvider()

    def fake_send(_):
        raise HTTPError("http://localhost", 500, "boom", MagicMock(), None)

    monkeypatch.setattr(provider, "_send_request", fake_send)

    with pytest.raises(LLMConnectionError):
        await provider.complete(LLMRequest(prompt="hi"))


@pytest.mark.asyncio
async def test_complete_raises_url_error(monkeypatch):
    provider = OllamaProvider()

    def fake_send(_):
        raise URLError("offline")

    monkeypatch.setattr(provider, "_send_request", fake_send)

    with pytest.raises(LLMConnectionError):
        await provider.complete(LLMRequest(prompt="hi"))


def test_parse_response_invalid():
    provider = OllamaProvider()
    with pytest.raises(LLMResponseError):
        provider._parse_response(None, 1.0)  # type: ignore[arg-type]


def test_estimate_cost_and_count_tokens():
    provider = OllamaProvider()
    assert provider.estimate_cost(LLMRequest(prompt="hi")) == 0.0
    assert provider.count_tokens("1234") == 1


def test_model_name_property():
    provider = OllamaProvider(model="tiny")
    assert provider.model_name == "tiny"


def test_send_request_parses_response(monkeypatch):
    provider = OllamaProvider(base_url="http://localhost:11434")

    class FakeResponse:
        def __init__(self) -> None:
            self._data = {"response": "ok"}

        def read(self) -> bytes:
            return json.dumps(self._data).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(_req, timeout=0):
        assert timeout == provider._timeout
        return FakeResponse()

    monkeypatch.setattr("treehouse.llm.ollama_provider.urlopen", fake_urlopen)

    response = provider._send_request({"prompt": "hi"})
    assert response["response"] == "ok"
