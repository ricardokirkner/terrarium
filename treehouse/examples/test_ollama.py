#!/usr/bin/env python3
"""Manual test script for OllamaProvider.

Run this to verify that OllamaProvider works with your local Ollama server.

Prerequisites:
1. Install Ollama: https://ollama.ai
2. Pull a model: ollama pull llama3.2
3. Run Ollama server: ollama serve (or it runs automatically)

Usage:
    python examples/test_ollama.py
    python examples/test_ollama.py --model mistral
"""

import argparse
import asyncio
import sys

from treehouse.llm import LLMConnectionError, LLMRequest, OllamaProvider


async def main(model: str, base_url: str) -> None:
    """Test the Ollama provider with a simple prompt."""
    print(f"Testing OllamaProvider with model: {model}")
    print(f"Connecting to: {base_url}")
    print("-" * 40)

    provider = OllamaProvider(model=model, base_url=base_url)

    # Test 1: Simple question
    print("\nTest 1: Simple math question")
    request = LLMRequest(
        prompt="What is 2+2? Answer with just the number.",
        temperature=0.1,
        max_tokens=10,
    )

    try:
        response = await provider.complete(request)
        print(f"Response: {response.content}")
        print(f"Tokens: {response.tokens_used}")
        print(f"Latency: {response.latency_ms:.1f}ms")
        print(f"Cost: ${response.cost:.4f}")
    except LLMConnectionError as e:
        print(f"Connection error: {e}")
        print("\nMake sure Ollama is running: ollama serve")
        sys.exit(1)

    # Test 2: With system prompt
    print("\n" + "-" * 40)
    print("Test 2: With system prompt")
    request = LLMRequest(
        prompt="Tell me a joke.",
        system_prompt="You are a helpful assistant who tells short, clean jokes.",
        temperature=0.7,
        max_tokens=100,
    )

    response = await provider.complete(request)
    print(f"Response: {response.content}")
    print(f"Tokens: {response.tokens_used}")
    print(f"Latency: {response.latency_ms:.1f}ms")

    # Test 3: JSON mode
    print("\n" + "-" * 40)
    print("Test 3: JSON mode")
    request = LLMRequest(
        prompt='Return JSON with keys "name" and "age" for a fictional person.',
        json_mode=True,
        temperature=0.1,
        max_tokens=50,
    )

    response = await provider.complete(request)
    print(f"Response: {response.content}")
    print(f"Tokens: {response.tokens_used}")
    print(f"Latency: {response.latency_ms:.1f}ms")

    print("\n" + "-" * 40)
    print("All tests completed successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test OllamaProvider")
    parser.add_argument(
        "--model",
        default="llama3.2",
        help="Model name (default: llama3.2)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.model, args.base_url))
