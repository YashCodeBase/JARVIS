"""
webauthn_store.py - stores the trusted device credential for Jarvis's
WebAuthn (Face/Fingerprint) login. Since this is a personal, single-user
assistant, we only ever store one credential. Registering a new device
replaces the previous one.

Stored in a local JSON file (git-ignored). This only holds a PUBLIC key --
not sensitive like a password -- but kept out of Git since it's specific
to your device.
"""

import json
import os

STORE_PATH = os.path.join(os.path.dirname(__file__), "webauthn_credential.json")


def save_credential(credential_id: str, public_key: str, sign_count: int) -> None:
    data = {
        "credential_id": credential_id,
        "public_key": public_key,
        "sign_count": sign_count,
    }
    with open(STORE_PATH, "w") as f:
        json.dump(data, f)


def load_credential():
    if not os.path.exists(STORE_PATH):
        return None
    with open(STORE_PATH) as f:
        return json.load(f)


def update_sign_count(new_count: int) -> None:
    data = load_credential()
    if data:
        data["sign_count"] = new_count
        with open(STORE_PATH, "w") as f:
            json.dump(data, f)


def clear_credential() -> None:
    if os.path.exists(STORE_PATH):
        os.remove(STORE_PATH)
