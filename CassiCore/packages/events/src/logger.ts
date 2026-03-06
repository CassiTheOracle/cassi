import type { LogLevel } from "../types/events.js";
import type { ILogger } from "../types/interfaces.js";

// ─── ANSI escape codes ───────────────────────────────────────────────────────

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

// ─── Level config ────────────────────────────────────────────────────────────

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

// ─── Timestamp ───────────────────────────────────────────────────────────────

/**
 * Format a Date as HH:MM:SS.mmm using local time and zero-padding.
 * Millisecond precision is essential for a long-running daemon.
 */
function timeStamp(date = new Date()): string {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  const ms = String(date.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}

// ─── Metadata formatter ──────────────────────────────────────────────────────

/** Maximum character length for a single metadata value before truncation. */
const META_VALUE_MAX = 120;

/**
 * Format a metadata object as human-readable `key=value` pairs.
 *
 * - Strings: unquoted unless they contain spaces
 * - Numbers/booleans: raw
 * - Objects/arrays: JSON (truncated if long)
 * - Undefined/null: skipped
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

// ─── Logger ──────────────────────────────────────────────────────────────────

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
   * Compose and write the log line to stdout or stderr depending on level.
   *
   * Format: `HH:MM:SS.mmm ▸ INFO  component  Message text  key=value`
   * Each segment is independently colored for readability.
   */
  private writeConsole(level: LogLevel, msg: string, meta?: Record<string, unknown>): void {
    const time = timeStamp();
    const symbol = LEVEL_SYMBOL[level];
    const label = LEVEL_LABEL[level];
    const color = LEVEL_COLOR[level];
    const comp = this.component;

    // Build the line with per-segment coloring:
    // [dim timestamp] [colored symbol+level] [bold component] [message] [dim metadata]
    let line = `${DIM}${time}${RESET} ${color}${symbol} ${label}${RESET}  ${BOLD}${WHITE}${comp}${RESET}  ${msg}`;

    if (meta && Object.keys(meta).length > 0) {
      const metaStr = formatMeta(meta);
      if (metaStr) {
        line += `  ${DIM}${metaStr}${RESET}`;
      }
    }

    if (level === "warn" || level === "error") {
      console.error(line);
    } else {
      // eslint-disable-next-line no-console
      console.log(line);
    }
  }
}

export const rootLogger = new Logger("core", "info");
