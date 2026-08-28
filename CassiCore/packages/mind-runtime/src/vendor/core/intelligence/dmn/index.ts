/**
 * DMN — Default Mode Network.
 *
 * Daemon-scoped singleton that attaches a DmnInstance to each
 * user-facing main session. Each instance runs its own AGOP tick loop:
 * polls the session substrate, records activity into a scheduler,
 * fires the dialectic when the threshold is crossed, caches the
 * synthesis for injection into the next main-session turn's system
 * prompt.
 *
 * AGOP follows the constellation pattern (cluster-observer-layer,
 * corpus-observer-layer). Observation is autonomous and ambient — the
 * session does not push turn-end events at the DMN; the DMN samples
 * session state at its own cadence.
 *
 * Public surface:
 *   - setActivitySnapshotProvider(fn): inject the substrate sampler
 *   - setOnFire(handler): inject the dialectic call (late-bound)
 *   - attachSession(sessionId): create and start a tick-looping instance
 *   - detachSession(sessionId): stop the instance
 *   - getContextInjection(sessionId): formatted observers block for the
 *     next system prompt (empty string when no signal cached)
 *
 * Lifecycle: created on daemon boot, disposed on daemon shutdown.
 */

import type { ILogger } from '@cassicore/foundation'

import type { ObserverActivityConfig, ObserverFireReason } from '@cassicore/helix'

import { DmnInstance, type SessionActivitySnapshot, type SessionActivitySnapshotProvider } from './instance.js'
import { formatObserversBlock } from './system-prompt-injection.js'
import type { DigestSynthesis } from './digest-cache.js'

export type { DigestSynthesis } from './digest-cache.js'
export type { SessionActivitySnapshot, SessionActivitySnapshotProvider } from './instance.js'


export interface DmnConfig {
  enabled: boolean
  /** Tick cadence for the AGOP poll loop. */
  pollIntervalMs: number
  /** Scheduler config: cooldown, idle ceiling, materialThreshold, warmup. */
  scheduler: ObserverActivityConfig
}


export const DEFAULT_DMN_SCHEDULER_CONFIG: ObserverActivityConfig = {
  cooldownMs: 30_000,
  maxIdleMs: 300_000,
  materialThreshold: 3,
  warmupEvents: 2,
  observerId: 'dmn',
}

export const DEFAULT_DMN_CONFIG: DmnConfig = {
  enabled: false,
  pollIntervalMs: 8_000,
  scheduler: DEFAULT_DMN_SCHEDULER_CONFIG,
}


export interface DmnOpts {
  logger: ILogger
  config?: Partial<DmnConfig>
  /**
   * Per-session firing hook. Default no-op; the daemon-boot wiring late-binds
   * this to dialecticSystem.processTurn() once providers are ready.
   */
  onFire?: (reason: ObserverFireReason, sessionId: string) => Promise<DigestSynthesis | null>
  /**
   * Substrate sampler used by every instance's AGOP tick loop. Optional at
   * construction; install via setActivitySnapshotProvider when sessionStore
   * is available. Sessions attached before the provider is set are queued
   * and started when the provider lands.
   */
  getActivitySnapshot?: SessionActivitySnapshotProvider
}


export class Dmn {
  private logger: ILogger
  private config: DmnConfig
  private onFire?: (reason: ObserverFireReason, sessionId: string) => Promise<DigestSynthesis | null>
  private snapshotProvider?: SessionActivitySnapshotProvider
  private instances = new Map<string, DmnInstance>()
  private pendingAttachments = new Set<string>()

  /**
   * Activity snapshots for sessions that aren't managed by the daemon's
   * SessionManager (CC proxy sessions). Populated via POST /dmn/sessions/.../activity
   * from the proxy bridge. Checked as fallback after the primary provider.
   */
  private externalSnapshots = new Map<string, SessionActivitySnapshot>()

  /** Last-access timestamps for auto-attached CC proxy sessions. Used for TTL-based staleness sweep. */
  private autoAttachedLastAccess = new Map<string, number>()
  private static readonly AUTO_ATTACH_TTL_MS = 10 * 60 * 1000  // 10 min


  constructor(opts: DmnOpts) {
    this.logger = opts.logger.child?.('dmn') ?? opts.logger
    this.config = {
      enabled: opts.config?.enabled ?? DEFAULT_DMN_CONFIG.enabled,
      pollIntervalMs: opts.config?.pollIntervalMs ?? DEFAULT_DMN_CONFIG.pollIntervalMs,
      scheduler: { ...DEFAULT_DMN_SCHEDULER_CONFIG, ...opts.config?.scheduler },
    }
    this.onFire = opts.onFire
    this.snapshotProvider = opts.getActivitySnapshot
    if (this.config.enabled) {
      this.logger.info('DMN enabled', {
        pollIntervalMs: this.config.pollIntervalMs,
        materialThreshold: this.config.scheduler.materialThreshold,
        cooldownMs: this.config.scheduler.cooldownMs,
      })
    } else {
      this.logger.info('DMN disabled (no-op)')
    }
  }


  /** Whether the DMN is enabled by config. */
  get enabled(): boolean {
    return this.config.enabled
  }


  /**
   * Install (or replace) the substrate sampler. Binds the daemon's
   * SessionManager as the primary source and falls back to external
   * snapshots (pushed from the CC proxy) for sessions the daemon doesn't
   * manage directly.
   *
   * Sessions attached before this call were queued; they start their tick
   * loops now.
   */
  setActivitySnapshotProvider(provider: SessionActivitySnapshotProvider): void {
    const wrapped: SessionActivitySnapshotProvider = (sessionId) => {
      const primary = provider(sessionId)
      if (primary) return primary
      return this.externalSnapshots.get(sessionId) ?? null
    }
    this.snapshotProvider = wrapped

    // Update already-running instances with the new wrapped provider
    for (const inst of this.instances.values()) {
      inst.setActivitySnapshotProvider(wrapped)
    }

    if (this.pendingAttachments.size > 0) {
      const queued = Array.from(this.pendingAttachments)
      this.pendingAttachments.clear()
      for (const sid of queued) this.doAttach(sid)
    }
  }


  /**
   * Record a session activity snapshot pushed from an external process
   * (the CC proxy bridge). Auto-attaches the session and feeds activity
   * into the AGOP scheduler so the DMN can observe without polling the
   * daemon's SessionManager.
   */
  recordActivity(sessionId: string, snapshot: SessionActivitySnapshot): void {
    this.externalSnapshots.set(sessionId, snapshot)
    this.autoAttachedLastAccess.set(sessionId, Date.now())
    let instance = this.instances.get(sessionId)
    if (!instance) {
      // Auto-attach: CC proxy sessions hit activity push before digest
      // request, so we may not have an AGOP instance yet. Create one now
      // so the scheduler starts accumulating activity events.
      this.attachSession(sessionId)
      instance = this.instances.get(sessionId)
    }
    if (instance) {
      instance.recordExternalActivity()
    }
  }

  /**
   * Return the last activity snapshot for a CC proxy session, or null
   * when this session has never pushed external activity.
   */
  getExternalSnapshot(sessionId: string): SessionActivitySnapshot | null {
    return this.externalSnapshots.get(sessionId) ?? null
  }


  /**
   * Install (or replace) the per-fire handler. Existing instances pick up
   * the new handler on their next fire.
   */
  setOnFire(onFire: (reason: ObserverFireReason, sessionId: string) => Promise<DigestSynthesis | null>): void {
    this.onFire = onFire
    for (const inst of this.instances.values()) {
      inst.setOnFire(onFire)
    }
  }


  /**
   * Attach an instance to a newly-created user-facing main session. If the
   * snapshot provider hasn't been installed yet, the attach is queued and
   * starts when the provider lands.
   */
  attachSession(sessionId: string): void {
    if (!this.config.enabled) return
    if (this.instances.has(sessionId)) return
    if (!this.snapshotProvider) {
      this.pendingAttachments.add(sessionId)
      return
    }
    this.doAttach(sessionId)
  }


  /**
   * Stop and dispose the instance for an ended session. Safe to call for
   * unknown or pending sessionIds.
   */
  async detachSession(sessionId: string): Promise<void> {
    this.pendingAttachments.delete(sessionId)
    this.externalSnapshots.delete(sessionId)
    this.autoAttachedLastAccess.delete(sessionId)
    const instance = this.instances.get(sessionId)
    if (!instance) return
    this.instances.delete(sessionId)
    await instance.stop()
    this.logger.debug('DMN detached', { sessionId })
  }


  /**
   * Return the formatted `<observers>` block for the next main-session
   * turn's system prompt. Empty string when no signal is cached or the
   * session is not attached.
   */
  getContextInjection(sessionId: string): string {
    let instance = this.instances.get(sessionId)
    if (!instance) {
      // Auto-attach: CC proxy sessions aren't created through the daemon's
      // SessionManager so they never fire session:created. Wire them on
      // first access instead.
      this.attachSession(sessionId)
      instance = this.instances.get(sessionId)
      if (!instance) return ''
    }
    this.autoAttachedLastAccess.set(sessionId, Date.now())
    // Sweep stale auto-attached sessions (proxy sessions the daemon's
    // SessionManager doesn't track — they'd otherwise live forever).
    this.sweepStaleAutoAttached()
    // Feed the external-digest request into the AGOP scheduler — the proxy
    // requesting a digest IS activity, independent of the daemon's SessionManager.
    instance.recordExternalActivity()
    return formatObserversBlock(instance.getDigest())
  }


  /** Telemetry. */
  stats(): { sessions: number; pending: number; perSession: Record<string, ReturnType<DmnInstance['stats']>> } {
    const perSession: Record<string, ReturnType<DmnInstance['stats']>> = {}
    for (const [sid, inst] of this.instances) {
      perSession[sid] = inst.stats()
    }
    return { sessions: this.instances.size, pending: this.pendingAttachments.size, perSession }
  }


  /** Tear down all instances. Called on daemon shutdown. */
  async dispose(): Promise<void> {
    this.pendingAttachments.clear()
    this.externalSnapshots.clear()
    this.autoAttachedLastAccess.clear()
    const instances = Array.from(this.instances.values())
    this.instances.clear()
    await Promise.all(instances.map(inst => inst.stop()))
  }

  /**
   * Detach auto-attached sessions whose last access is older than the TTL.
   * Called on every getContextInjection() — amortized cheap.
   */
  private sweepStaleAutoAttached(): void {
    const cutoff = Date.now() - Dmn.AUTO_ATTACH_TTL_MS
    const stale: string[] = []
    for (const [sid, ts] of this.autoAttachedLastAccess) {
      if (ts < cutoff) stale.push(sid)
    }
    for (const sid of stale) {
      void this.detachSession(sid)
    }
  }


  private doAttach(sessionId: string): void {
    if (!this.snapshotProvider) return
    const instance = new DmnInstance({
      sessionId,
      logger: this.logger,
      schedulerConfig: this.config.scheduler,
      pollIntervalMs: this.config.pollIntervalMs,
      getActivitySnapshot: this.snapshotProvider,
      onFire: this.onFire,
    })
    this.instances.set(sessionId, instance)
    instance.start()
    this.logger.debug('DMN attached', { sessionId })
  }
}


export function createDmn(opts: DmnOpts): Dmn {
  return new Dmn(opts)
}
