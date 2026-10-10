import json
import re

from langchain_core.tools import tool
from sqlalchemy import text
from tools.db import READER_ROLE, engine

# Defence in depth on top of the read-only role: never touch private tables or system catalogs.
BLOCKED = re.compile(
    r"\b(leads|chat_history|documents|doc_chunks|pg_\w+|information_schema|"
    r"query_to_xml\w*|dblink\w*|lo_\w+|copy|set_config|current_setting)\b",
    re.IGNORECASE,
)

_reader_ok = None


def _reader_available(conn) -> bool:
    global _reader_ok
    if _reader_ok is None:
        _reader_ok = bool(conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :r) "
            "AND pg_has_role(current_user, :r, 'MEMBER')"), {"r": READER_ROLE}).scalar())
    return _reader_ok


@tool
def query_academy_db(sql: str) -> str:
    """Run a read-only SQL SELECT query on the academy PostgreSQL database.
    Tables:
      courses(id, name, duration_weeks, fee_inr, description)
      batches(id, course_id -> courses.id, start_date, timing, seats_left)
    Use this for fees, course durations, batch timings, start dates and seats.
    Select readable columns (e.g. course name, not just ids). Returns JSON rows."""
    cleaned = sql.strip().rstrip(";")
    if not cleaned.lower().startswith(("select", "with")) or ";" in cleaned:
        return "Error: only a single SELECT query is allowed."
    if BLOCKED.search(cleaned):
        return "Error: only the courses and batches tables can be queried."
    try:
        with engine.connect() as conn:
            reader = _reader_available(conn)
            conn.rollback()
            with conn.begin():
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
                if reader:
                    conn.exec_driver_sql(f"SET LOCAL ROLE {READER_ROLE}")
                rows = conn.execute(text(cleaned)).mappings().all()
    except Exception as e:
        return f"SQL error: {str(e).splitlines()[0][:300]}"
    if not rows:
        return "No rows found."
    return json.dumps([dict(r) for r in rows[:20]], default=str)
