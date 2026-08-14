import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Database from 'better-sqlite3'
import { MnemicField } from '../src/index.js'
import { mockLogger } from './helpers.js'

function makeInMemoryDb(): Database.Database {
  const db = new Database(':memory:')
  db.pragma('foreign_keys = ON')
  return db
}

describe('Global Workspace Broadcast', () => {
  let field: MnemicField
  let db: Database.Database

  beforeEach(() => {
    db = makeInMemoryDb()
    field = new MnemicField(mockLogger(), db)
  })

  afterEach(() => {
    field.close()
  })

  describe('BroadcastResult', () => {
    it('returns null when luminal set is empty', () => {
      const result = (field as any).broadcastGlobalWorkspace([])
      expect(result).toBeNull()
    })

    it('returns null when no luminal engrams have positions', () => {
      // Create engrams at origin (x=0, y=0) which are filtered out
      const e1 = field.store({ content: 'fact 1', nodeType: 'fact', x: 0, y: 0 })
      const e2 = field.store({ content: 'fact 2', nodeType: 'fact', x: 0, y: 0 })

      const result = (field as any).broadcastGlobalWorkspace([e1.id, e2.id])
      expect(result).toBeNull()
    })

    it('broadcasts with positioned luminal engrams and no nuclei', () => {
      const e1 = field.store({ content: 'positioned', nodeType: 'fact', x: 1.5, y: 2.0 })

      const result = (field as any).broadcastGlobalWorkspace([e1.id])
      expect(result).not.toBeNull()
      expect(result.nucleiPrimed).toBe(0)
      expect(result.nucleiIgnored).toBe(0)
      expect(result.broadcastX).toBeCloseTo(1.5)
      expect(result.broadcastY).toBeCloseTo(2.0)
      expect(result.durationMs).toBeGreaterThanOrEqual(0)
    })

    it('primes nuclei close to the broadcast centroid', () => {
      // Create engrams at position (5, 5)
      const e1 = field.store({ content: 'engram a', nodeType: 'fact', x: 5.0, y: 5.0 })
      const e2 = field.store({ content: 'engram b', nodeType: 'fact', x: 5.0, y: 5.0 })

      // Create nucleus at position (5, 5) — distance 0 → resonance 1.0
      const n1 = field.createNucleus({ label: 'Close Nucleus', centroidX: 5.0, centroidY: 5.0 })

      // Create nucleus far away at (100, 100) — distance ~134 → resonance < 0.01
      const n2 = field.createNucleus({ label: 'Far Nucleus', centroidX: 100.0, centroidY: 100.0 })

      const result = (field as any).broadcastGlobalWorkspace([e1.id, e2.id])
      expect(result).not.toBeNull()
      expect(result!.nucleiPrimed).toBe(1) // n1 primed
      expect(result!.nucleiIgnored).toBe(1) // n2 ignored
      expect(result!.totalNuclei).toBe(2)
    })

    it('computes broadcast centroid as mean of luminal positions', () => {
      const e1 = field.store({ content: 'left', nodeType: 'fact', x: 1.0, y: 1.0 })
      const e2 = field.store({ content: 'right', nodeType: 'fact', x: 3.0, y: 3.0 })

      const result = (field as any).broadcastGlobalWorkspace([e1.id, e2.id])
      expect(result).not.toBeNull()
      expect(result!.broadcastX).toBeCloseTo(2.0)
      expect(result!.broadcastY).toBeCloseTo(2.0)
    })
  })

  describe('getBroadcastSparkModulation', () => {
    it('returns 1.0 when nothing is primed', () => {
      const e = field.store({ content: 'test', nodeType: 'fact', x: 1.0, y: 1.0 })
      const mod = field.getBroadcastSparkModulation(e.id)
      expect(mod).toBe(1.0)
    })

    it('returns 1.0 for engram with no clusterId', () => {
      const e = field.store({ content: 'unclustered', nodeType: 'fact', x: 1.0, y: 1.0 })
      // e.clusterId is null by default
      const mod = field.getBroadcastSparkModulation(e.id)
      expect(mod).toBe(1.0)
    })

    it('returns < 1.0 for engram in a primed nucleus', () => {
      // Create a nucleus
      const n = field.createNucleus({ label: 'Test', centroidX: 1.0, centroidY: 1.0 })

      // Create an engram at the nucleus position
      const e = field.store({ content: 'clustered', nodeType: 'fact', x: 1.0, y: 1.0 })

      // Assign engram to nucleus
      field.update(e.id, { clusterId: n.id })

      // Manually prime the nucleus via broadcast
      const result = (field as any).broadcastGlobalWorkspace([e.id])
      expect(result).not.toBeNull()
      expect(result!.nucleiPrimed).toBe(1)

      // Now the engram's nucleus is primed — modulation should be < 1.0.
      // getBroadcastSparkModulation takes a cluster (nucleus) id; `n.id` is the
      // primed nucleus (engram's clusterId was set to n.id above).
      const mod = field.getBroadcastSparkModulation(n.id)
      expect(mod).toBeLessThan(1.0)
      expect(mod).toBeGreaterThan(0.0)
      // With resonance 1.0 (distance 0), modulation = 1 - 0.9*1.0 = 0.1
      expect(mod).toBeCloseTo(0.1, 1)
    })
  })

  describe('getPrimedNuclei', () => {
    it('returns empty array when nothing is primed', () => {
      const primed = field.getPrimedNuclei()
      expect(primed).toEqual([])
    })

    it('returns primed nuclei after broadcast', () => {
      const n1 = field.createNucleus({ label: 'A', centroidX: 1.0, centroidY: 1.0 })
      const n2 = field.createNucleus({ label: 'B', centroidX: 100.0, centroidY: 100.0 })
      const e = field.store({ content: 'near A', nodeType: 'fact', x: 1.0, y: 1.0 })

      const result = (field as any).broadcastGlobalWorkspace([e.id])
      expect(result).not.toBeNull()

      const primed = field.getPrimedNuclei()
      expect(primed.length).toBe(1)
      expect(primed[0]!.nucleusId).toBe(n1.id)
      expect(primed[0]!.resonance).toBeCloseTo(1.0, 1)
    })
  })

  describe('broadcast failure isolation', () => {
    it('getBroadcastSparkModulation handles nonexistent engram gracefully', () => {
      const mod = field.getBroadcastSparkModulation('nonexistent-id')
      expect(mod).toBe(1.0)
    })

    it('getPrimedNuclei handles empty state gracefully', () => {
      const primed = field.getPrimedNuclei()
      expect(Array.isArray(primed)).toBe(true)
      expect(primed.length).toBe(0)
    })
  })
})
