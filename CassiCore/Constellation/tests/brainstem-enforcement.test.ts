/**
 * Brainstem Enforcement Tests
 *
 * Tests the enforcement mechanisms injected by the Corpus intervention system:
 *   - onCorpusDirective(): iteration cap, requiredAction storage, enforcement text
 *   - formatDirectiveWithEnforcement(): ENFORCED text blocks per action type
 *   - processSingleWorkUnit(): iteration cap enforcement (forced conclusion)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { HelixBrainstem, createHelixBrainstem } from '../src/vendor/helix/brainstem.js'
import type { BrainstemDeps, BrainstemConfig } from '../src/vendor/helix/brainstem-types.js'
import type { CorpusDirective } from '../src/corpus-types.js'

function makeLogger(): any {
  // WHY: child() must return the same instance so we can assert on the
  // same mock functions the Brainstem's internal child logger uses
  const log: any = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() }
  log.child = () => log
  return log
}

function makeLLM(response: string) {
  return { complete: vi.fn().mockResolvedValue({ content: response, truncated: false }) }
}

function makeWorkUnit(id: string, reasoning = 'test reasoning', iteration = 1) {
  return {
    id,
    iteration,
    reasoning,
    toolCalls: [{ name: 'read_file', input: { path: 'test.ts' } }],
    toolResults: [{ content: 'file content', isError: false }],
    filesModified: [],
    timestamp: Date.now(),
  }
}

// WHY: Section-based format matches the current parseAnnotation parser
const IMPL_RESPONSE = [
  '###SCORES',
  'GOAL_ALIGNMENT: 0.8',
  'NOVELTY: 0.7',
  'PROGRESS: 0.8',
  '###ANNOTATION',
  'implementation',
  '###SYNTHESIS',
  'Good progress on the feature.',
  '###PATTERN',
  'none',
  '###GUIDANCE',
  'Continue this approach.',
  '###TRAINING_NOTE',
  'Solid implementation step.',
].join('\n')

function makeDirective(overrides: Partial<CorpusDirective> = {}): CorpusDirective {
  return {
    targetHelixId: 'test-session',
    type: 'guidance',
    // WHY: critical urgency bypasses the reviewer gate and cooldown, making
    // getLatestGuidance() return the directive immediately in tests
    urgency: 'critical',
    reason: 'test',
    text: 'Please refocus on the primary goal.',
    timestamp: Date.now(),
    ...overrides,
  }
}

describe('Brainstem Enforcement', () => {
  let deps: BrainstemDeps

  beforeEach(() => {
    deps = {
      llm: makeLLM(IMPL_RESPONSE),
      logger: makeLogger(),
      goal: 'Implement a new feature',
      sessionId: 'test-session',
    }
  })

  describe('onCorpusDirective — iteration cap', () => {
    it('should cap maxWorkUnits when maxIterationsRemaining is set', () => {
      const bs = createHelixBrainstem(deps)
      const state = bs.getState()
      expect(state.maxWorkUnits).toBe(0) // 0 = no limit initially

      bs.onCorpusDirective(makeDirective({
        maxIterationsRemaining: 10,
      }))

      // maxWorkUnits = workUnitsProcessed + maxIterationsRemaining = 0 + 10 = 10
      expect(bs.getState().maxWorkUnits).toBe(10)
    })

    it('should lower the cap but never raise it', () => {
      const bs = createHelixBrainstem(deps)

      bs.onCorpusDirective(makeDirective({ maxIterationsRemaining: 10 }))
      expect(bs.getState().maxWorkUnits).toBe(10)

      // A larger cap should not raise the limit
      bs.onCorpusDirective(makeDirective({ maxIterationsRemaining: 20 }))
      expect(bs.getState().maxWorkUnits).toBe(10) // stays at 10

      // A smaller cap should lower it
      bs.onCorpusDirective(makeDirective({ maxIterationsRemaining: 5 }))
      expect(bs.getState().maxWorkUnits).toBe(5)
    })

    it('should account for already-processed work units', async () => {
      const bs = createHelixBrainstem(deps)
      // Process 3 work units first
      bs.onWorkUnit(makeWorkUnit('wu-1'), 1); await bs.processNow()
      bs.onWorkUnit(makeWorkUnit('wu-2'), 2); await bs.processNow()
      bs.onWorkUnit(makeWorkUnit('wu-3'), 3); await bs.processNow()
      expect(bs.getState().workUnitsProcessed).toBe(3)

      bs.onCorpusDirective(makeDirective({ maxIterationsRemaining: 5 }))
      // maxWorkUnits = 3 (processed) + 5 (remaining) = 8
      expect(bs.getState().maxWorkUnits).toBe(8)
    })
  })

  describe('onCorpusDirective — requiredAction', () => {
    it('should store requiredAction in state', () => {
      const bs = createHelixBrainstem(deps)
      expect(bs.getState().requiredAction).toBeUndefined()

      bs.onCorpusDirective(makeDirective({
        requiredAction: 'narrow_scope',
      }))

      expect(bs.getState().requiredAction).toBe('narrow_scope')
      expect(bs.getState().requiredActionSince).toBeDefined()
    })

    it('should overwrite requiredAction with a new directive', () => {
      const bs = createHelixBrainstem(deps)

      bs.onCorpusDirective(makeDirective({ requiredAction: 'narrow_scope' }))
      expect(bs.getState().requiredAction).toBe('narrow_scope')

      bs.onCorpusDirective(makeDirective({ requiredAction: 'conclude' }))
      expect(bs.getState().requiredAction).toBe('conclude')
    })

    it('should not set requiredAction when directive has none', () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({}))
      expect(bs.getState().requiredAction).toBeUndefined()
    })
  })

  describe('formatDirectiveWithEnforcement', () => {
    it('should include ENFORCED iteration text when maxIterationsRemaining is set', () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({
        maxIterationsRemaining: 10,
      }))
      // WHY: Critical corpus directives bypass the reviewer gate
      const guidance = bs.getLatestGuidance()
      expect(guidance).not.toBeNull()
      expect(guidance!.text).toContain('ENFORCED: You have 10 iterations remaining')
      expect(guidance!.text).toContain('you MUST conclude')
    })

    it('should include ENFORCED action text for narrow_scope', () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({
        requiredAction: 'narrow_scope',
      }))
      const guidance = bs.getLatestGuidance()
      expect(guidance).not.toBeNull()
      expect(guidance!.text).toContain('ENFORCED: You must narrow your scope immediately')
    })

    it('should include ENFORCED action text for switch_strategy', () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({
        requiredAction: 'switch_strategy',
      }))
      const guidance = bs.getLatestGuidance()
      expect(guidance!.text).toContain('ENFORCED: Your current approach has failed')
    })

    it('should include ENFORCED action text for conclude', () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({
        requiredAction: 'conclude',
      }))
      const guidance = bs.getLatestGuidance()
      expect(guidance!.text).toContain('ENFORCED: You must call signal_conclusion')
    })

    it('should include ENFORCED action text for produce_output', () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({
        requiredAction: 'produce_output',
      }))
      const guidance = bs.getLatestGuidance()
      expect(guidance!.text).toContain('ENFORCED: You must produce concrete output')
    })

    it('should include both iteration and action enforcement', () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({
        maxIterationsRemaining: 5,
        requiredAction: 'conclude',
      }))
      const guidance = bs.getLatestGuidance()
      expect(guidance!.text).toContain('ENFORCED: You have 5 iterations remaining')
      expect(guidance!.text).toContain('ENFORCED: You must call signal_conclusion')
    })

    it('should include the original directive text', () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({
        text: 'Branch is underperforming.',
        requiredAction: 'narrow_scope',
      }))
      const guidance = bs.getLatestGuidance()
      expect(guidance!.text).toContain('Branch is underperforming.')
    })
  })

  describe('processSingleWorkUnit — iteration cap enforcement', () => {
    it('should force conclusion when iteration cap reached', async () => {
      const bs = createHelixBrainstem(deps)

      // Set a cap of 2 iterations
      bs.onCorpusDirective(makeDirective({ maxIterationsRemaining: 2 }))
      expect(bs.getState().maxWorkUnits).toBe(2)

      // Consume the initial directive guidance so it doesn't interfere
      const initialGuidance = bs.getLatestGuidance()
      expect(initialGuidance).not.toBeNull()

      // First unit: should process normally
      bs.onWorkUnit(makeWorkUnit('wu-1'), 1); await bs.processNow()
      expect(bs.getState().workUnitsProcessed).toBe(1)

      // Second unit: hits the cap (workUnitsProcessed=2 >= maxWorkUnits=2)
      bs.onWorkUnit(makeWorkUnit('wu-2'), 2); await bs.processNow()
      expect(bs.getState().workUnitsProcessed).toBe(2)
      // WHY: The cap check fires after incrementing workUnitsProcessed, so at step 2
      // it matches the cap of 2 — critical guidance pushed
      const guidance = bs.getLatestGuidance()
      expect(guidance).not.toBeNull()
      expect(guidance!.urgency).toBe('critical')
      expect(guidance!.text).toContain('You MUST call signal_conclusion')
    })

    it('should log a warning when iteration cap reached', async () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({ maxIterationsRemaining: 1 }))
      // Consume the initial directive
      bs.getLatestGuidance()

      bs.onWorkUnit(makeWorkUnit('wu-1'), 1); await bs.processNow()

      expect(deps.logger.warn).toHaveBeenCalledWith(
        expect.stringContaining('iteration cap reached'),
        expect.objectContaining({ maxWorkUnits: 1 })
      )
    })
  })

  describe('context-inject directive', () => {
    it('should not produce guidance text for context-inject directives', () => {
      const bs = createHelixBrainstem(deps)
      bs.onCorpusDirective(makeDirective({
        type: 'context-inject' as any,
        text: '/some/file/path.ts',
      }))
      // context-inject should return early without queuing guidance
      const guidance = bs.getLatestGuidance()
      expect(guidance).toBeNull()
    })
  })
})
