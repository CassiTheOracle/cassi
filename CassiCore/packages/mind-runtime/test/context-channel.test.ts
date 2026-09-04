/**
 * @cassicore/mind-runtime — field-native context endpoints over the real
 * 127.0.0.1 channel. Verifies explicit disabled/no-fallback behavior, opaque
 * address selection through a loopback field provider, exact byte resolution,
 * feedback delivery, status, validation, and bearer authentication.
 */

import { once } from 'node:events'
import { mkdtempSync, rmSync } from 'node:fs'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

import { createMindRuntime, MindChannelServer, type MindRuntime } from '../src/index.js'
import type { ILogger } from '@cassicore/foundation'

const quietLogger: ILogger = {
  debug: () => {}, info: () => {}, warn: () => {}, error: () => {},
  child: () => quietLogger,
}

async function postJson(port: number, path: string, body: unknown, token?: string): Promise<{ status: number; json: unknown }> {
  const res = await fetch(`http://127.0.0.1:${port}${path}`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  })
  const text = await res.text()
  let json: unknown
  try { json = JSON.parse(text) } catch { json = text }
  return { status: res.status, json }
}

async function startFieldRecallServer(): Promise<{
  url: string
  observed: Array<Record<string, unknown>>
  requests: Array<{ path: string; body: Record<string, unknown> }>
  close(): Promise<void>
}> {
  const observed: Array<Record<string, unknown>> = []
  const requests: Array<{ path: string; body: Record<string, unknown> }> = []
  let remoteSequence = 0
  let remoteEventId = '0'.repeat(64)
  const fieldServer = createServer(async (req, res) => {
    const chunks: Buffer[] = []
    for await (const chunk of req) chunks.push(Buffer.from(chunk))
    const body = JSON.parse(Buffer.concat(chunks).toString('utf8')) as Record<string, unknown>
    res.setHeader('content-type', 'application/json')
    requests.push({ path: req.url ?? '', body })
    if (req.url === '/v1/context/status') {
      res.end(JSON.stringify({
        checkpoint: {
          status: 'compatible',
          sha256: 'a'.repeat(64),
          engine_fingerprint: 'b'.repeat(64),
        },
        stream: {
          stream_id: body.stream_id,
          sequence: remoteSequence,
          event_id: remoteEventId,
        },
      }))
      return
    }
    if (req.url === '/v1/context/observe') {
      const sequence = body.sequence
      const previousEventId = body.previous_event_id
      const eventId = body.event_id
      if (
        typeof sequence !== 'number'
        || typeof previousEventId !== 'string'
        || typeof eventId !== 'string'
      ) {
        res.statusCode = 400
        res.end(JSON.stringify({ error: 'invalid field event' }))
        return
      }
      if (sequence === remoteSequence + 1 && previousEventId === remoteEventId) {
        remoteSequence = sequence
        remoteEventId = eventId
        observed.push(body)
      } else if (sequence !== remoteSequence || eventId !== remoteEventId) {
        res.statusCode = 409
        res.end(JSON.stringify({ error: 'journal divergence' }))
        return
      }
      res.end(JSON.stringify({
        stream: {
          stream_id: body.stream_id,
          sequence: remoteSequence,
          event_id: remoteEventId,
        },
      }))
      return
    }
    if (req.url === '/v1/counterflow/plan') {
      res.end(JSON.stringify({
        schema: 'cassi.counterflow.derived-runtime.v2',
        schema_version: 2,
        mode: body.mode,
        status: 'no_transition_data',
        derived: true,
        persistent_state: false,
        session_id: 'cassicore-context',
        state_sha256: 'd'.repeat(64),
        primary_field_sha256: 'd'.repeat(64),
        counterflow_state_sha256: 'e'.repeat(64),
      }))
      return
    }
    if (req.url === '/v1/context/recall') {
      const addresses = Array.isArray(body.addresses)
        ? body.addresses.filter((address): address is string => typeof address === 'string')
        : []
      res.end(JSON.stringify({
        schema: 'cassi.mnemic.field-recall.v1',
        address: addresses[0] ?? null,
        signal: addresses.length > 0 ? 1 : 0,
        selection_margin: addresses.length > 0 ? 1 : 0,
        availability: addresses.length > 0 ? 1 : 0,
      }))
      return
    }
    res.statusCode = 404
    res.end(JSON.stringify({ error: 'not found' }))
  })
  fieldServer.listen(0, '127.0.0.1')
  await once(fieldServer, 'listening')
  const address = fieldServer.address()
  if (!address || typeof address === 'string') throw new Error('field test server has no TCP address')
  return {
    url: `http://127.0.0.1:${address.port}`,
    observed,
    requests,
    close: async () => {
      fieldServer.close()
      await once(fieldServer, 'close')
    },
  }
}

describe('mind-runtime context channel (P8 shared context seam)', () => {
  let home: string
  let rt: MindRuntime
  let server: MindChannelServer
  let port: number

  beforeAll(async () => {
    home = mkdtempSync(join(tmpdir(), 'cassimind-context-'))
    rt = await createMindRuntime({
      logger: quietLogger,
      homePath: home,
      disableUnifiedLoop: true,
      disableOscillation: true,
      token: 'sekrit',
      verifyMnemicJournal: true,
    })
    server = new MindChannelServer(rt, { logger: quietLogger, port: 0, token: 'sekrit' })
    port = await server.listen()
  }, 30_000)

  afterAll(async () => {
    await server.close()
    await rt.close()
    try { rmSync(home, { recursive: true, force: true }) } catch { /* Windows file-lock — best effort */ }
  })

  it('candidates returns typed empty results + source statuses and echoes requestId', async () => {
    const { status, json } = await postJson(port, '/v1/context/candidates', {
      requestId: 'r1',
      sessionId: 'sess-1',
      turnId: 1,
      query: 'nothing matches this',
    }, 'sekrit')
    expect(status).toBe(200)
    const r = json as {
      candidates: unknown[]
      sources: Array<{ source: string; status: string }>
      fieldAdvisory: unknown
      requestId?: string
    }
    expect(Array.isArray(r.candidates)).toBe(true)
    expect(r.sources.some(s => s.source === 'mnemic')).toBe(true)
    expect(r.sources[0].status).toBe('disabled')
    expect(r.fieldAdvisory).toBeNull()
    expect(r.requestId).toBe('r1')
  })

  it('does not fall back to lexical retrieval when field recall is disabled', async () => {
    await postJson(port, '/v1/memory/save', {
      content: 'the purple candidate parrot returns at dawn',
      type: 'fact',
      sessionId: 'prior-session',
    }, 'sekrit')

    const { status, json } = await postJson(port, '/v1/context/candidates', {
      sessionId: 'sess-1',
      turnId: 1,
      query: 'purple parrot',
    }, 'sekrit')
    expect(status).toBe(200)
    expect(json).toMatchObject({
      candidates: [],
      sources: [{ source: 'mnemic', status: 'disabled' }],
    })
  })

  it('resolves a field-selected address through the public channel and delivers feedback', async () => {
    const liveHome = mkdtempSync(join(tmpdir(), 'cassimind-field-context-'))
    const field = await startFieldRecallServer()
    let liveRuntime: MindRuntime | null = null
    let liveChannel: MindChannelServer | null = null
    try {
      liveRuntime = await createMindRuntime({
        logger: quietLogger,
        homePath: liveHome,
        disableUnifiedLoop: true,
        disableOscillation: true,
        token: 'field-secret',
        verifyMnemicJournal: true,
        fieldIntelligenceUrl: field.url,
      })
      liveChannel = new MindChannelServer(liveRuntime, {
        logger: quietLogger,
        port: 0,
        token: 'field-secret',
      })
      const livePort = await liveChannel.listen()
      const saved = await postJson(livePort, '/v1/memory/save', {
        content: 'the exact cobalt crossing opens at sunrise',
        type: 'fact',
        sessionId: 'prior-session',
      }, 'field-secret')
      expect(liveRuntime.field.fieldAddressManifest({
        excludeSessionId: 'current-session',
      })).toHaveLength(1)
      expect(saved.status).toBe(200)

      const recalled = await postJson(livePort, '/v1/context/candidates', {
        sessionId: 'current-session',
        turnId: 7,
        query: 'cobalt crossing',
      }, 'field-secret')
      expect(recalled.status).toBe(200)
      const response = recalled.json as {
        candidates: Array<{ id: string; text: string; fieldAddress?: string }>
        sources: Array<{ source: string; status: string }>
      }
      expect(
        response.sources,
        JSON.stringify({ observed: field.observed, requests: field.requests, response }, null, 2),
      ).toContainEqual(expect.objectContaining({
        source: 'mnemic',
        status: 'ready',
      }))
      expect(response.candidates).toHaveLength(1)
      expect(response.candidates[0]?.text).toBe('the exact cobalt crossing opens at sunrise')
      expect(response.candidates[0]?.fieldAddress).toMatch(/^[0-9a-f]{32}$/)

      const feedback = await postJson(livePort, '/v1/context/feedback', {
        sessionId: 'current-session',
        turnId: 7,
        planId: 'field-plan',
        includedCandidateIds: [response.candidates[0]!.id],
        outcome: 'completed',
      }, 'field-secret')
      expect(feedback).toEqual({ status: 200, json: { ack: true } })
      await postJson(livePort, '/v1/context/candidates', {
        sessionId: 'current-session',
        turnId: 8,
        query: 'cobalt crossing',
      }, 'field-secret')
      expect(field.observed.some(event => (
        (event.payload as { kind?: string } | undefined)?.kind === 'feedback'
      ))).toBe(true)
    } finally {
      if (liveChannel) await liveChannel.close()
      if (liveRuntime) await liveRuntime.close()
      await field.close()
      try { rmSync(liveHome, { recursive: true, force: true }) } catch { /* Windows native-store lock — best effort */ }
    }
  })

  it('exposes read-only counterflow, verification, and recovery status', async () => {
    const first = await postJson(port, '/v1/context/status', {}, 'sekrit')
    const second = await postJson(port, '/v1/context/status', {}, 'sekrit')
    expect(first.status).toBe(200)
    expect(second).toEqual(first)
    expect(first.json).toMatchObject({
      schemaVersion: 1,
      candidates: {
        counterflow: null,
      },
      journal: {
        stream: {
          streamId: expect.any(String),
          headSequence: expect.any(Number),
          acknowledgedSequence: expect.any(Number),
        },
        verification: {
          status: 'valid',
          acknowledgedPrefixValid: true,
        },
        unresolvedActions: [],
      },
    })
  })

  it('malformed candidates/feedback requests → 400', async () => {
    const noQuery = await postJson(port, '/v1/context/candidates', { sessionId: 's', turnId: 1 }, 'sekrit')
    expect(noQuery.status).toBe(400)

    const empty = await postJson(port, '/v1/context/candidates', {}, 'sekrit')
    expect(empty.status).toBe(400)

    const badFeedback = await postJson(port, '/v1/context/feedback', {
      sessionId: 's', turnId: 1, planId: 'p', includedCandidateIds: null, outcome: 'completed',
    }, 'sekrit')
    expect(badFeedback.status).toBe(400)

    const badAction = await postJson(port, '/v1/context/action', {
      operation: 'start',
      sessionId: 's',
      turnId: 1,
      planId: 'p',
      toolCallId: 'tc',
      toolName: 'read',
      argumentsSha256: 'bad',
      requiredAuthority: 0.8,
      reversible: true,
    }, 'sekrit')
    expect(badAction.status).toBe(400)
  })

  it('feedback acks with requestId and publishes an observable retained bus event', async () => {
    const seen: unknown[] = []
    const unsub = rt.bus.onAll(e => { seen.push(e) })
    try {
      const { status, json } = await postJson(port, '/v1/context/feedback', {
        requestId: 'f1',
        sessionId: 'sess-1',
        turnId: 1,
        planId: 'plan-1',
        includedCandidateIds: ['engram-a', 'engram-b'],
        outcome: 'completed',
      }, 'sekrit')
      expect(status).toBe(200)
      const r = json as { ack: boolean; requestId?: string }
      expect(r.ack).toBe(true)
      expect(r.requestId).toBe('f1')

      const ev = seen.find(e => (e as { type?: string }).type === 'cassi.context.feedback') as
        { sessionId?: string; planId?: string; includedCandidateIds?: string[]; outcome?: string } | undefined
      expect(ev).toBeDefined()
      expect(ev?.sessionId).toBe('sess-1')
      expect(ev?.planId).toBe('plan-1')
      expect(ev?.includedCandidateIds).toEqual(['engram-a', 'engram-b'])
      expect(ev?.outcome).toBe('completed')
    } finally {
      unsub()
    }
  })

  it('durably acknowledges an exact action start before its outcome', async () => {
    const start = await postJson(port, '/v1/context/action', {
      requestId: 'a1',
      operation: 'start',
      sessionId: 'sess-action',
      turnId: 2,
      planId: 'plan-action',
      toolCallId: 'call-action',
      toolName: 'read',
      requiredAuthority: 0.8,
      reversible: true,
      argumentsSha256: 'a'.repeat(64),
    }, 'sekrit')
    expect(start).toEqual({ status: 200, json: { ack: true, requestId: 'a1' } })
    const unresolved = await postJson(port, '/v1/context/status', {}, 'sekrit')
    expect(unresolved.json).toMatchObject({
      journal: {
        unresolvedActions: [{
          episodeId: 'call-action',
          requiredAuthority: 0.8,
          reversible: true,
        }],
      },
    })

    const outcome = await postJson(port, '/v1/context/action', {
      requestId: 'a2',
      operation: 'outcome',
      sessionId: 'sess-action',
      turnId: 2,
      planId: 'plan-action',
      toolCallId: 'call-action',
      isError: false,
    }, 'sekrit')
    expect(outcome).toEqual({ status: 200, json: { ack: true, requestId: 'a2' } })
    const resolved = await postJson(port, '/v1/context/status', {}, 'sekrit')
    expect(resolved.json).toMatchObject({
      journal: { unresolvedActions: [] },
    })
  })

  it('rejects requests without the bearer token (401)', async () => {
    const noAuth = await postJson(port, '/v1/context/candidates', { sessionId: 's', turnId: 1, query: 'x' })
    const noAuthStatus = await postJson(port, '/v1/context/status', {})
    expect(noAuthStatus.status).toBe(401)
    expect(noAuth.status).toBe(401)
    const noAuthFeedback = await postJson(port, '/v1/context/feedback', {
      sessionId: 's', turnId: 1, planId: 'p', includedCandidateIds: ['a'], outcome: 'completed',
    })
    expect(noAuthFeedback.status).toBe(401)
    const noAuthAction = await postJson(port, '/v1/context/action', {
      operation: 'outcome',
      sessionId: 's',
      turnId: 1,
      planId: 'p',
      toolCallId: 'tc',
      isError: true,
    })
    expect(noAuthAction.status).toBe(401)
  })
})
