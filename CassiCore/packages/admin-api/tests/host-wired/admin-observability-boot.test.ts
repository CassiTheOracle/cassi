import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import http from 'node:http'

import { createAdminApi } from '../core/admin-api.js'
import type { DaemonBootSnapshot } from '../core/daemon.js'
import { mockLogger } from './helpers.js'

function request(port: number, path: string): Promise<{ status: number; body: any }> {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: '127.0.0.1',
      port,
      path,
      method: 'GET',
    }, (res) => {
      const chunks: Buffer[] = []
      res.on('data', (chunk) => chunks.push(Buffer.from(chunk)))
      res.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8')
        let body: any
        try {
          body = JSON.parse(raw)
        } catch {
          body = raw
        }
        resolve({ status: res.statusCode ?? 0, body })
      })
    })

    req.on('error', reject)
    req.end()
  })
}

function createBootSnapshot(sequence: number, offsetMs: number): DaemonBootSnapshot {
  const startedAt = 1_710_000_000_000 + offsetMs
  const readyAt = startedAt + 3_250
  return {
    sequence,
    pid: 4242,
    startedAt,
    readyAt,
    durationMs: 3_250,
    timeToAdminReadyMs: 2_100,
    phases: [
      {
        name: 'configuration',
        startedAt,
        endedAt: startedAt + 250,
        sinceBootMs: 0,
        durationMs: 250,
      },
      {
        name: 'services',
        startedAt: readyAt - 500,
        endedAt: readyAt,
        sinceBootMs: 2_750,
        durationMs: 500,
      },
    ],
    services: [
      {
        name: 'admin-api',
        startedAt: startedAt + 1_500,
        readyAt: startedAt + 2_100,
        sinceBootMs: 1_500,
        durationMs: 600,
        meta: {
          status: 'ready',
          tcpPort: 7433,
        },
      },
    ],
  }
}

function createMockDaemon() {
  const history: DaemonBootSnapshot[] = [
    createBootSnapshot(1, 0),
    createBootSnapshot(2, 10_000),
    createBootSnapshot(3, 20_000),
  ]

  return {
    getBootMetrics: vi.fn<() => DaemonBootSnapshot | null>(() => history[history.length - 1] ?? null),
    getBootMetricsHistory: vi.fn((limit = 10) => history.slice(-limit)),
    bus: {
      on: vi.fn(),
      off: vi.fn(),
    },
    config: {
      get: vi.fn((key: string, defaultValue?: unknown) => {
        if (key === 'admin.host') return '127.0.0.1'
        if (key === 'admin.port') return 0
        return defaultValue
      }),
    },
    sessions: { list: vi.fn(() => []) },
    pluginHost: { all: vi.fn(() => []) },
    intelligence: { all: [] },
  }
}

describe('Admin API boot observability', () => {
  let api: ReturnType<typeof createAdminApi>
  let port: number
  let daemon: ReturnType<typeof createMockDaemon>

  beforeAll(async () => {
    daemon = createMockDaemon()
    api = createAdminApi(daemon, mockLogger())
    const result = await api.start()
    port = result.tcpPort ?? 0
  })

  afterAll(async () => {
    await api.stop()
  })

  it('returns the latest boot snapshot and bounded history', async () => {
    const response = await request(port, '/observability/boot?limit=2')

    expect(response.status).toBe(200)
    expect(daemon.getBootMetricsHistory).toHaveBeenCalledWith(2)
    expect(response.body.current.sequence).toBe(3)
    expect(response.body.history).toHaveLength(2)
    expect(response.body.history[0].sequence).toBe(2)
    expect(response.body.history[1].sequence).toBe(3)
    expect(response.body.current.timeToAdminReadyMs).toBe(2_100)
    expect(response.body.current.services[0].name).toBe('admin-api')
    expect(response.body.process.pid).toBe(process.pid)
    expect(typeof response.body.process.uptimeMs).toBe('number')
    expect(typeof response.body.process.startedAt).toBe('number')
  })

  it('returns null when boot metrics are not available yet', async () => {
    daemon.getBootMetrics.mockReturnValueOnce(null)
    daemon.getBootMetricsHistory.mockReturnValueOnce([])

    const response = await request(port, '/observability/boot')

    expect(response.status).toBe(200)
    expect(response.body.current).toBeNull()
    expect(response.body.history).toEqual([])
  })
})
