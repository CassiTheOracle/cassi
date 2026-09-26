/**
 * @cassicore/spine — attention context controller contract test (faithful fake ExtensionAPI).
 *
 * Covers the acceptance contract:
 *   - inject one-message behavior (one synthetic agent-attributed user packet
 *     immediately before the canonical direct-user message; opaque packet content
 *     never copies provider-bound text across the authority boundary)
 *   - opaque OMP block preservation (originals untouched and order-preserved)
 *   - frozen plans across tool calls (one plan/render per window)
 *   - real OMP event order (`context` before `turn_start`/input `message_end`)
 *   - runtime timeout/down fail-open (plan still injected with sources unavailable)
 *   - one receipt/feedback per turn (text-free receipt, ID-only feedback)
 *   - text-free compaction checkpoint in inject only; observe contributes nothing
 *   - all /cassi-context command paths and session cleanup
 *   - no raw tool/user content in receipts
 *
 * The kernel (`@cassicore/thalamus/attention`) is mocked with the deterministic
 * FakeThalamusAttentionSession; the runtime channel client is a recording stub.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

import cassiSpine from '../src/index.js'
import type { ChannelClient } from '../src/channel/client.js'
import type { AssistantMessage, ToolResultMessage, UserMessage } from '../src/oh-my-pi-types.js'
import { createStubPi, type StubPi } from './stub-pi.js'
import {
  fakeAttentionReset,
  fakeState,
  type FakeAttentionObservation,
  type FakeAttentionAuthority,
} from './fake-attention.js'

vi.mock('@cassicore/thalamus/attention', async () => {
  const mod = await import('./fake-attention.js')
  return {
    ThalamusAttentionSession: mod.FakeThalamusAttentionSession,
    contextCandidateUnitId: mod.contextCandidateUnitId,
  }
})

// ── helpers ─────────────────────────────────────────────────────────────────

function userMsg(text: string, extra: Partial<UserMessage> = {}): UserMessage {
  return { role: 'user', content: text, timestamp: 1, ...extra }
}
function assistantMsg(text: string): AssistantMessage {
  return { role: 'assistant', content: [{ type: 'text', text }], timestamp: 2 }
}
function assistantToolMsg(
  id = 'tc-1',
  name = 'read',
  args: Record<string, unknown> = { path: 'src/file.ts', line: 1 },
): AssistantMessage {
  return {
    role: 'assistant',
    content: [{ type: 'toolCall', id, name, arguments: args }],
    timestamp: 2,
  }
}
function toolMsg(
  text: string,
  toolName = 'read',
  isError = false,
  toolCallId = 'tc-1',
): ToolResultMessage {
  return { role: 'toolResult', toolCallId, toolName, content: [{ type: 'text', text }], isError, timestamp: 3 }
}

type CandidatesFn = (req: Record<string, unknown>) => Promise<Record<string, unknown>>
interface ClientMocks {
  client: ChannelClient
  candidatesCalls: Array<Record<string, unknown>>
  feedbackCalls: Array<Record<string, unknown>>
  actionCalls: Array<Record<string, unknown>>
  memorySaveCalls: Array<Record<string, unknown>>
}

function makeClient(overrides: {
  candidates?: CandidatesFn
  action?: (req: Record<string, unknown>) => Promise<Record<string, unknown>>
} = {}): ClientMocks {
  const candidatesCalls: Array<Record<string, unknown>> = []
  const feedbackCalls: Array<Record<string, unknown>> = []
  const actionCalls: Array<Record<string, unknown>> = []
  const memorySaveCalls: Array<Record<string, unknown>> = []
  const client = {
    executeTool: async () => ({ ok: true, result: '' }),
    mirrorSession: async () => {},
    getSnapshot: async () => ({ state: { memory: {}, loops: {}, sessions: [], uptimeMs: 1, health: 'ok' } }),
    postEvent: async () => ({}),
    memoryStatus: async () => ({ backend: 'mnemic-field', stats: {} }),
    memorySearch: async () => ({ results: [] }),
    memorySave: async (req: Record<string, unknown>) => {
      memorySaveCalls.push(req)
      return { id: 'm1' }
    },
    ping: async () => true,
    contextCandidates: async (req: Record<string, unknown>) => {
      candidatesCalls.push(req)
      if (overrides.candidates) return overrides.candidates(req)
      return {
        candidates: [{ id: 'cand-1', source: 'mnemic', text: 'candidate one', score: 0.9 }],
        sources: [{ source: 'mnemic', status: 'ready', latencyMs: 5 }],
        fieldAdvisory: null,
      }
    },
    contextFeedback: async (req: Record<string, unknown>) => {
      feedbackCalls.push(req)
      return { ack: true }
    },
    contextAction: async (req: Record<string, unknown>) => {
      actionCalls.push(req)
      return overrides.action ? overrides.action(req) : { ack: true }
    },
  } as unknown as ChannelClient
  return { client, candidatesCalls, feedbackCalls, actionCalls, memorySaveCalls }
}

/** Drive the legacy notification-first order too; the controller remains order-tolerant. */
async function runTurn(
  stub: StubPi,
  messages: unknown[],
  opts: { turnIndex?: number; query?: string } = {},
): Promise<unknown[]> {
  const turnIndex = opts.turnIndex ?? 1
  await stub.fire('message_end', { type: 'message_end', message: userMsg(opts.query ?? 'tell me about X') })
  await stub.fire('turn_start', { type: 'turn_start', turnIndex, timestamp: 100 })
  const results = await stub.fire('context', { type: 'context', messages })
  await stub.fire('turn_end', { type: 'turn_end', turnIndex, message: assistantMsg('ok'), toolResults: [] })
  return results
}

/** Faithful OMP order: agent_start → context transform → turn_start → input message_end → turn_end. */
async function runOmpTurn(
  stub: StubPi,
  messages: unknown[],
  opts: { turnIndex?: number; query?: string; agentStart?: boolean } = {},
): Promise<unknown[]> {
  const turnIndex = opts.turnIndex ?? 0
  const query = opts.query ?? 'tell me about X'
  if (opts.agentStart ?? true) await stub.fire('agent_start', { type: 'agent_start' })
  const results = await stub.fire('context', { type: 'context', messages })
  await stub.fire('turn_start', { type: 'turn_start', turnIndex, timestamp: 100 })
  await stub.fire('message_end', { type: 'message_end', message: userMsg(query) })
  await stub.fire('turn_end', { type: 'turn_end', turnIndex, message: assistantMsg('ok'), toolResults: [] })
  return results
}

beforeEach(() => {
  fakeAttentionReset()
})

// ── observe equality ────────────────────────────────────────────────────────

describe('observe mode (default) — provider context unchanged', () => {
  it('returns no replacement messages and never mutates the provider-bound array', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionCandidateWaitMs: 20 })

    const before: unknown[] = [userMsg('tell me about X'), assistantMsg('sure')]
    await stub.fire('message_end', { type: 'message_end', message: userMsg('tell me about X') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 100 })
    const results = await stub.fire('context', { type: 'context', messages: before })

    expect(results).toHaveLength(1)
    expect(results[0]).toBeUndefined()
    expect(before).toEqual([userMsg('tell me about X'), assistantMsg('sure')])
    expect(stub.entries.filter(e => e.type === 'cassi.context.plan')).toHaveLength(0)
  })

  it('off mode creates no attention session and leaves everything untouched', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'off' })

    const before = [userMsg('secret question')]
    await stub.fire('message_end', { type: 'message_end', message: userMsg('secret question') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 100 })
    const results = await stub.fire('context', { type: 'context', messages: before })
    await stub.fire('turn_end', { type: 'turn_end', turnIndex: 1, message: assistantMsg('ok'), toolResults: [] })

    expect(results[0]).toBeUndefined()
    expect(fakeState.instances).toHaveLength(0)
    expect(mocks.candidatesCalls).toHaveLength(0)
    expect(mocks.feedbackCalls).toHaveLength(0)
    expect(stub.entries).toHaveLength(0)
  })
})

describe('inject mode — exactly one opaque packet', () => {
  it('inserts one synthetic agent packet before the canonical direct-user message', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    const before = [userMsg('tell me about X')]
    await stub.fire('message_end', { type: 'message_end', message: userMsg('tell me about X') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 100 })
    const results = await stub.fire('context', { type: 'context', messages: before })

    const out = results[0] as { messages: unknown[] } | undefined
    expect(out).toBeDefined()
    expect(out!.messages).toHaveLength(2)
    const packet = out!.messages[0] as Record<string, unknown>
    expect(packet).toMatchObject({
      role: 'user',
      synthetic: true,
      attribution: 'agent',
      content: 'packet:plan-sess-test-1-1-1',
    })
    expect(out!.messages[1]).toEqual(before[0])
  })

  it('preserves structured content blocks byte-for-byte', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    const structured: UserMessage = {
      role: 'user',
      content: [
        { type: 'text', text: 'first part' },
        { type: 'text', text: 'second part' },
      ],
      timestamp: 7,
    }
    await stub.fire('message_end', { type: 'message_end', message: structured })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 100 })
    const results = await stub.fire('context', { type: 'context', messages: [structured] })
    const out = results[0] as { messages: unknown[] }
    expect(out.messages[1]).toEqual(structured)
    expect(JSON.stringify(out.messages[1])).toBe(JSON.stringify(structured))
  })

  it('observes bounded user/assistant/tool messages into the attention session', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('long query')], { query: 'long query' })
    await stub.fire('message_end', { type: 'message_end', message: assistantMsg('assistant reasoning') })
    await stub.fire('message_end', { type: 'message_end', message: toolMsg('tool output here', 'bash') })

    const obs = fakeState.instances[0].calls.observe
    expect(obs.some(o => o.type === 'user' && o.text === 'long query')).toBe(true)
    expect(obs.some(o => o.type === 'assistant' && o.text === 'assistant reasoning')).toBe(true)
    const toolObs = obs.find(o => o.type === 'tool_result') as FakeAttentionObservation | undefined
    expect(toolObs).toBeDefined()
    expect(toolObs!.text).toBe('tool output here')
    expect(toolObs!.toolName).toBe('bash')
    expect(toolObs!.toolCallId).toBe('tc-1')
  })
})

// ── frozen plans across tool calls ──────────────────────────────────────────

describe('plan freezing', () => {
  it('plans and renders once per user window; later context events reuse and reinsert the frozen packet', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    const first = [userMsg('tell me about X')]
    await stub.fire('message_end', { type: 'message_end', message: userMsg('tell me about X') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 100 })
    const r1 = await stub.fire('context', { type: 'context', messages: first })
    const firstOut = r1[0] as { messages: unknown[] }
    expect(firstOut.messages).toHaveLength(2)

    // Tool-call round: a second context event in the same window.
    const second = [userMsg('tell me about X'), assistantMsg('using a tool'), toolMsg('tool output')]
    const r2 = await stub.fire('context', { type: 'context', messages: second })
    const secondOut = r2[0] as { messages: unknown[] }
    expect(secondOut.messages).toHaveLength(4)
    expect(secondOut.messages[0]).toEqual(firstOut.messages[0])

    const fake = fakeState.instances[0]
    expect(fake.calls.plan).toHaveLength(1)
    expect(fake.calls.render).toHaveLength(1)
    expect(fake.calls.beginTurn).toHaveLength(1)

    // New user message → new window → replan once.
    await stub.fire('message_end', { type: 'message_end', message: userMsg('second question') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 2, timestamp: 200 })
    const r3 = await stub.fire('context', { type: 'context', messages: [userMsg('second question')] })
    expect((r3[0] as { messages: unknown[] }).messages).toHaveLength(2)
    expect(fake.calls.plan).toHaveLength(2)
  })
})

describe('exact action lifecycle', () => {
  it('awaits a text-free durable start before recording the matching outcome', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, {
      client: mocks.client,
      noAutoSpawn: true,
      attentionMode: 'inject',
      attentionCandidateWaitMs: 20,
    })
    await stub.fire('message_end', { type: 'message_end', message: userMsg('inspect the file') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 100 })
    await stub.fire('context', { type: 'context', messages: [userMsg('inspect the file')] })

    await stub.fire('message_end', {
      type: 'message_end',
      message: assistantToolMsg('tc-action', 'read', { line: 7, path: 'src/file.ts' }),
    })
    expect(mocks.actionCalls).toHaveLength(1)
    expect(mocks.actionCalls[0]).toMatchObject({
      operation: 'start',
      sessionId: 'sess-test-1',
      turnId: 1,
      planId: 'plan-sess-test-1-1-1',
      toolCallId: 'tc-action',
      toolName: 'read',
      argumentsSha256: expect.stringMatching(/^[0-9a-f]{64}$/),
      requiredAuthority: 1,
      reversible: true,
    })
    expect(JSON.stringify(mocks.actionCalls[0])).not.toContain('src/file.ts')

    await stub.fire('message_end', {
      type: 'message_end',
      message: toolMsg('file contents stay out of the journal', 'read', false, 'tc-action'),
    })
    expect(mocks.actionCalls[1]).toEqual({
      operation: 'outcome',
      sessionId: 'sess-test-1',
      turnId: 1,
      planId: 'plan-sess-test-1-1-1',
      toolCallId: 'tc-action',
      isError: false,
    })
    expect(JSON.stringify(mocks.actionCalls[1])).not.toContain('file contents')
  })

  it.each([
    ['direct_user', 1],
    ['agent', 0.8],
    ['tool', 0.6],
    ['memory', 0.4],
    ['external_data', 0.2],
  ] satisfies Array<[FakeAttentionAuthority, number]>)(
    'converts %s attention provenance once into normalized action authority %s',
    async (authority, requiredAuthority) => {
      fakeState.planAuthority = authority
      const stub = createStubPi()
      const mocks = makeClient()
      cassiSpine(stub.pi, {
        client: mocks.client,
        noAutoSpawn: true,
        attentionMode: 'inject',
        attentionCandidateWaitMs: 20,
      })
      await stub.fire('message_end', {
        type: 'message_end',
        message: userMsg(`plan from ${authority}`),
      })
      await stub.fire('turn_start', {
        type: 'turn_start',
        turnIndex: 1,
        timestamp: 100,
      })
      await stub.fire('context', {
        type: 'context',
        messages: [userMsg(`plan from ${authority}`)],
      })
      await stub.fire('message_end', {
        type: 'message_end',
        message: assistantToolMsg(`tc-${authority}`, 'read', { path: 'src/file.ts' }),
      })

      expect(mocks.actionCalls[0]).toMatchObject({
        operation: 'start',
        requiredAuthority,
      })
    },
  )

  it('rejects the message event when the exact start cannot be made durable', async () => {
    const stub = createStubPi()
    const mocks = makeClient({
      action: async () => { throw new Error('journal unavailable') },
    })
    cassiSpine(stub.pi, {
      client: mocks.client,
      noAutoSpawn: true,
      attentionMode: 'inject',
      attentionCandidateWaitMs: 20,
    })
    await stub.fire('message_end', { type: 'message_end', message: userMsg('inspect the file') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 100 })
    await stub.fire('context', { type: 'context', messages: [userMsg('inspect the file')] })

    await expect(stub.fire('message_end', {
      type: 'message_end',
      message: assistantToolMsg('tc-action'),
    })).rejects.toThrow('exact action start must be durable before execution')
  })
})

describe('real OMP event order', () => {
  it('plans before turn_start, then attributes the receipt and feedback to the emitted turn', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    const results = await runOmpTurn(stub, [userMsg('real-order query')], { query: 'real-order query' })
    const out = results[0] as { messages: Array<Record<string, unknown>> }
    expect(out.messages[0]).toMatchObject({ role: 'user', synthetic: true, attribution: 'agent' })
    expect(out.messages[1]).toMatchObject({ role: 'user', content: 'real-order query' })
    expect(mocks.candidatesCalls[0]).toMatchObject({ turnId: 0, query: 'real-order query' })
    expect(mocks.feedbackCalls[0]).toMatchObject({ turnId: 0, outcome: 'completed' })
    expect(stub.entries.find(entry => entry.type === 'cassi.context.plan')?.data).toMatchObject({ turnId: 0 })
  })

  it('reuses one frozen packet across tool rounds and replans after the next agent_start prompt', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    const first = await runOmpTurn(stub, [userMsg('q1')], { query: 'q1' })
    const firstPacket = (first[0] as { messages: unknown[] }).messages[0]

    const toolContext = [userMsg('q1'), assistantMsg('using a tool'), toolMsg('tool evidence')]
    const toolResults = await stub.fire('context', { type: 'context', messages: toolContext })
    const toolOut = toolResults[0] as { messages: unknown[] }
    expect(toolOut.messages[0]).toEqual(firstPacket)
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 200 })
    await stub.fire('message_end', { type: 'message_end', message: toolMsg('tool evidence') })
    await stub.fire('turn_end', { type: 'turn_end', turnIndex: 1, message: assistantMsg('done'), toolResults: [] })

    await runOmpTurn(stub, [userMsg('q2')], { query: 'q2' })

    const fake = fakeState.instances[0]
    expect(fake.calls.plan).toHaveLength(2)
    expect(fake.calls.render).toHaveLength(2)
    expect(mocks.candidatesCalls.map(call => call.query)).toEqual(['q1', 'q2'])
    expect(mocks.feedbackCalls.map(call => call.turnId)).toEqual([0, 1, 0])
    expect(stub.entries.filter(entry => entry.type === 'cassi.context.plan')).toHaveLength(3)
  })
})

// ── runtime timeout / down fail-open ────────────────────────────────────────

describe('runtime candidate timeout/down fail open', () => {
  it('injects the local plan with sources unavailable when the runtime is down', async () => {
    const stub = createStubPi()
    const mocks = makeClient({ candidates: async () => { throw new Error('connection refused') } })
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    const results = await runTurn(stub, [userMsg('tell me about X')])
    const out = results[0] as { messages: unknown[] }
    expect(out.messages).toHaveLength(2)

    const fake = fakeState.instances[0]
    const frame = fake.calls.plan[0].frame
    expect(frame.sourceStatuses).toEqual([expect.objectContaining({ source: 'mnemic', status: 'offline' })])
    expect(mocks.feedbackCalls).toHaveLength(1)
    expect(mocks.feedbackCalls[0]).toMatchObject({ outcome: 'completed', includedCandidateIds: [] })
  })

  it('injects the local plan after waiting only the short deadline when candidates never arrive', async () => {
    const stub = createStubPi()
    const mocks = makeClient({ candidates: () => new Promise<Record<string, unknown>>(() => {}) })
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 10 })

    const started = Date.now()
    const results = await runTurn(stub, [userMsg('tell me about X')])
    expect(Date.now() - started).toBeLessThan(2000)

    const out = results[0] as { messages: unknown[] }
    expect(out.messages).toHaveLength(2)
    const fake = fakeState.instances[0]
    expect(fake.calls.plan[0].frame.sourceStatuses).toEqual([expect.objectContaining({ source: 'mnemic', status: 'timeout' })])
  })

  it('returns the original messages unchanged when the LOCAL planner throws (fail-open)', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })
    fakeState.planError = new Error('planner boom')

    const before = [userMsg('tell me about X')]
    await stub.fire('message_end', { type: 'message_end', message: userMsg('tell me about X') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 100 })
    const results = await stub.fire('context', { type: 'context', messages: before })
    expect(results[0]).toBeUndefined()
    expect(before).toEqual([userMsg('tell me about X')])

    await stub.fire('turn_end', { type: 'turn_end', turnIndex: 1, message: assistantMsg('ok'), toolResults: [] })
    expect(mocks.feedbackCalls).toHaveLength(0)
    expect(stub.entries.filter(e => e.type === 'cassi.context.plan')).toHaveLength(0)
  })
})

describe('live field candidate timing', () => {
  it('gives an explicitly enabled CassiFI ranker enough time to affect the turn', async () => {
    const previous = process.env.CASSI_FI_PROVIDER_URL
    process.env.CASSI_FI_PROVIDER_URL = 'http://127.0.0.1:8086'
    try {
      const stub = createStubPi()
      const mocks = makeClient()
      cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject' })

      await runTurn(stub, [userMsg('field-ranked context')])

      expect(mocks.candidatesCalls[0]).toMatchObject({ deadlineMs: 2_500 })
    } finally {
      if (previous === undefined) delete process.env.CASSI_FI_PROVIDER_URL
      else process.env.CASSI_FI_PROVIDER_URL = previous
    }
  })
})

// ── one receipt/feedback per turn ───────────────────────────────────────────

describe('receipts and feedback', () => {
  it('appends one text-free receipt and sends one ID/outcome-only feedback per completed turn', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('tell me about X')])

    const receipts = stub.entries.filter(e => e.type === 'cassi.context.plan')
    expect(receipts).toHaveLength(1)
    expect(mocks.feedbackCalls).toHaveLength(1)
    expect(mocks.feedbackCalls[0]).toMatchObject({
      sessionId: 'sess-test-1',
      turnId: 1,
      planId: 'plan-sess-test-1-1-1',
      includedCandidateIds: ['cand-1'],
      outcome: 'completed',
    })
    // Candidates request carries only {sessionId,turnId,query,limit,deadlineMs,includeFieldShadow}.
    // deadlineMs is clamped to the runtime's [100, 10000] range.
    expect(mocks.candidatesCalls[0]).toEqual({
      sessionId: 'sess-test-1',
      turnId: 1,
      query: 'tell me about X',
      limit: 5,
      deadlineMs: 100,
      includeFieldShadow: false,
    })
  })

  it('credits the latest successful tool after an expected failing reproduction', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, {
      client: mocks.client,
      noAutoSpawn: true,
      attentionMode: 'inject',
      attentionCandidateWaitMs: 20,
    })

    await stub.fire('message_end', { type: 'message_end', message: userMsg('repair it') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 1, timestamp: 100 })
    await stub.fire('context', { type: 'context', messages: [userMsg('repair it')] })
    await stub.fire('message_end', {
      type: 'message_end',
      message: toolMsg('EXPECTED-FAILURE-OUTPUT', 'pytest', true, 'tc-fail'),
    })
    await stub.fire('message_end', {
      type: 'message_end',
      message: toolMsg('PASS-OUTPUT', 'pytest', false, 'tc-pass'),
    })
    await stub.fire('turn_end', {
      type: 'turn_end',
      turnIndex: 1,
      message: assistantMsg('fixed'),
      toolResults: [],
    })

    expect(mocks.feedbackCalls).toHaveLength(1)
    expect(mocks.feedbackCalls[0]).toMatchObject({
      outcome: 'completed',
      toolResult: { id: 'tc-pass', name: 'pytest', isError: false },
    })
    expect(JSON.stringify(mocks.feedbackCalls[0])).not.toContain('PASS-OUTPUT')
    expect(JSON.stringify(mocks.feedbackCalls[0])).not.toContain('EXPECTED-FAILURE-OUTPUT')
  })

  it('reports the final exact tool failure without its output text', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, {
      client: mocks.client,
      noAutoSpawn: true,
      attentionMode: 'inject',
      attentionCandidateWaitMs: 20,
    })

    await stub.fire('message_end', { type: 'message_end', message: userMsg('verify it') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 2, timestamp: 100 })
    await stub.fire('context', { type: 'context', messages: [userMsg('verify it')] })
    await stub.fire('message_end', {
      type: 'message_end',
      message: toolMsg('PRIVATE-STACK-TRACE', 'pytest', true, 'tc-error'),
    })
    await stub.fire('turn_end', {
      type: 'turn_end',
      turnIndex: 2,
      message: assistantMsg('still failing'),
      toolResults: [],
    })

    expect(mocks.feedbackCalls).toHaveLength(1)
    expect(mocks.feedbackCalls[0]).toMatchObject({
      outcome: 'error',
      toolResult: { id: 'tc-error', name: 'pytest', isError: true },
    })
    expect(JSON.stringify(mocks.feedbackCalls[0])).not.toContain('PRIVATE-STACK-TRACE')
  })

  it('omits a successful tool outcome when packet rendering failed', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    fakeState.renderError = new Error('render failed')
    cassiSpine(stub.pi, {
      client: mocks.client,
      noAutoSpawn: true,
      attentionMode: 'inject',
      attentionCandidateWaitMs: 20,
    })

    await stub.fire('message_end', { type: 'message_end', message: userMsg('render it') })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 3, timestamp: 100 })
    await stub.fire('context', { type: 'context', messages: [userMsg('render it')] })
    await stub.fire('message_end', {
      type: 'message_end',
      message: toolMsg('PASS-OUTPUT', 'pytest', false, 'tc-pass'),
    })
    await stub.fire('turn_end', {
      type: 'turn_end',
      turnIndex: 3,
      message: assistantMsg('render failed'),
      toolResults: [],
    })

    expect(mocks.feedbackCalls).toHaveLength(1)
    expect(mocks.feedbackCalls[0]).toMatchObject({ outcome: 'error' })
    expect(mocks.feedbackCalls[0]).not.toHaveProperty('toolResult')
  })

  it('does not double-emit for the same turn', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('tell me about X')])
    // Duplicate turn_end for the same turn index → no second receipt/feedback.
    await stub.fire('turn_end', { type: 'turn_end', turnIndex: 1, message: assistantMsg('ok'), toolResults: [] })

    expect(stub.entries.filter(e => e.type === 'cassi.context.plan')).toHaveLength(1)
    expect(mocks.feedbackCalls).toHaveLength(1)
  })

  it('emits a receipt for the next turn too (one per completed turn)', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('q1')], { turnIndex: 1, query: 'q1' })
    await runTurn(stub, [userMsg('q2')], { turnIndex: 2, query: 'q2' })

    expect(stub.entries.filter(e => e.type === 'cassi.context.plan')).toHaveLength(2)
    expect(mocks.feedbackCalls).toHaveLength(2)
    expect(mocks.feedbackCalls[1]).toMatchObject({ turnId: 2, outcome: 'completed' })
  })

  it('a turn with no plan emits neither a receipt nor invalid feedback', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 3, timestamp: 100 })
    await stub.fire('turn_end', { type: 'turn_end', turnIndex: 3, message: assistantMsg('ok'), toolResults: [] })

    expect(stub.entries.filter(e => e.type === 'cassi.context.plan')).toHaveLength(0)
    expect(mocks.feedbackCalls).toHaveLength(0)
  })
})

// ── no raw content in receipts ──────────────────────────────────────────────

describe('receipt hygiene', () => {
  it('the receipt carries plan/IDs only — no raw user or tool text', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('SECRET-USER-CONTENT')])
    await stub.fire('message_end', { type: 'message_end', message: toolMsg('SECRET-TOOL-OUTPUT') })

    const receipt = stub.entries.find(e => e.type === 'cassi.context.plan')!.data as Record<string, unknown>
    expect('text' in receipt).toBe(false)
    expect('content' in receipt).toBe(false)
    expect(JSON.stringify(receipt)).not.toContain('SECRET-USER-CONTENT')
    expect(JSON.stringify(receipt)).not.toContain('SECRET-TOOL-OUTPUT')
    expect(receipt).toMatchObject({
      schemaVersion: 1,
      planId: 'plan-sess-test-1-1-1',
      sessionId: 'sess-test-1',
      turnId: 1,
      packetHash: 'h-plan-sess-test-1-1-1',
    })
    const included = (receipt.included as Array<{ unitId: string; reason: string; estimatedTokens: number; sourceRefs: string[] }>)
    for (const item of included) {
      expect(item).toMatchObject({ unitId: expect.any(String), reason: expect.any(String), estimatedTokens: expect.any(Number), sourceRefs: expect.any(Array) })
    }
  })

  it('feedback carries IDs/outcome only, never raw text', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('SECRET-USER-CONTENT')])
    expect(JSON.stringify(mocks.feedbackCalls)).not.toContain('SECRET-USER-CONTENT')
    expect(mocks.feedbackCalls[0]).toMatchObject({ sessionId: 'sess-test-1', planId: expect.any(String), includedCandidateIds: ['cand-1'], outcome: 'completed' })
  })
})

// ── compaction contribution ─────────────────────────────────────────────────

describe('session.compacting contribution', () => {
  it('persists a text-free checkpoint without overwriting other extension hook results', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('SECRET-USER-CONTENT')])
    const results = await stub.fire('session.compacting', { type: 'session.compacting', sessionId: 'sess-test-1', messages: [] })
    expect(results[0]).toBeUndefined()

    const checkpoint = stub.entries.find(entry => entry.type === 'cassi.context.compaction')?.data
    expect(checkpoint).toMatchObject({
      sessionId: 'sess-test-1',
      revision: expect.any(Number),
      turnId: 1,
      latestPlanId: 'plan-sess-test-1-1-1',
      checkpoint: ['compact:sess-test-1'],
    })
    expect(JSON.stringify(checkpoint)).not.toContain('SECRET-USER-CONTENT')
    expect(mocks.memorySaveCalls).toEqual([
      expect.objectContaining({
        type: 'session',
        provenance: 'cassi-context-compaction',
        sessionId: 'sess-test-1',
        metadata: expect.objectContaining({ candidateIds: ['cand-1'] }),
      }),
    ])
    expect(JSON.stringify(mocks.memorySaveCalls)).not.toContain('SECRET-USER-CONTENT')
  })

  it('observe mode records compaction internally but contributes no provider or preserve context', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'observe', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('OBSERVE-ONLY-SECRET')])
    const results = await stub.fire('session.compacting', { type: 'session.compacting', sessionId: 'sess-test-1', messages: [] })
    expect(results[0]).toBeUndefined()
    expect(fakeState.instances[0].calls.compact).toBe(0)
  })
})

// ── /cassi-context command paths ────────────────────────────────────────────

describe('/cassi-context command', () => {
  it('registers the command', () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true })
    expect(stub.commands.map(c => c.name)).toContain('cassi-context')
  })

  it('status reports mode + session state', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject' })

    await runTurn(stub, [userMsg('tell me about X')])
    await stub.runCommand('cassi-context', 'status')
    const last = stub.notifications.at(-1)!
    expect(last.message).toContain('mode=inject')
    expect(last.message).toContain('session=sess-test-1')
    expect(last.message).toContain('units=')
  })

  it('explain reports the frozen plan items and reasons', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await stub.runCommand('cassi-context', 'explain')
    expect(stub.notifications.at(-1)!.message).toContain('no frozen plan')

    await runTurn(stub, [userMsg('tell me about X')])
    await stub.runCommand('cassi-context', 'explain')
    const msg = stub.notifications.at(-1)!.message
    expect(msg).toContain('plan-sess-test-1-1-1')
    expect(msg).toContain('budget=')
    expect(msg).toContain('candidate:mnemic:cand-1')
  })

  it('mode switches off/observe/inject and rejects unknown values', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true })

    await stub.runCommand('cassi-context', 'mode inject')
    expect(stub.notifications.at(-1)!.message).toBe('cassi-context: mode set to inject')

    await stub.runCommand('cassi-context', 'mode bogus')
    expect(stub.notifications.at(-1)!.message).toContain('mode requires off|observe|inject')

    await stub.runCommand('cassi-context', 'mode off')
    expect(stub.notifications.at(-1)!.message).toBe('cassi-context: mode set to off')

    // After `mode off`, the next turn produces nothing.
    const before = stub.entries.length
    await runTurn(stub, [userMsg('q')])
    expect(stub.entries.length).toBe(before)
    expect(fakeState.instances).toHaveLength(0)
  })

  it('pin/unpin round-trip and unknown verbs warn', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject' })

    await stub.runCommand('cassi-context', 'pin remember the fix')
    const pinMsg = stub.notifications.at(-1)!.message
    expect(pinMsg).toMatch(/^cassi-context: pinned pin-\d+$/)
    const unitId = pinMsg.split(' ').at(-1)!

    await stub.runCommand('cassi-context', 'unpin nope')
    expect(stub.notifications.at(-1)!.message).toContain('no unit nope')

    await stub.runCommand('cassi-context', `unpin ${unitId}`)
    expect(stub.notifications.at(-1)!.message).toBe(`cassi-context: unpinned ${unitId}`)

    await stub.runCommand('cassi-context', 'bogus')
    expect(stub.notifications.at(-1)!.message).toContain("unknown verb 'bogus'")

    await stub.runCommand('cassi-context', 'pin ')
    expect(stub.notifications.at(-1)!.message).toContain('pin requires text')
  })

  it('reset clears the attention session', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('tell me about X')])
    const fake = fakeState.instances[0]
    expect(fake.calls.reset).toBe(0)

    await stub.runCommand('cassi-context', 'reset')
    expect(stub.notifications.at(-1)!.message).toBe('cassi-context: attention reset')
    expect(fake.calls.reset).toBe(1)

    // A new turn starts a fresh session (old one was dropped from the map).
    await runTurn(stub, [userMsg('again')])
    expect(fakeState.instances).toHaveLength(2)
  })
})

// ── session reset / switch / shutdown ───────────────────────────────────────

describe('session lifecycle cleanup', () => {
  it('session_switch resets the previous session and starts fresh on the new one', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('q1')])
    expect(fakeState.instances).toHaveLength(1)
    const first = fakeState.instances[0]
    expect(first.calls.reset).toBe(0)

    stub.setSessionId('sess-test-2')
    await stub.fire('session_switch', { type: 'session_switch', reason: 'resume', previousSessionFile: 'x.jsonl' })
    expect(first.calls.reset).toBe(1)

    await runTurn(stub, [userMsg('q2')])
    expect(fakeState.instances).toHaveLength(2)
    expect(fakeState.instances[1].sessionId).toBe('sess-test-2')
  })

  it('sends cancelled feedback when a frozen plan is abandoned', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await stub.fire('agent_start', { type: 'agent_start' })
    await stub.fire('context', { type: 'context', messages: [userMsg('q1')] })
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 0, timestamp: 100 })
    await stub.fire('message_end', { type: 'message_end', message: userMsg('q1') })
    expect(mocks.feedbackCalls).toHaveLength(0)

    stub.setSessionId('sess-test-2')
    await stub.fire('session_switch', { type: 'session_switch', reason: 'resume', previousSessionFile: 'x.jsonl' })
    expect(mocks.feedbackCalls).toEqual([expect.objectContaining({
      sessionId: 'sess-test-1',
      turnId: 0,
      outcome: 'cancelled',
    })])
  })

  it('invalidates an awaiting old window before deferred candidates resolve', async () => {
    const candidates = Promise.withResolvers<Record<string, unknown>>()
    const stub = createStubPi()
    const mocks = makeClient({ candidates: () => candidates.promise })
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 10_000 })

    const staleContext = stub.fire('context', { type: 'context', messages: [userMsg('old query')] })
    await vi.waitFor(() => expect(mocks.candidatesCalls).toHaveLength(1))
    stub.setSessionId('sess-test-2')
    await stub.fire('session_switch', { type: 'session_switch', reason: 'resume', previousSessionFile: 'x.jsonl' })
    candidates.resolve({
      candidates: [{ id: 'stale', source: 'mnemic', text: 'stale candidate', score: 1 }],
      sources: [{ source: 'mnemic', status: 'ready', latencyMs: 1 }],
      fieldAdvisory: null,
    })

    expect(await staleContext).toEqual([undefined])
    expect(mocks.feedbackCalls).toEqual([{
      sessionId: 'sess-test-1',
      turnId: 0,
      planId: 'stale-context',
      includedCandidateIds: [],
      outcome: 'cancelled',
    }])
    expect(fakeState.instances[0].calls.plan).toHaveLength(0)
  })

  it('session_branch resets abandoned-leaf state and rehydrates the canonical tail', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('old branch goal')])
    const first = fakeState.instances[0]
    stub.setSessionId('sess-branched-2')
    await stub.fire('session_branch', { type: 'session_branch', previousSessionFile: 'session.jsonl' })
    expect(first.calls.reset).toBe(1)

    const restored = [
      userMsg('restored branch goal'),
      assistantMsg('restored decision'),
      toolMsg('restored evidence'),
    ]
    await stub.fire('turn_start', { type: 'turn_start', turnIndex: 2, timestamp: 200 })
    const result = await stub.fire('context', { type: 'context', messages: restored })

    expect(fakeState.instances).toHaveLength(2)
    const second = fakeState.instances[1]
    expect(second.calls.observe.map(call => call.type)).toEqual(['user', 'assistant', 'tool_result'])
    const replacement = result[0] as { messages: unknown[] }
    expect(replacement.messages).toHaveLength(4)
  })

  it('session_shutdown resets every live attention session', async () => {
    const stub = createStubPi()
    const mocks = makeClient()
    cassiSpine(stub.pi, { client: mocks.client, noAutoSpawn: true, attentionMode: 'inject', attentionCandidateWaitMs: 20 })

    await runTurn(stub, [userMsg('q1')])
    const first = fakeState.instances[0]
    await stub.fire('session_shutdown', { type: 'session_shutdown' })
    expect(first.calls.reset).toBe(1)
  })
})
