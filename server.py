"""
server.py - Jarvis's web server: password login + WebAuthn (Face/Fingerprint)
device registration, served over HTTPS via Tailscale.
"""

import hmac
from functools import wraps

from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response

import webauthn
from webauthn import generate_registration_options, verify_registration_response, options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    RegistrationCredential,
    ResidentKeyRequirement,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes

import config
import webauthn_store
from orchestrator import Orchestrator

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

if not app.secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY is not set in your .env file. "
        "Run: python -c \"import secrets; print(secrets.token_hex(32))\" "
        "and paste the result into .env as FLASK_SECRET_KEY=..."
    )

if not config.JARVIS_PASSWORD:
    raise RuntimeError(
        "JARVIS_PASSWORD is not set in your .env file. "
        "Add a line like JARVIS_PASSWORD=yourpassword to .env"
    )

orch = Orchestrator()

RP_ID = config.RP_ID
RP_NAME = config.RP_NAME
ORIGIN = f"https://{RP_ID}:5000"
USER_ID = b"jarvis-owner"
USER_NAME = "yash"


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        submitted = request.form.get("password", "")
        if hmac.compare_digest(submitted, config.JARVIS_PASSWORD):
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Incorrect password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    user_text = (data.get("message") or "").strip()
    mode = (data.get("mode") or "auto").strip()
    if not user_text:
        return jsonify({"error": "empty message"}), 400
    reply = orch.handle(user_text, mode=mode)
    return jsonify({"reply": reply})

# --- WebAuthn: device registration (Step 3b-i) ---

@app.route("/webauthn/register/begin", methods=["GET"])
@login_required
def webauthn_register_begin():
    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=USER_ID,
        user_name=USER_NAME,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
    )
    session["webauthn_challenge"] = bytes_to_base64url(options.challenge)
    return Response(options_to_json(options), mimetype="application/json")


@app.route("/webauthn/register/complete", methods=["POST"])
@login_required
def webauthn_register_complete():
    expected_challenge = base64url_to_bytes(session.get("webauthn_challenge", ""))
    try:
        verification = verify_registration_response(
            credential=request.data,
            expected_challenge=expected_challenge,
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
        )
    except Exception as e:
        return jsonify({"verified": False, "error": str(e)}), 400

if __name__ == "__main__":
    print("Jarvis web server starting...")
    print(f"Open: {ORIGIN}")
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        ssl_context=(
            "jarvis.taildd8ebf.ts.net.crt",
            "jarvis.taildd8ebf.ts.net.key",
        ),
        threaded=True,
    )
