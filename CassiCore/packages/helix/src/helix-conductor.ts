/**
 * HelixConductor — Lifecycle owner for brain-integrated Helix sessions.
 *
 * Phase B scope: orchestrates the pieces added by the new design without
 * yet changing how the Helix pipeline *decides* to terminate or *curates*
 * attention. What the Conductor does today:
 *
 *   - Creates / owns three PostureModules (unity, yang, yin) per session.
 *   - Wires each PostureModule to the GlobalWorkspace + EventBus.
 *   - Owns the HelixTelemetry sink (session + posture-turn spans, metrics).
 *   - Owns the HelixJournal append-only log (every signal, ignition,
 *     broadcast, and lifecycle transition persisted).
 *   - Owns the HelixSessionStore snapshot writer (periodic state dumps
 *     for crash-recovery / resume).
 *   - Subscribes to GlobalWorkspace broadcasts and journals them as
 *     `workspace.broadcast` entries scoped to this session.
 *
 * The Helix pipeline delegates to this when `brainIntegration: true` and
 * a GlobalWorkspace is provided; the legacy path (flag off) is untouched.
 *
 * Future phases will extend this class without changing its public API:
 *   Phase D — HelixLocus scoring + kindle.spark / kindle.radiate journaling.
 *   Phase E — MnemicBridge engram writes + Aurora observation + Pineal.
 *   Phase F — Quiescence-based termination detection.
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { CognitiveSignal, GlobalWorkspace } from './vendor/core/intelligence/workspace/index.js'
import type { HelixPosture } from './types.js'

import { PostureModule } from './posture-module.js'
import { HelixTelemetry } from './helix-telemetry.js'
import { HelixJournal, getSharedHelixJournal } from './helix-journal.js'
import type { HelixJournalEntry } from './helix-journal.js'
import { HelixSessionStore, getSharedHelixSessionStore } from './helix-session-store.js'
import type { HelixSnapshotState } from './helix-session-store.js'
import { UNITY_POSTURE, YANG_POSTURE, YIN_POSTURE } from './helix-postures.js'
import { HelixLocus } from './helix-locus.js'
import type { HelixLocusOpts } from './helix-locus.js'
import { HelixMnemicBridge } from './helix-mnemic-bridge.js'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { Aurora } from '@cassicore/aurora'
import type { LaminaField } from '@cassicore/lamina-locus-bridge'
import { appendCoordinationLine } from './vendor/core/intelligence/constellation/helix-goal-lamina.js'
import { HelixQuiescenceDetector } from './helix-quiescence.js'
import type { HelixQuiescenceConfig, HelixQuiescenceReport } from './helix-quiescence.js'


export interface HelixConductorOpts {
  sessionId: string
  goal: string
  logger: ILogger
  globalWorkspace: GlobalWorkspace
  eventBus?: IEventBus
  /** Inject an existing telemetry sink; a fresh one is created otherwise. */
  telemetry?: HelixTelemetry
  /** Inject a journal; a fresh one is created otherwise (shared across sessions). */
  journal?: HelixJournal
  /** Inject a session store; a fresh one is created otherwise. */
  sessionStore?: HelixSessionStore
  /** Override the posture roster. Defaults to UNITY/YANG/YIN. */
  postures?: HelixPosture[]
  /** Snapshot cadence in ms. Default 30s. Set to 0 to disable. */
  snapshotIntervalMs?: number
  /**
   * Unique suffix appended to posture names (e.g. `helix-unity-{roleId}`).
   * Defaults to first 8 chars of sessionId.
   */
  roleId?: string
  /**
   * HelixLocus options — session-scoped kindling. When unset, the
   * Conductor creates a HelixLocus with default weights / threshold.
   * Set to `false` to disable kindling entirely.
   */
  locus?: Partial<HelixLocusOpts> | false
  /**
   * Mnemic Field — when provided, the Conductor instantiates a
   * HelixMnemicBridge that writes milestone engrams (session, outcome,
   * concern, decision, anomaly) so future sessions can kindle prior
   * reasoning via spreading activation.
   */
  mnemicField?: MnemicField
  /**
   * LaminaField — when provided, bridge signals received from the workspace
   * cause a Coordinating-with-Helix entry to be appended to this Helix's
   * `helix-goal` lamina (intra-Helix territory awareness).
   */
  lamina?: LaminaField
  /**
   * Aurora — when provided, the runner pipes posture reasoning text
   * through `aurora.observeReasoning()` at turn boundaries. The
   * conductor holds the reference so the pipeline can thread it down.
   */
  aurora?: Aurora
  /**
   * Quiescence detection — set to `false` to disable. When a quiescence
   * report fires, the Conductor journals it and invokes `onQuiescence`
   * so the pipeline can trigger orderly cancellation.
   */
  quiescence?: HelixQuiescenceConfig | false
  /**
   * Callback invoked when quiescence (idle or hard-cutoff) is detected.
   * The pipeline typically wires this to its `cancelAll` function.
   */
  onQuiescence?: (report: HelixQuiescenceReport) => void
}


export class HelixConductor {
  readonly sessionId: string
  readonly goal: string
  readonly roleId: string
  readonly telemetry: HelixTelemetry
  readonly journal: HelixJournal
  readonly sessionStore: HelixSessionStore
  readonly locus?: HelixLocus
  readonly mnemicBridge?: HelixMnemicBridge
  readonly aurora?: Aurora
  readonly quiescence?: HelixQuiescenceDetector

  private logger: ILogger
  private locusUnsubs: Array<() => void> = []
  private onQuiescenceCb?: (report: HelixQuiescenceReport) => void
  private globalWorkspace: GlobalWorkspace
  private eventBus?: IEventBus
  private lamina?: LaminaField
  private postures: HelixPosture[]
  private modules: Map<string, PostureModule> = new Map()
  private broadcastUnsub?: () => void
  private snapshotTimer?: ReturnType<typeof setInterval>
  private readonly snapshotIntervalMs: number
  private readonly ownsTelemetry: boolean
  private readonly ownsJournal: boolean
  private readonly ownsSessionStore: boolean
  private startedAt?: string
  private lastActivityAt: string
  private status: 'created' | 'starting' | 'running' | 'stopping' | 'stopped' = 'created'


  constructor(opts: HelixConductorOpts) {
    this.sessionId = opts.sessionId
    this.goal = opts.goal
    this.logger = opts.logger.child
      ? opts.logger.child(`helix-conductor:${opts.sessionId.slice(0, 8)}`)
      : opts.logger
    this.globalWorkspace = opts.globalWorkspace
    this.eventBus = opts.eventBus
    this.lamina = opts.lamina
    this.postures = opts.postures ?? [UNITY_POSTURE, YANG_POSTURE, YIN_POSTURE]
    this.snapshotIntervalMs = opts.snapshotIntervalMs ?? 30_000
    this.roleId = opts.roleId ?? opts.sessionId.slice(0, 8)
    this.lastActivityAt = new Date().toISOString()

    this.ownsTelemetry = !opts.telemetry
    // Shared singletons — the Conductor doesn't own their lifecycle, the
    // daemon does. Only close them when an injected non-shared instance is
    // provided (i.e. never in production).
    this.ownsJournal = false
    this.ownsSessionStore = false

    this.telemetry = opts.telemetry ?? new HelixTelemetry(this.logger)
    this.journal = opts.journal ?? getSharedHelixJournal(this.logger)
    this.sessionStore = opts.sessionStore ?? getSharedHelixSessionStore(this.logger)

    this.telemetry.setJournal(this.journal)
    if (this.eventBus) this.telemetry.setEventBus(this.eventBus)

    if (opts.locus !== false) {
      this.locus = new HelixLocus({
        sessionId: this.sessionId,
        logger: this.logger,
        ...(opts.locus ?? {}),
      })
      this.wireLocusJournaling()
    }

    if (opts.mnemicField) {
      this.mnemicBridge = new HelixMnemicBridge({
        sessionId: this.sessionId,
        goal: this.goal,
        logger: this.logger,
        mnemicField: opts.mnemicField,
        journal: this.journal,
        locus: this.locus,
        roleId: this.roleId,
      })
    }

    this.aurora = opts.aurora

    if (opts.quiescence !== false) {
      this.quiescence = new HelixQuiescenceDetector({
        sessionId: this.sessionId,
        logger: this.logger,
        journal: this.journal,
        locus: this.locus,
        config: opts.quiescence,
      })
      this.onQuiescenceCb = opts.onQuiescence
      this.quiescence.onQuiescence((report) => this.handleQuiescence(report))
    }
  }


  private handleQuiescence(report: HelixQuiescenceReport): void {
    try {
      this.journal.append({
        sessionId: this.sessionId,
        eventType: 'diagnostic',
        payload: {
          kind: 'quiescence.detected',
          reason: report.reason,
          sessionAgeMs: report.sessionAgeMs,
          idleDurationMs: report.idleDurationMs,
          liveKindles: report.liveKindles,
        },
      })
    } catch { /* best-effort */ }

    if (this.onQuiescenceCb) {
      try { this.onQuiescenceCb(report) } catch (err) {
        this.logger.warn('onQuiescence callback failed', { error: String(err) })
      }
    }
  }


  private wireLocusJournaling(): void {
    if (!this.locus) return
    this.locusUnsubs.push(
      this.locus.on({
        kind: 'kindle',
        handler: (event) => {
          try {
            this.journal.append({
              sessionId: this.sessionId,
              eventType: 'kindle.spark',
              postureId: event.postureId,
              correlationId: event.correlation,
              payload: {
                signalId: event.signalId,
                kind: event.kind,
                audience: event.audience,
                ttlMs: event.ttlMs,
                score: event.score,
              },
            })
          } catch { /* best-effort */ }
        },
      }),
    )
    this.locusUnsubs.push(
      this.locus.on({
        kind: 'radiance',
        handler: (event) => {
          try {
            this.journal.append({
              sessionId: this.sessionId,
              eventType: 'kindle.radiate',
              payload: {
                signalId: event.signalId,
                sparkId: event.sparkId,
                reason: event.reason,
              },
            })
          } catch { /* best-effort */ }
        },
      }),
    )
  }


  async start(): Promise<void> {
    if (this.status !== 'created') return
    this.status = 'starting'

    this.startedAt = new Date().toISOString()
    this.lastActivityAt = this.startedAt

    this.telemetry.startSession(this.sessionId, { goal: this.goal.slice(0, 200), roleId: this.roleId })
    this.journal.append({
      sessionId: this.sessionId,
      eventType: 'session.start',
      payload: { goal: this.goal.slice(0, 500), roleId: this.roleId, postures: this.postures.map(p => p.name) },
    })

    if (this.mnemicBridge) {
      try {
        await this.mnemicBridge.start()
      } catch (err) {
        this.logger.warn('MnemicBridge start failed', { error: String(err) })
      }
    }

    this.quiescence?.start()

    for (const posture of this.postures) {
      const mod = new PostureModule(this.logger, {
        posture,
        sessionId: this.sessionId,
        roleId: this.roleId,
      })
      if (this.eventBus) mod.setEventBus(this.eventBus)
      mod.setGlobalWorkspace(this.globalWorkspace)

      try {
        await mod.init()
        await mod.start()
      } catch (err) {
        this.logger.warn('PostureModule start failed', { name: mod.name, error: String(err) })
      }

      this.modules.set(posture.name, mod)
      this.telemetry.registerPostureSession(mod.name, this.sessionId)
      this.journal.append({
        sessionId: this.sessionId,
        eventType: 'posture.lifecycle',
        postureId: mod.name,
        payload: { phase: 'started', role: posture.name },
      })
    }

    this.broadcastUnsub = this.globalWorkspace.onBroadcast((signals) => {
      this.handleBroadcast(signals)
    })

    if (this.snapshotIntervalMs > 0) {
      this.snapshotTimer = setInterval(() => {
        try { this.takeSnapshot() } catch (err) {
          this.logger.debug('snapshot tick failed', { error: String(err) })
        }
      }, this.snapshotIntervalMs)
      // Don't hold the process alive for the snapshot timer.
      if (typeof (this.snapshotTimer as any)?.unref === 'function') {
        (this.snapshotTimer as any).unref()
      }
    }

    this.status = 'running'
    this.logger.info('Conductor started', {
      sessionId: this.sessionId,
      postures: [...this.modules.keys()],
      journal: this.journal.getDbPath(),
      snapshots: this.sessionStore.getDbPath(),
    })
  }


  async stop(outcome: 'ok' | 'error' = 'ok', error?: string): Promise<void> {
    if (this.status === 'stopped' || this.status === 'stopping') return
    this.status = 'stopping'

    if (this.broadcastUnsub) {
      try { this.broadcastUnsub() } catch { /* best-effort */ }
      this.broadcastUnsub = undefined
    }
    if (this.snapshotTimer) {
      clearInterval(this.snapshotTimer)
      this.snapshotTimer = undefined
    }
    this.quiescence?.stop()

    // Drain any live kindles so their radiance events get journaled.
    if (this.locus) {
      try { this.locus.drain() } catch { /* best-effort */ }
    }
    for (const unsub of this.locusUnsubs) {
      try { unsub() } catch { /* best-effort */ }
    }
    this.locusUnsubs = []

    if (this.mnemicBridge) {
      try { await this.mnemicBridge.stop(outcome) } catch (err) {
        this.logger.warn('MnemicBridge stop failed', { error: String(err) })
      }
    }

    for (const [role, mod] of this.modules) {
      try {
        await mod.stop()
      } catch (err) {
        this.logger.warn('PostureModule stop failed', { name: mod.name, error: String(err) })
      }
      this.telemetry.unregisterPostureSession(mod.name)
      this.journal.append({
        sessionId: this.sessionId,
        eventType: 'posture.lifecycle',
        postureId: mod.name,
        payload: { phase: 'stopped', role },
      })
    }
    this.modules.clear()

    this.journal.append({
      sessionId: this.sessionId,
      eventType: 'session.terminate',
      payload: { outcome, error, durationMs: this.computeDurationMs() },
    })

    this.telemetry.endSession(this.sessionId, outcome, {
      error,
      durationMs: this.computeDurationMs(),
    })

    try {
      this.takeSnapshot()
    } catch (err) {
      this.logger.debug('final snapshot failed', { error: String(err) })
    }

    if (this.ownsTelemetry) this.telemetry.shutdown()
    if (this.ownsJournal) this.journal.close()
    if (this.ownsSessionStore) this.sessionStore.close()

    this.status = 'stopped'
    this.logger.info('Conductor stopped', { sessionId: this.sessionId, outcome })
  }


  /**
   * Set / replace the quiescence callback after construction. The pipeline
   * uses this because `cancelAll` is assembled after the Conductor is
   * instantiated.
   */
  setOnQuiescence(callback: (report: HelixQuiescenceReport) => void): void {
    this.onQuiescenceCb = callback
  }


  /**
   * The PostureModules this Conductor is managing. The Helix pipeline
   * threads these into each HelixPostureRunner so dual-publish writes
   * land in the GlobalWorkspace (and the journal via the telemetry sink).
   */
  getPostureModules(): Record<string, PostureModule | undefined> {
    const out: Record<string, PostureModule | undefined> = {}
    for (const [role, mod] of this.modules) out[role] = mod
    return out
  }


  /**
   * Take an ad-hoc snapshot right now. Used by the SSE endpoint's
   * `GET .../snapshot` response and the `finally` clause on stop.
   */
  takeSnapshot(): void {
    const state: HelixSnapshotState = {
      seq: this.journal.countSession(this.sessionId),
      postures: [...this.modules.values()].map(m => ({
        name: m.name,
        role: m.role,
        roleId: m.roleId,
        ...m.getStats(),
      })),
      metrics: this.telemetry.getMetricsSnapshot() as unknown as Record<string, unknown>,
      conductor: {
        startedAt: this.startedAt ?? new Date().toISOString(),
        lastActivityAt: this.lastActivityAt,
        status: this.status === 'running' ? 'running' : 'terminated',
      },
    }

    this.sessionStore.saveSnapshot(this.sessionId, state)
    this.journal.append({
      sessionId: this.sessionId,
      eventType: 'snapshot.taken',
      payload: { seq: state.seq, postures: state.postures.length },
    })
  }


  private handleBroadcast(signals: CognitiveSignal[]): void {
    const relevant = signals.filter(s =>
      s.sessionId === this.sessionId || s.sessionId === '*',
    )
    if (relevant.length === 0) return

    this.lastActivityAt = new Date().toISOString()

    // One journal entry per broadcast tick summarising the slot contents.
    this.journal.append({
      sessionId: this.sessionId,
      eventType: 'workspace.broadcast',
      payload: {
        occupied: relevant.length,
        signals: relevant.map(s => ({
          signalId: s.signalId,
          source: s.source,
          type: s.type,
          luminance: s.luminance?.composite,
          correlation: s.metadata?.correlation,
          recipient: s.metadata?.recipient,
          kind: s.metadata?.kind,
        })),
      },
    })

    // Phase D — feed each signal to the HelixLocus. Scoring + kindle
    // emission happens inside; the Conductor's registered listener turns
    // kindle events into journal entries.
    if (this.locus) {
      for (const signal of relevant) {
        try { this.locus.observe(signal) } catch (err) {
          this.logger.debug('locus.observe failed', { error: String(err) })
        }
      }
    }

    // Territory awareness (PR-2 of helix-goal-lamina): bridge signals from the
    // Corpus get a Coordinating-with-Helix line appended to this Helix's goal
    // lamina. FIFO-capped at 5 augmentation lines combined with mentor flags.
    if (this.lamina) {
      for (const signal of relevant) {
        if (signal.type !== 'bridge') continue
        const md = signal.metadata as Record<string, unknown> | undefined
        const peerHelixId = typeof md?.peerHelixId === 'string' ? md.peerHelixId : undefined
        const sharedFiles = Array.isArray(md?.sharedFiles)
          ? md.sharedFiles.filter((f): f is string => typeof f === 'string')
          : []
        if (!peerHelixId) continue
        appendCoordinationLine(this.lamina, this.sessionId, peerHelixId, sharedFiles)
      }
    }
  }


  private computeDurationMs(): number {
    if (!this.startedAt) return 0
    return Date.parse(new Date().toISOString()) - Date.parse(this.startedAt)
  }
}


/**
 * Convenience predicate for pipeline code: are we in a brain-integrated
 * configuration that warrants booting a Conductor?
 */
export function shouldUseConductor(opts: {
  brainIntegration?: boolean
  globalWorkspace?: GlobalWorkspace
}): boolean {
  return Boolean(opts.brainIntegration && opts.globalWorkspace)
}


/**
 * Exposed for observability surfaces and tests. Returns the typed entry;
 * callers can re-export to Observatory views.
 */
export type { HelixJournalEntry }
