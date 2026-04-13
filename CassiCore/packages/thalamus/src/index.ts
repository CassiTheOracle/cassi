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
} from './types.js'
import { DEFAULT_CURATION_CONFIG, SIGNAL_TYPE_WEIGHTS, REGION_WEIGHTS, DEFAULT_SLOT_BUDGETS } from './types.js'

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

  private locusBridge: LocusBridge | null = null
  private cortex: CorticalField | null = null
  private mnemicField: MnemicField | null = null
  private selfModelField: SelfModelField | null = null
  private pinealFacets: FacetManager | null = null

  setLocusBridge(lb: LocusBridge): void { this.locusBridge = lb }
  setCortex(c: CorticalField): void { this.cortex = c }
  setMnemicField(mf: MnemicField): void { this.mnemicField = mf }
  setSelfModelField(smf: SelfModelField): void { this.selfModelField = smf }
  setPinealFacets(fm: FacetManager): void { this.pinealFacets = fm }

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

  curate(
    sessionId: string,
    messages: any[],
    configOverrides?: Partial<CurationConfig>,
  ): CurationResult {
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

    // Phase 1: Slot-aware compression — uses _thalamus.tool.class for strategy selection
    const { messages: compressed, compressed: compressedCount, deduped: dedupedCount } =
      this.compressor.compress(annotated, annotated.length, { toolResultMaxChars: cfg.toolResultMaxChars }, session.fileReadMap)

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
    const brainContext = this.buildBrainContext(sessionId, compressed)
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

    const assembled = this.assembleByThreshold(compressed, scored, protectedStart, cfg)

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
      dropped,
      durationMs: meta.durationMs,
    })

    return { messages: assembled.messages, meta }
  }

  getStats(): { sessions: number; totalCurations: number } {
    let totalCurations = 0
    for (const s of this.sessions.values()) {
      totalCurations += s.totalCurations
    }
    return { sessions: this.sessions.size, totalCurations }
  }

  private buildBrainContext(sessionId: string, messages: any[]): BrainContext {
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
    for (let i = messages.length - 1; i >= 0 && seen < 8; i--) {
      const msg = messages[i]
      if (msg?.role !== 'user' && msg?.role !== 'assistant') continue
      seen++
      const content = extractMessageContent(msg)
      for (const term of extractTerms(content)) recentMessageTerms.add(term)
      for (const file of extractFilePaths(content)) recentMessageFiles.add(file)
    }

    const { architecturalTerms, architecturalConcepts, architecturalHits } =
      this.buildSelfModelContext(focusTerms, recentMessageTerms)

    const { pinealTerms, pinealPriorities } = this.buildPinealContext(sessionId)

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
    }
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
  private buildSelfModelContext(focusTerms: Set<string>, recentMessageTerms: Set<string>): {
    architecturalTerms: Set<string>
    architecturalConcepts: Set<string>
    architecturalHits: SelfModelHit[]
  } {
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

      const hits = this.selfModelField.retrieve(sample, { limit: 10 })
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

    this.ensureToolPairs(messages, included, protectedStart)
    this.ensureAlternation(messages, included, protectedStart)

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
          // Time-aware gap note using temporal registry
          const gapDesc = this.buildGapDescription(gapSize, prevIdx, idx, messages)
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
            included.add(bridge)
            break
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
            included.add(bridge)
            break
          }
        }
      }
    }
  }

  private ensureToolPairs(
    messages: any[],
    included: Set<number>,
    protectedStart: number,
  ): void {
    const hasToolUse = (msg: any): boolean =>
      Array.isArray(msg?.content) && msg.content.some((c: any) => c?.type === 'tool_use')
    const hasToolResult = (msg: any): boolean =>
      Array.isArray(msg?.content) && msg.content.some((c: any) => c?.type === 'tool_result')

    for (const idx of Array.from(included)) {
      if (idx >= protectedStart) continue
      const msg = messages[idx]

      if (hasToolUse(msg) && idx + 1 < protectedStart) {
        if (!included.has(idx + 1)) {
          if (hasToolResult(messages[idx + 1])) {
            included.add(idx + 1)
          } else {
            included.delete(idx)
          }
        }
      }

      if (hasToolResult(msg) && idx - 1 >= 0) {
        if (!included.has(idx - 1)) {
          if (hasToolUse(messages[idx - 1])) {
            included.add(idx - 1)
          } else {
            included.delete(idx)
          }
        }
      }
    }

    // Protected boundary: first protected message may be a tool_result
    // whose tool_use companion is in the non-protected region and was dropped
    if (protectedStart > 0 && protectedStart < messages.length) {
      if (hasToolResult(messages[protectedStart]) && !included.has(protectedStart - 1)) {
        if (hasToolUse(messages[protectedStart - 1])) {
          included.add(protectedStart - 1)
        }
      }
    }
  }

  private skipResult(messages: any[], durationMs: number, reason: string): CurationResult {
    return {
      messages,
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
        fileReadMap: new Map(),
        toolUseMap: new Map(),
        lastCuratedAt: Date.now(),
        totalCurations: 0,
      }
      this.sessions.set(sessionId, session)
    }
    return session
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
  private buildGapDescription(gapSize: number, fromIdx: number, toIdx: number, messages: any[]): string {
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
      // tool_call + tool_result = 1 logical tool call
      const logical = Math.ceil(toolCalls / 2)
      if (logical > 0) parts.push(`${logical} tool call${logical > 1 ? 's' : ''}`)
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
