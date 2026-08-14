/**
 * GlobalWorkspace — The capacity-limited broadcast medium at the heart of CassiCore.
 *
 * Implements Global Workspace Theory (Baars, 1988) at the system level:
 *
 *   1. Specialist modules submit CognitiveSignals (proposals for conscious access)
 *   2. Signals are scored on luminance (novelty, urgency, relevance, credibility)
 *   3. Signals below the ignition threshold stay unconscious (local to their module)
 *   4. Bright signals compete for limited workspace slots (7 by default)
 *   5. Winners are broadcast to ALL modules and injected into the LLM context
 *   6. Feedback from the LLM response updates source credibility (learning loop)
 *
 * The workspace generalizes Constellation's Locus system to the entire
 * cognitive architecture. Locus operates as a nested workspace within
 * Constellation; the GlobalWorkspace operates at the system level across
 * all modules and sessions.
 *
 * Eclipse dynamics: when all slots are full, a brighter signal can displace
 * the dimmest occupant (with hysteresis margin to prevent oscillation).
 * Occupancy decays over ticks — old signals lose effective brightness,
 * making room for fresh information.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type {
  CognitiveSignal,
  WorkspaceSlot,
  GlobalWorkspaceConfig,
  TraitVector,
} from './cognitive-signal.js'
import { DEFAULT_WORKSPACE_CONFIG, UNITY_PRESET } from './cognitive-signal.js'
import { SystemLuminanceScorer } from './luminance.js'
import { CoalitionDetector } from './coalition.js'
import type { Coalition } from './coalition.js'
import { WorkspaceMemory } from './workspace-memory.js'
import { FeedbackTracker } from './feedback-tracker.js'
import type { FeedbackResult } from './feedback-tracker.js'
import {
  buildAttentionSchema,
  formatAttentionSchema,
  type AttentionSchema,
  type EclipseRecord,
} from './attention-schema.js'
import type {
  WorkspaceResponse,
  WorkspaceResponseHandler,
  ResponsePattern,
} from './radiance-types.js'


type Unsubscribe = () => void


export class GlobalWorkspace {
  private slots: WorkspaceSlot[]
  private config: GlobalWorkspaceConfig
  private scorer: SystemLuminanceScorer
  private coalitions: CoalitionDetector
  private memory: WorkspaceMemory
  private feedback: FeedbackTracker
  private logger: ILogger
  private eventBus?: IEventBus

  // C-POLY-1: Workspace trait vector for trait-aware credibility scoring
  private workspaceTraitVector: TraitVector

  // Pending signals below ignition threshold (for coalition detection)
  private pendingSignals: CognitiveSignal[] = []

  // Eclipse history for attention schema
  private eclipseHistory: EclipseRecord[] = []

  // Counters
  private totalSubmitted = 0
  private totalIgnited = 0
  private tickCount = 0
  private submittedThisTick = 0

  // Threshold adaptation
  private recentTickSubmissions: number[] = []
  private previousThreshold: number

  // Session tracking
  private activeSessionCount = 1

  // Broadcast subscribers
  private broadcastHandlers: Array<(signals: CognitiveSignal[]) => void> = []

  // Response channel subscribers (bidirectional broadcast — modules return context)
  private responseHandlers = new Map<string, WorkspaceResponseHandler>()

  // Last collected response pattern (for observer consumption)
  private lastResponsePattern: ResponsePattern | null = null

  // Signals that were active during the current/last turn (for feedback)
  private lastAssembledSignals: CognitiveSignal[] = []


  constructor(logger: ILogger, config?: Partial<GlobalWorkspaceConfig>) {
    this.config = { ...DEFAULT_WORKSPACE_CONFIG, ...config }
    this.logger = logger.child ? logger.child('workspace') : logger
    this.workspaceTraitVector = this.config.workspaceTraitVector ?? UNITY_PRESET
    this.scorer = new SystemLuminanceScorer(this.config.weights)
    this.scorer.updateWorkspaceTraitVector(this.workspaceTraitVector)
    this.coalitions = new CoalitionDetector()
    this.memory = new WorkspaceMemory()
    this.feedback = new FeedbackTracker(this.memory)
    this.previousThreshold = this.config.ignitionThreshold

    // Initialize empty slots
    this.slots = Array.from({ length: this.config.slots }, (_, i) => ({
      index: i,
      signal: null,
      occupiedSince: null,
      occupancyTicks: 0,
    }))

    this.logger.info('[Workspace] Initialized', {
      slots: this.config.slots,
      threshold: this.config.ignitionThreshold,
      workspaceTraitVector: this.workspaceTraitVector,
    })
  }


  setEventBus(bus: IEventBus): void {
    this.eventBus = bus
  }

  setActiveSessionCount(count: number): void {
    this.activeSessionCount = Math.max(1, count)
  }

  /**
   * Update the workspace trait vector for trait-aware credibility scoring (C-POLY-1).
   * Signals from traits aligned with workspace context get a credibility boost.
   */
  setTraitVector(traitVector: TraitVector): void {
    this.workspaceTraitVector = traitVector
    this.scorer.updateWorkspaceTraitVector(traitVector)
    this.logger.debug('[Workspace] Trait vector updated', { traitVector })
  }



  /**
   * Submit a signal for workspace competition.
   * The signal is scored, checked against the ignition threshold,
   * and either placed in a slot (conscious) or kept pending (unconscious).
   *
   * Returns true if the signal ignited (entered workspace).
   */
  submit(signal: CognitiveSignal): boolean {
    this.totalSubmitted++
    this.submittedThisTick++
    this.memory.recordSubmission(signal.source)

    signal.luminance = this.scorer.score(
      signal,
      this.slots,
      this.memory,
      this.activeSessionCount,
    )

    return this.tryIgnite(signal)
  }

  /**
   * Submit a pre-scored signal (for Locus forwarding or modules with custom scoring).
   */
  submitScored(signal: CognitiveSignal): boolean {
    this.totalSubmitted++
    this.memory.recordSubmission(signal.source)
    return this.tryIgnite(signal)
  }


  private tryIgnite(signal: CognitiveSignal): boolean {
    let effectiveLuminance = signal.luminance.composite

    // Coalition boost for sub-threshold signals
    if (this.config.coalitionsEnabled && effectiveLuminance < this.config.ignitionThreshold) {
      const { boost, coalitions } = this.coalitions.detectCoalitions(signal, this.pendingSignals)
      if (boost > 0) {
        effectiveLuminance += boost
        signal.coalitionIds = coalitions.map(c => c.coalitionId)
      }
    }

    // Check ignition threshold
    if (effectiveLuminance < this.config.ignitionThreshold) {
      this.pendingSignals.push(signal)
      // Keep pending list bounded
      if (this.pendingSignals.length > 50) {
        this.pendingSignals = this.pendingSignals.slice(-30)
      }
      return false
    }

    // Signal is bright enough — find a slot
    const emptySlot = this.slots.find(s => s.signal === null)
    if (emptySlot) {
      this.placeInSlot(emptySlot, signal)
      this.totalIgnited++
      this.emitIgnition(signal)
      return true
    }

    // All slots occupied — try to eclipse the dimmest
    const dimmest = this.findDimmestSlot()
    if (!dimmest || !dimmest.signal) return false

    const dimmestEffective = this.effectiveLuminance(dimmest)
    if (effectiveLuminance > dimmestEffective + this.config.eclipseMargin) {
      const eclipsed = dimmest.signal
      this.recordEclipse(eclipsed, 'eclipsed')
      this.placeInSlot(dimmest, signal)
      dimmest.eclipsedSignalId = eclipsed.signalId
      this.totalIgnited++
      this.emitEclipse(signal, eclipsed)
      return true
    }

    // Bright enough to ignite but not to eclipse — dropped (not pending)
    return false
  }


  private placeInSlot(slot: WorkspaceSlot, signal: CognitiveSignal): void {
    slot.signal = signal
    slot.occupiedSince = Date.now()
    slot.occupancyTicks = 0
  }

  private findDimmestSlot(): WorkspaceSlot | undefined {
    let dimmest: WorkspaceSlot | undefined
    let dimmestLuminance = Infinity

    for (const slot of this.slots) {
      if (!slot.signal) continue
      const effective = this.effectiveLuminance(slot)
      if (effective < dimmestLuminance) {
        dimmestLuminance = effective
        dimmest = slot
      }
    }

    return dimmest
  }

  /**
   * Effective luminance decays with occupancy — old signals lose brightness.
   * Linear decay: 10% per tick, minimum 20% of original.
   */
  private effectiveLuminance(slot: WorkspaceSlot): number {
    if (!slot.signal) return 0
    const base = slot.signal.luminance.composite
    return base * Math.max(0.2, 1.0 - slot.occupancyTicks * 0.1)
  }



  /**
   * Assemble workspace content for injection into the LLM context.
   * Returns occupied signals formatted as injection parts, sorted by luminance.
   * This replaces InjectionAggregator.aggregate() in the turn pipeline.
   */
  assemble(sessionId: string): Array<{ content: string; source: string }> {
    const occupied = this.slots
      .filter(s => s.signal !== null)
      .sort((a, b) => {
        const la = this.effectiveLuminance(a)
        const lb = this.effectiveLuminance(b)
        return lb - la
      })
      .map(s => s.signal!)

    // Filter to session-relevant signals ('*' = all signals)
    const relevant = sessionId === '*'
      ? occupied
      : occupied.filter(s => s.sessionId === sessionId || s.sessionId === '*')

    // Truncate to total budget
    const parts: Array<{ content: string; source: string }> = []
    let totalChars = 0

    for (const signal of relevant) {
      const content = signal.content.slice(0, this.config.slotBudget)
      if (totalChars + content.length > this.config.totalBudget) break
      parts.push({ content, source: signal.source })
      totalChars += content.length
    }

    // Optionally append attention schema as metacognitive context
    if (this.config.injectAttentionSchema) {
      const schema = this.getAttentionSchema()
      const schemaText = formatAttentionSchema(schema)
      if (totalChars + schemaText.length <= this.config.totalBudget) {
        parts.push({ content: schemaText, source: 'workspace:attention' })
      }
    }

    // Track for feedback analysis
    this.lastAssembledSignals = relevant

    return parts
  }



  /**
   * Broadcast current workspace state to all subscribers.
   * Called after assembly, before the LLM call.
   */
  broadcast(): void {
    const signals = this.slots
      .filter(s => s.signal !== null)
      .map(s => s.signal!)

    for (const handler of this.broadcastHandlers) {
      try {
        handler(signals)
      } catch {
        // Non-critical — don't let broadcast failures block the turn
      }
    }

    if (this.eventBus) {
      void (this.eventBus as any).emit({
        type: 'workspace:broadcast',
        signals: signals.map(s => ({
          signalId: s.signalId,
          source: s.source,
          type: s.type,
          contentPreview: s.content.slice(0, 200),
          luminance: s.luminance.composite,
        })),
        slotCount: this.config.slots,
        occupiedCount: signals.length,
        threshold: this.config.ignitionThreshold,
        timestamp: Date.now(),
      })
    }
  }

  /**
   * Subscribe to workspace broadcasts.
   */
  onBroadcast(handler: (signals: CognitiveSignal[]) => void): Unsubscribe {
    this.broadcastHandlers.push(handler)
    return () => {
      const idx = this.broadcastHandlers.indexOf(handler)
      if (idx >= 0) this.broadcastHandlers.splice(idx, 1)
    }
  }


  /**
   * Register a response handler for the bidirectional broadcast channel.
   * When the workspace broadcasts, this handler is called and may return
   * relevant context (WorkspaceResponse) or null for silence.
   */
  onRadiance(source: string, handler: WorkspaceResponseHandler): Unsubscribe {
    this.responseHandlers.set(source, handler)
    return () => { this.responseHandlers.delete(source) }
  }

  /**
   * Collect responses from all registered response handlers.
   * Called after broadcast to build the ResponsePattern.
   */
  async collectResponses(signals: CognitiveSignal[]): Promise<ResponsePattern> {
    const responses: ResponsePattern['responses'] = []
    const respondedSources = new Set<string>()

    const broadcastSummary = signals.map(s => ({
      signalId: s.signalId,
      source: s.source,
      type: s.type,
      contentPreview: s.content.slice(0, 200),
      luminance: s.luminance.composite,
    }))

    const entries = [...this.responseHandlers.entries()]
    const results = await Promise.allSettled(
      entries.map(async ([source, handler]) => {
        const response = await handler(signals)
        return { source, response }
      }),
    )

    for (const result of results) {
      if (result.status === 'fulfilled') {
        const { source, response } = result.value
        if (response) {
          respondedSources.add(source)
          responses.push({
            source,
            disposition: response.disposition,
            contentPreview: response.content.slice(0, 500),
            confidence: response.confidence,
            type: response.type,
            wasExpected: false,
          })
        } else {
          responses.push({
            source,
            disposition: 'silent',
            contentPreview: '',
            confidence: 0,
            type: 'context',
            wasExpected: false,
          })
        }
      } else {
        const entry = entries[results.indexOf(result)]
        if (entry) {
          this.logger.warn('Response handler failed', {
            source: entry[0],
            error: String(result.reason),
          })
        }
      }
    }

    let convergent = 0, divergent = 0, lateral = 0, silent = 0
    for (const r of responses) {
      switch (r.disposition) {
        case 'convergent': convergent++; break
        case 'divergent': divergent++; break
        case 'lateral': lateral++; break
        case 'silent': silent++; break
      }
    }

    const pattern: ResponsePattern = {
      broadcastSignals: broadcastSummary,
      responses,
      unexpectedSilences: [],
      unexpectedResponses: [],
      convergentCount: convergent,
      divergentCount: divergent,
      lateralCount: lateral,
      silentCount: silent,
      totalModules: this.responseHandlers.size,
      timestamp: Date.now(),
    }

    this.lastResponsePattern = pattern
    return pattern
  }

  /**
   * Get the last collected response pattern (for observer consumption).
   */
  getLastResponsePattern(): ResponsePattern | null {
    return this.lastResponsePattern
  }



  /**
   * Process turn-end feedback: detect which signals were incorporated.
   * Updates source credibility in workspace memory.
   */
  processFeedback(response: string): FeedbackResult[] {
    if (!this.config.feedbackEnabled) return []
    return this.feedback.analyzeResponse(response, this.lastAssembledSignals)
  }



  /**
   * Run per-turn maintenance: decay occupancy, adapt threshold, clean up.
   * Called once per turn by the turn pipeline.
   */
  tick(): void {
    this.tickCount++

    // Record per-tick submission count for adaptive threshold, then reset
    this.recentTickSubmissions.push(this.submittedThisTick)
    if (this.recentTickSubmissions.length > 5) this.recentTickSubmissions.shift()
    this.submittedThisTick = 0

    // Decay occupancy on all occupied slots
    for (const slot of this.slots) {
      if (!slot.signal) continue
      slot.occupancyTicks++

      // Natural expiry
      if (slot.occupancyTicks > this.config.maxOccupancyTicks) {
        this.recordEclipse(slot.signal, 'expired')
        slot.signal = null
        slot.occupiedSince = null
        slot.occupancyTicks = 0
      }
    }

    // Adapt ignition threshold
    if (this.config.adaptiveThreshold) {
      this.adaptThreshold()
    }

    // Prune coalitions and pending signals
    this.coalitions.prune()
    if (this.pendingSignals.length > 30) {
      this.pendingSignals = this.pendingSignals.slice(-20)
    }

    // Trim eclipse history
    if (this.eclipseHistory.length > 50) {
      this.eclipseHistory = this.eclipseHistory.slice(-30)
    }
  }


  /**
   * Adaptive threshold: rises under signal pressure, falls during quiet periods.
   */
  private adaptThreshold(): void {
    const occupiedCount = this.slots.filter(s => s.signal !== null).length

    const avgPerTick = this.recentTickSubmissions.length > 0
      ? this.recentTickSubmissions.reduce((a, b) => a + b, 0) / this.recentTickSubmissions.length
      : 0

    // High pressure: many signals per tick competing for few slots → raise threshold
    if (avgPerTick > this.config.slots * 3 && occupiedCount >= this.config.slots - 1) {
      this.config.ignitionThreshold = Math.min(
        this.config.thresholdMax,
        this.config.ignitionThreshold + 0.02,
      )
    }
    // Low pressure: slots mostly empty → lower threshold
    else if (occupiedCount < this.config.slots / 2) {
      this.config.ignitionThreshold = Math.max(
        this.config.thresholdMin,
        this.config.ignitionThreshold - 0.01,
      )
    }
  }



  /**
   * Get the current workspace state as a snapshot.
   */
  getSnapshot(): {
    slots: WorkspaceSlot[]
    pendingCount: number
    totalSubmitted: number
    totalIgnited: number
    ignitionRate: number
    threshold: number
    tickCount: number
  } {
    return {
      slots: this.slots.map(s => ({ ...s })),
      pendingCount: this.pendingSignals.length,
      totalSubmitted: this.totalSubmitted,
      totalIgnited: this.totalIgnited,
      ignitionRate: this.totalSubmitted > 0 ? this.totalIgnited / this.totalSubmitted : 0,
      threshold: this.config.ignitionThreshold,
      tickCount: this.tickCount,
    }
  }

  /**
   * Get signals currently in focus (occupied slots).
   */
  getCurrentFoci(): CognitiveSignal[] {
    return this.slots
      .filter(s => s.signal !== null)
      .map(s => s.signal!)
  }

  /**
   * Build the full attention schema — metacognitive self-model.
   */
  getAttentionSchema(): AttentionSchema {
    const thresholdTrend = this.config.ignitionThreshold > this.previousThreshold ? 'rising'
      : this.config.ignitionThreshold < this.previousThreshold ? 'falling'
      : 'stable'
    this.previousThreshold = this.config.ignitionThreshold

    return buildAttentionSchema(
      this.slots,
      this.eclipseHistory,
      this.config.ignitionThreshold,
      thresholdTrend,
      this.memory.getAllRecords(),
      this.coalitions.getActiveCoalitions(),
      this.totalSubmitted,
      this.totalIgnited,
    )
  }

  /**
   * Get workspace memory (for credibility inspection).
   */
  getMemory(): WorkspaceMemory {
    return this.memory
  }


  /**
   * Reset the workspace to initial state. Useful for testing and hot-reload.
   */
  reset(): void {
    for (const slot of this.slots) {
      slot.signal = null
      slot.occupiedSince = null
      slot.occupancyTicks = 0
      slot.eclipsedSignalId = undefined
    }
    this.pendingSignals = []
    this.eclipseHistory = []
    this.lastAssembledSignals = []
    this.totalSubmitted = 0
    this.totalIgnited = 0
    this.submittedThisTick = 0
    this.tickCount = 0
    this.recentTickSubmissions = []
    this.config.ignitionThreshold = DEFAULT_WORKSPACE_CONFIG.ignitionThreshold
    this.previousThreshold = this.config.ignitionThreshold
  }



  private emitIgnition(signal: CognitiveSignal): void {
    if (!this.eventBus) return
    void (this.eventBus as any).emit({
      type: 'workspace:ignition',
      signalId: signal.signalId,
      source: signal.source,
      signalType: signal.type,
      luminance: signal.luminance.composite,
      coalitionIds: signal.coalitionIds,
      timestamp: Date.now(),
    })
  }

  private emitEclipse(newSignal: CognitiveSignal, eclipsed: CognitiveSignal): void {
    if (!this.eventBus) return
    void (this.eventBus as any).emit({
      type: 'workspace:eclipse',
      newSignalId: newSignal.signalId,
      newSource: newSignal.source,
      newLuminance: newSignal.luminance.composite,
      eclipsedSignalId: eclipsed.signalId,
      eclipsedSource: eclipsed.source,
      eclipsedLuminance: eclipsed.luminance.composite,
      timestamp: Date.now(),
    })
  }

  private recordEclipse(signal: CognitiveSignal, reason: EclipseRecord['reason']): void {
    this.eclipseHistory.push({
      signalId: signal.signalId,
      source: signal.source,
      type: signal.type,
      reason,
      luminanceAtExit: signal.luminance.composite,
      exitedAt: Date.now(),
    })
  }
}
