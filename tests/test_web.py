import pytest

from agent import tools
from agent.web import app


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(tools, "OUTBOX", tmp_path / "outbox.jsonl")
    monkeypatch.setattr(tools, "TODOS", tmp_path / "todos.jsonl")


def test_run_streams_events_and_pauses():
    c = app.test_client()
    r = c.post("/api/run", json={"task": "email alex@example.com about demo day"}).json
    assert [e["node"] for e in r["events"]] == ["plan", "execute", "approval"]
    assert r["pending"]["tool"] == "send_email" and not r["done"]

    r2 = c.post("/api/resume", json={"thread_id": r["thread_id"], "decision": "yes"}).json
    assert [e["node"] for e in r2["events"]] == ["execute", "summarize"] and r2["done"]


def test_run_requires_task():
    assert app.test_client().post("/api/run", json={}).status_code == 400
