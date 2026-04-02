import { assembleContext } from '../intelligence/context-assembler.js'

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
  const { runtime, sendJSON, parseBody, parts } = deps

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

  // POST /context/compact/:sessionId — CassiCore-powered compaction
  //
  // Accepts the session's conversation history (as role/text pairs) and
  // produces a rich compaction summary using:
  //   1. Memory search (relevant past context)
  //   2. Cognitive signals (thinker insights, subconscious patterns)
  //   3. LLM summarization via qwen3.5-plus (alibaba-coding, 1M context)
  //
  // Returns { summary: string } on success.
  // Falls back gracefully if ModelPool, memory, or cognitive signals are unavailable.
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

      const modelPool = runtime.getLumenModelPool()
      if (!modelPool || typeof modelPool.acquire !== 'function') {
        sendJSON(res, 503, { error: 'ModelPool not available — CassiCore compaction unavailable' })
        return true
      }

      // Index all messages NOW, before the LLM summary replaces the history.
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

      let memoryContext = ''
      try {
        const memory = runtime.getIntelligence()?.memory as any
        if (memory && typeof memory.search === 'function') {
          // Extract a query from the last user message
          const lastUser = [...messages].reverse().find((m: any) => m.role === 'user')
          const query = typeof lastUser?.content === 'string'
            ? lastUser.content.slice(0, 200)
            : (Array.isArray(lastUser?.content)
              ? lastUser.content.filter((p: any) => p.type === 'text').map((p: any) => p.text || '').join(' ').slice(0, 200)
              : 'session context')

          const results = await memory.search(query, { limit: 6, minScore: 0.25 })
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

      // Iterate newest → oldest so that recent context is preserved within the
      // 80K char budget. Older turns are truncated first, not newer ones.
      // (Previous approach iterated oldest → newest and silently lost the end
      //  of the conversation — the most relevant part.)
      const CONV_CHAR_LIMIT = 80_000
      const segments: string[] = []
      let totalChars = 0
      for (let i = messages.length - 1; i >= 0; i--) {
        const m = messages[i]
        const role = (m.role ?? 'user').toUpperCase()
        let content = ''
        if (typeof m.content === 'string') {
          content = m.content
        } else if (Array.isArray(m.content)) {
          content = m.content
            .filter((p: any) => p.type === 'text')
            .map((p: any) => p.text || '')
            .join('\n')
        }
        const segment = `[${role}]: ${content}\n---\n`
        if (totalChars + segment.length > CONV_CHAR_LIMIT) {
          // Older messages don't fit — note the truncation at the top
          segments.unshift('[... older context truncated — recent messages preserved above ...]\n')
          break
        }
        segments.unshift(segment)
        totalChars += segment.length
      }
      const conversationText = segments.join('')

      const contextSections: string[] = []
      if (memoryContext) contextSections.push(memoryContext)
      if (cognitiveContext) {
        contextSections.push(
          '### Cognitive Signals\n' +
          'The following signals were active in this session. Preserve any insights relevant to the work:\n' +
          cognitiveContext
        )
      }
      const contextBlock = contextSections.length > 0
        ? `\n\n## CassiCore Context\n${contextSections.join('\n\n')}\n\n---`
        : ''

      const systemPrompt =
        'You are a context compaction assistant. Your job is to produce a detailed, ' +
        'structured summary of the conversation above that will serve as the starting ' +
        'context for the SAME agent continuing the SAME task. The summary replaces the ' +
        'full conversation history, so it must capture everything needed to continue ' +
        'working without loss of direction or context.\n\n' +
        'Structure your summary using exactly this template:\n' +
        '---\n' +
        '## Goal\n' +
        '[What goal(s) is the user trying to accomplish?]\n\n' +
        '## Instructions\n' +
        '- [Important instructions the user gave that are still relevant]\n' +
        '- [Any plan, spec, or approach being followed]\n\n' +
        '## Discoveries\n' +
        '[Notable things learned during the conversation that the next agent needs to know]\n\n' +
        '## Accomplished\n' +
        '[What work has been completed, what is in progress, what remains]\n\n' +
        '## Relevant Files / Directories\n' +
        '[Structured list of files read, edited, or created that pertain to the task]\n\n' +
        '## Decisions Made\n' +
        '[Architectural, design, or implementation decisions made during the session]\n' +
        '---\n\n' +
        'Be thorough and precise. The summary will be the ONLY context the next agent has.'

      const userMessage =
        `Here is the conversation to compact:${contextBlock}\n\n` +
        `## Conversation\n${conversationText}\n\n` +
        `Produce the compaction summary now.`

      const COMPACTION_MODEL = 'qwen3.5-plus'
      const COMPACTION_PROVIDER = 'alibaba-coding'

      let handle: any
      try {
        handle = await modelPool.acquire('compaction', undefined, sessionId, {
          provider: COMPACTION_PROVIDER,
          model: COMPACTION_MODEL,
        })
      } catch (acquireErr) {
        sendJSON(res, 503, { error: `Failed to acquire model ${COMPACTION_PROVIDER}/${COMPACTION_MODEL}: ${String(acquireErr)}` })
        return true
      }

      try {
        const result = await handle.complete(
          [{ role: 'user', content: userMessage }],
          {
            model: COMPACTION_MODEL,
            maxTokens: 4000,
            temperature: 0.2,
            thinking: 'none',
            systemPrompt,
            source: 'context-compaction',
            trigger: 'compact',
            sessionId,
            allowConcurrent: true,
            timeoutMs: 60_000,
          }
        )

        const summary = (result.response ?? '').trim()
        if (!summary) {
          sendJSON(res, 500, { error: 'LLM returned empty summary' })
          return true
        }

        // Persisting the summary lets cassi_enrich surface it in later
        // sessions, so compacted conversations are not truly forgotten.
        try {
          const memory = runtime.getIntelligence()?.memory as any
          if (memory && typeof memory.store === 'function') {
            await memory.store({
              content: `[Compaction summary — session ${sessionId}]\n\n${summary}`,
              type: 'conversation',
              tags: ['compaction', 'session', sessionId],
            })
          }
        } catch {
          // Non-fatal — memory store failure should not fail the compaction
        }

        sendJSON(res, 200, {
          sessionId,
          summary,
          model: `${COMPACTION_PROVIDER}/${COMPACTION_MODEL}`,
          tokensUsed: result.tokensUsed ?? 0,
          hasMemory: !!memoryContext,
          hasCognitive: !!cognitiveContext,
        })
        return true
      } finally {
        try { handle.release() } catch { /* ignore */ }
      }
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
