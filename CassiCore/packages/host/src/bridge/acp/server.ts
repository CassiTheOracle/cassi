
import {
  AgentSideConnection,
  PROTOCOL_VERSION,
  type Agent,
  type CancelNotification,
  type InitializeRequest,
  type InitializeResponse,
  type NewSessionRequest,
  type NewSessionResponse,
  type PromptRequest,
  type PromptResponse,
} from '@zed-industries/agent-client-protocol'

import { CassiDaemonClient } from './client.js'
import { chatEventToSessionUpdate, extractPromptText } from './translator.js'

import type { StopReason } from './types.js'

export interface CassiAgentOptions {
  baseUrl?: string
  adminToken?: string
  log?: (msg: string) => void
}

export class CassiAgent implements Agent {
  private readonly conn: AgentSideConnection
  private readonly client: CassiDaemonClient
  private readonly log: (msg: string) => void
  private readonly active = new Map<string, AbortController>()

  constructor(conn: AgentSideConnection, options: CassiAgentOptions = {}) {
    this.conn = conn
    this.client = new CassiDaemonClient({
      baseUrl: options.baseUrl,
      adminToken: options.adminToken,
    })
    this.log = options.log ?? (() => {})
  }

  async authenticate(): Promise<void> {}

  async initialize(params: InitializeRequest): Promise<InitializeResponse> {
    this.log(`initialize: protocolVersion=${params.protocolVersion}`)
    return {
      protocolVersion: PROTOCOL_VERSION,
      agentCapabilities: {
        loadSession: false,
        promptCapabilities: { image: false, audio: false, embeddedContext: false },
      },
      authMethods: [],
    }
  }

  async newSession(_params: NewSessionRequest): Promise<NewSessionResponse> {
    const sessionId = await this.client.createSession()
    this.log(`newSession: ${sessionId}`)
    return { sessionId }
  }

  async prompt(params: PromptRequest): Promise<PromptResponse> {
    const { sessionId } = params
    const text = extractPromptText(params.prompt as ReadonlyArray<{ type: string; text?: string }>)
    this.log(`prompt: session=${sessionId} len=${text.length}`)

    const controller = new AbortController()
    this.active.set(sessionId, controller)

    let stopReason: StopReason = 'end_turn'
    let streamFailed: string | null = null

    try {
      for await (const event of this.client.executeTurnStream(sessionId, text, controller.signal)) {
        if (event.type === 'error') {
          streamFailed = event.error
          stopReason = event.error === 'cancelled' ? 'cancelled' : 'end_turn'
          break
        }
        const update = chatEventToSessionUpdate(event, sessionId)
        if (update) await this.conn.sessionUpdate(update)
        if (event.type === 'response') break
      }
    } catch (err) {
      if (controller.signal.aborted) {
        stopReason = 'cancelled'
      } else {
        streamFailed = String(err)
      }
    } finally {
      this.active.delete(sessionId)
    }

    if (streamFailed && streamFailed !== 'cancelled') {
      throw new Error(streamFailed)
    }
    return { stopReason }
  }

  async cancel(params: CancelNotification): Promise<void> {
    const ctrl = this.active.get(params.sessionId)
    if (ctrl) {
      this.log(`cancel: session=${params.sessionId}`)
      ctrl.abort()
    }
  }
}
