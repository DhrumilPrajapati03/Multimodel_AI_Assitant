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
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 7860))
    print(f"\n  Open the assistant at: http://localhost:{port}\n")
    uvicorn.run(app, host=host, port=port)