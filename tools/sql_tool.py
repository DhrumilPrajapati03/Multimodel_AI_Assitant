from langchain_core.tools import tool
from sqlalchemy import text
from tools.db import engine


@tool
def query_academy_db(sql: str) -> str:
    """Run a read-only SQL SELECT query on the academy PostgreSQL database.
    Tables:
      courses(id, name, duration_weeks, fee_inr, description)
      batches(id, course_id -> courses.id, start_date, timing, seats_left)
    Use this for fees, course durations, batch timings, start dates and seats."""
    cleaned = sql.strip().rstrip(";")
    if not cleaned.lower().startswith("select") or ";" in cleaned:
        return "Error: only a single SELECT query is allowed."
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(cleaned)).mappings().all()
    except Exception as e:
        return f"SQL error: {e}"
    if not rows:
        return "No rows found."
    return str([dict(r) for r in rows[:20]])