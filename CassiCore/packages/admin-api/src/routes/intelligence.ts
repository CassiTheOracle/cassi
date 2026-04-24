import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'
import { getDataDir } from '../utils/paths.js'
import { MnemicField } from '../intelligence/mnemic-field/index.js'

let _mnemicField: MnemicField | undefined
function getMnemicField(logger: ILogger): MnemicField {
  if (_mnemicField) return _mnemicField
  const dbPath = path.join(getDataDir(), 'mnemic-field.db')
  _mnemicField = new MnemicField(logger, dbPath)
  _mnemicField.enableNeuralKindling()
  return _mnemicField
}

export interface IntelligenceRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  parts: string[]
}

/**
 * @dep callers: handler (core/admin-api.ts)
 * @dep calls: acknowledgeAnomaly, getRecentObservations, getAnomalies, getEventStreamStats, getObserverStats [+31]
 * @dep flows: HandleIntelligenceRoutes → Kv_get (1/4), HandleIntelligenceRoutes → KeyForSession (1/4), HandleIntelligenceRoutes → CognitiveKeyForSession (1/4) [+2]
 * @dep module: Subconscious
 * @dep risk: HIGH | 1 caller, 5 flows, 1 module
 */

export async function handleIntelligenceRoutes(
  deps: IntelligenceRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, url, parts } = deps

  // --- Locus Bridge Routes ---

  // Must come before generic /intelligence/:module handlers below.

  if (parts[0] === 'intelligence' && parts[1] === 'locus-bridge' && parts[2] === 'assemble' && method === 'POST') {
    const locusBridge = daemon.intelligence?.locusBridge
    if (!locusBridge) {
      sendJSON(res, 404, { error: 'LocusBridge not available' })
      return true
    }

    try {
      const body = await parseBody(req)
      const { messages, systemPromptBase, sessionId } = body
      if (!messages || !Array.isArray(messages)) {
        sendJSON(res, 400, { error: 'messages array is required' })
        return true
      }

      const result = await locusBridge.assemble(
        messages,
        systemPromptBase ?? [],
        sessionId ?? 'unknown',
      )
      sendJSON(res, 200, result)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts[0] === 'intelligence' && parts[1] === 'locus-bridge' && parts[2] === 'spark' && method === 'POST') {
    const locusBridge = daemon.intelligence?.locusBridge
    if (!locusBridge) {
      sendJSON(res, 404, { error: 'LocusBridge not available' })
      return true
    }

    try {
      const body = await parseBody(req)
      const { sessionId, content, type, goal, toolName, filePath, action } = body

      let events: any[] = []

      if (type === 'user-intent' || (!type && content)) {
        events = locusBridge.sparkFromUserPrompt(sessionId ?? 'unknown', content ?? '', goal)
      } else if (type === 'tool-discovery') {
        events = locusBridge.sparkFromToolResult(sessionId ?? 'unknown', toolName ?? 'unknown', content ?? '', goal)
      } else if (type === 'code-reference') {
        events = locusBridge.sparkFromCodeReference(sessionId ?? 'unknown', filePath ?? '', action ?? 'read', content, goal)
      } else {
        sendJSON(res, 400, { error: 'Unsupported spark type or missing content' })
        return true
      }

      sendJSON(res, 200, {
        ok: true,
        kindled: events.length,
        events: events.map((e: any) => ({
          eventId: e.eventId,
          slotIndex: e.slotIndex,
          luminance: e.kindlingLuminance,
          eclipse: e.eclipse ? {
            eclipsedSparkId: e.eclipse.eclipsedSpark.sparkId,
            luminanceDelta: e.eclipse.luminanceDelta,
          } : null,
        })),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts[0] === 'intelligence' && parts[1] === 'locus-bridge' && parts[2] === 'state' && method === 'GET') {
    const locusBridge = daemon.intelligence?.locusBridge
    if (!locusBridge) {
      sendJSON(res, 404, { error: 'LocusBridge not available' })
      return true
    }

    try {
      const snapshot = locusBridge.getSnapshot()
      sendJSON(res, 200, snapshot)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts[0] === 'intelligence' && parts[1] === 'locus-bridge' && parts[2] === 'curate' && method === 'POST') {
    const locusBridge = daemon.intelligence?.locusBridge
    if (!locusBridge) {
      sendJSON(res, 404, { error: 'LocusBridge not available' })
      return true
    }

    try {
      const curated = await locusBridge.curate()
      sendJSON(res, 200, curated)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence - list modules
  if (parts[0] === 'intelligence' && method === 'GET' && parts.length === 1) {
    const modules = (daemon.intelligence?.all ?? []).map((m: any) => ({ name: m.name, priority: m.priority, status: 'active' }))
    sendJSON(res, 200, modules)
    return true
  }

  // GET /intelligence/:module/model
  if (parts[0] === 'intelligence' && parts[2] === 'model' && parts.length === 3 && method === 'GET') {
    const moduleName = parts[1]
    const mod = (daemon.intelligence?.all ?? []).find((m: any) => m.name === moduleName)
    if (!mod) {
      sendJSON(res, 404, { error: `Module '${moduleName}' not found` })
      return true
    }
    if (typeof (mod as any).getModelConfig !== 'function') {
      sendJSON(res, 400, { error: `Module '${moduleName}' does not support model config (legacy module)` })
      return true
    }
    sendJSON(res, 200, { module: moduleName, config: (mod as any).getModelConfig() })
    return true
  }

  // POST /intelligence/:module/model
  if (parts[0] === 'intelligence' && parts[2] === 'model' && parts.length === 3 && method === 'POST') {
    const moduleName = parts[1]
    const mod = (daemon.intelligence?.all ?? []).find((m: any) => m.name === moduleName)
    if (!mod) {
      sendJSON(res, 404, { error: `Module '${moduleName}' not found` })
      return true
    }
    if (typeof (mod as any).setModelConfig !== 'function') {
      sendJSON(res, 400, { error: `Module '${moduleName}' does not support model config (legacy module)` })
      return true
    }

    try {
      const body = await parseBody(req)
      const overrides: Record<string, unknown> = {}
      if (body.model !== undefined) overrides.model = body.model
      if (body.providerId !== undefined) overrides.providerId = body.providerId
      if (body.temperature !== undefined) overrides.temperature = body.temperature
      if (body.maxTokens !== undefined) overrides.maxTokens = body.maxTokens
      if (body.timeoutMs !== undefined) overrides.timeoutMs = body.timeoutMs

      if (Object.keys(overrides).length === 0) {
        sendJSON(res, 400, { error: 'No model config fields provided. Accepts: model, providerId, temperature, maxTokens, timeoutMs' })
        return true
      }

      ;(mod as any).setModelConfig(overrides)
      sendJSON(res, 200, { module: moduleName, config: (mod as any).getModelConfig(), updated: Object.keys(overrides) })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/subconscious/debug
  if (parts[0] === 'intelligence' && parts[1] === 'subconscious' && parts[2] === 'debug' && method === 'GET') {
    const sessionId = url.searchParams.get('sessionId') || 'default'
    try {
      const subconscious = daemon.intelligence?.subconscious
      const contextManager = daemon.intelligence?.contextManager

      const snap = subconscious?.snapshot?.()

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

      const recentObservations = subconscious?.getRecentObservations?.(10) ?? []

      sendJSON(res, 200, {
        sessionId,
        timestamp: Date.now(),
        snapshot: snap ?? null,
        context: contextData,
        recentObservations: recentObservations.map((o: any) => ({
          type: o.type ?? o.source ?? 'observation',
          summary: o.summary ?? o.content ?? o.description,
          confidence: o.confidence,
          timestamp: o.timestamp,
          patterns: o.patterns,
        })),
        stats: subconscious?.getEventStreamStats?.() ?? {},
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET/POST/DELETE /intelligence/thinker/strategy
  if (pathname === '/intelligence/thinker/strategy') {
    try {
      const mem = daemon.intelligence?.memory
      if (!mem) {
        sendJSON(res, 503, { error: 'memory not initialised' })
        return true
      }

      if (method === 'GET') {
        const strategy = await mem.kv_get('thinker:strategy')
        sendJSON(res, 200, { strategy: strategy ?? null })
        return true
      }

      if (method === 'POST') {
        const body = await parseBody(req)
        if (!body || typeof body !== 'object') {
          sendJSON(res, 400, { error: 'missing strategy body' })
          return true
        }
        await mem.kv_set('thinker:strategy', body)
        daemon.bus.emit({ type: 'thinker:strategy-updated', strategy: body })
        sendJSON(res, 200, { ok: true })
        return true
      }

      if (method === 'DELETE') {
        await mem.kv_del('thinker:strategy')
        daemon.bus.emit({ type: 'thinker:strategy-updated', strategy: null })
        sendJSON(res, 200, { ok: true })
        return true
      }
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET/POST/DELETE /intelligence/thinker/insight-history
  if (pathname === '/intelligence/thinker/insight-history') {
    try {
      const mem = daemon.intelligence?.memory
      if (!mem) {
        sendJSON(res, 503, { error: 'memory not initialised' })
        return true
      }

      if (method === 'GET') {
        const history = await mem.kv_get('thinker:insight-history')
        sendJSON(res, 200, { insightHistory: history ?? [] })
        return true
      }

      if (method === 'POST') {
        const body = await parseBody(req)
        if (!body || !Array.isArray(body)) {
          sendJSON(res, 400, { error: 'expected array body' })
          return true
        }
        await mem.kv_set('thinker:insight-history', body)
        daemon.bus.emit({ type: 'thinker:insight-history-updated', history: body })
        sendJSON(res, 200, { ok: true })
        return true
      }

      if (method === 'DELETE') {
        await mem.kv_del('thinker:insight-history')
        daemon.bus.emit({ type: 'thinker:insight-history-updated', history: [] })
        sendJSON(res, 200, { ok: true })
        return true
      }
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/thinker/stats
  if (method === 'GET' && pathname === '/intelligence/thinker/stats') {
    try {
      const thinker = daemon.intelligence?.thinker
      if (!thinker) {
        sendJSON(res, 503, { error: 'thinker not initialised' })
        return true
      }
      const stats = typeof thinker.stats === 'function' ? await Promise.resolve(thinker.stats()) : undefined
      sendJSON(res, 200, { stats: stats ?? null })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/subconscious/learnings
  if (method === 'GET' && pathname === '/intelligence/subconscious/learnings') {
    try {
      const subconscious = daemon.intelligence?.subconscious

      // v5: use live getRecentObservations(); fallback to KV/file for legacy data
      let learnings: any[] = []
      if (typeof subconscious?.getRecentObservations === 'function') {
        const limit = parseInt(url.searchParams.get('limit') || '50', 10)
        learnings = subconscious.getRecentObservations(limit).map((o: any) => ({
          id: o.id,
          summary: o.summary,
          type: o.source === 'llm' ? 'llm_sweep' : 'pattern',
          confidence: o.confidence,
          patterns: o.patterns,
          timestamp: o.timestamp,
          sessionId: o.sessionId,
        }))
      } else {
        const mem = daemon.intelligence?.memory
        if (mem) {
          try { learnings = await mem.kv_get('subconscious:learnings') || [] } catch {}
        }
        if (!learnings.length) {
          const filePath = path.join(getDataDir(), 'subconscious.json')
          try {
            if (fs.existsSync(filePath)) learnings = JSON.parse(fs.readFileSync(filePath, 'utf8') || '[]')
          } catch { /* ignore */ }
        }
      }

      sendJSON(res, 200, { learnings })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/subconscious/stream
  // Returns live event stream stats + observer pipeline status for the cassi_consciousness tool.
  if (method === 'GET' && pathname === '/intelligence/subconscious/stream') {
    try {
      const subconscious = daemon.intelligence?.subconscious
      const windowSecs = parseInt(url.searchParams.get('windowSecs') || '60', 10)

      if (typeof subconscious?.getObserverStats === 'function') {
        const data = subconscious.getObserverStats(windowSecs)
        sendJSON(res, 200, { stream: data })
      } else {
        sendJSON(res, 503, { error: 'subconscious not initialised or getObserverStats unavailable' })
      }
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/subconscious/anomalies
  if (method === 'GET' && pathname === '/intelligence/subconscious/anomalies') {
    try {
      const subconscious = daemon.intelligence?.subconscious

      // v5: use live getAnomalies(); fallback to KV
      let anomalies: any[] = []
      if (typeof subconscious?.getAnomalies === 'function') {
        const includeAck = url.searchParams.get('includeAcknowledged') === 'true'
        anomalies = subconscious.getAnomalies(includeAck).map((a: any) => ({
          id: a.id,
          description: a.description,
          severity: a.severity,
          eventTypes: a.eventTypes,
          suggestedAction: a.suggestedAction,
          timestamp: a.timestamp,
          sessionId: a.sessionId,
          acknowledged: a.acknowledged ?? false,
        }))
      } else {
        const mem = daemon.intelligence?.memory
        if (mem) {
          try { anomalies = await mem.kv_get('subconscious:anomalies') || [] } catch {}
        }
      }

      sendJSON(res, 200, { anomalies })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/subconscious/stats
  if (method === 'GET' && pathname === '/intelligence/subconscious/stats') {
    try {
      const subconscious = daemon.intelligence?.subconscious

      // v5: use live APIs for stats
      if (typeof subconscious?.getEventStreamStats === 'function') {
        const streamStats = subconscious.getEventStreamStats()
        const observations = typeof subconscious.getRecentObservations === 'function'
          ? subconscious.getRecentObservations(200)
          : []
        const anomalies = typeof subconscious.getAnomalies === 'function'
          ? subconscious.getAnomalies(true)
          : []

        const stats = {
          totalEvents: streamStats.totalEvents,
          activeSessions: streamStats.activeSessions,
          eventRate: streamStats.eventRate,
          totalObservations: observations.length,
          totalAnomalies: anomalies.length,
          activeAnomalies: anomalies.filter((a: any) => !a.acknowledged).length,
          patternsRecognized: observations.filter((o: any) => o.patterns?.length > 0).length,
          averageConfidence: observations.length > 0
            ? observations.reduce((s: number, o: any) => s + (o.confidence || 0), 0) / observations.length
            : 0,
          lastUpdate: observations.length > 0
            ? Math.max(...observations.map((o: any) => o.timestamp || 0))
            : Date.now(),
          topEventTypes: streamStats.typeCounts
            ? Object.entries(streamStats.typeCounts)
                .sort((a: any, b: any) => b[1] - a[1])
                .slice(0, 10)
                .map(([type, count]) => ({ type, count }))
            : [],
        }
        sendJSON(res, 200, { stats })
        return true
      }

      // Fallback: KV-based stats
      const mem = daemon.intelligence?.memory
      let learnings: any[] = []
      let anomalies: any[] = []
      if (mem) {
        try { learnings = await mem.kv_get('subconscious:learnings') || [] } catch {}
        try { anomalies = await mem.kv_get('subconscious:anomalies') || [] } catch {}
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

      sendJSON(res, 200, { stats })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /intelligence/subconscious/learnings/search
  if (method === 'POST' && pathname === '/intelligence/subconscious/learnings/search') {
    try {
      const body = await parseBody(req)
      const query = body?.query?.toLowerCase() || ''
      if (!query) {
        sendJSON(res, 400, { error: 'query required' })
        return true
      }

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

      sendJSON(res, 200, { learnings: results, query, count: results.length })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /intelligence/subconscious/anomalies/:id/acknowledge
  if (method === 'POST' && parts[0] === 'intelligence' && parts[1] === 'subconscious' && parts[2] === 'anomalies' && parts[4] === 'acknowledge') {
    try {
      const anomalyId = parts[3]
      if (!anomalyId) {
        sendJSON(res, 400, { error: 'anomaly id required' })
        return true
      }

      const subconscious = daemon.intelligence?.subconscious

      // v5: delegate to live acknowledgeAnomaly()
      if (typeof subconscious?.acknowledgeAnomaly === 'function') {
        const found = subconscious.acknowledgeAnomaly(anomalyId)
        if (!found) {
          sendJSON(res, 404, { error: 'anomaly not found' })
          return true
        }
        sendJSON(res, 200, { ok: true, anomalyId })
        return true
      }

      // Fallback: KV-based acknowledge
      const mem = daemon.intelligence?.memory
      if (!mem) {
        sendJSON(res, 503, { error: 'memory not available' })
        return true
      }

      const anomalies: any[] = await mem.kv_get('subconscious:anomalies') || []
      const idx = anomalies.findIndex((a: any) => a.id === anomalyId || a.summary === anomalyId)

      if (idx === -1) {
        sendJSON(res, 404, { error: 'anomaly not found' })
        return true
      }

      anomalies[idx] = { ...anomalies[idx], acknowledged: true, acknowledgedAt: Date.now() }
      await mem.kv_set('subconscious:anomalies', anomalies)

      sendJSON(res, 200, { ok: true, anomalyId })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // DELETE /intelligence/subconscious/learnings
  if (method === 'DELETE' && pathname === '/intelligence/subconscious/learnings') {
    try {
      const mem = daemon.intelligence?.memory
      if (mem) {
        await mem.kv_del('subconscious:learnings')
      }
      const filePath = path.join(getDataDir(), 'subconscious.json')
      try {
        if (fs.existsSync(filePath)) fs.unlinkSync(filePath)
      } catch {}

      sendJSON(res, 200, { ok: true, cleared: 'learnings' })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // DELETE /intelligence/subconscious/anomalies
  if (method === 'DELETE' && pathname === '/intelligence/subconscious/anomalies') {
    try {
      const mem = daemon.intelligence?.memory
      if (mem) {
        await mem.kv_del('subconscious:anomalies')
      }
      sendJSON(res, 200, { ok: true, cleared: 'anomalies' })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/archivist/recent
  if (method === 'GET' && pathname === '/intelligence/archivist/recent') {
    try {
      const mem = daemon.intelligence?.memory
      if (!mem) {
        sendJSON(res, 503, { error: 'memory module not initialized' })
        return true
      }
      const limit = parseInt(url.searchParams.get('limit') || '20', 10)
      const entries = mem.getRecentArchiveEntries(limit)
      sendJSON(res, 200, { entries })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/archivist/stats
  if (method === 'GET' && pathname === '/intelligence/archivist/stats') {
    try {
      const mem = daemon.intelligence?.memory
      if (!mem) {
        sendJSON(res, 503, { error: 'memory module not initialized' })
        return true
      }
      const stats = mem.getArchiveStats()
      const queueStats = mem.getArchiveQueueStats()
      sendJSON(res, 200, { stats, queueStats })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/context-focus
  if (method === 'GET' && pathname === '/intelligence/context-focus') {
    try {
      const sessionId = url.searchParams.get('sessionId')
      if (!sessionId) {
        sendJSON(res, 400, { error: 'sessionId query parameter is required' })
        return true
      }
      // This function is defined in the main admin-api and passed via deps
      sendJSON(res, 501, { error: 'context-focus endpoint requires buildFocusState function' })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/activity
  if (method === 'GET' && pathname === '/intelligence/activity') {
    try {
      const intel = daemon.intelligence
      if (!intel) {
        sendJSON(res, 503, { error: 'intelligence layer not initialized' })
        return true
      }

      const modules = intel.all.map((m: any) => ({
        name: m.name || m.constructor?.name || 'unknown',
        priority: m.priority ?? 0,
        status: 'active',
      }))

      let thinkerStats = null
      try { thinkerStats = intel.thinker?.stats?.() ?? null } catch {}

      let thinkerStrategy = null
      try { thinkerStrategy = intel.memory?.kv_get('thinker:strategy') ?? null } catch {}

      let memoryStats = null
      try { memoryStats = intel.memory?.stats?.() ?? null } catch {}

      let archiveStats = null
      try { archiveStats = intel.memory?.getArchiveStats?.() ?? null } catch {}

      let unresolvedPatterns = null
      try { unresolvedPatterns = intel.reflect?.unresolved?.(5) ?? null } catch {}

      const optimizerHealth: Record<string, any> = {}
      try {
        const sessions = Array.from(daemon.sessions?.['sessions']?.values?.() || [])
        for (const s of sessions.slice(0, 5)) {
          const score = intel.optimizer?.scoreSession?.((s as any).id)
          if (score) optimizerHealth[(s as any).id] = score
        }
      } catch {}

      let dialecticSummary = null
      try {
        const sessions = Array.from(daemon.sessions?.['sessions']?.values?.() || [])
        if (sessions.length > 0) {
          const recentSession = sessions.sort((a: any, b: any) => (b.lastActiveAt || 0) - (a.lastActiveAt || 0))[0] as any
          dialecticSummary = intel.dialectic?.getStats?.(recentSession.id) ?? null
        }
      } catch {}

      let recentStudies = null
      let scientistSummary = null
      try {
        recentStudies = intel.aiScientist?.getRecentStudies?.(3) ?? null
        scientistSummary = (intel.aiScientist as any)?.getResearchSummary?.() ?? null
      } catch {}

      let engineerSummary = null
      try {
        engineerSummary = (intel.aiEngineer as any)?.getEngineerSummary?.() ?? null
      } catch {}

      sendJSON(res, 200, {
        timestamp: Date.now(),
        modules,
        thinker: { stats: thinkerStats, strategy: thinkerStrategy },
        memory: memoryStats,
        archive: archiveStats,
        reflect: { unresolvedPatterns },
        optimizer: { sessionHealth: optimizerHealth },
        dialectic: dialecticSummary,
        aiScientist: { recentStudies, ...(scientistSummary ?? {}) },
        aiEngineer: engineerSummary,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /intelligence/thinker/think
  if (method === 'POST' && pathname === '/intelligence/thinker/think') {
    try {
      const body = await parseBody(req)
      const publicDepth = body?.depth === 'Think' ? 'Think' : 'Ponder'
      const context = body?.context
      const wait = body?.wait === false ? false : true
      const urgency = body?.urgency || 'medium'
      const trigger = body?.trigger || 'admin'
      const thinker = daemon.intelligence?.thinker
      if (!thinker) {
        sendJSON(res, 503, { error: 'thinker not available' })
        return true
      }

      if (context) {
        const p = publicDepth === 'Think'
          ? (thinker as any).Think({ context, urgency, trigger })
          : (thinker as any).Ponder({ context, urgency, trigger })

        if (!wait) {
          p.catch((e: any) => daemon.logger?.warn?.('admin: thinker background failed', { error: String(e) }))
          sendJSON(res, 200, { ok: true, message: 'Thinker triggered (async)' })
          return true
        }

        const result = await p
        sendJSON(res, 200, { ok: true, result: result ?? null })
        return true
      } else {
        if (!wait) {
          (thinker as any).think(publicDepth).then(() => {}).catch((e: any) => daemon.logger?.warn?.('admin: thinker background failed', { error: String(e) }))
          sendJSON(res, 200, { ok: true, message: 'Thinker triggered (async)' })
          return true
        }
        const insight = await (thinker as any).think(publicDepth)
        sendJSON(res, 200, { ok: true, insight })
        return true
      }
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /intelligence/thinker/feedback
  if (method === 'POST' && pathname === '/intelligence/thinker/feedback') {
    try {
      const body = await parseBody(req)
      const insight = body?.insight
      const helpful = body?.helpful
      const usedInResponse = body?.usedInResponse ?? false
      const sessionId = body?.sessionId
      if (!insight || typeof helpful !== 'boolean') {
        sendJSON(res, 400, { error: 'missing insight or helpful flag' })
        return true
      }
      daemon.bus.emit({ type: 'thinker:feedback', insight, helpful, usedInResponse, sessionId })
      sendJSON(res, 200, { ok: true })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }


   // GET /intelligence/self-healer/status
   if (method === 'GET' && pathname === '/intelligence/self-healer/status') {
     const selfHealer = daemon.intelligence?.selfHealer
     if (!selfHealer) {
       sendJSON(res, 404, { error: 'SelfHealingAgent not loaded' })
       return true
     }
     try {
       const stats = (selfHealer as any).getStats?.()
       sendJSON(res, 200, stats ?? { error: 'getStats not available' })
     } catch (err) {
       sendJSON(res, 500, { error: String(err) })
     }
     return true
   }

   // PATCH /intelligence/self-healer/config  — runtime toggle for autoApply / autoRestart
   if (method === 'PATCH' && pathname === '/intelligence/self-healer/config') {
     const selfHealer = daemon.intelligence?.selfHealer
     if (!selfHealer) {
       sendJSON(res, 404, { error: 'SelfHealingAgent not loaded' })
       return true
     }
     try {
       const body = await parseBody(req)
       const updated: Record<string, boolean> = {}
       if (typeof body?.autoApply === 'boolean') {
         ;(selfHealer as any).setAutoApply(body.autoApply)
         updated.autoApply = body.autoApply
       }
       if (typeof body?.autoRestart === 'boolean') {
         ;(selfHealer as any).setAutoRestart(body.autoRestart)
         updated.autoRestart = body.autoRestart
       }
       if (Object.keys(updated).length === 0) {
         sendJSON(res, 400, { error: 'Provide autoApply and/or autoRestart (boolean)' })
         return true
       }
       sendJSON(res, 200, { updated })
     } catch (err) {
       sendJSON(res, 500, { error: String(err) })
     }
     return true
   }

   // POST /intelligence/self-healer/trigger
  if (method === 'POST' && pathname === '/intelligence/self-healer/trigger') {
    const selfHealer = daemon.intelligence?.selfHealer
    if (!selfHealer) {
      sendJSON(res, 404, { error: 'SelfHealingAgent not loaded' })
      return true
    }
    try {
      const body = await parseBody(req)
      const processorName = body?.processorName ?? body?.moduleName ?? 'manual'
      const errorMsg = body?.error ?? ''
      if (!errorMsg) {
        sendJSON(res, 400, { error: 'body.error is required' })
        return true
      }
      // Concat stack trace so the self-healer can parse file:line references directly
      const rawError = body?.stack ? `${errorMsg}\n${body.stack}` : errorMsg
      const id = await (selfHealer as any).triggerRepair(processorName, rawError)
      sendJSON(res, 202, { accepted: true, id })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // POST /intelligence/workspace/enrich — Search memory and submit results as workspace signals
  if (method === 'POST' && parts[1] === 'workspace' && parts[2] === 'enrich') {
    const workspace = daemon.intelligence?.globalWorkspace
    if (!workspace) {
      sendJSON(res, 503, { error: 'Global Workspace not available' })
      return true
    }

    try {
      const body = await deps.parseBody(req)
      const query = body?.query as string
      const sessionId = body?.sessionId as string ?? '*'
      if (!query) {
        sendJSON(res, 400, { error: 'Missing query' })
        return true
      }

      let submitted = 0
      const signalBase = `memory-enrich-${Date.now()}`

      // Search the Mnemic Field (spatial memory — engrams, potentiation, kindling)
      try {
        const mnemicField = getMnemicField(logger)
        const hits = await mnemicField.retrieve(query, { limit: 5 })
        for (const hit of hits) {
          if (!hit.content || hit.content.length < 10) continue
          const signal = {
            signalId: `${signalBase}-mnemic-${submitted}`,
            source: 'memory',
            sessionId,
            type: 'memory' as const,
            content: hit.content,
            luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, composite: 0 },
            createdAt: Date.now(),
            urgencyHint: Math.min(0.2, (hit.potentiation ?? 0) * 0.3),
            metadata: {
              engramId: hit.id,
              nodeType: hit.nodeType,
              score: hit.score,
              charge: hit.charge,
              provenance: hit.provenance,
            },
          }
          if (workspace.submit(signal)) submitted++
        }
      } catch (err) {
        logger.warn('Workspace enrich: mnemic field search failed', { error: String(err) })
      }

      // Search the Self-Model Field (architectural knowledge — modules, capabilities, weaknesses)
      try {
        const smf = (daemon as any).__selfModelField ?? (daemon?.intelligence as any)?.__selfModelField
        if (smf && typeof smf.retrieve === 'function') {
          const smHits = await smf.retrieve(query, { limit: 3 })
          for (const hit of smHits) {
            const prefix = hit.nodeType === 'module' ? '[Module]'
              : hit.nodeType === 'capability' ? '[Capability]'
              : hit.nodeType === 'weakness' ? '[Weakness]'
              : `[${hit.nodeType}]`
            const signal = {
              signalId: `${signalBase}-selfmodel-${submitted}`,
              source: 'self-model',
              sessionId,
              type: 'memory' as const,
              content: `${prefix} ${hit.content}`,
              luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, composite: 0 },
              createdAt: Date.now(),
              metadata: {
                engramId: hit.id,
                nodeType: hit.nodeType,
                score: hit.score,
                sourceField: 'self-model',
              },
            }
            if (workspace.submit(signal)) submitted++
          }
        }
      } catch (err) {
        logger.warn('Workspace enrich: self-model search failed', { error: String(err) })
      }

      // Search the classic Memory module (archived conversations, insights, patterns)
      const memory = daemon.intelligence?.memory
      if (memory) {
        try {
          const results = await (memory as any).search(query, { limit: 5 })
          for (const result of results) {
            const content = result.content ?? result.text
            if (!content || content.length < 10) continue
            const signal = {
              signalId: `${signalBase}-classic-${submitted}`,
              source: 'memory',
              sessionId,
              type: 'memory' as const,
              content,
              luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, composite: 0 },
              createdAt: Date.now(),
              metadata: {
                memoryId: result.id,
                type: result.type,
                confidence: result.confidence,
                score: result.score,
              },
            }
            if (workspace.submit(signal)) submitted++
          }
        } catch (err) {
          logger.warn('Workspace enrich: classic memory search failed', { error: String(err) })
        }
      }

      sendJSON(res, 200, { submitted, query: query.slice(0, 100) })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/workspace/context — Assembled workspace context for hook injection
  if (method === 'GET' && parts[1] === 'workspace' && parts[2] === 'context') {
    const workspace = daemon.intelligence?.globalWorkspace
    if (!workspace) {
      sendJSON(res, 503, { error: 'Global Workspace not available' })
      return true
    }

    try {
      const sessionId = deps.url.searchParams.get('sessionId') ?? '*'
      const assembled = workspace.assemble(sessionId)
      const schema = workspace.getAttentionSchema()

      sendJSON(res, 200, {
        parts: assembled,
        attentionSchema: schema,
        threshold: workspace.getSnapshot().threshold,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/workspace — Global Workspace state
  if (method === 'GET' && parts[1] === 'workspace') {
    const workspace = daemon.intelligence?.globalWorkspace
    if (!workspace) {
      sendJSON(res, 503, { error: 'Global Workspace not available' })
      return true
    }

    try {
      const snapshot = workspace.getSnapshot()
      const schema = workspace.getAttentionSchema()
      const memory = workspace.getMemory()

      sendJSON(res, 200, {
        snapshot: {
          slots: snapshot.slots.map((s: any) => s.signal ? {
            index: s.index,
            source: s.signal.source,
            type: s.signal.type,
            contentPreview: s.signal.content.slice(0, 200),
            luminance: s.signal.luminance.composite,
            occupancyTicks: s.occupancyTicks,
          } : { index: s.index, empty: true }),
          pendingCount: snapshot.pendingCount,
          totalSubmitted: snapshot.totalSubmitted,
          totalIgnited: snapshot.totalIgnited,
          ignitionRate: snapshot.ignitionRate,
          threshold: snapshot.threshold,
          tickCount: snapshot.tickCount,
        },
        attentionSchema: schema,
        credibility: memory.getAllRecords(),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts[1] === 'aurora') {
    const aurora = daemon.intelligence?.aurora
    if (!aurora) {
      sendJSON(res, 503, { error: 'Aurora not available' })
      return true
    }

    if (method === 'GET' && !parts[2]) {
      try {
        const state = aurora.currentState
        if (!state) {
          sendJSON(res, 200, { state: null, message: 'No cognitive state built yet' })
          return true
        }
        sendJSON(res, 200, {
          foci: state.foci ?? [],
          nodeCount: state.graph?.nodes?.size ?? 0,
          edgeCount: state.graph?.edgeCount ?? 0,
          coherence: state.coherence ?? 0,
          integration: state.integration ?? 0,
          affect: state.affect ?? null,
          trendingConcepts: state.trendingConcepts ?? [],
          gaps: state.gaps ?? [],
          hubs: (state.hubs ?? []).map((h: any) => ({ id: h.id, label: h.label, centrality: h.centrality })),
          timestamp: state.timestamp,
        })
        return true
      } catch (err) {
        sendJSON(res, 500, { error: String(err) })
        return true
      }
    }

    if (method === 'GET' && parts[2] === 'serialize') {
      try {
        const serialized = aurora.serialize()
        sendJSON(res, 200, { context: serialized })
        return true
      } catch (err) {
        sendJSON(res, 500, { error: String(err) })
        return true
      }
    }

    if (method === 'GET' && parts[2] === 'path') {
      const from = deps.url.searchParams.get('from')
      const to = deps.url.searchParams.get('to')
      if (!from || !to) {
        sendJSON(res, 400, { error: 'Missing from/to query parameters' })
        return true
      }
      try {
        const claustrum = aurora.getClaustrum()
        const state = aurora.currentState
        if (!state || !claustrum) {
          sendJSON(res, 200, { path: null })
          return true
        }
        const cogPath = claustrum.findShortestPath(state.graph, from, to)
        sendJSON(res, 200, { path: cogPath })
        return true
      } catch (err) {
        sendJSON(res, 500, { error: String(err) })
        return true
      }
    }

    if (method === 'POST' && parts[2] === 'observe') {
      try {
        const body = await deps.parseBody(req)
        const text = body?.text as string
        if (!text) {
          sendJSON(res, 400, { error: 'Missing text field' })
          return true
        }
        const update = aurora.observeReasoning(text)
        sendJSON(res, 200, update)
        return true
      } catch (err) {
        sendJSON(res, 500, { error: String(err) })
        return true
      }
    }

    return true
  }

  return false
}
