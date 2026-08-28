/**
 * Helix Goal Lamina (vendor stub)
 *
 * Faithful port of CassiCore `core/intelligence/constellation/helix-goal-lamina.ts`,
 * limited to the two runtime helpers helix consumes: `appendCoordinationLine`
 * and `appendMentorFlagLine` (consumed by helix-conductor.ts and
 * helix-posture-runner.ts). These are pure string helpers operating on the
 * caller-injected `LaminaField` (a lean, structurally-compatible local surface
 * declared here for self-containment).
 */

export const HELIX_GOAL_LABEL = 'helix-goal'
export const HELIX_GOAL_OWNER = 'helix-unity'
export const HELIX_GOAL_CHAR_LIMIT = 1_500
/** Max augmentation lines (Coordinating with Helix... + Mentor noted...) preserved on rethink/append. Combined cap; oldest dropped FIFO. */
export const HELIX_GOAL_AUG_CAP = 5

const AUG_LINE_RE = /^(Coordinating with Helix |Mentor noted: )/

/**
 * Minimal local LaminaField surface — the members the ported helpers use.
 * Matches the CassiCore lamina facade (`read` returning a field with
 * `content`/`contentHash`, and CAS-based `replace`).
 */
export interface LaminaField {
  read(label: string, scope: { kind: 'session'; sessionId: string }): { content: string; contentHash: string } | null
  replace(
    label: string,
    edit: { expectedHash: string; content: string; reason: string },
    owner: string,
    scope: { kind: 'session'; sessionId: string },
  ): void
}

/**
 * Pure FIFO trim helper for the helix-goal lamina's augmentation lines.
 * Aug lines = "Coordinating with Helix ..." OR "Mentor noted: ...". Other lines
 * (seed body, terminal-rethink content) are preserved verbatim.
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
