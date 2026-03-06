/**
 * Embedding stack auto-launcher — spawns the local llama.cpp embedding server
 * and zerank reranker as child processes when the daemon starts.
 *
 * Both processes are supervised: if they crash, they are restarted automatically
 * (up to MAX_RESTARTS within a window). On daemon shutdown, both are killed.
 *
 * The launcher checks whether each server is already running before spawning,
 * so it's safe to run alongside a manually-started `bin/embedding-stack`.
 *
 * Port defaults: 18820 (embedding), 18821 (reranker).
 * Override via EMBEDDING_PORT / RERANKER_PORT env vars.
 */

import { spawn, type ChildProcess } from 'child_process'
import { existsSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import { homedir } from 'os'

import type { ILogger } from '../../../types/interfaces.js'

// ── Defaults ────────────────────────────────────────────────────────────────
export const DEFAULT_EMBEDDING_PORT = 18820
export const DEFAULT_RERANKER_PORT = 18821

const MAX_RESTARTS = 5
const RESTART_WINDOW_MS = 300_000  // 5 min — reset restart count after this
const HEALTH_POLL_INTERVAL_MS = 1_000
const HEALTH_TIMEOUT_MS = 180_000  // 3 min max wait (zerank-2 on CPU is slow)

interface ManagedProcess {
  name: string
  proc: ChildProcess | null
  port: number
  restarts: number
  restartWindowStart: number
  dead: boolean
  /** Rebuild the spawn args (called on each restart). */
  buildArgs: () => { command: string; args: string[]; env?: Record<string, string> }
}

export interface EmbeddingStackLauncherConfig {
  /** GPU backend for llama.cpp: 'hip' | 'vulkan'. Default: 'hip' */
  backend?: 'hip' | 'vulkan'
  embeddingPort?: number
  rerankerPort?: number
  /** Path to zembed-1 GGUF model. Default: ~/models/zembed-1.gguf */
  embeddingModelPath?: string
  /** Path to the reranker venv python binary. Default: ~/.venvs/reranker/bin/python */
  rerankerPython?: string
  /** Disable auto-start entirely (e.g. for tests). */
  disabled?: boolean
}

export class EmbeddingStackLauncher {
  private logger: ILogger
  private managed: ManagedProcess[] = []
  private stopped = false
  private config: Required<EmbeddingStackLauncherConfig>

  constructor(logger: ILogger, config?: EmbeddingStackLauncherConfig) {
    this.logger = logger.child?.('embedding-stack') ?? logger

    const home = homedir()
    this.config = {
      backend: config?.backend ?? (process.env.EMBEDDING_BACKEND as 'hip' | 'vulkan') ?? 'hip',
      embeddingPort: config?.embeddingPort
        ?? Number(process.env.EMBEDDING_PORT || String(DEFAULT_EMBEDDING_PORT)),
      rerankerPort: config?.rerankerPort
        ?? Number(process.env.RERANKER_PORT || String(DEFAULT_RERANKER_PORT)),
      embeddingModelPath: config?.embeddingModelPath
        ?? process.env.EMBEDDING_MODEL_PATH
        ?? join(home, 'models', 'zembed-1.gguf'),
      rerankerPython: config?.rerankerPython
        ?? process.env.ZERANK_PYTHON
        ?? join(home, '.venvs', 'reranker', 'bin', 'python'),
      disabled: config?.disabled ?? false,
    }
  }

  /**
   * Start both servers if they aren't already running.
   * Waits for health checks before returning.
   * Throws only if a required binary/model is missing.
   */
  async start(): Promise<void> {
    if (this.config.disabled) {
      this.logger.info('Embedding stack auto-start disabled')
      return
    }

    const { embeddingPort, rerankerPort, backend } = this.config

    // ── Embedding server (llama.cpp) ──
    const llamaServer = join(
      homedir(), 'workspaces', 'llama.cpp', `build-${backend}`, 'bin', 'llama-server',
    )
    if (!existsSync(llamaServer)) {
      this.logger.warn(`llama-server not found at ${llamaServer} — embedding auto-start skipped`)
    } else if (!existsSync(this.config.embeddingModelPath)) {
      this.logger.warn(`Embedding model not found at ${this.config.embeddingModelPath} — skipped`)
    } else if (await this.isHealthy(embeddingPort)) {
      this.logger.info(`Embedding server already running on :${embeddingPort}`)
    } else {
      this.spawnManaged({
        name: 'zembed-1',
        port: embeddingPort,
        buildArgs: () => ({
          command: llamaServer,
          args: [
            '--model', this.config.embeddingModelPath,
            '--port', String(embeddingPort),
            '--embeddings',
            '--gpu-layers', '999',
            '--ctx-size', '8192',
            '--batch-size', '2048',
            '--ubatch-size', '512',
          ],
        }),
      })
    }

    // ── Reranker server (zerank-server Python) ──
    // Resolve project root: __dirname is dist/core/intelligence/embeddings/ at runtime,
    // but bin/ lives at the repo root (4 levels up from dist source).
    const __dirname = dirname(fileURLToPath(import.meta.url))
    const projectRoot = join(__dirname, '..', '..', '..', '..')
    const zerankScript = join(projectRoot, 'bin', 'zerank-server')
    if (!existsSync(this.config.rerankerPython)) {
      this.logger.warn(`Reranker venv not found at ${this.config.rerankerPython} — reranker auto-start skipped`)
    } else if (!existsSync(zerankScript)) {
      this.logger.warn(`zerank-server script not found at ${zerankScript} — reranker auto-start skipped`)
    } else if (await this.isHealthy(rerankerPort)) {
      this.logger.info(`Reranker server already running on :${rerankerPort}`)
    } else {
      this.spawnManaged({
        name: 'zerank-2',
        port: rerankerPort,
        buildArgs: () => ({
          command: this.config.rerankerPython,
          args: [zerankScript, '--model', 'zerank-2', '--port', String(rerankerPort)],
        }),
      })
    }

    // Wait for all managed processes to become healthy
    await this.waitForHealthy()
  }

  /** Kill all managed child processes. */
  stop(): void {
    this.stopped = true
    for (const m of this.managed) {
      m.dead = true
      this.killProc(m)
    }
    this.managed = []
  }

  // ── Internal ──────────────────────────────────────────────────────────────

  private spawnManaged(opts: {
    name: string
    port: number
    buildArgs: () => { command: string; args: string[]; env?: Record<string, string> }
  }): void {
    const m: ManagedProcess = {
      name: opts.name,
      proc: null,
      port: opts.port,
      restarts: 0,
      restartWindowStart: Date.now(),
      dead: false,
      buildArgs: opts.buildArgs,
    }
    this.managed.push(m)
    this.spawnProcess(m)
  }

  private spawnProcess(m: ManagedProcess): void {
    if (m.dead || this.stopped) return

    const { command, args, env } = m.buildArgs()
    this.logger.info(`Starting ${m.name} on :${m.port}`, { command: `${command} ${args.join(' ')}` })

    const proc = spawn(command, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, ...env },
      detached: false,
    })
    m.proc = proc

    // Log stderr for diagnostics (condensed)
    let stderrBuf = ''
    proc.stderr?.on('data', (chunk: Buffer) => {
      stderrBuf += chunk.toString()
      // Flush complete lines
      const lines = stderrBuf.split('\n')
      stderrBuf = lines.pop() ?? ''
      for (const line of lines) {
        if (line.trim()) {
          this.logger.debug(`[${m.name}] ${line}`)
        }
      }
    })

    proc.on('error', (err) => {
      this.logger.error(`${m.name} process error`, { error: String(err) })
    })

    proc.on('exit', (code, signal) => {
      if (m.dead || this.stopped) return  // Intentional shutdown
      this.logger.warn(`${m.name} exited`, { code, signal })
      this.maybeRestart(m)
    })
  }

  private maybeRestart(m: ManagedProcess): void {
    if (m.dead || this.stopped) return

    // Reset restart counter if outside the window
    if (Date.now() - m.restartWindowStart > RESTART_WINDOW_MS) {
      m.restarts = 0
      m.restartWindowStart = Date.now()
    }

    m.restarts++
    if (m.restarts > MAX_RESTARTS) {
      this.logger.error(`${m.name} exceeded ${MAX_RESTARTS} restarts — giving up`)
      m.dead = true
      return
    }

    const delay = Math.min(1000 * m.restarts, 10_000)
    this.logger.info(`Restarting ${m.name} in ${delay}ms (attempt ${m.restarts}/${MAX_RESTARTS})`)
    setTimeout(() => this.spawnProcess(m), delay)
  }

  private killProc(m: ManagedProcess): void {
    if (!m.proc || m.proc.exitCode !== null) return
    try {
      m.proc.kill('SIGTERM')
      // Force kill after 5s if still alive
      const pid = m.proc.pid
      setTimeout(() => {
        try {
          if (pid) process.kill(pid, 0)  // Check if still alive
          if (pid) process.kill(pid, 'SIGKILL')
        } catch {
          // Already dead — fine
        }
      }, 5000)
    } catch {
      // Already dead
    }
  }

  private async isHealthy(port: number): Promise<boolean> {
    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 2000)
      const res = await fetch(`http://127.0.0.1:${port}/health`, {
        signal: controller.signal,
      })
      clearTimeout(timer)
      return res.ok
    } catch {
      return false
    }
  }

  private async waitForHealthy(): Promise<void> {
    const pending = this.managed.filter(m => !m.dead && m.proc)
    if (pending.length === 0) return

    this.logger.info(`Waiting for ${pending.length} server(s) to become healthy...`)
    const deadline = Date.now() + HEALTH_TIMEOUT_MS

    for (const m of pending) {
      while (Date.now() < deadline) {
        if (m.dead || this.stopped) break
        if (await this.isHealthy(m.port)) {
          this.logger.info(`${m.name} healthy on :${m.port}`)
          break
        }
        if (Date.now() >= deadline) {
          this.logger.warn(`${m.name} did not become healthy within ${HEALTH_TIMEOUT_MS / 1000}s`)
          break
        }
        await new Promise(r => setTimeout(r, HEALTH_POLL_INTERVAL_MS))
      }
    }
  }
}
