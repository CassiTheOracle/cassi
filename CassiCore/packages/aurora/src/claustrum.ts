/**
 * Claustrum — the unified cognitive graph.
 *
 * Named for the thin neural sheet Crick called "the conductor of the orchestra."
 * Integrates model knowledge (LARQL), personal memory (Mnemic Field),
 * portal bridges, and dream discoveries into a single queryable graph.
 */

import type { ILogger } from '@cassicore/foundation'
import type { Cortex } from '@cassicore/mnemic-field'
import type { Engram } from '@cassicore/mnemic-field'
import type { PortalBridge } from './vendor/core/intelligence/memory-bridge/portal-bridge.js'
import type { DreamDiscovery } from './vendor/core/intelligence/memory-bridge/dream-engine.js'
import type {
  ClaustrumInsightSink,
  ObserverInsight,
} from '@cassicore/constellation'
import type {
  CognitiveNode,
  CognitiveEdge,
  CognitiveNodeSource,
  UnifiedGraph,
  CognitivePath,
  KnowledgeGap,
  ModelKnowledgeProvider,
  AuroraConfig,
} from './types.js'
import { AURORA_DEFAULTS } from './types.js'

/**
 * Buffers typed observer insights as they're emitted by constellation
 * observer layers. Aurora's `Claustrum.buildFocusedGraph` reads from this
 * buffer on each rebuild and folds the insights into the unified graph as
 * `source: 'observer'` nodes.
 *
 * Implements `ClaustrumInsightSink` so it can be passed straight into an
 * `ObserverMemoryBridge`. Bounded by `maxBuffered` to keep memory steady
 * during long sessions — oldest insights are dropped when the cap is hit.
 *
 * See: docs/design/aurora-extensions-roadmap.md §A3
 */
export class ObserverInsightCollector implements ClaustrumInsightSink {
  private buffer: ObserverInsight[] = []
  private byId = new Map<string, ObserverInsight>()
  private readonly maxBuffered: number
  private _droppedCount = 0

  constructor(maxBuffered = 64) {
    this.maxBuffered = Math.max(8, maxBuffered)
  }

  ingest(insight: ObserverInsight): void {
    if (!insight.id) {
      this._droppedCount++
      return
    }
    if (this.byId.has(insight.id)) return
    this.byId.set(insight.id, insight)
    this.buffer.push(insight)
    while (this.buffer.length > this.maxBuffered) {
      const dropped = this.buffer.shift()
      if (dropped?.id) this.byId.delete(dropped.id)
    }
  }

  /** Snapshot the currently-buffered insights (most recent last). */
  snapshot(): ReadonlyArray<ObserverInsight> {
    return this.buffer.slice()
  }

  /** Clear the buffer — typically called by Aurora after folding into the graph if a one-shot policy is desired. */
  drain(): ObserverInsight[] {
    const out = this.buffer
    this.buffer = []
    this.byId = new Map()
    return out
  }

  get size(): number {
    return this.buffer.length
  }

  /** How many insights were silently dropped due to missing id (diagnostic). */
  get droppedCount(): number {
    return this._droppedCount
  }

  /**
   * A3.4 cleanup integration — drop insights older than `maxAgeMs` ms,
   * UNLESS at least one of their concept hints is still active (per the
   * caller's `isConceptActive` predicate). Concepts that have decayed
   * out of the claustrum lose their anchor; insights that reference
   * only decayed concepts get pruned. Insights still tied to active
   * concepts stay regardless of age — they remain useful for Aurora's
   * merge step.
   *
   * `nowMs` defaults to Date.now(); pass a fixed value in tests for
   * determinism. Returns the number of insights dropped.
   */
  pruneOlderThan(
    maxAgeMs: number,
    isConceptActive: (label: string) => boolean,
    nowMs: number = Date.now(),
  ): number {
    const cutoff = nowMs - maxAgeMs
    const kept: ObserverInsight[] = []
    let dropped = 0
    for (const insight of this.buffer) {
      const observedAt = insight.observedAt ?? nowMs
      if (observedAt >= cutoff) {
        kept.push(insight)
        continue
      }
      const concepts = insight.concepts ?? []
      if (concepts.some(c => isConceptActive(c))) {
        kept.push(insight)
        continue
      }
      if (insight.id) this.byId.delete(insight.id)
      dropped++
    }
    this.buffer = kept
    return dropped
  }

  /**
   * A3.4 admin endpoint — diagnostic summary of buffer state without
   * exposing insight contents. Intended for operator inspection: how
   * old is the data, what layers contributed, how full is the buffer.
   */
  inspect(): {
    size: number
    capacity: number
    droppedCount: number
    oldestObservedAt: number | null
    newestObservedAt: number | null
    byLayer: Record<string, number>
  } {
    const byLayer: Record<string, number> = {}
    let oldest: number | null = null
    let newest: number | null = null
    for (const insight of this.buffer) {
      byLayer[insight.layer] = (byLayer[insight.layer] ?? 0) + 1
      if (typeof insight.observedAt === 'number') {
        if (oldest === null || insight.observedAt < oldest) oldest = insight.observedAt
        if (newest === null || insight.observedAt > newest) newest = insight.observedAt
      }
    }
    return {
      size: this.buffer.length,
      capacity: this.maxBuffered,
      droppedCount: this._droppedCount,
      oldestObservedAt: oldest,
      newestObservedAt: newest,
      byLayer,
    }
  }
}

/**
 * Options for {@link Claustrum.buildFocusedGraph}.
 * All fields except `foci` and `cortex` are optional — null is the default.
 */
export interface BuildGraphOptions {
  foci: string[]
  cortex: Cortex
  modelProvider?: ModelKnowledgeProvider | null
  knowledgeProvider?: ModelKnowledgeProvider | null
  portalBridge?: PortalBridge | null
  recentDiscoveries?: DreamDiscovery[]
  observerCollector?: ObserverInsightCollector | null
}

export class Claustrum {
  private config: AuroraConfig
  private logger: ILogger

  constructor(
    logger: ILogger,
    config?: Partial<AuroraConfig>,
  ) {
    this.logger = logger.child ? logger.child('claustrum') : logger
    this.config = { ...AURORA_DEFAULTS, ...config }
  }

  /**
   * Build a focused unified graph around current attention foci.
   * Extracts the neighborhood around what we're paying attention to
   * rather than merging entire graphs.
   */
  buildFocusedGraph(opts: BuildGraphOptions): UnifiedGraph {
    const {
      foci,
      cortex,
      modelProvider = null,
      knowledgeProvider = null,
      portalBridge = null,
      recentDiscoveries = [],
      observerCollector = null,
    } = opts

    const start = Date.now()

    const nodes = new Map<string, CognitiveNode>()
    const edges = new Map<string, CognitiveEdge[]>()
    const reverseEdges = new Map<string, CognitiveEdge[]>()

    const memorySeeds = this.seedFromMemory(foci, cortex, nodes)
    this.expandMemoryNeighborhood(memorySeeds, cortex, nodes, edges, reverseEdges)

    if (knowledgeProvider) {
      const knowledgeSeeds = this.seedFromKnowledge(foci, knowledgeProvider, nodes)
      this.expandKnowledgeNeighborhood(knowledgeSeeds, knowledgeProvider, nodes, edges, reverseEdges)
    }

    if (modelProvider) {
      this.seedFromModel(foci, modelProvider, nodes, edges, reverseEdges)
    }
    if (portalBridge) {
      this.bridgeViaPortals(portalBridge, nodes, edges, reverseEdges)
    }

    this.addDreamEdges(recentDiscoveries, nodes, edges, reverseEdges)

    if (observerCollector && observerCollector.size > 0) {
      this.seedFromObservers(observerCollector, nodes, edges, reverseEdges)
      observerCollector.drain() // one-shot: each insight is folded at most once per
      // dedup-window cycle. Observer layers re-emit on their next poll, so the
      // insight will re-enter the collector and be folded again when appropriate.
    }

    // Merge hydrated state from persistence (B6.1). These are pre-populated
    // nodes/edges from a prior session that survived decay — they enrich the
    // graph without requiring re-derivation from providers.
    if (this._hydratedNodes.length > 0 || this._hydratedEdges.length > 0) {
      this.mergeHydratedState(nodes, edges, reverseEdges)
      // Clear after merging — subsequent buildFocusedGraph calls only get
      // fresh provider data unless persistence re-seeds.
      this._hydratedNodes = []
      this._hydratedEdges = []
    }

    this.resolveOverlappingEntities(nodes)
    this.computePageRank(nodes, edges, reverseEdges)

    const sourceBreakdown: Record<CognitiveNodeSource, number> = { model: 0, memory: 0, knowledge: 0, observer: 0, both: 0 }
    for (const node of nodes.values()) {
      sourceBreakdown[node.source]++
    }

    let edgeCount = 0
    for (const edgeList of edges.values()) {
      edgeCount += edgeList.length
    }

    this.logger.debug('Claustrum graph built', {
      foci,
      nodeCount: nodes.size,
      edgeCount,
      sourceBreakdown,
      durationMs: Date.now() - start,
    })

    return { nodes, edges, reverseEdges, sourceBreakdown, edgeCount, builtAt: Date.now() }
  }

  findShortestPath(
    graph: UnifiedGraph,
    fromId: string,
    toId: string,
  ): CognitivePath | null {
    if (!graph.nodes.has(fromId) || !graph.nodes.has(toId)) return null
    if (fromId === toId) {
      return { nodeIds: [fromId], edges: [], totalWeight: 0, crossesSourceBoundary: false, length: 0 }
    }

    const visited = new Set<string>()
    const queue: Array<{ nodeId: string; path: string[]; pathEdges: CognitiveEdge[] }> = []
    visited.add(fromId)
    queue.push({ nodeId: fromId, path: [fromId], pathEdges: [] })

    while (queue.length > 0) {
      const current = queue.shift()!

      // Collect neighbors from both forward and reverse edges
      const neighbors = this.getUndirectedNeighbors(graph, current.nodeId)

      for (const { neighborId, edge } of neighbors) {
        if (visited.has(neighborId)) continue
        visited.add(neighborId)

        const newPath = [...current.path, neighborId]
        const newEdges = [...current.pathEdges, edge]

        if (neighborId === toId) {
          return this.buildPathResult(newPath, newEdges, graph)
        }

        queue.push({ nodeId: neighborId, path: newPath, pathEdges: newEdges })
      }
    }

    return null
  }

  findGaps(graph: UnifiedGraph): KnowledgeGap[] {
    const gaps: KnowledgeGap[] = []

    for (const [id, node] of graph.nodes) {
      if (node.source === 'model' && node.resonance === 0) {
        const outEdges = graph.edges.get(id) ?? []
        if (outEdges.length > 0) {
          const topEdge = outEdges.sort((a, b) => b.weight - a.weight)[0]
          gaps.push({
            entity: node.label,
            knownBy: 'model',
            knowledge: `${node.label} → ${topEdge.edgeType} → ${graph.nodes.get(topEdge.targetId)?.label ?? topEdge.targetId}`,
            strength: Claustrum.clampConfidence(node.modelConfidence),
            gapType: 'missing',
          })
        }
      } else if (node.source === 'memory' && node.resonance === 0) {
        gaps.push({
          entity: node.label,
          knownBy: 'memory',
          knowledge: node.content?.slice(0, 100) ?? node.label,
          strength: node.potentiation ?? 0.5,
          gapType: 'missing',
        })
      } else if (node.source === 'both' && node.resonance < 0.3) {
        gaps.push({
          entity: node.label,
          knownBy: 'model',
          knowledge: `Weak agreement on "${node.label}" between model and memory`,
          strength: node.resonance,
          gapType: 'contradictory',
        })
      }
    }

    return gaps
      .filter(g => g.strength > 0)
      .sort((a, b) => b.strength - a.strength)
      .slice(0, this.config.maxGaps)
  }

  getResonanceHubs(graph: UnifiedGraph): CognitiveNode[] {
    const hubs: CognitiveNode[] = []

    for (const node of graph.nodes.values()) {
      if (node.source === 'both' || node.resonance >= this.config.minResonanceForHub) {
        hubs.push(node)
      }
    }

    hubs.sort((a, b) => {
      const scoreA = (a.resonance + 0.1) * (a.centrality + 0.1)
      const scoreB = (b.resonance + 0.1) * (b.centrality + 0.1)
      return scoreB - scoreA
    })

    return hubs.slice(0, this.config.maxResonanceHubs)
  }

  /**
   * Seed the claustrum with nodes and edges hydrated from AuroraPersistence.
   * This is called at boot when cross-session continuity (B6) is enabled.
   *
   * The seeded nodes/edges become part of the next `buildFocusedGraph` result
   * — they're pre-populated so the graph doesn't start empty on a fresh boot.
   * When `buildFocusedGraph` runs, it will merge these with whatever the
   * providers discover for the current turn's foci.
   *
   * See: docs/design/aurora-cross-session-continuity.md §5
   */
  seedFromPersistence(nodes: CognitiveNode[], edges: CognitiveEdge[]): void {
    // Store for merging on next buildFocusedGraph call
    this._hydratedNodes = nodes
    this._hydratedEdges = edges
    this.logger.info('Seeded from persistence', {
      nodes: nodes.length,
      edges: edges.length,
    })
  }

  /** Hydrated state from persistence, merged into the next buildFocusedGraph. */
  private _hydratedNodes: CognitiveNode[] = []
  private _hydratedEdges: CognitiveEdge[] = []

  /**
   * Compute coherence and integration in a single pass over the graph.
   * Coherence = largest connected component dominance.
   * Integration = cross-boundary edge ratio + both-node ratio.
   */
  computeGraphMetrics(graph: UnifiedGraph): { coherence: number; integration: number } {
    if (graph.nodes.size === 0) return { coherence: 0, integration: 0 }

    // Single BFS pass: find connected components AND count cross-boundary edges
    const visited = new Set<string>()
    let componentCount = 0
    let largestComponent = 0
    let crossBoundaryEdges = 0
    let totalEdges = 0
    const countedEdges = new Set<string>()

    for (const nodeId of graph.nodes.keys()) {
      if (visited.has(nodeId)) continue

      componentCount++
      let componentSize = 0
      const queue = [nodeId]
      visited.add(nodeId)

      while (queue.length > 0) {
        const current = queue.shift()!
        componentSize++

        // Forward edges
        const outEdges = graph.edges.get(current) ?? []
        for (const edge of outEdges) {
          // Count edge for integration (avoid double-counting)
          const edgeKey = `${edge.sourceId}→${edge.targetId}:${edge.edgeType}`
          if (!countedEdges.has(edgeKey)) {
            countedEdges.add(edgeKey)
            totalEdges++
            const sourceNode = graph.nodes.get(edge.sourceId)
            const targetNode = graph.nodes.get(edge.targetId)
            if (sourceNode && targetNode) {
              if (sourceNode.source !== targetNode.source || edge.origin === 'portal' || edge.origin === 'dream') {
                crossBoundaryEdges++
              }
            }
          }

          if (!visited.has(edge.targetId) && graph.nodes.has(edge.targetId)) {
            visited.add(edge.targetId)
            queue.push(edge.targetId)
          }
        }

        // Reverse edges (for component connectivity)
        const inEdges = graph.reverseEdges.get(current) ?? []
        for (const edge of inEdges) {
          if (!visited.has(edge.sourceId) && graph.nodes.has(edge.sourceId)) {
            visited.add(edge.sourceId)
            queue.push(edge.sourceId)
          }
        }
      }

      if (componentSize > largestComponent) {
        largestComponent = componentSize
      }
    }

    // Coherence: largest component dominance × inverse fragmentation
    const dominance = largestComponent / graph.nodes.size
    const fragmentation = componentCount > 1 ? 1 / componentCount : 1
    const coherence = dominance * 0.7 + fragmentation * 0.3

    // Integration: cross-boundary ratio + both-node ratio
    const crossRatio = totalEdges > 0 ? crossBoundaryEdges / totalEdges : 0
    const bothRatio = graph.sourceBreakdown.both / Math.max(1, graph.nodes.size)
    const integration = Math.min(1.0, crossRatio * 0.7 + bothRatio * 0.3)

    return { coherence, integration }
  }

  private seedFromMemory(
    foci: string[],
    cortex: Cortex,
    nodes: Map<string, CognitiveNode>,
  ): Engram[] {
    const seeds: Engram[] = []
    const seen = new Set<string>()

    for (const focus of foci) {
      const results = cortex.searchText(focus, 10)
      for (const result of results) {
        const engram = result.engram
        if (seen.has(engram.id)) continue
        seen.add(engram.id)
        seeds.push(engram)
        nodes.set(engram.id, this.memoryNode(engram, true))
      }
    }

    const topEngrams = cortex.listEngrams(20)
    for (const engram of topEngrams) {
      if (seen.has(engram.id)) continue
      if (engram.potentiation < 0.3) continue
      seen.add(engram.id)
      seeds.push(engram)
      nodes.set(engram.id, this.memoryNode(engram, false))
    }

    return seeds
  }

  private expandMemoryNeighborhood(
    seeds: Engram[],
    cortex: Cortex,
    nodes: Map<string, CognitiveNode>,
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
  ): void {
    const visited = new Set(seeds.map(s => s.id))
    let frontier = seeds.map(s => s.id)

    for (let depth = 0; depth < this.config.subgraphRadius && frontier.length > 0; depth++) {
      const nextFrontier: string[] = []

      for (const nodeId of frontier) {
        const synapses = cortex.getNeighborSynapses(nodeId, 'all')
        for (const synapse of synapses) {
          this.addEdge(edges, reverseEdges, {
            sourceId: synapse.sourceId,
            targetId: synapse.targetId,
            origin: 'memory',
            edgeType: synapse.edgeType,
            weight: synapse.weight,
            synapseType: synapse.edgeType,
          })

          // Discover the neighbor ID (the other end of the synapse)
          const neighborId = synapse.sourceId === nodeId ? synapse.targetId : synapse.sourceId
          if (!visited.has(neighborId)) {
            visited.add(neighborId)
            const engram = cortex.getEngram(neighborId)
            if (engram) {
              nodes.set(engram.id, this.memoryNode(engram, false))
              nextFrontier.push(engram.id)
            }
          }
        }
      }

      frontier = nextFrontier
      if (nodes.size >= this.config.maxGraphNodes) break
    }
  }

  /**
   * Merge hydrated nodes and edges from AuroraPersistence into the graph
   * being built. Existing nodes (from providers this turn) take precedence
   * over hydrated ones — hydration fills gaps, it doesn't overwrite fresh data.
   */
  private mergeHydratedState(
    nodes: Map<string, CognitiveNode>,
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
  ): void {
    for (const node of this._hydratedNodes) {
      if (!nodes.has(node.id)) {
        nodes.set(node.id, node)
      }
    }
    for (const edge of this._hydratedEdges) {
      if (!nodes.has(edge.sourceId) || !nodes.has(edge.targetId)) continue
      const list = edges.get(edge.sourceId) ?? []
      const exists = list.some(e => e.targetId === edge.targetId && e.edgeType === edge.edgeType)
      if (!exists) {
        list.push(edge)
        edges.set(edge.sourceId, list)
        const revList = reverseEdges.get(edge.targetId) ?? []
        revList.push(edge)
        reverseEdges.set(edge.targetId, revList)
      }
    }
  }

  private seedFromModel(
    foci: string[],
    modelProvider: ModelKnowledgeProvider,
    nodes: Map<string, CognitiveNode>,
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
  ): void {
    for (const focus of foci) {
      const entities = modelProvider.search(focus, 5)

      for (const entity of entities) {
        const nodeId = `model:${entity.name}`

        if (!nodes.has(nodeId)) {
          nodes.set(nodeId, {
            id: nodeId,
            label: entity.name,
            source: 'model',
            modelConfidence: entity.relations.length > 0
              ? Math.max(...entity.relations.map(r => r.confidence))
              : 0,
            modelLayers: entity.relations.length > 0
              ? [entity.relations[0].layerMin, entity.relations[0].layerMax]
              : undefined,
            resonance: 0,
            centrality: 0,
            activated: true,
          })
        }

        for (const rel of entity.relations.slice(0, 10)) {
          const targetId = `model:${rel.target}`

          if (!nodes.has(targetId)) {
            nodes.set(targetId, {
              id: targetId,
              label: rel.target,
              source: 'model',
              modelConfidence: rel.confidence,
              modelLayers: [rel.layerMin, rel.layerMax],
              resonance: 0,
              centrality: 0,
              activated: false,
            })
          }

          this.addEdge(edges, reverseEdges, {
            sourceId: nodeId,
            targetId,
            origin: 'model',
            edgeType: rel.relation,
            weight: Claustrum.clampConfidence(rel.confidence),
            modelConfidence: rel.confidence,
            modelLayers: [rel.layerMin, rel.layerMax],
          })
        }
      }

      if (nodes.size >= this.config.maxGraphNodes) break
    }
  }

  private seedFromKnowledge(
    foci: string[],
    knowledgeProvider: ModelKnowledgeProvider,
    nodes: Map<string, CognitiveNode>,
  ): Map<string, CognitiveNode> {
    const seeds = new Map<string, CognitiveNode>()

    for (const focus of foci) {
      const entities = knowledgeProvider.search(focus, 5)

      for (const entity of entities) {
        const nodeId = `knowledge:${entity.name}`

        if (!nodes.has(nodeId)) {
          const node: CognitiveNode = {
            id: nodeId,
            label: entity.name,
            source: 'knowledge',
            resonance: 0,
            centrality: 0,
            activated: true,
          }
          nodes.set(nodeId, node)
          seeds.set(nodeId, node)
        }
      }

      if (nodes.size >= this.config.maxGraphNodes) break
    }

    return seeds
  }

  private expandKnowledgeNeighborhood(
    seeds: Map<string, CognitiveNode>,
    knowledgeProvider: ModelKnowledgeProvider,
    nodes: Map<string, CognitiveNode>,
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
  ): void {
    for (const [seedId, seedNode] of seeds) {
      const kgEdges = knowledgeProvider.subgraph(seedNode.label, 1)

      for (const edge of kgEdges) {
        const targetId = `knowledge:${edge.object}`

        if (!nodes.has(targetId)) {
          nodes.set(targetId, {
            id: targetId,
            label: edge.object,
            source: 'knowledge',
            resonance: 0,
            centrality: 0,
            activated: false,
          })
        }

        this.addEdge(edges, reverseEdges, {
          sourceId: seedId,
          targetId,
          origin: 'memory',
          edgeType: edge.relation,
          weight: Math.min(1.0, edge.confidence),
        })
      }
    }
  }

  private bridgeViaPortals(
    portalBridge: PortalBridge,
    nodes: Map<string, CognitiveNode>,
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
  ): void {
    for (const [nodeId, node] of nodes) {
      if (node.source !== 'memory' && node.source !== 'knowledge') continue

      const portals = portalBridge.getPortalsForEngram(nodeId)
      for (const portal of portals) {
        const modelNodeId = `model:feature:L${portal.feature.layer}:F${portal.feature.featureIndex}`

        if (!nodes.has(modelNodeId)) {
          nodes.set(modelNodeId, {
            id: modelNodeId,
            label: portal.feature.label ?? `Feature L${portal.feature.layer}:${portal.feature.featureIndex}`,
            source: 'model',
            modelLayers: [portal.feature.layer],
            resonance: 0,
            centrality: 0,
            activated: false,
          })
        }

        this.addEdge(edges, reverseEdges, {
          sourceId: modelNodeId,
          targetId: nodeId,
          origin: 'portal',
          edgeType: portal.connectionType,
          weight: portal.strength,
        })
      }
    }
  }

  private addDreamEdges(
    discoveries: DreamDiscovery[],
    nodes: Map<string, CognitiveNode>,
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
  ): void {
    for (const discovery of discoveries) {
      if (!nodes.has(discovery.sourceId) || !nodes.has(discovery.targetId)) continue

      this.addEdge(edges, reverseEdges, {
        sourceId: discovery.sourceId,
        targetId: discovery.targetId,
        origin: 'dream',
        edgeType: 'dream_discovered',
        weight: discovery.combinedScore,
      })
    }
  }

  /**
   * Fold buffered observer insights into the focused graph.
   *
   * Each insight becomes a `source: 'observer'` node (id `observer:<insightId>`).
   * If the insight carries `concepts`, we look for existing nodes whose label
   * contains any concept (case-insensitive) and link them with `origin: 'observer'`
   * edges weighted by the insight's confidence.
   *
   * Insights about helices/clusters/constellations don't usually overlap with
   * the existing memory/model node labels, so most observer nodes start as
   * free-standing islands. They become connected over time as the same
   * concepts surface in conversation/memory.
   *
   * See: docs/design/aurora-extensions-roadmap.md §A3
   */
  private seedFromObservers(
    collector: ObserverInsightCollector,
    nodes: Map<string, CognitiveNode>,
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
  ): void {
    const insights = collector.snapshot()
    if (insights.length === 0) return

    // Index existing nodes by lowercased label for cheap concept matching.
    const labelIndex: Array<{ id: string; lower: string }> = []
    for (const [id, node] of nodes) {
      if (node.label) labelIndex.push({ id, lower: node.label.toLowerCase() })
    }

    for (const insight of insights) {
      if (nodes.size >= this.config.maxGraphNodes) break

      const id = `observer:${insight.id}`
      if (!nodes.has(id)) {
        nodes.set(id, {
          id,
          label: insight.label,
          source: 'observer',
          content: insight.content,
          resonance: insight.confidence ?? 0.5,
          centrality: 0,
          activated: true,
        })
      }

      const concepts = insight.concepts ?? []
      if (concepts.length === 0) continue

      const seenTargets = new Set<string>()
      for (const concept of concepts) {
        const needle = concept.toLowerCase()
        if (needle.length < 3) continue
        for (const candidate of labelIndex) {
          if (candidate.id === id) continue
          if (seenTargets.has(candidate.id)) continue
          if (!candidate.lower.includes(needle)) continue
          seenTargets.add(candidate.id)
          this.addEdge(edges, reverseEdges, {
            sourceId: id,
            targetId: candidate.id,
            origin: 'observer',
            edgeType: 'observed_about',
            weight: insight.confidence ?? 0.5,
          })
        }
      }
    }
  }

  private resolveOverlappingEntities(nodes: Map<string, CognitiveNode>): void {
    const modelNodes = [...nodes.entries()].filter(([_, n]) => n.source === 'model')
    const memoryNodesWithLower = [...nodes.entries()]
      .filter(([_, n]) => n.source === 'memory' && n.content)
      .map(([id, node]) => ({ id, node, lower: node.content!.toLowerCase() }))

    for (const [modelId, modelNode] of modelNodes) {
      const entityName = modelNode.label.toLowerCase()
      if (entityName.length < 3) continue

      for (const mem of memoryNodesWithLower) {
        if (mem.lower.includes(entityName)) {
const modelStrength = Claustrum.clampConfidence(modelNode.modelConfidence)
          const memoryStrength = mem.node.potentiation ?? 0.5
          const resonance = Math.sqrt(modelStrength * memoryStrength)

          modelNode.source = 'both'
          modelNode.resonance = Math.max(modelNode.resonance, resonance)
          modelNode.potentiation = mem.node.potentiation
          modelNode.nodeType = mem.node.nodeType

          mem.node.resonance = Math.max(mem.node.resonance, resonance)
          mem.node.modelConfidence = modelNode.modelConfidence
          mem.node.modelLayers = modelNode.modelLayers
        }
      }
    }
  }

  /**
   * PageRank via reverse-adjacency list — O(edges) per iteration, not O(n²).
   */
  private computePageRank(
    nodes: Map<string, CognitiveNode>,
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
  ): void {
    const nodeIds = [...nodes.keys()]
    const n = nodeIds.length
    if (n === 0) return

    const damping = this.config.pageRankDamping
    const iterations = this.config.pageRankIterations

    const scores = new Map<string, number>()
    const outDegree = new Map<string, number>()
    for (const id of nodeIds) {
      scores.set(id, 1.0 / n)
      outDegree.set(id, (edges.get(id) ?? []).length)
    }

    for (let iter = 0; iter < iterations; iter++) {
      const newScores = new Map<string, number>()

      for (const id of nodeIds) {
        let score = (1 - damping) / n

        // Only iterate incoming edges via reverse adjacency — O(in-degree)
        const incoming = reverseEdges.get(id) ?? []
        for (const edge of incoming) {
          const degree = outDegree.get(edge.sourceId) ?? 0
          if (degree === 0) continue
          score += damping * (scores.get(edge.sourceId) ?? 0) * edge.weight / degree
        }

        newScores.set(id, score)
      }

      for (const [id, score] of newScores) {
        scores.set(id, score)
      }
    }

    let maxScore = 0
    for (const score of scores.values()) {
      if (score > maxScore) maxScore = score
    }

    if (maxScore > 0) {
      for (const [id, node] of nodes) {
        node.centrality = (scores.get(id) ?? 0) / maxScore
      }
    }
  }

  private memoryNode(engram: Engram, activated: boolean): CognitiveNode {
    return {
      id: engram.id,
      label: engram.content.slice(0, 80),
      source: 'memory',
      potentiation: engram.potentiation,
      nodeType: engram.nodeType,
      content: engram.content,
      resonance: 0,
      centrality: 0,
      activated,
    }
  }

  /** Collect forward + reverse neighbors for undirected BFS traversal. */
  private getUndirectedNeighbors(
    graph: UnifiedGraph,
    nodeId: string,
  ): Array<{ neighborId: string; edge: CognitiveEdge }> {
    const neighbors: Array<{ neighborId: string; edge: CognitiveEdge }> = []

    const outEdges = graph.edges.get(nodeId) ?? []
    for (const edge of outEdges) {
      neighbors.push({ neighborId: edge.targetId, edge })
    }

    const inEdges = graph.reverseEdges.get(nodeId) ?? []
    for (const edge of inEdges) {
      neighbors.push({
        neighborId: edge.sourceId,
        edge: { ...edge, sourceId: nodeId, targetId: edge.sourceId },
      })
    }

    return neighbors
  }

  private buildPathResult(
    nodeIds: string[],
    pathEdges: CognitiveEdge[],
    graph: UnifiedGraph,
  ): CognitivePath {
    let totalWeight = 0
    let crossesBoundary = false

    for (const edge of pathEdges) {
      totalWeight += edge.weight
      const sourceNode = graph.nodes.get(edge.sourceId)
      const targetNode = graph.nodes.get(edge.targetId)
      if (sourceNode && targetNode && sourceNode.source !== targetNode.source) {
        crossesBoundary = true
      }
    }

    return {
      nodeIds,
      edges: pathEdges,
      totalWeight,
      crossesSourceBoundary: crossesBoundary,
      length: pathEdges.length,
    }
  }

  /** Normalize a confidence value from either [0, 1000] or [0, 1] range into [0, 1]. */
  private static clampConfidence(v: number | undefined, fallback = 0): number {
    const c = v ?? fallback
    if (c <= 0) return 0
    return Math.min(1.0, c > 1 ? c / 1000 : c)
  }

  private addEdge(
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
    edge: CognitiveEdge,
  ): void {
    if (!edges.has(edge.sourceId)) {
      edges.set(edge.sourceId, [])
    }
    edges.get(edge.sourceId)!.push(edge)

    if (!reverseEdges.has(edge.targetId)) {
      reverseEdges.set(edge.targetId, [])
    }
    reverseEdges.get(edge.targetId)!.push(edge)
  }
}
