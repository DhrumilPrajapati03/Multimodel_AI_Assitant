import logging
from tools.intent import classify_intent
from tools.agent import ask_agent
from tools.stt import transcribe
from tools.db import save_message
from config import TTS_MODE

log = logging.getLogger(__name__)

GREETING_REPLY = "Hello! I'm the academy assistant. Ask me about courses, fees or batch timings."
NOT_HEARD_REPLY = "Sorry, I didn't catch that. Could you say it again?"
ERROR_REPLY = "Sorry, I'm having trouble answering right now. Please try again in a moment."


def handle_text(text: str, session_id: str, channel: str = "text"):
    intent = classify_intent(text)
    save_message(session_id, "user", text, intent, channel)

    if intent == "greeting":
        reply = GREETING_REPLY          # no LLM call needed
    else:
        try:
            reply = ask_agent(text, session_id)
        except Exception:
            log.exception("Agent failed")
            reply = ERROR_REPLY

    save_message(session_id, "assistant", reply, intent, channel)
    return reply, intent


def speak(text: str):
    """Path to a WAV of the reply, or None when the browser does the speaking."""
    if TTS_MODE != "server":
        return None
    from tools.tts import synthesize   # loads Piper only when it's used
    return synthesize(text)


def handle_voice(audio_path: str, session_id: str):
    transcript = transcribe(audio_path)
    if not transcript:
        return transcript, NOT_HEARD_REPLY, speak(NOT_HEARD_REPLY)
    reply, _ = handle_text(transcript, session_id, channel="voice")
    return transcript, reply, speak(reply)