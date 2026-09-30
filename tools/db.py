from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def save_message(session_id, role, message, intent=None, channel="text"):
    with engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO chat_history (session_id, role, message, intent, channel)
                    VALUES (:s, :r, :m, :i, :c)"""),
            {"s": session_id, "r": role, "m": message, "i": intent, "c": channel},
        )


def get_history(session_id, limit=50):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""SELECT role, message, intent, channel, created_at
                    FROM chat_history WHERE session_id = :s
                    ORDER BY created_at LIMIT :l"""),
            {"s": session_id, "l": limit},
        ).mappings().all()
    return [dict(r) for r in rows]