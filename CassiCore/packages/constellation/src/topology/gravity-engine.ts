/**
 * Gravity Engine — Computes attraction forces between Helix sessions
 * based on LLM embedding similarity, file overlap, and approach alignment.
 *
 * HOW: On each tick (triggered by a digest update), the engine:
 *   1. Embeds the updated Helix's goal/findings via EmbeddingService
 *   2. Computes pairwise similarity scores with all other active Helixes
 *   3. Converts similarity to attractive force
 *   4. Applies force to velocity, velocity to position (Verlet-like integration)
 *   5. Applies friction to prevent unbounded acceleration
 *
 * The engine does NOT decide when to link — that's the LinkManager's job.
 * It only maintains positions and computes distances.
 */

import type { ILogger } from '../vendor/types/interfaces.js'
import type { EmbeddingService } from '@cassicore/embeddings'
import type { BranchDigest } from '../corpus-types.js'
import type { TopologyEmbeddingCache } from './embedding-cache.js'
import type {
  GravityConfig,
  HelixPosition,
  HelixTopologyState,
} from './topology-types.js'

/**
 * Dependencies for the GravityEngine.
 */
export interface GravityEngineDeps {
  embeddingService: EmbeddingService
  logger: ILogger
  config: GravityConfig
  /**
   * Optional topology-scoped embedding cache.
   * When provided, the engine routes embed() calls through the cache
   * for content-change detection (skips re-embedding unchanged text).
   * When absent, calls embeddingService.embed() directly (original behavior).
   */
  embeddingCache?: TopologyEmbeddingCache
}

export class GravityEngine {
  private states = new Map<string, HelixTopologyState>()
  private deps: GravityEngineDeps
  private logger: ILogger
  private tickCount = 0

  constructor(deps: GravityEngineDeps) {
    this.deps = deps
    this.logger = deps.logger.child?.('gravity-engine') ?? deps.logger
  }

  /**
   * Register a new Helix in the topology.
   * Initial position is derived from the goal embedding projected to 2D.
   * If embedding fails, falls back to random placement.
   */
  async registerHelix(helixId: string, digest: BranchDigest): Promise<void> {
    if (this.states.has(helixId)) return

    let goalEmbedding: number[] | null = null
    try {
      goalEmbedding = this.deps.embeddingCache
        ? await this.deps.embeddingCache.getEmbedding(helixId, 'goal', digest.goalSummary)
        : await this.deps.embeddingService.embed(digest.goalSummary, 'document')
    } catch (err) {
      this.logger.warn('Failed to embed goal for initial placement', {
        helixId, error: String(err),
      })
    }

    // WHY: Project embedding to 2D for initial position.
    // Use first two principal components of the embedding vector.
    // If no embedding, use deterministic hash-based placement to avoid collisions.
    const pos = goalEmbedding
      ? this.projectTo2D(goalEmbedding)
      : this.hashPosition(helixId)

    const state: HelixTopologyState = {
      helixId,
      position: { helixId, x: pos.x, y: pos.y, vx: 0, vy: 0 },
      goalEmbedding,
      findingsEmbedding: null,
      filesActive: [...digest.filesActive],
      approach: digest.approach,
      active: true,
      updatedAt: Date.now(),
    }

    this.states.set(helixId, state)
    this.logger.info('Helix registered in topology', {
      helixId, x: pos.x.toFixed(3), y: pos.y.toFixed(3),
    })
  }

  /**
   * Handle a digest update — re-embed, recalculate forces, update positions.
   * This is the main tick entry point, called by the TopologyGraph when
   * a BranchDigest update arrives from CorpusTree.
   */
  async onDigestUpdate(helixId: string, digest: BranchDigest): Promise<void> {
    let state = this.states.get(helixId)
    if (!state) {
      await this.registerHelix(helixId, digest)
      state = this.states.get(helixId)!
    }

    // WHY: Re-embed on digest update because findings may have changed
    // significantly since last tick. Goal embedding is stable, so only
    // re-embed if it was null (failed on registration).
    // When embeddingCache is present, it detects unchanged content via
    // FNV-1a hash and skips the embed() call entirely.
    const embeddingPromises: Promise<void>[] = []

    if (!state.goalEmbedding) {
      const goalPromise = this.deps.embeddingCache
        ? this.deps.embeddingCache.getEmbedding(helixId, 'goal', digest.goalSummary)
        : this.deps.embeddingService.embed(digest.goalSummary, 'document')

      embeddingPromises.push(
        goalPromise
          .then(emb => { state!.goalEmbedding = emb })
          .catch(() => { /* goal embedding optional */ }),
      )
    }

    const findingsText = (digest.keyFindings || []).join(' | ')
    if (findingsText.length > 10) {
      const findingsPromise = this.deps.embeddingCache
        ? this.deps.embeddingCache.getEmbedding(helixId, 'findings', findingsText)
        : this.deps.embeddingService.embed(findingsText, 'document')

      embeddingPromises.push(
        findingsPromise
          .then(emb => { state!.findingsEmbedding = emb })
          .catch(() => { /* findings embedding optional */ }),
      )
    }

    await Promise.all(embeddingPromises)

    // Update non-embedding state
    state.filesActive = [...digest.filesActive]
    state.approach = digest.approach
    state.updatedAt = Date.now()

    // Run physics tick for ALL active positions
    this.tick()
  }

  /**
   * Mark a Helix as inactive (completed/failed/cancelled).
   * Inactive Helixes stop attracting but their positions remain
   * for cluster history purposes.
   */
  deregisterHelix(helixId: string): void {
    const state = this.states.get(helixId)
    if (state) {
      state.active = false
      state.position.vx = 0
      state.position.vy = 0
    }
  }

  /**
   * Get the current position of a Helix.
   */
  getPosition(helixId: string): HelixPosition | undefined {
    return this.states.get(helixId)?.position
  }

  /**
   * Get all current positions (active and inactive).
   */
  getAllPositions(): HelixPosition[] {
    return Array.from(this.states.values()).map(s => ({ ...s.position }))
  }

  /**
   * Get the Euclidean distance between two Helixes.
   * Returns Infinity if either doesn't exist.
   */
  getDistance(helixIdA: string, helixIdB: string): number {
    const a = this.states.get(helixIdA)
    const b = this.states.get(helixIdB)
    if (!a || !b) return Infinity
    return Math.sqrt(
      (a.position.x - b.position.x) ** 2 +
      (a.position.y - b.position.y) ** 2,
    )
  }

  /**
   * Compute composite similarity between two Helixes (0-1).
   * Used by the LinkManager for threshold checks.
   */
  computeSimilarity(helixIdA: string, helixIdB: string): number {
    const a = this.states.get(helixIdA)
    const b = this.states.get(helixIdB)
    if (!a || !b) return 0

    const w = this.deps.config.weights
    const cosine = this.deps.embeddingCache
      ? (x: number[] | null, y: number[] | null) => this.deps.embeddingCache!.cosineSimilarity(x, y)
      : (x: number[] | null, y: number[] | null) => this.deps.embeddingService.cosineSimilarity(x, y)
    let score = 0

    // Goal similarity via cosine
    if (a.goalEmbedding && b.goalEmbedding) {
      score += w.goalSimilarity * cosine(a.goalEmbedding, b.goalEmbedding)
    }

    // Findings similarity via cosine
    if (a.findingsEmbedding && b.findingsEmbedding) {
      score += w.findingsSimilarity * cosine(a.findingsEmbedding, b.findingsEmbedding)
    }

    // File overlap via Jaccard index
    if (a.filesActive.length > 0 || b.filesActive.length > 0) {
      const setA = new Set(a.filesActive)
      const setB = new Set(b.filesActive)
      const intersection = a.filesActive.filter(f => setB.has(f)).length
      const union = new Set([...a.filesActive, ...b.filesActive]).size
      score += w.fileOverlap * (union > 0 ? intersection / union : 0)
    }

    // Approach alignment bonus
    if (a.approach === b.approach) {
      score += w.approachAlignment
    }

    return Math.min(score, 1.0)
  }

  /**
   * Get all pairwise distances as a nested map.
   */
  getDistanceMatrix(): Map<string, Map<string, number>> {
    const matrix = new Map<string, Map<string, number>>()
    const ids = Array.from(this.states.keys())

    for (const idA of ids) {
      const row = new Map<string, number>()
      for (const idB of ids) {
        if (idA !== idB) {
          row.set(idB, this.getDistance(idA, idB))
        }
      }
      matrix.set(idA, row)
    }

    return matrix
  }

  /**
   * Get the number of ticks processed.
   */
  getTickCount(): number {
    return this.tickCount
  }

  /**
   * Get all topology states (for testing/inspection).
   */
  getStates(): Map<string, HelixTopologyState> {
    return this.states
  }

  // --- Private ---

  /**
   * Run one physics tick: compute forces, update velocities, update positions.
   *
   * HOW: N-body simulation with O(n^2) pairwise force computation.
   * Fine for Constellation scale (typically 2-16 Helixes).
   */
  private tick(): void {
    this.tickCount++
    const { friction, forceScale, minDistance, maxVelocity, repulsionStrength } = this.deps.config
    const activeStates = Array.from(this.states.values()).filter(s => s.active)

    if (activeStates.length < 2) return

    // Compute net force on each active Helix
    const forces = new Map<string, { fx: number; fy: number }>()
    for (const state of activeStates) {
      forces.set(state.helixId, { fx: 0, fy: 0 })
    }

    for (let i = 0; i < activeStates.length; i++) {
      for (let j = i + 1; j < activeStates.length; j++) {
        const a = activeStates[i]
        const b = activeStates[j]

        const similarity = this.computeSimilarity(a.helixId, b.helixId)

        const dx = b.position.x - a.position.x
        const dy = b.position.y - a.position.y
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), minDistance)

        // HOW: Net force = attraction - repulsion.
        //   Attraction: similarity-weighted, pulls similar nodes together (∝ similarity/dist)
        //   Repulsion:  constant inverse-square, pushes all nodes apart (∝ 1/dist²)
        // This creates equilibrium distances that depend on similarity:
        //   High-similarity pairs settle close (attraction dominates)
        //   Low-similarity pairs settle far apart (repulsion dominates)
        const attractForce = forceScale * similarity / dist
        const repulseForce = repulsionStrength / (dist * dist)
        const netForce = attractForce - repulseForce

        const fx = netForce * (dx / dist)
        const fy = netForce * (dy / dist)

        // Newton's third law: equal and opposite
        const fa = forces.get(a.helixId)!
        const fb = forces.get(b.helixId)!
        fa.fx += fx
        fa.fy += fy
        fb.fx -= fx
        fb.fy -= fy
      }
    }

    // Apply forces → velocity → position
    for (const state of activeStates) {
      const force = forces.get(state.helixId)!
      const pos = state.position

      // Update velocity: add force, apply friction
      pos.vx = (pos.vx + force.fx) * (1 - friction)
      pos.vy = (pos.vy + force.fy) * (1 - friction)

      // Clamp velocity
      const speed = Math.sqrt(pos.vx * pos.vx + pos.vy * pos.vy)
      if (speed > maxVelocity) {
        const scale = maxVelocity / speed
        pos.vx *= scale
        pos.vy *= scale
      }

      // Update position
      pos.x += pos.vx
      pos.y += pos.vy
    }
  }

  /**
   * Project a high-dimensional embedding vector to 2D coordinates.
   *
   * HOW: Use a simple but effective approach — take the first two
   * components of the embedding after L2 normalization. This preserves
   * the most significant variance in the embedding space. More
   * sophisticated projection (t-SNE, UMAP) would be overkill for
   * the small number of Helixes in a Constellation.
   */
  private projectTo2D(embedding: number[]): { x: number; y: number } {
    if (embedding.length < 2) return { x: 0, y: 0 }

    // L2 normalize first
    let norm = 0
    for (const v of embedding) norm += v * v
    norm = Math.sqrt(norm)
    if (norm === 0) return { x: 0, y: 0 }

    // Scale to reasonable range (0-10)
    return {
      x: (embedding[0] / norm) * 10,
      y: (embedding[1] / norm) * 10,
    }
  }

  /**
   * Deterministic hash-based position for fallback when embedding fails.
   */
  private hashPosition(helixId: string): { x: number; y: number } {
    let hash = 0
    for (let i = 0; i < helixId.length; i++) {
      hash = ((hash << 5) - hash) + helixId.charCodeAt(i)
      hash |= 0
    }
    // Spread across 0-10 range
    const x = ((hash & 0xFFFF) / 0xFFFF) * 10
    const y = (((hash >> 16) & 0xFFFF) / 0xFFFF) * 10
    return { x, y }
  }
}
