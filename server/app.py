"""StrideBoard website (Agent 3).

The pages people see. All data comes from data.py (Agent 1); this file never
writes SQL. Run from the server folder with:  flask run
"""
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import (Flask, abort, flash, g, get_flashed_messages, jsonify, redirect,
                   render_template, request, send_from_directory, session, url_for)

import api
import config
import data
import db

TZ = ZoneInfo("Asia/Dubai")

# Display settings. The game rules themselves live in data.py / calc.py.
TIERS = list(config.TIERS)  # from Agent 1's config.py, so the rules live in one place
LEADERBOARD_VIEWS = [("student", "Students"), ("teacher", "Teachers"),
                     ("department", "Classes & departments"), ("effort", "Effort"),
                     ("improvement", "Most improved")]
AGE_BANDS = [("under_13", "Under 13"), ("teen_13_17", "13 to 17"),
             ("adult_18_39", "18 to 39"), ("adult_40_59", "40 to 59"),
             ("senior_60_plus", "60 and over")]
ACTIVITY_TYPES = [("walk", "Walk"), ("gym", "Gym"), ("sport", "Sport"),
                  ("yoga", "Yoga"), ("stretch", "Stretch"), ("other", "Other")]
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

WATER_TARGET = 8  # glasses a day: placeholder suggestion, team to verify like the step goals
STAND_MINUTES = 45  # in-site "time to stand up" reminder interval
# Bump this (and VERSION in static/sw.js) whenever style.css or app.js change,
# so phones load the new files instead of an old cached copy.
ASSET_VERSION = "4"

PUBLIC_ENDPOINTS = {"login", "logout", "static", "offline", "service_worker"}


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
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

    db.init_app(app)
    app.register_blueprint(api.bp)
    add_template_helpers(app)
    add_security(app)
    add_routes(app)
    return app


# ---------------------------------------------------------------- templates

def add_template_helpers(app):
    @app.template_filter("num")
    def num(n):
        """8423 -> "8,423"."""
        try:
            return f"{int(n):,}"
        except (TypeError, ValueError):
            return "0"

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
                "BADGES": BADGES, "MOODS": MOODS, "STAND_MINUTES": STAND_MINUTES,
                "ASSET_VERSION": ASSET_VERSION,
                "AVATARS": config.AVATARS, "AVATAR_COLORS": config.AVATAR_COLORS}


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
            user = data.authenticate(db.get_db(), username, pin) if username and pin else None
            if user:
                session.clear()
                session.permanent = True  # stay signed in on phones
                session["user_id"] = user["id"]
                return redirect(url_for("dashboard"))
            flash("That username and PIN don't match. Check them and try again.", "error")
        return render_template("login.html", username=username)

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
        preview = board[:3] + ([mine] if mine and mine["rank"] > 3 else [])
        return render_template("dashboard.html", d=d, week=week, preview=preview,
                               preview_view=view, my_rank=mine,
                               tier_progress=tier_progress(d["weekly_total"]),
                               badge_cards=badge_cards(d["badges"]),
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
                               activity_types=ACTIVITY_TYPES,
                               recent=data.history(conn, uid, 8, today()))

    # ---------- Leaderboards
    @app.route("/leaderboard")
    def leaderboard():
        views = dict(LEADERBOARD_VIEWS)
        default = g.user["role"] if g.user["role"] in views else "student"
        view = request.args.get("view", default)
        if view not in views:
            view = default
        rows = data.leaderboard(db.get_db(), view, today())
        return render_template("leaderboard.html", rows=rows, view=view,
                               views=LEADERBOARD_VIEWS, view_name=views[view])

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
    @app.route("/challenges")
    def challenges():
        items = data.active_challenges(db.get_db(), today())
        t = datetime.now(TZ).date()
        for c in items:  # add "days left" for display
            end = datetime.strptime(c["end_date"], "%Y-%m-%d").date()
            c["days_left"] = (end - t).days
        return render_template("challenges.html", challenges=items)

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
                elif action == "avatar":
                    data.set_avatar(conn, uid, request.form.get("avatar"),
                                    request.form.get("avatar_color"))
                    flash("Avatar saved. It shows next to your name on the leaderboards.", "ok")
            except ValueError as e:
                flash(first_upper(str(e)), "error")
            return redirect(url_for("settings"))
        return render_template("settings.html", me=data.get_user(conn, uid), age_bands=AGE_BANDS,
                               avatar_options=data.avatar_options(conn, uid),
                               server_url=request.url_root.rstrip("/"))

    # ---------- Admin
    @app.route("/admin", methods=["GET", "POST"])
    def admin():
        admin_only()
        conn = db.get_db()
        result = None
        if request.method == "POST":
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
                elif action == "close_challenge":
                    data.close_challenge(conn, to_int(request.form.get("challenge_id"), "challenge"))
                    flash("Challenge closed.", "ok")
            except ValueError as e:
                flash(first_upper(str(e)), "error")
            if result is None:
                return redirect(url_for("admin"))
        t = datetime.now(TZ).date()
        return render_template("admin.html", users=data.list_users(conn),
                               challenges=data.active_challenges(conn, today()),
                               stats=data.impact_stats(conn), result=result,
                               age_labels=dict(AGE_BANDS),
                               per_day=data.suggested_distance_target(conn, 1),
                               suggested=data.suggested_distance_target(conn, 7),
                               start=t.isoformat(), end=(t + timedelta(days=6)).isoformat(),
                               csv_text=request.form.get("csv", "") if result else "")

    # ---------- PWA plumbing
    @app.route("/sw.js")
    def service_worker():
        # Served from the root so it can work offline for the whole site.
        resp = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    @app.route("/offline")
    def offline():
        return render_template("offline.html")


# ------------------------------------------------------------------ helpers

def save_log_form(conn, uid, dates):
    """Handle one of the small forms on /log or the dashboard."""
    action = request.form.get("action")
    day = request.form.get("date") or today()
    if day not in dates:
        raise ValueError("you can only log today or the last 7 days")
    if action == "steps":
        steps = to_int(request.form.get("steps"), "steps")
        if not 0 <= steps <= 100000:
            raise ValueError("steps must be between 0 and 100,000")
        r = data.save_steps(conn, uid, day, steps, "manual")
        flash(f"Saved {steps:,} steps. This week: {r['weekly_total']:,} ({r['tier']}).", "ok")
        for key in r.get("new_badges", []):
            flash(f"New badge: {BADGES.get(key, (key,))[0]}!", "badge")
    elif action == "mood":
        mood = to_int(request.form.get("mood"), "mood")
        if mood not in dict(MOODS):
            raise ValueError("mood must be 1 to 5")
        data.save_mood(conn, uid, day, mood)
        flash(f"Mood saved: {dict(MOODS)[mood]}.", "ok")
    elif action == "water":
        current = data.dashboard(conn, uid, today())["water_today"] or 0
        change = 1 if request.form.get("change") == "plus" else -1
        data.save_water(conn, uid, today(), max(0, current + change))
    elif action == "activity":
        kind = request.form.get("type")
        if kind not in dict(ACTIVITY_TYPES):
            raise ValueError("please choose an activity type")
        minutes = to_int(request.form.get("minutes"), "minutes")
        if not 1 <= minutes <= 600:
            raise ValueError("minutes must be between 1 and 600")
        data.add_activity(conn, uid, day, kind, minutes)
        flash(f"Saved {minutes} minutes of {dict(ACTIVITY_TYPES)[kind].lower()}.", "ok")
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


def badge_cards(earned_list):
    """Up to 4 badges for the dashboard: newest earned first, then ones to aim for."""
    earned = sorted(earned_list, key=lambda b: b["earned_on"], reverse=True)
    keys = {b["key"] for b in earned}
    cards = [{"key": b["key"], "name": b["name"], "earned_on": b["earned_on"], "earned": True}
             for b in earned]
    cards += [{"key": k, "name": v[0], "how": v[3], "earned": False}
              for k, v in BADGES.items() if k not in keys]
    return cards[:4]


def water_due(glasses):
    """True if behind a steady pace of WATER_TARGET glasses between 7:00 and 21:00."""
    now = datetime.now(TZ)
    hours = min(max(now.hour + now.minute / 60 - 7, 0), 14)
    return (glasses or 0) < round(WATER_TARGET * hours / 14)


# PythonAnywhere's WSGI file does "from app import app as application",
# and "flask --app app run" finds it too.
app = create_app()
