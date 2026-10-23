// StrideBoard Leaderboard: a window that shows only this week's Students and Teachers
// leaderboards from the StrideBoard website (the /board page), refreshing every minute.
// It asks for the screen code once (Admin -> Leaderboard screen) and remembers it.
const { app, BrowserWindow, Menu, ipcMain, shell } = require("electron");
const fs = require("fs");
const path = require("path");

const SITE = process.env.STRIDEBOARD_SITE || "https://strideboard.pythonanywhere.com";   // the env var is for testing
const settingsFile = () => path.join(app.getPath("userData"), "settings.json");
let win = null;

function readCode() {
  try { return JSON.parse(fs.readFileSync(settingsFile(), "utf8")).code || ""; } catch (e) { return ""; }
}
function saveCode(code) {
  fs.mkdirSync(path.dirname(settingsFile()), { recursive: true });
  fs.writeFileSync(settingsFile(), JSON.stringify({ code }));
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
  win = new BrowserWindow({
    width: 1280, height: 760, minWidth: 720, minHeight: 480,
    backgroundColor: "#0A1222", title: "StrideBoard Leaderboard", autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
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

app.whenReady().then(() => {
  buildMenu();
  createWindow();
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
