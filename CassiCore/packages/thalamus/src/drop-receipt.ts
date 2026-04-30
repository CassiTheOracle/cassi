/**
 * Drop receipts: a single human-readable line describing what curation removed,
 * plus per-domain anomaly flags.
 *
 * The receipt rides curate's `meta` field and is injected by the proxy as a
 * synthetic system block on the next turn. This makes silent message removal
 * visible from inside the model — closing the curation feedback loop that the
 * cassi-context-awareness spec calls out.
 */

import type { ScoredMessage, ThalamusAnnotation } from './types.js'
import { hasQuestionResult, buildToolUseMapFromMessages } from '../../pipeline/turn/overflow.js'

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
}

/** Build a receipt or return null when nothing was dropped. */
export function buildDropReceipt(input: BuildReceiptInput): DropReceipt | null {
  const { before, scored, includedIndices, protectedIndices } = input
  const droppedIndices: number[] = []
  for (const s of scored) {
    if (includedIndices.has(s.messageIndex)) continue
    if (protectedIndices.has(s.messageIndex)) continue
    droppedIndices.push(s.messageIndex)
  }

  if (droppedIndices.length === 0) return null

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

  return {
    dropped: droppedIndices.length,
    bySlot,
    charsFreed,
    anomalies,
    summary,
    ts: new Date().toISOString(),
  }
}

/** Render the receipt as a system-block payload for proxy injection. */
export function renderDropReceiptBlock(receipt: DropReceipt): string {
  const lines = [receipt.summary]
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
