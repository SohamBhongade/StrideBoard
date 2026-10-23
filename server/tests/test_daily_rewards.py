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
    assert s["tier"] == "Bronze"                  # Gold has no calendar yet, so Bronze's is used


def test_reset_clears_the_calendar(conn):
    uid = make_user(conn)
    data.claim_daily_reward(conn, uid, DAY1)
    data.reset_person(conn, uid)
    assert data.reward_status(conn, uid, DAY1)["day"] == 1
