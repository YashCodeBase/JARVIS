"""
listen.py - offline listening: double-clap wake trigger, record command,
transcribe with faster-whisper (fully local, no API call).
"""

import time
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

from clap_detector import listen_for_double_clap

SAMPLE_RATE = 16000
TMP_WAV = "jarvis_capture.wav"
POST_CLAP_PAUSE = 0.4  # avoid capturing the tail of the clap itself

# --- Silence-based auto-stop settings ---
BLOCK_DURATION = 0.1          # seconds analyzed per chunk
SILENCE_THRESHOLD = 0.02      # RMS below this = "silence". Raise if it cuts you
                               # off mid-sentence; lower if it never stops on its own.
SILENCE_DURATION_SEC = 1.2    # how long you must pause before it stops recording
MIN_RECORD_SECONDS = 0.6      # grace period before silence-detection kicks in,
                               # so it doesn't stop before you've started talking
MAX_RECORD_SECONDS = 20       # hard cap so it can never listen forever

# "base" gives much better accuracy than "tiny" for a small speed cost.
# Drop to "tiny" only if this feels too slow on your machine.
_model = WhisperModel("base", device="cpu", compute_type="int8")


def _beep():
    # Short audible cue so you know exactly when to start talking.
    tone = (np.sin(2 * np.pi * 880 * np.arange(int(SAMPLE_RATE * 0.15)) / SAMPLE_RATE) * 0.3).astype("float32")
    sd.play(tone, SAMPLE_RATE)
    sd.wait()


def _record() -> str:
    """Records from the mic until you pause for SILENCE_DURATION_SEC, instead
    of a fixed duration -- so long sentences aren't cut off."""
    time.sleep(POST_CLAP_PAUSE)  # let the clap's echo die out
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
                continue  # don't count silence during the initial grace period

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
        audio = audio / peak * 0.9  # scale down so max amplitude is a safe 0.9

    sf.write(TMP_WAV, audio, SAMPLE_RATE)
    return TMP_WAV


def _transcribe(wav_path: str) -> str:
    segments, _ = _model.transcribe(
        wav_path,
        language="en",             # avoid Whisper mis-guessing the language on noisy audio
        vad_filter=True,           # skip silent stretches instead of hallucinating text from them
        vad_parameters=dict(min_silence_duration_ms=300),
    )
    return " ".join(seg.text for seg in segments).strip()


def listen_for_command() -> str:
    """Blocks until a double-clap is heard, then records a short command and
    returns the transcribed text. Call this in a loop for continuous listening."""
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
