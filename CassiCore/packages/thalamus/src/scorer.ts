import type { ILogger } from '../../../types/interfaces.js'
import type { SystemLuminanceScore } from '../workspace/cognitive-signal.js'
import type { BrainContext, ScoredMessage } from './types.js'

/**
 * Five-axis luminance scoring:
 * - novelty (12%): unique information, self-model-aware
 * - urgency (13%): recency decay + role boost
 * - relevance (40%): focus + workspace + file + architectural + cortex-weighted
 * - sourceCredibility (15%): dynamic, pineal + architectural concept modulated
 * - cognitiveResonance (20%): alignment with brain state (executive goals, affect, insights, identity)
 */
const THALAMUS_WEIGHTS = {
  novelty: 0.12,
  urgency: 0.13,
  relevance: 0.40,
  sourceCredibility: 0.15,
  cognitiveResonance: 0.20,
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

      // Pre-extract content once — reused across all scoring axes
      const content = extractMessageContent(msg).toLowerCase()
      const terms = extractTerms(content)

      const nov = this.novelty(content, terms, ctx)
      const urg = this.urgency(msg, i, total)
      const rel = this.relevance(msg, content, ctx)
      const cred = this.credibility(msg, content, ctx)
      const res = this.cognitiveResonance(content, ctx)

      const composite =
        THALAMUS_WEIGHTS.novelty * nov +
        THALAMUS_WEIGHTS.urgency * urg +
        THALAMUS_WEIGHTS.relevance * rel +
        THALAMUS_WEIGHTS.sourceCredibility * cred +
        THALAMUS_WEIGHTS.cognitiveResonance * res

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
   * Self-model-aware: content known to the architecture but absent from episodic memory
   * represents structurally novel information worth retaining.
   */
  private novelty(content: string, terms: string[], ctx: BrainContext): number {
    if (!content) return 0
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

    // Self-model architectural novelty: content known to architecture
    // but NOT to episodic memory = structurally important new information
    let architecturalNovelty = 0
    if (ctx.architecturalTerms.size > 0 && terms.length > 0) {
      let archHits = 0
      let mnemoHits = 0
      for (const term of terms) {
        if (ctx.architecturalTerms.has(term)) archHits++
        if (ctx.mnemonicTerms.has(term)) mnemoHits++
      }
      // Architecturally known but episodically novel = high value
      if (archHits > 0 && mnemoHits === 0) {
        architecturalNovelty = Math.min(0.4, archHits / terms.length)
      }
    }

    // Novelty is high density minus mnemonic overlap, plus architectural novelty bonus
    return Math.max(0, Math.min(1.0,
      density * (1 - mnemonicRatio * 0.7) + architecturalNovelty,
    ))
  }

  /**
   * Urgency: exponential recency decay + role-based boost.
   * Recent messages are urgent. User instructions get a floor.
   */
  private urgency(msg: any, index: number, total: number): number {
    if (total <= 1) return 1.0

    // Prefer real timestamp-based urgency from _thalamus annotation
    const ts: string | undefined = msg?._thalamus?.ts
    if (ts) {
      const msgTime = new Date(ts).getTime()
      const now = Date.now()
      const ageMs = Math.max(0, now - msgTime)
      const halfLifeMs = 10 * 60 * 1000 // 10 minutes
      const temporalUrgency = 1 / (1 + ageMs / halfLifeMs)

      // Role boost: user messages carry instructions that may still be active
      if (msg?.role === 'user' && !msg._thalamus?.tool) {
        return Math.max(0.15, temporalUrgency)
      }
      return Math.max(0.02, temporalUrgency)
    }

    // Fallback: positional decay for un-annotated messages
    const position = index / (total - 1)
    const recency = Math.pow(position, 2.5)

    const role = msg?.role
    if (role === 'user') return Math.max(0.15, recency)

    return Math.max(0.02, recency)
  }

  /**
   * Relevance: alignment with current cognitive focus across five sub-signals:
   * - GWT focus overlap (30%): primary attentional focus terms + files
   * - Workspace signals (15%): GWT broadcast winner alignment
   * - File proximity (10%): messages touching actively-focused files
   * - Architectural alignment (20%): self-model concept matching
   * - Cortex-weighted alignment (25%): weighted by signal type, region, salience
   */
  private relevance(msg: any, content: string, ctx: BrainContext): number {
    if (!content) return 0

    // 1. GWT focus relevance (30%)
    let focusScore = 0
    if (ctx.focusTerms.size > 0 || ctx.focusFiles.size > 0) {
      focusScore = this.termOverlap(content, ctx.focusTerms, ctx.focusFiles)
    } else if (ctx.recentMessageTerms.size > 0) {
      focusScore = this.termOverlap(content, ctx.recentMessageTerms, ctx.recentMessageFiles)
    }

    // 2. Workspace signal alignment (15%)
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

    // 3. File proximity (10%)
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

    // 4. Architectural alignment (20%) — self-model concept matching
    let archScore = 0
    if (ctx.architecturalTerms.size > 0) {
      archScore = this.termOverlap(content, ctx.architecturalTerms, new Set())
      // Strong boost if message names a specific architectural concept
      for (const concept of ctx.architecturalConcepts) {
        if (concept.length > 3 && content.includes(concept)) {
          archScore = Math.max(archScore, 0.8)
          break
        }
      }
    }

    // 5. Cortex-weighted signal alignment (25%) — signal metadata matters
    let cortexScore = 0

    // High-salience signals: weighted by pre-computed importance
    for (const ws of ctx.cortexIndex.highSalience) {
      const overlap = ws.terms.filter(t => content.includes(t)).length
      if (overlap > 0) {
        const match = Math.min(1.0, overlap / Math.max(ws.terms.length * 0.3, 1))
        cortexScore = Math.max(cortexScore, match * Math.min(1.0, ws.weight))
      }
    }

    // Working memory boost — messages about actively focused thoughts
    for (const ws of ctx.cortexIndex.workingMemory) {
      const overlap = ws.terms.filter(t => content.includes(t)).length
      if (overlap > 0) {
        cortexScore = Math.max(cortexScore, 0.9)
        break
      }
    }

    // Threat boost — messages relevant to active concerns/anomalies
    for (const ws of ctx.cortexIndex.threats) {
      const overlap = ws.terms.filter(t => content.includes(t)).length
      if (overlap > 0) {
        cortexScore = Math.max(cortexScore, 0.85)
        break
      }
    }

    return Math.min(1.0,
      focusScore * 0.30 + workspaceScore * 0.15 + fileScore * 0.10 +
      archScore * 0.20 + cortexScore * 0.25,
    )
  }

  /**
   * Credibility: dynamic priors modulated by brain state.
   * Base priors by role (user=0.90, assistant=0.40), then:
   * - Pineal conviction boost: messages aligned with high-conviction identity concepts
   * - Architectural concept boost: messages discussing known patterns/principles
   */
  private credibility(msg: any, content: string, ctx: BrainContext): number {
    const role = msg?.role ?? ''

    let base: number
    if (role === 'user') {
      const hasToolResult = Array.isArray(msg?.content) &&
        msg.content.some((c: any) => c?.type === 'tool_result')
      base = hasToolResult
        ? (MESSAGE_CREDIBILITY_PRIORS['user:tool_result'] ?? 0.70)
        : (MESSAGE_CREDIBILITY_PRIORS['user'] ?? 0.90)
    } else if (role === 'assistant') {
      const hasToolUse = Array.isArray(msg?.content) &&
        msg.content.some((c: any) => c?.type === 'tool_use')
      base = hasToolUse
        ? (MESSAGE_CREDIBILITY_PRIORS['assistant:tool_use'] ?? 0.65)
        : (MESSAGE_CREDIBILITY_PRIORS['assistant'] ?? 0.40)
    } else {
      base = MESSAGE_CREDIBILITY_PRIORS[role] ?? 0.20
    }

    // Pineal conviction boost: messages aligned with high-conviction identity/wisdom
    if (ctx.pinealPriorities.size > 0) {
      let maxConviction = 0
      for (const [term, conviction] of ctx.pinealPriorities) {
        if (content.includes(term)) maxConviction = Math.max(maxConviction, conviction)
      }
      if (maxConviction > 0.5) {
        base = Math.min(1.0, base + 0.10)
      }
    }

    // Architectural concept boost: messages discussing known patterns/principles
    if (ctx.architecturalHits.length > 0) {
      for (const hit of ctx.architecturalHits) {
        if ((hit.nodeType === 'pattern' || hit.nodeType === 'principle') &&
            hit.conceptName.length > 3 && content.includes(hit.conceptName)) {
          base = Math.min(1.0, base + 0.08)
          break
        }
      }
    }

    return base
  }

  /**
   * Cognitive Resonance (NEW axis): alignment with the current brain state.
   * Measures how well a message resonates with active cognitive processes:
   * - Executive signals: messages about active goals/decisions
   * - Affect modulation: messages relevant to current emotional state
   * - Insight resonance: messages about discovered patterns
   * - Pineal identity alignment: messages echoing core identity/wisdom
   * - Working memory alignment: messages about consciously focused topics
   */
  private cognitiveResonance(content: string, ctx: BrainContext): number {
    if (!content) return 0

    let score = 0

    // 1. Executive signal alignment — messages about active goals/decisions
    const executiveSignals = ctx.cortexIndex.byRegion?.executive ?? []
    for (const ws of executiveSignals) {
      if (ws.terms.some(t => content.includes(t))) {
        score = Math.max(score, 0.8 * ws.signal.confidence)
      }
    }

    // 2. Affect modulation — emotional state modulates what's important
    if (ctx.affectState) {
      const { valence, arousal } = ctx.affectState
      if (valence < -0.2 && arousal > 0.4) {
        // Negative + high arousal = alarmed/frustrated — keep error/fix messages
        if (/error|fail|bug|fix|issue|problem|broken|crash|exception/.test(content)) {
          score = Math.max(score, 0.7)
        }
      }
      if (valence > 0.3 && arousal > 0.3) {
        // Positive + moderate arousal = engaged — keep implementation messages
        if (/implement|create|build|add|feature|design|refactor/.test(content)) {
          score = Math.max(score, 0.5)
        }
      }
    }

    // 3. Insight resonance — messages about discovered patterns/insights
    const insights = ctx.cortexIndex.byType?.insight ?? []
    for (const ws of insights) {
      if (ws.terms.some(t => content.includes(t))) {
        score = Math.max(score, 0.6)
        break
      }
    }

    // 4. Concern resonance — messages addressing active concerns
    const concerns = ctx.cortexIndex.byType?.concern ?? []
    for (const ws of concerns) {
      if (ws.terms.some(t => content.includes(t))) {
        score = Math.max(score, 0.65 * ws.signal.salience)
        break
      }
    }

    // 5. Working memory alignment — messages about consciously focused topics
    if (ctx.workingMemoryTerms.size > 0) {
      const wmHits = Array.from(ctx.workingMemoryTerms).filter(t => content.includes(t)).length
      if (wmHits > 0) {
        const ratio = Math.min(1.0, wmHits / Math.max(ctx.workingMemoryTerms.size * 0.2, 1))
        score = Math.max(score, 0.7 * ratio)
      }
    }

    // 6. Pineal identity alignment — messages echoing core identity/wisdom
    if (ctx.pinealTerms.size > 0) {
      const pinealHits = Array.from(ctx.pinealTerms).filter(t => content.includes(t)).length
      if (pinealHits > 2) {
        score = Math.max(score, 0.4) // Identity-aligned gets a floor
      }
    }

    return Math.min(1.0, score)
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
    // WHY: External clients (OpenCode plugin) send truncated digests (≤2000 chars)
    // but attach the REAL char count as _originalChars. Without this, the thalamus
    // thinks each message is ~2KB and keeps 10-50x more content than the budget
    // allows, causing context window overflow.
    if (typeof msg?._originalChars === 'number' && msg._originalChars > 0) {
      return msg._originalChars
    }
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
