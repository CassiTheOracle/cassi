/**
 * @cassicore/mind-runtime — retained mind-tools runtime test.
 *
 * Asserts the registered retained mind tools execute against the booted retained
 * mind with its injected deps and return non-empty strings WITHOUT throwing —
 * with no live LLM providers (P3 boots the cognitive field + loops, no provider
 * calls; the mind_complete cutover is P4).
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

describe('retained mind tools execute in the runtime', () => {
  let home: string
  let rt: MindRuntime

  beforeAll(async () => {
    home = mkdtempSync(join(tmpdir(), 'cassimind-tools-'))
    rt = await createMindRuntime({ logger: quietLogger, homePath: home, disableUnifiedLoop: true, disableOscillation: true })
  }, 30_000)

  afterAll(async () => {
    await rt.close()
    try { rmSync(home, { recursive: true, force: true }) } catch { /* best effort */ }
  })

  it.each([
    ['list_sessions', {}],
    ['system_health', {}],
    ['_reflect', {}],
    ['graph_discover', {}],
    ['cassandra_query_events', { sessionId: 'none' }],
  ])('tool %s returns a non-empty string without throwing', async (tool, params) => {
    const res = await rt.executeTool(tool, params as Record<string, unknown>)
    expect(typeof res.result).toBe('string')
    expect(res.result.length).toBeGreaterThan(0)
  })

  it('collect_thoughts runs the enrichment pipeline and returns JSON', async () => {
    const res = await rt.executeTool('collect_thoughts', {
      thought: 'a tiny thought', step: 1, estimated_steps: 2, continue_thinking: true,
    })
    expect(res.result.length).toBeGreaterThan(0)
    // Returns structured JSON (CollectThoughtsResult).
    const parsed = JSON.parse(res.result)
    expect(parsed.step.recorded).toBe(true)
  })

  it('memory tools operate on the shared field', async () => {
    const saved = await rt.executeTool('remember', { note: 'a fact to keep' })
    expect(saved.result).toContain('Stored memory')
    const found = await rt.executeTool('memory_search', { query: 'fact to keep' })
    expect(found.result.length).toBeGreaterThan(0)
  })
})
