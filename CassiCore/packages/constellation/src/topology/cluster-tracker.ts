/**
 * Cluster Tracker — Identifies transitive groups of linked Helix sessions
 * and tracks their stability over time.
 *
 * HOW: After each LinkManager evaluation, the ClusterTracker:
 *   1. Runs connected-component detection on the link graph
 *   2. Assigns stable cluster IDs (preserved across ticks if membership matches)
 *   3. Computes effective merge depth (minimum across links in cluster)
 *   4. Tracks stability scores (how long the cluster has persisted unchanged)
 *
 * Clusters are the unit of coordination the Corpus reasons about.
 * The Corpus can see "these 3 Helixes formed a tight cluster doing
 * implementation work" and decide whether to merge their goals.
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { LinkManager } from './link-manager.js'
import type { GravityEngine } from './gravity-engine.js'
import type {
  TopologyCluster,
  TopologyLink,
  MergeDepth,
} from './topology-types.js'


export interface ClusterTrackerDeps {
  linkManager: LinkManager
  gravityEngine: GravityEngine
  logger: ILogger
}

/**
 * Merge depth priority for computing the effective depth across a cluster.
 * Lower number = shallower depth (the cluster operates at its weakest link).
 */
const MERGE_DEPTH_PRIORITY: Record<MergeDepth, number> = {
  shallow: 0,
  medium: 1,
  deep: 2,
}

const MERGE_DEPTH_FROM_PRIORITY: MergeDepth[] = ['shallow', 'medium', 'deep']

export class ClusterTracker {
  private clusters = new Map<string, TopologyCluster>()
  private previousMemberships = new Map<string, string>()
  private clusterIdCounter = 0
  private deps: ClusterTrackerDeps
  private logger: ILogger

  constructor(deps: ClusterTrackerDeps) {
    this.deps = deps
    this.logger = deps.logger.child?.('cluster-tracker') ?? deps.logger
  }

  /**
   * Recompute clusters from current link state.
   * Called after each LinkManager evaluation.
   */
  update(activeHelixIds: string[]): void {
    const links = this.deps.linkManager.getAllLinks()
    const components = this.findConnectedComponents(activeHelixIds, links)

    // Build new cluster map, preserving IDs for unchanged memberships
    const newClusters = new Map<string, TopologyCluster>()
    const newMemberships = new Map<string, string>()

    for (const component of components) {
      if (component.length < 2) continue // Singletons are not clusters

      const memberSet = new Set(component)
      const clusterLinks = links.filter(
        l => memberSet.has(l.helixIdA) && memberSet.has(l.helixIdB),
      )

      // Check if this cluster existed before (same members)
      const sortedMembers = [...component].sort()
      const memberKey = sortedMembers.join(',')
      const existingId = this.findExistingClusterId(sortedMembers)

      const clusterId = existingId || this.generateClusterId()
      const existing = existingId ? this.clusters.get(existingId) : undefined

      const effectiveMergeDepth = this.computeEffectiveMergeDepth(clusterLinks)
      const averageInternalDistance = this.computeAverageDistance(component)

      const cluster: TopologyCluster = {
        clusterId,
        members: sortedMembers,
        links: clusterLinks,
        effectiveMergeDepth,
        averageInternalDistance,
        stabilityScore: existing
          ? Math.min((existing.ticksStable + 1) / 100, 1.0) // Asymptotic to 1.0
          : 0,
        formedAt: existing?.formedAt ?? Date.now(),
        ticksStable: existing ? existing.ticksStable + 1 : 0,
      }

      newClusters.set(clusterId, cluster)

      // Track which cluster each Helix belongs to
      for (const helixId of sortedMembers) {
        newMemberships.set(helixId, clusterId)
      }
    }

    // Detect cluster formation and dissolution events
    this.detectClusterEvents(this.clusters, newClusters)

    this.clusters = newClusters
    this.previousMemberships = newMemberships
  }

  /**
   * Get all current clusters.
   */
  getAllClusters(): TopologyCluster[] {
    return Array.from(this.clusters.values())
  }

  /**
   * Get the cluster a specific Helix belongs to, if any.
   */
  getClusterFor(helixId: string): TopologyCluster | undefined {
    const clusterId = this.previousMemberships.get(helixId)
    return clusterId ? this.clusters.get(clusterId) : undefined
  }

  /**
   * Get all Helix IDs that are in any cluster.
   */
  getClusteredHelixIds(): string[] {
    return Array.from(this.previousMemberships.keys())
  }

  /**
   * Check if two Helixes are in the same cluster.
   */
  areInSameCluster(helixIdA: string, helixIdB: string): boolean {
    const clusterA = this.previousMemberships.get(helixIdA)
    const clusterB = this.previousMemberships.get(helixIdB)
    return clusterA !== undefined && clusterA === clusterB
  }

  /**
   * Get the effective merge depth between two Helixes.
   * Returns undefined if they're not in the same cluster.
   */
  getEffectiveMergeDepth(helixIdA: string, helixIdB: string): MergeDepth | undefined {
    const cluster = this.getClusterFor(helixIdA)
    if (!cluster) return undefined
    if (!cluster.members.includes(helixIdB)) return undefined
    return cluster.effectiveMergeDepth
  }

  // --- Private ---

  /**
   * Find connected components in the link graph using BFS.
   */
  private findConnectedComponents(helixIds: string[], links: TopologyLink[]): string[][] {
    // Build adjacency list
    const adj = new Map<string, string[]>()
    for (const id of helixIds) {
      adj.set(id, [])
    }
    for (const link of links) {
      adj.get(link.helixIdA)?.push(link.helixIdB)
      adj.get(link.helixIdB)?.push(link.helixIdA)
    }

    const visited = new Set<string>()
    const components: string[][] = []

    for (const id of helixIds) {
      if (visited.has(id)) continue

      // BFS from this node
      const component: string[] = []
      const queue = [id]
      visited.add(id)

      while (queue.length > 0) {
        const current = queue.shift()!
        component.push(current)

        for (const neighbor of adj.get(current) || []) {
          if (!visited.has(neighbor)) {
            visited.add(neighbor)
            queue.push(neighbor)
          }
        }
      }

      components.push(component)
    }

    return components
  }

  /**
   * Find existing cluster ID by checking if sorted members match.
   */
  private findExistingClusterId(sortedMembers: string[]): string | undefined {
    const memberKey = sortedMembers.join(',')
    for (const [id, cluster] of this.clusters) {
      if (cluster.members.join(',') === memberKey) {
        return id
      }
    }
    return undefined
  }

  /**
   * Compute effective merge depth across all links in a cluster.
   * The cluster operates at its weakest (shallowest) link.
   */
  private computeEffectiveMergeDepth(links: TopologyLink[]): MergeDepth {
    if (links.length === 0) return 'shallow'

    let minPriority = Infinity
    for (const link of links) {
      const priority = MERGE_DEPTH_PRIORITY[link.mergeDepth]
      if (priority < minPriority) minPriority = priority
    }

    return MERGE_DEPTH_FROM_PRIORITY[Math.min(minPriority, 2)]
  }

  /**
   * Compute average pairwise distance within a component.
   */
  private computeAverageDistance(members: string[]): number {
    if (members.length < 2) return 0

    let totalDist = 0
    let pairs = 0

    for (let i = 0; i < members.length; i++) {
      for (let j = i + 1; j < members.length; j++) {
        totalDist += this.deps.gravityEngine.getDistance(members[i], members[j])
        pairs++
      }
    }

    return pairs > 0 ? totalDist / pairs : 0
  }

  /**
   * Generate a unique cluster ID.
   */
  private generateClusterId(): string {
    return `cluster-${++this.clusterIdCounter}-${Date.now()}`
  }

  /**
   * Detect and log cluster formation/dissolution events.
   */
  private detectClusterEvents(
    oldClusters: Map<string, TopologyCluster>,
    newClusters: Map<string, TopologyCluster>,
  ): void {
    // New clusters (IDs not in old)
    for (const [id, cluster] of newClusters) {
      if (!oldClusters.has(id)) {
        this.logger.info('Cluster formed', {
          clusterId: id,
          members: cluster.members,
          mergeDepth: cluster.effectiveMergeDepth,
        })
      }
    }

    // Dissolved clusters (IDs not in new)
    for (const [id, cluster] of oldClusters) {
      if (!newClusters.has(id)) {
        this.logger.info('Cluster dissolved', {
          clusterId: id,
          members: cluster.members,
          lifespan: Date.now() - cluster.formedAt,
        })
      }
    }
  }
}
