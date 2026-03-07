"""
ACEest Fitness & Gym Management - Flask Web Application
A fitness management API built for the DevOps CI/CD assignment.
"""

from flask import Flask, jsonify, request, g
import sqlite3
import os
from datetime import date

# ─────────────────────────────────────────────────────────────────────────────
# Application Factory
# ─────────────────────────────────────────────────────────────────────────────

DB_NAME = os.environ.get("DB_NAME", "aceest_fitness.db")


def create_app(db_name: str = None) -> Flask:
    """
    Application factory.  Accepts an optional db_name so tests can inject
    an in-memory SQLite database without touching the real file.

    For in-memory databases (":memory:") we keep a single persistent
    connection on the app object so that all requests share the same
    in-memory schema.
    """
    app = Flask(__name__)
    app.config["DB_NAME"] = db_name or DB_NAME

    # ── If using in-memory SQLite, keep one persistent connection ────────────
    if app.config["DB_NAME"] == ":memory:":
        _mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
        _mem_conn.row_factory = sqlite3.Row
        app.config["_MEM_CONN"] = _mem_conn
        _init_db_conn(_mem_conn)
    else:
        _init_db(app.config["DB_NAME"])

    # ── Register blueprints / routes ─────────────────────────────────────────
    _register_routes(app)

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Database helpers
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS members (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    age           INTEGER,
    height_cm     REAL,
    weight_kg     REAL,
    program       TEXT,
    calories      INTEGER,
    membership    TEXT    DEFAULT 'Active',
    expiry        TEXT
);

CREATE TABLE IF NOT EXISTS workouts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id     INTEGER NOT NULL REFERENCES members(id),
    date          TEXT    NOT NULL,
    workout_type  TEXT    NOT NULL,
    duration_min  INTEGER,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS progress (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id     INTEGER NOT NULL REFERENCES members(id),
    week          TEXT    NOT NULL,
    adherence_pct INTEGER NOT NULL
);
"""


def _init_db_conn(conn: sqlite3.Connection) -> None:
    """Apply schema to an already-open connection."""
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


def _init_db(db_name: str) -> None:
    """Open a file-backed SQLite database and apply schema."""
    conn = sqlite3.connect(db_name)
    _init_db_conn(conn)
    conn.close()


def _get_conn(app: Flask) -> sqlite3.Connection:
    """
    Return a database connection appropriate for the current request.

    - In-memory mode: reuse the single persistent connection stored on app.
    - File mode: open a fresh per-request connection.
    """
    if "_MEM_CONN" in app.config:
        return app.config["_MEM_CONN"]

    # Per-request connection for file-backed databases (stored on flask.g)
    if "_db_conn" not in g:
        conn = sqlite3.connect(app.config["DB_NAME"])
        conn.row_factory = sqlite3.Row
        g._db_conn = conn
    return g._db_conn


# ─────────────────────────────────────────────────────────────────────────────
# Route registration
# ─────────────────────────────────────────────────────────────────────────────

def _register_routes(app: Flask) -> None:

    # ── Tear-down: close per-request file connection ──────────────────────
    @app.teardown_appcontext
    def close_db(exc=None):
        conn = g.pop("_db_conn", None)
        if conn is not None:
            conn.close()

    # ── Health check ─────────────────────────────────────────────────────────

    @app.route("/", methods=["GET"])
    def index():
        """Root health-check endpoint."""
        return jsonify({
            "service": "ACEest Fitness & Gym Management",
            "version": "1.0.0",
            "status": "running"
        }), 200

    @app.route("/health", methods=["GET"])
    def health():
        """Detailed health-check used by Docker / Kubernetes probes."""
        return jsonify({"status": "healthy"}), 200

    # ── Members ───────────────────────────────────────────────────────────────

    @app.route("/members", methods=["GET"])
    def get_members():
        """Return all members."""
        conn = _get_conn(app)
        rows = conn.execute("SELECT * FROM members ORDER BY name").fetchall()
        return jsonify([dict(r) for r in rows]), 200

    @app.route("/members/<int:member_id>", methods=["GET"])
    def get_member(member_id: int):
        """Return a single member by ID."""
        conn = _get_conn(app)
        row = conn.execute(
            "SELECT * FROM members WHERE id = ?", (member_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Member not found"}), 404
        return jsonify(dict(row)), 200

    @app.route("/members", methods=["POST"])
    def add_member():
        """
        Create a new member.
        Expects JSON: { name, age?, height_cm?, weight_kg?, program?,
                        membership?, expiry? }
        """
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400

        age        = data.get("age")
        height_cm  = data.get("height_cm")
        weight_kg  = data.get("weight_kg")
        program    = data.get("program", "")
        membership = data.get("membership", "Active")
        expiry     = data.get("expiry", "")

        # Auto-calculate calories when weight is provided
        CALORIE_FACTORS = {
            "Fat Loss":    22,
            "Muscle Gain": 35,
            "Beginner":    26,
        }
        calories = None
        if weight_kg:
            factor   = CALORIE_FACTORS.get(program, 28)
            calories = int(float(weight_kg) * factor)

        conn = _get_conn(app)
        try:
            cur = conn.execute(
                """
                INSERT INTO members
                    (name, age, height_cm, weight_kg, program,
                     calories, membership, expiry)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (name, age, height_cm, weight_kg, program,
                 calories, membership, expiry),
            )
            conn.commit()
            member_id = cur.lastrowid
        except sqlite3.IntegrityError:
            return jsonify({"error": f"Member '{name}' already exists"}), 409

        return jsonify({"id": member_id, "name": name, "calories": calories}), 201

    @app.route("/members/<int:member_id>", methods=["PUT"])
    def update_member(member_id: int):
        """Update an existing member's details."""
        data = request.get_json(silent=True) or {}

        conn = _get_conn(app)
        row = conn.execute(
            "SELECT * FROM members WHERE id = ?", (member_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Member not found"}), 404

        current = dict(row)
        name       = data.get("name",       current["name"])
        age        = data.get("age",        current["age"])
        height_cm  = data.get("height_cm",  current["height_cm"])
        weight_kg  = data.get("weight_kg",  current["weight_kg"])
        program    = data.get("program",    current["program"])
        membership = data.get("membership", current["membership"])
        expiry     = data.get("expiry",     current["expiry"])

        conn.execute(
            """
            UPDATE members
            SET name=?, age=?, height_cm=?, weight_kg=?,
                program=?, membership=?, expiry=?
            WHERE id=?
            """,
            (name, age, height_cm, weight_kg, program,
             membership, expiry, member_id),
        )
        conn.commit()
        return jsonify({"message": "Member updated", "id": member_id}), 200

    @app.route("/members/<int:member_id>", methods=["DELETE"])
    def delete_member(member_id: int):
        """Delete a member and all associated records."""
        conn = _get_conn(app)
        row = conn.execute(
            "SELECT id FROM members WHERE id = ?", (member_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Member not found"}), 404

        conn.execute("DELETE FROM workouts WHERE member_id = ?", (member_id,))
        conn.execute("DELETE FROM progress  WHERE member_id = ?", (member_id,))
        conn.execute("DELETE FROM members   WHERE id        = ?", (member_id,))
        conn.commit()
        return jsonify({"message": "Member deleted"}), 200

    # ── Workouts ──────────────────────────────────────────────────────────────

    @app.route("/members/<int:member_id>/workouts", methods=["GET"])
    def get_workouts(member_id: int):
        """Return all workouts for a member."""
        conn = _get_conn(app)
        rows = conn.execute(
            "SELECT * FROM workouts WHERE member_id=? ORDER BY date DESC",
            (member_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows]), 200

    @app.route("/members/<int:member_id>/workouts", methods=["POST"])
    def add_workout(member_id: int):
        """
        Log a workout session for a member.
        Expects JSON: { date?, workout_type, duration_min?, notes? }
        """
        data = request.get_json(silent=True) or {}
        workout_type = (data.get("workout_type") or "").strip()
        if not workout_type:
            return jsonify({"error": "workout_type is required"}), 400

        session_date = data.get("date", date.today().isoformat())
        duration_min = data.get("duration_min", 60)
        notes        = data.get("notes", "")

        conn = _get_conn(app)
        if not conn.execute(
            "SELECT id FROM members WHERE id=?", (member_id,)
        ).fetchone():
            return jsonify({"error": "Member not found"}), 404

        cur = conn.execute(
            """
            INSERT INTO workouts (member_id, date, workout_type, duration_min, notes)
            VALUES (?,?,?,?,?)
            """,
            (member_id, session_date, workout_type, duration_min, notes),
        )
        conn.commit()
        return jsonify({"id": cur.lastrowid, "member_id": member_id}), 201

    # ── Progress ──────────────────────────────────────────────────────────────

    @app.route("/members/<int:member_id>/progress", methods=["GET"])
    def get_progress(member_id: int):
        """Return weekly adherence progress for a member."""
        conn = _get_conn(app)
        rows = conn.execute(
            "SELECT * FROM progress WHERE member_id=? ORDER BY week",
            (member_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows]), 200

    @app.route("/members/<int:member_id>/progress", methods=["POST"])
    def add_progress(member_id: int):
        """
        Record weekly adherence.
        Expects JSON: { week, adherence_pct }
        """
        data = request.get_json(silent=True) or {}
        week          = (data.get("week") or "").strip()
        adherence_pct = data.get("adherence_pct")

        if not week or adherence_pct is None:
            return jsonify({"error": "week and adherence_pct are required"}), 400

        if not (0 <= int(adherence_pct) <= 100):
            return jsonify({"error": "adherence_pct must be between 0 and 100"}), 400

        conn = _get_conn(app)
        if not conn.execute(
            "SELECT id FROM members WHERE id=?", (member_id,)
        ).fetchone():
            return jsonify({"error": "Member not found"}), 404

        cur = conn.execute(
            "INSERT INTO progress (member_id, week, adherence_pct) VALUES (?,?,?)",
            (member_id, week, int(adherence_pct)),
        )
        conn.commit()
        return jsonify({"id": cur.lastrowid, "member_id": member_id}), 201

    # ── Calorie calculator ────────────────────────────────────────────────────

    @app.route("/calculate-calories", methods=["POST"])
    def calculate_calories():
        """
        Standalone calorie estimator.
        Expects JSON: { weight_kg, program }
        Returns recommended daily calorie intake.
        """
        data = request.get_json(silent=True) or {}
        weight_kg = data.get("weight_kg")
        program   = data.get("program", "")

        if weight_kg is None:
            return jsonify({"error": "weight_kg is required"}), 400

        CALORIE_FACTORS = {
            "Fat Loss":    22,
            "Muscle Gain": 35,
            "Beginner":    26,
        }
        factor   = CALORIE_FACTORS.get(program, 28)
        calories = int(float(weight_kg) * factor)
        return jsonify({
            "weight_kg": weight_kg,
            "program":   program,
            "calories":  calories,
        }), 200

    # ── BMI ───────────────────────────────────────────────────────────────────

    @app.route("/bmi", methods=["POST"])
    def calculate_bmi():
        """
        Compute BMI.
        Expects JSON: { weight_kg, height_cm }
        """
        data      = request.get_json(silent=True) or {}
        weight_kg = data.get("weight_kg")
        height_cm = data.get("height_cm")

        if weight_kg is None or height_cm is None:
            return jsonify({"error": "weight_kg and height_cm are required"}), 400

        if float(height_cm) <= 0:
            return jsonify({"error": "height_cm must be greater than 0"}), 400

        bmi = round(float(weight_kg) / ((float(height_cm) / 100) ** 2), 2)

        if bmi < 18.5:
            category = "Underweight"
        elif bmi < 25.0:
            category = "Normal weight"
        elif bmi < 30.0:
            category = "Overweight"
        else:
            category = "Obese"

        return jsonify({
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "bmi":       bmi,
            "category":  category,
        }), 200

    # ── Membership status ─────────────────────────────────────────────────────

    @app.route("/members/<int:member_id>/membership", methods=["GET"])
    def membership_status(member_id: int):
        """Check if a member's membership is still active."""
        conn = _get_conn(app)
        row  = conn.execute(
            "SELECT name, membership, expiry FROM members WHERE id=?",
            (member_id,),
        ).fetchone()

        if row is None:
            return jsonify({"error": "Member not found"}), 404

        today  = date.today().isoformat()
        expiry = row["expiry"] or ""
        active = (expiry >= today) if expiry else (row["membership"] == "Active")

        return jsonify({
            "member_id": member_id,
            "name":      row["name"],
            "membership": row["membership"],
            "expiry":    expiry,
            "active":    active,
        }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Entry-point
# ─────────────────────────────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
