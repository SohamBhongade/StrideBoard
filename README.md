# StrideBoard

Students and teachers' daily steps arrive automatically from their phones; they compete
on weekly leaderboards, level up through tiers, join school challenges, and see a weekly
wrap-up linking steps and mood. Built for AL SOUT, The Student Wellbeing Project 2026.

Each agent edits only its own section below.

---

## Agent 1: database and data layer

Files: `server/config.py, schema.sql, db.py, calc.py, data.py, api.py, seed.py, devapp.py, tests/`

| File | What it does |
|---|---|
| `config.py` | Every game number (tiers, goals, badges, limits). Change rules here. |
| `schema.sql` | The tables. Safe to run again; never deletes data. |
| `db.py` | Opens the database, Dubai "today", Flask setup and `flask` commands. |
| `calc.py` | Pure game maths (no database): weeks, tiers, streaks, goals, badges, insight. |
| `data.py` | **All** SQL. The website calls only these functions. |
| `api.py` | `POST /api/steps` for the iPhone Shortcut and the Android app. |
| `seed.py` | Admin account plus optional fake demo data. |
| `devapp.py` | A tiny app with only the database and the API, for testing before the website exists. |

### Run it on a laptop

Use **Git Bash** on Windows (the commands below are Bash), from the `server` folder:

```bash
python -m venv .venv
source .venv/Scripts/activate        # Mac/Linux: source .venv/bin/activate
pip install -r ../requirements.txt

python -m pytest tests -q            # run all tests (about 150, ~20 seconds)
python seed.py                       # fake demo data; prints the admin PIN
flask --app devapp run               # API at http://127.0.0.1:5000
```

The database file is `server/instance/strideboard.sqlite3` unless you set
`STRIDEBOARD_DATABASE`. It is in `.gitignore`: never commit it.

### Seed options

```bash
python seed.py                      # fake data (refuses if users already exist)
python seed.py --reset              # DELETE everything, then fake data
python seed.py --admin-only         # real server: only the admin account
python seed.py --admin-pin 482913   # choose the admin PIN (otherwise random, printed once)
```

Fake users are `teacher1`-`teacher5` and `student1`-`student10`, all with PIN `1234`.
Their steps and moods are **random**: never show them as evidence of impact.

### Test the API with curl (Git Bash on Windows)

```bash
TOKEN=$(flask --app devapp show-token student1)
SERVER=http://127.0.0.1:5000        # or https://sohambhongade.pythonanywhere.com

curl -X POST "$SERVER/api/steps" -H "Content-Type: application/json" \
  -d "{\"token\":\"$TOKEN\",\"steps\":8423,\"source\":\"ios_shortcut\"}"
# {"ok":true,"tier":"Silver","weekly_total":41230}

curl -X POST "$SERVER/api/steps" -H "Content-Type: application/json" \
  -d '{"token":"wrong","steps":1,"source":"manual"}'
# {"error":"invalid token","ok":false}   (401)
```

`date` is optional (default: today in Dubai). Dates may be up to 7 days ago, never in the future.

### Put it online (PythonAnywhere, free plan)

Account: `SohamBhongade`. Address: **https://sohambhongade.pythonanywhere.com**.
Below, `/home/SohamBhongade` is the account's home folder (capital letters matter).

1. **Upload the code.** Files tab -> upload `strideboard.zip` to `/home/SohamBhongade`.
   Then open a **Bash** console (Consoles tab) and run:
   ```bash
   cd ~ && unzip -o strideboard.zip && mkdir -p ~/strideboard-data
   ```
   (With GitHub instead: `git clone <repo-url> ~/strideboard`.)
   The database lives in `~/strideboard-data`, **outside** the code folder, so uploading
   new code never overwrites real data.

2. **Make the virtualenv** (same Bash console):
   ```bash
   mkvirtualenv --python=/usr/bin/python3.13 strideboard
   pip install -r ~/strideboard/requirements.txt
   ```
   If 3.13 is not offered, use the newest 3.10+ version, and pick the same one in step 4.

3. **Settings for the console.** Make a secret key and save both settings so they load
   every time you run `workon strideboard`:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"     # copy the output
   echo 'export STRIDEBOARD_DATABASE=/home/SohamBhongade/strideboard-data/strideboard.sqlite3' >> ~/.virtualenvs/strideboard/bin/postactivate
   echo 'export STRIDEBOARD_SECRET_KEY=PASTE_THE_KEY_HERE' >> ~/.virtualenvs/strideboard/bin/postactivate
   deactivate && workon strideboard
   ```

4. **Create the web app.** Web tab -> "Add a new web app" -> "Manual Configuration" ->
   the same Python version. In the **Virtualenv** section enter `strideboard`.

5. **Edit the WSGI file** (link near the top of the Web tab). Delete everything and paste:
   ```python
   import os
   import sys

   os.environ["STRIDEBOARD_SECRET_KEY"] = "PASTE_THE_SAME_KEY_HERE"
   os.environ["STRIDEBOARD_DATABASE"] = "/home/SohamBhongade/strideboard-data/strideboard.sqlite3"

   path = "/home/SohamBhongade/strideboard/server"
   if path not in sys.path:
       sys.path.insert(0, path)

   # Use the full website once Agent 3's app.py exists; until then, only the API.
   if os.path.exists(os.path.join(path, "app.py")):
       from app import app as application
   else:
       from devapp import app as application
   ```
   Never commit or share this file: it contains the secret key.

6. **Create the database.** In the Bash console:
   ```bash
   workon strideboard && cd ~/strideboard/server
   python seed.py                     # testing phase: fake data so Agent 2 can test phones
   # Before real users join:  python seed.py --reset --admin-only
   ```
   Write down the admin PIN it prints.

7. **Turn on HTTPS only and start.** Web tab: switch on **Force HTTPS**, then click
   **Reload**. Open the address: it should say "StrideBoard API is running".

8. **Test from a laptop** with the curl commands above (`SERVER=https://sohambhongade.pythonanywhere.com`).
   Get a token in the PythonAnywhere console: `flask --app devapp show-token student1`.

**Keep it alive:** free web apps stop after one month. Log in and click the button on the
Web tab that runs the app for another month, at least once a month and before the demo.

**After uploading new code:** click **Reload** on the Web tab. Run `python -m pytest tests -q`
in the console first if you changed Agent 1's files.

**Monday goal updates:** the free plan has no scheduled tasks, so the first request of each
week updates everyone's adaptive goal automatically. `flask --app devapp update-goals` does
it by hand.

### For Agent 3: using the data layer

```python
import api, data, db
db.init_app(app)                     # tables, connection cleanup, weekly goals, flask commands
app.register_blueprint(api.bp)       # POST /api/steps

conn = db.get_db()                   # inside a request
today = db.local_today()             # Dubai date: never date.today()
user = data.authenticate(conn, username, pin)          # dict or None
info = data.dashboard(conn, user["id"], today)
board = data.leaderboard(conn, "teacher", today)       # teacher|student|department|effort|improvement
```

Every function raises `ValueError` with a sentence you can show the user. All functions,
names and return shapes are exactly as in the shared brief, plus these notes:

- `weekly_wrapup` also returns `daily_goal` (handy for a goal line on the chart).
  `change_percent` compares Monday-to-today with the **same days** last week, so it is fair
  mid-week; `last_week` is last week's full total. The improvement board works the same way.
- Person leaderboards leave out people with 0 steps this week. Department averages count
  them as 0. Admins never appear.
- `history` returns the days oldest first; days without data have `steps: 0, source: None`.
- `save_steps(..., today=None)`, `suggested_distance_target(..., today=None)` and
  `impact_stats(..., today=None)` take an optional `today` (only needed in tests).
- If you add CSRF protection (e.g. Flask-WTF), exempt `api.bp`: phones cannot send a CSRF token.
- PINs and tokens are never logged. Show the token only on the user's own Settings page.

---

## Agent 2: phone step fetchers

*(Agent 2 writes this section.)*

## Agent 3: website

*(Agent 3 writes this section.)*
