import os
import subprocess
import sys
from pathlib import Path

import uvicorn

# 1. Download the Piper voice if missing
voice_dir = Path("models/voices")
if not (voice_dir / "en_US-lessac-medium.onnx").exists():
    voice_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "piper.download_voices", "en_US-lessac-medium"],
                   cwd=voice_dir, check=True)

# 2. Build the vector index if missing
if not Path("chroma_db").exists():
    subprocess.run([sys.executable, "-m", "scripts.ingest"], check=True)

# 3. Start the app
from app.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 7860)))