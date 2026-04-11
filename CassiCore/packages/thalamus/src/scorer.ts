import type { ILogger } from '../../../types/interfaces.js'
import type { SystemLuminanceScore } from '../workspace/cognitive-signal.js'
import type { BrainContext, ScoredMessage } from './types.js'

const THALAMUS_WEIGHTS = {
  novelty: 0.15,
  urgency: 0.15,
  relevance: 0.50,
  sourceCredibility: 0.20,
} as const
import { MESSAGE_CREDIBILITY_PRIORS } from './types.js'

const STOP_WORDS = new Set([
  'the', 'and', 'for', 'not', 'but', 'are', 'was', 'all', 'can', 'had',
  'her', 'his', 'one', 'our', 'out', 'has', 'its', 'let', 'say', 'she',
  'too', 'use', 'way', 'who', 'how', 'any', 'may', 'got', 'get', 'did',
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

export class MessageLuminanceScorer {
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child('thalamus-scorer')
  }

  scoreAll(
    messages: any[],
    ctx: BrainContext,
    protectedStart: number,
  ): ScoredMessage[] {
    const total = messages.length
    const scored: ScoredMessage[] = []

    for (let i = 0; i < total; i++) {
      const msg = messages[i]

      if (i >= protectedStart) {
        scored.push({
          messageIndex: i,
          luminance: { novelty: 1, urgency: 1, relevance: 1, sourceCredibility: 1, composite: 1 },
          estimatedChars: this.estimateChars(msg),
        })
        continue
      }

      const nov = this.novelty(msg, ctx)
      const urg = this.urgency(msg, i, total)
      const rel = this.relevance(msg, ctx)
      const cred = this.credibility(msg)

      const composite =
        THALAMUS_WEIGHTS.novelty * nov +
        THALAMUS_WEIGHTS.urgency * urg +
        THALAMUS_WEIGHTS.relevance * rel +
        THALAMUS_WEIGHTS.sourceCredibility * cred

      const luminance: SystemLuminanceScore = {
        novelty: nov,
        urgency: urg,
        relevance: rel,
        sourceCredibility: cred,
        composite,
      }

      scored.push({
        messageIndex: i,
        luminance,
        estimatedChars: this.estimateChars(msg),
      })
    }

    return scored
  }

  /**
   * Novelty: unique information not covered by memory or redundant with other messages.
   * Mnemonic coverage → low novelty (memory already holds this).
   * High unique-term density → high novelty.
   */
  private novelty(msg: any, ctx: BrainContext): number {
    const content = extractMessageContent(msg).toLowerCase()
    if (!content) return 0

    const terms = extractTerms(content)
    if (terms.length === 0) return 0.1

    // Mnemonic anti-coverage: terms already in long-term memory reduce novelty
    let mnemonicOverlap = 0
    if (ctx.mnemonicTerms.size > 0) {
      for (const term of terms) {
        if (ctx.mnemonicTerms.has(term)) mnemonicOverlap++
      }
    }
    const mnemonicRatio = terms.length > 0 ? mnemonicOverlap / terms.length : 0

    // Unique term density — how much distinct information per unit length
    const uniqueTerms = new Set(terms)
    const density = Math.min(1.0, uniqueTerms.size / Math.max(content.length / 50, 1))

    // Novelty is high density minus mnemonic overlap
    return Math.max(0, Math.min(1.0, density * (1 - mnemonicRatio * 0.7)))
  }

  /**
   * Urgency: exponential recency decay + role-based boost.
   * Recent messages are urgent. User instructions get a floor.
   */
  private urgency(msg: any, index: number, total: number): number {
    if (total <= 1) return 1.0

    // Exponential decay — much steeper than linear, drops old messages faster
    const position = index / (total - 1)
    const recency = Math.pow(position, 2.5)

    // Role boost: user messages carry instructions that may still be active
    const role = msg?.role
    if (role === 'user') return Math.max(0.15, recency)

    return Math.max(0.02, recency)
  }

  /**
   * Relevance: alignment with current GWT focus + workspace signals + active files.
   * Merges the old focusOverlap, workspaceAlignment, and editProximity.
   */
  private relevance(msg: any, ctx: BrainContext): number {
    const content = extractMessageContent(msg).toLowerCase()
    if (!content) return 0

    // GWT focus relevance (primary)
    let focusScore = 0
    if (ctx.focusTerms.size > 0 || ctx.focusFiles.size > 0) {
      focusScore = this.termOverlap(content, ctx.focusTerms, ctx.focusFiles)
    } else if (ctx.recentMessageTerms.size > 0) {
      focusScore = this.termOverlap(content, ctx.recentMessageTerms, ctx.recentMessageFiles)
    }

    // Workspace signal alignment — boost from broadcast winners
    let workspaceScore = 0
    for (const sig of ctx.workspaceSignals) {
      const sigTerms = extractTerms(sig.content)
      const overlap = sigTerms.filter(t => content.includes(t)).length
      if (overlap > 0) {
        const match = Math.min(1.0, overlap / Math.max(sigTerms.length * 0.25, 1))
        const weighted = match * sig.luminance.composite
        workspaceScore = Math.max(workspaceScore, weighted)
      }
    }

    // File proximity — does this message touch files we're focused on
    let fileScore = 0
    const allFiles = new Set([...ctx.focusFiles, ...ctx.recentMessageFiles])
    if (allFiles.size > 0 && Array.isArray(msg?.content)) {
      for (const block of msg.content) {
        if (block?.type === 'tool_use') {
          const input = block.input ?? {}
          const filePath = input.filePath ?? input.path ?? input.relative_path ?? input.file_path ?? ''
          if (filePath && allFiles.has(filePath)) {
            fileScore = 1.0
            break
          }
          const fileName = filePath.split('/').pop() ?? ''
          for (const f of allFiles) {
            if (f.endsWith(fileName) && fileName.length > 3) {
              fileScore = 0.8
              break
            }
          }
        }
      }
    }

    // Composite relevance: focus is primary, workspace and file proximity add signal
    return Math.min(1.0, focusScore * 0.5 + workspaceScore * 0.3 + fileScore * 0.2)
  }

  /**
   * Credibility: static priors based on message role and content type.
   * User instructions are almost always useful. Old assistant reasoning rarely is.
   */
  private credibility(msg: any): number {
    const role = msg?.role ?? ''

    if (role === 'user') {
      const hasToolResult = Array.isArray(msg?.content) &&
        msg.content.some((c: any) => c?.type === 'tool_result')
      return hasToolResult
        ? (MESSAGE_CREDIBILITY_PRIORS['user:tool_result'] ?? 0.70)
        : (MESSAGE_CREDIBILITY_PRIORS['user'] ?? 0.90)
    }

    if (role === 'assistant') {
      const hasToolUse = Array.isArray(msg?.content) &&
        msg.content.some((c: any) => c?.type === 'tool_use')
      return hasToolUse
        ? (MESSAGE_CREDIBILITY_PRIORS['assistant:tool_use'] ?? 0.65)
        : (MESSAGE_CREDIBILITY_PRIORS['assistant'] ?? 0.40)
    }

    return MESSAGE_CREDIBILITY_PRIORS[role] ?? 0.20
  }

  private termOverlap(content: string, terms: Set<string>, files: Set<string>): number {
    if (terms.size === 0 && files.size === 0) return 0

    let hits = 0
    let checks = 0

    for (const file of files) {
      checks++
      if (content.includes(file) || content.includes(file.split('/').pop() ?? '')) hits++
    }

    for (const term of terms) {
      if (term.length < 4) continue
      checks++
      if (content.includes(term)) hits++
    }

    return checks > 0 ? Math.min(1.0, hits / Math.max(checks * 0.25, 1)) : 0
  }

  private estimateChars(msg: any): number {
    return extractMessageContent(msg).length
  }
}

export function extractMessageContent(msg: any): string {
  if (!msg) return ''
  if (typeof msg.content === 'string') return msg.content
  if (Array.isArray(msg.content)) {
    return msg.content
      .map((c: any) => {
        if (typeof c === 'string') return c
        if (c?.type === 'text') return c.text ?? ''
        if (c?.type === 'tool_use') return `tool:${c.name ?? ''} ${JSON.stringify(c.input ?? {}).slice(0, 200)}`
        if (c?.type === 'tool_result') {
          const inner = Array.isArray(c.content)
            ? c.content.map((b: any) => b?.text ?? '').join('\n')
            : (typeof c.content === 'string' ? c.content : '')
          return inner
        }
        return ''
      })
      .join('\n')
  }
  return ''
}

export function extractTerms(text: string): string[] {
  const lower = text.toLowerCase()
  const words = lower.match(/[a-z_][a-z0-9_]{2,}/g) ?? []
  return words.filter(w => !STOP_WORDS.has(w))
}

export function extractFilePaths(text: string): string[] {
  const paths: string[] = []
  const urlStripped = text.replace(/https?:\/\/\S+/g, '')
  const matches = urlStripped.match(/(?:[\w.-]+\/)+[\w.-]+\.\w+/g)
  if (matches) {
    for (const m of matches) {
      if (m.split('/').length >= 2) {
        paths.push(m)
      }
    }
  }
  return paths
}
