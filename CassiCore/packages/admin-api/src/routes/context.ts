import { assembleContext } from '../intelligence/context-assembler.js'
import { SmartCompactionEngine } from '../intelligence/smart-compaction.js'

import type { AdminRuntimeFacade } from './runtime.js'

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface ContextRoutesDeps {
  runtime: AdminRuntimeFacade
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  parts: string[]
}

/**
 * @dep callers: handler (core/admin-api.ts)
 * @dep calls: getSessionState, scoreForOpenCode, buildForOpenCode, indexSession, getContextWindow [+11]
 * @dep flows: HandleContextRoutes → CognitiveKeyForSession (1/4), HandleContextRoutes → KeyForSession (1/4), HandleContextRoutes → Kv_get (1/4) [+2]
 * @dep module: Context-window
 * @dep risk: HIGH | 1 caller, 5 flows, 1 module
 */

export async function handleContextRoutes(
  deps: ContextRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { runtime, logger, sendJSON, parseBody, parts } = deps

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
      const cm = runtime.getIntelligence()?.contextManager as any
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

      const contextWindow = runtime.getContextWindow()
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

      const contextWindow = runtime.getContextWindow()
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
      const aggregator = runtime.getIntelligence()?.injectionAggregator as any
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

      const indexer = runtime.getIntelligence()?.memory?.sessionIndexer as any
      if (!indexer || typeof indexer.indexSession !== 'function') {
        sendJSON(res, 503, { error: 'SessionIndexer not available' })
        return true
      }

      // Index messages in OpenCode format (role + content text)
      const toIndex = Array.isArray(messages)
        ? messages.map((m: any) => ({
            role: m.role || 'user',
            content: typeof m.content === 'string'
              ? m.content
              : Array.isArray(m.content)
                ? m.content.filter((p: any) => p.type === 'text').map((p: any) => p.text || '').join('\n')
                : '',
          }))
        : []

      const label = indexer.indexSession(sessionId, toIndex)
      const stats = indexer.getStats(sessionId)

      sendJSON(res, 200, { sessionId, label, indexed: toIndex.length, stats })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /context/assess/:sessionId — optimizer's recommendation for context pressure
  // Query params: tokensUsed (number), contextLimit (number)
  if (method === 'GET' && parts[0] === 'context' && parts[1] === 'assess' && parts.length === 3) {
    try {
      const sessionId = parts[2]
      const optimizer = runtime.getIntelligence()?.optimizer as any

      // Parse optional token pressure hints from query string
      const url = new URL(req.url ?? '/', 'http://localhost')
      const tokensUsed = parseInt(url.searchParams.get('tokensUsed') ?? '0', 10)
      const contextLimit = parseInt(url.searchParams.get('contextLimit') ?? '0', 10)

      // Default recommendation: let scored selection handle it
      let decision = 'select' as 'select' | 'summarize' | 'reset'

      if (optimizer && typeof optimizer.getSessionState === 'function') {
        const state = optimizer.getSessionState(sessionId)
        // If optimizer has explicitly flagged this session
        if (state?.pendingAction === 'summarize') decision = 'summarize'
        else if (state?.pendingAction === 'context-reset') decision = 'reset'
      }

      // If decision is still 'select', check token pressure.
      // If we're at ≥75% capacity, scored selection alone can't recover — compact.
      // (Lowered from 85% to give compaction time to run before the hard limit.)
      if (decision === 'select' && tokensUsed > 0 && contextLimit > 0) {
        const usageRatio = tokensUsed / contextLimit
        if (usageRatio >= 0.75) {
          decision = 'summarize'
        }
      }

      sendJSON(res, 200, { sessionId, decision })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /context/compact/:sessionId — Smart CassiCore-powered compaction
  //
  // Uses the SmartCompactionEngine to intelligently process the conversation:
  //   1. Scores every message by importance (recency, errors, tool impact, decisions)
  //   2. Clusters messages by topic (shared files, tools, context)
  //   3. Keeps high-importance clusters verbatim
  //   4. Summarizes medium-importance clusters using an LLM
  //   5. Prunes low-importance messages (preserving key references)
  //   6. Enriches with CassiCore cognitive signals + memory search
  //
  // Returns { summary, strategy, stats } on success.
  // Falls back to heuristic-only mode if ModelPool is unavailable.
  if (method === 'POST' && parts[0] === 'context' && parts[1] === 'compact' && parts.length === 3) {
    try {
      const sessionId = parts[2]
      const body = await parseBody(req)
      const { messages } = body || {}

      if (!sessionId) {
        sendJSON(res, 400, { error: 'missing sessionId' })
        return true
      }

      if (!Array.isArray(messages) || messages.length === 0) {
        sendJSON(res, 400, { error: 'messages array is required and must not be empty' })
        return true
      }

      // Index all messages NOW, before compaction replaces the history.
      // This allows cassi_enrich / FTS search to retrieve content from
      // compacted sessions even after their history is summarised away.
      try {
        const indexer = runtime.getIntelligence()?.memory?.sessionIndexer as any
        if (indexer && typeof indexer.indexSession === 'function') {
          const toIndex = messages
            .map((m: any) => ({
              role: (m.role || 'user') as string,
              content: typeof m.content === 'string'
                ? m.content
                : Array.isArray(m.content)
                  ? m.content.filter((p: any) => p.type === 'text').map((p: any) => p.text || '').join('\n')
                  : '',
            }))
            .filter((m: any) => m.content.length > 0)
          if (toIndex.length > 0) {
            await indexer.indexSession(sessionId, toIndex)
          }
        }
      } catch {
        // Non-fatal — archive is best-effort; compaction proceeds regardless
      }

      // Gather CassiCore cognitive signals
      let cognitiveContext = ''
      try {
        const aggregator = runtime.getIntelligence()?.injectionAggregator as any
        if (aggregator && typeof aggregator.aggregateForExternal === 'function') {
          const externalParts = await aggregator.aggregateForExternal(sessionId)
          if (Array.isArray(externalParts) && externalParts.length > 0) {
            cognitiveContext = externalParts
              .filter((p: any) => p.content && p.charCount > 0)
              .map((p: any) => String(p.content))
              .join('\n\n')
          }
        }
      } catch {
        // Cognitive signals are optional — continue without them
      }

      // Search memory for relevant past context
      let memoryContext = ''
      let lastUserQuery = ''
      try {
        const memory = runtime.getIntelligence()?.memory as any
        if (memory && typeof memory.search === 'function') {
          const lastUser = [...messages].reverse().find((m: any) => m.role === 'user')
          lastUserQuery = typeof lastUser?.content === 'string'
            ? lastUser.content.slice(0, 200)
            : (Array.isArray(lastUser?.content)
              ? lastUser.content.filter((p: any) => p.type === 'text').map((p: any) => p.text || '').join(' ').slice(0, 200)
              : 'session context')

          const results = await memory.search(lastUserQuery, { limit: 6, minScore: 0.25 })
          if (results && results.length > 0) {
            const items = results.map((r: any) => {
              const score = Math.round((r.score ?? 0) * 100)
              return `- (${score}%) ${String(r.entry?.content ?? r.content ?? '').slice(0, 400)}`
            })
            memoryContext = `### Relevant Memory\n${items.join('\n')}`
          }
        }
      } catch {
        // Memory search is optional — continue without it
      }

      // Build the LLM-powered summarizer callback for medium-importance clusters
      const COMPACTION_MODEL = 'qwen3.5-plus'
      const COMPACTION_PROVIDER = 'alibaba-coding'
      let summarizer: ((content: string, instruction: string) => Promise<string>) | undefined
      let modelLabel = 'heuristic-only'

      const modelPool = runtime.getLumenModelPool()
      if (modelPool && typeof modelPool.acquire === 'function') {
        summarizer = async (content: string, instruction: string): Promise<string> => {
          let handle: any
          try {
            handle = await modelPool.acquire('compaction', undefined, sessionId, {
              provider: COMPACTION_PROVIDER,
              model: COMPACTION_MODEL,
            })
          } catch {
            // HOW: If model acquisition fails, return empty string — the engine
            // falls back to heuristic summarization automatically.
            return ''
          }
          try {
            const result = await handle.complete(
              [{ role: 'user', content: `${instruction}\n\n---\n\n${content}` }],
              {
                model: COMPACTION_MODEL,
                maxTokens: 2_000,
                temperature: 0.2,
                thinking: 'none',
                reasoning: 'none',
                systemPrompt: 'You are a concise summarizer. Follow the instruction exactly. Output only the summary, no preamble or reasoning.',
                source: 'smart-compaction-cluster',
                trigger: 'compact',
                sessionId,
                allowConcurrent: true,
                timeoutMs: 30_000,
              }
            )
            // HOW: Strip thinking/reasoning artifacts that some models embed in
            // response text despite thinking: 'none' (e.g. Qwen's bold headers).
            return SmartCompactionEngine.stripThinkingArtifacts((result.response ?? '').trim())
          } finally {
            try { handle.release() } catch { /* ignore */ }
          }
        }
        modelLabel = `${COMPACTION_PROVIDER}/${COMPACTION_MODEL}`
      }

      // Run the SmartCompactionEngine
      const engine = new SmartCompactionEngine(
        {
          outputCharBudget: 80_000,
          preserveRecentCount: 8,
          minMessagesForCompaction: 12,
          summarizer,
        },
        logger,
      )

      const compactionResult = await engine.compact(messages, {
        memoryContext,
        cognitiveContext,
        lastUserQuery,
      })

      if (!compactionResult.summary) {
        sendJSON(res, 500, { error: 'Smart compaction produced empty summary' })
        return true
      }

      // Persist the summary to memory so cassi_enrich surfaces it in later sessions
      try {
        const memory = runtime.getIntelligence()?.memory as any
        if (memory && typeof memory.store === 'function') {
          await memory.store({
            content: `[Compaction summary — session ${sessionId}]\n\n${compactionResult.summary.slice(0, 8000)}`,
            type: 'conversation',
            tags: ['compaction', 'session', sessionId],
          })
        }
      } catch {
        // Non-fatal — memory store failure should not fail the compaction
      }

      sendJSON(res, 200, {
        sessionId,
        summary: compactionResult.summary,
        model: modelLabel,
        strategy: compactionResult.strategy,
        stats: {
          keptVerbatim: compactionResult.keptVerbatim,
          summarized: compactionResult.summarized,
          pruned: compactionResult.pruned,
          durationMs: compactionResult.durationMs,
        },
        hasMemory: !!memoryContext,
        hasCognitive: !!cognitiveContext,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
