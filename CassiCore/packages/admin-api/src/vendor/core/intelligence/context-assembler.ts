import fs from 'node:fs'
import path from 'node:path'

import { CONTEXT_SETTINGS } from '@cassicore/foundation'

import { getEmbeddingService } from '@cassicore/embeddings'
import { getRerankerService } from '@cassicore/embeddings'

import type { IMemory } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
import type { ISessionManager } from '@cassicore/foundation'
import type { TurnPipeline } from './turn-pipeline.js'

export interface ContextAssemblerDeps {
  memory?: IMemory
  mnemicField?: import('@cassicore/mnemic-field').MnemicField
  sessionManager?: ISessionManager
  getPipeline?: () => TurnPipeline | undefined
  logger?: ILogger
}

export interface AssembleOpts {
  sessionId?: string
  query?: string
  includeHistory?: boolean
  memoryLimit?: number
  files?: string[]
  extra?: string
  workingDir?: string
  allowedPaths?: string[]
  // Approximate character budget for the assembled context (best-effort)
  charBudget?: number
}

export interface AssembledContext {
  recentMemories: string[]
  availableTools: string[]
  sessionHistory: string[]
  files: Array<{ path: string; content: string }>
  extraContext?: string
  taskGuide?: string
  sessionSummary?: string
  // Indicates whether the assembler trimmed content to satisfy budget
  trimmed?: boolean
  // Optional semantic hits produced by embedding-based ranking
  semanticHits?: Array<{ source: string; path?: string; text: string; score: number }>
}

/**
 * Context Assembler — improved PoC
 * - Collects recent memories, session history, available tools, and file snippets
 * - Best-effort trimming to respect a charBudget (pressure-aware)
 * - Embedding-based ranking via shared EmbeddingService + RerankerService
 * - LLM-backed summarizer with improved prompt + heuristic fallback
 * - Safe, defensive: never throws on optional subsystem failures
 * @dep callers: getEffectiveContext (core/intelligence/context-manager.ts), handleDialecticRoutes (core/admin-api/dialectic.ts), handleContextRoutes (core/admin-api/context.ts), makeThinkHandler (core/tools/implementations/think.ts), execute (core/intelligence/flux-team/topology-engine.ts) [+2]
 * @dep calls: getEmbeddingService, getRerankerService, rerank, cosineSimilarity [+7]
 * @dep flows: AssembleContext → CheckNvidiaSmi (1/5), AssembleContext → CheckRocmSmi (1/5), AssembleContext → IsHealthy (1/6) [+1]
 * @dep module: Memory
 * @dep risk: HIGH | 7 callers, 4 flows, 1 module
 */
export async function assembleContext(deps: ContextAssemblerDeps, opts: AssembleOpts = {}, signal?: AbortSignal): Promise<AssembledContext> {
  const logger = deps.logger
  const sessionId = opts.sessionId
  const q = (opts.query || '').trim()
  const includeHistory = opts.includeHistory ?? true
  const memoryLimit = opts.memoryLimit ?? 5
  const files = opts.files || []
  const extra = opts.extra || ''
  const workingDir = opts.workingDir || process.cwd()
  const allowedPaths = opts.allowedPaths || []
  const charBudget = typeof opts.charBudget === 'number' ? opts.charBudget : CONTEXT_SETTINGS.assemblerCharBudget

  const assembled: AssembledContext = {
    recentMemories: [],
    availableTools: [],
    sessionHistory: [],
    files: [],
  }

  const approxChars = () => {
    let total = 0
    total += assembled.recentMemories.reduce((s, r) => s + (typeof r === 'string' ? r.length : 0), 0)
    total += assembled.sessionHistory.reduce((s, r) => s + (typeof r === 'string' ? r.length : 0), 0)
    total += assembled.files.reduce((s, f) => s + (typeof f.content === 'string' ? f.content.length : 0), 0)
    if (assembled.extraContext) total += assembled.extraContext.length
    if (assembled.taskGuide) total += assembled.taskGuide.length
    total += assembled.availableTools.join(',').length
    return total
  }

  // 1) Primary memory retrieval (Mnemic Field first, classic memory fallback)
  if (deps.mnemicField && q) {
    try {
      const hits = await deps.mnemicField.retrieve(q, { complexity: 'normal', limit: memoryLimit })
      for (const h of hits) {
        if (h.nodeType === 'source_file') {
          // Code engrams: include as file context with path metadata
          const filePath = (h.metadata as Record<string, unknown>)?.filePath as string | undefined
          if (filePath) {
            assembled.files.push({
              path: filePath,
              content: (h.content || '').slice(0, 4000),
            })
          }
        } else {
          assembled.recentMemories.push((h.content || '').slice(0, 1200))
        }
      }
    } catch (err) {
      logger?.warn?.('context-assembler: mnemicField.retrieve failed', { error: String(err) })
    }
  }
  if (assembled.recentMemories.length === 0 && deps.memory) {
    try {
      const query = q || ''
      const results = await deps.memory.search(query, { limit: memoryLimit })
      assembled.recentMemories = (results || []).map(r => (r.entry.content || '').slice(0, 1200))
    } catch (err) {
      logger?.warn?.('context-assembler: memory.search failed', { error: String(err) })
    }
  }

  // 1b) Semantic Recall of old session turns (if available)
  if (deps.memory && typeof (deps.memory as any).searchArchives === 'function' && q) {
    try {
      // Find highly relevant old turns from the current session
      const archiveResults = await (deps.memory as any).searchArchives(q, {
        filters: { sessionId, types: ['conversation', 'thinking', 'insight'] },
        limit: 3,
        sortBy: 'relevance'
      });
      const relevantOldTurns = (archiveResults || []).map((r: any) => `[Relevance: ${(r.score * 100).toFixed(0)}%] ${  (r.entry.content || '').slice(0, 800)}`);
      if (relevantOldTurns.length > 0) {
        assembled.recentMemories.push(...relevantOldTurns.map((t: string) => `[Recalled from earlier in this session] ${t}`));
      }
    } catch (err) {
      logger?.warn?.('context-assembler: memory.searchArchives failed', { error: String(err) })
    }
  }

  // 2) Available tools (from pipeline's toolRegistry)
  try {
    const pipeline = deps.getPipeline ? deps.getPipeline() : undefined
    const tReg = pipeline ? (pipeline as any).toolRegistry : undefined
    if (tReg && typeof tReg.list === 'function') {
      assembled.availableTools = tReg.list().map((d: any) => d.name)
    }
  } catch (err) {
    logger?.warn?.('context-assembler: failed to list tools', { error: String(err) })
  }

  // 3) Session history (trim oldest until under budget)
  try {
    if (deps.sessionManager && sessionId && includeHistory) {
      const sess = deps.sessionManager.get(sessionId)
      if (sess && Array.isArray(sess.history)) {
        const texts = sess.history.map((m: any) => {
          try {
            if (typeof m.content === 'string') return m.content
            if (Array.isArray(m.content)) return m.content.map((b: any) => (b && typeof b.text === 'string') ? b.text : '').join('\n')
            return ''
          } catch { return '' }
        })
        // WHY: exclude last 10 messages (5 turns) — contextWindowMiddleware already passes them raw
        const MAX_RAW_MESSAGES = 10;
        const olderTexts = texts.length > MAX_RAW_MESSAGES ? texts.slice(0, texts.length - MAX_RAW_MESSAGES) : [];
        
        const keptOlder: string[] = []
        let total = 0
        // HOW: take most recent of the *older* messages (work backwards from olderTexts)
        for (let i = olderTexts.length - 1; i >= 0; i--) {
          const t = olderTexts[i] || ''
          const len = t.length
          if (keptOlder.length >= 20) break
          if (total + len > 12000) break
          keptOlder.unshift(t)
          total += len
        }
        assembled.sessionHistory = keptOlder
      }
    }
  } catch (err) {
    logger?.warn?.('context-assembler: session history fetch failed', { error: String(err) })
  }

  // 4) Files (read small snippets)
  if (files.length > 0) {
    for (const f of files) {
      try {
        const abs = path.isAbsolute(f) ? path.resolve(f) : path.resolve(workingDir, f)
        const allowed = !allowedPaths || allowedPaths.length === 0 || allowedPaths.some(p => abs.startsWith(path.resolve(p)))
        if (!allowed) {
          logger?.warn?.('context-assembler: file outside allowed paths', { file: abs })
          continue
        }
        if (!fs.existsSync(abs)) {
          logger?.warn?.('context-assembler: file not found', { file: abs })
          continue
        }
        let content = fs.readFileSync(abs, 'utf8')
        if (content.length > CONTEXT_SETTINGS.maxFileContentChars) content = `${content.slice(0, CONTEXT_SETTINGS.maxFileContentChars)  }\n// ...truncated`
        assembled.files.push({ path: f, content })
      } catch (err) {
        logger?.warn?.('context-assembler: failed reading file', { file: f, error: String(err) })
      }
    }
  }

  // 5) Extra context
  if (extra) assembled.extraContext = extra

  // 6) Attempt to create a short task guide from dialectic if available via pipeline
  // WHY: emit enhanced diagnostic once per process run to avoid log spam
  const __taskGuideDiagKey = '__context_assembler_taskguide_diag_logged'
  try {
    const pipeline = deps.getPipeline ? deps.getPipeline() : undefined
    const dialectic = pipeline ? (pipeline as any).dialectic as any : undefined
    const __taskGuideDisabledKey = '__context_assembler_taskguide_disabled'
    // Hardened background taskGuide invocation — bounded concurrency, per-session cooldown, and timeout.
    if ((globalThis as any)[__taskGuideDisabledKey]) {
      // taskGuide generation previously failed repeatedly; skip to avoid log spam
    } else if (dialectic && typeof dialectic.buildTaskGuide === 'function') {
      try {
        const TASKGUIDE_TIMEOUT_MS = Number(process.env.CONTEXT_TASKGUIDE_TIMEOUT_MS || '3000')
        const TASKGUIDE_COOLDOWN_MS = Number(process.env.CONTEXT_TASKGUIDE_COOLDOWN_MS || '300000') // 5m
        const TASKGUIDE_MAX_CONCURRENCY = Number(process.env.CONTEXT_TASKGUIDE_MAX_CONCURRENCY || '6')

        const stateKey = '__context_assembler_taskguide_state'
        if (!(globalThis as any)[stateKey]) (globalThis as any)[stateKey] = { inFlight: 0, sessions: new Map() }
        const state = (globalThis as any)[stateKey] as { inFlight: number; sessions: Map<string, any> }

        const sessKey = sessionId || '__nosession'
        const sstate = state.sessions.get(sessKey) || { lastAttempt: 0, failures: 0, cooldownUntil: 0 }
        const now = Date.now()

        if (sstate.cooldownUntil && now < sstate.cooldownUntil) {
          // under cooldown — skip to avoid repeated failures
        } else if (state.inFlight >= TASKGUIDE_MAX_CONCURRENCY) {
          // global concurrency limit reached — skip this run
        } else {
          state.inFlight++
          try {
            const run = async () => {
              try {
                // Always call with the new signature (sessionId, userMessage, context, memories)
                const fn = (dialectic as any).buildTaskGuide
                const args = [sessionId || '', q || '', { recentMemories: assembled.recentMemories, availableTools: assembled.availableTools, sessionHistory: assembled.sessionHistory }, assembled.recentMemories]
                const p = Promise.resolve(Reflect.apply(fn, dialectic, args))
                const res = await Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), TASKGUIDE_TIMEOUT_MS))])
                if (typeof res === 'string' && res.trim()) {
                  assembled.taskGuide = String(res)
                  sstate.failures = 0
                }
              } catch (err) {
                sstate.failures = (sstate.failures || 0) + 1
                if (sstate.failures >= 3) {
                  sstate.cooldownUntil = Date.now() + TASKGUIDE_COOLDOWN_MS
                }
                if (sstate.failures === 1 || sstate.failures >= 3) {
                  logger?.warn?.('[context-assembler] dialectic.buildTaskGuide failed', { sessionId: sessionId ? String(sessionId).slice(-16) : null, error: String(err) })
                } else {
                  logger?.debug?.('[context-assembler] dialectic.buildTaskGuide transient failure', { sessionId: sessionId ? String(sessionId).slice(-16) : null })
                }
              }
            }
            await run()
          } finally {
            state.inFlight--
            state.sessions.set(sessKey, sstate)
          }
        }
      } catch (err) {
        logger?.warn?.('context-assembler: taskGuide generation failed', { error: String(err) })
      }
    }
  } catch (err) {
    logger?.warn?.('context-assembler: taskGuide generation failed', { error: String(err) })
  }

  // 6b) Embedding-based ranking + reranking via shared services
  try {
    const embSvc = getEmbeddingService(logger as ILogger)
    const reranker = getRerankerService(logger as ILogger)

    const candidates: Array<{ id: string; source: string; path?: string; text: string }> = []
    for (let i = 0; i < Math.min(assembled.recentMemories.length, 10); i++) {
      candidates.push({ id: `mem:${i}`, source: 'memory', text: assembled.recentMemories[i] })
    }
    for (let i = Math.max(0, assembled.sessionHistory.length - 12); i < assembled.sessionHistory.length; i++) {
      const idx = i - Math.max(0, assembled.sessionHistory.length - 12)
      candidates.push({ id: `hist:${idx}`, source: 'history', text: assembled.sessionHistory[i] })
    }
    for (let i = 0; i < Math.min(assembled.files.length, 5); i++) {
      const f = assembled.files[i]
      candidates.push({ id: `file:${i}`, source: 'file', path: f.path, text: f.content.slice(0, 1600) })
    }

    if (candidates.length > 0 && q && embSvc.available) {
      // Embed query (asymmetric 'query' mode) and all candidates ('document' mode)
      const [queryVec, ...docVecs] = await Promise.all([
        embSvc.embed(q, 'query'),
        ...candidates.map(c => embSvc.embed(c.text, 'document')),
      ])

      if (queryVec) {
        const scored = candidates.map((c, i) => ({
          source: c.source,
          path: c.path,
          text: c.text,
          score: embSvc.cosineSimilarity(queryVec, docVecs[i]),
        }))
        scored.sort((a, b) => b.score - a.score)

        // HOW: rerank top candidates with cross-encoder (if available)
        const topN = Math.min(scored.length, 12)
        const topCandidates = scored.slice(0, topN)
        if (reranker.available && topCandidates.length > 1) {
          const reranked = await reranker.rerank(q, topCandidates.map(c => c.text), 6)
          if (reranked.length > 0) {
            assembled.semanticHits = reranked.map(r => topCandidates[r.index])
          } else {
            assembled.semanticHits = topCandidates.slice(0, 6)
          }
        } else {
          assembled.semanticHits = topCandidates.slice(0, 6)
        }

        if ((!assembled.taskGuide || assembled.taskGuide.trim() === '') && q) {
          const short = q.replace(/\s+/g, ' ').trim().slice(0, 160)
          assembled.taskGuide = `TASK GUIDE: Address the user's request: "${short}" using the provided context.`
        }
      }
    }
  } catch (err) {
    logger?.warn?.('context-assembler: embedding/ranking failed', { error: String(err) })
  }

  // 7) Pressure-aware trimming to respect charBudget (best-effort)
  try {
    let total = approxChars()
    if (total <= charBudget) return assembled

    logger?.warn?.('context-assembler: trimming context to fit budget', { beforeChars: total, budget: charBudget, sessionId: sessionId || 'none', query: q.slice(0, 100) })
    assembled.trimmed = true

    // HOW: trim session history aggressively (drop older turns and truncate messages)
    if (assembled.sessionHistory && assembled.sessionHistory.length > 0) {
      // Try progressively smaller caps
      const caps = [12, 8, 6, 4, 2]
      for (const cap of caps) {
        if (total <= charBudget) break
        if (assembled.sessionHistory.length > cap) {
          assembled.sessionHistory = assembled.sessionHistory.slice(-cap).map(s => s.slice(0, 600))
          total = approxChars()
        }
      }
      // WHY: still over budget, so create short session summary and replace history
      if (total > charBudget) {
        const head = assembled.sessionHistory.slice(0, 1).join('\n')
        const tail = assembled.sessionHistory.slice(-2).join('\n')
        const summary = [`SUMMARY: recent conversation`, head ? `HEAD: ${head.slice(0, 300)}` : '', `TAIL: ${tail.slice(0, 600)}`].filter(Boolean).join('\n---\n')
        assembled.sessionSummary = summary
        assembled.sessionHistory = []
        total = approxChars()
      }
    }

    // HOW: trim recent memories (reduce count and truncate each)
    if (total > charBudget && assembled.recentMemories && assembled.recentMemories.length > 0) {
      for (let keep = Math.max(0, Math.floor(assembled.recentMemories.length / 2)); keep >= 0 && total > charBudget; keep = Math.floor(keep / 2)) {
        assembled.recentMemories = assembled.recentMemories.slice(0, keep).map(r => r.slice(0, 400))
        total = approxChars()
      }
      if (total > charBudget) assembled.recentMemories = assembled.recentMemories.map(r => r.slice(0, 200))
      total = approxChars()
    }

    // HOW: drop or truncate file contents
    if (total > charBudget && assembled.files && assembled.files.length > 0) {
      // Try truncating each file to small snippet
      for (const f of assembled.files) {
        if (total <= charBudget) break
        f.content = `${f.content.slice(0, 6000)  }\n// ...truncated`
        total = approxChars()
      }
      // HOW: still over budget, so drop files one-by-one starting with largest
      if (total > charBudget) {
        assembled.files.sort((a, b) => b.content.length - a.content.length)
        while (assembled.files.length > 0 && total > charBudget) {
          const dropped = assembled.files.shift()
          total = approxChars()
          logger?.warn?.('context-assembler: dropped file from context due to budget', { dropped: dropped?.path })
        }
      }
    }

    // HOW: final fallback — truncate extraContext or taskGuide
    if (total > charBudget) {
      if (assembled.extraContext) {
        assembled.extraContext = assembled.extraContext.slice(0, Math.max(0, Math.floor(charBudget / 5)))
        total = approxChars()
      }
    }

    if (total > charBudget) {
      if (assembled.taskGuide) assembled.taskGuide = assembled.taskGuide.slice(0, Math.max(0, Math.floor(charBudget / 10)))
      total = approxChars()
    }

    logger?.info?.('context-assembler: trimming complete', { afterChars: total, budget: charBudget, sessionId: sessionId || 'none' })
  } catch (err) {
    logger?.warn?.('context-assembler: trimming failed', { error: String(err) })
  }

  return assembled
}
