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
import { Claustrum } from './claustrum.js'
import { StateProjector } from './state-projector.js'
import type {
  MentalState,
  MentalStateUpdate,
  ReasoningMomentum,
  ReasoningShift,
  ModelKnowledgeProvider,
  AuroraConfig,
  CognitiveEdge,
} from './types.js'
import { AURORA_DEFAULTS } from './types.js'

export { Claustrum } from './claustrum.js'
export { StateProjector } from './state-projector.js'
export { LarqlKnowledgeProvider } from './larql-provider.js'
export type {
  MentalState,
  MentalStateUpdate,
  CognitiveNode,
  CognitiveEdge,
  ModelKnowledgeProvider,
  AuroraConfig,
} from './types.js'

const MAX_RECENT_CONCEPTS = 200

export class Aurora {
  private logger: ILogger
  private claustrum: Claustrum
  private projector: StateProjector

  private currentState: MentalState | null = null
  private lastFingerprint: string | null = null
  private lastSerialization: string | null = null

  private recentConcepts: Map<string, number> = new Map()
  private turnCount = 0
  private conceptHistory: string[][] = []
  private maxConceptsPerTurn: number

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

    this.claustrum = new Claustrum(logger, config)
    this.projector = new StateProjector(logger, config)

    this.logger.info('Aurora initialized', {
      hasModelProvider: !!modelProvider,
      hasKnowledgeProvider: !!knowledgeProvider,
      hasPortalBridge: !!portalBridge,
    })
  }

  buildState(
    foci: string[],
    affect: ResonantAffectSignal | null = null,
    recentDiscoveries: DreamDiscovery[] = [],
  ): MentalState {
    const start = Date.now()

    const graph = this.claustrum.buildFocusedGraph(
      foci,
      this.cortex,
      this.modelProvider,
      this.knowledgeProvider,
      this.portalBridge,
      recentDiscoveries,
    )

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

    this.logger.debug('Reasoning observed', {
      concepts: concepts.length,
      activatedNodes: activatedNodes.length,
      shift: shift?.type ?? 'none',
      turnCount: this.turnCount,
    })

    return {
      activatedNodes,
      newEdges,
      affectDelta: null,
      shift,
      momentum,
      extractedConcepts: concepts,
      durationMs: Date.now() - start,
    }
  }

  private extractConcepts(text: string): string[] {
    const concepts = new Set<string>()

    // Capitalized phrases (e.g., "Phase Coherence", "Brain Context")
    const capitalizedPattern = /[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*/g
    let match: RegExpExecArray | null = null
    while ((match = capitalizedPattern.exec(text)) !== null) {
      const term = match[0].trim()
      if (term.length >= 3 && term.length <= 50) {
        concepts.add(term)
      }
    }

    // Quoted strings
    const quotedPattern = /"([^"]{3,50})"/g
    while ((match = quotedPattern.exec(text)) !== null) {
      concepts.add(match[1])
    }

    // Backtick code references (e.g., `buildBrainContext`, `phase_coherence`)
    const backtickPattern = /`([^`]{2,40})`/g
    while ((match = backtickPattern.exec(text)) !== null) {
      concepts.add(match[1])
    }

    // camelCase identifiers (e.g., buildBrainContext, phaseCoherence)
    // Must have at least one lowercase→uppercase transition and be 6+ chars
    const camelCasePattern = /\b[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*\b/g
    while ((match = camelCasePattern.exec(text)) !== null) {
      if (match[0].length >= 6 && match[0].length <= 50) {
        concepts.add(match[0])
      }
    }

    // PascalCase identifiers (e.g., ThalamusModule, BrainContext)
    // Already partially covered by capitalizedPattern, but this catches
    // single-word PascalCase like "ThalamusModule" more reliably
    const pascalCasePattern = /\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b/g
    while ((match = pascalCasePattern.exec(text)) !== null) {
      if (match[0].length >= 6 && match[0].length <= 50) {
        concepts.add(match[0])
      }
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
