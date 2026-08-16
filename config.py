"""
Put your Groq API key(s) here. This is the ONLY file you need to edit to get
Jarvis running -- no terminal exports needed.

Get free keys at: https://console.groq.com/keys
(You can create multiple keys on the same account, or use keys from separate
free accounts, to multiply your daily rate limit.)

Add as many as you want -- Jarvis will automatically rotate to the next key
whenever one hits a rate limit (HTTP 429).

IMPORTANT: if you ever share this folder, back this file up with a backup
tool, or push it to GitHub, delete/blank out your real keys first. Treat
these like passwords.
"""

GROQ_API_KEYS = [
    "Paste Here",
    
]


# Which model to use by default. See orchestrator.py for notes on alternatives.
MODEL = "openai/gpt-oss-120b"

# --- Optional: Telegram integration ---
# Get free credentials at https://my.telegram.org/apps (login with your phone
# number, create an app -- 2 minutes). Leave blank to skip Telegram entirely;
# Jarvis runs fine without it.
TELEGRAM_API_ID = #paste
          # your real api_id, as a number, no quotes
TELEGRAM_API_HASH = "Paste here"


WEATHER_API_KEY = "paste here"
