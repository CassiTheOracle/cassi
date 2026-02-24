/**
 * Telegram channel worker for CassiCore.
 *
 * Uses long-polling (getUpdates) - no webhook/SSL needed.
 * Session ID = 'tg:' + chatId (stable per conversation).
 *
 * Streaming: buffers tokens, edits the "typing..." message live every ~400ms.
 * Falls back to single send if edit fails.
 *
 * Images: detects photo messages, downloads the largest available size via
 * the Bot API, base64-encodes them, and attaches to the inbound payload.
 *
 * FIXES:
 *   - getUpdates fetch timeout is now POLL_TIMEOUT_SEC + 10s (35s) - previously
 *     15s, which meant the fetch always aborted before Telegram responded.
 *   - Exponential backoff (2s → 4s → 8s → cap 30s) on getUpdates errors so
 *     we don't hammer the API after a transient failure.
 *   - Separate AbortController per poll so a slow response doesn't leak into
 *     the next cycle.
 */

import { parentPort } from 'node:worker_threads'
import * as tg from './telegram-common'

const POLL_TIMEOUT_SEC   = 25           // Telegram server-side long-poll timeout
const FETCH_TIMEOUT_MS   = (POLL_TIMEOUT_SEC + 10) * 1_000  // must exceed server timeout
const EDIT_INTERVAL_MS   = 450          // how often to flush streaming buffer to Telegram edit
const BACKOFF_BASE_MS    = 2_000
const BACKOFF_MAX_MS     = 30_000

type HostMessage =
  | { type: 'init';          config: TelegramConfig }
  | { type: 'config:update'; config: Partial<TelegramConfig> }
  | { type: 'message';       payload: { sessionId: string; content: string; done?: boolean; parse_mode?: 'MarkdownV2' | 'HTML' } }
  | { type: 'shutdown' }

interface TelegramConfig {
  token: string
  allowedChatIds?: number[]
}

type WorkerMessage =
  | { type: 'ready' }
  | { type: 'message'; payload: { sessionId: string; content: string; attachments?: tg.ImageAttachment[] } }
  | { type: 'error';   message: string }
  | { type: 'log';     level: 'info' | 'warn' | 'error'; message: string }

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

// Wire token into common helper
function setTokenFromCfg() {
  tg.setToken(cfg.token)
}

// ── Streaming: buffer → edit loop (uses tg common helpers) ───────────────────

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
    const msgId = await tg.sendMessage(s.chatId, text)
    s.msgId = msgId
  } else {
    await tg.editMessage(s.chatId, s.msgId as number, text)
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

interface TgPhotoSize {
  file_id:    string
  file_size?: number
  width:      number
  height:     number
}

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
      const res = await fetch(`https://api.telegram.org/bot${cfg.token}/getUpdates`, {
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
    await tg.sendMessage(chatId, '👋 CassiCore is listening.')
    return
  }

  if (!text && !hasPhoto) return

  const sessionId = sessionIdFor(chatId)

  // ── COMMAND BYPASS: Send commands directly without streaming overhead ─────
  if (text.startsWith('/')) {
    parentPort?.postMessage({
      type: 'message',
      payload: { sessionId, content: text }
    } satisfies WorkerMessage)
    return
  }

  // ── NORMAL MESSAGE: Set up streaming for LLM responses ────────────────────
  await tg.sendTyping(chatId)
  getOrCreateStream(chatId, sessionId)
  startStreamTimer(sessionId)

  let attachments: tg.ImageAttachment[] | undefined
  if (hasPhoto && msg.photo) {
    const largest = msg.photo[msg.photo.length - 1]
    const att = await tg.downloadPhoto(largest.file_id)
    if (att) {
      attachments = [att]
      log('info', `Downloaded photo for session ${sessionId} (${att.data.length} b64 chars)`)
    }
  }

  const payload: { sessionId: string; content: string; attachments?: tg.ImageAttachment[] } = {
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
    setTokenFromCfg()
    if (cfg.token) pollLoop().catch((e) => log('error', `poll loop crashed: ${String(e)}`))
    parentPort?.postMessage({ type: 'ready' } satisfies WorkerMessage)
    return
  }

  if (m.type === 'config:update') {
    const prevToken = cfg.token
    cfg = { ...cfg, ...m.config }
    if (cfg.token !== prevToken) setTokenFromCfg()
    if (!prevToken && cfg.token) {
      pollLoop().catch((e) => log('error', `poll loop crashed: ${String(e)}`))
    }
    return
  }

  if (m.type === 'message') {
    const { sessionId, content, done, parse_mode } = m.payload
    const chatId = parseChatId(sessionId)
    if (chatId === null) return

    const hasActiveStream = streams.has(sessionId)
    if (done && content && !hasActiveStream) {
      const parseMode = parse_mode as 'MarkdownV2' | 'HTML' | undefined
      tg.sendMessage(chatId, content, parseMode).catch(() => {})
      return
    }

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
