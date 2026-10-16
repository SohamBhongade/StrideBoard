## Website and iPhone app (Agent 3)

Paste this section into the team README under the website heading.

**What it is:** the Flask + Jinja website everyone uses (and that the Android app shows full screen), installable on iPhone as a home-screen app (PWA).

**Files (Agent 3 owns these):**
- `server/app.py`: `create_app()`, login, CSRF check, and all page routes. Gets all data from `data.py` (no SQL here).
- `server/templates/`: one template per page, plus `base.html` (layout, navigation, footer) and `_macros.html` (icons, headers, empty states).
- `server/static/css/style.css`: all styles. Mobile first, works at 360px wide.
- `server/static/js/app.js`: copy button, "are you sure?" prompts, stand-up reminder, iPhone install hint, service worker setup.
- `server/static/js/wrapup.js`: the mood-and-steps chart (Chart.js from a CDN).
- `server/static/manifest.json`, `server/static/sw.js`, `server/static/icons/`: the PWA (app name, icons, offline page).

**Run it:** from the `server` folder, `flask run`, then open http://127.0.0.1:5000 . Log in with a username and PIN made by `seed.py` or the admin page.

**Pages:**

| Page | What it shows | Game stage |
|---|---|---|
| `/login` | Username + PIN | |
| `/` | Today's steps vs goal (ring + blocks), water, tier and steps to the next tier, this week's bars, streak, mood check-in, reminders, leaderboard preview, badges | 1, 2, 3 |
| `/log` | Add steps by hand (today or the last 7 days), mood, water, activity; last 7 days list | 2 |
| `/leaderboard?view=` | student, teacher, department, effort, improvement, with a top-3 podium | 2 |
| `/challenges` | School distance (km and progress bar) and class-vs-class standings | 2 |
| `/insights` | Weekly Wrap-Up: vs last week, tier change, best day, mood-vs-steps chart, insight sentence | 4 |
| `/settings` | Phone token (show, copy, make new), iPhone and Android setup, age band, own goal | |
| `/admin` | Admins only: add people from CSV, create and close challenges, impact stats for the video | |
| `/offline`, `/sw.js` | PWA offline page and service worker | |

**Reminders (in-site only):** a "time to stand up" card every 45 minutes between 7:00 and 21:00 while the site is open, and a water-break card when you're behind a steady pace of 8 glasses a day. Both are general suggestions, not medical advice. The 8-glass target is a placeholder for the team to verify, like the step goals.

**Security:** session login; every form has a hidden CSRF token checked on the server; Jinja autoescape stays on; the token is hidden until you tap Show. The `/api/` blueprint skips the login and CSRF check because phones use their token instead.

**Things to check with Agent 1:**
- Every `data.py` function is called with `today` as a "YYYY-MM-DD" string (from `app.today()`).
- `get_user()` must include `api_token` so Settings can show it.
- `weekly_wrapup()["mood_vs_steps"]` rows: `{"date", "steps", "mood"}`; `mood` can be None.
- `active_challenges()["standings"]` rows: `{"name", "value", "label"}`.
- `impact_stats()["entries_by_source"]`: a dict like `{"ios_shortcut": 61, "android_app": 48, "manual": 22}`.

**Things to check with Agent 2:** the iPhone and Android setup steps on `/settings` (marked TODO in `settings.html`).
