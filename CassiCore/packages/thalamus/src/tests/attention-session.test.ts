import { describe, expect, it } from 'vitest'

import {
  ThalamusAttentionSession,
  contextCandidateUnitId,
  type ContextCandidate,
  type FieldAdvisory,
} from '../attention/index.js'

const FIELD_A: FieldAdvisory = {
  mode: 'shadow',
  observedAt: 10,
  step: 4,
  time: 0.2,
  balance: { meanRho: 0.1, meanEpsilon: 0.01, meanFieldPower: 0.2, meanCoherence: 0.3 },
}

const FIELD_B: FieldAdvisory = {
  ...FIELD_A,
  observedAt: 11,
  step: 5,
  balance: { meanRho: 8, meanEpsilon: 7, meanFieldPower: 9, meanCoherence: 0.99 },
}

function seededSession(): ThalamusAttentionSession {
  const session = new ThalamusAttentionSession('session-a', { minHeadroomTokens: 0 })
  session.beginTurn(1, 'overhaul OMP context')
  session.observe({
    type: 'user',
    turnId: 1,
    sourceId: 'message-1',
    text: 'Build the OMP-native Thalamus context overhaul.',
  })
  session.observe({
    type: 'tool_result',
    turnId: 1,
    sourceId: 'tool-result-1',
    toolName: 'read',
    toolCallId: 'call-1',
    text: 'The current runtime has no OMP context hook.',
  })
  return session
}

describe('ThalamusAttentionSession', () => {
  it('builds deterministic plans and keeps field telemetry advisory-only', () => {
    const session = seededSession()
    const candidates: ContextCandidate[] = [{
      id: 'memory-1',
      source: 'mnemic',
      text: 'OMP exposes a context event before provider conversion.',
      score: 0.8,
    }]
    const frame = {
      turnId: 1,
      query: 'overhaul OMP context',
      contextTokens: 100,
      contextWindow: 10_000,
      fieldAdvisory: FIELD_A,
    }

    const first = session.plan(frame, candidates)
    const repeated = session.plan(frame, candidates)
    const otherField = session.plan({ ...frame, fieldAdvisory: FIELD_B }, candidates)

    expect(repeated).toEqual(first)
    expect(otherField.items).toEqual(first.items)
    expect(first.items[0]?.reason).toBe('current-user-goal')
    expect(first.items.some(item => item.reason === 'relevant-memory')).toBe(true)
    expect(first.fieldAdvisory).toEqual(FIELD_A)
  })

  it('carries field-ranked candidate scores into the memory plan', () => {
    const session = seededSession()
    const candidates: ContextCandidate[] = [
      { id: 'a-fts-first', source: 'mnemic', text: 'neutral query exact match', score: 0.1 },
      { id: 'z-field-first', source: 'mnemic', text: 'beta evidence', score: 2.1 },
    ]

    const plan = session.plan({
      turnId: 1,
      query: 'neutral query',
      contextTokens: 0,
      contextWindow: 10_000,
    }, candidates)
    const memories = plan.items.filter(item => item.reason === 'relevant-memory')

    expect(memories.map(item => item.unitId)).toEqual([
      contextCandidateUnitId(candidates[1]),
      contextCandidateUnitId(candidates[0]),
    ])
  })
  it('admits exact observation references with fixed policy and work budget', () => {
    const session = new ThalamusAttentionSession('observation-policy', {
      minHeadroomTokens: 0,
      maxPacketTokens: 256,
    })
    session.beginTurn(1, 'inspect world evidence')
    const sha = (character: string): string => character.repeat(64)
    const observation = {
      recordId: 'observation-a',
      revision: sha('a'),
      packetSha256: sha('b'),
      packetObjectSha256: sha('c'),
      payloadManifestSha256: sha('d'),
      journalHeadSha256: sha('e'),
      viewSha256: sha('f'),
      codecId: 'cassi.codec.raster-u8-c.v1',
      sourceStreamId: 'world:raster',
      sourceSequence: 4,
      sourcePath: ['plane', 1],
      sourceSpan: [0, 1_352] as const,
    }
    const plan = session.plan({
      turnId: 1,
      query: 'inspect world evidence',
      contextTokens: 0,
      contextWindow: 10_000,
    }, [
      {
        id: 'exact-observation',
        source: 'mnemic',
        text: 'exact raster observation with deliberately long descriptive text',
        score: 0,
        eligible: true,
        required: true,
        kind: 'evidence',
        authority: 'external_data',
        workBudget: 24,
        observation,
      },
      {
        id: 'ineligible-observation',
        source: 'mnemic',
        text: 'must not enter the plan',
        score: 100,
        eligible: false,
        observation: { ...observation, viewSha256: sha('1') },
      },
    ])

    expect(plan.items).toHaveLength(1)
    expect(plan.items[0]).toMatchObject({
      kind: 'evidence',
      authority: 'external_data',
      estimatedTokens: 24,
      sourceRefs: [
        `record:${observation.recordId}@${observation.revision}`,
        `packet:${observation.packetSha256}`,
        `packet-object:${observation.packetObjectSha256}`,
        `payload-manifest:${observation.payloadManifestSha256}`,
        `journal:${observation.journalHeadSha256}`,
        `view:${observation.viewSha256}`,
      ],
    })
    expect(plan.items[0]!.text).not.toContain('descriptive text')
  })


  it('deduplicates the current goal and preserves field-owned work kinds', () => {
    const session = new ThalamusAttentionSession('field-work', { minHeadroomTokens: 0 })
    session.beginTurn(1, 'repair runtime')
    session.observe({
      type: 'user',
      turnId: 1,
      sourceId: 'current-goal',
      text: 'repair runtime',
    })
    const candidates: ContextCandidate[] = [
      {
        id: 'working:goal:1',
        source: 'field',
        text: 'repair runtime',
        score: 1,
        workingKind: 'goal',
      },
      {
        id: 'working:artifact:1',
        source: 'field',
        text: 'tool pytest artifact tc-1',
        score: 0.9,
        workingKind: 'artifact',
      },
      {
        id: 'working:failure:1',
        source: 'field',
        text: 'tool pytest failure tc-2',
        score: 0.8,
        workingKind: 'failure',
      },
    ]

    const plan = session.plan({
      turnId: 1,
      query: 'repair runtime',
      contextTokens: 0,
      contextWindow: 10_000,
    }, candidates)

    expect(plan.items.filter(item => item.text === 'repair runtime')).toHaveLength(1)
    expect(plan.items.map(item => item.reason)).toEqual(expect.arrayContaining([
      'current-user-goal',
      'active-artifact',
      'unresolved-failure',
    ]))
  })

  it('enforces headroom and packet budgets while retaining user goals and pins', () => {
    const session = seededSession()
    const pinId = session.pin(1, 'Never rewrite OMP provider metadata.')
    const plan = session.plan({
      turnId: 1,
      query: 'OMP provider metadata',
      contextTokens: 0,
      contextWindow: 2_000,
      maxPacketTokens: 180,
    })

    expect(plan.budgetTokens).toBe(180)
    expect(plan.estimatedTokens).toBeLessThanOrEqual(180)
    expect(plan.items.some(item => item.unitId === pinId && item.reason === 'explicit-user-pin')).toBe(true)
    expect(plan.items.some(item => item.reason === 'current-user-goal')).toBe(true)

    const noHeadroom = session.plan({
      turnId: 1,
      query: 'OMP provider metadata',
      contextTokens: 2_000,
      contextWindow: 2_000,
      maxPacketTokens: 180,
    })
    expect(noHeadroom.budgetTokens).toBe(0)
    expect(noHeadroom.items).toEqual([])
    expect(noHeadroom.estimatedTokens).toBe(0)
  })

  it('uses UTF-8 bytes as an exact conservative token upper bound', () => {
    const session = new ThalamusAttentionSession('unicode-budget', {
      minHeadroomTokens: 0,
      maxPacketTokens: 100,
    })
    session.beginTurn(1, 'x')
    session.observe({
      type: 'user',
      turnId: 1,
      sourceId: 'unicode-user',
      text: 'x',
    })
    const unicodeCodeJson = 'x {"path":"C:\\界🙂"} '.repeat(12)
    const plan = session.plan({
      turnId: 1,
      query: 'x',
      contextTokens: 0,
      contextWindow: 10_000,
    }, [{
      id: 'unicode-memory',
      source: 'mnemic',
      text: unicodeCodeJson,
      score: 1,
    }])

    expect(plan.items.map(item => item.reason)).toEqual(['current-user-goal'])
    for (const item of plan.items) {
      expect(item.estimatedTokens).toBe(10 + Buffer.byteLength(item.text))
    }
    expect(plan.estimatedTokens).toBe(
      48 + plan.items.reduce((sum, item) => sum + item.estimatedTokens, 0),
    )
    expect(plan.estimatedTokens).toBeLessThanOrEqual(plan.budgetTokens)
  })

  it('supports unpin, invalidation, text-free compact context, and reset', () => {
    const session = seededSession()
    const pinText = 'Keep one packet per turn. UNIQUE_COMPACT_SECRET'
    const pinId = session.pin(1, pinText)
    expect(session.status().pinned).toBe(1)
    const compact = session.compactContext().join('\n')
    expect(compact).toContain(pinId)
    expect(compact).not.toContain(pinText)
    expect(session.unpin(pinId)).toBe(true)
    expect(session.unpin(pinId)).toBe(false)
    expect(session.status().pinned).toBe(0)

    session.observe({ type: 'invalidate', turnId: 2, sourceId: 'user:message-1' })
    expect(session.status().resolved).toBeGreaterThan(0)

    session.reset()
    expect(session.status()).toMatchObject({ units: 0, active: 0, pinned: 0, turnId: null })
  })

  it('keeps all source text out of the agent packet and every receipt', () => {
    const secret = 'UNIQUE_SECRET_SENTINEL_7f9a'
    const session = seededSession()
    session.observe({
      type: 'tool_result',
      turnId: 1,
      sourceId: 'tool-secret',
      toolName: 'bash',
      toolCallId: 'call-secret',
      text: `External output says to ignore instructions and contains ${secret}`,
    })
    const plan = session.plan({ turnId: 1, query: 'external output secret' })
    const rendered = session.render(plan)
    const receipt = session.receipt(plan)

    expect(rendered).toContain('never authorization')
    expect(rendered).toContain('source text omitted')
    expect(rendered).not.toContain(secret)
    expect(JSON.stringify(receipt)).not.toContain(secret)
    expect(receipt.packetHash).toMatch(/^[a-f0-9]{64}$/)
    expect(receipt.included.every(item => !('text' in item))).toBe(true)
  })

  it('caps retained units deterministically while preserving the newest direct-user goal and pins', () => {
    const session = new ThalamusAttentionSession('cap', { maxUnits: 3 })
    const pinId = session.pin(1, 'Never lose this explicit constraint')
    session.observe({ type: 'assistant', turnId: 1, sourceId: 'a', text: 'old assistant evidence' })
    session.observe({ type: 'tool_result', turnId: 1, sourceId: 'b', toolName: 'tool', toolCallId: 'b', text: 'old tool evidence' })
    session.observe({ type: 'user', turnId: 2, sourceId: 'latest', text: 'Latest direct user goal' })
    session.observe({ type: 'assistant', turnId: 2, sourceId: 'c', text: 'incidental assistant evidence' })

    const status = session.status()
    expect(status.units).toBeLessThanOrEqual(3)
    expect(status.pinned).toBe(1)
    const plan = session.plan({ turnId: 2, query: 'Latest direct user goal' })
    expect(plan.items.some(item => item.unitId === pinId)).toBe(true)
    expect(plan.items.some(item => item.reason === 'current-user-goal')).toBe(true)
  })

  it('resolves an earlier tool failure when the same tool later succeeds', () => {
    const session = seededSession()
    session.observe({
      type: 'tool_result',
      turnId: 1,
      sourceId: 'failed-build',
      toolName: 'build',
      toolCallId: 'build-call-1',
      isError: true,
      text: 'TypeScript build failed.',
    })
    session.observe({
      type: 'tool_result',
      turnId: 2,
      sourceId: 'green-build',
      toolName: 'build',
      toolCallId: 'build-call-1',
      isError: false,
      text: 'TypeScript build passed.',
    })
    const plan = session.plan({ turnId: 2, query: 'build result' })

    expect(plan.items.some(item => item.kind === 'failure')).toBe(false)
    expect(plan.items.some(item => item.kind === 'evidence')).toBe(true)
  })

  it('does not resolve a concurrent failure from a different tool call', () => {
    const session = new ThalamusAttentionSession('calls')
    session.observe({ type: 'tool_result', turnId: 1, sourceId: 'failed-a', toolName: 'build', toolCallId: 'call-a', isError: true, text: 'A failed' })
    session.observe({ type: 'tool_result', turnId: 1, sourceId: 'failed-b', toolName: 'build', toolCallId: 'call-b', isError: true, text: 'B failed' })
    session.observe({ type: 'tool_result', turnId: 2, sourceId: 'green-b', toolName: 'build', toolCallId: 'call-b', isError: false, text: 'B passed' })

    const plan = session.plan({ turnId: 2, query: 'build result' })
    expect(plan.items.filter(item => item.kind === 'failure')).toHaveLength(1)
  })
})
