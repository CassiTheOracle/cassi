/**
 * Topology Graph — Orchestrates gravity, links, and clusters into
 * a unified spatial coordination layer for Helix sessions.
 *
 * This is the main entry point consumed by the Corpus. It:
 *   1. Receives BranchDigest updates from the CorpusTree
 *   2. Drives the GravityEngine to update positions
 *   3. Runs the LinkManager to form/dissolve links
 *   4. Runs the ClusterTracker to identify groups
 *   5. Produces TopologySnapshot for Corpus consumption
 *
 * Event-driven: only ticks when a digest update arrives.
 * The Corpus reads the latest snapshot during its sweep loop.
 */

import type { ILogger, IEventBus } from '../vendor/types/interfaces.js'
import type { EmbeddingService } from '@cassicore/embeddings'
import type { BranchDigest } from '../corpus-types.js'
import { GravityEngine } from './gravity-engine.js'
import { LinkManager } from './link-manager.js'
import { ClusterTracker } from './cluster-tracker.js'
import { TopologyEmbeddingCache } from './embedding-cache.js'
import type { BrainstemBridge } from './brainstem-bridge.js'
import type {
  TopologyGraphConfig,
  TopologySnapshot,
  TopologyCluster,
  TopologyLink,
  MergeDepth,
} from './topology-types.js'
import { DEFAULT_TOPOLOGY_CONFIG } from './topology-types.js'


export interface TopologyGraphDeps {
  embeddingService: EmbeddingService
  logger: ILogger
  eventBus?: IEventBus
  config?: TopologyGraphConfig
  bridge?: BrainstemBridge
  /** Callback to persist topology events to the ConstellationStore audit trail */
  persistEvent?: (type: string, entity: string | null, message: string, data?: unknown) => void
}

export class TopologyGraph {
  private gravityEngine: GravityEngine
  private linkManager: LinkManager
  private clusterTracker: ClusterTracker
  private embeddingCache: TopologyEmbeddingCache
  private bridge?: BrainstemBridge
  private config: TopologyGraphConfig
  private logger: ILogger
  private eventBus?: IEventBus
  private persistEvent?: (type: string, entity: string | null, message: string, data?: unknown) => void
  private activeHelixIds = new Set<string>()
  private constellationId?: string
  /** Snapshot of link states before each evaluation, for diff detection */
  private previousLinkKeys = new Set<string>()
  /** Snapshot of link depths before each evaluation */
  private previousLinkDepths = new Map<string, MergeDepth>()

  constructor(deps: TopologyGraphDeps) {
    this.config = deps.config ?? DEFAULT_TOPOLOGY_CONFIG
    this.logger = deps.logger.child?.('topology-graph') ?? deps.logger
    this.eventBus = deps.eventBus
    this.bridge = deps.bridge
    this.persistEvent = deps.persistEvent

    this.embeddingCache = new TopologyEmbeddingCache(deps.embeddingService, this.logger)

    this.gravityEngine = new GravityEngine({
      embeddingService: deps.embeddingService,
      logger: this.logger,
      config: this.config.gravity,
      embeddingCache: this.embeddingCache,
    })

    this.linkManager = new LinkManager({
      gravityEngine: this.gravityEngine,
      logger: this.logger,
      config: this.config.links,
    })

    this.clusterTracker = new ClusterTracker({
      linkManager: this.linkManager,
      gravityEngine: this.gravityEngine,
      logger: this.logger,
    })

    this.logger.info('TopologyGraph initialized', {
      enabled: this.config.enabled,
      linkThreshold: this.config.links.linkThreshold,
      unlinkThreshold: this.config.links.unlinkThreshold,
    })
  }

  /**
   * Set the constellation ID for event emission.
   */
  setConstellationId(id: string): void {
    this.constellationId = id
  }

  /**
   * Handle a BranchDigest update from the CorpusTree.
   * This is the main tick trigger — drives the entire topology update cycle.
   *
   * Called by the Corpus or CorpusTree when a Brainstem publishes a digest.
   */
  async onDigestUpdate(helixId: string, digest: BranchDigest): Promise<void> {
    if (!this.config.enabled) return

    // Track active Helixes
    this.activeHelixIds.add(helixId)

    // 1. Update gravity (embeds + physics tick)
    await this.gravityEngine.onDigestUpdate(helixId, digest)

    // 2. Snapshot link state before evaluation (for bridge diff detection)
    this.snapshotLinkState()

    // 3. Evaluate links (form/dissolve/promote)
    const activeIds = Array.from(this.activeHelixIds)
    this.linkManager.evaluate(activeIds)

    // 4. Drive bridge based on link changes
    this.driveBridge()

    // 5. Update clusters (connected components)
    this.clusterTracker.update(activeIds)

    // 6. Push bridged context (respects cooldown internally)
    if (this.bridge) {
      this.bridge.pushContext()
    }

    // 7. Emit topology event for external observers
    this.emitTopologyUpdate(helixId)
  }

  /**
   * Register a new Helix in the topology.
   * Called when a new Helix branch is registered in the CorpusTree.
   */
  async registerHelix(helixId: string, digest: BranchDigest): Promise<void> {
    if (!this.config.enabled) return

    this.activeHelixIds.add(helixId)
    await this.gravityEngine.registerHelix(helixId, digest)
  }

  /**
   * Deregister a Helix from the topology.
   * Called when a Helix branch closes (completed/cancelled/failed).
   */
  deregisterHelix(helixId: string): void {
    this.activeHelixIds.delete(helixId)
    this.gravityEngine.deregisterHelix(helixId)
    this.linkManager.removeHelix(helixId)
    this.bridge?.removeHelix(helixId)
    this.embeddingCache.removeHelix(helixId)
  }

  /**
   * Get a complete topology snapshot for Corpus consumption.
   * The Corpus reads this during its sweep loop as an additional reasoning signal.
   */
  getSnapshot(): TopologySnapshot {
    return {
      positions: this.gravityEngine.getAllPositions(),
      links: this.linkManager.getAllLinks(),
      clusters: this.clusterTracker.getAllClusters(),
      distances: this.gravityEngine.getDistanceMatrix(),
      tickCount: this.gravityEngine.getTickCount(),
      snapshotAt: Date.now(),
    }
  }

  // Convenience accessors for the Corpus

  /**
   * Get the cluster a Helix belongs to, if any.
   */
  getClusterFor(helixId: string): TopologyCluster | undefined {
    return this.clusterTracker.getClusterFor(helixId)
  }

  /**
   * Check if two Helixes are in the same cluster.
   */
  areInSameCluster(helixIdA: string, helixIdB: string): boolean {
    return this.clusterTracker.areInSameCluster(helixIdA, helixIdB)
  }

  /**
   * Get the effective merge depth between two Helixes.
   */
  getMergeDepth(helixIdA: string, helixIdB: string): MergeDepth | undefined {
    return this.clusterTracker.getEffectiveMergeDepth(helixIdA, helixIdB)
  }

  /**
   * Get distance between two Helixes.
   */
  getDistance(helixIdA: string, helixIdB: string): number {
    return this.gravityEngine.getDistance(helixIdA, helixIdB)
  }

  /**
   * Get similarity score between two Helixes.
   */
  getSimilarity(helixIdA: string, helixIdB: string): number {
    return this.gravityEngine.computeSimilarity(helixIdA, helixIdB)
  }

  /**
   * Get all links for a specific Helix.
   */
  getLinksFor(helixId: string): TopologyLink[] {
    return this.linkManager.getLinksFor(helixId)
  }

  /**
   * Get neighbors of a Helix (all linked Helixes).
   */
  getNeighbors(helixId: string): string[] {
    return this.linkManager.getNeighbors(helixId)
  }

  /**
   * Whether the topology graph is enabled.
   */
  get enabled(): boolean {
    return this.config.enabled
  }

  /**
   * Access to the underlying gravity engine (for testing).
   */
  get engine(): GravityEngine {
    return this.gravityEngine
  }

  /**
   * Get embedding cache metrics (hits, misses, evictions, hit rate).
   */
  getCacheMetrics() {
    return this.embeddingCache.getMetrics()
  }

  /**
   * Embedding cache hit rate (0-1).
   */
  get cacheHitRate(): number {
    return this.embeddingCache.hitRate
  }

  /**
   * Access to the embedding cache (for testing/inspection).
   */
  get cache(): TopologyEmbeddingCache {
    return this.embeddingCache
  }

  // --- Private ---

  /**
   * Snapshot the current link state before evaluation.
   * Used to detect new, changed, and dissolved links for bridge management.
   */
  private snapshotLinkState(): void {
    this.previousLinkKeys.clear()
    this.previousLinkDepths.clear()
    for (const link of this.linkManager.getAllLinks()) {
      const key = `${link.helixIdA}::${link.helixIdB}`
      this.previousLinkKeys.add(key)
      this.previousLinkDepths.set(key, link.mergeDepth)
    }
  }

  /**
   * Compare current links to the pre-evaluation snapshot and drive the bridge.
   * Detects: new links, dissolved links, depth changes.
   */
  private driveBridge(): void {
    if (!this.bridge) return

    const currentLinks = this.linkManager.getAllLinks()
    const currentLinkKeys = new Set<string>()

    for (const link of currentLinks) {
      const key = `${link.helixIdA}::${link.helixIdB}`
      currentLinkKeys.add(key)

      if (!this.previousLinkKeys.has(key)) {
        // New link — activate bridge
        this.bridge.activateLink(link.helixIdA, link.helixIdB, link.mergeDepth)
      } else {
        // Existing link — check for depth change
        const prevDepth = this.previousLinkDepths.get(key)
        if (prevDepth && prevDepth !== link.mergeDepth) {
          this.bridge.updateDepth(link.helixIdA, link.helixIdB, link.mergeDepth)
        }
      }
    }

    // Dissolved links — deactivate bridge
    for (const prevKey of this.previousLinkKeys) {
      if (!currentLinkKeys.has(prevKey)) {
        const [idA, idB] = prevKey.split('::')
        this.bridge.deactivateLink(idA, idB)
      }
    }
  }

  private emitTopologyUpdate(helixId: string): void {
    if (!this.constellationId) return

    const eventData = {
      helixId,
      tickCount: this.gravityEngine.getTickCount(),
      linkCount: this.linkManager.getAllLinks().length,
      clusterCount: this.clusterTracker.getAllClusters().length,
    }

    // Emit to EventBus for live subscribers
    if (this.eventBus) {
      try {
        void this.eventBus.emit({
          type: 'topology:updated',
          constellationId: this.constellationId,
          ...eventData,
          timestamp: new Date(),
        })
      } catch (_err) {
        // Event emission is best-effort
      }
    }

    // Persist to ConstellationStore for audit trail
    if (this.persistEvent) {
      try {
        this.persistEvent(
          'topology:updated',
          helixId,
          `Topology tick ${eventData.tickCount}: ${eventData.linkCount} links, ${eventData.clusterCount} clusters`,
          eventData,
        )
      } catch (_err) {
        // Persistence is best-effort
      }
    }
  }
}
