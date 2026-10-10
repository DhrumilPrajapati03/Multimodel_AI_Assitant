"""One conversation turn - text, voice and/or image in; streamed events out."""
import logging
import re
from pathlib import Path

from config import TTS_MODE
from tools.agent import stream_agent
from tools.db import recent_messages, save_message
from tools.guard import is_attack
from tools.intent import classify_intent
from tools.stt import transcribe
from tools.vision import check_image, describe_for_question

log = logging.getLogger(__name__)

GREETING_REPLY = ("Hello! I'm the academy assistant. Ask me about courses, fees or batch timings - "
                  "you can type, talk, or send a photo.")
NOT_HEARD_REPLY = "Sorry, I didn't catch that. Could you say it again?"
ERROR_REPLY = "Sorry, I'm having trouble answering right now. Please try again in a moment."
BLOCKED_REPLY = "Sorry, I can't help with that. I can answer questions about our courses, fees, batches and policies."
IMAGE_FAILED_NOTE = "(the image could not be read)"

_NON_LATIN = re.compile(rf"[^\W\d_a-zA-Z{chr(0xC0)}-{chr(0x24F)}]")   # letters outside the Latin script


def is_latin(text: str) -> bool:
    return not _NON_LATIN.search(text or "")


_GUJARATI = re.compile(f"[{chr(0x0A80)}-{chr(0x0AFF)}]")
_DEVANAGARI = re.compile(f"[{chr(0x0900)}-{chr(0x097F)}]")   # Hindi, Marathi, ...


def script_language(text: str):
    """Language implied by the script of typed text (Whisper reports it for voice)."""
    if _GUJARATI.search(text or ""):
        return "Gujarati"
    if _DEVANAGARI.search(text or ""):
        return "Hindi"
    return None


def speak(text: str):
    """Path to a WAV of the reply, or None when the browser should speak it instead
    (TTS_MODE=browser, a non-English reply, or the server voice failed)."""
    if not text or TTS_MODE == "browser" or not is_latin(text):
        return None
    try:
        if TTS_MODE == "groq":
            from tools.tts_groq import synthesize
        else:
            from tools.tts import synthesize   # Piper - loaded only when used
        return synthesize(text)
    except Exception:
        log.warning("Server text-to-speech failed; the browser will speak instead", exc_info=True)
        return None


def run_turn(session_id: str, text: str = "", audio_path: str = None, image: tuple = None):
    """Yield events (dicts) for one turn:
      transcript {text, language} - what a voice message said
      token {text} / reset        - the answer as it streams (reset = discard streamed text)
      rows {rows}                 - database rows behind the answer, for tables and charts
      done {reply, intent, audio_url, language}
      error {message}             - the input was unusable (nothing was saved)
    `image` is (bytes, mime_type)."""
    channel = "voice" if audio_path else "text"
    language, rows = None, None
    text = (text or "").strip()

    if image:
        try:
            check_image(*image)
        except ValueError as exc:
            yield {"type": "error", "message": str(exc)}
            return

    if audio_path:
        text, language = transcribe(audio_path)
        yield {"type": "transcript", "text": text, "language": language}
        if not text and not image:
            yield {"type": "done", "reply": NOT_HEARD_REPLY, "intent": "other",
                   "audio_url": speak(NOT_HEARD_REPLY), "language": language}
            return

    if not text and not image:
        yield {"type": "error", "message": "Type a message, talk, or attach an image."}
        return

    history = recent_messages(session_id)   # read before saving this turn

    image_note = None
    if image:
        try:
            image_note = describe_for_question(image[0], image[1], text)
        except Exception:
            log.exception("Vision model failed")
            image_note = IMAGE_FAILED_NOTE

    # Screen only what the user typed or said. Image descriptions are our vision model's own
    # wording (code blocks, headings), which the guard misreads as attacks; the agent instead
    # treats image text as untrusted data (see SYSTEM_PROMPT).
    blocked = is_attack(text)
    intent = classify_intent(text) if text else "other"
    save_message(session_id, "user", text or "(sent an image)", intent, channel,
                 image_note=image_note, language=language)

    if blocked:
        reply = BLOCKED_REPLY
        yield {"type": "token", "text": reply}
    elif intent == "greeting" and not image and is_latin(text) and len(text.split()) <= 4:
        reply = GREETING_REPLY                  # a plain "hi" needs no LLM call
        yield {"type": "token", "text": reply}
    else:
        reply = ""
        try:
            for kind, value in stream_agent(text or "What does this image show?", session_id,
                                            history, image_note, language or script_language(text)):
                if kind == "token":
                    yield {"type": "token", "text": value}
                elif kind == "reset":
                    yield {"type": "reset"}
                elif kind == "rows":
                    rows = value
                    yield {"type": "rows", "rows": value}
                else:
                    reply = value
        except Exception:
            log.exception("Agent failed")
            reply = ""
        if not reply.strip():
            reply = ERROR_REPLY
            yield {"type": "reset"}
            yield {"type": "token", "text": reply}

    save_message(session_id, "assistant", reply, intent, channel,
                 data=rows if reply != ERROR_REPLY else None)
    audio_url = None
    if channel == "voice":
        path = speak(reply)
        audio_url = f"/audio/{Path(path).name}" if path else None
    yield {"type": "done", "reply": reply, "intent": intent, "audio_url": audio_url, "language": language}


def collect(events):
    """Run a turn to completion: (final 'done' event, transcript or None, rows or None)."""
    done, transcript, rows = None, None, None
    for event in events:
        if event["type"] == "error":
            raise ValueError(event["message"])
        if event["type"] == "transcript":
            transcript = event["text"]
        elif event["type"] == "rows":
            rows = event["rows"]
        elif event["type"] == "done":
            done = event
    return done, transcript, rows
