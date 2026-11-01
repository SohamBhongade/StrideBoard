"""People making their own account: Student or Teacher, full name, checked by an emailed code."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import config
import data
from conftest import make_user

SECRET = "test-secret"
T0 = datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo("Asia/Dubai"))


def start(conn, email="amal.k@gmail.com", role="student", dept="Grade 10A",
          pin="4821", pin2="4821", now=T0, name="Amal Khan"):
    return data.start_signup(conn, SECRET, email, name, role, dept, "teen_13_17",
                             pin, pin2, now=now)


def test_sign_up_with_code_makes_the_account(conn):
    pid, to, code = start(conn)
    assert to == "amal.k@gmail.com" and len(code) == 6
    assert data.finish_signup(conn, pid, code, now=T0 + timedelta(minutes=2))
    user = data.authenticate_name(conn, "  amal   khan ", "4821")
    assert user and user["role"] == "student" and user["department"] == "Grade 10A"
    assert data.pending_email(conn, pid) is None          # the address is not kept


def test_teacher_sign_up(conn):
    pid, _, code = start(conn, "mr.ali@school.ae", role="Teacher", dept="Science", name="Ali Hassan")
    uid = data.finish_signup(conn, pid, code, now=T0)
    assert data.get_user(conn, uid)["role"] == "teacher"


@pytest.mark.parametrize("kw, message", [
    ({"role": "admin"}, "Student or Teacher"),
    ({"role": ""}, "Student or Teacher"),
    ({"dept": "  "}, "your class"),
    ({"dept": "Grade 13Z"}, "your class"),
    ({"role": "teacher", "dept": ""}, "your department"),
    ({"role": "teacher", "dept": "Grade 10A"}, "your department"),
    ({"dept": "Science"}, "your class"),
    ({"pin2": "4822"}, "don't match"),
    ({"pin": "12", "pin2": "12"}, "PIN must be"),
    ({"email": "not-an-email"}, "real email"),
    ({"name": "Amal"}, "full name"),
    ({"name": "   "}, "full name"),
])
def test_bad_forms_are_refused(conn, kw, message):
    with pytest.raises(ValueError, match=message):
        start(conn, **kw)


def test_one_account_per_inbox_even_with_gmail_tricks(conn):
    pid, _, code = start(conn)
    data.finish_signup(conn, pid, code, now=T0)
    for alias in ("AmalK@gmail.com", "a.m.a.l.k+2@googlemail.com"):
        with pytest.raises(ValueError, match="already an account"):
            start(conn, alias, name="Other Person")


def test_wrong_code_counts_down_then_locks(conn):
    pid, _, code = start(conn)
    wrong = "000000" if code != "000000" else "111111"
    for left in range(config.CODE_TRIES - 1, 0, -1):
        with pytest.raises(ValueError, match=f"{left} tr"):
            data.finish_signup(conn, pid, wrong, now=T0)
    with pytest.raises(ValueError):
        data.finish_signup(conn, pid, wrong, now=T0)
    with pytest.raises(ValueError, match="too many wrong"):
        data.finish_signup(conn, pid, code, now=T0)        # even the right one, until resent


def test_code_expires_and_resend_needs_a_wait(conn):
    pid, _, code = start(conn)
    with pytest.raises(ValueError, match="expired"):
        data.finish_signup(conn, pid, code, now=T0 + timedelta(minutes=config.CODE_MINUTES + 1))
    with pytest.raises(ValueError, match="please wait"):
        data.resend_signup_code(conn, pid, now=T0 + timedelta(seconds=10))
    to, new = data.resend_signup_code(conn, pid, now=T0 + timedelta(minutes=20))
    assert data.finish_signup(conn, pid, new, now=T0 + timedelta(minutes=21))


def test_no_username_and_full_name_login(conn):
    pid, _, code = start(conn)
    uid = data.finish_signup(conn, pid, code, now=T0)
    assert data.get_user(conn, uid)["username"].startswith("student")
    assert data.authenticate_name(conn, "AMAL KHAN", "4821")["id"] == uid
    assert data.authenticate_name(conn, "Amal Khan", "9999") is None
    assert data.authenticate_email(conn, SECRET, "amalk+x@googlemail.com", "4821")["id"] == uid


def test_full_names_must_be_unique(conn):
    make_user(conn, "sam", display_name="Sam Lee")
    with pytest.raises(ValueError, match="already uses the name"):
        start(conn, name="  sam   LEE ")
    pid, _, code = start(conn, name="Sam Ahmed Lee")
    data.finish_signup(conn, pid, code, now=T0)


def test_admin_made_accounts_still_log_in_with_username(conn):
    uid = make_user(conn, "soham.admin", role="admin", department=None, pin="2468")
    assert data.authenticate_name(conn, "soham.admin", "2468")["id"] == uid


def test_signup_never_offers_admin():
    assert "admin" not in config.SIGNUP_ROLES


def test_signup_lists():
    assert len(config.SIGNUP_CLASSES) == 14
    assert config.SIGNUP_CLASSES[0] == "Grade 9A" and config.SIGNUP_CLASSES[-1] == "Grade 12C"
    assert "Computer Science" in config.SIGNUP_DEPARTMENTS


# ---- Names that might be rude but might be real ("Possible real name" in Admin > Reports) ----

def test_maybe_real_name_signs_up_but_waits_off_the_boards(conn):
    import wordfilter
    assert wordfilter.needs_review("Kundan Lal") == "kundan" and wordfilter.needs_review("Amal Khan") is None
    assert wordfilter.needs_review("Dickson Mathew") is None                  # whole words only
    pid, _, code = start(conn, name="Kundan Lal")
    uid = data.finish_signup(conn, pid, code, now=T0 + timedelta(minutes=2))
    data.save_steps(conn, uid, None, 9000, "android_app")
    other = make_user(conn, "omar")
    data.save_steps(conn, other, None, 4000, "android_app")

    def on_board():
        return any(r.get("user_id") == uid for r in data.leaderboard(conn, "student", data.local_today()))

    assert not on_board()
    [row] = data.name_reviews(conn)
    assert (row["target"], row["word"], row["reason_label"]) == ("Kundan Lal", "kundan", "Possible real name")
    assert data.leaderboard(conn, "department", data.local_today())[0]["value"] > 0   # still counts for the class
    data.decide_name(conn, uid, approve=True)
    assert on_board() and data.name_reviews(conn) == []
    with pytest.raises(ValueError, match="already checked"):
        data.decide_name(conn, uid, approve=True)


def test_not_approved_deletes_and_blocks_until_the_owner_types_the_email(conn):
    pid, _, code = start(conn, email="Kundan.Lal+x@gmail.com", name="Kundan Lal")
    uid = data.finish_signup(conn, pid, code, now=T0 + timedelta(minutes=2))
    assert data.decide_name(conn, uid, approve=False) == "Kundan Lal"
    assert data.get_user(conn, uid) is None and data.name_reviews(conn) == []     # deleted: logged out
    assert data.blocked_emails(conn)[0]["name"] == "Kundan Lal"
    assert data.blocked_emails(conn)[0]["reason"] == "Name not approved"
    with pytest.raises(ValueError, match="can't be used"):
        start(conn, email="kundanlal@gmail.com", name="Kundan Lal")             # same inbox, still blocked
    with pytest.raises(ValueError, match="isn't blocked"):
        data.unblock_email(conn, SECRET, "someone.else@gmail.com")
    address, name = data.unblock_email(conn, SECRET, "kundan.lal@gmail.com")   # dots don't matter
    assert (address, name) == ("kundanlal@gmail.com", "Kundan Lal") and data.blocked_emails(conn) == []
    assert "kundan" not in str(conn.execute("SELECT * FROM blocked_emails").fetchall()).lower()
    pid, _, code = start(conn, email="kundan.lal@gmail.com", name="Kundan Lalith Kumar")
    assert data.finish_signup(conn, pid, code, now=T0 + timedelta(minutes=4))


def test_name_changes_are_checked_again(conn):
    uid = make_user(conn, "dick", display_name="Dick Smith")       # made by an admin: no hold
    assert data.name_reviews(conn) == []
    data.update_my_details(conn, uid, "Randi Joseph", "Grade 10A")   # chosen by themselves: held
    assert [r["word"] for r in data.name_reviews(conn)] == ["randi"]
    assert data.name_review_state(data.get_user(conn, uid)) == "pending"
    data.update_my_details(conn, uid, "Joseph Mathew", "Grade 10A")  # a clean name clears the hold
    assert data.name_reviews(conn) == []
    data.update_my_details(conn, uid, "Lund Peter", "Grade 10A")
    data.rename_person(conn, uid, "Peter Lund")                      # the owner's rename clears it too
    assert data.name_reviews(conn) == []


def test_maybe_real_names_are_still_blocked_in_titles_and_notes():
    import wordfilter
    with pytest.raises(ValueError):
        wordfilter.check("Dick walkers", "The title")
    wordfilter.check_name("Dick Smith")                               # fine as a name
