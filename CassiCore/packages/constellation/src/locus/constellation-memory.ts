/**
 * Locus Memory — Persistent experiential learning across Constellations
 *
 * The memory store serves the three integration points of the feedback loop:
 *
 *   1. write()   — Called when a spark kindles → creates provisional memory
 *   2. recall()  — Called during luminance scoring → returns novelty modulation
 *   3. update()  — Called when radiance responses arrive → adjusts confidence
 *
 * Memories are content-matched: if the same discovery emerges in a later
 * constellation, it merges with (boosts) the existing memory rather than
 * creating a duplicate. This is how experience accumulates.
 *
 * In-memory cache for fast scoring, backed by ConstellationStore for persistence.
 * The cache loads on construction and is maintained in sync with the DB.
 */

import type { ILogger } from '../vendor/types/interfaces.js'
import type { Spark, KindlingEvent, RadianceResponse } from './locus-types.js'
import type {
  LocusMemoryEntry,
  LocusMemoryConfig,
  LocusMemoryStats,
  MemoryPhase,
  MemoryFeedback,
  MemoryRecall,
} from './memory-types.js'
import { DEFAULT_MEMORY_CONFIG } from './memory-types.js'

let memoryCounter = 0
function nextMemoryId(): string {
  return `lmem-${++memoryCounter}-${Date.now().toString(36)}`
}


/**
 * Persistence interface — injected by the Locus to decouple from SQLite details.
 * ConstellationStore implements this.
 */
export interface LocusMemoryPersistence {
  loadMemories(): LocusMemoryEntry[]
  saveMemory(entry: LocusMemoryEntry): void
  updateMemory(entry: LocusMemoryEntry): void
  deleteMemory(id: string): void
}


export interface LocusMemoryDeps {
  logger: ILogger
  config?: LocusMemoryConfig
  persistence?: LocusMemoryPersistence
}


export class LocusMemory {
  private memories = new Map<string, LocusMemoryEntry>()
  private config: LocusMemoryConfig
  private logger: ILogger
  private persistence: LocusMemoryPersistence | null

  constructor(deps: LocusMemoryDeps) {
    this.config = deps.config ?? DEFAULT_MEMORY_CONFIG
    this.logger = deps.logger.child?.('locus-memory') ?? deps.logger
    this.persistence = deps.persistence ?? null

    if (this.persistence && this.config.enabled) {
      this.loadFromPersistence()
    }

    this.logger.info('LocusMemory initialized', {
      enabled: this.config.enabled,
      loaded: this.memories.size,
    })
  }


  /**
   * Create a memory from a kindling event.
   * Called by the Locus facade when a spark kindles.
   *
   * If existing memory has sufficiently similar content, merges instead
   * of creating a duplicate (confirmation strengthens memory).
   */
  write(event: KindlingEvent, sessionId: string): LocusMemoryEntry {
    const spark = event.spark

    // Check for existing similar memory
    const existing = this.findSimilar(spark.content)
    if (existing) {
      return this.merge(existing, event, sessionId)
    }

    // Create new provisional memory
    const entry: LocusMemoryEntry = {
      id: nextMemoryId(),
      content: spark.content,
      memoryType: spark.type,
      confidence: spark.luminance.composite * 0.5, // Initial confidence = half of luminance
      luminance: spark.luminance.composite,
      phase: 'provisional',
      originSessionId: sessionId,
      sourceHelixId: spark.sourceHelixId,
      sourceGoal: spark.sourceGoal,
      relevantFiles: [...spark.relevantFiles],
      confirmations: 0,
      contradictions: 0,
      recallCount: 0,
      createdAt: Date.now(),
      lastRecalledAt: null,
      lastUpdatedAt: Date.now(),
    }

    this.memories.set(entry.id, entry)
    this.persistence?.saveMemory(entry)

    this.logger.info('Memory created', {
      id: entry.id,
      type: entry.memoryType,
      confidence: entry.confidence.toFixed(3),
      phase: entry.phase,
    })

    this.prune()
    return entry
  }


  /**
   * Recall relevant memories for a spark being scored.
   * Called by the KindlingEngine during luminance computation.
   *
   * Returns MemoryRecalls with novelty modulation:
   *   - Confirming memories (same type, similar content) → reduce novelty
   *     ("we already know this")
   *   - Contradicting memories (different conclusion) → boost novelty
   *     ("this challenges what we knew")
   */
  recall(spark: Spark): MemoryRecall[] {
    if (!this.config.enabled || this.memories.size === 0) return []

    const recalls: MemoryRecall[] = []
    const now = Date.now()

    for (const memory of this.memories.values()) {
      if (memory.phase === 'invalidated') continue

      const relevance = this.contentSimilarity(spark.content, memory.content)
      if (relevance < this.config.matchThreshold) continue

      // Determine novelty modulation
      let noveltyModulation: number
      if (memory.memoryType === spark.type) {
        // Same type + similar content → confirmation → reduce novelty
        noveltyModulation = -this.config.confirmingNoveltyReduction * relevance * memory.confidence
      } else if (
        (spark.type === 'tension' && memory.memoryType === 'convergence') ||
        (spark.type === 'convergence' && memory.memoryType === 'tension')
      ) {
        // Direct contradiction between tension and convergence → boost novelty
        noveltyModulation = this.config.contradictingNoveltyBoost * relevance * memory.confidence
      } else {
        // Related but different type → mild novelty reduction
        noveltyModulation = -this.config.confirmingNoveltyReduction * relevance * memory.confidence * 0.3
      }

      recalls.push({
        memory,
        relevance,
        noveltyModulation,
      })

      // Update recall stats (in-memory only, batched to persistence on consolidate)
      memory.recallCount++
      memory.lastRecalledAt = now
    }

    // Sort by relevance, take top N
    recalls.sort((a, b) => b.relevance - a.relevance)
    return recalls.slice(0, this.config.maxRecallsPerSpark)
  }


  /**
   * Update memory confidence based on radiance responses.
   * Called by the Locus facade after Radiance tracks responses.
   *
   * The loop closes:  memory → luminance → kindle → broadcast → response → memory
   */
  applyFeedback(responses: RadianceResponse[], radianceSourceSparkContent: Map<string, string>): MemoryFeedback[] {
    if (!this.config.enabled) return []

    const feedbacks: MemoryFeedback[] = []
    const now = Date.now()

    for (const response of responses) {
      // Find the memory that matches the broadcast's source spark
      const sparkContent = radianceSourceSparkContent.get(response.radianceId)
      if (!sparkContent) continue

      const matchingMemory = this.findSimilar(sparkContent)
      if (!matchingMemory) continue

      let feedbackType: MemoryFeedback['feedbackType']
      let confidenceDelta: number

      switch (response.responseType) {
        case 'incorporated':
          feedbackType = 'confirmation'
          confidenceDelta = this.config.confirmationBoost
          matchingMemory.confirmations++
          break
        case 'contradicted':
          feedbackType = 'contradiction'
          confidenceDelta = -this.config.contradictionPenalty
          matchingMemory.contradictions++
          break
        case 'noted':
        case 'ignored':
        default:
          feedbackType = 'neutral'
          confidenceDelta = -this.config.idleDecay
          break
      }

      // Apply confidence delta with bounds
      matchingMemory.confidence = Math.max(0, Math.min(1,
        matchingMemory.confidence + confidenceDelta,
      ))
      matchingMemory.lastUpdatedAt = now

      // Phase transitions
      this.updatePhase(matchingMemory)

      // Persist
      this.persistence?.updateMemory(matchingMemory)

      feedbacks.push({
        memoryId: matchingMemory.id,
        radianceId: response.radianceId,
        helixId: response.helixId,
        feedbackType,
        evidence: response.evidence,
        timestamp: now,
      })
    }

    if (feedbacks.length > 0) {
      this.logger.info('Memory feedback applied', {
        count: feedbacks.length,
        confirmations: feedbacks.filter(f => f.feedbackType === 'confirmation').length,
        contradictions: feedbacks.filter(f => f.feedbackType === 'contradiction').length,
        neutral: feedbacks.filter(f => f.feedbackType === 'neutral').length,
      })
    }

    return feedbacks
  }


  /**
   * Consolidate memories at the end of a constellation run.
   * Provisional memories that survived → confirmed.
   * Confirmed memories with high confidence → consolidated.
   * Low-confidence memories → invalidated.
   */
  consolidate(): { promoted: number; invalidated: number } {
    let promoted = 0
    let invalidated = 0

    for (const memory of this.memories.values()) {
      if (memory.phase === 'invalidated') continue

      if (memory.confidence < this.config.invalidationThreshold) {
        memory.phase = 'invalidated'
        memory.lastUpdatedAt = Date.now()
        this.persistence?.updateMemory(memory)
        invalidated++
        continue
      }

      if (memory.phase === 'provisional' && memory.confirmations > 0) {
        memory.phase = 'confirmed'
        memory.lastUpdatedAt = Date.now()
        this.persistence?.updateMemory(memory)
        promoted++
      } else if (memory.phase === 'confirmed' && memory.confidence > 0.7) {
        memory.phase = 'consolidated'
        memory.lastUpdatedAt = Date.now()
        this.persistence?.updateMemory(memory)
        promoted++
      }
    }

    this.logger.info('Memory consolidation', {
      promoted,
      invalidated,
      total: this.memories.size,
    })

    return { promoted, invalidated }
  }

  /**
   * Apply idle decay to all memories. Called once per sweep.
   * Memories that aren't being recalled slowly fade.
   */
  decayIdle(): void {
    if (!this.config.enabled) return

    for (const memory of this.memories.values()) {
      if (memory.phase === 'invalidated') continue
      if (memory.phase === 'consolidated') continue // consolidated memories don't idle-decay

      memory.confidence = Math.max(0, memory.confidence - this.config.idleDecay)
      if (memory.confidence < this.config.invalidationThreshold) {
        memory.phase = 'invalidated'
        memory.lastUpdatedAt = Date.now()
        this.persistence?.updateMemory(memory)
      }
    }
  }


  getAll(): LocusMemoryEntry[] {
    return [...this.memories.values()]
  }

  getActive(): LocusMemoryEntry[] {
    return [...this.memories.values()].filter(m => m.phase !== 'invalidated')
  }

  getStats(): LocusMemoryStats {
    const entries = [...this.memories.values()]
    const byPhase: Record<MemoryPhase, number> = {
      provisional: 0, confirmed: 0, consolidated: 0, invalidated: 0,
    }
    const byType: Record<string, number> = {}
    let totalConfidence = 0
    let totalRecalls = 0
    let totalConfirmations = 0
    let totalContradictions = 0

    for (const entry of entries) {
      byPhase[entry.phase]++
      byType[entry.memoryType] = (byType[entry.memoryType] || 0) + 1
      totalConfidence += entry.confidence
      totalRecalls += entry.recallCount
      totalConfirmations += entry.confirmations
      totalContradictions += entry.contradictions
    }

    return {
      totalMemories: entries.length,
      byPhase,
      byType,
      avgConfidence: entries.length > 0 ? totalConfidence / entries.length : 0,
      totalRecalls,
      totalConfirmations,
      totalContradictions,
    }
  }

  /**
   * Reset all state (for testing).
   */
  reset(): void {
    this.memories.clear()
    memoryCounter = 0
  }


  /**
   * Load memories from persistence into the in-memory cache.
   */
  private loadFromPersistence(): void {
    if (!this.persistence) return

    try {
      const entries = this.persistence.loadMemories()
      for (const entry of entries) {
        if (entry.phase !== 'invalidated') {
          this.memories.set(entry.id, entry)
        }
      }
    } catch (err) {
      this.logger.error('Failed to load memories from persistence', { error: String(err) })
    }
  }

  /**
   * Find existing memory with similar content.
   * Uses a lightweight token-overlap similarity metric.
   */
  private findSimilar(content: string): LocusMemoryEntry | null {
    let bestMatch: LocusMemoryEntry | null = null
    let bestScore = 0

    for (const memory of this.memories.values()) {
      if (memory.phase === 'invalidated') continue

      const score = this.contentSimilarity(content, memory.content)
      if (score > bestScore && score >= this.config.matchThreshold) {
        bestScore = score
        bestMatch = memory
      }
    }

    return bestMatch
  }

  /**
   * Merge a kindling event into an existing memory (confirmation).
   * Boosts confidence and updates metadata.
   */
  private merge(existing: LocusMemoryEntry, event: KindlingEvent, _sessionId: string): LocusMemoryEntry {
    existing.confidence = Math.min(1, existing.confidence + this.config.confirmationBoost)
    existing.confirmations++
    existing.lastUpdatedAt = Date.now()
    this.updatePhase(existing)
    this.persistence?.updateMemory(existing)

    this.logger.info('Memory merged (re-kindled)', {
      id: existing.id,
      confidence: existing.confidence.toFixed(3),
      confirmations: existing.confirmations,
      phase: existing.phase,
    })

    return existing
  }

  /**
   * Token-overlap similarity between two content strings.
   * Fast, deterministic, no embeddings needed.
   *
   * Tokenizes on whitespace + punctuation, computes Jaccard coefficient
   * with a length-weighting bonus for shared longer tokens.
   */
  private contentSimilarity(a: string, b: string): number {
    const tokensA = this.tokenize(a)
    const tokensB = this.tokenize(b)

    if (tokensA.size === 0 || tokensB.size === 0) return 0

    let intersection = 0
    for (const token of tokensA) {
      if (tokensB.has(token)) intersection++
    }

    const union = tokensA.size + tokensB.size - intersection
    if (union === 0) return 0

    return intersection / union
  }

  /**
   * Tokenize content into a set of normalized tokens.
   */
  private tokenize(content: string): Set<string> {
    return new Set(
      content
        .toLowerCase()
        .replace(/[^\w\s]/g, ' ')
        .split(/\s+/)
        .filter(t => t.length > 2),
    )
  }

  /**
   * Update memory phase based on current state.
   */
  private updatePhase(memory: LocusMemoryEntry): void {
    if (memory.confidence < this.config.invalidationThreshold) {
      memory.phase = 'invalidated'
    } else if (memory.phase === 'provisional' && memory.confirmations > 0) {
      memory.phase = 'confirmed'
    } else if (memory.phase === 'confirmed' && memory.confidence > 0.7) {
      memory.phase = 'consolidated'
    }
  }

  /**
   * Prune memories if over capacity.
   * Removes invalidated first, then lowest-confidence.
   */
  private prune(): void {
    if (this.memories.size <= this.config.maxMemories) return

    const entries = [...this.memories.values()]
      .sort((a, b) => {
        // Invalidated always first to prune
        if (a.phase === 'invalidated' && b.phase !== 'invalidated') return -1
        if (b.phase === 'invalidated' && a.phase !== 'invalidated') return 1
        // Then lowest confidence
        return a.confidence - b.confidence
      })

    const toRemove = entries.slice(0, this.memories.size - this.config.maxMemories)
    for (const entry of toRemove) {
      this.memories.delete(entry.id)
      this.persistence?.deleteMemory(entry.id)
    }

    if (toRemove.length > 0) {
      this.logger.info('Memories pruned', { removed: toRemove.length, remaining: this.memories.size })
    }
  }
}
