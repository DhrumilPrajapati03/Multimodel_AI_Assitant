import uuid
import wave
from pathlib import Path
import tools.onnx_threads  # noqa: F401  (must run before the model loads)
from piper import PiperVoice

VOICE_PATH = "models/voices/en_US-lessac-medium.onnx"
OUT_DIR = Path("audio_out")
OUT_DIR.mkdir(exist_ok=True)

_voice = None


def synthesize(text: str) -> str:
    global _voice
    if _voice is None:
        _voice = PiperVoice.load(VOICE_PATH)
    path = OUT_DIR / f"{uuid.uuid4().hex}.wav"
    with wave.open(str(path), "wb") as wav:
        _voice.synthesize_wav(text, wav)
    return str(path)