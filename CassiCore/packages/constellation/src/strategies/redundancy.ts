/**
 * Redundancy Strategy — Detects when two branches are doing substantially
 * overlapping work (same work pattern on the same files) and redirects
 * the lower-scorer to unique work.
 *
 * WHY: Unlike conflict (any file overlap), redundancy means two branches
 * are doing the same TYPE of work (both implementation, both analysis)
 * on largely the same files. One branch should be redirected to unique
 * deliverables rather than duplicating effort.
 *
 * Flow:
 *   assess-redundancy → redirect-lower-scorer
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


interface RedundancyAssessment {
  redundantBranch: { helixId: string; score: number; goal: string }
  keepBranch: { helixId: string; score: number; goal: string }
  sharedFiles: string[]
  uniqueFilesForRedundant: string[]
  workPattern: string
}


function createRedundancyWorkflow(
  context: StrategyContext,
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): WorkflowDefinition {
  const { pattern } = context
  const [helixA, helixB] = pattern.helixIds

  const assessStep = corpusAssessStep<RedundancyAssessment>({
    id: 'assess-redundancy',
    description: `Assess redundancy between ${helixA} and ${helixB}`,
    reader,
    assess: (stateReader) => {
      const state = stateReader.getProcessedState()
      const tree = stateReader.getTree()

      const assessA = state.branchAssessments.get(helixA)
      const assessB = state.branchAssessments.get(helixB)
      const branchA = tree.getBranch(helixA)
      const branchB = tree.getBranch(helixB)

      const scoreA = assessA?.rollingScore ?? 0
      const scoreB = assessB?.rollingScore ?? 0
      const filesA = assessA?.filesModified ?? new Set<string>()
      const filesB = assessB?.filesModified ?? new Set<string>()

      const sharedFiles = [...filesA].filter(f => filesB.has(f))
      const aWins = scoreA >= scoreB

      const keepId = aWins ? helixA : helixB
      const redundantId = aWins ? helixB : helixA
      const redundantFiles = aWins ? filesB : filesA
      const keepFiles = aWins ? filesA : filesB

      const uniqueFilesForRedundant = [...redundantFiles].filter(f => !keepFiles.has(f))

      // Extract work pattern from the pattern description (set during detection)
      const workPatternMatch = context.pattern.description.match(/redundant (\w+) work/)
      const detectedWorkPattern = workPatternMatch ? workPatternMatch[1] : 'unknown'

      return {
        keepBranch: {
          helixId: keepId,
          score: aWins ? scoreA : scoreB,
          goal: (aWins ? branchA : branchB)?.goal ?? '(unknown)',
        },
        redundantBranch: {
          helixId: redundantId,
          score: aWins ? scoreB : scoreA,
          goal: (aWins ? branchB : branchA)?.goal ?? '(unknown)',
        },
        sharedFiles,
        uniqueFilesForRedundant,
        workPattern: detectedWorkPattern,
      }
    },
  })

  const redirectRedundant: WorkflowStep = {
    id: 'redirect-redundant',
    description: 'Redirect redundant branch to unique work',
    timeoutMs: 30_000,
    execute: async (ctx) => {
      const assessment = ctx.input as RedundancyAssessment
      const { redundantBranch, keepBranch, sharedFiles, uniqueFilesForRedundant, workPattern } = assessment

      const hasUniqueWork = uniqueFilesForRedundant.length > 0
      const uniqueFilesStr = uniqueFilesForRedundant.slice(0, 5).join(', ')

      await sender.sendDirective({
        targetHelixId: redundantBranch.helixId,
        type: 'redirect',
        urgency: 'high',
        reason: `Redundancy: ${redundantBranch.helixId} and ${keepBranch.helixId} doing overlapping ${workPattern} on ${sharedFiles.length} shared files`,
        text: [
          `REDUNDANCY DETECTED — Your ${workPattern} work overlaps significantly with branch "${keepBranch.goal}".`,
          `Shared files: ${sharedFiles.slice(0, 5).join(', ')}${sharedFiles.length > 5 ? ` (+${sharedFiles.length - 5} more)` : ''}`,
          '',
          'ACTION REQUIRED: Stop working on the shared files.',
          hasUniqueWork
            ? `Focus on your unique files instead: ${uniqueFilesStr}${uniqueFilesForRedundant.length > 5 ? ` (+${uniqueFilesForRedundant.length - 5} more)` : ''}`
            : 'Find a different angle or set of files to contribute to the overall goal.',
          `The other branch (score: ${keepBranch.score.toFixed(2)}) has priority on the shared files.`,
        ].join('\n'),
        fromPattern: 'redundancy',
        requiredAction: 'switch_strategy',
      })

      ctx.logger.info('Redundancy directive sent', {
        redundantId: redundantBranch.helixId,
        keepId: keepBranch.helixId,
        sharedFiles: sharedFiles.length,
        uniqueFiles: uniqueFilesForRedundant.length,
      })
    },
  }

  const builder = createWorkflow({
    id: `redundancy-${helixA}-${helixB}`,
    description: `Resolve redundancy between ${helixA} and ${helixB}`,
  })

  builder
    .then(assessStep)
    .then(redirectRedundant)

  return builder.commit()
}


export function createRedundancyStrategy(
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): CorpusStrategy {
  return {
    id: 'redundancy',
    description: 'Redirect duplicate work when branches overlap on same files and work pattern',
    patternTypes: ['redundancy'],
    priority: 8,

    matches(pattern: CrossHelixPattern, _state: CorpusProcessedState): boolean {
      return pattern.helixIds.length >= 2 && !pattern.actedUpon
    },

    createWorkflow(context: StrategyContext): WorkflowDefinition {
      return createRedundancyWorkflow(context, sender, reader)
    },
  }
}
