"""Mock LLM provider for testing.

This module provides MockLLMProvider, a configurable mock implementation
of LLMProvider for unit testing without real API calls.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from treehouse.llm.provider import (
    LLMError,
    LLMProvider,
    LLMRequest,
    LLMResponse,
)


@dataclass
class MockConfig:
    """Configuration for MockLLMProvider behavior.

    Attributes:
        default_response: Default response content when no canned response matches.
        canned_responses: Dict mapping prompt substrings to responses.
        simulate_delay_ms: Simulated latency in milliseconds (0 = no delay).
        fail_after: Fail after N successful calls (None = never fail).
        failure_error: The error to raise when failing.
        response_callback: Optional callback for dynamic responses.
        cost_per_1k_tokens: Simulated cost per 1k tokens (USD).
        cost_per_call: Fixed cost added to every response (USD).
    """

    default_response: str = "This is a mock response."
    canned_responses: dict[str, str] = field(default_factory=dict)
    simulate_delay_ms: float = 0.0
    fail_after: int | None = None
    failure_error: LLMError | None = None
    response_callback: Callable[[LLMRequest], str] | None = None
    cost_per_1k_tokens: float = 0.0
    cost_per_call: float = 0.0


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing.

    Provides configurable behavior for unit tests:
    - Canned responses based on prompt content
    - Simulated latency
    - Configurable failures
    - Token count simulation

    Example:
        config = MockConfig(
            canned_responses={"hello": "Hi there!"},
            simulate_delay_ms=100,
        )
        provider = MockLLMProvider(config)
        response = await provider.complete(LLMRequest(prompt="hello world"))
        assert response.content == "Hi there!"
    """

    def __init__(self, config: MockConfig | None = None, model: str = "mock-model"):
        """Initialize the mock provider.

        Args:
            config: Optional MockConfig for behavior customization.
            model: Model name to report in responses.
        """
        self._config = config or MockConfig()
        self._model = model
        self._call_count = 0
        self._requests: list[LLMRequest] = []

    @property
    def model_name(self) -> str:
        """Return the mock model name."""
        return self._model

    @property
    def call_count(self) -> int:
        """Return the number of complete() calls made."""
        return self._call_count

    @property
    def requests(self) -> list[LLMRequest]:
        """Return all requests received (for test assertions)."""
        return self._requests.copy()

    def last_request(self) -> LLMRequest | None:
        """Return the most recent request, or None."""
        return self._requests[-1] if self._requests else None

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a mock response based on configuration.

        Args:
            request: The LLMRequest to process.

        Returns:
            LLMResponse with mock content and simulated metrics.

        Raises:
            LLMError: If configured to fail.
        """
        self._call_count += 1
        self._requests.append(request)

        # Check if we should fail
        if self._config.fail_after is not None:
            if self._call_count > self._config.fail_after:
                error = self._config.failure_error or LLMError("Mock failure")
                raise error

        # Simulate delay
        start_time = time.perf_counter()
        if self._config.simulate_delay_ms > 0:
            await asyncio.sleep(self._config.simulate_delay_ms / 1000)

        # Determine response content
        content = self._get_response_content(request)

        # Calculate simulated metrics
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        prompt_tokens = self.count_tokens(request.prompt)
        if request.system_prompt:
            prompt_tokens += self.count_tokens(request.system_prompt)
        completion_tokens = self.count_tokens(content)
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(total_tokens)

        return LLMResponse(
            content=content,
            reasoning=None,
            tokens_used={
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": total_tokens,
            },
            model=self._model,
            cost=cost,
            latency_ms=elapsed_ms,
            raw_response={"mock": True, "request": request.prompt},
        )

    def _get_response_content(self, request: LLMRequest) -> str:
        """Determine response content based on config."""
        # Check callback first
        if self._config.response_callback:
            return self._config.response_callback(request)

        # Check canned responses
        for trigger, response in self._config.canned_responses.items():
            if trigger.lower() in request.prompt.lower():
                return response

        return self._config.default_response

    def _calculate_cost(self, total_tokens: int) -> float:
        if self._config.cost_per_1k_tokens <= 0 and self._config.cost_per_call <= 0:
            return 0.0
        token_cost = (total_tokens / 1000) * self._config.cost_per_1k_tokens
        return self._config.cost_per_call + token_cost

    def reset(self) -> None:
        """Reset call count and recorded requests."""
        self._call_count = 0
        self._requests.clear()
