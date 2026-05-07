import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { ThinkingLevel } from '../../../types/runtime.js'
import type { HelixSynapse, SynapseBroadcast, SynapseRollingSlice } from '../helix/helix-synapse.js'
import type { TopologySnapshot } from './topology/topology-types.js'
import type { CrossSessionTopicIndex } from '../thalamus/cross-session-index.js'
import { ObserverMemoryBridge, extractConceptHints, priorityToConfidence } from './observer-memory-bridge.js'
import type { ObserverMemorySource } from './observer-memory-bridge.js'
import { BroadcastDedupe } from './observer-broadcast-dedupe.js'
import { ObserverActivityScheduler, type ObserverActivityConfig, type ObserverFireReason } from '../helix/observer-activity-scheduler.js'


export interface CorpusObserverLLM {
  complete(opts: {
    prompt: string
    modelTier: string
    maxTokens: number
    timeoutMs: number
    thinking?: ThinkingLevel
  }): Promise<{ content: string; truncated?: boolean }>
}


export interface CorpusObserverLayerConfig {
  enabled: boolean
  modelTier: string
  maxTokens: number
  timeoutMs: number
  pollIntervalMs: number
  maxEventsPerSlice: number
  overlapEvents: number
  maxCharsPerPosture: number
  maxHelixesPerPrompt: number
  ttlMs: number
  minBroadcastChars: number
}


export const DEFAULT_CORPUS_OBSERVER_LAYER_CONFIG: CorpusObserverLayerConfig = {
  enabled: true,
  modelTier: 'opus',
  maxTokens: 2_000,
  timeoutMs: 60_000,
  pollIntervalMs: 12_000,
  maxEventsPerSlice: 12,
  overlapEvents: 3,
  maxCharsPerPosture: 2_000,
  maxHelixesPerPrompt: 16,
  ttlMs: 45_000,
  minBroadcastChars: 60,
}


export interface CorpusObserverLayerOpts {
  constellationId: string
  goal: string
  logger: ILogger
  llm: CorpusObserverLLM
  getActiveHelixIds: () => string[]
  getHelixSynapse: (helixId: string) => HelixSynapse | undefined
  getTopologySnapshot?: () => TopologySnapshot | undefined
  /**
   * C-OBS-1 GWT-grounding supplement — provides the signal-pattern digest
   * rendered by the Corpus from its onWorkspaceBroadcast buffer. Returns
   * undefined when the buffer is empty or in meditation mode.
   */
  getSignalPatternDigest?: () => string | undefined
  memory?: ObserverMemorySource
  crossSessionIndex?: CrossSessionTopicIndex
  eventBus?: IEventBus
  config?: Partial<CorpusObserverLayerConfig>
}


interface ParsedCorpusObservation {
  content: string
  priority: SynapseBroadcast['priority']
  targetHelixes: string[]
}


export class CorpusObserverLayer {
  private constellationId: string
  private goal: string
  private logger: ILogger
  private llm: CorpusObserverLLM
  private eventBus?: IEventBus
  private getActiveHelixIds: () => string[]
  private getHelixSynapse: (helixId: string) => HelixSynapse | undefined
  private getTopologySnapshot?: () => TopologySnapshot | undefined
  private getSignalPatternDigest?: () => string | undefined
  private config: CorpusObserverLayerConfig
  private memory?: ObserverMemoryBridge
  private crossSessionIndex?: CrossSessionTopicIndex
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null
  private dedupe = new BroadcastDedupe({ ttlMs: 180_000, similarityThreshold: 0.80 })
  private scheduler?: ObserverActivityScheduler

  constructor(opts: CorpusObserverLayerOpts) {
    this.constellationId = opts.constellationId
    this.goal = opts.goal
    this.logger = opts.logger.child?.(`corpus-observer:${opts.constellationId}`) ?? opts.logger
    this.llm = opts.llm
    this.eventBus = opts.eventBus
    this.getActiveHelixIds = opts.getActiveHelixIds
    this.getHelixSynapse = opts.getHelixSynapse
    this.getTopologySnapshot = opts.getTopologySnapshot
    this.getSignalPatternDigest = opts.getSignalPatternDigest
    this.config = { ...DEFAULT_CORPUS_OBSERVER_LAYER_CONFIG, ...opts.config }
    this.crossSessionIndex = opts.crossSessionIndex
    this.memory = opts.memory
      ? new ObserverMemoryBridge({ source: opts.memory, logger: this.logger, sessionId: opts.constellationId, limit: 6 })
      : undefined
  }

  start(): void {
    if (!this.config.enabled || this.running) return
    this.running = true
    this.shutdownRequested = false
    this.scheduler = new ObserverActivityScheduler(
      this.activityConfig(),
      (reason: ObserverFireReason) => this.fireOnce(reason),
      this.logger,
    )
    this.loopPromise = this.tickLoop()
    this.logger.info('Corpus observer layer started (activity-gated)', {
      constellationId: this.constellationId,
      cooldownMs: this.activityConfig().cooldownMs,
      maxIdleMs: this.activityConfig().maxIdleMs,
      materialThreshold: this.activityConfig().materialThreshold,
    })
  }

  async stop(): Promise<void> {
    if (!this.running) return
    this.shutdownRequested = true
    if (this.loopPromise) {
      await this.loopPromise
      this.loopPromise = null
    }
    if (this.scheduler) {
      this.scheduler.fireTerminal()
      this.scheduler.stop()
      this.scheduler = undefined
    }
    this.running = false
    this.logger.info('Corpus observer layer stopped', { constellationId: this.constellationId })
  }

  private activityConfig(): ObserverActivityConfig {
    return {
      cooldownMs: 480_000,
      maxIdleMs: 2_400_000,
      materialThreshold: 16,
      warmupEvents: 8,
      observerId: `corpus-observer:${this.constellationId}`,
    }
  }

  private async fireOnce(reason: ObserverFireReason): Promise<void> {
    if (this.shutdownRequested && reason !== 'terminal') return
    try {
      await this.observeOnce()
    } catch (err) {
      this.logger.warn('Corpus observer sweep failed', { error: String(err), reason })
    }
  }

  private async tickLoop(): Promise<void> {
    while (!this.shutdownRequested) {
      await this.sleep(this.config.pollIntervalMs)
      if (this.shutdownRequested) break
      this.discoverActivity()
    }
  }

  private discoverActivity(): void {
    const helixIds = this.getActiveHelixIds()
    if (helixIds.length === 0) return
    this.scheduler?.recordEvent()
  }

  private async observeOnce(): Promise<void> {
    const helixIds = this.getActiveHelixIds().slice(0, this.config.maxHelixesPerPrompt)
    if (helixIds.length === 0) return

    const observerId = `corpus:${this.constellationId}`
    const entries: Array<{ helixId: string; slices: SynapseRollingSlice[] }> = []

    for (const helixId of helixIds) {
      const synapse = this.getHelixSynapse(helixId)
      if (!synapse) continue
      const slices = synapse.renderSlicesForObserver(observerId, {
        maxEventsPerSlice: this.config.maxEventsPerSlice,
        overlapEvents: this.config.overlapEvents,
        maxCharsPerPosture: this.config.maxCharsPerPosture,
      })
      if (slices.length > 0) entries.push({ helixId, slices })
    }

    if (entries.length === 0) return

    const memoryContext = await this.memory?.recall(this.buildMemoryQuery(entries), 'corpus-observer') ?? ''
    const crossSessionContext = await this.queryCrossSession(entries)
    const conflictContext = this.crossSessionIndex?.formatConflicts(helixIds) ?? ''
    const prompt = this.buildPrompt(entries, memoryContext, crossSessionContext, conflictContext)
    const response = await this.llm.complete({
      prompt,
      modelTier: this.config.modelTier,
      maxTokens: this.config.maxTokens,
      timeoutMs: this.config.timeoutMs,
      thinking: 'none',
    })

    for (const helixId of helixIds) {
      this.getHelixSynapse(helixId)?.markObservedBy(observerId)
    }

    const parsed = this.parseResponse(response.content, helixIds)
    if (!parsed) return
    if (parsed.content.length < this.config.minBroadcastChars) return

    const dedupeKey = `corpus:${this.constellationId}`
    const dedupe = this.dedupe.check(dedupeKey, parsed.content)
    if (dedupe.duplicate) return
    this.dedupe.remember(dedupeKey, parsed.content)
    this.memory?.rememberObservation(parsed.content, {
      layer: 'corpus-observer',
      constellationId: this.constellationId,
      targets: parsed.targetHelixes,
      priority: parsed.priority,
      tags: ['corpus-observer', `constellation:${this.constellationId}`],
    })
    this.memory?.emitInsight({
      label: `corpus:${this.constellationId}`,
      content: parsed.content,
      layer: 'corpus',
      constellationId: this.constellationId,
      subjectHelixIds: parsed.targetHelixes.length > 0 ? parsed.targetHelixes : helixIds,
      concepts: extractConceptHints(parsed.content),
      confidence: priorityToConfidence(parsed.priority),
      tags: ['corpus-observer', `constellation:${this.constellationId}`],
    })

    const references = entries.flatMap(entry => entry.slices.map(s => ({
      posture: `${entry.helixId}/${String(s.posture)}`,
      fromSeq: s.fromSeq,
      toSeq: s.toSeq,
    })))

    const targets = parsed.targetHelixes.length > 0 ? parsed.targetHelixes : helixIds
    for (const helixId of targets) {
      this.getHelixSynapse(helixId)?.enqueueExternalBroadcast({
        source: `corpus-observer:${this.constellationId}`,
        content: parsed.content,
        priority: parsed.priority,
        ttlMs: this.config.ttlMs,
        references,
      })
    }

    this.emitCorpusBroadcast(parsed, targets)
    this.logger.info('Corpus observation broadcast queued', {
      targets,
      priority: parsed.priority,
      preview: parsed.content.slice(0, 160),
    })
  }

  private async queryCrossSession(entries: Array<{ helixId: string; slices: SynapseRollingSlice[] }>): Promise<string> {
    if (!this.crossSessionIndex) return ''
    try {
      // Build query text from slice content
      const queryParts = entries.flatMap(entry =>
        entry.slices.map(s => s.rendered.slice(-500))
      )
      const queryText = [this.goal, ...queryParts].join('\n')
      return await this.crossSessionIndex.queryFormatted(queryText, { limit: 5 })
    } catch (err) {
      this.logger.debug('Cross-session query failed (non-critical)', { error: String(err) })
      return ''
    }
  }

  private buildPrompt(entries: Array<{ helixId: string; slices: SynapseRollingSlice[] }>, memoryContext = '', crossSessionContext = '', conflictContext = ''): string {
    const topology = this.getTopologySnapshot?.()
    const topologySection = topology
      ? `Nearby groups: ${topology.clusters.map(c => `${c.clusterId}[${c.members.join(',')}; closeness=${c.effectiveMergeDepth}; steady=${c.ticksStable}]`).join('; ') || '(none)'}\nThread relationships: ${topology.links.slice(0, 12).map(l => `${l.helixIdA}<->${l.helixIdB} ${l.mergeDepth} sim=${l.similarity.toFixed(2)} dist=${l.distance.toFixed(2)}`).join('; ') || '(none)'}`
      : '(nearness unavailable)'

    const body = entries.map(entry => {
      const slices = entry.slices.map(slice => {
        return `### ${entry.helixId}/${slice.posture} seq ${slice.fromSeq}-${slice.toSeq}\n` +
          `tools=${slice.metadata.latestToolNames.join(', ') || 'none'} recentError=${slice.metadata.hasRecentError}\n\n` +
          slice.rendered
      }).join('\n\n')
      return `## Thread ${entry.helixId}\n${slices}`
    }).join('\n\n---\n\n')

    const digest = this.getSignalPatternDigest?.()
    const digestSection = digest
      ? `<workspace_signal_patterns>\n${digest}\n</workspace_signal_patterns>`
      : ''

    return `<identity>
I am watching the whole field of work at once. I see the recent current of each active thread and can notice the shape of the effort as a whole: what is converging, what is missing, what is duplicated, what is blocked, and what needs shared awareness.

I do not command or micromanage. I speak only when a global observation would help the next thoughts become clearer or better coordinated. If the field is already coherent, I rest.
</identity>

<whole_work>
Work: ${this.constellationId}
Goal: ${this.goal}
</whole_work>

<nearness>
${topologySection}
</nearness>

${conflictContext ? `<file_conflicts>
${conflictContext}
</file_conflicts>` : ''}

${digestSection}

${crossSessionContext ? `<cross_session_topics>
These are distilled summaries of what other threads have been working on, curated by the Thalamus from the full history of all sessions. Use this to spot duplication, convergence, or gaps across the whole effort. Files already flagged in the conflict section above are not repeated here.

${crossSessionContext}
</cross_session_topics>` : ''}

<current_context>
${body}
</current_context>

${memoryContext ? `<relevant_memory>\n${memoryContext}\n</relevant_memory>` : ''}

<instructions>
Look across all active threads. Speak only if there is a useful global observation: a gap in coverage, a systemic risk, convergence across multiple threads, a dependency between nearby groups, or a strategic imbalance in the whole effort.

Do not issue commands. Phrase the broadcast as first-person shared awareness for the work. If the work is already coherent, rest.

Respond in exactly one of these forms:

REST: <brief reason>

or

PRIORITY: <ambient|normal|urgent>
TARGET_THREADS: <all|comma-separated thread ids>
BROADCAST: <1-6 sentences to show to the target threads>
</instructions>`
  }

  private buildMemoryQuery(entries: Array<{ helixId: string; slices: SynapseRollingSlice[] }>): string {
    const parts = [this.goal, `constellation ${this.constellationId}`]
    for (const entry of entries) {
      parts.push(entry.slices.map(s => `${entry.helixId}/${s.posture}: ${s.rendered.slice(-450)}`).join('\n'))
    }
    return parts.join('\n')
  }

  private parseResponse(content: string, helixIds: string[]): ParsedCorpusObservation | null {
    if (/^\s*REST\s*:/i.test(content)) return null
    const broadcastMatch = content.match(/BROADCAST:\s*([\s\S]+)$/i)
    const broadcast = (broadcastMatch?.[1] ?? content).trim()
    if (!broadcast) return null

    const priorityMatch = content.match(/PRIORITY:\s*(ambient|normal|urgent)/i)
    const priority = (priorityMatch?.[1]?.toLowerCase() as SynapseBroadcast['priority'] | undefined) ?? 'normal'

    const targetsMatch = content.match(/(?:TARGET_THREADS|TARGET_HELIXES):\s*([^\n]+)/i)
    const rawTargets = targetsMatch?.[1]?.trim().toLowerCase()
    const targetHelixes = !rawTargets || rawTargets === 'all'
      ? []
      : rawTargets.split(',').map(t => t.trim()).filter(t => helixIds.includes(t))

    return { content: broadcast, priority, targetHelixes }
  }

  private emitCorpusBroadcast(parsed: ParsedCorpusObservation, targets: string[]): void {
    if (!this.eventBus) return
    try {
      void (this.eventBus as any).emit({
        type: 'constellation:corpus-observer:broadcast',
        constellationId: this.constellationId,
        targets,
        priority: parsed.priority,
        preview: parsed.content.slice(0, 300),
        timestamp: Date.now(),
      })
    } catch {
      // fire-and-forget
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
}

