"""The LangGraph state machine.

    START -> plan -> execute (loops per step) -> summarize -> END
                         |
                         +-- sensitive tool? -> interrupt() and wait for a human yes/no
"""
import json
import os
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .planner import make_plan
from .tools import SENSITIVE, TOOLS


class AgentState(TypedDict, total=False):
    task: str
    plan: list[dict]
    step: int
    results: list[dict]
    summary: str


def plan_node(state: AgentState) -> AgentState:
    return {"plan": make_plan(state["task"]), "step": 0, "results": []}


def _resolve_args(args: Any, results: list[dict]) -> dict:
    prev = results[-1]["output"] if results else ""
    if args == "$draft":  # send exactly what draft_email produced
        return json.loads(prev)
    return {k: (prev if v == "$prev" else v) for k, v in args.items()}


def execute_node(state: AgentState) -> AgentState:
    step = state["plan"][state["step"]]
    tool, args = step["tool"], _resolve_args(step["args"], state["results"])

    if tool in SENSITIVE:
        decision = interrupt({"tool": tool, "args": args, "question": f"Allow {tool}?"})
        if str(decision).lower() not in ("y", "yes", "approve"):
            out = f"skipped: human denied {tool}"
            return {"results": state["results"] + [{"tool": tool, "output": out}], "step": state["step"] + 1}

    try:
        out = TOOLS[tool](**args)
    except Exception as e:  # keep the agent alive and record the failure
        out = f"error: {e}"
    return {"results": state["results"] + [{"tool": tool, "args": args, "output": out}],
            "step": state["step"] + 1}


def route(state: AgentState) -> str:
    return "execute" if state["step"] < len(state["plan"]) else "summarize"


def summarize_node(state: AgentState) -> AgentState:
    lines = [f"{r['tool']}: {r['output']}" for r in state["results"]]
    if os.getenv("OPENAI_API_KEY") and lines:
        from openai import OpenAI

        msg = f"Task: {state['task']}\nTool results:\n" + "\n".join(lines) + "\nSummarize for the user in 2 sentences."
        resp = OpenAI().chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), messages=[{"role": "user", "content": msg}])
        return {"summary": resp.choices[0].message.content}
    return {"summary": "\n".join(lines) or "I had no tools for that task."}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("plan", plan_node)
    g.add_node("execute", execute_node)
    g.add_node("summarize", summarize_node)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", route, ["execute", "summarize"])
    g.add_conditional_edges("execute", route, ["execute", "summarize"])
    g.add_edge("summarize", END)
    return g.compile(checkpointer=MemorySaver())
