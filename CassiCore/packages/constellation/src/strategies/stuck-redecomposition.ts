/**
 * Stuck Redecomposition Strategy — Handles asymmetric-progress patterns
 * where a branch is stuck while peers are making progress.
 *
 * WHY: The inline escalation system uses a fixed 3-level approach
 * (guidance → redirect → cancel). This strategy adds intelligence:
 * it reads the branch's actual progress, budget consumption, and peer
 * performance to decide between narrowing scope and requesting
 * re-decomposition of the stuck branch's goal into smaller sub-tasks.
 *
 * Flow:
 *   assess-stuck-branch → decide-action → [narrow-scope OR request-redecompose]
 *
 * Decision logic:
 *   - If budget < 50% consumed AND score > 0.3: narrow scope (recoverable)
 *   - If budget >= 50% consumed OR score <= 0.3: request re-decomposition
 *
 * Re-decomposition requests are posted as a structured result that the
 * Corpus's main loop can pick up and act on during its next sweep.
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


interface StuckAssessment {
  stuckBranch: {
    helixId: string
    goal: string
    score: number
    budgetConsumedPct: number
    filesModified: number
  }
  bestPeer: {
    helixId: string
    score: number
    filesModified: number
  } | null
  action: 'narrow-scope' | 'redecompose'
  reason: string
}

interface RedecompositionResult {
  type: 'narrow-scope' | 'redecompose'
  stuckHelixId: string
  goal: string
  reason: string
}


function createStuckRedecompositionWorkflow(
  context: StrategyContext,
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): WorkflowDefinition {
  const { pattern } = context

  // Find the stuck branch: the one with the lowest score among pattern branches
  const stuckHelixId = pattern.helixIds[0]

  const assessStep = corpusAssessStep<StuckAssessment>({
    id: 'assess-stuck',
    description: `Assess stuck branch ${stuckHelixId} for redecomposition`,
    reader,
    assess: (stateReader) => {
      const state = stateReader.getProcessedState()
      const tree = stateReader.getTree()

      // Find the stuck branch (lowest score)
      let worstScore = Infinity
      let stuckId = stuckHelixId
      let bestPeerId: string | null = null
      let bestPeerScore = -1

      for (const helixId of pattern.helixIds) {
        const assessment = state.branchAssessments.get(helixId)
        if (!assessment) continue
        const score = assessment.rollingScore

        if (score < worstScore) {
          worstScore = score
          stuckId = helixId
        }
        if (score > bestPeerScore) {
          bestPeerScore = score
          bestPeerId = helixId
        }
      }

      const stuckAssessment = state.branchAssessments.get(stuckId)
      const stuckBranchData = tree.getBranch(stuckId)
      const budget = state.budgets.get(stuckId)

      const score = stuckAssessment?.rollingScore ?? 0
      const filesModified = stuckAssessment?.filesModified?.size ?? 0
      const budgetConsumedPct = budget
        ? (budget.consumedSteps / Math.max(budget.maxSteps, 1))
        : 0

      // Decision: narrow scope vs redecompose
      const shouldRedecompose = budgetConsumedPct >= 0.5 || score <= 0.3
      const action = shouldRedecompose ? 'redecompose' as const : 'narrow-scope' as const

      const reason = shouldRedecompose
        ? `Branch ${stuckId} has consumed ${(budgetConsumedPct * 100).toFixed(0)}% of budget with score ${score.toFixed(2)} — goal should be split into sub-tasks`
        : `Branch ${stuckId} has score ${score.toFixed(2)} but budget is only ${(budgetConsumedPct * 100).toFixed(0)}% consumed — narrowing scope may recover it`

      context.logger.info('Stuck branch assessed', {
        stuckId,
        score,
        budgetConsumedPct: budgetConsumedPct.toFixed(2),
        action,
        filesModified,
      })

      const bestPeer = bestPeerId && bestPeerId !== stuckId
        ? {
            helixId: bestPeerId,
            score: bestPeerScore,
            filesModified: state.branchAssessments.get(bestPeerId)?.filesModified?.size ?? 0,
          }
        : null

      return {
        stuckBranch: {
          helixId: stuckId,
          goal: stuckBranchData?.goal ?? '(unknown)',
          score,
          budgetConsumedPct,
          filesModified,
        },
        bestPeer,
        action,
        reason,
      }
    },
  })

  const actOnAssessment: WorkflowStep = {
    id: 'act-on-stuck',
    description: 'Send directive to stuck branch based on assessment',
    timeoutMs: 30_000,
    execute: async (ctx) => {
      const assessment = ctx.input as StuckAssessment
      const { stuckBranch, action, bestPeer } = assessment

      if (action === 'narrow-scope') {
        await sender.sendDirective({
          targetHelixId: stuckBranch.helixId,
          type: 'redirect',
          urgency: 'high',
          reason: assessment.reason,
          text: [
            'PROGRESS ALERT — Your progress is significantly behind peer branches.',
            '',
            bestPeer
              ? `Your peer "${bestPeer.helixId}" has score ${bestPeer.score.toFixed(2)} and modified ${bestPeer.filesModified} files.`
              : 'Other branches are progressing faster.',
            `Your score: ${stuckBranch.score.toFixed(2)}, files modified: ${stuckBranch.filesModified}`,
            '',
            'ACTION REQUIRED: Narrow your scope immediately.',
            '- Focus on the single most impactful deliverable',
            '- Skip any exploratory or analysis work',
            '- Produce concrete output (file edits) in the next few iterations',
          ].join('\n'),
          fromPattern: 'asymmetric-progress',
          requiredAction: 'narrow_scope',
        })
      } else {
        // Redecompose: tell the branch to conclude immediately
        await sender.sendDirective({
          targetHelixId: stuckBranch.helixId,
          type: 'redirect',
          urgency: 'critical',
          reason: assessment.reason,
          text: [
            'REDECOMPOSITION — Your goal is being split into smaller sub-tasks.',
            '',
            `You have consumed ${(stuckBranch.budgetConsumedPct * 100).toFixed(0)}% of your budget with score ${stuckBranch.score.toFixed(2)}.`,
            'New branches will be spawned with narrower goals.',
            '',
            'ACTION REQUIRED: Conclude immediately.',
            '- Save any partial work you have',
            '- Summarize what you attempted and what blocked you',
            '- Produce output for whatever you have completed',
          ].join('\n'),
          fromPattern: 'asymmetric-progress',
          maxIterationsRemaining: 3,
          requiredAction: 'conclude',
        })
      }

      // Return a result that the Corpus can use
      const result: RedecompositionResult = {
        type: action,
        stuckHelixId: stuckBranch.helixId,
        goal: stuckBranch.goal,
        reason: assessment.reason,
      }

      ctx.logger.info('Stuck branch action taken', {
        action,
        helixId: stuckBranch.helixId,
        goal: stuckBranch.goal.slice(0, 80),
      })

      return result
    },
  }

  const builder = createWorkflow({
    id: `stuck-redecompose-${stuckHelixId}`,
    description: `Handle stuck branch ${stuckHelixId}: assess and narrow/redecompose`,
  })

  builder
    .then(assessStep)
    .then(actOnAssessment)

  return builder.commit()
}


export function createStuckRedecompositionStrategy(
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): CorpusStrategy {
  return {
    id: 'stuck-redecomposition',
    description: 'Handle stuck branches by narrowing scope or requesting re-decomposition',
    patternTypes: ['asymmetric-progress'],
    priority: 10,

    matches(pattern: CrossHelixPattern, _state: CorpusProcessedState): boolean {
      return pattern.helixIds.length >= 1 && !pattern.actedUpon
    },

    createWorkflow(context: StrategyContext): WorkflowDefinition {
      return createStuckRedecompositionWorkflow(context, sender, reader)
    },
  }
}
