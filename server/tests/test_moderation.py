"""Owner-only moderation: time out, ban, unban, rename, remove a day's steps."""
from datetime import datetime, timedelta

import pytest

import data
import db
from conftest import TODAY, make_user, put_steps

NOW = "2026-10-14T10:00:00+04:00"


def test_timeout_blocks_then_ends(conn):
    uid = make_user(conn)
    until = data.block_user(conn, uid, "1h", "Fake steps", now=NOW)
    assert until == "2026-10-14T11:00:00+04:00"
    assert data.block_status(conn, uid, now="2026-10-14T10:30:00+04:00") == {"until": until, "reason": "Fake steps"}
    assert data.block_status(conn, uid, now="2026-10-14T11:00:01+04:00") is None


def test_ban_until_unban(conn):
    uid = make_user(conn)
    assert data.block_user(conn, uid, "ban", "", now=NOW) is None
    assert data.block_status(conn, uid)["until"] is None
    assert [b["id"] for b in data.blocked_people(conn)] == [uid]
    data.unblock_user(conn, uid)
    assert data.block_status(conn, uid) is None and data.blocked_people(conn) == []


def test_cannot_block_yourself_or_pick_a_bad_length(conn):
    boss = make_user(conn, "boss", role="admin", department=None)
    with pytest.raises(ValueError, match="your own account"):
        data.block_user(conn, boss, "ban", "", acting_id=boss)
    with pytest.raises(ValueError, match="choose"):
        data.block_user(conn, make_user(conn, "kid"), "1y", "")


def test_blocked_people_leave_the_leaderboards(conn):
    a, b = make_user(conn, "aaa"), make_user(conn, "bbb")
    put_steps(conn, a, TODAY, 9000)
    put_steps(conn, b, TODAY, 5000)
    data.block_user(conn, a, "ban", "")
    names = [r["user_id"] for r in data.leaderboard(conn, "student", TODAY)]
    assert names == [b]
    dept = data.leaderboard(conn, "department", TODAY)
    assert dept[0]["value"] == 5000          # the banned person's steps don't count either


def test_find_rename_and_remove_steps(conn):
    uid = make_user(conn, "rude1", display_name="Rude Name")
    make_user(conn, "taken", display_name="Amal Khan")
    assert data.find_person(conn, "  rude   NAME ") == uid and data.find_person(conn, "RUDE1") == uid
    with pytest.raises(ValueError, match="already uses"):
        data.rename_person(conn, uid, "amal khan")
    data.rename_person(conn, uid, "Sam Lee")
    assert data.get_user(conn, uid)["display_name"] == "Sam Lee"
    put_steps(conn, uid, TODAY, 99999)
    assert data.remove_steps(conn, uid, str(TODAY)) == 99999
    with pytest.raises(ValueError, match="no steps"):
        data.remove_steps(conn, uid, str(TODAY))


def test_rename_leaves_a_notice_until_ok(conn):
    uid = make_user(conn, "kid9", display_name="Silly Name")
    data.rename_person(conn, uid, "Sam Lee")
    data.rename_person(conn, uid, "Sam Lee Two")          # renamed twice: still shows the original
    assert data.get_user(conn, uid)["rename_notice"] == "Silly Name"
    data.dismiss_rename_notice(conn, uid)
    assert data.get_user(conn, uid)["rename_notice"] is None


def test_delete_people_erases_everything_and_blocks_their_email(conn):
    secret = "s"
    boss = make_user(conn, "boss", role="admin", department=None)
    a, b = make_user(conn, "alt1", display_name="Alt One"), make_user(conn, "alt2", display_name="Alt Two")
    conn.execute("UPDATE users SET email_hash = ? WHERE id = ?", (data.email_fingerprint("alt@gmail.com", secret), a))
    put_steps(conn, a, TODAY, 5000)
    conn.commit()
    assert data.delete_people(conn, [a, b, str(b)], acting_id=boss) == ["Alt One", "Alt Two"]
    assert data.get_user(conn, a) is None and data.get_user(conn, b) is None
    assert conn.execute("SELECT COUNT(*) FROM steps WHERE user_id = ?", (a,)).fetchone()[0] == 0
    with pytest.raises(ValueError, match="can't be used"):
        data.start_signup(conn, secret, "a.l.t+2@googlemail.com", "Alt Again", "student", "Grade 9A",
                          "teen_13_17", "1234", "1234")
    with pytest.raises(ValueError, match="your own"):
        data.delete_people(conn, [boss], acting_id=boss)
