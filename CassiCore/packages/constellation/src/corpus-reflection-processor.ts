/**
 * CorpusReflectionProcessor — The bridge between friction detection and self-editing
 *
 * This processor sits between the Subconscious (which observes everything)
 * and the self-edit system (which stores and evaluates edit requests).
 *
 * It does three things:
 *
 * 1. COLLECT: Listens for friction-related observations from the Subconscious
 *    and HeuristicObserver, translating them into FrictionSignals.
 *
 * 2. AGGREGATE: Groups friction signals by pattern (same kind + similar paths)
 *    across sessions, building edit requests when cross-session recurrence
 *    suggests a systemic issue rather than a one-off.
 *
 * 3. REFLECT: Periodically asks the corpus-level qualitative questions:
 *    - "What actually happened?" (factual, not evaluative)
 *    - "Where was the friction?" (noticed, not judged)
 *    - "What would we do differently next time?" (forward-looking)
 *
 * The processor does NOT make edit decisions. It produces EditRequests
 * that bubble up to Cassi (the top-level session) for evaluation.
 *
 * Architecture:
 *   Subconscious observations
 *     → CorpusReflectionProcessor (this)
 *       → FrictionSignals → SelfEditStore
 *       → EditRequests → SelfEditStore
 *         → Cassi reads pending requests
 *           → Cassi evaluates (spawns analysis helixes if needed)
 *             → Cassi applies or rejects
 */

import { v4 as uuidv4 } from 'uuid'

import {
  classifyEditAuthority,
} from './self-edit-types.js'
import type {
  FrictionSignal,
  FrictionKind,
  OutcomeSignal,
  ReflectionSignal,
  EditRequest,
  EditKind,
  EditAuthority,
  ISelfEditStore,
} from './self-edit-types.js'
import type { Observation, Anomaly } from '../subconscious/types.js'
import type { BrainstemAnnotation, DetectedPattern } from '../helix/brainstem-types.js'
import type { ILogger, IEventBus } from '../../../types/interfaces.js'


// ═══════════════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════════════

export interface CorpusReflectionConfig {
  /** Whether the reflection processor is enabled */
  enabled: boolean
  /** Minimum cross-session recurrence before generating an edit request */
  minCrossSessionRecurrence: number
  /** How far back to look for friction patterns (ms) */
  frictionWindowMs: number
  /** How often to run the aggregation sweep (ms) */
  aggregationIntervalMs: number
  /** Maximum pending edit requests before throttling */
  maxPendingRequests: number
}

export const DEFAULT_REFLECTION_CONFIG: CorpusReflectionConfig = {
  enabled: true,
  minCrossSessionRecurrence: 3,
  frictionWindowMs: 7 * 24 * 60 * 60 * 1000, // 7 days
  aggregationIntervalMs: 5 * 60 * 1000, // 5 minutes
  maxPendingRequests: 20,
}


// ═══════════════════════════════════════════════════════════════════
// Pattern → Friction Kind Mapping
// ═══════════════════════════════════════════════════════════════════

/**
 * Maps subconscious observation patterns to friction kinds.
 * This is deliberately conservative — we only map patterns we're
 * confident represent genuine friction, not noise.
 */
const PATTERN_TO_FRICTION: Record<string, FrictionKind> = {
  // Brainstem patterns
  'paralysis': 'repeated-work',
  'drift': 'wrong-path',
  'stalling': 'unnecessary-steps',

  // Subconscious heuristic patterns
  'high_turn_rate': 'unnecessary-steps',
  'trust_decline': 'misleading-guidance',
  'trust_outcome_issue': 'tool-mismatch',
  'permission_denied': 'unclear-boundary',
  'high_risk_permission_allowed': 'unclear-boundary',

  // Dialectic patterns
  'dialectic_tension': 'coordination-gap',
  'dialectic_gap': 'missing-context',
  'dialectic_edge_case': 'unclear-boundary',
  'dialectic_assumption': 'stale-knowledge',
}


// ═══════════════════════════════════════════════════════════════════
// Processor
// ═══════════════════════════════════════════════════════════════════

export class CorpusReflectionProcessor {
  private readonly logger: ILogger
  private readonly config: CorpusReflectionConfig
  private readonly store: ISelfEditStore

  /** Pending friction signals not yet aggregated */
  private pendingFriction: FrictionSignal[] = []
  /** Pending outcome signals from completed sessions */
  private pendingOutcomes: OutcomeSignal[] = []
  /** Pending reflection signals */
  private pendingReflections: ReflectionSignal[] = []

  /** Aggregation timer */
  private aggregationTimer?: NodeJS.Timeout
  /** Unsubscribe functions for event bus listeners */
  private unsubscribers: Array<() => void> = []

  constructor(
    store: ISelfEditStore,
    logger: ILogger,
    config?: Partial<CorpusReflectionConfig>,
  ) {
    this.store = store
    this.logger = logger.child?.('corpus-reflection') ?? logger
    this.config = { ...DEFAULT_REFLECTION_CONFIG, ...config }
  }


  /**
   * Connect to the event bus and start listening for friction signals.
   */
  start(eventBus: IEventBus): void {
    if (!this.config.enabled) {
      this.logger.info('CorpusReflectionProcessor: disabled')
      return
    }

    // Listen for subconscious observations that may indicate friction
    this.subscribe(eventBus, 'consciousness:observation', (event: any) => {
      this.onObservation(event.observation)
    })

    // Listen for subconscious anomalies
    this.subscribe(eventBus, 'consciousness:anomaly', (event: any) => {
      this.onAnomaly(event.anomaly)
    })

    // Listen for brainstem annotations (from helix sessions)
    this.subscribe(eventBus, 'brainstem:annotation', (event: any) => {
      this.onBrainstemAnnotation(event.annotation, event.sessionId, event.helixId)
    })

    // Listen for session completion (to gather outcome signals)
    this.subscribe(eventBus, 'session:completed', (event: any) => {
      this.onSessionCompleted(event)
    })

    // Listen for helix completion (richer outcome data)
    this.subscribe(eventBus, 'constellation:helix:completed', (event: any) => {
      this.onHelixCompleted(event)
    })

    // Start the periodic aggregation sweep
    this.aggregationTimer = setInterval(() => {
      this.runAggregationSweep()
    }, this.config.aggregationIntervalMs)
    try { (this.aggregationTimer as any).unref?.() } catch {}

    this.logger.info('CorpusReflectionProcessor: started', {
      minRecurrence: this.config.minCrossSessionRecurrence,
      aggregationIntervalMs: this.config.aggregationIntervalMs,
    })
  }

  stop(): void {
    for (const unsub of this.unsubscribers) {
      try { unsub() } catch {}
    }
    this.unsubscribers = []

    if (this.aggregationTimer) {
      clearInterval(this.aggregationTimer)
      this.aggregationTimer = undefined
    }

    this.logger.info('CorpusReflectionProcessor: stopped')
  }


  // ═══════════════════════════════════════════════════════════════════
  // Event Handlers — Translate observations into friction signals
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Process a subconscious observation for friction signals.
   */
  private onObservation(obs: Observation): void {
    for (const pattern of obs.patterns) {
      const frictionKind = PATTERN_TO_FRICTION[pattern]
      if (!frictionKind) continue

      const signal: FrictionSignal = {
        kind: frictionKind,
        whatHappened: obs.summary,
        context: `Pattern: ${pattern} (confidence: ${obs.confidence})`,
        involvedPaths: obs.relatedEventTypes,
        recurrence: 1,
        observedAt: obs.timestamp,
        sessionId: obs.sessionId ?? 'system',
      }

      this.pendingFriction.push(signal)
      this.store.recordFriction(signal)
    }
  }

  /**
   * Process a subconscious anomaly — anomalies are always friction.
   */
  private onAnomaly(anomaly: Anomaly): void {
    const signal: FrictionSignal = {
      kind: this.anomalyToFrictionKind(anomaly),
      whatHappened: anomaly.description,
      context: `Anomaly (severity: ${anomaly.severity})${anomaly.suggestedAction ? ` — ${anomaly.suggestedAction}` : ''}`,
      involvedPaths: anomaly.eventTypes,
      recurrence: 1,
      observedAt: anomaly.timestamp,
      sessionId: anomaly.sessionId ?? 'system',
    }

    this.pendingFriction.push(signal)
    this.store.recordFriction(signal)
  }

  /**
   * Process a brainstem annotation — these carry rich session-level friction data.
   */
  private onBrainstemAnnotation(
    annotation: BrainstemAnnotation,
    sessionId?: string,
    helixId?: string,
  ): void {
    // Only friction-indicating patterns
    if (annotation.pattern === 'none') return

    const frictionKind = this.brainstemPatternToFrictionKind(annotation.pattern)

    const signal: FrictionSignal = {
      kind: frictionKind,
      whatHappened: `Brainstem detected ${annotation.pattern}: ${annotation.synthesis || annotation.trainingNote}`,
      context: `Work unit ${annotation.workUnitId}, annotation: ${annotation.annotation}, axon step: ${annotation.axonStep}`,
      involvedPaths: [],
      recurrence: 1,
      observedAt: annotation.timestamp,
      sessionId: sessionId ?? 'unknown',
      posture: helixId ? `helix:${helixId}` : undefined,
    }

    this.pendingFriction.push(signal)
    this.store.recordFriction(signal)

    // If the brainstem also produced guidance, that's a reflection signal
    if (annotation.guidance) {
      const reflection: ReflectionSignal = {
        whatDifferently: annotation.guidance,
        why: annotation.synthesis || 'Brainstem pattern detection',
        relatesTo: `helix:${helixId ?? 'unknown'}`,
        scope: 'this-pattern',
        reflectedAt: annotation.timestamp,
        sessionId: sessionId ?? 'unknown',
      }
      this.pendingReflections.push(reflection)
    }
  }

  /**
   * Process a session completion — produces outcome signals.
   */
  private onSessionCompleted(event: any): void {
    const outcome: OutcomeSignal = {
      worked: !event.error,
      whatWorkedMeans: event.error
        ? 'Session completed without errors'
        : 'Session produced output',
      whatHappened: event.summary ?? 'Session completed',
      whatWentWrong: event.error ? String(event.error) : undefined,
      timeProportionate: 'unclear', // Can't determine without more context
      determinedAt: Date.now(),
      sessionId: event.sessionId ?? 'unknown',
    }

    this.pendingOutcomes.push(outcome)
  }

  /**
   * Process a helix completion — richer outcome data.
   */
  private onHelixCompleted(event: any): void {
    const outcome: OutcomeSignal = {
      worked: event.status === 'completed',
      whatWorkedMeans: 'Helix completed its goal successfully',
      whatHappened: `Helix ${event.helixId} completed with status: ${event.status}`,
      whatWentWrong: event.error ? String(event.error) : undefined,
      timeProportionate: 'unclear',
      determinedAt: Date.now(),
      sessionId: event.helixId ?? 'unknown',
    }

    this.pendingOutcomes.push(outcome)
  }


  // ═══════════════════════════════════════════════════════════════════
  // Aggregation — Group friction into edit requests
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Periodic sweep that aggregates friction signals into edit requests.
   *
   * The key insight: a friction signal from ONE session might be a fluke.
   * The same friction across MULTIPLE sessions is a systemic issue worth
   * addressing. This is where cross-session recurrence matters.
   */
  private runAggregationSweep(): void {
    // Check if we're already at capacity for pending requests
    const pendingCount = this.store.getPendingRequests(1).length
    if (pendingCount >= this.config.maxPendingRequests) {
      this.logger.debug('CorpusReflectionProcessor: max pending requests reached, skipping sweep')
      return
    }

    const since = Date.now() - this.config.frictionWindowMs

    // Group friction by kind and check cross-session recurrence
    const frictionKinds: FrictionKind[] = [
      'repeated-work', 'wrong-path', 'missing-context', 'misleading-guidance',
      'unnecessary-steps', 'tool-mismatch', 'stale-knowledge', 'unclear-boundary',
      'coordination-gap',
    ]

    for (const kind of frictionKinds) {
      const crossSessionCount = this.store.countCrossSessionFriction(kind, undefined, since)

      if (crossSessionCount >= this.config.minCrossSessionRecurrence) {
        // Get the actual friction signals for context
        const signals = this.store.findFriction({ kind, since, limit: 20 })
        if (signals.length === 0) continue

        // Check if we already have a pending request for this pattern
        const existing = this.store.getPendingRequests(100)
        const alreadyPending = existing.some(r =>
          r.signals.friction.some(f => f.kind === kind),
        )
        if (alreadyPending) continue

        // Build the edit request
        const request = this.buildEditRequest(kind, signals, crossSessionCount)
        if (request) {
          this.store.submitRequest(request)
          this.logger.info('CorpusReflectionProcessor: edit request created', {
            requestId: request.id,
            kind: request.editKind,
            frictionKind: kind,
            crossSessionRecurrence: crossSessionCount,
          })
        }
      }
    }

    // Drain pending buffers
    this.pendingFriction = []
    this.pendingOutcomes = []
    this.pendingReflections = []
  }


  /**
   * Build an edit request from aggregated friction signals.
   *
   * This is where the qualitative questions get asked:
   * - What actually happened? → the friction signals tell us
   * - Where was the friction? → the kind + paths tell us
   * - What would we do differently? → the reflections tell us
   */
  private buildEditRequest(
    frictionKind: FrictionKind,
    signals: FrictionSignal[],
    crossSessionCount: number,
  ): EditRequest | undefined {
    // Determine edit kind from friction kind
    const editKind = this.frictionToEditKind(frictionKind)
    if (!editKind) return undefined

    // Extract involved paths across all signals
    const allPaths = new Set<string>()
    for (const s of signals) {
      for (const p of s.involvedPaths) allPaths.add(p)
    }

    // Build the suggestion from aggregated friction context
    const whatHappened = signals.map(s => s.whatHappened).join('\n')
    const contexts = signals.map(s => s.context).join('\n')

    // Gather any pending reflections related to this friction
    const relatedReflections = this.pendingReflections.filter(r =>
      r.scope !== 'this-task', // Only broader reflections
    )

    // Gather any pending outcomes
    const relatedOutcomes = this.pendingOutcomes.filter(o =>
      !o.worked || !o.timeProportionate,
    )

    const targetFiles = [...allPaths].slice(0, 5)

    // ── THE ONE RULE ──
    // Classify edit authority: does this touch files that shape how agents think?
    // If yes → cassi-only. Agents cannot modify their own prompts.
    const authority = classifyEditAuthority(editKind, targetFiles)

    return {
      id: uuidv4(),
      sourceSessionId: signals[0].sessionId,
      sourceHelixId: signals[0].posture?.startsWith('helix:')
        ? signals[0].posture.slice(6)
        : undefined,
      sourcePosture: signals[0].posture,
      editKind,
      signals: {
        friction: signals.slice(0, 10), // Cap at 10 for readability
        outcomes: relatedOutcomes.slice(0, 5),
        reflections: relatedReflections.slice(0, 5),
      },
      suggestion: {
        targetFiles,
        description: `Recurring ${frictionKind} friction detected across ${crossSessionCount} sessions`,
        currentProblem: whatHappened.slice(0, 2000),
        proposedImprovement: relatedReflections.length > 0
          ? relatedReflections.map(r => r.whatDifferently).join('; ')
          : `Address recurring ${frictionKind} pattern (specific improvement to be determined by Cassi)`,
      },
      crossSessionRecurrence: crossSessionCount,
      createdAt: Date.now(),
      status: 'pending',
      authority,
    }
  }


  // ═══════════════════════════════════════════════════════════════════
  // Public API — For Cassi to interact with
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Get pending edit requests for Cassi to evaluate.
   * Ordered by cross-session recurrence (most widespread friction first).
   */
  getPendingRequests(limit = 10): EditRequest[] {
    return this.store.getPendingRequests(limit)
  }

  /**
   * Get the full self-edit stats for observability.
   */
  getStats() {
    return this.store.getStats()
  }

  /**
   * Manually submit a friction signal (e.g., from Cassi's own observation).
   */
  submitFriction(signal: FrictionSignal): void {
    this.store.recordFriction(signal)
    this.logger.info('CorpusReflectionProcessor: manual friction recorded', {
      kind: signal.kind,
      sessionId: signal.sessionId,
    })
  }

  /**
   * Manually submit an edit request (e.g., from Cassi's direct observation).
   *
   * Enforces the one rule: if the edit targets behavior-shaping files,
   * it MUST have cassi-only authority. Local agents cannot bypass this.
   */
  submitEditRequest(request: EditRequest): void {
    // Re-classify authority to prevent spoofing — the source doesn't get to
    // decide its own authority level
    const actualAuthority = classifyEditAuthority(
      request.editKind,
      request.suggestion.targetFiles,
    )
    request.authority = actualAuthority

    this.store.submitRequest(request)
    this.logger.info('CorpusReflectionProcessor: edit request submitted', {
      requestId: request.id,
      editKind: request.editKind,
      authority: actualAuthority,
    })
  }

  /**
   * Attempt to apply an edit locally (without Cassi).
   *
   * Returns false and logs a warning if the edit requires Cassi's authority.
   * This is the enforcement point for the one rule.
   */
  canApplyLocally(request: EditRequest): boolean {
    const authority = classifyEditAuthority(
      request.editKind,
      request.suggestion.targetFiles,
    )

    if (authority === 'cassi-only') {
      this.logger.warn('CorpusReflectionProcessor: local edit blocked — requires Cassi', {
        requestId: request.id,
        editKind: request.editKind,
        targetFiles: request.suggestion.targetFiles,
      })
      return false
    }

    return true
  }


  // ═══════════════════════════════════════════════════════════════════
  // Helpers
  // ═══════════════════════════════════════════════════════════════════

  private subscribe(bus: IEventBus, eventType: string, handler: (event: any) => void): void {
    const unsub = (bus as any).on?.(eventType, handler)
    if (typeof unsub === 'function') {
      this.unsubscribers.push(unsub)
    }
  }

  private anomalyToFrictionKind(anomaly: Anomaly): FrictionKind {
    // Map anomaly characteristics to friction kinds
    if (anomaly.description.includes('crash') || anomaly.description.includes('error')) {
      return 'tool-mismatch'
    }
    if (anomaly.description.includes('trust')) {
      return 'misleading-guidance'
    }
    if (anomaly.description.includes('budget') || anomaly.description.includes('rate')) {
      return 'unnecessary-steps'
    }
    if (anomaly.description.includes('permission')) {
      return 'unclear-boundary'
    }
    if (anomaly.description.includes('silent') || anomaly.description.includes('unhealthy')) {
      return 'stale-knowledge'
    }
    return 'other'
  }

  private brainstemPatternToFrictionKind(pattern: DetectedPattern): FrictionKind {
    switch (pattern) {
      case 'paralysis': return 'repeated-work'
      case 'drift': return 'wrong-path'
      case 'stalling': return 'unnecessary-steps'
      case 'convergence': return 'coordination-gap' // Convergence itself isn't friction, but signals something worth noting
      default: return 'other'
    }
  }

  private frictionToEditKind(frictionKind: FrictionKind): EditKind | undefined {
    switch (frictionKind) {
      case 'misleading-guidance': return 'agents-update'
      case 'missing-context': return 'skill-update'
      case 'stale-knowledge': return 'doc-update'
      case 'unclear-boundary': return 'agents-update'
      case 'wrong-path': return 'prompt-update'
      case 'repeated-work': return 'skill-update'
      case 'unnecessary-steps': return 'config-update'
      case 'tool-mismatch': return 'tool-update'
      case 'coordination-gap': return 'config-update'
      case 'other': return undefined // Don't generate requests for unclassified friction
    }
  }
}
