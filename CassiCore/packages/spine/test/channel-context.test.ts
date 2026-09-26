/**
 * @cassicore/spine — ChannelClient attention-context endpoint contract test.
 *
 * Asserts the two shared runtime endpoints:
 *   POST /v1/context/candidates — `{sessionId, turnId, query, limit?, deadlineMs?, includeFieldShadow?}`
 *   POST /v1/context/feedback   — `{sessionId, turnId, planId, includedCandidateIds, outcome}` (ID-only)
 * plus the per-call timeout override and the standard error mapping
 * (401 UnauthorizedError, 404 NotFoundError, non-2xx → Error).
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { createDecipheriv, createHash, createHmac } from 'node:crypto'

import { ChannelClient, NotFoundError, UnauthorizedError } from '../src/channel/client.js'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
    ...init,
  })
}

function healthProofResponse(url: RequestInfo | URL, token: string): Response | undefined {
  const value = String(url)
  const nonce = new URL(value).searchParams.get('nonce')
  if (!nonce) return undefined
  return jsonResponse({ ok: true, proof: createHmac('sha256', token).update(nonce).digest('hex') })
}

function decryptWireBody(wireBody: unknown, token: string): unknown {
  const envelope = JSON.parse(String(wireBody)) as { v: number; iv: string; ciphertext: string; tag: string }
  expect(envelope.v).toBe(1)
  const key = createHash('sha256').update(`cassi-mind-channel\u0000${token}`).digest()
  const decipher = createDecipheriv('aes-256-gcm', key, Buffer.from(envelope.iv, 'base64'))
  decipher.setAuthTag(Buffer.from(envelope.tag, 'base64'))
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(envelope.ciphertext, 'base64')),
    decipher.final(),
  ]).toString('utf8')
  return JSON.parse(plaintext)
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ChannelClient attention context endpoints', () => {
  it('POSTs the candidates request to /v1/context/candidates and parses the response', async () => {
    const fetchImpl = vi.fn(async (url: RequestInfo | URL) => {
      const proof = healthProofResponse(url, 'tok')
      if (proof) return proof
      return jsonResponse({
        candidates: [{ id: 'cand-1', source: 'mnemic', text: 'candidate one', score: 0.9 }],
        sources: [{ source: 'mnemic', status: 'ready', latencyMs: 4 }],
        fieldAdvisory: { mode: 'shadow', observedAt: 123, step: 5, time: 42 },
      })
    })
    vi.stubGlobal('fetch', fetchImpl)

    const client = new ChannelClient({ baseUrl: 'http://127.0.0.1:7273/', token: 'tok' })
    const res = await client.contextCandidates({
      sessionId: 'sess-1',
      turnId: 3,
      query: 'what is the field doing?',
      limit: 5,
      deadlineMs: 2500,
      includeFieldShadow: true,
    })

    expect(res.candidates[0]).toMatchObject({ id: 'cand-1', text: 'candidate one', score: 0.9 })
    expect(res.sources[0]).toMatchObject({ source: 'mnemic', status: 'ready' })
    expect(res.fieldAdvisory).toMatchObject({ mode: 'shadow', observedAt: 123, step: 5 })

    const [url, init] = fetchImpl.mock.calls[1]
    expect(url).toBe('http://127.0.0.1:7273/v1/context/candidates')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'content-type': 'application/json' })
    expect(String(init.body)).not.toContain('what is the field doing?')
    expect(decryptWireBody(init.body, 'tok')).toEqual({
      sessionId: 'sess-1',
      turnId: 3,
      query: 'what is the field doing?',
      limit: 5,
      deadlineMs: 2500,
      includeFieldShadow: true,
    })
  })

  it('accepts a null fieldAdvisory (first-miss/stale/offline) and empty candidates', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({
      candidates: [],
      sources: [{ source: 'mnemic', status: 'timeout', error: 'deadline exceeded' }],
      fieldAdvisory: null,
    }))
    vi.stubGlobal('fetch', fetchImpl)

    const client = new ChannelClient({ baseUrl: 'http://127.0.0.1:7273' })
    const res = await client.contextCandidates({ sessionId: 's', turnId: 1, query: 'q' })
    expect(res.candidates).toEqual([])
    expect(res.sources[0].status).toBe('timeout')
    expect(res.fieldAdvisory).toBeNull()
  })

  it('POSTs ID-only feedback to /v1/context/feedback with the locked protocol', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ ack: true }))
    vi.stubGlobal('fetch', fetchImpl)

    const client = new ChannelClient({ baseUrl: 'http://127.0.0.1:7273' })
    const res = await client.contextFeedback({
      sessionId: 'sess-1',
      turnId: 3,
      planId: 'plan-sess-1-3-1',
      includedCandidateIds: ['cand-1'],
      outcome: 'completed',
    })

    expect(res).toEqual({ ack: true })
    const [url, init] = fetchImpl.mock.calls[0]
    expect(url).toBe('http://127.0.0.1:7273/v1/context/feedback')
    expect(JSON.parse(String(init.body))).toEqual({
      sessionId: 'sess-1',
      turnId: 3,
      planId: 'plan-sess-1-3-1',
      includedCandidateIds: ['cand-1'],
      outcome: 'completed',
    })
  })

  it('honors a per-call timeout override shorter than the client default', async () => {
    const fetchImpl = vi.fn((_url: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    vi.stubGlobal('fetch', fetchImpl)

    const client = new ChannelClient({ baseUrl: 'http://127.0.0.1:7273', timeoutMs: 60_000 })
    await expect(client.contextCandidates({ sessionId: 's', turnId: 1, query: 'q' }, { timeoutMs: 5 }))
      .rejects.toThrow(/Mind runtime unreachable/)
  })

  it('maps 401 → UnauthorizedError and 404 → NotFoundError after a valid server proof', async () => {
    let status = 401
    const fetchImpl = vi.fn(async (url: RequestInfo | URL) => {
      const proof = healthProofResponse(url, 'bad')
      return proof ?? new Response('nope', { status })
    })
    vi.stubGlobal('fetch', fetchImpl)
    const client = new ChannelClient({ baseUrl: 'http://127.0.0.1:7273', token: 'bad' })
    await expect(client.contextCandidates({ sessionId: 's', turnId: 1, query: 'q' })).rejects.toBeInstanceOf(UnauthorizedError)

    status = 404
    await expect(client.contextCandidates({ sessionId: 's', turnId: 1, query: 'q' })).rejects.toBeInstanceOf(NotFoundError)
  })

  it('does not send a bearer or context body before a token-bound health proof succeeds', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ ok: true, proof: '0'.repeat(64) }))
    vi.stubGlobal('fetch', fetchImpl)

    const client = new ChannelClient({ baseUrl: 'http://127.0.0.1:7273', token: 'tok' })
    await expect(client.contextCandidates({ sessionId: 's', turnId: 1, query: 'PRIVATE_QUERY' }))
      .rejects.toThrow(/identity proof failed/)

    expect(fetchImpl).toHaveBeenCalledTimes(1)
    const [url, init] = fetchImpl.mock.calls[0]
    expect(String(url)).toMatch(/\/v1\/health\?nonce=/)
    expect(init?.headers).toBeUndefined()
  })

  it('surfaces non-2xx runtime errors with status', async () => {
    const fetchImpl = vi.fn(async () => new Response('bad body', { status: 400 }))
    vi.stubGlobal('fetch', fetchImpl)
    const client = new ChannelClient({ baseUrl: 'http://127.0.0.1:7273' })
    await expect(client.contextFeedback({ sessionId: 's', turnId: 1, planId: 'p', includedCandidateIds: [], outcome: 'unknown' }))
      .rejects.toThrow(/mind runtime error 400/)
  })
})
