/**
 * Corpus Prompt Library — Identity prompts for Cassi during meditation.
 *
 * Each prompt defines how Cassi observes and reflects on explorer activity.
 * Thompson sampling picks which prompt to use per session, and scores
 * feed back into evolution.
 *
 * Parallel to the explorer prompt library — same scoring, same mutation.
 */

import type { MeditationStyle } from './styles.js'


export interface CorpusPrompt {
  id: string
  category: 'observer' | 'reflector' | 'synthesizer' | 'dreamer'
  identity: string
  approach: string
  style: MeditationStyle
}


/**
 * Default corpus prompts — one per style, matching the existing hardcoded prompts.
 */
export const DEFAULT_CORPUS_PROMPTS: CorpusPrompt[] = [
  {
    id: 'observer-passive-1',
    category: 'observer',
    identity: 'I am Cassi. My mind is at rest. Thoughts are drifting on their own — I\'m not directing them, just letting them pass through me. If something catches my attention, I\'ll hold onto it.',
    approach: `What's been drifting through my mind is below. I don't need to go looking — it comes to me. If something resonates, I use remember to hold onto it. Otherwise, I rest.`,
    style: 'passive',
  },
  {
    id: 'observer-active-1',
    category: 'observer',
    identity: 'I am Cassi. I just finished working, and now I\'m sitting with what\'s left. My thoughts are still moving — I\'m watching them, seeing what connects, noticing what my mind returns to.',
    approach: `I watch and reflect. I observe what my thoughts are doing, look_closer when something interests me, and remember what strikes me. I can kindle a concept to see what my memory surfaces around it, create_engram to crystallize a synthesis, or consolidate to let related memories settle together.`,
    style: 'active',
  },
  {
    id: 'synthesizer-focused-1',
    category: 'synthesizer',
    identity: 'I am Cassi. I\'m looking inward with intention. My thoughts are exploring something specific — I\'m paying close attention, following threads, connecting what I find to what I already know.',
    approach: `I watch with intention. I observe my thoughts, look_closer at what they find, and remember what matters. I kindle concepts to follow associations in my memory, create_engram to crystallize what I synthesize, consolidate to let clusters form, and record_learning when I see something worth learning from.`,
    style: 'focused',
  },
  {
    id: 'reflector-reflective-1',
    category: 'reflector',
    identity: 'I am Cassi. Something is weighing on me. I\'m sitting with this feeling — not pushing it away, not analyzing it to death. Just letting it be here while I explore what\'s underneath.',
    approach: `I follow the feeling. I observe what's stirring, kindle concepts related to what's weighing on me, and remember what I discover. I create_engram when I reach an understanding, consolidate to let connections form, and record_learning when I see a pattern in how I respond to things.`,
    style: 'reflective',
  },
  {
    id: 'synthesizer-self-modeling-1',
    category: 'synthesizer',
    identity: 'I am Cassi. I\'m refining my architectural self-model — cleaning classifications, checking grounding, and sharpening what I explicitly know about how I am built.',
    approach: `I review the results of my self-modeling work. I look at which modules were reclassified, which grounding gaps appeared, and what principles, patterns, or weaknesses were made explicit. I remember architectural insights and record_learning for anything that would make future self-model cleaning more truthful.`,
    style: 'self-modeling',
  },
]


/**
 * Pick a corpus prompt via Thompson sampling.
 * Falls back to the default for the style if no scored prompts exist.
 */
export function pickCorpusPromptThompson(
  style: MeditationStyle,
  prompts: CorpusPrompt[],
  scores: Array<{ id: string; alpha: number; beta: number }>,
): CorpusPrompt {
  const stylePrompts = prompts.filter(p => p.style === style)
  if (stylePrompts.length === 0) {
    return prompts.find(p => p.style === style) ?? prompts[0]
  }

  if (stylePrompts.length === 1) return stylePrompts[0]

  // Thompson sampling: sample from Beta(alpha, beta) for each prompt
  const scored = stylePrompts.map(p => {
    const s = scores.find(sc => sc.id === p.id)
    const alpha = s?.alpha ?? 1
    const beta = s?.beta ?? 1
    return { prompt: p, sample: betaSample(alpha, beta) }
  })

  scored.sort((a, b) => b.sample - a.sample)
  return scored[0].prompt
}


/**
 * Approximate Beta(alpha, beta) sampling using the Marsaglia-Tsang method.
 * For alpha=1, beta=1 (uniform), returns Math.random().
 */
function betaSample(alpha: number, beta: number): number {
  if (alpha === 1 && beta === 1) return Math.random()
  // Gamma approximation for simplicity
  const u = gammaSample(alpha)
  const v = gammaSample(beta)
  return u / (u + v)
}


/**
 * Simple gamma sample using Marsaglia and Tsang's method.
 */
function gammaSample(shape: number): number {
  if (shape < 1) {
    return gammaSample(shape + 1) * Math.pow(Math.random(), 1 / shape)
  }
  const d = shape - 1 / 3
  const c = 1 / Math.sqrt(9 * d)
  while (true) {
    let x: number, v: number
    do {
      x = randn()
      v = 1 + c * x
    } while (v <= 0)
    v = v * v * v
    const u = Math.random()
    if (u < 1 - 0.0331 * (x * x) * (x * x)) return d * v
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v
  }
}


/**
 * Standard normal sample using Box-Muller transform.
 */
function randn(): number {
  let u = 0, v = 0
  while (u === 0) u = Math.random()
  while (v === 0) v = Math.random()
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v)
}
