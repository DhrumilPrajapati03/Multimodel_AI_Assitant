import time
import uuid
from pathlib import Path

OUT_DIR = Path("audio_out")
OUT_DIR.mkdir(exist_ok=True)
KEEP_SECONDS = 30 * 60


def new_wav_path() -> Path:
    """A fresh file for a spoken reply. Replies older than 30 minutes are deleted
    so a long-running server never fills its disk."""
    cutoff = time.time() - KEEP_SECONDS
    for old in OUT_DIR.glob("*.wav"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass
    return OUT_DIR / f"{uuid.uuid4().hex}.wav"
