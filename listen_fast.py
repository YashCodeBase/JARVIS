"""
listen_fast.py - speed-optimized alternative to listen.py.

Same clap-wake + silence-based recording, but transcribes via Groq's hosted
Whisper (whisper-large-v3-turbo) instead of running Whisper locally on your
CPU. Groq's inference hardware is typically much faster than CPU-bound local
transcription, at the cost of needing internet and using a small slice of
your Groq free-tier quota (shares your existing keys in config.py).

Kept as a separate file from listen.py on purpose -- your original offline
setup keeps working untouched; this is an opt-in alternative you can compare
side-by-side (see main_fast.py).
"""

import time
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

from clap_detector import listen_for_double_clap
from groq_client import transcribe_audio

SAMPLE_RATE = 16000
TMP_WAV = "jarvis_capture.wav"
POST_CLAP_PAUSE = 0.4

# --- Silence-based auto-stop settings (same tuning as listen.py) ---
BLOCK_DURATION = 0.1
SILENCE_THRESHOLD = 0.02
SILENCE_DURATION_SEC = 1.2
MIN_RECORD_SECONDS = 0.6
MAX_RECORD_SECONDS = 20


def _beep():
    tone = (np.sin(2 * np.pi * 880 * np.arange(int(SAMPLE_RATE * 0.15)) / SAMPLE_RATE) * 0.3).astype("float32")
    sd.play(tone, SAMPLE_RATE)
    sd.wait()


def _record() -> str:
    time.sleep(POST_CLAP_PAUSE)
    _beep()
    print("Listening... (stops automatically when you pause)")

    block_size = int(SAMPLE_RATE * BLOCK_DURATION)
    silent_blocks_needed = int(SILENCE_DURATION_SEC / BLOCK_DURATION)
    max_blocks = int(MAX_RECORD_SECONDS / BLOCK_DURATION)
    min_blocks = int(MIN_RECORD_SECONDS / BLOCK_DURATION)

    frames = []
    silent_count = 0

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
        for i in range(max_blocks):
            block, _ = stream.read(block_size)
            frames.append(block.copy())

            rms = float(np.sqrt(np.mean(block ** 2)))
            if i < min_blocks:
                continue
            if rms < SILENCE_THRESHOLD:
                silent_count += 1
                if silent_count >= silent_blocks_needed:
                    break
            else:
                silent_count = 0

    audio = np.concatenate(frames, axis=0)

    peak = float(np.abs(audio).max())
    print(f"[debug] recorded peak amplitude: {peak:.3f}")
    if peak > 1.0:
        print("[warning] Input was over 1.0 (mic gain too hot) — normalizing before transcription.")
        audio = audio / peak * 0.9

    sf.write(TMP_WAV, audio, SAMPLE_RATE)
    return TMP_WAV


def _transcribe(wav_path: str) -> str:
    t0 = time.time()
    with open(wav_path, "rb") as f:
        result = transcribe_audio(
            file=(wav_path, f.read()),
            model="whisper-large-v3-turbo",
            language="en",
        )
    print(f"[debug] Groq transcription took {time.time() - t0:.2f}s")
    return (result.text or "").strip()


def listen_for_command() -> str:
    captured = {"text": ""}
    stop_event = threading.Event()

    def _on_clap():
        wav = _record()
        captured["text"] = _transcribe(wav)
        stop_event.set()

    listen_for_double_clap(_on_clap, stop_event=stop_event)
    return captured["text"]


if __name__ == "__main__":
    print("Clap twice, wait for the beep, then say something...")
    text = listen_for_command()
    print(f"You said: {text}")
