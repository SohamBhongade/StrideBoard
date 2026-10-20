"""Database connection helpers and Flask setup.

Agent 3's app.py only needs:  import db;  db.init_app(app)
That closes connections after each request, creates missing tables, runs the
weekly goal update, and adds these commands:
    flask init-db              create missing tables (never deletes data)
    flask show-token USERNAME  print a user's phone token (for testing)
    flask update-goals         recompute adaptive goals now
"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import click
from flask import current_app, g
from flask.cli import with_appcontext

import config

DUBAI = ZoneInfo(config.TIMEZONE)
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
log = logging.getLogger(__name__)


def local_today():
    """Today's date in Dubai. Never use date.today(): servers often run in UTC."""
    return datetime.now(DUBAI).date()


def local_now_iso():
    """Current Dubai time as text, e.g. '2026-10-14T21:30:00+04:00'."""
    return datetime.now(DUBAI).isoformat(timespec="seconds")


def connect(path=None):
    """Open the SQLite file with foreign keys on and rows that work like dicts."""
    path = str(path or config.DATABASE)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after the first release. CREATE TABLE IF NOT EXISTS does not
# change a table that already exists, so older databases get them here.
ADDED_COLUMNS = {"users": ["avatar TEXT", "avatar_color TEXT", "email_hash TEXT"]}


def create_tables(conn):
    """Create any missing tables and columns. Safe to run again: it never drops data."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    for table, columns in ADDED_COLUMNS.items():
        have = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column in columns:
            if column.split()[0] not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column}")  # fixed names, no user input
    # One account per email address (people made by an admin have none, which is fine).
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email_hash)")
    conn.commit()


def get_db():
    """One connection per web request, closed automatically afterwards."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# The week (its Monday) for which this worker already checked goals,
# so we only touch the database once per week per worker.
_goals_checked_for = None


def _weekly_goal_check():
    """Before each request: if goals were not updated yet this week, do it now.

    The free PythonAnywhere plan has no scheduled tasks, so the first visit of
    each week does the Monday goal update instead.
    """
    global _goals_checked_for
    import calc
    import data  # imported here to avoid a circular import

    monday = calc.week_bounds(local_today())[0]
    if _goals_checked_for == monday:
        return
    try:
        data.maybe_update_goals(get_db(), local_today())
        _goals_checked_for = monday
    except Exception:  # never break a page because of the goal update
        log.exception("weekly goal update failed")


def init_app(app):
    """Connect the database to a Flask app. Call once in app.py."""
    app.config.setdefault("DATABASE", config.DATABASE)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = config.SECRET_KEY

    conn = connect(app.config["DATABASE"])
    create_tables(conn)
    conn.close()

    app.teardown_appcontext(close_db)
    app.before_request(_weekly_goal_check)
    app.cli.add_command(init_db_command)
    app.cli.add_command(show_token_command)
    app.cli.add_command(update_goals_command)


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create missing tables (never deletes data)."""
    create_tables(get_db())
    click.echo(f"Database ready: {current_app.config['DATABASE']}")


@click.command("show-token")
@click.argument("username")
@with_appcontext
def show_token_command(username):
    """Print a user's phone token. For testing only: the token is a password."""
    row = get_db().execute(
        "SELECT api_token FROM users WHERE username = ?", (username.strip().lower(),)
    ).fetchone()
    if row is None:
        raise click.ClickException(f"No user called {username!r}")
    click.echo(row["api_token"])


@click.command("update-goals")
@with_appcontext
def update_goals_command():
    """Recompute adaptive daily goals now."""
    import data

    changed = data.update_weekly_goals(get_db(), local_today())
    click.echo(f"Goals updated for {changed} user(s).")
