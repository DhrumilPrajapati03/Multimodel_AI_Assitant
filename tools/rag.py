from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.tools import tool

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
store = Chroma(
    collection_name="academy",
    embedding_function=embeddings,
    persist_directory="chroma_db",
)


@tool
def search_academy_docs(query: str) -> str:
    """Search the academy documents: syllabus, policies, FAQs.
    Use this for course content, topics covered, rules and general academy info."""
    docs = store.similarity_search(query, k=4)
    if not docs:
        return "Nothing relevant found in the documents."
    return "\n\n".join(d.page_content for d in docs)