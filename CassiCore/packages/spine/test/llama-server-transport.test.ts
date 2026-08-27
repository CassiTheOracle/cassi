import { describe, expect, it, vi } from 'vitest'

import { createLlamaServerTransport } from '../src/tools/llama-server-transport.js'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
    ...init,
  })
}

describe('createLlamaServerTransport', () => {
  it('maps a minimal completion request and response', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({
      model: 'ignored-by-spine-contract',
      choices: [{ message: { content: 'local answer' } }],
      usage: { prompt_tokens: 4, completion_tokens: 2, total_tokens: 6 },
    }))
    const transport = createLlamaServerTransport({ fetch: fetchImpl })

    const result = await transport(
      { id: 'qwen-local' },
      [{ role: 'user', content: 'hello' }],
      {},
    )

    expect(result).toEqual({
      content: 'local answer',
      usage: { prompt_tokens: 4, completion_tokens: 2, total_tokens: 6 },
    })
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    const [url, init] = fetchImpl.mock.calls[0]
    expect(url).toBe('http://127.0.0.1:8080/v1/chat/completions')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'content-type': 'application/json' })
    expect(JSON.parse(String(init.body))).toEqual({
      model: 'qwen-local',
      messages: [{ role: 'user', content: 'hello' }],
      stream: false,
    })
  })

  it('passes a finite temperature and omits effort', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({
      choices: [{ message: { content: '' } }],
    }))
    const transport = createLlamaServerTransport({ fetch: fetchImpl })

    await transport(
      { id: 'qwen-local' },
      [{ role: 'system', content: 'be concise' }],
      { temperature: 0.25, effort: 'high' },
    )

    const body = JSON.parse(String(fetchImpl.mock.calls[0][1].body))
    expect(body).toEqual({
      model: 'qwen-local',
      messages: [{ role: 'system', content: 'be concise' }],
      stream: false,
      temperature: 0.25,
    })
  })

  it('normalizes the base URL and sends an API token only when configured', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({
      choices: [{ message: { content: 'ok' } }],
    }))
    const transport = createLlamaServerTransport({
      baseUrl: 'http://127.0.0.1:9000///',
      apiToken: 'secret',
      fetch: fetchImpl,
    })

    await transport({ id: 'qwen' }, [], {})

    expect(fetchImpl.mock.calls[0][0]).toBe('http://127.0.0.1:9000/v1/chat/completions')
    expect(fetchImpl.mock.calls[0][1].headers).toEqual({
      'content-type': 'application/json',
      authorization: 'Bearer secret',
    })
  })

  it('routes explicit closed-loop requests to the world provider and marks the body', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({
      choices: [{ message: { content: 'world answer' } }],
    }))
    const transport = createLlamaServerTransport({
      baseUrl: 'http://127.0.0.1:9000',
      worldModeUrl: 'http://127.0.0.1:8082///',
      fetch: fetchImpl,
    })

    const result = await transport(
      { id: 'qwen-local' },
      [{ role: 'user', content: 'simulate' }],
      { cassi_world_mode: 'closed_loop', temperature: 0.4 },
    )

    expect(result.content).toBe('world answer')
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    expect(fetchImpl.mock.calls[0][0]).toBe('http://127.0.0.1:8082/v1/chat/completions')
    expect(JSON.parse(String(fetchImpl.mock.calls[0][1].body))).toEqual({
      cassi_world_mode: 'closed_loop',
      model: 'qwen-local',
      messages: [{ role: 'user', content: 'simulate' }],
      stream: false,
      temperature: 0.4,
    })
  })

  it('rejects an unsupported world mode at the transport boundary', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({
      choices: [{ message: { content: 'should not be called' } }],
    }))
    const transport = createLlamaServerTransport({ fetch: fetchImpl })

    await expect(
      transport({ id: 'qwen-local' }, [], {
        cassi_world_mode: 'open_loop',
      } as unknown as { cassi_world_mode?: 'closed_loop' }),
    ).rejects.toThrow('unsupported cassi_world_mode: open_loop')
    expect(fetchImpl).not.toHaveBeenCalled()
  })

  it('surfaces non-2xx status and bounds the body excerpt', async () => {
    const fetchImpl = vi.fn(async () => new Response('x'.repeat(700), { status: 503 }))
    const transport = createLlamaServerTransport({ fetch: fetchImpl })

    await expect(transport({ id: 'qwen' }, [], {})).rejects.toThrow(
      /^llama-server returned HTTP 503: x{512}…$/,
    )
  })

  it('rejects malformed JSON', async () => {
    const fetchImpl = vi.fn(async () => new Response('{broken', { status: 200 }))
    const transport = createLlamaServerTransport({ fetch: fetchImpl })

    await expect(transport({ id: 'qwen' }, [], {})).rejects.toThrow(
      'llama-server returned malformed JSON',
    )
  })

  it('rejects a success response without string completion content', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ choices: [{ message: {} }] }))
    const transport = createLlamaServerTransport({ fetch: fetchImpl })

    await expect(transport({ id: 'qwen' }, [], {})).rejects.toThrow(
      'llama-server response is missing string completion content',
    )
  })

  it('adds context to network errors', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error('connection refused')
    })
    const transport = createLlamaServerTransport({ fetch: fetchImpl })

    await expect(transport({ id: 'qwen' }, [], {})).rejects.toThrow(
      'llama-server request failed: connection refused',
    )
  })

  it('aborts and reports the configured timeout', async () => {
    const fetchImpl = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    const transport = createLlamaServerTransport({ timeoutMs: 5, fetch: fetchImpl })

    await expect(transport({ id: 'qwen' }, [], {})).rejects.toThrow(
      'llama-server request timed out after 5ms',
    )
  })

  it('rejects invalid timeout configuration before making requests', () => {
    expect(() => createLlamaServerTransport({ timeoutMs: 0 })).toThrow(
      'llama-server timeoutMs must be a positive finite number',
    )
  })
})
