"""Sign-up closed (the default): no new accounts, but existing people still log in."""
import pytest

import app as A
import data
import db


@pytest.fixture()
def site(tmp_path, monkeypatch):
    monkeypatch.setattr(A.mailer, "ready", lambda: True)
    web = A.create_app()
    path = str(tmp_path / "web.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    data.create_user(conn, "amal", "Amal Khan", "student", "Grade 10A", "teen_13_17", "4826")
    conn.close()
    return web.test_client()


def test_closed_by_default():
    assert A.config.SIGNUP_OPEN is False


def test_signup_page_says_closed(site):
    page = site.get("/signup").get_data(as_text=True)
    assert "Sign-up is closed" in page and 'name="email"' not in page


def test_signup_post_is_refused(site):
    with site.session_transaction() as s:
        s["csrf"] = "x"
    site.post("/signup", data={"csrf": "x", "agree": "1", "role": "student", "display_name": "New Person",
                               "class": "Grade 10A", "age_band": "teen_13_17", "email": "new@example.com",
                               "pin": "4826", "pin_again": "4826"})
    path = db.connect(site.application.config["DATABASE"])
    assert path.execute("SELECT COUNT(*) FROM pending_signups").fetchone()[0] == 0
    assert path.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_verify_step_is_closed_too(site):
    with site.session_transaction() as s:
        s["signup_id"] = 1
    r = site.get("/signup/verify")
    assert r.status_code == 302 and r.headers["Location"].endswith("/signup")


def test_login_still_works_and_hides_create_link(site):
    page = site.get("/login").get_data(as_text=True)
    assert "Sign-up is closed" in page and "Create an account" not in page
    with site.session_transaction() as s:
        s["csrf"] = "x"
    r = site.post("/login", data={"csrf": "x", "username": "Amal Khan", "pin": "4826"})
    assert r.status_code == 302 and "/login" not in r.headers["Location"]
