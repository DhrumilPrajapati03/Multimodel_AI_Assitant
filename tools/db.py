def save_message(session_id: str, role: str, message: str,
                 intent: str | None = None, channel: str = "text") -> None:
    raise NotImplementedError

def get_history(session_id: str, limit: int = 50) -> list[dict]:
    raise NotImplementedError