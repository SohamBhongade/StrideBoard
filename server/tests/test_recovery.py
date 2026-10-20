"""Recovery email on an account, and 'Forgot your PIN?'."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import data
from conftest import make_user

S = "test-secret"
T0 = datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo("Asia/Dubai"))


def link(conn, uid, email="strideboard.alsout@gmail.com"):
    cid, _, code = data.start_email_link(conn, S, uid, email, now=T0)
    data.finish_email_link(conn, cid, uid, code, now=T0)


def test_link_then_reset_pin(conn):
    uid = make_user(conn, "soham.admin", role="admin", department=None, pin="1111")
    assert not data.has_email(conn, uid)
    link(conn, uid)
    assert data.has_email(conn, uid)
    cid, to, code = data.start_pin_reset(conn, S, "StrideBoard.AlSout@gmail.com", now=T0)
    assert data.finish_pin_reset(conn, cid, code, "246810", "246810", now=T0) == uid
    assert data.authenticate(conn, "soham.admin", "246810")
    assert not data.authenticate(conn, "soham.admin", "1111")
    with pytest.raises(ValueError, match="expired"):             # a code works once
        data.finish_pin_reset(conn, cid, code, "135790", "135790", now=T0)


def test_reset_for_unknown_email_reveals_nothing(conn):
    make_user(conn)
    assert data.start_pin_reset(conn, S, "nobody@gmail.com", now=T0) is None


def test_email_can_belong_to_one_account(conn):
    a, b = make_user(conn, "aaa"), make_user(conn, "bbb")
    link(conn, a)
    with pytest.raises(ValueError, match="another account"):
        data.start_email_link(conn, S, b, "strideboard.alsout@gmail.com", now=T0)
    with pytest.raises(ValueError, match="already your"):
        data.start_email_link(conn, S, a, "strideboardalsout@gmail.com", now=T0)
    data.remove_email(conn, a)
    link(conn, b)                                               # free again after removing


def test_wrong_code_and_pin_checks(conn):
    uid = make_user(conn, pin="1111")
    link(conn, uid)
    cid, _, code = data.start_pin_reset(conn, S, "strideboard.alsout@gmail.com", now=T0)
    with pytest.raises(ValueError, match="don't match"):
        data.finish_pin_reset(conn, cid, code, "2222", "3333", now=T0)
    wrong = "000000" if code != "000000" else "111111"
    with pytest.raises(ValueError, match="4 tries left"):
        data.finish_pin_reset(conn, cid, wrong, "2222", "2222", now=T0)
    with pytest.raises(ValueError, match="expired"):
        data.finish_pin_reset(conn, cid, code, "2222", "2222", now=T0 + timedelta(minutes=30))
    assert data.authenticate(conn, "sam", "1111")


def test_link_code_only_for_that_user(conn):
    a, b = make_user(conn, "aaa"), make_user(conn, "bbb")
    cid, _, code = data.start_email_link(conn, S, a, "x@gmail.com", now=T0)
    with pytest.raises(ValueError, match="expired"):
        data.finish_email_link(conn, cid, b, code, now=T0)
