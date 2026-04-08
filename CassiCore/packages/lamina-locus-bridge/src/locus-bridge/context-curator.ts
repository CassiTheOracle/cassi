/**
 * Context Curator — Focus-to-Context Retrieval Pipeline
 *
 * Translates current LocusBridge foci into concrete retrieval operations
 * and assembles curated content for the system prompt.
 *
 * Per-focus pipeline:
 *   1. Extract query terms from spark content + goal
 *   2. Memory retrieval (memory module search)
 *   3. Code retrieval (file reads from spark.relevantFiles)
 *   4. Intelligence signals (thinker, dialectic, anomalies, teams)
 *   5. Budget allocation proportional to focus luminance
 *
 * The curator doesn't know about history or budget — it only produces
 * curated content. The WindowAssembler handles budget allocation.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  BridgeFocus,
  CuratedContext,
  CuratedMemory,
  CuratedCode,
  CuratedSignal,
  LocusBridgeConfig,
} from './types.js'
import { DEFAULT_LOCUS_BRIDGE_CONFIG } from './types.js'

const CHARS_PER_TOKEN = 4

/**
 * Abstract interface for memory retrieval.
 * The LocusBridge wires the actual memory module at initialization.
 */
export interface MemoryRetriever {
  search(query: string, opts?: { limit?: number }): Promise<Array<{
    entry: { content: string; type?: string }
    score: number
    source?: string
  }>>
}

/**
 * Abstract interface for intelligence signal retrieval.
 * Pulls thinker insights, dialectic signals, anomalies, team status.
 */
export interface IntelligenceSignalProvider {
  getSignals(): Promise<CuratedSignal[]>
}


export interface ContextCuratorDeps {
  logger: ILogger
  config?: LocusBridgeConfig
  memory?: MemoryRetriever
  signalProvider?: IntelligenceSignalProvider
}


export class ContextCurator {
  private logger: ILogger
  private config: LocusBridgeConfig
  private memory?: MemoryRetriever
  private signalProvider?: IntelligenceSignalProvider

  constructor(deps: ContextCuratorDeps) {
    this.logger = deps.logger.child?.('context-curator') ?? deps.logger
    this.config = deps.config ?? DEFAULT_LOCUS_BRIDGE_CONFIG
    this.memory = deps.memory
    this.signalProvider = deps.signalProvider
  }

  /**
   * Wire the memory retriever (may be set after construction).
   */
  setMemoryRetriever(memory: MemoryRetriever): void {
    this.memory = memory
  }

  /**
   * Wire the intelligence signal provider.
   */
  setSignalProvider(provider: IntelligenceSignalProvider): void {
    this.signalProvider = provider
  }

  /**
   * Curate context from current foci.
   * Returns curated content for system prompt injection.
   */
  async curate(foci: BridgeFocus[]): Promise<CuratedContext> {
    const activeFoci = foci.filter(f => f.spark !== null)

    if (activeFoci.length === 0) {
      return this.emptyContext()
    }

    // Compute luminance-proportional budgets per focus
    const totalLuminance = activeFoci.reduce(
      (sum, f) => sum + (f.spark?.luminance.composite ?? 0), 0,
    )

    const memoryLimit = this.config.memoryRetrievalLimit
    const allMemories: CuratedMemory[] = []
    const allCode: CuratedCode[] = []
    const seenContent = new Set<string>()

    for (const focus of activeFoci) {
      if (!focus.spark) continue

      const luminanceFraction = totalLuminance > 0
        ? focus.spark.luminance.composite / totalLuminance
        : 1 / activeFoci.length

      const focusMemoryLimit = Math.max(1, Math.ceil(memoryLimit * luminanceFraction))

      // Memory retrieval
      if (this.memory) {
        try {
          const query = this.buildQuery(focus.spark.content, focus.spark.sourceGoal)
          const results = await this.memory.search(query, { limit: focusMemoryLimit })

          for (const result of results) {
            const hash = this.contentHash(result.entry.content)
            if (seenContent.has(hash)) continue
            seenContent.add(hash)

            allMemories.push({
              content: result.entry.content,
              source: result.source ?? result.entry.type ?? 'memory',
              score: result.score,
            })
          }
        } catch (err) {
          this.logger.warn('Memory retrieval failed for focus', {
            slotIndex: focus.slotIndex,
            error: String(err),
          })
        }
      }

      // Code references from focus
      for (const file of focus.spark.relevantFiles.slice(0, this.config.codeRetrievalLimit)) {
        if (seenContent.has(`code:${file}`)) continue
        seenContent.add(`code:${file}`)

        allCode.push({
          path: file,
          content: `[Active file: ${file}]`,
        })
      }
    }

    // Intelligence signals
    let signals: CuratedSignal[] = []
    if (this.signalProvider) {
      try {
        signals = await this.signalProvider.getSignals()
      } catch (err) {
        this.logger.warn('Signal retrieval failed', { error: String(err) })
      }
    }

    // Build focus summary
    const focusSummary = this.buildFocusSummary(activeFoci)

    // Estimate total tokens
    const totalChars =
      focusSummary.length +
      allMemories.reduce((sum, m) => sum + m.content.length, 0) +
      allCode.reduce((sum, c) => sum + c.content.length, 0) +
      signals.reduce((sum, s) => sum + s.content.length, 0)
    const totalTokens = Math.ceil(totalChars / CHARS_PER_TOKEN)

    this.logger.info('Context curated', {
      foci: activeFoci.length,
      memories: allMemories.length,
      code: allCode.length,
      signals: signals.length,
      totalTokens,
    })

    return {
      focusSummary,
      memories: allMemories,
      code: allCode,
      signals,
      totalTokens,
    }
  }

  // --- Private ---

  private emptyContext(): CuratedContext {
    return {
      focusSummary: '',
      memories: [],
      code: [],
      signals: [],
      totalTokens: 0,
    }
  }

  /**
   * Build a search query from spark content and goal.
   * Takes the most distinctive terms.
   */
  private buildQuery(content: string, goal: string): string {
    const combined = `${content} ${goal}`
    const words = combined
      .split(/[\s,;:.!?()\[\]{}'"]+/)
      .filter(w => w.length >= 3)
      .slice(0, 20)

    return words.join(' ').slice(0, 200)
  }

  /**
   * Build a human-readable summary of current foci.
   */
  private buildFocusSummary(foci: BridgeFocus[]): string {
    const lines = ['Current attention:']

    for (const focus of foci) {
      if (!focus.spark) continue
      const lum = focus.spark.luminance.composite.toFixed(2)
      const age = focus.occupancyTicks
      const content = focus.spark.content.slice(0, 100)
      lines.push(`- [${focus.spark.type}] (L:${lum}, age:${age}) ${content}`)
    }

    return lines.join('\n')
  }

  /**
   * Simple content hash for deduplication.
   */
  private contentHash(content: string): string {
    const normalized = content.trim().toLowerCase().slice(0, 200)
    let hash = 0
    for (let i = 0; i < normalized.length; i++) {
      const char = normalized.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash |= 0
    }
    return `h${hash}`
  }
}
