"""Mini challenges: start one, do it, tap Done (or walk it), earn EXP; back out any time."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

import config
import data
from conftest import TODAY, make_user, put_steps

T0 = datetime.combine(TODAY, time(10, 0), tzinfo=ZoneInfo("Asia/Dubai"))


def later(seconds):
    return T0 + timedelta(seconds=seconds)


def track(conn, uid, key):
    return next(t for t in data.progression(conn, uid) if t["key"] == key)


def test_menu_lists_every_challenge_and_nothing_active(conn):
    uid = make_user(conn)
    state = data.mini_state(conn, uid, T0)
    assert state["active"] is None and state["exp_today"] == 0
    assert [c["key"] for c in state["challenges"]] == list(config.MINI_CHALLENGES)
    labels = {c["key"]: c["label"] for c in state["challenges"]}
    assert labels["pushups_10"] == "10 push-ups"
    assert labels["planks_30"] == "30-second plank"
    assert labels["walk_1000"] == "Walk 1,000 steps"


def test_finish_exercise_pays_exp_and_fills_the_track(conn):
    uid = make_user(conn)
    data.start_mini(conn, uid, "pushups_10", T0)
    assert data.mini_state(conn, uid, later(5))["active"]["wait"] == 10
    won = data.finish_mini(conn, uid, later(20))
    assert won["exp"] == 10 and won["balance"] == 10
    t = track(conn, uid, "pushups")
    assert t["total"] == 10 and t["best"] == 10
    state = data.mini_state(conn, uid, later(30))
    assert state["active"] is None and state["exp_today"] == 10
    assert next(c for c in state["challenges"] if c["key"] == "pushups_10")["done_today"] == 1
    assert data.exp_history(conn, uid)[0]["reason"] == "Mini challenge: 10 push-ups"


def test_done_too_fast_is_refused(conn):
    uid = make_user(conn)
    data.start_mini(conn, uid, "planks_30", T0)
    with pytest.raises(ValueError, match="Give it 20 more seconds"):
        data.finish_mini(conn, uid, later(10))
    assert data.exp_balance(conn, uid) == 0
    data.finish_mini(conn, uid, later(30))
    assert track(conn, uid, "planks")["total"] == 30


def test_back_out_gives_nothing_and_frees_you(conn):
    uid = make_user(conn)
    data.start_mini(conn, uid, "squats_30", T0)
    assert data.quit_mini(conn, uid, later(5)) == "30 squats"
    assert data.exp_balance(conn, uid) == 0 and track(conn, uid, "squats")["total"] == 0
    assert data.mini_state(conn, uid, later(6))["active"] is None
    data.start_mini(conn, uid, "squats_15", later(7))      # can start another straight away


def test_only_one_at_a_time(conn):
    uid = make_user(conn)
    data.start_mini(conn, uid, "pushups_10", T0)
    with pytest.raises(ValueError, match="finish or back out"):
        data.start_mini(conn, uid, "squats_15", later(1))


def test_daily_limit_per_challenge(conn):
    uid = make_user(conn)
    for i in range(config.MINI_DAILY_LIMIT):
        data.start_mini(conn, uid, "jumping_jacks_25", later(i * 100))
        data.finish_mini(conn, uid, later(i * 100 + 30))
    with pytest.raises(ValueError, match="3 times today"):
        data.start_mini(conn, uid, "jumping_jacks_25", later(1000))
    data.start_mini(conn, uid, "jumping_jacks_50", later(1001))   # a different one is fine
    assert data.mini_state(conn, uid, later(1002))["exp_today"] == 30


def test_nothing_to_finish_or_quit(conn):
    uid = make_user(conn)
    for fn in (data.finish_mini, data.quit_mini):
        with pytest.raises(ValueError, match="don't have a challenge"):
            fn(conn, uid, T0)
    with pytest.raises(ValueError, match="doesn't exist"):
        data.start_mini(conn, uid, "situps_1000", T0)


def test_walk_finishes_by_itself_from_new_steps(conn):
    uid = make_user(conn)
    put_steps(conn, uid, TODAY, 3_000)
    data.start_mini(conn, uid, "walk_1000", T0)
    with pytest.raises(ValueError, match="by themselves"):
        data.finish_mini(conn, uid, later(600))
    put_steps(conn, uid, TODAY, 3_600)
    assert data.check_walks(conn, uid, later(400)) is None
    assert data.mini_state(conn, uid, later(400))["active"]["walked"] == 600
    put_steps(conn, uid, TODAY, 4_100)
    assert data.check_walks(conn, uid, later(200)) is None          # too soon to be real walking
    won = data.check_walks(conn, uid, later(600))
    assert won["exp"] == 15 and data.mini_state(conn, uid, later(601))["active"] is None
    assert track(conn, uid, "steps")["total"] == 4_100              # not counted twice


def test_walk_from_yesterday_is_dropped(conn):
    uid = make_user(conn)
    data.start_mini(conn, uid, "walk_2500", T0)
    assert data.check_walks(conn, uid, T0 + timedelta(days=1)) is None
    assert data.mini_state(conn, uid, T0 + timedelta(days=1))["active"] is None
    assert data.exp_balance(conn, uid) == 0
