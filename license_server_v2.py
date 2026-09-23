#!/usr/bin/env python3
"""AutoPilot Pro License Server v2.

Persistent SQLite-backed license management with manually supplied expiration dates.
Keep PROTECTION_SECRET and ADMIN_TOKEN private on the server.
"""
import os
import hmac
import hashlib
import sqlite3
from datetime import datetime, timezone, time as dtime
from functools import wraps
from flask import Flask, request, jsonify

app = Flask(__name__)

PROTECTION_SECRET = os.getenv("PROTECTION_SECRET", "").strip()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
DB_PATH = os.getenv("LICENSE_DB_PATH", "./data/licenses.db")

if not PROTECTION_SECRET:
    raise RuntimeError("PROTECTION_SECRET is required")
if not ADMIN_TOKEN:
    raise RuntimeError("ADMIN_TOKEN is required")


def db_connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            telegram_id TEXT NOT NULL UNIQUE,
            created_at INTEGER NOT NULL,
            activated_at INTEGER,
            expires_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_licenses_telegram ON licenses(telegram_id)")
        conn.commit()


init_db()


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hmac.compare_digest(request.headers.get("X-Admin-Token", ""), ADMIN_TOKEN):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def generate_license(telegram_id: str) -> str:
    sig = hmac.new(
        PROTECTION_SECRET.encode(),
        str(telegram_id).encode(),
        hashlib.sha256,
    ).hexdigest()
    return (sig[:16] + "-" + sig[16:24]).upper()


def parse_expiration(value: str) -> int:
    """Accept YYYY-MM-DD or ISO-8601 and return a UTC timestamp."""
    value = str(value or "").strip()
    if not value:
        raise ValueError("expires_at is required")

    if len(value) == 10:
        dt = datetime.strptime(value, "%Y-%m-%d").replace(
            tzinfo=timezone.utc, hour=23, minute=59, second=59
        )
    else:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp())


def license_response(row, now=None):
    now = int(now or datetime.now(timezone.utc).timestamp())
    expired = row["expires_at"] <= now
    status = "expired" if expired else row["status"]
    return {
        "valid": status == "active" and not expired,
        "status": status,
        "license_key": row["license_key"],
        "telegram_id": row["telegram_id"],
        "activated_at": row["activated_at"],
        "expires_at": row["expires_at"],
    }


@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(force=True, silent=True) or {}
    telegram_id = str(data.get("telegram_id", "")).strip()
    license_key = str(data.get("license_key", "")).strip().upper()

    if not telegram_id or not license_key:
        return jsonify({"valid": False, "status": "invalid", "reason": "missing data"}), 400

    expected = generate_license(telegram_id)
    if not hmac.compare_digest(expected, license_key):
        return jsonify({"valid": False, "status": "invalid", "reason": "invalid key"})

    with db_connect() as conn:
        row = conn.execute(
            "SELECT * FROM licenses WHERE license_key=? AND telegram_id=?",
            (license_key, telegram_id),
        ).fetchone()

        if not row:
            return jsonify({"valid": False, "status": "not_activated", "reason": "license not activated"})

        now = int(datetime.now(timezone.utc).timestamp())
        if row["activated_at"] is None:
            conn.execute(
                "UPDATE licenses SET activated_at=? WHERE license_key=?",
                (now, license_key),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM licenses WHERE license_key=?", (license_key,)).fetchone()

        result = license_response(row, now)
        if result["status"] == "revoked":
            result["reason"] = "license revoked"
        elif result["status"] == "expired":
            result["reason"] = "license expired"
        return jsonify(result)


@app.route("/generate", methods=["POST"])
@require_admin
def generate():
    data = request.get_json(force=True, silent=True) or {}
    telegram_id = str(data.get("telegram_id", "")).strip()
    if not telegram_id:
        return jsonify({"error": "telegram_id required"}), 400

    try:
        expires_at = parse_expiration(data.get("expires_at"))
    except ValueError as exc:
        return jsonify({"error": str(exc), "format": "YYYY-MM-DD or ISO-8601"}), 400

    now = int(datetime.now(timezone.utc).timestamp())
    if expires_at <= now:
        return jsonify({"error": "expiration must be in the future"}), 400

    key = generate_license(telegram_id)
    with db_connect() as conn:
        existing = conn.execute(
            "SELECT activated_at FROM licenses WHERE license_key=?", (key,)
        ).fetchone()
        activated_at = existing["activated_at"] if existing else None
        conn.execute("""INSERT INTO licenses
            (license_key, telegram_id, created_at, activated_at, expires_at, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            ON CONFLICT(license_key) DO UPDATE SET
                telegram_id=excluded.telegram_id,
                expires_at=excluded.expires_at,
                status='active'
        """, (key, telegram_id, now, activated_at, expires_at))
        conn.commit()

    return jsonify({
        "telegram_id": telegram_id,
        "license_key": key,
        "expires_at": expires_at,
        "expires_at_utc": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(),
        "status": "active",
    })


@app.route("/revoke", methods=["POST"])
@require_admin
def revoke():
    data = request.get_json(force=True, silent=True) or {}
    key = str(data.get("license_key", "")).strip().upper()
    if not key:
        return jsonify({"error": "license_key required"}), 400
    with db_connect() as conn:
        cur = conn.execute("UPDATE licenses SET status='revoked' WHERE license_key=?", (key,))
        conn.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "license not found"}), 404
    return jsonify({"ok": True, "license_key": key, "status": "revoked"})


@app.route("/license", methods=["POST"])
@require_admin
def license_info():
    data = request.get_json(force=True, silent=True) or {}
    key = str(data.get("license_key", "")).strip().upper()
    if not key:
        return jsonify({"error": "license_key required"}), 400
    with db_connect() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE license_key=?", (key,)).fetchone()
    if not row:
        return jsonify({"error": "license not found"}), 404
    return jsonify(license_response(row))


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "autopilot-license-server", "version": "2.0"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
