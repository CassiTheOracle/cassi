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

    // 5. Global safety: log unhandled promise rejections to avoid daemon crash on library race conditions
    process.on('unhandledRejection', (reason) => {
      try { this.logger.warn('[daemon] unhandledRejection', { error: String(reason) }) } catch {}
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

      // ── Phase 3: Thinker Event Listeners ────────────────────────────────────
      // Listen for Thinker's proactive events
      ;(bus as any).on('thinker:inject-insight', (e: any) => {
        this.logger.info('[daemon] Thinker injecting insight', { urgency: e.urgency })
        // Store for next turn injection via pipeline
        if (e.insight && this.pipeline) {
          // This will be picked up by the turn pipeline
          ;(this.pipeline as any).pendingThinkerInsight = e.insight
        }
      })

      ;(bus as any).on('thinker:early-warning', (e: any) => {
        this.logger.warn('[daemon] Thinker early warning', { pattern: e.pattern })
        // Trigger optimizer early intervention
        if (this.intelligence?.optimizer) {
          ;(this.intelligence.optimizer as any).handleEarlyWarning?.(e)
        }
      })

      ;(bus as any).on('thinker:self-modified', (e: any) => {
        this.logger.info('[daemon] Thinker self-modified strategy', e.newStrategy)
      })

      ;(bus as any).on('thinker:swarm-deployed', (e: any) => {
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
    } catch (err) {
      this.logger.warn('[daemon] Providers not loaded — run Phase 3 providers build')
    }

    // Wire the default provider into the Thinker so it can make real calls
    if (this.intelligence?.thinker) {
      const defaultProviderId = this.config.get<string>('intelligence.defaultProvider', '') || 'kimi'
      const thinkerProvider = providers.get(defaultProviderId) ?? providers.values().next().value
      if (thinkerProvider) {
        ;(this.intelligence.thinker as any).setProvider(thinkerProvider)
        this.logger.info(`[daemon] Thinker provider wired: ${thinkerProvider.id}`)
      } else {
        this.logger.warn('[daemon] Thinker: no provider available — thinking cycles will be skipped')
      }
    }

    // Wire the provider into the DialecticSystem (Yang, Yin, Serenity)
    if (this.intelligence?.dialectic) {
      const dialecticProviderId = this.config.get<string>('intelligence.dialectic.provider', '') || 'pi-bridge'
      const dialecticProvider = providers.get(dialecticProviderId) ?? providers.get('pi-bridge') ?? providers.values().next().value
      if (dialecticProvider) {
        ;(this.intelligence.dialectic as any).setProvider(dialecticProvider)
        this.logger.info(`[daemon] Dialectic provider wired: ${dialecticProvider.id}`)
      } else {
        this.logger.warn('[daemon] Dialectic: no provider available — dialectic observations will be skipped')
      }
    }

    // Create sessions and turn pipeline
    const systemPrompt = buildSystemPrompt(this.logger)
    this.logger.info(`[daemon] System prompt built (${systemPrompt.length} chars)`)
    const sessionStore = SessionStore.open(this.logger)
    // Resolve default model: prefer intelligence config, fall back to kimi-k2-0711-preview
    const defaultProvider = this.config.get<string>('intelligence.defaultProvider', 'kimi-coding')
    const configuredModel = this.config.get<string>('intelligence.defaultModel', '')
    const defaultModel = configuredModel
      ? `${defaultProvider}/${configuredModel}`
      : `${defaultProvider}/k2p5`
    if (defaultModel) {
      this.logger.info(`[daemon] Default model: ${defaultModel}`)
    }
    // Resolve thinking level: prefer config override, fall back to 'high'
    const configuredThinking = this.config.get<string>('intelligence.thinking', 'high') as import('../types/runtime.js').ThinkingLevel
    this.logger.info(`[daemon] Thinking level: ${configuredThinking}`)
    this.sessions = createSessionManager(this.logger, systemPrompt, sessionStore, defaultModel, configuredThinking)

    // Build command dispatcher
    this.commands = new CommandDispatcher(this.logger, this.sessions, this.bus);

    // Build tool registry + executor
    const toolRegistry = new ToolRegistry()
    registerCoreTools(toolRegistry, {
      memory: this.intelligence?.memory,
      sessionManager: this.sessions,
      sessionStore: sessionStore,
      bus: this.bus,
      logger: this.logger,
      getPipeline: () => this.pipeline,
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
    })
    // Expose toolExecutor on the daemon instance so admin API and CLI can invoke tools
    ;(this as any).toolExecutor = toolExecutor
    this.logger.info(`[daemon] Tools loaded: ${toolRegistry.list().map(t => t.name).join(', ')}`)

    // Initialize MCP registry and connect configured servers
    let mcpRegistry: MCPRegistry | undefined
    const mcpConfigs = this.config.get<Array<{ id: string; command: string; args?: string[]; env?: Record<string, string>; restartOnCrash?: boolean; maxRestarts?: number; startupTimeoutMs?: number; description?: string }>>('mcp.servers', [])
    if (mcpConfigs.length > 0) {
      this.logger.info(`[daemon] Initializing MCP registry with ${mcpConfigs.length} server(s)`)
      mcpRegistry = new MCPRegistry(toolRegistry, this.logger)
      await mcpRegistry.start(mcpConfigs)
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
    
    // Wire dialectic system to pipeline for parallel processing
    if (this.intelligence?.dialectic) {
      this.pipeline.setDialectic(this.intelligence.dialectic)
    }

    // Mount intelligence middlewares — continuity only (thinker runs fire-and-forget via onTurnEnd)
    if (this.intelligence) {
      this.pipeline.mountIntelligence({
        continuity: this.intelligence.continuity as any,

      })

      // Wire optimizer to live session manager and pipeline — now it can actually work
      this.intelligence.optimizer.setSessions(this.sessions)
      this.intelligence.optimizer.setPipeline(this.pipeline)
      this.logger.info('[daemon] Optimizer wired to session manager and pipeline')
    }

    // ── Health Monitor ────────────────────────────────────────────────────────
    const healthIntervalMs = this.config.get<number>('health.intervalMs', 30_000)
    this.healthMonitor = new HealthMonitor(this.bus, this.logger, {
      intervalMs:  healthIntervalMs,
      historySize: 20,
      selfHeal:    true,
    })
    this.healthMonitor.wire({
      providers,
      pluginHost:   this.pluginHost as any,
      intelligence: this.intelligence as any,
      pipeline:     this.pipeline,
      sessions:     this.sessions as any,
      mcp:          mcpRegistry,
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
                // Stream thinking tokens to distinguish
                this.pluginHost.send(tgt, { sessionId: sid, content: `${payload.token as string}`, done: false })
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

          const { randomUUID } = await import('node:crypto')
          const inbound = {
            id: randomUUID(),
            sessionId: payload.sessionId as string,
            channelId: pluginId,
            senderId: payload.sessionId as string,
            content: (payload.content as string) || '(image)',
            attachments: payload.attachments as import('../types/runtime.js').ImageAttachment[] | undefined,
            timestamp: new Date(),
          }
          this.logger.info(`[daemon] Processing inbound message`, { channel: pluginId, sessionId: inbound.sessionId })

          // Process the turn — streaming tokens flow via bus → worker:message above.
          // We do NOT send the final response here; the turn:end handler does that
          // so the stream is finalized exactly once, after all tokens have been sent.
          try {
            await this.pipeline.process(inbound)
            this.logger.info(`[daemon] Turn complete`, { sessionId: inbound.sessionId })
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
    this.logger.info("║   CassiCore v0.1.0 — Ready       ║")
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
      ;(this.sessions as any).store?.close?.()
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
