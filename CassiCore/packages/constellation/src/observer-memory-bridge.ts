import type { ILogger } from './vendor/types/interfaces.js'


/**
 * Heuristic extractor for concept hints from observer-generated text.
 *
 * Pulls capitalised multi-word phrases plus quoted strings — these are the
 * tokens most likely to overlap with existing Claustrum node labels. Cheap
 * (regex only) and good enough; the Claustrum's `seedFromObservers` does the
 * actual semantic matching.
 *
 * Returned list is deduped, lower-cased, and capped at 8 hints.
 */
export function extractConceptHints(text: string, max = 8): string[] {
  if (!text) return []
  const hints = new Set<string>()

  // Multi-word capitalised phrases (e.g., "Aurora Snapshot Builder").
  const capPhrase = /\b([A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){0,3})\b/g
  let m: RegExpExecArray | null
  while ((m = capPhrase.exec(text)) !== null) {
    if (m[1].length >= 3) hints.add(m[1].toLowerCase())
    if (hints.size >= max * 2) break
  }

  // Quoted strings (often a literal symbol/topic name).
  const quoted = /"([^"\n]{2,40})"|'([^'\n]{2,40})'|`([^`\n]{2,40})`/g
  while ((m = quoted.exec(text)) !== null) {
    const raw = (m[1] ?? m[2] ?? m[3] ?? '').trim()
    if (raw.length >= 3) hints.add(raw.toLowerCase())
    if (hints.size >= max * 2) break
  }

  return [...hints].slice(0, max)
}


/**
 * Map observer broadcast priority to a 0–1 confidence score for the
 * Claustrum node. Extracted here so all three observer layers share one
 * mapping and callers can't accidentally drift.
 */
export function priorityToConfidence(
  priority: string,
  fallback = 0.65,
): number {
  switch (priority) {
    case 'urgent': return 0.85
    case 'ambient': return 0.45
    default: return fallback
  }
}


export interface ObserverMemoryHit {
  id?: string
  content: string
  score?: number
  nodeType?: string
  tags?: string[]
}


export interface ObserverMemorySource {
  retrieve(query: string, options?: { limit?: number; sessionId?: string }): Promise<ObserverMemoryHit[]> | ObserverMemoryHit[]
  store?(input: {
    content: string
    nodeType: string
    tags?: string[]
    provenance?: string
    metadata?: Record<string, unknown>
  }): unknown
}


/**
 * A typed observer insight emitted by cluster/corpus observer layers.
 *
 * Distinct from `rememberObservation` (which writes free-form text into the
 * Mnemic Field). An insight carries enough structure that downstream
 * consumers — chiefly Aurora's Claustrum via the `ClaustrumInsightSink`
 * below — can treat it as a first-class node candidate, not just text.
 *
 * See: docs/design/aurora-extensions-roadmap.md §A3
 */
export interface ObserverInsight {
  /** Stable id used for dedup across re-emissions. Bridge generates one if omitted. */
  readonly id?: string

  /** Short label suitable for use as a CognitiveNode label. */
  readonly label: string

  /** Full content of the observation (what the observer actually said). */
  readonly content: string

  /** Which observer layer produced this (e.g. "cluster", "corpus", "synapse"). */
  readonly layer: string

  /** Constellation/team this came from, when applicable. */
  readonly constellationId?: string

  /** Helix/branch ids that were the subject of the observation, when applicable. */
  readonly subjectHelixIds?: ReadonlyArray<string>

  /** Concepts the observer surfaced — used by Claustrum to attach to existing nodes. */
  readonly concepts?: ReadonlyArray<string>

  /** Observer's stated confidence in the insight (0–1). Defaults to 0.5 if omitted. */
  readonly confidence?: number

  /** Free-form tags for downstream filtering. */
  readonly tags?: ReadonlyArray<string>

  /** Wall-clock timestamp the insight was produced. Bridge stamps if omitted. */
  readonly observedAt?: number
}


/**
 * Sink that consumes typed observer insights as candidate Claustrum nodes.
 *
 * Implemented by Aurora (M2) — kept abstract here so the constellation layer
 * never imports Aurora directly.
 */
export interface ClaustrumInsightSink {
  ingest(insight: ObserverInsight): void
}


export interface ObserverMemoryBridgeOpts {
  source?: ObserverMemorySource
  logger: ILogger
  sessionId?: string
  limit?: number
  minScore?: number
  /** Optional Aurora-side sink. When provided, `emitInsight` fans out to it in addition to the Mnemic store. */
  claustrumSink?: ClaustrumInsightSink
  /**
   * Cap on the in-memory dedup window (number of recent insight ids retained).
   * Default 256 — enough for several minutes of bursty observer output.
   */
  dedupWindow?: number
}


export class ObserverMemoryBridge {
  private source?: ObserverMemorySource
  private logger: ILogger
  private sessionId?: string
  private limit: number
  private minScore: number
  private claustrumSink?: ClaustrumInsightSink
  private dedupWindow: number
  private recentInsightIds: string[] = []
  private recentInsightSet = new Set<string>()

  constructor(opts: ObserverMemoryBridgeOpts) {
    this.source = opts.source
    this.logger = opts.logger.child?.('observer-memory') ?? opts.logger
    this.sessionId = opts.sessionId
    this.limit = opts.limit ?? 5
    this.minScore = opts.minScore ?? 0.25
    this.claustrumSink = opts.claustrumSink
    this.dedupWindow = Math.max(16, opts.dedupWindow ?? 256)
  }

  /** Allow the sink to be wired up after construction (Aurora may not exist yet at bridge init). */
  setClaustrumSink(sink: ClaustrumInsightSink | undefined): void {
    this.claustrumSink = sink
  }

  async recall(query: string, label: string): Promise<string> {
    if (!this.source || !query.trim()) return ''
    try {
      const hits = await Promise.resolve(this.source.retrieve(query, {
        limit: this.limit,
        sessionId: this.sessionId,
      }))
      const filtered = hits
        .filter(h => (h.score ?? 1) >= this.minScore)
        .slice(0, this.limit)
      if (filtered.length === 0) return ''

      const lines = filtered.map((h, idx) => {
        const score = h.score !== undefined ? ` score=${h.score.toFixed(2)}` : ''
        const type = h.nodeType ? `/${h.nodeType}` : ''
        const tags = h.tags?.length ? ` tags=${h.tags.slice(0, 4).join(',')}` : ''
        return `${idx + 1}. [memory${type}${score}${tags}] ${h.content.slice(0, 700)}`
      })
      return `<memory label="${label}">\n${lines.join('\n')}\n</memory>`
    } catch (err) {
      this.logger.debug('Observer memory recall failed', { label, error: String(err) })
      return ''
    }
  }

  rememberObservation(content: string, metadata: Record<string, unknown> = {}): void {
    if (!this.source?.store || !content.trim()) return
    try {
      this.source.store({
        content,
        nodeType: 'pattern',
        provenance: 'observer-layer',
        tags: ['observer', 'constellation', ...(Array.isArray(metadata.tags) ? metadata.tags as string[] : [])],
        metadata,
      })
    } catch (err) {
      this.logger.debug('Observer memory store failed', { error: String(err) })
    }
  }

  /**
   * Emit a typed observer insight. Fans out to:
   *  1. Mnemic store (via `rememberObservation`) — preserves the existing free-form trail.
   *  2. The Claustrum sink, if registered — promotes the insight to a candidate cognitive node.
   *
   * Idempotent within the dedup window: re-emitting an insight with the same id is a no-op
   * for both fanout legs. This is what lets observer layers re-publish on every poll without
   * spamming the graph.
   */
  emitInsight(insight: ObserverInsight): void {
    if (!insight.content.trim()) return

    const id = insight.id ?? this.fingerprint(insight)
    if (this.recentInsightSet.has(id)) return
    this.recordSeen(id)

    const stamped: ObserverInsight = {
      ...insight,
      id,
      observedAt: insight.observedAt ?? Date.now(),
      confidence: insight.confidence ?? 0.5,
    }

    // Fanout 1: Mnemic store — keeps existing observer-memory contract intact.
    this.rememberObservation(stamped.content, {
      insightId: id,
      layer: stamped.layer,
      constellationId: stamped.constellationId,
      subjectHelixIds: stamped.subjectHelixIds,
      concepts: stamped.concepts,
      confidence: stamped.confidence,
      observedAt: stamped.observedAt,
      tags: stamped.tags ? [...stamped.tags] : undefined,
    })

    // Fanout 2: Claustrum sink, if Aurora has wired one up.
    if (this.claustrumSink) {
      try {
        this.claustrumSink.ingest(stamped)
      } catch (err) {
        this.logger.debug('Claustrum insight ingest failed', { id, error: String(err) })
      }
    }
  }

  /**
   * Test/diagnostic helper: how many distinct insights have been seen in the dedup window.
   */
  get dedupSize(): number {
    return this.recentInsightSet.size
  }

  private recordSeen(id: string): void {
    this.recentInsightSet.add(id)
    this.recentInsightIds.push(id)
    while (this.recentInsightIds.length > this.dedupWindow) {
      const evicted = this.recentInsightIds.shift()
      if (evicted !== undefined) this.recentInsightSet.delete(evicted)
    }
  }

  /**
   * Stable fingerprint for an insight without an explicit id.
   * Hashes layer + label + content + constellationId so identical re-emissions collapse.
   * Uses FNV-1a 32-bit — good enough for in-process dedup, no crypto needed.
   */
  private fingerprint(insight: ObserverInsight): string {
    const parts = [
      insight.layer,
      insight.label,
      insight.content,
      insight.constellationId ?? '',
    ].join('\u0001')
    // Uses FNV-1a 32-bit: http://www.isthe.com/chongo/tech/comp/fnv/
    let hash = 0x811c9dc5
    for (let i = 0; i < parts.length; i++) {
      hash ^= parts.charCodeAt(i)
      // FNV prime 0x01000193 expressed as shift-add for readability:
      //   0x01000193 = (1<<0) + (1<<4) + (1<<7) + (1<<8) + (1<<24)
      hash = (hash + ((hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24))) >>> 0
    }
    return `obs_${hash.toString(16).padStart(8, '0')}`
  }
}
