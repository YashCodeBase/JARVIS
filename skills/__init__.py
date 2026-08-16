from .base import registry
from .builtin import register_builtin_skills

register_builtin_skills()

try:
    from .telegram_skill import register_telegram_skills
    register_telegram_skills()
except Exception as e:
    print(f"[telegram] Skipping Telegram skills: {e}")

__all__ = ["registry"]
