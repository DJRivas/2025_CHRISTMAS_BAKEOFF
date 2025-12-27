import os
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DEFAULT_CRITERIA = [
    {"key": "taste", "label": "Taste", "max": 10, "weight": 1.0},
    {"key": "presentation", "label": "Presentation", "max": 10, "weight": 1.0},
    {"key": "creativity", "label": "Creativity", "max": 10, "weight": 1.0},
    {"key": "holiday_spirit", "label": "Holiday Spirit", "max": 10, "weight": 1.0},
]

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_data_dir() -> str:
    # Render disk: set DATA_DIR=/var/data (or any mounted path)
    return os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data"))

def db_path() -> str:
    os.makedirs(get_data_dir(), exist_ok=True)
    return os.path.join(get_data_dir(), "bakeoff.sqlite3")

@contextmanager
def connect():
    path = db_path()
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with connect() as conn:
        conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS desserts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id INTEGER NOT NULL,
                dessert_name TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
                UNIQUE(participant_id)
            );

            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id INTEGER NOT NULL,
                judge_name TEXT NOT NULL,
                criteria_json TEXT NOT NULL,
                comment TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                k TEXT PRIMARY KEY,
                v TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            '''
        )

        if conn.execute("SELECT COUNT(*) AS c FROM settings").fetchone()["c"] == 0:
            set_setting(conn, "competition_name", "2025 Holiday Bakeoff")
            set_setting(conn, "theme", "christmas")
            set_setting(conn, "criteria", DEFAULT_CRITERIA)
            set_setting(conn, "voting_open", True)
            set_setting(conn, "allow_multiple_scores_per_judge", False)


def _coerce_bool(v: str) -> bool:
    return v.lower().strip() in ("1", "true", "yes", "y", "on")


def get_settings(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT k,v FROM settings").fetchall()
    out = {}
    for r in rows:
        k, v = r["k"], r["v"]
        if k in ("voting_open", "allow_multiple_scores_per_judge"):
            out[k] = _coerce_bool(v)
        elif k in ("criteria",):
            try:
                out[k] = json.loads(v)
            except Exception:
                out[k] = DEFAULT_CRITERIA
        else:
            out[k] = v
    return out


def set_setting(conn: sqlite3.Connection, k: str, v) -> None:
    if isinstance(v, (dict, list)):
        v = json.dumps(v)
    elif isinstance(v, bool):
        v = "true" if v else "false"
    else:
        v = str(v)
    conn.execute(
        "INSERT INTO settings (k,v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (k, v),
    )


def add_event(conn: sqlite3.Connection, event_type: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO events (event_type, payload_json, created_at) VALUES (?,?,?)",
        (event_type, json.dumps(payload), utc_now_iso()),
    )


def list_events(conn: sqlite3.Connection, limit: int = 50) -> list:
    rows = conn.execute(
        "SELECT id, event_type, payload_json, created_at FROM events ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "type": r["event_type"],
                "payload": json.loads(r["payload_json"]),
                "created_at": r["created_at"],
            }
        )
    return out

def list_participants(conn: sqlite3.Connection, include_inactive: bool = True) -> list:
    if include_inactive:
        rows = conn.execute("SELECT * FROM participants ORDER BY active DESC, name ASC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM participants WHERE active=1 ORDER BY name ASC").fetchall()
    return [dict(r) for r in rows]


def upsert_participant(conn: sqlite3.Connection, name: str, active: bool = True) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Participant name required.")
    now = utc_now_iso()
    try:
        conn.execute(
            "INSERT INTO participants (name, active, created_at) VALUES (?,?,?)",
            (name, 1 if active else 0, now),
        )
        add_event(conn, "participant_added", {"name": name})
    except sqlite3.IntegrityError:
        conn.execute("UPDATE participants SET active=? WHERE name=?", (1 if active else 0, name))
        add_event(conn, "participant_updated", {"name": name, "active": active})
    row = conn.execute("SELECT * FROM participants WHERE name=?", (name,)).fetchone()
    return dict(row)


def set_participant_active(conn: sqlite3.Connection, participant_id: int, active: bool) -> None:
    conn.execute("UPDATE participants SET active=? WHERE id=?", (1 if active else 0, participant_id))
    row = conn.execute("SELECT name FROM participants WHERE id=?", (participant_id,)).fetchone()
    add_event(conn, "participant_updated", {"id": participant_id, "name": row["name"] if row else None, "active": active})


def delete_participant(conn: sqlite3.Connection, participant_id: int) -> None:
    row = conn.execute("SELECT name FROM participants WHERE id=?", (participant_id,)).fetchone()
    conn.execute("DELETE FROM participants WHERE id=?", (participant_id,))
    add_event(conn, "participant_deleted", {"id": participant_id, "name": row["name"] if row else None})

def get_desserts(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        '''
        SELECT d.id, d.participant_id, p.name as participant_name, d.dessert_name, d.description, d.category, d.created_at
        FROM desserts d
        JOIN participants p ON p.id = d.participant_id
        ORDER BY p.active DESC, p.name ASC
        '''
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_dessert(conn: sqlite3.Connection, participant_id: int, dessert_name: str, description: str = "", category: str = "") -> None:
    dessert_name = (dessert_name or "").strip()
    if not dessert_name:
        raise ValueError("Dessert name required.")
    description = (description or "").strip()
    category = (category or "").strip()
    now = utc_now_iso()
    conn.execute(
        '''
        INSERT INTO desserts (participant_id, dessert_name, description, category, created_at)
        VALUES (?,?,?,?,?)
        ON CONFLICT(participant_id) DO UPDATE SET
            dessert_name=excluded.dessert_name,
            description=excluded.description,
            category=excluded.category
        ''',
        (participant_id, dessert_name, description, category, now),
    )
    add_event(conn, "dessert_upserted", {"participant_id": participant_id, "dessert_name": dessert_name})

def list_scores(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        '''
        SELECT s.id, s.participant_id, p.name as participant_name, s.judge_name, s.criteria_json, s.comment, s.created_at
        FROM scores s
        JOIN participants p ON p.id = s.participant_id
        ORDER BY s.id DESC
        '''
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["criteria"] = json.loads(d.pop("criteria_json"))
        out.append(d)
    return out


def judge_has_scored(conn: sqlite3.Connection, judge_name: str, participant_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM scores WHERE judge_name=? AND participant_id=? LIMIT 1",
        (judge_name, participant_id),
    ).fetchone()
    return row is not None


def add_score(conn: sqlite3.Connection, participant_id: int, judge_name: str, criteria: dict, comment: str = "") -> int:
    judge_name = (judge_name or "").strip()
    if not judge_name:
        raise ValueError("Judge name required.")
    comment = (comment or "").strip()

    settings = get_settings(conn)
    if not settings.get("voting_open", True):
        raise ValueError("Voting is currently closed.")
    if not settings.get("allow_multiple_scores_per_judge", False):
        if judge_has_scored(conn, judge_name, participant_id):
            raise ValueError("You already scored this participant.")

    criteria_json = json.dumps(criteria)
    now = utc_now_iso()
    cur = conn.execute(
        "INSERT INTO scores (participant_id, judge_name, criteria_json, comment, created_at) VALUES (?,?,?,?,?)",
        (participant_id, judge_name, criteria_json, comment, now),
    )
    score_id = int(cur.lastrowid)
    add_event(conn, "score_added", {"participant_id": participant_id, "judge_name": judge_name, "score_id": score_id})
    return score_id


def delete_score(conn: sqlite3.Connection, score_id: int) -> None:
    row = conn.execute("SELECT participant_id, judge_name FROM scores WHERE id=?", (score_id,)).fetchone()
    conn.execute("DELETE FROM scores WHERE id=?", (score_id,))
    add_event(conn, "score_deleted", {"score_id": score_id, "participant_id": row["participant_id"] if row else None, "judge_name": row["judge_name"] if row else None})

def judge_has_scored(conn: sqlite3.Connection, judge_name: str, participant_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM scores WHERE judge_name=? AND participant_id=? LIMIT 1",
        (judge_name, participant_id),
    ).fetchone()
    return row is not None


def add_score(conn: sqlite3.Connection, participant_id: int, judge_name: str, criteria: dict, comment: str = "") -> int:
    judge_name = (judge_name or "").strip()
    if not judge_name:
        raise ValueError("Judge name required.")
    comment = (comment or "").strip()

    settings = get_settings(conn)
    if not settings.get("voting_open", True):
        raise ValueError("Voting is currently closed.")
    if not settings.get("allow_multiple_scores_per_judge", False):
        if judge_has_scored(conn, judge_name, participant_id):
            raise ValueError("You already scored this participant.")

    criteria_json = json.dumps(criteria)
    now = utc_now_iso()
    cur = conn.execute(
        "INSERT INTO scores (participant_id, judge_name, criteria_json, comment, created_at) VALUES (?,?,?,?,?)",
        (participant_id, judge_name, criteria_json, comment, now),
    )
    score_id = int(cur.lastrowid)
    add_event(conn, "score_added", {"participant_id": participant_id, "judge_name": judge_name, "score_id": score_id})
    return score_id


def delete_score(conn: sqlite3.Connection, score_id: int) -> None:
    row = conn.execute("SELECT participant_id, judge_name FROM scores WHERE id=?", (score_id,)).fetchone()
    conn.execute("DELETE FROM scores WHERE id=?", (score_id,))
    add_event(conn, "score_deleted", {"score_id": score_id, "participant_id": row["participant_id"] if row else None, "judge_name": row["judge_name"] if row else None})


def compute_leaderboard(conn: sqlite3.Connection) -> list:
    settings = get_settings(conn)
    criteria_cfg = settings.get("criteria") or DEFAULT_CRITERIA
    weights = {c["key"]: float(c.get("weight", 1.0)) for c in criteria_cfg}

    participants = list_participants(conn, include_inactive=True)
    scores = list_scores(conn)

    by_pid = {
        p["id"]: {
            "participant_id": p["id"],
            "name": p["name"],
            "active": bool(p["active"]),
            "num_scores": 0,
            "totals": {},
            "weighted_total": 0.0,
        }
        for p in participants
    }

    for s in scores:
        pid = s["participant_id"]
        if pid not in by_pid:
            continue
        by_pid[pid]["num_scores"] += 1
        crit = s.get("criteria") or {}
        for k, v in crit.items():
            by_pid[pid]["totals"][k] = by_pid[pid]["totals"].get(k, 0.0) + float(v)

    for pid, row in by_pid.items():
        n = row["num_scores"]
        if n <= 0:
            continue
        weighted = 0.0
        for k, total in row["totals"].items():
            avg = total / n
            weighted += avg * weights.get(k, 1.0)
        row["weighted_total"] = round(weighted, 3)

    leaderboard = sorted(
        by_pid.values(),
        key=lambda r: (r["active"], r["weighted_total"], r["num_scores"]),
        reverse=True,
    )
    return leaderboard

def export_all(conn: sqlite3.Connection) -> dict:
    return {
        "exported_at": utc_now_iso(),
        "participants": list_participants(conn, include_inactive=True),
        "desserts": get_desserts(conn),
        "scores": list_scores(conn),
        "settings": get_settings(conn),
        "events": list_events(conn, limit=500),
    }


def import_all(conn: sqlite3.Connection, payload: dict, mode: str = "replace") -> None:
    if mode not in ("replace", "merge"):
        mode = "replace"

    if mode == "replace":
        conn.executescript(
            """
            DELETE FROM scores;
            DELETE FROM desserts;
            DELETE FROM participants;
            DELETE FROM settings;
            DELETE FROM events;
            """
        )

    settings = payload.get("settings") or {}
    for k, v in settings.items():
        set_setting(conn, k, v)

    for p in payload.get("participants") or []:
        upsert_participant(conn, p.get("name", ""), active=bool(p.get("active", 1)))

    name_to_id = {p["name"]: p["id"] for p in list_participants(conn, include_inactive=True)}

    for d in payload.get("desserts") or []:
        pid = d.get("participant_id")
        if pid is None:
            pid = name_to_id.get(d.get("participant_name", ""))
        if pid:
            upsert_dessert(conn, int(pid), d.get("dessert_name", ""), d.get("description", ""), d.get("category", ""))

    for s in payload.get("scores") or []:
        pid = s.get("participant_id")
        if pid is None:
            pid = name_to_id.get(s.get("participant_name", ""))
        if pid:
            try:
                add_score(conn, int(pid), s.get("judge_name", ""), s.get("criteria", {}) or {}, s.get("comment", ""))
            except Exception:
                pass

    add_event(conn, "import_completed", {"mode": mode})
