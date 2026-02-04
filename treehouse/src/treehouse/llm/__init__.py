"""LLM integration for Treehouse behavior trees.

This package provides:
- LLMProvider: Abstract base class for LLM providers
- LLMRequest/LLMResponse: Data structures for LLM interactions
- MockLLMProvider: Mock provider for testing
- OllamaProvider: Local Ollama provider (default)
- LLMAction/LLMCondition: Behavior tree nodes using LLM providers
"""

from treehouse.llm.mock_provider import MockConfig, MockLLMProvider
from treehouse.llm.nodes import LLMAction, LLMCondition, LLMExecutionData
from treehouse.llm.ollama_provider import OllamaProvider
from treehouse.llm.provider import (
    LLMConnectionError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMRequest,
    LLMResponse,
    LLMResponseError,
)

__all__ = [
    # Provider interface
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    # Errors
    "LLMError",
    "LLMConnectionError",
    "LLMRateLimitError",
    "LLMResponseError",
    # Implementations
    "MockConfig",
    "MockLLMProvider",
    "OllamaProvider",
    # Nodes
    "LLMAction",
    "LLMCondition",
    "LLMExecutionData",
]
