"""Progression tracks on the Challenges page: lifetime levels and personal-best badges."""
from datetime import timedelta

import pytest

import data
from conftest import TODAY, make_user, put_steps


def track(conn, uid, key):
    return next(t for t in data.progression(conn, uid) if t["key"] == key)


def test_new_user_has_nothing_earned(conn):
    uid = make_user(conn)
    tracks = data.progression(conn, uid)
    assert [t["key"] for t in tracks] == ["steps", "pushups", "squats", "planks", "jumping_jacks"]
    for t in tracks:
        assert t["total"] == 0 and t["earned_count"] == 0 and t["record"]["level"] == 0
        assert t["next_target"] == t["levels"][0]["target"]
    assert len(track(conn, uid, "steps")["levels"]) == 9
    assert len(track(conn, uid, "pushups")["levels"]) == 11


def test_step_levels_use_lifetime_total_and_record_uses_best_day(conn):
    uid = make_user(conn)
    put_steps(conn, uid, TODAY - timedelta(days=2), 4_000)
    put_steps(conn, uid, TODAY - timedelta(days=1), 12_000)
    t = track(conn, uid, "steps")
    assert t["total"] == 16_000 and t["best"] == 12_000
    earned = [lv["target"] for lv in t["levels"] if lv["earned"]]
    assert earned == [1_000, 5_000, 10_000]
    # 1k was reached on the first day; 5k and 10k only once day two was added
    assert t["levels"][0]["earned_on"] == str(TODAY - timedelta(days=2))
    assert t["levels"][1]["earned_on"] == str(TODAY - timedelta(days=1))
    assert t["next_target"] == 25_000
    assert t["next_percent"] == round((16_000 - 10_000) * 100 / (25_000 - 10_000))
    assert t["record"]["level"] == 2 and t["record"]["next_target"] == 15_000


def test_exercise_sets_add_up_and_best_day_counts_for_record(conn):
    uid = make_user(conn)
    data.save_exercise(conn, uid, str(TODAY), "pushups", 8)
    data.save_exercise(conn, uid, str(TODAY), "pushups", 22)
    t = track(conn, uid, "pushups")
    assert t["total"] == 30 and t["best"] == 30          # both sets that day added up
    assert [lv["target"] for lv in t["levels"] if lv["earned"]] == [5, 10, 25]
    assert t["record"]["level"] == 3          # 30 in one day: 10, 20 and 30
    assert track(conn, uid, "squats")["total"] == 0   # tracks stay separate


def test_planks_are_seconds(conn):
    uid = make_user(conn)
    data.save_exercise(conn, uid, str(TODAY), "planks", "90")
    t = track(conn, uid, "planks")
    assert t["total"] == 90 and t["unit"] == "seconds"
    assert [lv["target"] for lv in t["levels"] if lv["earned"]] == [30, 60]


def test_everything_maxed_shows_100_percent(conn):
    uid = make_user(conn)
    for _ in range(10):
        data.save_exercise(conn, uid, str(TODAY), "pushups", 1_000)
    t = track(conn, uid, "pushups")
    assert t["earned_count"] == 11 and t["next_target"] is None and t["next_percent"] == 100


@pytest.mark.parametrize("args, message", [
    (("situps", 10), "exercise must be"),
    (("pushups", 0), "reps"),
    (("pushups", 1_001), "reps"),
    (("planks", 3_601), "seconds"),
    (("pushups", "lots"), "reps"),
])
def test_save_exercise_rejects_bad_input(conn, args, message):
    uid = make_user(conn)
    with pytest.raises(ValueError, match=message):
        data.save_exercise(conn, uid, str(TODAY), *args)


def test_save_exercise_rejects_old_and_future_dates(conn):
    uid = make_user(conn)
    with pytest.raises(ValueError):
        data.save_exercise(conn, uid, str(TODAY + timedelta(days=1)), "squats", 10)
    with pytest.raises(ValueError):
        data.save_exercise(conn, uid, str(TODAY - timedelta(days=30)), "squats", 10)


def test_exercises_never_touch_leaderboards(conn):
    uid = make_user(conn)
    data.save_exercise(conn, uid, str(TODAY), "jumping_jacks", 5_000)
    for view in ("student", "effort", "improvement", "department"):
        board = data.leaderboard(conn, view, TODAY)
        assert all(row["value"] == 0 for row in board if row.get("user_id") == uid) or \
            not any(row.get("user_id") == uid for row in board)
    assert data.dashboard(conn, uid, TODAY)["weekly_total"] == 0
