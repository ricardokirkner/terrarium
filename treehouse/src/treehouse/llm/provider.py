"""LLM provider interface for Treehouse.

This module defines the contract for LLM providers:
- LLMRequest: Input to an LLM call
- LLMResponse: Output from an LLM call
- LLMProvider: Abstract base class for provider implementations

Any provider (Ollama, OpenAI, Anthropic, Gemini) should implement LLMProvider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMRequest:
    """Request to an LLM provider.

    Attributes:
        prompt: The user prompt/message to send.
        system_prompt: Optional system prompt for context/instructions.
        max_tokens: Maximum tokens in the response (None = provider default).
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).
        stop_sequences: Optional list of sequences that stop generation.
        json_mode: If True, request JSON-formatted output.
        metadata: Optional metadata for tracking/debugging.
    """

    prompt: str
    system_prompt: str | None = None
    max_tokens: int | None = None
    temperature: float = 0.7
    stop_sequences: list[str] | None = None
    json_mode: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Response from an LLM provider.

    Attributes:
        content: The generated text content.
        reasoning: Optional chain-of-thought or reasoning (if model provides it).
        tokens_used: Token usage dict with 'prompt', 'completion', 'total' keys.
        model: The model identifier used.
        cost: Estimated cost in USD (0.0 for local models).
        latency_ms: Time taken for the request in milliseconds.
        raw_response: The raw response from the provider for debugging.
    """

    content: str
    reasoning: str | None = None
    tokens_used: dict[str, int] = field(
        default_factory=lambda: {
            "prompt": 0,
            "completion": 0,
            "total": 0,
        }
    )
    model: str = ""
    cost: float = 0.0
    latency_ms: float = 0.0
    raw_response: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert response to a dictionary for serialization."""
        return {
            "content": self.content,
            "reasoning": self.reasoning,
            "tokens_used": self.tokens_used,
            "model": self.model,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            # raw_response is intentionally omitted (may not be serializable)
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMResponse:
        """Create response from a dictionary."""
        return cls(
            content=data["content"],
            reasoning=data.get("reasoning"),
            tokens_used=data.get(
                "tokens_used", {"prompt": 0, "completion": 0, "total": 0}
            ),
            model=data.get("model", ""),
            cost=data.get("cost", 0.0),
            latency_ms=data.get("latency_ms", 0.0),
            raw_response=None,
        )


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Subclasses must implement:
    - complete(): Send a request and get a response
    - estimate_cost(): Estimate cost before sending (optional accuracy)
    - count_tokens(): Count tokens in text (for cost estimation)

    Example:
        provider = OllamaProvider(model="llama3:8b")
        request = LLMRequest(prompt="What is 2+2?")
        response = await provider.complete(request)
        print(response.content)
    """

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to the LLM.

        Args:
            request: The LLMRequest with prompt and parameters.

        Returns:
            LLMResponse with content, token usage, and metadata.

        Raises:
            LLMError: If the request fails.
        """
        pass

    def estimate_cost(self, request: LLMRequest) -> float:
        """Estimate the cost of a request before sending.

        Args:
            request: The LLMRequest to estimate.

        Returns:
            Estimated cost in USD. Returns 0.0 for local models.
        """
        return 0.0

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: The text to count tokens for.

        Returns:
            Estimated token count. Default is len(text) // 4.
        """
        # Simple heuristic: ~4 characters per token on average
        return len(text) // 4

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name/identifier."""
        pass


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class LLMConnectionError(LLMError):
    """Raised when connection to the LLM provider fails."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limited by the provider."""

    pass


class LLMResponseError(LLMError):
    """Raised when the response is malformed or invalid."""

    pass
