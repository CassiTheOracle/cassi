/**
 * Link Manager — Detects when Helix sessions should link/unlink
 * based on distance thresholds with hysteresis.
 *
 * HOW: After each GravityEngine tick, the LinkManager:
 *   1. Checks all pairwise distances
 *   2. Creates links when distance < linkThreshold
 *   3. Dissolves links when distance > unlinkThreshold (hysteresis band)
 *   4. Tracks link stability and promotes merge depth progressively
 *
 * The hysteresis band (linkThreshold < unlinkThreshold) prevents
 * rapid link/unlink oscillation when two sessions hover near the boundary.
 */

import type { ILogger } from '../vendor/types/interfaces.js'
import type { GravityEngine } from './gravity-engine.js'
import type {
  LinkConfig,
  TopologyLink,
  MergeDepth,
} from './topology-types.js'


export interface LinkManagerDeps {
  gravityEngine: GravityEngine
  logger: ILogger
  config: LinkConfig
}

export class LinkManager {
  private links = new Map<string, TopologyLink>()
  private deps: LinkManagerDeps
  private logger: ILogger

  constructor(deps: LinkManagerDeps) {
    this.deps = deps
    this.logger = deps.logger.child?.('link-manager') ?? deps.logger
  }

  /**
   * Evaluate all pairwise distances and create/dissolve/promote links.
   * Called after each GravityEngine tick.
   */
  evaluate(activeHelixIds: string[]): void {
    const { linkThreshold, unlinkThreshold, minLinkSimilarity } = this.deps.config

    // Check all pairs for potential new links
    for (let i = 0; i < activeHelixIds.length; i++) {
      for (let j = i + 1; j < activeHelixIds.length; j++) {
        const idA = activeHelixIds[i]
        const idB = activeHelixIds[j]
        const key = this.linkKey(idA, idB)
        const distance = this.deps.gravityEngine.getDistance(idA, idB)
        const similarity = this.deps.gravityEngine.computeSimilarity(idA, idB)
        const existing = this.links.get(key)

        if (existing) {
          // Update distance and similarity on existing link
          existing.distance = distance
          existing.similarity = similarity

          if (distance > unlinkThreshold) {
            // Dissolve: drifted beyond hysteresis band
            this.links.delete(key)
            this.logger.info('Link dissolved (drift)', {
              helixIdA: idA, helixIdB: idB,
              distance: distance.toFixed(3),
              threshold: unlinkThreshold,
            })
          } else {
            // Stable: increment stability and check for merge promotion
            existing.stabilityTicks++
            this.promoteMergeDepth(existing)
          }
        } else if (distance < linkThreshold && similarity >= minLinkSimilarity) {
          // New link: close enough spatially AND semantically similar enough
          const link: TopologyLink = {
            helixIdA: idA < idB ? idA : idB,
            helixIdB: idA < idB ? idB : idA,
            distance,
            similarity,
            createdAt: Date.now(),
            mergeDepth: 'shallow',
            stabilityTicks: 0,
          }
          this.links.set(key, link)
          this.logger.info('Link formed', {
            helixIdA: link.helixIdA, helixIdB: link.helixIdB,
            distance: distance.toFixed(3),
            similarity: similarity.toFixed(3),
          })
        }
      }
    }

    // Clean up links involving deregistered Helixes
    const activeSet = new Set(activeHelixIds)
    for (const [key, link] of this.links) {
      if (!activeSet.has(link.helixIdA) && !activeSet.has(link.helixIdB)) {
        // Both sides inactive — remove
        this.links.delete(key)
      }
    }
  }

  /**
   * Remove a Helix from all links (called when deregistering).
   */
  removeHelix(helixId: string): void {
    for (const [key, link] of this.links) {
      if (link.helixIdA === helixId || link.helixIdB === helixId) {
        this.links.delete(key)
      }
    }
  }

  /**
   * Get all current links.
   */
  getAllLinks(): TopologyLink[] {
    return Array.from(this.links.values())
  }

  /**
   * Get all links involving a specific Helix.
   */
  getLinksFor(helixId: string): TopologyLink[] {
    const result: TopologyLink[] = []
    for (const link of this.links.values()) {
      if (link.helixIdA === helixId || link.helixIdB === helixId) {
        result.push(link)
      }
    }
    return result
  }

  /**
   * Check if two specific Helixes are linked.
   */
  areLinked(helixIdA: string, helixIdB: string): boolean {
    return this.links.has(this.linkKey(helixIdA, helixIdB))
  }

  /**
   * Get the link between two specific Helixes, if it exists.
   */
  getLink(helixIdA: string, helixIdB: string): TopologyLink | undefined {
    return this.links.get(this.linkKey(helixIdA, helixIdB))
  }

  /**
   * Get neighbors of a Helix (all Helixes linked to it).
   */
  getNeighbors(helixId: string): string[] {
    const neighbors: string[] = []
    for (const link of this.links.values()) {
      if (link.helixIdA === helixId) neighbors.push(link.helixIdB)
      else if (link.helixIdB === helixId) neighbors.push(link.helixIdA)
    }
    return neighbors
  }

  // --- Private ---

  /**
   * Promote merge depth based on stability ticks.
   * Progressive: shallow → medium → deep as the link proves stable.
   */
  private promoteMergeDepth(link: TopologyLink): void {
    const { mediumMergeStabilityTicks, deepMergeStabilityTicks } = this.deps.config
    const prevDepth = link.mergeDepth

    if (link.mergeDepth === 'shallow' && link.stabilityTicks >= mediumMergeStabilityTicks) {
      link.mergeDepth = 'medium'
    } else if (link.mergeDepth === 'medium' && link.stabilityTicks >= deepMergeStabilityTicks) {
      link.mergeDepth = 'deep'
    }

    if (link.mergeDepth !== prevDepth) {
      this.logger.info('Link merge depth promoted', {
        helixIdA: link.helixIdA, helixIdB: link.helixIdB,
        from: prevDepth, to: link.mergeDepth,
        stabilityTicks: link.stabilityTicks,
      })
    }
  }

  /**
   * Create a deterministic key for a pair of Helix IDs.
   * Alphabetically ordered to ensure (A,B) === (B,A).
   */
  private linkKey(idA: string, idB: string): string {
    return idA < idB ? `${idA}::${idB}` : `${idB}::${idA}`
  }
}
