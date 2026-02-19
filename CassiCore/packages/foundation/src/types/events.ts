/**
 * All typed events that flow through the ClaraCore EventBus.
 * Every module communicates exclusively through these types.
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

export type RuntimeEvent =
  | { type: "daemon:ready"; startedAt: Date }
  | { type: "daemon:shutdown"; reason: string }
  | { type: "turn:start"; sessionId: string; message: string; timestamp: Date }
  | { type: "turn:end"; sessionId: string; response: string; durationMs: number }
  | { type: "plugin:loaded"; pluginId: string }
  | { type: "plugin:crashed"; pluginId: string; error: string; crashCount: number }
  | { type: "plugin:restarted"; pluginId: string; attempt: number }
  | { type: "plugin:stopped"; pluginId: string; reason: "max-restarts" | "manual" }
  | { type: "config:changed"; key: string; oldVal: unknown; newVal: unknown }
  | { type: "config:reloaded" }
  | { type: "worker:message"; pluginId: string; payload: unknown };

export type EventType = RuntimeEvent["type"];

/** Extract the event shape for a given type literal */
export type EventOf<T extends EventType> = Extract<RuntimeEvent, { type: T }>;

/** Unsubscribe function returned by EventBus.on() */
export type Unsubscribe = () => void;
