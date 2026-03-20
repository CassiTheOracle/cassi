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

  constructor(config: Partial<RateLimiterConfig>, sendFn: SendFn, logger: ILogger) {
    this.config = {
      messagesPerSecond: config.messagesPerSecond ?? 20,
      batchWindowMs: config.batchWindowMs ?? 500,
      maxMessageLength: config.maxMessageLength ?? 3500,
      ...config,
    }
    this.sendFn = sendFn
    this.logger = logger
  }


  /**
   * Enqueue a message for sending. Messages are prioritized and rate-limited.
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
    this.logger.warn('[rate-limiter] Rate limited, backing off', { backoffMs: this.backoffMs })
  }

  /**
   * Current queue depth.
   */
  get queueDepth(): number {
    return this.queue.length
  }


  private async drain(): Promise<void> {
    if (this.queue.length === 0) return

    // Respect backoff
    if (Date.now() < this.backoffUntil) return

    // Reset backoff on successful drain
    this.backoffMs = 0

    const msg = this.queue.shift()
    if (!msg) return

    try {
      await this.sendFn(msg)
    } catch (err) {
      const errStr = String(err)
      if (errStr.includes('429') || errStr.includes('Too Many Requests')) {
        this.onRateLimited()
        // Re-queue the failed message at the front
        this.queue.unshift(msg)
      } else {
        this.logger.warn('[rate-limiter] Send failed', { id: msg.id, error: errStr })
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
