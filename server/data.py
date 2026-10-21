"""All database reads and writes for StrideBoard.

The website (Agent 3) calls only these functions; no SQL lives anywhere else.
Every function takes an open sqlite3 connection first, returns plain dicts and
lists (dates as 'YYYY-MM-DD'), and raises ValueError with a readable message
for bad input. All SQL uses ? placeholders, never string formatting of values.
"""
import csv
import io
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

import calc
import config
from db import local_now_iso, local_today

USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,30}$")
# pin_hash is never selected for anything that leaves this file.
USER_FIELDS = ("id, username, display_name, role, department, age_band, api_token, "
               "daily_goal, goal_is_custom, created_at, avatar, avatar_color")
PLAYER_ROLES = ("teacher", "student")   # admins never appear on boards or in stats


# =====================================================================
# Small helpers
# =====================================================================

def _day(value):
    """'YYYY-MM-DD' text for a date or text."""
    return calc.to_date(value).isoformat()


def _today(today):
    return calc.to_date(today) if today is not None else local_today()


def _clean_username(username):
    name = (username or "").strip().lower()
    if not USERNAME_RE.fullmatch(name):
        raise ValueError("username must be 3-30 characters: letters, numbers, . _ or -")
    return name


def clean_pin(pin):
    """A PIN is 4-6 digits. Returns it as text. (Also used by seed.py.)"""
    text = str(pin if pin is not None else "").strip().translate(calc._DIGITS)
    low, high = config.PIN_MIN_LENGTH, config.PIN_MAX_LENGTH
    if not re.fullmatch(rf"\d{{{low},{high}}}", text):
        raise ValueError(f"PIN must be {low}-{high} digits")
    return text


def _check_age_band(age_band):
    band = (age_band or "").strip()
    if band not in config.AGE_BANDS:
        raise ValueError("age_band must be one of: " + ", ".join(config.AGE_BANDS))
    return band


def _require_user(conn, user_id):
    user = get_user(conn, user_id)
    if user is None:
        raise ValueError("user not found")
    return user


def _sum_steps(conn, user_id, start, end):
    """Total steps for one user between two dates (inclusive)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(steps), 0) FROM steps WHERE user_id = ? AND date BETWEEN ? AND ?",
        (user_id, _day(start), _day(end)),
    ).fetchone()
    return row[0]


def _goal_met_dates(conn, user_id, goal, today):
    rows = conn.execute(
        "SELECT date FROM steps WHERE user_id = ? AND steps >= ? AND date <= ? AND date >= ?",
        (user_id, goal, _day(today), _day(calc.to_date(today) - timedelta(days=400))),
    ).fetchall()
    return [r["date"] for r in rows]


def _set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _get_meta(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


SHORTCUT_LINK_RE = re.compile(r"https://www\.icloud\.com/shortcuts/[A-Za-z0-9]{16,64}/?")


def ios_shortcut_link(conn):
    """The iCloud link of the StrideBoard Sync Shortcut that students install, or None."""
    return _get_meta(conn, "ios_shortcut_url")


def set_ios_shortcut_link(conn, link):
    """Save (or clear, with blank) the Shortcut's iCloud share link. Returns the saved link."""
    link = (link or "").strip()
    if link and not SHORTCUT_LINK_RE.fullmatch(link):
        raise ValueError("that isn't a Shortcut share link. It should look like "
                         "https://www.icloud.com/shortcuts/abc123...")
    if link:
        _set_meta(conn, "ios_shortcut_url", link)
    else:
        conn.execute("DELETE FROM meta WHERE key = 'ios_shortcut_url'")
    conn.commit()
    return link or None


# =====================================================================
# Users
# =====================================================================

def get_user(conn, user_id):
    """One user as a dict (never includes pin_hash), or None."""
    row = conn.execute(f"SELECT {USER_FIELDS} FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_token(conn, token):
    """The user who owns a phone token, or None. Used by /api/steps."""
    if not isinstance(token, str) or not token.strip():
        return None
    row = conn.execute("SELECT id FROM users WHERE api_token = ?", (token.strip(),)).fetchone()
    return get_user(conn, row["id"]) if row else None


def authenticate(conn, username, pin):
    """The user if username + PIN are right, otherwise None."""
    name = (username or "").strip().lower()
    row = conn.execute("SELECT id, pin_hash FROM users WHERE username = ?", (name,)).fetchone()
    if row is None or not check_password_hash(row["pin_hash"], str(pin or "").strip()):
        return None
    return get_user(conn, row["id"])


def _check_new_user(conn, username, display_name, role, department, age_band):
    """Clean and check a new person's details. Returns them, or raises ValueError."""
    username = _clean_username(username)
    display_name = (display_name or "").strip()
    if not 1 <= len(display_name) <= 50:
        raise ValueError("display name must be 1-50 characters")
    role = (role or "").strip().lower()
    if role not in config.ROLES:
        raise ValueError("role must be student, teacher or admin")
    department = (department or "").strip() or None
    if department and len(department) > 50:
        raise ValueError("department must be at most 50 characters")
    age_band = _check_age_band(age_band)
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        raise ValueError(f"username {username!r} is already taken")
    return username, display_name, role, department, age_band


def _insert_user(conn, username, display_name, role, department, age_band, pin_hash, email_hash=None):
    try:
        cur = conn.execute(
            "INSERT INTO users (username, display_name, pin_hash, role, department, age_band, "
            "api_token, daily_goal, goal_is_custom, created_at, email_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (username, display_name, pin_hash, role, department, age_band,
             secrets.token_urlsafe(24), config.AGE_BAND_GOALS[age_band], local_now_iso(), email_hash),
        )
    except sqlite3.IntegrityError:
        raise ValueError(f"username {username!r} is already taken") from None
    conn.commit()
    return cur.lastrowid


def create_user(conn, username, display_name, role, department, age_band, pin):
    """Add a user and return the new id. The starting goal comes from the age band."""
    details = _check_new_user(conn, username, display_name, role, department, age_band)
    return _insert_user(conn, *details, generate_password_hash(clean_pin(pin)))


# ---- Sign-up with an email code -------------------------------------------

EMAIL_RE = re.compile(r"[^@\s]{1,64}@[A-Za-z0-9.-]{1,200}\.[A-Za-z]{2,}")


def normalize_email(email):
    """Lower case, and for Gmail drop dots and +tags, so one inbox = one account."""
    email = (email or "").strip().lower()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise ValueError("please enter a real email address")
    local, domain = email.rsplit("@", 1)
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    if config.EMAIL_DOMAINS and domain not in config.EMAIL_DOMAINS:
        raise ValueError("please use an email ending in " + " or ".join("@" + d for d in config.EMAIL_DOMAINS))
    return f"{local}@{domain}"


def email_fingerprint(email, secret):
    """A one-way fingerprint of the email, so we can stop duplicates without keeping addresses."""
    import hashlib
    return hashlib.sha256((secret + "|" + normalize_email(email)).encode()).hexdigest()


def _new_code():
    return f"{secrets.randbelow(10 ** 6):06d}"


def _hidden_username(conn, role):
    """People who sign up log in with their email, so they never choose (or see) a username.

    This makes a plain one for the database, e.g. student482913.
    """
    while True:
        name = f"{role}{secrets.randbelow(10 ** 6):06d}"
        if not conn.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone():
            return name


def clean_name(name):
    """'  amal   K ' -> 'amal K' (spaces tidied), so names compare fairly."""
    return " ".join((name or "").split())


def name_taken(conn, name):
    return conn.execute("SELECT 1 FROM users WHERE lower(display_name) = lower(?)",
                        (clean_name(name),)).fetchone() is not None


def authenticate_name(conn, name, pin):
    """Log in with your name (as on the leaderboards) + PIN. Usernames still work too."""
    name = clean_name(name)
    if not name:
        return None
    user = authenticate(conn, name, pin)          # older accounts made by an admin
    if user:
        return user
    rows = conn.execute("SELECT id, pin_hash FROM users WHERE lower(display_name) = lower(?)",
                        (name,)).fetchall()
    for row in rows:                               # normally one; older duplicates are tried in turn
        if check_password_hash(row["pin_hash"], str(pin or "").strip()):
            return get_user(conn, row["id"])
    return None


def authenticate_email(conn, secret, email, pin):
    """Log in with email + PIN (for people who signed up themselves). The user, or None."""
    try:
        fingerprint = email_fingerprint(email, secret)
    except ValueError:
        return None
    row = conn.execute("SELECT id, pin_hash FROM users WHERE email_hash = ?", (fingerprint,)).fetchone()
    if row is None or not check_password_hash(row["pin_hash"], str(pin or "").strip()):
        return None
    return get_user(conn, row["id"])


def start_signup(conn, secret, email, display_name, role, department, age_band, pin, pin_again,
                 now=None):
    """Check a sign-up form and hold it until the email code is entered.

    Only student or teacher. Returns (pending_id, email_to_send_to, code).
    """
    now = _now(now)
    role = (role or "").strip().lower()
    if role not in config.SIGNUP_ROLES:
        raise ValueError("please choose Student or Teacher")
    choices = config.SIGNUP_CLASSES if role == "student" else config.SIGNUP_DEPARTMENTS
    if (department or "").strip() not in choices:
        raise ValueError("please choose your " + ("class" if role == "student" else "department"))
    display_name = clean_name(display_name)
    if len(display_name.split()) < 2:
        raise ValueError("please type your full name: first and last name, like Amal Khan")
    if name_taken(conn, display_name):
        raise ValueError(f"someone already uses the name {display_name!r}. Add your middle name "
                         "or another part of your name so you can tell yourselves apart")
    details = _check_new_user(conn, _hidden_username(conn, role), display_name, role, department, age_band)
    pin = clean_pin(pin)
    if pin != str(pin_again or "").strip():
        raise ValueError("the two PINs don't match")
    fingerprint = email_fingerprint(email, secret)
    if conn.execute("SELECT 1 FROM users WHERE email_hash = ?", (fingerprint,)).fetchone():
        raise ValueError("there's already an account with that email. Log in instead")
    # tidy up: old waiting sign-ups, and any earlier try with this email
    cutoff = (now - timedelta(days=1)).isoformat(timespec="seconds")
    conn.execute("DELETE FROM pending_signups WHERE created_at < ? OR email_hash = ?", (cutoff, fingerprint))
    code = _new_code()
    import json
    stamp = now.isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO pending_signups (email, email_hash, code_hash, details, sent_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ((email or "").strip(), fingerprint, generate_password_hash(code),
         json.dumps(list(details) + [generate_password_hash(pin)]), stamp, stamp))
    conn.commit()
    return cur.lastrowid, (email or "").strip(), code


def _pending(conn, pending_id):
    row = conn.execute("SELECT * FROM pending_signups WHERE id = ?", (pending_id,)).fetchone()
    if row is None:
        raise ValueError("that sign-up has expired. Please start again")
    return row


def pending_email(conn, pending_id):
    """The address a code went to (for the 'we sent a code to …' line), or None."""
    row = conn.execute("SELECT email FROM pending_signups WHERE id = ?", (pending_id,)).fetchone()
    return row["email"] if row else None


def resend_signup_code(conn, pending_id, now=None):
    """A fresh code (the old one stops working). Returns (email, code)."""
    now = _now(now)
    row = _pending(conn, pending_id)
    waited = (now - datetime.fromisoformat(row["sent_at"])).total_seconds()
    if waited < config.CODE_RESEND_SECONDS:
        raise ValueError(f"please wait {int(config.CODE_RESEND_SECONDS - waited) + 1} seconds before asking again")
    if row["sends"] >= config.CODE_MAX_SENDS:
        raise ValueError("too many codes sent. Please start again later")
    code = _new_code()
    conn.execute("UPDATE pending_signups SET code_hash = ?, sends = sends + 1, attempts = 0, sent_at = ? "
                 "WHERE id = ?", (generate_password_hash(code), now.isoformat(timespec="seconds"), pending_id))
    conn.commit()
    return row["email"], code


def finish_signup(conn, pending_id, code, now=None):
    """Check the emailed code and make the account. Returns the new user id."""
    import json
    now = _now(now)
    row = _pending(conn, pending_id)
    age = (now - datetime.fromisoformat(row["sent_at"])).total_seconds()
    if age > config.CODE_MINUTES * 60:
        raise ValueError("that code has expired. Tap 'Send a new code'")
    if row["attempts"] >= config.CODE_TRIES:
        raise ValueError("too many wrong codes. Tap 'Send a new code'")
    code = str(code or "").strip().translate(calc._DIGITS).replace(" ", "")
    if not check_password_hash(row["code_hash"], code):
        conn.execute("UPDATE pending_signups SET attempts = attempts + 1 WHERE id = ?", (pending_id,))
        conn.commit()
        left = config.CODE_TRIES - row["attempts"] - 1
        raise ValueError(f"that code isn't right. {left} tr{'y' if left == 1 else 'ies'} left"
                         if left else "that code isn't right. Tap 'Send a new code'")
    if conn.execute("SELECT 1 FROM users WHERE email_hash = ?", (row["email_hash"],)).fetchone():
        raise ValueError("there's already an account with that email. Log in instead")
    username, display_name, role, department, age_band, pin_hash = json.loads(row["details"])
    if name_taken(conn, display_name):
        raise ValueError(f"someone just took the name {display_name!r}. Please start again with a different one")
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        username = _hidden_username(conn, role)
    uid = _insert_user(conn, username, display_name, role, department, age_band, pin_hash, row["email_hash"])
    conn.execute("DELETE FROM pending_signups WHERE id = ?", (pending_id,))
    conn.commit()
    return uid


def bulk_create_users(conn, csv_text):
    """Add many users from pasted CSV: username,display_name,role,department,age_band,pin.

    A header row is optional. Bad rows are skipped and reported; good rows are added.
    """
    created, errors = 0, []
    reader = csv.reader(io.StringIO((csv_text or "").lstrip("﻿")))
    for row in reader:
        line = reader.line_num
        cells = [cell.strip() for cell in row]
        if not any(cells):
            continue                                   # blank line
        if line == 1 and cells[0].lower() == "username":
            continue                                   # header row
        if len(cells) != 6:
            errors.append(f"row {line}: expected 6 columns "
                          f"(username,display_name,role,department,age_band,pin), found {len(cells)}")
            continue
        try:
            create_user(conn, *cells)
            created += 1
        except ValueError as exc:
            errors.append(f"row {line}: {exc}")
    return {"created": created, "errors": errors}


def list_users(conn):
    """All users for the admin page (no PIN hashes, no tokens)."""
    rows = conn.execute(
        "SELECT id, username, display_name, role, department, age_band, daily_goal, "
        "goal_is_custom, created_at FROM users ORDER BY role, department, display_name"
    ).fetchall()
    return [dict(r) for r in rows]


def set_custom_goal(conn, user_id, goal):
    """The user picks their own goal. Automatic goal changes stop for them."""
    goal = calc.parse_int(goal, "goal", config.CUSTOM_GOAL_MIN, config.CUSTOM_GOAL_MAX)
    cur = conn.execute("UPDATE users SET daily_goal = ?, goal_is_custom = 1 WHERE id = ?",
                       (goal, user_id))
    if cur.rowcount == 0:
        raise ValueError("user not found")
    conn.commit()


def set_age_band(conn, user_id, age_band):
    """Change the age band. Without a custom goal, the goal resets to the band's default."""
    age_band = _check_age_band(age_band)
    user = _require_user(conn, user_id)
    if user["goal_is_custom"]:
        conn.execute("UPDATE users SET age_band = ? WHERE id = ?", (age_band, user_id))
    else:
        conn.execute("UPDATE users SET age_band = ?, daily_goal = ? WHERE id = ?",
                     (age_band, config.AGE_BAND_GOALS[age_band], user_id))
    conn.commit()


def regenerate_token(conn, user_id):
    """Make a new phone token (the old one stops working). Returns the new token."""
    token = secrets.token_urlsafe(24)
    cur = conn.execute("UPDATE users SET api_token = ? WHERE id = ?", (token, user_id))
    if cur.rowcount == 0:
        raise ValueError("user not found")
    conn.commit()
    return token


def avatar_options(conn, user_id):
    """Every avatar with whether this user has unlocked it (for the Settings picker).

    Returns [{"key", "emoji", "unlocked", "badge", "badge_name"}] in display order.
    """
    earned = {r["badge_key"] for r in conn.execute(
        "SELECT badge_key FROM badges WHERE user_id = ?", (user_id,))}
    return [{"key": key, "emoji": emoji, "unlocked": badge is None or badge in earned,
             "badge": badge, "badge_name": config.BADGES.get(badge) if badge else None}
            for key, (emoji, badge) in config.AVATARS.items()]


def set_avatar(conn, user_id, avatar, color):
    """Pick an avatar and colour. Locked avatars need their badge first."""
    option = next((o for o in avatar_options(conn, user_id) if o["key"] == avatar), None)
    if option is None:
        raise ValueError("please choose an avatar")
    if color not in config.AVATAR_COLORS:
        raise ValueError("please choose a colour")
    if not option["unlocked"]:
        raise ValueError(f"earn the {option['badge_name']} badge to unlock this avatar")
    cur = conn.execute("UPDATE users SET avatar = ?, avatar_color = ? WHERE id = ?",
                       (avatar, color, user_id))
    if cur.rowcount == 0:
        raise ValueError("user not found")
    conn.commit()


# =====================================================================
# EXP and the avatar studio
# =====================================================================

def exp_balance(conn, user_id):
    """Current EXP: the sum of every gain and spend."""
    return conn.execute("SELECT COALESCE(SUM(amount), 0) FROM exp_ledger WHERE user_id = ?",
                        (user_id,)).fetchone()[0]


def add_exp(conn, user_id, amount, reason):
    """Give someone EXP (a positive whole number). Returns the new balance.

    The earning rules will call this; for now admins use it from the Admin page.
    """
    amount = calc.parse_int(amount, "EXP", 1, config.EXP_MAX_GRANT)
    reason = (reason or "").strip()
    if not 1 <= len(reason) <= 100:
        raise ValueError("please give a short reason (1 to 100 characters)")
    _require_user(conn, user_id)
    conn.execute("INSERT INTO exp_ledger (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
                 (user_id, amount, reason, local_now_iso()))
    conn.commit()
    return exp_balance(conn, user_id)


def exp_history(conn, user_id, limit=20):
    """Latest EXP gains and spends, newest first: [{"amount", "reason", "created_at"}]."""
    rows = conn.execute("SELECT amount, reason, created_at FROM exp_ledger WHERE user_id = ? "
                        "ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def _default_build(user_id):
    build = dict(config.AVATAR_DEFAULTS)
    build["color"] = config.AVATAR_START_COLORS[user_id % len(config.AVATAR_START_COLORS)]
    return build


def avatar_builds(conn, user_ids):
    """What each person's avatar is wearing: {user_id: {slot: item_key}} (defaults filled in)."""
    ids = [int(u) for u in user_ids if u is not None]
    builds = {u: _default_build(u) for u in ids}
    if ids:
        marks = ",".join("?" * len(ids))
        for r in conn.execute(f"SELECT user_id, slot, item_key FROM avatar_equipped "
                              f"WHERE user_id IN ({marks})", ids):
            if r["item_key"] in config.AVATAR_ITEMS:
                builds[r["user_id"]][r["slot"]] = r["item_key"]
    return builds


def avatar_build(conn, user_id):
    return avatar_builds(conn, [user_id])[user_id]


def avatar_shop(conn, user_id):
    """Everything the studio needs: balance, what's worn, and every item with its state.

    items: [{"key", "slot", "name", "price", "owned", "worn"}] in catalogue order.
    """
    _require_user(conn, user_id)
    build = avatar_build(conn, user_id)
    bought = {r[0] for r in conn.execute("SELECT item_key FROM avatar_owned WHERE user_id = ?", (user_id,))}
    items = [{"key": k, "slot": slot, "name": name, "price": price,
              "owned": price == 0 or k in bought, "worn": build.get(slot) == k}
             for k, (slot, name, price) in config.AVATAR_ITEMS.items()]
    return {"balance": exp_balance(conn, user_id), "build": build, "items": items}


def _item(key):
    if key not in config.AVATAR_ITEMS:
        raise ValueError("that item doesn't exist")
    slot, name, price = config.AVATAR_ITEMS[key]
    return slot, name, price


def wear_avatar_item(conn, user_id, key):
    """Put on an item you own (free items are always yours)."""
    slot, name, price = _item(key)
    _require_user(conn, user_id)
    if price > 0 and not conn.execute("SELECT 1 FROM avatar_owned WHERE user_id = ? AND item_key = ?",
                                      (user_id, key)).fetchone():
        raise ValueError(f"buy {name} first")
    conn.execute("INSERT INTO avatar_equipped (user_id, slot, item_key) VALUES (?, ?, ?) "
                 "ON CONFLICT (user_id, slot) DO UPDATE SET item_key = excluded.item_key",
                 (user_id, slot, key))
    conn.commit()


def buy_avatar_item(conn, user_id, key):
    """Spend EXP on an item and put it on. Returns the new balance."""
    slot, name, price = _item(key)
    _require_user(conn, user_id)
    if price == 0:
        raise ValueError(f"{name} is free: just tap Wear")
    balance = exp_balance(conn, user_id)
    if balance < price:
        raise ValueError(f"{name} costs {price:,} EXP and you have {balance:,}")
    try:
        # The primary key stops the same item being bought twice (e.g. a double tap).
        conn.execute("INSERT INTO avatar_owned (user_id, item_key, bought_at) VALUES (?, ?, ?)",
                     (user_id, key, local_now_iso()))
    except sqlite3.IntegrityError:
        raise ValueError(f"you already own {name}") from None
    conn.execute("INSERT INTO exp_ledger (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
                 (user_id, -price, f"Bought {name}", local_now_iso()))
    conn.commit()
    wear_avatar_item(conn, user_id, key)
    return exp_balance(conn, user_id)


def set_role(conn, user_id, role, department=None, acting_admin_id=None):
    """Change someone's role (student, teacher or admin). Optionally set their class/department.

    You can't take admin away from yourself, so there is always at least one admin.
    """
    role = (role or "").strip().lower()
    if role not in config.ROLES:
        raise ValueError("role must be student, teacher or admin")
    user = _require_user(conn, user_id)
    if user_id == acting_admin_id and role != "admin":
        raise ValueError("you can't remove your own admin role")
    department = (department or "").strip() or None
    if department and len(department) > 50:
        raise ValueError("department must be at most 50 characters")
    conn.execute("UPDATE users SET role = ?, department = COALESCE(?, department) WHERE id = ?",
                 (role, department, user_id))
    conn.commit()
    return user["role"]


def find_user_id(conn, username):
    """A user's id from their username (any case), or None."""
    row = conn.execute("SELECT id FROM users WHERE username = ?", (_clean_username(username),)).fetchone()
    return row["id"] if row else None


# =====================================================================
# Entries
# =====================================================================

def _write_steps(conn, user_id, day, steps, source, updated_at=None):
    """Insert or overwrite one day's steps (no checks; callers check first)."""
    conn.execute(
        "INSERT INTO steps (user_id, date, steps, source, updated_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, date) DO UPDATE SET steps = excluded.steps, "
        "source = excluded.source, updated_at = excluded.updated_at",
        (user_id, day, steps, source, updated_at or local_now_iso()),
    )


def award_badges(conn, user_id, day, today):
    """Give any badges the user has just earned. Returns the new badge keys.

    `day` is the date that was just saved; week badges look at that day's week.
    """
    user = _require_user(conn, user_id)
    day = calc.to_date(day)
    monday, sunday = calc.week_bounds(day)
    last_monday = monday - timedelta(days=7)

    entry_count = conn.execute("SELECT COUNT(*) FROM steps WHERE user_id = ?",
                               (user_id,)).fetchone()[0]
    day_row = conn.execute("SELECT steps FROM steps WHERE user_id = ? AND date = ?",
                           (user_id, day.isoformat())).fetchone()
    days_logged = conn.execute(
        "SELECT COUNT(*) FROM steps WHERE user_id = ? AND steps > 0 AND date BETWEEN ? AND ?",
        (user_id, monday.isoformat(), sunday.isoformat()),
    ).fetchone()[0]

    earned = calc.badge_keys(
        entry_count=entry_count,
        day_steps=day_row["steps"] if day_row else 0,
        streak_days=calc.streak(_goal_met_dates(conn, user_id, user["daily_goal"], today), today),
        days_logged_in_week=days_logged,
        week_total=_sum_steps(conn, user_id, monday, sunday),
        last_week_total=_sum_steps(conn, user_id, last_monday, monday - timedelta(days=1)),
    )

    new_badges = []
    for key in config.BADGES:            # keep the display order
        if key in earned:
            cur = conn.execute(
                "INSERT OR IGNORE INTO badges (user_id, badge_key, earned_on) VALUES (?, ?, ?)",
                (user_id, key, _day(today)),
            )
            if cur.rowcount:
                new_badges.append(key)
    return new_badges


def save_steps(conn, user_id, date, steps, source, today=None):
    """Save one day's steps (overwrites that day), give badges, return the week so far.

    Returns {"weekly_total", "tier", "new_badges": [keys]}.
    `today` is only for tests; normally it is today's date in Dubai.
    """
    today = _today(today)
    day = calc.parse_date(date, today)
    steps = calc.parse_steps(steps)
    if source not in config.SOURCES:
        raise ValueError("source must be one of: " + ", ".join(config.SOURCES))
    _require_user(conn, user_id)

    _write_steps(conn, user_id, day, steps, source)
    if day == today.isoformat():
        _record_sample(conn, user_id, day, steps)
    new_badges = award_badges(conn, user_id, day, today)
    conn.commit()
    if day == local_today().isoformat():
        check_walks(conn, user_id)   # a walking mini challenge may now be finished

    monday, sunday = calc.week_bounds(today)
    total = _sum_steps(conn, user_id, monday, sunday)
    return {"weekly_total": total, "tier": calc.tier_for(total), "new_badges": new_badges}


def _record_sample(conn, user_id, day, total, at=None):
    """Note today's total and when it arrived (for the stand-up reminder). Old notes are removed."""
    at = at or local_now_iso()
    conn.execute("INSERT INTO step_samples (user_id, date, total, at) VALUES (?, ?, ?, ?)",
                 (user_id, day, total, at))
    oldest = (calc.to_date(day) - timedelta(days=config.SAMPLE_KEEP_DAYS)).isoformat()
    conn.execute("DELETE FROM step_samples WHERE user_id = ? AND date < ?", (user_id, oldest))


def inactivity(conn, user_id, now=None):
    """Has this person barely moved lately? Used for the stand-up reminder.

    Returns {"inactive": True/False, "minutes": n} when it can tell, or
    {"inactive": None} when it can't (no recent sync, or no sync 30+ minutes earlier).
    Steps only go up during a day, so fewer than 50 steps between two syncs that are
    30+ minutes apart means at least 30 minutes of sitting still, ending at the newer sync.
    """
    now = now or datetime.fromisoformat(local_now_iso())
    rows = conn.execute("SELECT total, at FROM step_samples WHERE user_id = ? AND date = ? ORDER BY at",
                        (user_id, now.date().isoformat())).fetchall()
    if not rows:
        return {"inactive": None}
    latest_total, latest_at = rows[-1]["total"], datetime.fromisoformat(rows[-1]["at"])
    if now - latest_at > timedelta(minutes=config.SYNC_FRESH_MINUTES):
        return {"inactive": None}          # the newest number is too old to say anything
    window = timedelta(minutes=config.INACTIVE_MINUTES)
    earlier = [r for r in rows if latest_at - datetime.fromisoformat(r["at"]) >= window]
    if not earlier:
        return {"inactive": None}          # no sync far enough back to compare with
    base = earlier[-1]                     # the newest sync at least 30 minutes earlier
    gained = latest_total - base["total"]
    minutes = int((latest_at - datetime.fromisoformat(base["at"])).total_seconds() // 60)
    return {"inactive": gained < config.INACTIVE_MAX_STEPS, "minutes": minutes, "gained": gained}


def save_mood(conn, user_id, date, mood):
    """Mood check-in, 1 (low) to 5 (great). One per day; a new one replaces it."""
    day = calc.parse_date(date, local_today())
    mood = calc.parse_int(mood, "mood", config.MOOD_MIN, config.MOOD_MAX)
    _require_user(conn, user_id)
    conn.execute(
        "INSERT INTO moods (user_id, date, mood) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, date) DO UPDATE SET mood = excluded.mood",
        (user_id, day, mood),
    )
    conn.commit()


def save_water(conn, user_id, date, glasses):
    """Glasses of water for a day (the total, not an addition)."""
    day = calc.parse_date(date, local_today())
    glasses = calc.parse_int(glasses, "glasses", 0, config.WATER_MAX_GLASSES)
    _require_user(conn, user_id)
    conn.execute(
        "INSERT INTO water (user_id, date, glasses) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, date) DO UPDATE SET glasses = excluded.glasses",
        (user_id, day, glasses),
    )
    conn.commit()


def add_activity(conn, user_id, date, type, minutes):
    """Log an activity (walk, gym, sport, yoga, stretch, other). Returns its id."""
    day = calc.parse_date(date, local_today())
    if type not in config.ACTIVITY_TYPES:
        raise ValueError("type must be one of: " + ", ".join(config.ACTIVITY_TYPES))
    minutes = calc.parse_int(minutes, "minutes", 1, config.ACTIVITY_MAX_MINUTES)
    _require_user(conn, user_id)
    cur = conn.execute("INSERT INTO activities (user_id, date, type, minutes) VALUES (?, ?, ?, ?)",
                       (user_id, day, type, minutes))
    conn.commit()
    return cur.lastrowid


def save_exercise(conn, user_id, date, type, amount):
    """Log one set of an exercise (reps, or seconds for planks). Returns its id.

    Typed in by the user, so it only earns personal progression badges.
    """
    day = calc.parse_date(date, local_today())
    if type not in config.EXERCISE_TYPES:
        raise ValueError("exercise must be one of: " + ", ".join(config.EXERCISE_TYPES))
    what = "seconds" if type == "planks" else "reps"
    amount = calc.parse_int(amount, what, 1, config.EXERCISE_MAX_PER_SET[type])
    _require_user(conn, user_id)
    cur = conn.execute(
        "INSERT INTO exercises (user_id, date, type, amount, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, day, type, amount, local_now_iso()))
    conn.commit()
    return cur.lastrowid


def _track_rows(conn, user_id, track):
    """[(date, day_total, best_single), ...] oldest first, for one track."""
    if track == "steps":
        sql = ("SELECT date, SUM(steps), MAX(steps) FROM steps "
               "WHERE user_id = ? AND steps > 0 GROUP BY date ORDER BY date")
        return conn.execute(sql, (user_id,)).fetchall()
    sql = ("SELECT date, SUM(amount), MAX(amount) FROM exercises "
           "WHERE user_id = ? AND type = ? GROUP BY date ORDER BY date")
    return conn.execute(sql, (user_id, track)).fetchall()


def progression(conn, user_id):
    """The Challenges page: one entry per track (steps, push-ups, squats, planks, jumping jacks).

    Each track: {"key", "name", "unit", "total", "best", "levels": [{"level", "target",
    "earned", "earned_on"}], "next_target", "next_percent", "record": {"name", "best",
    "level", "levels": [...same shape...], "next_target"}}.
    A level is earned on the first day the lifetime total (or best in one go) reaches it.
    """
    _require_user(conn, user_id)
    out = []
    for key, t in config.TRACKS.items():
        rows = _track_rows(conn, user_id, key)
        running, best = 0, 0
        level_dates = [None] * len(t["levels"])
        record_dates = [None] * len(t["record_levels"])
        for day, day_total, day_best in rows:
            running += day_total
            best = max(best, day_best)
            for i, target in enumerate(t["levels"]):
                if level_dates[i] is None and running >= target:
                    level_dates[i] = day
            for i, target in enumerate(t["record_levels"]):
                if record_dates[i] is None and best >= target:
                    record_dates[i] = day

        def levels(targets, dates):
            return [{"level": i + 1, "target": target, "earned": d is not None, "earned_on": d}
                    for i, (target, d) in enumerate(zip(targets, dates))]

        lv = levels(t["levels"], level_dates)
        rec = levels(t["record_levels"], record_dates)
        nxt = next((x["target"] for x in lv if not x["earned"]), None)
        prev = max([x["target"] for x in lv if x["earned"]], default=0)
        pct = 100 if nxt is None else round((running - prev) * 100 / (nxt - prev))
        out.append({
            "key": key, "name": t["name"], "unit": t["unit"], "total": running, "best": best,
            "levels": lv, "earned_count": sum(x["earned"] for x in lv),
            "next_target": nxt, "next_percent": max(0, min(100, pct)),
            "record": {"name": t["record_name"], "best": best, "levels": rec,
                       "level": sum(x["earned"] for x in rec),
                       "next_target": next((x["target"] for x in rec if not x["earned"]), None)},
        })
    return out


# =====================================================================
# Views
# =====================================================================

def earned_badges(conn, user_id):
    """The general badges someone has: [{"key", "name", "earned_on"}], oldest first."""
    return [
        {"key": r["badge_key"], "name": config.BADGES.get(r["badge_key"], r["badge_key"]),
         "earned_on": r["earned_on"]}
        for r in conn.execute("SELECT badge_key, earned_on FROM badges WHERE user_id = ? "
                              "ORDER BY earned_on, id", (user_id,))
    ]


def dashboard(conn, user_id, today):
    """Everything for the home page (game stage 1 and 2)."""
    user = _require_user(conn, user_id)
    today = calc.to_date(today)
    day = today.isoformat()
    monday, sunday = calc.week_bounds(today)

    row = conn.execute("SELECT steps FROM steps WHERE user_id = ? AND date = ?",
                       (user_id, day)).fetchone()
    today_steps = row["steps"] if row else 0
    weekly = _sum_steps(conn, user_id, monday, sunday)
    next_name, needed = calc.next_tier(weekly)

    badges = earned_badges(conn, user_id)
    mood = conn.execute("SELECT mood FROM moods WHERE user_id = ? AND date = ?",
                        (user_id, day)).fetchone()
    water = conn.execute("SELECT glasses FROM water WHERE user_id = ? AND date = ?",
                         (user_id, day)).fetchone()

    return {
        "today_steps": today_steps,
        "daily_goal": user["daily_goal"],
        "goal_percent": calc.goal_percent(today_steps, user["daily_goal"]),
        "streak": calc.streak(_goal_met_dates(conn, user_id, user["daily_goal"], today), today),
        "weekly_total": weekly,
        "tier": calc.tier_for(weekly),
        "next_tier": next_name,
        "steps_to_next_tier": needed,
        "badges": badges,
        "mood_today": mood["mood"] if mood else None,
        "water_today": water["glasses"] if water else 0,
    }


def _player_totals(conn, start, end, roles=PLAYER_ROLES):
    """Each player's steps between two dates (players with no steps are left out)."""
    marks = ",".join("?" * len(roles))
    rows = conn.execute(
        f"SELECT u.id, u.display_name, u.department, u.daily_goal, u.avatar, u.avatar_color, "
        f"SUM(s.steps) AS total, MAX(s.updated_at) AS last_update "
        f"FROM users u JOIN steps s ON s.user_id = u.id AND s.date BETWEEN ? AND ? "
        f"WHERE u.role IN ({marks}) GROUP BY u.id HAVING total > 0",
        (_day(start), _day(end), *roles),
    ).fetchall()
    return {r["id"]: dict(r) for r in rows}


def _ranked(items):
    """Sort by value (high first); ties go to the earlier latest update; add ranks."""
    items.sort(key=lambda it: (-it["_sort"], it["_last"] or "9999", it["_tiebreak"]))
    out = []
    for rank, it in enumerate(items, start=1):
        out.append({"rank": rank, "name": it["name"], "department": it["department"],
                    "value": it["value"], "label": it["label"], "user_id": it["user_id"],
                    "avatar": it.get("avatar"), "avatar_color": it.get("avatar_color")})
    return out


def _department_rows(conn, start, end, roles=PLAYER_ROLES):
    """Average steps per member for each department between two dates.

    Members with no steps count as 0, so big departments cannot hide inactive people.
    roles limits it to teacher departments or student classes.
    """
    marks = ",".join("?" * len(roles))
    rows = conn.execute(
        "SELECT u.department AS department, COUNT(*) AS members, "
        "COALESCE(SUM(w.total), 0) AS total, MAX(w.last_update) AS last_update "
        "FROM users u LEFT JOIN ("
        "  SELECT user_id, SUM(steps) AS total, MAX(updated_at) AS last_update "
        "  FROM steps WHERE date BETWEEN ? AND ? GROUP BY user_id"
        ") w ON w.user_id = u.id "
        f"WHERE u.role IN ({marks}) AND u.department IS NOT NULL "
        "AND u.department <> '' GROUP BY u.department",
        (_day(start), _day(end), *roles),
    ).fetchall()
    items = []
    for r in rows:
        avg = r["total"] / r["members"]
        items.append({"name": r["department"], "department": r["department"],
                      "value": round(avg), "label": f"{round(avg):,} avg steps",
                      "user_id": None, "_sort": avg, "_last": r["last_update"],
                      "_tiebreak": r["department"]})
    return _ranked(items)


def leaderboard(conn, view, today, role=None):
    """This week's ranking. view: teacher | student | department | effort | improvement.

    Rows: {"rank", "name", "department", "value", "label", "user_id",
           "avatar", "avatar_color"} (avatar fields are None for departments).
    Only display name, department and the value are shown; admins never appear.
    People with no steps this week are left off the person boards.
    role ("student" or "teacher") keeps the department, effort and improvement
    boards to that group only; None (admins) includes both.
    """
    today = calc.to_date(today)
    monday, sunday = calc.week_bounds(today)
    roles = (role,) if role in PLAYER_ROLES else PLAYER_ROLES
    items = []

    if view in ("teacher", "student"):
        for p in _player_totals(conn, monday, sunday, roles=(view,)).values():
            items.append({"name": p["display_name"], "department": p["department"],
                          "value": p["total"], "label": f"{p['total']:,} steps",
                          "user_id": p["id"], "_sort": p["total"],
                          "avatar": p["avatar"], "avatar_color": p["avatar_color"],
                          "_last": p["last_update"], "_tiebreak": p["id"]})

    elif view == "department":
        return _department_rows(conn, monday, sunday, roles)

    elif view == "effort":
        # % of their own weekly goal (daily goal x 7): fair for every age and fitness level
        for p in _player_totals(conn, monday, sunday, roles).values():
            ratio = p["total"] / (p["daily_goal"] * 7) * 100
            items.append({"name": p["display_name"], "department": p["department"],
                          "value": round(ratio), "label": f"{round(ratio)}% of weekly goal",
                          "user_id": p["id"], "_sort": ratio,
                          "avatar": p["avatar"], "avatar_color": p["avatar_color"],
                          "_last": p["last_update"], "_tiebreak": p["id"]})

    elif view == "improvement":
        # Fair mid-week: compare Monday-to-today with the same days last week.
        this_week = _player_totals(conn, monday, today, roles)
        last_week = _player_totals(conn, monday - timedelta(days=7), today - timedelta(days=7), roles)
        for uid, p in this_week.items():
            before = last_week.get(uid, {}).get("total", 0)
            if before < config.IMPROVEMENT_MIN_LAST_WEEK:
                continue   # nothing fair to compare against
            change = (p["total"] - before) / before * 100
            items.append({"name": p["display_name"], "department": p["department"],
                          "value": round(change), "label": f"{round(change):+d}% vs last week",
                          "user_id": uid, "_sort": change,
                          "avatar": p["avatar"], "avatar_color": p["avatar_color"],
                          "_last": p["last_update"], "_tiebreak": uid})
    else:
        raise ValueError("view must be teacher, student, department, effort or improvement")

    return _ranked(items)


def history(conn, user_id, days, today):
    """The user's last `days` days, oldest first (for charts). Only for the user themself."""
    user = _require_user(conn, user_id)
    days = calc.parse_int(days, "days", 1, 366)
    today = calc.to_date(today)
    start = today - timedelta(days=days - 1)

    steps = {r["date"]: r for r in conn.execute(
        "SELECT date, steps, source FROM steps WHERE user_id = ? AND date BETWEEN ? AND ?",
        (user_id, start.isoformat(), today.isoformat()))}
    moods = {r["date"]: r["mood"] for r in conn.execute(
        "SELECT date, mood FROM moods WHERE user_id = ? AND date BETWEEN ? AND ?",
        (user_id, start.isoformat(), today.isoformat()))}

    out = []
    for i in range(days):
        day = (start + timedelta(days=i)).isoformat()
        row = steps.get(day)
        count = row["steps"] if row else 0
        out.append({"date": day, "steps": count, "goal_met": count >= user["daily_goal"],
                    "mood": moods.get(day), "source": row["source"] if row else None})
    return out


def weekly_wrapup(conn, user_id, today):
    """Game stage 4 (Reflect): this week vs last week, best day, mood vs steps, insight.

    change_percent compares Monday-to-today with the same days last week, so it
    is fair on any day of the week. last_week is last week's full total.
    """
    user = _require_user(conn, user_id)
    today = calc.to_date(today)
    monday, _ = calc.week_bounds(today)
    last_monday = monday - timedelta(days=7)

    this_week = _sum_steps(conn, user_id, monday, today)
    last_week = _sum_steps(conn, user_id, last_monday, monday - timedelta(days=1))
    last_week_same_days = _sum_steps(conn, user_id, last_monday, today - timedelta(days=7))

    week_days = history(conn, user_id, (today - monday).days + 1, today)
    daily = [{"date": d["date"], "day": calc.to_date(d["date"]).strftime("%a"),
              "steps": d["steps"], "goal_met": d["goal_met"]} for d in week_days]
    best = max(daily, key=lambda d: d["steps"])   # first (earliest) day wins a tie
    best_day = {"date": best["date"], "steps": best["steps"]} if best["steps"] > 0 else None

    recent = history(conn, user_id, config.MOOD_CHART_DAYS, today)
    pairs = [d for d in recent if d["mood"] is not None and d["source"] is not None]
    mood_vs_steps = [{"date": d["date"], "steps": d["steps"], "mood": d["mood"]} for d in pairs]
    goal_moods = [d["mood"] for d in pairs if d["goal_met"]]
    other_moods = [d["mood"] for d in pairs if not d["goal_met"]]

    return {
        "this_week": this_week,
        "last_week": last_week,
        "change_percent": calc.percent_change(this_week, last_week_same_days),
        "tier": calc.tier_for(this_week),
        "last_tier": calc.tier_for(last_week),
        "best_day": best_day,
        "daily": daily,
        "mood_vs_steps": mood_vs_steps,
        "insight": calc.insight_sentence(this_week, last_week_same_days, goal_moods, other_moods),
        "daily_goal": user["daily_goal"],
    }


# =====================================================================
# Challenges
# =====================================================================

def active_challenges(conn, today, role=None):
    """Open challenges (not closed, not finished), with progress so far.

    role ("student" or "teacher") keeps the department standings to that group
    (student classes or teacher departments); None (admins) includes both.
    The distance total stays school-wide, since the target is set for everyone.
    """
    today = calc.to_date(today)
    roles = (role,) if role in PLAYER_ROLES else PLAYER_ROLES
    rows = conn.execute(
        "SELECT * FROM challenges WHERE active = 1 AND end_date >= ? ORDER BY start_date, id",
        (today.isoformat(),),
    ).fetchall()

    out = []
    for c in rows:
        start = calc.to_date(c["start_date"])
        end = min(calc.to_date(c["end_date"]), today)   # count only days so far
        if start > today:
            total, standings = 0, []                    # not started yet
        else:
            total = conn.execute(
                "SELECT COALESCE(SUM(s.steps), 0) FROM steps s JOIN users u ON u.id = s.user_id "
                "WHERE u.role IN ('teacher', 'student') AND s.date BETWEEN ? AND ?",
                (start.isoformat(), end.isoformat()),
            ).fetchone()[0]
            standings = [{"rank": d["rank"], "department": d["department"],
                          "value": d["value"], "label": d["label"]}
                         for d in _department_rows(conn, start, end, roles)]
        target = c["target_steps"]
        out.append({
            "id": c["id"], "title": c["title"], "description": c["description"],
            "kind": c["kind"], "start_date": c["start_date"], "end_date": c["end_date"],
            "target_steps": target, "total_steps": total, "km": calc.steps_to_km(total),
            "target_km": calc.steps_to_km(target) if target else None,
            "percent": min(100, round(total / target * 100)) if target else None,
            "standings": standings,
        })
    return out


def create_challenge(conn, title, description, kind, target_steps, start_date, end_date):
    """Add a challenge (admin). Returns its id. Distance challenges need target_steps."""
    title = (title or "").strip()
    if not 1 <= len(title) <= 100:
        raise ValueError("title must be 1-100 characters")
    description = (description or "").strip() or None
    if description and len(description) > 500:
        raise ValueError("description must be at most 500 characters")
    if kind not in ("department", "school_distance"):
        raise ValueError("kind must be department or school_distance")
    if target_steps in (None, ""):
        if kind == "school_distance":
            raise ValueError("a distance challenge needs target_steps")
        target_steps = None
    else:
        target_steps = calc.parse_int(target_steps, "target_steps", 1, 100_000_000)
    start, end = calc.to_date(start_date), calc.to_date(end_date)
    if end < start:
        raise ValueError("end date must be on or after the start date")
    if (end - start).days > 365:
        raise ValueError("a challenge can last at most one year")

    cur = conn.execute(
        "INSERT INTO challenges (title, description, kind, target_steps, start_date, end_date, active) "
        "VALUES (?, ?, ?, ?, ?, ?, 1)",
        (title, description, kind, target_steps, start.isoformat(), end.isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def close_challenge(conn, challenge_id):
    """Close a challenge so it no longer shows."""
    cur = conn.execute("UPDATE challenges SET active = 0 WHERE id = ?", (challenge_id,))
    if cur.rowcount == 0:
        raise ValueError("challenge not found")
    conn.commit()


def suggested_distance_target(conn, days, today=None):
    """A fair target for a distance challenge: active users x 7,000 steps x days.

    Active = teachers/students with steps in the last 14 days (or everyone if nobody yet).
    """
    days = calc.parse_int(days, "days", 1, 366)
    since = _today(today) - timedelta(days=config.ACTIVE_USER_DAYS - 1)
    active = conn.execute(
        "SELECT COUNT(DISTINCT s.user_id) FROM steps s JOIN users u ON u.id = s.user_id "
        "WHERE u.role IN ('teacher', 'student') AND s.date >= ?", (since.isoformat(),),
    ).fetchone()[0]
    if active == 0:
        active = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role IN ('teacher', 'student')").fetchone()[0]
    return max(active, 1) * config.DISTANCE_STEPS_PER_USER_PER_DAY * days


# =====================================================================
# Impact numbers for the judges
# =====================================================================

def impact_stats(conn, today=None):
    """Numbers that show real impact.

    avg_before / avg_during: average daily steps on dates before / from the day
    each user joined (created_at). users_hitting_goal: people who met their goal
    at least once in the last 7 days. mood_*: average mood on goal days vs other days.
    """
    today = _today(today)

    def one(sql, params=()):
        value = conn.execute(sql, params).fetchone()[0]
        return value

    joined = ("FROM steps s JOIN users u ON u.id = s.user_id "
              "WHERE u.role IN ('teacher', 'student') ")
    avg_before = one(f"SELECT AVG(s.steps) {joined} AND s.date < substr(u.created_at, 1, 10)")
    avg_during = one(f"SELECT AVG(s.steps) {joined} AND s.date >= substr(u.created_at, 1, 10)")
    hitting = one(f"SELECT COUNT(DISTINCT s.user_id) {joined} AND s.steps >= u.daily_goal "
                  f"AND s.date >= ?", ((today - timedelta(days=6)).isoformat(),))

    by_source = {source: 0 for source in config.SOURCES}
    for r in conn.execute(f"SELECT s.source, COUNT(*) AS n {joined} GROUP BY s.source"):
        by_source[r["source"]] = r["n"]

    mood_sql = ("SELECT AVG(m.mood) FROM moods m "
                "JOIN steps s ON s.user_id = m.user_id AND s.date = m.date "
                "JOIN users u ON u.id = m.user_id "
                "WHERE u.role IN ('teacher', 'student') AND s.steps {} u.daily_goal")
    mood_goal = one(mood_sql.format(">="))
    mood_other = one(mood_sql.format("<"))

    return {
        "avg_before": round(avg_before) if avg_before is not None else None,
        "avg_during": round(avg_during) if avg_during is not None else None,
        "users_hitting_goal": hitting,
        "entries_by_source": by_source,
        "mood_goal_days": round(mood_goal, 1) if mood_goal is not None else None,
        "mood_other_days": round(mood_other, 1) if mood_other is not None else None,
    }


# =====================================================================
# Weekly adaptive goals
# =====================================================================

def update_weekly_goals(conn, today=None):
    """Recompute daily goals from each user's last 14 days of data.

    Skips admins, users with a custom goal, and users with fewer than 14 days.
    Today is not counted (it is not finished). Returns how many goals changed.
    """
    today = _today(today)
    users = conn.execute("SELECT id, daily_goal FROM users WHERE role IN ('teacher', 'student') "
                         "AND goal_is_custom = 0").fetchall()
    changed = 0
    for u in users:
        recent = [r["steps"] for r in conn.execute(
            "SELECT steps FROM steps WHERE user_id = ? AND date < ? ORDER BY date DESC LIMIT ?",
            (u["id"], today.isoformat(), config.ADAPTIVE_MIN_DAYS))]
        new_goal = calc.adaptive_goal(recent)
        if new_goal is not None and new_goal != u["daily_goal"]:
            conn.execute("UPDATE users SET daily_goal = ? WHERE id = ?", (new_goal, u["id"]))
            changed += 1
    _set_meta(conn, "goals_updated_week", calc.week_bounds(today)[0].isoformat())
    conn.commit()
    return changed


def maybe_update_goals(conn, today=None):
    """Run update_weekly_goals once per week (the first time this is called in a week).

    Returns True if it ran. The website calls this before requests.
    """
    monday = calc.week_bounds(_today(today))[0].isoformat()
    if _get_meta(conn, "goals_updated_week") == monday:
        return False
    update_weekly_goals(conn, today)
    return True


# ------------------------------------------------------------------ mini challenges

def mini_label(key):
    """'10 push-ups', '30-second plank', 'Walk 1,000 steps'."""
    c = config.MINI_CHALLENGES[key]
    if c["track"] == "steps":
        return f"Walk {c['amount']:,} steps"
    if c["track"] == "planks":
        return f"{c['amount']}-second plank"
    return f"{c['amount']} {config.TRACKS[c['track']]['unit']}"


def _now(now):
    return now or datetime.fromisoformat(local_now_iso())


def _steps_on(conn, user_id, day):
    row = conn.execute("SELECT steps FROM steps WHERE user_id = ? AND date = ?",
                       (user_id, day)).fetchone()
    return row["steps"] if row else 0


def _active_run(conn, user_id):
    return conn.execute("SELECT * FROM mini_runs WHERE user_id = ? AND status = 'active' "
                        "ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()


def _done_today(conn, user_id, day):
    rows = conn.execute("SELECT key, COUNT(*) AS n FROM mini_runs WHERE user_id = ? AND date = ? "
                        "AND status = 'done' GROUP BY key", (user_id, day)).fetchall()
    return {r["key"]: r["n"] for r in rows}


def _complete_run(conn, run, now):
    """Mark a run done, add it to the Challenges track and pay its EXP. Returns a summary."""
    c = config.MINI_CHALLENGES[run["key"]]
    day = now.date().isoformat()
    if c["track"] != "steps":   # walks already count through the phone's steps
        conn.execute("INSERT INTO exercises (user_id, date, type, amount, created_at) "
                     "VALUES (?, ?, ?, ?, ?)", (run["user_id"], day, c["track"], c["amount"],
                                                now.isoformat(timespec="seconds")))
    conn.execute("UPDATE mini_runs SET status = 'done', finished_at = ? WHERE id = ?",
                 (now.isoformat(timespec="seconds"), run["id"]))
    conn.execute("INSERT INTO exp_ledger (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
                 (run["user_id"], c["exp"], "Mini challenge: " + mini_label(run["key"]),
                  now.isoformat(timespec="seconds")))
    conn.commit()
    return {"key": run["key"], "label": mini_label(run["key"]), "exp": c["exp"],
            "track": c["track"], "balance": exp_balance(conn, run["user_id"])}


def check_walks(conn, user_id, now=None):
    """Finish an active walk if the phone has sent enough new steps. Returns the summary or None.

    A walk started on an earlier day can't be measured any more (steps restart at midnight),
    so it is quietly dropped.
    """
    now = _now(now)
    run = _active_run(conn, user_id)
    if not run or config.MINI_CHALLENGES[run["key"]]["track"] != "steps":
        return None
    if run["date"] != now.date().isoformat():
        conn.execute("UPDATE mini_runs SET status = 'quit', finished_at = ? WHERE id = ?",
                     (now.isoformat(timespec="seconds"), run["id"]))
        conn.commit()
        return None
    c = config.MINI_CHALLENGES[run["key"]]
    walked = _steps_on(conn, user_id, run["date"]) - run["base_steps"]
    elapsed = (now - datetime.fromisoformat(run["started_at"])).total_seconds()
    if walked >= c["amount"] and elapsed >= c["min_seconds"]:
        return _complete_run(conn, run, now)
    return None


def mini_state(conn, user_id, now=None):
    """Everything the mini challenge panel needs.

    {"active": {...} or None, "challenges": [...], "exp_today": n, "balance": n}
    """
    now = _now(now)
    day = now.date().isoformat()
    _require_user(conn, user_id)
    done = _done_today(conn, user_id, day)
    active = None
    run = _active_run(conn, user_id)
    if run:
        c = config.MINI_CHALLENGES[run["key"]]
        elapsed = int((now - datetime.fromisoformat(run["started_at"])).total_seconds())
        active = {"key": run["key"], "label": mini_label(run["key"]), "track": c["track"],
                  "amount": c["amount"], "exp": c["exp"], "elapsed": max(0, elapsed),
                  "wait": max(0, c["min_seconds"] - elapsed), "started_at": run["started_at"]}
        if c["track"] == "steps":
            walked = max(0, _steps_on(conn, user_id, day) - run["base_steps"])
            active.update(walked=min(walked, c["amount"]), base_steps=run["base_steps"],
                          percent=min(100, walked * 100 // c["amount"]))
    items = []
    for key, c in config.MINI_CHALLENGES.items():
        n = done.get(key, 0)
        items.append({"key": key, "label": mini_label(key), "track": c["track"], "exp": c["exp"],
                      "done_today": n, "left_today": max(0, config.MINI_DAILY_LIMIT - n)})
    exp_today = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM exp_ledger WHERE user_id = ? AND amount > 0 "
        "AND reason LIKE 'Mini challenge:%' AND substr(created_at, 1, 10) = ?",
        (user_id, day)).fetchone()[0]
    return {"active": active, "challenges": items, "exp_today": exp_today,
            "balance": exp_balance(conn, user_id), "daily_limit": config.MINI_DAILY_LIMIT}


def start_mini(conn, user_id, key, now=None):
    """Start a mini challenge. Only one at a time, each up to MINI_DAILY_LIMIT times a day."""
    now = _now(now)
    if key not in config.MINI_CHALLENGES:
        raise ValueError("that mini challenge doesn't exist")
    _require_user(conn, user_id)
    if _active_run(conn, user_id):
        raise ValueError("finish or back out of your current challenge first")
    day = now.date().isoformat()
    if _done_today(conn, user_id, day).get(key, 0) >= config.MINI_DAILY_LIMIT:
        raise ValueError(f"you've done {mini_label(key)} {config.MINI_DAILY_LIMIT} times today. "
                         "Try a different one, or come back tomorrow")
    conn.execute("INSERT INTO mini_runs (user_id, key, date, base_steps, started_at) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (user_id, key, day, _steps_on(conn, user_id, day), now.isoformat(timespec="seconds")))
    conn.commit()


def finish_mini(conn, user_id, now=None):
    """Tap Done on the active exercise challenge. Returns the summary from _complete_run."""
    now = _now(now)
    run = _active_run(conn, user_id)
    if not run:
        raise ValueError("you don't have a challenge going")
    c = config.MINI_CHALLENGES[run["key"]]
    if c["track"] == "steps":
        raise ValueError("walks finish by themselves once your phone sends the new steps")
    elapsed = (now - datetime.fromisoformat(run["started_at"])).total_seconds()
    if elapsed < c["min_seconds"]:
        left = int(c["min_seconds"] - elapsed + 0.999)
        raise ValueError(f"that was quick! Give it {left} more second{'s' if left != 1 else ''}")
    return _complete_run(conn, run, now)


def quit_mini(conn, user_id, now=None):
    """Back out of the active challenge. No EXP, nothing lost."""
    now = _now(now)
    run = _active_run(conn, user_id)
    if not run:
        raise ValueError("you don't have a challenge going")
    conn.execute("UPDATE mini_runs SET status = 'quit', finished_at = ? WHERE id = ?",
                 (now.isoformat(timespec="seconds"), run["id"]))
    conn.commit()
    return mini_label(run["key"])


# ------------------------------------------------------------------ recovery email + PIN reset

def has_email(conn, user_id):
    row = conn.execute("SELECT email_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["email_hash"])


def _new_email_code(conn, purpose, user_id, email, fingerprint, now):
    stamp = now.isoformat(timespec="seconds")
    cutoff = (now - timedelta(days=1)).isoformat(timespec="seconds")
    conn.execute("DELETE FROM email_codes WHERE created_at < ? OR (user_id = ? AND purpose = ?)",
                 (cutoff, user_id, purpose))
    code = _new_code()
    cur = conn.execute(
        "INSERT INTO email_codes (purpose, user_id, email, email_hash, code_hash, sent_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (purpose, user_id, email.strip(), fingerprint, generate_password_hash(code), stamp, stamp))
    conn.commit()
    return cur.lastrowid, email.strip(), code


def start_email_link(conn, secret, user_id, email, now=None):
    """A logged-in person adds (or changes) their recovery email. Returns (id, email, code)."""
    now = _now(now)
    _require_user(conn, user_id)
    fingerprint = email_fingerprint(email, secret)
    row = conn.execute("SELECT id FROM users WHERE email_hash = ?", (fingerprint,)).fetchone()
    if row and row["id"] != user_id:
        raise ValueError("that email is already used by another account")
    if row:
        raise ValueError("that email is already your recovery email")
    return _new_email_code(conn, "link", user_id, email, fingerprint, now)


def start_pin_reset(conn, secret, email, now=None):
    """'Forgot your PIN?': (id, email, code) if an account has this email, else None.

    The page says the same thing either way, so it can't be used to find out who has an account.
    """
    now = _now(now)
    fingerprint = email_fingerprint(email, secret)
    row = conn.execute("SELECT id FROM users WHERE email_hash = ?", (fingerprint,)).fetchone()
    if row is None:
        return None
    return _new_email_code(conn, "reset", row["id"], email, fingerprint, now)


def email_code_info(conn, code_id, purpose):
    """{"email", "user_id"} for a waiting code, or None."""
    row = conn.execute("SELECT email, user_id FROM email_codes WHERE id = ? AND purpose = ?",
                       (code_id, purpose)).fetchone()
    return dict(row) if row else None


def resend_email_code(conn, code_id, purpose, now=None):
    now = _now(now)
    row = conn.execute("SELECT * FROM email_codes WHERE id = ? AND purpose = ?", (code_id, purpose)).fetchone()
    if row is None:
        raise ValueError("that has expired. Please start again")
    waited = (now - datetime.fromisoformat(row["sent_at"])).total_seconds()
    if waited < config.CODE_RESEND_SECONDS:
        raise ValueError(f"please wait {int(config.CODE_RESEND_SECONDS - waited) + 1} seconds before asking again")
    if row["sends"] >= config.CODE_MAX_SENDS:
        raise ValueError("too many codes sent. Please try again later")
    code = _new_code()
    conn.execute("UPDATE email_codes SET code_hash = ?, sends = sends + 1, attempts = 0, sent_at = ? WHERE id = ?",
                 (generate_password_hash(code), now.isoformat(timespec="seconds"), code_id))
    conn.commit()
    return row["email"], code


def _check_email_code(conn, code_id, purpose, code, now):
    row = conn.execute("SELECT * FROM email_codes WHERE id = ? AND purpose = ?", (code_id, purpose)).fetchone()
    if row is None:
        raise ValueError("that has expired. Please start again")
    if (now - datetime.fromisoformat(row["sent_at"])).total_seconds() > config.CODE_MINUTES * 60:
        raise ValueError("that code has expired. Tap 'Send a new code'")
    if row["attempts"] >= config.CODE_TRIES:
        raise ValueError("too many wrong codes. Tap 'Send a new code'")
    code = str(code or "").strip().translate(calc._DIGITS).replace(" ", "")
    if not check_password_hash(row["code_hash"], code):
        conn.execute("UPDATE email_codes SET attempts = attempts + 1 WHERE id = ?", (code_id,))
        conn.commit()
        left = config.CODE_TRIES - row["attempts"] - 1
        raise ValueError(f"that code isn't right. {left} tr{'y' if left == 1 else 'ies'} left"
                         if left else "that code isn't right. Tap 'Send a new code'")
    return row


def finish_email_link(conn, code_id, user_id, code, now=None):
    """Check the code and save the recovery email (as a fingerprint) on the account."""
    row = _check_email_code(conn, code_id, "link", code, _now(now))
    if row["user_id"] != user_id:
        raise ValueError("that has expired. Please start again")
    taken = conn.execute("SELECT id FROM users WHERE email_hash = ? AND id != ?",
                         (row["email_hash"], user_id)).fetchone()
    if taken:
        raise ValueError("that email is already used by another account")
    conn.execute("UPDATE users SET email_hash = ? WHERE id = ?", (row["email_hash"], user_id))
    conn.execute("DELETE FROM email_codes WHERE id = ?", (code_id,))
    conn.commit()


def remove_email(conn, user_id):
    conn.execute("UPDATE users SET email_hash = NULL WHERE id = ?", (user_id,))
    conn.commit()


def finish_pin_reset(conn, code_id, code, pin, pin_again, now=None):
    """Check the code and set a new PIN. Returns the user id."""
    pin = clean_pin(pin)
    if pin != str(pin_again or "").strip():
        raise ValueError("the two PINs don't match")
    row = _check_email_code(conn, code_id, "reset", code, _now(now))
    conn.execute("UPDATE users SET pin_hash = ? WHERE id = ?", (generate_password_hash(pin), row["user_id"]))
    conn.execute("DELETE FROM email_codes WHERE id = ?", (code_id,))
    conn.commit()
    return row["user_id"]
