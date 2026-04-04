/**
 * Convergence Synthesis Strategy — Coordinates the endgame when multiple
 * branches are performing well and approaching completion.
 *
 * WHY: When 2+ branches have high rolling scores and are actively implementing,
 * they're converging on the goal. Today this pattern is detected but passive.
 * This strategy actively coordinates the final phase: it tells each branch
 * what the others have accomplished so they can avoid duplication and build
 * on each other's work.
 *
 * Flow:
 *   assess-convergence → parallel[context-inject-to-each-converging-branch]
 *
 * The assess step gathers each converging branch's modified files and goal,
 * then each branch receives a context-inject directive with a summary of
 * what peer branches have done.
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


interface BranchSummary {
  helixId: string
  goal: string
  score: number
  filesModified: string[]
}

interface ConvergenceAssessment {
  convergingBranches: BranchSummary[]
  totalFilesModified: string[]
}


function createConvergenceSynthesisWorkflow(
  context: StrategyContext,
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): WorkflowDefinition {
  const { pattern } = context

  const assessStep = corpusAssessStep<ConvergenceAssessment>({
    id: 'assess-convergence',
    description: 'Gather converging branch summaries for cross-pollination',
    reader,
    assess: (stateReader) => {
      const state = stateReader.getProcessedState()
      const tree = stateReader.getTree()

      const summaries: BranchSummary[] = []
      const allFiles = new Set<string>()

      for (const helixId of pattern.helixIds) {
        const assessment = state.branchAssessments.get(helixId)
        const branch = tree.getBranch(helixId)

        if (!assessment || !branch) continue

        const files = [...(assessment.filesModified ?? [])]
        files.forEach(f => allFiles.add(f))

        summaries.push({
          helixId,
          goal: branch.goal,
          score: assessment.rollingScore,
          filesModified: files,
        })
      }

      context.logger.info('Convergence assessed', {
        branches: summaries.length,
        totalFiles: allFiles.size,
      })

      return {
        convergingBranches: summaries,
        totalFilesModified: [...allFiles],
      }
    },
  })

  const injectContext: WorkflowStep = {
    id: 'inject-peer-context',
    description: 'Send each converging branch a summary of peer progress',
    timeoutMs: 30_000,
    execute: async (ctx) => {
      const assessment = ctx.input as ConvergenceAssessment

      for (const branch of assessment.convergingBranches) {
        const peers = assessment.convergingBranches.filter(b => b.helixId !== branch.helixId)
        if (peers.length === 0) continue

        const peerSummary = peers.map(p =>
          `- Branch "${p.goal}" (score: ${p.score.toFixed(2)}): modified ${p.filesModified.length} files — ${p.filesModified.slice(0, 5).join(', ')}${p.filesModified.length > 5 ? ` (+${p.filesModified.length - 5} more)` : ''}`,
        ).join('\n')

        await sender.sendDirective({
          targetHelixId: branch.helixId,
          type: 'context-inject',
          urgency: 'medium',
          reason: 'Convergence synthesis: sharing peer progress for coordination',
          text: [
            'CONVERGENCE UPDATE — Multiple branches are performing well.',
            '',
            '## What your peer branches have accomplished:',
            peerSummary,
            '',
            '## Guidance:',
            '- Avoid re-editing files that peers have already modified',
            '- Focus on your remaining unique deliverables',
            '- If your work depends on a peer\'s files, note the dependency but do not edit their files',
          ].join('\n'),
          fromPattern: 'convergence',
        })
      }

      ctx.logger.info('Convergence context injected', {
        branches: assessment.convergingBranches.length,
      })
    },
  }

  const builder = createWorkflow({
    id: `convergence-synthesis-${Date.now()}`,
    description: `Convergence coordination for ${pattern.helixIds.length} branches`,
  })

  builder
    .then(assessStep)
    .then(injectContext)

  return builder.commit()
}


export function createConvergenceSynthesisStrategy(
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): CorpusStrategy {
  return {
    id: 'convergence-synthesis',
    description: 'Coordinate converging branches by sharing peer progress context',
    patternTypes: ['convergence'],
    priority: 5,

    matches(pattern: CrossHelixPattern, _state: CorpusProcessedState): boolean {
      return pattern.helixIds.length >= 2 && !pattern.actedUpon
    },

    createWorkflow(context: StrategyContext): WorkflowDefinition {
      return createConvergenceSynthesisWorkflow(context, sender, reader)
    },
  }
}
