import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { HelixSynapse, SynapseBroadcast, SynapseRollingSlice } from '../helix/helix-synapse.js'
import type { TopologyCluster, TopologySnapshot } from './topology/topology-types.js'
import { ObserverMemoryBridge, extractConceptHints, priorityToConfidence } from './observer-memory-bridge.js'
import type { ObserverMemorySource } from './observer-memory-bridge.js'
import { BroadcastDedupe } from './observer-broadcast-dedupe.js'


export interface ClusterObserverLLM {
  complete(opts: {
    prompt: string
    modelTier: string
    maxTokens: number
    timeoutMs: number
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
  modelTier: 'qwenPlus',
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
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null
  private dedupe = new BroadcastDedupe({ ttlMs: 120_000, similarityThreshold: 0.82 })

  constructor(opts: ClusterObserverLayerOpts) {
    this.constellationId = opts.constellationId
    this.goal = opts.goal
    this.logger = opts.logger.child?.(`cluster-observer:${opts.constellationId}`) ?? opts.logger
    this.llm = opts.llm
    this.eventBus = opts.eventBus
    this.getTopologySnapshot = opts.getTopologySnapshot
    this.getHelixSynapse = opts.getHelixSynapse
    this.config = { ...DEFAULT_CLUSTER_OBSERVER_LAYER_CONFIG, ...opts.config }
    this.memory = opts.memory
      ? new ObserverMemoryBridge({ source: opts.memory, logger: this.logger, sessionId: opts.constellationId, limit: 5 })
      : undefined
  }

  start(): void {
    if (!this.config.enabled || this.running) return
    this.running = true
    this.shutdownRequested = false
    this.loopPromise = this.runLoop()
    this.logger.info('Cluster observer layer started', { constellationId: this.constellationId })
  }

  async stop(): Promise<void> {
    if (!this.running) return
    this.shutdownRequested = true
    if (this.loopPromise) {
      await this.loopPromise
      this.loopPromise = null
    }
    this.running = false
    this.logger.info('Cluster observer layer stopped', { constellationId: this.constellationId })
  }

  private async runLoop(): Promise<void> {
    while (!this.shutdownRequested) {
      await this.sleep(this.config.pollIntervalMs)
      if (this.shutdownRequested) break
      try {
        await this.observeClusters()
      } catch (err) {
        this.logger.warn('Cluster observer sweep failed', { error: String(err) })
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
    const prompt = this.buildPrompt(cluster, entries, memoryContext)
    const response = await this.llm.complete({
      prompt,
      modelTier: this.config.modelTier,
      maxTokens: this.config.maxTokens,
      timeoutMs: this.config.timeoutMs,
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

  private buildPrompt(
    cluster: TopologyCluster,
    entries: Array<{ helixId: string; slices: SynapseRollingSlice[] }>,
    memoryContext = '',
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
I am watching several nearby threads of work whose attention has drifted close together. I see their recent currents side by side, so I can notice when one thread has something another thread is missing.

I do not command. I notice shared context, contradictions, duplicated effort, missed handoffs, and opportunities for useful knowledge transfer. I speak only when a nearby thread would think better with this shared awareness.
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

<current_context>
${body}
</current_context>

${memoryContext ? `<relevant_memory>\n${memoryContext}\n</relevant_memory>` : ''}

<instructions>
Look across these nearby threads. If there is a useful shared observation, say it concisely. Mention the concrete thread ids, files, or findings when relevant. If there is nothing useful to add, rest.

Respond in exactly one of these forms:

REST: <brief reason>

or

PRIORITY: <ambient|normal|urgent>
TARGET_THREADS: <all|comma-separated thread ids>
BROADCAST: <1-5 sentences to show to the nearby threads>
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

