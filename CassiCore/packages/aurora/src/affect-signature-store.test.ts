/**
 * Tests for AffectSignatureStore — schema v3 read/write of B2 signatures.
 *
 * Uses an in-memory SQLite for speed. The schema migration runs as part
 * of AuroraPersistence construction, so we open a real persistence
 * instance pointed at ':memory:' to get the v3 tables created.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import Database from 'better-sqlite3'

import { AffectSignatureStore } from './affect-signature-store.js'
import { AuroraPersistence } from './persistence.js'
import type { FeatureAffectSignature } from './larql-provider.js'

function mockLogger(): any {
  const make = (): any => ({
    debug: () => {}, info: () => {}, warn: () => {}, error: () => {},
    child: () => make(),
  })
  return make()
}

function sig(layer: number, idx: number, labels: FeatureAffectSignature['labels']): FeatureAffectSignature {
  let m2 = 0
  for (const v of Object.values(labels)) {
    if (typeof v === 'number') m2 += v * v
  }
  return { layer, featureIndex: idx, labels, magnitude: Math.sqrt(m2) }
}

describe('AffectSignatureStore', () => {
  let db: Database.Database
  let store: AffectSignatureStore

  beforeEach(() => {
    db = new Database(':memory:')
    // Run migrations by booting an AuroraPersistence over the same DB handle.
    // ('AuroraPersistence' accepts a Database instance directly — see ctor.)
    new AuroraPersistence(db, mockLogger())
    store = new AffectSignatureStore(db, mockLogger())
  })

  it('inserts and reads back a single signature', () => {
    store.upsertSignatures('vindex-X', 'probes-v1', [
      sig(20, 1234, { excited: 0.7, delighted: 0.4 }),
    ])
    const got = store.getSignature('vindex-X', 20, 1234)
    expect(got).not.toBeNull()
    expect(got!.labels.excited).toBeCloseTo(0.7, 6)
    expect(got!.labels.delighted).toBeCloseTo(0.4, 6)
    expect(got!.magnitude).toBeCloseTo(Math.sqrt(0.7 * 0.7 + 0.4 * 0.4), 6)
  })

  it('returns null for unknown (vindex, layer, feature) tuples', () => {
    expect(store.getSignature('vindex-X', 20, 999)).toBeNull()
  })

  it('upsert replaces existing rows on same primary key', () => {
    store.upsertSignatures('vindex-X', 'probes-v1', [sig(20, 1, { excited: 0.5 })])
    store.upsertSignatures('vindex-X', 'probes-v1', [sig(20, 1, { delighted: 0.9 })])
    const got = store.getSignature('vindex-X', 20, 1)!
    expect(got.labels.excited).toBeUndefined()
    expect(got.labels.delighted).toBeCloseTo(0.9, 6)
  })

  it('counts only the requested vindex', () => {
    store.upsertSignatures('vindex-X', 'probes-v1', [
      sig(20, 1, { excited: 0.5 }),
      sig(20, 2, { calm: 0.5 }),
    ])
    store.upsertSignatures('vindex-Y', 'probes-v1', [sig(20, 1, { engaged: 0.5 })])
    expect(store.count('vindex-X')).toBe(2)
    expect(store.count('vindex-Y')).toBe(1)
  })

  it('clear removes only the named vindex rows', () => {
    store.upsertSignatures('vindex-X', 'probes-v1', [sig(20, 1, { excited: 0.5 })])
    store.upsertSignatures('vindex-Y', 'probes-v1', [sig(20, 1, { engaged: 0.5 })])
    expect(store.clear('vindex-X')).toBe(1)
    expect(store.count('vindex-X')).toBe(0)
    expect(store.count('vindex-Y')).toBe(1)
  })

  it('loadAllAsMap returns a layer:idx-keyed map', () => {
    store.upsertSignatures('vindex-X', 'probes-v1', [
      sig(20, 1, { excited: 0.5 }),
      sig(22, 7, { calm: 0.4 }),
    ])
    const map = store.loadAllAsMap('vindex-X')
    expect(map.size).toBe(2)
    expect(map.get('20:1')!.labels.excited).toBeCloseTo(0.5, 6)
    expect(map.get('22:7')!.labels.calm).toBeCloseTo(0.4, 6)
  })

  it('upsertProbeSet stores metadata + roundtrips', () => {
    store.upsertProbeSet({
      id: 'probes-v1',
      vindexId: 'vindex-X',
      description: 'starter pack',
      probeCountPerQuadrant: 3,
      totalProbes: 12,
      createdAt: '2026-05-06T00:00:00Z',
      metadata: { author: 'cassi+valerie' },
    })
    const got = store.getProbeSet('probes-v1')
    expect(got).not.toBeNull()
    expect(got!.totalProbes).toBe(12)
    expect(got!.metadata.author).toBe('cassi+valerie')
  })

  it('returns null for unknown probe set id', () => {
    expect(store.getProbeSet('nope')).toBeNull()
  })

  it('upsert is transactional — all-or-nothing on bulk insert', () => {
    // 1000 rows in a single tx — ensure they're all visible after
    const sigs: FeatureAffectSignature[] = []
    for (let i = 0; i < 1000; i++) {
      sigs.push(sig(20, i, { excited: 0.5 }))
    }
    store.upsertSignatures('vindex-X', 'probes-v1', sigs)
    expect(store.count('vindex-X')).toBe(1000)
  })
})
