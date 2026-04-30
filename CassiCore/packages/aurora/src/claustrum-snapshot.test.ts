/**
 * Tests for claustrum-snapshot.ts — graph serialization, manifest building,
 * provenance export, and full round-trip (M5 + M6).
 *
 * Covers:
 *  - serializeGraph / parseSerializedGraph round-trip
 *  - buildManifest structure validation
 *  - exportProvenance output shape
 *  - writeClaustrumSnapshot / readClaustrumSnapshot round-trip (M6)
 *
 * See: docs/design/claustrum-vindex.md §4.2–§4.4, §7
 *      docs/design/aurora-extensions-roadmap.md §A1 (M5, M6)
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'

import type { UnifiedGraph, CognitiveNode, CognitiveEdge } from './types.js'
import { ClaustrumRecorder } from './claustrum-recorder.js'
import {
  serializeGraph,
  parseSerializedGraph,
  buildManifest,
  exportProvenance,
  writeClaustrumSnapshot,
  readClaustrumSnapshot,
  type SerializedClaustrumGraph,
  type ClaustrumManifest,
  type ProvenanceRecord,
} from './claustrum-snapshot.js'
import { exportRetained } from '../../../scripts/export-claustrum-retained.js'

// section

function mockLogger(): any {
  const make = () => ({
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => make(),
  })
  return make()
}

function makeTestGraph(): UnifiedGraph {
  const nodes = new Map<string, CognitiveNode>()
  nodes.set('node_a', {
    id: 'node_a',
    label: 'spreading activation',
    source: 'both',
    resonance: 0.85,
    centrality: 0.72,
    activated: true,
    modelConfidence: 0.9,
    modelLayers: [14, 22],
  })
  nodes.set('node_b', {
    id: 'node_b',
    label: 'memory consolidation',
    source: 'memory',
    resonance: 0.6,
    centrality: 0.4,
    activated: false,
  })
  nodes.set('node_c', {
    id: 'node_c',
    label: 'observer insight',
    source: 'observer',
    resonance: 0.5,
    centrality: 0.3,
    activated: true,
  })

  const edge: CognitiveEdge = {
    sourceId: 'node_a',
    targetId: 'node_b',
    origin: 'model',
    edgeType: 'co_activates_with',
    weight: 0.83,
  }
  const edges = new Map<string, CognitiveEdge[]>()
  edges.set('node_a', [edge])
  const reverseEdges = new Map<string, CognitiveEdge[]>()
  reverseEdges.set('node_b', [edge])

  return {
    nodes,
    edges,
    reverseEdges,
    sourceBreakdown: { model: 1, memory: 1, observer: 1, both: 1, knowledge: 0 },
    edgeCount: 1,
    builtAt: Date.now(),
  }
}

// section

describe('serializeGraph', () => {
  it('converts UnifiedGraph Maps to JSON-safe arrays', () => {
    const graph = makeTestGraph()
    const result = serializeGraph(graph)

    expect(result.format_version).toBe(1)
    expect(result.nodes).toHaveLength(3)
    expect(result.edges).toHaveLength(1)
    expect(result.total_edges).toBe(1)
    expect(result.built_at).toBe(new Date(graph.builtAt).toISOString())
  })

  it('maps node sources to wire-format source tags', () => {
    const graph = makeTestGraph()
    const result = serializeGraph(graph)

    const nodeA = result.nodes.find(n => n.id === 'node_a')!
    expect(nodeA.sources).toContain('model')
    expect(nodeA.sources).toContain('mnemic')

    const nodeB = result.nodes.find(n => n.id === 'node_b')!
    expect(nodeB.sources).toContain('mnemic')

    const nodeC = result.nodes.find(n => n.id === 'node_c')!
    expect(nodeC.sources).toContain('observer')
  })

  it('preserves edge weight and maps origin to wire-format source', () => {
    const graph = makeTestGraph()
    const result = serializeGraph(graph)

    expect(result.edges[0].from).toBe('node_a')
    expect(result.edges[0].to).toBe('node_b')
    expect(result.edges[0].weight).toBe(0.83)
    expect(result.edges[0].source).toBe('model_relation')
  })

  it('includes model features when featureLocalIdMap is provided', () => {
    const graph = makeTestGraph()
    const localIdMap = new Map<string, number>()
    localIdMap.set('14:spreading activation', 42)

    const result = serializeGraph(graph, localIdMap)
    const nodeA = result.nodes.find(n => n.id === 'node_a')!
    expect(nodeA.model_features).toHaveLength(1)
    expect(nodeA.model_features[0]).toEqual({ layer: 14, claustrum_local_id: 42 })
  })

  it('is pure JSON (no Map, no undefined)', () => {
    const graph = makeTestGraph()
    const result = serializeGraph(graph)
    const json = JSON.stringify(result)
    expect(json).not.toContain('Map')
    expect(json).not.toContain('undefined')
  })
})

describe('parseSerializedGraph', () => {
  it('round-trips through JSON serialization', () => {
    const graph = makeTestGraph()
    const serialized = serializeGraph(graph)
    const json = JSON.stringify(serialized)
    const parsed = parseSerializedGraph(JSON.parse(json))

    expect(parsed.format_version).toBe(1)
    expect(parsed.nodes).toHaveLength(3)
    expect(parsed.edges).toHaveLength(1)
  })

  it('rejects wrong format_version', () => {
    expect(() => parseSerializedGraph({ format_version: 99 }))
      .toThrow('unsupported format_version')
  })

  it('rejects missing nodes or edges', () => {
    expect(() => parseSerializedGraph({ format_version: 1 }))
      .toThrow('missing nodes or edges')
  })
})


// section

describe('buildManifest', () => {
  it('captures source vindex metadata and snapshot window', () => {
    const graph = makeTestGraph()
    const manifest = buildManifest({
      sourcePath: '/path/to/gemma3-4b.vindex',
      sourceSha256: 'abc123',
      sourceFamily: 'gemma3',
      windowStart: '2026-04-27T00:00:00Z',
      windowEnd: '2026-05-15T18:00:00Z',
      auroraCyclesObserved: 14823,
      graph,
      retainedLayerCount: 5,
      retainedFeatureCount: 1873,
    })

    expect(manifest.format_version).toBe(1)
    expect(manifest.source.path).toBe('/path/to/gemma3-4b.vindex')
    expect(manifest.source.sha256).toBe('abc123')
    expect(manifest.source.family).toBe('gemma3')
    expect(manifest.snapshot.window_start).toBe('2026-04-27T00:00:00Z')
    expect(manifest.snapshot.window_end).toBe('2026-05-15T18:00:00Z')
    expect(manifest.snapshot.aurora_cycles_observed).toBe(14823)
    expect(manifest.graph_stats.node_count).toBe(3)
    expect(manifest.graph_stats.edge_count).toBe(1)
    expect(manifest.retained_stats.layer_count).toBe(5)
    expect(manifest.retained_stats.total_features).toBe(1873)
  })

  it('defaults nullable fields to null', () => {
    const graph = makeTestGraph()
    const manifest = buildManifest({
      sourcePath: '/path/to/vindex',
      graph,
      retainedLayerCount: 0,
      retainedFeatureCount: 0,
    })

    expect(manifest.source.sha256).toBeNull()
    expect(manifest.snapshot.window_start).toBeNull()
    expect(manifest.snapshot.window_end).toBeNull()
    expect(manifest.source.family).toBe('unknown')
  })
})


// section

describe('exportProvenance', () => {
  it('maps retained features to provenance records', () => {
    const retained = [
      { layer: 14, featureIndex: 100, hitCount: 3, maxScore: 0.9, firstSeen: '2026-04-28T10:00:00Z', lastSeen: '2026-04-29T10:00:00Z' },
      { layer: 22, featureIndex: 50, hitCount: 1, maxScore: 0.7, firstSeen: '2026-04-29T10:00:00Z', lastSeen: '2026-04-29T10:00:00Z' },
    ]

    const records = exportProvenance(retained, {})
    expect(records).toHaveLength(2)
    expect(records[0].layer).toBe(14)
    expect(records[0].source_global_id).toBe(100)
    expect(records[0].local_id).toBe(0) // sequential
    expect(records[1].layer).toBe(22)
    expect(records[1].local_id).toBe(1)
  })

  it('uses custom localIdFn when provided', () => {
    const retained = [
      { layer: 14, featureIndex: 100, hitCount: 1, maxScore: 0.9, firstSeen: '2026-04-28T10:00:00Z', lastSeen: '2026-04-29T10:00:00Z' },
    ]
    const customId = (_layer: number, globalId: number) => globalId * 10
    const records = exportProvenance(retained, {}, customId)
    expect(records[0].local_id).toBe(1000)
  })
})


// section

describe('writeClaustrumSnapshot / readClaustrumSnapshot round-trip', () => {
  let tmpDir: string
  let recorder: ClaustrumRecorder

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'claustrum-snapshot-'))
    recorder = new ClaustrumRecorder(mockLogger(), '/fake/vindex', path.join(tmpDir, 'recorder.db'))
  })

  afterEach(() => {
    recorder.close()
    fs.rmSync(tmpDir, { recursive: true, force: true })
  })

  it('writes and reads a complete snapshot', () => {
    const graph = makeTestGraph()

    // Record some gate hits so we have retained features
    recorder.recordGateHits({
      cycleId: 'aur_1',
      queryConcept: 'activation',
      trigger: 'larql_gate_knn',
      hits: [
        { layer: 14, featureIndex: 100, score: 0.9 },
        { layer: 14, featureIndex: 200, score: 0.8 },
        { layer: 22, featureIndex: 50, score: 0.7 },
      ],
    })
    recorder.recordGateHits({
      cycleId: 'aur_2',
      queryConcept: 'memory',
      trigger: 'larql_gate_knn',
      hits: [
        { layer: 14, featureIndex: 100, score: 0.95 },
        { layer: 22, featureIndex: 150, score: 0.6 },
      ],
    })

    const retained = recorder.retainedFeatures({})
    const snapshotDir = path.join(tmpDir, 'snapshot.vindex')

    const result = writeClaustrumSnapshot({
      outputDir: snapshotDir,
      graph,
      retained,
      window: {},
      sourcePath: '/fake/vindex',
      sourceSha256: 'deadbeef',
      sourceFamily: 'gemma3',
      auroraCyclesObserved: 42,
    })

    // Verify the write result
    expect(result.nodeCount).toBe(3)
    expect(result.edgeCount).toBe(1)
    expect(result.provenanceRecords).toBe(4) // 4 distinct (layer, feature) pairs
    expect(fs.existsSync(result.graphPath)).toBe(true)
    expect(fs.existsSync(result.manifestPath)).toBe(true)
    expect(fs.existsSync(result.provenancePath)).toBe(true)

    // Read back
    const read = readClaustrumSnapshot(snapshotDir)
    expect(read).not.toBeNull()

    const { graph: readGraph, manifest, provenance } = read!

    // Graph round-trip
    expect(readGraph.format_version).toBe(1)
    expect(readGraph.nodes).toHaveLength(3)
    expect(readGraph.edges).toHaveLength(1)
    expect(readGraph.nodes[0].concept).toBe('spreading activation')

    // Manifest round-trip
    expect(manifest.format_version).toBe(1)
    expect(manifest.source.sha256).toBe('deadbeef')
    expect(manifest.source.family).toBe('gemma3')
    expect(manifest.snapshot.aurora_cycles_observed).toBe(42)
    expect(manifest.graph_stats.node_count).toBe(3)
    expect(manifest.retained_stats.total_features).toBe(4)

    // Provenance round-trip
    expect(provenance).toHaveLength(4)
    const layers = new Set(provenance.map(p => p.layer))
    expect(layers.has(14)).toBe(true)
    expect(layers.has(22)).toBe(true)
  })

  it('returns null when reading a missing snapshot', () => {
    expect(readClaustrumSnapshot('/nonexistent/path')).toBeNull()
  })

  it('returns null when reading a directory without graph/manifest', () => {
    const emptyDir = path.join(tmpDir, 'empty')
    fs.mkdirSync(emptyDir)
    expect(readClaustrumSnapshot(emptyDir)).toBeNull()
  })

  it('snapshot graph is valid JSON parseable by parseSerializedGraph', () => {
    const graph = makeTestGraph()
    const snapshotDir = path.join(tmpDir, 'json-test.vindex')

    writeClaustrumSnapshot({
      outputDir: snapshotDir,
      graph,
      retained: [],
      window: {},
      sourcePath: '/test',
    })

    const raw = JSON.parse(fs.readFileSync(path.join(snapshotDir, 'claustrum_graph.json'), 'utf-8'))
    const parsed = parseSerializedGraph(raw)
    expect(parsed.nodes).toHaveLength(3)
  })
})


// section

describe('Full pipeline: retained.bin + snapshot (M4a→M5→M6)', () => {
  let tmpDir: string
  let recorder: ClaustrumRecorder

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'claustrum-pipeline-'))
    recorder = new ClaustrumRecorder(mockLogger(), '/fake/vindex', path.join(tmpDir, 'recorder.db'))
  })

  afterEach(() => {
    recorder.close()
    fs.rmSync(tmpDir, { recursive: true, force: true })
  })

  it('exports retained.bin then writes snapshot with matching feature counts', () => {
    // Step 1: Record gate hits
    recorder.recordGateHits({
      cycleId: 'aur_1',
      queryConcept: 'test',
      trigger: 'larql_gate_knn',
      hits: [
        { layer: 0, featureIndex: 10, score: 0.9 },
        { layer: 0, featureIndex: 20, score: 0.8 },
        { layer: 5, featureIndex: 30, score: 0.7 },
      ],
    })

    // Step 2: Export retained.bin (M4a)
    const retainedBinPath = path.join(tmpDir, 'retained.bin')
    const exportResult = exportRetained({ recorder, outputPath: retainedBinPath })
    expect(exportResult.snapshot.totals.layers).toBe(2)
    expect(exportResult.snapshot.totals.features).toBe(3)

    // Step 3: Write snapshot adjuncts (M5)
    const graph = makeTestGraph()
    const retained = recorder.retainedFeatures({})
    const snapshotDir = path.join(tmpDir, 'full-snapshot.vindex')

    const snapResult = writeClaustrumSnapshot({
      outputDir: snapshotDir,
      graph,
      retained,
      window: {},
      sourcePath: '/fake/vindex',
      auroraCyclesObserved: 1,
    })

    // Step 4: Verify pipeline coherence (M6)
    expect(snapResult.provenanceRecords).toBe(exportResult.snapshot.totals.features)
    expect(snapResult.nodeCount).toBe(3)

    const read = readClaustrumSnapshot(snapshotDir)!
    expect(read.manifest.retained_stats.total_features).toBe(exportResult.snapshot.totals.features)
    expect(read.manifest.retained_stats.layer_count).toBe(exportResult.snapshot.totals.layers)

    // Verify the retained.bin and provenance agree on feature counts
    expect(read.provenance.length).toBe(3)
  })
})
