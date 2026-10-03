from faster_whisper import WhisperModel

_model = None


def transcribe(audio_path: str) -> str:
    global _model
    if _model is None:
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = _model.transcribe(audio_path, vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()