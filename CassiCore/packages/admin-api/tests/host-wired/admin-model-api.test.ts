/**
 * Admin API Model Configuration Endpoints
 *
 * These endpoints allow runtime inspection and modification of intelligence module
 * model configurations. Each intelligence module (thinker, dialectic, etc.) can
 * expose getModelConfig() and setModelConfig() methods to support hot-reloading
 * of model parameters without daemon restarts.
 *
 * Endpoints:
 *   - GET /intelligence/:module/model — retrieve current model configuration
 *   - POST /intelligence/:module/model — update model configuration at runtime
 *
 * This enables dynamic model selection, temperature adjustment, and token limit
 * tuning based on workload characteristics or operator preference.
 */

import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest'
import http from 'node:http'
import { createAdminApi } from '../src/admin-api.js'
import { mockLogger } from '../test-utils.js'

// HTTP request helper for testing admin API endpoints

/**
 * Makes an HTTP request to the admin API and returns status and parsed body.
 * Handles JSON serialization and content-length headers automatically.
 */
function request(
  port: number,
  method: string,
  path: string,
  body?: Record<string, unknown>,
): Promise<{ status: number; body: any }> {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : undefined
    const opts: http.RequestOptions = {
      hostname: '127.0.0.1',
      port,
      path,
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
      },
    }

    const req = http.request(opts, (res) => {
      const chunks: Buffer[] = []
      res.on('data', (c) => chunks.push(Buffer.from(c)))
      res.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8')
        let parsed: any
        try { parsed = JSON.parse(raw) } catch { parsed = raw }
        resolve({ status: res.statusCode ?? 0, body: parsed })
      })
    })

    req.on('error', reject)
    if (payload) req.write(payload)
    req.end()
  })
}

// Mock factories for creating testable intelligence modules

/**
 * Creates a mock intelligence module with configurable model configuration support.
 *
 * @param name - The module identifier (e.g., 'thinker', 'dialectic')
 * @param opts.legacy - If true, creates a legacy module without model config methods
 * @returns A mock module suitable for injection into the admin API
 */
function createMockModule(name: string, opts?: { legacy?: boolean }) {
  const modelConfig = {
    providerId: 'kimi-coding',
    model: 'k2p5',
    temperature: 0.3,
    maxTokens: 1024,
    timeoutMs: 10_000,
  }

  if (opts?.legacy) {
    // Legacy modules predate the runtime config feature and lack get/set methods
    return { name, priority: 50 }
  }

  return {
    name,
    priority: 50,
    getModelConfig: vi.fn(() => ({ ...modelConfig })),
    setModelConfig: vi.fn((overrides: Record<string, unknown>) => {
      Object.assign(modelConfig, overrides)
    }),
  }
}

/**
 * Creates a minimal mock daemon with just enough structure for the admin API
 * model configuration routes to function.
 */
function createMockDaemon(modules: any[]) {
  return {
    intelligence: {
      all: modules,
    },
    config: {
      get: vi.fn((_key: string, defaultVal?: any) => defaultVal),
    },
    sessions: { list: () => [] },
    pluginHost: { all: () => [] },
  }
}

// Test suite for admin API model configuration endpoints

describe('Admin API Model Configuration', () => {
  let api: { start: () => Promise<{ tcpPort: number | null; unixPath: string }>; stop: () => Promise<void> }
  let port: number
  let thinkerMod: ReturnType<typeof createMockModule>
  let dialecticMod: ReturnType<typeof createMockModule>
  let legacyMod: ReturnType<typeof createMockModule>

  beforeAll(async () => {
    thinkerMod = createMockModule('thinker')
    dialecticMod = createMockModule('dialectic')
    legacyMod = createMockModule('memory', { legacy: true })

    const daemon = createMockDaemon([thinkerMod, dialecticMod, legacyMod])
    const logger = mockLogger()

    api = createAdminApi(daemon, logger)
    const result = await api.start()
    port = result.tcpPort!
    expect(port).toBeGreaterThan(0)
  })

  afterAll(async () => {
    await api.stop()
  })

  // Retrieving current model configuration

  describe('GET /intelligence/:module/model', () => {
    it('returns the complete model configuration for a modern module', async () => {
      const res = await request(port, 'GET', '/intelligence/thinker/model')

      expect(res.status).toBe(200)
      expect(res.body.module).toBe('thinker')
      expect(res.body.config).toBeDefined()
      expect(res.body.config.providerId).toBe('kimi-coding')
      expect(res.body.config.model).toBe('k2p5')
      expect((thinkerMod as any).getModelConfig).toHaveBeenCalled()
    })

    it('returns 404 when requesting config for a non-existent module', async () => {
      const res = await request(port, 'GET', '/intelligence/nonexistent/model')

      expect(res.status).toBe(404)
      expect(res.body.error).toMatch(/not found/i)
    })

    it('returns 400 for legacy modules that lack getModelConfig method', async () => {
      const res = await request(port, 'GET', '/intelligence/memory/model')

      expect(res.status).toBe(400)
      expect(res.body.error).toMatch(/legacy module/i)
    })

    it('returns different configs for different modules', async () => {
      const res = await request(port, 'GET', '/intelligence/dialectic/model')

      expect(res.status).toBe(200)
      expect(res.body.module).toBe('dialectic')
      expect(res.body.config).toBeDefined()
    })
  })

  // Updating model configuration at runtime

  describe('POST /intelligence/:module/model', () => {
    it('updates model configuration with partial field overrides', async () => {
      const res = await request(port, 'POST', '/intelligence/thinker/model', {
        temperature: 0.8,
        maxTokens: 4096,
      })

      expect(res.status).toBe(200)
      expect(res.body.module).toBe('thinker')
      expect(res.body.updated).toContain('temperature')
      expect(res.body.updated).toContain('maxTokens')
      expect((thinkerMod as any).setModelConfig).toHaveBeenCalledWith(
        expect.objectContaining({ temperature: 0.8, maxTokens: 4096 }),
      )
    })

    it('accepts provider/model shorthand format for convenience', async () => {
      const res = await request(port, 'POST', '/intelligence/dialectic/model', {
        model: 'github-copilot/gpt-5-mini',
      })

      expect(res.status).toBe(200)
      expect(res.body.updated).toContain('model')
      expect((dialecticMod as any).setModelConfig).toHaveBeenCalledWith(
        expect.objectContaining({ model: 'github-copilot/gpt-5-mini' }),
      )
    })

    it('returns 400 when request body contains no valid config fields', async () => {
      const res = await request(port, 'POST', '/intelligence/thinker/model', {})

      expect(res.status).toBe(400)
      expect(res.body.error).toMatch(/no model config fields/i)
    })

    it('returns 404 when updating config for a non-existent module', async () => {
      const res = await request(port, 'POST', '/intelligence/nonexistent/model', {
        model: 'some-model',
      })

      expect(res.status).toBe(404)
      expect(res.body.error).toMatch(/not found/i)
    })

    it('returns 400 for legacy modules that lack setModelConfig method', async () => {
      const res = await request(port, 'POST', '/intelligence/memory/model', {
        model: 'some-model',
      })

      expect(res.status).toBe(400)
      expect(res.body.error).toMatch(/legacy module/i)
    })

    it('accepts all five configurable fields in a single update', async () => {
      const overrides = {
        model: 'new-model',
        providerId: 'new-provider',
        temperature: 0.5,
        maxTokens: 2048,
        timeoutMs: 30_000,
      }

      const res = await request(port, 'POST', '/intelligence/thinker/model', overrides)

      expect(res.status).toBe(200)
      expect(res.body.updated).toHaveLength(5)
      expect(res.body.updated).toEqual(
        expect.arrayContaining(['model', 'providerId', 'temperature', 'maxTokens', 'timeoutMs']),
      )
    })

    it('returns the updated configuration in the response body', async () => {
      const res = await request(port, 'POST', '/intelligence/thinker/model', {
        model: 'verify-return',
      })

      expect(res.status).toBe(200)
      expect(res.body.config).toBeDefined()
      // getModelConfig is called after setModelConfig to retrieve the new state
      expect((thinkerMod as any).getModelConfig).toHaveBeenCalled()
    })
  })

  // Edge cases and error handling

  describe('edge cases and error conditions', () => {
    it('handles invalid JSON in request body gracefully', async () => {
      return new Promise<void>((resolve, reject) => {
        const opts: http.RequestOptions = {
          hostname: '127.0.0.1',
          port,
          path: '/intelligence/thinker/model',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': '5',
          },
        }

        const req = http.request(opts, (res) => {
          expect(res.statusCode).toBeGreaterThanOrEqual(400)
          resolve()
        })

        req.on('error', reject)
        req.write('bad{!')
        req.end()
      })
    })

    it('ignores unknown config fields while updating valid ones', async () => {
      const res = await request(port, 'POST', '/intelligence/thinker/model', {
        temperature: 0.9,
        unknownField: 'ignored',
        anotherInvalid: 123,
      })

      expect(res.status).toBe(200)
      expect(res.body.updated).toContain('temperature')
      // The API filters to only known config fields before calling setModelConfig
      expect((thinkerMod as any).setModelConfig).toHaveBeenCalledWith({ temperature: 0.9 })
    })

    it('handles boundary temperature values correctly', async () => {
      const res = await request(port, 'POST', '/intelligence/thinker/model', {
        temperature: 0,
      })

      expect(res.status).toBe(200)
      expect((thinkerMod as any).setModelConfig).toHaveBeenCalledWith(
        expect.objectContaining({ temperature: 0 }),
      )
    })

    it('handles large maxTokens values correctly', async () => {
      const res = await request(port, 'POST', '/intelligence/thinker/model', {
        maxTokens: 128_000,
      })

      expect(res.status).toBe(200)
      expect((thinkerMod as any).setModelConfig).toHaveBeenCalledWith(
        expect.objectContaining({ maxTokens: 128_000 }),
      )
    })

    it('handles special characters in model names', async () => {
      const res = await request(port, 'POST', '/intelligence/dialectic/model', {
        model: 'provider/model-name_v2.5:extended',
      })

      expect(res.status).toBe(200)
      expect((dialecticMod as any).setModelConfig).toHaveBeenCalledWith(
        expect.objectContaining({ model: 'provider/model-name_v2.5:extended' }),
      )
    })
  })
})
