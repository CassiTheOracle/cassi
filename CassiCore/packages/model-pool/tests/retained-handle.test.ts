/**
 * @cassicore/model-pool — RETAINED HANDLE / ACQUIRE-SHIM TESTS (CASSICORE-FOCUS §6 P4)
 *
 * The retained suite that survives the P4 model-access cutover. Exercises the
 * retained surface (ports/):
 *   - `ModelPool` acquire-shim contract (setModelPool shape)
 *   - `createMindCompleteAcquirer` → `acquire(...)` → retained `ModelHandle`
 *   - `ModelHandleImpl.complete()` / `stream()` routed through the injected
 *     `mind_complete` transport
 *   - default 'not wired' transport error
 *   - release/dispose lifecycle and single-shot stream adaptation.
 *
 * The pool-machinery suites (fallback/budget/billing/capability) died with the
 * delegate class at P4.
 */

import { describe, it, expect, vi } from 'vitest'
import {
  createMindCompleteAcquirer,
  defaultMindCompleteTransport,
  ModelHandleImpl,
} from '../src/index.js'
import type { MindCompleteTransport } from '../src/index.js'
import type { ILogger } from '@cassicore/foundation'
import type { ModelHandle } from '../src/index.js'

const createLogger = (): ILogger =>
  ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    child: () => createLogger(),
  } as unknown as ILogger)

const fakeTransport: MindCompleteTransport = vi.fn(async (resolved, messages, opts) => {
  const lastUser = [...messages].reverse().find((m) => m.role === 'user')
  return {
    content: `echo:${resolved.id}:${lastUser?.content ?? ''}`,
    usage: { outputTokens: 12 },
    model: resolved.id,
  }
})

describe('retained acquire-shim (createMindCompleteAcquirer)', () => {
  it('acquire() returns a retained ModelHandle', async () => {
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport: fakeTransport })
    const handle = await pool.acquire('unity', 'tier', 'sess')
    expect(handle).toBeInstanceOf(ModelHandleImpl)
    expect((handle as any).provider).toBe('mind_complete')
    expect((handle as any).model).toBe('@slow')
  })

  it('acquire() honors the override provider/model', async () => {
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport: fakeTransport })
    const handle = await pool.acquire('unity', undefined, 'sess', { provider: 'z-ai', model: 'glm-5.1' })
    expect(handle.provider).toBe('z-ai')
    expect(handle.model).toBe('glm-5.1')
  })

  it('acquire() throws after dispose()', async () => {
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport: fakeTransport })
    pool.dispose()
    await expect(pool.acquire('unity')).rejects.toThrow('disposed')
  })

  it('acquire() returns handles that release without throwing', async () => {
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport: fakeTransport })
    const handle = await pool.acquire('unity')
    expect(() => pool.release(handle)).not.toThrow()
    expect(() => handle.release()).not.toThrow()
  })
})

describe('retained ModelHandleImpl — mind_complete routing', () => {
  it('complete() routes through the transport and returns a TurnResult', async () => {
    const transport = fakeTransport as ReturnType<typeof vi.fn>
    transport.mockClear()
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport })
    const handle = await pool.acquire('brainstem', undefined, 's', { provider: 'z-ai', model: 'glm-5.1' })

    const result = await handle.complete(
      [{ role: 'user', content: 'hello' }],
      { model: 'glm-5.1', temperature: 0.3 },
    )

    expect(transport).toHaveBeenCalledTimes(1)
    const [resolved, messages] = transport.mock.calls[0]
    expect(resolved.id).toBe('z-ai/glm-5.1')
    expect(messages).toEqual([{ role: 'user', content: 'hello' }])
    expect(result.response).toBe('echo:z-ai/glm-5.1:hello')
    expect(result.model).toBe('z-ai/glm-5.1')
    expect(result.durationMs).toBeGreaterThanOrEqual(0)
  })

  it('stream() yields a token chunk then a done chunk (single-shot adaptation)', async () => {
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport: fakeTransport })
    const handle = await pool.acquire('corpus', undefined, 's', { provider: 'p', model: 'm' })

    const chunks = []
    for await (const c of handle.stream([{ role: 'user', content: 'hi' }], { model: 'm', stream: true })) {
      chunks.push(c)
    }

    expect(chunks.length).toBe(2)
    expect(chunks[0].type).toBe('token')
    expect((chunks[0] as any).text).toContain('echo:p/m:hi')
    expect(chunks[1].type).toBe('done')
  })

  it('complete() throws after release()', async () => {
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport: fakeTransport })
    const handle = await pool.acquire('unity')
    handle.release()
    await expect(handle.complete([{ role: 'user', content: 'x' }], { model: 'm' })).rejects.toThrow('released')
  })

  it('stream() surfaces a transport error as an error chunk (does not throw)', async () => {
    const failing: MindCompleteTransport = async () => {
      throw new Error('provider down')
    }
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport: failing })
    const handle = await pool.acquire('unity')
    const chunks = []
    for await (const c of handle.stream([{ role: 'user', content: 'x' }], { model: 'm' })) {
      chunks.push(c)
    }
    expect(chunks[0].type).toBe('error')
    expect((chunks[0] as any).error).toContain('provider down')
  })

  it('the default transport throws the documented not-wired error', async () => {
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport: defaultMindCompleteTransport })
    const handle = await pool.acquire('unity')
    await expect(handle.complete([{ role: 'user', content: 'x' }], { model: 'm' })).rejects.toThrow(
      'mind_complete transport not wired',
    )
  })

  it('Symbol.dispose releases the handle automatically', async () => {
    const pool = createMindCompleteAcquirer({ logger: createLogger(), transport: fakeTransport })
    const handle = (await pool.acquire('unity')) as ModelHandle
    handle[Symbol.dispose]()
    await expect(handle.complete([{ role: 'user', content: 'x' }], { model: 'm' })).rejects.toThrow('released')
  })
})
