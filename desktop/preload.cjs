/**
 * MediFlux Desktop Native Preload Bridge.
 * Exposes safe, typed OS integration APIs to the React frontend.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("medifluxDesktop", {
  isDesktop: true,
  runtime: "electron",

  // Query platform details (OS, architecture, runtime version)
  getPlatformInfo: () => ipcRenderer.invoke("mediflux:get-platform-info"),

  // Native Windows Desktop Notification trigger
  showNotification: (options) => ipcRenderer.invoke("mediflux:show-notification", options),

  // Open external links safely via default browser
  openExternal: (url) => ipcRenderer.invoke("mediflux:open-external", url),

  // Deep-link / tray navigation listener
  onNavigate: (callback) => {
    const subscription = (_event, path) => callback(path);
    ipcRenderer.on("mediflux:navigate", subscription);
    return () => ipcRenderer.removeListener("mediflux:navigate", subscription);
  },

  // Open settings modal trigger listener
  onOpenSettings: (callback) => {
    const subscription = () => callback();
    ipcRenderer.on("mediflux:open-settings", subscription);
    return () => ipcRenderer.removeListener("mediflux:open-settings", subscription);
  },
});
