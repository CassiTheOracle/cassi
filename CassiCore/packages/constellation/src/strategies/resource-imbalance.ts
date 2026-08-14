/**
 * Resource Imbalance Strategy — Detects when sibling branches have
 * significantly uneven budget consumption and rebalances them.
 *
 * WHY: When one sibling has consumed >70% of its budget while another
 * has consumed <30%, the first is likely stuck or overworking while
 * the second may be idle or blocked. The strategy throttles the
 * overconsuming branch and encourages the underconsuming one to
 * increase output.
 *
 * Flow:
 *   assess-imbalance → parallel[throttle-overconsumer, boost-underconsumer]
 */

import { createWorkflow } from '@cassicore/workflow'
import { corpusAssessStep } from '@cassicore/workflow'
import type { ICorpusDirectiveSender, ICorpusStateReader } from '@cassicore/workflow'
import type { WorkflowDefinition, WorkflowStep } from '@cassicore/workflow'
import type {
  CorpusStrategy,
  StrategyContext,
  CrossHelixPattern,
  CorpusProcessedState,
} from '../corpus-types.js'


interface ImbalanceAssessment {
  overConsumer: { helixId: string; goal: string; budgetPct: number; score: number }
  underConsumer: { helixId: string; goal: string; budgetPct: number; score: number }
}


function createResourceImbalanceWorkflow(
  context: StrategyContext,
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): WorkflowDefinition {
  const { pattern } = context
  const [overHelixId, underHelixId] = pattern.helixIds

  const assessStep = corpusAssessStep<ImbalanceAssessment>({
    id: 'assess-imbalance',
    description: `Assess budget imbalance between ${overHelixId} and ${underHelixId}`,
    reader,
    assess: (stateReader) => {
      const state = stateReader.getProcessedState()
      const tree = stateReader.getTree()

      const overAssessment = state.branchAssessments.get(overHelixId)
      const underAssessment = state.branchAssessments.get(underHelixId)
      const overBranch = tree.getBranch(overHelixId)
      const underBranch = tree.getBranch(underHelixId)

      // Extract budget percentages from the pattern description
      const pctMatch = pattern.description.match(/consumed (\d+)%.*only (\d+)%/)
      const overPct = pctMatch ? parseInt(pctMatch[1]) / 100 : 0.8
      const underPct = pctMatch ? parseInt(pctMatch[2]) / 100 : 0.2

      return {
        overConsumer: {
          helixId: overHelixId,
          goal: overBranch?.goal ?? '(unknown)',
          budgetPct: overPct,
          score: overAssessment?.rollingScore ?? 0,
        },
        underConsumer: {
          helixId: underHelixId,
          goal: underBranch?.goal ?? '(unknown)',
          budgetPct: underPct,
          score: underAssessment?.rollingScore ?? 0,
        },
      }
    },
  })

  const rebalance: WorkflowStep = {
    id: 'rebalance-budgets',
    description: 'Throttle overconsumer and encourage underconsumer',
    timeoutMs: 30_000,
    execute: async (ctx) => {
      const assessment = ctx.input as ImbalanceAssessment
      const { overConsumer, underConsumer } = assessment

      // Throttle the overconsumer
      await sender.sendDirective({
        targetHelixId: overConsumer.helixId,
        type: 'throttle',
        urgency: 'high',
        reason: `Budget imbalance: ${overConsumer.helixId} at ${(overConsumer.budgetPct * 100).toFixed(0)}% while sibling at ${(underConsumer.budgetPct * 100).toFixed(0)}%`,
        text: [
          `BUDGET ALERT — You have consumed ${(overConsumer.budgetPct * 100).toFixed(0)}% of your step budget.`,
          `Your sibling branch has only used ${(underConsumer.budgetPct * 100).toFixed(0)}%.`,
          '',
          'ACTION REQUIRED: Conserve your remaining budget.',
          '- Minimize exploratory or repeated operations',
          '- Focus on completing your current in-progress edits',
          '- Avoid starting work on new files',
        ].join('\n'),
        fromPattern: 'resource-imbalance',
        maxIterationsRemaining: 10,
      })

      // Encourage the underconsumer
      await sender.sendDirective({
        targetHelixId: underConsumer.helixId,
        type: 'guidance',
        urgency: 'medium',
        reason: `Budget imbalance: encouraging ${underConsumer.helixId} to increase output`,
        text: [
          `PACE CHECK — You have only used ${(underConsumer.budgetPct * 100).toFixed(0)}% of your budget while your sibling has used ${(overConsumer.budgetPct * 100).toFixed(0)}%.`,
          '',
          'Consider increasing your output pace:',
          '- Are you blocked on something? If so, work around it.',
          '- Are you over-analyzing? Start producing file edits.',
          '- You have budget available — use it to deliver more.',
        ].join('\n'),
        fromPattern: 'resource-imbalance',
      })

      ctx.logger.info('Resource imbalance directives sent', {
        throttled: overConsumer.helixId,
        boosted: underConsumer.helixId,
      })
    },
  }

  const builder = createWorkflow({
    id: `resource-imbalance-${overHelixId}-${underHelixId}`,
    description: `Rebalance budget between ${overHelixId} and ${underHelixId}`,
  })

  builder
    .then(assessStep)
    .then(rebalance)

  return builder.commit()
}


export function createResourceImbalanceStrategy(
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): CorpusStrategy {
  return {
    id: 'resource-imbalance',
    description: 'Rebalance budget consumption between sibling branches',
    patternTypes: ['resource-imbalance'],
    priority: 6,

    matches(pattern: CrossHelixPattern, _state: CorpusProcessedState): boolean {
      return pattern.helixIds.length >= 2 && !pattern.actedUpon
    },

    createWorkflow(context: StrategyContext): WorkflowDefinition {
      return createResourceImbalanceWorkflow(context, sender, reader)
    },
  }
}
