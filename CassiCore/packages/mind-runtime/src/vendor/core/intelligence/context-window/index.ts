/**
 * IntelligentContextWindow — scoring-based context window selection.
 *
 * Replaces the naïve last-N-messages trim with a multi-factor scoring system:
 *
 *   score = w_recency * recency + w_relevance * relevance
 *
 * where:
 *   recency    = exp(-λ * age)              exponential decay from the tail
 *   relevance  = normalized FTS5 rank       similarity to the current user query
 *
 * The last `anchorTurns` conversation pairs are always kept verbatim.
 * Older messages are scored, ranked, and selected greedily within the char budget.
 * Omitted spans are replaced with compact gap annotations (S0#M3–M6) so the model
 * knows those messages exist and can retrieve them with cassi_resolve_ref.
 *
 * Cross-session fragments from other indexed sessions are optionally prepended
 * when they score highly enough on relevance alone.
 *
 * If the session has not been indexed yet, the class transparently falls back
 * to the original dumb-trim behaviour so the turn is never blocked.
 */

import { getEmbeddingService } from '@cassicore/embeddings'
import { getRerankerService } from '@cassicore/embeddings'
// SessionIndexer used to live in core/intelligence/memory/session-indexer.ts but
// that module was a no-op stub. The interface is inlined here for the optional
// constructor param; in practice the indexer is always undefined now.
interface SessionIndexer {
  indexSession(sessionId: string, history: any[]): string
  indexIncremental(sessionId: string, history: any[], fromMsgIdx: number): string
  search(query: string, opts?: { limit?: number; sessionId?: string; label?: string }): any[]
  searchIndex(query: string, opts?: { limit?: number; sessionId?: string; label?: string }): any[]
  resolveRef(ref: string): any[]
  getLabel(sessionId: string): string
  isIndexed(sessionId: string): boolean
}

import type { ILogger } from '@cassicore/foundation'
import type { Message, TurnContext } from '@cassicore/foundation'
import type { IndexSearchResult } from '@cassicore/foundation'
import type { TurnMiddleware } from '../../turn-pipeline.js'



export interface ContextWindowConfig {
  /**
   * Always include the last N conversation turns (pairs) verbatim.
   * These act as the recency anchor and are never scored or dropped.
   * @default 3
   */
  anchorTurns: number

  /**
   * Hard cap on total history messages included (excluding anchor + system).
   * @default 18
   */
  maxMessages: number

  /**
   * Total character budget for the assembled messages array.
   * System messages, anchor messages, and the current user message are
   * charged against this budget first; the remainder goes to scored candidates.
   * @default 60_000
   */
  charBudget: number

  /**
   * Exponential decay rate λ.  Higher → older messages decay faster.
   * At λ=0.12 and 20 history messages, the oldest gets recency ≈ 0.10.
   * @default 0.12
   */
  decayRate: number

  /**
   * Scoring weights.  Should sum to 1.0.
   * When embedding service is unavailable at runtime, `semantic` is
   * redistributed proportionally to recency + relevance.
   */
  weights: {
    /** Weight for recency component. @default 0.35 */
    recency: number
    /** Weight for FTS relevance component. @default 0.30 */
    relevance: number
    /** Weight for embedding-based semantic similarity. @default 0.35 */
    semantic: number
  }

  /**
   * Include relevant text fragments from other indexed sessions.
   * @default true
   */
  crossSession: boolean

  /**
   * Maximum number of cross-session message fragments to prepend.
   * @default 4
   */
  crossSessionLimit: number

  /**
   * Insert gap annotations in place of omitted message spans.
   * Annotations include the ref range and top score so the model can
   * decide whether to retrieve them.
   * @default true
   */
  annotateGaps: boolean

  /**
   * Minimum combined score for a candidate to be eligible.
   * Messages below this threshold are excluded even if budget remains.
   * @default 0.04
   */
  minScore: number
}

export const DEFAULT_CONFIG: ContextWindowConfig = {
  anchorTurns: 3,
  maxMessages: 18,
  charBudget: 60_000,
  decayRate: 0.12,
  weights: { recency: 0.35, relevance: 0.30, semantic: 0.35 },
  crossSession: true,
  crossSessionLimit: 4,
  annotateGaps: true,
  minScore: 0.04,
}


export interface ContextWindowStats {
  /** Number of non-anchor history messages evaluated. */
  candidates: number
  /** Number of candidate messages selected. */
  selected: number
  /** Number of candidate messages omitted. */
  omitted: number
  /** Number of anchor messages always included. */
  anchorCount: number
  /** Number of cross-session system messages injected. */
  crossSessionCount: number
  /** Estimated total characters in the assembled messages. */
  charCount: number
  /** Conservative token estimate (charCount / 3). */
  tokenEstimate: number
  /** Whether the intelligent path was bypassed (session not indexed). */
  fallback: boolean
}

export interface ContextWindowResult {
  messages: Message[]
  stats: ContextWindowStats
}


export interface OpenCodeModelMessage {
  role: 'user' | 'assistant' | 'system'
  content: string | Array<OpenCodeContentPart>
}

export interface OpenCodeContentPart {
  type: string
  text?: string
  toolCallId?: string
  toolName?: string
  args?: any
  result?: any
}

export interface OpenCodeContextResult {
  messages: OpenCodeModelMessage[]
  stats: ContextWindowStats
  crossSession: OpenCodeModelMessage[]
}


/** Lightweight digest sent by OpenCode for scoring — no AI SDK objects. */
export interface MessageDigest {
  index: number
  role: string
  text: string
  chars: number
}

/** Gap annotation for a span of omitted messages. */
export interface GapAnnotation {
  /** First omitted index in the original array. */
  start: number
  /** Last omitted index (inclusive). */
  end: number
  /** Compact ref range e.g. "S0#M3–M6". */
  ref: string
  /** Number of omitted messages. */
  count: number
  /** Highest score among omitted messages. */
  score: number
}

/** Score-only result — indices + gaps, no message objects. */
export interface ScoreResult {
  /** Indices into the original digest array that should be kept. */
  kept: number[]
  /** Gap annotations for omitted spans. */
  gaps: GapAnnotation[]
  /** Cross-session context strings for system prompt injection. */
  crossSession: string[]
  /** Selection statistics. */
  stats: ContextWindowStats
}


/**
 * @dep callers: build (core/intelligence/context-window/index.ts), scoreAndSelect (core/intelligence/context-window/index.ts), dumbTrim (core/intelligence/context-window/index.ts), trimSystemMessages (core/intelligence/context-window/index.ts)
 * @dep flows: HandleContextRoutes → ContentLength (5/5)
 * @dep module: Context-window
 * @dep risk: MEDIUM | 4 callers, 1 flow, 1 module
 */

function contentLength(content: Message['content']): number {
  if (typeof content === 'string') return content.length
  if (!Array.isArray(content)) return 0
  return (content as any[]).reduce((sum: number, block: any) => {
    if (block.type === 'text') return sum + (block.text?.length ?? 0)
    if (block.type === 'tool_result') return sum + String(block.content ?? '').length
    if (block.type === 'tool_use') return sum + JSON.stringify(block.input ?? {}).length
    return sum + 50
  }, 0)
}

/**
 * Maximum proportion of the char budget that system messages may consume.
 * The remainder is reserved for conversation history + the current user message.
 * Injected system messages (optimizer, thinker, dialectic, subconscious, digest)
 * are added after the base prompt, so trimming from the tail removes injections
 * first while preserving the base system prompt.
 */
const SYSTEM_MSG_BUDGET_RATIO = 0.4

/**
 * Trim system messages to fit within a fraction of the total char budget.
 *
 * Always keeps the first system message (base prompt) intact.
 * Drops injected system messages from the tail (lowest priority) until
 * total system chars fit within `charBudget * SYSTEM_MSG_BUDGET_RATIO`.
 *
 * If a single injection is oversized, it gets truncated with a marker.
 * @dep callers: build (core/intelligence/context-window/index.ts), dumbTrim (core/intelligence/context-window/index.ts)
 * @dep calls: contentLength
 * @dep flows: HandleContextRoutes → ContentLength (4/5)
 * @dep module: Context-window
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */
function trimSystemMessages(
  systemMsgs: Message[],
  charBudget: number,
  logger?: ILogger,
): Message[] {
  if (systemMsgs.length <= 1) return systemMsgs

  const maxSystemChars = Math.floor(charBudget * SYSTEM_MSG_BUDGET_RATIO)
  let totalChars = systemMsgs.reduce((s, m) => s + contentLength(m.content), 0)

  if (totalChars <= maxSystemChars) return systemMsgs

  // Work backwards: trim injected messages from the tail (most recent injections = lowest priority)
  const result = [...systemMsgs]
  for (let i = result.length - 1; i >= 1 && totalChars > maxSystemChars; i--) {
    const msgChars = contentLength(result[i].content)
    const excess = totalChars - maxSystemChars

    if (msgChars <= excess) {
      // Drop the entire message
      totalChars -= msgChars
      logger?.debug('Context window: dropped injected system message', {
        index: i,
        chars: msgChars,
        remainingTotal: totalChars,
      })
      result.splice(i, 1)
    } else {
      // Truncate this message to fit
      const allowedChars = msgChars - excess
      const content = result[i].content
      if (typeof content === 'string' && allowedChars > 30) {
        result[i] = {
          ...result[i],
          content: `${content.slice(0, allowedChars - 15)  }\n…[truncated]`,
        }
        totalChars = totalChars - msgChars + allowedChars
        logger?.debug('Context window: truncated injected system message', {
          index: i,
          originalChars: msgChars,
          newChars: allowedChars,
        })
      } else {
        // Too short to truncate meaningfully — drop entirely
        totalChars -= msgChars
        result.splice(i, 1)
      }
    }
  }

  return result
}


export class IntelligentContextWindow {
  private config: ContextWindowConfig

  constructor(
    private indexer: SessionIndexer | undefined,
    private logger: ILogger,
    config?: Partial<ContextWindowConfig>,
  ) {
    this.config = {
      ...DEFAULT_CONFIG,
      ...config,
      weights: { ...DEFAULT_CONFIG.weights, ...(config?.weights ?? {}) },
    }
  }

  // PUBLIC API

  /**
   * Build the optimised messages array from `ctxMessages`.
   *
   * Uses a three-factor scoring model:
   *   score = w_recency * recency + w_relevance * fts + w_semantic * cosine
   *
   * When the embedding server is unavailable, semantic weight is redistributed
   * proportionally to recency and relevance (graceful degradation).
   * After greedy selection, a cross-encoder reranker refines the final set.
   *
   * @param sessionId   The current session ID (for index lookup)
   * @param ctxMessages The full ctx.messages array (session history + userMsg)
   * @param currentQuery The current user query (used as the FTS search term)
   */
  async build(
    sessionId: string,
    ctxMessages: Message[],
    currentQuery: string,
  ): Promise<ContextWindowResult> {
    const cfg = this.config

    // Partition: system messages / history / current user message
    const rawSystemMsgs = ctxMessages.filter(m => m.role === 'system')
    const systemMsgs = trimSystemMessages(rawSystemMsgs, cfg.charBudget, this.logger)
    const lastUser = ctxMessages[ctxMessages.length - 1]
    const history = ctxMessages.filter(m => m.role !== 'system' && m !== lastUser)

    // Fast path: nothing to trim
    if (history.length <= cfg.anchorTurns * 2) {
      const charCount = ctxMessages.reduce((s, m) => s + contentLength(m.content), 0)
      return {
        messages: ctxMessages,
        stats: {
          candidates: 0, selected: 0, omitted: 0,
          anchorCount: history.length, crossSessionCount: 0,
          charCount, tokenEstimate: Math.round(charCount / 3), fallback: false,
        },
      }
    }

    // Anchor: last anchorTurns * 2 messages are unconditionally included
    const anchorCount = Math.min(cfg.anchorTurns * 2, history.length)
    const anchorMsgs = history.slice(-anchorCount)
    const candidateMsgs = history.slice(0, history.length - anchorCount)

    // Nothing to score
    if (candidateMsgs.length === 0) {
      const charCount = ctxMessages.reduce((s, m) => s + contentLength(m.content), 0)
      return {
        messages: ctxMessages,
        stats: {
          candidates: 0, selected: 0, omitted: 0,
          anchorCount, crossSessionCount: 0,
          charCount, tokenEstimate: Math.round(charCount / 3), fallback: false,
        },
      }
    }

    // Check whether the session has been indexed
    const label = this.indexer?.getLabel(sessionId)
    const indexed = !!label && !!this.indexer?.isIndexed(sessionId)

    if (!indexed) {
      return this.dumbTrim(ctxMessages, cfg.charBudget, cfg.anchorTurns)
    }


    const ftsHits = currentQuery.trim() && this.indexer
      ? this.indexer.search(currentQuery, { label: label!, limit: 100 })
      : []

    // Per message: keep the *most* relevant (most-negative rank) hit
    const rawRankByMsgIdx = new Map<number, number>()
    for (const hit of ftsHits) {
      const existing = rawRankByMsgIdx.get(hit.entry.msgIdx)
      if (existing === undefined || hit.rank < existing) {
        rawRankByMsgIdx.set(hit.entry.msgIdx, hit.rank)
      }
    }

    // Normalise ranks to [0, 1] within this query's result set
    const ranks = [...rawRankByMsgIdx.values()]
    const minRank = ranks.length > 0 ? Math.min(...ranks) : 0
    const maxRank = ranks.length > 0 ? Math.max(...ranks) : 0
    const rankRange = maxRank - minRank

    const normalizeRank = (rank: number): number =>
      rankRange === 0 ? 1.0 : (maxRank - rank) / rankRange


    const embSvc = getEmbeddingService(this.logger)
    const hasEmbeddings = embSvc.available && !!currentQuery.trim() && candidateMsgs.length > 4
    let semanticScores: number[] | null = null

    if (hasEmbeddings) {
      try {
        const queryVec = await embSvc.embed(currentQuery, 'query')
        if (queryVec) {
          const docTexts = candidateMsgs.map(m => {
            const c = m.content
            const text = typeof c === 'string' ? c : Array.isArray(c)
              ? (c as any[]).map((b: any) => b?.text || '').join(' ')
              : ''
            return text.slice(0, 1200)
          })
          const docVecs = await embSvc.embedBatch(docTexts, 'document')
          semanticScores = docVecs.map(v => embSvc.cosineSimilarity(queryVec, v))
        }
      } catch (err) {
        this.logger.debug('Context window: embedding scoring failed, falling back', { error: String(err) })
      }
    }

    // If embeddings are unavailable, redistribute semantic weight proportionally

    let wRecency = cfg.weights.recency
    let wRelevance = cfg.weights.relevance
    let wSemantic = cfg.weights.semantic

    if (!semanticScores) {
      const ftsSum = wRecency + wRelevance
      if (ftsSum > 0) {
        wRecency = wRecency / ftsSum
        wRelevance = wRelevance / ftsSum
      } else {
        wRecency = 0.5
        wRelevance = 0.5
      }
      wSemantic = 0
    }


    const H = history.length

    interface ScoredCandidate {
      msgIdx: number    // position in history[] == msg_idx in session_index
      msg: Message
      score: number
      chars: number
    }

    const scored: ScoredCandidate[] = candidateMsgs.map((msg, i) => {
      // i == position in history[] (0 = oldest candidate)
      const age = H - 1 - i           // 0 = anchor-adjacent, higher = older
      const recency = Math.exp(-cfg.decayRate * age)
      const rawRank = rawRankByMsgIdx.get(i)
      const relevance = rawRank !== undefined ? normalizeRank(rawRank) : 0
      const semantic = semanticScores ? semanticScores[i] : 0
      const score = wRecency * recency + wRelevance * relevance + wSemantic * semantic

      return { msgIdx: i, msg, score, chars: contentLength(msg.content) }
    })


    const systemChars = systemMsgs.reduce((s, m) => s + contentLength(m.content), 0)
    const lastUserChars = contentLength(lastUser.content)
    const anchorChars = anchorMsgs.reduce((s, m) => s + contentLength(m.content), 0)
    let remainingBudget = cfg.charBudget - systemChars - lastUserChars - anchorChars


    let eligible = scored
      .filter(s => s.score >= cfg.minScore)
      .sort((a, b) => b.score - a.score)

    const reranker = getRerankerService(this.logger)
    if (reranker.available && eligible.length > cfg.maxMessages && currentQuery.trim()) {
      try {
        const topPool = eligible.slice(0, Math.min(eligible.length, cfg.maxMessages * 3))
        const docTexts = topPool.map(s => {
          const c = s.msg.content
          return (typeof c === 'string' ? c : '').slice(0, 1200)
        })
        const reranked = await reranker.rerank(currentQuery, docTexts, cfg.maxMessages * 2)
        if (reranked.length > 0) {
          // Merge reranker scores: blend original score with reranker position
          const rerankedMap = new Map(reranked.map((r, pos) => [r.index, pos]))
          eligible = topPool.map((s, origIdx) => {
            const rerankerPos = rerankedMap.get(origIdx)
            if (rerankerPos !== undefined) {
              // Boost items the reranker ranked highly
              const rerankerBoost = 1.0 - (rerankerPos / reranked.length)
              return { ...s, score: 0.6 * s.score + 0.4 * rerankerBoost }
            }
            return s
          }).sort((a, b) => b.score - a.score)
        }
      } catch (err) {
        this.logger.debug('Context window: reranker pass failed, using embedding scores', { error: String(err) })
      }
    }

    const selectedIdxs = new Set<number>()
    let selectedCount = 0

    for (const s of eligible) {
      if (selectedCount >= cfg.maxMessages) break
      if (s.chars > remainingBudget) continue
      selectedIdxs.add(s.msgIdx)
      remainingBudget -= s.chars
      selectedCount++
    }


    const reconstructed: Message[] = []
    let gapStart: number | null = null
    let gapCount = 0
    let gapMaxScore = 0

    const flushGap = (nextMsgIdx: number) => {
      if (gapStart === null || gapCount === 0 || !cfg.annotateGaps) return

      const startRef = `${label}#M${gapStart}`
      const endRef = `${label}#M${nextMsgIdx - 1}`
      const refRange = gapCount === 1 ? startRef : `${startRef}–${endRef}`

      reconstructed.push({
        role: 'system',
        content:
          `[omitted: ${refRange} · ${gapCount} message${gapCount !== 1 ? 's' : ''}, ` +
          `top score ${gapMaxScore.toFixed(2)} · use cassi_resolve_ref to retrieve]`,
      } as Message)

      gapStart = null
      gapCount = 0
      gapMaxScore = 0
    }

    for (let i = 0; i < candidateMsgs.length; i++) {
      if (selectedIdxs.has(i)) {
        flushGap(i)
        reconstructed.push(candidateMsgs[i])
      } else {
        if (gapStart === null) gapStart = i
        gapCount++
        const s = scored.find(c => c.msgIdx === i)
        if (s && s.score > gapMaxScore) gapMaxScore = s.score
      }
    }
    flushGap(candidateMsgs.length)


    const crossSessionMsgs: Message[] = []

    if (cfg.crossSession && currentQuery.trim() && this.indexer) {
      const xsHits = this.indexer
        .search(currentQuery, { limit: cfg.crossSessionLimit * 5 })
        .filter(h => h.entry.sessionId !== sessionId && h.entry.blockType === 'text')

      // Deduplicate by (label, msgIdx) — keep most-relevant hit per message
      const xsGroups = new Map<string, IndexSearchResult>()
      for (const hit of xsHits) {
        const key = `${hit.entry.label}#M${hit.entry.msgIdx}`
        const existing = xsGroups.get(key)
        if (!existing || hit.rank < existing.rank) xsGroups.set(key, hit)
      }

      let top = [...xsGroups.values()]
        .sort((a, b) => a.rank - b.rank)

      // Re-score cross-session hits with embeddings for better precision
      if (embSvc.available && top.length > cfg.crossSessionLimit) {
        try {
          const queryVec = await embSvc.embed(currentQuery, 'query')
          if (queryVec) {
            const xsTexts = top.map(h => h.entry.content.slice(0, 800))
            const xsVecs = await embSvc.embedBatch(xsTexts, 'document')
            const xsScored = top.map((h, i) => ({
              hit: h,
              embScore: embSvc.cosineSimilarity(queryVec, xsVecs[i]),
              ftsRank: h.rank,
            }))
            // Blend: 40% FTS rank position + 60% embedding cosine
            const maxFts = Math.max(...xsScored.map(x => -x.ftsRank))
            xsScored.sort((a, b) => {
              const ftsA = maxFts > 0 ? (-a.ftsRank / maxFts) : 0
              const ftsB = maxFts > 0 ? (-b.ftsRank / maxFts) : 0
              const blendA = 0.4 * ftsA + 0.6 * a.embScore
              const blendB = 0.4 * ftsB + 0.6 * b.embScore
              return blendB - blendA
            })
            top = xsScored.map(x => x.hit)
          }
        } catch (err) {
          this.logger.debug('Context window: cross-session embedding re-score failed', { error: String(err) })
        }
      }

      top = top.slice(0, cfg.crossSessionLimit)

      if (top.length > 0) {
        const lines = top.map(h => {
          const e = h.entry
          const preview = e.content.slice(0, 280).replace(/\n/g, ' ')
          const ellipsis = e.content.length > 280 ? '…' : ''
          return `${e.ref}  ${e.role.toUpperCase()}: ${preview}${ellipsis}`
        })
        crossSessionMsgs.push({
          role: 'system',
          content:
            `[relevant context from other sessions — use cassi_resolve_ref for full content]\n${ 
            lines.join('\n')}`,
        } as Message)
      }
    }


    const finalMessages: Message[] = [
      ...systemMsgs,
      ...crossSessionMsgs,
      ...reconstructed,
      ...anchorMsgs,
      lastUser,
    ]

    const charCount = finalMessages.reduce((s, m) => s + contentLength(m.content), 0)

    this.logger.debug('Context window built', {
      sessionId,
      label,
      candidates: candidateMsgs.length,
      selected: selectedIdxs.size,
      omitted: candidateMsgs.length - selectedIdxs.size,
      anchorCount,
      crossSession: crossSessionMsgs.length,
      charCount,
    })

    return {
      messages: finalMessages,
      stats: {
        candidates: candidateMsgs.length,
        selected: selectedIdxs.size,
        omitted: candidateMsgs.length - selectedIdxs.size,
        anchorCount,
        crossSessionCount: crossSessionMsgs.length,
        charCount,
        tokenEstimate: Math.round(charCount / 3),
        fallback: false,
      },
    }
  }

  /**
   * Build the optimised messages array from OpenCode's model message format.
   * Translates between OpenCode's AI SDK format and CassiCore's native Message format,
   * delegates to the core `build()` method, then translates the result back.
   *
   * @param sessionId   The OpenCode session ID
   * @param ocMessages  Messages in OpenCode's AI SDK format
   * @param currentQuery The current user query text
   * @param charBudget  Optional override for the char budget (computed from model limits)
   */
  async buildForOpenCode(
    sessionId: string,
    ocMessages: OpenCodeModelMessage[],
    currentQuery: string,
    charBudget?: number,
  ): Promise<OpenCodeContextResult> {
    const originalBudget = this.config.charBudget
    let cassiMessages: Message[] = []

    try {
      // Temporarily override char budget if provided
      if (charBudget !== undefined) {
        this.config.charBudget = charBudget
      }

      // Convert OpenCode messages to CassiCore format
      for (const ocMsg of ocMessages) {
        const msg: Message = {
          role: ocMsg.role,
          content: '',
        }

        if (typeof ocMsg.content === 'string') {
          msg.content = ocMsg.content
        } else if (Array.isArray(ocMsg.content)) {
          const blocks: Array<{ type: 'text'; text: string } | { type: 'tool_use'; id: string; name: string; input: Record<string, unknown> } | { type: 'tool_result'; tool_use_id: string; content: string; is_error?: boolean }> = []

          for (const part of ocMsg.content) {
            if (part.type === 'text' && part.text !== undefined) {
              blocks.push({ type: 'text', text: part.text })
            } else if (part.type === 'tool-call' && part.toolCallId && part.toolName) {
              blocks.push({
                type: 'tool_use',
                id: part.toolCallId,
                name: part.toolName,
                input: part.args ?? {},
              })
            } else if (part.type === 'tool-result' && part.toolCallId) {
              const content = typeof part.result === 'string' ? part.result : JSON.stringify(part.result)
              blocks.push({
                type: 'tool_result',
                tool_use_id: part.toolCallId,
                content,
              })
            }
          }

          msg.content = blocks
        }

        cassiMessages.push(msg)
      }

      // Call the core build method
      const result = await this.build(sessionId, cassiMessages, currentQuery)

      // Convert CassiCore messages back to OpenCode format
      const convertToOpenCode = (msg: Message): OpenCodeModelMessage => {
        const ocMsg: OpenCodeModelMessage = {
          role: msg.role as 'user' | 'assistant' | 'system',
          content: '',
        }

        if (typeof msg.content === 'string') {
          ocMsg.content = msg.content
        } else if (Array.isArray(msg.content)) {
          const parts: OpenCodeContentPart[] = []

          for (const block of msg.content) {
            if (block.type === 'text' && 'text' in block) {
              parts.push({ type: 'text', text: block.text })
            } else if (block.type === 'tool_use') {
              parts.push({
                type: 'tool-call',
                toolCallId: block.id,
                toolName: block.name,
                args: block.input,
              })
            } else if (block.type === 'tool_result') {
              parts.push({
                type: 'tool-result',
                toolCallId: block.tool_use_id,
                result: block.content,
              })
            }
          }

          ocMsg.content = parts
        }

        return ocMsg
      }

      const messages = result.messages.map(convertToOpenCode)

      // Separate cross-session system messages from the rest
      const regularMessages: OpenCodeModelMessage[] = []
      const crossSession: OpenCodeModelMessage[] = []

      for (const msg of messages) {
        const content = typeof msg.content === 'string' ? msg.content : ''
        if (msg.role === 'system' && content.startsWith('[relevant context')) {
          crossSession.push(msg)
        } else {
          regularMessages.push(msg)
        }
      }

      return {
        messages: regularMessages,
        stats: result.stats,
        crossSession,
      }
    } catch (err) {
      this.logger.error('buildForOpenCode failed', { error: String(err), sessionId })
      throw err
    } finally {
      // Restore original char budget
      if (charBudget !== undefined) {
        this.config.charBudget = originalBudget
      }
    }
  }

  /**
   * Score messages and return selection decisions (indices + gap annotations).
   *
   * Unlike `buildForOpenCode()`, this method never touches the actual message
   * objects — it operates on lightweight text digests and returns which indices
   * to keep/drop.  The caller applies the decisions to its original array,
   * preserving AI SDK type fidelity.
   *
   * Scoring uses the same three-factor model as `build()`:
   *   score = w_recency * recency + w_relevance * fts + w_semantic * cosine
   *
   * @param sessionId   The session ID (for FTS index lookup)
   * @param digests     Lightweight message digests (index, role, text, chars)
   * @param query       The current user query text
   * @param charBudget  Optional char budget override
   */
  async scoreForOpenCode(
    sessionId: string,
    digests: MessageDigest[],
    query: string,
    charBudget?: number,
  ): Promise<ScoreResult> {
    const cfg = this.config
    const effectiveBudget = charBudget ?? cfg.charBudget

    const systemDigests = digests.filter(d => d.role === 'system')
    const lastDigest = digests[digests.length - 1]
    const history = digests.filter(d => d.role !== 'system' && d !== lastDigest)

    // Fast path: nothing to trim
    if (history.length <= cfg.anchorTurns * 2) {
      const charCount = digests.reduce((s, d) => s + d.chars, 0)
      return {
        kept: digests.map(d => d.index),
        gaps: [],
        crossSession: [],
        stats: {
          candidates: 0, selected: 0, omitted: 0,
          anchorCount: history.length, crossSessionCount: 0,
          charCount, tokenEstimate: Math.round(charCount / 3), fallback: false,
        },
      }
    }

    // Anchor: last anchorTurns * 2 history messages are unconditionally kept
    const anchorCount = Math.min(cfg.anchorTurns * 2, history.length)
    const anchorDigests = history.slice(-anchorCount)
    const candidateDigests = history.slice(0, history.length - anchorCount)

    // Nothing to score
    if (candidateDigests.length === 0) {
      const charCount = digests.reduce((s, d) => s + d.chars, 0)
      return {
        kept: digests.map(d => d.index),
        gaps: [],
        crossSession: [],
        stats: {
          candidates: 0, selected: 0, omitted: 0,
          anchorCount, crossSessionCount: 0,
          charCount, tokenEstimate: Math.round(charCount / 3), fallback: false,
        },
      }
    }

    // Check whether the session has been indexed
    const label = this.indexer?.getLabel(sessionId)
    const indexed = !!label && !!this.indexer?.isIndexed(sessionId)

    if (!indexed) {
      // Dumb trim fallback: keep as many recent messages as fit in budget
      return this.dumbTrimDigests(digests, effectiveBudget, cfg.anchorTurns)
    }

    const ftsHits = query.trim() && this.indexer
      ? this.indexer.search(query, { label: label!, limit: 100 })
      : []

    const rawRankByMsgIdx = new Map<number, number>()
    for (const hit of ftsHits) {
      const existing = rawRankByMsgIdx.get(hit.entry.msgIdx)
      if (existing === undefined || hit.rank < existing) {
        rawRankByMsgIdx.set(hit.entry.msgIdx, hit.rank)
      }
    }

    const ranks = [...rawRankByMsgIdx.values()]
    const minRank = ranks.length > 0 ? Math.min(...ranks) : 0
    const maxRank = ranks.length > 0 ? Math.max(...ranks) : 0
    const rankRange = maxRank - minRank
    const normalizeRank = (rank: number): number =>
      rankRange === 0 ? 1.0 : (maxRank - rank) / rankRange

    const embSvc = getEmbeddingService(this.logger)
    const hasEmbeddings = embSvc.available && !!query.trim() && candidateDigests.length > 4
    let semanticScores: number[] | null = null

    if (hasEmbeddings) {
      try {
        const queryVec = await embSvc.embed(query, 'query')
        if (queryVec) {
          const docTexts = candidateDigests.map(d => d.text.slice(0, 1200))
          const docVecs = await embSvc.embedBatch(docTexts, 'document')
          semanticScores = docVecs.map(v => embSvc.cosineSimilarity(queryVec, v))
        }
      } catch (err) {
        this.logger.debug('scoreForOpenCode: embedding scoring failed', { error: String(err) })
      }
    }

    let wRecency = cfg.weights.recency
    let wRelevance = cfg.weights.relevance
    let wSemantic = cfg.weights.semantic

    if (!semanticScores) {
      const ftsSum = wRecency + wRelevance
      if (ftsSum > 0) {
        wRecency = wRecency / ftsSum
        wRelevance = wRelevance / ftsSum
      } else {
        wRecency = 0.5
        wRelevance = 0.5
      }
      wSemantic = 0
    }

    const H = history.length

    interface ScoredCandidate {
      digestIdx: number   // position in candidateDigests
      origIdx: number     // original index in the caller's array
      score: number
      chars: number
      text: string
    }

    const scored: ScoredCandidate[] = candidateDigests.map((d, i) => {
      const age = H - 1 - i
      const recency = Math.exp(-cfg.decayRate * age)
      const rawRank = rawRankByMsgIdx.get(d.index)
      const relevance = rawRank !== undefined ? normalizeRank(rawRank) : 0
      const semantic = semanticScores ? semanticScores[i] : 0
      const score = wRecency * recency + wRelevance * relevance + wSemantic * semantic
      return { digestIdx: i, origIdx: d.index, score, chars: d.chars, text: d.text }
    })

    const systemChars = systemDigests.reduce((s, d) => s + d.chars, 0)
    const lastUserChars = lastDigest.chars
    const anchorChars = anchorDigests.reduce((s, d) => s + d.chars, 0)
    let remainingBudget = effectiveBudget - systemChars - lastUserChars - anchorChars

    let eligible = scored
      .filter(s => s.score >= cfg.minScore)
      .sort((a, b) => b.score - a.score)

    const reranker = getRerankerService(this.logger)
    if (reranker.available && eligible.length > cfg.maxMessages && query.trim()) {
      try {
        const topPool = eligible.slice(0, Math.min(eligible.length, cfg.maxMessages * 3))
        const docTexts = topPool.map(s => s.text.slice(0, 1200))
        const reranked = await reranker.rerank(query, docTexts, cfg.maxMessages * 2)
        if (reranked.length > 0) {
          const rerankedMap = new Map(reranked.map((r, pos) => [r.index, pos]))
          eligible = topPool.map((s, origIdx) => {
            const rerankerPos = rerankedMap.get(origIdx)
            if (rerankerPos !== undefined) {
              const rerankerBoost = 1.0 - (rerankerPos / reranked.length)
              return { ...s, score: 0.6 * s.score + 0.4 * rerankerBoost }
            }
            return s
          }).sort((a, b) => b.score - a.score)
        }
      } catch (err) {
        this.logger.debug('scoreForOpenCode: reranker failed', { error: String(err) })
      }
    }

    const selectedOrigIdxs = new Set<number>()
    let selectedCount = 0

    for (const s of eligible) {
      if (selectedCount >= cfg.maxMessages) break
      if (s.chars > remainingBudget) continue
      selectedOrigIdxs.add(s.origIdx)
      remainingBudget -= s.chars
      selectedCount++
    }

    const kept: number[] = []

    // System messages are always kept
    for (const d of systemDigests) kept.push(d.index)

    // Selected candidates (in chronological order)
    for (const d of candidateDigests) {
      if (selectedOrigIdxs.has(d.index)) kept.push(d.index)
    }

    // Anchor messages are always kept
    for (const d of anchorDigests) kept.push(d.index)

    // Current user message is always kept
    kept.push(lastDigest.index)

    const gaps: GapAnnotation[] = []

    if (cfg.annotateGaps) {
      let gapStart: number | null = null
      let gapCount = 0
      let gapMaxScore = 0

      const flushGap = (nextOrigIdx: number) => {
        if (gapStart === null || gapCount === 0) return

        const startRef = `${label}#M${gapStart}`
        const endRef = `${label}#M${nextOrigIdx - 1}`
        const refRange = gapCount === 1 ? startRef : `${startRef}–${endRef}`

        gaps.push({
          start: gapStart,
          end: nextOrigIdx - 1,
          ref: refRange,
          count: gapCount,
          score: gapMaxScore,
        })

        gapStart = null
        gapCount = 0
        gapMaxScore = 0
      }

      for (const d of candidateDigests) {
        if (selectedOrigIdxs.has(d.index)) {
          flushGap(d.index)
        } else {
          if (gapStart === null) gapStart = d.index
          gapCount++
          const s = scored.find(c => c.origIdx === d.index)
          if (s && s.score > gapMaxScore) gapMaxScore = s.score
        }
      }
      // Flush final gap (before anchor zone)
      if (anchorDigests.length > 0) {
        flushGap(anchorDigests[0].index)
      } else {
        flushGap(lastDigest.index)
      }
    }

    const crossSession: string[] = []

    if (cfg.crossSession && query.trim() && this.indexer) {
      const xsHits = this.indexer
        .search(query, { limit: cfg.crossSessionLimit * 5 })
        .filter(h => h.entry.sessionId !== sessionId && h.entry.blockType === 'text')

      const xsGroups = new Map<string, typeof xsHits[number]>()
      for (const hit of xsHits) {
        const key = `${hit.entry.label}#M${hit.entry.msgIdx}`
        const existing = xsGroups.get(key)
        if (!existing || hit.rank < existing.rank) xsGroups.set(key, hit)
      }

      let top = [...xsGroups.values()].sort((a, b) => a.rank - b.rank)

      // Re-score with embeddings for better precision
      if (embSvc.available && top.length > cfg.crossSessionLimit) {
        try {
          const queryVec = await embSvc.embed(query, 'query')
          if (queryVec) {
            const xsTexts = top.map(h => h.entry.content.slice(0, 800))
            const xsVecs = await embSvc.embedBatch(xsTexts, 'document')
            const xsScored = top.map((h, i) => ({
              hit: h,
              embScore: embSvc.cosineSimilarity(queryVec, xsVecs[i]),
              ftsRank: h.rank,
            }))
            const maxFts = Math.max(...xsScored.map(x => -x.ftsRank))
            xsScored.sort((a, b) => {
              const ftsA = maxFts > 0 ? (-a.ftsRank / maxFts) : 0
              const ftsB = maxFts > 0 ? (-b.ftsRank / maxFts) : 0
              return (0.4 * ftsB + 0.6 * b.embScore) - (0.4 * ftsA + 0.6 * a.embScore)
            })
            top = xsScored.map(x => x.hit)
          }
        } catch (err) {
          this.logger.debug('scoreForOpenCode: cross-session embedding re-score failed', { error: String(err) })
        }
      }

      top = top.slice(0, cfg.crossSessionLimit)

      if (top.length > 0) {
        const lines = top.map(h => {
          const e = h.entry
          const preview = e.content.slice(0, 280).replace(/\n/g, ' ')
          const ellipsis = e.content.length > 280 ? '…' : ''
          return `${e.ref}  ${e.role.toUpperCase()}: ${preview}${ellipsis}`
        })
        crossSession.push(
          `[relevant context from other sessions — use cassi_resolve_ref for full content]\n${
            lines.join('\n')}`,
        )
      }
    }

    const charCount = kept.reduce((s, idx) => {
      const d = digests.find(dd => dd.index === idx)
      return s + (d?.chars ?? 0)
    }, 0)

    this.logger.debug('scoreForOpenCode complete', {
      sessionId, label,
      candidates: candidateDigests.length,
      selected: selectedOrigIdxs.size,
      omitted: candidateDigests.length - selectedOrigIdxs.size,
      gaps: gaps.length,
      crossSession: crossSession.length,
      anchorCount,
      charCount,
    })

    return {
      kept,
      gaps,
      crossSession,
      stats: {
        candidates: candidateDigests.length,
        selected: selectedOrigIdxs.size,
        omitted: candidateDigests.length - selectedOrigIdxs.size,
        anchorCount,
        crossSessionCount: crossSession.length,
        charCount,
        tokenEstimate: Math.round(charCount / 3),
        fallback: false,
      },
    }
  }

  //
  // Lightweight scoring for multi-agent sessions (Dyad/Lumen/Helix).
  // These sessions don't have indexed sessions — they need the scoring
  // algorithm to decide which messages to keep when context fills up.

  /**
   * Score and select messages for a multi-agent context window.
   *
   * Unlike build(), this method:
   *   - Does NOT require a SessionIndexer or session ID
   *   - Uses only recency + basic keyword matching (no FTS5 index)
   *   - Does NOT inject cross-session context or gap annotations
   *
   * @param messages - Full message history for this agent posture
   * @param currentQuery - The current goal or last user message (for relevance scoring)
   * @param charBudget - Maximum total characters to keep
   * @param opts - Optional tuning parameters
   * @returns Selected messages in original order, plus stats
   */
  scoreAndSelect(
    messages: Message[],
    currentQuery: string,
    charBudget: number,
    opts?: {
      /** Anchor turns to always keep from the head (default: 2) */
      anchorTurns?: number
      /** Anchor turns to always keep from the tail (default: 3) */
      tailAnchorTurns?: number
      /** Weight overrides (default: recency=0.50, relevance=0.50) */
      weights?: Partial<{ recency: number; relevance: number }>
      /** Minimum score threshold (default: 0.05) */
      minScore?: number
      /** Exponential decay rate for recency (default: 0.08) */
      decayRate?: number
    },
  ): { messages: Message[]; stats: { candidates: number; selected: number; omitted: number; charCount: number } } {
    const anchorTurns = opts?.anchorTurns ?? 2
    const tailAnchorTurns = opts?.tailAnchorTurns ?? 3
    const wRecency = opts?.weights?.recency ?? 0.50
    const wRelevance = opts?.weights?.relevance ?? 0.50
    const minScore = opts?.minScore ?? 0.05
    const decayRate = opts?.decayRate ?? 0.08

    if (messages.length === 0) {
      return { messages: [], stats: { candidates: 0, selected: 0, omitted: 0, charCount: 0 } }
    }

    // Separate system messages (always kept)
    const systemMsgs: Message[] = []
    const nonSystem: Message[] = []
    for (const m of messages) {
      if (m.role === 'system') systemMsgs.push(m)
      else nonSystem.push(m)
    }

    if (nonSystem.length === 0) {
      return { messages: [...systemMsgs], stats: { candidates: 0, selected: 0, omitted: 0, charCount: systemMsgs.reduce((s, m) => s + contentLength(m.content), 0) } }
    }

    // Anchor: first N and last N turns are always kept
    const anchorIdxs = new Set<number>()
    for (let i = 0; i < Math.min(anchorTurns, nonSystem.length); i++) anchorIdxs.add(i)
    for (let i = Math.max(0, nonSystem.length - tailAnchorTurns); i < nonSystem.length; i++) anchorIdxs.add(i)

    // Candidate messages = everything not anchored
    const candidates: Array<{ idx: number; msg: Message }> = []
    for (let i = 0; i < nonSystem.length; i++) {
      if (!anchorIdxs.has(i)) candidates.push({ idx: i, msg: nonSystem[i] })
    }

    // Build keyword set from current query for lightweight relevance
    const queryTerms = currentQuery.toLowerCase().split(/\W+/).filter(t => t.length > 2)
    const queryTermSet = new Set(queryTerms)

    // Score each candidate
    const H = nonSystem.length
    const scored = candidates.map(({ idx, msg }) => {
      // Recency: exponential decay from tail
      const age = H - 1 - idx
      const recency = Math.exp(-decayRate * age)

      // Relevance: keyword overlap (lightweight, no FTS needed)
      let relevance = 0
      if (queryTermSet.size > 0) {
        const text = typeof msg.content === 'string'
          ? msg.content.toLowerCase()
          : Array.isArray(msg.content)
            ? (msg.content as any[]).map((b: any) => typeof b === 'string' ? b : (b.text ?? '')).join(' ').toLowerCase()
            : ''
        let hits = 0
        for (const term of queryTermSet) {
          if (text.includes(term)) hits++
        }
        relevance = hits / queryTermSet.size
      }

      const score = wRecency * recency + wRelevance * relevance
      return { idx, msg, score, chars: contentLength(msg.content) }
    })

    // Sort by score descending, greedily select within budget
    const systemChars = systemMsgs.reduce((s, m) => s + contentLength(m.content), 0)
    const anchorChars = [...anchorIdxs].reduce((s, i) => s + contentLength(nonSystem[i].content), 0)
    let remaining = charBudget - systemChars - anchorChars

    const eligible = scored
      .filter(s => s.score >= minScore)
      .sort((a, b) => b.score - a.score)

    const selectedIdxs = new Set<number>(anchorIdxs)
    for (const s of eligible) {
      if (remaining <= 0) break
      if (s.chars <= remaining) {
        selectedIdxs.add(s.idx)
        remaining -= s.chars
      }
    }

    // Reconstruct in original order
    const result: Message[] = [...systemMsgs]
    for (let i = 0; i < nonSystem.length; i++) {
      if (selectedIdxs.has(i)) result.push(nonSystem[i])
    }

    const charCount = result.reduce((s, m) => s + contentLength(m.content), 0)
    return {
      messages: result,
      stats: {
        candidates: candidates.length,
        selected: selectedIdxs.size,
        omitted: candidates.length - (selectedIdxs.size - anchorIdxs.size),
        charCount,
      },
    }
  }

  /**
   * Return this strategy as a drop-in TurnMiddleware.
   * Reads the current user query from ctx.inbound.content.
   */
  asMiddleware(): TurnMiddleware {
    return async (ctx: TurnContext, next: () => Promise<any>) => {
      try {
        const query = typeof ctx.inbound?.content === 'string'
          ? ctx.inbound.content
          : ''
        const result = await this.build(ctx.session.id, ctx.messages, query)
        ctx.messages = result.messages

        // Expose stats on ctx for observability (optional downstream consumers)
        ;(ctx as any).__contextWindowStats = result.stats
      } catch (err) {
        // Never block the turn — log and fall through with original messages
        this.logger.error('IntelligentContextWindow failed, using original messages', {
          error: String(err),
          sessionId: ctx.session.id,
        })
      }
      return next()
    }
  }

  /**
   * Hot-update configuration without recreating the instance.
   */
  updateConfig(partial: Partial<ContextWindowConfig>): void {
    this.config = {
      ...this.config,
      ...partial,
      weights: { ...this.config.weights, ...(partial.weights ?? {}) },
    }
    this.logger.info('Context window config updated', { config: this.config })
  }

  // FALLBACK: dumb trim (identical to original contextWindowMiddleware)

  private dumbTrim(
    ctxMessages: Message[],
    budgetChars: number,
    anchorTurns: number,
  ): ContextWindowResult {
    const MAX_HISTORY_MESSAGES = Math.max(anchorTurns * 2, 10)

    const rawSystemMsgs = ctxMessages.filter(m => m.role === 'system')
    const systemMsgs = trimSystemMessages(rawSystemMsgs, budgetChars, this.logger)
    const lastUser = ctxMessages[ctxMessages.length - 1]
    const history = ctxMessages.filter(m => m.role !== 'system' && m !== lastUser)

    let totalChars = systemMsgs.reduce((s, m) => s + contentLength(m.content), 0)
    totalChars += contentLength(lastUser.content)

    const kept: Message[] = []

    for (
      let i = history.length - 1;
      i >= Math.max(0, history.length - MAX_HISTORY_MESSAGES);
      i--
    ) {
      const chars = contentLength(history[i].content)
      if (totalChars + chars > budgetChars) break
      kept.unshift(history[i])
      totalChars += chars
    }

    const messages = [...systemMsgs, ...kept, lastUser]

    return {
      messages,
      stats: {
        candidates: history.length,
        selected: kept.length,
        omitted: history.length - kept.length,
        anchorCount: 0,
        crossSessionCount: 0,
        charCount: totalChars,
        tokenEstimate: Math.round(totalChars / 3),
         fallback: true,
      },
    }
  }

  /**
   * Dumb trim for digest arrays — keeps as many recent messages as fit in budget.
   * Fallback when the session has not been FTS-indexed.
   */
  private dumbTrimDigests(
    digests: MessageDigest[],
    budgetChars: number,
    anchorTurns: number,
  ): ScoreResult {
    const maxHistory = Math.max(anchorTurns * 2, 10)

    const systemDigests = digests.filter(d => d.role === 'system')
    const lastDigest = digests[digests.length - 1]
    const history = digests.filter(d => d.role !== 'system' && d !== lastDigest)

    let totalChars = systemDigests.reduce((s, d) => s + d.chars, 0)
    totalChars += lastDigest.chars

    const kept: number[] = []
    for (const d of systemDigests) kept.push(d.index)

    const historyKept: number[] = []
    for (
      let i = history.length - 1;
      i >= Math.max(0, history.length - maxHistory);
      i--
    ) {
      if (totalChars + history[i].chars > budgetChars) break
      historyKept.unshift(history[i].index)
      totalChars += history[i].chars
    }

    kept.push(...historyKept)
    kept.push(lastDigest.index)

    return {
      kept,
      gaps: [],
      crossSession: [],
      stats: {
        candidates: history.length,
        selected: historyKept.length,
        omitted: history.length - historyKept.length,
        anchorCount: 0,
        crossSessionCount: 0,
        charCount: totalChars,
        tokenEstimate: Math.round(totalChars / 3),
        fallback: true,
      },
    }
  }
}
