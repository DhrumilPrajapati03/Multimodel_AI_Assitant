from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tools.rag import store

pdfs = list(Path("data").glob("*.pdf"))
docs = []
for pdf in pdfs:
    docs.extend(PyPDFLoader(str(pdf)).load())

splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
chunks = splitter.split_documents(docs)
store.add_documents(chunks)
print(f"Indexed {len(chunks)} chunks from {len(pdfs)} PDFs")