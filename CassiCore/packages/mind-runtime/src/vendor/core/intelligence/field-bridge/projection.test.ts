import { describe, expect, it } from 'vitest'
import * as net from 'node:net'

import type { ILogger } from '@cassicore/foundation'
import { FieldShadowBridge, parseProjectionReply } from './index.js'
import { StandardMindFieldEncoder } from '../field-encoder/index.js'
import { MindClient } from '../../../mind-plugin/src/mind-client.js'

const noopLogger: ILogger = {
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
  child: () => noopLogger,
}

function emptyQueue() {
  return { dequeue: () => [] }
}

function makeBridge(overrides: Record<string, unknown> = {}) {
  return new FieldShadowBridge(
    new StandardMindFieldEncoder(),
    emptyQueue(),
    { enabled: true, port: 7598, timeoutMs: 300, ...overrides },
    noopLogger,
  )
}

describe('FieldShadowBridge readProjection (Stage 4, parity by construction)', () => {
  it('disabled bridge returns [] without touching the network', async () => {
    const bridge = makeBridge({ enabled: false })
    const started = Date.now()
    const cells = await bridge.readProjection()
    // Disabled short-circuits before any connect/network work: must be
    // effectively instantaneous and empty.
    expect(Date.now() - started).toBeLessThan(50)
    expect(cells).toEqual([])
  })

  it('enabled bridge with the engine down returns [] and does not throw, fast', async () => {
    const bridge = makeBridge({ enabled: true, port: 7598, timeoutMs: 300 })
    const started = Date.now()
    // Port 7598 has no listener: connect is refused immediately (ECONNREFUSED),
    // well inside the 300ms wall-clock bound.
    await expect(bridge.readProjection()).resolves.toEqual([])
    expect(Date.now() - started).toBeLessThan(2000)
  })

  it('parses a synthetic project reply into cells, sorted by q DESC (order-tolerant)', () => {
    const reply = {
      ok: true,
      cmd: 'project',
      step: 41,
      t: 12.5,
      cells: [
        { i: 999, gx: 1, gy: 2, gz: 3, x: 0.1, y: 0.2, z: 0.3, ey: 0.4, ei: 0.3, q: 0.25 },
        { i: 1, gx: 0, gy: 0, gz: 0, x: -0.5, y: 0.5, z: 0, ey: 1.1, ei: 0.0, q: 1.21 },
        { i: 5, gx: 4, gy: 5, gz: 6, x: 0.0, y: 0.0, z: 0.0, ey: 0.1, ei: 0.0, q: 0.01 },
      ],
    }
    const cells = parseProjectionReply(reply, 8)
    expect(cells).toHaveLength(3)
    // Pre-sorted by the engine but re-sorted DESC defensively.
    expect(cells.map((c) => c.q)).toEqual([1.21, 0.25, 0.01])
    expect(cells[0]).toMatchObject({ i: 1, gx: 0, gy: 0, gz: 0, x: -0.5, y: 0.5, z: 0, ey: 1.1, q: 1.21 })
    expect(cells[1]).toMatchObject({ i: 999, x: 0.1, y: 0.2, z: 0.3, ei: 0.3, q: 0.25 })
  })

  it('tolerates missing/coercible fields and drops non-object entries', () => {
    const reply = {
      ok: true,
      cells: [
        { i: 3, q: '0.5' }, // missing coords/charges → coerced to defaults
        null,
        'nope',
        { i: 'not-a-number', q: NaN },
      ],
    }
    const cells = parseProjectionReply(reply, 8)
    // Only the two object entries survive; strings/null are skipped.
    expect(cells).toHaveLength(2)
    expect(cells[0].q).toBeCloseTo(0.5)
    expect(cells[0].x).toBe(0)
    expect(cells[1].q).toBe(0) // NaN coerced to 0
  })

  it('returns [] for a malformed reply (cells not an array) or non-ok reply', () => {
    expect(parseProjectionReply({ ok: true, cells: 'nope' }, 8)).toEqual([])
    expect(parseProjectionReply(null, 8)).toEqual([])
    expect(parseProjectionReply({ ok: false, cells: [] }, 8)).toEqual([])
    expect(parseProjectionReply({ ok: true }, 8)).toEqual([])
  })

  it('never hangs when the engine accepts the connection then dies without replying', async () => {
    // A server that accepts and destroys the socket as soon as it sees the
    // `project` request, WITHOUT replying — the exact "engine died after
    // connect but before reply" case that used to hang readProjection.
    const server = net.createServer((sock) => {
      sock.on('data', () => sock.destroy())
    })
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    const addr = server.address() as net.AddressInfo
    const bridge = makeBridge({ enabled: true, port: addr.port, timeoutMs: 1500 })
    try {
      const started = Date.now()
      const cells = await bridge.readProjection()
      // Must resolve (not hang) and be empty, well inside the ~2s bound.
      expect(cells).toEqual([])
      expect(Date.now() - started).toBeLessThan(2000)
    } finally {
      await new Promise<void>((resolve) => server.close(() => resolve()))
    }
  })

  it('MindClient send() rejects immediately when not connected (never queues forever)', async () => {
    const client = new MindClient(7598, '127.0.0.1')
    expect(client.connected).toBe(false)
    await expect(client.send({ cmd: 'project', k: 8 })).rejects.toThrow('not connected')
  })
})
