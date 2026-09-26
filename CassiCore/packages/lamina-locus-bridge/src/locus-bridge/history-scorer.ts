/**
 * History Scorer — Task segmentation and semantic turn scoring
 *
 * Two-layer scoring for conversation history turns:
 *
 * Layer 1: Task Segmentation
 *   Tracks task boundaries by monitoring focus eclipses. When foci shift
 *   significantly (multiple eclipses in one turn), that's a task boundary.
 *   Turns within the current task get a base score of 1.0; prior tasks
 *   get a decaying base score. Boundaries emerge naturally from the Locus.
 *
 * Layer 2: Semantic Scoring
 *   Within a task segment, turns are scored by:
 *   - Recency (more recent = higher)
 *   - Reference density (mentions files/concepts in active foci)
 *   - Information density (tool results > conversation)
 *   - Edit proximity (edits to active files score higher)
 *
 * Final score = taskMultiplier × semanticScore
 */

import type { ILogger } from '@cassicore/foundation'
import type { BridgeFocus, BridgeKindlingEvent, ScoredTurn } from './types.js'

/**
 * Token estimation: ~4 chars per token for English text.
 * This is a rough heuristic — good enough for budget allocation.
 */
const CHARS_PER_TOKEN = 4

export interface HistoryScorerDeps {
  logger: ILogger
}

export class HistoryScorer {
  private logger: ILogger
  private taskBoundaries: number[] = []
  private currentTaskId = 'task-0'
  private taskCounter = 0

  constructor(deps: HistoryScorerDeps) {
    this.logger = deps.logger.child?.('history-scorer') ?? deps.logger
  }

  /**
   * Record a potential task boundary from kindling events.
   * Multiple eclipses in a short window signal a task switch.
   */
  recordKindlingEvents(events: BridgeKindlingEvent[], messageIndex: number): void {
    const eclipses = events.filter(e => e.eclipse !== null)
    if (eclipses.length >= 2) {
      this.taskBoundaries.push(messageIndex)
      this.taskCounter++
      this.currentTaskId = `task-${this.taskCounter}`
      this.logger.info('Task boundary detected', {
        messageIndex,
        eclipses: eclipses.length,
        taskId: this.currentTaskId,
      })
    }
  }

  /**
   * Force a task boundary (e.g., from explicit user signal).
   */
  forceTaskBoundary(messageIndex: number): void {
    this.taskBoundaries.push(messageIndex)
    this.taskCounter++
    this.currentTaskId = `task-${this.taskCounter}`
  }

  /**
   * Score all turns in a messages array.
   * Returns scored turns sorted by score (highest first).
   */
  scoreTurns(
    messages: any[],
    foci: BridgeFocus[],
  ): ScoredTurn[] {
    const activeFoci = foci.filter(f => f.spark !== null)
    const activeFiles = new Set<string>()
    const activeTerms = new Set<string>()

    // Layer A: Extract terms from foci sparks
    for (const focus of activeFoci) {
      if (!focus.spark) continue
      for (const file of focus.spark.relevantFiles) {
        activeFiles.add(file)
      }
      for (const term of this.extractTerms(focus.spark.content)) {
        activeTerms.add(term.toLowerCase())
      }
    }

    // Layer B: Extract terms directly from recent user and assistant messages.
    // Foci only capture 500-char spark summaries and can be eclipsed.
    // This ensures the actual words/files mentioned in recent conversation
    // are always used for scoring, giving a direct relevance signal.
    // Assistant messages are especially valuable — they contain the active
    // work context: file paths, function names, decisions, and concepts.
    const recentMessageWindow = 10
    let messagesSeen = 0
    for (let i = messages.length - 1; i >= 0 && messagesSeen < recentMessageWindow; i--) {
      const msg = messages[i]
      if (msg?.role !== 'user' && msg?.role !== 'assistant') continue
      messagesSeen++
      const content = this.extractMessageContent(msg)
      for (const term of this.extractTerms(content)) {
        activeTerms.add(term.toLowerCase())
      }
      for (const file of this.extractFilePaths(content)) {
        activeFiles.add(file)
      }
    }

    const latestBoundary = this.taskBoundaries.length > 0
      ? this.taskBoundaries[this.taskBoundaries.length - 1]
      : 0

    const scored: ScoredTurn[] = []
    const totalMessages = messages.length

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      const taskId = this.getTaskIdForIndex(i)
      const isCurrentTask = i >= latestBoundary

      const taskMultiplier = this.taskMultiplier(i, latestBoundary)
      const semanticScore = this.semanticScore(msg, i, totalMessages, activeFiles, activeTerms)
      const score = Math.min(1.0, taskMultiplier * semanticScore)

      scored.push({
        messageIndex: i,
        score,
        taskId,
        isCurrentTask,
        estimatedTokens: this.estimateTokens(msg),
      })
    }

    return scored.sort((a, b) => b.score - a.score)
  }

  /**
   * Get current task boundaries for snapshot.
   */
  getTaskBoundaries(): number[] {
    return [...this.taskBoundaries]
  }

  /**
   * Get current task ID.
   */
  getCurrentTaskId(): string {
    return this.currentTaskId
  }

  /**
   * Restore state from persisted data.
   */
  restoreState(boundaries: number[]): void {
    this.taskBoundaries = [...boundaries]
    this.taskCounter = boundaries.length
    this.currentTaskId = `task-${this.taskCounter}`
  }

  /**
   * Reset all state (for testing).
   */
  reset(): void {
    this.taskBoundaries = []
    this.taskCounter = 0
    this.currentTaskId = 'task-0'
  }

  // --- Private ---

  /**
   * Task multiplier: current task = 1.0, previous tasks decay.
   */
  private taskMultiplier(index: number, latestBoundary: number): number {
    if (index >= latestBoundary) return 1.0

    // Find which task segment this index belongs to
    let segmentsBack = 0
    for (let b = this.taskBoundaries.length - 1; b >= 0; b--) {
      if (index < this.taskBoundaries[b]) {
        segmentsBack++
      } else {
        break
      }
    }

    // Decay: 0.3 for immediately previous task, 0.15 for older, 0.05 minimum
    return Math.max(0.05, 0.3 * Math.pow(0.5, segmentsBack))
  }

  /**
   * Semantic scoring within a task segment.
   * Components: recency, reference density, information density, edit proximity.
   */
  private semanticScore(
    msg: any,
    index: number,
    totalMessages: number,
    activeFiles: Set<string>,
    activeTerms: Set<string>,
  ): number {
    const recency = this.recencyScore(index, totalMessages)
    const refDensity = this.referenceDensityScore(msg, activeFiles, activeTerms)
    const infoDensity = this.informationDensityScore(msg)
    const editProx = this.editProximityScore(msg, activeFiles)

    return (
      0.35 * recency +
      0.30 * refDensity +
      0.20 * infoDensity +
      0.15 * editProx
    )
  }

  /**
   * Recency: linear decay from 1.0 (most recent) to 0.1 (oldest).
   */
  private recencyScore(index: number, total: number): number {
    if (total <= 1) return 1.0
    return 0.1 + 0.9 * (index / (total - 1))
  }

  /**
   * Reference density: how much of the turn content overlaps with active foci.
   */
  private referenceDensityScore(
    msg: any,
    activeFiles: Set<string>,
    activeTerms: Set<string>,
  ): number {
    const content = this.extractMessageContent(msg).toLowerCase()
    if (!content || activeTerms.size === 0) return 0

    let hits = 0
    let checks = 0

    // Check file references
    for (const file of activeFiles) {
      checks++
      if (content.includes(file) || content.includes(file.split('/').pop() ?? '')) {
        hits++
      }
    }

    // Check term overlap
    for (const term of activeTerms) {
      if (term.length < 4) continue
      checks++
      if (content.includes(term)) {
        hits++
      }
    }

    return checks > 0 ? Math.min(1.0, hits / Math.max(checks * 0.3, 1)) : 0
  }

  /**
   * Information density: tool results and code blocks > plain conversation.
   */
  private informationDensityScore(msg: any): number {
    const role = msg?.role
    const content = this.extractMessageContent(msg)

    if (role === 'tool' || role === 'tool_result') return 0.8
    if (role === 'assistant') {
      const hasToolUse = Array.isArray(msg?.content) &&
        msg.content.some((c: any) => c?.type === 'tool_use')
      if (hasToolUse) return 0.7

      const hasCodeBlock = content.includes('```')
      if (hasCodeBlock) return 0.6

      return 0.3
    }
    if (role === 'user') return 0.5
    if (role === 'system') return 0.2
    return 0.3
  }

  /**
   * Edit proximity: does this turn contain edits to files in active foci?
   */
  private editProximityScore(msg: any, activeFiles: Set<string>): number {
    if (activeFiles.size === 0) return 0

    const content = this.extractMessageContent(msg)
    if (!content) return 0

    // Check for tool_use blocks that reference active files
    if (Array.isArray(msg?.content)) {
      for (const block of msg.content) {
        if (block?.type === 'tool_use') {
          const input = block.input ?? {}
          const filePath = input.filePath ?? input.path ?? input.relative_path ?? ''
          if (filePath && activeFiles.has(filePath)) return 1.0
          // Check if basename matches
          const basename = filePath.split('/').pop() ?? ''
          for (const af of activeFiles) {
            if (af.endsWith(basename) && basename.length > 3) return 0.8
          }
        }
      }
    }

    return 0
  }

  /**
   * Extract readable content from a message (handles string and content block formats).
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

  /**
   * Estimate token count for a message.
   */
  estimateTokens(msg: any): number {
    const content = this.extractMessageContent(msg)
    const base = Math.ceil(content.length / CHARS_PER_TOKEN)

    // Tool use blocks add structural overhead
    if (Array.isArray(msg?.content)) {
      const toolBlocks = msg.content.filter((c: any) => c?.type === 'tool_use' || c?.type === 'tool_result')
      return base + toolBlocks.length * 50
    }

    return Math.max(base, 10)
  }

  /**
   * Get task ID for a given message index.
   */
  private getTaskIdForIndex(index: number): string {
    let taskNum = 0
    for (const boundary of this.taskBoundaries) {
      if (index >= boundary) {
        taskNum++
      } else {
        break
      }
    }
    return `task-${taskNum}`
  }

  /**
   * Extract significant terms from content for overlap checking.
   */
  private extractTerms(content: string): string[] {
    const words = content.split(/[\s,;:.!?()\[\]{}'"]+/)
    return words.filter(w => w.length >= 4 && !STOP_WORDS.has(w.toLowerCase()))
  }

  /**
   * Extract file paths from content (e.g. "core/intelligence/locus-bridge/index.ts").
   * Matches common path patterns found in user messages and code references.
   */
  private extractFilePaths(content: string): string[] {
    const pathPattern = /(?:^|\s|["'`(])([a-zA-Z0-9_\-./]+\/[a-zA-Z0-9_\-./]+\.[a-zA-Z]{1,10})(?:\s|["'`),:]|$)/g
    const paths: string[] = []
    let match: RegExpExecArray | null
    while ((match = pathPattern.exec(content)) !== null) {
      const p = match[1]
      if (p.length > 5 && !p.startsWith('http')) {
        paths.push(p)
      }
    }
    return paths
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
])
