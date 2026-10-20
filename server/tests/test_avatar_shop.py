"""EXP wallet and avatar studio: balances, buying, wearing."""
import pytest

import config
import data
from conftest import make_user


def test_new_user_has_no_exp_and_a_free_default_avatar(conn):
    uid = make_user(conn)
    shop = data.avatar_shop(conn, uid)
    assert shop["balance"] == 0
    assert shop["build"]["color"] in config.AVATAR_START_COLORS
    assert shop["build"]["hat"] == "hat_none"
    free = [i for i in shop["items"] if i["price"] == 0]
    assert free and all(i["owned"] for i in free)
    assert not any(i["owned"] for i in shop["items"] if i["price"] > 0)


def test_add_exp_and_history(conn):
    uid = make_user(conn)
    assert data.add_exp(conn, uid, 200, "Test gift") == 200
    assert data.add_exp(conn, uid, "50", "Another") == 250
    assert [h["amount"] for h in data.exp_history(conn, uid)] == [50, 200]


@pytest.mark.parametrize("amount, reason, message", [
    (0, "x", "EXP"), (-5, "x", "EXP"), (config.EXP_MAX_GRANT + 1, "x", "EXP"),
    ("lots", "x", "EXP"), (10, "", "reason"),
])
def test_add_exp_rejects_bad_input(conn, amount, reason, message):
    uid = make_user(conn)
    with pytest.raises(ValueError, match=message):
        data.add_exp(conn, uid, amount, reason)


def test_buy_spends_exp_owns_and_wears(conn):
    uid = make_user(conn)
    data.add_exp(conn, uid, 300, "gift")
    assert data.buy_avatar_item(conn, uid, "hat_cap") == 150
    shop = data.avatar_shop(conn, uid)
    cap = next(i for i in shop["items"] if i["key"] == "hat_cap")
    assert cap["owned"] and cap["worn"] and shop["build"]["hat"] == "hat_cap"
    assert data.exp_history(conn, uid)[0] == {**data.exp_history(conn, uid)[0], "amount": -150, "reason": "Bought Cap"}


def test_cannot_buy_without_enough_exp(conn):
    uid = make_user(conn)
    data.add_exp(conn, uid, 100, "gift")
    with pytest.raises(ValueError, match="costs 1,000 EXP and you have 100"):
        data.buy_avatar_item(conn, uid, "hat_crown")
    assert data.exp_balance(conn, uid) == 100


def test_cannot_buy_twice_or_buy_free_items(conn):
    uid = make_user(conn)
    data.add_exp(conn, uid, 500, "gift")
    data.buy_avatar_item(conn, uid, "extra_glasses")
    with pytest.raises(ValueError, match="already own"):
        data.buy_avatar_item(conn, uid, "extra_glasses")
    with pytest.raises(ValueError, match="free"):
        data.buy_avatar_item(conn, uid, "color_mint")
    assert data.exp_balance(conn, uid) == 450


def test_wear_free_and_owned_items_only(conn):
    uid = make_user(conn)
    data.wear_avatar_item(conn, uid, "eyes_happy")
    assert data.avatar_build(conn, uid)["eyes"] == "eyes_happy"
    with pytest.raises(ValueError, match="buy Crown first"):
        data.wear_avatar_item(conn, uid, "hat_crown")
    with pytest.raises(ValueError, match="doesn't exist"):
        data.wear_avatar_item(conn, uid, "hat_spaceship")


def test_wearing_replaces_only_that_slot(conn):
    uid = make_user(conn)
    data.wear_avatar_item(conn, uid, "bg_sage")
    data.wear_avatar_item(conn, uid, "color_lilac")
    data.wear_avatar_item(conn, uid, "color_peach")
    b = data.avatar_build(conn, uid)
    assert b["bg"] == "bg_sage" and b["color"] == "color_peach"


def test_builds_for_many_people(conn):
    a, b = make_user(conn, "aaa"), make_user(conn, "bbb")
    data.wear_avatar_item(conn, b, "mouth_o")
    builds = data.avatar_builds(conn, [a, b, None])
    assert set(builds) == {a, b} and builds[b]["mouth"] == "mouth_o"


def test_find_user_id(conn):
    uid = make_user(conn, "sam.k")
    assert data.find_user_id(conn, "SAM.K") == uid
    assert data.find_user_id(conn, "nobody") is None


def test_set_role(conn):
    admin = make_user(conn, "boss", role="admin")
    uid = make_user(conn, "mentor", role="admin", department=None)
    assert data.set_role(conn, uid, "teacher", "Mentors", acting_admin_id=admin) == "admin"
    u = data.get_user(conn, uid)
    assert u["role"] == "teacher" and u["department"] == "Mentors"
    data.set_role(conn, uid, "student")
    assert data.get_user(conn, uid)["department"] == "Mentors"   # blank keeps the old one
    with pytest.raises(ValueError, match="your own admin"):
        data.set_role(conn, admin, "teacher", acting_admin_id=admin)
    with pytest.raises(ValueError, match="role must be"):
        data.set_role(conn, uid, "boss")
