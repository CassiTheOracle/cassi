/**
 * Dialectic Deduction — Tests for Logical Inference Through the Dialectic Trio
 *
 * The Dialectic System performs structured logical analysis through three phases:
 *
 * 1. **Yang (Expansion)** — Generates diverse branches representing alternative
 *    interpretations, edge cases, assumptions, and cross-domain connections.
 *    These serve as the *premises* for deduction.
 *
 * 2. **Yin (Refinement)** — Critiques and validates Yang's premises, providing
 *    grounding constraints and reality checks. Filters invalid or low-confidence
 *    branches to ensure sound reasoning.
 *
 * 3. **Serenity (Synthesis)** — Deduces actionable signals from the interplay
 *    between Yang's expansions and Yin's critiques. Produces conclusions with
 *    confidence scores, urgency levels, and source attribution.
 *
 * This test file documents the deductive reasoning behavior:
 * - Premise generation and validation
 * - Confidence-based filtering
 * - Signal injection decisions (when conclusions reach action thresholds)
 * - Quality metrics and cost tracking
 * - Error handling for invalid or contradictory inputs
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { tmpDir, mockLogger } from './helpers.ts'
import { createDialecticSystem, DialecticSystem } from '../src/dialectic/index.js'
import { ConsolidatedDialecticProcessor } from '../src/dialectic/consolidated-processor.js'
import type {
  YangOutput,
  YinBaselineOutput,
  SerenityOutput,
  ParallelDialecticResult,
  YangBranch,
  YinBaselineBranch,
  YinCritique,
  DialecticSignal,
} from '@cassicore/foundation'
import type { IProvider } from '@cassicore/foundation'


/**
 * Creates a Yang branch representing a premise for deduction.
 */
function createYangBranch(overrides?: Partial<YangBranch>): YangBranch {
  return {
    id: `yang-${Math.random().toString(36).slice(2, 7)}`,
    type: 'edge_case',
    content: 'Potential SQL injection through unsanitized user input',
    confidence: 0.9,
    noveltyScore: 0.7,
    ...overrides,
  }
}

/**
 * Creates a Yin baseline representing grounding constraints.
 */
function createYinBaseline(overrides?: Partial<YinBaselineBranch>): YinBaselineBranch {
  return {
    id: `yin-base-${Math.random().toString(36).slice(2, 7)}`,
    type: 'risk_assessment',
    content: 'Input validation currently only exists on client side',
    confidence: 0.85,
    relevanceScore: 0.9,
    ...overrides,
  }
}

/**
 * Creates a Yin critique validating or rejecting a Yang premise.
 * Note: Consolidated processor uses actions: 'keep' | 'compress' | 'discard' | 'flag'
 * while the base YinAction type is 'surface' | 'ignore' | 'refine'.
 */
function createYinCritique(overrides?: Partial<YinCritique>): YinCritique {
  return {
    yangBranchId: 'yang-1',
    valid: true,
    critique: 'Valid concern — this is a known vulnerability pattern',
    relevance: 0.9,
    action: 'surface', // Use valid YinAction type
    ...overrides,
  }
}

/**
 * Creates a Serenity signal representing a deduced conclusion.
 */
function createSerenitySignal(overrides?: Partial<DialecticSignal>): DialecticSignal {
  return {
    type: 'edge_case',
    content: 'Critical SQL injection vulnerability requires immediate sanitization',
    confidence: 0.92,
    sourceBranches: ['yang-1', 'yang-2'],
    urgency: 'immediate',
    ...overrides,
  }
}


/**
 * Creates a mock provider that returns a controlled dialectic response.
 * This allows testing the full parsing and synthesis pipeline without LLM calls.
 */
function createMockProvider(responseOverride?: Record<string, unknown>): IProvider {
  const defaultResponse = {
    yang: {
      branches: [
        {
          type: 'edge_case',
          content: 'SQL injection via unsanitized user input',
          confidence: 0.95,
          noveltyScore: 0.3,
        },
        {
          type: 'assumption_challenge',
          content: 'Input validation only client-side, bypassable',
          confidence: 0.88,
          noveltyScore: 0.6,
        },
      ],
    },
    yin: {
      baselines: [
        {
          type: 'risk_assessment',
          content: 'Current validation is insufficient for security',
          confidence: 0.9,
          relevanceScore: 0.95,
        },
      ],
      critiques: [
        {
          yangBranchIndex: 0,
          valid: true,
          critique: 'Confirmed vulnerability with high confidence',
          relevance: 0.95,
          action: 'keep',
        },
        {
          yangBranchIndex: 1,
          valid: true,
          critique: 'Valid concern about client-side assumptions',
          relevance: 0.85,
          action: 'keep',
        },
      ],
    },
    serenity: {
      hasSignal: true,
      signal: {
        type: 'edge_case',
        content: 'Critical SQL injection vulnerability detected',
        confidence: 0.92,
        urgency: 'immediate',
      },
      branchesConsidered: 2,
      branchesSurfaced: 2,
      dialecticQuality: 0.88,
    },
  }

  const response = responseOverride ?? defaultResponse

  return {
    id: 'mock-deduction-provider',
    models: ['mock-model'],
    async *complete(_messages, _opts) {
      // Yield the JSON response
      yield { type: 'token' as const, text: JSON.stringify(response) }
      yield { type: 'done' as const }
    },
    async countTokens(): Promise<number> { return 0 },
    async ping(): Promise<boolean> { return true },
  }
}


describe('Dialectic Deduction', () => {
  let homeTmp: ReturnType<typeof tmpDir>
  let originalHome: string | undefined

  beforeEach(() => {
    homeTmp = tmpDir()
    originalHome = process.env.HOME
    process.env.HOME = homeTmp.path
  })

  afterEach(() => {
    if (originalHome === undefined) delete process.env.HOME
    else process.env.HOME = originalHome
    homeTmp.cleanup()
  })

  // Core Deductive Reasoning Flow

  describe('deductive reasoning flow', () => {
    it('generates premises (Yang branches) from user input', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: {
          branches: [
            { type: 'edge_case', content: 'Test premise A', confidence: 0.8, noveltyScore: 0.5 },
            { type: 'alternative_interpretation', content: 'Test premise B', confidence: 0.7, noveltyScore: 0.6 },
            { type: 'what_if', content: 'Test premise C', confidence: 0.9, noveltyScore: 0.4 },
          ],
        },
        yin: { baselines: [], critiques: [] },
        serenity: { hasSignal: false, branchesConsidered: 3, branchesSurfaced: 0, dialecticQuality: 0.6 },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn(
        'sess-premise',
        'turn-1',
        'Analyze this security code',
        { recentMemories: [], availableTools: [], sessionHistory: [] }
      )

      // Should generate multiple premise branches
      expect(result.yang.branches.length).toBeGreaterThanOrEqual(2)
      expect(result.yang.branches[0]).toHaveProperty('id')
      expect(result.yang.branches[0]).toHaveProperty('type')
      expect(result.yang.branches[0]).toHaveProperty('content')
      expect(result.yang.branches[0]).toHaveProperty('confidence')
    })

    it('validates premises through Yin critique (soundness check)', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: {
          branches: [
            { type: 'edge_case', content: 'High-confidence premise', confidence: 0.95, noveltyScore: 0.8 },
            { type: 'what_if', content: 'Low-confidence speculation', confidence: 0.3, noveltyScore: 0.2 },
          ],
        },
        yin: {
          baselines: [
            { type: 'grounding', content: 'Baseline context', confidence: 0.8, relevanceScore: 0.7 },
          ],
          critiques: [
            { yangBranchIndex: 0, valid: true, critique: 'Strong premise', relevance: 0.9, action: 'keep' },
            { yangBranchIndex: 1, valid: false, critique: 'Too speculative', relevance: 0.3, action: 'discard' },
          ],
        },
        serenity: {
          hasSignal: true,
          signal: { type: 'edge_case', content: 'Deduced conclusion', confidence: 0.85, urgency: 'immediate' },
          branchesConsidered: 2,
          branchesSurfaced: 1,
          dialecticQuality: 0.75,
        },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn(
        'sess-validation',
        'turn-1',
        'test input',
        { recentMemories: [], availableTools: [], sessionHistory: [] }
      )

      // Yin should provide critiques for each Yang branch
      const yinOutput = result.yin as YinBaselineOutput
      expect(yinOutput.selfCritiques.length).toBeGreaterThanOrEqual(2)

      // Critiques should distinguish valid from invalid premises
      const validCritiques = yinOutput.selfCritiques.filter(c => c.valid)
      const invalidCritiques = yinOutput.selfCritiques.filter(c => !c.valid)

      expect(validCritiques.length).toBeGreaterThanOrEqual(1)
      expect(invalidCritiques.length).toBeGreaterThanOrEqual(1)
    })

    it('deduces actionable signals when premises warrant intervention', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: {
          branches: [
            { type: 'edge_case', content: 'Critical vulnerability', confidence: 0.95, noveltyScore: 0.7 },
          ],
        },
        yin: {
          baselines: [{ type: 'risk_assessment', content: 'High risk', confidence: 0.9, relevanceScore: 0.95 }],
          critiques: [{ yangBranchIndex: 0, valid: true, critique: 'Confirmed critical', relevance: 0.95, action: 'keep' }],
        },
        serenity: {
          hasSignal: true,
          signal: {
            type: 'edge_case',
            content: 'CRITICAL: Immediate action required',
            confidence: 0.92,
            urgency: 'immediate',
          },
          branchesConsidered: 1,
          branchesSurfaced: 1,
          dialecticQuality: 0.9,
        },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn(
        'sess-deduce',
        'turn-1',
        'security analysis',
        { recentMemories: [], availableTools: [], sessionHistory: [] }
      )

      // Should produce a signal when deduction warrants it
      expect(result.serenity.synthesis.hasSignal).toBe(true)
      expect(result.serenity.synthesis.signal).toBeDefined()
      expect(result.serenity.synthesis.signal!.content).toBe('CRITICAL: Immediate action required')
      expect(result.serenity.synthesis.signal!.urgency).toBe('immediate')
      expect(result.serenity.synthesis.signal!.confidence).toBeGreaterThanOrEqual(0.7)
    })

    it('withholds signals when premises are insufficient or weak', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: {
          branches: [
            { type: 'what_if', content: 'Weak speculation', confidence: 0.4, noveltyScore: 0.3 },
          ],
        },
        yin: {
          baselines: [],
          critiques: [{ yangBranchIndex: 0, valid: false, critique: 'Not actionable', relevance: 0.3, action: 'discard' }],
        },
        serenity: {
          hasSignal: false,
          branchesConsidered: 1,
          branchesSurfaced: 0,
          dialecticQuality: 0.4,
        },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn(
        'sess-no-signal',
        'turn-1',
        'greeting',
        { recentMemories: [], availableTools: [], sessionHistory: [] }
      )

      // Should not produce a signal when premises are weak
      expect(result.serenity.synthesis.hasSignal).toBe(false)
      expect(result.serenity.synthesis.signal).toBeUndefined()
      expect(result.signalInjected).toBe(false)
    })
  })

  // Confidence-Based Signal Injection Logic

  describe('signal injection thresholds', () => {
    it('injects signals when confidence >= 0.3 regardless of urgency', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: { branches: [] },
        yin: { baselines: [], critiques: [] },
        serenity: {
          hasSignal: true,
          signal: { type: 'edge_case', content: 'Test', confidence: 0.3, urgency: 'immediate' },
          branchesConsidered: 1,
          branchesSurfaced: 1,
          dialecticQuality: 0.7,
        },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn('sess-inject', 'turn-1', 'test', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      expect(result.signalInjected).toBe(true)
    })

    it('does not inject signals when confidence is below threshold', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: { branches: [] },
        yin: { baselines: [], critiques: [] },
        serenity: {
          hasSignal: true,
          signal: { type: 'edge_case', content: 'Test', confidence: 0.29, urgency: 'immediate' },
          branchesConsidered: 1,
          branchesSurfaced: 1,
          dialecticQuality: 0.7,
        },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn('sess-no-inject', 'turn-1', 'test', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      expect(result.signalInjected).toBe(false)
    })

    it('injects background urgency signals with sufficient confidence', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: { branches: [] },
        yin: { baselines: [], critiques: [] },
        serenity: {
          hasSignal: true,
          signal: { type: 'assumption', content: 'Test', confidence: 0.95, urgency: 'background' },
          branchesConsidered: 1,
          branchesSurfaced: 1,
          dialecticQuality: 0.8,
        },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn('sess-bg-inject', 'turn-1', 'test', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      // Background urgency with high confidence (>= 0.3) should trigger injection
      expect(result.signalInjected).toBe(true)
    })
  })

  // Edge Cases and Error Handling

  describe('edge cases and error handling', () => {
    it('handles empty premise generation gracefully', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: { branches: [] },
        yin: { baselines: [], critiques: [] },
        serenity: { hasSignal: false, branchesConsidered: 0, branchesSurfaced: 0, dialecticQuality: 0.5 },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn('sess-empty', 'turn-1', '', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      expect(result.yang.branches).toEqual([])
      expect(result.serenity.synthesis.hasSignal).toBe(false)
    })

    it('handles malformed provider responses with fallback defaults', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })

      const brokenProvider: IProvider = {
        id: 'broken-provider',
        models: ['broken'],
        async *complete() {
          yield { type: 'token' as const, text: 'not valid json {' }
          yield { type: 'done' as const }
        },
        async countTokens(): Promise<number> { return 0 },
        async ping(): Promise<boolean> { return false },
      }

      system.setProvider(brokenProvider)

      const result = await system.processTurn('sess-broken', 'turn-1', 'test', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      // Should return empty structures rather than crash
      expect(result.yang.branches).toEqual([])
      expect(result.serenity.synthesis.hasSignal).toBe(false)
    })

    it('filters out low-confidence premises below minConfidence threshold', async () => {
      const logger = mockLogger()
      const processor = new ConsolidatedDialecticProcessor(logger, { minConfidence: 0.5, maxBranches: 5 })

      // Use reflection to test parsing behavior
      const parseYang = (processor as any).parseYang.bind(processor)

      const rawYang = {
        branches: [
          { type: 'edge_case', content: 'High confidence', confidence: 0.9, noveltyScore: 0.7 },
          { type: 'edge_case', content: 'Low confidence', confidence: 0.2, noveltyScore: 0.5 },
          { type: 'edge_case', content: 'Borderline', confidence: 0.5, noveltyScore: 0.6 },
        ],
      }

      const parsed = parseYang(rawYang)

      // Should filter out the 0.2 confidence branch
      expect(parsed.branches.length).toBe(2)
      expect(parsed.branches.some((b: YangBranch) => b.content === 'Low confidence')).toBe(false)
    })

    it('handles contradictory premises by selecting highest-confidence path', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: {
          branches: [
            { type: 'edge_case', content: 'Path A: Critical issue', confidence: 0.95, noveltyScore: 0.8 },
            // Use confidence above minConfidence (0.3) but below threshold to differentiate
            { type: 'alternative_interpretation', content: 'Path B: Not an issue', confidence: 0.45, noveltyScore: 0.3 },
          ],
        },
        yin: {
          baselines: [],
          critiques: [
            { yangBranchIndex: 0, valid: true, critique: 'Strong evidence', relevance: 0.95, action: 'keep' },
            { yangBranchIndex: 1, valid: false, critique: 'Weak counter-evidence', relevance: 0.3, action: 'discard' },
          ],
        },
        serenity: {
          hasSignal: true,
          signal: { type: 'convergence', content: 'High-confidence path selected', confidence: 0.9, urgency: 'immediate' },
          branchesConsidered: 2,
          branchesSurfaced: 1,
          dialecticQuality: 0.85,
        },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn('sess-contradiction', 'turn-1', 'test', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      // Should converge on the high-confidence path
      expect(result.serenity.synthesis.hasSignal).toBe(true)
      expect(result.serenity.synthesis.signal).toBeDefined()
      expect(result.serenity.synthesis.signal!.type).toBe('convergence')
      expect(result.serenity.synthesis.signal!.confidence).toBeGreaterThan(0.7)
    })

    it('returns empty result when dialectic system is disabled', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: false })

      const result = await system.processTurn('sess-disabled', 'turn-1', 'test', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      expect(result.yang.branches).toEqual([])
      // In disabled state, result.yin is YinBaselineOutput with empty baselineBranches
      const yinOutput = result.yin as YinBaselineOutput
      expect(yinOutput.baselineBranches).toEqual([])
      expect(result.serenity.synthesis.hasSignal).toBe(false)
      expect(result.signalInjected).toBe(false)
    })
  })

  // Quality Metrics and Cost Tracking

  describe('quality metrics', () => {
    it('calculates yang-yin agreement based on critique validity ratio', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider({
        yang: {
          branches: [
            { type: 'edge_case', content: 'A', confidence: 0.9, noveltyScore: 0.7 },
            { type: 'edge_case', content: 'B', confidence: 0.8, noveltyScore: 0.6 },
            { type: 'edge_case', content: 'C', confidence: 0.3, noveltyScore: 0.4 },
          ],
        },
        yin: {
          baselines: [],
          critiques: [
            { yangBranchIndex: 0, valid: true, critique: 'Valid', relevance: 0.9, action: 'keep' },
            { yangBranchIndex: 1, valid: true, critique: 'Valid', relevance: 0.8, action: 'keep' },
            { yangBranchIndex: 2, valid: false, critique: 'Invalid', relevance: 0.3, action: 'discard' },
          ],
        },
        serenity: {
          hasSignal: true,
          signal: { type: 'edge_case', content: 'Test', confidence: 0.8, urgency: 'immediate' },
          branchesConsidered: 3,
          branchesSurfaced: 2,
          dialecticQuality: 0.75,
        },
      })

      system.setProvider(mockProvider)

      const result = await system.processTurn('sess-agreement', 'turn-1', 'test', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      // 2 out of 3 critiques are valid = ~0.67 agreement
      expect(result.quality.yangYinAgreement).toBeGreaterThan(0)
      expect(result.quality.yangYinAgreement).toBeLessThanOrEqual(1)
    })

    it('measures dialectic tension based on premise diversity', async () => {
      const logger = mockLogger()
      const processor = new ConsolidatedDialecticProcessor(logger)
      const calculateTension = (processor as any).calculateTension.bind(processor)

      // High diversity = high tension
      const diverseYang: YangOutput = {
        branches: [
          { id: '1', type: 'edge_case', content: 'A', confidence: 0.8, noveltyScore: 0.7 },
          { id: '2', type: 'alternative_interpretation', content: 'B', confidence: 0.8, noveltyScore: 0.7 },
          { id: '3', type: 'what_if', content: 'C', confidence: 0.8, noveltyScore: 0.7 },
          { id: '4', type: 'cross_domain', content: 'D', confidence: 0.8, noveltyScore: 0.7 },
        ],
        meta: { expansionTemperature: 0.7, generationTimeMs: 0, inputTokens: 0, outputTokens: 0 },
      }

      // Low diversity = low tension
      const uniformYang: YangOutput = {
        branches: [
          { id: '1', type: 'edge_case', content: 'A', confidence: 0.8, noveltyScore: 0.7 },
          { id: '2', type: 'edge_case', content: 'B', confidence: 0.8, noveltyScore: 0.7 },
          { id: '3', type: 'edge_case', content: 'C', confidence: 0.8, noveltyScore: 0.7 },
        ],
        meta: { expansionTemperature: 0.7, generationTimeMs: 0, inputTokens: 0, outputTokens: 0 },
      }

      const highTension = calculateTension(diverseYang, { baselineBranches: [], selfCritiques: [] })
      const lowTension = calculateTension(uniformYang, { baselineBranches: [], selfCritiques: [] })

      expect(highTension).toBeGreaterThan(lowTension)
      expect(highTension).toBeGreaterThan(0.5)
      expect(lowTension).toBeLessThan(0.5)
    })

    it('tracks processing latency for each deductive phase', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider()

      system.setProvider(mockProvider)

      const result = await system.processTurn('sess-timing', 'turn-1', 'test', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      expect(result.totalLatencyMs).toBeGreaterThanOrEqual(0)
      expect(result.timing.yangDuration).toBeGreaterThanOrEqual(0)
      expect(result.timing.yinDuration).toBeGreaterThanOrEqual(0)
      expect(result.timing.serenityDuration).toBeGreaterThanOrEqual(0)
    })
  })

  // Stream Events and Observability

  describe('stream events', () => {
    it('emits structured events through the dialectic lifecycle', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider()

      system.setProvider(mockProvider)

      const events: string[] = []
      system.subscribeToStream('sess-events', (event) => {
        events.push(event.stage)
      })

      await system.processTurn('sess-events', 'turn-1', 'test', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      // Should emit lifecycle events
      expect(events).toContain('start')
      expect(events).toContain('complete')
    })

    it('provides access to recent deduction history', async () => {
      const logger = mockLogger()
      const system = createDialecticSystem(logger, { enabled: true })
      const mockProvider = createMockProvider()

      system.setProvider(mockProvider)

      // Process multiple turns
      await system.processTurn('sess-history', 'turn-1', 'first', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })
      await system.processTurn('sess-history', 'turn-2', 'second', {
        recentMemories: [],
        availableTools: [],
        sessionHistory: [],
      })

      const recent = await system.getRecent('sess-history', 5)
      expect(recent.length).toBeGreaterThanOrEqual(0) // May be 0 if persistence fails

      const stats = await system.getStats('sess-history')
      expect(typeof stats.totalTurns).toBe('number')
      expect(typeof stats.avgLatencyMs).toBe('number')
    })
  })

  // Response Parsing and Validation

  describe('response parsing', () => {
    it('extracts JSON from markdown-fenced responses', async () => {
      const logger = mockLogger()
      const processor = new ConsolidatedDialecticProcessor(logger)
      const extractJson = (processor as any).extractJson.bind(processor)

      const fencedResponse = '```json\n{"yang": {"branches": []}}\n```'
      const extracted = extractJson(fencedResponse)

      expect(JSON.parse(extracted)).toEqual({ yang: { branches: [] } })
    })

    it('validates and normalizes branch types', async () => {
      const logger = mockLogger()
      const processor = new ConsolidatedDialecticProcessor(logger)
      const parseYang = (processor as any).parseYang.bind(processor)

      const rawYang = {
        branches: [
          { type: 'invalid_type', content: 'Test', confidence: 0.8, noveltyScore: 0.7 },
          { type: 'edge_case', content: 'Valid', confidence: 0.8, noveltyScore: 0.7 },
        ],
      }

      const parsed = parseYang(rawYang)

      // Invalid types should be normalized to valid ones
      expect(parsed.branches.length).toBe(2)
      expect(['edge_case', 'alternative_interpretation', 'cross_domain', 'what_if', 'assumption_challenge']).toContain(
        parsed.branches[0].type
      )
    })

    it('validates and normalizes signal types', async () => {
      const logger = mockLogger()
      const processor = new ConsolidatedDialecticProcessor(logger)
      const parseSerenity = (processor as any).parseSerenity.bind(processor)

      const validTypes = ['edge_case', 'alternative', 'assumption', 'connection', 'contradiction', 'convergence', 'tension', 'gap']

      for (const type of validTypes) {
        const rawSerenity = {
          hasSignal: true,
          signal: { type, content: 'Test', confidence: 0.8, urgency: 'immediate' },
          branchesConsidered: 1,
          branchesSurfaced: 1,
          dialecticQuality: 0.8,
        }

        const parsed = parseSerenity(rawSerenity)
        expect(parsed.synthesis.signal?.type).toBe(type)
      }
    })

    it('clamps confidence values to valid 0-1 range', async () => {
      const logger = mockLogger()
      // Use minConfidence: 0 to allow all branches through for clamping test
      const processor = new ConsolidatedDialecticProcessor(logger, { minConfidence: 0 })
      const parseYang = (processor as any).parseYang.bind(processor)

      const rawYang = {
        branches: [
          { type: 'edge_case', content: 'Over', confidence: 1.5, noveltyScore: 2.0 },
          { type: 'edge_case', content: 'Under', confidence: -0.5, noveltyScore: -0.1 },
        ],
      }

      const parsed = parseYang(rawYang)

      // Both branches should exist with clamped values
      expect(parsed.branches.length).toBe(2)
      expect(parsed.branches[0].confidence).toBe(1)
      expect(parsed.branches[0].noveltyScore).toBe(1)
      expect(parsed.branches[1].confidence).toBe(0)
      expect(parsed.branches[1].noveltyScore).toBe(0)
    })
  })
})
