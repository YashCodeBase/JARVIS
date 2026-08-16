# Jarvis — starter project

LLM-driven tool routing + a pluggable skill system + a fully offline
clap-wake voice loop (STT and TTS both run locally; only the reasoning LLM
calls out to Groq's free API).

## What's here

```
jarvis/
  config.py               # <-- paste your Groq (and optionally Telegram) keys here
  groq_client.py            # key-rotation wrapper (auto-switches keys on rate limits)
  telegram_client.py        # Telethon client -- logs in as YOUR Telegram account
  skills/
    base.py            # Skill interface + registry (add new skills here)
    builtin.py          # time, tasks, open_app, web_search, news, daily_briefing, weather (stub)
    telegram_skill.py    # send_telegram_message, check_telegram (optional, self-disables if unconfigured)
    __init__.py          # auto-registers all skills on import
  orchestrator.py         # Groq tool-use loop: text in -> skill calls -> reply out
  clap_detector.py        # zero-ML double-clap wake trigger
  listen.py                # clap -> record until silence -> faster-whisper STT (offline)
  speak.py                  # Piper TTS (offline)
  main.py                    # wires clap -> daily briefing (first wake/day) -> listen -> orchestrator -> speak
  requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
python3 -m piper.download_voices en_US-lessac-medium
```

Open `config.py` and paste your key(s):
```python
GROQ_API_KEYS = [
    "gsk_your_real_key_here",
    "gsk_your_second_key_here",   # optional — add more to extend your daily quota
]
```
Get free keys at https://console.groq.com/keys. `groq_client.py`
automatically rotates to the next key whenever one hits a rate limit (HTTP 429).

**Optional — Telegram:** get free credentials at https://my.telegram.org/apps,
add `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` to `config.py`, then run
`python telegram_client.py` once to log in (asks for your phone + a login
code). This logs in as your real account (not a separate bot), so it can
message any of your actual contacts. Leave the credentials blank to skip
Telegram entirely — Jarvis runs fine without it.

**Security note:** `config.py` and `jarvis_telegram.session` both hold real
secrets once filled in. Don't push either to GitHub or share the folder
as-is without stripping them first.

Default model is `openai/gpt-oss-120b`, set in `config.py`. Swap to
`openai/gpt-oss-20b` (faster/smaller) or `llama-3.1-8b-instant` (fastest,
higher request cap, weaker reasoning) if you hit limits. Groq
renames/deprecates models periodically — check https://console.groq.com/docs/models
if a model 404s.

## Running it

Text-only (fastest way to test routing logic):
```bash
python orchestrator.py
```

Test voice pieces independently:
```bash
python speak.py    # should play audio through your speakers
python listen.py    # clap twice, wait for the beep, say something, check the transcript
```

Full voice loop, with automatic daily briefing on first wake of the day:
```bash
python main.py
```

## Adding a new skill

1. Create a class in `skills/builtin.py` (or a new file) inheriting from `Skill`:

```python
class MySkill(Skill):
    name = "my_skill"
    description = "One clear sentence — this is what the LLM reads to decide when to call it."
    parameters = {
        "type": "object",
        "properties": {"arg1": {"type": "string"}},
        "required": ["arg1"],
    }

    def execute(self, arg1: str) -> str:
        ...
        return "result text"
```

2. Register it (add to the list in `register_builtin_skills()`, or
   `registry.register(MySkill())` anywhere that runs at import time).

Nothing in `orchestrator.py` needs to change — the LLM sees the new tool
automatically and decides when to call it based on `description`.

## open_app on Linux

`OpenAppSkill` tries, in order: (1) a quick-hit map of known apps in
`APP_MAP`, (2) checking if the name is directly a command on your `PATH`,
(3) searching your installed `.desktop` entries (`/usr/share/applications`
etc.) for a name match and launching via `gtk-launch`. This means most
installed GUI apps work without you having to hand-map them — only add to
`APP_MAP` for apps where the display name doesn't match the actual command.

## Troubleshooting audio

- **Garbled/wrong-language transcripts** — almost always a mic gain issue,
  not a code bug. Check the `[debug] recorded peak amplitude` line `listen.py`
  prints after each recording: it should be roughly 0.3–0.8. If it's near 0,
  your mic isn't picking up voice; if it's above 1.0, your input gain is too
  hot (check both `alsamixer` -> F4 -> Capture *and* `pavucontrol` -> Input
  Devices, since PipeWire/PulseAudio has its own separate gain layer on top
  of ALSA).
- **speak.py fails to load the voice model** — usually means the `.onnx`
  file didn't fully download. Check its size (`ls -la *.onnx`, should be
  ~60MB) and re-run the download command if it's small/corrupted.

## Known stubs to fill in

- `skills/builtin.py::WeatherSkill` — needs an OpenWeatherMap/WeatherAPI key
- `skills/builtin.py::OpenAppSkill.APP_MAP` — extend for any app whose
  display name doesn't match its actual launch command
- Web search / news / game recommendation skills — not included yet; add as
  a `Skill` that calls a search API and returns a summarized string

## Notes on hardware

- STT (`listen.py`, faster-whisper `base` model) and TTS (`speak.py`, Piper)
  both run fully offline/locally — no internet needed for voice, only for the
  LLM reasoning step.
- Clap detection (`clap_detector.py`) intentionally avoids any ML model, so
  it can idle continuously without taxing the CPU.
- Free-tier Groq limits still apply to the reasoning step — if you hit 429s
  even with key rotation, switch `MODEL` in `config.py` to a higher-RPM model.
- When you move to the Raspberry Pi: `clap_detector.py` + `listen.py` are
  light enough to run there directly; `speak.py`/Piper is also lightweight
  enough for a Pi 4/5. Only `orchestrator.py`'s Groq calls need internet.

## Suggested next steps

1. Fill in more `APP_MAP` entries / test open_app against your real apps
2. Add a `web_search` skill (news briefing, game recommendations, etc.)
3. Build a daily-briefing skill (news + open tasks) triggered specifically on wake
4. Telegram integration as a parallel input channel
5. WhatsApp integration (higher effort, treat as optional/last)
