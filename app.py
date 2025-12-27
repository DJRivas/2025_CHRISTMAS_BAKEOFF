import os
os.environ.setdefault("EVENTLET_NO_GREENDNS", "yes")
import eventlet
eventlet.monkey_patch()

import json
from datetime import datetime, timezone
import re
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

# ---- Config ----
DATA_PATH = os.environ.get("DATA_PATH", "data.json")  # On Render, point this at your Disk mount (e.g. /data/data.json)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")  # optional: if set, /admin will prompt

DEFAULT_PARTICIPANTS = [
    {"id": "yesenia", "name": "Yesenia", "dessert": "—"},
    {"id": "bryan", "name": "Bryan", "dessert": "—"},
    {"id": "lindsay", "name": "Lindsay", "dessert": "—"},
    {"id": "javier", "name": "Javier", "dessert": "—"},
    {"id": "vivana", "name": "Vivana", "dessert": "—"},
    {"id": "bernie", "name": "Bernie", "dessert": "—"},
    {"id": "daniella", "name": "Daniella", "dessert": "—"},
    {"id": "rogelio", "name": "Rogelio", "dessert": "—"},
]

def _init_data():
    return {
        "participants": DEFAULT_PARTICIPANTS,
        "scores": [],  # list of {participantId, judge, taste, presentation, spirit, total, comments, createdAt}
        "meta": {"createdAt": datetime.now(timezone.utc).isoformat()},
    }

def load_data():
    if not os.path.exists(DATA_PATH):
        data = _init_data()
        save_data(data)
        return data
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    os.makedirs(os.path.dirname(DATA_PATH) or ".", exist_ok=True)
    tmp_path = DATA_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, DATA_PATH)

# ---- App ----
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "bakeoff-secret")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
def admin():
    # Admin password is optional; if set, the page will require it (handled in admin.js).
    return render_template("admin.html", require_password=bool(ADMIN_PASSWORD))

@app.route("/api/state")
def state():
    return jsonify(load_data())

@app.route("/api/participants", methods=["POST"])
def update_participants():
    data = load_data()
    participants = request.json or []
    # normalize / ensure ids
    norm = []
    for p in participants:
        pid = (p.get("id") or "").strip() or (p.get("name","").strip().lower().replace(" ", "-"))
        pid = re.sub(r"[^a-z0-9\-]+", "", pid)
        norm.append({
            "id": pid,
            "name": (p.get("name") or "").strip() or pid,
            "dessert": (p.get("dessert") or "").strip() or "—"
        })
    data["participants"] = norm
    save_data(data)
    socketio.emit("update", data)
    return jsonify(success=True)

@app.route("/api/score", methods=["POST"])
def submit_score():
    payload = request.json or {}
    data = load_data()

    participant_id = payload.get("participantId") or ""
    judge = (payload.get("judge") or "").strip()
    comments = (payload.get("comments") or "").strip()

    def clamp_int(x):
        try:
            x = int(float(x))
        except Exception:
            x = 0
        return max(1, min(10, x))

    taste = clamp_int(payload.get("taste"))
    presentation = clamp_int(payload.get("presentation"))
    spirit = clamp_int(payload.get("spirit"))
    total = round((taste + presentation + spirit) / 3.0, 2)

    # basic validation
    known_ids = {p["id"] for p in data.get("participants", [])}
    if participant_id not in known_ids:
        return jsonify(success=False, error="Unknown participant"), 400
    if not judge:
        return jsonify(success=False, error="Judge name required"), 400

    record = {
        "id": payload.get("id") or f"s_{int(datetime.now(timezone.utc).timestamp()*1000)}",
        "participantId": participant_id,
        "judge": judge,
        "taste": taste,
        "presentation": presentation,
        "spirit": spirit,
        "total": total,
        "comments": comments,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    data["scores"].append(record)
    save_data(data)
    socketio.emit("update", data)
    return jsonify(success=True, total=total)

@app.route("/api/admin/auth", methods=["POST"])
def admin_auth():
    # simple password check (optional)
    if not ADMIN_PASSWORD:
        return jsonify(success=True)
    payload = request.json or {}
    pw = payload.get("password") or ""
    return jsonify(success=(pw == ADMIN_PASSWORD))

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
