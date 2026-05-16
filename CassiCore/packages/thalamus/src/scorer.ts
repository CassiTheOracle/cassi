import type { ILogger } from '../../../types/interfaces.js'
import type { SystemLuminanceScore } from '../workspace/cognitive-signal.js'
import type { BrainContext, ScoredMessage } from './types.js'
import { hasQuestionResult, buildToolUseMapFromMessages } from '../../pipeline/turn/overflow.js'
import { EPISTEMIC_SHIFT_PHRASES } from '../phrase-prototypes.js'
import type { MnemicField } from '../mnemic-field/index.js'

/**
 * Six-axis luminance scoring:
 * - novelty (10%): unique information, self-model-aware
 * - urgency (12%): recency decay + role boost
 * - relevance (35%): focus + recent conversation + workspace + file + architectural + cortex-weighted,
 *                     with phase-coherence modulation to suppress stale signals
 * - sourceCredibility (13%): dynamic, pineal + architectural concept modulated
 * - cognitiveResonance (15%): alignment with brain state (executive goals, affect, insights, identity)
 * - strategicImportance (15%): enduring significance — user decisions, cross-topic landmarks, error anchors
 */
const THALAMUS_WEIGHTS = {
  novelty: 0.10,
  urgency: 0.12,
  relevance: 0.35,
  sourceCredibility: 0.13,
  cognitiveResonance: 0.15,
  strategicImportance: 0.15,
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
  private currentToolUseMap: Map<string, string> = new Map()
  private mnemicField?: MnemicField

  constructor(logger: ILogger) {
    this.logger = logger.child('thalamus-scorer')
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }

  async applyEpistemicBoosts(scored: ScoredMessage[], messages: any[]): Promise<void> {
    if (!this.mnemicField) return
    for (const sm of scored) {
      if (sm.luminance.composite >= 1) continue
      const content = extractMessageContent(messages[sm.messageIndex]).toLowerCase()
      if (!content) continue
      const result = await this.mnemicField.classifyPhrase(content, EPISTEMIC_SHIFT_PHRASES).catch(() => null)
      if (!result || !result.label || result.score < 0.40) continue

      const multipliers: Record<string, number> = {
        reversal: 0.30,
        revelation: 0.25,
        resolution: 0.15,
        confirmation: 0.08,
      }
      const boost = (multipliers[result.label] ?? 0) * result.score
      if (boost > 0) {
        sm.luminance.cognitiveResonance = Math.min(1, sm.luminance.cognitiveResonance + boost)
        sm.luminance.composite = Math.min(1, sm.luminance.composite + boost * 0.5)
      }
    }
  }

  scoreAll(
    messages: any[],
    ctx: BrainContext,
    protectedStart: number,
  ): ScoredMessage[] {
    this.currentToolUseMap = buildToolUseMapFromMessages(messages)
    const total = messages.length
    const scored: ScoredMessage[] = []

    // Pre-build architectural concept map for O(1) lookup in credibility scoring.
    // Only pattern/principle hits with concept names longer than 3 characters
    // contribute to credibility boosts, so we filter and index once.
    const archConceptMap = new Map<string, { nodeType: string; conceptName: string }>()
    for (const hit of ctx.architecturalHits) {
      if ((hit.nodeType === 'pattern' || hit.nodeType === 'principle') &&
          hit.conceptName.length > 3) {
        archConceptMap.set(hit.conceptName, { nodeType: hit.nodeType, conceptName: hit.conceptName })
      }
    }

    for (let i = 0; i < total; i++) {
      const msg = messages[i]

      if (i >= protectedStart) {
        scored.push({
          messageIndex: i,
          luminance: { novelty: 1, urgency: 1, relevance: 1, sourceCredibility: 1, cognitiveResonance: 1, strategicImportance: 1, composite: 1 },
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
      const cred = this.credibility(msg, content, ctx, archConceptMap)
      const res = this.cognitiveResonance(content, ctx)
      const strat = this.strategicImportance(msg, content, terms, i, messages, ctx)

      const composite =
        THALAMUS_WEIGHTS.novelty * nov +
        THALAMUS_WEIGHTS.urgency * urg +
        THALAMUS_WEIGHTS.relevance * rel +
        THALAMUS_WEIGHTS.sourceCredibility * cred +
        THALAMUS_WEIGHTS.cognitiveResonance * res +
        THALAMUS_WEIGHTS.strategicImportance * strat

      const luminance: SystemLuminanceScore = {
        novelty: nov,
        urgency: urg,
        relevance: rel,
        sourceCredibility: cred,
        cognitiveResonance: res,
        strategicImportance: strat,
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

      // Role boost: user messages carry instructions that may still be active.
      // AskUserQuestion answers arrive as tool_result blocks but are semantically
      // user input — they must receive the same urgency floor as plain user messages.
      if (msg?.role === 'user' && (!msg._thalamus?.tool || hasQuestionResult(msg, { toolUseMap: this.currentToolUseMap }))) {
        return Math.max(0.25, temporalUrgency)
      }
      return Math.max(0.02, temporalUrgency)
    }

    // Fallback: positional decay for un-annotated messages
    const position = index / (total - 1)
    const recency = Math.pow(position, 2.5)

    const role = msg?.role
    if (role === 'user') return Math.max(0.25, recency)

    return Math.max(0.02, recency)
  }

  /**
   * Relevance: alignment with current cognitive focus across five sub-signals:
   * - GWT focus overlap (25%): primary attentional focus terms + files, modulated by phase coherence
   * - Recent conversation overlap (15%): always-on signal from recent messages (phase-independent)
   * - Workspace signals (10%): GWT broadcast winner alignment
   * - File proximity (10%): messages touching actively-focused files
   * - Architectural alignment (15%): self-model concept matching
   * - Cortex-weighted alignment (25%): weighted by signal type, region, salience
   *
   * Phase coherence modulates focus/cortex axes: when the conversation has shifted
   * topics but cortex/focus signals are stale, their contribution is reduced so
   * completed work phases don't get resurfaced.
   */
  private relevance(msg: any, content: string, ctx: BrainContext): number {
    if (!content) return 0

    const pc = ctx.phaseCoherence ?? 1.0

    // 1. GWT focus relevance (25%) — modulated by phase coherence
    let focusScore = 0
    if (ctx.focusTerms.size > 0 || ctx.focusFiles.size > 0) {
      focusScore = this.termOverlap(content, ctx.focusTerms, ctx.focusFiles) * pc
    }

    // 2. Recent conversation overlap (15%) — always-on, phase-independent
    //    This ensures the thalamus tracks what's CURRENTLY being discussed,
    //    not just what cortex/focus signals remember from earlier phases.
    let recentScore = 0
    if (ctx.recentMessageTerms.size > 0 || ctx.recentMessageFiles.size > 0) {
      recentScore = this.termOverlap(content, ctx.recentMessageTerms, ctx.recentMessageFiles)
    }

    // 3. Workspace signal alignment (10%)
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

    // 4. File proximity (10%)
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

    // 5. Architectural alignment (15%) — self-model concept matching
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

    // 6. Cortex-weighted signal alignment (25%) — modulated by phase coherence
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

    // Apply phase coherence to cortex score — stale signals contribute less
    cortexScore *= pc

    return Math.min(1.0,
      focusScore * 0.25 + recentScore * 0.15 + workspaceScore * 0.10 + fileScore * 0.10 +
      archScore * 0.15 + cortexScore * 0.25,
    )
  }

  /**
   * Credibility: dynamic priors modulated by brain state.
   * Base priors by role (user=0.90, assistant=0.40), then:
   * - Pineal conviction boost: messages aligned with high-conviction identity concepts
   * - Architectural concept boost: messages discussing known patterns/principles
   */
  private credibility(msg: any, content: string, ctx: BrainContext, archConceptMap?: Map<string, { nodeType: string; conceptName: string }>): number {
    const role = msg?.role ?? ''

    let base: number
    if (role === 'user') {
      const hasToolResult = Array.isArray(msg?.content) &&
        msg.content.some((c: any) => c?.type === 'tool_result')
      // AskUserQuestion answers wrap user intent in a tool_result block —
      // they're real user messages and earn the full user-credibility prior.
      const isQuestionAnswer = hasQuestionResult(msg, { toolUseMap: this.currentToolUseMap })
      base = (hasToolResult && !isQuestionAnswer)
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

    // Architectural concept boost: O(1) lookup via pre-built map.
    // If archConceptMap is provided, iterate the message content's terms
    // and check for matches against known pattern/principle concept names.
    if (archConceptMap && archConceptMap.size > 0) {
      for (const term of extractTerms(content)) {
        if (archConceptMap.has(term)) {
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

  /**
   * Strategic importance: enduring significance independent of current topic.
   * Three signals: user decisions (lexical), cross-topic landmarks, error/commit anchors.
   */
  private strategicImportance(
    msg: any,
    content: string,
    terms: string[],
    index: number,
    allMessages: any[],
    ctx: BrainContext,
  ): number {
    let decision = 0
    let landmark = 0
    let anchor = 0

    // Signal 1: User decision/directive (lexical classifier over user messages)
    const role = (msg.role ?? '').toLowerCase()
    if (role === 'user') {
      decision = this.classifyUserDecision(content)
    }

    // Signal 2: Cross-topic landmark — terms appearing in multiple archived topic clusters
    const archiveTerms = ctx.topicArchiveTerms
    if (archiveTerms && archiveTerms.size > 0) {
      let clusterHits = 0
      for (const term of terms) {
        const count = archiveTerms.get(term)
        if (count && count >= 2) clusterHits++
      }
      if (clusterHits >= 2) landmark = 0.7
      else if (clusterHits >= 1) landmark = 0.4
    }

    // Signal 3: Error/commit anchor — proximity to errors or git commits
    const window = 2
    for (let j = Math.max(0, index - window); j <= Math.min(allMessages.length - 1, index + window); j++) {
      if (j === index) continue
      const neighbor = allMessages[j]
      const nRole = (neighbor.role ?? '').toLowerCase()
      if (nRole === 'tool') {
        // Tool errors
        const nContent = extractMessageContent(neighbor).toLowerCase()
        if (nContent.includes('"iserror":true') || nContent.includes('"iserror": true')
          || nContent.includes('error:') || nContent.includes('failed')
          || nContent.includes('assertion') || nContent.includes('panic')) {
          anchor = 0.5
        }
        // Git commits
        const toolName = this.currentToolUseMap.get(neighbor.tool_use_id ?? '') ?? ''
        if (toolName === 'bash') {
          if (nContent.includes('git commit') || nContent.includes('git push')) {
            anchor = Math.max(anchor, 0.4)
          }
        }
      }
    }

    const raw = 0.50 * decision + 0.30 * landmark + 0.20 * anchor
    return Math.min(1.0, raw)
  }

  /** Lexical classifier for user decision/directive language. */
  private classifyUserDecision(content: string): number {
    // Strong signals — multi-word phrases that clearly indicate decisions
    const strong = [
      /\b(i want|i prefer|let's do|the right approach|we should|i'd like|make it)\b/i,
      /\b(not that|no not|no,? not|stop doing|don't do|wrong|incorrect|not what i)\b/i,
      /\b(instead|rather|actually|i meant|what i meant)\b/i,
      /\bgo with (?:approach|method|option|design|pattern)\b/i,
      /\b(yes,?\s+(?:commit|ship|proceed|do it|go ahead)|confirmed|sounds good|that works)\b/i,
    ]
    // Moderate signals — require sentence-initial position to avoid false positives
    const moderate = [
      /(?:^|[.!?]\s+)(use|skip|avoid|never|always|prefer|choose|select|delete|remove|rename|extract)\b/i,
      /\b(commit|ship|implement|refactor|create)\s+(?:this|the|a|an|it|now)\b/i,
    ]

    let score = 0
    for (const re of strong) if (re.test(content)) { score = Math.max(score, 0.8); break }
    for (const re of moderate) if (re.test(content)) { score = Math.max(score, 0.5); break }

    return score
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
