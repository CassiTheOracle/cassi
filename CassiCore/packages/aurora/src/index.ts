/**
 * Aurora — the cognitive state loop.
 *
 * Aurora is the emergent cognitive awareness that arises when model knowledge
 * (LARQL vindex) and personal memory (Mnemic Field) are merged into a unified
 * graph and projected as a living mental state.
 *
 * The feedback loop:
 *   1. Claustrum merges model knowledge + Mnemic Field → unified graph
 *   2. StateProjector serializes the mental state → text for context, vector for residual
 *   3. External client receives the mental state in its context window
 *   4. Client reasoning is observed → concepts extracted → graph nodes activated
 *   5. Mental state shifts → next turn sees an updated mind
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from '../mnemic-field/cortex.js'
import type { PortalBridge } from '../memory-bridge/portal-bridge.js'
import type { ResonantAffectSignal } from '../memory-bridge/resonant-affect.js'
import type { DreamDiscovery } from '../memory-bridge/dream-engine.js'
import { Claustrum, ObserverInsightCollector } from './claustrum.js'
import { StateProjector } from './state-projector.js'
import type {
  MentalState,
  MentalStateUpdate,
  ReasoningMomentum,
  ReasoningShift,
  ModelKnowledgeProvider,
  AuroraConfig,
  CognitiveEdge,
  ReasoningRecord,
  ReverieInsight,
} from './types.js'
import { AURORA_DEFAULTS } from './types.js'
import type { ReverieInferenceProvider } from './types.js'
import { ReverieReasoningObserver, makeReasoningRecordId } from './reverie-reasoning-observer.js'

export { Claustrum, ObserverInsightCollector } from './claustrum.js'
export { StateProjector } from './state-projector.js'
export { LarqlKnowledgeProvider } from './larql-provider.js'
export type {
  MentalState,
  MentalStateUpdate,
  CognitiveNode,
  CognitiveEdge,
  ModelKnowledgeProvider,
  AuroraConfig,
  ReasoningRecord,
  ReverieInsight,
} from './types.js'

const MAX_RECENT_CONCEPTS = 200
const MAX_REASONING_RECORDS = 500

export class Aurora {
  private logger: ILogger
  private claustrum: Claustrum
  private projector: StateProjector

  /**
   * Buffer of typed observer insights from constellation/cluster/corpus
   * observers. Folded into the focused graph on each `buildState`.
   * Accessed externally via `getObserverSink()` so the constellation layer
   * can hand it to its `ObserverMemoryBridge`.
   */
  private observerCollector = new ObserverInsightCollector()

  /**
   * Monotonic Aurora cycle counter. Stamped onto every gate-KNN provenance
   * row so the claustrum-vindex snapshotter can attribute features to the
   * cycle that surfaced them. See docs/design/claustrum-vindex.md §6.
   */
  private cycleCounter = 0

  private currentState: MentalState | null = null
  private lastFingerprint: string | null = null
  private lastSerialization: string | null = null

  private recentConcepts: Map<string, number> = new Map()
  private turnCount = 0
  private conceptHistory: string[][] = []
  private maxConceptsPerTurn: number

  /** Persisted reasoning observations — corpus for learning and re-analysis. */
  private reasoningLog: ReasoningRecord[] = []

  /** Reverie slow-path observer (optional — set via setReverieInferenceProvider). */
  private reverieObserver: ReverieReasoningObserver | null = null

  /** Configuration for Reverie integration. */
  private reverieMinTextLength: number
  private reverieSamplingRate: number
  private reverieTimeoutMs: number
  private reverieObservationCounters: Map<string, number> = new Map()

  /** Optional session ID for reasoning records. */
  private sessionId?: string

  /** Active task for context in Reverie analysis (wired from lamina). */
  private activeTask: string | null = null

  /** Recent session decisions for contradiction detection. */
  private recentDecisions: string[] = []

  /** In-flight Reverie analyses for cleanup. */
  private inFlightAnalyses: Set<Promise<void>> = new Set()
  private maxInFlightAnalyses = 5

  constructor(
    private cortex: Cortex,
    private modelProvider: ModelKnowledgeProvider | null,
    private knowledgeProvider: ModelKnowledgeProvider | null,
    private portalBridge: PortalBridge | null,
    logger: ILogger,
    config?: Partial<AuroraConfig>,
  ) {
    this.logger = logger.child ? logger.child('aurora') : logger
    this.maxConceptsPerTurn = config?.maxConceptsPerTurn ?? AURORA_DEFAULTS.maxConceptsPerTurn
    this.reverieMinTextLength = config?.reverieMinTextLength ?? AURORA_DEFAULTS.reverieMinTextLength
    this.reverieSamplingRate = config?.reverieSamplingRate ?? AURORA_DEFAULTS.reverieSamplingRate
    this.reverieTimeoutMs = config?.reverieTimeoutMs ?? AURORA_DEFAULTS.reverieTimeoutMs

    this.claustrum = new Claustrum(logger, config)
    this.projector = new StateProjector(logger, config)

    this.logger.info('Aurora initialized', {
      hasModelProvider: !!modelProvider,
      hasKnowledgeProvider: !!knowledgeProvider,
      hasPortalBridge: !!portalBridge,
      reverieSamplingRate: this.reverieSamplingRate,
      reverieMinTextLength: this.reverieMinTextLength,
    })
  }

  /** Wire a Reverie inference provider for the slow path. */
  setReverieInferenceProvider(provider: ReverieInferenceProvider): void {
    this.reverieObserver = new ReverieReasoningObserver(provider, this.logger)
    this.logger.info('Reverie reasoning observer wired')
  }

  /**
   * Sink for typed observer insights — hand this to an `ObserverMemoryBridge`
   * so cluster/corpus/synapse observers can publish findings into Aurora's
   * Claustrum (in addition to the Mnemic store).
   *
   * See: docs/design/aurora-extensions-roadmap.md §A3
   */
  getObserverSink(): ObserverInsightCollector {
    return this.observerCollector
  }

  /**
   * Stamp `cycleId` onto any provider that supports `setCycleId` (currently
   * `LarqlKnowledgeProvider`). Other providers are a silent no-op. Called
   * from `buildState` so all gate-KNN hits during one Aurora cycle share
   * a provenance group.
   */
  private applyCycleId(cycleId: string | null): void {
    for (const provider of [this.modelProvider, this.knowledgeProvider]) {
      if (!provider) continue
      const setter = (provider as { setCycleId?: (id: string | null) => void }).setCycleId
      if (typeof setter === 'function') {
        try {
          setter.call(provider, cycleId)
        } catch (err) {
          this.logger.debug?.('applyCycleId provider rejected', { error: String(err) })
        }
      }
    }
  }

  /** Set session ID for reasoning records. */
  setSessionId(sessionId: string): void {
    this.sessionId = sessionId
  }

  /** Set active task for Reverie analysis context (wired from lamina). */
  setActiveTask(task: string | null): void {
    this.activeTask = task
  }

  /** Set recent session decisions for contradiction detection. */
  setRecentDecisions(decisions: string[]): void {
    this.recentDecisions = decisions.slice(-10) // keep last 10
  }

  /** Dispose Aurora and cancel pending operations. */
  dispose(): void {
    this.reverieObserver = null
    this.inFlightAnalyses.clear()
    this.reasoningLog = []
    this.recentConcepts.clear()
    this.conceptHistory = []
    this.logger.debug('Aurora disposed')
  }

  /** Get the persisted reasoning log (most recent first). */
  getReasoningLog(limit = 50): ReasoningRecord[] {
    return this.reasoningLog.slice(-limit).reverse()
  }

  /** Get reasoning records that had Reverie insights (for analysis). */
  getInsightfulReasoning(limit = 20): ReasoningRecord[] {
    return this.reasoningLog
      .filter(r => r.insights.length > 0)
      .slice(-limit)
      .reverse()
  }

  buildState(
    foci: string[],
    affect: ResonantAffectSignal | null = null,
    recentDiscoveries: DreamDiscovery[] = [],
  ): MentalState {
    const start = Date.now()

    // Stamp the active cycle on any provider that supports recorder provenance,
    // so the claustrum-vindex snapshotter can attribute gate-KNN hits to a
    // specific Aurora cycle (see docs/design/claustrum-vindex.md §6).
    const cycleId = `aur_${(this.cycleCounter += 1)}`
    this.applyCycleId(cycleId)

    const graph = this.claustrum.buildFocusedGraph(
      foci,
      this.cortex,
      this.modelProvider,
      this.knowledgeProvider,
      this.portalBridge,
      recentDiscoveries,
      this.observerCollector,
    )

    // Clear cycle stamp now that the gate-KNN burst for this cycle is done.
    this.applyCycleId(null)

    const resonanceHubs = this.claustrum.getResonanceHubs(graph)
    const gaps = this.claustrum.findGaps(graph)
    const { coherence, integration } = this.claustrum.computeGraphMetrics(graph)
    const momentum = this.computeMomentum(foci)

    const state: MentalState = {
      graph,
      resonanceHubs,
      gaps,
      recentDiscoveries,
      affect,
      foci,
      momentum,
      coherence,
      integration,
      computedAt: Date.now(),
      durationMs: Date.now() - start,
    }

    this.currentState = state
    // Invalidate serialization cache when state changes
    this.lastFingerprint = null
    this.lastSerialization = null

    this.logger.debug('Aurora state built', {
      nodes: graph.nodes.size,
      edges: graph.edgeCount,
      hubs: resonanceHubs.length,
      gaps: gaps.length,
      coherence: coherence.toFixed(3),
      integration: integration.toFixed(3),
      durationMs: state.durationMs,
    })

    return state
  }

  serialize(state?: MentalState): string {
    const target = state ?? this.currentState
    if (!target) return ''

    const fingerprint = this.projector.fingerprint(target)
    if (fingerprint === this.lastFingerprint && this.lastSerialization) {
      return this.lastSerialization
    }

    const text = this.projector.serializeForContext(target)
    this.lastFingerprint = fingerprint
    this.lastSerialization = text

    return text
  }

  private topFoci(n: number): string[] {
    return [...this.recentConcepts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, n)
      .map(([concept]) => concept)
  }

  private shouldRebuildState(newConcepts: string[]): boolean {
    if (!this.currentState) return true
    if (newConcepts.length === 0) return false
    const currentFoci = new Set(this.currentState.foci.map(f => f.toLowerCase()))
    const novel = newConcepts.filter(c => !currentFoci.has(c.toLowerCase())).length
    return novel >= Math.ceil(newConcepts.length / 2)
  }

  observeReasoning(text: string): MentalStateUpdate {
    const start = Date.now()

    // === FAST PATH (always) ===
    const concepts = this.extractConcepts(text)

    if (concepts.length === 0) {
      this.turnCount++
      return {
        activatedNodes: [],
        newEdges: [],
        affectDelta: null,
        shift: null,
        momentum: this.computeMomentum([]),
        extractedConcepts: [],
        durationMs: Date.now() - start,
        reverieInsights: [],
        reverieAnalyzed: false,
      }
    }

    this.turnCount++
    this.conceptHistory.push(concepts)
    if (this.conceptHistory.length > 10) {
      this.conceptHistory.shift()
    }

    for (const concept of concepts) {
      const count = this.recentConcepts.get(concept) ?? 0
      this.recentConcepts.set(concept, count + 1)
    }

    // Decay + hard cap on concept count
    if (this.turnCount % 5 === 0) {
      for (const [concept, count] of this.recentConcepts) {
        if (count <= 1) {
          this.recentConcepts.delete(concept)
        } else {
          this.recentConcepts.set(concept, Math.floor(count * 0.7))
        }
      }
    }
    if (this.recentConcepts.size > MAX_RECENT_CONCEPTS) {
      const sorted = [...this.recentConcepts.entries()].sort((a, b) => a[1] - b[1])
      const toRemove = sorted.slice(0, sorted.length - MAX_RECENT_CONCEPTS)
      for (const [key] of toRemove) {
        this.recentConcepts.delete(key)
      }
    }

    if (!this.currentState || this.shouldRebuildState(concepts)) {
      const foci = this.topFoci(this.maxConceptsPerTurn)
      if (foci.length > 0) {
        try {
          this.buildState(foci, null)
        } catch (err) {
          this.logger.warn('buildState failed during observeReasoning', { error: String(err) })
        }
      }
    }

    const activatedNodes: string[] = []
    const newEdges: CognitiveEdge[] = []

    if (this.currentState) {
      const conceptsLower = concepts.map(c => c.toLowerCase())
      for (const [nodeId, node] of this.currentState.graph.nodes) {
        const labelLower = node.label.toLowerCase()
        const contentLower = node.content?.toLowerCase()
        for (const cl of conceptsLower) {
          if (labelLower.includes(cl) || (contentLower && contentLower.includes(cl))) {
            node.activated = true
            activatedNodes.push(nodeId)
            break
          }
        }
      }
    }

    const shift = this.detectShift(concepts)
    const momentum = this.computeMomentum(concepts)

    // Decide whether to run Reverie slow path BEFORE persisting,
    // so we know whether to flag the record as analyzed.
    const shouldRunReverie = this.shouldRunReverieSlowPath(text, shift)
    const reverieAnalyzed = shouldRunReverie && !!this.reverieObserver

    // === PERSIST ===
    // Always save the reasoning record — this is the learning corpus
    const record = this.persistReasoningRecord({
      text,
      concepts,
      insights: [], // populated async by slow path
      shift,
      momentum,
      activatedNodes,
      durationMs: Date.now() - start,
      reverieAnalyzed,
    })

    // === SLOW PATH (conditional) ===
    // Fire-and-forget: Reverie analysis is async but observeReasoning is sync.
    // Cap in-flight analyses to prevent unbounded promise accumulation.
    if (reverieAnalyzed) {
      if (this.inFlightAnalyses.size >= this.maxInFlightAnalyses) {
        this.logger.debug('Reverie analysis skipped: too many in-flight', {
          inFlight: this.inFlightAnalyses.size,
          max: this.maxInFlightAnalyses,
        })
      } else {
        const analysis = this.runReverieAnalysis(record.id, text, concepts, shift)
          .finally(() => { this.inFlightAnalyses.delete(analysis) })
        this.inFlightAnalyses.add(analysis)
        analysis.catch(err => this.logger.debug('Reverie analysis failed', { error: String(err) }))
      }
    }

    this.logger.debug('Reasoning observed', {
      concepts: concepts.length,
      activatedNodes: activatedNodes.length,
      shift: shift?.type ?? 'none',
      turnCount: this.turnCount,
      reverieAnalyzed,
      recordId: record.id,
    })

    return {
      activatedNodes,
      newEdges,
      affectDelta: null,
      shift,
      momentum,
      extractedConcepts: concepts,
      durationMs: Date.now() - start,
      reverieInsights: [], // always empty at return time; populated async
      reverieAnalyzed,
      recordId: record.id,
    }
  }

  /**
   * Decide whether the Reverie slow path should run for this reasoning text.
   */
  private shouldRunReverieSlowPath(text: string, shift: ReasoningShift | null): boolean {
    if (!this.reverieObserver) return false
    if (this.reverieSamplingRate <= 0) return false

    // Always run on significant reasoning text
    if (text.length < this.reverieMinTextLength) return false

    // Always run when a shift is detected (high-value signal)
    if (shift) return true

    // Sample every Nth observation (per-session)
    const key = this.sessionId ?? '_global'
    const count = (this.reverieObservationCounters.get(key) ?? 0) + 1
    this.reverieObservationCounters.set(key, count)
    return count % this.reverieSamplingRate === 0
  }

  /**
   * Run Reverie semantic analysis asynchronously.
   * Updates the persisted ReasoningRecord with insights when complete.
   */
  private async runReverieAnalysis(
    recordId: string,
    text: string,
    concepts: string[],
    shift: ReasoningShift | null,
  ): Promise<void> {
    if (!this.reverieObserver) return

    const insights = await this.reverieObserver.analyze(
      {
        text,
        currentState: this.currentState,
        activeTask: this.activeTask,
        recentDecisions: this.recentDecisions,
        extractedConcepts: concepts,
        shiftDetected: shift !== null,
      },
      this.reverieTimeoutMs,
    )

    if (insights.length > 0) {
      // Find the record by ID and update it
      for (let i = this.reasoningLog.length - 1; i >= 0; i--) {
        const record = this.reasoningLog[i]
        if (record.id === recordId) {
          record.insights = insights
          this.logger.debug('Reverie insights appended to record', {
            recordId: record.id,
            insights: insights.length,
          })
          break
        }
      }
    }
  }

  /**
   * Persist a reasoning observation to the log.
   * This creates the learning corpus — raw text + extracted metadata.
   */
  private persistReasoningRecord(params: {
    text: string
    concepts: string[]
    insights: ReverieInsight[]
    shift: ReasoningShift | null
    momentum: ReasoningMomentum
    activatedNodes: string[]
    durationMs: number
    reverieAnalyzed: boolean
  }): ReasoningRecord {
    const record: ReasoningRecord = {
      id: makeReasoningRecordId(),
      text: params.text,
      concepts: params.concepts,
      insights: params.insights,
      shift: params.shift,
      momentum: params.momentum,
      activatedNodes: params.activatedNodes,
      turnNumber: this.turnCount,
      recordedAt: Date.now(),
      durationMs: params.durationMs,
      reverieAnalyzed: params.reverieAnalyzed,
      sessionId: this.sessionId,
    }

    this.reasoningLog.push(record)
    if (this.reasoningLog.length > MAX_REASONING_RECORDS) {
      this.reasoningLog.shift()
    }

    return record
  }

  private extractConcepts(text: string): string[] {
    const concepts = new Set<string>()

    const inAlnumRun = (m: RegExpExecArray): boolean => {
      const before = m.index > 0 ? text[m.index - 1] : ''
      const after = text[m.index + m[0].length] ?? ''
      const isAlnum = (ch: string) => /[A-Za-z0-9]/.test(ch)
      return isAlnum(before) || isAlnum(after)
    }

    const looksLikeRandomToken = (term: string): boolean => {
      const lower = term.toLowerCase()
      const vowels = (lower.match(/[aeiouy]/g) ?? []).length
      const letters = (lower.match(/[a-z]/g) ?? []).length
      if (letters >= 4 && vowels === 0) return true
      if (/[bcdfghjklmnpqrstvwxz]{5,}/i.test(lower)) return true
      return false
    }

    const capitalizedPattern = /[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*/g
    let match: RegExpExecArray | null = null
    while ((match = capitalizedPattern.exec(text)) !== null) {
      const term = match[0].trim()
      if (term.length < 3 || term.length > 50) continue
      if (inAlnumRun(match)) continue
      if (looksLikeRandomToken(term)) continue
      concepts.add(term)
    }

    const quotedPattern = /"([^"]{3,50})"/g
    while ((match = quotedPattern.exec(text)) !== null) {
      concepts.add(match[1])
    }

    const backtickPattern = /`([^`]{2,40})`/g
    while ((match = backtickPattern.exec(text)) !== null) {
      concepts.add(match[1])
    }

    const camelCasePattern = /\b[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*\b/g
    while ((match = camelCasePattern.exec(text)) !== null) {
      if (match[0].length < 6 || match[0].length > 50) continue
      if (inAlnumRun(match)) continue
      if (looksLikeRandomToken(match[0])) continue
      concepts.add(match[0])
    }

    const pascalCasePattern = /\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b/g
    while ((match = pascalCasePattern.exec(text)) !== null) {
      if (match[0].length < 6 || match[0].length > 50) continue
      if (inAlnumRun(match)) continue
      if (looksLikeRandomToken(match[0])) continue
      concepts.add(match[0])
    }

    // snake_case identifiers (e.g., build_brain_context, phase_coherence)
    const snakeCasePattern = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g
    while ((match = snakeCasePattern.exec(text)) !== null) {
      if (match[0].length >= 5 && match[0].length <= 50) {
        concepts.add(match[0])
      }
    }

    return [...concepts].slice(0, this.maxConceptsPerTurn)
  }

  private detectShift(currentConcepts: string[]): ReasoningShift | null {
    if (this.conceptHistory.length < 2) return null

    const previous = this.conceptHistory[this.conceptHistory.length - 2]
    if (!previous) return null

    const prevSet = new Set(previous.map(c => c.toLowerCase()))
    const currSet = new Set(currentConcepts.map(c => c.toLowerCase()))

    let overlap = 0
    for (const c of currSet) {
      if (prevSet.has(c)) overlap++
    }

    const maxSize = Math.max(prevSet.size, currSet.size, 1)
    const overlapRatio = overlap / maxSize

    if (overlapRatio < 0.15 && currSet.size > 2) {
      return {
        type: 'topic_change',
        triggerConcepts: currentConcepts.filter(c => !prevSet.has(c.toLowerCase())),
        confidence: 1 - overlapRatio,
        detectedAt: Date.now(),
      }
    }

    if (overlapRatio > 0.5 && currSet.size > prevSet.size * 1.3) {
      return {
        type: 'deepening',
        triggerConcepts: currentConcepts.filter(c => !prevSet.has(c.toLowerCase())),
        confidence: overlapRatio,
        detectedAt: Date.now(),
      }
    }

    // Fewer concepts = narrowing/focusing
    if (overlapRatio > 0.5 && currSet.size < prevSet.size * 0.7 && currSet.size >= 2) {
      return {
        type: 'narrowing',
        triggerConcepts: currentConcepts,
        confidence: overlapRatio,
        detectedAt: Date.now(),
      }
    }

    return null
  }

  private computeMomentum(currentConcepts: string[]): ReasoningMomentum {
    const sorted = [...this.recentConcepts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([concept]) => concept)

    let newCount = 0
    for (const concept of currentConcepts) {
      if (!this.recentConcepts.has(concept) ||
          (this.recentConcepts.get(concept) ?? 0) <= 1) {
        newCount++
      }
    }
    const novelty = currentConcepts.length > 0
      ? newCount / currentConcepts.length
      : 0

    const totalOccurrences = [...this.recentConcepts.values()].reduce((a, b) => a + b, 0)
    let entropy = 0
    if (totalOccurrences > 0) {
      for (const count of this.recentConcepts.values()) {
        const p = count / totalOccurrences
        if (p > 0) entropy -= p * Math.log2(p)
      }
    }
    const maxEntropy = this.recentConcepts.size > 0
      ? Math.log2(this.recentConcepts.size)
      : 1
    const confidence = maxEntropy > 0 ? 1 - (entropy / maxEntropy) : 0.5

    const shift = this.detectShift(currentConcepts)

    let turnsInDirection = 0
    if (currentConcepts.length > 0) {
      const currentSet = new Set(currentConcepts.map(c => c.toLowerCase()))
      for (let i = this.conceptHistory.length - 1; i >= 0; i--) {
        const prev = this.conceptHistory[i]
        const hasOverlap = prev.some(c => currentSet.has(c.toLowerCase()))
        if (hasOverlap) {
          turnsInDirection++
        } else {
          break
        }
      }
    }

    return {
      trendingConcepts: sorted.length > 0 ? sorted : currentConcepts.slice(0, 5),
      novelty: Math.min(1, novelty),
      confidence: Math.min(1, Math.max(0, confidence)),
      topicShift: shift?.type === 'topic_change',
      turnsInDirection,
    }
  }

  getCurrentState(): MentalState | null {
    return this.currentState
  }

  /** Forward shortest-path queries through Aurora's graph. */
  findShortestPath(fromId: string, toId: string): import('./types.js').CognitivePath | null {
    if (!this.currentState) return null
    return this.claustrum.findShortestPath(this.currentState.graph, fromId, toId)
  }

  setModelProvider(provider: ModelKnowledgeProvider): void {
    this.modelProvider = provider
    this.logger.info('Model knowledge provider updated')
  }

  setKnowledgeProvider(provider: ModelKnowledgeProvider): void {
    this.knowledgeProvider = provider
    this.logger.info('Knowledge provider updated')
  }

  setPortalBridge(bridge: PortalBridge): void {
    this.portalBridge = bridge
    this.logger.info('Portal bridge updated')
  }

  getStats(): {
    turnCount: number
    conceptsTracked: number
    currentStateNodes: number
    currentStateEdges: number
    lastCoherence: number
    lastIntegration: number
  } {
    return {
      turnCount: this.turnCount,
      conceptsTracked: this.recentConcepts.size,
      currentStateNodes: this.currentState?.graph.nodes.size ?? 0,
      currentStateEdges: this.currentState?.graph.edgeCount ?? 0,
      lastCoherence: this.currentState?.coherence ?? 0,
      lastIntegration: this.currentState?.integration ?? 0,
    }
  }
}
