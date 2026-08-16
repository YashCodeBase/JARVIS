"""
Full voice loop: clap -> listen -> orchestrator -> speak.

The FIRST double-clap of each day triggers the daily briefing immediately
(news + open tasks) -- no need to say anything first, matching "clap twice,
Jarvis wakes up and briefs me." Every wake after that behaves normally:
clap, then say a command.

Designed to keep running even if a single turn fails (network hiccup, search
timeout, TTS glitch, etc.) -- only Ctrl+C or saying an exit phrase stops it.
"""

import sys
import threading
import traceback

from clap_detector import listen_for_double_clap
from listen import listen_for_command
from speak import speak
from orchestrator import Orchestrator
from skills.builtin import has_briefed_today, mark_briefed_today, DailyBriefingSkill

EXIT_PHRASES = {"exit", "quit", "shut down", "goodbye jarvis", "go to sleep"}


def deliver_daily_briefing():
    """Blocks until the next double-clap, then speaks the daily briefing
    directly -- no speech recording/transcription needed for this one."""
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
    print("Jarvis is running. Clap twice to talk. Ctrl+C to quit.")
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
            # Never let one bad turn kill the whole assistant -- log it,
            # tell the user something went wrong, and keep listening.
            print(f"[error] {e}")
            traceback.print_exc()
            try:
                speak("Sorry, something went wrong on that one.")
            except Exception:
                pass  # even TTS failing shouldn't crash the loop
            continue


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[fatal] Jarvis crashed on startup: {e}")
        traceback.print_exc()
        sys.exit(1)
