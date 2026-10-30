"""UAE Child Digital Safety Law, ahead of the January 2027 deadline: names private by default on
the leaderboards, parents' daily time limits, break reminders; plus sealed phone tokens and
log out by form only."""
from datetime import datetime, timedelta

import pytest

import app as A
import data
import db
import tokens
from conftest import TODAY, put_steps


# ------------------------------------------------------------- leaderboard names

def test_names_are_short_for_students_full_for_teachers(conn):
    s = data.create_user(conn, "stu1", "Amal Noor Khan", "student", "Grade 9A", "teen_13_17", "4826")
    t = data.create_user(conn, "tea1", "Sara Rossi", "teacher", "Science", "adult_18_39", "4826")
    put_steps(conn, s, TODAY, 5000)
    put_steps(conn, t, TODAY, 4000)
    assert [r["name"] for r in data.leaderboard(conn, "student", TODAY)] == ["Amal K."]
    assert [r["name"] for r in data.leaderboard(conn, "teacher", TODAY)] == ["Sara Rossi"]


def test_anyone_can_choose_and_hidden_still_counts_for_the_class(conn):
    a = data.create_user(conn, "amal1", "Amal Khan", "student", "Grade 9A", "teen_13_17", "4826")
    b = data.create_user(conn, "omar1", "Omar Saeed", "student", "Grade 9A", "teen_13_17", "4826")
    put_steps(conn, a, TODAY, 6000)
    put_steps(conn, b, TODAY, 2000)
    data.set_board_name(conn, a, "full")
    data.set_board_name(conn, b, "hidden")
    assert [r["name"] for r in data.leaderboard(conn, "student", TODAY)] == ["Amal Khan"]
    dept = data.leaderboard(conn, "department", TODAY)
    assert dept[0]["value"] == 4000                         # (6000 + 2000) / 2: Omar still counts
    with pytest.raises(ValueError):
        data.set_board_name(conn, a, "nickname")


def test_shown_name_rules():
    assert data.shown_name("Amal Khan", "short") == "Amal K."
    assert data.shown_name("Amal", "short") == "Amal"
    assert data.shown_name("Amal Khan", "hidden") == ""
    assert data.shown_name("Amal Khan", "full") == "Amal Khan"


@pytest.fixture()
def school(tmp_path):
    web = A.create_app()
    path = str(tmp_path / "s.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    ids = {"amal": data.create_user(conn, "amal", "Amal Khan", "student", "Grade 9A", "teen_13_17", "4826"),
           "omar": data.create_user(conn, "omar", "Omar Saeed", "student", "Grade 9A", "teen_13_17", "4826"),
           "kid": data.create_user(conn, "kid", "Kid Young", "student", "Grade 5A", "under_13", "4826"),
           "teacher": data.create_user(conn, "teach", "Sara Rossi", "teacher", "Science", "adult_18_39", "4826")}
    for uid in ids.values():
        data.save_steps(conn, uid, A.today(), 5000, "manual")
    conn.close()

    def client(uid):
        c = web.test_client()
        with c.session_transaction() as s:
            s["user_id"] = uid
            s["csrf"] = "x"
        return c
    return client, path, ids


def test_you_see_your_own_full_name_others_see_short(school):
    client, path, ids = school
    page = client(ids["amal"]).get("/leaderboard?view=student").get_data(as_text=True)
    assert "Amal Khan (you)" in page and "Omar S." in page and "Omar Saeed" not in page
    report = client(ids["amal"]).get(f'/report/{ids["omar"]}').get_data(as_text=True)
    assert "Omar S." in report and "Omar Saeed" not in report


def test_settings_change_the_board_name(school):
    client, path, ids = school
    c = client(ids["omar"])
    assert "Your name on the leaderboards" in c.get("/settings").get_data(as_text=True)
    c.post("/settings", data={"csrf": "x", "action": "board_name", "board_name": "full"})
    page = client(ids["amal"]).get("/leaderboard?view=student").get_data(as_text=True)
    assert "Omar Saeed" in page


# ------------------------------------------------------------- time limits and breaks

def test_screen_minutes_count_once_per_minute_and_old_days_go(conn):
    uid = data.create_user(conn, "kid1", "Kid One", "student", "Grade 5A", "under_13", "4826")
    t = datetime(2026, 10, 14, 16, 0, 5)
    conn.execute("INSERT INTO screen_time (user_id, date, minutes) VALUES (?, '2026-10-01', 40)", (uid,))
    assert data.note_screen_minute(conn, uid, t) == 1
    assert data.note_screen_minute(conn, uid, t + timedelta(seconds=30)) == 1     # same minute
    assert data.note_screen_minute(conn, uid, t + timedelta(minutes=1)) == 2
    assert conn.execute("SELECT COUNT(*) FROM screen_time WHERE user_id = ?", (uid,)).fetchone()[0] == 1
    data.set_time_limit(conn, uid, 0)                                             # no limit: no tracking
    assert conn.execute("SELECT COUNT(*) FROM screen_time").fetchone()[0] == 0
    with pytest.raises(ValueError):
        data.set_time_limit(conn, uid, 7)


def test_nobody_without_a_limit_is_tracked(school):
    client, path, ids = school
    client(ids["amal"]).get("/")
    assert db.connect(path).execute("SELECT COUNT(*) FROM screen_time").fetchone()[0] == 0


def test_times_up_page_once_the_limit_is_used(school):
    client, path, ids = school
    conn = db.connect(path)
    data.set_time_limit(conn, ids["kid"], 15)
    c = client(ids["kid"])
    assert "up for today" not in c.get("/").get_data(as_text=True)
    conn.execute("UPDATE screen_time SET minutes = 15, last_minute = 'xx' WHERE user_id = ?", (ids["kid"],))
    conn.commit()
    page = c.get("/leaderboard").get_data(as_text=True)
    assert "up for today" in page and "15 minutes" in page
    assert c.get("/ping").get_json()["over"] is True
    assert c.get("/privacy").status_code == 200 and "up for today" not in c.get("/privacy").get_data(as_text=True)


def test_parent_sets_limit_and_name(tmp_path, monkeypatch):
    web = A.create_app()
    path = str(tmp_path / "p.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    uid = data.create_user(conn, "kid", "Kid Young", "student", "Grade 5A", "under_13", "4826")
    conn.execute("UPDATE users SET parent_status = 'pending', parent_email = 'p@x.com' WHERE id = ?", (uid,))
    conn.commit()
    _, token = data.parent_request(conn, uid)
    data.parent_approve(conn, token)
    c = web.test_client()
    with c.session_transaction() as s:
        s["csrf"] = "x"
    page = c.get(f"/parent/{token}").get_data(as_text=True)
    assert "Parental controls" in page and "Daily time limit" in page
    c.post(f"/parent/{token}", data={"csrf": "x", "choice": "controls", "time_limit": "30", "board_name": "hidden"})
    kid = data.get_user(conn, uid)
    assert kid["time_limit"] == 30 and kid["board_name"] == "hidden"
    assert "settings for Kid Young are saved" in c.get(f"/parent/{token}?done=saved").get_data(as_text=True)


def test_break_reminder_only_for_under_18s(school):
    client, path, ids = school
    assert 'data-break-after="30"' in client(ids["amal"]).get("/").get_data(as_text=True)
    assert "data-break-after" not in client(ids["teacher"]).get("/").get_data(as_text=True)


# ------------------------------------------------------------- phone tokens and logging out

def test_tokens_are_sealed_and_still_work(school):
    client, path, ids = school
    conn = db.connect(path)
    stored = conn.execute("SELECT api_token, api_token_hash FROM users WHERE id = ?", (ids["amal"],)).fetchone()
    token = data.get_user(conn, ids["amal"])["api_token"]
    assert stored["api_token"].startswith(tokens.PREFIX) and token not in stored["api_token"]
    assert token not in stored["api_token_hash"]
    assert data.get_user_by_token(conn, token)["id"] == ids["amal"]
    assert data.get_user_by_token(conn, stored["api_token"]) is None      # the stored value is useless


def test_old_readable_tokens_are_sealed_without_changing(conn):
    uid = data.create_user(conn, "old1", "Old One", "student", "Grade 9A", "teen_13_17", "4826")
    conn.execute("UPDATE users SET api_token = 'old-readable-token', api_token_hash = NULL WHERE id = ?", (uid,))
    conn.commit()
    db.create_tables(conn)
    assert data.get_user_by_token(conn, "old-readable-token")["id"] == uid   # the phone keeps working
    assert conn.execute("SELECT api_token FROM users WHERE id = ?", (uid,)).fetchone()[0] != "old-readable-token"


def test_new_secret_key_means_new_tokens(conn, monkeypatch):
    uid = data.create_user(conn, "new1", "New Key", "student", "Grade 9A", "teen_13_17", "4826")
    old = data.get_user(conn, uid)["api_token"]
    monkeypatch.setenv("STRIDEBOARD_SECRET_KEY", "a-completely-different-secret")
    fresh = data.get_user(conn, uid)["api_token"]
    assert fresh and fresh != old and data.get_user_by_token(conn, fresh)["id"] == uid
    assert data.get_user_by_token(conn, old) is None


def test_a_link_cant_log_you_out(school):
    client, path, ids = school
    c = client(ids["amal"])
    assert c.get("/logout").headers["Location"].endswith("/settings")
    assert c.get("/").status_code == 200                                  # still logged in
    c.post("/logout", data={"csrf": "x"})
    assert "/login" in c.get("/").headers["Location"]


def test_settings_header_has_no_none_for_people_without_a_class(school):
    """Live bug (30 Oct): an admin with no class saw '@name · None' in the Settings header."""
    client, path, ids = school
    conn = db.connect(path)
    conn.execute("UPDATE users SET department = NULL WHERE id = ?", (ids["teacher"],))
    conn.commit()
    page = client(ids["teacher"]).get("/settings").get_data(as_text=True)
    assert "@teach · None" not in page and "@teach" in page
    assert "@amal · Grade 9A" in client(ids["amal"]).get("/settings").get_data(as_text=True)
