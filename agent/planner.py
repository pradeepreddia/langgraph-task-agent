"""Turns a task into a list of tool steps.

LLM planner when OPENAI_API_KEY is set; otherwise a small rule-based planner
so the graph can be explored (and tested) offline.
"""
import json
import os
import re

from .tools import TOOL_DOCS

PLAN_PROMPT = """You are a planning agent. Break the task into tool calls.
Available tools:
{tools}

Return JSON: {{"steps": [{{"tool": "...", "args": {{...}}}}]}}
Use "$prev" as an arg value to pass the previous step's output.
Task: {task}"""


def llm_plan(task: str) -> list[dict]:
    from openai import OpenAI

    resp = OpenAI().chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": PLAN_PROMPT.format(tools=TOOL_DOCS, task=task)}],
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)["steps"]


def rule_plan(task: str) -> list[dict]:
    t = task.lower()
    steps = []
    math = re.search(r"[\d\.\s\(\)]+[\+\-\*/%][\d\.\s\(\)\+\-\*/%]+", task)
    if math:
        steps.append({"tool": "calculator", "args": {"expression": math.group().strip()}})
    if any(w in t for w in ("note", "find", "look up", "remind me what")):
        topic = re.sub(r".*?(about|for|on)\s+", "", t, count=1) or t
        steps.append({"tool": "search_notes", "args": {"query": topic}})
    if "email" in t:
        to = re.search(r"[\w\.-]+@[\w\.-]+", task)
        topic = re.search(r"about (.+?)(?: and |$|\.)", t)
        steps.append({"tool": "draft_email", "args": {
            "to": to.group() if to else "manager@example.com",
            "topic": topic.group(1) if topic else "status update",
            "context": "$prev"}})
        steps.append({"tool": "send_email", "args": "$draft"})
    if "todo" in t or "add a task" in t:
        item = re.search(r"todo:?\s*(.+)", task, re.I)
        steps.append({"tool": "add_todo", "args": {"item": item.group(1) if item else task}})
    return steps


def make_plan(task: str) -> list[dict]:
    return llm_plan(task) if os.getenv("OPENAI_API_KEY") else rule_plan(task)
