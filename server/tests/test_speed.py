"""Speed changes must not change what people see: big boards trim to the top 50 + you."""
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
    today = A.today()
    ids = []
    for i in range(60):                                   # 60 students, most steps first
        uid = data.create_user(conn, f"student{i:02d}", f"Student {i:02d} Test", "student", "Grade 9A",
                               "teen_13_17", "1234")
        data.save_steps(conn, uid, today, 20000 - i * 100, "manual")
        ids.append(uid)
    conn.close()
    c = web.test_client()

    def login(uid):
        with c.session_transaction() as s:
            s["user_id"] = uid
            s["csrf"] = "x"
    return c, ids, login


def test_big_board_shows_top_50_and_you(site):
    c, ids, login = site
    login(ids[57])                                        # rank 58
    page = c.get("/leaderboard?view=student").get_data(as_text=True)
    assert page.count("title=\"Report Student T.\"") == 50
    assert "Student 57 Test (you)" in page and ">58<" in page
    assert "Show everyone (60)" in page


def test_show_everyone_lists_all(site):
    c, ids, login = site
    login(ids[0])
    page = c.get("/leaderboard?view=student&all=1").get_data(as_text=True)
    assert page.count("title=\"Report Student T.\"") == 59 and "Show top 50" in page and "Show everyone" not in page


def test_in_top_50_no_extra_row(site):
    c, ids, login = site
    login(ids[3])
    page = c.get("/leaderboard?view=student").get_data(as_text=True)
    assert page.count("(you)") == 1 and "rank-gap" not in page


def test_old_address_sends_everyone_to_the_new_one(monkeypatch):
    import config
    monkeypatch.setattr(config, "MOVED_TO", "https://strideboard.pythonanywhere.com")
    c = A.create_app().test_client()
    r = c.get("/leaderboard?view=effort")
    assert r.status_code == 301
    assert r.headers["Location"] == "https://strideboard.pythonanywhere.com/leaderboard?view=effort"
    assert c.get("/").headers["Location"] == "https://strideboard.pythonanywhere.com/"
    api = c.post("/api/steps", json={"token": "x", "steps": 1})
    assert api.status_code == 410 and "moved to strideboard.pythonanywhere.com" in api.get_json()["message"]


def test_admin_people_shows_50_then_everyone_or_search(tmp_path):
    """A full school is 1,000+ rows: the Admin page shows the first 50 unless asked."""
    import app as A
    import db
    path = str(tmp_path / "big.sqlite3")
    conn = db.connect(path)
    db.create_tables(conn)
    from werkzeug.security import generate_password_hash
    pin = generate_password_hash("4826")
    ids = [data._insert_user(conn, f"kid{i:03d}", f"Kid{i:03d} Walker", "student", "Grade 9A", "teen_13_17", pin)
           for i in range(120)]
    admin = data._insert_user(conn, "boss", "Boss Admin", "admin", None, "adult_18_39", pin)
    conn.commit()
    web = A.create_app()
    web.config.update(TESTING=True, DATABASE=path)
    c = web.test_client()
    with c.session_transaction() as s:
        s["user_id"], s["csrf"] = admin, "x"
    page = c.get("/admin").get_data(as_text=True)
    assert page.count('<tr data-search=') == 50 and "Showing the first 50 of 121" in page
    assert 'data-people-partial="1"' in page
    everyone = c.get("/admin?show=all").get_data(as_text=True)
    assert everyone.count('data-search="kid') == 120 and "Showing the first" not in everyone
    found = c.get("/admin?q=Kid117").get_data(as_text=True)                  # search covers everyone
    assert found.count('data-search="kid') == 1 and "Kid117 Walker" in found
    assert len(page) < len(everyone)
