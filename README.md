# Jarvis — personal AI assistant

A modular, self-hosted AI assistant with two ways to interact: a fully
offline voice loop (clap-to-wake, local STT/TTS) and a browser-based web
app (dark futuristic UI, browser-native voice, HTTPS, login + WebAuthn).
Both share the same reasoning core: an LLM tool-use loop (Groq) with a
pluggable skill system, plus a persistent long-term memory that lets
Jarvis apply known facts/preferences about you automatically, without
asking again.

## What's here

```
jarvis/
  config.py               # loads all settings from .env (see Setup)
  .env / .env.example      # your real secrets go in .env, never committed
  groq_client.py           # key-rotation wrapper (auto-switches keys on rate limits)
  orchestrator.py          # Groq tool-use loop: text in -> skill calls -> reply out
  memory.py                # long-term memory (SQLite) -- facts persist across restarts
  telegram_client.py       # Telethon client -- logs in as YOUR Telegram account
  skills/
    base.py                # Skill interface + registry (add new skills here)
    builtin.py             # time, tasks, open_app, web_search, news, daily_briefing, weather (stub)
    telegram_skill.py      # send_telegram_message, check_telegram (optional, self-disables if unconfigured)
    __init__.py            # auto-registers all skills on import

  # --- Web app (primary interface) ---
  server.py                # Flask server: password login, WebAuthn, HTTPS, /api/chat
  templates/
    login.html             # password login page
    index.html              # dark futuristic chat UI, browser-native voice (Web Speech API)
  webauthn_store.py        # stores registered WebAuthn (Face ID/fingerprint) credentials
  cert.pem / key.pem        # self-signed HTTPS cert (gitignored -- regenerate locally, see Setup)
  san.cnf                   # OpenSSL config used to generate the cert above

  # --- Offline voice loop (secondary/original interface) ---
  clap_detector.py          # zero-ML double-clap wake trigger
  listen.py                 # clap -> record until silence -> faster-whisper STT (offline)
  speak.py                  # Piper TTS (offline)
  main.py                   # wires clap -> daily briefing (first wake/day) -> listen -> orchestrator -> speak

  requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
python3 -m piper.download_voices en_US-lessac-medium
```

### 1. Secrets (`.env`)

Copy the example file and fill in your real values:

```bash
cp .env.example .env
```

Open `.env` and paste in:

```env
GROQ_API_KEYS=gsk_your_real_key_here,gsk_your_second_key_here
FLASK_SECRET_KEY=            # generate with the command below
JARVIS_PASSWORD=yourpassword
```

Generate a Flask secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Get free Groq keys at https://console.groq.com/keys — `groq_client.py`
automatically rotates to the next key whenever one hits a rate limit
(HTTP 429). Adding more keys extends your daily quota.

**Optional — Telegram:** get free credentials at https://my.telegram.org/apps,
add `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` to `.env`, then run
`python telegram_client.py` once to log in (asks for your phone + a login
code). This logs in as your real account, so it can message any of your
actual contacts. Leave blank to skip Telegram entirely.

**Security note:** never commit `.env`, `cert.pem`, `key.pem`, or
`*.session` files. All are already listed in `.gitignore` — double-check
with `git status` before pushing if you fork this.

### 2. HTTPS certificate (needed for the web app)

The web app requires HTTPS (browsers only allow microphone/voice access
and WebAuthn over secure origins). Generate a local self-signed cert:

```bash
openssl req -new -x509 -days 365 -nodes \
  -keyout key.pem -out cert.pem -config san.cnf
```

`san.cnf` should list `localhost`, your LAN IP, and (if using Tailscale)
your Tailscale hostname as Subject Alternative Names — edit it before
generating if your network setup differs.

### 3. Model

Default model is `openai/gpt-oss-120b`, set via `JARVIS_MODEL` in `.env`.
Swap to `openai/gpt-oss-20b` (faster/smaller) if you hit rate limits.
Groq renames/deprecates models periodically — check
https://console.groq.com/docs/models if a model 404s.

## Running it

### Web app (recommended — chat UI, voice, HTTPS)

```bash
python server.py
```

Then open the HTTPS URL it prints (e.g. `https://<your-ip-or-hostname>:5000`)
in a browser, log in with your `JARVIS_PASSWORD`, and start chatting or
talking — voice input/output runs through your browser's built-in Web
Speech API, so no local Whisper/Piper round-trip is needed for the web
app.

### Text-only orchestrator (fastest way to test routing logic)

```bash
python orchestrator.py
```

### Offline voice loop (clap-to-wake, fully local STT/TTS)

Test voice pieces independently:

```bash
python speak.py    # should play audio through your speakers
python listen.py   # clap twice, wait for the beep, say something, check the transcript
```

Full voice loop, with automatic daily briefing on first wake of the day:

```bash
python main.py
```

## Long-term memory

Jarvis remembers facts about you permanently in a local SQLite database
(`jarvis_memory.db`, auto-created, gitignored). After each exchange, a
lightweight background call decides whether anything worth remembering
was said (preferences, ongoing projects, recurring details) and saves it.
Before every reply, Jarvis is reminded of everything it knows and is
instructed to apply known preferences automatically rather than asking
again — e.g. if you've mentioned you prefer black cars, it won't ask
"what color?" the next time that's relevant.

This is retrieval-based memory, not model fine-tuning: no GPU or
retraining involved, just fast local database lookups feeding into the
prompt.

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

## Troubleshooting

- **Garbled/wrong-language transcripts (offline voice loop)** — almost
  always a mic gain issue, not a code bug. Check the
  `[debug] recorded peak amplitude` line `listen.py` prints after each
  recording: it should be roughly 0.3–0.8. If it's near 0, your mic isn't
  picking up voice; if it's above 1.0, your input gain is too hot (check
  both `alsamixer` -> F4 -> Capture *and* `pavucontrol` -> Input Devices).
- **speak.py fails to load the voice model** — usually means the `.onnx`
  file didn't fully download. Check its size (`ls -la *.onnx`, should be
  ~60MB) and re-run the download command if it's small/corrupted.
- **`[memory] Skipped saving facts due to error: ... model_not_found`** —
  Groq deprecated the model set as `MEMORY_MODEL` in `memory.py`. Check
  https://console.groq.com/docs/models for a current model ID and update
  the constant.
- **Browser blocks microphone/WebAuthn** — both require a secure (HTTPS)
  context. Make sure you're opening the `https://` URL server.py prints,
  not `http://`, and that your browser trusts the self-signed cert (or
  you're accessing via your Tailscale hostname once that's set up).

## Known stubs / in progress

- `skills/builtin.py::WeatherSkill` — needs an OpenWeatherMap/WeatherAPI key
- `skills/builtin.py::OpenAppSkill.APP_MAP` — extend for any app whose
  display name doesn't match its actual launch command
- Tailscale private hostname — needed for stable remote access and to
  finish enabling WebAuthn outside your home network
- Arduino Uno integration for physical/hardware control — not started
- Jarvis can currently *draft* actions (e.g. a message to send) but can't
  yet autonomously take real-world actions (submitting forms, sending
  messages itself) — planned as a future "Computer Interaction" phase

## Notes on hardware

- STT (`listen.py`, faster-whisper `base` model) and TTS (`speak.py`,
  Piper) both run fully offline/locally for the CLI voice loop — no
  internet needed for voice there, only for the LLM reasoning step.
  The web app instead uses the browser's built-in Web Speech API for
  speed, so it needs an internet-connected browser either way.
- Clap detection (`clap_detector.py`) intentionally avoids any ML model,
  so it can idle continuously without taxing the CPU.
- Free-tier Groq limits still apply to the reasoning step — if you hit
  429s even with key rotation, switch `JARVIS_MODEL` in `.env` to a
  higher-RPM model.
- No GPU is required anywhere in this project — Groq's reasoning calls
  run in the cloud, and the memory system is plain SQLite lookups.

## Suggested next steps

1. Finish Tailscale setup for a stable private hostname
2. Enable WebAuthn (Face ID/fingerprint) login once the hostname is stable
3. Fill in more `APP_MAP` entries / test open_app against your real apps
4. Add a memory management skill (view/forget specific facts) if desired
5. Arduino Uno integration for physical/hardware control
