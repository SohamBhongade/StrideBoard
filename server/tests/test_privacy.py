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
    monkeypatch.setattr(A.config, "SIGNUP_OPEN", True)
    page = site.get("/signup").get_data(as_text=True)
    assert 'name="agree_terms"' in page and 'name="agree_privacy"' in page and 'href="/privacy"' in page
    assert "checked" not in page.split('name="agree_terms"')[1].split(">")[0]      # never pre-ticked
    with site.session_transaction() as s:
        s["csrf"] = "x"
    r = site.post("/signup", data={"csrf": "x", "role": "student", "display_name": "Amal Khan", "class": "Grade 10A",
                                   "age_band": "teen_13_17", "email": "amal@example.com", "pin": "4826",
                                   "pin_again": "4826", "code": A.config.JOIN_CODE})
    assert "agree to the terms of use" in r.get_data(as_text=True)


# ------------------------------------------------------------- Your data (Settings)

import data  # noqa: E402
from datetime import datetime  # noqa: E402


@pytest.fixture()
def me(tmp_path):
    web = A.create_app()
    path = str(tmp_path / "me.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    uid = data.create_user(conn, "amal", "Amal Khan", "student", "Grade 10A", "teen_13_17", "4826")
    other = data.create_user(conn, "omar", "Omar Saeed", "student", "Grade 10A", "teen_13_17", "1357")
    data.save_steps(conn, uid, A.today(), 4321, "manual")
    data.save_steps(conn, other, A.today(), 9999, "manual")
    conn.close()
    c = web.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["csrf"] = "x"
    return c, path, uid


def test_settings_has_your_data_section(me):
    c, _, _ = me
    page = c.get("/settings").get_data(as_text=True)
    for bit in ("Your data and privacy", "Save my details", "Download my data", "Delete my account", 'href="/privacy"'):
        assert bit in page


def test_download_my_data(me):
    c, _, _ = me
    r = c.get("/settings/my-data.json")
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    body = r.get_json()
    assert body["account"]["display_name"] == "Amal Khan"
    assert [d["steps"] for d in body["steps"]] == [4321]                       # only mine
    for secret in ("pin_hash", "email_hash", "api_token"):
        assert secret not in body["account"]


def test_download_needs_login(tmp_path):
    web = A.create_app()
    web.config.update(TESTING=True, DATABASE=str(tmp_path / "x.sqlite3"))
    assert web.test_client().get("/settings/my-data.json").status_code == 302


def test_correct_my_details(me):
    c, path, uid = me
    c.post("/settings", data={"csrf": "x", "action": "my_details", "display_name": "Amal  Khan Ali",
                              "department": "Grade 11B"})
    conn = db.connect(path)
    row = conn.execute("SELECT display_name, department FROM users WHERE id = ?", (uid,)).fetchone()
    assert (row["display_name"], row["department"]) == ("Amal Khan Ali", "Grade 11B")
    c.post("/settings", data={"csrf": "x", "action": "my_details", "display_name": "Omar Saeed",
                              "department": "Grade 11B"})                      # taken
    assert conn.execute("SELECT display_name FROM users WHERE id = ?", (uid,)).fetchone()[0] == "Amal Khan Ali"
    c.post("/settings", data={"csrf": "x", "action": "my_details", "display_name": "Amal",
                              "department": "Made Up Class"})                  # not on the list
    assert conn.execute("SELECT department FROM users WHERE id = ?", (uid,)).fetchone()[0] == "Grade 11B"


def test_delete_my_account(me):
    c, path, uid = me
    c.post("/settings", data={"csrf": "x", "action": "delete_me", "pin": "0000", "confirm": "1"})
    conn = db.connect(path)
    assert conn.execute("SELECT 1 FROM users WHERE id = ?", (uid,)).fetchone()     # wrong PIN: kept
    c.post("/settings", data={"csrf": "x", "action": "delete_me", "pin": "4826"})
    assert conn.execute("SELECT 1 FROM users WHERE id = ?", (uid,)).fetchone()     # no confirm tick: kept
    r = c.post("/settings", data={"csrf": "x", "action": "delete_me", "pin": "4826", "confirm": "1"})
    assert "/logout" in r.headers["Location"]
    assert conn.execute("SELECT 1 FROM users WHERE id = ?", (uid,)).fetchone() is None
    assert conn.execute("SELECT COUNT(*) FROM steps WHERE user_id = ?", (uid,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1           # Omar untouched


def test_owner_cannot_delete_self(tmp_path):
    path = str(tmp_path / "o.sqlite3")
    conn = db.connect(path)
    db.create_tables(conn)
    uid = data.create_user(conn, A.config.OWNER_USERNAME, "Owner", "admin", None, "adult_18_39", "4826")
    with pytest.raises(ValueError, match="owner"):
        data.delete_my_account(conn, uid, "4826")


def test_logged_out_after_30_idle_days(me):
    c, _, _ = me
    with c.session_transaction() as s:
        s["seen"] = int(datetime.now().timestamp()) - 31 * 86400
    r = c.get("/settings")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_privacy_page_lists_rights_and_transfer(site):
    page = site.get("/privacy").get_data(as_text=True)
    assert "Your rights" in page and "outside the UAE" in page and "Data protection contact" in page


def test_pages_block_outside_code(me):
    c, _, _ = me
    for url in ("/", "/insights", "/settings", "/leaderboard", "/privacy"):
        r = c.get(url)
        csp = r.headers.get("Content-Security-Policy", "")
        assert "script-src 'self'" in csp and "connect-src 'self'" in csp
        assert "https://" not in r.get_data(as_text=True).split("<script")[1:][0][:200] if "<script src" in r.get_data(as_text=True) else True
        assert "cdn.jsdelivr" not in r.get_data(as_text=True)


def test_privacy_page_health_connect_disclosures(site):
    page = site.get("/privacy").get_data(as_text=True)
    for bit in ("Android Health Connect", "Limited Use", "Health Connect Permissions Policy", "AES-256", "Agree &amp; Connect"):
        assert bit in page


def test_arabic_privacy_page(site):
    page = site.get("/privacy?lang=ar").get_data(as_text=True)
    assert 'dir="rtl"' in page and "حقوقك" in page and "الاستخدام المحدود" in page
    assert 'href="/privacy"' in page                       # back to English
    assert "privacy?lang=ar" in site.get("/privacy").get_data(as_text=True)


def test_download_steps_csv(me):
    c, _, _ = me
    r = c.get("/settings/my-steps.csv")
    lines = r.get_data(as_text=True).strip().splitlines()
    assert r.mimetype == "text/csv" and lines[0] == "date,steps,source,updated_at"
    assert len(lines) == 2 and ",4321," in lines[1]


# ------------------------------------------------------------- security audit fixes

def test_back_link_never_leaves_the_site():
    for bad in ("//evil.com", "/\\\\evil.com", "/\\evil.com", "https://evil.com", "javascript:alert(1)", "", "/x\nLocation: y"):
        assert A.safe_back(bad) is None
    assert A.safe_back("/leaderboard?view=teacher") == "/leaderboard?view=teacher"


def test_token_only_in_the_android_app(me):
    c, path, uid = me
    token = db.connect(path).execute("SELECT api_token FROM users WHERE id = ?", (uid,)).fetchone()[0]
    android_chrome = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36"
    assert token not in c.get("/", headers={"User-Agent": android_chrome}).get_data(as_text=True)
    iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) Safari/604.1"
    assert token in c.get("/", headers={"User-Agent": iphone}).get_data(as_text=True)   # Shortcut button
    page = c.get("/", headers={"User-Agent": "Mozilla/5.0 StrideBoardAndroid/1.0 StrideBoardApp/6"}).get_data(as_text=True)
    assert token in page


def test_wrong_pins_from_one_address_are_throttled(site):
    A.FAILED_BY_ADDRESS.clear(); A.FAILED_LOGINS.clear()
    with site.session_transaction() as s:
        s["csrf"] = "x"
    for i in range(A.ADDRESS_TRIES):
        site.post("/login", data={"csrf": "x", "username": f"Person {i}", "pin": "1234"})
    page = site.post("/login", data={"csrf": "x", "username": "Someone Else", "pin": "1234"}).get_data(as_text=True)
    assert "Too many wrong PINs" in page
    A.FAILED_BY_ADDRESS.clear(); A.FAILED_LOGINS.clear()


def test_secure_cookie_and_hsts_on_https(me):
    c, _, _ = me
    r = c.get("/settings", base_url="https://localhost")
    assert "max-age" in r.headers.get("Strict-Transport-Security", "")
    assert r.headers.get("X-Frame-Options") == "SAMEORIGIN"
    with c.session_transaction() as s:
        s["seen"] = 1
    r = c.get("/settings", base_url="https://localhost")
    cookie = r.headers.get("Set-Cookie", "")
    assert "Secure" in cookie or cookie == ""


def test_refuses_public_secret_key_on_pythonanywhere(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHONANYWHERE_DOMAIN", "pythonanywhere.com")
    monkeypatch.setattr(A.config, "SECRET_KEY", "dev-only-not-secret-change-me")
    import flask
    app = flask.Flask("x")
    app.config["DATABASE"] = str(tmp_path / "k.sqlite3")
    with pytest.raises(RuntimeError):
        db.init_app(app)
