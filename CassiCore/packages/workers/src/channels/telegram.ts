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
import * as tg from './telegram-common.js'

const POLL_TIMEOUT_SEC   = 25           // Telegram server-side long-poll timeout
const FETCH_TIMEOUT_MS   = (POLL_TIMEOUT_SEC + 10) * 1_000  // must exceed server timeout
const EDIT_INTERVAL_MS   = 1000         // Optimized: 1s to respect Telegram's rate limits for edits
const BACKOFF_BASE_MS    = 2_000
const BACKOFF_MAX_MS     = 30_000

type HostMessage =
  | { type: 'init';          config: TelegramConfig }
  | { type: 'config:update'; config: Partial<TelegramConfig> }
  | { type: 'message';       payload: { sessionId: string; content: string; done?: boolean; parse_mode?: 'MarkdownV2' | 'HTML' } }
  | { type: 'status';        payload: { sessionId: string; text: string; type?: string } }
  | { type: 'shutdown' }

interface TelegramConfig {
  token: string
  allowedChatIds?: number[]
}

type WorkerMessage =
  | { type: 'ready' }
  | { type: 'message'; payload: { sessionId: string; content: string; attachments?: tg.ImageAttachment[] } }
  | { type: 'signal';  payload: { sessionId: string; signalType: string; content: string } }
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

// Wire token and logger into common helpers
function setTokenFromCfg() {
  tg.setToken(cfg.token)
}

function initCommonHelpers() {
  tg.setToken(cfg.token)
  // Route common-module warnings through the structured log channel so they
  // appear in daemon logs rather than raw stderr.
  tg.setLogger((msg) => log('warn', msg))
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

function chooseParseModeForText(text: string): 'MarkdownV2' | 'HTML' {
  if (!text) return 'MarkdownV2'
  
  // If the text already has HTML tags that we explicitly support, use HTML
  if (text.includes('<code>') || text.includes('<pre>') || text.includes('<b>') || text.includes('<i>') || text.includes('<a href=')) {
    return 'HTML'
  }
  
  // Default to MarkdownV2 for everything else. 
  // We will handle markdown-to-entities conversion in the common helper.
  return 'MarkdownV2'
}

async function flushStream(sessionId: string): Promise<void> {
  const s = streams.get(sessionId)
  if (!s || !s.buffer) return

  const text = s.buffer
  const parseMode = chooseParseModeForText(text)

  if (s.msgId === null) {
    const msgId = await tg.sendMessage(s.chatId, text, parseMode)
    s.msgId = msgId
  } else {
    await tg.editMessage(s.chatId, s.msgId as number, text, parseMode)
  }
}

function startStreamTimer(sessionId: string): void {
  const s = streams.get(sessionId)
  if (!s || s.timer) return
  let typingCounter = 0
  s.timer = setInterval(() => {
    flushStream(sessionId).catch((err) => log('warn', `stream flush error for ${sessionId}: ${String(err)}`))
    
    // Refresh typing indicator every ~5 seconds
    typingCounter += EDIT_INTERVAL_MS
    if (typingCounter >= 4000) {
      tg.sendTyping(s.chatId).catch(() => {})
      typingCounter = 0
    }
  }, EDIT_INTERVAL_MS)
}

async function finalizeStream(sessionId: string): Promise<void> {
  const s = streams.get(sessionId)
  if (!s) return

  if (s.timer) { clearInterval(s.timer); s.timer = null }
  
  // Only flush if there is still something in the buffer
  if (s.buffer) {
    await flushStream(sessionId)
  }
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
        const desc = String(json.description ?? '')
        if (desc.includes('Conflict: terminated by other getUpdates request')) {
          log('info', `tg/getUpdates conflict: ${desc} — backing off`)
        } else {
          log('warn', `tg/getUpdates not ok: ${desc}`)
        }
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

  // ── SIGNAL DETECTION: Recognize feedback/directives ──────────────────────
  let isSignal = false
  let signalType = ''
  
  if (text.startsWith('!')) {
    isSignal = true
    const spaceIdx = text.indexOf(' ')
    signalType = spaceIdx > 0 ? text.slice(1, spaceIdx) : text.slice(1)
    if (!signalType) signalType = 'feedback'
  } else if (text.toLowerCase().includes('fix this') || text.toLowerCase().includes('don\'t do that') || text.toLowerCase().includes('stop')) {
    isSignal = true
    signalType = 'feedback'
  } else if (text.toLowerCase().startsWith('instruction:') || text.toLowerCase().startsWith('directive:')) {
    isSignal = true
    signalType = 'instruction'
  }

  if (isSignal) {
    log('info', `Detected signal in Telegram: ${signalType}`)
    parentPort?.postMessage({
      type: 'signal',
      payload: { sessionId, signalType, content: text }
    } satisfies WorkerMessage)
    // continue to process as message too
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
    initCommonHelpers()
    if (cfg.token) pollLoop().catch((e) => log('error', `poll loop crashed: ${String(e)}`))
    parentPort?.postMessage({ type: 'ready' } satisfies WorkerMessage)
    return
  }

  if (m.type === 'config:update') {
    const prevToken = cfg.token
    cfg = { ...cfg, ...m.config }
    if (cfg.token !== prevToken) tg.setToken(cfg.token)
    if (!prevToken && cfg.token) {
      pollLoop().catch((e) => log('error', `poll loop crashed: ${String(e)}`))
    }
    return
  }

  if (m.type === 'message') {
    const p = m.payload as Record<string, unknown>

    // PluginHost.send() always wraps payloads in { type: 'message', payload: X }.
    // Status notifications therefore arrive here rather than via m.type === 'status'.
    // Detect and route them before falling through to the streaming path.
    if (p.type === 'status') {
      const inner = (p.payload ?? p) as Record<string, unknown>
      const statusSid  = String(inner.sessionId ?? '')
      const statusText = String(inner.text ?? '')
      const statusType = String(inner.type ?? '')
      const chatId = parseChatId(statusSid)
      if (chatId !== null) {
        if (statusType === 'compaction' || statusType === 'summarization') {
          tg.sendMessage(chatId, `🧠 _${statusText}_`, 'MarkdownV2')
            .catch((err) => log('warn', `status sendMessage error: ${String(err)}`))
        } else {
          log('info', `Status update for ${statusSid}: ${statusText}`)
        }
      }
      return
    }

    const { sessionId, content, done, parse_mode } = p as {
      sessionId: string
      content: string
      done?: boolean
      parse_mode?: 'MarkdownV2' | 'HTML'
    }
    const chatId = parseChatId(sessionId)
    if (chatId === null) return

    const hasActiveStream = streams.has(sessionId)
    
    // Send a one-off message (not part of an active stream)
    if (done && content && !hasActiveStream) {
      const providedParse = parse_mode as 'MarkdownV2' | 'HTML' | undefined
      const finalParse = providedParse ?? chooseParseModeForText(content)
      tg.sendMessage(chatId, content, finalParse).catch((err) => log('warn', `sendMessage error for ${sessionId}: ${String(err)}`))
      return
    }

    // Append to existing stream or create new one
    const s = getOrCreateStream(chatId, sessionId)
    if (content) {
      s.buffer += content
      startStreamTimer(sessionId)
    }

    if (done) {
      // Finalizing: ensure we stop the timer first to avoid concurrent edits
      if (s.timer) { clearInterval(s.timer); s.timer = null }
      finalizeStream(sessionId).catch((err) => log('warn', `stream finalize error for ${sessionId}: ${String(err)}`))
    }
    return
  }

  if (m.type === 'status') {
    const { sessionId, text, type } = m.payload
    const chatId = parseChatId(sessionId)
    if (chatId === null) return
    
    // Show a short notice for interesting statuses
    if (type === 'compaction' || type === 'summarization') {
      tg.sendMessage(chatId, `🧠 _${text}_`, 'MarkdownV2').catch((err) => log('warn', `status sendMessage error: ${String(err)}`))
    } else {
      log('info', `Status update for ${sessionId}: ${text}`)
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
