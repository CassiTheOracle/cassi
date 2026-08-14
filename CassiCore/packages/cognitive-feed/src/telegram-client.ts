/**
 * Standalone Telegram Bot API client for the Cognitive Feed.
 *
 * Instance-based (not module-level state like telegram-common.ts) so it can
 * coexist with the main Telegram channel which uses a different bot token.
 *
 * Supports Forum Topics (supergroup threads) for per-module message routing.
 */

import type { ILogger } from '../../../types/interfaces.js'

// Errors

/**
 * Thrown when Telegram returns 429 Too Many Requests.
 * Carries the retry-after duration so callers can back off correctly.
 */
export class TelegramRateLimitError extends Error {
  readonly retryAfterSecs: number

  constructor(retryAfterSecs: number) {
    super(`Too Many Requests: retry after ${retryAfterSecs}`)
    this.name = 'TelegramRateLimitError'
    this.retryAfterSecs = retryAfterSecs
  }
}

// Types

export interface TelegramClientConfig {
  token: string
  /** Request timeout in ms (default: 15000) */
  timeoutMs?: number
}

export interface ForumTopic {
  message_thread_id: number
  name: string
  icon_color?: number
}

export interface BotCommand {
  command: string
  description: string
}

export interface TelegramUpdate {
  update_id: number
  message?: TelegramMessage
}

export interface TelegramMessage {
  message_id: number
  message_thread_id?: number
  chat: { id: number; type: string }
  from?: { id: number; username?: string; first_name?: string }
  text?: string
  reply_to_message?: TelegramMessage
  date: number
}

interface ApiResponse<T> {
  ok: boolean
  result: T
  description?: string
}

// Client

export class TelegramClient {
  private readonly token: string
  private readonly timeoutMs: number
  private readonly logger: ILogger

  constructor(config: TelegramClientConfig, logger: ILogger) {
    this.token = config.token
    this.timeoutMs = config.timeoutMs ?? 15_000
    this.logger = logger
  }


  private async call<T>(method: string, body?: Record<string, unknown>): Promise<T | null> {
    const ac = new AbortController()
    const timer = setTimeout(() => ac.abort(), this.timeoutMs)
    try {
      const res = await fetch(`https://api.telegram.org/bot${this.token}/${method}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
        signal: ac.signal,
      })
      clearTimeout(timer)
      const json = (await res.json()) as ApiResponse<T>
      if (!json.ok) {
        const desc = json.description ?? '?'

        // Detect Telegram 429 rate-limit and throw a typed error so
        // callers (rate-limiter) can apply proper backoff.
        if (res.status === 429 || desc.includes('Too Many Requests')) {
          const match = desc.match(/retry after (\d+)/)
          const retryAfterSecs = match ? parseInt(match[1], 10) : 30
          throw new TelegramRateLimitError(retryAfterSecs)
        }

        if (!desc.includes('not modified')) {
          this.logger.warn(`[cognitive-feed-tg] ${method} failed: ${desc}`)
        }
        return null
      }
      return json.result
    } catch (err) {
      clearTimeout(timer)
      // Let rate-limit errors propagate — callers (RateLimiter) need them for backoff
      if (err instanceof TelegramRateLimitError) throw err
      if (err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError')) {
        return null
      }
      this.logger.warn(`[cognitive-feed-tg] ${method} error: ${String(err)}`)
      return null
    }
  }


  /**
   * Send a message to a chat, optionally in a specific forum topic thread.
   * Uses HTML parse mode. Returns the message_id on success.
   */
  async sendMessage(
    chatId: number,
    text: string,
    options?: {
      threadId?: number
      parseMode?: 'HTML' | 'MarkdownV2' | 'none'
      disableNotification?: boolean
    },
  ): Promise<number | null> {
    const body: Record<string, unknown> = {
      chat_id: chatId,
      text: text || '\u2026',
    }
    if (options?.parseMode && options.parseMode !== 'none') {
      body.parse_mode = options.parseMode
    } else if (!options?.parseMode) {
      body.parse_mode = 'HTML' // Default to HTML for backward compat
    }
    if (options?.threadId) body.message_thread_id = options.threadId
    if (options?.disableNotification) body.disable_notification = true

    const result = await this.call<{ message_id: number }>('sendMessage', body)
    if (result !== null) return result.message_id

    // If HTML parse mode failed, retry as plain text
    if (body.parse_mode) {
      this.logger.debug('[cognitive-feed-tg] Formatted send failed, retrying plain text')
      delete body.parse_mode
      const plainResult = await this.call<{ message_id: number }>('sendMessage', body)
      return plainResult?.message_id ?? null
    }
    return null
  }

  /**
   * Edit an existing message's text. Returns true on success or no-change.
   */
  async editMessage(
    chatId: number,
    messageId: number,
    text: string,
    parseMode?: 'HTML' | 'MarkdownV2' | 'none',
  ): Promise<boolean> {
    const body: Record<string, unknown> = {
      chat_id: chatId,
      message_id: messageId,
      text: text || '\u2026',
    }
    if (parseMode && parseMode !== 'none') {
      body.parse_mode = parseMode
    } else if (!parseMode) {
      body.parse_mode = 'HTML' // Default
    }

    const result = await this.call<unknown>('editMessageText', body)
    if (result !== null) return true

    // Formatted failed -- retry without parse mode
    if (body.parse_mode) {
      delete body.parse_mode
      const plainResult = await this.call<unknown>('editMessageText', body)
      return plainResult !== null
    }
    return false
  }

  async pinMessage(chatId: number, messageId: number): Promise<boolean> {
    try {
      await this.call('pinChatMessage', { chat_id: chatId, message_id: messageId })
      return true
    } catch {
      return false
    }
  }

  async deleteMessage(chatId: number, messageId: number): Promise<boolean> {
    try {
      await this.call('deleteMessage', { chat_id: chatId, message_id: messageId })
      return true
    } catch {
      return false
    }
  }


  /**
   * Create a forum topic in a supergroup.
   * Returns the created topic with its message_thread_id.
   *
   * Valid icon_color values:
   *  7322096 (blue), 16766590 (yellow), 13338331 (violet),
   *  9367192 (green), 16749490 (rose), 16478047 (red)
   */
  async createForumTopic(
    chatId: number,
    name: string,
    iconColor?: number,
  ): Promise<ForumTopic | null> {
    const body: Record<string, unknown> = {
      chat_id: chatId,
      name,
    }
    if (iconColor !== undefined) body.icon_color = iconColor
    return this.call<ForumTopic>('createForumTopic', body)
  }

  /**
   * Get existing forum topics in a supergroup.
   */
  async getForumTopicsByName(chatId: number): Promise<Map<string, ForumTopic> | null> {
    // Telegram doesn't have a direct "list forum topics" API,
    // but we can use getForumTopicIconStickers as a connectivity check.
    // Topic IDs are tracked by TopicManager instead.
    return null
  }

  /**
   * Close a forum topic.
   */
  async closeForumTopic(chatId: number, threadId: number): Promise<boolean> {
    const result = await this.call('closeForumTopic', {
      chat_id: chatId,
      message_thread_id: threadId,
    })
    return result !== null
  }

  /**
   * Reopen a forum topic.
   */
  async reopenForumTopic(chatId: number, threadId: number): Promise<boolean> {
    const result = await this.call('reopenForumTopic', {
      chat_id: chatId,
      message_thread_id: threadId,
    })
    return result !== null
  }


  /**
   * Long-poll for updates. Used for receiving steering replies.
   */
  async getUpdates(
    offset: number,
    timeoutSec: number = 25,
  ): Promise<TelegramUpdate[] | null> {
    const ac = new AbortController()
    const timer = setTimeout(() => ac.abort(), (timeoutSec + 10) * 1000)
    try {
      const res = await fetch(`https://api.telegram.org/bot${this.token}/getUpdates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          offset,
          timeout: timeoutSec,
          allowed_updates: ['message'],
        }),
        signal: ac.signal,
      })
      clearTimeout(timer)
      const json = (await res.json()) as ApiResponse<TelegramUpdate[]>
      if (!json.ok) {
        const desc = json.description ?? '?'
        // Conflict is expected when the telegram channel worker is also polling
        if (desc.includes('Conflict')) {
          this.logger.debug(`[cognitive-feed-tg] getUpdates conflict — backing off`)
        } else {
          this.logger.warn(`[cognitive-feed-tg] getUpdates failed: ${desc}`)
        }
        return null
      }
      return json.result
    } catch (err) {
      clearTimeout(timer)
      if (err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError')) {
        return null
      }
      this.logger.warn(`[cognitive-feed-tg] getUpdates error: ${String(err)}`)
      return null
    }
  }


  /**
   * Send a typing indicator.
   */
  async sendTyping(chatId: number, threadId?: number): Promise<void> {
    const body: Record<string, unknown> = {
      chat_id: chatId,
      action: 'typing',
    }
    if (threadId) body.message_thread_id = threadId
    await this.call('sendChatAction', body)
  }

  async setMyCommands(commands: BotCommand[]): Promise<boolean> {
    const result = await this.call('setMyCommands', { commands })
    return result !== null
  }

  /**
   * Validate the bot token by calling getMe.
   */
  async validateToken(): Promise<{ id: number; first_name: string; username?: string } | null> {
    return this.call<{ id: number; first_name: string; username?: string }>('getMe')
  }
}
