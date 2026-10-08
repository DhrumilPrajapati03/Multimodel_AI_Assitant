import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_NAME = "openai/gpt-oss-20b"

# Hosts like Render, Neon and Railway give "postgres://" or "postgresql://" URLs;
# SQLAlchemy needs the driver named explicitly.
if DATABASE_URL:
    for prefix in ("postgres://", "postgresql://"):
        if DATABASE_URL.startswith(prefix):
            DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(prefix):]
            break
