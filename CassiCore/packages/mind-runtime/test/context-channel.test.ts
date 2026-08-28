/**
 * @cassicore/mind-runtime — context endpoints channel test.
 *
 * Asserts the P8 shared context seam over the real 127.0.0.1 channel:
 * `/v1/context/candidates` (typed Mnemic candidates, source statuses, cached
 * field advisory, requestId echo) and `/v1/context/feedback` (ID-only ack +
 * observable retained bus event), plus malformed → 400 and missing bearer
 * token → 401. Uses an in-process harness (server + runtime) — no external
 * process, no 7599 socket.
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

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
    expect(r.sources[0].status).toMatch(/ready|timeout/)
    expect(r.fieldAdvisory).toBeNull()
    expect(r.requestId).toBe('r1')
  })

  it('candidates returns a saved engram as a typed Mnemic candidate', async () => {
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
    const r = json as { candidates: Array<{ id: string; text: string; source: string; score: number }> }
    expect(r.candidates.length).toBeGreaterThan(0)
    for (const c of r.candidates) {
      expect(typeof c.id).toBe('string')
      expect(typeof c.text).toBe('string')
      expect(c.source).toBe('mnemic')
      expect(typeof c.score).toBe('number')
    }
    expect(r.candidates.some(c => c.text.includes('purple candidate parrot'))).toBe(true)
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

  it('rejects requests without the bearer token (401)', async () => {
    const noAuth = await postJson(port, '/v1/context/candidates', { sessionId: 's', turnId: 1, query: 'x' })
    expect(noAuth.status).toBe(401)
    const noAuthFeedback = await postJson(port, '/v1/context/feedback', {
      sessionId: 's', turnId: 1, planId: 'p', includedCandidateIds: ['a'], outcome: 'completed',
    })
    expect(noAuthFeedback.status).toBe(401)
  })
})
