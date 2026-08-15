import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'

import type { IOrchestrationBus } from './orchestration-bus.js'
import type { ILogger , IEventBus } from '@cassicore/foundation'
import { getCassiCoreHome } from '@cassicore/foundation'

const SOCKET_PATH = path.join(getCassiCoreHome(), 'session-bridge.sock')

// Message types for bidirectional communication
interface InsightMessage {
  method: 'insight:inject'
  params: {
    sessionId: string
    text: string
    priority?: 'high' | 'normal' | 'low'
  }
}

interface SuggestActionMessage {
  method: 'suggest:action'
  params: {
    sessionId?: string
    action: string
    reason: string
  }
}

interface StatusReportMessage {
  method: 'status:report'
  params: {
    activeAgents: number
    queueDepth: number
    insightsPending?: number
  }
}

interface PollRequest {
  method: 'poll'
  params: {
    sessionId?: string
    since?: number  // timestamp
    maxResults?: number
  }
}

type OutboundMessage = InsightMessage | SuggestActionMessage | StatusReportMessage

// Queued message with metadata
interface QueuedMessage {
  id: string
  timestamp: number
  message: OutboundMessage
  targetSession?: string
}

export interface ISessionBridge {
  emitInsight(sessionId: string, text: string, priority?: 'high' | 'normal' | 'low'): void
  suggestAction(action: string, reason: string, sessionId?: string): void
  broadcastStatus(): void
  destroy(): void
}

/**
 * @dep callers: computeActiveAgents.test.ts (core/tests/computeActiveAgents.test.ts), computeActiveAgents.test.ts (tests/core/computeActiveAgents.test.ts), broadcastStatus (core/session-bridge.ts)
 * @dep calls: getStats, match, getSummary
 * @dep module: Cluster_291
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

export async function computeActiveAgents(orchestration: any, logger?: ILogger): Promise<number> {
  // Feature-detect getStats (sync or async), normalize common key names, fall back to parsing getSummary()
  try {
    if (orchestration && typeof orchestration.getStats === 'function') {
      const stats = orchestration.getStats()
      const resolved = (stats && typeof stats.then === 'function') ? await stats : stats

      if (resolved && typeof resolved === 'object') {
        // Common candidate keys
        const keys = ['running', 'active', 'activeAgents', 'runningCount', 'agentsRunning']
        for (const k of keys) {
          const v = resolved[k]
          if (typeof v === 'number' && Number.isFinite(v) && v >= 0) return Math.max(0, Math.floor(v))
        }
        // As a last resort, try to find any numeric value in the object
        for (const key of Object.keys(resolved)) {
          const v = (resolved as any)[key]
          if (typeof v === 'number' && Number.isFinite(v) && v >= 0) return Math.max(0, Math.floor(v))
        }
      }
    }

    // Fallback to parsing summary string
    if (orchestration && typeof orchestration.getSummary === 'function') {
      const summary = orchestration.getSummary()
      if (typeof summary === 'string') {
        const match = summary.match(/(\d+)\s+running/) || summary.match(/(\d+)\s+active/)
        if (match) {
          const n = parseInt(match[1], 10)
          if (!Number.isNaN(n) && n >= 0) return n
        }
        // Log that we fell back but couldn't parse
        logger?.debug?.('computeActiveAgents: getSummary present but did not match running/active pattern')
      }
    }
  } catch (err) {
    logger?.warn?.(`computeActiveAgents: error while computing stats: ${(err && (err as Error).message) || String(err)}`)
  }

  return 0
}

export function createSessionBridge(
  orchestration: IOrchestrationBus,
  logger: ILogger,
  eventBus?: IEventBus
): ISessionBridge {
  // ensure directory
  const dir = path.dirname(SOCKET_PATH)
  try { fs.mkdirSync(dir, { recursive: true }) } catch {}
  // remove stale socket
  try { if (fs.existsSync(SOCKET_PATH)) fs.unlinkSync(SOCKET_PATH) } catch (err) { /* stale socket cleanup failure is safe to ignore */ }

  // Message queue for connected clients and poll-based retrieval
  const messageQueue: QueuedMessage[] = []
  const MAX_QUEUE_SIZE = 100
  const clients = new Set<net.Socket>()
  const unsubscribers: Array<() => void> = []

  const server = net.createServer((socket) => {
    clients.add(socket)
    logger.debug(`client connected, total: ${clients.size}`)

    let buf = ''
    socket.on('data', (d) => {
      buf += d.toString('utf8')
      // accept newline-delimited JSON messages
      let idx
      while ((idx = buf.indexOf('\n')) !== -1) {
        const line = buf.slice(0, idx).trim()
        buf = buf.slice(idx + 1)
        if (!line) continue
        try {
          const msg = JSON.parse(line)
          handleMessage(msg, socket)
        } catch (err) {
          socket.write(`${JSON.stringify({ error: String(err) })  }\n`)
        }
      }
    })

    socket.on('close', () => {
      clients.delete(socket)
      logger.debug(`client disconnected, total: ${clients.size}`)
    })

    socket.on('error', (err) => {
      logger.warn(`socket error: ${err.message}`)
      clients.delete(socket)
    })
  })

  server.listen(SOCKET_PATH, () => {
    try { fs.chmodSync(SOCKET_PATH, 0o600) } catch {}
    logger.info(`listening on ${SOCKET_PATH}`)
  })

  function handleMessage(msg: any, socket: net.Socket) {
    const { id, method, params } = msg
    try {
      let result: any

      // Core orchestration methods
      if (method === 'register') {
        orchestration.register(params)
        result = { ok: true }
      } else if (method === 'update') {
        orchestration.update(params.id, params.patch)
        result = { ok: true }
      } else if (method === 'complete') {
        orchestration.complete(params.id, params.result)
        result = { ok: true }
      } else if (method === 'list') {
        result = orchestration.list(params?.status)
      }
      // Polling method - retrieve queued messages
      else if (method === 'poll') {
        result = handlePoll(params)
      }
      // Heartbeat/keepalive
      else if (method === 'ping') {
        result = { ok: true, timestamp: Date.now() }
      }
      // Get bridge status
      else if (method === 'status') {
        result = {
          connected: true,
          clients: clients.size,
          queueSize: messageQueue.length,
          uptime: process.uptime(),
        }
      }
      else {
        throw new Error('unknown method')
      }

      if (id) {
        socket.write(`${JSON.stringify({ id, result })  }\n`)
      }
    } catch (err) {
      if (id) {
        socket.write(`${JSON.stringify({ id, error: String(err) })  }\n`)
      }
    }
  }

  function handlePoll(params: PollRequest['params']): { messages: QueuedMessage[]; hasMore: boolean } {
    const since = params?.since || 0
    const maxResults = params?.maxResults || 10
    const targetSession = params?.sessionId

    // Filter messages by timestamp and optionally by session
    let filtered = messageQueue.filter(m => m.timestamp > since)
    if (targetSession) {
      filtered = filtered.filter(m => !m.targetSession || m.targetSession === targetSession)
    }

    // Return up to maxResults
    const results = filtered.slice(0, maxResults)
    const hasMore = filtered.length > maxResults

    // Remove returned messages from queue (they're delivered)
    for (const msg of results) {
      const idx = messageQueue.findIndex(m => m.id === msg.id)
      if (idx !== -1) messageQueue.splice(idx, 1)
    }

    return { messages: results, hasMore }
  }

  function queueMessage(message: OutboundMessage, targetSession?: string): void {
    const queued: QueuedMessage = {
      id: Math.random().toString(36).slice(2),
      timestamp: Date.now(),
      message,
      targetSession,
    }

    messageQueue.push(queued)

    // Trim queue if too large
    if (messageQueue.length > MAX_QUEUE_SIZE) {
      messageQueue.shift()
    }

    // Try to send immediately to all connected clients
    broadcast(message)
  }

  function broadcast(message: OutboundMessage): void {
    const data = `${JSON.stringify({ method: message.method, params: message.params })  }\n`
    const deadClients = new Set<net.Socket>()

    for (const client of clients) {
      try {
        client.write(data)
      } catch (err) {
        deadClients.add(client)
      }
    }

    // Clean up dead clients
    for (const dead of deadClients) {
      clients.delete(dead)
      try { dead.end() } catch {}
    }
  }

  // Subscribe to intelligence module events
  function subscribeToEvents(): void {
    if (!eventBus) return

    // Listen for thinker insights
    const unsub1 = (eventBus as any).on?.('worker:message', (e: any) => {
      if (e.pluginId === 'thinker' && e.payload?.type === 'thinker:insight') {
        const insight = e.payload.insight
        const level = e.payload.level
        // Accept both legacy internal levels and new public names
        const priority = (level === 'Think' || level === 'opus') ? 'high' : 'normal'
        // Insights are global (no specific session)
        emitInsight('global', insight, priority)
      }
    })
    if (unsub1) unsubscribers.push(unsub1)

    // Listen for other intelligence events
    const unsub2 = (eventBus as any).on?.('insight', (e: any) => {
      if (e.text) {
        emitInsight(e.sessionId || 'global', e.text, e.priority || 'normal')
      }
    })
    if (unsub2) unsubscribers.push(unsub2)

    logger.info('subscribed to event bus')
  }

  // Public API for intelligence modules
  function emitInsight(sessionId: string, text: string, priority: 'high' | 'normal' | 'low' = 'normal'): void {
    queueMessage(
      {
        method: 'insight:inject',
        params: { sessionId, text, priority },
      },
      sessionId
    )
    logger.debug(`insight queued: ${text.slice(0, 50)}...`)
  }

  function suggestAction(action: string, reason: string, sessionId?: string): void {
    queueMessage(
      {
        method: 'suggest:action',
        params: { action, reason, sessionId },
      },
      sessionId
    )
    logger.debug(`action suggested: ${action}`)
  }

  function broadcastStatus(): void {
    // computeActiveAgents may be sync or async — handle promise safely so periodic timer doesn't throw
    computeActiveAgents(orchestration, logger).then((activeAgents) => {
      queueMessage({
        method: 'status:report',
        params: {
          activeAgents,
          queueDepth: messageQueue.length,
          insightsPending: messageQueue.filter(m => m.message.method === 'insight:inject').length,
        },
      })
    }).catch((err) => {
      logger?.warn?.(`broadcastStatus: failed to compute activeAgents: ${(err && err.message) || String(err)}`)
      queueMessage({
        method: 'status:report',
        params: {
          activeAgents: 0,
          queueDepth: messageQueue.length,
          insightsPending: messageQueue.filter(m => m.message.method === 'insight:inject').length,
        },
      })
    })
  }

  // Subscribe to events if eventBus provided
  if (eventBus) {
    subscribeToEvents()
  }

  // Periodic status broadcast
  const statusInterval = setInterval(() => {
    if (clients.size > 0) {
      broadcastStatus()
    }
  }, 30000) // every 30s
  try { statusInterval.unref?.() } catch {}

  // Cleanup on process exit
  process.on('exit', () => {
    clearInterval(statusInterval)
    server.close()
  })

  function destroy(): void {
    clearInterval(statusInterval)
    server.close()
    // Unsubscribe from event bus
    for (const unsub of unsubscribers) {
      try { unsub() } catch {}
    }
    unsubscribers.length = 0
    logger.info('destroyed')
  }

  return {
    emitInsight,
    suggestAction,
    broadcastStatus,
    destroy,
  }
}
