/**
 * SessionDigestStore — Cross-Session Awareness
 *
 * Maintains a live digest of every active session so any session can see
 * what sibling sessions are currently doing.  The store also carries a
 * per-session mailbox that enables future inter-session messaging.
 *
 * Design goals
 * - Zero-latency reads: all state is in-memory (Map + array)
 * - 10-minute TTL: sessions inactive for > 10 min are excluded from
 *   the always-on digest block but remain searchable
 * - Future-proof: mailbox field + send/receive helpers are present from
 *   day one so inter-session messaging can be wired without structural changes
 */

import type { ConversationPhase } from '@cassicore/dreamer-reverie-subconscious'
import type { ILogger } from '@cassicore/foundation'


export const DIGEST_ACTIVE_TTL_MS = 10 * 60 * 1000   // 10 minutes


export interface SessionMessage {
  id: string
  fromSessionId: string
  fromTopic: string
  content: string
  timestamp: number
  read: boolean
}

export interface SessionDigest {
  sessionId: string
  channelId: string
  senderId: string

  /** High-level topic inferred from MentalModel.state.topic */
  topic: string
  /** Current task description from MentalModel.state.intent.description */
  currentTask: string
  /** Current conversation phase */
  phase: ConversationPhase

  /** Last 10 files accessed (from tool call records) */
  filesActive: string[]
  /** Last 5 tool calls summarised as "<tool>(<target>)" */
  recentActions: string[]
  /** Decisions recorded from dialectic synthesis signals (confidence > 0.7) */
  decisions: string[]
  /** Key learnings recorded from thinker:insight events */
  learnings: string[]

  turnCount: number
  lastActiveAt: number
  /** True when lastActiveAt is within DIGEST_ACTIVE_TTL_MS */
  isActive: boolean

  /** Pending messages from other sessions */
  mailbox: SessionMessage[]
}


export class SessionDigestStore {
  private readonly digests = new Map<string, SessionDigest>()
  private readonly logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child?.('session-digest-store') ?? logger
  }


  /**
   * Upsert (create or patch) a digest for the given session.
   * Only the supplied fields are updated; existing fields are preserved.
   */
  upsert(sessionId: string, patch: Partial<Omit<SessionDigest, 'sessionId' | 'mailbox' | 'isActive'>>): void {
    const now = Date.now()
    const existing = this.digests.get(sessionId)

    if (existing) {
      // Merge arrays with deduplication (keep last N)
      if (patch.filesActive) {
        const merged = [...new Set([...existing.filesActive, ...patch.filesActive])]
        existing.filesActive = merged.slice(-10)
      }
      if (patch.recentActions) {
        existing.recentActions = [...existing.recentActions, ...patch.recentActions].slice(-5)
      }
      if (patch.decisions) {
        existing.decisions = [...new Set([...existing.decisions, ...patch.decisions])].slice(-20)
      }
      if (patch.learnings) {
        existing.learnings = [...new Set([...existing.learnings, ...patch.learnings])].slice(-20)
      }

      // Scalar overwrites
      if (patch.topic !== undefined)       existing.topic       = patch.topic
      if (patch.currentTask !== undefined) existing.currentTask = patch.currentTask
      if (patch.phase !== undefined)       existing.phase       = patch.phase
      if (patch.channelId !== undefined)   existing.channelId   = patch.channelId
      if (patch.senderId !== undefined)    existing.senderId    = patch.senderId
      if (patch.turnCount !== undefined)   existing.turnCount   = patch.turnCount

      existing.lastActiveAt = patch.lastActiveAt ?? now
      existing.isActive     = (now - existing.lastActiveAt) < DIGEST_ACTIVE_TTL_MS
    } else {
      const lastActiveAt = patch.lastActiveAt ?? now
      this.digests.set(sessionId, {
        sessionId,
        channelId:     patch.channelId     ?? '',
        senderId:      patch.senderId      ?? '',
        topic:         patch.topic         ?? 'New conversation',
        currentTask:   patch.currentTask   ?? '',
        phase:         patch.phase         ?? 'initial',
        filesActive:   (patch.filesActive  ?? []).slice(-10),
        recentActions: (patch.recentActions ?? []).slice(-5),
        decisions:     (patch.decisions    ?? []).slice(-20),
        learnings:     (patch.learnings    ?? []).slice(-20),
        turnCount:     patch.turnCount     ?? 0,
        lastActiveAt,
        isActive:      (now - lastActiveAt) < DIGEST_ACTIVE_TTL_MS,
        mailbox:       [],
      })
    }
  }

  /**
   * Record that a session has had activity (touch lastActiveAt).
   */
  touch(sessionId: string): void {
    const d = this.digests.get(sessionId)
    if (!d) return
    const now = Date.now()
    d.lastActiveAt = now
    d.isActive     = true
  }

  /**
   * Mark a session as inactive immediately (e.g. on session:ended).
   */
  markInactive(sessionId: string): void {
    const d = this.digests.get(sessionId)
    if (!d) return
    d.isActive = false
  }


  get(sessionId: string): SessionDigest | undefined {
    return this.rehydrate(this.digests.get(sessionId))
  }

  /**
   * Return all digests for sessions OTHER than `currentSessionId`.
   * Inactive sessions are included if `includeInactive` is true.
   */
  getSiblings(currentSessionId: string, includeInactive = false): SessionDigest[] {
    const now = Date.now()
    const out: SessionDigest[] = []
    for (const [id, d] of this.digests) {
      if (id === currentSessionId) continue
      const active = (now - d.lastActiveAt) < DIGEST_ACTIVE_TTL_MS
      d.isActive = active
      if (!active && !includeInactive) continue
      out.push({ ...d })
    }
    return out.sort((a, b) => b.lastActiveAt - a.lastActiveAt)
  }

  /**
   * Return all active sibling digests (shorthand).
   */
  getActiveSiblings(currentSessionId: string): SessionDigest[] {
    return this.getSiblings(currentSessionId, false)
  }

  all(): SessionDigest[] {
    return Array.from(this.digests.values()).map(d => ({ ...d }))
  }


  /**
   * Score all sibling sessions against a query string.
   * Returns at most `limit` results sorted by descending score (>0 only).
   */
  searchSiblings(currentSessionId: string, query: string, limit = 5): Array<{ digest: SessionDigest; score: number }> {
    const q = query.toLowerCase()
    const terms = q.split(/\s+/).filter(Boolean)

    const results: Array<{ digest: SessionDigest; score: number }> = []

    for (const sibling of this.getSiblings(currentSessionId, true)) {
      const score = this.scoreDigest(sibling, terms)
      if (score > 0) results.push({ digest: sibling, score })
    }

    return results
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
  }

  private scoreDigest(d: SessionDigest, terms: string[]): number {
    const searchable = [
      d.topic,
      d.currentTask,
      ...d.filesActive,
      ...d.recentActions,
      ...d.decisions,
      ...d.learnings,
    ].join(' ').toLowerCase()

    let score = 0
    for (const term of terms) {
      // Count occurrences
      const re = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')
      const matches = searchable.match(re)?.length ?? 0
      score += matches

      // Bonus for topic / task match
      if (d.topic.toLowerCase().includes(term)) score += 3
      if (d.currentTask.toLowerCase().includes(term)) score += 2
      if (d.filesActive.some(f => f.toLowerCase().includes(term))) score += 2
    }

    // Recency bonus (active sessions score higher)
    if (d.isActive && score > 0) score += 1

    return score
  }


  /**
   * Send a message to another session's mailbox.
   * Returns the message ID.
   */
  sendMessage(toSessionId: string, fromSessionId: string, content: string): string {
    const from = this.digests.get(fromSessionId)
    const to   = this.digests.get(toSessionId)

    if (!to) {
      this.logger.warn('sendMessage: target session not found', { toSessionId })
      return ''
    }

    const id = `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const msg: SessionMessage = {
      id,
      fromSessionId,
      fromTopic: from?.topic ?? 'unknown',
      content,
      timestamp: Date.now(),
      read: false,
    }

    to.mailbox.push(msg)
    this.logger.info('message sent', { from: fromSessionId.slice(-8), to: toSessionId.slice(-8), id })
    return id
  }

  /**
   * Return unread messages for a session and mark them read.
   */
  readMailbox(sessionId: string): SessionMessage[] {
    const d = this.digests.get(sessionId)
    if (!d) return []

    const unread = d.mailbox.filter(m => !m.read)
    for (const m of unread) m.read = true
    return unread
  }

  /**
   * Peek at all mailbox messages (without marking read).
   */
  peekMailbox(sessionId: string): SessionMessage[] {
    return this.digests.get(sessionId)?.mailbox ?? []
  }


  /**
   * Remove digests for sessions that have been inactive for > `ttlMs`.
   * Call periodically (e.g. from a unified loop cycle hook) if you want
   * to limit memory growth for long-running daemons.
   */
  evictStale(ttlMs = DIGEST_ACTIVE_TTL_MS * 6): void {
    const cutoff = Date.now() - ttlMs
    for (const [id, d] of this.digests) {
      if (d.lastActiveAt < cutoff) {
        this.digests.delete(id)
        this.logger.debug('evicted stale digest', { sessionId: id.slice(-8) })
      }
    }
  }

  size(): number { return this.digests.size }


  private rehydrate(d: SessionDigest | undefined): SessionDigest | undefined {
    if (!d) return undefined
    const now = Date.now()
    d.isActive = (now - d.lastActiveAt) < DIGEST_ACTIVE_TTL_MS
    return d
  }
}


/**
 * @dep callers: makeStore (tests/intelligence/session-digest-ttl.test.ts), makeStore (tests/intelligence/session-digest-siblings.test.ts), makeStore (tests/intelligence/session-digest-formatting.test.ts), initializeSessionDigestStore (core/daemon/boot-pipeline-tools.ts), start (core/daemon.ts)
 * @dep module: Unknown
 * @dep risk: MEDIUM | 5 callers, 0 flows, 1 module
 */

export const createSessionDigestStore = (logger: ILogger): SessionDigestStore =>
  new SessionDigestStore(logger)


/**
 * Build the compact [SIBLING SESSIONS] block injected every turn.
 * Returns an empty string if there are no active siblings and no unread mail.
 * @dep callers: getDigestInjection (core/intelligence/injection-aggregator.ts), session-digest-formatting.test.ts (tests/intelligence/session-digest-formatting.test.ts)
 * @dep calls: readMailbox, getActiveSiblings, formatAgo
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function formatSiblingBlock(
  currentSessionId: string,
  store: SessionDigestStore,
): string {
  const siblings   = store.getActiveSiblings(currentSessionId)
  const unreadMsgs = store.readMailbox(currentSessionId)

  if (siblings.length === 0 && unreadMsgs.length === 0) return ''

  const lines: string[] = []
  lines.push(`[SIBLING SESSIONS — ${siblings.length} other active session(s)]`)

  for (const s of siblings) {
    const ago     = formatAgo(s.lastActiveAt)
    const files   = s.filesActive.length > 0 ? ` [${s.filesActive.slice(-3).join(', ')}]` : ''
    const task    = s.currentTask ? ` — ${s.currentTask.slice(0, 60)}` : ''
    lines.push(`• "${s.topic}"${task} (${ago}, ${s.turnCount} turns)${files}`)
  }

  if (unreadMsgs.length > 0) {
    lines.push('')
    lines.push('[MESSAGES FROM OTHER SESSIONS]')
    for (const m of unreadMsgs) {
      lines.push(`From "${m.fromTopic}": ${m.content.slice(0, 300)}`)
    }
    lines.push('[/MESSAGES]')
  }

  lines.push('[/SIBLING SESSIONS]')
  return lines.join('\n')
}

/**
 * @dep callers: formatSiblingBlock (core/intelligence/session-digest.ts), session-digest-formatting.test.ts (tests/intelligence/session-digest-formatting.test.ts)
 * @dep calls: now
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function formatAgo(ts: number): string {
  const diffMs  = Date.now() - ts
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1)  return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  return `${diffH}h ago`
}
