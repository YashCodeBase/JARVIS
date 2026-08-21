"""
Loads all secrets/settings from a `.env` file (NOT committed to Git) via
environment variables. This is the ONLY file the rest of Jarvis imports
from, so nothing else in the project needs to change.

SETUP (do this once):
1. Copy `.env.example` in this folder, rename the copy to `.env`
2. Open `.env` and paste your real keys in there
3. NEVER put real keys directly in this file (config.py) -- put them in `.env`
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env in this folder and loads its values


def _get_env_list(key: str) -> list:
    """Reads a comma-separated env var into a list.
    e.g. GROQ_API_KEYS=key1,key2 -> ["key1", "key2"]"""
    raw = os.getenv(key, "")
    return [k.strip() for k in raw.split(",") if k.strip()]


GROQ_API_KEYS = _get_env_list("GROQ_API_KEYS")

# Which model to use by default. See orchestrator.py for notes on alternatives.
MODEL = os.getenv("JARVIS_MODEL", "openai/gpt-oss-120b")

# --- Optional: Telegram integration ---
_telegram_id_raw = os.getenv("TELEGRAM_API_ID", "")
TELEGRAM_API_ID = int(_telegram_id_raw) if _telegram_id_raw.isdigit() else None
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")




# --- Web login ---
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
JARVIS_PASSWORD = os.getenv("JARVIS_PASSWORD", "")




# --- WebAuthn (Face/Fingerprint device login) ---
# This MUST be your Tailscale hostname, no "https://" prefix and no port number.
RP_ID = "jarvis.taildd8ebf.ts.net"
RP_NAME = "Jarvis"
