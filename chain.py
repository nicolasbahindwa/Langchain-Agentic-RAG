# rag_chat.py
from core.llm_manager import LLMManager, LLMProvider
from core.config import config
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Initialize manager
manager = LLMManager()

# Create a chat model (switch providers here)
llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,  # Change to OLLAMA or OPENAI
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=256
)

# Build a simple RAG chain
prompt = ChatPromptTemplate.from_messages([
    ("system", "You're a helpful assistant. Use the context to answer questions."),
    ("human", "Context:\n{context}\n\nQuestion: {question}")
])

chain = prompt | llm | StrOutputParser()

# Example usage
context = """
Quantum computing uses quantum bits (qubits) that can exist in multiple states simultaneously.
This allows quantum computers to solve certain problems much faster than classical computers.
Key concepts include superposition and entanglement.
"""

response = chain.invoke({
    "context": context,
    "question": "Explain quantum computing in simple terms"
})

print("🤖 Assistant Response:")
print(response)