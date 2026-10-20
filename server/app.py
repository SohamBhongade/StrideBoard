"""StrideBoard website (Agent 3).

The pages people see. All data comes from data.py (Agent 1); this file never
writes SQL. Run from the server folder with:  flask run
"""
import gzip
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import (Flask, abort, flash, g, get_flashed_messages, jsonify, redirect,
                   render_template, request, session, url_for)

import api
import avatar_art
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

# How each progression track looks: icon and colour (the levels live in config.TRACKS).
TRACK_LOOK = {"steps": ("foot", "blue"), "pushups": ("pushup", "pink"), "squats": ("squat", "peach"),
              "planks": ("plank", "mint"), "jumping_jacks": ("jump", "violet")}
EXERCISE_CHOICES = [("pushups", "Push-ups"), ("squats", "Squats"), ("planks", "Plank (seconds)"),
                    ("jumping_jacks", "Jumping jacks")]
RECORD_VERB = {"steps": "Walk {n} steps in one day", "pushups": "Do {n} push-ups in one go",
               "squats": "Do {n} squats in one go", "planks": "Hold a plank for {n}",
               "jumping_jacks": "Do {n} jumping jacks in one go"}

WATER_TARGET = 8  # glasses a day: placeholder suggestion, team to verify like the step goals
# Bump this whenever style.css, app.js or the font change, so phones load the new
# files instead of their saved copy (the service worker picks it up automatically).
ASSET_VERSION = "13"

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
    add_speed(app)
    add_template_helpers(app)
    add_security(app)
    add_routes(app)
    return app


# -------------------------------------------------------------------- speed

COMPRESSIBLE = ("text/", "application/javascript", "application/json", "image/svg+xml",
                "application/manifest+json")


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
                "creature": avatar_art.render, "my_build": my_build(),
                "try_on": lambda build, slot, key: {**build, slot: key},
                "AVATARS": config.AVATARS, "AVATAR_COLORS": config.AVATAR_COLORS}


def my_build():
    """The logged-in person's avatar parts, for the top bar (None when logged out)."""
    if not g.get("user") or request.blueprint == api.bp.name:
        return None
    if "my_build" not in g:
        g.my_build = data.avatar_build(db.get_db(), g.user["id"])
    return g.my_build


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
                               activity_types=ACTIVITY_TYPES, exercise_choices=EXERCISE_CHOICES,
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
        rows = with_builds(db.get_db(), data.leaderboard(db.get_db(), view, today(), role=role))
        return render_template("leaderboard.html", rows=rows, view=view,
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
    @app.route("/challenges")
    def challenges():
        """Progression tracks: lifetime totals unlock levels, best-in-one-go unlocks records."""
        conn, uid = db.get_db(), g.user["id"]
        badges = all_badges(conn, uid, data.dashboard(conn, uid, today())["badges"])
        return render_template("challenges.html", tracks=data.progression(conn, uid),
                               summary=badge_summary(badges))

    # ---------- Badges: everything still to earn on top, earned at the bottom
    @app.route("/badges")
    def badges():
        conn, uid = db.get_db(), g.user["id"]
        items = all_badges(conn, uid, data.dashboard(conn, uid, today())["badges"])
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
                elif action in ("avatar_buy", "avatar_wear"):
                    key = request.form.get("item", "")
                    name = config.AVATAR_ITEMS.get(key, (None, "That item"))[1]
                    if action == "avatar_buy":
                        left = data.buy_avatar_item(conn, uid, key)
                        flash(f"Bought {name}! You have {left:,} EXP left.", "badge")
                    else:
                        data.wear_avatar_item(conn, uid, key)
                        flash(f"Now wearing {name}.", "ok")
            except ValueError as e:
                flash(first_upper(str(e)), "error")
            slot = request.form.get("slot")
            if action in ("avatar_buy", "avatar_wear") and slot in dict(config.AVATAR_SLOTS):
                return redirect(url_for("settings", slot=slot, _anchor="studio"))
            return redirect(url_for("settings"))
        slot = request.args.get("slot")
        if slot not in dict(config.AVATAR_SLOTS):
            slot = config.AVATAR_SLOTS[0][0]
        return render_template("settings.html", me=data.get_user(conn, uid), age_bands=AGE_BANDS,
                               shop=data.avatar_shop(conn, uid), slot=slot, slots=config.AVATAR_SLOTS,
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
                elif action == "give_exp":
                    who = (request.form.get("username") or "").strip()
                    target = data.find_user_id(conn, who) if who else None
                    if target is None:
                        raise ValueError(f"no one has the username {who or '(blank)'}")
                    new = data.add_exp(conn, target, request.form.get("amount"),
                                       request.form.get("reason") or "Given by an admin")
                    flash(f"Gave EXP to {who}. Their balance is now {new:,}.", "ok")
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
    """Handle one of the small forms on /log or the dashboard (mood, water, activity)."""
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
    elif action == "exercise":
        kind = request.form.get("type")
        if kind not in dict(EXERCISE_CHOICES):
            raise ValueError("please choose an exercise")
        before = {t["key"]: t for t in data.progression(conn, uid)}[kind]
        data.save_exercise(conn, uid, day, kind, request.form.get("amount"))
        after = {t["key"]: t for t in data.progression(conn, uid)}[kind]
        amount = to_int(request.form.get("amount"), "amount")
        flash(f"Saved {fmt_amount(amount, kind)}. Total: {fmt_amount(after['total'], kind)}.", "ok")
        new = [lv for lv, old in zip(after["levels"], before["levels"]) if lv["earned"] and not old["earned"]]
        new += [lv for lv, old in zip(after["record"]["levels"], before["record"]["levels"])
                if lv["earned"] and not old["earned"]]
        if new:
            flash(f"New badge{'s' if len(new) > 1 else ''} unlocked! See them on the Challenges page.", "badge")
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


def all_badges(conn, uid, earned_general):
    """Every badge a person can earn, in display order.

    Each: {"group", "name", "icon", "tone", "earned", "earned_on", "hint"}.
    The 7 general badges come from steps; the rest come from the progression tracks.
    """
    got = {b["key"]: b["earned_on"] for b in earned_general}
    items = [{"group": "General", "name": v[0], "icon": v[1], "tone": v[2],
              "earned": k in got, "earned_on": got.get(k), "hint": v[3]} for k, v in BADGES.items()]
    for t in data.progression(conn, uid):
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
