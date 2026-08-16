"""
Wraps the Groq client so callers can just do:

    from groq_client import chat_completion
    response = chat_completion(model=..., messages=..., tools=..., tool_choice=...)

and it transparently rotates through config.GROQ_API_KEYS whenever one hits a
rate limit (HTTP 429), so you can stack multiple free-tier keys instead of
sharing one key's daily/per-minute cap.
"""

import itertools

from groq import Groq, RateLimitError

from config import GROQ_API_KEYS

if not GROQ_API_KEYS or GROQ_API_KEYS[0].startswith("gsk_PASTE"):
    raise RuntimeError(
        "No Groq API key configured. Open config.py and paste at least one "
        "real key into GROQ_API_KEYS."
    )

_clients = [Groq(api_key=k) for k in GROQ_API_KEYS]
_client_cycle = itertools.cycle(enumerate(_clients))


def chat_completion(**kwargs):
    """Same signature as client.chat.completions.create(...). Tries each
    configured key in turn if the current one is rate-limited."""
    last_error = None
    for _ in range(len(_clients)):
        idx, client = next(_client_cycle)
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            last_error = e
            print(f"[groq_client] Key #{idx + 1} rate-limited, trying next key...")
            continue
    raise RuntimeError(
        f"All {len(_clients)} Groq API key(s) are rate-limited. "
        f"Wait a bit, or add another key in config.py. Last error: {last_error}"
    )


def transcribe_audio(**kwargs):
    """Same signature as client.audio.transcriptions.create(...), with the
    same key-rotation behavior. (Not used by default now that listen.py runs
    transcription locally via faster-whisper, but kept here in case you want
    to fall back to Groq's hosted Whisper.)"""
    last_error = None
    for _ in range(len(_clients)):
        idx, client = next(_client_cycle)
        try:
            return client.audio.transcriptions.create(**kwargs)
        except RateLimitError as e:
            last_error = e
            print(f"[groq_client] Key #{idx + 1} rate-limited, trying next key...")
            continue
    raise RuntimeError(
        f"All {len(_clients)} Groq API key(s) are rate-limited. "
        f"Wait a bit, or add another key in config.py. Last error: {last_error}"
    )
