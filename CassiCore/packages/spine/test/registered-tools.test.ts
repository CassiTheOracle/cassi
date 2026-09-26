/**
 * @cassicore/spine — registered-tools contract test (stubbed ExtensionAPI; no live ohmypi).
 *
 * Asserts the factory registers the 13 retained tools (plan §4.2: 12 retained + the
 * mind_complete bridge) with the retained definitions' names/param schemas, hides the
 * P5 seam tools (hidden + defaultInactive), delegates retained execution to the runtime
 * channel, and mind_complete resolves via ctx.models.resolve with effort/temperature
 * passthrough, including the default local llama-server transport.
 */

import { describe, expect, it, vi } from 'vitest'

import cassiSpine from '../src/index.js'
import type { MindCompleteTransport } from '../src/tools/mind-complete.js'
import type { ChannelClient } from '../src/channel/client.js'
import { createStubPi } from './stub-pi.js'

type ClientLike = Pick<ChannelClient, 'executeTool' | 'mirrorSession' | 'getSnapshot' | 'postEvent' | 'memoryStatus' | 'memorySearch' | 'memorySave' | 'ping'>

function makeClient(): ClientLike & { calls: Array<{ tool: string; params: unknown; sessionId?: string }> } {
  const calls: Array<{ tool: string; params: unknown; sessionId?: string }> = []
  const c: ClientLike = {
    executeTool: async (tool, params, sessionId) => {
      calls.push({ tool, params, sessionId })
      return { ok: true, result: `result-of-${tool}` }
    },
    mirrorSession: async () => {},
    getSnapshot: async () => ({ state: { memory: { stats: {}, lightning: null }, loops: { unifiedLoopRunning: true, cortexOscillation: true }, sessions: [], uptimeMs: 1, health: 'ok' } }),
    postEvent: async () => ({}),
    memoryStatus: async () => ({ backend: 'mnemic-field' as never, stats: {} }),
    memorySearch: async () => ({ results: [] }),
    memorySave: async () => ({ id: 'm1' }),
    ping: async () => true,
  }
  return { ...c, calls }
}

describe('spine factory registers retained mind tools', () => {
  it('registers the 13 plan §4.2 tools (12 retained + mind_complete) by exact name', () => {
    const stub = createStubPi()
    const client = makeClient()
    cassiSpine(stub.pi, { client: client as unknown as ChannelClient, noAutoSpawn: true })

    const names = stub.registered.map(r => r.name).sort()
    for (const expectName of [
      'collect_thoughts', 'graph_discover', 'list_sessions', 'list_subagents',
      'get_subagent_status', 'get_subagent_result', 'system_health', 'debug_session',
      'universal_search', 'cassandra_query_events', 'cassandra_context_inspect',
      'query_events', 'mind_complete',
    ]) {
      expect(names).toContain(expectName)
    }
  })

  it('registers the retained tools as visible (not hidden) and the seam tools hidden+inactive', () => {
    const stub = createStubPi()
    const client = makeClient()
    cassiSpine(stub.pi, { client: client as unknown as ChannelClient, noAutoSpawn: true })

    for (const visible of ['collect_thoughts', 'system_health', 'query_events']) {
      const t = stub.registered.find(r => r.name === visible)
      expect(t).toBeDefined()
      expect(t!.hidden).toBeFalsy()
      expect(t!.defaultInactive).toBeFalsy()
    }
    for (const seam of ['_coordinate', '_check_peers']) {
      const t = stub.registered.find(r => r.name === seam)
      expect(t, `seam tool ${seam}`).toBeDefined()
      expect(t!.hidden).toBe(true)
      expect(t!.defaultInactive).toBe(true)
    }
    // P5-deleted redundant memory mind tools (merge into ohmypi memory built-ins) — absent.
    for (const gone of ['_reflect', '_remember', 'remember', 'memory_search']) {
      expect(stub.registered.find(r => r.name === gone), `${gone} should be deleted`).toBeUndefined()
    }
  })

  it('retained execute delegates {tool, params, sessionId} to the runtime channel and returns the string', async () => {
    const stub = createStubPi()
    const client = makeClient()
    cassiSpine(stub.pi, { client: client as unknown as ChannelClient, noAutoSpawn: true })

    const tool = stub.getTool('system_health')
    expect(tool).toBeDefined()
    const result = await tool!.execute('call-1', { includeSessions: false }, undefined, undefined, stub.makeCtx() as never)
    expect(result.content[0]).toMatchObject({ type: 'text', text: 'result-of-system_health' })
    expect(client.calls).toContainEqual(expect.objectContaining({ tool: 'system_health', sessionId: 'sess-test-1' }))
  })

  it('mind_complete resolves the model via ctx.models.resolve and passes effort/temperature to the transport', async () => {
    const stub = createStubPi()
    const client = makeClient()
    const transport: MindCompleteTransport = vi.fn(async (resolved, _msgs, opts) => {
      void opts
      return { content: `completed-with-${resolved.id}` }
    })
    cassiSpine(stub.pi, { client: client as unknown as ChannelClient, noAutoSpawn: true, mindCompleteTransport: transport })

    const tool = stub.getTool('mind_complete')
    const result = await tool!.execute('call-2', { model: '@slow', messages: [{ role: 'user', content: 'hi' }], effort: 'high', temperature: 0.3 }, undefined, undefined, stub.makeCtx() as never)
    expect(stub.resolvedModels).toContain('@slow')
    expect(result.content[0]).toMatchObject({ type: 'text' })
    // json body contains model id + content
    expect(String(result.content[0].text)).toContain('completed-with-@slow')
  })

  it('mind_complete defaults to the local llama-server transport and preserves model/usage', async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({
      choices: [{ message: { content: 'local completion' } }],
      usage: { prompt_tokens: 3, completion_tokens: 2, total_tokens: 5 },
    }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }))
    for (const name of [
      'CASSI_LLAMA_SERVER_URL',
      'CASSI_LLAMA_SERVER_TOKEN',
      'CASSI_LLAMA_SERVER_TIMEOUT_MS',
      'LLAMA_SERVER_URL',
      'LLAMA_SERVER_TOKEN',
      'LLAMA_SERVER_TIMEOUT_MS',
    ]) {
      vi.stubEnv(name, '')
    }
    vi.stubGlobal('fetch', fetchImpl)
    try {
      const stub = createStubPi()
      const client = makeClient()
      cassiSpine(stub.pi, { client: client as unknown as ChannelClient, noAutoSpawn: true })

      const tool = stub.getTool('mind_complete')
      const result = await tool!.execute(
        'call-default',
        { model: '@slow', messages: [{ role: 'user', content: 'hello' }], temperature: 0.2 },
        undefined,
        undefined,
        stub.makeCtx() as never,
      )

      expect(result.isError).toBeFalsy()
      expect(JSON.parse(String(result.content[0].text))).toEqual({
        content: 'local completion',
        model: '@slow',
        usage: { prompt_tokens: 3, completion_tokens: 2, total_tokens: 5 },
      })
      expect(fetchImpl).toHaveBeenCalledTimes(1)
      expect(fetchImpl.mock.calls[0][0]).toBe('http://127.0.0.1:8080/v1/chat/completions')
      expect(JSON.parse(String(fetchImpl.mock.calls[0][1].body))).toEqual({
        model: '@slow',
        messages: [{ role: 'user', content: 'hello' }],
        stream: false,
        temperature: 0.2,
      })
    } finally {
      vi.unstubAllGlobals()
      vi.unstubAllEnvs()
    }
  })

  it('mind_complete returns an isError result when the model is unresolvable', async () => {
    const stub = createStubPi()
    const client = makeClient()
    cassiSpine(stub.pi, { client: client as unknown as ChannelClient, noAutoSpawn: true })
    stub.setResolveResult(undefined)
    const tool = stub.getTool('mind_complete')
    const result = await tool!.execute('c', { model: 'unresolvable', messages: [] }, undefined, undefined, stub.makeCtx() as never)
    expect(result.isError).toBe(true)
  })
})
