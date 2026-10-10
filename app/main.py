import shutil
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.pipeline import handle_text, handle_voice
from tools.db import get_history

def _warm_up():
    # Load the embedding model in the background so the first document question
    # doesn't pay for it (that takes ~40 s on a 0.1-CPU free plan).
    from tools.rag import store
    store.similarity_search("warm up", k=1)


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(title="Academy Assistant API", lifespan=lifespan)
app.mount("/audio", StaticFiles(directory="audio_out"), name="audio")


class ChatIn(BaseModel):
    text: str
    session_id: str


class ChatOut(BaseModel):
    reply: str
    intent: str


STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn):
    reply, intent = handle_text(body.text, body.session_id)
    return ChatOut(reply=reply, intent=intent)


@app.post("/voice")
def voice(session_id: str = Form(...), audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(audio.file, tmp)
    try:
        transcript, reply, audio_path = handle_voice(tmp.name, session_id)
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    return {
        "transcript": transcript,
        "reply": reply,
        "audio_url": f"/audio/{Path(audio_path).name}" if audio_path else None,
    }


@app.get("/history/{session_id}")
def history(session_id: str):
    return get_history(session_id)
