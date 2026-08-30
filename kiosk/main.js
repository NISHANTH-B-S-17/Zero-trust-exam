const { app, BrowserWindow, globalShortcut, session, ipcMain } = require('electron');
const path = require('path');
const { exec, spawn } = require('child_process');
const http = require('http');

let mainWindow;
let backendProcess = null;

function checkBackendHealth(callback, retries = 30) {
  const req = http.get('http://127.0.0.1:8080/api/v1/health', (res) => {
    if (res.statusCode === 200) {
      callback(true);
    } else if (retries > 0) {
      setTimeout(() => checkBackendHealth(callback, retries - 1), 250);
    } else {
      callback(false);
    }
  });

  req.on('error', () => {
    if (retries > 0) {
      setTimeout(() => checkBackendHealth(callback, retries - 1), 250);
    } else {
      callback(false);
    }
  });
}

function startBackendServer(callback) {
  checkBackendHealth((alreadyRunning) => {
    if (alreadyRunning) {
      console.log('Backend is already running on port 8080.');
      return callback();
    }

    console.log('Starting local backend process...');
    const rootDir = path.resolve(__dirname, '..');
    
    // Set PYTHONPATH so python can locate the backend/app package
    const env = Object.assign({}, process.env, {
      PYTHONPATH: path.join(rootDir, 'backend') + (process.platform === 'win32' ? ';' : ':') + (process.env.PYTHONPATH || '')
    });

    backendProcess = spawn('python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8080'], {
      cwd: path.join(rootDir, 'backend'),
      env: env,
      stdio: 'ignore',
      windowsHide: true
    });

    backendProcess.on('error', (err) => {
      console.error('Failed to spawn python backend:', err);
    });

    checkBackendHealth((success) => {
      if (success) {
        console.log('Backend successfully started and health check passed.');
      } else {
        console.warn('Backend process started but health check timed out.');
      }
      callback();
    });
  });
}

// VM Detection function
function checkVM(callback) {
  if (process.platform === 'win32') {
    const powershellCmd = 'Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object -ExpandProperty Model';
    exec(`powershell -NoProfile -Command "${powershellCmd}"`, (error, stdout, stderr) => {
      let isVM = false;
      if (!error && stdout) {
        const output = stdout.toLowerCase();
        isVM = output.includes('vmware') || 
               output.includes('virtualbox') || 
               output.includes('qemu') || 
               output.includes('bochs') || 
               output.includes('hyper-v') ||
               output.includes('virtual');
      }
      if (isVM && process.env.NIVASHA_STRICT_VM === '1') {
        console.error('Virtual Machine detected. Kiosk cannot run in a VM.');
        app.quit();
        return;
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
    const currentUrl = mainWindow.webContents.getURL();
    if (url === currentUrl || url.split('#')[0] === currentUrl.split('#')[0]) {
      return;
    }
    if (!url.startsWith('file://')) {
      event.preventDefault();
      console.warn(`Blocked navigation to: ${url}`);
    }
  });

  // Disable devTools in production, warn if open
  mainWindow.webContents.on('devtools-opened', () => {
    mainWindow.webContents.send('security-event', 'devtools_opened');
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

ipcMain.on('exit-terminal', () => {
  if (backendProcess) {
    try { backendProcess.kill(); } catch (e) {}
  }
  app.quit();
});

app.whenReady().then(() => {
  startBackendServer(() => {
    checkVM((isVM) => {
      createWindow();
      registerShortcuts();

      app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
      });
    });
  });
});

app.on('window-all-closed', function () {
  if (backendProcess) {
    try { backendProcess.kill(); } catch (e) {}
  }
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});
