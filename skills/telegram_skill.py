"""
skills/telegram_skill.py - lets Jarvis send Telegram messages and check
unread messages via your own account (see telegram_client.py for setup).

These skills only register themselves if config.py has real Telegram
credentials filled in -- if you haven't set that up, Jarvis just runs
without them, no crash, no error.
"""

from .base import Skill, registry
import config


class SendTelegramMessageSkill(Skill):
    name = "send_telegram_message"
    description = (
        "Send a Telegram message to a contact by name, @username, or phone number."
    )
    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Contact display name, @username, or phone number",
            },
            "message": {"type": "string", "description": "The message to send"},
        },
        "required": ["target", "message"],
    }

    def execute(self, target: str, message: str) -> str:
        from telegram_client import send_message
        return send_message(target, message)


class CheckTelegramSkill(Skill):
    name = "check_telegram"
    description = "Check which Telegram chats have unread messages."

    def execute(self, **kwargs) -> str:
        from telegram_client import get_recent_unread
        return get_recent_unread()


def register_telegram_skills() -> None:
    has_creds = bool(getattr(config, "TELEGRAM_API_ID", "")) and bool(
        getattr(config, "TELEGRAM_API_HASH", "")
    )
    if not has_creds:
        print("[telegram] No Telegram API credentials in config.py -- skipping Telegram skills.")
        return
    registry.register(SendTelegramMessageSkill())
    registry.register(CheckTelegramSkill())
