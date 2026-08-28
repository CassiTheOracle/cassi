/**
 * @cassicore/mind-runtime — mind-side session mirror store.
 *
 * The spine mirrors ohmypi session lifecycle events (`session_start/switch/branch/
 * compact/shutdown`) into the runtime over `/v1/session/mirror`. This store keeps
 * a thin, id-keyed record of those mirrored sessions in a shape the retained tools
 * (`list_sessions`, `debug_session`, `system_health`) can read — giving the runtime
 * a `sessionManager`-like surface WITHOUT re-implementing ohmypi's session tree.
 *
 * The retained tool handlers expect an `ISessionManager`-shaped `list()` (sessions
 * with `id, channelId, history, lastActiveAt, tokenCount, status`) — this store
 * satisfies that structural read surface; the write surface (`getOrCreate`,
 * `addTurn`, …) is intentionally no-op because ohmypi owns session writes (plan §4.4).
 */

import type { MirrorSessionRequest, MindMirroredSession, SessionMirrorEvent } from './channel/protocol.js'

/** Full ISessionManager-shaped surface the retained tools compile against. */
export interface MindSessionManagerSurface {
  list(): MindMirroredSession[]
  get(sessionId: string): MindMirroredSession | undefined
  getOrCreate(channelId: string, senderId: string): MindMirroredSession
  getOrCreateById(stableId: string, channelId: string, senderId: string): MindMirroredSession
  addTurn(sessionId: string, _msg: unknown): void
  clear(sessionId: string): void
  delete(sessionId: string): void
  /** The current frontmost session (used by cassandra_query_events). */
  currentSessionId?: string
}

export class MindSessionMirror implements MindSessionManagerSurface {
  private sessions = new Map<string, MindMirroredSession>()
  currentSessionId?: string

  /** Apply a mirrored lifecycle event, creating/updating the session record. */
  mirror(req: MirrorSessionRequest): void {
    const now = new Date()
    const existing = this.sessions.get(req.sessionId)
    const base: MindMirroredSession = existing ?? {
      id: req.sessionId,
      channelId: 'mirrored',
      history: [],
      config: {},
      createdAt: now.toISOString(),
      status: 'active',
    }
    base.lastEvent = req.event
    base.lastActiveAt = now.toISOString()
    base.branchFrom = req.branchFrom ?? base.branchFrom
    base.summary = req.summary ?? base.summary
    base.cwd = req.cwd ?? base.cwd
    if (req.event === 'start' || req.event === 'switch') this.currentSessionId = req.sessionId
    if (req.event === 'compact') base.status = 'compacted'
    if (req.event === 'shutdown') base.status = 'shutdown'
    this.sessions.set(req.sessionId, base)
  }

  list(): MindMirroredSession[] {
    return [...this.sessions.values()]
  }

  get(sessionId: string): MindMirroredSession | undefined {
    return this.sessions.get(sessionId)
  }

  getOrCreate(channelId: string, senderId: string): MindMirroredSession {
    const id = `${channelId}:${senderId}`
    return this.getOrCreateById(id, channelId, senderId)
  }

  getOrCreateById(stableId: string, channelId: string, senderId: string): MindMirroredSession {
    const existing = this.sessions.get(stableId)
    if (existing) return existing
    const created: MindMirroredSession = {
      id: stableId,
      channelId,
      history: [],
      config: { senderId },
      createdAt: new Date().toISOString(),
      lastActiveAt: new Date().toISOString(),
      tokenCount: 0,
      status: 'active',
    }
    this.sessions.set(stableId, created)
    return created
  }

  addTurn(_sessionId: string, _msg: unknown): void {
    // ohmypi owns session writes; no-op on the mirror.
  }

  clear(sessionId: string): void {
    const s = this.sessions.get(sessionId)
    if (s) s.history = []
  }

  delete(sessionId: string): void {
    this.sessions.delete(sessionId)
  }

  /** Human-readable event list for `/v1/snapshot`. */
  snapshotEntries(): Array<{ id: string; lastEvent?: string; lastActiveAt?: string }> {
    return this.list().map(s => ({
      id: s.id,
      lastEvent: s.lastEvent,
      lastActiveAt: s.lastActiveAt,
    }))
  }
}

// re-export for consumers of the mirror type
export type { SessionMirrorEvent }
