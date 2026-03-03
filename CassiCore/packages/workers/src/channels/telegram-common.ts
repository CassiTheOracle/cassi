// Shared Telegram helpers for workers/channels/telegram.ts

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
 * Escape all MarkdownV2 special characters in a plain-text region.
 * Does NOT escape backticks (`` ` ``) here — those are handled by the
 * code-region pass in sanitizeMarkdown().
 */
function escapeMarkdownV2Chars(text: string): string {
  return text.replace(/([_*[\]()~`>#+\-=|{}.!\\])/g, '\\$1')
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// ── Public API helpers ─────────────────────────────────────────────────────────

export async function tgCall<T>(
  method: string,
  body?: Record<string, unknown>,
  timeoutMs = 15_000,
): Promise<T | null> {
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(), timeoutMs)
  try {
    const res = await fetch(apiUrl(method), {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : {},
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

/**
 * Sanitize text for Telegram's MarkdownV2 parse mode.
 *
 * Strategy: escape all MarkdownV2 special characters in plain-text regions,
 * while preserving code spans (`` `...` ``) and code blocks (` ```...``` `)
 * verbatim — Telegram renders those without further parsing.
 *
 * Incomplete code spans (e.g. a lone opening backtick mid-stream) fall through
 * to plain text where the backtick is escaped, keeping the message valid.
 */
export function sanitizeMarkdown(text: string): string {
  if (!text) return ''

  const parts: string[] = []
  let i = 0

  while (i < text.length) {
    // ── Triple-backtick code block ─────────────────────────────────────────
    if (text.startsWith('```', i)) {
      const closeIdx = text.indexOf('```', i + 3)
      if (closeIdx !== -1) {
        parts.push(text.slice(i, closeIdx + 3))  // preserve verbatim
        i = closeIdx + 3
        continue
      }
    }

    // ── Single-backtick code span ──────────────────────────────────────────
    if (text[i] === '`') {
      const closeIdx = text.indexOf('`', i + 1)
      // Only treat as a code span if it closes on the same line
      if (closeIdx !== -1 && !text.slice(i + 1, closeIdx).includes('\n')) {
        parts.push(text.slice(i, closeIdx + 1))  // preserve verbatim
        i = closeIdx + 1
        continue
      }
      // No valid closing backtick — escape the lone backtick and advance
      parts.push('\\`')
      i++
      continue
    }

    // ── Plain text: scan ahead to the next backtick ────────────────────────
    const nextBacktick = text.indexOf('`', i)
    if (nextBacktick === -1) {
      parts.push(escapeMarkdownV2Chars(text.slice(i)))
      break
    } else {
      parts.push(escapeMarkdownV2Chars(text.slice(i, nextBacktick)))
      i = nextBacktick
    }
  }

  return parts.join('')
}

/**
 * Send a new message to a chat.
 *
 * Attempts MarkdownV2 (with sanitized text) first. If the API rejects the
 * formatted send, falls back to plain text so the message always gets through.
 */
export async function sendMessage(
  chatId: number,
  text: string,
  parseMode?: 'MarkdownV2' | 'HTML',
): Promise<number | null> {
  if (parseMode === 'MarkdownV2') {
    const safeText = sanitizeMarkdown(text || '…')
    const result = await tgCall<{ message_id: number }>('sendMessage', {
      chat_id: chatId,
      text: safeText,
      parse_mode: 'MarkdownV2',
    })
    if (result !== null) return result.message_id ?? null
    // Formatted send failed — fall through to plain text
    WARN(`[telegram-common] sendMessage MarkdownV2 failed for chat ${chatId}, retrying as plain text`)
  } else if (parseMode === 'HTML') {
    const safeText = escapeHtml(text || '…')
    const result = await tgCall<{ message_id: number }>('sendMessage', {
      chat_id: chatId,
      text: safeText,
      parse_mode: 'HTML',
    })
    if (result !== null) return result.message_id ?? null
    WARN(`[telegram-common] sendMessage HTML failed for chat ${chatId}, retrying as plain text`)
  }

  // Plain text fallback (also used when parseMode is undefined)
  const result = await tgCall<{ message_id: number }>('sendMessage', {
    chat_id: chatId,
    text: text || '…',
  })
  return result?.message_id ?? null
}

/**
 * Edit an existing message in place.
 *
 * Same MarkdownV2-with-fallback strategy as sendMessage().
 */
export async function editMessage(
  chatId: number,
  msgId: number,
  text: string,
  parseMode?: 'MarkdownV2' | 'HTML',
): Promise<boolean> {
  if (parseMode === 'MarkdownV2') {
    const safeText = sanitizeMarkdown(text || '…')
    const result = await tgCall('editMessageText', {
      chat_id: chatId,
      message_id: msgId,
      text: safeText,
      parse_mode: 'MarkdownV2',
    })
    if (result !== null) return true
    WARN(`[telegram-common] editMessage MarkdownV2 failed for chat ${chatId} msg ${msgId}, retrying as plain text`)
  } else if (parseMode === 'HTML') {
    const safeText = escapeHtml(text || '…')
    const result = await tgCall('editMessageText', {
      chat_id: chatId,
      message_id: msgId,
      text: safeText,
      parse_mode: 'HTML',
    })
    if (result !== null) return true
    WARN(`[telegram-common] editMessage HTML failed for chat ${chatId} msg ${msgId}, retrying as plain text`)
  }

  // Plain text fallback
  const result = await tgCall('editMessageText', {
    chat_id: chatId,
    message_id: msgId,
    text: text || '…',
  })
  return result !== null
}

export async function sendTyping(chatId: number): Promise<void> {
  await tgCall('sendChatAction', { chat_id: chatId, action: 'typing' })
}

interface FileInfoResult { file_path?: string }

/**
 * Download the photo with the given file_id and return it as a base64
 * ImageAttachment. Returns null on any error (logged via WARN).
 */
export async function downloadPhoto(fileId: string): Promise<ImageAttachment | null> {
  try {
    const fileInfo = await tgCall<FileInfoResult>('getFile', { file_id: fileId })
    if (!fileInfo?.file_path) {
      WARN(`[telegram-common] downloadPhoto: no file_path in getFile result for ${fileId}`)
      return null
    }

    const fileUrl = `https://api.telegram.org/file/bot${TOKEN}/${fileInfo.file_path}`
    const photoAc = new AbortController()
    const photoTimer = setTimeout(() => photoAc.abort(), 20_000)
    const res = await fetch(fileUrl, { signal: photoAc.signal })
    clearTimeout(photoTimer)
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
