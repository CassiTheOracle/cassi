/**
 * HelixMnemicBridge — Writes Mnemic Field engrams for milestone events in
 * brain-integrated Helix sessions.
 *
 * Mirrors the existing meditation MnemicBridge pattern (core/intelligence/
 * meditation/mnemic-bridge.ts) at session granularity. When the Conductor
 * reports session lifecycle transitions and the HelixLocus emits kindle
 * events, this bridge persists each one as a typed engram so spreading
 * activation can surface the reasoning in future related sessions.
 *
 * Engram type mapping:
 *
 *   session start       → `session`    (root engram; everything links to it)
 *   work-unit kindle    → `outcome`    (part_of the session)
 *   challenge kindle    → `concern`    (part_of the session)
 *   concession kindle   → `decision`   (mitigates the matching concern)
 *   mentor-flag kindle  → `anomaly`    (part_of the session)
 *   finding kindle      → `abstraction` (part_of the session)
 *
 * Phase E scope: best-effort writes. When Mnemic Field throws, we log and
 * continue — a failed engram never blocks the Helix session. Journal
 * entries (`engram.write`) make the writes observable even if they
 * quietly fail on the Mnemic Field side.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { MnemicField } from '../mnemic-field/index.js'
import type { EngramType, SynapseType } from '../mnemic-field/types.js'
import type { HelixKindleEvent } from './helix-locus.js'
import type { HelixLocus } from './helix-locus.js'
import type { HelixJournal } from './helix-journal.js'


export interface HelixMnemicBridgeOpts {
  sessionId: string
  goal: string
  logger: ILogger
  mnemicField: MnemicField
  journal?: HelixJournal
  locus?: HelixLocus
  roleId?: string
}


/** Subset of kindle.kind values that should become engrams. */
const KINDLE_ENGRAM_MAP: Record<string, { nodeType: EngramType; synapseType?: SynapseType }> = {
  'work-unit': { nodeType: 'outcome', synapseType: 'part_of' },
  'finding': { nodeType: 'abstraction', synapseType: 'part_of' },
  'challenge': { nodeType: 'concern', synapseType: 'part_of' },
  'concession': { nodeType: 'decision', synapseType: 'mitigates' },
  'mentor-flag': { nodeType: 'anomaly', synapseType: 'part_of' },
  'investigation-request': { nodeType: 'goal', synapseType: 'part_of' },
}


export class HelixMnemicBridge {
  readonly sessionId: string

  private logger: ILogger
  private mnemicField: MnemicField
  private journal?: HelixJournal
  private locus?: HelixLocus
  private goal: string
  private roleId?: string

  private sessionEngramId?: string
  private correlationToEngram = new Map<string, string>()
  private unsubscribers: Array<() => void> = []
  private written = 0
  private failed = 0


  constructor(opts: HelixMnemicBridgeOpts) {
    this.sessionId = opts.sessionId
    this.logger = opts.logger.child
      ? opts.logger.child(`helix-mnemic:${opts.sessionId.slice(0, 8)}`)
      : opts.logger
    this.mnemicField = opts.mnemicField
    this.journal = opts.journal
    this.locus = opts.locus
    this.goal = opts.goal
    this.roleId = opts.roleId
  }


  async start(): Promise<void> {
    // Root session engram. Everything else links back to it with `part_of`.
    try {
      const engram = this.mnemicField.store({
        nodeType: 'session',
        content: `Helix session: ${this.goal.slice(0, 500)}`,
        tags: ['helix', 'session', `session:${this.sessionId}`, `role:${this.roleId ?? ''}`],
        provenance: 'helix',
        metadata: {
          sessionId: this.sessionId,
          goal: this.goal,
          roleId: this.roleId,
          status: 'running',
          startedAt: new Date().toISOString(),
        },
      })
      this.sessionEngramId = engram.id
      this.written++
      this.journalWrite('session', engram.id, { sessionId: this.sessionId, engramId: engram.id })
    } catch (err) {
      this.failed++
      this.logger.warn('session engram write failed', { error: String(err), sessionId: this.sessionId })
    }

    if (this.locus) {
      this.unsubscribers.push(
        this.locus.on({
          kind: 'kindle',
          handler: (event) => { this.onKindle(event) },
        }),
      )
    }
  }


  async stop(outcome: 'ok' | 'error' = 'ok'): Promise<void> {
    for (const unsub of this.unsubscribers) {
      try { unsub() } catch { /* best-effort */ }
    }
    this.unsubscribers = []

    if (this.sessionEngramId) {
      try {
        this.mnemicField.store({
          nodeType: 'session',
          content: `Helix session complete (${outcome}): ${this.goal.slice(0, 500)}`,
          tags: ['helix', 'session-end', `session:${this.sessionId}`],
          provenance: 'helix',
          metadata: {
            sessionId: this.sessionId,
            goal: this.goal,
            outcome,
            written: this.written,
            failed: this.failed,
            endedAt: new Date().toISOString(),
            precedingSessionEngramId: this.sessionEngramId,
          },
        })
        this.written++
      } catch (err) {
        this.failed++
        this.logger.warn('session-end engram write failed', { error: String(err), sessionId: this.sessionId })
      }
    }
  }


  getStats(): { written: number; failed: number; sessionEngramId?: string } {
    return { written: this.written, failed: this.failed, sessionEngramId: this.sessionEngramId }
  }


  private onKindle(event: HelixKindleEvent): void {
    const mapping = KINDLE_ENGRAM_MAP[event.kind]
    if (!mapping) return

    let engramId: string | undefined
    // Snapshot the prior correlation target *before* storing the new engram
    // so a concession's `mitigates` synapse points at the challenge, not
    // at itself.
    const priorCorrelationTarget = event.correlation
      ? this.correlationToEngram.get(event.correlation)
      : undefined

    try {
      const engram = this.mnemicField.store({
        nodeType: mapping.nodeType,
        content: this.buildContent(event),
        tags: ['helix', event.kind, `session:${this.sessionId}`, `posture:${event.postureId}`, ...(event.correlation ? [`correlation:${event.correlation}`] : [])],
        provenance: 'helix',
        initialPotentiation: Math.max(0.1, event.score.composite),
        metadata: {
          sessionId: this.sessionId,
          signalId: event.signalId,
          postureId: event.postureId,
          kind: event.kind,
          correlation: event.correlation,
          luminance: event.score.composite,
          ignitedAt: event.timestamp,
        },
      })
      engramId = engram.id
      this.written++
      // Only the first engram to claim a correlation is recorded as the
      // canonical target — subsequent siblings reference it instead of
      // replacing it (e.g. a concession should wire to its challenge).
      if (event.correlation && !this.correlationToEngram.has(event.correlation)) {
        this.correlationToEngram.set(event.correlation, engram.id)
      }
    } catch (err) {
      this.failed++
      this.logger.debug('engram write failed', { error: String(err), kind: event.kind })
      return
    }

    // Link to session root.
    if (this.sessionEngramId && engramId && mapping.synapseType) {
      try {
        this.mnemicField.connect({
          sourceId: engramId,
          targetId: mapping.synapseType === 'mitigates'
            ? priorCorrelationTarget ?? this.sessionEngramId
            : this.sessionEngramId,
          edgeType: mapping.synapseType,
          weight: event.score.composite,
          metadata: { correlation: event.correlation, kind: event.kind },
        })
      } catch (err) {
        this.logger.debug('synapse write failed', { error: String(err), kind: event.kind })
      }
    }

    this.journalWrite(mapping.nodeType, engramId, {
      sessionId: this.sessionId,
      signalId: event.signalId,
      kind: event.kind,
      correlation: event.correlation,
    })
  }


  private buildContent(event: HelixKindleEvent): string {
    const correlationTag = event.correlation ? ` [${event.correlation}]` : ''
    return `[${event.kind}] from ${event.postureId}${correlationTag}`
  }


  private journalWrite(nodeType: string, engramId: string | undefined, payload: Record<string, unknown>): void {
    if (!this.journal) return
    try {
      this.journal.append({
        sessionId: this.sessionId,
        eventType: 'engram.write',
        payload: { nodeType, engramId, ...payload },
      })
    } catch { /* best-effort */ }
  }
}
