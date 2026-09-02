/**
 * @cassicore/mind-runtime — boot smoke test.
 *
 * Asserts `createMindRuntime` constructs the retained intelligence layer, exact
 * Mnemic record store, and mind-tool registry without provider access on an
 * isolated temp home. No live ohmypi / spine is required.
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { createMindRuntime, type MindRuntime } from '../src/index.js'
import type { ILogger } from '@cassicore/foundation'

const quietLogger: ILogger = {
  debug: () => {}, info: () => {}, warn: () => {}, error: () => {},
  child: () => quietLogger,
}

describe('mind-runtime boot (exact memory, no providers)', () => {
  let home: string
  let rt: MindRuntime

  beforeAll(async () => {
    home = mkdtempSync(join(tmpdir(), 'cassimind-boot-'))
    rt = await createMindRuntime({
      logger: quietLogger,
      homePath: home,
      disableUnifiedLoop: true,
      disableOscillation: true,
    })
  }, 30_000)

  afterAll(async () => {
    await rt.close()
    try { rmSync(home, { recursive: true, force: true }) } catch { /* Windows file-lock — best effort */ }
  })

  it('opens exact Mnemic records under CASSICORE_HOME and exposes stats', () => {
    const status = rt.memory.status()
    expect(status.backend).toBe('mnemic-field')
    expect(rt.field).toBeDefined()
    expect(rt.field.stats).toBeTypeOf('function')
  })

  it('does not construct the retired adaptive Mnemic subsystems', () => {
    const field = rt.field as unknown as Record<string, unknown>
    for (const retired of ['kindle', 'consolidate', 'lightningStatus', 'computeHarmony']) {
      expect(field[retired]).toBeUndefined()
    }
  })

  it('registers the retained mind tools (P5: _reflect/_remember/remember/memory_search deleted)', () => {
    const names = rt.registry.list({ includeHidden: true }).map(t => t.name)
    for (const name of [
      'collect_thoughts', 'graph_discover', 'list_sessions', 'system_health',
      'debug_session', 'universal_search', 'cassandra_query_events',
      'cassandra_context_inspect', 'query_events', '_coordinate', '_check_peers',
    ]) {
      expect(names).toContain(name)
    }
    // P5-deleted redundant memory mind tools (merge into ohmypi memory built-ins).
    for (const gone of ['_reflect', '_remember', 'remember', 'memory_search']) {
      expect(names).not.toContain(gone)
    }
    // list_subagents family is conditional (needs tracker/thinker) — confirm absent w/o one.
    expect(names).not.toContain('list_subagents')
  })

  it('exposes the exact record store to retained tool slices', () => {
    const inf = rt.intelligence as never as { __mnemicField?: unknown }
    expect(inf.__mnemicField).toBe(rt.field)
  })

  it('executes retained mind tools through the registry', async () => {
    const res = await rt.executeTool('list_sessions', {})
    expect(typeof res.result).toBe('string')
  })

  it('memory save → search round-trips through the field', async () => {
    const id = rt.memory.save({ content: 'a golden thought about the mind', type: 'fact' })
    expect(id).toBeTypeOf('string')
    const hits = await rt.memory.search('golden thought')
    expect(Array.isArray(hits)).toBe(true)
    expect(hits.length).toBeGreaterThan(0)
  })
})
