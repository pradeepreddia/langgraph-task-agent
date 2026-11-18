"""Web UI that streams LangGraph node events so you can watch the agent coordinate.

    python -m agent.web    ->  http://localhost:8000
"""
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from langgraph.types import Command

from .graph import build_graph

STATIC = Path(__file__).resolve().parent / "static"
app = Flask(__name__)
graph = build_graph()  # one graph + checkpointer shared across requests


def _stream(payload, thread_id: str) -> dict:
    """Run until the graph finishes or pauses; return every node event in order."""
    config = {"configurable": {"thread_id": thread_id}}
    events, pending = [], None
    for chunk in graph.stream(payload, config, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "__interrupt__":
                pending = update[0].value
                events.append({"node": "approval", "tool": pending["tool"], "args": pending["args"]})
            elif node == "plan":
                events.append({"node": "plan", "plan": [s["tool"] for s in update["plan"]]})
            elif node == "execute":
                last = update["results"][-1]
                events.append({"node": "execute", "tool": last["tool"], "output": str(last["output"])[:300]})
            elif node == "summarize":
                events.append({"node": "summarize", "summary": update["summary"]})
    return {"thread_id": thread_id, "events": events, "pending": pending, "done": pending is None}


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.post("/api/run")
def run():
    task = (request.get_json(silent=True) or {}).get("task", "").strip()
    if not task:
        return jsonify(error="task is required"), 400
    return _stream({"task": task}, str(uuid.uuid4()))


@app.post("/api/resume")
def resume():
    body = request.get_json(silent=True) or {}
    if not body.get("thread_id"):
        return jsonify(error="thread_id is required"), 400
    return _stream(Command(resume=body.get("decision", "no")), body["thread_id"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
