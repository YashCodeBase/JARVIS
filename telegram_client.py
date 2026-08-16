"""
telegram_client.py - Telethon-based Telegram client that logs in as YOUR own
account (a "userbot"), so Jarvis can send messages to your real contacts
exactly as if you typed them yourself.

First-time setup:
1. Get free API credentials at https://my.telegram.org/apps (login with your
   phone number, create an app -- takes about 2 minutes)
2. Put TELEGRAM_API_ID and TELEGRAM_API_HASH into config.py
3. Run this file directly once:
       python telegram_client.py
   It will ask for your phone number, then the login code Telegram texts
   you. After that, a jarvis_telegram.session file is saved locally and you
   won't be asked to log in again.

IMPORTANT:
- jarvis_telegram.session grants full access to your Telegram account.
  Treat it like a password -- never share it, commit it, or upload it
  anywhere. Add it to .gitignore if you use git.
- This automates your personal account. Telegram is generally permissive
  about userbots for personal use (unlike WhatsApp's stricter stance), but
  avoid spammy/bulk messaging behavior, which can still get flagged.
"""

import asyncio

from telethon import TelegramClient

import config

SESSION_NAME = "jarvis_telegram"

# On newer Python versions, asyncio.get_event_loop() no longer auto-creates a
# loop outside of a running coroutine -- so we create one explicitly here and
# share it between the client and every call below, instead of asking for
# "the current loop" fresh each time (which is what was breaking).
try:
    _loop = asyncio.get_event_loop()
    if _loop.is_closed():
        raise RuntimeError
except RuntimeError:
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

_client = TelegramClient(SESSION_NAME, config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH, loop=_loop)


async def _resolve_entity(target: str):
    """Try target as a direct username/phone/ID first; fall back to a
    case-insensitive substring search over your chat list by display name."""
    try:
        return await _client.get_entity(target)
    except Exception:
        pass

    async for dialog in _client.iter_dialogs():
        if target.lower() in dialog.name.lower():
            return dialog.entity

    raise ValueError(f"Could not find a Telegram contact matching '{target}'")


def send_message(target: str, message: str) -> str:
    """target can be a username (e.g. '@someone'), phone number, or a
    contact's display name (fuzzy-matched against your chat list)."""

    async def _send():
        if not _client.is_connected():
            await _client.connect()
        entity = await _resolve_entity(target)
        await _client.send_message(entity, message)
        return f"Sent to {target}: {message}"

    try:
        return _loop.run_until_complete(_send())
    except Exception as e:
        return f"Failed to send Telegram message to '{target}': {e}"


def get_recent_unread(limit_chats: int = 10) -> str:
    async def _fetch():
        if not _client.is_connected():
            await _client.connect()
        lines = []
        async for dialog in _client.iter_dialogs(limit=limit_chats):
            if dialog.unread_count > 0:
                lines.append(f"{dialog.name}: {dialog.unread_count} unread")
        return lines

    try:
        lines = _loop.run_until_complete(_fetch())
        if not lines:
            return "No unread Telegram messages."
        return "Unread Telegram chats:\n" + "\n".join(lines)
    except Exception as e:
        return f"Failed to check Telegram messages: {e}"


if __name__ == "__main__":
    # One-time interactive login. Run this manually before using the skills.
    with _client:
        print("Telegram login successful. Session saved -- you won't need to log in again.")
