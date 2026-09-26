/**
 * SessionActivityStore — Chronological Activity Feed
 *
 * Maintains a live feed of all agent/team activity within a conversation session.
 * Tracks spawned agents, completions, failures, checkpoints, and budget usage.
 * Supports automatic result surfacing to parent sessions via event-driven notifications.
 *
 * Design goals:
 * - Chronological ordering: events stored in timestamp order for timeline reconstruction
 * - Parent-child tracking: link child sessions to parents for automatic notification
 * - Budget awareness: track token/iteration usage across all agents
 * - Query support: filter by event type, status, search text
 * - TTL-based cleanup: old events archived to prevent unbounded growth
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { EngramCreate, EngramType } from '@cassicore/mnemic-field'

export const ACTIVITY_TTL_MS = 60 * 60 * 1000  // 1 hour for active feed
export const MAX_EVENTS_PER_SESSION = 500

export type ActivityEventType =
  | 'agent:spawned'
  | 'agent:progress'
  | 'agent:completed'
  | 'agent:failed'
  | 'agent:timeout'
  | 'team:created'
  | 'team:checkpoint'
  | 'team:completed'
  | 'team:failed'
  | 'lumen:started'
  | 'lumen:posture:concluded'
  | 'lumen:completed'
  | 'lumen:failed'
  | 'dyad:started'
  | 'dyad:posture:concluded'
  | 'dyad:completed'
  | 'dyad:failed'
  | 'helix:started'
  | 'helix:posture:concluded'
  | 'helix:completed'
  | 'helix:failed'
  | 'subagent:spawned'
  | 'subagent:completed'
  | 'subagent:failed'

export interface ActivityEvent {
  id: string
  sessionId: string
  channelId: string  // For correlation (e.g., team ID, job ID)
  eventType: ActivityEventType
  timestamp: number
  summary: string
  metadata: {
    goal?: string
    result?: string
    confidence?: number
    tokenUsage?: { input: number; output: number }
    duration?: number
    agentType?: 'lumen' | 'dyad' | 'helix' | 'flux' | 'subagent'
    [key: string]: unknown
  }
  /** Parent session ID (if this was spawned from another session) */
  parentSessionId?: string
  /** Whether this event has been surfaced to the parent */
  surfaced: boolean
}

export interface SessionActivityFeed {
  sessionId: string
  events: ActivityEvent[]
  activeAgents: Set<string>  // sessionIds of active agents
  completedAgents: Set<string>  // sessionIds of completed agents
  budgetUsed: { tokens: number; iterations: number }
  lastUpdated: number
}

export interface ActivityQuery {
  sessionId: string
  limit?: number
  eventType?: string
  status?: 'all' | 'active' | 'completed' | 'failed'
  search?: string
  since?: number
}

export class SessionActivityStore {
  private readonly feeds = new Map<string, SessionActivityFeed>()
  private readonly eventIndex = new Map<string, ActivityEvent>()  // eventId → event
  private readonly byParentSession = new Map<string, Set<string>>()  // parentSessionId → Set<childSessionId>
  private readonly logger: ILogger
  private readonly eventBus?: IEventBus
  private mnemicField?: MnemicField

  constructor(logger: ILogger, eventBus?: IEventBus, mnemicField?: MnemicField) {
    this.logger = logger.child?.('session-activity-store') ?? logger
    this.eventBus = eventBus
    this.mnemicField = mnemicField
    this.wireEventListeners()
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }

  /**
   * Wire event bus listeners to automatically capture agent/team lifecycle events.
   */
  private wireEventListeners(): void {
    if (!this.eventBus) return

    // Cast to any for non-standard event names that are emitted with `as any` in daemon code
    const bus = this.eventBus as any

    bus.on('lumen:started', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId,
        channelId: event.sessionId,
        eventType: 'lumen:started',
        timestamp: Date.now(),
        summary: `Lumen analysis started: ${event.goal || 'Unknown goal'}`,
        metadata: {
          goal: event.goal,
          agentType: 'lumen',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
    })

    bus.on('lumen:completed', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId,
        channelId: event.sessionId,
        eventType: 'lumen:completed',
        timestamp: Date.now(),
        summary: `Lumen analysis completed: ${event.result?.conclusion || 'Analysis complete'}`,
        metadata: {
          goal: event.goal,
          result: event.result?.conclusion,
          confidence: event.result?.confidence,
          tokenUsage: event.tokenUsage,
          duration: event.duration,
          agentType: 'lumen',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
      this.markAgentCompleted(event.sessionId, event.parentSessionId)
    })

    bus.on('lumen:failed', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId,
        channelId: event.sessionId,
        eventType: 'lumen:failed',
        timestamp: Date.now(),
        summary: `Lumen analysis failed: ${event.error || 'Unknown error'}`,
        metadata: {
          goal: event.goal,
          result: event.error,
          agentType: 'lumen',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
      this.markAgentCompleted(event.sessionId, event.parentSessionId)
    })

    bus.on('dyad:started', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId,
        channelId: event.sessionId,
        eventType: 'dyad:started',
        timestamp: Date.now(),
        summary: `Dyad pipeline started: ${event.goal || 'Unknown goal'}`,
        metadata: {
          goal: event.goal,
          agentType: 'dyad',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
    })

    bus.on('dyad:completed', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId,
        channelId: event.sessionId,
        eventType: 'dyad:completed',
        timestamp: Date.now(),
        summary: `Dyad pipeline completed: ${event.result?.conclusion || 'Pipeline complete'}`,
        metadata: {
          goal: event.goal,
          result: event.result?.conclusion,
          tokenUsage: event.tokenUsage,
          duration: event.duration,
          agentType: 'dyad',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
      this.markAgentCompleted(event.sessionId, event.parentSessionId)
    })

    bus.on('helix:started', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId,
        channelId: event.sessionId,
        eventType: 'helix:started',
        timestamp: Date.now(),
        summary: `Helix session started: ${event.goal || 'Unknown goal'}`,
        metadata: {
          goal: event.goal,
          agentType: 'helix',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
    })

    bus.on('helix:completed', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId,
        channelId: event.sessionId,
        eventType: 'helix:completed',
        timestamp: Date.now(),
        summary: `Helix session completed: ${event.result?.conclusion || 'Session complete'}`,
        metadata: {
          goal: event.goal,
          result: event.result?.conclusion,
          confidence: event.result?.confidence,
          tokenUsage: event.tokenUsage,
          duration: event.duration,
          agentType: 'helix',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
      this.markAgentCompleted(event.sessionId, event.parentSessionId)
    })

    bus.on('subagent:spawned', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId,
        channelId: event.sessionId,
        eventType: 'subagent:spawned',
        timestamp: Date.now(),
        summary: `Subagent spawned: ${event.goal || 'Unknown task'}`,
        metadata: {
          goal: event.goal,
          agentType: 'subagent',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
      this.markAgentActive(event.sessionId, event.parentSessionId)
    })

    bus.on('subagent:completed', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId,
        channelId: event.sessionId,
        eventType: 'subagent:completed',
        timestamp: Date.now(),
        summary: `Subagent completed: ${event.result || 'Task complete'}`,
        metadata: {
          goal: event.goal,
          result: event.result,
          agentType: 'subagent',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
      this.markAgentCompleted(event.sessionId, event.parentSessionId)
    })

    bus.on('team:created', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId || 'global',
        channelId: event.teamId,
        eventType: 'team:created',
        timestamp: Date.now(),
        summary: `Team created: ${event.goal || 'Unknown goal'}`,
        metadata: {
          goal: event.goal,
          agentType: 'flux',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
    })

    bus.on('team:completed', (event: any) => {
      this.recordEvent({
        id: this.generateEventId(),
        sessionId: event.sessionId || 'global',
        channelId: event.teamId,
        eventType: 'team:completed',
        timestamp: Date.now(),
        summary: `Team completed: ${event.result || 'Goal achieved'}`,
        metadata: {
          goal: event.goal,
          result: event.result,
          agentType: 'flux',
        },
        parentSessionId: event.parentSessionId,
        surfaced: false,
      })
    })

    this.logger.info('SessionActivityStore: event listeners wired')
  }

  /**
   * Record an activity event.
   */
  recordEvent(event: ActivityEvent): void {
    // Track parent-child relationship
    if (event.parentSessionId) {
      if (!this.byParentSession.has(event.parentSessionId)) {
        this.byParentSession.set(event.parentSessionId, new Set())
      }
      this.byParentSession.get(event.parentSessionId)!.add(event.sessionId)
    }

    // Get or create feed for this session
    let feed = this.feeds.get(event.sessionId)
    if (!feed) {
      feed = {
        sessionId: event.sessionId,
        events: [],
        activeAgents: new Set(),
        completedAgents: new Set(),
        budgetUsed: { tokens: 0, iterations: 0 },
        lastUpdated: Date.now(),
      }
      this.feeds.set(event.sessionId, feed)
    }

    // Add event to feed
    feed.events.push(event)
    feed.lastUpdated = Date.now()

    // Enforce limits
    if (feed.events.length > MAX_EVENTS_PER_SESSION) {
      feed.events = feed.events.slice(-MAX_EVENTS_PER_SESSION)
    }

    // Index event for lookup
    this.eventIndex.set(event.id, event)
    this.writeReplayEngram(event)

    // Cleanup old events
    this.cleanupOldEvents(event.sessionId)

    this.logger.debug(`SessionActivityStore: recorded event ${event.id} (${event.eventType})`)
  }

  private writeReplayEngram(event: ActivityEvent): void {
    if (!this.mnemicField) return
    try {
      this.ensureReplaySession(event.sessionId, event.timestamp)
      if (event.parentSessionId) this.ensureReplaySession(event.parentSessionId, event.timestamp)
      const { id, nodeType } = this.replayEventIdentity(event)
      this.upsertReplayEngram({
        id,
        content: JSON.stringify(event),
        nodeType,
        t: event.timestamp,
        createdAt: new Date(event.timestamp).toISOString(),
        tags: ['session-replay', 'activity', event.eventType, event.metadata.agentType ?? 'unknown'],
        provenance: 'session-activity-store',
        metadata: {
          eventId: event.id,
          eventType: event.eventType,
          sessionId: event.sessionId,
          parentSessionId: event.parentSessionId,
          surfaced: event.surfaced,
        },
      })
      this.mnemicField.connect({ sourceId: id, targetId: `session:${event.sessionId}`, edgeType: 'part_of' })
      if (event.parentSessionId) {
        this.mnemicField.connect({ sourceId: `session:${event.sessionId}`, targetId: `session:${event.parentSessionId}`, edgeType: 'spawned_from' })
      }
    } catch (err) {
      this.logger.warn('SessionActivityStore replay engram write failed', { eventId: event.id, error: String(err) })
    }
  }

  private replayEventIdentity(event: ActivityEvent): { id: string; nodeType: EngramType } {
    if (event.eventType.includes('failed') || event.eventType.includes('timeout')) {
      return { id: `err:${event.id}`, nodeType: 'anomaly' }
    }
    if (event.eventType.includes('completed') || event.eventType.includes('concluded')) {
      return { id: `artifact:${event.id}`, nodeType: 'outcome' }
    }
    if (event.eventType.includes('checkpoint')) {
      return { id: `artifact:${event.id}`, nodeType: 'decision' }
    }
    return { id: `artifact:${event.id}`, nodeType: 'artifact' }
  }

  private ensureReplaySession(sessionId: string, timestamp: number): void {
    if (!this.mnemicField || this.mnemicField.get(`session:${sessionId}`)) return
    this.upsertReplayEngram({
      id: `session:${sessionId}`,
      content: JSON.stringify({ sessionId, source: 'session-activity-store' }),
      nodeType: 'session',
      t: timestamp,
      createdAt: new Date(timestamp).toISOString(),
      tags: ['session-replay', 'activity-session-stub'],
      provenance: 'session-activity-store',
      metadata: { sessionId, source: 'session-activity-store' },
    })
  }

  private upsertReplayEngram(input: EngramCreate): void {
    if (!this.mnemicField || !input.id) return
    const existing = this.mnemicField.get(input.id)
    if (existing) {
      this.mnemicField.update(input.id, {
        content: input.content,
        nodeType: input.nodeType,
        t: input.t,
        tags: input.tags,
        metadata: input.metadata,
      })
      return
    }
    this.mnemicField.store(input)
  }

  /**
   * Mark an agent as active.
   */
  markAgentActive(sessionId: string, parentSessionId?: string): void {
    if (parentSessionId) {
      const feed = this.feeds.get(parentSessionId)
      if (feed) {
        feed.activeAgents.add(sessionId)
        feed.completedAgents.delete(sessionId)
      }
    }
  }

  /**
   * Mark an agent as completed.
   */
  markAgentCompleted(sessionId: string, parentSessionId?: string): void {
    if (parentSessionId) {
      const feed = this.feeds.get(parentSessionId)
      if (feed) {
        feed.activeAgents.delete(sessionId)
        feed.completedAgents.add(sessionId)
      }
    }
  }

  /**
   * Get the activity feed for a session.
   */
  getFeed(sessionId: string, limit = 50): ActivityEvent[] {
    const feed = this.feeds.get(sessionId)
    if (!feed) return []

    const events = [...feed.events].sort((a, b) => b.timestamp - a.timestamp)
    return events.slice(0, limit)
  }

  /**
   * Get unsurfaced completion events for a parent session.
   */
  getUnsurfacedCompletions(parentSessionId: string): ActivityEvent[] {
    const feed = this.feeds.get(parentSessionId)
    if (!feed) return []

    const completions = feed.events.filter(
      e => (
        e.eventType.includes('completed') ||
        e.eventType.includes('failed') ||
        e.eventType.includes('timeout')
      ) &&
      !e.surfaced &&
      e.parentSessionId === parentSessionId
    )

    return completions.sort((a, b) => b.timestamp - a.timestamp)
  }

  /**
   * Mark an event as surfaced to the parent.
   */
  markSurfaced(eventId: string): void {
    const event = this.eventIndex.get(eventId)
    if (event) {
      event.surfaced = true
    }
  }

  /**
   * Get active agents for a session.
   */
  getActiveAgents(sessionId: string): string[] {
    const feed = this.feeds.get(sessionId)
    if (!feed) return []
    return Array.from(feed.activeAgents)
  }

  /**
   * Get completed agents for a session.
   */
  getCompletedAgents(sessionId: string): ActivityEvent[] {
    const feed = this.feeds.get(sessionId)
    if (!feed) return []

    const completedSessionIds = Array.from(feed.completedAgents)
    return feed.events.filter(
      e => completedSessionIds.includes(e.sessionId) &&
           (e.eventType.includes('completed') || e.eventType.includes('failed'))
    )
  }

  /**
   * Search events by query text.
   */
  searchEvents(sessionId: string, query: string, limit = 20): ActivityEvent[] {
    const feed = this.feeds.get(sessionId)
    if (!feed) return []

    const q = query.toLowerCase()
    const results = feed.events.filter(e =>
      e.summary.toLowerCase().includes(q) ||
      e.metadata.goal?.toLowerCase().includes(q) ||
      e.metadata.result?.toLowerCase().includes(q)
    )

    return results.sort((a, b) => b.timestamp - a.timestamp).slice(0, limit)
  }

  /**
   * Query events with filters.
   */
  queryEvents(options: ActivityQuery): ActivityEvent[] {
    const feed = this.feeds.get(options.sessionId)
    if (!feed) return []

    let events = [...feed.events]

    // Filter by event type
    if (options.eventType && options.eventType !== 'all') {
      if (options.eventType === 'completions') {
        events = events.filter(e => e.eventType.includes('completed') || e.eventType.includes('failed'))
      } else if (options.eventType === 'failures') {
        events = events.filter(e => e.eventType.includes('failed') || e.eventType.includes('timeout'))
      } else {
        events = events.filter(e => e.eventType.startsWith(options.eventType!))
      }
    }

    // Filter by status
    if (options.status && options.status !== 'all') {
      if (options.status === 'active') {
        events = events.filter(e => !e.eventType.includes('complete') && !e.eventType.includes('failed'))
      } else if (options.status === 'completed') {
        events = events.filter(e => e.eventType.includes('complete'))
      } else if (options.status === 'failed') {
        events = events.filter(e => e.eventType.includes('failed') || e.eventType.includes('timeout'))
      }
    }

    // Filter by time
    if (options.since) {
      events = events.filter(e => e.timestamp >= options.since!)
    }

    // Search filter
    if (options.search) {
      const q = options.search.toLowerCase()
      events = events.filter(e =>
        e.summary.toLowerCase().includes(q) ||
        e.metadata.goal?.toLowerCase().includes(q) ||
        e.metadata.result?.toLowerCase().includes(q)
      )
    }

    // Sort and limit
    return events.sort((a, b) => b.timestamp - a.timestamp).slice(0, options.limit || 50)
  }

  /**
   * Update budget usage for a session.
   */
  updateBudget(sessionId: string, delta: { tokens?: number; iterations?: number }): void {
    const feed = this.feeds.get(sessionId)
    if (!feed) return

    if (delta.tokens !== undefined) {
      feed.budgetUsed.tokens += delta.tokens
    }
    if (delta.iterations !== undefined) {
      feed.budgetUsed.iterations += delta.iterations
    }
    feed.lastUpdated = Date.now()
  }

  /**
   * Get budget usage for a session.
   */
  getBudgetUsage(sessionId: string): { tokens: number; iterations: number } {
    const feed = this.feeds.get(sessionId)
    if (!feed) return { tokens: 0, iterations: 0 }
    return { ...feed.budgetUsed }
  }

  /**
   * Get all child session IDs for a parent session.
   */
  getChildSessions(parentSessionId: string): string[] {
    const children = this.byParentSession.get(parentSessionId)
    if (!children) return []
    return Array.from(children)
  }

  /**
   * Get statistics about the store.
   */
  getStats(): {
    totalSessions: number
    totalEvents: number
    totalActiveAgents: number
    totalCompletedAgents: number
  } {
    let totalEvents = 0
    let totalActiveAgents = 0
    let totalCompletedAgents = 0

    for (const feed of Array.from(this.feeds.values())) {
      totalEvents += feed.events.length
      totalActiveAgents += feed.activeAgents.size
      totalCompletedAgents += feed.completedAgents.size
    }

    return {
      totalSessions: this.feeds.size,
      totalEvents,
      totalActiveAgents,
      totalCompletedAgents,
    }
  }

  /**
   * Cleanup old events beyond TTL.
   */
  private cleanupOldEvents(sessionId: string): void {
    const feed = this.feeds.get(sessionId)
    if (!feed) return

    const cutoff = Date.now() - ACTIVITY_TTL_MS
    feed.events = feed.events.filter(e => e.timestamp > cutoff)

    // Remove feed if empty and no active agents
    if (feed.events.length === 0 && feed.activeAgents.size === 0) {
      this.feeds.delete(sessionId)
    }
  }

  /**
   * Generate a unique event ID.
   */
  private generateEventId(): string {
    return `evt-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
  }
}
