/**
 * Divergence Strategy — Detects when a branch's work pattern has diverged
 * from its siblings (e.g., doing analysis while siblings implement) and
 * sends a realignment directive.
 *
 * WHY: When siblings are spawned from the same parent goal, they should
 * be working in complementary patterns. If one branch drifts to a different
 * work type AND its score is declining, it's likely lost or stuck in an
 * unproductive loop. This strategy nudges it back toward its siblings'
 * pattern.
 *
 * Flow:
 *   assess-divergence → send-realignment-directive
 */

import { createWorkflow } from '../../../workflow/builder.js'
import { corpusAssessStep } from '../../../workflow/steps.js'
import type { ICorpusDirectiveSender, ICorpusStateReader } from '../../../workflow/steps.js'
import type { WorkflowDefinition, WorkflowStep } from '../../../../types/workflow.js'
import type {
  CorpusStrategy,
  StrategyContext,
  CrossHelixPattern,
  CorpusProcessedState,
} from '../corpus-types.js'


interface DivergenceAssessment {
  divergentBranch: { helixId: string; goal: string; score: number; currentPattern: string }
  siblingPattern: string
  siblingCount: number
}


function createDivergenceWorkflow(
  context: StrategyContext,
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): WorkflowDefinition {
  const { pattern } = context
  const divergentHelixId = pattern.helixIds[0]

  const assessStep = corpusAssessStep<DivergenceAssessment>({
    id: 'assess-divergence',
    description: `Assess divergence for ${divergentHelixId}`,
    reader,
    assess: (stateReader) => {
      const state = stateReader.getProcessedState()
      const tree = stateReader.getTree()

      const branch = tree.getBranch(divergentHelixId)
      const assessment = state.branchAssessments.get(divergentHelixId)

      // Extract patterns from the detection description
      const descMatch = pattern.description.match(/doing (\w+) while siblings do (\w+)/)
      const currentPattern = descMatch ? descMatch[1] : 'unknown'
      const siblingPattern = descMatch ? descMatch[2] : 'unknown'

      return {
        divergentBranch: {
          helixId: divergentHelixId,
          goal: branch?.goal ?? '(unknown)',
          score: assessment?.rollingScore ?? 0,
          currentPattern,
        },
        siblingPattern,
        siblingCount: pattern.helixIds.length - 1,
      }
    },
  })

  const sendRealignment: WorkflowStep = {
    id: 'send-realignment',
    description: 'Send realignment directive to divergent branch',
    timeoutMs: 30_000,
    execute: async (ctx) => {
      const assessment = ctx.input as DivergenceAssessment
      const { divergentBranch, siblingPattern, siblingCount } = assessment

      await sender.sendDirective({
        targetHelixId: divergentBranch.helixId,
        type: 'redirect',
        urgency: 'high',
        reason: `Divergence: ${divergentBranch.helixId} doing ${divergentBranch.currentPattern} while ${siblingCount} siblings do ${siblingPattern}`,
        text: [
          `DIVERGENCE DETECTED — Your work pattern (${divergentBranch.currentPattern}) differs from your sibling branches (${siblingPattern}).`,
          `Your score (${divergentBranch.score.toFixed(2)}) is declining, suggesting this approach is not productive.`,
          '',
          `ACTION REQUIRED: Realign with your siblings' ${siblingPattern} pattern.`,
          `- Stop any ${divergentBranch.currentPattern}-oriented work`,
          `- Focus on producing concrete ${siblingPattern} output`,
          '- If you need analysis first, keep it brief and transition to implementation quickly',
        ].join('\n'),
        fromPattern: 'divergence',
        requiredAction: 'switch_strategy',
      })

      ctx.logger.info('Realignment directive sent', {
        helixId: divergentBranch.helixId,
        from: divergentBranch.currentPattern,
        to: siblingPattern,
      })
    },
  }

  const builder = createWorkflow({
    id: `divergence-${divergentHelixId}`,
    description: `Realign divergent branch ${divergentHelixId}`,
  })

  builder
    .then(assessStep)
    .then(sendRealignment)

  return builder.commit()
}


export function createDivergenceStrategy(
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): CorpusStrategy {
  return {
    id: 'divergence',
    description: 'Realign branches whose work pattern diverges from siblings with declining scores',
    patternTypes: ['divergence'],
    priority: 7,

    matches(pattern: CrossHelixPattern, _state: CorpusProcessedState): boolean {
      return pattern.helixIds.length >= 2 && !pattern.actedUpon
    },

    createWorkflow(context: StrategyContext): WorkflowDefinition {
      return createDivergenceWorkflow(context, sender, reader)
    },
  }
}
