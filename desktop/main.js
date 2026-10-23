// StrideBoard Leaderboard: a window that shows only this week's Students and Teachers
// leaderboards from the StrideBoard website (the /board page), refreshing every minute.
// It asks for the screen code once (Admin -> Leaderboard screen) and remembers it.
const { app, BrowserWindow, Menu, ipcMain, nativeTheme, powerSaveBlocker, screen, shell } = require("electron");
const fs = require("fs");
const path = require("path");

const SITE = process.env.STRIDEBOARD_SITE || "https://strideboard.pythonanywhere.com";   // the env var is for testing
const settingsFile = () => path.join(app.getPath("userData"), "settings.json");
let win = null;

// settings.json: { code, bounds: {x, y, width, height}, fullScreen }
function readSettings() {
  try { return JSON.parse(fs.readFileSync(settingsFile(), "utf8")) || {}; } catch (e) { return {}; }
}
function writeSettings(changes) {
  const next = Object.assign(readSettings(), changes);
  fs.mkdirSync(path.dirname(settingsFile()), { recursive: true });
  fs.writeFileSync(settingsFile(), JSON.stringify(next));
}
function readCode() { return readSettings().code || ""; }
function saveCode(code) { writeSettings({ code }); }

// A window that was on a screen that's no longer plugged in comes back on the main screen.
function onSomeScreen(b) {
  return b && screen.getAllDisplays().some((d) => {
    const a = d.workArea;
    return b.x + 80 > a.x && b.x < a.x + a.width - 80 && b.y + 40 > a.y && b.y < a.y + a.height - 40;
  });
}

function showBoard() {
  const code = readCode();
  if (!code) return showSetup();
  win.loadURL(`${SITE}/board?key=${encodeURIComponent(code)}`);
}
function showSetup(problem) {
  win.loadFile(path.join(__dirname, "setup.html"), problem ? { query: { problem } } : undefined);
}

function createWindow() {
  const saved = readSettings();
  const bounds = onSomeScreen(saved.bounds) ? saved.bounds : { width: 1280, height: 760 };
  win = new BrowserWindow({
    ...bounds, minWidth: 480, minHeight: 360, fullscreen: !!saved.fullScreen,
    show: false,                       // appear only once painted: no white flash on start
    backgroundColor: "#0A1222", title: "StrideBoard Leaderboard", autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false,
                      sandbox: true, spellcheck: false },
  });
  win.once("ready-to-show", () => win.show());
  // Only StrideBoard opens inside the window; anything else opens in the normal browser.
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith(SITE) && !url.startsWith("file:")) { event.preventDefault(); shell.openExternal(url); }
  });
  // The website says the code is wrong (or was changed in Admin): ask for it again straight away.
  win.webContents.on("did-navigate", (_e, url, status) => {
    if (url.startsWith(SITE) && status === 403) showSetup("wrong");
  });
  // No internet: wait a moment and try again, rather than leaving an error on the screen.
  win.webContents.on("did-fail-load", (_e, _code, _desc, url) => {
    if (url && url.startsWith(SITE)) setTimeout(showBoard, 15000);
  });
  // Remember the window's size, place and full screen for next time.
  let saveTimer = null;
  const remember = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      if (!win || win.isDestroyed()) return;
      const full = win.isFullScreen();
      writeSettings(full ? { fullScreen: true } : { fullScreen: false, bounds: win.getNormalBounds() });
    }, 400);
  };
  ["resize", "move", "enter-full-screen", "leave-full-screen"].forEach((e) => win.on(e, remember));
  // In full screen the mouse pointer hides itself after a few still seconds (the page does this).
  win.on("enter-full-screen", () => win.webContents.send("full-screen", true));
  win.on("leave-full-screen", () => win.webContents.send("full-screen", false));
  win.webContents.on("did-finish-load", () => win.webContents.send("full-screen", win.isFullScreen()));
  showBoard();
}

ipcMain.handle("save-code", (_event, code) => {
  const clean = String(code || "").trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (clean.length < 6) return false;
  saveCode(clean);
  showBoard();
  return true;
});

function buildMenu() {
  const isMac = process.platform === "darwin";
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(isMac ? [{ role: "appMenu" }] : []),
    {
      label: "Screen",
      submenu: [
        { label: "Reload", accelerator: "CmdOrCtrl+R", click: () => showBoard() },
        { label: "Change screen code…", accelerator: "CmdOrCtrl+K", click: () => showSetup() },
        { type: "separator" },
        { role: "togglefullscreen", accelerator: isMac ? "Ctrl+Cmd+F" : "F11" },
        { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" },
        { type: "separator" },
        isMac ? { role: "close" } : { role: "quit" },
      ],
    },
  ]));
}

// One window only: opening the app again just brings the screen to the front.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
  app.whenReady().then(() => {
    nativeTheme.themeSource = "dark";   // dark title bar on Mac and Windows, to match the board
    // A leaderboard screen should stay on: stop the computer dimming or sleeping the display.
    powerSaveBlocker.start("prevent-display-sleep");
    buildMenu();
    createWindow();
    app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
  });
  app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
}
