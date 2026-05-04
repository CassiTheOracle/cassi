/**
 * Counterfactual Engine (B7) — Sandboxed "what-if" analysis over prior reasoning.
 *
 * Provides the core forking primitive: deep-copy a subgraph from the live
 * claustrum, allow perturbations on the copy, observe what changes, then
 * dispose. The live claustrum is NEVER mutated by fork operations.
 *
 * Phase B7.1: forking, perturbation application, observation, and lifecycle.
 * Later phases add Reverie integration, welfare guards, and cross-feature hooks.
 *
 * See: docs/design/aurora-counterfactual-exploration.md
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  CognitiveNode,
  CognitiveEdge,
  UnifiedGraph,
  ReasoningRecord,
  ReasoningShift,
  ReasoningMomentum,
  MentalState,
} from './types.js'



/**
 * Scope specification for a fork — which part of the graph to copy.
 */
export interface ForkScope {
  /** Anchor node IDs — the fork copies these and their neighborhoods. */
  anchors: string[]
  /** Hop radius from anchors (default 2). */
  hops: number
  /** Cap on total nodes in the fork (default 200). */
  maxNodes?: number
  /** Whether to include observer-source nodes (default true). */
  includeObserverNodes?: boolean
}

/**
 * A perturbation to apply to a forked subgraph.
 */
export type Perturbation =
  | { type: 'affect'; valence: number; arousal: number; mode?: 'replace' | 'blend' }
  | { type: 'concept_prime'; concepts: string[]; salience: number }
  | { type: 'remove_nodes'; nodeIds: string[] }
  | { type: 'add_nodes'; nodes: PerturbationNode[] }
  | { type: 'add_edges'; edges: PerturbationEdge[] }

/**
 * A node to inject into a fork via add_nodes perturbation.
 */
export interface PerturbationNode {
  id: string
  label: string
  resonance: number
  centrality: number
  activated?: boolean
}

/**
 * An edge to inject into a fork via add_edges perturbation.
 */
export interface PerturbationEdge {
  sourceId: string
  targetId: string
  edgeType: string
  weight: number
}

/**
 * Handle for an active fork — lightweight metadata.
 */
export interface ClaustrumFork {
  id: string
  createdAt: string
  expiresAt: string
  scope: ForkScope
  nodeCount: number
  edgeCount: number
  perturbationsApplied: number
}

/**
 * Internal fork state — the deep-copied subgraph + derived data.
 */
interface ForkState {
  handle: ClaustrumFork
  nodes: Map<string, CognitiveNode>
  edges: Map<string, CognitiveEdge[]>
  reverseEdges: Map<string, CognitiveEdge[]>
  /** Perturbation-sourced nodes that don't exist in live graph. */
  forkOnlyNodes: Set<string>
  /** Affect override for this fork (null = inherit from base). */
  affectOverride: { valence: number; arousal: number } | null
  /** Whether this fork has been disposed. */
  disposed: false
}

/**
 * Observation kinds for a counterfactual query.
 */
export type ObservationKind =
  | 'activated_nodes'
  | 'reasoning_shift'
  | 'retrieval_distribution'

/**
 * A single observation result.
 */
export interface ObservationResult {
  kind: ObservationKind
  data: unknown
}

/**
 * Complete counterfactual result returned to the caller.
 */
export interface CounterfactualResult {
  forkId: string
  forkExpiresAt: string
  perturbationsApplied: Perturbation[]
  observations: ObservationResult[]
  baseNodeCount: number
  perturbedNodeCount: number
  durationMs: number
}

/**
 * Diff between base and perturbed activated nodes.
 */
export interface ActivatedNodesDiff {
  added: string[]
  removed: string[]
  reweighted: Record<string, number>
}

/**
 * Diff for reasoning shift analysis.
 */
export interface ReasoningShiftDiff {
  base: ReasoningShift | null
  perturbed: ReasoningShift | null
  significance: 'none' | 'minor' | 'major'
}

/**
 * Per-entity retrieval distribution diff.
 */
export interface RetrievalDistributionEntry {
  nodeId: string
  label: string
  baseDegree: number
  perturbedDegree: number
  delta: number
}

/**
 * Default fork scope parameters.
 */
const DEFAULT_FORK_SCOPE: Omit<ForkScope, 'anchors'> = {
  hops: 2,
  maxNodes: 200,
  includeObserverNodes: true,
}

/** Default TTL for a fork (5 minutes). */
const DEFAULT_TTL_SECONDS = 300

/** Maximum TTL (1 hour) — welfare constraint B7.W5. */
const MAX_TTL_SECONDS = 3600

/** Maximum number of concurrent forks. */
const MAX_CONCURRENT_FORKS = 10



export class CounterfactualEngine {
  private forks = new Map<string, ForkState>()
  private ttlTimers = new Map<string, ReturnType<typeof setTimeout>>()

  constructor(
    private logger: ILogger,
  ) {
    this.logger = logger.child ? logger.child('counterfactual') : logger
  }


  /**
   * Fork a subgraph from the live claustrum around the given anchors.
   *
   * Deep-copies all nodes within `hops` of the anchors, along with edges
   * between copied nodes. The fork is isolated — no mutation of the live
   * graph is possible from the fork.
   */
  fork(
    graph: UnifiedGraph,
    scope: ForkScope,
    opts?: { ttlSeconds?: number },
  ): ClaustrumFork {
    if (this.forks.size >= MAX_CONCURRENT_FORKS) {
      throw new Error(
        `Cannot create fork: ${MAX_CONCURRENT_FORKS} concurrent forks already active. ` +
        'Dispose an existing fork first.',
      )
    }

    const resolvedScope = { ...DEFAULT_FORK_SCOPE, ...scope }
    const ttlSeconds = Math.min(
      opts?.ttlSeconds ?? DEFAULT_TTL_SECONDS,
      MAX_TTL_SECONDS,
    )

    const id = `fork-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const now = new Date()

    // Expand anchors by hop radius to find all nodes in scope
    const scopedNodeIds = this.expandScope(graph, resolvedScope)

    // Deep-copy nodes
    const forkNodes = new Map<string, CognitiveNode>()
    for (const nodeId of scopedNodeIds) {
      const original = graph.nodes.get(nodeId)
      if (!original) continue
      if (!resolvedScope.includeObserverNodes && original.source === 'observer') continue
      forkNodes.set(nodeId, { ...original })
    }

    // Copy edges between scoped nodes only
    const forkEdges = new Map<string, CognitiveEdge[]>()
    const forkReverseEdges = new Map<string, CognitiveEdge[]>()
    let edgeCount = 0

    for (const [sourceId, edges] of graph.edges) {
      if (!forkNodes.has(sourceId)) continue
      const copied: CognitiveEdge[] = []
      for (const edge of edges) {
        if (!forkNodes.has(edge.targetId)) continue
        copied.push({ ...edge })
        // Build reverse edge
        const rev = forkReverseEdges.get(edge.targetId) ?? []
        rev.push({ ...edge })
        forkReverseEdges.set(edge.targetId, rev)
      }
      if (copied.length > 0) {
        forkEdges.set(sourceId, copied)
        edgeCount += copied.length
      }
    }

    const handle: ClaustrumFork = {
      id,
      createdAt: now.toISOString(),
      expiresAt: new Date(now.getTime() + ttlSeconds * 1000).toISOString(),
      scope: resolvedScope,
      nodeCount: forkNodes.size,
      edgeCount,
      perturbationsApplied: 0,
    }

    const state: ForkState = {
      handle,
      nodes: forkNodes,
      edges: forkEdges,
      reverseEdges: forkReverseEdges,
      forkOnlyNodes: new Set(),
      affectOverride: null,
      disposed: false,
    }

    this.forks.set(id, state)

    // Schedule TTL expiry
    this.ttlTimers.set(id, setTimeout(() => {
      this.disposeFork(id)
    }, ttlSeconds * 1000))

    this.logger.debug('Fork created', {
      forkId: id,
      nodeCount: forkNodes.size,
      edgeCount,
      ttlSeconds,
    })

    return handle
  }

  /**
   * Get a fork handle by ID. Returns undefined if not found or disposed.
   */
  getFork(forkId: string): ClaustrumFork | undefined {
    return this.forks.get(forkId)?.handle
  }

  /**
   * List all active forks.
   */
  listActiveForks(): ClaustrumFork[] {
    return [...this.forks.values()].map(s => s.handle)
  }

  /**
   * Extend a fork's TTL. Respects the 1-hour hard cap.
   */
  retainFork(forkId: string, additionalSeconds: number): void {
    const state = this.getForkState(forkId)
    const currentExpiry = new Date(state.handle.expiresAt).getTime()
    const newExpiry = Math.min(
      currentExpiry + additionalSeconds * 1000,
      Date.now() + MAX_TTL_SECONDS * 1000,
    )
    state.handle.expiresAt = new Date(newExpiry).toISOString()

    // Reset TTL timer
    const existingTimer = this.ttlTimers.get(forkId)
    if (existingTimer) clearTimeout(existingTimer)

    const remainingMs = newExpiry - Date.now()
    this.ttlTimers.set(forkId, setTimeout(() => {
      this.disposeFork(forkId)
    }, remainingMs))

    this.logger.debug('Fork retained', { forkId, additionalSeconds, newExpiry: state.handle.expiresAt })
  }

  /**
   * Dispose a fork, releasing all its state.
   */
  disposeFork(forkId: string): void {
    const state = this.forks.get(forkId)
    if (!state) return

    const timer = this.ttlTimers.get(forkId)
    if (timer) {
      clearTimeout(timer)
      this.ttlTimers.delete(forkId)
    }

    this.forks.delete(forkId)

    this.logger.debug('Fork disposed', {
      forkId,
      perturbationsApplied: state.handle.perturbationsApplied,
    })
  }

  /**
   * Dispose all active forks. Used during shutdown.
   */
  disposeAll(): void {
    for (const forkId of [...this.forks.keys()]) {
      this.disposeFork(forkId)
    }
  }


  /**
   * Apply a perturbation to a fork's subgraph.
   *
   * Each perturbation type modifies the fork's in-memory state:
   * - `affect`: override the affect vector used during observations
   * - `concept_prime`: boost activation of named concept nodes
   * - `remove_nodes`: delete nodes and their edges from the fork
   * - `add_nodes`: inject new nodes into the fork
   * - `add_edges`: inject new edges between fork nodes
   *
   * NONE of these modify the live claustrum. The isolation guarantee
   * is structural: the fork operates on its own Maps.
   */
  applyPerturbation(forkId: string, perturbation: Perturbation): void {
    const state = this.getForkState(forkId)

    switch (perturbation.type) {
      case 'affect':
        this.applyAffectPerturbation(state, perturbation)
        break
      case 'concept_prime':
        this.applyConceptPrime(state, perturbation)
        break
      case 'remove_nodes':
        this.applyRemoveNodes(state, perturbation)
        break
      case 'add_nodes':
        this.applyAddNodes(state, perturbation)
        break
      case 'add_edges':
        this.applyAddEdges(state, perturbation)
        break
    }

    state.handle.perturbationsApplied += 1

    this.logger.debug('Perturbation applied', {
      forkId,
      type: perturbation.type,
    })
  }


  /**
   * Run observations against a forked subgraph and produce diffs
   * against the base (live) state.
   *
   * For B7.1, supports:
   * - `activated_nodes`: which nodes changed activation state
   * - `reasoning_shift`: would the topic-change classifier fire differently?
   * - `retrieval_distribution`: how did node degrees change
   */
  observe(
    forkId: string,
    kinds: ObservationKind[],
    baseGraph: UnifiedGraph,
    baseReasoning?: ReasoningRecord | null,
    baseMomentum?: ReasoningMomentum | null,
  ): ObservationResult[] {
    const state = this.getForkState(forkId)
    const results: ObservationResult[] = []

    for (const kind of kinds) {
      switch (kind) {
        case 'activated_nodes':
          results.push(this.observeActivatedNodes(state, baseGraph))
          break
        case 'reasoning_shift':
          results.push(this.observeReasoningShift(state, baseReasoning, baseMomentum))
          break
        case 'retrieval_distribution':
          results.push(this.observeRetrievalDistribution(state, baseGraph))
          break
      }
    }

    return results
  }

  /**
   * Convenience: fork, perturb, observe, and optionally dispose in one call.
   */
  explore(
    graph: UnifiedGraph,
    scope: ForkScope,
    perturbations: Perturbation[],
    observeKinds: ObservationKind[],
    opts?: {
      ttlSeconds?: number
      retainAfter?: boolean
      baseReasoning?: ReasoningRecord | null
      baseMomentum?: ReasoningMomentum | null
    },
  ): CounterfactualResult {
    const start = Date.now()
    const baseNodeCount = graph.nodes.size

    // 1. Fork
    const forkHandle = this.fork(graph, scope, { ttlSeconds: opts?.ttlSeconds })

    // 2. Apply perturbations
    for (const p of perturbations) {
      this.applyPerturbation(forkHandle.id, p)
    }

    // 3. Observe
    const observations = this.observe(
      forkHandle.id,
      observeKinds,
      graph,
      opts?.baseReasoning ?? null,
      opts?.baseMomentum ?? null,
    )

    // 4. Optionally dispose
    if (!opts?.retainAfter) {
      this.disposeFork(forkHandle.id)
    }

    const state = this.forks.get(forkHandle.id)
    const perturbedNodeCount = state?.nodes.size ?? forkHandle.nodeCount

    return {
      forkId: forkHandle.id,
      forkExpiresAt: forkHandle.expiresAt,
      perturbationsApplied: perturbations,
      observations,
      baseNodeCount,
      perturbedNodeCount,
      durationMs: Date.now() - start,
    }
  }


  /**
   * Get the affect override for a fork, if set.
   */
  getForkAffect(forkId: string): { valence: number; arousal: number } | null {
    const state = this.forks.get(forkId)
    return state?.affectOverride ?? null
  }

  /**
   * Get all nodes in a fork (for external observation).
   */
  getForkNodes(forkId: string): ReadonlyMap<string, CognitiveNode> | null {
    const state = this.forks.get(forkId)
    return state?.nodes ?? null
  }

  /**
   * Get all edges in a fork (for external observation).
   */
  getForkEdges(forkId: string): ReadonlyMap<string, CognitiveEdge[]> | null {
    const state = this.forks.get(forkId)
    return state?.edges ?? null
  }


  private getForkState(forkId: string): ForkState {
    const state = this.forks.get(forkId)
    if (!state) throw new Error(`Fork ${forkId} not found or expired`)
    return state
  }

  /**
   * Expand anchors by hop radius using BFS, respecting maxNodes cap.
   */
  private expandScope(graph: UnifiedGraph, scope: ForkScope): Set<string> {
    const visited = new Set<string>()
    const queue: Array<{ nodeId: string; depth: number }> = []

    for (const anchor of scope.anchors) {
      if (graph.nodes.has(anchor) && !visited.has(anchor)) {
        visited.add(anchor)
        queue.push({ nodeId: anchor, depth: 0 })
      }
    }

    const maxNodes = scope.maxNodes ?? DEFAULT_FORK_SCOPE.maxNodes!

    while (queue.length > 0) {
      if (visited.size >= maxNodes) break

      const { nodeId, depth } = queue.shift()!
      if (depth >= scope.hops) continue

      // Forward edges
      const outEdges = graph.edges.get(nodeId) ?? []
      for (const edge of outEdges) {
        if (visited.size >= maxNodes) break
        if (!visited.has(edge.targetId) && graph.nodes.has(edge.targetId)) {
          visited.add(edge.targetId)
          queue.push({ nodeId: edge.targetId, depth: depth + 1 })
        }
      }

      // Reverse edges
      const inEdges = graph.reverseEdges.get(nodeId) ?? []
      for (const edge of inEdges) {
        if (visited.size >= maxNodes) break
        if (!visited.has(edge.sourceId) && graph.nodes.has(edge.sourceId)) {
          visited.add(edge.sourceId)
          queue.push({ nodeId: edge.sourceId, depth: depth + 1 })
        }
      }
    }

    return visited
  }


  private applyAffectPerturbation(
    state: ForkState,
    p: { valence: number; arousal: number; mode?: 'replace' | 'blend' },
  ): void {
    if (p.mode === 'blend' && state.affectOverride) {
      state.affectOverride = {
        valence: (state.affectOverride.valence + p.valence) / 2,
        arousal: (state.affectOverride.arousal + p.arousal) / 2,
      }
    } else {
      state.affectOverride = { valence: p.valence, arousal: p.arousal }
    }
  }

  private applyConceptPrime(
    state: ForkState,
    p: { concepts: string[]; salience: number },
  ): void {
    for (const concept of p.concepts) {
      // Find matching node by label or id
      let node = state.nodes.get(concept)
      if (!node) {
        for (const [, n] of state.nodes) {
          if (n.label.toLowerCase() === concept.toLowerCase()) {
            node = n
            break
          }
        }
      }
      if (!node) continue

      // Boost activation
      node.activated = true
      node.resonance = Math.min(1, node.resonance + p.salience * 0.3)

      // Propagate one hop: slightly boost neighbor activation
      const outEdges = state.edges.get(node.id) ?? []
      const inEdges = state.reverseEdges.get(node.id) ?? []
      const neighborBoost = p.salience * 0.15

      for (const edge of outEdges) {
        const neighbor = state.nodes.get(edge.targetId)
        if (neighbor) {
          neighbor.resonance = Math.min(1, neighbor.resonance + neighborBoost)
        }
      }
      for (const edge of inEdges) {
        const neighbor = state.nodes.get(edge.sourceId)
        if (neighbor) {
          neighbor.resonance = Math.min(1, neighbor.resonance + neighborBoost)
        }
      }
    }
  }

  private applyRemoveNodes(
    state: ForkState,
    p: { nodeIds: string[] },
  ): void {
    for (const nodeId of p.nodeIds) {
      state.nodes.delete(nodeId)
      state.forkOnlyNodes.delete(nodeId)
      state.edges.delete(nodeId)

      // Remove edges pointing to this node
      for (const [, edges] of state.edges) {
        const filtered = edges.filter(e => e.targetId !== nodeId)
        if (filtered.length === 0) {
          // Don't delete the entry — it may have been the source
        }
      }

      // Clean up reverse edges
      state.reverseEdges.delete(nodeId)
      for (const [, edges] of state.reverseEdges) {
        const idx = edges.findIndex(e => e.sourceId === nodeId)
        if (idx >= 0) edges.splice(idx, 1)
      }
    }

    // Update handle counts
    state.handle.nodeCount = state.nodes.size
    state.handle.edgeCount = this.countEdges(state)
  }

  private applyAddNodes(
    state: ForkState,
    p: { nodes: PerturbationNode[] },
  ): void {
    for (const pNode of p.nodes) {
      const node: CognitiveNode = {
        id: pNode.id,
        label: pNode.label,
        source: 'observer', // synthetic origin
        resonance: pNode.resonance,
        centrality: pNode.centrality,
        activated: pNode.activated ?? true,
      }
      state.nodes.set(pNode.id, node)
      state.forkOnlyNodes.add(pNode.id)
    }

    state.handle.nodeCount = state.nodes.size
  }

  private applyAddEdges(
    state: ForkState,
    p: { edges: PerturbationEdge[] },
  ): void {
    for (const pEdge of p.edges) {
      const edge: CognitiveEdge = {
        sourceId: pEdge.sourceId,
        targetId: pEdge.targetId,
        origin: 'observer',
        edgeType: pEdge.edgeType,
        weight: pEdge.weight,
      }

      const outEdges = state.edges.get(pEdge.sourceId) ?? []
      outEdges.push(edge)
      state.edges.set(pEdge.sourceId, outEdges)

      const revEdges = state.reverseEdges.get(pEdge.targetId) ?? []
      revEdges.push(edge)
      state.reverseEdges.set(pEdge.targetId, revEdges)
    }

    state.handle.edgeCount = this.countEdges(state)
  }


  private observeActivatedNodes(
    state: ForkState,
    baseGraph: UnifiedGraph,
  ): ObservationResult {
    const diff: ActivatedNodesDiff = { added: [], removed: [], reweighted: {} }

    for (const [id, node] of state.nodes) {
      const baseNode = baseGraph.nodes.get(id)
      if (!baseNode) continue

      const wasActivated = baseNode.activated
      const nowActivated = node.activated

      if (!wasActivated && nowActivated) {
        diff.added.push(id)
      } else if (wasActivated && !nowActivated) {
        diff.removed.push(id)
      }

      const resonanceDelta = Math.abs(node.resonance - baseNode.resonance)
      if (resonanceDelta > 0.05) {
        diff.reweighted[id] = Math.round(resonanceDelta * 1000) / 1000
      }
    }

    return { kind: 'activated_nodes', data: diff }
  }

  private observeReasoningShift(
    state: ForkState,
    baseReasoning: ReasoningRecord | null | undefined,
    baseMomentum: ReasoningMomentum | null | undefined,
  ): ObservationResult {
    const result: ReasoningShiftDiff = {
      base: baseReasoning?.shift ?? null,
      perturbed: null,
      significance: 'none',
    }

    // Estimate whether perturbation would cause a reasoning shift
    // by checking if activated nodes differ significantly from base.
    if (baseMomentum) {
      const activationRatio = state.nodes.size > 0
        ? [...state.nodes.values()].filter(n => n.activated).length / state.nodes.size
        : 0
      const baseRatio = baseMomentum.novelty

      const delta = Math.abs(activationRatio - baseRatio)
      if (delta > 0.3) {
        result.perturbed = {
          type: 'topic_change',
          triggerConcepts: [],
          confidence: Math.min(1, delta),
          detectedAt: Date.now(),
        }
        result.significance = delta > 0.5 ? 'major' : 'minor'
      }
    }

    return { kind: 'reasoning_shift', data: result }
  }

  private observeRetrievalDistribution(
    state: ForkState,
    baseGraph: UnifiedGraph,
  ): ObservationResult {
    const entries: RetrievalDistributionEntry[] = []

    for (const [id, node] of state.nodes) {
      const baseOutDegree = baseGraph.edges.get(id)?.length ?? 0
      const perturbedOutDegree = state.edges.get(id)?.length ?? 0
      const delta = perturbedOutDegree - baseOutDegree

      if (delta !== 0) {
        entries.push({
          nodeId: id,
          label: node.label,
          baseDegree: baseOutDegree,
          perturbedDegree: perturbedOutDegree,
          delta,
        })
      }
    }

    return { kind: 'retrieval_distribution', data: { entries } }
  }


  private countEdges(state: ForkState): number {
    let count = 0
    for (const [, edges] of state.edges) {
      count += edges.length
    }
    return count
  }
}
