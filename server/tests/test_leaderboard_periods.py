"""Leaderboards for today, this week, this month and all time, plus name search.

Today is fixed to Wednesday 2026-10-14 (see conftest.py).
"""
from datetime import date, timedelta

import pytest

import app as A
import data
import db
from conftest import TODAY, make_user, put_steps


def test_period_bounds():
    assert data.period_bounds("day", TODAY)[:2] == (TODAY, TODAY)
    assert data.period_bounds("week", TODAY)[:2] == (date(2026, 10, 12), date(2026, 10, 18))
    start, end, prev_start, prev_end, goal_days = data.period_bounds("month", TODAY)
    assert (start, end, goal_days) == (date(2026, 10, 1), date(2026, 10, 31), 31)
    assert (prev_start, prev_end) == (date(2026, 9, 1), date(2026, 9, 14))   # same days so far
    assert data.period_bounds("all", TODAY)[2:] == (None, None, None)
    # 31 March: last month (February) is shorter, so the comparison stops at its last day
    _, _, p0, p1, _ = data.period_bounds("month", date(2026, 3, 31))
    assert (p0, p1) == (date(2026, 2, 1), date(2026, 2, 28))
    with pytest.raises(ValueError):
        data.period_bounds("year", TODAY)


def test_each_period_counts_its_own_days(conn):
    sam = make_user(conn, "sam")
    mia = make_user(conn, "mia")
    put_steps(conn, sam, TODAY, 3000)                       # today
    put_steps(conn, mia, TODAY - timedelta(days=1), 9000)   # Tuesday: this week, not today
    put_steps(conn, sam, date(2026, 10, 2), 20000)          # earlier this month
    put_steps(conn, mia, date(2026, 3, 5), 50000)           # months ago
    board = lambda period: [(r["name"], r["value"]) for r in data.leaderboard(conn, "student", TODAY, period=period)]
    assert board("day") == [("Sam", 3000)]
    assert board("week") == [("Mia", 9000), ("Sam", 3000)]
    assert board("month") == [("Sam", 23000), ("Mia", 9000)]
    assert board("all") == [("Mia", 59000), ("Sam", 23000)]


def test_department_board_follows_the_period(conn):
    a = make_user(conn, "amy", department="Grade 9A")
    make_user(conn, "ben", department="Grade 9A")
    put_steps(conn, a, date(2026, 10, 1), 8000)
    rows = data.leaderboard(conn, "department", TODAY, period="month")
    assert rows[0]["name"] == "Grade 9A" and rows[0]["value"] == 4000      # (8,000 + 0) / 2
    assert data.leaderboard(conn, "department", TODAY, period="day")[0]["value"] == 0


def test_effort_uses_the_period_goal(conn):
    sam = make_user(conn, "sam")                     # student goal 10,000 a day
    put_steps(conn, sam, TODAY, 5000)
    day = data.leaderboard(conn, "effort", TODAY, period="day")[0]
    assert day["value"] == 50 and day["label"] == "50% of daily goal"
    month = data.leaderboard(conn, "effort", TODAY, period="month")[0]
    assert month["value"] == round(5000 / 310000 * 100) and month["label"].endswith("of monthly goal")
    with pytest.raises(ValueError):
        data.leaderboard(conn, "effort", TODAY, period="all")


def test_improvement_today_is_against_yesterday(conn):
    sam = make_user(conn, "sam")
    put_steps(conn, sam, TODAY - timedelta(days=1), 4000)
    put_steps(conn, sam, TODAY, 5000)
    row = data.leaderboard(conn, "improvement", TODAY, period="day")[0]
    assert row["value"] == 25 and row["label"] == "+25% vs yesterday"
    with pytest.raises(ValueError):
        data.leaderboard(conn, "improvement", TODAY, period="all")


def test_default_is_still_this_week(conn):
    sam = make_user(conn, "sam")
    put_steps(conn, sam, date(2026, 10, 2), 20000)          # this month, last week
    assert data.leaderboard(conn, "student", TODAY) == []


# ------------------------------------------------------------- the page

@pytest.fixture()
def site(tmp_path):
    web = A.create_app()
    path = str(tmp_path / "web.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    today = A.today()
    ids = {}
    for name, steps in (("Aisha Khan", 9000), ("Omar Saeed", 7000), ("Maryam Rahman", 5000)):
        uid = data.create_user(conn, name.split()[0].lower(), name, "student", "Grade 10A", "teen_13_17", "1234")
        data.save_steps(conn, uid, today, steps, "manual")
        ids[name] = uid
    conn.close()
    c = web.test_client()
    with c.session_transaction() as s:
        s["user_id"] = ids["Maryam Rahman"]
        s["csrf"] = "x"
    return c


def test_page_has_period_dropdown(site):
    page = site.get("/leaderboard").get_data(as_text=True)
    assert 'name="period"' in page
    for label in ("Today", "This week", "This month", "All time"):
        assert f">{label}</option>" in page
    assert "Monday to Sunday" in page


def test_page_switches_period(site):
    page = site.get("/leaderboard?period=all").get_data(as_text=True)
    assert "All-time" in page and 'value="all" selected' in page and "Aisha K." in page
    page = site.get("/leaderboard?period=nonsense").get_data(as_text=True)
    assert 'value="week" selected' in page


def test_effort_has_no_all_time(site):
    page = site.get("/leaderboard?view=effort&period=all").get_data(as_text=True)
    assert ">All time</option>" not in page and 'value="week" selected' in page


def test_search_finds_names_and_keeps_ranks(site):
    page = site.get("/leaderboard?q=omar").get_data(as_text=True)
    assert "Omar S." in page and "Aisha K." not in page
    assert "1 match for" in page and ">2<" in page                 # Omar keeps rank 2
    page = site.get("/leaderboard?q=zzz").get_data(as_text=True)
    assert "No one called" in page


# ------------------------------------------------------------- the leaderboard screen (/board, the desktop app)

@pytest.fixture()
def screen(tmp_path):
    web = A.create_app()
    path = str(tmp_path / "screen.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    today = A.today()
    for name, steps in (("Aisha Khan", 9000), ("Omar Saeed", 7000), ("Maryam Rahman", 5000), ("Lina Odeh", 3000)):
        uid = data.create_user(conn, name.split()[0].lower(), name, "student", "Grade 10A", "teen_13_17", "1234")
        data.save_steps(conn, uid, today, steps, "manual")
    key = data.board_key(conn) if hasattr(data, "board_key") else None
    conn.close()
    return web.test_client(), key


def _key(screen):
    client, key = screen
    if key is None:
        pytest.skip("no screen-code helper")
    return client, key


def test_screen_period_dropdown(screen):
    c, key = _key(screen)
    page = c.get(f"/board?key={key}").get_data(as_text=True)
    assert 'name="period"' in page and 'value="week" selected' in page and "resets every Monday" in page
    page = c.get(f"/board?key={key}&period=month").get_data(as_text=True)
    assert 'value="month" selected' in page and "resets on the 1st" in page and "Aisha K." in page
    page = c.get(f"/board?key={key}&period=bogus").get_data(as_text=True)
    assert 'value="week" selected' in page


def test_screen_search(screen):
    c, key = _key(screen)
    page = c.get(f"/board?key={key}&q=lina").get_data(as_text=True)
    assert "Lina O." in page and "Aisha K." not in page and "1 match" in page
    assert ">4<" in page                                    # Lina keeps her real rank
    page = c.get(f"/board?key={key}&q=nobody").get_data(as_text=True)
    assert "No one called" in page


def test_screen_still_needs_the_code(screen):
    c, _ = screen
    assert c.get("/board?period=all&q=a").status_code == 403


def test_search_rule():
    rows = [{"name": "Rami Aziz", "department": "Grade 10A"}, {"name": "Noor Hamdan", "department": "Grade 11B"}]
    assert [r["name"] for r in data.board_search(rows, "ra")] == ["Rami Aziz"]      # not every "Grade"
    assert [r["name"] for r in data.board_search(rows, "10a")] == ["Rami Aziz"]     # class word
    assert [r["name"] for r in data.board_search(rows, "AMDA")] == ["Noor Hamdan"]  # any part of a name
    assert data.board_search(rows, "  ") == rows
