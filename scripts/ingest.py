"""Index the PDFs in data/ into the knowledge base (Postgres).

The app does this automatically on start-up; run it by hand after adding PDFs to data/:
    python scripts/ingest.py
Files that are already indexed are skipped. Staff can also upload documents at /admin.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

pdfs = list((ROOT / "data").glob("*.pdf"))
if not pdfs:
    sys.exit(f"No PDFs found in {ROOT / 'data'} - add the academy PDFs there and run again.")

from tools import docstore  # noqa: E402
from tools.db import init_db  # noqa: E402

init_db()
added = docstore.seed_from_folder(ROOT / "data")
for doc in docstore.list_documents():
    if doc["source"] == "seed":
        print(f"  {doc['status']:10s} {doc['chunks']:4d} chunks  {doc['name']}"
              + (f"  ({doc['error']})" if doc["error"] else ""))
print(f"Indexed {added} new PDF(s); {len(pdfs) - added} already in the knowledge base.")
