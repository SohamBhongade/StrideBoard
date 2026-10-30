<p align="center">
  <img src="docs/images/banner.svg" alt="StrideBoard: every step, every student, every teacher, one live game" width="100%">
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-3-000000?logo=flask&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-built--in-003B57?logo=sqlite&logoColor=white">
  <img alt="Kotlin" src="https://img.shields.io/badge/Android-Kotlin-7F52FF?logo=kotlin&logoColor=white">
  <img alt="Health Connect" src="https://img.shields.io/badge/Health%20Connect-steps-34A853?logo=android&logoColor=white">
  <img alt="Apple Health" src="https://img.shields.io/badge/Apple%20Health-Shortcuts-000000?logo=apple&logoColor=white">
  <img alt="PWA" src="https://img.shields.io/badge/PWA-installable-5A0FC8?logo=pwa&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-449%20passing-brightgreen">
</p>

<h3 align="center">A cross-platform, server-authoritative movement engine that turns a whole school's step counts into a live, fair, weekly game.</h3>

---

## ⚡ The pitch

Schools sit still. Students sit through six or seven lessons a day; teachers stand at a board, then sit through marking. Everyone *knows* they should move more, and almost nobody counts.

**StrideBoard counts for them, and then makes it a game.**

Every phone in the school already measures steps. StrideBoard reaches into that data through **two completely different health platforms**: Apple Health on iPhone (through a one-tap Shortcut) and Google Health Connect on Android (through a native Kotlin app). Daily totals arrive through a single hardened REST endpoint in a **Flask + SQLite core**, where a rules engine on a Dubai-time clock turns raw numbers into:

- 🎯 **adaptive personal goals** that learn from each person's own 14-day rhythm,
- 🏆 **five live leaderboards** (today, this week, this month or all time), including *effort* and *improvement* boards so the fittest person doesn't always win,
- 🥉🥈🥇💎 **weekly tiers** that reset every Monday, so anyone can climb,
- 🏅 **about 85 server-awarded badges**, from a first step to a million,
- 💪 **mini challenges** (push-ups, squats, planks, jumping jacks, walks) played as animated game scenes that earn **EXP**,
- 🎨 an **avatar studio** where EXP buys shoes, hats, colours and themes, plus a **daily login reward** calendar,
- 🌍 **school-wide distance challenges** where every step moves one shared progress bar,
- 🪞 a **Weekly Wrap-Up** that puts steps next to mood and writes each person one honest sentence about their week.

All of it lives on **one mobile-first website** that installs like an app: a native WebView shell on Android, a Home Screen PWA on iPhone, a normal page in any browser, and a **leaderboard screen** app for a big display in the school.

No GPS. No weight. No BMI. No photos. Just steps, and a reason to take more of them.

> Built for **AL SOUT, The Student Wellbeing Project 2026** (Ras Al Khaimah, UAE, via RAKDOK), category **"Play, Code, Create: The AI Innovation Challenge"**, theme *Innovating for Everyday Wellbeing*.
>
> **Live site:** https://strideboard.pythonanywhere.com

---

## 📚 Contents

1. [Feature tour](#-feature-tour)
2. [The game](#-the-game)
3. [How it works](#-how-it-works)
4. [The algorithms](#-the-algorithms)
5. [Measuring real wellbeing impact](#-measuring-real-wellbeing-impact)
6. [Privacy, child safety and security](#-privacy-child-safety-and-security)
7. [Tech stack](#-tech-stack)
8. [Repository layout](#-repository-layout)
9. [Run it on your own computer](#-run-it-on-your-own-computer)
10. [Connect your phone](#-connect-your-phone)
11. [Deploying and updating](#-deploying-and-updating)
12. [Backups, housekeeping and disk space](#-backups-housekeeping-and-disk-space)
13. [API reference](#-api-reference)
14. [Testing](#-testing)
15. [Honest limits](#-honest-limits)
16. [Team](#-team)

---

## 📱 Feature tour

<table>
  <tr>
    <td align="center" width="33%"><img src="docs/screenshots/dashboard.png" width="240" alt="Dashboard"><br><b>Dashboard</b></td>
    <td align="center" width="33%"><img src="docs/screenshots/leaderboard.png" width="240" alt="Leaderboards"><br><b>Leaderboards</b></td>
    <td align="center" width="33%"><img src="docs/screenshots/wrapup.png" width="240" alt="Weekly Wrap-Up"><br><b>Weekly Wrap-Up</b></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/screenshots/challenges.png" width="240" alt="Challenges"><br><b>Challenges</b></td>
    <td align="center"><img src="docs/screenshots/log.png" width="240" alt="Log"><br><b>Log</b></td>
    <td align="center"><img src="docs/screenshots/badges-avatars.png" width="240" alt="Badges and avatars"><br><b>Badges &amp; avatars</b></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/screenshots/settings.png" width="240" alt="Settings"><br><b>Settings</b></td>
    <td align="center"><img src="docs/screenshots/admin.png" width="240" alt="Admin"><br><b>Admin</b></td>
    <td align="center"><img src="docs/screenshots/iphone-pwa.png" width="240" alt="iPhone Home Screen app"><br><b>iPhone app (PWA)</b></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/screenshots/iphone-shortcut.png" width="240" alt="iPhone Shortcut"><br><b>iPhone Shortcut</b></td>
    <td align="center"><img src="docs/screenshots/android-app.png" width="240" alt="Android app"><br><b>Android app</b></td>
    <td align="center"><img src="docs/screenshots/android-setup.png" width="240" alt="Android setup"><br><b>Android setup</b></td>
  </tr>
</table>

### 🏠 Home: the four game stages on one screen
1. **Goal:** a progress ring that fills toward today's goal (the number counts up), and a water glass that fills as you tap **+**.
2. **Move:** this week's total, your streak, a one-tap mood check-in (1 to 5) and reminders. A **stand-up reminder** appears only when two recent syncs show fewer than 50 new steps in 30+ minutes.
3. **Level up:** your tier card, how to reach the next tier, and the daily login reward calendar.
4. **Social:** a leaderboard preview (top 3 and you) and your badges.

On iPhone there's a **"Sync from Apple Health"** button; on Android an **Update** notice appears when a new app version is out. Home also works offline (the service worker keeps a copy, forgotten on logout).

### 🏆 Leaderboards: five ways to win
| View | Ranks people by | Why it exists |
|---|---|---|
| **Students** | Total steps | The main race |
| **Teachers** | Total steps | Same race, separate league |
| **Departments / classes** | Average steps per member | Everyone counts, even with 0 steps |
| **Effort** | % of your own goal | Fair: a 6,000-step goal hit 120% beats a 10,000-step goal hit 90% |
| **Improvement** | % change vs the same days last period | Rewards getting better, not being the fittest (needs 1,000+ steps last time) |

- **Periods:** Today, This week (default), This month, All time (Effort and Improvement have no all-time version).
- **Search** by any part of a name, or a class/department word.
- A **podium** for the top 3, avatars, the top 50 plus your own row, and "Show everyone".
- **Private names by default:** students and anyone under 18 appear as "Amal K."; each person can choose Full name, First name and initial, or Hidden in Settings.
- A **Report** flag next to everyone else, reviewed by admins.
- Admins and blocked people never appear. Ties go to whoever got there first.

### 💪 Challenges: mini challenges and progression tracks
- **Mini challenges** earn EXP, each up to 3 times a day: 10 or 25 push-ups, 15 or 30 squats, 30 s or 60 s plank, 25 or 50 jumping jacks, and walks of 1,000 or 2,500 steps. Each is an animated scene where an athlete in your avatar's colours does the move; **Done** unlocks after a minimum time.
- **Walks** have 5 checkpoints; the walker only moves forward when your phone sends real new steps (Android pushes live steps every 30 s).
- **Progression tracks** for steps, push-ups, squats, planks and jumping jacks: lifetime level badges plus a "record" badge for your best single day.
- **School challenges:** a distance challenge (`km = steps × 0.0007`) along a real route, and department races. Admins create and close them.

### 🪞 Weekly Wrap-Up: the reflection stage
- **This week vs last week**, compared fairly (Monday to today against the same days last week).
- **Tier change** (for example *Silver → Gold*) and your **best day**.
- A **daily steps chart** and a **mood-vs-steps chart** (28 days, Chart.js).
- One **insight sentence** from simple, explainable rules, for example *"On days you hit your goal, your average mood was 4.2 vs 3.1 on other days."* (shown only with 3+ days of mood data in each group).

### ✍️ Log
Mood, water and activities (walk, gym, sport, yoga, stretch, other) with minutes, plus your last 7 days. **Steps can't be typed in:** they only come from phones, so the leaderboards stay fair.

### 🏅 Badges, EXP and the avatar studio
- **Seven classic badges** (First Steps, 10K Club, On a Roll, Unstoppable, Consistent Logger, Comeback Kid, Platinum Walker) each unlock an emoji avatar. With the track badges there are about 85 in all, on the Badges page.
- **EXP** comes from mini challenges, the daily login reward and admin gifts.
- **The studio** sells colours, eyes, mouths, headwear, extras, shoes, backgrounds, Glass gradients (Apple devices) and Material You themes (Android, Windows, Chromebooks) for free, 50, 150, 400 or 1,000 EXP.
- **Daily login reward:** a 28-day calendar per tier; days 14 and 28 give items, and some items are tier-only (Silver visor, Gold cape, Platinum halo...).

### ⚙️ Settings
Daily goal, age band, appearance (Light / Dark / Automatic, Fast mode), recovery email, the avatar studio, iPhone and Android setup, and **Your data and privacy**: correct your name and class, choose your leaderboard name, download everything (JSON) or your steps (CSV), and delete your account. The phone token is hidden under **Advanced**, because phones link themselves.

### 🛠️ Admin
- Reports to review, wellbeing impact numbers, give EXP.
- **Add people from pasted CSV:** `username,display_name,role,department,age_band,pin`
- People list with role tabs, search, steps today and this week, last sync, and Change role.
- Challenges, the iPhone Shortcut link, the leaderboard screen code, and backups.
- **Owner only:** time out, ban, unban, rename, remove a day's steps, reset a person's data, and delete accounts forever.

### 📺 Leaderboard screen
`/board?key=CODE` shows Students and Teachers side by side for a big display, refreshing every minute. The **StrideBoard Leaderboard** desktop app (Windows and Mac, in `desktop/`) shows it full screen, keeps the display awake and hides the pointer.

### 📲 Two native integrations, one app experience
| | iPhone | Android |
|---|---|---|
| **Reads steps from** | Apple Health | Google Health Connect |
| **How** | "Strideboard" Shortcut, installed with one tap from Settings | Native Kotlin app + WorkManager |
| **When** | The Home "Sync" button, plus optional 07:00 and 21:30 automations | Every 3 hours, ~23:30 nightly, on app open, and live every 30 s while open |
| **Linking** | The Sync button hands the Shortcut your token | The app links itself when you log in |
| **The app itself** | Website added to the Home Screen (PWA) | Same website in a full-screen WebView |
| **Sends** | Yesterday's and today's totals | Yesterday's and today's totals |

Sending **yesterday as well as today** on every sync means late-evening steps are never lost. A **0 total is never sent**, so an empty sync can't wipe out a day.

---

## 🎮 The game

<p align="center"><img src="docs/images/game-loop.svg" alt="The four-stage weekly game loop" width="100%"></p>

The competition rules require at least three stages. StrideBoard has four, and they repeat every week:

| Stage | What happens | Where you see it |
|---|---|---|
| **1 · Set the goal** | A personal daily goal, your current tier, and one line on why movement helps wellbeing | Home |
| **2 · Move and compete** | Steps arrive from phones; leaderboards, streaks, challenges and mini challenges update live | Home, Leaderboards, Challenges |
| **3 · Level up** | A new tier every week, badges, EXP and avatar items | Home, Badges, Settings |
| **4 · Reflect** | Week vs last week, tier change, best day, mood-vs-steps chart, a personal insight | Weekly Wrap-Up |

### Tiers

<p align="center"><img src="docs/images/tiers.svg" alt="Bronze, Silver, Gold and Platinum weekly tiers" width="100%"></p>

| Tier | Weekly steps |
|---|---|
| Bronze | 0 |
| Silver | 35,000 |
| Gold | 60,000 |
| Platinum | 90,000 |

### Classic badges

| Badge | Name | How to earn it | Unlocks |
|---|---|---|---|
| `first_log` | First Steps | Your first steps entry | 👟 sneaker |
| `ten_k` | 10K Club | 10,000+ steps in one day | ⭐ star |
| `streak_3` | On a Roll | 3-day goal streak | 🔥 fire |
| `streak_7` | Unstoppable | 7-day goal streak | 🚀 rocket |
| `consistent` | Consistent Logger | Steps on 5 different days in one week | ⚡ bolt |
| `comeback` | Comeback Kid | A week 25%+ above the last (last week at least 10,000) | 🦁 lion |
| `platinum` | Platinum Walker | Reach Platinum in a week | 👑 crown |

---

## 🧠 How it works

<p align="center"><img src="docs/images/architecture.svg" alt="StrideBoard architecture: phones to API to Flask and SQLite to the website" width="100%"></p>

1. **Phones collect.** The iPhone Shortcut asks Apple Health for step samples **grouped by day**, so Health itself merges phone and Apple Watch data without counting anything twice. The Android app calls Health Connect's `aggregate()` with `StepsRecord.COUNT_TOTAL` over exact Dubai-time day boundaries.
2. **The server decides.** Each phone sends `{token, date, steps, source}` to `POST /api/steps`. The server identifies the person by their secret token, validates every field, **upserts** one row per person per day (a newer total replaces the older one), then recalculates their week, tier and badges.
3. **Everyone sees.** The website reads everything through one data layer (`data.py`) and renders it with server-side Jinja templates. There is no front-end framework and no build step: plain HTML, CSS, a little vanilla JavaScript and Chart.js.

**Design rules the whole codebase follows:**
- **One source of truth for time.** "Today" is always `datetime.now(ZoneInfo("Asia/Dubai"))`, never the server's clock (cloud servers run in UTC, which would shift the school day by four hours).
- **All SQL lives in one file** (`data.py`), always parameterised.
- **Pure game maths** (`calc.py`) has no database access at all, so every rule is unit-tested in isolation.
- **Every rule and number lives in `config.py`.**
- **The server is authoritative.** Badges, tiers, streaks and EXP are never trusted from a client.

---

## 📐 The algorithms

### Adaptive daily goal
Everyone starts at **6,000 steps a day**. Once someone has **14+ days of data**, their goal adapts to them every Monday:

```
goal = round_to_nearest_250( average_of_last_14_days × 1.10 )
goal = clamp(goal, 3,000, 15,000)
```

In words: *"a little more than you usually do"*. It's always reachable, and it always nudges you up. A goal you set yourself in Settings (1,000 to 30,000) is never overridden.

<sub>Goals are general suggestions, not medical advice.</sub>

### Leaderboard maths
```
effort       = steps_in_period / (daily_goal × days_in_period)
improvement  = (this_period_so_far − same_days_last_period) / same_days_last_period
department   = sum(member steps) / number of members   (members with no steps count as 0)
distance_km  = total_steps_of_everyone_in_window × 0.0007
```
Ties go to the person whose latest update came **first**.

### Streaks
Count back from today (or from yesterday, if today's goal isn't reached yet) while `steps ≥ daily_goal`.

### Input hardening on `/api/steps`
The endpoint accepts what real phones actually send and rejects everything else:
- `"8423"`, `8423.4` and Arabic-Indic digits like `"٨٤٢٣"` are all accepted (decimals are rounded);
- negative numbers, anything over 100,000, future dates, dates over 7 days old, unknown sources and non-JSON bodies are rejected with a readable reason;
- request bodies over 16 KB are refused.

---

## 📈 Measuring real wellbeing impact

The rules ask every project to show how its data shows real impact. StrideBoard measures it directly from the database (`data.impact_stats`, on the Admin page):

| Measure | What it shows |
|---|---|
| **Average daily steps before vs during** | Phones keep step history, so a person's first sync captures up to 7 days *before* they joined. That gives a real baseline to compare against. |
| **People hitting their goal** | How many users reach their personal goal on a typical day |
| **Mood on goal days vs other days** | Whether people report feeling better on days they move more |
| **Entries by source** | How much data comes straight from iPhone and Android |
| **Improvement leaderboard** | Week-on-week change across the school |

We report these honestly: a short school trial can show **association**, not proof of cause, and we say so in the demo.

---

## 🔒 Privacy, child safety and security

Many users are minors, so StrideBoard follows the UAE **Personal Data Protection Law (PDPL)** and the **Child Digital Safety Law**, and collects the minimum:

| Collected | Not collected |
|---|---|
| Daily step totals | Location / GPS |
| Optional mood (1–5), water, activity minutes, exercises | Weight, height, BMI |
| Age **band** (not exact age) | Date of birth |
| Department or class | Photos, contacts, ads |
| A fingerprint of the recovery email (never the address) | The email address itself |

**Privacy**
- **Sign-up is closed** by default (admins add people). A full English and Arabic privacy policy and terms are at `/privacy`.
- **Your-data rights** in Settings: correct, download (JSON or CSV) and delete.
- **Private leaderboard names** by default for students and under-18s.
- Logged out after 30 days without use (phones keep syncing).
- Data is hosted outside the UAE (PythonAnywhere); the policy says so.

**Child safety**
- **Under-13 self sign-ups need a parent's approval** by email link; the parent can also set a **daily time limit** and the leaderboard name choice. Unanswered requests are deleted after 7 days.
- **Break reminder:** under-18s get a "Time for a break" screen after 30 minutes of use.
- **Report button** with admin review; the reporter is never shown to the person reported.
- A **word filter** (English, Arabic, Arabizi, Hindi/Urdu) checks names, renames, CSV imports, challenge titles and report notes.

**Security**
- PINs are hashed (Werkzeug), with lockouts after 5 wrong PINs per name or 20 per address.
- **Phone tokens are sealed** (AES-256-GCM) with an HMAC fingerprint for lookup, never logged, and shown only where needed.
- CSRF check on every form, POST-only logout, HttpOnly/SameSite/Secure cookies, HSTS, a strict Content Security Policy (everything self-hosted), open-redirect protection, parameterised SQL and Jinja autoescaping.
- **Backups are encrypted** (AES-256-GCM).
- The Android app reads **only step totals**, shows a consent screen (English and Arabic) and has a Disconnect button.

---

## 🧰 Tech stack

| Layer | Technology |
|---|---|
| Server | Python 3.10+, Flask 3, built-in `sqlite3` (no ORM) |
| Website | Jinja templates, plain CSS, vanilla JS, Chart.js 4.4.1 (self-hosted), Outfit font, mobile-first |
| Looks | Default, Glass (Apple devices), Material 3 Expressive (Android, Windows, Chromebooks), dark mode, Lite and Fast modes |
| iPhone app experience | PWA: `manifest.json`, icons, service worker with offline Home |
| iPhone steps | Apple Shortcuts + Apple Health |
| Android | Kotlin, Health Connect, WorkManager, WebView (APK built by GitHub Actions) |
| Leaderboard screen | Electron desktop app (Windows and Mac) |
| Tests | pytest (449 tests) |
| Hosting | PythonAnywhere (HTTPS) |

---

## 🗂️ Repository layout

```
StrideBoard/
├── server/
│   ├── app.py           website routes, login, sign-up, settings, admin, security headers
│   ├── api.py           POST /api/steps (Flask Blueprint)
│   ├── data.py          the data layer: every SQL query lives here
│   ├── calc.py          pure game maths: weeks, tiers, streaks, goals, badges, insights
│   ├── db.py            connections, schema upgrades, Dubai clock, CLI commands
│   ├── config.py        every rule and number
│   ├── schema.sql       database tables
│   ├── tokens.py        phone-token sealing
│   ├── wordfilter.py    rude-word filter
│   ├── mailer.py        Gmail: sign-up codes, PIN resets, parent emails, backup emails
│   ├── backup.py        encrypted backups and nightly housekeeping
│   ├── avatar_art.py    SVG avatars
│   ├── mini_scene.py, workout_rig.py   animated mini challenge scenes
│   ├── material.py      Material You colour palettes
│   ├── make_admin.py    make a user an admin from the console
│   ├── seed.py          demo data or a clean admin-only start
│   ├── devapp.py        API-only app for testing
│   ├── templates/       Jinja pages
│   ├── static/          CSS, JS, Chart.js, font, PWA manifest, service worker, icons, iPhone Shortcut
│   └── tests/           pytest suite
├── android/             Kotlin app: WebView + Health Connect sync (see android/README.md)
├── ios/                 the "Strideboard" Shortcut (see ios/README.md)
├── desktop/             the Leaderboard screen app (see desktop/README.md)
├── docs/                images and screenshots for this README
├── requirements.txt
└── README.md
```

---

## 💻 Run it on your own computer

You need **Python 3.10 or newer** and **Git**.

```bash
git clone https://github.com/SohamBhongade/StrideBoard.git
cd StrideBoard

python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux / Git Bash:  source .venv/bin/activate

pip install -r requirements.txt

cd server
python seed.py              # a local database with clearly fake demo people
flask --app app run         # open http://127.0.0.1:5000
```

Log in with a demo person's **full name** (for example *Rami Aziz*) and PIN **1234**.

Useful extras:
```bash
python seed.py --reset                 # wipe and reseed the demo data
python seed.py --reset --admin-only    # clean start for real users (prints a new admin PIN)
STRIDEBOARD_SIGNUP_OPEN=1 flask --app app run    # try the sign-up page
STRIDEBOARD_MAIL_DEBUG=1 flask --app app run     # print emails instead of sending them
```

Restart the server after changing templates (they are cached).

---

## 📲 Connect your phone

### iPhone
1. In Safari, open the website and log in → **Share → Add to Home Screen**.
2. Settings → **iPhone** → tap the link to install the **Strideboard** Shortcut, and allow **Steps** access the first time it runs.
3. On Home, tap **Sync from Apple Health** whenever you like. Optional: in Shortcuts → **Automation**, run it daily at **07:00** and **21:30**.

Full guide: [`ios/README.md`](ios/README.md).

### Android
1. Install the StrideBoard APK (the link is on the Settings page; it comes from the `android-latest` release).
2. Log in. The app **links itself**: no token to type. Allow step access on the consent screen.
3. Set battery usage for StrideBoard to **Unrestricted** so background sync keeps running.

The app updates itself when a new version is out. Build guide: [`android/README.md`](android/README.md).

---

## 🚀 Deploying and updating

StrideBoard runs on **PythonAnywhere** (https://strideboard.pythonanywhere.com) with HTTPS forced.

**Updating the live site** (Bash console):
```
cd ~/strideboard && git pull && touch /var/www/strideboard_pythonanywhere_com_wsgi.py
```

**Setting up from scratch:**
1. `git clone` the repository to `~/strideboard` and `pip3 install --user -r requirements.txt`.
2. In the WSGI file, set the settings below with `os.environ["..."] = "..."`, then `from app import app as application`.
3. Run `python3 seed.py --reset --admin-only` and keep the admin PIN safe.
4. Click **Reload** on the Web tab. Daily backups and housekeeping then run by themselves (see [Backups](#-backups-housekeeping-and-disk-space)).
5. On the free plan, click the button on the Web tab that extends the site before it expires.

| Setting | What it does |
|---|---|
| `STRIDEBOARD_SECRET_KEY` | **Required.** Signs sessions and protects phone tokens. The app refuses the public default. |
| `STRIDEBOARD_DATABASE` | Path to the database. Keep it **outside** the code folder (`~/strideboard-data/`). |
| `STRIDEBOARD_BACKUP_KEY` | 64 hex characters for backup encryption (recommended, so changing the secret key doesn't lock old backups). |
| `STRIDEBOARD_GMAIL_USER`, `STRIDEBOARD_GMAIL_APP_PASSWORD` | Gmail for codes, PIN resets, parent emails and backup emails. |
| `STRIDEBOARD_OWNER` | The owner account's username. |
| `STRIDEBOARD_SIGNUP_OPEN=1` | Opens self sign-up (closed by default). |
| `STRIDEBOARD_JOIN_CODE`, `STRIDEBOARD_EMAIL_DOMAINS` | Optional sign-up limits. |
| `STRIDEBOARD_SCHOOL_NAME`, `STRIDEBOARD_PRIVACY_CONTACT`, `STRIDEBOARD_TEAM_NAMES` | Filled into the privacy policy. |

Never put these values in commits or chats.

When CSS or JS changes, bump `ASSET_VERSION` in `server/app.py` so phones fetch the new files.

---

## 💾 Backups, housekeeping and disk space

**The site runs this by itself, once a day.** The free PythonAnywhere plan has no scheduled
tasks, so the first visit or phone sync of each Dubai day claims the daily job, and it runs
just after that reply has been sent, so nobody waits. Only one web worker runs it each day,
and if it fails the site carries on (Admin → Backups shows the latest copy). To turn it off,
set `STRIDEBOARD_DAILY_JOB=0`. You can also run it by hand from a Bash console (or as a daily
task on a paid plan); it reads the site's settings from the WSGI file:
```
python3 /home/strideboard/strideboard/server/backup.py
```
Each day it:

1. **Backs up** the database (SQLite's own backup, consistent even while phones sync), compressed and **encrypted (AES-256-GCM)**, into `strideboard-data/backups/`, keeping the last 7. On Mondays it also emails the copy to the site's Gmail. Delete those emails after 4 weeks, as the privacy policy promises.
2. **Tidies up** (after the backup, so the backup is the safety net). Only working notes are trimmed; what people see never changes:

   | Table | What happens |
   |---|---|
   | `step_samples` | Snapshots older than 2 days are removed |
   | `screen_time` | Days older than a week are removed |
   | `email_codes`, `pending_signups` | Removed after a day (they hold email addresses) |
   | `mini_runs` | Attempts older than 14 days are removed (only today's count is used) |
   | `exercises` | Sets older than 14 days are merged into one row per type per day (same totals and best days) |
   | `exp_ledger` | Rows older than 60 days are merged into one per person (same balance) |
   | `daily_rewards` | Claims older than 60 days are removed, except each person's latest |

3. **Shrinks the file** when a quarter or more of it is empty space (SQLite files never shrink by themselves).

**How much space?** Measured with a simulated school of 1,000 people syncing every day for 200 days: the database is **84 MB** with housekeeping (240 MB without it), and each backup is about **11 MB**. That leaves plenty of room on the free plan's 512 MB. Steps, moods and water are kept for good, so the database grows by roughly that much per school year at that size. With today's handful of users it's well under 1 MB.

Check disk use any time on the **Files** tab. PythonAnywhere's own web logs also count towards it; old ones can be deleted from the **Web** tab's log links.

**Any time:** the owner can click **Admin → Backups → Download a backup** (not encrypted: it goes straight to the owner's computer over HTTPS).

**To restore** (Bash console):
```
cd ~/strideboard-data
cp strideboard.sqlite3 strideboard-before-restore.sqlite3     # keep the current one, just in case
python3 ~/strideboard/server/backup.py --decrypt backups/strideboard-backup-YYYY-MM-DD.sqlite3.gz.enc strideboard.sqlite3
touch /var/www/strideboard_pythonanywhere_com_wsgi.py
```
(For a downloaded or emailed backup, upload the file first, then use its name instead.)

---

## 🔌 API reference

### `POST /api/steps`
```json
{ "token": "<your api_token>", "date": "2026-10-14", "steps": 8423, "source": "ios_shortcut" }
```

| Field | Rules |
|---|---|
| `token` | Required. The person's secret phone token |
| `date` | Optional (`YYYY-MM-DD`, Dubai time). Default today. Not in the future, at most 7 days ago |
| `steps` | 0 to 100,000. Decimals rounded. Numeric strings and Arabic-Indic digits accepted |
| `source` | `manual`, `ios_shortcut`, `android_app` or `other` |

| Reply | Meaning | Phone should |
|---|---|---|
| `200 {"ok": true, "weekly_total": 41230, "tier": "Silver"}` | Saved | Show "synced" |
| `400 {"ok": false, "error": "..."}` | Bad input | Show the reason, don't retry |
| `401 {"ok": false, "error": "invalid token"}` | Wrong or old token | Relink (Android does this itself; on iPhone tap Sync on Home) |
| `413 {"ok": false, "error": "request is too large"}` | Body over 16 KB | Don't retry |
| Network error / 5xx | Server unreachable | Retry later |

---

## 🧪 Testing

```bash
cd server && python3 -m pytest -q
```

449 tests (about 90 s) cover week boundaries, tier edges, streaks, adaptive goals, ties, every badge and leaderboard, every API error, sign-up, parent approval, moderation, privacy controls, backups and housekeeping.

---

## 🧭 Honest limits

- **iPhone sync isn't continuous.** iOS hides Health data while the phone is locked, so a timed automation can occasionally miss. The Sync button on Home covers this.
- **Android background sync depends on the phone.** Some phones pause background work to save battery. The app also syncs whenever it's opened.
- **The Android app is sideloaded** (no Play Store), and there is no native iPhone app; iPhone uses the PWA.
- **The live database file isn't encrypted at rest** (the backups are).
- **Login lockouts are kept in memory**, so they aren't shared between several server workers (fine at the current size).
- **Insights are rule-based**, which makes them explainable. They show patterns, not medical advice.

---

## 👥 Team

StrideBoard was created by **the StrideBoard team** (its members are named in [LICENSE](LICENSE)),
supervised by **Ahamed Kaleel**.

© 2026 The StrideBoard team. All rights reserved. See [LICENSE](LICENSE): no part of StrideBoard may be copied,
reused or hosted elsewhere without the team's written permission. Third-party parts: Chart.js (MIT) and the
Outfit font (SIL OFL).

Built with AI coding assistants, as the competition category intends. The team planned the design, split the work into three parts with fixed interfaces, reviewed and tested the code, and ran it with real users.

---

<p align="center"><i>This app is for fun and motivation. Goals are general suggestions, not medical advice.</i></p>
