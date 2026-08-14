/**
 * Roundtrip integration test for the ACP bridge.
 *
 * Spins a mock daemon HTTP server that mimics
 * POST /admin/sessions/:id/turn/stream SSE, then drives a CassiAgent
 * through newSession → prompt and asserts session updates translate
 * correctly.
 */

import http from 'node:http'
import type { AddressInfo } from 'node:net'

import { describe, it, expect, beforeAll, afterAll } from 'vitest'

import { CassiAgent } from '../src/bridge/acp/server.js'

import type {
  AgentSideConnection,
  PromptRequest,
  NewSessionRequest,
  InitializeRequest,
} from '@zed-industries/agent-client-protocol'

type Scenario = 'happy' | 'error' | 'slow'

function startMockDaemon(): Promise<{ baseUrl: string; close: () => Promise<void> }> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      if (req.method === 'POST' && req.url === '/sessions') {
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ sessionId: '11111111-1111-4111-8111-111111111111' }))
        return
      }
      const m = req.url?.match(/^\/sessions\/([^/]+)\/turn\/stream$/)
      if (req.method !== 'POST' || !m) {
        res.writeHead(404)
        res.end()
        return
      }
      let body = ''
      req.on('data', (c) => (body += c))
      req.on('end', () => {
        const parsed = JSON.parse(body || '{}')
        const scenario: Scenario = parsed.content?.startsWith('error:')
          ? 'error'
          : parsed.content?.startsWith('slow:')
            ? 'slow'
            : 'happy'

        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        })

        const send = (event: string, data: unknown) => {
          res.write(`event: ${event}\n`)
          res.write(`data: ${JSON.stringify(data)}\n\n`)
        }

        if (scenario === 'error') {
          send('error', { error: 'daemon exploded' })
          res.end()
          return
        }

        if (scenario === 'slow') {
          send('token', { token: 'slow start...' })
          const timer = setTimeout(() => {
            if (!res.writableEnded) {
              send('done', {})
              res.end()
            }
          }, 5000)
          res.on('close', () => clearTimeout(timer))
          return
        }

        send('token', { token: 'Hello, ' })
        send('token', { token: 'world!' })
        send('tool_call', {
          toolCallId: 'tcid_42',
          tool: 'cassi_memory',
          input: { action: 'search', query: 'hi' },
        })
        send('tool_result', {
          toolCallId: 'tcid_42',
          isError: false,
          content: 'found nothing relevant',
        })
        send('done', {})
        res.end()
      })
    })
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address() as AddressInfo
      resolve({
        baseUrl: `http://127.0.0.1:${addr.port}`,
        close: () =>
          new Promise<void>((r) => {
            server.close(() => r())
          }),
      })
    })
  })
}

function makeStubConn(): { conn: AgentSideConnection; updates: any[] } {
  const updates: any[] = []
  const conn = {
    sessionUpdate: async (u: unknown) => {
      updates.push(u)
    },
  } as unknown as AgentSideConnection
  return { conn, updates }
}

describe('CassiAgent ACP bridge (roundtrip against mock daemon)', () => {
  let baseUrl: string
  let shutdown: () => Promise<void>

  beforeAll(async () => {
    const srv = await startMockDaemon()
    baseUrl = srv.baseUrl
    shutdown = srv.close
  })

  afterAll(async () => {
    await shutdown()
  })

  it('initialize advertises ACP capabilities', async () => {
    const { conn } = makeStubConn()
    const agent = new CassiAgent(conn, { baseUrl })
    const resp = await agent.initialize({
      protocolVersion: 1,
    } as InitializeRequest)
    expect(resp.protocolVersion).toBeGreaterThan(0)
    expect(resp.agentCapabilities.loadSession).toBe(false)
    expect(resp.agentCapabilities.promptCapabilities?.image).toBe(false)
  })

  it('newSession returns a valid UUID sessionId', async () => {
    const { conn } = makeStubConn()
    const agent = new CassiAgent(conn, { baseUrl })
    const resp = await agent.newSession({
      mcpServers: [],
      cwd: process.cwd(),
    } as unknown as NewSessionRequest)
    expect(resp.sessionId).toMatch(/^[0-9a-f-]{36}$/i)
  })

  it('prompt streams tokens + tool_call + tool_result as ACP session updates', async () => {
    const { conn, updates } = makeStubConn()
    const agent = new CassiAgent(conn, { baseUrl })

    const { sessionId } = await agent.newSession({
      mcpServers: [],
      cwd: process.cwd(),
    } as unknown as NewSessionRequest)

    const result = await agent.prompt({
      sessionId,
      prompt: [{ type: 'text', text: 'hi' }],
    } as unknown as PromptRequest)

    expect(result.stopReason).toBe('end_turn')
    expect(updates).toHaveLength(4)

    expect(updates[0].sessionId).toBe(sessionId)
    expect(updates[0].update.sessionUpdate).toBe('agent_message_chunk')
    expect(updates[0].update.content).toEqual({ type: 'text', text: 'Hello, ' })

    expect(updates[1].update.sessionUpdate).toBe('agent_message_chunk')
    expect(updates[1].update.content).toEqual({ type: 'text', text: 'world!' })

    expect(updates[2].update.sessionUpdate).toBe('tool_call')
    expect(updates[2].update.toolCallId).toBe('tcid_42')
    expect(updates[2].update.title).toBe('cassi_memory')
    expect(updates[2].update.rawInput).toEqual({ action: 'search', query: 'hi' })

    expect(updates[3].update.sessionUpdate).toBe('tool_call_update')
    expect(updates[3].update.toolCallId).toBe('tcid_42')
    expect(updates[3].update.status).toBe('completed')
    expect(updates[3].update.content).toEqual([
      { type: 'content', content: { type: 'text', text: 'found nothing relevant' } },
    ])
  })

  it('prompt surfaces daemon error events as thrown errors', async () => {
    const { conn, updates } = makeStubConn()
    const agent = new CassiAgent(conn, { baseUrl })

    const { sessionId } = await agent.newSession({
      mcpServers: [],
      cwd: process.cwd(),
    } as unknown as NewSessionRequest)

    await expect(
      agent.prompt({
        sessionId,
        prompt: [{ type: 'text', text: 'error: boom' }],
      } as unknown as PromptRequest),
    ).rejects.toThrow(/daemon exploded/)

    expect(updates).toHaveLength(0)
  })

  it('cancel aborts an in-flight prompt', async () => {
    const { conn } = makeStubConn()
    const agent = new CassiAgent(conn, { baseUrl })

    const { sessionId } = await agent.newSession({
      mcpServers: [],
      cwd: process.cwd(),
    } as unknown as NewSessionRequest)

    const promptP = agent.prompt({
      sessionId,
      prompt: [{ type: 'text', text: 'slow: please' }],
    } as unknown as PromptRequest)

    await new Promise((r) => setTimeout(r, 100))
    await agent.cancel({ sessionId })

    const result = await promptP
    expect(result.stopReason).toBe('cancelled')
  })
})
