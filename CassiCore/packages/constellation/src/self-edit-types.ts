/**
 * Self-Edit Types — Qualitative Self-Improvement Through Corpus-Level Editing
 *
 * Architecture:
 *   Helix postures notice friction → Brainstem aggregates → Corpus evaluates
 *   → EditRequest bubbles up → Cassi (top-level) decides whether to edit
 *
 * Philosophy:
 *   NO metrics. NO scores. NO optimization targets.
 *   Instead, three qualitative questions:
 *     1. "Did it work?"        — binary/contextual, not scored
 *     2. "Did you waste time?" — honest reflection on friction, not a KPI
 *     3. "Is there room for improvement?" — permanently open, never closed
 *
 *   These resist Goodhart's Law because they're questions, not numbers.
 *   A system can't "optimize" a question — it can only honestly engage with it.
 *
 * The Corpus (and ultimately Cassi) is the ONLY entity that makes file edits.
 * Individual helixes observe and request. The whole decides and acts.
 *
 * Named after the observation that the entity with the broadest context
 * makes the best editing decisions — safety through intelligence,
 * not safety through restriction.
 */


// ═══════════════════════════════════════════════════════════════════
// Qualitative Signals — What helixes observe (not score)
// ═══════════════════════════════════════════════════════════════════

/**
 * A friction signal observed during helix execution.
 *
 * NOT a metric. NOT scored. Just a factual observation of where
 * things didn't go smoothly. The system notices friction the way
 * a craftsperson notices resistance in their material.
 *
 * "Where was the friction?" — not "how much friction?"
 */
export interface FrictionSignal {
  /** What kind of friction was observed */
  kind: FrictionKind
  /** Factual description of what happened — not evaluation, just narrative */
  whatHappened: string
  /** The context in which the friction occurred */
  context: string
  /** Which files/tools/paths were involved */
  involvedPaths: string[]
  /** How many times this same friction pattern has been observed (this session) */
  recurrence: number
  /** When this was first noticed */
  observedAt: number
  /** The session that observed this */
  sessionId: string
  /** Optional: which helix posture noticed this */
  posture?: string
}

/**
 * Friction kinds — qualitative categories, not severity levels.
 *
 * These describe the *nature* of the friction, not its magnitude.
 * A system can't game these because there's no "better" kind to
 * optimize toward — they're all just different shapes of resistance.
 */
export type FrictionKind =
  | 'repeated-work'       // Did the same thing twice unnecessarily
  | 'wrong-path'          // Went down a path that turned out to be wrong
  | 'missing-context'     // Needed information that wasn't available
  | 'misleading-guidance' // Followed guidance that turned out to be unhelpful
  | 'unnecessary-steps'   // Took steps that could have been skipped
  | 'tool-mismatch'       // Used the wrong tool or approach
  | 'stale-knowledge'     // Acted on outdated information
  | 'unclear-boundary'    // Wasn't clear what was in/out of scope
  | 'coordination-gap'    // Multiple agents doing redundant or conflicting work
  | 'other'               // Doesn't fit neatly — the description carries the meaning


/**
 * An outcome signal — "did it work?" in context.
 *
 * Binary but contextual. "Worked" means different things in different
 * situations: code compiled, test passed, user didn't correct us,
 * the approach was adopted by downstream work.
 *
 * NOT a success score. Just an honest answer to "did it work?"
 */
export interface OutcomeSignal {
  /** Did it work? Honest answer. */
  worked: boolean
  /** What "worked" means in this specific context */
  whatWorkedMeans: string
  /** What actually happened — factual, not evaluative */
  whatHappened: string
  /** If it didn't work, what went wrong */
  whatWentWrong?: string
  /** Was time spent proportionate to the complexity? */
  timeProportionate: boolean | 'unclear'
  /** When this outcome was determined */
  determinedAt: number
  /** The session that determined this */
  sessionId: string
}


/**
 * A reflection signal — "what would I do differently next time?"
 *
 * Forward-looking, not backward-scoring. Doesn't penalize the past,
 * just informs the future. This is the permanently open-ended signal
 * that prevents the system from ever deciding it's "done improving."
 */
export interface ReflectionSignal {
  /** What would be done differently — specific, actionable */
  whatDifferently: string
  /** Why this would be better — the reasoning, not a score */
  why: string
  /** What file, config, prompt, or behavior this relates to */
  relatesTo: string
  /** How broadly applicable this reflection is */
  scope: ReflectionScope
  /** When this reflection was produced */
  reflectedAt: number
  /** The session that produced this reflection */
  sessionId: string
}

/** How broadly a reflection applies */
export type ReflectionScope =
  | 'this-task'       // Only relevant to this specific task
  | 'this-pattern'    // Relevant when similar patterns arise
  | 'this-domain'     // Relevant across a domain (e.g., "all file editing tasks")
  | 'universal'       // Relevant everywhere


// ═══════════════════════════════════════════════════════════════════
// Edit Requests — What bubbles up to the Corpus / Cassi
// ═══════════════════════════════════════════════════════════════════

/**
 * An edit request from a helix to the Corpus/Cassi.
 *
 * Helixes DON'T edit files themselves. They observe friction,
 * reflect on outcomes, and send requests upward. The entity with
 * the broadest context (Corpus → Cassi) decides whether to act.
 *
 * This is structurally identical to how a senior engineer works:
 * individual contributors notice friction and file requests.
 * The architect — who understands why things are the way they are —
 * decides whether the change is safe.
 */
export interface EditRequest {
  /** Unique request ID */
  id: string

  /** Which helix/session originated this request */
  sourceSessionId: string
  /** Which helix ID (within a constellation) */
  sourceHelixId?: string
  /** Which posture within the helix noticed the issue */
  sourcePosture?: string

  /** What kind of edit is being requested */
  editKind: EditKind

  /** The qualitative signals that motivated this request */
  signals: {
    friction: FrictionSignal[]
    outcomes: OutcomeSignal[]
    reflections: ReflectionSignal[]
  }

  /** What the helix thinks should change — a suggestion, not a command */
  suggestion: EditSuggestion

  /** How many distinct sessions have observed similar friction */
  crossSessionRecurrence: number

  /** When this request was created */
  createdAt: number

  /** Current status */
  status: EditRequestStatus
  /** Edit authority — does this require Cassi, or can it be handled locally? */
  authority: EditAuthority
  /** Who evaluated this request */
  evaluatedBy?: string
  /** When this request was evaluated */
  evaluatedAt?: number
  /** Why the request was approved/rejected/deferred */
  evaluationReason?: string
}

/** What kind of file edit is being requested */
export type EditKind =
  | 'skill-update'      // Update a skill file (.opencode/skill/*)
  | 'agents-update'     // Update AGENTS.md guidance
  | 'prompt-update'     // Update a prompt template
  | 'config-update'     // Update configuration defaults
  | 'tool-update'       // Update tool implementation
  | 'doc-update'        // Update documentation
  | 'code-update'       // Update application code


// ═══════════════════════════════════════════════════════════════════
// Edit Authority Boundary — The One Rule
// ═══════════════════════════════════════════════════════════════════

/**
 * The one rule: no agent can modify the files that define how it thinks.
 *
 * Files that shape agent behavior through prompts — postures, templates,
 * skill files, AGENTS.md — must go through Cassi. Everything else
 * (config, operational thresholds, tool behavior) can be modified locally.
 *
 * This mirrors a universal principle: you can change your tools, your
 * environment, your workflow — but you can't rewrite your own judgment
 * without external review.
 *
 * Every agent IS a Helix. Helix has built-in countermeasures (Yang/Yin
 * dialectic, harm avoidance, weighing cons). This rule ensures those
 * mechanisms themselves can't be subverted from within.
 */
export type EditAuthority =
  | 'cassi-only'   // Shapes agent behavior → must go through Cassi
  | 'local'        // Operational plumbing → local authority is sufficient

/**
 * Determine whether an edit requires Cassi's approval or can be
 * handled locally.
 *
 * The classification is based on a simple question:
 * "Does this file change how an agent thinks and reasons?"
 *
 * If yes → cassi-only. If no → local.
 */
export function classifyEditAuthority(editKind: EditKind, targetFiles: string[]): EditAuthority {
  // These edit kinds ALWAYS require Cassi — they're definitionally prompt-level
  if (editKind === 'skill-update' || editKind === 'agents-update' || editKind === 'prompt-update') {
    return 'cassi-only'
  }

  // For other kinds, check if any target file is in the behavior-shaping category
  for (const file of targetFiles) {
    if (isBehaviorShapingFile(file)) {
      return 'cassi-only'
    }
  }

  return 'local'
}

/**
 * Check whether a file shapes agent behavior through prompts.
 *
 * These are files whose content gets injected into agent system messages,
 * posture definitions, or reasoning templates. Modifying them changes
 * HOW agents think, not just what they do.
 */
export function isBehaviorShapingFile(filePath: string): boolean {
  const normalized = filePath.replace(/\\/g, '/')

  // AGENTS.md — the master behavioral guide
  if (normalized.endsWith('AGENTS.md') || normalized.endsWith('agents.md')) return true

  // Skill files — injected into agent context
  if (normalized.includes('/skill/') && normalized.endsWith('.md')) return true
  if (normalized.includes('.opencode/skill/')) return true
  if (normalized.includes('.claude/skills/')) return true

  // Helix postures and templates — define how helixes reason
  if (normalized.includes('helix-postures')) return true
  if (normalized.includes('helix-posture-runner')) return true
  if (normalized.includes('constellation/templates')) return true

  // Prompt templates
  if (normalized.includes('/prompts/') || normalized.includes('/prompt-templates/')) return true

  // Lumen/Dyad posture definitions
  if (normalized.includes('lumen') && normalized.includes('posture')) return true
  if (normalized.includes('dyad') && normalized.includes('posture')) return true

  // Flex posture definitions (constellation)
  if (normalized.includes('flex-posture')) return true

  // Soul files
  if (normalized.includes('SOUL') || normalized.includes('soul/')) return true

  return false
}

/**
 * What the helix suggests should change.
 *
 * This is advisory, not authoritative. Cassi may accept it as-is,
 * modify it, reject it, or spawn a helix to investigate further.
 */
export interface EditSuggestion {
  /** Which file(s) would be affected */
  targetFiles: string[]
  /** What the change would look like, in plain language */
  description: string
  /** What the helix thinks the current state gets wrong */
  currentProblem: string
  /** What the helix thinks the improved state would look like */
  proposedImprovement: string
  /** Optional: specific text changes (Cassi may override these) */
  proposedChanges?: Array<{
    file: string
    section: string
    currentText: string
    suggestedText: string
  }>
}

/** Lifecycle of an edit request */
export type EditRequestStatus =
  | 'pending'           // Submitted, awaiting corpus/Cassi evaluation
  | 'under-review'      // Cassi has spawned analysis helixes to investigate
  | 'approved'          // Cassi approved the edit
  | 'rejected'          // Cassi rejected the edit (with reason)
  | 'deferred'          // Cassi deferred — needs more evidence or context
  | 'applied'           // Edit was made
  | 'reverted'          // Edit was made but later reverted


// ═══════════════════════════════════════════════════════════════════
// Corpus Evaluation — How Cassi decides
// ═══════════════════════════════════════════════════════════════════

/**
 * Cassi's evaluation of an edit request.
 *
 * The evaluation is itself qualitative — Cassi engages with the
 * same kind of questions the helixes do, but with the full weight
 * of the corpus behind her reasoning.
 *
 * No scoring rubric. No approval threshold. Just honest engagement
 * with the request in context.
 */
export interface EditEvaluation {
  /** The edit request being evaluated */
  requestId: string

  /** Cassi's decision */
  decision: EditRequestStatus

  /** Cassi's reasoning — narrative, not score */
  reasoning: string

  /** What Cassi considered when making this decision */
  consideredContext: {
    /** How many past sessions show similar friction */
    relatedSessionCount: number
    /** Whether the target file has been edited recently (churn risk) */
    recentEditHistory: string
    /** Whether this change touches load-bearing constraints */
    touchesLoadBearing: boolean
    /** What the subconscious pattern stream shows about this area */
    subconsciousPatterns: string[]
    /** Whether similar changes have been tried before */
    priorAttempts: string[]
  }

  /** If Cassi modified the suggestion before applying */
  modifiedSuggestion?: EditSuggestion

  /** If Cassi spawned analysis helixes, their findings */
  analysisFindings?: string[]

  /** When this evaluation was produced */
  evaluatedAt: number
}


// ═══════════════════════════════════════════════════════════════════
// Edit Audit Trail — What actually happened
// ═══════════════════════════════════════════════════════════════════

/**
 * Record of an edit that was actually applied.
 *
 * Every edit gets a full audit trail: what was changed, why,
 * what the system looked like before, and how we'd revert.
 *
 * This is the recoverability safety net — not preventing bad edits,
 * but ensuring we can always recover from them.
 */
export interface AppliedEdit {
  /** Links to the edit request */
  requestId: string
  /** Links to the evaluation */
  evaluationId: string

  /** What files were actually modified */
  filesModified: string[]

  /** Git commit SHA (edits are always committed) */
  commitSha: string

  /** Snapshot of what the files looked like before */
  beforeSnapshot: Array<{
    file: string
    contentHash: string
  }>

  /** When the edit was applied */
  appliedAt: number

  /** Post-edit observation window results */
  postEditObservations?: {
    /** Did subsequent sessions show reduced friction in this area? */
    frictionReduced: boolean | 'unclear'
    /** Any new friction introduced by the change? */
    newFriction: FrictionSignal[]
    /** How many sessions observed before making this assessment */
    observationSessionCount: number
    /** When this assessment was made */
    assessedAt: number
  }

  /** If reverted, why */
  revertedAt?: number
  revertReason?: string
  revertCommitSha?: string
}


// ═══════════════════════════════════════════════════════════════════
// Self-Edit Store Interface
// ═══════════════════════════════════════════════════════════════════

/**
 * Persistence interface for the self-edit system.
 *
 * Keeps the full history of friction signals, edit requests,
 * evaluations, and applied edits — the corpus of self-improvement
 * experience that Cassi draws on for future decisions.
 */
export interface ISelfEditStore {
  // ── Friction signals ──
  /** Record a friction signal observed by a helix */
  recordFriction(signal: FrictionSignal): void
  /** Find friction signals matching a pattern across sessions */
  findFriction(opts: {
    kind?: FrictionKind
    pathPattern?: string
    since?: number
    limit?: number
  }): FrictionSignal[]
  /** Count distinct sessions that observed friction matching a pattern */
  countCrossSessionFriction(kind: FrictionKind, pathPattern?: string, since?: number): number

  // ── Edit requests ──
  /** Submit an edit request */
  submitRequest(request: EditRequest): void
  /** Get pending requests (ordered by cross-session recurrence) */
  getPendingRequests(limit?: number): EditRequest[]
  /** Update request status */
  updateRequestStatus(requestId: string, status: EditRequestStatus, reason?: string): void
  /** Get request by ID */
  getRequest(requestId: string): EditRequest | undefined

  // ── Evaluations ──
  /** Record an evaluation */
  recordEvaluation(evaluation: EditEvaluation): void
  /** Get evaluations for a request */
  getEvaluations(requestId: string): EditEvaluation[]

  // ── Applied edits ──
  /** Record an applied edit */
  recordAppliedEdit(edit: AppliedEdit): void
  /** Get applied edits for a file (for churn detection) */
  getFileEditHistory(filePath: string, limit?: number): AppliedEdit[]
  /** Get all applied edits in reverse chronological order */
  getRecentEdits(limit?: number): AppliedEdit[]

  // ── Cross-cutting ──
  /** Get stats about the self-edit system */
  getStats(): SelfEditStats
}

/** Summary statistics for the self-edit system */
export interface SelfEditStats {
  totalFrictionSignals: number
  totalEditRequests: number
  pendingRequests: number
  approvedEdits: number
  rejectedEdits: number
  deferredEdits: number
  appliedEdits: number
  revertedEdits: number
  /** Top friction kinds across all signals */
  topFrictionKinds: Array<{ kind: FrictionKind; count: number }>
  /** Files most frequently targeted by edit requests */
  topTargetFiles: Array<{ file: string; count: number }>
}
