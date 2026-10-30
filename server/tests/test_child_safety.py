"""Child safety: parents approve under-13 accounts, the word filter, and reports."""
import re
from datetime import timedelta

import pytest

import app as A
import data
import db
import wordfilter


# ------------------------------------------------------------- word filter

@pytest.mark.parametrize("name", [
    "Hassan Ali", "Assad Khan", "Dickson Mathew", "Shitanshu Rao", "Cassandra Lee", "Kamini Iyer",
    "Pornima Kale", "Nazir Ahmed", "Harshita Sharma", "Kalbani Saeed", "Abi Tchandran", "Alan Samuel D S",
    "زبيدة محمد", "دخول المدرسة", "Walk to Dubai", "Pedometer Club", "Crisis Team", "Grade 10A walkers"])
def test_real_names_and_words_pass(name):
    assert wordfilter.is_clean(name)


@pytest.mark.parametrize("text", [
    "fuck", "F.U.C.K", "f u c k", "fu ck", "fuuuck", "sh1t", "a$$", "b1tch", "motherfucker", "Bhenchod",
    "chutiya", "Saala", "kos omak", "kosomak", "ibn el kalb", "a7a", "Yel3an", "شرموطة", "كسمك", "كس",
    "حمار", "n1gger", "porn", "hitler", "stupid", "Shiiit"])
def test_rude_words_are_blocked(text):
    assert not wordfilter.is_clean(text)


def test_filter_guards_every_way_in(conn):
    with pytest.raises(ValueError, match="isn't allowed"):
        data.create_user(conn, "rude", "Big Shit", "student", "Grade 10A", "teen_13_17", "4826")
    uid = data.create_user(conn, "sam", "Sam Khan", "student", "Grade 10A", "teen_13_17", "4826")
    with pytest.raises(ValueError, match="isn't allowed"):
        data.update_my_details(conn, uid, "Sam B1tch", "Grade 10A")
    with pytest.raises(ValueError, match="isn't allowed"):
        data.rename_person(conn, uid, "Kos Omak")
    with pytest.raises(ValueError, match="isn't allowed"):
        data.create_challenge(conn, "Stupid walk", None, "department", None, "2026-10-01", "2026-10-31")
    result = data.bulk_create_users(conn, "username,display_name,role,department,age_band,pin\n"
                                          "x1,Fuck Off,student,Grade 10A,teen_13_17,4826\n")
    assert result["created"] == 0 and result["errors"]


# ------------------------------------------------------------- parent consent

@pytest.fixture()
def site(tmp_path, monkeypatch):
    monkeypatch.setattr(A.mailer, "ready", lambda: True)
    monkeypatch.setattr(A.config, "SIGNUP_OPEN", True)
    web = A.create_app()
    path = str(tmp_path / "web.sqlite3")
    sent = {"codes": [], "parents": []}
    web.config.update(TESTING=True, DATABASE=path,
                      SEND_CODE=lambda to, code, purpose="signup": sent["codes"].append((to, code)),
                      SEND_PARENT=lambda to, name, link: sent["parents"].append((to, name, link)))
    conn = db.connect(path)
    db.create_tables(conn)
    conn.close()
    c = web.test_client()
    with c.session_transaction() as s:
        s["csrf"] = "x"
    return c, path, sent


def _signup(c, sent, band="under_13", parent="mum@example.com", name="Amal Khan"):
    r = c.post("/signup", data={"csrf": "x", "agree_terms": "1", "agree_privacy": "1", "role": "student",
                                "display_name": name, "class": "Grade 9C", "age_band": band,
                                "email": "amal@example.com", "parent_email": parent, "pin": "4826",
                                "pin_again": "4826", "code": A.config.JOIN_CODE})
    return r


def test_under_13_needs_a_parent_email(site):
    c, path, sent = site
    page = _signup(c, sent, parent="").get_data(as_text=True)
    assert "parent or guardian" in page and not sent["codes"]


def test_under_13_waits_for_a_parent_then_logs_in(site):
    c, path, sent = site
    _signup(c, sent)
    code = sent["codes"][-1][1]
    r = c.post("/signup/verify", data={"csrf": "x", "verify_code": code})
    assert r.headers["Location"].endswith("/login")                 # not logged in yet
    to, name, link = sent["parents"][-1]
    assert to == "mum@example.com" and name == "Amal Khan"
    with c.session_transaction() as s:
        s["csrf"] = "x"
    page = c.post("/login", data={"csrf": "x", "username": "Amal Khan", "pin": "4826"}).get_data(as_text=True)
    assert "waiting for your parent" in page
    token = link.rsplit("/", 1)[1]
    page = c.get(f"/parent/{token}").get_data(as_text=True)
    assert "Approve Amal Khan" in page or "Approve</span> Amal Khan" in page
    c.post(f"/parent/{token}", data={"csrf": "x", "choice": "approve"})       # no tick: nothing happens
    conn = db.connect(path)
    assert conn.execute("SELECT parent_status FROM users").fetchone()[0] == "pending"
    c.post(f"/parent/{token}", data={"csrf": "x", "choice": "approve", "agree": "1"})
    row = conn.execute("SELECT parent_status, parent_email FROM users").fetchone()
    assert tuple(row) == ("given", None)                                   # parent's email deleted
    r = c.post("/login", data={"csrf": "x", "username": "Amal Khan", "pin": "4826"})
    assert r.status_code == 302 and "/login" not in r.headers["Location"]


def test_parent_can_decline_or_withdraw(site):
    c, path, sent = site
    _signup(c, sent)
    c.post("/signup/verify", data={"csrf": "x", "verify_code": sent["codes"][-1][1]})
    token = sent["parents"][-1][2].rsplit("/", 1)[1]
    with c.session_transaction() as s:      # the parent's own browser
        s["csrf"] = "x"
    c.post(f"/parent/{token}", data={"csrf": "x", "choice": "approve", "agree": "1"})
    page = c.post(f"/parent/{token}", data={"csrf": "x", "choice": "withdraw"}).get_data(as_text=True)
    assert "Account deleted" in page
    assert db.connect(path).execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert c.get(f"/parent/{token}").status_code == 404


def test_teen_sign_up_needs_no_parent(site):
    c, path, sent = site
    _signup(c, sent, band="teen_13_17", parent="")
    r = c.post("/signup/verify", data={"csrf": "x", "verify_code": sent["codes"][-1][1]})
    assert r.headers["Location"].endswith("/") and not sent["parents"]


def test_unanswered_accounts_are_removed(conn):
    uid = data.create_user(conn, "kid", "Kid One", "student", "Grade 9C", "under_13", "4826")
    old = (data._now(None) - timedelta(days=8)).isoformat(timespec="seconds")
    conn.execute("UPDATE users SET parent_status = 'pending', parent_email = 'p@x.com', created_at = ? "
                 "WHERE id = ?", (old, uid))
    conn.commit()
    assert data.clear_unapproved_children(conn) == 1


def test_students_cant_switch_themselves_to_under_13(site):
    c, path, sent = site
    conn = db.connect(path)
    uid = data.create_user(conn, "teen", "Teen One", "student", "Grade 9C", "teen_13_17", "4826")
    conn.close()
    with c.session_transaction() as s:
        s["user_id"] = uid
    c.post("/settings", data={"csrf": "x", "action": "age_band", "age_band": "under_13"})
    assert db.connect(path).execute("SELECT age_band FROM users").fetchone()[0] == "teen_13_17"


# ------------------------------------------------------------- reports

@pytest.fixture()
def school(tmp_path):
    web = A.create_app()
    path = str(tmp_path / "s.sqlite3")
    web.config.update(TESTING=True, DATABASE=path)
    conn = db.connect(path)
    db.create_tables(conn)
    ids = {n: data.create_user(conn, n.split()[0].lower(), n, "student", "Grade 10A", "teen_13_17", "4826")
           for n in ("Amal Khan", "Omar Saeed")}
    ids["admin"] = data.create_user(conn, "boss.admin", "Boss Admin", "admin", None, "adult_18_39", "4826")
    data.save_steps(conn, ids["Omar Saeed"], A.today(), 5000, "manual")
    conn.close()

    def client(uid):
        c = web.test_client()
        with c.session_transaction() as s:
            s["user_id"] = uid
            s["csrf"] = "x"
        return c
    return client, path, ids


def test_report_flow(school):
    client, path, ids = school
    amal = client(ids["Amal Khan"])
    page = amal.get("/leaderboard").get_data(as_text=True)
    assert f'/report/{ids["Omar Saeed"]}' in page and f'/report/{ids["Amal Khan"]}' not in page   # not yourself
    assert "Cheating on steps" in amal.get(f'/report/{ids["Omar Saeed"]}').get_data(as_text=True)
    amal.post(f'/report/{ids["Omar Saeed"]}', data={"csrf": "x", "reason": "name", "note": "rude nickname"})
    amal.post(f'/report/{ids["Omar Saeed"]}', data={"csrf": "x", "reason": "name"})            # duplicate ignored
    conn = db.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1
    admin = client(ids["admin"])
    overview = admin.get("/admin").get_data(as_text=True)
    assert "/admin/reports" in overview and '<span class="tab-count">1</span>' in overview
    assert "rude nickname" not in overview                       # reports live on their own tab
    page = admin.get("/admin/reports").get_data(as_text=True)
    assert "Omar Saeed" in page and "Rude or fake name" in page and "rude nickname" in page
    # Type dropdown (only types that have reports, with counts) and a name search
    assert '<option value="name">Rude or fake name · 1</option>' in page
    assert 'value="cheating"' not in page.split("data-report-type")[1].split("</select>")[0]
    assert "data-report-search" in page and 'data-reason="name"' in page
    assert 'data-search="amal khan omar saeed' in page          # reporter and reported person
    rid = conn.execute("SELECT id FROM reports").fetchone()[0]
    r = admin.post("/admin", data={"csrf": "x", "action": "report_done", "report_id": rid})
    assert r.headers["Location"].endswith("/admin/reports")      # back to the Reports tab
    assert conn.execute("SELECT status FROM reports").fetchone()[0] == "done"


def test_report_rules(conn):
    a = data.create_user(conn, "aaa", "Aa Bb", "student", "Grade 10A", "teen_13_17", "4826")
    b = data.create_user(conn, "bbb", "Cc Dd", "student", "Grade 10A", "teen_13_17", "4826")
    with pytest.raises(ValueError, match="yourself"):
        data.report_person(conn, a, a, "name")
    with pytest.raises(ValueError, match="what's wrong"):
        data.report_person(conn, a, b, "nonsense")
    with pytest.raises(ValueError, match="isn't allowed"):
        data.report_person(conn, a, b, "other", "you are stupid")
    data.report_person(conn, a, b, "cheating")
    data.delete_people(conn, [b], acting_id=a, block_emails=False)
    assert conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0     # gone with the account


def test_students_cant_open_admin_reports(school):
    client, path, ids = school
    assert client(ids["Amal Khan"]).get("/admin/reports").status_code == 403
    assert client(ids["Amal Khan"]).post("/admin", data={"csrf": "x", "action": "report_done", "report_id": 1}).status_code in (302, 403)
