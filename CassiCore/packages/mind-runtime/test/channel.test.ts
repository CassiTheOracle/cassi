/**
 * @cassicore/mind-runtime — channel contract test.
 *
 * Asserts the 127.0.0.1 channel server behaves per the brief §3.2 endpoint table:
 * tools/execute runs a retained handler, session/mirror + events/push ack, snapshot
 * returns state, health 200, memory/* round-trip, unknown → 404, bad token → 401,
 * and the browser-CSRF/content-type/body-size boundary rejects unsafe POSTs.
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { createHmac } from 'node:crypto'
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

describe('mind-runtime channel (127.0.0.1 contract)', () => {
  let home: string
  let rt: MindRuntime
  let server: MindChannelServer
  let port: number

  beforeAll(async () => {
    home = mkdtempSync(join(tmpdir(), 'cassimind-channel-'))
    rt = await createMindRuntime({ logger: quietLogger, homePath: home, disableUnifiedLoop: true, disableOscillation: true })
    server = new MindChannelServer(rt, { logger: quietLogger, port: 0 })
    port = await server.listen()
    // Verify loopback-only bind address.
    expect(server.address().host).toBe('127.0.0.1')
  }, 30_000)

  afterAll(async () => {
    await server.close()
    await rt.close()
    try { rmSync(home, { recursive: true, force: true }) } catch { /* Windows file-lock — best effort */ }
  })

  it('GET /v1/health → 200 ok (plain liveness)', async () => {
    const res = await fetch(`http://127.0.0.1:${port}/v1/health`)
    expect(res.status).toBe(200)
    expect(await res.text()).toBe('ok')
  })

  it('tools/execute runs a retained handler and echoes requestId', async () => {
    const { status, json } = await postJson(port, '/v1/tools/execute', { requestId: 'abc', tool: 'list_sessions', params: {} })
    expect(status).toBe(200)
    const r = json as { ok: boolean; result: string; requestId?: string }
    expect(r.ok).toBe(true)
    expect(typeof r.result).toBe('string')
    expect(r.requestId).toBe('abc')
  })

  it('tools/execute returns ok:false for an unknown tool', async () => {
    const { status, json } = await postJson(port, '/v1/tools/execute', { tool: 'nope', params: {} })
    expect(status).toBe(200)
    expect((json as { ok: boolean }).ok).toBe(false)
  })

  it('session/mirror acks and records the session', async () => {
    const { status, json } = await postJson(port, '/v1/session/mirror', { event: 'start', sessionId: 'sess-1' })
    expect(status).toBe(200)
    expect((json as { ack: boolean }).ack).toBe(true)
    expect(rt.sessions.get('sess-1')).toBeDefined()
  })

  it('events/push acks and emits onto the retained bus', async () => {
    const { status, json } = await postJson(port, '/v1/events/push', { type: 'mcp_notification', payload: { p: 1 }, sessionId: 'sess-1' })
    expect(status).toBe(200)
    expect((json as { ack: boolean }).ack).toBe(true)
  })

  it('snapshot returns mind-state', async () => {
    const { status, json } = await postJson(port, '/v1/snapshot', {})
    expect(status).toBe(200)
    const s = (json as { state: { health: string; sessions: unknown[]; memory: { backend: string } } }).state
    expect(s.health).toBe('ok')
    expect(Array.isArray(s.sessions)).toBe(true)
    expect(s.memory.backend).toBe('mnemic-field')
  })

  it('memory/status + search + save round-trip', async () => {
    const st = await postJson(port, '/v1/memory/status', {})
    expect((st.json as { backend: string }).backend).toBe('mnemic-field')

    const saved = await postJson(port, '/v1/memory/save', { content: 'channel round-trip memory', type: 'fact' })
    expect(typeof (saved.json as { id: string }).id).toBe('string')

    const found = await postJson(port, '/v1/memory/search', { query: 'round-trip' })
    const results = (found.json as { results: unknown[] }).results
    expect(Array.isArray(results)).toBe(true)
  })

  it('unknown path → 404', async () => {
    const { status } = await postJson(port, '/v1/does-not-exist', {})
    expect(status).toBe(404)
  })

  it('bad role-method → 405', async () => {
    const res = await fetch(`http://127.0.0.1:${port}/v1/health`, { method: 'PUT' })
    expect(res.status).toBe(405)
  })

  it('rejects browser-origin and simple non-JSON POST requests before dispatch', async () => {
    const browser = await fetch(`http://127.0.0.1:${port}/v1/events/push`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', origin: 'https://malicious.example' },
      body: JSON.stringify({ type: 'should-not-dispatch' }),
    })
    expect(browser.status).toBe(403)

    const simple = await fetch(`http://127.0.0.1:${port}/v1/events/push`, {
      method: 'POST',
      headers: { 'content-type': 'text/plain' },
      body: JSON.stringify({ type: 'should-not-dispatch' }),
    })
    expect(simple.status).toBe(415)
  })

  it('rejects request bodies larger than the one-megabyte channel bound', async () => {
    const res = await fetch(`http://127.0.0.1:${port}/v1/events/push`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ type: 'oversized', payload: 'x'.repeat(1024 * 1024) }),
    })
    expect(res.status).toBe(413)
  })
})

describe('mind-runtime channel auth', () => {
  it('rejects requests without the bearer token when CASSI_MIND_TOKEN set', async () => {
    const home = mkdtempSync(join(tmpdir(), 'cassimind-auth-'))
    const rt = await createMindRuntime({
      logger: quietLogger, homePath: home, disableUnifiedLoop: true, disableOscillation: true, token: 'sekrit',
    })
    const server = new MindChannelServer(rt, { logger: quietLogger, port: 0, token: 'sekrit' })
    const port = await server.listen()
    try {
      const noAuth = await fetch(`http://127.0.0.1:${port}/v1/health`)
      expect(noAuth.status).toBe(401)

      const nonce = 'a'.repeat(64)
      const challenge = await fetch(`http://127.0.0.1:${port}/v1/health?nonce=${nonce}`)
      expect(challenge.status).toBe(200)
      expect(await challenge.json()).toEqual({
        ok: true,
        proof: createHmac('sha256', 'sekrit').update(nonce).digest('hex'),
      })

      const withAuth = await postJson(port, '/v1/snapshot', {}, 'sekrit')
      expect(withAuth.status).toBe(200)
    } finally {
      await server.close()
      await rt.close()
      try { rmSync(home, { recursive: true, force: true }) } catch { /* Windows file-lock — best effort */ }
    }
  }, 30_000)
})
