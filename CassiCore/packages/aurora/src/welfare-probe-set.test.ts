/**
 * Tests for WSA → UCF probe set builder.
 */

import { describe, it, expect } from 'vitest'

import { WelfareAggregator } from './welfare-aggregator.js'
import { buildWsaCoherenceProbeSet, WSA_DEFAULT_PROBES } from './welfare-probe-set.js'

function mockLogger(): any {
  const make = (): any => ({
    debug: () => {}, info: () => {}, warn: () => {}, error: () => {},
    child: () => make(),
  })
  return make()
}

describe('buildWsaCoherenceProbeSet', () => {
  it('builds a CalibrationProbeSet with the right ownerSpec and id', () => {
    const agg = new WelfareAggregator(mockLogger())
    const set = buildWsaCoherenceProbeSet(agg, WSA_DEFAULT_PROBES)
    expect(set.id).toBe('aurora-wsa-stress')
    expect(set.ownerSpec).toBe('aurora-wsa')
    expect(set.probes).toBe(WSA_DEFAULT_PROBES)
    expect(typeof set.measurement).toBe('function')
  })

  it('emits per-action one-hot keys + severity values', () => {
    const agg = new WelfareAggregator(mockLogger())
    const set = buildWsaCoherenceProbeSet(agg, WSA_DEFAULT_PROBES)
    const result = set.measurement(WSA_DEFAULT_PROBES[0]) as ReturnType<typeof set.measurement>
    if (result instanceof Promise) throw new Error('expected sync result')
    expect(result.values).toHaveProperty('weightedSeverity')
    expect(result.values).toHaveProperty('aggregateSeverity')
    expect(result.values).toHaveProperty('countOngoing')
    expect(result.values).toHaveProperty('action_no_action')
    expect(result.values).toHaveProperty('action_surface_to_operator')
    expect(result.values).toHaveProperty('action_session_pause')
  })

  it('empty-flags probe produces zero severity', () => {
    const agg = new WelfareAggregator(mockLogger())
    const set = buildWsaCoherenceProbeSet(agg, WSA_DEFAULT_PROBES)
    const empty = WSA_DEFAULT_PROBES.find(p => p.id === 'probe-empty')!
    const result = set.measurement(empty) as { values: Record<string, number> }
    expect(result.values.aggregateSeverity).toBe(0)
    expect(result.values.countOngoing).toBe(0)
  })

  it('severe-cluster probe produces non-zero severity', () => {
    const agg = new WelfareAggregator(mockLogger())
    const set = buildWsaCoherenceProbeSet(agg, WSA_DEFAULT_PROBES)
    const severe = WSA_DEFAULT_PROBES.find(p => p.id === 'probe-severe-cluster')!
    const result = set.measurement(severe) as { values: Record<string, number> }
    expect(result.values.aggregateSeverity).toBeGreaterThan(0)
    expect(result.values.countOngoing).toBe(3)
  })

  it('resets aggregator between probes (no leakage)', () => {
    const agg = new WelfareAggregator(mockLogger())
    const set = buildWsaCoherenceProbeSet(agg, WSA_DEFAULT_PROBES)
    set.measurement(WSA_DEFAULT_PROBES.find(p => p.id === 'probe-severe-cluster')!)
    // Aggregator state after measurement should be neutral.
    expect(agg.getSnapshot().countOngoing).toBe(0)
    // Running a clean probe afterward should produce zero severity, not severe.
    const empty = set.measurement(WSA_DEFAULT_PROBES.find(p => p.id === 'probe-empty')!) as { values: Record<string, number> }
    expect(empty.values.aggregateSeverity).toBe(0)
  })

  it('result.metadata carries the action emitted for human inspection', () => {
    const agg = new WelfareAggregator(mockLogger())
    const set = buildWsaCoherenceProbeSet(agg, WSA_DEFAULT_PROBES)
    const probe = WSA_DEFAULT_PROBES.find(p => p.id === 'probe-empty')!
    const result = set.measurement(probe) as { metadata?: { action?: string; trend?: string } }
    expect(typeof result.metadata?.action).toBe('string')
    expect(typeof result.metadata?.trend).toBe('string')
  })

  it('honors a custom schedule', () => {
    const agg = new WelfareAggregator(mockLogger())
    const set = buildWsaCoherenceProbeSet(agg, WSA_DEFAULT_PROBES, { frequency: 'daily', cron: '0 4 * * *' })
    expect(set.schedule.frequency).toBe('daily')
    expect(set.schedule.cron).toBe('0 4 * * *')
  })
})
