from pathlib import Path

from groq import Groq

from config import GROQ_API_KEY

# Groq's hosted Whisper: no local model, so it fits small free-tier servers.
STT_MODEL = "whisper-large-v3-turbo"

_client = None


def transcribe(audio_path: str) -> str:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY, timeout=30, max_retries=2)
    path = Path(audio_path)
    result = _client.audio.transcriptions.create(
        file=(path.name, path.read_bytes()),
        model=STT_MODEL,
    )
    return result.text.strip()
