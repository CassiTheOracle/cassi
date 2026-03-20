import { assembleContext } from '../intelligence/context-assembler.js'

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

import type { AdminRuntimeFacade } from './runtime.js'

export interface DialecticRoutesDeps {
  runtime: AdminRuntimeFacade
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  parts: string[]
}

export async function handleDialecticRoutes(
  deps: DialecticRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { runtime, sendJSON, parseBody, url, parts } = deps

  if (parts[0] !== 'dialectic') return false

  // GET /dialectic/:sessionId/history
  if (parts.length === 3 && parts[2] === 'history' && method === 'GET') {
    const sessionId = parts[1]
    const limit = parseInt(url.searchParams.get('limit') || '10', 10)
    try {
      const history = await runtime.getIntelligence()?.dialectic?.getRecent?.(sessionId, limit) ?? []
      sendJSON(res, 200, { sessionId, history })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /dialectic/:sessionId/stats
  if (parts.length === 3 && parts[2] === 'stats' && method === 'GET') {
    const sessionId = parts[1]
    try {
      const stats = await runtime.getIntelligence()?.dialectic?.getStats?.(sessionId) ?? {
        totalTurns: 0, signalsGenerated: 0, signalsInjected: 0, avgLatencyMs: 0, totalCostUsd: 0
      }
      sendJSON(res, 200, { sessionId, stats })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /dialectic/:sessionId/think
  if (parts.length === 3 && parts[2] === 'think' && method === 'POST') {
    try {
      const sessionId = parts[1]
      const body = await parseBody(req)
      const { query, depth, include_history, memory_limit, files, extra_context, wait, structured, include_raw } = body || {}

      const ctxObj = await assembleContext(
        {
          memory: runtime.getIntelligence()?.memory,
          sessionManager: runtime.getLegacySessionStore(),
          getPipeline: () => runtime.getPipeline(),
          logger: runtime.logger,
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
      const dialectic = runtime.getIntelligence()?.dialectic
      if (!dialectic) {
        sendJSON(res, 503, { error: 'dialectic not available' })
        return true
      }

      const promise = dialectic.processTurn(sessionId || `admin-session-${Date.now()}`, turnId, query || '', ctxObj)
      if (wait === false) {
        promise.catch((e: any) => runtime.logger?.warn?.('admin: background dialectic failed', { error: String(e) }))
        sendJSON(res, 200, { ok: true, message: 'Dialectic triggered (async)' })
        return true
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
      sendJSON(res, 200, out)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /dialectic/:sessionId/stream
  if (parts.length === 3 && parts[2] === 'stream' && method === 'GET') {
    const acceptHeader = req.headers['accept'] || ''
    if (acceptHeader.includes('text/html')) {
      try {
        const htmlPath = new URL('../../../../public/dialectic-observatory.html', import.meta.url)
        const fs = await import('node:fs')
        const html = fs.readFileSync(htmlPath, 'utf8')
        res.writeHead(200, { 'Content-Type': 'text/html' })
        res.end(html)
        return true
      } catch (err) {
        sendJSON(res, 500, { error: 'Dashboard not found' })
        return true
      }
    }
    sendJSON(res, 426, { error: 'WebSocket upgrade required' })
    return true
  }

  return false
}
