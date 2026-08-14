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
const TELEGRAM_MAX_MESSAGE_LENGTH = 4096
const RATE_LIMIT_WINDOW_MS = 1000
const RATE_LIMIT_MAX_MESSAGES = 10

const TELEGRAM_COMMANDS: tg.BotCommand[] = [
  { command: 'help', description: 'Show available commands' },
  { command: 'model', description: 'Show or change model' },
  { command: 'session', description: 'Session info' },
  { command: 'recall', description: 'Search memory' },
  { command: 'remember', description: 'Store a note' },
  { command: 'think', description: 'Trigger thinker cycle' },
  { command: 'cassi', description: 'MCP tools and agents' },
  { command: 'cassicore', description: 'Daemon CLI' },
  { command: 'cancel', description: 'Cancel current operation' },
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

interface RateLimitState {
  messageCount: number
  windowStart: number
}
const rateLimitState = new Map<number, RateLimitState>()

/** Returns true if message should be sent, false if rate limited. */
function checkRateLimit(chatId: number): boolean {
  const now = Date.now()
  let state = rateLimitState.get(chatId)
  
  if (!state || (now - state.windowStart) > RATE_LIMIT_WINDOW_MS) {
    state = { messageCount: 0, windowStart: now }
    rateLimitState.set(chatId, state)
  }
  
  if (state.messageCount >= RATE_LIMIT_MAX_MESSAGES) {
    return false
  }
  
  state.messageCount++
  return true
}

/**
 * Split content into chunks that fit within Telegram's message length limit.
 * Respects code block boundaries when possible.
 */
function chunkMessage(content: string, maxLength: number = TELEGRAM_MAX_MESSAGE_LENGTH): string[] {
  const chunks: string[] = []
  
  if (content.length <= maxLength) {
    return [content]
  }
  
  let remaining = content
  
  while (remaining.length > maxLength) {
    // Try to split at a code block boundary first
    const codeBlockMatch = remaining.slice(0, maxLength).match(/```[\s\S]*?\n```/g)
    if (codeBlockMatch && codeBlockMatch.length > 0) {
      const lastCodeBlock = codeBlockMatch[codeBlockMatch.length - 1]
      const lastCodeBlockEnd = remaining.indexOf(lastCodeBlock) + lastCodeBlock.length
      if (lastCodeBlockEnd > maxLength * 0.5) {
        chunks.push(remaining.slice(0, lastCodeBlockEnd))
        remaining = remaining.slice(lastCodeBlockEnd)
        continue
      }
    }
    
    // Try to split at paragraph boundary
    let splitIndex = remaining.lastIndexOf('\n\n', maxLength)
    if (splitIndex === -1 || splitIndex < maxLength * 0.5) {
      // Try single newline
      splitIndex = remaining.lastIndexOf('\n', maxLength)
    }
    if (splitIndex === -1 || splitIndex < maxLength * 0.5) {
      // Hard split at maxLength
      splitIndex = maxLength
    }
    
    chunks.push(remaining.slice(0, splitIndex))
    remaining = remaining.slice(splitIndex)
  }
  
  if (remaining.length > 0) {
    chunks.push(remaining)
  }
  
  return chunks
}

/**
 * Send a message with chunking and rate limiting.
 * Returns array of sent message IDs.
 */
async function sendChunkedMessage(chatId: number, content: string, parseMode?: 'MarkdownV2' | 'HTML'): Promise<number[]> {
  if (!checkRateLimit(chatId)) {
    log('warn', 'Rate limit exceeded, queuing message', { chatId })
    await sleep(RATE_LIMIT_WINDOW_MS)
  }
  
  const chunks = chunkMessage(content)
  const messageIds: number[] = []
  
  for (let i = 0; i < chunks.length; i++) {
    if (i > 0) {
      await sleep(EDIT_INTERVAL_MS)
      if (!checkRateLimit(chatId)) {
        await sleep(RATE_LIMIT_WINDOW_MS - (Date.now() % RATE_LIMIT_WINDOW_MS))
      }
    }
    
    try {
      const msgId = await tg.sendMessage(chatId, chunks[i], parseMode)
      if (msgId) messageIds.push(msgId)
    } catch (err) {
      log('warn', 'sendChunkedMessage error', { chatId, chunkIndex: i, error: String(err) })
    }
  }
  
  return messageIds
}

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
 *  and create duplicate messages.
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

  if (cfg.allowedChatIds?.length && !cfg.allowedChatIds.includes(chatId)) return

  // Handle /start locally — no daemon round-trip needed
  if (text === '/start' || text.startsWith('/start ')) {
    await tg.sendMessage(chatId, 'CassiCore is listening.')
    return
  }

  if (!text && !hasPhoto) return

  const sessionId = sessionIdFor(chatId)

  if (!text.startsWith('/')) {
    await tg.sendTyping(chatId)
    getOrCreateStream(chatId, sessionId)
    startStreamTimer(sessionId)
  }

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

function isChatIdAllowedForToolResponse(chatId: number): boolean {
  if (!cfg.allowedChatIds || cfg.allowedChatIds.length === 0) {
    return true
  }
  return cfg.allowedChatIds.includes(chatId)
}

/** Sends formatted tool results to the user. */
function handleToolCallResult(sessionId: string, payload: Record<string, unknown>): void {
  const chatId = parseChatId(sessionId)
  if (chatId === null) return
  
  if (!isChatIdAllowedForToolResponse(chatId)) {
    log('warn', 'Tool response blocked: chat ID not in allowed list', { chatId, sessionId })
    return
  }
  
  const toolName = payload.toolName as string ?? 'unknown'
  const result = payload.result as string ?? JSON.stringify(payload.result)
  
  const content = `**Tool Result: ${toolName}**\n\`\`\`\n${result}\n\`\`\``
  
  sendChunkedMessage(chatId, content, 'MarkdownV2').catch((err) => {
    log('warn', 'handleToolCallResult error', { sessionId, error: String(err) })
  })
}

/** Shows the model's reasoning process to the user. */
function handleReasoning(sessionId: string, payload: Record<string, unknown>): void {
  const chatId = parseChatId(sessionId)
  if (chatId === null) return
  
  const reasoning = payload.reasoning as string ?? payload.content as string ?? ''
  if (!reasoning) return
  
  const content = `🤔 *Reasoning:*\n${reasoning}`
  
  sendChunkedMessage(chatId, content, 'MarkdownV2').catch((err) => {
    log('warn', 'handleReasoning error', { sessionId, error: String(err) })
  })
}

/** Shows progress updates from long-running tools. */
function handleToolUpdate(sessionId: string, payload: Record<string, unknown>): void {
  const chatId = parseChatId(sessionId)
  if (chatId === null) return
  
  if (!isChatIdAllowedForToolResponse(chatId)) {
    log('warn', 'Tool update blocked: chat ID not in allowed list', { chatId, sessionId })
    return
  }
  
  const toolName = payload.toolName as string ?? 'unknown'
  const status = payload.status as string ?? 'updating'
  const message = payload.message as string ?? ''
  
  const content = `🔧 *${toolName}: ${status}*\n${message}`
  
  sendChunkedMessage(chatId, content, 'MarkdownV2').catch((err) => {
    log('warn', 'handleToolUpdate error', { sessionId, error: String(err) })
  })
}

/** Injects system messages and notifications into the conversation. */
function handleInject(sessionId: string, payload: Record<string, unknown>): void {
  const chatId = parseChatId(sessionId)
  if (chatId === null) return
  
  const content = payload.content as string ?? payload.message as string ?? ''
  const parseMode = payload.parse_mode as 'MarkdownV2' | 'HTML' | undefined
  const priority = payload.priority as 'high' | 'normal' | 'low' ?? 'normal'
  
  if (!content) return
  
  // High priority messages bypass rate limiting
  if (priority === 'high') {
    rateLimitState.delete(chatId)
  }
  
  sendChunkedMessage(chatId, content, parseMode).catch((err) => {
    log('warn', 'handleInject error', { sessionId, error: String(err) })
  })
}

/** Supports: content/done (streaming), tool_call, tool_call_result, reasoning, tool_update, inject */
function handleDaemonMessage(p: Record<string, unknown>): void {
  // PluginHost wraps all payloads in { type: 'message', payload: X }.
  // Status notifications arrive here instead of via 'status' type.
  if (p.type === 'status') {
    const inner = (p.payload ?? p) as StatusPayload
    handleStatusMessage(inner)
    return
  }

  const sessionId = p.sessionId as string | undefined
  const chatId = sessionId ? parseChatId(sessionId) : null
  
  if (!sessionId || chatId === null) return
  
  const eventType = p.type as string | undefined
  
  switch (eventType) {
    case 'tool_call_result':
      handleToolCallResult(sessionId, p)
      return
    
    case 'reasoning':
      handleReasoning(sessionId, p)
      return
    
    case 'tool_update':
      handleToolUpdate(sessionId, p)
      return
    
    case 'inject':
      handleInject(sessionId, p)
      return
    
    case 'tool_call':
      tg.sendTyping(chatId).catch(() => {})
      return
  }

  const content = p.content as string | undefined
  const parseMode = p.parse_mode as 'MarkdownV2' | 'HTML' | undefined
  const done = p.done as boolean | undefined

  const hasActiveStream = streams.has(sessionId)

  // Guard: ignore spurious done signals with no content and no active stream
  // (e.g., from duplicate turn:end events)
  if (done && !content && !hasActiveStream) return

  if (done && content && !hasActiveStream) {
    sendChunkedMessage(chatId, content, parseMode).catch((err) => {
      log('warn', 'sendMessage error', { sessionId, error: String(err) })
    })
    return
  }

  const s = getOrCreateStream(chatId, sessionId)
  if (content) {
    s.buffer += content
    startStreamTimer(sessionId)
  }

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

  if (p.type === 'compaction' || p.type === 'summarization') {
    sendChunkedMessage(chatId, p.text).catch(() => {})
  }
}


function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}
