"""Chat with the agent in your terminal.

    python -m agent.cli "Find my note about demo day and email alex@example.com about demo day"
"""
import sys
import uuid

from langgraph.types import Command

from .graph import build_graph


def run(task: str, approve=input):
    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = graph.invoke({"task": task}, config)

    while "__interrupt__" in result:  # paused for a human
        ask = result["__interrupt__"][0].value
        print(f"\nAgent wants to run {ask['tool']} with {ask['args']}")
        answer = approve("Approve? [y/N] ")
        result = graph.invoke(Command(resume=answer), config)

    print("\nPlan:")
    for i, s in enumerate(result["plan"], 1):
        print(f"  {i}. {s['tool']}")
    print("\nResult:\n" + result["summary"])
    return result


if __name__ == "__main__":
    run(" ".join(sys.argv[1:]) or input("Task: "))
