"""Piper text-to-speech on the server (TTS_MODE=piper)."""
import wave

import tools.onnx_threads  # noqa: F401  (must run before the model loads)
from piper import PiperVoice

from tools.audio_out import new_wav_path

VOICE_PATH = "models/voices/en_US-lessac-medium.onnx"

_voice = None


def synthesize(text: str) -> str:
    global _voice
    if _voice is None:
        _voice = PiperVoice.load(VOICE_PATH)
    path = new_wav_path()
    with wave.open(str(path), "wb") as wav:
        _voice.synthesize_wav(text, wav)
    return str(path)
