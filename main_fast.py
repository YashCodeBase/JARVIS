"""
main_fast.py - identical to main.py, but uses listen_fast.py (cloud STT via
Groq) instead of listen.py (local CPU STT). Run this side-by-side with
main.py to compare speed/accuracy for yourself.
"""

import sys
import threading
import traceback

from clap_detector import listen_for_double_clap
from listen_fast import listen_for_command
from speak import speak
from orchestrator import Orchestrator
from skills.builtin import has_briefed_today, mark_briefed_today, DailyBriefingSkill

EXIT_PHRASES = {"exit", "quit", "shut down", "goodbye jarvis", "go to sleep"}


def deliver_daily_briefing():
    print("Clap twice for your daily briefing...")
    stop_event = threading.Event()

    def _on_clap():
        stop_event.set()

    listen_for_double_clap(_on_clap, stop_event=stop_event)

    reply = DailyBriefingSkill().execute()
    mark_briefed_today()
    speak(reply)


def main():
    orch = Orchestrator()
    print("=" * 50)
    print("Jarvis (fast/cloud STT) is running. Clap twice to talk. Ctrl+C to quit.")
    print("=" * 50)

    if not has_briefed_today():
        try:
            deliver_daily_briefing()
        except KeyboardInterrupt:
            print("\nShutting down.")
            return
        except Exception as e:
            print(f"[error] Daily briefing failed: {e}")
            traceback.print_exc()

    while True:
        try:
            text = listen_for_command()

            if not text:
                speak("I didn't catch that.")
                continue

            print(f"You said: {text}")

            if text.strip().lower().rstrip(".!") in EXIT_PHRASES:
                speak("Goodbye.")
                break

            reply = orch.handle(text)
            speak(reply)

        except KeyboardInterrupt:
            print("\nShutting down.")
            break

        except Exception as e:
            print(f"[error] {e}")
            traceback.print_exc()
            try:
                speak("Sorry, something went wrong on that one.")
            except Exception:
                pass
            continue


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[fatal] Jarvis crashed on startup: {e}")
        traceback.print_exc()
        sys.exit(1)
