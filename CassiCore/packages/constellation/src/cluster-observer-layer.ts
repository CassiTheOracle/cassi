import type { ILogger, IEventBus } from './vendor/types/interfaces.js'
import type { ThinkingLevel } from './vendor/types/runtime.js'
import type { HelixSynapse, SynapseBroadcast, SynapseRollingSlice } from './vendor/helix/helix-synapse.js'
import type { TopologyCluster, TopologySnapshot } from './topology/topology-types.js'
import type { CrossSessionTopicIndex } from '@cassicore/thalamus'
import { ObserverMemoryBridge, extractConceptHints, priorityToConfidence } from './observer-memory-bridge.js'
import type { ObserverMemorySource } from './observer-memory-bridge.js'
import { BroadcastDedupe } from './observer-broadcast-dedupe.js'
import { ObserverActivityScheduler, type ObserverActivityConfig, type ObserverFireReason } from './vendor/helix/observer-activity-scheduler.js'


export interface ClusterObserverLLM {
  complete(opts: {
    prompt: string
    modelTier: string
    maxTokens: number
    timeoutMs: number
    thinking?: ThinkingLevel
  }): Promise<{ content: string; truncated?: boolean }>
}


export interface ClusterObserverLayerConfig {
  enabled: boolean
  modelTier: string
  maxTokens: number
  timeoutMs: number
  pollIntervalMs: number
  minClusterMembers: number
  minStabilityTicks: number
  maxEventsPerSlice: number
  overlapEvents: number
  maxCharsPerPosture: number
  ttlMs: number
  minBroadcastChars: number
}


export const DEFAULT_CLUSTER_OBSERVER_LAYER_CONFIG: ClusterObserverLayerConfig = {
  enabled: true,
  modelTier: 'opus',
  maxTokens: 1_500,
  timeoutMs: 45_000,
  pollIntervalMs: 8_000,
  minClusterMembers: 2,
  minStabilityTicks: 1,
  maxEventsPerSlice: 16,
  overlapEvents: 4,
  maxCharsPerPosture: 3_000,
  ttlMs: 30_000,
  minBroadcastChars: 50,
}


export interface ClusterObserverLayerOpts {
  constellationId: string
  goal: string
  logger: ILogger
  llm: ClusterObserverLLM
  getTopologySnapshot: () => TopologySnapshot | undefined
  getHelixSynapse: (helixId: string) => HelixSynapse | undefined
  memory?: ObserverMemorySource
  crossSessionIndex?: CrossSessionTopicIndex
  eventBus?: IEventBus
  config?: Partial<ClusterObserverLayerConfig>
}


interface ParsedClusterObservation {
  content: string
  priority: SynapseBroadcast['priority']
  targetHelixes: string[]
}


export class ClusterObserverLayer {
  private constellationId: string
  private goal: string
  private logger: ILogger
  private llm: ClusterObserverLLM
  private eventBus?: IEventBus
  private getTopologySnapshot: () => TopologySnapshot | undefined
  private getHelixSynapse: (helixId: string) => HelixSynapse | undefined
  private config: ClusterObserverLayerConfig
  private memory?: ObserverMemoryBridge
  private crossSessionIndex?: CrossSessionTopicIndex
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null
  private dedupe = new BroadcastDedupe({ ttlMs: 120_000, similarityThreshold: 0.82 })
  private scheduler?: ObserverActivityScheduler

  constructor(opts: ClusterObserverLayerOpts) {
    this.constellationId = opts.constellationId
    this.goal = opts.goal
    this.logger = opts.logger.child?.(`cluster-observer:${opts.constellationId}`) ?? opts.logger
    this.llm = opts.llm
    this.eventBus = opts.eventBus
    this.getTopologySnapshot = opts.getTopologySnapshot
    this.getHelixSynapse = opts.getHelixSynapse
    this.config = { ...DEFAULT_CLUSTER_OBSERVER_LAYER_CONFIG, ...opts.config }
    this.crossSessionIndex = opts.crossSessionIndex
    this.memory = opts.memory
      ? new ObserverMemoryBridge({ source: opts.memory, logger: this.logger, sessionId: opts.constellationId, limit: 5 })
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
    this.logger.info('Cluster observer layer started (activity-gated)', {
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
    this.logger.info('Cluster observer layer stopped', { constellationId: this.constellationId })
  }

  private activityConfig(): ObserverActivityConfig {
    return {
      cooldownMs: 240_000,
      maxIdleMs: 1_200_000,
      materialThreshold: 12,
      warmupEvents: 6,
      observerId: `cluster-observer:${this.constellationId}`,
    }
  }

  private async fireOnce(reason: ObserverFireReason): Promise<void> {
    if (this.shutdownRequested && reason !== 'terminal') return
    try {
      await this.observeClusters()
    } catch (err) {
      this.logger.warn('Cluster observer sweep failed', { error: String(err), reason })
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
    const snapshot = this.getTopologySnapshot()
    if (!snapshot || snapshot.clusters.length === 0) return
    for (const cluster of snapshot.clusters) {
      if (cluster.members.length >= this.config.minClusterMembers && cluster.ticksStable >= this.config.minStabilityTicks) {
        this.scheduler?.recordEvent()
        return
      }
    }
  }

  private async observeClusters(): Promise<void> {
    const snapshot = this.getTopologySnapshot()
    if (!snapshot || snapshot.clusters.length === 0) return

    for (const cluster of snapshot.clusters) {
      if (cluster.members.length < this.config.minClusterMembers) continue
      if (cluster.ticksStable < this.config.minStabilityTicks) continue
      await this.observeCluster(cluster)
    }
  }

  private async observeCluster(cluster: TopologyCluster): Promise<void> {
    const entries: Array<{ helixId: string; slices: SynapseRollingSlice[] }> = []
    const observerId = `cluster:${cluster.clusterId}`

    for (const helixId of cluster.members) {
      const synapse = this.getHelixSynapse(helixId)
      if (!synapse) continue
      const slices = synapse.renderSlicesForObserver(observerId, {
        maxEventsPerSlice: this.config.maxEventsPerSlice,
        overlapEvents: this.config.overlapEvents,
        maxCharsPerPosture: this.config.maxCharsPerPosture,
      })
      if (slices.length > 0) entries.push({ helixId, slices })
    }

    if (entries.length < this.config.minClusterMembers) return

    const memoryContext = await this.memory?.recall(this.buildMemoryQuery(cluster, entries), 'cluster-observer') ?? ''
    const crossSessionContext = await this.queryCrossSession(cluster, entries)
    const conflictContext = this.crossSessionIndex?.formatConflicts(cluster.members) ?? ''
    const prompt = this.buildPrompt(cluster, entries, memoryContext, crossSessionContext, conflictContext)
    const response = await this.llm.complete({
      prompt,
      modelTier: this.config.modelTier,
      maxTokens: this.config.maxTokens,
      timeoutMs: this.config.timeoutMs,
      thinking: 'none',
    })

    for (const helixId of cluster.members) {
      this.getHelixSynapse(helixId)?.markObservedBy(observerId)
    }

    const parsed = this.parseResponse(response.content, cluster.members)
    if (!parsed) return
    if (parsed.content.length < this.config.minBroadcastChars) return

    const dedupeKey = `cluster:${cluster.clusterId}`
    const dedupe = this.dedupe.check(dedupeKey, parsed.content)
    if (dedupe.duplicate) return
    this.dedupe.remember(dedupeKey, parsed.content)
    this.memory?.rememberObservation(parsed.content, {
      layer: 'cluster-observer',
      clusterId: cluster.clusterId,
      members: cluster.members,
      priority: parsed.priority,
      tags: ['cluster-observer', `cluster:${cluster.clusterId}`],
    })
    this.memory?.emitInsight({
      label: `cluster:${cluster.clusterId}`,
      content: parsed.content,
      layer: 'cluster',
      constellationId: this.constellationId,
      subjectHelixIds: cluster.members,
      concepts: extractConceptHints(parsed.content),
      confidence: priorityToConfidence(parsed.priority),
      tags: ['cluster-observer', `cluster:${cluster.clusterId}`],
    })

    const references = entries.flatMap(entry => entry.slices.map(s => ({
      posture: `${entry.helixId}/${String(s.posture)}`,
      fromSeq: s.fromSeq,
      toSeq: s.toSeq,
    })))

    const targets = parsed.targetHelixes.length > 0 ? parsed.targetHelixes : cluster.members
    for (const helixId of targets) {
      this.getHelixSynapse(helixId)?.enqueueExternalBroadcast({
        source: `cluster-observer:${cluster.clusterId}`,
        content: parsed.content,
        priority: parsed.priority,
        ttlMs: this.config.ttlMs,
        references,
      })
    }

    this.emitClusterBroadcast(cluster, parsed, targets)
    this.logger.info('Cluster observation broadcast queued', {
      clusterId: cluster.clusterId,
      targets,
      priority: parsed.priority,
      preview: parsed.content.slice(0, 140),
    })
  }

  private async queryCrossSession(
    cluster: TopologyCluster,
    entries: Array<{ helixId: string; slices: SynapseRollingSlice[] }>,
  ): Promise<string> {
    if (!this.crossSessionIndex) return ''
    try {
      const queryParts = entries.flatMap(entry =>
        entry.slices.map(s => s.rendered.slice(-500))
      )
      const queryText = [this.goal, `cluster ${cluster.clusterId}`, ...queryParts].join('\n')
      return await this.crossSessionIndex.queryFormatted(queryText, {
        excludeSessionIds: cluster.members,
        limit: 3,
      })
    } catch (err) {
      this.logger.debug('Cross-session query failed (non-critical)', { error: String(err) })
      return ''
    }
  }

  private buildPrompt(
    cluster: TopologyCluster,
    entries: Array<{ helixId: string; slices: SynapseRollingSlice[] }>,
    memoryContext = '',
    crossSessionContext = '',
    conflictContext = '',
  ): string {
    const body = entries.map(entry => {
      const sliceText = entry.slices.map(slice => {
        return `### ${entry.helixId}/${slice.posture} seq ${slice.fromSeq}-${slice.toSeq}\n` +
          `tools=${slice.metadata.latestToolNames.join(', ') || 'none'} recentError=${slice.metadata.hasRecentError}\n\n` +
          slice.rendered
      }).join('\n\n')
      return `## Thread ${entry.helixId}\n${sliceText}`
    }).join('\n\n---\n\n')

    const links = cluster.links.map(l => `${l.helixIdA}<->${l.helixIdB} depth=${l.mergeDepth} distance=${l.distance.toFixed(2)} sim=${l.similarity.toFixed(2)}`).join('\n')

    return `<identity>
I am watching several nearby threads of work whose attention has drifted close together. I see their recent currents side by side.

My scope is TOPOLOGY-LOCAL: I only observe threads that the topology engine has clustered together because they are doing similar or related work. A separate global observer watches the whole field — I focus on what happens when nearby threads interact.

I notice: convergent findings that one thread found but its neighbors haven't seen yet, divergent strategies that create conflict between nearby threads, and opportunities for handoffs where one thread's output is another's missing piece.
</identity>

<whole_work>
Work: ${this.constellationId}
Goal: ${this.goal}
</whole_work>

<nearby_threads>
Group: ${cluster.clusterId}
Threads: ${cluster.members.join(', ')}
Closeness: ${cluster.effectiveMergeDepth}
Steadiness: ${cluster.ticksStable}
Relationships:
${links || '(none)'}
</nearby_threads>

${conflictContext ? `<file_conflicts>
${conflictContext}
</file_conflicts>` : ''}

${crossSessionContext ? `<cross_session_topics>
These are distilled summaries of work in other threads outside this cluster, curated by the Thalamus. Use this to spot handoff opportunities, conflicts, or convergent findings that the cluster's threads need to know about. Files already flagged in the conflict section above are not repeated here.

${crossSessionContext}
</cross_session_topics>` : ''}

<current_context>
${body}
</current_context>

${memoryContext ? `<relevant_memory>\n${memoryContext}\n</relevant_memory>` : ''}

<instructions>
Look ONLY for topology-local dynamics between these nearby threads:
- A finding in one thread that its cluster neighbor needs but hasn't seen
- Divergent strategies between close threads that create unnecessary conflict
- A handoff opportunity where one thread's output completes another's task
- Resource contention (same file being edited by multiple cluster members)

Do NOT observe: global coverage gaps, strategic direction, or patterns outside this cluster. Those are handled by the global observer.

If there is nothing topology-specific to add, REST immediately.

Respond in exactly one of these forms:

REST: <brief reason>

or

PRIORITY: <ambient|normal|urgent>
TARGET_THREADS: <comma-separated thread ids from this cluster>
BROADCAST: <1-5 sentences about the cluster-local dynamic>
</instructions>`
  }

  private buildMemoryQuery(cluster: TopologyCluster, entries: Array<{ helixId: string; slices: SynapseRollingSlice[] }>): string {
    const parts = [this.goal, `cluster ${cluster.clusterId}`, `members ${cluster.members.join(' ')}`, `depth ${cluster.effectiveMergeDepth}`]
    for (const entry of entries) {
      parts.push(entry.slices.map(s => `${entry.helixId}/${s.posture}: ${s.rendered.slice(-500)}`).join('\n'))
    }
    return parts.join('\n')
  }

  private parseResponse(content: string, members: string[]): ParsedClusterObservation | null {
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
      : rawTargets.split(',').map(t => t.trim()).filter(t => members.includes(t))

    return { content: broadcast, priority, targetHelixes }
  }

  private emitClusterBroadcast(cluster: TopologyCluster, parsed: ParsedClusterObservation, targets: string[]): void {
    if (!this.eventBus) return
    try {
      void (this.eventBus as any).emit({
        type: 'constellation:cluster-observer:broadcast',
        constellationId: this.constellationId,
        clusterId: cluster.clusterId,
        members: cluster.members,
        targets,
        priority: parsed.priority,
        preview: parsed.content.slice(0, 300),
        timestamp: Date.now(),
      })
    } catch {
      // Observability must never crash coordination.
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
}

