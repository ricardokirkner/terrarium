#!/usr/bin/env python3
"""Interactive chatbot example with tool routing.

This example runs a simple assistant loop that:
- Captures user prompts
- Uses an LLM to decide whether to call a tool
- Executes the selected tool
- Uses the LLM to craft the final response

Usage:
    cd treehouse
    python examples/chatbot_with_tools.py --mock --visualize
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import operator
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

from vivarium import Action, BehaviorTree, NodeStatus, Selector, Sequence

from treehouse import DebuggerClient, DebuggerTree, TraceCollector
from treehouse.llm.mock_provider import MockConfig, MockLLMProvider
from treehouse.llm.nodes import LLMAction, LLMCondition, LLMExecutionData
from treehouse.llm.ollama_provider import OllamaProvider
from treehouse.llm.provider import LLMError, LLMProvider, LLMRequest


def run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[..., str]


def safe_eval(expression: str) -> float:  # noqa: C901
    allowed_operators = {
        "Add": operator.add,
        "Sub": operator.sub,
        "Mult": operator.mul,
        "Div": operator.truediv,
        "Pow": operator.pow,
        "Mod": operator.mod,
    }
    allowed_unary = {
        "UAdd": operator.pos,
        "USub": operator.neg,
    }

    def _eval(node):
        node_type = type(node).__name__
        if node_type == "Expression":
            return _eval(node.body)
        if node_type == "BinOp":
            left = _eval(node.left)
            right = _eval(node.right)
            op = allowed_operators.get(type(node.op).__name__)
            if not op:
                raise ValueError("Unsupported operator")
            return op(left, right)
        if node_type == "UnaryOp":
            operand = _eval(node.operand)
            op = allowed_unary.get(type(node.op).__name__)
            if not op:
                raise ValueError("Unsupported unary operator")
            return op(operand)
        if node_type == "Constant" and isinstance(node.value, (int, float)):
            return node.value
        if node_type == "Call":
            if hasattr(node.func, "id") and node.func.id in {
                "sqrt",
                "sin",
                "cos",
                "tan",
                "log",
            }:
                if len(node.args) != 1:
                    raise ValueError("Unsupported function usage")
                func = getattr(math, node.func.id)
                return func(_eval(node.args[0]))
        raise ValueError("Unsupported expression")

    import ast

    tree = ast.parse(expression, mode="eval")
    return float(_eval(tree))


def tool_calculator(tool_input: str) -> str:
    if not tool_input.strip():
        return "No expression provided."
    try:
        result = safe_eval(tool_input)
    except Exception as exc:
        return f"Calculator error: {exc}"
    if result.is_integer():
        return str(int(result))
    return str(result)


def tool_time(_: str) -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def tool_memory_lookup(tool_input: str, state: dict) -> str:
    count = 5
    match = re.search(r"(\d+)", tool_input or "")
    if match:
        count = max(1, min(20, int(match.group(1))))
    history = state.get("history", [])[-count:]
    if not history:
        return "No prior turns yet."
    formatted = []
    for item in history:
        formatted.append(f"{item['role']}: {item['content']}")
    return "\n".join(formatted)


class ToolRouterAction(Action):
    def __init__(self, name: str, provider: LLMProvider, tools: list[Tool]):
        super().__init__(name)
        self.provider = provider
        self.tools = tools

    def execute(self, state) -> NodeStatus:
        tools_text = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self.tools
        )
        prompt = (
            "You are routing a user request to the right tool. "
            "Respond only with a JSON object using keys tool, input, reason. "
            "If no tool applies, set tool to 'none'.\n\n"
            f"Tools:\n{tools_text}\n\n"
            f"User message: {state.get('user_input', '')}\n"
        )
        request = LLMRequest(prompt=prompt, temperature=0.0, json_mode=True)

        try:
            response = run_async(self.provider.complete(request))
        except LLMError:
            return NodeStatus.FAILURE

        state[f"_llm_{self.name}"] = LLMExecutionData(
            prompt=prompt,
            response=response.content,
            reasoning=response.reasoning,
            tokens_used=response.tokens_used,
            cost=response.cost,
            latency_ms=response.latency_ms,
            model=response.model,
        )

        tool_name, tool_input, reason = parse_tool_choice(response.content)
        state["tool_name"] = tool_name
        state["tool_input"] = tool_input
        state["tool_reason"] = reason

        if tool_name == "none":
            return NodeStatus.FAILURE
        if tool_name not in {tool.name for tool in self.tools}:
            state["tool_name"] = "none"
            return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class ToolExecuteAction(Action):
    def __init__(self, name: str, tools: list[Tool]):
        super().__init__(name)
        self.tools = {tool.name: tool for tool in tools}

    def execute(self, state) -> NodeStatus:
        tool_name = state.get("tool_name")
        tool_input = str(state.get("tool_input", ""))
        if not tool_name or tool_name == "none":
            return NodeStatus.FAILURE
        tool = self.tools.get(tool_name)
        if not tool:
            return NodeStatus.FAILURE
        if not tool_input.strip():
            tool_input = str(state.get("user_input", ""))
        if tool_name == "memory_lookup":
            output = tool.handler(tool_input, state)
        else:
            output = tool.handler(tool_input)
        state["tool_output"] = output
        state[f"_llm_{self.name}"] = LLMExecutionData(
            prompt=f"Tool: {tool_name}\nInput: {tool_input}",
            response=str(output),
            tokens_used={"prompt": 0, "completion": 0, "total": 0},
            cost=0.0,
            latency_ms=0.0,
            model="tool",
        )
        return NodeStatus.SUCCESS


def parse_tool_choice(content: str) -> tuple[str, str, str]:
    cleaned = content.strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            tool_name = str(data.get("tool", "none")).strip()
            tool_input = str(data.get("input", "")).strip()
            reason = str(data.get("reason", "")).strip()
            return tool_name, tool_input, reason
        except json.JSONDecodeError:
            pass

    match = re.search(r"tool\s*[:=]\s*(\w+)", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).lower(), "", ""
    return "none", "", ""


def mock_router_callback(request: LLMRequest) -> str:
    prompt = request.prompt.lower()
    user_match = re.search(r"user message:(.*)", prompt, re.DOTALL)
    user_text = user_match.group(1).strip() if user_match else prompt
    if any(token in user_text for token in ["time", "date", "clock"]):
        return json.dumps({"tool": "time", "input": "now", "reason": "time request"})
    if re.search(r"\d+\s*[+\-*/^]\s*\d+", user_text):
        expression = re.sub(r"[^0-9+\-*/().^ ]", "", user_text).strip()
        return json.dumps(
            {
                "tool": "calculator",
                "input": expression or user_text,
                "reason": "math expression",
            }
        )
    if any(token in user_text for token in ["remember", "recall", "what did i say"]):
        return json.dumps(
            {
                "tool": "memory_lookup",
                "input": "last 5 turns",
                "reason": "conversation recall",
            }
        )
    return json.dumps({"tool": "none", "input": "", "reason": ""})


def mock_needs_tool_callback(request: LLMRequest) -> str:
    prompt = request.prompt.lower()
    user_match = re.search(r"user message:(.*)", prompt, re.DOTALL)
    user_text = user_match.group(1).strip() if user_match else prompt
    if any(token in user_text for token in ["time", "date", "clock"]):
        return "YES"
    if re.search(r"\d+\s*[+\-*/^]\s*\d+", user_text):
        return "YES"
    if any(token in user_text for token in ["remember", "recall", "what did i say"]):
        return "YES"
    return "NO"


def build_tree(
    needs_tool_provider: LLMProvider,
    router_provider: LLMProvider,
    assistant_provider: LLMProvider,
    tools: list[Tool],
):
    needs_tool = LLMCondition(
        "needs_tool",
        provider=needs_tool_provider,
        question=(
            "Does the user request require using one of the tools below? "
            "Answer YES or NO.\n\n"
            "User: {user_input}"
        ),
    )

    route_tool = ToolRouterAction("tool_router", router_provider, tools)
    execute_tool = ToolExecuteAction("tool_executor", tools)

    tool_response = LLMAction(
        "assistant_with_tool",
        provider=assistant_provider,
        task=(
            "You are a helpful assistant. Use the tool output to answer.\n"
            "User: {user_input}\n"
            "Tool: {tool_name}\n"
            "Tool input: {tool_input}\n"
            "Tool output: {tool_output}\n"
            "Conversation history:\n{history_text}\n"
            "Answer concisely and cite the tool output if relevant."
        ),
        output_key="assistant_response",
    )

    direct_response = LLMAction(
        "assistant_direct",
        provider=assistant_provider,
        task=(
            "You are a helpful assistant. Answer the user without tools.\n"
            "User: {user_input}\n"
            "Conversation history:\n{history_text}\n"
            "Answer concisely."
        ),
        output_key="assistant_response",
    )

    tool_branch = Sequence(
        "tool_branch",
        [needs_tool, route_tool, execute_tool, tool_response],
    )

    root = Selector("chatbot_root", [tool_branch, direct_response])
    return root


async def main():  # noqa: C901
    parser = argparse.ArgumentParser(description="Interactive chatbot with tools")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM providers")
    parser.add_argument(
        "--assistant-model",
        default="llama3.2",
        help="Model for assistant responses",
    )
    parser.add_argument(
        "--router-model",
        default="llama3.2",
        help="Model for tool routing",
    )
    parser.add_argument(
        "--mock-cost-per-1k",
        type=float,
        default=0.002,
        help="Mock cost per 1k tokens",
    )
    parser.add_argument(
        "--router-cost-per-1k",
        type=float,
        default=0.0005,
        help="Mock router cost per 1k tokens",
    )
    parser.add_argument(
        "--mock-cost-per-call",
        type=float,
        default=0.0,
        help="Mock cost per call",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Stream events to the Treehouse visualizer",
    )
    parser.add_argument(
        "--server",
        default="ws://localhost:8000/ws/agent",
        help="Visualizer server WebSocket URL",
    )
    parser.add_argument(
        "--agent-name",
        default="chatbot_with_tools.py",
        help="Visualizer agent name",
    )
    args = parser.parse_args()

    if args.mock:
        needs_tool_provider = MockLLMProvider(
            MockConfig(
                response_callback=mock_needs_tool_callback,
                cost_per_1k_tokens=args.router_cost_per_1k,
                cost_per_call=args.mock_cost_per_call,
            ),
            model="mock-router",
        )
        router_provider = MockLLMProvider(
            MockConfig(
                response_callback=mock_router_callback,
                cost_per_1k_tokens=args.router_cost_per_1k,
                cost_per_call=args.mock_cost_per_call,
            ),
            model="mock-router",
        )
        assistant_provider = MockLLMProvider(
            MockConfig(
                default_response="This is a mock response.",
                cost_per_1k_tokens=args.mock_cost_per_1k,
                cost_per_call=args.mock_cost_per_call,
            ),
            model="mock-assistant",
        )
    else:
        needs_tool_provider = OllamaProvider(model=args.router_model)
        router_provider = OllamaProvider(model=args.router_model)
        assistant_provider = OllamaProvider(model=args.assistant_model)

    tools = [
        Tool(
            "calculator",
            "Evaluate math expressions like '12 * (3 + 4)'",
            tool_calculator,
        ),
        Tool(
            "time",
            "Get the current UTC time",
            tool_time,
        ),
        Tool(
            "memory_lookup",
            "Retrieve recent conversation turns (e.g. 'last 3 turns')",
            tool_memory_lookup,
        ),
    ]

    collector = TraceCollector()
    root = build_tree(needs_tool_provider, router_provider, assistant_provider, tools)
    tree = BehaviorTree(root=root, emitter=collector)
    debugger_tree = DebuggerTree(tree)

    debugger_client = None
    if args.visualize:
        debugger_client = DebuggerClient(
            url=args.server,
            command_handler=debugger_tree,
            agent_name=args.agent_name,
        )
        connected = await debugger_client.connect()
        if not connected:
            print("Visualizer connection failed; continuing without streaming.")
            debugger_client = None

    if debugger_client:
        collector.set_debugger(debugger_client)

        def handle_debugger_command(command: str, data: dict) -> None:
            debugger_client.send_sync({"type": command, "data": data})

        debugger_tree.set_command_handler(handle_debugger_command)
        debugger_tree.send_tree_structure()
        await debugger_client.send_event(
            {
                "type": "agent_idle",
                "data": {
                    "note": "Awaiting user input",
                },
            }
        )
    state: dict[str, object] = {
        "history": [],
    }

    print("Chatbot started. Type 'exit' to quit.")
    try:
        while True:
            user_input = (await asyncio.to_thread(input, "\nYou: ")).strip()
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                break

            history = cast(list[dict[str, str]], state.get("history", []))
            history_text = "\n".join(
                f"{item['role']}: {item['content']}" for item in history[-8:]
            )

            state["user_input"] = user_input
            state["history_text"] = history_text
            state["tool_name"] = "none"
            state["tool_input"] = ""
            state["tool_output"] = ""
            state["assistant_response"] = ""
            collector.set_state(state)

            if debugger_client:
                await debugger_client.send_event(
                    {
                        "type": "agent_active",
                        "data": {"note": "Running behavior tree"},
                    }
                )
                await debugger_tree.tick_async(state)
            else:
                await asyncio.to_thread(tree.tick, state)

            response = str(state.get("assistant_response", ""))
            print(f"Assistant: {response}")

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            state["history"] = history

            if debugger_client:
                await debugger_client.send_event(
                    {
                        "type": "agent_idle",
                        "data": {
                            "note": "Awaiting user input",
                        },
                    }
                )
    finally:
        if debugger_client:
            await debugger_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
