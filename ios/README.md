# StrideBoard — iPhone Setup (Shortcuts)

StrideBoard has no native iPhone app. Instead, you'll build a **Shortcut** (a small automation
in Apple's free Shortcuts app) that reads your daily step count from Apple Health and sends it
to the StrideBoard server automatically, twice a day. You'll also install the website itself
as a home-screen app (a PWA) — see the "Install the website" section at the bottom.

This takes about 10 minutes to set up once, and then runs by itself.

---

## Quick setup (students and teachers start here)

The Shortcut is already built. You don't need to build anything.

**You need:**
- An **iPhone** (an iPad doesn't count steps on its own).
- The **Apple Health** app (the white app with a red heart). It comes with every iPhone. If you
  deleted it, download **Health** from the App Store.
- The **Shortcuts** app. It also comes with every iPhone, or download **Shortcuts** from the App Store.
- A StrideBoard account.

**Steps:**
1. Log in to StrideBoard in Safari, open **Settings**, tap **Get the iPhone Shortcut**, then
   **Add Shortcut**. (The file is `server/static/ios/Strideboard.shortcut`, signed on a Mac so
   iPhones accept it.) If you already have an old **Strideboard** Shortcut, delete it first.
2. Open the StrideBoard website in Safari, log in, and on **Home** tap **Sync from Apple Health**.
3. The first time, tap **Allow** so the Shortcut can read **Steps** from Apple Health.
4. Done. Tap **Sync from Apple Health** any time you want fresh numbers.

Don't rename the Shortcut: the Sync button looks for the name **Strideboard**.

**What the Shortcut does (5 actions, nothing to type):** finds today's Steps in Apple Health,
adds them up, sends them to `POST /api/steps` with the token the Sync button passes in, reads the
server's `message`, and shows it as a notification (for example "Synced 6,350 steps. This week:
22,950 (Bronze)."). It never opens the website, so it can't log you out.

**To change it later:** the team rebuilds the file with a script, then signs it on a Mac:
`shortcuts sign -m anyone -i Strideboard-unsigned.shortcut -o Strideboard.shortcut`.

The rest of this guide explains how the Shortcut was built, for the team.

---

## Part 1: Build the Shortcut

You only need to do this once if you're the team member building it — after that, you'll share
it with everyone else on the team as a link (see Part 2).

### Step 1 — Create a new Shortcut
1. Open the **Shortcuts** app (built into iOS).
2. Tap **+** (top right) to create a new shortcut.
3. Tap the name at the top and rename it **Strideboard**.

### Step 2 — Add the two variables (Token and Server)
These hold your personal login token and the server address, so you only have to type them once.

1. Tap **+ Add Action**, search for **Text**, add a **Text** action. Leave it empty for now —
   you'll fill it in Part 2 when you first set up the Shortcut on your own phone.
2. Tap the **⋯** menu on that Text action → **Rename** → call it `Token`.
   (Under the hood this uses Shortcuts' "Ask for Input"/Import Question setup — see Step 8.)
3. Repeat: add a second **Text** action, rename it `Server`. This holds the server's web
   address with **no trailing slash**: type exactly `https://sohambhongade.pythonanywhere.com`
   (not `https://sohambhongade.pythonanywhere.com/`).

> You'll come back and wire these up properly as "Import Questions" in Step 8, so that when you
> share this Shortcut with teammates, each person is prompted to paste in their *own* token the
> first time they run it.

### Step 3 — Figure out "yesterday at midnight"
We want today's steps **and** yesterday's steps (in case some of yesterday's steps synced late).
So we need a date variable for "the start of yesterday."

1. Add an **Adjust Date** action.
   - Date: **Current Date**
   - Adjust: **Subtract 1 Day**
2. Add a **Get Start of Day** action (sometimes called "Start of Day" under Date actions), and
   feed it the result of the Adjust Date action above (tap into the field and pick the magic
   variable).
3. Rename this result **Start** (tap the output chip → Rename, or rename the action itself) so
   you can find it later.

You now have a date variable called **Start** = yesterday at 12:00 AM.

### Step 4 — Find your step data
1. Add a **Find Health Samples where** action.
   - Type: **Steps**
   - Condition: **Start Date is after `Start`** (use the Start variable from Step 3)
   - Sort: **Start Date**, **Oldest First**
   - Group By: **Day**

   The "Group By Day" setting matters: it adds up all your step sources (phone + Apple Watch)
   into **one number per day**, so you don't double-count steps your watch and phone both saw.
   Without this, you may get inflated totals.

2. This gives you a list of "Health Sample" items, one per day (yesterday and today).

### Step 5 — Repeat for each day and send it
1. Add a **Repeat with Each** action, using the list from Step 4 as the input.
2. Inside the repeat, add:
   - **Get Details of Health Sample** → **Value** → rename this `StepsValue`.
   - **Round Number** on `StepsValue` (round to nearest whole number — Health sometimes
     returns decimals).
   - **Get Details of Health Sample** → **Start Date** → rename this `SampleDate`.
   - **Format Date**: input `SampleDate`, Date Format → **Custom**, Format string: `yyyy-MM-dd`.
     Rename this result `DateString`.
3. Still inside the repeat, add an **If** action: **Rounded Number** **is greater than** `0`.
   Everything in the next step goes *inside* this If (between "If" and "Otherwise").
   This rule comes from the shared brief: phones must never send a 0 total, so a day where
   someone typed their steps in by hand on the website is never wiped out by an empty upload.
   Delete the empty "Otherwise" section if you like.
4. Inside the If, add **Get Contents of URL**:
   - URL: `Server` + `/api/steps` — i.e. tap the field, insert the `Server` variable, then type
     `/api/steps` right after it. It should look like `{Server}/api/steps`.
   - Method: **POST**
   - Headers: `Content-Type` = `application/json`
   - Request Body: **JSON**, with these fields:
     | Key | Value |
     |---|---|
     | `token` | the `Token` variable |
     | `date` | the `DateString` variable |
     | `steps` | the rounded `StepsValue` (Number, not text) |
     | `source` | `ios_shortcut` (typed literally) |

That's the whole data flow: for each of the last two days, round the step count, format the
date, and (if it isn't 0) POST it.

> **Time zone note:** "start of day" uses the iPhone's own time zone. Phones set to UAE time
> match the server (Asia/Dubai). A phone set to another time zone would send slightly shifted
> days.

### Step 6 — (Optional but recommended) Show a result
After the Repeat with Each, add a **Show Notification** action saying something like
"StrideBoard synced ✅" so you get quiet confirmation it ran, especially for the automated runs.

### Step 7 — Test it manually
1. Tap the **Play** button at the bottom of the Shortcuts editor.
2. The first time, iOS will ask for **permission to read your Health data** — allow **Steps**.
3. Check the notification/result. If something failed, see the **Troubleshooting** table below.

### Step 8 — Turn Token and Server into Import Questions
This is what lets you **share one Shortcut with your whole team**, and have each person enter
their own token without editing the Shortcut itself:

1. Tap the **Shortcut Details** (ⓘ) icon at the top.
2. Under **Setup**, tap **Add New Question**.
3. Add a question for `Token`: prompt text like "Paste your StrideBoard token" → set as the
   default value for the `Token` text action from Step 2.
4. Repeat for `Server`, with a prompt like "StrideBoard server address" and
   `https://sohambhongade.pythonanywhere.com` as the default (so most people can just tap through).

Now when someone imports this Shortcut via your shared link, Shortcuts will prompt them to fill
in their own Token the first time, and the value sticks after that.

### Step 9 — Automate it (run without opening the app)
1. In the Shortcuts app, go to the **Automation** tab → **+** → **Create Personal Automation**.
2. Choose **Time of Day** → set it to **21:30**, Daily → **Next** → **Add Action** → search for
   your **Strideboard** shortcut → add it.
3. Turn **off** "Ask Before Running" if you want it fully silent, and make sure
   **Run Immediately** is selected (not "Notify Me," which requires you to tap to confirm).
4. Repeat for a second automation at **07:00**.

Two runs a day (morning and night) means even if one fails silently, the other catches most of
the day's steps.

### Step 10 — The "Sync from Apple Health" button on the website
On an iPhone, the website's dashboard shows a **Sync from Apple Health** button. It runs this
Shortcut by its name (`shortcuts://run-shortcut?name=Strideboard`), so **keep the name
exactly `Strideboard`**. After it runs, tap the back arrow at the top left; the dashboard
reloads with the new steps.

Why the button matters: iPhones lock Health data while the phone is locked, so a timed
automation that fires while the phone is in a pocket usually can't read the steps. The button is
pressed while the phone is unlocked, so it always works. The timed runs are the backup.

---

## Part 2: Share the Shortcut with the team

1. Open the finished **Strideboard** shortcut, tap the **⋯** menu, then the **Share**
   icon, then **Add to iCloud Drive / Copy iCloud Link**.
2. Share that link with teammates (group chat, email, whatever's easiest).
3. Each person opens the link, taps **Get Shortcut**, and on first run will be asked to paste in
   their own Token (Step 8 above) and confirm the Server address.
4. Each person then sets up their own two automations (Step 9) — this part can't be shared, it
   has to be done once per phone.

**Where does each person get their Token?** From the StrideBoard website: log in, go to
**Settings**, and the token is shown there with a copy button.

---

## Part 3: Testing

Compare what the Shortcut sends against the iPhone's own **Health app**:

1. Open **Health** → **Browse** → **Activity** → **Steps**.
2. Tap on **Today** or a specific day to see the exact total Apple recorded.
3. Run the Shortcut manually (Part 1, Step 7) and check the server accepted the same number
   (ask whoever owns the server/database to confirm, or check the Settings page once the
   website shows recent entries).

**Testing before real users exist:** Agent 1 can give you a test token (for `student1`). Test
users are fake and will be deleted before real use, so the test token stops working then and
everyone pastes their own. Never put a token in a screenshot, a chat group or GitHub.

**Common errors:**

| What you see | Likely cause | Fix |
|---|---|---|
| `401` / "invalid token" | Token wasn't pasted correctly, or has a stray space | Re-copy the token from `/settings` on the website, re-run the Import Question |
| `400` / "steps out of range" | Health returned a number above 100,000 for one day | Check the Health app for that date (usually a duplicate source or a bad import) |
| `400` / "source" error | The `source` field was typed wrong | It must be exactly `ios_shortcut`, all lowercase |
| `400` / "invalid date" | Date more than 7 days old or in the future | Shouldn't happen with this setup since we only ever send yesterday/today |
| Shortcut fails with no Health data | Health permission wasn't granted | Settings app → Privacy & Security → Health → Strideboard → turn on Steps |
| "Could not connect to server" | Server address wrong, or server is down | Double-check the `Server` value has no typo and no trailing slash |

---

## Honest limits (tell your judges this too)

- **This is not continuous background tracking.** It runs twice a day, on a schedule. If your
  phone is off, in Airplane Mode, or Shortcuts' automation silently fails to fire (this
  happens occasionally on iOS, outside our control), that sync is simply missed until the next
  one.
- **Health data is locked while the iPhone is locked.** A timed run that fires while the phone
  is locked usually can't read the steps, so that run is missed. The dashboard's **Sync from
  Apple Health** button (Step 10) fixes this. Timed runs can also be skipped in Low Power Mode or
  with Background App Refresh disabled for Shortcuts. If syncs seem to stop, check Settings → General → Background App
  Refresh → Shortcuts is **on**.
- **No live/real-time updates.** The leaderboard reflects whatever the last successful sync
  sent, not your steps right now. Use the **Sync now** option (manually running the Shortcut)
  before checking your rank if you want it fresh.
- If you skip this setup entirely, you can still participate — use the **manual entry form**
  on the website's `/log` page.

---

## Install the website as an app (PWA)

The website itself works like an app once installed:

1. Open the StrideBoard website in **Safari** (must be Safari, not Chrome, for this to work).
2. Tap the **Share** icon (square with an arrow).
3. Scroll down and tap **Add to Home Screen**.
4. Confirm the name, tap **Add**.

It now appears as an icon on your home screen and opens full-screen, like a normal app.
