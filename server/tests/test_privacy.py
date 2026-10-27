"""The privacy policy and terms page, and agreeing to it at sign-up."""
import pytest

import app as A
import db


@pytest.fixture()
def site(tmp_path):
    web = A.create_app()
    path = str(tmp_path / "web.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    conn.close()
    return web.test_client()


def test_privacy_page_is_open_to_everyone(site):
    r = site.get("/privacy")
    page = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "What we never collect" in page and "Terms of use" in page and "PythonAnywhere" in page


def test_login_page_links_to_it(site):
    assert 'href="/privacy"' in site.get("/login").get_data(as_text=True)


def test_signup_needs_agreement(site, monkeypatch):
    monkeypatch.setattr(A.mailer, "ready", lambda: True)
    page = site.get("/signup").get_data(as_text=True)
    assert 'name="agree"' in page and 'href="/privacy"' in page
    with site.session_transaction() as s:
        s["csrf"] = "x"
    r = site.post("/signup", data={"csrf": "x", "role": "student", "display_name": "Amal Khan", "class": "Grade 10A",
                                   "age_band": "teen_13_17", "email": "amal@example.com", "pin": "4826",
                                   "pin_again": "4826", "code": A.config.JOIN_CODE})
    assert "agree to the privacy policy" in r.get_data(as_text=True)
