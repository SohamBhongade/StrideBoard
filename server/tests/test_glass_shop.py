"""Glass gradients (Avatar studio > Glass) and the extra sneakers."""
import pytest

import avatar_art
import config
import data
import workout_rig
from conftest import make_user


def test_everyone_starts_on_the_free_stock_gradient(conn):
    uid = make_user(conn)
    assert data.glass_choice(conn, uid) == "glass_stock"
    glass = [i for i in data.avatar_shop(conn, uid)["items"] if i["slot"] == "glass"]
    assert [i["key"] for i in glass] == list(config.GLASS_GRADIENTS)
    stock = glass[0]
    assert stock["price"] == 0 and stock["owned"] and stock["worn"]
    assert not any(i["owned"] for i in glass[1:])     # the rest are locked behind EXP


def test_gradients_cost_exp_and_can_switch_back_to_stock(conn):
    uid = make_user(conn)
    with pytest.raises(ValueError, match="costs 400 EXP"):
        data.buy_avatar_item(conn, uid, "glass_aurora")
    with pytest.raises(ValueError, match="buy Aurora first"):
        data.wear_avatar_item(conn, uid, "glass_aurora")
    data.add_exp(conn, uid, 500, "gift")
    assert data.buy_avatar_item(conn, uid, "glass_aurora") == 100
    assert data.glass_choice(conn, uid) == "glass_aurora"
    data.wear_avatar_item(conn, uid, "glass_stock")          # stock is always there to go back to
    assert data.glass_choice(conn, uid) == "glass_stock"
    data.wear_avatar_item(conn, uid, "glass_aurora")         # bought once, kept
    assert data.glass_choice(conn, uid) == "glass_aurora"


def test_gradient_is_not_part_of_the_avatar(conn):
    uid = make_user(conn)
    data.add_exp(conn, uid, 100, "gift")
    data.buy_avatar_item(conn, uid, "glass_ocean")
    assert "glass" not in data.avatar_build(conn, uid)


def test_reset_puts_the_gradient_back_to_stock(conn):
    uid = make_user(conn)
    data.add_exp(conn, uid, 100, "gift")
    data.buy_avatar_item(conn, uid, "glass_ocean")
    data.reset_person(conn, uid)
    assert data.glass_choice(conn, uid) == "glass_stock"


@pytest.mark.parametrize("key", [k for k, v in config.AVATAR_ITEMS.items() if v[0] == "shoes"])
def test_every_pair_of_shoes_draws(key):
    build = {"color": "color_mint", "shoes": key}
    assert avatar_art.render(build, 60).count("<ellipse") >= 2
    if key != "shoes_plain":
        assert avatar_art.SHOES[key][0] in workout_rig.figure(build, "walk")


def test_there_are_more_sneakers_now():
    assert sum(1 for v in config.AVATAR_ITEMS.values() if v[0] == "shoes") >= 10


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
    data.add_exp(conn, uid, 200, "gift")
    conn.close()
    c = web.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["csrf"] = "x"
    return c


def test_studio_glass_tab_buy_and_page_colours(client):
    page = client.get("/settings?slot=glass").data.decode()
    assert "glass-swatch" in page and "Stock" in page and "Forest" in page
    assert "html.glass { background" not in page          # stock comes from the stylesheet
    r = client.post("/settings", data={"csrf": "x", "action": "avatar_buy", "item": "glass_forest", "slot": "glass"})
    assert r.status_code == 302 and "slot=glass" in r.headers["Location"]
    page = client.get("/").data.decode()
    light, dark = config.GLASS_GRADIENTS["glass_forest"][2:]
    assert "html.glass { background" in page and light[1] in page and dark[1] in page
