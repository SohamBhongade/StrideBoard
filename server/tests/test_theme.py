"""Settings > Appearance: Light, Dark or Automatic, remembered in a cookie."""
import pytest


@pytest.fixture()
def client(tmp_path):
    """The real website, using a fresh database in a temporary folder."""
    import app as A
    import data
    import db
    web = A.create_app()
    path = str(tmp_path / "web.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    uid = data.create_user(conn, "sam", "Sam Lee", "student", "Grade 9A", "teen_13_17", "1234")
    conn.close()
    c = web.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["csrf"] = "x"
    return c


def test_default_is_light(client):
    assert b'data-theme="light"' in client.get("/settings").data


@pytest.mark.parametrize("choice", ["dark", "auto", "light"])
def test_choosing_a_theme_sets_the_cookie_and_page(client, choice):
    r = client.post("/settings", data={"csrf": "x", "action": "theme", "theme": choice})
    assert r.status_code == 302 and f"theme={choice}" in r.headers["Set-Cookie"]
    assert f'data-theme="{choice}"'.encode() in client.get("/").data


def test_bad_choice_is_ignored(client):
    r = client.post("/settings", data={"csrf": "x", "action": "theme", "theme": "neon"}, follow_redirects=True)
    assert b"Light, Dark or Automatic" in r.data
    client.set_cookie("theme", "neon")
    assert b'data-theme="light"' in client.get("/").data


def test_iphone_shortcut_is_offered_and_downloads(client):
    page = client.get("/settings").data
    assert b'href="/iphone-shortcut"' in page
    r = client.get("/iphone-shortcut")
    assert r.status_code == 200 and r.data[:4] == b"AEA1"          # Apple-signed file
    assert "Strideboard.shortcut" in r.headers["Content-Disposition"]
