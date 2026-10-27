"""Everyone who signs up starts with a 6,000-step daily goal, whatever their age band."""
import pytest

import config
import data
from conftest import make_user

pytestmark = pytest.mark.real_goals


def test_everyone_starts_at_6000(conn):
    assert config.START_GOAL == 6000
    for band in config.AGE_BANDS:
        uid = make_user(conn, f"user_{band}", age_band=band)
        assert data.get_user(conn, uid)["daily_goal"] == 6000


def test_changing_age_band_keeps_6000(conn):
    uid = make_user(conn, "sam", age_band="teen_13_17")
    data.set_age_band(conn, uid, "adult_40_59")
    assert data.get_user(conn, uid)["daily_goal"] == 6000
