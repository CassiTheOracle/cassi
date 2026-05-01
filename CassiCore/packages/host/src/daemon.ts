import { EventBus, bus } from "./event-bus.js"
import { Logger, rootLogger } from "./logger.js"
import { Config } from "./config.js"
import { createLayeredConfig } from "./runtime-config.js"
import { getBuildIdentifier, formatBuildId, type BuildIdentifier } from "./build-id.js"

import fs from "node:fs"
import { homedir } from "node:os"
import path, { join } from "node:path"
import { fileURLToPath } from "node:url"

const _BUILD = getBuildIdentifier()
export const CASSICORE_VERSION: string = _BUILD.version
export const CASSICORE_BUILD: BuildIdentifier = _BUILD
export const CASSICORE_BUILD_STRING: string = formatBuildId(_BUILD)

import { createAdminApi } from './admin-api.js'
import { createBridge } from './bridge/openai.js'
import { CommandDispatcher } from './commands.js'
import { createSkillMetricsTracker, type SkillMetricsTracker } from './intelligence/skill-metrics.js'
import { createCrossSessionCorrelator, type CrossSessionCorrelator } from './intelligence/cross-session-correlator.js'
import { createStrategyTracker, type StrategyTracker } from './intelligence/strategy-tracker.js'
import { createProviderProfiler, type ProviderProfiler } from './intelligence/provider-profiler.js'
import { createAdaptiveBehavior, type AdaptiveBehavior } from './intelligence/adaptive-behavior.js'
import { createSelfVerification, type SelfVerification } from './intelligence/self-verification.js'
import { createMonitoringHook, type MonitoringHook } from './monitoring-hook.js'
import { bootIntelligencePostPipeline } from './daemon/boot-intelligence-post.js'
import { PrimarySessionRouter, createPrimarySessionRouter } from './daemon/primary-session-router.js'
import { initContextWindowDebugger, ContextWindowDebugger } from './events/context-window-debug.js'
import { setContextWindowDebugger, contextWindowDebugMiddleware } from './turn-pipeline.js'
import { createSessionDigestStore, type SessionDigestStore } from './intelligence/session-digest.js'
import { IntelligentContextWindow } from './intelligence/context-window/index.js'
import { createSynapse } from './intelligence/synapse/index.js'
import { MODEL_DEFAULTS, getModelSpec } from './config/system-settings.js'
import { HealthMonitor } from './health-monitor.js'
import { createIntelligence } from "./intelligence/index.js"
import { createOutcomeTracker, type OutcomeTracker } from './intelligence/outcome-tracker.js'
import { GlobalBlackboardRegistry } from './intelligence/flux-team/global-blackboard-registry.js'
import { MCPRegistry } from './mcp/registry.js'
import { createOrchestrationBus } from './orchestration-bus.js'
import { PluginHost } from "./plugin-host.js"
import { type BudgetTracker, createBudgetTracker } from './providers/budget-tracker.js'
import { ModelDirective } from './model-routing/index.js'
import { type ModelRouter, createModelRouter } from './providers/model-router.js'
import { createSessionBridge } from './session-bridge.js'
import { createSessionManager } from './session-manager.js'
import { SessionStore } from './session-store.js'
import { FileArtifactStore } from './file-artifact-store.js'
import { MnemicField, CodeStore } from './intelligence/mnemic-field/index.js'
import { FileVault } from './intelligence/file-vault/index.js'
import { createSubagentTracker, type SubagentTracker } from './subagent-tracker.js'
import { ToolExecutor } from './tools/executor.js'
import { registerCoreTools } from './tools/implementations/index.js'
import { ToolRegistry } from './tools/registry.js'
import { ToolReliabilityTracker } from './tools/reliability.js'
import { WorkflowEngine } from './workflow/engine.js'
import { WorkflowRegistry } from './workflow/registry.js'
import { WorkflowStore } from './workflow/persistence.js'
import { WorkflowDefinitionStore } from './workflow/definition-store.js'
import { WorkflowScheduler } from './workflow/scheduler.js'
import { WorkflowTriggerStore } from './workflow/trigger-store.js'
import { BranchingConversationManager } from './intelligence/branching-conversation/manager.js'
import { TurnPipeline } from './turn-pipeline.js'
import { buildSystemPrompt } from './workspace/loader.js'
import { executeTurn, getPreferredTurnEngine } from './admin-api/turn-routing.js'


import type { IEventBus, ILogger, IConfig, IPluginHost, IntelligenceModule } from "../types/interfaces.js"
import type { IProvider } from '../types/runtime.js'
import type { IntelligenceLayer } from "./intelligence/index.js"

// Type helper for intelligence modules with optional event handlers
interface EventHandler { onEvent?: (e: unknown) => void | Promise<void> }

// WHY: singleton enforcement via PID file prevents multiple daemon instances
const CASSICORE_PID_FILE = path.join(homedir(), '.cassicore', 'daemon.pid')

export interface DaemonBootPhaseMetric {
  name: string
  startedAt: number
  endedAt: number
  sinceBootMs: number
  durationMs: number
  meta?: Record<string, unknown>
}

export interface DaemonBootServiceMetric {
  name: string
  startedAt: number
  readyAt: number
  sinceBootMs: number
  durationMs: number
  meta?: Record<string, unknown>
}

export interface DaemonBootSnapshot {
  sequence: number
  pid: number
  startedAt: number
  readyAt: number
  durationMs: number
  timeToAdminReadyMs: number | null
  phases: DaemonBootPhaseMetric[]
  services: DaemonBootServiceMetric[]
}

/**
 * @dep callers: start (core/daemon.ts), startDeferredStartup (core/daemon.ts), recordService (core/daemon.ts), completePhase (core/daemon.ts)
 * @dep module: Workflow
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

function roundDurationMs(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.round(value))
}

/**
 * Check if another daemon instance is already running.
 * WHY: singleton enforcement — only one daemon should run per user.
 * Returns the PID of the running daemon, or null if none.
 */
function checkExistingDaemon(): number | null {
  try {
    if (!fs.existsSync(CASSICORE_PID_FILE)) {
      return null
    }

    const pidContent = fs.readFileSync(CASSICORE_PID_FILE, 'utf-8').trim()
    const existingPid = parseInt(pidContent, 10)

    if (isNaN(existingPid) || existingPid <= 0) {
      // WHY: invalid PID format — remove corrupted file
      fs.unlinkSync(CASSICORE_PID_FILE)
      return null
    }

    // Check if process is actually running
    try {
      process.kill(existingPid, 0)
      // WHY: signal 0 succeeds only if process exists and we have permission
      return existingPid
    } catch (err) {
      // WHY: ESRCH = process dead (stale file), EPERM = different user
      if ((err as NodeJS.ErrnoException).code === 'ESRCH') {
        fs.unlinkSync(CASSICORE_PID_FILE)
        return null
      }
      // WHY: EPERM means process exists but runs as different user — treat as running
      return existingPid
    }
  } catch (err) {
    // WHY: defensive — file read errors, permission issues = assume safe to start
    return null
  }
}

/**
 * Write current PID to lock file.
 * WHY: enables singleton check on subsequent daemon start attempts.
 */
function writePidFile(logger: ILogger): void {
  try {
    const cassicoreDir = path.dirname(CASSICORE_PID_FILE)
    if (!fs.existsSync(cassicoreDir)) {
      fs.mkdirSync(cassicoreDir, { recursive: true })
    }
    fs.writeFileSync(CASSICORE_PID_FILE, process.pid.toString(), 'utf-8')
  } catch (err) {
    rootLogger.warn(`Could not write PID file: ${String(err)}`)
  }
}

/**
 * Remove PID file on shutdown.
 * WHY: prevents stale PID from blocking future daemon starts.
 */
function cleanupPidFile(): void {
  try {
    if (fs.existsSync(CASSICORE_PID_FILE)) {
      fs.unlinkSync(CASSICORE_PID_FILE)
    }
  } catch (err) {
    // WHY: cleanup is best-effort — failure should not block shutdown
  }
}

export class Daemon {
  public bus: IEventBus
  private config!: IConfig
  private pluginHost!: IPluginHost
  private logger: ILogger
  private running = false
  private intelligence!: IntelligenceLayer
  private sessions!: ReturnType<typeof createSessionManager>
  public pipeline!: TurnPipeline
  public healthMonitor!: HealthMonitor
  private commands!: CommandDispatcher
  public subagentTracker!: SubagentTracker
  public skillMetricsTracker?: SkillMetricsTracker
  public outcomeTracker?: OutcomeTracker
  public crossSessionCorrelator?: CrossSessionCorrelator
  public strategyTracker?: StrategyTracker
  public providerProfiler?: ProviderProfiler
  public adaptiveBehavior?: AdaptiveBehavior
   public selfVerification?: SelfVerification
   /** Runtime self-monitoring — tool latency, context pressure, loop detection. */
   public monitoringHook?: MonitoringHook
   public sessionDigestStore?: SessionDigestStore
    /** Background embedding pre-computation worker. */
   public bgEmbeddingWorker?: import('./intelligence/embeddings/background-worker.js').BackgroundEmbeddingWorker
   /** Background tagger worker for autonomous LLM annotation. */
   public bgTaggerWorker?: import('./intelligence/training/background-tagger-worker.js').BackgroundTaggerWorker
   /** Embedding stack launcher (auto-starts llama.cpp + zerank servers). */
    public embeddingStackLauncher?: import('./intelligence/embeddings/inference-stack-launcher.js').InferenceStackLauncher
  /** Loaded provider map — available after daemon start(). */
  public providers: Map<string, IProvider> = new Map()
  /** Prompt log store — persistent SQLite storage of every prompt sent to providers. */
  public promptLogStore?: import('./prompt-log-store.js').PromptLogStore
  /** Rate limit store — persists adaptive learned rate limits across daemon restarts. */
  public rateLimitStore?: import('./providers/rate-limit-store.js').RateLimitStore
  /** Timeline store — unified chronological view of all system data. */
  public timelineStore?: import('./timeline-store.js').TimelineStore
  public contextDistiller?: import('./intelligence/context-distiller.js').ContextDistiller
  /** Background intelligence loop — available after daemon start(). */
  public unifiedLoop?: import('./intelligence/unified-loop.js').UnifiedIntelligenceLoop
  /** Tool executor — available after daemon start(). */
  public toolExecutor?: ToolExecutor
  /** Workflow engine — available after daemon start(). */
  public workflowEngine?: WorkflowEngine
  /** Workflow definition registry — available after daemon start(). */
  public workflowRegistry?: WorkflowRegistry
  /** Workflow scheduler (trigger-based automation) — available after daemon start(). */
  public workflowScheduler?: WorkflowScheduler
  /** Autonomous agent loop — available when feature is enabled. */
  public autonomousLoop?: import('./intelligence/autonomous-loop.js').AutonomousAgentLoop
  /** Session pipeline integration */
  public sessionPipeline?: import('./pipeline/adapter/SessionPipeline.js').SessionPipeline
  public budgetTracker?: BudgetTracker
  private primaryRouter?: PrimarySessionRouter
  public modelRouter?: ModelRouter
  public modelDirective?: ModelDirective
  /** Helix/Constellation ModelPool — stored for re-wiring after late provider init (e.g. copilot-sdk). */
  private helixModelPool?: import('./model-pool/index.js').ModelPool
  /** IntelligentContextWindow instance — available after daemon start(). */
  public contextWindow?: IntelligentContextWindow
  /** Global Blackboard Registry — shared singleton for daemon-scoped modules. */
  public globalBlackboardRegistry?: GlobalBlackboardRegistry
  // expose orchestration bus for external use
  public orchestration?: ReturnType<typeof createOrchestrationBus>
  private bootSequence = 0
  private latestBootSnapshot: DaemonBootSnapshot | null = null
  private bootHistory: DaemonBootSnapshot[] = []
  private deferredStartupTimer: NodeJS.Timeout | null = null
  /** Tracks whether the inference stack (llama.cpp servers) is currently running. */
  private inferenceStackEnabled = false

  constructor(busInstance: IEventBus = bus, logger: ILogger = rootLogger) {
    this.bus = busInstance
    this.logger = logger.child('daemon')
    if (CASSICORE_VERSION === 'unknown') {
      this.logger.warn('Could not determine CassiCore version from package.json')
    }
    // WHY: orchestration bus enables cross-session coordination
    try {
      this.orchestration = createOrchestrationBus(this.logger.child('orchestration'))
      // WHY: session bridge propagates events across orchestration boundary
      createSessionBridge(this.orchestration, this.logger.child('bridge'))
    } catch (err) {
      this.logger.warn(`failed to initialize orchestration: ${String(err)}`)
    }
  }

  /**
   * Wire an intelligence module to the event bus.
   * Uses the optional `onEventBus` declared on the IntelligenceModule interface.
   */
  private wireModule(mod: unknown, bus: IEventBus): void {
    (mod as IntelligenceModule).onEventBus?.(bus)
  }

  /** Start an intelligence module's background processing if it implements `start()`. */
  private startModule(mod: unknown): void {
    (mod as IntelligenceModule).start?.()
  }

  getBootMetrics(): DaemonBootSnapshot | null {
    return this.latestBootSnapshot
  }

  getBootMetricsHistory(limit = 10): DaemonBootSnapshot[] {
    const normalizedLimit = Math.max(1, Math.floor(limit))
    return this.bootHistory.slice(-normalizedLimit)
  }

  private recordBootMetrics(snapshot: DaemonBootSnapshot): void {
    this.bootSequence = snapshot.sequence
    this.latestBootSnapshot = snapshot
    this.bootHistory.push(snapshot)
    if (this.bootHistory.length > 10) {
      this.bootHistory.splice(0, this.bootHistory.length - 10)
    }
  }

  // WHY: defer non-critical startup (inference stack, embeddings) until after daemon readiness
  // so admin API and critical paths are not blocked. setTimeout(0) yields to event loop.
  private scheduleDeferredStartup(): void {
    if (this.deferredStartupTimer) return
    this.deferredStartupTimer = setTimeout(() => {
      this.deferredStartupTimer = null
      void this.startDeferredStartup()
    }, 0)
    this.deferredStartupTimer.unref?.()
  }

  /**
   * Start (or restart) the local inference stack — llama.cpp embedding server,
   * reranker, and generative model. Idempotent: safe to call when already running.
   *
   * Controlled by `intelligence.inferenceStack.enabled` (default: true).
   * Set to `false` via `cassi_config_set` to free GPU VRAM (e.g. when gaming).
   */
  private async startInferenceStackLauncher(): Promise<void> {
    try {
      const { InferenceStackLauncher } = await import('./intelligence/embeddings/inference-stack-launcher.js')
      const gpuGuardEnabled = this.config.get<boolean>('intelligence.inferenceStack.gpuGuard', true)
      const gpuGuardIntervalMs = this.config.get<number>('intelligence.inferenceStack.gpuGuardIntervalMs', 60_000)
      this.embeddingStackLauncher = new InferenceStackLauncher(this.logger, {
        gpuGuardEnabled,
        gpuGuardIntervalMs,
      })
      this.embeddingStackLauncher.start()
        .then(() => {
          this.logger.info('InferenceStackLauncher ready')
        })
        .catch((err: unknown) => {
          this.logger.warn(`Failed to start inference stack: ${String(err)}`)
        })
      this.inferenceStackEnabled = true
      this.logger.info('InferenceStackLauncher starting')
    } catch (err) {
      this.logger.warn(`Failed to start embedding stack: ${String(err)}`)
    }
  }

  private async startDeferredStartup(): Promise<void> {
    const deferredStart = performance.now()

    const inferenceStackEnabled = this.config.get<boolean>('intelligence.inferenceStack.enabled', true)
    if (inferenceStackEnabled) {
      await this.startInferenceStackLauncher()
    } else {
      this.logger.info('InferenceStack disabled by config (intelligence.inferenceStack.enabled=false)')
    }

    const backgroundEmbeddingEnabled = this.config.get<boolean>('intelligence.backgroundEmbedding.enabled', false)
    if (backgroundEmbeddingEnabled) {
      try {
        const { getBackgroundEmbeddingWorker } = await import('./intelligence/embeddings/background-worker.js')
        this.bgEmbeddingWorker = getBackgroundEmbeddingWorker(this.logger)
        this.bgEmbeddingWorker.start()
        this.logger.info('BackgroundEmbeddingWorker started after readiness')
      } catch (err) {
        this.logger.warn(`Failed to start BackgroundEmbeddingWorker: ${String(err)}`)
      }
    } else {
      this.logger.info('BackgroundEmbeddingWorker disabled by config')
    }

    const backgroundTaggerEnabled = this.config.get<boolean>('intelligence.backgroundTagger.enabled', false)
    if (backgroundTaggerEnabled) {
      try {
        const sdkProvider = this.providers.get('copilot-sdk')
        const warehouse = (this as any).intelligence?.training
        if (sdkProvider && warehouse?.store) {
          const { BackgroundTaggerWorker } = await import('./intelligence/training/background-tagger-worker.js')
          this.bgTaggerWorker = new BackgroundTaggerWorker(warehouse.store, sdkProvider, this.logger)
          this.bgTaggerWorker.start()
          this.logger.info('BackgroundTaggerWorker started after readiness')
        } else {
          this.logger.warn('BackgroundTaggerWorker: missing copilot-sdk provider or training warehouse')
        }
      } catch (err) {
        this.logger.warn(`Failed to start BackgroundTaggerWorker: ${String(err)}`)
      }
    } else {
      this.logger.info('BackgroundTaggerWorker disabled by config')
    }

    this.logger.info('Deferred startup completed', {
      durationMs: roundDurationMs(performance.now() - deferredStart),
      inferenceStackEnabled,
      backgroundEmbeddingEnabled,
    })
  }

  /**
   * Start the daemon: load config, start plugin host, wire signals and workers.
   */
  async start(): Promise<{ admin?: { tcpPort: number | null; unixPath: string }; pid: number }> {
    const bootStart = performance.now()
    const bootStartedAt = Date.now()
    const bootPhases: DaemonBootPhaseMetric[] = []
    const bootServices: DaemonBootServiceMetric[] = []
    let phaseStartPerf = bootStart
    let phaseStartedAt = bootStartedAt
    let adminReadyPerf: number | null = null

    const completePhase = (
      name: string,
      meta?: Record<string, unknown>,
      endedAt = Date.now(),
      endedPerf = performance.now(),
    ): void => {
      bootPhases.push({
        name,
        startedAt: phaseStartedAt,
        endedAt,
        sinceBootMs: roundDurationMs(phaseStartPerf - bootStart),
        durationMs: roundDurationMs(endedPerf - phaseStartPerf),
        ...(meta ? { meta } : {}),
      })
      phaseStartedAt = endedAt
      phaseStartPerf = endedPerf
    }

    const recordService = (
      name: string,
      serviceStartedAt: number,
      serviceStartedPerf: number,
      meta?: Record<string, unknown>,
      readyAt = Date.now(),
      readyPerf = performance.now(),
    ): DaemonBootServiceMetric => {
      const metric: DaemonBootServiceMetric = {
        name,
        startedAt: serviceStartedAt,
        readyAt,
        sinceBootMs: roundDurationMs(serviceStartedPerf - bootStart),
        durationMs: roundDurationMs(readyPerf - serviceStartedPerf),
        ...(meta ? { meta } : {}),
      }
      bootServices.push(metric)
      return metric
    }

    // 0. Load .env secrets (before anything reads env vars)
    await this._loadEnv()

    // 0b. Check for existing daemon instance (singleton enforcement)
    const existingPid = checkExistingDaemon()
    if (existingPid !== null) {
      // WHY: silent exit prevents log spam from periodic daemon probes (OpenCode, etc.)
      process.exit(0)
    }

    // Write our PID to the lock file
    writePidFile(this.logger)
    this.logger.info(`PID file written: ${process.pid}`)

    // Register cleanup on exit
    process.on('exit', cleanupPidFile)
    process.on('SIGTERM', () => { cleanupPidFile(); process.exit(0) })
    process.on('SIGINT', () => { cleanupPidFile(); process.exit(0) })

    this.logger.info('── Phase 1: Configuration ──────────────────────────────')

    // 1. Load base file config
    const baseCfg = await Config.load()

    // 2. Create layered runtime config wrapping file config
    const layered = createLayeredConfig(baseCfg, this.bus, this.logger)
    // attempt to load persisted runtime overrides
    try {
      await layered.loadPersistedOverrides()
    } catch (err) {
      this.logger.warn(`failed to load persisted overrides: ${String(err)}`)
    }

    this.config = layered

    // 3. Start config watcher (file-level) — enables hot-reload without restart
    try {
      baseCfg.watch()
    } catch (err) {
      this.logger.warn("failed to start config watcher")
    }

    // Log config summary
    {
      const logLevel = this.config.get<string>('logging.level', 'info')
      const thinking = this.config.get<string>('intelligence.thinking', 'high')
      const defaultModel = this.config.get<string>('intelligence.defaultModel', '(default)')
      const defaultProvider = this.config.get<string>('intelligence.defaultProvider', '(default)')
      this.logger.info(`Config loaded`, { logLevel, thinking, defaultProvider, defaultModel })
    }

    // 3. Register SIGHUP -> reload (hot config reload without restart)
    process.on("SIGHUP", () => {
      void this.reload()
    })

    // 4. Register SIGTERM + SIGINT -> graceful shutdown
    const stopHandler = () => {
      void this.stop()
    }
    process.on("SIGTERM", stopHandler)
    process.on("SIGINT", stopHandler)

    if (process.stdin.listenerCount("error") === 0) {
      process.stdin.on("error", (err) => {
        // WHY: EIO = EOF on stdin (common when detached), ignore silently
        if ((err as NodeJS.ErrnoException).code === "EIO") return;
        this.logger.warn?.('process.stdin error', { error: String(err) })
      })
    }

    // 5. Global safety: log unhandled promise rejections to avoid daemon crash on library race conditions
    process.on('unhandledRejection', (reason, _promise) => {
      try {
        let errMsg = String(reason)
        try {
          if (reason && typeof reason === 'object') {
            const err = reason as Error
            errMsg = err.stack || err.message || String(reason)
          }
        } catch (e) { /* ignore */ }
        // WHY: timeouts are expected (provider cancellations, polling) — downgrade to debug
        if (String(errMsg).toLowerCase().includes('timeout')) {
          this.logger.debug?.('unhandledRejection (timeout)', { error: errMsg })
        } else {
          this.logger.warn?.('unhandledRejection', { error: errMsg })
        }
      } catch (e) { /* ignore */ }
    })

    // WHY: ENOENT on spawn = missing shell command — log but don't crash daemon
    process.on('uncaughtException', (error) => {
      if (error && (error as NodeJS.ErrnoException).code === 'ENOENT' && (error as NodeJS.ErrnoException).syscall?.includes('spawn')) {
        this.logger.error?.('shell command failed', {
          syscall: (error as NodeJS.ErrnoException).syscall,
          path: (error as NodeJS.ErrnoException).path,
          message: error.message
        })
        return
      }
      // WHY: uncaught exceptions leave process in undefined state (dead HTTP server, corrupted event loop).
      // Schedule graceful shutdown to allow in-flight operations to complete.
      this.logger.error?.('uncaughtException — scheduling shutdown', { error: error.message, stack: error.stack })
      
      // HOW: Dump active session state so post-mortem can identify what was running at crash time
      try {
        const mem = process.memoryUsage()
        this.logger.error?.('crash diagnostics', {
          heapMB: Math.round(mem.heapUsed / 1024 / 1024),
          rssMB: Math.round(mem.rss / 1024 / 1024),
          uptimeS: Math.round(process.uptime()),
          activeTimers: (process as any)._getActiveHandles?.()?.length ?? 'unknown',
        })
      } catch { /* best-effort diagnostics */ }
      
      this.bus.emit({ type: 'daemon:shutdown', reason: 'uncaughtException' })
      setTimeout(() => {
        this.logger.error?.('Exiting after uncaughtException')
        process.exit(1)
      }, 5000).unref()
    })

    completePhase('configuration', {
      logLevel: this.config.get<string>('logging.level', 'info'),
      thinking: this.config.get<string>('intelligence.thinking', 'high'),
      defaultProvider: this.config.get<string>('intelligence.defaultProvider', '(default)'),
      defaultModel: this.config.get<string>('intelligence.defaultModel', '(default)'),
    })

    // 5. Create PluginHost — manages channel workers as isolated plugins
    this.pluginHost = new PluginHost(this.logger)

    this.logger.info('── Phase 2: Intelligence Layer ────────────────────────')

    // Initialize intelligence layer before loading plugins
    try {
      this.intelligence = createIntelligence(this.logger, this.config, this.bus)

      // Create shared GlobalBlackboardRegistry for daemon-scoped modules
      this.globalBlackboardRegistry = new GlobalBlackboardRegistry(this.logger.child('global-blackboard-registry'))

      // WHY: BaseCognitiveModule subclasses need blackboard registry for cross-module communication
      if (this.globalBlackboardRegistry) {
        for (const mod of Object.values(this.intelligence)) {
          if (mod && typeof (mod as any).setGlobalBlackboardRegistry === 'function') {
            (mod as any).setGlobalBlackboardRegistry(this.globalBlackboardRegistry)
          }
        }
      }

      // Start cortex oscillation — periodic decay, prune, consolidate, bind
      if (this.intelligence.cortex) {
        this.intelligence.cortex.startOscillation()
      }

      // Wire modules to event bus — enables reactive intelligence triggers
      const bus = this.bus
      bus.on("turn:start", (e) => {
        void (this.intelligence.memory as EventHandler).onEvent?.(e)
      })

      bus.on("turn:end", (e) => {
        void (this.intelligence.memory as EventHandler).onEvent?.(e)
        void (this.intelligence.continuity as EventHandler).onEvent?.(e)
        void (this.intelligence.thinker as EventHandler).onEvent?.(e)
      })

      bus.on("plugin:crashed", (e) => {
        void (this.intelligence.recover as EventHandler).onEvent?.(e)
        void (this.intelligence.reflect as EventHandler).onEvent?.(e)
      })

      // REMOVED: Optimizer daemon:ready / daemon:shutdown handlers — OptimizerModule deleted

      // Wire DialecticSystem to event bus for streaming
      this.wireModule(this.intelligence.dialectic, bus)

      // WHY: Thinker listens for turn:end to trigger proactive thinking cycles
      this.wireModule(this.intelligence.thinker, bus)

      // WHY: AI Scientist collects metrics for research analysis
      this.wireModule(this.intelligence.aiScientist, bus)

      // Start AI Scientist monitoring
      this.startModule(this.intelligence.aiScientist)

      // Initialize and start Unified Intelligence Loop
      try {
        const { createUnifiedIntelligenceLoop } = await import('./intelligence/unified-loop.js')
        const unifiedLoop = createUnifiedIntelligenceLoop(
          this.logger.child('unified-loop'),
          this.bus,
          {
            enabled: this.config.get<boolean>('intelligence.unifiedLoop.enabled', true),
            backgroundIntervalMs: this.config.get<number>('intelligence.unifiedLoop.backgroundIntervalMs', 60000),
            consolidationCadence: this.config.get<number>('intelligence.unifiedLoop.consolidationCadence', 5),
            maintenanceCadence: this.config.get<number>('intelligence.unifiedLoop.maintenanceCadence', 10),
          }
        )

        // Wire module references for background coordination
        interface SubconsciousWithLoop {
          persistMentalModels?(): Promise<void>
          getStats?(): Record<string, unknown>
        }
        interface MemoryWithLoop {
          kv_get?<T>(key: string): Promise<T | undefined>
          kv_set?(key: string, value: unknown): Promise<void>
          cleanup?(): Promise<void>
          getStats?(): Record<string, unknown>
        }
        interface OptimizerWithLoop {
          getStats?(): Record<string, unknown>
        }
        unifiedLoop.wire({
          subconscious: this.intelligence.subconscious as SubconsciousWithLoop,
          memory: this.intelligence.memory as MemoryWithLoop,
          // REMOVED: optimizer wiring — OptimizerModule deleted
          all: this.intelligence.all,
        })

        await unifiedLoop.start()
        ;this.unifiedLoop = unifiedLoop
        this.logger.info('Unified Intelligence Loop started')

        // Enrich heartbeats with live request/session counts
        if (this.sessions) {
          const sessions = this.sessions
          unifiedLoop.setActiveSessionsGetter(() => sessions.list().length)
        }
        // activeRequests getter is wired below after providers are available
      } catch (err) {
        this.logger.warn('Failed to initialize Unified Intelligence Loop', { error: String(err) })
      }

      // WHY: Subconscious listens for session events to build mental models
      this.wireModule(this.intelligence.subconscious, bus)
      this.startModule(this.intelligence.subconscious)

      // WHY: reconcile sessions created before Subconscious was wired — prevents telemetry drift
      // (activeSessions=0 without this, causing metric inconsistencies)
      interface SubconsciousModule {
        reconcile?: (args: { sessions: Array<{ sessionId: string; startedAt: number; lastActivityAt: number; turnCount: number }> }) => void
      }
      try {
        const subconscious = this.intelligence.subconscious as SubconsciousModule | undefined
        if (typeof subconscious?.reconcile === 'function' && this.sessions) {
          const liveSessions = this.sessions.list().map((s) => ({
            sessionId:      s.id,
            startedAt:      s.createdAt instanceof Date ? s.createdAt.getTime() : Number(s.createdAt),
            lastActivityAt: s.lastActiveAt instanceof Date ? s.lastActiveAt.getTime() : Number(s.lastActiveAt),
            turnCount:      s.history?.length ?? 0,
          }))
          subconscious.reconcile({ sessions: liveSessions })
        }
      } catch (err) {
        this.logger.warn('Subconscious reconcile failed — session counts may be stale', { error: String(err) })
      }

      // WHY: Subconscious needs live session list for reconciliation without circular dependency on SessionManager
      try {
        interface SubconsciousWithGetter {
          setLiveSessionGetter?(getter: () => Array<{ sessionId: string; startedAt: number; lastActivityAt?: number; turnCount?: number }>): void
        }
        const subconsciousWithGetter = this.intelligence.subconscious as SubconsciousWithGetter | undefined
        if (typeof subconsciousWithGetter?.setLiveSessionGetter === 'function' && this.sessions) {
          const sessions = this.sessions
          subconsciousWithGetter.setLiveSessionGetter(() =>
            sessions.list().map((s) => ({
              sessionId:      s.id,
              startedAt:      s.createdAt instanceof Date ? s.createdAt.getTime() : Number(s.createdAt),
              lastActivityAt: s.lastActiveAt instanceof Date ? s.lastActiveAt.getTime() : Number(s.lastActiveAt),
              turnCount:      s.history?.length ?? 0,
            }))
          )
        }
      } catch (err) {
        this.logger.warn('Failed to wire Subconscious live session getter', { error: String(err) })
      }

      // Wire Rule Enforcer to event bus
      this.wireModule(this.intelligence.ruleEnforcer, bus)

      // WHY: DroneSwarm needs event bus for mission coordination
       if (this.intelligence.droneSwarm?.setEventBus) {
         this.intelligence.droneSwarm.setEventBus(bus)
         this.logger.info('DroneSwarm event bus wired')
       }

       // Wire SelfHealingAgent — give it the EventBus and a repair provider
       // that delegates to the Thinker's repair-request/response event pair.
       this.wireModule(this.intelligence.selfHealer, bus)
       ;(this.intelligence.selfHealer as IntelligenceModule).setRepairProvider?.(
             async (prompt: string): Promise<string> => {
                // WHY: Strategy 1 = github-copilot direct call (fallback independent of Thinker health)
                 const gcProvider = this.providers.get('github-copilot')
                if (gcProvider) {
                  try {
                    let text = ''
                    const stream = gcProvider.complete(
                      [{ role: 'user', content: prompt }],
                      { model: 'gpt-4.1', stream: true, maxTokens: 4000, thinking: 'none' }
                    )
                   for await (const chunk of stream) {
                     if (chunk.type === 'token' && chunk.text) text += chunk.text
                     else if (chunk.type === 'done') break
                     else if (chunk.type === 'error') { text = ''; break }
                   }
                   if (text.trim()) {
                     this.logger.info('SelfHealingAgent: repair generated via github-copilot')
                     return text.trim()
                   }
                  } catch (err) {
                    this.logger.warn('SelfHealingAgent: github-copilot repair failed', { error: String(err) })
                  }
                }
                // WHY: Strategy 2 = Thinker event chain with 90s timeout (primary repair mechanism)
                return new Promise((resolve) => {
                 const id = `repair:${Date.now()}:${Math.random().toString(36).slice(2)}`
                 const timer = setTimeout(() => {
                   bus.off('thinker:repair-response', handler)
                   this.logger.warn('SelfHealingAgent: repair timed out (90s)', { id })
                   resolve('')
                 }, 90_000)
                 const handler = (e: { id: string; text: string; error?: string }) => {
                   if (e?.id !== id) return
                   clearTimeout(timer)
                   bus.off('thinker:repair-response', handler)
                   if (e?.error) {
                     this.logger.warn('SelfHealingAgent: Thinker repair error', { id, error: e.error })
                   }
                   resolve(e?.text ?? '')
                 }
                 bus.on('thinker:repair-response', handler)
                 bus.emit({ type: 'thinker:repair-request', id, prompt })
               })
             }
           )
         await (this.intelligence.selfHealer as IntelligenceModule).start?.()
          this.logger.info('SelfHealingAgent wired and started')

        // WHY: ConsequenceEstimator + TrustLedger + PermissionOracle = graduated autonomy system
        try {
          this.wireModule(this.intelligence.consequenceEstimator, bus)
          this.wireModule(this.intelligence.trustLedger, bus)
          // WHY: Trust Ledger needs Memory DB for persisting trust scores across restarts
          const memoryDb = (this.intelligence.memory as { getDb?: () => import('better-sqlite3').Database }).getDb?.()
          interface AutonomyModule {
            setMemory?(memory: unknown): void
            init?(): Promise<void>
            start?(): void
          }
          if (memoryDb) {
            const trustLedger = this.intelligence.trustLedger as AutonomyModule
            trustLedger.setMemory?.(this.intelligence.memory)
          }
          this.wireModule(this.intelligence.permissionOracle, bus)
          // Init and start
          await (this.intelligence.consequenceEstimator as AutonomyModule).init?.()
          await (this.intelligence.trustLedger as AutonomyModule).init?.()
          await (this.intelligence.permissionOracle as AutonomyModule).init?.()
         await (this.intelligence.consequenceEstimator as IntelligenceModule).start?.()
         await (this.intelligence.trustLedger as IntelligenceModule).start?.()
         await (this.intelligence.permissionOracle as IntelligenceModule).start?.()
         this.logger.info('Graduated autonomy modules wired: ConsequenceEstimator, TrustLedger, PermissionOracle')
       } catch (err) {
         this.logger.warn(`Failed to wire autonomy modules: ${String(err)}`)
       }

      // Initialize Skill Metrics Tracker
      try {
        this.skillMetricsTracker = createSkillMetricsTracker(this.logger.child('skill-metrics'), bus)
        await this.skillMetricsTracker.initialize()
        this.logger.info('Skill Metrics Tracker initialized')
      } catch (err) {
        this.logger.warn(`Failed to initialize Skill Metrics Tracker: ${String(err)}`)
      }

      // Initialize Outcome Tracker (Phase 1 — feedback detection + tool outcome scoring)
      try {
        const tracker = createOutcomeTracker(this.logger.child('outcome-tracker'), bus)
        const memoryDb = (this.intelligence.memory as { getDb?: () => import('better-sqlite3').Database }).getDb?.()
        if (memoryDb) {
          tracker.initialize(memoryDb)
          // WHY: cycle hook enables per-turn outcome scoring during unified loop execution
          const loop = this.unifiedLoop
          if (loop?.addCycleHook) {
            loop.addCycleHook(tracker)
            this.logger.debug('OutcomeTracker registered as unified loop cycle hook')
          }
          this.outcomeTracker = tracker
          this.logger.debug('OutcomeTracker initialized')
        } else {
          this.logger.warn('OutcomeTracker skipped — memory DB not available')
        }
      } catch (err) {
        this.logger.warn(`Failed to initialize OutcomeTracker: ${String(err)}`)
      }

      // Initialize Phase 2 modules (Cross-Session Intelligence)
      const memoryDb2 = (this.intelligence.memory as { getDb?: () => import('better-sqlite3').Database }).getDb?.()
      const loop2 = this.unifiedLoop

      // Phase 2.1: Cross-Session Pattern Correlator
      try {
        if (memoryDb2) {
          const correlator = createCrossSessionCorrelator(this.logger.child('cross-session-correlator'))
          correlator.initialize(memoryDb2)
          if (loop2?.addCycleHook) {
            loop2.addCycleHook(correlator)
            this.logger.debug('CrossSessionCorrelator registered as unified loop cycle hook')
          }
          this.crossSessionCorrelator = correlator
          this.logger.debug('CrossSessionCorrelator initialized')
        }
      } catch (err) {
        this.logger.warn(`Failed to initialize CrossSessionCorrelator: ${String(err)}`)
      }

      // Phase 2.2: Strategy Effectiveness Tracker
      try {
        if (memoryDb2) {
          const stratTracker = createStrategyTracker(this.logger.child('strategy-tracker'), bus)
          stratTracker.initialize(memoryDb2)
          if (loop2?.addCycleHook) {
            loop2.addCycleHook(stratTracker)
            this.logger.debug('StrategyTracker registered as unified loop cycle hook')
          }
          this.strategyTracker = stratTracker
          this.logger.debug('StrategyTracker initialized')
        }
      } catch (err) {
        this.logger.warn(`Failed to initialize StrategyTracker: ${String(err)}`)
      }

      // Phase 2.3: Provider Performance Profiler
      try {
        if (memoryDb2) {
          const profiler = createProviderProfiler(this.logger.child('provider-profiler'), bus)
          profiler.initialize(memoryDb2)
          if (loop2?.addCycleHook) {
            loop2.addCycleHook(profiler)
            this.logger.debug('ProviderProfiler registered as unified loop cycle hook')
          }
          this.providerProfiler = profiler
          this.logger.debug('ProviderProfiler initialized')
        }
      } catch (err) {
        this.logger.warn(`Failed to initialize ProviderProfiler: ${String(err)}`)
      }

      // Phase 3: Adaptive Behavior Engine
      try {
        if (memoryDb2) {
          const adaptive = createAdaptiveBehavior(this.logger.child('adaptive-behavior'), bus)
          adaptive.initialize(memoryDb2)
          if (loop2?.addCycleHook) {
            loop2.addCycleHook(adaptive)
            this.logger.debug('AdaptiveBehavior registered as unified loop cycle hook')
          }
          this.adaptiveBehavior = adaptive
          this.logger.debug('AdaptiveBehavior initialized')
        }
      } catch (err) {
        this.logger.warn(`Failed to initialize AdaptiveBehavior: ${String(err)}`)
      }

      // Phase 4: Self-Verification Engine
      try {
        if (memoryDb2) {
          const verification = createSelfVerification(this.logger.child('self-verification'), bus)
          verification.initialize(memoryDb2)
          if (loop2?.addCycleHook) {
            loop2.addCycleHook(verification)
            this.logger.debug('SelfVerification registered as unified loop cycle hook')
          }
          this.selfVerification = verification
          this.logger.debug('SelfVerification initialized')
        }
      } catch (err) {
        this.logger.warn(`Failed to initialize SelfVerification: ${String(err)}`)
      }

      // Phase 5b: Runtime Self-Monitoring Hook
      try {
        const monitor = createMonitoringHook()
        // Subscribe to tool:executed events
        bus.on('tool:executed', (e: any) => {
          const callId = monitor.toolMonitor.startCall(e.toolName, e.sessionId)
          // Immediately end since the event is post-execution
          monitor.toolMonitor.endCall(
            callId,
            e.isError ? new Error('Tool execution failed') : undefined,
            e.sessionId,
          )
        })
        // Subscribe to provider:request_end for token tracking
        bus.on('provider:request_end', (e: any) => {
          const tokensUsed = (e.usageInput ?? 0) + (e.usageOutput ?? 0) + (e.tokensUsed ?? 0)
          if (tokensUsed > 0) {
            monitor.contextMonitor.checkPressure(tokensUsed, 200000, e.sessionId)
          }
        })
        // Subscribe to budget tier changes
        bus.on('budget:tier_changed', (e: any) => {
          const tierToThreshold: Record<string, number> = { normal: 0, cautious: 0.5, frugal: 0.75, critical: 0.9 }
          const ratio = tierToThreshold[e.newTier] ?? 0.5
          monitor.contextMonitor.checkPressure(
            Math.round(ratio * 200000), 200000, e.sessionId,
          )
        })
        this.monitoringHook = monitor
        this.logger.info('MonitoringHook initialized and wired to EventBus')
      } catch (err) {
        this.logger.warn(`Failed to initialize MonitoringHook: ${String(err)}`)
      }

      // Phase 5: Wire Improvement Orchestrator into adaptor modules
      try {
        const orch = this.intelligence?.improvementOrchestrator
        if (orch) {
          // Wire event bus for scenario generation triggers
          if ('setEventBus' in orch && bus) {
            orch.setEventBus(bus)
          }
          // Start the orchestrator (initializes persistence)
          if ('start' in orch) orch.start()
          // Register as cycle hook
          if (loop2?.addCycleHook) {
            loop2.addCycleHook(orch)
            this.logger.debug('ImprovementOrchestrator registered as unified loop cycle hook')
          }
          // Wire into AdaptiveBehavior
          if (this.adaptiveBehavior && 'setImprovementOrchestrator' in this.adaptiveBehavior) {
            (this.adaptiveBehavior as any).setImprovementOrchestrator(orch)
          }
          // Wire into AIEngineer
          if ('setImprovementOrchestrator' in this.intelligence.aiEngineer) {
            (this.intelligence.aiEngineer as any).setImprovementOrchestrator(orch)
          }
          // Wire into AIScientist
          if ('setImprovementOrchestrator' in this.intelligence.aiScientist) {
            (this.intelligence.aiScientist as any).setImprovementOrchestrator(orch)
          }
          this.logger.info('ImprovementOrchestrator initialized and wired')
        }
      } catch (err) {
        this.logger.warn(`Failed to initialize ImprovementOrchestrator: ${String(err)}`)
      }

      // Wire introspection sources into Thinker for self-aware thinking cycles
      // The Thinker uses these during deep think() to ground reflections in real metrics
      interface ThinkerWithIntrospection {
        setIntrospectionSources?(sources: {
          outcomeTracker?: unknown
          strategyTracker?: unknown
          crossSessionCorrelator?: unknown
          providerProfiler?: unknown
        }): void
      }
      try {
        const thinker = this.intelligence.thinker as ThinkerWithIntrospection
        if (thinker?.setIntrospectionSources) {
          thinker.setIntrospectionSources({
            outcomeTracker: this.outcomeTracker,
            strategyTracker: this.strategyTracker,
            crossSessionCorrelator: this.crossSessionCorrelator,
            providerProfiler: this.providerProfiler,
          })
          this.logger.info('Thinker wired with introspection sources')
        }
      } catch (err) {
        this.logger.warn(`Failed to wire Thinker introspection sources: ${String(err)}`)
      }

      // Listen for Thinker's proactive events
      interface ThinkerInjectInsightEvent {
        urgency?: number
        insight?: string
      }
      interface ThinkerEarlyWarningEvent {
        warning: string
      }
      // REMOVED: OptimizerWithEarlyWarning — OptimizerModule deleted
      bus.on('thinker:inject-insight', (e) => {
        const event = e as ThinkerInjectInsightEvent
        this.logger.info('Thinker injecting insight', { urgency: event.urgency })
        // REMOVED: injectionAggregator.setThinkerInsight — InjectionAggregator deleted.
        if (event.insight && this.intelligence?.globalWorkspace) {
          this.intelligence.globalWorkspace.submit({
            signalId: `thinker-insight-${Date.now()}`,
            source: 'thinker',
            sessionId: (event as any).sessionId ?? '*',
            type: 'insight',
            content: event.insight,
            luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, cognitiveResonance: 0, strategicImportance: 0, composite: 0 },
            createdAt: Date.now(),
            urgencyHint: (event as any).urgency === 'high' ? 0.15 : 0,
          })
        }
      })

      bus.on('thinker:early-warning', (e) => {
        const event = e as ThinkerEarlyWarningEvent
        this.logger.warn('Thinker early warning', { pattern: event.warning })
        // REMOVED: optimizer.handleEarlyWarning — OptimizerModule deleted
      })

      bus.on('thinker:self-modified', (e) => {
        this.logger.info('Thinker self-modified strategy', e.change)
      })

      bus.on('thinker:swarm-deployed', (e) => {
        this.logger.info('Thinker deployed swarm', { swarmId: e.swarmId, mission: e.mission })
      })

      this.logger.info(`Intelligence layer loaded`, { modules: this.intelligence.all.length })
      // Summarize cycle hooks attached to unified loop
      if (this.unifiedLoop) {
        const hooks: string[] = []
        if (this.outcomeTracker) hooks.push('OutcomeTracker')
        if (this.crossSessionCorrelator) hooks.push('CrossSessionCorrelator')
        if (this.strategyTracker) hooks.push('StrategyTracker')
        if (this.providerProfiler) hooks.push('ProviderProfiler')
        if (this.adaptiveBehavior) hooks.push('AdaptiveBehavior')
        if (this.selfVerification) hooks.push('SelfVerification')
        if (hooks.length > 0) {
          this.logger.info(`Unified Loop hooks: ${hooks.join(', ')}`)
        }
      }
    } catch (err) {
      this.logger.warn(`failed to initialize intelligence layer: ${String(err)}`)
    }

    completePhase('intelligence', {
      modules: this.intelligence?.all.length ?? 0,
    })

    // Helper to resolve worker path (handles both .js and .ts)
    const __dirname = path.dirname(fileURLToPath(import.meta.url))
    const resolveWorker = (relPath: string): string | null => {
      const jsPath = path.resolve(__dirname, `${relPath  }.js`)
      if (fs.existsSync(jsPath)) return jsPath
      const tsPath = path.resolve(__dirname, `${relPath  }.ts`)
      if (fs.existsSync(tsPath)) return tsPath
      return null
    }

    // 6. Load the echo-channel worker (phase 1, optional — only if explicitly enabled)
    this.logger.info('── Phase 3: Channels ──────────────────────────────────')

    const echoEnabled = this.config.get<boolean>("channels.echo.enabled", false)
    const echoPath = echoEnabled ? resolveWorker("../workers/echo-channel") : null

    if (!echoEnabled) {
      // Silent skip — echo is a debug/test channel, not noteworthy
    } else if (!echoPath) {
      this.logger.warn("echo-channel worker not found; continuing without it")
    } else {
      try {
        await this.pluginHost.load({
          id: "echo-channel",
          entryPoint: echoPath,
          restartOnCrash: true,
          maxRestarts: 5,
          config: {},
        })
      } catch (err) {
        this.logger.warn(`failed to load echo-channel: ${String(err)}`)
      }
    }

    // 7. Load webchat channel worker (Phase 3)
    const webchatPath = resolveWorker("../workers/channels/webchat")
    if (!webchatPath) {
      this.logger.warn("webchat worker not found; skipping")
    } else {
      try {
        const enabled = this.config.get<boolean>("channels.webchat.enabled", false)
        this.logger.info(`webchat.enabled -> ${enabled}`)
        if (!enabled) {
          this.logger.info('webchat channel disabled by config; skipping')
        } else {
          const webchatPort = this.config.get<number>("channels.webchat.port", 3000)
          await this.pluginHost.load({
            id: "channel:webchat",
            entryPoint: webchatPath,
            restartOnCrash: true,
            maxRestarts: 5,
            config: { port: webchatPort },
          });
          this.logger.info(`Webchat channel listening on port ${webchatPort}`);
        }
      } catch (err) {
        this.logger.warn(`failed to load webchat: ${String(err)}`);
      }
    }

    // 7b. Load CLI channel worker (default-enabled; opt out via channels.cli.enabled=false)
    const cliEnabled = this.config.get<boolean>("channels.cli.enabled", true)
    const cliPath = cliEnabled ? resolveWorker("../workers/channels/cli") : null
    if (!cliEnabled) {
      this.logger.info("CLI channel disabled by config; skipping")
    } else if (!cliPath) {
      this.logger.warn("cli worker not found; skipping")
    } else {
      try {
        await this.pluginHost.load({
          id: "channel:cli",
          entryPoint: cliPath,
          restartOnCrash: true,
          maxRestarts: 5,
          config: {},
        })
        this.logger.info(`CLI channel active`)
      } catch (err) {
        this.logger.warn(`failed to load cli channel: ${String(err)}`)
      }
    }

    // 7c. Load Telegram channel worker (optional — requires channels.telegram.token in config)
    // Config accepts both "token" and "botToken" key names for the Bot API token.
    // Config accepts both "allowedChatIds" and "allowFrom" key names for the allowlist.
    const tgEnabled = this.config.get<boolean>("channels.telegram.enabled", false)
    const tgToken = this.config.get<string>("channels.telegram.token", "")
               || this.config.get<string>("channels.telegram.botToken", "")

    // Initialize PrimarySessionRouter — routes ALL channel messages to cassi:primary
    this.primaryRouter = createPrimarySessionRouter(this.config, this.logger)
    if (this.primaryRouter) {
      this.logger.info(`[primary-router] Conductor session enabled: ${this.primaryRouter.primarySessionId}`)
    }
    if (tgEnabled && tgToken) {
      const tgPath = resolveWorker("../workers/channels/telegram")
      if (!tgPath) {
        this.logger.warn("telegram worker not found; skipping")
      } else {
        try {
          const allowedChatIds = (this.config.get<number[]>("channels.telegram.allowedChatIds", []) as number[]).length
            ? this.config.get<number[]>("channels.telegram.allowedChatIds", [])
            : this.config.get<number[]>("channels.telegram.allowFrom", [])
          await this.pluginHost.load({
            id: "channel:telegram",
            entryPoint: tgPath,
            restartOnCrash: true,
            maxRestarts: 5,
            config: { token: tgToken, allowedChatIds },
          })
          this.logger.info(`Telegram channel active`)
        } catch (err) {
          this.logger.warn(`failed to load telegram: ${String(err)}`)
        }
      }
    } else if (tgToken && !tgEnabled) {
      this.logger.info(`Telegram channel disabled by config; skipping`)
    }

    // 7d. Load OpenCode channel worker (optional — requires channels.opencode.enabled in config)
    const ocEnabled = this.config.get<boolean>("channels.opencode.enabled", false)
    if (ocEnabled) {
      const ocPath = resolveWorker("../workers/channels/opencode")
      if (!ocPath) {
        this.logger.warn("opencode channel worker not found; skipping")
      } else {
        try {
          const ocDbPath = this.config.get<string>("channels.opencode.dbPath", "")
          const ocServerUrl = this.config.get<string>("channels.opencode.serverUrl", "")
          const ocPollIntervalMs = this.config.get<number>("channels.opencode.pollIntervalMs", 2000)
          const ocLookbackMs = this.config.get<number>("channels.opencode.lookbackMs", 30000)
          const ocSessionId = this.config.get<string>("channels.opencode.sessionId", "")
          await this.pluginHost.load({
            id: "channel:opencode",
            entryPoint: ocPath,
            restartOnCrash: true,
            maxRestarts: 5,
            config: {
              ...(ocDbPath ? { dbPath: ocDbPath } : {}),
              ...(ocServerUrl ? { serverUrl: ocServerUrl } : {}),
              pollIntervalMs: ocPollIntervalMs,
              lookbackMs: ocLookbackMs,
              ...(ocSessionId ? { openCodeSessionId: ocSessionId } : {}),
            },
          })
          this.logger.info(`OpenCode channel active`, {
            dbPath: ocDbPath || '~/.local/share/opencode/opencode.db (default)',
            pollIntervalMs: ocPollIntervalMs,
            serverUrl: ocServerUrl || '(none)',
          })
        } catch (err) {
          this.logger.warn(`failed to load opencode channel: ${String(err)}`)
        }
      }
    } else {
      this.logger.info(`OpenCode channel disabled by config; skipping`)
    }

    completePhase('channels', {
      plugins: this.pluginHost.all().length,
    })

    this.logger.info('── Phase 4: Providers & Wiring ────────────────────────')

    // Must be created before providers so CentralizedProvider can record usage
    let budgetTracker: BudgetTracker | undefined
    let modelRouter: ModelRouter | undefined
    try {
      const budgetConfig = this.config.get<Record<string, { monthlyLimit: number }>>('budget.providers', {})
      const budgets: Record<string, { monthlyLimit: number }> = {}
      for (const [id, cfg] of Object.entries(budgetConfig)) {
        if (cfg?.monthlyLimit) budgets[id] = { monthlyLimit: cfg.monthlyLimit }
      }
      budgetTracker = createBudgetTracker(this.logger, Object.keys(budgets).length > 0 ? budgets : undefined)
      budgetTracker.wire(this.bus)
      await budgetTracker.loadFromDisk()
      this.budgetTracker = budgetTracker
      this.logger.info('BudgetTracker initialized and wired to EventBus')

      modelRouter = createModelRouter(this.logger, budgetTracker)
      this.modelRouter = modelRouter
      this.logger.info('ModelRouter initialized')
    } catch (err) {
      this.logger.warn('Failed to initialize BudgetTracker/ModelRouter', { error: String(err) })
    }

    let providers: Map<string, IProvider> = new Map()
    try {
      const { createProviders } = await import('./providers/index.js')
      providers = createProviders(this.config, this.logger, {
        centralized: true,
        bus: this.bus,
      })
        // Store providers on daemon instance for admin API access
        ; this.providers = providers
      // Log provider summary
      if (providers.size > 0) {
        const providerSummary = Array.from(providers.entries())
          .map(([id, p]) => `${id}(${(p as any).model ?? '?'})`)
          .join(', ')
        this.logger.info(`${providers.size} provider(s) ready: ${providerSummary}`)
      }
    } catch (err) {
      this.logger.warn('Providers not loaded — run Phase 3 providers build')
    }

    // Wire BudgetTracker into all CentralizedProvider instances
    interface ProviderWithBudgetTracker {
      setBudgetTracker?(tracker: BudgetTracker): void
    }
    if (budgetTracker && providers.size > 0) {
      for (const [id, p] of providers) {
        const provider = p as ProviderWithBudgetTracker
        if (typeof provider.setBudgetTracker === 'function') {
          provider.setBudgetTracker(budgetTracker)
        }
      }
      this.logger.info('BudgetTracker wired to CentralizedProvider instances')
    }

    // Open RateLimitStore and wire into all CentralizedProvider instances.
    // This restores learned 429 limits from the previous run so the daemon
    // enforces known ceilings immediately without re-hitting them on startup.
    try {
      const { RateLimitStore } = await import('./providers/rate-limit-store.js')
      const dataDir = String(this.config?.get?.('dataDir') ?? join(homedir(), '.cassicore', 'data'))
      const rateLimitStore = RateLimitStore.open(this.logger, dataDir)
      this.rateLimitStore = rateLimitStore
      if (providers.size > 0) {
        interface ProviderWithRateLimitStore {
          setRateLimitStore?(store: typeof rateLimitStore): void
        }
        let wired = 0
        for (const [, p] of providers) {
          const provider = p as ProviderWithRateLimitStore
          if (typeof provider.setRateLimitStore === 'function') {
            provider.setRateLimitStore(rateLimitStore)
            wired++
          }
        }
        this.logger.info('RateLimitStore wired to CentralizedProvider instances', { wired })
      }
    } catch (err) {
      this.logger.warn('RateLimitStore: failed to open, adaptive limits will not be persisted', { error: String(err) })
    }

    try {
      const providerKeys = providers
      this.modelDirective = new ModelDirective({
        config: this.config,
        eventBus: this.bus,
        logger: this.logger,
        availableProviders: () => Array.from(providerKeys.keys()),
        getProviderModels: (providerId: string) => {
          const provider = providers.get(providerId)
          return provider ? provider.models : null
        },
        persistDefault: (cfg, slot) => {
          try {
            const layered = this.config as any
            if (typeof layered.setOverride === 'function') {
              if (slot) {
                // Slot-specific override → persist under intelligence.modelDirective.slots.<slot>
                layered.setOverride(`intelligence.modelDirective.slots.${slot}.provider`, cfg.provider, { reason: 'model-directive' })
                layered.setOverride(`intelligence.modelDirective.slots.${slot}.model`, cfg.model, { reason: 'model-directive' })
              } else {
                // Slot-less default
                layered.setOverride('intelligence.modelDirective.default.provider', cfg.provider, { reason: 'model-directive' })
                layered.setOverride('intelligence.modelDirective.default.model', cfg.model, { reason: 'model-directive' })
              }
            }
          } catch { /* non-critical */ }
        },
      })
      this.logger.info('ModelDirective initialized')
    } catch (err) {
      this.logger.warn('Failed to initialize ModelDirective', { error: String(err) })
    }

    // Wire activeRequests getter into the unified loop for heartbeat enrichment.
    // Counts in-flight requests across all CentralizedProvider instances.
    if (this.unifiedLoop && providers.size > 0) {
      interface ProviderWithMetrics { getMetrics?(): { activeRequests?: number } }
      const providerRefs = Array.from(providers.values())
      this.unifiedLoop.setActiveRequestsGetter(() => {
        let total = 0
        for (const p of providerRefs) {
          const pm = p as ProviderWithMetrics
          total += pm.getMetrics?.()?.activeRequests ?? 0
        }
        return total
      })
    }

    try {
      const { PromptLogStore } = await import('./prompt-log-store.js')
      const { withPromptLogging } = await import('./prompt-log-provider.js')
      const promptLogDbPath = join(
        String(this.config?.get?.('dataDir') ?? join(homedir(), '.cassicore', 'data')),
        'prompt-log.db',
      )
      const promptLogStore = new PromptLogStore(promptLogDbPath, this.logger)
      this.promptLogStore = promptLogStore

      for (const [id, provider] of providers) {
        providers.set(id, withPromptLogging(provider, promptLogStore, id))
      }

      // Daily cleanup of old entries
      const cleanupInterval = setInterval(() => {
        try { promptLogStore.cleanup() } catch {}
      }, 24 * 60 * 60 * 1000)
      cleanupInterval.unref()

      this.logger.info('Prompt logging enabled — all provider calls will be captured')
    } catch (err) {
      this.logger.warn('Failed to initialize prompt log store', { error: String(err) })
    }

    // Initialize Timeline Store — unified chronological view of all system data
    try {
      const { TimelineStore } = await import('./timeline-store.js')
      const timelineDbPath = join(
        String(this.config?.get?.('dataDir') ?? join(homedir(), '.cassicore', 'data')),
        'timeline.db',
      )
      const timelineStore = new TimelineStore(timelineDbPath, this.logger)
      this.timelineStore = timelineStore

      // Wire event bus → timeline ingestion (onAll captures every event)
      const unsub = bus.onAll((event) => {
        timelineStore.ingest(event as unknown as Record<string, unknown>)
      })

      // Store the unsubscribe for cleanup (attach to store for access)
      ;(timelineStore as any)._busUnsub = unsub

      // Emit retention events to the bus (picked up by cognitive feed TimeStore topic)
      timelineStore.onRetention = (deleted) => {
        const stats = timelineStore.getStats()
        bus.emit({
          type: 'system:event' as any,
          timestamp: new Date(),
          sessionId: 'timeline',
          message: `Timeline retention: deleted ${deleted} entries. Total: ${stats.totalEntries}, DB: ${(stats.dbSizeBytes / 1024 / 1024).toFixed(1)}MB`,
        })
      }

      this.logger.info('Timeline store initialized — all events will be captured chronologically')
    } catch (err) {
      this.logger.warn('Failed to initialize timeline store', { error: String(err) })
    }

    // Wire the default provider into the Thinker so it can make real calls
    interface ThinkerWithProvider {
      setProvider?(provider: IProvider): void
      setConfig?(config: IConfig): void
      setModelRouter?(router: ModelRouter): void
      init?(): Promise<void>
    }
    if (this.intelligence?.thinker) {
      const defaultProviderId = this.config.get<string>('intelligence.defaultProvider', '') || MODEL_DEFAULTS.fast.provider
      const thinkerProvider = providers.get(defaultProviderId) ?? providers.values().next().value
      const thinker = this.intelligence.thinker as ThinkerWithProvider
      if (thinkerProvider) {
        thinker.setProvider?.(thinkerProvider)
        this.logger.info(`Thinker provider wired: ${thinkerProvider.id}`)
      } else {
        this.logger.warn('Thinker: no provider available — thinking cycles will be skipped')
      }
      // Wire config and run BaseCognitiveModule lifecycle
      thinker.setConfig?.(this.config)
      // Wire model router for budget-aware model selection
      if (modelRouter) {
        thinker.setModelRouter?.(modelRouter)
        this.logger.info('Thinker model router wired')
      }
      await thinker.init?.()
    }

    // Wire the provider into the Drone Swarm Controller
    // Drones use the fallback tier (github-copilot/gpt-5-mini) by default — free on request-based billing.
    if (this.intelligence?.droneSwarm) {
      const droneProviderId = this.config.get<string>('intelligence.droneSwarm.provider', '') || 'github-copilot'
      const droneProvider = providers.get(droneProviderId) ?? providers.get('github-copilot') ?? providers.values().next().value
      if (droneProvider) {
        this.intelligence.droneSwarm.setProvider(droneProvider)
        this.logger.info(`DroneSwarm provider wired: ${droneProvider.id}`)
      } else {
        this.logger.warn('DroneSwarm: no provider available — drone swarms will be unavailable')
      }

      // WHY: Each drone tier specifies its own providerId via MODEL_DEFAULTS (e.g. 'alibaba-coding'
      // for the fallback tier). Without a resolver, drones send the wrong model name to the
      // default provider, producing empty results.
      this.intelligence.droneSwarm.setProviderResolver((providerId: string) => providers.get(providerId))

      // Wire cognitive modules into DroneSwarm for signal extraction from drone outputs.
      // This enables: drone output → ThoughtObserver → CognitiveBridge → parent session.
      // All processing is local — zero additional LLM requests.
      if (this.intelligence.thoughtObserver) {
        this.intelligence.droneSwarm.setThoughtObserver(this.intelligence.thoughtObserver)
      }
      if (this.intelligence.cognitiveBridge) {
        this.intelligence.droneSwarm.setCognitiveBridge(this.intelligence.cognitiveBridge)
      }
    }

    // Wire the provider into the DialecticSystem (Yang, Yin, Serenity)
    interface DialecticWithProvider {
      setProvider?(provider: IProvider): void
    }
    interface SubconsciousWithProvider {
      setProvider?(provider: IProvider): void
    }
    if (this.intelligence?.dialectic) {
      const dialecticProviderId = this.config.get<string>('intelligence.dialectic.provider', '') || 'github-copilot'
      const dialecticProvider = providers.get(dialecticProviderId) ?? providers.get('github-copilot') ?? providers.values().next().value
      const dialectic = this.intelligence.dialectic as DialecticWithProvider
      if (dialecticProvider) {
        dialectic.setProvider?.(dialecticProvider)
        this.logger.info(`Dialectic provider wired: ${dialecticProvider.id}`)

        // Wire provider to Subconscious. Prefer a dedicated subconscious provider if configured,
        // otherwise fall back to the dialectic provider.
        try {
          const subconsciousProviderId = this.config.get<string>('intelligence.subconscious.provider', '') || ''
          const subconsciousProvider = subconsciousProviderId ? providers.get(subconsciousProviderId) : dialecticProvider
          const subconscious = this.intelligence.subconscious as SubconsciousWithProvider
          if (subconsciousProvider && subconscious?.setProvider) {
            subconscious.setProvider(subconsciousProvider)
            this.logger.info(`Subconscious provider wired: ${subconsciousProvider.id}`)
          }
        } catch (err) {
          this.logger.warn('Subconscious: failed to wire provider', { error: String(err) })
        }
      } else {
        this.logger.warn('Dialectic: no provider available — dialectic observations will be skipped')
      }
    }

    // Wire ModelRouter into Memory/Archivist for budget-aware archival model selection
    interface MemoryWithModelRouter {
      setModelRouter?(router: ModelRouter): void
    }
    if (modelRouter && this.intelligence?.memory) {
      try {
        const memory = this.intelligence.memory as MemoryWithModelRouter
        if (typeof memory.setModelRouter === 'function') {
          memory.setModelRouter(modelRouter)
          this.logger.info('Memory/Archivist model router wired')
        }
      } catch (err) {
        this.logger.warn('Failed to wire model router to Memory/Archivist', { error: String(err) })
      }
    }

    // Wire Helix + Constellation with a dedicated ModelPool.
    // copilot-sdk warm sessions return 400 for Helix's tool-heavy multi-posture prompts,
    // so this pool routes directly to configured providers without copilot-sdk.
    if ((this.intelligence?.helix || this.intelligence?.constellation) && providers.size > 0) {
      try {
        const directive = this.modelDirective
        const defaultRouting = directive
          ? directive.resolve()
          : {
              provider: this.config.get<string>('intelligence.helix.provider', 'alibaba-coding'),
              model: this.config.get<string>('intelligence.helix.model', 'kimi-k2.5'),
            }
        const helixBlockedProviders = this.config.get<string[]>('intelligence.helix.blockedProviders', ['github-copilot-lb'])
        const helixAllowedModels = this.config.get<Record<string, string[]>>('intelligence.helix.allowedModels', {
          'github-copilot': ['gpt-4o', 'gpt-4.1', 'gpt-5-mini'],
        })

        const kimiConfig = directive ? directive.resolveTier('kimi')    : { provider: 'alibaba-coding', model: 'kimi-k2.5' }
        const glmConfig  = directive ? directive.resolveTier('glm')     : { provider: 'alibaba-coding', model: 'glm-5' }
        const qwenMaxCfg = directive ? directive.resolveTier('qwenMax') : { provider: 'alibaba-coding', model: 'qwen3-max-2026-01-23' }
        const qwenPlusCfg= directive ? directive.resolveTier('qwenPlus'): { provider: 'alibaba-coding', model: 'qwen3.6-plus' }
        const bgConfig   = directive ? directive.resolveTier('background'): { provider: 'github-copilot', model: 'gpt-5-mini' }
        const claudeHaikuCfg  = directive ? directive.resolveTier('background') : { provider: 'claude-code', model: 'claude-haiku-4-5' }


        const makeHelixChain = (slot: string, tierCfg: { provider: string; model: string }) => ({
          slotName: slot,
          chain: [
            { role: slot, provider: tierCfg.provider, model: tierCfg.model, priority: 10 },
            { role: slot, provider: bgConfig.provider, model: bgConfig.model, priority: 5 },
          ],
          triggers: ['rate_limit' as const, 'timeout' as const, 'model_unavailable' as const, 'error' as const],
        })

        const brainstemChain = {
          slotName: 'brainstem',
          chain: [
            { role: 'brainstem', provider: claudeHaikuCfg.provider, model: claudeHaikuCfg.model, priority: 10 },
            { role: 'brainstem', provider: bgConfig.provider, model: bgConfig.model, priority: 5 },
          ],
          triggers: ['rate_limit' as const, 'timeout' as const, 'model_unavailable' as const, 'error' as const],
        }
        const miniHelixCorpusChain = {
          slotName: 'mini-helix:corpus',
          chain: [
            { role: 'mini-helix:corpus', provider: qwenPlusCfg.provider, model: qwenPlusCfg.model, priority: 10 },
            { role: 'mini-helix:corpus', provider: bgConfig.provider, model: bgConfig.model, priority: 5 },
          ],
          triggers: ['rate_limit' as const, 'timeout' as const, 'model_unavailable' as const, 'error' as const],
        }
        const miniHelixBrainstemChain = {
          slotName: 'mini-helix:brainstem',
          chain: [
            { role: 'mini-helix:brainstem', provider: claudeHaikuCfg.provider, model: claudeHaikuCfg.model, priority: 10 },
            { role: 'mini-helix:brainstem', provider: bgConfig.provider, model: bgConfig.model, priority: 5 },
          ],
          triggers: ['rate_limit' as const, 'timeout' as const, 'model_unavailable' as const, 'error' as const],
        }

        const { ModelPool } = await import('./model-pool/index.js')
        const helixModelPool = new ModelPool({
          logger: this.logger.child('helix-pool'),
          eventBus: this.bus,
          fallbackChains: [
            makeHelixChain('yang', qwenPlusCfg),
            makeHelixChain('yin', qwenPlusCfg),
            makeHelixChain('apex', qwenPlusCfg),
            makeHelixChain('unity', qwenPlusCfg),
            makeHelixChain('helix', qwenPlusCfg),
            brainstemChain,
            miniHelixCorpusChain,
            miniHelixBrainstemChain,
          ],
          budgetScopes: [],
          defaultTimeoutMs: this.config.get<number>('intelligence.helix.timeoutMs', 600000),
          auditEnabled: false,
          blockedProviders: helixBlockedProviders,
          allowedModels: helixAllowedModels,
        })
        helixModelPool.setProviders(providers)
        this.helixModelPool = helixModelPool

        if (this.intelligence?.helix) {
          this.intelligence.helix.setModelPool(helixModelPool)
          if (directive && typeof (this.intelligence.helix as any).setModelDirective === 'function') {
            (this.intelligence.helix as any).setModelDirective(directive)
          }
          this.logger.info('Helix ModelPool wired', { provider: defaultRouting.provider, model: defaultRouting.model })
        }

        if (this.intelligence?.constellation) {
          this.intelligence.constellation.setModelPool(helixModelPool)
          if (directive) {
            this.intelligence.constellation.setModelDirective(directive)
          }
          this.logger.info('Constellation ModelPool wired (shared with Helix)', { provider: defaultRouting.provider, model: defaultRouting.model })
        }

        // Wire Meditation handleFactory so SoloRunners can acquire model handles
        // Use 'unity' slot — meditation explorers share the same model tier as Helix unity agents
        if (this.intelligence?.setMeditationHandleFactory) {
          this.intelligence.setMeditationHandleFactory(
            (config) => helixModelPool.acquire('unity', config.tier, config.sessionId),
          )
          this.logger.info('Meditation handleFactory wired (shared ModelPool)')
        }
      } catch (err) {
        this.logger.warn('Failed to wire Helix/Constellation ModelPool', { error: String(err) })
      }
    }

    // Create shared ContextDistiller — Phase Zero context injection for teams/helix.
    // Must be created after providers and ModelPools are wired.
    if (this.intelligence && providers.size > 0) {
      try {
        const { ContextDistiller } = await import('./intelligence/context-distiller.js')
        const contextDistiller = new ContextDistiller(this.logger)

        // Wire ModelPool — use Helix pool
        const distillerPool = this.helixModelPool
        if (distillerPool) {
          contextDistiller.setModelPool(distillerPool)
        }

        // Wire ModelDirective for routing overrides
        if (this.modelDirective) {
          contextDistiller.setModelDirective(this.modelDirective)
        }

        // Wire PromptLogStore for parent conversation access
        if (this.promptLogStore) {
          contextDistiller.setPromptLogStore(this.promptLogStore)
        }

        // Wire Memory for enrichment search
        if (this.intelligence.memory) {
          contextDistiller.setMemory(this.intelligence.memory)
        }

        try {
          const artifactStore = FileArtifactStore.open(this.logger)
          contextDistiller.setFileArtifactStore(artifactStore)
        } catch (err) {
          this.logger.warn('Failed to wire FileArtifactStore into ContextDistiller', { error: String(err) })
        }

        // Wire EventBus for parent session auto-detection via tool-call fingerprinting.
        // Cast needed because IEventBus doesn't expose getGlobalEventsSince(),
        // but the concrete EventBus (which the daemon always creates) does.
        if (typeof (this.bus as any).getGlobalEventsSince === 'function') {
          contextDistiller.setEventBus(this.bus as any)
        }

        // Store for wiring into orchestrators during pipeline-tools phase
        this.contextDistiller = contextDistiller
        this.logger.info('ContextDistiller (Phase Zero) created', {
          hasModelPool: !!distillerPool,
          hasPromptLog: !!this.promptLogStore,
          hasMemory: !!this.intelligence.memory,
          hasEventBus: true,
        })
      } catch (err) {
        this.logger.warn('Failed to create ContextDistiller — teams will start without Phase Zero context', {
          error: String(err),
        })
      }
    }

    completePhase('providers-routing', {
      providers: providers.size,
      budgetTracker: !!budgetTracker,
      modelRouter: !!modelRouter,
    })

    // Create sessions and turn pipeline
    this.logger.info('── Phase 5: Pipeline & Tools ───────────────────────────')

    const systemPrompt = buildSystemPrompt(this.logger)
    this.logger.info(`System prompt built (${systemPrompt.length} chars)`)
    const sessionStore = SessionStore.open(this.logger)

    // Initialize FileArtifactStore for agent file sharing
    let fileArtifactStore: FileArtifactStore | undefined
    try {
      fileArtifactStore = FileArtifactStore.open(this.logger)
      this.logger.info('FileArtifactStore initialized for agent file sharing')
    } catch (err) {
      this.logger.warn('FileArtifactStore not available', { error: String(err) })
    }

    // Initialize CodeStore for CassiCore source files in the mnemic field
    let codeStore: CodeStore | undefined
    try {
      const field = new MnemicField(this.logger)
      field.enableNeuralKindling()
      sessionStore.setMnemicField(field)
      this.logger.info('SessionStore MnemicField replay bridge wired')
      if (this.intelligence?.audit && typeof (this.intelligence.audit as any).setMnemicField === 'function') {
        const auditStore = this.intelligence.audit as any
        auditStore.setMnemicField(field)
        this.logger.info('AuditStore MnemicField replay bridge wired')
      }
      
      // Initialize ANN indexes asynchronously (non-blocking)
      field.initializeAnn().catch(err => {
        this.logger.warn('ANN initialization failed, will use brute-force fallback', { error: String(err) })
      })
      
      codeStore = new CodeStore(field, this.logger)
      ;(this as any).__codeStore = codeStore
      ;(this as any).__mnemicFieldForCode = field
      this.logger.info('CodeStore initialized for codebase-in-database')
      if (this.intelligence?.cortex) {
        try {
          this.intelligence.cortex.setAffectRegister(field.getAffectRegister())
          const { createConsolidationBridge } = await import('./intelligence/cortex/mnemic-bridge.js')
          this.intelligence.cortex.setConsolidationCallback(
            createConsolidationBridge(field, this.logger)
          )
          field.setCorticalField(this.intelligence.cortex)
        } catch (err) {
          this.logger.warn('Cortex affect/consolidation bridge not available', { error: String(err) })
        }
      }

      // Wire MnemicField into meditation controller for post-session spiking/consolidation
      if (this.intelligence?.meditation && typeof (this.intelligence.meditation as any).setMnemicField === 'function') {
        (this.intelligence.meditation as any).setMnemicField(field)
        this.logger.info('Meditation MnemicField wired')
      }

      // Wire MnemicField into memory module so cassi_memory store creates engrams
      if (this.intelligence?.memory && typeof (this.intelligence.memory as any).setMnemicField === 'function') {
        (this.intelligence.memory as any).setMnemicField(field)
        this.logger.info('Memory MnemicField bridge wired')

        try {
          const dualWriteTurns = this.config.get<boolean>('intelligence.memory.dualWriteTurns')
          if (typeof dualWriteTurns === 'boolean' && typeof (this.intelligence.memory as any).setDualWriteTurns === 'function') {
            ;(this.intelligence.memory as any).setDualWriteTurns(dualWriteTurns)
          }
        } catch (err) {
          this.logger.debug('Memory dualWriteTurns config read failed', { error: String(err) })
        }

        const memoryAny = this.intelligence.memory as { getConsolidationEngine?: () => { setMnemicConsolidation?: (r: unknown) => void } }
        const consolidation = memoryAny.getConsolidationEngine?.()
        if (consolidation && typeof consolidation.setMnemicConsolidation === 'function') {
          consolidation.setMnemicConsolidation(field)
          this.logger.info('Consolidation receiver wired (legacy → mnemic)')
        }
      }

      // Wire MnemicField into Archivist so each archive write produces an engram
      // inline (fail-open). Replaces the old ArchiveIngestionBridge polling path.
      try {
        const archivist = (this.intelligence?.memory as any)?.getArchivist?.()
        if (archivist && typeof archivist.setMnemicField === 'function') {
          archivist.setMnemicField(field)
          this.logger.info('Archivist MnemicField bridge wired')
        }
      } catch (err) {
        this.logger.warn('Archivist MnemicField wiring failed', { error: String(err) })
      }

      // Store MnemicField on intelligence layer for post-boot wiring (e.g. Thalamus)
      ;(this.intelligence as any).__mnemicField = field

      // Wire MnemicField into constellation orchestrator
      if (this.intelligence?.constellation && typeof this.intelligence.constellation.setMnemicField === 'function') {
        this.intelligence.constellation.setMnemicField(field)
      }

      // REMOVED: MnemicField injection source registration — InjectionAggregator deleted.
      // MnemicField content is now accessed directly by Thalamus.

      // Wire LLM reranker into MnemicField (alternative to filament kindling).
      // Uses gpt-5-mini for fast (~1s) cross-encoder reranking vs ~30s for kindling.
      const rerankerProviderId = this.config.get<string>('intelligence.mnemic.rerankerProvider', 'github-copilot')
      const rerankerModel = this.config.get<string>('intelligence.mnemic.rerankerModel', 'gpt-5-mini')
      const rerankerProvider = providers.get(rerankerProviderId) ?? providers.values().next().value
      const rerankerEnabled = this.config.get<boolean>('intelligence.mnemic.rerankerEnabled', true)
      if (rerankerProvider && rerankerEnabled) {
        field.setRerankerProvider(rerankerProvider, rerankerModel, true)
        this.logger.info(`MnemicField LLM reranker wired: ${rerankerProviderId}/${rerankerModel}`)
      } else if (!rerankerEnabled) {
        this.logger.info('MnemicField LLM reranker disabled by config')
      } else {
        this.logger.warn('MnemicField LLM reranker: no provider available')
      }

      const lightningShadow = this.config.get<boolean>('intelligence.mnemic.lightningShadow', false)
      if (lightningShadow) {
        field.setLightningShadowMode(true)
        this.logger.info('MnemicField Lightning Indexer shadow mode enabled')
      }

      // Wire GlobalWorkspace into constellation orchestrator so spawned Helix
      // sessions boot in brain-integrated mode (Conductor + journal + locus).
      if (
        this.intelligence?.constellation &&
        this.intelligence.globalWorkspace &&
        typeof (this.intelligence.constellation as any).setGlobalWorkspace === 'function'
      ) {
        ;(this.intelligence.constellation as any).setGlobalWorkspace(this.intelligence.globalWorkspace)
      }

      // MnemicField injection — now handled by Thalamus via Aurora cognitive state

      // ArchiveIngestionBridge is no longer wired into the unified loop. Live
      // engram creation now happens inline inside Archivist via setMnemicField
      // above; the bridge module remains as a one-shot backfill utility.

      // Initialize Self-Model Field — a second Mnemic Field for architectural self-knowledge.
      // Stores semantic understanding of the codebase (modules, capabilities, weaknesses)
      // and connects to the episodic field via portal engrams for cross-field retrieval.
      try {
        const { SelfModelField } = await import('./intelligence/mnemic-field/self-model/self-model-field.js')
        const { InterFieldBridge } = await import('./intelligence/mnemic-field/self-model/inter-field-bridge.js')

        const selfModelField = new SelfModelField(this.logger)
        const interFieldBridge = new InterFieldBridge(field, selfModelField, this.logger)
        interFieldBridge.rebuildFromPersisted()

        ;(this as any).__selfModelField = selfModelField
        ;(this as any).__interFieldBridge = interFieldBridge
        ;(this.intelligence as any).__selfModelField = selfModelField
        ;(this.intelligence as any).__interFieldBridge = interFieldBridge

        if (this.intelligence?.meditation) {
          if (typeof (this.intelligence.meditation as any).setSelfModelField === 'function') {
            (this.intelligence.meditation as any).setSelfModelField(selfModelField)
          }
          if (typeof (this.intelligence.meditation as any).setInterFieldBridge === 'function') {
            (this.intelligence.meditation as any).setInterFieldBridge(interFieldBridge)
          }
          this.logger.info('Meditation Self-Model Field and bridge wired')
        }

        this.logger.info('Self-Model Field initialized with InterFieldBridge')

        // Run ingestion from GitNexus in background (non-blocking)
        const repoRoot = process.cwd()
        setImmediate(async () => {
          try {
            const { SelfModelIngestor } = await import('./intelligence/mnemic-field/self-model/ingestor.js')
            const ingestor = new SelfModelIngestor(selfModelField, this.logger, repoRoot, interFieldBridge)
            const result = await ingestor.ingest({
              minCommunitySize: 5,
              weaknessThreshold: 0.6,
              updateExisting: true,
            })
            this.logger.info('Self-Model ingestion complete', {
              modules: result.modulesCreated,
              modulesUpdated: result.modulesUpdated,
              capabilities: result.capabilitiesCreated,
              weaknesses: result.weaknessesCreated,
              synapses: result.dependencySynapsesCreated,
              portals: result.portalsCreated,
              durationMs: result.durationMs,
            })

            const seeded = interFieldBridge.seedEpisodicLinks()
            if (seeded > 0) {
              this.logger.info('Seeded episodic portal links', { count: seeded })
            }
          } catch (err) {
            this.logger.warn('Self-Model ingestion failed (GitNexus may not be indexed)', { error: String(err) })
          }
        })
      } catch (err) {
        this.logger.warn('Self-Model Field not available', { error: String(err) })
      }

      // Initialize Knowledge Field — a third Mnemic Field for external research
      // and technique knowledge. Implements ModelKnowledgeProvider so Aurora's
      // Claustrum can seed from it directly.
      try {
        const { KnowledgeField } = await import('./intelligence/mnemic-field/knowledge/knowledge-field.js')
        const knowledgeField = new KnowledgeField(this.logger)

        ;(this as any).__knowledgeField = knowledgeField
        ;(this.intelligence as any).__knowledgeField = knowledgeField

        this.logger.info('Knowledge Field initialized')

        // Background ingestion from data/papers/ if directory exists
        const dataDir = (await import('./utils/paths.js')).getDataDir()
        const papersDir = path.join(dataDir, 'papers')
        if (fs.existsSync(papersDir)) {
          setImmediate(async () => {
            try {
              const { KnowledgeIngestor } = await import('./intelligence/mnemic-field/knowledge/ingestor.js')
              const ingestor = new KnowledgeIngestor(knowledgeField, this.logger)
              const result = await ingestor.ingestFromDirectory(papersDir, {
                skipExisting: true,
                createSynapses: true,
              })
              this.logger.info('Knowledge ingestion complete', {
                papers: result.papersCreated,
                techniques: result.techniquesCreated,
                synapses: result.synapsesCreated,
                durationMs: result.durationMs,
              })
            } catch (err) {
              this.logger.warn('Knowledge ingestion failed', { error: String(err) })
            }
          })
        }
      } catch (err) {
        this.logger.warn('Knowledge Field not available', { error: String(err) })
      }
    } catch (err) {
      this.logger.warn('CodeStore not available', { error: String(err) })
    }

    // Initialize FileVault (topology-aware replacement for FileArtifactStore)
    let fileVault: FileVault | undefined
    try {
      fileVault = FileVault.open(this.logger)
      ;(this as any).__fileVault = fileVault
      this.logger.info('FileVault initialized for topology-aware file storage')
    } catch (err) {
      this.logger.warn('FileVault not available', { error: String(err) })
    }

    // Initialize Constellation audit trail (bridges EventBus events to FileArtifactStore)
    if (fileArtifactStore) {
      try {
        const { createConstellationAuditTrail } = await import('./intelligence/constellation/constellation-audit-trail.js')
        const auditTrail = createConstellationAuditTrail({
          eventBus: this.bus,
          artifactStore: fileArtifactStore,
          logger: this.logger,
        })
        auditTrail.start()
        this.intelligence.constellationAuditTrail = auditTrail
        this.logger.info('Constellation audit trail started')
      } catch (err) {
        this.logger.warn('Constellation audit trail not available', { error: String(err) })
      }
    }
    const defaultProvider = this.config.get<string>('intelligence.defaultProvider', MODEL_DEFAULTS.main.provider)
    const configuredModel = this.config.get<string>('intelligence.defaultModel', MODEL_DEFAULTS.main.model)
    const defaultModel = configuredModel
      ? `${defaultProvider}/${configuredModel}`
      : getModelSpec('main')
    if (defaultModel) {
      this.logger.info(`Default model: ${defaultModel}`)
    }
    // Resolve thinking level: prefer config override, fall back to 'high'
    const configuredThinking = this.config.get<string>('intelligence.thinking', 'high') as import('../types/runtime.js').ThinkingLevel
    this.logger.info(`Thinking level: ${configuredThinking}`)
    this.sessions = createSessionManager(this.logger, systemPrompt, sessionStore, defaultModel, configuredThinking)

    // Start automatic session pruning to prevent unbounded memory growth
    this.sessions.startPruning()

    // Build command dispatcher
    this.commands = new CommandDispatcher(this.logger, this.sessions, this.bus);

    // Initialize subagent tracker FIRST (needed for tool registration)
    try {
      this.subagentTracker = createSubagentTracker({
        bus: this.bus,
        logger: this.logger.child('subagent-tracker'),
        maxTracked: 1000,
        defaultMaxAgeMs: 24 * 60 * 60 * 1000, // 24 hours
      })
      this.logger.info('subagent-tracker started')
    } catch (err) {
      this.logger.warn('failed to start subagent-tracker', { error: String(err) })
    }

    // Build tool registry + executor
    const toolRegistry = new ToolRegistry()
    ;(this as any).toolRegistry = toolRegistry

    // Initialize workflow system
    let workflowStore: WorkflowStore | undefined
    let workflowDefStore: WorkflowDefinitionStore | undefined
    try {
      this.workflowEngine = new WorkflowEngine({
        logger: this.logger.child('workflow-engine'),
        eventBus: this.bus,
      })
      this.workflowRegistry = new WorkflowRegistry(this.logger)
      workflowStore = WorkflowStore.open(this.logger)
      workflowDefStore = WorkflowDefinitionStore.open(this.logger)

      const triggerStore = WorkflowTriggerStore.open(this.logger)
      this.workflowScheduler = new WorkflowScheduler({
        engine: this.workflowEngine,
        getDefinition: (id) => this.workflowRegistry?.get(id),
        logger: this.logger,
        eventBus: this.bus,
        store: triggerStore,
      })

      this.logger.info('Workflow system initialized (engine, registry, scheduler)')
    } catch (err) {
      this.logger.warn('Workflow system initialization failed', { error: String(err) })
    }

    registerCoreTools(toolRegistry, {
      memory: this.intelligence?.memory,
      sessionManager: this.sessions,
      sessionStore: sessionStore,
      bus: this.bus,
      logger: this.logger,
      getPipeline: () => this.pipeline,
      subagentTracker: this.subagentTracker,
      cognitiveToolDeps: this.intelligence ? {
        thoughtObserver: this.intelligence.thoughtObserver,
        cognitiveBridge: this.intelligence.cognitiveBridge,
        contextManager: this.intelligence.contextManager as any,
        subconscious: this.intelligence.subconscious as any,
        logger: this.logger,
      } : undefined,
      probeDeps: this.intelligence ? {
        thoughtObserver: this.intelligence.thoughtObserver,
        cognitiveBridge: this.intelligence.cognitiveBridge,
        contextManager: this.intelligence.contextManager as any,
        subconscious: this.intelligence.subconscious as any,
        logger: this.logger,
        droneSwarm: this.intelligence.droneSwarm as any,
      } : undefined,
      autofixDeps: this.intelligence ? {
        thoughtObserver: this.intelligence.thoughtObserver,
        cognitiveBridge: this.intelligence.cognitiveBridge,
        logger: this.logger,
        droneSwarm: this.intelligence.droneSwarm as any,
        improvementOrchestrator: this.intelligence.improvementOrchestrator as any,
        projectRoot: process.cwd(),
      } : undefined,
      peerToolDeps: (this.intelligence && this.sessionDigestStore) ? {
        digestStore: this.sessionDigestStore as any,
        memory: this.intelligence.memory as any,
        cognitiveBridge: this.intelligence.cognitiveBridge,
        logger: this.logger,
      } : undefined,
      fileArtifactStore,
      collectThoughtsDeps: this.intelligence ? (() => {
        const synapseLogger = this.logger.child?.('synapse') ?? this.logger
        const firstProvider = this.providers.values().next().value
        let synapse: ReturnType<typeof createSynapse> | undefined
        if (firstProvider) {
          try {
            synapse = createSynapse({
              llm: {
                async complete(opts: { prompt: string; modelTier: string; maxTokens: number; timeoutMs: number }) {
                  const messages = [{ role: 'user' as const, content: opts.prompt }]
                  let content = ''
                  const { ActivityTimeout } = await import('./utils/activity-timeout.js')
                  const activityTimeout = new ActivityTimeout({
                    inactivityMs: opts.timeoutMs,
                    maxDurationMs: opts.timeoutMs * 3,
                    label: 'synapse-llm',
                  })
                  try {
                    for await (const chunk of ActivityTimeout.wrapIterator(
                      firstProvider.complete(messages, { model: opts.modelTier, maxTokens: opts.maxTokens }, undefined, activityTimeout.signal),
                      activityTimeout,
                    )) {
                      if (chunk.type === 'token' && chunk.text) content += chunk.text
                    }
                  } finally { activityTimeout.dispose() }
                  return { content, truncated: false }
                },
              },
              logger: synapseLogger,
            })
            synapseLogger.info('Synapse initialized for collect_thoughts (Axon)')
          } catch (err) {
            synapseLogger.warn('Synapse initialization failed', { error: String(err) })
          }
        }
        return {
          branchingManager: new BranchingConversationManager(),
          thoughtObserver: this.intelligence!.thoughtObserver,
          cognitiveBridge: this.intelligence!.cognitiveBridge,
          memory: this.intelligence!.memory,
          mnemicField: (this.intelligence as any).__mnemicField,
          bus: this.bus,
          logger: this.logger.child?.('collect-thoughts') ?? this.logger,
          synapse,
          constellationGuidanceRegistry: this.intelligence!.constellationGuidanceRegistry,
          getThinkerSession: (sessionId: string) => (this.intelligence?.thinker as any)?.getThinkerSession?.(sessionId),
        }
      })() : undefined,
      getWorkflowEngine: () => this.workflowEngine ?? null,
      getWorkflowDefinitions: () => {
        if (!this.workflowRegistry) return new Map()
        const map = new Map<string, import('../types/workflow.js').WorkflowDefinition>()
        for (const def of this.workflowRegistry.list()) map.set(def.id, def)
        return map
      },
      getWorkflowStore: () => workflowStore ?? null,
      getWorkflowDefStore: () => workflowDefStore ?? null,
    })
    const allowedPaths = this.config.get<string[]>('tools.allowedPaths', [
      join(homedir(), 'workspaces'),
      join(homedir(), '.cassicore'),
      join(homedir(), '.cassi'),
      '/tmp',
    ])
    const networkAllowlist = this.config.get<string[]>('tools.networkAllowlist', ['*'])
    // Bug 10 fix: Use process.cwd() instead of hardcoded ~/workspaces
    // This ensures tools run in the actual project directory
    const projectRoot = process.cwd()
    const toolExecutor = new ToolExecutor(toolRegistry, {
      workingDir: projectRoot,
      allowedPaths,
      networkAllowlist,
      logger: this.logger,
      _fileArtifactStore: fileArtifactStore,
      _fileVault: fileVault,
      _codeStore: codeStore,
      _globalBlackboardRegistry: this.globalBlackboardRegistry,
      _cortex: this.intelligence?.cortex,
      _memory: this.intelligence?.memory as any,
    }, this.bus)
      // Expose toolExecutor on the daemon instance so admin API and CLI can invoke tools
      ; this.toolExecutor = toolExecutor

    // Wire Permission Oracle to ToolExecutor for graduated autonomy gating
    if (this.intelligence?.permissionOracle) {
      toolExecutor.setPermissionOracle(this.intelligence.permissionOracle)
      this.logger.info('Permission Oracle wired to ToolExecutor — graduated autonomy active')
    }

    // Wire Trust Ledger to ToolExecutor for outcome feedback (learning loop)
    if (this.intelligence?.trustLedger) {
      toolExecutor.setTrustLedger(this.intelligence.trustLedger)
      this.logger.info('Trust Ledger wired to ToolExecutor — outcome learning active')
    }

    // Wire Tool Reliability Tracker for circuit breaker pattern
    const reliabilityTracker = new ToolReliabilityTracker(this.logger)
    toolExecutor.setReliabilityTracker(reliabilityTracker)
    this.logger.info('Tool Reliability Tracker wired to ToolExecutor — circuit breaker active')

    // Wire External Shell Hooks for PreToolUse/PostToolUse interception
    const hookConfig = this.config.get<{ preToolUse?: string[]; postToolUse?: string[]; timeoutMs?: number }>('tools.hooks', {})
    if (hookConfig.preToolUse?.length || hookConfig.postToolUse?.length) {
      toolExecutor.setExternalHooks({
        preToolUse: hookConfig.preToolUse ?? [],
        postToolUse: hookConfig.postToolUse ?? [],
        timeoutMs: hookConfig.timeoutMs,
      })
      this.logger.info('External Hooks wired to ToolExecutor', {
        preCount: hookConfig.preToolUse?.length ?? 0,
        postCount: hookConfig.postToolUse?.length ?? 0,
      })
    }

    this.logger.info(`Tools loaded: ${toolRegistry.list().map(t => t.name).join(', ')}`)

    // Initialize MCP registry and connect configured servers.
    // WHY: MCP servers (especially gitnexus via npx) can take 10-30s to start.
    // We must not block the boot path — the supervisor kills the daemon if it
    // doesn't become ready within 60s.  Start the registry asynchronously and
    // let servers connect in the background.  Tools registered by MCP become
    // available as each server completes its handshake.
    let mcpRegistry: MCPRegistry | undefined
    const mcpConfigs = this.config.get<Array<{ id: string; command: string; args?: string[]; env?: Record<string, string>; restartOnCrash?: boolean; maxRestarts?: number; startupTimeoutMs?: number; description?: string }>>('mcp.servers', [])
    if (mcpConfigs.length > 0) {
      this.logger.info(`Initializing MCP registry with ${mcpConfigs.length} server(s) (non-blocking)`)
      mcpRegistry = new MCPRegistry(toolRegistry, this.logger)
      // Fire-and-forget: servers connect asynchronously, tools appear as they become ready
      mcpRegistry.start(mcpConfigs).catch(err => {
        this.logger.warn('MCP registry startup error', { error: String(err) })
      })
    } else {
      this.logger.info('No MCP servers configured')
    }

    // Start Copilot SDK init early — runs in parallel with intelligence
    // registry init below. They share no mutual dependency: SDK needs
    // toolRegistry + providers (both ready), registry needs the same.
    // The SDK spawns a CLI server + auth (network I/O), while the registry
    // discovers/wires modules (CPU + dynamic imports). Parallelizing saves ~1.5s.
    const copilotSdkPromise = (async () => {
      try {
        const { initCopilotSdkProvider } = await import('./providers/index.js')
        const sdkManager = await initCopilotSdkProvider(
          providers, this.config, this.logger, this.bus,
          toolRegistry, toolExecutor,
        )
        if (sdkManager) {
          ;(this as unknown as Record<string, unknown>).__copilotSdkManager = sdkManager
          if (this.helixModelPool) {
            this.helixModelPool.setProviders(providers)
            this.logger.info('Helix ModelPool re-wired after copilot-sdk init')
          }
        }
      } catch (err) {
        this.logger.warn('Copilot SDK provider init skipped', { error: String(err) })
      }
    })()

    // This runs after all dependencies (bus, memory, providers, tools) are available.
    try {
      if (this.intelligence?.registry) {
        const registry = this.intelligence.registry

        // Discover modules from the compiled intelligence directory.
        // __dirname points to the compiled output (dist/core/), so navigate to intelligence/
        const intelligenceDir = join(path.dirname(fileURLToPath(import.meta.url)), 'intelligence')
        await registry.discover(intelligenceDir, new Set([
          'base', 'memory', 'continuity', 'recover', 'reflect', 'thinker',
          'optimizer', 'dialectic', 'ai-scientist', 'rule-enforcer',
           'subconscious', 'team-orchestrator', 'triad-team', 'embeddings', 'yang', 'yin',
          'synthesizer', 'serenity',
          // self-healer is manually instantiated in createIntelligence() — skip auto-discovery
          // to prevent a duplicate instance from appearing in intelligence.all[]
          'self-healer',
          // These modules extend BaseCognitiveModule but are manually created in
          // createIntelligence() and wired with extra dependencies (pipeline,
          // sessionManager, pluginHost, etc.) in bootIntelligencePostPipeline().
          // Auto-discovery would create a second instance lacking those dependencies.
          'heart',
          'dreamer',
          'smart-rules',
          'reflex',
          'consequence-estimator',
          'trust-ledger',
          'permission-oracle',
        ]))

        // Resolve the provider for registry modules (default to the configured fast-tier provider)
        const registryProviderId = this.config.get<string>('intelligence.defaultProvider', '') || MODEL_DEFAULTS.fast.provider
        const registryProvider = providers.get(registryProviderId) ?? providers.values().next().value

        // Wire all dependencies into discovered modules
        registry.wire({
          eventBus: this.bus,
          memory: this.intelligence.memory as any,
          provider: registryProvider,
          config: this.config,
          toolRegistry,
          toolExecutor,
        })

        // The MacroDialecticOrchestrator needs multi-provider resolution and
        // access to the dialectic system for micro-dialectic nesting.
        const macroDialectic = registry.get('macro-dialectic')
        if (macroDialectic) {
          const md = macroDialectic as any

          // Provider resolver — maps providerId → IProvider for Yang/Yin/Unity
          if (typeof md.setProviderResolver === 'function') {
            md.setProviderResolver((providerId: string) => providers.get(providerId))
          }

          // Tool executor for Unity to execute tools on behalf of thinkers
          if (typeof md.setToolExecutor === 'function') {
            md.setToolExecutor(toolExecutor)
          }

          // Dialectic system for micro-dialectic nesting within thinker sessions
          if (typeof md.setDialecticSystem === 'function') {
            md.setDialecticSystem(this.intelligence.dialectic)
          }

          this.logger.info('Macro-dialectic custom wiring complete')
        }

        // This gives every BaseCognitiveModule access to centralized model routing.
        if (this.modelDirective) {
          const resolveProvider = (id: string) => providers.get(id)
          for (const mod of registry.getAll()) {
            if (typeof (mod as any)?.setModelDirective === 'function') {
              (mod as any).setModelDirective(this.modelDirective)
            }
            if (typeof (mod as any)?.setProviderResolver === 'function') {
              (mod as any).setProviderResolver(resolveProvider)
            }
          }
          this.logger.info('ModelDirective wired to intelligence modules')
        }

        // Initialize and start all discovered modules
        await registry.initAll()
        await registry.startAll()

        if (this.intelligence?.droneSwarm) {
          this.intelligence.droneSwarm.setToolRegistry?.(toolRegistry)
          this.intelligence.droneSwarm.setToolExecutor?.(toolExecutor)
        }

        // REMOVED: Triad Team and Flux Team orchestrator wiring — deprecated systems deleted.
        // All orchestration now uses Helix and Constellation, which are wired separately.

        // Wire Helix tools, store, and context distiller
        if (this.intelligence?.helix) {
          try {
            this.intelligence.helix.setToolRegistry(toolRegistry)
            this.intelligence.helix.setToolExecutor(toolExecutor)

            // Wire HelixStore for Helix session persistence (dedicated helix.db)
            try {
              const { HelixStore } = await import('./intelligence/helix/helix-store.js')
              const helixStore = HelixStore.open(this.logger.child('helix-store'))
              // WHY: Clean up helix sessions left in 'running' state from a previous daemon crash.
              // Without this, orphaned helix sessions stay in 'running' forever.
              const helixRecovered = helixStore.recoverOrphanedSessions()
              if (helixRecovered > 0) {
                this.logger.info('Recovered orphaned helix sessions at startup', { count: helixRecovered })
              }
              this.intelligence.helix.setStore(helixStore)
              this.logger.info('HelixStore wired (SQLite persistence)')
            } catch (storeErr) {
              this.logger.warn('HelixStore failed to initialize — running without persistence', {
                error: String(storeErr),
              })
            }

            // Wire ContextDistiller for Phase Zero context injection
            if (this.contextDistiller) {
              this.intelligence.helix.setContextDistiller(this.contextDistiller)
              this.logger.info('Helix ContextDistiller wired for Phase Zero')
            }

            this.logger.info('Helix tool access wired')
          } catch (helixErr) {
            this.logger.warn('Failed to wire Helix tools — Helix will not be available', {
              error: String(helixErr),
            })
          }
        }

        // Wire Constellation tools, store, and context distiller
        if (this.intelligence?.constellation) {
          try {
            this.intelligence.constellation.setToolRegistry(toolRegistry)
            this.intelligence.constellation.setToolExecutor(toolExecutor)

            // Wire HelixStore for Constellation session persistence (reuses helix.db)
            try {
              const { HelixStore } = await import('./intelligence/helix/helix-store.js')
              const helixStore = HelixStore.open(this.logger.child('helix-store'))
              this.intelligence.constellation.setStore(helixStore)
            } catch (storeErr) {
              this.logger.warn('Constellation HelixStore failed to initialize', { error: String(storeErr) })
            }

            // Wire ConstellationStore for persistent Corpus tree, branch assessments, and reports
            try {
              const { ConstellationStore } = await import('./intelligence/constellation/constellation-store.js')
              const constellationStore = ConstellationStore.open(this.logger.child('constellation-store'))
              // Recover any sessions left in 'running' state from a previous daemon crash.
              // Sessions with checkpoint data are marked 'interrupted' (resumable);
              // sessions without are marked 'failed'.
              const recovered = constellationStore.recoverOrphanedSessions()
              if (recovered.interrupted > 0 || recovered.failed > 0) {
                this.logger.info('Recovered orphaned constellation sessions at startup', {
                  interrupted: recovered.interrupted,
                  failed: recovered.failed,
                })
              }
              this.intelligence.constellation.setConstellationStore(constellationStore)

              // WHY: Auto-resume interrupted constellations after all wiring is complete.
              // This runs after setConstellationStore so the orchestrator has access to the store.
              // Fire-and-forget: resume failures are logged but don't block boot.
              if (recovered.interrupted > 0) {
                const interrupted = constellationStore.listSessions({ status: 'interrupted' })
                for (const session of interrupted) {
                  // Defense-in-depth: skip meditation sessions even if they somehow reach 'interrupted'
                  if (session.id.startsWith('meditation-') || session.meditationMode) {
                    this.logger.info('Skipping auto-resume for meditation session', { sessionId: session.id })
                    continue
                  }
                  this.logger.info('Auto-resuming interrupted constellation', {
                    sessionId: session.id,
                    goal: session.goal.slice(0, 100),
                  })
                  this.intelligence.constellation.resumeConstellation(session.id).catch((err: unknown) => {
                    this.logger.warn('Auto-resume failed for constellation', {
                      sessionId: session.id,
                      error: String(err),
                    })
                  })
                }
              }
            } catch (storeErr) {
              this.logger.warn('ConstellationStore failed to initialize', { error: String(storeErr) })
            }

            if (this.contextDistiller) {
              this.intelligence.constellation.setContextDistiller(this.contextDistiller)
            }

            // Wire audit trail into Constellation orchestrator
            if (this.intelligence.constellationAuditTrail) {
              this.intelligence.constellation.setAuditTrail(this.intelligence.constellationAuditTrail)
            }

            // Wire Reasoning Bank into Constellation orchestrator so traces
            // are available for ingestion/retrieval during pipeline runs
            if (this.intelligence.reasoningBank) {
              this.intelligence.constellation.setReasoningBank(this.intelligence.reasoningBank)
            }

            this.logger.info('Constellation tool access wired')
          } catch (constErr) {
            this.logger.warn('Failed to wire Constellation tools', { error: String(constErr) })
          }
        }

        // Wire Meditation controller tool deps (SoloRunner needs direct tool access)
        if (this.intelligence?.meditation) {
          try {
            const med = this.intelligence.meditation as { setToolRegistry?: (r: typeof toolRegistry) => void; setToolExecutor?: (e: typeof toolExecutor) => void }
            if (typeof med.setToolRegistry === 'function') med.setToolRegistry(toolRegistry)
            if (typeof med.setToolExecutor === 'function') med.setToolExecutor(toolExecutor)
            this.logger.info('Meditation controller tool access wired')
          } catch (medErr) {
            this.logger.warn('Failed to wire Meditation tools', { error: String(medErr) })
          }
        }

        // Wire Training Warehouse tagger adapter.
        // Uses the background tier (gpt-4o) for batch tagging operations since
        // it is unlimited and tagging is non-interactive background work.
        if (this.intelligence?.training) {
          try {
            const taggerProviderId = 'github-copilot'
            const taggerModel = 'gpt-4o'
            const taggerProvider = providers.get(taggerProviderId) ?? providers.values().next().value
            if (taggerProvider) {
              this.intelligence.tagger = {
                model: taggerModel,
                provider: taggerProviderId,
                complete: async (system: string, user: string) => {
                  const messages = [
                    { role: 'system' as const, content: system },
                    { role: 'user' as const, content: user },
                  ]
                  let text = ''
                  let tokensUsed = 0
                  for await (const chunk of taggerProvider.complete(messages, { model: taggerModel, stream: true })) {
                    if (chunk.type === 'token' && chunk.text) text += chunk.text
                    if (chunk.type === 'done' && chunk.tokensUsed) tokensUsed = chunk.tokensUsed
                  }
                  return { text, tokensUsed }
                },
              }
              this.logger.info('Training tagger adapter wired', { provider: taggerProviderId, model: taggerModel })
            }
          } catch (err) {
            this.logger.warn('Failed to wire training tagger adapter', { error: String(err) })
          }
        }

        // Wire CorpusLLM adapter for Constellation Corpus strategic analysis.
        // Uses ModelPool 'unity' slot (qwenPlus tier) for high-capability synthesis.
        if (this.intelligence?.setCorpusLLMProvider && this.helixModelPool) {
          try {
            const corpusHandle = await this.helixModelPool.acquire('unity', undefined, 'corpus-llm')
            this.intelligence.setCorpusLLMProvider(corpusHandle)
            this.logger.info('CorpusLLM handle wired', { provider: corpusHandle.provider, model: corpusHandle.model })
          } catch (err) {
            this.logger.warn('Failed to wire CorpusLLM handle', { error: String(err) })
          }
        }

        // Wire BrainstemLLM adapter for Helix per-branch annotation.
        // Uses ModelPool 'mini-helix:brainstem' slot (haiku with gpt-5-mini fallback).
        if (this.intelligence?.setBrainstemLLMProvider && this.helixModelPool) {
          try {
            const bsHandle = await this.helixModelPool.acquire('mini-helix:brainstem', undefined, 'brainstem-llm')
            this.intelligence.setBrainstemLLMProvider(bsHandle)
            this.logger.info('BrainstemLLM handle wired', { provider: bsHandle.provider, model: bsHandle.model })
          } catch (err) {
            this.logger.warn('Failed to wire BrainstemLLM handle', { error: String(err) })
          }
        }

        // Merge auto-discovered modules into the existing all[] array
        const registryModules = registry.getAllAsIntelligenceModules()
        if (registryModules.length > 0) {
          this.intelligence.all.push(...registryModules)
          this.intelligence.all.sort((a, b) => b.priority - a.priority)
          this.logger.info(`Registry: ${registryModules.length} module(s) discovered and started`, {
            modules: registryModules.map(m => `${m.name}(${m.priority})`),
          })
        }
      }
    } catch (err) {
      this.logger.warn('IntelligenceRegistry initialization failed — auto-discovered modules will not be available', { error: String(err) })
    }

    // Wait for Copilot SDK init that was started in parallel with intelligence registry
    await copilotSdkPromise

    this.pipeline = new TurnPipeline(
      providers, this.sessions, this.bus, this.logger,
      this.intelligence?.memory ?? undefined,
      this.orchestration,
      toolRegistry,
      toolExecutor,
    )

    // Initialize context window debugger
    try {
      const ctxDebugEnabled = this.config.get<boolean>('debug.contextWindow.enabled', true)
      if (ctxDebugEnabled) {
        const ctxDebugger = initContextWindowDebugger(this.bus as any)
        setContextWindowDebugger(ctxDebugger)
        // Mount the debug middleware early in the pipeline
        this.pipeline.prependMiddleware(contextWindowDebugMiddleware)
        this.logger.info('Context window debugging enabled')
      }
    } catch (err) {
      this.logger.warn('Failed to initialize context window debugger', { error: String(err) })
    }

    // Wire dialectic system to pipeline for parallel processing
    if (this.intelligence?.dialectic) {
      this.pipeline.setDialectic(this.intelligence.dialectic)
    }

    // Wire macro-dialectic middleware to pipeline — Unity becomes the user-facing response.
    // HOW: intercepts turns before provider middleware, runs Yang + Yin + Unity, streams Unity's output
    if (this.intelligence?.registry) {
      const md = this.intelligence.registry.get('macro-dialectic')
      if (md && typeof (md as any).createMiddleware === 'function') {
        this.pipeline.prependMiddleware((md as any).createMiddleware())
        this.logger.info('Macro-dialectic middleware wired to pipeline (Unity-as-response)')
      }
    }

    // Bridge daemon.bus events → CassiCoreEventBus session buffers
    // so /events/history and verification tools can query pipeline events.
    // WHY: The CassiCoreEventBus IS the same singleton as this.bus (core/event-bus.ts).
    // A previous bridge here re-emitted every event from onAll → cassiCoreBus.emit()
    // which caused infinite recursion (stack overflow). No bridge is needed since
    // they are the same instance.
    try {
      const { getEventBus: getCassiCoreEventBus } = await import('./events/index.js')
      const cassiCoreBus = getCassiCoreEventBus()
      if (cassiCoreBus === bus) {
        this.logger.info('Event bridge: skipped — CassiCoreEventBus is the same singleton as daemon.bus')
      } else {
        // Only bridge if they are genuinely different instances
        this.bus.onAll((event: any) => {
          if (event?.type && event?.sessionId) {
            cassiCoreBus.emit({
              ...event,
              timestamp: event.timestamp instanceof Date ? event.timestamp.getTime() : (event.timestamp ?? Date.now()),
            })
          }
        })
        this.logger.info('Event bridge: daemon.bus → CassiCoreEventBus wired')
      }
    } catch (err) {
      this.logger.warn('Failed to wire event bridge', { error: String(err) })
    }

    // Wire subconscious system to pipeline for automatic context retrieval
    if (this.intelligence?.subconscious) {
      this.pipeline.setSubconscious(this.intelligence.subconscious)
    }

    // REMOVED: IntelligentContextWindow via archivist.sessionIndexer — MemoryModule deleted.
    // Context window uses default trim. Reimplementation with MnemicField in Phase 5.

    completePhase('pipeline-tools', {
      tools: toolRegistry.list().length,
      mcpServers: mcpConfigs.length,
      contextWindow: !!this.contextWindow,
    })

    // Wire SessionDigestStore for cross-session awareness
    try {
      this.sessionDigestStore = createSessionDigestStore(this.logger.child('session-digest'))
      // Wire digest store into pipeline (injection #5) and subconscious (digest population)
      this.pipeline.setDigestStore(this.sessionDigestStore)
      if (this.intelligence?.subconscious) {
        ;(this.intelligence.subconscious as any).setDigestStore?.(this.sessionDigestStore)
      }
      // Wire EventBus into SessionManager so it can emit session:created
      this.sessions.setBus(this.bus)
      // Auto-clear event bus session history when sessions end (prevents memory leak)
      this.bus.wireSessionCleanup?.()
      // Seed digests for any sessions already in memory
      this.bus.on('session:created' as any, (e: any) => {
        if (e?.sessionId && this.sessionDigestStore) {
          this.sessionDigestStore.upsert(e.sessionId, {
            channelId: e.channelId ?? '',
            senderId:  e.senderId  ?? '',
          })
        }
      })
      this.logger.info('SessionDigestStore initialized and wired')
    } catch (err) {
      this.logger.warn(`Failed to initialize SessionDigestStore: ${String(err)}`)
    }

    this.autonomousLoop = await bootIntelligencePostPipeline({
      bus: this.bus,
      config: this.config,
      logger: this.logger,
      intelligence: this.intelligence,
      pipeline: this.pipeline,
      sessionPipeline: this.sessionPipeline,
      sessions: this.sessions,
      sessionStore,
      sessionDigestStore: this.sessionDigestStore,
      toolRegistry,
      toolExecutor,
      pluginHost: this.pluginHost,
      compactionProvider:
        providers.get('github-copilot/gpt-5-mini')
        ?? providers.get('swift')
        ?? providers.get('qwen')
        ?? providers.get('alibaba')
        ?? Array.from(providers.values())[0],
      contextDistiller: this.contextDistiller,
      handleFactory: this.helixModelPool
        ? (config: { tier: string; purpose: string; sessionId: string }) =>
          this.helixModelPool!.acquire('unity', config.tier, config.sessionId)
        : undefined,
    })

    // Register workflow templates now that intelligence modules are wired
    if (this.workflowRegistry && this.intelligence) {
      try {
        const { createHelixRunnerAdapter, createConstellationAdapter, createToolExecutorAdapter } = await import('./workflow/adapters.js')
        const { codeReviewPipeline, researchPipeline, featureImplementation, scheduledCleanup, eventReactorChain } = await import('./workflow/templates.js')
        const { helixStep, createStep } = await import('./workflow/index.js')

        const helixRunner = createHelixRunnerAdapter(() => this.intelligence?.helix)
        const constellationOrch = createConstellationAdapter(() => this.intelligence?.constellation)
        const wfToolExecutor = createToolExecutorAdapter(() => this.toolExecutor)

        this.workflowRegistry.register(codeReviewPipeline({ runner: helixRunner }))
        this.workflowRegistry.register(researchPipeline({
          runner: helixRunner,
          angles: [
            { name: 'code', goal: 'Investigate the codebase for relevant patterns, implementations, and architecture' },
            { name: 'context', goal: 'Gather broader context: documentation, conventions, and related systems' },
          ],
        }))
        this.workflowRegistry.register(featureImplementation({ runner: helixRunner }))
        this.workflowRegistry.register(scheduledCleanup({
          executor: wfToolExecutor,
          sessionId: 'workflow:cleanup',
          tasks: [
            { name: 'prune-sessions', tool: 'bash', args: { command: 'echo "session pruning handled by SessionManager"' } },
          ],
        }))

        this.workflowRegistry.register(eventReactorChain({
          id: 'system-event-reactor',
          routes: [
            {
              name: 'workflow-failure',
              match: (input: unknown) => {
                const evt = input as Record<string, unknown>
                return evt?.type === 'workflow:run:failed' || evt?.type === 'workflow:step:failed'
              },
              handler: helixStep({
                id: 'analyze-failure',
                goal: (input: unknown) => {
                  const evt = input as Record<string, unknown>
                  return `Analyze this workflow failure and suggest fixes: ${JSON.stringify(evt)}`
                },
                runner: helixRunner,
              }),
            },
            {
              name: 'health-degraded',
              match: (input: unknown) => {
                const evt = input as Record<string, unknown>
                return evt?.type === 'health:degraded' || evt?.type === 'provider:error'
              },
              handler: helixStep({
                id: 'diagnose-health',
                goal: (input: unknown) => {
                  const evt = input as Record<string, unknown>
                  return `Diagnose this system health issue and recommend recovery steps: ${JSON.stringify(evt)}`
                },
                runner: helixRunner,
              }),
            },
          ],
          fallback: createStep({
            id: 'log-unhandled',
            description: 'Log unhandled events',
            execute: async (ctx) => {
              this.logger.info('Event reactor: unhandled event', { event: ctx.input })
              return { handled: false, event: ctx.input }
            },
          }),
        }))

        this.logger.info(`Workflow templates registered: ${this.workflowRegistry.size} definitions`)
      } catch (err) {
        this.logger.warn('Failed to register workflow templates', { error: String(err) })
      }
    }

    try {
      const { SessionPipeline } = await import('./pipeline/adapter/SessionPipeline.js')
      const v2Options = {
        config: this.config,
        logger: this.logger,
        providers,
        toolExecutor: {
          execute: async (name: string, input: unknown, context: unknown) => {
            const result = await (this as any).toolExecutor.execute(name, input, context)
            return { content: result.content, isError: result.isError }
          },
          isAvailable: (name: string) => (this as any).toolExecutor.isAvailable(name)
        },
        // HOW: Pass a getter function so the LLM always sees the latest tools
        // (tools can be registered after init by MCP, teams, etc.)
        toolSchemas: () => toolRegistry.toAnthropicSchema(),
        intelligence: {
          memory: (this as any).intelligence?.memory,
          dialectic: (this as any).intelligence?.dialectic,
          thinker: (this as any).intelligence?.thinker,
          subconscious: (this as any).intelligence?.subconscious,
          locusBridge: (this as any).intelligence?.locusBridge,
          thalamus: (this as any).intelligence?.registry?.get('thalamus'),
        },
        eventBus: this.bus,
        // REMOVED: injectionAggregator — deprecated. Now uses Thalamus/GlobalWorkspace.
      }
      const pipeline = new SessionPipeline(v2Options as any)
      await pipeline.initialize()
      this.sessionPipeline = pipeline
      this.logger.info('Session pipeline initialized')

      // Wire GlobalWorkspace into session pipeline for GWT-based injection
      if (this.intelligence?.globalWorkspace) {
        const useGwt = this.config.get<boolean>('intelligence.workspace.enabled', false)
        pipeline.setGlobalWorkspace(this.intelligence.globalWorkspace, useGwt)
        this.logger.info('GlobalWorkspace wired to session pipeline', { enabled: useGwt })
      }

      // Phase 4: Bootstrap cassi:primary conductor session so turn:token routing works
      if (this.primaryRouter) {
        try {
          this.sessions.getOrCreateById(
            this.primaryRouter.primarySessionId,
            'channel:system',  // home channel — responses fan out to original channels
            this.primaryRouter.primarySessionId,
            { projectPath: process.cwd() } as any,
          )
          this.logger.info(`[primary-router] Conductor session registered: ${this.primaryRouter.primarySessionId}`)
        } catch (err) {
          this.logger.warn(`[primary-router] Failed to register conductor session: ${String(err)}`)
        }
      }

      if (this.autonomousLoop) {
        const { createExecutionBackend } = await import('./intelligence/execution-backends/index.js')
        const backend = createExecutionBackend('cassicore', this.logger.child('execution-backend'), {
          pipeline: this.pipeline,
          sessionPipeline: this.sessionPipeline,
        })
        this.autonomousLoop.setBackend(backend)
        this.logger.info('Autonomous loop switched to session pipeline backend')
      }
    } catch (err) {
      this.logger.warn('Failed to initialize session pipeline', { error: String(err) })
    }

    const healthIntervalMs = this.config.get<number>('health.intervalMs', 30_000)
    this.healthMonitor = new HealthMonitor(this.bus, this.logger, {
      intervalMs: healthIntervalMs,
      historySize: 20,
      selfHeal: true,
    })
    this.healthMonitor.wire({
      providers,
      pluginHost: this.pluginHost,
      intelligence: this.intelligence,
      pipeline: this.pipeline,
      sessions: this.sessions,
      mcp: mcpRegistry,
      eventBus: this.bus,
    })

    // 7. Subscribe to worker:message
    interface WorkerMessageEvent {
      pluginId: string
      payload: Record<string, unknown>
    }
    this.bus.on("worker:message", async (e) => {
      const event = e as WorkerMessageEvent
      // log any message received from workers
      this.logger.debug(`[worker:${event.pluginId}]`, { payload: event.payload })

      try {
        const pluginId = event.pluginId
        const payload = event.payload

        // pluginId is "session:<sessionId>" for events emitted by the pipeline.
        // Route streaming tokens and status events to the channel worker that
        // owns the session.
        if (pluginId?.startsWith("session:") && payload?.sessionId) {
          try {
            const sid = payload.sessionId as string
            const s = this.sessions.get(sid)
            // HOW: Determine the target channel. For sessions created via the
            // primary router (e.g. tg:1339199309 → cassi:primary), the session
            // won't be found under the original ID. Fall back to the primary
            // router's tracked source or the cassi:primary session.
            let tgt = s?.channelId
            let effectiveSid = sid
            if (!tgt) {
              const routerSrc = this.primaryRouter?.getSource()
              if (routerSrc && routerSrc.sessionId === sid) {
                tgt = routerSrc.channelId
              } else {
                // Check if the sid is a channel-specific ID (tg:*, cli:*) and look up
                // the primary session's channel
                const primarySession = this.sessions.get('cassi:primary')
                if (primarySession) {
                  tgt = primarySession.channelId
                  // But channel:system has no worker — use the pluginId hint
                  if (tgt === 'channel:system') {
                    // Extract channel from the session ID prefix
                    if (sid.startsWith('tg:')) tgt = 'channel:telegram'
                    else if (sid.startsWith('cli:')) tgt = 'channel:cli'
                    else if (sid.startsWith('oc:')) tgt = 'channel:opencode'
                  }
                }
              }
            }
            if (tgt) {
              if (payload.type === 'turn:direct_message' && payload.content) {
                // Command dispatcher response — send once and done
                this.pluginHost.send(tgt, { sessionId: sid, content: payload.content as string, done: true })
                return
              } else if (payload.type === 'turn:token' && payload.token) {
                // Stream token to channel — done=false keeps stream open
                this.pluginHost.send(tgt, { sessionId: sid, content: payload.token as string, done: false })
                // Fan out streaming token to original channel if routed via primary conductor
                const routerSrc = this.primaryRouter?.getSource()
                if (routerSrc) {
                  this.pluginHost.send(routerSrc.channelId, { sessionId: routerSrc.sessionId, content: payload.token as string, done: false })
                }
                return
              } else if (payload.type === 'turn:thinking' && payload.token) {
                // Thinking tokens are processed by subconscious but not displayed in CLI
                // to avoid garbled output. Use SSE streaming endpoint (/chat/:id/stream)
                // if you need to capture thinking events separately.
                return
              } else if (payload.type === 'turn:tool_call') {
                // Show tool usage inline — italicised name, no done flag
                const toolName = (payload.tool as string) || 'tool'
                this.pluginHost.send(tgt, { sessionId: sid, content: `\n_[${toolName}]_`, done: false })
                return
              } else if (payload.type === 'turn:error') {
                this.pluginHost.send(tgt, { sessionId: sid, content: `❌ ${payload.error as string}`, done: true })
                return
              }
            }
          } catch (err) {
            this.logger.warn(`failed to forward session message: ${String(err)}`)
          }
        }

        if (payload?.type === 'log') {
          const level = (payload.level as string) || 'info'
          const msg = (payload.message as string) || ''
          if (level === 'error') this.logger.error(msg)
          else if (level === 'warn') this.logger.warn(msg)
          else this.logger.info(msg)
          return
        }

        // The OpenCode channel worker polls reasoning blocks from the LLM's
        // thinking stream (stored in OpenCode's SQLite DB) and forwards them
        // here as { type: 'reasoning', payload: { sessionId, text } }.
        //
        // We re-emit these as turn:thinking events on the bus so that the
        // ThoughtObserver picks them up and extracts cognitive signals.
        // This bridges the external agent's thinking into the cognitive
        // drone network — fully automatic, zero agent effort.
        if (payload?.type === 'reasoning' && payload?.sessionId && payload?.text) {
          const sid = payload.sessionId as string
          const text = payload.text as string

          // Ensure the session exists with projectPath for auto-linking
          // OpenCode sessions use oc:* IDs and we set projectPath to cwd
          // so they auto-link with other sessions on the same project.
          if (this.sessions) {
            const existing = this.sessions.get(sid)
            if (!existing) {
              const s = this.sessions.getOrCreateById(sid, 'channel:opencode', sid, { projectPath: process.cwd() } as any)
              if (s && !(s as any).projectPath) (s as any).projectPath = process.cwd()
            } else if (!(existing as any).projectPath) {
              (existing as any).projectPath = process.cwd()
            }
          }

          // Emit as turn:thinking so ThoughtObserver picks it up
          this.bus.emit({
            type: 'worker:message',
            pluginId: `session:${sid}`,
            payload: {
              type: 'turn:thinking',
              sessionId: sid,
              token: text,
            },
          } as any)

          const extractedSignals = this.intelligence?.thoughtObserver?.extractSignalsFromText?.(text) ?? []
          await this.intelligence?.thoughtObserver?.storeSignals?.(sid, extractedSignals)

          this.logger.debug(`External reasoning captured`, {
            sessionId: sid.slice(0, 12),
            length: text.length,
            model: (payload.model as string) ?? '(unknown)',
          })
          return
        }

        // OpenCode channel worker forwards tool usage events from the external
        // agent's SSE stream. We emit these as channel:tool_update events so
        // they land in EventHistory and can be used for parent session
        // auto-detection in Phase Zero (context distiller).
        if (payload?.type === 'tool_update' && payload?.sessionId && payload?.toolName) {
          const sid = payload.sessionId as string
          const toolName = payload.toolName as string
          const status = (payload.status as string) ?? 'unknown'
          const partData = payload.partData as Record<string, unknown> | undefined

          this.bus.emit({
            type: 'channel:tool_update',
            sessionId: sid,
            toolName,
            status,
            partData,
            timestamp: new Date(),
          })

          this.logger.debug('Channel tool event captured', {
            sessionId: sid.slice(0, 12),
            toolName,
            status,
          })
          return
        }

        // Channel workers send { sessionId, content } when a user message arrives.
        // The pipeline processes it; streaming tokens are handled above via bus
        // events. The final done=true is sent below via the turn:end subscription.
        if (pluginId?.startsWith("channel:") && payload?.sessionId && (payload?.content || payload?.attachments) && payload?.sessionId !== "system") {
          const sid = payload.sessionId as string;
          const content = payload.content as string;

          // INTERCEPT COMMANDS FIRST
          if (content && content.startsWith('/')) {
            const handled = await this.commands.handle(sid, pluginId, content);
            if (handled) return;
          }

          // Primary conductor session: re-route ALL channel messages to cassi:primary
          // WHY: Capture original session ID before rewrite so the response can be
          // sent back with the correct ID (e.g. tg:1339199309 instead of cassi:primary)
          let originalSessionId: string | undefined
          if (
            this.primaryRouter &&
            !this.primaryRouter.isPrimary(sid) &&
            pluginId?.startsWith('channel:') &&
            pluginId !== 'channel:module' &&
            !payload.type  // skip structured events (reasoning, tool_update, etc.)
          ) {
            originalSessionId = sid
            this.primaryRouter.trackTurn(sid, pluginId)
            payload.sessionId = this.primaryRouter.primarySessionId
            this.logger.debug('[primary-router] Re-routing to conductor session', {
              from: sid, channel: pluginId, to: this.primaryRouter.primarySessionId,
            })
          }

          // When the OpenCode channel captures a completed turn (user message +
          // assistant response pair), we skip the SessionPipeline's LLM call
          // and go straight to intelligence modules. OpenCode already handled
          // the conversation — CassiCore just needs the context.
          if (payload.type === 'response-complete') {
            const userMessage = content || '(context)'
            const assistantResponse = (payload.assistantResponse as string) || ''
            const model = payload.model as string | undefined

            // Ensure session exists
            const session = this.sessions.getOrCreateById(
              sid, pluginId, sid, { projectPath: process.cwd() } as any
            )

            this.logger.info(`Processing captured OpenCode turn`, {
              sessionId: sid,
              userLen: userMessage.length,
              responseLen: assistantResponse.length,
              model: model ?? '(unknown)',
            })

            // Emit turn:start — triggers feedback detection, thinker, etc.
            this.bus.emit({
              type: 'turn:start' as any,
              sessionId: sid,
              message: userMessage,
              timestamp: new Date()
            } as any)

            // Add to session history (user + assistant)
            // The pipeline's SessionManager uses SHA256-hashed IDs, so we must
            // getOrCreate first (which generates the correct ID), then addTurn
            // with that ID — not the raw OpenCode session ID.
            try {
              const sm = this.sessionPipeline?.getSessionManager()
              if (sm) {
                const pipelineSession = await sm.getOrCreate(pluginId, sid)
                await sm.addTurn(pipelineSession.id, userMessage, assistantResponse, { tokensUsed: 0 })
              }
            } catch (err) {
              this.logger.warn(`Failed to persist captured turn: ${String(err)}`, { sessionId: sid })
            }

            // Submit workspace signals from the captured turn so the GWT
            // workspace has content for broadcast and the RadianceLoop can
            // observe module responses to external agent activity.
            if (this.intelligence?.globalWorkspace) {
              try {
                const ws = this.intelligence.globalWorkspace
                ws.submit({
                  signalId: `ext-user-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                  source: pluginId,
                  sessionId: sid,
                  type: 'observation' as const,
                  content: userMessage.slice(0, 500),
                  luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, cognitiveResonance: 0, strategicImportance: 0, composite: 0 },
                  createdAt: Date.now(),
                })
                if (assistantResponse) {
                  ws.submit({
                    signalId: `ext-response-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                    source: `${pluginId}:response`,
                    sessionId: sid,
                    type: 'context' as const,
                    content: assistantResponse.slice(0, 500),
                    luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, cognitiveResonance: 0, strategicImportance: 0, composite: 0 },
                    createdAt: Date.now(),
                  })
                }

                // Enrich workspace with memory-derived signals (Mnemic Field).
                // Same pattern as the Claude Code hook server's workspaceEnrich call,
                // but inline to avoid HTTP round-trip.
                try {
                  const mnemicField = (this.intelligence as any).__mnemicField
                  if (mnemicField?.retrieve) {
                    const hits = mnemicField.retrieve(userMessage, { limit: 3 })
                    for (const hit of hits) {
                      if (!hit.content || hit.content.length < 10) continue
                      ws.submit({
                        signalId: `ext-memory-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                        source: 'mnemic-field',
                        sessionId: sid,
                        type: 'memory' as const,
                        content: hit.content.slice(0, 400),
                        luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, cognitiveResonance: 0, strategicImportance: 0, composite: 0 },
                        createdAt: Date.now(),
                        metadata: { engram: hit.id, score: hit.score },
                      })
                    }
                  }
                } catch { /* non-critical — enrichment is supplementary */ }

                ws.broadcast()
                ws.tick()
              } catch { /* non-critical */ }
            }

            // Emit turn:end — triggers archivist, thinker end, streaming finalization
            this.bus.emit({
              type: 'turn:end' as any,
              sessionId: sid,
              response: assistantResponse,
              durationMs: 0,
              timestamp: new Date()
            } as any)

            // Trigger intelligence modules directly — NO LLM CALL
            try {
              const il = (this.sessionPipeline as any)?.getIntelligenceLayer?.()
              if (il) {
                // Map runtime Message[] → pipeline Message[] (add required timestamp)
                const now = Date.now()
                const pipelineHistory = (session.history || []).map((m, i) => ({
                  role: m.role,
                  content: m.content,
                  timestamp: now - (session.history.length - i) * 1000,
                }))
                il.process(sid, {
                  userMessage,
                  assistantResponse,
                  toolCalls: [],
                  sessionHistory: pipelineHistory as any,
                  availableTools: [],
                  timestamp: now,
                })
              }
            } catch (err) {
              this.logger.warn(`Intelligence processing failed for captured turn: ${String(err)}`, { sessionId: sid })
            }

            // Auto-index the captured turn for FTS scoring
            // This keeps the SessionIndexer fresh so /context/score returns
            // meaningful results even between explicit /context/index calls.
            try {
              const indexer = (this.intelligence as any)?.memory?.sessionIndexer
              if (indexer?.indexIncremental) {
                const history = session.history || []
                // Index from the second-to-last message (the new user + assistant pair)
                const fromIdx = Math.max(0, history.length - 2)
                indexer.indexIncremental(sid, history, fromIdx)
              }
            } catch (err) {
              this.logger.debug?.(`Auto-index of captured turn failed (non-fatal): ${String(err)}`, { sessionId: sid })
            }

            return // Done — no SessionPipeline.processMessage()
          }

          // SIGNAL HANDLING
          if (payload.type === 'signal') {
            this.bus.emit({
              type: 'dialectic:signal',
              sessionId: sid,
              signalType: (payload.signalType as string) || 'feedback',
              content: content,
              confidence: 1.0,
            } as any);
          }

          const { generateShortId } = await import('./utils/ids.js')
          const inbound = {
            id: generateShortId(8),
            sessionId: payload.sessionId as string,
            channelId: pluginId,
            senderId: payload.sessionId as string,
            content: (payload.content as string) || '(image)',
            attachments: payload.attachments as import('../types/runtime.js').ImageAttachment[] | undefined,
            timestamp: new Date(),
          }

          // Update session model if provided (for CLI channel with model arg)
          const modelFromPayload = payload.model as string | undefined
          const providerFromPayload = typeof modelFromPayload === 'string'
            ? modelFromPayload.split('/')[0] || undefined
            : undefined
          if (modelFromPayload && pluginId === 'channel:cli') {
            const session = this.sessions.get(inbound.sessionId)
            if (session) {
              session.config.model = modelFromPayload
            }
          }

          this.logger.info(`Processing inbound message`, {
            channel: pluginId,
            sessionId: inbound.sessionId,
            provider: providerFromPayload,
            model: modelFromPayload,
          })

          // Process the turn via the canonical turn router.
          try {
            if (getPreferredTurnEngine(this as any)) {
              const result = await executeTurn(this as any, {
                requestedSessionId: inbound.sessionId,
                channelId: inbound.channelId,
                senderId: inbound.senderId,
                content: inbound.content,
                attachments: inbound.attachments,
              })

              if (result.engine === 'session-pipeline') {
                this.logger.info(`Turn complete`, {
                  sessionId: result.sessionId,
                  provider: providerFromPayload,
                  model: modelFromPayload,
                  engine: result.engine,
                })
                // HOW: When primary router is active, the response must be sent with
                // the ORIGINAL session ID (e.g. tg:1339199309) — not the rewritten
                // cassi:primary — so the channel worker can route it correctly.
                // The turn:end handler may have already cleared the router source,
                // so we use the pre-captured originalSessionId.
                const effectiveSessionId = originalSessionId ?? result.sessionId
                this.pluginHost.send(pluginId, {
                  sessionId: effectiveSessionId,
                  content: result.response,
                  done: true,
                })
              } else {
                this.logger.info(`Turn complete (legacy)`, {
                  sessionId: inbound.sessionId,
                  provider: providerFromPayload,
                  model: modelFromPayload,
                  engine: result.engine,
                })
              }
            } else {
              throw new Error('pipeline not ready')
            }
          } catch (err) {
            this.logger.warn(`pipeline error: ${String(err)}`, {
              channel: pluginId,
              sessionId: inbound.sessionId,
              provider: providerFromPayload,
              model: modelFromPayload,
            })
            // Send error message to channel
            this.pluginHost.send(pluginId, {
              sessionId: originalSessionId ?? inbound.sessionId,
              content: `Something went wrong. Please try again.`,
              done: true,
            })
          }
        }
      } catch (err) {
        this.logger.warn(`error processing inbound message: ${String(err)}`)
      }
    })

    interface SessionCompactedEvent {
      sessionId: string
      summary: string
    }
    this.bus.on("session:compacted", (e) => {
      const { sessionId } = e as SessionCompactedEvent
      const s = this.sessions.get(sessionId)
      if (s?.channelId) {
        this.pluginHost.send(s.channelId, {
          type: 'status',
          payload: { sessionId, text: 'Context compacted to focus on recent goals.', type: 'compaction' }
        })
      }
    })

    interface SessionEvent {
      sessionId: string
    }
    this.bus.on("context-manager:sync", (e) => {
      const { sessionId } = e as SessionEvent
      const s = this.sessions.get(sessionId)
      if (s?.channelId && s.channelId === 'channel:telegram') {
        // only notify Telegram for now as it's more "detached"
      }
    })

    // turn:end fires after pipeline completion. All streaming tokens already forwarded to channel worker.
    // HOW: send done=true with empty content to close stream — Telegram does final flush/edit of buffer
    this.bus.on("turn:end", (e) => {
      const sid = (e as SessionEvent).sessionId
      if (!sid) return
      try {
        const s = this.sessions.get(sid)
        if (s?.channelId) {
          this.pluginHost.send(s.channelId, { sessionId: sid, content: '', done: true })
        }
        // Fan out done signal to original channel via primary router
        const routerSrcEnd = this.primaryRouter?.getSource()
        if (routerSrcEnd) {
          this.pluginHost.send(routerSrcEnd.channelId, { sessionId: routerSrcEnd.sessionId, content: '', done: true })
          this.primaryRouter!.clearTurn()
        }
      } catch (err) {
        this.logger.warn(`failed to finalize stream for ${sid}: ${String(err)}`)
      }
    })

    // Detect feedback signals in every user message.
    // WHY: runs on turn:start to capture signals from previous turn response before current turn context assembly
    this.bus.on("turn:start", (e) => {
      if (!this.outcomeTracker) return
      const { sessionId, message } = e as { sessionId: string; message: string }
      if (!message) return
      try {
        const signals = this.outcomeTracker.detectFeedback(message, sessionId)
        if (signals.length > 0) {
          this.logger.debug(`Detected ${signals.length} feedback signal(s) in ${sessionId.slice(-8)}`, {
            types: signals.map(s => s.type),
          })
        }
      } catch (err) {
        this.logger.warn(`Feedback detection failed: ${String(err)}`)
      }
    })

    // 8. Subscribe to plugin:crashed — log worker crashes
    interface PluginCrashedEvent {
      pluginId: string
      error: string
    }
    this.bus.on("plugin:crashed", (e) => {
      const event = e as PluginCrashedEvent
      this.logger.warn(`plugin crashed: ${event.pluginId} — ${event.error}`)
    })

    // 9. Subscribe to plugin:restarted — track restart attempts
    interface PluginRestartedEvent {
      pluginId: string
      attempt: number
    }
    this.bus.on("plugin:restarted", (e) => {
      const event = e as PluginRestartedEvent
      this.logger.info(`plugin restarted: ${event.pluginId} (attempt ${event.attempt})`)
    })

    // 10. Subscribe to config:reloaded — hot-reload confirmation + dialectic hot-update
    this.bus.on("config:reloaded", () => {
      this.logger.info("Config reloaded — no restart needed")
      // Hot-update dialectic injectAsThoughts from runtime config
      try {
        const dialecticCfg = this.config.get('intelligence.dialectic.injectAsThoughts', undefined) as
          | { enabled?: boolean; mode?: 'parallel' | 'consolidated'; timeoutMs?: number }
          | undefined
        if (dialecticCfg && this.intelligence?.dialectic) {
          this.intelligence.dialectic.setInjectAsThoughts(dialecticCfg)
        }
      } catch { /* best-effort */ }
    })

    // One-shot: propagate persisted dialectic injectAsThoughts override on boot
    // (loadPersistedOverrides runs before this, so the override is in the layered config)
    try {
      const dialecticCfg = this.config.get('intelligence.dialectic.injectAsThoughts', undefined) as
        | { enabled?: boolean; mode?: 'parallel' | 'consolidated'; timeoutMs?: number }
        | undefined
      if (dialecticCfg && this.intelligence?.dialectic) {
        this.intelligence.dialectic.setInjectAsThoughts(dialecticCfg)
      }
    } catch { /* best-effort */ }

    completePhase('runtime-wiring', {
      sessionPipeline: !!this.sessionPipeline,
      healthMonitor: !!this.healthMonitor,
      autonomousLoop: !!this.autonomousLoop,
    })

    // 11. Start AdminAPI — HTTP + Unix socket API for tool/session access
    this.logger.info('── Phase 6: Services ──────────────────────────────────')

    let adminInfo: { tcpPort: number | null; unixPath: string; tcpServer?: unknown; unixServer?: unknown } | undefined = undefined
    const adminApiStartedAt = Date.now()
    const adminApiStartPerf = performance.now()
    try {
      const adminApi = createAdminApi(this, this.logger)
      adminInfo = await adminApi.start()
      const adminApiReadyAt = Date.now()
      const adminApiReadyPerf = performance.now()
      adminReadyPerf = adminApiReadyPerf
      recordService(
        'admin-api',
        adminApiStartedAt,
        adminApiStartPerf,
        {
          status: 'ready',
          tcpPort: adminInfo?.tcpPort,
          unixPath: adminInfo?.unixPath,
        },
        adminApiReadyAt,
        adminApiReadyPerf,
      )
      this.logger.info(`AdminAPI listening on unix:${adminInfo?.unixPath} + http:${adminInfo?.tcpPort}`)
      // Wire HTTP server to health monitor for zombie detection
      if (adminInfo?.tcpServer && this.healthMonitor) {
        this.healthMonitor.wire({ httpServer: adminInfo.tcpServer as { listening: boolean } })
      }
    } catch (err) {
      recordService('admin-api', adminApiStartedAt, adminApiStartPerf, {
        status: 'failed',
        error: String(err),
      })
      this.logger.warn(`AdminAPI failed to start: ${String(err)}`)
    }

    // 11b. Start Bridge (OpenAI-compatible API for OpenClaw integration)
    let bridgeStarted = false
    const bridgeServiceStartedAt = Date.now()
    const bridgeServiceStartPerf = performance.now()
    try {
      const bridgeSocketPath = this.config.get<string>('bridge.socketPath', path.join(homedir(), '.cassicore', 'bridge.sock'))
      const bridge = createBridge(providers, this.logger, { socketPath: bridgeSocketPath })
      await bridge.start()
      bridgeStarted = true
      recordService('bridge', bridgeServiceStartedAt, bridgeServiceStartPerf, {
        status: 'ready',
        socketPath: bridgeSocketPath,
      })
      this.logger.info(`Bridge listening on unix:${bridgeSocketPath}`)
    } catch (err) {
      recordService('bridge', bridgeServiceStartedAt, bridgeServiceStartPerf, {
        status: 'failed',
        error: String(err),
      })
      this.logger.warn(`Bridge failed to start: ${String(err)}`)
    }

    // 12. Set running
    this.running = true

    const readyAt = Date.now()
    const readyPerf = performance.now()
    completePhase('services', {
      adminApiStarted: !!adminInfo,
      bridgeStarted,
    }, readyAt, readyPerf)

    const bootSnapshot: DaemonBootSnapshot = {
      sequence: this.bootSequence + 1,
      pid: process.pid,
      startedAt: bootStartedAt,
      readyAt,
      durationMs: roundDurationMs(readyPerf - bootStart),
      timeToAdminReadyMs: adminReadyPerf === null ? null : roundDurationMs(adminReadyPerf - bootStart),
      phases: bootPhases,
      services: bootServices,
    }
    this.recordBootMetrics(bootSnapshot)

    // 13. Emit daemon:ready — triggers optimizer loop start
    void this.bus.emit({
      type: 'daemon:boot_complete',
      startedAt: new Date(bootSnapshot.startedAt),
      readyAt: new Date(bootSnapshot.readyAt),
      durationMs: bootSnapshot.durationMs,
      timeToAdminReadyMs: bootSnapshot.timeToAdminReadyMs,
      phases: bootSnapshot.phases.map((phase) => ({
        name: phase.name,
        durationMs: phase.durationMs,
        sinceBootMs: phase.sinceBootMs,
      })),
      services: bootSnapshot.services.map((service) => ({
        name: service.name,
        durationMs: service.durationMs,
        sinceBootMs: service.sinceBootMs,
      })),
    })
    void this.bus.emit({ type: "daemon:ready", startedAt: new Date(readyAt) })

    // 14. Start health monitor (after daemon:ready so all subsystems are wired)
    this.healthMonitor.start()

    // 15. Start optional non-critical services after readiness — do not block admin/API critical path
    this.scheduleDeferredStartup()

    // 16. Log startup banner with boot timing
    const loaded = this.pluginHost.all().length
    const pid = process.pid
    const bootMs = Math.round(performance.now() - bootStart)
    const bootSec = (bootMs / 1000).toFixed(1)
    const readyLabel = `CassiCore v${CASSICORE_VERSION} — Ready`
    const timingLabel = `(${bootSec}s boot)`
    // Dynamically size the banner to fit content
    const innerWidth = Math.max(readyLabel.length + timingLabel.length + 5, 40)
    const topBot = '═'.repeat(innerWidth)
    const paddedContent = `  ${readyLabel}  ${timingLabel}  `
    const pad = innerWidth - paddedContent.length
    const line = `║${paddedContent}${' '.repeat(Math.max(0, pad))}║`
    this.logger.info(`╔${topBot}╗`)
    this.logger.info(line)
    this.logger.info(`╚${topBot}╝`)

    // Compact summary line
    const toolCount = toolRegistry.list().length
    const moduleCount = this.intelligence?.all.length ?? 0
    const providerCount = providers.size
    const channelList: string[] = []
    for (const p of this.pluginHost.all()) {
      if (p.id.startsWith('channel:')) channelList.push(p.id.replace('channel:', ''))
    }
    this.logger.info(
      `PID ${pid} | ${providerCount} providers | ${moduleCount} cognitive modules | ${toolCount} tools | ${loaded} plugins | ${channelList.length > 0 ? channelList.join(', ') : 'no channels'} | hot-reload active`
    )
    this.logger.info('Boot phases recorded', {
      totalMs: bootSnapshot.durationMs,
      timeToAdminReadyMs: bootSnapshot.timeToAdminReadyMs,
      phases: bootSnapshot.phases.map((phase) => `${phase.name}:${phase.durationMs}ms`),
    })

    // Return runtime info (useful for CLI agents)
    return { admin: adminInfo, pid }
  }

  /**
  * Load secrets from ~/.cassicore/.env into process.env.
   * Keys are only set if not already present in the environment.
   * Safe to call multiple times. .env is optional — silently ignored if missing.
   */
  private async _loadEnv(): Promise<void> {
    const envPath = join(homedir(), '.cassicore', '.env')
    try {
      const raw = fs.readFileSync(envPath, 'utf8')
      let loaded = 0
      for (const line of raw.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith('#')) continue
        const eq = trimmed.indexOf('=')
        if (eq < 0) continue
        const key = trimmed.slice(0, eq).trim()
        const val = trimmed.slice(eq + 1).trim().replace(/^["']|["']$/g, '')
        if (key && !process.env[key]) {
          process.env[key] = val
          loaded++
        }
      }
      if (loaded > 0) {
        this.logger.debug(`Loaded ${loaded} secret(s) from .cassicore/.env`)
      }
    } catch {
      // .env is optional
    }
  }


  /**
   * Stop the daemon gracefully.
   * Each async shutdown step is time-bounded to prevent hangs.
   * @returns Promise that resolves after shutdown
   */
  async stop(): Promise<void> {
    if (!this.running) return
    this.logger.info("Shutting down gracefully...")

    const SHUTDOWN_STEP_TIMEOUT_MS = 30_000 // 30s per step

    /** WHY: timeout prevents hangs — if a subsystem won't stop, move on to avoid blocking shutdown */
    const timedStep = async (label: string, fn: () => Promise<void> | void): Promise<void> => {
      try {
        await Promise.race([
          Promise.resolve(fn()),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error(`Shutdown step "${label}" timed out after ${SHUTDOWN_STEP_TIMEOUT_MS}ms`)), SHUTDOWN_STEP_TIMEOUT_MS)
          ),
        ])
      } catch (err) {
        this.logger.warn(`Shutdown step "${label}" failed: ${String(err)}`)
      }
    }

    // emit shutdown — triggers optimizer loop stop
    this.bus.emit({ type: "daemon:shutdown", reason: "signal" })

    // WHY: Mark running constellations as 'interrupted' before other shutdown steps.
    // This preserves their checkpoint data so they can be auto-resumed on next boot.
    // Must happen early — before providers or stores are torn down.
    await timedStep('constellation-interrupt', async () => {
      try {
        const { ConstellationStore } = await import('./intelligence/constellation/constellation-store.js')
        const constellationStore = ConstellationStore.open(this.logger.child('constellation-store'))
        const running = constellationStore.listSessions({ status: 'running' })
        for (const session of running) {
          constellationStore.interruptSession(session.id, session.durationMs ?? undefined)
          this.logger.info('Interrupted constellation for graceful shutdown', { sessionId: session.id })
        }
        constellationStore.close()
      } catch (err) {
        this.logger.warn('Failed to interrupt constellations during shutdown', { error: String(err) })
      }
    })

    if (this.deferredStartupTimer) {
      clearTimeout(this.deferredStartupTimer)
      this.deferredStartupTimer = null
    }

    // stop health monitor
    try {
      this.healthMonitor?.stop()
    } catch { /* ignore */ }

    // stop background embedding worker
    try {
      this.bgEmbeddingWorker?.stop()
    } catch { /* ignore */ }

    // stop background tagger worker
    try {
      this.bgTaggerWorker?.stop()
    } catch { /* ignore */ }

    // stop embedding stack child processes (llama.cpp + zerank)
    try {
      this.embeddingStackLauncher?.stop()
    } catch { /* ignore */ }

    // stop warm provider manager — destroys OpenCode warm sessions to release resources
    await timedStep('warm-provider', async () => {
      const { shutdownWarmProvider } = await import('./admin-api/warm-provider.js')
      await shutdownWarmProvider()
    })

    // stop Copilot SDK — kills CLI server process, destroys sessions
    await timedStep('copilot-sdk', async () => {
      const sdkManager = (this as unknown as Record<string, unknown>).__copilotSdkManager as
        { stop(): Promise<void> } | undefined
      if (sdkManager) {
        // Destroy all SDK sessions first
        const sdkProvider = (this.pipeline as unknown as { providers?: Map<string, unknown> })
          ?.providers?.get?.('copilot-sdk') as { destroyAllSessions(): Promise<void> } | undefined
        await sdkProvider?.destroyAllSessions?.()
        await sdkManager.stop()
        this.logger.info('Copilot SDK stopped')
      }
    })

    // stop unified intelligence loop
    await timedStep('unified-loop', async () => {
      if (this.unifiedLoop) {
        await this.unifiedLoop.stop('daemon-shutdown')
      }
    })

    // stop auto-discovered registry modules
    await timedStep('registry-modules', async () => {
      if (this.intelligence?.registry) {
        await this.intelligence.registry.stopAll()
      }
    })

    // stop Thinker BaseCognitiveModule lifecycle
    await timedStep('thinker', async () => {
      interface ThinkerWithStop {
        stop?(): Promise<void> | void
      }
      const thinker = this.intelligence?.thinker as ThinkerWithStop | undefined
      await thinker?.stop?.()
    })

    // shutdown session pipeline if active
    await timedStep('session-pipeline', async () => {
      if (this.sessionPipeline) {
        await this.sessionPipeline.shutdown()
        this.logger.info('Session pipeline shut down')
      }
    })

    // shutdown plugin host
    await timedStep('plugin-host', async () => {
      await this.pluginHost.shutdown()
    })

    // attempt to stop config watcher if possible
    interface ConfigWithWatcher {
      watcher?: { close(): void }
    }
    try {
      const cfg = this.config as ConfigWithWatcher
      if (typeof cfg?.watcher?.close === "function") {
        cfg.watcher.close()
      }
    } catch {
      // WHY: ignore — config watcher shutdown is best-effort, process exiting anyway
    }

    // stop session pruning and close session store
    try {
      this.sessions?.stopPruning?.()
    } catch { /* ignore */ }
    interface SessionsWithStore {
      store?: { close(): void }
    }
    try {
      const sessions = this.sessions as unknown as SessionsWithStore | undefined
      sessions?.store?.close?.()
    } catch { /* ignore */ }

    try {
      this.intelligence?.cortex?.close()
    } catch { /* ignore */ }

    // Close mnemic field code store and file vault databases
    try {
      const mnemicField = (this as any).__mnemicFieldForCode as { close(): void } | undefined
      mnemicField?.close()
    } catch { /* ignore */ }
    try {
      const vault = (this as any).__fileVault as { close(): void } | undefined
      vault?.close()
    } catch { /* ignore */ }

    // Close prompt log store
    try {
      this.promptLogStore?.close()
    } catch { /* ignore */ }
    // Close rate limit store
    try {
      this.rateLimitStore?.close()
    } catch { /* ignore */ }
    // Close timeline store
    try {
      if (this.timelineStore) {
        // Unsubscribe from event bus
        const unsub = (this.timelineStore as any)._busUnsub
        if (typeof unsub === 'function') unsub()
        this.timelineStore.close()
      }
    } catch { /* ignore */ }
    try {
      this.intelligence?.training?.close()
    } catch { /* ignore */ }

    // intelligence cleanup
    await timedStep('intelligence-cleanup', async () => {
      interface ModuleWithCleanup {
        cleanup?(): Promise<void> | void
      }
      for (const m of this.intelligence.all) {
        const mod = m as ModuleWithCleanup
        if (typeof mod.cleanup === "function") {
          await mod.cleanup()
        }
      }
    })

    // persist budget tracker state
    await timedStep('budget-save', async () => {
      if (this.budgetTracker) {
        await this.budgetTracker.saveToDisk()
      }
    })

    this.running = false
    this.logger.info("Goodbye.")
    process.exit(0)
  }

  /**
   * Hot-reload configuration and push changes to workers.
   */
  async reload(): Promise<void> {
    this.logger.info("Reloading config (no restart)...")
    try {
      await this.config.reload()

      const defaultModel = this.config.get<string>('intelligence.defaultModel', getModelSpec('main'))
      const thinking = this.config.get<string>('intelligence.thinking', 'high') as import('../types/runtime.js').ThinkingLevel
      this.sessions.setDefaultConfig({ model: defaultModel, thinking })

      // Propagate model config to BaseCognitiveModule subclasses
      // (config:changed handlers handle this automatically for modules with wireConfigWatcher,
      //  but explicit reload covers modules that may not have been initialized yet)
      interface ModuleWithReload {
        reloadModelConfig?(): void
      }
      for (const m of this.intelligence?.all ?? []) {
        const mod = m as ModuleWithReload
        if (typeof mod.reloadModelConfig === 'function') {
          try {
            mod.reloadModelConfig()
          } catch (err) {
            this.logger.warn(`failed to reload model config for ${m.name}: ${String(err)}`)
          }
        }
      }
    } catch (err) {
      this.logger.warn(`failed to reload config: ${String(err)}`)
      return
    }

    // Hot-toggle inference stack (llama.cpp GPU processes) based on config change.
    // WHY: set intelligence.inferenceStack.enabled=false to free GPU VRAM (e.g. when gaming)
    const inferenceStackEnabled = this.config.get<boolean>('intelligence.inferenceStack.enabled', true)
    if (this.inferenceStackEnabled && !inferenceStackEnabled) {
      this.logger.info('InferenceStack disabled via config — stopping local inference processes to free GPU')
      try {
        this.embeddingStackLauncher?.stop()
      } catch (err) {
        this.logger.warn(`Failed to stop embedding stack: ${String(err)}`)
      }
      this.inferenceStackEnabled = false
    } else if (!this.inferenceStackEnabled && inferenceStackEnabled) {
      this.logger.info('InferenceStack enabled via config — starting local inference processes')
      await this.startInferenceStackLauncher()
    }

    const all = this.pluginHost.all()
    for (const p of all) {
      const newCfg = this.config.get<Record<string, unknown>>(`plugins.${p.id}`, {})
      try {
        this.pluginHost.updateConfig(p.id, newCfg)
      } catch (err) {
        this.logger.warn(`failed to update config for ${p.id}: ${String(err)}`)
      }
    }

    this.logger.info("Reload complete.")
  }
}
