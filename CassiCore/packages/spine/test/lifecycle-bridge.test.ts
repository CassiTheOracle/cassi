/**
 * @cassicore/spine — lifecycle-bridge contract test (stubbed ExtensionAPI; no live ohmypi).
 *
 * Asserts each of session_start/switch/branch/compact/shutdown fires the runtime client's
 * mirror with the right `{event, sessionId, …}`, appendEntry('mind.runtime.state', …) is
 * called on each lifecycle event with a `{sessionId, ts, state}` snapshot, and
 * mcp_notification pushes `{type, payload, sessionId}`.
 */

import { describe, expect, it } from 'vitest'

import cassiSpine from '../src/index.js'
import type { ChannelClient } from '../src/channel/client.js'
import { createStubPi } from './stub-pi.js'

type Mirrors = Array<Record<string, unknown>>
function makeClient(mirrors: Mirrors) {
  return {
    executeTool: async () => ({ ok: true, result: '' }),
    mirrorSession: async (req: Record<string, unknown>) => { mirrors.push(req) },
    getSnapshot: async () => ({ state: { memory: {}, loops: {}, sessions: [], uptimeMs: 1, health: 'ok' } }),
    postEvent: async () => ({}),
    memoryStatus: async () => ({ backend: 'mnemic-field' as never, stats: {} }),
    memorySearch: async () => ({ results: [] }),
    memorySave: async () => ({ id: 'm1' }),
    ping: async () => true,
  } as unknown as ChannelClient
}

describe('spine lifecycle → runtime mirror + snapshots', () => {
  it('session_start mirrors {event:start, sessionId} and appends a snapshot', async () => {
    const stub = createStubPi()
    const mirrors: Mirrors = []
    cassiSpine(stub.pi, { client: makeClient(mirrors), noAutoSpawn: true })
    await stub.fire('session_start', { type: 'session_start' })
    expect(mirrors[0]).toMatchObject({ event: 'start', sessionId: 'sess-test-1' })
    expect(stub.entries.some(e => e.type === 'mind.runtime.state')).toBe(true)
  })

  it('session_switch mirrors {event:switch}', async () => {
    const stub = createStubPi()
    const mirrors: Mirrors = []
    cassiSpine(stub.pi, { client: makeClient(mirrors), noAutoSpawn: true })
    await stub.fire('session_switch', { type: 'session_switch' })
    expect(mirrors[0]).toMatchObject({ event: 'switch', sessionId: 'sess-test-1' })
  })

  it('session_branch mirrors the captured branch-point entry ID', async () => {
    const stub = createStubPi()
    const mirrors: Mirrors = []
    cassiSpine(stub.pi, { client: makeClient(mirrors), noAutoSpawn: true })
    await stub.fire('session_before_branch', { type: 'session_before_branch', entryId: 'entry-branch-point-7' })
    await stub.fire('session_branch', { type: 'session_branch', previousSessionFile: 'session-before-branch.jsonl' })
    expect(mirrors[0]).toMatchObject({ event: 'branch', branchFrom: 'entry-branch-point-7' })
  })

  it('session_compact mirrors {event:compact, summary}', async () => {
    const stub = createStubPi()
    const mirrors: Mirrors = []
    cassiSpine(stub.pi, { client: makeClient(mirrors), noAutoSpawn: true })
    await stub.fire('session_compact', {
      type: 'session_compact',
      compactionEntry: { summary: 'a compaction summary' },
      fromExtension: false,
    })
    expect(mirrors[0]).toMatchObject({ event: 'compact', summary: 'a compaction summary' })
  })

  it('session_shutdown mirrors {event:shutdown}', async () => {
    const stub = createStubPi()
    const mirrors: Mirrors = []
    cassiSpine(stub.pi, { client: makeClient(mirrors), noAutoSpawn: true })
    await stub.fire('session_shutdown', { type: 'session_shutdown' })
    expect(mirrors[0]).toMatchObject({ event: 'shutdown', sessionId: 'sess-test-1' })
  })

  it('every lifecycle event appends the episodic snapshot with ts + state', async () => {
    const stub = createStubPi()
    const mirrors: Mirrors = []
    cassiSpine(stub.pi, { client: makeClient(mirrors), noAutoSpawn: true })
    for (const ev of ['session_start', 'session_switch', 'session_compact', 'session_shutdown']) {
      await stub.fire(ev, { type: ev })
    }
    await stub.fire('session_before_branch', { type: 'session_before_branch', entryId: 'entry-branch-point-7' })
    await stub.fire('session_branch', { type: 'session_branch' })
    expect(stub.entries.filter(e => e.type === 'mind.runtime.state').length).toBe(5)
    const snap = stub.entries[0].data as { sessionId: string; ts: number; state: unknown }
    expect(snap.sessionId).toBe('sess-test-1')
    expect(typeof snap.ts).toBe('number')
    expect(snap.state).toMatchObject({ health: 'ok' })
  })

  it('mcp_notification pushes {type, payload, sessionId} to the runtime', async () => {
    const stub = createStubPi()
    const pushed: Array<Record<string, unknown>> = []
    const client = {
      executeTool: async () => ({ ok: true, result: '' }),
      mirrorSession: async () => {},
      getSnapshot: async () => ({ state: { memory: {}, loops: {}, sessions: [], uptimeMs: 1, health: 'ok' } }),
      postEvent: async (req: Record<string, unknown>) => { pushed.push(req) },
      memoryStatus: async () => ({ backend: 'mnemic-field' as never, stats: {} }),
      memorySearch: async () => ({ results: [] }),
      memorySave: async () => ({ id: 'm1' }),
      ping: async () => true,
    } as unknown as ChannelClient
    cassiSpine(stub.pi, { client, noAutoSpawn: true })
    await stub.fire('mcp_notification', { type: 'mcp_notification', payload: { jsonrpc: '2.0', method: 'notify' } })
    expect(pushed[0]).toMatchObject({ type: 'mcp_notification', sessionId: 'sess-test-1' })
  })
})
