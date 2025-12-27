
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import json, os

app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet")

DATA_FILE = "data.json"

DEFAULT_PARTICIPANTS = [
    {"name": "Yesenia", "dessert": "TBD", "active": True},
    {"name": "Bryan", "dessert": "TBD", "active": True},
    {"name": "Lindsay", "dessert": "TBD", "active": True},
    {"name": "Javier", "dessert": "TBD", "active": True},
    {"name": "Vivana", "dessert": "TBD", "active": True},
    {"name": "Bernie", "dessert": "TBD", "active": True},
    {"name": "Daniella", "dessert": "TBD", "active": True},
    {"name": "Rogelio", "dessert": "TBD", "active": True},
]

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"participants": DEFAULT_PARTICIPANTS, "scores": []}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/api/state")
def state():
    return jsonify(load_data())

@app.route("/api/participants", methods=["POST"])
def update_participants():
    data = load_data()
    data["participants"] = request.json
    save_data(data)
    socketio.emit("update", data)
    return jsonify(success=True)

@app.route("/api/score", methods=["POST"])
def submit_score():
    data = load_data()
    data["scores"].append(request.json)
    save_data(data)
    socketio.emit("update", data)
    return jsonify(success=True)

if __name__ == "__main__":
    socketio.run(app)
