"""Groq-hosted text-to-speech (TTS_MODE=groq) - a natural voice with no model on the server.
The model's terms must be accepted once in the Groq console before it can be used."""
import io
import re
import wave

from config import TTS_MODEL, TTS_VOICE
from tools.audio_out import new_wav_path
from tools.groq_client import client

MAX_CHARS = 190   # stay under the model's per-request input limit


def _pieces(text: str):
    """Split into sentence-aligned pieces of at most MAX_CHARS."""
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        while len(sentence) > MAX_CHARS:   # an over-long sentence: cut at a space
            space = sentence.rfind(" ", 0, MAX_CHARS)
            cut = space if space > 0 else MAX_CHARS
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if current and len(current) + 1 + len(sentence) > MAX_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return [p for p in pieces if p]


def synthesize(text: str) -> str:
    path = new_wav_path()
    params, frames = None, []
    for piece in _pieces(text):
        audio = client().audio.speech.create(model=TTS_MODEL, voice=TTS_VOICE, input=piece,
                                             response_format="wav").read()
        with wave.open(io.BytesIO(audio)) as part:
            params = params or part.getparams()
            frames.append(part.readframes(part.getnframes()))
    with wave.open(str(path), "wb") as out:
        out.setparams(params)
        for f in frames:
            out.writeframes(f)
    return str(path)
