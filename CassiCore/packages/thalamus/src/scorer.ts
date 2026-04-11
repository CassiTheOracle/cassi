import type { ILogger } from '../../../types/interfaces.js'
import type { CorticalSignal } from '../cortex/types.js'
import type { BrainContext, ScoredMessage } from './types.js'

const CHARS_PER_TOKEN = 4

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

export class MessageScorer {
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child('thalamus-scorer')
  }

  scoreAll(
    messages: any[],
    brainContext: BrainContext,
    recentWindowStart: number,
  ): ScoredMessage[] {
    const total = messages.length
    const scored: ScoredMessage[] = []

    for (let i = 0; i < total; i++) {
      const msg = messages[i]

      if (i >= recentWindowStart) {
        scored.push({
          messageIndex: i,
          score: 1.0,
          estimatedChars: this.estimateChars(msg),
          mnemonicallyCovered: false,
        })
        continue
      }

      const recency = this.recencyScore(i, total)
      const refDensity = this.referenceDensityScore(msg, brainContext)
      const infoDensity = this.informationDensityScore(msg)
      const editProx = this.editProximityScore(msg, brainContext.cortexFiles, brainContext.recentMessageFiles)
      const cortexRel = this.cortexRelevance(msg, brainContext.cortexSignals)

      const score =
        0.35 * recency +
        0.25 * refDensity +
        0.20 * infoDensity +
        0.10 * editProx +
        0.10 * cortexRel

      const mnemonicallyCovered = this.checkMnemonicCoverage(msg, brainContext.mnemonicTerms)

      scored.push({
        messageIndex: i,
        score,
        estimatedChars: this.estimateChars(msg),
        mnemonicallyCovered,
      })
    }

    return scored
  }

  private recencyScore(index: number, total: number): number {
    if (total <= 1) return 1.0
    return 0.1 + 0.9 * (index / (total - 1))
  }

  private referenceDensityScore(msg: any, ctx: BrainContext): number {
    const content = extractMessageContent(msg).toLowerCase()
    if (!content) return 0

    const allTerms = new Set([...ctx.cortexTerms, ...ctx.recentMessageTerms])
    const allFiles = new Set([...ctx.cortexFiles, ...ctx.recentMessageFiles])
    if (allTerms.size === 0 && allFiles.size === 0) return 0

    let hits = 0
    let checks = 0

    for (const file of allFiles) {
      checks++
      if (content.includes(file) || content.includes(file.split('/').pop() ?? '')) {
        hits++
      }
    }

    for (const term of allTerms) {
      if (term.length < 4) continue
      checks++
      if (content.includes(term)) {
        hits++
      }
    }

    return checks > 0 ? Math.min(1.0, hits / Math.max(checks * 0.3, 1)) : 0
  }

  private informationDensityScore(msg: any): number {
    const role = msg?.role
    const content = extractMessageContent(msg)

    if (role === 'tool' || role === 'tool_result') return 0.8
    if (role === 'assistant') {
      const hasToolUse = Array.isArray(msg?.content) &&
        msg.content.some((c: any) => c?.type === 'tool_use')
      if (hasToolUse) return 0.7

      if (content.includes('```')) return 0.6
      return 0.3
    }
    if (role === 'user') {
      const hasToolResult = Array.isArray(msg?.content) &&
        msg.content.some((c: any) => c?.type === 'tool_result')
      if (hasToolResult) return 0.8
      return 0.5
    }
    if (role === 'system') return 0.2
    return 0.3
  }

  private editProximityScore(msg: any, cortexFiles: Set<string>, recentFiles: Set<string>): number {
    const allFiles = new Set([...cortexFiles, ...recentFiles])
    if (allFiles.size === 0) return 0

    if (Array.isArray(msg?.content)) {
      for (const block of msg.content) {
        if (block?.type === 'tool_use') {
          const input = block.input ?? {}
          const filePath = input.filePath ?? input.path ?? input.relative_path ?? input.file_path ?? ''
          if (filePath && allFiles.has(filePath)) return 1.0
          const basename = filePath.split('/').pop() ?? ''
          if (basename.length > 3) {
            for (const af of allFiles) {
              if (af.endsWith(basename)) return 0.8
            }
          }
        }
      }
    }

    return 0
  }

  private cortexRelevance(msg: any, signals: CorticalSignal[]): number {
    const content = extractMessageContent(msg).toLowerCase()
    if (!content || signals.length === 0) return 0

    let maxMatch = 0
    for (const sig of signals) {
      const sigTerms = extractTerms(sig.content)
      const overlap = sigTerms.filter(t => content.includes(t)).length
      if (overlap > 0) {
        const match = Math.min(1.0, overlap / Math.max(sigTerms.length * 0.3, 1))
        const weighted = match * sig.activation
        maxMatch = Math.max(maxMatch, weighted)
      }
    }

    return maxMatch
  }

  private checkMnemonicCoverage(msg: any, mnemonicTerms: Set<string>): boolean {
    if (mnemonicTerms.size === 0) return false

    const content = extractMessageContent(msg).toLowerCase()
    if (!content || content.length < 50) return false

    const msgTerms = extractTerms(content)
    if (msgTerms.length === 0) return false

    let covered = 0
    for (const term of msgTerms) {
      if (mnemonicTerms.has(term)) covered++
    }

    return (covered / msgTerms.length) > 0.6
  }

  private estimateChars(msg: any): number {
    const content = extractMessageContent(msg)
    let base = content.length

    if (Array.isArray(msg?.content)) {
      const toolBlocks = msg.content.filter(
        (c: any) => c?.type === 'tool_use' || c?.type === 'tool_result'
      )
      base += toolBlocks.length * 200
    }

    return Math.max(base, 40)
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
        if (c?.type === 'tool_result') return typeof c.content === 'string' ? c.content : ''
        return ''
      })
      .join('\n')
  }
  return ''
}

export function extractTerms(content: string): string[] {
  const words = content.toLowerCase().split(/[\s,;:.!?()\[\]{}'"]+/)
  return words.filter(w => w.length >= 4 && !STOP_WORDS.has(w))
}

export function extractFilePaths(content: string): string[] {
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

export function djb2Hash(str: string): number {
  let hash = 5381
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) + str.charCodeAt(i)
  }
  return hash >>> 0
}
