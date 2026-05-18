/**
 * CopilotClient lifecycle manager.
 *
 * Manages the Copilot CLI server process via the @github/copilot-sdk.
 * Handles start/stop, auth, auto-restart on crash, and health checking.
 */
import { CopilotClient, approveAll } from '@github/copilot-sdk'
import type { CopilotClientOptions, ConnectionState, ModelInfo } from '@github/copilot-sdk'

import type { ILogger } from '../../../types/interfaces.js'

export interface CopilotSdkManagerOptions {
  /** GitHub OAuth token (from device flow / config) */
  githubToken?: string
  /** Path to `copilot` CLI binary (default: searches PATH) */
  cliPath?: string
  /** Working directory for the CLI process */
  cwd?: string
  /** Log level for the CLI server */
  logLevel?: 'none' | 'error' | 'warning' | 'info' | 'debug' | 'all'
  /** Auto-restart the CLI if it crashes (default: true) */
  autoRestart?: boolean
}

export class CopilotSdkManager {
  private client: CopilotClient | null = null
  private logger: ILogger
  private options: CopilotSdkManagerOptions
  private running = false
  private modelsCache: ModelInfo[] | null = null

  constructor(logger: ILogger, options: CopilotSdkManagerOptions = {}) {
    this.logger = logger.child('copilot-sdk')
    this.options = options
  }

  /**
   * Start the CopilotClient — spawns the Copilot CLI in server mode.
   */
  async start(): Promise<void> {
    if (this.running && this.client) {
      this.logger.warn('CopilotSdkManager already running')
      return
    }

    const clientOpts: CopilotClientOptions = {
      useStdio: true,
      autoStart: true,
      autoRestart: this.options.autoRestart ?? true,
      logLevel: this.options.logLevel ?? 'warning',
    }

    if (this.options.cliPath) {
      clientOpts.cliPath = this.options.cliPath
    }
    if (this.options.cwd) {
      clientOpts.cwd = this.options.cwd
    }
    if (this.options.githubToken) {
      clientOpts.githubToken = this.options.githubToken
      clientOpts.useLoggedInUser = false
    } else {
      clientOpts.useLoggedInUser = true
    }

    this.client = new CopilotClient(clientOpts)

    try {
      await this.client.start()
      this.running = true
      this.logger.info('Copilot CLI server started')

      // Verify auth
      try {
        const authStatus = await this.client.getAuthStatus()
        if (authStatus.isAuthenticated) {
          this.logger.info(`Copilot auth OK: ${authStatus.authType} (${authStatus.login ?? 'unknown'})`)
        } else {
          this.logger.warn('Copilot CLI started but not authenticated — run `copilot login`')
        }
      } catch (err) {
        this.logger.warn(`Could not check auth status: ${String(err)}`)
      }
    } catch (err) {
      this.client = null
      this.running = false
      throw new Error(`Failed to start Copilot CLI: ${String(err)}`)
    }
  }

  /**
   * Stop the CopilotClient — shuts down the CLI server process.
   */
  async stop(): Promise<void> {
    if (!this.client) return

    try {
      const errors = await this.client.stop()
      if (errors.length > 0) {
        this.logger.warn(`Copilot CLI stop had ${errors.length} error(s): ${errors.map(e => e.message).join(', ')}`)
      }
    } catch (err) {
      this.logger.error(`Error stopping Copilot CLI: ${String(err)}`)
      // Force stop if graceful fails
      try {
        await this.client.forceStop()
      } catch { /* best effort */ }
    } finally {
      this.client = null
      this.running = false
      this.modelsCache = null
      this.logger.info('Copilot CLI server stopped')
    }
  }

  /**
   * Get the CopilotClient instance.
   * @throws if not started
   */
  getClient(): CopilotClient {
    if (!this.client || !this.running) {
      throw new Error('CopilotSdkManager not started — call start() first')
    }
    return this.client
  }

  isRunning(): boolean {
    return this.running && this.client !== null
  }

  getState(): ConnectionState {
    if (!this.client) return 'disconnected'
    return this.client.getState()
  }

  /**
   * List available models (cached after first call).
   */
  async listModels(): Promise<ModelInfo[]> {
    if (this.modelsCache) return this.modelsCache
    const client = this.getClient()
    try {
      this.modelsCache = await client.listModels()
      this.logger.info(`Copilot SDK models: ${this.modelsCache.map(m => m.id).join(', ')}`)
      return this.modelsCache
    } catch (err) {
      this.logger.error(`Failed to list models: ${String(err)}`)
      return []
    }
  }

  /**
   * Health check — pings the CLI server.
   */
  async ping(): Promise<boolean> {
    if (!this.client || !this.running) return false
    try {
      await this.client.ping('health-check')
      return true
    } catch {
      return false
    }
  }
}
