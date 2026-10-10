import os
import subprocess
import sys
from pathlib import Path

import uvicorn

# Run everything from the project folder, wherever start.py was launched from.
# The app uses relative paths (data/, models/, chroma_db/, audio_out/).
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Child processes need to import project packages (tools, config) too.
child_env = {**os.environ, "PYTHONPATH": os.pathsep.join(
    p for p in (str(PROJECT_ROOT), os.environ.get("PYTHONPATH")) if p)}

# 1. Download the Piper voice if missing
voice_dir = PROJECT_ROOT / "models" / "voices"
if not (voice_dir / "en_US-lessac-medium.onnx").exists():
    voice_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "piper.download_voices", "en_US-lessac-medium"],
                   cwd=voice_dir, check=True)

# 2. Build the vector index if missing.
# Run ingest.py by file path, not "-m scripts.ingest": a module named "scripts"/"Scripts"
# clashes with Python's own Scripts folders on Windows, and the import is case-sensitive.
if not (PROJECT_ROOT / "chroma_db").exists():
    ingest = PROJECT_ROOT / "scripts" / "ingest.py"
    if not ingest.exists():
        sys.exit(f"Missing {ingest} - the vector index can't be built without it.")
    subprocess.run([sys.executable, str(ingest)], cwd=PROJECT_ROOT, env=child_env, check=True)

# 3. Create and seed the database tables if this is a fresh database
import time

from tools.db import init_db

# Retry: hosted databases (e.g. Neon's free tier) may need a moment to wake up.
for attempt in range(1, 6):
    try:
        if init_db():
            print("Database was empty - created tables from db/schema.sql and db/seed.sql")
        break
    except Exception as exc:
        if attempt == 5:
            raise
        print(f"Database not reachable yet ({type(exc).__name__}), retrying in 3s... [{attempt}/5]")
        time.sleep(3)

# 4. Start the app
from app.main import app

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 7860))
    print(f"\n  Open the assistant at: http://localhost:{port}\n")
    uvicorn.run(app, host=host, port=port)
