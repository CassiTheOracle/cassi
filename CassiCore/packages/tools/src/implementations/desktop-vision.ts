/**
 * Desktop Vision Tool for CassiCore
 * Linux/KDE Plasma implementation
 * 
 * Gives Cassi the ability to see your desktop windows via native Linux tools.
 */

import { spawn } from 'node:child_process';
import { readFile, unlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js';

const execAsync = promisify(spawn);

// User/session detection for graceful error handling
interface SessionCheck {
  canAccessDesktop: boolean;
  runningAsUser: string;
  desktopSessionUser: string | null;
  displayAvailable: boolean;
  dbusAccessible: boolean;
  error: string | null;
}

/**
 * Check if we're running in the same user context as the desktop session.
 * Returns detailed info for graceful error handling.
 */
async function checkDesktopAccess(): Promise<SessionCheck> {
  const result: SessionCheck = {
    canAccessDesktop: false,
    runningAsUser: 'unknown',
    desktopSessionUser: null,
    displayAvailable: false,
    dbusAccessible: false,
    error: null,
  };

  try {
    // Get current user
    const whoami = await execCommand('whoami', 5000);
    result.runningAsUser = whoami.trim();

    // Check DISPLAY
    const display = process.env.DISPLAY;
    result.displayAvailable = !!display;

    // Check DBus session bus
    const dbusAddr = process.env.DBUS_SESSION_BUS_ADDRESS;
    if (dbusAddr) {
      // Try to ping the session bus
      try {
        await execCommand('dbus-send --session --dest=org.freedesktop.DBus --type=method_call --print-reply /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>/dev/null | head -5', 3000);
        result.dbusAccessible = true;
      } catch {
        result.dbusAccessible = false;
      }
    }

    // Try to determine desktop session user
    try {
      // Derive X socket from $DISPLAY (e.g. ":1" → X1, ":0.0" → X0)
      const displayNum = (display || ':0').replace(/^:/, '').replace(/\..*$/, '');
      const xSocketPath = `/tmp/.X11-unix/X${displayNum}`;
      const xOwner = await execCommand(`stat -c "%U" ${xSocketPath} 2>/dev/null || echo "unknown"`, 3000);
      if (xOwner.trim() !== 'unknown') {
        result.desktopSessionUser = xOwner.trim();
      }
    } catch {
      // Ignore
    }

    // Can we access desktop if we're the same user and have display/dbus?
    if (result.runningAsUser === result.desktopSessionUser && 
        result.displayAvailable && 
        result.dbusAccessible) {
      result.canAccessDesktop = true;
    }

    // If we have a mismatch, build helpful error
    if (!result.canAccessDesktop) {
      if (result.runningAsUser !== result.desktopSessionUser && result.desktopSessionUser) {
        result.error = `CassiCore is running as user "${result.runningAsUser}" but your desktop session is owned by "${result.desktopSessionUser}". Desktop vision requires CassiCore to run as the same user as your KDE session. See migration guide: docs/migrate-to-valerie.md`;
      } else if (!result.displayAvailable) {
        result.error = `No DISPLAY environment variable set. CassiCore needs access to your X11/Wayland session.`;
      } else if (!result.dbusAccessible) {
        result.error = `Cannot access D-Bus session bus. Your desktop environment (KDE) requires D-Bus access for window management.`;
      } else {
        result.error = `Desktop session not accessible. CassiCore may be running as a different user or in a different session than your desktop.`;
      }
    }

    return result;
  } catch (err) {
    result.error = `Failed to check desktop access: ${err}`;
    return result;
  }
}

// Privacy blocklist - windows/apps that should never be captured
const BLOCKED_PATTERNS = [
  /password/i, /passwort/i, /contraseña/i,
  /1password/i, /bitwarden/i, /lastpass/i, /keepass/i, /dashlane/i,
  /authy/i, /authenticator/i,
  /bank/i, /credit.?card/i, /ssn/i, /social.?security/i,
  /tax/i, /turbotax/i,
  /login.*:/i, /sign.?in/i,
  /vpn/i, /wireguard/i, /openvpn/i
];

interface WindowInfo {
  id: string;
  title: string;
  app: string;
  pid: number;
  isActive: boolean;
  isMinimized: boolean;
  workspace: number;
}

interface ScreenshotResult {
  path: string;
  windowTitle: string;
  app: string;
  blocked: boolean;
}

/**
 * Check if a window title/app should be blocked for privacy
 * @dep callers: captureActiveWindow (core/tools/implementations/desktop-vision.ts), desktopVisionHandler (core/tools/implementations/desktop-vision.ts)
 * @dep calls: test
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function isBlocked(title: string, app: string): boolean {
  const combined = `${title} ${app}`.toLowerCase();
  return BLOCKED_PATTERNS.some(pattern => pattern.test(combined));
}

/**
 * Execute a shell command and return stdout
 * @dep callers: checkDesktopAccess (core/tools/implementations/desktop-vision.ts), resolveQdbus (core/tools/implementations/desktop-vision.ts), listWindowsKDE (core/tools/implementations/desktop-vision.ts), listWindowsXdotool (core/tools/implementations/desktop-vision.ts), getActiveWindow (core/tools/implementations/desktop-vision.ts) [+3]
 * @dep calls: on
 * @dep flows: DesktopVisionHandler → ExecCommand (4/4)
 * @dep module: Implementations
 * @dep risk: HIGH | 8 callers, 1 flow, 1 module
 */
async function execCommand(command: string, timeoutMs = 10000): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn('bash', ['-c', command]);
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      proc.kill();
      reject(new Error(`Command timeout after ${timeoutMs}ms`));
    }, timeoutMs);

    proc.stdout.on('data', (data: Buffer) => { stdout += data.toString(); });
    proc.stderr.on('data', (data: Buffer) => { stderr += data.toString(); });
    proc.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0 && !stdout) {
        reject(new Error(`Exit ${code}: ${stderr}`));
      } else {
        resolve(stdout.trim());
      }
    });
  });
}

/**
 * Resolve the qdbus binary name — Qt6 ships "qdbus6", Qt5 ships "qdbus"
 */
let _qdbusCmd: string | null | undefined;
/**
 * @dep callers: listWindowsKDE (core/tools/implementations/desktop-vision.ts), getActiveWindow (core/tools/implementations/desktop-vision.ts)
 * @dep calls: execCommand
 * @dep flows: DesktopVisionHandler → ExecCommand (3/4)
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */

async function resolveQdbus(): Promise<string | null> {
  if (_qdbusCmd !== undefined) return _qdbusCmd;
  for (const candidate of ['qdbus6', 'qdbus', 'qdbus-qt6', 'qdbus-qt5']) {
    try {
      await execCommand(`command -v ${candidate}`, 2000);
      _qdbusCmd = candidate;
      return _qdbusCmd;
    } catch {
      // try next
    }
  }
  _qdbusCmd = null;
  return null;
}

/**
 * List all windows using KWin's D-Bus interface or xdotool fallback
 * @dep callers: desktopVisionHandler (core/tools/implementations/desktop-vision.ts)
 * @dep calls: listWindowsXdotool, parseKWinWindowInfo, resolveQdbus, execCommand
 * @dep flows: DesktopVisionHandler → ParseKWinWindowInfo (2/3), DesktopVisionHandler → ExecCommand (2/4)
 * @dep module: Implementations
 * @dep risk: LOW | 1 caller, 2 flows, 1 module
 */
async function listWindowsKDE(): Promise<WindowInfo[]> {
  try {
    // Try KWin's D-Bus interface first (most reliable on KDE)
    const qdbusCmd = await resolveQdbus();
    if (!qdbusCmd) return listWindowsXdotool();
    const cmd = `${qdbusCmd} org.kde.KWin /KWin queryWindowInfo 2>/dev/null || echo "FALLBACK"`;
    const result = await execCommand(cmd, 5000);
    
    if (result !== 'FALLBACK' && result.includes('windowId')) {
      // Parse KWin output
      return parseKWinWindowInfo(result);
    }
    
    // Fallback to xdotool
    return listWindowsXdotool();
  } catch {
    return listWindowsXdotool();
  }
}

/**
 * Parse KWin window info output
 * @dep callers: listWindowsKDE (core/tools/implementations/desktop-vision.ts)
 * @dep flows: DesktopVisionHandler → ParseKWinWindowInfo (3/3)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
function parseKWinWindowInfo(output: string): WindowInfo[] {
  const windows: WindowInfo[] = [];
  const lines = output.split('\n');
  let current: Partial<WindowInfo> = {};
  
  for (const line of lines) {
    if (line.startsWith('windowId:')) {
      if (current.id) windows.push(current as WindowInfo);
      current = { id: line.split(':')[1]?.trim() || '' };
    } else if (line.includes('caption:')) {
      current.title = line.split(':')[1]?.trim() || '';
    } else if (line.includes('resourceClass:')) {
      current.app = line.split(':')[1]?.trim() || 'Unknown';
    } else if (line.includes('pid:')) {
      current.pid = parseInt(line.split(':')[1]?.trim() || '0');
    } else if (line.includes('active:')) {
      current.isActive = line.includes('true');
    }
  }
  
  if (current.id) windows.push(current as WindowInfo);
  return windows;
}

/**
 * List windows using xdotool (fallback)
 */
async function listWindowsXdotool(): Promise<WindowInfo[]> {
  try {
    // Get all window IDs
    const idsOutput = await execCommand('xdotool search --onlyvisible --class "" 2>/dev/null');
    const ids = idsOutput.split('\n').filter(id => id.trim());
    
    const windows: WindowInfo[] = [];
    const activeId = await execCommand('xdotool getactivewindow 2>/dev/null').catch(() => '');
    
    for (const id of ids.slice(0, 50)) { // Limit to 50 windows
      try {
        const [title, app, pid] = await Promise.all([
          execCommand(`xdotool getwindowname ${id} 2>/dev/null`).catch(() => ''),
          execCommand(`xdotool getwindowclassname ${id} 2>/dev/null`).catch(() => 'Unknown'),
          execCommand(`xdotool getwindowpid ${id} 2>/dev/null`).catch(() => '0'),
        ]);
        
        windows.push({
          id,
          title: title || 'Untitled',
          app: app || 'Unknown',
          pid: parseInt(pid) || 0,
          isActive: id === activeId,
          isMinimized: false, // Would need additional check
          workspace: 0,
        });
      } catch {
        // Skip problematic windows
      }
    }
    
    return windows;
  } catch {
    return [];
  }
}

/**
 * Get the currently active window
 * @dep callers: captureActiveWindow (core/tools/implementations/desktop-vision.ts), desktopVisionHandler (core/tools/implementations/desktop-vision.ts)
 * @dep calls: resolveQdbus, execCommand, all
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
async function getActiveWindow(): Promise<WindowInfo | null> {
  try {
    // Try KWin first
    const qdbusCmd = await resolveQdbus();
    const result = await execCommand(
      qdbusCmd
        ? `${qdbusCmd} org.kde.KWin /KWin activeWindow 2>/dev/null || xdotool getactivewindow 2>/dev/null`
        : `xdotool getactivewindow 2>/dev/null`
    );
    
    if (!result) return null;
    
    const id = result.trim();
    const [title, app] = await Promise.all([
      execCommand(`xdotool getwindowname ${id} 2>/dev/null${qdbusCmd ? ` || ${qdbusCmd} org.kde.KWin /KWin queryWindowInfo 2>/dev/null | grep caption | head -1` : ''}`).catch(() => 'Unknown'),
      execCommand(`xdotool getwindowclassname ${id} 2>/dev/null`).catch(() => 'Unknown'),
    ]);
    
    return {
      id,
      title: title.split(':')[1]?.trim() || title || 'Unknown',
      app: app || 'Unknown',
      pid: 0,
      isActive: true,
      isMinimized: false,
      workspace: 0,
    };
  } catch {
    return null;
  }
}

/**
 * Capture a screenshot of the active window
 */
async function captureActiveWindow(): Promise<ScreenshotResult | null> {
  const activeWindow = await getActiveWindow();
  if (!activeWindow) return null;
  
  // Check privacy blocklist
  if (isBlocked(activeWindow.title, activeWindow.app)) {
    return {
      path: '',
      windowTitle: activeWindow.title,
      app: activeWindow.app,
      blocked: true,
    };
  }
  
  const tmpPath = join(tmpdir(), `cassi-capture-${Date.now()}.png`);
  
  try {
    // Try spectacle (KDE's screenshot tool) first
    try {
      await execCommand(`spectacle --background --activewindow --nonotify --output ${tmpPath} 2>/dev/null`, 10000);
    } catch {
      // Fallback to gnome-screenshot or import (ImageMagick)
      try {
        await execCommand(`gnome-screenshot -w -f ${tmpPath} 2>/dev/null`, 10000);
      } catch {
        // Try ImageMagick import with window ID
        await execCommand(`import -window ${activeWindow.id} ${tmpPath} 2>/dev/null`, 10000);
      }
    }
    
    return {
      path: tmpPath,
      windowTitle: activeWindow.title,
      app: activeWindow.app,
      blocked: false,
    };
  } catch (error) {
    return null;
  }
}

/**
 * Focus a window by ID
 */
async function focusWindow(windowId: string): Promise<boolean> {
  try {
    await execCommand(`xdotool windowactivate ${windowId} 2>/dev/null || wmctrl -i -r ${windowId} -b add,above 2>/dev/null`);
    return true;
  } catch {
    return false;
  }
}

/**
 * Extract text from an image using OCR
 */
async function extractText(imagePath: string): Promise<{ text: string; confidence: number }> {
  try {
    // Try tesseract first
    const result = await execCommand(`tesseract ${imagePath} stdout 2>/dev/null`, 15000);
    return { text: result, confidence: 0.85 };
  } catch {
    // Fallback: check if ocrmypdf or other tools available
    return { text: '[OCR not available - install tesseract]', confidence: 0 };
  }
}

// Tool definition
export const desktopVisionDefinition: ToolDefinition = {
  name: 'desktop_vision',
  description: `View and interact with your desktop windows on KDE Plasma.

This tool allows me to:
- List all visible windows
- See which window is currently active
- Capture screenshots of your active window (for debugging, reading errors, etc.)
- Focus/bring windows to the front
- Extract text from windows using OCR

PRIVACY PROTECTION:
- Password managers, banking apps, and login screens are automatically blocked
- Screenshots are only taken when explicitly requested
- All processing is local - no data leaves your machine
- You can disable this tool at any time in config

Examples:
- "What windows do I have open?" → list_windows
- "Can you see this error?" → capture_active
- "Bring Firefox to the front" → focus
- "Read this dialog box to me" → capture_active + ocr`,
  parameters: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['list_windows', 'get_active', 'capture_active', 'focus', 'ocr_active'],
        description: 'Action to perform on desktop windows',
      },
      window_id: {
        type: 'string',
        description: 'Window ID to focus (only for focus action)',
      },
    },
    required: ['action'],
  },
  timeoutMs: 30_000,
  readOnly: true,
  requiredPermission: 'read-only',
};

// Tool handler
export const desktopVisionHandler: ToolHandler = async (input, ctx) => {
  const action = input['action'] as string;
  const windowId = input['window_id'] as string | undefined;
  
  // Check desktop access before attempting any action
  const accessCheck = await checkDesktopAccess();
  if (!accessCheck.canAccessDesktop) {
    return JSON.stringify({
      success: false,
      error: accessCheck.error,
      context: {
        running_as: accessCheck.runningAsUser,
        desktop_session_user: accessCheck.desktopSessionUser,
        display_available: accessCheck.displayAvailable,
        dbus_accessible: accessCheck.dbusAccessible,
      },
      migration_guide: 'To use desktop vision, CassiCore must run as the same user as your desktop session. See: /home/valerie/workspaces/cassicore/docs/migrate-to-valerie.md',
    }, null, 2);
  }
  
  try {
    switch (action) {
      case 'list_windows': {
        const windows = await listWindowsKDE();
        const activeWindow = windows.find(w => w.isActive);
        
        // Filter out blocked windows from listing
        const visibleWindows = windows
          .filter(w => !isBlocked(w.title, w.app))
          .slice(0, 30); // Limit output
        
        const lines = visibleWindows.map(w => {
          const indicator = w.isActive ? '🟢' : '⚪';
          const title = w.title.length > 50 ? `${w.title.slice(0, 47)  }...` : w.title;
          return `${indicator} [${w.id}] ${title} (${w.app})`;
        });
        
        return JSON.stringify({
          success: true,
          count: visibleWindows.length,
          total: windows.length,
          active_window: activeWindow && !isBlocked(activeWindow.title, activeWindow.app) 
            ? activeWindow.title 
            : null,
          windows: lines.join('\n'),
          blocked_count: windows.length - visibleWindows.length,
        }, null, 2);
      }
      
      case 'get_active': {
        const window = await getActiveWindow();
        if (!window) {
          return JSON.stringify({ success: false, error: 'Could not determine active window' });
        }
        
        if (isBlocked(window.title, window.app)) {
          return JSON.stringify({
            success: false,
            error: 'Active window is blocked for privacy (password manager or sensitive app)',
            blocked: true,
          });
        }
        
        return JSON.stringify({
          success: true,
          id: window.id,
          title: window.title,
          app: window.app,
        }, null, 2);
      }
      
      case 'capture_active': {
        const result = await captureActiveWindow();
        
        if (!result) {
          return JSON.stringify({ success: false, error: 'Failed to capture window' });
        }
        
        if (result.blocked) {
          return JSON.stringify({
            success: false,
            error: `Window "${result.windowTitle}" is blocked for privacy (password manager or sensitive app)`,
            blocked: true,
          });
        }
        
        // Read the image and return as base64
        const imageData = await readFile(result.path);
        const base64Image = imageData.toString('base64');
        
        // Clean up temp file
        await unlink(result.path).catch(() => {});
        
        return JSON.stringify({
          success: true,
          window_title: result.windowTitle,
          app: result.app,
          image_base64: base64Image,
          mime_type: 'image/png',
          note: 'I can see this screenshot. Describe what you need help with.',
        }, null, 2);
      }
      
      case 'focus': {
        if (!windowId) {
          return JSON.stringify({ success: false, error: 'window_id is required for focus action' });
        }
        
        const success = await focusWindow(windowId);
        return JSON.stringify({
          success,
          message: success ? `Focused window ${windowId}` : `Failed to focus window ${windowId}`,
        }, null, 2);
      }
      
      case 'ocr_active': {
        const captureResult = await captureActiveWindow();
        
        if (!captureResult) {
          return JSON.stringify({ success: false, error: 'Failed to capture window for OCR' });
        }
        
        if (captureResult.blocked) {
          return JSON.stringify({
            success: false,
            error: 'Window is blocked for privacy',
            blocked: true,
          });
        }
        
        const ocrResult = await extractText(captureResult.path);
        
        // Clean up temp file
        await unlink(captureResult.path).catch(() => {});
        
        return JSON.stringify({
          success: true,
          window_title: captureResult.windowTitle,
          text: ocrResult.text,
          confidence: ocrResult.confidence,
          word_count: ocrResult.text.split(/\s+/).length,
        }, null, 2);
      }
      
      default:
        return JSON.stringify({ success: false, error: `Unknown action: ${action}` });
    }
  } catch (error) {
    return JSON.stringify({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};
