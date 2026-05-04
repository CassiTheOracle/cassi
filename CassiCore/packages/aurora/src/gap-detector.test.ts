/**
 * GapDetector tests — topology-aware gap detection.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import os from 'node:os'
import path from 'node:path'
import fs from 'node:fs'

import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import type { CognitiveNode, CognitiveEdge, UnifiedGraph } from './types.js'
import { GapDetector } from './gap-detector.js'



function makeLogger(): ILogger {
  return {
    info: () => {},
    debug: () => {},
    warn: () => {},
    error: () => {},
    child: () => makeLogger(),
  } as unknown as ILogger
}

function makeNode(id: string, label: string, source: CognitiveNode['source'] = 'both', resonance = 0.5): CognitiveNode {
  return {
    id,
    label,
    source,
    resonance,
    centrality: 0.5,
    modelConfidence: 0.5,
    memoryPotentiation: 0.5,
  }
}

function makeEdge(sourceId: string, targetId: string, weight = 0.5, edgeType = 'related_to'): CognitiveEdge {
  return { sourceId, targetId, weight, edgeType, origin: 'memory' }
}

function makeGraph(nodes: CognitiveNode[], edges: CognitiveEdge[]): UnifiedGraph {
  const nodeMap = new Map<string, CognitiveNode>()
  const edgeMap = new Map<string, CognitiveEdge[]>()

  for (const node of nodes) {
    nodeMap.set(node.id, node)
  }

  for (const edge of edges) {
    const existing = edgeMap.get(edge.sourceId) ?? []
    existing.push(edge)
    edgeMap.set(edge.sourceId, existing)
  }

  return { nodes: nodeMap, edges: edgeMap }
}

let tmpDir: string

beforeEach(() => {
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'gap-detector-test-'))
})

afterEach(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true })
})



describe('GapDetector', () => {
  it('initializes the database and schema', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger())

    const gap = detector.getGap('nonexistent')
    expect(gap).toBeUndefined()

    detector.close()
  })

  it('detects underconnected nodes', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger())

    // Well-connected core
    const a = makeNode('a', 'Alpha')
    const b = makeNode('b', 'Beta')
    const c = makeNode('c', 'Gamma')
    const d = makeNode('d', 'Delta') // Will be underconnected

    const graph = makeGraph(
      [a, b, c, d],
      [
        makeEdge('a', 'b'), makeEdge('b', 'a'),
        makeEdge('a', 'c'), makeEdge('c', 'a'),
        makeEdge('b', 'c'), makeEdge('c', 'b'),
        // d has only one edge
        makeEdge('a', 'd'),
      ],
    )

    const gaps = detector.detectGaps(graph)
    const underconnected = gaps.filter(g => g.category === 'underconnected')

    // Node d should be flagged as underconnected
    expect(underconnected.length).toBeGreaterThanOrEqual(1)
    const dGap = underconnected.find(g => g.scope.nodeIds.includes('d'))
    expect(dGap).toBeDefined()
    expect(dGap!.signals[0].type).toBe('low_edge_density')

    detector.close()
  })

  it('detects fragmented components', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger())

    // Two disconnected clusters of 3 nodes each
    const a1 = makeNode('a1', 'A1'), a2 = makeNode('a2', 'A2'), a3 = makeNode('a3', 'A3')
    const b1 = makeNode('b1', 'B1'), b2 = makeNode('b2', 'B2'), b3 = makeNode('b3', 'B3')

    const graph = makeGraph(
      [a1, a2, a3, b1, b2, b3],
      [
        makeEdge('a1', 'a2'), makeEdge('a2', 'a3'), makeEdge('a3', 'a1'),
        makeEdge('b1', 'b2'), makeEdge('b2', 'b3'), makeEdge('b3', 'b1'),
      ],
    )

    const gaps = detector.detectGaps(graph)
    const fragmented = gaps.filter(g => g.category === 'fragmented')

    // The smaller component should be flagged
    expect(fragmented.length).toBeGreaterThanOrEqual(1)

    detector.close()
  })

  it('detects missing focus for high-resonance low-degree nodes', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger())

    // Node with high resonance but few connections
    const hub = makeNode('hub', 'Hub', 'both', 0.9)
    const isolated = makeNode('iso', 'IsolatedImportant', 'both', 0.8)
    const filler = makeNode('f1', 'Filler', 'both', 0.3)
    const filler2 = makeNode('f2', 'Filler2', 'both', 0.3)
    const filler3 = makeNode('f3', 'Filler3', 'both', 0.3)

    const graph = makeGraph(
      [hub, isolated, filler, filler2, filler3],
      [
        makeEdge('hub', 'f1'), makeEdge('hub', 'f2'), makeEdge('hub', 'f3'),
        makeEdge('f1', 'f2'), makeEdge('f2', 'f3'), makeEdge('f3', 'f1'),
        // isolated has 0 edges despite high resonance
      ],
    )

    const gaps = detector.detectGaps(graph)
    const missingFocus = gaps.filter(g => g.category === 'missing_focus')

    expect(missingFocus.length).toBeGreaterThanOrEqual(1)
    const isoGap = missingFocus.find(g => g.scope.nodeIds.includes('iso'))
    expect(isoGap).toBeDefined()
    expect(isoGap!.signals[0].type).toBe('missing_portal')

    detector.close()
  })

  it('detects isolated nuclei', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger(), { minNucleusSize: 2 })

    // Main cluster + isolated cluster of 3 nodes with no bridges
    const m1 = makeNode('m1', 'M1'), m2 = makeNode('m2', 'M2'), m3 = makeNode('m3', 'M3')
    const i1 = makeNode('i1', 'I1'), i2 = makeNode('i2', 'I2'), i3 = makeNode('i3', 'I3')

    const graph = makeGraph(
      [m1, m2, m3, i1, i2, i3],
      [
        makeEdge('m1', 'm2'), makeEdge('m2', 'm3'), makeEdge('m3', 'm1'),
        makeEdge('i1', 'i2'), makeEdge('i2', 'i3'), makeEdge('i3', 'i1'),
        // No bridges between the two clusters
      ],
    )

    const gaps = detector.detectGaps(graph)
    const nuclei = gaps.filter(g => g.category === 'isolated_nucleus')

    // The isolated cluster should be flagged
    expect(nuclei.length).toBeGreaterThanOrEqual(1)
    const nucleus = nuclei.find(g =>
      g.scope.nodeIds.includes('i1') || g.scope.nodeIds.includes('i2'),
    )
    expect(nucleus).toBeDefined()
    expect(nucleus!.scope.nodeIds.length).toBeGreaterThanOrEqual(2)

    detector.close()
  })

  it('persists gaps and increments detection count on re-detection', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger(), { minNucleusSize: 2 })

    // Two disconnected clusters of 3 nodes each — will produce isolated nucleus + fragmented gaps
    const a1 = makeNode('a1', 'A1'), a2 = makeNode('a2', 'A2'), a3 = makeNode('a3', 'A3')
    const b1 = makeNode('b1', 'B1'), b2 = makeNode('b2', 'B2'), b3 = makeNode('b3', 'B3')
    const graph = makeGraph(
      [a1, a2, a3, b1, b2, b3],
      [
        makeEdge('a1', 'a2'), makeEdge('a2', 'a3'), makeEdge('a3', 'a1'),
        makeEdge('b1', 'b2'), makeEdge('b2', 'b3'), makeEdge('b3', 'b1'),
      ],
    )

    // First detection
    const gaps1 = detector.detectGaps(graph)
    expect(gaps1.length).toBeGreaterThanOrEqual(1)
    const gapId = gaps1[0].id

    // Second detection — same graph
    const gaps2 = detector.detectGaps(graph)
    const sameGap = gaps2.find(g => g.id === gapId)
    expect(sameGap).toBeDefined()
    expect(sameGap!.detectionCount).toBeGreaterThanOrEqual(2)

    // Verify persistence
    const fromDb = detector.getGap(gapId)
    expect(fromDb).toBeDefined()
    expect(fromDb!.detectionCount).toBeGreaterThanOrEqual(2)

    detector.close()
  })

  it('preserves non-pending status on re-detection', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger(), { minNucleusSize: 2 })

    // Two disconnected clusters of 3 nodes each
    const a1 = makeNode('a1', 'A1'), a2 = makeNode('a2', 'A2'), a3 = makeNode('a3', 'A3')
    const b1 = makeNode('b1', 'B1'), b2 = makeNode('b2', 'B2'), b3 = makeNode('b3', 'B3')
    const graph = makeGraph(
      [a1, a2, a3, b1, b2, b3],
      [
        makeEdge('a1', 'a2'), makeEdge('a2', 'a3'), makeEdge('a3', 'a1'),
        makeEdge('b1', 'b2'), makeEdge('b2', 'b3'), makeEdge('b3', 'b1'),
      ],
    )

    const gaps1 = detector.detectGaps(graph)
    const gapId = gaps1[0].id

    // Manually set status to in_meditation
    detector.updateStatus(gapId, 'in_meditation')

    // Re-detect — status should stay in_meditation
    const gaps2 = detector.detectGaps(graph)
    const sameGap = gaps2.find(g => g.id === gapId)
    expect(sameGap!.status).toBe('in_meditation')

    detector.close()
  })

  it('getPendingGaps returns only pending/scheduled gaps', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger(), { minNucleusSize: 2 })

    // Two disconnected clusters of 3 nodes each
    const a1 = makeNode('a1', 'A1'), a2 = makeNode('a2', 'A2'), a3 = makeNode('a3', 'A3')
    const b1 = makeNode('b1', 'B1'), b2 = makeNode('b2', 'B2'), b3 = makeNode('b3', 'B3')
    const graph = makeGraph(
      [a1, a2, a3, b1, b2, b3],
      [
        makeEdge('a1', 'a2'), makeEdge('a2', 'a3'), makeEdge('a3', 'a1'),
        makeEdge('b1', 'b2'), makeEdge('b2', 'b3'), makeEdge('b3', 'b1'),
      ],
    )

    const gaps = detector.detectGaps(graph)
    expect(gaps.length).toBeGreaterThanOrEqual(1)

    const pendingBefore = detector.getPendingGaps()
    expect(pendingBefore.length).toBeGreaterThanOrEqual(1)

    // Resolve the first gap
    detector.updateStatus(pendingBefore[0].id, 'resolved')

    const pendingAfter = detector.getPendingGaps()
    expect(pendingAfter.length).toBe(pendingBefore.length - 1)

    detector.close()
  })

  it('returns empty for well-connected graph', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger())

    // Fully connected graph — no gaps expected
    const nodes = [
      makeNode('a', 'A'), makeNode('b', 'B'), makeNode('c', 'C'), makeNode('d', 'D'),
    ]
    const edges: CognitiveEdge[] = [
      makeEdge('a', 'b'), makeEdge('a', 'c'), makeEdge('a', 'd'),
      makeEdge('b', 'a'), makeEdge('b', 'c'), makeEdge('b', 'd'),
      makeEdge('c', 'a'), makeEdge('c', 'b'), makeEdge('c', 'd'),
      makeEdge('d', 'a'), makeEdge('d', 'b'), makeEdge('d', 'c'),
    ]

    const graph = makeGraph(nodes, edges)
    const gaps = detector.detectGaps(graph)

    expect(gaps.length).toBe(0)

    detector.close()
  })

  it('generates stable IDs for same category and nodes', () => {
    const dbPath = path.join(tmpDir, 'test-gaps.db')
    const detector = new GapDetector(dbPath, makeLogger(), { minNucleusSize: 2 })

    // Two disconnected clusters of 3 nodes each
    const a1 = makeNode('a1', 'A1'), a2 = makeNode('a2', 'A2'), a3 = makeNode('a3', 'A3')
    const b1 = makeNode('b1', 'B1'), b2 = makeNode('b2', 'B2'), b3 = makeNode('b3', 'B3')
    const graph = makeGraph(
      [a1, a2, a3, b1, b2, b3],
      [
        makeEdge('a1', 'a2'), makeEdge('a2', 'a3'), makeEdge('a3', 'a1'),
        makeEdge('b1', 'b2'), makeEdge('b2', 'b3'), makeEdge('b3', 'b1'),
      ],
    )

    const gaps1 = detector.detectGaps(graph)
    const gaps2 = detector.detectGaps(graph)

    // Same gap should produce same ID
    expect(gaps2.some(g => gaps1.some(g1 => g1.id === g.id))).toBe(true)

    detector.close()
  })
})
