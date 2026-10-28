"""Tests for data.py on a temporary database. 'Today' is Wednesday 2026-10-14."""
from datetime import date, timedelta

import pytest

import data
from conftest import TODAY, make_user, put_steps

MON = date(2026, 10, 12)          # this week's Monday
LAST_MON = MON - timedelta(days=7)


def days_ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


# =====================================================================
# Users
# =====================================================================

def test_create_get_and_authenticate(conn):
    uid = make_user(conn, "Sam.K", display_name="Sam K", age_band="teen_13_17", pin="4321")
    user = data.get_user(conn, uid)
    assert user["username"] == "sam.k"                 # stored in lower case
    assert user["daily_goal"] == 10000                 # from the teen age band
    assert user["goal_is_custom"] == 0
    assert "pin_hash" not in user
    assert len(user["api_token"]) >= 30
    assert user["created_at"].endswith("+04:00")

    assert data.authenticate(conn, "SAM.K ", "4321")["id"] == uid
    assert data.authenticate(conn, "sam.k", "0000") is None
    assert data.authenticate(conn, "nobody", "4321") is None
    assert data.get_user(conn, 999) is None


def test_pin_is_hashed(conn):
    make_user(conn, "sam", pin="1234")
    stored = conn.execute("SELECT pin_hash FROM users").fetchone()[0]
    # A real hash (method:salt$digest), never the PIN. (A random digest can contain "1234" by chance.)
    assert stored != "1234" and stored.startswith(("scrypt:", "pbkdf2:")) and "$" in stored


@pytest.mark.parametrize("kwargs, message", [
    ({"username": "ab"}, "username"),
    ({"username": "has space"}, "username"),
    ({"role": "parent"}, "role"),
    ({"age_band": "baby"}, "age_band"),
    ({"pin": "12"}, "PIN"),
    ({"pin": "1234567"}, "PIN"),
    ({"pin": "12a4"}, "PIN"),
    ({"display_name": " "}, "display name"),
])
def test_create_user_rejects_bad_input(conn, kwargs, message):
    args = {"username": "sam", "role": "student", "department": "Grade 10A",
            "age_band": "teen_13_17", "pin": "1234", "display_name": "Sam"}
    args.update(kwargs)
    with pytest.raises(ValueError, match=message):
        make_user(conn, **args)


def test_duplicate_username(conn):
    make_user(conn, "sam")
    with pytest.raises(ValueError, match="already taken"):
        make_user(conn, "SAM")


def test_bulk_create_users(conn):
    text = (
        "username,display_name,role,department,age_band,pin\n"
        "t.ali,Mr Ali,teacher,Science,adult_40_59,1111\n"
        "\n"
        "s.mia,Mia,student,Grade 10A,teen_13_17,2222\n"
        "s.bad,Bad,student,Grade 10A,teen_13_17,12\n"
        "s.short,Short,student\n"
        "t.ali,Again,teacher,Math,adult_18_39,3333\n"
    )
    result = data.bulk_create_users(conn, text)
    assert result["created"] == 2
    assert len(result["errors"]) == 3
    assert result["errors"][0].startswith("row 5: PIN")
    assert result["errors"][1].startswith("row 6: expected 6 columns")
    assert "already taken" in result["errors"][2]
    assert "12" not in result["errors"][0].replace("row 5", "")  # PINs are not echoed


def test_list_users_hides_secrets(conn):
    make_user(conn, "sam")
    make_user(conn, "t.ali", role="teacher", department="Science", age_band="adult_18_39")
    users = data.list_users(conn)
    assert len(users) == 2
    assert all("pin_hash" not in u and "api_token" not in u for u in users)


def test_custom_goal_and_age_band(conn):
    uid = make_user(conn, "sam", age_band="teen_13_17")
    data.set_age_band(conn, uid, "under_13")
    assert data.get_user(conn, uid)["daily_goal"] == 10000   # the band never changes the goal

    data.set_custom_goal(conn, uid, "9000")
    user = data.get_user(conn, uid)
    assert (user["daily_goal"], user["goal_is_custom"]) == (9000, 1)

    data.set_age_band(conn, uid, "adult_18_39")
    assert data.get_user(conn, uid)["daily_goal"] == 9000    # custom goal is kept

    with pytest.raises(ValueError):
        data.set_custom_goal(conn, uid, 500)
    with pytest.raises(ValueError, match="not found"):
        data.set_custom_goal(conn, 999, 9000)


def test_regenerate_token(conn):
    uid = make_user(conn, "sam")
    old = data.get_user(conn, uid)["api_token"]
    new = data.regenerate_token(conn, uid)
    assert new != old
    assert data.get_user_by_token(conn, old) is None
    assert data.get_user_by_token(conn, new)["id"] == uid
    assert data.get_user_by_token(conn, "") is None
    assert data.get_user_by_token(conn, None) is None


# =====================================================================
# Steps and badges
# =====================================================================

def test_save_steps_upserts_and_returns_week(conn):
    uid = make_user(conn, "sam")
    put_steps(conn, uid, LAST_MON, 50000)                 # last week: not counted
    result = data.save_steps(conn, uid, "2026-10-13", 8000, "ios_shortcut")
    assert result["weekly_total"] == 8000
    assert result["tier"] == "Bronze"

    result = data.save_steps(conn, uid, "2026-10-13", "9,500.0", "android_app")  # overwrite
    assert result["weekly_total"] == 9500
    rows = conn.execute("SELECT steps, source FROM steps WHERE date = '2026-10-13'").fetchall()
    assert [tuple(r) for r in rows] == [(9500, "android_app")]


def test_save_steps_date_rules(conn):
    uid = make_user(conn, "sam")
    assert data.save_steps(conn, uid, None, 1000, "manual")["weekly_total"] == 1000  # default today
    data.save_steps(conn, uid, days_ago(7), 1000, "manual")                          # 7 days: OK
    with pytest.raises(ValueError, match="more than 7 days"):
        data.save_steps(conn, uid, days_ago(8), 1000, "manual")
    with pytest.raises(ValueError, match="future"):
        data.save_steps(conn, uid, "2026-10-15", 1000, "manual")


def test_save_steps_bad_values(conn):
    uid = make_user(conn, "sam")
    with pytest.raises(ValueError, match="source"):
        data.save_steps(conn, uid, None, 1000, "fitbit")
    with pytest.raises(ValueError, match="negative"):
        data.save_steps(conn, uid, None, -1, "manual")
    with pytest.raises(ValueError, match="100,000"):
        data.save_steps(conn, uid, None, 100001, "manual")
    with pytest.raises(ValueError, match="user not found"):
        data.save_steps(conn, 999, None, 1000, "manual")


def test_first_log_and_ten_k_badges_once(conn):
    uid = make_user(conn, "sam")
    assert data.save_steps(conn, uid, None, 12000, "manual")["new_badges"] == ["first_log", "ten_k"]
    assert data.save_steps(conn, uid, None, 13000, "manual")["new_badges"] == []


def test_streak_badges(conn):
    uid = make_user(conn, "sam")                                  # goal 10,000
    for n in range(6, 0, -1):
        put_steps(conn, uid, days_ago(n), 10500)
    new = data.save_steps(conn, uid, None, 10000, "manual")["new_badges"]
    assert {"streak_3", "streak_7"} <= set(new)


def test_consistent_badge(conn):
    uid = make_user(conn, "sam")
    for d in ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]:  # last week, 4 days
        put_steps(conn, uid, d, 100)
    new = data.save_steps(conn, uid, "2026-10-09", 100, "manual")["new_badges"]
    assert "consistent" in new           # 5 days in the week of the saved date


def test_comeback_badge_needs_last_week_10000(conn):
    uid = make_user(conn, "sam")
    put_steps(conn, uid, LAST_MON, 8000)                          # last week below 10,000
    assert "comeback" not in data.save_steps(conn, uid, None, 20000, "manual")["new_badges"]

    other = make_user(conn, "mia")
    put_steps(conn, other, LAST_MON, 20000)
    put_steps(conn, other, MON, 20000)
    assert "comeback" in data.save_steps(conn, other, None, 5000, "manual")["new_badges"]


def test_platinum_badge(conn):
    uid = make_user(conn, "sam")
    put_steps(conn, uid, MON, 50000)
    put_steps(conn, uid, MON + timedelta(days=1), 35000)
    result = data.save_steps(conn, uid, None, 5000, "manual")
    assert result["tier"] == "Platinum"
    assert "platinum" in result["new_badges"]


# =====================================================================
# Mood, water, activities
# =====================================================================

def test_mood_water_activity(conn):
    uid = make_user(conn, "sam")
    data.save_mood(conn, uid, None, 3)
    data.save_mood(conn, uid, None, "5")                  # replaces today's mood
    data.save_water(conn, uid, None, 6)
    aid = data.add_activity(conn, uid, None, "yoga", 20)
    dash = data.dashboard(conn, uid, TODAY)
    assert dash["mood_today"] == 5
    assert dash["water_today"] == 6
    assert aid > 0

    for bad in [0, 6, "great"]:
        with pytest.raises(ValueError):
            data.save_mood(conn, uid, None, bad)
    with pytest.raises(ValueError):
        data.save_water(conn, uid, None, 21)
    with pytest.raises(ValueError, match="type"):
        data.add_activity(conn, uid, None, "chess", 20)
    with pytest.raises(ValueError, match="minutes"):
        data.add_activity(conn, uid, None, "walk", 601)
    with pytest.raises(ValueError, match="future"):
        data.save_mood(conn, uid, "2026-10-15", 3)


# =====================================================================
# Dashboard and history
# =====================================================================

def test_dashboard(conn):
    uid = make_user(conn, "sam")                                  # goal 10,000
    put_steps(conn, uid, MON, 11000)
    put_steps(conn, uid, MON + timedelta(days=1), 12000)
    data.save_steps(conn, uid, None, 5000, "manual")
    d = data.dashboard(conn, uid, TODAY)
    assert d["today_steps"] == 5000
    assert d["daily_goal"] == 10000
    assert d["goal_percent"] == 50
    assert d["streak"] == 2                                       # Mon + Tue; today not yet met
    assert d["weekly_total"] == 28000
    assert (d["tier"], d["next_tier"], d["steps_to_next_tier"]) == ("Bronze", "Silver", 7000)
    assert [b["key"] for b in d["badges"]] == ["first_log", "ten_k", "streak_3"][:len(d["badges"])]
    assert d["badges"][0]["name"] == "First Steps"
    assert d["mood_today"] is None and d["water_today"] == 0


def test_dashboard_unknown_user(conn):
    with pytest.raises(ValueError):
        data.dashboard(conn, 999, TODAY)


def test_history(conn):
    uid = make_user(conn, "sam")
    put_steps(conn, uid, days_ago(1), 12000, source="ios_shortcut")
    data.save_mood(conn, uid, days_ago(1), 4)
    h = data.history(conn, uid, 7, TODAY)
    assert len(h) == 7
    assert h[0]["date"] == days_ago(6) and h[-1]["date"] == TODAY.isoformat()
    assert h[-2] == {"date": days_ago(1), "steps": 12000, "goal_met": True,
                     "mood": 4, "source": "ios_shortcut"}
    assert h[-1] == {"date": TODAY.isoformat(), "steps": 0, "goal_met": False,
                     "mood": None, "source": None}


# =====================================================================
# Leaderboards
# =====================================================================

def _board_setup(conn):
    t1 = make_user(conn, "tc1", role="teacher", department="Science", age_band="adult_18_39")
    t2 = make_user(conn, "tc2", role="teacher", department="Math", age_band="adult_18_39")
    t3 = make_user(conn, "tc3", role="teacher", department="Science", age_band="adult_18_39")
    s1 = make_user(conn, "st1", department="Grade 10A")
    admin = make_user(conn, "boss", role="admin", department=None, age_band="adult_18_39")
    put_steps(conn, t1, MON, 20000, updated_at="2026-10-12T21:00:00+04:00")
    put_steps(conn, t2, MON, 20000, updated_at="2026-10-12T20:00:00+04:00")  # same total, earlier
    put_steps(conn, s1, MON, 15000)
    put_steps(conn, admin, MON, 99999)
    return t1, t2, t3, s1


def test_teacher_board_ties_go_to_earlier_update(conn):
    t1, t2, t3, _ = _board_setup(conn)
    board = data.leaderboard(conn, "teacher", TODAY)
    assert [r["user_id"] for r in board] == [t2, t1]   # t3 has no steps: left off
    assert board[0] == {"rank": 1, "name": "Tc2", "department": "Math", "value": 20000,
                        "label": "20,000 steps", "user_id": t2,
                        "avatar": None, "avatar_color": None}


def test_student_board_excludes_admin(conn):
    _, _, _, s1 = _board_setup(conn)
    board = data.leaderboard(conn, "student", TODAY)
    assert [r["user_id"] for r in board] == [s1]


def test_department_board_counts_zero_members(conn):
    _board_setup(conn)
    board = data.leaderboard(conn, "department", TODAY)
    by_name = {r["name"]: r for r in board}
    assert by_name["Science"]["value"] == 10000      # (20,000 + 0) / 2 members
    assert by_name["Math"]["value"] == 20000
    assert by_name["Grade 10A"]["value"] == 15000
    assert [r["name"] for r in board] == ["Math", "Grade 10A", "Science"]
    assert all(r["user_id"] is None for r in board)


def test_effort_board(conn):
    t1, t2, _, s1 = _board_setup(conn)               # teachers' goal 8,000; student 10,000
    board = data.leaderboard(conn, "effort", TODAY)
    values = {r["user_id"]: r["value"] for r in board}
    assert values[t1] == round(20000 / 56000 * 100)  # 36%
    assert values[s1] == round(15000 / 70000 * 100)  # 21%
    assert board[0]["label"].endswith("% of weekly goal")


def test_improvement_board_compares_same_days(conn):
    uid = make_user(conn, "sam")
    lazy = make_user(conn, "mia")
    put_steps(conn, uid, LAST_MON, 10000)            # Mon last week
    put_steps(conn, uid, LAST_MON + timedelta(days=5), 50000)  # Sat last week: not compared
    put_steps(conn, uid, MON, 12000)
    put_steps(conn, lazy, MON, 9000)                 # no steps last week: not on this board
    board = data.leaderboard(conn, "improvement", TODAY)
    assert len(board) == 1
    assert board[0]["value"] == 20 and board[0]["label"] == "+20% vs last week"


def test_unknown_board(conn):
    with pytest.raises(ValueError):
        data.leaderboard(conn, "parents", TODAY)


# =====================================================================
# Weekly Wrap-Up
# =====================================================================

def test_weekly_wrapup(conn):
    uid = make_user(conn, "sam")                     # goal 10,000
    put_steps(conn, uid, LAST_MON, 10000)
    put_steps(conn, uid, LAST_MON + timedelta(days=1), 10000)
    put_steps(conn, uid, LAST_MON + timedelta(days=4), 30000)
    put_steps(conn, uid, MON, 12000)
    put_steps(conn, uid, MON + timedelta(days=1), 12000)
    w = data.weekly_wrapup(conn, uid, TODAY)
    assert w["this_week"] == 24000
    assert w["last_week"] == 50000
    assert w["change_percent"] == 20                 # 24,000 vs 20,000 (Mon-Wed last week)
    assert (w["tier"], w["last_tier"]) == ("Bronze", "Silver")
    assert w["best_day"] == {"date": "2026-10-12", "steps": 12000}   # tie: earlier day
    assert [d["day"] for d in w["daily"]] == ["Mon", "Tue", "Wed"]
    assert w["insight"] == "You walked 20% more than last week. Nice."


def test_wrapup_mood_insight(conn):
    uid = make_user(conn, "sam")                     # goal 10,000
    for n, (steps, mood) in enumerate([(12000, 5), (11000, 4), (10000, 4),
                                       (3000, 3), (2000, 2), (4000, 3)], start=1):
        put_steps(conn, uid, days_ago(n), steps)
        data.save_mood(conn, uid, days_ago(n), mood)
    w = data.weekly_wrapup(conn, uid, TODAY)
    assert len(w["mood_vs_steps"]) == 6
    assert w["insight"] == ("On days you hit your goal, your average mood was 4.3 "
                            "vs 2.7 on other days.")


def test_wrapup_empty_week(conn):
    uid = make_user(conn, "sam")
    w = data.weekly_wrapup(conn, uid, TODAY)
    assert w["this_week"] == 0 and w["best_day"] is None and w["change_percent"] is None
    assert "No steps yet" in w["insight"]


# =====================================================================
# Challenges
# =====================================================================

def test_challenges(conn):
    t1, _, _, s1 = _board_setup(conn)
    cid = data.create_challenge(conn, "RAK to Dubai", "Walk 120 km together", "school_distance",
                                171429, "2026-10-12", "2026-11-12")
    data.create_challenge(conn, "Dept Step-Off", "", "department", None, "2026-10-12", "2026-10-18")
    data.create_challenge(conn, "Old one", None, "department", None, "2026-09-01", "2026-09-30")
    data.create_challenge(conn, "Later", None, "department", None, "2026-11-01", "2026-11-07")

    active = data.active_challenges(conn, TODAY)
    assert [c["title"] for c in active] == ["RAK to Dubai", "Dept Step-Off", "Later"]
    rak = active[0]
    assert rak["total_steps"] == 55000                # teachers + student, admin not counted
    assert rak["km"] == 38.5 and rak["target_km"] == 120.0
    assert rak["percent"] == 32
    assert rak["standings"][0]["department"] == "Math"
    assert active[1]["percent"] is None and active[1]["description"] is None
    assert active[2]["total_steps"] == 0 and active[2]["standings"] == []

    data.close_challenge(conn, cid)
    assert "RAK to Dubai" not in [c["title"] for c in data.active_challenges(conn, TODAY)]


@pytest.mark.parametrize("args, message", [
    (("", None, "department", None, "2026-10-12", "2026-10-18"), "title"),
    (("X", None, "race", None, "2026-10-12", "2026-10-18"), "kind"),
    (("X", None, "school_distance", None, "2026-10-12", "2026-10-18"), "target_steps"),
    (("X", None, "department", None, "2026-10-18", "2026-10-12"), "end date"),
    (("X", None, "department", None, "18/10/2026", "2026-10-20"), "YYYY-MM-DD"),
])
def test_create_challenge_rejects(conn, args, message):
    with pytest.raises(ValueError, match=message):
        data.create_challenge(conn, *args)


def test_close_missing_challenge(conn):
    with pytest.raises(ValueError):
        data.close_challenge(conn, 42)


def test_suggested_distance_target(conn):
    assert data.suggested_distance_target(conn, 10) == 1 * 7000 * 10   # nobody yet: minimum 1
    _board_setup(conn)
    # 3 active players (t1, t2, s1); the admin and t3 are not counted
    assert data.suggested_distance_target(conn, 30) == 3 * 7000 * 30


# =====================================================================
# Impact numbers
# =====================================================================

def test_impact_stats(conn):
    uid = make_user(conn, "sam")                      # goal 10,000
    conn.execute("UPDATE users SET created_at = '2026-10-10T09:00:00+04:00' WHERE id = ?", (uid,))
    put_steps(conn, uid, "2026-10-08", 4000, source="manual")        # before joining
    put_steps(conn, uid, "2026-10-09", 6000, source="manual")        # before joining
    put_steps(conn, uid, "2026-10-12", 11000, source="ios_shortcut")
    put_steps(conn, uid, "2026-10-13", 9000, source="android_app")
    data.save_mood(conn, uid, "2026-10-12", 5)
    data.save_mood(conn, uid, "2026-10-13", 3)
    stats = data.impact_stats(conn)
    assert stats["avg_before"] == 5000
    assert stats["avg_during"] == 10000
    assert stats["users_hitting_goal"] == 1
    assert stats["entries_by_source"] == {"manual": 2, "ios_shortcut": 1,
                                          "android_app": 1, "other": 0}
    assert (stats["mood_goal_days"], stats["mood_other_days"]) == (5.0, 3.0)


def test_impact_stats_empty(conn):
    stats = data.impact_stats(conn)
    assert stats["avg_before"] is None and stats["users_hitting_goal"] == 0


# =====================================================================
# Adaptive goals
# =====================================================================

def test_update_weekly_goals(conn):
    keen = make_user(conn, "keen")
    custom = make_user(conn, "custom")
    new = make_user(conn, "new")
    data.set_custom_goal(conn, custom, 5000)
    for n in range(1, 15):                           # 14 finished days
        put_steps(conn, keen, days_ago(n), 8000)
        put_steps(conn, custom, days_ago(n), 8000)
    put_steps(conn, keen, TODAY, 50000)              # today is not counted
    for n in range(1, 10):
        put_steps(conn, new, days_ago(n), 8000)      # only 9 days

    assert data.update_weekly_goals(conn, TODAY) == 1
    assert data.get_user(conn, keen)["daily_goal"] == 8750
    assert data.get_user(conn, custom)["daily_goal"] == 5000
    assert data.get_user(conn, new)["daily_goal"] == 10000


def test_maybe_update_goals_runs_once_per_week(conn):
    assert data.maybe_update_goals(conn, TODAY) is True
    assert data.maybe_update_goals(conn, TODAY + timedelta(days=4)) is False   # same week (Sun)
    assert data.maybe_update_goals(conn, TODAY + timedelta(days=5)) is True    # next Monday
