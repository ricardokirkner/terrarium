"""Tests for LLM provider interface and mock implementation."""

import pytest

from treehouse.llm.mock_provider import MockConfig, MockLLMProvider
from treehouse.llm.provider import (
    LLMError,
    LLMProvider,
    LLMRequest,
    LLMResponse,
)


class TestLLMRequest:
    """Tests for LLMRequest dataclass."""

    def test_basic_request(self):
        """Test creating a basic request with just a prompt."""
        request = LLMRequest(prompt="Hello, world!")
        assert request.prompt == "Hello, world!"
        assert request.system_prompt is None
        assert request.max_tokens is None
        assert request.temperature == 0.7
        assert request.stop_sequences is None
        assert request.json_mode is False
        assert request.metadata == {}

    def test_full_request(self):
        """Test creating a request with all parameters."""
        request = LLMRequest(
            prompt="What is 2+2?",
            system_prompt="You are a helpful assistant.",
            max_tokens=100,
            temperature=0.3,
            stop_sequences=["\n", "END"],
            json_mode=True,
            metadata={"task": "math"},
        )
        assert request.prompt == "What is 2+2?"
        assert request.system_prompt == "You are a helpful assistant."
        assert request.max_tokens == 100
        assert request.temperature == 0.3
        assert request.stop_sequences == ["\n", "END"]
        assert request.json_mode is True
        assert request.metadata == {"task": "math"}


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_basic_response(self):
        """Test creating a basic response."""
        response = LLMResponse(content="Hello!")
        assert response.content == "Hello!"
        assert response.reasoning is None
        assert response.tokens_used == {"prompt": 0, "completion": 0, "total": 0}
        assert response.model == ""
        assert response.cost == 0.0
        assert response.latency_ms == 0.0
        assert response.raw_response is None

    def test_full_response(self):
        """Test creating a response with all fields."""
        response = LLMResponse(
            content="The answer is 4.",
            reasoning="2+2 equals 4 because...",
            tokens_used={"prompt": 10, "completion": 5, "total": 15},
            model="gpt-4",
            cost=0.001,
            latency_ms=150.5,
            raw_response={"id": "123"},
        )
        assert response.content == "The answer is 4."
        assert response.reasoning == "2+2 equals 4 because..."
        assert response.tokens_used["total"] == 15
        assert response.model == "gpt-4"
        assert response.cost == 0.001
        assert response.latency_ms == 150.5

    def test_to_dict(self):
        """Test serialization to dict."""
        response = LLMResponse(
            content="Test",
            tokens_used={"prompt": 5, "completion": 3, "total": 8},
            model="test-model",
            cost=0.0,
            latency_ms=10.0,
        )
        data = response.to_dict()
        assert data["content"] == "Test"
        assert data["tokens_used"]["total"] == 8
        assert data["model"] == "test-model"
        # raw_response should not be in dict
        assert "raw_response" not in data

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "content": "Response text",
            "reasoning": "Because...",
            "tokens_used": {"prompt": 10, "completion": 20, "total": 30},
            "model": "llama3",
            "cost": 0.0,
            "latency_ms": 50.0,
        }
        response = LLMResponse.from_dict(data)
        assert response.content == "Response text"
        assert response.reasoning == "Because..."
        assert response.tokens_used["total"] == 30
        assert response.model == "llama3"

    def test_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        original = LLMResponse(
            content="Test content",
            reasoning="Test reasoning",
            tokens_used={"prompt": 5, "completion": 10, "total": 15},
            model="test",
            cost=0.001,
            latency_ms=100.0,
        )
        restored = LLMResponse.from_dict(original.to_dict())
        assert restored.content == original.content
        assert restored.reasoning == original.reasoning
        assert restored.tokens_used == original.tokens_used
        assert restored.model == original.model
        assert restored.cost == original.cost
        assert restored.latency_ms == original.latency_ms


class TestMockLLMProvider:
    """Tests for MockLLMProvider."""

    @pytest.mark.asyncio
    async def test_default_response(self):
        """Test that default response is returned."""
        provider = MockLLMProvider()
        request = LLMRequest(prompt="Hello")
        response = await provider.complete(request)
        assert response.content == "This is a mock response."
        assert response.model == "mock-model"

    @pytest.mark.asyncio
    async def test_custom_default_response(self):
        """Test custom default response."""
        config = MockConfig(default_response="Custom response")
        provider = MockLLMProvider(config)
        response = await provider.complete(LLMRequest(prompt="Anything"))
        assert response.content == "Custom response"

    @pytest.mark.asyncio
    async def test_canned_responses(self):
        """Test canned responses based on prompt content."""
        config = MockConfig(
            canned_responses={
                "hello": "Hi there!",
                "bye": "Goodbye!",
            }
        )
        provider = MockLLMProvider(config)

        response1 = await provider.complete(LLMRequest(prompt="hello world"))
        assert response1.content == "Hi there!"

        response2 = await provider.complete(LLMRequest(prompt="say bye now"))
        assert response2.content == "Goodbye!"

    @pytest.mark.asyncio
    async def test_canned_responses_case_insensitive(self):
        """Test that canned response matching is case-insensitive."""
        config = MockConfig(canned_responses={"hello": "Hi!"})
        provider = MockLLMProvider(config)

        response = await provider.complete(LLMRequest(prompt="HELLO there"))
        assert response.content == "Hi!"

    @pytest.mark.asyncio
    async def test_token_counting(self):
        """Test token count simulation."""
        provider = MockLLMProvider()
        request = LLMRequest(prompt="This is a test prompt")  # 21 chars
        response = await provider.complete(request)

        # Default counting is len // 4
        assert response.tokens_used["prompt"] == 21 // 4
        assert response.tokens_used["completion"] > 0
        assert response.tokens_used["total"] == (
            response.tokens_used["prompt"] + response.tokens_used["completion"]
        )

    @pytest.mark.asyncio
    async def test_token_counting_with_system_prompt(self):
        """Test token counting includes system prompt."""
        provider = MockLLMProvider()
        request = LLMRequest(
            prompt="User prompt",  # 11 chars
            system_prompt="System prompt",  # 13 chars
        )
        response = await provider.complete(request)

        expected_prompt_tokens = (11 // 4) + (13 // 4)
        assert response.tokens_used["prompt"] == expected_prompt_tokens

    @pytest.mark.asyncio
    async def test_mock_costs(self):
        """Test simulated cost calculation."""
        config = MockConfig(
            default_response="abcd",
            cost_per_1k_tokens=1.0,
            cost_per_call=0.5,
        )
        provider = MockLLMProvider(config)
        response = await provider.complete(LLMRequest(prompt="abcd"))

        # prompt tokens = 1, completion tokens = 1, total = 2
        assert response.tokens_used["total"] == 2
        assert response.cost == pytest.approx(0.5 + 2 / 1000)

    @pytest.mark.asyncio
    async def test_simulated_delay(self):
        """Test simulated delay."""
        config = MockConfig(simulate_delay_ms=50)
        provider = MockLLMProvider(config)

        request = LLMRequest(prompt="Test")
        response = await provider.complete(request)

        # Latency should be at least the simulated delay
        assert response.latency_ms >= 50

    @pytest.mark.asyncio
    async def test_call_count(self):
        """Test call counting."""
        provider = MockLLMProvider()
        assert provider.call_count == 0

        await provider.complete(LLMRequest(prompt="1"))
        assert provider.call_count == 1

        await provider.complete(LLMRequest(prompt="2"))
        assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_request_tracking(self):
        """Test that requests are tracked."""
        provider = MockLLMProvider()

        await provider.complete(LLMRequest(prompt="First"))
        await provider.complete(LLMRequest(prompt="Second"))

        assert len(provider.requests) == 2
        assert provider.requests[0].prompt == "First"
        assert provider.requests[1].prompt == "Second"
        last_request = provider.last_request()
        assert last_request is not None
        assert last_request.prompt == "Second"

    @pytest.mark.asyncio
    async def test_fail_after(self):
        """Test failure after N calls."""
        config = MockConfig(fail_after=2)
        provider = MockLLMProvider(config)

        # First two calls succeed
        await provider.complete(LLMRequest(prompt="1"))
        await provider.complete(LLMRequest(prompt="2"))

        # Third call fails
        with pytest.raises(LLMError):
            await provider.complete(LLMRequest(prompt="3"))

    @pytest.mark.asyncio
    async def test_custom_failure_error(self):
        """Test custom failure error."""
        custom_error = LLMError("Custom failure message")
        config = MockConfig(fail_after=0, failure_error=custom_error)
        provider = MockLLMProvider(config)

        with pytest.raises(LLMError, match="Custom failure message"):
            await provider.complete(LLMRequest(prompt="Fail"))

    @pytest.mark.asyncio
    async def test_response_callback(self):
        """Test dynamic response via callback."""

        def callback(request: LLMRequest) -> str:
            return f"Echo: {request.prompt}"

        config = MockConfig(response_callback=callback)
        provider = MockLLMProvider(config)

        response = await provider.complete(LLMRequest(prompt="Hello"))
        assert response.content == "Echo: Hello"

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test reset clears state."""
        provider = MockLLMProvider()

        await provider.complete(LLMRequest(prompt="Test"))
        assert provider.call_count == 1
        assert len(provider.requests) == 1

        provider.reset()
        assert provider.call_count == 0
        assert len(provider.requests) == 0

    def test_model_name(self):
        """Test model name property."""
        provider1 = MockLLMProvider()
        assert provider1.model_name == "mock-model"

        provider2 = MockLLMProvider(model="custom-model")
        assert provider2.model_name == "custom-model"

    def test_count_tokens(self):
        """Test token counting helper."""
        provider = MockLLMProvider()

        # Default is len // 4
        assert provider.count_tokens("") == 0
        assert provider.count_tokens("test") == 1  # 4 chars
        assert provider.count_tokens("hello world") == 2  # 11 chars

    def test_estimate_cost(self):
        """Test cost estimation (always 0 for mock)."""
        provider = MockLLMProvider()
        request = LLMRequest(prompt="Test")
        assert provider.estimate_cost(request) == 0.0

    def test_is_llm_provider(self):
        """Test that MockLLMProvider is an LLMProvider."""
        provider = MockLLMProvider()
        assert isinstance(provider, LLMProvider)
