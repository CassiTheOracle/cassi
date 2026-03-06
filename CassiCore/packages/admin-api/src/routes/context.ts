import { assembleContext } from '../intelligence/context-assembler.js'

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface ContextRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  parts: string[]
}

export async function handleContextRoutes(
  deps: ContextRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, parts } = deps

  // GET /context
  if (method === 'GET' && pathname === '/context') {
    try {
      // buildInjectPayload is passed from main admin-api
      sendJSON(res, 501, { error: 'GET /context requires buildInjectPayload function from main module' })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /context/assemble
  if (method === 'POST' && pathname === '/context/assemble') {
    try {
      const body = await parseBody(req)
      const { sessionId, query, include_history, memory_limit, files, extra_context, char_budget } = body || {}

      if (!sessionId) {
        sendJSON(res, 400, { error: 'missing sessionId' })
        return true
      }

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

      sendJSON(res, 200, {
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
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /context/:sessionId
  if (method === 'GET' && parts[0] === 'context' && parts.length === 2) {
    try {
      const sessionId = parts[1]
      const cm = (daemon.intelligence as any)?.contextManager
      if (!cm || typeof cm.getEffectiveContext !== 'function') {
        sendJSON(res, 503, { error: 'context manager not available' })
        return true
      }
      const result = await cm.getEffectiveContext(sessionId, { charBudget: 50000 })
      sendJSON(res, 200, {
        sessionId,
        globalContext: result?.globalContext,
        merged: result?.merged?.slice(0, 1000)
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /context/select — OpenCode context bridge: scored message selection
  if (method === 'POST' && pathname === '/context/select') {
    try {
      const body = await parseBody(req)
      const { sessionId, messages, query, charBudget } = body || {}

      if (!sessionId || !Array.isArray(messages)) {
        sendJSON(res, 400, { error: 'missing sessionId or messages array' })
        return true
      }

      const contextWindow = (daemon as any).contextWindow
      if (!contextWindow || typeof contextWindow.buildForOpenCode !== 'function') {
        sendJSON(res, 503, { error: 'IntelligentContextWindow not available' })
        return true
      }

      const result = await contextWindow.buildForOpenCode(
        sessionId,
        messages,
        query || '',
        charBudget,
      )

      sendJSON(res, 200, {
        messages: result.messages,
        stats: result.stats,
        crossSession: result.crossSession,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /context/score — index-only scored selection (preserves AI SDK types)
  if (method === 'POST' && pathname === '/context/score') {
    try {
      const body = await parseBody(req)
      const { sessionId, messages, query, charBudget } = body || {}

      if (!sessionId || !Array.isArray(messages)) {
        sendJSON(res, 400, { error: 'missing sessionId or messages[] digest array' })
        return true
      }

      const contextWindow = (daemon as any).contextWindow
      if (!contextWindow || typeof contextWindow.scoreForOpenCode !== 'function') {
        sendJSON(res, 503, { error: 'IntelligentContextWindow not available (scoreForOpenCode)' })
        return true
      }

      // Validate digest shape
      const digests = messages.map((m: any, i: number) => ({
        index: typeof m.index === 'number' ? m.index : i,
        role: m.role || 'user',
        text: typeof m.text === 'string' ? m.text : '',
        chars: typeof m.chars === 'number' ? m.chars : (typeof m.text === 'string' ? m.text.length : 0),
      }))

      const result = await contextWindow.scoreForOpenCode(
        sessionId,
        digests,
        query || '',
        charBudget,
      )

      sendJSON(res, 200, result)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /context/inject/:sessionId — aggregated cognitive signals for injection
  if (method === 'GET' && parts[0] === 'context' && parts[1] === 'inject' && parts.length === 3) {
    try {
      const sessionId = parts[2]
      const aggregator = (daemon.intelligence as any)?.injectionAggregator
      if (!aggregator || typeof aggregator.aggregateForExternal !== 'function') {
        sendJSON(res, 503, { error: 'InjectionAggregator not available' })
        return true
      }

      const injections = await aggregator.aggregateForExternal(sessionId)
      sendJSON(res, 200, { sessionId, parts: injections })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /context/index — index session messages for FTS scoring
  if (method === 'POST' && pathname === '/context/index') {
    try {
      const body = await parseBody(req)
      const { sessionId, messages } = body || {}

      if (!sessionId) {
        sendJSON(res, 400, { error: 'missing sessionId' })
        return true
      }

      const indexer = (daemon.intelligence as any)?.memory?.sessionIndexer
      if (!indexer || typeof indexer.indexMessages !== 'function') {
        sendJSON(res, 503, { error: 'SessionIndexer not available' })
        return true
      }

      // Index messages in OpenCode format (role + content text)
      const toIndex = Array.isArray(messages)
        ? messages.map((m: any, i: number) => ({
            role: m.role || 'user',
            content: typeof m.content === 'string'
              ? m.content
              : Array.isArray(m.content)
                ? m.content.filter((p: any) => p.type === 'text').map((p: any) => p.text || '').join('\n')
                : '',
            msgIdx: i,
          }))
        : []

      await indexer.indexMessages(sessionId, toIndex)
      const stats = indexer.getStats(sessionId)

      sendJSON(res, 200, { sessionId, indexed: toIndex.length, stats })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /context/assess/:sessionId — optimizer's recommendation for context pressure
  if (method === 'GET' && parts[0] === 'context' && parts[1] === 'assess' && parts.length === 3) {
    try {
      const sessionId = parts[2]
      const optimizer = (daemon.intelligence as any)?.optimizer
      
      // Default recommendation: let scored selection handle it
      let decision = 'select' as 'select' | 'summarize' | 'reset'

      if (optimizer && typeof optimizer.getSessionState === 'function') {
        const state = optimizer.getSessionState(sessionId)
        // If optimizer has flagged this session for summarization or reset
        if (state?.pendingAction === 'summarize') decision = 'summarize'
        else if (state?.pendingAction === 'context-reset') decision = 'reset'
      }

      sendJSON(res, 200, { sessionId, decision })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
