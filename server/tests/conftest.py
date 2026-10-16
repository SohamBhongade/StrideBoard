"""Shared test setup.

Every test uses its own temporary database and a FIXED "today"
(Wednesday 2026-10-14), so tests pass on any day and in any timezone.
"""
import sys
from datetime import date
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

import api  # noqa: E402
import data  # noqa: E402
import db  # noqa: E402

TODAY = date(2026, 10, 14)  # a Wednesday; its week is Mon 12 Oct - Sun 18 Oct


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    """Make 'today' always 2026-10-14 everywhere in the server code."""
    monkeypatch.setattr(db, "local_today", lambda: TODAY)
    monkeypatch.setattr(data, "local_today", lambda: TODAY)
    monkeypatch.setattr(db, "_goals_checked_for", None)
    return TODAY


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.sqlite3")
    db.create_tables(connection)
    yield connection
    connection.close()


@pytest.fixture
def app(tmp_path):
    """A tiny Flask app with only the database and the API (no web pages)."""
    from flask import Flask

    flask_app = Flask(__name__)
    flask_app.config.update(TESTING=True, DATABASE=str(tmp_path / "app.sqlite3"))
    db.init_app(flask_app)
    flask_app.register_blueprint(api.bp)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(conn, username="sam", role="student", department="Grade 10A",
              age_band="teen_13_17", pin="1234", display_name=None):
    """Helper: create a user and return their id."""
    return data.create_user(conn, username, display_name or username.title(),
                            role, department, age_band, pin)


def put_steps(conn, user_id, day, steps, source="manual", updated_at=None):
    """Helper: write steps for any date (skips the 7-day rule)."""
    data._write_steps(conn, user_id, str(day), steps, source, updated_at)
    conn.commit()
