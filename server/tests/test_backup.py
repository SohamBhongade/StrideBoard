"""Backups: consistent copies, 14 kept, owner-only download."""
import gzip
import sqlite3
from datetime import datetime, timedelta

import pytest

import backup
import config
import data


def make_db(tmp_path):
    import db
    path = tmp_path / "live.sqlite3"
    conn = db.connect(str(path))
    db.create_tables(conn)
    uid = data.create_user(conn, "sam", "Sam Lee", "student", "Grade 9A", "teen_13_17", "1234")
    data.save_steps(conn, uid, None, 8123, "android_app")
    conn.close()
    return path


def test_snapshot_is_a_complete_database(tmp_path):
    path = make_db(tmp_path)
    raw = gzip.decompress(backup.snapshot(str(path)))
    copy = tmp_path / "copy.sqlite3"
    copy.write_bytes(raw)
    c = sqlite3.connect(copy)
    assert c.execute("SELECT steps FROM steps").fetchone()[0] == 8123
    assert c.execute("SELECT username FROM users").fetchone()[0] == "sam"


def test_daily_backups_keep_the_last_7(tmp_path):
    path = make_db(tmp_path)
    start = datetime(2026, 10, 1, 3, 0, tzinfo=backup.TZ)
    for d in range(20):
        backup.save_daily(str(path), start + timedelta(days=d))
    files = sorted(p.name for p in backup.folder_for(str(path)).iterdir())
    assert len(files) == 7 and files[0].endswith("2026-10-14.sqlite3.gz.enc") and files[-1].endswith("2026-10-20.sqlite3.gz.enc")
    assert backup.latest(str(path))[0] == files[-1]


@pytest.fixture()
def web(tmp_path):
    import app as A
    import db
    w = A.create_app()
    path = make_db(tmp_path)
    w.config.update(TESTING=True, DATABASE=str(path))
    conn = db.connect(str(path))
    owner = data.create_user(conn, config.OWNER_USERNAME, "Owner", "admin", None, "adult_18_39", "1234")
    other = data.create_user(conn, "teacher.admin", "Other Admin", "admin", None, "adult_18_39", "1234")
    conn.close()
    return w, owner, other


def as_user(w, uid):
    c = w.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["csrf"] = "x"
    return c


def test_only_the_owner_can_download_a_backup(web):
    w, owner, other = web
    r = as_user(w, owner).get("/admin/backup")
    assert r.status_code == 200 and r.headers["Content-Disposition"].startswith("attachment")
    assert gzip.decompress(r.data)[:15] == b"SQLite format 3"
    assert as_user(w, other).get("/admin/backup").status_code == 403
    page = as_user(w, owner).get("/admin").data.decode()
    assert "Download a backup" in page and "Automatic daily backups aren't on yet" in page
    assert "Download a backup" not in as_user(w, other).get("/admin").data.decode()


def test_saved_copies_are_encrypted_and_restore(tmp_path):
    path = make_db(tmp_path)
    saved = backup.save_daily(str(path))
    blob = saved.read_bytes()
    assert blob.startswith(backup.MAGIC) and b"SQLite format 3" not in blob and b"sam" not in blob
    out = tmp_path / "restored.sqlite3"
    backup.decrypt_file(saved, out)
    assert sqlite3.connect(out).execute("SELECT steps FROM steps").fetchone()[0] == 8123


def test_wrong_key_cant_read_a_copy(tmp_path, monkeypatch):
    path = make_db(tmp_path)
    saved = backup.save_daily(str(path))
    monkeypatch.setenv("STRIDEBOARD_BACKUP_KEY", "11" * 32)
    with pytest.raises(ValueError, match="wrong key"):
        backup.decrypt_file(saved, tmp_path / "x.sqlite3")


def test_old_plain_copies_still_count_and_get_pruned(tmp_path):
    path = make_db(tmp_path)
    folder = backup.folder_for(str(path))
    folder.mkdir(parents=True)
    for d in range(1, 9):
        (folder / f"{backup.PREFIX}2026-09-0{d}.sqlite3.gz").write_bytes(b"old")
    backup.save_daily(str(path), datetime(2026, 10, 1, 3, 0, tzinfo=backup.TZ))
    names = sorted(p.name for p in folder.iterdir())
    assert len(names) == 7 and names[-1].endswith(".enc")


def test_task_reads_the_sites_settings(tmp_path, monkeypatch):
    wsgi = tmp_path / "site_wsgi.py"
    wsgi.write_text('import os, sys\nos.environ["STRIDEBOARD_DATABASE"] = "/home/x/data.sqlite3"\n'
                    "os.environ['STRIDEBOARD_GMAIL_USER'] = 'a@b.c'\npath = '/x'\n")
    monkeypatch.delenv("STRIDEBOARD_DATABASE", raising=False)
    monkeypatch.delenv("STRIDEBOARD_GMAIL_USER", raising=False)
    backup.load_site_settings(str(tmp_path / "*_wsgi.py"))
    import os
    assert os.environ["STRIDEBOARD_DATABASE"] == "/home/x/data.sqlite3"
    assert os.environ["STRIDEBOARD_GMAIL_USER"] == "a@b.c"
    os.environ.pop("STRIDEBOARD_DATABASE"); os.environ.pop("STRIDEBOARD_GMAIL_USER")
