// HOST-WIRED QUARANTINE — NOT part of the counted by-default suite.
//
// Ported from D: tests/parallel-dialectic.test.ts (HEAD@d63358da). Quarantined
// because it imports `ParallelDialecticProcessor` from
// `core/intelligence/dialectic/parallel-processor.ts`, which is DEAD (excluded —
// P5-A table §0). Must be re-pointed to the surviving dialectic surface or the dead
// module revived before promotion. Assertions are NOT weakened.
//

/**
 * Parallel Dialectic Tests
 *
 * Tests for the parallel Yang + Yin execution mode.
 *
 * The Parallel Dialectic runs Yang (creative/expansive) and Yin (critical/refinement)
 * voices concurrently rather than sequentially, reducing latency by ~1.7x while
 * maintaining synthesis quality through Serenity's dual-synthesis capability.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ParallelDialecticProcessor } from '../core/intelligence/dialectic/parallel-processor.js';
import { YinObserver } from '../core/intelligence/dialectic/yin.js';
import { YangObserver } from '../core/intelligence/dialectic/yang.js';
import { Serenity } from '../core/intelligence/dialectic/serenity.js';
import { mockLogger } from './helpers.js';
import type { YangOutput, YinBaselineOutput, SerenityOutput, YangBranch, YinBaselineBranch, YinCritique, DialecticSignal, ParallelDialecticResult, YinOutput } from '../types/dialectic.js';
import type { IProvider } from '../types/runtime.js';

/**
 * Type guard to check if Yin output is a baseline output (parallel mode)
 */
function isYinBaselineOutput(output: YinOutput | YinBaselineOutput): output is YinBaselineOutput {
  return 'baselineBranches' in output;
}

/**
 * Creates a mock provider that returns a delayed response.
 * Used to simulate realistic LLM call timing and test parallel execution.
 */
function createMockProvider(responseText: string, delayMs = 0): IProvider {
  return {
    complete: vi.fn(async function* () {
      if (delayMs > 0) {
        await new Promise(r => setTimeout(r, delayMs));
      }
      yield { type: 'token' as const, text: responseText, tokensUsed: Math.ceil(responseText.length / 4) };
      yield { type: 'done' as const };
    }),
  } as unknown as IProvider;
}

/**
 * Creates a mock provider that returns specific JSON content.
 */
function createJsonProvider(jsonResponse: object, delayMs = 0): IProvider {
  return createMockProvider(JSON.stringify(jsonResponse), delayMs);
}

describe('Parallel Dialectic Execution', () => {
  const logger = mockLogger();

  describe('ParallelDialecticProcessor', () => {
    it('runs Yang (creative) and Yin (critical) voices concurrently to reduce latency', async () => {
      const yangDelay = 50;
      const yinDelay = 50;
      const startTime = Date.now();

      const yangProvider = createJsonProvider({
        branches: [{
          id: 'yang-1',
          type: 'edge_case',
          content: 'Consider memory limits when processing large files',
          confidence: 0.85,
          noveltyScore: 0.7
        }]
      }, yangDelay);

      const yinProvider = createJsonProvider({
        baselineBranches: [{
          id: 'yin-1',
          type: 'constraint',
          content: 'The user has not specified file size constraints',
          confidence: 0.9,
          relevanceScore: 0.8
        }],
        selfCritiques: [{
          yangBranchId: 'yang-1',
          valid: true,
          essence: 'Memory limits are a valid concern',
          critique: 'Relevant to the task at hand',
          relevance: 0.85,
          action: 'surface' as const
        }]
      }, yinDelay);

      const serenityProvider = createJsonProvider({
        hasSignal: true,
        signal: {
          type: 'edge_case',
          content: 'Consider adding file size validation',
          confidence: 0.8,
          urgency: 'immediate'
        },
        branchesConsidered: 2,
        branchesSurfaced: 1,
        dialecticQuality: 0.75
      });

      const processor = new ParallelDialecticProcessor(
        logger,
        { maxWaitMs: 5000, observerTimeoutMs: 3000, partialResultsOnFailure: true, synchronization: 'best-effort' },
        { model: 'test-model', temperature: 0.9, maxBranches: 3 },
        { model: 'test-model', temperature: 0.3 },
        { model: 'test-model', temperature: 0.4 }
      );

      processor.setProvider(yangProvider);

      const streamEvents: Array<{ stage: string; timestamp: number }> = [];
      const emitStreamEvent = (event: { stage: string; timestamp: number }) => {
        streamEvents.push(event);
      };

      // Manually wire the providers by mocking the internal observers
      (processor as any).yang.setProvider(yangProvider);
      (processor as any).yin.setProvider(yinProvider);
      (processor as any).serenity.setProvider(serenityProvider);

      const result = await processor.processTurn(
        'test-session',
        'turn-1',
        'How should I process large files?',
        { recentMemories: [], availableTools: [], sessionHistory: [] },
        emitStreamEvent,
        { providers: { yang: yangProvider, yin: yinProvider, serenity: serenityProvider } }
      );

      const elapsed = Date.now() - startTime;

      // Parallel execution should complete faster than sequential (yangDelay + yinDelay)
      expect(elapsed).toBeLessThan(yangDelay + yinDelay - 20);

      // Both Yang and Yin should have produced results
      expect(result.yang.branches.length).toBeGreaterThan(0);
      expect(isYinBaselineOutput(result.yin) ? result.yin.baselineBranches.length : 0).toBeGreaterThan(0);
      expect(result.executionMode).toBe('parallel');
    });

    it('emits stream events for each dialectic stage in order', async () => {
      const yangProvider = createJsonProvider({
        branches: [{ id: 'yang-1', type: 'what_if', content: 'Test', confidence: 0.8, noveltyScore: 0.7 }]
      }, 10);

      const yinProvider = createJsonProvider({
        baselineBranches: [{ id: 'yin-1', type: 'grounding', content: 'Test', confidence: 0.8, relevanceScore: 0.7 }],
        selfCritiques: []
      }, 10);

      const serenityProvider = createJsonProvider({
        hasSignal: false,
        branchesConsidered: 1,
        branchesSurfaced: 0,
        dialecticQuality: 0.5
      });

      const processor = new ParallelDialecticProcessor(
        logger,
        { maxWaitMs: 5000, observerTimeoutMs: 3000, partialResultsOnFailure: true, synchronization: 'best-effort' },
        { model: 'test-model', temperature: 0.9 },
        { model: 'test-model', temperature: 0.3 },
        { model: 'test-model', temperature: 0.4 }
      );

      // Wire providers
      (processor as any).yang.setProvider(yangProvider);
      (processor as any).yin.setProvider(yinProvider);
      (processor as any).serenity.setProvider(serenityProvider);

      const streamEvents: string[] = [];
      const emitStreamEvent = (event: { stage: string }) => {
        streamEvents.push(event.stage);
      };

      await processor.processTurn(
        'test-session',
        'turn-1',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] },
        emitStreamEvent,
        { providers: { yang: yangProvider, yin: yinProvider, serenity: serenityProvider } }
      );

      // Should emit events in expected order
      expect(streamEvents).toContain('start');
      expect(streamEvents).toContain('yang');
      expect(streamEvents).toContain('yin');
      expect(streamEvents).toContain('serenity');
      expect(streamEvents).toContain('complete');

      // start should come before yang/yin
      expect(streamEvents.indexOf('start')).toBeLessThan(streamEvents.indexOf('yang'));
      expect(streamEvents.indexOf('start')).toBeLessThan(streamEvents.indexOf('yin'));

      // yang/yin should come before serenity
      expect(streamEvents.indexOf('yang')).toBeLessThan(streamEvents.indexOf('serenity'));
      expect(streamEvents.indexOf('yin')).toBeLessThan(streamEvents.indexOf('serenity'));

      // serenity should come before complete
      expect(streamEvents.indexOf('serenity')).toBeLessThan(streamEvents.indexOf('complete'));
    });

    it('calculates timing metrics showing which voice completed first', async () => {
      const yangProvider = createJsonProvider({
        branches: [{ id: 'yang-1', type: 'edge_case', content: 'Fast', confidence: 0.8, noveltyScore: 0.7 }]
      }, 20);

      const yinProvider = createJsonProvider({
        baselineBranches: [{ id: 'yin-1', type: 'constraint', content: 'Slow', confidence: 0.8, relevanceScore: 0.7 }],
        selfCritiques: []
      }, 100);

      const serenityProvider = createJsonProvider({
        hasSignal: false,
        branchesConsidered: 1,
        branchesSurfaced: 0,
        dialecticQuality: 0.5
      });

      const processor = new ParallelDialecticProcessor(
        logger,
        { maxWaitMs: 5000, observerTimeoutMs: 3000, partialResultsOnFailure: true, synchronization: 'best-effort' },
        { model: 'test-model', temperature: 0.9 },
        { model: 'test-model', temperature: 0.3 },
        { model: 'test-model', temperature: 0.4 }
      );

      // Wire providers
      (processor as any).yang.setProvider(yangProvider);
      (processor as any).yin.setProvider(yinProvider);
      (processor as any).serenity.setProvider(serenityProvider);

      const result = await processor.processTurn(
        'test-session',
        'turn-1',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] },
        () => {},
        { providers: { yang: yangProvider, yin: yinProvider, serenity: serenityProvider } }
      );

      // Timing metrics should be present
      expect(result.timing).toBeDefined();
      expect(result.timing.yangDuration).toBeGreaterThan(0);
      expect(result.timing.yinDuration).toBeGreaterThan(0);
      expect(result.timing.firstCompletion).toBe('yang'); // Yang was faster
    });

    it('injects signals when synthesis has high-confidence urgent findings', async () => {
      const yangProvider = createJsonProvider({
        branches: [{ id: 'yang-1', type: 'assumption_challenge', content: 'Test', confidence: 0.9, noveltyScore: 0.8 }]
      });

      const yinProvider = createJsonProvider({
        baselineBranches: [{ id: 'yin-1', type: 'reality_check', content: 'Test', confidence: 0.9, relevanceScore: 0.9 }],
        selfCritiques: []
      });

      const serenityProvider = createJsonProvider({
        hasSignal: true,
        signal: {
          type: 'assumption',
          content: 'Critical assumption detected',
          confidence: 0.85,
          urgency: 'immediate'
        },
        branchesConsidered: 2,
        branchesSurfaced: 1,
        dialecticQuality: 0.8
      });

      const processor = new ParallelDialecticProcessor(
        logger,
        { maxWaitMs: 5000, observerTimeoutMs: 3000, partialResultsOnFailure: true, synchronization: 'best-effort' },
        { model: 'test-model', temperature: 0.9 },
        { model: 'test-model', temperature: 0.3 },
        { model: 'test-model', temperature: 0.4 }
      );

      // Wire providers
      (processor as any).yang.setProvider(yangProvider);
      (processor as any).yin.setProvider(yinProvider);
      (processor as any).serenity.setProvider(serenityProvider);

      const result = await processor.processTurn(
        'test-session',
        'turn-1',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] },
        () => {},
        { providers: { yang: yangProvider, yin: yinProvider, serenity: serenityProvider } }
      );

      expect(result.signalInjected).toBe(true);
      expect(result.serenity.synthesis.hasSignal).toBe(true);
      expect(result.serenity.synthesis.signal?.urgency).toBe('immediate');
    });

    it('calculates quality metrics including dialectic tension and agreement', async () => {
      const yangProvider = createJsonProvider({
        branches: [
          { id: 'yang-1', type: 'alternative_interpretation', content: 'Option A', confidence: 0.8, noveltyScore: 0.9 },
          { id: 'yang-2', type: 'edge_case', content: 'Option B', confidence: 0.7, noveltyScore: 0.8 }
        ]
      });

      const yinProvider = createJsonProvider({
        baselineBranches: [
          { id: 'yin-1', type: 'grounding', content: 'Option A', confidence: 0.8, relevanceScore: 0.9 }
        ],
        selfCritiques: []
      });

      const serenityProvider = createJsonProvider({
        hasSignal: false,
        branchesConsidered: 2,
        branchesSurfaced: 0,
        dialecticQuality: 0.75
      });

      const processor = new ParallelDialecticProcessor(
        logger,
        { maxWaitMs: 5000, observerTimeoutMs: 3000, partialResultsOnFailure: true, synchronization: 'best-effort' },
        { model: 'test-model', temperature: 0.9 },
        { model: 'test-model', temperature: 0.3 },
        { model: 'test-model', temperature: 0.4 }
      );

      // Wire providers
      (processor as any).yang.setProvider(yangProvider);
      (processor as any).yin.setProvider(yinProvider);
      (processor as any).serenity.setProvider(serenityProvider);

      const result = await processor.processTurn(
        'test-session',
        'turn-1',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] },
        () => {},
        { providers: { yang: yangProvider, yin: yinProvider, serenity: serenityProvider } }
      );

      expect(result.quality).toBeDefined();
      expect(result.quality.yangYinAgreement).toBeGreaterThanOrEqual(0);
      expect(result.quality.yangYinAgreement).toBeLessThanOrEqual(1);
      expect(result.quality.dialecticTension).toBeGreaterThanOrEqual(0);
      expect(result.quality.dialecticTension).toBeLessThanOrEqual(1);
      expect(result.quality.synthesisConfidence).toBeGreaterThanOrEqual(0);
      expect(result.quality.synthesisConfidence).toBeLessThanOrEqual(1);
    });
  });

  describe('Error Handling and Edge Cases', () => {
    it('times out when Yang observer exceeds the configured timeout', async () => {
      const slowYangProvider = createJsonProvider({
        branches: [{ id: 'yang-1', type: 'edge_case', content: 'Too late', confidence: 0.8, noveltyScore: 0.7 }]
      }, 1000); // 1 second delay

      const fastYinProvider = createJsonProvider({
        baselineBranches: [{ id: 'yin-1', type: 'constraint', content: 'Quick', confidence: 0.8, relevanceScore: 0.7 }],
        selfCritiques: []
      }, 10);

      const processor = new ParallelDialecticProcessor(
        logger,
        { maxWaitMs: 5000, observerTimeoutMs: 100, partialResultsOnFailure: true, synchronization: 'best-effort' },
        { model: 'test-model', temperature: 0.9 },
        { model: 'test-model', temperature: 0.3 },
        { model: 'test-model', temperature: 0.4 }
      );

      // Wire providers
      (processor as any).yang.setProvider(slowYangProvider);
      (processor as any).yin.setProvider(fastYinProvider);

      const streamEvents: string[] = [];
      const emitStreamEvent = (event: { stage: string }) => {
        streamEvents.push(event.stage);
      };

      await expect(processor.processTurn(
        'test-session',
        'turn-1',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] },
        emitStreamEvent,
        { providers: { yang: slowYangProvider, yin: fastYinProvider } }
      )).rejects.toThrow('yang observer timed out');

      expect(streamEvents).toContain('error');
    });

    it('times out when Yin observer exceeds the configured timeout', async () => {
      const fastYangProvider = createJsonProvider({
        branches: [{ id: 'yang-1', type: 'edge_case', content: 'Quick', confidence: 0.8, noveltyScore: 0.7 }]
      }, 10);

      const slowYinProvider = createJsonProvider({
        baselineBranches: [{ id: 'yin-1', type: 'constraint', content: 'Too late', confidence: 0.8, relevanceScore: 0.7 }],
        selfCritiques: []
      }, 1000);

      const processor = new ParallelDialecticProcessor(
        logger,
        { maxWaitMs: 5000, observerTimeoutMs: 100, partialResultsOnFailure: true, synchronization: 'best-effort' },
        { model: 'test-model', temperature: 0.9 },
        { model: 'test-model', temperature: 0.3 },
        { model: 'test-model', temperature: 0.4 }
      );

      // Wire providers
      (processor as any).yang.setProvider(fastYangProvider);
      (processor as any).yin.setProvider(slowYinProvider);

      await expect(processor.processTurn(
        'test-session',
        'turn-1',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] },
        () => {},
        { providers: { yang: fastYangProvider, yin: slowYinProvider } }
      )).rejects.toThrow('yin observer timed out');
    });

    it('does not inject signals when confidence is below threshold', async () => {
      const yangProvider = createJsonProvider({
        branches: [{ id: 'yang-1', type: 'edge_case', content: 'Test', confidence: 0.8, noveltyScore: 0.7 }]
      });

      const yinProvider = createJsonProvider({
        baselineBranches: [{ id: 'yin-1', type: 'constraint', content: 'Test', confidence: 0.8, relevanceScore: 0.7 }],
        selfCritiques: []
      });

      const serenityProvider = createJsonProvider({
        hasSignal: true,
        signal: {
          type: 'edge_case',
          content: 'Low confidence signal',
          confidence: 0.5, // Below 0.6 threshold
          urgency: 'immediate'
        },
        branchesConsidered: 2,
        branchesSurfaced: 1,
        dialecticQuality: 0.6
      });

      const processor = new ParallelDialecticProcessor(
        logger,
        { maxWaitMs: 5000, observerTimeoutMs: 3000, partialResultsOnFailure: true, synchronization: 'best-effort' },
        { model: 'test-model', temperature: 0.9 },
        { model: 'test-model', temperature: 0.3 },
        { model: 'test-model', temperature: 0.4 }
      );

      // Wire providers
      (processor as any).yang.setProvider(yangProvider);
      (processor as any).yin.setProvider(yinProvider);
      (processor as any).serenity.setProvider(serenityProvider);

      const result = await processor.processTurn(
        'test-session',
        'turn-1',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] },
        () => {},
        { providers: { yang: yangProvider, yin: yinProvider, serenity: serenityProvider } }
      );

      // Signal should exist but not be injected due to low confidence
      expect(result.serenity.synthesis.hasSignal).toBe(true);
      expect(result.signalInjected).toBe(false);
    });
  });

  describe('YinObserver Baseline Mode', () => {
    it('generates baseline branches independently without waiting for Yang input', async () => {
      const yin = new YinObserver(logger, { enabled: true, model: 'test-model', temperature: 0.3 });
      
      const provider = createJsonProvider({
        baselineBranches: [
          { id: 'yin-1', type: 'grounding', content: 'User is asking about API design', confidence: 0.9, relevanceScore: 0.9 },
          { id: 'yin-2', type: 'constraint', content: 'No specific framework mentioned', confidence: 0.8, relevanceScore: 0.7 }
        ]
      });
      
      yin.setProvider(provider);

      const result = await yin.observeWithBaseline(
        'test-session',
        'How should I design a scalable API?',
        {
          recentMemories: [],
          availableTools: ['read', 'write', 'bash'],
          sessionHistory: [],
          taskGuide: 'Design a REST API'
        }
      );

      // Should return baseline output structure with concurrent timing
      expect(result).toHaveProperty('baselineBranches');
      expect(result).toHaveProperty('selfCritiques');
      expect(result).toHaveProperty('meta');
      expect(result.meta).toHaveProperty('relativeTiming', 'concurrent');
      
      // Baseline branches should be array with content
      expect(Array.isArray(result.baselineBranches)).toBe(true);
      expect(result.baselineBranches.length).toBeGreaterThan(0);
      
      // Each branch should have required fields
      const branch = result.baselineBranches[0];
      expect(branch).toHaveProperty('id');
      expect(branch).toHaveProperty('type');
      expect(branch).toHaveProperty('content');
      expect(branch).toHaveProperty('confidence');
      expect(branch).toHaveProperty('relevanceScore');
    });

    it('generates self-critiques for each baseline branch based on relevance', async () => {
      const yin = new YinObserver(logger, { enabled: true, model: 'test-model', temperature: 0.3, minRelevance: 0.6 });
      
      const provider = createJsonProvider({
        baselineBranches: [
          { id: 'yin-1', type: 'grounding', content: 'High relevance content', confidence: 0.9, relevanceScore: 0.9 },
          { id: 'yin-2', type: 'constraint', content: 'Low relevance content', confidence: 0.3, relevanceScore: 0.3 }
        ]
      });
      
      yin.setProvider(provider);

      const result = await yin.observeWithBaseline(
        'test-session',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] }
      );

      // Should have self-critiques matching baseline branches
      expect(result.selfCritiques.length).toBe(result.baselineBranches.length);
      
      // High relevance branch should be valid
      const highRelevanceCritique = result.selfCritiques.find(c => c.yangBranchId === 'yin-1');
      expect(highRelevanceCritique?.valid).toBe(true);
      expect(highRelevanceCritique?.action).toBe('surface');
      
      // Low relevance branch should be invalid
      const lowRelevanceCritique = result.selfCritiques.find(c => c.yangBranchId === 'yin-2');
      expect(lowRelevanceCritique?.valid).toBe(false);
      expect(lowRelevanceCritique?.action).toBe('discard');
    });

    it('returns empty results when disabled', async () => {
      const yin = new YinObserver(logger, { enabled: false });
      
      const result = await yin.observeWithBaseline(
        'test-session',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] }
      );

      expect(result.baselineBranches).toEqual([]);
      expect(result.selfCritiques).toEqual([]);
      expect(result.meta.relativeTiming).toBe('concurrent');
    });

    it('returns empty results when no provider is wired', async () => {
      const yin = new YinObserver(logger, { enabled: true, model: 'test-model' });
      // Don't set provider
      
      const result = await yin.observeWithBaseline(
        'test-session',
        'Test message',
        { recentMemories: [], availableTools: [], sessionHistory: [] }
      );

      expect(result.baselineBranches).toEqual([]);
      expect(result.selfCritiques).toEqual([]);
    });
  });

  describe('Signal Type Classification', () => {
    it('classifies signals by type based on synthesis analysis', async () => {
      const signalTypes = [
        { type: 'edge_case', desc: 'boundary condition discovered' },
        { type: 'alternative', desc: 'different approach available' },
        { type: 'assumption', desc: 'hidden assumption identified' },
        { type: 'connection', desc: 'pattern link found' },
        { type: 'contradiction', desc: 'conflicting information detected' },
        { type: 'convergence', desc: 'both voices agree' },
        { type: 'tension', desc: 'creative vs grounded conflict' },
        { type: 'gap', desc: 'missing information identified' }
      ];

      for (const { type, desc } of signalTypes) {
        const yangProvider = createJsonProvider({
          branches: [{ id: 'yang-1', type: 'what_if', content: desc, confidence: 0.8, noveltyScore: 0.7 }]
        });

        const yinProvider = createJsonProvider({
          baselineBranches: [{ id: 'yin-1', type: 'grounding', content: desc, confidence: 0.8, relevanceScore: 0.7 }],
          selfCritiques: []
        });

        const serenityProvider = createJsonProvider({
          hasSignal: true,
          signal: {
            type,
            content: `Test ${desc}`,
            confidence: 0.8,
            urgency: 'immediate'
          },
          branchesConsidered: 2,
          branchesSurfaced: 1,
          dialecticQuality: 0.75
        });

        const processor = new ParallelDialecticProcessor(
          logger,
          { maxWaitMs: 5000, observerTimeoutMs: 3000, partialResultsOnFailure: true, synchronization: 'best-effort' },
          { model: 'test-model', temperature: 0.9 },
          { model: 'test-model', temperature: 0.3 },
          { model: 'test-model', temperature: 0.4 }
        );

        // Wire providers
        (processor as any).yang.setProvider(yangProvider);
        (processor as any).yin.setProvider(yinProvider);
        (processor as any).serenity.setProvider(serenityProvider);

        const result = await processor.processTurn(
          'test-session',
          'turn-1',
          'Test message',
          { recentMemories: [], availableTools: [], sessionHistory: [] },
          () => {},
          { providers: { yang: yangProvider, yin: yinProvider, serenity: serenityProvider } }
        );

        expect(result.serenity.synthesis.signal?.type).toBe(type);
      }
    });

    it('distinguishes between immediate and background urgency signals', async () => {
      const urgencies: Array<{ urgency: 'immediate' | 'background'; expectedInjection: boolean }> = [
        { urgency: 'immediate', expectedInjection: true },
        { urgency: 'background', expectedInjection: false }
      ];

      for (const { urgency, expectedInjection } of urgencies) {
        const yangProvider = createJsonProvider({
          branches: [{ id: 'yang-1', type: 'what_if', content: 'Test', confidence: 0.8, noveltyScore: 0.7 }]
        });

        const yinProvider = createJsonProvider({
          baselineBranches: [{ id: 'yin-1', type: 'grounding', content: 'Test', confidence: 0.8, relevanceScore: 0.7 }],
          selfCritiques: []
        });

        const serenityProvider = createJsonProvider({
          hasSignal: true,
          signal: {
            type: 'edge_case',
            content: 'Test signal',
            confidence: 0.8,
            urgency
          },
          branchesConsidered: 2,
          branchesSurfaced: 1,
          dialecticQuality: 0.75
        });

        const processor = new ParallelDialecticProcessor(
          logger,
          { maxWaitMs: 5000, observerTimeoutMs: 3000, partialResultsOnFailure: true, synchronization: 'best-effort' },
          { model: 'test-model', temperature: 0.9 },
          { model: 'test-model', temperature: 0.3 },
          { model: 'test-model', temperature: 0.4 }
        );

        // Wire providers
        (processor as any).yang.setProvider(yangProvider);
        (processor as any).yin.setProvider(yinProvider);
        (processor as any).serenity.setProvider(serenityProvider);

        const result = await processor.processTurn(
          'test-session',
          `turn-${urgency}`,
          'Test message',
          { recentMemories: [], availableTools: [], sessionHistory: [] },
          () => {},
          { providers: { yang: yangProvider, yin: yinProvider, serenity: serenityProvider } }
        );

        expect(result.signalInjected).toBe(expectedInjection);
        expect(result.serenity.synthesis.signal?.urgency).toBe(urgency);
      }
    });
  });

  describe('Configuration', () => {
    it('initializes with correct timeout and synchronization settings', () => {
      const processor = new ParallelDialecticProcessor(
        logger,
        {
          maxWaitMs: 8000,
          observerTimeoutMs: 6000,
          partialResultsOnFailure: true,
          synchronization: 'best-effort'
        },
        { model: 'kimi-coding/k2p5', temperature: 0.9 },
        { model: 'kimi-coding/k2p5', temperature: 0.3 },
        { model: 'kimi-coding/k2p5', temperature: 0.4 }
      );

      expect(processor).toBeDefined();
      // Configuration is stored internally - we verify through behavior in other tests
    });

    it('allows wiring provider to all observers at once', () => {
      const processor = new ParallelDialecticProcessor(
        logger,
        { maxWaitMs: 5000, observerTimeoutMs: 3000, partialResultsOnFailure: true, synchronization: 'best-effort' },
        { model: 'test-model', temperature: 0.9 },
        { model: 'test-model', temperature: 0.3 },
        { model: 'test-model', temperature: 0.4 }
      );

      const mockProvider = createJsonProvider({ branches: [] });
      
      // Should not throw
      expect(() => processor.setProvider(mockProvider)).not.toThrow();
    });
  });
});
