/**
 * Cross-Session Topic Index — Federated Thalamus-curated awareness.
 *
 * Each session's Thalamus detects topic clusters (work phases) and archives
 * completed topics with summaries. This index collects those topic summaries
 * across all sessions in a Constellation and makes them queryable via
 * embedding similarity + importance + recency scoring.
 *
 * Observer layers (Cluster, Corpus) and HelixSynapse query this index to
 * enrich their prompts with cross-session context — what other threads have
 * been working on, what they found, and what's still open.
 *
 * Lifecycle: created per-Constellation by ConstellationPipeline, passed
 * to observer layers and Helix sessions. Garbage-collected when the
 * Constellation stops.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { EmbeddingService } from '../embeddings/embedding-service.js'
import type { TopicSummary } from './types.js'


export interface CrossSessionTopicEntry {
  /** Unique id: "${sessionId}::${topicId}" */
  id: string
  /** Constellation this entry belongs to */
  constellationId: string
  /** Session that produced this topic */
  sessionId: string
  /** Short topic label (LLM-generated or heuristic) */
  label: string
  /** 1-2 sentence summary of what happened in this work phase */
  summary: string
  /** Whether the topic is still active or has been archived */
  status: 'active' | 'archived'
  /** Key terms extracted from the topic's messages */
  keyTerms: string[]
  /** Average luminance (composite) of messages in this topic, 0-1 */
  importanceScore: number
  /** Unix ms when this entry was last updated */
  timestamp: number
  /** Pre-computed embedding of "${label}: ${summary}" */
  vector: number[] | null
}


export interface CrossSessionIndexConfig {
  /** Maximum entries per constellation before LRU eviction. Default: 100 */
  maxEntriesPerConstellation: number
}


export const DEFAULT_CROSS_SESSION_CONFIG: CrossSessionIndexConfig = {
  maxEntriesPerConstellation: 100,
}


export interface CrossSessionQueryOpts {
  /** Session IDs to exclude from results (e.g., the caller's own session) */
  excludeSessionIds?: string[]
  /** Maximum results to return. Default: 5 */
  limit?: number
  /** Minimum score threshold for inclusion. Default: 0.05 */
  minScore?: number
}


interface ScoredEntry {
  entry: CrossSessionTopicEntry
  score: number
}


export class CrossSessionTopicIndex {
  private constellationId: string
  private embeddingService: EmbeddingService | null
  private config: CrossSessionIndexConfig
  private logger: ILogger

  /** constellationId → entries */
  private entries: CrossSessionTopicEntry[] = []
  /** Insertion order for LRU eviction */
  private insertionOrder: string[] = []

  constructor(opts: {
    constellationId: string
    embeddingService?: EmbeddingService
    logger: ILogger
    config?: Partial<CrossSessionIndexConfig>
  }) {
    this.constellationId = opts.constellationId
    this.embeddingService = opts.embeddingService ?? null
    this.config = { ...DEFAULT_CROSS_SESSION_CONFIG, ...opts.config }
    this.logger = (opts.logger.child?.(`cross-session-index:${opts.constellationId}`) ?? opts.logger)
  }


  /**
   * Publish topic summaries from a session's Thalamus curation.
   *
   * Embeds topic summaries in batch, upserts entries (idempotent), and
   * evicts stale entries if over the cap.
   */
  async publish(sessionId: string, topics: TopicSummary[]): Promise<void> {
    if (topics.length === 0) return

    // Embed all topic summaries in one batch
    const texts = topics.map(t => `${t.label}: ${t.summary}`)
    let vectors: Array<number[] | null> = []

    if (this.embeddingService) {
      try {
        vectors = await this.embeddingService.embedBatch(texts, 'document')
      } catch (err) {
        this.logger.warn('Cross-session embedding failed, storing without vectors', {
          sessionId,
          error: String(err),
        })
        vectors = topics.map(() => null)
      }
    } else {
      vectors = topics.map(() => null)
    }

    const now = Date.now()

    for (let i = 0; i < topics.length; i++) {
      const topic = topics[i]
      const id = `${sessionId}::${topic.id}`

      // Remove old entry if upserting
      const existingIdx = this.entries.findIndex(e => e.id === id)
      if (existingIdx !== -1) {
        this.entries.splice(existingIdx, 1)
      }

      const entry: CrossSessionTopicEntry = {
        id,
        constellationId: this.constellationId,
        sessionId,
        label: topic.label,
        summary: topic.summary,
        status: topic.status,
        keyTerms: topic.keyTerms,
        importanceScore: topic.importanceScore,
        timestamp: now,
        vector: vectors[i],
      }

      this.entries.push(entry)

      // Track insertion order for LRU
      const orderIdx = this.insertionOrder.indexOf(id)
      if (orderIdx !== -1) this.insertionOrder.splice(orderIdx, 1)
      this.insertionOrder.push(id)
    }

    // LRU eviction
    while (this.entries.length > this.config.maxEntriesPerConstellation) {
      const evictId = this.insertionOrder.shift()
      if (!evictId) break
      const idx = this.entries.findIndex(e => e.id === evictId)
      if (idx !== -1) this.entries.splice(idx, 1)
    }
  }


  /**
   * Remove all entries for a session (e.g., when a session ends).
   */
  evictSession(sessionId: string): void {
    this.entries = this.entries.filter(e => e.sessionId !== sessionId)
    this.insertionOrder = this.insertionOrder.filter(id => !id.startsWith(`${sessionId}::`))
  }


  /**
   * Query the index for topics semantically related to the given text.
   *
   * Uses embedding cosine similarity when available, falling back to
   * Jaccard term overlap when vectors are absent.
   */
  async query(queryText: string, opts?: CrossSessionQueryOpts): Promise<CrossSessionTopicEntry[]> {
    if (this.entries.length === 0) return []

    const exclude = new Set(opts?.excludeSessionIds ?? [])
    const limit = opts?.limit ?? 5
    const minScore = opts?.minScore ?? 0.05

    // Embed the query
    let queryVec: number[] | null = null
    if (this.embeddingService) {
      try {
        queryVec = await this.embeddingService.embed(queryText, 'query')
      } catch {
        // Fall back to term overlap
      }
    }

    // Extract query terms for fallback matching
    const queryTerms = this.extractTerms(queryText)

    // Score each entry
    const scored: ScoredEntry[] = []

    for (const entry of this.entries) {
      if (exclude.has(entry.sessionId)) continue

      let score: number

      if (queryVec && entry.vector) {
        // Primary: cosine similarity
        const semantic = this.cosineSimilarity(queryVec, entry.vector)
        const recency = Math.exp(-(Date.now() - entry.timestamp) / (24 * 3600 * 1000))
        const importance = entry.importanceScore
        score = (semantic * 0.6) + (importance * 0.25) + (recency * 0.15)
      } else {
        // Fallback: Jaccard term overlap
        const entryTerms = new Set(entry.keyTerms.map(t => t.toLowerCase()))
        const qTerms = new Set(queryTerms.map(t => t.toLowerCase()))
        const intersection = [...entryTerms].filter(t => qTerms.has(t)).length
        const union = new Set([...entryTerms, ...qTerms]).size
        const jaccard = union > 0 ? intersection / union : 0
        const recency = Math.exp(-(Date.now() - entry.timestamp) / (24 * 3600 * 1000))
        const importance = entry.importanceScore
        score = (jaccard * 0.5) + (importance * 0.3) + (recency * 0.2)
      }

      if (score >= minScore) {
        scored.push({ entry, score })
      }
    }

    // Sort by score descending, take top N
    scored.sort((a, b) => b.score - a.score)
    return scored.slice(0, limit).map(s => s.entry)
  }


  /**
   * Format query results into a compact human-readable string for prompt injection.
   * Returns empty string if no results. Output is capped at ~1200 chars to avoid
   * blowing observer token budgets.
   */
  async queryFormatted(queryText: string, opts?: CrossSessionQueryOpts): Promise<string> {
    const results = await this.query(queryText, opts)
    if (results.length === 0) return ''

    const MAX_CHARS = 1200
    const lines: string[] = []
    let chars = 0

    for (const entry of results) {
      const sessionTag = entry.sessionId.length > 12
        ? entry.sessionId.slice(0, 12)
        : entry.sessionId
      const statusTag = entry.status === 'archived' ? '(completed)' : '(active)'
      const termsPreview = entry.keyTerms.slice(0, 5).join(', ')
      const importance = `importance: ${entry.importanceScore.toFixed(2)}`
      const line = `[${sessionTag}] ${entry.label} ${statusTag}\n  Terms: ${termsPreview} | ${importance}\n  ${entry.summary}`

      if (chars + line.length + 2 > MAX_CHARS && lines.length > 0) break
      lines.push(line)
      chars += line.length + 2
    }

    return lines.join('\n\n')
  }


  /** Current entry count */
  get size(): number {
    return this.entries.length
  }


  /** Get all entries (for debugging / admin API) */
  getAll(): CrossSessionTopicEntry[] {
    return [...this.entries]
  }


  // --- Private helpers ---

  private cosineSimilarity(a: number[], b: number[]): number {
    if (!a || !b || a.length !== b.length) return 0
    let dot = 0, ma = 0, mb = 0
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i]
      ma += a[i] * a[i]
      mb += b[i] * b[i]
    }
    if (ma === 0 || mb === 0) return 0
    return dot / (Math.sqrt(ma) * Math.sqrt(mb))
  }


  /** Simple term extraction for fallback matching */
  private extractTerms(text: string): string[] {
    const terms = new Set<string>()
    // Multi-word capitalised phrases (e.g., "File Watcher", "Event Emitter")
    const capPhrase = /\b([A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){0,3})\b/g
    let m: RegExpExecArray | null
    while ((m = capPhrase.exec(text)) !== null) {
      if (m[1].length >= 3) terms.add(m[1].toLowerCase())
    }
    // CamelCase / PascalCase words (e.g., "fileWatcher", "FileWatcher")
    const camel = /\b([a-z]+[A-Z][a-zA-Z0-9]{2,})\b/g
    while ((m = camel.exec(text)) !== null) {
      terms.add(m[1].toLowerCase())
      // Also add the split form
      const split = m[1].replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase()
      terms.add(split)
    }
    // Individual words and kebab/snake identifiers (≥4 chars)
    const words = /\b([a-z][a-z0-9_\-]{3,})\b/g
    while ((m = words.exec(text.toLowerCase())) !== null) {
      terms.add(m[1].replace(/[_\-]/g, ' '))
    }
    return [...terms].slice(0, 24)
  }
}
