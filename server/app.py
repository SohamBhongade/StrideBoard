"""StrideBoard website (Agent 3).

The pages people see. All data comes from data.py (Agent 1); this file never
writes SQL. Run from the server folder with:  flask run
"""
import gzip
import os
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import (Flask, abort, current_app, send_file, flash, g, get_flashed_messages, jsonify, redirect,
                   render_template, request, session, url_for)

import api
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
RECORD_VERB = {"steps": "Walk {n} steps in one day", "pushups": "Do {n} push-ups in one go",
               "squats": "Do {n} squats in one go", "planks": "Hold a plank for {n}",
               "jumping_jacks": "Do {n} jumping jacks in one go"}

WATER_TARGET = 8  # glasses a day: placeholder suggestion, team to verify like the step goals
# Bump this whenever style.css, app.js or the font change, so phones load the new
# files instead of their saved copy (the service worker picks it up automatically).
ASSET_VERSION = "38"

PUBLIC_ENDPOINTS = {"login", "signup", "signup_verify", "forgot", "logout", "static", "offline", "service_worker",
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


def create_app():
    app = Flask(__name__)
    # No SECRET_KEY here: db.init_app() sets it from the server's environment.
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
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


def add_speed(app):
    """Make pages load faster on phones and school Wi-Fi.

    - Files whose address carries ?v=<ASSET_VERSION> (CSS, JS, the font) never change,
      so phones may keep them for a year; a new version gets a new address.
    - Other static files (icons, manifest) are kept for a day.
    - Text responses are gzip-compressed: pages shrink to about a fifth.
    """
    @app.after_request
    def cache_and_compress(resp):
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
                "today_label": f"{now:%A} {now.day} {now:%B}",
                "BADGES": BADGES, "MOODS": MOODS, "stand_due": stand_due(),
                "INACTIVE_MINUTES": config.INACTIVE_MINUTES, "INACTIVE_MAX_STEPS": config.INACTIVE_MAX_STEPS,
                "ASSET_VERSION": ASSET_VERSION, "TRACK_LOOK": TRACK_LOOK,
                "creature": creature, "avatar_sheet": avatar_sheet, "my_build": my_build(),
                "theme": current_theme(), "THEMES": THEMES,
                "try_on": lambda build, slot, key: {**build, slot: key},
                "my_glass": my_glass(), "GLASS_GRADIENTS": config.GLASS_GRADIENTS,
                "glass_bg": glass_bg, "android": is_android(), "my_material": my_material,
                "MATERIAL_THEMES": config.MATERIAL_THEMES, "material_swatch": material.swatch,
                "AVATARS": config.AVATARS, "AVATAR_COLORS": config.AVATAR_COLORS}


# Appearance: remembered per phone/computer in a cookie, so the login page follows it too.
THEMES = [("light", "Light", "sun"), ("dark", "Dark", "moon"), ("auto", "Automatic", "phone")]
THEME_COOKIE = "theme"


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
    """Android phones and tablets get the Material You look (Apple devices get glass)."""
    return "Android" in request.headers.get("User-Agent", "")


def my_material():
    """CSS for the logged-in person's Material You colours, light and dark."""
    key = config.MATERIAL_DEFAULT
    if g.get("user") and request.blueprint != api.bp.name:
        key = data.material_choice(db.get_db(), g.user["id"])
    seed = config.MATERIAL_THEMES[key][2]
    return {"light": material.css_vars(seed), "dark": material.css_vars(seed, dark=True)}


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


def note_failed_login(name):
    _prune(FAILED_LOGINS, LOGIN_LOCK_MINUTES * 60)
    FAILED_LOGINS.setdefault(_login_key(name), []).append(datetime.now().timestamp())


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
                note_failed_login(username)
            block = data.block_status(db.get_db(), user["id"]) if user else None
            if block:
                flash(block_message(block), "blocked")
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
        open_now = mailer.ready()
        if request.method == "POST" and open_now:
            try:
                if config.JOIN_CODE and form.get("code", "").strip().lower() != config.JOIN_CODE.lower():
                    raise ValueError("that school code isn't right. Ask your teacher for it")
                if too_many_signups(request.remote_addr):
                    raise ValueError("too many sign-ups from here. Try again in an hour")
                dept = form.get("class") if form.get("role") == "student" else form.get("department")
                pending, email, code = data.start_signup(
                    db.get_db(), app.config["SECRET_KEY"], form.get("email"),
                    form.get("display_name"), form.get("role"), dept,
                    form.get("age_band"), form.get("pin"), form.get("pin_again"))
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

    @app.route("/signup/verify", methods=["GET", "POST"])
    def signup_verify():
        """Type the 6-digit code from the email; then the account is made and you're logged in."""
        if g.user:
            return redirect(url_for("dashboard"))
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
        back = request.form.get("back", "")
        return redirect(back if back.startswith("/") and not back.startswith("//") else url_for("dashboard"))

    @app.route("/logout", methods=["GET", "POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ---------- Stage 1-3: dashboard
    @app.route("/")
    def dashboard():
        conn, uid, t = db.get_db(), g.user["id"], today()
        d = data.dashboard(conn, uid, t)
        week = this_week(data.history(conn, uid, 7, t), d["daily_goal"])
        # A small leaderboard preview: top 3 plus where you are
        view = g.user["role"] if g.user["role"] in ("student", "teacher") else "student"
        board = data.leaderboard(conn, view, t)
        mine = next((r for r in board if r.get("user_id") == uid), None)
        preview = with_builds(conn, board[:3] + ([mine] if mine and mine["rank"] > 3 else []))
        return render_template("dashboard.html", d=d, week=week, preview=preview,
                               preview_view=view, my_rank=mine,
                               tier_progress=tier_progress(d["weekly_total"]),
                               badge_summary=badge_summary(all_badges(conn, uid, d["badges"])),
                               water_target=WATER_TARGET,
                               water_due=water_due(d["water_today"]))

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
        rows = data.leaderboard(db.get_db(), view, today(), role=role)
        # Big boards show the top 50 plus your own row; "Show everyone" opens the full list.
        # Ranks are worked out on the full board first, so they never change.
        show_all = request.args.get("all") == "1"
        total = len(rows)
        mine = []
        if not show_all and total > LEADERBOARD_TOP:
            me_id, my_group = g.user["id"], g.user["department"]
            mine = [r for r in rows[LEADERBOARD_TOP:]
                    if r.get("user_id") == me_id or (r.get("user_id") is None and r["name"] == my_group)]
            rows = rows[:LEADERBOARD_TOP]
        with_builds(db.get_db(), rows + mine)
        return render_template("leaderboard.html", rows=rows, mine=mine, total=total,
                               trimmed=total > len(rows), show_all=show_all, view=view,
                               views=allowed, view_name=views[view])

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
                if action == "new_token":
                    data.regenerate_token(conn, uid)
                    flash("New token made. Update it in your phone's Shortcut or app.", "ok")
                elif action == "age_band":
                    band = request.form.get("age_band")
                    if band not in dict(AGE_BANDS):
                        raise ValueError("please choose an age band")
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
            return redirect(url_for("settings"))
        slot = request.args.get("slot")
        if slot not in dict(config.AVATAR_SLOTS):
            slot = config.AVATAR_SLOTS[0][0]
        return render_template("settings.html", me=data.get_user(conn, uid), age_bands=AGE_BANDS,
                               shop=data.avatar_shop(conn, uid), slot=slot, slots=config.AVATAR_SLOTS,
                               server_url=request.url_root.rstrip("/"),
                               email_linked=data.has_email(conn, uid), mail_ready=mailer.ready(),
                               shortcut_link=iphone_shortcut_link(conn),
                               email_pending=(data.email_code_info(conn, session["email_link_id"], "link")
                                              if session.get("email_link_id") else None))

    # ---------- Leaderboard screen (the Mac app, or any browser on a school TV)
    @app.route("/board")
    def board():
        """Students and Teachers boards side by side, for a big screen. Needs the screen code
        from Admin (?key=...), so pupils' names are never public. Refreshes itself every minute."""
        conn = db.get_db()
        if not data.board_key_ok(conn, request.args.get("key")):
            return render_template("board_locked.html", tried=bool(request.args.get("key"))), 403
        t = today()
        boards = []
        for view, title in (("student", "Students"), ("teacher", "Teachers")):
            rows = data.leaderboard(conn, view, t)
            boards.append({"title": title, "rows": with_builds(conn, rows[:BOARD_ROWS]), "count": len(rows),
                           "total": sum(r["value"] for r in rows)})
        monday = db.local_today() - timedelta(days=db.local_today().weekday())
        return render_template("board.html", boards=boards, monday=monday, sunday=monday + timedelta(days=6),
                               now=datetime.now(TZ))

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
            action = request.form.get("action")
            try:
                if action == "add_users":
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
        return render_template("admin.html", board_code=data.board_key(conn), app_downloads=BOARD_APP_DOWNLOADS,
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
                               blocked=data.blocked_people(conn) if is_owner(g.user) else [])

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
