"""LLM-powered behavior tree nodes.

This module provides Action and Condition nodes that use LLM providers
to make decisions and perform tasks within behavior trees.

Nodes:
- LLMAction: Performs a task using an LLM and updates state
- LLMCondition: Asks the LLM a yes/no question to make decisions
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Coroutine, TypeVar

from vivarium.core import Action, Condition, NodeStatus

from treehouse.llm.provider import LLMError, LLMProvider, LLMRequest, LLMResponse

T = TypeVar("T")


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from a sync context.

    Handles the case where we're already inside an event loop
    (e.g., when called from an async context).

    Args:
        coro: The coroutine to run.

    Returns:
        The result of the coroutine.
    """
    try:
        # Check if there's already a running event loop
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, use asyncio.run()
        return asyncio.run(coro)

    # We're inside an existing event loop
    # Create a new thread to run the coroutine
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


@dataclass
class LLMExecutionData:
    """Data captured from an LLM node execution for observability.

    This is stored in state under a key like "_llm_{node_name}" so that
    TraceCollector can capture it for visualization.

    Attributes:
        prompt: The prompt sent to the LLM.
        response: The LLM's response content.
        reasoning: Optional reasoning/chain-of-thought.
        tokens_used: Token usage dict.
        cost: Cost in USD.
        latency_ms: Latency in milliseconds.
        model: Model name used.
    """

    prompt: str = ""
    response: str = ""
    reasoning: str | None = None
    tokens_used: dict[str, int] = field(
        default_factory=lambda: {
            "prompt": 0,
            "completion": 0,
            "total": 0,
        }
    )
    cost: float = 0.0
    latency_ms: float = 0.0
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "prompt": self.prompt,
            "response": self.response,
            "reasoning": self.reasoning,
            "tokens_used": self.tokens_used,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "model": self.model,
        }


class LLMAction(Action):
    """Action node that uses an LLM to perform a task.

    LLMAction sends a prompt to an LLM provider, parses the response,
    and optionally updates the behavior tree state with the result.

    The prompt can include placeholders like {variable} that will be
    filled from the state before sending to the LLM.

    Example:
        action = LLMAction(
            name="summarize",
            provider=OllamaProvider(),
            task="Summarize the following text: {input_text}",
            output_key="summary",
        )
        # When executed, reads state["input_text"], sends to LLM,
        # and stores response in state["summary"]

    Attributes:
        name: Unique identifier for this action.
        provider: LLM provider to use.
        task: Task description/prompt (may contain {placeholders}).
        system_prompt: Optional system prompt for context.
        output_key: State key to store the response (None = don't store).
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response.
        json_mode: Whether to request JSON output.
    """

    def __init__(
        self,
        name: str,
        provider: LLMProvider,
        task: str,
        system_prompt: str | None = None,
        output_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ):
        """Initialize the LLMAction.

        Args:
            name: Unique identifier for this action.
            provider: LLM provider to use for completions.
            task: Task description that becomes the prompt.
            system_prompt: Optional system-level instructions.
            output_key: State key to store the LLM response.
            temperature: Sampling temperature (0.0-1.0).
            max_tokens: Maximum tokens in response.
            json_mode: Request JSON-formatted output.
        """
        super().__init__(name)
        self.provider = provider
        self.task = task
        self.system_prompt = system_prompt
        self.output_key = output_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.json_mode = json_mode

        self._last_response: LLMResponse | None = None

    def execute(self, state) -> NodeStatus:
        """Execute the LLM action.

        Builds a prompt from the task and state, sends it to the LLM,
        and stores the result in state if output_key is set.

        Args:
            state: The behavior tree state (dict-like).

        Returns:
            SUCCESS if the LLM call succeeded.
            FAILURE if the LLM call failed.
        """
        try:
            # Build prompt with variable substitution
            prompt = self._build_prompt(state)

            # Create LLM request
            request = LLMRequest(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                json_mode=self.json_mode,
            )

            # Execute async LLM call (handles both sync and async contexts)
            response = _run_async(self.provider.complete(request))
            self._last_response = response

            # Store response in state if output_key is set
            if self.output_key:
                state[self.output_key] = response.content

            # Store LLM execution data for observability
            llm_data = LLMExecutionData(
                prompt=prompt,
                response=response.content,
                reasoning=response.reasoning,
                tokens_used=response.tokens_used,
                cost=response.cost,
                latency_ms=response.latency_ms,
                model=response.model,
            )
            state[f"_llm_{self.name}"] = llm_data

            return NodeStatus.SUCCESS

        except LLMError:
            return NodeStatus.FAILURE

    def _build_prompt(self, state) -> str:
        """Build prompt by substituting {placeholders} from state."""
        prompt = self.task

        # Find all {placeholder} patterns
        placeholders = re.findall(r"\{(\w+)\}", prompt)

        for key in placeholders:
            if key in state:
                prompt = prompt.replace(f"{{{key}}}", str(state[key]))

        return prompt

    @property
    def last_response(self) -> LLMResponse | None:
        """Return the last LLM response, or None if not executed."""
        return self._last_response


class LLMCondition(Condition):
    """Condition node that uses an LLM to answer a yes/no question.

    LLMCondition sends a question to an LLM and parses the response
    to determine a boolean result. Uses a lower temperature for
    more consistent answers.

    The question can include placeholders like {variable} that will be
    filled from the state before sending to the LLM.

    Example:
        condition = LLMCondition(
            name="is_simple_question",
            provider=OllamaProvider(),
            question="Is this a simple factual question: {user_input}",
        )
        # Returns SUCCESS if LLM says yes, FAILURE if no

    Attributes:
        name: Unique identifier for this condition.
        provider: LLM provider to use.
        question: The yes/no question to ask.
        system_prompt: Optional system prompt for context.
        temperature: Sampling temperature (low for consistency).
    """

    # Patterns that indicate "yes" response
    YES_PATTERNS = [
        r"^yes\b",
        r"^true\b",
        r"^1$",
        r"^correct\b",
        r"^affirmative\b",
        r"^definitely\b",
        r"^absolutely\b",
    ]

    # Patterns that indicate "no" response
    NO_PATTERNS = [
        r"^no\b",
        r"^false\b",
        r"^0$",
        r"^incorrect\b",
        r"^negative\b",
    ]

    def __init__(
        self,
        name: str,
        provider: LLMProvider,
        question: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
    ):
        """Initialize the LLMCondition.

        Args:
            name: Unique identifier for this condition.
            provider: LLM provider to use for completions.
            question: The yes/no question to ask the LLM.
            system_prompt: Optional system-level instructions.
            temperature: Sampling temperature (default 0.1 for consistency).
        """
        super().__init__(name)
        self.provider = provider
        self.question = question
        self.system_prompt = system_prompt or (
            "You are a helpful assistant. Answer the following question with "
            "YES or NO. Be concise - just answer YES or NO."
        )
        self.temperature = temperature

        self._last_response: LLMResponse | None = None

    def evaluate(self, state) -> bool:
        """Evaluate the condition by asking the LLM.

        Args:
            state: The behavior tree state (dict-like).

        Returns:
            True if the LLM's answer indicates yes.
            False if the LLM's answer indicates no or on error.
        """
        try:
            # Build question with variable substitution
            question = self._build_question(state)

            # Create LLM request with low temperature for consistency
            request = LLMRequest(
                prompt=question,
                system_prompt=self.system_prompt,
                temperature=self.temperature,
                max_tokens=20,  # Short answer expected
            )

            # Execute async LLM call (handles both sync and async contexts)
            response = _run_async(self.provider.complete(request))
            self._last_response = response

            # Parse the response to boolean
            result = self._parse_response(response.content)

            # Store LLM execution data for observability
            llm_data = LLMExecutionData(
                prompt=question,
                response=response.content,
                reasoning=response.reasoning,
                tokens_used=response.tokens_used,
                cost=response.cost,
                latency_ms=response.latency_ms,
                model=response.model,
            )
            state[f"_llm_{self.name}"] = llm_data

            return result

        except LLMError:
            return False

    def _build_question(self, state) -> str:
        """Build question by substituting {placeholders} from state."""
        question = self.question

        # Find all {placeholder} patterns
        placeholders = re.findall(r"\{(\w+)\}", question)

        for key in placeholders:
            if key in state:
                question = question.replace(f"{{{key}}}", str(state[key]))

        return question

    def _parse_response(self, content: str) -> bool:
        """Parse LLM response to boolean.

        Tries to match known yes/no patterns. Defaults to False
        if the response is ambiguous.

        Args:
            content: The LLM response text.

        Returns:
            True if response indicates yes, False otherwise.
        """
        # Normalize: lowercase, strip whitespace
        normalized = content.strip().lower()

        # Check yes patterns first
        for pattern in self.YES_PATTERNS:
            if re.match(pattern, normalized, re.IGNORECASE):
                return True

        # Check no patterns
        for pattern in self.NO_PATTERNS:
            if re.match(pattern, normalized, re.IGNORECASE):
                return False

        # Ambiguous response - default to False
        return False

    @property
    def last_response(self) -> LLMResponse | None:
        """Return the last LLM response, or None if not evaluated."""
        return self._last_response
