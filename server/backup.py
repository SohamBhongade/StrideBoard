"""Backups of the StrideBoard database, so the school's data survives any mistake.

Three layers:
  1. Daily: PythonAnywhere runs `python3 ~/strideboard/server/backup.py` once a day (Tasks tab).
     It saves a compressed copy next to the database, in backups/, and keeps the last 7.
  2. Weekly (Mondays): that same run also emails the copy to the site's own Gmail, so a copy
     exists outside PythonAnywhere too.
  3. Any time: the owner can download a copy from Admin > Backups.

A copy is taken with SQLite's own backup feature, so it is consistent even while people sync.
To restore: unzip the .gz file and put it in place of the database file (see README).
"""
import gzip
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

TZ = ZoneInfo(config.TIMEZONE)

KEEP_DAYS = 7          # a week of copies: a whole school year fits easily in the free disk space
EMAIL_LIMIT = 20_000_000   # Gmail refuses attachments over 25 MB; bigger copies get a note instead
PREFIX = "strideboard-backup-"


def folder_for(db_path):
    return Path(db_path).resolve().parent / "backups"


def snapshot(db_path):
    """The whole database as compressed bytes (.sqlite3.gz)."""
    src = sqlite3.connect(db_path)
    fd, tmp = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    try:
        dst = sqlite3.connect(tmp)
        with dst:
            src.backup(dst)
        dst.close()
        # Level 6: about 10x faster than the maximum (9) for a file only a few % bigger, so the
        # daily task stays well inside PythonAnywhere's free CPU time.
        return gzip.compress(Path(tmp).read_bytes(), compresslevel=6)
    finally:
        src.close()
        os.remove(tmp)


def file_name(now=None):
    return f"{PREFIX}{(now or datetime.now(TZ)):%Y-%m-%d}.sqlite3.gz"


def save_daily(db_path, now=None, keep=KEEP_DAYS):
    """Write today's backup into backups/ and delete ones older than the newest `keep`."""
    folder = folder_for(db_path)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / file_name(now)
    path.write_bytes(snapshot(db_path))
    for old in sorted(folder.glob(PREFIX + "*.sqlite3.gz"))[:-keep]:
        old.unlink()
    return path


def latest(db_path):
    """(file name, when it was made) of the newest automatic backup, or None."""
    files = sorted(folder_for(db_path).glob(PREFIX + "*.sqlite3.gz"))
    if not files:
        return None
    f = files[-1]
    return f.name, datetime.fromtimestamp(f.stat().st_mtime, TZ)


def main(argv=None):
    argv = argv or sys.argv[1:]
    db_path = config.DATABASE
    now = datetime.now(TZ)
    path = save_daily(db_path, now)
    print(f"Saved {path} ({path.stat().st_size / 1024:.0f} KB)")
    if now.weekday() == 0 or "--email" in argv:      # Mondays, or when asked
        import mailer
        try:
            blob = path.read_bytes()
            if len(blob) > EMAIL_LIMIT:
                to = mailer.send_backup(path.name, None)
                print(f"Too big to attach ({len(blob) / 1e6:.0f} MB): emailed {to} a reminder to download one")
            else:
                to = mailer.send_backup(path.name, blob)
                print(f"Emailed it to {to}")
        except ValueError as e:
            print(f"Couldn't email it: {e}")


if __name__ == "__main__":
    main()
