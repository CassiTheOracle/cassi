/**
 * StateProjector — serializes the mental state for context injection.
 *
 * Two projection modes:
 *   1. Text serialization (~3K tokens) for external client context windows
 *   2. Vector projection (Float32Array) for residual stream injection (future)
 *
 * The text serialization is designed to be:
 *   - Compact: fits within injection budget
 *   - Structured: LLMs can parse and reference specific sections
 *   - Dynamic: changes between turns as reasoning updates the state
 *   - First-person: written as "my" mental state, not "the system's"
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  MentalState,
  CognitiveNode,
  CognitiveEdge,
  KnowledgeGap,
  AuroraConfig,
  UnifiedGraph,
  VectorProjection,
  VectorProjectionOptions,
} from './types.js'
import { AURORA_DEFAULTS } from './types.js'
import { SelfNarrativeRenderer } from './self-narrative-renderer.js'
import { composeVectorProjection, type ProjectionContext, type GateVectorSource, type BaselineNormSource } from './projection/vector-projection.js'
import { renderActiveGateAnnotation } from './projection/active-gate-annotation.js'

/**
 * StateProjector — converts mental state to injectable formats.
 */
export class StateProjector {
  private config: AuroraConfig
  private logger: ILogger
  private narrative: SelfNarrativeRenderer

  constructor(
    logger: ILogger,
    config?: Partial<AuroraConfig>,
  ) {
    this.logger = logger.child ? logger.child('state-projector') : logger
    this.config = { ...AURORA_DEFAULTS, ...config }
    this.narrative = new SelfNarrativeRenderer(logger, this.config)
  }

  /**
   * Serialize the mental state to text for context injection.
   *
   * Returns a compact, structured representation that fits within
   * the configured character budget.
   */
  serializeForContext(state: MentalState): string {
    const sections: string[] = []
    let charCount = 0

    const budgetRemaining = () => this.config.maxSerializedChars - charCount

    // Header
    const header = '[Aurora — Cognitive State]'
    sections.push(header)
    charCount += header.length + 1

    // Narrative section (N1 — first-person rendering)
    const narr = this.narrative.render(state)
    if (narr) {
      sections.push(narr.text)
      charCount += narr.charCount + 1
    }

    // Section 1: Focus (always included, very compact)
    if (state.foci.length > 0) {
      const focusLine = `Focus: ${state.foci.join(', ')}`
      sections.push(focusLine)
      charCount += focusLine.length + 1
    }

    // Section 2: Affect (compact, important for tone)
    if (state.affect) {
      const a = state.affect
      const affectLine = `Affect: ${a.label} (v:${a.affect.valence.toFixed(2)} a:${a.affect.arousal.toFixed(2)})`
      sections.push(affectLine)
      charCount += affectLine.length + 1
    }

    // Section 3: Reasoning momentum
    if (state.momentum.trendingConcepts.length > 0) {
      const momentum = this.serializeMomentum(state)
      if (momentum.length < budgetRemaining() * 0.15) {
        sections.push(momentum)
        charCount += momentum.length + 1
      }
    }

    // Section 4: Resonance hubs (most important — where model and memory agree)
    if (state.resonanceHubs.length > 0) {
      const hubs = this.serializeResonanceHubs(state, budgetRemaining() * 0.3)
      if (hubs) {
        sections.push(hubs)
        charCount += hubs.length + 1
      }
    }

    // Section 4b: Active steering (A2.4 — surfaces vector-projection
    // contributions as text steering metadata for runtimes that can't
    // accept residual injection. No-op when projection is disabled or
    // empty.)
    if (this.config.vectorProjectionEnabled) {
      const projection = composeVectorProjection(state, undefined)
      const annotation = renderActiveGateAnnotation(projection, {
        maxGates: this.config.vectorProjectionMaxGates,
      })
      if (annotation && annotation.length < budgetRemaining() * 0.2) {
        sections.push(annotation)
        charCount += annotation.length + 1
      }
    }

    // Section 5: Knowledge gaps (what I know that the model doesn't, and vice versa)
    if (state.gaps.length > 0) {
      const gaps = this.serializeGaps(state, budgetRemaining() * 0.25)
      if (gaps) {
        sections.push(gaps)
        charCount += gaps.length + 1
      }
    }

    // Section 6: Recent discoveries (dream-found connections)
    if (state.recentDiscoveries.length > 0) {
      const discoveries = this.serializeDiscoveries(state, budgetRemaining() * 0.2)
      if (discoveries) {
        sections.push(discoveries)
        charCount += discoveries.length + 1
      }
    }

    // Section 7: Graph detail (if enabled and budget allows)
    if (this.config.includeGraphDetail && budgetRemaining() > 200) {
      const detail = this.serializeGraphDetail(state, budgetRemaining())
      if (detail) {
        sections.push(detail)
        charCount += detail.length + 1
      }
    }

    // Section 8: Coherence and integration metrics
    const metrics = `Coherence: ${state.coherence.toFixed(2)} | Integration: ${state.integration.toFixed(2)}`
    if (metrics.length < budgetRemaining()) {
      sections.push(metrics)
    }

    const result = sections.join('\n')

    this.logger.debug('State serialized', {
      sections: sections.length,
      chars: result.length,
      budget: this.config.maxSerializedChars,
      resonanceHubs: state.resonanceHubs.length,
      gaps: state.gaps.length,
    })

    return result
  }

  /**
   * A2 vector projection — sibling to `serializeForContext`. Returns the
   * structured projection (per-layer placeholders + contributions intent +
   * metadata) for residual-stream injection or downstream annotation.
   *
   * Returns `null` when no nodes are activated or when the projection has
   * no contributions after layer/weight filtering.
   */
  projectVector(
    state: MentalState,
    options?: VectorProjectionOptions,
    ctx?: ProjectionContext,
    vectorSource?: GateVectorSource,
    baselineNormSource?: BaselineNormSource,
  ): VectorProjection | null {
    return composeVectorProjection(state, options, ctx, vectorSource, baselineNormSource)
  }

  /**
   * Compute a fingerprint for change detection.
   * If the fingerprint hasn't changed, skip re-serialization.
   */
  fingerprint(state: MentalState): string {
    const parts = [
      state.foci.sort().join(','),
      state.resonanceHubs.map(h => h.id).join(','),
      state.gaps.length.toString(),
      state.affect?.label ?? 'none',
      state.momentum.trendingConcepts.join(','),
      state.coherence.toFixed(2),
    ]
    return parts.join('|')
  }

  /**
   * Serialize reasoning momentum.
   */
  private serializeMomentum(state: MentalState): string {
    const m = state.momentum
    const parts: string[] = ['Momentum:']

    if (m.trendingConcepts.length > 0) {
      parts.push(`  Trending: ${m.trendingConcepts.slice(0, 5).join(', ')}`)
    }

    if (m.topicShift) {
      parts.push('  [topic shift detected]')
    }

    const noveltyLabel = m.novelty > 0.7 ? 'high' : m.novelty > 0.3 ? 'moderate' : 'low'
    parts.push(`  Novelty: ${noveltyLabel} | Confidence: ${m.confidence.toFixed(2)}`)

    return parts.join('\n')
  }

  /**
   * Serialize resonance hubs.
   */
  private serializeResonanceHubs(state: MentalState, budget: number): string | null {
    const lines: string[] = ['Resonance hubs (strong in both model and memory):']
    let chars = lines[0].length

    for (const hub of state.resonanceHubs) {
      const modelInfo = hub.modelConfidence
        ? `model:${Math.min(1.0, hub.modelConfidence / 1000).toFixed(2)}`
        : 'model:—'
      const memoryInfo = hub.potentiation !== undefined
        ? `memory:${hub.potentiation.toFixed(2)}`
        : 'memory:—'

      const line = `  ${hub.label} — ${modelInfo}, ${memoryInfo}, resonance:${hub.resonance.toFixed(2)}`

      if (chars + line.length + 1 > budget) break
      lines.push(line)
      chars += line.length + 1
    }

    return lines.length > 1 ? lines.join('\n') : null
  }

  /**
   * Serialize knowledge gaps.
   */
  private serializeGaps(state: MentalState, budget: number): string | null {
    const modelGaps = state.gaps.filter(g => g.knownBy === 'model' && g.gapType === 'missing')
    const memoryGaps = state.gaps.filter(g => g.knownBy === 'memory' && g.gapType === 'missing')
    const tensions = state.gaps.filter(g => g.gapType === 'contradictory')

    const lines: string[] = ['Knowledge landscape:']
    let chars = lines[0].length

    if (modelGaps.length > 0) {
      const line = `  Model knows (I don't): ${modelGaps.slice(0, 3).map(g => g.entity).join(', ')}`
      if (chars + line.length + 1 <= budget) {
        lines.push(line)
        chars += line.length + 1
      }
    }

    if (memoryGaps.length > 0) {
      const line = `  I know (model doesn't): ${memoryGaps.slice(0, 3).map(g => g.entity).join(', ')}`
      if (chars + line.length + 1 <= budget) {
        lines.push(line)
        chars += line.length + 1
      }
    }

    if (tensions.length > 0) {
      const line = `  Tensions: ${tensions.slice(0, 2).map(g => `"${g.entity}"`).join(', ')}`
      if (chars + line.length + 1 <= budget) {
        lines.push(line)
        chars += line.length + 1
      }
    }

    return lines.length > 1 ? lines.join('\n') : null
  }

  /**
   * Serialize recent dream discoveries.
   */
  private serializeDiscoveries(state: MentalState, budget: number): string | null {
    const lines: string[] = ['Recent discoveries:']
    let chars = lines[0].length

    const graph = state.graph

    for (const discovery of state.recentDiscoveries.slice(0, 5)) {
      const sourceNode = graph.nodes.get(discovery.sourceId)
      const targetNode = graph.nodes.get(discovery.targetId)

      if (!sourceNode || !targetNode) continue

      const sourceLabel = sourceNode.label.slice(0, 40)
      const targetLabel = targetNode.label.slice(0, 40)
      const layers = discovery.topOverlapLayers.slice(0, 2).map(l => `L${l.layer}`).join(',')

      const line = `  "${sourceLabel}" ↔ "${targetLabel}" (shared:${discovery.sharedFeatureCount}, layers:${layers})`

      if (chars + line.length + 1 > budget) break
      lines.push(line)
      chars += line.length + 1
    }

    return lines.length > 1 ? lines.join('\n') : null
  }

  /**
   * Serialize graph detail summary.
   */
  private serializeGraphDetail(state: MentalState, budget: number): string | null {
    const g = state.graph
    const line = `Graph: ${g.nodes.size} nodes (${g.sourceBreakdown.model} model, ${g.sourceBreakdown.memory} memory, ${g.sourceBreakdown.observer} observer, ${g.sourceBreakdown.both} shared), ${g.edgeCount} edges`

    return line.length <= budget ? line : null
  }
}
