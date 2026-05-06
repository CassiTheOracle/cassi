/**
 * N2 Posture Coherence Detector — pairwise consistency checks across
 * active compositions, pending meditation seeds, and (when their inputs
 * land) retrieval policies + scheduled replays + claustrum activation.
 *
 * Stateless except for the running config; all state comes in through the
 * `detect()` argument bag. This is the same shape as the existing
 * coherence-checker.ts (N6) — pure consumer of state.
 *
 * Severity legend (from spec §3.1):
 *   info     — noted but not actionable
 *   warning  — noted with a recommendation; default behavior continues
 *   serious  — blocks operation unless explicitly acknowledged
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { ActiveComposition, CompositionRecord } from '../composition/types.js'
import type { MeditationSeed } from '../meditation-seeder.js'
import {
  COHERENCE_DEFAULTS,
  type CoherenceCheck,
  type CoherenceDetectorConfig,
  type InvolvedElement,
} from './types.js'
import {
  cancellationOverlap,
  gateWeights,
  l1Norm,
  suppressedLabels,
} from './gate-weights.js'

export interface DetectorInputs {
  /** Active compositions and the records they reference (for AST lookup). */
  active: ActiveComposition[]
  records: CompositionRecord[]
  /** Pending meditation seeds (C1.3). Empty array when meditation seeder is disabled. */
  pendingSeeds: MeditationSeed[]
  /** Reserved for future B2/B3/claustrum inputs. */
  retrievalPolicy?: { affectBias?: 'similar' | 'complementary' | 'neutral' }
  scheduledReplays?: Array<{ id: string; sourceAffect?: { valence: number; arousal: number } }>
  currentAffect?: { valence: number; arousal: number }
  claustrumActivations?: Map<string, number>
}

export class PostureCoherenceDetector {
  private readonly logger: ILogger
  private readonly config: CoherenceDetectorConfig

  constructor(logger: ILogger, config?: Partial<CoherenceDetectorConfig>) {
    this.logger = logger.child ? logger.child('aurora:posture-coherence') : logger
    this.config = { ...COHERENCE_DEFAULTS, ...config }
  }

  detect(inputs: DetectorInputs): CoherenceCheck[] {
    const checks: CoherenceCheck[] = []
    checks.push(...this.detectCompositionPairs(inputs))
    checks.push(...this.detectCompositionMeditationSuppression(inputs))
    checks.push(...this.detectCompositionRetrievalMismatch(inputs))
    checks.push(...this.detectReplayAffectMismatch(inputs))
    checks.push(...this.detectMeditationEntrypointCold(inputs))
    checks.push(...this.detectCompositionMeditationColdTopic(inputs))
    return checks
  }

  /**
   * Categories 1+2: pairwise cancellation between active compositions.
   * Two compositions whose gate-weight maps share labels with OPPOSITE signs
   * are partly working against each other. The fraction of either composition's
   * L1 norm captured by the overlap distinguishes `cancelling` (partial) from
   * `contradictory` (most of one composition's mass is being undone).
   */
  private detectCompositionPairs(inputs: DetectorInputs): CoherenceCheck[] {
    const out: CoherenceCheck[] = []
    if (inputs.active.length < 2) return out

    const weighted = inputs.active.map(a => {
      const rec = inputs.records.find(r => r.name === a.name)
      const ast = rec?.ast ?? a.ast
      const weights = gateWeights(ast)
      return { name: a.name, weights, scale: a.magnitudeScale, l1: l1Norm(weights) }
    })

    for (let i = 0; i < weighted.length; i++) {
      for (let j = i + 1; j < weighted.length; j++) {
        const a = weighted[i]
        const b = weighted[j]
        const { overlap, conflictingGates } = cancellationOverlap(a.weights, b.weights)
        if (overlap < this.config.cancellingThreshold) continue

        const fracA = a.l1 > 0 ? overlap / a.l1 : 0
        const fracB = b.l1 > 0 ? overlap / b.l1 : 0
        const maxFrac = Math.max(fracA, fracB)
        const involved: InvolvedElement[] = [
          { kind: 'composition', id: a.name, label: a.name },
          { kind: 'composition', id: b.name, label: b.name },
        ]
        const gateList = conflictingGates.slice(0, 4).join(', ')

        if (maxFrac >= this.config.contradictoryFraction) {
          out.push(this.makeCheck({
            category: 'composition_pair_contradictory',
            severity: 'warning',
            message: `Compositions "${a.name}" and "${b.name}" largely contradict on { ${gateList} }: ${(maxFrac * 100).toFixed(0)}% of one's steering mass is being undone.`,
            involvedElements: involved,
            recommendation: `Deactivate one or reduce the magnitudeScale on the less-essential of the pair.`,
          }))
        } else {
          out.push(this.makeCheck({
            category: 'composition_pair_cancelling',
            severity: 'info',
            message: `Compositions "${a.name}" and "${b.name}" partly cancel on { ${gateList} }; net steering on those gates will be muted.`,
            involvedElements: involved,
          }))
        }
      }
    }
    return out
  }

  /**
   * Category 3: a suppressive composition is active and a pending meditation
   * seed targets one of the suppressed labels. C1's curator wants to fill a
   * gap in territory B1 is dampening — the meditation will hit a wall.
   *
   * Detection: tokenize seed.topic against the suppressed-label set. Any
   * substring match (case-insensitive) flags the pair.
   */
  private detectCompositionMeditationSuppression(inputs: DetectorInputs): CoherenceCheck[] {
    const out: CoherenceCheck[] = []
    if (inputs.active.length === 0 || inputs.pendingSeeds.length === 0) return out

    const suppressors = inputs.active
      .map(a => {
        const rec = inputs.records.find(r => r.name === a.name)
        if (!rec || !rec.suppressive) return null
        return { name: a.name, suppressed: suppressedLabels(rec.ast) }
      })
      .filter((x): x is { name: string; suppressed: Set<string> } => x !== null)
    if (suppressors.length === 0) return out

    for (const seed of inputs.pendingSeeds) {
      const topicLower = seed.topic.toLowerCase()
      for (const sup of suppressors) {
        const hits = [...sup.suppressed].filter(label => topicLower.includes(label.toLowerCase()))
        if (hits.length === 0) continue
        out.push(this.makeCheck({
          category: 'composition_meditation_suppression',
          severity: 'serious',
          message: `Composition "${sup.name}" is suppressing { ${hits.join(', ')} } while a pending meditation seed targets that area; the meditation will hit a wall.`,
          involvedElements: [
            { kind: 'composition', id: sup.name, label: sup.name },
            { kind: 'meditation_seed', id: seed.id, label: seed.topic.slice(0, 60) },
          ],
          recommendation: `Defer the seed, deactivate the composition before scheduling, or refuse the upcoming meditation.`,
        }))
      }
    }
    return out
  }

  /** Category 4: composition × retrieval policy. Stub until B2 lands. */
  private detectCompositionRetrievalMismatch(_inputs: DetectorInputs): CoherenceCheck[] {
    return []
  }

  /** Category 5: replay × current affect. Stub until B3 scheduling lands. */
  private detectReplayAffectMismatch(_inputs: DetectorInputs): CoherenceCheck[] {
    return []
  }

  /** Category 6: meditation entry-points cold. Stub until claustrum activation timeline lands. */
  private detectMeditationEntrypointCold(_inputs: DetectorInputs): CoherenceCheck[] {
    return []
  }

  /** Category 7: composition vs meditation cold-topic. Stub until claustrum activation lands. */
  private detectCompositionMeditationColdTopic(_inputs: DetectorInputs): CoherenceCheck[] {
    return []
  }

  /** Sort checks by severity (serious > warning > info), most recent first within ties. */
  rankChecks(checks: CoherenceCheck[]): CoherenceCheck[] {
    const order: Record<string, number> = { serious: 0, warning: 1, info: 2 }
    return [...checks].sort((a, b) => {
      const sd = order[a.severity] - order[b.severity]
      if (sd !== 0) return sd
      return b.detectedAt.localeCompare(a.detectedAt)
    })
  }

  /** Top-N projection helper — returns the N highest-priority checks. */
  topN(checks: CoherenceCheck[], n = this.config.projectionTopN): CoherenceCheck[] {
    return this.rankChecks(checks).slice(0, n)
  }

  private makeCheck(opts: {
    category: CoherenceCheck['category']
    severity: CoherenceCheck['severity']
    message: string
    involvedElements: InvolvedElement[]
    recommendation?: string
  }): CoherenceCheck {
    return {
      id: `coherence-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      detectedAt: new Date().toISOString(),
      category: opts.category,
      severity: opts.severity,
      message: opts.message,
      involvedElements: opts.involvedElements,
      recommendation: opts.recommendation,
    }
  }
}
