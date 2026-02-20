/**
 * Core interface contracts for CassieCore modules.
 * All implementations must satisfy these shapes exactly.
 */

import type { EventType, EventOf, Unsubscribe, RuntimeEvent, LogLevel } from "./events.js";

// ─── EventBus ────────────────────────────────────────────────────────────────

export interface IEventBus {
  /** Emit a typed event to all registered listeners */
  emit<T extends RuntimeEvent>(event: T): void;

  /** Subscribe to a typed event. Returns an unsubscribe function. */
  on<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): Unsubscribe;

  /** Subscribe once — auto-unsubscribes after first fire */
  once<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): void;

  /** Remove a specific handler */
  off<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): void;

  /** Number of listeners currently registered */
  listenerCount(type: EventType): number;
}

// ─── Logger ──────────────────────────────────────────────────────────────────

export interface ILogger {
  debug(msg: string, meta?: Record<string, unknown>): void;
  info(msg: string, meta?: Record<string, unknown>): void;
  warn(msg: string, meta?: Record<string, unknown>): void;
  error(msg: string, meta?: Record<string, unknown>): void;

  /** Create a child logger with a fixed component label */
  child(component: string): ILogger;
}

// ─── Config ──────────────────────────────────────────────────────────────────

export interface IConfig {
  /** Get a config value by dot-path key (e.g. "daemon.logLevel") */
  get<T>(key: string, defaultVal?: T): T;

  /** Get the full config object */
  toJSON(): Record<string, unknown>;

  /** Start watching the config file for changes (hot-reload) */
  watch(): void;

  /** Manually trigger a reload */
  reload(): Promise<void>;

  /** Register a callback for when a specific key changes */
  onChanged(key: string, cb: (newVal: unknown, oldVal: unknown) => void): Unsubscribe;
}

// ─── PluginHost ───────────────────────────────────────────────────────────────

export type PluginStatus = {
  id: string;
  status: "starting" | "healthy" | "crashed" | "restarting" | "stopped";
  crashes: number;
  startedAt: Date;
  lastCrashAt?: Date;
};

export interface PluginManifest {
  id: string;
  /** Absolute path to the worker module */
  entryPoint: string;
  restartOnCrash: boolean;
  maxRestarts: number;
  config?: Record<string, unknown>;
}

export interface IPluginHost {
  /** Load and start a plugin worker */
  load(manifest: PluginManifest): Promise<void>;

  /** Gracefully unload a plugin worker */
  unload(pluginId: string): Promise<void>;

  /** Restart a specific plugin */
  restart(pluginId: string): Promise<void>;

  /** Get status for a specific plugin */
  status(pluginId: string): PluginStatus | undefined;

  /** Get status for all loaded plugins */
  all(): PluginStatus[];

  /** Push a config update to a worker without restarting it */
  updateConfig(pluginId: string, config: Record<string, unknown>): void;

  /** Send a typed message to a worker */
  send(pluginId: string, payload: unknown): void;

  /** Gracefully shut down all workers */
  shutdown(): Promise<void>;
}

// ─── Intelligence Module ─────────────────────────────────────────────────────

export interface IntelligenceModule {
  readonly name: string;
  /** Higher priority = runs first */
  readonly priority: number;

  /** Called for every runtime event (optional — implement for side effects) */
  onEvent?(event: RuntimeEvent): Promise<void>;
}
