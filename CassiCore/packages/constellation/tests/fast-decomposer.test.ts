/**
 * Fast Decomposer Tests
 *
 * Tests for the direct LLM-based goal decomposition module.
 * Covers specificity scoring, vague goal detection, structural markers,
 * and edge cases to prevent regressions.
 */

import { describe, it, expect, vi } from 'vitest'
import { shouldDecompose, fastDecompose } from '../src/fast-decomposer.js'
import type { CorpusLLM } from '../src/corpus-types.js'
import type { ILogger } from '../src/vendor/types/interfaces.js'

describe('fast-decomposer', () => {
  describe('shouldDecompose', () => {
    // --- Skip cases: trivially simple goals ---

    it('should return skip for short goals without file paths', () => {
      expect(shouldDecompose('Fix the bug')).toBe('skip')
      expect(shouldDecompose('Add logging')).toBe('skip')
      expect(shouldDecompose('Update config')).toBe('skip')
    })

    it('should skip very short single-concept goals', () => {
      expect(shouldDecompose('Rename a variable')).toBe('skip')
      expect(shouldDecompose('Delete unused import')).toBe('skip')
      expect(shouldDecompose('Fix typo in readme')).toBe('skip')
      expect(shouldDecompose('Bump version')).toBe('skip')
    })

    it('should handle edge cases', () => {
      expect(shouldDecompose('')).toBe('skip')
      expect(shouldDecompose('   ')).toBe('skip')
    })

    // --- Vague goal detection ---

    it('should skip vague goals with no specificity', () => {
      expect(shouldDecompose('Improve the code')).toBe('skip')
      expect(shouldDecompose('Make it better')).toBe('skip')
      expect(shouldDecompose('Clean up stuff')).toBe('skip')
      expect(shouldDecompose('Optimize things')).toBe('skip')
      expect(shouldDecompose('Fix things')).toBe('skip')
    })

    it('should NOT skip vague keywords when combined with specificity', () => {
      // WHY: "improve" + "throughout" is cross-cutting and actionable
      expect(shouldDecompose('Improve error handling throughout the codebase')).toBe('full')
      // WHY: "optimize" + file path gives enough target info
      expect(shouldDecompose('Optimize query performance in core/database.ts')).toBe('simple')
      // WHY: "clean up" + "across" is cross-cutting
      expect(shouldDecompose('Clean up imports across all modules')).toBe('full')
    })

    // --- Simple cases: single-module work with some specificity ---

    it('should return simple for medium goals with 1-2 file paths', () => {
      expect(shouldDecompose('Update the session manager in core/session-manager.ts')).toBe('simple')
      expect(shouldDecompose('Fix auth in core/auth.ts and core/session.ts')).toBe('simple')
    })

    it('should return simple for goals with one connector', () => {
      expect(shouldDecompose('Add error handling and retry logic to the provider')).toBe('simple')
    })

    it('should return simple for goals over 100 chars without cross-cutting signals', () => {
      const longSingle = 'Add a new configuration option to the admin API that allows controlling the maximum request body size for upload endpoints'
      expect(shouldDecompose(longSingle)).toBe('simple')
    })

    // --- Full cases: multi-module cross-cutting work ---

    it('should return full for long goals with cross-cutting keywords', () => {
      const longGoal = 'Implement comprehensive rate limiting across all admin API endpoints with configurable limits per endpoint type and proper error handling'
      expect(shouldDecompose(longGoal)).toBe('full')
    })

    it('should return full for goals with multiple numbered items', () => {
      const numberedGoal = '1. Add rate limiting\n2. Update documentation\n3. Add tests'
      expect(shouldDecompose(numberedGoal)).toBe('full')
    })

    it('should return full for goals with bullet/dash lists', () => {
      const dashedGoal = '- Add logging\n- Update tests\n- Fix bugs'
      expect(shouldDecompose(dashedGoal)).toBe('full')

      const asteriskGoal = '* Refactor auth\n* Update docs\n* Add tests'
      expect(shouldDecompose(asteriskGoal)).toBe('full')
    })

    it('should return full for refactor keywords regardless of length', () => {
      expect(shouldDecompose('Refactor the memory module')).toBe('full')
      expect(shouldDecompose('Migrate across all files')).toBe('full')
      expect(shouldDecompose('Restructure the entire codebase')).toBe('full')
      expect(shouldDecompose('Reorganize the test suite')).toBe('full')
    })

    it('should return full for "across" keyword', () => {
      expect(shouldDecompose('Add logging across all modules')).toBe('full')
      expect(shouldDecompose('Update types across the codebase')).toBe('full')
    })

    it('should return full for "all files" keyword', () => {
      expect(shouldDecompose('Update imports in all files')).toBe('full')
    })

    it('should return full for "throughout" keyword', () => {
      expect(shouldDecompose('Improve error handling throughout the codebase')).toBe('full')
      expect(shouldDecompose('Add structured logging throughout')).toBe('full')
    })

    it('should return full for 3+ file paths', () => {
      expect(shouldDecompose('Update core/a.ts, core/b.ts, and core/c.ts')).toBe('full')
    })

    it('should return full for 2+ connectors', () => {
      expect(shouldDecompose('Add logging and metrics and tracing to the service layer')).toBe('full')
    })

    // --- Context parameter interaction ---

    it('should consider context parameter', () => {
      const goal = 'Add logging'
      const context = 'This needs to be done across all modules in the codebase'
      expect(shouldDecompose(goal, context)).toBe('full')
    })

    it('should upgrade skip to full when context adds cross-cutting signals', () => {
      expect(shouldDecompose('Fix the handler')).toBe('skip')
      expect(shouldDecompose('Fix the handler', 'Needs refactoring across every module')).toBe('full')
    })

    it('should upgrade skip to simple when context adds a file path', () => {
      expect(shouldDecompose('Fix the handler', 'Look at core/handler.ts')).toBe('simple')
    })

    // --- Regression tests for previously-misclassified goals ---

    it('should not misclassify short goals with keywords as skip', () => {
      // WHY: These were previously returning 'skip' because the <60 char
      // early-exit ran before keyword detection
      expect(shouldDecompose('Refactor auth')).toBe('full')
      expect(shouldDecompose('Migrate the DB')).toBe('full')
    })

    it('should distinguish vague "improve X" from specific "improve X throughout Y"', () => {
      expect(shouldDecompose('Improve things')).toBe('skip')
      expect(shouldDecompose('Improve error handling throughout the codebase')).toBe('full')
      expect(shouldDecompose('Improve the session manager module')).toBe('skip')
    })

    // --- URL and path disambiguation ---

    it('should not treat URLs as file paths', () => {
      // WHY: http:// and https:// URLs contain dots that look like file extensions
      expect(shouldDecompose('Fix the bug at https://github.com/issue/123')).toBe('skip')
      expect(shouldDecompose('Check http://api.example.com/v2/users.json endpoint')).toBe('skip')
    })

    it('should still detect real file paths alongside URLs', () => {
      expect(shouldDecompose('Fix core/auth.ts per https://github.com/issue/123')).toBe('simple')
    })

    // --- Parenthetical numbering ---

    it('should return full for parenthetical numbering (1) (2) (3)', () => {
      expect(shouldDecompose('(1) Add tests (2) Fix docs (3) Update config')).toBe('full')
    })

    // --- Single list item should NOT trigger full ---

    it('should skip for a single numbered or bullet item', () => {
      expect(shouldDecompose('1. Fix the login button')).toBe('skip')
      expect(shouldDecompose('- Fix the login button')).toBe('skip')
    })

    // --- Asterisk bullets ---

    it('should return full for asterisk bullet lists', () => {
      const asteriskGoal = '* Refactor auth\n* Update docs\n* Add tests'
      expect(shouldDecompose(asteriskGoal)).toBe('full')
    })

    // --- Long vague goals ---

    it('should skip very long goals that are entirely vague', () => {
      const longVague = 'Improve the overall code quality of the project by making things better and cleaning up stuff that needs to be cleaned up and optimizing performance'
      expect(shouldDecompose(longVague)).toBe('skip')
    })

    // --- Unicode / non-ASCII ---

    it('should handle non-ASCII input gracefully', () => {
      expect(shouldDecompose('修复登录按钮的错误')).toBe('skip')
      expect(shouldDecompose('Fix the Über-bug in core/auth.ts')).toBe('simple')
    })

    // --- Bare file paths ---

    it('should return simple for bare file path goals', () => {
      expect(shouldDecompose('core/session-manager.ts')).toBe('simple')
    })

    // --- Backtick code in goals ---

    it('should handle goals with inline code', () => {
      expect(shouldDecompose('Fix the `handleRequest()` function in core/handler.ts')).toBe('simple')
    })

    // --- Case sensitivity ---

    it('should detect cross-cutting keywords case-insensitively', () => {
      expect(shouldDecompose('REFACTOR the entire auth module')).toBe('full')
      expect(shouldDecompose('ACROSS all modules')).toBe('full')
      expect(shouldDecompose('Migrate ALL FILES to new schema')).toBe('full')
    })

    // --- Detailed mode (DecompositionDecision) ---

    it('should return vague=true in detailed mode for unfocused goals', () => {
      const decision = shouldDecompose('Improve the code', undefined, true)
      expect(decision.mode).toBe('skip')
      expect(decision.vague).toBe(true)
    })

    it('should return vague=false in detailed mode for simple-but-focused goals', () => {
      const decision = shouldDecompose('Fix the bug', undefined, true)
      expect(decision.mode).toBe('skip')
      expect(decision.vague).toBe(false)
    })

    it('should return vague=false for non-skip modes', () => {
      const decision = shouldDecompose('Refactor the auth module', undefined, true)
      expect(decision.mode).toBe('full')
      expect(decision.vague).toBe(false)
    })
  })

  describe('fastDecompose (tool-use path)', () => {
    function makeMockLogger(): ILogger {
      const log = {
        debug: vi.fn(),
        info: vi.fn(),
        warn: vi.fn(),
        error: vi.fn(),
        child: vi.fn(() => log as unknown as ILogger),
      }
      return log as unknown as ILogger
    }

    function makeLLMWithToolCall(input: Record<string, unknown>): CorpusLLM {
      return {
        async complete() {
          return {
            content: '',
            truncated: false,
            toolCalls: [{ id: 'call-1', name: 'decompose_goal', input }],
          }
        },
      }
    }

    it('produces a multi-subtask decomposition from a tool call', async () => {
      const llm = makeLLMWithToolCall({
        strategy: 'sequential',
        sharedContext: 'Coordinated implementation',
        tasks: [
          { goal: 'Analyze admin API structure', priority: 1, template: 'research', relevantFiles: ['core/admin-api/routes.ts'] },
          { goal: 'Implement rate limiter middleware', priority: 2, template: 'implementation', relevantFiles: ['core/admin-api/middleware.ts'] },
          { goal: 'Wire middleware into routes', priority: 3, template: 'implementation' },
        ],
      })
      const result = await fastDecompose({
        goal: 'Refactor the entire admin API to use middleware-based rate limiting across all endpoints',
        llm,
        log: makeMockLogger(),
      })
      expect(result.decomposed).toBe(true)
      expect(result.subTasks).toHaveLength(3)
      expect(result.strategy).toBe('sequential')
      expect(result.sharedContext).toBe('Coordinated implementation')
      expect(result.subTasks[0].template).toBe('research')
    })

    it('falls back to single-task when LLM returns NO tool call', async () => {
      const llm: CorpusLLM = {
        async complete() {
          return { content: 'I refuse to use the tool', truncated: false }
        },
      }
      const log = makeMockLogger()
      const result = await fastDecompose({
        goal: 'Refactor the entire intelligence module to use event-driven architecture',
        llm,
        log,
      })
      expect(result.decomposed).toBe(false)
      expect(result.subTasks).toHaveLength(1)
      expect(result.subTasks[0].goal).toBe('Refactor the entire intelligence module to use event-driven architecture')
      expect((log as unknown as { warn: ReturnType<typeof vi.fn> }).warn).toHaveBeenCalledWith(
        expect.stringMatching(/no decompose_goal tool call/),
        expect.any(Object),
      )
    })

    it('falls back when tool-call input fails content validation (priority < 1)', async () => {
      const llm = makeLLMWithToolCall({
        strategy: 'parallel',
        tasks: [{ goal: 'do stuff', priority: 0 }],
      })
      const result = await fastDecompose({
        goal: 'Refactor the entire intelligence module to use event-driven architecture',
        llm,
        log: makeMockLogger(),
      })
      expect(result.decomposed).toBe(false)
    })

    it('falls back when LLM call throws', async () => {
      const llm: CorpusLLM = {
        async complete() {
          throw new Error('upstream rate-limited')
        },
      }
      const result = await fastDecompose({
        goal: 'Refactor the entire intelligence module to use event-driven architecture',
        llm,
        log: makeMockLogger(),
      })
      expect(result.decomposed).toBe(false)
      expect(result.subTasks).toHaveLength(1)
    })

    it('skips the LLM entirely for trivial goals (early exit)', async () => {
      const completeFn = vi.fn()
      const llm: CorpusLLM = { complete: completeFn as unknown as CorpusLLM['complete'] }
      const result = await fastDecompose({
        goal: 'Fix the typo',
        llm,
        log: makeMockLogger(),
      })
      expect(result.decomposed).toBe(false)
      expect(completeFn).not.toHaveBeenCalled()
    })

    it('passes through complexity=multi-phase when the cost gate is satisfied (template=implementation)', async () => {
      const llm = makeLLMWithToolCall({
        strategy: 'parallel',
        tasks: [{
          goal: 'substantial work',
          priority: 1,
          template: 'implementation',
          complexity: 'multi-phase',
        }],
      })
      const result = await fastDecompose({
        goal: 'Refactor the entire admin API to use middleware-based rate limiting across all endpoints',
        llm,
        log: makeMockLogger(),
      })
      expect(result.subTasks[0].complexity).toBe('multi-phase')
    })

    it('passes through complexity=multi-phase when ≥3 relevantFiles satisfy the gate', async () => {
      const llm = makeLLMWithToolCall({
        strategy: 'parallel',
        tasks: [{
          goal: 'work spanning many files',
          priority: 1,
          template: 'standard',
          relevantFiles: ['a.ts', 'b.ts', 'c.ts'],
          complexity: 'multi-phase',
        }],
      })
      const result = await fastDecompose({
        goal: 'Refactor the entire admin API to use middleware-based rate limiting across all endpoints',
        llm,
        log: makeMockLogger(),
      })
      expect(result.subTasks[0].complexity).toBe('multi-phase')
    })

    it('passes through complexity=multi-phase when goal length ≥200 satisfies the gate', async () => {
      const longGoal = 'A'.repeat(200)
      const llm = makeLLMWithToolCall({
        strategy: 'parallel',
        tasks: [{
          goal: longGoal,
          priority: 1,
          template: 'standard',
          complexity: 'multi-phase',
        }],
      })
      const result = await fastDecompose({
        goal: 'Refactor the entire admin API to use middleware-based rate limiting across all endpoints',
        llm,
        log: makeMockLogger(),
      })
      expect(result.subTasks[0].complexity).toBe('multi-phase')
    })

    it('demotes complexity=multi-phase to flat when the cost gate is NOT satisfied', async () => {
      const llm = makeLLMWithToolCall({
        strategy: 'parallel',
        tasks: [{
          goal: 'tiny work',
          priority: 1,
          template: 'standard',
          relevantFiles: ['only-one.ts'],
          complexity: 'multi-phase',
        }],
      })
      const log = makeMockLogger()
      const result = await fastDecompose({
        goal: 'Refactor the entire admin API to use middleware-based rate limiting across all endpoints',
        llm,
        log,
      })
      expect(result.subTasks[0].complexity).toBe('flat')
      expect((log as unknown as { warn: ReturnType<typeof vi.fn> }).warn).toHaveBeenCalledWith(
        expect.stringMatching(/Demoting multi-phase/),
        expect.objectContaining({ goal: 'tiny work' }),
      )
    })

    it('forces tool-use via toolChoice on the LLM call', async () => {
      let capturedOpts: Parameters<CorpusLLM['complete']>[0] | undefined
      const llm: CorpusLLM = {
        async complete(opts) {
          capturedOpts = opts
          return {
            content: '',
            truncated: false,
            toolCalls: [{ id: 'c', name: 'decompose_goal', input: {
              strategy: 'parallel',
              tasks: [{ goal: 'a', priority: 1 }, { goal: 'b', priority: 1 }],
            } }],
          }
        },
      }
      await fastDecompose({
        goal: 'Refactor the entire intelligence module to use event-driven architecture',
        llm,
        log: makeMockLogger(),
      })
      expect(capturedOpts?.toolChoice).toEqual({ type: 'tool', name: 'decompose_goal' })
      expect(capturedOpts?.tools?.[0]?.name).toBe('decompose_goal')
    })
  })
})
