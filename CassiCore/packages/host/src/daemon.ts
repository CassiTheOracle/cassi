import { EventBus, bus } from "./event-bus.js"
import { Logger, rootLogger } from "./logger.js"
import { Config } from "./config.js"
import { PluginHost } from "./plugin-host.js"
import type { IEventBus, ILogger, IConfig, IPluginHost } from "../types/interfaces.js"
import path from "node:path"
import { fileURLToPath } from "node:url"
import fs from "node:fs"
import { createIntelligence } from "./intelligence/index.js"
import type { IntelligenceLayer } from "./intelligence/index.js"

export class Daemon {
  private bus: IEventBus
  private config!: IConfig
  private pluginHost!: IPluginHost
  private logger: ILogger
  private running = false
  private intelligence!: IntelligenceLayer

  constructor(busInstance: IEventBus = bus, logger: ILogger = rootLogger) {
    this.bus = busInstance
    this.logger = logger
  }

  /**
   * Start the daemon: load config, start plugin host, wire signals and workers.
   */
  async start(): Promise<void> {
    // 1. Load config
    this.config = await Config.load()

    // 2. Start config watcher
    try {
      this.config.watch()
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

      this.logger.info("[daemon] Intelligence layer loaded — 5 modules active")
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

    // 7. Subscribe to worker:message
    this.bus.on("worker:message", (e) => {
      // log any message received from workers
      this.logger.info(`[worker:${(e as any).pluginId}] ${(e as any).payload as string}`)
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

    // 11. Set running
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
