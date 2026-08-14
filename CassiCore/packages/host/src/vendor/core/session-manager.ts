import { SESSION_SETTINGS, MODEL_DEFAULTS, getModelSpec } from '@cassicore/foundation'
import { generateShortId } from '@cassicore/utils'
import { contentLength } from '@cassicore/pipeline'

import type { SessionStore } from './session-store.js'
import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { ISessionManager, Session, SessionConfig, Message , ContentBlock } from '@cassicore/foundation'


export class SessionManager implements ISessionManager {
  private sessions = new Map<string, Session>()
  private senderIndex = new Map<string, string>()   // "channelId:senderId" → sessionId
  private sessionAccessTimes = new Map<string, number>() // sessionId → last access timestamp
  private pruneTimer: ReturnType<typeof setInterval> | null = null
  private pruneIntervalMs = 5 * 60 * 1000  // Default: 5 minutes
  private pruneMaxIdleMs = 2 * 60 * 60 * 1000  // Default: 2 hours

  // Write-behind persistence buffer
  private dirtySessionIds = new Set<string>()
  private persistTimer: ReturnType<typeof setInterval> | null = null
  private static readonly PERSIST_INTERVAL_MS = 5_000  // Flush every 5 seconds
  private static readonly MAX_DIRTY_SESSIONS = 50  // Force flush if this many dirty

  // Session limits for burst protection
  private readonly maxSessions: number
  private readonly maxSessionsWarningThreshold: number
  private static readonly DEFAULT_MAX_SESSIONS = 10000
  private static readonly WARNING_THRESHOLD_PERCENT = 0.9

  /**
   * Track recently-ended session IDs to suppress duplicate session:ended
   * emissions. A session can be ended multiple times due to pruning cycles
   * restoring sessions from disk and then re-pruning them. Entries expire
   * after 10 minutes.
   */
  private recentlyEnded = new Map<string, number>()
  private static readonly ENDED_TTL_MS = 10 * 60 * 1000

  constructor(
    private logger: ILogger,
    private defaultConfig: SessionConfig = {
      model: getModelSpec('main'),
      thinking: SESSION_SETTINGS.defaultThinking,
      maxContextTokens: SESSION_SETTINGS.defaultMaxContextTokens,
    },
    private store?: SessionStore,
    private bus?: IEventBus,
    maxSessions?: number,
  ) {
    this.maxSessions = maxSessions ?? SessionManager.DEFAULT_MAX_SESSIONS
    this.maxSessionsWarningThreshold = Math.floor(this.maxSessions * SessionManager.WARNING_THRESHOLD_PERCENT)

    // Start write-behind persistence timer
    this.persistTimer = setInterval(
      () => this.flushDirtySessions(),
      SessionManager.PERSIST_INTERVAL_MS
    )
  }


  setDefaultConfig(config: Partial<SessionConfig>): void {
    this.defaultConfig = { ...this.defaultConfig, ...config }
    this.logger.info(`updated default config: ${JSON.stringify(config)}`)
  }

  /**
   * Get or create a session for a channel/sender pair.
   * @param channelId - Channel identifier (e.g., "telegram", "discord")
   * @param senderId - Sender/user identifier within the channel
   * @param config - Optional session-specific configuration overrides
   */
  getOrCreate(channelId: string, senderId: string, config?: Partial<SessionConfig>): Session {
    const key = `${channelId}:${senderId}`

    // Hot path: in-memory lookup
    const existingId = this.senderIndex.get(key)
    if (existingId) {
      const session = this.sessions.get(existingId)!
      this.touchSession(existingId)
      return session
    }

    // Restore from disk if not in memory
    if (this.store) {
      const restored = this.store.findBySender(channelId, senderId)
      if (restored) {
        // Check if at capacity before adding restored session
        if (this.sessions.size >= this.maxSessions) {
          this.evictLRUSessions(1)
        }
        this.sessions.set(restored.id, restored)
        this.senderIndex.set(key, restored.id)
        this.sessionAccessTimes.set(restored.id, Date.now())
        this.logger.info(`restored session ${restored.id} for ${key} (${restored.history.length} turns)`)
        return restored
      }
    }

    // Create new session after capacity check
    if (this.sessions.size >= this.maxSessions) {
      const evictedCount = this.evictLRUSessions(1)
      if (evictedCount === 0) {
        this.logger.error('Session limit reached and eviction failed - cannot create new session', {
          maxSessions: this.maxSessions,
          currentSessions: this.sessions.size
        })
        throw new Error(`Session limit (${this.maxSessions}) reached. Cannot create new session.`)
      }
    }

    // Warn when approaching limit
    if (this.sessions.size >= this.maxSessionsWarningThreshold) {
      this.logger.warn('Approaching session limit', {
        current: this.sessions.size,
        threshold: this.maxSessionsWarningThreshold,
        max: this.maxSessions
      })
    }

    const id  = generateShortId(6)
    const now = new Date()
    const session: Session = {
      id,
      channelId,
      senderId,
      createdAt:    now,
      lastActiveAt: now,
      history:      [],
      tokenCount:   0,
      config:       { ...this.defaultConfig, ...(config || {}) },
    }

    this.sessions.set(id, session)
    this.senderIndex.set(key, id)
    this.sessionAccessTimes.set(id, now.getTime())
    this.logger.info(`created session ${id} for ${key}`)
    this.emitCreated(session)
    return session
  }

  /**
   * Get or create a session using a caller-supplied stable ID (e.g. "tg:12345").
   *
   * Channel workers maintain their own stable session IDs (Telegram uses "tg:<chatId>",
   * Discord uses "dc:<channelId>", etc.). Using the stable ID directly as the session ID
   * allows tokens emitted during turns to be routed back without an extra lookup table.
   */
  getOrCreateById(stableId: string, channelId: string, senderId: string, config?: Partial<SessionConfig>, opts?: { skipSenderLookup?: boolean }): Session {
    // Hot path: in-memory by stable ID
    const hot = this.sessions.get(stableId)
    if (hot) {
      this.touchSession(stableId)
      return hot
    }

    // Restore from disk by stable ID
    if (this.store) {
      const restored = this.store.load(stableId)
      if (restored) {
        if (this.sessions.size >= this.maxSessions) {
          this.evictLRUSessions(1)
        }
        this.sessions.set(restored.id, restored)
        const key = `${restored.channelId}:${restored.senderId}`
        this.senderIndex.set(key, restored.id)
        this.sessionAccessTimes.set(restored.id, Date.now())
        this.logger.info(`restored session ${restored.id} by stableId`)
        return restored
      }
    }

    // Fall back to sender-key lookup (handles legacy sessions created before stable IDs)
    // Skip when caller explicitly wants a fresh session (e.g., ACP newSession)
    const senderKey = `${channelId}:${senderId}`
    if (!opts?.skipSenderLookup) {
      const existingId = this.senderIndex.get(senderKey)
      if (existingId) {
        const session = this.sessions.get(existingId)!
        this.touchSession(existingId)
        return session
      }
      if (this.store) {
        const restored = this.store.findBySender(channelId, senderId)
        if (restored) {
          if (this.sessions.size >= this.maxSessions) {
            this.evictLRUSessions(1)
          }
          this.sessions.set(restored.id, restored)
          this.senderIndex.set(senderKey, restored.id)
          this.sessionAccessTimes.set(restored.id, Date.now())
          this.logger.info(`restored session ${restored.id} by sender key (stableId mismatch — old session)`)
          return restored
        }
      }
    }

    // Create fresh session with stable ID
    if (this.sessions.size >= this.maxSessions) {
      const evictedCount = this.evictLRUSessions(1)
      if (evictedCount === 0) {
        this.logger.error('Session limit reached and eviction failed - cannot create new session', {
          maxSessions: this.maxSessions,
          currentSessions: this.sessions.size
        })
        throw new Error(`Session limit (${this.maxSessions}) reached. Cannot create new session.`)
      }
    }

    // Warn when approaching limit
    if (this.sessions.size >= this.maxSessionsWarningThreshold) {
      this.logger.warn('Approaching session limit', {
        current: this.sessions.size,
        threshold: this.maxSessionsWarningThreshold,
        max: this.maxSessions
      })
    }

    const now = new Date()
    const session: Session = {
      id:           stableId,
      channelId,
      senderId,
      createdAt:    now,
      lastActiveAt: now,
      history:      [],
      tokenCount:   0,
      config:       { ...this.defaultConfig, ...(config || {}) },
    }

    this.sessions.set(stableId, session)
    this.senderIndex.set(senderKey, stableId)
    this.sessionAccessTimes.set(stableId, now.getTime())
    this.logger.info(`created session ${stableId} (stable ID) for ${senderKey}`)
    this.emitCreated(session)
    return session
  }

  private touchSession(sessionId: string): void {
    this.sessionAccessTimes.set(sessionId, Date.now())
  }

  /**
   * Evict least-recently-used sessions to free up capacity.
   */
  private evictLRUSessions(count: number): number {
    if (this.sessions.size === 0 || count <= 0) return 0

    // Sort by access time (oldest first)
    const entries = Array.from(this.sessionAccessTimes.entries())
    entries.sort((a, b) => a[1] - b[1])

    let evicted = 0
    for (let i = 0; i < Math.min(count, entries.length); i++) {
      const sessionId = entries[i][0]
      const session = this.sessions.get(sessionId)
      
      if (session) {
        // WHY: permanent sessions (e.g. module sessions) must not be evicted
        if (session.config.permanent) continue
        // Persist to disk before eviction
        if (this.store) {
          try {
            this.store.save(session)
          } catch (err) {
            this.logger.warn(`Failed to persist session ${sessionId} before eviction`, { error: String(err) })
          }
        }
        
        // Remove from in-memory structures
        this.sessions.delete(sessionId)
        this.sessionAccessTimes.delete(sessionId)
        const key = `${session.channelId}:${session.senderId}`
        this.senderIndex.delete(key)
        
        this.logger.info(`Evicted LRU session ${sessionId} due to capacity pressure`, {
          lastAccessed: new Date(entries[i][1]).toISOString(),
          sessionAge: Date.now() - entries[i][1]
        })
        evicted++
      }
    }

    if (evicted > 0) {
      this.emitMetric('session:evicted', { count: evicted, remaining: this.sessions.size })
    }

    return evicted
  }

  get(sessionId: string): Session | undefined {
    // Hot path: in-memory lookup
    const hot = this.sessions.get(sessionId)
    if (hot) {
      this.touchSession(sessionId)
      return hot
    }

    // Try disk — may be a session from a different sender key (e.g. CLI re-using a UUID directly)
    if (this.store) {
      const restored = this.store.load(sessionId)
      if (restored) {
        // Check capacity before restoring
        if (this.sessions.size >= this.maxSessions) {
          this.evictLRUSessions(1)
        }
        this.sessions.set(restored.id, restored)
        const key = `${restored.channelId}:${restored.senderId}`
        this.senderIndex.set(key, restored.id)
        this.sessionAccessTimes.set(restored.id, Date.now())
        this.logger.info(`lazy-restored session ${restored.id}`)
        return restored
      }
    }

    return undefined
  }

  addTurn(sessionId: string, message: Message): void {
    const s = this.sessions.get(sessionId)
    if (!s) throw new Error(`session ${sessionId} not found`)
    s.history.push(message)
    const estimate = Math.ceil(contentLength(message.content) / 4)
    s.tokenCount += estimate
    s.lastActiveAt = new Date()
    this.touchSession(sessionId)

    // Mark dirty for write-behind persistence
    this.dirtySessionIds.add(sessionId)

    // Force flush if too many dirty sessions
    if (this.dirtySessionIds.size >= SessionManager.MAX_DIRTY_SESSIONS) {
      this.flushDirtySessions()
    }
  }

  /**
   * Update session token count after turn completion.
   * Called by TurnPipeline with actual token count from provider.
   */
  addTokens(sessionId: string, tokensUsed: number): void {
    const s = this.sessions.get(sessionId)
    if (!s) throw new Error(`session ${sessionId} not found`)
    // Replace estimate with actual token count
    s.tokenCount += tokensUsed
    this.touchSession(sessionId)

    // Mark dirty for write-behind persistence
    this.dirtySessionIds.add(sessionId)
    if (this.dirtySessionIds.size >= SessionManager.MAX_DIRTY_SESSIONS) {
      this.flushDirtySessions()
    }
  }

  private flushDirtySessions(): void {
    if (this.dirtySessionIds.size === 0 || !this.store) return

    const toFlush = [...this.dirtySessionIds]
    this.dirtySessionIds.clear()

    for (const id of toFlush) {
      const session = this.sessions.get(id)
      if (session) {
        try {
          this.store.save(session)
        } catch (err) {
          this.logger.error('Failed to persist session', {
            sessionId: id,
            error: String(err),
          })
          // Re-mark as dirty for next flush
          this.dirtySessionIds.add(id)
        }
      }
    }

    if (toFlush.length > 0) {
      this.logger.debug('Flushed dirty sessions', { count: toFlush.length })
    }
  }

  clear(sessionId: string): void {
    const s = this.sessions.get(sessionId)
    if (!s) throw new Error(`session ${sessionId} not found`)
    s.history = []
    s.tokenCount = 0
    this.touchSession(sessionId)
    // Persist the cleared state
    if (this.store) {
      try { this.store.save(s) } catch {}
    }
    this.logger.info(`cleared session ${sessionId}`)
  }

  delete(sessionId: string): void {
    const s = this.sessions.get(sessionId)
    if (!s) return
    this.sessions.delete(sessionId)
    this.sessionAccessTimes.delete(sessionId)
    const key = `${s.channelId}:${s.senderId}`
    this.senderIndex.delete(key)
    // Remove from persistent storage
    if (this.store && (this.store as any).remove) {
      try { (this.store as any).remove(sessionId) } catch {}
    }
    this.logger.info(`deleted session ${sessionId}`)
    this.emitEnded(s, 'deleted')

    // Track recently-ended to suppress duplicate events
    this.recentlyEnded.set(sessionId, Date.now())
    setTimeout(() => this.recentlyEnded.delete(sessionId), SessionManager.ENDED_TTL_MS)
  }

  /**
   * List all active sessions, sorted by lastActiveAt descending.
   */
  list(): Session[] {
    const sessions = new Map<string, Session>()

    // Add in-memory sessions
    for (const [id, s] of this.sessions) {
      sessions.set(id, s)
    }

    // Merge from persistent storage (if available)
    if (this.store && (this.store as any).listAll) {
      try {
        const stored = (this.store as any).listAll() as Session[]
        if (Array.isArray(stored)) {
          for (const s of stored) {
            if (!sessions.has(s.id)) {
              sessions.set(s.id, s)
            }
          }
        }
      } catch {}
    }

    // Sort by lastActiveAt descending
    return Array.from(sessions.values()).sort((a, b) =>
      b.lastActiveAt.getTime() - a.lastActiveAt.getTime()
    )
  }

  count(): number {
    return this.sessions.size
  }

  getLimits(): { current: number; max: number; threshold: number } {
    return {
      current: this.sessions.size,
      max: this.maxSessions,
      threshold: this.maxSessionsWarningThreshold
    }
  }

  /**
   * Start automatic pruning of idle sessions.
   */
  startPruning(intervalMs = this.pruneIntervalMs, maxIdleMs = this.pruneMaxIdleMs): void {
    // Clear existing timer if restarting
    if (this.pruneTimer) {
      clearInterval(this.pruneTimer)
      this.pruneTimer = null
    }
    this.pruneIntervalMs = intervalMs
    this.pruneMaxIdleMs = maxIdleMs
    this.pruneTimer = setInterval(() => this.prune(), intervalMs)
    this.logger.info('automatic pruning started', { intervalMs, maxIdleMs })
  }

  stopPruning(): void {
    if (this.pruneTimer) {
      clearInterval(this.pruneTimer)
      this.pruneTimer = null
    }
    this.logger.info('automatic pruning stopped')
  }

  prune(): number {
    const now = Date.now()
    let pruned = 0
    for (const [id, s] of this.sessions) {
      // WHY: permanent sessions (e.g. module sessions) must not be pruned
      if (s.config.permanent) continue
      if (now - s.lastActiveAt.getTime() > this.pruneMaxIdleMs) {
        // Persist before pruning
        if (this.store) {
          try { this.store.save(s) } catch {}
        }
        
        this.sessions.delete(id)
        this.sessionAccessTimes.delete(id)
        const key = `${s.channelId}:${s.senderId}`
        this.senderIndex.delete(key)
        this.logger.debug(`pruned idle session ${id}`)
        this.emitEnded(s, 'pruned')

        this.recentlyEnded.set(id, Date.now())
        setTimeout(() => this.recentlyEnded.delete(id), SessionManager.ENDED_TTL_MS)

        pruned++
      }
    }
    if (pruned > 0) {
      this.logger.info(`pruned ${pruned} idle session(s)`)
      this.logger.debug('pruned idle sessions', { count: pruned, remaining: this.sessions.size })
    }
    return pruned
  }

  pruneAll(): number {
    // Clear in-memory structures
    this.sessions.clear()
    this.senderIndex.clear()
    this.sessionAccessTimes.clear()

    // Delegate to store
    if (this.store && (this.store as any).pruneAll) {
      try {
        return (this.store as any).pruneAll() as number
      } catch { return 0 }
    }
    return 0
  }

  pruneByChannelId(channelId: string): void {
    for (const [id, s] of this.sessions) {
      if (s.channelId === channelId) {
        this.sessions.delete(id)
        this.sessionAccessTimes.delete(id)
        const key = `${s.channelId}:${s.senderId}`
        this.senderIndex.delete(key)
      }
    }
  }

  pruneEmpty(): void {
    for (const [id, s] of this.sessions) {
      if (s.history.length === 0) {
        this.sessions.delete(id)
        this.sessionAccessTimes.delete(id)
        const key = `${s.channelId}:${s.senderId}`
        this.senderIndex.delete(key)
      }
    }
  }

  pruneOlderThan(days: number): number {
    const cutoffMs = days * 24 * 60 * 60 * 1000
    const now = Date.now()
    let pruned = 0

    for (const [id, s] of this.sessions) {
      if (now - s.lastActiveAt.getTime() > cutoffMs) {
        this.sessions.delete(id)
        this.sessionAccessTimes.delete(id)
        const key = `${s.channelId}:${s.senderId}`
        this.senderIndex.delete(key)
        pruned++
      }
    }

    // Also prune from persistent storage
    if (this.store && (this.store as any).prune) {
      try { (this.store as any).prune() } catch {}
    }

    return pruned
  }


  private emitCreated(session: Session): void {
    if (!this.bus) return
    this.bus.emit({
      type: 'session:created',
      sessionId: session.id,
      channelId: session.channelId,
      senderId: session.senderId,
    } as any)
  }

  private emitEnded(session: Session, reason: string): void {
    // Suppress duplicate events for recently-ended sessions
    if (this.recentlyEnded.has(session.id)) {
      return
    }

    if (!this.bus) return
    this.bus.emit({
      type: 'session:ended',
      sessionId: session.id,
      channelId: session.channelId,
      senderId: session.senderId,
      reason,
    } as any)
  }

  private emitMetric(type: string, data: Record<string, unknown>): void {
    if (!this.bus) return
    this.bus.emit({ type, ...data } as any)
  }

  setBus(bus: IEventBus): void {
    this.bus = bus
  }

  save(sessionId: string): void {
    const session = this.sessions.get(sessionId)
    if (!session) return
    if (!this.store) return
    try {
      this.store.save(session)
    } catch (err) {
      this.logger.warn(`Failed to save session ${sessionId}`, { error: String(err) })
    }
  }

  /**
   * Shutdown session manager: stop timers and flush dirty sessions.
   */
  async shutdown(): Promise<void> {
    // Stop timers
    if (this.persistTimer) {
      clearInterval(this.persistTimer)
      this.persistTimer = null
    }
    if (this.pruneTimer) {
      clearInterval(this.pruneTimer)
      this.pruneTimer = null
    }
    this.flushDirtySessions()
  }
}

/**
 * Factory for creating a SessionManager from config values.
 * @dep callers: bootPipelineTools (core/daemon/boot-pipeline-tools.ts), start (core/daemon.ts)
 * @dep calls: getModelSpec
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export const createSessionManager = (
  logger: ILogger,
  systemPrompt: string,
  store?: SessionStore,
  defaultModel?: string,
  thinking?: import('@cassicore/foundation').ThinkingLevel,
  bus?: IEventBus,
): SessionManager =>
  new SessionManager(
    logger,
    {
      model:            defaultModel ?? getModelSpec('main'),
      thinking:         thinking ?? SESSION_SETTINGS.defaultThinking,
      maxContextTokens: SESSION_SETTINGS.defaultMaxContextTokens,
      systemPrompt,
    },
    store,
    bus,
  )
