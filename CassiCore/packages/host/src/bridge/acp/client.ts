import http from 'node:http'
import { URL } from 'node:url'

import type { ChatStreamEvent } from './types.js'

const ACP_DEFAULT_MODEL = 'deepseek-v4-pro'

export interface DaemonClientOptions {
  baseUrl?: string
  adminToken?: string
}

export class CassiDaemonClient {
  private readonly baseUrl: URL
  private readonly adminToken: string | undefined

  constructor(options: DaemonClientOptions = {}) {
    this.baseUrl = new URL(options.baseUrl || 'http://127.0.0.1:7433')
    this.adminToken = options.adminToken
  }

  private authHeaders(): Record<string, string> {
    return this.adminToken ? { Authorization: `Bearer ${this.adminToken}` } : {}
  }

  async createSession(name = 'ACP session'): Promise<string> {
    const url = new URL('/sessions', this.baseUrl)
    const payload = JSON.stringify({
      name,
      channelId: 'channel:acp',
      senderId: 'acp-client',
    })
    return await new Promise<string>((resolve, reject) => {
      const req = http.request(
        url,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload).toString(),
            ...this.authHeaders(),
          },
        },
        (res) => {
          const chunks: Buffer[] = []
          res.on('data', (c: Buffer) => chunks.push(c))
          res.on('end', () => {
            const body = Buffer.concat(chunks).toString('utf8')
            if (!res.statusCode || res.statusCode < 200 || res.statusCode >= 300) {
              reject(new Error(`createSession failed: HTTP ${res.statusCode} ${body}`))
              return
            }
            try {
              const parsed = JSON.parse(body)
              if (!parsed?.sessionId) {
                reject(new Error(`createSession: missing sessionId in response: ${body}`))
                return
              }
              resolve(String(parsed.sessionId))
            } catch (err) {
              reject(new Error(`createSession: invalid JSON: ${String(err)}`))
            }
          })
        },
      )
      req.once('error', reject)
      req.write(payload)
      req.end()
    })
  }

  async *executeTurnStream(
    sessionId: string,
    content: string,
    signal?: AbortSignal,
  ): AsyncIterable<ChatStreamEvent> {
    const url = new URL(
      `/sessions/${encodeURIComponent(sessionId)}/turn/stream`,
      this.baseUrl,
    )
    const payload = JSON.stringify({ content, channelId: 'channel:acp', model: ACP_DEFAULT_MODEL })
    const req = http.request(url, {
      method: 'POST',
      signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        'Content-Length': Buffer.byteLength(payload).toString(),
        ...this.authHeaders(),
      },
    })
    req.write(payload)
    req.end()

    const response: http.IncomingMessage = await new Promise((resolve, reject) => {
      req.once('response', resolve)
      req.once('error', reject)
    })

    if (response.statusCode && response.statusCode >= 400) {
      const body = await readAll(response)
      throw new Error(`daemon turn/stream failed: HTTP ${response.statusCode} ${body}`)
    }

    let buffer = ''
    response.setEncoding('utf8')
    try {
      for await (const chunk of response) {
        buffer += chunk
        let idx: number
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          const ev = parseSseFrame(frame)
          if (ev) {
            yield ev
            if (ev.type === 'response' || ev.type === 'error') return
          }
        }
      }
    } catch (err) {
      if (signal?.aborted) {
        yield { type: 'error', error: 'cancelled' }
        return
      }
      throw err
    }
    if (signal?.aborted) {
      yield { type: 'error', error: 'cancelled' }
    }
  }
}

async function readAll(res: http.IncomingMessage): Promise<string> {
  res.setEncoding('utf8')
  let out = ''
  for await (const chunk of res) out += chunk
  return out
}

function parseSseFrame(frame: string): ChatStreamEvent | null {
  let eventName = 'message'
  let data = ''
  for (const line of frame.split('\n')) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      data += line.slice(5).trimStart()
    }
  }
  if (!data) return null
  let payload: any
  try { payload = JSON.parse(data) } catch { return null }
  switch (eventName) {
    case 'token':
      return { type: 'token', token: String(payload.token ?? '') }
    case 'tool_call':
      return {
        type: 'tool_call',
        toolCallId: payload.toolCallId ? String(payload.toolCallId) : undefined,
        tool: String(payload.tool ?? 'unknown'),
        input: payload.input,
      }
    case 'tool_result':
      return {
        type: 'tool_result',
        toolCallId: payload.toolCallId ? String(payload.toolCallId) : undefined,
        tool: payload.tool ? String(payload.tool) : undefined,
        isError: Boolean(payload.isError),
        content: payload.content,
      }
    case 'done':
      return {
        type: 'response',
        text: String(payload.content ?? payload.response ?? ''),
        model: payload.model,
        tokensUsed: payload.tokensUsed,
        durationMs: payload.durationMs,
      }
    case 'error':
      return { type: 'error', error: String(payload.error ?? 'unknown') }
    default:
      return null
  }
}
