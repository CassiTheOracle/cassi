import { assembleContext } from '../vendor/core/intelligence/context-assembler.js'
import { SmartCompactionEngine } from '@cassicore/thalamus'

import type { AdminRuntimeFacade } from './runtime.js'

import type { ILogger } from '@cassicore/foundation'
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
 * @dep calls: sendJSON, parseBody, getEffectiveContext, assembleContext, complete [+11]
 * @dep flows: HandleContextRoutes → PrepareStatements (1/6), HandleContextRoutes → ContentLength (1/5), HandleContextRoutes → Kv_get (1/4) [+2]
 * @dep module: Intelligence
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

  // GET /context/inject/:sessionId — REMOVED: InjectionAggregator deleted.
  // Use /context/thalamus or /context/workspace for injection assembly.
  if (method === 'GET' && parts[0] === 'context' && parts[1] === 'inject' && parts.length === 3) {
    sendJSON(res, 410, { error: 'Deprecated: InjectionAggregator removed. Use /context/thalamus instead.' })
    return true
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

      // WHY: Always return "select" — auto-compaction (LLM summarization)
      // is disabled. Scored selection in the message transform hook handles
      // all context pressure by dropping low-value messages. Manual /compact
      // remains available for explicit user requests.
      sendJSON(res, 200, { sessionId, decision: 'select' })
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

      // REMOVED: cognitive signals via injectionAggregator — InjectionAggregator deleted.
      let cognitiveContext = ''

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
      const COMPACTION_MODEL = 'gpt-5-mini'
      const COMPACTION_PROVIDER = 'github-copilot'
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

  // POST /context/chunks/store — batch store collapsed chunk content
  //
  // Called by OpenCode when the agent collapses or removes chunks.
  // Stores full content in the KV store so it can be retrieved later
  // via context_expand.
  if (method === 'POST' && pathname === '/context/chunks/store') {
    try {
      const body = await parseBody(req)
      const { sessionId, chunks } = body || {}

      if (!sessionId || !Array.isArray(chunks)) {
        sendJSON(res, 400, { error: 'missing sessionId or chunks array' })
        return true
      }

      const memory = runtime.getIntelligence()?.memory as any
      if (!memory?.kv_set) {
        sendJSON(res, 503, { error: 'KV store not available' })
        return true
      }

      let stored = 0
      for (const chunk of chunks) {
        if (!chunk.id || !chunk.content) continue
        await memory.kv_set(`chunk:${sessionId}:${chunk.id}`, {
          content: chunk.content,
          role: chunk.role || 'unknown',
          type: chunk.type || 'text',
          toolName: chunk.toolName,
          tokens: chunk.tokens || 0,
          preview: chunk.preview || '',
          storedAt: Date.now(),
        })
        stored++
      }

      // Store chunk manifest index for listing
      const existingIndex = await memory.kv_get(`chunk-index:${sessionId}`) as string[] | undefined
      const index = new Set(existingIndex || [])
      for (const chunk of chunks) {
        if (chunk.id) index.add(chunk.id)
      }
      await memory.kv_set(`chunk-index:${sessionId}`, [...index])

      sendJSON(res, 200, { sessionId, stored })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /context/chunks/:sessionId/:chunkId — retrieve a single chunk's content
  if (method === 'GET' && parts[0] === 'context' && parts[1] === 'chunks' && parts.length === 4) {
    try {
      const sessionId = parts[2]
      const chunkId = parts[3]

      const memory = runtime.getIntelligence()?.memory as any
      if (!memory?.kv_get) {
        sendJSON(res, 503, { error: 'KV store not available' })
        return true
      }

      const data = await memory.kv_get(`chunk:${sessionId}:${chunkId}`)
      if (!data) {
        sendJSON(res, 404, { error: 'chunk not found' })
        return true
      }

      sendJSON(res, 200, { sessionId, chunkId, ...data })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /context/chunks/retrieve — batch retrieve multiple chunks
  if (method === 'POST' && pathname === '/context/chunks/retrieve') {
    try {
      const body = await parseBody(req)
      const { sessionId, chunkIds } = body || {}

      if (!sessionId || !Array.isArray(chunkIds)) {
        sendJSON(res, 400, { error: 'missing sessionId or chunkIds array' })
        return true
      }

      const memory = runtime.getIntelligence()?.memory as any
      if (!memory?.kv_get) {
        sendJSON(res, 503, { error: 'KV store not available' })
        return true
      }

      const results: Array<{ id: string; content: string; role: string; type: string; toolName?: string }> = []
      for (const id of chunkIds) {
        const data = await memory.kv_get(`chunk:${sessionId}:${id}`) as any
        if (data) {
          results.push({
            id,
            content: data.content,
            role: data.role,
            type: data.type,
            toolName: data.toolName,
          })
        }
      }

      sendJSON(res, 200, { sessionId, chunks: results, found: results.length, requested: chunkIds.length })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /context/chunks/:sessionId — list all stored chunks for a session
  if (method === 'GET' && parts[0] === 'context' && parts[1] === 'chunks' && parts.length === 3) {
    try {
      const sessionId = parts[2]

      const memory = runtime.getIntelligence()?.memory as any
      if (!memory?.kv_get) {
        sendJSON(res, 503, { error: 'KV store not available' })
        return true
      }

      const index = await memory.kv_get(`chunk-index:${sessionId}`) as string[] | undefined
      if (!index || index.length === 0) {
        sendJSON(res, 200, { sessionId, chunks: [], count: 0 })
        return true
      }

      sendJSON(res, 200, { sessionId, chunkIds: index, count: index.length })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // DELETE /context/chunks/:sessionId — clean up all stored chunks for a session
  if (method === 'DELETE' && parts[0] === 'context' && parts[1] === 'chunks' && parts.length === 3) {
    try {
      const sessionId = parts[2]

      const memory = runtime.getIntelligence()?.memory as any
      if (!memory?.kv_get || !memory?.kv_del) {
        sendJSON(res, 503, { error: 'KV store not available' })
        return true
      }

      const index = await memory.kv_get(`chunk-index:${sessionId}`) as string[] | undefined
      let deleted = 0
      if (index) {
        for (const id of index) {
          try {
            await memory.kv_del(`chunk:${sessionId}:${id}`)
            deleted++
          } catch { /* best-effort cleanup */ }
        }
        await memory.kv_del(`chunk-index:${sessionId}`)
      }

      sendJSON(res, 200, { sessionId, deleted })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /context/inject — Hermes memory-provider injection
  // Searches MnemicField via kindling, filters/deduplicates/formats results
  // for direct <memory-context> injection into the Hermes agent loop.
  if (method === 'POST' && pathname === '/context/inject') {
    try {
      const body = await parseBody(req)
      const query = typeof body?.query === 'string' ? body.query : ''
      const sessionId = typeof body?.sessionId === 'string' ? body.sessionId : ''
      const limit = typeof body?.limit === 'number' ? body.limit : 5

      if (!query || !sessionId) {
        sendJSON(res, 400, { error: 'query and sessionId required' })
        return true
      }

      const thalamus = runtime.getIntelligence()?.registry?.get?.('thalamus')
      if (!thalamus?.injectForMemory) {
        sendJSON(res, 503, { error: 'Thalamus not available' })
        return true
      }

      const result = await thalamus.injectForMemory(query, sessionId, limit)
      sendJSON(res, 200, { ok: true, ...result })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
