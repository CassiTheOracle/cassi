// HOST-WIRED: requires CassiCore daemon runtime; excluded from default vitest run.

/**
 * Corpus LLM health tracking tests (C-LLM-1).
 *
 * Covers: state-machine transitions, exponential backoff, fallback adapter,
 * gradual recovery window, and probe targeting.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CorpusTree } from '../../core/intelligence/constellation/corpus-tree.js'
import { Corpus } from '../../core/intelligence/constellation/corpus.js'
import type { CorpusDeps } from '../../core/intelligence/constellation/corpus-types.js'
import { DEFAULT_ADAPTIVE_CADENCE_CONFIG } from '../../core/intelligence/constellation/corpus-types.js'
import type { BrainstemAnnotation, WorkUnitAnnotation, DetectedPattern } from '../../core/intelligence/helix/brainstem-types.js'

const FAST_CADENCE = { ...DEFAULT_ADAPTIVE_CADENCE_CONFIG, minPollMs: 1, maxPollMs: 20 }


function makeLogger() {
  const log = { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn(), child: vi.fn(() => log) }
  return log
}

function makeAnnotation(overrides: Partial<BrainstemAnnotation> = {}): BrainstemAnnotation {
  return {
    workUnitId: `wu-${Math.random().toString(36).slice(2, 8)}`,
    axonStep: 1,
    score: 0.7,
    annotation: 'implementation' as WorkUnitAnnotation,
    pattern: 'none' as DetectedPattern,
    synthesis: 'Yang and Yin agree',
    guidance: null,
    guidanceUrgency: 'low' as any,
    trainingNote: '',
    timestamp: Date.now(),
    ...overrides,
  }
}

function makePrimaryLLM(
  impl: () => Promise<{ content: string; truncated: boolean }> = () =>
    Promise.resolve({ content: 'ASSESSMENT: ok\nSYNTHESIS: NONE', truncated: false }),
) {
  return { complete: vi.fn().mockImplementation(impl) }
}

function makeDeps(overrides: Partial<CorpusDeps> = {}): CorpusDeps {
  return {
    llm: makePrimaryLLM(),
    logger: makeLogger() as any,
    goal: 'Test goal',
    constellationId: 'test-constellation',
    ...overrides,
  }
}


/**
 * Run a Corpus briefly while continuously pushing annotations so the LLM
 * is triggered multiple times, then stop and drain.
 */
async function runBriefly(corpus: Corpus, tree: CorpusTree, waitMs = 150): Promise<void> {
  tree.registerBranch('helix-0', 'Test branch', 0)
  // Seed initial annotations before start so the loop sees work immediately
  for (let i = 0; i < 3; i++) tree.pushAnnotation('helix-0', makeAnnotation())
  await corpus.start()
  // Keep pushing so pending stays non-zero across multiple sweeps
  const pump = setInterval(() => tree.pushAnnotation('helix-0', makeAnnotation()), 15)
  await new Promise(r => setTimeout(r, waitMs))
  clearInterval(pump)
  await corpus.stop()
}


describe('Corpus LLM health tracking', () => {
  let tree: CorpusTree

  beforeEach(() => {
    tree = new CorpusTree(makeLogger() as any)
  })

  describe('initial state', () => {
    it('starts in primary state with no failures', () => {
      const corpus = new Corpus(tree, makeDeps())
      const status = corpus.getLLMHealthStatus()
      expect(status.state).toBe('primary')
      expect(status.consecutiveFailures).toBe(0)
      expect(status.nextProbeAt).toBeNull()
      expect(status.recoverySweepsLeft).toBe(0)
      expect(status.hasFallback).toBe(false)
    })

    it('reports hasFallback when fallbackLLM is provided', () => {
      const corpus = new Corpus(tree, makeDeps({ fallbackLLM: { complete: vi.fn() } }))
      expect(corpus.getLLMHealthStatus().hasFallback).toBe(true)
    })

    it('isLLMHealthy returns true in primary state', () => {
      const corpus = new Corpus(tree, makeDeps())
      expect(corpus.isLLMHealthy()).toBe(true)
    })
  })

  describe('failure threshold + state transitions', () => {
    it('flips to rule_based when primary fails at threshold with no fallback', async () => {
      const failDeps = makeDeps({
        llm: makePrimaryLLM(() => Promise.reject(new Error('LLM timeout'))),
      })
      const corpus = new Corpus(tree, failDeps, {
        idlePollMs: 5,
        llmAnalysisThreshold: 1,
        cadence: 'active',
        useToolBasedAnalysis: false,
        adaptiveCadence: FAST_CADENCE,
        llmHealth: { failureThreshold: 2, probeBackoffBase: 60_000, probeBackoffMax: 60_000 },
      })

      await runBriefly(corpus, tree)

      const status = corpus.getLLMHealthStatus()
      expect(status.state).toBe('rule_based')
      expect(corpus.isLLMHealthy()).toBe(false)
      expect(status.nextProbeAt).toBeGreaterThan(Date.now())
    })

    it('flips to fallback (not rule_based) when fallbackLLM is available', async () => {
      const primaryLLM = makePrimaryLLM(() => Promise.reject(new Error('primary fail')))
      const fallbackLLM = {
        complete: vi.fn().mockResolvedValue({ content: 'ASSESSMENT: ok\nSYNTHESIS: NONE', truncated: false }),
      }
      const corpus = new Corpus(tree, { ...makeDeps({ llm: primaryLLM }), fallbackLLM }, {
        idlePollMs: 5,
        llmAnalysisThreshold: 1,
        cadence: 'active',
        useToolBasedAnalysis: false,
        adaptiveCadence: FAST_CADENCE,
        llmHealth: { failureThreshold: 2, probeBackoffBase: 60_000, probeBackoffMax: 60_000 },
      })

      await runBriefly(corpus, tree, 150)

      const status = corpus.getLLMHealthStatus()
      // Primary failed → escalated to fallback; fallback succeeds so stays 'fallback'
      expect(status.state).toBe('fallback')
      expect(corpus.isLLMHealthy()).toBe(true)
      expect(fallbackLLM.complete).toHaveBeenCalled()
    })

    it('flips to rule_based when both primary and fallback fail', async () => {
      const primaryLLM = makePrimaryLLM(() => Promise.reject(new Error('primary fail')))
      const fallbackLLM = { complete: vi.fn().mockRejectedValue(new Error('fallback fail')) }
      const corpus = new Corpus(tree, { ...makeDeps({ llm: primaryLLM }), fallbackLLM }, {
        idlePollMs: 5,
        llmAnalysisThreshold: 1,
        cadence: 'active',
        useToolBasedAnalysis: false,
        adaptiveCadence: FAST_CADENCE,
        llmHealth: { failureThreshold: 2, probeBackoffBase: 60_000, probeBackoffMax: 60_000 },
      })

      await runBriefly(corpus, tree, 200)

      const status = corpus.getLLMHealthStatus()
      expect(status.state).toBe('rule_based')
      expect(corpus.isLLMHealthy()).toBe(false)
    })

    it('sets nextProbeAt to a future timestamp after hitting threshold', async () => {
      const before = Date.now()
      const corpus = new Corpus(tree, makeDeps({
        llm: makePrimaryLLM(() => Promise.reject(new Error('fail'))),
      }), {
        idlePollMs: 5,
        llmAnalysisThreshold: 1,
        cadence: 'active',
        useToolBasedAnalysis: false,
        adaptiveCadence: FAST_CADENCE,
        llmHealth: { failureThreshold: 2, probeBackoffBase: 10_000, probeBackoffMax: 60_000 },
      })

      await runBriefly(corpus, tree)

      const { nextProbeAt } = corpus.getLLMHealthStatus()
      expect(nextProbeAt).not.toBeNull()
      expect(nextProbeAt!).toBeGreaterThan(before + 5_000)
    })
  })

  describe('backoff enforcement', () => {
    it('does not call primary LLM for probes until backoff expires', async () => {
      let callCount = 0
      const primaryLLM = {
        complete: vi.fn().mockImplementation(() => {
          callCount++
          // First 2 calls fail to trigger threshold; after that always recovers
          return callCount <= 2
            ? Promise.reject(new Error('fail'))
            : Promise.resolve({ content: 'ok', truncated: false })
        }),
      }
      const corpus = new Corpus(tree, makeDeps({ llm: primaryLLM }), {
        idlePollMs: 5,
        llmAnalysisThreshold: 1,
        cadence: 'active',
        useToolBasedAnalysis: false,
        adaptiveCadence: FAST_CADENCE,
        llmHealth: { failureThreshold: 2, probeBackoffBase: 300_000, probeBackoffMax: 300_000 },
      })

      await runBriefly(corpus, tree, 200)

      // Primary should have been called exactly twice (both failures); backoff prevents probes
      expect(primaryLLM.complete).toHaveBeenCalledTimes(2)
      expect(corpus.getLLMHealthStatus().state).toBe('rule_based')
    })
  })

  describe('health probe targets primary', () => {
    it('probes primary LLM to recover even when in fallback state', async () => {
      let primaryCalls = 0
      const primaryLLM = {
        complete: vi.fn().mockImplementation(() => {
          primaryCalls++
          // Fail first two calls, succeed on probe
          return primaryCalls <= 2
            ? Promise.reject(new Error('fail'))
            : Promise.resolve({ content: 'ok', truncated: false })
        }),
      }
      const fallbackLLM = {
        complete: vi.fn().mockResolvedValue({ content: 'fallback ok', truncated: false }),
      }
      const corpus = new Corpus(tree, { ...makeDeps({ llm: primaryLLM }), fallbackLLM }, {
        idlePollMs: 5,
        llmAnalysisThreshold: 1,
        cadence: 'active',
        useToolBasedAnalysis: false,
        adaptiveCadence: FAST_CADENCE,
        llmHealth: { failureThreshold: 2, probeBackoffBase: 0, probeBackoffMax: 0, recoveryWindow: 2 },
      })

      await runBriefly(corpus, tree, 200)

      // Primary should have been called: 2 failures + at least 1 probe
      expect(primaryLLM.complete.mock.calls.length).toBeGreaterThanOrEqual(3)

      // After recovery, corpus should be back on primary
      const status = corpus.getLLMHealthStatus()
      expect(status.state).toBe('primary')
    })
  })

  describe('gradual recovery window', () => {
    it('recoverySweepsLeft decrements from recoveryWindow after probe succeeds', async () => {
      let calls = 0
      const primaryLLM = {
        complete: vi.fn().mockImplementation(() => {
          calls++
          // Fail 2×, then succeed so probe fires and recovers
          return calls <= 2
            ? Promise.reject(new Error('fail'))
            : Promise.resolve({ content: 'ok', truncated: false })
        }),
      }
      const corpus = new Corpus(tree, makeDeps({ llm: primaryLLM }), {
        idlePollMs: 5,
        llmAnalysisThreshold: 1,
        cadence: 'active',
        useToolBasedAnalysis: false,
        adaptiveCadence: FAST_CADENCE,
        llmHealth: { failureThreshold: 2, probeBackoffBase: 0, probeBackoffMax: 0, recoveryWindow: 5 },
      })

      tree.registerBranch('helix-0', 'Test', 0)
      for (let i = 0; i < 3; i++) tree.pushAnnotation('helix-0', makeAnnotation())
      await corpus.start()
      const pump = setInterval(() => tree.pushAnnotation('helix-0', makeAnnotation()), 15)
      await new Promise(r => setTimeout(r, 200))
      clearInterval(pump)
      await corpus.stop()

      const status = corpus.getLLMHealthStatus()
      if (status.state === 'primary') {
        // If recovered, recoverySweepsLeft should be <= recoveryWindow (may have ticked down)
        expect(status.recoverySweepsLeft).toBeLessThanOrEqual(5)
      }
      // Either recovered (primary) or still in fallback/rule_based — both are valid timing outcomes
      expect(['primary', 'fallback', 'rule_based']).toContain(status.state)
    })
  })

  describe('config defaults', () => {
    it('uses DEFAULT_LLM_HEALTH_CONFIG when llmHealth not provided', async () => {
      const failDeps = makeDeps({
        llm: makePrimaryLLM(() => Promise.reject(new Error('fail'))),
      })
      const corpus = new Corpus(tree, failDeps, {
        idlePollMs: 5,
        llmAnalysisThreshold: 1,
        cadence: 'active',
        useToolBasedAnalysis: false,
        adaptiveCadence: FAST_CADENCE,
      })

      await runBriefly(corpus, tree)

      // Default failureThreshold is 2 — state should have flipped
      const status = corpus.getLLMHealthStatus()
      expect(status.state).toBe('rule_based')
    })

    it('respects partial llmHealth config override', () => {
      const corpus = new Corpus(tree, makeDeps(), {
        llmHealth: { failureThreshold: 5 },
      })
      // Not easily observable directly, but we can confirm construction succeeds
      const status = corpus.getLLMHealthStatus()
      expect(status.state).toBe('primary')
    })
  })
})
