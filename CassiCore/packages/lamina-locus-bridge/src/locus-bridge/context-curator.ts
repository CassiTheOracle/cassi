/**
 * Context Curator — Memory retrieval and context assembly
 *
 * Searches memories relevant to the current work and assembles curated
 * content for system prompt injection. Uses two complementary signals:
 *
 *   1. Foci sparks — attentional state from session events
 *   2. Recent messages — direct conversational context (user + assistant)
 *
 * This dual-source approach ensures memory retrieval works from the first
 * turn (before foci build up) and stays relevant to what's actively being
 * discussed and worked on.
 *
 * The curator produces content without budget awareness — the
 * WindowAssembler handles budget allocation dynamically.
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
   * Curate context from foci and recent messages.
   *
   * Memory queries are built from two sources:
   *   1. Active foci (spark content + goals)
   *   2. Recent user + assistant messages (direct conversational context)
   *
   * This ensures memories are found even when foci are empty (fresh
   * session, first turn) and that the assistant's active work context
   * (tool calls, file references, decisions) feeds the search.
   */
  async curate(foci: BridgeFocus[], messages?: any[]): Promise<CuratedContext> {
    if (!this.memory) {
      return this.emptyContext()
    }

    const activeFoci = foci.filter(f => f.spark !== null)
    const memoryLimit = this.config.memoryRetrievalLimit
    const allMemories: CuratedMemory[] = []
    const allCode: CuratedCode[] = []
    const seenContent = new Set<string>()

    // Source 1: Foci-driven queries (attentional state)
    if (activeFoci.length > 0) {
      const totalLuminance = activeFoci.reduce(
        (sum, f) => sum + (f.spark?.luminance.composite ?? 0), 0,
      )

      for (const focus of activeFoci) {
        if (!focus.spark) continue

        const luminanceFraction = totalLuminance > 0
          ? focus.spark.luminance.composite / totalLuminance
          : 1 / activeFoci.length

        const focusMemoryLimit = Math.max(1, Math.ceil(memoryLimit * luminanceFraction))

        try {
          const query = this.buildQuery(focus.spark.content, focus.spark.sourceGoal)
          const results = await this.memory.search(query, { limit: focusMemoryLimit })
          this.addMemories(results, allMemories, seenContent)
        } catch (err) {
          this.logger.warn('Memory retrieval failed for focus', {
            slotIndex: focus.slotIndex,
            error: String(err),
          })
        }

        // Code references from focus
        for (const file of focus.spark.relevantFiles.slice(0, this.config.codeRetrievalLimit)) {
          if (seenContent.has(`code:${file}`)) continue
          seenContent.add(`code:${file}`)
          allCode.push({ path: file, content: `[Active file: ${file}]` })
        }
      }
    }

    // Source 2: Recent message-driven queries (conversational context)
    // Extracts terms from the last few user + assistant messages and
    // searches memories against them. This catches context that foci
    // may have missed (eclipsed sparks, fresh session, etc.)
    if (messages && messages.length > 0) {
      const messageQueries = this.buildMessageQueries(messages)
      for (const query of messageQueries) {
        try {
          const results = await this.memory.search(query, { limit: Math.ceil(memoryLimit / 2) })
          this.addMemories(results, allMemories, seenContent)
        } catch (err) {
          this.logger.warn('Memory retrieval from messages failed', { error: String(err) })
        }
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

    // Build focus summary (only if foci are active)
    const focusSummary = activeFoci.length > 0 ? this.buildFocusSummary(activeFoci) : ''

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

  /**
   * Add memory results, deduplicating by content hash.
   */
  private addMemories(
    results: Array<{ entry: { content: string; type?: string }; score: number; source?: string }>,
    allMemories: CuratedMemory[],
    seenContent: Set<string>,
  ): void {
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
  }

  /**
   * Build search queries from recent user + assistant messages.
   * Returns 1-3 queries covering the most recent conversational context.
   */
  private buildMessageQueries(messages: any[]): string[] {
    const queries: string[] = []
    let seen = 0

    for (let i = messages.length - 1; i >= 0 && seen < 6; i--) {
      const msg = messages[i]
      if (msg?.role !== 'user' && msg?.role !== 'assistant') continue
      seen++

      const content = this.extractMessageContent(msg)
      if (content.length < 20) continue

      const terms = content
        .split(/[\s,;:.!?()\[\]{}'"]+/)
        .filter((w: string) => w.length >= 4 && !STOP_WORDS.has(w.toLowerCase()))
        .slice(0, 15)

      if (terms.length >= 3) {
        queries.push(terms.join(' ').slice(0, 200))
      }

      if (queries.length >= 3) break
    }

    return queries
  }

  /**
   * Extract readable text from a message.
   */
  private extractMessageContent(msg: any): string {
    if (!msg) return ''
    if (typeof msg.content === 'string') return msg.content
    if (Array.isArray(msg.content)) {
      return msg.content
        .map((c: any) => {
          if (typeof c === 'string') return c
          if (c?.type === 'text') return c.text ?? ''
          if (c?.type === 'tool_result') return c.content ?? ''
          return ''
        })
        .join('\n')
    }
    return ''
  }

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


const STOP_WORDS = new Set([
  'this', 'that', 'with', 'from', 'have', 'been', 'will', 'would', 'could',
  'should', 'their', 'there', 'they', 'what', 'when', 'where', 'which',
  'while', 'about', 'after', 'before', 'between', 'through', 'during',
  'into', 'each', 'some', 'more', 'most', 'other', 'than', 'then',
  'them', 'these', 'those', 'such', 'only', 'also', 'just', 'very',
  'make', 'made', 'like', 'well', 'back', 'over', 'does', 'done',
  'need', 'want', 'here', 'your', 'were', 'being', 'still', 'much',
  'same', 'both', 'many', 'even', 'under', 'sure', 'look', 'good',
  'true', 'false', 'null', 'undefined', 'const', 'function', 'return',
  'import', 'export', 'default', 'class', 'type', 'interface',
  'let', 'help', 'please', 'thanks',
])
