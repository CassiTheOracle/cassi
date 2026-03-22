/**
 * Telegram channel worker for CassiCore.
 *
 * TRANSPORT ONLY — all intelligence, tools, model resolution, and streaming
 * are handled by the daemon's SessionPipeline via the channel message handler.
 *
 * Responsibilities:
 *  - Poll Telegram API for updates (long-polling with exponential backoff)
 *  - Download photo attachments
 *  - Forward messages to daemon via workerPort
 *  - Buffer streaming tokens and edit messages (Telegram rate limit: ~1 edit/sec)
 *  - Send typing indicators
 *  - Handle /start locally
 *
 * Everything else — commands, model selection, tool execution, system prompt,
 * memory retrieval, intelligence context — is the daemon's job.
 */

import { workerPort } from '../../core/worker-ipc.js'
import * as tg from './telegram-common.js'


const POLL_TIMEOUT_SEC = 25
const FETCH_TIMEOUT_MS = (POLL_TIMEOUT_SEC + 10) * 1_000
const EDIT_INTERVAL_MS = 1000
const TYPING_INTERVAL_MS = 4000
const BACKOFF_BASE_MS = 2_000
const BACKOFF_MAX_MS = 30_000

const TELEGRAM_COMMANDS: tg.BotCommand[] = [
  { command: 'cassi', description: 'MCP tools: list, invoke, or run agents' },
  { command: 'cassicore', description: 'Daemon CLI (boot/model/provider)' },
  { command: 'help', description: 'Show available commands' },
  { command: 'start', description: 'Initialize the bot' },
  { command: 'bash', description: 'Execute a shell command' },
  { command: 'read', description: 'Read a file' },
  { command: 'model', description: 'Show or change model' },
  { command: 'think', description: 'Trigger thinker cycle' },
  { command: 'recall', description: 'Search memory' },
  { command: 'remember', description: 'Store a note' },
  { command: 'git', description: 'Git operations' },
  { command: 'session', description: 'Session info' },
  { command: 'cancel', description: 'Cancel current operation' },
  { command: 'skip', description: 'Skip optional parameter' },
  { command: 'confirm', description: 'Confirm tool execution' },
]

async function registerBotCommands(): Promise<void> {
  if (!cfg.token) return
  await tg.setMyCommands(TELEGRAM_COMMANDS)
}


interface TelegramConfig {
  token: string
  allowedChatIds?: number[]
}

/** Messages FROM the daemon */
type HostMessage =
  | { type: 'init'; config: TelegramConfig }
  | { type: 'config:update'; config: Partial<TelegramConfig> }
  | { type: 'message'; payload: Record<string, unknown> }
  | { type: 'status'; payload: StatusPayload }
  | { type: 'shutdown' }

interface StatusPayload {
  sessionId: string
  text: string
  type?: string
}

/** Messages TO the daemon */
type WorkerMessage =
  | { type: 'ready' }
  | { type: 'message'; payload: { sessionId: string; content: string; attachments?: tg.ImageAttachment[] } }
  | { type: 'error'; message: string }
  | { type: 'log'; level: 'info' | 'warn' | 'error'; message: string }


let cfg: TelegramConfig = { token: '' }
let offset = 0
let polling = false
let shutdownRequested = false

/** Per-session streaming state: accumulates tokens, edits message every 1s. */
interface StreamState {
  chatId: number
  msgId: number | null
  buffer: string
  lastFlushed: string
  timer: ReturnType<typeof setInterval> | null
  /** Serializes flush operations to prevent concurrent sendMessage/editMessage calls.
   *  Without this, a timer-initiated flush and a finalize flush can both see msgId===null
   *  and both call sendMessage, creating duplicate messages. */
  flushChain: Promise<void>
}
const streams = new Map<string, StreamState>()


function log(level: 'info' | 'warn' | 'error', msg: string, meta?: Record<string, unknown>): void {
  const entry: Record<string, unknown> = { type: 'log', level, message: `[telegram] ${msg}` }
  if (meta) entry.meta = meta
  workerPort.postMessage(entry as unknown as WorkerMessage)
}


function sessionIdFor(chatId: number): string {
  return `tg:${chatId}`
}

/**
 * @dep callers: handleStatusMessage (workers/channels/telegram.ts), handleDaemonMessage (workers/channels/telegram.ts)
 * @dep module: Channels
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function parseChatId(sessionId: string): number | null {
  if (!sessionId.startsWith('tg:')) return null
  const n = Number(sessionId.slice(3))
  return Number.isFinite(n) ? n : null
}


/**
 * @dep callers: handleDaemonMessage (workers/channels/telegram.ts), handleIncoming (workers/channels/telegram.ts)
 * @dep calls: get
 * @dep module: Channels
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function getOrCreateStream(chatId: number, sessionId: string): StreamState {
  let s = streams.get(sessionId)
  if (!s) {
    s = { chatId, msgId: null, buffer: '', lastFlushed: '', timer: null, flushChain: Promise.resolve() }
    streams.set(sessionId, s)
  }
  return s
}

/** Internal flush — must only be called via enqueueFlush to prevent concurrent execution. */
async function doFlush(s: StreamState): Promise<void> {
  if (!s.buffer) return

  // Skip edit if buffer hasn't changed since last flush (avoids Telegram "not modified" errors)
  if (s.msgId !== null && s.buffer === s.lastFlushed) return

  if (s.msgId === null) {
    s.msgId = await tg.sendMessage(s.chatId, s.buffer)
  } else {
    await tg.editMessage(s.chatId, s.msgId, s.buffer)
  }
  s.lastFlushed = s.buffer
}

/** Enqueue a flush operation on the stream's serial chain.
 *  This ensures only one sendMessage/editMessage is in-flight at a time,
 *  preventing the race where two concurrent flushes both see msgId===null
 *  and create duplicate messages. */
/**
 * @dep callers: finalizeStream (workers/channels/telegram.ts), startStreamTimer (workers/channels/telegram.ts)
 * @dep calls: get, doFlush
 * @dep module: Branching-conversation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function enqueueFlush(sessionId: string): void {
  const s = streams.get(sessionId)
  if (!s) return
  s.flushChain = s.flushChain.then(() => doFlush(s)).catch((err) => {
    log('warn', 'stream flush error', { sessionId, error: String(err) })
  })
}

/**
 * @dep callers: handleDaemonMessage (workers/channels/telegram.ts), handleIncoming (workers/channels/telegram.ts)
 * @dep calls: get, enqueueFlush, sendTyping
 * @dep module: Channels
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function startStreamTimer(sessionId: string): void {
  const s = streams.get(sessionId)
  if (!s || s.timer) return

  let typingCounter = 0
  s.timer = setInterval(() => {
    enqueueFlush(sessionId)
    typingCounter += EDIT_INTERVAL_MS
    if (typingCounter >= TYPING_INTERVAL_MS) {
      tg.sendTyping(s.chatId).catch(() => {})
      typingCounter = 0
    }
  }, EDIT_INTERVAL_MS)
}

async function finalizeStream(sessionId: string): Promise<void> {
  const s = streams.get(sessionId)
  if (!s) return

  if (s.timer) { clearInterval(s.timer); s.timer = null }
  // Enqueue one final flush, then wait for the entire chain to complete
  enqueueFlush(sessionId)
  await s.flushChain
  streams.delete(sessionId)
}


interface TgUpdate {
  update_id: number
  message?: {
    message_id: number
    chat: { id: number; type: string }
    from?: { id: number; username?: string; first_name?: string }
    text?: string
    caption?: string
    photo?: Array<{ file_id: string; width: number; height: number }>
    date: number
  }
}

async function pollLoop(): Promise<void> {
  if (polling) return
  polling = true
  log('info', `Long-poll started (timeout=${POLL_TIMEOUT_SEC}s)`)

  let backoffMs = BACKOFF_BASE_MS

  while (!shutdownRequested) {
    if (!cfg.token) { await sleep(2000); continue }

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)

    try {
      const res = await fetch(`https://api.telegram.org/bot${cfg.token}/getUpdates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ offset, timeout: POLL_TIMEOUT_SEC, allowed_updates: ['message'] }),
        signal: controller.signal,
      })
      clearTimeout(timer)

      const json = await res.json() as { ok: boolean; result: TgUpdate[]; description?: string }
      if (!json.ok) {
        const desc = json.description ?? '?'
        // Conflict means another instance is polling — back off
        if (desc.includes('Conflict')) {
          log('info', `getUpdates conflict — backing off`)
        } else {
          log('warn', `getUpdates not ok: ${desc}`)
        }
        await sleep(backoffMs)
        backoffMs = Math.min(backoffMs * 2, BACKOFF_MAX_MS)
        continue
      }

      backoffMs = BACKOFF_BASE_MS
      for (const upd of json.result) {
        offset = upd.update_id + 1
        if (upd.message) await handleIncoming(upd.message)
      }
    } catch (err) {
      clearTimeout(timer)
      const isAbort = err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError')
      if (!isAbort) {
        log('warn', 'getUpdates error', { error: String(err), backoffMs })
        await sleep(backoffMs)
        backoffMs = Math.min(backoffMs * 2, BACKOFF_MAX_MS)
      }
    }
  }

  polling = false
  log('info', 'Poll loop stopped')
}


async function handleIncoming(msg: NonNullable<TgUpdate['message']>): Promise<void> {
  const chatId = msg.chat.id
  const text = (msg.text ?? msg.caption ?? '').trim()
  const hasPhoto = Array.isArray(msg.photo) && msg.photo.length > 0

  // Access control
  if (cfg.allowedChatIds?.length && !cfg.allowedChatIds.includes(chatId)) return

  // Handle /start locally — no daemon round-trip needed
  if (text === '/start' || text.startsWith('/start ')) {
    await tg.sendMessage(chatId, 'CassiCore is listening.')
    return
  }

  // Skip empty messages (no text and no photo)
  if (!text && !hasPhoto) return

  const sessionId = sessionIdFor(chatId)

  // For non-command messages, show typing and prepare stream buffer
  if (!text.startsWith('/')) {
    await tg.sendTyping(chatId)
    getOrCreateStream(chatId, sessionId)
    startStreamTimer(sessionId)
  }

  // Download photo attachment if present
  let attachments: tg.ImageAttachment[] | undefined
  if (hasPhoto && msg.photo) {
    const largest = msg.photo[msg.photo.length - 1]
    const att = await tg.downloadPhoto(largest.file_id)
    if (att) attachments = [att]
  }

  // Forward to daemon — commands, model, tools, intelligence all handled there
  const payload: { sessionId: string; content: string; attachments?: tg.ImageAttachment[] } = {
    sessionId,
    content: text || '(image)',
  }
  if (attachments) payload.attachments = attachments
  workerPort.postMessage({ type: 'message', payload } satisfies WorkerMessage)
}


workerPort.on('message', (raw) => {
  const m = raw as HostMessage

  switch (m.type) {
    case 'init':
      cfg = m.config
      tg.setToken(cfg.token)
      tg.setLogger((msg) => log('warn', msg))
      if (cfg.token) {
        registerBotCommands().catch((e) => log('warn', 'setMyCommands failed', { error: String(e) }))
        pollLoop().catch((e) => log('error', 'poll loop crashed', { error: String(e) }))
      }
      workerPort.postMessage({ type: 'ready' } satisfies WorkerMessage)
      break

    case 'config:update': {
      const prevToken = cfg.token
      cfg = { ...cfg, ...m.config }
      if (cfg.token !== prevToken) tg.setToken(cfg.token)
      if (!prevToken && cfg.token) {
        registerBotCommands().catch((e) => log('warn', 'setMyCommands failed', { error: String(e) }))
        pollLoop().catch((e) => log('error', 'poll loop crashed', { error: String(e) }))
      }
      break
    }

    case 'message':
      handleDaemonMessage(m.payload)
      break

    case 'status':
      handleStatusMessage(m.payload)
      break

    case 'shutdown':
      shutdownRequested = true
      Promise.allSettled([...streams.keys()].map(finalizeStream))
        .finally(() => process.exit(0))
      break
  }
})


function handleDaemonMessage(p: Record<string, unknown>): void {
  // PluginHost wraps all payloads in { type: 'message', payload: X }.
  // Status notifications arrive here instead of via 'status' type.
  if (p.type === 'status') {
    const inner = (p.payload ?? p) as StatusPayload
    handleStatusMessage(inner)
    return
  }

  const sessionId = p.sessionId as string | undefined
  const content = p.content as string | undefined
  const parseMode = p.parse_mode as 'MarkdownV2' | 'HTML' | undefined
  const done = p.done as boolean | undefined
  const msgType = p.type as string | undefined

  if (!sessionId) return
  const chatId = parseChatId(sessionId)
  if (chatId === null) return

  // Tool call notifications: show typing indicator instead of adding to buffer
  if (msgType === 'tool_call') {
    tg.sendTyping(chatId).catch(() => {})
    return
  }

  const hasActiveStream = streams.has(sessionId)

  // Guard: ignore spurious done signals with no content and no active stream
  // (e.g., from duplicate turn:end events)
  if (done && !content && !hasActiveStream) return

  // One-off message (not part of an active stream)
  if (done && content && !hasActiveStream) {
    tg.sendMessage(chatId, content, parseMode).catch((err) => {
      log('warn', 'sendMessage error', { sessionId, error: String(err) })
    })
    return
  }

  // Append to stream buffer
  const s = getOrCreateStream(chatId, sessionId)
  if (content) {
    s.buffer += content
    startStreamTimer(sessionId)
  }

  // Finalize stream
  if (done) {
    if (s.timer) { clearInterval(s.timer); s.timer = null }
    // Always finalize the stream to stop typing indicator, even if buffer is empty
    // If buffer has content, flush it; otherwise send empty message to clear typing
    if (s.buffer) {
      enqueueFlush(sessionId)
    } else {
      // Send empty message to stop typing indicator when no content was produced
      tg.sendMessage(chatId, '').catch(() => {})
    }
    finalizeStream(sessionId).catch((err) => {
      log('warn', 'stream finalize error', { sessionId, error: String(err) })
    })
  }
}

/**
 * @dep callers: telegram.ts (workers/channels/telegram.ts), handleDaemonMessage (workers/channels/telegram.ts)
 * @dep calls: sendMessage, parseChatId
 * @dep module: Channels
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function handleStatusMessage(p: StatusPayload): void {
  const chatId = parseChatId(p.sessionId)
  if (chatId === null) return

  // Show cognitive status updates (compaction, summarization)
  if (p.type === 'compaction' || p.type === 'summarization') {
    tg.sendMessage(chatId, p.text).catch(() => {})
  }
}


function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}
