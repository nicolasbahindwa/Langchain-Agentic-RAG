# #!/usr/bin/env python3
# """
# Interactive CLI for the RAG graph with human-in-the-loop support.
# """

# import os
# import sys
# from typing import Dict, Any

# from graph import app 




# # ------------------------------------------------------------------
# # Pretty printer
# # ------------------------------------------------------------------
# def print_step(name: str, data: Dict[str, Any]) -> None:
#     print(f"\n● {name}")
#     if "ai_feedback_request" in data:
#         print("💬", data["ai_feedback_request"])
#     elif "final_answer" in data:
#         print("\n" + "="*60)
#         print(data["final_answer"])
#         print("="*60)
#     elif "current_question" in data:
#         print("📝 Reframed question →", data["current_question"])
#     elif "retrieved_docs" in data:
#         print("📚 Retrieved", len(data["retrieved_docs"]), "document(s)")
#     elif "error" in data:
#         print("❌", data["error"])

# # ------------------------------------------------------------------
# # Main loop
# # ------------------------------------------------------------------
# def main() -> None:
#     thread = {"configurable": {"thread_id": "cli_demo"}}
#     state = {
#         "original_question": input("Ask me anything: ").strip(),
#         "human_feedback": None,
#         "feedback_cycles": 0
#     }

#     while True:
#         # Stream every update
#         for step_name, payload in app.stream(state, thread, stream_mode="updates"):
#             print_step(step_name, payload)

#         # Check if we are paused waiting for human input
#         snapshot = app.get_state(thread)
#         if snapshot.next and "request_human_feedback" in snapshot.next:
#             feedback = input("\n👉 Your feedback (empty = continue as-is): ").strip()
#             state = snapshot.values
#             state["human_feedback"] = feedback or None
#             continue   # continue the loop – graph will resume

#         # No more steps -> we are done
#         if not snapshot.next:
#             break

#     print("\n✅ Done.")

# if __name__ == "__main__":
#     try:
#         main()
#     except KeyboardInterrupt:
#         print("\nInterrupted by user.")

# from core.search_manager import ResultCleaner, create_search_manager
# from langchain_community.graphs import ArangoGraph


# def chat_with_agent(user_input: str, conversation_state: Dict[str, Any] = None):
#     """
#     Chat with the agent, maintaining conversation history automatically
    
#     Args:
#         user_input: The user's question/message
#         conversation_state: Previous conversation state (optional)
    
#     Returns:
#         Updated conversation state with new messages and response
#     """
#     # Create new human message
#     new_message = HumanMessage(content=user_input)
    
#     # Initialize or update state
#     if conversation_state is None:
#         # First interaction
#         initial_state = {
#             "messages": [new_message],
#             "current_question": "",
#             "search_results": [],
#             "answer": ""
#         }
#     else:
#         # Continue conversation - add_messages will handle appending automatically
#         initial_state = {
#             **conversation_state,
#             "messages": [new_message]  # This gets added to existing messages
#         }
    
#     # Run the agent
#     result = app.invoke(initial_state)
    
#     print(f"🤖 Answer: {result.get('answer', 'No answer generated')}\n")
#     return result

# # Example usage demonstrating conversation flow
# if __name__ == "__main__":
#     print("🚀 Starting RAG Agent Conversation\n")
    
#     # First question
#     print("=" * 50)
#     state1 = chat_with_agent("What is machine learning?")
    
#     # Second question - history maintained automatically
#     print("=" * 50)
#     state2 = chat_with_agent("What is deep learning?", state1)
    
#     # Third question - building on conversation
#     print("=" * 50)
#     state3 = chat_with_agent("How are they different?", state2)
    
#     # Print final conversation history
#     print("\n" + "=" * 50)
#     print("📚 CONVERSATION HISTORY:")
#     for i, msg in enumerate(state3.get("messages", []), 1):
#         role = "Human" if isinstance(msg, HumanMessage) else "AI"
#         content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
#         print(f"{i}. {role}: {content}")