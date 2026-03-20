/**
 * CassiCore daemon client for cassi-watch.
 * Specialized for SSE streaming of LLM call events.
 */

import http from 'node:http'
import path from 'node:path'
import os from 'node:os'
import { EventEmitter } from 'node:events'

import type {
  WatchEvent,
  ProviderStartEvent,
  ProviderEndEvent,
  ProviderErrorEvent,
} from '../types/index.js'

const DEFAULT_DAEMON_URL = 'http://localhost:7433'
const DEFAULT_SOCKET_PATH = path.join(os.homedir(), '.cassicore', 'admin.sock')

interface WatchClientOptions {
  socketPath?: string
  baseURL?: string
}

/**
 * Client for streaming LLM call events from the CassiCore daemon.
 * Uses Server-Sent Events (SSE) over the admin API.
 */
export class WatchClient extends EventEmitter {
  private socketPath: string | undefined
  private baseURL: string
  private preferSocket: boolean
  private connectedVia: 'unix' | 'http' = 'http'
  private currentStream: http.IncomingMessage | null = null
  private isConnecting: boolean = false
  private reconnectAttempts: number = 0
  private maxReconnectAttempts: number = 5
  private reconnectDelayMs: number = 2000

  constructor(opts?: WatchClientOptions) {
    super()
    this.baseURL = opts?.baseURL ?? DEFAULT_DAEMON_URL
    this.socketPath = opts?.socketPath ?? DEFAULT_SOCKET_PATH
    this.preferSocket = !!this.socketPath
  }

  get connectionString(): string {
    if (this.connectedVia === 'unix' && this.socketPath) {
      return `unix:${this.socketPath}`
    }
    return this.baseURL
  }

  /**
   * Check if the daemon is reachable
   */
  async ping(): Promise<{ version: string; uptimeMs: number }> {
    return new Promise((resolve, reject) => {
      const trySocket = () => {
        if (!this.socketPath) {
          tryHttp()
          return
        }

        const req = http.get(
          {
            socketPath: this.socketPath,
            path: '/health',
            timeout: 5000,
          },
          (res) => {
            if (res.statusCode === 200) {
              this.connectedVia = 'unix'
              readJSON(res, resolve, reject)
            } else {
              tryHttp()
            }
          },
        )
        req.on('error', tryHttp)
        req.on('timeout', () => {
          req.destroy()
          tryHttp()
        })
      }

      const tryHttp = () => {
        const url = new URL('/health', this.baseURL)
        const req = http.get(
          {
            hostname: url.hostname,
            port: url.port,
            path: url.pathname + url.search,
            timeout: 5000,
          },
          (res) => {
            if (res.statusCode === 200) {
              this.connectedVia = 'http'
              this.preferSocket = false
              readJSON(res, resolve, reject)
            } else {
              reject(new Error(`Health check failed: HTTP ${res.statusCode}`))
            }
          },
        )
        req.on('error', reject)
        req.on('timeout', () => {
          req.destroy()
          reject(new Error('Health check timeout'))
        })
      }

      if (this.preferSocket) {
        trySocket()
      } else {
        tryHttp()
      }
    })
  }

  /**
   * Start streaming LLM call events via SSE.
   * Emits events via EventEmitter interface.
   */
  async startStream(filters?: {
    provider?: string
    session?: string
  }): Promise<void> {
    if (this.isConnecting) {
      return
    }

    this.isConnecting = true
    this.reconnectAttempts = 0

    const queryParams = new URLSearchParams()
    if (filters?.provider) {
      queryParams.set('provider', filters.provider)
    }
    if (filters?.session) {
      queryParams.set('session', filters.session)
    }
    queryParams.set('includeTokens', 'true')

    const path = `/observability/prompts/stream?${queryParams.toString()}`

    const connect = () => {
      const opts: http.RequestOptions = this.preferSocket
        ? {
            socketPath: this.socketPath,
            path,
            method: 'GET',
            timeout: 30000,
          }
        : {
            hostname: new URL(this.baseURL).hostname,
            port: new URL(this.baseURL).port,
            path,
            method: 'GET',
            timeout: 30000,
          }

      const req = http.get(opts, (res) => {
        this.isConnecting = false
        this.currentStream = res
        this.reconnectAttempts = 0

        if (res.statusCode !== 200) {
          this.emit('error', new Error(`SSE stream failed: HTTP ${res.statusCode}`))
          this.scheduleReconnect()
          return
        }

        this.emit('connected', { message: 'Connected to CassiCore daemon' })
        this.parseSSEStream(res)
      })

      req.on('error', (err) => {
        this.isConnecting = false
        this.emit('error', err)
        this.scheduleReconnect()
      })

      req.on('timeout', () => {
        this.isConnecting = false
        req.destroy()
        this.emit('error', new Error('Connection timeout'))
        this.scheduleReconnect()
      })

      req.on('close', () => {
        this.currentStream = null
        if (!this.isConnecting) {
          this.emit('disconnected', { message: 'Stream closed' })
          this.scheduleReconnect()
        }
      })
    }

    connect()
  }

  /**
   * Stop the current stream
   */
  stopStream(): void {
    if (this.currentStream) {
      this.currentStream.destroy()
      this.currentStream = null
    }
    this.isConnecting = false
  }

  /**
   * Parse SSE stream and emit events
   */
  private parseSSEStream(res: http.IncomingMessage): void {
    let eventType = ''
    let dataBuf = ''
    let remainder = ''

    res.setEncoding('utf-8')

    res.on('data', (chunk: string) => {
      remainder += chunk
      const lines = remainder.split('\n')
      remainder = lines.pop() ?? ''

      for (const line of lines) {
        if (line === '') {
          // Blank line → dispatch event
          if (dataBuf) {
            const type = eventType || 'message'
            try {
              const data = JSON.parse(dataBuf)
              const event: WatchEvent = { type: type as any, data }
              this.emit('event', event)
              this.emit(type, data)
            } catch {
              // Non-JSON data
              this.emit('event', { type, data: dataBuf })
            }
          }
          eventType = ''
          dataBuf = ''
        } else if (line.startsWith('event:')) {
          eventType = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          const payload = line.slice(5).replace(/^ /, '')
          if (dataBuf) dataBuf += '\n'
          dataBuf += payload
        }
      }
    })

    res.on('end', () => {
      // Flush any remaining event
      if (dataBuf) {
        const type = eventType || 'message'
        try {
          const data = JSON.parse(dataBuf)
          this.emit('event', { type, data })
          this.emit(type, data)
        } catch {
          this.emit('event', { type, data: dataBuf })
        }
      }
    })
  }

  /**
   * Schedule a reconnection attempt
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.emit('error', new Error('Max reconnection attempts reached'))
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelayMs * Math.pow(2, this.reconnectAttempts - 1)

    this.emit('reconnecting', {
      attempt: this.reconnectAttempts,
      delay,
    })

    setTimeout(() => {
      if (!this.currentStream && !this.isConnecting) {
        this.startStream().catch(() => {})
      }
    }, delay)
  }
}

/**
 * @dep callers: tryHttp (cassi-watch/src/client/watch-client.ts), trySocket (cassi-watch/src/client/watch-client.ts)
 * @dep calls: on
 * @dep module: Client
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function readJSON<T>(
  res: http.IncomingMessage,
  resolve: (value: T) => void,
  reject: (reason: Error) => void,
): void {
  const chunks: Buffer[] = []
  res.on('data', (chunk) => chunks.push(chunk as Buffer))
  res.on('end', () => {
    try {
      const json = JSON.parse(Buffer.concat(chunks).toString('utf-8'))
      resolve(json)
    } catch (err) {
      reject(err as Error)
    }
  })
  res.on('error', reject)
}
