from datetime import date

import pytest

import calc

WED = date(2026, 10, 14)


# ---------- weeks ----------

@pytest.mark.parametrize("day, monday, sunday", [
    ("2026-10-12", "2026-10-12", "2026-10-18"),  # Monday is the first day
    ("2026-10-18", "2026-10-12", "2026-10-18"),  # Sunday is the last day
    ("2026-10-19", "2026-10-19", "2026-10-25"),  # next Monday starts a new week
    ("2026-12-31", "2026-12-28", "2027-01-03"),  # week across the new year
])
def test_week_bounds(day, monday, sunday):
    m, s = calc.week_bounds(day)
    assert (m.isoformat(), s.isoformat()) == (monday, sunday)


def test_to_date_rejects_bad_text():
    for bad in ["2026-13-01", "2026-02-30", "14/10/2026", "", None, 20261014]:
        with pytest.raises(ValueError):
            calc.to_date(bad)


# ---------- parse_date ----------

def test_parse_date_empty_means_today():
    assert calc.parse_date(None, WED) == "2026-10-14"
    assert calc.parse_date("  ", WED) == "2026-10-14"


def test_parse_date_window():
    assert calc.parse_date("2026-10-07", WED) == "2026-10-07"   # exactly 7 days ago: OK
    with pytest.raises(ValueError, match="more than 7 days"):
        calc.parse_date("2026-10-06", WED)                      # 8 days ago
    with pytest.raises(ValueError, match="future"):
        calc.parse_date("2026-10-15", WED)
    assert calc.parse_date("2026-01-01", WED, max_days_back=None) == "2026-01-01"


def test_parse_date_arabic_digits_and_bad_types():
    assert calc.parse_date("٢٠٢٦-١٠-١٤", WED) == "2026-10-14"
    with pytest.raises(ValueError):
        calc.parse_date(20261014, WED)
    with pytest.raises(ValueError):
        calc.parse_date("2026-10-14T10:00", WED)


# ---------- parse_steps ----------

@pytest.mark.parametrize("value, expected", [
    (8423, 8423), (0, 0), (100000, 100000), (8423.4, 8423), (8423.5, 8424),
    ("8423", 8423), (" 8423 ", 8423), ("9,500.0", 9500), ("٨٤٢٣", 8423),
    ("۸۴۲۳", 8423), ("٩٬٥٠٠", 9500), ("100000.4", 100000),
])
def test_parse_steps_ok(value, expected):
    assert calc.parse_steps(value) == expected


@pytest.mark.parametrize("value", [
    -1, -0.5, "-1", 100001, "100,001", 100000.5, "abc", "", "1e5", None, True,
    float("nan"), float("inf"), [1], {"steps": 1},
])
def test_parse_steps_rejects(value):
    with pytest.raises(ValueError):
        calc.parse_steps(value)


def test_parse_int():
    assert calc.parse_int("4", "mood", 1, 5) == 4
    assert calc.parse_int("٣", "mood", 1, 5) == 3
    for bad in [0, 6, "x", 3.5, None, True]:
        with pytest.raises(ValueError):
            calc.parse_int(bad, "mood", 1, 5)


# ---------- tiers ----------

@pytest.mark.parametrize("total, tier", [
    (0, "Bronze"), (34999, "Bronze"), (35000, "Silver"), (59999, "Silver"),
    (60000, "Gold"), (89999, "Gold"), (90000, "Platinum"), (500000, "Platinum"),
])
def test_tier_boundaries(total, tier):
    assert calc.tier_for(total) == tier


def test_next_tier():
    assert calc.next_tier(0) == ("Silver", 35000)
    assert calc.next_tier(34999) == ("Silver", 1)
    assert calc.next_tier(35000) == ("Gold", 25000)
    assert calc.next_tier(90000) == (None, 0)


# ---------- streaks ----------

def test_streak_ending_today():
    assert calc.streak(["2026-10-12", "2026-10-13", "2026-10-14"], WED) == 3


def test_streak_ending_yesterday_counts():
    # Today's goal not met yet: the streak up to yesterday still counts.
    assert calc.streak(["2026-10-12", "2026-10-13"], WED) == 2


def test_streak_broken_or_empty():
    assert calc.streak(["2026-10-11", "2026-10-12"], WED) == 0   # gap on 13th
    assert calc.streak([], WED) == 0
    assert calc.streak(["2026-10-14", "2026-10-12"], WED) == 1


def test_streak_across_week_boundary():
    days = ["2026-10-09", "2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13"]
    assert calc.streak(days, WED) == 5


# ---------- adaptive goal ----------

def test_adaptive_goal_needs_14_days():
    assert calc.adaptive_goal([8000] * 13) is None


def test_adaptive_goal_math():
    # 8000 x 1.10 = 8800 -> nearest 250 = 8750 (8800/250 = 35.2)
    assert calc.adaptive_goal([8000] * 14) == 8750
    # 8295 x 1.1 = 9124.5 -> 9000 ; 8300 x 1.1 = 9130 -> 9250 (36.52 -> 37)
    assert calc.adaptive_goal([8295] * 14) == 9000
    assert calc.adaptive_goal([8300] * 14) == 9250


def test_adaptive_goal_uses_only_first_14_values():
    assert calc.adaptive_goal([10000] * 14 + [0] * 10) == 11000


def test_adaptive_goal_clamped():
    assert calc.adaptive_goal([500] * 14) == 3000
    assert calc.adaptive_goal([30000] * 14) == 15000


# ---------- small helpers ----------

def test_helpers():
    assert calc.percent_change(118, 100) == 18
    assert calc.percent_change(50, 0) is None
    assert calc.goal_percent(4000, 8000) == 50
    assert calc.goal_percent(100, 0) == 0
    assert calc.steps_to_km(171429) == 120.0
    assert calc.average([]) is None
    assert calc.round_to_nearest(8875, 250) == 9000   # exactly halfway rounds up


# ---------- badges ----------

def test_badges_none_and_all():
    assert calc.badge_keys(0, 0, 0, 0, 0, 0) == set()
    all_keys = calc.badge_keys(20, 12000, 7, 6, 95000, 40000)
    assert all_keys == {"first_log", "ten_k", "streak_3", "streak_7",
                        "consistent", "comeback", "platinum"}


def test_badge_thresholds():
    assert "ten_k" in calc.badge_keys(1, 10000, 0, 1, 10000, 0)
    assert "ten_k" not in calc.badge_keys(1, 9999, 0, 1, 9999, 0)
    assert "consistent" not in calc.badge_keys(4, 0, 0, 4, 0, 0)
    assert "streak_3" in calc.badge_keys(3, 0, 3, 3, 0, 0)


def test_comeback_needs_real_last_week():
    assert "comeback" in calc.badge_keys(1, 0, 0, 1, 12500, 10000)       # +25% exactly
    assert "comeback" not in calc.badge_keys(1, 0, 0, 1, 12499, 10000)
    assert "comeback" not in calc.badge_keys(1, 0, 0, 1, 9000, 5000)     # last week < 10,000


# ---------- insight sentence ----------

def test_insight_mood_needs_three_days_each():
    text = calc.insight_sentence(50000, 40000, [5, 4, 4], [3, 3, 3])
    assert text == "On days you hit your goal, your average mood was 4.3 vs 3.0 on other days."
    # only 2 'other' days: fall back to the steps sentence
    assert "more than last week" in calc.insight_sentence(50000, 40000, [5, 4, 4], [3, 3])


def test_insight_change_cases():
    assert calc.insight_sentence(118, 100, [], []) == "You walked 18% more than last week. Nice."
    assert "less than last week" in calc.insight_sentence(80, 100, [], [])
    assert "about the same" in calc.insight_sentence(102, 100, [], [])
    assert "Great start" in calc.insight_sentence(5000, 0, [], [])
    assert "No steps yet" in calc.insight_sentence(0, 0, [], [])
