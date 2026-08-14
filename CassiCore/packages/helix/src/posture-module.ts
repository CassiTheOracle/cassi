/**
 * PostureModule — Helix postures as first-class cognitive modules.
 *
 * Wraps a HelixPosture definition so it can participate in the brain's
 * Global Workspace: publish CognitiveSignals (work, findings, challenges,
 * nudges, concessions) and receive broadcast of signals that matter to it.
 *
 * Instances are session-scoped and created by the Helix pipeline; they are
 * not registered with the IntelligenceRegistry. Each instance has a unique
 * `name` of the form `helix-{role}-{roleId}` for signal attribution.
 *
 * Correlation metadata on every published signal keeps threads linked across
 * postures (e.g. Unity work unit → Yang finding → Unity concession share a
 * correlation id visible in any downstream observer).
 */

import { BaseCognitiveModule } from '@cassicore/foundation'
import type { CognitiveSignal, SignalType } from './vendor/core/intelligence/workspace/index.js'
import type { ILogger } from '@cassicore/foundation'
import type { HelixPosture, HelixRole } from './types.js'


export interface PostureModuleOpts {
  posture: HelixPosture
  sessionId: string
  /** Short unique id for this posture instance (e.g. a session suffix). */
  roleId: string
  /** Optional priority for workspace-level ordering. Default 50. */
  priority?: number
}


export interface PostureSignalOpts {
  /** Thread id linking related signals across postures. */
  correlation?: string
  /** Target posture name when a signal is directed (e.g. nudges to Unity). */
  recipient?: string
  /** Semantic kind inside the SignalType (e.g. 'work-unit', 'finding'). */
  kind?: string
  /** Extra urgency beyond the SignalType baseline (0-1). */
  urgencyHint?: number
  /** Additional metadata merged into the published signal. */
  extra?: Record<string, unknown>
}


export interface PostureModuleStats {
  submitted: number
  ignited: number
  queued: number
}


export class PostureModule extends BaseCognitiveModule {
  readonly name: string
  readonly priority: number

  readonly posture: HelixPosture
  readonly sessionId: string
  readonly roleId: string
  readonly role: HelixRole

  private _broadcastQueue: CognitiveSignal[] = []
  private _broadcastWaiters: Array<(signals: CognitiveSignal[]) => void> = []
  private _signalsSubmitted = 0
  private _signalsIgnited = 0
  private _stopped = false

  constructor(logger: ILogger, opts: PostureModuleOpts) {
    const childLogger = logger.child
      ? logger.child(`posture-${opts.posture.name}-${opts.roleId}`)
      : logger
    super(childLogger)
    this.posture = opts.posture
    this.sessionId = opts.sessionId
    this.roleId = opts.roleId
    this.role = opts.posture.name
    this.name = `helix-${opts.posture.name}-${opts.roleId}`
    this.priority = opts.priority ?? 50
  }

  async stop(): Promise<void> {
    this._stopped = true
    this._broadcastQueue = []
    const waiters = this._broadcastWaiters
    this._broadcastWaiters = []
    for (const cb of waiters) {
      try { cb([]) } catch { /* best-effort */ }
    }
    await super.stop()
  }

  /**
   * Publish a cognitive signal into the Global Workspace.
   *
   * Returns true if the signal crossed the ignition threshold and entered the
   * workspace. If no GlobalWorkspace is wired, returns false and the call
   * becomes a no-op — safe to use when brainIntegration is disabled.
   */
  publish(
    type: SignalType,
    content: string,
    opts: PostureSignalOpts = {},
  ): boolean {
    if (this._stopped) return false
    if (!this.globalWorkspace) return false

    const metadata: Record<string, unknown> = {
      helix: true,
      sessionId: this.sessionId,
      posture: this.role,
      roleId: this.roleId,
      ...(opts.extra ?? {}),
    }
    if (opts.correlation !== undefined) metadata.correlation = opts.correlation
    if (opts.recipient !== undefined) metadata.recipient = opts.recipient
    if (opts.kind !== undefined) metadata.kind = opts.kind

    this._signalsSubmitted++
    const ignited = this.submitSignal(type, content, this.sessionId, {
      urgencyHint: opts.urgencyHint,
      metadata,
    })
    if (ignited) this._signalsIgnited++
    return ignited
  }

  getStats(): PostureModuleStats {
    return {
      submitted: this._signalsSubmitted,
      ignited: this._signalsIgnited,
      queued: this._broadcastQueue.length,
    }
  }

  /**
   * Pop all queued broadcasts without blocking. Called by the posture loop
   * when it wants a non-blocking peek at recent activity from other postures.
   */
  drainBroadcasts(): CognitiveSignal[] {
    const out = this._broadcastQueue
    this._broadcastQueue = []
    return out
  }

  /**
   * Await the next batch of relevant broadcasts, up to `timeoutMs`. Returns
   * an empty array on timeout. Intended for Phase C when postures replace
   * WorkStream/DialecticChannel reads with broadcast consumption.
   */
  async awaitBroadcast(timeoutMs = 1_000): Promise<CognitiveSignal[]> {
    if (this._broadcastQueue.length > 0) return this.drainBroadcasts()
    if (this._stopped) return []

    return new Promise<CognitiveSignal[]>(resolve => {
      const cb = (signals: CognitiveSignal[]) => {
        clearTimeout(timer)
        resolve(signals)
      }
      const timer = setTimeout(() => {
        const idx = this._broadcastWaiters.indexOf(cb)
        if (idx >= 0) this._broadcastWaiters.splice(idx, 1)
        resolve([])
      }, timeoutMs)
      this._broadcastWaiters.push(cb)
    })
  }

  protected override onWorkspaceBroadcast(
    signals: CognitiveSignal[],
  ): void {
    if (this._stopped) return

    const relevant = signals.filter(sig => this.isRelevant(sig))
    if (relevant.length === 0) return

    this._broadcastQueue.push(...relevant)

    const waiters = this._broadcastWaiters
    this._broadcastWaiters = []
    for (const cb of waiters) {
      try { cb(relevant) } catch { /* best-effort */ }
    }
  }

  private isRelevant(sig: CognitiveSignal): boolean {
    if (sig.sessionId !== this.sessionId && sig.sessionId !== '*') return false
    if (sig.source === this.name) return false
    const recipient = sig.metadata?.recipient
    if (typeof recipient === 'string' && recipient.length > 0) {
      if (recipient === this.name) return true
      if (recipient === this.role) return true
      return false
    }
    return true
  }
}


/**
 * Factory helper — creates a PostureModule for a HelixPosture. Keeping this
 * separate from the class lets call sites stay readable when constructing
 * several postures in sequence (see helix-pipeline.ts).
 */
export function createPostureModule(
  logger: ILogger,
  posture: HelixPosture,
  sessionId: string,
  roleId: string,
  priority?: number,
): PostureModule {
  return new PostureModule(logger, { posture, sessionId, roleId, priority })
}
