import type { ILogger } from "../types/interfaces.js";
import type { LogLevel } from "../types/events.js";

const ANSI_RESET = "\u001b[0m";
const ANSI_GRAY = "\u001b[90m";
const ANSI_CYAN = "\u001b[36m";
const ANSI_YELLOW = "\u001b[33m";
const ANSI_RED = "\u001b[31m";

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

/**
 * Format a Date as HH:MM:SS using local time and zero-padding.
 */
function timeStamp(date = new Date()): string {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

/**
 * Logger implementation used across CassieCore.
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

  /** Create a child logger with a fixed component label that inherits the level. */
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
   * @param meta - optional structured metadata to append as JSON
   */
  debug(msg: string, meta?: Record<string, unknown>): void {
    if (!this.shouldLog("debug")) return;
    this.writeConsole("debug", msg, meta);
  }

  /**
   * Log an info-level message. Filtered by configured level.
   * @param msg - human-readable message
   * @param meta - optional structured metadata to append as JSON
   */
  info(msg: string, meta?: Record<string, unknown>): void {
    if (!this.shouldLog("info")) return;
    this.writeConsole("info", msg, meta);
  }

  /**
   * Log a warning-level message. Filtered by configured level.
   * @param msg - human-readable message
   * @param meta - optional structured metadata to append as JSON
   */
  warn(msg: string, meta?: Record<string, unknown>): void {
    if (!this.shouldLog("warn")) return;
    this.writeConsole("warn", msg, meta);
  }

  /**
   * Log an error-level message. Filtered by configured level.
   * @param msg - human-readable message
   * @param meta - optional structured metadata to append as JSON
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
   */
  private writeConsole(level: LogLevel, msg: string, meta?: Record<string, unknown>): void {
    const time = timeStamp();
    const upper = level.toUpperCase();
    const base = `[${time}] [${upper}] [${this.component}] ${msg}`;
    const line = meta && Object.keys(meta).length > 0 ? `${base} ${JSON.stringify(meta)}` : base;

    const colored = this.colorize(level, line);

    if (level === "warn" || level === "error") {
      // stderr
      // eslint-disable-next-line no-console
      console.error(colored + ANSI_RESET);
    } else {
      // stdout
      // eslint-disable-next-line no-console
      console.log(colored + ANSI_RESET);
    }
  }

  /**
   * Apply ANSI color codes to a log line for the given level.
   */
  private colorize(level: LogLevel, text: string): string {
    switch (level) {
      case "debug":
        return `${ANSI_GRAY}${text}`;
      case "info":
        return `${ANSI_CYAN}${text}`;
      case "warn":
        return `${ANSI_YELLOW}${text}`;
      case "error":
        return `${ANSI_RED}${text}`;
    }
  }
}

export const rootLogger = new Logger("core", "info");
