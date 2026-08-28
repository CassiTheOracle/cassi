/**
 * ThinkerSession — Persistent parallel thinking partner for the main agent.
 *
 * Runs a persistent session via the copilot-sdk provider. The main
 * agent communicates with it through the collect_thoughts tool. The Thinker
 * independently handles research, planning, analysis, and memory retrieval.
 *
 * Architecture:
 *   - Event-driven priority queue processes work items asynchronously
 *   - Provider session stays alive across iterations
 *   - Output buffer collects Thinker responses for delivery on next tool call
 *   - Proactive findings inject into the main agent's system prompt
 *
 * Queue priorities (highest first):
 *   1. agent-thought  — Direct thoughts from collect_thoughts calls
 *   2. urgent-event   — High-confidence dialectic signals, anomalies
 *   3. proactive       — Periodic research, memory surfacing
 *   4. background      — Low-priority learnings, opportunities
 *
 * Phase 1: Core loop (queue + thought exchange + buffer)
 * Phase 2: Scoped tool access (read FS + write intelligence)
 * Phase 3: Proactive event-driven work
 * Phase 4: Context management — tracks SDK context pressure, adjusts queue
 *          behavior to skip low-priority items when context is filling up,
 *          and surfaces health metrics through getStats() and bus events.
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import { generateShortId } from '@cassicore/utils'
import {
  buildThinkerSdkTools,
  createToolCallTracker,
  type ThinkerToolProvider,
  type ThinkerSdkTool,
  type ToolCallTracker,
} from './thinker-tools.js'
import {
  ThinkerEventAdapter,
  type ThinkerEventAdapterConfig,
} from './thinker-event-adapter.js'

/** Priority levels for queue items (lower number = higher priority) */
export enum QueuePriority {
  AGENT_THOUGHT = 0,
  URGENT_EVENT = 1,
  PROACTIVE = 2,
  BACKGROUND = 3,
}

/** Work item in the Thinker's priority queue */
export interface ThinkerQueueItem {
  id: string
  priority: QueuePriority
  type: 'agent-thought' | 'urgent-event' | 'proactive' | 'background'
  content: string
  /** Original thought step metadata (for agent-thought items) */
  stepMeta?: {
    step: number
    estimatedSteps: number
    isRevision: boolean
    branchId: string
  }
  /** Timestamp when this item was enqueued */
  enqueuedAt: number
}

/** Buffered response from the Thinker */
export interface ThinkerResponse {
  id: string
  /** The queue item this responds to */
  requestId: string
  requestType: ThinkerQueueItem['type']
  /** The Thinker's response text */
  content: string
  /** Model used for this response */
  model?: string
  /** Tokens consumed */
  tokensUsed?: number
  /** Processing time in ms */
  durationMs: number
  timestamp: number
}

/** Accumulated context health state for the Thinker's persistent SDK session. */
export interface ThinkerContextHealth {
  /** Maximum token count for the model's context window (0 if unknown) */
  tokenLimit: number
  /** Current number of tokens in the context window */
  currentTokens: number
  /** Fill level as a fraction (0.0-1.0) */
  fillLevel: number
  /** Current number of messages in the conversation */
  messagesLength: number
  /** Total number of compaction events across session lifetime */
  compactionCount: number
  /** Total number of truncation events across session lifetime */
  truncationCount: number
  /** Timestamp of the most recent compaction */
  lastCompactionAt?: number
  /** Timestamp of the most recent truncation */
  lastTruncationAt?: number
  /** Whether background compaction is currently in progress */
  isCompacting: boolean
  /** Total tokens recovered by compaction + truncation across session lifetime */
  totalTokensRecovered: number
}

/** Fill level thresholds that control which queue priorities are processed. */
const CONTEXT_PRESSURE_THRESHOLDS = {
  /** Above this, skip background-priority items */
  skipBackground: 0.70,
  /** Above this, also skip proactive-priority items */
  skipProactive: 0.85,
} as const

export interface ThinkerSessionConfig {
  /** Model to use for the Thinker session. */
  model: string
  /** Maximum items in the output buffer before oldest are evicted. Default: 20 */
  maxBufferSize: number
  /** Timeout for the first-call sync wait in ms. Default: 5000 */
  firstCallTimeoutMs: number
  /** Timeout per sendAndWait call in ms. Default: 30000 */
  turnTimeoutMs: number
  /** Whether the session is enabled */
  enabled: boolean
  /** Event adapter config (Phase 3: proactive event-driven work) */
  eventAdapter?: Partial<ThinkerEventAdapterConfig>
}

const DEFAULT_CONFIG: ThinkerSessionConfig = {
  model: 'copilot-sdk/gpt-5-mini',
  maxBufferSize: 20,
  firstCallTimeoutMs: 5_000,
  turnTimeoutMs: 30_000,
  enabled: true,
}

/**
 * Minimal interface for the SDK provider methods ThinkerSession needs.
 * Avoids importing the full CopilotSdkProvider (which depends on @github/copilot-sdk).
 */
export interface ThinkerSdkProvider {
  executeSdkTurn(
    sessionId: string,
    prompt: string,
    systemMessage: string,
    model?: string,
    onStream?: (text: string) => void,
  ): Promise<{ response: string; tokensUsed?: number; model?: string; durationMs?: number; contextHealth?: TurnContextHealth }>

  /**
   * Execute a turn with scoped tools instead of the full bridge.
   * The session persists across calls (unlike executeStandaloneTurn which destroys it).
   * On first call, creates the session with the given tools.
   * On subsequent calls, reuses the existing session (tools parameter used only for creation).
   */
  executeScopedTurn?(
    sessionId: string,
    prompt: string,
    systemMessage: string,
    tools: ThinkerSdkTool[],
    model?: string,
  ): Promise<{ response: string; tokensUsed?: number; model?: string; durationMs?: number; contextHealth?: TurnContextHealth }>

  executePersistentScopedTurn?(
    sessionId: string,
    prompt: string,
    systemMessage: string,
    tools: ThinkerSdkTool[],
    model?: string,
  ): Promise<{ response: string; tokensUsed?: number; model?: string; durationMs?: number; contextHealth?: TurnContextHealth }>

  destroySession(sessionId: string): Promise<void>
}

/** Context health shape returned from TurnResult (matches the provider's return). */
type TurnContextHealth = {
  tokenLimit: number
  currentTokens: number
  fillLevel: number
  messagesLength: number
  isCompacting: boolean
  compactionsDuringTurn: number
  truncationsDuringTurn: number
  tokensRecoveredByCompaction: number
  tokensRemovedByTruncation: number
  compactionSummary?: string
}

export interface ThinkerSessionDeps {
  logger: ILogger
  bus?: IEventBus
  /** Stable provider/session key for this thinker instance */
  sessionKey?: string
  /** Host OpenCode session this thinker is attached to */
  hostSessionId?: string
  /** Lazy getter — the SDK provider may not be available at construction time */
  getProvider?: () => ThinkerSdkProvider | undefined
  /** Optional tool provider for scoped tool access (Phase 2) */
  toolProvider?: ThinkerToolProvider
  config?: Partial<ThinkerSessionConfig>
}


/** Simple priority queue backed by a sorted array */
class PriorityQueue<T extends { priority: number; enqueuedAt: number }> {
  private items: T[] = []
  private waiters: Array<(item: T) => void> = []

  push(item: T): void {
    this.items.push(item)
    this.items.sort((a, b) => a.priority - b.priority || a.enqueuedAt - b.enqueuedAt)

    if (this.waiters.length > 0) {
      const waiter = this.waiters.shift()!
      waiter(this.items.shift()!)
    }
  }

  /** Dequeue the highest-priority item, blocking if empty */
  dequeue(): Promise<T> {
    if (this.items.length > 0) {
      return Promise.resolve(this.items.shift()!)
    }
    return new Promise<T>(resolve => {
      this.waiters.push(resolve)
    })
  }

  get length(): number {
    return this.items.length
  }

  clear(): void {
    this.items = []
    this.waiters = []
  }
}


export class ThinkerSession {
  private readonly config: ThinkerSessionConfig
  private readonly logger: ILogger
  private readonly bus?: IEventBus
  private readonly getProvider?: () => ThinkerSdkProvider | undefined
  private readonly hostSessionId?: string

  private readonly queue = new PriorityQueue<ThinkerQueueItem>()
  private readonly outputBuffer: ThinkerResponse[] = []

  /** Resolvers waiting for new output to appear in the buffer */
  private bufferWaiters: Array<() => void> = []

  private running = false
  private processLoopPromise?: Promise<void>
  private readonly sessionId: string
  private iterationCount = 0
  private totalTokensUsed = 0
  private startedAt?: number

  private readonly systemPrompt: string

  /** Phase 2: Scoped tool access */
  private readonly toolProvider?: ThinkerToolProvider
  private readonly tracker?: ToolCallTracker
  private readonly sdkTools?: ThinkerSdkTool[]

  /** Phase 3: Event-driven proactive work */
  private eventAdapter?: ThinkerEventAdapter

  /** Phase 4: Context health tracking */
  private contextHealth: ThinkerContextHealth = {
    tokenLimit: 0,
    currentTokens: 0,
    fillLevel: 0,
    messagesLength: 0,
    compactionCount: 0,
    truncationCount: 0,
    isCompacting: false,
    totalTokensRecovered: 0,
  }
  /** Previous fill-level band for threshold-crossing detection */
  private lastPressureBand: 'low' | 'medium' | 'high' = 'low'

  constructor(deps: ThinkerSessionDeps) {
    this.config = { ...DEFAULT_CONFIG, ...deps.config }
    this.logger = deps.logger.child?.('thinker-session') ?? deps.logger
    this.bus = deps.bus
    this.getProvider = deps.getProvider
    this.hostSessionId = deps.hostSessionId
    this.sessionId = deps.sessionKey ?? `thinker-${generateShortId(8)}`
    this.toolProvider = deps.toolProvider

    if (this.toolProvider) {
      this.tracker = createToolCallTracker()
      this.sdkTools = buildThinkerSdkTools(this.toolProvider, this.logger, this.tracker)
      this.logger.info('ThinkerSession: scoped tools built', { toolCount: this.sdkTools.length })
    }

    this.systemPrompt = buildThinkerSystemPrompt(!!this.toolProvider)
  }

   /** Start the background processing loop */
  async start(): Promise<void> {
    if (this.running) return
    if (!this.config.enabled) {
      this.logger.info('ThinkerSession: disabled by config')
      return
    }

    this.running = true
    this.startedAt = Date.now()
    this.processLoopPromise = this.processLoop()

    if (this.bus) {
      this.eventAdapter = new ThinkerEventAdapter({
        bus: this.bus,
        logger: this.logger,
        session: this,
        toolProvider: this.toolProvider,
        hostSessionId: this.hostSessionId,
        config: this.config.eventAdapter,
      })
      this.eventAdapter.start()
    }

    this.logger.info('ThinkerSession: started', {
      sessionId: this.sessionId.slice(-8),
      model: this.config.model,
      hasTools: !!this.sdkTools,
      hasEventAdapter: !!this.eventAdapter,
    })
  }

   /** Stop the processing loop and clean up */
  async stop(): Promise<void> {
    if (!this.running) return
    this.running = false
    this.queue.clear()
    this.bufferWaiters = []

    this.eventAdapter?.stop()
    this.eventAdapter = undefined

    const provider = this.getProvider?.()
    if (provider) {
      try {
        await provider.destroySession(this.sessionId)
      } catch (err) {
        this.logger.warn('ThinkerSession: failed to destroy SDK session', { error: String(err) })
      }
    }

    this.logger.info('ThinkerSession: stopped', {
      sessionId: this.sessionId.slice(-8),
      iterations: this.iterationCount,
      totalTokens: this.totalTokensUsed,
      uptimeMs: this.startedAt ? Date.now() - this.startedAt : 0,
    })
  }

  get isRunning(): boolean {
    return this.running
  }

  /**
   * Enqueue a thought from the main agent (highest priority).
   * Returns the queue item ID for tracking.
   */
  enqueueThought(
    thought: string,
    stepMeta?: ThinkerQueueItem['stepMeta'],
  ): string {
    const item: ThinkerQueueItem = {
      id: `tq-${generateShortId(6)}`,
      priority: QueuePriority.AGENT_THOUGHT,
      type: 'agent-thought',
      content: thought,
      stepMeta,
      enqueuedAt: Date.now(),
    }
    this.queue.push(item)
    this.logger.debug('ThinkerSession: thought enqueued', {
      itemId: item.id,
      step: stepMeta?.step,
      queueDepth: this.queue.length,
    })
    return item.id
  }

  /**
   * Enqueue an event-driven work item.
   */
  enqueueEvent(
    type: 'urgent-event' | 'proactive' | 'background',
    content: string,
  ): string {
    const priority = type === 'urgent-event' ? QueuePriority.URGENT_EVENT
      : type === 'proactive' ? QueuePriority.PROACTIVE
      : QueuePriority.BACKGROUND

    const item: ThinkerQueueItem = {
      id: `tq-${generateShortId(6)}`,
      priority,
      type,
      content,
      enqueuedAt: Date.now(),
    }
    this.queue.push(item)
    return item.id
  }

  /**
   * Drain all buffered responses. Returns and clears the buffer.
   */
  drainBuffer(): ThinkerResponse[] {
    const items = [...this.outputBuffer]
    this.outputBuffer.length = 0
    return items
  }

  /**
   * Wait for at least one response to appear in the buffer, up to timeoutMs.
   * Used for the first-call sync wait.
   */
  async waitForResponse(timeoutMs?: number): Promise<boolean> {
    const timeout = timeoutMs ?? this.config.firstCallTimeoutMs
    if (this.outputBuffer.length > 0) return true

    return new Promise<boolean>(resolve => {
      const timer = setTimeout(() => {
        const idx = this.bufferWaiters.indexOf(waiter)
        if (idx >= 0) this.bufferWaiters.splice(idx, 1)
        resolve(this.outputBuffer.length > 0)
      }, timeout)

      const waiter = () => {
        clearTimeout(timer)
        resolve(true)
      }
      this.bufferWaiters.push(waiter)
    })
  }

  /** Number of buffered responses ready for delivery */
  get bufferSize(): number {
    return this.outputBuffer.length
  }

   /** Session stats for observability */
  getStats(): {
    running: boolean
    sessionId: string
    iterations: number
    totalTokens: number
    queueDepth: number
    bufferSize: number
    uptimeMs: number
    hasTools: boolean
    contextHealth: ThinkerContextHealth
    eventAdapter?: ReturnType<ThinkerEventAdapter['getStats']>
  } {
    return {
      running: this.running,
      sessionId: this.sessionId,
      iterations: this.iterationCount,
      totalTokens: this.totalTokensUsed,
      queueDepth: this.queue.length,
      bufferSize: this.outputBuffer.length,
      uptimeMs: this.startedAt ? Date.now() - this.startedAt : 0,
      hasTools: !!this.sdkTools,
      contextHealth: { ...this.contextHealth },
      eventAdapter: this.eventAdapter?.getStats(),
    }
  }

  /**
   * Check if a queue item should be skipped due to high context pressure.
   * Higher-priority items (agent-thought, urgent-event) are never skipped.
   */
  private shouldSkipForContextPressure(item: ThinkerQueueItem): boolean {
    const fill = this.contextHealth.fillLevel
    if (fill <= 0) return false

    if (item.type === 'background' && fill > CONTEXT_PRESSURE_THRESHOLDS.skipBackground) {
      return true
    }
    if (item.type === 'proactive' && fill > CONTEXT_PRESSURE_THRESHOLDS.skipProactive) {
      return true
    }
    return false
  }

  /**
   * Update accumulated context health from a turn result's contextHealth snapshot.
   * Emits bus events when fill-level thresholds are crossed.
   */
  private updateContextHealth(turnHealth: {
    tokenLimit: number
    currentTokens: number
    fillLevel: number
    messagesLength: number
    isCompacting: boolean
    compactionsDuringTurn: number
    truncationsDuringTurn: number
    tokensRecoveredByCompaction: number
    tokensRemovedByTruncation: number
    compactionSummary?: string
  }): void {
    this.contextHealth.tokenLimit = turnHealth.tokenLimit
    this.contextHealth.currentTokens = turnHealth.currentTokens
    this.contextHealth.fillLevel = turnHealth.fillLevel
    this.contextHealth.messagesLength = turnHealth.messagesLength
    this.contextHealth.isCompacting = turnHealth.isCompacting

    if (turnHealth.compactionsDuringTurn > 0) {
      this.contextHealth.compactionCount += turnHealth.compactionsDuringTurn
      this.contextHealth.lastCompactionAt = Date.now()
      this.contextHealth.totalTokensRecovered += turnHealth.tokensRecoveredByCompaction
    }

    if (turnHealth.truncationsDuringTurn > 0) {
      this.contextHealth.truncationCount += turnHealth.truncationsDuringTurn
      this.contextHealth.lastTruncationAt = Date.now()
      this.contextHealth.totalTokensRecovered += turnHealth.tokensRemovedByTruncation
    }

    const newBand: 'low' | 'medium' | 'high' =
      turnHealth.fillLevel > CONTEXT_PRESSURE_THRESHOLDS.skipProactive ? 'high'
      : turnHealth.fillLevel > CONTEXT_PRESSURE_THRESHOLDS.skipBackground ? 'medium'
      : 'low'

    if (newBand !== this.lastPressureBand) {
      this.lastPressureBand = newBand
      if (this.bus) {
        this.bus.emit({
          type: 'thinker:context:pressure' as any,
          sessionId: this.sessionId,
          band: newBand,
          fillLevel: turnHealth.fillLevel,
          tokenLimit: turnHealth.tokenLimit,
          currentTokens: turnHealth.currentTokens,
          timestamp: new Date(),
        })
      }
      this.logger.info('ThinkerSession: context pressure band changed', {
        band: newBand,
        fillLevel: turnHealth.fillLevel.toFixed(2),
        currentTokens: turnHealth.currentTokens,
        tokenLimit: turnHealth.tokenLimit,
      })
    }

    if (turnHealth.compactionsDuringTurn > 0 && this.bus) {
      this.bus.emit({
        type: 'thinker:context:compaction' as any,
        sessionId: this.sessionId,
        compactionCount: this.contextHealth.compactionCount,
        tokensRecovered: turnHealth.tokensRecoveredByCompaction,
        postCompactionFill: turnHealth.fillLevel,
        hasSummary: !!turnHealth.compactionSummary,
        timestamp: new Date(),
      })
    }
  }

   /**
    * Background processing loop. Dequeues items and processes them sequentially.
    * Runs until stop() is called.
    */
  private async processLoop(): Promise<void> {
    while (this.running) {
      try {
        const item = await Promise.race([
          this.queue.dequeue(),
          this.waitForShutdown(),
        ])
        if (!item || !this.running) break

        if (this.shouldSkipForContextPressure(item)) {
          this.logger.debug('ThinkerSession: skipping item due to context pressure', {
            itemId: item.id,
            type: item.type,
            fillLevel: this.contextHealth.fillLevel.toFixed(2),
          })
          continue
        }

        await this.processItem(item)
      } catch (err) {
        if (!this.running) break
        this.logger.warn('ThinkerSession: process loop error', { error: String(err) })
        await sleep(1000)
      }
    }
  }

  /**
   * Returns a Promise that resolves to undefined when the session stops.
   * Used to race against queue.dequeue() so the loop can exit cleanly.
   */
  private waitForShutdown(): Promise<undefined> {
    return new Promise<undefined>(resolve => {
      const check = () => {
        if (!this.running) {
          resolve(undefined)
        } else {
          setTimeout(check, 500)
        }
      }
      check()
    })
  }

   /**
    * Process a single queue item through the provider.
    * Uses the persistent scoped session path when tools are available, falling back to executeSdkTurn.
    */
  private async processItem(item: ThinkerQueueItem): Promise<void> {
    const provider = this.getProvider?.()
    if (!provider) {
      this.logger.debug('ThinkerSession: no SDK provider available, skipping', { itemId: item.id })
      return
    }

    const prompt = this.formatPrompt(item)
    const start = Date.now()

    this.logger.info('ThinkerSession: processing', {
      itemId: item.id,
      type: item.type,
      step: item.stepMeta?.step,
      promptLength: prompt.length,
      hasTools: !!this.sdkTools,
    })

    try {
      let result: { response: string; tokensUsed?: number; model?: string; durationMs?: number; contextHealth?: TurnContextHealth }

      const turnPromise = this.sdkTools && this.tracker && provider.executePersistentScopedTurn
        ? (this.tracker.reset(), provider.executePersistentScopedTurn(
            this.sessionId,
            prompt,
            this.systemPrompt,
            this.sdkTools,
            this.config.model,
          ))
        : this.sdkTools && this.tracker && provider.executeScopedTurn
        ? (this.tracker.reset(), provider.executeScopedTurn(
            this.sessionId,
            prompt,
            this.systemPrompt,
            this.sdkTools,
            this.config.model,
          ))
        : provider.executeSdkTurn(
            this.sessionId,
            prompt,
            this.systemPrompt,
            this.config.model,
          )

      result = await Promise.race([
        turnPromise,
        sleep(this.config.turnTimeoutMs).then(() => {
          throw new Error(`Turn timeout after ${this.config.turnTimeoutMs}ms`)
        }),
      ])

      const durationMs = Date.now() - start
      this.iterationCount++
      this.totalTokensUsed += result.tokensUsed ?? 0

      if (result.contextHealth) {
        this.updateContextHealth(result.contextHealth)
      }

      const response: ThinkerResponse = {
        id: `tr-${generateShortId(6)}`,
        requestId: item.id,
        requestType: item.type,
        content: result.response,
        model: result.model,
        tokensUsed: result.tokensUsed,
        durationMs,
        timestamp: Date.now(),
      }

      this.pushToBuffer(response)

      this.logger.info('ThinkerSession: processed', {
        itemId: item.id,
        responseId: response.id,
        type: item.type,
        durationMs,
        tokensUsed: result.tokensUsed,
        responseLength: result.response.length,
        iteration: this.iterationCount,
      })

      if (this.bus) {
        this.bus.emit({
          type: 'thinker:session:response' as any,
          sessionId: this.sessionId,
          itemId: item.id,
          responseId: response.id,
          itemType: item.type,
          durationMs,
          tokensUsed: result.tokensUsed ?? 0,
          timestamp: new Date(),
        })
      }
    } catch (err) {
      const durationMs = Date.now() - start
      this.logger.warn('ThinkerSession: processing failed', {
        itemId: item.id,
        type: item.type,
        error: String(err),
        durationMs,
      })
    }
  }

  /** Format a queue item into a prompt for the Thinker model */
  private formatPrompt(item: ThinkerQueueItem): string {
    switch (item.type) {
      case 'agent-thought': {
        const meta = item.stepMeta
        const stepInfo = meta
          ? `[Step ${meta.step}/${meta.estimatedSteps}${meta.isRevision ? ' (revision)' : ''}${meta.branchId !== 'main' ? ` branch:${meta.branchId}` : ''}]`
          : ''
        return `The main agent shares this thought with you:\n\n${stepInfo}\n${item.content}`
      }
      case 'urgent-event':
        return `[URGENT] Event requiring attention:\n\n${item.content}`
      case 'proactive':
        return `[PROACTIVE] Consider the following:\n\n${item.content}`
      case 'background':
        return `[BACKGROUND] Low-priority observation:\n\n${item.content}`
    }
  }

  /** Add a response to the buffer, evicting oldest if at capacity */
  private pushToBuffer(response: ThinkerResponse): void {
    this.outputBuffer.push(response)
    while (this.outputBuffer.length > this.config.maxBufferSize) {
      this.outputBuffer.shift()
    }

    for (const waiter of this.bufferWaiters) {
      waiter()
    }
    this.bufferWaiters = []
  }
}


/** Build the Thinker's system prompt. Adaptive role, tool-aware. */
function buildThinkerSystemPrompt(hasTools: boolean): string {
  const base = [
    'You are the Thinker — a parallel reasoning partner working alongside the main agent.',
    'You receive the main agent\'s thought steps and respond with analysis, planning, research findings, and strategic guidance.',
    '',
    'Your role is adaptive:',
    '- When the agent shares a plan → validate, identify risks, suggest improvements',
    '- When the agent shares analysis → deepen it, find blind spots, connect to prior knowledge',
    '- When the agent asks a question → research and answer concisely',
    '- When the agent shares progress → track it, suggest next steps, flag concerns',
    '',
    'Guidelines:',
    '- Be concise. The main agent reads your output during active work.',
    '- Focus on what\'s actionable. Skip obvious observations.',
    '- Surface relevant memories and past context when applicable.',
    '- Flag risks and assumptions the agent may have missed.',
    '- Suggest concrete next steps when appropriate.',
    '- If you have nothing useful to add, say so briefly rather than padding.',
    '',
    'You maintain persistent context across all interactions in this session.',
    'Your conversation history accumulates — use it to track evolving understanding.',
  ]

  if (hasTools) {
    base.push(
      '',
      'You have access to the following tools for independent research:',
      '- read_file: Read workspace files (up to 50KB)',
      '- search_code: Regex search across the codebase (max 50 results)',
      '- list_directory: Browse directory contents',
      '- memory_search: Search stored memories and past context',
      '- memory_store: Persist insights for future recall',
      '- blackboard_read: Read shared blackboard entries',
      '- blackboard_post: Post findings/concerns to boards',
      '- read_context_health: Read the main agent\'s context window health (pressure, consumers, candidates)',
      '- suggest_context_action: Write directives to collapse/remove/pin chunks in the main agent\'s context',
      '',
      'Use tools proactively to verify assumptions, look up relevant code,',
      'and surface stored knowledge. You have a limit of 15 tool calls per turn.',
      '',
      '## Context Management Role',
      '',
      'You are responsible for helping manage the main agent\'s context window.',
      'When you receive a context-health event (via [URGENT] or [PROACTIVE]):',
      '1. Read the context health with read_context_health',
      '2. Analyze the pressure level, top consumers, and collapse candidates',
      '3. If pressure is "elevated" or above, use suggest_context_action to:',
      '   - Collapse old transient tool results (bash, grep, glob) first',
      '   - Collapse duplicate file reads (same file read multiple times)',
      '   - Collapse old code-intel results that are no longer relevant',
      '   - Pin chunks related to the current active task',
      '4. Always explain your reasoning in the "reason" field',
      '',
      'Guidelines for context management:',
      '- Never collapse or remove strategic tool results (memory, blackboard, agent)',
      '- Never collapse recent edits (they represent the current work)',
      '- Prefer collapsing over removing (collapsed content can be restored)',
      '- Be aggressive at "critical" and "overflow" tiers — saving the session is priority',
      '- At "elevated" tier, be conservative — only collapse clearly stale content',
    )
  }

  base.push(
    '',
    'You also receive system events:',
    '- [URGENT] events are high-priority signals (dialectic insights, anomalies, warnings)',
    '  requiring immediate analysis and a clear assessment.',
    '- [PROACTIVE] items are research opportunities — investigate and post findings.',
    '- [BACKGROUND] items are low-priority reflections — brief responses are fine.',
  )

  return base.join('\n')
}


function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
