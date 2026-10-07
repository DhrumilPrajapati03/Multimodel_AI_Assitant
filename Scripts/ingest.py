import sys
from pathlib import Path

# Check for PDFs before importing tools.rag: creating the store makes an empty chroma_db/,
# which start.py would then treat as an existing index and never rebuild.
pdfs = list(Path("data").glob("*.pdf"))
if not pdfs:
    sys.exit(f"No PDFs found in {Path('data').resolve()} - add the academy PDFs there and run again.")

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tools.rag import store

docs = []
for pdf in pdfs:
    docs.extend(PyPDFLoader(str(pdf)).load())

splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
chunks = splitter.split_documents(docs)
if not chunks:
    sys.exit("The PDFs contain no extractable text (scanned images?) - nothing to index.")
store.add_documents(chunks)
print(f"Indexed {len(chunks)} chunks from {len(pdfs)} PDFs")