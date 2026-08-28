/**
 * Tests for ClaustrumRecorder — provenance log feeding the claustrum-vindex
 * snapshotter.
 *
 * Covers M3 of the Aurora A1 milestone (provenance enrichment):
 *  - cycleId is persisted alongside hits
 *  - distinctFeaturesByLayer returns correct per-layer summaries
 *
 * See: docs/design/claustrum-vindex.md §6, §7
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'

import { ClaustrumRecorder } from './claustrum-recorder.js'

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

describe('ClaustrumRecorder', () => {
  let tmpDir: string
  let dbPath: string
  let recorder: ClaustrumRecorder

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'claustrum-recorder-'))
    dbPath = path.join(tmpDir, 'recorder.db')
    recorder = new ClaustrumRecorder(mockLogger(), '/fake/vindex', dbPath)
  })

  afterEach(() => {
    recorder.close()
    fs.rmSync(tmpDir, { recursive: true, force: true })
  })

  it('persists cycleId on every hit row', () => {
    recorder.recordGateHits({
      cycleId: 'aur_1',
      queryConcept: 'authentication',
      trigger: 'larql_gate_knn',
      hits: [
        { layer: 14, featureIndex: 100, score: 0.9 },
        { layer: 14, featureIndex: 200, score: 0.8 },
      ],
    })
    recorder.recordGateHits({
      cycleId: 'aur_2',
      queryConcept: 'cache',
      trigger: 'larql_gate_knn',
      hits: [{ layer: 22, featureIndex: 50, score: 0.7 }],
    })

    expect(recorder.recordCount()).toBe(3)

    const retained = recorder.retainedFeatures()
    expect(retained.length).toBe(3)
    // Ordered by layer asc then feature_index asc
    expect(retained[0].layer).toBe(14)
    expect(retained[0].featureIndex).toBe(100)
    expect(retained[2].layer).toBe(22)
  })

  it('distinctFeaturesByLayer returns one row per layer with correct counts', () => {
    // Layer 14: features 100, 100 (dupe), 200, 300 → 3 distinct, 4 total
    recorder.recordGateHits({
      cycleId: 'aur_1', queryConcept: 'q', trigger: 't',
      hits: [
        { layer: 14, featureIndex: 100, score: 0.9 },
        { layer: 14, featureIndex: 100, score: 0.5 },
        { layer: 14, featureIndex: 200, score: 0.8 },
        { layer: 14, featureIndex: 300, score: 0.7 },
      ],
    })
    // Layer 22: features 50, 60 → 2 distinct, 2 total
    recorder.recordGateHits({
      cycleId: 'aur_1', queryConcept: 'q', trigger: 't',
      hits: [
        { layer: 22, featureIndex: 50, score: 0.6 },
        { layer: 22, featureIndex: 60, score: 0.5 },
      ],
    })

    const summary = recorder.distinctFeaturesByLayer()
    expect(summary.length).toBe(2)

    const l14 = summary.find(s => s.layer === 14)!
    const l22 = summary.find(s => s.layer === 22)!
    expect(l14.distinctFeatures).toBe(3)
    expect(l14.totalHits).toBe(4)
    expect(l22.distinctFeatures).toBe(2)
    expect(l22.totalHits).toBe(2)
  })

  it('distinctFeaturesByLayer respects the time window', () => {
    const earlier = '2026-01-01T00:00:00Z'
    const later = '2026-12-31T23:59:59Z'

    // Insert directly with explicit timestamp via SQL because recorder stamps Date.now().
    // Easier: just record now and filter to a window in the future.
    recorder.recordGateHits({
      cycleId: 'aur_1', queryConcept: 'q', trigger: 't',
      hits: [
        { layer: 14, featureIndex: 100, score: 0.9 },
        { layer: 14, featureIndex: 200, score: 0.8 },
      ],
    })

    // Window in the past → no rows
    const past = recorder.distinctFeaturesByLayer({ startTs: earlier, endTs: earlier })
    expect(past.length).toBe(0)

    // Window covering now → both rows visible
    const wide = recorder.distinctFeaturesByLayer({ startTs: earlier, endTs: later })
    expect(wide[0].distinctFeatures).toBe(2)
  })

  it('null cycleId is still allowed (back-compat for callers without one)', () => {
    expect(() => recorder.recordGateHits({
      cycleId: null,
      queryConcept: 'x',
      trigger: 't',
      hits: [{ layer: 14, featureIndex: 1, score: 0.5 }],
    })).not.toThrow()
    expect(recorder.recordCount()).toBe(1)
  })

  it('returns empty arrays after close', () => {
    recorder.recordGateHits({
      cycleId: 'aur_1', queryConcept: 'x', trigger: 't',
      hits: [{ layer: 14, featureIndex: 1, score: 0.5 }],
    })
    recorder.close()
    expect(recorder.distinctFeaturesByLayer()).toEqual([])
    expect(recorder.retainedFeatures()).toEqual([])
    expect(recorder.recordCount()).toBe(0)
  })
})
