"""StrideBoard settings.

Every number the game uses lives here, so the team can change a rule in one place.
Secrets and the database location come from environment variables, with safe
defaults for development on a laptop.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- Server settings (set these as environment variables on the real server) ---
# STRIDEBOARD_SECRET_KEY: a long random string. The default is for laptops only.
SECRET_KEY = os.environ.get("STRIDEBOARD_SECRET_KEY", "dev-only-not-secret-change-me")
# STRIDEBOARD_DATABASE: full path to the SQLite file.
DATABASE = os.environ.get(
    "STRIDEBOARD_DATABASE", str(BASE_DIR / "instance" / "strideboard.sqlite3")
)

# STRIDEBOARD_JOIN_CODE: optional. If set, people need this code to make their own
# account on the sign-up page (stops strangers joining). Leave unset for no code.
JOIN_CODE = os.environ.get("STRIDEBOARD_JOIN_CODE", "").strip()
# Sign-up is switched OFF (school data protection rules, October 2026). Everything for it is
# kept: to open it again later, add STRIDEBOARD_SIGNUP_OPEN=1 to the server (WSGI file) and
# reload. Existing accounts still log in either way; admins can still add people.
SIGNUP_OPEN = os.environ.get("STRIDEBOARD_SIGNUP_OPEN", "").strip() == "1"
# Logged out after this many days without opening StrideBoard (phones' step syncing, which
# uses the phone token, carries on regardless).
SESSION_IDLE_DAYS = 30
# Privacy policy and terms (/privacy): who runs it and who to contact. Set these on the server.
SCHOOL_NAME = os.environ.get("STRIDEBOARD_SCHOOL_NAME", "").strip() or "our school"
PRIVACY_CONTACT = os.environ.get("STRIDEBOARD_PRIVACY_CONTACT", "").strip() or "a StrideBoard admin at school"
TEAM_NAMES = os.environ.get("STRIDEBOARD_TEAM_NAMES", "").strip() or "the StrideBoard student team"
PRIVACY_UPDATED = "27 October 2026"   # change when the policy changes
# The one account that can time out, ban, rename and remove steps (Admin > Moderation).
# STRIDEBOARD_OWNER can change it on the server without editing code.
# STRIDEBOARD_MOVED_TO: set ONLY on an old copy of the site after moving it, e.g.
# "https://strideboard.pythonanywhere.com". Pages then redirect there and phones are told.
MOVED_TO = os.environ.get("STRIDEBOARD_MOVED_TO", "").strip()
OWNER_USERNAME = os.environ.get("STRIDEBOARD_OWNER", "soham.admin").strip().lower()
SIGNUP_ROLES = ("student", "teacher")   # admin is never offered on the sign-up page
# The choices on the sign-up page. Add a class or department by adding it to the list.
SIGNUP_CLASSES = (
    [f"Grade 9{c}" for c in "ABCD"] + [f"Grade 10{c}" for c in "ABCD"]
    + [f"Grade 11{c}" for c in "ABC"] + [f"Grade 12{c}" for c in "ABC"]
)
SIGNUP_DEPARTMENTS = ["English", "Science", "Social Science", "Maths", "Computer Science", "PE"]
# The iPhone Shortcut students install (Settings > Get the iPhone Shortcut).
# An admin can replace it on the Admin page without changing code.
IOS_SHORTCUT_URL = "https://www.icloud.com/shortcuts/05df17c346754e76940780a7fa048043"
SIGNUPS_PER_HOUR = 10                   # per network address, to stop spam accounts
# Email check for sign-ups: a 6-digit code is sent from a Gmail account.
# STRIDEBOARD_GMAIL_USER / STRIDEBOARD_GMAIL_APP_PASSWORD: that account and its app password.
# Without them, sign-up is closed (admins can still add people).
GMAIL_USER = os.environ.get("STRIDEBOARD_GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.environ.get("STRIDEBOARD_GMAIL_APP_PASSWORD", "").replace(" ", "")
# STRIDEBOARD_EMAIL_DOMAINS: optional, e.g. "gmail.com,school.ae" to only allow those.
EMAIL_DOMAINS = tuple(d.strip().lower().lstrip("@") for d in
                      os.environ.get("STRIDEBOARD_EMAIL_DOMAINS", "").split(",") if d.strip())
CODE_MINUTES = 15          # a code works for this long
CODE_TRIES = 5             # wrong guesses before the code stops working
CODE_RESEND_SECONDS = 60   # wait this long before sending another code
CODE_MAX_SENDS = 5         # codes per sign-up attempt

TIMEZONE = "Asia/Dubai"          # all dates and weeks use Dubai time (UTC+4)
MAX_UPLOAD_BYTES = 16 * 1024     # /api/steps rejects bodies larger than 16 KB

# --- Allowed values ---
ROLES = ("student", "teacher", "admin")
SOURCES = ("manual", "ios_shortcut", "android_app", "other")
ACTIVITY_TYPES = ("walk", "gym", "sport", "yoga", "stretch", "other")
AGE_BANDS = ("under_13", "teen_13_17", "adult_18_39", "adult_40_59", "senior_60_plus")

# --- Limits on what people can enter ---
MAX_DAILY_STEPS = 100_000
MAX_DAYS_BACK = 7                # steps/mood/water can be entered for up to 7 days ago
PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 6
MOOD_MIN, MOOD_MAX = 1, 5
WATER_MAX_GLASSES = 20
ACTIVITY_MAX_MINUTES = 600
CUSTOM_GOAL_MIN, CUSTOM_GOAL_MAX = 1_000, 30_000

# --- Tiers by weekly steps: (name, lowest weekly total for that tier) ---
TIERS = [
    ("Bronze", 0),
    ("Silver", 35_000),
    ("Gold", 60_000),
    ("Platinum", 90_000),
]

# --- Starting daily goal: the same for everyone ---
# 6,000 is an easy start; after two weeks each person's goal adapts to their own steps.
START_GOAL = 6_000   # everyone starts here; the adaptive goal takes over after two weeks
AGE_BAND_GOALS = {band: START_GOAL for band in
                  ("under_13", "teen_13_17", "adult_18_39", "adult_40_59", "senior_60_plus")}

# --- Adaptive goal: 14-day average x 1.10, rounded to 250, kept in 3,000-15,000 ---
ADAPTIVE_MIN_DAYS = 14
ADAPTIVE_FACTOR = 1.10
ADAPTIVE_ROUND_TO = 250
ADAPTIVE_GOAL_MIN = 3_000
ADAPTIVE_GOAL_MAX = 15_000

# --- Badges: key -> name shown on the website (order = display order) ---
BADGES = {
    "first_log": "First Steps",
    "ten_k": "10K Club",
    "streak_3": "On a Roll",
    "streak_7": "Unstoppable",
    "consistent": "Consistent Logger",
    "comeback": "Comeback Kid",
    "platinum": "Platinum Walker",
}
# --- Stand-up reminder: shown only when the phone's syncs show you've barely moved ---
# "Inactive" = fewer than INACTIVE_MAX_STEPS new steps across at least INACTIVE_MINUTES,
# judged from two syncs; the newer sync must be at most SYNC_FRESH_MINUTES old.
INACTIVE_MINUTES = 30
INACTIVE_MAX_STEPS = 50
SYNC_FRESH_MINUTES = 15
SAMPLE_KEEP_DAYS = 2

# --- Progression tracks (the Challenges page) ---
# Lifetime totals unlock level badges; the "record" badge levels up with your best single day
# (everything you did that day added up). Planks are in seconds.
# Exercises are typed in by the user, so they only ever earn personal badges:
# they never count on leaderboards, tiers or challenges.
EXERCISE_TYPES = ("pushups", "squats", "planks", "jumping_jacks")
EXERCISE_MAX_PER_SET = {"pushups": 1_000, "squats": 2_000, "planks": 3_600, "jumping_jacks": 5_000}
TRACKS = {
    "steps": {
        "name": "Steps", "unit": "steps", "record_name": "Longest walk",
        "levels": [1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000],
        "record_levels": [5_000, 10_000, 15_000, 20_000, 30_000],
    },
    "pushups": {
        "name": "Push-ups", "unit": "push-ups", "record_name": "Most in a day",
        "levels": [5, 10, 25, 50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000],
        "record_levels": [10, 20, 30, 50, 100],
    },
    "squats": {
        "name": "Squats", "unit": "squats", "record_name": "Most in a day",
        "levels": [10, 25, 50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000, 20_000],
        "record_levels": [20, 40, 60, 100, 200],
    },
    "planks": {
        "name": "Planks", "unit": "seconds", "record_name": "Most plank time in a day",
        "levels": [30, 60, 120, 300, 600, 1_200, 1_800, 3_600, 7_200, 18_000, 36_000],
        "record_levels": [30, 60, 120, 180, 300],
    },
    "jumping_jacks": {
        "name": "Jumping jacks", "unit": "jumping jacks", "record_name": "Most in a day",
        "levels": [25, 50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000],
        "record_levels": [50, 100, 200, 300, 500],
    },
}

# --- Avatars: an emoji on a coloured circle. No photos: many users are minors. ---
# key -> (emoji, badge needed to unlock it, or None for free). Order = display order.
AVATARS = {
    "fox": ("🦊", None), "cat": ("🐱", None), "panda": ("🐼", None), "frog": ("🐸", None),
    "owl": ("🦉", None), "turtle": ("🐢", None), "penguin": ("🐧", None), "rabbit": ("🐰", None),
    "sneaker": ("👟", "first_log"), "star": ("⭐", "ten_k"), "fire": ("🔥", "streak_3"),
    "rocket": ("🚀", "streak_7"), "bolt": ("⚡", "consistent"), "lion": ("🦁", "comeback"),
    "crown": ("👑", "platinum"),
}
# Background colours (the CSS class is av-<key>, defined in static/css/style.css)
AVATAR_COLORS = ("peri", "blue", "pink", "mint", "peach", "violet", "gold", "sage")

# --- Avatar studio (Settings): build a character from parts, bought with EXP ---
# EXP is the in-app currency. How it is earned comes later; for now admins can give it.
# Price tiers: 0 = free starter, 50 common, 150 rare, 400 epic, 1000 legendary.
AVATAR_SLOTS = [   # (slot key, name shown) in display order
    ("color", "Colour"), ("eyes", "Eyes"), ("mouth", "Mouth"), ("hat", "Headwear"),
    ("extra", "Extras"), ("shoes", "Shoes"), ("bg", "Background"), ("glass", "Glass"), ("material", "Theme"),
]
# item key -> (slot, name, price in EXP). Order = display order within a slot.
AVATAR_ITEMS = {
    "color_mint": ("color", "Mint", 0), "color_sky": ("color", "Sky", 0),
    "color_peach": ("color", "Peach", 0), "color_lilac": ("color", "Lilac", 0),
    "color_sunny": ("color", "Sunny", 50), "color_coral": ("color", "Coral", 50),
    "color_berry": ("color", "Berry", 150), "color_ocean": ("color", "Ocean", 150),
    "color_midnight": ("color", "Midnight", 400), "color_gold": ("color", "Gold", 1000),

    "eyes_dots": ("eyes", "Dots", 0), "eyes_happy": ("eyes", "Happy", 0),
    "eyes_big": ("eyes", "Big", 50), "eyes_sleepy": ("eyes", "Sleepy", 50),
    "eyes_wink": ("eyes", "Wink", 150), "eyes_stars": ("eyes", "Starry", 400),

    "mouth_smile": ("mouth", "Smile", 0), "mouth_o": ("mouth", "Ooh", 0),
    "mouth_grin": ("mouth", "Grin", 50), "mouth_smirk": ("mouth", "Smirk", 50),
    "mouth_tongue": ("mouth", "Cheeky", 150),

    "hat_none": ("hat", "None", 0), "hat_headband": ("hat", "Sweatband", 50),
    "hat_cap": ("hat", "Cap", 150), "hat_beanie": ("hat", "Beanie", 150),
    "hat_flower": ("hat", "Flower", 150), "hat_party": ("hat", "Party hat", 400),
    "hat_headphones": ("hat", "Headphones", 400), "hat_crown": ("hat", "Crown", 1000),
    "hat_silver_visor": ("hat", "Silver visor", 100), "hat_gold_laurel": ("hat", "Gold laurel", 150),
    "hat_platinum_halo": ("hat", "Platinum halo", 200),

    "extra_none": ("extra", "None", 0), "extra_glasses": ("extra", "Glasses", 50),
    "extra_scarf": ("extra", "Scarf", 150), "extra_shades": ("extra", "Shades", 150),
    "extra_whistle": ("extra", "Coach whistle", 150), "extra_medal": ("extra", "Medal", 400),
    "extra_silver_wings": ("extra", "Silver wings", 100), "extra_gold_cape": ("extra", "Gold cape", 150),

    "shoes_plain": ("shoes", "Bare feet", 0), "shoes_sneakers": ("shoes", "Sneakers", 150),
    "shoes_runners": ("shoes", "Red runners", 50), "shoes_sky": ("shoes", "Sky trainers", 50),
    "shoes_neon": ("shoes", "Neon", 150), "shoes_pink": ("shoes", "Pink pops", 150),
    "shoes_court": ("shoes", "Court classics", 150), "shoes_black": ("shoes", "Midnight", 400),
    "shoes_rainbow": ("shoes", "Rainbow", 400), "shoes_gold": ("shoes", "Gold sneakers", 1000),

    "bg_plain": ("bg", "Plain", 0), "bg_sage": ("bg", "Sage", 0), "bg_sky": ("bg", "Sky", 50),
    "bg_track": ("bg", "Running track", 150), "bg_sunrise": ("bg", "Sunrise", 400),
    "bg_stars": ("bg", "Night sky", 400), "bg_platinum_glow": ("bg", "Platinum glow", 200),
}
# The "Glass" tab of the studio: the colour field behind the frosted glass look, which only
# Apple devices (iPhone, iPad, Mac) show. Stock is free and is what everyone starts with.
# key -> (name, price in EXP, light colours, dark colours); colours = (base, 4 glows).
GLASS_GRADIENTS = {
    "glass_stock": ("Stock", 0, ("#EEF1F6", "#B9E6C9", "#C7CBFF", "#FFD3C2", "#BFE3F7"),
                    ("#0A1020", "#1E4F48", "#2C2F7A", "#5A2E4A", "#183A66")),
    "glass_ocean": ("Ocean", 50, ("#EAF4F8", "#A8E0F0", "#B7C8FF", "#C5F2E6", "#9FD2F5"),
                    ("#07121F", "#12466A", "#1F2E7A", "#0F5A5A", "#173A66")),
    "glass_forest": ("Forest", 150, ("#F0F6EC", "#B5E3B0", "#D9EFA8", "#A8DCC8", "#CDE8B9"),
                     ("#08140C", "#1E4F2A", "#3A4F1A", "#145048", "#24402A")),
    "glass_sunset": ("Sunset", 150, ("#FFF3EC", "#FFC9A8", "#FFB3C7", "#FFE3A3", "#F9C2E0"),
                     ("#160A12", "#6A2E2A", "#6A1F4A", "#6A4A1A", "#4A1F5A")),
    "glass_candy": ("Candy", 400, ("#FFF2F8", "#FFC2E2", "#C9C2FF", "#B8F0E8", "#FFE0B8"),
                    ("#120A18", "#6A2456", "#3A2A7A", "#145A55", "#6A4520")),
    "glass_aurora": ("Aurora", 400, ("#EEF3FA", "#B4F5D8", "#C2B5FF", "#A8E8FF", "#E6C2FF"),
                     ("#050A16", "#0F6A50", "#3A1F8A", "#0F4F7A", "#5A1F7A")),
    "glass_gold": ("Gold", 1000, ("#FFF8EA", "#FFE19A", "#FFD0A0", "#FFF0C2", "#F2C88A"),
                   ("#120D04", "#6A4F12", "#5A3410", "#4A3A10", "#3A2A0A")),
}
GLASS_DEFAULT = "glass_stock"
# The "Theme" tab: Android phones get the Material You look, with the whole colour scheme
# grown from one seed colour (see material.py). Stock is free. A grey or black seed makes a
# neutral theme with no colour at all (Black also goes true black in dark mode). key -> (name, price, seed colour)
MATERIAL_THEMES = {
    "mat_stock": ("Stock", 0, "#5B67D8"), "mat_graphite": ("Graphite", 50, "#6B6B6B"),
    "mat_black": ("Black", 50, "#000000"), "mat_ocean": ("Ocean", 50, "#1E88C8"),
    "mat_forest": ("Forest", 150, "#3E8E4F"), "mat_berry": ("Berry", 150, "#C2185B"),
    "mat_sunset": ("Sunset", 400, "#E8743B"), "mat_grape": ("Grape", 400, "#7E57C2"),
    "mat_gold": ("Gold", 1000, "#C9A227"),
}
MATERIAL_DEFAULT = "mat_stock"
# Themes that look the same whatever Light/Dark/Automatic says: Graphite is always the light
# grey look, Black is always black and white.
MATERIAL_FIXED_MODE = {"mat_graphite": "light", "mat_black": "dark"}
# Everything the studio sells: avatar parts, glass gradients and Material You themes.
SHOP_ITEMS = {**AVATAR_ITEMS, **{k: ("glass", v[0], v[1]) for k, v in GLASS_GRADIENTS.items()},
              **{k: ("material", v[0], v[1]) for k, v in MATERIAL_THEMES.items()}}

# --- Daily login rewards: a 28-day calendar per tier. Open StrideBoard, tap Claim, move one day
# along (missing a day doesn't reset you). After day 28 it starts again, using the tier you
# finished last week: same tier, same rewards; a higher tier gets a better calendar.
# Each day: ("exp", amount) or ("item", avatar item key); an item you already own pays its
# price in EXP instead. Moving up a tier switches to the better calendar straight away (same
# day number); dropping down only shows when a calendar starts again. Tiers without their own
# calendar use the best one below them.
def _calendar(*weeks):
    return [day for week in weeks for day in week]


# Tier-only items: never sold, only given by that tier's reward calendar. Their "price" is the
# EXP paid instead if a calendar gives one you already own.
EXCLUSIVE_ITEMS = {"hat_silver_visor": "Silver", "extra_silver_wings": "Silver",
                   "hat_gold_laurel": "Gold", "extra_gold_cape": "Gold",
                   "hat_platinum_halo": "Platinum", "bg_platinum_glow": "Platinum"}

REWARD_TRACKS = {
    "Bronze": _calendar(
        [("exp", 5)] * 6 + [("exp", 25)],
        [("exp", 6)] * 6 + [("item", "hat_headband")],
        [("exp", 8)] * 6 + [("exp", 40)],
        [("exp", 10)] * 6 + [("item", "shoes_runners")],
    ),
    "Silver": _calendar(
        [("exp", 8)] * 6 + [("exp", 35)],
        [("exp", 10)] * 6 + [("item", "hat_silver_visor")],
        [("exp", 12)] * 6 + [("exp", 60)],
        [("exp", 15)] * 6 + [("item", "extra_silver_wings")],
    ),
    "Gold": _calendar(
        [("exp", 12)] * 6 + [("exp", 50)],
        [("exp", 15)] * 6 + [("item", "hat_gold_laurel")],
        [("exp", 18)] * 6 + [("exp", 80)],
        [("exp", 20)] * 6 + [("item", "extra_gold_cape")],
    ),
    "Platinum": _calendar(
        [("exp", 18)] * 6 + [("exp", 75)],
        [("exp", 22)] * 6 + [("item", "hat_platinum_halo")],
        [("exp", 26)] * 6 + [("exp", 120)],
        [("exp", 30)] * 6 + [("item", "bg_platinum_glow")],
    ),
}

# What everyone starts with. The colour varies by person so the leaderboards aren't all one colour.
AVATAR_DEFAULTS = {"eyes": "eyes_dots", "mouth": "mouth_smile", "hat": "hat_none",
                   "extra": "extra_none", "shoes": "shoes_plain", "bg": "bg_plain"}
AVATAR_START_COLORS = ("color_mint", "color_sky", "color_peach", "color_lilac")
EXP_MAX_GRANT = 100_000          # most EXP an admin can give in one go

TEN_K_STEPS = 10_000
CONSISTENT_DAYS = 5              # steps on 5 different days in one week
COMEBACK_FACTOR = 1.25           # week at least 25% above last week...
COMEBACK_MIN_LAST_WEEK = 10_000  # ...and last week had at least 10,000 steps

# --- The Android app: the newest version on the Releases page. Bump this with versionCode in
# android/app/build.gradle.kts, and Home shows older apps a small "Update" notice. ---
ANDROID_APP_LATEST = {"code": 6, "name": "1.5",
                      "news": "Your account link is now stored encrypted on your phone."}
ANDROID_APP_UPDATER_FROM = 5     # versions from here on update in-app; older ones reinstall once
ANDROID_APK_URL = "https://github.com/SohamBhongade/StrideBoard/releases/download/android-latest/StrideBoard.apk"

# --- Leaderboards, wrap-up and challenges ---
IMPROVEMENT_MIN_LAST_WEEK = 1_000  # need some steps last week to compare against
MOOD_CHART_DAYS = 28               # mood-vs-steps chart looks back 4 weeks
MIN_MOOD_DAYS_FOR_INSIGHT = 3      # mood insight needs 3+ days in each group
KM_PER_STEP = 0.0007
DISTANCE_STEPS_PER_USER_PER_DAY = 7_000
ACTIVE_USER_DAYS = 14              # "active" = has steps in the last 14 days

# --- Mini challenges: the way to earn EXP. Start one, do it, tap Done. ---
# Exercises go straight into the Challenges tracks (no typing numbers in).
# Walks finish by themselves once the phone has sent enough new steps.
# min_seconds: Done can't be tapped sooner than this after starting (stops instant taps).
# key -> {track, amount, exp, min_seconds}. Order = display order.
MINI_CHALLENGES = {
    "pushups_10": {"track": "pushups", "amount": 10, "exp": 10, "min_seconds": 15},
    "pushups_25": {"track": "pushups", "amount": 25, "exp": 25, "min_seconds": 40},
    "squats_15": {"track": "squats", "amount": 15, "exp": 10, "min_seconds": 20},
    "squats_30": {"track": "squats", "amount": 30, "exp": 20, "min_seconds": 45},
    "planks_30": {"track": "planks", "amount": 30, "exp": 10, "min_seconds": 30},
    "planks_60": {"track": "planks", "amount": 60, "exp": 25, "min_seconds": 60},
    "jumping_jacks_25": {"track": "jumping_jacks", "amount": 25, "exp": 10, "min_seconds": 20},
    "jumping_jacks_50": {"track": "jumping_jacks", "amount": 50, "exp": 20, "min_seconds": 40},
    "walk_1000": {"track": "steps", "amount": 1_000, "exp": 15, "min_seconds": 300},
    "walk_2500": {"track": "steps", "amount": 2_500, "exp": 35, "min_seconds": 900},
}
MINI_DAILY_LIMIT = 3               # each mini challenge can earn EXP this many times a day
