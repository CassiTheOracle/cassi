/**
 * GeneralChatHandler — Bridges the Telegram supergroup's General chat
 * to a full CassiCore session via the admin API.
 *
 * When a user types in the General chat (no thread_id), this handler:
 *  1. Creates/retrieves a per-user CassiCore session
 *  2. Builds a cognitive context preamble from recent cross-topic activity
 *  3. Sends the turn via SSE streaming to the admin API
 *  4. Streams the response back to Telegram using buffer+edit pattern
 *
 * The cognitive context ensures the session "sees" the same cross-topic
 * message timeline the user sees when scrolling the General chat in Telegram.
 */

import type { TelegramClient, TelegramMessage } from './telegram-client.js'
import type { ILogger } from '../../../types/interfaces.js'

// Types

interface CognitiveContextEntry {
  /** Formatted text (same as what was sent to Telegram) */
  text: string
  /** Topic it was posted to (null = main chat highlight) */
  topicKey: string | null
  /** Topic display name */
  topicName: string
  /** Timestamp */
  timestamp: number
}

interface StreamState {
  chatId: number
  msgId: number | null
  buffer: string
  lastFlushed: string
  timer: ReturnType<typeof setInterval> | null
  flushChain: Promise<void>
}

export interface GeneralChatConfig {
  /** Admin API base URL (default: http://127.0.0.1:7433) */
  adminApiUrl: string
  /** Max cognitive context entries to keep (default: 200) */
  maxContextEntries: number
  /** Max cognitive context chars to inject per turn (default: 8000) */
  maxContextChars: number
  /** Stream edit interval in ms (default: 1000) */
  editIntervalMs: number
}

const DEFAULT_CONFIG: GeneralChatConfig = {
  adminApiUrl: 'http://127.0.0.1:7433',
  maxContextEntries: 200,
  maxContextChars: 8000,
  editIntervalMs: 1000,
}

// GeneralChatHandler

export class GeneralChatHandler {
  private readonly client: TelegramClient
  private readonly chatId: number
  private readonly logger: ILogger
  private readonly config: GeneralChatConfig

  /** Ring buffer of recent cognitive events across all topics */
  private readonly cognitiveContext: CognitiveContextEntry[] = []

  /** Active streams: telegramUserId → StreamState */
  private readonly streams = new Map<number, StreamState>()

  /** Track active SSE abort controllers for cleanup */
  private readonly activeAborts = new Map<number, AbortController>()

  constructor(
    client: TelegramClient,
    chatId: number,
    logger: ILogger,
    config?: Partial<GeneralChatConfig>,
  ) {
    this.client = client
    this.chatId = chatId
    this.logger = logger
    this.config = { ...DEFAULT_CONFIG, ...config }
  }


  /**
   * Record a cognitive event for context injection.
   * Called by the main module whenever a message is sent to any topic.
   */
  recordEvent(text: string, topicKey: string | null, topicName: string): void {
    this.cognitiveContext.push({
      text: this.stripHtml(text),
      topicKey,
      topicName,
      timestamp: Date.now(),
    })

    // Evict oldest entries beyond limit
    while (this.cognitiveContext.length > this.config.maxContextEntries) {
      this.cognitiveContext.shift()
    }
  }

  /**
   * Build a cognitive context summary for injection into the session.
   * Returns the most recent events formatted as a readable timeline.
   */
  private buildCognitiveContext(): string {
    if (this.cognitiveContext.length === 0) return ''

    const parts: string[] = [
      '=== Recent Cognitive Activity (what the user can see in the Telegram group) ===',
    ]

    let charCount = parts[0].length
    const maxChars = this.config.maxContextChars

    // Walk backwards from most recent, collecting entries until we hit the char limit
    const entries: string[] = []
    for (let i = this.cognitiveContext.length - 1; i >= 0; i--) {
      const entry = this.cognitiveContext[i]
      const time = new Date(entry.timestamp).toLocaleTimeString('en-GB', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      })
      const topic = entry.topicKey ? `[${entry.topicName}]` : '[Highlights]'
      const line = `${time} ${topic} ${entry.text}`

      if (charCount + line.length + 1 > maxChars) break
      entries.unshift(line)
      charCount += line.length + 1
    }

    parts.push(...entries)
    parts.push('=== End Cognitive Activity ===')

    return parts.join('\n')
  }


  /**
   * Handle a message in the General chat.
   * Creates a session and streams the response back.
   */
  async handleMessage(message: TelegramMessage): Promise<void> {
    const text = message.text?.trim()
    if (!text || !message.from) return

    const userId = message.from.id
    const username = message.from.username ?? message.from.first_name ?? String(userId)

    // Skip slash commands — those go to SteeringHandler
    if (text.startsWith('/')) return

    // Abort any existing stream for this user (new message supersedes)
    this.abortStream(userId)

    // Show typing
    await this.client.sendTyping(this.chatId)

    const sessionId = `cf:${userId}`
    const cognitiveContext = this.buildCognitiveContext()

    try {
      // Ensure session exists
      await this.ensureSession(sessionId, username)

      // Send turn with SSE streaming
      await this.streamTurn(sessionId, userId, text, cognitiveContext)
    } catch (err) {
      this.logger.error('[general-chat] Turn failed', { userId, error: String(err) })
      await this.client.sendMessage(
        this.chatId,
        `<i>Error processing message: ${this.escHtml(String(err).slice(0, 200))}</i>`,
      )
    }
  }


  private async ensureSession(sessionId: string, username: string): Promise<void> {
    // Check if session exists
    const checkRes = await fetch(`${this.config.adminApiUrl}/sessions/${sessionId}`)
    if (checkRes.ok) return // Session exists

    // Create session
    const createRes = await fetch(`${this.config.adminApiUrl}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId,
        name: `Cognitive Feed: ${username}`,
        channelId: 'channel:cognitive-feed',
        senderId: `tg:${username}`,
        permanent: true,
      }),
    })

    if (!createRes.ok) {
      const body = await createRes.text()
      throw new Error(`Failed to create session: ${createRes.status} ${body}`)
    }

    this.logger.info('[general-chat] Created session', { sessionId, username })
  }


  private async streamTurn(
    sessionId: string,
    userId: number,
    content: string,
    cognitiveContext: string,
  ): Promise<void> {
    const ac = new AbortController()
    this.activeAborts.set(userId, ac)

    // Prepend cognitive context to the user's message so the session sees
    // the same cross-topic timeline the user sees in the Telegram group.
    // The full CassiCore system prompt (identity, personality, memory,
    // intelligence module injections) is applied normally by the turn pipeline.
    let enrichedContent = content
    if (cognitiveContext) {
      enrichedContent = [
        '<cognitive-feed-context>',
        'The following is the recent activity visible in your Telegram cognitive feed group.',
        'The user can see all of this. They may reference events, insights, or module outputs.',
        '',
        cognitiveContext,
        '</cognitive-feed-context>',
        '',
        content,
      ].join('\n')
    }

    const turnBody: Record<string, unknown> = {
      content: enrichedContent,
      channelId: 'channel:cognitive-feed',
      senderId: `cf:${userId}`,
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

    // Process SSE stream
    const stream = this.getOrCreateStream(userId)
    await this.processSSEStream(res, stream, userId)
  }

  private async processSSEStream(
    res: Response,
    stream: StreamState,
    userId: number,
  ): Promise<void> {
    const reader = res.body?.getReader()
    if (!reader) {
      throw new Error('No response body')
    }

    const decoder = new TextDecoder()
    let eventBuffer = ''

    // Start the edit timer for periodic flushes
    this.startStreamTimer(stream, userId)

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        eventBuffer += decoder.decode(value, { stream: true })

        // Parse SSE events from the buffer
        const lines = eventBuffer.split('\n')
        eventBuffer = lines.pop() ?? '' // Keep incomplete line

        let currentEventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6)
            try {
              const parsed = JSON.parse(data)
              this.handleSSEEvent(currentEventType, parsed, stream, userId)
            } catch {
              // Ignore malformed JSON
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        this.logger.warn('[general-chat] SSE stream error', { userId, error: String(err) })
      }
    } finally {
      reader.releaseLock()
      await this.finalizeStream(userId)
      this.activeAborts.delete(userId)
    }
  }

  private handleSSEEvent(
    type: string,
    data: Record<string, unknown>,
    stream: StreamState,
    userId: number,
  ): void {
    switch (type) {
      case 'token': {
        const token = data.token as string
        if (token) {
          stream.buffer += token
        }
        break
      }

      case 'thinking': {
        // Show thinking indicator but don't buffer the thinking content
        // (it would be too noisy in Telegram)
        break
      }

      case 'tool_call': {
        // Show typing indicator for tool execution
        this.client.sendTyping(this.chatId).catch(() => {})
        break
      }

      case 'tool_result': {
        // Could optionally show tool results, but skip for cleanliness
        break
      }

      case 'done': {
        // Final response — use the complete response if available
        // (sometimes the stream tokens are incomplete, the 'done' event has the full text)
        if (data.response && typeof data.response === 'string') {
          stream.buffer = data.response
        }
        break
      }

      case 'error': {
        const errorMsg = data.error as string ?? 'Unknown error'
        stream.buffer += `\n\n_Error: ${errorMsg}_`
        break
      }
    }
  }


  private getOrCreateStream(userId: number): StreamState {
    let stream = this.streams.get(userId)
    if (!stream) {
      stream = {
        chatId: this.chatId,
        msgId: null,
        buffer: '',
        lastFlushed: '',
        timer: null,
        flushChain: Promise.resolve(),
      }
      this.streams.set(userId, stream)
    }
    return stream
  }

  private startStreamTimer(stream: StreamState, userId: number): void {
    if (stream.timer) return

    let typingCounter = 0
    stream.timer = setInterval(() => {
      this.enqueueFlush(stream)
      typingCounter += this.config.editIntervalMs
      if (typingCounter >= 4000) {
        this.client.sendTyping(this.chatId).catch(() => {})
        typingCounter = 0
      }
    }, this.config.editIntervalMs)
  }

  private enqueueFlush(stream: StreamState): void {
    stream.flushChain = stream.flushChain
      .then(() => this.doFlush(stream))
      .catch(err => {
        this.logger.warn('[general-chat] Flush error', { error: String(err) })
      })
  }

  private async doFlush(stream: StreamState): Promise<void> {
    if (!stream.buffer) return
    if (stream.msgId !== null && stream.buffer === stream.lastFlushed) return

    // Truncate for Telegram's 4096 char limit
    const text = stream.buffer.length > 4000
      ? stream.buffer.slice(0, 3980) + '\n\n... [streaming]'
      : stream.buffer

    if (stream.msgId === null) {
      // First send — no parse mode (LLM output is plain text, not HTML)
      const msgId = await this.client.sendMessage(stream.chatId, text, { parseMode: 'none' })
      if (msgId) {
        stream.msgId = msgId
      }
    } else {
      // Edit existing message (no parse mode)
      await this.client.editMessage(stream.chatId, stream.msgId, text)
    }
    stream.lastFlushed = stream.buffer
  }

  private async finalizeStream(userId: number): Promise<void> {
    const stream = this.streams.get(userId)
    if (!stream) return

    if (stream.timer) {
      clearInterval(stream.timer)
      stream.timer = null
    }

    // Final flush
    this.enqueueFlush(stream)
    await stream.flushChain

    this.streams.delete(userId)
  }

  private abortStream(userId: number): void {
    const ac = this.activeAborts.get(userId)
    if (ac) {
      ac.abort()
      this.activeAborts.delete(userId)
    }

    const stream = this.streams.get(userId)
    if (stream?.timer) {
      clearInterval(stream.timer)
      stream.timer = null
    }
    this.streams.delete(userId)
  }


  /**
   * Stop all active streams. Called during shutdown.
   */
  stop(): void {
    for (const [userId] of this.activeAborts) {
      this.abortStream(userId)
    }
    this.streams.clear()
  }


  private stripHtml(text: string): string {
    return text
      .replace(/<b>/g, '').replace(/<\/b>/g, '')
      .replace(/<i>/g, '').replace(/<\/i>/g, '')
      .replace(/<code>/g, '').replace(/<\/code>/g, '')
      .replace(/<pre>/g, '').replace(/<\/pre>/g, '')
      .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
      .replace(/&amp;/g, '&')
  }

  private escHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  }
}
