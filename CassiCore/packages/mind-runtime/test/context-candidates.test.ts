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
  type ContextFieldRecaller,
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

/** Fake exact manifest plus field recall with durable-turn semantics. */
type TestMemory = ContextMemorySurface & { fieldRecall: ContextFieldRecaller }

function makeMemory(
  impl: (query: string, opts?: { limit?: number; sessionId?: string; deadlineMs?: number }) => Promise<MemoryHitView[]>,
): {
  memory: TestMemory
  addresses: string[]
  calls: Array<{ query: string; limit?: number; sessionId?: string }>
  feedbackEvents: Array<Record<string, unknown>>
  manifestSessions: string[]
} {
  const addresses = Array.from(
    { length: 32 },
    (_, index) => (index + 1).toString(16).padStart(32, '0'),
  )
  const calls: Array<{ query: string; limit?: number; sessionId?: string }> = []
  const feedbackEvents: Array<Record<string, unknown>> = []
  const manifestSessions: string[] = []
  const resolved = new Map<string, MemoryHitView>()
  const eligibility = new Map<string, {
    query: string
    candidates: ReadonlyArray<{
      id: string
      recordId: string
      startByte: number
      endByte: number
      text: string
      revision: string
      fieldAddress?: string
    }>
  }>()
  const memory: TestMemory = {
    fieldAddressManifest: sessionId => {
      manifestSessions.push(sessionId)
      return addresses
    },
    resolveFieldAddress: address => resolved.get(address) ?? null,
    fieldRecall: async request => {
      calls.push({
        query: request.query,
        limit: request.addresses.length,
        sessionId: request.sessionId,
      })
      const hits = await impl(request.query, {
        limit: request.addresses.length,
        sessionId: request.sessionId,
        deadlineMs: request.deadlineMs,
      })
      resolved.clear()
      let selected: MemoryHitView | null = null
      for (const [index, value] of hits.entries()) {
        const address = addresses[index]!
        const recalled = { ...value, fieldAddress: address }
        resolved.set(address, recalled)
        if (!selected && value.metadata?.sessionId !== request.sessionId) {
          selected = recalled
        }
      }
      return {
        address: selected?.fieldAddress ?? null,
        signal: selected?.score ?? 0,
        selectionMargin: selected ? 1 : 0,
        availability: selected ? 1 : 0,
      }
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
  }
  return { memory, addresses, calls, feedbackEvents, manifestSessions }
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
  fieldRecall?: ContextFieldRecaller,
): RuntimeContextCandidateService {
  const events: unknown[] = []
  const fakeBus = bus ?? ({ emit: async (e: never) => { events.push(e) } } as unknown as IEventBus)
  return new RuntimeContextCandidateService(
    {
      memory,
      bus: fakeBus,
      logger: quietLogger,
      fieldTelemetry: telemetry,
      fieldRecall: fieldRecall ?? (memory as Partial<TestMemory>).fieldRecall,
    },
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
  it('returns the whole exact record selected by field address', async () => {
    const { memory, manifestSessions } = makeMemory(async () => [
      hit('a', 'alpha', 0.9, 'sess-1'),
      hit('b', 'beta', 0.8, 'sess-2'),
      hit('c', 'gamma', 0.7),
    ])
    const svc = makeService(memory)

    const res = await svc.candidates(req({ limit: 3 }))
    expect(res.candidates.map(candidate => candidate.id)).toEqual(['b'])
    expect(manifestSessions).toEqual(['sess-1'])
    expect(res.candidates[0]).toMatchObject({
      source: 'mnemic',
      text: 'beta',
      score: 0.8,
      sourceRefs: ['b'],
      fieldAddress: expect.stringMatching(/^[0-9a-f]{32}$/),
    })
    expect(res.sources).toHaveLength(1)
    expect(res.sources[0]).toMatchObject({ source: 'mnemic', status: 'ready' })
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
      error: 'field-recall-deadline-exceeded',
    })
    expect(typeof res.sources[0].latencyMs).toBe('number')
  })

  it('reports a strict Mnemic backend failure instead of labelling it ready', async () => {
    const { memory } = makeMemory(async () => { throw new Error('field unavailable with PRIVATE_QUERY') })
    const svc = makeService(memory)

    const res = await svc.candidates(req())
    expect(res.candidates).toEqual([])
    expect(res.sources[0]).toMatchObject({
      source: 'mnemic',
      status: 'error',
      error: 'field-recall-failed',
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

describe('RuntimeContextCandidateService — field-native recall', () => {
  it('resolves only the opaque address selected by the field', async () => {
    const { memory, addresses } = makeMemory(async () => [
      hit('first', 'first exact record', 0.9, 'prior-session'),
      hit('selected', 'field-selected record', 0.5, 'prior-session'),
    ])
    const fieldRecall = vi.fn<ContextFieldRecaller>(async request => {
      expect(request.query).toBe('golden thought')
      expect(request.addresses).toEqual(addresses)
      const selected = await memory.fieldRecall(request)
      return { ...selected, address: addresses[1]!, signal: 0.95 }
    })
    const svc = makeService(memory, {}, undefined, undefined, fieldRecall)

    const response = await svc.candidates(req())

    expect(response.candidates.map(candidate => candidate.id)).toEqual(['selected'])
    expect(response.candidates[0]?.score).toBe(0.95)
    expect(response.sources).toEqual([
      expect.objectContaining({ source: 'mnemic', status: 'ready' }),
    ])
    expect(fieldRecall).toHaveBeenCalledOnce()
  })

  it('rejects a field address omitted from the exact request manifest', async () => {
    const eligible = '1'.repeat(32)
    const omitted = '2'.repeat(32)
    const resolveFieldAddress = vi.fn(() => hit('omitted', 'must not resolve', 1, 'prior-session'))
    const memory: ContextMemorySurface = {
      fieldAddressManifest: sessionId => {
        expect(sessionId).toBe('sess-1')
        return [eligible]
      },
      resolveFieldAddress,
    }
    const fieldRecall = vi.fn<ContextFieldRecaller>(async request => {
      expect(request.addresses).toEqual([eligible])
      return { address: omitted, signal: 1, selectionMargin: 1, availability: 1 }
    })
    const svc = makeService(memory, {}, undefined, undefined, fieldRecall)

    const response = await svc.candidates(req())

    expect(response.candidates).toEqual([])
    expect(response.sources[0]).toMatchObject({ source: 'mnemic', status: 'error' })
    expect(resolveFieldAddress).not.toHaveBeenCalled()
  })

  it('rejects a selected address whose exact record becomes current-session ineligible', async () => {
    const eligible = '1'.repeat(32)
    const memory: ContextMemorySurface = {
      fieldAddressManifest: () => [eligible],
      resolveFieldAddress: () => hit('current', 'current-session record', 1, 'sess-1'),
    }
    const fieldRecall = vi.fn<ContextFieldRecaller>(async () => ({
      address: eligible,
      signal: 1,
      selectionMargin: 1,
      availability: 1,
    }))
    const svc = makeService(memory, {}, undefined, undefined, fieldRecall)

    const response = await svc.candidates(req())

    expect(response.candidates).toEqual([])
    expect(response.sources[0]).toMatchObject({ source: 'mnemic', status: 'error' })
  })

  it.each([
    {
      name: 'provider failure',
      recall: (async () => { throw new Error('provider unavailable') }) as ContextFieldRecaller,
      status: 'error',
    },
    {
      name: 'provider timeout',
      recall: (async () => {
        await delay(150)
        return { address: null, signal: 0, selectionMargin: 0, availability: 0 }
      }) as ContextFieldRecaller,
      status: 'timeout',
    },
  ])('returns no memory instead of bypassing the field on $name', async ({ recall, status }) => {
    const { memory } = makeMemory(async () => [
      hit('a', 'alpha', 0.9, 'prior-session'),
    ])
    const svc = makeService(memory, {}, undefined, undefined, recall)

    const response = await svc.candidates(req({ deadlineMs: 100 }))

    expect(response.candidates).toEqual([])
    expect(response.sources[0]).toMatchObject({ source: 'mnemic', status })
  })
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
    expect(withShadow.candidates.map(candidate => candidate.score)).toEqual([0.9])
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
        fieldAddress: expect.stringMatching(/^[0-9a-f]{32}$/),
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
      fieldAddressManifest: () => [],
      resolveFieldAddress: () => null,
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
      fieldAddressManifest: () => [],
      resolveFieldAddress: () => null,
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
