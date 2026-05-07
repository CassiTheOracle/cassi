/**
 * Tests for CounterfactualEngine (B7.1) — forking, perturbation, isolation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { CounterfactualEngine } from './counterfactual-engine.js'
import type {
  UnifiedGraph,
  CognitiveNode,
  CognitiveEdge,
  ReasoningRecord,
  ReasoningMomentum,
} from './types.js'

function mockLogger() {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => mockLogger(),
  } as any
}

/** Build a small test graph with known topology. */
function buildTestGraph(): UnifiedGraph {
  const nodes = new Map<string, CognitiveNode>()
  const edges = new Map<string, CognitiveEdge[]>()
  const reverseEdges = new Map<string, CognitiveEdge[]>()

  // 7 nodes in a known layout:
  //  A -- B -- C -- D
  //       |         |
  //       E -- F    G
  const labels = ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf']
  const ids = ['a', 'b', 'c', 'd', 'e', 'f', 'g']

  for (let i = 0; i < ids.length; i++) {
    nodes.set(ids[i], {
      id: ids[i],
      label: labels[i],
      source: 'model',
      resonance: 0.5,
      centrality: 0.1,
      activated: i < 3, // a, b, c are activated
    })
  }

  const edgePairs: [string, string][] = [
    ['a', 'b'], ['b', 'c'], ['c', 'd'], ['b', 'e'], ['e', 'f'], ['d', 'g'],
  ]

  for (const [src, tgt] of edgePairs) {
    const edge: CognitiveEdge = {
      sourceId: src, targetId: tgt, origin: 'model', edgeType: 'related', weight: 0.5,
    }
    const out = edges.get(src) ?? []
    out.push(edge)
    edges.set(src, out)

    const rev = reverseEdges.get(tgt) ?? []
    rev.push(edge)
    reverseEdges.set(tgt, rev)
  }

  return { nodes, edges, reverseEdges, sourceBreakdown: { model: 7 }, edgeCount: 6, builtAt: Date.now() }
}

function deepCloneGraph(g: UnifiedGraph): UnifiedGraph {
  return {
    nodes: new Map([...g.nodes].map(([k, v]) => [k, { ...v }])),
    edges: new Map([...g.edges].map(([k, vs]) => [k, vs.map(e => ({ ...e }))])),
    reverseEdges: new Map([...g.reverseEdges].map(([k, vs]) => [k, vs.map(e => ({ ...e }))])),
    sourceBreakdown: { ...g.sourceBreakdown },
    edgeCount: g.edgeCount,
    builtAt: g.builtAt,
  }
}

function serializeGraph(g: UnifiedGraph): string {
  const entries: string[] = []
  for (const [id, node] of g.nodes) {
    entries.push(`node:${id}:${node.label}:${node.activated}:${node.resonance}`)
  }
  for (const [src, edgeList] of g.edges) {
    for (const e of edgeList) {
      entries.push(`edge:${src}->${e.targetId}:${e.weight}`)
    }
  }
  return entries.sort().join('|')
}

describe('CounterfactualEngine', () => {
  let engine: CounterfactualEngine

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    engine = new CounterfactualEngine(mockLogger())
  })

  afterEach(() => {
    engine.disposeAll()
    vi.useRealTimers()
  })


  describe('fork()', () => {
    it('should create a fork with correct scope', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 1 })

      expect(handle.id).toMatch(/^fork-/)
      expect(handle.nodeCount).toBe(2) // a + b (1 hop)
      expect(handle.edgeCount).toBe(1) // a->b
      expect(handle.perturbationsApplied).toBe(0)
    })

    it('should expand to 2 hops by default', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })

      // 2 hops from 'a': a, b, (1 hop) c, e, (2 hops)
      expect(handle.nodeCount).toBe(4) // a, b, c, e
    })

    it('should respect maxNodes cap', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 5, maxNodes: 3 })

      expect(handle.nodeCount).toBeLessThanOrEqual(3)
    })

    it('should exclude observer nodes when includeObserverNodes=false', () => {
      const graph = buildTestGraph()
      // Add an observer node
      graph.nodes.set('obs1', {
        id: 'obs1', label: 'observer-insight', source: 'observer',
        resonance: 0.3, centrality: 0.1, activated: false,
      })
      graph.edges.set('a', [
        ...(graph.edges.get('a') ?? []),
        { sourceId: 'a', targetId: 'obs1', origin: 'observer', edgeType: 'insight', weight: 0.2 },
      ])

      const handle = engine.fork(graph, { anchors: ['a'], hops: 1, includeObserverNodes: false })
      const forkNodes = engine.getForkNodes(handle.id)!
      expect(forkNodes.has('obs1')).toBe(false)
    })

    it('should throw when max concurrent forks exceeded', () => {
      const graph = buildTestGraph()
      for (let i = 0; i < 10; i++) {
        engine.fork(graph, { anchors: ['a'], hops: 1 })
      }
      expect(() => engine.fork(graph, { anchors: ['a'], hops: 1 })).toThrow(
        /10 concurrent forks/,
      )
    })

    it('should set TTL from opts or default to 5 minutes', () => {
      const graph = buildTestGraph()
      const h1 = engine.fork(graph, { anchors: ['a'] })
      const h2 = engine.fork(graph, { anchors: ['a'] }, { ttlSeconds: 120 })

      const t1 = new Date(h1.expiresAt).getTime() - new Date(h1.createdAt).getTime()
      const t2 = new Date(h2.expiresAt).getTime() - new Date(h2.createdAt).getTime()

      expect(t1).toBe(300_000) // 5 minutes
      expect(t2).toBe(120_000) // 2 minutes
    })

    it('should enforce 1-hour max TTL', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] }, { ttlSeconds: 99999 })

      const ttl = new Date(handle.expiresAt).getTime() - new Date(handle.createdAt).getTime()
      expect(ttl).toBe(3_600_000) // 1 hour
    })
  })


  describe('disposeFork()', () => {
    it('should remove fork from registry', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })

      engine.disposeFork(handle.id)

      expect(engine.getFork(handle.id)).toBeUndefined()
      expect(engine.listActiveForks()).toHaveLength(0)
    })

    it('should be safe to call on non-existent fork', () => {
      expect(() => engine.disposeFork('nonexistent')).not.toThrow()
    })
  })

  describe('TTL expiry', () => {
    it('should auto-dispose fork after TTL', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] }, { ttlSeconds: 60 })

      expect(engine.getFork(handle.id)).toBeDefined()

      vi.advanceTimersByTime(61_000)

      expect(engine.getFork(handle.id)).toBeUndefined()
    })
  })

  describe('retainFork()', () => {
    it('should extend TTL', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] }, { ttlSeconds: 60 })

      engine.retainFork(handle.id, 120)

      // Should still be alive after original TTL
      vi.advanceTimersByTime(65_000)
      expect(engine.getFork(handle.id)).toBeDefined()

      // Should be gone after extended TTL
      vi.advanceTimersByTime(120_000)
      expect(engine.getFork(handle.id)).toBeUndefined()
    })

    it('should respect 1-hour max cap', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] }, { ttlSeconds: 60 })

      engine.retainFork(handle.id, 999999)

      const remaining = new Date(handle.expiresAt).getTime() - Date.now()
      expect(remaining).toBeLessThanOrEqual(3_600_000)
    })
  })


  describe('isolation', () => {
    it('MUST NOT mutate live graph after perturbation', () => {
      const graph = buildTestGraph()
      const before = serializeGraph(graph)

      const handle = engine.fork(graph, { anchors: ['a'], hops: 2 })

      // Apply aggressive perturbations
      engine.applyPerturbation(handle.id, { type: 'concept_prime', concepts: ['alpha'], salience: 1.0 })
      engine.applyPerturbation(handle.id, { type: 'add_nodes', nodes: [
        { id: 'new1', label: 'injected', resonance: 0.9, centrality: 0.5 },
      ]})
      engine.applyPerturbation(handle.id, { type: 'add_edges', edges: [
        { sourceId: 'a', targetId: 'new1', edgeType: 'synthetic', weight: 0.8 },
      ]})
      engine.applyPerturbation(handle.id, { type: 'remove_nodes', nodeIds: ['b'] })

      // Verify live graph is byte-identical
      const after = serializeGraph(graph)
      expect(after).toBe(before)

      engine.disposeFork(handle.id)
    })

    it('fork node mutations must not affect live nodes', () => {
      const graph = buildTestGraph()
      const originalResonance = graph.nodes.get('a')!.resonance

      const handle = engine.fork(graph, { anchors: ['a'], hops: 2 })

      engine.applyPerturbation(handle.id, {
        type: 'concept_prime', concepts: ['alpha'], salience: 1.0,
      })

      // Fork node should be modified
      const forkNodes = engine.getForkNodes(handle.id)!
      expect(forkNodes.get('a')!.resonance).toBeGreaterThan(originalResonance)

      // Live node must be unchanged
      expect(graph.nodes.get('a')!.resonance).toBe(originalResonance)
    })
  })


  describe('affect perturbation', () => {
    it('should override affect vector', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })

      engine.applyPerturbation(handle.id, {
        type: 'affect', valence: 0.8, arousal: 0.3, mode: 'replace',
      })

      expect(engine.getForkAffect(handle.id)).toEqual({ valence: 0.8, arousal: 0.3 })
    })

    it('should blend affect when mode=blend', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })

      engine.applyPerturbation(handle.id, {
        type: 'affect', valence: 0.6, arousal: 0.4, mode: 'replace',
      })
      engine.applyPerturbation(handle.id, {
        type: 'affect', valence: 0.2, arousal: 0.8, mode: 'blend',
      })

      const affect = engine.getForkAffect(handle.id)!
      expect(affect.valence).toBeCloseTo(0.4, 5)
      expect(affect.arousal).toBeCloseTo(0.6, 5)
    })
  })

  describe('concept_prime perturbation', () => {
    it('should activate matching nodes and boost neighbors', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 2 })

      engine.applyPerturbation(handle.id, {
        type: 'concept_prime', concepts: ['alpha'], salience: 1.0,
      })

      const nodes = engine.getForkNodes(handle.id)!
      const alpha = nodes.get('a')!
      expect(alpha.activated).toBe(true)
      expect(alpha.resonance).toBeGreaterThan(0.5)

      // Neighbor 'b' should get a slight boost from one-hop propagation
      const bravo = nodes.get('b')!
      expect(bravo.resonance).toBeGreaterThan(0.5)
    })

    it('should match by label case-insensitively', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 2 })

      engine.applyPerturbation(handle.id, {
        type: 'concept_prime', concepts: ['ALPHA'], salience: 0.5,
      })

      const nodes = engine.getForkNodes(handle.id)!
      expect(nodes.get('a')!.resonance).toBeGreaterThan(0.5)
    })
  })

  describe('remove_nodes perturbation', () => {
    it('should remove nodes and their edges from fork', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 2 })

      engine.applyPerturbation(handle.id, { type: 'remove_nodes', nodeIds: ['b'] })

      const nodes = engine.getForkNodes(handle.id)!
      expect(nodes.has('b')).toBe(false)
    })
  })

  describe('add_nodes perturbation', () => {
    it('should inject synthetic nodes into fork', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })

      engine.applyPerturbation(handle.id, { type: 'add_nodes', nodes: [
        { id: 'synth1', label: 'synthetic-concept', resonance: 0.7, centrality: 0.3, activated: true },
      ]})

      const nodes = engine.getForkNodes(handle.id)!
      expect(nodes.has('synth1')).toBe(true)
      expect(nodes.get('synth1')!.source).toBe('observer') // synthetic
    })
  })

  describe('add_edges perturbation', () => {
    it('should inject edges between fork nodes', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a', 'b'] })

      engine.applyPerturbation(handle.id, { type: 'add_edges', edges: [
        { sourceId: 'a', targetId: 'b', edgeType: 'counterfactual', weight: 0.9 },
      ]})

      const edges = engine.getForkEdges(handle.id)!
      const aEdges = edges.get('a') ?? []
      const cfEdge = aEdges.find(e => e.edgeType === 'counterfactual')
      expect(cfEdge).toBeDefined()
      expect(cfEdge!.weight).toBe(0.9)
    })
  })


  describe('observe()', () => {
    it('should detect activated_nodes diff', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 2 })

      // Initially 'e' is not activated in base. Prime a concept that
      // doesn't activate e directly, then add it.
      engine.applyPerturbation(handle.id, { type: 'concept_prime', concepts: ['echo'], salience: 0.9 })

      const results = engine.observe(handle.id, ['activated_nodes'], graph)
      const obs = results[0]

      expect(obs.kind).toBe('activated_nodes')
      const diff = obs.data as any
      expect(diff.added).toContain('e')
    })

    it('should detect retrieval_distribution diff after add_edges', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })

      engine.applyPerturbation(handle.id, { type: 'add_edges', edges: [
        { sourceId: 'a', targetId: 'b', edgeType: 'test', weight: 0.5 },
      ]})

      const results = engine.observe(handle.id, ['retrieval_distribution'], graph)
      const obs = results[0]

      expect(obs.kind).toBe('retrieval_distribution')
      const data = obs.data as any
      expect(data.entries.length).toBeGreaterThan(0)
      const aEntry = data.entries.find((e: any) => e.nodeId === 'a')
      expect(aEntry).toBeDefined()
      expect(aEntry.delta).toBe(1)
    })

    it('should produce reasoning_shift observation', () => {
      const graph = buildTestGraph()
      const baseMomentum: ReasoningMomentum = {
        trendingConcepts: ['alpha'],
        novelty: 0.3,
        confidence: 0.7,
        topicShift: false,
      }

      const handle = engine.fork(graph, { anchors: ['a'], hops: 2 })
      const results = engine.observe(handle.id, ['reasoning_shift'], graph, null, baseMomentum)

      expect(results[0].kind).toBe('reasoning_shift')
    })
  })


  describe('explore()', () => {
    it('should fork-perturb-observe-dispose in one call', () => {
      const graph = buildTestGraph()

      const result = engine.explore(
        graph,
        { anchors: ['a'], hops: 2 },
        [{ type: 'concept_prime', concepts: ['alpha'], salience: 0.8 }],
        ['activated_nodes'],
      )

      expect(result.perturbationsApplied).toHaveLength(1)
      expect(result.observations).toHaveLength(1)
      expect(result.observations[0].kind).toBe('activated_nodes')
      expect(result.durationMs).toBeGreaterThanOrEqual(0)

      // Fork should be auto-disposed
      expect(engine.listActiveForks()).toHaveLength(0)
    })

    it('should retain fork when retainAfter=true', () => {
      const graph = buildTestGraph()

      const result = engine.explore(
        graph,
        { anchors: ['a'], hops: 2 },
        [{ type: 'concept_prime', concepts: ['alpha'], salience: 0.8 }],
        ['activated_nodes'],
        { retainAfter: true },
      )

      expect(engine.listActiveForks()).toHaveLength(1)
      expect(engine.getFork(result.forkId)).toBeDefined()
    })

    it('should report node counts', () => {
      const graph = buildTestGraph()

      const result = engine.explore(
        graph,
        { anchors: ['a'], hops: 2 },
        [],
        ['activated_nodes'],
      )

      expect(result.baseNodeCount).toBe(7)
      expect(result.perturbedNodeCount).toBe(4) // a, b, c, e
    })
  })


  describe('multiple perturbations', () => {
    it('should track count of applied perturbations', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })

      engine.applyPerturbation(handle.id, { type: 'concept_prime', concepts: ['alpha'], salience: 0.5 })
      engine.applyPerturbation(handle.id, { type: 'add_nodes', nodes: [
        { id: 'x', label: 'extra', resonance: 0.5, centrality: 0.1 },
      ]})

      expect(handle.perturbationsApplied).toBe(2)
    })
  })


  describe('emitContribution (B8)', () => {
    it('uses the affect-override path when an affect perturbation is set', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })
      engine.applyPerturbation(handle.id, { type: 'affect', valence: 0.5, arousal: 0.6 })

      const contribution = engine.emitContribution(handle.id, 'neutral', { valence: 0, arousal: 0 })
      expect(contribution).not.toBeNull()
      expect(contribution!.color).toBe('excited')
      expect(contribution!.effectiveAffect).toEqual({ valence: 0.5, arousal: 0.6 })
      expect(contribution!.perturbations).toHaveLength(1)
      expect(contribution!.perturbations[0].type).toBe('affect')
    })

    it('falls back to baseColor + baseAffect when no affect override is present', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })
      engine.applyPerturbation(handle.id, { type: 'concept_prime', concepts: ['alpha'], salience: 0.4 })

      const contribution = engine.emitContribution(handle.id, 'calm', { valence: 0.3, arousal: 0.1 })
      expect(contribution).not.toBeNull()
      expect(contribution!.color).toBe('calm')
      expect(contribution!.effectiveAffect).toEqual({ valence: 0.3, arousal: 0.1 })
    })

    it('returns null when neither override nor baseColor is available', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })
      const contribution = engine.emitContribution(handle.id, null, null)
      expect(contribution).toBeNull()
    })

    it('returns null for an unknown forkId', () => {
      const contribution = engine.emitContribution('does-not-exist', 'calm', { valence: 0.3, arousal: 0.1 })
      expect(contribution).toBeNull()
    })

    it('captures activated nodes with their resonance as salience', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 2 })
      const contribution = engine.emitContribution(handle.id, 'calm', { valence: 0.3, arousal: 0.1 })
      expect(contribution).not.toBeNull()
      const activatedNodeIds = contribution!.contributedNodes.filter(n => n.activated).map(n => n.nodeId)
      expect(activatedNodeIds.sort()).toEqual(['a', 'b', 'c'])
    })

    it('flags forkOnly nodes introduced by add_nodes perturbations', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })
      engine.applyPerturbation(handle.id, { type: 'add_nodes', nodes: [
        { id: 'novel', label: 'novel-concept', resonance: 0.7, centrality: 0.1, activated: true },
      ]})

      const contribution = engine.emitContribution(handle.id, 'engaged', { valence: 0.4, arousal: 0.5 })
      expect(contribution).not.toBeNull()
      const novel = contribution!.contributedNodes.find(n => n.nodeId === 'novel')
      expect(novel).toBeDefined()
      expect(novel!.forkOnly).toBe(true)
    })

    it('clears the perturbation log on disposeFork', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'] })
      engine.applyPerturbation(handle.id, { type: 'affect', valence: 0.4, arousal: 0.3 })
      const before = engine.emitContribution(handle.id, 'neutral', { valence: 0, arousal: 0 })
      expect(before!.perturbations).toHaveLength(1)

      engine.disposeFork(handle.id)
      const after = engine.emitContribution(handle.id, 'neutral', { valence: 0, arousal: 0 })
      expect(after).toBeNull()
    })
  })


  describe('explore() with recordToPrism (B8 wiring)', () => {
    it('invokes the sink before disposing the fork', () => {
      const graph = buildTestGraph()
      const sink = vi.fn()

      engine.explore(
        graph,
        { anchors: ['a'], hops: 1 },
        [{ type: 'affect', valence: 0.4, arousal: 0.5 }],
        ['activated_nodes'],
        {
          recordToPrism: sink,
          baseColor: 'calm',
          baseAffect: { valence: 0.3, arousal: 0.1 },
        },
      )

      expect(sink).toHaveBeenCalledOnce()
      const contribution = sink.mock.calls[0][0]
      expect(contribution.color).toBe('engaged')
      expect(contribution.contributedNodes.length).toBeGreaterThan(0)
    })

    it('does not invoke the sink when recordToPrism is omitted', () => {
      const graph = buildTestGraph()
      const result = engine.explore(graph, { anchors: ['a'] }, [], ['activated_nodes'])
      expect(result.observations.length).toBe(1)
    })

    it('does not invoke the sink when no resolvable color is available', () => {
      const graph = buildTestGraph()
      const sink = vi.fn()

      engine.explore(
        graph,
        { anchors: ['a'] },
        [{ type: 'concept_prime', concepts: ['alpha'], salience: 0.5 }],
        ['activated_nodes'],
        { recordToPrism: sink, baseColor: null, baseAffect: null },
      )

      expect(sink).not.toHaveBeenCalled()
    })
  })

  describe('B7.4 — projection summary + cross-feature helpers', () => {
    it('getProjectionSummary returns empty array when no forks are active', () => {
      expect(engine.getProjectionSummary()).toEqual([])
    })

    it('getProjectionSummary lists active forks with age + nodeCount', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 1 })
      const summary = engine.getProjectionSummary()
      expect(summary).toHaveLength(1)
      expect(summary[0].forkId).toBe(handle.id)
      expect(summary[0].nodeCount).toBe(2)
      expect(summary[0].hasAffectOverride).toBe(false)
      expect(summary[0].ageSec).toBeGreaterThanOrEqual(0)
      expect(summary[0].expiresInSec).toBeGreaterThan(0)
    })

    it('getProjectionSummary excludes disposed forks', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 1 })
      engine.disposeFork(handle.id)
      expect(engine.getProjectionSummary()).toEqual([])
    })

    it('getProjectionSummary flags hasAffectOverride after applyPerturbation', () => {
      const graph = buildTestGraph()
      const handle = engine.fork(graph, { anchors: ['a'], hops: 1 })
      engine.applyPerturbation(handle.id, { type: 'affect', valence: 0.5, arousal: 0.5 })
      const summary = engine.getProjectionSummary()
      expect(summary[0].hasAffectOverride).toBe(true)
    })

    it('exploreAffectPerturbation runs explore() with an affect perturbation and disposes', () => {
      const graph = buildTestGraph()
      const result = engine.exploreAffectPerturbation(
        graph,
        { anchors: ['a'], hops: 1 },
        { valence: -0.4, arousal: 0.7 },
      )
      expect(result.perturbationsApplied).toEqual([
        { type: 'affect', valence: -0.4, arousal: 0.7 },
      ])
      expect(result.observations.length).toBeGreaterThan(0)
      // Default behavior is to dispose; subsequent getProjectionSummary should be empty.
      expect(engine.getProjectionSummary()).toEqual([])
    })

    it('exploreAffectPerturbation honors retainAfter so callers can inspect', () => {
      const graph = buildTestGraph()
      engine.exploreAffectPerturbation(
        graph,
        { anchors: ['a'], hops: 1 },
        { valence: -0.4, arousal: 0.7 },
        ['activated_nodes'],
        { retainAfter: true },
      )
      // Fork persists for inspection when retainAfter=true
      expect(engine.getProjectionSummary()).toHaveLength(1)
    })
  })
})
