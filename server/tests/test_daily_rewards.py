"""Daily login rewards: a 28-day calendar per tier, one claim a day."""
from datetime import date, timedelta

import pytest

import config
import data
from conftest import make_user, put_steps

DAY1 = date(2026, 10, 26)   # a Monday


def test_new_person_starts_on_bronze_day_1(conn):
    uid = make_user(conn)
    s = data.reward_status(conn, uid, DAY1)
    assert s["tier"] == "Bronze" and s["day"] == 1 and s["length"] == 28 and not s["claimed_today"]
    assert s["days"][0]["state"] == "today" and s["days"][1]["state"] == "later"


def test_claim_once_a_day_and_exp_is_paid(conn):
    uid = make_user(conn)
    got = data.claim_daily_reward(conn, uid, DAY1)
    assert got["label"] == "+5 EXP" and data.exp_balance(conn, uid) == 5
    with pytest.raises(ValueError, match="already claimed"):
        data.claim_daily_reward(conn, uid, DAY1)
    s = data.reward_status(conn, uid, DAY1)
    assert s["claimed_today"] and s["days"][0]["state"] == "claimed" and s["next"]["label"] == "+5 EXP"


def test_missing_days_does_not_reset_the_calendar(conn):
    uid = make_user(conn)
    data.claim_daily_reward(conn, uid, DAY1)
    data.claim_daily_reward(conn, uid, DAY1 + timedelta(days=5))    # away for 4 days
    assert data.reward_status(conn, uid, DAY1 + timedelta(days=9))["day"] == 3


def test_day_14_gives_an_item_or_its_price_if_owned(conn):
    uid = make_user(conn)
    for i in range(13):
        data.claim_daily_reward(conn, uid, DAY1 + timedelta(days=i))
    got = data.claim_daily_reward(conn, uid, DAY1 + timedelta(days=13))
    assert got["kind"] == "item" and got["item"] == "hat_headband"
    assert any(i["key"] == "hat_headband" and i["owned"] for i in data.avatar_shop(conn, uid)["items"])
    # someone who already owns day 28's item gets its price instead
    other = make_user(conn, "lee")
    conn.execute("INSERT INTO avatar_owned (user_id, item_key, bought_at) VALUES (?, 'shoes_runners', 'x')", (other,))
    for i in range(27):
        data.claim_daily_reward(conn, other, DAY1 + timedelta(days=i))
    before = data.exp_balance(conn, other)
    got = data.claim_daily_reward(conn, other, DAY1 + timedelta(days=27))
    assert got["swapped"] and data.exp_balance(conn, other) == before + config.AVATAR_ITEMS["shoes_runners"][2]


def test_after_28_days_a_new_calendar_uses_last_weeks_tier(conn):
    uid = make_user(conn)
    for i in range(28):
        data.claim_daily_reward(conn, uid, DAY1 + timedelta(days=i))
    later = DAY1 + timedelta(days=28)            # a Monday again
    for back in range(1, 8):                      # 70,000 steps last week: Gold
        put_steps(conn, uid, later - timedelta(days=back), 10_000)
    s = data.reward_status(conn, uid, later)
    assert s["cycle"] == 2 and s["day"] == 1
    assert s["tier"] == "Silver"                  # Gold has no calendar yet: the best one below it


def test_reset_clears_the_calendar(conn):
    uid = make_user(conn)
    data.claim_daily_reward(conn, uid, DAY1)
    data.reset_person(conn, uid)
    assert data.reward_status(conn, uid, DAY1)["day"] == 1


def test_moving_up_switches_to_silver_straight_away(conn):
    uid = make_user(conn)
    for i in range(3):
        data.claim_daily_reward(conn, uid, DAY1 + timedelta(days=i))
    assert data.reward_status(conn, uid, DAY1 + timedelta(days=3))["tier"] == "Bronze"
    put_steps(conn, uid, DAY1 + timedelta(days=3), 36_000)              # Silver this week
    s = data.reward_status(conn, uid, DAY1 + timedelta(days=3))
    assert s["tier"] == "Silver" and s["day"] == 4 and s["today"]["label"] == "+8 EXP"
    data.claim_daily_reward(conn, uid, DAY1 + timedelta(days=3))
    # next Monday this week's steps reset, but last week's Silver still counts
    assert data.reward_status(conn, uid, DAY1 + timedelta(days=7))["tier"] == "Silver"


def test_dropping_down_waits_for_a_new_calendar(conn):
    uid = make_user(conn)
    put_steps(conn, uid, DAY1, 36_000)
    data.claim_daily_reward(conn, uid, DAY1)
    two_weeks = DAY1 + timedelta(days=14)          # no steps for a fortnight: back to Bronze
    assert data.reward_status(conn, uid, two_weeks)["tier"] == "Silver"


def test_silver_items_are_reward_only(conn):
    uid = make_user(conn)
    data.add_exp(conn, uid, 5000, "gift")
    with pytest.raises(ValueError, match="can't be bought: it's a Silver daily reward"):
        data.buy_avatar_item(conn, uid, "hat_silver_visor")
    item = next(i for i in data.avatar_shop(conn, uid)["items"] if i["key"] == "extra_silver_wings")
    assert item["exclusive"] == "Silver" and not item["owned"]
    track = config.REWARD_TRACKS["Silver"]
    assert track[13] == ("item", "hat_silver_visor") and track[27] == ("item", "extra_silver_wings")
    assert sum(v for k, v in track if k == "exp") > sum(v for k, v in config.REWARD_TRACKS["Bronze"] if k == "exp")


def test_new_items_draw():
    import avatar_art
    svg = avatar_art.render({"color": "color_sky", "hat": "hat_silver_visor", "extra": "extra_silver_wings"}, 80)
    assert svg.count(avatar_art.SILVER) >= 3


def test_moving_up_after_claiming_today_shows_silver_now(conn):
    uid = make_user(conn)
    data.claim_daily_reward(conn, uid, DAY1)
    data.claim_daily_reward(conn, uid, DAY1 + timedelta(days=1))
    put_steps(conn, uid, DAY1 + timedelta(days=1), 36_000)
    s = data.reward_status(conn, uid, DAY1 + timedelta(days=1))
    assert s["tier"] == "Silver" and s["claimed_today"] and s["next"]["label"] == "+8 EXP"


def test_moving_up_on_day_1_after_claiming_shows_silver(conn):
    uid = make_user(conn)
    data.claim_daily_reward(conn, uid, DAY1)                     # claimed day 1 as Bronze
    put_steps(conn, uid, DAY1, 36_000)                           # then reached Silver
    s = data.reward_status(conn, uid, DAY1)
    assert s["tier"] == "Silver" and s["day"] == 1 and s["claimed_today"]
