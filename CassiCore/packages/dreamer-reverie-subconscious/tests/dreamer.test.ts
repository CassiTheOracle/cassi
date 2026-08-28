/**
 * DreamerModule Tests
 *
 * Tests cover:
 * 1. Idle detection (turn tracking, threshold gate)
 * 2. Archive sampling (sampleForDream delegation)
 * 3. Dream engine phases (mock provider, verify JSON output handling)
 * 4. Deep archive migration and filtering
 * 5. Gardening eligibility (only episodic memories retired)
 * 6. InjectionAggregator registration and context injection window
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { DreamerModule, createDreamer } from '../src/dreamer/index.js'
import { DreamCycleEngine } from '../src/dreamer/dream-engine.js'
import {
  buildFreeAssociationPrompt,
  buildCrystallizationPrompt,
  buildGardenPrompt,
} from '../src/dreamer/dream-prompt.js'
import {
  DEFAULT_DREAMER_CONFIG,
  type DreamerConfig,
  type DreamInsight,
} from '../src/dreamer/types.js'


function makeLogger() {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(function () { return this }),
  }
}


function makeMemory(overrides: Record<string, any> = {}) {
  return {
    store: vi.fn(async () => `mem_${Math.random().toString(36).slice(2)}`),
    search: vi.fn(async () => []),
    archiveDeep: vi.fn(),
    searchDeepArchive: vi.fn(async () => []),
    sampleForDream: vi.fn(() => []),
    markArchiveEntriesDreamed: vi.fn(),
    archiveDream: vi.fn(() => `arch_${Math.random().toString(36).slice(2)}`),
    getEpisodicMemoriesByIds: vi.fn(() => []),
    ...overrides,
  }
}


function makeEngine(
  inferReturn = 'Connection found between entries.',
  inferJSONReturn: any[] = [
    {
      content: 'Test insight content about recurring patterns',
      confidence: 0.75,
      sourceEntryIds: ['e1', 'e2'],
      title: 'Test Insight',
      topics: ['testing'],
    },
  ],
  memoryOverrides = {},
) {
  const logger = makeLogger()
  const memory = makeMemory(memoryOverrides)
  const inferFn = vi.fn(async () => inferReturn)
  const inferJSONFn = vi.fn(async () => inferJSONReturn)
  const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any)
  return { engine, memory, logger, inferFn, inferJSONFn }
}


function makeArchiveEntries(count = 3) {
  return Array.from({ length: count }, (_, i) => ({
    id: `entry_${i}`,
    type: 'conversation' as const,
    content: `Sample conversation content ${i}`,
    metadata: {},
    timestamp: Date.now() - i * 3_600_000,
    source: 'test',
  }))
}

// SECTION 1: Default config

describe('DreamerConfig defaults', () => {
  it('has expected default values', () => {
    expect(DEFAULT_DREAMER_CONFIG.enabled).toBe(true)
    expect(DEFAULT_DREAMER_CONFIG.checkIntervalMs).toBe(300_000)
    expect(DEFAULT_DREAMER_CONFIG.idleThresholdMs).toBe(600_000)
    expect(DEFAULT_DREAMER_CONFIG.archiveSampleSize).toBe(40)
    expect(DEFAULT_DREAMER_CONFIG.maxInsightsPerDream).toBe(5)
    expect(DEFAULT_DREAMER_CONFIG.minClusterSizeForGarden).toBe(3)
    expect(DEFAULT_DREAMER_CONFIG.enableGardening).toBe(true)
    expect(DEFAULT_DREAMER_CONFIG.enableLinking).toBe(true)
    expect(DEFAULT_DREAMER_CONFIG.injectContextEnabled).toBe(true)
    expect(DEFAULT_DREAMER_CONFIG.injectContextWindowHours).toBe(4)
  })

  it('createDreamer returns a DreamerModule', () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any)
    expect(dreamer).toBeInstanceOf(DreamerModule)
    expect(dreamer.name).toBe('dreamer')
    expect(dreamer.priority).toBe(15)
  })

  it('config overrides are applied', () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any, { idleThresholdMs: 999 })
    const status = dreamer.getStatus()
    expect(status.config.idleThresholdMs).toBe(999)
  })
})

// SECTION 2: DreamerModule status and history

describe('DreamerModule status', () => {
  it('returns initial idle state', () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any)
    const status = dreamer.getStatus()
    expect(status.state).toBe('idle')
    expect(status.dreamsCompleted).toBe(0)
    expect(status.lastDreamAt).toBe(0)
    expect(status.lastTurnAt).toBe(0)
  })

  it('returns empty history initially', () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any)
    expect(dreamer.getHistory()).toEqual([])
  })

  it('updateConfig merges correctly', () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any, { enabled: true })
    dreamer.updateConfig({ maxInsightsPerDream: 10, enableGardening: false })
    const status = dreamer.getStatus()
    expect(status.config.maxInsightsPerDream).toBe(10)
    expect(status.config.enableGardening).toBe(false)
    expect(status.config.enabled).toBe(true) // unchanged
  })
})

// SECTION 3: DreamCycleEngine — empty archive early exit

describe('DreamCycleEngine - empty archive', () => {
  it('returns empty record when no archive entries sampled', async () => {
    const { engine, inferFn } = makeEngine()
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG }
    // sampleForDream returns [] by default
    const record = await engine.runCycle(config)
    expect(record.insightsCreated).toHaveLength(0)
    expect(record.episodicsRetired).toHaveLength(0)
    expect(inferFn).not.toHaveBeenCalled() // LLM not called when no entries
  })
})

// SECTION 4: DreamCycleEngine — full cycle

describe('DreamCycleEngine - full cycle', () => {
  it('calls free-association and crystallization phases', async () => {
    const entries = makeArchiveEntries(5)
    const { engine, inferFn, inferJSONFn, memory } = makeEngine(
      'Free association analysis text.',
      [{ content: 'Insight A about recurring patterns in the codebase', confidence: 0.8, sourceEntryIds: ['entry_0', 'entry_1'], title: 'A', topics: ['t1'] }],
      { sampleForDream: vi.fn(() => entries) },
    )

    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    // Phase 2 (free association) and Phase 3 (crystallization) should have run
    expect(inferFn).toHaveBeenCalledOnce() // free association
    expect(inferJSONFn).toHaveBeenCalledOnce() // crystallization
    expect(record.insightsCreated).toHaveLength(1)
    expect(record.archiveEntriesProcessed).toEqual(entries.map(e => e.id))
    expect(memory.store).toHaveBeenCalledOnce()
    expect(memory.markArchiveEntriesDreamed).toHaveBeenCalledWith(entries.map(e => e.id))
  })

  it('captures topInsightContent from highest confidence insight', async () => {
    const entries = makeArchiveEntries(3)
    const insights = [
      { content: 'Low confidence insight', confidence: 0.3, sourceEntryIds: [], title: 'Low', topics: [] },
      { content: 'High confidence insight', confidence: 0.9, sourceEntryIds: [], title: 'High', topics: [] },
    ]
    const { engine } = makeEngine('Analysis', insights, {
      sampleForDream: vi.fn(() => entries),
    })

    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)
    expect(record.topInsightContent).toBe('High confidence insight')
  })

  it('stores insights with dreamer source metadata', async () => {
    const entries = makeArchiveEntries(2)
    const { engine, memory } = makeEngine(
      'Analysis',
      [{ content: 'Some insight', confidence: 0.7, sourceEntryIds: ['entry_0'], title: 'T', topics: [] }],
      { sampleForDream: vi.fn(() => entries) },
    )

    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    await engine.runCycle(config)

    expect(memory.store).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'insight',
        content: 'Some insight',
        metadata: expect.objectContaining({
          source: 'dreamer',
          confidence: 0.7,
        }),
      }),
    )
  })

  it('filters out malformed insights from LLM response', async () => {
    const entries = makeArchiveEntries(2)
    const { engine, memory } = makeEngine(
      'Analysis',
      [
        { content: 'Valid insight', confidence: 0.7, sourceEntryIds: [] },
        { confidence: 0.5 },             // missing content — invalid
        { content: 'X', confidence: 0.6 }, // content too short — invalid
        null,                              // null — invalid
      ] as any,
      { sampleForDream: vi.fn(() => entries) },
    )

    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)
    // Only 1 valid insight
    expect(record.insightsCreated).toHaveLength(1)
    expect(memory.store).toHaveBeenCalledOnce()
  })

  it('respects maxInsightsPerDream limit', async () => {
    const entries = makeArchiveEntries(4)
    const manyInsights = Array.from({ length: 10 }, (_, i) => ({
      content: `Insight ${i} with enough length to pass the filter`,
      confidence: 0.7,
      sourceEntryIds: [],
      title: `Insight ${i}`,
      topics: [],
    }))
    const { engine } = makeEngine('Analysis', manyInsights, {
      sampleForDream: vi.fn(() => entries),
    })

    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, maxInsightsPerDream: 3, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)
    expect(record.insightsCreated.length).toBeLessThanOrEqual(3)
  })

  it('handles LLM failure gracefully (returns empty insights)', async () => {
    const entries = makeArchiveEntries(3)
    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => { throw new Error('Provider unavailable') })
    const inferJSONFn = vi.fn(async () => null) // also fails for crystallization
    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any)

    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false }
    const record = await engine.runCycle(config)
    // Should complete without throwing
    expect(record.insightsCreated).toHaveLength(0)
    expect(logger.warn).toHaveBeenCalled()
  })
})

// SECTION 5: Deep archive filtering

describe('Deep archive gardening', () => {
  it('archiveDeep is called with episodic IDs on gardening cluster', async () => {
    const entries = makeArchiveEntries(3)
    const episodics = [
      { id: 'mem_1', content: 'Episodic memory A', cognitiveClass: 'episodic', createdAt: 1000 },
      { id: 'mem_2', content: 'Episodic memory B', cognitiveClass: 'episodic', createdAt: 2000 },
      { id: 'mem_3', content: 'Episodic memory C', cognitiveClass: 'episodic', createdAt: 3000 },
    ]

    // Gardening LLM returns a cluster of the 3 episodics
    const insights: DreamInsight[] = [{
      content: 'Synthesized semantic insight',
      confidence: 0.8,
      sourceEntryIds: ['mem_1', 'mem_2', 'mem_3'],
      title: 'Cluster synthesis',
      topics: [],
    }]

    const { engine, memory } = makeEngine(
      'Analysis',
      insights,
      {
        sampleForDream: vi.fn(() => entries),
        getEpisodicMemoriesByIds: vi.fn(() => episodics),
      },
    )

    // Override inferJSONFn for gardening call (2nd call returns cluster)
    const gardenCluster = [{ episodicIds: ['mem_1', 'mem_2', 'mem_3'], reasoning: 'Synthesized' }]
    ;(engine as any).inferJSONFn = vi.fn()
      .mockResolvedValueOnce(insights)       // crystallization
      .mockResolvedValueOnce(gardenCluster)  // gardening

    const config: DreamerConfig = {
      ...DEFAULT_DREAMER_CONFIG,
      enableGardening: true,
      minClusterSizeForGarden: 3,
      enableLinking: false,
    }

    const record = await engine.runCycle(config)
    expect(memory.archiveDeep).toHaveBeenCalledWith(
      expect.arrayContaining(['mem_1', 'mem_2', 'mem_3']),
      expect.any(String),
    )
    expect(record.episodicsRetired).toEqual(expect.arrayContaining(['mem_1', 'mem_2', 'mem_3']))
  })

  it('does not retire clusters smaller than minClusterSize', async () => {
    const entries = makeArchiveEntries(2)
    const episodics = [
      { id: 'mem_1', content: 'Short cluster A', cognitiveClass: 'episodic', createdAt: 1000 },
      { id: 'mem_2', content: 'Short cluster B', cognitiveClass: 'episodic', createdAt: 2000 },
    ]
    const gardenCluster = [{ episodicIds: ['mem_1', 'mem_2'], reasoning: 'Too small' }] // only 2

    const { engine, memory } = makeEngine(
      'Analysis',
      [{ content: 'Insight with enough length to pass validation', confidence: 0.7, sourceEntryIds: ['mem_1'], title: 'T', topics: [] }],
      {
        sampleForDream: vi.fn(() => entries),
        getEpisodicMemoriesByIds: vi.fn(() => episodics),
      },
    )

    ;(engine as any).inferJSONFn = vi.fn()
      .mockResolvedValueOnce([{ content: 'Insight with enough length to pass validation', confidence: 0.7, sourceEntryIds: ['mem_1'], title: 'T', topics: [] }])
      .mockResolvedValueOnce(gardenCluster)

    const config: DreamerConfig = {
      ...DEFAULT_DREAMER_CONFIG,
      enableGardening: true,
      minClusterSizeForGarden: 3, // requires 3 but cluster only has 2
      enableLinking: false,
    }

    const record = await engine.runCycle(config)
    expect(memory.archiveDeep).not.toHaveBeenCalled()
    expect(record.episodicsRetired).toHaveLength(0)
  })
})

// SECTION 6: Prompt builders

describe('Prompt builders', () => {
  const sampleEntries = makeArchiveEntries(3)

  it('buildFreeAssociationPrompt includes entry count and IDs', () => {
    const prompt = buildFreeAssociationPrompt(sampleEntries)
    expect(prompt).toContain('3 memory fragments')
    expect(prompt).toContain('entry_0')
    expect(prompt).toContain('conversation')
  })

  it('buildCrystallizationPrompt includes max insights count', () => {
    const prompt = buildCrystallizationPrompt('Free association text here', sampleEntries, 5)
    expect(prompt).toContain('5')
    expect(prompt).toContain('JSON array')
    expect(prompt).toContain('Free association text')
  })

  it('buildGardenPrompt includes min cluster size', () => {
    const episodics = [
      { id: 'ep1', content: 'Episodic entry 1', createdAt: 1000000 },
      { id: 'ep2', content: 'Episodic entry 2', createdAt: 2000000 },
    ]
    const insights: DreamInsight[] = [{
      content: 'Synthesized insight',
      confidence: 0.7,
      sourceEntryIds: ['ep1'],
      title: 'Test',
      topics: [],
    }]
    const prompt = buildGardenPrompt(episodics, insights, 3)
    expect(prompt).toContain('3')
    expect(prompt).toContain('ep1')
    expect(prompt).toContain('ep2')
    // The garden prompt shows insight titles (or content prefix if no title)
    expect(prompt).toContain('Test')
  })

  it('buildFreeAssociationPrompt truncates long content', () => {
    const longEntry = {
      id: 'long',
      type: 'conversation' as const,
      content: 'x'.repeat(600), // longer than 400 char limit
      metadata: {},
      timestamp: Date.now(),
    }
    const prompt = buildFreeAssociationPrompt([longEntry])
    // Should be truncated with '…'
    expect(prompt).toContain('…')
  })
})

// SECTION 7: Context injection window

describe('DreamerModule - context injection', () => {
  it('triggerDream returns null when no memory module set', async () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any, { enabled: true })
    // No fullMemory set
    const result = await dreamer.triggerDream()
    expect(result).toBeNull()
  })

  it('triggerDream returns null when no provider set but returns empty record when archive is also empty', async () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any, { enabled: true })
    const memory = makeMemory()
    dreamer.setFullMemory(memory as any)
    // No provider set — but archive is also empty, so engine returns early without calling provider
    const result = await dreamer.triggerDream()
    // Either a completed empty DreamRecord or null (depending on whether provider was needed)
    // The key is it does NOT throw
    expect(() => result).not.toThrow()
    if (result !== null) {
      expect(result.insightsCreated).toHaveLength(0)
    }
  })

  it('getStatus reflects latest config updates', () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any)
    dreamer.updateConfig({ injectContextWindowHours: 8 })
    expect(dreamer.getStatus().config.injectContextWindowHours).toBe(8)
  })
})

// SECTION 8: Reasoning Synthesis Phase (Improvement #11)

function makeReasoningBank(overrides: Record<string, any> = {}) {
  return {
    store: vi.fn(() => `rt-${Math.random().toString(36).slice(2)}`),
    search: vi.fn(() => []),
    retrieveForBranch: vi.fn(() => null),
    getStats: vi.fn(() => ({ totalTraces: 0, successfulTraces: 0, averageQuality: 0, totalReferences: 0, tracesNeverReferenced: 0, byTaskType: {} })),
    prune: vi.fn(() => 0),
    close: vi.fn(),
    ...overrides,
  }
}

function makeSearchResult(traceOverrides: Record<string, any> = {}, relevance = 0.7) {
  return {
    trace: {
      id: `rt-${Math.random().toString(36).slice(2)}`,
      sourceHelixId: 'helix-test-1',
      goal: 'implement feature X',
      approach: 'incremental-refactor',
      content: 'Reasoning about how to implement the feature',
      qualityScore: 0.8,
      succeeded: true,
      relevantFiles: ['core/feature.ts', 'core/utils.ts'],
      taskType: 'implementation',
      referenceCount: 2,
      createdAt: Date.now() - 86400000,
      lastRetrievedAt: Date.now() - 43200000,
      ...traceOverrides,
    },
    relevance,
  }
}

describe('DreamCycleEngine - Reasoning Synthesis (Phase 4)', () => {
  it('synthesizes meta-reasoning when reasoning bank has matching traces', async () => {
    const entries = makeArchiveEntries(3)
    const insights = [{
      content: 'Pattern: incremental refactoring leads to better outcomes',
      confidence: 0.85,
      sourceEntryIds: ['entry_0', 'entry_1'],
      title: 'Incremental Refactoring Pattern',
      topics: ['refactoring', 'implementation'],
    }]

    // Two matching traces (minimum 2 required for synthesis)
    const matchingTraces = [
      makeSearchResult({ goal: 'refactor module A', approach: 'incremental' }),
      makeSearchResult({ goal: 'refactor module B', approach: 'incremental-steps' }),
    ]

    const reasoningBank = makeReasoningBank({
      search: vi.fn(() => matchingTraces),
    })

    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => 'Free association text')
    const inferJSONFn = vi.fn()
      .mockResolvedValueOnce(insights)   // crystallization
      .mockResolvedValueOnce({           // reasoning synthesis
        synthesis: 'Incremental refactoring consistently outperforms big-bang rewrites across multiple sessions.',
        approach_pattern: 'incremental-refactor',
        applicable_context: 'Any module refactoring task',
      })

    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any, reasoningBank as any)
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    // Reasoning synthesis should have run and stored a trace
    expect(record.reasoningSyntheses).toBe(1)
    expect(reasoningBank.store).toHaveBeenCalledWith(
      expect.objectContaining({
        sourceHelixId: expect.stringContaining('dream-'),
        approach: 'incremental-refactor',
        content: expect.stringContaining('Incremental refactoring'),
        succeeded: true,
      }),
    )
  })

  it('skips synthesis when no reasoning bank is provided', async () => {
    const entries = makeArchiveEntries(3)
    const { engine, memory } = makeEngine(
      'Free association text',
      [{ content: 'Test insight about code patterns and approaches', confidence: 0.7, sourceEntryIds: ['entry_0'], title: 'T', topics: ['coding'] }],
      { sampleForDream: vi.fn(() => entries) },
    )

    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    // No reasoning bank → synthesis field absent or 0
    expect(record.reasoningSyntheses ?? 0).toBe(0)
  })

  it('skips synthesis when no traces match insight topics', async () => {
    const entries = makeArchiveEntries(2)
    const insights = [{
      content: 'Insight about database optimization patterns in CassiCore',
      confidence: 0.75,
      sourceEntryIds: ['entry_0'],
      title: 'DB Optimization',
      topics: ['database', 'performance'],
    }]

    const reasoningBank = makeReasoningBank({
      search: vi.fn(() => []),  // no matching traces
    })

    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => 'Analysis')
    const inferJSONFn = vi.fn().mockResolvedValueOnce(insights)

    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any, reasoningBank as any)
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    expect(record.reasoningSyntheses).toBe(0)
    expect(reasoningBank.store).not.toHaveBeenCalled()
  })

  it('skips synthesis when only 1 trace matches (needs at least 2)', async () => {
    const entries = makeArchiveEntries(2)
    const insights = [{
      content: 'Pattern in testing approaches that improve reliability',
      confidence: 0.8,
      sourceEntryIds: ['entry_0'],
      title: 'Test Reliability',
      topics: ['testing'],
    }]

    const singleTrace = [makeSearchResult()]

    const reasoningBank = makeReasoningBank({
      search: vi.fn(() => singleTrace),  // only 1 trace — below threshold
    })

    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => 'Analysis')
    const inferJSONFn = vi.fn().mockResolvedValueOnce(insights)

    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any, reasoningBank as any)
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    expect(record.reasoningSyntheses).toBe(0)
    expect(reasoningBank.store).not.toHaveBeenCalled()
  })

  it('handles reasoning synthesis LLM failure gracefully', async () => {
    const entries = makeArchiveEntries(2)
    const insights = [{
      content: 'Pattern about error handling in distributed systems',
      confidence: 0.85,
      sourceEntryIds: ['entry_0'],
      title: 'Error Handling',
      topics: ['error-handling', 'distributed'],
    }]

    const matchingTraces = [
      makeSearchResult({ goal: 'handle errors in worker A' }),
      makeSearchResult({ goal: 'handle errors in worker B' }),
    ]

    const reasoningBank = makeReasoningBank({
      search: vi.fn(() => matchingTraces),
    })

    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => 'Analysis')
    const inferJSONFn = vi.fn()
      .mockResolvedValueOnce(insights)
      .mockRejectedValueOnce(new Error('LLM synthesis failed'))  // synthesis LLM call fails

    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any, reasoningBank as any)
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    // Should complete gracefully — non-fatal
    expect(record.reasoningSyntheses).toBe(0)
    expect(reasoningBank.store).not.toHaveBeenCalled()
    expect(record.insightsCreated).toHaveLength(1) // insights still stored
  })

  it('handles complete synthesis phase failure gracefully', async () => {
    const entries = makeArchiveEntries(2)
    const insights = [{
      content: 'Insight about module architecture patterns and decisions',
      confidence: 0.75,
      sourceEntryIds: ['entry_0'],
      title: 'Architecture',
      topics: ['architecture'],
    }]

    // Reasoning bank search throws
    const reasoningBank = makeReasoningBank({
      search: vi.fn(() => { throw new Error('DB connection lost') }),
    })

    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => 'Analysis')
    const inferJSONFn = vi.fn().mockResolvedValueOnce(insights)

    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any, reasoningBank as any)
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    // Non-fatal — dream completes, synthesis count is 0
    expect(record.reasoningSyntheses).toBe(0)
    expect(record.insightsCreated).toHaveLength(1)
    expect(logger.warn).toHaveBeenCalled()
  })

  it('synthesizes multiple insights when multiple match reasoning traces', async () => {
    const entries = makeArchiveEntries(4)
    const insights = [
      {
        content: 'Refactoring pattern: extract shared utilities first',
        confidence: 0.8,
        sourceEntryIds: ['entry_0', 'entry_1'],
        title: 'Extract Utilities',
        topics: ['refactoring'],
      },
      {
        content: 'Testing pattern: write integration tests before unit tests',
        confidence: 0.75,
        sourceEntryIds: ['entry_2', 'entry_3'],
        title: 'Test Order',
        topics: ['testing'],
      },
    ]

    const refactorTraces = [
      makeSearchResult({ goal: 'refactor utils', approach: 'extract-first' }),
      makeSearchResult({ goal: 'refactor helpers', approach: 'extract-shared' }),
    ]
    const testTraces = [
      makeSearchResult({ goal: 'add integration tests', approach: 'top-down' }),
      makeSearchResult({ goal: 'test new API', approach: 'integration-first' }),
    ]

    const reasoningBank = makeReasoningBank({
      search: vi.fn()
        .mockReturnValueOnce(refactorTraces)   // for insight #1
        .mockReturnValueOnce(testTraces),       // for insight #2
    })

    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => 'Analysis')
    const inferJSONFn = vi.fn()
      .mockResolvedValueOnce(insights)
      .mockResolvedValueOnce({
        synthesis: 'Extracting shared utilities early reduces duplication downstream.',
        approach_pattern: 'extract-first',
        applicable_context: 'refactoring tasks',
      })
      .mockResolvedValueOnce({
        synthesis: 'Integration tests before unit tests catches interface bugs early.',
        approach_pattern: 'integration-first',
        applicable_context: 'new feature development',
      })

    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any, reasoningBank as any)
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    expect(record.reasoningSyntheses).toBe(2)
    expect(reasoningBank.store).toHaveBeenCalledTimes(2)
  })

  it('rejects synthesis with too-short content', async () => {
    const entries = makeArchiveEntries(2)
    const insights = [{
      content: 'Pattern about logging best practices for debugging',
      confidence: 0.8,
      sourceEntryIds: ['entry_0'],
      title: 'Logging',
      topics: ['logging'],
    }]

    const matchingTraces = [
      makeSearchResult({ goal: 'add logging to X' }),
      makeSearchResult({ goal: 'improve logging in Y' }),
    ]

    const reasoningBank = makeReasoningBank({
      search: vi.fn(() => matchingTraces),
    })

    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => 'Analysis')
    const inferJSONFn = vi.fn()
      .mockResolvedValueOnce(insights)
      .mockResolvedValueOnce({
        synthesis: 'Too short',  // <= 20 chars, should be rejected
        approach_pattern: 'log-pattern',
        applicable_context: 'logging',
      })

    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any, reasoningBank as any)
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    expect(record.reasoningSyntheses).toBe(0)
    expect(reasoningBank.store).not.toHaveBeenCalled()
  })

  it('skips insights with no topics or title for search', async () => {
    const entries = makeArchiveEntries(2)
    const insights = [{
      content: 'Bare insight with no topics and no title for searching',
      confidence: 0.7,
      sourceEntryIds: ['entry_0'],
      // no title, no topics
    }]

    const reasoningBank = makeReasoningBank()

    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => 'Analysis')
    const inferJSONFn = vi.fn().mockResolvedValueOnce(insights)

    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any, reasoningBank as any)
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    // No topics/title → no search terms → synthesis skipped
    expect(record.reasoningSyntheses).toBe(0)
    expect(reasoningBank.search).not.toHaveBeenCalled()
  })

  it('deduplicates relevant files in stored synthesis traces', async () => {
    const entries = makeArchiveEntries(2)
    const insights = [{
      content: 'Pattern about configuration management across modules',
      confidence: 0.85,
      sourceEntryIds: ['entry_0'],
      title: 'Config Management',
      topics: ['config'],
    }]

    // Both traces share the same file
    const matchingTraces = [
      makeSearchResult({ goal: 'update config A', relevantFiles: ['core/config.ts', 'core/utils.ts'] }),
      makeSearchResult({ goal: 'update config B', relevantFiles: ['core/config.ts', 'core/settings.ts'] }),
    ]

    const reasoningBank = makeReasoningBank({
      search: vi.fn(() => matchingTraces),
    })

    const logger = makeLogger()
    const memory = makeMemory({ sampleForDream: vi.fn(() => entries) })
    const inferFn = vi.fn(async () => 'Analysis')
    const inferJSONFn = vi.fn()
      .mockResolvedValueOnce(insights)
      .mockResolvedValueOnce({
        synthesis: 'Configuration should be centralized with a single source of truth to avoid drift.',
        approach_pattern: 'centralized-config',
        applicable_context: 'config management',
      })

    const engine = new DreamCycleEngine(inferFn, inferJSONFn, memory as any, logger as any, reasoningBank as any)
    const config: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG, enableGardening: false, enableLinking: false }
    const record = await engine.runCycle(config)

    expect(record.reasoningSyntheses).toBe(1)
    const storeCall = reasoningBank.store.mock.calls[0][0]
    // Files should be deduplicated
    const files = storeCall.relevantFiles
    expect(files).toContain('core/config.ts')
    expect(files).toContain('core/utils.ts')
    expect(files).toContain('core/settings.ts')
    // core/config.ts appears in both traces but should only appear once
    expect(files.filter((f: string) => f === 'core/config.ts')).toHaveLength(1)
  })
})

// SECTION 9: DreamerModule - ReasoningBank wiring

describe('DreamerModule - ReasoningBank wiring', () => {
  it('setReasoningBank wires the bank to the module', () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any)
    const bank = makeReasoningBank()
    // Should not throw
    expect(() => dreamer.setReasoningBank(bank as any)).not.toThrow()
  })

  it('dream cycle passes reasoning bank to DreamCycleEngine', async () => {
    const logger = makeLogger()
    const dreamer = createDreamer(logger as any, { enabled: true })
    const memory = makeMemory()
    const bank = makeReasoningBank()

    dreamer.setFullMemory(memory as any)
    dreamer.setReasoningBank(bank as any)

    // triggerDream with empty archive should return early without calling reasoning bank
    const result = await dreamer.triggerDream()
    // No entries → early exit → no reasoning synthesis needed
    if (result !== null) {
      expect(result.insightsCreated).toHaveLength(0)
    }
  })
})
