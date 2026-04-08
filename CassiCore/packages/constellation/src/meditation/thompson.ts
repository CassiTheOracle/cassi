/**
 * Thompson Sampling for Meditation Prompts
 *
 * Each prompt has alpha/beta parameters modeling a Beta distribution.
 * To select a prompt:
 *   1. Sample from Beta(alpha, beta) for each eligible prompt
 *   2. Pick the prompt with the highest sample
 *
 * This naturally balances exploration vs exploitation:
 *   - New prompts (alpha=1, beta=1) have high variance → explored often
 *   - Well-tested good prompts converge to high expected value
 *   - Well-tested bad prompts converge to low expected value
 *
 * Multiple explorers in the same session get different prompts (no repeats).
 */

import type { MeditationPrompt } from './types.js'
import type { MeditationStyle } from './styles.js'
import { STYLE_CONFIGS } from './styles.js'
import type { MeditationStore } from './meditation-store.js'


/**
 * Sample from a Gamma distribution using Marsaglia and Tsang's method.
 * For shape >= 1; uses Ahrens-Dieter transformation for shape < 1.
 */
function sampleGamma(shape: number): number {
  if (shape < 1) {
    // Ahrens-Dieter: Gamma(shape) = Gamma(shape+1) * U^(1/shape)
    return sampleGamma(shape + 1) * Math.pow(Math.random(), 1 / shape)
  }

  // Marsaglia and Tsang's method for shape >= 1
  const d = shape - 1 / 3
  const c = 1 / Math.sqrt(9 * d)

  for (;;) {
    let x: number
    let v: number

    do {
      // Box-Muller for standard normal
      x = Math.sqrt(-2 * Math.log(Math.random())) * Math.cos(2 * Math.PI * Math.random())
      v = 1 + c * x
    } while (v <= 0)

    v = v * v * v
    const u = Math.random()

    if (u < 1 - 0.0331 * x * x * x * x) return d * v
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v
  }
}


/**
 * Sample from Beta(alpha, beta) using the Gamma transform method.
 * X ~ Gamma(alpha, 1), Y ~ Gamma(beta, 1) → X/(X+Y) ~ Beta(alpha, beta)
 */
export function sampleBeta(alpha: number, beta: number): number {
  if (alpha <= 0 || beta <= 0) return 0.5

  const x = sampleGamma(alpha)
  const y = sampleGamma(beta)

  if (x + y === 0) return 0.5
  return x / (x + y)
}


/**
 * Pick prompts for a meditation session using Thompson sampling.
 *
 * When a store is available, samples from each prompt's Beta distribution
 * and picks the highest. Falls back to the static library if the store
 * is empty or unavailable.
 */
export function pickPromptsThompson(
  explorerCount: number,
  store: MeditationStore,
  style: MeditationStyle,
  fallbackPrompts: MeditationPrompt[],
): MeditationPrompt[] {
  // Use style-specific params when available — same prompt may perform differently per style
  const params = store.getStyleThompsonParams(style)
  if (params.length === 0) {
    return pickFallback(explorerCount, fallbackPrompts)
  }

  // Filter by style category preferences
  const prefs = STYLE_CONFIGS[style].categoryPreferences
  let eligible = prefs.length > 0
    ? params.filter(p => prefs.includes(p.category as MeditationPrompt['category']))
    : params

  // Fall back to all if style filtering leaves too few
  if (eligible.length < explorerCount) {
    eligible = params
  }

  // Sample and rank
  const sampled = eligible.map(p => ({
    id: p.id,
    theta: sampleBeta(p.alpha, p.beta),
  }))
  sampled.sort((a, b) => b.theta - a.theta)

  // Pick top-N (no repeats)
  const picked: MeditationPrompt[] = []
  for (let i = 0; i < explorerCount && i < sampled.length; i++) {
    const match = fallbackPrompts.find(p => p.id === sampled[i].id)
    if (match) {
      picked.push(match)
    }
  }

  // Fill any remaining with unique fallbacks where possible
  if (picked.length < explorerCount) {
    const pickedIds = new Set(picked.map(p => p.id))
    const remaining = fallbackPrompts.filter(p => !pickedIds.has(p.id))
    for (let i = 0; picked.length < explorerCount; i++) {
      const pool = remaining.length > 0 ? remaining : fallbackPrompts
      picked.push(pool[i % pool.length])
    }
  }

  return picked
}


function pickFallback(count: number, prompts: MeditationPrompt[]): MeditationPrompt[] {
  const result: MeditationPrompt[] = []
  for (let i = 0; i < count; i++) {
    result.push(prompts[i % prompts.length])
  }
  return result
}
