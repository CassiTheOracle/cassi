/**
 * @cassicore/spine — CassiCore attention context controller.
 *
 * Maintains one pure `ThalamusAttentionSession` (from `@cassicore/thalamus/attention` —
 * the OMP-agnostic attention kernel; the spine is the ONLY package that touches OMP) per
 * OMP session, and hooks the faithful 17.3.4 harness events:
 *
 *   - `message_end`   → observes bounded user/assistant/tool messages. A direct-user
 *                       message opens a new turn window (previous window's frozen plan
 *                       is dropped). Agent-attributed synthetic user messages are never
 *                       interpreted as direct-user goals.
 *   - `turn_start`    → records the turn index and starts the runtime candidate prefetch
 *                       (kernel `beginTurn` is deferred to the first `context` event so the
 *                       query is settled and the plan is frozen ONCE for the whole window).
 *   - `context`       → on the FIRST context event of the window, waits only up to the
 *                       configured short deadline for the prefetch, plans locally, and
 *                       freezes the plan for the window. `inject` mode inserts exactly
 *                       one synthetic, agent-attributed user-role packet immediately
 *                       before the latest direct-user message. The packet contains only
 *                       opaque planning IDs (never copied source text), and the canonical
 *                       direct-user instruction remains later and authoritative;
 *                       `observe`/`off` never modify provider context.
 *                       Runtime timeout/down NEVER blocks or throws — the plan is still
 *                       produced with source statuses marked unavailable. Only an
 *                       internal planner/render exception returns the original messages
 *                       unchanged (fail-open, once per window).
 *   - `turn_end`      → appends a text-free receipt (`appendEntry('cassi.context.plan', …)`)
 *                       once per completed turn and sends ID-only feedback
 *                       (`/v1/context/feedback`; no raw text) fire-and-forget.
 *   - `session.compacting` → contributes active compact context lines + ID-only
 *                       preserveData to the compaction entry.
 *   - `session_switch`/`session_branch`/`session_shutdown` → resets and drops attention
 *                       state so nothing leaks across sessions.
 *
 * `/cassi-context` command: `status|explain|mode <off|observe|inject>|pin <text>|
 * unpin <unitId>|reset`, answered through `ctx.ui.notify`.
 */
import { setTimeout as delay } from 'node:timers/promises'


import type {
  AgentMessage,
  AgentStartEvent,
  ContextEvent,
  ContextEventResult,
  ContextUsage,
  UserMessage,
  ExtensionAPI,
  ExtensionCommandContext,
  ExtensionContext,
  MessageEndEvent,
  SessionCompactingEvent,
  SessionSwitchEvent,
  TurnEndEvent,
  TurnStartEvent,
} from './oh-my-pi-types.js'
import type { ChannelClient } from './channel/client.js'
import {
  contextCandidateUnitId,
  ThalamusAttentionSession,
  type AttentionObservation,
  type ContextCandidate,
  type ContextFrame,
  type ContextPlan,
  type ContextPlanReceipt,
  type ContextSourceStatus,
  type FieldAdvisory,
  type ThalamusAttentionConfig,
  type ThalamusMode,
} from '@cassicore/thalamus/attention'

/** Controller options. Mode + the first-context wait deadline live HERE (SpineOptions), not in the kernel config. */
export interface ContextControllerOptions {
  /** Attention mode: `off` (no-op), `observe` (build attention, never touch provider context), `inject` (insert one synthetic agent packet per turn). Default `'observe'`. */
  mode?: ThalamusMode
  /** Short deadline (ms) waited on the FIRST context event for the prefetched candidates. Default 75. */
  candidateWaitMs?: number
  /** Candidate prefetch limit. Default 5. */
  candidateLimit?: number
  /** Ask the runtime for a cached field shadow with the candidates. Default false. */
  includeFieldShadow?: boolean
  /** Bound on observed user/assistant text characters. Default 4000. */
  maxObserveChars?: number
  /** Bound on observed tool-result text characters. Default 2000. */
  maxToolResultChars?: number
  /** Attention-kernel config (token budget etc.). */
  kernel?: ThalamusAttentionConfig
}

interface PrefetchResult {
  candidates: ContextCandidate[]
  sources: ContextSourceStatus[]
  fieldAdvisory: FieldAdvisory | null
}

/** One user-prompt window: plan frozen across tool calls until the next user message. */
interface TurnWindow {
  turnId: number
  query: string
  /** Buffered user observation — flushed to the kernel right after `beginTurn` so it carries the turn's id. */
  pendingUser: AttentionObservation | null
  frozenPlan: ContextPlan | null
  planFailed: boolean
  planError: string | null
  packetContent: string | null
  packetTimestamp: number | null
  beginTurnDone: boolean
  prefetch: Promise<PrefetchResult> | null
  candidateIds: string[]
  /** Canonical non-user tail observed once when this window is initialized. */
  tailObserved: boolean
  candidateUnitIds: Map<string, string>
  /** Identity of the direct-user message that opened this window. */
  userSourceId: string | null
  /** turnIndexes already receipted+fed back (one receipt/feedback per turn). */
  settledTurns: Set<number>
}

interface SessionState {
  attention: ThalamusAttentionSession
  window: TurnWindow
  /** Predicted OMP turn index, available before the next context transform. */
  nextTurnIndex: number
  /** Set by agent_start so a same-text prompt still opens a fresh window. */
  agentRunStarted: boolean
}

const DEFAULT_MODE: ThalamusMode = 'observe'
const DEFAULT_CANDIDATE_WAIT_MS = 75
const DEFAULT_CANDIDATE_LIMIT = 5
const DEFAULT_MAX_OBSERVE_CHARS = 4000
const DEFAULT_MAX_TOOL_RESULT_CHARS = 2000

function emptyWindow(): TurnWindow {
  return {
    turnId: 0,
    query: '',
    pendingUser: null,
    frozenPlan: null,
    planFailed: false,
    planError: null,
    packetContent: null,
    packetTimestamp: null,
    beginTurnDone: false,
    prefetch: null,
    tailObserved: false,
    candidateIds: [],
    candidateUnitIds: new Map(),
    userSourceId: null,
    settledTurns: new Set(),
  }
}

function truncate(text: string, max: number): string {
  if (max <= 0 || text.length <= max) return text
  return `${text.slice(0, max)}…`
}

/** Extract the plain-text content of a message (string content or `text` blocks). */
export function messageText(msg: AgentMessage): string {
  if (typeof msg.content === 'string') return msg.content
  if (Array.isArray(msg.content)) {
    const parts: string[] = []
    for (const block of msg.content) {
      if (block && typeof block === 'object' && block.type === 'text' && typeof block.text === 'string') {
        parts.push(block.text)
      }
    }
    return parts.join('\n')
  }
  return ''
}

function messageId(msg: AgentMessage): string {
  if ('id' in msg && typeof msg.id === 'string' && msg.id) return msg.id
  return `${msg.role}-${msg.timestamp}`
}

const ATTENTION_PACKET_PREFIX = 'CASSI ATTENTION —'

function isAttentionPacket(message: AgentMessage): boolean {
  return message.role === 'user'
    && message.synthetic === true
    && message.attribution === 'agent'
    && messageText(message).startsWith(ATTENTION_PACKET_PREFIX)
}

function isDirectUserMessage(message: AgentMessage | undefined): boolean {
  if (!message) return false
  if (message.role === 'user') {
    return message.synthetic !== true && message.attribution !== 'agent'
  }
  // OMP turns user-invoked skill/custom prompts into provider user messages.
  // Preserve their provenance before that conversion so they open a fresh window.
  return message.role === 'custom' && message.attribution === 'user'
}

/** Last direct-user message in provider-bound history (query/new-window source). */
function lastDirectUserMessage(messages: AgentMessage[]): AgentMessage | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i]
    if (isDirectUserMessage(message) && messageText(message)) return message
  }
  return undefined
}

/**
 * Per-OMP-session attention controller. Construct once per extension load and call
 * `register()` to wire the event handlers + the `/cassi-context` command.
 */
export class ContextController {
  private readonly pi: ExtensionAPI
  private readonly client: ChannelClient
  private readonly candidateWaitMs: number
  private readonly candidateLimit: number
  private readonly includeFieldShadow: boolean
  private readonly maxObserveChars: number
  private readonly maxToolResultChars: number
  private readonly kernelConfig: ThalamusAttentionConfig | undefined
  private mode: ThalamusMode
  private readonly sessions = new Map<string, SessionState>()
  private lastSessionId: string | undefined

  constructor(pi: ExtensionAPI, client: ChannelClient, options: ContextControllerOptions = {}) {
    this.pi = pi
    this.client = client
    this.mode = options.mode ?? DEFAULT_MODE
    const candidateWaitMs = options.candidateWaitMs
    this.candidateWaitMs = typeof candidateWaitMs === 'number' && Number.isFinite(candidateWaitMs)
      ? Math.min(1_000, Math.max(0, Math.floor(candidateWaitMs)))
      : DEFAULT_CANDIDATE_WAIT_MS
    const candidateLimit = options.candidateLimit
    this.candidateLimit = typeof candidateLimit === 'number' && Number.isFinite(candidateLimit)
      ? Math.min(20, Math.max(1, Math.floor(candidateLimit)))
      : DEFAULT_CANDIDATE_LIMIT
    this.includeFieldShadow = options.includeFieldShadow ?? false
    const maxObserveChars = options.maxObserveChars
    this.maxObserveChars = typeof maxObserveChars === 'number' && Number.isFinite(maxObserveChars)
      ? Math.min(16_000, Math.max(128, Math.floor(maxObserveChars)))
      : DEFAULT_MAX_OBSERVE_CHARS
    const maxToolResultChars = options.maxToolResultChars
    this.maxToolResultChars = typeof maxToolResultChars === 'number' && Number.isFinite(maxToolResultChars)
      ? Math.min(8_000, Math.max(128, Math.floor(maxToolResultChars)))
      : DEFAULT_MAX_TOOL_RESULT_CHARS
    this.kernelConfig = options.kernel
  }

  get currentMode(): ThalamusMode { return this.mode }

  /** Wire all event handlers + the `/cassi-context` command onto the extension API. */
  register(): void {
    const pi = this.pi
    pi.on('agent_start', (_e: AgentStartEvent, ctx: ExtensionContext) => this.handleAgentStart(ctx))
    pi.on('message_end', (e: MessageEndEvent, ctx: ExtensionContext) => this.handleMessageEnd(e, ctx))
    pi.on('turn_start', (e: TurnStartEvent, ctx: ExtensionContext) => this.handleTurnStart(e, ctx))
    pi.on('context', (e: ContextEvent, ctx: ExtensionContext) => this.handleContext(e, ctx))
    pi.on('turn_end', (e: TurnEndEvent, ctx: ExtensionContext) => this.handleTurnEnd(e, ctx))
    pi.on('session.compacting', (e: SessionCompactingEvent, ctx: ExtensionContext) => this.handleCompacting(e, ctx))
    pi.on('session_start', (_e, ctx: ExtensionContext) => { this.lastSessionId = ctx.sessionManager.getSessionId() })
    pi.on('session_switch', (e: SessionSwitchEvent, ctx: ExtensionContext) => this.handleSwitch(e, ctx))
    pi.on('session_branch', (_e, ctx: ExtensionContext) => {
      // OMP may mint the branched session id before emitting this event. Drop both
      // the abandoned leaf and the new leaf's empty/stale state, then rehydrate
      // exclusively from the next canonical branch context.
      const currentSessionId = ctx.sessionManager.getSessionId()
      if (this.lastSessionId && this.lastSessionId !== currentSessionId) this.dropSession(this.lastSessionId)
      this.dropSession(currentSessionId)
      this.lastSessionId = currentSessionId
    })
    pi.on('session_shutdown', () => this.handleShutdown())
    pi.registerCommand('cassi-context', {
      description: 'CassiCore attention context: status|explain|mode <off|observe|inject>|pin <text>|unpin <unitId>|reset',
      handler: (args: string, ctx: ExtensionCommandContext) => this.handleCommand(args, ctx),
    })
  }

  // ── event handlers ─────────────────────────────────────────────────────────

  handleMessageEnd(e: MessageEndEvent, ctx: ExtensionContext): void {
    if (this.mode === 'off') return
    const msg = e.message
    if (!msg || typeof msg.role !== 'string') return
    const st = this.stateFor(ctx)
    if (isDirectUserMessage(msg)) {
      const text = truncate(messageText(msg), this.maxObserveChars)
      const w = st.window
      // OMP transforms provider context before emitting the input message_end.
      // That post-transform event belongs to the already-frozen window.
      if (w.frozenPlan && w.settledTurns.size === 0 && text === w.query) {
        st.attention.observe({
          type: 'user',
          turnId: w.turnId,
          sourceId: messageId(msg),
          text,
          timestamp: msg.timestamp,
        })
      } else {
        this.openWindow(st, msg)
      }
      return
    }
    this.observeMessage(st, ctx, msg)
  }

  handleAgentStart(ctx: ExtensionContext): void {
    if (this.mode === 'off') return
    // An OMP agent run starts before its first context transform and restarts
    // turn indices. Drop only the frozen per-window plan: semantic units remain
    // session-scoped, while a compacted/rewritten history can never receive a
    // stale packet or inherit receipt deduplication from the prior run.
    const st = this.sessions.get(ctx.sessionManager.getSessionId())
    if (!st) return
    st.nextTurnIndex = 0
    st.agentRunStarted = true
    st.window = emptyWindow()
    st.window.turnId = 0
  }

  handleTurnStart(e: TurnStartEvent, ctx: ExtensionContext): void {
    if (this.mode === 'off') return
    const st = this.stateFor(ctx)
    st.nextTurnIndex = e.turnIndex
    if (!st.window.beginTurnDone) st.window.turnId = e.turnIndex
    // Start the candidate prefetch as early as possible — now that the turn id is
    // known, the request correlates with the plan + feedback. No-op when a prefetch
    // is already in flight (tool-call rounds fire turn_start repeatedly).
    if (!st.window.prefetch && st.window.query) this.prefetch(st, ctx)
  }

  /** The meat: plan once per window, freeze it, inject at most one packet in `inject` mode. */
  async handleContext(e: ContextEvent, ctx: ExtensionContext): Promise<ContextEventResult | void> {
    if (this.mode === 'off') return undefined
    try {
      const st = this.stateFor(ctx)
      let w = st.window
      const messages = e.messages ?? []
      const canonicalMessages = messages.filter(message => !isAttentionPacket(message))
      const directUser = lastDirectUserMessage(canonicalMessages)
      const canonicalQuery = truncate(directUser ? messageText(directUser) : '', this.maxObserveChars)
      const directUserId = directUser ? messageId(directUser) : null

      // Real OMP order is context transform → turn_start → input message_end, and
      // OMP may place file/custom messages after the direct user. Use the latest
      // direct-user identity plus agent_start—not the array tail—to distinguish a
      // new prompt from repeated context transforms inside one tool loop.
      if (
        directUser
        && canonicalQuery
        && (
          !w.query
          || (w.beginTurnDone && (
            st.agentRunStarted
            || directUserId !== w.userSourceId
            || canonicalQuery !== w.query
          ))
        )
      ) {
        this.openWindow(st, directUser)
        w = st.window
      }
      if (directUser) st.agentRunStarted = false

      if (!w.query) w.query = canonicalQuery

      if (!w.beginTurnDone) {
        st.attention.beginTurn(w.turnId, w.query)
        w.beginTurnDone = true
        if (w.pendingUser) {
          // Flush the buffered user observation with the settled turn id.
          st.attention.observe({ ...w.pendingUser, turnId: w.turnId })
          w.pendingUser = null
          this.observeNonUserContextTail(st, ctx, e.messages ?? [])
        } else {
          // Extension attach/session resume can begin without prior message_end events.
          // Rehydrate a bounded canonical tail; observation IDs make this idempotent.
          this.observeContextTail(st, ctx, e.messages ?? [], w.turnId)
        }
        w.tailObserved = true
        // Fallback: no turn_start fired before the first context event — prefetch now.
        if (!w.prefetch) this.prefetch(st, ctx)
      }

      // Context-hook mutations are ephemeral. Reuse the frozen plan and append the
      // exact same packet on every provider call in this user window.
      if (w.planFailed) return undefined
      if (w.frozenPlan) return this.packetResult(e, ctx, st, w)

      const pref = await this.awaitPrefetch(w)
      w.candidateIds = pref.candidates.map(c => c.id)
      w.candidateUnitIds = new Map(pref.candidates.map(candidate => [
        contextCandidateUnitId(candidate),
        candidate.id,
      ]))
      const usage: ContextUsage | undefined = ctx.getContextUsage?.()
      const frame: ContextFrame = {
        turnId: w.turnId,
        query: w.query,
        modelId: ctx.model?.id,
        contextTokens: usage?.tokens,
        contextWindow: usage?.contextWindow,
        maxPacketTokens: this.kernelConfig?.maxPacketTokens,
        sourceStatuses: pref.sources,
        fieldAdvisory: pref.fieldAdvisory ?? undefined,
      }

      let plan: ContextPlan
      try {
        plan = st.attention.plan(frame, pref.candidates)
      } catch (err) {
        this.markFailed(w, ctx, err)
        return undefined
      }
      w.frozenPlan = plan

      return this.packetResult(e, ctx, st, w)
    } catch (err) {
      // Any unexpected internal failure still fails OPEN: provider context unchanged.
      ctx.logger?.error?.(`cassi-context handler failed: ${String(err)}`)
      return undefined
    }
  }

  handleTurnEnd(e: TurnEndEvent, ctx: ExtensionContext): void {
    if (this.mode === 'off') return
    const st = this.stateFor(ctx)
    const w = st.window
    st.nextTurnIndex = Math.max(st.nextTurnIndex, e.turnIndex + 1)
    if (w.settledTurns.has(e.turnIndex)) return
    w.settledTurns.add(e.turnIndex)

    const plan = w.frozenPlan
    if (!plan) return
    let receipt: ContextPlanReceipt
    try {
      receipt = { ...st.attention.receipt(plan), turnId: e.turnIndex }
    } catch {
      this.sendFeedback(ctx, e.turnIndex, plan.id, this.includedCandidateIds(w, plan), 'error')
      return
    }
    // Text-free receipt — appended once per completed turn.
    this.pi.appendEntry('cassi.context.plan', receipt)
    this.sendFeedback(ctx, e.turnIndex, plan.id, this.includedCandidateIds(w, plan), w.planFailed ? 'error' : 'completed')
  }

  handleCompacting(e: SessionCompactingEvent, ctx: ExtensionContext): void {
    if (this.mode === 'off') return
    const st = this.stateFor(ctx)
    st.attention.observe({
      type: 'compaction',
      turnId: st.window.turnId,
      sourceId: 'session.compacting',
      timestamp: Date.now(),
    })
    if (this.mode !== 'inject') return

    // OMP keeps only the last non-empty `session.compacting` handler result, so
    // returning context/preserveData here could silently discard another extension's
    // compaction contract. Persist our text-free checkpoint separately instead.
    this.pi.appendEntry('cassi.context.compaction', {
      sessionId: ctx.sessionManager.getSessionId(),
      revision: st.attention.status().revision,
      turnId: st.window.turnId,
      latestPlanId: st.window.frozenPlan?.id ?? null,
      checkpoint: st.attention.compactContext(),
    })
  }

  handleSwitch(_e: SessionSwitchEvent, ctx: ExtensionContext): void {
    // The switch event fires AFTER the switch — ctx is the NEW session. Reset + drop the
    // session we came from so no attention state leaks across sessions.
    const old = this.lastSessionId
    if (old && old !== ctx.sessionManager.getSessionId()) {
      this.dropSession(old)
    }
    this.lastSessionId = ctx.sessionManager.getSessionId()
  }

  handleShutdown(): void {
    for (const st of this.sessions.values()) {
      try { st.attention.reset() } catch { /* best-effort */ }
    }
    this.sessions.clear()
    this.lastSessionId = undefined
  }

  /** Reset + drop the given session's attention state (also used by the `reset` command). */
  dropSession(sessionId: string): void {
    const st = this.sessions.get(sessionId)
    if (!st) return
    try { st.attention.reset() } catch { /* best-effort */ }
    this.sessions.delete(sessionId)
  }

  // ── internals ──────────────────────────────────────────────────────────────

  private stateFor(ctx: ExtensionContext): SessionState {
    const sessionId = ctx.sessionManager.getSessionId()
    this.lastSessionId = sessionId
    let st = this.sessions.get(sessionId)
    if (!st) {
      st = {
        attention: new ThalamusAttentionSession(sessionId, this.kernelConfig),
        window: emptyWindow(),
        nextTurnIndex: 0,
        agentRunStarted: true,
      }
      this.sessions.set(sessionId, st)
    }
    return st
  }

  private openWindow(st: SessionState, msg: AgentMessage): void {
    const w = st.window
    w.turnId = st.nextTurnIndex
    w.frozenPlan = null
    w.planFailed = false
    w.planError = null
    w.packetContent = null
    w.packetTimestamp = null
    w.beginTurnDone = false
    w.prefetch = null
    w.tailObserved = false
    w.candidateIds = []
    w.candidateUnitIds.clear()
    w.settledTurns.clear()
    w.userSourceId = messageId(msg)
    w.query = truncate(messageText(msg), this.maxObserveChars)
    w.pendingUser = {
      type: 'user',
      turnId: w.turnId,
      sourceId: messageId(msg),
      text: w.query,
      timestamp: msg.timestamp,
    }
    // Prefetch starts at turn_start (turn id known); the first-context fallback covers
    // windows without a turn_start.
  }

  private observeMessage(st: SessionState, _ctx: ExtensionContext, msg: AgentMessage): void {
    const w = st.window
    if (msg.role === 'assistant') {
      const text = truncate(messageText(msg), this.maxObserveChars)
      if (!text) return
      st.attention.observe({
        type: 'assistant',
        turnId: w.turnId,
        sourceId: messageId(msg),
        text,
        timestamp: msg.timestamp,
      })
    } else if (msg.role === 'toolResult') {
      const text = truncate(messageText(msg), this.maxToolResultChars)
      if (!text) return
      st.attention.observe({
        type: 'tool_result',
        turnId: w.turnId,
        sourceId: messageId(msg),
        text,
        timestamp: msg.timestamp,
        toolName: msg.toolName,
        toolCallId: msg.toolCallId,
        isError: msg.isError,
      })
    }
  }

  private prefetch(st: SessionState, ctx: ExtensionContext): void {
    const w = st.window
    if (!w.query) {
      w.prefetch = null
      return
    }
    const sessionId = ctx.sessionManager.getSessionId()
    w.prefetch = this.client.contextCandidates({
      sessionId,
      turnId: w.turnId,
      query: w.query,
      limit: this.candidateLimit,
      // Server-side search deadline mirrors the spine's short client-side wait (clamped to the runtime's [100, 10000] range).
      deadlineMs: Math.min(Math.max(this.candidateWaitMs, 100), 10_000),
      includeFieldShadow: this.includeFieldShadow,
    }, { timeoutMs: Math.max(25, this.candidateWaitMs + 25) }).then((res): PrefetchResult => ({
      candidates: res.candidates ?? [],
      sources: res.sources && res.sources.length > 0 ? res.sources : [{ source: 'mnemic', status: 'ready' }],
      fieldAdvisory: res.fieldAdvisory ?? null,
    })).catch((err): PrefetchResult => ({
      // Runtime down / network error — fail open: plan locally with sources unavailable.
      candidates: [],
      sources: [{ source: 'mnemic', status: 'offline', error: String(err) }],
      fieldAdvisory: null,
    }))
  }

  private async awaitPrefetch(w: TurnWindow): Promise<PrefetchResult> {
    if (!w.prefetch) {
      return { candidates: [], sources: [{ source: 'mnemic', status: 'offline', error: 'no prefetch' }], fieldAdvisory: null }
    }
    // Wait only to the configured short deadline on the FIRST context event.
    const result = await Promise.race<PrefetchResult | null>([
      w.prefetch,
      delay(this.candidateWaitMs, null),
    ])
    if (result === null) {
      return {
        candidates: [],
        sources: [{ source: 'mnemic', status: 'timeout', error: 'candidate wait deadline exceeded' }],
        fieldAdvisory: null,
      }
    }
    return result
  }

  private packetResult(
    e: ContextEvent,
    ctx: ExtensionContext,
    st: SessionState,
    w: TurnWindow,
  ): ContextEventResult | undefined {
    if (this.mode !== 'inject' || !w.frozenPlan) return undefined
    if (w.packetContent === null) {
      try {
        w.packetContent = st.attention.render(w.frozenPlan)
      } catch (err) {
        this.markFailed(w, ctx, err)
        return undefined
      }
    }
    if (!w.packetContent) return undefined
    if ((e.messages ?? []).some(isAttentionPacket)) return undefined
    w.packetTimestamp ??= Date.now()
    const packet: UserMessage = {
      role: 'user',
      content: w.packetContent,
      synthetic: true,
      attribution: 'agent',
      timestamp: w.packetTimestamp,
    }
    const messages = e.messages ?? []
    let insertionIndex = messages.length
    for (let i = messages.length - 1; i >= 0; i--) {
      if (isDirectUserMessage(messages[i])) {
        insertionIndex = i
        break
      }
    }
    return {
      messages: [
        ...messages.slice(0, insertionIndex),
        packet,
        ...messages.slice(insertionIndex),
      ],
    }
  }
  private observeContextTail(
    st: SessionState,
    ctx: ExtensionContext,
    messages: AgentMessage[],
    turnId: number,
  ): void {
    for (const msg of messages.slice(-12)) {
      if (isDirectUserMessage(msg)) {
        const text = truncate(messageText(msg), this.maxObserveChars)
        if (text) {
          st.attention.observe({
            type: 'user',
            turnId,
            sourceId: messageId(msg),
            text,
            timestamp: msg.timestamp,
          })
        }
      } else {
        this.observeMessage(st, ctx, msg)
      }
    }
  }

  /** Rehydrate native assistant/tool evidence beside an already-buffered user goal. */
  private observeNonUserContextTail(st: SessionState, ctx: ExtensionContext, messages: AgentMessage[]): void {
    for (const msg of messages.slice(-12)) {
      if (!isDirectUserMessage(msg)) this.observeMessage(st, ctx, msg)
    }
  }

  private markFailed(w: TurnWindow, ctx: ExtensionContext, err: unknown): void {
    w.planFailed = true
    w.planError = String(err)
    ctx.logger?.error?.(`cassi-context plan/render failed: ${String(err)}`)
  }

  /** Runtime candidate IDs the frozen plan actually referenced (ID-only). */
  private includedCandidateIds(w: TurnWindow, plan: ContextPlan): string[] {
    const ids = new Set<string>()
    for (const item of plan.items) {
      const candidateId = w.candidateUnitIds.get(item.unitId)
      if (candidateId) ids.add(candidateId)
    }
    return [...ids]
  }

  private sendFeedback(
    ctx: ExtensionContext,
    turnIndex: number,
    planId: string,
    includedCandidateIds: string[],
    outcome: 'completed' | 'error' | 'unknown',
  ): void {
    const sessionId = ctx.sessionManager.getSessionId()
    // Fire-and-forget: advisory, never a same-turn critical dependency.
    void this.client.contextFeedback({
      sessionId,
      turnId: turnIndex,
      planId,
      includedCandidateIds,
      outcome,
    }, { timeoutMs: 250 }).catch(() => { /* best-effort */ })
  }

  // ── /cassi-context command ────────────────────────────────────────────────

  private handleCommand(args: string, ctx: ExtensionCommandContext): void {
    const notify = (m: string, type?: 'info' | 'warning' | 'error') => ctx.ui?.notify?.(m, type)
    const [verb, ...rest] = args.trim().split(/\s+/)
    switch (verb) {
      case 'status': {
        const s = this.stateFor(ctx as ExtensionContext).attention.status()
        notify(`cassi-context: mode=${this.mode} session=${s.sessionId} turn=${s.turnId ?? '-'} units=${s.units} active=${s.active} resolved=${s.resolved} pinned=${s.pinned} latestPlan=${s.latestPlanId ?? '-'}`)
        break
      }
      case 'explain': {
        const plan = this.stateFor(ctx as ExtensionContext).window.frozenPlan
        if (!plan) {
          notify('cassi-context: no frozen plan for the current turn', 'info')
          break
        }
        const lines = plan.items.map(i => `- [${i.kind}/${i.authority}] ${i.unitId}: ${i.reason} (~${i.estimatedTokens}t)`)
        notify(`cassi-context: plan ${plan.id} budget=${plan.budgetTokens}t estimated=${plan.estimatedTokens}t omitted=${plan.omitted}\n${lines.join('\n') || '(no items)'}`)
        break
      }
      case 'mode': {
        const m = rest[0]
        if (m !== 'off' && m !== 'observe' && m !== 'inject') {
          notify('cassi-context: mode requires off|observe|inject', 'warning')
          break
        }
        this.mode = m
        notify(`cassi-context: mode set to ${m}`, 'info')
        break
      }
      case 'pin': {
        const text = rest.join(' ').trim()
        if (!text) {
          notify('cassi-context: pin requires text', 'warning')
          break
        }
        const st = this.stateFor(ctx as ExtensionContext)
        const unitId = st.attention.pin(st.window.turnId, truncate(text, this.maxObserveChars))
        notify(`cassi-context: pinned ${unitId}`)
        break
      }
      case 'unpin': {
        const unitId = rest[0]
        if (!unitId) {
          notify('cassi-context: unpin requires a unit id', 'warning')
          break
        }
        const ok = this.stateFor(ctx as ExtensionContext).attention.unpin(unitId)
        notify(ok ? `cassi-context: unpinned ${unitId}` : `cassi-context: no unit ${unitId}`, ok ? 'info' : 'warning')
        break
      }
      case 'reset': {
        this.dropSession(ctx.sessionManager.getSessionId())
        notify('cassi-context: attention reset', 'info')
        break
      }
      default:
        notify(`cassi-context: unknown verb '${verb ?? ''}' — status|explain|mode <off|observe|inject>|pin <text>|unpin <unitId>|reset`, 'warning')
    }
  }
}

/** Register the context controller on the extension API (called by the default factory). */
export function registerContextController(
  pi: ExtensionAPI,
  client: ChannelClient,
  options: ContextControllerOptions = {},
): ContextController {
  const controller = new ContextController(pi, client, options)
  controller.register()
  return controller
}
