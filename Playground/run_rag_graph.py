import uuid
from langchain_core.messages import HumanMessage
from QandA import compile_graph as graph  # compiled_graph is required

def run():
    print("🤖 Welcome to the RAG CLI assistant.")
    original_question = input("📝 Enter your question: ").strip()

    if not original_question:
        print("⚠️ Please enter a valid question.")
        return

    thread_id = f"cli-thread-{uuid.uuid4()}"

    config = {
        "original_question": original_question,
        "question": original_question,
        "messages": [HumanMessage(content=original_question)],
        "context": [],
        "ranked_context": [],
        "context_scores": [],
        "process_cycle_count": 0,
        "user_feedback": "",
        "feedback_cycle_count": 0,
        "needs_feedback": False,
        "configurable": {
            "thread_id": thread_id
        }
    }

    for event in graph.stream(config):
        if event["type"] == "on_interrupt":
            feedback_prompt = event["value"].get("message", "🛑 Feedback required:")
            print(f"\n{feedback_prompt}")
            user_feedback = input("✍️  Your feedback: ").strip()
            graph.send(user_feedback)
        elif event["type"] == "on_complete":
            final_state = event["value"]
            print("\n✅ Answer:")
            print(final_state["answer"])
            break

if __name__ == "__main__":
    run()
