/**
 * Rate limiter with priority queue and batching for Telegram message sending.
 *
 * Telegram enforces:
 *  - ~30 messages/second to groups
 *  - ~1 edit/second per message
 *  - 4096 character message limit
 *
 * This limiter queues outgoing messages, batches events that fire within a
 * short window, and applies exponential backoff on 429 responses.
 */

import type { ILogger } from '../../../types/interfaces.js'
import { TelegramRateLimitError } from './telegram-client.js'

// Types

export type MessagePriority = 'high' | 'medium' | 'low'

export interface QueuedMessage {
  id: string
  text: string
  chatId: number
  threadId?: number
  priority: MessagePriority
  timestamp: number
  /** If set, this message should update (edit) an existing message instead of sending new */
  editMessageId?: number
}

export interface RateLimiterConfig {
  /** Max messages per second (default: 20) */
  messagesPerSecond: number
  /** Batch events within this window (default: 500ms) */
  batchWindowMs: number
  /** Max Telegram message length before splitting (default: 3500, TG limit 4096) */
  maxMessageLength: number
  /** Max queued messages before dropping low-priority entries (default: 500) */
  maxQueueSize: number
}

export type SendFn = (msg: QueuedMessage) => Promise<number | null>

// Priority ordering

const PRIORITY_WEIGHT: Record<MessagePriority, number> = {
  high: 3,
  medium: 2,
  low: 1,
}

// RateLimiter

export class RateLimiter {
  private readonly config: RateLimiterConfig
  private readonly logger: ILogger
  private readonly sendFn: SendFn
  private readonly queue: QueuedMessage[] = []
  private drainTimer: ReturnType<typeof setInterval> | null = null
  private backoffMs = 0
  private backoffUntil = 0
  private running = false

  // Observability — allows DeliveryBatcher to monitor rate-limiter state
  private _recent429Count = 0
  private readonly _onBackoffCallbacks: Array<(retryAfterMs: number) => void> = []

  constructor(config: Partial<RateLimiterConfig>, sendFn: SendFn, logger: ILogger) {
    this.config = {
      messagesPerSecond: config.messagesPerSecond ?? 20,
      batchWindowMs: config.batchWindowMs ?? 500,
      maxMessageLength: config.maxMessageLength ?? 3500,
      maxQueueSize: config.maxQueueSize ?? 500,
      ...config,
    }
    this.sendFn = sendFn
    this.logger = logger
  }


  /**
   * Enqueue a message for sending. Messages are prioritized and rate-limited.
   * When the queue exceeds maxQueueSize, low-priority messages are dropped
   * from the tail to make room.
   */
  enqueue(msg: QueuedMessage): void {
    // Split long messages
    if (msg.text.length > this.config.maxMessageLength && !msg.editMessageId) {
      const chunks = this.splitMessage(msg.text, this.config.maxMessageLength)
      for (let i = 0; i < chunks.length; i++) {
        this.queue.push({
          ...msg,
          id: `${msg.id}:${i}`,
          text: chunks[i],
          // Only first chunk gets high priority, rest are medium
          priority: i === 0 ? msg.priority : 'medium',
        })
      }
    } else {
      // Truncate if editing (can't split edits)
      if (msg.editMessageId && msg.text.length > 4096) {
        msg.text = msg.text.slice(0, 4050) + '\n\n<i>... [truncated]</i>'
      }
      this.queue.push(msg)
    }

    // Sort queue by priority (stable sort keeps insertion order within same priority)
    this.queue.sort((a, b) => PRIORITY_WEIGHT[b.priority] - PRIORITY_WEIGHT[a.priority])

    // Enforce queue cap — drop lowest-priority messages from the tail
    if (this.queue.length > this.config.maxQueueSize) {
      const dropped = this.queue.length - this.config.maxQueueSize
      this.queue.length = this.config.maxQueueSize
      this.logger.warn('[rate-limiter] Queue overflow, dropped low-priority messages', { dropped })
    }
  }

  /**
   * Start the drain loop.
   */
  start(): void {
    if (this.running) return
    this.running = true

    const intervalMs = Math.max(50, Math.floor(1000 / this.config.messagesPerSecond))
    this.drainTimer = setInterval(() => this.drain(), intervalMs)
    this.logger.debug('[rate-limiter] Started', { intervalMs, maxMps: this.config.messagesPerSecond })
  }

  /**
   * Stop the drain loop and clear the queue.
   */
  stop(): void {
    this.running = false
    if (this.drainTimer) {
      clearInterval(this.drainTimer)
      this.drainTimer = null
    }
    const dropped = this.queue.length
    this.queue.length = 0
    if (dropped > 0) {
      this.logger.info('[rate-limiter] Stopped, dropped queued messages', { dropped })
    }
  }

  /**
   * Signal a 429 (Too Many Requests) from Telegram. Applies exponential backoff.
   */
  onRateLimited(retryAfterMs?: number): void {
    this.backoffMs = retryAfterMs ?? Math.min((this.backoffMs || 1000) * 2, 30_000)
    this.backoffUntil = Date.now() + this.backoffMs
    this._recent429Count++
    this.logger.warn('[rate-limiter] Rate limited, backing off', { backoffMs: this.backoffMs })

    // Notify observers
    for (const cb of this._onBackoffCallbacks) {
      try { cb(this.backoffMs) } catch { /* best effort */ }
    }
  }

  /**
   * Current queue depth.
   */
  get queueDepth(): number {
    return this.queue.length
  }

  /**
   * Whether the rate limiter is currently in backoff (429 received recently).
   */
  get isBackingOff(): boolean {
    return Date.now() < this.backoffUntil
  }

  /**
   * Number of 429 responses received since construction or last resetStats().
   */
  get recent429Count(): number {
    return this._recent429Count
  }

  /**
   * Register a callback invoked whenever a 429 backoff is applied.
   * Returns an unsubscribe function.
   */
  onBackoff(callback: (retryAfterMs: number) => void): () => void {
    this._onBackoffCallbacks.push(callback)
    return () => {
      const idx = this._onBackoffCallbacks.indexOf(callback)
      if (idx >= 0) this._onBackoffCallbacks.splice(idx, 1)
    }
  }

  /**
   * Reset observability counters.
   */
  resetStats(): void {
    this._recent429Count = 0
  }


  private async drain(): Promise<void> {
    if (this.queue.length === 0) return

    // Respect backoff
    if (Date.now() < this.backoffUntil) return

    const msg = this.queue.shift()
    if (!msg) return

    try {
      const result = await this.sendFn(msg)

      if (result !== null) {
        // Success — reset backoff
        this.backoffMs = 0
      } else {
        // sendFn returned null (non-rate-limit failure) — apply mild backoff
        // to avoid hammering on persistent failures, but don't re-queue
        this.backoffMs = Math.min(Math.max(this.backoffMs, 500) * 1.5, 5_000)
        this.backoffUntil = Date.now() + this.backoffMs
      }
    } catch (err) {
      if (err instanceof TelegramRateLimitError) {
        // Use the server-provided retry-after duration
        this.onRateLimited(err.retryAfterSecs * 1000)
        // Re-queue the failed message at the front
        this.queue.unshift(msg)
      } else {
        const errStr = String(err)
        this.logger.warn('[rate-limiter] Send failed', { id: msg.id, error: errStr })
        // Apply mild backoff for unknown errors
        this.backoffMs = Math.min(Math.max(this.backoffMs, 500) * 1.5, 5_000)
        this.backoffUntil = Date.now() + this.backoffMs
      }
    }
  }

  /**
   * Split a long message into chunks at paragraph/line boundaries.
   */
  private splitMessage(text: string, maxLen: number): string[] {
    const chunks: string[] = []
    let remaining = text

    while (remaining.length > 0) {
      if (remaining.length <= maxLen) {
        chunks.push(remaining)
        break
      }

      // Try to split at last double newline within limit
      let splitAt = remaining.lastIndexOf('\n\n', maxLen)
      if (splitAt < maxLen * 0.3) {
        // No good paragraph break -- try single newline
        splitAt = remaining.lastIndexOf('\n', maxLen)
      }
      if (splitAt < maxLen * 0.3) {
        // No good line break -- hard split
        splitAt = maxLen
      }

      chunks.push(remaining.slice(0, splitAt))
      remaining = remaining.slice(splitAt).trimStart()
    }

    // Add continuation markers
    if (chunks.length > 1) {
      for (let i = 0; i < chunks.length; i++) {
        const marker = `<i>[${i + 1}/${chunks.length}]</i>`
        if (i < chunks.length - 1) {
          chunks[i] += `\n${marker}`
        } else {
          chunks[i] = `${marker}\n${chunks[i]}`
        }
      }
    }

    return chunks
  }
}
