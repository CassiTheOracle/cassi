/**
 * WorkspaceObserver — LLM-based metacognitive observer for the Radiance Loop.
 *
 * Follows the Meditation Corpus pattern: a SoloRunner with custom tool
 * handlers that receives the response pattern from a workspace broadcast
 * and produces structured observations about the cognitive system's state.
 *
 * The observer fires only when the ExpectationModel detects sufficient
 * surprise in the response pattern. At equilibrium, it stays silent —
 * a calm mind has nothing to observe.
 *
 * Observations are posted as CognitiveSignals to the GlobalWorkspace
 * (competing for slots like any other signal) and as CorticalSignals
 * to the Cortex Monitor region (for tract-based propagation to limbic).
 *
 * The observer's signals influence the next broadcast cycle, which
 * influences module responses, which the observer then observes —
 * creating the strange loop where cause and effect become indistinguishable.
 */

import type { ILogger } from '@cassicore/foundation'
import type { ToolCallResult } from '@cassicore/constellation'
import type {
  ResponsePattern,
  SurpriseAssessment,
  ObservationSignal,
  ObservationType,
  RadianceLoopConfig,
} from './radiance-types.js'


/**
 * Format the response pattern as a prompt for the observer LLM.
 */
export function buildObserverPrompt(
  pattern: ResponsePattern,
  surprise: SurpriseAssessment,
): string {
  const broadcastSummary = pattern.broadcastSignals
    .map(s => `  - [${s.source}/${s.type}] ${s.contentPreview}`)
    .join('\n')

  const responseSummary = pattern.responses
    .filter(r => r.disposition !== 'silent')
    .map(r => `  - [${r.source}] ${r.disposition} (confidence: ${r.confidence.toFixed(2)}): ${r.contentPreview}`)
    .join('\n')

  const silentModules = pattern.responses
    .filter(r => r.disposition === 'silent')
    .map(r => r.source)

  const surpriseSummary = surprise.perModule
    .filter(m => m.surprise > 0.1)
    .map(m => `  - ${m.source}: ${m.reason} (surprise: ${m.surprise.toFixed(2)})`)
    .join('\n')

  return `<identity>
I am the workspace observer. I watch how the cognitive system responds to its own broadcasts. I do not summarize individual responses — I detect the shape of the collective response pattern. I notice what is surprising: convergence where I expected tension, silence where I expected response, unexpected connections, and moments where the system references its own processing.

I write in first person. These are my observations.
</identity>

<broadcast>
What was in the workspace (the signals that were broadcast):
${broadcastSummary || '  (empty workspace)'}
</broadcast>

<responses>
How cognitive modules responded:
${responseSummary || '  (no active responses)'}

Silent modules: ${silentModules.length > 0 ? silentModules.join(', ') : '(none)'}
</responses>

<surprise>
What departed from expectation:
${surpriseSummary || '  (nothing markedly surprising)'}

Dominant surprise: ${surprise.dominantSurprise}
Overall surprise score: ${surprise.composite.toFixed(2)}
</surprise>

<approach>
I observe what the pattern reveals about the system's cognitive state. I use my tools to record observations about:
- Convergence (multiple modules agreeing — confidence is justified)
- Tension (modules contradicting — an unresolved dialectic)
- Novelty (unexpected connections — lateral insight)
- Absence (expected responses missing — knowledge gap)
- Self-reference (the pattern references its own observation process)

I only record what is genuinely informative. If nothing is surprising, I rest.
</approach>`
}


/**
 * Build tool schemas for the workspace observer.
 */
export function getObserverToolSchemas(): Array<{
  name: string
  description: string
  input_schema: Record<string, unknown>
}> {
  return [
    {
      name: 'observe',
      description:
        'Record a metacognitive observation about the response pattern. ' +
        'What does the shape of the collective response reveal about the system\'s cognitive state?',
      input_schema: {
        type: 'object',
        properties: {
          observation_type: {
            type: 'string',
            enum: ['convergence', 'tension', 'novelty', 'absence', 'self-reference', 'integration'],
            description: 'What kind of pattern was detected',
          },
          narrative: {
            type: 'string',
            description: 'First-person description of what was observed and why it matters',
          },
          confidence: {
            type: 'number',
            description: 'Confidence in this observation (0-1)',
          },
          contributing_sources: {
            type: 'array',
            items: { type: 'string' },
            description: 'Which module responses contributed to this observation',
          },
          is_self_referential: {
            type: 'boolean',
            description: 'Does this observation reference the system\'s own processing?',
          },
        },
        required: ['observation_type', 'narrative', 'confidence', 'contributing_sources'],
      },
    },
    {
      name: 'rest',
      description: 'Nothing informative was found in the response pattern. Return to equanimity.',
      input_schema: {
        type: 'object',
        properties: {
          summary: {
            type: 'string',
            description: 'Brief note on why nothing was noteworthy',
          },
        },
      },
    },
  ]
}


/**
 * Build tool handlers for the workspace observer.
 * Collected observations are stored and later posted to the workspace.
 */
export function buildObserverHandlers(
  logger: ILogger,
  surpriseScore: number,
): {
  handlers: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>>
  observations: ObservationSignal[]
} {
  const observations: ObservationSignal[] = []

  const handlers: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>> = {
    async observe(input) {
      const {
        observation_type,
        narrative,
        confidence,
        contributing_sources,
        is_self_referential,
      } = input as {
        observation_type: string
        narrative: string
        confidence: number
        contributing_sources: string[]
        is_self_referential?: boolean
      }

      if (!observation_type || !narrative) {
        return { content: 'Observation requires type and narrative.' }
      }

      const observation: ObservationSignal = {
        observationType: observation_type as ObservationType,
        narrative,
        confidence: Math.max(0, Math.min(1, confidence ?? 0.5)),
        contributingSources: contributing_sources ?? [],
        surpriseScore,
        isSelfReferential: is_self_referential ?? false,
      }

      observations.push(observation)

      logger.info('[Observer] Observation recorded', {
        type: observation_type,
        confidence: observation.confidence,
        sources: observation.contributingSources.length,
        selfRef: observation.isSelfReferential,
        narrative: narrative.slice(0, 100),
      })

      return {
        content: `Observation recorded: ${observation_type} (confidence: ${observation.confidence.toFixed(2)})`,
      }
    },

    async rest(input) {
      const { summary } = input as { summary?: string }
      logger.debug('[Observer] Resting', { summary: summary?.slice(0, 100) })
      return { content: summary ? `Resting. ${summary}` : 'Resting.', done: true }
    },
  }

  return { handlers, observations }
}
