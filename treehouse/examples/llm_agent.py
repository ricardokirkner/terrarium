#!/usr/bin/env python3
"""Example LLM-powered behavior tree agent.

This example demonstrates:
1. Building a behavior tree with LLM nodes
2. Using OllamaProvider for local inference (no API costs)
3. Collecting execution traces with LLM observability
4. Visualizing traces with LLM prompt/response data

Prerequisites:
1. Install Ollama: https://ollama.ai
2. Pull a model: ollama pull llama3.2
3. Run Ollama server: ollama serve (or it runs automatically)

Usage:
    python examples/llm_agent.py
    python examples/llm_agent.py --model mistral
    python examples/llm_agent.py --mock  # Use mock provider (no Ollama needed)
"""

import argparse
import sys

from vivarium.core import BehaviorTree, Selector, Sequence

from treehouse import TraceCollector, print_timeline, print_trace
from treehouse.llm import (
    LLMAction,
    LLMCondition,
    LLMConnectionError,
    MockConfig,
    MockLLMProvider,
    OllamaProvider,
)


def create_qa_agent(provider):
    """Create a simple Q&A agent behavior tree.

    The tree works as follows:
    1. LLMCondition: Check if the question is simple/factual
    2. If yes: LLMAction answers directly
    3. If no: LLMAction explains it needs more context

    This demonstrates conditional LLM-based decision making.
    """
    # Condition: Is this a simple factual question?
    is_simple = LLMCondition(
        name="is_simple_question",
        provider=provider,
        question=(
            "Is the following question a simple factual question that can be "
            "answered in one sentence? Question: {user_question}"
        ),
    )

    # Action: Answer the question directly
    answer_directly = LLMAction(
        name="answer_directly",
        provider=provider,
        task="Answer this question concisely: {user_question}",
        output_key="answer",
        temperature=0.3,
        max_tokens=100,
    )

    # Action: Explain that more context is needed
    needs_context = LLMAction(
        name="needs_context",
        provider=provider,
        task=(
            "The following question requires more context or research to answer "
            "properly. Explain briefly why: {user_question}"
        ),
        output_key="answer",
        temperature=0.5,
        max_tokens=150,
    )

    # Build the tree:
    # Selector tries children until one succeeds
    # - First child: Sequence of (is_simple AND answer_directly)
    # - Second child: needs_context (fallback)
    tree = Selector(
        name="qa_selector",
        children=[
            Sequence(
                name="simple_answer_sequence",
                children=[is_simple, answer_directly],
            ),
            needs_context,
        ],
    )

    return tree


def run_agent(provider, question: str, use_color: bool = True):
    """Run the Q&A agent with a question and display results."""
    print(f"\nQuestion: {question}")
    print("=" * 60)

    # Create the behavior tree
    root = create_qa_agent(provider)
    collector = TraceCollector()
    tree = BehaviorTree(root=root, emitter=collector)

    # Set up state with the question
    state = {"user_question": question}

    # Important: Set state reference for LLM data extraction
    collector.set_state(state)

    # Execute the tree
    try:
        result = tree.tick(state)
    except LLMConnectionError as e:
        print(f"\nError: {e}")
        print("Make sure Ollama is running: ollama serve")
        return None

    # Get the trace
    trace = collector.get_trace()

    # Display results
    print(f"\nResult: {result.value}")
    print(f"Answer: {state.get('answer', 'No answer generated')}")

    print("\n" + "=" * 60)
    print("Execution Trace:")
    print("=" * 60)
    print_trace(trace, use_color=use_color, show_llm=True)

    print("\n" + "=" * 60)
    print("Timeline:")
    print("=" * 60)
    print_timeline(trace, use_color=use_color)

    # Cost analysis
    print("\n" + "=" * 60)
    print("Cost Analysis:")
    print("=" * 60)
    total_tokens = 0
    total_cost = 0.0
    for execution in trace.executions:
        if execution.has_llm_data:
            tokens = execution.llm_tokens.get("total", 0) if execution.llm_tokens else 0
            cost = execution.llm_cost or 0.0
            total_tokens += tokens
            total_cost += cost
            print(f"  {execution.node_name}: {tokens} tokens, ${cost:.4f}")

    print(f"\n  Total: {total_tokens} tokens, ${total_cost:.4f}")
    print("  (Local Ollama inference is free!)")

    return trace


def main():
    parser = argparse.ArgumentParser(description="LLM-powered Q&A Agent Example")
    parser.add_argument(
        "--model",
        default="llama3.2",
        help="Ollama model name (default: llama3.2)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock provider instead of Ollama",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--question",
        default="What is the capital of France?",
        help="Question to ask the agent",
    )
    args = parser.parse_args()

    # Create provider
    if args.mock:
        print("Using MockLLMProvider (no Ollama needed)")
        provider = MockLLMProvider(
            MockConfig(
                canned_responses={
                    "simple factual": "Yes",
                    "capital of france": "The capital of France is Paris.",
                    "meaning of life": "No",
                },
                default_response="This is a mock response.",
            ),
            model="mock-model",
        )
    else:
        print(f"Using OllamaProvider with model: {args.model}")
        provider = OllamaProvider(model=args.model, base_url=args.base_url)

    use_color = not args.no_color

    # Run with the provided question
    trace = run_agent(provider, args.question, use_color)

    if trace is None:
        sys.exit(1)

    # Run a second example with a more complex question
    print("\n\n" + "=" * 60)
    print("SECOND EXAMPLE - Complex Question")
    print("=" * 60)
    run_agent(
        provider,
        "What are the philosophical implications of artificial consciousness?",
        use_color,
    )


if __name__ == "__main__":
    main()
