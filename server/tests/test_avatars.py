"""Avatars: an emoji + colour per user, some unlocked by badges."""
import sqlite3

import pytest

import data
import db
from conftest import TODAY, make_user, put_steps


def test_new_user_has_no_avatar(conn):
    uid = make_user(conn, "amy")
    user = data.get_user(conn, uid)
    assert user["avatar"] is None and user["avatar_color"] is None


def test_free_avatars_unlocked_badge_ones_locked(conn):
    uid = make_user(conn, "amy")
    options = {o["key"]: o for o in data.avatar_options(conn, uid)}
    assert options["fox"]["unlocked"] and options["fox"]["emoji"] == "🦊"
    assert not options["crown"]["unlocked"]
    assert options["crown"]["badge_name"] == "Platinum Walker"


def test_set_free_avatar(conn):
    uid = make_user(conn, "amy")
    data.set_avatar(conn, uid, "panda", "mint")
    user = data.get_user(conn, uid)
    assert (user["avatar"], user["avatar_color"]) == ("panda", "mint")


def test_locked_avatar_needs_its_badge(conn):
    uid = make_user(conn, "amy")
    with pytest.raises(ValueError, match="10K Club"):
        data.set_avatar(conn, uid, "star", "gold")
    data.save_steps(conn, uid, TODAY.isoformat(), 12000, "manual")   # earns ten_k
    data.set_avatar(conn, uid, "star", "gold")
    assert data.get_user(conn, uid)["avatar"] == "star"


@pytest.mark.parametrize("avatar, color", [("dragon", "mint"), ("fox", "rainbow"), (None, None),
                                           ("<script>", "mint")])
def test_bad_avatar_or_colour_rejected(conn, avatar, color):
    uid = make_user(conn, "amy")
    with pytest.raises(ValueError):
        data.set_avatar(conn, uid, avatar, color)


def test_leaderboard_rows_carry_avatar(conn):
    uid = make_user(conn, "amy")
    data.set_avatar(conn, uid, "owl", "peri")
    put_steps(conn, uid, TODAY, 5000)
    row = data.leaderboard(conn, "student", TODAY)[0]
    assert (row["avatar"], row["avatar_color"]) == ("owl", "peri")
    dept = data.leaderboard(conn, "department", TODAY)[0]
    assert dept["avatar"] is None


def test_old_database_gets_avatar_columns(tmp_path):
    """The live server's database was made before avatars existed."""
    path = tmp_path / "old.sqlite3"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, "
                "display_name TEXT NOT NULL, pin_hash TEXT NOT NULL, role TEXT NOT NULL, "
                "department TEXT, age_band TEXT NOT NULL DEFAULT 'adult_18_39', "
                "api_token TEXT UNIQUE NOT NULL, daily_goal INTEGER NOT NULL, "
                "goal_is_custom INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)")
    old.execute("INSERT INTO users VALUES (1, 'kim', 'Kim', 'x', 'student', 'Grade 10A', "
                "'teen_13_17', 'tok', 10000, 0, '2026-10-01T08:00:00+04:00')")
    old.commit()
    old.close()

    conn = db.connect(path)
    db.create_tables(conn)
    db.create_tables(conn)                     # running twice is safe
    user = data.get_user(conn, 1)
    assert user["username"] == "kim" and user["avatar"] is None   # data kept
    data.set_avatar(conn, 1, "fox", "blue")
    assert data.get_user(conn, 1)["avatar"] == "fox"
    conn.close()
