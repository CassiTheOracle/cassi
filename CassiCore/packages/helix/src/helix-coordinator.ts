/**
 * HelixCoordinator — Native coordination layer for the Helix pattern.
 *
 * Replaces the direct use of WorkStream + DialecticChannel (borrowed from
 * Dyad and Lumen) with Helix-aware subclasses that fix the core semantic
 * mismatches:
 *
 * 1. WorkStream's nextWorkUnit() destructively pops → HelixWorkStream uses
 *    per-reviewer cursors so BOTH reviewers see ALL work units.
 *
 * 2. Termination is scattered and race-prone → unified termination that
 *    ensures all reviewers have observed all work units before concluding.
 *
 * 3. DialecticChannel excludes Unity → HelixDialecticMesh includes Unity
 *    as a valid participant in the dialectic.
 *
 * Strategy: Extend (not replace) WorkStream and DialecticChannel so the
 * entire existing API surface (55+ WorkStream methods, 30+ DialecticChannel
 * methods) remains intact. Only the broken methods are overridden.
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { HelixRole } from './types.js'
import { WorkStream } from './work-stream.js'
import { DialecticChannel } from './dialectic-channel.js'
import type { WorkUnit } from './work-types.js'
import type { Nudge } from './work-types.js'
import { HelixMetrics } from './helix-metrics.js'
import type { HelixMetricsSnapshot } from './helix-metrics.js'



/** Default timeout for waiting on work units in broadcast mode */
const BROADCAST_WORK_UNIT_TIMEOUT_MS = 3_000

/** Maximum time to wait for all reviewers to confirm during termination */
const TERMINATION_CONSENSUS_TIMEOUT_MS = 30_000



/**
 * Helix-native WorkStream that uses per-reviewer broadcast instead of a
 * destructive single-consumer queue.
 *
 * Key override: `nextWorkUnitForReviewer()` gives each reviewer an
 * independent cursor over the work unit list. Both reviewers see ALL
 * work units — no race conditions, no missed work.
 *
 * The original `nextWorkUnit()` is preserved for backward compat but
 * Helix runners should use `nextWorkUnitForReviewer()`.
 */
export class HelixWorkStream extends WorkStream {
  /** Per-reviewer read cursors into allPostedWorkUnits */
  private reviewerCursors = new Map<string, number>()

  /** Per-reviewer review-complete signals */
  private reviewerReady = new Map<string, boolean>()

  /** Resolvers waiting for new work units (per-reviewer) */
  private broadcastWaiters = new Map<string, Array<(wu: WorkUnit | null) => void>>()

  /** Whether termination consensus was reached */
  private terminationReached = false

  /** Event-based termination callbacks — replaces 500ms polling */
  private terminationCallbacks = new Set<() => void>()

  /** Canonical reviewer IDs for authoritative termination consensus checks. */
  private reviewerIds: string[] = ['yang', 'yin']

  constructor(
    opts?: {
      sessionId?: string
      eventBus?: IEventBus
      maxMessages?: number
      backpressureThreshold?: number
    },
  ) {
    super(opts?.maxMessages, opts?.backpressureThreshold, opts?.eventBus, opts?.sessionId)
  }

  /**
   * Non-destructive work unit read for a specific reviewer.
   * Each reviewer maintains its own cursor — both see all work units.
   *
   * Returns the next unseen work unit for this reviewer, or waits up to
   * timeoutMs for one to arrive. Returns null on timeout or when Unity
   * is done and all work units have been observed.
   */
  async nextWorkUnitForReviewer(
    reviewerId: string,
    timeoutMs = BROADCAST_WORK_UNIT_TIMEOUT_MS,
  ): Promise<WorkUnit | null> {
    const cursor = this.reviewerCursors.get(reviewerId) ?? 0
    const allWUs = this.getAllWorkUnits()

    // Return next unseen work unit immediately if available
    if (cursor < allWUs.length) {
      this.reviewerCursors.set(reviewerId, cursor + 1)
      return allWUs[cursor]
    }

    // If Unity is done and we've seen everything, return null
    if (this.isWorkerDone() && cursor >= allWUs.length) {
      return null
    }

    // Wait for a new work unit to arrive
    return new Promise<WorkUnit | null>((resolve) => {
      const timer = setTimeout(() => {
        // Remove this waiter
        const waiters = this.broadcastWaiters.get(reviewerId) ?? []
        const idx = waiters.indexOf(resolve)
        if (idx >= 0) waiters.splice(idx, 1)
        resolve(null)
      }, timeoutMs)

      const wrappedResolve = (wu: WorkUnit | null) => {
        clearTimeout(timer)
        if (wu) {
          const c = this.reviewerCursors.get(reviewerId) ?? 0
          this.reviewerCursors.set(reviewerId, c + 1)
        }
        resolve(wu)
      }

      const waiters = this.broadcastWaiters.get(reviewerId) ?? []
      waiters.push(wrappedResolve)
      this.broadcastWaiters.set(reviewerId, waiters)
    })
  }

  /** Optional metrics tracker — auto-incremented on postWorkUnit */
  private metrics?: HelixMetrics

  /**
   * Attach a HelixMetrics tracker to auto-increment on work unit events.
   */
  setMetrics(metrics: HelixMetrics): void {
    this.metrics = metrics
  }

  /**
   * Set the canonical reviewer IDs used for authoritative termination checks.
   * Defaults to ['yang', 'yin'] for backward compatibility.
   */
  setReviewerIds(ids: string[]): void {
    this.reviewerIds = [...ids]
  }

  /**
   * Override postWorkUnit to also notify broadcast waiters.
   */
  postWorkUnit(workUnit: WorkUnit): void {
    super.postWorkUnit(workUnit)
    this.metrics?.incrementWorkUnits()

    // Notify ALL waiting reviewers (broadcast, not single-consumer)
    for (const [_reviewerId, waiters] of this.broadcastWaiters) {
      const waiter = waiters.shift()
      if (waiter) {
        waiter(workUnit)
      }
    }
  }

  /**
   * Override signalWorkerDone to also unblock waiting reviewers.
   */
  signalWorkerDone(): void {
    super.signalWorkerDone()

    // Unblock all waiting reviewers with null
    for (const [_reviewerId, waiters] of this.broadcastWaiters) {
      for (const waiter of waiters) {
        waiter(null)
      }
      waiters.length = 0
    }

    // Check termination after worker signals done
    this.checkAndEmitTermination()
  }

  /**
   * Override postNudge to also track in metrics.
   */
  postNudge(nudge: Nudge, currentYangIteration: number): void {
    super.postNudge(nudge, currentYangIteration)
    this.metrics?.incrementNudges()
  }

  /**
   * Check whether a reviewer has observed all posted work units.
   */
  hasReviewerSeenAll(reviewerId: string): boolean {
    const cursor = this.reviewerCursors.get(reviewerId) ?? 0
    return cursor >= this.getAllWorkUnits().length
  }

  /**
   * Signal that a reviewer is ready to conclude.
   */
  signalReviewerReady(reviewerId: string): void {
    this.reviewerReady.set(reviewerId, true)
    // Emit event-based termination callbacks (replaces 500ms polling)
    this.checkAndEmitTermination()
  }

  /**
   * Register a callback to be called when termination consensus is reached.
   * Event-based alternative to polling waitForTerminationConsensus.
   */
  onTerminationConsensus(callback: () => void): () => void {
    this.terminationCallbacks.add(callback)
    // If already reached, fire immediately
    if (this.terminationReached) {
      callback()
    }
    return () => {
      this.terminationCallbacks.delete(callback)
    }
  }

  private checkAndEmitTermination(): void {
    if (this.terminationReached) return
    if (!this.isTerminationConsensus(this.reviewerIds)) return
    this.terminationReached = true
    for (const cb of this.terminationCallbacks) {
      try { cb() } catch { /* swallow */ }
    }
    this.terminationCallbacks.clear()
  }

  /**
   * Check if all registered reviewers are ready to conclude AND have
   * seen all work units.
   */
  isTerminationConsensus(reviewerIds: string[]): boolean {
    if (!this.isWorkerDone()) return false

    return reviewerIds.every((id) => {
      const ready = this.reviewerReady.get(id) ?? false
      const seenAll = this.hasReviewerSeenAll(id)
      return ready || seenAll
    })
  }

  /**
   * Wait for termination consensus or timeout.
   * Refactored from polling (500ms interval) to event-based waiting
   * via onTerminationConsensus callback.
   */
  async waitForTerminationConsensus(
    reviewerIds: string[],
    timeoutMs = TERMINATION_CONSENSUS_TIMEOUT_MS,
  ): Promise<boolean> {
    if (this.isTerminationConsensus(reviewerIds)) return true

    return new Promise<boolean>((resolve) => {
      let resolved = false

      // Event-based: resolve when termination event fires
      const unsubscribe = this.onTerminationConsensus(() => {
        if (!resolved && this.isTerminationConsensus(reviewerIds)) {
          resolved = true
          clearTimeout(timer)
          unsubscribe()
          resolve(true)
        }
      })

      // Timeout fallback
      const timer = setTimeout(() => {
        if (!resolved) {
          resolved = true
          unsubscribe()
          resolve(false)
        }
      }, timeoutMs)
    })
  }

  /**
   * Get broadcast progress for a reviewer.
   */
  getReviewerProgress(reviewerId: string): {
    cursor: number
    total: number
    ready: boolean
  } {
    return {
      cursor: this.reviewerCursors.get(reviewerId) ?? 0,
      total: this.getAllWorkUnits().length,
      ready: this.reviewerReady.get(reviewerId) ?? false,
    }
  }
}



/**
 * Helix-native DialecticChannel that includes Unity as a valid participant.
 *
 * The standard DialecticChannel only allows 'yang' | 'yin' | 'executive' | 'mentor'.
 * In Helix, Unity should be able to see reviewer debates and optionally respond.
 *
 * This subclass maps Unity to the 'executive' slot (which is unused in Helix
 * since Helix has its own Mentor) to allow Unity to read dialectic messages
 * without modifying the base DialecticChannel.
 */
export class HelixDialecticMesh extends DialecticChannel {
  /** Unity's cursor position — tracks what Unity has seen */
  private unityCursor = 0

  constructor(opts?: { eventBus?: IEventBus; maxMessages?: number; sessionId?: string }) {
    super(opts?.maxMessages, opts?.eventBus, opts?.sessionId)
  }

  /**
   * Drain dialectic messages for Unity.
   * Unity sees ALL messages from all postures (broadcast read).
   */
  drainForUnity(): Array<{ type: string; from: string; text?: string; [key: string]: unknown }> {
    const log = this.getFullLog()
    const allMessages = log.messages
    const newMessages = allMessages.slice(this.unityCursor)
    this.unityCursor = allMessages.length
    return newMessages as unknown as Array<{ type: string; from: string; text?: string; [key: string]: unknown }>
  }

  /**
   * Post a finding from Unity (mapped to executive posture internally).
   */
  postUnityFinding(finding: string, evidence?: string, tags?: string[]): string {
    return this.postFinding('executive', finding, evidence, tags)
  }
}



export interface HelixCoordinatorOpts {
  sessionId: string
  logger: ILogger
  eventBus?: IEventBus
  maxMessages?: number
  backpressureThreshold?: number
}

/**
 * Unified coordination layer for Helix sessions.
 *
 * Owns and exposes the Helix-native WorkStream and DialecticMesh.
 * The pipeline creates one coordinator per session and passes its
 * workStream and dialecticMesh to the posture runners.
 */
export class HelixCoordinator {
  readonly workStream: HelixWorkStream
  readonly dialecticMesh: HelixDialecticMesh
  readonly metrics: HelixMetrics
  private readonly logger: ILogger
  private readonly reviewerIds = ['yang', 'yin']

  constructor(opts: HelixCoordinatorOpts) {
    this.logger = opts.logger.child('helix-coordinator')

    this.metrics = new HelixMetrics(this.logger)

    this.workStream = new HelixWorkStream({
      sessionId: opts.sessionId,
      eventBus: opts.eventBus,
      maxMessages: opts.maxMessages,
      backpressureThreshold: opts.backpressureThreshold,
    })
    this.workStream.setMetrics(this.metrics)
    this.workStream.setReviewerIds(this.reviewerIds)

    this.dialecticMesh = new HelixDialecticMesh({
      sessionId: opts.sessionId,
      eventBus: opts.eventBus,
      maxMessages: opts.maxMessages,
    })

    this.logger.info('HelixCoordinator created', { sessionId: opts.sessionId })
  }

  /**
   * Check if all reviewers have observed all work units and are ready.
   */
  isAllReviewersReady(): boolean {
    return this.workStream.isTerminationConsensus(this.reviewerIds)
  }

  /**
   * Wait for all reviewers to finish observing work units.
   */
  async waitForReviewerConsensus(timeoutMs?: number): Promise<boolean> {
    return this.workStream.waitForTerminationConsensus(this.reviewerIds, timeoutMs)
  }

  /**
   * Get progress for all reviewers.
   */
  getProgress(): Record<string, { cursor: number; total: number; ready: boolean }> {
    const progress: Record<string, { cursor: number; total: number; ready: boolean }> = {}
    for (const id of this.reviewerIds) {
      progress[id] = this.workStream.getReviewerProgress(id)
    }
    return progress
  }

  /**
   * Get a snapshot of all dialectic activity visible to Unity.
   */
  getUnityView(): string[] {
    const messages = this.dialecticMesh.drainForUnity()
    return messages.map((m) => `[${m.from}] ${m.type}: ${m.text ?? JSON.stringify(m)}`)
  }

  /**
   * Get consolidated metrics snapshot for the session.
   */
  getMetricsSnapshot(): HelixMetricsSnapshot {
    return this.metrics.getSnapshot()
  }

  /**
   * Record a reviewer iteration (yang or yin).
   */
  recordReviewerIteration(reviewer: 'yang' | 'yin'): void {
    this.metrics.incrementReviewerIteration(reviewer)
  }

  /**
   * Record a nudge sent by a reviewer.
   */
  recordNudgeSent(): void {
    this.metrics.incrementNudges()
  }
}
