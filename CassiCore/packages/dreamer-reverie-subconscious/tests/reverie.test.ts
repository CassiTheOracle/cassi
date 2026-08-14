import { describe, it, expect } from 'vitest'

import {
  ReverieTriggerController,
} from '../src/reverie/trigger.js'
import { DEFAULT_REVERIE_CONFIG } from '../src/reverie/types.js'
import { ToolFilterRegistry, DEFAULT_TOOL_FILTER } from '../src/reverie/tool-filter.js'
import { ReverieModule } from '../src/reverie/index.js'
import { buildReveriePrompt } from '../src/reverie/prompt.js'
import { MnemicField } from '@cassicore/mnemic-field'
import type { IProvider, Message, CompletionOpts, CompletionChunk } from '@cassicore/foundation'

function mockProvider(text: string): IProvider {
  return {
    id: 'mock',
    models: ['mock-model'],
    async *complete(_messages: Message[], _opts: CompletionOpts): AsyncIterable<CompletionChunk> {
      yield { type: 'token', text }
      yield { type: 'done' }
    },
    countTokens: async () => 0,
    ping: async () => true,
  }
}

function mockLogger(): any {
  const logger = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {}, child: () => logger }
  return logger
}

describe('Reverie trigger', () => {
  it('fires on step cadence and resets after run', () => {
    const t = new ReverieTriggerController({ ...DEFAULT_REVERIE_CONFIG, stepInterval: 3, minIntervalMs: 0 })
    expect(t.recordStep('s1', 'primary')).toBeNull()
    expect(t.recordStep('s1', 'primary')).toBeNull()
    const trig = t.recordStep('s1', 'primary')
    expect(trig?.kind).toBe('step_count')
    t.recordRun('s1', { tokens: 100, durationMs: 10, suppressed: false })
    expect(t.recordStep('s1', 'primary')).toBeNull()
  })

  it('cascade prevention — reverie steps do not count', () => {
    const t = new ReverieTriggerController({ ...DEFAULT_REVERIE_CONFIG, stepInterval: 1, minIntervalMs: 0 })
    expect(t.recordStep('s1', 'reverie')).toBeNull()
    expect(t.recordStep('s1', 'meditation')).toBeNull()
    const trig = t.recordStep('s1', 'primary')
    expect(trig).not.toBeNull()
  })

  it('manual ping wins over cadence', () => {
    const t = new ReverieTriggerController({ ...DEFAULT_REVERIE_CONFIG, stepInterval: 100, minIntervalMs: 0 })
    t.ping('s1', 'user-asked')
    const trig = t.recordStep('s1', 'primary')
    expect(trig?.kind).toBe('ping_lamina')
  })

  it('suppresses when budget exhausted', () => {
    const t = new ReverieTriggerController({ ...DEFAULT_REVERIE_CONFIG, sessionTokenBudget: 100 })
    t.recordRun('s1', { tokens: 200, durationMs: 0, suppressed: false })
    const sup = t.shouldSuppress('s1')
    expect(sup.suppress).toBe(true)
    expect(sup.reason).toBe('budget_exhausted')
  })

  it('skips after slow run', () => {
    const t = new ReverieTriggerController({ ...DEFAULT_REVERIE_CONFIG, slowThresholdMs: 100, slowSkipCount: 2 })
    t.recordRun('s1', { tokens: 0, durationMs: 1000, suppressed: false })
    expect(t.shouldSuppress('s1').suppress).toBe(true)
    expect(t.shouldSuppress('s1').suppress).toBe(true)
    expect(t.shouldSuppress('s1').suppress).toBe(false)
  })
})

describe('Reverie tool filter', () => {
  it('blocks primary from rethinking user-model', () => {
    const denial = DEFAULT_TOOL_FILTER.checkLamina('primary', 'rethink', 'user-model')
    expect(denial).toMatch(/exclusive/)
  })

  it('allows reverie to rethink user-model', () => {
    expect(DEFAULT_TOOL_FILTER.checkLamina('reverie', 'rethink', 'user-model')).toBeNull()
  })

  it('allows reverie to rethink active-task (task-tree)', () => {
    expect(DEFAULT_TOOL_FILTER.checkLamina('reverie', 'rethink', 'active-task')).toBeNull()
  })

  it('blocks reverie from touching pineal:identity', () => {
    expect(DEFAULT_TOOL_FILTER.checkLamina('reverie', 'append', 'pineal:identity')).toMatch(/forbidden/)
  })

  it('blocks primary from mnemic.promote', () => {
    expect(DEFAULT_TOOL_FILTER.checkMnemic('primary', 'promote')).toMatch(/not allowed/)
  })

  it('allows registering custom agents', () => {
    const reg = new ToolFilterRegistry()
    reg.register({ agentId: 'helix-unity', exclusiveRethink: [], mnemicActions: ['read'], forbiddenLabels: ['secret'] })
    expect(reg.checkLamina('helix-unity', 'append', 'secret')).toMatch(/forbidden/)
    expect(reg.checkMnemic('helix-unity', 'store')).toMatch(/not allowed/)
  })
})

describe('Reverie prompt truncation', () => {
  it('caps total prompt size at 32K chars', () => {
    const hugeContent = 'x'.repeat(50_000)
    const prompt = buildReveriePrompt({
      sessionId: 's1',
      triggerReason: 'test',
      laminae: [{ label: 'big', content: hugeContent, owner: 'primary', contentHash: 'abc', version: 1, id: 'l1', charLimit: 8000, scope: { kind: 'global' }, tags: [], pinned: false, createdAt: '', updatedAt: '', description: null, ownerExclusive: false, readOnly: false, lastWriteProvenance: null }],
      recentSignals: [],
      recentExchange: 'User: hi\nAssistant: hello',
      recentToolRounds: [],
      budgetTokensRemaining: 50_000,
    })
    expect(prompt.system.length + prompt.user.length).toBeLessThanOrEqual(32_000 + 500) // allow small tolerance for boilerplate
  })
})

describe('Reverie auto-loop detection', () => {
  it('detects repeated errors', () => {
    const rev = new ReverieModule({ debug: () => {}, info: () => {}, warn: () => {}, error: () => {}, child: () => ({}) } as any)
    // Inject tool rounds with same error 3x
    const tr = {
      round: 1,
      toolCalls: [{ name: 'bash', id: 'tc1' }],
      results: [{ toolCallId: 'tc1', isError: true, contentPreview: 'ENOENT: no such file' }],
      at: Date.now(),
    }
    // @ts-ignore private
    rev['toolRoundLog'].set('s1', [tr, { ...tr, round: 2 }, { ...tr, round: 3 }])
    // @ts-ignore private
    const loop = rev['detectAutoLoops']('s1')
    expect(loop).toContain('ENOENT')
    expect(loop).toContain('3')
  })

  it('returns null when no loop', () => {
    const rev = new ReverieModule({ debug: () => {}, info: () => {}, warn: () => {}, error: () => {}, child: () => ({}) } as any)
    // @ts-ignore private
    const loop = rev['detectAutoLoops']('s1')
    expect(loop).toBeNull()
  })
})

describe('Reverie replay session summaries', () => {
  it('summarizes replay events into a stable session summary engram', async () => {
    const field = new MnemicField(mockLogger(), ':memory:')
    field.store({ id: 'session:s1', content: '{}', nodeType: 'session', createdAt: '2026-01-01T00:00:00.000Z' })
    field.store({ id: 'turn:s1:1', content: '{"role":"user","content":"hello"}', nodeType: 'episode', createdAt: '2026-01-01T00:00:01.000Z' })
    field.connect({ sourceId: 'turn:s1:1', targetId: 'session:s1', edgeType: 'part_of' })

    const rev = new ReverieModule(mockLogger())
    rev.setMnemicField(field)
    rev.setProvider(mockProvider('Goal: greet user. Next: continue.'))

    const summary = await rev.summarizeSessionNow('s1')
    expect(summary?.id).toBe('session_summary:s1')
    expect(summary?.nodeType).toBe('abstraction')
    expect(summary?.content).toContain('Goal: greet user')
    expect(field.getReplaySubgraph('session:s1').synapses.map(s => `${s.sourceId}->${s.targetId}:${s.edgeType}`)).toContain(
      'session_summary:s1->session:s1:part_of',
    )
    expect(field.replaySession('s1').map(e => e.kind)).toContain('session_summary')

    field.close()
  })

  it('does not feed previous session summaries back into regeneration prompts', async () => {
    const field = new MnemicField(mockLogger(), ':memory:')
    field.store({ id: 'session:s3', content: '{}', nodeType: 'session', createdAt: '2026-01-01T00:00:00.000Z' })
    field.store({ id: 'turn:s3:1', content: 'new work', nodeType: 'episode', createdAt: '2026-01-01T00:00:01.000Z' })
    field.store({ id: 'session_summary:s3', content: 'old self-referential summary', nodeType: 'abstraction', createdAt: '2026-01-01T00:00:02.000Z' })
    field.connect({ sourceId: 'turn:s3:1', targetId: 'session:s3', edgeType: 'part_of' })
    field.connect({ sourceId: 'session_summary:s3', targetId: 'session:s3', edgeType: 'part_of' })

    let promptText = ''
    const provider = mockProvider('fresh summary')
    const originalComplete = provider.complete.bind(provider)
    provider.complete = async function* (messages, opts, attachments, signal) {
      promptText = String(messages[messages.length - 1]?.content ?? '')
      yield* originalComplete(messages, opts, attachments, signal)
    }
    const rev = new ReverieModule(mockLogger())
    rev.setMnemicField(field)
    rev.setProvider(provider)

    await rev.summarizeSessionNow('s3')

    expect(promptText).toContain('new work')
    expect(promptText).not.toContain('old self-referential summary')

    field.close()
  })

  it('marks existing session summaries stale on new turn activity', async () => {
    const field = new MnemicField(mockLogger(), ':memory:')
    field.store({
      id: 'session_summary:s2',
      content: '{"summary":"old"}',
      nodeType: 'abstraction',
      tags: ['session-replay', 'session-summary'],
      metadata: { stale: false },
    })
    const rev = new ReverieModule(mockLogger())
    rev.setMnemicField(field)

    await rev.onEvent({ type: 'turn:start', sessionId: 's2', message: 'new work', timestamp: new Date() } as any)

    expect(field.get('session_summary:s2')?.metadata).toMatchObject({ stale: true, staleReason: 'turn-start' })
    expect(field.get('session_summary:s2')?.tags).toContain('stale')

    field.close()
  })
})
