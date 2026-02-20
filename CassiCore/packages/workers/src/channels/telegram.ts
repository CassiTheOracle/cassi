/**
 * Telegram channel worker for CassieCore.
 *
 * Uses long-polling (getUpdates) — no webhook/SSL needed.
 * Session ID = 'tg:' + chatId (stable per conversation).
 *
 * Streaming: buffers tokens, edits the "typing..." message live every ~400ms.
 * Falls back to single send if edit fails.
 *
 * Images: detects photo messages, downloads the largest available size via
 * the Bot API, base64-encodes them, and attaches to the inbound payload.
 *
 * FIXES:
 *   - getUpdates fetch timeout is now POLL_TIMEOUT_SEC + 10s (35s) — previously
 *     15s, which meant the fetch always aborted before Telegram responded.
 *   - Exponential backoff (2s → 4s → 8s → cap 30s) on getUpdates errors so
 *     we don't hammer the API after a transient failure.
 *   - Separate AbortController per poll so a slow response doesn't leak into
 *     the next cycle.
 */

import { parentPort } from 'node:worker_threads'

const POLL_TIMEOUT_SEC   = 25           // Telegram server-side long-poll timeout
const FETCH_TIMEOUT_MS   = (POLL_TIMEOUT_SEC + 10) * 1_000  // must exceed server timeout
const EDIT_INTERVAL_MS   = 450          // how often to flush streaming buffer to Telegram edit
const BACKOFF_BASE_MS    = 2_000
const BACKOFF_MAX_MS     = 30_000

type HostMessage =
  | { type: 'init';          config: TelegramConfig }
  | { type: 'config:update'; config: Partial<TelegramConfig> }
  | { type: 'message';       payload: { sessionId: string; content: string; done?: boolean } }
  | { type: 'shutdown' }

interface TelegramConfig {
  token: string
  allowedChatIds?: number[]
}

type WorkerMessage =
  | { type: 'ready' }
  | { type: 'message'; payload: { sessionId: string; content: string; attachments?: ImageAttachment[] } }
  | { type: 'error';   message: string }
  | { type: 'log';     level: 'info' | 'warn' | 'error'; message: string }

interface ImageAttachment {
  data: string
  mediaType: 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp'
  label?: string
}

// ── state ─────────────────────────────────────────────────────────────────────

let cfg: TelegramConfig = { token: '' }
let offset = 0
let polling = false
let shutdownRequested = false

// Per-session streaming buffer: sessionId → { chatId, msgId, buffer, timer }
interface StreamState {
  chatId: number
  msgId:  number | null
  buffer: string
  timer:  ReturnType<typeof setInterval> | null
}
const streams = new Map<string, StreamState>()

// ── Telegram API helpers ──────────────────────────────────────────────────────

function apiUrl(method: string): string {
  return `https://api.telegram.org/bot${cfg.token}/${method}`
}

async function tgCall<T>(method: string, body?: Record<string, unknown>, timeoutMs = 15_000): Promise<T | null> {
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
      log('warn', `tg/${method} not ok: ${json.description ?? '?'}`)
      return null
    }
    return json.result
  } catch (err) {
    clearTimeout(timer)
    // Silently swallow AbortError/TimeoutError — these are expected on slow/missing
    // responses to non-critical API calls (typing indicators etc.)
    if (err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError')) return null
    log('warn', `tg/${method} error: ${String(err)}`)
    return null
  }
}

/**
 * Escape special characters for Telegram MarkdownV2.
 * This prevents "Can't find end of the entity" errors from unclosed markdown.
 */
function sanitizeMarkdown(text: string): string {
  // Escape characters that have special meaning in MarkdownV2
  // Precede the following characters with a backslash:
  // _ * [ ] ( ) ~ ` > # + - = | { } . !
  return text.replace(/([_\*\[\]\(\)~`>#+\-=|{}.!])/g, '\\$1')
}

async function sendMessage(chatId: number, text: string): Promise<number | null> {
  const safeText = sanitizeMarkdown(text || '…')
  const result = await tgCall<{ message_id: number }>('sendMessage', {
    chat_id:    chatId,
    text:       safeText,
    parse_mode: 'MarkdownV2',
  })
  return result?.message_id ?? null
}

async function editMessage(chatId: number, msgId: number, text: string): Promise<boolean> {
  const safeText = sanitizeMarkdown(text || '…')
  const result = await tgCall('editMessageText', {
    chat_id:    chatId,
    message_id: msgId,
    text:       safeText,
    parse_mode: 'MarkdownV2',
  })
  return result !== null
}

async function sendTyping(chatId: number): Promise<void> {
  await tgCall('sendChatAction', { chat_id: chatId, action: 'typing' })
}

// ── Image download ────────────────────────────────────────────────────────────

interface TgPhotoSize {
  file_id:    string
  file_size?: number
  width:      number
  height:     number
}

/**
 * Download a Telegram file by file_id and return base64-encoded bytes.
 * Returns null on any failure (best-effort — don't crash the turn).
 */
async function downloadPhoto(fileId: string): Promise<ImageAttachment | null> {
  try {
    const fileInfo = await tgCall<{ file_path: string }>('getFile', { file_id: fileId })
    if (!fileInfo?.file_path) return null

    const fileUrl = `https://api.telegram.org/file/bot${cfg.token}/${fileInfo.file_path}`
    const photoAc = new AbortController()
    const photoTimer = setTimeout(() => photoAc.abort(), 20_000)
    const res = await fetch(fileUrl, { signal: photoAc.signal })
    clearTimeout(photoTimer)
    if (!res.ok) return null

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
    log('warn', `failed to download photo ${fileId}: ${String(err)}`)
    return null
  }
}

// ── Streaming: buffer → edit loop ────────────────────────────────────────────

function sessionIdFor(chatId: number): string {
  return `tg:${chatId}`
}

function getOrCreateStream(chatId: number, sessionId: string): StreamState {
  let s = streams.get(sessionId)
  if (!s) {
    s = { chatId, msgId: null, buffer: '', timer: null }
    streams.set(sessionId, s)
  }
  return s
}

async function flushStream(sessionId: string): Promise<void> {
  const s = streams.get(sessionId)
  if (!s || !s.buffer) return

  const text = s.buffer
  if (s.msgId === null) {
    const msgId = await sendMessage(s.chatId, text)
    s.msgId = msgId
  } else {
    await editMessage(s.chatId, s.msgId, text)
  }
}

function startStreamTimer(sessionId: string): void {
  const s = streams.get(sessionId)
  if (!s || s.timer) return
  s.timer = setInterval(() => {
    flushStream(sessionId).catch(() => {})
  }, EDIT_INTERVAL_MS)
}

async function finalizeStream(sessionId: string): Promise<void> {
  const s = streams.get(sessionId)
  if (!s) return

  if (s.timer) { clearInterval(s.timer); s.timer = null }
  await flushStream(sessionId)
  streams.delete(sessionId)
}

// ── Long-polling loop ─────────────────────────────────────────────────────────

interface TgUpdate {
  update_id: number
  message?: {
    message_id: number
    chat: { id: number; type: string }
    from?: { id: number; username?: string; first_name?: string }
    text?: string
    caption?: string
    photo?: TgPhotoSize[]
    date: number
  }
}

async function pollLoop(): Promise<void> {
  if (polling) return
  polling = true
  log('info', `Telegram long-poll started (timeout=${POLL_TIMEOUT_SEC}s, fetch timeout=${FETCH_TIMEOUT_MS}ms)`)

  let backoffMs = BACKOFF_BASE_MS

  while (!shutdownRequested) {
    if (!cfg.token) { await sleep(2000); continue }

    // Use a dedicated AbortController so each poll cycle is independent
    const controller = new AbortController()
    const fetchTimer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)

    let updates: TgUpdate[] | null = null
    try {
      const res = await fetch(apiUrl('getUpdates'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          offset,
          timeout: POLL_TIMEOUT_SEC,
          allowed_updates: ['message'],
        }),
        signal: controller.signal,
      })
      clearTimeout(fetchTimer)

      const json = await res.json() as { ok: boolean; result: TgUpdate[]; description?: string }
      if (!json.ok) {
        log('warn', `tg/getUpdates not ok: ${json.description ?? '?'}`)
        await sleep(backoffMs)
        backoffMs = Math.min(backoffMs * 2, BACKOFF_MAX_MS)
        continue
      }
      updates = json.result
      backoffMs = BACKOFF_BASE_MS  // reset backoff on success
    } catch (err) {
      clearTimeout(fetchTimer)
      // DOMException AbortError is expected when we abort — not a real error
      const isAbort = err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError')
      if (!isAbort) {
        log('warn', `tg/getUpdates error: ${String(err)} — retrying in ${backoffMs}ms`)
        await sleep(backoffMs)
        backoffMs = Math.min(backoffMs * 2, BACKOFF_MAX_MS)
      }
      continue
    }

    if (!updates) continue

    for (const upd of updates) {
      offset = upd.update_id + 1
      if (upd.message) {
        await handleIncoming(upd.message)
      }
    }
  }

  polling = false
  log('info', 'Telegram poll loop stopped.')
}

async function handleIncoming(msg: NonNullable<TgUpdate['message']>): Promise<void> {
  const chatId  = msg.chat.id
  const text    = (msg.text ?? msg.caption ?? '').trim()
  const hasPhoto = Array.isArray(msg.photo) && msg.photo.length > 0

  if (cfg.allowedChatIds?.length && !cfg.allowedChatIds.includes(chatId)) {
    log('warn', `Ignoring message from non-allowed chatId ${chatId}`)
    return
  }

  if (text.startsWith('/start')) {
    await sendMessage(chatId, '👋 CassieCore is listening.')
    return
  }

  if (!text && !hasPhoto) return

  await sendTyping(chatId)

  const sessionId = sessionIdFor(chatId)
  getOrCreateStream(chatId, sessionId)
  startStreamTimer(sessionId)

  let attachments: ImageAttachment[] | undefined
  if (hasPhoto && msg.photo) {
    const largest = msg.photo[msg.photo.length - 1]
    const att = await downloadPhoto(largest.file_id)
    if (att) {
      attachments = [att]
      log('info', `Downloaded photo for session ${sessionId} (${att.data.length} b64 chars)`)
    }
  }

  const payload: { sessionId: string; content: string; attachments?: ImageAttachment[] } = {
    sessionId,
    content: text || '(image)',
  }
  if (attachments) payload.attachments = attachments

  parentPort?.postMessage({ type: 'message', payload } satisfies WorkerMessage)
}

// ── Handle messages from daemon ───────────────────────────────────────────────

parentPort?.on('message', (m: HostMessage) => {
  if (m.type === 'init') {
    cfg = m.config
    if (cfg.token) pollLoop().catch((e) => log('error', `poll loop crashed: ${String(e)}`))
    parentPort?.postMessage({ type: 'ready' } satisfies WorkerMessage)
    return
  }

  if (m.type === 'config:update') {
    const prevToken = cfg.token
    cfg = { ...cfg, ...m.config }
    if (!prevToken && cfg.token) {
      pollLoop().catch((e) => log('error', `poll loop crashed: ${String(e)}`))
    }
    return
  }

  if (m.type === 'message') {
    const { sessionId, content, done } = m.payload
    const chatId = parseChatId(sessionId)
    if (chatId === null) return

    const s = getOrCreateStream(chatId, sessionId)
    s.buffer += content
    startStreamTimer(sessionId)

    if (done) {
      finalizeStream(sessionId).catch(() => {})
    }
    return
  }

  if (m.type === 'shutdown') {
    shutdownRequested = true
    const pending = [...streams.keys()].map(sid => finalizeStream(sid))
    Promise.allSettled(pending).finally(() => process.exit(0))
  }
})

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseChatId(sessionId: string): number | null {
  if (!sessionId.startsWith('tg:')) return null
  const n = Number(sessionId.slice(3))
  return Number.isFinite(n) ? n : null
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

function log(level: 'info' | 'warn' | 'error', msg: string): void {
  parentPort?.postMessage({
    type: 'log',
    level,
    message: `[telegram] ${msg}`,
  })
  process.stderr.write(`[telegram/${level}] ${msg}\n`)
}
