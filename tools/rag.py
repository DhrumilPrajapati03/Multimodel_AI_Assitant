from pathlib import Path

import tools.onnx_threads  # noqa: F401  (must run before the model loads)
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool

# all-MiniLM-L6-v2 run with ONNX Runtime instead of PyTorch: same vectors,
# a fraction of the memory. The model is cached in models/embeddings/.
ONNXMiniLM_L6_V2.DOWNLOAD_PATH = Path(__file__).resolve().parent.parent / "models" / "embeddings"


class MiniLMEmbeddings(Embeddings):
    def __init__(self):
        self._embed = ONNXMiniLM_L6_V2()

    def embed_documents(self, texts):
        return [[float(x) for x in v] for v in self._embed(list(texts))]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


embeddings = MiniLMEmbeddings()
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
