/**
 * Drop receipts: a single human-readable line describing what curation removed,
 * plus per-domain anomaly flags.
 *
 * The receipt rides curate's `meta` field and is injected by the proxy as a
 * synthetic system block on the next turn. This makes silent message removal
 * visible from inside the model — closing the curation feedback loop that the
 * cassi-context-awareness spec calls out.
 */

import type { ScoredMessage, ThalamusAnnotation, RerankerCompressionCache } from './types.js'
import { isWriteTool, isReadTool, shortenPath } from './classifier.js'
import { hasQuestionResult, buildToolUseMapFromMessages } from '../../pipeline/turn/overflow.js'

export interface TopicCluster {
  /** Short label derived from content keywords */
  topic: string
  /** Number of dropped messages in this cluster */
  count: number
}

export interface ClosestMiss {
  /** Index of the highest-scoring dropped message */
  msgIndex: number
  /** Slot/role of the message */
  slot: string
  /** Composite luminance score (0-1) */
  luminance: number
  /** Ignition threshold that this message failed to meet */
  threshold: number
  /** Per-axis breakdown */
  axes: Record<string, number>
  /** First 80 chars of content for identification */
  snippet: string
}

export interface BudgetInfo {
  /** Total char budget for this curation pass */
  budget: number
  /** Chars consumed by included messages */
  used: number
  /** Chars freed by dropping */
  freed: number
  /** Utilization ratio (used / budget) */
  utilization: number
}

export interface ProtectionCounts {
  /** Pinned messages (explicit pin, askuserquestion auto-pin, loop-detection, thought-command) */
  pin: number
  /** Last reads of files not yet written to since */
  liveRead: number
  /** System-slot messages */
  system: number
  /** Last N messages held by the protected window */
  recentWindow: number
}

export interface ProtectionSummary {
  /** Total protected (sum of categories) */
  total: number
  /** Per-category counts */
  counts: ProtectionCounts
  /** First live-read file path, when one exists, for the one-line summary */
  firstLiveReadPath?: string
  /**
   * Single-line human summary, e.g.
   * "14 (4 pinned · 8 recent-window · 1 live-read drop-receipt.ts · 1 system)"
   */
  summary: string
}

export interface DropReceipt {
  /** Total messages dropped this curation pass */
  dropped: number
  /** Messages dropped per slot (user, assistant, tool_result, etc.) */
  bySlot: Record<string, number>
  /** Total chars freed (compressed-content basis) */
  charsFreed: number
  /** Anomaly flags — present only when something noteworthy happened */
  anomalies: string[]
  /**
   * Single-line human summary suitable for embedding in a system block.
   * Format: "thalamus dropped N message(s) (M chars): A user, B tool_result"
   */
  summary: string
  /** ISO 8601 UTC timestamp the receipt was built */
  ts: string
  /**
   * Tool-chain metadata from dropped messages — tool names, file paths touched,
   * errors encountered. Used by the proxy to enrich the system-block injection
   * so the model knows what work was removed and can avoid repeating it.
   */
  toolChainSummary?: ToolChainSummary
  /** Topic clusters extracted from dropped content (top 5 by count) */
  topics: TopicCluster[]
  /** The highest-scoring message that still got dropped */
  closestMiss?: ClosestMiss
  /** Budget utilization for this curation pass */
  budget?: BudgetInfo
  /**
   * Protection summary — what's force-included and why. Always present.
   * Fires even when nothing was dropped, because Cassi needs continuous
   * visibility into which messages will survive the next curation pass.
   */
  protected: ProtectionSummary
  /** Reranker compression metadata — shows which tool results were compressed and by how much */
  rerankerSummary?: string
}

/**
 * Structured summary of tool-chain metadata from dropped messages.
 * Extracted heuristically — no LLM call needed.
 */
export interface ToolChainSummary {
  /** Unique tool names that were called in the dropped segment */
  toolsUsed: string[]
  /** File paths read by dropped tool calls */
  filesRead: string[]
  /** File paths written/edited by dropped tool calls */
  filesWritten: string[]
  /** Error snippets from dropped tool results */
  errors: string[]
  /** Count of tool_call/tool_result pairs dropped */
  toolPairCount: number
}

export interface BuildReceiptInput {
  /** Pre-curation messages (after annotation) */
  before: any[]
  /** Score records — used to find pinned overrides and dropped indices */
  scored: ScoredMessage[]
  /** Indices that survived ignition (selected for inclusion) */
  includedIndices: Set<number>
  /** Indices marked protected (recent tail) — never count as dropped */
  protectedIndices: Set<number>
  /** Char budget the threshold pass was working against */
  charBudget: number
  /** Chars actually consumed by included messages */
  charsUsed: number
  /** Ignition threshold — required for closestMiss gap calculation */
  threshold: number
  /** Reranker compression cache for showing compression metadata */
  rerankerCache?: RerankerCompressionCache
}

function summarizeProtections(messages: any[], includedIndices: Set<number>): ProtectionSummary {
  const counts: ProtectionCounts = { pin: 0, liveRead: 0, system: 0, recentWindow: 0 }
  let firstLiveReadPath: string | undefined
  for (const idx of includedIndices) {
    const annotation: ThalamusAnnotation | undefined = messages[idx]?._thalamus
    const tag = annotation?.protectedBy
    if (!tag) continue
    if (tag === 'pin') counts.pin++
    else if (tag === 'live-read') {
      counts.liveRead++
      if (!firstLiveReadPath && annotation?.protectedReason) {
        firstLiveReadPath = shortenPath(annotation.protectedReason)
      }
    } else if (tag === 'system') counts.system++
    else if (tag === 'recent-window') counts.recentWindow++
  }
  const total = counts.pin + counts.liveRead + counts.system + counts.recentWindow
  const parts: string[] = []
  if (counts.pin > 0) parts.push(`${counts.pin} pinned`)
  if (counts.recentWindow > 0) parts.push(`${counts.recentWindow} recent-window`)
  if (counts.liveRead > 0) {
    parts.push(firstLiveReadPath
      ? `${counts.liveRead} live-read ${firstLiveReadPath}${counts.liveRead > 1 ? ' …' : ''}`
      : `${counts.liveRead} live-read`)
  }
  if (counts.system > 0) parts.push(`${counts.system} system`)
  const summary = parts.length > 0 ? `${total} (${parts.join(' · ')})` : `${total}`
  return { total, counts, firstLiveReadPath, summary }
}

/** Build a receipt summarizing drops and protection state for this curation pass. */
export function buildDropReceipt(input: BuildReceiptInput): DropReceipt {
  const { before, scored, includedIndices, protectedIndices, charBudget, charsUsed } = input
  const droppedIndices: number[] = []
  const droppedScores = new Map<number, ScoredMessage>()
  for (const s of scored) {
    if (includedIndices.has(s.messageIndex)) continue
    if (protectedIndices.has(s.messageIndex)) continue
    droppedIndices.push(s.messageIndex)
    droppedScores.set(s.messageIndex, s)
  }

  const protectedSummary = summarizeProtections(before, includedIndices)

  if (droppedIndices.length === 0) {
    const rerankerSummary = buildRerankerSummary(input.rerankerCache)
    return {
      dropped: 0,
      bySlot: {},
      charsFreed: 0,
      anomalies: [],
      summary: '',
      ts: new Date().toISOString(),
      topics: [],
      protected: protectedSummary,
      rerankerSummary,
    }
  }

  const bySlot: Record<string, number> = {}
  let charsFreed = 0
  const anomalies: string[] = []

  const toolUseMap = buildToolUseMapFromMessages(before)

  for (const idx of droppedIndices) {
    const msg = before[idx]
    const annotation: ThalamusAnnotation | undefined = msg?._thalamus
    const slot = annotation?.slot ?? msg?.role ?? 'unknown'
    bySlot[slot] = (bySlot[slot] ?? 0) + 1

    const content = msg?._thalamus?.compressedContent ?? extractContent(msg)
    charsFreed += typeof content === 'string' ? content.length : 0

    if (hasQuestionResult(msg, { toolUseMap })) {
      anomalies.push(`question-answer dropped (msg index ${idx})`)
    }
    if (annotation?.pinned) {
      anomalies.push(`pinned message dropped (msg index ${idx}, reason: ${annotation.pinReason ?? 'unknown'})`)
    }
  }

  const lastUserDropped = findLastUserDropped(before, droppedIndices)
  if (lastUserDropped >= 0) {
    const ageRank = before.length - lastUserDropped
    if (ageRank <= 6) {
      anomalies.push(`recent user message dropped (${ageRank} turns ago)`)
    }
  }

  const slotParts = Object.entries(bySlot)
    .sort((a, b) => b[1] - a[1])
    .map(([slot, n]) => `${n} ${slot}`)
    .join(', ')

  const summary = `thalamus dropped ${droppedIndices.length} message(s) (${charsFreed} chars): ${slotParts}`

  // Extract tool-chain metadata from dropped messages
  const toolChainSummary = buildToolChainSummary(before, droppedIndices)
  const topics = extractTopics(before, droppedIndices)
  const closestMiss = findClosestMiss(before, droppedScores, input.threshold)

  let budget: BudgetInfo | undefined
  if (charBudget > 0) {
    budget = {
      budget: charBudget,
      used: charsUsed,
      freed: charsFreed,
      utilization: Math.round((charsUsed / charBudget) * 100) / 100,
    }
  }

  const rerankerSummary = buildRerankerSummary(input.rerankerCache)

  return {
    dropped: droppedIndices.length,
    bySlot,
    charsFreed,
    anomalies,
    summary,
    ts: new Date().toISOString(),
    toolChainSummary,
    topics,
    closestMiss,
    budget,
    protected: protectedSummary,
    rerankerSummary,
  }
}

/**
 * Extract tool-chain metadata from dropped messages. Scans for tool names,
 * file paths, and errors so the model can see what work was removed and
 * avoid re-executing the same tool calls.
 */
function buildToolChainSummary(messages: any[], droppedIndices: number[]): ToolChainSummary | undefined {
  const toolsUsed = new Set<string>()
  const filesReadSet = new Set<string>()
  const filesWrittenSet = new Set<string>()
  const errors: string[] = []
  let toolPairCount = 0

  const droppedSet = new Set(droppedIndices)

  for (const idx of droppedIndices) {
    const msg = messages[idx]
    if (!msg) continue
    const annotation: ThalamusAnnotation | undefined = msg?._thalamus
    const slot = annotation?.slot

    // Count tool pairs
    if (slot === 'tool_call' || slot === 'tool_result') {
      toolPairCount++
    }

    // Extract from tool_use blocks
    if (Array.isArray(msg.content)) {
      for (const block of msg.content) {
        if (block?.type === 'tool_use') {
          const toolName = block.name ?? ''
          if (toolName) toolsUsed.add(toolName)

          const input = block.input
          if (input && typeof input === 'object') {
            const filePath = (input as any).filePath ?? (input as any).path ?? (input as any).file_path ?? (input as any).relative_path ?? ''
            if (filePath && typeof filePath === 'string') {
              if (isWriteTool(toolName)) {
                filesWrittenSet.add(shortenPath(filePath))
              } else if (isReadTool(toolName)) {
                filesReadSet.add(shortenPath(filePath))
              }
            }
          }
        }

        // Extract from tool_result blocks
        if (block?.type === 'tool_result') {
          if (block.is_error) {
            const text = typeof block.content === 'string' ? block.content : ''
            const firstLine = text.split('\n')[0]?.slice(0, 80) ?? ''
            if (firstLine && errors.length < 3) errors.push(firstLine)
          }
        }
      }
    }
  }

  // Deduplicated tool pair count (each pair = tool_call + tool_result)
  const logicalToolCalls = Math.ceil(toolPairCount / 2)

  const tools = Array.from(toolsUsed)
  const filesRead = Array.from(filesReadSet)
  const filesWritten = Array.from(filesWrittenSet)

  // Only return if we found meaningful tool metadata
  if (tools.length === 0 && filesRead.length === 0 && filesWritten.length === 0) {
    return undefined
  }

  return {
    toolsUsed: tools.slice(0, 8),
    filesRead: filesRead.slice(0, 6),
    filesWritten: filesWritten.slice(0, 4),
    errors: errors.slice(0, 3),
    toolPairCount: logicalToolCalls,
  }
}

/** Render the receipt as a system-block payload for proxy injection. */
export function renderDropReceiptBlock(receipt: DropReceipt): string {
  const lines = [receipt.summary]

  // Include tool-chain metadata so the model knows what was removed
  const tcs = receipt.toolChainSummary
  if (tcs && (tcs.toolsUsed.length > 0 || tcs.filesRead.length > 0 || tcs.filesWritten.length > 0)) {
    const parts: string[] = []
    if (tcs.toolPairCount > 0) parts.push(`${tcs.toolPairCount} tool call${tcs.toolPairCount > 1 ? 's' : ''}`)
    if (tcs.filesRead.length > 0) parts.push(`read: ${tcs.filesRead.join(', ')}`)
    if (tcs.filesWritten.length > 0) parts.push(`wrote: ${tcs.filesWritten.join(', ')}`)
    if (tcs.errors.length > 0) parts.push(`errors: ${tcs.errors.join('; ')}`)
    if (parts.length > 0) {
      lines.push(`work dropped: ${parts.join(' · ')}`)
    }
  }

  if (receipt.anomalies.length > 0) {
    lines.push('')
    lines.push('anomalies:')
    for (const a of receipt.anomalies) lines.push(`  - ${a}`)
  }
  lines.push('')
  lines.push('to recover: call cassi_context({action: "audit"}) to see drops, or cassi_context({action: "recall", n: 5}) to re-include the last 5 dropped messages.')
  return lines.join('\n')
}

function extractContent(msg: any): string {
  if (!msg) return ''
  if (typeof msg.content === 'string') return msg.content
  if (Array.isArray(msg.content)) {
    return msg.content
      .map((b: any) => {
        if (typeof b?.text === 'string') return b.text
        if (typeof b?.content === 'string') return b.content
        return ''
      })
      .join('\n')
  }
  return ''
}

function findLastUserDropped(messages: any[], droppedIndices: number[]): number {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (!droppedIndices.includes(i)) continue
    if (messages[i]?.role === 'user') return i
  }
  return -1
}

function extractTopics(messages: any[], droppedIndices: number[]): TopicCluster[] {
  const topicCounts = new Map<string, number>()
  for (const idx of droppedIndices) {
    const msg = messages[idx]
    const content = msg?._thalamus?.compressedContent ?? extractContent(msg)
    if (!content || typeof content !== 'string') continue

    const label = deriveTopicLabel(msg, content)
    topicCounts.set(label, (topicCounts.get(label) ?? 0) + 1)
  }

  return Array.from(topicCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([topic, count]) => ({ topic, count }))
}

function deriveTopicLabel(msg: any, content: string): string {
  const role = msg?.role ?? 'unknown'
  const annotation: ThalamusAnnotation | undefined = msg?._thalamus

  if (role === 'tool_result' || role === 'tool_call') {
    const toolName = annotation?.tool?.name ?? extractToolName(content)
    if (toolName) return toolName
  }

  if (role === 'assistant') {
    if (content.includes('★ Insight')) return 'insight-blocks'
    if (content.includes('AskUserQuestion')) return 'qa-responses'
    return 'assistant-text'
  }

  if (role === 'user') return 'user-directives'

  const truncated = content.slice(0, 60).replace(/\n/g, ' ').trim()
  return truncated.length < content.length ? truncated + '…' : truncated
}

function extractToolName(content: string): string {
  const match = content.match(/"name"\s*:\s*"([^"]+)"/)
  return match?.[1] ?? ''
}

function findClosestMiss(
  messages: any[],
  droppedScores: Map<number, ScoredMessage>,
  threshold: number,
): ClosestMiss | undefined {
  let best: { idx: number; score: ScoredMessage } | undefined

  for (const [idx, score] of droppedScores) {
    if (!best || score.luminance.composite > best.score.luminance.composite) {
      best = { idx, score }
    }
  }

  if (!best) return undefined

  const msg = messages[best.idx]
  const slot = msg?._thalamus?.slot ?? msg?.role ?? 'unknown'
  const content = extractContent(msg)
  const preview = content.length > 80 ? content.slice(0, 80).replace(/\n/g, ' ').trim() + '…' : content
  const lum = best.score.luminance

  return {
    msgIndex: best.idx,
    slot,
    luminance: lum.composite,
    threshold,
    axes: {
      novelty: lum.novelty,
      urgency: lum.urgency,
      relevance: lum.relevance,
      sourceCredibility: lum.sourceCredibility,
      strategicImportance: lum.strategicImportance,
    },
    snippet: preview,
  }
}

function buildRerankerSummary(cache: RerankerCompressionCache | undefined): string | undefined {
  if (!cache || cache.entries.size === 0) return undefined
  const lines: string[] = []
  for (const [toolUseId, entry] of cache.entries) {
    const ratio = `${Math.round(entry.originalChars / 1000)}K → ${Math.round(entry.compressedChars / 1000)}K`
    const kept = `${entry.keptChunks.length}/${entry.totalChunks}`
    lines.push(`[${toolUseId.slice(0, 12)}…] ${ratio}, ${kept} chunks`)
    if (entry.keptChunks.length > 0) {
      const top = entry.keptChunks.slice(0, 3).map(c => c.summary).filter(Boolean).join(', ')
      if (top) lines.push(`  top: ${top}`)
    }
  }
  if (lines.length === 0) return undefined
  lines.push('Use cassi_context({action: "expand", tool_use_id: "…"}) to recover full content')
  return lines.join('\n')
}
