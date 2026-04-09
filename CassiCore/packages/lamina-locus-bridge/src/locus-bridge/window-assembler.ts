/**
 * Window Assembler — Budget allocation and context assembly
 *
 * The core assembly algorithm. Takes curated content (from ContextCurator)
 * and scored turns (from HistoryScorer), then assembles a complete context
 * window within the configured token budget.
 *
 * Assembly algorithm:
 *   1. Reserve system prompt budget (fixed)
 *   2. Allocate curated content budget (flex within soft cap)
 *   3. Calculate remaining history budget
 *   4. Always include the recent window (last N messages)
 *   5. Fill remaining budget with highest-scored older turns
 *   6. Re-order selected turns by original position
 *   7. Insert bridge summaries for gaps
 *   8. Return assembled window
 *
 * The recent window (configurable via recentWindowMinMessages, default 20)
 * is always included regardless of score — this ensures the model never
 * forgets what it was just working on, including intermediate tool call
 * chains and results.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  AssembledWindow,
  AssemblyMeta,
  BridgeFocus,
  CuratedContext,
  LocusBridgeConfig,
  ScoredTurn,
} from './types.js'
import { DEFAULT_LOCUS_BRIDGE_CONFIG } from './types.js'

const CHARS_PER_TOKEN = 4

export interface WindowAssemblerDeps {
  logger: ILogger
  config?: LocusBridgeConfig
}


export class WindowAssembler {
  private logger: ILogger
  private config: LocusBridgeConfig
  private lastMeta: AssemblyMeta | null = null

  constructor(deps: WindowAssemblerDeps) {
    this.logger = deps.logger.child?.('window-assembler') ?? deps.logger
    this.config = deps.config ?? DEFAULT_LOCUS_BRIDGE_CONFIG
  }

  /**
   * Assemble a complete context window within the token budget.
   *
   * @param systemPromptBase - Base system prompt content (SOUL + AGENTS)
   * @param curated - Curated content from ContextCurator
   * @param scoredTurns - Scored turns from HistoryScorer (sorted by score desc)
   * @param messages - Original messages array
   * @param foci - Current focus state (for metadata)
   */
  assemble(
    systemPromptBase: string[],
    curated: CuratedContext,
    scoredTurns: ScoredTurn[],
    messages: any[],
    foci: BridgeFocus[],
  ): AssembledWindow {
    const budget = this.config.tokenBudget

    // 1. Calculate system prompt tokens (fixed cost)
    const systemPromptTokens = this.estimateTokensFromStrings(systemPromptBase)

    // 2. Curated context — flex within soft cap
    const curatedTokens = Math.min(curated.totalTokens, this.config.curatedContextMax)
    const systemContextBlocks = this.formatCuratedContext(curated, this.config.curatedContextMax)

    // 3. Calculate history budget
    const fixedCost = systemPromptTokens + curatedTokens
    const historyBudget = Math.max(
      this.config.historyMinTokens,
      budget - fixedCost,
    )

    // 4. Select turns that fit within history budget
    const selectedIndices = this.selectTurns(scoredTurns, messages, historyBudget)

    // 5. Re-order by original position (conversation coherence)
    selectedIndices.sort((a, b) => a - b)

    // 6. Build selected messages with bridge summaries for gaps
    const assembledMessages = this.buildMessagesWithBridges(selectedIndices, messages, scoredTurns)

    // 7. Calculate actual token usage
    const actualHistoryTokens = selectedIndices.reduce((sum, idx) => {
      const scored = scoredTurns.find(s => s.messageIndex === idx)
      return sum + (scored?.estimatedTokens ?? 0)
    }, 0)

    const meta: AssemblyMeta = {
      tokenBudget: budget,
      systemPromptTokens,
      curatedContextTokens: curatedTokens,
      historyTokens: actualHistoryTokens,
      turnsIncluded: selectedIndices.length,
      turnsDropped: messages.length - selectedIndices.length,
      keptMessageIndices: [...selectedIndices],
      fociSnapshot: foci.map(f => ({
        slotIndex: f.slotIndex,
        content: f.spark?.content.slice(0, 80) ?? null,
        luminance: f.spark?.luminance.composite ?? 0,
      })),
      taskBoundaries: this.extractTaskBoundaries(scoredTurns),
      assembledAt: Date.now(),
    }

    this.lastMeta = meta

    this.logger.info('Window assembled', {
      budget,
      systemPromptTokens,
      curatedContextTokens: curatedTokens,
      historyTokens: actualHistoryTokens,
      turnsIncluded: selectedIndices.length,
      turnsDropped: meta.turnsDropped,
    })

    return {
      systemContext: systemContextBlocks,
      messages: assembledMessages,
      meta,
    }
  }

  /**
   * Get last assembly metadata.
   */
  getLastMeta(): AssemblyMeta | null {
    return this.lastMeta
  }

  /**
   * Reset state (for testing).
   */
  reset(): void {
    this.lastMeta = null
  }

  // --- Private ---

  /**
   * Select turns by score, respecting the history budget.
   *
   * Priority order:
   *   1. Recent window — always keep the last N messages (configurable via
   *      recentWindowMinMessages). This guarantees the model never forgets
   *      what it was just working on, including intermediate tool calls/results.
   *   2. Score-based fill — remaining budget is filled with the highest-scored
   *      turns from older history.
   */
  private selectTurns(
    scoredTurns: ScoredTurn[],
    messages: any[],
    historyBudget: number,
  ): number[] {
    const selected = new Set<number>()
    let usedTokens = 0

    // 1. Always include the recent window (last N messages).
    //    This keeps the current work context intact — tool call chains,
    //    results, and the ongoing conversation thread.
    const recentWindowSize = this.config.recentWindowMinMessages ?? 20
    const recentStart = Math.max(0, messages.length - recentWindowSize)
    for (let i = recentStart; i < messages.length; i++) {
      const scored = scoredTurns.find(s => s.messageIndex === i)
      if (scored) {
        selected.add(i)
        usedTokens += scored.estimatedTokens
      }
    }

    // 2. Fill remaining budget with highest-scored older turns
    for (const scored of scoredTurns) {
      if (selected.has(scored.messageIndex)) continue

      if (usedTokens + scored.estimatedTokens <= historyBudget) {
        selected.add(scored.messageIndex)
        usedTokens += scored.estimatedTokens
      }

      if (usedTokens >= historyBudget) break
    }

    return Array.from(selected)
  }

  /**
   * Build messages array with bridge summaries inserted for gaps.
   * A gap is when consecutive selected indices skip more than 2 messages.
   */
  private buildMessagesWithBridges(
    selectedIndices: number[],
    messages: any[],
    scoredTurns: ScoredTurn[],
  ): any[] {
    const result: any[] = []

    for (let i = 0; i < selectedIndices.length; i++) {
      const idx = selectedIndices[i]
      const prevIdx = i > 0 ? selectedIndices[i - 1] : -1
      const gap = idx - prevIdx - 1

      // Insert bridge summary for significant gaps
      if (gap > 2 && prevIdx >= 0) {
        const skippedTasks = this.summarizeGap(prevIdx + 1, idx, messages, scoredTurns)
        if (skippedTasks) {
          result.push({
            role: 'system',
            content: `[${gap} turns omitted — ${skippedTasks}]`,
          })
        }
      }

      result.push(messages[idx])
    }

    return result
  }

  /**
   * Summarize what happened in a gap between selected turns.
   */
  private summarizeGap(
    startIdx: number,
    endIdx: number,
    messages: any[],
    scoredTurns: ScoredTurn[],
  ): string | null {
    const skippedScored = scoredTurns.filter(
      s => s.messageIndex >= startIdx && s.messageIndex < endIdx,
    )

    if (skippedScored.length === 0) return null

    const tasks = new Set(skippedScored.map(s => s.taskId))
    const hasToolUse = messages.slice(startIdx, endIdx).some(
      m => Array.isArray(m?.content) && m.content.some((c: any) => c?.type === 'tool_use'),
    )

    const parts: string[] = []
    if (tasks.size > 1) {
      parts.push(`${tasks.size} task segments`)
    }
    if (hasToolUse) {
      parts.push('tool interactions')
    }

    return parts.length > 0 ? parts.join(', ') : 'earlier conversation'
  }

  /**
   * Format curated context into system prompt blocks.
   * Fits within the curated context token budget.
   */
  private formatCuratedContext(curated: CuratedContext, maxTokens: number): string[] {
    const blocks: string[] = []
    let usedTokens = 0

    // Focus summary always included
    if (curated.focusSummary) {
      blocks.push(curated.focusSummary)
      usedTokens += this.estimateTokens(curated.focusSummary)
    }

    // Memories — sorted by score desc
    if (curated.memories.length > 0) {
      const memoryLines = ['Relevant memories:']
      const sorted = [...curated.memories].sort((a, b) => b.score - a.score)

      for (const mem of sorted) {
        const line = `- [${mem.source}] ${mem.content.slice(0, 300)}`
        const lineTokens = this.estimateTokens(line)
        if (usedTokens + lineTokens > maxTokens) break
        memoryLines.push(line)
        usedTokens += lineTokens
      }

      if (memoryLines.length > 1) {
        blocks.push(memoryLines.join('\n'))
      }
    }

    // Code references
    if (curated.code.length > 0) {
      const codeLines = ['Active code context:']
      for (const code of curated.code) {
        const line = code.lines
          ? `- ${code.path}:${code.lines[0]}-${code.lines[1]}`
          : `- ${code.path}`
        const lineTokens = this.estimateTokens(line)
        if (usedTokens + lineTokens > maxTokens) break
        codeLines.push(line)
        usedTokens += lineTokens
      }

      if (codeLines.length > 1) {
        blocks.push(codeLines.join('\n'))
      }
    }

    // Intelligence signals
    if (curated.signals.length > 0) {
      const signalLines = ['Intelligence signals:']
      for (const signal of curated.signals) {
        const line = `- [${signal.source}] ${signal.content.slice(0, 200)}`
        const lineTokens = this.estimateTokens(line)
        if (usedTokens + lineTokens > maxTokens) break
        signalLines.push(line)
        usedTokens += lineTokens
      }

      if (signalLines.length > 1) {
        blocks.push(signalLines.join('\n'))
      }
    }

    return blocks
  }

  /**
   * Extract task boundaries from scored turns.
   */
  private extractTaskBoundaries(scoredTurns: ScoredTurn[]): number[] {
    const boundaries: number[] = []
    let lastTaskId = ''

    const sorted = [...scoredTurns].sort((a, b) => a.messageIndex - b.messageIndex)
    for (const turn of sorted) {
      if (turn.taskId !== lastTaskId && lastTaskId !== '') {
        boundaries.push(turn.messageIndex)
      }
      lastTaskId = turn.taskId
    }

    return boundaries
  }

  private estimateTokens(text: string): number {
    return Math.ceil(text.length / CHARS_PER_TOKEN)
  }

  private estimateTokensFromStrings(strs: string[]): number {
    return strs.reduce((sum, s) => sum + this.estimateTokens(s), 0)
  }
}
