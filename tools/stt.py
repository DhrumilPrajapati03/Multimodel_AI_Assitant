from pathlib import Path

from config import STT_MODEL
from tools.groq_client import client


def transcribe(audio_path: str):
    """Speech-to-text on Groq's hosted Whisper. Returns (text, language), where
    language is the name Whisper detected, e.g. "English" or "Hindi"."""
    path = Path(audio_path)
    result = client().audio.transcriptions.create(
        file=(path.name, path.read_bytes()),
        model=STT_MODEL,
        response_format="verbose_json",
    )
    language = (getattr(result, "language", None) or "").strip().title() or None
    return result.text.strip(), language
