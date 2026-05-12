/**
 * Memory Injection Service — Branch-level Memory Continuity for Helix Startup
 *
 * Uses the MnemicField for associative retrieval: when a new Helix branch is
 * spawned, the goal text is used as a kindling query. The MnemicField generates
 * an embedding, performs spreading activation across the engram graph, and
 * optionally reranks candidates via LLM. This replaces the deprecated stop-word
 * heuristic that produced 0% relevant results. (c-36 postmortem BUG L redesign)
 *
 * Fallback: if MnemicField is unavailable, falls back to the deprecated IMemory
 * interface with the raw goal as the search query.
 */

import type { IMemory } from '../../../types/intelligence.js'
import type { MnemicField, MnemicRetrievalHit } from '../mnemic-field/index.js'
import { GraphAttnPropagator } from '../mnemic-field/graph-attn-propagator.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { BranchMemoryContext, InjectedMemory } from './corpus-types.js'

/**
 * Configuration for memory injection behavior.
 */
export interface MemoryInjectionConfig {
  /** Maximum memories to inject per branch. Default: 5 */
  maxMemories: number
  /** Max memory content length (chars). Default: 2000 */
  maxContentLength: number
}

export const DEFAULT_MEMORY_INJECTION_CONFIG: MemoryInjectionConfig = {
  maxMemories: 5,
  maxContentLength: 2000,
}

/**
 * Meditation memory injection — broader associations.
 */
export const MEDITATION_MEMORY_INJECTION_CONFIG: Partial<MemoryInjectionConfig> = {
  maxMemories: 10,
  maxContentLength: 3000,
}

/**
 * Memory Injection Service — Provides branch-level memory continuity.
 *
 * Primary path: MnemicField.retrieve() — associative retrieval via kindling.
 * Fallback path: IMemory.search() with raw goal text (deprecated).
 */
export class MemoryInjectionService {
  private mnemicField: MnemicField | undefined
  private legacyMemory: IMemory | undefined
  private graphPropagator: GraphAttnPropagator | undefined
  private config: MemoryInjectionConfig
  private logger: ILogger

  constructor(
    fieldOrMemory: MnemicField | IMemory,
    logger: ILogger,
    config?: Partial<MemoryInjectionConfig>,
  ) {
    this.config = { ...DEFAULT_MEMORY_INJECTION_CONFIG, ...config }
    this.logger = logger.child('MemoryInjection')

    // Discriminate: MnemicField has a `retrieve` method; IMemory has `store` + `search`.
    if ('retrieve' in fieldOrMemory && typeof fieldOrMemory.retrieve === 'function') {
      this.mnemicField = fieldOrMemory as MnemicField
      this.graphPropagator = new GraphAttnPropagator(this.mnemicField.getCortex())
    } else {
      this.legacyMemory = fieldOrMemory as IMemory
    }
  }

  /**
   * Inject memories for a new branch based on its goal.
   * Returns a BranchMemoryContext with relevant memories, or undefined if none found.
   */
  async injectForBranch(
    helixId: string,
    goal: string,
    parentId?: string
  ): Promise<BranchMemoryContext | undefined> {
    if (this.mnemicField) {
      return this.injectViaMnemicField(helixId, goal, parentId)
    }
    if (this.legacyMemory) {
      return this.injectViaLegacyMemory(helixId, goal, parentId)
    }
    return undefined
  }

  /**
   * WHY: Primary path — associative retrieval via MnemicField kindling.
   * The goal text is used as a kindling query. The MnemicField generates an
   * embedding, performs spreading activation across the engram graph, and
   * optionally reranks candidates via the LLM reranker. This is topology-aware,
   * embedding-based retrieval that naturally finds related concepts even when
   * keyword overlap is zero. (c-36 postmortem BUG L redesign)
   */
  private async injectViaMnemicField(
    helixId: string,
    goal: string,
    parentId?: string,
  ): Promise<BranchMemoryContext | undefined> {
    const startTime = Date.now()

    this.logger.info('Injecting memories for branch via MnemicField', {
      helixId,
      goalPreview: goal.slice(0, 100),
      parentId,
    })

    try {
      const hits = await this.mnemicField!.retrieve(goal, {
        limit: this.config.maxMemories,
      })

      if (hits.length === 0) {
        this.logger.info('No engrams kindled for branch', { helixId })
        return undefined
      }

      const injectedMemories: InjectedMemory[] = hits
        .slice(0, this.config.maxMemories)
        .map(hit => this.convertHitToInjectedMemory(hit))

      const context: BranchMemoryContext = {
        memories: injectedMemories,
        injectedAt: Date.now(),
        searchQuery: goal.slice(0, 200),
        totalAvailable: hits.length,
      }

      // WHY: Supplement kindling with graph-walked propagation from the top hit.
      // The GraphAttnPropagator walks typed edges (spawned_from, part_of) from
      // the best-matching engram to find structurally related sessions and
      // findings that kindling (embedding-only) might miss.
      const topId = hits[0]?.id
      if (topId && context.memories.length < this.config.maxMemories && this.graphPropagator) {
        try {
          const propagated = this.graphPropagator.propagate({
            seedIds: [topId],
            edgeTypes: ['spawned_from', 'part_of', 'temporal_neighbor'],
            maxHops: 2,
            topN: 3,
            minCharge: 0.05,
          })
          for (const pe of propagated) {
            if (pe.engram.id === topId) continue
            const content = pe.engram.content.slice(0, this.config.maxContentLength)
            const pathSummary = pe.paths
              .map(p => p.hops.map(h => h.edgeType).join(' → '))
              .join(', ')
            context.memories.push({
              content,
              relevance: Math.min(1, pe.charge),
              type: pe.engram.nodeType ?? 'fact',
              createdAt: new Date(pe.engram.createdAt).getTime(),
              tags: [...(pe.engram.tags ?? []), `graph:${pathSummary}`],
            })
            context.totalAvailable!++
          }
        } catch { }
      }

      this.logger.info('MnemicField injection complete', {
        helixId,
        injectedCount: injectedMemories.length,
        totalAvailable: hits.length,
        durationMs: Date.now() - startTime,
        topScore: hits[0]?.score?.toFixed(3) ?? 'n/a',
        topCharge: hits[0]?.charge?.toFixed(3) ?? 'n/a',
      })

      return context
    } catch (error) {
      this.logger.error('MnemicField injection failed', {
        helixId,
        error: String(error),
      })
      return undefined
    }
  }

  /**
   * Fallback path — deprecated IMemory FTS5 search.
   * Uses the raw goal text as the query (no stop-word stripping).
   */
  private async injectViaLegacyMemory(
    helixId: string,
    goal: string,
    parentId?: string,
  ): Promise<BranchMemoryContext | undefined> {
    const startTime = Date.now()

    try {
      const searchResults = await this.legacyMemory!.search(goal.slice(0, 300), {
        limit: this.config.maxMemories * 2,
      })

      if (searchResults.length === 0) {
        this.logger.info('No memories found for branch (legacy)', { helixId })
        return undefined
      }

      const injectedMemories: InjectedMemory[] = searchResults
        .filter(r => r.score >= 0.2)
        .slice(0, this.config.maxMemories)
        .map(r => ({
          content: r.entry.content.length > this.config.maxContentLength
            ? r.entry.content.slice(0, this.config.maxContentLength) + '...'
            : r.entry.content,
          type: r.entry.type,
          relevance: r.score,
          createdAt: r.entry.createdAt.getTime(),
          tags: r.entry.metadata?.tags as string[] | undefined,
          importance: r.entry.importance,
          pinned: r.entry.pinned,
        }))

      if (injectedMemories.length === 0) return undefined

      this.logger.info('Legacy memory injection complete', {
        helixId,
        injectedCount: injectedMemories.length,
        durationMs: Date.now() - startTime,
      })

      return {
        memories: injectedMemories,
        injectedAt: Date.now(),
        searchQuery: goal.slice(0, 200),
        totalAvailable: searchResults.length,
      }
    } catch (error) {
      this.logger.error('Legacy memory injection failed', {
        helixId,
        error: String(error),
      })
      return undefined
    }
  }

  /**
   * Convert a MnemicRetrievalHit to an InjectedMemory.
   */
  private convertHitToInjectedMemory(hit: MnemicRetrievalHit): InjectedMemory {
    const content = hit.filamentExcerpt ?? hit.content
    return {
      content: content.length > this.config.maxContentLength
        ? content.slice(0, this.config.maxContentLength) + '...'
        : content,
      // WHY: Use kindling charge as relevance — it reflects how strongly the
      // engram activated in response to the goal's embedding. The LLM reranker
      // score (if enabled) is already folded into the final ranking order.
      relevance: Math.min(1, hit.charge + hit.potentiation * 0.1),
      type: hit.nodeType ?? 'fact',
      createdAt: new Date(hit.provenance).getTime() || Date.now(),
      tags: hit.tags,
    }
  }

  /**
   * Format injected memories for display in Helix context.
   */
  formatMemoriesForContext(memoryContext: BranchMemoryContext): string {
    if (memoryContext.memories.length === 0) {
      return ''
    }

    const lines: string[] = [
      '',
      '╔══════════════════════════════════════════════════════════════════╗',
      '║  CASSI MEMORY — Relevant context from past sessions              ║',
      '╚══════════════════════════════════════════════════════════════════╝',
      '',
    ]

    for (let i = 0; i < memoryContext.memories.length; i++) {
      const memory = memoryContext.memories[i]
      const date = new Date(memory.createdAt).toLocaleDateString()
      const pinned = memory.pinned ? ' [PINNED]' : ''
      const importance = memory.importance !== undefined
        ? ` imp:${memory.importance.toFixed(1)}`
        : ''

      lines.push(`[${i + 1}] ${memory.type.toUpperCase()} (${(memory.relevance * 100).toFixed(0)}%${importance}${pinned}, ${date})`)

      if (memory.tags && memory.tags.length > 0) {
        lines.push(`    tags: [${memory.tags.join(', ')}]`)
      }

      lines.push(`    ${memory.content}`)
      lines.push('')
    }

    lines.push('════════════════════════════════════════════════════════════════════')
    lines.push('')

    return lines.join('\n')
  }
}

/**
 * Create a memory injection service instance.
 */
export function createMemoryInjectionService(
  fieldOrMemory: MnemicField | IMemory,
  logger: ILogger,
  config?: Partial<MemoryInjectionConfig>
): MemoryInjectionService {
  return new MemoryInjectionService(fieldOrMemory, logger, config)
}
