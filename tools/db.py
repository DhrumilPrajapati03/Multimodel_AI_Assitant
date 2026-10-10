import json
from pathlib import Path

from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    # Hosted databases (e.g. Neon's free tier) suspend after ~5 idle minutes and drop
    # connections silently. Recycle pooled connections before that, and fail fast on a
    # dead connection instead of waiting ~15 min for Linux's default TCP timeout.
    pool_recycle=240,
    connect_args={
        "connect_timeout": 15,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "tcp_user_timeout": 30000,   # ms
    },
)

SQL_DIR = Path(__file__).resolve().parent.parent / "db"


def init_db():
    """Bring the schema up to date (idempotent) and seed courses on a fresh database.
    Returns True when the seed data was inserted."""
    with engine.begin() as conn:
        conn.exec_driver_sql((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        if conn.execute(text("SELECT count(*) FROM courses")).scalar():
            return False
        conn.exec_driver_sql((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))
    return True


READER_ROLE = "academy_reader"


def setup_reader_role() -> bool:
    """A login-less role that can only read courses and batches. The assistant's SQL tool
    switches to it, so even a tricked model can't read leads or other users' chats.
    Best effort: needs CREATEROLE (Neon's owner role has it)."""
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"""
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{READER_ROLE}') THEN
                        CREATE ROLE {READER_ROLE} NOLOGIN;
                    END IF;
                END $$;
                GRANT USAGE ON SCHEMA public TO {READER_ROLE};
                GRANT SELECT ON courses, batches TO {READER_ROLE};
                GRANT {READER_ROLE} TO CURRENT_USER;""")
        return True
    except Exception as exc:
        print(f"Note: couldn't set up the read-only '{READER_ROLE}' role ({type(exc).__name__}); "
              "the SQL tool falls back to a table blocklist.")
        return False


def save_message(session_id, role, message, intent=None, channel="text",
                 image_note=None, language=None, data=None):
    with engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO chat_history
                        (session_id, role, message, intent, channel, image_note, language, data)
                    VALUES (:s, :r, :m, :i, :c, :n, :l, CAST(:d AS JSONB))"""),
            {"s": session_id, "r": role, "m": message, "i": intent, "c": channel,
             "n": image_note, "l": language,
             "d": json.dumps(data, default=str) if data is not None else None},
        )


def get_history(session_id, limit=50):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""SELECT role, message, intent, channel, created_at, data,
                           image_note IS NOT NULL AS has_image
                    FROM chat_history WHERE session_id = :s
                    ORDER BY created_at LIMIT :l"""),
            {"s": session_id, "l": limit},
        ).mappings().all()
    return [dict(r) for r in rows]


def recent_messages(session_id, limit=12):
    """The last `limit` messages of a conversation, oldest first - the agent's memory.
    Kept in Postgres, so it survives restarts (free hosting plans sleep and restart often)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""SELECT role, message, image_note FROM chat_history
                    WHERE session_id = :s ORDER BY created_at DESC, id DESC LIMIT :l"""),
            {"s": session_id, "l": limit},
        ).mappings().all()
    return [dict(r) for r in reversed(rows)]
