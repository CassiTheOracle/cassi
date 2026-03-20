/**
 * MessageTracker — Maps sent Telegram message_ids back to their originating
 * events, enabling reply-based steering.
 *
 * Each tracked entry holds enough context to route a user's reply to the
 * correct module, team, or session.
 *
 * Entries are evicted after maxAge to prevent unbounded growth.
 */

// Types

export interface TrackedMessage {
  /** Telegram message_id */
  messageId: number
  /** The event type that generated this message */
  eventType: string
  /** Which topic this was sent to (null = main chat) */
  topicKey: string | null
  /** Source module/system key */
  moduleKey: string
  /** Associated session ID, if any */
  sessionId?: string
  /** Associated team ID, if any */
  teamId?: string
  /** Associated cell ID, if any */
  cellId?: string
  /** Lumen/Dyad session ID, if any */
  orchestrationSessionId?: string
  /** When this entry was created */
  timestamp: number
}

export interface MessageTrackerConfig {
  /** Max number of entries to keep (default: 5000) */
  maxEntries: number
  /** Max age in ms before eviction (default: 2h) */
  maxAgeMs: number
}

// MessageTracker

export class MessageTracker {
  private readonly config: MessageTrackerConfig
  /** messageId → TrackedMessage */
  private readonly entries = new Map<number, TrackedMessage>()

  constructor(config?: Partial<MessageTrackerConfig>) {
    this.config = {
      maxEntries: config?.maxEntries ?? 5000,
      maxAgeMs: config?.maxAgeMs ?? 2 * 60 * 60 * 1000, // 2 hours
    }
  }

  /**
   * Track a sent message.
   */
  track(entry: TrackedMessage): void {
    this.entries.set(entry.messageId, entry)

    // Evict old entries if over limit
    if (this.entries.size > this.config.maxEntries) {
      this.evict()
    }
  }

  /**
   * Look up a tracked message by its Telegram message_id.
   */
  get(messageId: number): TrackedMessage | undefined {
    return this.entries.get(messageId)
  }

  /**
   * Find the most recent tracked message for a given topic.
   * Useful for resolving replies to the "most recent" activity in a topic.
   */
  getLatestForTopic(topicKey: string): TrackedMessage | undefined {
    let latest: TrackedMessage | undefined
    for (const entry of this.entries.values()) {
      if (entry.topicKey === topicKey) {
        if (!latest || entry.timestamp > latest.timestamp) {
          latest = entry
        }
      }
    }
    return latest
  }

  /**
   * Current number of tracked entries.
   */
  get size(): number {
    return this.entries.size
  }

  /**
   * Clear all entries.
   */
  clear(): void {
    this.entries.clear()
  }


  private evict(): void {
    const now = Date.now()
    const cutoff = now - this.config.maxAgeMs

    // Remove expired entries
    for (const [id, entry] of this.entries) {
      if (entry.timestamp < cutoff) {
        this.entries.delete(id)
      }
    }

    // If still over limit, remove oldest entries
    if (this.entries.size > this.config.maxEntries) {
      const sorted = [...this.entries.entries()].sort(
        ([, a], [, b]) => a.timestamp - b.timestamp,
      )
      const toRemove = sorted.length - this.config.maxEntries
      for (let i = 0; i < toRemove; i++) {
        this.entries.delete(sorted[i][0])
      }
    }
  }
}
