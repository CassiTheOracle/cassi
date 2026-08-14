import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import http from 'node:http'

import { createAdminApi } from '../src/admin-api.js'
import { EventBus } from '@cassicore/events'
import { mockLogger } from '../test-utils.js'

function request(
  port: number,
  method: string,
  path: string,
  body?: Record<string, unknown>,
  headers?: Record<string, string>,
): Promise<{ status: number; body: any }> {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : undefined
    const req = http.request({
      hostname: '127.0.0.1',
      port,
      path,
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(payload ? { 'Content-Length': String(Buffer.byteLength(payload)) } : {}),
        ...headers,
      },
    }, (res) => {
      const chunks: Buffer[] = []
      res.on('data', (chunk) => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)))
      res.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8')
        let parsed: any
        try {
          parsed = JSON.parse(raw)
        } catch {
          parsed = raw
        }
        resolve({ status: res.statusCode ?? 0, body: parsed })
      })
    })

    req.on('error', reject)
    if (payload) req.write(payload)
    req.end()
  })
}

describe('Admin Plugin API auth', () => {
  let api: { start: () => Promise<{ tcpPort: number | null; unixPath: string }>; stop: () => Promise<void> }
  let port: number

  beforeAll(async () => {
    const daemon = {
      bus: new EventBus(),
      config: {
        get: (key: string, defaultValue?: unknown) => {
          if (key === 'admin.token') return 'admin-secret'
          return defaultValue
        },
      },
      intelligence: { all: [] },
      sessions: { list: () => [] },
      pluginHost: { all: () => [] },
    }

    api = createAdminApi(daemon, mockLogger())
    const result = await api.start()
    port = result.tcpPort!
  })

  afterAll(async () => {
    await api.stop()
  })

  it('does not allow plugin bearer tokens to access /plugin/list', async () => {
    const registration = await request(port, 'POST', '/plugin/register', {
      id: 'test-plugin',
      name: 'Test Plugin',
      version: '1.0.0',
      transport: 'unix-socket',
      capabilities: ['session'],
    })

    expect(registration.status).toBe(200)
    expect(registration.body.apiKey).toMatch(/^cpk_/) 

    const pluginListWithPluginToken = await request(
      port,
      'GET',
      '/plugin/list',
      undefined,
      { Authorization: `Bearer ${registration.body.apiKey as string}` },
    )

    expect(pluginListWithPluginToken.status).toBe(401)

    const pluginListWithAdminToken = await request(
      port,
      'GET',
      '/plugin/list',
      undefined,
      { Authorization: 'Bearer admin-secret' },
    )

    expect(pluginListWithAdminToken.status).toBe(200)
    expect(pluginListWithAdminToken.body.ok).toBe(true)
    expect(pluginListWithAdminToken.body.plugins).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: 'test-plugin', name: 'Test Plugin' }),
      ]),
    )
  })
})
