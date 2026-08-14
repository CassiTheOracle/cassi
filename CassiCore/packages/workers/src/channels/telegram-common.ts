/**
 * Shared Telegram helpers for workers/channels/telegram.ts.
 *
 * Formatting is handled by the markdown pipeline (markdown/ir.ts → render.ts → format.ts)
 * ported from OpenClaw's battle-tested implementation.
 */

import { markdownToTelegramHtml } from './markdown/format.js'

export { markdownToTelegramHtml }

export interface ImageAttachment {
  data: string
  mediaType: 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp'
  label?: string
}

export interface BotCommand {
  command: string
  description: string
}


let TOKEN = ''

/** Optional structured warning/error emitter — set via setLogger(). */
let WARN: (msg: string) => void = (msg) => process.stderr.write(`${msg}\n`)

/** Set the active Bot API token. */
/**
 * @dep callers: telegram.ts (workers/channels/telegram.ts), telegram.test.ts (tests/telegram.test.ts)
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function setToken(token: string) {
  TOKEN = token || ''
}

/**
 * Provide a structured logger callback so warnings from this module are
 * forwarded through parentPort rather than written to raw stderr.
 * @dep callers: telegram.ts (workers/channels/telegram.ts), telegram.test.ts (tests/telegram.test.ts)
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function setLogger(warnFn: (msg: string) => void) {
  WARN = warnFn
}


/**
 * @dep callers: tgEditMessageText (workers/channels/telegram-common.ts), tgCall (workers/channels/telegram-common.ts)
 * @dep module: Channels
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function apiUrl(method: string): string {
  return `https://api.telegram.org/bot${TOKEN}/${method}`
}

/**
 * Generic Telegram Bot API caller with timeout and error handling.
 */
async function tgCall<T>(method: string, body?: Record<string, unknown>): Promise<T | null> {
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(), 15_000)
  try {
    const res = await fetch(apiUrl(method), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      signal: ac.signal,
    })
    clearTimeout(timer)
    const json = await res.json() as { ok: boolean; result: T; description?: string }
    if (!json.ok) {
      // "message is not modified" is a harmless no-op (edit with identical content) — don't warn
      const desc = json.description ?? '?'
      if (!desc.includes('not modified')) {
        WARN(`[telegram-common] tg/${method} not ok: ${desc} `)
      }
      return null
    }
    return json.result
  } catch (err) {
    clearTimeout(timer)
    // AbortError/TimeoutError are expected for long-poll cycles — suppress them
    if (err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError')) return null
    WARN(`[telegram-common] tg/${method} error: ${String(err)}`)
    return null
  }
}


/**
 * Call editMessageText with tri-state return: 'ok' | 'not_modified' | 'error'.
 * This lets callers skip the plain-text retry on harmless "not modified" results.
 */
async function tgEditMessageText(
  chatId: number,
  messageId: number,
  text: string,
  parseMode?: string,
): Promise<'ok' | 'not_modified' | 'error'> {
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(), 15_000)
  try {
    const body: Record<string, unknown> = {
      chat_id: chatId,
      message_id: messageId,
      text,
    }
    if (parseMode) body.parse_mode = parseMode

    const res = await fetch(apiUrl('editMessageText'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ac.signal,
    })
    clearTimeout(timer)
    const json = await res.json() as { ok: boolean; description?: string }
    if (json.ok) return 'ok'
    if (json.description?.includes('not modified')) return 'not_modified'
    WARN(`[telegram-common] tg/editMessageText not ok: ${json.description ?? '?'} `)
    return 'error'
  } catch (err) {
    clearTimeout(timer)
    if (err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError')) return 'error'
    WARN(`[telegram-common] tg/editMessageText error: ${String(err)}`)
    return 'error'
  }
}

/**
 * Send a new message to a chat.
 *
 * Converts markdown to Telegram HTML by default. Falls back to plain text
 * if the API rejects the formatted send.
 */
export async function sendMessage(
  chatId: number,
  text: string,
  parseMode?: 'MarkdownV2' | 'HTML',
): Promise<number | null> {
  const htmlText = parseMode === 'HTML'
    ? (text || '\u2026')
    : markdownToTelegramHtml(text || '\u2026')
  const result = await tgCall<{ message_id: number }>('sendMessage', {
    chat_id: chatId,
    text: htmlText,
    parse_mode: 'HTML',
  })
  if (result !== null) return result.message_id ?? null

  // HTML send failed — fall through to plain text
  WARN(`[telegram-common] sendMessage HTML failed for chat ${chatId}, retrying as plain text`)

  const plainResult = await tgCall<{ message_id: number }>('sendMessage', {
    chat_id: chatId,
    text: text || '\u2026',
  })
  return plainResult?.message_id ?? null
}

/**
 * Edit an existing message.
 *
 * Converts markdown to Telegram HTML. Falls back to plain text on failure.
 * Returns true if the edit succeeded or if the message was already identical (not modified).
 * @dep callers: telegram.test.ts (tests/telegram.test.ts), doFlush (core/intelligence/cognitive-feed/general-chat-handler.ts), sendMessage (core/intelligence/cognitive-feed/index.ts), doFlush (workers/channels/telegram.ts)
 * @dep calls: WARN, tgEditMessageText, markdownToTelegramHtml
 * @dep module: Channels
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */
export async function editMessage(
  chatId: number,
  messageId: number,
  text: string,
  parseMode?: 'MarkdownV2' | 'HTML',
): Promise<boolean> {
  const htmlText = parseMode === 'HTML'
    ? (text || '\u2026')
    : markdownToTelegramHtml(text || '\u2026')
  const result = await tgEditMessageText(chatId, messageId, htmlText, 'HTML')
  if (result === 'ok' || result === 'not_modified') return true

  // HTML edit failed — retry as plain text
  WARN(`[telegram-common] editMessage HTML failed for chat ${chatId} msg ${messageId}, retrying as plain text`)

  const plainResult = await tgEditMessageText(chatId, messageId, text || '\u2026')
  return plainResult === 'ok' || plainResult === 'not_modified'
}

/**
 * Send a "typing..." indicator.
 * @dep callers: telegram.test.ts (tests/telegram.test.ts), startStreamTimer (core/intelligence/cognitive-feed/general-chat-handler.ts), handleSSEEvent (core/intelligence/cognitive-feed/general-chat-handler.ts), handleMessage (core/intelligence/cognitive-feed/general-chat-handler.ts), handleDaemonMessage (workers/channels/telegram.ts) [+2]
 * @dep calls: tgCall
 * @dep module: Channels
 * @dep risk: HIGH | 7 callers, 0 flows, 1 module
 */
export async function sendTyping(chatId: number): Promise<void> {
  await tgCall('sendChatAction', { chat_id: chatId, action: 'typing' })
}

export async function setMyCommands(commands: BotCommand[]): Promise<void> {
  await tgCall('setMyCommands', { commands })
}


/**
 * Download a photo from Telegram by file_id and return it as a base64 ImageAttachment.
 * @dep callers: telegram.test.ts (tests/telegram.test.ts), handleIncoming (workers/channels/telegram.ts)
 * @dep calls: WARN
 * @dep module: Channels
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export async function downloadPhoto(fileId: string): Promise<ImageAttachment | null> {
  try {
    const fileInfo = await tgCall<{ file_path: string }>('getFile', { file_id: fileId })
    if (!fileInfo?.file_path) {
      WARN(`[telegram-common] downloadPhoto: no file_path for ${fileId}`)
      return null
    }

    const url = `https://api.telegram.org/file/bot${TOKEN}/${fileInfo.file_path}`
    const ac = new AbortController()
    const timer = setTimeout(() => ac.abort(), 30_000)
    const res = await fetch(url, { signal: ac.signal })
    clearTimeout(timer)

    if (!res.ok) {
      WARN(`[telegram-common] downloadPhoto: HTTP ${res.status} for ${fileId}`)
      return null
    }

    const buf = await res.arrayBuffer()
    const base64 = Buffer.from(buf).toString('base64')

    const ext = fileInfo.file_path.split('.').pop()?.toLowerCase() ?? ''
    const mediaType: ImageAttachment['mediaType'] =
      ext === 'png'  ? 'image/png'  :
      ext === 'gif'  ? 'image/gif'  :
      ext === 'webp' ? 'image/webp' :
      'image/jpeg'

    return { data: base64, mediaType, label: fileId }
  } catch (err) {
    WARN(`[telegram-common] downloadPhoto error for ${fileId}: ${String(err)}`)
    return null
  }
}
