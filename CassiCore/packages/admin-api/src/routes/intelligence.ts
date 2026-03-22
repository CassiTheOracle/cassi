import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'
import { getDataDir } from '../utils/paths.js'

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

      // v5: use snapshot() and getRecentObservations(); fall back to legacy shims if needed
      const snap = typeof subconscious?.snapshot === 'function'
        ? subconscious.snapshot()
        : subconscious?.getMentalModel?.(sessionId)

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

      // v5: use getRecentObservations(); fall back to legacy getRecentSignals()
      const recentObservations = typeof subconscious?.getRecentObservations === 'function'
        ? subconscious.getRecentObservations(10)
        : (subconscious?.getRecentSignals?.(sessionId, 10) || [])

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
        stats: typeof subconscious?.getEventStreamStats === 'function'
          ? subconscious.getEventStreamStats()
          : (subconscious?.getEnhancedSearchStats?.() || {}),
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

  return false
}
