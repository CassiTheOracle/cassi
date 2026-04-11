import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { MessageScorer, extractTerms, extractFilePaths, extractMessageContent } from './scorer.js'
import { ToolResultCompressor } from './compressor.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { CorticalField } from '../cortex/index.js'
import type { MnemicField } from '../mnemic-field/index.js'
import type {
  CurationConfig,
  CurationResult,
  CurationSession,
  BrainContext,
} from './types.js'
import { DEFAULT_CURATION_CONFIG } from './types.js'

const SESSION_EVICT_MS = 2 * 60 * 60 * 1000

export class ThalamusModule extends BaseCognitiveModule {
  readonly name = 'thalamus'
  readonly priority = 85

  private scorer!: MessageScorer
  private compressor!: ToolResultCompressor
  private sessions = new Map<string, CurationSession>()
  private evictionTimer: ReturnType<typeof setInterval> | null = null

  private cortex: CorticalField | null = null
  private mnemicField: MnemicField | null = null

  constructor(logger: ILogger) {
    super(logger)
    this.logger = logger.child('thalamus')
  }

  async init(): Promise<void> {
    await super.init()
    this.scorer = new MessageScorer(this.logger)
    this.compressor = new ToolResultCompressor(this.logger)
  }

  async start(): Promise<void> {
    await super.start()
    this.evictionTimer = setInterval(() => this.evictStaleSessions(), SESSION_EVICT_MS / 4)
  }

  async stop(): Promise<void> {
    if (this.evictionTimer) {
      clearInterval(this.evictionTimer)
      this.evictionTimer = null
    }
    this.sessions.clear()
    await super.stop()
  }

  setCortex(cortex: CorticalField): void {
    this.cortex = cortex
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }

  curate(sessionId: string, messages: any[], config?: Partial<CurationConfig>): CurationResult {
    const startTime = Date.now()
    const cfg = { ...DEFAULT_CURATION_CONFIG, ...this.getConfigOverrides(), ...config }

    if (cfg.excludeSessionPrefixes.some(p => sessionId.startsWith(p))) {
      return {
        messages,
        meta: {
          originalCount: messages.length,
          curatedCount: messages.length,
          originalChars: 0,
          curatedChars: 0,
          compressed: 0,
          deduped: 0,
          dropped: 0,
          gapNotes: 0,
          durationMs: Date.now() - startTime,
          skipped: true,
          reason: 'excluded-session-type',
        },
      }
    }

    if (!messages || messages.length < cfg.recentWindowSize + 5) {
      return {
        messages,
        meta: {
          originalCount: messages.length,
          curatedCount: messages.length,
          originalChars: 0,
          curatedChars: 0,
          compressed: 0,
          deduped: 0,
          dropped: 0,
          gapNotes: 0,
          durationMs: Date.now() - startTime,
          skipped: true,
          reason: 'below-threshold',
        },
      }
    }

    const session = this.getSession(sessionId)
    session.lastCuratedAt = Date.now()
    session.totalCurations++

    const originalChars = messages.reduce(
      (sum: number, m: any) => sum + extractMessageContent(m).length, 0
    )

    const brainContext = this.buildBrainContext(sessionId, messages)
    const recentWindowStart = Math.max(0, messages.length - cfg.recentWindowSize)

    const { messages: compressed, compressed: compressedCount, deduped } =
      this.compressor.compress(messages, recentWindowStart, { toolResultMaxChars: cfg.toolResultMaxChars }, session.fileReadMap)

    const scored = this.scorer.scoreAll(compressed, brainContext, recentWindowStart)

    const assembled = this.assembleWindow(compressed, scored, recentWindowStart, cfg.charBudget)

    const curatedChars = assembled.messages.reduce(
      (sum: number, m: any) => sum + extractMessageContent(m).length, 0
    )

    const durationMs = Date.now() - startTime
    if (durationMs > 200) {
      this.logger.info('Curation completed', {
        sessionId,
        originalCount: messages.length,
        curatedCount: assembled.messages.length,
        dropped: messages.length - assembled.messages.length,
        compressed: compressedCount,
        deduped,
        durationMs,
      })
    }

    return {
      messages: assembled.messages,
      meta: {
        originalCount: messages.length,
        curatedCount: assembled.messages.length,
        originalChars,
        curatedChars,
        compressed: compressedCount,
        deduped,
        dropped: messages.length - assembled.messages.length,
        gapNotes: assembled.gapNotes,
        durationMs,
      },
    }
  }

  getStats(): { sessions: number; totalCurations: number } {
    let totalCurations = 0
    for (const s of this.sessions.values()) {
      totalCurations += s.totalCurations
    }
    return { sessions: this.sessions.size, totalCurations }
  }

  private buildBrainContext(sessionId: string, messages: any[]): BrainContext {
    const cortexSignals = this.cortex?.readActive({ limit: 15, sessionId }) ?? []
    const cortexTerms = new Set<string>()
    const cortexFiles = new Set<string>()

    for (const sig of cortexSignals) {
      for (const term of extractTerms(sig.content)) cortexTerms.add(term)
      for (const file of extractFilePaths(sig.content)) cortexFiles.add(file)
    }

    const mnemonicTerms = new Set<string>()
    if (this.mnemicField) {
      try {
        const topEngrams = this.mnemicField.list(20).filter(e => e.potentiation > 0.4)
        for (const e of topEngrams) {
          for (const term of extractTerms(e.content)) mnemonicTerms.add(term)
        }
      } catch {
        // MnemicField may not be fully initialized — degrade gracefully
      }
    }

    const recentMessageTerms = new Set<string>()
    const recentMessageFiles = new Set<string>()
    const recentWindow = 10
    let seen = 0
    for (let i = messages.length - 1; i >= 0 && seen < recentWindow; i--) {
      const msg = messages[i]
      if (msg?.role !== 'user' && msg?.role !== 'assistant') continue
      seen++
      const content = extractMessageContent(msg)
      for (const term of extractTerms(content)) recentMessageTerms.add(term)
      for (const file of extractFilePaths(content)) recentMessageFiles.add(file)
    }

    return {
      cortexSignals,
      cortexTerms,
      cortexFiles,
      mnemonicTerms,
      recentMessageTerms,
      recentMessageFiles,
    }
  }

  private assembleWindow(
    messages: any[],
    scored: ScoredMessage[],
    recentWindowStart: number,
    charBudget: number,
  ): { messages: any[]; gapNotes: number } {
    const recentMessages = messages.slice(recentWindowStart)
    let recentChars = 0
    for (const m of recentMessages) {
      recentChars += extractMessageContent(m).length
    }

    let remainingBudget = charBudget - recentChars
    if (remainingBudget <= 0) {
      return { messages: recentMessages, gapNotes: 0 }
    }

    const olderScored = scored
      .filter(s => s.messageIndex < recentWindowStart)
      .sort((a, b) => b.score - a.score)

    const includedIndices = new Set<number>()
    for (const s of olderScored) {
      if (remainingBudget <= 0) break

      const chars = s.estimatedChars
      if (s.mnemonicallyCovered) {
        if (s.score < 0.3) continue
      }
      if (chars <= remainingBudget) {
        includedIndices.add(s.messageIndex)
        remainingBudget -= chars
      }
    }

    this.ensureAlternation(messages, includedIndices, recentWindowStart)

    const allIndices = [
      ...Array.from(includedIndices).sort((a, b) => a - b),
      ...Array.from({ length: messages.length - recentWindowStart }, (_, i) => recentWindowStart + i),
    ]

    const assembled: any[] = []
    let gapNotes = 0

    for (let j = 0; j < allIndices.length; j++) {
      const idx = allIndices[j]
      const prevIdx = j > 0 ? allIndices[j - 1] : idx - 1

      if (idx - prevIdx > 2 && j > 0) {
        const gapSize = idx - prevIdx - 1
        const gapMsg = messages[idx]
        if (gapMsg && Array.isArray(gapMsg.content)) {
          const noted = [
            { type: 'text', text: `[${gapSize} turns omitted]` },
            ...gapMsg.content,
          ]
          assembled.push({ ...gapMsg, content: noted })
          gapNotes++
          continue
        }
      }

      assembled.push(messages[idx])
    }

    return { messages: assembled, gapNotes }
  }

  private ensureAlternation(
    messages: any[],
    included: Set<number>,
    recentWindowStart: number,
  ): void {
    const sorted = Array.from(included).sort((a, b) => a - b)

    for (let i = 0; i < sorted.length - 1; i++) {
      const curr = sorted[i]
      const next = sorted[i + 1]
      if (messages[curr]?.role === messages[next]?.role) {
        for (let bridge = curr + 1; bridge < next; bridge++) {
          if (messages[bridge]?.role !== messages[curr]?.role && bridge < recentWindowStart) {
            included.add(bridge)
            break
          }
        }
      }
    }

    if (sorted.length > 0) {
      const lastOlder = sorted[sorted.length - 1]
      const firstRecent = recentWindowStart
      if (firstRecent < messages.length && messages[lastOlder]?.role === messages[firstRecent]?.role) {
        for (let bridge = lastOlder + 1; bridge < firstRecent; bridge++) {
          if (messages[bridge]?.role !== messages[lastOlder]?.role) {
            included.add(bridge)
            break
          }
        }
      }
    }
  }

  private getSession(sessionId: string): CurationSession {
    let session = this.sessions.get(sessionId)
    if (!session) {
      session = {
        sessionId,
        scoreCache: new Map(),
        fileReadMap: new Map(),
        lastCuratedAt: Date.now(),
        totalCurations: 0,
      }
      this.sessions.set(sessionId, session)
    }
    return session
  }

  private evictStaleSessions(): void {
    const now = Date.now()
    for (const [id, session] of this.sessions) {
      if (now - session.lastCuratedAt > SESSION_EVICT_MS) {
        this.sessions.delete(id)
      }
    }
  }

  private getConfigOverrides(): Partial<CurationConfig> {
    if (!this.config) return {}
    const overrides: Partial<CurationConfig> = {}
    const budget = this.config.get<number>('intelligence.thalamus.charBudget', undefined)
    if (budget) overrides.charBudget = budget
    const window = this.config.get<number>('intelligence.thalamus.recentWindowSize', undefined)
    if (window) overrides.recentWindowSize = window
    const maxChars = this.config.get<number>('intelligence.thalamus.toolResultMaxChars', undefined)
    if (maxChars) overrides.toolResultMaxChars = maxChars
    const prefixes = this.config.get<string[]>('intelligence.thalamus.excludeSessionPrefixes', undefined)
    if (prefixes) overrides.excludeSessionPrefixes = prefixes
    return overrides
  }
}

import type { ScoredMessage } from './types.js'
