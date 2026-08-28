/**
 * VENDORED TYPE STUB — mirrors `types/interfaces.js` (CassiCore) for @cassicore/constellation.
 *
 * Holds the interface surface Constellation uses (ILogger, IEventBus, IConfig,
 * IntelligenceModule, WiringDependencies) plus self-contained shims for the event types
 * that IEventBus.on/emit reference. The full CassiCore `events.js` federation type graph
 * lives in the daemon and is a future shared-foundation concern (MODULARIZATION §d).
 *
 * Self-contained: no imports from CassiCore.
 */

import type { RuntimeEvent, EventType, EventOf, Unsubscribe } from './events.js'

export type { RuntimeEvent, EventType, EventOf, Unsubscribe }

export interface IEventBus {
  emit<T extends RuntimeEvent>(event: T): Promise<void>
  on<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): Unsubscribe
  once<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): void
  off<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): void
  listenerCount(type: EventType): number
  onAll(handler: (event: RuntimeEvent) => void): Unsubscribe
  clearSession?(sessionId: string): void
  sessionHistoryCount?: number
  wireSessionCleanup?(): void
}

export interface ILogger {
  debug(msg: string, meta?: Record<string, unknown>): void
  info(msg: string, meta?: Record<string, unknown>): void
  warn(msg: string, meta?: Record<string, unknown>): void
  error(msg: string, meta?: Record<string, unknown>): void
  child(component: string): ILogger
}

export interface IConfig {
  get<T>(key: string, defaultVal?: T): T
  toJSON(): Record<string, unknown>
  watch(): void
  reload(): Promise<void>
  onChanged(key: string, cb: (newVal: unknown, oldVal: unknown) => void): Unsubscribe
}

export interface WiringDependencies {
  eventBus?: IEventBus
  config?: IConfig
  memory?: unknown
  provider?: unknown
  toolRegistry?: unknown
  toolExecutor?: unknown
  pipeline?: unknown
  sessionManager?: unknown
  sessionStore?: unknown
  contextManager?: unknown
  dialectic?: unknown
  multiAgent?: unknown
  modelRouter?: unknown
  consequenceEstimator?: unknown
  trustLedger?: unknown
  cognitiveBridge?: unknown
  globalBlackboardRegistry?: unknown
  pipelineGetter?: () => unknown
  repairProvider?: (prompt: string) => Promise<string>
  introspectionSources?: Record<string, unknown>
}

export interface IntelligenceModule {
  readonly name: string
  readonly priority: number
  wire?(deps: Partial<WiringDependencies>): void
  setEventBus?(bus: IEventBus): void
  setMemory?(memory: unknown): void
  setProvider?(provider: unknown): void
  setConfig?(config: IConfig): void
  setToolRegistry?(registry: unknown): void
  setToolExecutor?(executor: unknown): void
  setRepairProvider?(fn: (prompt: string) => Promise<string>): void
  setContextManager?(contextManager: unknown): void
  setDialectic?(dialectic: unknown): void
  setMultiAgent?(multiAgent: unknown): void
  setAutonomousLoop?(loop: unknown): void
  setDigestStore?(store: unknown): void
  setPipeline?(pipeline: unknown): void
  setModelRouter?(router: unknown): void
  setSessionManager?(sessionManager: unknown, sessionStore?: unknown): void
  setPipelineGetter?(getPipeline: () => unknown): void
  setIntrospectionSources?(sources: Record<string, unknown>): void
  setConsequenceEstimator?(estimator: unknown): void
  setTrustLedger?(ledger: unknown): void
  onEvent?(event: RuntimeEvent): Promise<void>
  onEventBus?(bus: IEventBus): void
  start?(): void
  stop?(): void
  setGlobalWorkspace?(workspace: unknown): void
  setCortex?(cortex: unknown): void
  setModelDirective?(directive: unknown): void
}
