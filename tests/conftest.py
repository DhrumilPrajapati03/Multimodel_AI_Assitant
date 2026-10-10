import os
import sys
from pathlib import Path

# Make the project importable and let modules load without real credentials.
# These tests never connect to the database or call Groq.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("GROQ_API_KEY", "test-key")
