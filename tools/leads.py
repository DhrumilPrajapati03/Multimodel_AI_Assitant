"""Enquiries / enrollment requests the assistant collects for the front desk."""
import re

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import text

from tools.db import engine

STATUSES = ("new", "contacted", "closed")


def normalize_phone(phone: str):
    """Digits with an optional leading +, or None if it isn't a plausible phone number."""
    phone = (phone or "").strip()
    digits = re.sub(r"\D", "", phone)
    if not 10 <= len(digits) <= 13:
        return None
    return ("+" if phone.startswith("+") else "") + digits


@tool
def save_enquiry(name: str, phone: str, course: str = "", email: str = "", message: str = "",
                 config: RunnableConfig = None) -> str:
    """Save an enquiry so the academy's front desk can call the student back - for enrolling,
    joining a batch, booking a demo class or talking to a counsellor.
    Only call this after the user has told you their name and phone number in this conversation.
    Never make up contact details."""
    name = (name or "").strip()
    number = normalize_phone(phone)
    if len(name) < 2:
        return "Not saved: ask the user for their name."
    if not number:
        return "Not saved: the phone number looks invalid. Ask the user to repeat it (10-13 digits)."
    session_id = ((config or {}).get("configurable") or {}).get("session_id")
    course = (course or "").strip()[:100] or None
    with engine.begin() as conn:
        # Same person asking again (or repeating details mid-chat): update, don't duplicate.
        existing = conn.execute(
            text("""SELECT id FROM leads WHERE phone = :p AND course IS NOT DISTINCT FROM :c
                    AND created_at > now() - interval '1 day' ORDER BY id DESC LIMIT 1"""),
            {"p": number, "c": course}).scalar()
        if existing:
            conn.execute(text("""UPDATE leads SET name = :n, email = coalesce(:e, email),
                                  message = coalesce(:m, message), status = 'new' WHERE id = :id"""),
                         {"n": name[:100], "e": (email or "").strip()[:200] or None,
                          "m": (message or "").strip()[:500] or None, "id": existing})
            return f"Already saved - updated. The front desk will contact {name} at {number}."
        conn.execute(
            text("""INSERT INTO leads (session_id, name, phone, email, course, message)
                    VALUES (:s, :n, :p, :e, :c, :m)"""),
            {"s": session_id, "n": name[:100], "p": number, "e": (email or "").strip()[:200] or None,
             "c": course, "m": (message or "").strip()[:500] or None},
        )
    return f"Saved. The front desk will contact {name} at {number}."


def list_leads(limit=200):
    with engine.connect() as conn:
        rows = conn.execute(text("""SELECT id, name, phone, email, course, message, status, created_at
                                    FROM leads ORDER BY created_at DESC LIMIT :l"""),
                            {"l": limit}).mappings().all()
    return [dict(r) for r in rows]


def set_lead_status(lead_id: int, status: str) -> bool:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    with engine.begin() as conn:
        return conn.execute(text("UPDATE leads SET status = :s WHERE id = :id"),
                            {"s": status, "id": lead_id}).rowcount > 0
