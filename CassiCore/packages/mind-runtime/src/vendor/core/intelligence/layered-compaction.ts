/**
 * Layered Compaction Engine
 *
 * Inspired by Claude Code's multi-round compaction pattern.
 * When a session is compacted, older messages are summarized into
 * a structured system message. If compaction runs again on an
 * already-compacted session, the previous summary is preserved as
 * "Previously compacted context" while new messages become
 * "Newly compacted context".
 *
 * Key features:
 * - Extracts key files referenced in tool use blocks
 * - Infers pending work from keyword signals
 * - Preserves recent N messages verbatim
 * - Merges summaries across multiple compaction rounds
 * - Includes a direct resume instruction to prevent model recapping
 */

import type { Message } from '@cassicore/foundation'
import { CHARS_PER_TOKEN } from './shared/token-estimation.js'
import { hasQuestionResult, buildToolUseMapFromMessages } from '@cassicore/utils'

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const COMPACTION_PREAMBLE =
  'This session continues from a previous conversation that ran out of context. ' +
  'The summary below covers the earlier portion.\n\n'

const RECENT_MESSAGES_NOTE = 'Recent messages are preserved verbatim below.'

const DIRECT_RESUME_INSTRUCTION =
  'Continue the conversation from where it left off without asking the user ' +
  'any further questions. Resume directly — do not acknowledge the summary, ' +
  'do not recap what was happening, and do not preface with continuation text.'

const PREVIOUSLY_COMPACTED_HEADER = '## Previously compacted context'
const NEWLY_COMPACTED_HEADER = '## Newly compacted context'

/* ------------------------------------------------------------------ */
/*  Public types                                                       */
/* ------------------------------------------------------------------ */

export interface CompactionConfig {
  /** Number of recent messages to keep verbatim. Default 6 (3 turns). */
  preserveRecentMessages: number
  /** Estimated token threshold that triggers compaction. */
  maxEstimatedTokens: number
}

export const DEFAULT_COMPACTION_CONFIG: CompactionConfig = {
  preserveRecentMessages: 6,
  maxEstimatedTokens: 10_000,
}

export interface CompactionResult {
  /** Raw structured summary text (XML-tagged). */
  summary: string
  /** Human-readable formatted summary. */
  formattedSummary: string
  /** The compacted message array (system summary + preserved recent). */
  compactedMessages: Message[]
  /** Number of messages that were removed/summarized. */
  removedMessageCount: number
}

/* ------------------------------------------------------------------ */
/*  Token estimation                                                   */
/* ------------------------------------------------------------------ */

export function estimateMessageTokens(msg: Message): number {
  if (typeof msg.content === 'string') return Math.ceil(msg.content.length / CHARS_PER_TOKEN)
  if (!Array.isArray(msg.content)) return 10
  return msg.content.reduce((sum, block) => {
    if ('text' in block) return sum + Math.ceil(block.text.length / CHARS_PER_TOKEN)
    return sum + 50 // tool use / tool result overhead estimate
  }, 0)
}

export function estimateSessionTokens(messages: Message[]): number {
  return messages.reduce((sum, m) => sum + estimateMessageTokens(m), 0)
}

/* ------------------------------------------------------------------ */
/*  Core: should we compact?                                           */
/* ------------------------------------------------------------------ */

export function shouldCompact(messages: Message[], config: CompactionConfig): boolean {
  const start = existingSummaryPrefixLen(messages)
  const compactable = messages.slice(start)
  return (
    compactable.length > config.preserveRecentMessages &&
    estimateSessionTokens(compactable) >= config.maxEstimatedTokens
  )
}

/* ------------------------------------------------------------------ */
/*  Core: compact                                                      */
/* ------------------------------------------------------------------ */

export function compactMessages(
  messages: Message[],
  config: CompactionConfig = DEFAULT_COMPACTION_CONFIG,
): CompactionResult {
  if (!shouldCompact(messages, config)) {
    return {
      summary: '',
      formattedSummary: '',
      compactedMessages: [...messages],
      removedMessageCount: 0,
    }
  }

  // Question answers are semantically user messages and should be preserved
  const existingSummary = extractExistingCompactedSummary(messages)
  const prefixLen = existingSummary ? 1 : 0
  const keepFrom = Math.max(prefixLen, messages.length - config.preserveRecentMessages)
  const toolUseMap = buildToolUseMapFromMessages(messages)

  // Split into removable and protected messages
  // Messages with question results are protected — they're user input
  const removable: Message[] = []
  const protectedInRemoved: Message[] = []
  for (let i = prefixLen; i < keepFrom; i++) {
    if (hasQuestionResult(messages[i], { toolUseMap })) {
      protectedInRemoved.push(messages[i])
    } else {
      removable.push(messages[i])
    }
  }

  const preserved = [...protectedInRemoved, ...messages.slice(keepFrom)]
  const newSummary = summarizeMessages(removable)
  const mergedSummary = mergeSummaries(existingSummary ?? undefined, newSummary)
  const formattedSummary = formatCompactSummary(mergedSummary)
  const continuation = buildContinuationMessage(mergedSummary, preserved.length > 0)

  const compactedMessages: Message[] = [
    {
      role: 'system' as const,
      content: continuation,
    },
    ...preserved,
  ]

  return {
    summary: mergedSummary,
    formattedSummary,
    compactedMessages,
    removedMessageCount: removable.length,
  }
}

/* ------------------------------------------------------------------ */
/*  Summary construction                                               */
/* ------------------------------------------------------------------ */

function summarizeMessages(messages: Message[]): string {
  const userCount = messages.filter(m => m.role === 'user').length
  const assistantCount = messages.filter(m => m.role === 'assistant').length
  // Tool messages are represented as assistant messages with tool_result blocks
  // in CassiCore's message format (no separate 'tool' role)
  const toolCount = messages.filter(m => {
    if (typeof m.content === 'string') return false
    if (!Array.isArray(m.content)) return false
    return m.content.some((b: any) => b.type === 'tool_result' || b.type === 'tool_use')
  }).length

  const toolNames = collectToolNames(messages)
  const keyFiles = collectKeyFiles(messages)
  const pendingWork = inferPendingWork(messages)
  const recentRequests = collectRecentUserText(messages, 3)
  const currentWork = inferCurrentWork(messages)

  const lines: string[] = [
    '<summary>',
    'Conversation summary:',
    `- Scope: ${messages.length} earlier messages compacted (user=${userCount}, assistant=${assistantCount}, tool=${toolCount}).`,
  ]

  if (toolNames.length > 0) {
    lines.push(`- Tools mentioned: ${toolNames.join(', ')}.`)
  }

  if (recentRequests.length > 0) {
    lines.push('- Recent user requests:')
    for (const req of recentRequests) {
      lines.push(`  - ${truncate(req, 160)}`)
    }
  }

  if (pendingWork.length > 0) {
    lines.push('- Pending work:')
    for (const item of pendingWork) {
      lines.push(`  - ${truncate(item, 160)}`)
    }
  }

  if (keyFiles.length > 0) {
    lines.push(`- Key files referenced: ${keyFiles.join(', ')}.`)
  }

  if (currentWork) {
    lines.push(`- Current work: ${truncate(currentWork, 200)}`)
  }

  // Key timeline
  lines.push('- Key timeline:')
  for (const msg of messages) {
    const content = summarizeMessageContent(msg)
    lines.push(`  - ${msg.role}: ${truncate(content, 160)}`)
  }

  lines.push('</summary>')
  return lines.join('\n')
}

/* ------------------------------------------------------------------ */
/*  Summary merging (multi-round)                                      */
/* ------------------------------------------------------------------ */

function mergeSummaries(existingSummary: string | undefined, newSummary: string): string {
  if (!existingSummary) return newSummary

  const previousHighlights = extractSummaryHighlights(existingSummary)
  const newFormatted = formatCompactSummary(newSummary)
  const newHighlights = extractSummaryHighlights(newFormatted)
  const newTimeline = extractSummaryTimeline(newFormatted)

  const lines: string[] = [
    '<summary>',
    'Conversation summary:',
  ]

  if (previousHighlights.length > 0) {
    lines.push('- Previously compacted context:')
    for (const line of previousHighlights) {
      lines.push(`  ${line}`)
    }
  }

  if (newHighlights.length > 0) {
    lines.push('- Newly compacted context:')
    for (const line of newHighlights) {
      lines.push(`  ${line}`)
    }
  }

  if (newTimeline.length > 0) {
    lines.push('- Key timeline:')
    for (const line of newTimeline) {
      lines.push(`  ${line}`)
    }
  }

  lines.push('</summary>')
  return lines.join('\n')
}

/* ------------------------------------------------------------------ */
/*  Formatting / rendering                                             */
/* ------------------------------------------------------------------ */

function formatCompactSummary(summary: string): string {
  // Strip <analysis> blocks
  let result = stripTagBlock(summary, 'analysis')
  // Render <summary> content inline
  const content = extractTagContent(result, 'summary')
  if (content) {
    result = result.replace(
      `<summary>${content}</summary>`,
      `Summary:\n${content.trim()}`,
    )
  }
  return collapseBlankLines(result).trim()
}

function buildContinuationMessage(summary: string, hasPreservedMessages: boolean): string {
  let msg = COMPACTION_PREAMBLE + formatCompactSummary(summary)

  if (hasPreservedMessages) {
    msg += '\n\n' + RECENT_MESSAGES_NOTE
  }

  msg += '\n' + DIRECT_RESUME_INSTRUCTION
  return msg
}

/* ------------------------------------------------------------------ */
/*  Extraction helpers                                                 */
/* ------------------------------------------------------------------ */

function extractExistingCompactedSummary(messages: Message[]): string | null {
  const first = messages[0]
  if (!first || first.role !== 'system') return null
  const text = getTextContent(first)
  if (!text || !text.startsWith(COMPACTION_PREAMBLE.substring(0, 20))) return null
  // Strip preamble + notes
  let summary = text
  const preambleIdx = summary.indexOf(COMPACTION_PREAMBLE)
  if (preambleIdx >= 0) summary = summary.slice(COMPACTION_PREAMBLE.length)
  const notesIdx = summary.indexOf('\n\n' + RECENT_MESSAGES_NOTE)
  if (notesIdx >= 0) summary = summary.slice(0, notesIdx)
  const resumeIdx = summary.indexOf('\n' + DIRECT_RESUME_INSTRUCTION)
  if (resumeIdx >= 0) summary = summary.slice(0, resumeIdx)
  return summary.trim() || null
}

function existingSummaryPrefixLen(messages: Message[]): number {
  return extractExistingCompactedSummary(messages) !== null ? 1 : 0
}

function extractSummaryHighlights(summary: string): string[] {
  const lines: string[] = []
  let inTimeline = false

  for (const line of formatCompactSummary(summary).split('\n')) {
    const trimmed = line.trimEnd()
    if (!trimmed || trimmed === 'Summary:' || trimmed === 'Conversation summary:') continue
    if (trimmed === '- Key timeline:') { inTimeline = true; continue }
    if (inTimeline) continue
    lines.push(trimmed)
  }
  return lines
}

function extractSummaryTimeline(summary: string): string[] {
  const lines: string[] = []
  let inTimeline = false

  for (const line of formatCompactSummary(summary).split('\n')) {
    const trimmed = line.trimEnd()
    if (trimmed === '- Key timeline:') { inTimeline = true; continue }
    if (!inTimeline) continue
    if (!trimmed) break
    lines.push(trimmed)
  }
  return lines
}

/* ------------------------------------------------------------------ */
/*  Message content helpers                                            */
/* ------------------------------------------------------------------ */

function getTextContent(msg: Message): string | null {
  if (typeof msg.content === 'string') return msg.content
  if (!Array.isArray(msg.content)) return null
  for (const block of msg.content) {
    if ('text' in block && block.text) return block.text
  }
  return null
}

function summarizeMessageContent(msg: Message): string {
  if (typeof msg.content === 'string') return msg.content
  if (!Array.isArray(msg.content)) return '[non-text]'
  return msg.content.map(block => {
    if ('text' in block) return block.text
    if ('type' in block && block.type === 'tool_use') return `tool_use ${(block as any).name}(…)`
    if ('type' in block && block.type === 'tool_result') return `tool_result ${(block as any).tool_use_id}`
    return '[block]'
  }).join(' | ')
}

function collectToolNames(messages: Message[]): string[] {
  const names = new Set<string>()
  for (const msg of messages) {
    if (typeof msg.content === 'string') continue
    if (!Array.isArray(msg.content)) continue
    for (const block of msg.content) {
      if ('type' in block && block.type === 'tool_use' && 'name' in block) {
        names.add((block as any).name)
      }
    }
  }
  return [...names].sort()
}

function collectKeyFiles(messages: Message[]): string[] {
  const files = new Set<string>()
  for (const msg of messages) {
    const text = getTextContent(msg) ?? ''
    for (const token of text.split(/\s+/)) {
      const candidate = token.replace(/^[,.:;)"'`]+|[,.:;)"'`]+$/g, '')
      if (candidate.includes('/') && hasCodeExtension(candidate)) {
        files.add(candidate)
      }
    }
  }
  return [...files].slice(0, 8)
}

function inferPendingWork(messages: Message[]): string[] {
  const results: string[] = []
  for (let i = messages.length - 1; i >= 0 && results.length < 3; i--) {
    const text = getTextContent(messages[i])
    if (!text) continue
    const lower = text.toLowerCase()
    if (lower.includes('todo') || lower.includes('next') ||
        lower.includes('pending') || lower.includes('follow up') ||
        lower.includes('remaining')) {
      results.push(text)
    }
  }
  return results.reverse()
}

function collectRecentUserText(messages: Message[], limit: number): string[] {
  const results: string[] = []
  for (let i = messages.length - 1; i >= 0 && results.length < limit; i--) {
    if (messages[i].role === 'user') {
      const text = getTextContent(messages[i])
      if (text) results.push(text)
    }
  }
  return results.reverse()
}

function inferCurrentWork(messages: Message[]): string | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const text = getTextContent(messages[i])
    if (text && text.trim()) return text
  }
  return null
}

/* ------------------------------------------------------------------ */
/*  String helpers                                                     */
/* ------------------------------------------------------------------ */

function truncate(str: string, maxChars: number): string {
  if (str.length <= maxChars) return str
  return str.slice(0, maxChars) + '…'
}

function extractTagContent(content: string, tag: string): string | null {
  const start = `<${tag}>`
  const end = `</${tag}>`
  const startIdx = content.indexOf(start)
  if (startIdx < 0) return null
  const after = startIdx + start.length
  const endIdx = content.indexOf(end, after)
  if (endIdx < 0) return null
  return content.slice(after, endIdx)
}

function stripTagBlock(content: string, tag: string): string {
  const start = `<${tag}>`
  const end = `</${tag}>`
  const startIdx = content.indexOf(start)
  const endIdx = content.indexOf(end)
  if (startIdx < 0 || endIdx < 0) return content
  return content.slice(0, startIdx) + content.slice(endIdx + end.length)
}

function collapseBlankLines(content: string): string {
  const lines: string[] = []
  let prevBlank = false
  for (const line of content.split('\n')) {
    const isBlank = !line.trim()
    if (isBlank && prevBlank) continue
    lines.push(line.trimEnd())
    prevBlank = isBlank
  }
  return lines.join('\n')
}

const CODE_EXTENSIONS = new Set([
  'ts', 'tsx', 'js', 'jsx', 'json', 'md', 'rs', 'py',
  'yaml', 'yml', 'toml', 'sh', 'css', 'html', 'sql',
])

function hasCodeExtension(candidate: string): boolean {
  const ext = candidate.split('.').pop()?.toLowerCase()
  return ext ? CODE_EXTENSIONS.has(ext) : false
}
