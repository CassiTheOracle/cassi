/**
 * Tests for ObserverMemoryBridge — observer-layer fanout to Mnemic + Aurora's Claustrum.
 *
 * Covers M1 of the Aurora A3 milestone (observer feedback loop closure).
 * See: docs/design/aurora-extensions-roadmap.md §A3
 */

import { describe, it, expect } from 'vitest'
import {
  ObserverMemoryBridge,
  type ClaustrumInsightSink,
  type ObserverInsight,
  type ObserverMemorySource,
} from './observer-memory-bridge.js'

function mockLogger() {
  const make = () => ({
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => make(),
  }) as any
  return make()
}

function makeMemory() {
  const stored: any[] = []
  const source: ObserverMemorySource = {
    retrieve: () => [],
    store: (input) => { stored.push(input); return undefined },
  }
  return { source, stored }
}

function makeSink() {
  const ingested: ObserverInsight[] = []
  let throws = false
  const sink: ClaustrumInsightSink = {
    ingest: (insight) => {
      if (throws) throw new Error('boom')
      ingested.push(insight)
    },
  }
  return {
    sink,
    ingested,
    setThrows: (v: boolean) => { throws = v },
  }
}

describe('ObserverMemoryBridge.emitInsight', () => {
  it('fans out to both the Mnemic store and the Claustrum sink', () => {
    const mem = makeMemory()
    const sink = makeSink()
    const bridge = new ObserverMemoryBridge({
      source: mem.source,
      logger: mockLogger(),
      claustrumSink: sink.sink,
    })

    bridge.emitInsight({
      label: 'cluster-stuck',
      content: 'Cluster A has been blocked for three rounds.',
      layer: 'cluster',
      constellationId: 'con_42',
      concepts: ['blocked', 'cluster A'],
      confidence: 0.8,
    })

    expect(mem.stored.length).toBe(1)
    expect(mem.stored[0].content).toMatch(/blocked for three rounds/)
    expect(mem.stored[0].metadata.layer).toBe('cluster')
    expect(mem.stored[0].metadata.insightId).toMatch(/^obs_/)

    expect(sink.ingested.length).toBe(1)
    expect(sink.ingested[0].label).toBe('cluster-stuck')
    expect(sink.ingested[0].id).toMatch(/^obs_/)
    expect(sink.ingested[0].observedAt).toBeTypeOf('number')
    expect(sink.ingested[0].confidence).toBe(0.8)
  })

  it('dedups repeated insights within the window', () => {
    const mem = makeMemory()
    const sink = makeSink()
    const bridge = new ObserverMemoryBridge({
      source: mem.source,
      logger: mockLogger(),
      claustrumSink: sink.sink,
    })

    const insight: ObserverInsight = {
      label: 'corpus-coherence-drop',
      content: 'Coherence dipped to 0.31 over last 4 turns.',
      layer: 'corpus',
    }

    bridge.emitInsight(insight)
    bridge.emitInsight(insight)
    bridge.emitInsight(insight)

    expect(sink.ingested.length).toBe(1)
    expect(mem.stored.length).toBe(1)
    expect(bridge.dedupSize).toBe(1)
  })

  it('treats different content as distinct insights', () => {
    const mem = makeMemory()
    const sink = makeSink()
    const bridge = new ObserverMemoryBridge({
      source: mem.source,
      logger: mockLogger(),
      claustrumSink: sink.sink,
    })

    bridge.emitInsight({ label: 'a', content: 'one', layer: 'cluster' })
    bridge.emitInsight({ label: 'a', content: 'two', layer: 'cluster' })

    expect(sink.ingested.length).toBe(2)
    expect(sink.ingested[0].id).not.toBe(sink.ingested[1].id)
  })

  it('honours an explicit insight id for dedup', () => {
    const sink = makeSink()
    const bridge = new ObserverMemoryBridge({
      source: makeMemory().source,
      logger: mockLogger(),
      claustrumSink: sink.sink,
    })

    bridge.emitInsight({ id: 'fixed-1', label: 'x', content: 'first body', layer: 'cluster' })
    bridge.emitInsight({ id: 'fixed-1', label: 'x', content: 'different body', layer: 'cluster' })

    expect(sink.ingested.length).toBe(1)
    expect(sink.ingested[0].content).toBe('first body')
  })

  it('drops the oldest id when the dedup window is exceeded', () => {
    const sink = makeSink()
    const bridge = new ObserverMemoryBridge({
      source: makeMemory().source,
      logger: mockLogger(),
      claustrumSink: sink.sink,
      dedupWindow: 16, // floor enforced
    })

    for (let i = 0; i < 30; i++) {
      bridge.emitInsight({ label: `x${i}`, content: `body ${i}`, layer: 'cluster' })
    }
    expect(bridge.dedupSize).toBe(16)

    // The very first insight should have aged out, so re-emitting fires again.
    const before = sink.ingested.length
    bridge.emitInsight({ label: 'x0', content: 'body 0', layer: 'cluster' })
    expect(sink.ingested.length).toBe(before + 1)
  })

  it('still writes to Mnemic even if no Claustrum sink is registered', () => {
    const mem = makeMemory()
    const bridge = new ObserverMemoryBridge({
      source: mem.source,
      logger: mockLogger(),
    })

    bridge.emitInsight({ label: 'orphan', content: 'no sink', layer: 'cluster' })

    expect(mem.stored.length).toBe(1)
  })

  it('still writes to Mnemic even if the sink throws', () => {
    const mem = makeMemory()
    const sink = makeSink()
    sink.setThrows(true)
    const bridge = new ObserverMemoryBridge({
      source: mem.source,
      logger: mockLogger(),
      claustrumSink: sink.sink,
    })

    expect(() => bridge.emitInsight({
      label: 'flaky',
      content: 'sink will throw',
      layer: 'corpus',
    })).not.toThrow()
    expect(mem.stored.length).toBe(1)
  })

  it('setClaustrumSink wires the sink up after construction', () => {
    const sink = makeSink()
    const bridge = new ObserverMemoryBridge({
      source: makeMemory().source,
      logger: mockLogger(),
    })

    bridge.emitInsight({ label: 'pre', content: 'before sink', layer: 'cluster' })
    expect(sink.ingested.length).toBe(0)

    bridge.setClaustrumSink(sink.sink)
    bridge.emitInsight({ label: 'post', content: 'after sink', layer: 'cluster' })
    expect(sink.ingested.length).toBe(1)
    expect(sink.ingested[0].label).toBe('post')
  })

  it('ignores empty content', () => {
    const mem = makeMemory()
    const sink = makeSink()
    const bridge = new ObserverMemoryBridge({
      source: mem.source,
      logger: mockLogger(),
      claustrumSink: sink.sink,
    })

    bridge.emitInsight({ label: 'empty', content: '   ', layer: 'cluster' })

    expect(sink.ingested.length).toBe(0)
    expect(mem.stored.length).toBe(0)
  })
})
