const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  onSecurityEvent: (callback) => ipcRenderer.on('security-event', (_event, value) => callback(value)),
  reportRendererReady: () => ipcRenderer.send('kiosk-ready'),
  exitTerminal: () => ipcRenderer.send('kiosk-exit'),
  getAppInfo: () => ({ platform: process.platform, version: process.versions.electron })
});
