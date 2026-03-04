import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import { assembleContext } from '../intelligence/context-assembler.js'

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

  return false
}
