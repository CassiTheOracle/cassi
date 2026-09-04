/**
 * @cassicore/mind-runtime — composition root (boot.ts).
 *
 * Recreates the RETAINED slice of the daemon's boot wiring (plan §5 verdict 26:
 * "the composition that builds MnemicField + injections") MINUS providers/sessions/
 * CLI/ACP/admin-api. Specifically excluded (plan §5 verdicts 22-31): createAdminApi,
 * createBridge, CommandDispatcher, channel workers, PluginHost, createModelRouter/
 * providers, SessionPipeline/TurnPipeline, PID-file singleton enforcement, config
 * watcher, .env secrets loader, budget tracker, ModelDirective. The retained core
 * HERE is: paths ports, the intelligence layer (createIntelligence), the orchestration
 * bus, MnemicField + its injections, the unified intelligence loop, and the retained
 * mind-tool deps (collectThoughtsDeps / peerToolDeps) wired into
 * `registerMindTools` (the P3 retained-mind seam from @cassicore/tools).
 *
 * Model access (P4 boundary): this phase boots the retained mind with NO live LLM
 * handles. The daemon's setMeditationHandleFactory / setCorpusLLMProvider /
 * setBrainstemLLMProvider calls are P4 cutover (task-agents / mind_complete), so the
 * P3 runtime's provider-facing loops simply never fire. The retained `ModelHandle`
 * cast seam is defined in @cassicore/model-pool for P4 to inject the mind_complete
 * backed handle.
 *
 * Config: read directly from `CASSICORE_HOME` + env (no Config watcher / layered
 * config — brief Open Item 10). The retained defaults mirror the daemon's
 * `intelligence.*` defaults.
 */

import { homedir } from 'node:os'
import path from 'node:path'

import { setRootResolver, type IConfig, type IEventBus, type ILogger, type ISessionManager } from '@cassicore/foundation'
import { setDataDirRoot } from '@cassicore/constellation'
import { bus as busSingleton, EventHistory, getEventHistory, rootLogger } from '@cassicore/events'
import { MnemicExactStore } from '@cassicore/mnemic-field'
import { registerMindTools, ToolRegistry, type CoreToolDeps } from '@cassicore/tools'
import { MindFieldTelemetry } from './field/telemetry.js'
import type { FieldTelemetryConfig } from './field/telemetry.js'

// Retained brain composition — host-agnostic in @cassicore/mind-runtime:
// the createIntelligence closure + retained vendored core/intelligence modules
// relocated from the retired host's vendor tree (P5 verdict 26). mind-runtime is
// now the sole composition root for the retained mind.
import { createIntelligence, type IntelligenceLayer } from './vendor/core/intelligence/index.js'
import { createUnifiedIntelligenceLoop } from './vendor/core/intelligence/unified-loop.js'
import { BranchingConversationManager } from './vendor/core/intelligence/branching-conversation/manager.js'
import { createOrchestrationBus } from './vendor/core/orchestration-bus.js'

import { MnemicMemoryAdapter } from './memory/backend.js'
import { MindSessionMirror } from './session-store.js'
import {
  createHttpContextFieldClient,
  RuntimeContextCandidateService,
  type ContextFieldClientOptions,
} from './context/candidates.js'

/** Minimal `IConfig` — reads retained `intelligence.*` defaults direct from env.
 *  No watcher (`watch()`/`onChanged` are no-ops); `reload()` is a no-op. */
class RuntimeConfig implements IConfig {
  private readonly defaults: Record<string, unknown>

  constructor() {
    this.defaults = {
      'intelligence.unifiedLoop.enabled': true,
      'intelligence.unifiedLoop.backgroundIntervalMs': 60_000,
      'intelligence.unifiedLoop.consolidationCadence': 5,
      'intelligence.unifiedLoop.maintenanceCadence': 10,
      'intelligence.memory.dualWriteTurns': false,
    }
  }

  get<T>(key: string, defaultVal?: T): T {
    if (key in this.defaults) return this.defaults[key] as T
    return defaultVal as T
  }
  toJSON(): Record<string, unknown> { return { ...this.defaults } }
  watch(): void { /* no-op — config watcher is standalone surface */ }
  async reload(): Promise<void> { /* no-op */ }
  onChanged(): () => void { return () => { /* no-op */ } }
}

/** Functional result of booting the retained mind (used by server.ts + tests). */
export interface MindRuntime {
  readonly config: {
    homePath: string
    port: number
    token: string | undefined
  }
  readonly logger: ILogger
  readonly bus: IEventBus
  readonly field: MnemicExactStore
  readonly fieldTelemetry: MindFieldTelemetry | undefined
  readonly context: RuntimeContextCandidateService
  readonly intelligence: IntelligenceLayer
  readonly memory: MnemicMemoryAdapter
  readonly sessions: MindSessionMirror
  readonly registry: ToolRegistry
  readonly startedAt: number
  /** Flush field observations and release the exact Mnemic DB. */
  close(): Promise<void>
  /** Execute a retained mind tool by name (used by `/v1/tools/execute`). */
  executeTool(tool: string, params: Record<string, unknown>, sessionId?: string): Promise<{ result: string }>
}

export interface MindRuntimeOptions {
  logger?: ILogger
  bus?: IEventBus
  homePath?: string
  port?: number
  token?: string
  disableUnifiedLoop?: boolean
  disableOscillation?: boolean
  /** Optional, default-off read-only 7599 field telemetry. */
  fieldTelemetry?: FieldTelemetryConfig | boolean
  /** Optional loopback CassiFI provider with sole authority over Mnemic relevance. */
  fieldIntelligenceUrl?: string
  /** Explicit startup verification; ordinary Mnemic reads remain available on failure. */
  verifyMnemicJournal?: boolean
  /** Default-off counterflow experiments and shadow-only calibration threshold. */
  counterflow?: ContextFieldClientOptions
}

/**
 * Boot the focused mind runtime: open the field, build the retained intelligence
 * layer + injections, wire retained mind tools, and stand up the unified loop (unless
 * disabled for tests). Returns a `MindRuntime` handle. Fail-open per retained module
 * so the field + channel always come up.
 */
export async function createMindRuntime(opts: MindRuntimeOptions = {}): Promise<MindRuntime> {
  const bus: IEventBus = opts.bus ?? busSingleton
  const baseLogger: ILogger = opts.logger ?? rootLogger
  const logger = baseLogger.child ? baseLogger.child('mind-runtime') : baseLogger

  const home = opts.homePath ?? process.env.CASSICORE_HOME ?? path.join(homedir(), '.cassicore')
  const homePath = path.resolve(home)

  // ── Paths ports (plan §5 verdict 26 / P7 wiring matrix §7) ───────────────
  try {
    setRootResolver({ getCassiCoreHome: () => homePath })
    setDataDirRoot(homePath)
    logger.info('P7 paths ports wired', { home: homePath })
  } catch (err) {
    logger.warn('paths port wiring failed (non-fatal)', { error: String(err) })
  }

  const config = new RuntimeConfig()
  const startedAt = Date.now()

  // ── Phase 2: Intelligence Layer ─────────────────────────────────────────
  let intelligence: IntelligenceLayer
  try {
    intelligence = createIntelligence(logger, config, bus)
    if (!opts.disableOscillation && intelligence.cortex) {
      intelligence.cortex.startOscillation()
    }

    // Wire modules to the event bus — enables reactive intelligence triggers.
    bus.on('turn:start', (e) => { void (intelligence.memory as never as { onEvent?: (ev: unknown) => void }).onEvent?.(e) })
    bus.on('turn:end', (e) => {
      void (intelligence.memory as never as { onEvent?: (ev: unknown) => void }).onEvent?.(e)
      void (intelligence.continuity as never as { onEvent?: (ev: unknown) => void }).onEvent?.(e)
      void (intelligence.thinker as never as { onEvent?: (ev: unknown) => void }).onEvent?.(e)
    })
    bus.on('plugin:crashed', (e) => {
      void (intelligence.recover as never as { onEvent?: (ev: unknown) => void }).onEvent?.(e)
      void (intelligence.reflect as never as { onEvent?: (ev: unknown) => void }).onEvent?.(e)
    })
    wireModule(intelligence.dialectic, bus)
    wireModule(intelligence.thinker, bus)
    wireModule(intelligence.subconscious, bus)
    ;(intelligence.subconscious as unknown as { start?: () => void }).start?.()
    wireModule(intelligence.ruleEnforcer, bus)

    logger.info('Intelligence layer loaded', { modules: intelligence.all.length })

    // ── Orchestration bus (daemon.ts:259-261 retained slice) ──────────────
    try {
      const orchestration = createOrchestrationBus(logger.child('orchestration'))
      // Session bridge (createSessionBridge) is omitted — no standalone sessions to
      // bridge; ohmypi owns sessions (plan §4.4). Kept here for future mirror wiring.
      logger.info('Orchestration bus initialized')
    } catch (err) {
      logger.warn('orchestration bus init failed (non-fatal)', { error: String(err) })
    }

    // ── Unified Intelligence Loop (daemon.ts:763-798 retained) ────────────
    if (!opts.disableUnifiedLoop) {
      try {
        const unifiedLoop = createUnifiedIntelligenceLoop(logger.child('unified-loop'), bus, {
          enabled: config.get<boolean>('intelligence.unifiedLoop.enabled', true),
          backgroundIntervalMs: config.get<number>('intelligence.unifiedLoop.backgroundIntervalMs', 60_000),
          consolidationCadence: config.get<number>('intelligence.unifiedLoop.consolidationCadence', 5),
          maintenanceCadence: config.get<number>('intelligence.unifiedLoop.maintenanceCadence', 10),
        })
        unifiedLoop.wire({
          subconscious: intelligence.subconscious as never as { persistMentalModels?(): Promise<void>; getStats?(): Record<string, unknown> },
          memory: intelligence.memory as never as { kv_get?<T>(k: string): Promise<T | undefined>; kv_set?(k: string, v: unknown): Promise<void>; cleanup?(): Promise<void>; getStats?(): Record<string, unknown> },
          all: intelligence.all,
        })
        ;(unifiedLoop as unknown as { setActiveSessionsGetter?: (g: () => number) => void }).setActiveSessionsGetter?.(() => 0)
        await unifiedLoop.start()
        logger.info('Unified Intelligence Loop started')
      } catch (err) {
        logger.warn('Failed to initialize Unified Intelligence Loop', { error: String(err) })
      }
    }
  } catch (err) {
    logger.warn('failed to initialize intelligence layer', { error: String(err) })
    throw err
  }

  // ── Exact Mnemic records + sole adaptive CassiFI field ───────────────────
  const fieldTelemetry = opts.fieldTelemetry
    ? new MindFieldTelemetry(opts.fieldTelemetry === true ? {} : opts.fieldTelemetry)
    : undefined
  const field = new MnemicExactStore(logger)
  const verifyMnemicJournal = opts.verifyMnemicJournal
    ?? process.env.CASSI_MNEMIC_VERIFY_JOURNAL === '1'
  if (verifyMnemicJournal) {
    const verification = field.verifyFieldJournal()
    field.requireVerifiedActionJournal(verification)
    const log = verification.status === 'valid' ? logger.info.bind(logger) : logger.warn.bind(logger)
    log('Mnemic exact journal verification completed', {
      status: verification.status,
      acknowledgedPrefixValid: verification.acknowledgedPrefixValid,
      checkedThroughSequence: verification.checkedThroughSequence,
      failure: verification.failure,
    })
  }
  const enabledCounterflowFeatures = new Set(
    (process.env.CASSI_COUNTERFLOW_FEATURES ?? '')
      .split(',')
      .map(value => value.trim())
      .filter(Boolean),
  )
  const configuredShadowSupport = Number(process.env.CASSI_COUNTERFLOW_SHADOW_SUPPORT)
  const counterflowOptions: ContextFieldClientOptions = {
    failureInhibition: opts.counterflow?.failureInhibition
      ?? enabledCounterflowFeatures.has('failure-inhibition'),
    actionRoleAbstraction: opts.counterflow?.actionRoleAbstraction
      ?? enabledCounterflowFeatures.has('action-roles'),
    lineageRoleAbstraction: opts.counterflow?.lineageRoleAbstraction
      ?? enabledCounterflowFeatures.has('lineage-roles'),
    multiActionTrajectories: opts.counterflow?.multiActionTrajectories
      ?? enabledCounterflowFeatures.has('multi-action'),
    shadowSupportThreshold: opts.counterflow?.shadowSupportThreshold
      ?? (Number.isFinite(configuredShadowSupport) && configuredShadowSupport >= 0
        ? configuredShadowSupport
        : undefined),
  }
  const fieldClient = opts.fieldIntelligenceUrl
    ? createHttpContextFieldClient(
        opts.fieldIntelligenceUrl,
        field,
        logger.child('cassi-fi'),
        counterflowOptions,
      )
    : undefined
  if (fieldClient) {
    field.onFieldEvent = fieldClient.notify
    fieldClient.notify()
  }
  ;(intelligence as unknown as { __mnemicField: MnemicExactStore }).__mnemicField = field

  // ── Session mirror store (ohmypi owns sessions; runtime mirrors) ────────
  const sessions = new MindSessionMirror()

  // ── Retained mind-tool deps + registration ──────────────────────────────
  const memory = new MnemicMemoryAdapter(field)
  const registry = new ToolRegistry()

  // Exact Mnemic records supply only opaque addresses and resolved bytes;
  // CassiFI alone selects relevance, and provider failure abstains.
  const context = new RuntimeContextCandidateService({
    memory,
    fieldTelemetry,
    fieldRecall: fieldClient?.recall,
    bus,
    counterflowStatus: fieldClient?.status,
    logger: logger.child('context'),
  })

  // Retained event history store for query_events (mirror the bus history).
  const eventHistory: EventHistory | undefined = getEventHistory({ maxEvents: 5000 })

  const intelligenceAny = intelligence as never as {
    thoughtObserver: unknown
    cognitiveBridge: unknown
    contextManager: unknown
    subconscious: unknown
    memory: unknown
    constellationGuidanceRegistry: unknown
    thinker: unknown
    all: unknown[]
  }

  const mindDeps: CoreToolDeps = {
    memory: intelligence.memory,
    sessionManager: sessions as unknown as ISessionManager,
    bus,
    logger: logger.child('mind-tools'),
    subagentTracker: undefined,
    eventHistory,
    peerToolDeps: {
      memory: intelligence.memory,
      cognitiveBridge: intelligenceAny.cognitiveBridge,
      logger: logger.child('_peers'),
    } as never as CoreToolDeps['peerToolDeps'],
    collectThoughtsDeps: {
      branchingManager: new BranchingConversationManager(),
      thoughtObserver: intelligenceAny.thoughtObserver,
      cognitiveBridge: intelligenceAny.cognitiveBridge,
      memory: intelligence.memory,
      mnemicField: field,
      bus,
      logger: logger.child('collect-thoughts'),
      constellationGuidanceRegistry: intelligenceAny.constellationGuidanceRegistry,
      getThinkerSession: (sessionId: string) =>
        (intelligenceAny.thinker as { getThinkerSession?: (id: string) => never }).getThinkerSession?.(sessionId),
      // synapse omitted — P3 has no live LLM; the collect_thoughts enrichment
      // pipeline runs without the Axon synapse gating (daemon wires it only when
      // a provider is present).
    } as never as CoreToolDeps['collectThoughtsDeps'],
  }

  registerMindTools(registry, mindDeps)

  const configuredToken = (opts.token ?? process.env.CASSI_MIND_TOKEN)?.trim() || undefined
  const runtime: MindRuntime = {
    config: { homePath, port: opts.port ?? readPort(), token: configuredToken },
    logger,
    bus,
    field,
    fieldTelemetry,
    context,
    intelligence,
    memory,
    sessions,
    registry,
    startedAt,
    close: async () => {
      try { context.close() } catch { /* ignore */ }
      try { await fieldClient?.close() } catch { /* ignore */ }
      try { fieldTelemetry?.close() } catch { /* ignore */ }
      try { field.close() } catch { /* ignore */ }
      logger.info('Mind runtime closed', { uptimeMs: Date.now() - startedAt })
    },
    executeTool: async (tool, params, sessionId) => {
      const entry = registry.get(tool)
      if (!entry) throw new Error(`Tool not found: ${tool}`)
      const result = await entry.handler(params, {
        sessionId: sessionId ?? sessions.currentSessionId ?? 'default',
        workingDir: homePath,
        allowedPaths: [homePath],
        networkAllowlist: ['*'],
        logger: logger.child(`tool:${tool}`),
        registry,
      })
      return { result }
    },
  }

  return runtime
}

function readPort(): number {
  const raw = process.env.CASSI_MIND_PORT
  if (!raw) return 7273
  const n = Number(raw)
  return Number.isInteger(n) && n > 0 && n < 65536 ? n : 7273
}

function wireModule(mod: unknown, bus: IEventBus): void {
  ;(mod as { onEventBus?: (b: IEventBus) => void }).onEventBus?.(bus)
}

export { RuntimeConfig }
// Convenience re-export so server.ts/index.ts don't re-guess the port.
export type { MindMirroredSession, SessionMirrorEvent } from './channel/protocol.js'
