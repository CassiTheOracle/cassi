import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { ContentBlock, Message } from '../../../types/runtime.js'
import type { HelixRole } from './types.js'
import { ObserverMemoryBridge, extractConceptHints, priorityToConfidence } from '../constellation/observer-memory-bridge.js'
import type { ObserverMemorySource } from '../constellation/observer-memory-bridge.js'
import { BroadcastDedupe, normalizeForDedupe } from '../constellation/observer-broadcast-dedupe.js'


export type SynapseContextEventType =
  | 'message'
  | 'stream-delta'
  | 'tool-call'
  | 'tool-result'
  | 'injection'
  | 'lifecycle'


export interface SynapseContextEvent {
  seq: number
  type: SynapseContextEventType
  posture: HelixRole | string
  timestamp: number
  content: string
  metadata?: Record<string, unknown>
}


export interface SynapseRollingSlice {
  posture: HelixRole | string
  fromSeq: number
  toSeq: number
  overlapFromSeq: number
  rendered: string
  tokenEstimate: number
  metadata: {
    eventCount: number
    latestToolNames: string[]
    hasRecentError: boolean
    lastAssistantTextPreview: string
  }
}


export interface SynapseBroadcast {
  id: string
  helixId: string
  source?: string
  content: string
  priority: 'ambient' | 'normal' | 'urgent'
  createdAt: number
  expiresAt: number
  targetPostures: Array<HelixRole | string>
  references: Array<{ posture: string; fromSeq: number; toSeq: number }>
}


type BroadcastFeedbackOutcome = 'pending' | 'incorporated' | 'ignored'


interface BroadcastFeedbackRecord {
  broadcast: SynapseBroadcast
  posture: string
  injectedAtSeq: number
  checkedUntilSeq: number
  outcome: BroadcastFeedbackOutcome
  evidence?: string
}


export interface HelixSynapseLLM {
  complete(opts: {
    prompt: string
    modelTier: string
    maxTokens: number
    timeoutMs: number
  }): Promise<{ content: string; truncated?: boolean }>
}


export interface HelixSynapseConfig {
  enabled: boolean
  modelTier: string
  maxTokens: number
  timeoutMs: number
  pollIntervalMs: number
  maxEventsPerSlice: number
  overlapEvents: number
  maxCharsPerPosture: number
  broadcastTtlTurns: number
  minBroadcastChars: number
}


export const DEFAULT_HELIX_SYNAPSE_CONFIG: HelixSynapseConfig = {
  enabled: true,
  modelTier: 'qwenPlus',
  maxTokens: 1_200,
  timeoutMs: 30_000,
  pollIntervalMs: 5_000,
  maxEventsPerSlice: 24,
  overlapEvents: 6,
  maxCharsPerPosture: 6_000,
  broadcastTtlTurns: 3,
  minBroadcastChars: 40,
}


export interface HelixSynapseOpts {
  helixId: string
  goal: string
  logger: ILogger
  llm: HelixSynapseLLM
  eventBus?: IEventBus
  memory?: ObserverMemorySource
  config?: Partial<HelixSynapseConfig>
}


class PostureContextStream {
  readonly posture: HelixRole | string
  private seqCounter = 0
  private events: SynapseContextEvent[] = []
  private maxStoredEvents = 240

  constructor(posture: HelixRole | string) {
    this.posture = posture
  }

  append(input: Omit<SynapseContextEvent, 'seq' | 'posture' | 'timestamp'> & { timestamp?: number }): SynapseContextEvent {
    const event: SynapseContextEvent = {
      seq: ++this.seqCounter,
      posture: this.posture,
      timestamp: input.timestamp ?? Date.now(),
      type: input.type,
      content: input.content,
      metadata: input.metadata,
    }

    const last = this.events[this.events.length - 1]
    if (event.type === 'stream-delta' && last?.type === 'stream-delta') {
      this.events[this.events.length - 1] = event
    } else {
      this.events.push(event)
      if (this.events.length > this.maxStoredEvents) {
        this.events = this.events.slice(-this.maxStoredEvents)
      }
    }
    return event
  }

  get latestSeq(): number {
    return this.seqCounter
  }

  render(lastObservedSeq: number, config: HelixSynapseConfig): SynapseRollingSlice | null {
    if (this.events.length === 0) return null
    const latestSeq = this.latestSeq
    const overlapFromSeq = Math.max(1, lastObservedSeq - config.overlapEvents + 1)

    let selected = this.events
      .filter(e => e.seq >= overlapFromSeq)
      .slice(-config.maxEventsPerSlice)

    if (selected.length === 0) {
      selected = this.events.slice(-Math.min(config.overlapEvents, config.maxEventsPerSlice))
    }

    let rendered = selected.map(formatEvent).join('\n\n')
    if (rendered.length > config.maxCharsPerPosture) {
      rendered = rendered.slice(-config.maxCharsPerPosture)
      rendered = `[older context truncated]\n${rendered}`
    }

    const latestToolNames = selected
      .filter(e => e.type === 'tool-call')
      .map(e => String(e.metadata?.toolName ?? 'unknown'))
      .slice(-8)
    const hasRecentError = selected.some(e => e.type === 'tool-result' && e.metadata?.isError === true)
    const lastAssistantTextPreview = [...selected]
      .reverse()
      .find(e => e.type === 'message' && e.metadata?.role === 'assistant')
      ?.content.slice(0, 300) ?? ''

    return {
      posture: this.posture,
      fromSeq: selected[0]?.seq ?? latestSeq,
      toSeq: latestSeq,
      overlapFromSeq,
      rendered,
      tokenEstimate: Math.ceil(rendered.length / 4),
      metadata: {
        eventCount: selected.length,
        latestToolNames,
        hasRecentError,
        lastAssistantTextPreview,
      },
    }
  }
}


export class HelixSynapse {
  readonly helixId: string
  readonly goal: string

  private logger: ILogger
  private llm: HelixSynapseLLM
  private eventBus?: IEventBus
  private config: HelixSynapseConfig
  private memory?: ObserverMemoryBridge
  private streams = new Map<string, PostureContextStream>()
  private lastObservedSeq = new Map<string, number>()
  private externalObservedSeq = new Map<string, Map<string, number>>()
  private queues = new Map<string, SynapseBroadcast[]>()
  private dedupe = new BroadcastDedupe({ ttlMs: 90_000, similarityThreshold: 0.84 })
  private feedbackRecords = new Map<string, BroadcastFeedbackRecord>()
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null
  private broadcastCounter = 0
  private lastBroadcastText = ''

  constructor(opts: HelixSynapseOpts) {
    this.helixId = opts.helixId
    this.goal = opts.goal
    this.logger = opts.logger.child?.(`helix-synapse:${opts.helixId.slice(0, 8)}`) ?? opts.logger
    this.llm = opts.llm
    this.eventBus = opts.eventBus
    this.config = { ...DEFAULT_HELIX_SYNAPSE_CONFIG, ...opts.config }
    this.memory = opts.memory
      ? new ObserverMemoryBridge({ source: opts.memory, logger: this.logger, sessionId: opts.helixId, limit: 4 })
      : undefined
  }

  start(): void {
    if (!this.config.enabled || this.running) return
    this.running = true
    this.shutdownRequested = false
    this.loopPromise = this.runLoop()
    this.logger.info('Helix Synapse observer started', { helixId: this.helixId })
  }

  async stop(): Promise<void> {
    if (!this.running) return
    this.shutdownRequested = true
    if (this.loopPromise) {
      await this.loopPromise
      this.loopPromise = null
    }
    this.running = false
    this.logger.info('Helix Synapse observer stopped', { helixId: this.helixId })
  }

  appendMessage(posture: HelixRole | string, message: Message): void {
    const event = this.append(posture, {
      type: 'message',
      content: renderMessage(message),
      metadata: { role: message.role },
    })
    this.checkFeedback(posture, event)
  }

  appendStreamDelta(posture: HelixRole | string, text: string, metadata?: Record<string, unknown>): void {
    if (!text.trim()) return
    const event = this.append(posture, {
      type: 'stream-delta',
      content: text.slice(-4_000),
      metadata,
    })
    this.checkFeedback(posture, event)
  }

  appendToolCall(posture: HelixRole | string, call: { id: string; name: string; input: unknown }): void {
    const event = this.append(posture, {
      type: 'tool-call',
      content: `${call.name}(${safeJson(call.input).slice(0, 1_500)})`,
      metadata: { toolName: call.name, callId: call.id },
    })
    this.checkFeedback(posture, event)
  }

  appendToolResult(posture: HelixRole | string, result: { callId: string; content: string; isError?: boolean }): void {
    const event = this.append(posture, {
      type: 'tool-result',
      content: result.content.slice(0, 2_000),
      metadata: { callId: result.callId, isError: result.isError ?? false },
    })
    this.checkFeedback(posture, event)
  }

  appendInjection(posture: HelixRole | string, broadcast: SynapseBroadcast): void {
    const event = this.append(posture, {
      type: 'injection',
      content: broadcast.content,
      metadata: { broadcastId: broadcast.id, priority: broadcast.priority, source: 'helix-synapse' },
    })
    const key = this.feedbackKey(broadcast.id, posture)
    this.feedbackRecords.set(key, {
      broadcast,
      posture: String(posture),
      injectedAtSeq: event.seq,
      checkedUntilSeq: event.seq,
      outcome: 'pending',
    })
  }

  drainBroadcasts(posture: HelixRole | string): SynapseBroadcast[] {
    const key = String(posture)
    const now = Date.now()
    const queue = this.queues.get(key) ?? []
    const active = queue.filter(b => b.expiresAt > now)
    this.queues.set(key, [])
    return active
  }

  renderSlicesForObserver(
    observerId: string,
    config?: Partial<Pick<HelixSynapseConfig, 'maxEventsPerSlice' | 'overlapEvents' | 'maxCharsPerPosture'>>,
  ): SynapseRollingSlice[] {
    const mergedConfig = { ...this.config, ...config }
    const cursors = this.externalObservedSeq.get(observerId) ?? new Map<string, number>()
    const slices: SynapseRollingSlice[] = []
    for (const [posture, stream] of this.streams) {
      const slice = stream.render(cursors.get(posture) ?? 0, mergedConfig)
      if (slice) slices.push(slice)
    }
    return slices
  }

  markObservedBy(observerId: string): void {
    const cursors = this.externalObservedSeq.get(observerId) ?? new Map<string, number>()
    for (const [posture, stream] of this.streams) {
      cursors.set(posture, stream.latestSeq)
    }
    this.externalObservedSeq.set(observerId, cursors)
  }

  enqueueExternalBroadcast(input: {
    source: string
    content: string
    priority?: SynapseBroadcast['priority']
    targetPostures?: Array<HelixRole | string>
    ttlMs?: number
    references?: SynapseBroadcast['references']
  }): SynapseBroadcast {
    const targetPostures = input.targetPostures?.length
      ? input.targetPostures
      : [...this.streams.keys()]
    const now = Date.now()
    const broadcast: SynapseBroadcast = {
      id: `${input.source}-${this.helixId}-${++this.broadcastCounter}-${now.toString(36)}`,
      helixId: this.helixId,
      source: input.source,
      content: input.content,
      priority: input.priority ?? 'normal',
      createdAt: now,
      expiresAt: now + (input.ttlMs ?? this.config.broadcastTtlTurns * this.config.pollIntervalMs * 2),
      targetPostures,
      references: input.references ?? [],
    }

    for (const posture of targetPostures) {
      this.enqueueForPosture(posture, broadcast)
    }
    return broadcast
  }

  private append(posture: HelixRole | string, event: Omit<SynapseContextEvent, 'seq' | 'posture' | 'timestamp'>): SynapseContextEvent {
    const key = String(posture)
    let stream = this.streams.get(key)
    if (!stream) {
      stream = new PostureContextStream(posture)
      this.streams.set(key, stream)
    }
    return stream.append(event)
  }

  private async runLoop(): Promise<void> {
    while (!this.shutdownRequested) {
      try {
        await this.sleep(this.config.pollIntervalMs)
        if (this.shutdownRequested) break
        if (!this.hasNewContext()) continue
        await this.observeOnce()
      } catch (err) {
        this.logger.warn('Helix Synapse observer loop failed', { error: String(err) })
      }
    }
  }

  private hasNewContext(): boolean {
    for (const [posture, stream] of this.streams) {
      const last = this.lastObservedSeq.get(posture) ?? 0
      if (stream.latestSeq > last) return true
    }
    return false
  }

  private async observeOnce(): Promise<void> {
    const slices: SynapseRollingSlice[] = []
    for (const [posture, stream] of this.streams) {
      const slice = stream.render(this.lastObservedSeq.get(posture) ?? 0, this.config)
      if (slice) slices.push(slice)
    }
    if (slices.length === 0) return

    const memoryContext = await this.memory?.recall(this.buildMemoryQuery(slices), 'helix-synapse') ?? ''
    const prompt = this.buildObserverPrompt(slices, memoryContext)
    const response = await this.llm.complete({
      prompt,
      modelTier: this.config.modelTier,
      maxTokens: this.config.maxTokens,
      timeoutMs: this.config.timeoutMs,
    })

    for (const [posture, stream] of this.streams) {
      this.lastObservedSeq.set(posture, stream.latestSeq)
    }

    const parsed = this.parseObserverResponse(response.content)
    if (!parsed) return
    if (parsed.content.length < this.config.minBroadcastChars) return
    const dedupeKey = `helix:${this.helixId}`
    const dedupe = this.dedupe.check(dedupeKey, parsed.content)
    if (dedupe.duplicate) return

    const targetPostures = parsed.targets.length > 0
      ? parsed.targets
      : [...this.streams.keys()]

    const broadcast: SynapseBroadcast = {
      id: `synapse-${this.helixId}-${++this.broadcastCounter}-${Date.now().toString(36)}`,
      helixId: this.helixId,
      source: 'helix-synapse',
      content: parsed.content,
      priority: parsed.priority,
      createdAt: Date.now(),
      expiresAt: Date.now() + this.config.broadcastTtlTurns * this.config.pollIntervalMs * 2,
      targetPostures,
      references: slices.map(s => ({ posture: String(s.posture), fromSeq: s.fromSeq, toSeq: s.toSeq })),
    }

    for (const posture of targetPostures) {
      this.enqueueForPosture(posture, broadcast)
    }

    this.lastBroadcastText = parsed.content
    this.dedupe.remember(dedupeKey, parsed.content)
    this.memory?.rememberObservation(parsed.content, {
      layer: 'helix-synapse',
      helixId: this.helixId,
      priority: parsed.priority,
      tags: ['helix-synapse', `helix:${this.helixId}`],
    })
    this.memory?.emitInsight({
      label: `helix:${this.helixId}`,
      content: parsed.content,
      layer: 'synapse',
      subjectHelixIds: [this.helixId],
      concepts: extractConceptHints(parsed.content),
      confidence: priorityToConfidence(parsed.priority),
      tags: ['helix-synapse', `helix:${this.helixId}`],
    })
    this.emitBroadcastEvent(broadcast)
    this.logger.info('Helix Synapse broadcast queued', {
      helixId: this.helixId,
      targets: targetPostures,
      priority: parsed.priority,
      preview: parsed.content.slice(0, 120),
    })
  }

  private buildObserverPrompt(slices: SynapseRollingSlice[], memoryContext = ''): string {
    const postureSections = slices.map(slice => {
      return `## ${slice.posture} — rolling context slice seq ${slice.fromSeq}-${slice.toSeq}\n` +
        `Events: ${slice.metadata.eventCount}; tools: ${slice.metadata.latestToolNames.join(', ') || 'none'}; recentError: ${slice.metadata.hasRecentError}\n\n` +
        slice.rendered
    }).join('\n\n---\n\n')

    return `<identity>
I am watching one thread of work as it unfolds through several voices. I see the recent current of each voice directly, with enough overlap that I can notice what carries across turns.

I do not command or grade. I notice relationships, missed handoffs, stale assumptions, contradictions, and moments of convergence. I speak only when saying something would help the next thought become clearer. If nothing needs saying, I rest.
</identity>

<thread>
Thread: ${this.helixId}
Goal: ${this.goal}
</thread>

<current_context>
${postureSections}
</current_context>

${memoryContext ? `<relevant_memory>\n${memoryContext}\n</relevant_memory>` : ''}

<instructions>
Look across all voices. Notice convergence, contradiction, missed handoffs, duplicated effort, stale assumptions, ignored discoveries, tool-result implications, or an obvious next integration step.

Only speak if the observation is specifically useful right now. Do not repeat generic advice. Do not command. Write as a calm first-person shared observation.

Respond in exactly one of these forms:

REST: <brief reason>

or

PRIORITY: <ambient|normal|urgent>
TARGETS: <all|unity,yang,yin>
BROADCAST: <1-4 sentences to show to the named voices>
</instructions>`
  }

  private enqueueForPosture(posture: HelixRole | string, broadcast: SynapseBroadcast): void {
    const key = String(posture)
    const now = Date.now()
    const incomingNorm = normalizeForDedupe(broadcast.content)
    const queue = (this.queues.get(key) ?? [])
      .filter(b => b.expiresAt > now)
      .filter(b => {
        if (b.source !== broadcast.source) return true
        return normalizeForDedupe(b.content) !== incomingNorm
      })
    queue.push(broadcast)
    this.queues.set(key, queue.slice(-6))
  }

  private checkFeedback(posture: HelixRole | string, event: SynapseContextEvent): void {
    const postureKey = String(posture)
    for (const record of this.feedbackRecords.values()) {
      if (record.posture !== postureKey) continue
      if (record.outcome !== 'pending') continue
      if (event.seq <= record.injectedAtSeq) continue
      if (event.type === 'injection') continue

      record.checkedUntilSeq = event.seq
      const overlap = contentOverlap(record.broadcast.content, event.content)
      const toolName = typeof event.metadata?.toolName === 'string' ? event.metadata.toolName : undefined

      if (overlap >= 0.18 || (toolName && record.broadcast.content.toLowerCase().includes(toolName.toLowerCase()))) {
        record.outcome = 'incorporated'
        record.evidence = event.content.slice(0, 400)
        this.emitFeedback(record)
        continue
      }

      if (event.seq - record.injectedAtSeq >= 6) {
        record.outcome = 'ignored'
        record.evidence = 'No meaningful overlap in the next several context events.'
        this.emitFeedback(record)
      }
    }
  }

  private emitFeedback(record: BroadcastFeedbackRecord): void {
    this.memory?.rememberObservation(
      `Observer broadcast was ${record.outcome} by ${record.posture}: ${record.broadcast.content.slice(0, 500)}`,
      {
        layer: 'observer-feedback',
        helixId: this.helixId,
        posture: record.posture,
        source: record.broadcast.source,
        outcome: record.outcome,
        tags: ['observer-feedback', record.outcome],
      },
    )

    if (!this.eventBus) return
    try {
      void (this.eventBus as any).emit({
        type: 'helix:synapse:feedback',
        sessionId: this.helixId,
        helixId: this.helixId,
        broadcastId: record.broadcast.id,
        source: record.broadcast.source,
        posture: record.posture,
        outcome: record.outcome,
        evidence: record.evidence?.slice(0, 300),
        timestamp: Date.now(),
      })
    } catch {
      // Observability must not affect execution.
    }
  }

  private feedbackKey(broadcastId: string, posture: HelixRole | string): string {
    return `${broadcastId}::${String(posture)}`
  }

  private buildMemoryQuery(slices: SynapseRollingSlice[]): string {
    const parts = [this.goal]
    for (const slice of slices) {
      parts.push(`${slice.posture}: ${slice.rendered.slice(-800)}`)
    }
    return parts.join('\n')
  }

  private parseObserverResponse(content: string): { content: string; priority: SynapseBroadcast['priority']; targets: string[] } | null {
    if (/^\s*REST\s*:/i.test(content)) return null
    const broadcastMatch = content.match(/BROADCAST:\s*([\s\S]+)$/i)
    const broadcast = (broadcastMatch?.[1] ?? content).trim()
    if (!broadcast) return null

    const priorityMatch = content.match(/PRIORITY:\s*(ambient|normal|urgent)/i)
    const priority = (priorityMatch?.[1]?.toLowerCase() as SynapseBroadcast['priority'] | undefined) ?? 'normal'

    const targetsMatch = content.match(/TARGETS:\s*([^\n]+)/i)
    const rawTargets = targetsMatch?.[1]?.trim().toLowerCase()
    const targets = !rawTargets || rawTargets === 'all'
      ? []
      : rawTargets.split(',').map(t => t.trim()).filter(Boolean)

    return { content: broadcast, priority, targets }
  }

  private emitBroadcastEvent(broadcast: SynapseBroadcast): void {
    if (!this.eventBus) return
    try {
      void (this.eventBus as any).emit({
        type: 'helix:synapse:broadcast',
        sessionId: this.helixId,
        helixId: this.helixId,
        broadcastId: broadcast.id,
        priority: broadcast.priority,
        targets: broadcast.targetPostures,
        preview: broadcast.content.slice(0, 300),
        timestamp: Date.now(),
      })
    } catch {
      // Observability must never crash the observer.
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
}


function formatEvent(event: SynapseContextEvent): string {
  const ts = new Date(event.timestamp).toISOString()
  const header = `[${event.seq}] ${ts} ${event.type}`
  return `${header}\n${event.content}`
}


function renderMessage(message: Message): string {
  if (typeof message.content === 'string') {
    return `${message.role}: ${message.content}`
  }
  return `${message.role}: ${message.content.map(renderContentBlock).join('\n')}`
}


function renderContentBlock(block: ContentBlock): string {
  if (block.type === 'text') return block.text
  if (block.type === 'tool_use') return `tool_use ${block.name}(${safeJson(block.input).slice(0, 1000)})`
  return `tool_result ${block.tool_use_id}${block.is_error ? ' [ERROR]' : ''}: ${String(block.content).slice(0, 1000)}`
}


function safeJson(value: unknown): string {
  try { return JSON.stringify(value) } catch { return String(value) }
}


function contentOverlap(a: string, b: string): number {
  const aTokens = importantTokens(a)
  const bTokens = importantTokens(b)
  if (aTokens.size === 0 || bTokens.size === 0) return 0
  let overlap = 0
  for (const token of aTokens) {
    if (bTokens.has(token)) overlap++
  }
  return overlap / Math.max(1, Math.min(aTokens.size, bTokens.size))
}


function importantTokens(text: string): Set<string> {
  const stop = new Set(['the', 'and', 'that', 'this', 'with', 'from', 'have', 'should', 'could', 'would', 'there', 'their', 'about', 'into', 'onto', 'then', 'than', 'they', 'them', 'your', 'work'])
  return new Set(
    text
      .toLowerCase()
      .split(/[^a-z0-9_./-]+/)
      .filter(t => t.length > 3 && !stop.has(t))
      .slice(0, 120),
  )
}
