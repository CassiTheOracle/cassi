import { Worker } from "node:worker_threads";

import { bus } from "../core/event-bus.js";

import type { IPluginHost, PluginManifest, PluginStatus , ILogger } from "../types/interfaces.js";

type HostMessage =
  | { type: "init"; config: Record<string, unknown> }
  | { type: "config:update"; config: Record<string, unknown> }
  | { type: "message"; payload: unknown }
  | { type: "shutdown" };

type WorkerMessage =
  | { type: "ready" }
  | { type: "message"; payload: unknown }
  | { type: "error"; message: string }
  | { type: "log"; level: string; message: string }
  | { type: "signal"; payload: Record<string, unknown> };

interface InternalWorkerRecord {
  manifest: PluginManifest;
  worker?: Worker;
  status: PluginStatus;
  restartTimer?: NodeJS.Timeout;
}

/**
 * PluginHost manages the lifecycle of plugin workers (one Worker per plugin).
 */
export class PluginHost implements IPluginHost {
  private workers: Map<string, InternalWorkerRecord> = new Map();

  constructor(private logger: ILogger) { }

  /**
   * Load and start a plugin worker
   */
  async load(manifest: PluginManifest): Promise<void> {
    if (this.workers.has(manifest.id)) {
      this.logger.warn(`plugin ${manifest.id} already loaded`);
      return;
    }

    const status: PluginStatus = {
      id: manifest.id,
      status: "starting",
      crashes: 0,
      startedAt: new Date(),
    };

    const record: InternalWorkerRecord = { manifest, status };
    this.workers.set(manifest.id, record);

    await this.spawnWorker(record);
  }

  private spawnWorker(record: InternalWorkerRecord): Promise<void> {
    return new Promise((resolve, reject) => {
      const { manifest } = record;
      this.logger.info(`spawning worker for ${manifest.id}`, { entry: manifest.entryPoint });

      const worker = new Worker(manifest.entryPoint, { eval: false });
      record.worker = worker;

      const initMsg: HostMessage = { type: "init", config: manifest.config ?? {} };

      let ready = false;
      const readyTimeout = setTimeout(() => {
        if (!ready) {
          this.logger.error(`plugin ${manifest.id} failed to become ready in time`);
          reject(new Error("ready timeout"));
        }
      }, 10000);

      const cleanup = () => {
        worker.removeAllListeners();
      };

      worker.on("message", (m: WorkerMessage) => {
        if (m.type === "ready") {
          ready = true;
          clearTimeout(readyTimeout);
          record.status.status = "healthy";
          record.status.startedAt = record.status.startedAt ?? new Date();
          this.logger.info(`plugin ${manifest.id} ready`);
          bus.emit({ type: "plugin:loaded", pluginId: manifest.id });
          resolve();
          return;
        }

        if (m.type === "message") {
          bus.emit({ type: "worker:message", pluginId: manifest.id, payload: m.payload });
        }

        if (m.type === "error") {
          // Handle both { type: "error", message } and { type: "error", payload: { message } }
          // Use type narrowing to safely access properties
          const errorMsg = 'message' in m ? m.message : ('payload' in m ? (m as any).payload?.message : 'unknown error');
          this.logger.error(`worker ${manifest.id} error: ${errorMsg}`);
        }

        if (m.type === "log") {
          // Forward structured log messages from workers to the daemon bus.
          // The daemon's worker:message handler routes these to the system logger.
          bus.emit({ type: "worker:message", pluginId: manifest.id, payload: m });
        }

        if (m.type === "signal") {
          // Flatten signal payload so daemon can handle: { type, sessionId, signalType, content }
          bus.emit({ type: "worker:message", pluginId: manifest.id, payload: { type: "signal", ...m.payload } });
        }
      });

      worker.on("error", (err) => {
        this.handleCrash(record, err instanceof Error ? err.message : String(err));
      });

      worker.on("exit", (code) => {
        if (code !== 0) {
          this.handleCrash(record, `exit code ${code}`);
        } else {
          // graceful exit
          record.status.status = "stopped";
          this.logger.info(`worker ${manifest.id} exited gracefully`);
          bus.emit({ type: "plugin:stopped", pluginId: manifest.id, reason: "manual" });
        }
        cleanup();
      });

      // send init after attaching handlers
      try {
        worker.postMessage(initMsg as HostMessage);
      } catch (err) {
        clearTimeout(readyTimeout);
        reject(err);
      }
    });
  }

  private handleCrash(record: InternalWorkerRecord, errorMsg: string) {
    const { manifest } = record;
    record.status.crashes += 1;
    record.status.lastCrashAt = new Date();
    record.status.status = "crashed";
    this.logger.error(`plugin ${manifest.id} crashed: ${errorMsg}`, { crashes: record.status.crashes });
    bus.emit({ type: "plugin:crashed", pluginId: manifest.id, error: errorMsg, crashCount: record.status.crashes });

    // Terminate the old worker if it still exists
    const oldWorker = record.worker;
    if (oldWorker) {
      record.worker = undefined;
      oldWorker.removeAllListeners();
      oldWorker.terminate().catch(() => {
        // Ignore termination errors - worker may already be dead
      });
    }

    const crashes = record.status.crashes;
    if (manifest.restartOnCrash && crashes < manifest.maxRestarts) {
      const backoff = Math.min(1000 * Math.pow(2, crashes - 1), 30000);
      this.logger.info(`scheduling restart for ${manifest.id} in ${backoff}ms`);
      record.status.status = "restarting";
      record.restartTimer = setTimeout(() => {
        this.logger.info(`restarting plugin ${manifest.id} (attempt ${crashes + 1})`);
        this.spawnWorker(record).then(() => {
          bus.emit({ type: "plugin:restarted", pluginId: manifest.id, attempt: crashes + 1 });
        }).catch((err) => {
          this.logger.error(`failed to restart ${manifest.id}: ${String(err)}`);
        });
      }, backoff);
    } else {
      this.logger.warn(`plugin ${manifest.id} reached max restarts or not configured to restart`);
      record.status.status = "stopped";
      bus.emit({ type: "plugin:stopped", pluginId: manifest.id, reason: "max-restarts" });
    }
  }

  /**
   * Gracefully unload a plugin worker
   */
  async unload(pluginId: string): Promise<void> {
    const record = this.workers.get(pluginId);
    if (!record) return;

    if (record.restartTimer) {
      clearTimeout(record.restartTimer);
      record.restartTimer = undefined;
    }

    if (!record.worker) {
      this.workers.delete(pluginId);
      this.logger.info(`plugin ${pluginId} unloaded (was not active)`);
      return;
    }

    const w = record.worker;
    record.worker = undefined;

    try {
      try {
        w.postMessage({ type: "shutdown" } as HostMessage);
      } catch (e) {
        this.logger.warn(`failed to send shutdown to ${pluginId}`);
      }

      // terminate after 2s if still alive
      await Promise.race([
        new Promise<void>((res) => w.once("exit", () => res())),
        new Promise<void>((res) => setTimeout(res, 2000)),
      ]);

      try {
        await w.terminate();
      } catch (e) {
        // ignore
      }
    } finally {
      this.workers.delete(pluginId);
      this.logger.info(`plugin ${pluginId} unloaded`);
    }
  }

  /**
   * Restart a specific plugin
   */
  async restart(pluginId: string): Promise<void> {
    const record = this.workers.get(pluginId);
    if (!record) throw new Error("unknown plugin");

    await this.unload(pluginId);
    // reset status
    record.status = {
      id: pluginId,
      status: "starting",
      crashes: 0,
      startedAt: new Date(),
    };
    this.workers.set(pluginId, record);
    await this.spawnWorker(record);
    bus.emit({ type: "plugin:restarted", pluginId, attempt: 1 });
  }

  /**
   * Get status for a specific plugin
   */
  status(pluginId: string) {
    const r = this.workers.get(pluginId);
    return r?.status;
  }

  /**
   * Get status for all loaded plugins
   */
  all() {
    return Array.from(this.workers.values()).map((r) => r.status);
  }

  /**
   * Push a config update to a worker without restarting it
   */
  updateConfig(pluginId: string, config: Record<string, unknown>): void {
    const record = this.workers.get(pluginId);
    if (!record || !record.worker || record.status.status !== "healthy") {
      this.logger.warn(`skipping config update for ${pluginId} — not healthy`);
      return;
    }
    try {
      record.worker.postMessage({ type: "config:update", config } as HostMessage);
    } catch (e) {
      this.logger.error(`failed to send config update to ${pluginId}: ${String(e)}`);
    }
  }

  /**
   * Send a typed message to a worker
   */
  send(pluginId: string, payload: unknown): void {
    const record = this.workers.get(pluginId);
    if (!record || !record.worker) {
      this.logger.warn(`cannot send to ${pluginId} — not loaded`);
      return;
    }
    try {
      record.worker.postMessage({ type: "message", payload } as HostMessage);
    } catch (e) {
      this.logger.error(`failed to send message to ${pluginId}: ${String(e)}`);
    }
  }

  /**
   * Gracefully shut down all workers
   */
  async shutdown(): Promise<void> {
    const ids = Array.from(this.workers.keys());
    await Promise.all(ids.map((id) => this.unload(id)));
  }
}
