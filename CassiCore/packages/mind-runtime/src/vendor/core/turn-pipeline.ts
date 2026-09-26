/*
 * Turn middleware pipeline for CassieCore.
 *
 * Middlewares are applied in registration order.
 * The provider middleware runs the tool-use loop (stream  execute  continue).
 *
 * REQUEST-BURN FIXES:
 *
 * 1. makeContinuityMiddleware  removed. Continuity turns are already in
 *    session.history (session-manager persists every turn to SQLite). Injecting
 *    them again doubled the context and spent tokens on data the model already
 *    had. getRecent() now only fires if session.history is empty (cold-start
 *    recovery from a fresh daemon boot where the in-memory history is gone but
 *    SQLite still has the turns).
 *
 * 2. makeThinkerMiddleware  removed inline call. The Thinker fires
 *    fire-and-forget AFTER turns via onTurnEnd(). Calling think('sonnet')
 *    inside the pipeline added a full blocking provider round-trip to every
 *    10th turn. The background cycle already handles this.
 *
 * 3. Optimizer steering messages now use a lightweight system-prompt injection
 *    instead of pipeline.process(). That eliminates the provider request the
 *    optimizer was burning every time it detected a loop.
 *    (Optimizer changes in optimizer/index.ts)
 */

import { SESSION_SETTINGS, getModelSpec } from '@cassicore/foundation'
import { formatSiblingBlock } from './intelligence/session-digest.js'
import { compactMessages, shouldCompact, estimateSessionTokens, DEFAULT_COMPACTION_CONFIG } from './intelligence/layered-compaction.js'
import { bus as globalBus } from '@cassicore/events'
import { CHARS_PER_TOKEN } from './intelligence/shared/token-estimation.js'
import { signalPromise } from '@cassicore/utils'
import { isOverflowError, stripToolFiller, contentLength, ContextOverflowError, hasQuestionResult, buildToolUseMapFromMessages } from '@cassicore/utils'

import type { IOrchestrationBus } from './orchestration-bus.js'
import type { SessionManager } from './session-manager.js'
import type { IMemory } from '@cassicore/foundation'
import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { IProvider, TurnContext, TurnResult, InboundMessage, Message, ContentBlock, CompletionOpts, CompletionChunk, ImageAttachment, Session } from '@cassicore/foundation'
import type { DialecticSystem } from '@cassicore/cortex-pineal-dialectic'
import type { SessionDigestStore } from './intelligence/session-digest.js'
import type { ToolExecutor } from '@cassicore/tools'
import type { ToolRegistry } from '@cassicore/tools'
import type { ToolCall } from '@cassicore/tools'
import type { TraceInjectionPart, TraceToolCall, TurnTrace } from '@cassicore/foundation'
// MemoryModule was deleted; the legacy ArchiveEntry shape is inlined here for
// the few trace-snapshot callsites that still consume it via TraceMemoryLike.
interface ArchiveEntry {
  id: string
  content: string
  type: string
  createdAt: number
  sessionId?: string
  source?: string
  metadata?: Record<string, unknown>
  analysis?: {
    summary?: string
    topics?: string[]
    entities?: string[]
    sentiment?: string
    importance?: number
    tags?: string[]
    keyFacts?: Iterable<string>
  }
}




const MAX_TOOL_ROUNDS = SESSION_SETTINGS.maxToolRounds

/** Maximum chars for the tool-loop message array before emergency trimming. */
const TOOL_LOOP_MAX_CHARS = 120_000


export type TurnMiddleware = (
  ctx: TurnContext,
  next: () => Promise<TurnResult>
) => Promise<TurnResult>

interface TraceMemoryLike {
  getConversationWithThinking?(sessionId: string, limit?: number): ArchiveEntry[]
  archiveEvent?(eventType: string, content: string, metadata?: Record<string, unknown>): Promise<{ id: string }>
}


export const systemPromptMiddleware: TurnMiddleware = async (ctx, next) => {
  const sp = ctx.session.config.systemPrompt
  const hasSystem = ctx.messages.find(m => m.role === 'system')
  if (sp && !hasSystem) {
    // Include session ID in system prompt for provider tracking
    const sessionMarker = `session:${ctx.session.id}`
    const spWithMarker = `${sp}\n\n[${sessionMarker}]`
    ctx.messages = [{ role: 'system', content: spWithMarker }, ...ctx.messages]
    ctx.opts = { ...ctx.opts, systemPrompt: spWithMarker }
  }
  return next()
}

interface ContextWindowDebugger {
  captureSnapshot(sessionId: string, turnIndex: number, model: string, messages: Message[], contextWindow: number): void
}
let contextWindowDebugger: ContextWindowDebugger | null = null

export function setContextWindowDebugger(debugFn: ContextWindowDebugger | null): void {
  contextWindowDebugger = debugFn
}

export const contextWindowDebugMiddleware: TurnMiddleware = async (ctx, next) => {
  if (contextWindowDebugger) {
    try {
      const turnIndex = ctx.session.history?.length || 0
      const model = ctx.session.config.model || 'unknown'
      const contextWindow = ctx.session.config.maxContextTokens || 200000

      contextWindowDebugger.captureSnapshot(
        ctx.session.id,
        turnIndex,
        model,
        ctx.messages,
        contextWindow
      )
    } catch (err) {
      // Silent fail - debugging shouldn't break the pipeline
    }
  }
  return next()
}

export const contextWindowMiddleware: TurnMiddleware = async (ctx, next) => {
  if (!ctx.messages || ctx.messages.length === 0) return next()

  const max = ctx.session.config.maxContextTokens ?? SESSION_SETTINGS.defaultMaxContextTokens
  // WHY: 3x multiplier is conservative for code-heavy sessions
  const budgetChars = max * 3

  // WHY: layered compaction preserves structure better than trim
  const compactionConfig = {
    preserveRecentMessages: 6,  // 3 full turns
    maxEstimatedTokens: Math.floor(max * 0.7), // compact when 70% of budget used
  }

  if (shouldCompact(ctx.messages, compactionConfig)) {
    const result = compactMessages(ctx.messages, compactionConfig)
    if (result.removedMessageCount > 0) {
      ctx.messages = result.compactedMessages
      // Emit compaction event for observability
      try {
        globalBus.emit({
          type: 'context:compacted' as any,
          sessionId: ctx.session.id,
          removedMessages: result.removedMessageCount,
          preservedMessages: result.compactedMessages.length - 1, // minus the summary msg
          timestamp: new Date(),
        })
      } catch { /* non-fatal */ }
    }
  }

  // WHY: hard trim is the safety net when compaction fails
  const systemMsgs = ctx.messages.filter(m => m.role === 'system')
  const lastUser = ctx.messages[ctx.messages.length - 1]
  const history = ctx.messages.filter(m => m.role !== 'system' && m !== lastUser)

  let totalChars = systemMsgs.reduce((s, m) => s + contentLength(m.content), 0)
  totalChars += contentLength(lastUser.content)

  const kept: Message[] = []
  // Keep last 10 messages max (5 full turns), AND enforce budget
  const MAX_HISTORY_MESSAGES = 10
  
  for (let i = history.length - 1; i >= Math.max(0, history.length - MAX_HISTORY_MESSAGES); i--) {
    const chars = contentLength(history[i].content)
    if (totalChars + chars > budgetChars) break
    kept.unshift(history[i])
    totalChars += chars
  }

  ctx.messages = [...systemMsgs, ...kept, lastUser]
  return next()
}

/**
 * Continuity middleware — cold-start recovery only.
 *
 * Under normal operation, session.history already contains all prior turns
 * (session-manager writes every turn to SQLite and restores on getOrCreate).
 * Calling continuity.getRecent() on every turn would duplicate context the
 * model already has, burning tokens unnecessarily.
 *
 * We only invoke it when history is empty — meaning the daemon just restarted
 * and the in-memory history hasn't been seeded yet. In that case we pull the
 * last 20 turns from the continuity DB and inject them as a summary block so
 * the model has continuity on the very first post-restart turn.
 */
export function makeContinuityMiddleware(continuity: {
  getRecent(sessionId: string, limit?: number): Promise<Array<{ role: string; content: string }>>
  saveTurn(turn: { sessionId: string; role: string; content: string; tokensUsed?: number; model?: string }): Promise<void>
}): TurnMiddleware {
  return async (ctx, next) => {
    try {
      // WHY: only inject on cold-start recovery to avoid duplicates
      const historyDepth = Math.max(0, ctx.messages.filter(m => m.role !== 'system').length - 1)  // exclude current user msg
      if (historyDepth <= 0) {
        const recent = await continuity.getRecent(ctx.session.id, 20)
        if (recent.length > 0) {
          const summary = recent
            .map(t => `[${t.role}]: ${t.content.slice(0, 200)}`)
            .join('\n')
          const injected = `[CONTINUITY — recovered ${recent.length} turns from previous session]\n${summary}\n[/CONTINUITY]`
          const sysIdx = ctx.messages.findIndex(m => m.role === 'system')
          const insertAt = sysIdx >= 0 ? sysIdx + 1 : 0
          ctx.messages = [
            ...ctx.messages.slice(0, insertAt),
            { role: 'system', content: injected },
            ...ctx.messages.slice(insertAt),
          ]
        }
      }
    } catch { /* best-effort */ }

    const result = await next()

    // Save both sides of the turn to continuity DB so it stays in sync
    try {
      const userContent = typeof ctx.inbound.content === 'string'
        ? ctx.inbound.content
        : '(image)'
      await continuity.saveTurn({ sessionId: ctx.session.id, role: 'user', content: userContent })
      if (result.response) {
        await continuity.saveTurn({
          sessionId: ctx.session.id,
          role: 'assistant',
          content: result.response,
          tokensUsed: result.tokensUsed,
          model: result.model,
        })
      }
    } catch { /* best-effort */ }

    return result
  }
}


/**
 * @dep callers: buildDefaultChain (core/turn-pipeline.ts), process (core/intelligence/triad-team/cell-turn-pipeline.ts)
 * @dep calls: executeAll, toAnthropicSchema, has, emit, streamOnce [+4]
 * @dep module: Cluster_97
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function makeProviderMiddleware(
  providers: Map<string, IProvider>,
  bus: IEventBus,
  logger: ILogger,
  toolRegistry?: ToolRegistry,
  toolExecutor?: ToolExecutor,
): TurnMiddleware {
  return async (ctx, next) => {
    // If macro-dialectic middleware already handled this turn via Unity,
    // skip the provider call entirely. The __result is already set.
    if ((ctx as unknown as Record<string, unknown>).__unityHandled) {
      return next()
    }

    const [provId, ...rest] = ctx.opts.model.includes('/')
      ? ctx.opts.model.split('/')
      : ['github-copilot', ctx.opts.model]
    const provider = providers.get(provId)
    if (!provider) throw new Error(`Provider '${provId}' not loaded`)

    const sysMsg = ctx.messages.find(m => m.role === 'system')

    const modelName = rest.join('/')
    const start = Date.now()
    let totalTokens = 0
    const toolCallLog: Array<{ name: string; durationMs: number }> = []

    const opts: CompletionOpts = {
      ...ctx.opts,
      model: modelName,
      stream: true,
      source: 'turn-pipeline',
      trigger: undefined,
      tools: toolRegistry
        ? toolRegistry.toAnthropicSchema()
        : undefined,
    }

    // Pull attachments from the inbound message (first round only)
    const inboundAttachments = ctx.inbound.attachments

    // Direct streaming callback (bypasses event bus for SSE)
    const onStreamEvent: ((type: string, data: any) => void) | undefined = (ctx.inbound as any).onStreamEvent

    const messages = [...ctx.messages]
    let finalText = ''
    const toolOutputs: Array<{
      tool_name: string;
      tool_call_id: string;
      output: string;
      is_error: boolean;
      timestamp: Date;
    }> = []

    let overflowRetried = false
    for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
      const roundOpts: CompletionOpts = round === 0
        ? opts
        : { ...opts, thinking: 'none' }

      // Only pass attachments on the first round — they belong to the user's message
      const roundAttachments = round === 0 ? inboundAttachments : undefined

      let streamResult: { text: string; toolCalls: ToolCall[]; tokensUsed: number; thinkingBlocks: string[] }
      try {
        streamResult = await streamOnce(
          provider, messages, roundOpts, ctx.session.id, bus, logger, roundAttachments, ctx.opts.signal, onStreamEvent,
        )
      } catch (err) {
        if (err instanceof ContextOverflowError && !overflowRetried) {
          overflowRetried = true
          logger.warn('Context overflow detected — applying emergency trim and retrying', {
            sessionId: ctx.session.id,
            messageCount: messages.length,
            totalChars: messages.reduce((s, m) => s + contentLength(m.content), 0),
          })

          // Keep only the first system message (base prompt), drop all injected system messages
          const firstSys = messages.find(m => m.role === 'system')
          const nonSystem = messages.filter(m => m.role !== 'system')

          // From non-system messages, keep only the last 6 (3 pairs) + current user message
          const trimmedNonSystem = nonSystem.length > 6
            ? nonSystem.slice(-6)
            : nonSystem

          messages.length = 0
          if (firstSys) messages.push(firstSys)
          messages.push(...trimmedNonSystem)

          logger.info('Emergency trim complete, retrying', {
            newMessageCount: messages.length,
            newChars: messages.reduce((s, m) => s + contentLength(m.content), 0),
          })

          // Retry this round
          round--
          continue
        }
        throw err  // Non-overflow error or already retried — propagate
      }

      const { text, toolCalls, tokensUsed, thinkingBlocks } = streamResult
      totalTokens += tokensUsed

      if (toolCalls.length === 0 || !toolExecutor) {
        finalText = text
        // Push final assistant response to messages array (fixes empty assistant bug)
        if (text) {
          messages.push({ role: 'assistant', content: [{ type: 'text', text }] })
        }
        break
      }

      // Strip filler text before tool calls for cleaner conversational flow
      const cleanedText = stripToolFiller(text || '')

      const assistantContent: ContentBlock[] = []
      if (cleanedText) assistantContent.push({ type: 'text', text: cleanedText })
      for (const tc of toolCalls) {
        assistantContent.push({ type: 'tool_use', id: tc.id, name: tc.name, input: tc.input })
      }
      messages.push({ role: 'assistant', content: assistantContent })

      for (const tc of toolCalls) {
        bus.emit({
          type: 'worker:message',
          pluginId: `session:${ctx.session.id}`,
          payload: { type: 'turn:tool_call', sessionId: ctx.session.id, toolCallId: tc.id, tool: tc.name, input: tc.input },
        })
        onStreamEvent?.('tool_call', { toolCallId: tc.id, tool: tc.name, input: tc.input })
      }

      const toolStart = Date.now()
      const results = await toolExecutor.executeAll(toolCalls, ctx.session.id)
      const toolDuration = Date.now() - toolStart
      for (const tc of toolCalls) {
        toolCallLog.push({ name: tc.name, durationMs: toolDuration })
      }

      // Emit tool results for monitoring
      for (let idx = 0; idx < results.length; idx++) {
        const r = results[idx]
        const tc = toolCalls[idx]
        // Truncate content for the event — full content is kept in messages for the provider
        const contentPreview = typeof r.content === 'string'
          ? r.content.slice(0, 500) + (r.content.length > 500 ? '…' : '')
          : String(r.content ?? '').slice(0, 500)
        bus.emit({
          type: 'worker:message',
          pluginId: `session:${ctx.session.id}`,
          payload: { type: 'turn:tool_result', sessionId: ctx.session.id, toolCallId: r.toolCallId, tool: tc?.name ?? 'unknown', isError: r.isError, content: contentPreview },
        })
        onStreamEvent?.('tool_result', { toolCallId: r.toolCallId, isError: r.isError, content: contentPreview })
      }

      // Emit aggregated tool:round-complete for cognitive modules (Reverie, Reflex, etc.)
      bus.emit({
        type: 'tool:round-complete',
        sessionId: ctx.session.id,
        round,
        toolCalls: toolCalls.map(tc => ({ name: tc.name, id: tc.id })),
        results: results.map((r, idx) => ({
          toolCallId: r.toolCallId,
          isError: r.isError,
          contentPreview: typeof r.content === 'string' ? r.content : String(r.content ?? ''),
        })),
        timestamp: new Date(),
      } as any)

      // Build reasoning prefix from thinking blocks for this round
      const reasoningPrefix = thinkingBlocks.length > 0
        ? `[Previous reasoning: ${thinkingBlocks.join('').trim()}]\n\n`
        : ''

      const resultBlocks: ContentBlock[] = results.map((r, idx) => {
        const tc = toolCalls[idx]
        const isQuestion = tc?.name === 'question' || tc?.name === 'AskUserQuestion'
        const content = isQuestion && reasoningPrefix
          ? `${reasoningPrefix}${r.content}`
          : r.content
        return {
          type: 'tool_result' as const,
          tool_use_id: r.toolCallId,
          content,
          is_error: r.isError || undefined,
          tool_name: r.toolName,
        }
      })
      messages.push({ role: 'user', content: resultBlocks })

      const loopChars = messages.reduce((s, m) => s + contentLength(m.content), 0)
      if (loopChars > TOOL_LOOP_MAX_CHARS) {
        // Identify tool-pair boundaries: assistant(tool_use) + user(tool_result) pairs
        // Keep: all system messages, the initial user message (idx after system), and last 3 tool pairs
        // Question tool results are treated as user messages and never trimmed
        const systemEnd = messages.findIndex(m => m.role !== 'system')
        const preserveHead = systemEnd >= 0 ? systemEnd + 1 : 1  // system msgs + first user msg
        const toolUseMap = buildToolUseMapFromMessages(messages)

        // Count trimmable tool pairs (exclude pairs with question results)
        let toolPairCount = 0
        for (let i = preserveHead; i < messages.length - 1; i++) {
          const m = messages[i]
          if (m.role === 'assistant' && Array.isArray(m.content) &&
              (m.content as ContentBlock[]).some(b => b.type === 'tool_use')) {
            // Skip if the following user message contains a question result
            if (i + 1 < messages.length && hasQuestionResult(messages[i + 1], { toolUseMap })) continue
            toolPairCount++
          }
        }

        // Drop oldest tool pairs until under budget (keep last 3 pairs minimum)
        const KEEP_PAIRS = 3
        if (toolPairCount > KEEP_PAIRS) {
          let pairsToRemove = toolPairCount - KEEP_PAIRS
          let newChars = loopChars
          const toRemove: number[] = []

          for (let i = preserveHead; i < messages.length - 1 && pairsToRemove > 0; i++) {
            const m = messages[i]
            if (m.role === 'assistant' && Array.isArray(m.content) &&
                (m.content as ContentBlock[]).some(b => b.type === 'tool_use')) {
              // Skip pairs containing question results — they're user messages
              if (i + 1 < messages.length && hasQuestionResult(messages[i + 1], { toolUseMap })) continue

              // Found a tool_use assistant msg — mark it and its following tool_result for removal
              const assistChars = contentLength(m.content)
              toRemove.push(i)
              newChars -= assistChars
              // The next message should be the tool_result
              if (i + 1 < messages.length - 1 && messages[i + 1].role === 'user') {
                const resultChars = contentLength(messages[i + 1].content)
                toRemove.push(i + 1)
                newChars -= resultChars
              }
              pairsToRemove--
              if (newChars <= TOOL_LOOP_MAX_CHARS) break
            }
          }

          if (toRemove.length > 0) {
            const removeSet = new Set(toRemove)
            const trimmed = messages.filter((_, idx) => !removeSet.has(idx))
            messages.length = 0
            messages.push(...trimmed)
            logger.debug('Mid-loop context trim: dropped tool pairs', {
              removed: toRemove.length,
              oldChars: loopChars,
              newChars: messages.reduce((s, m) => s + contentLength(m.content), 0),
            })
          }
        }
      }

      // Build tool_outputs array for TurnResult
      const now = new Date()
      for (let idx = 0; idx < results.length; idx++) {
        const r = results[idx]
        const tc = toolCalls[idx]
        toolOutputs.push({
          tool_name: tc?.name || 'unknown',
          tool_call_id: r.toolCallId,
          output: r.content,
          is_error: r.isError,
          timestamp: now,
        })
      }
    }

    const result: TurnResult = {
      response: finalText,
      tokensUsed: totalTokens,
      model: modelName,
      durationMs: Date.now() - start,
      toolCalls: toolCallLog.length > 0 ? toolCallLog : undefined,
      tool_outputs: toolOutputs.length > 0 ? toolOutputs : undefined,
    }

      ; (ctx as unknown as Record<string, unknown>)['__result'] = result
    return next().then(() => result)
  }
}

/** Single provider stream call — collect text tokens and tool_use chunks */
async function streamOnce(
  provider: IProvider,
  messages: Message[],
  opts: CompletionOpts,
  sessionId: string,
  bus: IEventBus,
  logger: ILogger,
  attachments?: ImageAttachment[],
  signal?: AbortSignal,
  onStreamEvent?: (type: string, data: any) => void,
): Promise<{ text: string; toolCalls: ToolCall[]; tokensUsed: number; thinkingBlocks: string[] }> {
  let text = ''
  const toolCalls: ToolCall[] = []
  let tokensUsed = 0
  let tokenBuffer: string[] = []
  const thinkingBlocks: string[] = []

  try {
    // Extended provider interface with optional attachments and signal support
    interface IExtendedProvider extends IProvider {
      complete(messages: Message[], opts: CompletionOpts, attachments?: ImageAttachment[], signal?: AbortSignal): AsyncIterable<CompletionChunk>
    }
    const stream = (provider as IExtendedProvider).complete(messages, opts, attachments, signal)
    let chunkCount = 0

    const streamAsync = stream as AsyncIterable<CompletionChunk> & { [Symbol.asyncIterator](): AsyncIterator<CompletionChunk> }
    const iterator = streamAsync[Symbol.asyncIterator] ? streamAsync[Symbol.asyncIterator]() : null
    if (!iterator) throw new Error('provider did not return an async iterator')

    // WHY: cancellation promise races against provider to enable abort
    const pCancel = signal ? signalPromise(signal) : new Promise<void>(() => {})

    interface CancelledResult { __cancelled: true }

    while (true) {
      // Race between the provider iterator and a possible cancellation signal
      const race: IteratorResult<CompletionChunk> | CancelledResult = await Promise.race([
        iterator.next(),
        pCancel.then((): CancelledResult => ({ __cancelled: true })),
      ])

      if ('__cancelled' in race && race.__cancelled) {
        // Attempt graceful shutdown of provider iterator
        if (typeof iterator.return === 'function') {
          try { await iterator.return() } catch {}
        }
        // Notify listeners of cancellation
        bus.emit({
          type: 'worker:message',
          pluginId: `session:${sessionId}`,
          payload: { type: 'turn:error', sessionId, error: 'cancelled' },
        })
        throw new Error('cancelled')
      }

      const nextResult = race as IteratorResult<CompletionChunk>
      if (nextResult.done) break
      const ch = nextResult.value

      chunkCount++
      if (ch.type === 'token') {
        const t = ch.text ?? ''
        text += t
        tokensUsed += ch.tokensUsed ?? Math.ceil(t.length / CHARS_PER_TOKEN)
        tokenBuffer.push(t)  // Buffer for bus emission (batch)
        // Stream tokens immediately via direct callback for SSE
        onStreamEvent?.('token', { token: t })
      } else if (ch.type === 'thinking') {
        const t = ch.text ?? ''
        // Thinking tokens are NOT included in the response text — they are
        // only emitted as events for internal subscribers (subconscious, etc.)
        tokensUsed += ch.tokensUsed ?? Math.ceil(t.length / CHARS_PER_TOKEN)
        thinkingBlocks.push(t)
        bus.emit({
          type: 'worker:message',
          pluginId: `session:${sessionId}`,
          payload: { type: 'turn:thinking', sessionId, token: t },
        })
        // Stream thinking tokens for SSE so the UI can show reasoning in real-time
        onStreamEvent?.('thinking', { token: t })
      } else if (ch.type === 'tool_use' && ch.toolCall) {
        toolCalls.push(ch.toolCall as ToolCall)
      } else if (ch.type === 'error') {
        const errText = ch.error ?? 'provider error'
        if (isOverflowError(errText)) {
          throw new ContextOverflowError(errText)
        }
        throw new Error(errText)
      }
    }

    // Stream completed - decide what to emit
    if (toolCalls.length > 0) {
      // Tools detected - strip filler before emitting
      const bufferedText = tokenBuffer.join('')
      const cleanedText = stripToolFiller(bufferedText)
      if (cleanedText) {
        bus.emit({
          type: 'worker:message',
          pluginId: `session:${sessionId}`,
          payload: { type: 'turn:token', sessionId, token: cleanedText },
        })
      }
    } else {
      // No tools - emit buffered tokens normally
      for (const token of tokenBuffer) {
        bus.emit({
          type: 'worker:message',
          pluginId: `session:${sessionId}`,
          payload: { type: 'turn:token', sessionId, token },
        })
      }
    }
  } catch (err) {
    // Flush any buffered tokens so the UI doesn't appear "stuck" with no output
    for (const token of tokenBuffer) {
      bus.emit({
        type: 'worker:message',
        pluginId: `session:${sessionId}`,
        payload: { type: 'turn:token', sessionId, token },
      })
    }
    tokenBuffer = []

    // Reclassify generic Errors that carry overflow messages (e.g. "http 400: prompt token count...")
    if (!(err instanceof ContextOverflowError) && err instanceof Error && isOverflowError(err.message)) {
      const overflow = new ContextOverflowError(err.message)
      logger.error(`context overflow detected: ${err.message}`)
      bus.emit({
        type: 'worker:message',
        pluginId: `session:${sessionId}`,
        payload: { type: 'turn:error', sessionId, error: overflow.message },
      })
      throw overflow
    }

    const errorInfo: Record<string, unknown> = {
      operation: 'provider_complete',
      message: err instanceof Error ? err.message : String(err),
      sessionId,
    }
    if (err instanceof Error && err.stack) {
      errorInfo.stack = err.stack
    }
    logger.error('provider error', errorInfo)
    bus.emit({
      type: 'worker:message',
      pluginId: `session:${sessionId}`,
      payload: { type: 'turn:error', sessionId, error: String(err) },
    })
    throw err
  }

  return { text, toolCalls, tokensUsed, thinkingBlocks }
}

/**
 * Per-session state for memory middleware (collected during turn processing)
 */
interface SessionArchiveState {
  thinkingBlocks: string[]
  toolCalls: Array<{name: string; input: unknown; output?: string; error?: boolean}>
}

// Module-level state storage (avoids closure creation per turn)
const sessionArchiveStates = new Map<string, SessionArchiveState>()

// Private state storage for TurnContext metadata (avoids as any casts)
const turnContextMeta = new WeakMap<TurnContext, { preIndexMsgCount: number }>()

// Extended Memory interface with optional archivist methods
interface IExtendedMemory extends IMemory {
  archiveConversation?(sessionId: string, userContent: string, assistantContent: string, thinking?: string, metadata?: Record<string, unknown>): Promise<{ id: string; analysis: unknown }>
  archiveToolCall?(sessionId: string, toolName: string, input: unknown, output?: unknown, error?: string, metadata?: Record<string, unknown>): Promise<{ id: string; analysis: unknown }>
  indexIncremental?(sessionId: string, history: Message[], fromMsgIdx: number): string
}

/**
 * Memory middleware with comprehensive archiving (v0.1.3-optimized)
 *
 * OPTIMIZATIONS:
 * - Fire-and-forget archiving (non-blocking)
 * - No bus monkey-patching (uses pre-registered listeners)
 * - Single state lookup per session
 *
 * Archives all context flowing through the system:
 * - User/assistant conversations
 * - Model thinking/reasoning blocks
 * - Tool calls and their results
 * - Metadata (model, tokens, timing)
 */
export function makeMemoryMiddleware(memory: IMemory, bus?: IEventBus, logger?: ILogger): TurnMiddleware {
  // OPTIMIZATION: Register listeners once at middleware creation, not per-turn
  if (bus) {
    // These events are emitted via worker:message payload, not as direct event types
    interface TurnThinkingEvent { sessionId?: string; token?: string }
    interface TurnToolCallEvent { sessionId?: string; tool?: string; input?: unknown }
    interface TurnToolResultEvent { sessionId?: string; result?: string; isError?: boolean }
    
    bus.on('turn:thinking' as any, (event: unknown) => {
      const e = event as Record<string, unknown>
      const payload = (e?.payload ?? e) as TurnThinkingEvent
      const sessionId = payload?.sessionId
      const token = payload?.token
      if (sessionId && token) {
        const state = sessionArchiveStates.get(sessionId) ?? { thinkingBlocks: [], toolCalls: [] }
        state.thinkingBlocks.push(token)
        sessionArchiveStates.set(sessionId, state)
      }
    })

    bus.on('turn:tool_call' as any, (event: unknown) => {
      const e = event as Record<string, unknown>
      const payload = (e?.payload ?? e) as TurnToolCallEvent
      const sessionId = payload?.sessionId
      const tool = payload?.tool
      const input = payload?.input
      if (sessionId && tool) {
        const state = sessionArchiveStates.get(sessionId) ?? { thinkingBlocks: [], toolCalls: [] }
        state.toolCalls.push({ name: tool, input })
        sessionArchiveStates.set(sessionId, state)
      }
    })

    bus.on('turn:tool_result' as any, (event: unknown) => {
      const e = event as Record<string, unknown>
      const payload = (e?.payload ?? e) as TurnToolResultEvent
      const sessionId = payload?.sessionId
      const result = payload?.result
      const isError = payload?.isError
      if (sessionId) {
        const state = sessionArchiveStates.get(sessionId)
        if (state && state.toolCalls.length > 0) {
          const lastCall = state.toolCalls[state.toolCalls.length - 1]
          lastCall.output = result || '(no output)'
          lastCall.error = isError
        }
      }
    })
  }

  return async (ctx, next) => {
    // Initialize/clear state for this session at turn start
    const sessionId = ctx.session.id
    const state: SessionArchiveState = { thinkingBlocks: [], toolCalls: [] }
    sessionArchiveStates.set(sessionId, state)

    // Snapshot message count before the turn for incremental indexing
    turnContextMeta.set(ctx, { preIndexMsgCount: ctx.session.history.length })

    try {
      const result = await next()

      // OPTIMIZATION: Fire-and-forget archiving (don't block turn completion)
      try {
        const fullThinking = state.thinkingBlocks.length > 0 ? state.thinkingBlocks.join('') : undefined
        const extendedMemory = memory as IExtendedMemory

        if (typeof extendedMemory.archiveConversation === 'function') {
          // Archive conversation without awaiting
          extendedMemory.archiveConversation(
            sessionId,
            ctx.inbound.content,
            result.response,
            fullThinking,
            {
              model: result.model,
              tokensUsed: result.tokensUsed,
              durationMs: result.durationMs,
              toolCount: state.toolCalls.length,
            }
          ).catch((err: unknown) => {
            logger?.error('[MemoryMiddleware] Archive conversation failed', {
        operation: 'archive_conversation',
        message: err instanceof Error ? err.message : String(err),
        ...(err instanceof Error && err.stack ? { stack: err.stack } : {}),
      })
          })

          // Archive tool calls without awaiting
          if (state.toolCalls.length > 0 && typeof extendedMemory.archiveToolCall === 'function') {
            for (const toolCall of state.toolCalls) {
              extendedMemory.archiveToolCall(
                sessionId,
                toolCall.name,
                toolCall.input,
                toolCall.output,
                toolCall.error ? 'Error' : undefined,
                { turnContext: ctx.inbound.content.slice(0, 200) }
              ).catch((err: unknown) => {
                logger?.error('[MemoryMiddleware] Archive tool call failed', {
        operation: 'archive_tool_call',
        message: err instanceof Error ? err.message : String(err),
        ...(err instanceof Error && err.stack ? { stack: err.stack } : {}),
      })
              })
            }
          }
        } else {
          // Legacy fallback (also non-blocking)
          extendedMemory.store?.({
            type: 'conversation',
            content: `user: ${ctx.inbound.content}\nassistant: ${result.response}`,
            sessionId,
          }).catch(() => {})
        }
      } catch (err) {
        /* best-effort */
        logger?.error('[MemoryMiddleware] Archive setup failed', {
        operation: 'archive_setup',
        message: err instanceof Error ? err.message : String(err),
        ...(err instanceof Error && err.stack ? { stack: err.stack } : {}),
      })
      }

      // Incremental session indexing (best-effort, non-blocking)
      try {
        const extendedMemory = memory as IExtendedMemory
        if (typeof extendedMemory.indexIncremental === 'function') {
          const history = ctx.session.history
          // Index only new messages: the turn added at least 2 (user + assistant),
          // possibly more if tool calls were involved. We conservatively index
          // from the message *before* the current turn's user message.
          const meta = turnContextMeta.get(ctx)
          const preExistingCount = meta?.preIndexMsgCount ?? 0
          extendedMemory.indexIncremental(sessionId, history, preExistingCount)
        }
      } catch (err) {
        /* indexing failure must never break the turn */
        logger?.error('[MemoryMiddleware] Session index update failed', {
        operation: 'session_index_update',
        message: err instanceof Error ? err.message : String(err),
        ...(err instanceof Error && err.stack ? { stack: err.stack } : {}),
      })
      }

      return result
    } finally {
      // Clean up state for this session — guaranteed even if middleware throws
      sessionArchiveStates.delete(sessionId)
    }
  }
}

export function makeOrchestrationMiddleware(bus: IOrchestrationBus): TurnMiddleware {
  return async (ctx, next) => {
    const result = await next()
    try {
      const existing = bus.get(ctx.session.id)
      if (existing) bus.update(ctx.session.id, { progress: `turn complete — ${result.tokensUsed} tokens` })
    } catch { /* best-effort */ }
    return result
  }
}


export class TurnPipeline {
  private middlewares: TurnMiddleware[] = []

  // REMOVED: pendingInjections map deleted — optimizer steering never worked with SessionPipeline
  // Pending cancellation resolvers: sessionId → resolve() to trigger cancellation

  // A proxy field lets us hot-swap the context window implementation at
  // runtime (e.g. after the intelligence layer is wired) without rebuilding
  // the entire middleware chain.  The proxy captures `this` by reference so
  // calls always dispatch to the current `contextWindowImpl`.
  private contextWindowImpl: TurnMiddleware = contextWindowMiddleware
  private readonly contextWindowProxy: TurnMiddleware = (ctx, next) =>
    this.contextWindowImpl(ctx, next)
  private pendingCancelResolvers = new Map<string, () => void>()

  // Dialectic system for parallel thought processing
  private dialectic?: DialecticSystem

  // Subconscious for automatic context retrieval
  private subconscious?: any

  // Intelligence layer reference for tool handlers (e.g., think tool accessing Thinker)
  private intelligence?: any

  // Cross-session digest store
  private digestStore?: SessionDigestStore

  // OPTIMIZATION: Cached tool names to avoid repeated registry scans
  private cachedToolNames?: string[]
  private lastToolRegistrySize = 0

  // REMOVED: InjectionAggregator — deprecated. Now uses GlobalWorkspace or Thalamus.
  // GWT Global Workspace for injection assembly
  private globalWorkspace?: import('./intelligence/workspace/index.js').GlobalWorkspace

  // Radiance Loop: bidirectional GWT broadcast with surprise-gated observation
  private radianceLoop?: import('./intelligence/workspace/radiance-loop.js').RadianceLoop

  // Session locks for serializing per-session turn processing
  private _sessionLocks = new Map<string, Promise<unknown>>()

  constructor(
    private providers: Map<string, IProvider>,
    private sessions: SessionManager,
    private bus: IEventBus,
    private logger: ILogger,
    private memory?: IMemory,
    private orchestration?: IOrchestrationBus,
    private toolRegistry?: ToolRegistry,
    private toolExecutor?: ToolExecutor,
  ) {
    this.buildDefaultChain()
    this.setupDialecticListener()
    this.setupSessionCleanup()
  }

  /**
   * Clean up pending maps when sessions end to prevent unbounded growth.
   */
  private setupSessionCleanup(): void {
    this.bus.on('session:ended', (event) => {
        const sessionId = event?.sessionId
        if (sessionId) {
          // REMOVED: pendingInjections cleanup deleted
          this.pendingCancelResolvers.delete(sessionId)
        }
    })
  }

  /**
   * Set the intelligence layer reference for tool handlers.
   * This allows tools like 'think' to access Thinker for subagent spawning.
   * @param intelligence - The intelligence layer instance to wire up
   */
  setIntelligence(intelligence: any): void {
    this.intelligence = intelligence
    this.logger.info('Intelligence layer reference set')
  }

  /**
   * OPTIMIZATION: Get cached tool names to avoid repeated registry scans.
   * Invalidates cache when registry size changes.
   */
  private getToolNames(): string[] {
    const currentSize = this.toolRegistry?.list().length ?? 0
    if (!this.cachedToolNames || this.lastToolRegistrySize !== currentSize) {
      this.cachedToolNames = this.toolRegistry?.list().map(t => t.name) ?? []
      this.lastToolRegistrySize = currentSize
    }
    return this.cachedToolNames
  }

  /**
   * Get the intelligence layer reference.
   * @returns The wired intelligence layer instance, or undefined if not set
   */
  getIntelligence(): any {
    return this.intelligence
  }
  
  /**
   * REMOVED: Dialectic signal listener — InjectionAggregator deleted.
   * Dialectic signals now flow through GlobalWorkspace or Thalamus directly.
   */
  private setupDialecticListener(): void {
    // no-op — InjectionAggregator removed
  }
  
  /**
   * Set the dialectic system for parallel thought processing.
   * This is called after construction to avoid circular dependencies.
   * @param dialectic - The DialecticSystem instance to wire up
   */
  setDialectic(dialectic: DialecticSystem): void {
    this.dialectic = dialectic
    this.logger.debug('Dialectic system wired')
  }

  /**
   * Set the subconscious system for automatic context retrieval.
   * This is called after construction to avoid circular dependencies.
   * @param subconscious - The subconscious system instance to wire up
   */
  setSubconscious(subconscious: any): void {
    this.subconscious = subconscious
    this.logger.debug('Subconscious system wired')
  }

  /**
   * Set the SessionDigestStore for cross-session awareness injection.
   * @param store - The SessionDigestStore instance to wire up
   */
  setDigestStore(store: SessionDigestStore): void {
    this.digestStore = store
    this.logger.debug('SessionDigestStore wired')
  }

  /**
   * Hot-swap the context window strategy.
   * The middleware chain is already built; the proxy dispatches to this
   * implementation so the swap takes effect on the very next turn.
   * @param impl - A TurnMiddleware produced by IntelligentContextWindow.asMiddleware()
   */
  setContextWindow(impl: TurnMiddleware): void {
    this.contextWindowImpl = impl
    this.logger.info('Context window strategy updated')
  }

  private buildDefaultChain(): void {
    const chain: TurnMiddleware[] = [
      systemPromptMiddleware,
      this.contextWindowProxy,   // proxied — hot-swappable via setContextWindow()
      makeProviderMiddleware(this.providers, this.bus, this.logger, this.toolRegistry, this.toolExecutor),
    ]
    // OPTIMIZATION: Pass bus to enable listener-based event capture (no monkey-patching)
    if (this.memory) chain.push(makeMemoryMiddleware(this.memory, this.bus, this.logger))
    if (this.orchestration) chain.push(makeOrchestrationMiddleware(this.orchestration))
    this.middlewares = chain
  }

  /**
   * Prepend a middleware to the chain (runs before existing middlewares).
   * This is used by external subsystems (e.g., ContextManager) to inject
   * per-turn context without rebuilding the pipeline.
   * @param mw - The TurnMiddleware to prepend
   */
  prependMiddleware(mw: TurnMiddleware): void {
    if (!mw) return
    this.middlewares.unshift(mw)
  }

  /**
   * Insert a middleware at the specified index (0-based).
   * If index is out of range, the middleware is appended or prepended.
   * @param index - Position to insert at (0 = first)
   * @param mw - The TurnMiddleware to insert
   */
  insertMiddlewareAt(index: number, mw: TurnMiddleware): void {
    if (!mw) return
    const i = Math.max(0, Math.min(index, this.middlewares.length))
    this.middlewares.splice(i, 0, mw)
  }

  /**
   * Mount intelligence middlewares into the pipeline.
   * @param opts - Configuration for intelligence middlewares
   * @param opts.continuity - Continuity system for cold-start recovery
   */
  mountIntelligence(opts: {
    continuity?: {
      getRecent(id: string, limit?: number): Promise<Array<{ role: string; content: string }>>
      saveTurn(turn: { sessionId: string; role: string; content: string; tokensUsed?: number; model?: string }): Promise<void>
    }
  }): void {
    if (opts.continuity) this.middlewares.unshift(makeContinuityMiddleware(opts.continuity))
    // WHY: thinker middleware removed — background fire-and-forget cycle handles it
  }

  // REMOVED: injectOnNextTurn() deleted — optimizer steering never worked with SessionPipeline
  // REMOVED: getPendingInjection() deleted — was only called by InjectionAggregator which now returns null

  // REMOVED: setInjectionAggregator — InjectionAggregator deleted.
  // Use setGlobalWorkspace or Thalamus for injection assembly.

  /**
   * Set the Global Workspace for GWT-based injection.
   * When enabled, uses luminance-gated competition for context assembly.
   */
  setGlobalWorkspace(workspace: import('./intelligence/workspace/index.js').GlobalWorkspace, enable = true): void {
    this.globalWorkspace = workspace
    this.logger.debug('GlobalWorkspace wired', { enabled: enable })
  }

  setRadianceLoop(loop: import('./intelligence/workspace/radiance-loop.js').RadianceLoop): void {
    this.radianceLoop = loop
    this.logger.debug('RadianceLoop wired')
  }

  /**
   * Request cancellation of an in-flight processing turn (best-effort).
   * Returns true if a cancel resolver was found and triggered.
   */
  requestCancel(sessionId: string): boolean {
    const resolver = this.pendingCancelResolvers.get(sessionId)
    if (!resolver) return false
    try { resolver() } catch {}
    this.pendingCancelResolvers.delete(sessionId)
    this.logger.info(`Cancellation requested for ${sessionId.slice(-8)}`)
    return true
  }

  async process(inbound: InboundMessage): Promise<TurnResult> {
    // Serialize processing per-session to avoid concurrent provider requests for
    // the same session (which can trigger centralized provider dedup errors).
    const sessionKey = inbound.sessionId || `${inbound.channelId}:${inbound.senderId}`
    // OPTIMIZATION: Single lookup with nullish coalescing assignment
    const locks = this._sessionLocks

    const run = async (): Promise<TurnResult> => {
      // original process body starts here

      // When the inbound message carries a stable channel-scoped session ID (e.g.
      // "tg:12345"), use getOrCreateById so the session is stored and emitted under
      // that exact ID — this ensures that streaming token events (payload.sessionId)
      // can be routed back to the channel worker without a secondary lookup.
      // Extended session manager interface with getOrCreateById method
    interface ISessionManagerExtended {
      getOrCreateById(stableId: string, channelId: string, senderId: string): Session
      get(sessionId: string): Session | undefined
      getOrCreate(channelId: string, senderId: string): Session
    }
    const sessions = this.sessions as unknown as ISessionManagerExtended
    const session = inbound.sessionId
        ? 'getOrCreateById' in this.sessions
          ? sessions.getOrCreateById(inbound.sessionId, inbound.channelId, inbound.senderId)
          : sessions.get(inbound.sessionId) ?? sessions.getOrCreate(inbound.channelId, inbound.senderId)
        : sessions.getOrCreate(inbound.channelId, inbound.senderId)
  
      const userMsg: Message = inbound.attachments?.length
        ? {
          role: 'user',
          content: [
            ...inbound.attachments.map(att => ({
              type: 'image' as const,
              source: { type: 'base64' as const, media_type: att.mediaType, data: att.data },
            })) as unknown as ContentBlock[],
            { type: 'text' as const, text: inbound.content || '(image)' },
          ],
        }
        : { role: 'user', content: inbound.content }
  
      const ctx: TurnContext = {
        session,
        inbound,
        messages: [...session.history, userMsg],
        opts: {
          model: session.config.model ?? getModelSpec('main'),
          thinking: session.config.thinking,
          stream: true,
        },
      }

      // Cancellation controller for this session (best-effort). External callers
      // can trigger cancellation via requestCancel(sessionId). We expose both a
      // promise and the AbortSignal on ctx.opts so middleware/providers can
      // react to cancellation promptly.
      const _ac = new AbortController()
      this.pendingCancelResolvers.set(session.id, () => { try { _ac.abort() } catch {} })
      ctx.opts.signal = _ac.signal

      // OPTIMIZATION: Compute system message index once for all injections
      const sysIdx = ctx.messages.findIndex(m => m.role === 'system')
      const insertAt = sysIdx >= 0 ? sysIdx + 1 : 0

      // Batch all context injections into a single array rebuild
      let injections: Array<{ content: string; source: string }> = []

      // REMOVED: InjectionAggregator — deprecated. Now uses GlobalWorkspace or Thalamus.
      if (this.globalWorkspace) {
        // GWT path: workspace assembles from luminance-ranked signal slots
        injections = this.globalWorkspace.assemble(session.id)
        this.globalWorkspace.broadcast()
        this.globalWorkspace.tick()
      }
      // If no GlobalWorkspace, Thalamus handles injection assembly separately

      // Single array rebuild for all injections
      if (injections.length > 0) {
        ctx.messages = [
          ...ctx.messages.slice(0, insertAt),
          ...injections.map(i => ({ role: 'system' as const, content: i.content })),
          ...ctx.messages.slice(insertAt),
        ]

        // Persist injection ledger for forensic trace (trace)
        const archiveFn = this.memory?.archiveEvent?.bind(this.memory)
        if (archiveFn) {
          for (const inj of injections) {
            archiveFn('injection', inj.content, {
              sessionId: session.id,
              source: inj.source,
              turnTimestamp: Date.now(),
              category: 'injection',
            }).catch(err => {
              this.logger.debug('Failed to archive injection ledger entry', { error: String(err) })
            })
          }
        }
      }
  
      this.bus.emit({ type: 'turn:start', sessionId: session.id, message: inbound.content, timestamp: new Date() })

      const trace: TurnTrace = {
        id: `trace_${session.id}_${Date.now()}`,
        turnId: `turn_${Date.now()}`,
        sessionId: session.id,
        timestamp: Date.now(),
        input: {
          message: inbound.content,
          attachmentCount: inbound.attachments?.length ?? 0,
        },
        contextSnapshot: {
          historyMessageCount: session.history.length,
          injections: injections.map((injection): TraceInjectionPart => ({
            source: injection.source,
            content: injection.content,
            charCount: injection.content.length,
          })),
          retrievedMemories: [],
        },
        providerCall: {
          model: ctx.opts.model ?? '',
          tokensUsed: 0,
          durationMs: 0,
          toolCalls: [],
        },
        cognitiveSignals: [],
        // REMOVED: pendingInjections from InjectionAggregator — now empty array
        pendingInjections: [],
        response: {
          text: '',
        },
      }

      try {
        const traceMemory = this.memory as IMemory & TraceMemoryLike
        const archiveContext = traceMemory.getConversationWithThinking?.(session.id, 20) ?? []
        trace.contextSnapshot.retrievedMemories = archiveContext.slice(0, 5).map((entry: ArchiveEntry) => ({
          id: entry.id,
          type: entry.type,
          source: entry.source,
          summary: entry.analysis?.summary ?? entry.content.slice(0, 240),
        }))
      } catch (err) {
        this.logger.debug('Failed to collect trace archive context', { error: String(err) })
      }

      // Start dialectic processing in parallel (fire-and-forget, results emitted via events)
      // OR run synchronously and inject as assistant thoughts (if injectAsThoughts enabled)
      if (this.dialectic) {
        if (this.dialectic.injectAsThoughtsEnabled) {
          // Synchronous mode: run dialectic reasoning on this user message,
          // inject full Yang/Yin/Unity reasoning as an assistant message.
          // The model sees it as its own prior thoughts about the question.
          try {
            const thoughts = await this.dialectic.reasonAsThoughts(inbound.content, {
              signal: ctx.opts.signal,
            })
            if (thoughts) {
              // Find the last user message (the one we just appended) and insert
              // an assistant "thinking" message right before it
              const lastUserIdx = ctx.messages.length - 1 // the user message is always last
              ctx.messages = [
                ...ctx.messages.slice(0, lastUserIdx),
                { role: 'assistant' as const, content: thoughts },
                ctx.messages[lastUserIdx],
              ]
              this.logger.info('Injected dialectic thoughts as assistant message', {
                sessionId: session.id,
                thoughtChars: thoughts.length,
              })

              // Also record in the trace
              trace.contextSnapshot.injections.push({
                source: 'dialectic-thoughts',
                content: thoughts.slice(0, 500) + (thoughts.length > 500 ? '...' : ''),
                charCount: thoughts.length,
              })
            }
          } catch (err) {
            this.logger.debug('Dialectic thought injection failed (non-critical)', { error: String(err) })
          }
        } else {
          // Original async mode: fire-and-forget, results come via events
          this.dialectic.processTurn(
            session.id,
            `turn-${Date.now()}`,
            inbound.content,
            {
              recentMemories: [],
              availableTools: this.getToolNames(),
              sessionHistory: session.history,
            },
            { signal: ctx.opts.signal }
          ).catch(err => {
            this.logger.debug('Dialectic processing failed (non-critical)', { error: String(err) })
          })
        }
      }
  
      let idx = 0
      const dispatch = async (): Promise<TurnResult> => {
        if (idx >= this.middlewares.length) {
          return (ctx as unknown as Record<string, unknown>)['__result'] as TurnResult
            ?? { response: '', tokensUsed: 0, model: '', durationMs: 0 }
        }
        return this.middlewares[idx++](ctx, dispatch)
      }
  
      let result: TurnResult | undefined
      try {
        result = await dispatch()
        trace.providerCall.model = result.model
        trace.providerCall.tokensUsed = result.tokensUsed
        trace.providerCall.durationMs = result.durationMs
        trace.providerCall.toolCalls = (result.toolCalls ?? []).map((toolCall): TraceToolCall => ({
          name: toolCall.name,
          durationMs: toolCall.durationMs,
        }))
        trace.response.text = result.response

        // Store plain-text version in history (don't persist raw image bytes)
        const historyUserMsg: Message = { role: 'user', content: inbound.content || '(image)' }
        this.sessions.addTurn(session.id, historyUserMsg)
        this.sessions.addTurn(session.id, { role: 'assistant', content: result.response })
        this.sessions.save(session.id)

        let traceId: string | undefined
        if (this.memory?.archiveEvent) {
          try {
            const archived = await this.memory.archiveEvent('turn-trace', JSON.stringify(trace), {
              sessionId: session.id,
              category: 'trace',
              traceId: trace.id,
              turnId: trace.turnId,
              tags: ['trace', 'turn-trace'],
            })
            traceId = archived.id
          } catch (err) {
            this.logger.debug('Failed to archive turn trace', { error: String(err), sessionId: session.id })
          }
        }

        // GWT feedback: detect which workspace signals were incorporated in the response
        // Fire-and-forget — keyword matching shouldn't delay turn completion
        if (this.globalWorkspace && result.response) {
          const ws = this.globalWorkspace
          const resp = result.response
          queueMicrotask(() => {
            try { ws.processFeedback(resp) } catch { /* non-critical */ }
          })
        }

        // Radiance Loop is now triggered via the turn:end event bus listener
        // in boot-intelligence-post.ts, covering both legacy and session pipelines.

        this.bus.emit({ type: 'turn:end', sessionId: session.id, response: result.response, durationMs: result.durationMs, traceId })
      } catch (err) {
        // Ensure turn:end always fires so channels (e.g. Telegram) can finalize their stream
        const errorResponse = `Error processing request: ${String(err)}`
        const errorInfo: Record<string, unknown> = {
        operation: 'turn_dispatch',
        message: err instanceof Error ? err.message : String(err),
        sessionId: session.id,
        ...(err instanceof Error && err.stack ? { stack: err.stack } : {}),
      }
      this.logger.error('Turn dispatch failed', errorInfo)
        trace.response.text = errorResponse
        this.bus.emit({ type: 'turn:end', sessionId: session.id, response: errorResponse, durationMs: 0, traceId: trace.id })
        throw err
      } finally {
        try { this.pendingCancelResolvers.delete(session.id) } catch {}
      }

      return result as TurnResult
    }

    // OPTIMIZATION: Use nullish coalescing for cleaner lookup
    const prev = locks.get(sessionKey) ?? Promise.resolve()
    const promise = prev.then(() => run()).finally(() => {
      // WHY: single-threaded JS makes identity check atomic — no race conditions
      if (locks.get(sessionKey) === promise) locks.delete(sessionKey)
    })
    locks.set(sessionKey, promise)
    return promise
  }

}
