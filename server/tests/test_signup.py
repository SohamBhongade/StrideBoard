"""People making their own account: Student or Teacher, checked by an emailed code."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import config
import data
from conftest import make_user

SECRET = "test-secret"
T0 = datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo("Asia/Dubai"))


def start(conn, email="amal.k@gmail.com", username="amal.k", role="student", dept="Grade 10A",
          pin="4821", pin2="4821", now=T0):
    return data.start_signup(conn, SECRET, email, username, "Amal K", role, dept, "teen_13_17",
                             pin, pin2, now=now)


def test_sign_up_with_code_makes_the_account(conn):
    pid, to, code = start(conn)
    assert to == "amal.k@gmail.com" and len(code) == 6
    assert data.finish_signup(conn, pid, code, now=T0 + timedelta(minutes=2))
    user = data.authenticate(conn, "amal.k", "4821")
    assert user and user["role"] == "student" and user["department"] == "Grade 10A"
    assert data.pending_email(conn, pid) is None          # the address is not kept


def test_teacher_sign_up(conn):
    pid, _, code = start(conn, "mr.ali@school.ae", "mr.ali", role="Teacher", dept="Science")
    uid = data.finish_signup(conn, pid, code, now=T0)
    assert data.get_user(conn, uid)["role"] == "teacher"


@pytest.mark.parametrize("kw, message", [
    ({"role": "admin"}, "Student or Teacher"),
    ({"role": ""}, "Student or Teacher"),
    ({"dept": "  "}, "your class"),
    ({"role": "teacher", "dept": ""}, "your department"),
    ({"pin2": "4822"}, "don't match"),
    ({"pin": "12", "pin2": "12"}, "PIN must be"),
    ({"email": "not-an-email"}, "real email"),
    ({"username": "x"}, "username must be"),
])
def test_bad_forms_are_refused(conn, kw, message):
    with pytest.raises(ValueError, match=message):
        start(conn, **kw)


def test_one_account_per_inbox_even_with_gmail_tricks(conn):
    pid, _, code = start(conn)
    data.finish_signup(conn, pid, code, now=T0)
    for alias in ("AmalK@gmail.com", "a.m.a.l.k+2@googlemail.com"):
        with pytest.raises(ValueError, match="already an account"):
            start(conn, alias, "other.name")


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


def test_username_taken(conn):
    make_user(conn, "sam")
    with pytest.raises(ValueError, match="already taken"):
        start(conn, username="SAM")


def test_signup_never_offers_admin():
    assert "admin" not in config.SIGNUP_ROLES
