"""The stand-up reminder: only when syncs show under 50 steps across 30+ minutes."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import data
from conftest import TODAY, make_user

DUBAI = ZoneInfo("Asia/Dubai")
NOON = datetime(TODAY.year, TODAY.month, TODAY.day, 12, 0, tzinfo=DUBAI)


def sample(conn, uid, total, minutes_before_noon):
    at = (NOON - timedelta(minutes=minutes_before_noon)).isoformat(timespec="seconds")
    data._record_sample(conn, uid, str(TODAY), total, at=at)
    conn.commit()


def test_no_syncs_means_we_cannot_tell(conn):
    uid = make_user(conn)
    assert data.inactivity(conn, uid, NOON)["inactive"] is None


def test_sitting_still_for_30_minutes_is_inactive(conn):
    uid = make_user(conn)
    sample(conn, uid, 4_000, 35)
    sample(conn, uid, 4_030, 2)          # +30 steps in 33 minutes
    r = data.inactivity(conn, uid, NOON)
    assert r["inactive"] is True and r["minutes"] == 33 and r["gained"] == 30


def test_walking_is_not_inactive(conn):
    uid = make_user(conn)
    sample(conn, uid, 4_000, 40)
    sample(conn, uid, 4_800, 1)
    assert data.inactivity(conn, uid, NOON)["inactive"] is False


def test_exactly_50_steps_counts_as_moving(conn):
    uid = make_user(conn)
    sample(conn, uid, 1_000, 31)
    sample(conn, uid, 1_050, 0)
    assert data.inactivity(conn, uid, NOON)["inactive"] is False


def test_syncs_less_than_30_minutes_apart_cannot_tell(conn):
    uid = make_user(conn)
    sample(conn, uid, 1_000, 20)
    sample(conn, uid, 1_000, 0)
    assert data.inactivity(conn, uid, NOON)["inactive"] is None


def test_old_latest_sync_cannot_tell(conn):
    uid = make_user(conn)
    sample(conn, uid, 1_000, 120)
    sample(conn, uid, 1_000, 60)         # newest sync is an hour old
    assert data.inactivity(conn, uid, NOON)["inactive"] is None


def test_compares_with_the_newest_sync_at_least_30_minutes_earlier(conn):
    uid = make_user(conn)
    sample(conn, uid, 1_000, 90)         # a walk happened after this one...
    sample(conn, uid, 3_000, 40)         # ...but since this one, only 20 steps
    sample(conn, uid, 3_020, 1)
    r = data.inactivity(conn, uid, NOON)
    assert r["inactive"] is True and r["gained"] == 20


def test_saving_todays_steps_records_a_sample_but_not_other_days(conn):
    uid = make_user(conn)
    data.save_steps(conn, uid, str(TODAY), 500, "android_app", today=TODAY)
    data.save_steps(conn, uid, str(TODAY - timedelta(days=1)), 9_000, "android_app", today=TODAY)
    rows = conn.execute("SELECT date, total FROM step_samples WHERE user_id = ?", (uid,)).fetchall()
    assert [tuple(r) for r in rows] == [(str(TODAY), 500)]


def test_old_samples_are_cleaned_up(conn):
    uid = make_user(conn)
    data._record_sample(conn, uid, str(TODAY - timedelta(days=5)), 100, at="2026-10-09T10:00:00+04:00")
    data._record_sample(conn, uid, str(TODAY), 200)
    dates = [r[0] for r in conn.execute("SELECT date FROM step_samples WHERE user_id = ?", (uid,))]
    assert dates == [str(TODAY)]
