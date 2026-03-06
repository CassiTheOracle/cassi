import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface ObservabilityRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  url: URL
  pathname: string
}

export async function handleObservabilityRoutes(
  deps: ObservabilityRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, sendJSON, url, pathname } = deps

  // GET /observability/prompts/stream
  if (method === 'GET' && pathname === '/observability/prompts/stream') {
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
        const name = String(eventName).replace(/[:]/g, '.')
        res.write(`event: ${name}\n`)
        res.write(`data: ${JSON.stringify(payload)}\n\n`)
      } catch (err) { /* SSE write failures are expected when clients disconnect — safe to ignore */ }
    }

    const matchesSessionFilter = (evSessionId: any) => {
      if (!sessionFilter) return true
      if (!evSessionId) return false
      const s = String(evSessionId)
      if (s === sessionFilter) return true
      if (s === `sess_${sessionFilter}`) return true
      if (s.startsWith(`sess_${sessionFilter}`)) return true
      if (s.includes(sessionFilter)) return true
      if (s.startsWith('sess_') && s.slice(5) === sessionFilter) return true
      return false
    }

    const onProviderStart = (e: any) => {
      try {
        if (providerFilter && e.providerId !== providerFilter) return
        if (!matchesSessionFilter(e.sessionId)) return
        sendEvent('provider:request_start', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, model: e.model, messageCount: e.messageCount, timestamp: Date.now() })
      } catch { /* individual event failures should not crash the SSE stream */ }
    }
    const onProviderEnd = (e: any) => {
      try {
        if (providerFilter && e.providerId !== providerFilter) return
        if (!matchesSessionFilter(e.sessionId)) return
        sendEvent('provider:request_end', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, tokensUsed: e.tokensUsed, durationMs: e.durationMs, error: e.error || null, timestamp: Date.now() })
      } catch { /* individual event failures should not crash the SSE stream */ }
    }
    const onProviderError = (e: any) => {
      try {
        if (providerFilter && e.providerId !== providerFilter) return
        if (!matchesSessionFilter(e.sessionId)) return
        sendEvent('provider:request_error', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, error: e.error, consecutiveErrors: e.consecutiveErrors, timestamp: Date.now() })
      } catch { /* individual event failures should not crash the SSE stream */ }
    }
    const onProviderDedup = (e: any) => {
      try {
        if (providerFilter && e.providerId !== providerFilter) return
        if (!matchesSessionFilter(e.sessionId)) return
        sendEvent('provider:deduplicated', e)
      } catch { /* individual event failures should not crash the SSE stream */ }
    }
    const onProviderRateLimited = (e: any) => {
      try {
        if (providerFilter && e.providerId !== providerFilter) return
        if (!matchesSessionFilter(e.sessionId)) return
        sendEvent('provider:rate_limited', e)
      } catch { /* individual event failures should not crash the SSE stream */ }
    }
    const onProviderErrorReset = (e: any) => {
      try {
        if (providerFilter && e.providerId !== providerFilter) return
        sendEvent('provider:error_reset', { providerId: e.providerId, timestamp: Date.now() })
      } catch { /* individual event failures should not crash the SSE stream */ }
    }
    const onProviderTimeout = (e: any) => {
      try {
        if (providerFilter && e.providerId !== providerFilter) return
        if (!matchesSessionFilter(e.sessionId)) return
        sendEvent('provider:request_timeout', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, timeoutMs: e.timeoutMs, timestamp: Date.now() })
      } catch { /* individual event failures should not crash the SSE stream */ }
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
      } catch (err) { /* SSE write failures are expected when clients disconnect — safe to ignore */ }
    }

    const onTurnStart = (e: any) => {
      try {
        if (sessionFilter && String(e.sessionId) !== sessionFilter) return
        sendEvent('turn.start', { sessionId: e.sessionId, message: e.message, timestamp: e.timestamp || Date.now() })
      } catch { /* individual event failures should not crash the SSE stream */ }
    }
    const onTurnEnd = (e: any) => {
      try {
        if (sessionFilter && String(e.sessionId) !== sessionFilter) return
        sendEvent('turn.end', { sessionId: e.sessionId, response: e.response, durationMs: e.durationMs, timestamp: Date.now() })
      } catch { /* individual event failures should not crash the SSE stream */ }
    }
    const onDialecticStream = (e: any) => {
      try {
        if (sessionFilter && String(e.sessionId) !== sessionFilter) return
        sendEvent('dialectic.stream', e)
      } catch { /* individual event failures should not crash the SSE stream */ }
    }

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

    const ping = setInterval(() => {
      try { res.write(': ping\n\n') } catch { clearInterval(ping) }
    }, 15_000)
    try { (ping as any).unref?.() } catch { /* unref not available on all platforms — safe to ignore */ }

    req.on('close', () => {
      clearInterval(ping)
      try { daemon.bus.off('provider:request_start', onProviderStart) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('provider:request_end', onProviderEnd) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('provider:request_error', onProviderError) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('provider:deduplicated', onProviderDedup) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('provider:rate_limited', onProviderRateLimited) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('provider:error_reset', onProviderErrorReset) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('provider:request_timeout', onProviderTimeout) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('worker:message', onWorkerMessage) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('turn:start', onTurnStart) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('turn:end', onTurnEnd) } catch { /* handler may not be registered */ }
      try { daemon.bus.off('dialectic:stream', onDialecticStream) } catch { /* handler may not be registered */ }
    })

    return true
  }

  return false
}
