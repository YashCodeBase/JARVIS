"""
memory.py - Long-term memory for Jarvis.

Stores facts about the user in a local SQLite database file
(jarvis_memory.db) so Jarvis remembers them forever, even after
restarting the server.

This does NOT retrain or fine-tune the AI model. Instead, every time
you talk to Jarvis, we quietly hand it a "cheat sheet" of known facts
about you, and Jarvis uses that as context. This is the same technique
ChatGPT's memory feature and most commercial AI assistants use under
the hood -- it's fast, cheap, and needs no GPU.
"""

import sqlite3
import json
import threading

from groq_client import chat_completion
import config

DB_PATH = "jarvis_memory.db"

# A small, fast model just for deciding what's worth remembering.
# This is a separate, lightweight call -- it does NOT affect the speed
# of Jarvis's main replies, since it runs in the background AFTER you
# already got your answer.
MEMORY_MODEL = "openai/gpt-oss-20b"


MAX_FACTS_IN_PROMPT = 50  # keeps the prompt from growing forever


def _get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Creates the facts table if it doesn't already exist. Safe to call every startup."""
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def save_fact(fact_text: str) -> None:
    """Saves a single fact permanently."""
    fact_text = fact_text.strip()
    if not fact_text:
        return
    conn = _get_connection()
    conn.execute("INSERT INTO facts (fact) VALUES (?)", (fact_text,))
    conn.commit()
    conn.close()


def get_recent_facts(limit: int = MAX_FACTS_IN_PROMPT) -> list[str]:
    """Returns the most recent saved facts, newest last."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT fact FROM facts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [r[0] for r in reversed(rows)]


def build_memory_block() -> str:
    """Formats all known facts into a text block to insert into the system prompt.
    Returns an empty string if nothing is known yet."""
    facts = get_recent_facts()
    if not facts:
        return ""
    bullet_list = "\n".join(f"- {f}" for f in facts)
    return (
        "\n\nHere is what you already know about the user from past "
        f"conversations:\n{bullet_list}\n\n"
        "IMPORTANT: Treat these as settled preferences, not guesses. If a "
        "known fact answers part of the user's request (e.g. a preferred "
        "color, brand, size, option, or way of doing something), apply it "
        "automatically and proceed -- do NOT ask the user to confirm or "
        "re-state something you already know. Only ask a clarifying "
        "question if the request needs information you genuinely don't "
        "have yet. Don't recite this list back to the user or mention "
        "that you have a memory file -- just act like you remember them, "
        "the same way a long-time assistant would."
    )

_EXTRACTION_SYSTEM_PROMPT = """You extract durable, worth-remembering facts \
about a user from a single conversation turn.

Only extract facts that are:
- Personal and likely to stay true for a while (name, preferences, projects, \
relationships, ongoing goals, recurring habits)
- NOT already obvious from a single throwaway message (e.g. don't save \
"user said hello")
- NOT sensitive in a way that would be risky to store in plain text \
(no passwords, no financial account numbers, no private keys)

Respond ONLY with a JSON array of short fact strings, e.g.:
["User's dog is named Max", "User is building a project called JARVIS"]

If there is nothing worth remembering, respond with exactly: []
Do not include any other text, explanation, or markdown formatting."""


def extract_and_save_facts(user_text: str, assistant_reply: str) -> None:
    """Runs in a background thread. Asks a small fast model whether anything
    in this exchange is worth remembering, and saves it if so."""

    def _run():
        try:
            response = chat_completion(
                model=MEMORY_MODEL,
                messages=[
                    {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"User said: {user_text}\n"
                            f"Assistant replied: {assistant_reply}"
                        ),
                    },
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            facts = json.loads(content)
            if isinstance(facts, list):
                for fact in facts:
                    if isinstance(fact, str) and fact.strip():
                        save_fact(fact)
        except Exception as e:
            # Never let a memory-saving failure crash or slow down Jarvis.
            print(f"[memory] Skipped saving facts due to error: {e}")

    threading.Thread(target=_run, daemon=True).start()
