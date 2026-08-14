/**
 * VENDORED — faithful type surface of `core/intelligence/thalamus/cross-session-index.ts`.
 * Consumed by helix (helix-synapse.ts, helix-pipeline.ts) as `CrossSessionTopicIndex`.
 *
 * Self-contained stub: imports only shared types from `@cassicore/foundation`.
 */
import type { ILogger } from '@cassicore/foundation'

/** Minimal local surface of the EmbeddingService used for topic embedding. */
export interface EmbeddingService {
  embed(text: string, kind: 'query' | 'document'): Promise<number[] | null>
  embedBatch(texts: string[], kind: 'document'): Promise<Array<number[] | null>>
}

/** Topic summary produced by a session's Thalamus curation. */
export interface TopicSummary {
  id: string
  label: string
  summary: string
  status: 'active' | 'archived'
  keyTerms: string[]
  filesTouched?: string[]
  importanceScore: number
}

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
  /** Files touched during this work phase */
  filesTouched: string[]
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

export interface FileConflict {
  /** File path with overlapping access */
  file: string
  /** Session IDs that have touched this file */
  sessions: string[]
  /** Map of sessionId → topic labels for that session touching this file */
  sessionTopics: Record<string, string[]>
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

  private entries: CrossSessionTopicEntry[] = []
  private insertionOrder: string[] = []
  private fileSessions = new Map<string, Set<string>>()

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

  async publish(sessionId: string, topics: TopicSummary[]): Promise<void> {
    if (topics.length === 0) return
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
        filesTouched: topic.filesTouched ?? [],
        importanceScore: topic.importanceScore,
        timestamp: now,
        vector: vectors[i],
      }
      this.entries.push(entry)
      for (const file of entry.filesTouched) {
        const sessions = this.fileSessions.get(file) ?? new Set<string>()
        sessions.add(sessionId)
        this.fileSessions.set(file, sessions)
      }
      const orderIdx = this.insertionOrder.indexOf(id)
      if (orderIdx !== -1) this.insertionOrder.splice(orderIdx, 1)
      this.insertionOrder.push(id)
    }

    while (this.entries.length > this.config.maxEntriesPerConstellation) {
      const evictId = this.insertionOrder.shift()
      if (!evictId) break
      const idx = this.entries.findIndex(e => e.id === evictId)
      if (idx !== -1) {
        const evicted = this.entries.splice(idx, 1)[0]
        if (evicted) {
          for (const file of evicted.filesTouched) {
            const sessions = this.fileSessions.get(file)
            if (sessions) {
              sessions.delete(evicted.sessionId)
              if (sessions.size === 0) this.fileSessions.delete(file)
            }
          }
        }
      }
    }
  }

  evictSession(sessionId: string): void {
    const removedEntries = this.entries.filter(e => e.sessionId === sessionId)
    this.entries = this.entries.filter(e => e.sessionId !== sessionId)
    this.insertionOrder = this.insertionOrder.filter(id => !id.startsWith(`${sessionId}::`))
    for (const entry of removedEntries) {
      for (const file of entry.filesTouched) {
        const sessions = this.fileSessions.get(file)
        if (sessions) {
          sessions.delete(sessionId)
          if (sessions.size === 0) {
            this.fileSessions.delete(file)
          }
        }
      }
    }
  }

  async query(queryText: string, opts?: CrossSessionQueryOpts): Promise<CrossSessionTopicEntry[]> {
    if (this.entries.length === 0) return []
    const exclude = new Set(opts?.excludeSessionIds ?? [])
    const limit = opts?.limit ?? 5
    const minScore = opts?.minScore ?? 0.05

    const cappedQuery = queryText.slice(0, 2000)
    let queryVec: number[] | null = null
    if (this.embeddingService) {
      try {
        queryVec = await this.embeddingService.embed(cappedQuery, 'query')
      } catch {
        // Fall back to term overlap
      }
    }
    const queryTerms = this.extractTerms(queryText)
    const scored: ScoredEntry[] = []

    for (const entry of this.entries) {
      if (exclude.has(entry.sessionId)) continue
      let score: number
      if (queryVec && entry.vector) {
        const semantic = this.cosineSimilarity(queryVec, entry.vector)
        const recency = Math.exp(-(Date.now() - entry.timestamp) / (24 * 3600 * 1000))
        const importance = entry.importanceScore
        score = (semantic * 0.6) + (importance * 0.25) + (recency * 0.15)
      } else {
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

    scored.sort((a, b) => b.score - a.score)
    return scored.slice(0, limit).map(s => s.entry)
  }

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

  get size(): number {
    return this.entries.length
  }

  getAll(): CrossSessionTopicEntry[] {
    return [...this.entries]
  }

  detectFileConflicts(sessionIds?: string[]): FileConflict[] {
    const conflicts: FileConflict[] = []
    const idSet = sessionIds ? new Set(sessionIds) : null
    for (const [file, sessions] of this.fileSessions) {
      const relevantSessions = idSet
        ? [...sessions].filter(s => idSet.has(s))
        : [...sessions]
      if (relevantSessions.length < 2) continue
      const sessionTopics = new Map<string, string[]>()
      for (const entry of this.entries) {
        if (!entry.filesTouched.includes(file)) continue
        if (idSet && !idSet.has(entry.sessionId)) continue
        const topics = sessionTopics.get(entry.sessionId) ?? []
        topics.push(entry.label)
        sessionTopics.set(entry.sessionId, topics)
      }
      conflicts.push({
        file,
        sessions: relevantSessions,
        sessionTopics: Object.fromEntries(sessionTopics),
      })
    }
    conflicts.sort((a, b) => b.sessions.length - a.sessions.length)
    return conflicts
  }

  formatConflicts(sessionIds?: string[]): string {
    const conflicts = this.detectFileConflicts(sessionIds)
    if (conflicts.length === 0) return ''
    const MAX_CONFLICTS = 5
    const MAX_CHARS = 800
    const lines: string[] = []
    let chars = 0
    for (const c of conflicts.slice(0, MAX_CONFLICTS)) {
      const sessionTags = c.sessions.map(s => s.length > 12 ? s.slice(0, 12) : s)
      const topicHints = Object.entries(c.sessionTopics)
        .map(([sid, topics]) => {
          const tag = sid.length > 8 ? sid.slice(0, 8) : sid
          return `${tag}: ${topics.slice(0, 2).join(', ')}`
        })
        .join('; ')
      const line = `  ${c.file}\n    Threads: ${sessionTags.join(', ')}\n    Work: ${topicHints}`
      if (chars + line.length + 2 > MAX_CHARS && lines.length > 0) break
      lines.push(line)
      chars += line.length + 2
    }
    if (lines.length === 0) return ''
    return `FILE OVERLAP WARNING\nThe following files are being touched by multiple threads simultaneously. Consider coordinating or splitting responsibility to avoid conflicts and duplicated effort.\n\n${lines.join('\n\n')}`
  }

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

  private extractTerms(text: string): string[] {
    const terms = new Set<string>()
    const capPhrase = /\b([A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){0,3})\b/g
    let m: RegExpExecArray | null
    while ((m = capPhrase.exec(text)) !== null) {
      if (m[1].length >= 3) terms.add(m[1].toLowerCase())
    }
    const camel = /\b([a-z]+[A-Z][a-zA-Z0-9]{2,})\b/g
    while ((m = camel.exec(text)) !== null) {
      terms.add(m[1].toLowerCase())
      const split = m[1].replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase()
      terms.add(split)
    }
    const words = /\b([a-z][a-z0-9_\-]{3,})\b/g
    while ((m = words.exec(text.toLowerCase())) !== null) {
      terms.add(m[1].replace(/[_\-]/g, ' '))
    }
    return [...terms].slice(0, 24)
  }
}
