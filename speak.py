"""
speak.py - offline text-to-speech using Piper (fast, natural-sounding, no
internet needed, runs comfortably on CPU).

Setup (one-time):
    pip install piper-tts
    python3 -m piper.download_voices en_US-lessac-medium

That downloads en_US-lessac-medium.onnx + .onnx.json into your current
directory. Browse other voices: https://github.com/rhasspy/piper/blob/master/VOICES.md
"""

import wave
import subprocess
import platform

from piper import PiperVoice

VOICE_MODEL = "en_US-lessac-medium.onnx"  # change if you downloaded a different voice
OUT_WAV = "jarvis_speak.wav"

_voice = PiperVoice.load(VOICE_MODEL)


def speak(text: str) -> None:
    if not text:
        return
    print(f"Jarvis: {text}")
    with wave.open(OUT_WAV, "wb") as wav_file:
        _voice.synthesize_wav(text, wav_file)
    _play(OUT_WAV)


def _play(wav_path: str) -> None:
    # Cross-platform playback without extra Python deps.
    try:
        system = platform.system()
        if system == "Windows":
            import winsound
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)
        elif system == "Darwin":
            subprocess.run(["afplay", wav_path])
        else:  # Linux
            subprocess.run(["aplay", wav_path])
    except Exception as e:
        print(f"[speak] Playback failed ({e}); wav saved at {wav_path}")


if __name__ == "__main__":
    speak("Hello, I am Jarvis. This is a test of the offline speech system.")
