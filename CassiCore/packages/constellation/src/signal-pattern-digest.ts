/**
 * Signal-pattern digest — rolling buffer of recent CognitiveSignals from sibling
 * Helixes, rendered as advisory pattern-recognition input for the Corpus's
 * decision LLM. Implements C-OBS-1 GWT-grounding supplement
 * (docs/design/cassi-proposed/pending/2026-05-06-c-obs-1-gwt-grounding.md).
 *
 * The digest is *advisory*, not procedural — pattern thresholds enter the prompt
 * as suggestions ("consider send_directive..."), not as automated tool calls.
 * The Corpus LLM decides whether to act.
 */

import type { CognitiveSignal, SignalType } from './vendor/workspace/cognitive-signal.js'

const DEFAULT_MAX_ENTRIES = 30
const DEFAULT_WINDOW_MS = 60_000
const RENDER_CHAR_CAP = 1_500
const TENSION_CLUSTER_THRESHOLD = 3
const WARNING_COALITION_THRESHOLD = 2

export interface PatternEntry {
  type: SignalType
  source: string
  sessionId: string
  contentPreview: string
  receivedAt: number
}

export class SignalPatternBuffer {
  private entries: PatternEntry[] = []

  constructor(
    private readonly maxEntries: number = DEFAULT_MAX_ENTRIES,
    private readonly windowMs: number = DEFAULT_WINDOW_MS,
  ) {}

  record(signal: CognitiveSignal): void {
    this.prune()
    this.entries.push({
      type: signal.type,
      source: signal.source,
      sessionId: signal.sessionId,
      contentPreview: signal.content.slice(0, 200),
      receivedAt: signal.createdAt,
    })
    if (this.entries.length > this.maxEntries) {
      this.entries = this.entries.slice(-this.maxEntries)
    }
  }

  snapshot(): PatternEntry[] {
    this.prune()
    return [...this.entries]
  }

  size(): number {
    this.prune()
    return this.entries.length
  }

  clear(): void {
    this.entries = []
  }

  private prune(): void {
    const cutoff = Date.now() - this.windowMs
    this.entries = this.entries.filter(e => e.receivedAt >= cutoff)
  }
}

/**
 * Filter that determines whether a signal should be recorded into the digest.
 * Skips Corpus's own emissions (prevents self-feedback) and types already
 * handled by the territory-awareness pillar (goal, bridge).
 */
export function shouldRecordForDigest(signal: CognitiveSignal): boolean {
  if (signal.source === 'corpus') return false
  if (signal.type === 'goal' || signal.type === 'bridge') return false
  return true
}

export function renderDigestMarkdown(buffer: SignalPatternBuffer): string | undefined {
  const entries = buffer.snapshot()
  if (entries.length === 0) return undefined

  const byType = new Map<SignalType, number>()
  for (const e of entries) byType.set(e.type, (byType.get(e.type) ?? 0) + 1)

  const tensionsByHelix = new Map<string, number>()
  for (const e of entries) {
    if (e.type === 'tension') {
      tensionsByHelix.set(e.sessionId, (tensionsByHelix.get(e.sessionId) ?? 0) + 1)
    }
  }

  const warningHelixes = new Set<string>()
  for (const e of entries) if (e.type === 'warning') warningHelixes.add(e.sessionId)

  const lines: string[] = []
  lines.push(`Recent workspace signals (last ${entries.length} in 60s window):`)

  const typeSummary = [...byType.entries()].map(([t, c]) => `${t}=${c}`).join(', ')
  lines.push(`  Counts: ${typeSummary}`)

  for (const [hid, count] of tensionsByHelix) {
    if (count >= TENSION_CLUSTER_THRESHOLD) {
      lines.push(
        `  ⚠ ${hid.slice(0, 8)} produced ${count} tension signals — consider send_directive with narrowed framing, or request_spawn with narrowedGoal if framing was already attempted`,
      )
    }
  }

  if (warningHelixes.size >= WARNING_COALITION_THRESHOLD) {
    lines.push(
      `  ⚠ ${warningHelixes.size} sibling Helixes raised warnings — consider request_spawn with a research subtask, or escalate via send_directive to all members`,
    )
  }

  const recent = entries
    .filter(e => e.type === 'tension' || e.type === 'warning' || e.type === 'convergence')
    .slice(-5)
  if (recent.length) {
    lines.push(
      `  Recent: ${recent.map(e => `[${e.type}] ${e.contentPreview.slice(0, 60)}`).join(' | ')}`,
    )
  }

  let out = lines.join('\n')
  if (out.length > RENDER_CHAR_CAP) {
    out = out.slice(0, RENDER_CHAR_CAP) + ' [truncated]'
  }
  return out
}
