"""
test_app.py
===========
Comprehensive Pytest suite for the ACEest Fitness & Gym Flask application.

All tests run against an isolated in-memory SQLite database so that nothing
is written to disk and tests never interfere with each other.
"""

import json
import pytest
from app import create_app


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create a fresh Flask app backed by an in-memory SQLite database."""
    flask_app = create_app(db_name=":memory:")
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    """Return a test client for the Flask app."""
    return app.test_client()


@pytest.fixture
def member_payload():
    """A valid JSON payload for creating a member."""
    return {
        "name":      "Alice Johnson",
        "age":       28,
        "height_cm": 165.0,
        "weight_kg": 62.0,
        "program":   "Fat Loss",
        "membership": "Active",
        "expiry":    "2026-12-31",
    }


@pytest.fixture
def created_member(client, member_payload):
    """Helper: create a member and return the parsed JSON response."""
    resp = client.post(
        "/members",
        data=json.dumps(member_payload),
        content_type="application/json",
    )
    assert resp.status_code == 201
    return resp.get_json()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Health / Root endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthEndpoints:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_json_keys(self, client):
        data = client.get("/").get_json()
        assert "service" in data
        assert "status"  in data
        assert data["status"] == "running"

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_json_status(self, client):
        data = client.get("/health").get_json()
        assert data.get("status") == "healthy"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Member CRUD
# ─────────────────────────────────────────────────────────────────────────────

class TestMemberCreation:
    def test_create_member_success(self, client, member_payload):
        resp = client.post(
            "/members",
            data=json.dumps(member_payload),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id"   in data
        assert data["name"] == member_payload["name"]

    def test_create_member_auto_calories(self, client, member_payload):
        """Fat Loss factor = 22  →  62 * 22 = 1364 calories."""
        resp   = client.post("/members", data=json.dumps(member_payload),
                             content_type="application/json")
        data   = resp.get_json()
        assert data["calories"] == 1364          # 62 * 22

    def test_create_member_missing_name(self, client):
        resp = client.post(
            "/members",
            data=json.dumps({"age": 25}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_duplicate_member(self, client, member_payload):
        client.post("/members", data=json.dumps(member_payload),
                    content_type="application/json")
        resp = client.post("/members", data=json.dumps(member_payload),
                           content_type="application/json")
        assert resp.status_code == 409

    def test_create_member_no_body(self, client):
        resp = client.post("/members", content_type="application/json")
        assert resp.status_code == 400


class TestMemberRead:
    def test_get_all_members_empty(self, client):
        resp = client.get("/members")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_get_all_members_after_create(self, client, created_member):
        resp = client.get("/members")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1

    def test_get_member_by_id(self, client, created_member):
        member_id = created_member["id"]
        resp      = client.get(f"/members/{member_id}")
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Alice Johnson"

    def test_get_member_not_found(self, client):
        resp = client.get("/members/9999")
        assert resp.status_code == 404


class TestMemberUpdate:
    def test_update_member(self, client, created_member):
        mid  = created_member["id"]
        resp = client.put(
            f"/members/{mid}",
            data=json.dumps({"age": 30}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        # Verify the change persisted
        fetched = client.get(f"/members/{mid}").get_json()
        assert fetched["age"] == 30

    def test_update_nonexistent_member(self, client):
        resp = client.put(
            "/members/9999",
            data=json.dumps({"age": 30}),
            content_type="application/json",
        )
        assert resp.status_code == 404


class TestMemberDelete:
    def test_delete_member(self, client, created_member):
        mid  = created_member["id"]
        resp = client.delete(f"/members/{mid}")
        assert resp.status_code == 200
        # Should be gone
        assert client.get(f"/members/{mid}").status_code == 404

    def test_delete_nonexistent_member(self, client):
        resp = client.delete("/members/9999")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 3. Workouts
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkouts:
    def test_add_workout(self, client, created_member):
        mid  = created_member["id"]
        resp = client.post(
            f"/members/{mid}/workouts",
            data=json.dumps({
                "workout_type": "Strength",
                "duration_min": 60,
                "notes":        "Heavy compound lifts",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["member_id"] == mid

    def test_add_workout_missing_type(self, client, created_member):
        mid  = created_member["id"]
        resp = client.post(
            f"/members/{mid}/workouts",
            data=json.dumps({"duration_min": 45}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_add_workout_invalid_member(self, client):
        resp = client.post(
            "/members/9999/workouts",
            data=json.dumps({"workout_type": "Cardio"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_get_workouts_empty(self, client, created_member):
        mid  = created_member["id"]
        resp = client.get(f"/members/{mid}/workouts")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_get_workouts_after_add(self, client, created_member):
        mid = created_member["id"]
        client.post(
            f"/members/{mid}/workouts",
            data=json.dumps({"workout_type": "Cardio"}),
            content_type="application/json",
        )
        resp = client.get(f"/members/{mid}/workouts")
        assert len(resp.get_json()) == 1

    def test_multiple_workouts(self, client, created_member):
        mid = created_member["id"]
        for wtype in ("Strength", "Cardio", "HIIT"):
            client.post(
                f"/members/{mid}/workouts",
                data=json.dumps({"workout_type": wtype}),
                content_type="application/json",
            )
        resp = client.get(f"/members/{mid}/workouts")
        assert len(resp.get_json()) == 3


# ─────────────────────────────────────────────────────────────────────────────
# 4. Progress tracking
# ─────────────────────────────────────────────────────────────────────────────

class TestProgress:
    def test_add_progress(self, client, created_member):
        mid  = created_member["id"]
        resp = client.post(
            f"/members/{mid}/progress",
            data=json.dumps({"week": "2025-W01", "adherence_pct": 85}),
            content_type="application/json",
        )
        assert resp.status_code == 201

    def test_add_progress_missing_fields(self, client, created_member):
        mid  = created_member["id"]
        resp = client.post(
            f"/members/{mid}/progress",
            data=json.dumps({"week": "2025-W01"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_add_progress_out_of_range(self, client, created_member):
        mid  = created_member["id"]
        resp = client.post(
            f"/members/{mid}/progress",
            data=json.dumps({"week": "2025-W01", "adherence_pct": 150}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_get_progress(self, client, created_member):
        mid = created_member["id"]
        for week, pct in [("2025-W01", 80), ("2025-W02", 90)]:
            client.post(
                f"/members/{mid}/progress",
                data=json.dumps({"week": week, "adherence_pct": pct}),
                content_type="application/json",
            )
        resp = client.get(f"/members/{mid}/progress")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2

    def test_progress_invalid_member(self, client):
        resp = client.post(
            "/members/9999/progress",
            data=json.dumps({"week": "2025-W01", "adherence_pct": 80}),
            content_type="application/json",
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 5. Calorie calculator
# ─────────────────────────────────────────────────────────────────────────────

class TestCalorieCalculator:
    def test_fat_loss_calories(self, client):
        resp = client.post(
            "/calculate-calories",
            data=json.dumps({"weight_kg": 70, "program": "Fat Loss"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["calories"] == 70 * 22

    def test_muscle_gain_calories(self, client):
        resp = client.post(
            "/calculate-calories",
            data=json.dumps({"weight_kg": 80, "program": "Muscle Gain"}),
            content_type="application/json",
        )
        assert resp.get_json()["calories"] == 80 * 35

    def test_default_calories_unknown_program(self, client):
        """Unknown programs should fall back to factor 28."""
        resp = client.post(
            "/calculate-calories",
            data=json.dumps({"weight_kg": 70, "program": "Unknown"}),
            content_type="application/json",
        )
        assert resp.get_json()["calories"] == 70 * 28

    def test_calories_missing_weight(self, client):
        resp = client.post(
            "/calculate-calories",
            data=json.dumps({"program": "Fat Loss"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_beginner_calories(self, client):
        resp = client.post(
            "/calculate-calories",
            data=json.dumps({"weight_kg": 60, "program": "Beginner"}),
            content_type="application/json",
        )
        assert resp.get_json()["calories"] == 60 * 26


# ─────────────────────────────────────────────────────────────────────────────
# 6. BMI calculator
# ─────────────────────────────────────────────────────────────────────────────

class TestBMICalculator:
    def test_normal_bmi(self, client):
        resp = client.post(
            "/bmi",
            data=json.dumps({"weight_kg": 70, "height_cm": 175}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "bmi"      in data
        assert "category" in data
        assert data["category"] == "Normal weight"

    def test_underweight_bmi(self, client):
        resp = client.post(
            "/bmi",
            data=json.dumps({"weight_kg": 45, "height_cm": 175}),
            content_type="application/json",
        )
        assert resp.get_json()["category"] == "Underweight"

    def test_overweight_bmi(self, client):
        resp = client.post(
            "/bmi",
            data=json.dumps({"weight_kg": 85, "height_cm": 170}),
            content_type="application/json",
        )
        assert resp.get_json()["category"] == "Overweight"

    def test_obese_bmi(self, client):
        resp = client.post(
            "/bmi",
            data=json.dumps({"weight_kg": 120, "height_cm": 170}),
            content_type="application/json",
        )
        assert resp.get_json()["category"] == "Obese"

    def test_bmi_missing_fields(self, client):
        resp = client.post(
            "/bmi",
            data=json.dumps({"weight_kg": 70}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_bmi_zero_height(self, client):
        resp = client.post(
            "/bmi",
            data=json.dumps({"weight_kg": 70, "height_cm": 0}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_bmi_value_accuracy(self, client):
        """70 kg / (1.75 m)^2 = 22.86"""
        resp = client.post(
            "/bmi",
            data=json.dumps({"weight_kg": 70, "height_cm": 175}),
            content_type="application/json",
        )
        assert resp.get_json()["bmi"] == 22.86


# ─────────────────────────────────────────────────────────────────────────────
# 7. Membership status
# ─────────────────────────────────────────────────────────────────────────────

class TestMembership:
    def test_active_membership(self, client, created_member):
        mid  = created_member["id"]
        resp = client.get(f"/members/{mid}/membership")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is True      # expiry = 2026-12-31

    def test_membership_not_found(self, client):
        resp = client.get("/members/9999/membership")
        assert resp.status_code == 404

    def test_expired_membership(self, client):
        """Create a member with a past expiry date."""
        payload = {
            "name":   "Bob Expired",
            "expiry": "2020-01-01",
        }
        create_resp = client.post(
            "/members",
            data=json.dumps(payload),
            content_type="application/json",
        )
        mid  = create_resp.get_json()["id"]
        resp = client.get(f"/members/{mid}/membership")
        assert resp.get_json()["active"] is False
