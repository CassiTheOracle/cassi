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

  /**
   * Category 4: composition × retrieval policy.
   *
   * A retrieval policy with a non-neutral affect bias actively shapes WHAT
   * gets surfaced to the model. A suppressive composition actively
   * SUPPRESSES specific labels. When both are active, the policy's
   * directional pull is being undermined by the composition hiding
   * exactly what the policy is trying to surface (or surface against).
   *
   * We can't compare the *specific* labels the policy targets to the
   * composition's suppressed labels without cross-mapping affect to
   * concept space — that's a richer integration that lands when B2's
   * policy semantics are richer. For now we flag the structural pattern:
   * any suppressive composition is potentially fighting any non-neutral
   * policy. One check per (suppressive composition, policy) pair —
   * since there's a single policy, one check per suppressor.
   */
  private detectCompositionRetrievalMismatch(inputs: DetectorInputs): CoherenceCheck[] {
    const out: CoherenceCheck[] = []
    const policy = inputs.retrievalPolicy
    if (!policy || !policy.affectBias || policy.affectBias === 'neutral') return out
    if (inputs.active.length === 0) return out

    for (const a of inputs.active) {
      const rec = inputs.records.find(r => r.name === a.name)
      if (!rec || !rec.suppressive) continue
      const suppressed = [...suppressedLabels(rec.ast)]
      if (suppressed.length === 0) continue
      const labelList = suppressed.slice(0, 4).join(', ')
      out.push(this.makeCheck({
        category: 'composition_retrieval_mismatch',
        severity: 'warning',
        message: `Composition "${a.name}" is suppressing { ${labelList} } while a retrieval policy with affectBias="${policy.affectBias}" is active; the policy's directional pull is being undermined.`,
        involvedElements: [
          { kind: 'composition', id: a.name, label: a.name },
          { kind: 'retrieval_policy', id: 'policy', label: `affectBias=${policy.affectBias}` },
        ],
        recommendation: `Either deactivate the composition before this retrieval pass, or switch policy to affectBias="neutral".`,
      }))
    }
    return out
  }

  /**
   * Category 5: replay × current affect.
   *
   * A scheduled replay carries the affect state captured at the trace's
   * original turn. Replaying a trace into a state with very different
   * affect mismatches the cognitive context — the trace's reasoning was
   * tuned for *that* state, and surfacing it now will likely feel
   * incongruent. We measure euclidean distance on (valence, arousal)
   * and flag pairs above the configured threshold.
   *
   * No-op when current affect or scheduled replays aren't supplied.
   */
  private detectReplayAffectMismatch(inputs: DetectorInputs): CoherenceCheck[] {
    const out: CoherenceCheck[] = []
    if (!inputs.currentAffect || !inputs.scheduledReplays || inputs.scheduledReplays.length === 0) return out

    const cur = inputs.currentAffect
    const threshold = this.config.replayAffectMismatchThreshold
    for (const replay of inputs.scheduledReplays) {
      const src = replay.sourceAffect
      if (!src) continue
      const dv = cur.valence - src.valence
      const da = cur.arousal - src.arousal
      const distance = Math.sqrt(dv * dv + da * da)
      if (distance < threshold) continue
      out.push(this.makeCheck({
        category: 'replay_affect_mismatch',
        severity: 'warning',
        message: `Scheduled replay "${replay.id}" was traced at affect (v=${src.valence.toFixed(2)}, a=${src.arousal.toFixed(2)}) but current affect is (v=${cur.valence.toFixed(2)}, a=${cur.arousal.toFixed(2)}); distance ${distance.toFixed(2)} exceeds threshold ${threshold.toFixed(2)}.`,
        involvedElements: [
          { kind: 'replay', id: replay.id, label: replay.id },
        ],
        recommendation: `Defer the replay until affect aligns, or skip — the trace's reasoning was tuned for a state that's no longer current.`,
      }))
    }
    return out
  }

  /**
   * Category 6: meditation entry-points cold.
   *
   * A directed meditation needs claustrum entry-points that are warm
   * enough to anchor the discovery loop. If a pending seed's topic
   * mentions concepts that have no active claustrum nodes (or only
   * cold ones below threshold), the meditation will burn budget on
   * bootstrap before it can do useful work. Flag as warning.
   *
   * Match heuristic: tokenize the seed's topic and look for any
   * claustrum node id whose id appears (case-insensitive) in the topic.
   * If no such node exists OR all matching nodes are cold, the seed has
   * no warm anchor.
   */
  private detectMeditationEntrypointCold(inputs: DetectorInputs): CoherenceCheck[] {
    const out: CoherenceCheck[] = []
    if (!inputs.claustrumActivations || inputs.pendingSeeds.length === 0) return out
    const activations = inputs.claustrumActivations
    const cold = this.config.coldActivationThreshold

    for (const seed of inputs.pendingSeeds) {
      const topicLower = seed.topic.toLowerCase()
      const matches: Array<{ id: string; activation: number }> = []
      for (const [nodeId, activation] of activations) {
        if (topicLower.includes(nodeId.toLowerCase())) {
          matches.push({ id: nodeId, activation })
        }
      }
      const warm = matches.filter(m => m.activation > cold)
      if (warm.length > 0) continue
      const detail = matches.length === 0
        ? `no claustrum nodes in topic`
        : `all matching nodes ({ ${matches.map(m => `${m.id}@${m.activation.toFixed(2)}`).join(', ')} }) are at or below cold threshold ${cold}`
      out.push(this.makeCheck({
        category: 'meditation_entrypoint_cold',
        severity: 'warning',
        message: `Pending meditation seed "${seed.topic.slice(0, 60)}" has no warm claustrum entry-points (${detail}); the meditation will spend budget on bootstrap.`,
        involvedElements: [
          { kind: 'meditation_seed', id: seed.id, label: seed.topic.slice(0, 60) },
          ...matches.map(m => ({ kind: 'claustrum_node' as const, id: m.id, label: `${m.id}@${m.activation.toFixed(2)}` })),
        ],
        recommendation: `Defer the seed until claustrum is warmer in this region, or replace with one whose entry-points are currently active.`,
      }))
    }
    return out
  }

  /**
   * Category 7: composition vs meditation cold-topic.
   *
   * A composition that BOOSTS labels (positive contributions) the
   * meditation seed targets — but those labels have no warm claustrum
   * support — is amplifying noise. The composition's effect won't
   * ground out into anything the model can build on; it'll just
   * inflate magnitude on a region the model has no traction in.
   *
   * Severity is `info` — this isn't a blocker, just a heads-up that the
   * composition's boost isn't doing useful work for the upcoming
   * meditation.
   */
  private detectCompositionMeditationColdTopic(inputs: DetectorInputs): CoherenceCheck[] {
    const out: CoherenceCheck[] = []
    if (!inputs.claustrumActivations || inputs.pendingSeeds.length === 0 || inputs.active.length === 0) return out
    const activations = inputs.claustrumActivations
    const cold = this.config.coldActivationThreshold

    const boosters = inputs.active
      .map(a => {
        const rec = inputs.records.find(r => r.name === a.name)
        const ast = rec?.ast ?? a.ast
        const weights = gateWeights(ast)
        const boostedLabels = [...weights.entries()]
          .filter(([, w]) => w > 0)
          .map(([label]) => label)
        return { name: a.name, boosted: boostedLabels }
      })
      .filter(b => b.boosted.length > 0)
    if (boosters.length === 0) return out

    for (const seed of inputs.pendingSeeds) {
      const topicLower = seed.topic.toLowerCase()
      for (const booster of boosters) {
        const overlap = booster.boosted.filter(label => topicLower.includes(label.toLowerCase()))
        if (overlap.length === 0) continue
        const coldHits = overlap.filter(label => {
          const act = activations.get(label)
          return act === undefined || act <= cold
        })
        if (coldHits.length === 0) continue
        out.push(this.makeCheck({
          category: 'composition_meditation_cold_topic',
          severity: 'info',
          message: `Composition "${booster.name}" is boosting { ${coldHits.join(', ')} } in the topic of seed "${seed.topic.slice(0, 60)}" but those concepts are cold in claustrum; the boost won't ground out.`,
          involvedElements: [
            { kind: 'composition', id: booster.name, label: booster.name },
            { kind: 'meditation_seed', id: seed.id, label: seed.topic.slice(0, 60) },
          ],
          recommendation: `Acceptable — informational. The composition will still steer for other turns; the seed will just have to bootstrap that region itself.`,
        }))
      }
    }
    return out
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
