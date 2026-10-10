import json
import logging
import shutil
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.admin import router as admin_router
from config import TTS_MODE
from app.pipeline import collect, run_turn
from tools.db import get_history
from tools.vision import MAX_IMAGE_BYTES

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

MAX_TEXT = 2000
MAX_AUDIO_BYTES = 15_000_000


def _background_start():
    """Index the bundled PDFs (first run only) and load everything the first question needs -
    on a 0.1-CPU free plan the embedding model, the intent model and the first Groq connection
    together take ~50 s, which would otherwise land on the first visitor."""
    from tools import docstore
    from tools.guard import attack_score
    from tools.intent import classify_intent
    try:
        docstore.recover_interrupted()
        added = docstore.seed_from_folder()
        if added:
            log.info("Indexed %d bundled PDF(s) into the knowledge base", added)
        docstore.search("warm up", k=1)
        classify_intent("hello")
        attack_score("hello")
        log.info("Warm-up finished - ready for questions")
    except Exception:
        log.exception("Background start-up work failed")


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_background_start, daemon=True).start()
    yield


app = FastAPI(title="Academy Assistant API", lifespan=lifespan)
app.mount("/audio", StaticFiles(directory="audio_out"), name="audio")
app.include_router(admin_router)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/config")
def client_config():
    """Tells the page how replies are spoken, so it can start talking while the answer streams."""
    return {"tts_mode": TTS_MODE}


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


async def _read_inputs(audio: UploadFile, image: UploadFile):
    """Save audio to a temp file and read image bytes. Uploads are closed once the
    endpoint returns, so this must happen before streaming starts."""
    audio_path, image_data = None, None
    if image is not None and image.filename:
        data = await image.read(MAX_IMAGE_BYTES + 1)
        image_data = (data, image.content_type or "")
    if audio is not None and audio.filename:
        suffix = Path(audio.filename).suffix or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(audio.file, tmp, length=1024 * 1024)
        if Path(tmp.name).stat().st_size > MAX_AUDIO_BYTES:
            Path(tmp.name).unlink(missing_ok=True)
            raise HTTPException(413, "Recording is too long.")
        audio_path = tmp.name
    return audio_path, image_data


@app.post("/ask")
async def ask(session_id: str = Form(..., max_length=64), text: str = Form("", max_length=MAX_TEXT),
              audio: UploadFile = File(None), image: UploadFile = File(None)):
    """One turn with any mix of text, voice and image. Streams Server-Sent Events:
    transcript, token, reset, rows, done, error (see app.pipeline.run_turn)."""
    audio_path, image_data = await _read_inputs(audio, image)

    def events():
        try:
            for event in run_turn(session_id, text, audio_path, image_data):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception:
            log.exception("Turn failed")
            yield 'data: {"type": "error", "message": "Something went wrong. Please try again."}\n\n'
        finally:
            if audio_path:
                Path(audio_path).unlink(missing_ok=True)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---- Simple, non-streaming endpoints (kept for API clients and scripts) ----

class ChatIn(BaseModel):
    text: str = Field(max_length=MAX_TEXT)
    session_id: str = Field(max_length=64)


class ChatOut(BaseModel):
    reply: str
    intent: str


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn):
    try:
        done, _, _ = collect(run_turn(body.session_id, body.text))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return ChatOut(reply=done["reply"], intent=done["intent"])


@app.post("/voice")
async def voice(session_id: str = Form(..., max_length=64), audio: UploadFile = File(...),
                image: UploadFile = File(None)):
    audio_path, image_data = await _read_inputs(audio, image)
    try:   # the pipeline blocks on network calls - keep it off the event loop
        done, transcript, _ = await run_in_threadpool(
            lambda: collect(run_turn(session_id, "", audio_path, image_data)))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    finally:
        Path(audio_path).unlink(missing_ok=True)
    return {"transcript": transcript, "reply": done["reply"], "audio_url": done["audio_url"]}


@app.get("/history/{session_id}")
def history(session_id: str):
    return get_history(session_id)
