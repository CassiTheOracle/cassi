import { mkdir, appendFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

type LogLevel = "debug" | "info" | "warn" | "error";

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const MIN_LEVEL: LogLevel =
  (process.env.CASSICORE_LOG_LEVEL as LogLevel) ?? "info";

interface IntegrationLogger {
  debug(message: string, meta?: Record<string, unknown>): void;
  info(message: string, meta?: Record<string, unknown>): void;
  warn(message: string, meta?: Record<string, unknown>): void;
  error(message: string, meta?: Record<string, unknown>): void;
  child(component: string): IntegrationLogger;
}

class CassiCoreFileLogger implements IntegrationLogger {
  constructor(private readonly component: string) {}

  child(component: string): IntegrationLogger {
    return new CassiCoreFileLogger(`${this.component}:${component}`);
  }

  debug(message: string, meta?: Record<string, unknown>): void {
    this.write("debug", message, meta);
  }

  info(message: string, meta?: Record<string, unknown>): void {
    this.write("info", message, meta);
  }

  warn(message: string, meta?: Record<string, unknown>): void {
    this.write("warn", message, meta);
  }

  error(message: string, meta?: Record<string, unknown>): void {
    this.write("error", message, meta);
  }

  private write(level: LogLevel, message: string, meta?: Record<string, unknown>): void {
    if (LEVEL_PRIORITY[level] < LEVEL_PRIORITY[MIN_LEVEL]) return;
    void (async () => {
      const dir = join(homedir(), ".cassicore");
      await mkdir(dir, { recursive: true });
      const line = JSON.stringify({
        timestamp: new Date().toISOString(),
        level,
        component: this.component,
        message,
        meta: meta ?? {},
      });
      await appendFile(join(dir, "daemon.log"), `${line}\n`, "utf8");
    })().catch(() => {});
  }
}

export const integrationLogger = new CassiCoreFileLogger("claude-code");
