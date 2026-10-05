import os
import uuid
import requests
import gradio as gr

API_URL = os.getenv("API_URL", "http://localhost:7860")


def chat_fn(message, history, session_id):
    if not message.strip():
        return history, ""
    r = requests.post(f"{API_URL}/chat",
                      json={"text": message, "session_id": session_id}, timeout=60)
    reply = r.json()["reply"]
    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]
    return history, ""


def voice_fn(audio_path, history, session_id):
    if audio_path is None:
        return history, None
    with open(audio_path, "rb") as f:
        r = requests.post(f"{API_URL}/voice", data={"session_id": session_id},
                          files={"audio": f}, timeout=120)
    d = r.json()
    history = history + [
        {"role": "user", "content": f"(voice) {d['transcript'] or '...'}"},
        {"role": "assistant", "content": d["reply"]},
    ]
    return history, f"{API_URL}{d['audio_url']}"


with gr.Blocks(title="Academy Assistant") as demo:
    gr.Markdown("## Academy Assistant\nAsk about courses, fees, timings or syllabus.")
    session = gr.State(lambda: uuid.uuid4().hex)   # new id per browser session
    chatbot = gr.Chatbot(height=450)
    with gr.Row():
        txt = gr.Textbox(placeholder="Type your question...", show_label=False, scale=4)
        send = gr.Button("Send", scale=1)
    mic = gr.Audio(sources=["microphone"], type="filepath", label="Or ask by voice")
    reply_audio = gr.Audio(label="Spoken reply", autoplay=True)

    send.click(chat_fn, [txt, chatbot, session], [chatbot, txt])
    txt.submit(chat_fn, [txt, chatbot, session], [chatbot, txt])
    mic.stop_recording(voice_fn, [mic, chatbot, session], [chatbot, reply_audio])