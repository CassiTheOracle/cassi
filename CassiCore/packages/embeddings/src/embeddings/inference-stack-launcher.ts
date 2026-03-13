/**
 * Inference stack auto-launcher — spawns local inference servers as supervised
 * child processes when the daemon starts.
 *
 * Managed processes:
 *   1. zembed-1   — embedding server    (llama.cpp, port 18820, Q4_K_M GGUF)
 *   2. reranker   — reranker server     (zerank-server + llama-cpp-python, port 18821, Qwen3-Reranker-0.6B Q8_0)
 *   3. generative — smartrecall model   (llama.cpp, port 18822, Q8_0 GGUF)
 *
 * All processes are supervised: if they crash, they are restarted automatically
 * (up to MAX_RESTARTS within a window). On daemon shutdown, all are killed.
 *
 * Idle unloading: after `idleTimeoutMs` of inactivity (no `notifyActivity` calls),
 * a managed process is killed to free VRAM. On the next request, the consuming
 * service calls `ensureRunning(name)` which re-spawns and waits for health.
 *
 * The launcher checks whether each server is already running before spawning,
 * so it's safe to run alongside manually-started servers.
 *
 * Port defaults: 18820 (embedding), 18821 (reranker), 18822 (generative).
 * Override via EMBEDDING_PORT / RERANKER_PORT / GENERATIVE_PORT env vars.
 *
 * NOTE: The reranker uses llama-cpp-python for raw logit access. Qwen3-Reranker-0.6B
 * uses softmax([no_logit, yes_logit])[1] scoring with an instruction-aware prompt
 * template. The older zerank-2 model uses sigmoid(Yes_logit/5.0) scoring.
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
export const DEFAULT_GENERATIVE_PORT = 18822

/** Stable logical names for managed processes — use these in service call sites. */
export const MANAGED_EMBEDDING = 'zembed-1'
export const MANAGED_RERANKER = 'reranker'
export const MANAGED_GENERATIVE = 'qwen3.5-0.8b'

const MAX_RESTARTS = 5
const RESTART_WINDOW_MS = 300_000  // 5 min — reset restart count after this
const HEALTH_POLL_INTERVAL_MS = 1_000
const HEALTH_TIMEOUT_MS = 180_000  // 3 min max wait (zerank-2 on CPU is slow)
const IDLE_CHECK_INTERVAL_MS = 60_000  // Check for idle processes every 60s
const DEFAULT_IDLE_TIMEOUT_MS = 600_000  // 10 minutes

interface ManagedProcess {
  name: string
  proc: ChildProcess | null
  port: number
  restarts: number
  restartWindowStart: number
  dead: boolean
  /** True when the process was intentionally killed due to idle timeout.
   *  Can be restarted on demand via `ensureRunning()`. */
  unloaded: boolean
  /** Timestamp of last activity notification from a consuming service. */
  lastActivity: number
  /** Guards concurrent `ensureRunning()` calls — only one restart at a time. */
  startingPromise: Promise<void> | null
  /** Rebuild the spawn args (called on each restart). */
  buildArgs: () => { command: string; args: string[]; env?: Record<string, string> }
}

export interface InferenceStackLauncherConfig {
  /** GPU backend for llama.cpp: 'hip' | 'vulkan'. Default: 'hip' */
  backend?: 'hip' | 'vulkan'
  embeddingPort?: number
  rerankerPort?: number
  /** Path to zembed-1 GGUF model. Default: ~/models/zembed-1-Q4_K_M.gguf */
  embeddingModelPath?: string
  /** @deprecated Reranker now uses GGUF via llama-cpp-python. Use rerankerModelPath instead. */
  rerankerPython?: string
  /** Path to reranker GGUF model. Default: ~/models/Qwen3-Reranker-0.6B-Q8_0.gguf */
  rerankerModelPath?: string
  /** Reranker model type: 'zerank' or 'qwen-reranker'. Default: 'qwen-reranker' */
  rerankerModelType?: 'zerank' | 'qwen-reranker'
  /** GPU layers for reranker (llama-cpp-python). Default: 99 */
  rerankerGpuLayers?: number
  /** Context size for the reranker. Default: 4096 */
  rerankerCtxSize?: number
  /** @deprecated Reranker uses llama-cpp-python, not llama-server. No effect. */
  rerankerBatchSize?: number
  /** @deprecated Reranker uses llama-cpp-python, not llama-server. No effect. */
  rerankerParallel?: number
  /** Disable reranker auto-start. Default: false */
  rerankerDisabled?: boolean
  /** llama.cpp GPU layers. Lower this if HIP/Vulkan runs out of VRAM. Default: 99 */
  embeddingGpuLayers?: number
  /** llama.cpp context size for the embedding server. Default: 4096 */
  embeddingCtxSize?: number
  /** llama.cpp batch size for the embedding server. Default: 512 */
  embeddingBatchSize?: number
  /** llama.cpp micro-batch size for the embedding server. Default: 128 */
  embeddingUbatchSize?: number
  /** Disable auto-start entirely (e.g. for tests). */
  disabled?: boolean
  // ── Generative model (local LLM for query extraction, summarization, etc.) ──
  /** Port for the local generative model server. Default: 18822 */
  generativePort?: number
   /** Path to generative GGUF model. Default: ~/models/smartrecall-0.8B-Q8_0.gguf */
  generativeModelPath?: string
  /** GPU layers for generative model. Default: 99 (all on GPU) */
  generativeGpuLayers?: number
  /** Context size for generative model. Default: 4096 */
  generativeCtxSize?: number
  /** Batch size for generative model. Default: 512 */
  generativeBatchSize?: number
  /** Number of parallel request slots. Default: 2 */
  generativeParallel?: number
  /** Disable generative model auto-start. Default: false */
  generativeDisabled?: boolean
  /**
   * Idle timeout in ms before unloading a model to free VRAM.
   * After this duration of inactivity, the process is killed.
   * It will be restarted on demand when a service calls `ensureRunning()`.
   * Set to 0 to disable idle unloading. Default: 600000 (10 min).
   */
  idleTimeoutMs?: number
}

/** @deprecated Use InferenceStackLauncherConfig instead */
export type EmbeddingStackLauncherConfig = InferenceStackLauncherConfig

export class InferenceStackLauncher {
  private logger: ILogger
  private managed: ManagedProcess[] = []
  private stopped = false
  private config: Required<InferenceStackLauncherConfig>
  private idleCheckTimer: ReturnType<typeof setInterval> | null = null

  constructor(logger: ILogger, config?: InferenceStackLauncherConfig) {
    this.logger = logger.child?.('inference-stack') ?? logger

    const home = homedir()
    this.config = {
      backend: config?.backend ?? (process.env.EMBEDDING_BACKEND as 'hip' | 'vulkan') ?? 'hip',
      embeddingPort: config?.embeddingPort
        ?? Number(process.env.EMBEDDING_PORT || String(DEFAULT_EMBEDDING_PORT)),
      rerankerPort: config?.rerankerPort
        ?? Number(process.env.RERANKER_PORT || String(DEFAULT_RERANKER_PORT)),
      embeddingModelPath: config?.embeddingModelPath
        ?? process.env.EMBEDDING_MODEL_PATH
        ?? join(home, 'models', 'zembed-1-Q4_K_M.gguf'),
      rerankerPython: config?.rerankerPython
        ?? process.env.ZERANK_PYTHON
        ?? join(home, '.venvs', 'reranker', 'bin', 'python'),
      rerankerModelPath: config?.rerankerModelPath
        ?? process.env.RERANKER_MODEL_PATH
        ?? join(home, 'models', 'Qwen3-Reranker-0.6B-Q8_0.gguf'),
      rerankerModelType: config?.rerankerModelType
        ?? (process.env.RERANKER_MODEL_TYPE as 'zerank' | 'qwen-reranker')
        ?? 'qwen-reranker',
      rerankerGpuLayers: config?.rerankerGpuLayers
        ?? Number(process.env.RERANKER_GPU_LAYERS || '99'),
      rerankerCtxSize: config?.rerankerCtxSize
        ?? Number(process.env.RERANKER_CTX_SIZE || '4096'),
      rerankerBatchSize: config?.rerankerBatchSize
        ?? Number(process.env.RERANKER_BATCH_SIZE || '512'),
      rerankerParallel: config?.rerankerParallel
        ?? Number(process.env.RERANKER_PARALLEL || '8'),
      rerankerDisabled: config?.rerankerDisabled ?? false,
      embeddingGpuLayers: config?.embeddingGpuLayers
        ?? Number(process.env.EMBEDDING_GPU_LAYERS || '99'),
      embeddingCtxSize: config?.embeddingCtxSize
        ?? Number(process.env.EMBEDDING_CTX_SIZE || '4096'),
      embeddingBatchSize: config?.embeddingBatchSize
        ?? Number(process.env.EMBEDDING_SERVER_BATCH_SIZE || '512'),
      embeddingUbatchSize: config?.embeddingUbatchSize
        ?? Number(process.env.EMBEDDING_SERVER_UBATCH_SIZE || '128'),
      disabled: config?.disabled ?? false,
      // ── Generative model defaults ──
      generativePort: config?.generativePort
        ?? Number(process.env.GENERATIVE_PORT || String(DEFAULT_GENERATIVE_PORT)),
      generativeModelPath: config?.generativeModelPath
        ?? process.env.GENERATIVE_MODEL_PATH
        ?? join(home, 'models', 'smartrecall-0.8B-Q8_0.gguf'),
      generativeGpuLayers: config?.generativeGpuLayers
        ?? Number(process.env.GENERATIVE_GPU_LAYERS || '99'),
      generativeCtxSize: config?.generativeCtxSize
        ?? Number(process.env.GENERATIVE_CTX_SIZE || '4096'),
      generativeBatchSize: config?.generativeBatchSize
        ?? Number(process.env.GENERATIVE_BATCH_SIZE || '512'),
      generativeParallel: config?.generativeParallel
        ?? Number(process.env.GENERATIVE_PARALLEL || '2'),
      generativeDisabled: config?.generativeDisabled ?? false,
      idleTimeoutMs: config?.idleTimeoutMs
        ?? Number(process.env.INFERENCE_IDLE_TIMEOUT_MS || String(DEFAULT_IDLE_TIMEOUT_MS)),
    }
  }

  /**
   * Start all servers if they aren't already running.
   * Waits for health checks before returning.
   * Throws only if a required binary/model is missing.
   */
  async start(): Promise<void> {
    if (this.config.disabled) {
      this.logger.info('Inference stack auto-start disabled')
      return
    }

    const { embeddingPort, rerankerPort, generativePort, backend } = this.config

    // Resolve llama-server binary path (shared by embedding + generative)
    const llamaServer = join(
      homedir(), 'workspaces', 'llama.cpp', `build-${backend}`, 'bin', 'llama-server',
    )
    const llamaServerExists = existsSync(llamaServer)
    if (!llamaServerExists) {
      this.logger.warn(`llama-server not found at ${llamaServer} — llama.cpp servers will be skipped`)
    }

    // ── Embedding server (llama.cpp) ──
    if (!llamaServerExists) {
      // Already warned above
    } else if (!existsSync(this.config.embeddingModelPath)) {
      this.logger.warn(`Embedding model not found at ${this.config.embeddingModelPath} — skipped`)
    } else if (await this.isHealthy(embeddingPort)) {
      this.logger.info(`Embedding server already running on :${embeddingPort}`)
    } else {
      this.spawnManaged({
        name: MANAGED_EMBEDDING,
        port: embeddingPort,
        buildArgs: () => ({
          command: llamaServer,
          args: [
            '--model', this.config.embeddingModelPath,
            '--port', String(embeddingPort),
            '--embeddings',
            '--gpu-layers', String(this.config.embeddingGpuLayers),
            '--ctx-size', String(this.config.embeddingCtxSize),
            '--batch-size', String(this.config.embeddingBatchSize),
            '--ubatch-size', String(this.config.embeddingUbatchSize),
          ],
        }),
      })
    }

    // ── Reranker server (zerank-server with GGUF via llama-cpp-python) ──
    const __dirname = dirname(fileURLToPath(import.meta.url))
    const projectRoot = join(__dirname, '..', '..', '..', '..')
    const zerankScript = join(projectRoot, 'bin', 'zerank-server')
    if (this.config.rerankerDisabled) {
      this.logger.info('Reranker auto-start disabled')
    } else if (!existsSync(this.config.rerankerPython)) {
      this.logger.warn(`Reranker Python not found at ${this.config.rerankerPython} — reranker auto-start skipped`)
    } else if (!existsSync(zerankScript)) {
      this.logger.warn(`zerank-server script not found at ${zerankScript} — reranker auto-start skipped`)
    } else if (!existsSync(this.config.rerankerModelPath)) {
      this.logger.warn(`Reranker model not found at ${this.config.rerankerModelPath} — skipped`)
    } else if (await this.isHealthy(rerankerPort)) {
      this.logger.info(`Reranker server already running on :${rerankerPort}`)
    } else {
      this.spawnManaged({
        name: MANAGED_RERANKER,
        port: rerankerPort,
        buildArgs: () => ({
          command: this.config.rerankerPython,
          args: [
            zerankScript,
            '--gguf', this.config.rerankerModelPath,
            '--model-type', this.config.rerankerModelType,
            '--port', String(rerankerPort),
            '--gpu-layers', String(this.config.rerankerGpuLayers),
            '--ctx-size', String(this.config.rerankerCtxSize),
          ],
        }),
      })
    }

    // ── Generative model server (llama.cpp) ──
    if (this.config.generativeDisabled) {
      this.logger.info('Generative model auto-start disabled')
    } else if (!llamaServerExists) {
      // Already warned about missing llama-server
    } else if (!existsSync(this.config.generativeModelPath)) {
      this.logger.warn(`Generative model not found at ${this.config.generativeModelPath} — skipped`)
    } else if (await this.isHealthy(generativePort)) {
      this.logger.info(`Generative model server already running on :${generativePort}`)
    } else {
      this.spawnManaged({
        name: MANAGED_GENERATIVE,
        port: generativePort,
        buildArgs: () => ({
          command: llamaServer,
          args: [
            '--model', this.config.generativeModelPath,
            '--port', String(generativePort),
            '--gpu-layers', String(this.config.generativeGpuLayers),
            '--ctx-size', String(this.config.generativeCtxSize),
            '--batch-size', String(this.config.generativeBatchSize),
            '--parallel', String(this.config.generativeParallel),
          ],
        }),
      })
    }

    // Wait for all managed processes to become healthy
    await this.waitForHealthy()

    // Start the idle-unload timer
    this.startIdleChecker()
  }

  /** Kill all managed child processes and stop idle monitoring. */
  stop(): void {
    this.stopped = true
    if (this.idleCheckTimer) {
      clearInterval(this.idleCheckTimer)
      this.idleCheckTimer = null
    }
    for (const m of this.managed) {
      m.dead = true
      this.killProc(m)
    }
    this.managed = []
  }

  // ── Public: demand loading / activity tracking ────────────────────────────

  /**
   * Ensure a managed process is running. If it was idle-unloaded, re-spawn
   * it and wait for health before returning. If already running, returns
   * immediately.
   *
   * @returns `true` if the process was restarted (callers may want to reset
   *   their circuit breaker), `false` if it was already running.
   */
  async ensureRunning(name: string): Promise<boolean> {
    const m = this.managed.find(p => p.name === name)
    if (!m || m.dead || this.stopped) return false

    // Process is alive and not unloaded — nothing to do
    if (!m.unloaded && m.proc && m.proc.exitCode === null) return false

    // If not unloaded (e.g., in a crash-restart cycle), let maybeRestart handle it
    if (!m.unloaded) return false

    // Guard against concurrent restarts
    if (m.startingPromise) {
      await m.startingPromise
      return true
    }

    this.logger.info(`Reloading ${m.name} on demand`)
    m.startingPromise = this.demandRestart(m)
    try {
      await m.startingPromise
    } finally {
      m.startingPromise = null
    }
    return true
  }

  /**
   * Notify that a service made a successful request to the named process.
   * Resets the idle timer for that process.
   */
  notifyActivity(name: string): void {
    const m = this.managed.find(p => p.name === name)
    if (m) m.lastActivity = Date.now()
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
      unloaded: false,
      lastActivity: Date.now(),
      startingPromise: null,
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
      if (m.dead || this.stopped || m.unloaded) return  // Intentional shutdown or idle unload
      this.logger.warn(`${m.name} exited`, { code, signal })
      this.maybeRestart(m)
    })
  }

  /** Restart a process that was idle-unloaded. Resets counters and waits for health. */
  private async demandRestart(m: ManagedProcess): Promise<void> {
    m.unloaded = false
    m.restarts = 0
    m.restartWindowStart = Date.now()
    m.lastActivity = Date.now()

    this.spawnProcess(m)
    await this.waitForSingleHealthy(m)
  }

  private maybeRestart(m: ManagedProcess): void {
    if (m.dead || this.stopped || m.unloaded) return

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
    const pending = this.managed.filter(m => !m.dead && !m.unloaded && m.proc)
    if (pending.length === 0) return

    this.logger.info(`Waiting for ${pending.length} server(s) to become healthy...`)

    await Promise.all(pending.map(m => this.waitForSingleHealthy(m)))
  }

  /** Wait for a single managed process to become healthy (or timeout). */
  private async waitForSingleHealthy(m: ManagedProcess): Promise<void> {
    const deadline = Date.now() + HEALTH_TIMEOUT_MS
    while (Date.now() < deadline) {
      if (m.dead || this.stopped) break
      if (await this.isHealthy(m.port)) {
        this.logger.info(`${m.name} healthy on :${m.port}`)
        return
      }
      await new Promise(r => setTimeout(r, HEALTH_POLL_INTERVAL_MS))
    }
    this.logger.warn(`${m.name} did not become healthy within ${HEALTH_TIMEOUT_MS / 1000}s`)
  }

  // ── Idle unloading ──────────────────────────────────────────────────────

  /** Start periodic idle checker. Processes idle longer than idleTimeoutMs are killed. */
  private startIdleChecker(): void {
    const timeout = this.config.idleTimeoutMs
    if (timeout <= 0) {
      this.logger.info('Idle unloading disabled (idleTimeoutMs=0)')
      return
    }

    this.logger.info(`Idle unloading enabled: timeout=${Math.round(timeout / 1000)}s`)
    this.idleCheckTimer = setInterval(() => this.checkIdle(), IDLE_CHECK_INTERVAL_MS)
  }

  /** Kill processes that have been idle longer than the configured timeout. */
  private checkIdle(): void {
    const now = Date.now()
    const timeout = this.config.idleTimeoutMs

    for (const m of this.managed) {
      if (m.dead || m.unloaded || !m.proc || m.proc.exitCode !== null) continue

      const idleMs = now - m.lastActivity
      if (idleMs > timeout) {
        const idleMin = Math.round(idleMs / 60_000)
        this.logger.info(`Unloading ${m.name} (idle ${idleMin}min) to free VRAM`)
        m.unloaded = true
        this.killProc(m)
      }
    }
  }
}

/** @deprecated Use InferenceStackLauncher instead */
export const EmbeddingStackLauncher = InferenceStackLauncher

// ── Singleton ────────────────────────────────────────────────────────────────
let _launcherInstance: InferenceStackLauncher | null = null

/** Register the launcher singleton (called by the daemon at startup). */
export function setInferenceStackLauncher(launcher: InferenceStackLauncher): void {
  _launcherInstance = launcher
}

/** Get the launcher singleton. Returns null if the daemon hasn't started it. */
export function getInferenceStackLauncher(): InferenceStackLauncher | null {
  return _launcherInstance
}
