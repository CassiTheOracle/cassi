import { createHash } from 'node:crypto'
import { once } from 'node:events'
import { createServer } from 'node:http'

import type { ILogger } from '@cassicore/foundation'
import { MnemicExactStore } from '@cassicore/mnemic-field'
import { describe, expect, it } from 'vitest'

import { createHttpContextFieldClient } from '../src/context/candidates.js'

const logger: ILogger = {
  debug: () => {}, info: () => {}, warn: () => {}, error: () => {},
  child: () => logger,
}

function counterflowAddress(
  id: string,
  revision: string,
  endByte: number,
  semanticKind: string,
): string {
  return createHash('sha256')
    .update(JSON.stringify([
      'cassicore.mnemic.counterflow-address.v1',
      id,
      revision,
      0,
      endByte,
      semanticKind,
    ]))
    .digest()
    .subarray(0, 16)
    .toString('hex')
}

interface FieldCandidateBody {
  id: string
  record_id: string
  start_byte: number
  end_byte: number
  text: string
  revision: string
}

interface MemoryPayloadBody {
  kind: 'memory'
  record: { content: string }
}

interface FeedbackPayloadBody {
  kind: 'feedback'
  query: string
  candidates: FieldCandidateBody[]
}

interface CounterflowIdentityBody {
  address: string
  revision: string
  start_byte: number
  end_byte: number
  semantic_kind: string
}

interface CounterflowObservationBody {
  id: string
  before: CounterflowIdentityBody
  after: CounterflowIdentityBody
  symbol: string
  outcome?: 'completed' | 'error'
  action?: Record<string, unknown>
}

interface TestRequestBody {
  user: string
  stream_id?: string
  sequence?: number
  previous_event_id?: string
  event_id?: string
  payload?: MemoryPayloadBody | FeedbackPayloadBody
  query?: string
  candidates?: FieldCandidateBody[]
  observations?: CounterflowObservationBody[]
  observation?: CounterflowObservationBody
  acknowledgment?: {
    stream_id: string
    sequence: number
    event_id: string
    status: 'committed' | 'completed' | 'error'
    before_revision: string
    after_revision: string
    authorization_path: string[]
  }
  current?: CounterflowIdentityBody
  expected?: CounterflowIdentityBody
  observed_outcome?: 'completed' | 'error'
  trajectory?: Array<CounterflowIdentityBody & {
    mask: number[]
    authority: number
    required: boolean
  }>
  policy?: Record<string, unknown>
}

async function startFieldServer(
  dropFirstObservation = false,
  dropFirstCounterflow = false,
  counterflowFailure?: { status: number; message: string },
): Promise<{
  requests: Array<{ path: string; body: TestRequestBody }>
  close(): Promise<void>
}> {
  const requests: Array<{ path: string; body: TestRequestBody }> = []
  let remoteSequence = 0
  let remoteEventId = '0'.repeat(64)
  let counterflowCommitSequence = 0
  let counterflowCommitEventId = '0'.repeat(64)
  let dropped = false
  let droppedCounterflow = false
  const server = createServer(async (req, res) => {
    const chunks: Buffer[] = []
    for await (const chunk of req) chunks.push(Buffer.from(chunk))
    // This loopback server only receives requests created by the client under test.
    const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8')) as TestRequestBody
    requests.push({ path: req.url ?? '', body: parsed })
    res.setHeader('content-type', 'application/json')

    if (req.url === '/v1/context/status') {
      res.end(JSON.stringify({
        checkpoint: { status: 'compatible', sha256: 'a'.repeat(64), engine_fingerprint: 'b'.repeat(64) },
        stream: {
          stream_id: parsed.stream_id,
          sequence: remoteSequence,
          event_id: remoteEventId,
        },
      }))
      return
    }
    if (req.url === '/v1/context/observe') {
      if (
        typeof parsed.sequence !== 'number'
        || typeof parsed.event_id !== 'string'
        || typeof parsed.previous_event_id !== 'string'
      ) throw new Error('invalid observation')
      if (parsed.sequence === remoteSequence + 1 && parsed.previous_event_id === remoteEventId) {
        remoteSequence = parsed.sequence
        remoteEventId = parsed.event_id
      } else if (parsed.sequence !== remoteSequence || parsed.event_id !== remoteEventId) {
        res.statusCode = 409
        res.end(JSON.stringify({ error: 'journal divergence' }))
        return
      }
      if (dropFirstObservation && !dropped) {
        dropped = true
        res.destroy()
        return
      }
      res.end(JSON.stringify({
        stream: {
          stream_id: parsed.stream_id,
          sequence: remoteSequence,
          event_id: remoteEventId,
        },
      }))
      return
    }
    if (req.url === '/v1/counterflow/plan') {
      const hasTrainingData = (parsed.observations?.length ?? 0) > 0
      if (dropFirstCounterflow && !droppedCounterflow) {
        droppedCounterflow = true
        res.destroy()
        return
      }
      if (counterflowFailure) {
        res.statusCode = counterflowFailure.status
        res.end(JSON.stringify({ error: counterflowFailure.message }))
        return
      }
      const actionObservation = parsed.observations?.some(observation => observation.action) ?? false
      const evaluated = hasTrainingData && parsed.expected !== undefined
      res.end(JSON.stringify({
        schema: 'cassi.counterflow.derived-runtime.v2',
        schema_version: 2,
        mode: parsed.mode,
        status: hasTrainingData
          ? (parsed.mode === 'predict' ? 'predicted' : 'settled')
          : 'no_transition_data',
        derived: true,
        persistent_state: false,
        session_id: 'cassicore-context',
        state_sha256: 'd'.repeat(64),
        primary_field_sha256: 'd'.repeat(64),
        counterflow_state_sha256: 'e'.repeat(64),
        ...(hasTrainingData ? {
          inference_memory_frozen: true,
          prediction: { support: 2, margin: 0.25 },
          evaluation: evaluated
            ? {
                prediction_residual: 0.25,
                identity_baseline_residual: 1,
                improved_over_identity: true,
              }
            : null,
          action_proposal: actionObservation ? { inert: true } : null,
          abstention: actionObservation
            ? null
            : { code: 'prediction_only', evidence: { support: 2 } },
        } : {}),
      }))
      return
    }
    if (req.url === '/v1/counterflow/commit') {
      const acknowledgment = parsed.acknowledgment
      const observation = parsed.observation
      if (!acknowledgment || !observation) throw new Error('invalid counterflow commit')
      const duplicate = (
        acknowledgment.sequence === counterflowCommitSequence
        && acknowledgment.event_id === counterflowCommitEventId
      )
      if (!duplicate) {
        if (acknowledgment.sequence <= counterflowCommitSequence) {
          res.statusCode = 409
          res.end(JSON.stringify({ error: 'counterflow commit conflict' }))
          return
        }
        counterflowCommitSequence = acknowledgment.sequence
        counterflowCommitEventId = acknowledgment.event_id
      }
      res.end(JSON.stringify({
        schema: 'cassi.counterflow.observed-commit-receipt.v1',
        session_id: 'cassicore-context',
        stream_id: acknowledgment.stream_id,
        sequence: acknowledgment.sequence,
        event_id: acknowledgment.event_id,
        status: duplicate ? 'duplicate' : acknowledgment.status,
        consolidated: !duplicate,
        state_sha256: 'd'.repeat(64),
        counterflow_state_in_sha256: 'e'.repeat(64),
        counterflow_state_out_sha256: 'f'.repeat(64),
      }))
      return
    }
    if (req.url === '/v1/context/rank') {
      const candidates = parsed.candidates
      if (!candidates) throw new Error('candidates must be an array')
      res.end(JSON.stringify({
        ranked: candidates.map((candidate, index) => ({
          id: candidate.id,
          score: candidates.length - index,
        })),
        working: [{
          id: 'working:goal:test',
          revision: 'c'.repeat(64),
          text: 'prior goal',
          kind: 'goal',
          score: 0.5,
        }],
      }))
      return
    }
    res.statusCode = 404
    res.end(JSON.stringify({ error: 'not found' }))
  })
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  const address = server.address()
  if (!address || typeof address === 'string') throw new Error('test server has no TCP address')
  return {
    url: `http://127.0.0.1:${address.port}`,
    requests,
    close: async () => {
      server.close()
      await once(server, 'close')
    },
  }
}

describe('HTTP context field client', () => {
  it('drains exact events before ranking and bounds multibyte text by UTF-8 bytes', async () => {
    const server = await startFieldServer()
    const store = new MnemicExactStore(logger, ':memory:')
    try {
      const longQuery = '🙂'.repeat(3_000)
      const longCandidate = '界'.repeat(6_000)
      const longMemory = '🧠'.repeat(5_000)
      store.store({
        id: 'memory-a',
        content: longMemory,
        nodeType: 'fact',
        metadata: { sessionId: 'session-a' },
      })
      store.rememberContextTurn('session-a', 1, longQuery, [{
        id: 'memory-a',
        recordId: 'memory-a',
        startByte: 0,
        endByte: Buffer.byteLength(longCandidate),
        text: longCandidate,
        revision: 'a'.repeat(64),
      }])
      store.consumeContextFeedback('session-a', 1, ['memory-a'], 'completed')

      const client = createHttpContextFieldClient(server.url, store)
      store.onFieldEvent = client.notify
      const ranked = await client.rank({
        sessionId: 'session-b',
        query: longQuery,
        candidates: [
          {
            id: 'memory-a',
            recordId: 'memory-a',
            startByte: 0,
            endByte: Buffer.byteLength(longCandidate),
            revision: 'a'.repeat(64),
            source: 'mnemic',
            text: longCandidate,
            score: 0,
          },
          {
            id: 'memory-b',
            recordId: 'memory-b',
            startByte: 0,
            endByte: Buffer.byteLength('beta memory'),
            revision: 'b'.repeat(64),
            source: 'mnemic',
            text: 'beta memory',
            score: 0,
          },
        ],
        deadlineMs: 1_000,
      })
      await client.close()

      expect(ranked.ranked.map(item => item.id)).toEqual(['memory-a', 'memory-b'])
      expect(ranked.working).toEqual([{
        id: 'working:goal:test',
        revision: 'c'.repeat(64),
        source: 'field',
        text: 'prior goal',
        score: 0.5,
        sourceRefs: ['working:goal:test'],
        workingKind: 'goal',
      }])
      const observations = server.requests.filter(request => request.path === '/v1/context/observe')
      const counterflow = server.requests.filter(request => request.path === '/v1/counterflow/plan')
      expect(observations).toHaveLength(2)
      expect(counterflow).toHaveLength(2)
      expect(counterflow.every(request => request.body.observations?.length === 0)).toBe(true)
      expect(server.requests.findIndex(request => request.path === '/v1/context/rank'))
        .toBeGreaterThan(server.requests.lastIndexOf(counterflow[1]))
      expect(server.requests.every(request => request.body.user === 'cassicore-context')).toBe(true)

      const memoryPayload = observations[0]?.body.payload
      const feedbackPayload = observations[1]?.body.payload
      const rankRequest = server.requests.find(request => request.path === '/v1/context/rank')?.body
      if (memoryPayload?.kind !== 'memory') throw new Error('missing memory payload')
      if (feedbackPayload?.kind !== 'feedback') throw new Error('missing feedback payload')
      if (!rankRequest?.candidates || typeof rankRequest.query !== 'string') throw new Error('missing rank payload')
      const feedbackCandidate = feedbackPayload.candidates[0]
      const rankCandidate = rankRequest.candidates[0]
      if (!feedbackCandidate || !rankCandidate) throw new Error('missing candidate payload')

      expect(Buffer.byteLength(feedbackPayload.query)).toBe(8 * 1_024)
      expect(Buffer.byteLength(rankRequest.query)).toBe(8 * 1_024)
      expect(Buffer.byteLength(memoryPayload.record.content)).toBe(16 * 1_024)
      expect(Buffer.byteLength(feedbackCandidate.text)).toBeLessThanOrEqual(16 * 1_024)
      expect(Buffer.byteLength(rankCandidate.text)).toBeLessThanOrEqual(16 * 1_024)
      expect(feedbackCandidate.end_byte - feedbackCandidate.start_byte)
        .toBe(Buffer.byteLength(feedbackCandidate.text))
      expect(rankCandidate.end_byte - rankCandidate.start_byte)
        .toBe(Buffer.byteLength(rankCandidate.text))
      for (const text of [
        feedbackPayload.query,
        rankRequest.query,
        memoryPayload.record.content,
        feedbackCandidate.text,
        rankCandidate.text,
      ]) expect(text).not.toContain('\uFFFD')
    } finally {
      store.close()
      await server.close()
    }
  })

  it('predicts the held-out update from one continuous exact record lineage', async () => {
    const server = await startFieldServer()
    const store = new MnemicExactStore(logger, ':memory:')
    try {
      store.store({ id: 'memory-a', content: 'alpha', nodeType: 'fact' })
      store.update('memory-a', { content: 'beta' })
      store.update('memory-a', { content: 'gamma' })
      const client = createHttpContextFieldClient(server.url, store)
      await client.flush()
      const status = client.status()
      await client.close()

      const events = store.fieldEventsAfter(0)
      const firstUpdate = events[1]
      const heldOut = events[2]
      if (
        !firstUpdate
        || firstUpdate.payload.kind !== 'memory'
        || !firstUpdate.payload.previous_record
        || !heldOut
        || heldOut.payload.kind !== 'memory'
        || !heldOut.payload.previous_record
      ) throw new Error('missing exact update lineage')
      const plans = server.requests.filter(request => request.path === '/v1/counterflow/plan')
      expect(plans).toHaveLength(3)
      const commits = server.requests.filter(
        request => request.path === '/v1/counterflow/commit',
      )
      expect(commits).toHaveLength(2)
      expect(commits[0]?.body).toMatchObject({
        observation: {
          id: firstUpdate.eventId,
          before: { revision: firstUpdate.payload.previous_record.revision },
          after: { revision: firstUpdate.payload.record.revision },
          symbol: 'mnemic:update',
        },
        acknowledgment: {
          stream_id: firstUpdate.streamId,
          sequence: firstUpdate.sequence,
          event_id: firstUpdate.eventId,
          status: 'committed',
          before_revision: firstUpdate.payload.previous_record.revision,
          after_revision: firstUpdate.payload.record.revision,
          authorization_path: ['mnemic:exact-journal'],
        },
      })
      const firstPlanIndex = server.requests.findIndex(request =>
        request.path === '/v1/counterflow/plan'
        && request.body.expected?.revision === firstUpdate.payload.record.revision)
      const firstObserveIndex = server.requests.findIndex(request =>
        request.path === '/v1/context/observe'
        && request.body.sequence === firstUpdate.sequence)
      const firstCommitIndex = server.requests.findIndex(request =>
        request.path === '/v1/counterflow/commit'
        && request.body.acknowledgment?.sequence === firstUpdate.sequence)
      expect(firstPlanIndex).toBeLessThan(firstObserveIndex)
      expect(firstObserveIndex).toBeLessThan(firstCommitIndex)
      expect(status).toMatchObject({
        residuals: {
          evaluated: 1,
          predictionLast: 0.25,
          predictionMean: 0.25,
          identityLast: 1,
          identityMean: 1,
          improved: 1,
        },
        latencyMs: { count: 3 },
        supportBuckets: {
          '2-3': {
            evaluated: 1,
            predicted: 1,
            improved: 1,
            precision: 1,
            coverage: 1,
          },
        },
        lastAbstention: {
          code: 'prediction_only',
          evidence: { support: 2 },
        },
      })
      expect(plans[0]?.body).toMatchObject({
        mode: 'plan',
        observations: [],
        trajectory: [],
        policy: {},
      })
      expect(plans[1]?.body).toMatchObject({
        mode: 'predict',
        observations: [],
        current: {
          record_id: 'memory-a',
          revision: firstUpdate.payload.previous_record.revision,
        },
        expected: {
          record_id: 'memory-a',
          revision: firstUpdate.payload.record.revision,
        },
      })

      const prediction = plans[2]?.body
      expect(prediction?.mode).toBe('predict')
      expect(prediction?.observations).toEqual([{
        id: firstUpdate.eventId,
        before: {
          record_id: 'memory-a',
          address: counterflowAddress(
            firstUpdate.payload.previous_record.id,
            firstUpdate.payload.previous_record.revision,
            Buffer.byteLength('alpha'),
            'fact',
          ),
          revision: firstUpdate.payload.previous_record.revision,
          start_byte: 0,
          end_byte: Buffer.byteLength('alpha'),
          semantic_kind: 'fact',
        },
        after: {
          record_id: 'memory-a',
          address: counterflowAddress(
            firstUpdate.payload.record.id,
            firstUpdate.payload.record.revision,
            Buffer.byteLength('beta'),
            'fact',
          ),
          revision: firstUpdate.payload.record.revision,
          start_byte: 0,
          end_byte: Buffer.byteLength('beta'),
          semantic_kind: 'fact',
        },
        symbol: 'mnemic:update',
      }])
      expect(prediction?.current).toEqual(prediction?.observations?.[0]?.after)
      expect(prediction?.expected).toMatchObject({
        record_id: 'memory-a',
        revision: heldOut.payload.record.revision,
        end_byte: Buffer.byteLength('gamma'),
      })
      expect(prediction?.observations?.map(observation => observation.id))
        .not.toContain(heldOut.eventId)
      expect(prediction?.policy).toEqual({
        eligible_observation_ids: [firstUpdate.eventId],
        permitted_action_kinds: [],
        authority: 1,
        authorization_path: ['mnemic:exact-journal', 'mnemic:continuous-lineage'],
      })
    } finally {
      store.close()
      await server.close()
    }
  })
  it('preserves an empty exact span as a real update transition', async () => {
    const server = await startFieldServer()
    const store = new MnemicExactStore(logger, ':memory:')
    try {
      store.store({ id: 'memory-empty', content: '', nodeType: 'fact' })
      store.update('memory-empty', { content: 'filled' })
      const client = createHttpContextFieldClient(server.url, store)
      await client.flush()
      await client.close()

      const plans = server.requests.filter(request => request.path === '/v1/counterflow/plan')
      expect(plans[1]?.body).toMatchObject({
        mode: 'predict',
        observations: [],
        current: {
          record_id: 'memory-empty',
          start_byte: 0,
          end_byte: 0,
          semantic_kind: 'fact',
        },
        expected: {
          record_id: 'memory-empty',
          start_byte: 0,
          end_byte: Buffer.byteLength('filled'),
          semantic_kind: 'fact',
        },
      })
    } finally {
      store.close()
      await server.close()
    }
  })

  it('predicts an inert action from prior successful exact outcomes only', async () => {
    const server = await startFieldServer()
    const store = new MnemicExactStore(logger, ':memory:')
    const argumentsSha256 = 'b'.repeat(64)
    try {
      store.startActionEpisode({
        contextSessionId: 'session-a',
        turnId: 1,
        planId: 'plan-1',
        toolCallId: 'call-1',
        toolName: 'read',
        argumentsSha256,
        requiredAuthority: 0.8,
        reversible: true,
      })
      store.finishActionEpisode({
        contextSessionId: 'session-a',
        turnId: 1,
        planId: 'plan-1',
        toolCallId: 'call-1',
        isError: false,
      })
      store.startActionEpisode({
        contextSessionId: 'session-a',
        turnId: 2,
        planId: 'plan-2',
        toolCallId: 'call-2',
        toolName: 'read',
        argumentsSha256,
        requiredAuthority: 0.8,
        reversible: true,
      })
      const client = createHttpContextFieldClient(
        server.url,
        store,
        undefined,
        { shadowSupportThreshold: 4 },
      )
      await client.flush()

      const events = store.fieldEventsAfter(0)
      const successful = events[1]
      if (
        !successful
        || successful.payload.kind !== 'memory'
        || !successful.payload.previous_record
        || !successful.payload.action
      ) throw new Error('missing successful action evidence')
      let commits = server.requests.filter(
        request => request.path === '/v1/counterflow/commit',
      )
      expect(commits).toHaveLength(1)
      expect(commits[0]?.body).toMatchObject({
        user: 'cassicore-context',
        observation: {
          id: successful.eventId,
          outcome: 'completed',
          action: {
            id: successful.payload.action.action_id,
            kind: 'tool:read',
            required_authority: 0.8,
            reversible: true,
            effects: [],
          },
        },
        acknowledgment: {
          stream_id: successful.streamId,
          sequence: successful.sequence,
          event_id: successful.eventId,
          status: 'completed',
          before_revision: successful.payload.previous_record.revision,
          authorization_path: [
            'thalamus:plan:plan-1',
            'omp:tool-call:call-1',
          ],
        },
      })
      let plans = server.requests.filter(request => request.path === '/v1/counterflow/plan')
      expect(plans).toHaveLength(3)
      expect(plans[2]?.body).toMatchObject({
        mode: 'predict',
        observations: [{
          id: successful.eventId,
          before: {
            record_id: successful.payload.record.id,
            end_byte: 0,
          },
          after: {
            record_id: successful.payload.record.id,
            end_byte: Buffer.byteLength('completed'),
          },
          symbol: 'tool:read',
          action: {
            id: successful.payload.action.action_id,
            kind: 'tool:read',
            required_authority: 0.8,
            reversible: true,
          },
        }],
        current: {
          record_id: successful.payload.record.id,
          end_byte: 0,
        },
        policy: {
          eligible_observation_ids: [successful.eventId],
          permitted_action_kinds: ['tool:read'],
          authority: 0.8,
          authorization_path: ['thalamus:plan:plan-2', 'omp:tool-call:call-2'],
        },
      })
      expect(plans[2]?.body.expected).toBeUndefined()
      expect(client.status()).toMatchObject({
        schemaVersion: 1,
        proposals: {
          count: 1,
          supportLast: 2,
          supportMean: 2,
          marginLast: 0.25,
          marginMean: 0.25,
        },
        shadowThreshold: {
          support: 4,
          metrics: { proposals: 0 },
        },
      })

      store.finishActionEpisode({
        contextSessionId: 'session-a',
        turnId: 2,
        planId: 'plan-2',
        toolCallId: 'call-2',
        isError: true,
      })
      await client.flush()
      plans = server.requests.filter(request => request.path === '/v1/counterflow/plan')
      expect(plans[3]?.body).toMatchObject({
        mode: 'predict',
        observations: [{ id: successful.eventId }],
        observed_outcome: 'error',
        expected: {
          record_id: successful.payload.record.id,
          end_byte: Buffer.byteLength('error'),
        },
      })
      expect(client.status().failures['action-error']).toBe(1)
      commits = server.requests.filter(
        request => request.path === '/v1/counterflow/commit',
      )
      expect(commits).toHaveLength(2)
      expect(commits[1]?.body).toMatchObject({
        user: 'cassicore-context',
        observation: { outcome: 'error' },
        acknowledgment: { status: 'error' },
      })
      expect(plans[3]?.body.observations).toHaveLength(1)
      await client.close()
    } finally {
      store.close()
      await server.close()
    }
  })

  it('opts into same-field failure inhibition and action-role evidence', async () => {
    const server = await startFieldServer()
    const store = new MnemicExactStore(logger, ':memory:')
    const record = (
      call: string,
      turn: number,
      digest: string,
      isError?: boolean,
    ): void => {
      store.startActionEpisode({
        contextSessionId: 'session-a',
        turnId: turn,
        planId: `plan-${turn}`,
        toolCallId: call,
        toolName: 'edit',
        argumentsSha256: digest.repeat(64),
        requiredAuthority: 1,
        reversible: false,
      })
      if (isError !== undefined) {
        store.finishActionEpisode({
          contextSessionId: 'session-a',
          turnId: turn,
          planId: `plan-${turn}`,
          toolCallId: call,
          isError,
        })
      }
    }
    try {
      record('call-1', 1, 'a', false)
      record('call-2', 2, 'b', true)
      record('call-3', 3, 'c')
      const events = store.fieldEventsAfter(0)
      const current = events[4]
      if (current?.payload.kind !== 'memory' || !current.payload.action) {
        throw new Error('missing current action role')
      }
      const client = createHttpContextFieldClient(server.url, store, undefined, {
        failureInhibition: true,
        actionRoleAbstraction: true,
      })
      await client.flush()
      const plans = server.requests.filter(request => request.path === '/v1/counterflow/plan')
      const request = plans[4]?.body
      expect(request).toMatchObject({
        mode: 'predict',
        failure_inhibition: true,
        observations: [
          { outcome: 'completed' },
          { outcome: 'error' },
        ],
      })
      expect(request?.observations).toHaveLength(2)
      expect(request?.observations?.every(
        observation => observation.action?.id === current.payload.action?.action_id,
      )).toBe(true)
      expect(client.status().features).toMatchObject({
        failureInhibition: true,
        actionRoleAbstraction: true,
      })
      await client.close()
    } finally {
      store.close()
      await server.close()
    }
  })

  it('opts into exact semantic lineage roles without changing default lineages', async () => {
    const server = await startFieldServer()
    const store = new MnemicExactStore(logger, ':memory:')
    try {
      store.store({ id: 'memory-a', content: 'alpha', nodeType: 'fact' })
      store.update('memory-a', { content: 'beta' })
      store.store({ id: 'memory-b', content: 'one', nodeType: 'fact' })
      store.update('memory-b', { content: 'two' })
      const events = store.fieldEventsAfter(0)
      const client = createHttpContextFieldClient(server.url, store, undefined, {
        lineageRoleAbstraction: true,
      })
      await client.flush()
      const plans = server.requests.filter(request => request.path === '/v1/counterflow/plan')
      expect(plans[3]?.body).toMatchObject({
        observations: [{ id: events[1]?.eventId }],
        policy: {
          authorization_path: ['mnemic:exact-journal', 'mnemic:semantic-lineage-role'],
        },
      })
      expect(plans[3]?.body.observations).toHaveLength(1)
      await client.close()
    } finally {
      store.close()
      await server.close()
    }
  })

  it('opts into inert next-action trajectories from exact completed episodes', async () => {
    const server = await startFieldServer()
    const store = new MnemicExactStore(logger, ':memory:')
    try {
      for (let turn = 1; turn <= 3; turn++) {
        store.startActionEpisode({
          contextSessionId: 'session-a',
          turnId: turn,
          planId: `plan-${turn}`,
          toolCallId: `call-${turn}`,
          toolName: 'edit',
          argumentsSha256: String(turn).repeat(64),
          requiredAuthority: 1,
          reversible: false,
        })
        store.finishActionEpisode({
          contextSessionId: 'session-a',
          turnId: turn,
          planId: `plan-${turn}`,
          toolCallId: `call-${turn}`,
          isError: turn === 3,
        })
      }
      const events = store.fieldEventsAfter(0)
      const client = createHttpContextFieldClient(server.url, store, undefined, {
        multiActionTrajectories: true,
      })
      await client.flush()
      const plans = server.requests.filter(request => request.path === '/v1/counterflow/plan')
      expect(plans[5]?.body).toMatchObject({
        mode: 'predict',
        trajectory_mode: 'next-action',
        observed_outcome: 'error',
        observations: [{
          id: `trajectory:${events[1]?.eventId}:${events[3]?.eventId}`,
          symbol: 'trajectory:tool:edit',
        }],
      })
      expect(plans[5]?.body.expected).toBeUndefined()
      expect(client.status().features.multiActionTrajectories).toBe(true)
      expect(client.status().failures['action-error']).toBe(1)
      await client.close()
    } finally {
      store.close()
      await server.close()
    }
  })

  it('classifies journal-hash and authority provider failures', async () => {
    for (const failure of [
      { status: 409, message: 'event_id hash mismatch', code: 'journal-hash' },
      { status: 403, message: 'authority is insufficient', code: 'authority' },
    ] as const) {
      const server = await startFieldServer(false, false, failure)
      const store = new MnemicExactStore(logger, ':memory:')
      const client = createHttpContextFieldClient(server.url, store)
      try {
        store.store({ id: 'memory-a', content: 'alpha', nodeType: 'fact' })
        await expect(client.flush()).rejects.toThrow()
        expect(client.status().failures[failure.code]).toBe(1)
        expect(store.fieldStreamStatus().acknowledgedSequence).toBe(0)
      } finally {
        await client.close()
        store.close()
        await server.close()
      }
    }
  })

  it('retries counterflow before acknowledging after a client restart', async () => {
    const server = await startFieldServer(false, true)
    const store = new MnemicExactStore(logger, ':memory:')
    try {
      store.store({ id: 'memory-a', content: 'alpha', nodeType: 'fact' })
      const firstClient = createHttpContextFieldClient(server.url, store)
      await expect(firstClient.flush()).rejects.toThrow()
      expect(store.fieldStreamStatus()).toMatchObject({
        headSequence: 1,
        acknowledgedSequence: 0,
      })

      const restartedClient = createHttpContextFieldClient(server.url, store)
      await restartedClient.flush()
      expect(store.fieldStreamStatus()).toMatchObject({
        headSequence: 1,
        acknowledgedSequence: 1,
      })
      expect(server.requests.filter(request => request.path === '/v1/context/observe'))
        .toHaveLength(1)
      expect(server.requests.filter(request => request.path === '/v1/counterflow/plan'))
        .toHaveLength(2)
      await restartedClient.close()
    } finally {
      store.close()
      await server.close()
    }
  })

  it('reconciles a provider commit whose acknowledgement was lost', async () => {
    const server = await startFieldServer(true)
    const store = new MnemicExactStore(logger, ':memory:')
    try {
      store.store({ id: 'memory-a', content: 'alpha', nodeType: 'fact' })
      const client = createHttpContextFieldClient(server.url, store)
      await expect(client.flush()).rejects.toThrow()
      await expect(client.rank({
        sessionId: 'session-a',
        query: 'alpha',
        candidates: [{
          id: 'memory-a',
          recordId: 'memory-a',
          startByte: 0,
          endByte: Buffer.byteLength('alpha'),
          revision: 'a'.repeat(64),
          source: 'mnemic',
          text: 'alpha',
          score: 0,
        }],
        deadlineMs: 1_000,
      })).resolves.toEqual({
        ranked: [{ id: 'memory-a', score: 1 }],
        working: [{
          id: 'working:goal:test',
          revision: 'c'.repeat(64),
          source: 'field',
          text: 'prior goal',
          score: 0.5,
          sourceRefs: ['working:goal:test'],
          workingKind: 'goal',
        }],
      })
      expect(server.requests.filter(request => request.path === '/v1/context/observe')).toHaveLength(1)
      expect(store.fieldStreamStatus()).toMatchObject({ headSequence: 1, acknowledgedSequence: 1 })
      await client.close()
    } finally {
      store.close()
      await server.close()
    }
  })
  it('leaves durable events pending when the provider is down at shutdown', async () => {
    const server = await startFieldServer()
    await server.close()
    const store = new MnemicExactStore(logger, ':memory:')
    try {
      store.store({ id: 'memory-a', content: 'alpha', nodeType: 'fact' })
      const client = createHttpContextFieldClient(server.url, store)

      await expect(client.close()).resolves.toBeUndefined()
      expect(store.fieldStreamStatus()).toMatchObject({
        headSequence: 1,
        acknowledgedSequence: 0,
      })
      expect(client.status().failures['provider-unavailable']).toBe(1)
    } finally {
      store.close()
    }
  })

})
