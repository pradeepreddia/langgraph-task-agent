"""Tools the agent can call. Some are 'sensitive' and need a human yes first."""
import ast
import json
import operator
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
OUTBOX = DATA / "outbox.jsonl"
TODOS = DATA / "todos.jsonl"

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg}


def calculator(expression: str) -> str:
    """Safe math: only numbers and + - * / ** %. No eval()."""
    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        raise ValueError(f"unsupported expression: {expression}")
    return str(round(ev(ast.parse(expression, mode="eval").body), 4))


def search_notes(query: str) -> str:
    notes = json.loads((DATA / "notes.json").read_text())
    stop = {"the", "and", "for", "about", "with", "email", "find", "note", "notes", "my"}
    words = {w for w in query.lower().split() if len(w) > 2 and w not in stop}
    hits = [n for n in notes if words & set(n["text"].lower().replace(".", "").split())]
    return "\n".join(f"- {n['title']}: {n['text']}" for n in hits) or "no matching notes"


def draft_email(to: str, topic: str, context: str = "") -> str:
    body = f"Hi,\n\nQuick note about {topic}.\n{context}\n\nThanks,\nPradeep"
    return json.dumps({"to": to, "subject": topic.title(), "body": body})


def send_email(to: str, subject: str, body: str) -> str:
    """Fake send: appends to data/outbox.jsonl. Nothing leaves your machine."""
    with OUTBOX.open("a") as f:
        f.write(json.dumps({"to": to, "subject": subject, "body": body}) + "\n")
    return f"email to {to} saved to outbox"


def add_todo(item: str) -> str:
    with TODOS.open("a") as f:
        f.write(json.dumps({"item": item, "added": date.today().isoformat()}) + "\n")
    return f"todo added: {item}"


TOOLS = {"calculator": calculator, "search_notes": search_notes, "draft_email": draft_email,
         "send_email": send_email, "add_todo": add_todo}
SENSITIVE = {"send_email", "add_todo"}

TOOL_DOCS = """calculator(expression) - safe arithmetic
search_notes(query) - keyword search over personal notes
draft_email(to, topic, context) - returns a JSON draft {to, subject, body}
send_email(to, subject, body) - sends an email (NEEDS HUMAN APPROVAL)
add_todo(item) - adds a todo (NEEDS HUMAN APPROVAL)"""
