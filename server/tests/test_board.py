"""The leaderboard screen (/board): both boards, only with the screen code."""
import pytest

import app as A
import data
import db


@pytest.fixture()
def site(tmp_path):
    web = A.create_app()
    path = str(tmp_path / "web.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    t = A.today()
    s = data.create_user(conn, "student01", "Amal Khan", "student", "Grade 9A", "teen_13_17", "1234")
    te = data.create_user(conn, "teacher01", "Ms Rossi", "teacher", "Science", "adult_18_39", "1234")
    data.save_steps(conn, s, t, 9000, "manual")
    data.save_steps(conn, te, t, 7000, "manual")
    key = data.board_key(conn)
    conn.close()
    return web.test_client(), key, path


def test_screen_needs_the_code(site):
    c, key, _ = site
    assert c.get("/board").status_code == 403
    r = c.get("/board?key=WRONG12345")
    assert r.status_code == 403 and b"didn't work" in r.data and b"Amal" not in r.data


def test_screen_shows_students_and_teachers(site):
    c, key, _ = site
    page = c.get(f"/board?key={key.lower()}").get_data(as_text=True)     # not fussy about capitals
    assert "Students" in page and "Teachers" in page and "Amal Khan" in page and "Ms Rossi" in page
    assert "9,000" in page and "7,000" in page


def test_new_code_replaces_the_old_one(site):
    c, key, path = site
    conn = db.connect(path)
    new = data.board_key(conn, renew=True)
    conn.close()
    assert new != key and len(new) == 10
    assert c.get(f"/board?key={key}").status_code == 403 and c.get(f"/board?key={new}").status_code == 200


def test_admin_page_shows_the_screen_card(site):
    c, key, path = site
    conn = db.connect(path)
    boss = data.create_user(conn, "soham.admin", "Soham B", "admin", None, "adult_18_39", "2468")
    conn.close()
    with c.session_transaction() as s:
        s["user_id"] = boss
    page = c.get("/admin")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Leaderboard screen" in html and key in html and "Make a new code" in html
    assert "Today" in html and "This week" in html and "Last sync" in html
