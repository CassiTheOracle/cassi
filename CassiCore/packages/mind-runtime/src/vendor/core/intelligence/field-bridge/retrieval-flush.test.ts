import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import type { ILogger } from '@cassicore/foundation'
import { FieldShadowBridge, type RetrievalPositionRecord } from './index.js'
import { StandardMindFieldEncoder } from '../field-encoder/index.js'

const noopLogger: ILogger = {
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
  child: () => noopLogger,
}

/** A queue that supplies retrieval records and no deposits. */
function retrievalQueue(records: RetrievalPositionRecord[]) {
  return {
    dequeue: () => [] as number[][],
    retrievals: () => records,
  }
}

function tmpLogPath(): string {
  return path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'cassi-retr-flush-')), 'mind.jsonl')
}

describe('FieldShadowBridge retrieval flush (Stage 4, parity by construction)', () => {
  it('unset retrievalLogPath → drain() writes no file and behaves exactly as before', async () => {
    const logPath = tmpLogPath()
    const bridge = new FieldShadowBridge(
      new StandardMindFieldEncoder(),
      retrievalQueue([{ t: '2026-08-13T00:00:00Z', hits: [{ x: 0.1, y: -0.2, z: 0.3 }] }]),
      { enabled: false }, // no retrievalLogPath — flush disabled
      noopLogger,
    )
    const n = await bridge.drain()
    // Deposit behavior unchanged: nothing went out, nothing written.
    expect(n).toBe(0)
    expect(fs.existsSync(logPath)).toBe(false)
  })

  it('set retrievalLogPath + fake queue → drain() appends valid JSONL retrieval lines', async () => {
    const logPath = tmpLogPath()
    const records: RetrievalPositionRecord[] = [
      { t: '2026-08-13T00:00:01Z', hits: [{ x: 0.1, y: 0.2, z: 0.3 }, { x: -0.4, y: 0.5, z: -0.6 }] },
      { t: '2026-08-13T00:00:02Z', hits: [{ x: 0.7, y: 0.8, z: 0.9 }] },
    ]
    const bridge = new FieldShadowBridge(
      new StandardMindFieldEncoder(),
      retrievalQueue(records),
      { enabled: false, retrievalLogPath: logPath },
      noopLogger,
    )
    const n = await bridge.drain()
    // Deposit side disabled — drain returns 0, but the flush must still run.
    expect(n).toBe(0)
    expect(fs.existsSync(logPath)).toBe(true)

    const lines = fs.readFileSync(logPath, 'utf8').trim().split('\n')
    expect(lines).toHaveLength(2)
    const parsed = lines.map((l) => JSON.parse(l))
    expect(parsed[0]).toMatchObject({
      t: '2026-08-13T00:00:01Z',
      retrievals: [
        { x: 0.1, y: 0.2, z: 0.3 },
        { x: -0.4, y: 0.5, z: -0.6 },
      ],
    })
    expect(parsed[1]).toMatchObject({
      t: '2026-08-13T00:00:02Z',
      retrievals: [{ x: 0.7, y: 0.8, z: 0.9 }],
    })
  })

  it('empty retrieval batches append nothing (no empty lines, no file if never non-empty)', async () => {
    const logPath = tmpLogPath()
    const bridge = new FieldShadowBridge(
      new StandardMindFieldEncoder(),
      retrievalQueue([]),
      { enabled: false, retrievalLogPath: logPath },
      noopLogger,
    )
    expect(await bridge.drain()).toBe(0)
    expect(fs.existsSync(logPath)).toBe(false)
  })

  it('write failure (invalid location) → drain() does not throw and logs bounded', async () => {
    // A path whose parent is a regular file: mkdirSync(recursive) fails
    // (ENOTDIR) — the flush must swallow it, never throw into the harness.
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cassi-retr-flush-fail-'))
    const bogusParent = path.join(dir, 'not-a-dir') // not created
    fs.writeFileSync(bogusParent, 'i am a file, not a dir')
    const logPath = path.join(bogusParent, 'deep', 'mind.jsonl') // ENOTDIR

    const warnings: unknown[] = []
    let count = 0
    const countingLogger: ILogger = {
      ...noopLogger,
      warn: (msg) => {
        warnings.push(msg)
        count += 1
      },
      child: () => countingLogger,
    }
    const bridge = new FieldShadowBridge(
      new StandardMindFieldEncoder(),
      retrievalQueue([{ t: '2026-08-13T00:00:00Z', hits: [{ x: 0, y: 0, z: 0 }] }]),
      { enabled: false, retrievalLogPath: logPath },
      countingLogger,
    )
    // Must resolve (never throw) even though the append path is invalid.
    await expect(bridge.drain()).resolves.toBe(0)
    expect(fs.existsSync(logPath)).toBe(false)
    expect(count).toBeGreaterThan(0)

    fs.rmSync(dir, { recursive: true, force: true })
  })
})
