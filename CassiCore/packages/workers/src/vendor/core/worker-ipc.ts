/**
 * worker-ipc.ts — Unified IPC adapter for child_process workers.
 *
 * Provides the same interface that workers previously used with `parentPort`
 * from `worker_threads`, but backed by `process.send()` / `process.on('message')`.
 *
 * Workers import this instead of `node:worker_threads`:
 *
 *   import { workerPort } from '../core/worker-ipc.js'
 *
 * The adapter also handles:
 *   - Health pings from the plugin host (automatic pong replies)
 *   - Graceful shutdown via 'shutdown' message
 *   - Type-safe message protocol (HostMessage / WorkerMessage)
 */


/** Messages sent from daemon (plugin-host) to worker */
export type HostMessage =
  | { type: 'init'; config: Record<string, unknown> }
  | { type: 'config:update'; config: Record<string, unknown> }
  | { type: 'message'; payload: unknown }
  | { type: 'health:ping'; ts: number }
  | { type: 'shutdown' }

/** Messages sent from worker back to daemon (plugin-host) */
export type WorkerMessage =
  | { type: 'ready' }
  | { type: 'message'; payload: unknown }
  | { type: 'error'; message: string }
  | { type: 'log'; level: string; message: string }
  | { type: 'signal'; payload: Record<string, unknown> }
  | { type: 'health:pong'; ts: number; metrics?: { memoryMb: number } }


// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyMessage = { type: string; [key: string]: any }
type MessageHandler = (msg: AnyMessage) => void

/**
 * Drop-in replacement for `parentPort` from `worker_threads`.
 * Uses `process.send()` / `process.on('message')` for IPC over child_process.
 *
 * Message typing is intentionally loose (AnyMessage) because:
 *   1. IPC is JSON-serialized — runtime types are inherently dynamic
 *   2. Each worker defines its own typed HostMessage/WorkerMessage unions
 *   3. The health:ping/pong protocol is handled transparently here
 *
 * Workers should cast the incoming message to their own HostMessage type:
 *   workerPort.on('message', (raw) => { const msg = raw as MyHostMessage; ... })
 */
class WorkerPort {
  private handlers: MessageHandler[] = []
  private closed = false

  constructor() {
    if (typeof process.send !== 'function') {
      throw new Error(
        'WorkerPort: must be run as a child_process.fork() — process.send is not available'
      )
    }

    // Set process title for visibility in ps/top/htop
    const workerId = process.env.CASSICORE_WORKER_ID ?? 'worker'
    const shortName = workerId.replace(/^channel:/, '').replace(/-channel$/, '')
    process.title = `cassi:w:${shortName}`

    // Listen for IPC messages from the plugin host
    process.on('message', (raw: unknown) => {
      if (this.closed) return
      const msg = raw as AnyMessage

      // Auto-handle health pings (transparent to worker code)
      if (msg?.type === 'health:ping') {
        this.postMessage({
          type: 'health:pong',
          ts: msg.ts,
          metrics: {
            memoryMb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
          },
        })
        return
      }

      // Dispatch to registered handlers
      for (const handler of this.handlers) {
        try {
          handler(msg)
        } catch (err) {
          this.postMessage({
            type: 'error',
            message: `Unhandled error in message handler: ${String(err)}`,
          })
        }
      }
    })
  }

  /**
   * Register a message handler (same signature as `parentPort.on('message', fn)`)
   */
  on(_event: 'message', handler: MessageHandler): void {
    this.handlers.push(handler)
  }

  /**
   * Send a message back to the plugin host
   */
  postMessage(msg: AnyMessage): void {
    if (this.closed) return
    try {
      process.send!(msg)
    } catch {
      // IPC channel already closed — worker is shutting down
    }
  }

  /**
   * Close the IPC channel (called during shutdown)
   */
  close(): void {
    this.closed = true
    try {
      process.disconnect?.()
    } catch {
      // Already disconnected
    }
  }
}


/**
 * The worker port singleton.
 * Import this in worker files to communicate with the daemon.
 *
 * Replaces: `import { parentPort } from 'node:worker_threads'`
 * With:     `import { workerPort } from '../core/worker-ipc.js'`
 */
export const workerPort = new WorkerPort()
