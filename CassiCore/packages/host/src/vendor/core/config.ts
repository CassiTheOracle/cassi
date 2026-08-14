/**
 * core/config.ts
 * CassieCore Config implementation.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import { bus } from "@cassicore/events";
import { rootLogger } from "@cassicore/events";

const logger = rootLogger.child('config');

import type { Unsubscribe } from "@cassicore/foundation";
import type { IConfig } from "@cassicore/foundation";

const readFile = promisify(fs.readFile);
const writeFile = promisify(fs.writeFile);
const mkdir = promisify(fs.mkdir);

const DEFAULT_CONFIG = {
  daemon: { logLevel: "info" },
  logging: {
    maxFileSize: 10 * 1024 * 1024, // 10MB default
    maxFiles: 5,
  },
  providers: {},
  channels: {},
    intelligence: {
    memory: { enabled: true },
    thinker: { enabled: true },
    backgroundEmbedding: { enabled: false },
    // Overhaul defaults (2026-08-13 owner directive): every Cassi Mind
    // mechanism is ON by default during the continuous-measurement period.
    // Off-states remain for A/B baselines; pre-registered verdicts (Stage-2
    // HOLD etc.) remain on record and still govern any eventual production
    // default. These are only consulted where a code path reads them from
    // config — the pure-internal class defaults live on MnemicField itself.
    mnemicField: {
      // §20 H4 merge journal (observation-only; path set in daemon boot).
      mergeJournal: true,
    },
    consolidation: { tiered: 'cascade' },
    fieldBridge: {
      // TCP drainer to the GPU field engine. enabled=true is the overhaul
      // default; bail on a stock config only if the operator flips it.
      enabled: true,
      host: '127.0.0.1',
      port: 7599,
    },
    thalamus: { gateComposite: 'cascade' },
  },
  tools: {
    allowedPaths: [
      path.join(os.homedir(), 'workspaces'),
      path.join(os.homedir(), '.cassicore'),
      path.join(os.homedir(), '.cassi'),
      path.join(os.homedir(), '.config'),
      '/tmp',
      process.cwd(),
    ],
    networkAllowlist: ['*'],
  },
  mcp: {
    servers: [
      {
        id: 'serena',
        command: 'node',
        args: ['mcp/serena-server.js'],
        restartOnCrash: true,
        maxRestarts: 5,
        startupTimeoutMs: 5000,
        description: 'Local Serena MCP shim for file operations',
      },
      {
        id: 'duckduckgo',
        command: 'uvx',
        args: ['duckduckgo-mcp-server'],
        restartOnCrash: true,
        maxRestarts: 3,
        startupTimeoutMs: 10000,
        description: 'DuckDuckGo search and content fetching',
      },
    ],
  },
} as const;

/**
 * @dep callers: flatten (core/config.ts), mergeDeep (core/config.ts), handleProvidersRoutes (core/admin-api/providers.ts), get (core/config.ts)
 * @dep module: Cluster_159
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * @dep callers: flatten (core/config.ts), diffObjects (core/config.ts)
 * @dep calls: flatten, isObject
 * @dep module: Cluster_159
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function flatten(obj: Record<string, unknown>, prefix = ""): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (isObject(v)) {
      Object.assign(out, flatten(v as Record<string, unknown>, key));
    } else {
      out[key] = v;
    }
  }
  return out;
}

/** Diff two objects and return changed keys with old/new values */
function diffObjects(oldObj: Record<string, unknown>, newObj: Record<string, unknown>) {
  const oldFlat = flatten(oldObj);
  const newFlat = flatten(newObj);
  const keys = new Set<string>([...Object.keys(oldFlat), ...Object.keys(newFlat)]);
  const changes: Array<{ key: string; oldVal: unknown; newVal: unknown }> = [];
  for (const k of keys) {
    const a = Object.prototype.hasOwnProperty.call(oldFlat, k) ? oldFlat[k] : undefined;
    const b = Object.prototype.hasOwnProperty.call(newFlat, k) ? newFlat[k] : undefined;
    const same = (() => {
      // simple deep equality for primitives and JSON-serializable values
      try {
        return JSON.stringify(a) === JSON.stringify(b);
      } catch {
        return a === b;
      }
    })();
    if (!same) {
      changes.push({ key: k, oldVal: a, newVal: b });
    }
  }
  return changes;
}

export class Config implements IConfig {
  private filePath: string;
  private data: Record<string, unknown>;
  private watcher?: fs.FSWatcher;
  private changeHandlers: Map<string, Set<(newVal: unknown, oldVal: unknown) => void>> = new Map();
  private debounceTimer?: NodeJS.Timeout;

  private constructor(filePath: string, data: Record<string, unknown>) {
    this.filePath = filePath;
    this.data = data;
  }

  /** Load or create config file and return Config instance */
  static async load(configPath?: string): Promise<Config> {
    const defaultPath = path.join(os.homedir(), ".cassicore", "config.json");
    const resolved = configPath ? path.resolve(configPath) : defaultPath;

    const dir = path.dirname(resolved);
    try {
      await mkdir(dir, { recursive: true });
    } catch (err) {
      logger.debug('Config directory creation failed', { path: dir, error: String(err) });
    }

    try {
      await readFile(resolved, { encoding: "utf8" });
    } catch (err) {
      try {
        await writeFile(resolved, JSON.stringify(DEFAULT_CONFIG, null, 2), { encoding: "utf8" });
      } catch (e) {
        logger.warn('Config file write failed - proceeding with in-memory config', { 
          path: resolved, 
          error: String(e) 
        });
      }
    }

    let content = "";
    let parsed: Record<string, unknown> = {};
    try {
      content = await readFile(resolved, { encoding: "utf8" });
      // HOW: Try JSON first, then YAML based on file extension
      const ext = path.extname(resolved).toLowerCase();
      if (ext === '.json') {
        parsed = JSON.parse(content) as Record<string, unknown>;
      } else if (ext === '.yaml' || ext === '.yml') {
        const yaml = (await import('yaml')).default;
        parsed = yaml.parse(content) as Record<string, unknown>;
      } else {
        // Unknown extension - try JSON, then YAML
        try {
          parsed = JSON.parse(content) as Record<string, unknown>;
        } catch {
          const yaml = (await import('yaml')).default;
          parsed = yaml.parse(content) as Record<string, unknown>;
        }
      }
    } catch (err) {
      // JSON/YAML parse error or read error — fallback to defaults
      parsed = JSON.parse(JSON.stringify(DEFAULT_CONFIG));
    }

    const expanded = expandEnvVars(parsed) as Record<string, unknown>;

    const merged = mergeDeep(DEFAULT_CONFIG as Record<string, unknown>, expanded);

    return new Config(resolved, merged);
  }

  /**
   * Get a configuration value by dot-path.
   * @param key - Dot-separated path (e.g., "daemon.logLevel")
   * @param defaultVal - Default value if key is not found
   * @returns The configuration value, or defaultVal if not found
   */
  get<T>(key: string, defaultVal?: T): T {
    if (!key) {
      // WHY: return entire config
      return (this.data as unknown) as T;
    }
    const parts = key.split(".");
    let cur: unknown = this.data;
    for (const p of parts) {
      if (isObject(cur) && Object.prototype.hasOwnProperty.call(cur, p)) {
        cur = (cur as Record<string, unknown>)[p];
      } else {
        return (defaultVal as T);
      }
    }
    return (cur as T);
  }

  /**
   * Serialize the config to a plain object.
   * @returns A deep clone of the configuration data
   */
  toJSON(): Record<string, unknown> {
    // WHY: returns a shallow clone to avoid accidental mutation
    return JSON.parse(JSON.stringify(this.data)) as Record<string, unknown>;
  }

  /**
   * Start watching the config file for changes.
   * Emits 'config:changed' events when values change and 'config:reloaded' when complete.
   */
  watch(): void {
    if (this.watcher) return;
    try {
      this.watcher = fs.watch(this.filePath, { persistent: false }, () => {
        // HOW: debounce rapid file changes with 100ms timeout
        if (this.debounceTimer) clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
          void this.reload();
        }, 100);
      });
    } catch (err) {
      logger.warn('Config watcher start failed', { path: this.filePath, error: String(err) });
    }
  }

  /**
   * Reload configuration from disk and emit change events.
   * Compares new values with current and emits 'config:changed' for each diff.
   */
  async reload(): Promise<void> {
    let content = "";
    let parsed: Record<string, unknown> = {};
    try {
      content = await readFile(this.filePath, { encoding: "utf8" });
      parsed = JSON.parse(content) as Record<string, unknown>;
    } catch (err) {
      // HOW: On parse/read error, keep current data and emit no changes to avoid corrupting state
      return;
    }

    const merged = mergeDeep(DEFAULT_CONFIG as Record<string, unknown>, parsed);
    const old = this.toJSON();
    const changes = diffObjects(old, merged);

    this.data = merged;

    // HOW: emit per-change events first, then call registered handlers
    for (const c of changes) {
      bus.emit({ type: "config:changed", key: c.key, oldVal: c.oldVal, newVal: c.newVal });
      const handlers = this.changeHandlers.get(c.key);
      if (handlers) {
        for (const h of Array.from(handlers)) {
          try {
            h(c.newVal, c.oldVal);
          } catch (err) {
            logger.debug('Config change handler error', { key: c.key, error: String(err) });
          }
        }
      }
    }

    bus.emit({ type: "config:reloaded" });
  }

  /**
   * Register a callback for a specific configuration key change.
   * @param key - Dot-separated path to watch (e.g., "daemon.logLevel")
   * @param cb - Callback invoked with (newVal, oldVal) when the key changes
   * @returns Unsubscribe function to remove the listener
   */
  onChanged(key: string, cb: (newVal: unknown, oldVal: unknown) => void): Unsubscribe {
    const set = this.changeHandlers.get(key) ?? new Set();
    set.add(cb);
    this.changeHandlers.set(key, set);
    return () => {
      const s = this.changeHandlers.get(key);
      if (!s) return;
      s.delete(cb);
      if (s.size === 0) this.changeHandlers.delete(key);
    };
  }

  /**
   * Stop watching the config file and clean up resources.
   * Removes the file watcher and clears any pending debounce timers.
   */
  stopWatching(): void {
    if (this.watcher) {
      this.watcher.close();
      this.watcher = undefined;
    }
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = undefined;
    }
  }
}

/** Keys that could pollute Object prototype — reject during merge */
const UNSAFE_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

/** Deep merge of two plain objects. src takes precedence over target */
/**
 * @dep callers: mergeDeep (core/config.ts), handleProvidersRoutes (core/admin-api/providers.ts), load (core/config.ts), reload (core/config.ts)
 * @dep calls: has, mergeDeep, isObject
 * @dep module: Cluster_160
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

function mergeDeep(target: Record<string, unknown>, src: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = JSON.parse(JSON.stringify(target));
  for (const [k, v] of Object.entries(src)) {
    if (UNSAFE_KEYS.has(k)) continue; // WHY: prevent prototype pollution attacks
    if (isObject(v) && isObject(out[k] as unknown)) {
      out[k] = mergeDeep(out[k] as Record<string, unknown>, v as Record<string, unknown>);
    } else {
      out[k] = v;
    }
  }
  return out;
}

/**
 * Expand environment variables in config values
 * Supports ${VAR} and $VAR syntax
 * @dep callers: expandEnvVars (core/config.ts), load (core/config.ts)
 * @dep calls: expandEnvVars
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function expandEnvVars(obj: unknown): unknown {
  if (typeof obj === 'string') {
    // HOW: two-pass replacement - ${VAR} first, then $VAR to avoid double-expansion
    let result = obj.replace(/\$\{([^}]+)\}/g, (_, name) => {
      return process.env[name] ?? '';
    });
    result = result.replace(/\$([A-Za-z_][A-Za-z0-9_]*)/g, (_, name) => {
      return process.env[name] ?? '';
    });
    return result;
  }

  if (Array.isArray(obj)) {
    return obj.map(item => expandEnvVars(item));
  }

  if (obj !== null && typeof obj === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
      result[key] = expandEnvVars(value);
    }
    return result;
  }

  return obj;
}
