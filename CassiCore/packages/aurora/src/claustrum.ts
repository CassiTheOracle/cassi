/**
 * Claustrum — the unified cognitive graph.
 *
 * Named for the thin neural sheet Crick called "the conductor of the orchestra."
 * Integrates model knowledge (LARQL), personal memory (Mnemic Field),
 * portal bridges, and dream discoveries into a single queryable graph.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from '../mnemic-field/cortex.js'
import type { Engram } from '../mnemic-field/types.js'
import type { PortalBridge } from '../memory-bridge/portal-bridge.js'
import type { DreamDiscovery } from '../memory-bridge/dream-engine.js'
import type {
  CognitiveNode,
  CognitiveEdge,
  UnifiedGraph,
  CognitivePath,
  KnowledgeGap,
  ModelKnowledgeProvider,
  AuroraConfig,
} from './types.js'
import { AURORA_DEFAULTS } from './types.js'

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
  buildFocusedGraph(
    foci: string[],
    cortex: Cortex,
    modelProvider: ModelKnowledgeProvider | null,
    knowledgeProvider: ModelKnowledgeProvider | null,
    portalBridge: PortalBridge | null,
    recentDiscoveries: DreamDiscovery[] = [],
  ): UnifiedGraph {
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
    this.resolveOverlappingEntities(nodes)
    this.computePageRank(nodes, edges, reverseEdges)

    const sourceBreakdown = { model: 0, memory: 0, knowledge: 0, both: 0 }
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
            strength: node.modelConfidence ? Math.min(1.0, node.modelConfidence / 1000) : 0.5,
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
            weight: Math.min(1.0, rel.confidence / 1000),
            modelConfidence: rel.confidence,
            modelLayers: [rel.layerMin, rel.layerMax],
          })
        }
      }

      if (nodes.size >= this.config.maxGraphNodes) break
    }
  }

  private bridgeViaPortals(
    portalBridge: PortalBridge,
    nodes: Map<string, CognitiveNode>,
    edges: Map<string, CognitiveEdge[]>,
    reverseEdges: Map<string, CognitiveEdge[]>,
  ): void {
    for (const [nodeId, node] of nodes) {
      if (node.source !== 'memory') continue

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
          const modelStrength = modelNode.modelConfidence
            ? Math.min(1.0, modelNode.modelConfidence / 1000)
            : 0.5
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
