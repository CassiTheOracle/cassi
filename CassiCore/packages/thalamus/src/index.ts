import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { MessageLuminanceScorer, extractTerms, extractFilePaths, extractMessageContent } from './scorer.js'
import { ToolResultCompressor } from './compressor.js'
import { TemporalRegistry } from './temporal.js'
import { createSlots } from './slots/index.js'
import { classifyMessage } from './classifier.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { CorticalField } from '../cortex/index.js'
import type { MnemicField } from '../mnemic-field/index.js'
import type { SelfModelField } from '../mnemic-field/self-model/self-model-field.js'
import type { LocusBridge } from '../locus-bridge/index.js'
import type { FacetManager } from '../pineal/facet.js'
import type { PinealAssembler } from '../pineal/assembler.js'
import type { Aurora } from '../aurora/index.js'
import type {
  CurationConfig,
  CurationResult,
  CurationSession,
  BrainContext,
  ScoredMessage,
  CortexIndex,
  WeightedSignal,
  SelfModelHit,
  MessageSlot,
  SlotContext,
  ThalamusAnnotation,
  MessageSlotType,
  TopicCluster,
} from './types.js'
import { DEFAULT_CURATION_CONFIG, SIGNAL_TYPE_WEIGHTS, REGION_WEIGHTS, DEFAULT_SLOT_BUDGETS } from './types.js'

/** A function that acquires a model handle for background LLM calls. */
type HandleFactory = (config: { tier: string; purpose: string; sessionId: string }) => Promise<{
  complete(messages: Array<{ role: string; content: string }>, opts: Record<string, unknown>): Promise<{ response: string }>
  release(): void
  model: string
}>

const SESSION_EVICT_MS = 2 * 60 * 60 * 1000

/** Format a duration in ms to a human-readable string for gap notes. */
function formatGapDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(0)}s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = Math.floor((ms % 60_000) / 1000)
  if (seconds === 0) return `${minutes}m`
  return `${minutes}m${seconds}s`
}

/**
 * Strip _thalamus annotations from messages before they leave CassiCore.
 * The Anthropic API (and other providers) reject extra fields on message objects
 * with "Extra inputs are not permitted". _thalamus is CassiCore-internal metadata.
 */
function stripThalamusAnnotations(messages: any[]): any[] {
  return messages.map(msg => {
    if (!msg || typeof msg !== 'object') return msg
    const { _thalamus, ...rest } = msg
    return rest
  })
}

export class ThalamusModule extends BaseCognitiveModule {
  readonly name = 'thalamus'
  readonly priority = 85

  private scorer!: MessageLuminanceScorer
  private compressor!: ToolResultCompressor
  private sessions = new Map<string, CurationSession>()
  private evictionTimer: ReturnType<typeof setInterval> | null = null

  /** GWT-style processing slots — one per message type */
  private slots!: MessageSlot[]
  /** Per-session temporal registries */
  private temporalRegistries = new Map<string, TemporalRegistry>()
  /** Per-turn brain context cache — cleared after each curate() call */
  private cachedBrainContext: { sessionId: string; ctx: BrainContext } | null = null

  private locusBridge: LocusBridge | null = null
  private cortex: CorticalField | null = null
  private mnemicField: MnemicField | null = null
  private selfModelField: SelfModelField | null = null
  private pinealFacets: FacetManager | null = null
  private aurora: Aurora | null = null
  private pinealAssembler: PinealAssembler | null = null
  private lastPinealFacetIds: string[] = []
  /** Factory for background LLM calls (topic archiving, gap summaries) */
  private handleFactory: HandleFactory | null = null

  setLocusBridge(lb: LocusBridge): void { this.locusBridge = lb }
  setCortex(c: CorticalField): void { this.cortex = c }
  setMnemicField(mf: MnemicField): void { this.mnemicField = mf }
  setSelfModelField(smf: SelfModelField): void { this.selfModelField = smf }
  setPinealFacets(fm: FacetManager): void { this.pinealFacets = fm }
  setAurora(a: Aurora): void { this.aurora = a }
  setPinealAssembler(pa: PinealAssembler): void { this.pinealAssembler = pa }
  setHandleFactory(fn: HandleFactory): void { this.handleFactory = fn }

  /** Wire a Reverie inference provider into Aurora for the reasoning slow path. */
  setReverieInferenceProvider(provider: import('../aurora/reverie-reasoning-observer.js').ReverieInferenceProvider): void {
    this.aurora?.setReverieInferenceProvider(provider)
  }

  async init(): Promise<void> {
    await super.init()
    this.scorer = new MessageLuminanceScorer(this.logger)
    this.compressor = new ToolResultCompressor(this.logger)
    this.slots = createSlots()
    this.evictionTimer = setInterval(() => this.evictStaleSessions(), SESSION_EVICT_MS / 2)
  }

  async stop(): Promise<void> {
    if (this.evictionTimer) {
      clearInterval(this.evictionTimer)
      this.evictionTimer = null
    }
    this.sessions.clear()
    this.temporalRegistries.clear()
    await super.stop()
  }

  /**
   * Process a message in real-time as it arrives. Routes it to the
   * appropriate slot, attaches _thalamus annotation, and records
   * temporal data.
   *
   * Call this when a message enters the conversation — before it's
   * stored in the message history. Returns the augmented message.
   */
  process(
    sessionId: string,
    msg: any,
    index: number,
    toolMetrics?: Map<string, { durationMs: number; outputBytes: number }>,
  ): any {
    const temporal = this.getTemporalRegistry(sessionId)
    const timestamp = new Date().toISOString()
    const slotType = classifyMessage(msg)
    const isUser = slotType === 'user'

    temporal.recordMessage(index, timestamp, isUser)

    // Record tool metrics if provided (from the executor)
    if (toolMetrics) {
      for (const [id, metrics] of toolMetrics) {
        temporal.recordToolMetrics(id, metrics.durationMs, metrics.outputBytes)
      }
    }

    const ctx: SlotContext = {
      timestamp,
      sessionStart: temporal.sessionStart,
      lastUserMessageAt: temporal.lastUserMessageAt,
      toolMetrics: temporal.getToolMetricsMap(),
      toolUseMap: this.getSession(sessionId).toolUseMap,
      previousMessageTs: index > 0 ? temporal.getTimestamp(index - 1) : null,
    }

    // Route to the matching slot
    const slot = this.slots.find(s => s.matches(msg))
    if (!slot) {
      // Fallback: attach minimal annotation
      return {
        ...msg,
        _thalamus: { ts: timestamp, slot: slotType, chars: extractMessageContent(msg).length },
      }
    }

    return slot.augment(msg, ctx)
  }

  /**
   * Process an array of messages that don't yet have _thalamus annotations.
   * Used when curate() receives un-processed messages (backward compatibility).
   */
  processAll(sessionId: string, messages: any[]): any[] {
    return messages.map((msg, i) => {
      if (msg?._thalamus) return msg // already processed
      return this.process(sessionId, msg, i)
    })
  }

  /**
   * Get the slot instance for a given message type.
   * Useful for external callers that need type-specific rendering.
   */
  getSlot(type: MessageSlotType): MessageSlot | undefined {
    return this.slots.find(s => s.type === type)
  }

  /**
   * Get the temporal registry for a session.
   */
  getTemporalRegistry(sessionId: string): TemporalRegistry {
    let registry = this.temporalRegistries.get(sessionId)
    if (!registry) {
      registry = new TemporalRegistry()
      this.temporalRegistries.set(sessionId, registry)
    }
    return registry
  }

  async curate(
    sessionId: string,
    messages: any[],
    configOverrides?: Partial<CurationConfig>,
  ): Promise<CurationResult> {
    const start = Date.now()

    if (!messages || messages.length === 0) {
      return this.skipResult(messages ?? [], Date.now() - start, 'empty')
    }

    const cfg = { ...DEFAULT_CURATION_CONFIG, ...this.getConfigOverrides(), ...configOverrides }

    // Exclude non-primary sessions
    if (cfg.excludeSessionPrefixes.some(p => sessionId.startsWith(p))) {
      return this.skipResult(messages, Date.now() - start, 'excluded_session')
    }

    const session = this.getSession(sessionId)
    session.totalCurations++
    session.lastCuratedAt = Date.now()

    // Ensure all messages have _thalamus annotations (backward compatibility)
    const annotated = this.processAll(sessionId, messages)

    const originalChars = annotated.reduce(
      (sum: number, m: any) => sum + extractMessageContent(m).length, 0
    )

    // Identify latest reads per file — non-latest reads are suppressed during scoring
    // so they get dropped entirely instead of being summarized.
    // Detect topic clusters before read suppression so we can scope dedup per-topic
    const topicClusters = this.detectTopicClusters(sessionId, annotated)
    const { nonLatestToolUseIds } = this.computeReadSuppression(annotated, topicClusters)

    // Phase 1: Slot-aware compression — uses _thalamus.tool.class for strategy selection
    const { messages: compressed, compressed: compressedCount } =
      this.compressor.compress(annotated, annotated.length, { toolResultMaxChars: cfg.toolResultMaxChars })

    // Phase 2: Enrich with temporal context for scoring
    const temporal = this.getTemporalRegistry(sessionId)
    for (let i = 0; i < compressed.length; i++) {
      const msg = compressed[i]
      if (msg?._thalamus && !msg._thalamus.temporal) {
        const tc = temporal.computeTemporalContext(i)
        if (tc) {
          compressed[i] = { ...msg, _thalamus: { ...msg._thalamus, temporal: tc } }
        }
      }
    }

    // Phase 3: Score with GWT luminance and select by ignition threshold
    const brainContext = await this.getBrainContext(sessionId, compressed)
    const protectedStart = Math.max(0, compressed.length - cfg.recentWindowSize)

    const scored = this.scorer.scoreAll(compressed, brainContext, protectedStart)

    // Apply slot-specific score adjustments
    for (const sm of scored) {
      const msg = compressed[sm.messageIndex]
      const annotation: ThalamusAnnotation | undefined = msg?._thalamus
      if (annotation) {
        const slot = this.slots.find(s => s.type === annotation.slot)
        if (slot) {
          sm.luminance = slot.adjustScore(sm.luminance, annotation)
        }
      }
    }

    // Phase 3b: Zero out scores for redundant (non-latest) file reads.
    // Past reads are dropped entirely during assembly instead of being summarized.
    const dedupedCount = this.suppressRedundantReads(scored, compressed, nonLatestToolUseIds)

    const assembled = this.assembleByThreshold(compressed, scored, protectedStart, cfg, topicClusters, sessionId)

    const curatedChars = assembled.messages.reduce(
      (sum: number, m: any) => sum + extractMessageContent(m).length, 0
    )

    const dropped = compressed.length - assembled.messages.length

    const meta = {
      originalCount: messages.length,
      curatedCount: assembled.messages.length,
      originalChars,
      curatedChars,
      compressed: compressedCount,
      deduped: dedupedCount,
      dropped,
      gapNotes: assembled.gapNotes,
      durationMs: Date.now() - start,
    }

    this.logger.info('Thalamus curated', {
      sessionId,
      original: messages.length,
      curated: assembled.messages.length,
      originalChars,
      curatedChars,
      threshold: cfg.ignitionThreshold,
      phaseCoherence: brainContext.phaseCoherence.toFixed(2),
      dropped,
      durationMs: meta.durationMs,
    })

    // Invalidate brain context cache after curation — each turn gets fresh context
    this.cachedBrainContext = null

    return { messages: stripThalamusAnnotations(assembled.messages), meta }
  }

  getStats(): { sessions: number; totalCurations: number } {
    let totalCurations = 0
    for (const s of this.sessions.values()) {
      totalCurations += s.totalCurations
    }
    return { sessions: this.sessions.size, totalCurations }
  }

  /**
   * Get or build brain context for this session+messages.
   * Caches the result so assembleInjections and curate don't
   * duplicate the expensive buildBrainContext call in the same turn.
   */
  private async getBrainContext(sessionId: string, messages: any[]): Promise<BrainContext> {
    if (this.cachedBrainContext?.sessionId === sessionId) {
      return this.cachedBrainContext.ctx
    }
    const ctx = await this.buildBrainContext(sessionId, messages)
    this.cachedBrainContext = { sessionId, ctx }
    return ctx
  }

  private async buildBrainContext(sessionId: string, messages: any[]): Promise<BrainContext> {
    const foci = this.locusBridge?.getFoci() ?? []
    const focusTerms = new Set<string>()
    const focusFiles = new Set<string>()
    for (const f of foci) {
      if (!f.spark) continue
      for (const term of extractTerms(f.spark.content)) focusTerms.add(term)
      for (const file of extractFilePaths(f.spark.content)) focusFiles.add(file)
      for (const file of (f.spark.relevantFiles ?? [])) focusFiles.add(file)
    }

    const snapshot = this.globalWorkspace?.getSnapshot()
    const workspaceSignals = snapshot?.slots
      ?.filter((s: any) => s.signal !== null)
      ?.map((s: any) => s.signal!) ?? []

    for (const sig of workspaceSignals) {
      for (const term of extractTerms(sig.content)) focusTerms.add(term)
      for (const file of extractFilePaths(sig.content)) focusFiles.add(file)
    }

    const cortexSignals = this.cortex?.readActive({ limit: 30, sessionId }) ?? []
    const cortexIndex = this.buildCortexIndex(cortexSignals, sessionId)
    const affectState = this.cortex?.getAffectState?.() ?? null

    // Add high-salience cortex terms to focus
    for (const ws of cortexIndex.highSalience) {
      for (const term of ws.terms) focusTerms.add(term)
      for (const file of extractFilePaths(ws.signal.content)) focusFiles.add(file)
    }

    // Working memory terms — highest priority cognitive signals
    const workingMemoryTerms = new Set<string>()
    for (const ws of cortexIndex.workingMemory) {
      for (const term of ws.terms) workingMemoryTerms.add(term)
    }

    const mnemonicTerms = new Set<string>()
    if (this.mnemicField) {
      try {
        const topEngrams = this.mnemicField.list(15).filter(e => e.potentiation > 0.5)
        for (const e of topEngrams) {
          for (const term of extractTerms(e.content)) mnemonicTerms.add(term)
        }
      } catch {
        // Degrade gracefully
      }
    }

    const recentMessageTerms = new Set<string>()
    const recentMessageFiles = new Set<string>()
    let seen = 0
    for (let i = messages.length - 1; i >= 0 && seen < 15; i--) {
      const msg = messages[i]
      if (msg?.role !== 'user' && msg?.role !== 'assistant') continue
      seen++
      const content = extractMessageContent(msg)
      for (const term of extractTerms(content)) recentMessageTerms.add(term)
      for (const file of extractFilePaths(content)) recentMessageFiles.add(file)
    }

    const { architecturalTerms, architecturalConcepts, architecturalHits } =
      await this.buildSelfModelContext(focusTerms, recentMessageTerms)

    const { pinealTerms, pinealPriorities } = this.buildPinealContext(sessionId)

    // Phase transition detection: measure overlap between recent conversation
    // and the cortex/focus signals. Low overlap = topic shift → stale signals
    // should be down-weighted so we don't resurface completed work phases.
    const phaseCoherence = this.computePhaseCoherence(
      recentMessageTerms, focusTerms, cortexIndex,
    )

    return {
      foci,
      workspaceSignals,
      focusTerms,
      focusFiles,
      cortexSignals,
      cortexIndex,
      affectState,
      workingMemoryTerms,
      mnemonicTerms,
      architecturalTerms,
      architecturalConcepts,
      architecturalHits,
      pinealTerms,
      pinealPriorities,
      recentMessageTerms,
      recentMessageFiles,
      phaseCoherence,
    }
  }

  /**
   * Build a compact context string for the dialectic engine from the current
   * brain state. Summarizes cortex signals, affect, memory, self-model concepts,
   * focus files, and recent conversation themes into a ~2000-char payload.
   */
  async buildDialecticContext(sessionId: string, messages: any[]): Promise<string> {
    const ctx = await this.getBrainContext(sessionId, messages)
    const parts: string[] = []

    // Cortex signals — what's active in working memory
    if (ctx.cortexIndex.highSalience.length > 0) {
      const signals = ctx.cortexIndex.highSalience.slice(0, 5)
        .map(ws => `[${ws.signal.type}] ${ws.signal.content.slice(0, 120)}`)
        .join('\n')
      parts.push(`Active cognitive signals:\n${signals}`)
    }

    // Affect state — emotional/cognitive tone
    if (ctx.affectState) {
      const a = ctx.affectState as { valence?: number; arousal?: number; dominantEmotion?: string }
      if (a.dominantEmotion) {
        parts.push(`Affect: ${a.dominantEmotion} (valence=${a.valence?.toFixed(2) ?? '?'}, arousal=${a.arousal?.toFixed(2) ?? '?'})`)
      }
    }

    // Attention focus — what files and terms are being worked on
    if (ctx.focusTerms.size > 0) {
      parts.push(`Focus terms: ${[...ctx.focusTerms].slice(0, 15).join(', ')}`)
    }
    if (ctx.focusFiles.size > 0) {
      parts.push(`Focus files: ${[...ctx.focusFiles].slice(0, 8).join(', ')}`)
    }

    // Memory terms — what's been potentiated in the Mnemic Field
    if (ctx.mnemonicTerms.size > 0) {
      parts.push(`Active memories: ${[...ctx.mnemonicTerms].slice(0, 12).join(', ')}`)
    }

    // Architectural self-knowledge — relevant codebase concepts
    if (ctx.architecturalHits.length > 0) {
      const hits = ctx.architecturalHits.slice(0, 4)
        .map(h => `${h.nodeType}: ${h.conceptName}`)
        .join(', ')
      parts.push(`Architectural context: ${hits}`)
    }

    // Identity / pineal priorities
    if (ctx.pinealTerms.size > 0) {
      parts.push(`Identity priorities: ${[...ctx.pinealTerms].slice(0, 8).join(', ')}`)
    }

    // Recent conversation themes
    if (ctx.recentMessageTerms.size > 0) {
      parts.push(`Recent conversation: ${[...ctx.recentMessageTerms].slice(0, 15).join(', ')}`)
    }

    // Working memory threats / concerns
    if (ctx.cortexIndex.threats.length > 0) {
      const threats = ctx.cortexIndex.threats.slice(0, 3)
        .map(ws => ws.signal.content.slice(0, 100))
        .join('; ')
      parts.push(`Active concerns: ${threats}`)
    }

    return parts.join('\n\n')
  }

  /**
   * Assemble context injections from Aurora (cognitive state) and Pineal (identity).
   * Replaces the InjectionAggregator — the Thalamus now owns injection assembly
   * using the same brain context it uses for message scoring.
   */
  async assembleInjections(
    sessionId: string,
    messages: any[],
  ): Promise<Array<{ content: string; source: string }>> {
    const injections: Array<{ content: string; source: string }> = []

    try {
      // Aurora: build cognitive state from current attention foci
      if (this.aurora) {
        const brainContext = await this.getBrainContext(sessionId, messages)

        // Blend focus terms with recent conversation terms, weighted by
        // phase coherence. When coherence is low (topic shift), recent
        // terms dominate so Aurora doesn't build mental state around
        // stale focus from a completed work phase.
        const pc = brainContext.phaseCoherence
        const blended: string[] = []

        // Recent terms always contribute (phase-independent ground truth)
        for (const term of brainContext.recentMessageTerms) {
          blended.push(term)
        }
        // Focus terms contribute proportionally to phase coherence
        if (pc > 0.3) {
          for (const term of brainContext.focusTerms) {
            if (!brainContext.recentMessageTerms.has(term)) {
              blended.push(term)
            }
          }
        }

        const foci = blended.slice(0, 8)

        const state = this.aurora.buildState(foci)
        const text = this.aurora.serialize(state)
        if (text) {
          injections.push({ content: `<aurora>\n${text}\n</aurora>`, source: 'aurora' })
        }
      }

      // Pineal: assemble identity facets
      if (this.pinealAssembler) {
        const { text, facetIds } = this.pinealAssembler.assemble(sessionId)
        if (text) {
          this.lastPinealFacetIds = facetIds
          injections.push({ content: `<pineal>\n${text}\n</pineal>`, source: 'pineal' })
        }
      }
    } catch (err) {
      this.logger.warn('Thalamus injection assembly failed (non-fatal)', {
        sessionId: sessionId.slice(-8),
        error: String(err),
      })
    }

    if (injections.length > 0) {
      this.logger.debug('Thalamus injections assembled', {
        sessionId: sessionId.slice(-8),
        sources: injections.map(i => i.source),
        totalChars: injections.reduce((s, i) => s + i.content.length, 0),
      })
    }

    return injections
  }

  /**
   * Reinforce Pineal facets that were injected on the last turn.
   * Called on turn:end — facets earn conviction through use.
   */
  reinforcePinealFacets(): number {
    if (this.lastPinealFacetIds.length === 0 || !this.pinealFacets) return 0

    const count = this.pinealFacets.reinforceMany(this.lastPinealFacetIds)
    this.lastPinealFacetIds = []
    return count
  }

  /**
   * Forward reasoning to Aurora for cognitive state feedback.
   * Called on turn:end with the assistant's response.
   *
   * Aurora runs a fast path (regex concept extraction + graph activation)
   * and optionally a Reverie slow path (LLM semantic analysis).
   * The reasoning text is persisted as a ReasoningRecord for learning.
   */
  observeReasoning(text: string): void {
    if (!this.aurora) return
    this.aurora.observeReasoning(text)
  }

  /**
   * Measure coherence between recent conversation and the cortex/focus state.
   * Returns 0.0 (total topic shift) to 1.0 (same topic).
   *
   * When the conversation has moved on (e.g., from code review to running tests)
   * but cortex/focus signals still reflect the old phase, this returns a low value.
   * The scorer uses this to down-weight stale focus signals so old completed
   * work phases don't get resurfaced into context.
   */
  private computePhaseCoherence(
    recentTerms: Set<string>,
    focusTerms: Set<string>,
    cortexIndex: CortexIndex,
  ): number {
    if (recentTerms.size === 0) return 1.0 // No recent data → assume coherent

    // Gather all "background state" terms from focus + high-salience cortex
    const backgroundTerms = new Set<string>(focusTerms)
    for (const ws of cortexIndex.highSalience) {
      for (const term of ws.terms) backgroundTerms.add(term)
    }
    for (const ws of cortexIndex.workingMemory) {
      for (const term of ws.terms) backgroundTerms.add(term)
    }

    if (backgroundTerms.size === 0) return 1.0 // No background state → coherent

    // Jaccard-like overlap: what fraction of background terms appear in recent conversation?
    let overlap = 0
    for (const term of backgroundTerms) {
      if (recentTerms.has(term)) overlap++
    }

    const coherence = overlap / backgroundTerms.size
    // Clamp to [0.15, 1.0] — never fully zero (some background context is always useful)
    return Math.max(0.15, Math.min(1.0, coherence))
  }

  /**
   * Build a structured index of cortex signals, categorized by type, region,
   * salience, valence, and working memory state. This enables efficient
   * multi-axis scoring without repeated iteration.
   */
  private buildCortexIndex(signals: import('../cortex/types.js').CorticalSignal[], sessionId: string): CortexIndex {
    const index: CortexIndex = {
      byType: {},
      byRegion: {},
      workingMemory: [],
      highSalience: [],
      threats: [],
    }

    for (const sig of signals) {
      const typeW = SIGNAL_TYPE_WEIGHTS[sig.type] ?? 1.0
      const regionW = REGION_WEIGHTS[sig.region] ?? 1.0
      const weight = Math.min(2.0, sig.salience * sig.confidence * typeW * regionW)
      const terms = extractTerms(sig.content)
      const ws: WeightedSignal = { signal: sig, weight, terms }

      // Group by type
      ;(index.byType[sig.type] ??= []).push(ws)
      // Group by region
      ;(index.byRegion[sig.region] ??= []).push(ws)
      // High salience (above default)
      if (sig.salience > 0.6) index.highSalience.push(ws)
      // Negative valence = threat/concern
      if (sig.valence < -0.2) index.threats.push(ws)
    }

    // Working memory: session-focused signals
    const session = this.cortex?.getSession?.(sessionId)
    if (session) {
      try {
        const wmSignals = session.getWorkingMemory()
        for (const wmSig of wmSignals) {
          const terms = extractTerms(wmSig.content)
          index.workingMemory.push({ signal: wmSig, weight: 1.5, terms })
        }
      } catch {
        // Session may not have working memory
      }
    }

    return index
  }

  /**
   * Query the self-model using current focus terms to find architecturally
   * relevant concepts. Returns enriched terms, concept names, and raw hits.
   * ~4-5ms cost, called once per curation.
   */
  private async buildSelfModelContext(focusTerms: Set<string>, recentMessageTerms: Set<string>): Promise<{
    architecturalTerms: Set<string>
    architecturalConcepts: Set<string>
    architecturalHits: SelfModelHit[]
  }> {
    const empty = { architecturalTerms: new Set<string>(), architecturalConcepts: new Set<string>(), architecturalHits: [] as SelfModelHit[] }
    if (!this.selfModelField) return empty

    try {
      // Sample top focus terms to query the self-model for architectural context
      // Falls back to recent message terms if no focus terms exist yet (cold start)
      let sample = Array.from(focusTerms).slice(0, 6).join(' ')
      if (!sample && recentMessageTerms.size > 0) {
        sample = Array.from(recentMessageTerms).slice(0, 6).join(' ')
      }
      if (!sample) return empty

      const hits = await this.selfModelField.retrieve(sample, { limit: 10 })
      const architecturalTerms = new Set<string>()
      const architecturalConcepts = new Set<string>()
      const architecturalHits: SelfModelHit[] = []

      for (const hit of hits) {
        const conceptName = hit.content.split(' — ')[0]?.trim().toLowerCase() ?? ''
        if (conceptName) architecturalConcepts.add(conceptName)
        for (const term of extractTerms(hit.content)) architecturalTerms.add(term)
        architecturalHits.push({
          content: hit.content,
          score: hit.score,
          nodeType: (hit as any).nodeType ?? 'module',
          conceptName,
        })
      }

      return { architecturalTerms, architecturalConcepts, architecturalHits }
    } catch {
      return empty
    }
  }

  /**
   * Extract high-conviction pineal facets as identity/wisdom terms.
   * Only includes facets with conviction > 0.4 (earned through use).
   * Uses sessionId to include channel-scoped facets for the right channel.
   * ~1ms cost, called once per curation.
   */
  private buildPinealContext(sessionId: string): {
    pinealTerms: Set<string>
    pinealPriorities: Map<string, number>
  } {
    const empty = { pinealTerms: new Set<string>(), pinealPriorities: new Map<string, number>() }
    if (!this.pinealFacets) return empty

    try {
      // Detect channel from session ID prefix for scope-aware facet filtering
      const channel = this.detectChannel(sessionId)
      const facets = this.pinealFacets.list({
        active: true,
        minConviction: 0.4,
        matchScope: channel,
        limit: 30,
      })
      const pinealTerms = new Set<string>()
      const pinealPriorities = new Map<string, number>()

      for (const facet of facets) {
        for (const term of extractTerms(facet.content)) {
          pinealTerms.add(term)
          const existing = pinealPriorities.get(term) ?? 0
          pinealPriorities.set(term, Math.max(existing, facet.conviction))
        }
      }

      return { pinealTerms, pinealPriorities }
    } catch {
      return empty
    }
  }

  /**
   * Extract channel identifier from session ID prefix.
   * Maps "oc:" → "opencode", "mcp:" → "mcp", etc.
   * Returns null for internal/unknown sessions (universal facets only).
   */
  private detectChannel(sessionId: string): string | null {
    const CHANNEL_PREFIXES: Record<string, string> = {
      'oc:': 'opencode', 'mcp:': 'mcp', 'web:': 'web', 'vscode:': 'vscode',
    }
    for (const [prefix, channel] of Object.entries(CHANNEL_PREFIXES)) {
      if (sessionId.startsWith(prefix)) return channel
    }
    return null
  }

  /**
   * Threshold-based assembly: include only messages that ignite.
   * Protected messages (last N) are always included.
   * If ignited messages exceed budget, raise threshold until they fit.
   */
  private assembleByThreshold(
    messages: any[],
    scored: ScoredMessage[],
    protectedStart: number,
    config: CurationConfig,
    topicClusters?: TopicCluster[],
    sessionId?: string,
  ): { messages: any[]; gapNotes: number } {
    let threshold = config.ignitionThreshold

    // Protected messages always included
    const protectedChars = scored
      .filter(s => s.messageIndex >= protectedStart)
      .reduce((sum, s) => sum + s.estimatedChars, 0)

    let remainingBudget = config.charBudget - protectedChars
    if (remainingBudget <= 0) {
      return {
        messages: messages.slice(protectedStart),
        gapNotes: 0,
      }
    }

    // Candidates: older messages that must compete for inclusion
    const candidates = scored
      .filter(s => s.messageIndex < protectedStart)
      .sort((a, b) => b.luminance.composite - a.luminance.composite)

    // Ignition: select candidates above threshold, within budget
    let included = new Set<number>()
    let usedChars = 0

    const selectByThreshold = (t: number): { set: Set<number>; chars: number } => {
      const set = new Set<number>()
      let chars = 0
      for (const s of candidates) {
        if (s.luminance.composite < t) continue
        if (chars + s.estimatedChars > remainingBudget) continue
        set.add(s.messageIndex)
        chars += s.estimatedChars
      }
      return { set, chars }
    }

    const result = selectByThreshold(threshold)
    included = result.set
    usedChars = result.chars

    // If still over budget (shouldn't happen with the check above, but safety), raise threshold
    if (usedChars > remainingBudget) {
      const step = 0.05
      for (let t = threshold + step; t < 1.0; t += step) {
        const retry = selectByThreshold(t)
        if (retry.chars <= remainingBudget) {
          included = retry.set
          break
        }
      }
    }

    // Iterate both repair passes to fixpoint. Each pass can create work for
    // the other: ensureAlternation may bridge a gap with an assistant tool_use
    // whose tool_result isn't included (alternation fixed, pairing broken);
    // ensureToolPairs may delete an orphan pair member (pairing fixed,
    // alternation broken). Cap at 5 iterations — converges in ≤2 in practice.
    for (let pass = 0; pass < 5; pass++) {
      const before = Array.from(included).sort((a, b) => a - b).join(',')
      this.ensureToolPairs(messages, included, protectedStart)
      this.ensureAlternation(messages, included, protectedStart)
      const after = Array.from(included).sort((a, b) => a - b).join(',')
      if (before === after) break
    }

    // Diversity pass: ensure at least one representative per completed topic cluster.
    // This prevents older work phases from being completely erased when their messages
    // all score below the ignition threshold.
    if (topicClusters && topicClusters.length > 1) {
      const scoredByIndex = new Map(scored.map(s => [s.messageIndex, s]))
      // Skip the last (active) cluster — it's covered by protectedStart
      for (let ci = 0; ci < topicClusters.length - 1; ci++) {
        const cluster = topicClusters[ci]
        const clusterOldIndices = cluster.messageIndices.filter(idx => idx < protectedStart)
        if (clusterOldIndices.length === 0) continue
        const hasRepresentative = clusterOldIndices.some(idx => included.has(idx))
        if (!hasRepresentative) {
          // Pick the highest-scored message in this cluster that fits in budget
          const candidates2 = clusterOldIndices
            .map(idx => scoredByIndex.get(idx))
            .filter((s): s is ScoredMessage => s !== undefined && s.luminance.composite > 0)
            .sort((a, b) => b.luminance.composite - a.luminance.composite)
          for (const s of candidates2) {
            if (s.estimatedChars <= remainingBudget - usedChars) {
              included.add(s.messageIndex)
              usedChars += s.estimatedChars
              break
            }
          }
        }
      }
    }

    // Merge included older messages with protected recent messages, in order
    const allIndices = [
      ...Array.from(included).sort((a, b) => a - b),
      ...Array.from({ length: messages.length - protectedStart }, (_, i) => protectedStart + i),
    ]

    const assembled: any[] = []
    let gapNotes = 0

    for (let j = 0; j < allIndices.length; j++) {
      const idx = allIndices[j]
      const prevIdx = j > 0 ? allIndices[j - 1] : idx - 1

      if (idx - prevIdx > 2 && j > 0) {
        const gapSize = idx - prevIdx - 1
        const gapMsg = messages[idx]
        if (gapMsg && Array.isArray(gapMsg.content)) {
          // Time-aware gap note (may include topic archive summary)
          const gapDesc = this.buildGapDescription(gapSize, prevIdx, idx, messages, sessionId)
          const noted = [
            { type: 'text', text: `[${gapDesc}]` },
            ...gapMsg.content,
          ]
          assembled.push({ ...gapMsg, content: noted })
          gapNotes++
          continue
        }
      }

      assembled.push(messages[idx])
    }

    return { messages: assembled, gapNotes }
  }

  private ensureAlternation(
    messages: any[],
    included: Set<number>,
    protectedStart: number,
  ): void {
    const sorted = Array.from(included).sort((a, b) => a - b)

    for (let i = 0; i < sorted.length - 1; i++) {
      const curr = sorted[i]
      const next = sorted[i + 1]
      if (messages[curr]?.role === messages[next]?.role) {
        for (let bridge = curr + 1; bridge < next; bridge++) {
          if (messages[bridge]?.role !== messages[curr]?.role && bridge < protectedStart) {
            if (this.tryAddBridge(messages, included, bridge, protectedStart)) break
          }
        }
      }
    }

    if (sorted.length > 0) {
      const lastOlder = sorted[sorted.length - 1]
      const firstRecent = protectedStart
      if (firstRecent < messages.length && messages[lastOlder]?.role === messages[firstRecent]?.role) {
        for (let bridge = lastOlder + 1; bridge < firstRecent; bridge++) {
          if (messages[bridge]?.role !== messages[lastOlder]?.role) {
            if (this.tryAddBridge(messages, included, bridge, protectedStart)) break
          }
        }
      }
    }
  }

  private tryAddBridge(
    messages: any[],
    included: Set<number>,
    bridge: number,
    protectedStart: number,
  ): boolean {
    const msg = messages[bridge]
    if (!msg) return false
    const content = Array.isArray(msg.content) ? msg.content : null
    const hasToolUse = !!content?.some((c: any) => c?.type === 'tool_use')
    const hasToolResult = !!content?.some((c: any) => c?.type === 'tool_result')

    if (hasToolUse) {
      const partnerIdx = bridge + 1
      if (partnerIdx >= messages.length) return false
      const partner = messages[partnerIdx]
      const partnerOk = Array.isArray(partner?.content) &&
        partner.content.some((c: any) => c?.type === 'tool_result')
      if (!partnerOk) return false
      if (partnerIdx < protectedStart) included.add(partnerIdx)
    }

    if (hasToolResult) {
      const partnerIdx = bridge - 1
      if (partnerIdx < 0) return false
      const partner = messages[partnerIdx]
      const partnerOk = Array.isArray(partner?.content) &&
        partner.content.some((c: any) => c?.type === 'tool_use')
      if (!partnerOk) return false
      if (partnerIdx < protectedStart) included.add(partnerIdx)
    }

    included.add(bridge)
    return true
  }

  private ensureToolPairs(
    messages: any[],
    included: Set<number>,
    protectedStart: number,
  ): void {
    // Build bidirectional maps by tool_use_id so we can find the *actual*
    // partner even when compaction (or summary injection) makes pairs
    // non-consecutive.
    const toolUseIdxById = new Map<string, number>()
    const toolResultIdxById = new Map<string, number>()

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_use' && typeof block.id === 'string') {
          toolUseIdxById.set(block.id, i)
        }
        if (block?.type === 'tool_result' && typeof block.tool_use_id === 'string') {
          toolResultIdxById.set(block.tool_use_id, i)
        }
      }
    }

    const idsInMessage = (msg: any, type: 'tool_use' | 'tool_result'): string[] => {
      if (!Array.isArray(msg?.content)) return []
      return msg.content
        .filter((c: any) => c?.type === type && typeof (type === 'tool_use' ? c.id : c.tool_use_id) === 'string')
        .map((c: any) => (type === 'tool_use' ? c.id : c.tool_use_id))
    }

    // Resolve tool_use messages: every tool_use must have its matching tool_result
    for (const idx of Array.from(included)) {
      if (idx >= protectedStart) continue
      const msg = messages[idx]
      const useIds = idsInMessage(msg, 'tool_use')
      if (useIds.length === 0) continue

      let allPaired = true
      for (const id of useIds) {
        const resultIdx = toolResultIdxById.get(id)
        if (resultIdx === undefined) {
          allPaired = false
          break
        }
        if (resultIdx < protectedStart && !included.has(resultIdx)) {
          included.add(resultIdx)
        }
      }
      if (!allPaired) {
        included.delete(idx)
      }
    }

    // Resolve tool_result messages: every tool_result must have its matching tool_use
    for (const idx of Array.from(included)) {
      if (idx >= protectedStart) continue
      const msg = messages[idx]
      const resultIds = idsInMessage(msg, 'tool_result')
      if (resultIds.length === 0) continue

      let allPaired = true
      for (const id of resultIds) {
        const useIdx = toolUseIdxById.get(id)
        if (useIdx === undefined) {
          allPaired = false
          break
        }
        if (useIdx < protectedStart && !included.has(useIdx)) {
          included.add(useIdx)
        }
      }
      if (!allPaired) {
        included.delete(idx)
      }
    }

    // Protected boundary: fix pairs that cross the protected/candidate line.
    // Case A: tool_result in protected region, tool_use in candidate region
    if (protectedStart > 0 && protectedStart < messages.length) {
      const msg = messages[protectedStart]
      for (const id of idsInMessage(msg, 'tool_result')) {
        const useIdx = toolUseIdxById.get(id)
        if (useIdx !== undefined && useIdx < protectedStart && !included.has(useIdx)) {
          included.add(useIdx)
        }
      }
    }
    // Case B: tool_use in protected region, tool_result in candidate region
    if (protectedStart > 0 && protectedStart < messages.length) {
      const msg = messages[protectedStart]
      for (const id of idsInMessage(msg, 'tool_use')) {
        const resultIdx = toolResultIdxById.get(id)
        if (resultIdx !== undefined && resultIdx < protectedStart && !included.has(resultIdx)) {
          included.add(resultIdx)
        }
      }
    }
  }

  private skipResult(messages: any[], durationMs: number, reason: string): CurationResult {
    return {
      messages: stripThalamusAnnotations(messages),
      meta: {
        originalCount: messages.length,
        curatedCount: messages.length,
        originalChars: 0,
        curatedChars: 0,
        compressed: 0,
        deduped: 0,
        dropped: 0,
        gapNotes: 0,
        durationMs,
        skipped: true,
        reason,
      },
    }
  }

  private getSession(sessionId: string): CurationSession {
    let session = this.sessions.get(sessionId)
    if (!session) {
      session = {
        sessionId,
        toolUseMap: new Map(),
        lastCuratedAt: Date.now(),
        totalCurations: 0,
        topicClusters: [],
        topicArchive: [],
      }
      this.sessions.set(sessionId, session)
    }
    return session
  }

  /**
   * Compute which file-read tool results are the latest for each file.
   * Returns:
   *   - latestResultIndices: indices of tool_result messages that are the latest
   *     read of their file (protected from compression)
   *   - nonLatestToolUseIds: tool_use_ids whose results are NOT the latest read
   *     of their file (to be suppressed during scoring)
   */
  /**
   * Detect topic clusters in the message array using a sliding-window
   * Jaccard similarity approach.  A topic boundary is inferred at user-turn
   * boundaries where the overlap between the preceding N/2 messages and the
   * following N/2 messages drops below BOUNDARY_THRESHOLD.
   *
   * Clusters are stored on the session so async archiving can proceed.
   * Returns the clusters for this curation call.
   */
  private detectTopicClusters(sessionId: string, messages: any[]): TopicCluster[] {
    const WINDOW = 6          // sliding-window size (3 look-back + 3 look-ahead)
    const HALF = WINDOW / 2
    const BOUNDARY_THRESHOLD = 0.12  // Jaccard below this at a user turn → new topic

    // Build term sets per message
    const termSets: Set<string>[] = messages.map(msg => {
      const content = extractMessageContent(msg)
      return new Set(extractTerms(content))
    })

    const clusters: TopicCluster[] = []
    let current: TopicCluster = {
      id: 'topic-0',
      messageIndices: [],
      termSet: new Set(),
      asyncPending: false,
    }

    for (let i = 0; i < messages.length; i++) {
      // Only consider a boundary at user turns after we have enough context
      if (i >= WINDOW && messages[i]?.role === 'user' && current.messageIndices.length >= 2) {
        const prevSet = new Set<string>()
        const nextSet = new Set<string>()
        for (let j = i - WINDOW; j < i - HALF; j++) {
          if (j >= 0) for (const t of termSets[j]) prevSet.add(t)
        }
        for (let j = i - HALF; j < i; j++) {
          if (j >= 0) for (const t of termSets[j]) nextSet.add(t)
        }
        const unionSize = new Set([...prevSet, ...nextSet]).size
        const intersectSize = [...prevSet].filter(t => nextSet.has(t)).length
        const jaccard = unionSize > 0 ? intersectSize / unionSize : 1.0

        if (jaccard < BOUNDARY_THRESHOLD) {
          clusters.push(current)
          current = {
            id: `topic-${clusters.length}`,
            messageIndices: [],
            termSet: new Set(),
            asyncPending: false,
          }
        }
      }
      current.messageIndices.push(i)
      for (const t of termSets[i]) current.termSet.add(t)
    }
    if (current.messageIndices.length > 0) clusters.push(current)

    // Persist on session; fire async archiving for completed (non-last) clusters
    const session = this.getSession(sessionId)
    session.topicClusters = clusters
    for (let k = 0; k < clusters.length - 1; k++) {
      const c = clusters[k]
      const existing = session.topicArchive.find(a => a.id === c.id)
      if (!existing && !c.asyncPending) {
        this.fireTopicArchive(sessionId, c, messages)
      }
    }
    return clusters
  }

  /**
   * Strip reasoning/thinking artifacts some models emit despite instructions.
   * Mirrors SmartCompactionEngine.stripThinkingArtifacts.
   */
  private static stripThinkingArtifacts(text: string): string {
    return text
      .replace(/\*\*[A-Z][^*\n]{8,80}\*\*:?\s*\n*/g, '')
      .replace(/<think>[\s\S]*?<\/think>\s*/gi, '')
      .replace(/Here's a thinking process:[\s\S]*/i, '')
      .replace(/\d+\.\s*Analyze User Input:[\s\S]*/i, '')
      .replace(/\d+\.\s*Task:[\s\S]*/i, '')
      .trim()
  }

  /**
   * Build a heuristic label from the cluster's messages when LLM summarization
   * fails or produces garbage.
   */
  private heuristicTopicLabel(cluster: TopicCluster, messages: any[]): string {
    const userMsgs = cluster.messageIndices
      .map(idx => messages[idx])
      .filter(m => m?.role === 'user')
      .map(m => extractMessageContent(m).trim())
    const seed = userMsgs.find(t => t.length > 10)
    if (seed) return seed.split(/[.!?\n]/)[0].slice(0, 60)
    return Array.from(cluster.termSet).slice(0, 4).join(', ').slice(0, 60)
  }

  private fireTopicArchive(sessionId: string, cluster: TopicCluster, messages: any[]): void {
    if (!this.handleFactory || cluster.asyncPending) return
    cluster.asyncPending = true

    const text = cluster.messageIndices
      .slice(0, 20)
      .map(idx => {
        const msg = messages[idx]
        if (!msg) return ''
        const role = msg.role === 'user' ? 'User' : 'Cassi'
        return `${role}: ${extractMessageContent(msg).slice(0, 300)}`
      })
      .filter(Boolean)
      .join('\n')

    const keyTerms = Array.from(cluster.termSet).slice(0, 10).join(', ')

    this.handleFactory({ tier: 'background', purpose: 'topic-archive', sessionId })
      .then(async (handle) => {
        try {
          const result = await handle.complete(
            [{
              role: 'user',
              content:
                `Summarize this conversation segment in 1-2 sentences. ` +
                `Focus on the main task and key outcome. Output ONLY the summary — ` +
                `no thinking, no numbered steps, no analysis.\n\n` +
                `Key terms: ${keyTerms}\n\nConversation:
${text}`,
            }],
            {
              model: handle.model,
              maxTokens: 120,
              temperature: 0.2,
              systemPrompt:
                'You are a concise summarizer. Output only the requested summary. ' +
                'Never include thinking steps, reasoning, or analysis.',
              thinking: 'none',
              reasoning: 'none',
              source: 'thalamus-topic-archive',
              trigger: 'background',
              sessionId,
            },
          )
          let raw = result.response?.trim() ?? ''
          let summary = ThalamusModule.stripThinkingArtifacts(raw)

          if (!summary || summary.length > 300 || /thinking process|Analyze User Input/i.test(summary)) {
            summary = this.heuristicTopicLabel(cluster, messages)
          }

          const label = summary.split('.')[0]?.slice(0, 60) || `Topic ${cluster.id}`
          cluster.summary = summary
          cluster.label = label
          cluster.asyncPending = false

          const session = this.getSession(sessionId)
          if (!session.topicArchive.find(a => a.id === cluster.id)) {
            session.topicArchive.push({
              id: cluster.id,
              label,
              summary,
              originalIndices: cluster.messageIndices,
              archivedAt: Date.now(),
              keyTerms: Array.from(cluster.termSet).slice(0, 8),
            })
          }
        } catch {
          cluster.asyncPending = false
        } finally {
          handle.release()
        }
      })
      .catch(() => { cluster.asyncPending = false })
  }

    /**
   * Topic-aware read suppression.
   * Within each topic cluster, only the latest read of a given file is kept.
   * Reads of the same file in DIFFERENT topics are preserved — a new topic
   * may legitimately re-read a file that was read in an earlier phase.
   */
  private computeReadSuppression(
    messages: any[],
    topicClusters?: TopicCluster[],
  ): {
    latestResultIndices: Set<number>
    nonLatestToolUseIds: Set<string>
  } {
    const readPattern = /^(Read|cassi_read|cassi_file.*read|mcp__\w+__read)$/i
    const toolUseIdToFile = new Map<string, string>()

    // Build O(1) message-index -> topic-id lookup so the inner loops stay fast
    const idxToTopic = new Map<number, string>()
    if (topicClusters) {
      for (const c of topicClusters) {
        for (const idx of c.messageIndices) idxToTopic.set(idx, c.id)
      }
    }

    // Pass 1: map read tool_use ids to their file paths
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_use' && block.id) {
          const toolName = block.name ?? ''
          if (readPattern.test(toolName)) {
            const fp = block.input?.filePath ?? block.input?.path ?? block.input?.file_path ?? ''
            if (fp) toolUseIdToFile.set(block.id, fp)
          }
        }
      }
    }

    // Build per-topic (or global fallback) fileRead maps
    const getTopicId = (msgIdx: number): string =>
      idxToTopic.get(msgIdx) ?? 'global'

    // Pass 2: track the latest tool_result index for each (topicId, file) pair
    const latestResultByTopicFile = new Map<string, number>()
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_result' && block.tool_use_id) {
          const fp = toolUseIdToFile.get(block.tool_use_id)
          if (fp) {
            const key = `${getTopicId(i)}::${fp}`
            latestResultByTopicFile.set(key, i)
          }
        }
      }
    }

    // Pass 3: identify non-latest tool_use ids (within their topic)
    const nonLatestToolUseIds = new Set<string>()
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_result' && block.tool_use_id) {
          const fp = toolUseIdToFile.get(block.tool_use_id)
          if (fp) {
            const key = `${getTopicId(i)}::${fp}`
            const latestIndex = latestResultByTopicFile.get(key)
            if (latestIndex !== undefined && latestIndex !== i) {
              nonLatestToolUseIds.add(block.tool_use_id)
            }
          }
        }
      }
    }

    return {
      latestResultIndices: new Set(latestResultByTopicFile.values()),
      nonLatestToolUseIds,
    }
  }

  /**
   * Zero out luminance scores for non-latest file reads.
   * Both the tool_result and its paired tool_use are suppressed so that
   * assembly drops them entirely instead of keeping a summary.
   */
  private suppressRedundantReads(
    scored: ScoredMessage[],
    messages: any[],
    nonLatestToolUseIds: Set<string>,
  ): number {
    let suppressed = 0

    for (const sm of scored) {
      const msg = messages[sm.messageIndex]
      if (!Array.isArray(msg?.content)) continue

      const isNonLatest = msg.content.some((block: any) => {
        if (block?.type === 'tool_result' && nonLatestToolUseIds.has(block.tool_use_id)) {
          return true
        }
        if (block?.type === 'tool_use' && nonLatestToolUseIds.has(block.id)) {
          return true
        }
        return false
      })

      if (isNonLatest) {
        sm.luminance = {
          novelty: 0,
          urgency: 0,
          relevance: 0,
          sourceCredibility: 0,
          composite: 0,
        }
        suppressed++
      }
    }

    return suppressed
  }

  private evictStaleSessions(): void {
    const now = Date.now()
    for (const [id, session] of this.sessions) {
      if (now - session.lastCuratedAt > SESSION_EVICT_MS) {
        this.sessions.delete(id)
        this.temporalRegistries.delete(id)
      }
    }
  }

  /**
   * Build a time-aware gap description for omitted turns.
   * Uses temporal annotations if available, falls back to count-only.
   */
  private buildGapDescription(
    gapSize: number,
    fromIdx: number,
    toIdx: number,
    messages: any[],
    sessionId?: string,
  ): string {
    const parts: string[] = [`${gapSize} turn${gapSize > 1 ? 's' : ''}`]

    // Try to compute elapsed time from _thalamus annotations
    const fromTs = messages[fromIdx]?._thalamus?.ts
    const toTs = messages[toIdx]?._thalamus?.ts
    if (fromTs && toTs) {
      const elapsed = new Date(toTs).getTime() - new Date(fromTs).getTime()
      if (elapsed > 0) {
        parts.push(`~${formatGapDuration(elapsed)}`)
      }
    }

    // Count tool calls in the gap
    let toolCalls = 0
    for (let i = fromIdx + 1; i < toIdx; i++) {
      const slotType = messages[i]?._thalamus?.slot
      if (slotType === 'tool_call' || slotType === 'tool_result') toolCalls++
    }
    if (toolCalls > 0) {
      const logical = Math.ceil(toolCalls / 2)
      if (logical > 0) parts.push(`${logical} tool call${logical > 1 ? 's' : ''}`)
    }

    // If a completed topic archive entry covers this gap, include its summary
    if (sessionId) {
      const session = this.getSession(sessionId)
      const matchingArchive = session.topicArchive.find(a =>
        a.originalIndices.some(idx => idx > fromIdx && idx < toIdx)
      )
      if (matchingArchive) {
        const brief = matchingArchive.summary.slice(0, 100)
        parts.push(`topic: ${matchingArchive.label} — ${brief}`)
      }
    }

    parts.push('omitted')
    return parts.join(' · ')
  }

  private getConfigOverrides(): Partial<CurationConfig> {
    if (!this.config) return {}
    const overrides: Partial<CurationConfig> = {}
    const budget = this.config.get('intelligence.thalamus.charBudget', undefined)
    if (budget) overrides.charBudget = budget
    const window = this.config.get('intelligence.thalamus.recentWindowSize', undefined)
    if (window) overrides.recentWindowSize = window
    const maxChars = this.config.get('intelligence.thalamus.toolResultMaxChars', undefined)
    if (maxChars) overrides.toolResultMaxChars = maxChars
    const threshold = this.config.get('intelligence.thalamus.ignitionThreshold', undefined)
    if (threshold) overrides.ignitionThreshold = threshold
    const prefixes = this.config.get('intelligence.thalamus.excludeSessionPrefixes', undefined)
    if (prefixes) overrides.excludeSessionPrefixes = prefixes
    return overrides
  }
}
