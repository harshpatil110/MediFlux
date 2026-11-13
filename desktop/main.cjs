/**
 * MediFlux Desktop Main Process.
 * Manages native window lifecycle, single-instance locking, system tray, application menu,
 * and IPC native notification dispatcher.
 */

const { app, BrowserWindow, Menu, Tray, ipcMain, shell, Notification } = require("electron");
const path = require("path");

let mainWindow = null;
let tray = null;

// 1. Single-Instance Lock Enforcement
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", (_event, commandLine, _workingDirectory) => {
    // Focus existing window when a second instance tries to launch
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

function getIconPath() {
  const ico = path.join(__dirname, "icons", "icon.ico");
  const png = path.join(__dirname, "icons", "icon.png");
  return process.platform === "win32" ? ico : png;
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    title: "MediFlux — Autonomous Supply Chain Control Tower",
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    center: true,
    resizable: true,
    backgroundColor: "#E8E4D3", // Warm Editorial Minimalism Warm Ivory
    icon: getIconPath(),
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  // Load production bundle or dev server
  const devUrl = process.env.ELECTRON_DEV_URL;
  if (devUrl) {
    mainWindow.loadURL(devUrl);
  } else {
    const indexPath = path.join(__dirname, "../frontend/dist/index.html");
    mainWindow.loadFile(indexPath);
  }

  // Handle external URL requests (open in user's default browser)
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http:") || url.startsWith("https:")) {
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// 2. System Tray & Context Menu
function createSystemTray() {
  try {
    const trayIconPath = path.join(__dirname, "icons", process.platform === "win32" ? "icon.ico" : "icon.png");
    tray = new Tray(trayIconPath);
    tray.setToolTip("MediFlux — Autonomous Supply Chain Network");

    const contextMenu = Menu.buildFromTemplate([
      {
        label: "Open MediFlux Control Tower",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          }
        },
      },
      { type: "separator" },
      {
        label: "Navigate: Network Overview",
        click: () => navigateToRoute("/overview"),
      },
      {
        label: "Navigate: Strip Demand Cascade",
        click: () => navigateToRoute("/cascade"),
      },
      {
        label: "Navigate: Approvals Inbox",
        click: () => navigateToRoute("/approvals"),
      },
      {
        label: "Navigate: Cold-Chain Monitor",
        click: () => navigateToRoute("/cold-chain"),
      },
      { type: "separator" },
      {
        label: "Backend Connection Settings...",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
            mainWindow.webContents.send("mediflux:open-settings");
          }
        },
      },
      { type: "separator" },
      {
        label: "Quit MediFlux",
        click: () => {
          app.isQuitting = true;
          app.quit();
        },
      },
    ]);

    tray.setContextMenu(contextMenu);
    tray.on("double-click", () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
      }
    });
  } catch (err) {
    console.error("Failed to create tray icon:", err);
  }
}

function navigateToRoute(routePath) {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
    mainWindow.webContents.send("mediflux:navigate", routePath);
  }
}

// 3. Application Menu
function createApplicationMenu() {
  const template = [
    {
      label: "File",
      submenu: [
        {
          label: "Backend Connection Settings...",
          accelerator: "CmdOrCtrl+,",
          click: () => {
            if (mainWindow) mainWindow.webContents.send("mediflux:open-settings");
          },
        },
        { type: "separator" },
        { role: "reload", label: "Reload Interface" },
        { role: "forceReload", label: "Force Reload" },
        { type: "separator" },
        { role: "quit", label: "Exit MediFlux" },
      ],
    },
    {
      label: "Operations",
      submenu: [
        {
          label: "Network Overview",
          accelerator: "CmdOrCtrl+1",
          click: () => navigateToRoute("/overview"),
        },
        {
          label: "Demand Cascade Replay",
          accelerator: "CmdOrCtrl+2",
          click: () => navigateToRoute("/cascade"),
        },
        {
          label: "Agent Intelligence Console",
          accelerator: "CmdOrCtrl+3",
          click: () => navigateToRoute("/agents"),
        },
        {
          label: "HITL Approvals Inbox",
          accelerator: "CmdOrCtrl+4",
          click: () => navigateToRoute("/approvals"),
        },
        {
          label: "Cold-Chain Biologics Monitor",
          accelerator: "CmdOrCtrl+5",
          click: () => navigateToRoute("/cold-chain"),
        },
        {
          label: "Prescription Scanner",
          accelerator: "CmdOrCtrl+6",
          click: () => navigateToRoute("/prescriptions"),
        },
        {
          label: "Network Copilot",
          accelerator: "CmdOrCtrl+7",
          click: () => navigateToRoute("/copilot"),
        },
        {
          label: "Developer Platform & MCP",
          accelerator: "CmdOrCtrl+8",
          click: () => navigateToRoute("/developer"),
        },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
        { role: "toggleDevTools", label: "Developer Tools" },
      ],
    },
    {
      label: "Help",
      submenu: [
        {
          label: "FastAPI Backend Documentation",
          click: () => shell.openExternal("http://localhost:8000/docs"),
        },
        {
          label: "CDSCO Drug Schedules Reference",
          click: () => shell.openExternal("https://cdsco.gov.in"),
        },
        { type: "separator" },
        {
          label: "About MediFlux Control Tower",
          click: () => {
            const { dialog } = require("electron");
            dialog.showMessageBox(mainWindow, {
              type: "info",
              title: "About MediFlux",
              message: "MediFlux Control Tower v1.0.0",
              detail: "AI-Native Autonomous Pharmaceutical Supply Chain Ecosystem for India.\nWarm Editorial Minimalism Design System.",
              icon: getIconPath(),
            });
          },
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// 4. IPC Native Notification Handler
ipcMain.handle("mediflux:show-notification", (_event, { title, body, route }) => {
  if (Notification.isSupported()) {
    const notif = new Notification({
      title: title || "MediFlux Notification",
      body: body || "",
      icon: getIconPath(),
    });

    notif.on("click", () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
        if (route) {
          mainWindow.webContents.send("mediflux:navigate", route);
        }
      }
    });

    notif.show();
    return { status: "displayed" };
  }
  return { status: "unsupported" };
});

ipcMain.handle("mediflux:get-platform-info", () => {
  return {
    platform: process.platform,
    arch: process.arch,
    isDesktop: true,
    runtime: "electron",
    version: app.getVersion(),
  };
});

ipcMain.handle("mediflux:open-external", (_event, url) => {
  if (url && (url.startsWith("http:") || url.startsWith("https:"))) {
    shell.openExternal(url);
    return true;
  }
  return false;
});

// 5. App Lifecycle
app.whenReady().then(() => {
  createMainWindow();
  createSystemTray();
  createApplicationMenu();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
