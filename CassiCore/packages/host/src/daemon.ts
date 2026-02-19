import { EventBus, bus } from "./event-bus.js"
import { Logger, rootLogger } from "./logger.js"
import { Config } from "./config.js"
import { createLayeredConfig } from "./runtime-config.js"
import { PluginHost } from "./plugin-host.js"
import type { IEventBus, ILogger, IConfig, IPluginHost } from "../types/interfaces.js"
import path from "node:path"
import { fileURLToPath } from "node:url"
import fs from "node:fs"
import { createIntelligence } from "./intelligence/index.js"
import type { IntelligenceLayer } from "./intelligence/index.js"

import { createOrchestrationBus } from './orchestration-bus.js'
import { createSessionBridge } from './session-bridge.js'
import { createAdminApi } from './admin-api.js'

import { createSessionManager } from './session-manager.js'
import { TurnPipeline } from './turn-pipeline.js'
import type { IProvider } from '../types/runtime.js'
import { ToolRegistry } from './tools/registry.js'
import { ToolExecutor } from './tools/executor.js'
import { registerCoreTools } from './tools/implementations/index.js'
import { buildSystemPrompt } from './workspace/loader.js'

export class Daemon {
  private bus: IEventBus
  private config!: IConfig
  private pluginHost!: IPluginHost
  private logger: ILogger
  private running = false
  private intelligence!: IntelligenceLayer
  private sessions!: ReturnType<typeof createSessionManager>
  private pipeline!: TurnPipeline
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
      this.intelligence = createIntelligence(this.logger)

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
      providers = createProviders(this.config, this.logger)
    } catch (err) {
      this.logger.warn('[daemon] Providers not loaded — run Phase 3 providers build')
    }

    // Create sessions and turn pipeline
    const systemPrompt = buildSystemPrompt(this.logger)
    this.logger.info(`[daemon] System prompt built (${systemPrompt.length} chars)`)
    this.sessions = createSessionManager(this.logger, systemPrompt)

    // Build tool registry + executor
    const toolRegistry = new ToolRegistry()
    registerCoreTools(toolRegistry, {
      memory: this.intelligence?.memory,
      sessionManager: this.sessions,
    })
    const allowedPaths = this.config.get<string[]>('tools.allowedPaths', [
      '/home/valerie/Workspaces',
      '/tmp/claracore',
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

    // Mount intelligence middlewares (continuity + thinker injection)
    if (this.intelligence) {
      this.pipeline.mountIntelligence({
        continuity: this.intelligence.continuity as any,
        thinker: this.intelligence.thinker as any,
      })
    }

    // 7. Subscribe to worker:message
    this.bus.on("worker:message", async (e) => {
      // log any message received from workers
      this.logger.debug(`[worker:${(e as any).pluginId}]`, { payload: (e as any).payload })

      try {
        const pluginId = (e as any).pluginId as string
        const payload = (e as any).payload as Record<string, unknown>

        // Route worker log messages to daemon logger
        if (payload?.type === 'log') {
          const level = (payload.level as string) || 'info'
          const msg = (payload.message as string) || ''
          if (level === 'error') this.logger.error(msg)
          else if (level === 'warn') this.logger.warn(msg)
          else this.logger.info(msg)
          return
        }

        if (pluginId?.startsWith("channel:") && payload?.sessionId && payload?.content && payload?.sessionId !== "system") {
          // Build a proper InboundMessage from channel payload
          const { randomUUID } = await import('node:crypto')
          const inbound = {
            id: randomUUID(),
            sessionId: payload.sessionId as string,
            channelId: pluginId,
            senderId: payload.sessionId as string,
            content: payload.content as string,
            timestamp: new Date(),
          }
          this.logger.info(`[daemon] Processing inbound message`, { channel: pluginId, sessionId: inbound.sessionId })
          const result = await this.pipeline.process(inbound)
          this.logger.info(`[daemon] Response generated`, { tokens: result.tokensUsed, model: result.model })
          this.pluginHost.send(pluginId, {
            sessionId: inbound.sessionId,
            content: result.response,
            done: true,
          })
        }
      } catch (err) {
        this.logger.warn(`error processing inbound message: ${String(err)}`)
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
      this.logger.info('[daemon] AdminAPI listening on ~/.claracore/admin.sock + :7432')
    } catch (err) {
      this.logger.warn(`AdminAPI failed to start: ${String(err)}`)
    }

    // 12. Set running
    this.running = true

    // 12. Emit daemon:ready
    this.bus.emit({ type: "daemon:ready", startedAt: new Date() })

    // 13. Log startup banner
    const loaded = this.pluginHost.all().length
    const pid = process.pid
    this.logger.info("╔══════════════════════════════════╗")
    this.logger.info("║   ClaraCore v0.1.0 — Ready       ║")
    this.logger.info("╚══════════════════════════════════╝")
    this.logger.info(`[daemon] ${loaded} plugin(s) loaded | hot-reload active | PID: ${pid}`)
  }

  /**
   * Stop the daemon gracefully.
   * @returns Promise that resolves after shutdown
   */
  async stop(): Promise<void> {
    if (!this.running) return
    this.logger.info("Shutting down gracefully...")

    // emit shutdown
    this.bus.emit({ type: "daemon:shutdown", reason: "signal" })

    // shutdown plugin host
    try {
      await this.pluginHost.shutdown()
    } catch (err) {
      this.logger.warn(`error shutting down plugins: ${String(err)}`)
    }

    // attempt to stop config watcher if possible
    try {
      // Config implementation doesn't expose explicit stop; try to access watcher via casting
      if (typeof (this.config as any).watcher?.close === "function") {
        (this.config as any).watcher.close()
      }
    } catch {
      // ignore
    }

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
    // exit
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

    // For each loaded plugin, read new config and update if changed
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
