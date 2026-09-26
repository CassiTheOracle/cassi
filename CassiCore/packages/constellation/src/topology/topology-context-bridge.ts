/**
 * Topology Context Bridge — Progressive data sharing between linked Helixes.
 *
 * WHY: In observer coordination mode, the BrainstemBridge is disabled because
 * it depends on the Brainstem (which doesn't exist in observer mode). This leaves
 * linked helixes blind to each other's context — they only see observer
 * summaries, not the raw findings, decisions, and active files of their neighbors.
 *
 * This bridge replaces the BrainstemBridge's DATA SHARING function (not its
 * observation function — that's handled by ClusterObserverLayer). It:
 *   1. Reads topology links from TopologyGraph
 *   2. Reads context from ObserverBranchState digests via CorpusTree
 *   3. Injects linked context via GlobalWorkspace so posture runners see it
 *
 * No LLM calls — pure data forwarding. Cheap and fast.
 *
 * Progressive depth model (same as BrainstemBridge):
 *   - shallow: goal, approach, progress, active files, top findings
 *   - medium: + discoveries, blockers, next steps, hypothesis
 *   - deep: + full reasoning chain via liveStreamSnippet
 */

import type { ILogger } from '../vendor/types/interfaces.js'
import type { ICorpusTree, BranchDigest } from '../corpus-types.js'
import type { TopologySnapshot, TopologyLink, MergeDepth } from './topology-types.js'
import type { GlobalWorkspace, CognitiveSignal } from '@cassicore/workspace'


export interface TopologyContextBridgeOpts {
  constellationId: string
  goal: string
  logger: ILogger
  getTopologySnapshot: () => TopologySnapshot | undefined
  getCorpusTree: () => ICorpusTree
  globalWorkspace: GlobalWorkspace
  /** Minimum interval between context injections for the same link. Default: 30_000 */
  injectionCooldownMs?: number
  /** Maximum chars per context injection. Default: 800 */
  maxContextChars?: number
}


interface BridgeState {
  lastInjectionAt: number
  depth: MergeDepth
}


export class TopologyContextBridge {
  private constellationId: string
  private goal: string
  private logger: ILogger
  private getTopologySnapshot: () => TopologySnapshot | undefined
  private getCorpusTree: () => ICorpusTree
  private globalWorkspace: GlobalWorkspace
  private injectionCooldownMs: number
  private maxContextChars: number
  private bridgeStates = new Map<string, BridgeState>()  // "helixA:helixB" → state
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null
  private injectionCount = 0

  constructor(opts: TopologyContextBridgeOpts) {
    this.constellationId = opts.constellationId
    this.goal = opts.goal
    this.logger = opts.logger.child?.(`topology-bridge:${opts.constellationId}`) ?? opts.logger
    this.getTopologySnapshot = opts.getTopologySnapshot
    this.getCorpusTree = opts.getCorpusTree
    this.globalWorkspace = opts.globalWorkspace
    this.injectionCooldownMs = opts.injectionCooldownMs ?? 30_000
    this.maxContextChars = opts.maxContextChars ?? 800
  }

  start(): void {
    if (this.running) return
    this.running = true
    this.shutdownRequested = false
    this.loopPromise = this.runLoop()
    this.logger.info('Topology context bridge started', { constellationId: this.constellationId })
  }

  async stop(): Promise<void> {
    if (!this.running) return
    this.shutdownRequested = true
    if (this.loopPromise) {
      await this.loopPromise
      this.loopPromise = null
    }
    this.running = false
    this.logger.info('Topology context bridge stopped', {
      constellationId: this.constellationId,
      injections: this.injectionCount,
    })
  }

  private async runLoop(): Promise<void> {
    while (!this.shutdownRequested) {
      await this.sleep(this.injectionCooldownMs)
      if (this.shutdownRequested) break
      try {
        this.pushContext()
      } catch (err) {
        this.logger.warn('Topology context push failed', { error: String(err) })
      }
    }
  }

  /**
   * Push context from linked helixes to each other.
   * Called every injectionCooldownMs by the run loop.
   */
  private pushContext(): void {
    const snapshot = this.getTopologySnapshot()
    if (!snapshot || snapshot.links.length === 0) return

    const tree = this.getCorpusTree()
    const now = Date.now()

    for (const link of snapshot.links) {
      const key = linkKey(link.helixIdA, link.helixIdB)
      const state = this.bridgeStates.get(key)

      // Respect cooldown
      if (state && now - state.lastInjectionAt < this.injectionCooldownMs) continue

      // Build context packs for both directions
      const packAtoB = this.buildContextPack(link.helixIdA, link.mergeDepth, tree)
      const packBtoA = this.buildContextPack(link.helixIdB, link.mergeDepth, tree)

      // Inject A's context into B
      if (packAtoB) {
        const content = this.formatContext(packAtoB, link.mergeDepth)
        this.injectViaWorkspace(link.helixIdB, link.helixIdA, content)
      }

      // Inject B's context into A
      if (packBtoA) {
        const content = this.formatContext(packBtoA, link.mergeDepth)
        this.injectViaWorkspace(link.helixIdA, link.helixIdB, content)
      }

      // Update bridge state
      this.bridgeStates.set(key, {
        lastInjectionAt: now,
        depth: link.mergeDepth,
      })
    }
  }

  /**
   * Build a context pack from a branch digest.
   * Same progressive depth model as BrainstemBridge but reads from CorpusTree
   * instead of Brainstem cognitive models.
   */
  private buildContextPack(helixId: string, depth: MergeDepth, tree: ICorpusTree): ContextPack | null {
    const digest = tree.getDigestFor(helixId)
    if (!digest) return null

    const pack: ContextPack = {
      helixId: digest.helixId,
      goalSummary: digest.goalSummary,
      approach: digest.approach,
      progress: digest.progress,
      rollingScore: digest.rollingScore,
      filesActive: digest.filesActive.slice(0, 10),
      topFindings: (digest.keyFindings || []).slice(0, 3),
    }

    if (depth === 'medium' || depth === 'deep') {
      pack.discoveries = (digest.allDiscoveries || []).slice(-5)
      pack.blockers = digest.blockers || []
      pack.nextSteps = (digest.currentNextSteps || []).slice(-3)
      pack.hypothesis = digest.currentHypothesis || ''
    }

    if (depth === 'deep') {
      pack.liveSnippet = digest.liveStreamSnippet?.slice(-500) || ''
      pack.recentOutputs = (digest.recentOutputs || []).slice(-5)
    }

    return pack
  }

  /**
   * Format a context pack into a concise human-readable string.
   */
  private formatContext(pack: ContextPack, depth: MergeDepth): string {
    const lines: string[] = [
      `[Linked thread: ${pack.helixId}]`,
      `Goal: ${pack.goalSummary}`,
      `Approach: ${pack.approach} | Progress: ${(pack.progress * 100).toFixed(0)}% | Score: ${pack.rollingScore.toFixed(2)}`,
    ]

    if (pack.filesActive.length > 0) {
      lines.push(`Active files: ${pack.filesActive.join(', ')}`)
    }

    if (pack.topFindings.length > 0) {
      lines.push(`Key findings: ${pack.topFindings.join('; ')}`)
    }

    if ((depth === 'medium' || depth === 'deep') && pack.discoveries) {
      if (pack.hypothesis) lines.push(`Hypothesis: ${pack.hypothesis}`)
      if (pack.discoveries.length > 0) lines.push(`Recent discoveries: ${pack.discoveries.join('; ')}`)
      if (pack.blockers && pack.blockers.length > 0) lines.push(`Blockers: ${pack.blockers.join('; ')}`)
      if (pack.nextSteps && pack.nextSteps.length > 0) lines.push(`Next steps: ${pack.nextSteps.join('; ')}`)
    }

    if (depth === 'deep' && pack.liveSnippet) {
      lines.push(`Latest reasoning: ${pack.liveSnippet}`)
    }

    if (depth === 'deep' && pack.recentOutputs && pack.recentOutputs.length > 0) {
      lines.push(`Recent outputs: ${pack.recentOutputs.join('; ')}`)
    }

    const full = lines.join('\n')
    return full.length > this.maxContextChars
      ? full.slice(0, this.maxContextChars) + '...'
      : full
  }

  /**
   * Inject context via GlobalWorkspace so the posture runner's
   * injectWorkspaceBroadcasts() picks it up at the start of the next iteration.
   */
  private injectViaWorkspace(targetHelixId: string, sourceHelixId: string, content: string): void {
    this.globalWorkspace.submit({
      signalId: `topo-bridge-${this.constellationId}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      source: `topology-bridge:${sourceHelixId}`,
      sessionId: targetHelixId,
      type: 'context',
      content,
      createdAt: Date.now(),
      luminance: {
        novelty: 0.1,
        urgency: 0.2,
        relevance: 0.6,
        sourceCredibility: 0.7,
        cognitiveResonance: 0, strategicImportance: 0,
        composite: 0.4,
      },
      urgencyHint: 0.15,
      metadata: {
        helix: true,
        posture: 'topology-bridge',
        kind: 'linked-context',
        sourceHelixId,
        constellationId: this.constellationId,
      },
    })

    this.injectionCount++
    this.logger.debug('Context injected', { sourceHelixId, targetHelixId })
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
}


// --- Internal types ---

interface ContextPack {
  helixId: string
  goalSummary: string
  approach: string
  progress: number
  rollingScore: number
  filesActive: string[]
  topFindings: string[]
  discoveries?: string[]
  blockers?: string[]
  nextSteps?: string[]
  hypothesis?: string
  liveSnippet?: string
  recentOutputs?: string[]
}


function linkKey(a: string, b: string): string {
  return a < b ? `${a}:${b}` : `${b}:${a}`
}
