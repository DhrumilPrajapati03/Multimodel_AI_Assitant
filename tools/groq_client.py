from groq import Groq

from config import GROQ_API_KEY

_client = None


def client() -> Groq:
    """One shared Groq client; timeouts so a stuck connection can't hang a request."""
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY, timeout=30, max_retries=2)
    return _client
