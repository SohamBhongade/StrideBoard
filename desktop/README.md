# StrideBoard Leaderboard (Windows and Mac)

A small desktop app that shows only the **Students** and **Teachers** leaderboards from
the StrideBoard website, big enough for a school TV or a laptop on a stand. It refreshes every
minute and keeps the last boards on screen if the Wi-Fi drops.

**Choose the time:** the dropdown at the top switches between **Today**, **This week**, **This month**
and **All time**. The app remembers your choice next time it opens. **Find someone:** type in the
search box to filter both boards as you type; press Enter to search everyone, not just the top 8
(each person keeps their real rank).

**Download:** Admin → Leaderboard screen on the website, or the
[leaderboard-app-latest release](https://github.com/SohamBhongade/StrideBoard/releases/tag/leaderboard-app-latest):
`StrideBoard-Leaderboard.exe` (Windows: a one-click installer that adds Start menu and desktop shortcuts) and `StrideBoard-Leaderboard.dmg` (Mac).

**Made for a screen that's always on:** keeps the display awake (no dimming or sleep), remembers its
window size, place and full screen, hides the mouse pointer after 3 still seconds in full screen,
scrolls in small windows, keeps the last boards if the Wi-Fi drops, and asks for the screen code
again if it's wrong or was changed in Admin.

**First run:** type the 10-character screen code from Admin → Leaderboard screen. Change it later
with Screen → Change screen code (Ctrl/Cmd+K). Full screen: F11 on Windows, Ctrl+Cmd+F on Mac.

**Not signed by Microsoft or Apple** (a school project), so the first launch needs one extra click:
- Windows: "Windows protected your PC" → **More info** → **Run anyway**. It installs in a few
  seconds (no admin rights needed) and opens; after that use the Start menu or desktop shortcut.
  Uninstall from Settings → Apps like any other app.
- Mac: open the .dmg, drag the app to Applications, then **right-click the app → Open → Open**.

Built automatically by GitHub Actions (`.github/workflows/leaderboard-app.yml`) whenever this
folder changes. To build by hand: `npm install` then `npm run dist` on the matching computer.
