"""Tests for POST /api/steps. 'Today' is Wednesday 2026-10-14 (Dubai)."""
import json
import logging

import pytest

import data
import db
from conftest import make_user


@pytest.fixture
def token(app):
    with app.app_context():
        conn = db.get_db()
        uid = make_user(conn, "sam")
        return data.get_user(conn, uid)["api_token"]


def post(client, body, **kwargs):
    if not isinstance(body, (str, bytes)):
        body = json.dumps(body, ensure_ascii=False)
    return client.post("/api/steps", data=body, content_type="application/json", **kwargs)


def stored_steps(app, day="2026-10-14"):
    with app.app_context():
        row = db.get_db().execute("SELECT steps, source FROM steps WHERE date = ?", (day,)).fetchone()
        return tuple(row) if row else None


def test_valid_upload(client, app, token):
    r = post(client, {"token": token, "date": "2026-10-14", "steps": 8423, "source": "ios_shortcut"})
    assert r.status_code == 200
    assert r.get_json() == {"ok": True, "weekly_total": 8423, "tier": "Bronze"}
    assert r.headers["Cache-Control"] == "no-store"
    assert stored_steps(app) == (8423, "ios_shortcut")


def test_yesterday_then_today_adds_up(client, token):
    post(client, {"token": token, "date": "2026-10-13", "steps": 30000, "source": "android_app"})
    r = post(client, {"token": token, "date": "2026-10-14", "steps": 6000, "source": "android_app"})
    assert r.get_json() == {"ok": True, "weekly_total": 36000, "tier": "Silver"}


def test_date_is_optional(client, app, token):
    assert post(client, {"token": token, "steps": 500, "source": "other"}).status_code == 200
    assert stored_steps(app) == (500, "other")


@pytest.mark.parametrize("steps, expected", [
    ("9,500.0", 9500), ("٨٤٢٣", 8423), (8423.6, 8424), ("  700 ", 700), (0, 0), (100000, 100000),
])
def test_accepted_step_formats(client, app, token, steps, expected):
    r = post(client, {"token": token, "steps": steps, "source": "manual"})
    assert r.status_code == 200, r.get_json()
    assert stored_steps(app)[0] == expected


@pytest.mark.parametrize("body_changes, message", [
    ({"date": "2026-10-15"}, "future"),
    ({"date": "2026-10-06"}, "more than 7 days"),        # 8 days ago
    ({"date": "14-10-2026"}, "YYYY-MM-DD"),
    ({"steps": -1}, "negative"),
    ({"steps": 100001}, "100,000"),
    ({"steps": "lots"}, "number"),
    ({"steps": None}, "required"),
    ({"source": "fitbit"}, "source"),
    ({"source": None}, "source"),
])
def test_bad_input_is_400(client, app, token, body_changes, message):
    body = {"token": token, "date": "2026-10-14", "steps": 8000, "source": "ios_shortcut"}
    body.update(body_changes)
    r = post(client, body)
    assert r.status_code == 400
    assert r.get_json()["ok"] is False
    assert message in r.get_json()["error"]
    assert stored_steps(app) is None


@pytest.mark.parametrize("token_value", ["wrong-token", "", None, 12345])
def test_bad_token_is_401(client, token, token_value):
    r = post(client, {"token": token_value, "steps": 8000, "source": "ios_shortcut"})
    assert r.status_code == 401
    assert r.get_json() == {"ok": False, "error": "invalid token"}


def test_missing_token_is_401(client, token):
    r = post(client, {"steps": 8000, "source": "ios_shortcut"})
    assert r.status_code == 401


def test_bad_token_checked_before_other_errors(client):
    r = post(client, {"token": "nope", "steps": -5, "source": "x"})
    assert r.status_code == 401


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", "", "\"text\"", b"\xff\xfe"])
def test_body_not_json_object(client, raw):
    r = post(client, raw)
    assert r.status_code == 400
    assert "JSON" in r.get_json()["error"]


def test_body_over_16_kb_is_413(client, token):
    body = json.dumps({"token": token, "steps": 1, "source": "manual", "pad": "x" * 17000})
    r = post(client, body)
    assert r.status_code == 413
    assert r.get_json()["ok"] is False


def test_get_not_allowed(client):
    assert client.get("/api/steps").status_code == 405


def test_badges_given_through_api(client, app, token):
    post(client, {"token": token, "steps": 12000, "source": "ios_shortcut"})
    with app.app_context():
        keys = {r[0] for r in db.get_db().execute("SELECT badge_key FROM badges")}
    assert keys == {"first_log", "ten_k"}


def test_token_never_in_logs_or_errors(client, token, caplog):
    caplog.set_level(logging.DEBUG)
    r = post(client, {"token": token, "steps": -1, "source": "manual"})
    assert token not in r.get_data(as_text=True)
    assert token not in caplog.text


# ---------- the Flask commands added by db.init_app ----------

def test_cli_commands(app, token):
    runner = app.test_cli_runner()
    assert "Database ready" in runner.invoke(args=["init-db"]).output
    assert runner.invoke(args=["show-token", "SAM"]).output.strip() == token
    missing = runner.invoke(args=["show-token", "nobody"])
    assert missing.exit_code != 0 and "No user" in missing.output
    assert "Goals updated" in runner.invoke(args=["update-goals"]).output


def test_first_request_of_week_updates_goals(client, app):
    with app.app_context():
        assert data._get_meta(db.get_db(), "goals_updated_week") is None
    client.get("/api/steps")                       # any request triggers the weekly check
    with app.app_context():
        assert data._get_meta(db.get_db(), "goals_updated_week") == "2026-10-12"
