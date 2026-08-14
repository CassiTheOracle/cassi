/**
 * Cascade Recovery Strategy — Responds to cascade-failure patterns where
 * multiple branches fail or struggle simultaneously.
 *
 * WHY: When 2+ branches fail within a short window, the remaining branches
 * are at risk. The inline fallback sends the same directive to everyone.
 * This strategy discriminates: it throttles healthy branches gently,
 * redirects struggling branches aggressively, and skips already-failed ones.
 *
 * Flow:
 *   assess-severity → parallel[throttle-healthy, redirect-struggling]
 *
 * The assess step categorizes active branches into three buckets:
 *   - failed: skip (already dead)
 *   - struggling: receive aggressive redirect + produce_output
 *   - healthy: receive gentle throttle to prevent further cascade
 */

import { createWorkflow } from '@cassicore/workflow'
import { corpusAssessStep, corpusDirectiveStep } from '@cassicore/workflow'
import type { ICorpusDirectiveSender, ICorpusStateReader } from '@cassicore/workflow'
import type { WorkflowDefinition, WorkflowStep } from '@cassicore/workflow'
import type {
  CorpusStrategy,
  StrategyContext,
  CrossHelixPattern,
  CorpusProcessedState,
} from '../corpus-types.js'


interface CascadeAssessment {
  failedBranches: string[]
  strugglingBranches: string[]
  healthyBranches: string[]
  totalActive: number
  severity: string
}


function createCascadeRecoveryWorkflow(
  context: StrategyContext,
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): WorkflowDefinition {
  const { pattern } = context

  const assessStep = corpusAssessStep<CascadeAssessment>({
    id: 'assess-cascade',
    description: 'Categorize branches by health during cascade',
    reader,
    assess: (stateReader) => {
      const state = stateReader.getProcessedState()
      const tree = stateReader.getTree()
      const allBranches = tree.getAllBranches()

      const failed: string[] = []
      const struggling: string[] = []
      const healthy: string[] = []

      for (const branch of allBranches) {
        if (branch.status !== 'active') {
          failed.push(branch.helixId)
          continue
        }

        const assessment = state.branchAssessments.get(branch.helixId)
        if (!assessment) {
          healthy.push(branch.helixId)
          continue
        }

        if (assessment.status === 'struggling' || assessment.status === 'stuck' ||
            assessment.rollingScore < 0.4) {
          struggling.push(branch.helixId)
        } else {
          healthy.push(branch.helixId)
        }
      }

      context.logger.info('Cascade assessed', {
        failed: failed.length,
        struggling: struggling.length,
        healthy: healthy.length,
        patternHelixIds: pattern.helixIds,
      })

      return {
        failedBranches: failed,
        strugglingBranches: struggling,
        healthyBranches: healthy,
        totalActive: struggling.length + healthy.length,
        severity: pattern.severity,
      }
    },
  })

  // Build a single step that sends all directives based on the assessment
  const throttleAndRedirect: WorkflowStep = {
    id: 'send-recovery-directives',
    description: 'Send throttle/redirect directives to surviving branches',
    timeoutMs: 30_000,
    execute: async (ctx) => {
      const assessment = ctx.input as CascadeAssessment

      // Throttle healthy branches
      for (const helixId of assessment.healthyBranches) {
        await sender.sendDirective({
          targetHelixId: helixId,
          type: 'throttle',
          urgency: 'high',
          reason: `Cascade failure detected: ${assessment.failedBranches.length} branches failed. Throttling to prevent further cascade.`,
          text: [
            'CASCADE ALERT — Multiple peer branches have failed.',
            'Your branch is still healthy, but proceed cautiously.',
            'Narrow your remaining work to essential deliverables.',
            'Avoid risky operations that could trigger additional failures.',
          ].join('\n'),
          fromPattern: 'cascade-failure',
          maxIterationsRemaining: 15,
        })
      }

      // Redirect struggling branches aggressively
      for (const helixId of assessment.strugglingBranches) {
        await sender.sendDirective({
          targetHelixId: helixId,
          type: 'redirect',
          urgency: 'critical',
          reason: `Cascade failure: branch is struggling during cascade. Forcing immediate output.`,
          text: [
            'CRITICAL — CASCADE FAILURE IN PROGRESS',
            'Multiple branches are failing simultaneously.',
            'You are also struggling. Produce your output immediately.',
            'Narrow scope to only what you can complete right now.',
            'Do NOT start new files or new approaches.',
          ].join('\n'),
          fromPattern: 'cascade-failure',
          maxIterationsRemaining: 5,
          requiredAction: 'produce_output',
        })
      }

      ctx.logger.info('Recovery directives sent', {
        throttled: assessment.healthyBranches.length,
        redirected: assessment.strugglingBranches.length,
        skippedFailed: assessment.failedBranches.length,
      })
    },
  }

  const builder = createWorkflow({
    id: `cascade-recovery-${Date.now()}`,
    description: `Cascade recovery for ${pattern.helixIds.length} affected branches`,
  })

  builder
    .then(assessStep)
    .then(throttleAndRedirect)

  return builder.commit()
}


export function createCascadeRecoveryStrategy(
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): CorpusStrategy {
  return {
    id: 'cascade-recovery',
    description: 'Respond to cascade failures by throttling healthy branches and redirecting struggling ones',
    patternTypes: ['cascade-failure'],
    priority: 20,

    matches(pattern: CrossHelixPattern, _state: CorpusProcessedState): boolean {
      return pattern.helixIds.length >= 2 && !pattern.actedUpon
    },

    createWorkflow(context: StrategyContext): WorkflowDefinition {
      return createCascadeRecoveryWorkflow(context, sender, reader)
    },
  }
}
