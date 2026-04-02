import { appendFileSync, closeSync, existsSync, fstatSync, mkdirSync, openSync, renameSync, unlinkSync, writeSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

import type { LogLevel } from "../types/events.js";
import type { ILogger } from "../types/interfaces.js";
import type { Message } from '../types/runtime.js';


const RESET = "\u001b[0m";
const BOLD = "\u001b[1m";
const DIM = "\u001b[2m";
const GRAY = "\u001b[90m";
const WHITE = "\u001b[37m";
const CYAN = "\u001b[36m";
const YELLOW = "\u001b[33m";
const RED = "\u001b[31m";
const RED_BOLD = "\u001b[1;31m";
const MAGENTA = "\u001b[35m";


const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

/** Unicode symbols for each log level — fast visual scanning. */
const LEVEL_SYMBOL: Record<LogLevel, string> = {
  debug: "·",
  info: "▸",
  warn: "▵",
  error: "●",
};

/** ANSI color prefix per level (applied to symbol + level label). */
const LEVEL_COLOR: Record<LogLevel, string> = {
  debug: GRAY,
  info: CYAN,
  warn: YELLOW,
  error: RED_BOLD,
};

/** Padded uppercase labels — fixed 5-char width for column alignment. */
const LEVEL_LABEL: Record<LogLevel, string> = {
  debug: "DEBUG",
  info: "INFO ",
  warn: "WARN ",
  error: "ERROR",
};


// File Transport with Log Rotation

/** Default log file path for the daemon. */
const DEFAULT_LOG_FILE = join(homedir(), '.cassicore', 'daemon.log');

/** Configuration for file transport rotation. */
export interface FileTransportConfig {
  /** Maximum file size in bytes before rotation. Default: 10MB. */
  maxFileSize: number;
  /** Maximum number of rotated files to keep. Default: 5. */
  maxFiles: number;
  /** Log file path. Default: ~/.cassicore/daemon.log. */
  filePath: string;
}

/**
 * File transport with size-based log rotation.
 *
 * Rotation behavior:
 * - When log file exceeds maxFileSize, rotate:
 *   - daemon.log → daemon.1.log
 *   - daemon.1.log → daemon.2.log
 *   - etc.
 *   - Delete files beyond maxFiles
 * - Uses synchronous operations to avoid race conditions during rotation
 * - Checks size every N writes for performance (writeCounter)
 */
class FileTransport {
  private fd: number | null = null;
  private writeCounter = 0;
  private readonly checkInterval = 100; // Check size every 100 writes
  private currentSize = 0;

  constructor(private readonly config: FileTransportConfig) {
    this.openFile();
  }

  /**
   * Open the log file for appending. Creates parent directories if needed.
   */
  private openFile(): void {
    try {
      const dir = join(this.config.filePath, '..');
      mkdirSync(dir, { recursive: true });
    } catch {
      // Directory exists
    }

    try {
      // Open for appending, create if doesn't exist
      this.fd = openSync(this.config.filePath, 'a');
      // Get current file size
      const stats = fstatSync(this.fd);
      this.currentSize = stats.size;
    } catch {
      // If we can't open the file, we'll fall back to console-only
      this.fd = null;
      this.currentSize = 0;
    }
  }

  /**
   * Write a line to the log file. Performs rotation check periodically.
   */
  write(line: string): void {
    if (this.fd === null) return;

    const data = line + '\n';
    const byteLength = Buffer.byteLength(data, 'utf8');

    try {
      writeSync(this.fd, data);
      this.currentSize += byteLength;
      this.writeCounter++;

      // Check for rotation periodically (every checkInterval writes)
      if (this.writeCounter >= this.checkInterval) {
        this.writeCounter = 0;
        if (this.currentSize >= this.config.maxFileSize) {
          this.rotate();
        }
      }
    } catch {
      // Write failed - close and null out the fd
      try {
        closeSync(this.fd);
      } catch {
        // ignore
      }
      this.fd = null;
    }
  }

  /**
   * Rotate log files. Called when current log exceeds maxFileSize.
   *
   * Rotation: daemon.4.log → delete, daemon.3.log → daemon.4.log, etc.
   * Then daemon.log → daemon.1.log, create new daemon.log
   */
  private rotate(): void {
    if (this.fd !== null) {
      try {
        closeSync(this.fd);
      } catch {
        // ignore
      }
      this.fd = null;
    }

    const basePath = this.config.filePath;
    const maxFiles = this.config.maxFiles;

    // Delete the oldest file if it exists
    const oldestFile = `${basePath}.${maxFiles}`;
    try {
      if (existsSync(oldestFile)) {
        unlinkSync(oldestFile);
      }
    } catch {
      // Ignore deletion errors
    }

    // Shift files: daemon.(n-1).log → daemon.n.log
    for (let i = maxFiles - 1; i >= 1; i--) {
      const src = `${basePath}.${i}`;
      const dst = `${basePath}.${i + 1}`;
      try {
        if (existsSync(src)) {
          renameSync(src, dst);
        }
      } catch {
        // Ignore rename errors
      }
    }

    // Rename current log to .1
    try {
      if (existsSync(basePath)) {
        renameSync(basePath, `${basePath}.1`);
      }
    } catch {
      // Ignore rename errors
    }

    // Open new log file
    this.openFile();
  }

  /**
   * Close the file descriptor. Call on shutdown.
   */
  close(): void {
    if (this.fd !== null) {
      try {
        closeSync(this.fd);
      } catch {
        // ignore
      }
      this.fd = null;
    }
  }
}

/** Global file transport instance (initialized by daemon startup). */
let fileTransport: FileTransport | null = null;

/**
 * Initialize the file transport for log rotation.
 * Should be called once during daemon startup.
 * @dep callers: bootConfiguration (core/daemon/boot-configuration.ts), logger-rotation.test.ts (tests/logger-rotation.test.ts)
 * @dep module: Daemon
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function initFileTransport(config?: Partial<FileTransportConfig>): void {
  if (fileTransport) {
    fileTransport.close();
  }
  fileTransport = new FileTransport({
    maxFileSize: config?.maxFileSize ?? 10 * 1024 * 1024, // 10MB default
    maxFiles: config?.maxFiles ?? 5,
    filePath: config?.filePath ?? DEFAULT_LOG_FILE,
  });
}

/**
 * Close the file transport. Call on daemon shutdown.
 * @dep callers: bootConfiguration (core/daemon/boot-configuration.ts), logger-rotation.test.ts (tests/logger-rotation.test.ts)
 * @dep module: Daemon
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function closeFileTransport(): void {
  if (fileTransport) {
    fileTransport.close();
    fileTransport = null;
  }
}


/**
 * Format a Date as HH:MM:SS.mmm using local time and zero-padding.
 * Millisecond precision is essential for a long-running daemon.
 * @dep callers: writeThoughtLog (core/logger.ts), writeThoughtRequestLog (core/logger.ts), writeThoughtResultLog (core/logger.ts), writeConsole (core/logger.ts)
 * @dep module: Intelligence
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */
function timeStamp(date = new Date()): string {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  const ms = String(date.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}

const THOUGHT_LOG_DIR = join(homedir(), '.cassi');
const THOUGHT_LOG_PATH = join(THOUGHT_LOG_DIR, 'thought.log');

/**
 * @dep callers: writeThoughtLog (core/logger.ts), writeThoughtRequestLog (core/logger.ts), writeThoughtResultLog (core/logger.ts)
 * @dep module: Intelligence
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

function appendThoughtLine(line: string): void {
  try {
    mkdirSync(THOUGHT_LOG_DIR, { recursive: true });
    appendFileSync(THOUGHT_LOG_PATH, `${line}\n`, 'utf8');
  } catch {
    // best effort only
  }
}

export function writeThoughtLog(event: string, meta?: Record<string, unknown>): void {
  const time = timeStamp();
  const metaStr = meta && Object.keys(meta).length > 0 ? `  ${formatMeta(meta)}` : '';
  appendThoughtLine(`${time} ${event}${metaStr}`);
}

function stringifyContent(value: Message['content']): string {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '[unserializable content]';
  }
}

function indentBlock(text: string, prefix: string = '    '): string {
  return text
    .split('\n')
    .map((line) => `${prefix}${line}`)
    .join('\n');
}

/**
 * @dep callers: complete (core/providers/centralized.ts), complete (core/intelligence/index.ts)
 * @dep calls: indentBlock, stringifyContent, appendThoughtLine, timeStamp
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function writeThoughtRequestLog(args: {
  provider: string;
  model: string;
  sessionId: string;
  requestId: string;
  messages: Message[];
  systemPrompt?: string;
  toolCount?: number;
  attachmentCount?: number;
  timeoutMs?: number;
}): void {
  const { provider, model, sessionId, requestId, messages, systemPrompt, toolCount, attachmentCount, timeoutMs } = args;
  const time = timeStamp();

  const header = `${time} ▸ THOUGHT  provider=${provider}  model=${model}  sessionId=${sessionId}  requestId=${requestId}`;
  const meta = `${time} · META     messageCount=${messages.length}  toolCount=${toolCount ?? 0}  attachmentCount=${attachmentCount ?? 0}  timeoutMs=${timeoutMs ?? 0}`;

  const blocks: string[] = [header, meta];

  if (systemPrompt) {
    blocks.push(`${time} · SYSTEM`);
    blocks.push(indentBlock(systemPrompt));
  }

  messages.forEach((message, index) => {
    blocks.push(`${time} · MESSAGE  index=${index}  role=${message.role}${message.name ? `  name=${message.name}` : ''}`);
    blocks.push(indentBlock(stringifyContent(message.content)));
  });

  blocks.push(`${time} · END`);
  appendThoughtLine(blocks.join('\n'));
}

/**
 * @dep callers: complete (core/providers/centralized.ts), complete (core/intelligence/index.ts)
 * @dep calls: formatMeta, appendThoughtLine, timeStamp
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function writeThoughtResultLog(event: string, meta?: Record<string, unknown>): void {
  const time = timeStamp();
  const metaStr = meta && Object.keys(meta).length > 0 ? `  ${formatMeta(meta)}` : '';
  appendThoughtLine(`${time} ${event}${metaStr}`);
}


/** Maximum character length for a single metadata value before truncation. */
const META_VALUE_MAX = 120;

/**
 * Format a metadata object as human-readable `key=value` pairs.
 *
 * - Strings: unquoted unless they contain spaces
 * - Numbers/booleans: raw
 * - Objects/arrays: JSON (truncated if long)
 * - Undefined/null: skipped
 * @dep callers: writeThoughtLog (core/logger.ts), writeThoughtResultLog (core/logger.ts), writeConsole (core/logger.ts)
 * @dep calls: formatValue
 * @dep module: Intelligence
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */
function formatMeta(meta: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, val] of Object.entries(meta)) {
    if (val === undefined || val === null) continue;
    parts.push(`${key}=${formatValue(val)}`);
  }
  return parts.join("  ");
}

function formatValue(val: unknown): string {
  if (typeof val === "string") {
    if (val.length === 0) return '""';
    // Strings with spaces, newlines, or special chars get quoted
    if (/[\s"=]/.test(val)) {
      const truncated = val.length > META_VALUE_MAX ? val.slice(0, META_VALUE_MAX) + "…" : val;
      return `"${truncated.replace(/"/g, '\\"')}"`;
    }
    return val.length > META_VALUE_MAX ? val.slice(0, META_VALUE_MAX) + "…" : val;
  }
  if (typeof val === "number" || typeof val === "boolean") {
    return String(val);
  }
  // Objects and arrays — compact JSON with truncation
  try {
    const json = JSON.stringify(val);
    return json.length > META_VALUE_MAX ? json.slice(0, META_VALUE_MAX) + "…" : json;
  } catch {
    return "[unserializable]";
  }
}


/**
 * Logger implementation used across CassiCore.
 *
 * Output format:
 * ```
 * 14:32:01.847 ▸ INFO  daemon  Unified Intelligence Loop started  sessionId=abc12345
 * ```
 *
 * Segments are independently colored for fast visual scanning:
 * - Timestamp: dim gray
 * - Symbol + level: level-specific color
 * - Component: bold white
 * - Message: default terminal color
 * - Metadata: dim key=value pairs
 */
export class Logger implements ILogger {
  public readonly component: string;
  private readonly level: LogLevel;

  /**
   * Create a new Logger.
   * @param component - component label to include in logs
   * @param level - minimum log level to emit
   */
  constructor(component: string, level: LogLevel) {
    this.component = component;
    this.level = level;
  }

  /**
   * Create a child logger with a fixed component label that inherits the level.
   * @param component - component label for the child logger
   */
  child(component: string): ILogger {
    return new Logger(component, this.level);
  }

  /**
   * Log a debug-level message. Filtered by configured level.
   * @param msg - human-readable message
   * @param meta - optional structured metadata to append
   */
  debug(msg: string, meta?: Record<string, unknown>): void {
    if (!this.shouldLog("debug")) return;
    this.writeConsole("debug", msg, meta);
  }

  /**
   * Log an info-level message. Filtered by configured level.
   * @param msg - human-readable message
   * @param meta - optional structured metadata to append
   */
  info(msg: string, meta?: Record<string, unknown>): void {
    if (!this.shouldLog("info")) return;
    this.writeConsole("info", msg, meta);
  }

  /**
   * Log a warning-level message. Filtered by configured level.
   * @param msg - human-readable message
   * @param meta - optional structured metadata to append
   */
  warn(msg: string, meta?: Record<string, unknown>): void {
    if (!this.shouldLog("warn")) return;
    this.writeConsole("warn", msg, meta);
  }

  /**
   * Log an error-level message. Filtered by configured level.
   * @param msg - human-readable message
   * @param meta - optional structured metadata to append
   */
  error(msg: string, meta?: Record<string, unknown>): void {
    if (!this.shouldLog("error")) return;
    this.writeConsole("error", msg, meta);
  }

  /**
   * Determine if a message at the provided level should be emitted.
   */
  private shouldLog(level: LogLevel): boolean {
    return LEVEL_PRIORITY[level] >= LEVEL_PRIORITY[this.level];
  }

  /**
   * Check if we should emit ANSI color codes.
   * Only emit colors when writing directly to a TTY (interactive terminal).
   * When redirected to files or pipes, emit plain text for cleaner logs.
   */
  private writeConsole(level: LogLevel, msg: string, meta?: Record<string, unknown>): void {
    const time = timeStamp();
    const symbol = LEVEL_SYMBOL[level];
    const label = LEVEL_LABEL[level];
    const color = LEVEL_COLOR[level];
    const comp = this.component;

    // Determine if we're writing to a TTY (for color output)
    const isTTY = level === "warn" || level === "error"
      ? process.stderr.isTTY
      : process.stdout.isTTY;

    // Build the line with or without coloring based on TTY detection:
    // [dim timestamp] [colored symbol+level] [bold component] [message] [dim metadata]
    let line: string;
    if (isTTY) {
      line = `${DIM}${time}${RESET} ${color}${symbol} ${label}${RESET}  ${BOLD}${WHITE}${comp}${RESET}  ${msg}`;
    } else {
      line = `${time} ${symbol} ${label}  ${comp}  ${msg}`;
    }

    if (meta && Object.keys(meta).length > 0) {
      const metaStr = formatMeta(meta);
      if (metaStr) {
        line += isTTY ? `  ${DIM}${metaStr}${RESET}` : `  ${metaStr}`;
      }
    }

    // Write to console (with colors if TTY)
    if (level === "warn" || level === "error") {
      console.error(line); // contributing:ignore
    } else {
      // eslint-disable-next-line no-console
      console.log(line); // contributing:ignore
    }

    // Write to file transport (plain text, no ANSI codes)
    if (fileTransport) {
      const plainLine = `${time} ${symbol} ${label}  ${comp}  ${msg}`;
      const metaStr = meta && Object.keys(meta).length > 0 ? formatMeta(meta) : '';
      const fullLine = metaStr ? `${plainLine}  ${metaStr}` : plainLine;
      fileTransport.write(fullLine);
    }
  }
}

export const rootLogger = new Logger("core", "info");
