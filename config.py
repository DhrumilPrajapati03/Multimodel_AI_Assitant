import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# All models run on Groq, so the server stays small enough for free hosting plans.
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-20b")                 # chat agent
VISION_MODEL = os.getenv("VISION_MODEL", "qwen/qwen3.8-27b")               # image questions
STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3-turbo")               # speech-to-text
GUARD_MODEL = os.getenv("GUARD_MODEL", "meta-llama/llama-prompt-guard-2-86m")
GUARD_THRESHOLD = float(os.getenv("GUARD_THRESHOLD", "0.9"))  # prompt-attack score to block at

# How replies are spoken:
#   "piper"   - Piper voice on the server (default; "server" means the same)
#   "groq"    - Groq's Orpheus voice (accept its terms in the Groq console first)
#   "browser" - the browser speaks them; saves ~165 MB of RAM on small free plans
TTS_MODE = os.getenv("TTS_MODE", "piper").lower().replace("server", "piper")
TTS_MODEL = os.getenv("TTS_MODEL", "canopylabs/orpheus-v1-english")
TTS_VOICE = os.getenv("TTS_VOICE", "hannah")

# Protects the /admin dashboard. Leave unset to disable the admin API entirely.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Hosts like Render, Neon and Railway give "postgres://" or "postgresql://" URLs;
# SQLAlchemy needs the driver named explicitly.
if DATABASE_URL:
    for prefix in ("postgres://", "postgresql://"):
        if DATABASE_URL.startswith(prefix):
            DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(prefix):]
            break
