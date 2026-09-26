import type { ThalamusTemporalContext } from './types.js'

/**
 * Tracks real timestamps and tool execution metrics for a session.
 *
 * Populated during processing (as messages arrive) and queried during
 * curation to compute temporal context for each message. Replaces the
 * positional urgency decay (index/total) with actual time-based decay.
 */
export class TemporalRegistry {
  /** When the session was created */
  readonly sessionStart: string

  /** Timestamp of the most recent user message */
  lastUserMessageAt: string | null = null

  /** msg index → ISO 8601 timestamp */
  private timestamps = new Map<number, string>()

  /** tool_use_id → execution metrics */
  private toolMetrics = new Map<string, { durationMs: number; outputBytes: number }>()

  constructor(sessionStart?: string) {
    this.sessionStart = sessionStart ?? new Date().toISOString()
  }

  /** Record the timestamp for a message at the given index. */
  recordMessage(index: number, timestamp: string, isUser: boolean): void {
    this.timestamps.set(index, timestamp)
    if (isUser) this.lastUserMessageAt = timestamp
  }

  /** Record tool execution metrics (called when a tool result arrives). */
  recordToolMetrics(toolUseId: string, durationMs: number, outputBytes: number): void {
    this.toolMetrics.set(toolUseId, { durationMs, outputBytes })
  }

  /** Get the recorded timestamp for a message index, or null. */
  getTimestamp(index: number): string | null {
    return this.timestamps.get(index) ?? null
  }

  /** Get tool metrics for a tool_use_id, or null. */
  getToolMetrics(toolUseId: string): { durationMs: number; outputBytes: number } | null {
    return this.toolMetrics.get(toolUseId) ?? null
  }

  /** Get the shared toolMetrics map (for SlotContext). */
  getToolMetricsMap(): Map<string, { durationMs: number; outputBytes: number }> {
    return this.toolMetrics
  }

  /**
   * Compute temporal context for a message at the given index.
   * Returns null if the message has no recorded timestamp.
   */
  computeTemporalContext(index: number): ThalamusTemporalContext | null {
    const ts = this.timestamps.get(index)
    if (!ts) return null

    const msgTime = new Date(ts).getTime()
    const sessionStartTime = new Date(this.sessionStart).getTime()

    let msSincePrevious = 0
    if (index > 0) {
      const prevTs = this.timestamps.get(index - 1)
      if (prevTs) {
        msSincePrevious = Math.max(0, msgTime - new Date(prevTs).getTime())
      }
    }

    let msSinceLastUser = 0
    if (this.lastUserMessageAt) {
      const lastUserTime = new Date(this.lastUserMessageAt).getTime()
      msSinceLastUser = Math.max(0, msgTime - lastUserTime)
    }

    return {
      msSincePrevious,
      msSinceLastUser,
      sessionElapsedMs: Math.max(0, msgTime - sessionStartTime),
    }
  }

  /**
   * Compute time-based urgency for a message at the given index.
   * Uses sigmoid decay from actual timestamps instead of positional decay.
   *
   * @param index - Message index
   * @param now - Current timestamp in ms (default: Date.now())
   * @param halfLifeMs - Time in ms for urgency to decay to 0.5 (default: 10 minutes)
   */
  computeUrgency(index: number, now?: number, halfLifeMs = 10 * 60 * 1000): number {
    const ts = this.timestamps.get(index)
    if (!ts) return 0.1 // fallback for unrecorded messages

    const msgTime = new Date(ts).getTime()
    const currentTime = now ?? Date.now()
    const ageMs = Math.max(0, currentTime - msgTime)

    // Sigmoid decay: 1 / (1 + age/halfLife)
    // At halfLife, urgency = 0.5. At 2x halfLife, urgency = 0.33.
    return 1 / (1 + ageMs / halfLifeMs)
  }

  /** Total tracked messages */
  get size(): number {
    return this.timestamps.size
  }

  /**
   * Build a time-aware gap description for omitted turns.
   */
  describeGap(fromIndex: number, toIndex: number): string {
    const turns = toIndex - fromIndex - 1
    if (turns <= 0) return ''

    const fromTs = this.timestamps.get(fromIndex)
    const toTs = this.timestamps.get(toIndex)
    const parts: string[] = [`${turns} turn${turns > 1 ? 's' : ''}`]

    if (fromTs && toTs) {
      const elapsed = new Date(toTs).getTime() - new Date(fromTs).getTime()
      parts.push(`~${formatDuration(elapsed)}`)
    }

    // Count tool calls in the gap
    let toolCalls = 0
    for (let i = fromIndex + 1; i < toIndex; i++) {
      const ts = this.timestamps.get(i)
      if (ts) toolCalls++ // rough proxy — every recorded message in the gap
    }
    // A more accurate count would check message types, but this is a reasonable heuristic

    parts.push('omitted')
    return parts.join(' · ')
  }
}

/** Format a duration in ms to a human-readable string. */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(0)}s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = Math.floor((ms % 60_000) / 1000)
  if (seconds === 0) return `${minutes}m`
  return `${minutes}m${seconds}s`
}
