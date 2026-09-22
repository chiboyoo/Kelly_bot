import os
import hmac
import hashlib
import time
from flask import Flask, request, jsonify
from functools import wraps

app = Flask(__name__)

PROTECTION_SECRET = os.getenv("PROTECTION_SECRET")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me-to-strong-random")

# In-memory store (replace with Redis/DB for production)
ACTIVATED = {}

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get("X-Admin-Token") != ADMIN_TOKEN:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def generate_license(telegram_id: str) -> str:
    sig = hmac.new(
        PROTECTION_SECRET.encode(),
        str(telegram_id).encode(),
        hashlib.sha256
    ).hexdigest()
    return (sig[:16] + "-" + sig[16:24]).upper()

@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(force=True, silent=True) or {}
    telegram_id = str(data.get("telegram_id", "")).strip()
    license_key = str(data.get("license_key", "")).strip().upper()

    if not telegram_id or not license_key or not PROTECTION_SECRET:
        return jsonify({"valid": False, "reason": "missing data"}), 400

    expected = generate_license(telegram_id)
    if not hmac.compare_digest(expected, license_key):
        return jsonify({"valid": False, "reason": "invalid key"})

    # Prevent key reuse by different Telegram IDs
    if license_key in ACTIVATED and ACTIVATED[license_key] != telegram_id:
        return jsonify({"valid": False, "reason": "key already used"})

    ACTIVATED[license_key] = telegram_id
    return jsonify({
        "valid": True,
        "telegram_id": telegram_id,
        "activated_at": int(time.time())
    })

@app.route("/generate", methods=["POST"])
@require_admin
def generate():
    data = request.get_json(force=True, silent=True) or {}
    telegram_id = str(data.get("telegram_id", "")).strip()
    if not telegram_id:
        return jsonify({"error": "telegram_id required"}), 400
    key = generate_license(telegram_id)
    return jsonify({"telegram_id": telegram_id, "license_key": key})

@app.route("/health")
def health():
    return {"status": "ok", "service": "license-server"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
