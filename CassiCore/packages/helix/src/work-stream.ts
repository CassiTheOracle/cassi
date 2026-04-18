/**
 * WorkStream — Shared communication substrate for Dyad pipeline.
 *
 * Provides real-time, tool-result-injected communication between concurrent postures:
 * - Yang auto-emits work units after each iteration
 * - Yin blocks on work units, refines artifacts, sends nudges
 * - Apex watches autonomously, injects research/guidance
 * - Backpressure mechanism prevents Yang from overwhelming Yin
 * - High-severity nudges block Yang until acknowledged
 *
 * Thread-safe by virtue of Node.js single-threaded event loop —
 * no locks needed, just careful async-safe append-only data structures.
 */

// Types

import type {
  DyadRole,
  WorkUnit,
  Nudge,
  NudgeAck,
  Refinement,
  Research,
  Guidance,
  QualityAssessment,
  WorkStreamMessage,
  WorkUnitMessage,
  RefinementMessage,
  NudgeMessage,
  NudgeAckMessage,
  ResearchMessage,
  GuidanceMessage,
  QualityAssessmentMessage,
  FileChange,
} from './work-types.js'

import type { IEventBus } from '../../../types/interfaces.js'



/**
 * Lightweight status signal for proactive reviewer observation of Unity.
 *
 * Delivered via tool result injection (zero extra LLM requests).
 * Only emitted when thresholds are exceeded — not on every iteration.
 */
export interface UnityStatus {
  /** Iterations since Unity last posted a work unit */
  iterationsSinceWu: number
  /** Seconds since Unity last posted a work unit */
  secondsSinceWu: number
  /** Most recent tool Unity called */
  lastToolName: string | null
  /** Detected pattern (e.g., "5x read_file on /path/to/file"), null if no pattern */
  toolPatternSummary: string | null
  /** Total Unity iterations so far */
  totalIterations: number
  /** Total Unity tool calls so far */
  totalToolCalls: number
  /** Which thresholds triggered this signal */
  triggeredBy: Array<'iterations' | 'time' | 'pattern'>
}

/**
 * Configurable thresholds for UnityStatus signal emission.
 */
export interface UnityStatusThresholds {
  /** Max iterations without work unit before signaling (default: 10) */
  maxIterationsWithoutWu?: number
  /** Max seconds without work unit before signaling (default: 60) */
  maxSecondsWithoutWu?: number
  /** Max repeated same-tool-and-args calls before signaling (default: 5) */
  maxRepeatedSameTool?: number
}


// Constants

/** Maximum work units before backpressure is applied */
const DEFAULT_BACKPRESSURE_THRESHOLD = 5

/** Maximum size of a work unit in characters (50KB) */
const MAX_WORK_UNIT_SIZE = 50 * 1024

/** Rate limiting: max work units per window */
const RATE_LIMIT_WINDOW_MS = 30000
// 30 work units per 30s = 1/sec total budget across all 3 postures
// (Unity, Yang, Yin all produce work units now in posture-independence mode).
// Originally 10/30s when only Unity produced — bumped 3x to match producer count.
const MAX_WORK_UNITS_PER_WINDOW = 30

/** Nudge timeout: high-severity nudges auto-expire after this long */
const NUDGE_TIMEOUT_MS = 60000

/** Maximum high-severity nudges per session */
const MAX_HIGH_NUDGES_PER_SESSION = 10

/** Minimum iterations between high-severity nudges (cooldown) */
const MIN_NUDGE_GAP_ITERATIONS = 3

/** Maximum messages before eviction */
const DEFAULT_MAX_MESSAGES = 500

// WorkStream

export class WorkStream {
  /** All messages in chronological order */
  private messages: WorkStreamMessage[] = []

  /** Maximum messages before oldest non-critical messages are evicted */
  private readonly maxMessages: number

  /** Backpressure threshold */
  private readonly backpressureThreshold: number

  /** Per-role drain cursors — how far each has read */
  private cursors: Record<DyadRole, number> = { yang: 0, yin: 0, apex: 0, unity: 0 }

  /** Work unit queue for Yin — blocks via promise resolver */
  private workUnitQueue: WorkUnit[] = []
  private workUnitResolvers: Array<(unit: WorkUnit | null) => void> = []

  /** Persistent record of ALL work units posted (survives queue consumption) */
  private allPostedWorkUnits: WorkUnit[] = []

  /** Work units fully processed by Yin */
  private processedWorkUnitIds = new Set<string>()

  /** Work units for which Yin produced output (note_refinement or note_observation) */
  private reviewedWorkUnitIds = new Set<string>()

  /** Nudge queue for high-severity nudges */
  private highNudgeQueue: Nudge[] = []

  /** Rate limiting state */
  private workUnitTimestamps: number[] = []

  /** Nudge tracking */
  private highNudgeCount = 0
  private lastHighNudgeIteration = -1

  /** Monotonic ID counters */
  private workUnitCounter = 0
  private nudgeCounter = 0
  private refinementCounter = 0
  private researchCounter = 0
  private guidanceCounter = 0

  /** File tracking: file path → work unit IDs that modified it */
  private fileToWorkUnits = new Map<string, string[]>()

  /** Optional event bus for real-time message flow to cognitive-feed topics */
  private readonly eventBus?: IEventBus
  private readonly sessionId?: string

  /** Protected messages (never evicted) */
  private protectedMessageIds = new Set<string>()

  // These are updated by agent sessions via recordRoleActivity() so Apex
  // can see what Yang and Yin are doing without direct access to their sessions.

  private roleActivity: Record<DyadRole, {
    iterationCount: number
    toolCallCount: number
    tokensUsed: number
    lastToolName: string | null
    lastToolTimestamp: number
    concluded: boolean
    errored: boolean
    errorMessage: string | null
    recentToolCalls: Array<{ name: string; timestamp: number; isError: boolean; argsSummary?: string }>
  }> = {
    yang: { iterationCount: 0, toolCallCount: 0, tokensUsed: 0, lastToolName: null, lastToolTimestamp: 0, concluded: false, errored: false, errorMessage: null, recentToolCalls: [] },
    yin:  { iterationCount: 0, toolCallCount: 0, tokensUsed: 0, lastToolName: null, lastToolTimestamp: 0, concluded: false, errored: false, errorMessage: null, recentToolCalls: [] },
    apex: { iterationCount: 0, toolCallCount: 0, tokensUsed: 0, lastToolName: null, lastToolTimestamp: 0, concluded: false, errored: false, errorMessage: null, recentToolCalls: [] },
    unity: { iterationCount: 0, toolCallCount: 0, tokensUsed: 0, lastToolName: null, lastToolTimestamp: 0, concluded: false, errored: false, errorMessage: null, recentToolCalls: [] },
  }

  /** UnityStatus tracking — last work unit iteration for threshold detection */
  private lastWorkUnitIteration = 0
  private lastWorkUnitTimestamp = Date.now()

  constructor(maxMessages = DEFAULT_MAX_MESSAGES, backpressureThreshold = DEFAULT_BACKPRESSURE_THRESHOLD, eventBus?: IEventBus, sessionId?: string) {
    this.maxMessages = maxMessages
    this.backpressureThreshold = backpressureThreshold
    this.eventBus = eventBus
    this.sessionId = sessionId
  }

  /** Emit a work stream event on the bus if available */
  private emitStreamEvent(type: string, data: Record<string, unknown>): void {
    if (!this.eventBus) return
    try {
      void this.eventBus.emit({ type, sessionId: this.sessionId, ...data } as any)
    } catch { /* ignore bus emit errors */ }
  }


  /** Evict oldest non-protected messages when cap is hit */
  private evictIfNeeded(): void {
    while (this.messages.length > this.maxMessages) {
      // Never evict protected messages
      const evictIdx = this.messages.findIndex(m => !this.isProtected(m))
      if (evictIdx < 0) break // all remaining are protected
      this.messages.splice(evictIdx, 1)
      // Adjust cursors
      for (const role of ['yang', 'yin', 'apex', 'unity'] as DyadRole[]) {
        if (this.cursors[role] > evictIdx) {
          this.cursors[role]--
        }
      }
    }
  }

  /** Check if a message should be protected from eviction */
  private isProtected(msg: WorkStreamMessage): boolean {
    // Protect unresolved high-severity nudges
    if (msg.type === 'nudge' && msg.nudge.severity === 'high' && !msg.nudge.acknowledged) {
      return true
    }
    // Protect unprocessed work units
    if (msg.type === 'work_unit' && !msg.workUnit.processed) {
      return true
    }
    return false
  }


  /**
   * Post a work unit from Yang.
   * Automatically adds to Yin's blocking queue.
   * Applies rate limiting and size validation.
   */
  postWorkUnit(workUnit: WorkUnit): void {
    // Validate size
    const size = JSON.stringify(workUnit).length
    if (size > MAX_WORK_UNIT_SIZE) {
      throw new Error(`Work unit exceeds maximum size (${size} > ${MAX_WORK_UNIT_SIZE})`)
    }

    // Rate limiting
    this.applyRateLimiting()

    // Update UnityStatus tracking — record when last work unit was posted
    this.lastWorkUnitIteration = this.roleActivity.unity.iterationCount
    this.lastWorkUnitTimestamp = Date.now()

    // Track file modifications
    for (const file of workUnit.filesModified) {
      const existing = this.fileToWorkUnits.get(file.path) || []
      existing.push(workUnit.id)
      this.fileToWorkUnits.set(file.path, existing)
    }

    // Add to queue for Yin
    this.workUnitQueue.push(workUnit)
    // Persist in permanent record (survives queue consumption)
    this.allPostedWorkUnits.push(workUnit)
    // Resolve the next waiter if any
    if (this.workUnitResolvers.length > 0) {
      const resolver = this.workUnitResolvers.shift()!
      resolver(workUnit)
    }

    // Post message
    const msg: WorkUnitMessage = {
      type: 'work_unit',
      workUnit,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.evictIfNeeded()

    // Emit work unit event for real-time topic flow
    this.emitStreamEvent('dyad:work-unit', {
      id: workUnit.id,
      iteration: workUnit.iteration,
      description: (workUnit.reasoning ?? '').slice(0, 500),
      filesModified: workUnit.filesModified.map(f => f.path),
      fileCount: workUnit.filesModified.length,
    })
  }

  /** Apply rate limiting to work unit posting */
  private applyRateLimiting(): void {
    const now = Date.now()
    // Remove timestamps outside the window
    this.workUnitTimestamps = this.workUnitTimestamps.filter(
      ts => now - ts < RATE_LIMIT_WINDOW_MS,
    )
    if (this.workUnitTimestamps.length >= MAX_WORK_UNITS_PER_WINDOW) {
      throw new Error(
        `Rate limit exceeded: ${MAX_WORK_UNITS_PER_WINDOW} work units per ${RATE_LIMIT_WINDOW_MS / 1000}s`,
      )
    }
    this.workUnitTimestamps.push(now)
  }

  /**
   * Check if backpressure should be applied.
   * Returns true if unprocessed work units exceed threshold.
   * Counts total posted minus fully processed, not just queue length.
   */
  shouldApplyBackpressure(): boolean {
    const unprocessed = this.allPostedWorkUnits.length - this.processedWorkUnitIds.size
    if (unprocessed < this.backpressureThreshold) return false

    // Don't apply backpressure if all consumer roles have concluded —
    // no one is left to relieve it, so blocking would deadlock.
    const consumers: DyadRole[] = ['yin', 'yang', 'apex']
    const allConcluded = consumers.every(role => this.roleActivity[role].concluded)
    if (allConcluded) return false

    return true
  }

  /**
   * Wait for backpressure to be relieved.
   * Yin should call markWorkUnitProcessed() to relieve backpressure.
   */
  async awaitBackpressureRelief(timeoutMs = 60_000): Promise<void> {
    const deadline = Date.now() + timeoutMs
    while (this.shouldApplyBackpressure()) {
      if (Date.now() > deadline) return // Safety net — don't block forever
      await new Promise(resolve => setTimeout(resolve, 100))
    }
  }


  /**
   * Get the next work unit for Yin to process.
   * Returns null when Yang is done and the queue is empty (Yin should exit its loop).
   * Blocks if no work units are available (promise/resolver pattern).
   */
  async nextWorkUnit(timeoutMs = 300000): Promise<WorkUnit | null> {
    // Check if there's already a work unit queued
    if (this.workUnitQueue.length > 0) {
      const unit = this.workUnitQueue.shift()!
      return unit
    }

    // If Yang is already done and queue is empty, return null immediately
    if (this.yangDone) {
      return null
    }

    // Otherwise, wait for one (or for Yang to signal done)
    return new Promise<WorkUnit | null>((resolve, reject) => {
      const timeout = setTimeout(() => {
        // Remove this resolver from the queue
        const idx = this.workUnitResolvers.indexOf(wrappedResolve)
        if (idx >= 0) this.workUnitResolvers.splice(idx, 1)
        reject(new Error('Work unit timeout'))
      }, timeoutMs)

      const wrappedResolve = (unit: WorkUnit | null) => {
        clearTimeout(timeout)
        resolve(unit)
      }

      this.workUnitResolvers.push(wrappedResolve)
    })
  }

  /**
   * Mark a work unit as fully processed by Yin.
   * Relieves backpressure and updates message log.
   */
  markWorkUnitProcessed(workUnitId: string): void {
    this.processedWorkUnitIds.add(workUnitId)

    // Mark in the permanent record
    for (const wu of this.allPostedWorkUnits) {
      if (wu.id === workUnitId) {
        wu.processed = true
        break
      }
    }

    // Also mark in queue if still there (shouldn't be, but defensive)
    for (const wu of this.workUnitQueue) {
      if (wu.id === workUnitId) {
        wu.processed = true
        break
      }
    }

    // Update in messages
    for (const msg of this.messages) {
      if (msg.type === 'work_unit' && msg.workUnit.id === workUnitId) {
        msg.workUnit.processed = true
        break
      }
    }
  }

  /**
   * Mark a work unit as reviewed by Yin (Yin produced output — refinement or observation).
   * Separate from "processed" which is about queue consumption.
   * This tracks whether Yin actually performed its review duty.
   */
  markWorkUnitReviewed(workUnitId: string): void {
    this.reviewedWorkUnitIds.add(workUnitId)
  }

  /** Check whether Yin has produced output for a given work unit */
  isWorkUnitReviewed(workUnitId: string): boolean {
    return this.reviewedWorkUnitIds.has(workUnitId)
  }

  /** Count of work units that Yin consumed but did NOT produce output for */
  getUnreviewedWorkUnitCount(): number {
    const consumed = this.processedWorkUnitIds.size
    const reviewed = this.reviewedWorkUnitIds.size
    // Can't have more reviewed than consumed
    return Math.max(0, consumed - reviewed)
  }


  /**
   * Post a nudge from Yin to Yang.
   * High-severity nudges block Yang until acknowledged.
   * Applies cooldown and max count limits.
   */
  postNudge(nudge: Nudge, currentYangIteration: number): void {
    // Validate and sanitize content
    nudge.content = this.sanitizeNudgeContent(nudge.content)
    nudge.yangIteration = currentYangIteration

    // High-severity nudge limits
    if (nudge.severity === 'high') {
      // Check cooldown
      if (currentYangIteration - this.lastHighNudgeIteration < MIN_NUDGE_GAP_ITERATIONS) {
        throw new Error(
          `High-severity nudge cooldown: must wait ${MIN_NUDGE_GAP_ITERATIONS} iterations`,
        )
      }
      // Check max count
      if (this.highNudgeCount >= MAX_HIGH_NUDGES_PER_SESSION) {
        throw new Error(`Maximum high-severity nudges reached (${MAX_HIGH_NUDGES_PER_SESSION})`)
      }
      this.highNudgeCount++
      this.lastHighNudgeIteration = currentYangIteration
      // Add to blocking queue
      this.highNudgeQueue.push(nudge)
      nudge.blocking = true
    } else {
      nudge.blocking = false
    }

    // Post message
    const msg: NudgeMessage = {
      type: 'nudge',
      nudge,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.evictIfNeeded()

    // Emit nudge event for real-time topic flow
    this.emitStreamEvent('dyad:nudge', {
      id: nudge.id,
      severity: nudge.severity,
      content: nudge.content.slice(0, 300),
      blocking: nudge.blocking,
      yangIteration: nudge.yangIteration,
    })
  }

  /** Sanitize nudge content */
  private sanitizeNudgeContent(content: string): string {
    // Strip markdown/code blocks for simplicity
    let sanitized = content.replace(/```[\s\S]*?```/g, '')
    // Truncate to 500 chars
    sanitized = sanitized.slice(0, 500)
    // Remove control characters
    sanitized = sanitized.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, '')
    return sanitized.trim()
  }

  /**
   * Get the next high-severity nudge for Yang to acknowledge.
   * Returns undefined if no high-severity nudges are pending.
   */
  getNextHighNudge(): Nudge | undefined {
    // Check for expired nudges
    const now = Date.now()
    this.highNudgeQueue = this.highNudgeQueue.filter(n => {
      if (!n.acknowledged && now - n.timestamp > NUDGE_TIMEOUT_MS) {
        // Auto-expire
        n.blocking = false
        return false
      }
      return true
    })

    return this.highNudgeQueue.find(n => !n.acknowledged && n.blocking)
  }

  /**
   * Acknowledge a nudge from Yang.
   * Returns true if the nudge was found and acknowledged, false if the nudge
   * doesn't exist, was already acknowledged, or has expired.
   */
  acknowledgeNudge(nudgeId: string, message: string): boolean {
    // Validate: find the nudge in messages
    const nudgeMsg = this.messages.find(
      (m): m is NudgeMessage => m.type === 'nudge' && m.nudge.id === nudgeId,
    )
    if (!nudgeMsg) return false // Nudge doesn't exist
    if (nudgeMsg.nudge.acknowledged) return false // Already acknowledged

    // Check for expiration
    if (Date.now() - nudgeMsg.nudge.timestamp > NUDGE_TIMEOUT_MS) {
      nudgeMsg.nudge.blocking = false
      this.highNudgeQueue = this.highNudgeQueue.filter(n => n.id !== nudgeId)
      return false // Expired
    }

    const ack: NudgeAck = {
      nudgeId,
      acknowledgedBy: 'yang',
      message,
      timestamp: Date.now(),
    }

    // Mark nudge as acknowledged
    nudgeMsg.nudge.acknowledged = true
    nudgeMsg.nudge.blocking = false

    // Remove from high nudge queue
    this.highNudgeQueue = this.highNudgeQueue.filter(n => n.id !== nudgeId)

    // Post acknowledgment message
    const ackMsg: NudgeAckMessage = {
      type: 'nudge_ack',
      ack,
      timestamp: Date.now(),
    }
    this.messages.push(ackMsg)
    this.evictIfNeeded()
    return true
  }


  /**
   * Post a refinement from Yin.
   */
  postRefinement(refinement: Refinement): void {
    const msg: RefinementMessage = {
      type: 'refinement',
      refinement,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.evictIfNeeded()

    // Emit refinement event for real-time topic flow
    this.emitStreamEvent('dyad:refinement', {
      id: refinement.id,
      workUnitId: refinement.workUnitId,
      description: refinement.description.slice(0, 500),
      fileCount: refinement.filesModified.length,
    })
  }


  /**
   * Post research from Apex.
   */
  postResearch(research: Research): void {
    const msg: ResearchMessage = {
      type: 'research',
      research,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.evictIfNeeded()

    // Emit research event for real-time topic flow
    this.emitStreamEvent('dyad:research', {
      id: research.id,
      topic: research.topic.slice(0, 200),
      findings: research.findings.slice(0, 500),
      target: research.target,
    })
  }

  /**
   * Post guidance from Apex.
   */
  postGuidance(guidance: Guidance): void {
    const msg: GuidanceMessage = {
      type: 'guidance',
      guidance,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.evictIfNeeded()

    // Emit guidance event for real-time topic flow
    this.emitStreamEvent('dyad:guidance', {
      id: guidance.id,
      direction: guidance.direction.slice(0, 300),
      rationale: guidance.rationale.slice(0, 200),
      target: guidance.target,
    })
  }

  /**
   * Post quality assessment from Apex.
   */
  postQualityAssessment(assessment: QualityAssessment): void {
    const msg: QualityAssessmentMessage = {
      type: 'quality_assessment',
      assessment,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    // Protect quality assessment from eviction
    this.protectedMessageIds.add(`qa-${assessment.score}`)
    this.evictIfNeeded()

    // Emit quality assessment event for real-time topic flow
    this.emitStreamEvent('dyad:quality-assessment', {
      overallScore: assessment.overallScore,
      assessment: assessment.assessment.slice(0, 500),
      strengths: assessment.strengths.slice(0, 5),
      weaknesses: assessment.weaknesses.slice(0, 5),
      remainingIssues: assessment.remainingIssues.slice(0, 5),
    })
  }


  /**
   * Get new messages for a role since their last drain.
   * Updates the cursor automatically.
   */
  drainMessages(role: DyadRole): WorkStreamMessage[] {
    const cursor = this.cursors[role]
    const newMessages = this.messages.slice(cursor)
    this.cursors[role] = this.messages.length
    return newMessages
  }

  /**
   * Check if a message is relevant to a specific role.
   */
  isRelevantTo(msg: WorkStreamMessage, role: DyadRole): boolean {
    switch (msg.type) {
      case 'work_unit':
        // Work units are relevant to Yin and Apex (not Yang)
        return role !== 'yang'

      case 'refinement':
        // Refinements are relevant to Apex (logging) and Yin (own work)
        return role === 'apex' || role === 'yin'

      case 'nudge':
        // Nudges are relevant to Yang (recipient) and Apex (oversight)
        return role === 'yang' || role === 'apex'

      case 'nudge_ack':
        // Acknowledgments are relevant to Yin (sender) and Apex
        return role === 'yin' || role === 'apex'

      case 'research':
        // Research is relevant to the target role(s)
        return msg.research.target === role || msg.research.target === 'both'

      case 'guidance':
        // Guidance is relevant to the target role(s)
        return msg.guidance.target === role || msg.guidance.target === 'both'

      case 'quality_assessment':
        // Quality assessment is relevant to all (logging)
        return true

      default:
        return false
    }
  }


  /**
   * Get work units that modified a specific file.
   */
  getWorkUnitsByFile(filePath: string): WorkUnit[] {
    const workUnitIds = this.fileToWorkUnits.get(filePath) || []
    return this.allPostedWorkUnits.filter(wu => workUnitIds.includes(wu.id))
  }

  /**
   * Get work units that modified files in a specific directory.
   */
  getWorkUnitsByDirectory(dirPath: string): WorkUnit[] {
    const normalizedDir = dirPath.endsWith('/') ? dirPath : dirPath + '/'
    const matchingUnits: WorkUnit[] = []

    for (const [filePath, workUnitIds] of this.fileToWorkUnits.entries()) {
      if (filePath.startsWith(normalizedDir) || filePath === dirPath) {
        for (const wu of this.allPostedWorkUnits) {
          if (workUnitIds.includes(wu.id) && !matchingUnits.includes(wu)) {
            matchingUnits.push(wu)
          }
        }
      }
    }

    return matchingUnits
  }

  /**
   * Get all files modified by a specific work unit.
   */
  getFilesModifiedBy(workUnitIdOrRole: string): string[] {
    // If role name, get all files modified by work units
    if (workUnitIdOrRole === 'yang') {
      return [...new Set(this.allPostedWorkUnits.flatMap(wu => wu.filesModified.map(f => f.path)))]
    }
    if (workUnitIdOrRole === 'yin') {
      return [...new Set(
        this.messages
          .filter((m): m is RefinementMessage => m.type === 'refinement')
          .flatMap(m => m.refinement.filesModified.map(f => f.path))
      )]
    }
    // Otherwise treat as work unit ID
    const wu = this.allPostedWorkUnits.find(w => w.id === workUnitIdOrRole)
    return wu ? wu.filesModified.map(f => f.path) : []
  }


  /**
   * Get the full message log.
   */
  getFullLog(): WorkStreamMessage[] {
    return [...this.messages]
  }

  /**
   * Get all work units (total posted, not just queue).
   */
  getAllWorkUnits(): WorkUnit[] {
    return [...this.allPostedWorkUnits]
  }

  /**
   * Get all nudges.
   */
  getAllNudges(): Nudge[] {
    return this.messages
      .filter((m): m is NudgeMessage => m.type === 'nudge')
      .map(m => m.nudge)
  }

  /**
   * Get all refinements.
   */
  getAllRefinements(): Refinement[] {
    return this.messages
      .filter((m): m is RefinementMessage => m.type === 'refinement')
      .map(m => m.refinement)
  }

  /**
   * Get quality assessment if posted.
   */
  getQualityAssessment(): QualityAssessment | undefined {
    const qaMsg = this.messages.find(
      (m): m is QualityAssessmentMessage => m.type === 'quality_assessment',
    )
    return qaMsg?.assessment
  }


  /**
   * Get role activity data (public accessor for Apex visibility and admin API).
   */
  getRoleActivity(): Record<DyadRole, {
    iterationCount: number
    toolCallCount: number
    tokensUsed: number
    lastToolName: string | null
    lastToolTimestamp: number
    concluded: boolean
    errored: boolean
    errorMessage: string | null
    recentToolCalls: Array<{ name: string; timestamp: number; isError: boolean; argsSummary?: string }>
  }> {
    return {
      yang: { ...this.roleActivity.yang, recentToolCalls: [...this.roleActivity.yang.recentToolCalls] },
      yin: { ...this.roleActivity.yin, recentToolCalls: [...this.roleActivity.yin.recentToolCalls] },
      apex: { ...this.roleActivity.apex, recentToolCalls: [...this.roleActivity.apex.recentToolCalls] },
      unity: { ...this.roleActivity.unity, recentToolCalls: [...this.roleActivity.unity.recentToolCalls] },
    }
  }


  /**
   * Get Unity's current status for proactive reviewer observation.
   *
   * Returns null if no thresholds are exceeded — reviewers should not be notified.
   * When thresholds ARE exceeded, returns a lightweight status signal that can be
   * injected into reviewer tool results (zero extra LLM requests).
   */
  getUnityStatus(thresholds?: UnityStatusThresholds): UnityStatus | null {
    const unity = this.roleActivity.unity
    if (unity.concluded) return null

    const maxIter = thresholds?.maxIterationsWithoutWu ?? 10
    const maxSecs = thresholds?.maxSecondsWithoutWu ?? 60
    const maxRepeat = thresholds?.maxRepeatedSameTool ?? 5

    const itersSinceWu = unity.iterationCount - this.lastWorkUnitIteration
    const secsSinceWu = Math.round((Date.now() - this.lastWorkUnitTimestamp) / 1000)

    // Detect repeated tool+args pattern from recentToolCalls
    let toolPatternSummary: string | undefined
    let repeatedCount = 0
    if (unity.recentToolCalls.length >= 2) {
      const recent = unity.recentToolCalls
      const last = recent[recent.length - 1]
      let streak = 1
      for (let i = recent.length - 2; i >= 0; i--) {
        const prev = recent[i]
        if (prev.name === last.name && prev.argsSummary === last.argsSummary) {
          streak++
        } else {
          break
        }
      }
      repeatedCount = streak
      if (streak >= maxRepeat) {
        const argsPart = last.argsSummary ? ` on ${last.argsSummary}` : ''
        toolPatternSummary = `${streak}x ${last.name}${argsPart}`
      }
    }

    // Check thresholds
    const iterationTriggered = itersSinceWu > maxIter
    const timeTriggered = secsSinceWu > maxSecs
    const patternTriggered = repeatedCount >= maxRepeat

    if (!iterationTriggered && !timeTriggered && !patternTriggered) {
      return null
    }

    return {
      iterationsSinceWu: itersSinceWu,
      secondsSinceWu: secsSinceWu,
      lastToolName: unity.lastToolName,
      toolPatternSummary: toolPatternSummary ?? null,
      totalIterations: unity.iterationCount,
      totalToolCalls: unity.toolCallCount,
      triggeredBy: [
        ...(iterationTriggered ? ['iterations' as const] : []),
        ...(timeTriggered ? ['time' as const] : []),
        ...(patternTriggered ? ['pattern' as const] : []),
      ],
    }
  }

  /**
   * Reset UnityStatus tracking — call when a meaningful work unit is posted.
   * This is automatically called by postWorkUnit().
   */
  resetUnityStatusTracking(): void {
    this.lastWorkUnitIteration = this.roleActivity.unity.iterationCount
    this.lastWorkUnitTimestamp = Date.now()
  }

  /**
   * Format a UnityStatus signal as human-readable text for injection into reviewer context.
   */
  static formatUnityStatus(status: UnityStatus): string {
    const triggers = status.triggeredBy.map(t => {
      switch (t) {
        case 'iterations': return `${status.iterationsSinceWu} iterations without work unit`
        case 'time': return `${status.secondsSinceWu}s since last work unit`
        case 'pattern': return `repeated tool pattern: ${status.toolPatternSummary}`
      }
    }).join(', ')

    const lines = [
      `Unity Status Signal — ${triggers}`,
      `  Iterations: ${status.totalIterations} total, ${status.iterationsSinceWu} since last work unit`,
      `  Time: ${status.secondsSinceWu}s since last work unit`,
    ]
    if (status.lastToolName) {
      lines.push(`  Last tool: ${status.lastToolName}`)
    }
    if (status.toolPatternSummary) {
      lines.push(`  Pattern detected: ${status.toolPatternSummary}`)
    }
    lines.push('  Consider: Is Unity stuck? Use request_investigation before sending a nudge.')
    return lines.join('\n')
  }

  /**
   * Get aggregate statistics.
   */
  getStats(): {
    workUnits: number
    workUnitsProcessed: number
    workUnitsPending: number
    workUnitsReviewed: number
    workUnitsUnreviewed: number
    refinements: number
    nudges: { low: number; high: number; acknowledged: number }
    research: number
    guidance: number
  } {
    const nudgeMessages = this.messages.filter((m): m is NudgeMessage => m.type === 'nudge')
    return {
      workUnits: this.allPostedWorkUnits.length,
      workUnitsProcessed: this.processedWorkUnitIds.size,
      workUnitsPending: this.allPostedWorkUnits.length - this.processedWorkUnitIds.size,
      workUnitsReviewed: this.reviewedWorkUnitIds.size,
      workUnitsUnreviewed: this.getUnreviewedWorkUnitCount(),
      refinements: this.messages.filter((m): m is RefinementMessage => m.type === 'refinement').length,
      nudges: {
        low: nudgeMessages.filter(m => m.nudge.severity === 'low').length,
        high: nudgeMessages.filter(m => m.nudge.severity === 'high').length,
        acknowledged: nudgeMessages.filter(m => m.nudge.acknowledged).length,
      },
      research: this.messages.filter((m): m is ResearchMessage => m.type === 'research').length,
      guidance: this.messages.filter((m): m is GuidanceMessage => m.type === 'guidance').length,
    }
  }


  /**
   * Record a tool call from a role. Called by DyadPostureRunner after each tool execution.
   * @param argsSummary - Optional short summary of tool args for pattern detection (e.g. file path)
   */
  recordToolCall(role: DyadRole, toolName: string, isError: boolean, argsSummary?: string): void {
    const activity = this.roleActivity[role]
    activity.toolCallCount++
    activity.lastToolName = toolName
    activity.lastToolTimestamp = Date.now()
    activity.recentToolCalls.push({ name: toolName, timestamp: Date.now(), isError, argsSummary })
    // Keep only last 10
    if (activity.recentToolCalls.length > 10) {
      activity.recentToolCalls = activity.recentToolCalls.slice(-10)
    }
  }

  /**
   * Record an iteration completion from a role.
   */
  recordIteration(role: DyadRole, tokensUsed: number): void {
    const activity = this.roleActivity[role]
    activity.iterationCount++
    activity.tokensUsed += tokensUsed
  }

  /**
   * Record that a role has concluded (normally or with error).
   */
  recordRoleConclusion(role: DyadRole, errored: boolean, errorMessage?: string): void {
    const activity = this.roleActivity[role]
    activity.concluded = true
    activity.errored = errored
    activity.errorMessage = errorMessage ?? null
  }

  /**
   * Get rich progress report for Apex — full visibility into Yang and Yin activity.
   */
  getRichProgress(): string {
    const stats = this.getStats()
    const yang = this.roleActivity.yang
    const yin = this.roleActivity.yin

    const lines: string[] = [
      '## Pipeline Status',
      '',
    ]

    // Yang status
    const yangStatus = yang.concluded
      ? (yang.errored ? `ERRORED: ${yang.errorMessage}` : 'COMPLETED')
      : `ACTIVE (iteration ${yang.iterationCount})`
    lines.push(`### Yang (Worker): ${yangStatus}`)
    lines.push(`- Iterations: ${yang.iterationCount} | Tool calls: ${yang.toolCallCount} | Tokens: ${yang.tokensUsed}`)
    if (yang.lastToolName) {
      const ago = Math.round((Date.now() - yang.lastToolTimestamp) / 1000)
      lines.push(`- Last tool: \`${yang.lastToolName}\` (${ago}s ago)`)
    }
    if (yang.recentToolCalls.length > 0) {
      const recent = yang.recentToolCalls.slice(-5).map(t => {
        const err = t.isError ? ' [ERROR]' : ''
        return `\`${t.name}\`${err}`
      }).join(' → ')
      lines.push(`- Recent tools: ${recent}`)
    }
    const yangFiles = this.getFilesModifiedBy('yang')
    if (yangFiles.length > 0) {
      lines.push(`- Files modified: ${yangFiles.slice(0, 10).join(', ')}${yangFiles.length > 10 ? ` (+${yangFiles.length - 10} more)` : ''}`)
    }
    lines.push('')

    // Yin status
    const yinStatus = yin.concluded
      ? (yin.errored ? `ERRORED: ${yin.errorMessage}` : 'COMPLETED')
      : `ACTIVE (iteration ${yin.iterationCount})`
    lines.push(`### Yin (Refiner): ${yinStatus}`)
    lines.push(`- Iterations: ${yin.iterationCount} | Tool calls: ${yin.toolCallCount} | Tokens: ${yin.tokensUsed}`)
    lines.push(`- Work units processed: ${this.processedWorkUnitIds.size}/${stats.workUnits} (${stats.workUnitsPending} pending)`)
    if (yin.lastToolName) {
      const ago = Math.round((Date.now() - yin.lastToolTimestamp) / 1000)
      lines.push(`- Last tool: \`${yin.lastToolName}\` (${ago}s ago)`)
    }
    if (yin.recentToolCalls.length > 0) {
      const recent = yin.recentToolCalls.slice(-5).map(t => {
        const err = t.isError ? ' [ERROR]' : ''
        return `\`${t.name}\`${err}`
      }).join(' → ')
      lines.push(`- Recent tools: ${recent}`)
    }
    const yinFiles = this.getFilesModifiedBy('yin')
    if (yinFiles.length > 0) {
      lines.push(`- Files refined: ${yinFiles.slice(0, 10).join(', ')}${yinFiles.length > 10 ? ` (+${yinFiles.length - 10} more)` : ''}`)
    }
    lines.push('')

    // Aggregate stats
    lines.push('### Work Stream')
    lines.push(`- Work units: ${stats.workUnits} total, ${stats.workUnitsProcessed} processed, ${stats.workUnitsPending} pending`)
    lines.push(`- Yin reviews: ${stats.workUnitsReviewed} reviewed, ${stats.workUnitsUnreviewed} unreviewed`)
    lines.push(`- Refinements: ${stats.refinements}`)
    lines.push(`- Nudges: ${stats.nudges.low} low, ${stats.nudges.high} high (${stats.nudges.acknowledged} acknowledged)`)
    lines.push(`- Research injected: ${stats.research} | Guidance: ${stats.guidance}`)
    lines.push('')

    // Recent work units (last 3 summaries)
    const recentWUs = this.allPostedWorkUnits.slice(-3)
    if (recentWUs.length > 0) {
      lines.push('### Recent Work Units')
      for (const wu of recentWUs) {
        const files = wu.filesModified.map(f => f.path).join(', ')
        lines.push(`- **${wu.id}** (iter ${wu.iteration}): ${wu.reasoning?.slice(0, 150) ?? 'no reasoning'}`)
        if (files) lines.push(`  Files: ${files}`)
      }
      lines.push('')
    }

    // Recent refinements (last 3)
    const recentRefs = this.getAllRefinements().slice(-3)
    if (recentRefs.length > 0) {
      lines.push('### Recent Refinements')
      for (const ref of recentRefs) {
        const files = ref.filesModified.map(f => f.path).join(', ')
        lines.push(`- **${ref.id}**: ${ref.description?.slice(0, 150) ?? 'no description'}`)
        if (files) lines.push(`  Files: ${files}`)
      }
      lines.push('')
    }

    // Active nudges
    const activeNudges = this.getAllNudges().filter(n => !n.acknowledged)
    if (activeNudges.length > 0) {
      lines.push('### Active Nudges (unacknowledged)')
      for (const n of activeNudges.slice(-5)) {
        lines.push(`- [${n.severity}] ${n.content.slice(0, 100)}`)
      }
      lines.push('')
    }

    return lines.join('\n')
  }


  private yangDone = false
  private yangDoneResolvers: Array<() => void> = []

  /** Signal that Yang has completed all work. Unblocks Yin's nextWorkUnit(). */
  signalYangDone(): void {
    this.yangDone = true
    for (const resolve of this.yangDoneResolvers) resolve()
    this.yangDoneResolvers = []
    // Also resolve any pending nextWorkUnit waiters with null
    for (const resolve of this.workUnitResolvers) resolve(null)
    this.workUnitResolvers = []
  }

  /**
   * Force-cancel all pending waiters. Called by the pipeline watchdog
   * to break out of stuck blocking calls.
   */
  forceCancel(): void {
    this.yangDone = true
    for (const resolve of this.yangDoneResolvers) resolve()
    this.yangDoneResolvers = []
    for (const resolve of this.workUnitResolvers) resolve(null)
    this.workUnitResolvers = []
  }

  isYangDone(): boolean {
    return this.yangDone
  }

  // In Helix, the primary worker is Unity (not Yang), but WorkStream is shared.
  // These aliases make Helix call-sites self-documenting.

  /** Alias for signalYangDone() — used by Helix where Unity is the worker. */
  signalWorkerDone(): void { this.signalYangDone() }

  /** Alias for isYangDone() — used by Helix where Unity is the worker. */
  isWorkerDone(): boolean { return this.isYangDone() }

  /** Alias for waitForYangDone() — used by Helix where Unity is the worker. */
  waitForWorkerDone(): Promise<void> { return this.waitForYangDone() }

  waitForYangDone(): Promise<void> {
    if (this.yangDone) return Promise.resolve()
    return new Promise(resolve => this.yangDoneResolvers.push(resolve))
  }


  /** Drain new WorkStream messages relevant to a role since last drain. Returns formatted text or null. */
  drainForRole(role: DyadRole): string | null {
    const cursor = this.drainCursors.get(role) ?? 0
    const newMessages = this.messages.slice(cursor).filter(msg => {
      switch (role) {
        case 'yang':
          return msg.type === 'research' || msg.type === 'guidance' ||
                 (msg.type === 'nudge' && msg.nudge.severity === 'low')
        case 'yin':
          return msg.type === 'research' || msg.type === 'guidance'
        case 'apex':
          return msg.type === 'work_unit' || msg.type === 'refinement' || msg.type === 'nudge'
        default:
          return false
      }
    })

    this.drainCursors.set(role, this.messages.length)
    if (newMessages.length === 0) return null

    const parts: string[] = ['--- WorkStream Update ---']
    for (const msg of newMessages) {
      switch (msg.type) {
        case 'nudge':
          parts.push(`[Nudge from Yin] (${msg.nudge.severity}): ${msg.nudge.content}`)
          break
        case 'research':
          parts.push(`[Research from Apex]: ${msg.research.findings.slice(0, 500)}`)
          break
        case 'guidance':
          parts.push(`[Guidance from Apex]: ${msg.guidance.direction}`)
          break
        case 'work_unit':
          parts.push(`[Work Unit #${msg.workUnit.iteration}] ${msg.workUnit.filesModified.map(f => f.path).join(', ')}`)
          break
        case 'refinement':
          parts.push(`[Refinement] ${msg.refinement.description.slice(0, 200)}`)
          break
      }
    }
    return parts.join('\n')
  }

  private drainCursors = new Map<DyadRole, number>()


  private reportSections: ReportSection[] = []
  private nextSectionId = 1

  addReportSection(section: Omit<ReportSection, 'id' | 'status' | 'timestamp'>): ReportSection {
    const full: ReportSection = {
      ...section,
      id: `S${this.nextSectionId++}`,
      status: 'active',
      timestamp: Date.now(),
    }
    this.reportSections.push(full)
    return full
  }

  getReportView(filter?: { filterType?: string; filterAuthor?: string; filterStatus?: string }): ReportSection[] {
    return this.reportSections.filter(s => {
      if (filter?.filterType && s.type !== filter.filterType) return false
      if (filter?.filterAuthor && s.author !== filter.filterAuthor) return false
      if (filter?.filterStatus && s.status !== filter.filterStatus) return false
      return true
    })
  }

  reviseReportSection(sectionId: string, content: string, reason?: string): ReportSection | null {
    const idx = this.reportSections.findIndex(s => s.id === sectionId)
    if (idx < 0) return null
    const revised: ReportSection = {
      ...this.reportSections[idx],
      id: `S${this.nextSectionId++}`,
      content,
      status: 'active',
      timestamp: Date.now(),
    }
    this.reportSections[idx].status = 'superseded'
    this.reportSections.push(revised)
    return revised
  }

  promoteReportSection(sectionId: string): boolean {
    const section = this.reportSections.find(s => s.id === sectionId && s.status === 'draft')
    if (!section) return false
    section.status = 'active'
    return true
  }

  discardReportSection(sectionId: string): boolean {
    const section = this.reportSections.find(s => s.id === sectionId && s.status === 'draft')
    if (!section) return false
    section.status = 'discarded'
    return true
  }

  sendNudge(nudge: Nudge, currentYangIteration: number): void { return this.postNudge(nudge, currentYangIteration) }
  injectResearch(research: Research): void { return this.postResearch(research) }
  provideGuidance(guidance: Guidance): void { return this.postGuidance(guidance) }
  getReportMetrics(): { totalSections: number; activeSections: number; draftSections: number; avgConfidence: number } {
    const active = this.reportSections.filter(s => s.status === 'active')
    const drafts = this.reportSections.filter(s => s.status === 'draft')
    const confidences = this.reportSections.filter(s => s.confidence != null).map(s => s.confidence!)
    return {
      totalSections: this.reportSections.length,
      activeSections: active.length,
      draftSections: drafts.length,
      avgConfidence: confidences.length > 0 ? confidences.reduce((a, b) => a + b, 0) / confidences.length : 0,
    }
  }
}


interface ReportSection {
  id: string
  type: string
  title: string
  content: string
  author: string
  status: 'active' | 'draft' | 'superseded' | 'discarded'
  confidence?: number
  references?: string[]
  timestamp: number
}
