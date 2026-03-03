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

// ── Module-level state ─────────────────────────────────────────────────────────

let TOKEN = ''

/** Optional structured warning/error emitter — set via setLogger(). */
let WARN: (msg: string) => void = (msg) => process.stderr.write(`${msg}\n`)

/** Set the active Bot API token. */
export function setToken(token: string) {
  TOKEN = token || ''
}

/**
 * Provide a structured logger callback so warnings from this module are
 * forwarded through parentPort rather than written to raw stderr.
 */
export function setLogger(warnFn: (msg: string) => void) {
  WARN = warnFn
}

// ── Internal helpers ───────────────────────────────────────────────────────────

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
      WARN(`[telegram-common] tg/${method} not ok: ${json.description ?? '?'} `)
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

// ── Public API: formatting ─────────────────────────────────────────────────────

/**
 * Sanitize text for Telegram display.
 *
 * Converts GitHub-flavored Markdown to Telegram HTML using the markdown-it
 * based pipeline (ported from OpenClaw).
 *
 * @deprecated Prefer calling markdownToTelegramHtml() directly.
 */
export function sanitizeMarkdown(text: string): string {
  return markdownToTelegramHtml(text)
}

// ── Public API: messaging ──────────────────────────────────────────────────────

/**
 * Send a new message to a chat.
 *
 * Converts markdown to Telegram HTML by default. Falls back to plain text
 * if the API rejects the formatted send.
 */
export async function sendMessage(
  chatId: number,
  text: string,
  _parseMode?: 'MarkdownV2' | 'HTML',
): Promise<number | null> {
  // Convert markdown to HTML using the markdown-it pipeline
  const htmlText = markdownToTelegramHtml(text || '\u2026')
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
 */
export async function editMessage(
  chatId: number,
  messageId: number,
  text: string,
  _parseMode?: 'MarkdownV2' | 'HTML',
): Promise<boolean> {
  const htmlText = markdownToTelegramHtml(text || '\u2026')
  const result = await tgCall('editMessageText', {
    chat_id: chatId,
    message_id: messageId,
    text: htmlText,
    parse_mode: 'HTML',
  })
  if (result !== null) return true

  // HTML edit failed — retry as plain text
  WARN(`[telegram-common] editMessage HTML failed for chat ${chatId} msg ${messageId}, retrying as plain text`)

  const plainResult = await tgCall('editMessageText', {
    chat_id: chatId,
    message_id: messageId,
    text: text || '\u2026',
  })
  return plainResult !== null
}

/**
 * Send a "typing..." indicator.
 */
export async function sendTyping(chatId: number): Promise<void> {
  await tgCall('sendChatAction', { chat_id: chatId, action: 'typing' })
}

// ── Photo handling ─────────────────────────────────────────────────────────────

/**
 * Download a photo from Telegram by file_id and return it as a base64 ImageAttachment.
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
