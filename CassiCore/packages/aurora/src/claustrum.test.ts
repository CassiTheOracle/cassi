/**
 * Tests for ObserverInsightCollector and Claustrum's observer-source folding.
 *
 * Covers M2 of the Aurora A3 milestone (observer feedback loop closure).
 * See: docs/design/aurora-extensions-roadmap.md §A3
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'

import { Claustrum, ObserverInsightCollector } from './claustrum.js'
import { MnemicField } from '../mnemic-field/index.js'
import type { ObserverInsight } from '../constellation/observer-memory-bridge.js'

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

describe('ObserverInsightCollector', () => {
  it('buffers insights and dedups on id', () => {
    const c = new ObserverInsightCollector(8)
    const i1: ObserverInsight = { id: 'a', label: 'L', content: 'c1', layer: 'cluster' }
    const i2: ObserverInsight = { id: 'a', label: 'L', content: 'c2', layer: 'cluster' }
    const i3: ObserverInsight = { id: 'b', label: 'M', content: 'c3', layer: 'corpus' }
    c.ingest(i1)
    c.ingest(i2)
    c.ingest(i3)
    expect(c.size).toBe(2)
    expect(c.snapshot().map(i => i.id)).toEqual(['a', 'b'])
  })

  it('drops the oldest insight when the cap is hit', () => {
    const c = new ObserverInsightCollector(8) // floored to 8
    for (let i = 0; i < 12; i++) {
      c.ingest({ id: `i${i}`, label: 'L', content: 'x', layer: 'cluster' })
    }
    expect(c.size).toBe(8)
    expect(c.snapshot()[0].id).toBe('i4') // first 4 dropped
    expect(c.snapshot()[7].id).toBe('i11')
  })

  it('drain empties the buffer and returns the contents', () => {
    const c = new ObserverInsightCollector()
    c.ingest({ id: 'x', label: 'X', content: 'x', layer: 'cluster' })
    const drained = c.drain()
    expect(drained.length).toBe(1)
    expect(c.size).toBe(0)
  })

  it('ignores insights with no id (bridge always assigns one, but be defensive)', () => {
    const c = new ObserverInsightCollector()
    c.ingest({ label: 'no-id', content: 'oops', layer: 'cluster' })
    expect(c.size).toBe(0)
  })
})

describe('Claustrum.buildFocusedGraph + observer source', () => {
  let tmpDir: string
  let mnemic: MnemicField

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aurora-observer-'))
    mnemic = new MnemicField(mockLogger(), path.join(tmpDir, 'mnemic.db'))
  })

  afterEach(() => {
    mnemic.close()
    fs.rmSync(tmpDir, { recursive: true, force: true })
  })

  it('folds observer insights into the graph as source: observer nodes', () => {
    const claustrum = new Claustrum(mockLogger())
    const collector = new ObserverInsightCollector()

    collector.ingest({
      id: 'obs_1',
      label: 'cluster-stuck',
      content: 'Cluster has been blocked.',
      layer: 'cluster',
      confidence: 0.7,
    })

    const graph = claustrum.buildFocusedGraph({
      foci: ['anything'],
      cortex: (mnemic as any).cortex,
      observerCollector: collector,
    })

    expect(graph.sourceBreakdown.observer).toBe(1)
    const node = graph.nodes.get('observer:obs_1')
    expect(node).toBeDefined()
    expect(node!.source).toBe('observer')
    expect(node!.label).toBe('cluster-stuck')
    expect(node!.resonance).toBeCloseTo(0.7)
  })

  it('links observer nodes to existing memory nodes via concept overlap', () => {
    // Seed memory with an engram that mentions "authentication"
    mnemic.store({
      content: 'We refactored the authentication module last sprint.',
      nodeType: 'episode',
      tags: ['auth'],
      provenance: 'test',
    })

    const claustrum = new Claustrum(mockLogger())
    const collector = new ObserverInsightCollector()

    collector.ingest({
      id: 'obs_auth',
      label: 'auth-pattern',
      content: 'Repeated authentication issues across helices.',
      layer: 'cluster',
      concepts: ['authentication'],
      confidence: 0.8,
    })

    const graph = claustrum.buildFocusedGraph({
      foci: ['authentication'],
      cortex: (mnemic as any).cortex,
      observerCollector: collector,
    })

    const observerNode = graph.nodes.get('observer:obs_auth')
    expect(observerNode).toBeDefined()

    const outEdges = graph.edges.get('observer:obs_auth') ?? []
    expect(outEdges.length).toBeGreaterThan(0)
    expect(outEdges[0].origin).toBe('observer')
    expect(outEdges[0].edgeType).toBe('observed_about')
    expect(outEdges[0].weight).toBeCloseTo(0.8)
  })

  it('observer-source nodes free-stand when concepts are empty or unmatched', () => {
    const claustrum = new Claustrum(mockLogger())
    const collector = new ObserverInsightCollector()

    collector.ingest({
      id: 'obs_lonely',
      label: 'isolated-observation',
      content: 'Nothing else in the graph relates to this.',
      layer: 'corpus',
      concepts: ['xenobiology'], // nothing matches
    })

    const graph = claustrum.buildFocusedGraph({
      foci: ['unrelated'],
      cortex: (mnemic as any).cortex,
      observerCollector: collector,
    })

    const node = graph.nodes.get('observer:obs_lonely')
    expect(node).toBeDefined()
    expect((graph.edges.get('observer:obs_lonely') ?? []).length).toBe(0)
  })

  it('omits the observer step entirely when no collector is provided (back-compat)', () => {
    const claustrum = new Claustrum(mockLogger())
    const graph = claustrum.buildFocusedGraph({
      foci: ['anything'],
      cortex: (mnemic as any).cortex,
    })
    expect(graph.sourceBreakdown.observer).toBe(0)
  })

  it('collector-empty short-circuits the observer step', () => {
    const claustrum = new Claustrum(mockLogger())
    const empty = new ObserverInsightCollector()
    const graph = claustrum.buildFocusedGraph({
      foci: ['anything'],
      cortex: (mnemic as any).cortex,
      observerCollector: empty,
    })
    expect(graph.sourceBreakdown.observer).toBe(0)
  })
})
