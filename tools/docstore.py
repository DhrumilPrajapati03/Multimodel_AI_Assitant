"""Knowledge base kept in Postgres: documents, text chunks and their embeddings.

Vectors are stored as raw float32 bytes (works on any Postgres, no pgvector needed) and
searched in memory with numpy - a few thousand chunks is only a few MB. Everything
persists in the database, so uploads survive restarts and redeploys on free hosting.
"""
import io
import logging
import threading
from pathlib import Path

import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import text

from tools.db import engine
from tools.embeddings import DIM, embed

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10_000_000
MAX_PDF_PAGES = 300
MAX_CHUNKS = 2000
KINDS = {".pdf": "pdf", ".txt": "text", ".md": "text",
         ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image"}
IMAGE_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
_lock = threading.Lock()
_cache = {"key": None, "matrix": np.zeros((0, DIM), np.float32), "rows": []}


# ---------- reading files ----------

def kind_for(filename: str):
    return KINDS.get(Path(filename).suffix.lower())


def extract_pages(filename: str, data: bytes):
    """[(page_number, text)] for a PDF, text file or image."""
    kind = kind_for(filename)
    if kind == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF has {len(reader.pages)} pages; the limit is {MAX_PDF_PAGES}.")
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    if kind == "text":
        return [(1, data.decode("utf-8", errors="replace"))]
    if kind == "image":
        from tools.vision import transcribe_document
        return [(1, transcribe_document(data, IMAGE_MIME[Path(filename).suffix.lower()]))]
    raise ValueError("Unsupported file type - use PDF, TXT, MD, JPG, PNG or WebP.")


def chunk_pages(pages):
    chunks = []
    for page, page_text in pages:
        chunks += [(page, c) for c in _splitter.split_text(page_text) if c.strip()]
    return chunks


# ---------- writing ----------

def create_document(name: str, kind: str, source: str = "upload") -> int:
    with engine.begin() as conn:
        return conn.execute(
            text("INSERT INTO documents (name, kind, source) VALUES (:n, :k, :s) RETURNING id"),
            {"n": name, "k": kind, "s": source},
        ).scalar()


def process_document(doc_id: int, filename: str, data: bytes):
    """Extract, chunk, embed and store a document; marks it ready or failed."""
    try:
        chunks = chunk_pages(extract_pages(filename, data))
        if not chunks:
            raise ValueError("No readable text found (is it a scanned PDF? Try uploading page photos instead).")
        if len(chunks) > MAX_CHUNKS:
            raise ValueError(f"Document is too long ({len(chunks)} chunks; the limit is {MAX_CHUNKS}).")
        vectors = embed([c for _, c in chunks])
        rows = [{"d": doc_id, "p": page, "c": content, "e": vec.astype(np.float32).tobytes()}
                for (page, content), vec in zip(chunks, vectors)]
        with engine.begin() as conn:
            for i in range(0, len(rows), 200):
                conn.execute(text("INSERT INTO doc_chunks (document_id, page, content, embedding) "
                                  "VALUES (:d, :p, :c, :e)"), rows[i:i + 200])
            conn.execute(text("UPDATE documents SET status = 'ready', chunks = :n, error = NULL WHERE id = :id"),
                         {"n": len(rows), "id": doc_id})
        log.info("Indexed %s: %d chunks", filename, len(rows))
    except Exception as exc:
        log.exception("Indexing %s failed", filename)
        with engine.begin() as conn:
            conn.execute(text("UPDATE documents SET status = 'failed', error = :e WHERE id = :id"),
                         {"e": str(exc)[:500], "id": doc_id})


def add_document(filename: str, data: bytes, source: str = "upload", background: bool = True) -> int:
    kind = kind_for(filename)
    if not kind:
        raise ValueError("Unsupported file type - use PDF, TXT, MD, JPG, PNG or WebP.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("File is larger than 10 MB.")
    doc_id = create_document(Path(filename).name, kind, source)
    if background:
        threading.Thread(target=process_document, args=(doc_id, filename, data), daemon=True).start()
    else:
        process_document(doc_id, filename, data)
    return doc_id


def delete_document(doc_id: int) -> bool:
    with engine.begin() as conn:
        return conn.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_id}).rowcount > 0


def list_documents():
    with engine.connect() as conn:
        rows = conn.execute(text("""SELECT id, name, kind, source, status, chunks, error, created_at
                                    FROM documents ORDER BY created_at DESC""")).mappings().all()
    return [dict(r) for r in rows]


def recover_interrupted():
    """Documents left 'processing' by a restart will never finish - mark them failed."""
    with engine.begin() as conn:
        conn.execute(text("""UPDATE documents SET status = 'failed',
                             error = 'Interrupted by a server restart - please upload it again.'
                             WHERE status = 'processing'"""))


def seed_from_folder(folder="data"):
    """Index the bundled PDFs in data/ that aren't in the knowledge base yet (runs once)."""
    with engine.connect() as conn:
        ready = set(conn.execute(text(
            "SELECT name FROM documents WHERE source = 'seed' AND status = 'ready'")).scalars())
    added = 0
    for pdf in sorted(Path(folder).glob("*.pdf")):
        if pdf.name in ready:
            continue
        with engine.begin() as conn:   # clear earlier failed attempts for this file
            conn.execute(text("DELETE FROM documents WHERE source = 'seed' AND name = :n"), {"n": pdf.name})
        add_document(pdf.name, pdf.read_bytes(), source="seed", background=False)
        added += 1
    return added


# ---------- searching ----------

def _load_index():
    with engine.connect() as conn:
        key = tuple(conn.execute(text("""
            SELECT count(*), coalesce(max(c.id), 0) FROM doc_chunks c
            JOIN documents d ON d.id = c.document_id WHERE d.status = 'ready'""")).one())
        if key == _cache["key"]:
            return _cache
        rows = conn.execute(text("""
            SELECT c.content, c.page, c.embedding, d.name FROM doc_chunks c
            JOIN documents d ON d.id = c.document_id WHERE d.status = 'ready'
            ORDER BY c.id""")).mappings().all()
    matrix = np.frombuffer(b"".join(bytes(r["embedding"]) for r in rows), dtype=np.float32).reshape(-1, DIM)
    _cache.update(key=key, matrix=matrix,
                  rows=[{"content": r["content"], "page": r["page"], "name": r["name"]} for r in rows])
    return _cache


def search(query: str, k: int = 4):
    """Top-k chunks by cosine similarity: [{content, page, name, score}]."""
    with _lock:
        index = _load_index()
        if not index["rows"]:
            return []
        scores = index["matrix"] @ embed([query])[0]
        top = np.argsort(-scores)[:k]
        return [{**index["rows"][i], "score": float(scores[i])} for i in top]
