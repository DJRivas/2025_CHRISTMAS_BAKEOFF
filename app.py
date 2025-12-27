"""Holiday Bakeoff 2025 app (Flask + Socket.IO).

Deploy note (Render):
This app uses Flask-SocketIO with the Eventlet worker for realtime updates.
Eventlet MUST be monkey-patched before importing Flask/OpenAI, otherwise
you can see errors like "Working outside of request context" during startup.
"""

# ---- Eventlet monkey patch (must be first) ----
import eventlet
eventlet.monkey_patch()

import io
import os
import json
import zipfile
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_socketio import SocketIO

from db import (
    init_db,
    connect,
    export_all,
    import_all,
    get_settings,
    set_setting,
    list_participants,
    upsert_participant,
    set_participant_active,
    delete_participant,
    get_desserts,
    upsert_dessert,
    list_scores,
    add_score,
    delete_score,
    compute_leaderboard,
    list_events,
    get_data_dir,
)

# Optional AI (requires OPENAI_API_KEY).
# Imported lazily to keep Eventlet startup stable.
def get_ai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # local import on purpose
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = bool(os.getenv("SESSION_COOKIE_SECURE", ""))

    return app


app = create_app()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=os.getenv("SOCKETIO_ASYNC", "eventlet"))

# Ensure DB exists
init_db()


def admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "changeme")


def is_admin() -> bool:
    return session.get("is_admin") is True


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return jsonify({"ok": False, "error": "admin_required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def broadcast_state():
    with connect() as conn:
        state = build_state(conn)
    socketio.emit("state", state)


def build_state(conn):
    settings = get_settings(conn)
    participants = list_participants(conn, include_inactive=True)
    desserts = get_desserts(conn)
    leaderboard = compute_leaderboard(conn)
    scores = list_scores(conn)
    events = list_events(conn, limit=60)
    return {
        "ok": True,
        "server_time": utc_now_iso(),
        "settings": settings,
        "participants": participants,
        "desserts": desserts,
        "leaderboard": leaderboard,
        "scores": scores,
        "events": events,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/admin")
def admin_page():
    if not is_admin():
        return redirect(url_for("login", next="/admin"))
    return render_template("admin.html")


@app.get("/login")
def login():
    return render_template("login.html", next=request.args.get("next", "/admin"))


@app.post("/login")
def login_post():
    password = (request.form.get("password") or "").strip()
    nxt = request.form.get("next") or "/admin"
    if password and password == admin_password():
        session["is_admin"] = True
        return redirect(nxt)
    return render_template("login.html", next=nxt, error="Wrong password")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/api/state")
def api_state():
    with connect() as conn:
        return jsonify(build_state(conn))


@app.post("/api/scores")
def api_add_score():
    data = request.get_json(force=True) or {}
    participant_id = int(data.get("participant_id") or 0)
    judge_name = (data.get("judge_name") or "").strip()
    criteria = data.get("criteria") or {}
    comment = (data.get("comment") or "").strip()

    try:
        with connect() as conn:
            score_id = add_score(conn, participant_id, judge_name, criteria, comment)
            state = build_state(conn)
        socketio.emit("toast", {"type": "success", "message": "Score saved 🎉"})
        socketio.emit("state", state)
        return jsonify({"ok": True, "score_id": score_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/admin/participants")
@require_admin
def api_admin_add_participant():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    active = bool(data.get("active", True))
    try:
        with connect() as conn:
            p = upsert_participant(conn, name, active=active)
            state = build_state(conn)
        socketio.emit("state", state)
        return jsonify({"ok": True, "participant": p})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/admin/participants/<int:participant_id>/active")
@require_admin
def api_admin_set_participant_active(participant_id: int):
    data = request.get_json(force=True) or {}
    active = bool(data.get("active", True))
    with connect() as conn:
        set_participant_active(conn, participant_id, active)
        state = build_state(conn)
    socketio.emit("state", state)
    return jsonify({"ok": True})


@app.delete("/api/admin/participants/<int:participant_id>")
@require_admin
def api_admin_delete_participant(participant_id: int):
    with connect() as conn:
        delete_participant(conn, participant_id)
        state = build_state(conn)
    socketio.emit("state", state)
    return jsonify({"ok": True})


@app.post("/api/admin/desserts")
@require_admin
def api_admin_upsert_dessert():
    data = request.get_json(force=True) or {}
    participant_id = int(data.get("participant_id") or 0)
    dessert_name = (data.get("dessert_name") or "").strip()
    description = (data.get("description") or "").strip()
    category = (data.get("category") or "").strip()
    try:
        with connect() as conn:
            upsert_dessert(conn, participant_id, dessert_name, description, category)
            state = build_state(conn)
        socketio.emit("state", state)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/admin/settings")
@require_admin
def api_admin_settings():
    data = request.get_json(force=True) or {}
    with connect() as conn:
        for k, v in data.items():
            set_setting(conn, k, v)
        state = build_state(conn)
    socketio.emit("state", state)
    return jsonify({"ok": True})


@app.delete("/api/admin/scores/<int:score_id>")
@require_admin
def api_admin_delete_score(score_id: int):
    with connect() as conn:
        delete_score(conn, score_id)
        state = build_state(conn)
    socketio.emit("state", state)
    return jsonify({"ok": True})


@app.get("/api/admin/export.json")
@require_admin
def api_admin_export_json():
    with connect() as conn:
        payload = export_all(conn)
    b = json.dumps(payload, indent=2).encode("utf-8")
    return send_file(
        io.BytesIO(b),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"bakeoff_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )


@app.post("/api/admin/import")
@require_admin
def api_admin_import_json():
    mode = request.args.get("mode", "replace")
    payload = request.get_json(force=True) or {}
    with connect() as conn:
        import_all(conn, payload, mode=mode)
        state = build_state(conn)
    socketio.emit("state", state)
    return jsonify({"ok": True})


@app.get("/api/admin/download-db")
@require_admin
def api_admin_download_db():
    path = os.path.join(get_data_dir(), "bakeoff.sqlite3")
    return send_file(path, as_attachment=True, download_name="bakeoff.sqlite3")


@app.post("/api/admin/backup")
@require_admin
def api_admin_create_backup():
    backups_dir = os.path.join(get_data_dir(), "backups")
    os.makedirs(backups_dir, exist_ok=True)
    with connect() as conn:
        payload = export_all(conn)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"backup_{ts}.json"
    fpath = os.path.join(backups_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return jsonify({"ok": True, "file": fname})


@app.get("/api/admin/backups")
@require_admin
def api_admin_list_backups():
    backups_dir = os.path.join(get_data_dir(), "backups")
    os.makedirs(backups_dir, exist_ok=True)
    files = []
    for fn in sorted(os.listdir(backups_dir), reverse=True):
        if fn.endswith(".json"):
            files.append(fn)
    return jsonify({"ok": True, "files": files})


@app.get("/api/admin/backups/<path:filename>")
@require_admin
def api_admin_get_backup(filename: str):
    backups_dir = os.path.join(get_data_dir(), "backups")
    fpath = os.path.join(backups_dir, filename)
    return send_file(fpath, as_attachment=True, download_name=filename)


@app.post("/api/ai/commentary")
def api_ai_commentary():
    """Generates festive commentary for the dashboard. Optional."""
    client = get_ai_client()
    if client is None:
        if not os.getenv("OPENAI_API_KEY"):
            return jsonify({"ok": False, "error": "OPENAI_API_KEY not set"}), 400
        return jsonify({"ok": False, "error": "OpenAI SDK failed to load"}), 500

    model = os.getenv("OPENAI_MODEL", "gpt-5")

    with connect() as conn:
        state = build_state(conn)

    top = state["leaderboard"][:5]
    prompt = (
        "You are the hype host for a friendly Holiday Bakeoff. "
        "Write 4-6 short lines of festive commentary (no cringe, no profanity), "
        "mentioning the top bakers by name and keeping it fun. "
        "Add 1 short emoji per line max.\n\n"
        f"Competition: {state['settings'].get('competition_name','Holiday Bakeoff')}\n"
        f"Top 5 (name, score): {[(t['name'], t.get('weighted_total',0)) for t in top]}"
    )

    try:
        resp = client.responses.create(
            model=model,
            input=[{"role": "user", "content": prompt}],
        )
        text = getattr(resp, "output_text", None) or "".join(
            [
                (item.get("content", "") if isinstance(item, dict) else "")
                for item in (getattr(resp, "output", []) or [])
            ]
        )
        return jsonify({"ok": True, "text": text.strip()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@socketio.on("connect")
def on_connect():
    with connect() as conn:
        socketio.emit("state", build_state(conn))


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=bool(os.getenv("DEBUG", "")))
