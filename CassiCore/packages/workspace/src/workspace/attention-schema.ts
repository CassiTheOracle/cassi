/**
 * AttentionSchema — Metacognitive self-model of the workspace.
 *
 * The Attention Schema Theory (Graziano, 2013) extends GWT: the brain
 * doesn't just have attention — it has a MODEL of its own attention.
 * This model enables metacognition: "I am aware that I am paying
 * attention to X, and that Y was recently eclipsed."
 *
 * The AttentionSchema captures:
 *   - What's currently in focus (occupied slots)
 *   - What recently left focus (eclipses, expirations)
 *   - The current ignition threshold and its trend
 *   - Source credibility rankings (which modules are trusted)
 *   - Active coalitions (cross-module amplification)
 *   - Attention pressure (demand vs capacity)
 *
 * This schema can be:
 *   1. Queried by modules to inform their signal production
 *   2. Injected into the LLM context for genuine metacognition
 *   3. Logged for observability and debugging
 */

import type { SignalType, WorkspaceSlot } from './cognitive-signal.js'
import type { Coalition } from './coalition.js'
import type { CredibilityRecord } from './workspace-memory.js'


export interface FocusEntry {
  source: string
  type: SignalType
  contentSummary: string
  luminance: number
  ticksInFocus: number
}

export interface EclipseRecord {
  signalId: string
  source: string
  type: SignalType
  reason: 'eclipsed' | 'expired' | 'consumed'
  luminanceAtExit: number
  exitedAt: number
}

export interface AttentionSchema {
  /** What's currently occupying the workspace */
  currentFoci: FocusEntry[]
  /** What recently left the workspace */
  recentEclipses: EclipseRecord[]
  /** Current ignition threshold */
  threshold: number
  /** Is the threshold rising, falling, or stable? */
  thresholdTrend: 'rising' | 'stable' | 'falling'
  /** Module credibility rankings (top sources first) */
  sourceRankings: Array<{ source: string; credibility: number }>
  /** Number of active coalitions */
  activeCoalitions: number
  /** Ratio of submitted signals to available slots */
  pressure: number
  /** Total signals processed since last reset */
  totalSignalsProcessed: number
  /** Ignition rate: fraction of signals that entered workspace */
  ignitionRate: number
  /** Timestamp of this snapshot */
  timestamp: number
}


/**
 * Build an AttentionSchema from current workspace state.
 */
export function buildAttentionSchema(
  slots: WorkspaceSlot[],
  eclipseHistory: EclipseRecord[],
  threshold: number,
  thresholdTrend: 'rising' | 'stable' | 'falling',
  credibilityRecords: CredibilityRecord[],
  coalitions: Coalition[],
  totalSubmitted: number,
  totalIgnited: number,
): AttentionSchema {
  const currentFoci: FocusEntry[] = []
  for (const slot of slots) {
    if (!slot.signal) continue
    currentFoci.push({
      source: slot.signal.source,
      type: slot.signal.type,
      contentSummary: slot.signal.content.slice(0, 120),
      luminance: slot.signal.luminance.composite,
      ticksInFocus: slot.occupancyTicks,
    })
  }

  const sourceRankings = credibilityRecords
    .filter(r => r.totalSignals > 0)
    .sort((a, b) => b.credibility - a.credibility)
    .map(r => ({ source: r.source, credibility: r.credibility }))

  const occupiedCount = slots.filter(s => s.signal !== null).length

  return {
    currentFoci,
    recentEclipses: eclipseHistory.slice(-10),
    threshold,
    thresholdTrend,
    sourceRankings,
    activeCoalitions: coalitions.length,
    pressure: totalSubmitted > 0 ? totalSubmitted / slots.length : 0,
    totalSignalsProcessed: totalSubmitted,
    ignitionRate: totalSubmitted > 0 ? totalIgnited / totalSubmitted : 0,
    timestamp: Date.now(),
  }
}


/**
 * Format the attention schema as human-readable text for LLM context injection.
 * Concise — this competes for workspace budget like everything else.
 */
export function formatAttentionSchema(schema: AttentionSchema): string {
  const lines: string[] = ['[Attention State]']

  if (schema.currentFoci.length > 0) {
    lines.push(`Focus (${schema.currentFoci.length} signals):`)
    for (const f of schema.currentFoci) {
      lines.push(`  ${f.source}/${f.type} (${f.luminance.toFixed(2)}): ${f.contentSummary}`)
    }
  } else {
    lines.push('Focus: empty')
  }

  if (schema.recentEclipses.length > 0) {
    const last = schema.recentEclipses[schema.recentEclipses.length - 1]
    lines.push(`Last eclipse: ${last.source}/${last.type} (${last.reason})`)
  }

  lines.push(`Threshold: ${schema.threshold.toFixed(2)} (${schema.thresholdTrend}), pressure: ${schema.pressure.toFixed(1)}`)

  if (schema.sourceRankings.length > 0) {
    const top3 = schema.sourceRankings.slice(0, 3).map(r => `${r.source}:${r.credibility.toFixed(2)}`).join(', ')
    lines.push(`Top sources: ${top3}`)
  }

  return lines.join('\n')
}
