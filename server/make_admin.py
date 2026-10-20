"""Make (or reset) an admin account on the real server.

    python3 make_admin.py                 username soham.admin, new random PIN
    python3 make_admin.py some.name       a different username

Run it again any time to get a new PIN (the old one stops working).
It finds the live database from the PythonAnywhere WSGI file, so you don't
need to type the path. It never creates a new, empty database by mistake.
"""
import glob
import os
import re
import secrets
import sqlite3
import sys

from werkzeug.security import generate_password_hash

import config


def find_database():
    """The database the website uses: the env var, else the WSGI file, else the default."""
    if os.environ.get("STRIDEBOARD_DATABASE"):
        return os.environ["STRIDEBOARD_DATABASE"], "STRIDEBOARD_DATABASE"
    for wsgi in sorted(glob.glob("/var/www/*_wsgi.py")):
        text = open(wsgi, encoding="utf-8", errors="ignore").read()
        m = re.search(r"STRIDEBOARD_DATABASE['\"]\s*\]?\s*[=,:]\s*['\"]([^'\"]+)['\"]", text)
        if m:
            return os.path.expanduser(m.group(1)), wsgi
    return str(config.DATABASE), "the default in config.py"


def main():
    username = (sys.argv[1] if len(sys.argv) > 1 else "soham.admin").strip().lower()
    path, source = find_database()
    print(f"Database: {path}  (found via {source})")
    if not os.path.isfile(path):
        sys.exit("STOPPED: that database file doesn't exist. Nothing was changed.\n"
                 "Check the STRIDEBOARD_DATABASE line in your WSGI file (Web tab).")
    conn = sqlite3.connect(path, timeout=10)
    try:
        people = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    except sqlite3.OperationalError:
        sys.exit("STOPPED: that file has no users table, so it isn't the StrideBoard database.")
    print(f"It has {people} accounts.")

    pin = f"{secrets.randbelow(10 ** 6):06d}"
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if row:
        conn.execute("UPDATE users SET pin_hash = ?, role = 'admin' WHERE id = ?",
                     (generate_password_hash(pin), row[0]))
        what = "Reset the PIN of"
    else:
        import data   # only needed to create a new account
        data.create_user(conn, username, "Soham (Admin)" if username == "soham.admin" else username,
                         "admin", None, "adult_18_39", pin)
        what = "Created"
    conn.commit()
    admins = [r[0] for r in conn.execute("SELECT username FROM users WHERE role = 'admin' ORDER BY id")]
    print(f"{what} {username}. Admin accounts now: {', '.join(admins)}")
    print()
    print(f"  Log in with  username: {username}   PIN: {pin}")
    print()
    print("Write the PIN down now. It is not stored anywhere you can read it back.")


if __name__ == "__main__":
    main()
