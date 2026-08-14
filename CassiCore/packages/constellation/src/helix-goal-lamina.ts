import type { LaminaField } from '@cassicore/lamina-locus-bridge'
import type { GlobalWorkspace } from '@cassicore/workspace'
import type { CognitiveSignal } from '@cassicore/workspace'
import type { GoalSubTask } from './corpus-types.js'

export const HELIX_GOAL_LABEL = 'helix-goal'
export const HELIX_GOAL_OWNER = 'helix-unity'
export const HELIX_GOAL_CHAR_LIMIT = 1_500
/** Max augmentation lines (Coordinating with Helix... + Mentor noted...) preserved on rethink/append. Combined cap; oldest dropped FIFO. */
export const HELIX_GOAL_AUG_CAP = 5

export type HelixGoalTerminalStatus = 'completed' | 'failed'

const AUG_LINE_RE = /^(Coordinating with Helix |Mentor noted: )/

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

export type HelixGoalSignalKind = 'seed' | 'progress' | 'completed' | 'failed'

/**
 * Pure FIFO trim helper for the helix-goal lamina's augmentation lines.
 * Aug lines = "Coordinating with Helix ..." OR "Mentor noted: ...". Other lines
 * (seed body, terminal-rethink content) are preserved verbatim.
 *
 * Behavior: split content into preamble (non-aug) + existing aug lines. Append
 * the new line. If the resulting aug-line count exceeds `cap`, drop the oldest
 * aug lines (FIFO) until at cap. Re-assemble preamble + remaining aug lines.
 */
export function trimAugLines(content: string, newLine: string, cap: number = HELIX_GOAL_AUG_CAP): string {
  const lines = content.split('\n')
  const preamble: string[] = []
  const augs: string[] = []
  for (const ln of lines) {
    if (AUG_LINE_RE.test(ln)) augs.push(ln)
    else preamble.push(ln)
  }
  augs.push(newLine)
  while (augs.length > cap) augs.shift()
  const preambleText = preamble.join('\n').replace(/\s+$/, '')
  return preambleText + (preambleText ? '\n' : '') + augs.join('\n')
}

/**
 * Mid-flight rethink — invoked when DecompositionTracker emits a transition
 * that warrants re-stating the goal (assigned, in-progress, split, deviation).
 * Preserves any prior aug lines (Coordinating/Mentor) verbatim above the new
 * GOAL block; aug lines are interpretive history that shouldn't be lost on
 * routine re-statement.
 */
export function rethinkHelixGoalMidFlight(
  lamina: LaminaField | undefined,
  helixId: string,
  subTask: GoalSubTask,
  reason: string,
): void {
  if (!lamina) return
  try {
    const current = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })
    const existingAugs = current
      ? current.content.split('\n').filter(ln => AUG_LINE_RE.test(ln))
      : []

    const seedContent = renderSeedContent(subTask)
    const newContent = existingAugs.length
      ? `${seedContent}\n${existingAugs.join('\n')}`
      : seedContent

    lamina.rethink(
      HELIX_GOAL_LABEL,
      { content: newContent, reason: `mid-flight: ${reason}` },
      HELIX_GOAL_OWNER,
      { kind: 'session', sessionId: helixId },
    )
  } catch {
    // Non-fatal — mid-flight rethink is best-effort. CAS conflicts (e.g. with a
    // concurrent bridge append) are tolerable; the next transition will re-rethink.
  }
}

/**
 * Append a "Coordinating with Helix <peer> on <files>" entry to the helix-goal
 * lamina. FIFO-capped at HELIX_GOAL_AUG_CAP lines combined with mentor entries.
 * Called by HelixConductor.handleBroadcast when a bridge signal arrives.
 */
export function appendCoordinationLine(
  lamina: LaminaField | undefined,
  helixId: string,
  peerHelixId: string,
  sharedFiles: string[],
): void {
  if (!lamina) return
  try {
    const current = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })
    if (!current) return

    const filePart = sharedFiles.length ? ` on ${sharedFiles.join(', ')}` : ''
    const newLine = `Coordinating with Helix ${peerHelixId.slice(0, 8)}${filePart}`
    const newContent = trimAugLines(current.content, newLine)
    if (newContent === current.content) return

    lamina.replace(
      HELIX_GOAL_LABEL,
      { expectedHash: current.contentHash, content: newContent, reason: 'bridge signal received' },
      HELIX_GOAL_OWNER,
      { kind: 'session', sessionId: helixId },
    )
  } catch {
    // Non-fatal — CAS conflicts are tolerable; the next bridge will re-attempt.
  }
}

/**
 * Append a "Mentor noted: <type> at step <N>" entry to the helix-goal lamina.
 * FIFO-capped at HELIX_GOAL_AUG_CAP lines combined with coordination entries.
 * Called from HelixPostureRunner.handleMentorFlag adjacent to its publishSignal.
 */
export function appendMentorFlagLine(
  lamina: LaminaField | undefined,
  helixId: string,
  issueType: string,
  stepNumber: number,
): void {
  if (!lamina) return
  try {
    const current = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })
    if (!current) return

    const newLine = `Mentor noted: ${issueType} at step ${stepNumber}`
    const newContent = trimAugLines(current.content, newLine)
    if (newContent === current.content) return

    lamina.replace(
      HELIX_GOAL_LABEL,
      { expectedHash: current.contentHash, content: newContent, reason: 'mentor flag raised' },
      HELIX_GOAL_OWNER,
      { kind: 'session', sessionId: helixId },
    )
  } catch {
    // Non-fatal — mentor flag is logged separately via publishSignal.
  }
}

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
  if (kind === 'progress') {
    const tail = outcome ? `: ${outcome.slice(0, 200)}` : ''
    return `Refining: ${subTask.goal}${tail}`
  }
  const tag = kind === 'completed' ? 'Completed' : 'Failed'
  const tail = outcome ? `: ${outcome.slice(0, 200)}` : ''
  return `${tag}: ${subTask.goal}${tail}`
}
