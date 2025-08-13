#!/usr/bin/env python3
"""
Interactive CLI for the RAG graph with human-in-the-loop support.
"""

import os
import sys
from typing import Dict, Any

# Make sure we can import the graph you pasted above
# (rename if your file is different)
from graph import app          # <- change to your filename
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()                 # same instance the graph uses

# ------------------------------------------------------------------
# Pretty printer
# ------------------------------------------------------------------
def print_step(name: str, data: Dict[str, Any]) -> None:
    print(f"\n● {name}")
    if "ai_feedback_request" in data:
        print("💬", data["ai_feedback_request"])
    elif "final_answer" in data:
        print("\n" + "="*60)
        print(data["final_answer"])
        print("="*60)
    elif "current_question" in data:
        print("📝 Reframed question →", data["current_question"])
    elif "retrieved_docs" in data:
        print("📚 Retrieved", len(data["retrieved_docs"]), "document(s)")
    elif "error" in data:
        print("❌", data["error"])

# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------
def main() -> None:
    thread = {"configurable": {"thread_id": "cli_demo"}}
    state = {
        "original_question": input("Ask me anything: ").strip(),
        "human_feedback": None,
        "feedback_cycles": 0
    }

    while True:
        # Stream every update
        for step_name, payload in app.stream(state, thread, stream_mode="updates"):
            print_step(step_name, payload)

        # Check if we are paused waiting for human input
        snapshot = app.get_state(thread)
        if snapshot.next and "request_human_feedback" in snapshot.next:
            feedback = input("\n👉 Your feedback (empty = continue as-is): ").strip()
            state = snapshot.values
            state["human_feedback"] = feedback or None
            continue   # continue the loop – graph will resume

        # No more steps -> we are done
        if not snapshot.next:
            break

    print("\n✅ Done.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")