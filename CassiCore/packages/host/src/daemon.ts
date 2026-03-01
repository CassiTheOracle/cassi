import { EventBus, bus } from "./event-bus.js"
import { Logger, rootLogger } from "./logger.js"
import { Config } from "./config.js"
import { createLayeredConfig } from "./runtime-config.js"
import { PluginHost } from "./plugin-host.js"
import type { IEventBus, ILogger, IConfig, IPluginHost } from "../types/interfaces.js"
import path, { join } from "node:path"
import { homedir } from "node:os"
import { fileURLToPath } from "node:url"
import fs from "node:fs"
import { createIntelligence } from "./intelligence/index.js"
import type { IntelligenceLayer } from "./intelligence/index.js"

import { createOrchestrationBus } from './orchestration-bus.js'
import { createSessionBridge } from './session-bridge.js'
import { createAdminApi } from './admin-api.js'
import { createAgentRunner } from './intelligence/agent-runner.js'
import { createSubagentTracker, type SubagentTracker } from './subagent-tracker.js'

import { createSessionManager } from './session-manager.js'
import { SessionStore } from './session-store.js'
import { TurnPipeline } from './turn-pipeline.js'
import type { IProvider } from '../types/runtime.js'
import { ToolRegistry } from './tools/registry.js'
import { ToolExecutor } from './tools/executor.js'
import { registerCoreTools } from './tools/implementations/index.js'
import { buildSystemPrompt } from './workspace/loader.js'
import { HealthMonitor } from './health-monitor.js'
import { MCPRegistry } from './mcp/registry.js'
import { CommandDispatcher } from './commands.js'
import { createBridge } from './bridge.js'
import { createSkillMetricsTracker, SkillMetricsTracker } from './intelligence/skill-metrics.js'
import { initContextWindowDebugger, ContextWindowDebugger } from './events/context-window-debug.js'
import { setContextWindowDebugger, contextWindowDebugMiddleware } from './turn-pipeline.js'

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
  // expose orchestration bus for external use
  public orchestration?: ReturnType<typeof createOrchestrationBus>

  constructor(busInstance: IEventBus = bus, logger: ILogger = rootLogger) {
    this.bus = busInstance
    this.logger = logger
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
   * Start the daemon: load config, start plugin host, wire signals and workers.
   */
  async start(): Promise<{ admin?: { tcpPort: number | null; unixPath: string }; pid: number }> {
    // 0. Load .env secrets (before anything reads env vars)
    await this._loadEnv()

    // 0b. Check for existing daemon instance (singleton enforcement)
    const existingPid = checkExistingDaemon()
    if (existingPid !== null) {
      const errorMsg = `Another CassiCore daemon is already running (PID: ${existingPid}). Please stop it first or use: kill ${existingPid}`
      console.error(`\n❌ ${errorMsg}\n`)
      this.logger.error(errorMsg)
      process.exit(1)
    }

    // Write our PID to the lock file
    writePidFile()
    this.logger.info(`[daemon] PID file written: ${process.pid}`)

    // Register cleanup on exit
    process.on('exit', cleanupPidFile)
    process.on('SIGTERM', cleanupPidFile)
    process.on('SIGINT', cleanupPidFile)
    process.on('uncaughtException', cleanupPidFile)

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
        this.logger.warn?.('[daemon] process.stdin error', { error: String(err) })
      })
    }

    // 5. Global safety: log unhandled promise rejections to avoid daemon crash on library race conditions
    process.on('unhandledRejection', (reason, _promise) => {
      try {
        let errMsg = String(reason)
        try {
          if (reason && typeof reason === 'object') {
            errMsg = (reason as any).stack || (reason as any).message || String(reason)
          }
        } catch { }
        // Treat plain timeouts as lower-severity (they are common with provider/polling cancellations)
        if (String(errMsg).toLowerCase().includes('timeout')) {
          this.logger.debug?.('[daemon] unhandledRejection (timeout)', { error: errMsg })
        } else {
          this.logger.warn?.('[daemon] unhandledRejection', { error: errMsg })
        }
      } catch { }
    })

    // Handle unhandled child process errors to prevent daemon crashes
    process.on('uncaughtException', (error) => {
      if (error && (error as any).code === 'ENOENT' && (error as any).syscall?.includes('spawn')) {
        // Shell command failed - log but don't crash
        this.logger.error?.('[daemon] shell command failed', {
          syscall: (error as any).syscall,
          path: (error as any).path,
          message: error.message
        })
        // Don't exit - just log the error
        return
      }
      // For other uncaught exceptions, log and continue if possible
      this.logger.error?.('[daemon] uncaughtException', { error: error.message, stack: error.stack })
    })

    // 5. Create PluginHost with logger
    this.pluginHost = new PluginHost(this.logger)

    // Initialize intelligence layer before loading plugins
    try {
      this.intelligence = createIntelligence(this.logger, this.config)

      // Wire modules to event bus
      const bus = this.bus
      bus.on("turn:start", (e) => {
        void (this.intelligence.memory as any).onEvent?.(e)
      })

      bus.on("turn:end", (e) => {
        void (this.intelligence.memory as any).onEvent?.(e)
        void (this.intelligence.continuity as any).onEvent?.(e)
        void (this.intelligence.thinker as any).onEvent?.(e)
      })

      bus.on("plugin:crashed", (e) => {
        void (this.intelligence.recover as any).onEvent?.(e)
        void (this.intelligence.reflect as any).onEvent?.(e)
      })

      // Optimizer listens for daemon:ready (starts loop) and daemon:shutdown (stops loop)
      bus.on("daemon:ready", (e) => {
        void (this.intelligence.optimizer as any).onEvent?.(e)
      })
      bus.on("daemon:shutdown", (e) => {
        void (this.intelligence.optimizer as any).onEvent?.(e)
      })

      // Wire DialecticSystem to event bus for streaming
      if ((this.intelligence.dialectic as any)?.onEventBus) {
        (this.intelligence.dialectic as any).onEventBus(bus)
      }

      // Wire Thinker to event bus for proactive triggers
      if ((this.intelligence.thinker as any)?.onEventBus) {
        (this.intelligence.thinker as any).onEventBus(bus)
      }

      // Wire AI Scientist to event bus for metrics collection
      if ((this.intelligence.aiScientist as any)?.onEventBus) {
        (this.intelligence.aiScientist as any).onEventBus(bus)
      }

      // Start AI Scientist monitoring
      if ((this.intelligence.aiScientist as any)?.start) {
        (this.intelligence.aiScientist as any).start()
      }

      // Initialize and start Unified Intelligence Loop
      try {
        const { createUnifiedIntelligenceLoop } = await import('./intelligence/unified-loop.js')
        const unifiedLoop = createUnifiedIntelligenceLoop(
          this.logger.child('unified-loop'),
          this.bus,
          {
            enabled: this.config.get<boolean>('intelligence.unifiedLoop.enabled', true),
            backgroundIntervalMs: this.config.get<number>('intelligence.unifiedLoop.backgroundIntervalMs', 60000),
          }
        )

        await unifiedLoop.start()
        this.logger.info('[daemon] Unified Intelligence Loop started')
      } catch (err) {
        this.logger.warn('[daemon] Failed to initialize Unified Intelligence Loop', { error: String(err) })
      }

      // Wire Subconscious to event bus for background consolidation
      if ((this.intelligence.subconscious as any)?.onEventBus) {
        (this.intelligence.subconscious as any).onEventBus(bus)
      }
      if ((this.intelligence.subconscious as any)?.start) {
        (this.intelligence.subconscious as any).start()
      }

      // Wire Multi-Agent Coordinator to event bus
      if ((this.intelligence.multiAgent as any)?.onEventBus) {
        (this.intelligence.multiAgent as any).onEventBus(bus)
      }

      // Wire Rule Enforcer to event bus
      if ((this.intelligence.ruleEnforcer as any)?.onEventBus) {
        (this.intelligence.ruleEnforcer as any).onEventBus(bus)
      }

      // Initialize Skill Metrics Tracker
      try {
        this.skillMetricsTracker = createSkillMetricsTracker(this.logger.child('skill-metrics'), bus)
        await this.skillMetricsTracker.initialize()
        this.logger.info('[daemon] Skill Metrics Tracker initialized')
      } catch (err) {
        this.logger.warn(`[daemon] Failed to initialize Skill Metrics Tracker: ${String(err)}`)
      }

      // ── Phase 3: Thinker Event Listeners ────────────────────────────────────
      // Listen for Thinker's proactive events
      ; (bus as any).on('thinker:inject-insight', (e: any) => {
        this.logger.info('[daemon] Thinker injecting insight', { urgency: e.urgency })
        // Store for next turn injection via pipeline
        if (e.insight && this.pipeline) {
          // This will be picked up by the turn pipeline
          ; (this.pipeline as any).pendingThinkerInsight = e.insight
        }
      })

        ; (bus as any).on('thinker:early-warning', (e: any) => {
          this.logger.warn('[daemon] Thinker early warning', { pattern: e.pattern })
          // Trigger optimizer early intervention
          if (this.intelligence?.optimizer) {
            ; (this.intelligence.optimizer as any).handleEarlyWarning?.(e)
          }
        })

        ; (bus as any).on('thinker:self-modified', (e: any) => {
          this.logger.info('[daemon] Thinker self-modified strategy', e.newStrategy)
        })

        ; (bus as any).on('thinker:swarm-deployed', (e: any) => {
          this.logger.info('[daemon] Thinker deployed swarm', { agents: e.agentsDeployed, roles: e.roles })
        })

      this.logger.info(`[daemon] Intelligence layer loaded — ${this.intelligence.all.length} modules active`)
    } catch (err) {
      this.logger.warn(`failed to initialize intelligence layer: ${String(err)}`)
    }

    // Helper to resolve worker path (handles both .js and .ts)
    const __dirname = path.dirname(fileURLToPath(import.meta.url))
    const resolveWorker = (relPath: string): string | null => {
      const jsPath = path.resolve(__dirname, relPath + '.js')
      if (fs.existsSync(jsPath)) return jsPath
      const tsPath = path.resolve(__dirname, relPath + '.ts')
      if (fs.existsSync(tsPath)) return tsPath
      return null
    }

    // 6. Load the echo-channel worker (phase 1)
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
        this.logger.info(`[daemon] webchat.enabled -> ${enabled}`)
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
          this.logger.info(`[daemon] Webchat channel listening on port ${webchatPort}`);
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
        this.logger.info(`[daemon] CLI channel active`)
      } catch (err) {
        this.logger.warn(`failed to load cli channel: ${String(err)}`)
      }
    }

    // 7c. Load Telegram channel worker (optional — requires channels.telegram.token in config)
    const tgEnabled = this.config.get<boolean>("channels.telegram.enabled", false)
    const tgToken = this.config.get<string>("channels.telegram.token", "")
    if (tgEnabled && tgToken) {
      const tgPath = resolveWorker("../workers/channels/telegram")
      if (!tgPath) {
        this.logger.warn("telegram worker not found; skipping")
      } else {
        try {
          const allowedChatIds = this.config.get<number[]>("channels.telegram.allowedChatIds", [])
          await this.pluginHost.load({
            id: "channel:telegram",
            entryPoint: tgPath,
            restartOnCrash: true,
            maxRestarts: 5,
            config: { token: tgToken, allowedChatIds },
          })
          this.logger.info(`[daemon] Telegram channel active`)
        } catch (err) {
          this.logger.warn(`failed to load telegram: ${String(err)}`)
        }
      }
    } else if (tgToken && !tgEnabled) {
      this.logger.info(`[daemon] Telegram channel disabled by config; skipping`)
    }
    let providers: Map<string, IProvider> = new Map()
    try {
      const { createProviders } = await import('./providers/index.js')
      providers = createProviders(this.config, this.logger, {
        centralized: true,
        bus: this.bus,
      })
        // Store providers on daemon instance for admin API access
        ; (this as any).providers = providers
    } catch (err) {
      this.logger.warn('[daemon] Providers not loaded — run Phase 3 providers build')
    }

    // Wire provider map into Multi-Agent Coordinator so providerId hints can be resolved
    try {
      if (this.intelligence?.multiAgent && typeof (this.intelligence.multiAgent as any).setProviders === 'function') {
        (this.intelligence.multiAgent as any).setProviders(providers)
        this.logger.info('[daemon] Multi-Agent providers wired')
      }
    } catch (e) {
      this.logger.warn('[daemon] failed to wire providers to multi-agent', { error: String(e) })
    }

    // Wire the default provider into the Thinker so it can make real calls
    if (this.intelligence?.thinker) {
      const defaultProviderId = this.config.get<string>('intelligence.defaultProvider', '') || 'lmstudio'
      const thinkerProvider = providers.get(defaultProviderId) ?? providers.values().next().value
      if (thinkerProvider) {
        ; (this.intelligence.thinker as any).setProvider(thinkerProvider)
        this.logger.info(`[daemon] Thinker provider wired: ${thinkerProvider.id}`)
      } else {
        this.logger.warn('[daemon] Thinker: no provider available — thinking cycles will be skipped')
      }
    }

    // Wire the provider into the DialecticSystem (Yang, Yin, Serenity)
    if (this.intelligence?.dialectic) {
      const dialecticProviderId = this.config.get<string>('intelligence.dialectic.provider', '') || 'lmstudio'
      const dialecticProvider = providers.get(dialecticProviderId) ?? providers.get('lmstudio') ?? providers.values().next().value
      if (dialecticProvider) {
        ; (this.intelligence.dialectic as any).setProvider(dialecticProvider)
        this.logger.info(`[daemon] Dialectic provider wired: ${dialecticProvider.id}`)

        // Wire provider to Subconscious. Prefer a dedicated subconscious provider if configured,
        // otherwise fall back to the dialectic provider.
        try {
          const subconsciousProviderId = this.config.get<string>('intelligence.subconscious.provider', '') || ''
          const subconsciousProvider = subconsciousProviderId ? (providers.get(subconsciousProviderId) ?? providers.get(subconsciousProviderId)) : dialecticProvider
          if (subconsciousProvider && (this.intelligence.subconscious as any) && typeof (this.intelligence.subconscious as any).setProvider === 'function') {
            (this.intelligence.subconscious as any).setProvider(subconsciousProvider)
            this.logger.info(`[daemon] Subconscious provider wired: ${subconsciousProvider.id}`)
          }
        } catch (err) {
          this.logger.warn('[daemon] Subconscious: failed to wire provider', { error: String(err) })
        }
      } else {
        this.logger.warn('[daemon] Dialectic: no provider available — dialectic observations will be skipped')
      }
    }

    // Create sessions and turn pipeline
    const systemPrompt = buildSystemPrompt(this.logger)
    this.logger.info(`[daemon] System prompt built (${systemPrompt.length} chars)`)
    const sessionStore = SessionStore.open(this.logger)
    const defaultProvider = this.config.get<string>('intelligence.defaultProvider', 'kimi-coding')
    const configuredModel = this.config.get<string>('intelligence.defaultModel', 'kimi-k2p5')
    const defaultModel = configuredModel
      ? `${defaultProvider}/${configuredModel}`
      : `${defaultProvider}/kimi-k2p5`
    if (defaultModel) {
      this.logger.info(`[daemon] Default model: ${defaultModel}`)
    }
    // Resolve thinking level: prefer config override, fall back to 'high'
    const configuredThinking = this.config.get<string>('intelligence.thinking', 'high') as import('../types/runtime.js').ThinkingLevel
    this.logger.info(`[daemon] Thinking level: ${configuredThinking}`)
    this.sessions = createSessionManager(this.logger, systemPrompt, sessionStore, defaultModel, configuredThinking)

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
      this.logger.info('[daemon] subagent-tracker started')
    } catch (err) {
      this.logger.warn('[daemon] failed to start subagent-tracker', { error: String(err) })
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
    })
    const allowedPaths = this.config.get<string[]>('tools.allowedPaths', [
      join(homedir(), 'workspaces'),
      join(homedir(), '.cassicore'),
      '/tmp/cassicore',
    ])
    const networkAllowlist = this.config.get<string[]>('tools.networkAllowlist', ['*'])
    const toolExecutor = new ToolExecutor(toolRegistry, {
      workingDir: join(homedir(), 'workspaces'),
      allowedPaths,
      networkAllowlist,
      logger: this.logger,
    }, this.bus)
      // Expose toolExecutor on the daemon instance so admin API and CLI can invoke tools
      ; (this as any).toolExecutor = toolExecutor
    this.logger.info(`[daemon] Tools loaded: ${toolRegistry.list().map(t => t.name).join(', ')}`)

    // Start a local agent-runner to execute agent:task-assigned events (spawn_subagent)
    try {
      const agentRunner = createAgentRunner(this.logger.child('agent-runner'), this.bus, this.intelligence?.multiAgent as any, toolRegistry, this.sessions);
      (this as any).agentRunner = agentRunner;
      agentRunner.start();
      this.logger.info('[daemon] agent-runner started');
    } catch (err) {
      this.logger.warn('[daemon] failed to start agent-runner', { error: String(err) });
    }

    // Initialize MCP registry and connect configured servers
    let mcpRegistry: MCPRegistry | undefined
    const mcpConfigs = this.config.get<Array<{ id: string; command: string; args?: string[]; env?: Record<string, string>; restartOnCrash?: boolean; maxRestarts?: number; startupTimeoutMs?: number; description?: string }>>('mcp.servers', [])
    if (mcpConfigs.length > 0) {
      this.logger.info(`[daemon] Initializing MCP registry with ${mcpConfigs.length} server(s)`)
      mcpRegistry = new MCPRegistry(toolRegistry, this.logger)
      await mcpRegistry.start(mcpConfigs)

      // Inform the Multi-Agent coordinator about available tools so agents can
      // automatically include dynamic MCP tool instructions in their prompts.
      try {
        if (this.intelligence?.multiAgent && typeof (this.intelligence.multiAgent as any).setToolRegistry === 'function') {
          (this.intelligence.multiAgent as any).setToolRegistry(toolRegistry)
          this.logger.info('[daemon] Connected ToolRegistry to Multi-Agent Coordinator')
        }
      } catch (e) {
        this.logger.warn('[daemon] Failed to wire ToolRegistry to Multi-Agent Coordinator', { error: String(e) })
      }
    } else {
      this.logger.info('[daemon] No MCP servers configured')
    }

    // @ts-ignore - intelligence may be undefined in edge cases
    this.pipeline = new TurnPipeline(
      providers, this.sessions, this.bus, this.logger,
      this.intelligence?.memory,
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
        this.logger.info('[daemon] Context window debugging enabled')
      }
    } catch (err) {
      this.logger.warn('[daemon] Failed to initialize context window debugger', { error: String(err) })
    }

    // Wire dialectic system to pipeline for parallel processing
    if (this.intelligence?.dialectic) {
      this.pipeline.setDialectic(this.intelligence.dialectic)
    }

    // Wire subconscious system to pipeline for automatic context retrieval
    if (this.intelligence?.subconscious) {
      this.pipeline.setSubconscious(this.intelligence.subconscious)
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
            this.logger.info('[daemon] ContextManager wired to session manager and pipeline')
          } catch (err) {
            this.logger.warn('[daemon] ContextManager: failed to start sync', { error: String(err) })
          }
        }
      } catch (err) {
        this.logger.warn('[daemon] failed to wire context manager', { error: String(err) })
      }

      // Wire optimizer to live session manager and pipeline — now it can actually work
      this.intelligence.optimizer.setSessions(this.sessions)
      this.intelligence.optimizer.setPipeline(this.pipeline)
      this.logger.info('[daemon] Optimizer wired to session manager and pipeline')

      // Wire Thinker's session manager and pipeline getter for unified subagent spawning
      if ((this.intelligence.thinker as any)?.__awaitingWiring) {
        (this.intelligence.thinker as any).__awaitingWiring.setSessionManager(this.sessions, sessionStore)
          ; (this.intelligence.thinker as any).__awaitingWiring.setPipelineGetter(() => this.pipeline)
        this.logger.info('[daemon] Thinker wired to session manager and pipeline for subagent spawning')
      }
    }

    // ── V2 Session Flow Integration ───────────────────────────────────────────
    // Initialize V2 if enabled via config (features.v2sessionFlow)
    let v2Integration: any = undefined
    try {
      const v2Enabled = this.config.get<boolean>('features.v2sessionFlow', false)
      if (v2Enabled) {
        const { initializeV2 } = await import('./daemon-v2-integration.js')
        v2Integration = await initializeV2(this, this.config, this.logger)
        if (v2Integration) {
          this.logger.info('[daemon] V2 session flow initialized - handling 100% traffic')
          // Store on daemon for admin-api access
          ;(this as any).v2 = v2Integration
          ;(this as any).useV2 = true
        }
      }
    } catch (err) {
      this.logger.warn('[daemon] Failed to initialize V2 session flow', { error: String(err) })
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
      pluginHost: this.pluginHost as any,
      intelligence: this.intelligence as any,
      pipeline: this.pipeline,
      sessions: this.sessions as any,
      mcp: mcpRegistry,
    })

    // 7. Subscribe to worker:message
    this.bus.on("worker:message", async (e) => {
      // log any message received from workers
      this.logger.debug(`[worker:${(e as any).pluginId}]`, { payload: (e as any).payload })

      try {
        const pluginId = (e as any).pluginId as string
        const payload = (e as any).payload as Record<string, unknown>

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
          const modelFromPayload = (payload as any).model
          if (modelFromPayload && pluginId === 'channel:cli') {
            const session = this.sessions.get(inbound.sessionId)
            if (session) {
              session.config.model = modelFromPayload
            }
          }

          this.logger.info(`[daemon] Processing inbound message`, { channel: pluginId, sessionId: inbound.sessionId, model: modelFromPayload, v2: !!(this as any).useV2 })

          // Process the turn — use V2 if enabled, otherwise fall back to V1 pipeline
          try {
            if ((this as any).useV2 && (this as any).v2) {
              // V2 path: simplified session flow
              const result = await (this as any).v2.processMessage(
                inbound.channelId,
                inbound.senderId,
                inbound.content,
                { attachments: inbound.attachments }
              )
              this.logger.info(`[daemon] V2 turn complete`, { sessionId: result.sessionId })
              // Send final response via plugin host (V2 doesn't use bus events for completion)
              this.pluginHost.send(pluginId, {
                sessionId: result.sessionId,
                content: result.response,
                done: true,
              })
            } else {
              // V1 path: traditional pipeline with streaming via bus
              await this.pipeline.process(inbound)
              this.logger.info(`[daemon] V1 turn complete`, { sessionId: inbound.sessionId })
            }
          } catch (err) {
            this.logger.warn(`[daemon] pipeline error: ${String(err)}`)
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
    this.bus.on("session:compacted", (e: any) => {
      const { sessionId, summary } = e
      const s = this.sessions.get(sessionId)
      if (s?.channelId) {
        this.pluginHost.send(s.channelId, {
          type: 'status',
          payload: { sessionId, text: 'Context compacted to focus on recent goals.', type: 'compaction' }
        })
      }
    })

    this.bus.on("context-manager:sync", (e: any) => {
      const { sessionId } = e
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
      const sid = (e as any).sessionId as string | undefined
      if (!sid) return
      try {
        const s = this.sessions.get(sid)
        if (s?.channelId) {
          this.pluginHost.send(s.channelId, { sessionId: sid, content: '', done: true })
        }
      } catch (err) {
        this.logger.warn(`[daemon] failed to finalize stream for ${sid}: ${String(err)}`)
      }
    })

    // 8. Subscribe to plugin:crashed -> warn
    this.bus.on("plugin:crashed", (e) => {
      this.logger.warn(`plugin crashed: ${(e as any).pluginId} — ${(e as any).error}`)
    })

    // 9. Subscribe to plugin:restarted -> info
    this.bus.on("plugin:restarted", (e) => {
      this.logger.info(`plugin restarted: ${(e as any).pluginId} (attempt ${(e as any).attempt})`)
    })

    // 10. Subscribe to config:reloaded
    this.bus.on("config:reloaded", () => {
      this.logger.info("Config reloaded — no restart needed")
    })

    // 11. Start AdminAPI
    let adminInfo: { tcpPort: number | null; unixPath: string } | undefined = undefined
    try {
      const adminApi = createAdminApi(this, this.logger)
      adminInfo = await adminApi.start()
      this.logger.info(`[daemon] AdminAPI listening on unix:${adminInfo?.unixPath} + http:${adminInfo?.tcpPort}`)
    } catch (err) {
      this.logger.warn(`AdminAPI failed to start: ${String(err)}`)
    }

    // 11b. Start Bridge (OpenAI-compatible API for OpenClaw integration)
    try {
      const bridgeSocketPath = this.config.get<string>('bridge.socketPath', path.join(homedir(), '.cassicore', 'bridge.sock'))
      const bridge = createBridge(providers, this.logger, { socketPath: bridgeSocketPath })
      await bridge.start()
      this.logger.info(`[daemon] Bridge listening on unix:${bridgeSocketPath}`)
    } catch (err) {
      this.logger.warn(`[daemon] Bridge failed to start: ${String(err)}`)
    }

    // 12. Set running
    this.running = true

    // 13. Emit daemon:ready — triggers optimizer loop start
    this.bus.emit({ type: "daemon:ready", startedAt: new Date() })

    // 14. Start health monitor (after daemon:ready so all subsystems are wired)
    this.healthMonitor.start()

    // 15. Log startup banner
    const loaded = this.pluginHost.all().length
    const pid = process.pid
    this.logger.info("╔══════════════════════════════════╗")
    this.logger.info("║   CassiCore v0.1.2 — Ready       ║")
    this.logger.info("╚══════════════════════════════════╝")
    this.logger.info(`[daemon] ${loaded} plugin(s) loaded | hot-reload active | PID: ${pid}`)

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
        this.logger.debug(`[daemon] Loaded ${loaded} secret(s) from .cassicore/.env`)
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

    // stop unified intelligence loop
    try {
      // Note: unified loop is a singleton per process, we just emit the shutdown event
      this.bus.emit({ type: 'unified-loop:stop' as any })
    } catch { /* ignore */ }

    // shutdown plugin host
    try {
      await this.pluginHost.shutdown()
    } catch (err) {
      this.logger.warn(`error shutting down plugins: ${String(err)}`)
    }

    // attempt to stop config watcher if possible
    try {
      if (typeof (this.config as any).watcher?.close === "function") {
        (this.config as any).watcher.close()
      }
    } catch {
      // ignore
    }

    // close session store
    try {
      ; (this.sessions as any).store?.close?.()
    } catch { /* ignore */ }

    // intelligence cleanup
    try {
      for (const m of this.intelligence.all) {
        if (typeof (m as any).cleanup === "function") {
          await (m as any).cleanup()
        }
      }
    } catch (err) {
      this.logger.warn(`error during intelligence cleanup: ${String(err)}`)
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

      const defaultModel = this.config.get<string>('intelligence.defaultModel', 'github-copilot/gpt-5-mini')
      const thinking = this.config.get<string>('intelligence.thinking', 'high')
      this.sessions.setDefaultConfig({ model: defaultModel, thinking: thinking as any })
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
