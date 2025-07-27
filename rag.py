
from langchain_community.vectorstores import Chroma

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from langchain_community.document_loaders import WebBaseLoader

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from core.llm_manager import LLMManager, LLMProvider



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

documents = []

for url in list(URLS_DICTIONARY.values()):
    loader = WebBaseLoader(url)
    data = loader.load()
    documents += data

documents[0].page_content

for doc in documents:
    doc.page_content = " ".join(doc.page_content.split())

documents[0].page_content
# print(documents[0].page_content)



text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=0)
docs = text_splitter.split_documents(documents)

print("**" * 50)
for doc in docs:
    print("*" * 50)
    print(doc)

embedding_model = HuggingFaceEmbeddings(
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
)
PERSIST_DIRECTORY = "./chroma_db"
vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embedding_model,
    collection_name=COLLECTION_NAME,
    persist_directory=PERSIST_DIRECTORY
)

# vectorstore.persist()
print(f"vector store created with {len(docs)} emmbeddings")


retriever = vectorstore.as_retriever(search_kwargs={"k":4})


template = """Generate a summary of the context that answers the question. Explain the answer in multiple steps if possible.
answer style should match the context. Ideal answer leng 2-3 sentences.\n\n {context}\n Question:{question}\nAnswer:
"""

prompt = ChatPromptTemplate.from_template(template)


def format_docs(docs):
    return "\n\n".join([d.page_content for d in docs])

llm = manager.get_chat_model(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-haiku-20240307",
    temperature=0.7,
    max_tokens=1500
)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    |llm
    |StrOutputParser()
)


response = rag_chain.invoke("Tell me about the UFC announcement from November 14, 2024")

print(response)
