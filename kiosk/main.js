const { app, BrowserWindow, globalShortcut, session, ipcMain } = require('electron');
const path = require('path');
const { exec } = require('child_process');

let mainWindow;

// VM Detection function
function checkVM(callback) {
  if (process.platform === 'win32') {
    exec('wmic computersystem get model,manufacturer', (error, stdout, stderr) => {
      if (error) {
        console.warn('WMIC command failed or unavailable. Proceeding in demo mode.', error);
        return callback(false); // Can't detect, assume false
      }
      const output = stdout.toLowerCase();
      const isVM = output.includes('vmware') || 
                   output.includes('virtualbox') || 
                   output.includes('qemu') || 
                   output.includes('bochs') || 
                   output.includes('hyper-v') ||
                   output.includes('innotek'); // VirtualBox manufacturer
      
      if (isVM && process.env.NIVASHA_STRICT_VM === '1') {
        console.error('Virtual Machine detected. Kiosk cannot run in a VM.');
        app.quit();
        return;
      } else if (isVM) {
        console.warn('Virtual Machine detected, but strict mode disabled. Proceeding in demo mode.');
      }
      callback(isVM);
    });
  } else {
    console.warn('Anti-VM check not implemented for this platform.');
    callback(false);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    kiosk: true,
    fullscreen: true,
    alwaysOnTop: true,
    autoHideMenuBar: true,
    frame: false,
    resizable: false,
    minimizable: false,
    maximizable: false,
    skipTaskbar: true,
    backgroundColor: '#0a0e17',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      devTools: false, // Set to false in production
      sandbox: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Loopback Network Isolation
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
    const url = details.url;
    // Allow localhost, 127.0.0.1, local files, and Google Fonts
    if (url.startsWith('http://127.0.0.1:8080') || 
        url.startsWith('http://localhost:8080') || 
        url.startsWith('file://') ||
        url.startsWith('https://fonts.googleapis.com') ||
        url.startsWith('https://fonts.gstatic.com')) {
      callback({ cancel: false });
    } else {
      console.warn(`Blocked request to: ${url}`);
      callback({ cancel: true });
    }
  });
  
  // Disable navigation
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith('file://')) {
      event.preventDefault();
      console.warn(`Blocked navigation to: ${url}`);
    }
  });

  mainWindow.loadFile('index.html');

  // Handle blur event (focus loss)
  mainWindow.on('blur', () => {
    mainWindow.webContents.send('security-event', 'focus_loss');
  });

  mainWindow.on('focus', () => {
    mainWindow.webContents.send('security-event', 'focus_returned');
  });
}

function registerShortcuts() {
  const restrictedKeys = [
    'CommandOrControl+C',
    'CommandOrControl+V',
    'CommandOrControl+X',
    'CommandOrControl+A',
    'CommandOrControl+S',
    'CommandOrControl+P',
    'CommandOrControl+Shift+I',
    'F11',
    'F12',
    'F5',
    'CommandOrControl+R',
    'Alt+Tab',    // Global shortcut might not block OS-level Alt+Tab reliably, but we try
    'Alt+F4',
    'PrintScreen'
  ];

  restrictedKeys.forEach(key => {
    globalShortcut.register(key, () => {
      console.warn(`Blocked shortcut attempt: ${key}`);
      if (mainWindow) {
        mainWindow.webContents.send('security-event', `shortcut_attempt_${key}`);
      }
    });
  });
}

app.whenReady().then(() => {
  checkVM((isVM) => {
    createWindow();
    registerShortcuts();

    app.on('activate', function () {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});
