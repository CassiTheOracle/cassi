/**
 * All typed events that flow through the CassieCore EventBus.
 * Every module communicates exclusively through these types.
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

export type HealthStatus = "ok" | "degraded" | "down";

export type RuntimeEvent =
  | { type: "daemon:ready"; startedAt: Date }
  | { type: "daemon:shutdown"; reason: string }
  | {
      type: "daemon:health";
      overall: HealthStatus;
      checks: Array<{ name: string; status: HealthStatus }>;
      memoryMb: number;
      uptimeMs: number;
      eventLoopLagMs: number;
      timestamp: Date;
    }
  | { type: "turn:start"; sessionId: string; message: string; timestamp: Date }
  | { type: "turn:end"; sessionId: string; response: string; durationMs: number }
  | { type: "plugin:loaded"; pluginId: string }
  | { type: "plugin:crashed"; pluginId: string; error: string; crashCount: number }
  | { type: "plugin:restarted"; pluginId: string; attempt: number }
  | { type: "plugin:stopped"; pluginId: string; reason: "max-restarts" | "manual" }
  | { type: "config:changed"; key: string; oldVal: unknown; newVal: unknown }
  | { type: "config:reloaded" }
  | { type: "config:override:set"; key: string; value: unknown; meta?: object }
  | { type: "config:override:cleared"; key: string }
  | { type: "worker:message"; pluginId: string; payload: unknown }
  // Centralized provider events
  | { type: "provider:request_start"; providerId: string; requestId: string; sessionId: string; model: string; messageCount: number }
  | { type: "provider:request_end"; providerId: string; requestId: string; sessionId: string; tokensUsed: number; durationMs: number; error?: string }
  | { type: "provider:request_error"; providerId: string; requestId: string; sessionId: string; error: string; consecutiveErrors: number }
  | { type: "provider:request_aborted"; providerId: string; requestId: string; sessionId: string }
  | { type: "provider:deduplicated"; providerId: string; sessionId: string; existingRequestId: string }
  | { type: "provider:rate_limited"; providerId: string; sessionId: string; retryAfterMs: number };

export type EventType = RuntimeEvent["type"];

/** Extract the event shape for a given type literal */
export type EventOf<T extends EventType> = Extract<RuntimeEvent, { type: T }>;

/** Unsubscribe function returned by EventBus.on() */
export type Unsubscribe = () => void;
