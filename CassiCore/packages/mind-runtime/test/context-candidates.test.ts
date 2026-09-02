/**
 * @cassicore/mind-runtime — context candidate service tests.
 *
 * Covers candidate mapping/filtering/caps, deadline fail-open, malformed
 * request rejection, field cached-shadow first-miss/next-hit, concurrent
 * refresh coalescing, offline field neutrality, and ID-only feedback with an
 * observable bus event. Uses fakes for the memory + field-telemetry surfaces;
 * no HTTP, no real 7599 socket.
 */

import { setTimeout as delay } from 'node:timers/promises'

import { describe, expect, it, vi } from 'vitest'
import type { IEventBus, ILogger } from '@cassicore/foundation'
import {
  ContextRequestError,
  RuntimeContextCandidateService,
  type ContextFieldTelemetrySurface,
  type ContextFieldRanker,
  type ContextMemorySurface,
  type RuntimeContextCandidateServiceOptions,
} from '../src/context/candidates.js'
import type { ContextActionRequest, ContextCandidatesRequest, ContextFeedbackRequest } from '../src/channel/protocol.js'
import type { MemoryHitView } from '../src/memory/backend.js'
import { MnemicMemoryAdapter } from '../src/memory/backend.js'

const quietLogger: ILogger = {
  debug: () => {}, info: () => {}, warn: () => {}, error: () => {},
  child: () => quietLogger,
}

function hit(id: string, content: string, score: number, sessionId?: string): MemoryHitView {
  return { id, content, score, nodeType: 'fact', metadata: sessionId ? { sessionId } : {} }
}

function req(overrides: Partial<ContextCandidatesRequest> = {}): ContextCandidatesRequest {
  return { sessionId: 'sess-1', turnId: 1, query: 'golden thought', ...overrides }
}

function feedback(overrides: Partial<ContextFeedbackRequest> = {}): ContextFeedbackRequest {
  return {
    sessionId: 'sess-1',
    turnId: 1,
    planId: 'plan-1',
    includedCandidateIds: ['a', 'b'],
    outcome: 'completed',
    ...overrides,
  }
}

/** Fake exact memory surface with durable-turn semantics for service tests. */
function makeMemory(
  impl: (query: string, opts?: { limit?: number; type?: string; sessionId?: string; deadlineMs?: number }) => Promise<MemoryHitView[]>,
): {
  memory: ContextMemorySurface
  calls: Array<{ query: string; limit?: number; sessionId?: string }>
  feedbackEvents: Array<Record<string, unknown>>
} {
  const calls: Array<{ query: string; limit?: number; sessionId?: string }> = []
  const feedbackEvents: Array<Record<string, unknown>> = []
  const eligibility = new Map<string, {
    query: string
    candidates: ReadonlyArray<{
      id: string
      recordId: string
      startByte: number
      endByte: number
      text: string
      revision: string
    }>
  }>()
  return {
    memory: {
      searchReadOnly: async (query, opts) => {
        calls.push({ query, limit: opts?.limit, sessionId: opts?.sessionId })
        return impl(query, opts)
      },
      rememberContextTurn: (sessionId, turnId, query, candidates) => {
        eligibility.set(`${sessionId}\0${turnId}`, { query, candidates })
      },
      consumeContextFeedback: (sessionId, turnId, includedCandidateIds, outcome, toolResult) => {
        const key = `${sessionId}\0${turnId}`
        const remembered = eligibility.get(key)
        eligibility.delete(key)
        if (!remembered) return
        const included = new Set(includedCandidateIds)
        feedbackEvents.push({
          sessionId,
          query: remembered.query,
          candidates: remembered.candidates.filter(candidate => included.has(candidate.id)),
          outcome,
          ...(toolResult ? { toolResult } : {}),
        })
      },
    },
    calls,
    feedbackEvents,
  }
}

/** Fake 7599 client surface; counts reads, optional delay, configurable result. */
function makeTelemetry(behavior: {
  result?: () => Promise<unknown> | unknown
  delayMs?: number
  connected?: boolean
  lastError?: string | null
}): { telemetry: ContextFieldTelemetrySurface; readCount: () => number } {
  let count = 0
  const telemetry: ContextFieldTelemetrySurface = {
    read: async () => {
      count += 1
      if (behavior.delayMs) await delay(behavior.delayMs)
      const result = behavior.result ? await behavior.result() : null
      return result as never
    },
    status: () => ({
      host: '127.0.0.1',
      port: 7599,
      connected: behavior.connected ?? false,
      lastReadAt: null,
      lastError: behavior.lastError ?? null,
    }),
  }
  return { telemetry, readCount: () => count }
}

function shadowSnapshot(step = 42): unknown {
  return {
    step,
    time: 1.5,
    gridN: 4,
    cells: 64,
    balance: { meanRho: 0.1, meanEpsilon: 0.2, meanFieldPower: 0.9, meanCoherence: 0.7 },
    thetaTemporalResultant: { resultant: 0.8, weightedMeanAbsoluteIncrement: 0.3, samples: 64 },
    jProxy: { rms: 0.5, samples: 192 },
    helicalScan: { canonicalSpiral: false, bestValue: 0.9, bestAxis: 'x', bestMode: 2, modeZero: [0.1, 0.2, 0.3], samples: 64 },
  }
}
function makeService(
  memory: ContextMemorySurface,
  opts: RuntimeContextCandidateServiceOptions = {},
  telemetry?: ContextFieldTelemetrySurface,
  bus?: IEventBus,
  fieldRanker?: ContextFieldRanker,
): RuntimeContextCandidateService {
  const events: unknown[] = []
  const fakeBus = bus ?? ({ emit: async (e: never) => { events.push(e) } } as unknown as IEventBus)
  return new RuntimeContextCandidateService(
    { memory, bus: fakeBus, logger: quietLogger, fieldTelemetry: telemetry, fieldRanker },
    opts,
  )
}

async function waitFor(fn: () => boolean, timeoutMs = 2000): Promise<void> {
  const start = Date.now()
  while (!fn()) {
    if (Date.now() - start > timeoutMs) throw new Error('waitFor timed out')
    await new Promise(r => setTimeout(r, 5))
  }
}

describe('MnemicMemoryAdapter — read-only candidate lookup', () => {
  it('uses bounded literal FTS and propagates backend failures without retrieval telemetry', async () => {
    const retrieve = vi.fn(async () => { throw new Error('retrieve must not run') })
    const searchTextStrictAsync = vi.fn(async () => [{
      engram: {
        id: 'memory-1',
        content: 'prior retained fact',
        nodeType: 'fact',
        metadata: { sessionId: 'prior-session' },
      },
      score: 0.75,
    }])
    const adapter = new MnemicMemoryAdapter({ retrieve, searchTextStrictAsync } as never)

    await expect(adapter.searchReadOnly('ephemeral provider prompt', { limit: 1 })).resolves.toEqual([
      expect.objectContaining({ id: 'memory-1', content: 'prior retained fact', score: 0.75 }),
    ])
    expect(retrieve).not.toHaveBeenCalled()
    expect(searchTextStrictAsync).toHaveBeenCalledWith('"ephemeral" OR "provider" OR "prompt"', 2, 300)

    searchTextStrictAsync.mockRejectedValue(new Error('fts failed'))
    await expect(adapter.searchReadOnly('another prompt')).rejects.toThrow('fts failed')
  })
})

describe('RuntimeContextCandidateService — Mnemic candidates', () => {
  it('maps hits to typed candidates and applies same-session filtering', async () => {
    const { memory } = makeMemory(async () => [
      hit('a', 'alpha', 0.9, 'sess-1'),
      hit('b', 'beta', 0.8, 'sess-2'),
      hit('c', 'gamma', 0.7),
      hit('d', 'delta', 0.6, 'sess-1'),
    ])
    const svc = makeService(memory)

    const res = await svc.candidates(req({ limit: 3 }))
    expect(res.candidates.map(c => c.id)).toEqual(['b', 'c'])
    expect(res.candidates.every(c => c.source === 'mnemic')).toBe(true)
    expect(res.candidates.find(c => c.id === 'b')?.text).toBe('beta')
    expect(res.candidates.find(c => c.id === 'b')?.score).toBe(0.8)
    expect(res.candidates.find(c => c.id === 'b')?.sourceRefs).toEqual(['b'])
    expect(res.sources).toHaveLength(1)
    expect(res.sources[0]).toMatchObject({ source: 'mnemic', status: 'ready' })
    expect(typeof res.sources[0].latencyMs).toBe('number')
  })

  it('caps candidate count and returns bounded exact spans', async () => {
    const longContent = 'x'.repeat(500)
    const { memory } = makeMemory(async () => [
      hit('a', longContent, 0.9, 'prior-session'),
      hit('b', longContent, 0.8, 'prior-session'),
      hit('c', longContent, 0.7, 'prior-session'),
      hit('d', longContent, 0.6, 'prior-session'),
    ])
    const svc = makeService(memory, { maxCandidates: 2, maxCandidateChars: 100 })

    const res = await svc.candidates(req({ limit: 5 }))
    expect(res.candidates).toHaveLength(2)
    for (const candidate of res.candidates) {
      expect(Buffer.byteLength(candidate.text)).toBeLessThanOrEqual(100)
      expect(candidate.metadata?.exactSpan).toBe(true)
      expect(candidate.endByte! - candidate.startByte!).toBe(Buffer.byteLength(candidate.text))
    }
    const clamped = await svc.candidates(req({ limit: 999 }))
    expect(clamped.candidates.length).toBeLessThanOrEqual(2)
  })

  it('selects a query-bearing UTF-8 span with exact revision byte offsets', async () => {
    const content = `${'α'.repeat(20)}\nquiet section\nneedle 😀 payload\n${'ω'.repeat(20)}`
    const { memory } = makeMemory(async () => [
      { ...hit('unicode-record', content, 0.9, 'prior-session'), revision: 'a'.repeat(64) },
    ])
    const svc = makeService(memory, { maxCandidates: 4, maxCandidateChars: 24 })

    const res = await svc.candidates(req({ query: 'needle payload', limit: 4 }))
    const candidate = res.candidates[0]!
    const bytes = Buffer.from(content)
    expect(candidate.id).toMatch(/^span:[0-9a-f]{32}$/)
    expect(candidate.recordId).toBe('unicode-record')
    expect(candidate.revision).toBe('a'.repeat(64))
    expect(candidate.text).toContain('needle')
    expect(bytes.subarray(candidate.startByte, candidate.endByte).toString('utf8')).toBe(candidate.text)
  })

  it('truncates the query to the configured cap before Mnemic lookup', async () => {
    const { memory, calls } = makeMemory(async () => [])
    const svc = makeService(memory, { maxQueryChars: 8 })

    await svc.candidates(req({ query: 'abcdefghijkl' }))
    expect(calls[0].query).toBe('abcdefgh')
    expect(calls[0].sessionId).toBe('sess-1')
  })

  it('fails open with a static timeout status when the Mnemic deadline expires', async () => {
    const { memory } = makeMemory(async () => {
      await delay(150)
      return [hit('late', 'late result', 1, 'prior-session')]
    })
    const svc = makeService(memory)
    const started = Date.now()

    const res = await svc.candidates(req({ deadlineMs: 100 }))
    expect(Date.now() - started).toBeLessThan(1000)
    expect(res.candidates).toEqual([])
    expect(res.sources[0]).toMatchObject({
      source: 'mnemic',
      status: 'timeout',
      error: 'mnemic-deadline-exceeded',
    })
    expect(typeof res.sources[0].latencyMs).toBe('number')
  })

  it('reports a strict Mnemic backend failure instead of labelling it ready', async () => {
    const { memory } = makeMemory(async () => { throw new Error('fts unavailable with PRIVATE_QUERY') })
    const svc = makeService(memory)

    const res = await svc.candidates(req())
    expect(res.candidates).toEqual([])
    expect(res.sources[0]).toMatchObject({
      source: 'mnemic',
      status: 'error',
      error: 'mnemic-search-failed',
    })
    expect(JSON.stringify(res.sources)).not.toContain('PRIVATE_QUERY')
  })

  it('rejects malformed requests with 400 ContextRequestError', async () => {
    const { memory } = makeMemory(async () => [])
    const svc = makeService(memory)

    const bad: Array<Partial<ContextCandidatesRequest>> = [
      {}, // everything missing
      { sessionId: 's' }, // no turnId/query
      { sessionId: 's', turnId: 1 }, // no query
      { ...req(), query: '  ' }, // blank query
      { ...req(), limit: 'x' as never }, // wrong limit type
      { ...req(), limit: 0 }, // out of range
      { ...req(), includeFieldShadow: 'yes' as never }, // wrong boolean
    ]
    for (const b of bad) {
      await expect(svc.candidates(b as ContextCandidatesRequest)).rejects.toMatchObject({ statusCode: 400 })
    }

    const badFeedback: Array<Partial<ContextFeedbackRequest>> = [
      {},
      { ...feedback(), includedCandidateIds: null as never },
      { ...feedback(), includedCandidateIds: [1 as never] },
      { ...feedback(), planId: '  ' },
      { ...feedback(), outcome: 'maybe' as never },
      {
        ...feedback(),
        toolResult: { id: 'tc-1', name: 'bash', isError: true },
      },
      {
        ...feedback({ outcome: 'error' }),
        toolResult: { id: 'tc-1', name: 'bash', isError: true, text: 'forbidden' } as never,
      },
    ]
    for (const b of badFeedback) {
      await expect(svc.feedback(b as ContextFeedbackRequest)).rejects.toMatchObject({ statusCode: 400 })
    }
  })
})

describe('RuntimeContextCandidateService — field ranking', () => {
  it('lets the live field reorder Mnemic candidates without adding ranking state', async () => {
    const { memory } = makeMemory(async () => [
      hit('fts-first', 'lexically first', 0.9, 'prior-session'),
      hit('field-first', 'field continuation', 0.5, 'prior-session'),
    ])
    const fieldRanker = vi.fn<ContextFieldRanker>(async request => {
      expect(request.sessionId).toBe('sess-1')
      expect(request.query).toBe('golden thought')
      expect(request.candidates.map(candidate => candidate.id)).toEqual(['fts-first', 'field-first'])
      return {
        ranked: [
          { id: 'field-first', score: 0.95 },
          { id: 'fts-first', score: 0.1 },
        ],
        working: [],
      }
    })
    const svc = makeService(memory, {}, undefined, undefined, fieldRanker)

    const response = await svc.candidates(req())

    expect(response.candidates.map(candidate => candidate.id)).toEqual(['field-first', 'fts-first'])
    expect(response.candidates.map(candidate => candidate.score)).toEqual([0.95, 0.1])
    expect(response.sources[1]).toMatchObject({ source: 'field', status: 'ready' })
    expect(fieldRanker).toHaveBeenCalledOnce()
  })

  it.each([
    {
      name: 'provider failure',
      ranker: (async () => { throw new Error('provider unavailable') }) as ContextFieldRanker,
      status: 'error',
    },
    {
      name: 'provider timeout',
      ranker: (async () => {
        await delay(150)
        return { ranked: [], working: [] }
      }) as ContextFieldRanker,
      status: 'timeout',
    },
  ])('keeps deterministic FTS order on $name', async ({ ranker, status }) => {
    const { memory } = makeMemory(async () => [
      hit('a', 'alpha', 0.9, 'prior-session'),
      hit('b', 'beta', 0.8, 'prior-session'),
    ])
    const svc = makeService(memory, {}, undefined, undefined, ranker)

    const response = await svc.candidates(req({ deadlineMs: 100 }))

    expect(response.candidates.map(candidate => candidate.id)).toEqual(['a', 'b'])
    expect(response.candidates.map(candidate => candidate.score)).toEqual([0.9, 0.8])
    expect(response.sources[1]).toMatchObject({ source: 'field', status })
  })
})

  it('merges field-owned work while persisting only record-backed eligibility', async () => {
    const { memory, feedbackEvents } = makeMemory(async () => [
      hit('memory-a', 'stored memory', 0.8, 'prior-session'),
    ])
    const fieldRanker = vi.fn<ContextFieldRanker>(async () => ({
      ranked: [{ id: 'memory-a', score: 0.2 }],
      working: [{
        id: 'working:artifact:a',
        revision: 'a'.repeat(64),
        source: 'field',
        text: 'tool pytest artifact tc-1',
        score: 0.9,
        sourceRefs: ['working:artifact:a'],
        workingKind: 'artifact',
      }],
    }))
    const svc = makeService(memory, {}, undefined, undefined, fieldRanker)

    const response = await svc.candidates(req())
    expect(response.candidates.map(candidate => candidate.id)).toEqual([
      'working:artifact:a',
      'memory-a',
    ])
    expect(response.candidates[0]).toMatchObject({
      source: 'field',
      workingKind: 'artifact',
      score: 0.9,
    })

    await svc.feedback(feedback({
      includedCandidateIds: ['working:artifact:a', 'memory-a'],
    }))
    expect(feedbackEvents[0].candidates).toMatchObject([{ id: 'memory-a' }])
  })

describe('RuntimeContextCandidateService — field shadow', () => {
  it('first miss returns null advisory + schedules a refresh; next hit returns the cached advisory', async () => {
    const { memory } = makeMemory(async () => [hit('a', 'alpha', 0.9, 'prior-session')])
    const { telemetry, readCount } = makeTelemetry({ result: () => shadowSnapshot(42), delayMs: 20 })
    const svc = makeService(memory, {}, telemetry)

    const first = await svc.candidates(req({ includeFieldShadow: true }))
    expect(first.fieldAdvisory).toBeNull()
    expect(first.sources[1]).toMatchObject({ source: 'field', status: 'offline' })
    expect(readCount()).toBe(1)

    await waitFor(() => svc.status().cachedFieldShadow.available)

    const second = await svc.candidates(req({ includeFieldShadow: true }))
    expect(second.fieldAdvisory).not.toBeNull()
    expect(second.fieldAdvisory?.mode).toBe('shadow')
    expect(second.fieldAdvisory?.step).toBe(42)
    expect(second.fieldAdvisory?.time).toBe(1.5)
    expect(second.fieldAdvisory?.balance).toEqual({ meanRho: 0.1, meanEpsilon: 0.2, meanFieldPower: 0.9, meanCoherence: 0.7 })
    expect(second.fieldAdvisory?.temporal).toEqual({ resultant: 0.8, weightedMeanAbsoluteIncrement: 0.3, samples: 64 })
    expect(second.fieldAdvisory?.jProxy).toEqual({ rms: 0.5, samples: 192 })
    expect(second.fieldAdvisory?.helical).toMatchObject({
      canonicalSpiral: false,
      bestValue: 0.9,
      bestAxis: 'x',
      bestMode: 2,
      samples: 64,
    })
    expect(typeof second.fieldAdvisory?.observedAt).toBe('number')
    expect(second.sources[1]).toMatchObject({ source: 'field', status: 'ready' })
    // The shadow never alters candidate scores.
    expect(second.candidates[0].score).toBe(0.9)
    // No second read needed for the cached hit.
    expect(readCount()).toBe(1)
  })

  it('coalesces concurrent refresh triggers to a single read; refreshes again once free', async () => {
    const { memory } = makeMemory(async () => [])
    const { telemetry, readCount } = makeTelemetry({ result: () => shadowSnapshot(), delayMs: 40 })
    const svc = makeService(memory, { fieldShadowMinRefreshIntervalMs: 0, fieldShadowMaxAgeMs: 0 }, telemetry)

    await Promise.all([
      svc.candidates(req({ includeFieldShadow: true })),
      svc.candidates(req({ includeFieldShadow: true })),
      svc.candidates(req({ includeFieldShadow: true })),
      svc.feedback(feedback()),
    ])
    expect(readCount()).toBe(1)

    await waitFor(() => !svc.status().refreshInFlight)
    await svc.candidates(req({ includeFieldShadow: true }))
    expect(readCount()).toBe(2)
  })

  it('never makes candidate responses wait on a fresh 7599 read', async () => {
    const { memory } = makeMemory(async () => [hit('a', 'alpha', 0.9, 'sess-1')])
    const { telemetry } = makeTelemetry({ result: () => shadowSnapshot(), delayMs: 150 })
    const svc = makeService(memory, {}, telemetry)

    const started = Date.now()
    await svc.candidates(req({ includeFieldShadow: true }))
    expect(Date.now() - started).toBeLessThan(100)
  })

  it('degrades offline without touching candidate results', async () => {
    const hits = [hit('a', 'alpha', 0.9, 'prior-session'), hit('b', 'beta', 0.8, 'prior-session')]
    const { memory } = makeMemory(async () => hits)
    const { telemetry } = makeTelemetry({ result: () => null, connected: false })
    const svc = makeService(memory, {}, telemetry)

    const withShadow = await svc.candidates(req({ includeFieldShadow: true }))
    expect(withShadow.fieldAdvisory).toBeNull()
    expect(withShadow.sources[1]).toMatchObject({ source: 'field', status: 'offline' })
    expect(withShadow.sources[1].error).toContain('offline')

    const withoutShadow = await svc.candidates(req())
    expect(withoutShadow.fieldAdvisory).toBeNull()
    expect(withoutShadow.candidates).toEqual(withShadow.candidates)
    expect(withShadow.candidates.map(c => c.score)).toEqual([0.9, 0.8])
  })
})

describe('RuntimeContextCandidateService — feedback', () => {
  it('acks, publishes an ID-only outcome event, and never writes raw text', async () => {
    const events: unknown[] = []
    const bus = { emit: async (e: never) => { events.push(e) } } as unknown as IEventBus
    const { memory, feedbackEvents } = makeMemory(async () => [
      hit('id-1', 'selected exact memory', 0.9, 'prior-session'),
      hit('id-x', 'unused exact memory', 0.8, 'prior-session'),
    ])
    const { telemetry, readCount } = makeTelemetry({ result: () => shadowSnapshot(), delayMs: 10 })
    const svc = makeService(memory, {}, telemetry, bus)
    await svc.candidates(req())

    const res = await svc.feedback(feedback({
      includedCandidateIds: ['id-1', 'id-2'],
      outcome: 'error',
      toolResult: { id: 'tc-1', name: 'pytest', isError: true },
    }))
    expect(res).toEqual({ ack: true })

    const ev = events[0] as Record<string, unknown>
    expect(ev.type).toBe('cassi.context.feedback')
    expect(ev.sessionId).toBe('sess-1')
    expect(ev.turnId).toBe(1)
    expect(ev.planId).toBe('plan-1')
    expect(ev.includedCandidateIds).toEqual(['id-1', 'id-2'])
    expect(ev.outcome).toBe('error')
    expect(ev.toolResult).toEqual({ id: 'tc-1', name: 'pytest', isError: true })
    expect(ev.timestamp).toBeInstanceOf(Date)
    // ID-only: no transcript text ever enters the event.
    for (const forbidden of ['content', 'text', 'query']) {
      expect(Object.keys(ev)).not.toContain(forbidden)
    }
    expect(feedbackEvents).toEqual([{
      sessionId: 'sess-1',
      query: 'golden thought',
      candidates: [{
        id: 'id-1',
        recordId: 'id-1',
        startByte: 0,
        endByte: Buffer.byteLength('selected exact memory'),
        text: 'selected exact memory',
        revision: expect.stringMatching(/^[0-9a-f]{64}$/),
      }],
      outcome: 'error',
      toolResult: { id: 'tc-1', name: 'pytest', isError: true },
    }])

    // Feedback with an empty cache triggers the next cached field refresh.
    expect(readCount()).toBe(1)
    await waitFor(() => svc.status().cachedFieldShadow.available)
  })

  it('does not fabricate retrieval outcomes and acks even when the bus throws', async () => {
    const { memory } = makeMemory(async () => [])
    const bus = { emit: async () => { throw new Error('bus down') } } as unknown as IEventBus
    const svc = makeService(memory, {}, undefined, bus)

    await expect(svc.feedback(feedback({ includedCandidateIds: [] }))).resolves.toEqual({ ack: true })
  })
})

describe('RuntimeContextCandidateService — exact actions', () => {
  it('writes the start before accepting its matching text-free outcome', async () => {
    const startActionEpisode = vi.fn()
    const finishActionEpisode = vi.fn()
    const memory: ContextMemorySurface = {
      searchReadOnly: async () => [],
      startActionEpisode,
      finishActionEpisode,
    }
    const svc = makeService(memory)
    const start: ContextActionRequest = {
      operation: 'start',
      sessionId: 'sess-1',
      turnId: 3,
      planId: 'plan-3',
      toolCallId: 'call-3',
      toolName: 'read',
      argumentsSha256: 'a'.repeat(64),
      requiredAuthority: 0.8,
      reversible: true,
    }

    await expect(svc.action(start)).resolves.toEqual({ ack: true })
    expect(startActionEpisode).toHaveBeenCalledWith({
      contextSessionId: 'sess-1',
      turnId: 3,
      planId: 'plan-3',
      toolCallId: 'call-3',
      toolName: 'read',
      argumentsSha256: 'a'.repeat(64),
      requiredAuthority: 0.8,
      reversible: true,
    })
    await expect(svc.action({
      operation: 'outcome',
      sessionId: 'sess-1',
      turnId: 3,
      planId: 'plan-3',
      toolCallId: 'call-3',
      isError: false,
    })).resolves.toEqual({ ack: true })
    expect(finishActionEpisode).toHaveBeenCalledWith({
      contextSessionId: 'sess-1',
      turnId: 3,
      planId: 'plan-3',
      toolCallId: 'call-3',
      isError: false,
    })
  })

  it('rejects malformed action provenance before touching exact memory', async () => {
    const startActionEpisode = vi.fn()
    const svc = makeService({
      searchReadOnly: async () => [],
      startActionEpisode,
    })
    await expect(svc.action({
      operation: 'start',
      sessionId: 'sess-1',
      turnId: 1,
      planId: 'plan-1',
      toolCallId: 'call-1',
      toolName: 'read',
      argumentsSha256: 'not-a-digest',
      requiredAuthority: 0.8,
      reversible: true,
    })).rejects.toMatchObject({ statusCode: 400 })
    expect(startActionEpisode).not.toHaveBeenCalled()
  })
})
