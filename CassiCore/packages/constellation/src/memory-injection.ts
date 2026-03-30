/**
 * Memory Injection Service — Branch-level Memory Continuity for Helix Startup
 *
 * This service provides memory injection capabilities for the Constellation
 * framework. When a new Helix branch is registered, it searches CassiCore
 * memory for relevant context and injects it into the branch, providing
 * continuity instead of cold starts.
 *
 * The service:
 *   1. Extracts search keywords from the branch goal
 *   2. Searches CassiCore memory for relevant entries
 *   3. Filters and ranks results by relevance
 *   4. Formats memories for injection into the Helix context
 *
 * Named after the personified system "Cassi" — bringing memory to life.
 */

import type { IMemory, SearchResult, MemoryEntry } from '../../../types/intelligence.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { BranchMemoryContext, InjectedMemory } from './corpus-types.js'

/**
 * Configuration for memory injection behavior.
 */
export interface MemoryInjectionConfig {
  /** Maximum memories to inject per branch. Default: 5 */
  maxMemories: number
  /** Minimum relevance score (0-1) for injection. Default: 0.4 */
  minRelevance: number
  /** Maximum age of memories in days (0 = no limit). Default: 90 */
  maxAgeDays: number
  /** Whether to include pinned memories regardless of age. Default: true */
  includePinned: boolean
  /** Whether to prioritize high-importance memories. Default: true */
  prioritizeImportance: boolean
  /** Max memory content length (chars). Default: 2000 */
  maxContentLength: number
}

export const DEFAULT_MEMORY_INJECTION_CONFIG: MemoryInjectionConfig = {
  maxMemories: 5,
  minRelevance: 0.4,
  maxAgeDays: 90,
  includePinned: true,
  prioritizeImportance: true,
  maxContentLength: 2000,
}

/**
 * Memory Injection Service — Provides branch-level memory continuity.
 */
export class MemoryInjectionService {
  private memory: IMemory
  private config: MemoryInjectionConfig
  private logger: ILogger

  constructor(memory: IMemory, logger: ILogger, config?: Partial<MemoryInjectionConfig>) {
    this.memory = memory
    this.config = { ...DEFAULT_MEMORY_INJECTION_CONFIG, ...config }
    this.logger = logger.child('MemoryInjection')
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
    const startTime = Date.now()

    // Extract search query from goal
    const searchQuery = this.extractSearchQuery(goal)
    this.logger.info('Injecting memories for branch', {
      helixId,
      searchQuery,
      parentId,
    })

    try {
      // Search memory
      const searchResults = await this.memory.search(searchQuery, {
        limit: this.config.maxMemories * 2, // Fetch extra for filtering
      })

      if (searchResults.length === 0) {
        this.logger.info('No memories found for branch', { helixId, searchQuery })
        return undefined
      }

      // Filter and rank memories
      const filteredMemories = this.filterAndRankMemories(searchResults)

      if (filteredMemories.length === 0) {
        this.logger.info('No memories passed filter for branch', { helixId, searchQuery })
        return undefined
      }

      // Convert to injected memory format
      const injectedMemories: InjectedMemory[] = filteredMemories
        .slice(0, this.config.maxMemories)
        .map(result => this.convertToInjectedMemory(result))

      const context: BranchMemoryContext = {
        memories: injectedMemories,
        injectedAt: Date.now(),
        searchQuery,
        totalAvailable: searchResults.length,
      }

      this.logger.info('Memory injection complete', {
        helixId,
        injectedCount: injectedMemories.length,
        totalAvailable: searchResults.length,
        durationMs: Date.now() - startTime,
      })

      return context

    } catch (error) {
      this.logger.error('Memory injection failed', {
        helixId,
        searchQuery,
        error: String(error),
      })
      return undefined
    }
  }

  /**
   * Extract search keywords from a goal string.
   * Removes common stop words and focuses on technical terms.
   */
  private extractSearchQuery(goal: string): string {
    // Common stop words to remove
    const stopWords = new Set([
      'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
      'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
      'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
      'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this',
      'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
      'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its',
      'our', 'their', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
      'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
      'such', 'no', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
      'just', 'now', 'then', 'here', 'there', 'up', 'down', 'out', 'off',
      'over', 'under', 'again', 'further', 'once', 'during', 'before',
      'after', 'above', 'below', 'between', 'through', 'into', 'onto',
      'upon', 'within', 'without', 'across', 'around', 'behind', 'beyond',
      'except', 'inside', 'outside', 'until', 'via', 'per', 'among', 'toward',
      'towards', 'across', 'along', 'amid', 'amongst', 'beside', 'besides',
      'concerning', 'considering', 'despite', 'following', 'like', 'minus',
      'near', 'past', 'regarding', 'round', 'save', 'since', 'till', 'upon',
      'versus', 'worth',
    ])

    // Extract words, keeping technical terms and file paths
    const words = goal
      .toLowerCase()
      .replace(/[\/\\]([\w\-\.\/\\]+)/g, ' $1 ') // Preserve file paths
      .replace(/[^\w\s\/\._\-]/g, ' ') // Remove punctuation except path chars
      .split(/\s+/)
      .filter(word => word.length > 2) // Skip short words
      .filter(word => !stopWords.has(word)) // Skip stop words
      .filter((word, index, arr) => arr.indexOf(word) === index) // Deduplicate

    // Join top keywords (limit to avoid overly specific queries)
    const query = words.slice(0, 10).join(' ')

    // If we have very few keywords, use the original goal
    return query.length > 10 ? query : goal.slice(0, 200)
  }

  /**
   * Filter and rank search results by relevance, importance, and recency.
   */
  private filterAndRankMemories(searchResults: SearchResult[]): SearchResult[] {
    const now = Date.now()
    const maxAgeMs = this.config.maxAgeDays * 24 * 60 * 60 * 1000

    return searchResults
      .filter(result => {
        const entry = result.entry

        // Check minimum relevance
        if (result.score < this.config.minRelevance) {
          return false
        }

        // Check age (unless pinned and includePinned is true)
        const ageMs = now - entry.createdAt.getTime()
        const isPinned = entry.pinned ?? false
        if (this.config.maxAgeDays > 0 && ageMs > maxAgeMs) {
          if (!isPinned || !this.config.includePinned) {
            return false
          }
        }

        return true
      })
      .sort((a, b) => {
        // Composite score: relevance * importance * recency_boost
        const scoreA = this.computeCompositeScore(a, now)
        const scoreB = this.computeCompositeScore(b, now)
        return scoreB - scoreA // Descending
      })
  }

  /**
   * Compute a composite score for ranking memories.
   */
  private computeCompositeScore(result: SearchResult, now: number): number {
    const entry = result.entry

    // Base relevance from search
    let score = result.score

    // Importance boost (if available and prioritized)
    if (this.config.prioritizeImportance && entry.importance !== undefined) {
      score *= (0.5 + entry.importance / 20) // Scale 0-10 to 0.5-1.0 multiplier
    }

    // Recency boost (exponential decay)
    const ageMs = now - entry.createdAt.getTime()
    const ageDays = ageMs / (24 * 60 * 60 * 1000)
    const recencyBoost = Math.exp(-ageDays / 30) // Half-life of ~30 days
    score *= (0.5 + 0.5 * recencyBoost) // Scale 0.5-1.0

    // Pinned bonus
    if (entry.pinned) {
      score *= 1.2
    }

    return score
  }

  /**
   * Convert a SearchResult to an InjectedMemory.
   */
  private convertToInjectedMemory(result: SearchResult): InjectedMemory {
    const entry = result.entry

    // Truncate content if needed
    let content = entry.content
    if (content.length > this.config.maxContentLength) {
      content = content.slice(0, this.config.maxContentLength) + '...'
    }

    return {
      content,
      type: entry.type,
      relevance: result.score,
      createdAt: entry.createdAt.getTime(),
      tags: entry.metadata?.tags as string[] | undefined,
      importance: entry.importance,
      pinned: entry.pinned,
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
  memory: IMemory,
  logger: ILogger,
  config?: Partial<MemoryInjectionConfig>
): MemoryInjectionService {
  return new MemoryInjectionService(memory, logger, config)
}
