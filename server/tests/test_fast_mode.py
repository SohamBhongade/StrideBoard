"""Settings > Appearance > Fast mode: a cookie on this device that turns effects off."""
import pytest

import data


@pytest.fixture()
def client(tmp_path):
    import app as A
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


def test_off_by_default(client):
    page = client.get("/").data.decode()
    assert " fast " not in page and 'class="' in page
    assert 'aria-label="Fast mode"' in client.get("/settings").data.decode()


def test_turning_it_on_and_off(client):
    r = client.post("/settings", data={"csrf": "x", "action": "fast", "fast": "1"})
    assert r.status_code == 302 and "fast=1" in r.headers["Set-Cookie"]
    page = client.get("/").data.decode()
    assert "fast lite no-intro" in page
    assert 'aria-checked="true"' in client.get("/settings").data.decode()
    client.post("/settings", data={"csrf": "x", "action": "fast", "fast": "0"})
    assert "fast lite" not in client.get("/").data.decode()
