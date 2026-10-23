// The setup page can only hand the screen code to the app. On the leaderboard page, the
// mouse pointer hides after 3 still seconds while the window is full screen.
const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("strideboard", {
  saveCode: (code) => ipcRenderer.invoke("save-code", code),
});

let full = false, timer = null;
function idleCursor() {
  if (!document.documentElement) return;
  document.documentElement.style.cursor = "";
  clearTimeout(timer);
  if (full) timer = setTimeout(() => { document.documentElement.style.cursor = "none"; }, 3000);
}
ipcRenderer.on("full-screen", (_e, on) => { full = !!on; idleCursor(); });
window.addEventListener("mousemove", idleCursor);
