/**
 * LiveWorkflowHarness — executes workflow scenarios against a running CassiCore daemon.
 *
 * Uses the admin API endpoints:
 * - POST /sessions/:id/turn  { content }  → execute a turn
 * - GET  /events/stream       (SSE)       → subscribe to events
 * - GET  /events/history      ?sessionId  → query past events
 * - GET  /state               ?sessionId  → build state snapshot
 * - DELETE /sessions/:id                  → cleanup
 *
 * Test sessions use a `__test__` prefix for isolation and auto-pruning.
 */

import { EventTraceCollector } from '../verification/event-trace.js'
import { StateSnapshot } from '../verification/state-snapshot.js'
import type { WorkflowBackend, TurnResult } from '../verification/scenario-types.js'
import type { RuntimeEvent } from '@cassicore/foundation'
import { createHash } from 'node:crypto'

const DEFAULT_BASE_URL = 'http://127.0.0.1:7433'
const TEST_SESSION_PREFIX = '__test__'
const DEFAULT_TURN_TIMEOUT = 30_000
const VERIFY_CHANNEL_ID = 'channel:verify'
const VERIFY_SENDER_PREFIX = 'workflow-verifier:'

export interface LiveHarnessOptions {
  /** Base URL of the CassiCore admin API */
  baseUrl?: string
  /** Timeout for individual turn executions (ms) */
  turnTimeoutMs?: number
  /** Whether to auto-prune test sessions on teardown */
  autoPrune?: boolean
}

export class LiveWorkflowHarness implements WorkflowBackend {
  private readonly baseUrl: string
  private readonly turnTimeoutMs: number
  private autoPrune: boolean
  private readonly eventCollector: LiveEventCollector
  private readonly sessions: Set<string> = new Set()
  private _trace: EventTraceCollector | null = null

  /** Maps test session IDs to real session IDs (pipeline may assign different IDs) */
  private readonly sessionMapping = new Map<string, string>()

  constructor(options: LiveHarnessOptions = {}) {
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, '')
    this.turnTimeoutMs = options.turnTimeoutMs ?? DEFAULT_TURN_TIMEOUT
    this.autoPrune = options.autoPrune ?? true
    this.eventCollector = new LiveEventCollector(this.baseUrl)
  }


  async createSession(config?: Record<string, unknown>): Promise<string> {
    const id = `${TEST_SESSION_PREFIX}${randomHex(8)}`
    this.sessions.add(id)

    const predictedSessionId = this.predictPipelineSessionId(id)
    this.sessionMapping.set(id, predictedSessionId)
    this.sessions.add(predictedSessionId)

    // Start event collection for this session
    await this.eventCollector.start(predictedSessionId)
    this._trace = null // Invalidate cached trace

    // Ensure the session exists by sending a lightweight turn
    // or simply return the ID — the session auto-creates on first turn
    return id
  }

  async executeTurn(sessionId: string, message: string): Promise<TurnResult> {
    const startTime = Date.now()

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), this.turnTimeoutMs)

    try {
      const res = await fetch(`${this.baseUrl}/sessions/${encodeURIComponent(sessionId)}/turn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: message,
          channelId: VERIFY_CHANNEL_ID,
          senderId: `${VERIFY_SENDER_PREFIX}${sessionId}`,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Turn failed (${res.status}): ${text}`)
      }

      const data = await res.json() as any

      // Pipeline may assign a different session ID — track the mapping
      const realSessionId = data.sessionId
      if (realSessionId && realSessionId !== sessionId) {
        const previousReal = this.sessionMapping.get(sessionId)
        this.sessionMapping.set(sessionId, realSessionId)
        this.sessions.add(realSessionId) // Track for cleanup

        // Restart event collection on the real session ID if it changed
        if (previousReal !== realSessionId) {
          this.eventCollector.stop()
          await this.eventCollector.start(realSessionId)
          this._trace = null
        }
      }

      // Allow a brief moment for events to be emitted and collected
      await new Promise(resolve => setTimeout(resolve, 500))
      // Force a poll to capture trailing events
      await this.eventCollector.poll()

      return {
        response: data.response ?? '',
        durationMs: Date.now() - startTime,
        model: data.model,
        tokensUsed: data.tokensUsed,
        toolCalls: data.toolCalls,
      }
    } finally {
      clearTimeout(timeout)
    }
  }

  async snapshot(sessionId?: string): Promise<StateSnapshot> {
    const requestedSid = sessionId ?? this.firstSession()
    // Resolve to the real session ID if pipeline remapped it
    const sid = requestedSid ? (this.sessionMapping.get(requestedSid) ?? requestedSid) : undefined

    // Build state from session API and health data
    let stateData: any = {}
    let sessionState: any = undefined

    if (sid) {
      // Fetch session details from the /sessions listing (more reliable than /state)
      const sessionsRes = await fetch(`${this.baseUrl}/sessions`).catch(() => null)
      if (sessionsRes?.ok) {
        const sessionsData = await sessionsRes.json() as any
        const sessionInfo = sessionsData.sessions?.find((s: any) => s.id === sid)
        if (sessionInfo) {
          const histLen = sessionInfo.historyLength ?? 0
          sessionState = {
            turnCount: Math.floor(histLen / 2), // user + assistant = 1 turn
            messageCount: histLen,
            lastModel: sessionInfo.model,
          }
        }
      }
      // Also try /state for additional intelligence/trust data
      const res = await fetch(`${this.baseUrl}/state?sessionId=${encodeURIComponent(sid)}`).catch(() => null)
      if (res?.ok) stateData = await res.json()
    } else {
      // Daemon-level snapshot — fetch health + sessions for a top-level view
      const [healthRes, sessionsRes] = await Promise.all([
        fetch(`${this.baseUrl}/health`).catch(() => null),
        fetch(`${this.baseUrl}/sessions`).catch(() => null),
      ])
      const health = healthRes?.ok ? await healthRes.json() as any : {}
      const sessions = sessionsRes?.ok ? await sessionsRes.json() as any : {}
      stateData = {
        daemon: {
          status: health.status ?? 'unknown',
          uptimeMs: health.uptimeMs,
          memoryMb: health.memoryMb,
          version: health.version,
        },
        sessions: {
          count: sessions.sessions?.length ?? 0,
          ids: sessions.sessions?.map((s: any) => s.id) ?? [],
        },
      }
    }

    // Also get event counts from the trace
    const trace = this.trace
    const byType: Record<string, number> = {}
    for (const event of trace.dump()) {
      byType[event.type] = (byType[event.type] ?? 0) + 1
    }

    return StateSnapshot.fromLiveData({
      session: sessionState ?? stateData.session ?? (sid ? stateData : undefined),
      intelligence: stateData.intelligence,
      trust: stateData.trust,
      custom: !sid ? stateData : undefined,
      events: {
        totalEmitted: trace.length,
        byType,
      },
    })
  }

  get trace(): EventTraceCollector {
    // Always build from latest collected events — no caching, since events
    // arrive asynchronously via polling after each turn.
    return EventTraceCollector.fromArray(this.eventCollector.collected)
  }

  async teardown(): Promise<void> {
    // Stop event collection
    this.eventCollector.stop()

    // Delete test sessions
    if (this.autoPrune) {
      const deletePromises = Array.from(this.sessions).map(async (sid) => {
        try {
          await fetch(`${this.baseUrl}/sessions/${encodeURIComponent(sid)}`, {
            method: 'DELETE',
          })
        } catch {
          // Best-effort cleanup
        }
      })
      await Promise.all(deletePromises)
    }

    this.sessions.clear()
    this.sessionMapping.clear()
    this._trace = null
  }


  /** Check if the daemon is reachable */
  async ping(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/health`, { signal: AbortSignal.timeout(3000) })
      return res.ok
    } catch {
      return false
    }
  }

  /** Get all session IDs created by this harness */
  getSessionIds(): string[] {
    return Array.from(this.sessions)
  }

  /** Get the event collector's raw timeline (for debugging) */
  timeline(): string {
    return this.trace.timeline()
  }


  private firstSession(): string | undefined {
    return Array.from(this.sessions)[0]
  }

  private predictPipelineSessionId(sessionId: string): string {
    return createHash('sha256')
      .update(`${VERIFY_CHANNEL_ID}:${VERIFY_SENDER_PREFIX}${sessionId}`)
      .digest('hex')
      .slice(0, 16)
  }
}


/**
 * Collects events from the daemon's SSE stream, filtered to a specific session.
 *
 * Uses GET /events/history for polling-based collection (more reliable than
 * SSE for short-lived test scenarios where SSE connection setup latency
 * could cause missed events).
 */
class LiveEventCollector {
  private events: Array<RuntimeEvent & { _tracedAt: number }> = []
  private sessionId: string | null = null
  private pollingInterval: ReturnType<typeof setInterval> | null = null
  private lastSeen = 0
  private running = false

  constructor(private readonly baseUrl: string) {}

  get collected(): Array<RuntimeEvent & { _tracedAt: number }> {
    return this.events
  }

  async start(sessionId: string): Promise<void> {
    this.sessionId = sessionId
    this.events = []
    this.lastSeen = 0
    this.running = true

    // Poll events/history every 200ms for reliability
    // (SSE has connection setup latency that can miss early events)
    this.pollingInterval = setInterval(() => {
      if (this.running) this.poll().catch(() => {})
    }, 200)
  }

  stop(): void {
    this.running = false
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval)
      this.pollingInterval = null
    }
    // Do one final poll to capture any trailing events
    this.poll().catch(() => {})
  }

  /** Manual poll — also called automatically on interval */
  async poll(): Promise<void> {
    if (!this.sessionId) return

    try {
      const url = `${this.baseUrl}/events/history?sessionId=${encodeURIComponent(this.sessionId)}&since=${this.lastSeen}&limit=500`
      const res = await fetch(url, { signal: AbortSignal.timeout(5000) })
      if (!res.ok) return

      const data = await res.json() as any
      if (!data.events || !Array.isArray(data.events)) return

      for (const event of data.events) {
        // Deduplicate by eventId
        const isDuplicate = this.events.some(
          (e: any) => e.eventId && event.eventId && e.eventId === event.eventId
        )
        if (!isDuplicate) {
          this.events.push({
            ...event,
            _tracedAt: event.timestamp ?? Date.now(),
          })
          if (event.timestamp && event.timestamp > this.lastSeen) {
            this.lastSeen = event.timestamp
          }
        }
      }
    } catch {
      // Polling failure is non-fatal
    }
  }
}


function randomHex(length: number): string {
  const chars = '0123456789abcdef'
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars[Math.floor(Math.random() * 16)]
  }
  return result
}
