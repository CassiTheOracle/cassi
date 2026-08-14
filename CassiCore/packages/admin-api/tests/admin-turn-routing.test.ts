import { describe, expect, it, vi } from 'vitest'
import { EventEmitter } from 'node:events'
import type http from 'node:http'

import { createAdminRuntimeFacade } from '../src/routes/runtime.js'
import { handleChatRoutes } from '../src/routes/chat.js'
import { handleSessionsRoutes } from '../src/routes/sessions.js'
import {
  cancelTurn,
  executeTurn,
  resolveSessionPipelineSessionId,
  resolveStreamSessionId,
} from '../src/routes/turn-routing.js'

function createBus() {
  const handlers = new Map<string, Set<(event: any) => void>>()

  return {
    on(type: string, handler: (event: any) => void) {
      const bucket = handlers.get(type) ?? new Set<(event: any) => void>()
      bucket.add(handler)
      handlers.set(type, bucket)
    },
    off(type: string, handler: (event: any) => void) {
      handlers.get(type)?.delete(handler)
    },
    emit(event: any) {
      for (const handler of handlers.get(event.type) ?? []) {
        handler(event)
      }
    },
  }
}

function createReq(headers: Record<string, string> = {}) {
  const req = new EventEmitter() as http.IncomingMessage & EventEmitter
  Object.assign(req, {
    headers,
    socket: {
      setTimeout: vi.fn(),
      on: vi.fn(),
    },
  })
  return req
}

function createRes() {
  const res = new EventEmitter() as http.ServerResponse & EventEmitter & {
    writes: string[]
    statusCode?: number
    body?: unknown
    writable: boolean
  }

  Object.assign(res, {
    writes: [] as string[],
    writable: true,
    writeHead: vi.fn(),
    write: vi.fn((chunk: string) => {
      res.writes.push(chunk)
      return true
    }),
    end: vi.fn(() => {
      res.writable = false
      return res
    }),
  })

  return res
}

function createLogger() {
  const logger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(() => logger),
  }

  return logger
}

function createRuntime(overrides: Record<string, unknown> = {}) {
  const logger = (overrides.logger as ReturnType<typeof createLogger>) ?? createLogger()
  const bus = (overrides.bus as ReturnType<typeof createBus>) ?? createBus()

  return createAdminRuntimeFacade({
    logger,
    bus,
    ...overrides,
  } as any)
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })

  return { promise, resolve, reject }
}

describe('admin turn routing', () => {
  it('prefers the session pipeline and normalizes unknown models', async () => {
    const sessionPipeline = {
      processMessage: vi.fn().mockResolvedValue({
        response: 'hello',
        sessionId: 'internal-session',
        model: 'kimi-k2.5',
        tokensUsed: 12,
        durationMs: 34,
      }),
    }

    const result = await executeTurn(
      { sessionPipeline },
      {
        requestedSessionId: 'external-session',
        channelId: 'channel:cli',
        senderId: 'external-session',
        content: 'hi',
        model: 'unknown',
      },
    )

    expect(sessionPipeline.processMessage).toHaveBeenCalledWith(
      'channel:cli',
      'external-session',
      'hi',
      expect.objectContaining({ model: undefined }),
    )
    expect(result).toMatchObject({
      engine: 'session-pipeline',
      requestedSessionId: 'external-session',
      sessionId: 'internal-session',
      response: 'hello',
    })
  })

  it('falls back to the legacy pipeline and preserves the requested session id', async () => {
    const pipeline = {
      process: vi.fn().mockResolvedValue({
        response: 'legacy-response',
        model: 'legacy-model',
        tokensUsed: 4,
        durationMs: 9,
      }),
    }

    const result = await executeTurn(
      { pipeline },
      {
        requestedSessionId: 'legacy-session',
        channelId: 'channel:cli',
        senderId: 'legacy-session',
        content: 'hi',
      },
    )

    expect(pipeline.process).toHaveBeenCalledWith(
      expect.objectContaining({
        sessionId: 'legacy-session',
        channelId: 'channel:cli',
        senderId: 'legacy-session',
        content: 'hi',
      }),
    )
    expect(result).toMatchObject({
      engine: 'legacy-pipeline',
      sessionId: 'legacy-session',
      requestedSessionId: 'legacy-session',
      response: 'legacy-response',
    })
  })

  it('reports active session-pipeline turns as non-cancellable', async () => {
    const pending = deferred<{ response: string; sessionId: string }>()
    const sessionPipeline = {
      processMessage: vi.fn(() => pending.promise),
    }

    const turnPromise = executeTurn(
      { sessionPipeline },
      {
        requestedSessionId: 'active-session',
        channelId: 'channel:cli',
        senderId: 'active-session',
        content: 'hello',
      },
    )

    await Promise.resolve()

    expect(cancelTurn({ sessionPipeline }, 'active-session')).toEqual({
      engine: 'session-pipeline',
      supported: false,
      cancelled: false,
      active: true,
    })

    pending.resolve({ response: 'done', sessionId: 'internal-session' })
    await turnPromise
  })

  it('derives stream ids from channel and sender when the session pipeline is active', () => {
    const expected = resolveSessionPipelineSessionId('channel:cli', 'stream-session')

    expect(
      resolveStreamSessionId(
        { sessionPipeline: { processMessage: vi.fn() } },
        'stream-session',
        'channel:cli',
        'stream-session',
      ),
    ).toBe(expected)

    expect(resolveStreamSessionId({ pipeline: { process: vi.fn() } }, 'stream-session', 'channel:cli', 'stream-session')).toBe('stream-session')
  })

  it('routes chat stream events using the resolved session-pipeline id', async () => {
    const bus = createBus()
    const logger = createLogger()
    const req = createReq()
    const res = createRes()
    const sessionId = 'chat-stream'
    const streamSessionId = resolveSessionPipelineSessionId('channel:cli', sessionId)
    const runtime = createRuntime({
      logger,
      bus,
      sessionPipeline: { processMessage: vi.fn() },
    })

    const handled = await handleChatRoutes(
      {
        runtime,
        logger,
        sendJSON: vi.fn(),
        parseBody: vi.fn(),
        parts: ['chat', sessionId, 'stream'],
      },
      req,
      res,
      'GET',
      `/chat/${sessionId}/stream`,
    )

    expect(handled).toBe(true)

    bus.emit({
      type: 'worker:message',
      pluginId: `session:${streamSessionId}`,
      payload: { type: 'turn:token', token: 'hello' },
    })

    expect(res.writes.some(chunk => chunk.includes('hello'))).toBe(true)
  })

  it('returns explicit engine metadata for session route turns', async () => {
    const logger = createLogger()
    const req = createReq({ accept: 'application/json' })
    const res = createRes()
    const runtime = createRuntime({
      logger,
      sessionPipeline: {
        processMessage: vi.fn().mockResolvedValue({
          response: 'session-response',
          sessionId: 'internal-session',
          model: 'kimi-k2.5',
          tokensUsed: 9,
          durationMs: 21,
        }),
      },
    })
    const sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void = (response, code, body) => {
      response.statusCode = code
      ;(response as typeof res).body = body
    }

    const handled = await handleSessionsRoutes(
      {
        runtime,
        logger,
        sendJSON,
        parseBody: vi.fn().mockResolvedValue({ content: 'hello', model: 'kimi-k2.5' }),
        getFirstUserMessage: vi.fn(),
        getLastUserMessage: vi.fn(),
        tcpHost: '127.0.0.1',
        currentTcpPort: 7433,
      },
      req,
      res,
      'POST',
      '/sessions/external-session/turn',
      ['sessions', 'external-session', 'turn'],
    )

    expect(handled).toBe(true)
    expect(res.statusCode).toBe(200)
    expect(res.body).toMatchObject({
      ok: true,
      engine: 'session-pipeline',
      sessionId: 'internal-session',
      requestedSessionId: 'external-session',
      response: 'session-response',
    })
  })

  it('preserves legacy session ids when only the legacy pipeline is available', async () => {
    const logger = createLogger()
    const req = createReq({ accept: 'application/json' })
    const res = createRes()
    const runtime = createRuntime({
      logger,
      pipeline: {
        process: vi.fn().mockResolvedValue({
          response: 'legacy-session-response',
          model: 'legacy-model',
          tokensUsed: 3,
          durationMs: 8,
        }),
      },
      sessions: {
        getOrCreateById: vi.fn().mockReturnValue({ history: [] }),
      },
      intelligence: null,
      toolRegistry: {
        getAll: vi.fn().mockReturnValue({}),
      },
      config: {
        get: vi.fn((key: string, fallback: unknown) => fallback),
      },
    })
    const sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void = (response, code, body) => {
      response.statusCode = code
      ;(response as typeof res).body = body
    }

    const handled = await handleSessionsRoutes(
      {
        runtime,
        logger,
        sendJSON,
        parseBody: vi.fn().mockResolvedValue({ content: 'hello' }),
        getFirstUserMessage: vi.fn(),
        getLastUserMessage: vi.fn(),
        tcpHost: '127.0.0.1',
        currentTcpPort: 7433,
      },
      req,
      res,
      'POST',
      '/sessions/legacy-session/turn',
      ['sessions', 'legacy-session', 'turn'],
    )

    expect(handled).toBe(true)
    expect(res.statusCode).toBe(200)
    expect(res.body).toMatchObject({
      ok: true,
      engine: 'legacy-pipeline',
      sessionId: 'legacy-session',
      requestedSessionId: 'legacy-session',
      response: 'legacy-session-response',
    })
  })
})
