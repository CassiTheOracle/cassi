import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import type { ILogger } from '../types/interfaces.js'
import type { DialecticStreamEvent } from '../types/dialectic.js'
import { createToolsApi } from './tools-api.js'
import { assembleContext } from './intelligence/context-assembler.js'
import { listProviderConfigKeys } from './providers/centralized.js'
import { getModelSpec } from './config/system-settings.js'

// WebSocket state
interface WSConnection {
  socket: any
  sessionId: string
  subscribed: boolean
}

export function createAdminApi(daemon: any, logger: ILogger) {
  let unixPath = path.join(os.homedir(), '.cassicore', 'admin.sock')
  const tcpHost = (daemon?.config?.get?.('admin.host', '127.0.0.1')) ?? '127.0.0.1'
  const baseTcpPort = Number(daemon?.config?.get?.('admin.port', 7433)) || 7433
  let currentTcpPort = baseTcpPort

  // WebSocket connections store
  const wsConnections = new Map<string, WSConnection>()
  let wsConnectionId = 0

  // ── B7: Session hierarchy tracking (populated via subagent_start/subagent_end events) ──
  interface SessionHierarchyEntry {
    parentId: string | null
    childIds: Set<string>
    startedAt?: number
    endedAt?: number
    agentType?: string
    steps?: number
    durationMs?: number
  }
  const sessionHierarchyMap = new Map<string, SessionHierarchyEntry>()

  // ── T2: Subagent session ID → CassiCore team ID mapping ──
  const subagentToTeamMap = new Map<string, string>()

  // ── T3: Delegation requests — CassiCore-driven subagent spawning ──────────
  interface DelegationRequest {
    /** Unique delegation ID */
    id: string
    /** Target session to delegate from (the parent session) */
    sessionId: string
    /** Goal/prompt for the subagent */
    goal: string
    /** Suggested agent type for the subagent */
    agentType: 'code' | 'explore' | 'general' | 'researcher' | 'search'
    /** Priority: higher = more urgent */
    priority: 'low' | 'medium' | 'high' | 'critical'
    /** Why CassiCore wants to delegate */
    reason: string
    /** Estimated complexity of the delegated task */
    estimatedComplexity: 'low' | 'moderate' | 'high' | 'very-high'
    /** Packaged session context for the subagent (from packageSessionContext) */
    contextPreamble: string
    /** When this delegation request was created */
    createdAt: number
    /** Request expires after this timestamp (avoid stale delegations) */
    expiresAt: number
  }

  type DelegationStatus = 'pending' | 'acknowledged' | 'executing' | 'completed' | 'failed' | 'expired'

  interface DelegationTracking {
    request: DelegationRequest
    status: DelegationStatus
    /** The OpenCode session ID of the spawned subagent (set by plugin ack) */
    spawnedSessionId?: string
    /** The CassiCore team ID wrapping this subagent (set when T2 links it) */
    teamId?: string
    acknowledgedAt?: number
    completedAt?: number
    result?: string
  }

  /** Active delegation requests and their tracking state */
  const delegationTracker = new Map<string, DelegationTracking>()

  /** Sessions that have already had delegation computed this cycle (dedup within buildInjectPayload) */
  let lastDelegationComputeTime = 0
  const DELEGATION_COMPUTE_INTERVAL_MS = 5000 // Don't recompute more often than every 5 seconds
  const DELEGATION_EXPIRY_MS = 60_000 // Requests expire after 60 seconds
  const DELEGATION_MAX_PENDING = 3 // Max pending delegations at a time

  /** Ensure a hierarchy entry exists for the given session ID. */
  function ensureHierarchyEntry(sid: string): SessionHierarchyEntry {
    let entry = sessionHierarchyMap.get(sid)
    if (!entry) {
      entry = { parentId: null, childIds: new Set() }
      sessionHierarchyMap.set(sid, entry)
    }
    return entry
  }

  /** Process a subagent lifecycle event to update the hierarchy map. Called inline from /events/ingest.
   *  The bridge plugin sends events with fields at top level (not nested under .data):
   *    { type: "subagent_start", sessionId, parentSessionId, agentType, ... }
   *    { type: "subagent_end", sessionId, parentSessionId, agentType, steps, ... }
   *
   *  T2 enhancement: Also creates/completes external CassiCore teams wrapping the subagent.
   *  New fields from plugin (T2-9):
   *    subagent_start: { ..., taskPrompt?, taskDescription? }
   *    subagent_end:   { ..., resultText?, resultSummary?, tokensUsed? }
   */
  function processHierarchyEvent(event: any): void {
    if (event.type === 'subagent_start') {
      // Plugin sends childId as event.sessionId, parentId as event.parentSessionId (top-level)
      const childId = event.childSessionId || event.sessionId
      const parentId = event.parentSessionId || event.parentId
      if (!childId || !parentId) return

      // Register child → parent link
      const childEntry = ensureHierarchyEntry(childId)
      childEntry.parentId = parentId
      childEntry.startedAt = event.timestamp || Date.now()
      if (event.agentType) childEntry.agentType = event.agentType

      // Register parent → child link
      const parentEntry = ensureHierarchyEntry(parentId)
      parentEntry.childIds.add(childId)

      logger.debug('[admin-api] Session hierarchy updated', { childId, parentId, agentType: event.agentType })

      // ── T2: Create external team wrapping this subagent ──
      const to = daemon.intelligence?.teamOrchestrator as any
      if (to?.createTeam) {
        try {
          // Build goal from task prompt/description or fallback
          const goalText = event.taskPrompt
            || event.taskDescription
            || `OpenCode subagent task (${event.agentType || 'general'})`

          const teamName = event.taskDescription
            ? `Subagent: ${event.taskDescription.slice(0, 60)}`
            : `Subagent: ${event.agentType || 'task'}`

          const team = to.createTeam({
            name: teamName,
            goal: goalText,
            external: true,
            externalSessionId: childId,
            externalParentSessionId: parentId,
            checkpoint: { mode: 'none' },
            budget: {
              maxTokens: 200_000,   // Generous default for subagents
              maxAgents: 1,         // External teams have exactly 1 agent (the subagent)
              maxDepth: 1,
              maxDurationMs: 30 * 60 * 1000, // 30 min
            },
            metadata: {
              agentType: event.agentType,
              source: 'opencode-subagent',
            },
          })

          // Map subagent session → team ID for completion routing
          subagentToTeamMap.set(childId, team.id)

          // ── T3: Reverse-link delegation tracking to team ──
          // If this subagent was created by a T3 delegation, the ack may have
          // arrived before the team was created. Link them now.
          for (const tracking of delegationTracker.values()) {
            if (tracking.spawnedSessionId === childId && !tracking.teamId) {
              tracking.teamId = team.id
              logger.debug('[admin-api] T3: Linked delegation to team', {
                delegationId: tracking.request.id,
                teamId: team.id,
              })
            }
          }

          logger.info('[admin-api] External team created for subagent', {
            teamId: team.id,
            childId,
            parentId,
            agentType: event.agentType,
            goalPreview: goalText.slice(0, 100),
          })
        } catch (err) {
          logger.error('[admin-api] Failed to create external team for subagent', {
            childId,
            parentId,
            error: String(err),
          })
        }
      }
    } else if (event.type === 'subagent_end') {
      const childId = event.childSessionId || event.sessionId
      if (!childId) return

      const entry = sessionHierarchyMap.get(childId)
      if (entry) {
        entry.endedAt = event.timestamp || Date.now()
        if (event.steps != null) entry.steps = event.steps
        if (event.durationMs != null) entry.durationMs = event.durationMs
      }

      // ── T2: Complete the external team wrapping this subagent ──
      const teamId = subagentToTeamMap.get(childId)
      if (teamId) {
        const to = daemon.intelligence?.teamOrchestrator as any
        if (to?.completeExternalTeam) {
          try {
            to.completeExternalTeam(teamId, {
              summary: event.resultSummary || event.taskDescription || undefined,
              output: event.resultText || undefined,
              error: event.error || undefined,
              tokensUsed: event.tokensUsed || 0,
              durationMs: event.durationMs || (entry ? (entry.endedAt! - (entry.startedAt || 0)) : undefined),
              success: !event.error,
            })

            logger.info('[admin-api] External team completed for subagent', {
              teamId,
              childId,
              success: !event.error,
              tokensUsed: event.tokensUsed,
            })
          } catch (err) {
            logger.error('[admin-api] Failed to complete external team', {
              teamId,
              childId,
              error: String(err),
            })
          }
        }

        // Clean up mapping (team is finalized)
        subagentToTeamMap.delete(childId)
      }

      // ── T3: Complete delegation tracking for this subagent ──
      for (const tracking of delegationTracker.values()) {
        if (tracking.spawnedSessionId === childId && tracking.status === 'executing') {
          tracking.status = 'completed'
          tracking.completedAt = Date.now()
          tracking.result = event.resultSummary || event.resultText || 'Subagent completed'
          logger.info('[admin-api] T3: Delegation completed via subagent_end', {
            delegationId: tracking.request.id,
            childId,
          })
          break
        }
      }
    } else if (event.type === 'subagent_prompt_captured') {
      // ── T2: Update external team's goal with the actual task prompt ──
      // This event arrives after subagent_start, once messages.transform captures
      // the first user message (which IS the task prompt).
      const childId = event.sessionId
      if (!childId) return

      const teamId = subagentToTeamMap.get(childId)
      if (teamId) {
        const to = daemon.intelligence?.teamOrchestrator as any
        const team = to?.teams?.get?.(teamId)
        if (team && event.taskPrompt) {
          // Update the team's goal with the actual task prompt
          team.config.goal = event.taskPrompt
          // Update root goal description in the goal tree
          const goalTree = to.goalTrees?.get?.(teamId)
          const rootGoal = goalTree?.get?.(team.rootGoalId)
          if (rootGoal) {
            rootGoal.description = event.taskPrompt
            if (event.taskDescription) {
              rootGoal.title = event.taskDescription
            }
          }
          // Update team name if we have a better description
          if (event.taskDescription) {
            team.config.name = `Subagent: ${event.taskDescription.slice(0, 60)}`
          }

          logger.debug('[admin-api] External team goal enriched with task prompt', {
            teamId,
            childId,
            promptLength: event.taskPrompt.length,
            description: event.taskDescription?.slice(0, 80),
          })
        }
      }
    }
  }

  /** Serialize the hierarchy map for inject.json. */
  function serializeSessionHierarchy(): Record<string, { parentId?: string; childIds: string[] }> {
    const result: Record<string, { parentId?: string; childIds: string[] }> = {}
    for (const [sid, entry] of sessionHierarchyMap) {
      result[sid] = {
        ...(entry.parentId ? { parentId: entry.parentId } : {}),
        childIds: Array.from(entry.childIds),
      }
    }
    return result
  }

  function sendJSON(res: http.ServerResponse, code: number, obj: unknown) {
    const s = JSON.stringify(obj)
    res.writeHead(code, { 'Content-Type': 'application/json' })
    res.end(s)
  }

  // SSE connection store
  const sseConnections = new Map<string, { res: http.ServerResponse; sessionId: string; connectedAt: number }>()
  let sseConnectionId = 0

  /**
   * Extract first user message from session history
   */
  function getFirstUserMessage(history: any[]): string {
    for (const msg of history) {
      if (msg.role === 'user') {
        const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
        return content.slice(0, 200) || '(empty message)'
      }
    }
    return '(no messages)'
  }

  /**
   * Extract last user message from session history
   */
  function getLastUserMessage(history: any[]): string {
    let lastMessage = '(no messages)'
    for (const msg of history) {
      if (msg.role === 'user') {
        const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
        lastMessage = content.slice(0, 200) || '(empty message)'
      }
    }
    return lastMessage
  }

  /**
   * Build state snapshot from event history
   */
  function buildStateSnapshot(sessionId: string, events: any[]): any {
    const snapshot: any = {
      sessionId,
      connected: true,
      lastEventTimestamp: 0,
      turnIndex: 0,
      isStreaming: false,
      messageCount: 0,
      activeTools: [],
      activeToolCalls: [],
      totalTokensUsed: 0,
    }

    const activeToolCalls = new Map<string, { toolCallId: string; toolName: string; startTime: number }>()

    for (const event of events) {
      snapshot.lastEventTimestamp = Math.max(snapshot.lastEventTimestamp, event.timestamp || 0)

      switch (event.type) {
        case 'session_start':
          snapshot.sessionStartTime = event.timestamp
          break
        case 'agent_start':
          snapshot.turnIndex = event.turnIndex || 0
          snapshot.model = event.model
          break
        case 'streaming_start':
          snapshot.isStreaming = true
          break
        case 'streaming_end':
          snapshot.isStreaming = false
          break
        case 'user_message':
        case 'assistant_message':
          snapshot.messageCount++
          break
        case 'assistant_message':
          snapshot.totalTokensUsed += (event.inputTokens || 0) + (event.outputTokens || 0)
          break
        case 'tool_execution_start':
          activeToolCalls.set(event.toolCallId, {
            toolCallId: event.toolCallId,
            toolName: event.toolName,
            startTime: event.timestamp,
          })
          break
        case 'tool_execution_end':
          activeToolCalls.delete(event.toolCallId)
          break
        case 'model_select':
          snapshot.model = event.model
          break
        case 'context_usage':
          snapshot.contextUsage = {
            tokens: event.tokens,
            contextWindow: event.contextWindow,
            percent: event.percent,
          }
          break
      }
    }

    snapshot.activeToolCalls = Array.from(activeToolCalls.values())
    return snapshot
  }

  /**
   * Send SSE event to all connections for a session
   */
  function broadcastSSE(sessionId: string, event: any): void {
    const data = JSON.stringify(event)
    const message = [
      `id: ${event.eventId || `evt_${Date.now()}`}`,
      `event: ${event.type}`,
      `data: ${data}`,
      '',
    ].join('\n')

    for (const [id, conn] of sseConnections) {
      if (conn.sessionId === sessionId) {
        try {
          conn.res.write(message + '\n')
        } catch {
          // Connection closed
          sseConnections.delete(id)
        }
      }
    }
  }

  function parseBody(req: http.IncomingMessage): Promise<any> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = []
      req.on('data', (c) => chunks.push(Buffer.from(c)))
      req.on('end', () => {
        if (chunks.length === 0) return resolve(undefined)
        try {
          const s = Buffer.concat(chunks).toString('utf8')
          resolve(JSON.parse(s))
        } catch (err) {
          reject(err)
        }
      })
      req.on('error', reject)
    })
  }

  function authOk(req: http.IncomingMessage) {
    try {
      const token = daemon.config?.get?.('admin.token', undefined as string | undefined)
      if (!token) return true
      const h = req.headers['authorization']
      if (!h || Array.isArray(h)) return false
      return h === `Bearer ${token}`
    } catch (err) {
      return true
    }
  }

  /** Resolve latest active team ID when none is specified */
  function resolveLatestTeamId(to: any): string | undefined {
    const all = to.listAllTeams()
    const active = all.find((t: any) => t.status === 'running' || t.status === 'paused')
    return active?.id || all[all.length - 1]?.id
  }

  /**
   * Set up WebSocket connection handling
   */
  async function handleWebSocketUpgrade(req: http.IncomingMessage, socket: any, head: Buffer) {
    const url = new URL(req.url || '', `http://${tcpHost}:${currentTcpPort}`)
    const parts = url.pathname.split('/').filter(Boolean)
    
    // Only handle /dialectic/:sessionId/stream WebSocket connections
    if (parts[0] !== 'dialectic' || parts.length !== 3 || parts[2] !== 'stream') {
      socket.destroy()
      return
    }
    
    const sessionId = parts[1]
    if (!sessionId) {
      socket.destroy()
      return
    }

    // Accept WebSocket connection (minimal implementation)
    const key = req.headers['sec-websocket-key']
    if (!key) {
      socket.destroy()
      return
    }

    // Generate accept key
    const crypto = await import('node:crypto')
    const acceptKey = crypto.createHash('sha1')
      .update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11')
      .digest('base64')

    // Send handshake response
    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      `Sec-WebSocket-Accept: ${acceptKey}\r\n` +
      '\r\n'
    )

    const connId = `ws-${++wsConnectionId}`
    const conn: WSConnection = { socket, sessionId, subscribed: true }
    wsConnections.set(connId, conn)

    logger.info(`[admin-api] WebSocket connected for dialectic stream: ${sessionId}`)

    // Subscribe to dialectic events for this session
    const unsubscribe = daemon.intelligence?.dialectic?.subscribeToStream?.(sessionId, (event: DialecticStreamEvent) => {
      if (!conn.subscribed || socket.destroyed) return
      try {
        const message = JSON.stringify(event)
        sendWebSocketMessage(socket, message)
      } catch (err) {
        logger.warn(`[admin-api] WebSocket send error: ${String(err)}`)
      }
    })

    // Handle close
    socket.on('close', () => {
      conn.subscribed = false
      wsConnections.delete(connId)
      unsubscribe?.()
      logger.info(`[admin-api] WebSocket disconnected: ${sessionId}`)
    })

    socket.on('error', (err: any) => {
      logger.warn(`[admin-api] WebSocket error: ${String(err)}`)
      socket.destroy()
    })
  }

  /**
   * Send a text message over WebSocket
   */
  function sendWebSocketMessage(socket: any, message: string) {
    // Minimal WebSocket text frame encoding (no fragmentation)
    const msgBuf = Buffer.from(message, 'utf8')
    const len = msgBuf.length
    
    let frame: Buffer
    if (len < 126) {
      frame = Buffer.allocUnsafe(2 + len)
      frame[0] = 0x81 // FIN=1, opcode=text
      frame[1] = len
      msgBuf.copy(frame, 2)
    } else if (len < 65536) {
      frame = Buffer.allocUnsafe(4 + len)
      frame[0] = 0x81
      frame[1] = 126
      frame.writeUInt16BE(len, 2)
      msgBuf.copy(frame, 4)
    } else {
      frame = Buffer.allocUnsafe(10 + len)
      frame[0] = 0x81
      frame[1] = 127
      frame.writeBigUInt64BE(BigInt(len), 2)
      msgBuf.copy(frame, 10)
    }
    
    socket.write(frame)
  }

  // Helper: shallow/object checks and deep merge for nested object merges
  function isObject(v: unknown): v is Record<string, unknown> {
    return typeof v === 'object' && v !== null && !Array.isArray(v)
  }

  function mergeDeep(target: any, src: any): any {
    if (!isObject(target) || !isObject(src)) return src
    const out: any = { ...target }
    for (const k of Object.keys(src)) {
      if (isObject(src[k])) {
        out[k] = mergeDeep(out[k] ?? {}, src[k])
      } else {
        out[k] = src[k]
      }
    }
    return out
  }

  async function handler(req: http.IncomingMessage, res: http.ServerResponse) {
    if (!authOk(req)) {
      sendJSON(res, 401, { error: 'unauthorized' })
      return
    }

    const url = new URL(req.url || '', `http://${tcpHost}:${currentTcpPort}`)
    const parts = url.pathname.split('/').filter(Boolean)

    try {
      // ── Health endpoints ───────────────────────────────────────────────────

      if (req.method === 'GET' && url.pathname === '/health') {
        // Try to pull the latest snapshot from the HealthMonitor
        const monitor = daemon.healthMonitor
        const snapshot = monitor?.latest?.()

        if (snapshot) {
          // Full rich response
          const httpCode = snapshot.overall === 'ok' ? 200
            : snapshot.overall === 'degraded' ? 200   // degraded still serves traffic
            : 503
          return sendJSON(res, httpCode, {
            status:         snapshot.overall,
            timestamp:      snapshot.timestamp,
            uptimeMs:       snapshot.uptimeMs,
            memoryMb:       snapshot.memoryMb,
            eventLoopLagMs: snapshot.eventLoopLagMs,
            version:        daemon.config?.get?.('daemon.version', '0.1.2') ?? '0.1.2',
            checks:         snapshot.checks,
          })
        }

        // Fallback: monitor not yet initialised — return minimal response
        return sendJSON(res, 200, {
          status:  'starting',
          uptime:  process.uptime(),
          version: daemon.config?.get?.('daemon.version', '0.1.2') ?? '0.1.2',
        })
      }

      // GET /health/history — rolling snapshot window
      if (req.method === 'GET' && url.pathname === '/health/history') {
        const monitor = daemon.healthMonitor
        const history = monitor?.getHistory?.() ?? []
        return sendJSON(res, 200, history)
      }

      // POST /health/check — trigger an immediate check and return the result
      if (req.method === 'POST' && url.pathname === '/health/check') {
        const monitor = daemon.healthMonitor
        if (!monitor) return sendJSON(res, 503, { error: 'health monitor not initialised' })
        const snapshot = await monitor.runChecks()
        return sendJSON(res, snapshot.overall === 'down' ? 503 : 200, snapshot)
      }

      // ── Context payload (replaces inject.json file-based IPC) ─────────────
      // GET /context — serves the full bridge-plugin context via Unix socket
      if (req.method === 'GET' && url.pathname === '/context') {
        try {
          const payload = await buildInjectPayload()
          return sendJSON(res, 200, payload)
        } catch (err) {
          logger.error('[admin-api] GET /context failed', { error: String(err) })
          return sendJSON(res, 500, { error: 'Failed to build context payload' })
        }
      }

      // ── Event Ingestion (from CLI) ─────────────────────────────────────────
      // POST /events/ingest - Receive events from CLI extension bridge
      if (req.method === 'POST' && url.pathname === '/events/ingest') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object' || !body.sessionId || !Array.isArray(body.events)) {
            return sendJSON(res, 400, { error: 'expected { sessionId, events: [...] }' })
          }

          // Import event bus types
          const { getEventBus } = await import('./events/index.js')
          const eventBus = getEventBus()

          let ingested = 0
          const errors: string[] = []

          for (const event of body.events) {
            try {
              // Ensure required fields
              if (!event.eventId) {
                event.eventId = `evt_${Date.now()}_${Math.random().toString(36).slice(2)}`
              }
              if (!event.timestamp) {
                event.timestamp = Date.now()
              }
              if (!event.sessionId) {
                event.sessionId = body.sessionId
              }

              // B7: Intercept subagent lifecycle events to track session hierarchy
              processHierarchyEvent(event)

              eventBus.emit(event)
              ingested++
            } catch (err) {
              errors.push(String(err))
            }
          }

          return sendJSON(res, 200, { ingested, errors: errors.length > 0 ? errors : undefined })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /events/history?sessionId=xxx&since=xxx&limit=xxx
      if (req.method === 'GET' && url.pathname === '/events/history') {
        const sessionId = url.searchParams.get('sessionId')
        if (!sessionId) return sendJSON(res, 400, { error: 'sessionId required' })

        try {
          const { getEventBus } = await import('./events/index.js')
          const eventBus = getEventBus()

          const since = parseInt(url.searchParams.get('since') || '0', 10)
          const limit = parseInt(url.searchParams.get('limit') || '100', 10)
          const eventTypes = url.searchParams.get('eventTypes')?.split(',') || []

          let events = eventBus.getEventsSince(sessionId, since)
          if (eventTypes.length > 0) {
            events = events.filter(e => eventTypes.includes(e.type))
          }

          const total = events.length
          const hasMore = total > limit
          events = events.slice(0, limit)

          return sendJSON(res, 200, { events, total, hasMore })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /state?sessionId=xxx - Get current session state snapshot
      if (req.method === 'GET' && url.pathname === '/state') {
        const sessionId = url.searchParams.get('sessionId')
        if (!sessionId) return sendJSON(res, 400, { error: 'sessionId required' })

        try {
          const { getEventBus } = await import('./events/index.js')
          const eventBus = getEventBus()

          const events = eventBus.getAllEvents(sessionId)
          const snapshot = buildStateSnapshot(sessionId, events)

          return sendJSON(res, 200, snapshot)
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /events/stream?sessionId=xxx - SSE endpoint for real-time events
      // sessionId is optional: omit (or use "*") for a global all-sessions stream
      if (req.method === 'GET' && url.pathname === '/events/stream') {
        const sessionId = url.searchParams.get('sessionId') || null
        const globalStream = !sessionId || sessionId === '*'

        try {
          // Import event bus and subscribe
          const { getEventBus } = await import('./events/index.js')
          const eventBus = getEventBus()

          // Check for lastEventId for replay
          const lastEventId = url.searchParams.get('lastEventId')
          let missedEvents: any[] = []
          if (lastEventId && !globalStream) {
            const match = lastEventId.match(/evt_(\d+)_/)
            if (match) {
              const since = parseInt(match[1], 10)
              missedEvents = eventBus.getEventsSince(sessionId!, since)
            }
          }

          // Setup SSE headers
          res.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
          })

          const connId = `sse_${++sseConnectionId}`
          // For global streams, store as '*' so broadcastSSE can filter correctly
          const connSessionId = sessionId ?? '*'
          const conn = { res, sessionId: connSessionId, connectedAt: Date.now() }
          sseConnections.set(connId, conn)

          // Send missed events
          for (const event of missedEvents) {
            const data = JSON.stringify(event)
            res.write([
              `id: ${event.eventId}`,
              `event: ${event.type}`,
              `data: ${data}`,
              '',
            ].join('\n') + '\n')
          }

          // Send connected event
          const connectedEvent = {
            type: 'sse_connected',
            sessionId: connSessionId,
            timestamp: Date.now(),
            eventId: `evt_${Date.now()}`,
          }
          res.write([
            `id: ${connectedEvent.eventId}`,
            `event: ${connectedEvent.type}`,
            `data: ${JSON.stringify(connectedEvent)}`,
            '',
          ].join('\n') + '\n')

          // Subscribe to event bus — global stream receives all events, session stream filters by sessionId
          const unsubscribe = eventBus.onAll((event: any) => {
            if (globalStream || event.sessionId === sessionId) {
              broadcastSSE(connSessionId, event)
            }
          })

          // Handle disconnect
          res.on('close', () => {
            sseConnections.delete(connId)
            unsubscribe.unsubscribe()
          })

          return // Don't end response - keep connection open
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Context Window Debugging ───────────────────────────────────────────

      // GET /debug/context-window?sessionId=xxx - Get latest context window snapshot
      if (req.method === 'GET' && url.pathname === '/debug/context-window') {
        const sessionId = url.searchParams.get('sessionId')
        if (!sessionId) return sendJSON(res, 400, { error: 'sessionId required' })

        try {
          const { getContextWindowDebugger } = await import('./events/index.js')
          const ctxDebugger = getContextWindowDebugger()

          if (!ctxDebugger) {
            return sendJSON(res, 503, { error: 'Context window debugging not enabled' })
          }

          const snapshot = ctxDebugger.getLatestSnapshot(sessionId)
          if (!snapshot) {
            return sendJSON(res, 404, { error: 'No context window snapshot found for this session' })
          }

          return sendJSON(res, 200, { snapshot })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /debug/context-window/history?sessionId=xxx&since=xxx - Get snapshot history
      if (req.method === 'GET' && url.pathname === '/debug/context-window/history') {
        const sessionId = url.searchParams.get('sessionId')
        if (!sessionId) return sendJSON(res, 400, { error: 'sessionId required' })

        try {
          const { getContextWindowDebugger } = await import('./events/index.js')
          const ctxDebugger = getContextWindowDebugger()

          if (!ctxDebugger) {
            return sendJSON(res, 503, { error: 'Context window debugging not enabled' })
          }

          const since = url.searchParams.get('since') ? parseInt(url.searchParams.get('since')!, 10) : 0
          const snapshots = since 
            ? ctxDebugger.getSnapshotsSince(sessionId, since)
            : ctxDebugger.getSnapshots(sessionId)

          return sendJSON(res, 200, { 
            sessionId, 
            snapshots,
            count: snapshots.length,
            stats: ctxDebugger.getStats(sessionId)
          })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /debug/context-window/stream?sessionId=xxx - SSE stream for context window updates
      if (req.method === 'GET' && url.pathname === '/debug/context-window/stream') {
        const sessionId = url.searchParams.get('sessionId')
        if (!sessionId) return sendJSON(res, 400, { error: 'sessionId required' })

        try {
          const { getEventBus, getContextWindowDebugger } = await import('./events/index.js')
          const eventBus = getEventBus()
          const ctxDebugger = getContextWindowDebugger()

          if (!ctxDebugger) {
            return sendJSON(res, 503, { error: 'Context window debugging not enabled' })
          }

          // Send current snapshot first
          const latest = ctxDebugger.getLatestSnapshot(sessionId)

          // Setup SSE headers
          res.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
          })

          const connId = `ctx_sse_${++sseConnectionId}`
          const conn = { res, sessionId, connectedAt: Date.now() }
          sseConnections.set(connId, conn)

          // Send current snapshot as initial event
          if (latest) {
            res.write([
              `id: ${latest.eventId}`,
              `event: context_window_snapshot`,
              `data: ${JSON.stringify(latest)}`,
              '',
            ].join('\n') + '\n')
          }

          // Subscribe to context window events only
          const unsubscribe = eventBus.onAll((event: any) => {
            if (event.sessionId === sessionId && 
                (event.type === 'context_window_snapshot' || event.type === 'context_window_diff')) {
              const data = JSON.stringify(event)
              try {
                res.write([
                  `id: ${event.eventId}`,
                  `event: ${event.type}`,
                  `data: ${data}`,
                  '',
                ].join('\n') + '\n')
              } catch {
                // Connection closed
                sseConnections.delete(connId)
                unsubscribe.unsubscribe()
              }
            }
          })

          // Handle disconnect
          res.on('close', () => {
            sseConnections.delete(connId)
            unsubscribe.unsubscribe()
          })

          return // Keep connection open
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /debug/context-window/stats?sessionId=xxx - Get context window statistics
      if (req.method === 'GET' && url.pathname === '/debug/context-window/stats') {
        const sessionId = url.searchParams.get('sessionId')
        if (!sessionId) return sendJSON(res, 400, { error: 'sessionId required' })

        try {
          const { getContextWindowDebugger } = await import('./events/index.js')
          const ctxDebugger = getContextWindowDebugger()

          if (!ctxDebugger) {
            return sendJSON(res, 503, { error: 'Context window debugging not enabled' })
          }

          const stats = ctxDebugger.getStats(sessionId)
          return sendJSON(res, 200, { sessionId, stats })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /debug/context-window/clear - Clear context window history for a session
      if (req.method === 'POST' && url.pathname === '/debug/context-window/clear') {
        try {
          const body = await parseBody(req)
          const sessionId = body?.sessionId

          if (!sessionId) return sendJSON(res, 400, { error: 'sessionId required in body' })

          const { getContextWindowDebugger } = await import('./events/index.js')
          const ctxDebugger = getContextWindowDebugger()

          if (!ctxDebugger) {
            return sendJSON(res, 503, { error: 'Context window debugging not enabled' })
          }

          ctxDebugger.clearSession(sessionId)
          return sendJSON(res, 200, { ok: true, message: `Context window history cleared for ${sessionId}` })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /health/providers — detailed provider health including quota status
      if (req.method === 'GET' && url.pathname === '/health/providers') {
        const providerHealth: Array<{
          id: string
          status: 'ok' | 'degraded' | 'down'
          models: string[]
          accounts?: Array<{
            profileId: string
            status: 'ok' | 'degraded' | 'down'
            quotaStatus?: 'healthy' | 'low' | 'exhausted'
            tokenExpiry?: number
            tokenExpiresIn?: number
            error?: string
          }>
        }> = []

        // Access providers from the daemon's provider map or intelligence layer
        const providers = (daemon as any).providers || new Map<string, any>()
        
        // Helper to unwrap CentralizedProvider
        function unwrapProvider(p: any): any {
          return p?.wrapped || p
        }
        
        for (const [id, provider] of providers) {
          const health: any = {
            id,
            status: 'ok' as const,
            models: (provider as any).models || [],
          }

          // Qwen load balancer - check each account
          const unwrapped = unwrapProvider(provider)
          if (id === 'qwen' && (unwrapped as any).accounts) {
            const lb = unwrapped as any
            health.accounts = []
            
            for (let i = 0; i < lb.accounts.length; i++) {
              const acc = lb.accounts[i]
              const stats = lb.stats?.[i]
              const accountHealth: any = {
                profileId: acc.profileId,
                status: stats?.cooldownUntil && Date.now() < stats.cooldownUntil ? 'degraded' : 'ok',
                tokenExpiry: acc.credentials?.expires,
                tokenExpiresIn: acc.credentials?.expires ? acc.credentials.expires - Date.now() : undefined,
              }

              // Check if token is expired
              if (acc.credentials?.expires && acc.credentials.expires < Date.now()) {
                accountHealth.status = 'down'
                accountHealth.error = 'Token expired'
              }

              // Try a test ping to check quota
              try {
                const testProvider = lb.providers?.[i]
                if (testProvider) {
                  const pingResult = await testProvider.ping()
                  if (!pingResult) {
                    accountHealth.status = 'degraded'
                    accountHealth.quotaStatus = 'exhausted'
                    accountHealth.error = 'Quota exceeded or service unavailable'
                  } else {
                    accountHealth.quotaStatus = 'healthy'
                  }
                }
              } catch (err: any) {
                const errMsg = String(err?.message || err)
                if (errMsg.includes('quota') || errMsg.includes('429')) {
                  accountHealth.quotaStatus = 'exhausted'
                  accountHealth.status = 'degraded'
                } else if (errMsg.includes('auth') || errMsg.includes('token')) {
                  accountHealth.status = 'down'
                }
                accountHealth.error = errMsg
              }

              health.accounts.push(accountHealth)
            }

            // Overall status based on accounts
            const allDown = health.accounts.every((a: any) => a.status === 'down')
            const anyOk = health.accounts.some((a: any) => a.status === 'ok')
            health.status = allDown ? 'down' : (anyOk ? 'ok' : 'degraded')
          }

          providerHealth.push(health)
        }

        return sendJSON(res, 200, {
          timestamp: new Date().toISOString(),
          providers: providerHealth,
        })
      }

      if (req.method === 'GET' && parts[0] === 'config' && parts.length === 1) {
        return sendJSON(res, 200, daemon.config.toJSON())
      }

      if (parts[0] === 'config' && parts.length === 2) {
        const key = parts[1]
        if (req.method === 'GET') {
          const val = daemon.config.get(key as string, undefined)
          const source = val === undefined ? 'default' : 'file'
          return sendJSON(res, 200, { key, value: val, source })
        }
        if (req.method === 'POST') {
          const body = await parseBody(req)
          if (!body || !('value' in body)) return sendJSON(res, 400, { error: 'missing value' })
          daemon.__admin_overrides = daemon.__admin_overrides || {}
          daemon.__admin_overrides[key] = { value: body.value, reason: body.reason }
          return sendJSON(res, 200, { key, value: body.value })
        }
        if (req.method === 'DELETE') {
          daemon.__admin_overrides = daemon.__admin_overrides || {}
          delete daemon.__admin_overrides[key]
          return sendJSON(res, 200, { key, removed: true })
        }
      }

      // POST /config/set — set arbitrary config keys (set-and-persist) with nested merge support
      if (req.method === 'POST' && url.pathname === '/config/set') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing body' })
          const layered = (daemon.config as any)
          const updated: string[] = []

          if (Array.isArray(body.updates)) {
            for (const u of body.updates) {
              if (!u || typeof u.key !== 'string' || !Object.prototype.hasOwnProperty.call(u, 'value')) continue
              const k = String(u.key)
              const v = u.value
              try {
                if (typeof layered?.setOverride === 'function') {
                  const existing = layered.get(k, undefined)
                  const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
                  layered.setOverride(k, newVal, { reason: u.reason || 'admin' })
                } else {
                  daemon.__admin_overrides = daemon.__admin_overrides || {}
                  daemon.__admin_overrides[k] = { value: v, reason: u.reason || 'admin' }
                }
                updated.push(k)
              } catch (err) { /* continue */ }
            }
          } else if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
            const k = String(body.key)
            const v = body.value
            try {
              if (typeof layered?.setOverride === 'function') {
                const existing = layered.get(k, undefined)
                const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
                layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                daemon.__admin_overrides[k] = { value: v, reason: body.reason || 'admin' }
              }
              updated.push(k)
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          } else {
            return sendJSON(res, 400, { error: 'expected { key, value } or { updates: [{ key, value }] }' })
          }

          try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch {}
          try { if (typeof daemon.reload === 'function') await daemon.reload(); else daemon.bus.emit({ type: 'config:reloaded' }) } catch {}

          return sendJSON(res, 200, { ok: true, updated })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /channels/telegram/config — view telegram-specific configuration
      if (req.method === 'GET' && url.pathname === '/channels/telegram/config') {
        const tgCfg = daemon.config.get('channels.telegram', {});
        return sendJSON(res, 200, tgCfg);
      }

      // POST /channels/telegram/config — update telegram configuration (set-and-persist)
      if (req.method === 'POST' && url.pathname === '/channels/telegram/config') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing body' })
          const layered = (daemon.config as any)
          const updated: string[] = []

          const mapping: Record<string, string> = {
            allowedChatIds: 'channels.telegram.allowedChatIds',
            enabled: 'channels.telegram.enabled',
            token: 'channels.telegram.token'
          }

          for (const key of Object.keys(mapping)) {
            if (Object.prototype.hasOwnProperty.call(body, key)) {
              const k = mapping[key]
              const v = body[key]
              try {
                if (typeof layered?.setOverride === 'function') {
                  layered.setOverride(k, v, { reason: 'admin' })
                } else {
                  daemon.__admin_overrides = daemon.__admin_overrides || {}
                  daemon.__admin_overrides[k] = { value: v, reason: 'admin' }
                }
                updated.push(k)
              } catch (err) { /* continue */ }
            }
          }

          if (updated.length > 0) {
            try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch {}
            try { if (typeof daemon.reload === 'function') await daemon.reload() } catch {}
            return sendJSON(res, 200, { ok: true, updated })
          } else {
            return sendJSON(res, 400, { error: 'no valid fields to update' })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // orchestration endpoints
      if (parts[0] === 'orchestration') {
        if (req.method === 'GET' && parts.length === 1) {
          const list = daemon.pluginHost?.all?.() ?? []
          return sendJSON(res, 200, list)
        }
        if (req.method === 'GET' && parts[1] === 'stalled') {
          const all = daemon.pluginHost?.all?.() ?? []
          const stalled = (all as any[]).filter((p) => p.status === 'crashed' || p.status === 'restarting')
          return sendJSON(res, 200, stalled)
        }
        if (req.method === 'POST' && parts[1] === 'register') {
          const body = await parseBody(req)
          daemon.bus.emit({ type: 'orchestration:register', payload: body })
          return sendJSON(res, 200, { ok: true })
        }
        if (req.method === 'POST' && parts.length === 3 && parts[2] === 'update') {
          const id = parts[1]
          const body = await parseBody(req)
          daemon.bus.emit({ type: 'orchestration:update', id, payload: body })
          return sendJSON(res, 200, { ok: true })
        }
        if (req.method === 'POST' && parts.length === 3 && parts[2] === 'complete') {
          const id = parts[1]
          const body = await parseBody(req)
          daemon.bus.emit({ type: 'orchestration:complete', id, result: body })
          return sendJSON(res, 200, { ok: true })
        }
      }

      // plugins
      if (parts[0] === 'plugins' && req.method === 'GET') {
        const list = daemon.pluginHost?.all?.() ?? []
        return sendJSON(res, 200, list)
      }
      if (parts[0] === 'plugins' && parts.length === 2 && req.method === 'POST' && parts[1] && parts[1].endsWith('restart')) {
        // handled below
      }
      if (parts[0] === 'plugins' && parts.length === 3 && parts[2] === 'restart' && req.method === 'POST') {
        const id = parts[1]
        try {
          await daemon.pluginHost.restart(id)
          return sendJSON(res, 200, { ok: true })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // intelligence
      if (parts[0] === 'intelligence' && req.method === 'GET' && parts.length === 1) {
        const modules = (daemon.intelligence?.all ?? []).map((m: any) => ({ name: m.name, priority: m.priority, status: 'active' }))
        return sendJSON(res, 200, modules)
      }

      // GET /intelligence/:module/model — get current model config for a module
      if (parts[0] === 'intelligence' && parts[2] === 'model' && parts.length === 3 && req.method === 'GET') {
        const moduleName = parts[1]
        const mod = (daemon.intelligence?.all ?? []).find((m: any) => m.name === moduleName)
        if (!mod) return sendJSON(res, 404, { error: `Module '${moduleName}' not found` })
        if (typeof (mod as any).getModelConfig !== 'function') {
          return sendJSON(res, 400, { error: `Module '${moduleName}' does not support model config (legacy module)` })
        }
        return sendJSON(res, 200, { module: moduleName, config: (mod as any).getModelConfig() })
      }

      // POST /intelligence/:module/model — update model config for a module at runtime
      if (parts[0] === 'intelligence' && parts[2] === 'model' && parts.length === 3 && req.method === 'POST') {
        const moduleName = parts[1]
        const mod = (daemon.intelligence?.all ?? []).find((m: any) => m.name === moduleName)
        if (!mod) return sendJSON(res, 404, { error: `Module '${moduleName}' not found` })
        if (typeof (mod as any).setModelConfig !== 'function') {
          return sendJSON(res, 400, { error: `Module '${moduleName}' does not support model config (legacy module)` })
        }

        try {
          const body = await parseBody(req)
          // Accept: { model?, providerId?, temperature?, maxTokens?, timeoutMs? }
          // Also accept combined 'provider/model' in the model field
          const overrides: Record<string, unknown> = {}
          if (body.model !== undefined) overrides.model = body.model
          if (body.providerId !== undefined) overrides.providerId = body.providerId
          if (body.temperature !== undefined) overrides.temperature = body.temperature
          if (body.maxTokens !== undefined) overrides.maxTokens = body.maxTokens
          if (body.timeoutMs !== undefined) overrides.timeoutMs = body.timeoutMs

          if (Object.keys(overrides).length === 0) {
            return sendJSON(res, 400, { error: 'No model config fields provided. Accepts: model, providerId, temperature, maxTokens, timeoutMs' })
          }

          ;(mod as any).setModelConfig(overrides)
          return sendJSON(res, 200, { module: moduleName, config: (mod as any).getModelConfig(), updated: Object.keys(overrides) })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/subconscious/debug — expose subconscious capture for a session
      if (parts[0] === 'intelligence' && parts[1] === 'subconscious' && parts[2] === 'debug' && req.method === 'GET') {
        const sessionId = url.searchParams.get('sessionId') || 'default'
        try {
          const subconscious = daemon.intelligence?.subconscious
          const contextManager = daemon.intelligence?.contextManager
          
          // Get mental model if v2 enabled
          const mentalModel = subconscious?.getMentalModel?.(sessionId)
          
          // Get effective context
          let contextData: any = null
          if (contextManager?.getEffectiveContext) {
            try {
              const ctx = await contextManager.getEffectiveContext(sessionId, { charBudget: 2000 })
              contextData = {
                assembled: {
                  recentMemories: ctx.assembled.recentMemories?.slice(0, 5),
                  availableTools: ctx.assembled.availableTools?.slice(0, 10),
                  taskGuide: ctx.assembled.taskGuide,
                  sessionSummary: ctx.assembled.sessionSummary,
                  files: ctx.assembled.files?.map((f: any) => f.path).slice(0, 5),
                },
                mergedPreview: ctx.merged?.slice(0, 500),
              }
            } catch (e) {
              contextData = { error: String(e) }
            }
          }
          
          // Get recent signals
          const recentSignals = subconscious?.getRecentSignals?.(sessionId, 10) || []
          
          return sendJSON(res, 200, {
            sessionId,
            timestamp: Date.now(),
            mentalModel: mentalModel ? {
              sessionId: mentalModel.sessionId,
              state: mentalModel.state,
              lastUpdated: mentalModel.lastUpdated,
            } : null,
            context: contextData,
            recentSignals: recentSignals.map((s: any) => ({
              type: s.type,
              confidence: s.confidence,
              timestamp: s.timestamp,
            })),
            stats: subconscious?.getEnhancedSearchStats?.() || {},
          })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET/POST/DELETE => /intelligence/thinker/strategy
      if (url.pathname === '/intelligence/thinker/strategy') {
        try {
          const mem = daemon.intelligence?.memory
          if (!mem) return sendJSON(res, 503, { error: 'memory not initialised' })

          if (req.method === 'GET') {
            const strategy = await mem.kv_get('thinker:strategy')
            return sendJSON(res, 200, { strategy: strategy ?? null })
          }

          if (req.method === 'POST') {
            const body = await parseBody(req)
            if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing strategy body' })
            await mem.kv_set('thinker:strategy', body)
            // Emit bus event so Thinker picks it up
            daemon.bus.emit({ type: 'thinker:strategy-updated', strategy: body })
            return sendJSON(res, 200, { ok: true })
          }

          if (req.method === 'DELETE') {
            await mem.kv_del('thinker:strategy')
            daemon.bus.emit({ type: 'thinker:strategy-updated', strategy: null })
            return sendJSON(res, 200, { ok: true })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET/POST/DELETE => /intelligence/thinker/insight-history
      if (url.pathname === '/intelligence/thinker/insight-history') {
        try {
          const mem = daemon.intelligence?.memory
          if (!mem) return sendJSON(res, 503, { error: 'memory not initialised' })

          if (req.method === 'GET') {
            const history = await mem.kv_get('thinker:insight-history')
            return sendJSON(res, 200, { insightHistory: history ?? [] })
          }

          if (req.method === 'POST') {
            const body = await parseBody(req)
            if (!body || !Array.isArray(body)) return sendJSON(res, 400, { error: 'expected array body' })
            await mem.kv_set('thinker:insight-history', body)
            daemon.bus.emit({ type: 'thinker:insight-history-updated', history: body })
            return sendJSON(res, 200, { ok: true })
          }

          if (req.method === 'DELETE') {
            await mem.kv_del('thinker:insight-history')
            daemon.bus.emit({ type: 'thinker:insight-history-updated', history: [] })
            return sendJSON(res, 200, { ok: true })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/thinker/stats — return thinker runtime stats
      if (req.method === 'GET' && url.pathname === '/intelligence/thinker/stats') {
        try {
          const thinker = daemon.intelligence?.thinker
          if (!thinker) return sendJSON(res, 503, { error: 'thinker not initialised' })
          const stats = typeof thinker.stats === 'function' ? await Promise.resolve(thinker.stats()) : undefined
          return sendJSON(res, 200, { stats: stats ?? null })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET Subconscious learnings
      if (req.method === 'GET' && url.pathname === '/intelligence/subconscious/learnings') {
        try {
          const mem = daemon.intelligence?.memory
          let learnings: any[] | null = null
          if (mem) {
            try { learnings = await mem.kv_get('subconscious:learnings') || null } catch {}
          }
          if (!learnings) {
            // fallback: try reading persisted file
            const filePath = path.join(process.env.HOME || os.homedir(), '.cassicore', 'data', 'subconscious.json')
            try {
              if (fs.existsSync(filePath)) learnings = JSON.parse(fs.readFileSync(filePath, 'utf8') || '[]')
            } catch (err) { /* ignore */ }
          }
          return sendJSON(res, 200, { learnings: learnings ?? [] })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET Subconscious anomalies
      if (req.method === 'GET' && url.pathname === '/intelligence/subconscious/anomalies') {
        try {
          const mem = daemon.intelligence?.memory
          let anomalies: any[] | null = null
          if (mem) {
            try { anomalies = await mem.kv_get('subconscious:anomalies') || null } catch {}
          }
          return sendJSON(res, 200, { anomalies: anomalies ?? [] })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/subconscious/stats — subconscious statistics
      if (req.method === 'GET' && url.pathname === '/intelligence/subconscious/stats') {
        try {
          const mem = daemon.intelligence?.memory
          let learnings: any[] = []
          let anomalies: any[] = []
          let avgCounts: Record<string, number> = {}
          
          if (mem) {
            try { learnings = await mem.kv_get('subconscious:learnings') || [] } catch {}
            try { anomalies = await mem.kv_get('subconscious:anomalies') || [] } catch {}
            try { avgCounts = await mem.kv_get('subconscious:avgCounts') || {} } catch {}
          }
          
          const stats = {
            totalLearnings: learnings.length,
            totalAnomalies: anomalies.length,
            patternsRecognized: learnings.filter((l: any) => l.type === 'pattern').length,
            averageConfidence: learnings.length > 0 
              ? learnings.reduce((s: number, l: any) => s + (l.confidence || 0), 0) / learnings.length 
              : 0,
            lastUpdate: learnings.length > 0 
              ? Math.max(...learnings.map((l: any) => l.timestamp || 0)) 
              : Date.now(),
          }
          
          return sendJSON(res, 200, { stats, avgCounts })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/subconscious/learnings/search — search learnings
      if (req.method === 'POST' && url.pathname === '/intelligence/subconscious/learnings/search') {
        try {
          const body = await parseBody(req)
          const query = body?.query?.toLowerCase() || ''
          if (!query) return sendJSON(res, 400, { error: 'query required' })
          
          const mem = daemon.intelligence?.memory
          let learnings: any[] = []
          if (mem) {
            try { learnings = await mem.kv_get('subconscious:learnings') || [] } catch {}
          }
          
          const results = learnings.filter((l: any) => 
            (l.summary && l.summary.toLowerCase().includes(query)) ||
            (l.clusterLabel && l.clusterLabel.toLowerCase().includes(query)) ||
            (l.type && l.type.toLowerCase().includes(query))
          )
          
          return sendJSON(res, 200, { learnings: results, query, count: results.length })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/subconscious/anomalies/:id/acknowledge — acknowledge anomaly
      if (req.method === 'POST' && parts[0] === 'intelligence' && parts[1] === 'subconscious' && parts[2] === 'anomalies' && parts[4] === 'acknowledge') {
        try {
          const anomalyId = parts[3]
          if (!anomalyId) return sendJSON(res, 400, { error: 'anomaly id required' })
          
          const mem = daemon.intelligence?.memory
          if (!mem) return sendJSON(res, 503, { error: 'memory not available' })
          
          let anomalies: any[] = await mem.kv_get('subconscious:anomalies') || []
          const idx = anomalies.findIndex((a: any) => a.id === anomalyId || a.summary === anomalyId)
          
          if (idx === -1) return sendJSON(res, 404, { error: 'anomaly not found' })
          
          anomalies[idx] = { ...anomalies[idx], acknowledged: true, acknowledgedAt: Date.now() }
          await mem.kv_set('subconscious:anomalies', anomalies)
          
          return sendJSON(res, 200, { ok: true, anomalyId })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // DELETE /intelligence/subconscious/learnings — clear learnings
      if (req.method === 'DELETE' && url.pathname === '/intelligence/subconscious/learnings') {
        try {
          const mem = daemon.intelligence?.memory
          if (mem) {
            await mem.kv_del('subconscious:learnings')
          }
          // Also clear fallback file
          const filePath = path.join(process.env.HOME || os.homedir(), '.cassicore', 'data', 'subconscious.json')
          try {
            if (fs.existsSync(filePath)) fs.unlinkSync(filePath)
          } catch {}
          
          return sendJSON(res, 200, { ok: true, cleared: 'learnings' })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // DELETE /intelligence/subconscious/anomalies — clear anomalies
      if (req.method === 'DELETE' && url.pathname === '/intelligence/subconscious/anomalies') {
        try {
          const mem = daemon.intelligence?.memory
          if (mem) {
            await mem.kv_del('subconscious:anomalies')
          }
          return sendJSON(res, 200, { ok: true, cleared: 'anomalies' })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Archivist endpoints ────────────────────────────────────────────────

      // GET /intelligence/archivist/recent — recent archive entries
      if (req.method === 'GET' && url.pathname === '/intelligence/archivist/recent') {
        try {
          const mem = daemon.intelligence?.memory
          if (!mem) return sendJSON(res, 503, { error: 'memory module not initialized' })
          const limit = parseInt(url.searchParams.get('limit') || '20', 10)
          const entries = mem.getRecentArchiveEntries(limit)
          return sendJSON(res, 200, { entries })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/archivist/stats — archive statistics
      if (req.method === 'GET' && url.pathname === '/intelligence/archivist/stats') {
        try {
          const mem = daemon.intelligence?.memory
          if (!mem) return sendJSON(res, 503, { error: 'memory module not initialized' })
          const stats = mem.getArchiveStats()
          const queueStats = mem.getArchiveQueueStats()
          return sendJSON(res, 200, { stats, queueStats })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Context Focus (unified focus state for bridge plugin) ────────────────

      // GET /intelligence/context-focus — unified focus state for a session
      // Used by non-plugin consumers (MCP gateway, CLI, etc.) to get the same
      // focus data that the bridge plugin reads from inject.json.
      if (req.method === 'GET' && url.pathname === '/intelligence/context-focus') {
        try {
          const sessionId = url.searchParams.get('sessionId')
          if (!sessionId) {
            return sendJSON(res, 400, { error: 'sessionId query parameter is required' })
          }
          const focus = buildFocusState(sessionId, { includeParentFocus: true })
          if (!focus) {
            return sendJSON(res, 200, { sessionId, focusState: null, message: 'no focus data available for this session' })
          }
          return sendJSON(res, 200, { sessionId, focusState: focus })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Consolidated Activity Dashboard ─────────────────────────────────────

      // GET /intelligence/activity — consolidated cognitive activity dashboard
      if (req.method === 'GET' && url.pathname === '/intelligence/activity') {
        try {
          const intel = daemon.intelligence
          if (!intel) return sendJSON(res, 503, { error: 'intelligence layer not initialized' })

          // Gather module statuses
          const modules = intel.all.map((m: any) => ({
            name: m.name || m.constructor?.name || 'unknown',
            priority: m.priority ?? 0,
            status: 'active',
          }))

          // Thinker stats
          let thinkerStats = null
          try { thinkerStats = intel.thinker?.stats?.() ?? null } catch { /* ignore */ }

          // Thinker strategy
          let thinkerStrategy = null
          try { thinkerStrategy = intel.memory?.kv_get('thinker:strategy') ?? null } catch { /* ignore */ }

          // Memory stats
          let memoryStats = null
          try { memoryStats = intel.memory?.stats?.() ?? null } catch { /* ignore */ }

          // Archivist stats
          let archiveStats = null
          try { archiveStats = intel.memory?.getArchiveStats?.() ?? null } catch { /* ignore */ }

          // Reflect unresolved patterns
          let unresolvedPatterns = null
          try { unresolvedPatterns = intel.reflect?.unresolved?.(5) ?? null } catch { /* ignore */ }

          // Optimizer — score recent sessions
          let optimizerHealth: Record<string, any> = {}
          try {
            const sessions = Array.from(daemon.sessions?.['sessions']?.values?.() || [])
            for (const s of sessions.slice(0, 5)) {
              const score = intel.optimizer?.scoreSession?.((s as any).id)
              if (score) optimizerHealth[(s as any).id] = score
            }
          } catch { /* ignore */ }

          // Dialectic — try to get stats for recent sessions
          let dialecticSummary = null
          try {
            const sessions = Array.from(daemon.sessions?.['sessions']?.values?.() || [])
            if (sessions.length > 0) {
              const recentSession = sessions.sort((a: any, b: any) => (b.lastActiveAt || 0) - (a.lastActiveAt || 0))[0] as any
              dialecticSummary = intel.dialectic?.getStats?.(recentSession.id) ?? null
            }
          } catch { /* ignore */ }

          // AI Scientist — recent studies
          let recentStudies = null
          try { recentStudies = intel.aiScientist?.getRecentStudies?.(3) ?? null } catch { /* ignore */ }

          return sendJSON(res, 200, {
            timestamp: Date.now(),
            modules,
            thinker: { stats: thinkerStats, strategy: thinkerStrategy },
            memory: memoryStats,
            archive: archiveStats,
            reflect: { unresolvedPatterns },
            optimizer: { sessionHealth: optimizerHealth },
            dialectic: dialecticSummary,
            aiScientist: { recentStudies },
          })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Tier 2: CycleHook Module Endpoints ─────────────────────────────────

      // GET /intelligence/outcomes/stats — OutcomeTracker aggregate stats
      if (req.method === 'GET' && url.pathname === '/intelligence/outcomes/stats') {
        try {
          const tracker = daemon.outcomeTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'outcome tracker not initialized' })
          }
          return sendJSON(res, 200, tracker.getStats())
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/outcomes/feedback — recent feedback signals for a session
      if (req.method === 'GET' && url.pathname === '/intelligence/outcomes/feedback') {
        try {
          const tracker = daemon.outcomeTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'outcome tracker not initialized' })
          }
          const sessionId = url.searchParams.get('sessionId')
          if (!sessionId) {
            return sendJSON(res, 400, { error: 'sessionId query parameter is required' })
          }
          const limit = parseInt(url.searchParams.get('limit') || '10', 10)
          const feedback = tracker.getRecentFeedback(sessionId, limit)
          return sendJSON(res, 200, { feedback })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/outcomes/sources/:source — per-source outcome stats
      if (req.method === 'GET' && url.pathname.startsWith('/intelligence/outcomes/sources/')) {
        try {
          const tracker = daemon.outcomeTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'outcome tracker not initialized' })
          }
          const source = url.pathname.split('/intelligence/outcomes/sources/')[1]
          if (!source) {
            return sendJSON(res, 400, { error: 'source parameter is required' })
          }
          const windowMs = parseInt(url.searchParams.get('windowMs') || String(24 * 60 * 60_000), 10)
          const stats = tracker.getSourceStats(decodeURIComponent(source), windowMs)
          return sendJSON(res, 200, { stats: stats || null })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/outcomes/tools/:toolName — per-tool reliability stats
      if (req.method === 'GET' && url.pathname.startsWith('/intelligence/outcomes/tools/')) {
        try {
          const tracker = daemon.outcomeTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'outcome tracker not initialized' })
          }
          const toolName = url.pathname.split('/intelligence/outcomes/tools/')[1]
          if (!toolName) {
            return sendJSON(res, 400, { error: 'toolName parameter is required' })
          }
          const windowMs = parseInt(url.searchParams.get('windowMs') || String(24 * 60 * 60_000), 10)
          const stats = tracker.getToolStats(decodeURIComponent(toolName), windowMs)
          return sendJSON(res, 200, { stats: stats || null })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/profiler/stats — ProviderProfiler aggregate stats
      if (req.method === 'GET' && url.pathname === '/intelligence/profiler/stats') {
        try {
          const profiler = daemon.providerProfiler
          if (!profiler) {
            return sendJSON(res, 503, { error: 'provider profiler not initialized' })
          }
          return sendJSON(res, 200, profiler.getStats())
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/profiler/aggregate — per-provider/model aggregate stats
      if (req.method === 'GET' && url.pathname === '/intelligence/profiler/aggregate') {
        try {
          const profiler = daemon.providerProfiler
          if (!profiler) {
            return sendJSON(res, 503, { error: 'provider profiler not initialized' })
          }
          const opts: any = {}
          const providerId = url.searchParams.get('providerId')
          const model = url.searchParams.get('model')
          const windowMs = url.searchParams.get('windowMs')
          if (providerId) opts.providerId = providerId
          if (model) opts.model = model
          if (windowMs) opts.windowMs = parseInt(windowMs, 10)
          const aggregate = profiler.getAggregateStats(opts)
          return sendJSON(res, 200, { aggregate })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/profiler/hourly — hourly trend data
      if (req.method === 'GET' && url.pathname === '/intelligence/profiler/hourly') {
        try {
          const profiler = daemon.providerProfiler
          if (!profiler) {
            return sendJSON(res, 503, { error: 'provider profiler not initialized' })
          }
          const opts: any = {}
          const providerId = url.searchParams.get('providerId')
          const model = url.searchParams.get('model')
          const hours = url.searchParams.get('hours')
          if (providerId) opts.providerId = providerId
          if (model) opts.model = model
          if (hours) opts.hours = parseInt(hours, 10)
          const hourly = profiler.getHourlyStats(opts)
          return sendJSON(res, 200, { hourly })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/budget — Budget tracker snapshots (monthly limits, usage, tiers)
      if (req.method === 'GET' && url.pathname === '/intelligence/budget') {
        try {
          const tracker = daemon.budgetTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'budget tracker not initialized' })
          }
          const providerId = url.searchParams.get('providerId')
          if (providerId) {
            const snapshot = tracker.getSnapshot(providerId)
            return sendJSON(res, 200, { snapshots: snapshot ? [snapshot] : [], tier: tracker.getTier(providerId) })
          }
          const snapshots = tracker.getAllSnapshots()
          const tiers: Record<string, string> = {}
          for (const snap of snapshots) {
            tiers[snap.providerId] = tracker.getTier(snap.providerId)
          }
          return sendJSON(res, 200, { snapshots, tiers })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/strategy/stats — StrategyTracker aggregate stats
      if (req.method === 'GET' && url.pathname === '/intelligence/strategy/stats') {
        try {
          const tracker = daemon.strategyTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'strategy tracker not initialized' })
          }
          return sendJSON(res, 200, tracker.getStats())
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/strategy/history — strategy snapshots over time
      if (req.method === 'GET' && url.pathname === '/intelligence/strategy/history') {
        try {
          const tracker = daemon.strategyTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'strategy tracker not initialized' })
          }
          const module = url.searchParams.get('module')
          if (!module) {
            return sendJSON(res, 400, { error: 'module query parameter is required' })
          }
          const limit = parseInt(url.searchParams.get('limit') || '20', 10)
          const history = tracker.getStrategyHistory(module, limit)
          return sendJSON(res, 200, { history })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/strategy/best — current best strategy per module
      if (req.method === 'GET' && url.pathname === '/intelligence/strategy/best') {
        try {
          const tracker = daemon.strategyTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'strategy tracker not initialized' })
          }
          const module = url.searchParams.get('module')
          if (!module) {
            return sendJSON(res, 400, { error: 'module query parameter is required' })
          }
          const best = tracker.getBestStrategy(module)
          return sendJSON(res, 200, { strategy: best || null })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/strategy/dialectic-effectiveness — dialectic session effectiveness
      if (req.method === 'GET' && url.pathname === '/intelligence/strategy/dialectic-effectiveness') {
        try {
          const tracker = daemon.strategyTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'strategy tracker not initialized' })
          }
          const limit = parseInt(url.searchParams.get('limit') || '20', 10)
          const effectiveness = tracker.getDialecticEffectiveness(limit)
          return sendJSON(res, 200, { effectiveness })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/correlator/stats — CrossSessionCorrelator aggregate stats
      if (req.method === 'GET' && url.pathname === '/intelligence/correlator/stats') {
        try {
          const correlator = daemon.crossSessionCorrelator
          if (!correlator) {
            return sendJSON(res, 503, { error: 'cross-session correlator not initialized' })
          }
          return sendJSON(res, 200, correlator.getStats())
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/correlator/patterns — filtered cross-session patterns
      if (req.method === 'GET' && url.pathname === '/intelligence/correlator/patterns') {
        try {
          const correlator = daemon.crossSessionCorrelator
          if (!correlator) {
            return sendJSON(res, 503, { error: 'cross-session correlator not initialized' })
          }
          const opts: any = {}
          const category = url.searchParams.get('category')
          const minConfidence = url.searchParams.get('minConfidence')
          const limit = url.searchParams.get('limit')
          if (category) opts.category = category
          if (minConfidence) opts.minConfidence = parseFloat(minConfidence)
          if (limit) opts.limit = parseInt(limit, 10)
          const patterns = correlator.getPatterns(opts)
          return sendJSON(res, 200, { patterns })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/correlator/patterns/:key — patterns for a specific correlation key
      if (req.method === 'GET' && url.pathname.startsWith('/intelligence/correlator/patterns/')) {
        try {
          const correlator = daemon.crossSessionCorrelator
          if (!correlator) {
            return sendJSON(res, 503, { error: 'cross-session correlator not initialized' })
          }
          const key = url.pathname.split('/intelligence/correlator/patterns/')[1]
          if (!key) {
            return sendJSON(res, 400, { error: 'correlation key is required' })
          }
          const patterns = correlator.getPatternsForKey(decodeURIComponent(key))
          return sendJSON(res, 200, { patterns })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/trace — forensic trace of a specific turn
      if (req.method === 'GET' && url.pathname === '/intelligence/trace') {
        try {
          const sessionId = url.searchParams.get('sessionId')
          if (!sessionId) {
            return sendJSON(res, 400, { error: 'sessionId query parameter is required' })
          }
          const turnIndex = url.searchParams.get('turnIndex')
          const limit = parseInt(url.searchParams.get('limit') || '5', 10)

          // Gather data from multiple intelligence modules
          const intel = daemon.intelligence
          const trace: any = {
            sessionId,
            timestamp: Date.now(),
            continuity: null,
            dialectic: null,
            injections: null,
            archiveContext: null,
            reflectPatterns: null,
          }

          // 1. Continuity — recent turns for this session
          if (intel?.continuity) {
            try {
              const turns = await intel.continuity.getRecent(sessionId, limit)
              if (turnIndex !== null && turnIndex !== undefined) {
                const idx = parseInt(turnIndex, 10)
                // Return the specific turn and its neighbors
                trace.continuity = {
                  targetIndex: idx,
                  turns: turns.slice(Math.max(0, idx - 1), idx + 2),
                  totalTurns: turns.length,
                }
              } else {
                trace.continuity = { turns, totalTurns: turns.length }
              }
            } catch { /* ignore */ }
          }

          // 2. Dialectic — recent analysis for this session
          if (intel?.dialectic?.getRecent) {
            try {
              trace.dialectic = intel.dialectic.getRecent(sessionId, limit)
            } catch { /* ignore */ }
          }

          // 3. Injection ledger + archive context from conversation thread
          if (intel?.memory) {
            try {
              const thread = intel.memory.getConversationWithThinking?.(sessionId, limit * 2) ?? []
              trace.injections = thread.filter(
                (e: any) => e.type === 'injection' || e.category === 'injection'
              )
              trace.archiveContext = thread.filter(
                (e: any) => e.type !== 'injection' && e.category !== 'injection'
              ).slice(0, limit)
            } catch { /* ignore */ }
          }

          // 4. Reflect — unresolved patterns that may have influenced the turn
          if (intel?.reflect?.unresolved) {
            try {
              trace.reflectPatterns = await intel.reflect.unresolved(5)
            } catch { /* ignore */ }
          }

          // 5. Subconscious — mental model state at turn time
          if (daemon.intelligence?.subconscious) {
            try {
              const sub = daemon.intelligence.subconscious
              if (sub.getMentalModel) {
                trace.mentalModel = sub.getMentalModel(sessionId)
              }
            } catch { /* ignore */ }
          }

          return sendJSON(res, 200, trace)
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/skills/metrics — skill usage metrics
      if (req.method === 'GET' && url.pathname === '/intelligence/skills/metrics') {
        try {
          const tracker = daemon.skillMetricsTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'skill metrics tracker not initialized' })
          }
          const days = parseInt(url.searchParams.get('days') || '7', 10)
          const summary = tracker.getMetricsSummary(days)
          return sendJSON(res, 200, { summary })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/skills/details — detailed usage for a specific skill
      if (req.method === 'GET' && url.pathname === '/intelligence/skills/details') {
        try {
          const tracker = daemon.skillMetricsTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'skill metrics tracker not initialized' })
          }
          const skillName = url.searchParams.get('name')
          if (!skillName) {
            return sendJSON(res, 400, { error: 'name query param required' })
          }
          const days = parseInt(url.searchParams.get('days') || '30', 10)
          const details = tracker.getSkillDetails(skillName, days)
          return sendJSON(res, 200, { skillName, details })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/skills/all — list all skills with usage counts
      if (req.method === 'GET' && url.pathname === '/intelligence/skills/all') {
        try {
          const tracker = daemon.skillMetricsTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'skill metrics tracker not initialized' })
          }
          const days = parseInt(url.searchParams.get('days') || '30', 10)
          const skills = tracker.getAllSkillsWithUsage(days)
          return sendJSON(res, 200, { skills })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/skills/prune — prune old invocation records
      if (req.method === 'POST' && url.pathname === '/intelligence/skills/prune') {
        try {
          const tracker = daemon.skillMetricsTracker
          if (!tracker) {
            return sendJSON(res, 503, { error: 'skill metrics tracker not initialized' })
          }
          const body = await parseBody(req)
          const daysToKeep = body?.daysToKeep || 90
          tracker.pruneOldInvocations(daysToKeep)
          return sendJSON(res, 200, { message: `Pruned invocations older than ${daysToKeep} days` })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/thinker/think — manual Thinker trigger (supports context override)
      if (req.method === 'POST' && url.pathname === '/intelligence/thinker/think') {
        try {
          const body = await parseBody(req)
          const publicDepth = body?.depth === 'Think' ? 'Think' : 'Ponder'
          const context = body?.context
          const wait = body?.wait === false ? false : true
          const urgency = body?.urgency || 'medium'
          const trigger = body?.trigger || 'admin'
          const thinker = daemon.intelligence?.thinker
          if (!thinker) return sendJSON(res, 503, { error: 'thinker not available' })

          if (context) {
            // Use private Ponder/Think to pass explicit context
            const p = publicDepth === 'Think'
              ? (thinker as any).Think({ context, urgency, trigger })
              : (thinker as any).Ponder({ context, urgency, trigger })

            if (!wait) {
              p.catch((e: any) => daemon.logger?.warn?.('admin: thinker background failed', { error: String(e) }))
              return sendJSON(res, 200, { ok: true, message: 'Thinker triggered (async)' })
            }

            const result = await p
            return sendJSON(res, 200, { ok: true, result: result ?? null })
          } else {
            if (!wait) {
              (thinker as any).think(publicDepth).then(() => {}).catch((e: any) => daemon.logger?.warn?.('admin: thinker background failed', { error: String(e) }))
              return sendJSON(res, 200, { ok: true, message: 'Thinker triggered (async)' })
            }
            const insight = await (thinker as any).think(publicDepth)
            return sendJSON(res, 200, { ok: true, insight })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Multi-Agent endpoints (admin) ───────────────────────────────────────
      // GET /intelligence/multi-agent/metrics
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/metrics') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const metrics = typeof ma.getMetrics === 'function' ? ma.getMetrics() : undefined
          return sendJSON(res, 200, { metrics: metrics ?? null })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /providers — list all loaded provider IDs
      if (req.method === 'GET' && url.pathname === '/providers') {
        try {
          const providersMap: Map<string, any> | undefined = (daemon.pipeline && (daemon.pipeline as any).providers) || (daemon.providers as any) || undefined
          if (!providersMap) return sendJSON(res, 503, { error: 'providers not initialised' })
          
          const ids = Array.from(providersMap.keys())
          return sendJSON(res, 200, { providers: ids })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /providers/metrics — aggregated provider + global metrics
      if (req.method === 'GET' && url.pathname === '/providers/metrics') {
        try {
          // Prefer pipeline providers map, fall back to daemon-level providers (if any)
          const providersMap: Map<string, any> | undefined = (daemon.pipeline && (daemon.pipeline as any).providers) || (daemon.providers as any) || undefined
          if (!providersMap) return sendJSON(res, 503, { error: 'providers not initialised' })

          const providerMetrics: Array<{ id: string; metrics: any }> = []
          let globalConfig: any = null
          for (const [id, prov] of providersMap) {
            let metrics = null
            try { metrics = typeof prov.getMetrics === 'function' ? prov.getMetrics() : null } catch {}
            providerMetrics.push({ id, metrics })
            if (!globalConfig && metrics?.globalConfig) globalConfig = metrics.globalConfig
          }

          return sendJSON(res, 200, { global: globalConfig ?? null, providers: providerMetrics })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /providers/qwen/stats — Qwen load balancer stats
      if (req.method === 'GET' && url.pathname === '/providers/qwen/stats') {
        try {
          const providersMap: Map<string, any> | undefined = (daemon.pipeline && (daemon.pipeline as any).providers) || (daemon.providers as any) || undefined
          if (!providersMap) return sendJSON(res, 503, { error: 'providers not initialised' })

          const qwenProvider = providersMap.get('qwen')
          if (!qwenProvider) return sendJSON(res, 404, { error: 'qwen provider not found' })

          // Check if it's a load balancer
          if (typeof (qwenProvider as any).getStats === 'function') {
            const stats = (qwenProvider as any).getStats()
            const activeCount = typeof (qwenProvider as any).getActiveCount === 'function' 
              ? (qwenProvider as any).getActiveCount() 
              : undefined
            
            return sendJSON(res, 200, {
              loadBalancing: true,
              activeCount,
              accounts: stats,
            })
          }

          // Single account mode
          return sendJSON(res, 200, { loadBalancing: false, accounts: 1 })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /providers/config — view effective provider global configuration and overrides
      if (req.method === 'GET' && url.pathname === '/providers/config') {
        try {
          const layered = (daemon.config as any)
          const getWithSource = typeof layered?.getWithSource === 'function'
            ? (k: string) => layered.getWithSource(k)
            : (k: string) => ({ value: layered?.get?.(k, undefined), source: undefined })

          const keys = [
            'providers.global.maxConcurrent',
            'providers.global.windowMs',
            'providers.global.maxRequestsPerWindow',
            'providers.global.timeoutMs',
          ]

          const configView: Record<string, unknown> = {}
          for (const k of keys) {
            try {
              configView[k] = getWithSource(k)
            } catch (err) {
              configView[k] = { value: daemon.config.get(k, undefined), source: undefined }
            }
          }

          const overrides = typeof layered?.getOverrides === 'function' ? layered.getOverrides() : (daemon.__admin_overrides || {})

          return sendJSON(res, 200, { config: configView, overrides })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /providers/config/keys — list provider-specific config keys and defaults
      if (req.method === 'GET' && url.pathname === '/providers/config/keys') {
        try {
          const keys = listProviderConfigKeys()
          return sendJSON(res, 200, { keys })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /providers/config — set provider global configuration overrides
      // Accepts either { key: 'providers.global.maxConcurrent', value: 16 } or
      // a body with friendly keys { maxConcurrent: 16, windowMs: 60000, ... }
      if (req.method === 'POST' && url.pathname === '/providers/config') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing body' })

          const layered = (daemon.config as any)
          const mapping: Record<string, string> = {
            maxConcurrent: 'providers.global.maxConcurrent',
            windowMs: 'providers.global.windowMs',
            maxRequestsPerWindow: 'providers.global.maxRequestsPerWindow',
            timeoutMs: 'providers.global.timeoutMs',
          }

          const updated: string[] = []

          if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
            const k = String(body.key)
            try {
              if (typeof layered?.setOverride === 'function') {
                // Merge nested objects where applicable
                const existing = layered.get(k, undefined)
                const newVal = isObject(existing) && isObject(body.value) ? mergeDeep(existing, body.value) : body.value
                layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                daemon.__admin_overrides[k] = { value: body.value, reason: body.reason }
              }
              updated.push(k)
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          } else {
            for (const friendly of Object.keys(mapping)) {
              if (Object.prototype.hasOwnProperty.call(body, friendly)) {
                const k = mapping[friendly]
                try {
                  if (typeof layered?.setOverride === 'function') {
                    const existing = layered.get(k, undefined)
                    const provided = (body as any)[friendly]
                    const newVal = isObject(existing) && isObject(provided) ? mergeDeep(existing, provided) : provided
                    layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
                  } else {
                    daemon.__admin_overrides = daemon.__admin_overrides || {}
                    daemon.__admin_overrides[k] = { value: (body as any)[friendly], reason: body.reason || 'admin' }
                  }
                  updated.push(k)
                } catch (err) {
                  return sendJSON(res, 500, { error: String(err) })
                }
              }
            }
          }

          // Persist and reload so listeners (e.g., CentralizedProvider) re-apply new limits
          try {
            if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides()
          } catch (err) { /* best-effort */ }

          try {
            if (typeof daemon.reload === 'function') await daemon.reload()
            else daemon.bus.emit({ type: 'config:reloaded' })
          } catch (err) { /* best-effort */ }

          return sendJSON(res, 200, { ok: true, updated })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // DELETE /providers/config — remove overrides for one or more keys
      // Body may be { keys: ['providers.global.maxConcurrent'] } or empty to remove all providers.global.* overrides
      if (req.method === 'DELETE' && url.pathname === '/providers/config') {
        try {
          const body = await parseBody(req)
          const layered = (daemon.config as any)
          const mapping: Record<string, string> = {
            maxConcurrent: 'providers.global.maxConcurrent',
            windowMs: 'providers.global.windowMs',
            maxRequestsPerWindow: 'providers.global.maxRequestsPerWindow',
            timeoutMs: 'providers.global.timeoutMs',
          }

          let toRemove: string[] = []
          if (body && Array.isArray(body.keys)) {
            toRemove = body.keys.map(String)
          } else if (body && typeof body.key === 'string') {
            toRemove = [String(body.key)]
          } else if (body && typeof body === 'object' && Object.keys(body).length > 0) {
            for (const friendly of Object.keys(mapping)) {
              if ((body as any)[friendly]) toRemove.push(mapping[friendly])
            }
          } else {
            // default: clear all known keys
            toRemove = Object.values(mapping)
          }

          const removed: string[] = []
          for (const k of toRemove) {
            try {
              if (typeof layered?.clearOverride === 'function') {
                layered.clearOverride(k)
                removed.push(k)
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                if (Object.prototype.hasOwnProperty.call(daemon.__admin_overrides, k)) {
                  delete daemon.__admin_overrides[k]
                  removed.push(k)
                }
              }
            } catch (err) {
              // continue
            }
          }

          try {
            if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides()
          } catch (err) { /* best-effort */ }

          try {
            if (typeof daemon.reload === 'function') await daemon.reload()
            else daemon.bus.emit({ type: 'config:reloaded' })
          } catch (err) { /* best-effort */ }

          return sendJSON(res, 200, { ok: true, removed })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /providers/config/set — set arbitrary provider config keys
      if (req.method === 'POST' && url.pathname === '/providers/config/set') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing body' })

          const layered = (daemon.config as any)
          const updated: string[] = []

          // Support batch updates: { updates: [{ key, value, reason }] }
          if (Array.isArray(body.updates)) {
            for (const u of body.updates) {
              if (!u || typeof u.key !== 'string' || !Object.prototype.hasOwnProperty.call(u, 'value')) continue
              const k = String(u.key)
              const v = (u as any).value
              try {
                if (typeof layered?.setOverride === 'function') {
                  const existing = layered.get(k, undefined)
                  const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
                  layered.setOverride(k, newVal, { reason: u.reason || 'admin' })
                } else {
                  daemon.__admin_overrides = daemon.__admin_overrides || {}
                  daemon.__admin_overrides[k] = { value: v, reason: u.reason || 'admin' }
                }
                updated.push(k)
              } catch (err) {
                // continue on per-item errors
              }
            }
          } else if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
            const k = String(body.key)
            const v = body.value
            try {
              if (typeof layered?.setOverride === 'function') {
                const existing = layered.get(k, undefined)
                const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
                layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                daemon.__admin_overrides[k] = { value: v, reason: body.reason || 'admin' }
              }
              updated.push(k)
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          } else {
            return sendJSON(res, 400, { error: 'expected { key, value } or { updates: [{ key, value }] }' })
          }

          // Persist and reload
          try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch {}
          try { if (typeof daemon.reload === 'function') await daemon.reload(); else daemon.bus.emit({ type: 'config:reloaded' }) } catch {}

          return sendJSON(res, 200, { ok: true, updated })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /providers/config/apply — update overrides and return providers metrics snapshot
      if (req.method === 'POST' && url.pathname === '/providers/config/apply') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing body' })

          const layered = (daemon.config as any)
          const mapping: Record<string, string> = {
            maxConcurrent: 'providers.global.maxConcurrent',
            windowMs: 'providers.global.windowMs',
            maxRequestsPerWindow: 'providers.global.maxRequestsPerWindow',
            timeoutMs: 'providers.global.timeoutMs',
          }

          const updated: string[] = []

          // Accept same forms as /providers/config POST plus arbitrary updates
          if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
            const k = String(body.key)
            try {
              if (typeof layered?.setOverride === 'function') {
                const existing = layered.get(k, undefined)
                const newVal = isObject(existing) && isObject(body.value) ? mergeDeep(existing, body.value) : body.value
                layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                daemon.__admin_overrides[k] = { value: body.value, reason: body.reason || 'admin' }
              }
              updated.push(k)
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          } else if (Array.isArray(body.updates)) {
            for (const u of body.updates) {
              if (!u || typeof u.key !== 'string' || !Object.prototype.hasOwnProperty.call(u, 'value')) continue
              const k = String(u.key)
              try {
                if (typeof layered?.setOverride === 'function') {
                  const existing = layered.get(k, undefined)
                  const newVal = isObject(existing) && isObject(u.value) ? mergeDeep(existing, u.value) : u.value
                  layered.setOverride(k, newVal, { reason: u.reason || 'admin' })
                } else {
                  daemon.__admin_overrides = daemon.__admin_overrides || {}
                  daemon.__admin_overrides[k] = { value: u.value, reason: u.reason || 'admin' }
                }
                updated.push(k)
              } catch (err) { /* continue */ }
            }
          } else {
            // friendly mapping form
            for (const friendly of Object.keys(mapping)) {
              if (Object.prototype.hasOwnProperty.call(body, friendly)) {
                const k = mapping[friendly]
                try {
                  if (typeof layered?.setOverride === 'function') {
                    const existing = layered.get(k, undefined)
                    const provided = (body as any)[friendly]
                    const newVal = isObject(existing) && isObject(provided) ? mergeDeep(existing, provided) : provided
                    layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
                  } else {
                    daemon.__admin_overrides = daemon.__admin_overrides || {}
                    daemon.__admin_overrides[k] = { value: (body as any)[friendly], reason: body.reason || 'admin' }
                  }
                  updated.push(k)
                } catch (err) {
                  return sendJSON(res, 500, { error: String(err) })
                }
              }
            }
          }

          // Persist and reload so listeners re-apply new limits
          try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch {}
          try { if (typeof daemon.reload === 'function') await daemon.reload(); else daemon.bus.emit({ type: 'config:reloaded' }) } catch {}

          // Now return metrics snapshot
          try {
            const providersMap: Map<string, any> | undefined = (daemon.pipeline && (daemon.pipeline as any).providers) || (daemon.providers as any) || undefined
            if (!providersMap) return sendJSON(res, 503, { error: 'providers not initialised' })

            const providerMetrics: Array<{ id: string; metrics: any }> = []
            let globalConfig: any = null
            for (const [id, prov] of providersMap) {
              let metrics = null
              try { metrics = typeof prov.getMetrics === 'function' ? prov.getMetrics() : null } catch {}
              providerMetrics.push({ id, metrics })
              if (!globalConfig && metrics?.globalConfig) globalConfig = metrics.globalConfig
            }

            return sendJSON(res, 200, { ok: true, updated, metrics: { global: globalConfig ?? null, providers: providerMetrics } })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /providers/reset — reset provider error state and/or rate limit history
      // Body: { providerId?: string, resetErrors?: boolean, resetRateLimits?: boolean }
      // If providerId omitted, resets all providers
      if (req.method === 'POST' && url.pathname === '/providers/reset') {
        try {
          const body = await parseBody(req)
          const providerId = typeof body?.providerId === 'string' ? body.providerId : undefined
          const resetErrors = body?.resetErrors !== false  // default true
          const resetRateLimits = body?.resetRateLimits === true  // default false

          const providersMap: Map<string, any> | undefined = (daemon.pipeline && (daemon.pipeline as any).providers) || (daemon.providers as any) || undefined
          if (!providersMap) return sendJSON(res, 503, { error: 'providers not initialised' })

          const results: Array<{ id: string; resetErrors?: boolean; resetRateLimits?: boolean; error?: string }> = []

          for (const [id, prov] of providersMap) {
            if (providerId && id !== providerId) continue

            const result: typeof results[number] = { id }
            try {
              if (resetErrors && typeof prov.resetErrorState === 'function') {
                prov.resetErrorState()
                result.resetErrors = true
              }
              if (resetRateLimits && typeof prov.resetRateLimitHistory === 'function') {
                prov.resetRateLimitHistory()
                result.resetRateLimits = true
              }
            } catch (err) {
              result.error = String(err)
            }
            results.push(result)
          }

          return sendJSON(res, 200, { ok: true, results })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/stats
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/stats') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const stats = typeof ma.stats === 'function' ? await Promise.resolve(ma.stats()) : undefined
          return sendJSON(res, 200, { stats: stats ?? null })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/roles
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/roles') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const current = (ma as any).roleMap ?? {}
          const defaults = (ma.constructor as any)?.ROLES ?? {}
          return sendJSON(res, 200, { roles: { defaults, current } })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/roles
      if (req.method === 'POST' && url.pathname === '/intelligence/multi-agent/roles') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'expected roles object' })
          // Validate shape lightly
          const roles = body as Record<string, any>
          ma.updateRoles(roles)
          return sendJSON(res, 200, { ok: true, updated: Object.keys(roles) })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/templates
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/templates') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const templateMap = (ma as any).templateMap ?? {}
          const samples: Record<string, string> = {}
          for (const k of Object.keys(templateMap)) {
            try { samples[k] = templateMap[k]?.({}) ?? String(templateMap[k]) } catch { samples[k] = '[function]' }
          }
          return sendJSON(res, 200, { templates: samples })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/templates
      if (req.method === 'POST' && url.pathname === '/intelligence/multi-agent/templates') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'expected templates object' })
          const templatesIn = body as Record<string, string>
          // Convert string templates into simple functions
          const converted: Record<string, (args: any) => string> = {}
          for (const k of Object.keys(templatesIn)) {
            const v = templatesIn[k]
            converted[k] = () => String(v)
          }
          ma.updateTemplates(converted)
          return sendJSON(res, 200, { ok: true, updated: Object.keys(converted) })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/confirmations — list pending confirmations
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'confirmations') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })

          // GET list
          if (req.method === 'GET' && parts.length === 3) {
            const list = typeof ma.getConfirmations === 'function' ? ma.getConfirmations() : []
            return sendJSON(res, 200, { confirmations: list })
          }

          // POST /intelligence/multi-agent/confirmations/:id/approve
          if (req.method === 'POST' && parts.length === 5 && parts[4] === 'approve') {
            const id = parts[3]
            const body = await parseBody(req)
            try {
              const result = await ma.approveDestructiveConfirmation(id, body?.approver)
              return sendJSON(res, 200, { ok: true, result })
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          }

          // POST /intelligence/multi-agent/confirmations/:id/reject
          if (req.method === 'POST' && parts.length === 5 && parts[4] === 'reject') {
            const id = parts[3]
            const body = await parseBody(req)
            try {
              ma.rejectDestructiveConfirmation(id, body?.approver, body?.reason)
              return sendJSON(res, 200, { ok: true })
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          }

          return sendJSON(res, 405, { error: 'method not allowed on confirmations endpoint' })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET/POST notification filter for multi-agent tool announcements
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/notification-filter') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const filter = typeof ma.getNotificationFilter === 'function' ? ma.getNotificationFilter() : null
          return sendJSON(res, 200, { filter })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      if (req.method === 'POST' && url.pathname === '/intelligence/multi-agent/notification-filter') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'expected notification filter object' })
          ma.updateNotificationFilter(body)
          return sendJSON(res, 200, { ok: true })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Multi-Agent Dialectic control endpoints (admin) ───────────────────────

      // POST /intelligence/multi-agent/dialectic/spawn - spawn a Yang/Yin/Serenity trio
      if (req.method === 'POST' && url.pathname === '/intelligence/multi-agent/dialectic/spawn') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const body = await parseBody(req)
          const opts: any = {}
          if (body?.name) opts.name = body.name
          if (body?.initialInput) opts.initialInput = body.initialInput
          if (typeof body?.maxIterations === 'number') opts.maxIterations = body.maxIterations
          if (typeof body?.intervalMs === 'number') opts.intervalMs = body.intervalMs
          if (typeof body?.allowDestructive === 'boolean') opts.allowDestructive = body.allowDestructive
          if (body?.providers && typeof body.providers === 'object') opts.providers = body.providers
          try {
            const r = await ma.spawnDialecticCassis(opts)
            // Retrieve instance metadata (if available)
            const inst = ma.getDialectic?.(r.dialecticId)
            const meta = inst ? {
              sessionId: inst.sessionId,
              createdAt: inst.createdAt,
              updatedAt: inst.updatedAt,
              initialInput: inst.initialInput,
              providers: inst.providers ?? { yang: inst.agents[0]?.provider, yin: inst.agents[1]?.provider, serenity: inst.agents[2]?.provider },
            } : undefined
            return sendJSON(res, 200, { ok: true, dialecticId: r.dialecticId, agents: r.agents.map((a: any) => ({ id: a.id, role: a.role.name, provider: a.provider || null })), meta })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/start - start loop
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'start' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          const body = await parseBody(req)
          try {
            ma.startDialecticCassisLoop(id, { intervalMs: body?.intervalMs, maxIterations: body?.maxIterations, timeoutMs: body?.timeoutMs, initialInput: body?.initialInput })
            return sendJSON(res, 200, { ok: true })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/stop - stop loop
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'stop' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          const body = await parseBody(req)
          try {
            ma.stopDialecticCassis(id, body?.reason || 'admin_stop')
            return sendJSON(res, 200, { ok: true })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/resume - resume a paused swarm (optionally update scheduling)
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'resume' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          const body = await parseBody(req)
          try {
            const ok = ma.resumeDialecticCassis(id, { intervalMs: body?.intervalMs, maxIterations: body?.maxIterations })
            return sendJSON(res, 200, { ok })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/schedule - update scheduling for a swarm
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'schedule' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          const body = await parseBody(req)
          try {
            ma.updateDialecticScheduling(id, { intervalMs: body?.intervalMs, maxIterations: body?.maxIterations, stopConfidenceThreshold: body?.stopConfidenceThreshold })
            return sendJSON(res, 200, { ok: true })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/trigger - request an immediate iteration without changing scheduling
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'trigger' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          try {
            const ok = ma.requestImmediateDialecticIteration(id)
            return sendJSON(res, 200, { ok })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/dialectic - list active dialectic swarms
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/dialectic') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const list = ma.listDialecticSwarms?.() || []
          return sendJSON(res, 200, { dialectics: list })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/dialectic/:id/history - get iteration history
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 4 && req.method === 'GET') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          try {
            // Prefer persisted KV history
            const mem = daemon.intelligence?.memory
            if (mem) {
              const history = await mem.kv_get(`dialectic:instance:${id}:history`) as any[] | undefined
              if (history) return sendJSON(res, 200, { dialecticId: id, history })
            }

            // Fallback to in-memory snapshot
            const inst = ma.getDialectic?.(id)
            if (!inst) return sendJSON(res, 404, { error: 'not found' })
            return sendJSON(res, 200, { dialecticId: id, history: inst.history || [] })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/dialectic/:id/stats - aggregated statistics for a dialectic
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'stats' && req.method === 'GET') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          try {
            const mem = daemon.intelligence?.memory
            const history = mem ? (await mem.kv_get(`dialectic:instance:${id}:history`) as any[] || []) : (ma.getDialectic?.(id)?.history || [])
            const total = history.length
            const totalLatency = history.reduce((s: number, it: any) => s + (Number(it.durationMs) || 0), 0)
            const totalCost = history.reduce((s: number, it: any) => s + (Number(it.costUsd) || 0), 0)
            const avgLatency = total > 0 ? Math.round(totalLatency / total) : 0
            return sendJSON(res, 200, { dialecticId: id, totalIterations: total, avgLatencyMs: avgLatency, totalCostUsd: totalCost })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Subagent endpoints ─────────────────────────────────────────────────

      // GET /subagents - list all tracked subagents
      if (req.method === 'GET' && url.pathname === '/subagents') {
        try {
          const tracker = daemon.subagentTracker
          if (!tracker) return sendJSON(res, 503, { error: 'subagent tracker not initialised' })
          const parentFilter = url.searchParams.get('parent')
          const statusFilter = url.searchParams.get('status')
          let list = tracker.list()
          if (parentFilter) {
            list = list.filter((s: any) => s.parentSessionId === parentFilter)
          }
          if (statusFilter) {
            list = list.filter((s: any) => s.status === statusFilter)
          }
          return sendJSON(res, 200, { 
            subagents: list.map((s: any) => ({
              runId: s.runId,
              label: s.label,
              status: s.status,
              parentSessionId: s.parentSessionId,
              sessionKey: s.sessionKey,
              model: s.model,
              createdAt: s.createdAt,
              startedAt: s.startedAt,
              completedAt: s.completedAt,
              durationMs: s.durationMs,
              tokensUsed: s.tokensUsed,
              hasResult: !!s.result || !!s.error,
            }))
          })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /subagents/:runId - get specific subagent status
      if (parts[0] === 'subagents' && parts.length === 2 && req.method === 'GET') {
        try {
          const tracker = daemon.subagentTracker
          if (!tracker) return sendJSON(res, 503, { error: 'subagent tracker not initialised' })
          const runId = parts[1]
          const info = tracker.get(runId)
          if (!info) return sendJSON(res, 404, { error: 'subagent not found' })
          return sendJSON(res, 200, {
            subagent: {
              runId: info.runId,
              label: info.label,
              status: info.status,
              task: info.task,
              parentSessionId: info.parentSessionId,
              sessionKey: info.sessionKey,
              model: info.model,
              timeoutSeconds: info.timeoutSeconds,
              createdAt: info.createdAt,
              startedAt: info.startedAt,
              completedAt: info.completedAt,
              durationMs: info.durationMs,
              tokensUsed: info.tokensUsed,
            }
          })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /subagents/:runId/result - get subagent result (only if completed/failed/timeout)
      if (parts[0] === 'subagents' && parts.length === 3 && parts[2] === 'result' && req.method === 'GET') {
        try {
          const tracker = daemon.subagentTracker
          if (!tracker) return sendJSON(res, 503, { error: 'subagent tracker not initialised' })
          const runId = parts[1]
          const result = tracker.getResult(runId)
          if (!result) {
            const info = tracker.get(runId)
            if (!info) return sendJSON(res, 404, { error: 'subagent not found' })
            return sendJSON(res, 202, { 
              status: info.status, 
              message: 'Subagent still running or result not yet available' 
            })
          }
          return sendJSON(res, 200, {
            runId,
            result: result.result,
            error: result.error,
            durationMs: result.durationMs,
          })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /subagents/prune - manually prune old subagent entries
      if (req.method === 'POST' && url.pathname === '/subagents/prune') {
        try {
          const tracker = daemon.subagentTracker
          if (!tracker) return sendJSON(res, 503, { error: 'subagent tracker not initialised' })
          const body = await parseBody(req)
          const maxAgeMs = body?.maxAgeMs || 24 * 60 * 60 * 1000 // default 24h
          const maxEntries = body?.maxEntries
          const removed = tracker.prune(maxAgeMs, maxEntries)
          return sendJSON(res, 200, { pruned: removed })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── T3: Delegation acknowledgment ──────────────────────────────────────
      if (req.method === 'POST' && url.pathname === '/delegation/ack') {
        try {
          const body = await parseBody(req)
          const { delegationId, spawnedSessionId, status: ackStatus, error: ackError, result: ackResult } = body as any

          if (!delegationId) {
            return sendJSON(res, 400, { error: 'Missing delegationId' })
          }

          const tracking = delegationTracker.get(delegationId)
          if (!tracking) {
            return sendJSON(res, 404, { error: 'Delegation not found' })
          }

          if (ackStatus === 'executing' && spawnedSessionId) {
            tracking.status = 'executing'
            tracking.spawnedSessionId = spawnedSessionId
            tracking.acknowledgedAt = Date.now()

            // Link to team if T2 already created one for this session
            const teamId = subagentToTeamMap.get(spawnedSessionId)
            if (teamId) tracking.teamId = teamId

            logger.info('[admin-api] Delegation acknowledged', { delegationId, spawnedSessionId })
          } else if (ackStatus === 'failed') {
            tracking.status = 'failed'
            tracking.result = ackError || 'Unknown error'
            logger.warn('[admin-api] Delegation failed', { delegationId, error: ackError })
          } else if (ackStatus === 'completed') {
            tracking.status = 'completed'
            tracking.completedAt = Date.now()
            tracking.result = ackResult
            logger.info('[admin-api] Delegation completed', { delegationId })
          }

          return sendJSON(res, 200, { ok: true, status: tracking.status })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Team Orchestration endpoints ────────────────────────────────────────

      if (parts[0] === 'teams') {
        const to = daemon.intelligence?.teamOrchestrator as any

        // POST /teams — create and start a new team
        // Accepts optional sessionId for context packaging (job handoff)
        if (parts.length === 1 && req.method === 'POST') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const body = await parseBody(req)
            if (!body?.goal) return sendJSON(res, 400, { error: 'goal is required' })

            // T1-2: If sessionId provided, prepend session context to the goal
            let enrichedGoal = body.goal
            if (body.sessionId) {
              try {
                const handoffCtx = await buildHandoffContext(body.sessionId)
                if (handoffCtx) {
                  enrichedGoal = handoffCtx + body.goal
                }
              } catch (err) {
                logger.debug('[admin-api] buildHandoffContext failed, using raw goal', { error: String(err) })
              }
            }

            const config = {
              goal: enrichedGoal,
              name: body.name || undefined,
              budget: {
                maxTokens: body.maxTokens || 500_000,
                maxAgents: body.maxAgents || 5,
                maxDepth: body.maxDepth || 4,
                maxDurationMs: body.maxDurationMs || 60 * 60_000,
              },
              checkpoint: {
                mode: body.checkpointMode || 'cassi',
                budgetThresholdPct: body.budgetThresholdPct || 50,
                completedGoalsInterval: body.completedGoalsInterval || 3,
                autoApproveTimeoutMs: body.autoApproveTimeoutMs || 5 * 60_000,
              },
              provider: body.provider || undefined,
              allowDestructive: body.allowDestructive || false,
              supervisorSessionId: body.sessionId || undefined,
            }

            const team = to.createTeam(config)
            return sendJSON(res, 201, {
              teamId: team.id,
              status: team.status || 'created',
              coordinatorAgentId: team.coordinatorAgentId || null,
            })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams — list all teams
        if (parts.length === 1 && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const teams = to.listAllTeams().map((t: any) => ({
              id: t.id,
              status: t.status,
              goal: t.config?.goal,
              startedAt: t.startedAt,
              completedAt: t.completedAt,
              agentCount: t.agentIds?.length || 0,
              coordinatorAgentId: t.coordinatorAgentId,
            }))
            return sendJSON(res, 200, { teams })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams/status?teamId=xxx — get detailed team status
        if (parts.length === 2 && parts[1] === 'status' && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const teamId = url.searchParams.get('teamId') || undefined
            // If no teamId provided, use the most recently active team
            let resolvedTeamId = teamId
            if (!resolvedTeamId) {
              const all = to.listAllTeams()
              const active = all.find((t: any) => t.status === 'running' || t.status === 'paused')
              resolvedTeamId = active?.id || all[all.length - 1]?.id
            }
            if (!resolvedTeamId) return sendJSON(res, 404, { error: 'No teams found' })

            const status = to.getTeamStatus(resolvedTeamId)
            if (!status) return sendJSON(res, 404, { error: `Team ${resolvedTeamId} not found` })

            return sendJSON(res, 200, status)
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams/tree?teamId=xxx — get goal tree visualization
        if (parts.length === 2 && parts[1] === 'tree' && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const teamId = url.searchParams.get('teamId') || undefined
            let resolvedTeamId = teamId
            if (!resolvedTeamId) {
              const all = to.listAllTeams()
              const active = all.find((t: any) => t.status === 'running' || t.status === 'paused')
              resolvedTeamId = active?.id || all[all.length - 1]?.id
            }
            if (!resolvedTeamId) return sendJSON(res, 404, { error: 'No teams found' })

            const goalTree = to.getGoalTree(resolvedTeamId)
            if (!goalTree) return sendJSON(res, 404, { error: `Team ${resolvedTeamId} has no goal tree` })

            return sendJSON(res, 200, {
              teamId: resolvedTeamId,
              tree: goalTree.renderTree(),
              progress: goalTree.getProgressReport(),
            })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // POST /teams/pause — pause a team
        if (parts.length === 2 && parts[1] === 'pause' && req.method === 'POST') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const body = await parseBody(req)
            const teamId = body?.teamId || resolveLatestTeamId(to)
            if (!teamId) return sendJSON(res, 400, { error: 'teamId is required (or no active teams found)' })

            to.pauseTeam(teamId)
            return sendJSON(res, 200, { teamId, status: 'paused' })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // POST /teams/resume — resume a paused team
        if (parts.length === 2 && parts[1] === 'resume' && req.method === 'POST') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const body = await parseBody(req)
            const teamId = body?.teamId || resolveLatestTeamId(to)
            if (!teamId) return sendJSON(res, 400, { error: 'teamId is required (or no active teams found)' })

            to.resumeTeam(teamId)
            return sendJSON(res, 200, { teamId, status: 'running' })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // POST /teams/cancel — cancel a team
        if (parts.length === 2 && parts[1] === 'cancel' && req.method === 'POST') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const body = await parseBody(req)
            const teamId = body?.teamId || resolveLatestTeamId(to)
            if (!teamId) return sendJSON(res, 400, { error: 'teamId is required (or no active teams found)' })

            await to.cancelTeam(teamId, body?.reason || 'Cancelled by user')
            return sendJSON(res, 200, { teamId, status: 'cancelled' })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams/checkpoints?teamId=xxx — list pending checkpoints
        if (parts.length === 2 && parts[1] === 'checkpoints' && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const teamId = url.searchParams.get('teamId') || undefined
            const checkpoints = to.listPendingCheckpoints(teamId)
            return sendJSON(res, 200, { checkpoints })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // POST /teams/checkpoints/:checkpointId — respond to a checkpoint
        if (parts.length === 3 && parts[1] === 'checkpoints' && req.method === 'POST') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const checkpointId = parts[2]
            const body = await parseBody(req)
            if (!body?.action) return sendJSON(res, 400, { error: 'action is required (approve|reject|steer)' })
            if (!['approve', 'reject', 'steer'].includes(body.action)) {
              return sendJSON(res, 400, { error: 'action must be approve, reject, or steer' })
            }

            to.handleSupervisorResponse(checkpointId, {
              action: body.action,
              message: body.message || undefined,
            })
            return sendJSON(res, 200, { checkpointId, action: body.action })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams/events?teamId=xxx — fetch team event log (non-streaming)
        if (parts.length === 2 && parts[1] === 'events' && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })

            let teamId = url.searchParams.get('teamId') || ''
            if (!teamId) teamId = resolveLatestTeamId(to) || ''
            if (!teamId) return sendJSON(res, 404, { error: 'No active teams found' })

            const team = to.getTeam(teamId)
            if (!team) return sendJSON(res, 404, { error: `Team ${teamId} not found` })

            const limitParam = url.searchParams.get('limit')
            const limit = limitParam ? parseInt(limitParam, 10) : 50

            const eventLog = to.getTeamEventLog(teamId) || []
            const events = eventLog.slice(-limit)

            return sendJSON(res, 200, { teamId, total: eventLog.length, events })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams/stream?teamId=xxx — SSE endpoint for real-time team progress
        if (parts.length === 2 && parts[1] === 'stream' && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })

            const teamId = url.searchParams.get('teamId') || ''
            if (!teamId) return sendJSON(res, 400, { error: 'teamId query parameter is required' })

            const team = to.getTeam(teamId)
            if (!team) return sendJSON(res, 404, { error: `Team ${teamId} not found` })

            // SSE headers
            res.writeHead(200, {
              'Content-Type': 'text/event-stream',
              'Cache-Control': 'no-cache, no-transform',
              'Connection': 'keep-alive',
              'X-Accel-Buffering': 'no',
            })

            const connId = `team_sse_${++sseConnectionId}`
            sseConnections.set(connId, { res, sessionId: `team:${teamId}`, connectedAt: Date.now() })

            // Helper to write an SSE event
            const sendSSE = (eventType: string, payload: unknown) => {
              try {
                res.write(`event: ${eventType}\n`)
                res.write(`data: ${JSON.stringify(payload)}\n\n`)
              } catch { /* client disconnected */ }
            }

            // Send initial status snapshot
            const status = to.getTeamStatus(teamId)
            if (status) {
              sendSSE('snapshot', {
                teamId,
                team: status.team,
                goalTree: status.goalTree,
                progress: status.progress,
                activeAgents: status.activeAgents,
                pendingCheckpoints: status.pendingCheckpoints,
              })
            }

            res.write(': connected\n\n')

            // Determine if an event belongs to this team
            const isTeamEvent = (event: any): boolean => {
              // Direct teamId match (team:* events)
              if (event.teamId === teamId) return true
              // Agent/autonomy events — map agentId back to team via orchestrator
              if (event.agentId && to.agentToTeam?.get(event.agentId) === teamId) return true
              return false
            }

            // Event types to subscribe to
            const teamEventTypes = [
              'team:started', 'team:completed', 'team:failed', 'team:cancelled',
              'team:paused', 'team:resumed', 'team:budget:warning', 'team:checkpoint',
              'agent:spawned', 'agent:completed', 'agent:error',
              'autonomy:loop_started', 'autonomy:loop_stopped',
              'autonomy:loop_paused', 'autonomy:loop_resumed',
              'autonomy:iteration', 'autonomy:iteration_error',
              'autonomy:delegation_requested', 'autonomy:blocked',
            ]

            // Subscribe to each event type on daemon.bus (old bus — no wildcard)
            const handlers: Array<{ type: string; handler: (e: any) => void }> = []
            for (const eventType of teamEventTypes) {
              const handler = (e: any) => {
                if (!isTeamEvent(e)) return
                sendSSE(e.type || eventType, e)
              }
              daemon.bus.on(eventType, handler)
              handlers.push({ type: eventType, handler })
            }

            // Keep-alive ping every 15s
            const ping = setInterval(() => {
              try { res.write(': ping\n\n') } catch { clearInterval(ping) }
            }, 15_000)
            try { (ping as any).unref?.() } catch {}

            // Cleanup on disconnect
            req.on('close', () => {
              clearInterval(ping)
              sseConnections.delete(connId)
              for (const { type, handler } of handlers) {
                try { daemon.bus.off(type, handler) } catch {}
              }
            })

            return // Keep connection open
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams/:teamId — get a specific team by ID
        if (parts.length === 2 && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const teamId = parts[1]
            const team = to.getTeam(teamId)
            if (!team) return sendJSON(res, 404, { error: `Team ${teamId} not found` })

            const goalTree = to.getGoalTree(teamId)
            return sendJSON(res, 200, {
              team,
              goalTree: goalTree?.renderTree(),
              progress: goalTree?.getProgressReport(),
            })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // ── C3: Agent-level team coordination endpoints ──────────────────────
        // These mirror the 8 internal team-coordinator tools, exposed via HTTP
        // for use by external execution backends (OpenCode sessions acting as team agents).

        // POST /teams/agent/message — send message to another agent in the team
        if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'message' && req.method === 'POST') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const ds = daemon.sessionDigestStore
            if (!ds) return sendJSON(res, 503, { error: 'SessionDigestStore not available' })
            const body = await parseBody(req)
            if (!body?.toAgentId || !body?.message) {
              return sendJSON(res, 400, { error: 'toAgentId and message are required' })
            }
            const fromSessionId = body.fromSessionId || body.agentId ? `agent:${body.agentId}` : 'external'
            const toSessionId = `agent:${body.toAgentId}`
            const msgId = ds.sendMessage(toSessionId, fromSessionId, body.message)
            return sendJSON(res, 200, { messageId: msgId, toAgentId: body.toAgentId })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams/agent/result?agentId=xxx — get result from a completed agent
        if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'result' && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const agentId = url.searchParams.get('agentId')
            if (!agentId) return sendJSON(res, 400, { error: 'agentId query parameter is required' })

            for (const team of to.listAllTeams()) {
              const goalId = team.agentGoalMap?.[agentId]
              if (!goalId) continue
              const goal = team.goals?.[goalId]
              if (!goal) return sendJSON(res, 404, { error: `Goal for agent ${agentId} not found` })

              return sendJSON(res, 200, {
                agentId,
                teamId: team.id,
                goalTitle: goal.title,
                status: goal.status,
                result: goal.result ?? null,
              })
            }
            return sendJSON(res, 404, { error: `Agent ${agentId} not found in any team` })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams/agent/list?teamId=xxx — list all agents in a team
        if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'list' && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const teamId = url.searchParams.get('teamId')
            if (!teamId) return sendJSON(res, 400, { error: 'teamId query parameter is required' })
            const team = to.getTeam(teamId)
            if (!team) return sendJSON(res, 404, { error: `Team ${teamId} not found` })

            const agents = (team.agentIds || []).map((aid: string) => {
              const goalId = team.agentGoalMap?.[aid]
              const goal = goalId ? team.goals?.[goalId] : undefined
              return {
                agentId: aid,
                isCoordinator: aid === team.coordinatorAgentId,
                goalId: goalId ?? null,
                goalTitle: goal?.title ?? null,
                goalStatus: goal?.status ?? 'unknown',
                roleHint: goal?.roleHint ?? (aid === team.coordinatorAgentId ? 'team-coordinator' : null),
              }
            })
            return sendJSON(res, 200, { teamId, agents })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // POST /teams/agent/update-plan — create or modify sub-goals
        if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'update-plan' && req.method === 'POST') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const body = await parseBody(req)
            if (!body?.teamId) return sendJSON(res, 400, { error: 'teamId is required' })

            const goalTree = to.getGoalTree(body.teamId)
            if (!goalTree) return sendJSON(res, 404, { error: `Goal tree for team ${body.teamId} not found` })

            const results: any[] = []
            // Add new sub-goals
            if (body.addGoals && Array.isArray(body.addGoals)) {
              for (const g of body.addGoals) {
                if (!g.title || !g.parentGoalId) continue
                const newId = goalTree.addSubGoal(g.parentGoalId, {
                  title: g.title,
                  description: g.description || '',
                  roleHint: g.roleHint || undefined,
                })
                results.push({ action: 'added', goalId: newId, title: g.title })
              }
            }
            // Update existing goals
            if (body.updateGoals && Array.isArray(body.updateGoals)) {
              for (const g of body.updateGoals) {
                if (!g.goalId) continue
                if (g.status) goalTree.updateStatus(g.goalId, g.status, g.result || undefined)
                results.push({ action: 'updated', goalId: g.goalId, status: g.status })
              }
            }

            return sendJSON(res, 200, { teamId: body.teamId, results })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // POST /teams/agent/complete-goal — signal completion of a team goal
        if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'complete-goal' && req.method === 'POST') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const body = await parseBody(req)
            if (!body?.teamId || !body?.goalId) {
              return sendJSON(res, 400, { error: 'teamId and goalId are required' })
            }

            const goalTree = to.getGoalTree(body.teamId)
            if (!goalTree) return sendJSON(res, 404, { error: `Goal tree for team ${body.teamId} not found` })

            goalTree.updateStatus(body.goalId, body.success === false ? 'failed' : 'completed', {
              summary: body.summary || '',
              output: body.result || body.summary || '',
              tokensUsed: body.tokensUsed || 0,
              durationMs: body.durationMs || 0,
              error: body.error || undefined,
            })

            return sendJSON(res, 200, { teamId: body.teamId, goalId: body.goalId, status: body.success === false ? 'failed' : 'completed' })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // GET /teams/agent/goal-tree?teamId=xxx — get the full goal tree (for agents)
        if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'goal-tree' && req.method === 'GET') {
          try {
            if (!to) return sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
            const teamId = url.searchParams.get('teamId')
            if (!teamId) return sendJSON(res, 400, { error: 'teamId query parameter is required' })

            const goalTree = to.getGoalTree(teamId)
            if (!goalTree) return sendJSON(res, 404, { error: `Goal tree for team ${teamId} not found` })

            return sendJSON(res, 200, {
              teamId,
              tree: goalTree.renderTree(),
              progress: goalTree.getProgressReport(),
            })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        }
      }

      // ── Sessions endpoints ─────────────────────────────────────────────────

      if (parts[0] === 'sessions') {
        // POST /sessions/:id/turn — process a turn (V2 or V1 pipeline)
        if (parts.length === 3 && parts[2] === 'turn' && req.method === 'POST' && !(req.headers.accept || '').toLowerCase().includes('text/event-stream')) {
          const sessionId = parts[1]
          if (!sessionId) return sendJSON(res, 400, { error: 'missing sessionId' })

          const body = await parseBody(req)
          const content: string = body?.content
          if (!content) return sendJSON(res, 400, { error: 'missing content' })

          try {
            const channelId = body?.channelId || 'channel:cli'
            const senderId = body?.senderId || sessionId

            // Check if V2 is enabled
            const useV2 = (daemon as any).useV2 && (daemon as any).v2

            if (useV2) {
              // V2 path: simplified session flow
              logger.info(`[admin-api] Using V2 for turn`, { sessionId: sessionId.slice(0, 8) })
              const startTime = Date.now()
              const result = await (daemon as any).v2.processMessage(channelId, senderId, content)
              const durationMs = Date.now() - startTime

              return sendJSON(res, 200, {
                ok: true,
                sessionId: result.sessionId,
                response: result.response,
                model: 'v2', // V2 tracks model internally
                tokensUsed: 0, // V2 tracks tokens internally
                durationMs,
                v2: true,
              })
            }

            // V1 path: traditional pipeline
            if (!daemon.pipeline) return sendJSON(res, 503, { error: 'pipeline not ready' })

            const { randomUUID } = await import('node:crypto')
            const inbound = {
              id: randomUUID(),
              sessionId,
              channelId,
              senderId,
              content,
              timestamp: new Date(),
            }

            // Get or create session
            const session = daemon.sessions.getOrCreateById(
              sessionId,
              inbound.channelId,
              inbound.senderId,
              {
                model: body?.model || daemon.config?.get?.('session.model', getModelSpec('main')),
                thinking: body?.thinking || daemon.config?.get?.('session.thinking', 'high'),
                systemPrompt: body?.systemPrompt,
              }
            )

            // Run dialectic if enabled
            let dialecticResult: any = null
            const dialecticEnabled = body?.dialectic !== false && daemon.intelligence?.dialectic

            if (dialecticEnabled) {
              try {
                const dialectic = daemon.intelligence.dialectic
                const context = {
                  recentMemories: [],
                  availableTools: Object.keys(daemon.toolRegistry?.getAll?.() || {}),
                  sessionHistory: session.history,
                  taskGuide: body?.taskGuide || `Process user message: ${content.slice(0, 100)}...`,
                }

                dialecticResult = await dialectic.processTurn(
                  sessionId,
                  inbound.id,
                  content,
                  context,
                  { mode: body?.dialecticMode || 'parallel' }
                )
              } catch (dialecticErr) {
                logger.warn(`[admin-api] dialectic error: ${String(dialecticErr)}`)
                // Continue without dialectic result
              }
            }

            // Process through pipeline
            let result: any;
            try {
              result = await daemon.pipeline.process(inbound)
            } catch (pipelineErr) {
              logger.error(`[admin-api] pipeline.process failed: ${String(pipelineErr)}`);
              throw pipelineErr;
            }

            // Build response
            const response: any = {
              ok: true,
              sessionId,
              response: result.response,
              model: result.model,
              tokensUsed: result.tokensUsed,
              durationMs: result.durationMs,
              toolCalls: result.toolCalls,
              tool_outputs: result.tool_outputs,
              dialectic: dialecticResult ? {
                signalInjected: dialecticResult.signalInjected,
                yangBranches: dialecticResult.yang?.branches?.length || 0,
                yinCritiques: dialecticResult.yin?.critiques?.length || 0,
                synthesis: dialecticResult.serenity?.synthesis?.hasSignal
                  ? {
                      type: dialecticResult.serenity.synthesis.signal?.type,
                      content: dialecticResult.serenity.synthesis.signal?.content,
                      confidence: dialecticResult.serenity.synthesis.signal?.confidence,
                    }
                  : null,
              } : null,
            }

            return sendJSON(res, 200, response)
          } catch (err) {
            logger.error(`[admin-api] turn error: ${String(err)}`)
            return sendJSON(res, 500, { error: String(err) })
          }
        }

        // POST /sessions/:id/turn/stream — SSE streaming turn endpoint
        if (parts.length === 4 && parts[2] === 'turn' && parts[3] === 'stream' && req.method === 'POST' && (req.headers.accept || '').toLowerCase().includes('text/event-stream')) {
          const sessionId = parts[1]
          if (!sessionId) return sendJSON(res, 400, { error: 'missing sessionId' })

          // Check if V2 is enabled - V2 doesn't support SSE streaming yet, so we fall back to V1
          const useV2 = (daemon as any).useV2 && (daemon as any).v2
          if (useV2) {
            // V2 doesn't have SSE streaming - return error suggesting non-streaming endpoint
            return sendJSON(res, 501, { 
              error: 'SSE streaming not supported in V2 mode. Use POST /sessions/:id/turn without Accept: text/event-stream header'
            })
          }

          if (!daemon.pipeline) {
            logger.error('[admin-api] SSE stream rejected: pipeline not ready')
            return sendJSON(res, 503, { error: 'pipeline not ready' })
          }

          logger.info(`[admin-api] SSE stream request START: session=${sessionId.slice(0,8)}`)

          const body = await parseBody(req)
          const content: string = body?.content
          const model: string = body?.model || 'unknown'
          if (!content) {
            logger.error('[admin-api] SSE stream rejected: missing content')
            return sendJSON(res, 400, { error: 'missing content' })
          }

          logger.info(`[admin-api] SSE stream request: session=${sessionId.slice(0,8)}, model=${model}, content_length=${content.length}`)

          // Setup SSE headers
          res.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
          })

          // Track if response has ended to avoid writing after close
          let responseEnded = false;
          let streamCompleted = false;

          const sendEvent = (type: string, data: any) => {
            if (responseEnded || !res.writable) return;
            try {
              const written = res.write(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`)
              if (!written) {
                // Backpressure - wait for drain
                logger.debug(`[admin-api] SSE backpressure on ${type} event`)
              }
            } catch (err) {
              // Client disconnected, stop trying to send
              logger.debug(`[admin-api] SSE write failed, client may have disconnected: ${String(err)}`)
              responseEnded = true;
            }
          }

          // Socket timeout handling - prevent silent hangs
          req.socket.setTimeout(5 * 60 * 1000); // 5 minute timeout
          req.socket.on('timeout', () => {
            logger.warn(`[admin-api] SSE socket timeout: session=${sessionId.slice(0,8)}`)
            if (!streamCompleted) {
              sendEvent('error', { error: 'Request timeout' })
              res.end()
            }
          })

          // Keep-alive ping every 15s to prevent connection drops during tool execution
          const pingInterval = setInterval(() => {
            if (!responseEnded && res.writable) {
              try { res.write(': ping\n\n') } catch { clearInterval(pingInterval) }
            } else {
              clearInterval(pingInterval)
            }
          }, 15000)
          try { (pingInterval as any).unref?.() } catch {}

          // Cleanup on close
          const cleanup = () => {
            if (streamCompleted) return;
            clearInterval(pingInterval);
            responseEnded = true;
            streamCompleted = true;
            logger.info(`[admin-api] SSE stream closed: session=${sessionId.slice(0,8)}`);
          };
          req.on('close', cleanup);
          res.on('close', cleanup);
          res.on('finish', () => {
            streamCompleted = true;
            cleanup();
          });
          res.on('error', (err) => {
            logger.error(`[admin-api] SSE stream error: ${String(err)}`);
            streamCompleted = true;
            cleanup();
          });

          try {
            const { randomUUID } = await import('node:crypto')
            const inbound = {
              id: randomUUID(),
              sessionId,
              channelId: body?.channelId || 'channel:cli',
              senderId: body?.senderId || sessionId,
              content,
              timestamp: new Date(),
            }

            // Get or create session
            const session = daemon.sessions.getOrCreateById(
              sessionId,
              inbound.channelId,
              inbound.senderId,
              {
                model: body?.model || daemon.config?.get?.('session.model', getModelSpec('main')),
                thinking: body?.thinking || daemon.config?.get?.('session.thinking', 'high'),
                systemPrompt: body?.systemPrompt,
              }
            )

            // Run dialectic if enabled
            let dialecticResult: any = null
            const dialecticEnabled = body?.dialectic !== false && daemon.intelligence?.dialectic

            if (dialecticEnabled) {
              try {
                const dialectic = daemon.intelligence.dialectic
                const context = {
                  recentMemories: [],
                  availableTools: Object.keys(daemon.toolRegistry?.getAll?.() || {}),
                  sessionHistory: session.history,
                  taskGuide: body?.taskGuide || `Process user message: ${content.slice(0, 100)}...`,
                }

                dialecticResult = await dialectic.processTurn(
                  sessionId,
                  inbound.id,
                  content,
                  context,
                  { mode: body?.dialecticMode || 'parallel' }
                )

                // Emit dialectic stages separately with labels
                if (dialecticResult.yang?.branches?.length > 0) {
                  for (const branch of dialecticResult.yang.branches) {
                    sendEvent('dialectic', {
                      stage: 'yang',
                      label: 'Thesis - Exploring possibilities',
                      content: branch.argument || branch.content,
                      confidence: branch.confidence,
                    })
                  }
                }

                if (dialecticResult.yin?.critiques?.length > 0) {
                  for (const critique of dialecticResult.yin.critiques) {
                    sendEvent('dialectic', {
                      stage: 'yin',
                      label: 'Antithesis - Critical analysis',
                      content: critique.critique || critique.content,
                      confidence: critique.confidence,
                    })
                  }
                }

                // Send dialectic synthesis if available (CassiCore's multi-agent reasoning, NOT LLM thinking)
                if (dialecticResult.serenity?.synthesis?.hasSignal) {
                  sendEvent('dialectic', {
                    stage: 'serenity',
                    label: 'Synthesis - Unified conclusion',
                    type: dialecticResult.serenity.synthesis.signal?.type,
                    content: dialecticResult.serenity.synthesis.signal?.content,
                    confidence: dialecticResult.serenity.synthesis.signal?.confidence,
                  })
                }
              } catch (dialecticErr) {
                logger.warn(`[admin-api] dialectic error: ${String(dialecticErr)}`)
              }
            }

            // Process through pipeline - the pipeline emits worker:message events for tokens/thinking
            // We need to capture these and forward as SSE events
            let tokenCount = 0
            const onWorkerMessage = (ev: any) => {
              const payload = ev?.payload
              if (!payload || payload.sessionId !== sessionId) return

              if (payload.type === 'turn:token') {
                tokenCount++
                sendEvent('token', { token: payload.token })
              } else if (payload.type === 'turn:tool_call') {
                // Forward tool_call events so CLI knows tools are being invoked
                sendEvent('tool_call', { tool: payload.tool, input: payload.input })
              } else if (payload.type === 'turn:tool_result') {
                // Forward tool_result events so CLI knows tools completed
                sendEvent('tool_result', { toolCallId: payload.toolCallId, isError: payload.isError })
              }
              // Note: turn:thinking events are suppressed to avoid garbled CLI output
              // They are still processed by the subconscious system internally
            }

            daemon.bus.on('worker:message', onWorkerMessage)

            logger.info(`[admin-api] Calling pipeline.process for session ${sessionId.slice(0,8)}...`)

            let result: any;
            try {
              result = await daemon.pipeline.process(inbound)

              logger.info(`[admin-api] SSE stream completed: ${tokenCount} tokens sent, response=${result?.response?.slice(0, 50)}...`)

              // Send completion event with full response and tool call info
              sendEvent('done', {
                model: result?.model,
                tokensUsed: result?.tokensUsed,
                durationMs: result?.durationMs,
                response: result?.response,
                toolCalls: result?.toolCalls,
                tool_outputs: result?.tool_outputs,
                dialectic: dialecticResult ? {
                  signalInjected: dialecticResult.signalInjected,
                } : null,
              })

              res.end()
              streamCompleted = true;
            } catch (pipelineErr) {
              logger.error(`[admin-api] pipeline processing error: ${String(pipelineErr)}`)

              // Send error event if stream is still open
              if (!streamCompleted && !responseEnded) {
                sendEvent('error', {
                  error: String(pipelineErr),
                  type: 'pipeline_error'
                })
                res.end()
                streamCompleted = true;
              }
            } finally {
              daemon.bus.off('worker:message', onWorkerMessage)
            }
          } catch (err) {
            logger.error(`[admin-api] stream turn error: ${String(err)}`)
            if (!streamCompleted && !responseEnded) {
              sendEvent('error', { error: String(err) })
              res.end()
              streamCompleted = true;
            }
          }
          return
        }

        // DELETE /sessions/:id — delete a single session
        if (parts.length === 2 && req.method === 'DELETE') {
          const sessionId = parts[1]
          daemon.sessions.delete(sessionId)
          return sendJSON(res, 200, { ok: true, deleted: 1 })
        }

        // POST /sessions/prune — bulk prune with filter criteria
        if (parts.length === 2 && parts[1] === 'prune' && req.method === 'POST') {
          const body = await parseBody(req) as {
            all?: boolean
            olderThanDays?: number
            channelId?: string
            emptyOnly?: boolean
          } | null

          let deleted = 0

          if (body?.all) {
            deleted = daemon.sessions.pruneAll()
          } else if (body?.channelId) {
            deleted = daemon.sessions.pruneByChannelId(body.channelId)
          } else if (body?.emptyOnly) {
            deleted = daemon.sessions.pruneEmpty()
          } else if (typeof body?.olderThanDays === 'number') {
            deleted = daemon.sessions.pruneOlderThan(body.olderThanDays)
          } else {
            return sendJSON(res, 400, {
              error: 'Provide one of: all, olderThanDays, channelId, emptyOnly',
            })
          }

          return sendJSON(res, 200, { ok: true, deleted })
        }

        // GET /sessions/:id — get session info
        if (parts.length === 2 && req.method === 'GET') {
          const sessionId = parts[1]
          const session = daemon.sessions.get(sessionId)
          if (!session) return sendJSON(res, 404, { error: 'session not found' })
          
          return sendJSON(res, 200, {
            id: session.id,
            channelId: session.channelId,
            senderId: session.senderId,
            createdAt: session.createdAt,
            lastActiveAt: session.lastActiveAt,
            historyLength: session.history.length,
            tokenCount: session.tokenCount,
            config: session.config,
          })
        }

        // GET /sessions — list all sessions (in-memory + disk)
        if (parts.length === 1 && req.method === 'GET') {
          const sessions = daemon.sessions.list()
            .map((s: any) => ({
              id: s.id,
              channelId: s.channelId,
              senderId: s.senderId,
              createdAt: s.createdAt,
              lastActiveAt: s.lastActiveAt,
              historyLength: s.history.length,
              tokenCount: s.tokenCount,
              firstMessage: getFirstUserMessage(s.history || []),
              lastMessage: getLastUserMessage(s.history || []),
            }))
          return sendJSON(res, 200, { sessions })
        }
      }

      // ── Commands endpoints (Legacy/Compatibility) ──────────────────────────

      if (parts[0] === 'commands') {
        // POST /commands/think
        if (parts[1] === 'think' && req.method === 'POST') {
          const body = await parseBody(req)
          const thinker = daemon.intelligence?.thinker
          if (!thinker) return sendJSON(res, 503, { error: 'thinker not available' })
          
          void thinker.think(body?.depth === 'deep' ? 'Think' : 'Ponder').catch(() => {})
          return sendJSON(res, 200, { ok: true })
        }

        // POST /commands/remember
        if (parts[1] === 'remember' && req.method === 'POST') {
          const body = await parseBody(req)
          const memory = daemon.intelligence?.memory
          if (!memory) return sendJSON(res, 503, { error: 'memory not available' })
          
          await memory.store({
            type: 'fact',
            content: body?.note,
            metadata: { tags: ['cli'] }
          })
          return sendJSON(res, 200, { ok: true })
        }

        // GET /commands/recall
        if (parts[1] === 'recall' && req.method === 'GET') {
          const query = url.searchParams.get('query') || ''
          const limit = parseInt(url.searchParams.get('limit') || '5', 10)
          const memory = daemon.intelligence?.memory
          if (!memory) return sendJSON(res, 503, { error: 'memory not available' })
          
          const results = await memory.search(query, { limit })
          return sendJSON(res, 200, { results: results.map((r: { entry: any, score: number }) => ({ ...r.entry, score: r.score })) })
        }

        // POST /commands/execute
        if (parts[1] === 'execute' && req.method === 'POST') {
          const body = await parseBody(req)
          if (!body || !body.command || !body.sessionId) return sendJSON(res, 400, { error: 'missing command or sessionId' })

          const dispatcher = new (await import('./commands.js')).CommandDispatcher(daemon.logger, daemon.sessions, daemon.bus)
          dispatcher.setIntelligence(daemon.intelligence)

          // Note: handle() returns a boolean but doesn't return the text response directly
          // it emits it onto the bus. We'll return 202 accepted.
          void dispatcher.handle(body.sessionId, body.channelId || 'channel:cli', body.command)
          return sendJSON(res, 202, { ok: true, message: 'Command accepted' })
        }
      }

      // ── Memory endpoints (unified API for CLI/TUI) ──────────────────────────

      // POST /memory/store — store a memory entry
      if (parts[0] === 'memory' && parts[1] === 'store' && req.method === 'POST') {
        const body = await parseBody(req)
        const memory = daemon.intelligence?.memory
        if (!memory) return sendJSON(res, 503, { error: 'memory not available' })

        const id = await memory.store({
          type: body?.type || 'fact',
          content: body?.content || body?.note || '',
          metadata: body?.metadata || { tags: ['cli'] },
          sessionId: body?.metadata?.sessionId || body?.sessionId,
        })
        return sendJSON(res, 200, { ok: true, id })
      }

      // GET /memory/search — search memories
      if (parts[0] === 'memory' && parts[1] === 'search' && req.method === 'GET') {
        const query = url.searchParams.get('q') || url.searchParams.get('query') || ''
        const limit = parseInt(url.searchParams.get('limit') || '5', 10)
        const memory = daemon.intelligence?.memory
        if (!memory) return sendJSON(res, 503, { error: 'memory not available' })

        const results = await memory.search(query, { limit })
        return sendJSON(res, 200, results.map((r: { entry: any, score: number }) => ({ entry: r.entry, score: r.score })))
      }

      // GET /memory/recent — get recent memories
      if (parts[0] === 'memory' && parts[1] === 'recent' && req.method === 'GET') {
        const limit = parseInt(url.searchParams.get('limit') || '10', 10)
        const memory = daemon.intelligence?.memory
        if (!memory) return sendJSON(res, 503, { error: 'memory not available' })

        // Search with empty query to get recent entries
        const results = await memory.search('', { limit })
        return sendJSON(res, 200, results.map((r: { entry: any, score: number }) => r.entry))
      }

      // ── Dialectic endpoints (C: Query API) ─────────────────────────────────

      // GET /dialectic/:sessionId/history — recent dialectic turns
      if (parts[0] === 'dialectic' && parts.length === 3 && parts[2] === 'history' && req.method === 'GET') {
        const sessionId = parts[1]
        const limit = parseInt(url.searchParams.get('limit') || '10', 10)
        try {
          const history = await daemon.intelligence?.dialectic?.getRecent?.(sessionId, limit) ?? []
          return sendJSON(res, 200, { sessionId, history })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /dialectic/:sessionId/stats — aggregated statistics
      if (parts[0] === 'dialectic' && parts.length === 3 && parts[2] === 'stats' && req.method === 'GET') {
        const sessionId = parts[1]
        try {
          const stats = await daemon.intelligence?.dialectic?.getStats?.(sessionId) ?? {
            totalTurns: 0, signalsGenerated: 0, signalsInjected: 0, avgLatencyMs: 0, totalCostUsd: 0
          }
          return sendJSON(res, 200, { sessionId, stats })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /dialectic/:sessionId/think — trigger dialectic for a session (admin)
      if (parts[0] === 'dialectic' && parts.length === 3 && parts[2] === 'think' && req.method === 'POST') {
        try {
          const sessionId = parts[1]
          const body = await parseBody(req)
          // Accept same params as the think tool
          const { query, depth, include_history, memory_limit, files, extra_context, wait, structured, include_raw } = body || {}

          const ctxObj = await assembleContext(
            {
              memory: daemon.intelligence?.memory,
              sessionManager: daemon.sessions,
              getPipeline: () => daemon.pipeline,
              logger: daemon.logger,
            },
            {
              sessionId,
              query: query || '',
              includeHistory: include_history !== undefined ? include_history : true,
              memoryLimit: memory_limit || 5,
              files: Array.isArray(files) ? files : (files ? [files] : []),
              extra: extra_context || '',
              workingDir: process.cwd(),
              allowedPaths: [],
            }
          )

          const turnId = `admin-think-${Date.now()}`
          const dialectic = daemon.intelligence?.dialectic
          if (!dialectic) return sendJSON(res, 503, { error: 'dialectic not available' })

          const promise = dialectic.processTurn(sessionId || `admin-session-${Date.now()}`, turnId, query || '', ctxObj)
          if (wait === false) {
            promise.catch((e: any) => daemon.logger?.warn?.('admin: background dialectic failed', { error: String(e) }))
            return sendJSON(res, 200, { ok: true, message: 'Dialectic triggered (async)' })
          }

          const result = await promise
          const out = {
            sessionId,
            turnId,
            depth: depth || 'Ponder',
            yangBranches: result?.yang?.branches?.length ?? 0,
            yinCritiques: result?.yin?.critiques?.length ?? 0,
            serenity: result?.serenity?.synthesis ?? null,
            meta: { totalLatencyMs: result?.totalLatencyMs ?? null, totalCostUsd: result?.totalCostUsd ?? null },
          }
          if (include_raw) (out as any)['raw'] = result
          return sendJSON(res, 200, out)
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /dialectic/:sessionId/stream — WebSocket upgrade handled separately
      if (parts[0] === 'dialectic' && parts.length === 3 && parts[2] === 'stream' && req.method === 'GET') {
        // Return HTML dashboard for browser requests
        const acceptHeader = req.headers['accept'] || '';
        if (acceptHeader.includes('text/html')) {
          try {
            const htmlPath = path.join(process.cwd(), 'public', 'dialectic-observatory.html');
            const html = fs.readFileSync(htmlPath, 'utf8');
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(html);
            return;
          } catch (err) {
            return sendJSON(res, 500, { error: 'Dashboard not found' });
          }
        }
        // Non-WebSocket request without upgrade
        return sendJSON(res, 426, { error: 'WebSocket upgrade required' });
      }

      // ── Chat endpoints (used by CLI) ───────────────────────────────────────

      // GET /observability/prompts/stream — SSE aggregated prompts & tokens
      if (req.method === 'GET' && url.pathname === '/observability/prompts/stream') {
        // Optional query filters: ?session=<id>&provider=<providerId>&includeTokens=true|false
        const sessionFilter = url.searchParams.get('session') || null
        const providerFilter = url.searchParams.get('provider') || null
        const includeTokens = (url.searchParams.get('includeTokens') || 'true') !== 'false'

        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
          'Access-Control-Allow-Origin': '*',
        })
        res.write(': connected\n\n')

        const sendEvent = (eventName: string, payload: unknown) => {
          try {
            // Normalize event name to avoid ':' in SSE event names
            const name = String(eventName).replace(/[:]/g, '.')
            res.write(`event: ${name}\n`)
            res.write(`data: ${JSON.stringify(payload)}\n\n`)
          } catch (err) {
            // Ignore write errors (client disconnected)
          }
        }

        // Named handlers so we can remove them on close
        // Helper to match both public session ids and centralized provider 'sess_' markers
        const matchesSessionFilter = (evSessionId: any) => {
          if (!sessionFilter) return true
          if (!evSessionId) return false
          const s = String(evSessionId)
          if (s === sessionFilter) return true
          if (s === `sess_${sessionFilter}`) return true
          if (s.startsWith(`sess_${sessionFilter}`)) return true
          if (s.includes(sessionFilter)) return true
          // Also check normalized form (strip leading 'sess_')
          if (s.startsWith('sess_') && s.slice(5) === sessionFilter) return true
          return false
        }

        const onProviderStart = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:request_start', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, model: e.model, messageCount: e.messageCount, timestamp: Date.now() })
          } catch {}
        }
        const onProviderEnd = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:request_end', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, tokensUsed: e.tokensUsed, durationMs: e.durationMs, error: e.error || null, timestamp: Date.now() })
          } catch {}
        }
        const onProviderError = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:request_error', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, error: e.error, consecutiveErrors: e.consecutiveErrors, timestamp: Date.now() })
          } catch {}
        }
        const onProviderDedup = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:deduplicated', e)
          } catch {}
        }
        const onProviderRateLimited = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:rate_limited', e)
          } catch {}
        }
        const onProviderErrorReset = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            sendEvent('provider:error_reset', { providerId: e.providerId, timestamp: Date.now() })
          } catch {}
        }
        const onProviderTimeout = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:request_timeout', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, timeoutMs: e.timeoutMs, timestamp: Date.now() })
          } catch {}
        }

        const onWorkerMessage = (ev: any) => {
          try {
            const pluginId = ev.pluginId as string | undefined
            const payload = ev.payload as Record<string, any> | undefined
            const sid = payload?.sessionId || (typeof pluginId === 'string' && pluginId.startsWith('session:') ? pluginId.slice(8) : undefined)
            if (sessionFilter && sid && String(sid) !== sessionFilter) return

            if (payload?.type === 'turn:token') {
              if (!includeTokens) return
              sendEvent('turn.token', { sessionId: sid, token: payload.token, pluginId, timestamp: Date.now() })
            } else if (payload?.type === 'turn:thinking') {
              if (!includeTokens) return
              sendEvent('turn.thinking', { sessionId: sid, token: payload.token, pluginId, timestamp: Date.now() })
            } else if (payload?.type === 'turn:tool_call') {
              sendEvent('turn.tool_call', { sessionId: sid, tool: payload.tool, input: payload.input, timestamp: Date.now() })
            } else if (payload?.type === 'turn:done') {
              sendEvent('turn.done', { sessionId: sid, model: payload.model, tokensUsed: payload.tokensUsed, durationMs: payload.durationMs, timestamp: Date.now() })
            } else if (payload?.type === 'turn:error') {
              sendEvent('turn.error', { sessionId: sid, error: payload.error, timestamp: Date.now() })
            }
          } catch (err) { /* swallow */ }
        }

        const onTurnStart = (e: any) => {
          try {
            if (sessionFilter && String(e.sessionId) !== sessionFilter) return
            sendEvent('turn.start', { sessionId: e.sessionId, message: e.message, timestamp: e.timestamp || Date.now() })
          } catch {}
        }
        const onTurnEnd = (e: any) => {
          try {
            if (sessionFilter && String(e.sessionId) !== sessionFilter) return
            sendEvent('turn.end', { sessionId: e.sessionId, response: e.response, durationMs: e.durationMs, timestamp: Date.now() })
          } catch {}
        }
        const onDialecticStream = (e: any) => {
          try {
            if (sessionFilter && String(e.sessionId) !== sessionFilter) return
            sendEvent('dialectic.stream', e)
          } catch {}
        }

        // Register listeners
        daemon.bus.on('provider:request_start', onProviderStart)
        daemon.bus.on('provider:request_end', onProviderEnd)
        daemon.bus.on('provider:request_error', onProviderError)
        daemon.bus.on('provider:deduplicated', onProviderDedup)
        daemon.bus.on('provider:rate_limited', onProviderRateLimited)
        daemon.bus.on('provider:error_reset', onProviderErrorReset)
        daemon.bus.on('provider:request_timeout', onProviderTimeout)
        daemon.bus.on('worker:message', onWorkerMessage)
        daemon.bus.on('turn:start', onTurnStart)
        daemon.bus.on('turn:end', onTurnEnd)
        daemon.bus.on('dialectic:stream', onDialecticStream)

        // Keep-alive ping every 15s
        const ping = setInterval(() => {
          try { res.write(': ping\n\n') } catch { clearInterval(ping) }
        }, 15_000)
        try { (ping as any).unref?.() } catch {}

        req.on('close', () => {
          clearInterval(ping)
          try { daemon.bus.off('provider:request_start', onProviderStart) } catch {}
          try { daemon.bus.off('provider:request_end', onProviderEnd) } catch {}
          try { daemon.bus.off('provider:request_error', onProviderError) } catch {}
          try { daemon.bus.off('provider:deduplicated', onProviderDedup) } catch {}
          try { daemon.bus.off('provider:rate_limited', onProviderRateLimited) } catch {}
          try { daemon.bus.off('provider:error_reset', onProviderErrorReset) } catch {}
          try { daemon.bus.off('provider:request_timeout', onProviderTimeout) } catch {}
          try { daemon.bus.off('worker:message', onWorkerMessage) } catch {}
          try { daemon.bus.off('turn:start', onTurnStart) } catch {}
          try { daemon.bus.off('turn:end', onTurnEnd) } catch {}
          try { daemon.bus.off('dialectic:stream', onDialecticStream) } catch {}
        })

        return
      }

      // GET /chat/:sessionId/stream  — SSE token stream
      if (parts[0] === 'chat' && parts.length === 3 && parts[2] === 'stream' && req.method === 'GET') {
        const sessionId = parts[1]
        if (!sessionId) return sendJSON(res, 400, { error: 'missing sessionId' })

        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
          'Access-Control-Allow-Origin': '*',
        })
        res.write(': connected\n\n')

        // Subscribe to bus events for this session
        const busHandler = (e: any) => {
          if (e.pluginId !== `session:${sessionId}`) return
          const payload = e.payload as Record<string, unknown>
          if (payload?.type === 'turn:token') {
            try {
              res.write(`data: ${JSON.stringify({ type: 'token', token: payload.token })}\n\n`)
            } catch { /* client disconnected */ }
          } else if (payload?.type === 'turn:done') {
            try {
              res.write(`data: ${JSON.stringify({ type: 'done' })}\n\n`)
            } catch { /* client disconnected */ }
          } else if (payload?.type === 'turn:tool_call') {
            try {
              res.write(`data: ${JSON.stringify({ type: 'tool_call', tool: payload.tool, input: payload.input })}\n\n`)
            } catch { /* client disconnected */ }
          } else if (payload?.type === 'turn:error') {
            try {
              res.write(`data: ${JSON.stringify({ type: 'error', error: payload.error })}\n\n`)
            } catch { /* client disconnected */ }
          }
        }

        daemon.bus.on('worker:message', busHandler)

        // Keep-alive ping every 15s
        const ping = setInterval(() => {
          try { res.write(': ping\n\n') } catch { clearInterval(ping) }
        }, 15_000)
        try { (ping as any).unref?.() } catch {}

        req.on('close', () => {
          clearInterval(ping)
          daemon.bus.off('worker:message', busHandler)
        })

        return
      }

      // POST /chat/:sessionId/send  — send a message, returns { ok, model, durationMs, tokensUsed }
      if (parts[0] === 'chat' && parts.length === 3 && parts[2] === 'send' && req.method === 'POST') {
        const sessionId = parts[1]
        if (!sessionId) return sendJSON(res, 400, { error: 'missing sessionId' })

        if (!daemon.pipeline) return sendJSON(res, 503, { error: 'pipeline not ready' })

        const body = await parseBody(req)
        const content: string = body?.content
        if (!content) return sendJSON(res, 400, { error: 'missing content' })

        try {
          const { randomUUID } = await import('node:crypto')
          const inbound = {
            id: randomUUID(),
            sessionId,
            channelId: 'channel:cli',
            senderId: sessionId,
            content,
            timestamp: new Date(),
          }

          // process asynchronously (pipeline emits events onto bus for SSE clients)
          void daemon.pipeline.process(inbound).then((result: any) => {
            daemon.bus.emit({ type: 'turn:end', sessionId: inbound.sessionId, response: result.response, durationMs: result.durationMs })
          }).catch((err: any) => {
            daemon.logger?.error?.(`[admin-api] pipeline error: ${String(err)}`)
          })

          return sendJSON(res, 200, { ok: true, sessionId })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /chat/:sessionId/cancel — best-effort cancel of in-flight turn
      if (parts[0] === 'chat' && parts.length === 3 && parts[2] === 'cancel' && req.method === 'POST') {
        const sessionId = parts[1]
        if (!sessionId) return sendJSON(res, 400, { error: 'missing sessionId' })
        if (!daemon.pipeline) return sendJSON(res, 503, { error: 'pipeline not ready' })
        try {
          const ok = typeof (daemon.pipeline as any).requestCancel === 'function'
            ? (daemon.pipeline as any).requestCancel(sessionId)
            : false
          if (ok) return sendJSON(res, 200, { ok: true, cancelled: true })
          return sendJSON(res, 404, { ok: false, error: 'no active turn or not cancellable' })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /chat - Simple chat endpoint for provider integration
      if (parts[0] === "chat" && parts.length === 1 && req.method === "POST") {
        const body = await parseBody(req);
        const messages = body?.messages || [];
        const model = body?.model || getModelSpec('main');
        
        try {
          const { randomUUID } = await import("node:crypto");
          const sessionId = "provider-" + randomUUID();
          const content = messages[messages.length - 1]?.content || "";
          
          // Check if V2 is enabled
          const useV2 = (daemon as any).useV2 && (daemon as any).v2
          
          if (useV2) {
            // V2 path: simplified flow
            logger.info(`[admin-api] V2 chat for session ${sessionId}`);
            const startTime = Date.now();
            const result = await (daemon as any).v2.processMessage(
              "channel:cli",
              sessionId,
              content
            );
            const durationMs = Date.now() - startTime;
            
            return sendJSON(res, 200, {
              content: result.response,
              model: "v2",
              tokensUsed: 0,
              durationMs,
              v2: true
            });
          }
          
          // V1 path: traditional pipeline
          if (!daemon.pipeline) return sendJSON(res, 503, { error: "pipeline not ready" });
          
          const inbound = {
            id: randomUUID(),
            sessionId,
            channelId: "channel:cli",
            senderId: sessionId,
            content,
            timestamp: new Date(),
          };
          
          logger.info(`[admin-api] Processing provider chat for session ${sessionId}`);
          
          // Collect response content from bus events
          let responseContent = "";
          let responseModel = model;
          let tokensUsed = 0;
          let durationMs = 0;
          
          const busHandler = (e: any) => {
            if (e.pluginId !== `session:${sessionId}`) return;
            const payload = e.payload as Record<string, unknown>;
            if (payload?.type === "turn:token") {
              responseContent += String(payload.token || "");
            } else if (payload?.type === "turn:done") {
              responseModel = String(payload.model || model);
              tokensUsed = Number(payload.tokensUsed || 0);
              durationMs = Number(payload.durationMs || 0);
            }
          };
          
          daemon.bus.on("worker:message", busHandler);
          
          try {
            await daemon.pipeline.process(inbound);
            // Wait a bit for events to propagate
            await new Promise(resolve => setTimeout(resolve, 500));
          } finally {
            daemon.bus.off("worker:message", busHandler);
          }
          
          return sendJSON(res, 200, {
            content: responseContent,
            model: responseModel,
            tokensUsed,
            durationMs
          });
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) });
        }
      }

      // GET /models — list models exposed by the daemon (for external clients like CassiCore)
      if (req.method === 'GET' && url.pathname === '/models') {
        try {
          // Attempt to derive models from provider instances loaded into the pipeline.
          const providerMap = (daemon.pipeline as any)?.providers ?? new Map();
          const models: any[] = [];

          for (const [provId, prov] of providerMap.entries()) {
            try {
              const provModels = (prov as any)?.models ?? (prov as any)?.modelList ?? undefined;
              if (!provModels || !Array.isArray(provModels)) continue;

              for (const m of provModels) {
                const modelName = typeof m === 'string' ? m : String((m as any).id ?? m);
                const id = modelName.includes('/') ? modelName : `${provId}/${modelName}`;

                // Heuristics for sensible defaults
                let api = 'openai-completions';
                let reasoning = false;
                let input: string[] = ['text'];
                let contextWindow = 131072;
                let maxTokens = 8192;

                if (String(provId).toLowerCase().includes('kimi')) {
                  api = 'anthropic-messages';
                  reasoning = true;
                  input = ['text', 'image'];
                  contextWindow = 262144;
                  maxTokens = 32768;
                } else if (String(provId).toLowerCase().includes('copilot') || String(provId).toLowerCase().includes('github')) {
                  api = 'openai-completions';
                  reasoning = false;
                }

                // Base metadata
                const meta: any = {
                  id,
                  name: typeof m === 'string' ? id : ((m as any).name ?? id),
                  api,
                  reasoning,
                  input,
                  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
                  contextWindow,
                  maxTokens,
                };

                // If provider exposes richer metadata via describeModel/getModelInfo, prefer it
                try {
                  if (typeof (prov as any).describeModel === 'function') {
                    const info = await (prov as any).describeModel(modelName)
                    if (info && typeof info === 'object') {
                      meta.name = info.name ?? meta.name
                      meta.api = info.api ?? meta.api
                      meta.reasoning = info.reasoning ?? meta.reasoning
                      meta.input = info.input ?? meta.input
                      meta.cost = info.cost ?? meta.cost
                      meta.contextWindow = info.contextWindow ?? meta.contextWindow
                      meta.maxTokens = info.maxTokens ?? meta.maxTokens
                    }
                  } else if (typeof (prov as any).getModelInfo === 'function') {
                    const info = (prov as any).getModelInfo(modelName)
                    if (info && typeof info === 'object') {
                      meta.name = info.name ?? meta.name
                      meta.api = info.api ?? meta.api
                      meta.reasoning = info.reasoning ?? meta.reasoning
                      meta.input = info.input ?? meta.input
                      meta.cost = info.cost ?? meta.cost
                      meta.contextWindow = info.contextWindow ?? meta.contextWindow
                      meta.maxTokens = info.maxTokens ?? meta.maxTokens
                    }
                  }
                } catch (err) {
                  // best-effort; swallow provider metadata errors
                }

                models.push(meta);
              }
            } catch { /* best-effort */ }
          }

          // Fallback to a small curated set if none discovered
          if (models.length === 0) {
            models.push(
              { id: 'kimi-coding/k2p5', name: 'Kimi K2.5 (CassiCore)', api: 'anthropic-messages', reasoning: true, input: ['text','image'], cost: { input:0,output:0,cacheRead:0,cacheWrite:0 }, contextWindow: 262144, maxTokens: 32768 },
              { id: 'github-copilot/gpt-5-mini', name: 'GitHub Copilot gpt-5-mini (via CassiCore)', api: 'openai-completions', reasoning: false, input: ['text'], cost: { input:0,output:0,cacheRead:0,cacheWrite:0 }, contextWindow: 131072, maxTokens: 8192 },
              { id: 'openrouter/auto', name: 'OpenRouter (via CassiCore)', api: 'openai-completions', reasoning: false, input: ['text'], cost: { input:0,output:0,cacheRead:0,cacheWrite:0 }, contextWindow: 131072, maxTokens: 8192 },
            );
          }

          return sendJSON(res, 200, { models });
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) });
        }
      }

      // GET /mcp — list configured MCP servers and status
      if (req.method === 'GET' && url.pathname === '/mcp') {
        try {
          // Prefer HealthMonitor's mcp reference (wired in daemon.start)
          const mcpRef = (daemon.healthMonitor as any)?.mcp ?? (daemon.mcpRegistry as any) ?? undefined
          if (!mcpRef || typeof mcpRef.status !== 'function') {
            return sendJSON(res, 200, { servers: [], message: 'No MCP servers configured' })
          }
          const servers = mcpRef.status()
          return sendJSON(res, 200, servers)
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/thinker/feedback — record human feedback on an insight
      if (req.method === 'POST' && url.pathname === '/intelligence/thinker/feedback') {
        try {
          const body = await parseBody(req)
          const insight = body?.insight
          const helpful = body?.helpful
          const usedInResponse = body?.usedInResponse ?? false
          const sessionId = body?.sessionId
          if (!insight || typeof helpful !== 'boolean') return sendJSON(res, 400, { error: 'missing insight or helpful flag' })
          // Emit event on the bus for Thinker to consume
          daemon.bus.emit({ type: 'thinker:feedback', insight, helpful, usedInResponse, sessionId })
          return sendJSON(res, 200, { ok: true })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /tools/execute — execute a registered tool synchronously (admin)
      if (req.method === 'POST' && url.pathname === '/tools/execute') {
        try {
          const body = await parseBody(req)
          const toolName = body?.tool || body?.name
          const input = body?.input || {}
          const sessionId = body?.sessionId || null
          if (!toolName) return sendJSON(res, 400, { error: 'missing tool name (tool)' })
          const exec = (daemon as any).toolExecutor
          if (!exec || typeof exec.execute !== 'function') return sendJSON(res, 503, { error: 'toolExecutor not available' })
          const { randomUUID } = await import('node:crypto')
          const call = { id: randomUUID(), name: toolName, input }
          try {
            const result = await exec.execute(call, sessionId || `admin-${Date.now()}`)
            return sendJSON(res, 200, result)
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /tools/registry — list registered tools (name, description, parameters)
      if (req.method === 'GET' && url.pathname === '/tools/registry') {
        try {
          const toolRegistry = (daemon.pipeline as any)?.toolRegistry ?? (daemon.toolRegistry as any)
          if (!toolRegistry || typeof toolRegistry.list !== 'function') {
            return sendJSON(res, 503, { error: 'tool registry not initialised' })
          }
          const list = toolRegistry.list().map((t: any) => ({ name: t.name, description: t.description, parameters: t.parameters }))
          return sendJSON(res, 200, list)
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }
      // POST /context/assemble — assemble context for a session (CLI integration)
      if (req.method === 'POST' && url.pathname === '/context/assemble') {
        try {
          const body = await parseBody(req)
          const { sessionId, query, include_history, memory_limit, files, extra_context, char_budget } = body || {}
          
          if (!sessionId) return sendJSON(res, 400, { error: 'missing sessionId' })
          
          const ctxObj = await assembleContext(
            {
              memory: daemon.intelligence?.memory,
              sessionManager: daemon.sessions,
              getPipeline: () => daemon.pipeline,
              logger: daemon.logger,
            },
            {
              sessionId,
              query: query || '',
              includeHistory: include_history !== undefined ? include_history : true,
              memoryLimit: memory_limit || 5,
              files: Array.isArray(files) ? files : (files ? [files] : []),
              extra: extra_context || '',
              workingDir: process.cwd(),
              allowedPaths: [],
              charBudget: char_budget || 50000,
            }
          )
          
          return sendJSON(res, 200, {
            sessionId,
            assembled: {
              recentMemories: ctxObj.recentMemories,
              availableTools: ctxObj.availableTools,
              sessionHistory: ctxObj.sessionHistory,
              files: ctxObj.files,
              extraContext: ctxObj.extraContext,
              taskGuide: ctxObj.taskGuide,
              sessionSummary: ctxObj.sessionSummary,
              trimmed: ctxObj.trimmed,
              semanticHits: ctxObj.semanticHits,
            },
            tokensEstimate: JSON.stringify(ctxObj).length / 4,
          })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }
      
      // GET /context/:sessionId — get cached global context for a session
      if (req.method === 'GET' && parts[0] === 'context' && parts.length === 2) {
        try {
          const sessionId = parts[1]
          const cm = (daemon.intelligence as any)?.contextManager
          if (!cm || typeof cm.getEffectiveContext !== 'function') {
            return sendJSON(res, 503, { error: 'context manager not available' })
          }
          const result = await cm.getEffectiveContext(sessionId, { charBudget: 50000 })
          return sendJSON(res, 200, { 
            sessionId, 
            globalContext: result?.globalContext,
            merged: result?.merged?.slice(0, 1000) // Truncated for response size
          })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }
      
      if (parts[0] === "tools" || parts[0] === "fs") {
        const toolsApi = createToolsApi(logger);
        return toolsApi.handler(req, res);
      }
      sendJSON(res, 404, { error: 'not_found' })
    } catch (err) {
      logger.warn(`admin-api error: ${String(err)}`)
      sendJSON(res, 500, { error: String(err) })
    }
  }

  // ---------------------------------------------------------------------------
  // inject.json — file-based IPC for the OpenCode bridge plugin
  //
  // The bridge plugin runs inside OpenCode's embedded Bun runtime which cannot
  // make TCP connections to local services (Bug #5).  Instead of HTTP, we write
  // CassiCore context to a JSON file that the bridge reads with readFileSync().
  // ---------------------------------------------------------------------------

  const cassiDir = path.join(os.homedir(), '.cassicore')
  const injectPath = path.join(cassiDir, 'inject.json')
  const injectTmpPath = path.join(cassiDir, '.inject.tmp.json')

  /**
   * Map MentalModel ConversationPhase → bridge-friendly mode string.
   * The bridge plugin uses these to decide pruning aggressiveness.
   */
  function phaseToMode(phase: string, intentType?: string, topic?: string): 'exploration' | 'planning' | 'execution' | 'debugging' {
    // Check for debugging signals first (intent or topic keywords)
    if (intentType === 'debug' || intentType === 'fix' || intentType === 'troubleshoot') return 'debugging'
    if (topic && /\b(bug|error|fix|debug|crash|fail|broken|issue)\b/i.test(topic)) return 'debugging'

    switch (phase) {
      case 'initial':
      case 'clarifying':
        return 'exploration'
      case 'synthesizing':
        return 'planning'
      case 'executing':
        return 'execution'
      case 'concluding':
        return 'planning'
      default:
        return 'exploration'
    }
  }

  /**
   * Determine pruning aggressiveness based on session characteristics.
   */
  function computePruneAdvice(
    turnCount: number,
    complexity: number,
    mode: string,
    focusTopics: string[],
  ): { aggressiveness: string; staleAfterTurns: number; keepToolOutputs: string[]; focusTopics: string[] } {
    // Tools whose outputs should never be pruned
    const keepToolOutputs = ['skill', 'cassicore_cassi_activity']

    if (turnCount < 5 || complexity < 0.2) {
      return { aggressiveness: 'none', staleAfterTurns: 50, keepToolOutputs, focusTopics }
    }
    if (turnCount < 15 && complexity < 0.6) {
      return { aggressiveness: 'light', staleAfterTurns: 20, keepToolOutputs, focusTopics }
    }
    if (turnCount < 30) {
      return { aggressiveness: 'moderate', staleAfterTurns: 12, keepToolOutputs, focusTopics }
    }
    // Long sessions or high-complexity tasks: prune aggressively
    return { aggressiveness: 'aggressive', staleAfterTurns: 8, keepToolOutputs, focusTopics }
  }

  /**
   * Build a unified focusState for a single session by combining data from
   * MentalModel, SessionDigest, and Thinker strategy.
   */
  function buildFocusState(sessionId: string, opts?: { includeParentFocus?: boolean }): Record<string, any> | null {
    const subconscious = daemon.intelligence?.subconscious
    const digestStore = daemon.sessionDigestStore

    // --- MentalModel ---
    const mm = subconscious?.getMentalModel?.(sessionId)
    const mmState = mm?.state
    const mmContext = mm?.context

    // --- SessionDigest ---
    const digest = digestStore?.get?.(sessionId)

    // If neither source has data, skip this session
    if (!mmState && !digest) return null

    const topic = mmState?.topic || digest?.topic || ''
    const intentType = mmState?.intent?.type || ''
    const phase = mmState?.phase || digest?.phase || 'initial'

    const mode = phaseToMode(phase, intentType, topic)

    // Merge active files from both sources (deduplicated)
    const activeFilesSet = new Set<string>()
    if (mmContext?.loadedFiles) {
      for (const f of mmContext.loadedFiles) {
        if (f?.path) activeFilesSet.add(f.path)
      }
    }
    if (digest?.filesActive) {
      for (const f of digest.filesActive) activeFilesSet.add(f)
    }

    // Focus topics for relevance matching
    const focusTopics: string[] = []
    if (topic) focusTopics.push(topic)
    if (mmState?.intent?.description) focusTopics.push(mmState.intent.description)
    if (digest?.currentTask && digest.currentTask !== topic) focusTopics.push(digest.currentTask)

    const turnCount = digest?.turnCount ?? 0
    const complexity = mmState?.complexity ?? 0.5

    const pruneAdvice = computePruneAdvice(turnCount, complexity, mode, focusTopics)

    // Build compaction context — a human-readable summary for the session.compacting hook
    const compactionParts: string[] = []
    if (topic) compactionParts.push(`Topic: ${topic}`)
    if (digest?.currentTask) compactionParts.push(`Current task: ${digest.currentTask}`)
    if (mode) compactionParts.push(`Mode: ${mode}`)
    if (digest?.decisions?.length) compactionParts.push(`Key decisions: ${digest.decisions.slice(-3).join('; ')}`)
    if (digest?.learnings?.length) compactionParts.push(`Learnings: ${digest.learnings.slice(-3).join('; ')}`)

    const result: Record<string, any> = {
      mode,
      topic,
      intent: mmState?.intent
        ? { type: mmState.intent.type, description: mmState.intent.description, confidence: mmState.intent.confidence }
        : null,
      complexity,
      activeFiles: Array.from(activeFilesSet).slice(0, 20),
      activeSkills: (mmContext?.activeSkills ?? []).slice(0, 5),  // D3: Strip bloat — was 50+ items
      recentActions: digest?.recentActions ?? [],
      turnCount,  // D4: Expose for reinforcement timing
      filesActive: digest?.filesActive ?? [],
      pruneAdvice,
      compactionContext: compactionParts.length > 0 ? compactionParts.join('. ') : null,
    }

    // ── B8: Include parent's focus state for child sessions ──
    if (opts?.includeParentFocus) {
      const hierarchyEntry = sessionHierarchyMap.get(sessionId)
      if (hierarchyEntry?.parentId) {
        // Build parent focus WITHOUT includeParentFocus to avoid recursion
        const parentFocus = buildFocusState(hierarchyEntry.parentId)
        if (parentFocus) {
          result.parentFocus = {
            topic: parentFocus.topic,
            mode: parentFocus.mode,
            intent: parentFocus.intent,
            activeFiles: parentFocus.activeFiles?.slice(0, 10),
            turnCount: parentFocus.turnCount,
          }
        }
      }
    }

    return result
  }

  /**
   * Build a structured context package from the current session state,
   * suitable for prepending to a team goal description during job handoff.
   * Pulls from MentalModel, SessionDigest, and retrieved memory context.
   */
  async function buildHandoffContext(sessionId: string): Promise<string> {
    const parts: string[] = []

    // 1. Focus state (topic, intent, active files, mode)
    const focus = buildFocusState(sessionId)
    if (focus) {
      if (focus.topic) parts.push(`**Topic:** ${focus.topic}`)
      if (focus.intent?.description) parts.push(`**Intent:** ${focus.intent.description}`)
      if (focus.mode) parts.push(`**Working mode:** ${focus.mode}`)
      if (focus.activeFiles?.length > 0) {
        parts.push(`**Active files:** ${focus.activeFiles.slice(0, 15).join(', ')}`)
      }
    }

    // 2. Session digest — decisions, learnings, recent actions
    const digest = daemon.sessionDigestStore?.get?.(sessionId)
    if (digest) {
      if (digest.currentTask) parts.push(`**Current task:** ${digest.currentTask}`)
      if (digest.decisions?.length > 0) {
        parts.push(`**Key decisions so far:**\n${digest.decisions.slice(-5).map((d: string) => `- ${d}`).join('\n')}`)
      }
      if (digest.learnings?.length > 0) {
        parts.push(`**Learnings:**\n${digest.learnings.slice(-5).map((l: string) => `- ${l}`).join('\n')}`)
      }
      if (digest.filesActive?.length > 0) {
        parts.push(`**Files being worked on:** ${digest.filesActive.slice(0, 15).join(', ')}`)
      }
    }

    // 3. Retrieved memory context (proactive search based on topic/intent)
    const mem = daemon.intelligence?.memory
    if (mem?.search) {
      try {
        const searchTerms = [focus?.topic, focus?.intent?.description, digest?.currentTask].filter(Boolean)
        const seen = new Set<string>()
        const memResults: string[] = []
        for (const term of searchTerms.slice(0, 2)) {
          const results = await mem.search(term!, 3) as any[]
          for (const r of results) {
            const key = r.key || r.content?.slice(0, 50)
            if (key && !seen.has(key)) {
              seen.add(key)
              const snippet = typeof r.content === 'string' ? r.content.slice(0, 200) : String(r.content).slice(0, 200)
              memResults.push(`- ${snippet}`)
            }
          }
        }
        if (memResults.length > 0) {
          parts.push(`**Relevant memory context:**\n${memResults.slice(0, 5).join('\n')}`)
        }
      } catch {}
    }

    if (parts.length === 0) return ''
    return `## Session Context (auto-packaged from handoff)\n\n${parts.join('\n\n')}\n\n---\n\n`
  }

  /**
   * Compute a complexity score and handoff suggestion for a session.
   * Returns null if no suggestion is warranted.
   */
  function computeHandoffSuggestion(sessionId: string): {
    suggested: boolean
    reason: string
    proposedGoal: string
    estimatedComplexity: 'low' | 'moderate' | 'high' | 'very-high'
  } | null {
    const digest = daemon.sessionDigestStore?.get?.(sessionId)
    const subconscious = daemon.intelligence?.subconscious
    const mm = subconscious?.getMentalModel?.(sessionId)
    const mmState = mm?.state

    if (!digest && !mmState) return null

    const turnCount = digest?.turnCount ?? 0
    const complexity = mmState?.complexity ?? 0.5
    const fileCount = digest?.filesActive?.length ?? 0
    const topic = mmState?.topic || digest?.topic || ''
    const intent = mmState?.intent?.description || digest?.currentTask || ''

    // Don't suggest handoff too early — wait for enough signal
    if (turnCount < 3) return null

    // Score components
    let score = 0
    const reasons: string[] = []

    // High complexity from subconscious model
    if (complexity > 0.7) {
      score += 0.3
      reasons.push('high cognitive complexity detected')
    }

    // Many active files suggests cross-cutting work
    if (fileCount >= 5) {
      score += 0.2
      reasons.push(`${fileCount} files actively involved`)
    }
    if (fileCount >= 10) {
      score += 0.15
    }

    // Long-running session without completion
    if (turnCount > 15) {
      score += 0.15
      reasons.push(`${turnCount} turns without completion`)
    }
    if (turnCount > 30) {
      score += 0.15
    }

    // Intent keywords that suggest multi-step work
    const handoffKeywords = /\b(implement|refactor|migrate|redesign|overhaul|rewrite|add feature|build out|set up|create.*system|across.*files|multiple.*components)\b/i
    if (handoffKeywords.test(intent) || handoffKeywords.test(topic)) {
      score += 0.25
      reasons.push('task language suggests multi-step work')
    }

    // Check optimizer session health for stuck/loop signals
    const optimizer = daemon.intelligence?.optimizer
    if (optimizer?.scoreSession) {
      try {
        const health = optimizer.scoreSession(sessionId)
        if (health?.stuckScore > 0) {
          score += 0.3
          reasons.push('stuck pattern detected')
        }
        if (health?.loopScore > 0.4) {
          score += 0.2
          reasons.push('potential loop detected')
        }
      } catch {}
    }

    // Determine complexity tier
    let estimatedComplexity: 'low' | 'moderate' | 'high' | 'very-high' = 'low'
    if (score >= 0.7) estimatedComplexity = 'very-high'
    else if (score >= 0.5) estimatedComplexity = 'high'
    else if (score >= 0.3) estimatedComplexity = 'moderate'

    // Only suggest handoff above threshold
    if (score < 0.5) return null

    // Build proposed goal from session context
    const goalParts: string[] = []
    if (intent) goalParts.push(intent)
    else if (topic) goalParts.push(topic)
    else goalParts.push('Continue current task')
    if (digest?.currentTask && digest.currentTask !== intent) {
      goalParts.push(`(${digest.currentTask})`)
    }

    return {
      suggested: true,
      reason: reasons.join('; '),
      proposedGoal: goalParts.join(' '),
      estimatedComplexity,
    }
  }

  /**
   * T3: Compute delegation requests for a session.
   * Unlike handoff suggestions (which are advisory), delegation requests are
   * actionable — the plugin will auto-execute them by spawning subagents.
   *
   * Delegation triggers:
   * 1. Session is stuck/looping and could benefit from a fresh perspective
   * 2. Session complexity is very high with decomposable sub-goals
   * 3. Thinker has generated a spawn_subagent opportunity
   */
  function computeDelegationRequests(sessionId: string): DelegationRequest[] {
    const requests: DelegationRequest[] = []
    const now = Date.now()

    // Don't generate new requests if we already have pending ones for this session
    const pendingForSession = [...delegationTracker.values()].filter(
      t => t.request.sessionId === sessionId && (t.status === 'pending' || t.status === 'executing')
    )
    if (pendingForSession.length >= 2) return requests

    const digest = daemon.sessionDigestStore?.get?.(sessionId)
    const subconscious = daemon.intelligence?.subconscious
    const mm = subconscious?.getMentalModel?.(sessionId)
    const mmState = mm?.state

    if (!digest && !mmState) return requests

    const turnCount = digest?.turnCount ?? 0
    const complexity = mmState?.complexity ?? 0.5
    const intent = mmState?.intent?.description || digest?.currentTask || ''
    const topic = mmState?.topic || digest?.topic || ''

    // Don't delegate too early
    if (turnCount < 5) return requests

    // Check optimizer health signals
    const optimizer = daemon.intelligence?.optimizer
    let stuckScore = 0
    let loopScore = 0
    if (optimizer?.scoreSession) {
      try {
        const health = optimizer.scoreSession(sessionId)
        stuckScore = health?.stuckScore ?? 0
        loopScore = health?.loopScore ?? 0
      } catch {}
    }

    // ── Trigger 1: Session is stuck with high loop score ──
    // If the session is looping, delegate the current task to a fresh subagent
    if (loopScore > 0.6 && intent) {
      const delegationId = `del_${now}_stuck_${sessionId.replace(/[^a-zA-Z0-9]/g, '').slice(-8)}`

      // Don't duplicate if we already have a stuck delegation for this session
      const alreadyHasStuck = [...delegationTracker.values()].some(
        t => t.request.sessionId === sessionId && t.request.reason.includes('stuck/looping') && t.status !== 'completed' && t.status !== 'failed' && t.status !== 'expired'
      )
      if (!alreadyHasStuck) {
        requests.push({
          id: delegationId,
          sessionId,
          goal: `The parent session is stuck in a loop. Take a fresh approach to: ${intent}`,
          agentType: 'code',
          priority: 'high',
          reason: `Session stuck/looping (loopScore=${loopScore.toFixed(2)}, stuckScore=${stuckScore.toFixed(2)})`,
          estimatedComplexity: 'high',
          contextPreamble: '', // Will be filled below
          createdAt: now,
          expiresAt: now + DELEGATION_EXPIRY_MS,
        })
      }
    }

    // ── Trigger 2: Very high complexity with decomposable work ──
    // If complexity is extreme and there are multiple files, suggest parallel work
    if (complexity > 0.85 && turnCount > 10) {
      const fileCount = digest?.filesActive?.length ?? 0
      if (fileCount >= 8) {
        const delegationId = `del_${now}_complex_${sessionId.replace(/[^a-zA-Z0-9]/g, '').slice(-8)}`

        const alreadyHasComplex = [...delegationTracker.values()].some(
          t => t.request.sessionId === sessionId && t.request.reason.includes('High complexity') && t.status !== 'completed' && t.status !== 'failed' && t.status !== 'expired'
        )
        if (!alreadyHasComplex) {
          requests.push({
            id: delegationId,
            sessionId,
            goal: intent || topic || 'Continue current multi-file task',
            agentType: 'code',
            priority: 'medium',
            reason: `High complexity (${complexity.toFixed(2)}) with ${fileCount} active files`,
            estimatedComplexity: 'very-high',
            contextPreamble: '',
            createdAt: now,
            expiresAt: now + DELEGATION_EXPIRY_MS,
          })
        }
      }
    }

    // ── Trigger 3: Thinker ponder insights requesting delegation ──
    // Check if the Thinker has recently generated insights that recommend spawning subagents
    const thinker = daemon.intelligence?.thinker as any
    if (thinker?.getRecentInsights) {
      try {
        const insights = thinker.getRecentInsights?.(5) as any[] ?? []
        for (const insight of insights) {
          if (insight.trigger === 'subconscious_opportunity_subagent' && insight.timestamp > now - 30000) {
            const delegationId = `del_${now}_thinker_${sessionId.replace(/[^a-zA-Z0-9]/g, '').slice(-8)}`

            // Don't duplicate thinker delegations
            const alreadyHasThinker = [...delegationTracker.values()].some(
              t => t.request.sessionId === sessionId && t.request.reason.includes('Thinker') && now - t.request.createdAt < 30000
            )
            if (!alreadyHasThinker) {
              requests.push({
                id: delegationId,
                sessionId,
                goal: insight.insight || intent || 'Complex task requiring subagent assistance',
                agentType: 'code',
                priority: 'medium',
                reason: 'Thinker recommended subagent delegation',
                estimatedComplexity: complexity > 0.7 ? 'high' : 'moderate',
                contextPreamble: '',
                createdAt: now,
                expiresAt: now + DELEGATION_EXPIRY_MS,
              })
            }
          }
        }
      } catch {}
    }

    // Fill in context preamble for each request
    for (const req of requests) {
      try {
        // packageSessionContext is async, but we need sync here.
        // Use a minimal sync preamble instead.
        const parts: string[] = []
        if (topic) parts.push(`Topic: ${topic}`)
        if (intent) parts.push(`Current task: ${intent}`)
        if (digest?.filesActive?.length) {
          parts.push(`Active files: ${digest.filesActive.slice(0, 10).join(', ')}`)
        }
        if (digest?.currentTask) parts.push(`Task context: ${digest.currentTask}`)
        req.contextPreamble = parts.join('\n')
      } catch {}
    }

    return requests
  }

  /**
   * Build the full context payload for the bridge plugin.
   * This was formerly embedded in writeInjectFile() — now extracted so the
   * GET /context endpoint can serve it on-demand via Unix socket.
   */
  async function buildInjectPayload(): Promise<Record<string, unknown>> {
    const mem = daemon.intelligence?.memory
    const subconscious = daemon.intelligence?.subconscious

    // --- Thinker insight (latest from history) ---
    let insight: string | null = null
    if (mem) {
      try {
        const history = await mem.kv_get('thinker:insight-history') as any[] | undefined
        if (history && history.length > 0) {
          insight = history[history.length - 1]?.insight ?? null
        }
      } catch {}
    }

    // --- Subconscious learnings (top 10 by occurrence) ---
    let learnings: Array<{ clusterLabel: string; summary: string; occurrences: number }> = []
    if (mem) {
      try {
        const raw = await mem.kv_get('subconscious:learnings') as any[] | undefined
        if (raw) {
          learnings = raw
            .sort((a: any, b: any) => (b.occurrences || 0) - (a.occurrences || 0))
            .slice(0, 10)
            .map((l: any) => ({
              clusterLabel: l.clusterLabel || '',
              summary: l.summary || '',
              occurrences: l.occurrences || 0,
            }))
        }
      } catch {}
    }

    // --- Per-session retrieved context (non-consuming peek) ---
    const sessions: Record<string, { items: any[] }> = {}
    if (subconscious?.getSessionIds && subconscious?.peekRetrievedContext) {
      const sessionIds = subconscious.getSessionIds()
      for (const sid of sessionIds) {
        try {
          const items = subconscious.peekRetrievedContext(sid)
          if (items && items.length > 0) {
            sessions[sid] = {
              items: items.map((item: any) => ({
                source: item.source ?? 'memory',
                content: item.content ?? '',
                relevance: item.relevance ?? 0,
                query: item.query ?? '',
              })),
            }
          }
        } catch {}
      }
    }

    // --- Per-session focusState (unified from MentalModel + SessionDigest + Thinker) ---
    const focusStates: Record<string, any> = {}

    // Collect all known session IDs from both sources
    const allSessionIds = new Set<string>()
    if (subconscious?.getSessionIds) {
      for (const sid of subconscious.getSessionIds()) allSessionIds.add(sid)
    }
    if (daemon.sessionDigestStore) {
      for (const d of daemon.sessionDigestStore.all()) allSessionIds.add(d.sessionId)
    }

    for (const sid of allSessionIds) {
      const focus = buildFocusState(sid, { includeParentFocus: true })
      if (focus) focusStates[sid] = focus
    }

    // --- D1: Per-session optimizer health (loopScore, stuckScore, etc.) ---
    const sessionHealth: Record<string, any> = {}
    const optimizer = daemon.intelligence?.optimizer
    if (optimizer?.scoreSession) {
      for (const sid of allSessionIds) {
        try {
          const health = await optimizer.scoreSession(sid)
          if (health) {
            sessionHealth[sid] = {
              loopScore: health.loopScore,
              stuckScore: health.stuckScore,
              tokenVelocity: health.tokenVelocity,
              estimatedTokens: health.estimatedTokens,
              interventionCount: health.interventionCount,
              lastAction: health.lastAction ?? null,
            }
          }
        } catch {}
      }
    }

    // --- D2: Active anomalies from subconscious ---
    let anomalies: any[] = []
    if (mem) {
      try {
        const raw = await mem.kv_get('subconscious:anomalies') as any[] | undefined
        if (raw) {
          anomalies = raw
            .filter((a: any) => !a.acknowledged)
            .slice(0, 10)
            .map((a: any) => ({
              id: a.id || a.summary,
              type: a.type || 'unknown',
              summary: a.summary || '',
              severity: a.severity || 'low',
              detectedAt: a.detectedAt || a.timestamp,
              sessionId: a.sessionId || null,
            }))
        }
      } catch {}
    }

    // --- D5: Proactive memory search for OpenCode sessions ---
    // peekRetrievedContext() is empty for oc:* sessions because they don't go through
    // CassiCore's turn pipeline. Run memory searches based on focus topic+intent instead.
    if (mem?.search) {
      for (const sid of allSessionIds) {
        if (!sid.startsWith('oc:') || sessions[sid]) continue  // Only fill missing oc: sessions
        const focus = focusStates[sid]
        if (!focus?.topic && !focus?.intent?.description) continue

        try {
          const queries: string[] = []
          if (focus.topic) queries.push(focus.topic)
          if (focus.intent?.description && focus.intent.description !== focus.topic) {
            queries.push(focus.intent.description)
          }

          const allItems: any[] = []
          for (const q of queries.slice(0, 2)) {  // Max 2 queries per session
            const results = await mem.search(q, { limit: 3 })
            for (const r of results) {
              if (r.score && r.score < 0.3) continue  // Skip low-relevance results
              allItems.push({
                source: 'memory',
                content: typeof r.content === 'string' ? r.content.slice(0, 500) : String(r.content || '').slice(0, 500),
                relevance: r.score ?? 0,
                query: q,
              })
            }
          }

          if (allItems.length > 0) {
            // Deduplicate by content prefix
            const seen = new Set<string>()
            const deduped = allItems.filter(item => {
              const key = item.content.slice(0, 100)
              if (seen.has(key)) return false
              seen.add(key)
              return true
            }).slice(0, 5)  // Max 5 items per session

            sessions[sid] = { items: deduped }
          }
        } catch {}
      }
    }

    // ── B7: Serialize session hierarchy for plugin consumption ──
    const sessionHierarchy = serializeSessionHierarchy()

    // ── C1 + T1-3: Active teams, pending checkpoints, and recently completed teams ──
    let teams: { active: any[]; pendingCheckpoints: any[]; recentlyCompleted?: any[] } | undefined
    const to = daemon.intelligence?.teamOrchestrator as any
    if (to?.listActiveTeams) {
      try {
        const activeTeams = to.listActiveTeams() as any[]
        const pendingCheckpoints = (to.listPendingCheckpoints?.() ?? []) as any[]

        // T1-3: Also include recently completed teams (last 30 min) for result delivery
        let recentlyCompleted: any[] = []
        if (to.listAllTeams) {
          const allTeams = to.listAllTeams() as any[]
          const thirtyMinAgo = Date.now() - 30 * 60_000
          recentlyCompleted = allTeams
            .filter((t: any) => (t.status === 'completed' || t.status === 'failed') && (t.completedAt || 0) > thirtyMinAgo)
            .map((t: any) => {
              // Collect completed goal summaries from the goal tree
              let completedGoals: Array<{ title: string; summary: string }> = []
              let filesModified: string[] = []
              try {
                const status = to.getTeamStatus?.(t.id)
                if (status?.goals) {
                  completedGoals = (status.goals as any[])
                    .filter((g: any) => g.status === 'completed')
                    .map((g: any) => ({ title: g.title || '', summary: g.result?.slice(0, 300) || '' }))
                    .slice(0, 20)
                }
              } catch {}

              // Collect modified files from agent session digests
              if (t.agentIds && daemon.sessionDigestStore) {
                const filesSet = new Set<string>()
                for (const agentId of t.agentIds) {
                  try {
                    // Agent sessions are stored with the agent ID as session key
                    const agentDigest = daemon.sessionDigestStore.get(agentId)
                    if (agentDigest?.filesActive) {
                      for (const f of agentDigest.filesActive) filesSet.add(f)
                    }
                  } catch {}
                }
                filesModified = Array.from(filesSet).slice(0, 30)
              }

              return {
                id: t.id,
                name: t.config?.name ?? null,
                status: t.status,
                goal: t.config?.goal?.slice(0, 500) ?? '',
                finalResult: t.finalResult?.slice(0, 1000) ?? null,
                external: !!t.external,
                externalSessionId: t.externalSessionId ?? null,
                externalParentSessionId: t.externalParentSessionId ?? null,
                completedGoals,
                filesModified,
                completedAt: t.completedAt,
                budget: {
                  tokensUsed: t.budget?.tokensUsed ?? 0,
                  maxTokens: t.budget?.maxTokens ?? 0,
                  agentsSpawned: t.budget?.agentsSpawned ?? 0,
                },
              }
            })
            .slice(0, 5)  // Max 5 recently completed teams
        }

        if (activeTeams.length > 0 || pendingCheckpoints.length > 0 || recentlyCompleted.length > 0) {
          teams = {
            active: activeTeams.map((t: any) => {
              // Get rich status if available (includes progress + active agents)
              let progress: any = null
              let activeAgents: any[] = []
              let goalTreeStr: string | null = null
              try {
                const status = to.getTeamStatus?.(t.id)
                if (status) {
                  progress = status.progress ?? null
                  activeAgents = (status.activeAgents ?? []).slice(0, 10)
                  goalTreeStr = status.goalTree ?? null
                }
              } catch {}

              return {
                id: t.id,
                name: t.config?.name ?? null,
                status: t.status,
                goal: t.config?.goal ?? '',
                checkpointMode: t.config?.checkpoint?.mode ?? 'none',
                external: !!t.external,
                externalSessionId: t.externalSessionId ?? null,
                externalParentSessionId: t.externalParentSessionId ?? null,
                budget: {
                  tokensUsed: t.budget?.tokensUsed ?? 0,
                  maxTokens: t.budget?.maxTokens ?? 0,
                  agentsSpawned: t.budget?.agentsSpawned ?? 0,
                  maxAgents: t.budget?.maxAgents ?? 0,
                  elapsedMs: t.budget?.startedAt ? Date.now() - t.budget.startedAt : 0,
                  maxDurationMs: t.budget?.maxDurationMs ?? 0,
                },
                agentCount: t.agentIds?.length ?? 0,
                progress: progress ? {
                  completed: progress.completed ?? 0,
                  total: progress.total ?? 0,
                  inProgress: progress.inProgress ?? 0,
                  blocked: progress.blocked ?? 0,
                } : null,
                activeAgents: activeAgents.map((a: any) => ({
                  agentId: a.agentId,
                  goalTitle: a.goalTitle,
                })),
                goalTree: goalTreeStr,
                createdAt: t.createdAt,
              }
            }),
            pendingCheckpoints: pendingCheckpoints.map((cp: any) => ({
              id: cp.id,
              teamId: cp.teamId,
              trigger: cp.trigger,
              status: cp.status,
              progressSummary: cp.progressSummary ?? '',
              completedGoals: cp.completedGoals ?? 0,
              totalGoals: cp.totalGoals ?? 0,
              budget: cp.budgetSnapshot ?? null,
              createdAt: cp.createdAt,
            })),
            ...(recentlyCompleted.length > 0 ? { recentlyCompleted } : {}),
          }
        }
      } catch {}
    }

    // ── F7: Sibling session learnings for cross-session knowledge ──
    // Collects per-session learnings and decisions from SessionDigestStore
    // so the plugin can inject discoveries from other sessions.
    let siblingLearnings: Record<string, {
      topic: string
      learnings: string[]
      decisions: string[]
      filesActive: string[]
      lastActiveAt: number
      turnCount: number
    }> | undefined
    if (daemon.sessionDigestStore) {
      try {
        const allDigests = daemon.sessionDigestStore.all()
        // Only include active sessions with learnings or decisions
        const withContent = allDigests.filter(
          (d: any) => d.isActive && (d.learnings.length > 0 || d.decisions.length > 0)
        )
        if (withContent.length > 0) {
          siblingLearnings = {}
          for (const d of withContent) {
            siblingLearnings[d.sessionId] = {
              topic: d.topic || '',
              learnings: d.learnings.slice(-5),   // Most recent 5 per session
              decisions: d.decisions.slice(-5),
              filesActive: d.filesActive.slice(0, 5),
              lastActiveAt: d.lastActiveAt,
              turnCount: d.turnCount,
            }
          }
        }
      } catch {}
    }

    // ── F7: Cross-session patterns from correlator ──
    // High-confidence patterns discovered across sessions.
    let crossSessionPatterns: Array<{
      category: string
      description: string
      confidence: number
      sessionCount: number
    }> | undefined
    if (daemon.crossSessionCorrelator) {
      try {
        const patterns = daemon.crossSessionCorrelator.getPatterns({
          minConfidence: 0.5,
          limit: 10,
        })
        if (patterns.length > 0) {
          crossSessionPatterns = patterns.map((p: any) => ({
            category: p.category,
            description: p.description,
            confidence: p.confidence,
            sessionCount: p.sessionCount,
          }))
        }
      } catch {}
    }

    // ── F8: Latest dialectic signal per session ──
    // The most recent dialectic synthesis result (signal, tension, confidence)
    // for each active session, so the plugin can inject dialectic insights.
    let dialecticLatest: Record<string, {
      hasSignal: boolean
      signal?: {
        type: string
        content: string
        confidence: number
        urgency: string
      }
      yangBranchCount: number
      yinCritiqueCount: number
      dialecticTension: number
      synthesisConfidence: number
      timestamp: number
    }> | undefined
    const dialectic = daemon.intelligence?.dialectic as any
    if (dialectic?.getRecent) {
      try {
        const dialecticResults: Record<string, any> = {}
        for (const sid of allSessionIds) {
          const recent = await dialectic.getRecent(sid, 1) as any[]
          if (recent.length === 0) continue
          const r = recent[0]
          const synthesis = r.serenity?.synthesis
          if (!synthesis) continue

          dialecticResults[sid] = {
            hasSignal: synthesis.hasSignal ?? false,
            ...(synthesis.hasSignal && synthesis.signal ? {
              signal: {
                type: synthesis.signal.type,
                content: synthesis.signal.content,
                confidence: synthesis.signal.confidence,
                urgency: synthesis.signal.urgency ?? 'background',
              },
            } : {}),
            yangBranchCount: r.yang?.branches?.length ?? 0,
            yinCritiqueCount: r.yin?.baselineBranches?.length ?? r.yin?.critiques?.length ?? 0,
            dialecticTension: r.quality?.dialecticTension ?? r.serenity?.meta?.dialecticQuality ?? 0,
            synthesisConfidence: r.quality?.synthesisConfidence ?? 0,
            timestamp: r.timestamp,
          }
        }
        if (Object.keys(dialecticResults).length > 0) {
          dialecticLatest = dialecticResults
        }
      } catch {}
    }

    // ── T1-4: Handoff suggestions — per-session complexity detection ──
    // Analyzes each active session and suggests team handoff when complexity is high.
    let handoffSuggestions: Record<string, {
      suggested: boolean
      reason: string
      proposedGoal: string
      estimatedComplexity: 'low' | 'moderate' | 'high' | 'very-high'
    }> | undefined
    try {
      const suggestions: Record<string, any> = {}
      for (const sid of allSessionIds) {
        // Only compute for OpenCode sessions (oc: prefix)
        if (!sid.startsWith('oc:')) continue
        const suggestion = computeHandoffSuggestion(sid)
        if (suggestion) suggestions[sid] = suggestion
      }
      if (Object.keys(suggestions).length > 0) {
        handoffSuggestions = suggestions
      }
    } catch {}

    // ── T3: Delegation requests — auto-spawn subagents ──
    let delegationRequests: DelegationRequest[] | undefined
    try {
      const now = Date.now()

      // Expire old delegation requests
      for (const [id, tracking] of delegationTracker) {
        if (tracking.status === 'pending' && now > tracking.request.expiresAt) {
          tracking.status = 'expired'
          logger.debug('[admin-api] Delegation request expired', { id })
        }
        // Clean up old completed/expired/failed entries (older than 5 minutes)
        if (['completed', 'failed', 'expired'].includes(tracking.status) && now - tracking.request.createdAt > 5 * 60 * 1000) {
          delegationTracker.delete(id)
        }
      }

      // Only compute new delegations if enough time has passed
      if (now - lastDelegationComputeTime >= DELEGATION_COMPUTE_INTERVAL_MS) {
        lastDelegationComputeTime = now

        // Count pending delegations across all sessions
        const totalPending = [...delegationTracker.values()].filter(t => t.status === 'pending').length

        if (totalPending < DELEGATION_MAX_PENDING) {
          for (const sid of allSessionIds) {
            if (!sid.startsWith('oc:')) continue
            const newRequests = computeDelegationRequests(sid)
            for (const req of newRequests) {
              if (totalPending + delegationTracker.size >= DELEGATION_MAX_PENDING + 5) break // Hard cap
              delegationTracker.set(req.id, { request: req, status: 'pending' })
              logger.info('[admin-api] New delegation request', {
                id: req.id,
                sessionId: req.sessionId,
                reason: req.reason,
                priority: req.priority,
              })
            }
          }
        }
      }

      // Collect pending requests to serve to plugin
      const pending = [...delegationTracker.values()]
        .filter(t => t.status === 'pending')
        .map(t => t.request)

      if (pending.length > 0) {
        delegationRequests = pending
      }
    } catch {}

    return {
      updatedAt: Date.now(),
      insight,
      learnings,
      sessions,
      focusStates,
      sessionHealth,  // D1
      anomalies,      // D2
      ...(Object.keys(sessionHierarchy).length > 0 ? { sessionHierarchy } : {}),  // B7
      ...(teams ? { teams } : {}),  // C1
      ...(siblingLearnings ? { siblingLearnings } : {}),  // F7
      ...(crossSessionPatterns ? { crossSessionPatterns } : {}),  // F7
      ...(dialecticLatest ? { dialecticLatest } : {}),  // F8
      ...(handoffSuggestions ? { handoffSuggestions } : {}),  // T1-4
      ...(delegationRequests ? { delegationRequests } : {}),  // T3
    }
  }

  /**
   * Legacy inject.json writer — kept for backward compatibility / debugging.
   * The primary data path is now GET /context via Unix socket.
   */
  async function writeInjectFile(): Promise<void> {
    try {
      const payload = await buildInjectPayload()
      // Atomic write: temp file → rename (prevents partial reads)
      fs.writeFileSync(injectTmpPath, JSON.stringify(payload), 'utf8')
      fs.renameSync(injectTmpPath, injectPath)
    } catch (err) {
      logger.debug('[admin-api] inject.json write failed', { error: String(err) })
    }
  }

  // Separate servers for Unix socket and TCP
  let unixServer: http.Server | null = null
  let tcpServer: http.Server | null = null

  return {
    async start() {
      if (unixServer || tcpServer) return { tcpPort: currentTcpPort, unixPath }

      // Remove existing socket if present
      try {
        if (fs.existsSync(unixPath)) fs.unlinkSync(unixPath)
      } catch {}

      // Start Unix socket server
      unixServer = http.createServer(handler)
      unixServer.on('upgrade', (req, socket, head) => { void handleWebSocketUpgrade(req, socket, head) })
      unixServer.on('error', (e) => logger.warn(`[admin-api] unix server error: ${String(e)}`))
      await new Promise<void>((resolve, reject) => {
        unixServer!.listen(unixPath, () => {
          try { fs.chmodSync(unixPath, 0o660) } catch {}
          logger.info(`[admin-api] listening on unix:${unixPath}`)
          resolve()
        })
        unixServer!.on('error', reject)
      })

      // Start TCP server (separate instance) — attempt base port then fallback
      let boundPort: number | null = null
      for (let i = 0; i < 10; i++) {
        const tryPort = baseTcpPort + i
        const s = http.createServer(handler)
        s.on('upgrade', (req, socket, head) => { void handleWebSocketUpgrade(req, socket, head) })

        try {
          await new Promise<void>((resolve, reject) => {
            s.listen(tryPort, tcpHost, () => resolve())
            s.once('error', (err) => reject(err))
          })
          tcpServer = s
          boundPort = tryPort
          currentTcpPort = tryPort
          logger.info(`[admin-api] listening on http://${tcpHost}:${tryPort}`)
          break
        } catch (err: any) {
          if (err && err.code === 'EADDRINUSE') {
            logger.warn(`[admin-api] port ${tryPort} in use; trying ${tryPort + 1}`)
            try { s.close?.(); } catch {}
            continue
          }
          try { s.close?.(); } catch {}
          throw err
        }
      }

      if (!boundPort) {
        logger.warn('[admin-api] failed to bind TCP admin port (no available port found)')
      }

      // inject.json periodic writer DISABLED — replaced by GET /context via Unix socket.
      // The bridge plugin now fetches context on-demand from admin.sock instead of
      // polling a file. writeInjectFile() is retained for manual debugging:
      //   curl --unix-socket ~/.cassicore/admin.sock http://localhost/context | jq .
      // To re-enable file-based IPC temporarily, uncomment the lines below:
      // injectTimer = setInterval(() => { writeInjectFile().catch(() => {}) }, 5000)
      // writeInjectFile().catch(() => {})
      logger.info('[admin-api] context available via GET /context on unix socket (inject.json writer disabled)')

      return { tcpPort: boundPort, unixPath }
    },
    async stop() {
      if (unixServer) {
        await new Promise<void>((resolve) => unixServer!.close(() => resolve()))
        unixServer = null
      }
      if (tcpServer) {
        await new Promise<void>((resolve) => tcpServer!.close(() => resolve()))
        tcpServer = null
      }
      try { if (fs.existsSync(unixPath)) fs.unlinkSync(unixPath) } catch {}
      logger.info('[admin-api] stopped')
    }
  }
}
