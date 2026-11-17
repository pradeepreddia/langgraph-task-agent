import json
import uuid

import pytest
from langgraph.types import Command

from agent import tools
from agent.graph import build_graph
from agent.planner import rule_plan


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(tools, "OUTBOX", tmp_path / "outbox.jsonl")
    monkeypatch.setattr(tools, "TODOS", tmp_path / "todos.jsonl")


def cfg():
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


def test_calculator_is_safe():
    assert tools.calculator("25 * 8") == "200"
    with pytest.raises(ValueError):
        tools.calculator("__import__('os').system('ls')")


def test_rule_planner_email_flow():
    steps = rule_plan("find my note about demo day and email alex@example.com about demo day")
    assert [s["tool"] for s in steps] == ["search_notes", "draft_email", "send_email"]


def test_graph_runs_math_without_interrupt():
    out = build_graph().invoke({"task": "what is 25 * 8"}, cfg())
    assert "200" in out["summary"]


def test_graph_pauses_for_email_then_sends_on_yes():
    g, c = build_graph(), cfg()
    out = g.invoke({"task": "email alex@example.com about demo day"}, c)
    assert out["__interrupt__"][0].value["tool"] == "send_email"
    out = g.invoke(Command(resume="yes"), c)
    sent = json.loads(tools.OUTBOX.read_text().splitlines()[0])
    assert sent["to"] == "alex@example.com"


def test_graph_respects_no():
    g, c = build_graph(), cfg()
    g.invoke({"task": "add todo: book demo room"}, c)
    out = g.invoke(Command(resume="no"), c)
    assert "denied" in out["summary"]
    assert not tools.TODOS.exists()
