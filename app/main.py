import shutil
import tempfile
from pathlib import Path

import gradio as gr
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.pipeline import handle_text, handle_voice
from app.ui import demo
from tools.db import get_history

app = FastAPI(title="Academy Assistant API")
app.mount("/audio", StaticFiles(directory="audio_out"), name="audio")


class ChatIn(BaseModel):
    text: str
    session_id: str


class ChatOut(BaseModel):
    reply: str
    intent: str


@app.get("/")
def root():
    return RedirectResponse("/ui")


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn):
    reply, intent = handle_text(body.text, body.session_id)
    return ChatOut(reply=reply, intent=intent)


@app.post("/voice")
def voice(session_id: str = Form(...), audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(audio.file, tmp)
    transcript, reply, audio_path = handle_voice(tmp.name, session_id)
    return {
        "transcript": transcript,
        "reply": reply,
        "audio_url": f"/audio/{Path(audio_path).name}",
    }


@app.get("/history/{session_id}")
def history(session_id: str):
    return get_history(session_id)


app = gr.mount_gradio_app(app, demo, path="/ui")