"""Home page notice for older Android apps."""
import pytest

import config
import data

BROWSER = "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/141 Mobile Safari/537.36"
OLD_APP = BROWSER + " StrideBoardAndroid/1.0"
NEW = config.ANDROID_APP_LATEST["code"]


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


def home(client, ua):
    return client.get("/", headers={"User-Agent": ua}).data.decode()


def test_no_notice_in_a_browser_or_on_the_newest_app(client):
    assert "data-app-update" not in home(client, BROWSER)
    assert "data-app-update" not in home(client, f"{OLD_APP} StrideBoardApp/{NEW}")


def test_old_app_without_updater_gets_a_download_link(client):
    page = home(client, OLD_APP)
    assert "App update ready" in page and config.ANDROID_APK_URL in page
    assert "removes this old app" in page and "data-app-update-button" not in page


def test_app_with_updater_gets_the_update_button(client):
    page = home(client, f"{OLD_APP} StrideBoardApp/{NEW - 1}".replace(f"/{NEW - 1}", f"/{max(NEW - 1, config.ANDROID_APP_UPDATER_FROM)}"))
    if config.ANDROID_APP_UPDATER_FROM < NEW:
        assert "data-app-update-button" in page and "uninstall" not in page
