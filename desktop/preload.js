// The setup page can only do one thing: hand the screen code to the app.
const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("strideboard", {
  saveCode: (code) => ipcRenderer.invoke("save-code", code),
});
