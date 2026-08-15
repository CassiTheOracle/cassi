/**
 * ExpectationModel — Learned baseline for surprise detection.
 *
 * Maintains a Bayesian model of how each cognitive module typically responds
 * to workspace broadcasts. After each radiance cycle, the model updates its
 * expectations. Surprise is the deviation between expected and actual behavior.
 *
 * The model learns:
 *   - How often each module responds (vs. staying silent)
 *   - The typical disposition (convergent, divergent, lateral) when it does respond
 *   - Which signal types each module tends to respond to
 *
 * A module responding when it normally doesn't is surprising.
 * A module staying silent when it normally responds is surprising.
 * High convergence on a topic that usually produces tension is surprising.
 *
 * The expectation model IS the representation of equanimity: when
 * expectations match reality, the observer stays silent — a calm mind.
 */

import type {
  ResponsePattern,
  ResponseDisposition,
  ModuleExpectation,
  SurpriseAssessment,
} from './radiance-types.js'
import type { SignalType } from './cognitive-signal.js'


/**
 * How strongly different kinds of surprise contribute to the composite score.
 * Response/silence mismatch is weighted highest because it's the most
 * reliable signal of changed cognitive behavior.
 */
const SURPRISE_WEIGHT_RESPONSE_MISMATCH = 0.7
const SURPRISE_WEIGHT_DISPOSITION_MISMATCH = 0.5
const SURPRISE_SCORE_UNKNOWN_MODULE = 0.3


/**
 * Category of surprise detected for a module.
 * Used by determineDominantSurprise instead of fragile string matching.
 */
type SurpriseCategory = 'response-mismatch' | 'disposition-mismatch' | 'unknown-module' | 'expected'


export class ExpectationModel {
  private expectations = new Map<string, ModuleExpectation>()
  private cycleCount = 0
  private warmupCycles: number
  private learningRate: number

  constructor(warmupCycles = 10, learningRate = 0.1) {
    this.warmupCycles = warmupCycles
    this.learningRate = learningRate
  }


  /**
   * Assess surprise in a ResponsePattern by comparing against learned expectations.
   */
  assess(pattern: ResponsePattern): SurpriseAssessment {
    if (this.cycleCount < this.warmupCycles) {
      return {
        composite: 0,
        perModule: [],
        shouldObserve: false,
        dominantSurprise: 'none',
      }
    }

    const perModule: SurpriseAssessment['perModule'] = []
    let totalSurprise = 0

    const categories: SurpriseCategory[] = []

    for (const response of pattern.responses) {
      const expected = this.expectations.get(response.source)
      if (!expected) {
        perModule.push({ source: response.source, surprise: SURPRISE_SCORE_UNKNOWN_MODULE, reason: 'unknown module' })
        categories.push('unknown-module')
        totalSurprise += SURPRISE_SCORE_UNKNOWN_MODULE
        continue
      }

      const surprise = this.computeModuleSurprise(response, expected)
      perModule.push(surprise)
      categories.push(surprise.category)
      totalSurprise += surprise.surprise
    }

    // Check for expected modules that didn't appear at all
    for (const [source, expected] of this.expectations) {
      if (expected.responseRate > 0.5 && !pattern.responses.some(r => r.source === source)) {
        const silence = { source, surprise: expected.responseRate * SURPRISE_WEIGHT_RESPONSE_MISMATCH, reason: 'expected response missing' }
        perModule.push(silence)
        categories.push('response-mismatch')
        totalSurprise += silence.surprise
      }
    }

    const moduleCount = Math.max(1, perModule.length)
    const composite = Math.min(1, totalSurprise / moduleCount)

    const dominantSurprise = this.determineDominantSurprise(pattern, categories)

    return {
      composite,
      perModule: perModule.sort((a, b) => b.surprise - a.surprise),
      shouldObserve: composite > 0,
      dominantSurprise,
    }
  }


  /**
   * Update expectations after observing a response cycle.
   * Bayesian update: new_rate = old_rate * (1 - lr) + observed * lr
   */
  update(pattern: ResponsePattern): void {
    this.cycleCount++

    const broadcastTypes = new Set(pattern.broadcastSignals.map(s => s.type))

    for (const response of pattern.responses) {
      let exp = this.expectations.get(response.source)
      if (!exp) {
        exp = this.createInitialExpectation(response.source)
        this.expectations.set(response.source, exp)
      }

      const didRespond = response.disposition !== 'silent'
      const lr = this.learningRate

      // Update response rate
      exp.responseRate = exp.responseRate * (1 - lr) + (didRespond ? 1 : 0) * lr

      // Update disposition rates
      if (didRespond) {
        for (const disp of ['convergent', 'divergent', 'lateral', 'silent'] as ResponseDisposition[]) {
          const observed = response.disposition === disp ? 1 : 0
          exp.dispositionRates[disp] = (exp.dispositionRates[disp] ?? 0) * (1 - lr) + observed * lr
        }
      }

      // Update responded-to-types
      if (didRespond) {
        for (const signalType of broadcastTypes) {
          const current = exp.respondedToTypes[signalType] ?? 0
          exp.respondedToTypes[signalType] = current * (1 - lr) + 1 * lr
        }
      }

      exp.observationCount++
    }
  }


  /**
   * Get the current expectation for a module.
   */
  getExpectation(source: string): ModuleExpectation | undefined {
    return this.expectations.get(source)
  }

  /**
   * Get all learned expectations.
   */
  getAllExpectations(): ModuleExpectation[] {
    return [...this.expectations.values()]
  }

  /**
   * How many cycles have been observed.
   */
  getCycleCount(): number {
    return this.cycleCount
  }

  /**
   * Whether the model has completed warmup and can reliably score surprise.
   */
  isWarmedUp(): boolean {
    return this.cycleCount >= this.warmupCycles
  }


  private computeModuleSurprise(
    response: ResponsePattern['responses'][number],
    expected: ModuleExpectation,
  ): SurpriseAssessment['perModule'][number] & { category: SurpriseCategory } {
    const didRespond = response.disposition !== 'silent'

    const expectedRespond = expected.responseRate > 0.5
    if (didRespond !== expectedRespond) {
      const magnitude = Math.abs(expected.responseRate - (didRespond ? 1 : 0))
      const reason = didRespond
        ? `unexpected response (expected rate: ${expected.responseRate.toFixed(2)})`
        : `unexpected silence (expected rate: ${expected.responseRate.toFixed(2)})`
      return {
        source: response.source,
        surprise: magnitude * SURPRISE_WEIGHT_RESPONSE_MISMATCH,
        reason,
        category: 'response-mismatch',
      }
    }

    if (!didRespond) {
      return { source: response.source, surprise: 0, reason: 'expected silence', category: 'expected' }
    }

    const expectedDisp = this.getMostLikelyDisposition(expected)
    if (response.disposition !== expectedDisp) {
      const expectedRate = expected.dispositionRates[response.disposition] ?? 0
      const surprise = 1 - expectedRate
      return {
        source: response.source,
        surprise: surprise * SURPRISE_WEIGHT_DISPOSITION_MISMATCH,
        reason: `unexpected disposition: ${response.disposition} (expected: ${expectedDisp})`,
        category: 'disposition-mismatch',
      }
    }

    return { source: response.source, surprise: 0, reason: 'matches expectation', category: 'expected' }
  }


  private getMostLikelyDisposition(exp: ModuleExpectation): ResponseDisposition {
    let best: ResponseDisposition = 'convergent'
    let bestRate = 0
    for (const [disp, rate] of Object.entries(exp.dispositionRates)) {
      if (rate > bestRate) {
        bestRate = rate
        best = disp as ResponseDisposition
      }
    }
    return best
  }


  private determineDominantSurprise(
    pattern: ResponsePattern,
    categories: SurpriseCategory[],
  ): SurpriseAssessment['dominantSurprise'] {
    const nonExpected = categories.filter(c => c !== 'expected')
    if (nonExpected.length === 0) {
      return 'none'
    }

    // Check pattern-level disposition counts for the strongest signal
    if (pattern.divergentCount > pattern.convergentCount && pattern.divergentCount > pattern.lateralCount) {
      return 'divergence'
    }
    if (pattern.lateralCount > pattern.convergentCount) {
      return 'lateral'
    }
    if (pattern.convergentCount > 0) {
      return 'convergence'
    }

    // Fall back to category-based detection
    const hasResponseMismatch = nonExpected.includes('response-mismatch')
    if (hasResponseMismatch) {
      return 'silence'
    }

    return 'mixed'
  }


  private createInitialExpectation(source: string): ModuleExpectation {
    return {
      source,
      responseRate: 0.5,
      dispositionRates: {
        convergent: 0.4,
        divergent: 0.2,
        lateral: 0.1,
        silent: 0.3,
      },
      respondedToTypes: {},
      observationCount: 0,
    }
  }


  /**
   * Reset the model to initial state.
   */
  reset(): void {
    this.expectations.clear()
    this.cycleCount = 0
  }
}
