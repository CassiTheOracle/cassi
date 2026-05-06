import type { LaminaField } from '../lamina/index.js'
import type { GlobalWorkspace } from '../workspace/global-workspace.js'
import type { CognitiveSignal } from '../workspace/cognitive-signal.js'
import type { GoalSubTask } from './corpus-types.js'

export const HELIX_GOAL_LABEL = 'helix-goal'
export const HELIX_GOAL_OWNER = 'helix-unity'
export const HELIX_GOAL_CHAR_LIMIT = 1_500

export type HelixGoalTerminalStatus = 'completed' | 'failed'

export function seedHelixGoalLamina(
  lamina: LaminaField | undefined,
  helixId: string,
  subTask: GoalSubTask,
): void {
  if (!lamina) return
  const seedContent = renderSeedContent(subTask)

  try {
    lamina.ensure({
      label: HELIX_GOAL_LABEL,
      description: 'What this Helix is currently trying to accomplish.',
      owner: HELIX_GOAL_OWNER,
      ownerExclusive: false,
      charLimit: HELIX_GOAL_CHAR_LIMIT,
      content: seedContent,
      scope: { kind: 'session', sessionId: helixId },
    }, HELIX_GOAL_OWNER)
  } catch {
    // Non-fatal — Helix proceeds without the goal lamina if seeding fails.
  }
}

export function rethinkHelixGoalLamina(
  lamina: LaminaField | undefined,
  helixId: string,
  subTask: GoalSubTask,
  status: HelixGoalTerminalStatus,
  outcome?: string,
): void {
  if (!lamina) return
  const lines = [
    `GOAL: ${subTask.goal}`,
    '',
    `[${status} at ${new Date().toISOString()}]`,
  ]
  if (outcome) lines.push(outcome.slice(0, 800))
  try {
    lamina.rethink(
      HELIX_GOAL_LABEL,
      { content: lines.join('\n'), reason: `Helix ${status}` },
      HELIX_GOAL_OWNER,
      { kind: 'session', sessionId: helixId },
    )
  } catch {
    // Non-fatal — terminal state is already recorded by the tracker; lamina is forensic.
  }
}

function renderSeedContent(subTask: GoalSubTask): string {
  return [
    `GOAL: ${subTask.goal}`,
    '',
    subTask.relevantFiles?.length ? `Relevant files: ${subTask.relevantFiles.join(', ')}` : null,
    subTask.budgetSteps != null ? `Budget: ${subTask.budgetSteps} steps` : null,
  ].filter(Boolean).join('\n')
}

export type HelixGoalSignalKind = 'seed' | 'completed' | 'failed'

export function publishHelixGoalSignal(
  workspace: GlobalWorkspace | undefined,
  constellationId: string,
  helixId: string,
  subTask: GoalSubTask,
  kind: HelixGoalSignalKind,
  outcome?: string,
): void {
  if (!workspace) return
  const signal: CognitiveSignal = {
    signalId: `goal-${helixId}-${kind}-${Date.now()}`,
    source: 'helix',
    sessionId: helixId,
    type: 'goal',
    content: renderGoalSignalContent(subTask, kind, outcome),
    createdAt: Date.now(),
    urgencyHint: 0,
    luminance: {
      novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0,
      cognitiveResonance: 0, strategicImportance: 0, composite: 0,
    },
    metadata: {
      constellationId,
      helixId,
      relevantFiles: subTask.relevantFiles ?? [],
      budgetSteps: subTask.budgetSteps,
      kind,
    },
  }
  try {
    workspace.submit(signal)
  } catch {
    // Non-fatal — the territory-awareness consumer in PR-2 will tolerate gaps.
  }
}

function renderGoalSignalContent(
  subTask: GoalSubTask,
  kind: HelixGoalSignalKind,
  outcome?: string,
): string {
  if (kind === 'seed') {
    const files = subTask.relevantFiles?.length
      ? `\nFiles: ${subTask.relevantFiles.join(', ')}`
      : ''
    return `Working on: ${subTask.goal}${files}`
  }
  const tag = kind === 'completed' ? 'Completed' : 'Failed'
  const tail = outcome ? `: ${outcome.slice(0, 200)}` : ''
  return `${tag}: ${subTask.goal}${tail}`
}
