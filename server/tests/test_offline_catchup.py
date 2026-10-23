"""Back from camping: days synced late (up to a week) still count, and the streak carries on."""
from datetime import date, timedelta

import pytest

import data
from conftest import make_user

TODAY = date(2026, 10, 23)


def test_missed_days_sent_late_repair_the_streak(conn):
    uid = make_user(conn)
    goal = data.get_user(conn, uid)["daily_goal"]
    # Synced normally a week ago, then three days with no signal.
    for back in (6, 5, 4):
        data.save_steps(conn, uid, (TODAY - timedelta(days=back)).isoformat(), goal + 500, "android_app", today=TODAY)
    assert data.dashboard(conn, uid, TODAY)["streak"] == 0          # gap: yesterday and before missing
    # Back online: the app sends every missed day, oldest first, then today.
    for back in (3, 2, 1, 0):
        data.save_steps(conn, uid, (TODAY - timedelta(days=back)).isoformat(), goal + 500, "android_app", today=TODAY)
    assert data.dashboard(conn, uid, TODAY)["streak"] == 7


def test_a_week_is_the_limit(conn):
    uid = make_user(conn)
    data.save_steps(conn, uid, (TODAY - timedelta(days=7)).isoformat(), 9000, "android_app", today=TODAY)
    with pytest.raises(ValueError, match="more than 7 days ago"):
        data.save_steps(conn, uid, (TODAY - timedelta(days=8)).isoformat(), 9000, "android_app", today=TODAY)
