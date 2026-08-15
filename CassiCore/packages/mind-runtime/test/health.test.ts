/**
 * @cassicore/mind-runtime — retained mind-health read slice test (P5).
 *
 * Asserts `collectMindHealth(runtime)` returns a host-agnostic, read-only snapshot
 * across the retained admin disciplines (cortex/pineal/thalamus/memory/replay/
 * observability), reads real field + intelligence state, and never throws when a
 * subsystem is missing. This is the retained admin-api fold (§5 #27).
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { createMindRuntime, type MindRuntime } from '../src/index.js'
import { collectMindHealth } from '../src/health/index.js'
import type { ILogger } from '@cassicore/foundation'

const quietLogger: ILogger = {
  debug: () => {}, info: () => {}, warn: () => {}, error: () => {},
  child: () => quietLogger,
}

describe('mind-runtime retained health slice (admin-api fold)', () => {
  let home: string
  let rt: MindRuntime

  beforeAll(async () => {
    home = mkdtempSync(join(tmpdir(), 'cassimind-health-'))
    rt = await createMindRuntime({
      logger: quietLogger,
      homePath: home,
      disableUnifiedLoop: true,
      disableOscillation: true,
    })
  }, 30_000)

  afterAll(async () => {
    await rt.close()
    try { rmSync(home, { recursive: true, force: true }) } catch { /* Windows lock — best effort */ }
  })

  it('collects all six retained disciplines read-only, without throwing', () => {
    const snap = collectMindHealth(rt)
    expect(snap).toHaveProperty('cortex')
    expect(snap).toHaveProperty('pineal')
    expect(snap).toHaveProperty('thalamus')
    expect(snap).toHaveProperty('memory')
    expect(snap).toHaveProperty('replay')
    expect(snap).toHaveProperty('observability')
    // Every discipline is a typed object; none throws.
    for (const key of ['cortex', 'pineal', 'thalamus', 'memory', 'replay', 'observability'] as const) {
      expect(typeof snap[key].available).toBe('boolean')
    }
  })

  it('reads real MnemicField memory state (engrams + stats)', () => {
    const saved = rt.memory.save({ content: 'health probe memory', type: 'fact' })
    expect(saved).toBeTypeOf('string')
    const snap = collectMindHealth(rt)
    expect(snap.memory.available).toBe(true)
    expect(typeof snap.memory.engrams).toBe('number')
    expect(snap.memory.stats).toBeTruthy()
  })

  it('reports the retained replay/loops discipline against the running runtime', () => {
    const snap = collectMindHealth(rt)
    expect(snap.replay.available).toBe(true)
    expect(typeof snap.replay.uptimeMs).toBe('number')
    expect(snap.replay.loops?.unifiedLoop).toBe(true) // boot reports loop present
  })

  it('is read-only — does not mutate field or intelligence state', () => {
    const before = rt.field.stats()
    const snap = collectMindHealth(rt)
    const after = rt.field.stats()
    expect(after).toEqual(before)
    // Cortex health must be a report, not an emission: no side effect on stats.
    expect(typeof snap.cortex.available).toBe('boolean')
  })
})
