/**
 * A2 Aurora API tests — getVectorProjection() with the gate flag,
 * absence of state, and pass-through to StateProjector.projectVector.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'

import { Aurora } from '../index.js'
import type { AuroraConfig, MentalState, ReasoningMomentum } from '../types.js'
import { AURORA_DEFAULTS } from '../types.js'

function makeLogger() {
  const log: any = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {} }
  log.child = () => log
  return log
}

function makeCortex(): any {
  return { list: () => [], retrieve: async () => [], getAffectState: () => undefined }
}

function makeFakePersistence(dbPath: string): any {
  return {
    getDbPath: () => dbPath,
    beginSession: () => ({ sessionId: 'aur_test', inheritsFrom: null, createdAt: Date.now() }),
    hydrateClaustrum: () => ({ nodes: [], edges: [] }),
    hydrateReasoningLog: () => [],
    hydrateMomentum: () => null,
  }
}

function buildAurora(dbPath: string, overrides?: Partial<AuroraConfig>): Aurora {
  const cfg: Partial<AuroraConfig> = {
    ...AURORA_DEFAULTS,
    gapDetectionEnabled: false,
    meditationSeederEnabled: false,
    autoSchedulerEnabled: false,
    eventJournalEnabled: false,
    welfareAggregatorEnabled: false,
    refusalChannelEnabled: false,
    overlayLayerEnabled: false,
    cassiSpecChannelEnabled: false,
    modificationAuditEnabled: false,
    traceReplayEnabled: false,
    saturationDetectorEnabled: false,
    diversityFloorEnabled: false,
    counterfactualEngineEnabled: false,
    coherenceCheckEnabled: false,
    narrativeEnabled: false,
    compositionEnabled: false,
    postureCoherenceEnabled: false,
    calibrationEnabled: false,
    vectorProjectionEnabled: true,
    ...overrides,
  }
  return new Aurora(makeCortex(), null, null, null, makeLogger(), cfg, makeFakePersistence(dbPath))
}

const baselineMomentum: ReasoningMomentum = {
  trendingConcepts: [],
  shifts: [],
  topicShift: 0,
  novelty: 0,
  intensity: 0,
}

function activatedState(): MentalState {
  const nodes = new Map<string, any>([
    ['warmth', {
      id: 'warmth',
      label: 'warmth',
      source: 'model',
      resonance: 0.5,
      centrality: 0.2,
      activated: true,
      modelConfidence: 0.8,
      modelLayers: [14, 15, 16],
    }],
    ['rigor', {
      id: 'rigor',
      label: 'rigor',
      source: 'model',
      resonance: 0.4,
      centrality: 0.1,
      activated: true,
      modelConfidence: 0.6,
      modelLayers: [20, 21],
    }],
  ])
  return {
    graph: {
      nodes,
      edges: new Map(),
      reverseEdges: new Map(),
      sourceBreakdown: { model: 2, memory: 0, both: 0 },
      edgeCount: 0,
      builtAt: Date.now(),
    },
    resonanceHubs: [],
    gaps: [],
    recentDiscoveries: [],
    affect: null,
    foci: [],
    momentum: baselineMomentum,
    coherence: 0.5,
    integration: 0.5,
    computedAt: Date.now(),
    durationMs: 0,
  } as any
}

describe('Aurora.getVectorProjection (A2)', () => {
  let dbPath: string
  let aurora: Aurora

  beforeEach(() => {
    dbPath = `/tmp/aurora-a2-api-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
    aurora = buildAurora(dbPath)
  })

  afterEach(() => {
    try { fs.unlinkSync(dbPath) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-wal`) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-shm`) } catch { /* ignore */ }
  })

  it('returns null when vectorProjectionEnabled is false', () => {
    const dbPath2 = `/tmp/aurora-a2-disabled-${Date.now()}.db`
    const a = buildAurora(dbPath2, { vectorProjectionEnabled: false })
    expect(a.getVectorProjection(undefined, activatedState())).toBeNull()
    try { fs.unlinkSync(dbPath2) } catch { /* ignore */ }
  })

  it('returns null when no state is provided and Aurora has no current state', () => {
    expect(aurora.getVectorProjection()).toBeNull()
  })

  it('returns a projection when activated nodes exist in the state', () => {
    const projection = aurora.getVectorProjection(undefined, activatedState())
    expect(projection).not.toBeNull()
    expect(projection!.contributions.length).toBe(2)
    expect(projection!.contributions.map(c => c.nodeId).sort()).toEqual(['rigor', 'warmth'])
  })

  it('forwards layerSubset through StateProjector to the composer', () => {
    const projection = aurora.getVectorProjection({ layerSubset: [14, 15] }, activatedState())!
    expect(projection.contributions.map(c => c.nodeId)).toEqual(['warmth'])
  })

  it('forwards magnitudeScale through to weight', () => {
    const small = aurora.getVectorProjection({ magnitudeScale: 0.05 }, activatedState())!
    const large = aurora.getVectorProjection({ magnitudeScale: 0.5 }, activatedState())!
    expect(large.contributions[0].weight).toBeCloseTo(small.contributions[0].weight * 10)
  })
})
