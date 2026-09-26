/**
 * Tests for OverlayLayer (C3) — non-destructive vindex overlay patches.
 *
 * Covers:
 *  - Insert and InsertKnn application and query
 *  - Patch rollback and reactivate
 *  - Chain ordering
 *  - Serialization round-trip
 *  - Rejection of destructive operations (phase 1 policy)
 *  - Validation (missing vector, empty knn)
 *
 * See: docs/design/aurora-bidirectional-claustrum.md
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { OverlayLayer } from './overlay-layer.js'
import type { OverlayPatch } from './overlay-layer.js'

function makeLogger() {
  const logs: Record<string, unknown[]> = { info: [], warn: [], error: [], debug: [] }
  return {
    info: (...args: unknown[]) => logs.info.push(args),
    warn: (...args: unknown[]) => logs.warn.push(args),
    error: (...args: unknown[]) => logs.error.push(args),
    debug: (...args: unknown[]) => logs.debug.push(args),
    child: () => makeLogger(),
    logs,
  }
}

function makeProvenance(overrides: Record<string, string> = {}) {
  return {
    author: 'test-harness',
    reason: 'unit test',
    createdAt: new Date().toISOString(),
    ...overrides,
  }
}

function makeInsertPatch(overrides: Partial<OverlayPatch> = {}): OverlayPatch {
  return {
    id: `patch-${Math.random().toString(36).slice(2, 8)}`,
    op: 'insert',
    layer: 14,
    tokenId: Math.floor(Math.random() * 10000),
    label: 'test-concept',
    vector: new Float32Array([0.1, 0.2, 0.3]),
    provenance: makeProvenance(),
    ...overrides,
  }
}

function makeKnnPatch(overrides: Partial<OverlayPatch> = {}): OverlayPatch {
  return {
    id: `knn-${Math.random().toString(36).slice(2, 8)}`,
    op: 'insert_knn',
    layer: 14,
    tokenId: Math.floor(Math.random() * 10000),
    label: 'test-knn-concept',
    knnEntries: [
      { neighbourId: 100, distance: 0.9 },
      { neighbourId: 200, distance: 0.8 },
    ],
    provenance: makeProvenance(),
    ...overrides,
  }
}

describe('OverlayLayer', () => {
  let layer: OverlayLayer
  let logger: ReturnType<typeof makeLogger>

  beforeEach(() => {
    logger = makeLogger()
    layer = new OverlayLayer(logger)
  })

  describe('patch application', () => {
    it('should apply an insert patch', () => {
      const patch = makeInsertPatch()
      const result = layer.apply(patch)

      expect(result.applied).toBe(true)
      expect(result.patchId).toBe(patch.id)
    })

    it('should apply an insert_knn patch', () => {
      const patch = makeKnnPatch()
      const result = layer.apply(patch)

      expect(result.applied).toBe(true)
    })

    it('should reject duplicate patch id', () => {
      const patch = makeInsertPatch({ id: 'dup' })
      expect(layer.apply(patch).applied).toBe(true)

      const result = layer.apply(patch)
      expect(result.applied).toBe(false)
      expect(result.rejectedReason).toContain('already exists')
    })

    it('should reject insert without vector', () => {
      const patch = makeInsertPatch({ vector: undefined })
      const result = layer.apply(patch)

      expect(result.applied).toBe(false)
      expect(result.rejectedReason).toContain('non-empty vector')
    })

    it('should reject insert_knn without knnEntries', () => {
      const patch = makeKnnPatch({ knnEntries: undefined })
      const result = layer.apply(patch)

      expect(result.applied).toBe(false)
      expect(result.rejectedReason).toContain('at least one KNN entry')
    })

    it('should stack multiple patches', () => {
      layer.apply(makeInsertPatch({ id: 'p1' }))
      layer.apply(makeInsertPatch({ id: 'p2' }))

      const active = layer.getActivePatches()
      expect(active).toHaveLength(2)
    })
  })

  describe('rollback', () => {
    it('should rollback an applied patch', () => {
      const patch = makeInsertPatch({ id: 'rollback-test' })
      layer.apply(patch)
      expect(layer.getActivePatches()).toHaveLength(1)

      expect(layer.rollback('rollback-test')).toBe(true)
      expect(layer.getActivePatches()).toHaveLength(0)
    })

    it('should return false for non-existent patch', () => {
      expect(layer.rollback('no-such-patch')).toBe(false)
    })

    it('should return false for already-rolled-back patch', () => {
      const patch = makeInsertPatch({ id: 'double-rollback' })
      layer.apply(patch)
      expect(layer.rollback('double-rollback')).toBe(true)
      expect(layer.rollback('double-rollback')).toBe(false)
    })

    it('should only rollback the specified patch', () => {
      layer.apply(makeInsertPatch({ id: 'keep' }))
      layer.apply(makeInsertPatch({ id: 'remove' }))
      layer.rollback('remove')

      const active = layer.getActivePatches()
      expect(active).toHaveLength(1)
      expect(active[0].id).toBe('keep')
    })
  })

  describe('reactivate', () => {
    it('should reactivate a rolled-back patch', () => {
      layer.apply(makeInsertPatch({ id: 'react-me' }))
      layer.rollback('react-me')
      expect(layer.getActivePatches()).toHaveLength(0)

      expect(layer.reactivate('react-me')).toBe(true)
      expect(layer.getActivePatches()).toHaveLength(1)
    })

    it('should return false for non-existent patch', () => {
      expect(layer.reactivate('nope')).toBe(false)
    })

    it('should return false for already-active patch', () => {
      layer.apply(makeInsertPatch({ id: 'already-active' }))
      expect(layer.reactivate('already-active')).toBe(false)
    })
  })

  describe('query overlay', () => {
    it('should return overlay hits from insert_knn patches', () => {
      const patch = makeKnnPatch({ layer: 14 })
      layer.apply(patch)

      const hits = layer.queryOverlay([14], 10)
      expect(hits.length).toBeGreaterThanOrEqual(2)
      expect(hits[0].source).toBe('overlay')
      expect(hits[0].layer).toBe(14)
    })

    it('should not return hits for layers without patches', () => {
      layer.apply(makeKnnPatch({ layer: 14 }))

      const hits = layer.queryOverlay([99], 10)
      expect(hits).toHaveLength(0)
    })

    it('should respect topK limit', () => {
      layer.apply(makeKnnPatch({
        layer: 14,
        knnEntries: [
          { neighbourId: 100, distance: 0.9 },
          { neighbourId: 200, distance: 0.8 },
          { neighbourId: 300, distance: 0.7 },
        ],
      }))

      const hits = layer.queryOverlay([14], 2)
      expect(hits).toHaveLength(2)
    })

    it('should not include rolled-back patches', () => {
      layer.apply(makeKnnPatch({ id: 'inactive', layer: 14 }))
      layer.rollback('inactive')

      const hits = layer.queryOverlay([14], 10)
      expect(hits).toHaveLength(0)
    })
  })

  describe('query (merged base + overlay)', () => {
    it('should merge base hits with overlay entries', () => {
      layer.apply(makeKnnPatch({
        layer: 14,
        knnEntries: [{ neighbourId: 300, distance: 0.95 }],
      }))

      const baseHits = [
        { featureIndex: 100, score: 0.9 },
        { featureIndex: 200, score: 0.8 },
      ]

      const merged = layer.query(baseHits, 14, 42, 10)
      expect(merged.length).toBeGreaterThanOrEqual(3)
    })

    it('should boost overlay matches over base if distance is higher', () => {
      layer.apply(makeKnnPatch({
        layer: 14,
        knnEntries: [{ neighbourId: 100, distance: 0.99 }],
      }))

      const baseHits = [{ featureIndex: 100, score: 0.5 }]
      const merged = layer.query(baseHits, 14, 42, 10)

      const overlayEntry = merged.find(h => h.featureIndex === 100)
      expect(overlayEntry).toBeDefined()
      expect(overlayEntry!.score).toBeCloseTo(0.99)
      expect(overlayEntry!.source).toBe('overlay')
    })

    it('should return empty for no base hits and no overlay', () => {
      const merged = layer.query([], 14, 42, 10)
      expect(merged).toEqual([])
    })
  })

  describe('layer inspection', () => {
    it('hasLayerEdits returns true for patched layers', () => {
      layer.apply(makeInsertPatch({ layer: 7 }))
      expect(layer.hasLayerEdits(7)).toBe(true)
      expect(layer.hasLayerEdits(99)).toBe(false)
    })

    it('getLayerFeatures returns inserted feature indices', () => {
      layer.apply(makeKnnPatch({
        layer: 14,
        knnEntries: [
          { neighbourId: 100, distance: 0.9 },
          { neighbourId: 200, distance: 0.8 },
        ],
      }))

      const features = layer.getLayerFeatures(14)
      expect(features.sort()).toEqual([100, 200])
    })

    it('getPatch returns a specific patch', () => {
      const patch = makeInsertPatch({ id: 'lookup' })
      layer.apply(patch)

      const found = layer.getPatch('lookup')
      expect(found).not.toBeNull()
      expect(found!.id).toBe('lookup')
    })

    it('getPatch returns null for unknown id', () => {
      expect(layer.getPatch('nope')).toBeNull()
    })
  })

  describe('serialization', () => {
    it('should round-trip through serialize/deserialize', () => {
      const p1 = makeInsertPatch({ id: 'ser-1', vector: new Float32Array([0.5, 0.6]) })
      const p2 = makeKnnPatch({ id: 'ser-2' })
      layer.apply(p1)
      layer.apply(p2)

      const json = layer.serialize()
      const restored = OverlayLayer.deserialize(json, logger)

      const active = restored.getActivePatches()
      expect(active).toHaveLength(2)
      expect(active.map(p => p.id).sort()).toEqual(['ser-1', 'ser-2'])
    })

    it('should preserve rollback state through serialization', () => {
      layer.apply(makeInsertPatch({ id: 'ser-rollback' }))
      layer.rollback('ser-rollback')

      const json = layer.serialize()
      const restored = OverlayLayer.deserialize(json, logger)

      expect(restored.getActivePatches()).toHaveLength(0)
    })
  })

  describe('phase 1 policy', () => {
    it('should reject destructive operations', () => {
      const badPatch: OverlayPatch = {
        id: 'bad',
        op: 'delete' as any,
        layer: 14,
        tokenId: 0,
        provenance: makeProvenance(),
      }

      const result = layer.apply(badPatch)
      expect(result.applied).toBe(false)
      expect(result.rejectedReason).toContain('not permitted')
    })
  })

  describe('clear', () => {
    it('should remove all patches', () => {
      layer.apply(makeInsertPatch())
      layer.apply(makeKnnPatch())

      layer.clear()
      expect(layer.getActivePatches()).toEqual([])
    })
  })

  describe('stats', () => {
    it('should report correct stats', () => {
      layer.apply(makeInsertPatch({ layer: 14 }))
      layer.apply(makeKnnPatch({ layer: 14 }))

      const stats = layer.getStats()
      expect(stats.totalPatches).toBe(2)
      expect(stats.activePatches).toBe(2)
      expect(stats.layersAffected).toBe(1)
    })

    it('should reflect rollback in stats', () => {
      layer.apply(makeInsertPatch({ id: 'stat-rollback' }))
      layer.rollback('stat-rollback')

      const stats = layer.getStats()
      expect(stats.totalPatches).toBe(1)
      expect(stats.activePatches).toBe(0)
    })

    it('should count multiple layers', () => {
      layer.apply(makeInsertPatch({ layer: 7 }))
      layer.apply(makeKnnPatch({ layer: 14 }))

      const stats = layer.getStats()
      expect(stats.layersAffected).toBe(2)
    })
  })

  describe('C3.3 surveyDrift', () => {
    it('returns zero magnitude when overlay matches base exactly', () => {
      const findings = layer.surveyDrift([
        {
          id: 'p1',
          baseHits: [{ featureIndex: 1, score: 0.9 }, { featureIndex: 2, score: 0.5 }],
          overlayHits: [{ featureIndex: 1, score: 0.9 }, { featureIndex: 2, score: 0.5 }],
        },
      ])
      expect(findings).toHaveLength(1)
      expect(findings[0].magnitude).toBe(0)
      expect(findings[0].overlayAdded).toEqual([])
      expect(findings[0].overlayRemoved).toEqual([])
    })

    it('reports added + removed feature indices', () => {
      const findings = layer.surveyDrift([
        {
          id: 'p1',
          baseHits: [{ featureIndex: 1, score: 0.9 }, { featureIndex: 2, score: 0.5 }],
          overlayHits: [{ featureIndex: 2, score: 0.5 }, { featureIndex: 99, score: 0.7 }],
        },
      ])
      expect(findings[0].overlayAdded).toEqual([99])
      expect(findings[0].overlayRemoved).toEqual([1])
      expect(findings[0].magnitude).toBeGreaterThan(0)
    })

    it('sorts findings by magnitude descending', () => {
      const findings = layer.surveyDrift([
        { id: 'low', baseHits: [{ featureIndex: 1, score: 1 }], overlayHits: [{ featureIndex: 1, score: 1 }] },
        { id: 'high', baseHits: [{ featureIndex: 1, score: 1 }], overlayHits: [{ featureIndex: 99, score: 1 }] },
      ])
      expect(findings[0].probeId).toBe('high')
      expect(findings[1].probeId).toBe('low')
    })

    it('handles empty probe list', () => {
      expect(layer.surveyDrift([])).toEqual([])
    })
  })

  describe('C3.3 reversal candidates', () => {
    let patchId: string
    beforeEach(() => {
      const patch = makeInsertPatch()
      patchId = layer.apply(patch).patchId!
    })

    it('proposeReversalCandidate creates and returns a candidate', () => {
      const c = layer.proposeReversalCandidate({
        patchId,
        reason: 'drift_surveillance',
        proposer: 'system',
        rationale: 'overlay diverging from base on probe set',
      })
      expect(c.id).toMatch(/^rc-/)
      expect(c.patchId).toBe(patchId)
      expect(c.reason).toBe('drift_surveillance')
    })

    it('proposeReversalCandidate throws on unknown patch', () => {
      expect(() =>
        layer.proposeReversalCandidate({
          patchId: 'no-such-patch',
          reason: 'manual',
          proposer: 'operator',
          rationale: 'oops',
        }),
      ).toThrow(/not found/)
    })

    it('listReversalCandidates returns proposed candidates', () => {
      layer.proposeReversalCandidate({
        patchId, reason: 'manual', proposer: 'operator', rationale: 'r1',
      })
      layer.proposeReversalCandidate({
        patchId, reason: 'drift_surveillance', proposer: 'system', rationale: 'r2',
      })
      expect(layer.listReversalCandidates()).toHaveLength(2)
    })

    it('acceptReversalCandidate rolls back the patch', () => {
      const c = layer.proposeReversalCandidate({
        patchId, reason: 'manual', proposer: 'cassi', rationale: 'wrong direction',
      })
      const accepted = layer.acceptReversalCandidate(c.id)
      expect(accepted).toBe(true)
      const patch = layer.getAllPatches().find(p => p.id === patchId)
      expect(patch?.active).toBe(false)
      expect(layer.listReversalCandidates()).toEqual([])
    })

    it('rejectReversalCandidate discards without touching the patch', () => {
      const c = layer.proposeReversalCandidate({
        patchId, reason: 'manual', proposer: 'operator', rationale: 'looks wrong',
      })
      expect(layer.rejectReversalCandidate(c.id, 'review-deferred')).toBe(true)
      expect(layer.listReversalCandidates()).toEqual([])
      const patch = layer.getAllPatches().find(p => p.id === patchId)
      expect(patch?.active).toBe(true)
    })

    it('accept/reject return false on unknown candidate id', () => {
      expect(layer.acceptReversalCandidate('nope')).toBe(false)
      expect(layer.rejectReversalCandidate('nope')).toBe(false)
    })
  })

  describe('C3.2 proposed-patch candidates', () => {
    it('proposeOverlayCandidate creates and returns a candidate', () => {
      const c = layer.proposeOverlayCandidate({
        patch: makeInsertPatch(),
        source: 'reverie',
        rationale: 'High-confidence observation',
        confidence: 0.85,
      })
      expect(c.id).toMatch(/^oc-/)
      expect(c.source).toBe('reverie')
      expect(c.confidence).toBe(0.85)
    })

    it('proposeOverlayCandidate rejects disallowed op (Update/Delete)', () => {
      const badPatch = { ...makeInsertPatch(), op: 'update' as any }
      expect(() =>
        layer.proposeOverlayCandidate({
          patch: badPatch,
          source: 'cassi',
          rationale: 'test',
          confidence: 0.7,
        }),
      ).toThrow(/not allowed/)
    })

    it('proposeOverlayCandidate rejects out-of-range confidence', () => {
      expect(() =>
        layer.proposeOverlayCandidate({
          patch: makeInsertPatch(),
          source: 'cassi',
          rationale: 'r',
          confidence: 1.5,
        }),
      ).toThrow(/confidence/)
    })

    it('listOverlayCandidates sorts by confidence descending', () => {
      layer.proposeOverlayCandidate({ patch: makeInsertPatch({ id: 'p1' }), source: 'cassi', rationale: 'r', confidence: 0.4 })
      layer.proposeOverlayCandidate({ patch: makeKnnPatch({ id: 'p2' }), source: 'cassi', rationale: 'r', confidence: 0.9 })
      layer.proposeOverlayCandidate({ patch: makeInsertPatch({ id: 'p3' }), source: 'cassi', rationale: 'r', confidence: 0.7 })
      const list = layer.listOverlayCandidates()
      expect(list.map(c => c.confidence)).toEqual([0.9, 0.7, 0.4])
    })

    it('acceptOverlayCandidate applies the patch + clears', () => {
      const c = layer.proposeOverlayCandidate({
        patch: makeInsertPatch({ id: 'accept-me' }),
        source: 'reverie',
        rationale: 'apply this',
        confidence: 0.85,
      })
      const result = layer.acceptOverlayCandidate(c.id)
      expect(result).not.toBeNull()
      expect(result!.applied).toBe(true)
      expect(result!.patchId).toBe('accept-me')
      expect(layer.listOverlayCandidates()).toEqual([])
    })

    it('rejectOverlayCandidate clears without applying', () => {
      const c = layer.proposeOverlayCandidate({
        patch: makeInsertPatch({ id: 'reject-me' }),
        source: 'observer',
        rationale: 'maybe later',
        confidence: 0.6,
      })
      expect(layer.rejectOverlayCandidate(c.id, 'too-low-confidence')).toBe(true)
      expect(layer.listOverlayCandidates()).toEqual([])
      // Patch was NOT applied
      expect(layer.getPatch('reject-me')).toBeNull()
    })

    it('modifyOverlayCandidate updates patch in place', () => {
      const c = layer.proposeOverlayCandidate({
        patch: makeInsertPatch({ id: 'orig' }),
        source: 'cassi',
        rationale: 'r',
        confidence: 0.7,
      })
      const newPatch = makeKnnPatch({ id: 'modified' })
      const updated = layer.modifyOverlayCandidate(c.id, newPatch)
      expect(updated).not.toBeNull()
      expect(updated!.id).toBe(c.id) // Same candidate id
      expect(updated!.patch.id).toBe('modified')
      expect(updated!.patch.op).toBe('insert_knn')
    })

    it('modifyOverlayCandidate rejects disallowed op', () => {
      const c = layer.proposeOverlayCandidate({
        patch: makeInsertPatch(),
        source: 'cassi',
        rationale: 'r',
        confidence: 0.7,
      })
      expect(() => layer.modifyOverlayCandidate(c.id, { ...makeInsertPatch(), op: 'delete' as any }))
        .toThrow(/not allowed/)
    })

    it('accept/reject/modify return null/false on unknown id', () => {
      expect(layer.acceptOverlayCandidate('nope')).toBeNull()
      expect(layer.rejectOverlayCandidate('nope')).toBe(false)
      expect(layer.modifyOverlayCandidate('nope', makeInsertPatch())).toBeNull()
    })
  })
})
