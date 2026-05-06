/**
 * A2 vector-projection composer tests — salience math, top-N cap,
 * layer aggregation, layer subset filtering, empty-state handling.
 */

import { describe, it, expect } from 'vitest'

import { composeVectorProjection } from './vector-projection.js'
import type {
  CognitiveNode,
  MentalState,
  ReasoningMomentum,
  UnifiedGraph,
} from '../types.js'

function node(opts: Partial<CognitiveNode> & { id: string; label: string; activated?: boolean }): CognitiveNode {
  return {
    id: opts.id,
    label: opts.label,
    source: 'model',
    resonance: opts.resonance ?? 0,
    centrality: opts.centrality ?? 0,
    activated: opts.activated ?? true,
    modelConfidence: opts.modelConfidence,
    modelLayers: opts.modelLayers,
    potentiation: opts.potentiation,
    nodeType: opts.nodeType,
    content: opts.content,
  }
}

function buildGraph(nodes: CognitiveNode[]): UnifiedGraph {
  const map = new Map<string, CognitiveNode>()
  for (const n of nodes) map.set(n.id, n)
  return {
    nodes: map,
    edges: new Map(),
    reverseEdges: new Map(),
    sourceBreakdown: { model: 0, memory: 0, both: 0 },
    edgeCount: 0,
    builtAt: Date.now(),
  } as UnifiedGraph
}

const baselineMomentum: ReasoningMomentum = {
  trendingConcepts: [],
  novelty: 0,
  confidence: 0,
  topicShift: false,
  turnsInDirection: 0,
}

function buildState(graph: UnifiedGraph): MentalState {
  return {
    graph,
    resonanceHubs: [],
    gaps: [],
    recentDiscoveries: [],
    affect: null,
    foci: [],
    momentum: baselineMomentum,
    coherence: 0,
    integration: 0,
    computedAt: Date.now(),
    durationMs: 0,
  }
}

describe('composeVectorProjection', () => {
  it('returns null when no nodes are activated', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', activated: false, modelConfidence: 0.8, modelLayers: [14] }),
    ]))
    expect(composeVectorProjection(state)).toBeNull()
  })

  it('returns null when activated nodes have no model layers', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 0.8 /* no modelLayers */ }),
    ]))
    expect(composeVectorProjection(state)).toBeNull()
  })

  it('emits one contribution per activated node with model layers', () => {
    const state = buildState(buildGraph([
      node({ id: 'warmth', label: 'warmth', modelConfidence: 0.8, modelLayers: [14, 15, 16] }),
      node({ id: 'rigor',  label: 'rigor',  modelConfidence: 0.6, modelLayers: [20, 21] }),
    ]))
    const p = composeVectorProjection(state)
    expect(p).not.toBeNull()
    expect(p!.contributions.map(c => c.nodeId).sort()).toEqual(['rigor', 'warmth'])
    // perLayer carries placeholder zero-length Float32Arrays at each contributing layer
    expect([...p!.perLayer.keys()].sort((a, b) => a - b)).toEqual([14, 15, 16, 20, 21])
    for (const arr of p!.perLayer.values()) {
      expect(arr).toBeInstanceOf(Float32Array)
      expect(arr.length).toBe(0)
    }
  })

  it('orders contributions by salience descending', () => {
    const state = buildState(buildGraph([
      node({ id: 'low',  label: 'low',  modelConfidence: 0.2, modelLayers: [14] }),
      node({ id: 'high', label: 'high', modelConfidence: 0.9, modelLayers: [14] }),
      node({ id: 'mid',  label: 'mid',  modelConfidence: 0.5, modelLayers: [14] }),
    ]))
    const p = composeVectorProjection(state)!
    expect(p.contributions.map(c => c.nodeId)).toEqual(['high', 'mid', 'low'])
    expect(p.contributions[0].salience).toBeGreaterThan(p.contributions[1].salience)
  })

  it('applies maxNodes cap', () => {
    const nodes: CognitiveNode[] = []
    for (let i = 0; i < 10; i++) {
      nodes.push(node({ id: `n${i}`, label: `n${i}`, modelConfidence: 0.5, modelLayers: [14] }))
    }
    const p = composeVectorProjection(buildState(buildGraph(nodes)), { maxNodes: 3 })!
    expect(p.contributions).toHaveLength(3)
  })

  it('applies layerSubset filter', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 0.8, modelLayers: [14, 15, 20] }),
      node({ id: 'b', label: 'b', modelConfidence: 0.6, modelLayers: [21, 22] }),
    ]))
    const p = composeVectorProjection(state, { layerSubset: [14, 15] })!
    // only 'a' has layers in subset; 'b' filtered out entirely
    expect(p.contributions.map(c => c.nodeId)).toEqual(['a'])
    expect(p.contributions[0].layers).toEqual([14, 15])
    expect([...p.perLayer.keys()].sort()).toEqual([14, 15])
  })

  it('weight scales with magnitudeScale', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 0.8, modelLayers: [14] }),
    ]))
    const p1 = composeVectorProjection(state, { magnitudeScale: 0.1 })!
    const p2 = composeVectorProjection(state, { magnitudeScale: 0.5 })!
    expect(p2.contributions[0].weight).toBeCloseTo(p1.contributions[0].weight * 5)
  })

  it('falls back to resonance when modelConfidence is absent', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', resonance: 0.5, modelLayers: [14] }),
    ]))
    const p = composeVectorProjection(state)!
    expect(p.contributions[0].salience).toBeGreaterThan(0)
  })

  it('includes vindex / target-model metadata when ctx is supplied', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 0.8, modelLayers: [14] }),
    ]))
    const p = composeVectorProjection(state, undefined, { vindexId: 'gemma-3-1b', targetModelId: 'm-1' })!
    expect(p.metadata.vindexId).toBe('gemma-3-1b')
    expect(p.metadata.targetModelId).toBe('m-1')
    expect(p.metadata.contributingNodes).toEqual(['a'])
    expect(p.metadata.composedAt).toBeTruthy()
  })

  it('returns null when zero base confidence on all nodes', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 0, resonance: 0, modelLayers: [14] }),
    ]))
    expect(composeVectorProjection(state)).toBeNull()
  })
})

describe('composeVectorProjection — vectorSource callback', () => {
  it('fills perLayer with weighted Float32Array when vectorSource resolves', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14] }),
    ]))
    // Source returns [1, 2, 3, 4] for any (node, layer) — easy to verify.
    const source = () => new Float32Array([1, 2, 3, 4])
    const p = composeVectorProjection(state, { magnitudeScale: 0.5 }, {}, source)!
    const layer14 = p.perLayer.get(14)!
    expect(layer14.length).toBe(4)
    // Weight = salience * 0.5; for a single node we just need positive non-zero
    expect(layer14[0]).toBeGreaterThan(0)
    expect(layer14[1] / layer14[0]).toBeCloseTo(2, 5)
    expect(layer14[2] / layer14[0]).toBeCloseTo(3, 5)
  })

  it('accumulates weighted sums across multiple nodes at the same layer', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14] }),
      node({ id: 'b', label: 'b', modelConfidence: 1.0, modelLayers: [14] }),
    ]))
    let calls = 0
    const source = () => {
      calls++
      return new Float32Array([1, 1, 1])
    }
    const p = composeVectorProjection(state, { magnitudeScale: 0.5 }, {}, source)!
    const layer14 = p.perLayer.get(14)!
    expect(layer14.length).toBe(3)
    expect(calls).toBe(2)
    // Both nodes contribute weight w each; layer14[i] = 2*w
    const expected = p.contributions[0].weight + p.contributions[1].weight
    expect(layer14[0]).toBeCloseTo(expected, 5)
  })

  it('falls back to placeholder when vectorSource returns null', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14] }),
    ]))
    const p = composeVectorProjection(state, undefined, {}, () => null)!
    const layer14 = p.perLayer.get(14)!
    expect(layer14.length).toBe(0)
  })

  it('keeps existing accumulator when a later vector mismatches dimensions', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14] }),
      node({ id: 'b', label: 'b', modelConfidence: 1.0, modelLayers: [14] }),
    ]))
    let n = 0
    const source = (): Float32Array => {
      n++
      return n === 1 ? new Float32Array([1, 2, 3, 4]) : new Float32Array([5, 5]) // mismatch
    }
    const p = composeVectorProjection(state, undefined, {}, source)!
    const layer14 = p.perLayer.get(14)!
    expect(layer14.length).toBe(4) // first contribution preserved
  })

  it('separately keys layers when nodes contribute to different layers', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14] }),
      node({ id: 'b', label: 'b', modelConfidence: 1.0, modelLayers: [20] }),
    ]))
    const source = (_n: any, layer: number) =>
      new Float32Array([layer === 14 ? 1.0 : 0.0, layer === 14 ? 0.0 : 1.0])
    const p = composeVectorProjection(state, undefined, {}, source)!
    expect(p.perLayer.get(14)![0]).toBeGreaterThan(0)
    expect(p.perLayer.get(14)![1]).toBe(0)
    expect(p.perLayer.get(20)![0]).toBe(0)
    expect(p.perLayer.get(20)![1]).toBeGreaterThan(0)
  })
})

describe('composeVectorProjection — targetResidualFraction calibration', () => {
  function l2(v: Float32Array): number {
    let s = 0
    for (let i = 0; i < v.length; i++) s += v[i] * v[i]
    return Math.sqrt(s)
  }

  it('rescales each layer to target_fraction × baseline_norm', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14] }),
    ]))
    const source = () => new Float32Array([3, 4])
    const baseline = (layer: number) => (layer === 14 ? 100 : null)
    const p = composeVectorProjection(
      state,
      { targetResidualFraction: 0.1 },
      {},
      source,
      baseline,
    )!
    const v14 = p.perLayer.get(14)!
    expect(l2(v14)).toBeCloseTo(10, 4)
    expect(v14[1] / v14[0]).toBeCloseTo(4 / 3, 4)
  })

  it('leaves layer untouched when baselineNormSource returns null', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14] }),
    ]))
    const source = () => new Float32Array([3, 4])
    const baseline = () => null
    const p = composeVectorProjection(
      state,
      { targetResidualFraction: 0.1, magnitudeScale: 1.0 },
      {},
      source,
      baseline,
    )!
    const v14 = p.perLayer.get(14)!
    const norm = l2(v14)
    expect(norm).toBeGreaterThan(0)
    expect(norm).not.toBeCloseTo(10, 4)
  })

  it('is a no-op when baselineNormSource is omitted', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14] }),
    ]))
    const source = () => new Float32Array([3, 4])
    const p = composeVectorProjection(
      state,
      { targetResidualFraction: 0.05 },
      {},
      source,
    )!
    const v14 = p.perLayer.get(14)!
    expect(l2(v14)).toBeGreaterThan(0)
    expect(l2(v14)).toBeLessThan(5)
  })

  it('rescales independently per layer', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14, 20] }),
    ]))
    const source = () => new Float32Array([3, 4])
    const baseline = (layer: number) => layer === 14 ? 100 : 50
    const p = composeVectorProjection(
      state,
      { targetResidualFraction: 0.1 },
      {},
      source,
      baseline,
    )!
    expect(l2(p.perLayer.get(14)!)).toBeCloseTo(10, 4)
    expect(l2(p.perLayer.get(20)!)).toBeCloseTo(5, 4)
  })

  it('rejects negative or zero baseline norms (treats as unknown)', () => {
    const state = buildState(buildGraph([
      node({ id: 'a', label: 'a', modelConfidence: 1.0, modelLayers: [14] }),
    ]))
    const source = () => new Float32Array([3, 4])
    const baseline = () => 0
    const p = composeVectorProjection(
      state,
      { targetResidualFraction: 0.1, magnitudeScale: 1.0 },
      {},
      source,
      baseline,
    )!
    const v14 = p.perLayer.get(14)!
    // Untouched (no rescale): weight × [3,4]; weight is salience-bound.
    expect(l2(v14)).toBeGreaterThan(0)
    expect(l2(v14)).not.toBeCloseTo(10, 4)
  })
})
