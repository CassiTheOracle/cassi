/**
 * LLM Reranker — alternative to filament-based kindling for memory retrieval.
 *
 * Pipeline:
 *   1. Caller provides (query, top-K candidate engrams) — typically obtained
 *      via cheap embed-recall against the engram ANN index.
 *   2. Reranker chunks each engram into numbered sentences (e.g. A1, A2, B1).
 *   3. Sends a single LLM call asking which sentences are relevant to the query.
 *   4. Parses the response and returns ranked sentence excerpts with their
 *      originating engram IDs.
 *
 * Why this exists:
 *   - The filament index (~700k pre-segmented sentence vectors) costs ~2 GB
 *     of storage and 30s for cold kindling.
 *   - Embedding-based recall is coarse; LLMs reason about query intent.
 *   - With unlimited gpt-5-mini-class models the per-call cost is tractable.
 *
 * The reranker is OPT-IN. MnemicField.retrieve() falls back to kindling if
 * the reranker is disabled or unavailable.
 *
 * Cost / latency profile (typical):
 *   - Recall step:   ~50-100ms (engram ANN search)
 *   - LLM call:      ~500-1500ms (gpt-5-mini, ~2k input tokens, ~200 output)
 *   - Total:         ~1-2s vs ~30s for kindling
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { IProvider, Message } from '../../../types/runtime.js'
import type { Engram, MnemicRetrievalHit } from './types.js'

export interface LLMRerankerConfig {
  /** Provider used for the rerank LLM call. */
  provider: IProvider
  /** Model identifier (e.g. "github-copilot/gpt-5-mini"). */
  model: string
  /** Max sentences to consider across all candidates. Hard cap to avoid blowing context. */
  maxSentences?: number
  /** Max length of each sentence excerpt sent to the LLM (chars). */
  maxSentenceChars?: number
  /** LLM call timeout in ms. */
  timeoutMs?: number
  /** Log prefix tag for source attribution in prompt logging. */
  source?: string
}

const DEFAULT_MAX_SENTENCES = 120
const DEFAULT_MAX_SENTENCE_CHARS = 400
const DEFAULT_TIMEOUT_MS = 8000

/**
 * Split text into sentence-ish chunks. Keeps things simple and deterministic
 * (don't pull in NLP libs). Splits on sentence-final punctuation followed by
 * whitespace + capital letter, plus hard newlines.
 */
export function splitSentences(text: string, maxLen: number): string[] {
  if (!text) return []
  // First split on hard breaks (paragraphs, list items)
  const blocks = text.split(/\n\s*\n+|\n\s*[-*]\s+/g).map(b => b.trim()).filter(Boolean)
  const out: string[] = []
  for (const block of blocks) {
    // Then sentence-split each block. Conservative regex — keeps quoted dots intact.
    const parts = block.split(/(?<=[.!?])\s+(?=[A-Z"'])/g).map(s => s.trim()).filter(Boolean)
    for (const p of parts) {
      if (p.length <= maxLen) {
        out.push(p)
      } else {
        // Long sentence/run-on — chunk it
        for (let i = 0; i < p.length; i += maxLen) {
          out.push(p.slice(i, i + maxLen))
        }
      }
    }
  }
  return out
}

/** Generate a label like "A", "B", ..., "Z", "AA", "AB" for engram index. */
function engramLabel(idx: number): string {
  let n = idx
  let s = ''
  do {
    s = String.fromCharCode(65 + (n % 26)) + s
    n = Math.floor(n / 26) - 1
  } while (n >= 0)
  return s
}

export interface RankedSentence {
  /** Source engram id. */
  engramId: string
  /** Sentence label as sent to the LLM (e.g. "A1"). */
  label: string
  /** The actual text. */
  text: string
  /** Position rank from the LLM (0 = most relevant). */
  rank: number
}

export class LLMReranker {
  private logger: ILogger
  private provider: IProvider
  private model: string
  private maxSentences: number
  private maxSentenceChars: number
  private timeoutMs: number
  private source: string

  constructor(logger: ILogger, config: LLMRerankerConfig) {
    this.logger = logger.child?.('llm-reranker') ?? logger
    this.provider = config.provider
    this.model = config.model
    this.maxSentences = config.maxSentences ?? DEFAULT_MAX_SENTENCES
    this.maxSentenceChars = config.maxSentenceChars ?? DEFAULT_MAX_SENTENCE_CHARS
    this.timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS
    this.source = config.source ?? 'mnemic.reranker'
  }

  /**
   * Rerank candidate engrams against a query, returning the most relevant
   * sentence excerpts. Returns at most `topN` sentences.
   */
  async rerank(
    query: string,
    candidates: Engram[],
    topN: number,
    sessionId?: string,
  ): Promise<RankedSentence[]> {
    if (!candidates.length) return []

    // Build a numbered sentence catalog from the candidate engrams.
    type CatalogEntry = { engramId: string; label: string; text: string }
    const catalog: CatalogEntry[] = []
    let totalSentences = 0

    for (let i = 0; i < candidates.length; i++) {
      if (totalSentences >= this.maxSentences) break
      const eng = candidates[i]
      const eLabel = engramLabel(i)
      const sentences = splitSentences(eng.content || '', this.maxSentenceChars)
      for (let j = 0; j < sentences.length; j++) {
        if (totalSentences >= this.maxSentences) break
        catalog.push({
          engramId: eng.id,
          label: `${eLabel}${j + 1}`,
          text: sentences[j],
        })
        totalSentences++
      }
    }

    if (catalog.length === 0) return []

    const corpus = catalog.map(c => `[${c.label}] ${c.text}`).join('\n')
    const prompt =
      'You select the sentences most relevant to a user query.\n\n' +
      `QUERY: ${query.slice(0, 500)}\n\n` +
      'SENTENCES (each labeled like A1, B3, …):\n' +
      `${corpus}\n\n` +
      `Return JSON with the top ${topN} most relevant sentence labels, in order ` +
      'of relevance (most relevant first). Format:\n' +
      '{"labels":["A2","C1","B4",…]}\n' +
      'Respond with JSON only — no prose.'

    const messages: Message[] = [{ role: 'user', content: prompt }]

    // Use a unique reranker-specific sessionId to avoid provider dedup conflicts.
    // Provider dedup blocks overlapping requests to the same session. Reranker
    // calls are fast and independent, so each needs its own session scope.
    const rerankerSessionId = sessionId ?? `reranker:${Date.now().toString(36)}`

    let fullText = ''
    const start = Date.now()
    try {
      const ac = new AbortController()
      const timer = setTimeout(() => ac.abort(), this.timeoutMs)
      try {
        const stream = this.provider.complete(
          messages,
          {
            model: this.model,
            maxTokens: 400,
            temperature: 0,
            thinking: 'off',
            source: this.source,
            sessionId: rerankerSessionId,
          } as any,
          undefined,
          ac.signal,
        )
        for await (const chunk of stream) {
          if ((chunk as any).type === 'text') fullText += (chunk as any).content ?? ''
          if ((chunk as any).type === 'done') break
        }
      } finally {
        clearTimeout(timer)
      }
    } catch (err) {
      this.logger.warn('LLM rerank call failed', { error: String(err), durationMs: Date.now() - start })
      return []
    }

    // Parse JSON; tolerate code fences and surrounding noise.
    const labels = parseLabels(fullText)
    if (!labels.length) {
      this.logger.debug('LLM rerank produced no parseable labels', { rawLen: fullText.length })
      return []
    }

    const byLabel = new Map(catalog.map(c => [c.label, c]))
    const ranked: RankedSentence[] = []
    for (let r = 0; r < labels.length && ranked.length < topN; r++) {
      const entry = byLabel.get(labels[r])
      if (!entry) continue
      ranked.push({
        engramId: entry.engramId,
        label: entry.label,
        text: entry.text,
        rank: ranked.length,
      })
    }

    this.logger.debug('LLM rerank complete', {
      candidates: candidates.length,
      sentences: catalog.length,
      returned: ranked.length,
      durationMs: Date.now() - start,
    })

    return ranked
  }

  /**
   * Convenience: turn rerank output into MnemicRetrievalHits.
   * Aggregates sentences back to their parent engrams, preserving the best
   * (lowest) rank for the engram and concatenating excerpts.
   */
  static toRetrievalHits(
    candidates: Engram[],
    ranked: RankedSentence[],
    limit: number,
  ): MnemicRetrievalHit[] {
    const engramById = new Map(candidates.map(e => [e.id, e]))
    type Group = { engram: Engram; rank: number; excerpts: string[] }
    const groups = new Map<string, Group>()
    for (const r of ranked) {
      const eng = engramById.get(r.engramId)
      if (!eng) continue
      const existing = groups.get(r.engramId)
      if (existing) {
        existing.excerpts.push(r.text)
        if (r.rank < existing.rank) existing.rank = r.rank
      } else {
        groups.set(r.engramId, { engram: eng, rank: r.rank, excerpts: [r.text] })
      }
    }
    const out: MnemicRetrievalHit[] = []
    const sorted = Array.from(groups.values()).sort((a, b) => a.rank - b.rank)
    for (const g of sorted.slice(0, limit)) {
      const score = 1 - g.rank / Math.max(1, ranked.length) // 0-1, higher = more relevant
      out.push({
        id: g.engram.id,
        content: g.engram.content,
        nodeType: g.engram.nodeType,
        score,
        charge: score,
        potentiation: g.engram.potentiation,
        provenance: g.engram.provenance,
        tags: g.engram.tags,
        metadata: g.engram.metadata,
      })
    }
    return out
  }
}

/** Parse labels from possibly-fenced LLM JSON output. */
function parseLabels(text: string): string[] {
  if (!text) return []
  // Strip code fences
  const cleaned = text.replace(/^```(?:json)?\s*|\s*```\s*$/gm, '').trim()
  // Try direct parse
  try {
    const obj = JSON.parse(cleaned)
    if (Array.isArray(obj?.labels)) return obj.labels.filter((s: unknown): s is string => typeof s === 'string')
  } catch { /* fall through */ }
  // Fallback: pull out the first JSON object substring
  const m = cleaned.match(/\{[\s\S]*?\}/)
  if (m) {
    try {
      const obj = JSON.parse(m[0])
      if (Array.isArray(obj?.labels)) return obj.labels.filter((s: unknown): s is string => typeof s === 'string')
    } catch { /* fall through */ }
  }
  // Last-ditch: grep label-shaped tokens like "A1", "BC23"
  const tokens = cleaned.match(/\b[A-Z]{1,3}\d{1,3}\b/g)
  return tokens ? Array.from(new Set(tokens)) : []
}
