import os
import subprocess
import sys
import time
from pathlib import Path

import uvicorn

# Run everything from the project folder, wherever start.py was launched from.
# The app uses relative paths (data/, models/, audio_out/).
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import TTS_MODE

# 1. Download the Piper voice if it's used and missing
voice_dir = PROJECT_ROOT / "models" / "voices"
if TTS_MODE == "piper" and not (voice_dir / "en_US-lessac-medium.onnx").exists():
    voice_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "piper.download_voices", "en_US-lessac-medium"],
                   cwd=voice_dir, check=True)

# 2. Bring the database schema up to date (creates and seeds tables on a fresh database).
# The bundled PDFs are indexed into it in the background once the server is up.
from tools.db import init_db, setup_reader_role

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
setup_reader_role()

# 3. Start the app
from app.main import app

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 7860))
    print(f"\n  Open the assistant at: http://localhost:{port}"
          f"\n  Admin dashboard:       http://localhost:{port}/admin\n")
    uvicorn.run(app, host=host, port=port)
