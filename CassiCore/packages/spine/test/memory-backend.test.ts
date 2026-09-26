/**
 * @cassicore/spine — memory-backend adapter contract test (stubbed channel client).
 *
 * Asserts the MnemicMemoryBackend maps status/search/save onto the runtime channel's
 * /v1/memory/* endpoints and returns the MemoryRuntimeContext shapes. No live ohmypi.
 */

import { describe, expect, it } from 'vitest'

import { MnemicMemoryBackend } from '../src/memory-backend.js'
import type { ChannelClient } from '../src/channel/client.js'

function clientStub(overrides: Partial<ChannelClient> = {}): ChannelClient {
  return {
    executeTool: async () => ({ ok: true, result: '' }),
    mirrorSession: async () => {},
    getSnapshot: async () => ({ state: { memory: {}, loops: {}, sessions: [], uptimeMs: 1, health: 'ok' } }),
    postEvent: async () => ({}),
    memoryStatus: async () => ({ backend: 'mnemic-field' as never, stats: { engramCount: 3 } }),
    memorySearch: async () => ({ results: [{ id: 'e1', content: 'a recalled fact', score: 0.9 }] }),
    memorySave: async () => ({ id: 'e-new' }),
    ping: async () => true,
    ...overrides,
  } as unknown as ChannelClient
}

describe('MnemicMemoryBackend (memory backend adapter)', () => {
  it('status() proxies the runtime memory/status', async () => {
    const backend = new MnemicMemoryBackend(clientStub())
    const status = await backend.status()
    expect(status.active).toBe(true)
    expect(status.writable).toBe(true)
    expect(status.message).toContain('MnemicField')
  })

  it('search(query) proxies and maps hits to {id, content, score}', async () => {
    const backend = new MnemicMemoryBackend(clientStub())
    const result = await backend.search('recalled')
    expect(result.query).toBe('recalled')
    expect(result.count).toBe(1)
    expect(result.items[0]).toMatchObject({ id: 'e1', content: 'a recalled fact', score: 0.9 })
  })

  it('save(input) proxies to memory/save and returns stored:1', async () => {
    const backend = new MnemicMemoryBackend(clientStub())
    const result = await backend.save({ content: 'a saved note', context: 'ctx' })
    expect(result.stored).toBe(1)
    expect(result.ids).toEqual(['e-new'])
  })

  it('status() reports inactive when the runtime is unreachable', async () => {
    const backend = new MnemicMemoryBackend(clientStub({
      memoryStatus: async () => { throw new Error('down') },
    }))
    const status = await backend.status()
    expect(status.active).toBe(false)
    expect(status.error).toContain('down')
  })
})
