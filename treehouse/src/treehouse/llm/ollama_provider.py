"""Ollama LLM provider for local model inference.

This module provides OllamaProvider, which connects to a local Ollama
server for LLM completions. Cost is always 0 for local inference.

Ollama API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from treehouse.llm.provider import (
    LLMConnectionError,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMResponseError,
)


class OllamaProvider(LLMProvider):
    """LLM provider for local Ollama server.

    Connects to Ollama's HTTP API (default http://localhost:11434) to run
    local models like llama3, mistral, phi3, etc.

    Example:
        provider = OllamaProvider(model="llama3:8b")
        request = LLMRequest(prompt="What is 2+2?")
        response = await provider.complete(request)
        print(response.content)

    Attributes:
        model: The model name to use (e.g., "llama3:8b", "mistral").
        base_url: The Ollama server URL.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ):
        """Initialize the Ollama provider.

        Args:
            model: Model name to use (must be pulled in Ollama first).
            base_url: Ollama server URL.
            timeout: Request timeout in seconds.
        """
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to Ollama.

        Args:
            request: The LLMRequest with prompt and parameters.

        Returns:
            LLMResponse with content, token usage, and metadata.

        Raises:
            LLMConnectionError: If Ollama server is unreachable.
            LLMResponseError: If the response is malformed.
        """
        start_time = time.perf_counter()

        # Build the API request payload
        payload = self._build_payload(request)

        try:
            raw_response = self._send_request(payload)
        except HTTPError as e:
            raise LLMConnectionError(
                f"Ollama request failed with status {e.code}: {e.reason}"
            ) from e
        except URLError as e:
            raise LLMConnectionError(
                f"Failed to connect to Ollama at {self._base_url}: {e}"
            ) from e

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return self._parse_response(raw_response, elapsed_ms)

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """Build the Ollama API payload from an LLMRequest."""
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": request.prompt,
            "stream": False,
        }

        # Add system prompt if provided
        if request.system_prompt:
            payload["system"] = request.system_prompt

        # Build options dict for generation parameters
        options: dict[str, Any] = {}

        if request.temperature is not None:
            options["temperature"] = request.temperature

        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens

        if request.stop_sequences:
            options["stop"] = request.stop_sequences

        if options:
            payload["options"] = options

        # JSON mode: instruct the model to output JSON
        if request.json_mode:
            payload["format"] = "json"

        return payload

    def _send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send HTTP request to Ollama and return parsed response."""
        url = f"{self._base_url}/api/generate"
        data = json.dumps(payload).encode("utf-8")

        req = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(req, timeout=self._timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)

    def _parse_response(self, raw: dict[str, Any], elapsed_ms: float) -> LLMResponse:
        """Parse Ollama API response into LLMResponse."""
        try:
            content = raw.get("response", "")

            # Ollama provides token counts in the response
            prompt_tokens = raw.get("prompt_eval_count", 0)
            completion_tokens = raw.get("eval_count", 0)

            return LLMResponse(
                content=content,
                reasoning=None,  # Ollama doesn't provide separate reasoning
                tokens_used={
                    "prompt": prompt_tokens,
                    "completion": completion_tokens,
                    "total": prompt_tokens + completion_tokens,
                },
                model=raw.get("model", self._model),
                cost=0.0,  # Local inference is free
                latency_ms=elapsed_ms,
                raw_response=raw,
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise LLMResponseError(f"Failed to parse Ollama response: {e}") from e

    def estimate_cost(self, request: LLMRequest) -> float:
        """Estimate cost for Ollama (always 0, local inference)."""
        return 0.0

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        This is a rough estimate. For accurate counts, use the model's
        tokenizer directly.

        Args:
            text: Text to count tokens for.

        Returns:
            Estimated token count.
        """
        # Rough heuristic: ~4 characters per token
        return len(text) // 4
