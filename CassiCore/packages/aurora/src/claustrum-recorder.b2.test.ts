/**
 * B2.3 ClaustrumRecorder tests — affect-context columns + retrievalStats.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'

import { ClaustrumRecorder, type ClaustrumGateHit } from './claustrum-recorder.js'

function makeLogger() {
  const log: any = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {} }
  log.child = () => log
  return log
}

describe('ClaustrumRecorder — B2.3 affect context', () => {
  let dbPath: string
  let recorder: ClaustrumRecorder

  beforeEach(() => {
    dbPath = `/tmp/claustrum-b2-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
    recorder = new ClaustrumRecorder(makeLogger(), '/tmp/test-vindex', dbPath)
  })

  afterEach(() => {
    recorder.close()
    try { fs.unlinkSync(dbPath) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-wal`) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-shm`) } catch { /* ignore */ }
  })

  it('records hits without affect context (legacy path) and they show as biasMode=null', () => {
    recorder.recordGateHits({
      cycleId: 'c1', queryConcept: 'feedback', trigger: 'manual',
      hits: [
        { layer: 20, featureIndex: 1, score: 0.5 },
        { layer: 22, featureIndex: 2, score: 0.4 },
      ],
    })
    const stats = recorder.retrievalStats()
    expect(stats).toHaveLength(1)
    expect(stats[0].biasMode).toBeNull()
    expect(stats[0].hitCount).toBe(2)
    expect(stats[0].distinctFeatures).toBe(2)
    expect(stats[0].meanScore).toBeCloseTo(0.45, 4)
    expect(stats[0].meanAffectCompat).toBeNull()
  })

  it('records hits with affect context and reports mean compat per mode', () => {
    const hits: ClaustrumGateHit[] = [
      { layer: 20, featureIndex: 1, score: 0.6, rawScore: 0.5, affectCompat: 0.8, biasMode: 'consonant', biasStrength: 0.3 },
      { layer: 20, featureIndex: 2, score: 0.55, rawScore: 0.5, affectCompat: 0.6, biasMode: 'consonant', biasStrength: 0.3 },
      { layer: 22, featureIndex: 3, score: 0.4, rawScore: 0.5, affectCompat: -0.5, biasMode: 'complementary', biasStrength: 0.4 },
    ]
    recorder.recordGateHits({
      cycleId: 'c1', queryConcept: 'feedback', trigger: 'manual', hits,
    })
    const stats = recorder.retrievalStats()
    const consonant = stats.find(s => s.biasMode === 'consonant')!
    const complementary = stats.find(s => s.biasMode === 'complementary')!
    expect(consonant.hitCount).toBe(2)
    expect(consonant.meanAffectCompat).toBeCloseTo(0.7, 4)
    expect(complementary.hitCount).toBe(1)
    expect(complementary.meanAffectCompat).toBeCloseTo(-0.5, 4)
  })

  it('groups distinct features per mode correctly', () => {
    recorder.recordGateHits({
      cycleId: 'c1', queryConcept: 'feedback', trigger: 'manual',
      hits: [
        { layer: 20, featureIndex: 1, score: 0.5, biasMode: 'consonant', biasStrength: 0.3 },
        { layer: 20, featureIndex: 1, score: 0.6, biasMode: 'consonant', biasStrength: 0.3 },
        { layer: 22, featureIndex: 2, score: 0.4, biasMode: 'consonant', biasStrength: 0.3 },
      ],
    })
    const stats = recorder.retrievalStats()
    expect(stats[0].hitCount).toBe(3)
    expect(stats[0].distinctFeatures).toBe(2)
  })

  it('returns rows sorted by hitCount descending', () => {
    recorder.recordGateHits({
      cycleId: 'c1', queryConcept: 'feedback', trigger: 'manual',
      hits: [{ layer: 20, featureIndex: 1, score: 0.5, biasMode: 'complementary' }],
    })
    recorder.recordGateHits({
      cycleId: 'c1', queryConcept: 'feedback', trigger: 'manual',
      hits: [
        { layer: 20, featureIndex: 1, score: 0.5, biasMode: 'consonant' },
        { layer: 22, featureIndex: 2, score: 0.4, biasMode: 'consonant' },
      ],
    })
    const stats = recorder.retrievalStats()
    expect(stats[0].biasMode).toBe('consonant')   // 2 hits
    expect(stats[1].biasMode).toBe('complementary') // 1 hit
  })

  it('honors window filtering on retrievalStats', () => {
    const before = new Date('2026-05-01T00:00:00Z').toISOString()
    recorder.recordGateHits({
      cycleId: 'c1', queryConcept: 'feedback', trigger: 'manual',
      hits: [{ layer: 20, featureIndex: 1, score: 0.5, biasMode: 'consonant' }],
    })
    // Window in the past: should match nothing
    const stats = recorder.retrievalStats({ startTs: '2020-01-01', endTs: before })
    expect(stats).toHaveLength(0)
  })
})
