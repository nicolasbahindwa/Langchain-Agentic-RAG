
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
import traceback

# State definition
class RAGState(TypedDict):
    question: str
    documents: List
    chunks: List
    context: str
    answer: str
    error: str
    vectorstore: object  # Add this to make it explicit

# Initialize components
manager = LLMManager()
URLS_DICTIONARY = {
    "tomato_plantation": "https://www.almanac.com/plant/tomatoes",
    "how_to_grow_tomatoes": "https://eos.com/blog/how-to-grow-tomatoes/",
    "crops_management_guide":"https://eos.com/crop-management-guide/tomato-growth-stages/"
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

# Node functions with improved error handling
def load_documents(state: RAGState) -> RAGState:
    """Load documents from URLs"""
    print("Loading documents...")
    documents = []
    
    try:
        for url_name, url in URLS_DICTIONARY.items():
            try:
                loader = WebBaseLoader(url)
                data = loader.load()
                for doc in data:
                    # Clean content
                    doc.page_content = " ".join(doc.page_content.split())
                    doc.metadata["source_id"] = url_name
                documents.extend(data)
                print(f"Successfully loaded {url_name}")
            except (HTTPError, URLError) as e:
                print(f"Failed to load {url}: {str(e)}")
                state["error"] = f"Failed to load {url}: {str(e)}"
        
        state["documents"] = documents
        print(f"Loaded {len(documents)} documents total")
        
    except Exception as e:
        error_msg = f"Error in load_documents: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        state["error"] = error_msg
    
    return state

def chunk_documents(state: RAGState) -> RAGState:
    """Split documents into chunks"""
    print("Chunking documents...")
    
    try:
        documents = state.get("documents", [])
        if not documents:
            error_msg = "No documents found to chunk"
            print(error_msg)
            state["error"] = error_msg
            return state
        
        # Clean documents
        for doc in documents:
            doc.page_content = " ".join(doc.page_content.split())
        
        # Split documents
        chunks = text_splitter.split_documents(documents)
        state["chunks"] = chunks
        print(f"Created {len(chunks)} chunks")
        
    except Exception as e:
        error_msg = f"Error in chunk_documents: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        state["error"] = error_msg
    
    return state

def create_vectorstore(state: RAGState) -> RAGState:
    """Create vector store from chunks"""
    print("Creating vector store...")
    
    try:
        chunks = state.get("chunks", [])
        if not chunks:
            error_msg = "No chunks found to create vectorstore"
            print(error_msg)
            state["error"] = error_msg
            return state
        
        print(f"Creating vectorstore from {len(chunks)} chunks...")
        
        # Create vectorstore
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embedding_model,
            collection_name=COLLECTION_NAME,
            persist_directory=PERSIST_DIRECTORY
        )
        
        # Explicitly set in state
        state["vectorstore"] = vectorstore
        print(f"✅ Vector store created successfully with {len(chunks)} embeddings")
        print(f"✅ Vectorstore added to state: {vectorstore is not None}")
        
        # Verify it's actually in the state
        if "vectorstore" not in state:
            error_msg = "Failed to add vectorstore to state"
            print(error_msg)
            state["error"] = error_msg
        
    except Exception as e:
        error_msg = f"Error in create_vectorstore: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        state["error"] = error_msg
    
    return state

def retrieve_context(state: RAGState) -> RAGState:
    """Retrieve relevant context for the question"""
    print("Retrieving context...")
    
    try:
        # Check if vectorstore exists
        if "vectorstore" not in state:
            error_msg = "Vectorstore not found in state. Available keys: " + str(list(state.keys()))
            print(error_msg)
            state["error"] = error_msg
            return state
        
        question = state.get("question", "")
        if not question:
            error_msg = "No question provided"
            print(error_msg)
            state["error"] = error_msg
            return state
        
        vectorstore = state["vectorstore"]
        if vectorstore is None:
            error_msg = "Vectorstore is None"
            print(error_msg)
            state["error"] = error_msg
            return state
        
        print(f"Retrieving context for question: {question}")
        
        retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
        docs = retriever.invoke(question)
        
        context = "\n\n".join([d.page_content for d in docs])
        state["context"] = context
        print(f"✅ Retrieved {len(docs)} relevant documents")
        
    except Exception as e:
        error_msg = f"Error in retrieve_context: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        state["error"] = error_msg
    
    return state

def generate_answer(state: RAGState) -> RAGState:
    """Generate answer using LLM"""
    print("Generating answer...")
    
    try:
        # Check for errors first
        if state.get("error"):
            print(f"Previous error detected: {state['error']}")
            state["answer"] = f"Error occurred during processing: {state['error']}"
            return state
        
        question = state.get("question", "")
        context = state.get("context", "")
        
        if not context:
            error_msg = "No context available to generate answer"
            print(error_msg)
            state["error"] = error_msg
            state["answer"] = error_msg
            return state
        
        # Create chain
        chain = prompt | llm | StrOutputParser()
        
        # Generate response
        response = chain.invoke({"context": context, "question": question})
        state["answer"] = response
        print("✅ Answer generated successfully")
        
    except Exception as e:
        error_msg = f"Error in generate_answer: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        state["error"] = error_msg
        state["answer"] = error_msg
    
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

# # Usage example
# if __name__ == "__main__":
#     # Initialize state with all required keys
#     initial_state = {
#         "question": "How do you grow tomatoes successfully?",  # Changed to match your URLs
#         "documents": [],
#         "chunks": [],
#         "context": "",
#         "answer": "",
#         "error": "",
#         "vectorstore": None  # Initialize explicitly
#     }
    
#     # Run the graph
#     print("Starting RAG pipeline...")
#     print("="*50)
    
#     try:
#         result = app.invoke(initial_state)
        
#         print("\n" + "="*50)
#         print("PIPELINE RESULTS:")
#         print("="*50)
        
#         if result.get("error"):
#             print(f"❌ ERROR: {result['error']}")
#         else:
#             print("✅ Pipeline completed successfully!")
        
#         print(f"\nDocuments loaded: {len(result.get('documents', []))}")
#         print(f"Chunks created: {len(result.get('chunks', []))}")
#         print(f"Vectorstore created: {'vectorstore' in result and result['vectorstore'] is not None}")
#         print(f"Context retrieved: {bool(result.get('context'))}")
        
#         print("\n" + "="*50)
#         print("FINAL ANSWER:")
#         print("="*50)
#         print(result.get("answer", "No answer generated"))
        
#     except Exception as e:
#         print(f"❌ Pipeline failed with error: {str(e)}")
#         print(f"Traceback: {traceback.format_exc()}")