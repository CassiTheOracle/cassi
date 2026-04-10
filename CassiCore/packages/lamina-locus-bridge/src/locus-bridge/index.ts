/**
 * LocusBridge — Persistent attentional context assembly
 *
 * A standalone GWT-based attentional service running in the daemon process.
 * Maintains 5 capacity-limited Focus slots that track what the system is
 * paying attention to across the session. These foci drive proactive context
 * assembly: every API request gets a context window assembled from scratch
 * within a configurable token budget.
 *
 * Key differences from Constellation's Locus:
 *   - Input: session events (prompts, tool results), not BranchDigest diffs
 *   - No topology graph — session context instead of branch distances
 *   - Longer occupancy decay (15 ticks — turns are slower than sweeps)
 *   - Persists to KV store, not ConstellationStore
 *   - Drives context assembly, not branch guidance
 *
 * Named after the locus coeruleus — modulates attention across the cortex.
 * The bridge extends this modulation beyond Constellation to the entire system.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  AssembledWindow,
  AssemblyMeta,
  BridgeEclipseEvent,
  BridgeFocus,
  BridgeKindlingEvent,
  BridgeLuminanceScore,
  BridgeSpark,
  BridgeSparkType,
  CuratedContext,
  LocusBridgeConfig,
  LocusBridgePersistedState,
  LocusBridgeSnapshot,
} from './types.js'
import { DEFAULT_LOCUS_BRIDGE_CONFIG, DEFAULT_BRIDGE_LUMINANCE_WEIGHTS } from './types.js'
import { BridgeSparkExtractor, BASE_URGENCY, BASE_NOVELTY } from './spark-extractor.js'
import { ContextCurator } from './context-curator.js'
import type { MemoryRetriever, IntelligenceSignalProvider } from './context-curator.js'
import { HistoryScorer } from './history-scorer.js'
import { WindowAssembler } from './window-assembler.js'

let eventCounter = 0
function nextEventId(): string {
  return `bridge-kindle-${++eventCounter}-${Date.now().toString(36)}`
}


export interface LocusBridgeDeps {
  logger: ILogger
  config?: Partial<LocusBridgeConfig>
  memory?: MemoryRetriever
  signalProvider?: IntelligenceSignalProvider
  /** KV store for persistence (get/set/del) */
  kvStore?: {
    get(key: string): any
    set(key: string, value: any, ttl?: number): void
  }
}


export class LocusBridge {
  private foci: BridgeFocus[]
  private config: LocusBridgeConfig
  private logger: ILogger
  private sparkExtractor: BridgeSparkExtractor
  private curator: ContextCurator
  private historyScorer: HistoryScorer
  private assembler: WindowAssembler
  private kindlingHistory: BridgeKindlingEvent[] = []
  private totalSparksProcessed = 0
  private totalKindlings = 0
  private kvStore?: LocusBridgeDeps['kvStore']

  constructor(deps: LocusBridgeDeps) {
    this.config = { ...DEFAULT_LOCUS_BRIDGE_CONFIG, ...deps.config }
    this.logger = deps.logger.child?.('locus-bridge') ?? deps.logger
    this.kvStore = deps.kvStore

    this.foci = Array.from({ length: this.config.foci }, (_, i) => ({
      slotIndex: i,
      spark: null,
      occupiedSince: null,
      occupancyTicks: 0,
    }))

    this.sparkExtractor = new BridgeSparkExtractor({ logger: this.logger })
    this.curator = new ContextCurator({
      logger: this.logger,
      config: this.config,
      memory: deps.memory,
      signalProvider: deps.signalProvider,
    })
    this.historyScorer = new HistoryScorer({ logger: this.logger })
    this.assembler = new WindowAssembler({ logger: this.logger, config: this.config })

    // Restore persisted state
    this.restore()

    this.logger.info('LocusBridge initialized', {
      foci: this.config.foci,
      kindlingThreshold: this.config.kindlingThreshold,
      tokenBudget: this.config.tokenBudget,
      enabled: this.config.enabled,
    })
  }


  // --- Public API ---

  /**
   * Submit a spark and evaluate it against current foci.
   * Returns kindling events for sparks that won Focus slots.
   */
  submitSpark(spark: BridgeSpark): BridgeKindlingEvent[] {
    if (!this.config.enabled) return []

    this.totalSparksProcessed++

    // Decay occupants every spark submission
    this.decayOccupants()

    // Score the spark
    spark.luminance = this.scoreLuminance(spark)

    // Filter dim sparks
    if (spark.luminance.composite < this.config.kindlingThreshold) {
      this.logger.debug('Spark too dim', {
        sparkId: spark.sparkId,
        composite: spark.luminance.composite,
        threshold: this.config.kindlingThreshold,
      })
      return []
    }

    // Try to kindle
    const event = this.tryKindle(spark)
    if (event) {
      this.totalKindlings++
      this.kindlingHistory.push(event)
      this.trimHistory()

      // Record task boundary if significant eclipses occurred
      this.historyScorer.recordKindlingEvents([event], this.totalSparksProcessed)

      this.persist()

      this.logger.info('Spark kindled', {
        sparkId: spark.sparkId,
        type: spark.type,
        slotIndex: event.slotIndex,
        luminance: spark.luminance.composite.toFixed(3),
        eclipse: event.eclipse ? event.eclipse.eclipsedSpark.sparkId : null,
      })

      return [event]
    }

    return []
  }

  /**
   * Submit a batch of sparks and evaluate them.
   */
  submitSparks(sparks: BridgeSpark[]): BridgeKindlingEvent[] {
    const events: BridgeKindlingEvent[] = []
    for (const spark of sparks) {
      events.push(...this.submitSpark(spark))
    }
    return events
  }

  /**
   * Generate and submit a spark from a user prompt.
   */
  sparkFromUserPrompt(sessionId: string, content: string, goal?: string): BridgeKindlingEvent[] {
    const spark = this.sparkExtractor.fromUserPrompt(sessionId, content, goal)
    return this.submitSpark(spark)
  }

  /**
   * Generate and submit a spark from a tool result.
   */
  sparkFromToolResult(
    sessionId: string,
    toolName: string,
    content: string,
    goal?: string,
  ): BridgeKindlingEvent[] {
    const spark = this.sparkExtractor.fromToolResult(sessionId, toolName, content, goal)
    if (!spark) return []
    return this.submitSpark(spark)
  }

  /**
   * Generate and submit a spark from a code reference.
   */
  sparkFromCodeReference(
    sessionId: string,
    filePath: string,
    action: string,
    content?: string,
    goal?: string,
  ): BridgeKindlingEvent[] {
    const spark = this.sparkExtractor.fromCodeReference(sessionId, filePath, action, content, goal)
    return this.submitSpark(spark)
  }

  /**
   * Assemble a complete context window.
   * This is the main entry point for API request context construction.
   */
  async assemble(
    messages: any[],
    systemPromptBase: string[],
    sessionId: string,
  ): Promise<AssembledWindow> {
    if (!this.config.enabled) {
      return {
        systemContext: [],
        messages,
        meta: this.emptyMeta(messages.length),
      }
    }

    // Curate context from current foci and recent messages
    const curated = await this.curator.curate(this.foci, messages)

    // Score all history turns
    const scoredTurns = this.historyScorer.scoreTurns(messages, this.foci)

    // Assemble within budget
    return this.assembler.assemble(
      systemPromptBase,
      curated,
      scoredTurns,
      messages,
      this.foci,
    )
  }

  /**
   * Get curated context only (without history assembly).
   */
  async curate(messages?: any[]): Promise<CuratedContext> {
    return this.curator.curate(this.foci, messages)
  }

  /**
   * Get current state snapshot.
   */
  getSnapshot(): LocusBridgeSnapshot {
    return {
      foci: this.foci.map(f => ({ ...f })),
      recentKindlings: this.kindlingHistory.slice(-20),
      totalSparksProcessed: this.totalSparksProcessed,
      totalKindlings: this.totalKindlings,
      kindlingRate: this.totalSparksProcessed > 0
        ? this.totalKindlings / this.totalSparksProcessed
        : 0,
      taskBoundaries: this.historyScorer.getTaskBoundaries(),
      lastAssemblyMeta: this.assembler.getLastMeta(),
      snapshotAt: Date.now(),
    }
  }

  /**
   * Get current foci state.
   */
  getFoci(): BridgeFocus[] {
    return this.foci.map(f => ({ ...f }))
  }

  /**
   * Wire the memory retriever (may be wired after construction).
   */
  setMemoryRetriever(memory: MemoryRetriever): void {
    this.curator.setMemoryRetriever(memory)
  }

  /**
   * Wire the intelligence signal provider.
   */
  setSignalProvider(provider: IntelligenceSignalProvider): void {
    this.curator.setSignalProvider(provider)
  }

  onEventBus(bus: { on(eventType: string, handler: (event: unknown) => void): void }): void {
    bus.on('worker:message' as any, (event: unknown) => {
      try {
        if (!this.config.enabled) return
        const e = event as Record<string, unknown>
        const payload = (e?.payload ?? e) as Record<string, unknown>
        const payloadType = payload?.type ?? e?.type

        if (payloadType === 'turn:tool_result') {
          const sessionId = String(payload?.sessionId ?? 'unknown')
          const content = String(payload?.content ?? '')
          const toolName = String(payload?.tool ?? 'unknown')
          if (content) {
            this.sparkFromToolResult(sessionId, toolName, content.slice(0, 2000))
          }
        }
      } catch { /* non-blocking */ }
    })

    bus.on('turn:start' as any, (event: unknown) => {
      try {
        if (!this.config.enabled) return
        const e = event as Record<string, unknown>
        const sessionId = String(e?.sessionId ?? 'unknown')
        const message = String(e?.message ?? '')
        if (message) {
          this.sparkFromUserPrompt(sessionId, message)
        }
      } catch { /* non-blocking */ }
    })
  }

  /**
   * Check if the bridge is enabled.
   */
  get enabled(): boolean {
    return this.config.enabled
  }

  /**
   * Reset all state (for testing).
   */
  reset(): void {
    for (const focus of this.foci) {
      focus.spark = null
      focus.occupiedSince = null
      focus.occupancyTicks = 0
    }
    this.kindlingHistory = []
    this.totalSparksProcessed = 0
    this.totalKindlings = 0
    this.sparkExtractor.reset()
    this.historyScorer.reset()
    this.assembler.reset()
    eventCounter = 0
  }


  // --- Private: Kindling Engine ---

  /**
   * Try to kindle a spark into a focus slot.
   */
  private tryKindle(spark: BridgeSpark): BridgeKindlingEvent | null {
    const now = Date.now()

    // Try empty focus first
    const emptyFocus = this.foci.find(f => f.spark === null)
    if (emptyFocus) {
      emptyFocus.spark = spark
      emptyFocus.occupiedSince = now
      emptyFocus.occupancyTicks = 0

      return {
        eventId: nextEventId(),
        spark,
        slotIndex: emptyFocus.slotIndex,
        eclipse: null,
        kindlingLuminance: spark.luminance.composite,
        timestamp: now,
      }
    }

    // All occupied — try to eclipse the dimmest
    const dimmestFocus = this.findDimmestFocus()
    if (!dimmestFocus?.spark) return null

    const effectiveLum = this.effectiveLuminance(dimmestFocus)
    if (spark.luminance.composite > effectiveLum + this.config.eclipseMargin) {
      const eclipsedSpark = dimmestFocus.spark
      const eclipse: BridgeEclipseEvent = {
        eclipsedSpark,
        eclipsingSpark: spark,
        luminanceDelta: spark.luminance.composite - effectiveLum,
        occupancyAtEclipse: dimmestFocus.occupancyTicks,
      }

      dimmestFocus.eclipsedSparkId = eclipsedSpark.sparkId
      dimmestFocus.spark = spark
      dimmestFocus.occupiedSince = now
      dimmestFocus.occupancyTicks = 0

      return {
        eventId: nextEventId(),
        spark,
        slotIndex: dimmestFocus.slotIndex,
        eclipse,
        kindlingLuminance: spark.luminance.composite,
        timestamp: now,
      }
    }

    return null
  }

  /**
   * Find the focus with the lowest effective luminance.
   */
  private findDimmestFocus(): BridgeFocus | null {
    let dimmest: BridgeFocus | null = null
    let lowestLum = Infinity

    for (const focus of this.foci) {
      if (!focus.spark) continue
      const eff = this.effectiveLuminance(focus)
      if (eff < lowestLum) {
        lowestLum = eff
        dimmest = focus
      }
    }

    return dimmest
  }

  /**
   * Effective luminance decays with occupancy.
   * Linear decay: lose 7% per tick, min 20% of original.
   * Slower decay than Constellation (7% vs 10%) — turns are slower than sweeps.
   */
  private effectiveLuminance(focus: BridgeFocus): number {
    if (!focus.spark) return 0
    const base = focus.spark.luminance.composite
    if (focus.occupancyTicks <= 0) return base
    const decayFactor = Math.max(0.2, 1.0 - (focus.occupancyTicks * 0.07))
    return base * decayFactor
  }

  /**
   * Increment occupancy ticks on all occupied foci.
   */
  private decayOccupants(): void {
    for (const focus of this.foci) {
      if (focus.spark) {
        focus.occupancyTicks++
        if (focus.occupancyTicks > this.config.maxOccupancyTicks) {
          this.logger.info('Focus expired', {
            slotIndex: focus.slotIndex,
            sparkId: focus.spark.sparkId,
            ticks: focus.occupancyTicks,
          })
          focus.spark = null
          focus.occupiedSince = null
          focus.occupancyTicks = 0
        }
      }
    }
  }


  // --- Private: Luminance Scoring ---

  /**
   * Score a bridge spark's luminance.
   * Adapted from Constellation's KindlingEngine — uses relevance
   * (to active foci content) instead of cross-relevance (topology).
   */
  private scoreLuminance(spark: BridgeSpark): BridgeLuminanceScore {
    const w = this.config.luminanceWeights

    // Novelty: base + content richness + how different from current foci
    const baseNovelty = BASE_NOVELTY[spark.type]
    const contentRichness = Math.min(spark.content.length / 200, 1.0) * 0.15
    const fociDifference = this.fociNoveltyModulation(spark)
    const novelty = Math.min(1.0, baseNovelty + contentRichness + fociDifference)

    // Urgency: base type urgency
    const urgency = BASE_URGENCY[spark.type]

    // Relevance: overlap with active foci files and content
    const relevance = this.relevanceToFoci(spark)

    // Source credibility: default 0.5 (no GlobalWorkspace integration yet)
    const sourceCredibility = 0.5

    const composite = Math.min(1.0,
      w.novelty * novelty +
      w.urgency * urgency +
      w.relevance * relevance +
      w.sourceCredibility * sourceCredibility,
    )

    return { novelty, urgency, relevance, sourceCredibility, composite }
  }

  /**
   * How novel is this spark compared to current foci?
   * Returns a modulation value (-0.2 to +0.2).
   */
  private fociNoveltyModulation(spark: BridgeSpark): number {
    const activeFoci = this.foci.filter(f => f.spark !== null)
    if (activeFoci.length === 0) return 0.1 // no context = somewhat novel

    let totalOverlap = 0
    for (const focus of activeFoci) {
      if (!focus.spark) continue
      totalOverlap += this.contentOverlap(spark.content, focus.spark.content)
    }
    const avgOverlap = totalOverlap / activeFoci.length

    // High overlap → reduce novelty, low overlap → boost novelty
    return 0.2 * (1 - avgOverlap * 2)
  }

  /**
   * How relevant is this spark to current foci?
   * Based on file overlap and content overlap.
   */
  private relevanceToFoci(spark: BridgeSpark): number {
    const activeFoci = this.foci.filter(f => f.spark !== null)
    if (activeFoci.length === 0) return 0.5 // no context

    let fileOverlap = 0
    let contentOverlap = 0

    for (const focus of activeFoci) {
      if (!focus.spark) continue

      // File overlap
      const focusFiles = new Set(focus.spark.relevantFiles)
      for (const file of spark.relevantFiles) {
        if (focusFiles.has(file)) fileOverlap++
      }

      // Content overlap
      contentOverlap += this.contentOverlap(spark.content, focus.spark.content)
    }

    const maxFileOverlap = Math.max(spark.relevantFiles.length * activeFoci.length, 1)
    const normalizedFile = Math.min(1.0, fileOverlap / maxFileOverlap * 3) // boost small matches
    const normalizedContent = contentOverlap / activeFoci.length

    return 0.6 * normalizedFile + 0.4 * normalizedContent
  }

  /**
   * Simple content overlap measure (0-1).
   * Uses word overlap ratio.
   */
  private contentOverlap(a: string, b: string): number {
    const wordsA = new Set(a.toLowerCase().split(/\W+/).filter(w => w.length >= 4))
    const wordsB = new Set(b.toLowerCase().split(/\W+/).filter(w => w.length >= 4))

    if (wordsA.size === 0 || wordsB.size === 0) return 0

    let overlap = 0
    for (const word of wordsA) {
      if (wordsB.has(word)) overlap++
    }

    return overlap / Math.max(wordsA.size, wordsB.size)
  }


  // --- Private: Persistence ---

  private persist(): void {
    if (!this.kvStore) return
    try {
      const state: LocusBridgePersistedState = {
        foci: this.foci,
        kindlingHistory: this.kindlingHistory.slice(-50),
        totalSparksProcessed: this.totalSparksProcessed,
        totalKindlings: this.totalKindlings,
        taskBoundaries: this.historyScorer.getTaskBoundaries(),
        lastAssemblyMeta: this.assembler.getLastMeta(),
        persistedAt: Date.now(),
      }
      this.kvStore.set('locus-bridge:state', JSON.stringify(state))
    } catch (err) {
      this.logger.warn('Failed to persist LocusBridge state', { error: String(err) })
    }
  }

  private restore(): void {
    if (!this.kvStore) return
    try {
      const raw = this.kvStore.get('locus-bridge:state')
      if (!raw) return
      const state: LocusBridgePersistedState = typeof raw === 'string' ? JSON.parse(raw) : raw

      // Restore foci (only if slot count matches)
      if (state.foci?.length === this.config.foci) {
        this.foci = state.foci
      }

      this.kindlingHistory = state.kindlingHistory ?? []
      this.totalSparksProcessed = state.totalSparksProcessed ?? 0
      this.totalKindlings = state.totalKindlings ?? 0

      if (state.taskBoundaries) {
        this.historyScorer.restoreState(state.taskBoundaries)
      }

      this.logger.info('LocusBridge state restored', {
        fociOccupied: this.foci.filter(f => f.spark !== null).length,
        totalSparks: this.totalSparksProcessed,
        totalKindlings: this.totalKindlings,
        persistedAt: state.persistedAt,
      })
    } catch (err) {
      this.logger.warn('Failed to restore LocusBridge state', { error: String(err) })
    }
  }


  // --- Private: Utilities ---

  private trimHistory(): void {
    if (this.kindlingHistory.length > this.config.maxEventHistory) {
      this.kindlingHistory = this.kindlingHistory.slice(-this.config.maxEventHistory)
    }
  }

  private emptyMeta(totalMessages: number): AssemblyMeta {
    return {
      tokenBudget: this.config.tokenBudget,
      systemPromptTokens: 0,
      curatedContextTokens: 0,
      historyTokens: 0,
      turnsIncluded: totalMessages,
      turnsDropped: 0,
      keptMessageIndices: Array.from({ length: totalMessages }, (_, i) => i),
      fociSnapshot: [],
      taskBoundaries: [],
      assembledAt: Date.now(),
    }
  }
}


// Re-export components for direct access
export { BridgeSparkExtractor } from './spark-extractor.js'
export { ContextCurator } from './context-curator.js'
export type { MemoryRetriever, IntelligenceSignalProvider } from './context-curator.js'
export { HistoryScorer } from './history-scorer.js'
export { WindowAssembler } from './window-assembler.js'

// Re-export types
export type {
  AssembledWindow,
  AssemblyMeta,
  BridgeEclipseEvent,
  BridgeFocus,
  BridgeKindlingEvent,
  BridgeLuminanceScore,
  BridgeLuminanceWeights,
  BridgeSpark,
  BridgeSparkType,
  CuratedContext,
  CuratedMemory,
  CuratedCode,
  CuratedSignal,
  LocusBridgeConfig,
  LocusBridgePersistedState,
  LocusBridgeSnapshot,
  ScoredTurn,
} from './types.js'
export { DEFAULT_LOCUS_BRIDGE_CONFIG, DEFAULT_BRIDGE_LUMINANCE_WEIGHTS } from './types.js'
