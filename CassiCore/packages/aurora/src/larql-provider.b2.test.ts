/**
 * B2 affect-conditioned retrieval — tests for the RetrievalPolicy path
 * on LarqlKnowledgeProvider. Exercises:
 *   - resolveTargetAffectVector (consonant / complementary / directed)
 *   - affectCompatibility (dot product, clamping, missing-label handling)
 *   - applyRetrievalPolicy via gateKnnWithPolicy:
 *       welfare strength cap, no-op fallthrough, re-scoring + re-sort,
 *       missing signature → pass-through, currentAffect-less mode fallback
 *
 * The tests don't load a real vindex; they exercise the policy math on a
 * stubbed provider state. Real-vindex integration lands when B2.1b
 * provides actual signatures via the calibration command.
 */

import { describe, it, expect, beforeEach } from 'vitest'

import {
  LarqlKnowledgeProvider,
  resolveTargetAffectVector,
  affectCompatibility,
  type FeatureAffectSignature,
  type RetrievalPolicy,
  type AffectVector,
} from './larql-provider.js'
import { resolveLabel } from '@cassicore/mnemic-field'
import type { Affect, AffectLabel } from '@cassicore/mnemic-field'

function makeLogger() {
  const log: any = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {} }
  log.child = () => log
  return log
}

function sig(labels: Partial<Record<AffectLabel, number>>): FeatureAffectSignature {
  let mag2 = 0
  for (const v of Object.values(labels)) {
    if (typeof v === 'number') mag2 += v * v
  }
  return { layer: 20, featureIndex: 0, labels, magnitude: Math.sqrt(mag2) }
}

describe('resolveTargetAffectVector', () => {
  it('directed mode returns the explicit vector unchanged', () => {
    const v: AffectVector = { weights: { excited: 0.5, calm: -0.2 } }
    const out = resolveTargetAffectVector(
      { mode: 'directed', vector: v, strength: 0.3 },
      { valence: 0.4, arousal: 0.7 },
      resolveLabel,
    )
    expect(out).toBe(v)
  })

  it('consonant mode picks the canonical vector for the current quadrant', () => {
    const happyAffect: Affect = { valence: 0.6, arousal: 0.7 } // excited
    const out = resolveTargetAffectVector(
      { mode: 'consonant', strength: 0.3 },
      happyAffect,
      resolveLabel,
    )
    expect(out.weights.excited).toBeGreaterThan(0)
    // Should not include negative-valence labels in consonant
    expect(out.weights.melancholy).toBeUndefined()
    expect(out.weights.alarmed).toBeUndefined()
  })

  it('complementary mode negates the canonical vector', () => {
    const happyAffect: Affect = { valence: 0.6, arousal: 0.7 } // excited
    const consonant = resolveTargetAffectVector(
      { mode: 'consonant', strength: 0.3 },
      happyAffect,
      resolveLabel,
    )
    const complementary = resolveTargetAffectVector(
      { mode: 'complementary', strength: 0.3 },
      happyAffect,
      resolveLabel,
    )
    for (const k of Object.keys(consonant.weights)) {
      expect(complementary.weights[k as AffectLabel]).toBeCloseTo(
        -(consonant.weights[k as AffectLabel] ?? 0),
        6,
      )
    }
  })
})

describe('affectCompatibility', () => {
  it('returns 0 when feature signature has no overlap with target', () => {
    const featureSig = sig({ frustrated: 0.8 })
    const target: AffectVector = { weights: { excited: 1.0 } }
    expect(affectCompatibility(featureSig, target)).toBe(0)
  })

  it('returns positive compat for aligned signatures', () => {
    const featureSig = sig({ excited: 0.8, delighted: 0.4 })
    const target: AffectVector = { weights: { excited: 0.7, delighted: 0.5 } }
    expect(affectCompatibility(featureSig, target)).toBeGreaterThan(0)
  })

  it('returns negative compat for anti-aligned signatures', () => {
    const featureSig = sig({ excited: 0.8 })
    const target: AffectVector = { weights: { excited: -1.0 } }
    expect(affectCompatibility(featureSig, target)).toBeLessThan(0)
  })

  it('clamps to [-1, +1] for strongly aligned vectors', () => {
    const featureSig = sig({ excited: 5, delighted: 5 })
    const target: AffectVector = { weights: { excited: 5, delighted: 5 } }
    expect(affectCompatibility(featureSig, target)).toBe(1)
  })

  it('clamps to -1 for strongly anti-aligned vectors', () => {
    const featureSig = sig({ excited: 5, delighted: 5 })
    const target: AffectVector = { weights: { excited: -5, delighted: -5 } }
    expect(affectCompatibility(featureSig, target)).toBe(-1)
  })
})

describe('LarqlKnowledgeProvider — gateKnnWithPolicy', () => {
  let provider: LarqlKnowledgeProvider

  beforeEach(() => {
    provider = new LarqlKnowledgeProvider(makeLogger(), {})
    // Stub the larql module + handle so gateKnnWithPolicy can run.
    ;(provider as any).larql = {
      vindexGateKnn: (_h: any, _layer: number, _tok: number, _k: number) => [
        { featureIndex: 1, score: 0.9, label: 'aligned' },
        { featureIndex: 2, score: 0.8, label: 'opposed' },
        { featureIndex: 3, score: 0.7, label: 'unknown' },
      ],
    }
    ;(provider as any).handle = { id: 1 }
    ;(provider as any).loaded = true
  })

  it('returns base hits unchanged when affectBias is null', () => {
    const policy: RetrievalPolicy = { affectBias: null }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy)
    expect(hits.map(h => h.featureIndex)).toEqual([1, 2, 3])
    expect(hits[0].affectCompat).toBeUndefined()
  })

  it('returns base hits when no signature provider is wired', () => {
    const policy: RetrievalPolicy = {
      affectBias: { mode: 'directed', vector: { weights: { excited: 1 } }, strength: 0.5 },
    }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy)
    expect(hits[0].affectCompat).toBeUndefined()
  })

  it('returns base hits for consonant mode without currentAffect', () => {
    provider.setFeatureAffectSignatureProvider(() => sig({ excited: 1 }))
    const policy: RetrievalPolicy = {
      affectBias: { mode: 'consonant', strength: 0.5 },
    }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy)
    // No bias applied — no compat metadata
    expect(hits[0].affectCompat).toBeUndefined()
  })

  it('rescores and re-sorts hits in directed mode', () => {
    provider.setFeatureAffectSignatureProvider((_layer, idx) => {
      if (idx === 1) return sig({ excited: 0.8, delighted: 0.4 })
      if (idx === 2) return sig({ excited: -0.8, melancholy: 0.4 })
      return null
    })
    const policy: RetrievalPolicy = {
      affectBias: {
        mode: 'directed',
        vector: { weights: { excited: 1.0 } },
        strength: 0.5,
      },
    }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy)
    // hit 1 (aligned) should outscore hit 2 (anti-aligned) regardless of base scores
    const aligned = hits.find(h => h.featureIndex === 1)!
    const opposed = hits.find(h => h.featureIndex === 2)!
    expect(aligned.score).toBeGreaterThan(opposed.score)
    expect(aligned.affectCompat).toBeGreaterThan(0)
    expect(opposed.affectCompat).toBeLessThan(0)
  })

  it('preserves baseScore when re-scoring', () => {
    provider.setFeatureAffectSignatureProvider(() => sig({ excited: 0.5 }))
    const policy: RetrievalPolicy = {
      affectBias: { mode: 'directed', vector: { weights: { excited: 1 } }, strength: 0.3 },
    }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy)
    expect(hits[0].baseScore).toBe(0.9)
    expect(hits[0].score).not.toBe(0.9) // got rescored
  })

  it('marks hits with biasMode and biasStrength when policy is applied', () => {
    provider.setFeatureAffectSignatureProvider(() => sig({ excited: 0.5 }))
    const policy: RetrievalPolicy = {
      affectBias: { mode: 'directed', vector: { weights: { excited: 1 } }, strength: 0.4 },
    }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy)
    expect(hits[0].biasMode).toBe('directed')
    expect(hits[0].biasStrength).toBe(0.4)
  })

  it('caps strength at the welfare default (0.5) without explicit opt-in', () => {
    provider.setFeatureAffectSignatureProvider(() => sig({ excited: 1.0 }))
    const policy: RetrievalPolicy = {
      affectBias: { mode: 'directed', vector: { weights: { excited: 1 } }, strength: 0.9 },
    }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy)
    expect(hits[0].biasStrength).toBe(0.5)
  })

  it('honors strength above 0.5 with allowOverStrengthCap=true', () => {
    provider.setFeatureAffectSignatureProvider(() => sig({ excited: 1.0 }))
    const policy: RetrievalPolicy = {
      affectBias: { mode: 'directed', vector: { weights: { excited: 1 } }, strength: 0.8 },
    }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy, { allowOverStrengthCap: true })
    expect(hits[0].biasStrength).toBe(0.8)
  })

  it('passes through hits whose feature has no signature', () => {
    provider.setFeatureAffectSignatureProvider((_l, idx) => {
      if (idx === 1) return sig({ excited: 0.8 })
      return null // hits 2 and 3 unsigned
    })
    const policy: RetrievalPolicy = {
      affectBias: { mode: 'directed', vector: { weights: { excited: 1 } }, strength: 0.5 },
    }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy)
    const unsigned = hits.find(h => h.featureIndex === 2)!
    expect(unsigned.score).toBe(0.8) // unchanged
    expect(unsigned.affectCompat).toBeUndefined()
  })

  it('consonant mode + currentAffect produces a different ordering than directed', () => {
    provider.setCurrentAffect({ valence: -0.5, arousal: 0.7 }) // frustrated
    provider.setFeatureAffectSignatureProvider((_layer, idx) => {
      if (idx === 1) return sig({ frustrated: 0.8, alarmed: 0.4 })
      if (idx === 2) return sig({ excited: 0.8, delighted: 0.4 })
      return null
    })
    const policy: RetrievalPolicy = {
      affectBias: { mode: 'consonant', strength: 0.5 },
    }
    const hits = provider.gateKnnWithPolicy(20, 100, 3, policy)
    // frustrated hit (1) should now outrank excited hit (2)
    expect(hits[0].featureIndex).toBe(1)
  })

  it('complementary mode flips the ordering vs consonant on the same affect', () => {
    provider.setCurrentAffect({ valence: -0.5, arousal: 0.7 }) // frustrated
    provider.setFeatureAffectSignatureProvider((_layer, idx) => {
      if (idx === 1) return sig({ frustrated: 0.8 })
      if (idx === 2) return sig({ excited: 0.8 })
      return null
    })
    const consonantHits = provider.gateKnnWithPolicy(20, 100, 3, {
      affectBias: { mode: 'consonant', strength: 0.5 },
    })
    const complementaryHits = provider.gateKnnWithPolicy(20, 100, 3, {
      affectBias: { mode: 'complementary', strength: 0.5 },
    })
    // Under consonant, frustrated outranks excited.
    const con1 = consonantHits.findIndex(h => h.featureIndex === 1)
    const con2 = consonantHits.findIndex(h => h.featureIndex === 2)
    expect(con1).toBeLessThan(con2)
    // Under complementary, the order flips.
    const com1 = complementaryHits.findIndex(h => h.featureIndex === 1)
    const com2 = complementaryHits.findIndex(h => h.featureIndex === 2)
    expect(com2).toBeLessThan(com1)
  })
})
