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
  async start(): Promise<void> {
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

      this.logger.info(`[daemon] Intelligence layer loaded — ${this.intelligence.all.length} modules active`)
    } catch (err) {
      this.logger.warn(`failed to initialize intelligence layer: ${String(err)}`)
    }

    // 6. Load the echo-channel worker (phase 1)
    const __dirname = path.dirname(fileURLToPath(import.meta.url))
    const echoPath = path.resolve(__dirname, "../workers/echo-channel.js")

    if (!fs.existsSync(echoPath)) {
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
    const webchatPath = path.resolve(__dirname, "../workers/channels/webchat.js")
    if (!fs.existsSync(webchatPath)) {
      this.logger.warn("webchat worker not found; skipping")
    } else {
      try {
        const webchatPort = this.config.get<number>("channels.webchat.port", 3000)
        await this.pluginHost.load({
          id: "channel:webchat",
          entryPoint: webchatPath,
          restartOnCrash: true,
          maxRestarts: 5,
          config: { port: webchatPort },
        })
        this.logger.info(`[daemon] Webchat channel listening on port ${webchatPort}`)
      } catch (err) {
        this.logger.warn(`failed to load webchat: ${String(err)}`)
      }
    }

    // 7b. Load Telegram channel worker (optional — requires channels.telegram.token in config)
    const tgToken = this.config.get<string>("channels.telegram.token", "")
    if (tgToken) {
      const tgPath = path.resolve(__dirname, "../workers/channels/telegram.js")
      if (!fs.existsSync(tgPath)) {
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

    // Create sessions and turn pipeline
    const systemPrompt = buildSystemPrompt(this.logger)
    this.logger.info(`[daemon] System prompt built (${systemPrompt.length} chars)`)
    const sessionStore = SessionStore.open(this.logger)
    // Resolve default model: prefer intelligence config, fall back to kimi-k2-0711-preview
    const defaultProvider = this.config.get<string>('intelligence.defaultProvider', 'kimi')
    const configuredModel = this.config.get<string>('intelligence.defaultModel', '')
    const defaultModel = configuredModel
      ? `${defaultProvider}/${configuredModel}`
      : `${defaultProvider}/kimi-k2-0711-preview`
    if (defaultModel) {
      this.logger.info(`[daemon] Default model: ${defaultModel}`)
    }
    // Resolve thinking level: prefer config override, fall back to 'high'
    const configuredThinking = this.config.get<string>('intelligence.thinking', 'high') as import('../types/runtime.js').ThinkingLevel
    this.logger.info(`[daemon] Thinking level: ${configuredThinking}`)
    this.sessions = createSessionManager(this.logger, systemPrompt, sessionStore, defaultModel, configuredThinking)

    // Build tool registry + executor
    const toolRegistry = new ToolRegistry()
    registerCoreTools(toolRegistry, {
      memory: this.intelligence?.memory,
      sessionManager: this.sessions,
    })
    const allowedPaths = this.config.get<string[]>('tools.allowedPaths', [
      '/home/valerie/Workspaces',
      '/tmp/cassiecore',
    ])
    const networkAllowlist = this.config.get<string[]>('tools.networkAllowlist', ['*'])
    const toolExecutor = new ToolExecutor(toolRegistry, {
      workingDir: '/home/valerie/Workspaces',
      allowedPaths,
      networkAllowlist,
      logger: this.logger,
    })
    this.logger.info(`[daemon] Tools loaded: ${toolRegistry.list().map(t => t.name).join(', ')}`)

    // @ts-ignore - intelligence may be undefined in edge cases
    this.pipeline = new TurnPipeline(
      providers, this.sessions, this.bus, this.logger,
      this.intelligence?.memory,
      this.orchestration,
      toolRegistry,
      toolExecutor,
    )

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

              if (payload.type === 'turn:token' && payload.token) {
                // Stream token to channel — done=false keeps stream open
                this.pluginHost.send(tgt, { sessionId: sid, content: payload.token as string, done: false })
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
    try {
      const adminApi = createAdminApi(this, this.logger)
      await adminApi.start()
      this.logger.info('[daemon] AdminAPI listening on ~/.cassiecore/admin.sock + :7432')
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
    this.logger.info("║   CassieCore v0.1.0 — Ready       ║")
    this.logger.info("╚══════════════════════════════════╝")
    this.logger.info(`[daemon] ${loaded} plugin(s) loaded | hot-reload active | PID: ${pid}`)
  }

  /**
   * Load secrets from ~/.cassiecore/.env into process.env.
   * Keys are only set if not already present in the environment.
   * Safe to call multiple times. .env is optional — silently ignored if missing.
   */
  private async _loadEnv(): Promise<void> {
    const envPath = join(homedir(), '.cassiecore', '.env')
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
        this.logger.debug(`[daemon] Loaded ${loaded} secret(s) from .cassiecore/.env`)
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
