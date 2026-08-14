/**
 * VENDORED — faithful type surface of `core/intelligence/thalamus/index.ts`.
 * Consumed by helix (index.ts, helix-pipeline.ts) as `ThalamusModule`.
 *
 * Self-contained stub: imports only builtins and shared types from
 * `@cassicore/foundation` (including the real `BaseCognitiveModule`).
 */
import type { Message } from '@cassicore/foundation'
import { BaseCognitiveModule } from '@cassicore/foundation'

/** Temporal registry for a session — tracks timestamps and tool metrics. */
export class TemporalRegistry {
  private messageTimestamps = new Map<number, string>()
  private toolMetrics = new Map<string, { durationMs: number; outputBytes: number }>()
  sessionStart: string = new Date().toISOString()
  lastUserMessageAt: string | null = null

  recordMessage(index: number, timestamp: string, isUser: boolean): void {
    this.messageTimestamps.set(index, timestamp)
    if (isUser) this.lastUserMessageAt = timestamp
  }

  getTimestamp(index: number): string | undefined {
    return this.messageTimestamps.get(index)
  }

  recordToolMetrics(toolCallId: string, durationMs: number, outputBytes: number): void {
    this.toolMetrics.set(toolCallId, { durationMs, outputBytes })
  }

  getToolMetricsMap(): Map<string, { durationMs: number; outputBytes: number }> {
    return new Map(this.toolMetrics)
  }
}

/** Topic summary produced by curation for cross-session sharing. */
export interface CurationTopicSummary {
  id: string
  label: string
  summary: string
  status: 'active' | 'archived'
  keyTerms: string[]
  filesTouched?: string[]
  importanceScore: number
}

/** Curation metadata attached to a curation result. */
export interface CurationMetaData {
  originalCount: number
  curatedCount: number
  originalChars: number
  curatedChars: number
  compressed: number
  deduped: number
  dropped: number
  distilled: number
  gapNotes: number
  durationMs: number
  skipped?: boolean
  reason?: string
  cacheInvalidated: boolean
  topicSummaries?: CurationTopicSummary[]
  [key: string]: unknown
}

/** Result of a curation pass. */
export interface CurationResult {
  messages: Message[]
  meta: CurationMetaData
}

/** Config override surface for curation. */
export interface CurationConfig {
  excludeSessionPrefixes: string[]
  charBudget?: number
  ignitionThreshold?: number
  [key: string]: unknown
}

/**
 * ThalamusModule — context curation and annotation for agent sessions.
 * Reproduces the faithful member surface consumed by helix posture runners.
 */
export class ThalamusModule extends BaseCognitiveModule {
  readonly name = 'thalamus'
  readonly priority = 85

  private temporalRegistries = new Map<string, TemporalRegistry>()

  setLocusBridge(_lb: unknown): void { /* wired dependency */ }
  setCortex(_c: unknown): void { /* wired dependency */ }
  setMnemicField(_mf: unknown): void { /* wired dependency */ }
  setSelfModelField(_smf: unknown): void { /* wired dependency */ }
  setPinealFacets(_fm: unknown): void { /* wired dependency */ }
  setAurora(_a: unknown): void { /* wired dependency */ }
  setPinealAssembler(_pa: unknown): void { /* wired dependency */ }
  setHandleFactory(_fn: unknown): void { /* wired dependency */ }
  setReverieNoteSink(_fn: (sessionId: string, recipient: string, message: string) => void): void {
    /* wired dependency */
  }
  setReverieInferenceProvider(_provider: unknown): void { /* wired dependency */ }

  /**
   * Process a message — attach `_thalamus` annotations with timestamps and
   * metrics, and route through the slot processor.
   */
  process(
    sessionId: string,
    msg: unknown,
    index: number,
    toolMetrics?: Map<string, { durationMs: number; outputBytes: number }>,
    _provenance?: string,
  ): unknown {
    const temporal = this.getTemporalRegistry(sessionId)
    const existingTs = temporal.getTimestamp(index)
    const timestamp = existingTs ?? new Date().toISOString()
    const isUser = (msg as any)?.role === 'user'
    if (!existingTs) temporal.recordMessage(index, timestamp, isUser)
    if (toolMetrics) {
      for (const [id, metrics] of toolMetrics) {
        temporal.recordToolMetrics(id, metrics.durationMs, metrics.outputBytes)
      }
    }
    const content = this.extractContent(msg)
    return {
      ...(msg as object),
      _thalamus: { ts: timestamp, slot: 'assistant', chars: content.length, index },
    }
  }

  getTemporalRegistry(sessionId: string): TemporalRegistry {
    let registry = this.temporalRegistries.get(sessionId)
    if (!registry) {
      registry = new TemporalRegistry()
      this.temporalRegistries.set(sessionId, registry)
    }
    return registry
  }

  /**
   * Curate a message list to fit the context window by scoring and selecting
   * the most relevant messages while preserving the recent window.
   */
  async curate(
    sessionId: string,
    messages: Message[],
    configOverrides?: Partial<CurationConfig>,
  ): Promise<CurationResult> {
    const start = Date.now()
    if (!messages || messages.length === 0) {
      return this.skipResult(messages ?? [], Date.now() - start, 'empty')
    }
    const exclude = configOverrides?.excludeSessionPrefixes ?? []
    if (exclude.some(p => sessionId.startsWith(p))) {
      return this.skipResult(messages, Date.now() - start, 'excluded_session')
    }
    // Faithful marker curation: annotate and return the full message set.
    const annotated = messages.map((msg, i) => {
      const existing = (msg as any)?._thalamus
      if (existing) return msg
      const temporal = this.getTemporalRegistry(sessionId)
      const timestamp = temporal.getTimestamp(i) ?? new Date().toISOString()
      return { ...msg, _thalamus: { ts: timestamp, slot: 'assistant', chars: this.extractContent(msg).length, index: i } }
    })
    return {
      messages: annotated,
      meta: {
        originalCount: messages.length,
        curatedCount: annotated.length,
        originalChars: messages.reduce((sum, m) => sum + this.extractContent(m).length, 0),
        curatedChars: annotated.reduce((sum, m) => sum + this.extractContent(m).length, 0),
        compressed: 0,
        deduped: 0,
        dropped: 0,
        distilled: 0,
        gapNotes: 0,
        durationMs: Date.now() - start,
        cacheInvalidated: false,
        topicSummaries: [],
      },
    }
  }

  /**
   * Assemble cross-session context injections (Mnemic Field retrieval, Aurora,
   * Pineal) for prompt enrichment during inference.
   */
  async assembleInjections(
    _sessionId: string,
    _messages: Message[],
  ): Promise<Array<{ content: string; source: string }>> {
    return []
  }

  protected extractContent(msg: unknown): string {
    const m = msg as { content?: unknown } | undefined
    const content = m?.content
    if (typeof content === 'string') return content
    if (Array.isArray(content)) {
      return content.map(b => {
        const block = b as { type?: string; text?: string; content?: string }
        if (block?.type === 'text') return block.text ?? ''
        if (block?.type === 'tool_result') return block.content ?? ''
        return ''
      }).join('\n')
    }
    return ''
  }

  private skipResult(messages: Message[], durationMs: number, reason: string): CurationResult {
    return {
      messages,
      meta: {
        originalCount: messages.length,
        curatedCount: messages.length,
        originalChars: messages.reduce((sum, m) => sum + this.extractContent(m).length, 0),
        curatedChars: messages.reduce((sum, m) => sum + this.extractContent(m).length, 0),
        compressed: 0,
        deduped: 0,
        dropped: 0,
        distilled: 0,
        gapNotes: 0,
        durationMs,
        skipped: true,
        reason,
        cacheInvalidated: false,
      },
    }
  }
}
