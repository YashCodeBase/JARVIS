"""
Lightweight wake trigger: listens for two sharp amplitude spikes (claps)
within a short window. Deliberately avoids any ML model so it can run
continuously on modest hardware (or the Pi) with near-zero CPU usage.

pip install sounddevice numpy

Tune AMPLITUDE_THRESHOLD and CLAP_WINDOW_SEC for your mic/room — noisy
environments may need a higher threshold.
"""

import time
from collections import deque

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK_SIZE = 1024
AMPLITUDE_THRESHOLD = 0.4   # 0-1 scale, raise if false triggers happen
CLAP_WINDOW_SEC = 1.2       # both claps must land inside this window
REFRACTORY_SEC = 0.15       # ignore spikes closer together than this (avoids double-counting one clap)


def listen_for_double_clap(on_trigger, stop_event=None):
    """Blocks and calls on_trigger() each time it detects two claps in a row.

    stop_event: optional threading.Event to allow clean shutdown from another thread.
    """
    clap_times: deque[float] = deque(maxlen=2)
    last_clap = 0.0

    def callback(indata, frames, time_info, status):
        nonlocal last_clap
        amplitude = float(np.abs(indata).max())
        now = time.time()

        if amplitude > AMPLITUDE_THRESHOLD and (now - last_clap) > REFRACTORY_SEC:
            last_clap = now
            clap_times.append(now)
            if len(clap_times) == 2 and (clap_times[1] - clap_times[0]) <= CLAP_WINDOW_SEC:
                clap_times.clear()
                on_trigger()

    with sd.InputStream(
        channels=1,
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        callback=callback,
    ):
        print(f"Listening for double-clap (threshold={AMPLITUDE_THRESHOLD})... Ctrl+C to stop.")
        try:
            while True:
                if stop_event is not None and stop_event.is_set():
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":

    def _on_clap():
        print(">>> Double clap detected — wake Jarvis here <<<")

    listen_for_double_clap(_on_clap)
