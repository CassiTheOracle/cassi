/**
 * Telegram channel worker for ClaraCore.
 *
 * Uses long-polling (getUpdates) — no webhook/SSL needed.
 * Session ID = 'tg:' + chatId (stable per conversation).
 *
 * Streaming: buffers tokens, edits the "typing..." message live every ~400ms.
 * Falls back to single send if edit fails.
 */

import { parentPort } from 'node:worker_threads'

const POLL_TIMEOUT_SEC = 25          // Telegram long-poll timeout
const EDIT_INTERVAL_MS  = 450        // how often to flush streaming buffer to Telegram edit

type HostMessage =
  | { type: 'init';         config: TelegramConfig }
  | { type: 'config:update'; config: Partial<TelegramConfig> }
  | { type: 'message';      payload: { sessionId: string; content: string; done?: boolean } }
  | { type: 'shutdown' }

interface TelegramConfig {
  token: string
  allowedChatIds?: number[]   // if set, only these chat IDs are accepted
}

type WorkerMessage =
  | { type: 'ready' }
  | { type: 'message'; payload: { sessionId: string; content: string } }
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
  msgId:  number | null   // null until first message is sent
  buffer: string
  timer:  ReturnType<typeof setInterval> | null
}
const streams = new Map<string, StreamState>()

// ── Telegram API helpers ──────────────────────────────────────────────────────

function apiUrl(method: string): string {
  return `https://api.telegram.org/bot${cfg.token}/${method}`
}

async function tgCall<T>(method: string, body?: Record<string, unknown>): Promise<T | null> {
  try {
    const res = await fetch(apiUrl(method), {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(15_000),
    })
    const json = await res.json() as { ok: boolean; result: T; description?: string }
    if (!json.ok) {
      log('warn', `tg/${method} not ok: ${json.description ?? '?'}`)
      return null
    }
    return json.result
  } catch (err) {
    log('warn', `tg/${method} error: ${String(err)}`)
    return null
  }
}

async function sendMessage(chatId: number, text: string): Promise<number | null> {
  const result = await tgCall<{ message_id: number }>('sendMessage', {
    chat_id:    chatId,
    text:       text || '…',
    parse_mode: 'Markdown',
  })
  return result?.message_id ?? null
}

async function editMessage(chatId: number, msgId: number, text: string): Promise<boolean> {
  const result = await tgCall('editMessageText', {
    chat_id:    chatId,
    message_id: msgId,
    text:       text || '…',
    parse_mode: 'Markdown',
  })
  return result !== null
}

async function sendTyping(chatId: number): Promise<void> {
  await tgCall('sendChatAction', { chat_id: chatId, action: 'typing' })
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
    // First chunk — send new message
    const msgId = await sendMessage(s.chatId, text)
    s.msgId = msgId
  } else {
    // Subsequent chunks — edit in place (ignore failures, Telegram rate-limits edits)
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

  // Final flush
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
    date: number
  }
}

async function pollLoop(): Promise<void> {
  if (polling) return
  polling = true
  log('info', `Telegram long-poll started (bot token set, timeout=${POLL_TIMEOUT_SEC}s)`)

  while (!shutdownRequested) {
    if (!cfg.token) { await sleep(2000); continue }

    const updates = await tgCall<TgUpdate[]>('getUpdates', {
      offset,
      timeout: POLL_TIMEOUT_SEC,
      allowed_updates: ['message'],
    })

    if (!updates) { await sleep(3000); continue }

    for (const upd of updates) {
      offset = upd.update_id + 1
      if (upd.message?.text) {
        await handleIncoming(upd.message)
      }
    }
  }

  polling = false
  log('info', 'Telegram poll loop stopped.')
}

async function handleIncoming(msg: NonNullable<TgUpdate['message']>): Promise<void> {
  const chatId = msg.chat.id
  const text   = msg.text?.trim() ?? ''

  // Allowlist check
  if (cfg.allowedChatIds?.length && !cfg.allowedChatIds.includes(chatId)) {
    log('warn', `Ignoring message from non-allowed chatId ${chatId}`)
    return
  }

  // Ignore bot commands silently (for now)
  if (text.startsWith('/start')) {
    await sendMessage(chatId, '👋 ClaraCore is listening.')
    return
  }

  if (!text) return

  // Pre-warm typing indicator
  await sendTyping(chatId)

  const sessionId = sessionIdFor(chatId)

  // Pre-create stream state so tokens can accumulate before first flush
  getOrCreateStream(chatId, sessionId)
  startStreamTimer(sessionId)

  // Emit to daemon
  parentPort?.postMessage({
    type: 'message',
    payload: { sessionId, content: text },
  } satisfies WorkerMessage)
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

    // Determine chatId from sessionId (tg:12345 → 12345)
    const chatId = parseChatId(sessionId)
    if (chatId === null) return   // not our session

    const s = getOrCreateStream(chatId, sessionId)
    s.buffer += content

    // Start timer if not started (handles case where stream arrives before poll)
    startStreamTimer(sessionId)

    // If done, finalize
    if (done) {
      finalizeStream(sessionId).catch(() => {})
    }
    return
  }

  if (m.type === 'shutdown') {
    shutdownRequested = true
    // Finalize any in-flight streams
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
  // Use a 'log' type message that daemon can handle without treating as error
  parentPort?.postMessage({
    type: 'log',
    level,
    message: `[telegram] ${msg}`,
  })
  // Also stderr for local visibility
  process.stderr.write(`[telegram/${level}] ${msg}\n`)
}
