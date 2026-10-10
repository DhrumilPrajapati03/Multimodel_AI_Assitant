"""Admin API for the /admin dashboard: usage stats, leads and the document library.
Every endpoint needs the X-Admin-Token header to match the ADMIN_TOKEN setting."""
import secrets

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from config import ADMIN_TOKEN
from tools import docstore
from tools.db import engine
from tools.leads import list_leads, set_lead_status


def require_admin(x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN:
        raise HTTPException(503, "Admin is disabled. Set the ADMIN_TOKEN environment variable to enable it.")
    if not secrets.compare_digest(x_admin_token.encode(), ADMIN_TOKEN.encode()):
        raise HTTPException(401, "Wrong admin token.")


router = APIRouter(prefix="/admin/api", dependencies=[Depends(require_admin)])

# Replies that suggest the assistant couldn't answer - tells staff which documents to add.
UNANSWERED = """(a ILIKE '%don''t know%' OR a ILIKE '%do not know%' OR a ILIKE '%not sure%'
                 OR a ILIKE '%don''t have that%' OR a ILIKE '%don''t have any%' OR a ILIKE '%not aware%'
                 OR a ILIKE '%having trouble%' OR a ILIKE '%couldn''t find%' OR a ILIKE '%no information%')"""


@router.get("/stats")
def stats():
    with engine.connect() as conn:
        def one(sql):
            return conn.execute(text(sql)).mappings().one()

        def many(sql):
            return [dict(r) for r in conn.execute(text(sql)).mappings().all()]

        totals = one("""SELECT count(DISTINCT session_id) AS conversations,
                               count(*) FILTER (WHERE role = 'user') AS questions,
                               count(*) FILTER (WHERE role = 'user' AND channel = 'voice') AS voice,
                               count(*) FILTER (WHERE role = 'user' AND image_note IS NOT NULL) AS images,
                               count(DISTINCT session_id) FILTER (WHERE created_at > now() - interval '7 days') AS conversations_7d
                        FROM chat_history""")
        lead_totals = one("SELECT count(*) AS total, count(*) FILTER (WHERE status = 'new') AS new FROM leads")
        return {
            "totals": {**dict(totals), "leads": lead_totals["total"], "new_leads": lead_totals["new"]},
            "daily": many("""SELECT to_char(day, 'YYYY-MM-DD') AS day, count(h.id) AS questions
                             FROM generate_series(current_date - 13, current_date, interval '1 day') AS day
                             LEFT JOIN chat_history h ON h.role = 'user' AND h.created_at::date = day::date
                             GROUP BY day ORDER BY day"""),
            "intents": many("""SELECT coalesce(intent, 'other') AS intent, count(*) AS n FROM chat_history
                               WHERE role = 'user' GROUP BY 1 ORDER BY n DESC"""),
            "languages": many("""SELECT language, count(*) AS n FROM chat_history
                                 WHERE role = 'user' AND language IS NOT NULL GROUP BY 1 ORDER BY n DESC"""),
            "top_questions": many("""SELECT lower(trim(message)) AS question, count(*) AS n FROM chat_history
                                     WHERE role = 'user' AND message <> '(sent an image)'
                                     GROUP BY 1 ORDER BY n DESC, max(created_at) DESC LIMIT 10"""),
            "unanswered": many(f"""SELECT q AS question, a AS answer, created_at FROM (
                                       SELECT role, message AS a, created_at,
                                              lag(message) OVER (PARTITION BY session_id ORDER BY created_at, id) AS q
                                       FROM chat_history) t
                                   WHERE role = 'assistant' AND q IS NOT NULL AND {UNANSWERED}
                                   ORDER BY created_at DESC LIMIT 20"""),
        }


@router.get("/leads")
def leads():
    return list_leads()


class LeadUpdate(BaseModel):
    status: str


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, body: LeadUpdate):
    try:
        found = set_lead_status(lead_id, body.status)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not found:
        raise HTTPException(404, "Lead not found.")
    return {"ok": True}


@router.get("/documents")
def documents():
    return docstore.list_documents()


@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    data = await file.read(docstore.MAX_UPLOAD_BYTES + 1)
    try:
        doc_id = docstore.add_document(file.filename or "upload", data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": doc_id, "status": "processing"}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    if not docstore.delete_document(doc_id):
        raise HTTPException(404, "Document not found.")
    return {"ok": True}
