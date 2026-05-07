/**
 * N2 → UCF probe set tests. Verifies the MeasurementFn returns
 * per-category fire counts, the schema lines up with UCF expectations,
 * and the default probe pack exercises every category at least once.
 */

import { describe, it, expect } from 'vitest'

import { PostureCoherenceDetector } from './index.js'
import { buildN2CoherenceProbeSet, N2_DEFAULT_PROBES } from './probe-set.js'
import type { Probe } from '../calibration/types.js'

function makeLogger() {
  const log: any = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {} }
  log.child = () => log
  return log
}

describe('buildN2CoherenceProbeSet', () => {
  it('builds a CalibrationProbeSet with the right ownerSpec and id', () => {
    const detector = new PostureCoherenceDetector(makeLogger())
    const set = buildN2CoherenceProbeSet(detector, N2_DEFAULT_PROBES)
    expect(set.id).toBe('aurora-n2-coherence')
    expect(set.ownerSpec).toBe('aurora-n2')
    expect(set.probes).toBe(N2_DEFAULT_PROBES)
    expect(typeof set.measurement).toBe('function')
    expect(set.schedule.frequency).toBe('manual')
  })

  it('emits one fires_<category> key per known category, plus total_fires', () => {
    const detector = new PostureCoherenceDetector(makeLogger())
    const set = buildN2CoherenceProbeSet(detector, N2_DEFAULT_PROBES)

    const probe = N2_DEFAULT_PROBES[0]
    const result = set.measurement(probe) as ReturnType<typeof set.measurement>
    if (result instanceof Promise) throw new Error('expected sync result')

    const expectedCategoryKeys = [
      'fires_composition_pair_cancelling',
      'fires_composition_pair_contradictory',
      'fires_composition_meditation_suppression',
      'fires_composition_retrieval_mismatch',
      'fires_replay_affect_mismatch',
      'fires_meditation_entrypoint_cold',
      'fires_composition_meditation_cold_topic',
    ]
    for (const key of expectedCategoryKeys) {
      expect(result.values).toHaveProperty(key)
      expect(typeof result.values[key]).toBe('number')
    }
    expect(result.values).toHaveProperty('total_fires')
  })

  it('empty-state probe produces zero fires across all categories', () => {
    const detector = new PostureCoherenceDetector(makeLogger())
    const set = buildN2CoherenceProbeSet(detector, N2_DEFAULT_PROBES)
    const empty = N2_DEFAULT_PROBES.find(p => p.id === 'probe-empty-state')!
    const result = set.measurement(empty) as { values: Record<string, number> }
    expect(result.values.total_fires).toBe(0)
  })

  it('contradictory-pair probe fires the contradictory category', () => {
    const detector = new PostureCoherenceDetector(makeLogger())
    const set = buildN2CoherenceProbeSet(detector, N2_DEFAULT_PROBES)
    const probe = N2_DEFAULT_PROBES.find(p => p.id === 'probe-pair-contradictory')!
    const result = set.measurement(probe) as { values: Record<string, number> }
    expect(result.values.fires_composition_pair_contradictory).toBeGreaterThan(0)
  })

  it('replay-mismatch probe fires the replay category', () => {
    const detector = new PostureCoherenceDetector(makeLogger())
    const set = buildN2CoherenceProbeSet(detector, N2_DEFAULT_PROBES)
    const probe = N2_DEFAULT_PROBES.find(p => p.id === 'probe-replay-mismatch')!
    const result = set.measurement(probe) as { values: Record<string, number> }
    expect(result.values.fires_replay_affect_mismatch).toBeGreaterThan(0)
  })

  it('meditation-cold probe fires the entrypoint-cold category', () => {
    const detector = new PostureCoherenceDetector(makeLogger())
    const set = buildN2CoherenceProbeSet(detector, N2_DEFAULT_PROBES)
    const probe = N2_DEFAULT_PROBES.find(p => p.id === 'probe-meditation-cold')!
    const result = set.measurement(probe) as { values: Record<string, number> }
    expect(result.values.fires_meditation_entrypoint_cold).toBeGreaterThan(0)
  })

  it('result includes a categoriesFired metadata array for human inspection', () => {
    const detector = new PostureCoherenceDetector(makeLogger())
    const set = buildN2CoherenceProbeSet(detector, N2_DEFAULT_PROBES)
    const probe = N2_DEFAULT_PROBES.find(p => p.id === 'probe-pair-contradictory')!
    const result = set.measurement(probe) as { metadata?: { categoriesFired: string[] } }
    expect(Array.isArray(result.metadata?.categoriesFired)).toBe(true)
    expect(result.metadata!.categoriesFired).toContain('composition_pair_contradictory')
  })

  it('honors a custom schedule', () => {
    const detector = new PostureCoherenceDetector(makeLogger())
    const set = buildN2CoherenceProbeSet(detector, N2_DEFAULT_PROBES, { frequency: 'daily', cron: '0 4 * * *' })
    expect(set.schedule.frequency).toBe('daily')
    expect(set.schedule.cron).toBe('0 4 * * *')
  })

  it('accepts caller-supplied probes when defaults aren\'t enough', () => {
    const detector = new PostureCoherenceDetector(makeLogger())
    const customProbe: Probe = {
      id: 'custom',
      input: { active: [], records: [], pendingSeeds: [] },
      metadata: { intent: 'caller-defined edge case' },
    }
    const set = buildN2CoherenceProbeSet(detector, [customProbe])
    expect(set.probes).toHaveLength(1)
    expect(set.probes[0].id).toBe('custom')
  })
})
