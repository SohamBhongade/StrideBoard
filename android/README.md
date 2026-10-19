# StrideBoard — Android app

One small app (`com.strideboard.app`) that does two jobs:

1. **Shows the StrideBoard website** full screen, like a normal app (back button, offline
   screen, outside links open in the browser).
2. **Sends your daily step totals automatically.** It reads yesterday's and today's totals from
   **Health Connect** (Android's shared health store) and posts them to `POST /api/steps`.

It is shared as an APK file (sideloaded), not through the Play Store.

---

## ⚠️ What has and hasn't been tested

Be honest about this with the judges and the team.

| Part | Status |
|---|---|
| Kotlin code, layouts, manifest | **Written but not compiled.** The build computer used to write it couldn't reach Google's servers, so the first real build happens in Android Studio on your computer. Expect maybe one or two small fixes (see "If the build fails"). |
| XML files | Checked: all well-formed. |
| Request format sent to the server | Matches the shared brief. Tested against `tools/fake_api.py` (the stand-in server), not yet against Agent 1's real server. |
| Health Connect reading, permissions, background sync | **Not tested on a phone yet.** Must be tested on a real Android phone before you claim it works in the demo. |
| Library versions | Checked against developer.android.com on 15 Oct 2026 (latest stable). |

**Versions used:** Android Gradle Plugin 9.4.0 · Gradle 9.6.0 · Health Connect `connect-client`
1.1.0 · WorkManager 2.11.2 · `activity` 1.13.0 · `core` 1.19.1 · `lifecycle` 2.11.0 ·
compileSdk 37 · targetSdk 36 · minSdk 26.
Kotlin is built into AGP 9, so there is no separate Kotlin plugin line.

---

## How it works

```
Health Connect ──(yesterday + today totals, Dubai days)──▶ app ──POST /api/steps──▶ StrideBoard server
```

- **Sync reads** `StepsRecord.COUNT_TOTAL` with `aggregate()`, which combines phone, watch and
  other apps **without double counting**. Days run midnight to midnight **Dubai time**, the same
  as the server, even if the phone is set to another time zone.
- A day with **0 steps is never sent**, so a number someone typed on the website isn't wiped out.
- Each day is sent as `{"token", "date": "YYYY-MM-DD", "steps", "source": "android_app"}`.
- **When it syncs:**
  - in the background about **every 3 hours**, plus once **around 23:30** (only on phones that
    allow background reads; needs internet);
  - every time the app is **opened** (at most once every 15 minutes), which covers phones
    without background reads;
  - when you tap **Sync now**.
- Network problems are retried automatically (up to 3 times per run). A wrong token (401) or a
  refused entry (400) is **not** retried; it shows on the setup screen instead.
- Release builds talk to **https://** addresses only. Debug builds also allow **http://** so you
  can test against a laptop.
- The token is stored privately on the phone, never logged, and excluded from backups.

### Files

| File | What it does |
|---|---|
| `app/src/main/AndroidManifest.xml` | Permissions (internet, read steps, background read), Health Connect privacy entries, screens |
| `MainActivity.kt` | Website in a WebView, sync banner, offline screen, sync-on-open |
| `SetupActivity.kt` | Address, token, "Allow step access", Sync now, last sync result |
| `PrivacyActivity.kt` | Privacy screen (Health Connect links to it) |
| `StepReader.kt` | Health Connect: availability, permissions, read yesterday + today |
| `ApiClient.kt` | Sends one day to `/api/steps` and understands the answer |
| `SyncRunner.kt` | One full sync: read, skip zeros, send, save the result message |
| `SyncWorker.kt` | Background job + schedule (every 3 h, nightly ~23:30) |
| `Prefs.kt` | Saved settings and last sync status |
| `Insets.kt` | Keeps content clear of the status bar, navigation bar and keyboard |
| `tools/fake_api.py` | Stand-in server for testing before the real one is ready |

---

## 1. Build it in Android Studio

1. Install the latest **Android Studio** (free, from developer.android.com/studio).
2. **File → Open** and choose the `android` folder (not the whole repo).
3. Wait for **Gradle sync** to finish. The first time it downloads a lot, which can take 10 to 20
   minutes on school Wi-Fi.
   - If it asks to install **SDK Platform 37** or **Build Tools**, click the link to install.
4. Plug in an Android phone with **USB debugging** on (Settings → About phone → tap
   *Build number* 7 times → Developer options → USB debugging), or start an emulator.
5. Press the green **Run ▶** button. This installs a **debug** build on the phone.

## 2. Make the APK to share

Use the **release** build for real users (https only):

- **Build → Generate App Bundles or APKs → Generate APKs**, or in the Terminal tab:
  ```
  ./gradlew assembleRelease        (Windows: gradlew.bat assembleRelease)
  ```
- The file appears at `app/build/outputs/apk/release/app-release.apk`. Rename it to
  something like `StrideBoard-1.0.apk`.

**Important: always build on the same computer.** The APK is signed with that computer's
built-in debug key, so no keystore is needed. Phones only accept an **update** signed with the
same key. If an APK built on a different computer is installed over an old one, it fails with
"App not installed"; the user must uninstall the old app first. Choose one team computer as
"the APK computer".

For each new version, increase `versionCode` (and `versionName`) in `app/build.gradle.kts`.

**Don't commit the APK to git** (`.gitignore` already blocks it). Share it through Google Drive,
or have Agent 3 host it on the website.

## 3. Install and set up on each phone

1. Open the APK link on the phone and download it. When Android asks, allow the browser or Files
   app to **install unknown apps**. If Play Protect warns about an unknown developer, tap
   **More details → Install anyway**. That warning is normal for apps outside the Play Store.
2. **Check Health Connect:**
   - **Android 14 or newer:** it is built in (Settings → search "Health Connect").
   - **Android 9–13:** install **Health Connect** from the Play Store. The app's
     "Allow step access" button opens the right page.
   - **Samsung phones:** open **Samsung Health → Settings → Health Connect** and allow Samsung
     Health to share Steps. Otherwise Samsung's step counts never reach Health Connect.
   - **Other step apps** (Google Fit, Fitbit, Xiaomi/Mi Fitness, Huawei Health): turn on their
     Health Connect sharing too, if the phone has one of them.
3. Open **StrideBoard**. The setup screen appears first:
   1. **Website address** — already filled in: `https://sohambhongade.pythonanywhere.com`.
   2. **Token** — log in on the website → Settings → copy the token → paste it here.
   3. **Allow step access** → turn on **Steps**. If the phone offers **"Access data in the
      background"** (or similar), allow that too. Background sync needs it.
   4. **Sync now** → you should see "✓ Sent: Yesterday … · Today …".
   5. **Open StrideBoard**.
4. **Battery settings** (see section 5): set the app to *Unrestricted*.

The bar at the top of the website shows "Steps synced 12 minutes ago". If it turns orange,
tap it to see what's wrong.

## 4. Testing

### A. Before the real server exists: the fake server
1. On a laptop on the **same Wi-Fi** as the phone:
   ```
   python3 tools/fake_api.py            # token is "test-token"
   ```
2. Find the laptop's IP address (`ipconfig` on Windows, `ifconfig` or System Settings on Mac),
   e.g. `192.168.1.20`.
3. Install a **debug** build (Run ▶ in Android Studio). Release builds refuse http.
4. In the app: address `http://192.168.1.20:5050`, token `test-token`, then **Sync now**.
5. The laptop prints `ACCEPTED: 2026-10-15 8423 steps from android_app`. Open
   `http://192.168.1.20:5050` in a browser to see a table of uploads.
   (The website view will be blank or basic. That's expected, since the fake server has no website.)
6. Try a wrong token: the app should say the token was not accepted, without retrying.

If the phone can't connect, the laptop's firewall is usually blocking port 5050. Allow
Python through the firewall, or use a phone hotspot.

### B. On a real phone with the real server
The live server is `https://sohambhongade.pythonanywhere.com`. Until Agent 3 uploads the
website, its home page only says "StrideBoard API is running", so the app shows that line
instead of the website. Uploads already work.

- **Test token:** Agent 1 sends `student1`'s token privately. Paste it in the app and tap
  **Sync now**. You should see "✓ Sent: … This week: … (Bronze)" or similar. Never put a
  token in a screenshot, a chat group or GitHub. The app hides it with dots.
- **Wrong token:** change one letter and tap **Sync now**. The app should say the token was not
  accepted, without retrying.
- The test users are fake and will be deleted before real use. After that the test token stops
  working ("token not accepted"), and each person pastes their own real token.
- Compare the app's numbers with the phone's own step app (Samsung Health, Google Fit, or
  Health Connect → Data and access → Activity → Steps). Expect small differences only if a
  source synced into Health Connect late. The next sync fixes that.
- Test the most important rule: on the website, type a manual entry for **today**, then make
  sure a phone with 0 steps today does **not** overwrite it.
- Turn on Airplane Mode → open the app → you should see the offline screen with **Try again**.
- Tap a link to another website → it should open in Chrome, not inside the app.

### C. On the emulator (no real steps)
Install Google's **Health Connect Toolbox** (search "Health Connect Toolbox" on
developer.android.com) on the emulator to add fake step records, then tap **Sync now**.
Use an emulator image with Android 14 or newer (Health Connect is built in).

### D. Checking background sync
- In Android Studio: **View → Tool Windows → App Inspection → Background Task Inspector**.
  You should see two `SyncWorker` jobs ("every 3 hours" and "nightly") once step access and
  background access are allowed.
- Leave the phone alone for a few hours, then check the time on the banner.
- If the setup screen says *"This phone doesn't support background reading"*, there are no
  background jobs. The app syncs each time it's opened. Tell users to open it once in the
  evening.

## 5. Battery-saver advice (important)

Many phones stop background jobs to save battery, especially Xiaomi, Redmi, POCO, Huawei,
Honor, Oppo, Realme, Vivo and some Samsung phones.

- **All phones:** Settings → Apps → StrideBoard → Battery → **Unrestricted** (or "Don't optimise").
- **Samsung:** Settings → Battery → Background usage limits → make sure StrideBoard is **not**
  in "Sleeping apps" or "Deep sleeping apps".
- **Xiaomi / Redmi / POCO:** Settings → Apps → StrideBoard → turn on **Autostart**, and set Battery
  saver to **No restrictions**.
- **Huawei / Honor:** Settings → Battery → App launch → StrideBoard → **Manage manually**, all on.
- Phone-by-phone guides: **dontkillmyapp.com**.

Even if a phone blocks background jobs completely, opening the app once a day still syncs.

## 6. If the build fails

The code hasn't been compiled yet, so a first build may show an error. Most fixes are one line.

| Error message (roughly) | Fix |
|---|---|
| `Minimum supported Gradle version is X` | Edit `gradle/wrapper/gradle-wrapper.properties` and change `gradle-9.6.0` to the version it names. |
| `Plugin [id: 'com.android.application', version: '9.4.0'] was not found` or Android Studio says the AGP is too new | Update Android Studio. Or change `9.4.0` in `build.gradle.kts` to the newest version your Android Studio offers (the Upgrade Assistant suggests it). |
| `Dependency ... requires compileSdk 3X` | Change `compileSdk` in `app/build.gradle.kts` to that number and install that SDK platform when asked. |
| `Failed to find target with hash string 'android-37'` | Tools → SDK Manager → install Android SDK Platform 37 (or set `compileSdk = 36`). |
| `Unresolved reference: features` or `HealthConnectFeatures` | The Health Connect library version is too old. Make sure it's `connect-client:1.1.0`. |
| Something about `kotlin-android` / `org.jetbrains.kotlin.android` | Don't add that plugin. AGP 9 has Kotlin built in. |
| `Unsupported class file major version` / JDK errors | Settings → Build Tools → Gradle → Gradle JDK → choose the bundled **jbr-21**. |
| A Kotlin error in one file | Paste the full error message to your AI helper along with that file. Errors are usually a renamed method in a newer library. |
| "App not installed" on the phone | Uninstall the old StrideBoard app first (different signing computer, see section 2). |

After any change: **File → Sync Project with Gradle Files**, then build again.

---

## Text for the website's Settings page (for Agent 3)

Agent 3 can paste this onto `/settings` under the user's token. Replace the two placeholders.

> **Sync your steps automatically**
>
> **iPhone**
> 1. On your iPhone, open this link and tap **Add Shortcut**: `[ICLOUD_SHORTCUT_LINK]`
> 2. When asked, paste your token (shown above) and confirm the website address.
> 3. Open the **Shortcuts** app, tap **StrideBoard Sync** once, and allow access to **Steps**.
> 4. Make it automatic: Shortcuts → **Automation** → **+** → **Time of Day** → 21:30, Daily →
>    **Run Immediately** → choose **StrideBoard Sync**. Add a second one at 07:00.
> 5. To add this website to your home screen: in **Safari** tap **Share → Add to Home Screen**.
>
> **Android**
> 1. Download and install the StrideBoard app: `[APK_DOWNLOAD_LINK]`
>    (allow "install unknown apps" if your phone asks).
> 2. Open it, type this website's address, and paste your token (shown above).
> 3. Tap **Allow step access** and turn on **Steps** (and background access, if offered).
> 4. Tap **Sync now**, then **Open StrideBoard**.
> 5. Samsung phones: in **Samsung Health → Settings → Health Connect**, allow Steps to be shared.
>
> Steps can only come from a phone; there is no way to type them in on the website.

**Optional for Agent 3:** the app adds `StrideBoardAndroid/1.0` to its browser user agent. The
website can check for it, for example to hide the "Add to Home Screen" hint inside the app.
