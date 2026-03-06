import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface CycleHooksRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  pathname: string
}

export async function handleCycleHooksRoutes(
  deps: CycleHooksRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, url, pathname } = deps

  // GET /intelligence/outcomes/stats
  if (method === 'GET' && pathname === '/intelligence/outcomes/stats') {
    try {
      const tracker = daemon.outcomeTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'outcome tracker not initialized' })
        return true
      }
      sendJSON(res, 200, tracker.getStats())
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/outcomes/feedback
  if (method === 'GET' && pathname === '/intelligence/outcomes/feedback') {
    try {
      const tracker = daemon.outcomeTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'outcome tracker not initialized' })
        return true
      }
      const sessionId = url.searchParams.get('sessionId')
      if (!sessionId) {
        sendJSON(res, 400, { error: 'sessionId query parameter is required' })
        return true
      }
      const limit = parseInt(url.searchParams.get('limit') || '10', 10)
      const feedback = tracker.getRecentFeedback(sessionId, limit)
      sendJSON(res, 200, { feedback })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/outcomes/sources/:source
  if (method === 'GET' && pathname.startsWith('/intelligence/outcomes/sources/')) {
    try {
      const tracker = daemon.outcomeTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'outcome tracker not initialized' })
        return true
      }
      const source = pathname.split('/intelligence/outcomes/sources/')[1]
      if (!source) {
        sendJSON(res, 400, { error: 'source parameter is required' })
        return true
      }
      const windowMs = parseInt(url.searchParams.get('windowMs') || String(24 * 60 * 60_000), 10)
      const stats = tracker.getSourceStats(decodeURIComponent(source), windowMs)
      sendJSON(res, 200, { stats: stats || null })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/outcomes/tools/:toolName
  if (method === 'GET' && pathname.startsWith('/intelligence/outcomes/tools/')) {
    try {
      const tracker = daemon.outcomeTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'outcome tracker not initialized' })
        return true
      }
      const toolName = pathname.split('/intelligence/outcomes/tools/')[1]
      if (!toolName) {
        sendJSON(res, 400, { error: 'toolName parameter is required' })
        return true
      }
      const windowMs = parseInt(url.searchParams.get('windowMs') || String(24 * 60 * 60_000), 10)
      const stats = tracker.getToolStats(decodeURIComponent(toolName), windowMs)
      sendJSON(res, 200, { stats: stats || null })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/profiler/stats
  if (method === 'GET' && pathname === '/intelligence/profiler/stats') {
    try {
      const profiler = daemon.providerProfiler
      if (!profiler) {
        sendJSON(res, 503, { error: 'provider profiler not initialized' })
        return true
      }
      sendJSON(res, 200, profiler.getStats())
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/profiler/aggregate
  if (method === 'GET' && pathname === '/intelligence/profiler/aggregate') {
    try {
      const profiler = daemon.providerProfiler
      if (!profiler) {
        sendJSON(res, 503, { error: 'provider profiler not initialized' })
        return true
      }
      const opts: any = {}
      const providerId = url.searchParams.get('providerId')
      const model = url.searchParams.get('model')
      const windowMs = url.searchParams.get('windowMs')
      if (providerId) opts.providerId = providerId
      if (model) opts.model = model
      if (windowMs) opts.windowMs = parseInt(windowMs, 10)
      const aggregate = profiler.getAggregateStats(opts)
      sendJSON(res, 200, { aggregate })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/profiler/hourly
  if (method === 'GET' && pathname === '/intelligence/profiler/hourly') {
    try {
      const profiler = daemon.providerProfiler
      if (!profiler) {
        sendJSON(res, 503, { error: 'provider profiler not initialized' })
        return true
      }
      const opts: any = {}
      const providerId = url.searchParams.get('providerId')
      const model = url.searchParams.get('model')
      const hours = url.searchParams.get('hours')
      if (providerId) opts.providerId = providerId
      if (model) opts.model = model
      if (hours) opts.hours = parseInt(hours, 10)
      const hourly = profiler.getHourlyStats(opts)
      sendJSON(res, 200, { hourly })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/budget
  if (method === 'GET' && pathname === '/intelligence/budget') {
    try {
      const tracker = daemon.budgetTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'budget tracker not initialized' })
        return true
      }
      const providerId = url.searchParams.get('providerId')
      if (providerId) {
        const snapshot = tracker.getSnapshot(providerId)
        sendJSON(res, 200, { snapshots: snapshot ? [snapshot] : [], tier: tracker.getTier(providerId) })
        return true
      }
      const snapshots = tracker.getAllSnapshots()
      const tiers: Record<string, string> = {}
      for (const snap of snapshots) {
        tiers[snap.providerId] = tracker.getTier(snap.providerId)
      }
      sendJSON(res, 200, { snapshots, tiers })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/strategy/stats
  if (method === 'GET' && pathname === '/intelligence/strategy/stats') {
    try {
      const tracker = daemon.strategyTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'strategy tracker not initialized' })
        return true
      }
      sendJSON(res, 200, tracker.getStats())
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/strategy/history
  if (method === 'GET' && pathname === '/intelligence/strategy/history') {
    try {
      const tracker = daemon.strategyTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'strategy tracker not initialized' })
        return true
      }
      const module = url.searchParams.get('module')
      if (!module) {
        sendJSON(res, 400, { error: 'module query parameter is required' })
        return true
      }
      const limit = parseInt(url.searchParams.get('limit') || '20', 10)
      const history = tracker.getStrategyHistory(module, limit)
      sendJSON(res, 200, { history })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/strategy/best
  if (method === 'GET' && pathname === '/intelligence/strategy/best') {
    try {
      const tracker = daemon.strategyTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'strategy tracker not initialized' })
        return true
      }
      const module = url.searchParams.get('module')
      if (!module) {
        sendJSON(res, 400, { error: 'module query parameter is required' })
        return true
      }
      const best = tracker.getBestStrategy(module)
      sendJSON(res, 200, { strategy: best || null })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/strategy/dialectic-effectiveness
  if (method === 'GET' && pathname === '/intelligence/strategy/dialectic-effectiveness') {
    try {
      const tracker = daemon.strategyTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'strategy tracker not initialized' })
        return true
      }
      const limit = parseInt(url.searchParams.get('limit') || '20', 10)
      const effectiveness = tracker.getDialecticEffectiveness(limit)
      sendJSON(res, 200, { effectiveness })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/correlator/stats
  if (method === 'GET' && pathname === '/intelligence/correlator/stats') {
    try {
      const correlator = daemon.crossSessionCorrelator
      if (!correlator) {
        sendJSON(res, 503, { error: 'cross-session correlator not initialized' })
        return true
      }
      sendJSON(res, 200, correlator.getStats())
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/correlator/patterns
  if (method === 'GET' && pathname === '/intelligence/correlator/patterns') {
    try {
      const correlator = daemon.crossSessionCorrelator
      if (!correlator) {
        sendJSON(res, 503, { error: 'cross-session correlator not initialized' })
        return true
      }
      const opts: any = {}
      const category = url.searchParams.get('category')
      const minConfidence = url.searchParams.get('minConfidence')
      const limit = url.searchParams.get('limit')
      if (category) opts.category = category
      if (minConfidence) opts.minConfidence = parseFloat(minConfidence)
      if (limit) opts.limit = parseInt(limit, 10)
      const patterns = correlator.getPatterns(opts)
      sendJSON(res, 200, { patterns })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/correlator/patterns/:key
  if (method === 'GET' && pathname.startsWith('/intelligence/correlator/patterns/')) {
    try {
      const correlator = daemon.crossSessionCorrelator
      if (!correlator) {
        sendJSON(res, 503, { error: 'cross-session correlator not initialized' })
        return true
      }
      const key = pathname.split('/intelligence/correlator/patterns/')[1]
      if (!key) {
        sendJSON(res, 400, { error: 'correlation key is required' })
        return true
      }
      const patterns = correlator.getPatternsForKey(decodeURIComponent(key))
      sendJSON(res, 200, { patterns })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/trace
  if (method === 'GET' && pathname === '/intelligence/trace') {
    try {
      const sessionId = url.searchParams.get('sessionId')
      if (!sessionId) {
        sendJSON(res, 400, { error: 'sessionId query parameter is required' })
        return true
      }
      const turnIndex = url.searchParams.get('turnIndex')
      const limit = parseInt(url.searchParams.get('limit') || '5', 10)

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

      if (intel?.continuity) {
        try {
          const turns = await intel.continuity.getRecent(sessionId, limit)
          if (turnIndex !== null && turnIndex !== undefined) {
            const idx = parseInt(turnIndex, 10)
            trace.continuity = {
              targetIndex: idx,
              turns: turns.slice(Math.max(0, idx - 1), idx + 2),
              totalTurns: turns.length,
            }
          } else {
            trace.continuity = { turns, totalTurns: turns.length }
          }
        } catch {}
      }

      if (intel?.dialectic?.getRecent) {
        try {
          trace.dialectic = intel.dialectic.getRecent(sessionId, limit)
        } catch {}
      }

      if (intel?.memory) {
        try {
          const thread = intel.memory.getConversationWithThinking?.(sessionId, limit * 2) ?? []
          trace.injections = thread.filter(
            (e: any) => e.type === 'injection' || e.category === 'injection'
          )
          trace.archiveContext = thread.filter(
            (e: any) => e.type !== 'injection' && e.category !== 'injection'
          ).slice(0, limit)
        } catch {}
      }

      if (intel?.reflect?.unresolved) {
        try {
          trace.reflectPatterns = await intel.reflect.unresolved(5)
        } catch {}
      }

      if (daemon.intelligence?.subconscious) {
        try {
          const sub = daemon.intelligence.subconscious
          if (sub.getMentalModel) {
            trace.mentalModel = sub.getMentalModel(sessionId)
          }
        } catch {}
      }

      sendJSON(res, 200, trace)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/skills/metrics
  if (method === 'GET' && pathname === '/intelligence/skills/metrics') {
    try {
      const tracker = daemon.skillMetricsTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'skill metrics tracker not initialized' })
        return true
      }
      const days = parseInt(url.searchParams.get('days') || '7', 10)
      const summary = tracker.getMetricsSummary(days)
      sendJSON(res, 200, { summary })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/skills/details
  if (method === 'GET' && pathname === '/intelligence/skills/details') {
    try {
      const tracker = daemon.skillMetricsTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'skill metrics tracker not initialized' })
        return true
      }
      const skillName = url.searchParams.get('name')
      if (!skillName) {
        sendJSON(res, 400, { error: 'name query param required' })
        return true
      }
      const days = parseInt(url.searchParams.get('days') || '30', 10)
      const details = tracker.getSkillDetails(skillName, days)
      sendJSON(res, 200, { skillName, details })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /intelligence/skills/all
  if (method === 'GET' && pathname === '/intelligence/skills/all') {
    try {
      const tracker = daemon.skillMetricsTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'skill metrics tracker not initialized' })
        return true
      }
      const days = parseInt(url.searchParams.get('days') || '30', 10)
      const skills = tracker.getAllSkillsWithUsage(days)
      sendJSON(res, 200, { skills })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /intelligence/skills/prune
  if (method === 'POST' && pathname === '/intelligence/skills/prune') {
    try {
      const tracker = daemon.skillMetricsTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'skill metrics tracker not initialized' })
        return true
      }
      const body = await parseBody(req)
      const daysToKeep = body?.daysToKeep || 90
      tracker.pruneOldInvocations(daysToKeep)
      sendJSON(res, 200, { message: `Pruned invocations older than ${daysToKeep} days` })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
