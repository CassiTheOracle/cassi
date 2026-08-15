import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import type { Unsubscribe } from "@cassicore/foundation";
import type { IConfig, IEventBus, ILogger } from "@cassicore/foundation";
// CassiCore runtime config

const writeFile = promisify(fs.writeFile);
const mkdir = promisify(fs.mkdir);

export interface ILayeredConfig extends IConfig {
  setOverride(key: string, value: unknown, meta?: { reason?: string; setBy?: string }): Promise<void>;
  clearOverride(key: string): Promise<void>;
  getOverrides(): Record<string, { value: unknown; setAt: number; meta?: object }>;
  persistOverrides(): Promise<void>;
  loadPersistedOverrides(): Promise<void>;
  getWithSource(key: string): { value: unknown; source: "override" | "env" | "file" | "default" };
}

/**
 * @dep callers: runtime-config.test.ts (tests/runtime-config.test.ts), start (core/daemon.ts)
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function createLayeredConfig(base: IConfig, busInst?: IEventBus, logger?: ILogger): ILayeredConfig {
  const overrides: Record<string, { value: unknown; setAt: number; meta?: object }> = {};
  const overridesPath = path.join(os.homedir(), ".cassicore", "runtime-overrides.json");
  const tmpPath = `${overridesPath  }.tmp`;

  async function setOverride(key: string, value: unknown, meta?: { reason?: string; setBy?: string }) {
    const now = Date.now();
    const prev = (overrides as any)[key]?.value;
    overrides[key] = { value, setAt: now, meta };
    await busInst?.emit({ type: "config:override:set", key, value, meta });
    // also emit config:changed for downstream watchers
    await busInst?.emit({ type: "config:changed", key, oldVal: prev, newVal: value });
  }

  async function clearOverride(key: string) {
    const had = Object.prototype.hasOwnProperty.call(overrides, key);
    if (!had) return;
    delete overrides[key];
    await busInst?.emit({ type: "config:override:cleared", key });
  }

  function getOverrides() {
    // shallow clone
    return JSON.parse(JSON.stringify(overrides)) as Record<string, { value: unknown; setAt: number; meta?: object }>;
  }

  async function persistOverrides() {
    // ensure dir
    try {
      await mkdir(path.dirname(overridesPath), { recursive: true });
    } catch (err) {
      // ignore
    }
    const body = JSON.stringify(overrides, null, 2);
    // atomic write: write tmp then rename
    await writeFile(tmpPath, body, { encoding: "utf8" });
    await fs.promises.rename(tmpPath, overridesPath);
  }

  async function loadPersistedOverrides() {
    try {
      const content = await fs.promises.readFile(overridesPath, { encoding: "utf8" });
      const parsed = JSON.parse(content) as Record<string, { value: unknown; setAt: number; meta?: object }>;
      for (const [k, v] of Object.entries(parsed)) {
        overrides[k] = v;
        await busInst?.emit({ type: "config:override:set", key: k, value: v.value, meta: v.meta });
      }
    } catch (err) {
      // ignore if missing or parse error
    }
  }

  function getWithSource(key: string) {
    // 1. runtime override
    if (Object.prototype.hasOwnProperty.call(overrides, key)) {
      return { value: overrides[key].value, source: "override" as const };
    }
    // 2. env var — try uppercase with dots -> _
    const envKey = key.replace(/\./g, "_").toUpperCase();
    if (Object.prototype.hasOwnProperty.call(process.env, envKey)) {
      return { value: process.env[envKey], source: "env" as const };
    }
    // 3. file config
    const fileVal = base.get(key, undefined);
    if (typeof fileVal !== "undefined") return { value: fileVal, source: "file" as const };
    // 4. default — call base.get with no default to get maybe whole config? fallback undefined
    return { value: base.get(key, undefined), source: "default" as const };
  }

  const layered: ILayeredConfig = {
    get<T>(key: string, defaultVal?: T) {
      const res = getWithSource(key);
      if (typeof res.value === "undefined") return (defaultVal as T);
      return res.value as T;
    },
    toJSON() {
      // merge file config with overrides and env (overrides highest, then env, then file)
      const baseObj = base.toJSON();
      const flat: Record<string, unknown> = {};
      // flatten base
      function flatten(obj: Record<string, unknown>, prefix = "") {
        for (const [k, v] of Object.entries(obj)) {
          const key = prefix ? `${prefix}.${k}` : k;
          if (typeof v === "object" && v !== null && !Array.isArray(v)) {
            flatten(v as Record<string, unknown>, key);
          } else {
            flat[key] = v as unknown;
          }
        }
      }
      flatten(baseObj as Record<string, unknown>);
      // apply env
      for (const [k, v] of Object.entries(process.env)) {
        const possible = k.toLowerCase().replace(/_/g, ".");
        if (Object.prototype.hasOwnProperty.call(flat, possible)) {
          flat[possible] = v as unknown;
        }
      }
      // apply overrides
      for (const [k, v] of Object.entries(overrides)) {
        flat[k] = v.value;
      }
      // unflatten to nested object
      const out: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(flat)) {
        const parts = k.split(".");
        let cur = out;
        for (let i = 0; i < parts.length; i++) {
          const p = parts[i];
          if (i === parts.length - 1) {
            cur[p] = v;
          } else {
            if (!cur[p] || typeof cur[p] !== "object") cur[p] = {};
            cur = cur[p] as Record<string, unknown>;
          }
        }
      }
      return out;
    },
    watch() {
      // delegate to base watch if available
      try {
        base.watch();
      } catch {
        // ignore
      }
    },
    async reload() {
      await base.reload();
    },
    onChanged(key: string, cb: (newVal: unknown, oldVal: unknown) => void): Unsubscribe {
      return base.onChanged(key, cb);
    },
    setOverride,
    clearOverride,
    getOverrides,
    persistOverrides,
    loadPersistedOverrides,
    getWithSource,
  };

  return layered;
}
