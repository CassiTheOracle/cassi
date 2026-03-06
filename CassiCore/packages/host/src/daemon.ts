import { EventBus, bus } from "./event-bus.js"
import { Logger, rootLogger } from "./logger.js"
import { Config } from "./config.js"
import { createLayeredConfig } from "./runtime-config.js"

import fs from "node:fs"
import { homedir } from "node:os"
import path, { join } from "node:path"
import { fileURLToPath } from "node:url"

// Read version from package.json at module load time so it stays in sync
const _pkgPath = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'package.json')
const CASSICORE_VERSION: string = (() => {
  try { return JSON.parse(fs.readFileSync(_pkgPath, 'utf8')).version ?? '0.3.1' }
  catch { return '0.3.1' }
})()

import { createAdminApi } from './admin-api.js'
import { createBridge } from './bridge.js'
import { CommandDispatcher } from './commands.js'
import { createSkillMetricsTracker, type SkillMetricsTracker } from './intelligence/skill-metrics.js'
import { createCrossSessionCorrelator, type CrossSessionCorrelator } from './intelligence/cross-session-correlator.js'
import { createStrategyTracker, type StrategyTracker } from './intelligence/strategy-tracker.js'
import { createProviderProfiler, type ProviderProfiler } from './intelligence/provider-profiler.js'
import { createAdaptiveBehavior, type AdaptiveBehavior } from './intelligence/adaptive-behavior.js'
import { createSelfVerification, type SelfVerification } from './intelligence/self-verification.js'
import { initContextWindowDebugger, ContextWindowDebugger } from './events/context-window-debug.js'
import { setContextWindowDebugger, contextWindowDebugMiddleware } from './turn-pipeline.js'
import { createSessionDigestStore, type SessionDigestStore } from './intelligence/session-digest.js'
import { AutonomousAgentLoop } from './intelligence/autonomous-loop.js'
import { createExecutionBackend } from './intelligence/execution-backends/index.js'
import { IntelligentContextWindow } from './intelligence/context-window/index.js'
import type { ExecutionBackendType, OpenCodeBackendConfig } from '../types/execution-backend.js'
import { MODEL_DEFAULTS, getModelSpec } from './config/system-settings.js'
import { HealthMonitor } from './health-monitor.js'
import { createIntelligence } from "./intelligence/index.js"
import { createOutcomeTracker, type OutcomeTracker } from './intelligence/outcome-tracker.js'
import { MCPRegistry } from './mcp/registry.js'
import { createOrchestrationBus } from './orchestration-bus.js'
import { PluginHost } from "./plugin-host.js"
import { type BudgetTracker, createBudgetTracker } from './providers/budget-tracker.js'
import { type ModelRouter, createModelRouter } from './providers/model-router.js'
import { ScoutModule } from './scout/index.js'
import { createSessionBridge } from './session-bridge.js'
import { createSessionManager } from './session-manager.js'
import { SessionStore } from './session-store.js'
import { createSubagentTracker, type SubagentTracker } from './subagent-tracker.js'
import { ToolExecutor } from './tools/executor.js'
import { registerDroneTools } from './tools/implementations/drone-swarm.js'
import { registerCoreTools } from './tools/implementations/index.js'
import { registerTeamTools } from './tools/implementations/team-coordinator.js'
import { ToolRegistry } from './tools/registry.js'
import { TurnPipeline } from './turn-pipeline.js'
import { buildSystemPrompt } from './workspace/loader.js'


import type { IEventBus, ILogger, IConfig, IPluginHost, IntelligenceModule } from "../types/interfaces.js"
import type { IProvider } from '../types/runtime.js'
import type { IntelligenceLayer } from "./intelligence/index.js"

// Type helper for intelligence modules with optional event handlers
interface EventHandler { onEvent?: (e: unknown) => void | Promise<void> }

// Singleton lock file path
const CASSICORE_PID_FILE = path.join(homedir(), '.cassicore', 'daemon.pid')

/**
 * Check if another daemon instance is already running
 * Returns the PID of the running daemon, or null if none
 */
function checkExistingDaemon(): number | null {
  try {
    if (!fs.existsSync(CASSICORE_PID_FILE)) {
      return null
    }

    const pidContent = fs.readFileSync(CASSICORE_PID_FILE, 'utf-8').trim()
    const existingPid = parseInt(pidContent, 10)

    if (isNaN(existingPid) || existingPid <= 0) {
      // Stale PID file
      fs.unlinkSync(CASSICORE_PID_FILE)
      return null
    }

    // Check if process is actually running
    try {
      process.kill(existingPid, 0)
      // Process exists and we have permission to signal it
      return existingPid
    } catch (err) {
      // Process doesn't exist or no permission - stale PID file
      if ((err as NodeJS.ErrnoException).code === 'ESRCH') {
        fs.unlinkSync(CASSICORE_PID_FILE)
        return null
      }
      // EPERM - process exists but we can't signal it (different user)
      return existingPid
    }
  } catch (err) {
    // Any other error - assume no daemon running
    return null
  }
}

/**
 * Write current PID to lock file
 */
function writePidFile(): void {
  try {
    const cassicoreDir = path.dirname(CASSICORE_PID_FILE)
    if (!fs.existsSync(cassicoreDir)) {
      fs.mkdirSync(cassicoreDir, { recursive: true })
    }
    fs.writeFileSync(CASSICORE_PID_FILE, process.pid.toString(), 'utf-8')
  } catch (err) {
    console.error(`Warning: Could not write PID file: ${String(err)}`)
  }
}

/**
 * Remove PID file on shutdown
 */
function cleanupPidFile(): void {
  try {
    if (fs.existsSync(CASSICORE_PID_FILE)) {
      fs.unlinkSync(CASSICORE_PID_FILE)
    }
  } catch (err) {
    // Ignore cleanup errors
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
   public sessionDigestStore?: SessionDigestStore
    /** Background embedding pre-computation worker. */
   public bgEmbeddingWorker?: import('./intelligence/embeddings/background-worker.js').BackgroundEmbeddingWorker
   /** Embedding stack launcher (auto-starts llama.cpp + zerank servers). */
   public embeddingStackLauncher?: import('./intelligence/embeddings/embedding-stack-launcher.js').EmbeddingStackLauncher
  /** Loaded provider map — available after daemon start(). */
  public providers: Map<string, IProvider> = new Map()
  /** Background intelligence loop — available after daemon start(). */
  public unifiedLoop?: import('./intelligence/unified-loop.js').UnifiedIntelligenceLoop
  /** Tool executor — available after daemon start(). */
  public toolExecutor?: ToolExecutor
  /** Autonomous agent loop — available when feature is enabled. */
  public autonomousLoop?: import('./intelligence/autonomous-loop.js').AutonomousAgentLoop
  /** Session pipeline integration */
  public sessionPipeline?: import('./pipeline/adapter/SessionPipeline.js').SessionPipeline
  public budgetTracker?: BudgetTracker
  public modelRouter?: ModelRouter
  /** IntelligentContextWindow instance — available after daemon start(). */
  public contextWindow?: IntelligentContextWindow
  // expose orchestration bus for external use
  public orchestration?: ReturnType<typeof createOrchestrationBus>

  constructor(busInstance: IEventBus = bus, logger: ILogger = rootLogger) {
    this.bus = busInstance
    this.logger = logger.child('daemon')
    // create orchestration bus and attach
    try {
      this.orchestration = createOrchestrationBus(this.logger.child('orchestration'))
      // start session bridge
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

  /**
   * Start the daemon: load config, start plugin host, wire signals and workers.
   */
  async start(): Promise<{ admin?: { tcpPort: number | null; unixPath: string }; pid: number }> {
    const bootStart = performance.now()

    // 0. Load .env secrets (before anything reads env vars)
    await this._loadEnv()

    // 0b. Check for existing daemon instance (singleton enforcement)
    const existingPid = checkExistingDaemon()
    if (existingPid !== null) {
      // Exit silently — OpenCode or other tools may periodically probe for the daemon,
      // and noisy errors spam daemon.log when stdout/stderr is redirected there.
      process.exit(0)
    }

    // Write our PID to the lock file
    writePidFile()
    this.logger.info(`PID file written: ${process.pid}`)

    // Register cleanup on exit
    process.on('exit', cleanupPidFile)
    process.on('SIGTERM', () => { cleanupPidFile(); process.exit(0) })
    process.on('SIGINT', () => { cleanupPidFile(); process.exit(0) })

    // ── Phase 1: Configuration ──────────────────────────────────────────────
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

    // 3. Start config watcher (file-level)
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

    // 3. Register SIGHUP -> reload
    process.on("SIGHUP", () => {
      void this.reload()
    })

    // 4. Register SIGTERM + SIGINT -> stop
    const stopHandler = () => {
      void this.stop()
    }
    process.on("SIGTERM", stopHandler)
    process.on("SIGINT", stopHandler)

    if (process.stdin.listenerCount("error") === 0) {
      process.stdin.on("error", (err) => {
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
        // Treat plain timeouts as lower-severity (they are common with provider/polling cancellations)
        if (String(errMsg).toLowerCase().includes('timeout')) {
          this.logger.debug?.('unhandledRejection (timeout)', { error: errMsg })
        } else {
          this.logger.warn?.('unhandledRejection', { error: errMsg })
        }
      } catch (e) { /* ignore */ }
    })

    // Handle unhandled child process errors to prevent daemon crashes
    process.on('uncaughtException', (error) => {
      if (error && (error as NodeJS.ErrnoException).code === 'ENOENT' && (error as NodeJS.ErrnoException).syscall?.includes('spawn')) {
        // Shell command failed - log but don't crash
        this.logger.error?.('shell command failed', {
          syscall: (error as NodeJS.ErrnoException).syscall,
          path: (error as NodeJS.ErrnoException).path,
          message: error.message
        })
        // Don't exit - just log the error
        return
      }
      // For other uncaught exceptions, log and continue if possible
      this.logger.error?.('uncaughtException', { error: error.message, stack: error.stack })
    })

    // 5. Create PluginHost with logger
    this.pluginHost = new PluginHost(this.logger)

    // ── Phase 2: Intelligence Layer ──────────────────────────────────────────
    this.logger.info('── Phase 2: Intelligence Layer ────────────────────────')

    // Initialize intelligence layer before loading plugins
    try {
      this.intelligence = createIntelligence(this.logger, this.config)

      // Wire modules to event bus
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

      // Optimizer listens for daemon:ready (starts loop) and daemon:shutdown (stops loop)
      bus.on("daemon:ready", (e) => {
        void (this.intelligence.optimizer as EventHandler).onEvent?.(e)
      })
      bus.on("daemon:shutdown", (e) => {
        void (this.intelligence.optimizer as EventHandler).onEvent?.(e)
      })

      // Wire DialecticSystem to event bus for streaming
      this.wireModule(this.intelligence.dialectic, bus)

      // Wire Thinker to event bus for proactive triggers
      this.wireModule(this.intelligence.thinker, bus)

      // Wire AI Scientist to event bus for metrics collection
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
          optimizer: this.intelligence.optimizer as OptimizerWithLoop,
          all: this.intelligence.all,
        })

        await unifiedLoop.start()
        ;this.unifiedLoop = unifiedLoop
        this.logger.info('Unified Intelligence Loop started')
      } catch (err) {
        this.logger.warn('Failed to initialize Unified Intelligence Loop', { error: String(err) })
      }

      // Wire Subconscious to event bus for background consolidation
      this.wireModule(this.intelligence.subconscious, bus)
      this.startModule(this.intelligence.subconscious)

      // Reconcile the Subconscious SystemModel with the live SessionManager state.
      // Sessions created before the subconscious was wired never triggered a
      // session:created event, leaving activeSessions=0 and causing telemetry drift.
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

      // Wire Multi-Agent Coordinator to event bus
      this.wireModule(this.intelligence.multiAgent, bus)

      // Wire Rule Enforcer to event bus
      this.wireModule(this.intelligence.ruleEnforcer, bus)

      // Wire Drone Swarm Controller to event bus
       if (this.intelligence.droneSwarm?.setEventBus) {
         this.intelligence.droneSwarm.setEventBus(bus)
         this.logger.info('DroneSwarm event bus wired')
       }

       // Wire SelfHealingAgent — give it the EventBus and a repair provider
       // that delegates to the Thinker's repair-request/response event pair.
       this.wireModule(this.intelligence.selfHealer, bus)
       ;(this.intelligence.selfHealer as IntelligenceModule).setRepairProvider?.(
             async (prompt: string): Promise<string> => {
                // Strategy 1: direct call to github-copilot (doesn't depend on Thinker health)
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
               // Strategy 2: Thinker event chain (90s timeout)
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

        // Wire Consequence Estimator + Trust Ledger + Permission Oracle
        // These form the graduated autonomy system.
        try {
          this.wireModule(this.intelligence.consequenceEstimator, bus)
          this.wireModule(this.intelligence.trustLedger, bus)
          // Give Trust Ledger access to the Memory DB for persistence
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
          // Register as cycle hook on unified loop if available
          const loop = this.unifiedLoop
          if (loop?.addCycleHook) {
            loop.addCycleHook(tracker)
            this.logger.info('OutcomeTracker registered as unified loop cycle hook')
          }
          this.outcomeTracker = tracker
          this.logger.info('OutcomeTracker initialized')
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
            this.logger.info('CrossSessionCorrelator registered as unified loop cycle hook')
          }
          this.crossSessionCorrelator = correlator
          this.logger.info('CrossSessionCorrelator initialized')
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
            this.logger.info('StrategyTracker registered as unified loop cycle hook')
          }
          this.strategyTracker = stratTracker
          this.logger.info('StrategyTracker initialized')
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
            this.logger.info('ProviderProfiler registered as unified loop cycle hook')
          }
          this.providerProfiler = profiler
          this.logger.info('ProviderProfiler initialized')
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
            this.logger.info('AdaptiveBehavior registered as unified loop cycle hook')
          }
          this.adaptiveBehavior = adaptive
          this.logger.info('AdaptiveBehavior initialized')
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
            this.logger.info('SelfVerification registered as unified loop cycle hook')
          }
          this.selfVerification = verification
          this.logger.info('SelfVerification initialized')
        }
      } catch (err) {
        this.logger.warn(`Failed to initialize SelfVerification: ${String(err)}`)
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
            this.logger.info('ImprovementOrchestrator registered as unified loop cycle hook')
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

      // ── Phase 3: Thinker Event Listeners ────────────────────────────────────
      // Listen for Thinker's proactive events
      interface ThinkerInjectInsightEvent {
        urgency?: number
        insight?: string
      }
      interface ThinkerEarlyWarningEvent {
        warning: string
      }
      interface PipelineWithPendingInsight {
        pendingThinkerInsight?: string
      }
      interface OptimizerWithEarlyWarning {
        handleEarlyWarning?(e: ThinkerEarlyWarningEvent): void
      }
      bus.on('thinker:inject-insight', (e) => {
        const event = e as ThinkerInjectInsightEvent
        this.logger.info('Thinker injecting insight', { urgency: event.urgency })
        // Store for next turn injection via pipeline
        if (event.insight && this.pipeline) {
          // This will be picked up by the turn pipeline
          ;(this.pipeline as unknown as PipelineWithPendingInsight).pendingThinkerInsight = event.insight
        }
      })

      bus.on('thinker:early-warning', (e) => {
        const event = e as ThinkerEarlyWarningEvent
        this.logger.warn('Thinker early warning', { pattern: event.warning })
        // Trigger optimizer early intervention
        if (this.intelligence?.optimizer) {
          ;(this.intelligence.optimizer as OptimizerWithEarlyWarning).handleEarlyWarning?.(event)
        }
      })

      bus.on('thinker:self-modified', (e) => {
        this.logger.info('Thinker self-modified strategy', e.change)
      })

      bus.on('thinker:swarm-deployed', (e) => {
        this.logger.info('Thinker deployed swarm', { swarmId: e.swarmId, mission: e.mission })
      })

      // ── Embedding Stack Auto-Start ───────────────────────────────────────
      // Launches llama.cpp embedding server + zerank reranker as child
      // processes so they're available when the daemon needs them.
      try {
        const { EmbeddingStackLauncher } = await import('./intelligence/embeddings/embedding-stack-launcher.js')
        this.embeddingStackLauncher = new EmbeddingStackLauncher(this.logger)
        await this.embeddingStackLauncher.start()
        this.logger.info('EmbeddingStackLauncher ready')
      } catch (err) {
        this.logger.warn(`Failed to start embedding stack: ${String(err)}`)
      }

      // ── Background Embedding Worker ──────────────────────────────────────
      // Pre-computes embeddings for archived content in the background.
      // Uses SqliteVectorIndex as persistent store for rapid retrieval.
      try {
        const { getBackgroundEmbeddingWorker } = await import('./intelligence/embeddings/background-worker.js')
        this.bgEmbeddingWorker = getBackgroundEmbeddingWorker(this.logger)
        this.bgEmbeddingWorker.start()
        this.logger.info('BackgroundEmbeddingWorker started')
      } catch (err) {
        this.logger.warn(`Failed to start BackgroundEmbeddingWorker: ${String(err)}`)
      }

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

    // Helper to resolve worker path (handles both .js and .ts)
    const __dirname = path.dirname(fileURLToPath(import.meta.url))
    const resolveWorker = (relPath: string): string | null => {
      const jsPath = path.resolve(__dirname, `${relPath  }.js`)
      if (fs.existsSync(jsPath)) return jsPath
      const tsPath = path.resolve(__dirname, `${relPath  }.ts`)
      if (fs.existsSync(tsPath)) return tsPath
      return null
    }

    // 6. Load the echo-channel worker (phase 1)
    // ── Phase 3: Channels ────────────────────────────────────────────────────
    this.logger.info('── Phase 3: Channels ──────────────────────────────────')

    const echoPath = resolveWorker("../workers/echo-channel")

    if (!echoPath) {
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

    // 7b. Load CLI channel worker (always enabled for admin-api support)
    const cliPath = resolveWorker("../workers/channels/cli")
    if (!cliPath) {
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

    // ── Budget tracking & model routing ─────────────────────────────────────
    // ── Phase 4: Providers & Wiring ──────────────────────────────────────────
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

    // Wire provider map into Multi-Agent Coordinator so providerId hints can be resolved
    interface MultiAgentWithProviders {
      setProviders?(providers: Map<string, IProvider>): void
    }
    try {
      const multiAgent = this.intelligence?.multiAgent as MultiAgentWithProviders | undefined
      if (multiAgent && typeof multiAgent.setProviders === 'function') {
        multiAgent.setProviders(providers)
        this.logger.info('Multi-Agent providers wired')
      }
    } catch (e) {
      this.logger.warn('failed to wire providers to multi-agent', { error: String(e) })
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

    // Create sessions and turn pipeline
    // ── Phase 5: Pipeline & Tools ────────────────────────────────────────────
    this.logger.info('── Phase 5: Pipeline & Tools ───────────────────────────')

    const systemPrompt = buildSystemPrompt(this.logger)
    this.logger.info(`System prompt built (${systemPrompt.length} chars)`)
    const sessionStore = SessionStore.open(this.logger)
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
        injectionAggregator: this.intelligence.injectionAggregator,
        cognitiveBridge: this.intelligence.cognitiveBridge,
        contextManager: this.intelligence.contextManager as any,
        subconscious: this.intelligence.subconscious as any,
        logger: this.logger,
      } : undefined,
      probeDeps: this.intelligence ? {
        thoughtObserver: this.intelligence.thoughtObserver,
        injectionAggregator: this.intelligence.injectionAggregator,
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
    })
    const allowedPaths = this.config.get<string[]>('tools.allowedPaths', [
      join(homedir(), 'workspaces'),
      join(homedir(), '.cassicore'),
      '/tmp/cassicore',
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

    this.logger.info(`Tools loaded: ${toolRegistry.list().map(t => t.name).join(', ')}`)

    // Initialize MCP registry and connect configured servers
    let mcpRegistry: MCPRegistry | undefined
    const mcpConfigs = this.config.get<Array<{ id: string; command: string; args?: string[]; env?: Record<string, string>; restartOnCrash?: boolean; maxRestarts?: number; startupTimeoutMs?: number; description?: string }>>('mcp.servers', [])
    if (mcpConfigs.length > 0) {
      this.logger.info(`Initializing MCP registry with ${mcpConfigs.length} server(s)`)
      mcpRegistry = new MCPRegistry(toolRegistry, this.logger)
      await mcpRegistry.start(mcpConfigs)

      // Inform the Multi-Agent coordinator about available tools so agents can
      // automatically include dynamic MCP tool instructions in their prompts.
      interface MultiAgentWithToolRegistry {
        setToolRegistry?(registry: ToolRegistry): void
      }
      try {
        const multiAgent = this.intelligence?.multiAgent as MultiAgentWithToolRegistry | undefined
        if (multiAgent?.setToolRegistry) {
          multiAgent.setToolRegistry(toolRegistry)
          this.logger.info('Connected ToolRegistry to Multi-Agent Coordinator')
        }
      } catch (e) {
        this.logger.warn('Failed to wire ToolRegistry to Multi-Agent Coordinator', { error: String(e) })
      }
    } else {
      this.logger.info('No MCP servers configured')
    }

    // ── IntelligenceRegistry: discover, wire, and start auto-loaded modules ──
    // This runs after all dependencies (bus, memory, providers, tools) are available.
    try {
      if (this.intelligence?.registry) {
        const registry = this.intelligence.registry

        // Discover modules from the compiled intelligence directory.
        // __dirname points to the compiled output (dist/core/), so navigate to intelligence/
        const intelligenceDir = join(path.dirname(fileURLToPath(import.meta.url)), 'intelligence')
        await registry.discover(intelligenceDir, new Set([
          'base', 'memory', 'continuity', 'recover', 'reflect', 'thinker',
          'optimizer', 'dialectic', 'ai-scientist', 'multi-agent', 'rule-enforcer',
          'subconscious', 'team-orchestrator', 'embeddings', 'yang', 'yin',
          'synthesizer', 'serenity',
          // self-healer is manually instantiated in createIntelligence() — skip auto-discovery
          // to prevent a duplicate instance from appearing in intelligence.all[]
          'self-healer',
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

        // Initialize and start all discovered modules
        await registry.initAll()
        await registry.startAll()

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

    // Bridge daemon.bus events → CassiCoreEventBus session buffers
    // so /events/history and verification tools can query pipeline events.
    try {
      const { getEventBus: getCassiCoreEventBus } = await import('./events/index.js')
      const cassiCoreBus = getCassiCoreEventBus()
      this.bus.onAll((event: any) => {
        if (event?.type && event?.sessionId) {
          cassiCoreBus.emit({
            ...event,
            timestamp: event.timestamp instanceof Date ? event.timestamp.getTime() : (event.timestamp ?? Date.now()),
          })
        }
      })
      this.logger.info('Event bridge: daemon.bus → CassiCoreEventBus wired')
    } catch (err) {
      this.logger.warn('Failed to wire event bridge', { error: String(err) })
    }

    // Wire subconscious system to pipeline for automatic context retrieval
    if (this.intelligence?.subconscious) {
      this.pipeline.setSubconscious(this.intelligence.subconscious)
    }

    // Wire intelligent context window (scores + selects history by recency + FTS relevance)
    try {
      const archivist = (this.intelligence?.memory as any)?.archivist
      if (archivist?.sessionIndexer) {
        const icw = new IntelligentContextWindow(archivist.sessionIndexer, this.logger)
        this.pipeline.setContextWindow(icw.asMiddleware())
        this.contextWindow = icw
        this.logger.info('IntelligentContextWindow wired')
      }
    } catch (err) {
      this.logger.warn('IntelligentContextWindow wiring failed, using default trim', {
        error: String(err),
      })
    }

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

    // Wire InjectionAggregator for unified turn pipeline context injection
    try {
      if (this.intelligence?.injectionAggregator) {
        this.intelligence.injectionAggregator.setDependencies({
          pipeline: this.pipeline,
          dialectic: this.intelligence.dialectic as any,
          subconscious: this.intelligence.subconscious,
          digestStore: this.sessionDigestStore!,
        })
        this.pipeline.setInjectionAggregator(this.intelligence.injectionAggregator)
        this.logger.info('InjectionAggregator wired to pipeline')
      }
    } catch (err) {
      this.logger.warn(`Failed to wire InjectionAggregator: ${String(err)}`)
    }

    // Wire ThoughtObserver to event bus for thinking stream monitoring.
    // Zero additional LLM requests — passively observes thinking chunks and
    // extracts cognitive signals (edge cases, assumptions, tensions, gaps).
    try {
      if (this.intelligence?.thoughtObserver) {
        this.intelligence.thoughtObserver.onEventBus(this.bus)
        this.logger.info('ThoughtObserver wired to event bus')
      }
    } catch (err) {
      this.logger.warn(`Failed to wire ThoughtObserver: ${String(err)}`)
    }

    // Wire CognitiveBridge to event bus for cross-session signal routing.
    // Auto-links sessions by shared projectPath and parent-child spawn relationships.
    // Routes ThoughtObserver signals bidirectionally between linked sessions.
    try {
      if (this.intelligence?.cognitiveBridge) {
        this.intelligence.cognitiveBridge.onEventBus(this.bus)
        this.intelligence.cognitiveBridge.setSessionManager(this.sessions)
        this.logger.info('CognitiveBridge wired to event bus + session manager')
      }
    } catch (err) {
      this.logger.warn(`Failed to wire CognitiveBridge: ${String(err)}`)
    }

    // Mount intelligence middlewares — continuity only (thinker runs fire-and-forget via onTurnEnd)
    if (this.intelligence) {
      this.pipeline.mountIntelligence({
        continuity: this.intelligence.continuity as any,

      })
      // Set intelligence layer reference on pipeline for tool handlers
      this.pipeline.setIntelligence(this.intelligence)

      // Wire Context Manager to sessions + pipeline if available
      try {
        if ((this.intelligence as any).contextManager) {
          const cm = (this.intelligence as any).contextManager
          if (typeof cm.setSessions === 'function') cm.setSessions(this.sessions)
          if (typeof cm.setPipeline === 'function') cm.setPipeline(this.pipeline)
          if (typeof cm.onEventBus === 'function') cm.onEventBus(this.bus)
          // Start periodic sync if configured
          try {
            const enabled = this.config.get<boolean>('intelligence.contextManager.enabled', true)
            const intervalMs = this.config.get<number>('intelligence.contextManager.syncIntervalMs', 60000)
            if (enabled && typeof cm.start === 'function') cm.start({ intervalMs })
            this.logger.info('ContextManager wired to session manager and pipeline')
          } catch (err) {
            this.logger.warn('ContextManager: failed to start sync', { error: String(err) })
          }
        }
      } catch (err) {
        this.logger.warn('failed to wire context manager', { error: String(err) })
      }

      // Wire optimizer to live session manager and pipeline — now it can actually work
      this.intelligence.optimizer.setSessions(this.sessions)
      this.intelligence.optimizer.setPipeline(this.pipeline)
      this.logger.info('Optimizer wired to session manager and pipeline')

      // Wire Scout module — pre-turn search agent that gathers context before main model
      try {
        const scoutEnabled = this.config.get<boolean>('intelligence.scout.enabled', true)
        if (scoutEnabled) {
          const scoutModule = new ScoutModule(this.logger.child('scout'), {
            enabled: true,
            providerId: this.config.get<string>('intelligence.scout.providerId', undefined),
            model: this.config.get<string>('intelligence.scout.model', undefined),
            maxToolRounds: this.config.get<number>('intelligence.scout.maxToolRounds', undefined),
            timeoutMs: this.config.get<number>('intelligence.scout.timeoutMs', undefined),
            maxContextChars: this.config.get<number>('intelligence.scout.maxContextChars', undefined),
          })
          scoutModule.setToolRegistry(toolRegistry)
          scoutModule.setToolExecutor(toolExecutor)
          scoutModule.setEventBus(this.bus)
          await scoutModule.init()
          scoutModule.setPipeline(this.pipeline)
          await scoutModule.start()
          this.logger.info('Scout module wired to pipeline, tool registry, and event bus')
        }
      } catch (err) {
        this.logger.warn('Failed to wire Scout module', { error: String(err) })
      }

      // Wire Thinker's session manager and pipeline getter for unified subagent spawning
      if ((this.intelligence.thinker as any)?.__awaitingWiring) {
        (this.intelligence.thinker as any).__awaitingWiring.setSessionManager(this.sessions, sessionStore)
          ; (this.intelligence.thinker as any).__awaitingWiring.setPipelineGetter(() => this.pipeline)
        this.logger.info('Thinker wired to session manager and pipeline for subagent spawning')
      }
      // Wire drone swarm into Thinker for scout/speculative pre-fetching
      if (this.intelligence.droneSwarm && typeof (this.intelligence.thinker as any).setDroneSwarm === 'function') {
        (this.intelligence.thinker as any).setDroneSwarm(this.intelligence.droneSwarm)
        this.logger.info('Thinker wired to drone swarm controller')
      }
      // Start Thinker's BaseCognitiveModule lifecycle (after all deps wired)
      await (this.intelligence.thinker as any).start?.()

      // Wire AutonomousAgentLoop engine into MultiAgentCoordinator
      try {
        const autonomousLoop = new AutonomousAgentLoop(this.logger.child('autonomous-loop'))
        autonomousLoop.setPipeline(this.pipeline)
        autonomousLoop.setEventBus(this.bus)
        if (this.intelligence.memory) autonomousLoop.setMemory(this.intelligence.memory)
        if (this.sessionDigestStore) autonomousLoop.setDigestStore(this.sessionDigestStore)
        autonomousLoop.setSessions(this.sessions)
        if (this.intelligence.dialectic) autonomousLoop.setDialectic(this.intelligence.dialectic as any)
        if (this.intelligence.multiAgent) {
          autonomousLoop.setMultiAgent(this.intelligence.multiAgent as any)
          ;(this.intelligence.multiAgent as any).setAutonomousLoop(autonomousLoop)
        }

        // Wire execution backend if configured (default: 'cassicore' — no change from current behavior)
        const backendType = this.config.get<ExecutionBackendType>('intelligence.executionBackend.type', 'cassicore')
        let executionBackend: ReturnType<typeof createExecutionBackend> | undefined = undefined
        if (backendType !== 'cassicore') {
          const openCodeConfig = this.config.get<OpenCodeBackendConfig>('intelligence.executionBackend.opencode', {})
          executionBackend = createExecutionBackend(backendType, this.logger.child('execution-backend'), {
            pipeline: this.pipeline,
            openCodeConfig,
          })
          autonomousLoop.setBackend(executionBackend)
          this.logger.info(`Execution backend set: ${executionBackend.name}`)

          // Wire execution backend to ContextManager for ongoing context push updates
          if ((this.intelligence as any).contextManager &&
              typeof (this.intelligence as any).contextManager.setExecutionBackend === 'function') {
            (this.intelligence as any).contextManager.setExecutionBackend(executionBackend)
            this.logger.info('ContextManager wired to execution backend for push updates')
          }
        }

        ;this.autonomousLoop = autonomousLoop
        this.logger.info('AutonomousAgentLoop engine initialized and wired')
      } catch (err) {
        this.logger.warn('Failed to initialize AutonomousAgentLoop', { error: String(err) })
      }

      // Wire TeamOrchestrator dependencies (needs pipeline, bus, digestStore, autonomousLoop)
      try {
        const to = this.intelligence.teamOrchestrator
        if (to) {
          to.setEventBus(this.bus)
          to.setPipeline(this.pipeline)
          if (this.sessionDigestStore) to.setDigestStore(this.sessionDigestStore)
          if (this.autonomousLoop) to.setAutonomousLoop(this.autonomousLoop)
          if (this.intelligence.droneSwarm) to.setDroneSwarm(this.intelligence.droneSwarm)
          this.logger.info('TeamOrchestrator wired to pipeline, bus, digestStore, autonomousLoop, droneSwarm')

          // Register team tools now that TeamOrchestrator is available
          registerTeamTools(toolRegistry, {
            teamOrchestrator: to as any,
            digestStore: this.sessionDigestStore,
            logger: this.logger,
          })
          this.logger.info(`Team tools registered: check_team_status, send_team_message, get_agent_result, list_team_agents, update_team_plan, complete_team_goal, get_team_goal_tree, approve_checkpoint`)
        }
      } catch (err) {
        this.logger.warn('Failed to wire TeamOrchestrator', { error: String(err) })
      }

      // Register drone swarm tools (if DroneSwarmController is available)
      try {
        if (this.intelligence.droneSwarm) {
          registerDroneTools(toolRegistry, {
            droneSwarm: this.intelligence.droneSwarm,
            logger: this.logger,
          })
          this.logger.info('Drone tools registered: drone_swarm, drone_scout, drone_cancel')
        }
      } catch (err) {
        this.logger.warn('Failed to register drone tools', { error: String(err) })
      }
    }

     // ── Session Pipeline Integration ─────────────────────────────────────────
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
        intelligence: {
          memory: (this as any).intelligence?.memory,
          dialectic: (this as any).intelligence?.dialectic,
          thinker: (this as any).intelligence?.thinker,
          subconscious: (this as any).intelligence?.subconscious
        },
        eventBus: this.bus
      }
      const pipeline = new SessionPipeline(v2Options as any)
      await pipeline.initialize()
      this.sessionPipeline = pipeline
      this.logger.info('Session pipeline initialized')
    } catch (err) {
      this.logger.warn('Failed to initialize session pipeline', { error: String(err) })
    }

    // ── Health Monitor ────────────────────────────────────────────────────────
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

        // ── Session-scoped events from the turn pipeline ──────────────────────
        // pluginId is "session:<sessionId>" for events emitted by the pipeline.
        // Route streaming tokens and status events to the channel worker that
        // owns the session.
        if (pluginId?.startsWith("session:") && payload?.sessionId) {
          try {
            const sid = payload.sessionId as string
            const s = this.sessions.get(sid)
            if (s && s.channelId) {
              const tgt = s.channelId
              if (payload.type === 'turn:direct_message' && payload.content) {
                // Command dispatcher response — send once and done
                this.pluginHost.send(tgt, { sessionId: sid, content: payload.content as string, done: true })
                return
              } else if (payload.type === 'turn:token' && payload.token) {
                // Stream token to channel — done=false keeps stream open
                this.pluginHost.send(tgt, { sessionId: sid, content: payload.token as string, done: false })
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

        // ── Worker log messages ───────────────────────────────────────────────
        if (payload?.type === 'log') {
          const level = (payload.level as string) || 'info'
          const msg = (payload.message as string) || ''
          if (level === 'error') this.logger.error(msg)
          else if (level === 'warn') this.logger.warn(msg)
          else this.logger.info(msg)
          return
        }

        // ── Reasoning/thinking capture from external agents ──────────────────
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

        // ── Inbound messages from channel workers ─────────────────────────────
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
          if (modelFromPayload && pluginId === 'channel:cli') {
            const session = this.sessions.get(inbound.sessionId)
            if (session) {
              session.config.model = modelFromPayload
            }
          }

          this.logger.info(`Processing inbound message`, { channel: pluginId, sessionId: inbound.sessionId, model: modelFromPayload })

          // Process the turn via session pipeline
          try {
            if (this.sessionPipeline) {
              const result = await this.sessionPipeline.processMessage(
                inbound.channelId,
                inbound.senderId,
                inbound.content,
                { attachments: inbound.attachments }
              )
              this.logger.info(`Turn complete`, { sessionId: result.sessionId })
              this.pluginHost.send(pluginId, {
                sessionId: result.sessionId,
                content: result.response,
                done: true,
              })
            } else {
              // Fallback: legacy pipeline (intelligence modules still depend on this)
              await this.pipeline.process(inbound)
              this.logger.info(`Turn complete (legacy)`, { sessionId: inbound.sessionId })
            }
          } catch (err) {
            this.logger.warn(`pipeline error: ${String(err)}`)
            // Send error message to channel
            this.pluginHost.send(pluginId, {
              sessionId: inbound.sessionId,
              content: `⚠️ Something went wrong — please try again.`,
              done: true,
            })
          }
        }
      } catch (err) {
        this.logger.warn(`error processing inbound message: ${String(err)}`)
      }
    })

    // ── Status message routing ────────────────────────────────────────────────
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
        // this.pluginHost.send(s.channelId, { type: 'status', payload: { sessionId, text: 'Context synced.', type: 'sync' } })
      }
    })

    // ── Streaming finalization ────────────────────────────────────────────────
    // turn:end fires after the pipeline is done. At this point all streaming
    // tokens have already been forwarded to the channel worker. We send done=true
    // with an empty content string to close the stream — Telegram will do a final
    // flush/edit of the accumulated buffer.
    this.bus.on("turn:end", (e) => {
      const sid = (e as SessionEvent).sessionId
      if (!sid) return
      try {
        const s = this.sessions.get(sid)
        if (s?.channelId) {
          this.pluginHost.send(s.channelId, { sessionId: sid, content: '', done: true })
        }
      } catch (err) {
        this.logger.warn(`failed to finalize stream for ${sid}: ${String(err)}`)
      }
    })

    // ── Phase 1: Implicit Feedback Detection ───────────────────────────────
    // Detect feedback signals in every user message. Runs on turn:start so
    // that signals from the *previous* turn response are captured before the
    // current turn's context is assembled.
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

    // 8. Subscribe to plugin:crashed -> warn
    interface PluginCrashedEvent {
      pluginId: string
      error: string
    }
    this.bus.on("plugin:crashed", (e) => {
      const event = e as PluginCrashedEvent
      this.logger.warn(`plugin crashed: ${event.pluginId} — ${event.error}`)
    })

    // 9. Subscribe to plugin:restarted -> info
    interface PluginRestartedEvent {
      pluginId: string
      attempt: number
    }
    this.bus.on("plugin:restarted", (e) => {
      const event = e as PluginRestartedEvent
      this.logger.info(`plugin restarted: ${event.pluginId} (attempt ${event.attempt})`)
    })

    // 10. Subscribe to config:reloaded
    this.bus.on("config:reloaded", () => {
      this.logger.info("Config reloaded — no restart needed")
    })

    // 11. Start AdminAPI
    // ── Phase 6: Services ────────────────────────────────────────────────────
    this.logger.info('── Phase 6: Services ──────────────────────────────────')

    let adminInfo: { tcpPort: number | null; unixPath: string } | undefined = undefined
    try {
      const adminApi = createAdminApi(this, this.logger)
      adminInfo = await adminApi.start()
      this.logger.info(`AdminAPI listening on unix:${adminInfo?.unixPath} + http:${adminInfo?.tcpPort}`)
    } catch (err) {
      this.logger.warn(`AdminAPI failed to start: ${String(err)}`)
    }

    // 11b. Start Bridge (OpenAI-compatible API for OpenClaw integration)
    try {
      const bridgeSocketPath = this.config.get<string>('bridge.socketPath', path.join(homedir(), '.cassicore', 'bridge.sock'))
      const bridge = createBridge(providers, this.logger, { socketPath: bridgeSocketPath })
      await bridge.start()
      this.logger.info(`Bridge listening on unix:${bridgeSocketPath}`)
    } catch (err) {
      this.logger.warn(`Bridge failed to start: ${String(err)}`)
    }

    // 12. Set running
    this.running = true

    // 13. Emit daemon:ready — triggers optimizer loop start
    this.bus.emit({ type: "daemon:ready", startedAt: new Date() })

    // 14. Start health monitor (after daemon:ready so all subsystems are wired)
    this.healthMonitor.start()

    // 15. Log startup banner with boot timing
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
   * @returns Promise that resolves after shutdown
   */
  async stop(): Promise<void> {
    if (!this.running) return
    this.logger.info("Shutting down gracefully...")

    // emit shutdown — triggers optimizer loop stop
    this.bus.emit({ type: "daemon:shutdown", reason: "signal" })

    // stop health monitor
    try {
      this.healthMonitor?.stop()
    } catch { /* ignore */ }

    // stop background embedding worker
    try {
      this.bgEmbeddingWorker?.stop()
    } catch { /* ignore */ }

    // stop embedding stack child processes (llama.cpp + zerank)
    try {
      this.embeddingStackLauncher?.stop()
    } catch { /* ignore */ }

    // stop unified intelligence loop
    try {
      if (this.unifiedLoop) {
        await this.unifiedLoop.stop('daemon-shutdown')
      }
    } catch (err) {
      this.logger.warn(`Error stopping unified loop: ${String(err)}`)
    }

    // stop auto-discovered registry modules
    try {
      if (this.intelligence?.registry) {
        await this.intelligence.registry.stopAll()
      }
    } catch (err) {
      this.logger.warn(`Error stopping registry modules: ${String(err)}`)
    }

    // stop Thinker BaseCognitiveModule lifecycle
    interface ThinkerWithStop {
      stop?(): Promise<void> | void
    }
    try {
      const thinker = this.intelligence?.thinker as ThinkerWithStop | undefined
      await thinker?.stop?.()
    } catch (err) {
      this.logger.warn(`Error stopping Thinker: ${String(err)}`)
    }

    // shutdown session pipeline if active
    try {
      if (this.sessionPipeline) {
        await this.sessionPipeline.shutdown()
        this.logger.info('Session pipeline shut down')
      }
    } catch (err) {
        this.logger.warn(`Error shutting down session pipeline: ${String(err)}`)
    }

    // shutdown plugin host
    try {
      await this.pluginHost.shutdown()
    } catch (err) {
      this.logger.warn(`error shutting down plugins: ${String(err)}`)
    }

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
      // ignore
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

    // intelligence cleanup
    interface ModuleWithCleanup {
      cleanup?(): Promise<void> | void
    }
    try {
      for (const m of this.intelligence.all) {
        const mod = m as ModuleWithCleanup
        if (typeof mod.cleanup === "function") {
          await mod.cleanup()
        }
      }
    } catch (err) {
      this.logger.warn(`error during intelligence cleanup: ${String(err)}`)
    }

    // persist budget tracker state
    try {
      if (this.budgetTracker) {
        await this.budgetTracker.saveToDisk()
      }
    } catch (err) {
      this.logger.warn(`error saving budget state: ${String(err)}`)
    }

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
