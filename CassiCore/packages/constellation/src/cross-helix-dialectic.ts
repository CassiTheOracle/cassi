/**
 * CrossHelixDialectic — Inter-branch dialectic channel for Constellation.
 *
 * Mirrors the intra-Helix DialecticChannel (Yang ↔ Yin with Executive mediation)
 * but operates between Helix branches:
 *
 *   Branch A ←→ CrossHelixDialectic ←→ Branch B
 *                       ↕
 *                    Corpus (mediator)
 *
 * Findings from one branch become challenges to the other. Convergence points
 * emerge when both branches agree. The Corpus mediates like the Executive does
 * within a single Helix.
 *
 * Delivery: messages are injected into each branch's Brainstem guidance queue
 * as cross-branch dialectic guidance.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { HelixBrainstem } from '../helix/brainstem.js'
import type { CorpusDirective } from './corpus-types.js'

// ─── Message Types ──────────────────────────────────────────────────────

export type CrossHelixParticipant = string  // helixId

export type CrossHelixMessageType =
  | 'cross-finding'
  | 'cross-challenge'
  | 'cross-concession'
  | 'cross-convergence'
  | 'corpus-mediation'

export interface CrossHelixMessage {
  /** Unique message ID */
  id: string
  /** Message type */
  type: CrossHelixMessageType
  /** Which branch sent this */
  from: CrossHelixParticipant
  /** Which branch this targets (or 'all' for broadcast) */
  target: CrossHelixParticipant | 'all'
  /** The content */
  text: string
  /** Optional evidence or context */
  evidence?: string
  /** Optional reference to a message being challenged/conceded */
  referencesId?: string
  /** Tags for categorization */
  tags: string[]
  /** When this was created */
  timestamp: number
}

export interface CrossHelixConvergencePoint {
  /** What the branches agreed on */
  topic: string
  /** The finding that started it */
  findingId: string
  /** The response that confirmed agreement */
  responseId: string
  /** Which branches are converging */
  participants: CrossHelixParticipant[]
  /** When convergence was detected */
  timestamp: number
}

export interface CrossHelixTension {
  /** Branch A's position */
  positionA: { branchId: string; text: string; messageId: string }
  /** Branch B's position */
  positionB: { branchId: string; text: string; messageId: string }
  /** Whether this has been escalated to the Corpus */
  escalatedToCorpus: boolean
  /** When the tension was detected */
  timestamp: number
}

export interface CrossHelixDialecticSnapshot {
  /** All messages in the cross-branch dialectic */
  messages: CrossHelixMessage[]
  /** Detected convergence points */
  convergencePoints: CrossHelixConvergencePoint[]
  /** Unresolved tensions */
  unresolvedTensions: CrossHelixTension[]
  /** Participating branches */
  participants: CrossHelixParticipant[]
  /** Total findings exchanged */
  totalFindings: number
  /** Total challenges issued */
  totalChallenges: number
  /** Total concessions made */
  totalConcessions: number
}

// ─── Configuration ──────────────────────────────────────────────────────

export interface CrossHelixDialecticConfig {
  /** Max messages before oldest are evicted. Default: 200 */
  maxMessages: number
  /** Min confidence/score for a finding to be forwarded cross-branch. Default: 0.5 */
  minFindingScore: number
  /** Sweeps between Corpus mediation injections. Default: 3 */
  mediationCooldownSweeps: number
  /** Whether to auto-detect convergence from finding similarity. Default: true */
  autoDetectConvergence: boolean
}

export const DEFAULT_CROSS_HELIX_DIALECTIC_CONFIG: CrossHelixDialecticConfig = {
  maxMessages: 200,
  minFindingScore: 0.5,
  mediationCooldownSweeps: 3,
  autoDetectConvergence: true,
}

// ─── CrossHelixDialectic ────────────────────────────────────────────────

export class CrossHelixDialectic {
  private messages: CrossHelixMessage[] = []
  private convergencePoints: CrossHelixConvergencePoint[] = []
  private unresolvedTensions: CrossHelixTension[] = []
  private participants = new Map<string, { brainstem: HelixBrainstem; goal: string }>()
  private cursors = new Map<string, number>()  // per-branch read cursor
  private messageIdCounter = 0
  private sweepsSinceMediation = 0
  private readonly config: CrossHelixDialecticConfig
  private readonly logger: ILogger

  constructor(logger: ILogger, config?: Partial<CrossHelixDialecticConfig>) {
    this.config = { ...DEFAULT_CROSS_HELIX_DIALECTIC_CONFIG, ...config }
    this.logger = logger
  }

  // ── Participant Management ──────────────────────────────────────────

  /**
   * Register a branch as a participant in the cross-Helix dialectic.
   * Must be called after the Brainstem is created and started.
   */
  registerBranch(helixId: string, brainstem: HelixBrainstem, goal: string): void {
    this.participants.set(helixId, { brainstem, goal })
    this.cursors.set(helixId, 0)
    this.logger.info('Branch registered for cross-Helix dialectic', {
      helixId,
      goal: goal.slice(0, 100),
      participants: this.participants.size,
    })
  }

  /**
   * Unregister a branch (when it completes or fails).
   */
  unregisterBranch(helixId: string): void {
    this.participants.delete(helixId)
    this.cursors.delete(helixId)
    this.logger.info('Branch unregistered from cross-Helix dialectic', {
      helixId,
      remainingParticipants: this.participants.size,
    })
  }

  // ── Message Posting ─────────────────────────────────────────────────

  /**
   * Post a finding from one branch. This will be forwarded to all other
   * branches as a cross-branch finding they may challenge.
   */
  postFinding(
    fromHelixId: string,
    text: string,
    opts?: { evidence?: string; tags?: string[]; score?: number },
  ): string | null {
    // Filter low-quality findings
    if (opts?.score !== undefined && opts.score < this.config.minFindingScore) {
      return null
    }

    const msg = this.createMessage('cross-finding', fromHelixId, 'all', text, opts)
    this.addMessage(msg)

    // Deliver to all other branches' Brainstems as guidance
    this.deliverToOtherBranches(fromHelixId, msg)

    return msg.id
  }

  /**
   * Post a challenge from one branch to another's finding.
   */
  postChallenge(
    fromHelixId: string,
    targetHelixId: string,
    referencesId: string,
    counterargument: string,
    opts?: { evidence?: string; tags?: string[] },
  ): string {
    const msg = this.createMessage('cross-challenge', fromHelixId, targetHelixId, counterargument, {
      ...opts,
      referencesId,
    })
    this.addMessage(msg)

    // Deliver directly to the challenged branch's Brainstem
    this.deliverToBranch(targetHelixId, msg)

    // Check for tension pattern (challenge-counter-challenge)
    this.detectTensions(msg)

    return msg.id
  }

  /**
   * Post a concession from one branch, accepting another's challenge.
   */
  postConcession(
    fromHelixId: string,
    challengeId: string,
    reason?: string,
  ): string {
    const challengeMsg = this.messages.find((m) => m.id === challengeId)
    const msg = this.createMessage('cross-concession', fromHelixId, challengeMsg?.from ?? 'all',
      reason ?? 'Conceded', { referencesId: challengeId })
    this.addMessage(msg)

    // Concession may create convergence
    if (challengeMsg) {
      this.detectConvergence(msg, challengeMsg)
    }

    return msg.id
  }

  // ── Corpus Mediation ────────────────────────────────────────────────

  /**
   * Called by the Corpus during its sweep to inject mediation.
   * The Corpus reviews the cross-branch dialectic state and can:
   * - Inject steering to resolve tensions
   * - Highlight convergence points
   * - Redirect branches toward productive engagement
   */
  injectCorpusMediation(text: string, target: CrossHelixParticipant | 'all'): void {
    const msg = this.createMessage('corpus-mediation', 'corpus', target, text)
    this.addMessage(msg)

    if (target === 'all') {
      for (const [helixId] of this.participants) {
        this.deliverToBranch(helixId, msg)
      }
    } else {
      this.deliverToBranch(target, msg)
    }

    this.sweepsSinceMediation = 0
  }

  /**
   * Get the current dialectic state for the Corpus's LLM analysis.
   * Returns a formatted summary suitable for prompt inclusion.
   */
  getDialecticSummaryForCorpus(): string | null {
    if (this.messages.length === 0) return null

    const findings = this.messages.filter((m) => m.type === 'cross-finding')
    const challenges = this.messages.filter((m) => m.type === 'cross-challenge')
    const concessions = this.messages.filter((m) => m.type === 'cross-concession')

    const lines: string[] = [
      `## Cross-Branch Dialectic (${this.participants.size} branches)`,
      `Findings: ${findings.length} | Challenges: ${challenges.length} | Concessions: ${concessions.length}`,
    ]

    // Show convergence points
    if (this.convergencePoints.length > 0) {
      lines.push('')
      lines.push(`### Convergence Points (${this.convergencePoints.length})`)
      for (const cp of this.convergencePoints.slice(-5)) {
        lines.push(`- ${cp.topic} (${cp.participants.join(' + ')})`)
      }
    }

    // Show unresolved tensions
    const activeTensions = this.unresolvedTensions.filter((t) => !t.escalatedToCorpus)
    if (activeTensions.length > 0) {
      lines.push('')
      lines.push(`### Unresolved Tensions (${activeTensions.length})`)
      for (const t of activeTensions.slice(-3)) {
        lines.push(`- ${t.positionA.branchId}: "${t.positionA.text.slice(0, 80)}"`)
        lines.push(`  vs ${t.positionB.branchId}: "${t.positionB.text.slice(0, 80)}"`)
      }
    }

    // Show recent messages
    const recent = this.messages.slice(-10)
    if (recent.length > 0) {
      lines.push('')
      lines.push('### Recent Cross-Branch Messages')
      for (const m of recent) {
        const prefix = m.type === 'cross-finding' ? 'FINDING'
          : m.type === 'cross-challenge' ? 'CHALLENGE'
          : m.type === 'cross-concession' ? 'CONCESSION'
          : 'MEDIATION'
        lines.push(`- [${prefix}] ${m.from}: ${m.text.slice(0, 120)}`)
      }
    }

    this.sweepsSinceMediation++
    return lines.join('\n')
  }

  /**
   * Whether the Corpus should inject mediation this sweep.
   */
  shouldMediate(): boolean {
    return this.sweepsSinceMediation >= this.config.mediationCooldownSweeps &&
      (this.unresolvedTensions.filter((t) => !t.escalatedToCorpus).length > 0 ||
       this.messages.length > 0)
  }

  // ── Snapshot ────────────────────────────────────────────────────────

  getSnapshot(): CrossHelixDialecticSnapshot {
    return {
      messages: [...this.messages],
      convergencePoints: [...this.convergencePoints],
      unresolvedTensions: [...this.unresolvedTensions],
      participants: Array.from(this.participants.keys()),
      totalFindings: this.messages.filter((m) => m.type === 'cross-finding').length,
      totalChallenges: this.messages.filter((m) => m.type === 'cross-challenge').length,
      totalConcessions: this.messages.filter((m) => m.type === 'cross-concession').length,
    }
  }

  // ── Internal ────────────────────────────────────────────────────────

  private createMessage(
    type: CrossHelixMessageType,
    from: string,
    target: string,
    text: string,
    opts?: { evidence?: string; tags?: string[]; referencesId?: string },
  ): CrossHelixMessage {
    return {
      id: `chd-${++this.messageIdCounter}`,
      type,
      from,
      target,
      text,
      evidence: opts?.evidence,
      referencesId: opts?.referencesId,
      tags: opts?.tags ?? [],
      timestamp: Date.now(),
    }
  }

  private addMessage(msg: CrossHelixMessage): void {
    this.messages.push(msg)

    // Evict oldest non-challenge messages when over limit
    if (this.messages.length > this.config.maxMessages) {
      const evictCount = Math.floor(this.config.maxMessages * 0.2)
      const evictable = this.messages
        .map((m, i) => ({ msg: m, idx: i }))
        .filter((e) => e.msg.type !== 'cross-challenge' || (e.msg as any).resolved)
        .slice(0, evictCount)

      for (const e of evictable.reverse()) {
        this.messages.splice(e.idx, 1)
      }
    }
  }

  /**
   * Deliver a cross-branch message to all branches except the sender.
   * Injected as Brainstem guidance so it reaches the posture runners.
   */
  private deliverToOtherBranches(senderHelixId: string, msg: CrossHelixMessage): void {
    for (const [helixId, { brainstem }] of this.participants) {
      if (helixId === senderHelixId) continue
      this.injectIntoBrainstem(brainstem, helixId, msg)
    }
  }

  /**
   * Deliver a message to a specific branch's Brainstem.
   */
  private deliverToBranch(helixId: string, msg: CrossHelixMessage): void {
    const participant = this.participants.get(helixId)
    if (!participant) return
    this.injectIntoBrainstem(participant.brainstem, helixId, msg)
  }

  /**
   * Inject a cross-branch message into a Brainstem's guidance queue.
   * The message is formatted to be recognizable as a cross-branch dialectic message.
   */
  private injectIntoBrainstem(
    brainstem: HelixBrainstem,
    targetHelixId: string,
    msg: CrossHelixMessage,
  ): void {
    const prefix = msg.type === 'cross-finding' ? 'CROSS-BRANCH FINDING'
      : msg.type === 'cross-challenge' ? 'CROSS-BRANCH CHALLENGE'
      : msg.type === 'cross-concession' ? 'CROSS-BRANCH CONCESSION'
      : msg.type === 'cross-convergence' ? 'CONVERGENCE DETECTED'
      : 'CORPUS MEDIATION'

    const urgency = msg.type === 'cross-challenge' ? 'high' as const
      : msg.type === 'corpus-mediation' ? 'high' as const
      : 'medium' as const

    const formattedText = `[${prefix} from ${msg.from}]: ${msg.text}` +
      (msg.evidence ? `\nEvidence: ${msg.evidence}` : '') +
      (msg.referencesId ? `\n(Re: message ${msg.referencesId})` : '')

    // Use onCorpusDirective to inject — this bypasses cooldown for high urgency
    brainstem.onCorpusDirective({
      targetHelixId,
      type: 'guidance',
      urgency,
      text: formattedText,
      reason: `cross-helix-dialectic:${msg.type}`,
      timestamp: Date.now(),
    })

    this.logger.debug('Cross-branch message injected', {
      from: msg.from,
      to: targetHelixId,
      type: msg.type,
      textLen: msg.text.length,
    })
  }

  /**
   * Detect convergence when a concession references a challenge that references a finding.
   * This is the cross-branch equivalent of the challenge→concession→convergence chain
   * in the intra-Helix dialectic.
   */
  private detectConvergence(concession: CrossHelixMessage, challenge: CrossHelixMessage): void {
    // Find the original finding that was challenged
    const originalFinding = challenge.referencesId
      ? this.messages.find((m) => m.id === challenge.referencesId)
      : null

    if (originalFinding && originalFinding.from !== concession.from) {
      const cp: CrossHelixConvergencePoint = {
        topic: originalFinding.text.slice(0, 200),
        findingId: originalFinding.id,
        responseId: concession.id,
        participants: [originalFinding.from, concession.from],
        timestamp: Date.now(),
      }
      this.convergencePoints.push(cp)

      // Broadcast convergence to all branches
      const convergenceMsg = this.createMessage(
        'cross-convergence', 'corpus', 'all',
        `Convergence detected: "${cp.topic.slice(0, 100)}" — ` +
        `${cp.participants.join(' and ')} agree.`,
      )
      this.addMessage(convergenceMsg)
      for (const [helixId] of this.participants) {
        this.deliverToBranch(helixId, convergenceMsg)
      }

      this.logger.info('Cross-branch convergence detected', {
        topic: cp.topic.slice(0, 80),
        participants: cp.participants,
      })
    }
  }

  /**
   * Detect tensions when branches disagree — a challenge without concession
   * followed by a counter-challenge.
   */
  private detectTensions(challenge: CrossHelixMessage): void {
    // Check if the challenged branch has already challenged back
    const counterChallenges = this.messages.filter(
      (m) =>
        m.type === 'cross-challenge' &&
        m.from === challenge.target &&
        m.target === challenge.from &&
        m.timestamp > challenge.timestamp - 60000, // Within the last minute
    )

    if (counterChallenges.length > 0) {
      const tension: CrossHelixTension = {
        positionA: {
          branchId: challenge.from,
          text: challenge.text,
          messageId: challenge.id,
        },
        positionB: {
          branchId: counterChallenges[0].from,
          text: counterChallenges[0].text,
          messageId: counterChallenges[0].id,
        },
        escalatedToCorpus: false,
        timestamp: Date.now(),
      }
      this.unresolvedTensions.push(tension)

      this.logger.info('Cross-branch tension detected', {
        branchA: tension.positionA.branchId,
        branchB: tension.positionB.branchId,
      })
    }
  }
}
