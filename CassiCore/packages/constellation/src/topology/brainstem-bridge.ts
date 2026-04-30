/**
 * Brainstem Bridge — Progressive context sharing between linked Helix sessions.
 *
 * When the TopologyGraph detects that two Helix sessions are close enough
 * to link, the BrainstemBridge enables them to share context at progressive
 * depth levels:
 *
 *   - shallow: Digest summaries (goal, approach, progress, files, top findings)
 *   - medium: + cognitive model snippets (decisions, discoveries, blockers, next steps)
 *   - deep: + full cognitive model, blackboard state, quality trajectory
 *
 * HOW: The bridge reads context from CorpusTree digests and Brainstem state,
 * then injects it into linked Helixes via Corpus guidance directives.
 * It acts as a coordination layer — it doesn't replace the existing
 * SharedTreeReader mechanism but enhances it with topology-driven
 * selective context injection.
 *
 * The bridge is managed by the TopologyGraph, which calls:
 *   - activateLink() when two Helixes link
 *   - updateDepth() when merge depth is promoted
 *   - deactivateLink() when a link dissolves
 *   - pushContext() on each topology tick to inject latest context
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { BranchDigest, ICorpusTree } from '../corpus-types.js'
import type { CognitiveModel, BrainstemContextSources } from '../../helix/brainstem-types.js'
import type { MergeDepth } from './topology-types.js'


// --- Context Pack Types ---

/**
 * Shallow context: digest summary fields only.
 * Minimal footprint — safe to inject frequently.
 */
export interface ShallowContextPack {
  helixId: string
  goalSummary: string
  approach: string
  progress: number
  rollingScore: number
  filesActive: string[]
  topFindings: string[]
  updatedAt: number
}

/**
 * Medium context: adds cognitive model snippets.
 * More context for coordination when working on related tasks.
 */
export interface MediumContextPack extends ShallowContextPack {
  recentDecisions: string[]
  recentDiscoveries: string[]
  blockers: string[]
  nextSteps: string[]
  currentHypothesis: string
}

/**
 * Deep context: full cognitive model + blackboard + trajectory.
 * Maximum context for joint planning and complex coordination.
 */
export interface DeepContextPack extends MediumContextPack {
  fullDiscoveries: string[]
  fullDecisions: string[]
  recentOutputs: string[]
  blackboardFindings: string[]
  blackboardConcerns: string[]
  blackboardDecisions: string[]
  qualityTrajectory: number[]
}

/**
 * A bridged context injection ready to deliver to a Helix.
 */
export interface BridgeInjection {
  targetHelixId: string
  sourceHelixId: string
  depth: MergeDepth
  content: string
  timestamp: number
}


// --- Bridge State ---

/**
 * Tracks a single active bridge between two Helixes.
 */
interface ActiveBridge {
  helixIdA: string
  helixIdB: string
  depth: MergeDepth
  lastInjectionAt: number
  injectionCount: number
}


// --- Dependencies ---

export interface BrainstemBridgeDeps {
  tree: ICorpusTree
  logger: ILogger
  /**
   * Callback to inject guidance into a Helix's Brainstem.
   * This uses the existing Corpus directive mechanism.
   */
  injectGuidance: (helixId: string, content: string, urgency: 'low' | 'medium' | 'high' | 'critical') => void
  /**
   * Optional: access to Brainstem state for medium/deep sharing.
   * Maps helixId → state accessors.
   */
  getBrainstemState?: (helixId: string) => BrainstemStateAccessor | undefined
}

/**
 * Read-only accessor for a Brainstem's internal state.
 * Provided by the ConstellationPipeline when registering Brainstems.
 */
export interface BrainstemStateAccessor {
  getCognitiveModel(): CognitiveModel
  getQualityTrajectory(): number[]
  getContextSources(): BrainstemContextSources | undefined
}


// --- Main Class ---

export class BrainstemBridge {
  private activeBridges = new Map<string, ActiveBridge>()
  private deps: BrainstemBridgeDeps
  private logger: ILogger

  /**
   * Minimum interval between context injections per bridge (ms).
   * Prevents flooding linked Helixes with too-frequent updates.
   */
  private readonly injectionCooldownMs = 10_000

  constructor(deps: BrainstemBridgeDeps) {
    this.deps = deps
    this.logger = deps.logger.child?.('brainstem-bridge') ?? deps.logger
  }

  /**
   * Activate a bridge between two linked Helixes.
   * Called by the TopologyGraph when a link forms.
   */
  activateLink(helixIdA: string, helixIdB: string, depth: MergeDepth): void {
    const key = this.bridgeKey(helixIdA, helixIdB)
    if (this.activeBridges.has(key)) return

    this.activeBridges.set(key, {
      helixIdA: helixIdA < helixIdB ? helixIdA : helixIdB,
      helixIdB: helixIdA < helixIdB ? helixIdB : helixIdA,
      depth,
      lastInjectionAt: 0,
      injectionCount: 0,
    })

    this.logger.info('Bridge activated', { helixIdA, helixIdB, depth })
  }

  /**
   * Update the depth of an active bridge.
   * Called by the TopologyGraph when merge depth is promoted.
   */
  updateDepth(helixIdA: string, helixIdB: string, depth: MergeDepth): void {
    const bridge = this.activeBridges.get(this.bridgeKey(helixIdA, helixIdB))
    if (bridge && bridge.depth !== depth) {
      const prevDepth = bridge.depth
      bridge.depth = depth
      this.logger.info('Bridge depth updated', {
        helixIdA, helixIdB, from: prevDepth, to: depth,
      })
    }
  }

  /**
   * Deactivate a bridge when a link dissolves.
   */
  deactivateLink(helixIdA: string, helixIdB: string): void {
    const key = this.bridgeKey(helixIdA, helixIdB)
    const bridge = this.activeBridges.get(key)
    if (bridge) {
      this.activeBridges.delete(key)
      this.logger.info('Bridge deactivated', {
        helixIdA, helixIdB,
        totalInjections: bridge.injectionCount,
      })
    }
  }

  /**
   * Remove all bridges involving a specific Helix.
   */
  removeHelix(helixId: string): void {
    for (const [key, bridge] of this.activeBridges) {
      if (bridge.helixIdA === helixId || bridge.helixIdB === helixId) {
        this.activeBridges.delete(key)
      }
    }
  }

  /**
   * Push context for all active bridges.
   * Called by the TopologyGraph after each tick.
   * Respects cooldown to prevent flooding.
   *
   * Returns the injections that were delivered.
   */
  pushContext(): BridgeInjection[] {
    const now = Date.now()
    const injections: BridgeInjection[] = []

    for (const bridge of this.activeBridges.values()) {
      // Respect cooldown
      if (now - bridge.lastInjectionAt < this.injectionCooldownMs) continue

      // Build context packs for both directions
      const packAtoB = this.buildContextPack(bridge.helixIdA, bridge.depth)
      const packBtoA = this.buildContextPack(bridge.helixIdB, bridge.depth)

      // Inject A's context into B
      if (packAtoB) {
        const content = this.formatContextForInjection(packAtoB, bridge.depth)
        this.deps.injectGuidance(bridge.helixIdB, content, 'low')
        injections.push({
          targetHelixId: bridge.helixIdB,
          sourceHelixId: bridge.helixIdA,
          depth: bridge.depth,
          content,
          timestamp: now,
        })
      }

      // Inject B's context into A
      if (packBtoA) {
        const content = this.formatContextForInjection(packBtoA, bridge.depth)
        this.deps.injectGuidance(bridge.helixIdA, content, 'low')
        injections.push({
          targetHelixId: bridge.helixIdA,
          sourceHelixId: bridge.helixIdB,
          depth: bridge.depth,
          content,
          timestamp: now,
        })
      }

      bridge.lastInjectionAt = now
      bridge.injectionCount++
    }

    if (injections.length > 0) {
      this.logger.info('Context pushed', {
        injections: injections.length,
        bridges: this.activeBridges.size,
      })
    }

    return injections
  }

  /**
   * Get all active bridges (for inspection/testing).
   */
  getActiveBridges(): ActiveBridge[] {
    return Array.from(this.activeBridges.values())
  }

  /**
   * Check if two Helixes have an active bridge.
   */
  hasBridge(helixIdA: string, helixIdB: string): boolean {
    return this.activeBridges.has(this.bridgeKey(helixIdA, helixIdB))
  }

  /**
   * Get bridge count.
   */
  get bridgeCount(): number {
    return this.activeBridges.size
  }

  // --- Context Building ---

  /**
   * Build a context pack from a Helix's current state.
   * Returns null if the Helix has no digest.
   */
  private buildContextPack(helixId: string, depth: MergeDepth): ShallowContextPack | MediumContextPack | DeepContextPack | null {
    const digest = this.deps.tree.getDigestFor(helixId)
    if (!digest) return null

    // Shallow: digest summary only
    const shallow: ShallowContextPack = {
      helixId: digest.helixId,
      goalSummary: digest.goalSummary,
      approach: digest.approach,
      progress: digest.progress,
      rollingScore: digest.rollingScore,
      filesActive: digest.filesActive.slice(0, 10),
      topFindings: (digest.keyFindings || []).slice(0, 3),
      updatedAt: digest.updatedAt,
    }

    if (depth === 'shallow') return shallow

    // Medium: add cognitive model snippets from digest
    const medium: MediumContextPack = {
      ...shallow,
      recentDecisions: (digest.allDecisions || []).slice(-5),
      recentDiscoveries: (digest.allDiscoveries || []).slice(-5),
      blockers: digest.blockers || [],
      nextSteps: (digest.currentNextSteps || []).slice(-3),
      currentHypothesis: digest.currentHypothesis || '',
    }

    if (depth === 'medium') return medium

    // Deep: add full state from Brainstem accessor if available
    const accessor = this.deps.getBrainstemState?.(helixId)
    const cogModel = accessor?.getCognitiveModel()
    const trajectory = accessor?.getQualityTrajectory()
    const cs = accessor?.getContextSources()

    const deep: DeepContextPack = {
      ...medium,
      fullDiscoveries: cogModel?.allDiscoveries || medium.recentDiscoveries,
      fullDecisions: cogModel?.allDecisions || medium.recentDecisions,
      recentOutputs: cogModel?.recentOutputs?.slice(-10) || [],
      // REMOVED: blackboardFindings — Blackboard deprecated. Now uses GlobalWorkspace signals
      blackboardFindings: cs?.globalWorkspace?.getRecentSignals(5)?.map(s => s.content) || [],
      blackboardConcerns: [],
      blackboardDecisions: [],
      qualityTrajectory: trajectory?.slice(-20) || [],
    }

    return deep
  }

  // --- Formatting ---

  /**
   * Format a context pack into a human-readable guidance string
   * that will be injected into the target Helix's Brainstem.
   */
  private formatContextForInjection(pack: ShallowContextPack, depth: MergeDepth): string {
    const lines: string[] = [
      `[Linked Thread: ${pack.helixId}]`,
      `Goal: ${pack.goalSummary}`,
      `Approach: ${pack.approach} | Progress: ${(pack.progress * 100).toFixed(0)}% | Score: ${pack.rollingScore.toFixed(2)}`,
    ]

    if (pack.filesActive.length > 0) {
      lines.push(`Active files: ${pack.filesActive.join(', ')}`)
    }

    if (pack.topFindings.length > 0) {
      lines.push(`Key findings: ${pack.topFindings.join('; ')}`)
    }

    if (depth === 'medium' || depth === 'deep') {
      const medium = pack as MediumContextPack

      if (medium.currentHypothesis) {
        lines.push(`Hypothesis: ${medium.currentHypothesis}`)
      }

      if (medium.recentDecisions.length > 0) {
        lines.push(`Recent decisions: ${medium.recentDecisions.join('; ')}`)
      }

      if (medium.recentDiscoveries.length > 0) {
        lines.push(`Recent discoveries: ${medium.recentDiscoveries.join('; ')}`)
      }

      if (medium.blockers.length > 0) {
        lines.push(`Blockers: ${medium.blockers.join('; ')}`)
      }

      if (medium.nextSteps.length > 0) {
        lines.push(`Next steps: ${medium.nextSteps.join('; ')}`)
      }
    }

    if (depth === 'deep') {
      const deep = pack as DeepContextPack

      if (deep.blackboardFindings.length > 0) {
        lines.push(`Blackboard findings: ${deep.blackboardFindings.slice(0, 3).join('; ')}`)
      }

      if (deep.blackboardConcerns.length > 0) {
        lines.push(`Blackboard concerns: ${deep.blackboardConcerns.slice(0, 3).join('; ')}`)
      }

      if (deep.qualityTrajectory.length > 0) {
        const recent = deep.qualityTrajectory.slice(-5)
        const trend = recent[recent.length - 1] > recent[0] ? 'improving' : recent[recent.length - 1] < recent[0] ? 'declining' : 'stable'
        lines.push(`Quality trend: ${trend} (last 5: ${recent.map(v => v.toFixed(2)).join(', ')})`)
      }
    }

    return lines.join('\n')
  }

  // --- Utility ---

  private bridgeKey(idA: string, idB: string): string {
    return idA < idB ? `${idA}::${idB}` : `${idB}::${idA}`
  }
}
