/**
 * ModuleChatHandler — Routes Telegram topic messages to persistent module sessions.
 *
 * When a user types in a module's Telegram topic (e.g., the "Thinker" topic),
 * this handler:
 *  1. Resolves the topic → module key → persistent session
 *  2. Prepends a module context preamble (what module does, recent activity)
 *  3. Sends the turn via SSE streaming to the admin API
 *  4. Streams the response back to Telegram in the same topic thread
 *
 * This enables interactive debugging: "why did you generate that last insight?"
 * gets answered in context, with the module's full history available.
 */

import type { TelegramClient, TelegramMessage } from './telegram-client.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { ModuleSessionRegistry, ModuleRegistration } from '../module-session-registry.js'
import type { TopicManager } from './topic-manager.js'

interface StreamState {
  chatId: number
  threadId: number
  msgId: number | null
  buffer: string
  lastFlushed: string
  timer: ReturnType<typeof setInterval> | null
  flushChain: Promise<void>
}

export interface ModuleChatConfig {
  /** Admin API base URL (default: http://127.0.0.1:7433) */
  adminApiUrl: string
  /** Max recent turns to include in module context (default: 5) */
  recentTurnsInContext: number
  /** Stream edit interval in ms (default: 1000) */
  editIntervalMs: number
}

const DEFAULT_CONFIG: ModuleChatConfig = {
  adminApiUrl: 'http://127.0.0.1:7433',
  recentTurnsInContext: 5,
  editIntervalMs: 1000,
}

export class ModuleChatHandler {
  private readonly client: TelegramClient
  private readonly chatId: number
  private readonly logger: ILogger
  private readonly config: ModuleChatConfig
  private registry: ModuleSessionRegistry | undefined
  private topicManager: TopicManager | undefined

  /** Active streams: `${userId}:${threadId}` → StreamState */
  private readonly streams = new Map<string, StreamState>()
  /** Active SSE abort controllers */
  private readonly activeAborts = new Map<string, AbortController>()

  constructor(
    client: TelegramClient,
    chatId: number,
    logger: ILogger,
    config?: Partial<ModuleChatConfig>,
  ) {
    this.client = client
    this.chatId = chatId
    this.logger = logger.child?.('module-chat') ?? logger
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  setRegistry(registry: ModuleSessionRegistry): void {
    this.registry = registry
  }

  setTopicManager(topicManager: TopicManager): void {
    this.topicManager = topicManager
  }

  /**
   * Returns true if the given thread ID maps to a known module topic.
   * The cognitive feed poll loop calls this to decide routing.
   */
  isModuleTopic(threadId: number | undefined): boolean {
    if (!threadId || !this.topicManager || !this.registry) return false
    const topicKey = this.topicManager.getTopicKeyByThreadId(threadId)
    if (!topicKey) return false
    return this.registry.getModulesForTopic(topicKey).length > 0
  }

  /**
   * Handle a plain-text message in a module topic.
   * Resolves the topic → module → persistent session, streams a response.
   */
  async handleMessage(message: TelegramMessage): Promise<void> {
    const text = message.text?.trim()
    if (!text || !message.from) return
    if (!message.message_thread_id) return

    // Skip slash commands — those go to SteeringHandler
    if (text.startsWith('/')) return

    const threadId = message.message_thread_id
    const userId = message.from.id
    const streamKey = `${userId}:${threadId}`

    // Resolve topic → module
    const reg = this.resolveModule(threadId, text)
    if (!reg) {
      this.logger.debug('[module-chat] No module found for topic', { threadId })
      return
    }

    // Abort any existing stream for this user+topic
    this.abortStream(streamKey)

    // Show typing
    await this.client.sendTyping(this.chatId, threadId)
    try {
      // Build context preamble
      const preamble = await this.buildModuleContext(reg)
      const enriched = preamble ? [
        `<module-context>`,
        `You are interacting with the ${reg.displayName} module's debug session.`,
        preamble,
        `</module-context>`,
        '',
        text,
      ].join('\n') : text

      await this.streamTurn(reg.sessionId, streamKey, threadId, userId, enriched)
    } catch (err) {
      this.logger.error('[module-chat] Turn failed', { module: reg.moduleKey, error: String(err) })
      await this.client.sendMessage(
        this.chatId,
        `<i>Error: ${this.escHtml(String(err).slice(0, 200))}</i>`,
        { threadId },
      )
    }
  }

  /**
   * Resolve which module to chat with based on the thread ID and optional @name prefix.
   * If the topic has multiple modules (e.g. memoryDreams has dreamer + archiver + search),
   * the user can prefix with @moduleName to target a specific one, otherwise
   * the most recently active module is chosen.
   */
  private resolveModule(threadId: number, text: string): ModuleRegistration | undefined {
    if (!this.topicManager || !this.registry) return undefined

    const topicKey = this.topicManager.getTopicKeyByThreadId(threadId)
    if (!topicKey) return undefined

    const moduleKeys = this.registry.getModulesForTopic(topicKey)
    if (moduleKeys.length === 0) return undefined

    // Check for @moduleName prefix
    const atMatch = text.match(/^@([\w.-]+)\s/)
    if (atMatch) {
      const targetKey = atMatch[1].toLowerCase()
      const found = moduleKeys.find(k => k.toLowerCase() === targetKey || k.split('.').pop() === targetKey)
      if (found) return this.registry.getRegistration(found)
    }

    // Single module — direct
    if (moduleKeys.length === 1) return this.registry.getRegistration(moduleKeys[0])

    // Multiple — pick most recently active
    const bestKey = this.registry.getMostRecentModuleForTopic(topicKey)
    return bestKey ? this.registry.getRegistration(bestKey) : this.registry.getRegistration(moduleKeys[0])
  }

  /**
   * Build a context preamble that describes what the module does
   * and shows its recent session turns as debug context.
   */
  private async buildModuleContext(reg: ModuleRegistration): Promise<string> {
    const parts: string[] = []

    parts.push(`Module: ${reg.displayName} (session: ${reg.sessionId})`)

    // Fetch recent session history from admin API
    try {
      const res = await fetch(`${this.config.adminApiUrl}/sessions/${reg.sessionId}`)
      if (res.ok) {
        const session = await res.json() as { history?: Array<{ role: string; content: string }> }
        const history = session.history ?? []
        const recentTurns = history
          .filter(m => m.role !== 'system')
          .slice(-this.config.recentTurnsInContext)

        if (recentTurns.length > 0) {
          parts.push(`\nRecent module activity (last ${recentTurns.length} turns):`)
          for (const turn of recentTurns) {
            const content = typeof turn.content === 'string'
              ? turn.content
              : JSON.stringify(turn.content)
            parts.push(`[${turn.role}] ${content.slice(0, 300)}${content.length > 300 ? '…' : ''}`)
          }
        }
      }
    } catch { /* best-effort */ }

    return parts.join('\n')
  }


  private async streamTurn(
    sessionId: string,
    streamKey: string,
    threadId: number,
    userId: number,
    content: string,
  ): Promise<void> {
    const ac = new AbortController()
    this.activeAborts.set(streamKey, ac)

    const turnBody: Record<string, unknown> = {
      content,
      channelId: 'channel:module',
      senderId: `tg:module:${userId}`,
    }

    const url = `${this.config.adminApiUrl}/sessions/${sessionId}/turn/stream`

    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(turnBody),
      signal: ac.signal,
    })

    if (!res.ok) {
      const body = await res.text()
      throw new Error(`Turn API error: ${res.status} ${body}`)
    }

    const stream = this.getOrCreateStream(streamKey, threadId)
    await this.processSSEStream(res, stream, streamKey)
  }


  private processSSEStream(
    res: Response,
    stream: StreamState,
    streamKey: string,
  ): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const reader = res.body?.getReader()
      if (!reader) { reject(new Error('No response body')); return }

      const decoder = new TextDecoder()
      let eventBuffer = ''

      this.startStreamTimer(stream, streamKey)

      const pump = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            eventBuffer += decoder.decode(value, { stream: true })
            const events = eventBuffer.split('\n\n')
            eventBuffer = events.pop() ?? ''

            for (const eventBlock of events) {
              const dataLine = eventBlock.split('\n').find(l => l.startsWith('data: '))
              if (!dataLine) continue

              const json = dataLine.slice(6).trim()
              if (json === '[DONE]') continue

              try {
                const ev = JSON.parse(json) as { type?: string; text?: string; delta?: string; error?: string }
                if (ev.type === 'token' || ev.type === 'delta') {
                  stream.buffer += (ev.text ?? ev.delta ?? '')
                } else if (ev.type === 'done' || ev.type === 'end') {
                  await this.flushStream(stream, streamKey, true)
                  break
                } else if (ev.type === 'error') {
                  throw new Error(ev.error ?? 'Unknown error from turn API')
                }
              } catch { /* malformed JSON — skip */ }
            }
          }

          await this.flushStream(stream, streamKey, true)
          resolve()
        } catch (err) {
          reject(err)
        } finally {
          this.stopStreamTimer(stream)
          reader.cancel().catch(() => {})
        }
      }

      void pump()
    })
  }


  private getOrCreateStream(streamKey: string, threadId: number): StreamState {
    let s = this.streams.get(streamKey)
    if (!s) {
      s = { chatId: this.chatId, threadId, msgId: null, buffer: '', lastFlushed: '', timer: null, flushChain: Promise.resolve() }
      this.streams.set(streamKey, s)
    }
    return s
  }

  private startStreamTimer(stream: StreamState, streamKey: string): void {
    this.stopStreamTimer(stream)
    stream.timer = setInterval(() => {
      void this.flushStream(stream, streamKey, false)
    }, this.config.editIntervalMs)
  }

  private stopStreamTimer(stream: StreamState): void {
    if (stream.timer) {
      clearInterval(stream.timer)
      stream.timer = null
    }
  }

  private async flushStream(stream: StreamState, streamKey: string, final: boolean): Promise<void> {
    const text = stream.buffer.trim()
    if (!text || text === stream.lastFlushed) {
      if (final) {
        this.cleanupStream(streamKey)
      }
      return
    }

    stream.flushChain = stream.flushChain.then(async () => {
      try {
        const html = this.escHtml(text)

        if (stream.msgId === null) {
          const msgId = await this.client.sendMessage(this.chatId, html, { threadId: stream.threadId })
          stream.msgId = msgId ?? null
        } else {
          await this.client.editMessage(this.chatId, stream.msgId, html)
        }

        stream.lastFlushed = text

        if (final) {
          this.stopStreamTimer(stream)
          this.cleanupStream(streamKey)
        }
      } catch (err) {
        this.logger.debug('[module-chat] Flush error', { streamKey, error: String(err) })
      }
    })

    await stream.flushChain
  }

  private cleanupStream(streamKey: string): void {
    const stream = this.streams.get(streamKey)
    if (stream) {
      this.stopStreamTimer(stream)
    }
    this.streams.delete(streamKey)
    this.activeAborts.delete(streamKey)
  }

  private abortStream(streamKey: string): void {
    const ac = this.activeAborts.get(streamKey)
    if (ac) {
      ac.abort()
      this.activeAborts.delete(streamKey)
    }
    const stream = this.streams.get(streamKey)
    if (stream) {
      this.stopStreamTimer(stream)
    }
  }

  private escHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  }
}
