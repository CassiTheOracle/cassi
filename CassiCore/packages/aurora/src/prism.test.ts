/**
 * Tests for Prism (B8.P.1) — spectral accumulation, decay-on-read,
 * balanced/stark scans, gap reports, two-connection coexistence.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import Database from 'better-sqlite3'

import { Prism, ALL_AFFECT_COLORS, PRISM_SCHEMA_SQL } from './prism.js'
import type { ForkContribution } from './counterfactual-engine.js'
import type { AffectLabel } from '@cassicore/mnemic-field'


function mockLogger() {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => mockLogger(),
  } as any
}

function makeContribution(overrides: Partial<ForkContribution> = {}): ForkContribution {
  return {
    forkId: 'fork-test-1',
    color: 'calm',
    effectiveAffect: { valence: 0.4, arousal: 0.2 },
    perturbations: [{ type: 'affect', valence: 0.4, arousal: 0.2 }],
    contributedNodes: [
      { nodeId: 'lamina', salience: 0.7, forkOnly: false, activated: true },
    ],
    observedAt: Date.now(),
    ...overrides,
  }
}

describe('Prism', () => {
  let prism: Prism
  let tmpDir: string
  let dbPath: string

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-test-'))
    dbPath = path.join(tmpDir, 'aurora.db')
    prism = new Prism(dbPath, mockLogger())
  })

  afterEach(() => {
    prism.close()
    vi.useRealTimers()
    fs.rmSync(tmpDir, { recursive: true, force: true })
  })


  describe('deposit', () => {
    it('records a single contribution with one node', () => {
      prism.deposit(makeContribution())
      const spectrum = prism.spectrumAt('lamina')
      expect(spectrum.size).toBe(1)
      expect(spectrum.get('calm')?.weight).toBeCloseTo(0.7, 5)
      expect(spectrum.get('calm')?.contributionCount).toBe(1)
    })

    it('accumulates same-color deposits with decay-aware addition', () => {
      const t0 = Date.UTC(2026, 0, 1, 0, 0, 0)
      vi.setSystemTime(t0)
      prism.deposit(makeContribution({ forkId: 'f1', observedAt: t0, contributedNodes: [
        { nodeId: 'lamina', salience: 0.6, forkOnly: false, activated: true },
      ] }))

      vi.setSystemTime(t0 + 21 * 86_400_000)
      prism.deposit(makeContribution({ forkId: 'f2', observedAt: t0 + 21 * 86_400_000, contributedNodes: [
        { nodeId: 'lamina', salience: 0.4, forkOnly: false, activated: true },
      ] }))

      const spectrum = prism.spectrumAt('lamina', t0 + 21 * 86_400_000)
      expect(spectrum.get('calm')?.weight).toBeCloseTo(0.7, 2)
      expect(spectrum.get('calm')?.contributionCount).toBe(2)
    })

    it('keeps different colors as separate spectral bands', () => {
      prism.deposit(makeContribution({ forkId: 'f1', color: 'calm', contributedNodes: [
        { nodeId: 'lamina', salience: 0.5, forkOnly: false, activated: true },
      ] }))
      prism.deposit(makeContribution({ forkId: 'f2', color: 'excited', contributedNodes: [
        { nodeId: 'lamina', salience: 0.4, forkOnly: false, activated: true },
      ] }))
      const spectrum = prism.spectrumAt('lamina')
      expect(spectrum.size).toBe(2)
      expect(spectrum.get('calm')?.weight).toBeCloseTo(0.5, 5)
      expect(spectrum.get('excited' as AffectLabel)?.weight).toBeCloseTo(0.4, 5)
    })

    it('preserves the fork-only flag on synthetic nodes', () => {
      prism.deposit(makeContribution({ contributedNodes: [
        { nodeId: 'fork-only:novel-concept', salience: 0.5, forkOnly: true, activated: true },
      ] }))
      const stark = prism.starkConcepts(0.3, 0.1)
      expect(stark.length).toBe(1)
      expect(stark[0].forkOnly).toBe(true)
      expect(stark[0].conceptId).toBe('fork-only:novel-concept')
    })

    it('skips nodes with non-positive salience', () => {
      prism.deposit(makeContribution({ contributedNodes: [
        { nodeId: 'lamina', salience: 0.5, forkOnly: false, activated: true },
        { nodeId: 'noise', salience: 0, forkOnly: false, activated: false },
        { nodeId: 'negative', salience: -0.1, forkOnly: false, activated: false },
      ] }))
      expect(prism.spectrumAt('lamina').size).toBe(1)
      expect(prism.spectrumAt('noise').size).toBe(0)
      expect(prism.spectrumAt('negative').size).toBe(0)
    })

    it('writes a contribution row even when there are no contributed nodes', () => {
      prism.deposit(makeContribution({ forkId: 'empty', contributedNodes: [] }))
      const db = new Database(dbPath, { readonly: true })
      try {
        const row = db.prepare('SELECT fork_id, color FROM prism_fork_contributions WHERE fork_id = ?').get('empty') as any
        expect(row).toBeDefined()
        expect(row.color).toBe('calm')
      } finally {
        db.close()
      }
    })

    it('UPSERTs duplicate forkIds, keeping the latest emission', () => {
      const t0 = Date.UTC(2026, 0, 1)
      prism.deposit(makeContribution({ forkId: 'same', observedAt: t0, color: 'calm' }))
      prism.deposit(makeContribution({ forkId: 'same', observedAt: t0 + 1000, color: 'excited' }))

      const db = new Database(dbPath, { readonly: true })
      try {
        const rows = db.prepare('SELECT fork_id, color FROM prism_fork_contributions WHERE fork_id = ?').all('same') as any[]
        expect(rows.length).toBe(1)
        expect(rows[0].color).toBe('excited')
      } finally {
        db.close()
      }
    })
  })


  describe('spectrumAt + decay-on-read', () => {
    it('decays weights according to half-life', () => {
      const t0 = Date.UTC(2026, 0, 1)
      vi.setSystemTime(t0)
      prism.deposit(makeContribution({ observedAt: t0, contributedNodes: [
        { nodeId: 'lamina', salience: 1.0, forkOnly: false, activated: true },
      ] }))

      const oneHalfLife = t0 + 21 * 86_400_000
      const spectrum = prism.spectrumAt('lamina', oneHalfLife)
      expect(spectrum.get('calm')?.weight).toBeCloseTo(0.5, 2)
    })

    it('omits sub-threshold colors', () => {
      const t0 = Date.UTC(2026, 0, 1)
      prism.deposit(makeContribution({ observedAt: t0, contributedNodes: [
        { nodeId: 'lamina', salience: 0.06, forkOnly: false, activated: true },
      ] }))

      const eightHalfLives = t0 + 8 * 21 * 86_400_000
      const spectrum = prism.spectrumAt('lamina', eightHalfLives)
      expect(spectrum.has('calm')).toBe(false)
    })

    it('returns empty map for unknown concept', () => {
      expect(prism.spectrumAt('nonexistent').size).toBe(0)
    })
  })


  describe('balanced and starkConcepts', () => {
    it('flags multi-color nodes as balanced when weights are close to uniform', () => {
      const colors: AffectLabel[] = ['calm', 'engaged', 'warm', 'content', 'excited', 'delighted']
      let i = 0
      for (const color of colors) {
        prism.deposit(makeContribution({
          forkId: `f${i++}`,
          color,
          contributedNodes: [{ nodeId: 'lamina', salience: 2.0, forkOnly: false, activated: true }],
        }))
      }

      const balanced = prism.balanced(0.7, 5)
      expect(balanced.length).toBe(1)
      expect(balanced[0].conceptId).toBe('lamina')
      expect(balanced[0].balanceScore).toBeGreaterThan(0.7)
      expect(balanced[0].totalWeight).toBeGreaterThanOrEqual(12)
    })

    it('flags single-color-dominant nodes as stark', () => {
      prism.deposit(makeContribution({ contributedNodes: [
        { nodeId: 'lamina', salience: 5.0, forkOnly: false, activated: true },
      ] }))

      const stark = prism.starkConcepts(0.1, 1)
      expect(stark.length).toBe(1)
      expect(stark[0].conceptId).toBe('lamina')
      expect(stark[0].balanceScore).toBeLessThan(0.1)
    })

    it('respects minTotalWeight', () => {
      prism.deposit(makeContribution({ contributedNodes: [
        { nodeId: 'tiny', salience: 0.1, forkOnly: false, activated: true },
      ] }))

      expect(prism.balanced(0, 5).length).toBe(0)
      expect(prism.balanced(0, 0.05).length).toBe(1)
    })

    it('skips nodes whose spectrum has fully decayed away', () => {
      const t0 = Date.UTC(2026, 0, 1)
      prism.deposit(makeContribution({ observedAt: t0, contributedNodes: [
        { nodeId: 'lamina', salience: 0.06, forkOnly: false, activated: true },
      ] }))

      const farFuture = t0 + 12 * 21 * 86_400_000
      expect(prism.balanced(0, 0.01, farFuture).length).toBe(0)
      expect(prism.starkConcepts(1.0, 0.01, farFuture).length).toBe(0)
    })
  })


  describe('gapReport', () => {
    it('lists explored colors and missing colors', () => {
      prism.deposit(makeContribution({ forkId: 'f1', color: 'calm', contributedNodes: [
        { nodeId: 'lamina', salience: 1.0, forkOnly: false, activated: true },
      ] }))
      prism.deposit(makeContribution({ forkId: 'f2', color: 'engaged', contributedNodes: [
        { nodeId: 'lamina', salience: 1.0, forkOnly: false, activated: true },
      ] }))

      const gaps = prism.gapReport('lamina')
      expect(gaps.explored.sort()).toEqual(['calm', 'engaged'])
      expect(gaps.missing).toHaveLength(ALL_AFFECT_COLORS.length - 2)
      expect(gaps.suggestion).not.toBeNull()
      expect(gaps.suggestion?.fork).toBe('lamina')
      expect(gaps.suggestion?.perturbation.type).toBe('affect')
    })

    it('returns null suggestion when all colors are present', () => {
      let i = 0
      for (const color of ALL_AFFECT_COLORS) {
        prism.deposit(makeContribution({
          forkId: `f${i++}`,
          color,
          contributedNodes: [{ nodeId: 'lamina', salience: 1.0, forkOnly: false, activated: true }],
        }))
      }
      const gaps = prism.gapReport('lamina')
      expect(gaps.missing).toHaveLength(0)
      expect(gaps.suggestion).toBeNull()
    })

    it('treats sub-threshold colors as effectively unseen', () => {
      const t0 = Date.UTC(2026, 0, 1)
      prism.deposit(makeContribution({ observedAt: t0, color: 'calm', contributedNodes: [
        { nodeId: 'lamina', salience: 0.06, forkOnly: false, activated: true },
      ] }))
      prism.deposit(makeContribution({ forkId: 'f2', observedAt: t0, color: 'engaged', contributedNodes: [
        { nodeId: 'lamina', salience: 5.0, forkOnly: false, activated: true },
      ] }))

      const farFuture = t0 + 12 * 21 * 86_400_000
      const gaps = prism.gapReport('lamina', farFuture)
      expect(gaps.explored).not.toContain('calm')
      expect(gaps.missing).toContain('calm')
    })
  })


  describe('totalSpectrum', () => {
    it('aggregates per-color exposure across all nodes', () => {
      prism.deposit(makeContribution({ forkId: 'f1', color: 'calm', contributedNodes: [
        { nodeId: 'lamina', salience: 0.5, forkOnly: false, activated: true },
      ] }))
      prism.deposit(makeContribution({ forkId: 'f2', color: 'calm', contributedNodes: [
        { nodeId: 'reverie', salience: 0.7, forkOnly: false, activated: true },
      ] }))
      prism.deposit(makeContribution({ forkId: 'f3', color: 'engaged', contributedNodes: [
        { nodeId: 'lamina', salience: 0.3, forkOnly: false, activated: true },
      ] }))

      const total = prism.totalSpectrum()
      expect(total.get('calm')).toBeCloseTo(1.2, 2)
      expect(total.get('engaged')).toBeCloseTo(0.3, 5)
    })
  })


  describe('persistence round-trip', () => {
    it('reads back deposits after close and reopen', () => {
      const t0 = Date.UTC(2026, 0, 1)
      vi.setSystemTime(t0)
      prism.deposit(makeContribution({ observedAt: t0, contributedNodes: [
        { nodeId: 'lamina', salience: 0.5, forkOnly: false, activated: true },
      ] }))
      prism.close()

      const reopened = new Prism(dbPath, mockLogger())
      try {
        const spectrum = reopened.spectrumAt('lamina', t0)
        expect(spectrum.get('calm')?.weight).toBeCloseTo(0.5, 5)
        expect(reopened.nodeCount()).toBe(1)
      } finally {
        reopened.close()
      }
    })
  })


  describe('two-connection coexistence (WAL)', () => {
    it('writes from one Prism are visible to a second Prism on the same file', () => {
      const second = new Prism(dbPath, mockLogger())
      try {
        prism.deposit(makeContribution({ contributedNodes: [
          { nodeId: 'lamina', salience: 0.5, forkOnly: false, activated: true },
        ] }))
        const spectrum = second.spectrumAt('lamina')
        expect(spectrum.get('calm')?.weight).toBeCloseTo(0.5, 5)
      } finally {
        second.close()
      }
    })
  })


  describe('schema setup', () => {
    it('creates tables matching the exported PRISM_SCHEMA_SQL', () => {
      const db = new Database(dbPath, { readonly: true })
      try {
        const tables = db.prepare(`
          SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'prism_%'
        `).all() as Array<{ name: string }>
        const names = tables.map(t => t.name).sort()
        expect(names).toEqual(['prism_fork_contributions', 'prism_nodes', 'prism_spectra', 'prism_white_records'])
      } finally {
        db.close()
      }
    })

    it('PRISM_SCHEMA_SQL is idempotent (runs cleanly on a populated db)', () => {
      prism.deposit(makeContribution())
      const direct = new Database(dbPath)
      try {
        expect(() => direct.exec(PRISM_SCHEMA_SQL)).not.toThrow()
      } finally {
        direct.close()
      }
      expect(prism.spectrumAt('lamina').size).toBe(1)
    })
  })

  describe('B8.P.4 getProjectionSummary', () => {
    it('returns zero counts on empty Prism', () => {
      const summary = prism.getProjectionSummary()
      expect(summary.nodeCount).toBe(0)
      expect(summary.starkConcepts).toEqual([])
      expect(summary.totalSpectrum.size).toBe(0)
    })

    it('reports stark concepts dominated by a single color', () => {
      // Deposit only `calm`-color contributions to `lamina`
      for (let i = 0; i < 3; i++) {
        prism.deposit(makeContribution({ forkId: `fork-${i}`, color: 'calm' }))
      }
      const summary = prism.getProjectionSummary()
      expect(summary.nodeCount).toBeGreaterThan(0)
      expect(summary.starkConcepts.length).toBeGreaterThan(0)
      const lamina = summary.starkConcepts.find(c => c.conceptId === 'lamina')
      expect(lamina).toBeDefined()
      expect(lamina!.dominantColor).toBe('calm')
      expect(lamina!.missing.length).toBeGreaterThan(0)
      expect(lamina!.missing).not.toContain('calm')
    })

    it('respects topN cap', () => {
      // Deposit 6 distinct stark concepts
      for (let i = 0; i < 6; i++) {
        prism.deposit(makeContribution({
          forkId: `fork-${i}`,
          color: 'calm',
          contributedNodes: [{ nodeId: `concept-${i}`, salience: 0.7, forkOnly: false, activated: true }],
        }))
      }
      const summary = prism.getProjectionSummary({ topN: 3 })
      expect(summary.starkConcepts).toHaveLength(3)
    })

    it('totalSpectrum reflects per-color exposure across the prism', () => {
      prism.deposit(makeContribution({ color: 'calm' }))
      prism.deposit(makeContribution({ color: 'engaged', forkId: 'fork-2' }))
      const summary = prism.getProjectionSummary()
      expect(summary.totalSpectrum.has('calm')).toBe(true)
      expect(summary.totalSpectrum.has('engaged')).toBe(true)
    })

    it('starkConcepts sorted by totalWeight descending', () => {
      // High-salience concept
      prism.deposit(makeContribution({
        forkId: 'fork-h',
        color: 'calm',
        contributedNodes: [{ nodeId: 'high', salience: 1.0, forkOnly: false, activated: true }],
      }))
      // Low-salience concept
      prism.deposit(makeContribution({
        forkId: 'fork-l',
        color: 'calm',
        contributedNodes: [{ nodeId: 'low', salience: 0.1, forkOnly: false, activated: true }],
      }))
      const summary = prism.getProjectionSummary()
      const high = summary.starkConcepts.findIndex(c => c.conceptId === 'high')
      const low = summary.starkConcepts.findIndex(c => c.conceptId === 'low')
      expect(high).toBeLessThan(low)
    })
  })

  describe('B8.P.2 white promotion', () => {
    /** Helper: deposit a balanced-spectrum node 'concept' across N colors with N witnesses. */
    function depositBalanced(opts: {
      colors: string[]
      forkIds: string[]
      perturbationKinds?: string[][]
      observedAtSpacing?: number   // ms between observedAt timestamps
      conceptId?: string
      salience?: number
    }) {
      const { colors, forkIds } = opts
      const conceptId = opts.conceptId ?? 'concept'
      const salience = opts.salience ?? 0.7
      const baseTime = Date.now() - 30 * 86_400_000
      const spacing = opts.observedAtSpacing ?? 86_400_000 * 3 // 3 days
      for (let i = 0; i < forkIds.length; i++) {
        prism.deposit(makeContribution({
          forkId: forkIds[i],
          color: colors[i % colors.length] as any,
          perturbations: (opts.perturbationKinds?.[i] ?? ['affect']).map(k => ({ type: k })) as any,
          observedAt: baseTime + i * spacing,
          contributedNodes: [{ nodeId: conceptId, salience, forkOnly: false, activated: true }],
        }))
      }
    }

    it('whiteCandidates returns empty when no nodes meet criteria', () => {
      expect(prism.whiteCandidates()).toEqual([])
    })

    it('whiteCandidates surfaces nodes meeting balance + weight + colors', () => {
      // Deposit across 7 colors with high salience to clear the criteria thresholds.
      const colors = ['excited', 'delighted', 'engaged', 'content', 'warm', 'calm', 'curiosity']
      const forks = colors.map((_, i) => `fork-${i}`)
      // 8 deposits per color to push total weight past 30
      for (const c of colors) {
        for (let j = 0; j < 8; j++) {
          prism.deposit(makeContribution({
            forkId: `fork-${c}-${j}`,
            color: c as any,
            contributedNodes: [{ nodeId: 'concept', salience: 0.8, forkOnly: false, activated: true }],
          }))
        }
      }
      const candidates = prism.whiteCandidates({ minColors: 5, minBalance: 0.5, minTotalWeight: 5 })
      expect(candidates.length).toBeGreaterThan(0)
      expect(candidates[0].conceptId).toBe('concept')
    })

    it('promoteToWhite refuses witness set with insufficient temporal spread', () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm'],
        forkIds: ['f1', 'f2', 'f3'],
        observedAtSpacing: 60_000, // 1 minute apart — fails 7-day spread
      })
      expect(() => prism.promoteToWhite('concept', ['f1', 'f2', 'f3']))
        .toThrow(/temporal spread/)
    })

    it('promoteToWhite refuses witness set with insufficient kind diversity', () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm'],
        forkIds: ['f1', 'f2', 'f3'],
        perturbationKinds: [['affect'], ['affect'], ['affect']], // only one kind
        observedAtSpacing: 86_400_000 * 4, // 8 days total spread → passes spread gate
      })
      expect(() => prism.promoteToWhite('concept', ['f1', 'f2', 'f3']))
        .toThrow(/kind diversity/)
    })

    it('promoteToWhite succeeds with valid witness, returns WhiteRecord', () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm', 'content'],
        forkIds: ['f1', 'f2', 'f3', 'f4'],
        perturbationKinds: [['affect'], ['concept_prime'], ['add_nodes'], ['affect']],
        observedAtSpacing: 86_400_000 * 3, // 3 days each → spread 9 days
      })
      const record = prism.promoteToWhite('concept', ['f1', 'f2', 'f3', 'f4'])
      expect(record.conceptId).toBe('concept')
      expect(record.demotedAt).toBeNull()
      expect(record.criteriaSnapshot.witnessKindDiversity).toBeGreaterThanOrEqual(3)
      expect(record.criteriaSnapshot.witnessTemporalSpreadDays).toBeGreaterThanOrEqual(7)
    })

    it('promoteToWhite throws on empty witness set', () => {
      expect(() => prism.promoteToWhite('concept', [])).toThrow(/at least one witness/)
    })

    it('promoteToWhite throws when none of the witness fork ids are recorded', () => {
      expect(() => prism.promoteToWhite('concept', ['nope-1', 'nope-2'])).toThrow(/none.*found/)
    })

    it('whiteNodes lists currently-white nodes; demoted excluded', () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm'],
        forkIds: ['f1', 'f2', 'f3'],
        perturbationKinds: [['affect'], ['concept_prime'], ['add_nodes']],
        observedAtSpacing: 86_400_000 * 4,
      })
      prism.promoteToWhite('concept', ['f1', 'f2', 'f3'])
      expect(prism.whiteNodes()).toHaveLength(1)
      prism.demoteFromWhite('concept', 'manual')
      expect(prism.whiteNodes()).toHaveLength(0)
    })

    it('demoteFromWhite preserves the row + sets reason; re-promotion clears demotion', () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm'],
        forkIds: ['f1', 'f2', 'f3'],
        perturbationKinds: [['affect'], ['concept_prime'], ['add_nodes']],
        observedAtSpacing: 86_400_000 * 4,
      })
      prism.promoteToWhite('concept', ['f1', 'f2', 'f3'])
      expect(prism.demoteFromWhite('concept', 'contested')).toBe(true)
      // Re-promote
      const record = prism.promoteToWhite('concept', ['f1', 'f2', 'f3'])
      expect(record.demotedAt).toBeNull()
    })

    it('flagContested marks node + contestedNodes returns it', () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm'],
        forkIds: ['f1', 'f2', 'f3'],
        perturbationKinds: [['affect'], ['concept_prime'], ['add_nodes']],
        observedAtSpacing: 86_400_000 * 4,
      })
      prism.promoteToWhite('concept', ['f1', 'f2', 'f3'])
      expect(prism.flagContested('concept')).toBe(true)
      expect(prism.contestedNodes()).toHaveLength(1)
    })

    it('B8.P.3 — gatherSynthesisInputs throws on non-white concept', () => {
      expect(() => prism.gatherSynthesisInputs('not-promoted'))
        .toThrow(/not currently white/)
    })

    it('B8.P.3 — gatherSynthesisInputs returns spectrum + witness contributions', () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm'],
        forkIds: ['f1', 'f2', 'f3'],
        perturbationKinds: [['affect'], ['concept_prime'], ['add_nodes']],
        observedAtSpacing: 86_400_000 * 4,
      })
      prism.promoteToWhite('concept', ['f1', 'f2', 'f3'])
      const inputs = prism.gatherSynthesisInputs('concept')
      expect(inputs.conceptId).toBe('concept')
      expect(inputs.spectrum.size).toBeGreaterThan(0)
      expect(inputs.record.demotedAt).toBeNull()
      expect(inputs.contributions).toHaveLength(3)
      const forkIds = inputs.contributions.map(c => c.forkId).sort()
      expect(forkIds).toEqual(['f1', 'f2', 'f3'])
    })

    it('B8.P.3 — synthesizeWhiteInvariant calls callback + assembles engram', async () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm'],
        forkIds: ['f1', 'f2', 'f3'],
        perturbationKinds: [['affect'], ['concept_prime'], ['add_nodes']],
        observedAtSpacing: 86_400_000 * 4,
      })
      prism.promoteToWhite('concept', ['f1', 'f2', 'f3'])

      const llm = vi.fn(async (_inputs) => ({
        invariants: ['holds across colors', 'consistent under perturbation'],
        confidence: 0.85,
      }))
      const engram = await prism.synthesizeWhiteInvariant('concept', llm)
      expect(llm).toHaveBeenCalledOnce()
      expect(engram.engramType).toBe('synthesized_invariant')
      expect(engram.concept).toBe('concept')
      expect(engram.invariants).toHaveLength(2)
      expect(engram.affectSignature).toBe('balanced')
      expect(engram.sourceContributions.sort()).toEqual(['f1', 'f2', 'f3'])
      expect(engram.spectralProvenance.length).toBeGreaterThan(0)
      expect(engram.confidence).toBeCloseTo(0.85, 5)
    })

    it('B8.P.3 — synthesizeWhiteInvariant clamps confidence to [0,1]', async () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm'],
        forkIds: ['f1', 'f2', 'f3'],
        perturbationKinds: [['affect'], ['concept_prime'], ['add_nodes']],
        observedAtSpacing: 86_400_000 * 4,
      })
      prism.promoteToWhite('concept', ['f1', 'f2', 'f3'])
      const engram = await prism.synthesizeWhiteInvariant('concept', async () => ({
        invariants: ['x'], confidence: 5.0,
      }))
      expect(engram.confidence).toBe(1)

      const negative = await prism.synthesizeWhiteInvariant('concept', async () => ({
        invariants: ['y'], confidence: -0.5,
      }))
      expect(negative.confidence).toBe(0)
    })

    it('B8.P.3 — synthesizeWhiteInvariant rejects non-array invariants', async () => {
      depositBalanced({
        colors: ['calm', 'engaged', 'warm'],
        forkIds: ['f1', 'f2', 'f3'],
        perturbationKinds: [['affect'], ['concept_prime'], ['add_nodes']],
        observedAtSpacing: 86_400_000 * 4,
      })
      prism.promoteToWhite('concept', ['f1', 'f2', 'f3'])
      await expect(
        prism.synthesizeWhiteInvariant('concept', async () => ({
          invariants: 'not an array' as any, confidence: 0.5,
        })),
      ).rejects.toThrow(/invariants array/)
    })

    it('whiteCandidates excludes already-promoted nodes', () => {
      const colors = ['excited', 'delighted', 'engaged', 'content', 'warm', 'calm', 'curiosity']
      for (const c of colors) {
        for (let j = 0; j < 8; j++) {
          prism.deposit(makeContribution({
            forkId: `fork-${c}-${j}-A`,
            color: c as any,
            contributedNodes: [{ nodeId: 'concept', salience: 0.8, forkOnly: false, activated: true }],
          }))
        }
      }
      // Need diverse witnesses for promotion to succeed
      const witnessForks = ['w1', 'w2', 'w3']
      let baseTime = Date.now() - 30 * 86_400_000
      const witnessKinds = [['affect'], ['concept_prime'], ['add_nodes']]
      for (let i = 0; i < witnessForks.length; i++) {
        prism.deposit(makeContribution({
          forkId: witnessForks[i],
          color: 'calm',
          perturbations: witnessKinds[i].map(k => ({ type: k })) as any,
          observedAt: baseTime + i * 86_400_000 * 4,
          contributedNodes: [{ nodeId: 'concept', salience: 0.8, forkOnly: false, activated: true }],
        }))
      }
      const initialCandidates = prism.whiteCandidates({ minColors: 5, minBalance: 0.5, minTotalWeight: 5 })
      expect(initialCandidates.find(c => c.conceptId === 'concept')).toBeDefined()
      prism.promoteToWhite('concept', witnessForks)
      const afterCandidates = prism.whiteCandidates({ minColors: 5, minBalance: 0.5, minTotalWeight: 5 })
      expect(afterCandidates.find(c => c.conceptId === 'concept')).toBeUndefined()
    })
  })
})
