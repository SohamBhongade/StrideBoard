"""StrideBoard website (Agent 3).

The pages people see. All data comes from data.py (Agent 1); this file never
writes SQL. Run from the server folder with:  flask run
"""
import gzip
import io
import json
import os
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from flask.sessions import SecureCookieSessionInterface
from zoneinfo import ZoneInfo

from flask import (Flask, abort, current_app, send_file, flash, g, get_flashed_messages, jsonify, redirect,
                   render_template, request, session, url_for)

import api
import backup
import avatar_art
import material
import config
import data
import db
import mailer
import mini_scene

TZ = ZoneInfo("Asia/Dubai")
SHORTCUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "ios", "Strideboard.shortcut")

# Display settings. The game rules themselves live in data.py / calc.py.
TIERS = list(config.TIERS)  # from Agent 1's config.py, so the rules live in one place
LEADERBOARD_PERIODS = [("day", "Today"), ("week", "This week"), ("month", "This month"), ("all", "All time")]
LEADERBOARD_VIEWS = [("student", "Students"), ("teacher", "Teachers"),
                     ("department", "Classes & departments"), ("effort", "Effort"),
                     ("improvement", "Most improved")]
AGE_BANDS = [("under_13", "Under 13"), ("teen_13_17", "13 to 17"),
             ("adult_18_39", "18 to 39"), ("adult_40_59", "40 to 59"),
             ("senior_60_plus", "60 and over")]
BOARD_APP_DOWNLOADS = "https://github.com/SohamBhongade/StrideBoard/releases/download/leaderboard-app-latest/"
BOARD_ROWS = 8            # people per board on the leaderboard screen
LEADERBOARD_TOP = 50       # rows shown before "Show everyone"
MOODS = [(1, "Low"), (2, "Meh"), (3, "Okay"), (4, "Good"), (5, "Great")]
# badge key -> (name, icon, colour, how to earn it). Names come from config.BADGES below.
_BADGE_LOOK = {
    "first_log": ("First log", "flag", "blue", "Log steps for the first time"),
    "ten_k": ("10K day", "star", "pink", "Walk 10,000 steps in one day"),
    "streak_3": ("3-day streak", "flame", "peach", "Hit your goal 3 days in a row"),
    "streak_7": ("7-day streak", "flame", "pink", "Hit your goal 7 days in a row"),
    "consistent": ("Consistent", "calendar", "blue", "Log steps on 5 days in one week"),
    "comeback": ("Comeback", "trend", "violet", "Beat last week by 25% or more"),
    "platinum": ("Platinum", "gem", "mint", "Reach the Platinum tier"),
}
BADGES = {k: (config.BADGES.get(k, v[0]),) + v[1:] for k, v in _BADGE_LOOK.items()}

# How each progression track looks: icon and colour (the levels live in config.TRACKS).
TRACK_LOOK = {"steps": ("foot", "blue"), "pushups": ("pushup", "pink"), "squats": ("squat", "peach"),
              "planks": ("plank", "mint"), "jumping_jacks": ("jump", "violet")}
RECORD_VERB = {"steps": "Walk {n} steps in one day", "pushups": "Do {n} push-ups in one day",
               "squats": "Do {n} squats in one day", "planks": "Plank for {n} in one day",
               "jumping_jacks": "Do {n} jumping jacks in one day"}

WATER_TARGET = 8  # glasses a day: placeholder suggestion, team to verify like the step goals
# Bump this whenever style.css, app.js or the font change, so phones load the new
# files instead of their saved copy (the service worker picks it up automatically).
ASSET_VERSION = "62"

# Pages that still work after a parent's daily time limit is used up.
TIME_FREE = {"logout", "static", "service_worker", "offline", "privacy", "parent", "board"}

PUBLIC_ENDPOINTS = {"privacy", "parent", "login", "signup", "signup_verify", "forgot", "logout", "static", "offline", "service_worker",
                    "board"}


def today():
    """Today's date in Dubai as "YYYY-MM-DD" (never date.today(): servers run in UTC)."""
    return db.local_today().isoformat()


def days_back(n):
    """[today, yesterday, ...] as "YYYY-MM-DD" strings, n+1 entries."""
    t = datetime.now(TZ).date()
    return [(t - timedelta(days=i)).isoformat() for i in range(n + 1)]


def first_upper(text):
    """Capital first letter only ("earn the 10K Club badge" -> "Earn the 10K Club badge")."""
    return text[:1].upper() + text[1:]


def to_int(value, field):
    """Read a whole number from a form. int() also accepts Arabic-Indic digits."""
    try:
        return int(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a whole number")


class HttpsOnlyCookies(SecureCookieSessionInterface):
    """The login cookie is marked Secure (sent only over HTTPS) whenever the site is on HTTPS.
    On a laptop over plain http it still works."""
    def get_cookie_secure(self, app):
        return bool(app.config.get("SESSION_COOKIE_SECURE")) or request.is_secure


def create_app():
    app = Flask(__name__)
    app.session_interface = HttpsOnlyCookies()
    # No SECRET_KEY here: db.init_app() sets it from the server's environment.
    app.config.update(SEND_PARENT=mailer.send_parent_request)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=timedelta(days=config.SESSION_IDLE_DAYS),
                      SEND_CODE=mailer.send_code)   # tests swap this out

    moved_to = config.MOVED_TO
    if moved_to:
        add_moved(app, moved_to)   # this copy is the old address: send everyone to the new one
        return app

    db.init_app(app)
    app.register_blueprint(api.bp)
    add_speed(app)
    add_template_helpers(app)
    add_security(app)
    add_routes(app)
    return app


# -------------------------------------------------------------------- moved

def add_moved(app, new_base):
    """The old address after a move: pages redirect to the same page on the new address, and
    phones get a clear message instead of their steps vanishing into an empty database."""
    new_base = new_base.rstrip("/")

    @app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
    @app.route("/<path:path>", methods=["GET", "POST"])
    def moved(path):
        if path.startswith("api/"):
            return jsonify(ok=False, error="moved", moved_to=new_base,
                           message=f"StrideBoard has moved to {new_base.split('//')[-1]}. "
                                   "Get the new iPhone Shortcut or Android app from Settings there."), 410
        target = f"{new_base}/{path}"
        if request.query_string:
            target += "?" + request.query_string.decode("latin-1")
        return redirect(target, code=301)


# -------------------------------------------------------------------- speed

COMPRESSIBLE = ("text/", "application/javascript", "application/json", "image/svg+xml",
                "application/manifest+json")


_IMPACT_CACHE = {}          # database path -> (time made, numbers)
IMPACT_CACHE_SECONDS = 60


def cached_impact_stats(conn):
    """The Admin impact numbers, reused for up to a minute.

    They add up every step ever logged (the slowest work on /admin), and they are
    school-wide totals that barely move in a minute. Any Admin action clears them.
    """
    if current_app.testing:
        return data.impact_stats(conn)
    key = current_app.config.get("DATABASE") or config.DATABASE
    hit = _IMPACT_CACHE.get(key)
    now = datetime.now().timestamp()
    if hit and now - hit[0] < IMPACT_CACHE_SECONDS:
        return hit[1]
    stats = data.impact_stats(conn)
    _IMPACT_CACHE[key] = (now, stats)
    return stats


_BOARD_CACHE = {}           # (database, view, day, role, period) -> (time made, rows)
BOARD_CACHE_SECONDS = 30


def cached_leaderboard(conn, view, day, role=None, period="week"):
    """A leaderboard, ranked once and reused for up to 30 seconds.

    Ranking the whole school is the biggest job on Home (its top-3 preview), Ranks and the
    TV screen. At break time hundreds of people open those within seconds, so one ranking is
    shared instead of redone for each of them. Rows are copied so a page can't change it.
    """
    if current_app.testing:
        return data.leaderboard(conn, view, day, role=role, period=period)
    key = (current_app.config.get("DATABASE") or config.DATABASE, view, str(day), role, period)
    now = datetime.now().timestamp()
    hit = _BOARD_CACHE.get(key)
    if not hit or now - hit[0] >= BOARD_CACHE_SECONDS:
        if len(_BOARD_CACHE) > 64:
            _BOARD_CACHE.clear()
        hit = (now, data.leaderboard(conn, view, day, role=role, period=period))
        _BOARD_CACHE[key] = hit
    return [dict(r) for r in hit[1]]


def clear_leaderboard_cache():
    """After a ban, rename or reset, show the change straight away."""
    _BOARD_CACHE.clear()


CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self'; "
       "manifest-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none'")


def add_speed(app):
    """Make pages load faster on phones and school Wi-Fi.

    - Files whose address carries ?v=<ASSET_VERSION> (CSS, JS, the font) never change,
      so phones may keep them for a year; a new version gets a new address.
    - Other static files (icons, manifest) are kept for a day.
    - Text responses are gzip-compressed: pages shrink to about a fifth.
    """
    @app.after_request
    def cache_and_compress(resp):
        # Security: the browser may only load scripts, styles, fonts and images from StrideBoard
        # itself and talk only to StrideBoard, so no outside code can read anyone's steps.
        # (Inline scripts are allowed because the pages use small ones of their own.)
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if request.is_secure:   # once a browser has seen HTTPS, it never tries plain http again
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if request.path.startswith("/static/") and resp.status_code == 200:
            if request.args.get("v"):
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                resp.headers["Cache-Control"] = "public, max-age=86400"

        if (resp.status_code == 200 and "gzip" in request.headers.get("Accept-Encoding", "")
                and resp.mimetype.startswith(COMPRESSIBLE) and "Content-Encoding" not in resp.headers):
            resp.direct_passthrough = False   # static files are streamed; read them to compress
            body = resp.get_data()
            if len(body) > 1024:
                resp.set_data(gzip.compress(body, compresslevel=6))
                resp.headers["Content-Encoding"] = "gzip"
                resp.headers.add("Vary", "Accept-Encoding")
        return resp


# ---------------------------------------------------------------- templates

def add_template_helpers(app):
    @app.template_filter("synced")
    def synced(iso):
        """When a phone last synced, short: 'Today 08:12', 'Yesterday 21:30', 'Mon 19 Oct', or 'Never'."""
        if not iso:
            return "Never"
        when = datetime.fromisoformat(iso)
        days = (db.local_today() - when.date()).days
        if days == 0:
            return f"Today {when:%H:%M}"
        if days == 1:
            return f"Yesterday {when:%H:%M}"
        return when.strftime("%a %-d %b")

    @app.template_filter("num")
    def num(n):
        """8423 -> "8,423"."""
        try:
            return f"{int(n):,}"
        except (TypeError, ValueError):
            return "0"

    @app.template_filter("amount")
    def amount_filter(n, track, short=False):
        return fmt_amount(n, track, short)

    @app.template_filter("nice_date")
    def nice_date(s, style="short"):
        """"2026-10-14" -> "Wed 14 Oct" (or "Wednesday" with style="day")."""
        try:
            d = datetime.strptime(str(s)[:10], "%Y-%m-%d")
        except ValueError:
            return s
        if str(s)[:10] == today():
            return "Today"
        if style == "day":
            return d.strftime("%A")
        if style == "tiny":
            return d.strftime("%a")
        return f"{d:%a} {d.day} {d:%b}"  # "Wed 14 Oct" (works on Windows too)

    @app.context_processor
    def globals_for_templates():
        now = datetime.now(TZ)
        return {"csrf_token": csrf_token, "user": g.get("user"), "TIERS": TIERS,
                "signup_open": config.SIGNUP_OPEN,
                "COPYRIGHT": config.COPYRIGHT,
                "in_android_app": "StrideBoardAndroid/" in request.headers.get("User-Agent", ""),
                # Apple devices (iPads in desktop mode say "Macintosh"): the iPhone Shortcut button
                "on_apple": bool(re.search(r"iPhone|iPad|iPod|Macintosh", request.headers.get("User-Agent", ""))),
                "today_label": f"{now:%A} {now.day} {now:%B}",
                "BADGES": BADGES, "MOODS": MOODS, "stand_due": stand_due(),
                "INACTIVE_MINUTES": config.INACTIVE_MINUTES, "INACTIVE_MAX_STEPS": config.INACTIVE_MAX_STEPS,
                "ASSET_VERSION": ASSET_VERSION, "TRACK_LOOK": TRACK_LOOK,
                "creature": creature, "avatar_sheet": avatar_sheet, "my_build": my_build(),
                "theme": current_theme(), "THEMES": THEMES, "fast": fast_mode(), "page_theme": page_theme(),
                "fixed_mode": fixed_mode(), "BREAK_SECONDS": config.BREAK_SECONDS,
                # Under-18s get a break reminder after a while; a parent's limit gets a ping
                "break_after": (config.BREAK_AFTER_MINUTES if g.get("user") and
                                g.user["age_band"] in data.UNDER_18 else 0),
                "screen_limit": (g.user.get("time_limit") or 0) if g.get("user") else 0,
                "try_on": lambda build, slot, key: {**build, slot: key},
                "my_glass": my_glass(), "GLASS_GRADIENTS": config.GLASS_GRADIENTS,
                "glass_bg": glass_bg, "glass_vars": glass_vars, "android": is_android(), "my_material": my_material,
                "MATERIAL_THEMES": config.MATERIAL_THEMES, "material_swatch": material.swatch,
                "AVATARS": config.AVATARS, "AVATAR_COLORS": config.AVATAR_COLORS}


# Appearance: remembered per phone/computer in a cookie, so the login page follows it too.
THEMES = [("light", "Light", "sun"), ("dark", "Dark", "moon"), ("auto", "Automatic", "phone")]
THEME_COOKIE = "theme"
FAST_COOKIE = "fast"        # Settings > Appearance > Fast mode ("1" = on), saved on the device


def fast_mode():
    return request.cookies.get(FAST_COOKIE) == "1"


def current_theme():
    choice = request.cookies.get(THEME_COOKIE)
    return choice if choice in dict((k, k) for k, _, _ in THEMES) else "light"


def creature(build, size=40, title=None):
    """Draw an avatar. Each different look is drawn once per page (see avatar_sheet)."""
    looks = g.setdefault("avatar_looks", {})
    key = avatar_art.look_key(build)
    looks.setdefault(key, dict(build))
    return avatar_art.render_use(key, size, title)


def avatar_sheet():
    """The drawings for every look used on this page. base.html puts it at the very end."""
    return avatar_art.render_sheet(g.pop("avatar_looks", {}))


def my_build():
    """The logged-in person's avatar parts, for the top bar (None when logged out)."""
    if not g.get("user") or request.blueprint == api.bp.name:
        return None
    if "my_build" not in g:
        g.my_build = data.avatar_build(db.get_db(), g.user["id"])
    return g.my_build


def my_glass():
    """The logged-in person's glass gradient colours: {"light": (...), "dark": (...)}."""
    key = config.GLASS_DEFAULT
    if g.get("user") and request.blueprint != api.bp.name:
        key = data.glass_choice(db.get_db(), g.user["id"])
    _, _, light, dark = config.GLASS_GRADIENTS[key]
    return {"key": key, "light": light, "dark": dark}


def is_android():
    """Android phones and tablets, Windows laptops and PCs, and Chromebooks (CrOS) get the
    Material Expressive look (Apple devices get glass)."""
    ua = request.headers.get("User-Agent", "")
    return "Android" in ua or "Windows" in ua or "CrOS" in ua


def fixed_mode():
    """On Android and Windows, Graphite and Black ignore the Light/Dark setting: "light", "dark" or None."""
    if not (g.get("user") and request.blueprint != api.bp.name and is_android()):
        return None
    return config.MATERIAL_FIXED_MODE.get(data.material_choice(db.get_db(), g.user["id"]))


def page_theme():
    """The theme the page is actually drawn in (the setting, unless the colour theme fixes it)."""
    return fixed_mode() or current_theme()


def android_app_update():
    """Inside the StrideBoard Android app, an older version gets a small Update notice on Home.

    Returns None (no notice), or {"name", "news", "in_app": True when the app can update itself,
    "url"}. Old apps (before the updater) send only "StrideBoardAndroid/1.0".
    """
    ua = request.headers.get("User-Agent", "")
    if "StrideBoardAndroid/" not in ua:
        return None
    m = re.search(r"StrideBoardApp/(\d+)", ua)
    code = int(m.group(1)) if m else 0
    latest = config.ANDROID_APP_LATEST
    if code >= latest["code"]:
        return None
    return {"name": latest["name"], "news": latest["news"], "url": config.ANDROID_APK_URL,
            "in_app": code >= config.ANDROID_APP_UPDATER_FROM}


def my_material():
    """CSS for the logged-in person's Material You colours, light and dark."""
    key = config.MATERIAL_DEFAULT
    if g.get("user") and request.blueprint != api.bp.name:
        key = data.material_choice(db.get_db(), g.user["id"])
    seed = config.MATERIAL_THEMES[key][2]
    return {"light": material.css_vars(seed), "dark": material.css_vars(seed, dark=True)}


def glass_vars(colours):
    """The glass colours as CSS variables (--g0 base, --g1..--g4 glows): the still background
    and the slowly drifting layer above it both use them."""
    return " ".join(f"--g{i}: {c};" for i, c in enumerate(colours))


def glass_bg(colours, unit="vmax"):
    """CSS background for a glass colour field: (base, 4 glows) as soft blobs in the corners.
    unit="%" sizes the blobs to a small box (the swatches in the Avatar studio)."""
    base, a, b, c, d = colours
    big = 2 if unit == "%" else 1     # in a small box, % blobs need to be bigger to look the same
    return (f"radial-gradient({60 * big}{unit} {60 * big}{unit} at 8% 10%, {a} 0%, transparent 60%), "
            f"radial-gradient({55 * big}{unit} {55 * big}{unit} at 95% 20%, {b} 0%, transparent 60%), "
            f"radial-gradient({60 * big}{unit} {60 * big}{unit} at 85% 95%, {c} 0%, transparent 60%), "
            f"radial-gradient({50 * big}{unit} {50 * big}{unit} at 10% 90%, {d} 0%, transparent 60%), {base}")


def with_builds(conn, rows):
    """Add each person's avatar parts to leaderboard rows (department rows get none)."""
    builds = data.avatar_builds(conn, [r.get("user_id") for r in rows])
    for r in rows:
        r["build"] = builds.get(r.get("user_id"))
    return rows


def stand_due():
    """True only when the phone's recent syncs show under 50 steps in 30+ minutes."""
    if not g.get("user") or request.blueprint == api.bp.name:
        return False
    return data.inactivity(db.get_db(), g.user["id"]).get("inactive") is True


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


# ----------------------------------------------------------------- security

def add_security(app):
    @app.before_request
    def load_user_and_check():
        g.user = None
        if request.blueprint == api.bp.name:
            return  # phones use their token, not a login session
        user_id = session.get("user_id")
        if user_id is not None:
            # Auto log-out after SESSION_IDLE_DAYS without using the site (checked here too,
            # not only by the cookie's expiry). "seen" is refreshed at most every 10 minutes.
            now_ts, seen = int(datetime.now().timestamp()), session.get("seen")
            if seen and now_ts - seen > config.SESSION_IDLE_DAYS * 86400:
                session.clear()
                flash(f"You were logged out after {config.SESSION_IDLE_DAYS} days away. Log in again.", "ok")
                user_id = None
            elif not seen or now_ts - seen > 600:
                session["seen"] = now_ts
        if user_id is not None:
            g.user = data.get_user(db.get_db(), user_id)
            if g.user is None:
                session.clear()
            else:
                block = data.block_status(db.get_db(), user_id)
                if block:
                    session.clear()
                    g.user = None
                    flash(block_message(block), "blocked")
                    if request.endpoint not in PUBLIC_ENDPOINTS:
                        return redirect(url_for("login"))
        if g.user is None and request.endpoint not in PUBLIC_ENDPOINTS:
            return redirect(url_for("login"))
        # A parent's daily time limit: count the minutes, and once they're used up only the
        # "Time's up" page shows (steps still sync from the phone, which doesn't use the site).
        if g.user is not None and g.user.get("time_limit") and request.endpoint not in TIME_FREE:
            used = data.note_screen_minute(db.get_db(), g.user["id"])
            g.screen_left = max(0, g.user["time_limit"] - used)
            if used > g.user["time_limit"] and request.endpoint != "ping":
                return render_template("time_up.html", limit=g.user["time_limit"]), 200
        if request.method == "POST":
            sent, expected = request.form.get("csrf", ""), session.get("csrf", "")
            if not expected or not secrets.compare_digest(sent, expected):
                abort(400)

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", title="Please try again",
                               message="That form had expired. Go back, refresh the page and try again."), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", title="Not allowed",
                               message="This page is only for admins."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", title="Page not found",
                               message="We couldn't find that page."), 404


SIGNUP_LOG = {}   # network address -> times of recent sign-ups (kept in memory)


def _prune(log, window):
    """Drop old entries from an in-memory limiter so it never grows without end."""
    if len(log) > 2000:
        now = datetime.now().timestamp()
        for key in [k for k, times in log.items() if not times or now - times[-1] > window]:
            del log[key]


def too_many_signups(addr, kind="signup"):
    now = datetime.now().timestamp()
    key = (kind, addr)
    recent = [t for t in SIGNUP_LOG.get(key, []) if now - t < 3600]
    SIGNUP_LOG[key] = recent
    return len(recent) >= config.SIGNUPS_PER_HOUR


def note_signup(addr, kind="signup"):
    _prune(SIGNUP_LOG, 3600)
    SIGNUP_LOG.setdefault((kind, addr), []).append(datetime.now().timestamp())


FAILED_LOGINS = {}   # name (lower case) -> times of recent wrong PINs (kept in memory)
LOGIN_TRIES, LOGIN_LOCK_MINUTES = 5, 15
FAILED_BY_ADDRESS = {}   # internet address -> times of recent wrong PINs, for any name
ADDRESS_TRIES = 20       # wrong PINs from one address (any names) within LOGIN_LOCK_MINUTES


def _login_key(name):
    return " ".join((name or "").lower().split())


def login_locked(name):
    """Minutes left if this name has had too many wrong PINs lately, else 0."""
    now = datetime.now().timestamp()
    recent = [t for t in FAILED_LOGINS.get(_login_key(name), []) if now - t < LOGIN_LOCK_MINUTES * 60]
    FAILED_LOGINS[_login_key(name)] = recent
    if len(recent) < LOGIN_TRIES:
        return 0
    return max(1, int((recent[0] + LOGIN_LOCK_MINUTES * 60 - now) // 60) + 1)


def note_failed_login(name, address=None):
    _prune(FAILED_LOGINS, LOGIN_LOCK_MINUTES * 60)
    now = datetime.now().timestamp()
    FAILED_LOGINS.setdefault(_login_key(name), []).append(now)
    if address:
        _prune(FAILED_BY_ADDRESS, LOGIN_LOCK_MINUTES * 60)
        FAILED_BY_ADDRESS.setdefault(address, []).append(now)


def address_locked(address):
    """True when one internet address has guessed wrong too often, whatever names it tried."""
    now = datetime.now().timestamp()
    recent = [t for t in FAILED_BY_ADDRESS.get(address, []) if now - t < LOGIN_LOCK_MINUTES * 60]
    FAILED_BY_ADDRESS[address] = recent
    return len(recent) >= ADDRESS_TRIES


def safe_back(target):
    """A path on this site to go back to, or None. Refuses anything that could leave the site:
    //evil.com, /\\evil.com (browsers read \\ as /), full addresses, control characters."""
    t = (target or "").strip()
    if not t.startswith("/") or t.startswith("//") or "\\" in t or any(ord(ch) < 32 for ch in t):
        return None
    parts = urlsplit(t)
    return t if not parts.scheme and not parts.netloc else None


def is_owner(user):
    """Only this account gets Moderation (time out, ban, rename, remove steps)."""
    return bool(user) and user["role"] == "admin" and user["username"] == config.OWNER_USERNAME


def block_message(block):
    """'This account is banned.' / 'This account is timed out until Wed 21 Oct, 14:30.' + reason."""
    if block["until"] is None:
        text = "This account is banned."
    else:
        when = datetime.fromisoformat(block["until"]).strftime("%a %d %b, %H:%M")
        text = f"This account is timed out until {when}."
    return text + (f" Reason: {block['reason']}" if block["reason"] else "")


def admin_only():
    if g.user["role"] != "admin":
        abort(403)


def safe_next(default="dashboard"):
    """Where to go after a small form (only our own pages, never a URL)."""
    return {"dashboard": "dashboard", "log": "log"}.get(request.form.get("next"), default)


# ------------------------------------------------------------------- routes

def add_routes(app):

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("dashboard"))
        username = ""
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            pin = request.form.get("pin", "").strip()
            user, locked = None, login_locked(username)
            if not locked and address_locked(request.remote_addr):
                locked = LOGIN_LOCK_MINUTES
            if locked:
                flash(f"Too many wrong PINs for that name. Wait {locked} minutes and try again, "
                      "or use 'Forgot your PIN?'.", "error")
                return render_template("login.html", username=username)
            if username and pin:
                if "@" in username:   # an email works too
                    user = data.authenticate_email(db.get_db(), app.config["SECRET_KEY"], username, pin)
                else:
                    user = data.authenticate_name(db.get_db(), username, pin)
            if not user and username:
                note_failed_login(username, request.remote_addr)
            block = data.block_status(db.get_db(), user["id"]) if user else None
            if block:
                flash(block_message(block), "blocked")
                return render_template("login.html", username=username)
            if user and user.get("parent_status") == "pending":
                data.clear_unapproved_children(db.get_db())
                if data.get_user(db.get_db(), user["id"]) is None:
                    flash("Your parent didn't approve in time, so that account was removed. "
                          "You can sign up again.", "error")
                else:
                    ask_parent(user["id"])
                    flash("Your account is waiting for your parent or guardian to approve it. "
                          "Ask them to open the StrideBoard email and tap Approve.", "error")
                return render_template("login.html", username=username)
            if user:
                session.clear()
                session.permanent = True  # stay signed in on phones
                session["user_id"] = user["id"]
                return redirect(url_for("dashboard"))
            flash("That full name and PIN don't match. Check them and try again.", "error")
        return render_template("login.html", username=username)

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        """New people make their own account as a student or teacher, checked by an email code."""
        if g.user:
            return redirect(url_for("dashboard"))
        form = request.form if request.method == "POST" else {}
        open_now = config.SIGNUP_OPEN and mailer.ready()
        if request.method == "POST" and open_now:
            try:
                if config.JOIN_CODE and form.get("code", "").strip().lower() != config.JOIN_CODE.lower():
                    raise ValueError("that school code isn't right. Ask your teacher for it")
                if form.get("agree_terms") != "1":
                    raise ValueError("please read and agree to the terms of use")
                if form.get("agree_privacy") != "1":
                    raise ValueError("please read and agree to the privacy policy")
                if too_many_signups(request.remote_addr):
                    raise ValueError("too many sign-ups from here. Try again in an hour")
                dept = form.get("class") if form.get("role") == "student" else form.get("department")
                data.clear_unapproved_children(db.get_db())
                pending, email, code = data.start_signup(
                    db.get_db(), app.config["SECRET_KEY"], form.get("email"),
                    form.get("display_name"), form.get("role"), dept,
                    form.get("age_band"), form.get("pin"), form.get("pin_again"),
                    parent_email=form.get("parent_email"))
                app.config["SEND_CODE"](email, code)
            except ValueError as e:
                flash(first_upper(str(e)), "error")
            else:
                note_signup(request.remote_addr)
                session["signup_id"] = pending
                return redirect(url_for("signup_verify"))
        return render_template("signup.html", form=form, age_bands=AGE_BANDS, open_now=open_now,
                               classes=config.SIGNUP_CLASSES, departments=config.SIGNUP_DEPARTMENTS,
                               need_code=bool(config.JOIN_CODE), domains=config.EMAIL_DOMAINS)

    @app.route("/privacy")
    def privacy():
        """Privacy policy and terms of use: open to everyone, linked from sign-up and every page."""
        school, contact, team = config.SCHOOL_NAME, config.PRIVACY_CONTACT, config.TEAM_NAMES
        if request.args.get("lang") == "ar":
            # The server settings are usually in English; their built-in defaults get Arabic ones.
            defaults = {"our school": "مدرستنا", "a StrideBoard admin at school": "أحد مسؤولي StrideBoard في المدرسة",
                        "the StrideBoard student team": "فريق طلاب StrideBoard"}
            return render_template("privacy_ar.html", school=defaults.get(school, school),
                                   contact=defaults.get(contact, contact), team=defaults.get(team, team),
                                   updated=config.PRIVACY_UPDATED)
        return render_template("privacy.html", school=school, contact=contact, team=team,
                               updated=config.PRIVACY_UPDATED)

    def ask_parent(uid, force=False):
        """Email the parent the approval link (at most once an hour). Returns where it went."""
        conn = db.get_db()
        req = data.parent_request(conn, uid, force=force)
        if not req:
            return None
        to, token = req
        try:
            app.config["SEND_PARENT"](to, data.get_user(conn, uid)["display_name"],
                                      url_for("parent", token=token, _external=True))
        except ValueError:
            return None
        return to

    @app.route("/report/<int:uid>", methods=["GET", "POST"])
    def report(uid):
        """Report someone on the leaderboards to the admins."""
        conn = db.get_db()
        target = data.get_user(conn, uid)
        if target is None or target["role"] == "admin":
            abort(404)
        if request.method == "POST":
            try:
                data.report_person(conn, g.user["id"], uid, request.form.get("reason"), request.form.get("note"))
            except ValueError as e:
                flash(first_upper(str(e)), "error")
                return redirect(url_for("report", uid=uid))
            flash("Thanks for telling us. An admin will check it. Your name isn't shown to the person you reported.", "ok")
            return redirect(url_for("leaderboard"))
        shown = data.shown_name(target["display_name"], data.board_name_choice(target)) or "this person"
        return render_template("report.html", target=target, shown=shown, reasons=data.REPORT_REASONS)

    @app.route("/parent/<token>", methods=["GET", "POST"])
    def parent(token):
        """For a parent: approve, decline, or later withdraw consent for an under-13's account."""
        conn = db.get_db()
        data.clear_unapproved_children(conn)
        child = data.parent_lookup(conn, token)
        if child is None:
            return render_template("parent.html", child=None, done=request.args.get("done")), 404
        if request.method == "POST":
            choice = request.form.get("choice")
            if choice == "approve" and request.form.get("agree") == "1":
                data.parent_approve(conn, token)
                clear_leaderboard_cache()
                return redirect(url_for("parent", token=token, done="approved"))
            if choice == "controls" and child["status"] == "given":
                try:
                    data.set_time_limit(conn, child["id"], request.form.get("time_limit"))
                    data.set_board_name(conn, child["id"], request.form.get("board_name"))
                except ValueError as e:
                    flash(first_upper(str(e)), "error")
                    return redirect(url_for("parent", token=token))
                clear_leaderboard_cache()
                return redirect(url_for("parent", token=token, done="saved"))
            if choice in ("decline", "withdraw"):
                name = data.parent_remove(conn, token)
                clear_leaderboard_cache()
                return render_template("parent.html", child=None, done="removed", name=name)
            flash("Tick the box to confirm, then tap Approve.", "error")
            return redirect(url_for("parent", token=token))
        kid = data.get_user(conn, child["id"])
        return render_template("parent.html", child=child, token=token, done=request.args.get("done"),
                               wait_days=config.PARENT_WAIT_DAYS, time_limit=kid["time_limit"] or 0,
                               config_break=config.BREAK_AFTER_MINUTES,
                               board_name=data.board_name_choice(kid), limits=data.TIME_LIMIT_CHOICES,
                               name_choices=data.BOARD_NAME_CHOICES,
                               used=data.screen_minutes_today(conn, child["id"]))

    @app.route("/signup/verify", methods=["GET", "POST"])
    def signup_verify():
        """Type the 6-digit code from the email; then the account is made and you're logged in."""
        if g.user:
            return redirect(url_for("dashboard"))
        if not config.SIGNUP_OPEN:          # closed: a half-finished sign-up can't finish either
            session.pop("signup_id", None)
            return redirect(url_for("signup"))
        conn, pending = db.get_db(), session.get("signup_id")
        email = data.pending_email(conn, pending) if pending else None
        if not email:
            session.pop("signup_id", None)
            flash("That sign-up has expired. Please start again.", "error")
            return redirect(url_for("signup"))
        if request.method == "POST":
            try:
                if request.form.get("action") == "resend":
                    to, code = data.resend_signup_code(conn, pending)
                    app.config["SEND_CODE"](to, code, "signup")
                    flash(f"New code sent to {to}.", "ok")
                else:
                    uid = data.finish_signup(conn, pending, request.form.get("verify_code"))
                    if (data.get_user(conn, uid) or {}).get("parent_status") == "pending":
                        session.clear()
                        sent_to = ask_parent(uid, force=True)
                        flash("Your account is made! It switches on when your parent or guardian approves it"
                              + (f": we emailed {sent_to}." if sent_to else ". We'll email them when you log in.")
                              + " Then log in with your full name and PIN.", "ok")
                        return redirect(url_for("login"))
                    session.clear()
                    session.permanent = True
                    session["user_id"] = uid
                    flash("Welcome to StrideBoard! Next time, log in with your full name and PIN.", "ok")
                    return redirect(url_for("dashboard"))
            except ValueError as e:
                flash(first_upper(str(e)), "error")
            return redirect(url_for("signup_verify"))
        return render_template("signup_verify.html", email=email)

    @app.route("/forgot", methods=["GET", "POST"])
    def forgot():
        """Forgot your PIN? Type the account's recovery email, get a code, choose a new PIN."""
        if g.user:
            return redirect(url_for("settings"))
        conn = db.get_db()
        if request.method == "POST":
            action = request.form.get("action")
            try:
                if action == "send":
                    if not mailer.ready():
                        raise ValueError("email isn't set up on this site yet. Ask an admin to reset your PIN")
                    if too_many_signups(request.remote_addr, "reset"):
                        raise ValueError("too many tries from here. Try again in an hour")
                    email = (request.form.get("email") or "").strip()
                    found = data.start_pin_reset(conn, app.config["SECRET_KEY"], email)
                    note_signup(request.remote_addr, "reset")
                    if found:
                        app.config["SEND_CODE"](found[1], found[2], "reset")
                    session["reset_id"] = found[0] if found else 0
                    session["reset_email"] = email
                elif action == "resend":
                    if session.get("reset_id"):
                        to, code = data.resend_email_code(conn, session["reset_id"], "reset")
                        app.config["SEND_CODE"](to, code, "reset")
                    flash("If an account uses that email, a new code is on its way.", "ok")
                elif action == "restart":
                    session.pop("reset_id", None)
                    session.pop("reset_email", None)
                elif action == "reset":
                    if not session.get("reset_id"):
                        raise ValueError("that code isn't right. Check you typed the email your account uses")
                    uid = data.finish_pin_reset(conn, session["reset_id"], request.form.get("verify_code"),
                                                request.form.get("pin"), request.form.get("pin_again"))
                    session.clear()
                    session.permanent = True
                    session["user_id"] = uid
                    flash("PIN changed. You're logged in.", "ok")
                    return redirect(url_for("dashboard"))
            except ValueError as e:
                flash(first_upper(str(e)), "error")
            return redirect(url_for("forgot"))
        return render_template("forgot.html", email=session.get("reset_email"),
                               step2="reset_id" in session, mail_ready=mailer.ready())

    @app.route("/notice/rename", methods=["POST"])
    def dismiss_rename():
        """The OK button on the 'your name was changed' box."""
        data.dismiss_rename_notice(db.get_db(), g.user["id"])
        return redirect(safe_back(request.form.get("back", "")) or url_for("dashboard"))

    @app.route("/logout", methods=["GET", "POST"])
    def logout():
        # Logging out is a form (POST, with the page's code), so a link on another site can't
        # log anyone out. After "Delete my account" the session is already empty.
        if g.user is not None and request.method != "POST":
            return redirect(url_for("settings"))
        session.clear()
        if request.args.get("deleted") == "1":   # after "Delete my account" (going via here clears the offline copy too)
            flash("Your account and everything in it has been deleted.", "ok")
        return redirect(url_for("login"))

    # ---------- Stage 1-3: dashboard
    @app.route("/")
    def dashboard():
        conn, uid, t = db.get_db(), g.user["id"], today()
        d = data.dashboard(conn, uid, t)
        week = this_week(data.history(conn, uid, 7, t), d["daily_goal"])
        # A small leaderboard preview: top 3 plus where you are
        view = g.user["role"] if g.user["role"] in ("student", "teacher") else "student"
        board = cached_leaderboard(conn, view, t)
        mine = next((r for r in board if r.get("user_id") == uid), None)
        preview = with_builds(conn, board[:3] + ([mine] if mine and mine["rank"] > 3 else []))
        return render_template("dashboard.html", d=d, week=week, preview=preview,
                               preview_view=view, my_rank=mine,
                               tier_progress=tier_progress(d["weekly_total"]),
                               badge_summary=badge_summary(all_badges(conn, uid, d["badges"])),
                               water_target=WATER_TARGET,
                               water_due=water_due(d["water_today"]),
                               app_update=android_app_update(),
                               reward=data.reward_status(conn, uid, t))

    @app.route("/reward", methods=["POST"])
    def claim_reward():
        """The Claim button on Home's tier card: today's login reward."""
        try:
            got = data.claim_daily_reward(db.get_db(), g.user["id"], today())
            if got.get("swapped"):
                flash(f"Day {got['day']} reward: you already had {got['label']}, so here's {got['exp']} EXP instead!", "badge")
            else:
                flash(f"Day {got['day']} reward: {got['label']}!" +
                      (" It's in your Avatar studio." if got["kind"] == "item" else ""), "badge")
        except ValueError as e:
            flash(first_upper(str(e)), "error")
        return redirect(url_for("dashboard", _anchor="tier-h"))

    # ---------- Logging steps, mood, water, activity
    @app.route("/log", methods=["GET", "POST"])
    def log():
        conn, uid = db.get_db(), g.user["id"]
        dates = days_back(7)
        if request.method == "POST":
            # The dashboard's water and mood buttons send "X-Requested-With: fetch"
            # and get a small JSON reply, so the page updates without reloading.
            quick = request.headers.get("X-Requested-With") == "fetch"
            try:
                save_log_form(conn, uid, dates)
            except ValueError as e:
                if quick:
                    return jsonify(ok=False, error=first_upper(str(e))), 400
                flash(first_upper(str(e)), "error")
            if quick:
                messages = get_flashed_messages()  # shown by the page itself, not on the next load
                d = data.dashboard(conn, uid, today())
                return jsonify(ok=True, water=d["water_today"] or 0, target=WATER_TARGET,
                               mood=d["mood_today"], message=messages[0] if messages else "")
            return redirect(url_for(safe_next("log")))
        d = data.dashboard(conn, uid, today())
        return render_template("log.html", dates=dates, d=d, water_target=WATER_TARGET,
                               mini=data.mini_state(conn, uid),
                               recent=data.history(conn, uid, 8, today()))

    # ---------- Leaderboards
    @app.route("/leaderboard")
    def leaderboard():
        # Students only see student boards and teachers only see teacher boards;
        # admins see everything.
        role = g.user["role"] if g.user["role"] in ("student", "teacher") else None
        if role:
            other = "teacher" if role == "student" else "student"
            group = "Classes" if role == "student" else "Departments"
            allowed = [(k, group if k == "department" else label)
                       for k, label in LEADERBOARD_VIEWS if k != other]
        else:
            allowed = LEADERBOARD_VIEWS
        views = dict(allowed)
        default = role or "student"
        view = request.args.get("view", default)
        if view not in views:
            view = default
        # Today / This week / This month / All time. Effort and improvement need a
        # goal or an earlier stretch to compare with, so they have no all-time board.
        periods = [p for p in LEADERBOARD_PERIODS
                   if not (p[0] == "all" and view in ("effort", "improvement"))]
        period = request.args.get("period", "week")
        if period not in dict(periods):
            period = "week"
        rows = cached_leaderboard(db.get_db(), view, today(), role=role, period=period)
        total = len(rows)
        # Search: matching names (or class/department) from the whole board, ranks unchanged
        q = (request.args.get("q") or "").strip()[:60]
        if q:
            rows = data.board_search(rows, q)
            with_builds(db.get_db(), rows)
            return render_template("leaderboard.html", rows=rows, mine=[], total=total, trimmed=False,
                                   show_all=True, view=view, views=allowed, view_name=views[view],
                                   period=period, periods=periods, q=q)
        # Big boards show the top 50 plus your own row; "Show everyone" opens the full list.
        # Ranks are worked out on the full board first, so they never change.
        show_all = request.args.get("all") == "1"
        mine = []
        if not show_all and total > LEADERBOARD_TOP:
            me_id, my_group = g.user["id"], g.user["department"]
            mine = [r for r in rows[LEADERBOARD_TOP:]
                    if r.get("user_id") == me_id or (r.get("user_id") is None and r["name"] == my_group)]
            rows = rows[:LEADERBOARD_TOP]
        with_builds(db.get_db(), rows + mine)
        return render_template("leaderboard.html", rows=rows, mine=mine, total=total,
                               trimmed=total > len(rows), show_all=show_all, view=view,
                               views=allowed, view_name=views[view], period=period, periods=periods, q="")

    # ---------- Stage 4: Weekly Wrap-Up
    @app.route("/insights")
    def insights():
        w = data.weekly_wrapup(db.get_db(), g.user["id"], today())
        chart = {
            "labels": [datetime.strptime(r["date"], "%Y-%m-%d").strftime("%a") for r in w["mood_vs_steps"]],
            "steps": [r.get("steps") or 0 for r in w["mood_vs_steps"]],
            "moods": [r.get("mood") for r in w["mood_vs_steps"]],
        }
        return render_template("insights.html", w=w, chart=chart,
                               tier_up=tier_rank(w["tier"]) - tier_rank(w["last_tier"]))

    # ---------- Challenges
    @app.route("/challenges", methods=["GET", "POST"])
    def challenges():
        """Mini challenges (earn EXP) on top, then the progression tracks they feed."""
        conn, uid = db.get_db(), g.user["id"]
        if request.method == "POST":
            try:
                handle_mini(conn, uid)
            except ValueError as e:
                flash(first_upper(str(e)), "error")
            return redirect(url_for("challenges") + "#mini")
        walk = data.check_walks(conn, uid)
        if walk:
            flash(f"{walk['label']}: done! +{walk['exp']} EXP. You have {walk['balance']:,} EXP.", "badge")
        tracks = data.progression(conn, uid)
        badges = all_badges(conn, uid, data.earned_badges(conn, uid), tracks)
        mini = data.mini_state(conn, uid)
        a, build = mini["active"], my_build()
        game = ""
        if a and a["track"] == "steps":
            game = mini_scene.walk_scene(build, a["label"], a["exp"], a["walked"], a["amount"])
        elif a:
            game = mini_scene.scene(build, a["track"], a["label"], a["exp"])
        won, finish = session.pop("mini_won", None), ""
        # A walk can finish while the page is closed (the phone syncs), so remember which finished
        # walk this browser has already celebrated, and show the finish line for a new one.
        last_walk = data.last_finished_walk(conn, uid)
        if last_walk and session.get("walk_seen") != last_walk["id"]:
            session["walk_seen"] = last_walk["id"]
            won = {"label": last_walk["label"], "exp": last_walk["exp"],
                   "balance": last_walk["balance"], "walk": True}
            finish = mini_scene.walk_finish(build, last_walk["amount"])
        return render_template("challenges.html", tracks=tracks, summary=badge_summary(badges),
                               mini=mini, game=game, won=won, finish=finish,
                               cheer=mini_scene.celebration(build) if won else "")

    # ---------- Badges: everything still to earn on top, earned at the bottom
    @app.route("/badges")
    def badges():
        conn, uid = db.get_db(), g.user["id"]
        items = all_badges(conn, uid, data.earned_badges(conn, uid))
        groups = []   # [(group name, [badges])] in display order
        for b in items:
            if not groups or groups[-1][0] != b["group"]:
                groups.append((b["group"], []))
            groups[-1][1].append(b)
        to_earn = [(name, [b for b in bs if not b["earned"]]) for name, bs in groups]
        earned = [(name, sorted([b for b in bs if b["earned"]], key=lambda b: b["earned_on"], reverse=True))
                  for name, bs in groups]
        return render_template("badges.html", to_earn=[g for g in to_earn if g[1]],
                               earned=[g for g in earned if g[1]], summary=badge_summary(items))

    # ---------- Settings: token, phone setup, age band, goal
    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        conn, uid = db.get_db(), g.user["id"]
        if request.method == "POST":
            action = request.form.get("action")
            try:
                if action == "my_details":
                    data.update_my_details(conn, uid, request.form.get("display_name"),
                                           request.form.get("department"))
                    clear_leaderboard_cache()
                    flash("Your details are saved.", "ok")
                elif action == "delete_me":
                    if request.form.get("confirm") != "1":
                        raise ValueError("tick the box to confirm you want to delete everything")
                    data.delete_my_account(conn, uid, request.form.get("pin"))
                    clear_leaderboard_cache()
                    session.clear()
                    return redirect(url_for("logout", deleted=1))
                elif action == "board_name":
                    data.set_board_name(conn, uid, request.form.get("board_name"))
                    clear_leaderboard_cache()
                    flash("Saved. The leaderboards show your name this way now.", "ok")
                elif action == "new_token":
                    data.regenerate_token(conn, uid)
                    flash("New token made. Update it in your phone's Shortcut or app.", "ok")
                elif action == "age_band":
                    band = request.form.get("age_band")
                    if band not in dict(AGE_BANDS):
                        raise ValueError("please choose an age band")
                    if band == "under_13" and g.user["age_band"] != "under_13" and g.user["role"] != "admin":
                        raise ValueError("under 13s need a parent's permission. Ask your teacher to change "
                                         "your age band for you")
                    data.set_age_band(conn, uid, band)
                    flash("Age band saved.", "ok")
                elif action == "goal":
                    data.set_custom_goal(conn, uid, to_int(request.form.get("goal"), "goal"))
                    flash("Daily goal saved. It will stay fixed until you change it.", "ok")
                elif action == "email_send":
                    if not mailer.ready():
                        raise ValueError("email isn't set up on this site yet")
                    if too_many_signups(request.remote_addr, "email"):
                        raise ValueError("too many emails from here. Try again in an hour")
                    cid, to, code = data.start_email_link(conn, app.config["SECRET_KEY"], uid,
                                                          request.form.get("email"))
                    app.config["SEND_CODE"](to, code, "link")
                    note_signup(request.remote_addr, "email")
                    session["email_link_id"] = cid
                    flash(f"Code sent to {to}.", "ok")
                elif action == "email_verify":
                    data.finish_email_link(conn, session.get("email_link_id"), uid,
                                           request.form.get("verify_code"))
                    session.pop("email_link_id", None)
                    flash("Recovery email saved. If you forget your PIN, you can reset it with this email.", "ok")
                elif action == "email_resend":
                    to, code = data.resend_email_code(conn, session.get("email_link_id"), "link")
                    app.config["SEND_CODE"](to, code, "link")
                    flash(f"New code sent to {to}.", "ok")
                elif action == "email_cancel":
                    session.pop("email_link_id", None)
                elif action == "email_remove":
                    data.remove_email(conn, uid)
                    flash("Recovery email removed.", "ok")
                elif action == "fast":
                    resp = redirect(url_for("settings", _anchor="appearance"))
                    resp.set_cookie(FAST_COOKIE, "1" if request.form.get("fast") == "1" else "0",
                                    max_age=60 * 60 * 24 * 365 * 2, samesite="Lax", httponly=True,
                                    secure=request.is_secure)
                    flash("Fast mode is on: effects off, everything shows straight away."
                          if request.form.get("fast") == "1" else "Fast mode is off.", "ok")
                    return resp
                elif action == "theme":
                    choice = request.form.get("theme")
                    if choice not in [k for k, _, _ in THEMES]:
                        raise ValueError("please choose Light, Dark or Automatic")
                    resp = redirect(url_for("settings", _anchor="appearance"))
                    resp.set_cookie(THEME_COOKIE, choice, max_age=60 * 60 * 24 * 365 * 2,
                                    samesite="Lax", httponly=True,
                                    secure=request.is_secure)
                    return resp
                elif action in ("avatar_buy", "avatar_wear"):
                    key = request.form.get("item", "")
                    name = config.SHOP_ITEMS.get(key, (None, "That item"))[1]
                    if action == "avatar_buy":
                        left = data.buy_avatar_item(conn, uid, key)
                        flash(f"Bought {name}! You have {left:,} EXP left.", "badge")
                    else:
                        data.wear_avatar_item(conn, uid, key)
                        flash(f"Now using {name}." if key in config.GLASS_GRADIENTS or key in config.MATERIAL_THEMES
                              else f"Now wearing {name}.", "ok")
            except ValueError as e:
                flash(first_upper(str(e)), "error")
            slot = request.form.get("slot")
            if action in ("avatar_buy", "avatar_wear") and slot in dict(config.AVATAR_SLOTS):
                return redirect(url_for("settings", slot=slot, _anchor="studio"))
            if action and action.startswith("email_"):
                return redirect(url_for("settings", _anchor="recovery"))
            if action in ("my_details", "delete_me", "board_name"):
                return redirect(url_for("settings", _anchor="your-data"))
            return redirect(url_for("settings"))
        slot = request.args.get("slot")
        if slot not in dict(config.AVATAR_SLOTS):
            slot = config.AVATAR_SLOTS[0][0]
        return render_template("settings.html", me=data.get_user(conn, uid), age_bands=AGE_BANDS,
                               classes=config.SIGNUP_CLASSES, departments=config.SIGNUP_DEPARTMENTS,
                               is_owner=g.user["username"] == config.OWNER_USERNAME,
                               shop=data.avatar_shop(conn, uid), slot=slot, slots=config.AVATAR_SLOTS,
                               name_choices=data.BOARD_NAME_CHOICES,
                               board_name=data.board_name_choice(g.user),
                               server_url=request.url_root.rstrip("/"),
                               email_linked=data.has_email(conn, uid), mail_ready=mailer.ready(),
                               shortcut_link=iphone_shortcut_link(conn),
                               email_pending=(data.email_code_info(conn, session["email_link_id"], "link")
                                              if session.get("email_link_id") else None))

    @app.route("/settings/my-data.json")
    def my_data():
        """Download my data: everything StrideBoard holds about me, as a JSON file."""
        body = json.dumps(data.export_my_data(db.get_db(), g.user["id"]), indent=2, ensure_ascii=False)
        stamp = today().isoformat() if hasattr(today(), "isoformat") else str(today())
        resp = current_app.response_class(body, mimetype="application/json")
        resp.headers["Content-Disposition"] = f'attachment; filename="strideboard-my-data-{stamp}.json"'
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/settings/my-steps.csv")
    def my_steps_csv():
        """Download my step history as a spreadsheet file (date, steps, where it came from)."""
        import csv
        rows = data.export_my_data(db.get_db(), g.user["id"])["steps"]
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["date", "steps", "source", "updated_at"])
        for r in rows:
            w.writerow([r["date"], r["steps"], r["source"], r["updated_at"]])
        resp = current_app.response_class(out.getvalue(), mimetype="text/csv")
        resp.headers["Content-Disposition"] = f'attachment; filename="strideboard-my-steps-{today()}.csv"'
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---------- Leaderboard screen (the Mac app, or any browser on a school TV)
    @app.route("/board")
    def board():
        """Students and Teachers boards side by side, for a big screen. Needs the screen code
        from Admin (?key=...), so pupils' names are never public. Refreshes itself every minute."""
        conn = db.get_db()
        if not data.board_key_ok(conn, request.args.get("key")):
            return render_template("board_locked.html", tried=bool(request.args.get("key"))), 403
        t = today()
        # Today / This week / This month / All time, and a name search across both boards
        period = request.args.get("period", "week")
        if period not in dict(LEADERBOARD_PERIODS):
            period = "week"
        q = (request.args.get("q") or "").strip()[:60]
        boards = []
        for view, title in (("student", "Students"), ("teacher", "Teachers")):
            rows = cached_leaderboard(conn, view, t, period=period)
            shown = rows
            if q:   # matching names (or classes/departments), ranks unchanged
                shown = data.board_search(rows, q)
            boards.append({"title": title, "rows": with_builds(conn, shown[:BOARD_ROWS]), "count": len(rows),
                           "matches": len(shown), "total": sum(r["value"] for r in rows)})
        start, end = data.period_bounds(period, t)[:2]
        return render_template("board.html", boards=boards, start=start, end=end, period=period,
                               periods=LEADERBOARD_PERIODS, q=q, now=datetime.now(TZ))

    # ---------- iPhone Shortcut file (signed on a Mac, so iPhones can add it in one tap)
    @app.route("/iphone-shortcut")
    def iphone_shortcut():
        if not os.path.isfile(SHORTCUT_FILE):
            abort(404)
        return send_file(SHORTCUT_FILE, mimetype="application/octet-stream", as_attachment=True,
                         download_name="Strideboard.shortcut", max_age=0)

    def iphone_shortcut_link(conn):
        """Our own signed file when it's there; otherwise the iCloud link from Admin/config."""
        if os.path.isfile(SHORTCUT_FILE):
            return url_for("iphone_shortcut")
        return data.ios_shortcut_link(conn)

    # ---------- Admin
    @app.route("/admin", methods=["GET", "POST"])
    def admin():
        admin_only()
        conn = db.get_db()
        result = None
        if request.method == "POST":
            _IMPACT_CACHE.clear()      # an Admin change: show fresh impact numbers next
            clear_leaderboard_cache()  # ...and fresh leaderboards (bans, renames, resets)
            action = request.form.get("action")
            try:
                if action in ("report_done", "report_dismiss"):
                    data.handle_report(conn, to_int(request.form.get("report_id"), "report"), g.user["id"],
                                       "done" if action == "report_done" else "dismissed")
                    flash("Report marked as handled." if action == "report_done" else "Report dismissed.", "ok")
                    return redirect(url_for("admin_reports"))
                elif action == "add_users":
                    result = data.bulk_create_users(conn, request.form.get("csv", ""))
                    flash(f"Added {result['created']} user(s).", "ok" if not result["errors"] else "error")
                elif action == "create_challenge":
                    kind = request.form.get("kind")
                    if kind not in ("department", "school_distance"):
                        raise ValueError("please choose a challenge type")
                    target = to_int(request.form.get("target_steps") or 0, "target steps")
                    data.create_challenge(conn, request.form.get("title", "").strip(),
                                          request.form.get("description", "").strip(), kind, target,
                                          request.form.get("start_date"), request.form.get("end_date"))
                    flash("Challenge created.", "ok")
                elif action == "shortcut_link":
                    saved = data.set_ios_shortcut_link(conn, request.form.get("link"))
                    flash("iPhone Shortcut link saved. Students now see a 'Get the iPhone Shortcut' button "
                          "in Settings." if saved else "iPhone Shortcut link removed.", "ok")
                elif action == "board_new":
                    if not is_owner(g.user):
                        abort(403)
                    data.board_key(conn, renew=True)
                    flash("New screen code made. Screens using the old code will ask for the new one.", "ok")
                elif action == "give_exp":
                    who = (request.form.get("username") or "").strip()
                    target = data.find_user_id(conn, who) if who else None
                    if target is None:
                        raise ValueError(f"no one has the username {who or '(blank)'}")
                    new = data.add_exp(conn, target, request.form.get("amount"),
                                       request.form.get("reason") or "Given by an admin")
                    flash(f"Gave EXP to {who}. Their balance is now {new:,}.", "ok")
                elif action == "mod_delete_selected":
                    if not is_owner(g.user):
                        abort(403)
                    gone = data.delete_people(conn, request.form.getlist("ids"), acting_id=g.user["id"])
                    flash(f"Deleted {len(gone)} account{'s' if len(gone) != 1 else ''} forever: {', '.join(gone)}.", "ok")
                elif action.startswith("mod_"):
                    if not is_owner(g.user):
                        abort(403)
                    who = (request.form.get("person") or "").strip()
                    target = data.find_person(conn, who)
                    if target is None:
                        raise ValueError(f"no one is called {who or '(blank)'}")
                    name = data.get_user(conn, target)["display_name"]
                    if action.startswith("mod_block_"):
                        length = action.removeprefix("mod_block_")
                        until = data.block_user(conn, target, length, request.form.get("reason"),
                                                acting_id=g.user["id"])
                        flash(f"{name} is banned." if until is None else
                              f"{name} is timed out until {datetime.fromisoformat(until):%a %d %b, %H:%M}.", "ok")
                    elif action == "mod_delete":
                        gone = data.delete_people(conn, [target], acting_id=g.user["id"])
                        flash(f"Deleted {gone[0]} forever.", "ok")
                    elif action == "mod_reset":
                        data.reset_person(conn, target)
                        flash(f"Reset {name}: same account and log-in, but all their steps, badges, "
                              "EXP and avatar are gone.", "ok")
                    elif action == "mod_unblock":
                        data.unblock_user(conn, target)
                        flash(f"{name} can use StrideBoard again.", "ok")
                    elif action == "mod_rename":
                        data.rename_person(conn, target, request.form.get("new_name"), acting_id=g.user["id"])
                        flash(f"Renamed {name} to {data.get_user(conn, target)['display_name']}.", "ok")
                    elif action == "mod_steps":
                        removed = data.remove_steps(conn, target, request.form.get("date"))
                        flash(f"Removed {removed:,} steps from {name} on {request.form.get('date')}.", "ok")
                    else:
                        raise ValueError("unknown moderation action")
                elif action == "set_role":
                    who = (request.form.get("username") or "").strip()
                    target = data.find_user_id(conn, who) if who else None
                    if target is None:
                        raise ValueError(f"no one has the username {who or '(blank)'}")
                    role = request.form.get("role")
                    was = data.set_role(conn, target, role, request.form.get("department"),
                                        acting_admin_id=g.user["id"])
                    flash(f"{who} is now {'an' if role == 'admin' else 'a'} {role} (was {was}).", "ok")
                elif action == "close_challenge":
                    data.close_challenge(conn, to_int(request.form.get("challenge_id"), "challenge"))
                    flash("Challenge closed.", "ok")
            except ValueError as e:
                flash(first_upper(str(e)), "error")
            if result is None:
                if request.form.get("back", "").startswith("people-"):
                    tab = request.form["back"].removeprefix("people-")
                    return redirect(url_for("admin", people=tab if tab in ("all", "student", "teacher", "admin", "blocked") else "all") + "#people")
                if request.form.get("back") == "people-blocked":
                    return redirect(url_for("admin", people="blocked") + "#people")
                return redirect(url_for("admin"))
        t = datetime.now(TZ).date()
        users = data.list_users(conn)
        people_role = request.args.get("people", "all")
        if people_role not in ("all", "student", "teacher", "admin", "blocked"):
            people_role = "all"
        people_q = " ".join(request.args.get("q", "").split())[:60]
        role_counts = {"all": len(users)}
        for r in ("student", "teacher", "admin"):
            role_counts[r] = sum(1 for u in users if u["role"] == r)
        role_counts["blocked"] = sum(1 for u in users if u["blocked"])
        needle = people_q.lower()
        shown = [u for u in users
                 if (people_role == "all" or u["role"] == people_role
                     or (people_role == "blocked" and u["blocked"]))
                 and (not needle or needle in f"{u['display_name']} {u['username']} {u['department'] or ''}".lower())]
        per_day = data.suggested_distance_target(conn, 1)
        return render_template("admin.html", report_count=len(data.open_reports(conn)), board_code=data.board_key(conn), app_downloads=BOARD_APP_DOWNLOADS,
                               users=users, shown=shown, people_role=people_role,
                               people_q=people_q, role_counts=role_counts,
                               challenges=data.active_challenges(conn, today()),
                               stats=cached_impact_stats(conn), result=result,
                               age_labels=dict(AGE_BANDS),
                               per_day=per_day, suggested=per_day * 7,   # same formula, one query
                               start=t.isoformat(), end=(t + timedelta(days=6)).isoformat(),
                               csv_text=request.form.get("csv", "") if result else "",
                               shortcut_link=data.ios_shortcut_link(conn),
                               owner=is_owner(g.user),
                               blocked=data.blocked_people(conn) if is_owner(g.user) else [],
                               last_backup=backup.latest(current_app.config["DATABASE"])
                               if is_owner(g.user) else None,
                               backup_script=os.path.abspath(backup.__file__))

    @app.route("/admin/reports")
    def admin_reports():
        """The Reports tab: open reports, with a type filter and name search (handled via /admin)."""
        admin_only()
        conn = db.get_db()
        return render_template("admin_reports.html", reports=data.open_reports(conn),
                               report_reasons=data.REPORT_REASONS, owner=is_owner(g.user))

    @app.route("/admin/backup")
    def admin_backup():
        """Owner only: download the whole database, compressed, to keep a copy safe."""
        if not is_owner(g.user):
            abort(403)
        blob = backup.snapshot(current_app.config["DATABASE"])
        return send_file(io.BytesIO(blob), mimetype="application/gzip", as_attachment=True,
                         download_name=backup.file_name(), max_age=0)

    # ---------- PWA plumbing
    @app.route("/sw.js")
    def service_worker():
        # Served from the root so it can work offline for the whole site.
        # The asset version is filled in here, so the offline cache always matches the
        # files the pages actually load (no need to edit sw.js by hand any more).
        with open(f"{app.static_folder}/sw.js", encoding="utf-8") as f:
            body = f.read().replace("__ASSET_VERSION__", ASSET_VERSION)
        resp = app.response_class(body, mimetype="application/javascript")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    @app.route("/offline")
    def offline():
        return render_template("offline.html")

    @app.route("/ping")
    def ping():
        """Called once a minute (only for people with a time limit) while the app is open."""
        left = g.get("screen_left")
        resp = jsonify(ok=True, left=left, over=left == 0 if left is not None else False)
        resp.headers["Cache-Control"] = "no-store"
        return resp


# ------------------------------------------------------------------ helpers

def save_log_form(conn, uid, dates):
    """Handle one of the small forms on /log or the dashboard (mood, water)."""
    action = request.form.get("action")
    day = request.form.get("date") or today()
    if day not in dates:
        raise ValueError("you can only log today or the last 7 days")
    # Steps are not typed in here: they come only from phones, through /api/steps.
    if action == "mood":
        mood = to_int(request.form.get("mood"), "mood")
        if mood not in dict(MOODS):
            raise ValueError("mood must be 1 to 5")
        data.save_mood(conn, uid, day, mood)
        flash(f"Mood saved: {dict(MOODS)[mood]}.", "ok")
    elif action == "water":
        current = data.dashboard(conn, uid, today())["water_today"] or 0
        change = 1 if request.form.get("change") == "plus" else -1
        data.save_water(conn, uid, today(), max(0, current + change))
    else:
        raise ValueError("unknown form")



def handle_mini(conn, uid):
    """Start, finish or back out of a mini challenge (forms on the Challenges page)."""
    action = request.form.get("action")
    if action == "mini_start":
        data.start_mini(conn, uid, request.form.get("key"))
    elif action == "mini_done":
        before = {t["key"]: t for t in data.progression(conn, uid)}
        won = data.finish_mini(conn, uid)
        after = {t["key"]: t for t in data.progression(conn, uid)}[won["track"]]
        old = before[won["track"]]
        flash(f"{won['label']}: done! +{won['exp']} EXP. You have {won['balance']:,} EXP.", "ok")
        if won["track"] in mini_scene.POSES:     # walks finish by themselves, without the show
            session["mini_won"] = {"label": won["label"], "exp": won["exp"], "balance": won["balance"]}
        new = [1 for lv, o in zip(after["levels"], old["levels"]) if lv["earned"] and not o["earned"]]
        new += [1 for lv, o in zip(after["record"]["levels"], old["record"]["levels"])
                if lv["earned"] and not o["earned"]]
        if new:
            flash(f"New badge{'s' if len(new) > 1 else ''} unlocked on the {after['name']} track!", "badge")
    elif action == "mini_quit":
        label = data.quit_mini(conn, uid)
        flash(f"Backed out of {label}. No worries, try another any time.", "ok")
    else:
        raise ValueError("unknown form")


def this_week(history_rows, goal):
    """Monday-to-Sunday bars for the dashboard, from data.history()."""
    by_date = {r["date"]: r for r in history_rows}
    t = datetime.now(TZ).date()
    monday = t - timedelta(days=t.weekday())
    week = []
    for i in range(7):
        day = monday + timedelta(days=i)
        row = by_date.get(day.isoformat())
        steps = row["steps"] if row else 0
        week.append({"label": day.strftime("%a"), "date": day.isoformat(),
                     "steps": steps, "future": day > t, "today": day == t,
                     "met": bool(row and row.get("goal_met")),
                     "percent": min(100, round(steps * 100 / goal)) if goal else 0,
                     "real_percent": round(steps * 100 / goal) if goal else 0})
    return week


def tier_rank(name):
    return [t for t, _ in TIERS].index(name) if name in dict(TIERS) else 0


def tier_progress(weekly_total):
    """How far through the current tier (0-100) for the progress bar."""
    floors = [f for _, f in TIERS]
    i = max(n for n, f in enumerate(floors) if weekly_total >= f)
    if i == len(floors) - 1:
        return 100
    return round((weekly_total - floors[i]) * 100 / (floors[i + 1] - floors[i]))


def fmt_amount(n, track, short=False):
    """12000 steps -> "12,000 steps" (short: "12K"); planks are seconds -> "1 h 30 min"."""
    n = int(n or 0)
    if track == "planks":
        h, rest = divmod(n, 3600)
        m, s = divmod(rest, 60)
        parts = ([f"{h} h"] if h else []) + ([f"{m} min"] if m else []) + ([f"{s} s"] if s or not n else [])
        return " ".join(parts)
    if short:
        for size, letter in ((1_000_000, "M"), (1_000, "K")):
            if n >= size:
                return f"{n / size:g}{letter}"
        return str(n)
    unit = config.TRACKS[track]["unit"]
    return f"{n:,} {unit}"


def all_badges(conn, uid, earned_general, tracks=None):
    """Every badge a person can earn, in display order.

    Each: {"group", "name", "icon", "tone", "earned", "earned_on", "hint"}.
    The 7 general badges come from steps; the rest come from the progression tracks.
    """
    got = {b["key"]: b["earned_on"] for b in earned_general}
    items = [{"group": "General", "name": v[0], "icon": v[1], "tone": v[2],
              "earned": k in got, "earned_on": got.get(k), "hint": v[3]} for k, v in BADGES.items()]
    for t in (tracks if tracks is not None else data.progression(conn, uid)):
        ic, tone = TRACK_LOOK[t["key"]]
        for lv in t["levels"]:
            items.append({"group": t["name"], "icon": ic, "tone": tone,
                          "name": f"{fmt_amount(lv['target'], t['key'], short=True)} {'total' if t['key'] == 'planks' else t['unit']}",
                          "earned": lv["earned"], "earned_on": lv["earned_on"],
                          "hint": f"{fmt_amount(lv['target'] - t['total'], t['key'])} to go"})
        for lv in t["record"]["levels"]:
            items.append({"group": t["name"], "icon": "trophy", "tone": tone,
                          "name": f"{t['record']['name']}: {fmt_amount(lv['target'], t['key'], short=True)}",
                          "earned": lv["earned"], "earned_on": lv["earned_on"],
                          "hint": RECORD_VERB[t["key"]].format(n=fmt_amount(lv["target"], t["key"], short=True)
                                                               if t["key"] == "planks" else f"{lv['target']:,}")})
    return items


def badge_summary(items):
    """Count and the newest few earned badges, for the small cards that link to /badges."""
    earned = sorted([b for b in items if b["earned"]], key=lambda b: b["earned_on"], reverse=True)
    return {"earned": len(earned), "total": len(items), "recent": earned[:4]}


def water_due(glasses):
    """True if behind a steady pace of WATER_TARGET glasses between 7:00 and 21:00."""
    now = datetime.now(TZ)
    hours = min(max(now.hour + now.minute / 60 - 7, 0), 14)
    return (glasses or 0) < round(WATER_TARGET * hours / 14)


# PythonAnywhere's WSGI file does "from app import app as application",
# and "flask --app app run" finds it too.
app = create_app()
