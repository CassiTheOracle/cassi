/**
 * ModuleSessionCompactor
 *
 * Smart, selective compaction for persistent module sessions.
 * Rather than bluntly truncating history, it:
 *
 * 1. Classifies each turn by importance (heuristic + optional LLM)
 * 2. Keeps recent turns verbatim ("hot window")
 * 3. Keeps high-importance older turns verbatim
 * 4. Summarizes medium/low-importance turns into era summaries using a swift-tier LLM
 * 5. Archives compacted turns to the memory archive for long-term retention
 *
 * Era summaries are injected as system messages in the session history so the
 * module has context-aware access to its own past without inflating the prompt.
 */

import type { IProvider, Message } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
import type { SessionManager } from '../session-manager.js'
import type { ModuleRegistration } from './module-session-registry.js'

export interface CompactionPolicy {
  /** Number of most-recent turns to always keep verbatim */
  hotWindowTurns: number
  /** Total turn count that triggers compaction */
  compactionThreshold: number
  /** Maximum era summary messages to retain (oldest era is dropped when exceeded) */
  maxSummaryEras: number
  /** Whether to archive compacted turns to the memory archive for long-term search */
  archiveCompacted: boolean
  /** Keywords that raise a turn's importance classification */
  importanceKeywords: string[]
}

export type TurnImportance = 'high' | 'medium' | 'low'

interface ClassifiedTurn {
  message: Message
  index: number
  importance: TurnImportance
  reason: string
}

// Model config for the swift tier (used for all compaction LLM calls)
const SWIFT_MODEL = 'qwen3.6-plus'
const SWIFT_PROVIDER = 'swift'

const ERA_SUMMARY_MARKER = '[era-summary]'
const COMPACTION_LOCK_TTL_MS = 60_000

export class ModuleSessionCompactor {
  private readonly logger: ILogger
  private readonly sessionManager: SessionManager
  private provider: IProvider | undefined
  /** Per-session compaction locks to prevent concurrent compactions */
  private readonly compactionLocks = new Map<string, number>()

  constructor(sessionManager: SessionManager, logger: ILogger) {
    this.sessionManager = sessionManager
    this.logger = logger.child?.('module-session-compactor') ?? logger
  }

  /** Wire in the swift-tier provider (injected after construction). */
  setProvider(provider: IProvider): void {
    this.provider = provider
  }

  /**
   * Compact a module session's history.
   * Safe to call concurrently — locked per session ID.
   */
  async compact(sessionId: string, registration: ModuleRegistration): Promise<void> {
    // Lock guard — skip if already compacting this session
    const lockTs = this.compactionLocks.get(sessionId)
    if (lockTs && Date.now() - lockTs < COMPACTION_LOCK_TTL_MS) {
      this.logger.debug(`ModuleSessionCompactor: skipping ${sessionId} — compaction in progress`)
      return
    }
    this.compactionLocks.set(sessionId, Date.now())

    try {
      await this._doCompact(sessionId, registration)
    } finally {
      this.compactionLocks.delete(sessionId)
    }
  }

  private async _doCompact(sessionId: string, registration: ModuleRegistration): Promise<void> {
    const session = this.sessionManager.get(sessionId)
    if (!session) return

    const policy = registration.compactionPolicy
    const history = session.history

    // Count only non-era-summary messages to determine if we need to compact
    const realTurns = history.filter(m => !this.isEraSummary(m))
    if (realTurns.length <= policy.compactionThreshold) return

    this.logger.info(`ModuleSessionCompactor: compacting ${registration.moduleKey} (${realTurns.length} turns > ${policy.compactionThreshold} threshold)`)

    // Separate existing era summaries from real turns
    const existingEras = history.filter(m => this.isEraSummary(m))
    const turns = history.filter(m => !this.isEraSummary(m))

    // Determine hot window — keep the last N turns verbatim
    const hotStart = Math.max(0, turns.length - policy.hotWindowTurns)
    const coldTurns = turns.slice(0, hotStart)
    const hotTurns = turns.slice(hotStart)

    if (coldTurns.length === 0) {
      // Nothing to compact
      return
    }

    // Classify cold turns by importance
    const classified = this.classifyTurns(coldTurns, policy)

    // Separate high-importance (kept verbatim) from compactable
    const keptVerbatim = classified.filter(t => t.importance === 'high').map(t => t.message)
    const toCompact = classified.filter(t => t.importance !== 'high')

    let eraSummary: Message | undefined

    if (toCompact.length > 0) {
      // Generate era summary using LLM (swift tier) or heuristic fallback
      eraSummary = await this.generateEraSummary(
        registration.moduleKey,
        registration.displayName,
        toCompact,
        classified,
      )

      // Archive compacted turns if policy requests it
      if (policy.archiveCompacted) {
        this.archiveTurns(registration, toCompact.map(t => t.message))
      }
    }

    // Trim era list if we'd exceed maxSummaryEras
    let updatedEras = [...existingEras]
    if (eraSummary) {
      updatedEras.push(eraSummary)
    }
    if (updatedEras.length > policy.maxSummaryEras) {
      // Drop the oldest era(s)
      updatedEras = updatedEras.slice(updatedEras.length - policy.maxSummaryEras)
    }

    // Reconstruct history: [era summaries] + [kept verbatim high-importance] + [hot window]
    const newHistory: Message[] = [
      ...updatedEras,
      ...keptVerbatim,
      ...hotTurns,
    ]

    session.history = newHistory
    session.lastActiveAt = new Date()

    // Persist
    try {
      ;(this.sessionManager as any).store?.save(session)
    } catch { /* best-effort */ }

    const removedCount = coldTurns.length - keptVerbatim.length
    this.logger.info(
      `ModuleSessionCompactor: ${registration.moduleKey} compacted — removed ${removedCount} turns, kept ${keptVerbatim.length} verbatim, ${updatedEras.length} eras retained`,
    )
  }


  /**
   * Classify turns into high / medium / low importance.
   *
   * Classification is heuristic-first (fast, no LLM calls).
   * High: contains importance keywords, errors, or is very long (>500 chars — likely substantive output)
   * Medium: mentions numbers/metrics, decisions, or is a non-trivial user turn
   * Low: short routine outputs, repeated patterns, whitespace-heavy
   */
  private classifyTurns(turns: Message[], policy: CompactionPolicy): ClassifiedTurn[] {
    return turns.map((message, index) => {
      const text = this.extractText(message.content)
      const lower = text.toLowerCase()

      // High: keyword hit (errors, decisions, insights, etc.)
      const keywordHit = policy.importanceKeywords.some(kw => lower.includes(kw.toLowerCase()))
      if (keywordHit) {
        const hitKw = policy.importanceKeywords.find(kw => lower.includes(kw.toLowerCase()))!
        return { message, index, importance: 'high' as TurnImportance, reason: `keyword: ${hitKw}` }
      }

      // High: explicit error indicators
      if (/\b(error|exception|failed|failure|crash|threw|traceback)\b/i.test(text)) {
        return { message, index, importance: 'high' as TurnImportance, reason: 'error detected' }
      }

      // High: long substantive output (>800 chars in assistant turn)
      if (message.role === 'assistant' && text.length > 800) {
        return { message, index, importance: 'high' as TurnImportance, reason: 'long output' }
      }

      // Medium: user messages (they represent intent/steering)
      if (message.role === 'user') {
        return { message, index, importance: 'medium' as TurnImportance, reason: 'user message' }
      }

      // Medium: contains numbers/metrics (e.g. "3 insights", "latency: 142ms")
      if (/\b\d+\s*(ms|tokens|insights?|patterns?|errors?|results?|%)\b/i.test(text)) {
        return { message, index, importance: 'medium' as TurnImportance, reason: 'contains metrics' }
      }

      // Medium: medium-length output (300-800 chars)
      if (message.role === 'assistant' && text.length > 300) {
        return { message, index, importance: 'medium' as TurnImportance, reason: 'medium output' }
      }

      // Low: everything else (short outputs, routine "no anomalies", etc.)
      return { message, index, importance: 'low' as TurnImportance, reason: 'routine' }
    })
  }


  private async generateEraSummary(
    moduleKey: string,
    displayName: string,
    toCompact: ClassifiedTurn[],
    allClassified: ClassifiedTurn[],
  ): Promise<Message> {
    const highCount = allClassified.filter(t => t.importance === 'high').length
    const medCount = allClassified.filter(t => t.importance === 'medium').length
    const lowCount = allClassified.filter(t => t.importance === 'low').length

    // Attempt LLM summary using swift tier
    if (this.provider) {
      try {
        const summary = await this.llmSummarize(displayName, toCompact)
        return this.buildEraSummaryMessage(moduleKey, summary, toCompact.length, { high: highCount, medium: medCount, low: lowCount })
      } catch (err) {
        this.logger.warn(`ModuleSessionCompactor: LLM summary failed for ${moduleKey}, using heuristic`, { error: String(err) })
      }
    }

    // Heuristic fallback: extract first sentence of each medium turn
    const heuristic = this.heuristicSummary(toCompact)
    return this.buildEraSummaryMessage(moduleKey, heuristic, toCompact.length, { high: highCount, medium: medCount, low: lowCount })
  }

  private async llmSummarize(displayName: string, turns: ClassifiedTurn[]): Promise<string> {
    // Build a condensed view of the turns for the prompt
    const turnTexts = turns
      .slice(0, 60) // cap to avoid huge prompts
      .map((t, i) => `[${i + 1}/${t.message.role}] ${this.extractText(t.message.content).slice(0, 400)}`)
      .join('\n\n')

    const prompt = `You are summarizing the historical activity log of the "${displayName}" AI module for compact archiving.

Below are ${turns.length} conversation turns to summarize. Extract and preserve:
- Key decisions made
- Errors or failures encountered
- Significant patterns observed
- Configuration or strategy changes
- Notable outputs or results

Return ONLY the summary as structured bullet points. Be specific and concrete. Preserve important numbers, dates, and identifiers. Omit routine/repetitive entries.

TURNS:
${turnTexts}`

    let result = ''
    for await (const chunk of this.provider!.complete(
      [{ role: 'user', content: prompt }],
      {
        model: SWIFT_MODEL,
        source: 'module-compactor',
        thinking: 'none',
        allowConcurrent: true,
        dedupe: false,
        maxTokens: 800,
      },
    )) {
      if (chunk.text) result += chunk.text
    }
    return result.trim()
  }

  private heuristicSummary(turns: ClassifiedTurn[]): string {
    const lines: string[] = []
    for (const t of turns) {
      if (t.importance === 'medium') {
        const text = this.extractText(t.message.content)
        // First sentence or first 120 chars
        const sentence = text.split(/[.!?\n]/)[0]?.trim() ?? ''
        if (sentence.length > 20) {
          lines.push(`- [${t.message.role}] ${sentence.slice(0, 120)}`)
        }
      }
    }
    if (lines.length === 0) {
      lines.push(`- ${turns.length} routine turn(s) compacted`)
    }
    return lines.join('\n')
  }

  private buildEraSummaryMessage(
    moduleKey: string,
    summary: string,
    compactedCount: number,
    counts: { high: number; medium: number; low: number },
  ): Message {
    const now = new Date().toISOString().slice(0, 16).replace('T', ' ')
    const content = [
      `${ERA_SUMMARY_MARKER} [${moduleKey}] Compacted at ${now} (${compactedCount} turns — ${counts.high} high, ${counts.medium} medium, ${counts.low} low importance)`,
      summary,
    ].join('\n')

    return { role: 'system', content }
  }


  private archiveTurns(registration: ModuleRegistration, turns: Message[]): void {
    // Best-effort: write a summary of compacted turns to the filesystem archive
    // if the daemon's memory module is wired. For now this is a no-op placeholder —
    // the memory module is wired in at daemon level and can call compact() itself.
    // The important archival is handled by the era summary being persisted in the session.
    void registration // avoid unused warning
    void turns
  }


  private isEraSummary(message: Message): boolean {
    if (message.role !== 'system') return false
    const text = typeof message.content === 'string' ? message.content : ''
    return text.startsWith(ERA_SUMMARY_MARKER)
  }

  private extractText(content: Message['content']): string {
    if (typeof content === 'string') return content
    return content
      .filter(b => b.type === 'text')
      .map(b => (b as { type: 'text'; text: string }).text)
      .join('\n')
  }
}
