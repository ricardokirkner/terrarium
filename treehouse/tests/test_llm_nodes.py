"""Tests for LLM behavior tree nodes."""

import pytest
from vivarium.core import NodeStatus

from treehouse.llm import (
    LLMAction,
    LLMCondition,
    LLMExecutionData,
    MockConfig,
    MockLLMProvider,
)


class TestLLMAction:
    """Tests for LLMAction node."""

    def test_basic_execution(self):
        """Test basic LLM action execution."""
        provider = MockLLMProvider(MockConfig(default_response="The answer is 42."))
        action = LLMAction(
            name="answer",
            provider=provider,
            task="What is the answer?",
        )

        state = {}
        result = action.execute(state)

        assert result == NodeStatus.SUCCESS
        assert provider.call_count == 1

    def test_output_key(self):
        """Test that response is stored in state with output_key."""
        provider = MockLLMProvider(MockConfig(default_response="Hello, world!"))
        action = LLMAction(
            name="greet",
            provider=provider,
            task="Say hello",
            output_key="greeting",
        )

        state = {}
        action.execute(state)

        assert state["greeting"] == "Hello, world!"

    def test_placeholder_substitution(self):
        """Test that {placeholders} are filled from state."""
        provider = MockLLMProvider()
        action = LLMAction(
            name="summarize",
            provider=provider,
            task="Summarize this: {text}",
        )

        state = {"text": "The quick brown fox jumps over the lazy dog."}
        action.execute(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert "The quick brown fox" in last_request.prompt

    def test_multiple_placeholders(self):
        """Test multiple placeholders in task."""
        provider = MockLLMProvider()
        action = LLMAction(
            name="combine",
            provider=provider,
            task="Combine {first} and {second}",
        )

        state = {"first": "A", "second": "B"}
        action.execute(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert "A" in last_request.prompt
        assert "B" in last_request.prompt

    def test_missing_placeholder_unchanged(self):
        """Test that missing placeholders are left unchanged."""
        provider = MockLLMProvider()
        action = LLMAction(
            name="test",
            provider=provider,
            task="Value is {missing}",
        )

        state = {}
        action.execute(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert "{missing}" in last_request.prompt

    def test_system_prompt(self):
        """Test that system prompt is passed to provider."""
        provider = MockLLMProvider()
        action = LLMAction(
            name="test",
            provider=provider,
            task="Hello",
            system_prompt="You are a helpful assistant.",
        )

        state = {}
        action.execute(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert last_request.system_prompt == "You are a helpful assistant."

    def test_temperature(self):
        """Test that temperature is passed to provider."""
        provider = MockLLMProvider()
        action = LLMAction(
            name="test",
            provider=provider,
            task="Hello",
            temperature=0.3,
        )

        state = {}
        action.execute(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert last_request.temperature == 0.3

    def test_max_tokens(self):
        """Test that max_tokens is passed to provider."""
        provider = MockLLMProvider()
        action = LLMAction(
            name="test",
            provider=provider,
            task="Hello",
            max_tokens=100,
        )

        state = {}
        action.execute(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert last_request.max_tokens == 100

    def test_json_mode(self):
        """Test that json_mode is passed to provider."""
        provider = MockLLMProvider()
        action = LLMAction(
            name="test",
            provider=provider,
            task="Return JSON",
            json_mode=True,
        )

        state = {}
        action.execute(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert last_request.json_mode is True

    def test_failure_on_error(self):
        """Test that LLM errors result in FAILURE status."""
        from treehouse.llm import LLMError

        config = MockConfig(fail_after=0, failure_error=LLMError("Mock error"))
        provider = MockLLMProvider(config)
        action = LLMAction(
            name="test",
            provider=provider,
            task="Hello",
        )

        state = {}
        result = action.execute(state)

        assert result == NodeStatus.FAILURE

    def test_llm_data_stored_in_state(self):
        """Test that LLM execution data is stored in state."""
        provider = MockLLMProvider(
            MockConfig(default_response="Test response"),
            model="test-model",
        )
        action = LLMAction(
            name="myaction",
            provider=provider,
            task="Test prompt",
        )

        state = {}
        action.execute(state)

        assert "_llm_myaction" in state
        llm_data = state["_llm_myaction"]
        assert isinstance(llm_data, LLMExecutionData)
        assert llm_data.prompt == "Test prompt"
        assert llm_data.response == "Test response"
        assert llm_data.model == "test-model"

    def test_last_response_property(self):
        """Test last_response property."""
        provider = MockLLMProvider(MockConfig(default_response="Hello"))
        action = LLMAction(
            name="test",
            provider=provider,
            task="Greet",
        )

        assert action.last_response is None

        state = {}
        action.execute(state)

        assert action.last_response is not None
        assert action.last_response.content == "Hello"


class TestLLMCondition:
    """Tests for LLMCondition node."""

    def test_yes_response(self):
        """Test that 'yes' response returns True."""
        provider = MockLLMProvider(MockConfig(default_response="Yes"))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Is this true?",
        )

        state = {}
        result = condition.evaluate(state)

        assert result is True

    def test_no_response(self):
        """Test that 'no' response returns False."""
        provider = MockLLMProvider(MockConfig(default_response="No"))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Is this true?",
        )

        state = {}
        result = condition.evaluate(state)

        assert result is False

    @pytest.mark.parametrize(
        "response",
        [
            "Yes",
            "YES",
            "yes",
            "Yes, it is.",
            "True",
            "true",
            "1",
            "Correct",
            "Affirmative",
            "Definitely",
            "Absolutely",
        ],
    )
    def test_various_yes_responses(self, response):
        """Test various forms of 'yes' responses."""
        provider = MockLLMProvider(MockConfig(default_response=response))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Test?",
        )

        assert condition.evaluate({}) is True

    @pytest.mark.parametrize(
        "response",
        [
            "No",
            "NO",
            "no",
            "No, it isn't.",
            "False",
            "false",
            "0",
            "Incorrect",
            "Negative",
        ],
    )
    def test_various_no_responses(self, response):
        """Test various forms of 'no' responses."""
        provider = MockLLMProvider(MockConfig(default_response=response))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Test?",
        )

        assert condition.evaluate({}) is False

    def test_ambiguous_response_defaults_to_false(self):
        """Test that ambiguous responses default to False."""
        provider = MockLLMProvider(
            MockConfig(default_response="I'm not sure about that.")
        )
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Test?",
        )

        assert condition.evaluate({}) is False

    def test_placeholder_substitution(self):
        """Test that {placeholders} are filled from state."""
        provider = MockLLMProvider(MockConfig(default_response="Yes"))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Is {value} greater than 10?",
        )

        state = {"value": "15"}
        condition.evaluate(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert "15" in last_request.prompt

    def test_low_temperature_by_default(self):
        """Test that conditions use low temperature by default."""
        provider = MockLLMProvider(MockConfig(default_response="Yes"))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Test?",
        )

        state = {}
        condition.evaluate(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert last_request.temperature == 0.1

    def test_custom_temperature(self):
        """Test custom temperature setting."""
        provider = MockLLMProvider(MockConfig(default_response="Yes"))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Test?",
            temperature=0.5,
        )

        state = {}
        condition.evaluate(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert last_request.temperature == 0.5

    def test_default_system_prompt(self):
        """Test that default system prompt is set."""
        provider = MockLLMProvider(MockConfig(default_response="Yes"))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Test?",
        )

        state = {}
        condition.evaluate(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert "YES or NO" in last_request.system_prompt

    def test_custom_system_prompt(self):
        """Test custom system prompt."""
        provider = MockLLMProvider(MockConfig(default_response="Yes"))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Test?",
            system_prompt="Custom prompt",
        )

        state = {}
        condition.evaluate(state)

        last_request = provider.last_request()
        assert last_request is not None
        assert last_request.system_prompt == "Custom prompt"

    def test_failure_returns_false(self):
        """Test that LLM errors result in False."""
        from treehouse.llm import LLMError

        config = MockConfig(fail_after=0, failure_error=LLMError("Error"))
        provider = MockLLMProvider(config)
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Test?",
        )

        assert condition.evaluate({}) is False

    def test_llm_data_stored_in_state(self):
        """Test that LLM execution data is stored in state."""
        provider = MockLLMProvider(
            MockConfig(default_response="Yes"),
            model="test-model",
        )
        condition = LLMCondition(
            name="mycheck",
            provider=provider,
            question="Is this valid?",
        )

        state = {}
        condition.evaluate(state)

        assert "_llm_mycheck" in state
        llm_data = state["_llm_mycheck"]
        assert isinstance(llm_data, LLMExecutionData)
        assert llm_data.prompt == "Is this valid?"
        assert llm_data.response == "Yes"

    def test_last_response_property(self):
        """Test last_response property."""
        provider = MockLLMProvider(MockConfig(default_response="Yes"))
        condition = LLMCondition(
            name="check",
            provider=provider,
            question="Test?",
        )

        assert condition.last_response is None

        condition.evaluate({})

        assert condition.last_response is not None
        assert condition.last_response.content == "Yes"


class TestLLMExecutionData:
    """Tests for LLMExecutionData."""

    def test_default_values(self):
        """Test default values."""
        data = LLMExecutionData()
        assert data.prompt == ""
        assert data.response == ""
        assert data.reasoning is None
        assert data.tokens_used == {"prompt": 0, "completion": 0, "total": 0}
        assert data.cost == 0.0
        assert data.latency_ms == 0.0
        assert data.model == ""

    def test_to_dict(self):
        """Test serialization to dict."""
        data = LLMExecutionData(
            prompt="Test prompt",
            response="Test response",
            reasoning="Because...",
            tokens_used={"prompt": 10, "completion": 20, "total": 30},
            cost=0.001,
            latency_ms=150.0,
            model="test-model",
        )

        d = data.to_dict()
        assert d["prompt"] == "Test prompt"
        assert d["response"] == "Test response"
        assert d["reasoning"] == "Because..."
        assert d["tokens_used"]["total"] == 30
        assert d["cost"] == 0.001
        assert d["latency_ms"] == 150.0
        assert d["model"] == "test-model"


class TestRunAsyncHelper:
    """Tests for _run_async helper function."""

    @pytest.mark.asyncio
    async def test_run_async_from_event_loop(self):
        """_run_async should use ThreadPoolExecutor when called from event loop."""
        import asyncio

        from treehouse.llm.nodes import _run_async

        async def sample_coro():
            await asyncio.sleep(0.001)
            return "result"

        # Call _run_async from within an async context (event loop running)
        # This should trigger the ThreadPoolExecutor path
        result = _run_async(sample_coro())
        assert result == "result"
