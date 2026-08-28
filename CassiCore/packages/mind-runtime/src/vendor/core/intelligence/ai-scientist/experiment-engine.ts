/**
 * AI Scientist — Experiment Engine
 *
 * Manages the full lifecycle of controlled self-improvement experiments:
 *
 *   1. Queue      — experiment is waiting to start
 *   2. Active     — treatment has been applied to the live system
 *   3. Concluded  — statistical analysis complete; winner applied or reverted
 *
 * Each experiment targets a single cognitive parameter (stored in the KV
 * store and live-reloaded via an event bus signal) and measures one metric
 * over a rolling window of turns.  A Welch's t-test + Cohen's d gate
 * ensures we only apply changes that are statistically and practically
 * significant.
 */

import { welchTTest, cohensD, betaPosteriorMean, describeStats } from './stats.js'

import type { IMemory } from '@cassicore/foundation'
import type { ILogger , IEventBus } from '@cassicore/foundation'


export type ExperimentStatus = 'queued' | 'active' | 'concluded'
export type ExperimentOutcome = 'improvement' | 'neutral' | 'regression' | 'insufficient_data'

/** Which cognitive metric the experiment is optimising. */
export type ExperimentMetric =
  | 'thinker_helpfulness'   // fraction of insights rated helpful (binary → Bayesian)
  | 'thinker_insight_rate'  // insights generated per turn
  | 'turn_latency_ms'       // end-to-end turn duration (lower is better)
  | 'dialectic_signal_rate' // signals per turn
  | 'session_depth'         // avg turns per session (proxy for engagement)

/** A single-parameter treatment to A/B test. */
export interface ExperimentTreatment {
  /** KV key that the target module reads on startup / hot-reload. */
  kvKey: string
  /** New value to write for the treatment period. */
  treatmentValue: unknown
  /** Value to restore if the experiment fails. */
  baselineValue: unknown
  /**
   * Optional event type to emit on the bus so the target module applies the
   * change immediately without restart.
   */
  reloadEvent?: string
}

export interface Experiment {
  id: string
  title: string
  hypothesis: string
  /** One-sentence scientific rationale — why this is worth investigating. */
  rationale: string
  track: 'performance' | 'aging' | 'development' | 'self-improvement'
  metric: ExperimentMetric
  /** True when a higher metric value means better performance. */
  higherIsBetter: boolean
  treatment: ExperimentTreatment
  /** Minimum number of treatment samples before drawing conclusions. */
  minSamples: number
  /** Hard cap: auto-conclude after this many turns even with few samples. */
  maxTurns: number
  status: ExperimentStatus
  outcome?: ExperimentOutcome
  /** Metric samples captured BEFORE applying the treatment (rolling window). */
  baselineSamples: number[]
  /** Metric samples captured DURING the treatment. */
  treatmentSamples: number[]
  startedAt?: number
  concludedAt?: number
  turnsElapsed: number
  tStat?: number
  pValue?: number
  effectSize?: number
  appliedPermanently?: boolean
  notes?: string
}

export interface ExperimentConclusion {
  experiment: Experiment
  outcome: ExperimentOutcome
  deltaAbsolute: number
  deltaPercent: number
  pValue: number
  effectSize: number
  appliedPermanently: boolean
  summary: string
}


/** p-value threshold for statistical significance. */
const P_VALUE_THRESHOLD = 0.05
/** Minimum Cohen's d to consider an effect practically meaningful. */
const EFFECT_SIZE_THRESHOLD = 0.2
/** Maximum concurrent active experiments (to avoid confounding). */
const MAX_ACTIVE = 1


export class ExperimentEngine {
  private logger: ILogger
  private queue: Experiment[] = []
  private active: Experiment[] = []
  private concluded: Experiment[] = []

  constructor(
    logger: ILogger,
    private memory: IMemory,
    private eventBus: IEventBus,
  ) {
    this.logger = logger.child?.('experiment-engine') ?? logger
  }


  /** Enqueue a new experiment.  Deduplicates by KV key — only one experiment
   *  per parameter at a time. */
  enqueue(experiment: Omit<Experiment, 'status' | 'baselineSamples' | 'treatmentSamples' | 'turnsElapsed'>): void {
    const alreadyQueued = [...this.queue, ...this.active]
      .some(e => e.treatment.kvKey === experiment.treatment.kvKey)
    if (alreadyQueued) return

    this.queue.push({
      ...experiment,
      status: 'queued',
      baselineSamples: [],
      treatmentSamples: [],
      turnsElapsed: 0,
    })
    this.logger.info('ExperimentEngine: experiment queued', { id: experiment.id, title: experiment.title })
  }

  /**
   * Called every turn.  Feeds a new metric sample to all active experiments,
   * promotes queued experiments, and concludes experiments that have enough
   * data or have hit their turn cap.
   */
  async onTurn(metricSamples: Partial<Record<ExperimentMetric, number>>): Promise<ExperimentConclusion[]> {
    const conclusions: ExperimentConclusion[] = []

    // Feed samples to active experiments
    for (const exp of this.active) {
      exp.turnsElapsed++
      const sample = metricSamples[exp.metric]
      if (sample !== undefined) exp.treatmentSamples.push(sample)

      const hasEnough = exp.treatmentSamples.length >= exp.minSamples
      const hitCap    = exp.turnsElapsed >= exp.maxTurns

      if (hasEnough || hitCap) {
        const conclusion = await this.conclude(exp)
        conclusions.push(conclusion)
      }
    }

    // Remove concluded from active
    this.active = this.active.filter(e => e.status === 'active')

    // Promote queued experiments up to MAX_ACTIVE
    while (this.active.length < MAX_ACTIVE && this.queue.length > 0) {
      const next = this.queue.shift()!
      // Capture baseline before applying treatment
      const baseline = metricSamples[next.metric]
      if (baseline !== undefined) next.baselineSamples.push(baseline)
      await this.activate(next)
    }

    return conclusions
  }

  /** Append a baseline sample to queued experiments so we have a comparison window. */
  recordBaseline(metricSamples: Partial<Record<ExperimentMetric, number>>): void {
    for (const exp of this.queue) {
      const sample = metricSamples[exp.metric]
      if (sample !== undefined) {
        // Keep a rolling window of the last 30 baseline samples
        exp.baselineSamples.push(sample)
        if (exp.baselineSamples.length > 30) exp.baselineSamples.shift()
      }
    }
  }

  getActive(): Experiment[]   { return [...this.active]    }
  getQueue():  Experiment[]   { return [...this.queue]     }
  getConcluded(): Experiment[] { return [...this.concluded] }


  private async activate(exp: Experiment): Promise<void> {
    exp.status   = 'active'
    exp.startedAt = Date.now()
    exp.turnsElapsed = 0

    // Apply treatment to KV store
    try {
      await this.memory.kv_set(exp.treatment.kvKey, exp.treatment.treatmentValue)
      this.logger.info('ExperimentEngine: treatment applied', {
        id: exp.id, kvKey: exp.treatment.kvKey, value: exp.treatment.treatmentValue,
      })
    } catch (err) {
      this.logger.warn('ExperimentEngine: failed to apply treatment', { id: exp.id, error: String(err) })
    }

    // Notify the target module to hot-reload
    if (exp.treatment.reloadEvent) {
      try {
        ;(this.eventBus as any).emit?.({
          type: exp.treatment.reloadEvent,
          strategy: exp.treatment.treatmentValue,
          source: 'ai-scientist-experiment',
          experimentId: exp.id,
        })
      } catch {}
    }

    this.active.push(exp)
  }

  private async conclude(exp: Experiment): Promise<ExperimentConclusion> {
    exp.status       = 'concluded'
    exp.concludedAt  = Date.now()
    this.active      = this.active.filter(e => e !== exp)
    this.concluded.push(exp)

    const outcome = this.analyse(exp)
    exp.outcome             = outcome.outcome
    exp.pValue              = outcome.pValue
    exp.effectSize          = outcome.effectSize
    exp.appliedPermanently  = outcome.appliedPermanently

    if (!outcome.appliedPermanently) {
      // Revert to baseline
      try {
        await this.memory.kv_set(exp.treatment.kvKey, exp.treatment.baselineValue)
        if (exp.treatment.reloadEvent) {
          ;(this.eventBus as any).emit?.({
            type: exp.treatment.reloadEvent,
            strategy: exp.treatment.baselineValue,
            source: 'ai-scientist-revert',
            experimentId: exp.id,
          })
        }
      } catch (err) {
        this.logger.warn('ExperimentEngine: failed to revert treatment', { id: exp.id, error: String(err) })
      }
    }

    this.logger.info('ExperimentEngine: experiment concluded', {
      id: exp.id,
      outcome: outcome.outcome,
      pValue: outcome.pValue.toFixed(4),
      effectSize: outcome.effectSize.toFixed(3),
      applied: outcome.appliedPermanently,
      summary: outcome.summary,
    })

    return outcome
  }

  private analyse(exp: Experiment): ExperimentConclusion {
    const base = exp.baselineSamples
    const treat = exp.treatmentSamples
    const MIN_N = 3

    if (base.length < MIN_N || treat.length < MIN_N) {
      return this.buildConclusion(exp, 'insufficient_data', 0, 0, 1, 0, false,
        `Too few samples: baseline=${base.length} treatment=${treat.length}`)
    }

    let pValue: number
    let effectSize: number
    let deltaAbsolute: number
    let deltaPercent: number

    if (exp.metric === 'thinker_helpfulness') {
      // Binary metric: use Bayesian comparison
      const baseSuccesses  = base.reduce((s, x) => s + x, 0)
      const treatSuccesses = treat.reduce((s, x) => s + x, 0)
      const baseMean  = betaPosteriorMean(baseSuccesses, base.length)
      const treatMean = betaPosteriorMean(treatSuccesses, treat.length)
      deltaAbsolute = treatMean - baseMean
      deltaPercent  = baseMean > 0 ? (deltaAbsolute / baseMean) * 100 : 0
      // Use a proxy p-value from a z-test on proportions for simplicity
      const se = Math.sqrt(baseMean * (1 - baseMean) / base.length + treatMean * (1 - treatMean) / treat.length)
      const z = se > 0 ? Math.abs(deltaAbsolute / se) : 0
      pValue = z > 0 ? 2 * (1 - normalCDF(z)) : 1
      effectSize = cohensD(treat, base)
    } else {
      const tt = welchTTest(treat, base)
      pValue = tt.pValue
      effectSize = cohensD(treat, base)
      const baseMean  = describeStats(base).mean
      const treatMean = describeStats(treat).mean
      deltaAbsolute = treatMean - baseMean
      deltaPercent  = baseMean !== 0 ? (deltaAbsolute / Math.abs(baseMean)) * 100 : 0
    }

    exp.pValue     = pValue
    exp.effectSize = effectSize

    // For latency: improvement means delta < 0 (lower is better)
    const improvementDirection = exp.higherIsBetter ? deltaAbsolute > 0 : deltaAbsolute < 0
    const isSignificant   = pValue < P_VALUE_THRESHOLD
    const isPractical     = Math.abs(effectSize) >= EFFECT_SIZE_THRESHOLD

    let outcome: ExperimentOutcome
    if (isSignificant && isPractical && improvementDirection) {
      outcome = 'improvement'
    } else if (isSignificant && isPractical && !improvementDirection) {
      outcome = 'regression'
    } else {
      outcome = 'neutral'
    }

    const appliedPermanently = outcome === 'improvement'

    const direction = improvementDirection ? '↑' : '↓'
    const pct = Math.abs(deltaPercent).toFixed(1)
    const summary = `${direction} ${pct}% ${exp.metric.replace(/_/g, ' ')} | p=${pValue.toFixed(3)} | d=${effectSize.toFixed(2)} | ${outcome}`

    return this.buildConclusion(exp, outcome, deltaAbsolute, deltaPercent, pValue, effectSize, appliedPermanently, summary)
  }

  private buildConclusion(
    exp: Experiment,
    outcome: ExperimentOutcome,
    deltaAbsolute: number,
    deltaPercent: number,
    pValue: number,
    effectSize: number,
    appliedPermanently: boolean,
    summary: string,
  ): ExperimentConclusion {
    return { experiment: exp, outcome, deltaAbsolute, deltaPercent, pValue, effectSize, appliedPermanently, summary }
  }
}


/** Standard normal CDF (Abramowitz & Stegun approximation). */
/**
 * @dep callers: analyse (core/intelligence/ai-scientist/experiment-engine.ts)
 * @dep flows: OnTurnEnd → NormalCDF (5/5)
 * @dep module: Ai-scientist
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

function normalCDF(z: number): number {
  const t = 1 / (1 + 0.2316419 * z)
  const poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  return 1 - (1 / Math.sqrt(2 * Math.PI)) * Math.exp(-0.5 * z * z) * poly
}
