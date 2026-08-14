/**
 * Smart Compaction Engine
 *
 * Replaces naive LLM summarization with an intelligent multi-strategy approach:
 *
 *   1. Score every message by importance (recency, action impact, error signals, tool type)
 *   2. Cluster messages into topical groups
 *   3. Keep high-importance messages verbatim
 *   4. Summarize medium-importance clusters using an LLM
 *   5. Prune low-importance messages (preserving key files/tools referenced)
 *   6. Produce a structured compaction result with section-by-section output
 *
 * The engine adapts its strategy based on conversation pressure (how much context
 * needs to be freed) and task complexity (how many files/tools/errors are involved).
 *
 * Integrates with CassiCore's:
 *   - ModelPool for LLM summarization
 *   - Memory for relevant past context
 *   - Cognitive signals (thinker, dialectic, subconscious)
 *   - Session indexer for full-text search of compacted content
 */

import type { ILogger } from '@cassicore/foundation'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

/** Simplified message format matching what OpenCode sends to the compaction endpoint. */
export interface CompactionMessage {
  role: string
  content: string | ContentPart[]
}

interface ContentPart {
  type: string
  text?: string
  tool?: string
  toolCallId?: string
  [key: string]: unknown
}

export type ImportanceLevel = 'high' | 'medium' | 'low'

export interface ScoredMessage {
  index: number
  message: CompactionMessage
  importance: ImportanceLevel
  score: number
  reason: string
  textContent: string
}

export interface MessageCluster {
  id: string
  messages: ScoredMessage[]
  avgScore: number
  dominantImportance: ImportanceLevel
  /** Inferred topic from content analysis */
  topic: string
}

export interface SmartCompactionResult {
  /** The structured compaction summary */
  summary: string
  /** Number of messages kept verbatim */
  keptVerbatim: number
  /** Number of messages summarized by LLM */
  summarized: number
  /** Number of messages pruned */
  pruned: number
  /** Strategy used */
  strategy: CompactionStrategy
  /** Time taken in ms */
  durationMs: number
}

export type CompactionStrategy = 'conservative' | 'balanced' | 'aggressive' | 'critical'

export interface SmartCompactionConfig {
  /** Character budget for the entire compaction output. Default: 80,000 */
  outputCharBudget: number
  /** Number of most-recent messages to always preserve verbatim. Default: 8 */
  preserveRecentCount: number
  /** Minimum message count before smart compaction kicks in (below this, just keep all). Default: 12 */
  minMessagesForCompaction: number
  /** LLM summarizer function. If not provided, uses heuristic-only summarization. */
  summarizer?: (content: string, instruction: string) => Promise<string>
}

const DEFAULT_CONFIG: SmartCompactionConfig = {
  outputCharBudget: 80_000,
  preserveRecentCount: 8,
  minMessagesForCompaction: 12,
}

/* ------------------------------------------------------------------ */
/*  Smart Compaction Engine                                             */
/* ------------------------------------------------------------------ */

export class SmartCompactionEngine {
  private config: SmartCompactionConfig
  private logger?: ILogger

  constructor(config: Partial<SmartCompactionConfig> = {}, logger?: ILogger) {
    this.config = { ...DEFAULT_CONFIG, ...config }
    this.logger = logger
  }

  // HOW: Strip bold-header reasoning patterns and <think> blocks that some
  // models embed in response text. Applied to LLM output and stored memories.
  // Matches patterns like "**Analyzing the Request**" — bold headers that
  // appear as reasoning step titles in model output.
  static stripThinkingArtifacts(text: string): string {
    return text
      // WHY: Models like Qwen emit reasoning as bold headers (**Verb Phrase**)
      // in response text. These are standalone bold lines 10-80 chars. We use
      // a broad match because memory entries contain these from past sessions.
      // Minimum 10 chars avoids stripping short inline emphasis like **Note:**.
      .replace(/\*\*[A-Z][^*\n]{8,80}\*\*:?\s*\n*/g, '')
      .replace(/<think>[\s\S]*?<\/think>\s*/gi, '')
  }

  /**
   * Run smart compaction on a conversation.
   *
   * @param messages - The full conversation history
   * @param context - Optional enrichment context (memory, cognitive signals)
   * @returns Structured compaction result
   */
  async compact(
    messages: CompactionMessage[],
    context?: {
      memoryContext?: string
      cognitiveContext?: string
      lastUserQuery?: string
    },
  ): Promise<SmartCompactionResult> {
    const startTime = Date.now()

    // Bail early if not enough messages
    if (messages.length < this.config.minMessagesForCompaction) {
      return {
        summary: this.buildPassthroughSummary(messages),
        keptVerbatim: messages.length,
        summarized: 0,
        pruned: 0,
        strategy: 'conservative',
        durationMs: Date.now() - startTime,
      }
    }

    // Step 1: Score every message
    const scored = this.scoreMessages(messages)

    // Step 2: Determine strategy based on conversation pressure
    const strategy = this.selectStrategy(messages.length, scored)

    // Step 3: Partition messages into zones
    const recentCount = this.config.preserveRecentCount
    const recentMessages = scored.slice(-recentCount)
    const olderMessages = scored.slice(0, -recentCount)

    // Step 4: Cluster older messages by topic
    const clusters = this.clusterMessages(olderMessages)

    // Step 5: Process clusters based on strategy
    const sections: string[] = []
    let keptVerbatim = recentCount
    let summarized = 0
    let pruned = 0

    // Header
    sections.push('## Compaction Summary\n')
    sections.push(`Strategy: ${strategy} | ${messages.length} messages processed | ${new Date().toISOString()}\n`)

    // Add CassiCore context enrichment (strip thinking artifacts from stored content)
    if (context?.memoryContext) {
      sections.push(`\n${SmartCompactionEngine.stripThinkingArtifacts(context.memoryContext)}\n`)
    }
    if (context?.cognitiveContext) {
      sections.push(`\n### Cognitive Signals\n${SmartCompactionEngine.stripThinkingArtifacts(context.cognitiveContext)}\n`)
    }

    // Process clusters
    sections.push('\n## Session History\n')

    for (const cluster of clusters) {
      if (cluster.dominantImportance === 'high') {
        // Keep high-importance clusters verbatim
        const verbatimSection = this.renderClusterVerbatim(cluster)
        sections.push(verbatimSection)
        keptVerbatim += cluster.messages.length
      } else if (cluster.dominantImportance === 'medium') {
        // Summarize medium-importance clusters
        const summarySection = await this.summarizeCluster(cluster, strategy)
        sections.push(summarySection)
        summarized += cluster.messages.length
      } else {
        // Prune low-importance clusters (keep only a one-liner)
        const pruneSection = this.renderClusterPruned(cluster)
        sections.push(pruneSection)
        pruned += cluster.messages.length
      }
    }

    // Always include recent messages section
    sections.push('\n## Recent Conversation (preserved verbatim)\n')
    sections.push('The following messages are the most recent and represent the active working state.\n\n')
    for (const msg of recentMessages) {
      sections.push(this.renderMessageVerbatim(msg))
    }

    // Build goal/instructions/decisions from high-importance messages
    const structuredSections = this.extractStructuredSections(scored, context)
    const structuredText = this.renderStructuredSections(structuredSections)

    // Assemble final output
    let fullSummary = structuredText + '\n\n---\n\n' + sections.join('\n')

    // Trim to budget
    if (fullSummary.length > this.config.outputCharBudget) {
      fullSummary = this.trimToBudget(fullSummary, this.config.outputCharBudget)
    }

    return {
      summary: fullSummary,
      keptVerbatim,
      summarized,
      pruned,
      strategy,
      durationMs: Date.now() - startTime,
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Message Scoring                                                     */
  /* ------------------------------------------------------------------ */

  scoreMessages(messages: CompactionMessage[]): ScoredMessage[] {
    const totalMessages = messages.length
    return messages.map((message, index) => {
      const textContent = this.extractText(message)
      const { score, reason } = this.computeScore(message, textContent, index, totalMessages)
      const importance = this.classifyImportance(score)
      return { index, message, importance, score, reason, textContent }
    })
  }

  private computeScore(
    message: CompactionMessage,
    text: string,
    index: number,
    total: number,
  ): { score: number; reason: string } {
    const factors: { name: string; value: number; weight: number }[] = []

    // Recency: more recent = higher score (exponential decay)
    const recency = Math.pow((index + 1) / total, 0.5)
    factors.push({ name: 'recency', value: recency, weight: 0.15 })

    // Role: user messages carry intent
    const isUser = message.role === 'user'
    factors.push({ name: 'role', value: isUser ? 0.8 : 0.4, weight: 0.10 })

    // Length: longer messages tend to have more substance
    const lengthScore = Math.min(1, text.length / 2000)
    factors.push({ name: 'length', value: lengthScore, weight: 0.05 })

    // Error signals: errors are always important
    const hasError = /\b(error|exception|failed|failure|crash|traceback|ENOENT|EPERM|TypeError|ReferenceError)\b/i.test(text)
    if (hasError) {
      factors.push({ name: 'error', value: 1.0, weight: 0.20 })
    }

    // Modifying tool calls: edits, writes, creates are important
    const hasModifyingTool = /\b(edit|write|create|delete|commit|push|merge|rename|move)\b/i.test(text)
    if (hasModifyingTool) {
      factors.push({ name: 'modifying-tool', value: 0.9, weight: 0.15 })
    }

    // Decision signals: explicit decisions should be preserved
    const hasDecision = /\b(decided|decision|chose|approach|architecture|design|plan)\b/i.test(text)
    if (hasDecision) {
      factors.push({ name: 'decision', value: 0.85, weight: 0.10 })
    }

    // File references: messages referencing specific files are contextually important
    const fileRefs = this.extractFileRefs(text)
    if (fileRefs.length > 0) {
      factors.push({ name: 'file-refs', value: Math.min(1, fileRefs.length / 3), weight: 0.10 })
    }

    // Code content: messages with actual code snippets
    const hasCode = /```[\s\S]{50,}```/.test(text) || /\b(function|class|const|let|import|export)\b.*[{(]/.test(text)
    if (hasCode) {
      factors.push({ name: 'code', value: 0.7, weight: 0.08 })
    }

    // Tool output verbosity penalty: very long tool outputs without substance
    const isToolOutput = message.role === 'assistant' && text.length > 5000 && !hasError && !hasDecision
    if (isToolOutput) {
      factors.push({ name: 'verbose-tool-output', value: 0.2, weight: 0.15 })
    }

    // Compute weighted score
    const totalWeight = factors.reduce((sum, f) => sum + f.weight, 0)
    const score = totalWeight > 0
      ? factors.reduce((sum, f) => sum + f.value * f.weight, 0) / totalWeight
      : 0.5

    // Find the dominant factor for the reason
    const topFactor = factors.sort((a, b) => (b.value * b.weight) - (a.value * a.weight))[0]
    const reason = topFactor?.name ?? 'baseline'

    return { score: Math.min(1, Math.max(0, score)), reason }
  }

  private classifyImportance(score: number): ImportanceLevel {
    if (score >= 0.65) return 'high'
    if (score >= 0.40) return 'medium'
    return 'low'
  }

  /* ------------------------------------------------------------------ */
  /*  Clustering                                                         */
  /* ------------------------------------------------------------------ */

  clusterMessages(messages: ScoredMessage[]): MessageCluster[] {
    if (messages.length === 0) return []

    const clusters: MessageCluster[] = []
    let currentCluster: ScoredMessage[] = [messages[0]]
    let clusterIndex = 0

    for (let i = 1; i < messages.length; i++) {
      const prev = messages[i - 1]
      const curr = messages[i]

      // Heuristic clustering: group consecutive messages that share context
      const sameTopic = this.sharesContext(prev, curr)
      const sameImportance = prev.importance === curr.importance

      if (sameTopic || (sameImportance && i - currentCluster[0].index < 6)) {
        currentCluster.push(curr)
      } else {
        clusters.push(this.buildCluster(currentCluster, clusterIndex++))
        currentCluster = [curr]
      }
    }

    if (currentCluster.length > 0) {
      clusters.push(this.buildCluster(currentCluster, clusterIndex))
    }

    return clusters
  }

  private sharesContext(a: ScoredMessage, b: ScoredMessage): boolean {
    // Check for shared file references
    const aFiles = this.extractFileRefs(a.textContent)
    const bFiles = this.extractFileRefs(b.textContent)
    if (aFiles.length > 0 && bFiles.length > 0) {
      const shared = aFiles.filter(f => bFiles.includes(f))
      if (shared.length > 0) return true
    }

    // Check for shared tool names
    const aTools = this.extractToolNames(a.textContent)
    const bTools = this.extractToolNames(b.textContent)
    if (aTools.length > 0 && bTools.length > 0) {
      const shared = aTools.filter(t => bTools.includes(t))
      if (shared.length > 0) return true
    }

    return false
  }

  private buildCluster(messages: ScoredMessage[], index: number): MessageCluster {
    const avgScore = messages.reduce((sum, m) => sum + m.score, 0) / messages.length

    // Dominant importance: use the highest importance level present
    const hasHigh = messages.some(m => m.importance === 'high')
    const hasMedium = messages.some(m => m.importance === 'medium')
    const dominantImportance: ImportanceLevel = hasHigh ? 'high' : hasMedium ? 'medium' : 'low'

    // Infer topic from file refs and tool names
    const files = new Set<string>()
    const tools = new Set<string>()
    for (const m of messages) {
      this.extractFileRefs(m.textContent).forEach(f => files.add(f))
      this.extractToolNames(m.textContent).forEach(t => tools.add(t))
    }

    let topic = ''
    if (files.size > 0) topic = `Files: ${[...files].slice(0, 3).join(', ')}`
    else if (tools.size > 0) topic = `Tools: ${[...tools].slice(0, 3).join(', ')}`
    else topic = `${messages.length} messages (${messages[0].message.role})`

    return {
      id: `cluster-${index}`,
      messages,
      avgScore,
      dominantImportance,
      topic,
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Rendering                                                          */
  /* ------------------------------------------------------------------ */

  private renderClusterVerbatim(cluster: MessageCluster): string {
    const lines: string[] = [`### ${cluster.topic} [kept verbatim]\n`]
    for (const msg of cluster.messages) {
      lines.push(this.renderMessageVerbatim(msg))
    }
    return lines.join('\n')
  }

  private renderMessageVerbatim(msg: ScoredMessage): string {
    const role = msg.message.role.toUpperCase()
    let content = msg.textContent
    // Truncate individual messages that are excessively long
    if (content.length > 6000) {
      const half = 2500
      content = content.slice(0, half) + '\n[... truncated ...]\n' + content.slice(-half)
    }
    return `[${role}]: ${content}\n---\n`
  }

  private async summarizeCluster(
    cluster: MessageCluster,
    strategy: CompactionStrategy,
  ): Promise<string> {
    const combined = cluster.messages
      .map(m => `[${m.message.role.toUpperCase()}]: ${m.textContent.slice(0, 800)}`)
      .join('\n\n')

    if (this.config.summarizer) {
      try {
        const instruction = strategy === 'aggressive' || strategy === 'critical'
          ? 'Summarize the following conversation segment in 2-3 sentences. Focus on decisions, outcomes, and file changes. Be extremely concise.'
          : 'Summarize the following conversation segment. Preserve key decisions, error messages, file paths, and implementation details. Be thorough but concise.'

        const summary = await this.config.summarizer(combined, instruction)
        return `### ${cluster.topic} [summarized from ${cluster.messages.length} messages]\n${summary}\n`
      } catch (err) {
        this.logger?.warn('SmartCompaction: LLM summary failed, falling back to heuristic', { error: String(err) })
      }
    }

    // Heuristic fallback
    return this.heuristicSummarize(cluster)
  }

  private heuristicSummarize(cluster: MessageCluster): string {
    const lines: string[] = [`### ${cluster.topic} [heuristic summary — ${cluster.messages.length} messages]\n`]

    // Keep first sentence of each user message and key assistant lines
    for (const msg of cluster.messages) {
      if (msg.message.role === 'user') {
        const firstSentence = msg.textContent.split(/[.!?\n]/)[0]?.trim()
        if (firstSentence && firstSentence.length > 15) {
          lines.push(`- User: ${firstSentence.slice(0, 200)}`)
        }
      } else if (msg.importance === 'high' || msg.importance === 'medium') {
        const firstSentence = msg.textContent.split(/[.!?\n]/)[0]?.trim()
        if (firstSentence && firstSentence.length > 15) {
          lines.push(`- Assistant: ${firstSentence.slice(0, 200)}`)
        }
      }
    }

    if (lines.length === 1) {
      lines.push(`- ${cluster.messages.length} routine messages compacted`)
    }

    return lines.join('\n') + '\n'
  }

  private renderClusterPruned(cluster: MessageCluster): string {
    const files = new Set<string>()
    const tools = new Set<string>()
    for (const m of cluster.messages) {
      this.extractFileRefs(m.textContent).forEach(f => files.add(f))
      this.extractToolNames(m.textContent).forEach(t => tools.add(t))
    }

    const extras: string[] = []
    if (files.size > 0) extras.push(`files: ${[...files].slice(0, 5).join(', ')}`)
    if (tools.size > 0) extras.push(`tools: ${[...tools].slice(0, 5).join(', ')}`)
    const extrasStr = extras.length > 0 ? ` (${extras.join('; ')})` : ''

    return `[${cluster.messages.length} low-importance messages pruned${extrasStr}]\n`
  }

  /* ------------------------------------------------------------------ */
  /*  Structured Section Extraction                                      */
  /* ------------------------------------------------------------------ */

  private extractStructuredSections(
    scored: ScoredMessage[],
    context?: { lastUserQuery?: string },
  ): {
    goal: string
    instructions: string[]
    discoveries: string[]
    accomplished: string[]
    decisions: string[]
    relevantFiles: string[]
  } {
    const allFiles = new Set<string>()
    const decisions: string[] = []
    const discoveries: string[] = []
    const accomplished: string[] = []
    const instructions: string[] = []

    // Extract goal from the first or most recent user messages
    let goal = context?.lastUserQuery ?? ''
    if (!goal) {
      const firstUser = scored.find(m => m.message.role === 'user')
      goal = firstUser ? firstUser.textContent.slice(0, 300) : 'Unknown'
    }

    for (const msg of scored) {
      // Collect file refs
      this.extractFileRefs(msg.textContent).forEach(f => allFiles.add(f))

      // Extract decisions from high-importance messages
      if (msg.importance === 'high') {
        const lower = msg.textContent.toLowerCase()
        if (lower.includes('decided') || lower.includes('decision') || lower.includes('chose')) {
          const sentence = this.extractRelevantSentence(msg.textContent, /decid|chose|decision/i)
          if (sentence) decisions.push(sentence)
        }
        if (lower.includes('discovered') || lower.includes('found') || lower.includes('learned')) {
          const sentence = this.extractRelevantSentence(msg.textContent, /discover|found|learned/i)
          if (sentence) discoveries.push(sentence)
        }
        if (lower.includes('completed') || lower.includes('implemented') || lower.includes('fixed')) {
          const sentence = this.extractRelevantSentence(msg.textContent, /completed|implemented|fixed/i)
          if (sentence) accomplished.push(sentence)
        }
      }

      // Extract instructions from user messages
      if (msg.message.role === 'user' && msg.importance !== 'low') {
        const imperative = this.extractImperative(msg.textContent)
        if (imperative) instructions.push(imperative)
      }
    }

    return {
      goal: goal.slice(0, 500),
      instructions: instructions.slice(0, 10),
      discoveries: discoveries.slice(0, 10),
      accomplished: accomplished.slice(0, 10),
      decisions: decisions.slice(0, 10),
      relevantFiles: [...allFiles].slice(0, 20),
    }
  }

  private renderStructuredSections(sections: ReturnType<SmartCompactionEngine['extractStructuredSections']>): string {
    const lines: string[] = []

    lines.push('## Goal')
    lines.push(sections.goal || 'Not determined')
    lines.push('')

    if (sections.instructions.length > 0) {
      lines.push('## Instructions')
      for (const i of sections.instructions) lines.push(`- ${i}`)
      lines.push('')
    }

    if (sections.discoveries.length > 0) {
      lines.push('## Discoveries')
      for (const d of sections.discoveries) lines.push(`- ${d}`)
      lines.push('')
    }

    if (sections.accomplished.length > 0) {
      lines.push('## Accomplished')
      for (const a of sections.accomplished) lines.push(`- ${a}`)
      lines.push('')
    }

    if (sections.decisions.length > 0) {
      lines.push('## Decisions Made')
      for (const d of sections.decisions) lines.push(`- ${d}`)
      lines.push('')
    }

    if (sections.relevantFiles.length > 0) {
      lines.push('## Relevant Files / Directories')
      for (const f of sections.relevantFiles) lines.push(`- ${f}`)
      lines.push('')
    }

    return lines.join('\n')
  }

  /* ------------------------------------------------------------------ */
  /*  Strategy Selection                                                  */
  /* ------------------------------------------------------------------ */

  private selectStrategy(messageCount: number, scored: ScoredMessage[]): CompactionStrategy {
    const highCount = scored.filter(m => m.importance === 'high').length
    const highRatio = highCount / scored.length

    // More messages = more aggressive compaction needed
    if (messageCount > 200) return 'critical'
    if (messageCount > 100) return 'aggressive'
    if (messageCount > 50 || highRatio < 0.2) return 'balanced'
    return 'conservative'
  }

  /* ------------------------------------------------------------------ */
  /*  Helpers                                                            */
  /* ------------------------------------------------------------------ */

  private extractText(message: CompactionMessage): string {
    if (typeof message.content === 'string') return message.content
    if (!Array.isArray(message.content)) return ''
    return message.content
      .filter(p => p.type === 'text')
      .map(p => p.text ?? '')
      .join('\n')
  }

  private extractFileRefs(text: string): string[] {
    const files = new Set<string>()
    for (const token of text.split(/\s+/)) {
      const candidate = token.replace(/^[,.:;)"'`]+|[,.:;)"'`]+$/g, '')
      if (candidate.includes('/') && this.hasCodeExtension(candidate)) {
        files.add(candidate)
      }
    }
    return [...files].slice(0, 10)
  }

  private extractToolNames(text: string): string[] {
    const tools = new Set<string>()
    const toolPattern = /\b(cassi_\w+|serena_\w+|gitnexus_\w+|read|write|edit|bash|grep|glob)\b/gi
    let match
    while ((match = toolPattern.exec(text)) !== null) {
      tools.add(match[1].toLowerCase())
    }
    return [...tools]
  }

  private extractRelevantSentence(text: string, pattern: RegExp): string | null {
    const sentences = text.split(/[.!?\n]+/)
    for (const sentence of sentences) {
      if (pattern.test(sentence) && sentence.trim().length > 20) {
        return sentence.trim().slice(0, 200)
      }
    }
    return null
  }

  private extractImperative(text: string): string | null {
    // Extract the first actionable sentence from a user message
    const sentences = text.split(/[.!?\n]+/)
    for (const sentence of sentences) {
      const trimmed = sentence.trim()
      if (trimmed.length > 15 && trimmed.length < 300) {
        return trimmed
      }
    }
    return null
  }

  private hasCodeExtension(candidate: string): boolean {
    const ext = candidate.split('.').pop()?.toLowerCase()
    return ext ? CODE_EXTENSIONS.has(ext) : false
  }

  private buildPassthroughSummary(messages: CompactionMessage[]): string {
    // For short conversations, just render everything
    const lines: string[] = ['## Full Conversation (below compaction threshold)\n']
    for (const msg of messages) {
      const role = msg.role.toUpperCase()
      const text = this.extractText(msg)
      lines.push(`[${role}]: ${text}\n---\n`)
    }
    return lines.join('\n')
  }

  private trimToBudget(text: string, budget: number): string {
    if (text.length <= budget) return text

    // Find the "Recent Conversation" section and protect it
    const recentIdx = text.indexOf('## Recent Conversation')
    if (recentIdx > 0 && recentIdx < budget) {
      // Keep the structured sections + as much history as fits + all recent messages
      const recentSection = text.slice(recentIdx)
      const historyBudget = budget - recentSection.length - 200
      if (historyBudget > 1000) {
        const historySection = text.slice(0, historyBudget)
        return historySection + '\n\n[... history truncated to fit budget ...]\n\n' + recentSection
      }
    }

    // Fallback: simple truncation from the middle
    const half = Math.floor(budget / 2) - 100
    return text.slice(0, half) + '\n\n[... truncated ...]\n\n' + text.slice(-half)
  }
}

const CODE_EXTENSIONS = new Set([
  'ts', 'tsx', 'js', 'jsx', 'json', 'md', 'rs', 'py',
  'yaml', 'yml', 'toml', 'sh', 'css', 'html', 'sql',
  'go', 'java', 'cpp', 'c', 'h', 'vue', 'svelte',
])
