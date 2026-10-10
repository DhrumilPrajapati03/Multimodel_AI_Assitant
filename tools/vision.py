"""Image understanding on Groq's vision model (no image model runs on the server)."""
import base64

from config import VISION_MODEL
from tools.groq_client import client

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 3_500_000   # Groq accepts base64 images up to ~4 MB

QUESTION_PROMPT = """A student of a computer academy sent this image to the academy's helpdesk assistant.
Their message: "{question}"

Describe what the image shows so the assistant can answer without seeing it:
- Transcribe all readable text exactly (notices, receipts, forms, slides).
- If it shows code or an error message, copy the code and the error exactly.
- Focus on what matters for their message. Be factual and concise; don't answer the question yourself."""

DOCUMENT_PROMPT = """Transcribe all text in this image exactly, keeping headings, lists and table rows in order.
If there is little or no text, describe the image in a few sentences instead."""


def check_image(data: bytes, mime: str):
    """Raise ValueError with a user-friendly message if the image can't be used."""
    if mime not in ALLOWED_TYPES:
        raise ValueError("Please attach a JPEG, PNG, WebP or GIF image.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("That image is too large - please use one under 3.5 MB.")


def _ask(data: bytes, mime: str, prompt: str, max_tokens: int) -> str:
    check_image(data, mime)
    url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    response = client().chat.completions.create(
        model=VISION_MODEL,
        reasoning_format="hidden",
        max_tokens=max_tokens,
        temperature=0.2,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": url}},
        ]}],
    )
    return (response.choices[0].message.content or "").strip()


def describe_for_question(data: bytes, mime: str, question: str) -> str:
    return _ask(data, mime, QUESTION_PROMPT.format(question=question or "(no message)"), 900)


def transcribe_document(data: bytes, mime: str) -> str:
    return _ask(data, mime, DOCUMENT_PROMPT, 3000)
