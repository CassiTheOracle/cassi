/**
 * Conflict Resolution Strategy — Detects file conflicts between branches
 * and sends redirecting directives to resolve them.
 *
 * WHY: When two branches modify overlapping files, their changes may conflict
 * at merge time. The Corpus detects this as a 'conflict' cross-helix pattern.
 * This strategy automates the response: assess which branch should yield,
 * then send directives to redirect the yielding branch to alternative files
 * or to narrow its scope.
 *
 * Flow:
 *   assess-conflict → [parallel: directive-to-branch-A, directive-to-branch-B] → verify
 *
 * The assess step reads branch assessments to determine which branch is
 * more productive (higher rolling score, more files modified). The less
 * productive branch receives a 'redirect' directive; the more productive
 * one receives a 'guidance' with context about the conflict.
 */

import { createWorkflow } from '@cassicore/workflow'
import { corpusAssessStep, corpusDirectiveStep } from '@cassicore/workflow'
import type { ICorpusDirectiveSender, ICorpusStateReader } from '@cassicore/workflow'
import type { WorkflowDefinition } from '@cassicore/workflow'
import type {
  CorpusStrategy,
  StrategyContext,
  CrossHelixPattern,
  CorpusProcessedState,
} from '../corpus-types.js'


// Assessment result produced by the assess step

interface ConflictAssessment {
  conflictingFiles: string[]
  primaryBranch: { helixId: string; score: number; fileCount: number }
  yieldingBranch: { helixId: string; score: number; fileCount: number }
  severity: string
}

/**
 * Build the conflict resolution workflow.
 *
 * HOW: The workflow has three stages:
 *   1. Assess: Read branch scores and determine which yields.
 *   2. Parallel directives: Send redirect to yielding branch + context to primary.
 *   3. The workflow completes — the Corpus's next sweep verifies resolution
 *      (we don't add a verify step because the Corpus loop already monitors patterns).
 */
function createConflictResolutionWorkflow(
  context: StrategyContext,
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): WorkflowDefinition {
  const { pattern } = context
  const [helixA, helixB] = pattern.helixIds

  const assessStep = corpusAssessStep<ConflictAssessment>({
    id: 'assess-conflict',
    description: `Assess conflict between ${helixA} and ${helixB}`,
    reader,
    assess: (stateReader) => {
      const state = stateReader.getProcessedState()
      const tree = stateReader.getTree()

      const branchA = state.branchAssessments.get(helixA)
      const branchB = state.branchAssessments.get(helixB)

      const scoreA = branchA?.rollingScore ?? 0
      const scoreB = branchB?.rollingScore ?? 0
      const filesA = branchA?.filesModified?.size ?? 0
      const filesB = branchB?.filesModified?.size ?? 0

      const aGoal = tree.getBranch(helixA)?.goal ?? '(unknown)'
      const bGoal = tree.getBranch(helixB)?.goal ?? '(unknown)'

      // Determine who yields: lower score yields, ties broken by fewer files
      const aWins = scoreA > scoreB || (scoreA === scoreB && filesA >= filesB)

      const primary = aWins
        ? { helixId: helixA, score: scoreA, fileCount: filesA }
        : { helixId: helixB, score: scoreB, fileCount: filesB }

      const yielding = aWins
        ? { helixId: helixB, score: scoreB, fileCount: filesB }
        : { helixId: helixA, score: scoreA, fileCount: filesA }

      // Extract conflicting files from the pattern description if available,
      // or from the intersection of modified file sets
      const filesModifiedA = branchA?.filesModified ?? new Set<string>()
      const filesModifiedB = branchB?.filesModified ?? new Set<string>()
      const conflictingFiles = [...filesModifiedA].filter(f => filesModifiedB.has(f))

      context.logger.info('Conflict assessed', {
        primary: primary.helixId,
        yielding: yielding.helixId,
        conflictingFiles: conflictingFiles.length,
        scores: { a: scoreA, b: scoreB },
        goals: { a: aGoal, b: bGoal },
      })

      return {
        conflictingFiles,
        primaryBranch: primary,
        yieldingBranch: yielding,
        severity: pattern.severity,
      }
    },
  })

  const redirectYielding = corpusDirectiveStep({
    id: 'redirect-yielding',
    description: 'Redirect yielding branch away from conflicting files',
    sender,
    directiveType: 'redirect',
    urgency: pattern.severity === 'critical' ? 'critical' : 'high',
    fromPattern: 'conflict',
    targetHelixId: (input) => (input as ConflictAssessment).yieldingBranch.helixId,
    text: (input) => {
      const assessment = input as ConflictAssessment
      const files = assessment.conflictingFiles.join(', ')
      return [
        `FILE CONFLICT DETECTED — You are modifying files that another branch is also editing.`,
        `Conflicting files: ${files || '(overlap detected)'}`,
        ``,
        `ACTION REQUIRED: Stop editing these files immediately.`,
        `Focus on your remaining assigned files or narrow your scope to avoid the conflict.`,
        `The other branch has higher priority for these files.`,
      ].join('\n')
    },
    reason: (input) => {
      const assessment = input as ConflictAssessment
      return `Conflict resolution: redirecting ${assessment.yieldingBranch.helixId} (score ${assessment.yieldingBranch.score}) away from ${assessment.conflictingFiles.length} conflicting files`
    },
    requiredAction: 'narrow_scope',
  })

  const informPrimary = corpusDirectiveStep({
    id: 'inform-primary',
    description: 'Inform primary branch about resolved conflict',
    sender,
    directiveType: 'guidance',
    urgency: 'medium',
    fromPattern: 'conflict',
    targetHelixId: (input) => (input as ConflictAssessment).primaryBranch.helixId,
    text: (input) => {
      const assessment = input as ConflictAssessment
      const files = assessment.conflictingFiles.join(', ')
      return [
        `CONFLICT RESOLVED — A peer branch was redirected away from files you're editing.`,
        `You have priority on: ${files || '(your current files)'}`,
        `Continue your current approach.`,
      ].join('\n')
    },
    reason: 'Conflict resolution: informing primary branch of priority',
  })

  const builder = createWorkflow({
    id: `conflict-resolution-${helixA}-${helixB}`,
    description: `Resolve file conflict between ${helixA} and ${helixB}`,
  })

  builder
    .then(assessStep)
    .parallel([redirectYielding, informPrimary])

  return builder.commit()
}


/**
 * The conflict resolution strategy instance.
 *
 * Register this with the CorpusStrategyRegistry to enable automatic
 * conflict resolution when the Corpus detects file overlap patterns.
 */
export function createConflictResolutionStrategy(
  sender: ICorpusDirectiveSender,
  reader: ICorpusStateReader,
): CorpusStrategy {
  return {
    id: 'conflict-resolution',
    description: 'Resolve file conflicts between branches by redirecting the lower-scoring branch',
    patternTypes: ['conflict'],
    priority: 10,

    matches(pattern: CrossHelixPattern, _state: CorpusProcessedState): boolean {
      // Match conflict patterns with at least 2 involved branches
      return pattern.helixIds.length >= 2 && !pattern.actedUpon
    },

    createWorkflow(context: StrategyContext): WorkflowDefinition {
      return createConflictResolutionWorkflow(context, sender, reader)
    },
  }
}
