"""Nightly housekeeping: old working notes are trimmed, but nothing anyone sees changes."""
from datetime import timedelta

import backup
import data
from conftest import TODAY, make_user


def day(n):
    return (TODAY - timedelta(days=n)).isoformat()


def stamp(n):
    return day(n) + "T10:00:00+04:00"


def count(conn, table, uid=None):
    sql = f"SELECT COUNT(*) FROM {table}" + (" WHERE user_id = ?" if uid else "")
    return conn.execute(sql, (uid,) if uid else ()).fetchone()[0]


def test_exp_balance_and_history_survive_merging(conn):
    uid = make_user(conn)
    for n in range(100, 60, -1):       # 40 old rows (days 100..61)
        conn.execute("INSERT INTO exp_ledger (user_id, amount, reason, created_at) VALUES (?, 10, 'Mini challenge: x', ?)",
                     (uid, stamp(n)))
    conn.execute("INSERT INTO exp_ledger (user_id, amount, reason, created_at) VALUES (?, -150, 'Bought hat', ?)",
                 (uid, stamp(90)))
    conn.execute("INSERT INTO exp_ledger (user_id, amount, reason, created_at) VALUES (?, 25, 'Recent', ?)",
                 (uid, stamp(3)))
    conn.commit()
    balance = data.exp_balance(conn, uid)
    done = data.tidy_up(conn, TODAY)
    assert data.exp_balance(conn, uid) == balance == 40 * 10 - 150 + 25
    assert count(conn, "exp_ledger", uid) == 2          # one combined row + the recent one
    assert done["exp_ledger"] == 40      # 41 old rows became 1
    assert data.exp_history(conn, uid)[0]["reason"] == "Recent"
    # Running it again changes nothing.
    assert data.tidy_up(conn, TODAY)["exp_ledger"] == 0
    assert data.exp_balance(conn, uid) == balance


def test_exp_that_cancels_out_leaves_no_row(conn):
    uid = make_user(conn)
    for amount in (100, -100):
        conn.execute("INSERT INTO exp_ledger (user_id, amount, reason, created_at) VALUES (?, ?, 'x', ?)",
                     (uid, amount, stamp(80)))
    conn.commit()
    data.tidy_up(conn, TODAY)
    assert count(conn, "exp_ledger", uid) == 0 and data.exp_balance(conn, uid) == 0


def test_exercise_totals_and_best_days_survive_merging(conn):
    uid = make_user(conn)
    for n in (30, 30, 30, 20, 20, 2, 2):
        conn.execute("INSERT INTO exercises (user_id, date, type, amount, created_at) VALUES (?, ?, 'squats', 15, ?)",
                     (uid, day(n), stamp(n)))
    conn.commit()
    before = {t["key"]: (t["total"], t["best"]) for t in data.progression(conn, uid)}
    data.tidy_up(conn, TODAY)
    after = {t["key"]: (t["total"], t["best"]) for t in data.progression(conn, uid)}
    assert after == before and after["squats"] == (105, 45)
    assert count(conn, "exercises", uid) == 4           # day 30 and day 20 merged; recent day untouched


def test_old_mini_runs_go_but_today_counts_stay(conn):
    uid = make_user(conn)
    for n in (0, 0, 20, 40):
        conn.execute("INSERT INTO mini_runs (user_id, key, date, status, started_at) VALUES (?, 'squats_15', ?, 'done', ?)",
                     (uid, day(n), stamp(n)))
    conn.commit()
    data.tidy_up(conn, TODAY)
    assert count(conn, "mini_runs", uid) == 2
    assert data._done_today(conn, uid, TODAY.isoformat()) == {"squats_15": 2}


def test_reward_calendar_keeps_its_place(conn):
    uid = make_user(conn)
    for n in range(200, 99, -1):       # last claim was 100 days ago
        conn.execute("INSERT INTO daily_rewards (user_id, date, cycle, day, tier, reward, created_at) "
                     "VALUES (?, ?, 1, 5, 'Bronze', 'exp:10', ?)", (uid, day(n), stamp(n)))
    conn.commit()
    before = data.reward_status(conn, uid, TODAY)
    data.tidy_up(conn, TODAY)
    assert count(conn, "daily_rewards", uid) == 1        # only the latest claim is kept
    assert data.reward_status(conn, uid, TODAY) == before


def test_stale_samples_codes_and_screen_time_are_removed(conn):
    uid = make_user(conn)
    conn.execute("INSERT INTO step_samples (user_id, date, total, at) VALUES (?, ?, 5, ?)", (uid, day(10), stamp(10)))
    conn.execute("INSERT INTO step_samples (user_id, date, total, at) VALUES (?, ?, 5, ?)", (uid, day(0), stamp(0)))
    conn.execute("INSERT INTO screen_time (user_id, date, minutes) VALUES (?, ?, 5)", (uid, day(9)))
    conn.execute("INSERT INTO email_codes (purpose, user_id, email, email_hash, code_hash, sent_at, created_at) "
                 "VALUES ('reset', ?, 'a@b.c', 'h', 'c', ?, ?)", (uid, stamp(3), stamp(3)))
    conn.execute("INSERT INTO pending_signups (email, email_hash, code_hash, details, sent_at, created_at) "
                 "VALUES ('a@b.c', 'h', 'c', '{}', ?, ?)", (stamp(3), stamp(3)))
    conn.commit()
    data.tidy_up(conn, TODAY)
    assert count(conn, "step_samples") == 1
    for table in ("screen_time", "email_codes", "pending_signups"):
        assert count(conn, table) == 0


def test_real_data_is_never_touched(conn):
    uid = make_user(conn)
    data.save_steps(conn, uid, day(1), 9000, "android_app")
    conn.execute("INSERT INTO steps (user_id, date, steps, source, updated_at) VALUES (?, ?, 7000, 'manual', ?)",
                 (uid, day(300), stamp(300)))
    data.save_mood(conn, uid, day(1), 4)
    conn.commit()
    tables = ("steps", "moods", "water", "activities", "badges")
    before = {t: count(conn, t) for t in tables}
    data.tidy_up(conn, TODAY)
    assert {t: count(conn, t) for t in tables} == before


def test_file_shrinks_only_when_mostly_empty(conn):
    uid = make_user(conn)
    assert data.shrink_if_needed(conn) is False
    conn.executemany("INSERT INTO step_samples (user_id, date, total, at) VALUES (?, ?, 1, ?)",
                     [(uid, day(30), "x" * 200)] * 5000)
    conn.commit()
    data.tidy_up(conn, TODAY)
    assert data.shrink_if_needed(conn) is True
    assert data.shrink_if_needed(conn) is False


def test_nightly_task_backs_up_then_tidies(tmp_path, capsys):
    import db
    path = tmp_path / "live.sqlite3"
    conn = db.connect(str(path))
    db.create_tables(conn)
    uid = make_user(conn)
    conn.execute("INSERT INTO step_samples (user_id, date, total, at) VALUES (?, ?, 5, ?)", (uid, day(10), stamp(10)))
    conn.commit()
    conn.close()
    backup.tidy(str(path), TODAY)
    assert "step_samples 1" in capsys.readouterr().out


def test_daily_job_is_claimed_once_per_day(conn):
    assert data.claim_daily_job(conn, "2026-10-30") is True
    assert data.claim_daily_job(conn, "2026-10-30") is False      # another worker, same day
    assert data.claim_daily_job(conn, "2026-10-31") is True       # next day


def test_website_runs_the_daily_job_after_the_first_request(tmp_path, monkeypatch):
    """Free PythonAnywhere has no scheduled tasks, so the site runs backup + tidy itself."""
    import app as A
    ran = []
    monkeypatch.setattr(backup, "run_daily", lambda path, *a, **k: ran.append(path))
    import db
    path = str(tmp_path / "live.sqlite3")
    c0 = db.connect(path); db.create_tables(c0); c0.close()
    web = A.create_app()
    web.config.update(DATABASE=path)
    web.testing = False                     # the job is skipped in tests unless this is off
    c = web.test_client()
    # A real web server always closes each response; that's when the job runs.
    for url in ("/login", "/login", "/static/css/style.css"):
        c.get(url).close()
    assert ran == [path]                    # once, not on every page

    web2 = A.create_app()                   # a second worker on the same day
    web2.config.update(DATABASE=path)
    web2.testing = False
    web2.test_client().get("/login").close()
    assert ran == [path]


def test_run_daily_backs_up_tidies_and_emails_on_mondays(tmp_path, monkeypatch):
    from datetime import datetime
    import mailer
    sent = []
    monkeypatch.setattr(mailer, "send_backup", lambda name, blob: sent.append(name) or "site@gmail")
    import db
    path = tmp_path / "live.sqlite3"
    c = db.connect(str(path)); db.create_tables(c); make_user(c); c.close()
    backup.run_daily(str(path), datetime(2026, 10, 28, 3, 0, tzinfo=backup.TZ))   # Wednesday
    assert sent == [] and len(list(backup.folder_for(str(path)).iterdir())) == 1
    backup.run_daily(str(path), datetime(2026, 11, 2, 3, 0, tzinfo=backup.TZ))    # Monday
    assert len(sent) == 1
