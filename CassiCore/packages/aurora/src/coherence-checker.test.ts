/**
 * Tests for CoherenceChecker (N6) — cross-module coherence verification.
 *
 * See: docs/design/aurora-cross-module-coherence.md
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { CoherenceChecker } from './coherence-checker.js'
import type {
  CoherenceCheckInput,
  AuroraSnapshot,
  MnemicFieldSnapshot,
  CortexSnapshot,
  AffectSnapshot,
  CoherenceSignal,
} from './coherence-checker.js'
import type { CognitiveNode } from './types.js'


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


function makeNode(overrides: Partial<CognitiveNode> = {}): CognitiveNode {
  return {
    id: `node-${Math.random().toString(36).slice(2, 8)}`,
    label: 'test-node',
    source: 'memory',
    resonance: 0.5,
    centrality: 0.3,
    activated: true,
    ...overrides,
  }
}

function makeAurora(overrides: Partial<AuroraSnapshot> = {}): AuroraSnapshot {
  return {
    nodes: [],
    nodeCount: 0,
    edgeCount: 0,
    focusStack: [],
    momentum: 0.5,
    lastUpdateTime: new Date().toISOString(),
    ...overrides,
  }
}

function makeMnemic(overrides: Partial<MnemicFieldSnapshot> = {}): MnemicFieldSnapshot {
  return {
    engrams: [],
    totalEngams: 0,
    lastUpdateTime: new Date().toISOString(),
    ...overrides,
  }
}

function makeCortex(overrides: Partial<CortexSnapshot> = {}): CortexSnapshot {
  return {
    signals: [],
    totalSignals: 0,
    lastUpdateTime: new Date().toISOString(),
    ...overrides,
  }
}

function makeAffect(overrides: Partial<AffectSnapshot> = {}): AffectSnapshot {
  return {
    currentValence: 0.0,
    currentArousal: 0.3,
    labels: [],
    lastUpdateTime: new Date().toISOString(),
    history: [],
    ...overrides,
  }
}


describe('CoherenceChecker', () => {
  let checker: CoherenceChecker

  beforeEach(() => {
    checker = new CoherenceChecker(makeLogger())
  })

  it('returns empty signals for consistent modules', () => {
    const now = new Date().toISOString()
    const result = checker.checkCoherence({
      aurora: makeAurora({ lastUpdateTime: now }),
      mnemicField: makeMnemic({ lastUpdateTime: now }),
      cortex: makeCortex({ lastUpdateTime: now }),
      affect: makeAffect({ lastUpdateTime: now }),
    })

    expect(result.signals).toHaveLength(0)
    expect(result.autoCorrectedCount).toBe(0)
    expect(result.modulesChecked).toContain('aurora')
  })

  it('detects SIGNAL_MISSING when memory node has no engram', () => {
    const node = makeNode({
      label: 'lambda-calculus',
      content: 'lambda-calculus',
      source: 'memory',
    })

    const result = checker.checkCoherence({
      aurora: makeAurora({ nodes: [node] }),
      mnemicField: makeMnemic(),
    })

    const missing = result.signals.find(s =>
      s.category === 'SIGNAL_MISSING' &&
      s.modules.includes('aurora') &&
      s.modules.includes('mnemic-field'),
    )
    expect(missing).toBeDefined()
    expect(missing?.description).toContain('lambda-calculus')
  })

  it('detects TEMPORAL_DRIFT between Aurora and Mnemic Field', () => {
    const now = new Date()
    const oldTime = new Date(now.getTime() - 600_000).toISOString() // 10 min ago
    const currentTime = now.toISOString()

    const node = makeNode({
      label: 'stale-concept',
      content: 'stale-concept',
      source: 'memory',
    })

    const engram = {
      id: 'eng-1',
      content: 'stale-concept',
      tags: [] as string[],
      createdAt: oldTime,
      potentiation: 0.5,
    }

    const result = checker.checkCoherence({
      aurora: makeAurora({
        nodes: [node],
        lastUpdateTime: currentTime,
      }),
      mnemicField: makeMnemic({
        engrams: [engram],
        lastUpdateTime: oldTime,
      }),
    })

    const drift = result.signals.find(s =>
      s.category === 'TEMPORAL_DRIFT' &&
      s.modules.includes('aurora') &&
      s.modules.includes('mnemic-field'),
    )
    expect(drift).toBeDefined()
    expect(drift?.severity).toBe('warn')
  })

  it('detects TAG_DIVERGENCE between Aurora node and engram', () => {
    const node = makeNode({
      label: 'tagged-concept',
      content: 'tagged-concept',
      source: 'both',
      nodeType: 'episode' as any,
      modelLayers: [12, 14],
    })

    const engram = {
      id: 'eng-2',
      content: 'tagged-concept',
      tags: ['unrelated', 'completely-different'],
      createdAt: new Date().toISOString(),
      potentiation: 0.8,
    }

    const result = checker.checkCoherence({
      aurora: makeAurora({ nodes: [node] }),
      mnemicField: makeMnemic({ engrams: [engram] }),
    })

    const tagDiv = result.signals.find(s => s.category === 'TAG_DIVERGENCE')
    expect(tagDiv).toBeDefined()
    expect(tagDiv?.details).toHaveProperty('overlapRatio')
  })

  it('detects SIGNAL_MISSING when activated Aurora nodes have no Cortex signal', () => {
    const nodes = [
      makeNode({ label: 'active-concept-a', activated: true }),
      makeNode({ label: 'active-concept-b', activated: true }),
      makeNode({ label: 'active-concept-c', activated: true }),
    ]

    const result = checker.checkCoherence({
      aurora: makeAurora({ nodes }),
      cortex: makeCortex({ signals: [] }),
    })

    const missing = result.signals.find(s =>
      s.category === 'SIGNAL_MISSING' &&
      s.modules.includes('aurora') &&
      s.modules.includes('cortex'),
    )
    expect(missing).toBeDefined()
  })

  it('does not flag SIGNAL_MISSING when Cortex has matching signals', () => {
    const node = makeNode({ label: 'my-topic', activated: true })

    const result = checker.checkCoherence({
      aurora: makeAurora({ nodes: [node] }),
      cortex: makeCortex({
        signals: [{
          id: 'sig-1',
          type: 'perception',
          content: 'my-topic',
          region: 'sensory',
          createdAt: new Date().toISOString(),
        }],
      }),
    })

    const missing = result.signals.find(s =>
      s.category === 'SIGNAL_MISSING' &&
      s.modules.includes('aurora') &&
      s.modules.includes('cortex'),
    )
    expect(missing).toBeUndefined()
  })

  it('detects momentum-arousal mismatch (stuck reasoning loop)', () => {
    const result = checker.checkCoherence({
      aurora: makeAurora({ momentum: 0.95 }),
      affect: makeAffect({ currentArousal: 0.1 }),
    })

    const stuck = result.signals.find(s =>
      s.category === 'SIGNAL_MISSING' &&
      s.modules.includes('aurora') &&
      s.modules.includes('affect') &&
      s.description.includes('stuck reasoning loop'),
    )
    expect(stuck).toBeDefined()
    expect(stuck?.severity).toBe('warn')
  })

  it('detects negative valence with empty focus stack', () => {
    const result = checker.checkCoherence({
      aurora: makeAurora({ focusStack: [] }),
      affect: makeAffect({ currentValence: -0.7 }),
    })

    const sig = result.signals.find(s =>
      s.description.includes('negative valence'),
    )
    expect(sig).toBeDefined()
  })

  it('auto-corrects Mnemic-Cortex latency signals', () => {
    const now = new Date()
    const engContent = 'some-topic'
    const engTime = new Date(now.getTime() - 10_000).toISOString()

    const result = checker.checkCoherence({
      mnemicField: makeMnemic({
        engrams: [{
          id: 'eng-lat',
          content: engContent,
          tags: [],
          createdAt: engTime,
          potentiation: 0.5,
        }],
        lastUpdateTime: engTime,
      }),
      cortex: makeCortex({
        signals: [],
        lastUpdateTime: new Date().toISOString(),
      }),
    })

    // Find the Mnemic-Cortex missing signal
    const mcSignal = result.signals.find(s =>
      s.category === 'SIGNAL_MISSING' &&
      s.modules.includes('mnemic-field') &&
      s.modules.includes('cortex') &&
      s.description.includes('recent engrams'),
    )
    // It should be auto-corrected
    expect(mcSignal?.autoCorrected).toBe(true)
    expect(result.autoCorrectedCount).toBeGreaterThanOrEqual(1)
  })

  it('does not auto-correct genuine divergences', () => {
    const now = new Date()
    const oldTime = new Date(now.getTime() - 600_000).toISOString()

    const node = makeNode({
      label: 'divergent-concept',
      content: 'divergent-concept',
      source: 'memory',
    })

    const result = checker.checkCoherence({
      aurora: makeAurora({
        nodes: [node],
        lastUpdateTime: now.toISOString(),
      }),
      mnemicField: makeMnemic({
        lastUpdateTime: oldTime,
      }),
    })

    const genuineSignal = result.signals.find(s =>
      s.category === 'SIGNAL_MISSING' &&
      s.modules.includes('aurora') &&
      s.modules.includes('mnemic-field'),
    )
    // This is a genuine divergence, not auto-corrected
    expect(genuineSignal?.autoCorrected).toBe(false)
  })

  it('disables auto-correction when configured', () => {
    const noAutoChecker = new CoherenceChecker(makeLogger(), {
      autoCorrectLatencyPatterns: false,
    })

    const now = new Date()
    const engTime = new Date(now.getTime() - 10_000).toISOString()

    const result = noAutoChecker.checkCoherence({
      mnemicField: makeMnemic({
        engrams: [{
          id: 'eng-na',
          content: 'no-auto-topic',
          tags: [],
          createdAt: engTime,
          potentiation: 0.5,
        }],
      }),
      cortex: makeCortex({ signals: [] }),
    })

    const latencySig = result.signals.find(s =>
      s.description.includes('recent engrams'),
    )
    expect(latencySig?.autoCorrected).toBe(false)
    expect(result.autoCorrectedCount).toBe(0)
  })

  it('respects maxSignalsPerCheck', () => {
    // Create many nodes to generate many signals
    const nodes: CognitiveNode[] = []
    for (let i = 0; i < 20; i++) {
      nodes.push(makeNode({
        label: `missing-${i}`,
        content: `missing-${i}`,
        source: 'memory',
        activated: true,
      }))
    }

    const smallChecker = new CoherenceChecker(makeLogger(), { maxSignalsPerCheck: 3 })
    const result = smallChecker.checkCoherence({
      aurora: makeAurora({ nodes }),
      mnemicField: makeMnemic(),
      cortex: makeCortex(),
    })

    expect(result.signals.length).toBeLessThanOrEqual(3)
  })

  it('produces correct summary statistics', () => {
    const now = new Date()
    const oldTime = new Date(now.getTime() - 600_000).toISOString()

    const node = makeNode({
      label: 'stats-concept',
      content: 'stats-concept',
      source: 'memory',
      activated: true,
    })

    const result = checker.checkCoherence({
      aurora: makeAurora({
        nodes: [node],
        lastUpdateTime: now.toISOString(),
      }),
      mnemicField: makeMnemic({
        lastUpdateTime: oldTime,
      }),
      cortex: makeCortex({
        signals: [],
        lastUpdateTime: oldTime,
      }),
    })

    expect(result.byCategory).toBeDefined()
    expect(result.bySeverity).toBeDefined()
    expect(result.checkedAt).toBeTruthy()
    expect(result.modulesChecked.length).toBeGreaterThan(0)
  })

  it('maintains signal history', () => {
    // First check
    checker.checkCoherence({
      aurora: makeAurora({ nodes: [makeNode({ source: 'memory' })] }),
      mnemicField: makeMnemic(),
    })

    // Second check
    checker.checkCoherence({
      aurora: makeAurora({ nodes: [makeNode({ source: 'memory' })] }),
      mnemicField: makeMnemic(),
    })

    const history = checker.getHistory(100)
    expect(history.length).toBeGreaterThanOrEqual(2)
  })

  it('filters history by category', () => {
    const now = new Date()
    const oldTime = new Date(now.getTime() - 600_000).toISOString()

    checker.checkCoherence({
      aurora: makeAurora({
        nodes: [makeNode({ source: 'memory', content: 'x' })],
        lastUpdateTime: now.toISOString(),
      }),
      mnemicField: makeMnemic({ lastUpdateTime: oldTime }),
    })

    const missingHistory = checker.getHistoryByCategory('SIGNAL_MISSING')
    expect(missingHistory.every(s => s.category === 'SIGNAL_MISSING')).toBe(true)
  })

  it('filters history by module', () => {
    checker.checkCoherence({
      aurora: makeAurora({ nodes: [makeNode({ source: 'memory' })] }),
      mnemicField: makeMnemic(),
    })

    const auroraHistory = checker.getHistoryByModule('aurora')
    expect(auroraHistory.every(s => s.modules.includes('aurora'))).toBe(true)
  })

  it('clears history', () => {
    checker.checkCoherence({
      aurora: makeAurora({ nodes: [makeNode({ source: 'memory' })] }),
      mnemicField: makeMnemic(),
    })

    checker.clearHistory()
    expect(checker.getHistory().length).toBe(0)
  })

  it('returns modulesChecked for all combinations', () => {
    const result = checker.checkCoherence({
      aurora: makeAurora(),
      mnemicField: makeMnemic(),
      cortex: makeCortex(),
      affect: makeAffect(),
    })

    expect(result.modulesChecked).toContain('aurora')
    expect(result.modulesChecked).toContain('mnemic-field')
    expect(result.modulesChecked).toContain('cortex')
    expect(result.modulesChecked).toContain('affect')
  })

  it('handles empty input gracefully', () => {
    const result = checker.checkCoherence({})
    expect(result.signals).toHaveLength(0)
    expect(result.modulesChecked).toHaveLength(0)
  })

  it('handles single module input', () => {
    const result = checker.checkCoherence({
      aurora: makeAurora(),
    })
    // No cross-module checks possible with just one module
    expect(result.signals).toHaveLength(0)
    expect(result.modulesChecked).toEqual(['aurora'])
  })

  it('detects Affect-Cortex coherence mismatch', () => {
    const result = checker.checkCoherence({
      affect: makeAffect({
        currentArousal: 0.1,
        labels: [],
        currentValence: 0.0,
      }),
      cortex: makeCortex({
        signals: [{
          id: 'sig-aff',
          type: 'anomaly',
          content: 'something broke',
          region: 'limbic',
          createdAt: new Date().toISOString(),
          tags: ['affect', 'frustration'],
        }],
      }),
    })

    const mismatch = result.signals.find(s =>
      s.modules.includes('affect') &&
      s.modules.includes('cortex') &&
      s.category === 'SIGNAL_MISSING',
    )
    expect(mismatch).toBeDefined()
    expect(mismatch?.description).toContain('low arousal')
  })

  describe('N6.2 corrector callbacks', () => {
    function makeMnemicCortexLatencyInput() {
      const now = new Date()
      const engTime = new Date(now.getTime() - 10_000).toISOString()
      return {
        mnemicField: makeMnemic({
          engrams: [{
            id: 'eng-lat',
            content: 'some-topic',
            tags: [],
            createdAt: engTime,
            potentiation: 0.5,
          }],
          lastUpdateTime: engTime,
        }),
        cortex: makeCortex({
          signals: [],
          lastUpdateTime: new Date().toISOString(),
        }),
      }
    }

    it('invokes the mnemicCortexLatency corrector when auto-correcting that pattern', () => {
      const calls: string[] = []
      const c = new CoherenceChecker(makeLogger(), {
        correctors: {
          mnemicCortexLatency: (sig) => { calls.push(sig.id) },
        },
      })
      const result = c.checkCoherence(makeMnemicCortexLatencyInput())
      expect(result.autoCorrectedCount).toBeGreaterThanOrEqual(1)
      expect(calls.length).toBeGreaterThanOrEqual(1)
    })

    it('does not invoke a corrector when auto-correction is disabled', () => {
      const calls: string[] = []
      const c = new CoherenceChecker(makeLogger(), {
        autoCorrectLatencyPatterns: false,
        correctors: {
          mnemicCortexLatency: (sig) => { calls.push(sig.id) },
        },
      })
      c.checkCoherence(makeMnemicCortexLatencyInput())
      expect(calls).toEqual([])
    })

    it('catches corrector errors without breaking the flag', () => {
      const c = new CoherenceChecker(makeLogger(), {
        correctors: {
          mnemicCortexLatency: () => { throw new Error('sync failed') },
        },
      })
      const result = c.checkCoherence(makeMnemicCortexLatencyInput())
      // Despite the corrector throwing, the signal still got flagged
      const mcSig = result.signals.find(s =>
        s.modules.includes('mnemic-field') && s.modules.includes('cortex')
        && s.description.includes('recent engrams')
      )
      expect(mcSig?.autoCorrected).toBe(true)
    })
  })
})
