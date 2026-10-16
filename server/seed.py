"""Fill the database with an admin account and (optionally) fake demo data.

Run from the server folder:
    python seed.py                    fake demo data (refuses if users already exist)
    python seed.py --reset            DELETE everything, then add fake demo data
    python seed.py --admin-only       real server: only the admin account, no fake data
    python seed.py --admin-pin 482913 choose the admin PIN (otherwise a random one is printed)

The fake people have clearly fake names and PIN 1234. Their steps and moods are
random: never use them as evidence of impact.
"""
import argparse
import random
import secrets
import sys
from datetime import timedelta

import calc
import config
import data
import db

FAKE_PIN = "1234"
FAKE_TEACHERS = [  # (username, display name, department, age band)
    ("teacher1", "Test Teacher A", "Science", "adult_18_39"),
    ("teacher2", "Test Teacher B", "Math", "adult_40_59"),
    ("teacher3", "Test Teacher C", "PE", "adult_18_39"),
    ("teacher4", "Test Teacher D", "English", "adult_40_59"),
    ("teacher5", "Test Teacher E", "Science", "adult_18_39"),
]
FAKE_CLASSES = ["Grade 10A", "Grade 10B", "Grade 11A"]
TABLES_TO_WIPE = ["badges", "steps", "moods", "water", "activities", "challenges", "users", "meta"]


def wipe(conn):
    """Delete all rows (tables stay). Used only with --reset."""
    for table in TABLES_TO_WIPE:
        conn.execute(f"DELETE FROM {table}")   # table names are fixed above, not user input
    conn.commit()


def add_fake_people(conn, today, rng):
    """5 teachers, 10 students, 14 days of random steps and moods, two challenges."""
    people = list(FAKE_TEACHERS)
    for n in range(1, 11):
        people.append((f"student{n}", f"Test Student {n:02d}", FAKE_CLASSES[(n - 1) % 3],
                       "teen_13_17"))

    # They "joined" 7 days ago, so the impact page has 7 days before and 7 days during.
    joined = f"{(today - timedelta(days=7)).isoformat()}T08:00:00+04:00"
    sources = ["ios_shortcut", "android_app", "manual"]

    for username, name, dept, band in people:
        role = "teacher" if username.startswith("teacher") else "student"
        uid = data.create_user(conn, username, name, role, dept, band, FAKE_PIN)
        conn.execute("UPDATE users SET created_at = ? WHERE id = ?", (joined, uid))

        usual = rng.randint(5000, 11000)          # this person's typical day
        for back in range(13, -1, -1):            # 14 days, oldest first
            day = today - timedelta(days=back)
            if rng.random() < 0.1:
                continue                          # some days have no data
            steps = int(usual * rng.uniform(0.6, 1.4))
            if back == 0:
                steps //= 2                       # today is not over yet
            source = rng.choices(sources, weights=[45, 35, 20])[0]
            data._write_steps(conn, uid, day.isoformat(), steps, source,
                              f"{day.isoformat()}T21:{rng.randint(0, 59):02d}:00+04:00")
            data.award_badges(conn, uid, day, day)
            if rng.random() < 0.7:
                conn.execute("INSERT INTO moods (user_id, date, mood) VALUES (?, ?, ?)",
                             (uid, day.isoformat(), rng.randint(2, 5)))
            if rng.random() < 0.5:
                conn.execute("INSERT INTO water (user_id, date, glasses) VALUES (?, ?, ?)",
                             (uid, day.isoformat(), rng.randint(2, 8)))
    conn.commit()

    monday, sunday = calc.week_bounds(today)
    data.create_challenge(conn, "Department Step-Off",
                          "Which department or class walks the most on average this week?",
                          "department", None, monday, sunday)
    target = round(120 / config.KM_PER_STEP)     # about 120 km
    data.create_challenge(conn, "Ras Al Khaimah to Dubai",
                          "Walk the 120 km from Ras Al Khaimah to Dubai together as a school.",
                          "school_distance", target, today - timedelta(days=13),
                          today + timedelta(days=16))
    return len(people)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create the StrideBoard admin and demo data.")
    parser.add_argument("--reset", action="store_true",
                        help="DELETE all existing data first")
    parser.add_argument("--admin-only", action="store_true",
                        help="only create the admin account (for the real server)")
    parser.add_argument("--admin-pin", help="admin PIN, 4-6 digits (default: random 6 digits)")
    parser.add_argument("--database", help="SQLite file (default: config.DATABASE)")
    args = parser.parse_args(argv)

    # 1. Check the PIN BEFORE touching the database, so a typo never wipes data.
    if args.admin_pin is not None:
        try:
            admin_pin = data.clean_pin(args.admin_pin)
        except ValueError as exc:
            print(f"Error: {exc}. Nothing was changed.")
            return 2
    else:
        admin_pin = f"{secrets.randbelow(10 ** 6):06d}"

    path = args.database or config.DATABASE
    conn = db.connect(path)
    try:
        db.create_tables(conn)
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing and not args.reset:
            print(f"The database already has {existing} user(s). Nothing was changed.\n"
                  f"Use --reset to DELETE everything and start again.")
            return 1
        if args.reset:
            wipe(conn)

        data.create_user(conn, "admin", "School Admin", "admin", None, "adult_18_39", admin_pin)
        count = 0
        if not args.admin_only:
            count = add_fake_people(conn, db.local_today(), random.Random(2026))
    finally:
        conn.close()

    print(f"Database: {path}")
    print(f"Admin login -> username: admin   PIN: {admin_pin}   (write it down now)")
    if count:
        print(f"Added {count} FAKE users (teacher1-5, student1-10), all with PIN {FAKE_PIN}.")
        print("Their steps and moods are random demo data, not real results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
