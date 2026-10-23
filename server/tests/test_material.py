"""Material You for Android: the look, colour themes from the studio, and the palette maths."""
import re

import pytest

import config
import data
import material

ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/141 Mobile Safari/537.36"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"


@pytest.mark.parametrize("seed", [v[2] for v in config.MATERIAL_THEMES.values()])
@pytest.mark.parametrize("dark", [False, True])
def test_every_theme_makes_valid_colours_with_readable_text(seed, dark):
    s = material.scheme(seed, dark)
    assert all(re.fullmatch(r"#[0-9A-F]{6}", v) for v in s.values())
    lum = lambda h: sum(int(h[i:i + 2], 16) for i in (1, 3, 5)) / 765
    # text stays far from its background in both modes
    assert abs(lum(s["--ink"]) - lum(s["--sage"])) > .7
    assert abs(lum(s["--m-primary"]) - lum(s["--m-on-primary"])) > .3


def test_everyone_starts_on_stock_and_themes_cost_exp(conn):
    from conftest import make_user
    uid = make_user(conn)
    assert data.material_choice(conn, uid) == "mat_stock"
    with pytest.raises(ValueError, match="costs 150 EXP"):
        data.buy_avatar_item(conn, uid, "mat_berry")
    data.add_exp(conn, uid, 200, "gift")
    data.buy_avatar_item(conn, uid, "mat_berry")
    assert data.material_choice(conn, uid) == "mat_berry"
    assert data.glass_choice(conn, uid) == "glass_stock"       # the two looks are separate
    data.wear_avatar_item(conn, uid, "mat_stock")
    assert data.material_choice(conn, uid) == "mat_stock"


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
    data.add_exp(conn, uid, 500, "gift")
    conn.close()
    c = web.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["csrf"] = "x"
    return c


def test_android_gets_material_and_others_do_not(client):
    page = client.get("/", headers={"User-Agent": ANDROID}).data.decode()
    assert 'class="material"' in page and ":root.material" in page
    page = client.get("/", headers={"User-Agent": IPHONE}).data.decode()
    assert 'class="material"' not in page and ":root.material[" not in page


def test_choosing_a_theme_changes_the_android_colours(client):
    seed = config.MATERIAL_THEMES["mat_grape"][2]
    r = client.post("/settings", data={"csrf": "x", "action": "avatar_buy", "item": "mat_grape", "slot": "material"},
                    headers={"User-Agent": ANDROID})
    assert r.status_code == 302 and "slot=material" in r.headers["Location"]
    page = client.get("/", headers={"User-Agent": ANDROID}).data.decode()
    assert material.scheme(seed)["--m-primary"] in page
    studio = client.get("/settings?slot=material", headers={"User-Agent": ANDROID}).data.decode()
    assert "mat-swatch" in studio and "Your Android colour theme" in studio


def test_android_gets_the_expressive_extras():
    """Material 3 Expressive on Android: Material shapes, gradient cards, grain, still for reduced motion."""
    import pathlib
    css = (pathlib.Path(__file__).parent.parent / "static/css/style.css").read_text()
    for bit in ("--shape-cookie", "--shape-clover", "--grain", ".material .card {", "expr-spin"):
        assert bit in css
    assert ".material body::before, .material body::after { animation: none; }" in css
