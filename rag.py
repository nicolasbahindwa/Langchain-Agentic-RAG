
# from langchain_community.vectorstores import Chroma

# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from langchain_core.runnables import RunnablePassthrough

# from langchain_community.document_loaders import WebBaseLoader

# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_huggingface import HuggingFaceEmbeddings
# from core.llm_manager import LLMManager, LLMProvider
# from urllib.error import HTTPError, URLError



# manager = LLMManager()
 



# URLS_DICTIONARY = {
#     "ufc_ibm_partnership": "https://newsroom.ibm.com/2024-11-14-ufc-names-ibm-as-first-ever-official-ai-partner",
#     "granite.html": "https://www.ibm.com/granite",
#     "products_watsonx_ai.html": "https://www.ibm.com/products/watsonx-ai",
#     "products_watsonx_ai_foundation_models.html": "https://www.ibm.com/products/watsonx-ai/foundation-models",
#     "watsonx_pricing.html": "https://www.ibm.com/watsonx/pricing",
#     "watsonx.html": "https://www.ibm.com/watsonx",
#     "products_watsonx_data.html": "https://www.ibm.com/products/watsonx-data",
#     "products_watsonx_assistant.html": "https://www.ibm.com/products/watsonx-assistant",
#     "products_watsonx_code_assistant.html": "https://www.ibm.com/products/watsonx-code-assistant",
#     "products_watsonx_orchestrate.html": "https://www.ibm.com/products/watsonx-orchestrate",
#     "products_watsonx_governance.html": "https://www.ibm.com/products/watsonx-governance",
#     "granite_code_models_open_source.html": "https://research.ibm.com/blog/granite-code-models-open-source",
#     "red_hat_enterprise_linux_ai.html": "https://www.redhat.com/en/about/press-releases/red-hat-delivers-accessible-open-source-generative-ai-innovation-red-hat-enterprise-linux-ai",
#     "model_choice.html": "https://www.ibm.com/blog/announcement/enterprise-grade-model-choices/",
#     "democratizing.html": "https://www.ibm.com/blog/announcement/democratizing-large-language-model-development-with-instructlab-support-in-watsonx-ai/",
#     "ibm_consulting_expands_ai.html": "https://newsroom.ibm.com/Blog-IBM-Consulting-Expands-Capabilities-to-Help-Enterprises-Scale-AI",
#     "ibm_data_product_hub.html": "https://www.ibm.com/products/data-product-hub",
#     "ibm_price_performance_data.html": "https://www.ibm.com/blog/announcement/delivering-superior-price-performance-and-enhanced-data-management-for-ai-with-ibm-watsonx-data/",
#     "ibm_bi_adoption.html": "https://www.ibm.com/blog/a-new-era-in-bi-overcoming-low-adoption-to-make-smart-decisions-accessible-for-all/",
#     "code_assistant_for_java.html": "https://www.ibm.com/blog/announcement/watsonx-code-assistant-java/",
#     "accelerating_gen_ai.html": "https://newsroom.ibm.com/Blog-How-IBM-Cloud-is-Accelerating-Business-Outcomes-with-Gen-AI",
#     "watsonx_open_source.html": "https://newsroom.ibm.com/2024-05-21-IBM-Unveils-Next-Chapter-of-watsonx-with-Open-Source,-Product-Ecosystem-Innovations-to-Drive-Enterprise-AI-at-Scale",
#     "ibm_concert.html": "https://www.ibm.com/products/concert",
#     "ibm_consulting_advantage_news.html": "https://newsroom.ibm.com/2024-01-17-IBM-Introduces-IBM-Consulting-Advantage,-an-AI-Services-Platform-and-Library-of-Assistants-to-Empower-Consultants",
#     "ibm_consulting_advantage_info.html": "https://www.ibm.com/consulting/info/ibm-consulting-advantage"
# }
# COLLECTION_NAME = "askibm_2024"

# documents = []

# # for url in list(URLS_DICTIONARY.values()):
# #     loader = WebBaseLoader(url)
# #     data = loader.load()
# #     documents += data

# for url_name , url in URLS_DICTIONARY.items():
#     try:
#         loader = WebBaseLoader(url)
#         data = loader.load()
#         for doc in data:
#             # clean content 
#             doc.page_content = " ".join(doc.page_content.split())
#             doc.metadata["source_id"] = url_name
#         documents.extend(data)
#     except (HTTPError, URLError) as e:
#         print(f" Failed to load {url}: {str(e)}")


# documents[0].page_content

# for doc in documents:
#     doc.page_content = " ".join(doc.page_content.split())

# documents[0].page_content
# # print(documents[0].page_content)



# text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=0)
# docs = text_splitter.split_documents(documents)

# print("**" * 50)
# for doc in docs:
#     print("*" * 50)
#     print(doc)

# embedding_model = HuggingFaceEmbeddings(
#     model_name = "sentence-transformers/all-MiniLM-L6-v2"
# )
# PERSIST_DIRECTORY = "./chroma_db"
# vectorstore = Chroma.from_documents(
#     documents=docs,
#     embedding=embedding_model,
#     collection_name=COLLECTION_NAME,
#     persist_directory=PERSIST_DIRECTORY
# )

# # vectorstore.persist()
# print(f"vector store created with {len(docs)} emmbeddings")


# retriever = vectorstore.as_retriever(search_kwargs={"k":4})


# template = """Generate a summary of the context that answers the question. Explain the answer in multiple steps if possible.
# answer style should match the context. Ideal answer leng 2-3 sentences.\n\n {context}\n Question:{question}\nAnswer:
# """

# prompt = ChatPromptTemplate.from_template(template)


# def format_docs(docs):
#     return "\n\n".join([d.page_content for d in docs])

# llm = manager.get_chat_model(
#     provider=LLMProvider.ANTHROPIC,
#     model="claude-3-haiku-20240307",
#     temperature=0.7,
#     max_tokens=1500
# )

# rag_chain = (
#     {"context": retriever | format_docs, "question": RunnablePassthrough()}
#     | prompt
#     |llm
#     |StrOutputParser()
# )


# response = rag_chain.invoke("Tell me about the UFC announcement from November 14, 2024")

# print(response)


from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from core.llm_manager import LLMManager, LLMProvider
from urllib.error import HTTPError, URLError

# State definition
class RAGState(TypedDict):
    question: str
    documents: List
    chunks: List
    context: str
    answer: str
    error: str

# Initialize components
manager = LLMManager()
URLS_DICTIONARY = {
    "ufc_ibm_partnership": "https://newsroom.ibm.com/2024-11-14-ufc-names-ibm-as-first-ever-official-ai-partner",
    "granite.html": "https://www.ibm.com/granite",
    "products_watsonx_ai.html": "https://www.ibm.com/products/watsonx-ai",
    "products_watsonx_ai_foundation_models.html": "https://www.ibm.com/products/watsonx-ai/foundation-models",
    "watsonx_pricing.html": "https://www.ibm.com/watsonx/pricing",
    "watsonx.html": "https://www.ibm.com/watsonx",
    "products_watsonx_data.html": "https://www.ibm.com/products/watsonx-data",
    "products_watsonx_assistant.html": "https://www.ibm.com/products/watsonx-assistant",
    "products_watsonx_code_assistant.html": "https://www.ibm.com/products/watsonx-code-assistant",
    "products_watsonx_orchestrate.html": "https://www.ibm.com/products/watsonx-orchestrate",
    "products_watsonx_governance.html": "https://www.ibm.com/products/watsonx-governance",
    "granite_code_models_open_source.html": "https://research.ibm.com/blog/granite-code-models-open-source",
    "red_hat_enterprise_linux_ai.html": "https://www.redhat.com/en/about/press-releases/red-hat-delivers-accessible-open-source-generative-ai-innovation-red-hat-enterprise-linux-ai",
    "model_choice.html": "https://www.ibm.com/blog/announcement/enterprise-grade-model-choices/",
    "democratizing.html": "https://www.ibm.com/blog/announcement/democratizing-large-language-model-development-with-instructlab-support-in-watsonx-ai/",
    "ibm_consulting_expands_ai.html": "https://newsroom.ibm.com/Blog-IBM-Consulting-Expands-Capabilities-to-Help-Enterprises-Scale-AI",
    "ibm_data_product_hub.html": "https://www.ibm.com/products/data-product-hub",
    "ibm_price_performance_data.html": "https://www.ibm.com/blog/announcement/delivering-superior-price-performance-and-enhanced-data-management-for-ai-with-ibm-watsonx-data/",
    "ibm_bi_adoption.html": "https://www.ibm.com/blog/a-new-era-in-bi-overcoming-low-adoption-to-make-smart-decisions-accessible-for-all/",
    "code_assistant_for_java.html": "https://www.ibm.com/blog/announcement/watsonx-code-assistant-java/",
    "accelerating_gen_ai.html": "https://newsroom.ibm.com/Blog-How-IBM-Cloud-is-Accelerating-Business-Outcomes-with-Gen-AI",
    "watsonx_open_source.html": "https://newsroom.ibm.com/2024-05-21-IBM-Unveils-Next-Chapter-of-watsonx-with-Open-Source,-Product-Ecosystem-Innovations-to-Drive-Enterprise-AI-at-Scale",
    "ibm_concert.html": "https://www.ibm.com/products/concert",
    "ibm_consulting_advantage_news.html": "https://newsroom.ibm.com/2024-01-17-IBM-Introduces-IBM-Consulting-Advantage,-an-AI-Services-Platform-and-Library-of-Assistants-to-Empower-Consultants",
    "ibm_consulting_advantage_info.html": "https://www.ibm.com/consulting/info/ibm-consulting-advantage"
}

COLLECTION_NAME = "askibm_2024"
PERSIST_DIRECTORY = "./chroma_db"

# Initialize components
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=0)

template = """Generate a summary of the context that answers the question. Explain the answer in multiple steps if possible.
answer style should match the context. Ideal answer length 2-3 sentences.\n\n {context}\n Question:{question}\nAnswer:
"""
prompt = ChatPromptTemplate.from_template(template)

llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=1500
)

# Node functions
def load_documents(state: RAGState) -> RAGState:
    """Load documents from URLs"""
    print("Loading documents...")
    documents = []
    
    for url_name, url in URLS_DICTIONARY.items():
        try:
            loader = WebBaseLoader(url)
            data = loader.load()
            for doc in data:
                # Clean content
                doc.page_content = " ".join(doc.page_content.split())
                doc.metadata["source_id"] = url_name
            documents.extend(data)
        except (HTTPError, URLError) as e:
            print(f"Failed to load {url}: {str(e)}")
    
    state["documents"] = documents
    print(f"Loaded {len(documents)} documents")
    return state

def chunk_documents(state: RAGState) -> RAGState:
    """Split documents into chunks"""
    print("Chunking documents...")
    documents = state["documents"]
    
    # Clean documents
    for doc in documents:
        doc.page_content = " ".join(doc.page_content.split())
    
    # Split documents
    chunks = text_splitter.split_documents(documents)
    state["chunks"] = chunks
    print(f"Created {len(chunks)} chunks")
    return state

def create_vectorstore(state: RAGState) -> RAGState:
    """Create vector store from chunks"""
    print("Creating vector store...")
    chunks = state["chunks"]
    
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        collection_name=COLLECTION_NAME,
        persist_directory=PERSIST_DIRECTORY
    )
    
    state["vectorstore"] = vectorstore
    print(f"Vector store created with {len(chunks)} embeddings")
    return state

def retrieve_context(state: RAGState) -> RAGState:
    """Retrieve relevant context for the question"""
    print("Retrieving context...")
    question = state["question"]
    vectorstore = state["vectorstore"]
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    docs = retriever.invoke(question)
    
    context = "\n\n".join([d.page_content for d in docs])
    state["context"] = context
    print(f"Retrieved {len(docs)} relevant documents")
    return state

def generate_answer(state: RAGState) -> RAGState:
    """Generate answer using LLM"""
    print("Generating answer...")
    question = state["question"]
    context = state["context"]
    
    # Create chain
    chain = prompt | llm | StrOutputParser()
    
    # Generate response
    response = chain.invoke({"context": context, "question": question})
    state["answer"] = response
    print("Answer generated")
    return state

# Create the graph
workflow = StateGraph(RAGState)

# Add nodes
workflow.add_node("load_documents", load_documents)
workflow.add_node("chunk_documents", chunk_documents)
workflow.add_node("create_vectorstore", create_vectorstore)
workflow.add_node("retrieve_context", retrieve_context)
workflow.add_node("generate_answer", generate_answer)

# Add edges
workflow.set_entry_point("load_documents")
workflow.add_edge("load_documents", "chunk_documents")
workflow.add_edge("chunk_documents", "create_vectorstore")
workflow.add_edge("create_vectorstore", "retrieve_context")
workflow.add_edge("retrieve_context", "generate_answer")
workflow.add_edge("generate_answer", END)

# Compile the graph
app = workflow.compile()

# Usage example
if __name__ == "__main__":
    # Initialize state
    initial_state = {
        "question": "Tell me about the UFC announcement from November 14, 2024",
        "documents": [],
        "chunks": [],
        "context": "",
        "answer": "",
        "error": ""
    }
    
    # Run the graph
    print("Starting RAG pipeline...")
    result = app.invoke(initial_state)
    
    print("\n" + "="*50)
    print("FINAL ANSWER:")
    print("="*50)
    print(result["answer"])
    
    # Optional: Visualize the graph
    try:
        from IPython.display import Image, display
        display(Image(app.get_graph().draw_mermaid_png()))
    except:
        print("\nGraph structure:")
        print("load_documents -> chunk_documents -> create_vectorstore -> retrieve_context -> generate_answer")