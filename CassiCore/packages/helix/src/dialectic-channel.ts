/**
 * DialecticChannel — Shared communication substrate between Yang, Yin, and Executive.
 *
 * Provides real-time, tool-result-injected communication between concurrent postures:
 * - Yang and Yin share findings, challenges, and concessions
 * - Executive injects context (memories, past decisions) and advisory steering
 * - Every tool result gets pending messages appended automatically
 * - Challenge hard-gate: postures must resolve challenges before concluding
 *
 * Thread-safe by virtue of Node.js single-threaded event loop —
 * no locks needed, just careful async-safe append-only data structures.
 */

// Types

export type Posture = 'yang' | 'yin' | 'executive' | 'mentor'

export type DialecticMessage =
  | FindingMessage
  | ChallengeMessage
  | ConcessionMessage
  | InvestigationRequestMessage
  | InvestigationNoticeMessage
  | ExecutiveContextMessage
  | ExecutiveSteeringMessage
  | MentorSteeringMessage
  | EditProposalMessage
  | EditReviewMessage

export interface FindingMessage {
  type: 'finding'
  id: string
  from: Posture
  text: string
  evidence?: string
  tags: string[]
  timestamp: number
}

export interface ChallengeMessage {
  type: 'challenge'
  id: string
  from: Posture
  targetId: string
  counterargument: string
  evidence?: string
  resolved: boolean
  timestamp: number
}

export interface ConcessionMessage {
  type: 'concession'
  id: string
  from: Posture
  challengeId: string
  reason?: string
  timestamp: number
}

export interface InvestigationRequestMessage {
  type: 'investigation_request'
  id: string
  from: Posture
  area: string
  reason: string
  timestamp: number
}

export interface InvestigationNoticeMessage {
  type: 'investigation_notice'
  from: Posture
  resource: string
  timestamp: number
}

export interface ExecutiveContextMessage {
  type: 'executive_context'
  target: 'yang' | 'yin' | 'both'
  content: string
  source?: string
  timestamp: number
}

export interface ExecutiveSteeringMessage {
  type: 'executive_steering'
  target: 'yang' | 'yin' | 'both'
  instruction: string
  reason?: string
  timestamp: number
}

export interface MentorSteeringMessage {
  type: 'mentor_steering'
  directive: string
  target: 'yang' | 'yin' | 'both' | 'unity'
  category: 'steer' | 'flag' | 'force_conclusion' | 'synthesize'
  issueType?: string
  timestamp: number
}

/**
 * Edit Proposal — Yang or Yin proposes a file edit through the dialectic.
 * Must be approved by the peer posture, then by the Brainstem, before being applied.
 *
 * Flow: Propose → Peer Review → Brainstem Gate → Apply
 */
export interface EditProposalMessage {
  type: 'edit_proposal'
  id: string
  from: Posture
  filePath: string
  oldContent: string
  newContent: string
  reason: string
  /** Current approval state */
  status: EditProposalStatus
  /** ID of the peer review message (set after review) */
  reviewId?: string
  timestamp: number
}

export type EditProposalStatus =
  | 'proposed'           // Initial state — waiting for peer review
  | 'peer-approved'      // Peer posture approved — waiting for Brainstem
  | 'peer-rejected'      // Peer posture rejected — edit will not be applied
  | 'brainstem-approved'  // Brainstem approved — ready to apply
  | 'brainstem-rejected'  // Brainstem rejected — edit will not be applied
  | 'applied'            // Edit has been successfully applied
  | 'apply-failed'       // Edit application failed (e.g., oldContent not found)

/**
 * Edit Review — Peer posture's review of an edit proposal.
 */
export interface EditReviewMessage {
  type: 'edit_review'
  id: string
  from: Posture
  /** ID of the edit proposal being reviewed */
  proposalId: string
  /** Whether the peer approves */
  approved: boolean
  /** Reason for approval/rejection */
  reason: string
  /** Suggested modifications (if partially approving) */
  suggestedChanges?: string
  timestamp: number
}


import type { IEventBus } from '../../../types/interfaces.js'


export interface ConvergencePoint {
  topic: string
  yangFindingId: string
  yinChallengeId: string
  concessionFrom: Posture
  resolution: string
}

export interface UnresolvedTension {
  yangPosition: string
  yinPosition: string
  challengeChain: string[]
}


export interface ExecutiveSummary {
  convergencePoints: ConvergencePoint[]
  unresolvedTensions: UnresolvedTension[]
  investigationsConducted: Array<{
    resource: string
    investigatedBy: Posture[]
    relatedFindings: string[]
  }>
  yangConclusion: string
  yangKeyPoints: string[]
  yangConfidence: number
  yinConclusion: string
  yinKeyPoints: string[]
  yinConfidence: number
  executiveInjections: number
  messageCount: number
  challengeCount: number
  concessionCount: number
}


export interface PostureConclusion {
  conclusion: string
  confidence: number
  keyPoints: string[]
  timestamp: number
}


export interface PostureHealthRecord {
  state: 'not-started' | 'running' | 'concluded' | 'errored'
  lastActiveAt: number // Date.now() timestamp
  error?: string
}

// DialecticChannel

export class DialecticChannel {
  /** All messages in chronological order */
  private messages: DialecticMessage[] = []

  /** Maximum messages before oldest non-challenge messages are evicted */
  private readonly maxMessages: number

  /** Per-posture drain cursors — how far each has read */
  private cursors: Record<Posture, number> = { yang: 0, yin: 0, executive: 0, mentor: 0 }

  /** Investigation registry: resource → records of who investigated it */
  private investigations = new Map<string, Array<{ posture: Posture; timestamp: number }>>()

  /** Conclusion tracking for each posture */
  private conclusions = new Map<Posture, PostureConclusion>()

  /** Per-posture health tracking */
  private postureHealth: Record<Posture, PostureHealthRecord> = {
    yang: { state: 'not-started', lastActiveAt: 0 },
    yin: { state: 'not-started', lastActiveAt: 0 },
    executive: { state: 'not-started', lastActiveAt: 0 },
    mentor: { state: 'not-started', lastActiveAt: 0 },
  }

  /** Optional event bus for real-time message flow to cognitive-feed topics */
  private readonly eventBus?: IEventBus
  private readonly sessionId?: string

  /** Monotonic ID counters */
  private findingCounter = 0
  private challengeCounter = 0
  private concessionCounter = 0
  private requestCounter = 0

  /** Event counter since last Executive drain (for pacing boost) */
  private eventsSinceExecutiveDrain = 0

  private report: import('../../../types/flux-team.js').Report | null = null
  private reportSectionCounter = 0

  constructor(maxMessages = 500, eventBus?: IEventBus, sessionId?: string) {
    this.maxMessages = maxMessages
    this.eventBus = eventBus
    this.sessionId = sessionId
  }

  /** Emit a dialectic event on the bus if available */
  private emitDialecticEvent(type: string, data: Record<string, unknown>): void {
    if (!this.eventBus) return
    try {
      void this.eventBus.emit({ type, sessionId: this.sessionId, ...data } as any)
    } catch { /* ignore bus emit errors */ }
  }

  /** Evict oldest non-challenge messages when cap is hit */
  private evictIfNeeded(): void {
    while (this.messages.length > this.maxMessages) {
      // Never evict unresolved challenges — they're needed for the hard gate
      const evictIdx = this.messages.findIndex(m =>
        m.type !== 'challenge' || (m.type === 'challenge' && m.resolved),
      )
      if (evictIdx < 0) break // all remaining are unresolved challenges
      this.messages.splice(evictIdx, 1)
      // Adjust cursors
      for (const posture of ['yang', 'yin', 'executive'] as Posture[]) {
        if (this.cursors[posture] > evictIdx) {
          this.cursors[posture]--
        }
      }
    }
  }


  /**
   * Report that a posture has started running.
   * Sets state to 'running' and updates lastActiveAt.
   */
  reportPostureStarted(posture: Posture): void {
    this.postureHealth[posture].state = 'running'
    this.postureHealth[posture].lastActiveAt = Date.now()
  }

  /**
   * Report a heartbeat from a posture.
   * Updates lastActiveAt to indicate the posture is still active.
   */
  reportPostureHeartbeat(posture: Posture): void {
    this.postureHealth[posture].lastActiveAt = Date.now()
  }

  /**
   * Sanitize error string to prevent log injection and memory exhaustion.
   * Truncates to 500 chars and removes control characters.
   */
  private sanitizeErrorString(error: string): string {
    // Truncate to 500 chars to prevent memory exhaustion
    const truncated = error.slice(0, 500)
    // Remove control characters and ANSI escape sequences
    const sanitized = truncated
      .replace(/\x1b\[[0-9;]*m/g, '') // ANSI escape codes
      .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, '') // Control chars
      .replace(/\n/g, ' ') // Newlines to spaces
      .replace(/\r/g, '') // Carriage returns
      .trim()
    return sanitized
  }

  /**
   * Report that a posture has errored.
   * Sets state to 'errored' and stores the sanitized error message.
   */
  reportPostureError(posture: Posture, error: unknown): void {
    const errorString = error instanceof Error ? error.message : String(error)
    const sanitizedError = this.sanitizeErrorString(errorString)
    this.postureHealth[posture].state = 'errored'
    this.postureHealth[posture].error = sanitizedError
    this.postureHealth[posture].lastActiveAt = Date.now()
  }

  /**
   * Get current health status for all postures.
   * Returns a copy of the health records.
   */
   getPostureHealth(): Record<Posture, PostureHealthRecord> {
    return {
      yang: { ...this.postureHealth.yang },
      yin: { ...this.postureHealth.yin },
      executive: { ...this.postureHealth.executive },
      mentor: { ...this.postureHealth.mentor },
    }
  }

  /**
   * Format health status for display in tool results.
   * Returns a human-readable string showing posture health.
   */
  formatHealthStatus(): string {
    const now = Date.now()
    const lines: string[] = ['## Posture Health']

    for (const posture of ['yang', 'yin', 'executive'] as Posture[]) {
      const health = this.postureHealth[posture]
      const timeAgo = health.lastActiveAt > 0 ? ((now - health.lastActiveAt) / 1000).toFixed(1) + 's ago' : 'never'

      if (health.state === 'errored') {
        lines.push(`${posture.charAt(0).toUpperCase() + posture.slice(1)}: ERRORED | stopped ${timeAgo}${health.error ? ` | error: ${health.error.slice(0, 100)}` : ''}`)
      } else if (health.state === 'running') {
        lines.push(`${posture.charAt(0).toUpperCase() + posture.slice(1)}: running | last active: ${timeAgo}`)
      } else if (health.state === 'concluded') {
        lines.push(`${posture.charAt(0).toUpperCase() + posture.slice(1)}: concluded | last active: ${timeAgo}`)
      } else {
        lines.push(`${posture.charAt(0).toUpperCase() + posture.slice(1)}: not-started`)
      }
    }

    return lines.join('\n')
  }


  /**
   * Post a finding visible to the other posture.
   * Returns the finding ID for reference in challenges.
   */
  postFinding(from: Posture, text: string, evidence?: string, tags: string[] = []): string {
    const id = `f${++this.findingCounter}`
    const msg: FindingMessage = {
      type: 'finding',
      id,
      from,
      text,
      evidence,
      tags,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.eventsSinceExecutiveDrain++
    this.evictIfNeeded()

    // Auto-draft a report section from this finding
    this.autoDraftFromFinding(from, id, text, evidence ? [evidence] : undefined)

    // Emit finding event for real-time topic flow
    this.emitDialecticEvent('lumen:dialectic:finding', {
      from,
      id,
      text: text.slice(0, 500),
      evidence: evidence?.slice(0, 200),
      tags,
    })

    return id
  }

  /**
   * Challenge a specific finding from the other posture.
   * Creates an unresolved tension that must be addressed before concluding.
   */
  postChallenge(from: Posture, targetFindingId: string, counterargument: string, evidence?: string): string {
    const id = `c${++this.challengeCounter}`
    const msg: ChallengeMessage = {
      type: 'challenge',
      id,
      from,
      targetId: targetFindingId,
      counterargument,
      evidence,
      resolved: false,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.eventsSinceExecutiveDrain++
    this.evictIfNeeded()

    // Auto-draft a concern from this challenge
    this.autoDraftFromChallenge(from, id, counterargument, targetFindingId)

    // Emit challenge event for real-time topic flow
    this.emitDialecticEvent('lumen:dialectic:challenge', {
      from,
      id,
      targetFindingId,
      counterargument: counterargument.slice(0, 500),
      evidence: evidence?.slice(0, 200),
    })

    return id
  }

  /**
   * Concede a challenge — resolves the tension and records a convergence point.
   */
  postConcession(from: Posture, challengeId: string, reason?: string): string {
    const id = `x${++this.concessionCounter}`
    const msg: ConcessionMessage = {
      type: 'concession',
      id,
      from,
      challengeId,
      reason,
      timestamp: Date.now(),
    }
    this.messages.push(msg)

    // Mark the challenge as resolved
    for (const m of this.messages) {
      if (m.type === 'challenge' && m.id === challengeId) {
        m.resolved = true
        break
      }
    }

    this.eventsSinceExecutiveDrain++
    this.evictIfNeeded()

    // Auto-draft a decision from this concession
    this.autoDraftFromConcession(from, id, reason ?? 'Conceded challenge', challengeId)

    // Emit concession event for real-time topic flow
    this.emitDialecticEvent('lumen:dialectic:concession', {
      from,
      id,
      challengeId,
      reason: reason?.slice(0, 300),
    })

    return id
  }

  /**
   * Request the other posture investigate a specific area.
   */
  postInvestigationRequest(from: Posture, area: string, reason: string): string {
    const id = `r${++this.requestCounter}`
    const msg: InvestigationRequestMessage = {
      type: 'investigation_request',
      id,
      from,
      area,
      reason,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.eventsSinceExecutiveDrain++
    this.evictIfNeeded()

    // Emit investigation request event for real-time topic flow
    this.emitDialecticEvent('lumen:dialectic:investigation', {
      from,
      id,
      area: area.slice(0, 200),
      reason: reason.slice(0, 200),
    })

    return id
  }



  /**
   * Yang or Yin proposes a file edit through the dialectic channel.
   * The proposal enters the approval pipeline:
   *   Propose → Peer Review → Brainstem Gate → Apply
   */
  postEditProposal(
    from: Posture,
    filePath: string,
    oldContent: string,
    newContent: string,
    reason: string,
  ): string {
    const id = `ep-${++this.requestCounter}`
    const msg: EditProposalMessage = {
      type: 'edit_proposal',
      id,
      from,
      filePath,
      oldContent,
      newContent,
      reason,
      status: 'proposed',
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.eventsSinceExecutiveDrain++
    this.evictIfNeeded()

    this.emitDialecticEvent('lumen:dialectic:edit-proposal', {
      from,
      id,
      filePath,
      reason: reason.slice(0, 200),
    })

    return id
  }

  /**
   * Peer posture reviews an edit proposal (approve or reject).
   */
  postEditReview(
    from: Posture,
    proposalId: string,
    approved: boolean,
    reason: string,
    suggestedChanges?: string,
  ): string {
    const id = `er-${++this.requestCounter}`
    const msg: EditReviewMessage = {
      type: 'edit_review',
      id,
      from,
      proposalId,
      approved,
      reason,
      suggestedChanges,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.eventsSinceExecutiveDrain++
    this.evictIfNeeded()

    // Update the proposal's status
    const proposal = this.messages.find(
      (m) => m.type === 'edit_proposal' && m.id === proposalId,
    ) as EditProposalMessage | undefined
    if (proposal) {
      proposal.status = approved ? 'peer-approved' : 'peer-rejected'
      proposal.reviewId = id
    }

    this.emitDialecticEvent('lumen:dialectic:edit-review', {
      from,
      id,
      proposalId,
      approved,
      reason: reason.slice(0, 200),
    })

    return id
  }

  /**
   * Get all pending edit proposals (proposed or peer-approved, awaiting next gate).
   */
  getPendingEditProposals(): EditProposalMessage[] {
    return this.messages.filter(
      (m): m is EditProposalMessage =>
        m.type === 'edit_proposal' &&
        (m.status === 'proposed' || m.status === 'peer-approved'),
    )
  }

  /**
   * Update a proposal's status (called by Brainstem or apply mechanism).
   */
  updateEditProposalStatus(proposalId: string, status: EditProposalStatus): void {
    const proposal = this.messages.find(
      (m) => m.type === 'edit_proposal' && m.id === proposalId,
    ) as EditProposalMessage | undefined
    if (proposal) {
      proposal.status = status
    }
  }


  /**
   * Executive injects relevant context (memories, past decisions) to posture(s).
   */
  injectContext(target: 'yang' | 'yin' | 'both', content: string, source?: string): void {
    const msg: ExecutiveContextMessage = {
      type: 'executive_context',
      target,
      content,
      source,
      timestamp: Date.now(),
    }
    this.messages.push(msg)

    // Emit executive injection event for real-time topic flow
    this.emitDialecticEvent('lumen:dialectic:executive-injection', {
      target,
      content: content.slice(0, 500),
      source,
    })
  }

  /**
   * Executive suggests an investigation direction (advisory, not binding).
   */
  injectSteering(target: 'yang' | 'yin' | 'both', instruction: string, reason?: string): void {
    const msg: ExecutiveSteeringMessage = {
      type: 'executive_steering',
      target,
      instruction,
      reason,
      timestamp: Date.now(),
    }
    this.messages.push(msg)

    // Emit executive steering event for real-time topic flow
    this.emitDialecticEvent('lumen:dialectic:executive-steering', {
      target,
      instruction: instruction.slice(0, 500),
      reason: reason?.slice(0, 200),
    })
  }

  /**
   * Mentor injects a steering directive, flag, force_conclusion, or synthesis.
   * Routed through DialecticChannel so Yang/Yin receive it as tool-result-injected text.
   */
  injectMentorSteering(
    target: 'yang' | 'yin' | 'both' | 'unity',
    directive: string,
    category: 'steer' | 'flag' | 'force_conclusion' | 'synthesize',
    issueType?: string,
  ): void {
    const msg: MentorSteeringMessage = {
      type: 'mentor_steering',
      directive,
      target,
      category,
      issueType,
      timestamp: Date.now(),
    }
    this.messages.push(msg)

    this.emitDialecticEvent('helix:mentor:steering' as any, {
      target,
      category,
      directive: directive.slice(0, 500),
      issueType,
    })
  }


  /**
   * Record that a posture is investigating a resource.
   * Returns a notice string if the other posture has already investigated it.
   */
  registerInvestigation(posture: Posture, resource: string): string | undefined {
    const records = this.investigations.get(resource) ?? []
    records.push({ posture, timestamp: Date.now() })
    this.investigations.set(resource, records)

    // Emit investigation notice to channel
    const notice: InvestigationNoticeMessage = {
      type: 'investigation_notice',
      from: posture,
      resource,
      timestamp: Date.now(),
    }
    this.messages.push(notice)

    // Check if the other posture already investigated this
    const others = records.filter(r => r.posture !== posture)
    if (others.length > 0) {
      const otherPosture = others[0].posture
      const relatedFindings = this.getRelatedFindings(resource).filter(f => f.from !== posture)
      if (relatedFindings.length > 0) {
        const findingSummary = relatedFindings
          .map(f => `  [${f.from} finding #${f.id}] ${f.text}`)
          .join('\n')
        return `Note: ${otherPosture} also investigated ${resource} and shared:\n${findingSummary}`
      }
      return `Note: ${otherPosture} is also investigating ${resource}`
    }
    return undefined
  }

  /**
   * Get findings tagged with or mentioning a resource path.
   */
  getRelatedFindings(resource: string): FindingMessage[] {
    return this.messages.filter(
      (m): m is FindingMessage =>
        m.type === 'finding' &&
        (m.tags.some(t => resource.includes(t) || t.includes(resource)) ||
          m.text.includes(resource) ||
          (m.evidence?.includes(resource) ?? false)),
    )
  }


  /**
   * Drain all unread messages for a posture, formatted as injectable text.
   * Advances the cursor so messages are only shown once.
   */
  drainForPosture(posture: Posture): string {
    const cursor = this.cursors[posture]
    const pending = this.messages.slice(cursor).filter(m => this.isRelevantTo(m, posture))
    this.cursors[posture] = this.messages.length

    if (posture === 'executive') {
      this.eventsSinceExecutiveDrain = 0
    }

    if (pending.length === 0) return ''

    const sections: string[] = []

    // Group by source
    const fromYang = pending.filter(m => this.isFrom(m, 'yang'))
    const fromYin = pending.filter(m => this.isFrom(m, 'yin'))
    const fromExec = pending.filter(m => this.isFrom(m, 'executive'))
    const fromMentor = pending.filter(m => this.isFrom(m, 'mentor'))

    if (fromYang.length > 0 && posture !== 'yang') {
      sections.push(`\n─── From Yang ───\n${fromYang.map(m => this.formatMessage(m)).join('\n')}`)
    }
    if (fromYin.length > 0 && posture !== 'yin') {
      sections.push(`\n─── From Yin ───\n${fromYin.map(m => this.formatMessage(m)).join('\n')}`)
    }
    if (fromExec.length > 0 && posture !== 'executive') {
      sections.push(`\n─── From Executive ───\n${fromExec.map(m => this.formatMessage(m)).join('\n')}`)
    }
    if (fromMentor.length > 0 && posture !== 'mentor') {
      sections.push(`\n─── From Mentor ───\n${fromMentor.map(m => this.formatMessage(m)).join('\n')}`)
    }

    return sections.join('\n')
  }

  /**
   * Get the number of events since Executive last drained.
   * Used for pacing boost — Executive gets nudged when this exceeds a threshold.
   */
  getEventsSinceExecutiveDrain(): number {
    return this.eventsSinceExecutiveDrain
  }


  /**
   * Check if a posture has unresolved challenges against it.
   * Used by signal_conclusion hard gate.
   */
  hasUnresolvedChallenges(posture: Posture): boolean {
    return this.getUnresolvedChallenges(posture).length > 0
  }

  /**
   * Get unresolved challenges targeting a posture's findings.
   */
  getUnresolvedChallenges(posture: Posture): ChallengeMessage[] {
    // Find all findings by this posture
    const myFindings = new Set(
      this.messages
        .filter((m): m is FindingMessage => m.type === 'finding' && m.from === posture)
        .map(m => m.id),
    )

    // Find unresolved challenges targeting those findings
    return this.messages.filter(
      (m): m is ChallengeMessage =>
        m.type === 'challenge' &&
        !m.resolved &&
        myFindings.has(m.targetId),
    )
  }


  /**
   * Mark a posture as concluded.
   */
  markConcluded(posture: Posture, conclusion: string, confidence: number, keyPoints: string[]): void {
    this.conclusions.set(posture, {
      conclusion,
      confidence,
      keyPoints,
      timestamp: Date.now(),
    })
    this.postureHealth[posture].state = 'concluded'
    this.postureHealth[posture].lastActiveAt = Date.now()
    this.eventsSinceExecutiveDrain++
    this.evictIfNeeded()
  }

  /**
   * Get concluded status for all postures.
   */
  getConcludedStatus(): { yang: boolean; yin: boolean; executive: boolean } {
    return {
      yang: this.conclusions.has('yang'),
      yin: this.conclusions.has('yin'),
      executive: this.conclusions.has('executive'),
    }
  }

  /**
   * Get conclusion for a specific posture.
   */
  getConclusion(posture: Posture): PostureConclusion | undefined {
    return this.conclusions.get(posture)
  }


  /**
   * Build the structured summary for Executive's final synthesis.
   * Contains convergence points, unresolved tensions, conclusions, and metrics.
   */
  buildExecutiveSummary(): ExecutiveSummary {
    const convergencePoints = this.buildConvergencePoints()
    const unresolvedTensions = this.buildUnresolvedTensions()
    const investigationsConducted = this.buildInvestigationsSummary()

    const yangConclusion = this.conclusions.get('yang')
    const yinConclusion = this.conclusions.get('yin')

    const executiveInjections = this.messages.filter(
      m => m.type === 'executive_context' || m.type === 'executive_steering',
    ).length

    return {
      convergencePoints,
      unresolvedTensions,
      investigationsConducted,
      yangConclusion: yangConclusion?.conclusion ?? '(Yang did not conclude)',
      yangKeyPoints: yangConclusion?.keyPoints ?? [],
      yangConfidence: yangConclusion?.confidence ?? 0,
      yinConclusion: yinConclusion?.conclusion ?? '(Yin did not conclude)',
      yinKeyPoints: yinConclusion?.keyPoints ?? [],
      yinConfidence: yinConclusion?.confidence ?? 0,
      executiveInjections,
      messageCount: this.messages.length,
      challengeCount: this.messages.filter(m => m.type === 'challenge').length,
      concessionCount: this.messages.filter(m => m.type === 'concession').length,
    }
  }


  /**
   * Get the full message log with concluded status.
   * Used by Executive's review_dialectic_log tool.
   */
  getFullLog(): {
    messages: DialecticMessage[]
    concluded: { yang: boolean; yin: boolean }
    conclusions: { yang?: PostureConclusion; yin?: PostureConclusion }
    stats: { findings: number; challenges: number; concessions: number; unresolvedChallenges: number }
    postureHealth: Record<Posture, PostureHealthRecord>
  } {
    const unresolvedChallenges = this.messages.filter(
      (m): m is ChallengeMessage => m.type === 'challenge' && !m.resolved,
    ).length

    return {
      messages: [...this.messages],
      concluded: {
        yang: this.conclusions.has('yang'),
        yin: this.conclusions.has('yin'),
      },
      conclusions: {
        yang: this.conclusions.get('yang'),
        yin: this.conclusions.get('yin'),
      },
      stats: {
        findings: this.messages.filter(m => m.type === 'finding').length,
        challenges: this.messages.filter(m => m.type === 'challenge').length,
        concessions: this.messages.filter(m => m.type === 'concession').length,
        unresolvedChallenges,
      },
      postureHealth: this.getPostureHealth(),
    }
  }

  /**
   * Get aggregate statistics for the dialectic session.
   */
  getStats(): {
    findings: number
    challenges: number
    concessions: number
    investigationRequests: number
    executiveInjections: number
  } {
    return {
      findings: this.messages.filter(m => m.type === 'finding').length,
      challenges: this.messages.filter(m => m.type === 'challenge').length,
      concessions: this.messages.filter(m => m.type === 'concession').length,
      investigationRequests: this.messages.filter(m => m.type === 'investigation_request').length,
      executiveInjections: this.messages.filter(
        m => m.type === 'executive_context' || m.type === 'executive_steering',
      ).length,
    }
  }


  /**
   * Check if a message is relevant to a specific posture.
   */
  private isRelevantTo(msg: DialecticMessage, posture: Posture): boolean {
    // Finding, challenge, concession, investigation: relevant to non-sender postures
    if (msg.type === 'finding' || msg.type === 'challenge' || msg.type === 'concession' ||
        msg.type === 'investigation_request' || msg.type === 'investigation_notice') {
      return msg.from !== posture
    }

    // Executive injections: relevant to target posture(s)
    if (msg.type === 'executive_context' || msg.type === 'executive_steering') {
      return msg.target === posture || msg.target === 'both'
    }

    // Mentor steering: relevant to target posture(s), not to mentor itself
    if (msg.type === 'mentor_steering') {
      if (posture === 'mentor') return false
      return msg.target === posture || msg.target === 'both' || msg.target === 'unity'
    }

    return false
  }

  /**
   * Check if a message originates from a specific posture.
   */
  private isFrom(msg: DialecticMessage, posture: Posture): boolean {
    switch (msg.type) {
      case 'finding':
      case 'challenge':
      case 'concession':
      case 'investigation_request':
      case 'investigation_notice':
        return msg.from === posture

      case 'executive_context':
      case 'executive_steering':
        return posture === 'executive'

      case 'mentor_steering':
        return posture === 'mentor'

      default:
        return false
    }
  }

  /**
   * Format a single message for injection into a tool result.
   */
  private formatMessage(msg: DialecticMessage): string {
    switch (msg.type) {
      case 'finding':
        return `[finding #${msg.id}] ${msg.text}${msg.evidence ? `\n              Evidence: ${msg.evidence}` : ''}${msg.tags.length > 0 ? ` Tags: [${msg.tags.join(', ')}]` : ''}`

      case 'challenge':
        return `[challenge #${msg.id} -> finding #${msg.targetId}] ${msg.counterargument}${msg.evidence ? `\n              Evidence: ${msg.evidence}` : ''}`

      case 'concession':
        return `[concession -> challenge #${msg.challengeId}] ${msg.reason ?? 'Point conceded.'}`

      case 'investigation_request':
        return `[investigation request] Please investigate: ${msg.area}\n              Reason: ${msg.reason}`

      case 'investigation_notice':
        return `[investigating] ${msg.from} is investigating ${msg.resource}`

      case 'executive_context':
        return `[context] ${msg.content}${msg.source ? ` (Source: ${msg.source})` : ''}`

      case 'executive_steering':
        return `[suggestion] ${msg.instruction}${msg.reason ? `\n              Reason: ${msg.reason}` : ''}`

      case 'mentor_steering': {
        const prefix = msg.category === 'flag' ? `[mentor flag: ${msg.issueType ?? 'general'}]`
          : msg.category === 'force_conclusion' ? '[mentor → conclusion]'
          : msg.category === 'synthesize' ? '[mentor synthesis]'
          : `[mentor steer → ${msg.target}]`
        return `${prefix} ${msg.directive}`
      }

      default:
        return '[unknown message]'
    }
  }

  /**
   * Build convergence points from resolved challenges.
   */
  buildConvergencePoints(): ConvergencePoint[] {
    const points: ConvergencePoint[] = []

    const concessions = this.messages.filter(
      (m): m is ConcessionMessage => m.type === 'concession',
    )

    for (const concession of concessions) {
      const challenge = this.messages.find(
        (m): m is ChallengeMessage => m.type === 'challenge' && m.id === concession.challengeId,
      )
      if (!challenge) continue

      const finding = this.messages.find(
        (m): m is FindingMessage => m.type === 'finding' && m.id === challenge.targetId,
      )
      if (!finding) continue

      points.push({
        topic: finding.text.slice(0, 100),
        yangFindingId: finding.id,
        yinChallengeId: challenge.id,
        concessionFrom: concession.from,
        resolution: concession.reason ?? 'Conceded without stated reason',
      })
    }

    return points
  }

  /**
   * Build unresolved tensions from unresolved challenges.
   */
  buildUnresolvedTensions(): UnresolvedTension[] {
    const tensions: UnresolvedTension[] = []

    const unresolvedChallenges = this.messages.filter(
      (m): m is ChallengeMessage => m.type === 'challenge' && !m.resolved,
    )

    for (const challenge of unresolvedChallenges) {
      const finding = this.messages.find(
        (m): m is FindingMessage => m.type === 'finding' && m.id === challenge.targetId,
      )
      if (!finding) continue

      tensions.push({
        yangPosition: finding.from === 'yang' ? finding.text : challenge.counterargument,
        yinPosition: finding.from === 'yin' ? finding.text : challenge.counterargument,
        challengeChain: [
          `${finding.from} finding #${finding.id}: ${finding.text}`,
          `${challenge.from} challenge #${challenge.id}: ${challenge.counterargument}`,
        ],
      })
    }

    return tensions
  }

  /**
   * Build investigation summary from the investigation registry.
   */
  private buildInvestigationsSummary(): ExecutiveSummary['investigationsConducted'] {
    const summaries: ExecutiveSummary['investigationsConducted'] = []

    for (const [resource, records] of this.investigations) {
      const postures = [...new Set(records.map(r => r.posture))]
      const relatedFindings = this.getRelatedFindings(resource).map(f => `#${f.id}: ${f.text.slice(0, 80)}`)

      if (postures.length > 0) {
        summaries.push({
          resource,
          investigatedBy: postures,
          relatedFindings,
        })
      }
    }

    return summaries
  }

  // Incremental Report

  /**
   * Initialize the report for this session.
   */
  initReport(goal: string): import('../../../types/flux-team.js').Report {
    const now = Date.now()
    this.report = {
      id: `report-${now}`,
      goal,
      sections: [],
      createdAt: now,
      updatedAt: now,
    }
    return this.report
  }

  /**
   * Add a section to the report.
   */
  addReportSection(section: {
    type: import('../../../types/flux-team.js').ReportSectionType
    status?: import('../../../types/flux-team.js').ReportSectionStatus
    title: string
    content: string
    author: string
    confidence?: number
    references?: string[]
    threadId?: string
    respondsTo?: string
    challenges?: string
    supports?: string
  }): import('../../../types/flux-team.js').ReportSection {
    if (!this.report) this.initReport('')
    const now = Date.now()
    const id = `rs-${++this.reportSectionCounter}`
    const newSection: import('../../../types/flux-team.js').ReportSection = {
      id,
      type: section.type,
      status: section.status ?? 'active',
      title: section.title,
      content: section.content,
      author: section.author,
      confidence: section.confidence,
      references: section.references,
      threadId: section.threadId,
      respondsTo: section.respondsTo,
      challenges: section.challenges,
      supports: section.supports,
      createdAt: now,
      updatedAt: now,
    }
    this.report!.sections.push(newSection)
    this.report!.updatedAt = now
    return newSection
  }

  /**
   * Auto-draft a report section from a dialectic interaction.
   * Creates a section with status='draft' linked to the originating message.
   */
  autoDraftFromFinding(posture: Posture, findingId: string, text: string, evidence?: string[]): void {
    if (!this.report) this.initReport('')
    this.addReportSection({
      type: 'finding',
      status: 'draft',
      title: text.slice(0, 80),
      content: text,
      author: posture,
      references: evidence,
      threadId: findingId,
    })
  }

  autoDraftFromChallenge(posture: Posture, challengeId: string, text: string, targetFindingId: string): void {
    if (!this.report) this.initReport('')
    this.addReportSection({
      type: 'concern',
      status: 'draft',
      title: text.slice(0, 80),
      content: text,
      author: posture,
      threadId: targetFindingId,  // Same thread as the finding being challenged
      challenges: targetFindingId,
    })
  }

  autoDraftFromConcession(posture: Posture, concessionId: string, text: string, challengeId: string): void {
    if (!this.report) this.initReport('')
    this.addReportSection({
      type: 'decision',
      status: 'draft',
      title: text.slice(0, 80),
      content: text,
      author: posture,
      threadId: challengeId,
      respondsTo: challengeId,
    })
  }

  /**
   * Revise an existing section — creates a new active section that supersedes the original.
   */
  reviseReportSection(sectionId: string, content: string, _reason?: string): import('../../../types/flux-team.js').ReportSection | null {
    if (!this.report) return null
    const original = this.report.sections.find(s => s.id === sectionId)
    if (!original) return null

    // Mark original as superseded
    original.superseded = true
    original.status = 'superseded'
    original.updatedAt = Date.now()

    // Create new section that supersedes the original
    return this.addReportSection({
      type: original.type,
      title: original.title,
      content,
      author: original.author,
      confidence: original.confidence,
      references: original.references,
      threadId: original.threadId,
    })
  }

  /**
   * Promote a draft section to active.
   */
  promoteReportSection(sectionId: string): boolean {
    if (!this.report) return false
    const section = this.report.sections.find(s => s.id === sectionId && s.status === 'draft')
    if (!section) return false
    section.status = 'active'
    section.updatedAt = Date.now()
    this.report.updatedAt = Date.now()
    return true
  }

  /**
   * Discard a draft section (only works on drafts).
   * Cascades: removes references to this section from other sections.
   */
  discardReportSection(sectionId: string): boolean {
    if (!this.report) return false
    const idx = this.report.sections.findIndex(s => s.id === sectionId && s.status === 'draft')
    if (idx === -1) return false
    this.report.sections.splice(idx, 1)

    // Cascading cleanup: remove references to the discarded section
    for (const s of this.report.sections) {
      if (s.respondsTo === sectionId) s.respondsTo = undefined
      if (s.challenges === sectionId) s.challenges = undefined
      if (s.supports === sectionId) s.supports = undefined
      if (s.supersedes === sectionId) s.supersedes = undefined
    }

    this.report.updatedAt = Date.now()
    return true
  }

  /**
   * Get the current report.
   */
  getReport(): import('../../../types/flux-team.js').Report | null {
    return this.report
  }

  /**
   * Get filtered report sections.
   */
  getReportView(opts?: {
    filterType?: string
    filterAuthor?: string
    filterStatus?: string
    since?: number
  }): import('../../../types/flux-team.js').ReportSection[] {
    if (!this.report) return []
    let sections = this.report.sections
    if (opts?.filterType) sections = sections.filter(s => s.type === opts.filterType)
    if (opts?.filterAuthor) sections = sections.filter(s => s.author === opts.filterAuthor)
    if (opts?.filterStatus) sections = sections.filter(s => s.status === opts.filterStatus)
    if (opts?.since) sections = sections.filter(s => s.updatedAt > opts.since!)
    return sections
  }

  /**
   * Calculate quality metrics for the report.
   */
  getReportMetrics(): import('../../../types/flux-team.js').ReportQualityMetrics {
    if (!this.report) {
      return {
        totalSections: 0, activeSections: 0, draftSections: 0,
        byType: {}, byAuthor: {}, avgConfidence: 0,
        threadCount: 0, unresolvedConcerns: 0, coverageScore: 0,
      }
    }

    const sections = this.report.sections
    const active = sections.filter(s => s.status === 'active')
    const drafts = sections.filter(s => s.status === 'draft')

    // Count by type
    const byType: Partial<Record<string, number>> = {}
    for (const s of active) {
      byType[s.type] = (byType[s.type] || 0) + 1
    }

    // Count by author
    const byAuthor: Record<string, number> = {}
    for (const s of active) {
      byAuthor[s.author] = (byAuthor[s.author] || 0) + 1
    }

    // Avg confidence
    const withConf = active.filter(s => s.confidence != null)
    const avgConfidence = withConf.length > 0
      ? withConf.reduce((sum, s) => sum + (s.confidence ?? 0), 0) / withConf.length
      : 0

    // Thread count
    const threads = new Set(active.filter(s => s.threadId).map(s => s.threadId))

    // Unresolved concerns: concerns without a linked decision
    const decisionThreads = new Set(
      active.filter(s => s.type === 'decision').map(s => s.threadId).filter(Boolean)
    )
    const unresolvedConcerns = active.filter(
      s => s.type === 'concern' && (!s.threadId || !decisionThreads.has(s.threadId))
    ).length

    // Coverage: how many of the 7 section types are represented?
    const typesUsed = new Set(Object.keys(byType))
    const idealTypes = ['finding', 'concern', 'recommendation']
    const coverageScore = idealTypes.filter(t => typesUsed.has(t)).length / idealTypes.length

    return {
      totalSections: sections.length,
      activeSections: active.length,
      draftSections: drafts.length,
      byType,
      byAuthor,
      avgConfidence: Math.round(avgConfidence * 100) / 100,
      threadCount: threads.size,
      unresolvedConcerns,
      coverageScore: Math.round(coverageScore * 100) / 100,
    }
  }

  /**
   * Format the report for context injection (e.g., at synthesis time).
   */
  formatReportForContext(): string {
    if (!this.report || this.report.sections.length === 0) return ''

    const active = this.report.sections.filter(s => s.status === 'active')
    const drafts = this.report.sections.filter(s => s.status === 'draft')

    if (active.length === 0 && drafts.length === 0) return ''

    const parts: string[] = ['## Incremental Report']

    // Group active sections by type
    const byType = new Map<string, typeof active>()
    for (const s of active) {
      if (!byType.has(s.type)) byType.set(s.type, [])
      byType.get(s.type)!.push(s)
    }

    for (const [type, sections] of byType) {
      parts.push(`\n### ${type.charAt(0).toUpperCase() + type.slice(1)}s`)
      for (const s of sections) {
        const conf = s.confidence != null ? ` (confidence: ${s.confidence})` : ''
        const refs = s.references?.length ? `\n  References: ${s.references.join(', ')}` : ''
        const thread = s.threadId ? ` [thread: ${s.threadId}]` : ''
        parts.push(`- **${s.title}** — by ${s.author}${conf}${thread}\n  ${s.content}${refs}`)
      }
    }

    if (drafts.length > 0) {
      parts.push(`\n### Drafts (${drafts.length} pending review)`)
      for (const s of drafts) {
        parts.push(`- [DRAFT] **${s.title}** — ${s.type} by ${s.author}`)
      }
    }

    return parts.join('\n')
  }
}
