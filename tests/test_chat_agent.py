"""Tests the chatbot's agent loop end to end WITHOUT an API key.

A fake "scripted" model replaces Claude; everything else is real:
the MCP client, the MCP server process, the rules, and Postgres.
"""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chat_app.agent import OrderAgent  # noqa: E402


class ScriptedModel:
    """Pretends to be the Claude API: returns pre-written responses in order, records requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = NS(messages=NS(create=self._create))

    async def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})  # snapshot
        return self.responses.pop(0)


def tool_call(name, args, id_="call_1"):
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", id=id_, name=name, input=args)])


def answer(text):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=text)])


async def _run(responses, question):
    model = ScriptedModel(responses)
    agent = OrderAgent(client=model)
    await agent.connect()
    try:
        history = []
        result = await agent.run(history, question)
        return agent, model, history, result
    finally:
        await agent.close()


def test_agent_discovers_tools_over_mcp():
    agent, model, _, _ = asyncio.run(_run([answer("hi")], "hello"))
    assert {t["name"] for t in agent.tools} == {"find_late_orders", "flag_address_mismatch"}
    assert model.requests[0]["tools"] == agent.tools          # tool list was sent to the model


def test_loop_runs_tool_and_feeds_result_back():
    _, model, history, result = asyncio.run(_run(
        [tool_call("find_late_orders", {"days_ahead": 7}), answer("12 orders are at risk.")],
        "Which orders are at risk?"))
    assert result["reply"] == "12 orders are at risk."
    assert result["steps"][0]["tool"] == "find_late_orders"
    assert result["steps"][0]["summary"] == "12 order(s) returned"
    # The second request to the model must contain the real tool result from Postgres.
    tool_result = model.requests[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "call_1"
    assert json.loads(tool_result["content"])["count"] == 12


def test_unknown_write_tool_is_refused_not_executed():
    """Even if the model invents an 'update_order' tool, the MCP server has no such tool."""
    _, model, _, result = asyncio.run(_run(
        [tool_call("update_order", {"order_number": "ORD-1016", "status": "delivered"}),
         answer("I can only flag orders, not edit them.")],
        "Mark ORD-1016 as delivered"))
    tool_result = model.requests[1]["messages"][-1]["content"][0]
    assert tool_result.get("is_error") is True
    assert result["steps"][0]["summary"].startswith("error")
