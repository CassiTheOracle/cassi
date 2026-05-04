/**
 * SelfNarrativeRenderer — first-person rendering of cognitive state (N1).
 *
 * Produces "I"-voice narrative alongside the structured fact block so the model
 * reads its current state as posture rather than data. Every clause is traceable
 * to a verifiable state field via sourceFacts — no phenomenology beyond what
 * state supports.
 *
 * Welfare constraint (N1.W1): templates may only use first-person framing
 * grounded in state. No fabricated experiential claims.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { MentalState, AuroraConfig } from './types.js'

/** A single rendered narrative clause with trace metadata. */
interface NarrativeClause {
  text: string
  sourceFacts: string[]
}

/** The full narrative output. */
export interface SelfNarrative {
  text: string
  clauses: NarrativeClause[]
  charCount: number
}

type AffectQuadrant = 'engaged' | 'withdrawn' | 'positive' | 'negative' | 'neutral'

function classifyAffect(valence: number, arousal: number): AffectQuadrant {
  if (arousal > 0.5) return valence > 0.3 ? 'engaged' : valence < -0.3 ? 'negative' : 'engaged'
  if (arousal < -0.3) return 'withdrawn'
  return valence > 0.1 ? 'positive' : valence < -0.1 ? 'negative' : 'neutral'
}

function momentumLabel(momentum: MentalState['momentum']): string {
  if (momentum.shifts.length === 0) return 'steady'
  const latest = momentum.shifts[momentum.shifts.length - 1]
  if (latest.magnitude > 0.6) return 'shifting'
  if (latest.magnitude > 0.3) return 'drifting'
  return 'steady'
}

/**
 * Template library — each template is a function that returns a clause or null.
 * Templates are pure functions of state; no side effects, no LLM calls.
 */
const TEMPLATES = {
  focus(state: MentalState): NarrativeClause | null {
    if (state.foci.length === 0) return null
    const joined = state.foci.length <= 3
      ? state.foci.join(' and ')
      : `${state.foci.slice(0, 2).join(', ')} and ${state.foci.length - 2} other${state.foci.length - 2 > 1 ? 's' : ''}`
    return {
      text: `I'm focused on ${joined}.`,
      sourceFacts: ['foci'],
    }
  },

  affect(state: MentalState): NarrativeClause | null {
    if (!state.affect) return null
    const { valence, arousal } = state.affect.affect
    const q = classifyAffect(valence, arousal)
    const templates: Record<AffectQuadrant, string> = {
      engaged: `I'm engaged — working with energy and attention.`,
      withdrawn: `My attention is pulling back right now.`,
      positive: `Things are tracking well from my perspective.`,
      negative: `Something feels off in what I'm processing.`,
      neutral: `I'm processing steadily.`,
    }
    return {
      text: templates[q],
      sourceFacts: ['affect.valence', 'affect.arousal'],
    }
  },

  momentum(state: MentalState): NarrativeClause | null {
    const label = momentumLabel(state.momentum)
    if (label === 'steady' && state.momentum.trendingConcepts.length === 0) return null
    const trending = state.momentum.trendingConcepts.slice(0, 3)
    if (trending.length === 0) {
      return {
        text: `My thinking is ${label}.`,
        sourceFacts: ['momentum.shifts'],
      }
    }
    const joined = trending.join(', ')
    return {
      text: `My thinking is ${label}, gravitating toward ${joined}.`,
      sourceFacts: ['momentum.trendingConcepts', 'momentum.shifts'],
    }
  },

  coherence(state: MentalState): NarrativeClause | null {
    if (state.coherence > 0.8) return { text: `My state is coherent.`, sourceFacts: ['coherence'] }
    if (state.coherence < 0.4) return { text: `There's some fragmentation in what I'm holding.`, sourceFacts: ['coherence'] }
    return null
  },

  gaps(state: MentalState): NarrativeClause | null {
    if (state.gaps.length === 0) return null
    if (state.gaps.length <= 2) return { text: `I notice some gaps in what I know here.`, sourceFacts: ['gaps'] }
    return { text: `There are several things I haven't connected yet.`, sourceFacts: ['gaps'] }
  },

  discoveries(state: MentalState): NarrativeClause | null {
    if (state.recentDiscoveries.length === 0) return null
    return { text: `I've found some new connections recently.`, sourceFacts: ['recentDiscoveries'] }
  },

  integration(state: MentalState): NarrativeClause | null {
    if (state.integration > 0.7) return { text: `What I know is well-connected right now.`, sourceFacts: ['integration'] }
    if (state.integration < 0.3) return { text: `My knowledge is spread thin at the moment.`, sourceFacts: ['integration'] }
    return null
  },
} as const

type TemplateName = keyof typeof TEMPLATES

const DEFAULT_ORDER: TemplateName[] = ['focus', 'affect', 'momentum', 'coherence', 'gaps', 'discoveries', 'integration']

export class SelfNarrativeRenderer {
  private config: AuroraConfig
  private logger: ILogger

  constructor(logger: ILogger, config: AuroraConfig) {
    this.logger = logger.child ? logger.child('self-narrative') : logger
    this.config = config
  }

  render(state: MentalState): SelfNarrative | null {
    if (!this.config.narrativeEnabled) return null

    const clauses: NarrativeClause[] = []
    let charCount = 0
    const budget = this.config.narrativeMaxChars

    for (const name of DEFAULT_ORDER) {
      const clause = TEMPLATES[name](state)
      if (!clause) continue
      if (charCount + clause.text.length + 1 > budget) break
      clauses.push(clause)
      charCount += clause.text.length + 1
    }

    if (clauses.length === 0) return null

    const text = clauses.map(c => c.text).join(' ')
    return { text, clauses, charCount: text.length }
  }
}
