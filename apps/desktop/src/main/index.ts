import { join } from "node:path";
import { BrowserWindow, Menu, app, globalShortcut, ipcMain, session, shell } from "electron";
import { CuaTunnelHost } from "./cuaHost";

const ORCHESTRATOR_URL = process.env.OS1_ORCHESTRATOR_URL ?? "http://127.0.0.1:3008";
const CLIENT_TOKEN = process.env.OS1_CLIENT_TOKEN ?? "";
const CORAL = "#cd4f33";

const cuaHost = new CuaTunnelHost(ORCHESTRATOR_URL, CLIENT_TOKEN);

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: CORAL,
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      sandbox: true,
      autoplayPolicy: "no-user-gesture-required", // startup sound plays before any click
    },
  });
  win.once("ready-to-show", () => win.show());
  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });
  const hash = process.env.OS1_PREVIEW ? `preview=${process.env.OS1_PREVIEW}` : undefined;
  if (process.env.ELECTRON_RENDERER_URL) void win.loadURL(process.env.ELECTRON_RENDERER_URL + (hash ? `#${hash}` : ""));
  else void win.loadFile(join(__dirname, "../renderer/index.html"), { hash });
  return win;
}

function buildMenu(): void {
  const replayOnboarding = async () => {
    await fetch(`${ORCHESTRATOR_URL}/os1/dev/reset-onboarding`, {
      method: "POST",
      headers: { Authorization: `Bearer ${CLIENT_TOKEN}` },
    }).catch(() => undefined);
    BrowserWindow.getAllWindows().forEach((w) => w.webContents.reload());
  };
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      ...(process.platform === "darwin" ? [{ role: "appMenu" as const }] : []),
      { role: "editMenu" },
      {
        label: "Develop",
        submenu: [
          { label: "Replay Onboarding", accelerator: "CmdOrCtrl+Shift+R", click: () => void replayOnboarding() },
          { label: "Let Me Drive (Revoke Cua)", accelerator: "CmdOrCtrl+Shift+Escape", click: () => void cuaHost.revokeAll() },
          { role: "reload" },
          { role: "toggleDevTools" },
        ],
      },
      { role: "windowMenu" },
    ]),
  );
}

app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((_wc, permission, callback) => {
    callback(permission === "media");
  });

  ipcMain.handle("os1:config", () => ({
    orchestratorUrl: ORCHESTRATOR_URL,
    clientToken: CLIENT_TOKEN,
  }));
  ipcMain.handle("os1:cua:revoke", () => cuaHost.revokeAll());
  ipcMain.handle("os1:cua:status", () => cuaHost.status());

  if (!process.env.OS1_PREVIEW) {
    cuaHost.start();
    // Global kill switch: works even when another app is frontmost on macOS.
    try {
      globalShortcut.register("CommandOrControl+Shift+Escape", () => {
        void cuaHost.revokeAll();
      });
    } catch {
      /* shortcut unavailable in headless X11 */
    }
  }

  buildMenu();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
  cuaHost.stop();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
