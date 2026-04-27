import { mkdir, appendFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

type LogLevel = "debug" | "info" | "warn" | "error";

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
