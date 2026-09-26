/**
 * Mini-Helix Tests
 *
 * Tests the mini-Helix runner, Brainstem tools, and adapters.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createMiniHelixSession } from '@cassicore/mini-helix'
import type {
  MiniHelixTool,
  MiniHelixConfig,
  MiniHelixDeps,
  MiniHelixSession,
  MiniHelixStatus,
} from '@cassicore/mini-helix'
import { createBrainstemTools, buildBrainstemSystemPrompt } from '@cassicore/helix'
import type { BrainstemToolContext } from '@cassicore/helix'


// Helpers

function makeLogger() {
  const log = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(() => log),
  }
  return log
}

/**
 * Create a minimal tool that records calls and returns fixed content.
 */
function makeTool(name: string, result: { content: string; done?: boolean; pause?: boolean }): MiniHelixTool {
  return {
    def: {
      name,
      description: `Test tool: ${name}`,
      input_schema: { type: 'object', properties: {} },
    },
    handler: vi.fn().mockReturnValue(result),
  }
}

/**
 * Create a mock model handle that returns tool_use chunks.
 */
function makeMockHandle(responses: Array<{
  text?: string
  toolCalls?: Array<{ name: string; input: Record<string, unknown> }>
}>) {
  let callIndex = 0

  return {
    provider: 'test-provider',
    model: 'test-model',
    release: vi.fn(),
    complete: vi.fn(),
    stream: vi.fn().mockImplementation(function* () {
      const response = responses[Math.min(callIndex++, responses.length - 1)]

      if (response.text) {
        yield { type: 'token', text: response.text }
      }

      if (response.toolCalls) {
        for (const tc of response.toolCalls) {
          yield {
            type: 'tool_use',
            toolCall: {
              id: `tool-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
              name: tc.name,
              input: tc.input,
            },
          }
        }
      }

      yield { type: 'done', tokensUsed: 100, tokenBreakdown: { input: 80, output: 20 } }
    }),
  }
}

function makeMiniHelixDeps(handle: ReturnType<typeof makeMockHandle>): MiniHelixDeps {
  return {
    logger: makeLogger() as any,
    handleFactory: vi.fn().mockResolvedValue(handle),
  }
}

function makeConfig(overrides: Partial<MiniHelixConfig> = {}): MiniHelixConfig {
  return {
    consumer: 'corpus',
    systemPrompt: 'You are a test agent.',
    sessionId: 'test-session-1',
    constellationId: 'test-constellation-1',
    maxIterationsPerCycle: 10,
    maxTokens: 1024,
    cycleTimeoutMs: 30_000,
    modelTier: 'fast',
    ...overrides,
  }
}


// Mini-Helix Runner Tests

describe('MiniHelixRunner', () => {
  it('should create a session and acquire a model handle on first run', async () => {
    const signalDone = makeTool('signal_done', { content: 'done', done: true })
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'signal_done', input: {} }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const config = makeConfig()

    const session = createMiniHelixSession([signalDone], config, deps)
    const result = await session.run()

    expect(result.status).toBe('completed')
    expect(deps.handleFactory).toHaveBeenCalledOnce()
    expect(signalDone.handler).toHaveBeenCalledOnce()
  })

  it('should execute tool calls from the LLM and append results to history', async () => {
    const readTool = makeTool('read_data', { content: '{"items": 5}' })
    const signalDone = makeTool('signal_done', { content: 'done', done: true })
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'read_data', input: { limit: 10 } }] },
      { toolCalls: [{ name: 'signal_done', input: {} }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const session = createMiniHelixSession([readTool, signalDone], makeConfig(), deps)

    const result = await session.run()

    expect(result.status).toBe('completed')
    expect(result.toolCalls).toBe(2)
    expect(result.llmCalls).toBe(2)
    expect(readTool.handler).toHaveBeenCalledWith({ limit: 10 })
  })

  it('should handle pause_until_trigger and return paused status', async () => {
    const pauseTool = makeTool('pause_until_trigger', { content: 'paused', pause: true })
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'pause_until_trigger', input: { reason: 'stable' } }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const session = createMiniHelixSession([pauseTool], makeConfig(), deps)

    const result = await session.run()

    expect(result.status).toBe('paused')
    expect(session.getStatus()).toBe('paused')
    expect(pauseTool.handler).toHaveBeenCalledWith({ reason: 'stable' })
  })

  it('should support resume after pause', async () => {
    const pauseTool = makeTool('pause_until_trigger', { content: 'paused', pause: true })
    const signalDone = makeTool('signal_done', { content: 'done', done: true })
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'pause_until_trigger', input: {} }] },
      { toolCalls: [{ name: 'signal_done', input: {} }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const session = createMiniHelixSession([pauseTool, signalDone], makeConfig(), deps)

    // First cycle — pauses
    const r1 = await session.run()
    expect(r1.status).toBe('paused')

    // Resume
    session.resume()
    const r2 = await session.run('Triggered by escalation')
    expect(r2.status).toBe('completed')
    expect(r2.cycles).toBe(2)
  })

  it('should handle unknown tool names gracefully', async () => {
    const signalDone = makeTool('signal_done', { content: 'done', done: true })
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'nonexistent_tool', input: {} }] },
      { toolCalls: [{ name: 'signal_done', input: {} }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const session = createMiniHelixSession([signalDone], makeConfig(), deps)

    const result = await session.run()

    expect(result.status).toBe('completed')
    // Only signal_done counts as a tool call
    expect(result.toolCalls).toBe(1)
  })

  it('should complete when max iterations reached', async () => {
    const readTool = makeTool('read_data', { content: 'data' })
    // Always returns tool calls, never signal_done
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'read_data', input: {} }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const config = makeConfig({ maxIterationsPerCycle: 3 })
    const session = createMiniHelixSession([readTool], config, deps)

    const result = await session.run()

    expect(result.status).toBe('completed')
    expect(result.toolCalls).toBe(3) // Exactly max iterations
  })

  it('should handle cancel', async () => {
    const signalDone = makeTool('signal_done', { content: 'done', done: true })
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'signal_done', input: {} }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const session = createMiniHelixSession([signalDone], makeConfig(), deps)

    session.cancel()
    const result = await session.run()

    expect(result.status).toBe('cancelled')
  })

  it('should track token usage across cycles', async () => {
    const pauseTool = makeTool('pause_until_trigger', { content: 'paused', pause: true })
    const signalDone = makeTool('signal_done', { content: 'done', done: true })
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'pause_until_trigger', input: {} }] },
      { toolCalls: [{ name: 'signal_done', input: {} }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const session = createMiniHelixSession([pauseTool, signalDone], makeConfig(), deps)

    await session.run()
    session.resume()
    const result = await session.run()

    expect(result.tokenUsage.input).toBe(160) // 80 per call * 2
    expect(result.tokenUsage.output).toBe(40) // 20 per call * 2
    expect(result.tokenUsage.total).toBe(200)
  })

  it('should shut down cleanly and release model handle', async () => {
    const signalDone = makeTool('signal_done', { content: 'done', done: true })
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'signal_done', input: {} }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const session = createMiniHelixSession([signalDone], makeConfig(), deps)

    await session.run()
    await session.shutdown()

    expect(handle.release).toHaveBeenCalledOnce()
    expect(session.getStatus()).toBe('completed')
  })

  it('should return correct progress snapshot', async () => {
    const signalDone = makeTool('signal_done', { content: 'done', done: true })
    const handle = makeMockHandle([
      { toolCalls: [{ name: 'signal_done', input: {} }] },
    ])
    const deps = makeMiniHelixDeps(handle)
    const config = makeConfig({ consumer: 'brainstem' })
    const session = createMiniHelixSession([signalDone], config, deps)

    await session.run()
    const progress = session.getProgress()

    expect(progress.consumer).toBe('brainstem')
    expect(progress.sessionId).toBe('test-session-1')
    expect(progress.totalToolCalls).toBe(1)
    expect(progress.completedCycles).toBe(1)
    expect(progress.status).toBe('completed')
  })
})


// Brainstem Tools Tests

describe('BrainstemTools', () => {
  let ctx: BrainstemToolContext

  beforeEach(() => {
    ctx = {
      helixId: 'helix-test-1',
      goal: 'Implement authentication',
      logger: makeLogger() as any,
      getRecentWorkUnits: vi.fn().mockReturnValue([
        {
          id: 'wu-1',
          iteration: 1,
          filesModified: [{ path: 'src/auth.ts', action: 'modified', summary: 'Added login' }],
          reasoning: 'Implementing login flow',
          processed: false,
          timestamp: Date.now(),
        },
      ]),
      getAllWorkUnits: vi.fn().mockReturnValue([
        { id: 'wu-1', iteration: 1, filesModified: [], processed: false, timestamp: Date.now() },
      ]),
      getAnnotations: vi.fn().mockReturnValue([
        { workUnitId: 'wu-1', score: 0.8, annotation: 'implementation', pattern: 'none', timestamp: Date.now() },
      ]),
      getQualityTrajectory: vi.fn().mockReturnValue([0.6, 0.7, 0.8]),
      injectGuidance: vi.fn(),
      currentApproach: 'implementation' as any,
      recentFilesActive: new Set(['src/auth.ts']),
    }
  })

  it('should create 8 tools', () => {
    const tools = createBrainstemTools(ctx)
    expect(tools).toHaveLength(8)
    const names = tools.map((t) => t.def.name)
    expect(names).toContain('read_work_stream')
    expect(names).toContain('read_annotations')
    expect(names).toContain('publish_guidance')
    expect(names).toContain('publish_digest')
    expect(names).toContain('detect_topics')
    expect(names).toContain('self_organize')
    expect(names).toContain('escalate_to_corpus')
    expect(names).toContain('signal_done')
  })

  it('read_work_stream returns work units', async () => {
    const tools = createBrainstemTools(ctx)
    const readWS = tools.find((t) => t.def.name === 'read_work_stream')!

    const result = await readWS.handler({})
    const parsed = JSON.parse(result.content)

    expect(parsed.total).toBe(1)
    expect(parsed.returned).toBe(1)
  })

  it('read_annotations returns quality trajectory', async () => {
    const tools = createBrainstemTools(ctx)
    const readA = tools.find((t) => t.def.name === 'read_annotations')!

    const result = await readA.handler({})
    const parsed = JSON.parse(result.content)

    expect(parsed.averageScore).toBeCloseTo(0.7, 1)
    expect(parsed.recentTrajectory).toEqual([0.6, 0.7, 0.8])
  })

  it('publish_guidance calls injectGuidance', async () => {
    const tools = createBrainstemTools(ctx)
    const guide = tools.find((t) => t.def.name === 'publish_guidance')!

    const result = await guide.handler({ content: 'Focus on error handling', urgency: 'high' })

    expect(ctx.injectGuidance).toHaveBeenCalledWith('Focus on error handling', 'high')
    expect(result.content).toContain('high')
  })

  it('signal_done sets done flag', async () => {
    const tools = createBrainstemTools(ctx)
    const done = tools.find((t) => t.def.name === 'signal_done')!

    const result = await done.handler({ summary: 'All looks good', next_check: 'delayed' })

    expect(result.done).toBe(true)
    expect(result.metadata).toEqual({ nextCheck: 'delayed' })
  })

  it('publish_digest returns no-op when sharedTree is undefined', async () => {
    const tools = createBrainstemTools(ctx)
    const digest = tools.find((t) => t.def.name === 'publish_digest')!

    const result = await digest.handler({
      approach: 'implementation',
      summary: 'Making progress',
      activeFiles: ['src/auth.ts'],
      qualityScore: 0.8,
    })

    expect(result.content).toContain('No-op')
  })

  it('detect_topics returns no-op when sharedTree is undefined', async () => {
    const tools = createBrainstemTools(ctx)
    const detect = tools.find((t) => t.def.name === 'detect_topics')!

    const result = await detect.handler({ keywords: ['auth'] })
    expect(result.content).toContain('No-op')
  })

  it('self_organize returns no-op when sharedTree is undefined', async () => {
    const tools = createBrainstemTools(ctx)
    const selfOrg = tools.find((t) => t.def.name === 'self_organize')!

    const result = await selfOrg.handler({})
    expect(result.content).toContain('No-op')
  })

  it('escalate_to_corpus returns no-op when escalateToCorpus is undefined', async () => {
    const tools = createBrainstemTools(ctx)
    const escalate = tools.find((t) => t.def.name === 'escalate_to_corpus')!

    const result = await escalate.handler({ reason: 'Stuck on auth module' })
    expect(result.content).toContain('not available')
  })
})


// System Prompt Tests

describe('BrainstemSystemPrompt', () => {
  it('should be written in first person', () => {
    const prompt = buildBrainstemSystemPrompt('helix-1', 'Implement auth', 'Build the app')

    // Should NOT contain internal component names as labels
    expect(prompt).not.toMatch(/\bBrainstem\b/)
    expect(prompt).not.toMatch(/\bUnity posture\b/)
    expect(prompt).not.toMatch(/\bShared Thought Tree\b/)

    // Should contain first-person language
    expect(prompt).toContain('I observe')
    expect(prompt).toContain('my worker')
    expect(prompt).toContain('My worker\'s task')
  })

  it('should include the goal and constellation context', () => {
    const prompt = buildBrainstemSystemPrompt('helix-1', 'Implement auth', 'Build the app')

    expect(prompt).toContain('Implement auth')
    expect(prompt).toContain('Build the app')
    expect(prompt).toContain('helix-1')
  })
})
