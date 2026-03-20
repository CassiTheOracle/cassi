/**
 * Core interface contracts for CassieCore modules.
 * All implementations must satisfy these shapes exactly.
 */

import type { EventType, EventOf, Unsubscribe, RuntimeEvent } from "./events.js";

// CassiCore interface types

export interface IEventBus {
  /** Emit a typed event to all registered listeners. Returns a promise that resolves when all handlers complete. */
  emit<T extends RuntimeEvent>(event: T): Promise<void>;

  /** Subscribe to a typed event. Returns an unsubscribe function. */
  on<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): Unsubscribe;

  /** Subscribe once — auto-unsubscribes after first fire */
  once<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): void;

  /** Remove a specific handler */
  off<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): void;

  /** Number of listeners currently registered */
  listenerCount(type: EventType): number;

  /** Subscribe to ALL events regardless of type. Returns an unsubscribe function. */
  onAll(handler: (event: RuntimeEvent) => void): Unsubscribe;

  /** Clear retained history for a single session (prevents memory leak). */
  clearSession?(sessionId: string): void;

  /** Number of sessions with active history buffers. */
  sessionHistoryCount?: number;

  /** Subscribe to session:ended and auto-clear session history buffers. */
  wireSessionCleanup?(): void;
}


export interface ILogger {
  debug(msg: string, meta?: Record<string, unknown>): void;
  info(msg: string, meta?: Record<string, unknown>): void;
  warn(msg: string, meta?: Record<string, unknown>): void;
  error(msg: string, meta?: Record<string, unknown>): void;

  /** Create a child logger with a fixed component label */
  child(component: string): ILogger;
}


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


export type PluginStatus = {
  id: string;
  status: "starting" | "healthy" | "crashed" | "restarting" | "stopped" | "stopping" | "degraded";
  crashes: number;
  startedAt: Date;
  lastCrashAt?: Date;
  /** PID of the child process (when alive) */
  pid?: number;
  /** Whether the circuit breaker has tripped */
  circuitOpen?: boolean;
  /** Health probe ping interval in ms (default: 10000) */
  healthProbeIntervalMs?: number;
  /** Health probe timeout before declaring worker dead (default: 30000) */
  healthProbeTimeoutMs?: number;
  /** Circuit breaker: crash window in ms (default: 300000 = 5 min) */
  circuitBreakerWindowMs?: number;
  /** Circuit breaker: max crashes allowed in window (default: 5) */
  circuitBreakerMaxCrashes?: number;
};

export interface PluginManifest {
  id: string;
  /** Absolute path to the worker module */
  entryPoint: string;
  restartOnCrash: boolean;
  maxRestarts: number;
  config?: Record<string, unknown>;
  /** If true, daemon status degrades when this worker is down */
  critical?: boolean;
  /** Health probe ping interval in ms (default: 10000) */
  healthProbeIntervalMs?: number;
  /** Health probe timeout before declaring worker dead (default: 30000) */
  healthProbeTimeoutMs?: number;
  /** Circuit breaker: crash window in ms (default: 300000 = 5 min) */
  circuitBreakerWindowMs?: number;
  /** Circuit breaker: max crashes allowed in window (default: 5) */
  circuitBreakerMaxCrashes?: number;
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
  shutdown(opts?: { restart?: boolean }): Promise<void>;
}


/**
 * Typed dependency bag for intelligence module wiring.
 * Replaces the old ModuleWiringSurface pattern of individual setX() methods.
 * All fields are optional — modules only receive the deps they need.
 */
export interface WiringDependencies {
  eventBus?: IEventBus;
  config?: IConfig;
  memory?: unknown;
  provider?: unknown;
  toolRegistry?: unknown;
  toolExecutor?: unknown;
  pipeline?: unknown;
  sessionManager?: unknown;
  sessionStore?: unknown;
  contextManager?: unknown;
  dialectic?: unknown;
  multiAgent?: unknown;
  droneSwarm?: unknown;
  modelRouter?: unknown;
  consequenceEstimator?: unknown;
  trustLedger?: unknown;
  injectionAggregator?: unknown;
  cognitiveBridge?: unknown;
  pipelineGetter?: () => unknown;
  repairProvider?: (prompt: string) => Promise<string>;
  introspectionSources?: {
    outcomeTracker?: unknown;
    strategyTracker?: unknown;
    crossSessionCorrelator?: unknown;
    providerProfiler?: unknown;
  };
}

/**
 * @deprecated Use WiringDependencies + wire() instead.
 * Kept for backward compatibility — will be removed in next major version.
 */
export interface ModuleWiringSurface {
  setEventBus?(bus: IEventBus): void;
  setMemory?(memory: unknown): void;
  setProvider?(provider: unknown): void;
  setConfig?(config: IConfig): void;
  setToolRegistry?(registry: unknown): void;
  setToolExecutor?(executor: unknown): void;
  setRepairProvider?(fn: (prompt: string) => Promise<string>): void;
  setContextManager?(contextManager: unknown): void;
  setDialectic?(dialectic: unknown): void;
  setMultiAgent?(multiAgent: unknown): void;
  setAutonomousLoop?(loop: unknown): void;
  setDigestStore?(store: unknown): void;
  setPipeline?(pipeline: unknown): void;
  setDroneSwarm?(droneSwarm: unknown): void;
  setModelRouter?(router: unknown): void;
  setSessionManager?(sessionManager: unknown, sessionStore?: unknown): void;
  setPipelineGetter?(getPipeline: () => unknown): void;
  setIntrospectionSources?(sources: {
    outcomeTracker?: unknown;
    strategyTracker?: unknown;
    crossSessionCorrelator?: unknown;
    providerProfiler?: unknown;
  }): void;
  setConsequenceEstimator?(estimator: unknown): void;
  setTrustLedger?(ledger: unknown): void;
  setInjectionAggregator?(aggregator: unknown): void;
}

export interface ThinkerDeferredWiring {
  setSessionManager(sessionManager: unknown, sessionStore?: unknown): void;
  setPipelineGetter(getPipeline: () => unknown): void;
}

export interface IntelligenceModule extends Partial<ModuleWiringSurface> {
  readonly name: string;
  /** Higher priority = runs first */
  readonly priority: number;

  /** Wire dependencies in one call — preferred over individual setX() methods. */
  wire?(deps: Partial<WiringDependencies>): void;

  /** Called for every runtime event (optional — implement for side effects) */
  onEvent?(event: RuntimeEvent): Promise<void>;

  /** Wire module to the event bus (called during daemon startup). */
  onEventBus?(bus: IEventBus): void;

  /** Start background processing (timers, subscriptions). */
  start?(): void;

  /** Stop background processing and release resources. */
  stop?(): void;
}
