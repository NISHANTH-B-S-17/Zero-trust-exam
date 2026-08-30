const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  onSecurityEvent: (callback) => ipcRenderer.on('security-event', (_event, value) => callback(value)),
  reportRendererReady: () => ipcRenderer.send('renderer-ready'),
  exitTerminal: () => ipcRenderer.send('exit-terminal'),
  getAppInfo: () => ({ platform: process.platform, version: process.versions.electron })
});
