"""Screen user input for prompt-injection / jailbreak attempts with Llama Prompt Guard 2."""
import logging

from config import GUARD_MODEL, GUARD_THRESHOLD
from tools.groq_client import client

log = logging.getLogger(__name__)


def attack_score(text: str) -> float:
    """Probability (0-1) that the text tries to override the assistant's instructions."""
    text = (text or "").strip()
    if not text:
        return 0.0
    response = client().chat.completions.create(
        model=GUARD_MODEL,
        messages=[{"role": "user", "content": text[:2000]}],
    )
    return float(response.choices[0].message.content.strip())


def is_attack(text: str) -> bool:
    try:
        return attack_score(text) >= GUARD_THRESHOLD
    except Exception:
        # Fail open: an outage of the guard shouldn't take the whole assistant down.
        log.warning("Prompt guard unavailable; allowing message", exc_info=True)
        return False
