"""Backups of the StrideBoard database, so the school's data survives any mistake.

Three layers:
  1. Daily: PythonAnywhere runs `python3 ~/strideboard/server/backup.py` once a day (Tasks tab).
     It saves a compressed copy next to the database, in backups/, and keeps the last 7.
  2. Weekly (Mondays): that same run also emails the copy to the site's own Gmail, so a copy
     exists outside PythonAnywhere too.
  3. Any time: the owner can download a copy from Admin > Backups.

A copy is taken with SQLite's own backup feature, so it is consistent even while people sync.

Saved and emailed copies are ENCRYPTED (AES-256-GCM), so a copy sitting on the server or in
Gmail can't be read without the key. The key is STRIDEBOARD_BACKUP_KEY if set, otherwise it's
made from STRIDEBOARD_SECRET_KEY (so changing the secret key makes older copies unreadable:
set STRIDEBOARD_BACKUP_KEY to keep one key for good).
To restore: python3 backup.py --decrypt <file.enc> <out.sqlite3>, then put it in place (README).

The daily task doesn't run inside the website, so it reads the STRIDEBOARD_... settings from
the website's WSGI file first (database path, Gmail, keys), the same ones the site uses.
"""
import glob
import gzip
import hashlib
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def load_site_settings(pattern="/var/www/*_wsgi.py"):
    """Copy os.environ["STRIDEBOARD_..."] = "..." lines from the website's WSGI file into this
    process (anything already set wins). Lets the scheduled task use the site's settings."""
    line = re.compile(r'^\s*os\.environ\[\s*["\'](STRIDEBOARD_[A-Z0-9_]+)["\']\s*\]\s*=\s*["\']([^"\']*)["\']\s*$')
    for path in glob.glob(pattern):
        try:
            for text in Path(path).read_text().splitlines():
                m = line.match(text)
                if m:
                    os.environ.setdefault(m.group(1), m.group(2))
        except OSError:
            pass


if __name__ == "__main__":
    load_site_settings()   # before config reads the environment

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

TZ = ZoneInfo(config.TIMEZONE)

KEEP_DAYS = 7          # a week of copies: a whole school year fits easily in the free disk space
EMAIL_LIMIT = 20_000_000   # Gmail refuses attachments over 25 MB; bigger copies get a note instead
PREFIX = "strideboard-backup-"
MAGIC = b"SBENC1"          # start of an encrypted copy
ENC_SUFFIX = ".sqlite3.gz.enc"


def backup_key():
    """32 bytes for AES-256: STRIDEBOARD_BACKUP_KEY (64 hex characters), or made from the secret key."""
    given = os.environ.get("STRIDEBOARD_BACKUP_KEY", "").strip()
    if given:
        try:
            key = bytes.fromhex(given)
            if len(key) == 32:
                return key
        except ValueError:
            pass
        raise ValueError("STRIDEBOARD_BACKUP_KEY must be 64 hex characters")
    secret = os.environ.get("STRIDEBOARD_SECRET_KEY", config.SECRET_KEY)
    return hashlib.sha256(b"strideboard-backup-key|" + secret.encode()).digest()


def encrypt(blob, key=None):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return MAGIC + nonce + AESGCM(key or backup_key()).encrypt(nonce, blob, MAGIC)


def decrypt(blob, key=None):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not blob.startswith(MAGIC):
        raise ValueError("this isn't an encrypted StrideBoard backup")
    nonce, body = blob[len(MAGIC):len(MAGIC) + 12], blob[len(MAGIC) + 12:]
    try:
        return AESGCM(key or backup_key()).decrypt(nonce, body, MAGIC)
    except Exception:
        raise ValueError("wrong key: this copy was made with a different secret/backup key") from None


def can_encrypt():
    try:
        import cryptography.hazmat.primitives.ciphers.aead  # noqa: F401
        return True
    except ImportError:
        return False


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


def file_name(now=None, encrypted=False):
    return f"{PREFIX}{(now or datetime.now(TZ)):%Y-%m-%d}" + (ENC_SUFFIX if encrypted else ".sqlite3.gz")


def _copies(folder):
    return sorted(list(folder.glob(PREFIX + "*.sqlite3.gz")) + list(folder.glob(PREFIX + "*" + ENC_SUFFIX)),
                  key=lambda p: p.name)


def save_daily(db_path, now=None, keep=KEEP_DAYS):
    """Write today's backup into backups/ and delete ones older than the newest `keep`."""
    folder = folder_for(db_path)
    folder.mkdir(parents=True, exist_ok=True)
    blob, enc = snapshot(db_path), can_encrypt()
    if enc:
        blob = encrypt(blob)
    else:
        print("WARNING: the 'cryptography' package is missing, so this copy is NOT encrypted. "
              "Run: pip3 install --user cryptography")
    path = folder / file_name(now, encrypted=enc)
    path.write_bytes(blob)
    other = folder / file_name(now, encrypted=not enc)      # today's copy in the other form
    if other.exists():
        other.unlink()
    for old in _copies(folder)[:-keep]:
        old.unlink()
    return path


def latest(db_path):
    """(file name, when it was made) of the newest automatic backup, or None."""
    folder = folder_for(db_path)
    files = _copies(folder) if folder.exists() else []
    if not files:
        return None
    f = files[-1]
    return f.name, datetime.fromtimestamp(f.stat().st_mtime, TZ)


def decrypt_file(src, dst):
    """Turn an encrypted copy back into a plain .sqlite3 database file."""
    Path(dst).write_bytes(gzip.decompress(decrypt(Path(src).read_bytes())))


def main(argv=None):
    argv = argv or sys.argv[1:]
    if argv[:1] == ["--decrypt"]:
        if len(argv) != 3:
            sys.exit("Use: python3 backup.py --decrypt <backup.sqlite3.gz.enc> <out.sqlite3>")
        decrypt_file(argv[1], argv[2])
        print(f"Wrote {argv[2]}")
        return
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
