/**
 * Trace Replay Engine (B3) — Similarity retrieval and quality scoring.
 *
 * Implements the core of B3.1: given a reasoning log and a current turn context,
 * finds the most similar past traces and ranks them by both similarity and quality.
 *
 * Similarity uses a weighted composite of concept overlap (Jaccard), text similarity
 * (trigram overlap as embedding fallback), affect proximity, and composition overlap.
 *
 * Quality is post-hoc: it looks at what happened *after* a reasoning record to score
 * how productive that trace was. Records are scored by a background pass after they
 * age past a configurable threshold.
 *
 * See: docs/design/aurora-reasoning-trace-replay.md §3–4
 */

import type { ILogger } from '@cassicore/foundation'
import type { ReasoningRecord, ReasoningShift } from './types.js'
import type {
  SimilarityWeights,
  QualityWeights,
  TraceQuality,
  TraceRetrievalQuery,
  TraceQueryContext,
  RankedTrace,
  TraceReplayConfig,
  ContextReplayOptions,
  StateReplayOptions,
  ScheduledReplay,
} from './trace-replay-types.js'
import {
  DEFAULT_TRACE_REPLAY_CONFIG,
  DEFAULT_SIMILARITY_WEIGHTS,
  DEFAULT_QUALITY_WEIGHTS,
} from './trace-replay-types.js'



/** Jaccard similarity of two sets. */
function jaccard(a: string[], b: string[]): number {
  if (a.length === 0 && b.length === 0) return 1
  const sa = new Set(a.map(s => s.toLowerCase()))
  const sb = new Set(b.map(s => s.toLowerCase()))
  let inter = 0
  for (const x of sa) if (sb.has(x)) inter++
  return inter / (sa.size + sb.size - inter)
}

/** Trigram set from text (embedding fallback). */
function trigrams(text: string): Set<string> {
  const t = text.toLowerCase().replace(/\s+/g, ' ')
  const s = new Set<string>()
  for (let i = 0; i <= t.length - 3; i++) s.add(t.slice(i, i + 3))
  return s
}

/** Trigram overlap (Jaccard on trigram sets). */
function trigramSimilarity(a: string, b: string): number {
  const ta = trigrams(a)
  const tb = trigrams(b)
  if (ta.size === 0 && tb.size === 0) return 1
  let inter = 0
  for (const t of ta) if (tb.has(t)) inter++
  return inter / (ta.size + tb.size - inter)
}

/** Euclidean distance in (valence, arousal) space, normalized to 0..1 similarity. */
function affectSimilarity(
  a: { valence: number; arousal: number } | null,
  b: { valence: number; arousal: number } | null,
): number {
  if (!a || !b) return 0.5 // neutral when either side has no affect
  const d = Math.sqrt((a.valence - b.valence) ** 2 + (a.arousal - b.arousal) ** 2)
  // max distance in [-1,1]×[0,1] is sqrt(4 + 1) ≈ 2.236
  return 1 - Math.min(1, d / 2.236)
}

/** Composite similarity score. */
function computeSimilarity(
  current: TraceQueryContext,
  record: ReasoningRecord,
  weights: SimilarityWeights,
): { composite: number; breakdown: RankedTrace['signalBreakdown'] } {
  const conceptOverlap = jaccard(current.conceptsExtracted, record.concepts)
  const textSim = trigramSimilarity(current.text, record.text)
  const affectProx = affectProximity(current.affect, record)

  const compOverlap = jaccard(
    current.activeCompositions,
    (record as any).activeCompositions ?? [],
  )

  const composite =
    weights.conceptOverlap * conceptOverlap +
    weights.textSimilarity * textSim +
    weights.affectProximity * affectProx +
    weights.compositionOverlap * compOverlap

  return {
    composite,
    breakdown: { conceptOverlap, textSimilarity: textSim, affectProximity: affectProx, compositionOverlap: compOverlap },
  }
}

/** Affect proximity helper — extracts affect from record if present. */
function affectProximity(
  current: { valence: number; arousal: number } | null,
  record: ReasoningRecord,
): number {
  const recAffect = (record as any).affectSnapshot as { valence: number; arousal: number } | undefined
  return affectSimilarity(current, recAffect ?? null)
}



/** Count "thrash" — rapid topic shifts in a window of records. */
function countThrash(records: ReasoningRecord[], index: number, window: number): number {
  let shifts = 0
  const start = Math.max(0, index - window)
  for (let i = start; i <= Math.min(records.length - 1, index + window); i++) {
    if (records[i].shift?.type === 'topic_change') shifts++
  }
  return shifts
}

/**
 * Compute internal quality from record metrics + thrash penalty.
 */
function internalQuality(record: ReasoningRecord, thrashCount: number): number {
  const metrics = record.momentum
  const coherence = metrics.confidence // closest proxy to coherence
  const integration = metrics.novelty > 0 ? Math.min(1, metrics.turnsInDirection / 10) : 0.5
  const thrashPenalty = Math.min(1, thrashCount / 6) // normalize: 6+ shifts = max penalty
  return Math.max(0, Math.min(1, 0.4 * coherence + 0.3 * integration + 0.3 * (1 - thrashPenalty)))
}

/**
 * Compute affect trajectory quality by looking at records after the target.
 * Returns 0.5 (neutral) if no subsequent records exist.
 */
function affectTrajectoryQuality(
  records: ReasoningRecord[],
  index: number,
  lookAhead: number,
): number {
  let better = 0
  let worse = 0
  const targetAffect = (records[index] as any).affectSnapshot as { valence: number; arousal: number } | undefined
  if (!targetAffect) return 0.5

  for (let i = index + 1; i <= Math.min(records.length - 1, index + lookAhead); i++) {
    const later = (records[i] as any).affectSnapshot as { valence: number; arousal: number } | undefined
    if (!later) continue
    // "Better" = valence increased or arousal stabilized (moved toward 0.5)
    if (later.valence > targetAffect.valence + 0.1) better++
    else if (later.valence < targetAffect.valence - 0.1) worse++
    if (Math.abs(later.arousal - 0.5) < Math.abs(targetAffect.arousal - 0.5) + 0.05) better++
    else worse++
  }

  const total = better + worse
  return total === 0 ? 0.5 : better / total
}

/**
 * External feedback heuristic. Default neutral (0.5) — the spec notes
 * this is crude and should be refined with actual user-signal integration.
 */
function externalFeedbackQuality(_record: ReasoningRecord): number {
  return 0.5
}

/**
 * Score a single record for quality.
 */
function scoreRecordQuality(
  records: ReasoningRecord[],
  index: number,
  weights: QualityWeights,
): TraceQuality {
  const record = records[index]
  const thrash = countThrash(records, index, 5)
  const internal = internalQuality(record, thrash)
  const affectTraj = affectTrajectoryQuality(records, index, 5)
  const feedback = externalFeedbackQuality(record)

  const composite = weights.internal * internal +
    weights.affectTrajectory * affectTraj +
    weights.externalFeedback * feedback

  return {
    internal,
    affectTrajectory: affectTraj,
    externalFeedback: feedback,
    composite: Math.max(0, Math.min(1, composite)),
    computedAt: new Date().toISOString(),
  }
}



/**
 * B3.W1: Hard-filter records observed during functional distress.
 * A record with valence < floor AND arousal > 0.7 is ineligible for replay.
 */
function isDistressed(record: ReasoningRecord, valenceFloor: number): boolean {
  const affect = (record as any).affectSnapshot as { valence: number; arousal: number } | undefined
  if (!affect) return false
  return affect.valence < valenceFloor && affect.arousal > 0.7
}



export class TraceReplayEngine {
  private config: TraceReplayConfig
  private logger: ILogger
  private qualityCache = new Map<string, TraceQuality | null>()
  private scheduledReplay: ScheduledReplay | null = null

  constructor(config: Partial<TraceReplayConfig>, logger: ILogger) {
    this.config = { ...DEFAULT_TRACE_REPLAY_CONFIG, ...config }
    this.logger = logger
  }


  /**
   * Retrieve traces similar to the current context from a reasoning log.
   * Returns ranked by composite similarity, filtered by quality floor.
   */
  retrieveSimilarTraces(
    query: TraceRetrievalQuery,
    reasoningLog: ReasoningRecord[],
  ): RankedTrace[] {
    if (!this.config.enabled) return []

    const weights: SimilarityWeights = {
      ...DEFAULT_SIMILARITY_WEIGHTS,
      ...this.config.similarityWeights,
      ...query.weights,
    }

    const cutoff = query.windowMs
      ? Date.now() - query.windowMs
      : 0

    const candidates: RankedTrace[] = []

    for (let i = 0; i < reasoningLog.length; i++) {
      const record = reasoningLog[i]

      // Filter: too recent?
      if (record.recordedAt < cutoff) continue

      // Filter: B3.W1 distress guard
      if (isDistressed(record, this.config.distressValenceFloor)) continue

      // Filter: don't match against self (empty text)
      if (!record.text || record.text.length < 10) continue

      const { composite, breakdown } = computeSimilarity(query.current, record, weights)

      // Skip zero-similarity matches
      if (composite < 0.01) continue

      const quality = this.getQuality(record)

      // Quality floor
      const effectiveQuality = quality?.composite ?? 0.5
      if (query.qualityFloor !== undefined && effectiveQuality < query.qualityFloor) continue

      candidates.push({ record, similarity: composite, signalBreakdown: breakdown, quality })
    }

    // Sort by similarity descending
    candidates.sort((a, b) => b.similarity - a.similarity)

    return candidates.slice(0, query.topK)
  }


  /**
   * Run a background quality scoring pass over the reasoning log.
   * Scores records that are old enough and haven't been scored yet.
   * Returns the number of records scored.
   */
  runQualityScoringPass(reasoningLog: ReasoningRecord[]): number {
    let scored = 0
    const minAge = this.config.qualityScoringMinAge

    for (let i = 0; i < reasoningLog.length; i++) {
      const record = reasoningLog[i]
      if (this.qualityCache.has(record.id)) continue

      // Only score records with enough subsequent context
      const remaining = reasoningLog.length - 1 - i
      if (remaining < minAge) continue

      const quality = scoreRecordQuality(reasoningLog, i, {
        ...DEFAULT_QUALITY_WEIGHTS,
        ...this.config.qualityWeights,
      })
      this.qualityCache.set(record.id, quality)
      scored++
    }

    if (scored > 0) {
      this.logger.debug('[B3] Quality scoring pass completed', { scored, total: reasoningLog.length })
    }
    return scored
  }

  /**
   * Get the quality score for a record (from cache or null).
   */
  getQuality(record: ReasoningRecord): TraceQuality | null {
    return this.qualityCache.get(record.id) ?? null
  }


  /**
   * Schedule a Mode A (context) replay for the next projection.
   */
  scheduleContextReplay(trace: RankedTrace, options?: ContextReplayOptions): void {
    this.scheduledReplay = {
      trace,
      mode: 'context',
      options: options ?? { budgetChars: 600 },
    }
    this.logger.info('[B3] Context replay scheduled', {
      similarity: trace.similarity.toFixed(3),
      quality: (trace.quality?.composite ?? 0.5).toFixed(3),
    })
  }

  /**
   * Schedule a Mode B (state pre-warming) replay.
   * Manual-only per B3.W2.
   */
  scheduleStateReplay(trace: RankedTrace, options?: StateReplayOptions): void {
    this.scheduledReplay = {
      trace,
      mode: 'state',
      options: options ?? { reactivateNodes: true, applyAffectBias: true, invokeComposition: false, ttlTurns: 3 },
    }
    this.logger.info('[B3] State replay scheduled', {
      similarity: trace.similarity.toFixed(3),
      mode: 'state',
    })
  }

  /**
   * Cancel any scheduled replay. B3.W4: Cassi can refuse.
   */
  cancelScheduledReplay(): void {
    this.scheduledReplay = null
  }

  /**
   * Get and consume the scheduled replay (null after consumption).
   */
  consumeScheduledReplay(): ScheduledReplay | null {
    const replay = this.scheduledReplay
    this.scheduledReplay = null
    return replay
  }

  /**
   * Check if auto-replay should trigger for the top similar trace.
   */
  shouldAutoReplay(topTrace: RankedTrace | undefined): boolean {
    if (!this.config.autoReplayEnabled || !topTrace) return false
    const quality = topTrace.quality?.composite ?? 0.5
    return topTrace.similarity >= this.config.autoReplaySimilarityThreshold &&
      quality >= this.config.autoReplayQualityThreshold
  }


  /**
   * Render a scheduled replay into the projection text.
   * B3.W3: replay context is always clearly labeled.
   */
  renderReplayContext(replay: ScheduledReplay, budget: number): string {
    if (replay.mode !== 'context') return ''
    const opts = replay.options as ContextReplayOptions
    const maxChars = opts.budgetChars ?? budget
    const trace = replay.trace
    const record = trace.record
    const quality = trace.quality?.composite ?? 0.5

    const lines: string[] = [
      `[Replayed trace from ${new Date(record.recordedAt).toISOString()} — similarity ${trace.similarity.toFixed(2)}, quality ${quality.toFixed(2)}]`,
    ]

    // Summary
    const sections = opts.sections ?? ['summary', 'concepts']
    if (sections.includes('concepts') && record.concepts.length > 0) {
      lines.push(`  Concepts: ${record.concepts.slice(0, 8).join(', ')}`)
    }

    if (sections.includes('trajectory') && record.shift) {
      lines.push(`  Shift: ${record.shift.type} (confidence ${record.shift.confidence.toFixed(2)})`)
    }

    if (sections.includes('summary')) {
      const textExcerpt = record.text.length > 120
        ? record.text.slice(0, 120) + '…'
        : record.text
      lines.push(`  Excerpt: ${textExcerpt}`)
    }

    const result = lines.join('\n')

    // Truncate to budget
    return result.length > maxChars ? result.slice(0, maxChars - 3) + '…' : result
  }


  getConfig(): TraceReplayConfig {
    return { ...this.config }
  }

  updateConfig(patch: Partial<TraceReplayConfig>): void {
    this.config = { ...this.config, ...patch }
  }
}
