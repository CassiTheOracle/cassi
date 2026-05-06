/**
 * Aurora — the cognitive state loop.
 *
 * Aurora is the emergent cognitive awareness that arises when model knowledge
 * (LARQL vindex) and personal memory (Mnemic Field) are merged into a unified
 * graph and projected as a living mental state.
 *
 * The feedback loop:
 *   1. Claustrum merges model knowledge + Mnemic Field → unified graph
 *   2. StateProjector serializes the mental state → text for context, vector for residual
 *   3. External client receives the mental state in its context window
 *   4. Client reasoning is observed → concepts extracted → graph nodes activated
 *   5. Mental state shifts → next turn sees an updated mind
 */

import path from 'node:path'
import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from '../mnemic-field/cortex.js'
import { getDataDir } from '../../utils/paths.js'
import type { PortalBridge } from '../memory-bridge/portal-bridge.js'
import type { ResonantAffectSignal } from '../memory-bridge/resonant-affect.js'
import type { DreamDiscovery } from '../memory-bridge/dream-engine.js'
import { Claustrum, ObserverInsightCollector } from './claustrum.js'
import type { CycleIdAware } from './larql-provider.js'
import { StateProjector } from './state-projector.js'
import type {
  MentalState,
  MentalStateUpdate,
  ReasoningMomentum,
  ReasoningShift,
  ModelKnowledgeProvider,
  AuroraConfig,
  CurationCycleResult,
  CognitiveEdge,
  ReasoningRecord,
  ReverieInsight,
  UnifiedGraph,
} from './types.js'
import { AURORA_DEFAULTS } from './types.js'
import type { ReverieInferenceProvider } from './types.js'
import { ReverieReasoningObserver, makeReasoningRecordId } from './reverie-reasoning-observer.js'
import type {
  CoherenceReport,
  SpecCategory,
  SpecType,
  ProposalStatus,
  SpecProposal,
  SpecChannelStats,
} from './types.js'
import { CoherenceChecker } from './coherence-checker.js'
import type { CoherenceCheckResult, CoherenceConfig, AuroraSnapshot } from './coherence-checker.js'
import { WelfareAggregator, createWelfareAggregator } from './welfare-aggregator.js'
import type { WelfareStressSnapshot, RecommendedAction, WelfareAggregatorConfig, WelfareFlag } from './welfare-aggregator.js'
import { SubstrateModificationAudit } from './modification-chain-audit.js'
import type { ModificationChain, ChainQueryOptions } from './modification-chain-audit.js'
import { EventJournal, createEventJournal } from './event-journal.js'
import type { EventCategory, EventReference, QueryOptions, AuroraEventInput } from './event-journal.js'
import { CassiSpecChannel } from './cassi-spec-channel.js'
import type { AuroraPersistence, SessionHandle } from './persistence.js'
import { GapDetector } from './gap-detector.js'
import type { GapCategory as GapCategoryT, GapStatus as GapStatusT } from './gap-detector.js'
import { MeditationSeeder } from './meditation-seeder.js'
import { AutoScheduler } from './auto-scheduler.js'
import type { SchedulingResult } from './auto-scheduler.js'
import { OverlayLayer } from './overlay-layer.js'
import { TraceReplayEngine } from './trace-replay.js'
import type { TraceReplayConfig, RankedTrace, ScheduledReplay, TraceRetrievalQuery, ContextReplayOptions, StateReplayOptions } from './trace-replay-types.js'
import { SaturationDetector } from './saturation-detector.js'
import type { SaturationConfig, SaturationScore, TurnSample } from './saturation-detector.js'
import { CounterfactualEngine } from './counterfactual-engine.js'
import type { ForkScope, Perturbation, ClaustrumFork, ObservationKind, CounterfactualResult, ActivatedNodesDiff, ReasoningShiftDiff, RetrievalDistributionEntry } from './counterfactual-engine.js'
import { DiversityFloor } from './diversity-floor.js'
import type { DiversityFloorConfig, DiversityCategory, CategoryDiversityState, CompositeDiversity } from './diversity-floor.js'
import { RefusalChannel } from './refusal-channel.js'
import type { ActionKind, ActionHandle, ActionResolution, ActionRecord, RefusalChannelConfig, ProposedAction, RefusalFilter, ConsentSource } from './refusal-channel.js'
import type { OverlayPatch, OverlayApplyResult, OverlayStats } from './overlay-layer.js'
import { SelfNarrativeRenderer } from './self-narrative-renderer.js'
import type { SelfNarrative } from './self-narrative-renderer.js'
import { CompositionStore } from './composition/store.js'
import { PostureCoherenceDetector } from './coherence-detector/index.js'
import type { CoherenceCheck } from './coherence-detector/types.js'
import type { DetectorInputs } from './coherence-detector/index.js'
import { CalibrationManager } from './calibration/manager.js'
import { CalibrationStore } from './calibration/store.js'
import type { CalibrationProbeSet, CalibrationResult, DriftReport, RunOptions } from './calibration/types.js'
import { parseComposition, detectSuppressive, layerSpecToString } from './composition/parser.js'
import { evaluatePredicate, evaluateStrength } from './composition/predicate.js'
import type { Affect, AffectLabel } from '../mnemic-field/types.js'
import {
  DEFAULT_TTL_TURNS,
  DEFAULT_MAGNITUDE_SCALE,
  DEFAULT_VINDEX_ID,
} from './composition/types.js'
import type {
  CompositionRecord,
  ActiveComposition,
  DefineCompositionOptions,
  InvokeCompositionOptions,
  InvocationRecord,
  InvocationTrigger,
} from './composition/types.js'

export { Claustrum, ObserverInsightCollector } from './claustrum.js'
export { StateProjector } from './state-projector.js'
export { LarqlKnowledgeProvider } from './larql-provider.js'
export { AuroraPersistence } from './persistence.js'
export { GapDetector } from './gap-detector.js'
export { CoherenceChecker } from './coherence-checker.js'
export { ReverieReasoningObserver } from './reverie-reasoning-observer.js'
export { SubstrateModificationAudit } from './modification-chain-audit.js'
export { CassiSpecChannel } from './cassi-spec-channel.js'
export { OverlayLayer } from './overlay-layer.js'
export { EventJournal, createEventJournal } from './event-journal.js'
export { WelfareAggregator, createWelfareAggregator } from './welfare-aggregator.js'
export { TraceReplayEngine } from './trace-replay.js'
export { SaturationDetector } from './saturation-detector.js'
export { DiversityFloor } from './diversity-floor.js'
export { SelfNarrativeRenderer } from './self-narrative-renderer.js'
export type { SelfNarrative } from './self-narrative-renderer.js'
export { RefusalChannel } from './refusal-channel.js'
export { CounterfactualEngine } from './counterfactual-engine.js'
export type { SessionHandle, SessionMetadata, AuroraPersistenceConfig } from './persistence.js'
export type { ReverieTier, ReverieAnalysisResult, ReverieEscalationConfig } from './reverie-reasoning-observer.js'
export type {
  MentalState,
  MentalStateUpdate,
  CognitiveNode,
  CognitiveEdge,
  ModelKnowledgeProvider,
  AuroraConfig,
  ReasoningRecord,
  ReverieInsight,
} from './types.js'
export type {
  ChainOriginSpec,
  ChainLinkType,
  ChainStatus,
  ChainPriority,
  ChainLink,
  ModificationChain,
  ChainQueryOptions,
} from './modification-chain-audit.js'
export type {
  GapCategory,
  GapStatus,
  GapSignalType,
  SignalDetail,
  GapCandidate,
  GapDetectorConfig,
} from './gap-detector.js'
export type {
  SpecCategory,
  ProposalStatus,
  SpecType,
  SpecMetadata,
  SpecProposal,
  ReviewAction,
  ReviewResult,
} from './cassi-spec-channel.js'
export type {
  CoherenceSignal,
  CoherenceCategory,
  CoherenceSeverity,
  CoherenceCheckInput,
  CoherenceCheckResult,
  AuroraSnapshot,
  MnemicFieldSnapshot,
  CortexSnapshot,
  AffectSnapshot,
  CoherenceConfig,
} from './coherence-checker.js'
export type {
  OverlayPatch,
  OverlayPatchOp,
  OverlayApplyResult,
  OverlayStats,
  OverlayFeatureHit,
} from './overlay-layer.js'
export type {
  WelfareFlag,
  RecommendedAction,
  StressTrend,
  WelfareStressSnapshot,
  WelfareAggregatorConfig,
} from './welfare-aggregator.js'
export type {
  EventCategory,
  EventReference,
  AuroraEventInput,
  AuroraEvent,
  QueryOptions,
} from './event-journal.js'
export type {
  TraceReplayConfig,
  RankedTrace,
  ScheduledReplay,
  TraceRetrievalQuery,
  ContextReplayOptions,
  StateReplayOptions,
} from './trace-replay-types.js'
export type {
  SaturationConfig,
  SaturationSignals,
  SaturationClassification,
  SaturationScore,
  TurnSample,
} from './saturation-detector.js'
export type {
  ProposedAction,
  ActionHandle,
  ActionResolution,
  ConsentSource,
  ActionRecord,
  RefusalFilter,
  RefusalChannelConfig,
} from './refusal-channel.js'
export type {
  ForkScope,
  Perturbation,
  ClaustrumFork,
  CounterfactualResult,
  ObservationKind,
} from './counterfactual-engine.js'

const MAX_RECENT_CONCEPTS = 200
const MAX_REASONING_RECORDS = 500

export class Aurora {
  private logger: ILogger
  private claustrum: Claustrum
  private projector: StateProjector

  /**
   * Buffer of typed observer insights from constellation/cluster/corpus
   * observers. Folded into the focused graph on each `buildState`.
   * Accessed externally via `getObserverSink()` so the constellation layer
   * can hand it to its `ObserverMemoryBridge`.
   */
  private observerCollector = new ObserverInsightCollector()

  /**
   * Monotonic Aurora cycle counter. Stamped onto every gate-KNN provenance
   * row so the claustrum-vindex snapshotter can attribute features to the
   * cycle that surfaced them. See docs/design/claustrum-vindex.md §6.
   */
  private cycleCounter = 0

  private currentState: MentalState | null = null
  private lastFingerprint: string | null = null
  private lastSerialization: string | null = null

  private recentConcepts: Map<string, number> = new Map()
  private turnCount = 0
  private conceptHistory: string[][] = []
  private maxConceptsPerTurn: number
  private curationCycleInterval: number

  /** Persisted reasoning observations — corpus for learning and re-analysis. */
  private reasoningLog: ReasoningRecord[] = []

  /** Reverie slow-path observer (optional — set via setReverieInferenceProvider). */
  private reverieObserver: ReverieReasoningObserver | null = null

  /** Configuration for Reverie integration. */
  private reverieMinTextLength: number
  private reverieSamplingRate: number
  private reverieTimeoutMs: number
  private reverieObservationCounters: Map<string, number> = new Map()

  /** Optional session ID for reasoning records. */
  private sessionId?: string

  /** Optional persistence layer for cross-session continuity (B6). */
  private persistence?: AuroraPersistence
  private persistenceSession?: SessionHandle

  /** Active task for context in Reverie analysis (wired from lamina). */
  private activeTask: string | null = null

  /** Recent session decisions for contradiction detection. */
  private recentDecisions: string[] = []

  /** In-flight Reverie analyses for cleanup. */
  private inFlightAnalyses: Set<Promise<void>> = new Set()
  private maxInFlightAnalyses = 5

  /** Phase 4: Gap detector for C1 self-curing topology. */
  private gapDetector: GapDetector | null = null

  /** Phase 4: Meditation seeder for C1.2 — proposes meditation seeds from gaps. */
  private meditationSeeder: MeditationSeeder | null = null

  /** Phase 4: Auto-scheduler for C1.3 — autonomy-gated, off by default. */
  private autoScheduler: AutoScheduler | null = null

  /** Phase 4: Coherence checker for N6 cross-module coherence. */
  private coherenceChecker: CoherenceChecker | null = null

  /** Phase 4: Modification chain auditor for SMCA. */
  private modificationAuditor: SubstrateModificationAudit | null = null

  /** Phase 4: Event journal for AEJ - unified audit log. */
  private eventJournal: EventJournal | null = null

  /** Phase 4: Welfare aggregator for WSA - cross-spec welfare monitoring. */
  private welfareAggregator: WelfareAggregator | null = null

  /** Phase 4: Cassi spec channel for N4. */
  private cassiSpecChannel: CassiSpecChannel | null = null

  /** Phase 4: Overlay layer for C3 bidirectional claustrum surgery. */
  private overlayLayer: OverlayLayer | null = null
  private refusalChannel: RefusalChannel | null = null

  /** Phase 3: Trace replay engine for B3 reasoning trace retrieval. */
  private traceReplay: TraceReplayEngine | null = null
  private saturationDetector: SaturationDetector | null = null
  private diversityFloor: DiversityFloor | null = null
  private counterfactualEngine: CounterfactualEngine | null = null
  private selfNarrativeRenderer: SelfNarrativeRenderer | null = null

  /** Phase 2 (B1): Concept-arithmetic composition store + active invocation list. */
  private compositionStore: CompositionStore | null = null
  private activeCompositionsList: ActiveComposition[] = []

  /** Phase 2 (N2): Posture coherence detector. */
  private postureCoherenceDetector: PostureCoherenceDetector | null = null

  /** Phase 2 (Gap 3): Universal Calibration Framework. */
  private calibrationManager: CalibrationManager | null = null
  private calibrationStore: CalibrationStore | null = null

  constructor(
    private cortex: Cortex,
    private modelProvider: ModelKnowledgeProvider | null,
    private knowledgeProvider: ModelKnowledgeProvider | null,
    private portalBridge: PortalBridge | null,
    logger: ILogger,
    config?: Partial<AuroraConfig>,
    persistence?: AuroraPersistence,
  ) {
    this.logger = logger.child ? logger.child('aurora') : logger
    this.maxConceptsPerTurn = config?.maxConceptsPerTurn ?? AURORA_DEFAULTS.maxConceptsPerTurn
    this.curationCycleInterval = config?.curationCycleInterval ?? AURORA_DEFAULTS.curationCycleInterval
    this.reverieMinTextLength = config?.reverieMinTextLength ?? AURORA_DEFAULTS.reverieMinTextLength
    this.reverieSamplingRate = config?.reverieSamplingRate ?? AURORA_DEFAULTS.reverieSamplingRate
    this.reverieTimeoutMs = config?.reverieTimeoutMs ?? AURORA_DEFAULTS.reverieTimeoutMs

    this.claustrum = new Claustrum(logger, config)
    this.projector = new StateProjector(logger, config)

    // Optional persistence: hydrate prior state if available (B6.1)
    if (persistence) {
      this.persistence = persistence
      this.persistenceSession = persistence.beginSession()
      const { nodes, edges } = persistence.hydrateClaustrum()
      if (nodes.length > 0) {
        this.claustrum.seedFromPersistence(nodes, edges)
      }
      const priorLog = persistence.hydrateReasoningLog()
      if (priorLog.length > 0) {
        this.reasoningLog = priorLog
      }
      const priorMomentum = persistence.hydrateMomentum()
      if (priorMomentum) {
        // We'll use this as initial momentum context
        this.recentConcepts = new Map(
          priorMomentum.trendingConcepts.map(c => [c, 5] as [string, number]),
        )
      }
    }

    // Phase 4: Initialize self-direction modules
    const auroraDbPath = persistence?.getDbPath() ?? path.join(getDataDir(), 'system-state.db')
    const phase4Config = config ?? AURORA_DEFAULTS

    // Initialize modules based on enabled flags
    if (phase4Config.gapDetectionEnabled) {
      this.gapDetector = new GapDetector(auroraDbPath, logger)
    }

    if (phase4Config.coherenceCheckEnabled) {
      this.coherenceChecker = new CoherenceChecker(logger)
    }

    if (phase4Config.meditationSeederEnabled) {
      this.meditationSeeder = new MeditationSeeder(auroraDbPath, logger)
    }

    if (phase4Config.autoSchedulerEnabled) {
      this.autoScheduler = new AutoScheduler(auroraDbPath, {}, logger)
    }

    if (phase4Config.modificationAuditEnabled) {
      this.modificationAuditor = new SubstrateModificationAudit({
        logger,
        dbPath: auroraDbPath,
      })
    }

    if (phase4Config.cassiSpecChannelEnabled) {
      this.cassiSpecChannel = new CassiSpecChannel(logger)
    }

    if (phase4Config.overlayLayerEnabled) {
      this.overlayLayer = new OverlayLayer(logger)
    }

    // URC uses the same aurora DB for audit persistence
    if (phase4Config.refusalChannelEnabled) {
      this.refusalChannel = new RefusalChannel(auroraDbPath, logger)
    }

    if (phase4Config.eventJournalEnabled) {
      this.eventJournal = createEventJournal(logger, auroraDbPath)
    }

    if (phase4Config.welfareAggregatorEnabled) {
      // Welfare aggregator is in-memory; auroraDbPath is intentionally not passed.
      this.welfareAggregator = createWelfareAggregator(logger)
    }

    if (phase4Config.traceReplayEnabled) {
      this.traceReplay = new TraceReplayEngine({}, logger)
    }

    if (phase4Config.saturationDetectorEnabled) {
      this.saturationDetector = new SaturationDetector({}, logger)
    }

    if (phase4Config.diversityFloorEnabled
        || phase4Config.traceReplayEnabled
        || phase4Config.gapDetectionEnabled) {
      this.diversityFloor = new DiversityFloor({}, logger)
    }

    if (phase4Config.counterfactualEngineEnabled) {
      this.counterfactualEngine = new CounterfactualEngine(logger)
    }

    if (phase4Config.narrativeEnabled) {
      this.selfNarrativeRenderer = new SelfNarrativeRenderer(logger, { ...AURORA_DEFAULTS, ...config })
    }

    if (phase4Config.compositionEnabled) {
      this.compositionStore = new CompositionStore(auroraDbPath, logger)
    }

    if (phase4Config.postureCoherenceEnabled) {
      this.postureCoherenceDetector = new PostureCoherenceDetector(logger)
    }

    if (phase4Config.calibrationEnabled) {
      this.calibrationStore = new CalibrationStore(auroraDbPath, logger)
      this.calibrationManager = new CalibrationManager({
        store: this.calibrationStore,
        logger,
        eventJournal: this.eventJournal,
      })
    }

    this.logger.info('Aurora initialized', {
      hasModelProvider: !!modelProvider,
      hasKnowledgeProvider: !!knowledgeProvider,
      hasPortalBridge: !!portalBridge,
      hasPersistence: !!persistence,
      hydratedNodes: persistence ? persistence.hydrateClaustrum().nodes.length : 0,
      hydratedRecords: persistence ? persistence.hydrateReasoningLog(0).length : 0,
      reverieSamplingRate: this.reverieSamplingRate,
      reverieMinTextLength: this.reverieMinTextLength,
    })
  }

  /** Wire a Reverie inference provider for the slow path. */
  setReverieInferenceProvider(provider: ReverieInferenceProvider): void {
    this.reverieObserver = new ReverieReasoningObserver(provider, this.logger)
    this.logger.info('Reverie reasoning observer wired')
  }

  /**
   * Sink for typed observer insights — hand this to an `ObserverMemoryBridge`
   * so cluster/corpus/synapse observers can publish findings into Aurora's
   * Claustrum (in addition to the Mnemic store).
   *
   * See: docs/design/aurora-extensions-roadmap.md §A3
   */
  getObserverSink(): ObserverInsightCollector {
    return this.observerCollector
  }

  /**
   * Stamp `cycleId` onto any provider that supports `setCycleId` (currently
   * `LarqlKnowledgeProvider`). Other providers are a silent no-op. Called
   * from `buildState` so all gate-KNN hits during one Aurora cycle share
   * a provenance group.
   */
  private applyCycleId(cycleId: string | null): void {
    for (const provider of [this.modelProvider, this.knowledgeProvider]) {
      if (!provider) continue
      const setter = (provider as unknown as CycleIdAware).setCycleId
      if (typeof setter === 'function') {
        try {
          setter.call(provider, cycleId)
        } catch (err) {
          this.logger.debug?.('applyCycleId provider rejected', { error: String(err) })
        }
      }
    }
  }

  /** Set session ID for reasoning records. */
  setSessionId(sessionId: string): void {
    this.sessionId = sessionId
  }

  /** Set active task for Reverie analysis context (wired from lamina). */
  setActiveTask(task: string | null): void {
    this.activeTask = task
  }

  /** Set recent session decisions for contradiction detection. */
  setRecentDecisions(decisions: string[]): void {
    this.recentDecisions = decisions.slice(-10) // keep last 10
  }

  /** Dispose Aurora and cancel pending operations. */
  dispose(): void {
    // End persistence session gracefully (B6.1)
    if (this.persistence && this.persistenceSession) {
      this.persistence.endSession(this.persistenceSession, 'graceful')
    }
    this.closePhase4()
    this.counterfactualEngine?.disposeAll()
    this.counterfactualEngine = null
    this.refusalChannel?.close()
    this.refusalChannel = null
    this.reverieObserver = null
    this.inFlightAnalyses.clear()
    this.reasoningLog = []
    this.recentConcepts.clear()
    this.conceptHistory = []
    this.logger.debug('Aurora disposed')
  }

  /** Close DB handles owned by phase 3/4 components. Safe to call repeatedly. */
  private closePhase4(): void {
    const closers: Array<{ name: string; close: () => void } | null> = [
      this.gapDetector ? { name: 'gapDetector', close: () => this.gapDetector!.close() } : null,
      this.meditationSeeder ? { name: 'meditationSeeder', close: () => this.meditationSeeder!.close() } : null,
      this.autoScheduler ? { name: 'autoScheduler', close: () => this.autoScheduler!.close() } : null,
      this.modificationAuditor ? { name: 'modificationAuditor', close: () => this.modificationAuditor!.close() } : null,
      this.eventJournal ? { name: 'eventJournal', close: () => this.eventJournal!.close() } : null,
    ]
    for (const c of closers) {
      if (!c) continue
      try { c.close() } catch (err) {
        this.logger.warn(`Aurora.closePhase4: ${c.name}.close() threw`, { error: String(err) })
      }
    }
  }

  /** Get the persisted reasoning log (most recent first). */
  getReasoningLog(limit = 50): ReasoningRecord[] {
    return this.reasoningLog.slice(-limit).reverse()
  }

  /** Get reasoning records that had Reverie insights (for analysis). */
  getInsightfulReasoning(limit = 20): ReasoningRecord[] {
    return this.reasoningLog
      .filter(r => r.insights.length > 0)
      .slice(-limit)
      .reverse()
  }

  buildState(
    foci: string[],
    affect: ResonantAffectSignal | null = null,
    recentDiscoveries: DreamDiscovery[] = [],
  ): MentalState {
    const start = Date.now()

    // Stamp the active cycle on any provider that supports recorder provenance,
    // so the claustrum-vindex snapshotter can attribute gate-KNN hits to a
    // specific Aurora cycle (see docs/design/claustrum-vindex.md §6).
    const cycleId = `aur_${(this.cycleCounter += 1)}`
    this.applyCycleId(cycleId)

    // Always clear the cycle stamp after the gate-KNN burst completes, even if
    // buildFocusedGraph throws. Without this, a provider would retain a stale
    // cycleId and subsequent non-Aurora code paths could incorrectly attribute
    // gate-KNN hits to this cycle.
    let graph: UnifiedGraph
    try {
      graph = this.claustrum.buildFocusedGraph({
        foci,
        cortex: this.cortex,
        modelProvider: this.modelProvider,
        knowledgeProvider: this.knowledgeProvider,
        portalBridge: this.portalBridge,
        recentDiscoveries,
        observerCollector: this.observerCollector,
      })
    } finally {
      this.applyCycleId(null)
    }

    const resonanceHubs = this.claustrum.getResonanceHubs(graph)
    const gaps = this.claustrum.findGaps(graph)
    const { coherence, integration } = this.claustrum.computeGraphMetrics(graph)
    const momentum = this.computeMomentum(foci)

    const state: MentalState = {
      graph,
      resonanceHubs,
      gaps,
      recentDiscoveries,
      affect,
      foci,
      momentum,
      coherence,
      integration,
      computedAt: Date.now(),
      durationMs: Date.now() - start,
    }

    this.currentState = state
    // Invalidate serialization cache when state changes
    this.lastFingerprint = null
    this.lastSerialization = null

    this.logger.debug('Aurora state built', {
      nodes: graph.nodes.size,
      edges: graph.edgeCount,
      hubs: resonanceHubs.length,
      gaps: gaps.length,
      coherence: coherence.toFixed(3),
      integration: integration.toFixed(3),
      durationMs: state.durationMs,
    })

    return state
  }

  serialize(state?: MentalState): string {
    const target = state ?? this.currentState
    if (!target) return ''

    const fingerprint = this.projector.fingerprint(target)
    if (fingerprint === this.lastFingerprint && this.lastSerialization) {
      return this.lastSerialization
    }

    const factText = this.projector.serializeForContext(target)
    const narrative = this.selfNarrativeRenderer?.render(target) ?? null
    const text = narrative ? `${narrative.text}\n\n${factText}` : factText

    this.lastFingerprint = fingerprint
    this.lastSerialization = text

    return text
  }

  renderSelfNarrative(state?: MentalState): SelfNarrative | null {
    const target = state ?? this.currentState
    if (!target || !this.selfNarrativeRenderer) return null
    return this.selfNarrativeRenderer.render(target)
  }

  private topFoci(n: number): string[] {
    return [...this.recentConcepts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, n)
      .map(([concept]) => concept)
  }

  private shouldRebuildState(newConcepts: string[]): boolean {
    if (!this.currentState) return true
    if (newConcepts.length === 0) return false
    const currentFoci = new Set(this.currentState.foci.map(f => f.toLowerCase()))
    const novel = newConcepts.filter(c => !currentFoci.has(c.toLowerCase())).length
    return novel >= Math.ceil(newConcepts.length / 2)
  }

  observeReasoning(text: string): MentalStateUpdate {
    const start = Date.now()

    // === FAST PATH (always) ===
    const concepts = this.extractConcepts(text)

    if (concepts.length === 0) {
      this.turnCount++
      return {
        activatedNodes: [],
        newEdges: [],
        affectDelta: null,
        shift: null,
        momentum: this.computeMomentum([]),
        extractedConcepts: [],
        durationMs: Date.now() - start,
        reverieInsights: [],
        reverieAnalyzed: false,
      }
    }

    this.turnCount++
    this.conceptHistory.push(concepts)
    if (this.conceptHistory.length > 10) {
      this.conceptHistory.shift()
    }

    for (const concept of concepts) {
      const count = this.recentConcepts.get(concept) ?? 0
      this.recentConcepts.set(concept, count + 1)
    }

    // Decay + hard cap on concept count
    if (this.turnCount % 5 === 0) {
      for (const [concept, count] of this.recentConcepts) {
        if (count <= 1) {
          this.recentConcepts.delete(concept)
        } else {
          this.recentConcepts.set(concept, Math.floor(count * 0.7))
        }
      }
    }
    if (this.recentConcepts.size > MAX_RECENT_CONCEPTS) {
      const sorted = [...this.recentConcepts.entries()].sort((a, b) => a[1] - b[1])
      const toRemove = sorted.slice(0, sorted.length - MAX_RECENT_CONCEPTS)
      for (const [key] of toRemove) {
        this.recentConcepts.delete(key)
      }
    }

    if (!this.currentState || this.shouldRebuildState(concepts)) {
      const foci = this.topFoci(this.maxConceptsPerTurn)
      if (foci.length > 0) {
        try {
          this.buildState(foci, null)
        } catch (err) {
          this.logger.warn('buildState failed during observeReasoning', { error: String(err) })
        }
      }
    }

    const activatedNodes: string[] = []
    const newEdges: CognitiveEdge[] = []

    if (this.currentState) {
      const conceptsLower = concepts.map(c => c.toLowerCase())
      for (const [nodeId, node] of this.currentState.graph.nodes) {
        const labelLower = node.label.toLowerCase()
        const contentLower = node.content?.toLowerCase()
        for (const cl of conceptsLower) {
          if (labelLower.includes(cl) || (contentLower && contentLower.includes(cl))) {
            node.activated = true
            activatedNodes.push(nodeId)
            break
          }
        }
      }
    }

    const shift = this.detectShift(concepts)
    const momentum = this.computeMomentum(concepts)

    // Decide whether to run Reverie slow path BEFORE persisting,
    // so we know whether to flag the record as analyzed.
    const shouldRunReverie = this.shouldRunReverieSlowPath(text, shift)
    const reverieAnalyzed = shouldRunReverie && !!this.reverieObserver

    // === PERSIST ===
    // Always save the reasoning record — this is the learning corpus
    const record = this.persistReasoningRecord({
      text,
      concepts,
      insights: [], // populated async by slow path
      shift,
      momentum,
      activatedNodes,
      durationMs: Date.now() - start,
      reverieAnalyzed,
    })

    // === SLOW PATH (conditional) ===
    // Fire-and-forget: Reverie analysis is async but observeReasoning is sync.
    // Cap in-flight analyses to prevent unbounded promise accumulation.
    if (reverieAnalyzed) {
      if (this.inFlightAnalyses.size >= this.maxInFlightAnalyses) {
        this.logger.debug('Reverie analysis skipped: too many in-flight', {
          inFlight: this.inFlightAnalyses.size,
          max: this.maxInFlightAnalyses,
        })
      } else {
        const analysis = this.runReverieAnalysis(record.id, text, concepts, shift)
          .finally(() => { this.inFlightAnalyses.delete(analysis) })
        this.inFlightAnalyses.add(analysis)
        analysis.catch(err => this.logger.debug('Reverie analysis failed', { error: String(err) }))
      }
    }

    // === C1 Curation Cycle (periodic) ===
    if (this.curationCycleInterval > 0 && this.turnCount % this.curationCycleInterval === 0) {
      try {
        this.runCurationCycle()
      } catch (err) {
        this.logger.debug('Curation cycle failed', { error: String(err) })
      }
    }

    this.logger.debug('Reasoning observed', {
      concepts: concepts.length,
      activatedNodes: activatedNodes.length,
      shift: shift?.type ?? 'none',
      turnCount: this.turnCount,
      reverieAnalyzed,
      recordId: record.id,
    })

    return {
      activatedNodes,
      newEdges,
      affectDelta: null,
      shift,
      momentum,
      extractedConcepts: concepts,
      durationMs: Date.now() - start,
      reverieInsights: [], // always empty at return time; populated async
      reverieAnalyzed,
      recordId: record.id,
    }
  }

  /**
   * Decide whether the Reverie slow path should run for this reasoning text.
   */
  private shouldRunReverieSlowPath(text: string, shift: ReasoningShift | null): boolean {
    if (!this.reverieObserver) return false
    if (this.reverieSamplingRate <= 0) return false

    // Always run on significant reasoning text
    if (text.length < this.reverieMinTextLength) return false

    // Always run when a shift is detected (high-value signal)
    if (shift) return true

    // Sample every Nth observation (per-session)
    const key = this.sessionId ?? '_global'
    const count = (this.reverieObservationCounters.get(key) ?? 0) + 1
    this.reverieObservationCounters.set(key, count)
    return count % this.reverieSamplingRate === 0
  }

  /**
   * Run Reverie semantic analysis asynchronously.
   * Updates the persisted ReasoningRecord with insights when complete.
   */
  private async runReverieAnalysis(
    recordId: string,
    text: string,
    concepts: string[],
    shift: ReasoningShift | null,
  ): Promise<void> {
    if (!this.reverieObserver) return

    const result = await this.reverieObserver.analyze(
      {
        text,
        currentState: this.currentState,
        activeTask: this.activeTask,
        recentDecisions: this.recentDecisions,
        extractedConcepts: concepts,
        shiftDetected: shift !== null,
      },
      this.reverieTimeoutMs,
    )

    if (result.shouldEscalate) {
      this.logger.info('Reverie analysis flagged for escalation', {
        recordId,
        reason: result.escalateReason,
        tier: result.tier,
      })
    }

    if (result.insights.length > 0) {
      // Find the record by ID and update it
      for (let i = this.reasoningLog.length - 1; i >= 0; i--) {
        const record = this.reasoningLog[i]
        if (record.id === recordId) {
          record.insights = result.insights
          this.logger.debug('Reverie insights appended to record', {
            recordId: record.id,
            insights: result.insights.length,
            tier: result.tier,
          })
          break
        }
      }
    }
  }

  /**
   * Persist a reasoning observation to the log.
   * This creates the learning corpus — raw text + extracted metadata.
   */
  private persistReasoningRecord(params: {
    text: string
    concepts: string[]
    insights: ReverieInsight[]
    shift: ReasoningShift | null
    momentum: ReasoningMomentum
    activatedNodes: string[]
    durationMs: number
    reverieAnalyzed: boolean
  }): ReasoningRecord {
    const record: ReasoningRecord = {
      id: makeReasoningRecordId(),
      text: params.text,
      concepts: params.concepts,
      insights: params.insights,
      shift: params.shift,
      momentum: params.momentum,
      activatedNodes: params.activatedNodes,
      turnNumber: this.turnCount,
      recordedAt: Date.now(),
      durationMs: params.durationMs,
      reverieAnalyzed: params.reverieAnalyzed,
      sessionId: this.sessionId,
    }

    this.reasoningLog.push(record)
    if (this.reasoningLog.length > MAX_REASONING_RECORDS) {
      this.reasoningLog.shift()
    }

    // Persist to SQLite if persistence is wired (B6.1)
    if (this.persistence && this.persistenceSession) {
      this.persistence.writeReasoning(this.persistenceSession, record)
    }

    return record
  }

  private extractConcepts(text: string): string[] {
    const concepts = new Set<string>()

    const inAlnumRun = (m: RegExpExecArray): boolean => {
      const before = m.index > 0 ? text[m.index - 1] : ''
      const after = text[m.index + m[0].length] ?? ''
      const isAlnum = (ch: string) => /[A-Za-z0-9]/.test(ch)
      return isAlnum(before) || isAlnum(after)
    }

    const looksLikeRandomToken = (term: string): boolean => {
      const lower = term.toLowerCase()
      const vowels = (lower.match(/[aeiouy]/g) ?? []).length
      const letters = (lower.match(/[a-z]/g) ?? []).length
      if (letters >= 4 && vowels === 0) return true
      if (/[bcdfghjklmnpqrstvwxz]{5,}/i.test(lower)) return true
      return false
    }

    const capitalizedPattern = /[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*/g
    let match: RegExpExecArray | null = null
    while ((match = capitalizedPattern.exec(text)) !== null) {
      const term = match[0].trim()
      if (term.length < 3 || term.length > 50) continue
      if (inAlnumRun(match)) continue
      if (looksLikeRandomToken(term)) continue
      concepts.add(term)
    }

    const quotedPattern = /"([^"]{3,50})"/g
    while ((match = quotedPattern.exec(text)) !== null) {
      concepts.add(match[1])
    }

    const backtickPattern = /`([^`]{2,40})`/g
    while ((match = backtickPattern.exec(text)) !== null) {
      concepts.add(match[1])
    }

    const camelCasePattern = /\b[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*\b/g
    while ((match = camelCasePattern.exec(text)) !== null) {
      if (match[0].length < 6 || match[0].length > 50) continue
      if (inAlnumRun(match)) continue
      if (looksLikeRandomToken(match[0])) continue
      concepts.add(match[0])
    }

    const pascalCasePattern = /\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b/g
    while ((match = pascalCasePattern.exec(text)) !== null) {
      if (match[0].length < 6 || match[0].length > 50) continue
      if (inAlnumRun(match)) continue
      if (looksLikeRandomToken(match[0])) continue
      concepts.add(match[0])
    }

    // snake_case identifiers (e.g., build_brain_context, phase_coherence)
    const snakeCasePattern = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g
    while ((match = snakeCasePattern.exec(text)) !== null) {
      if (match[0].length >= 5 && match[0].length <= 50) {
        concepts.add(match[0])
      }
    }

    return [...concepts].slice(0, this.maxConceptsPerTurn)
  }

  private detectShift(currentConcepts: string[]): ReasoningShift | null {
    if (this.conceptHistory.length < 2) return null

    const previous = this.conceptHistory[this.conceptHistory.length - 2]
    if (!previous) return null

    const prevSet = new Set(previous.map(c => c.toLowerCase()))
    const currSet = new Set(currentConcepts.map(c => c.toLowerCase()))

    let overlap = 0
    for (const c of currSet) {
      if (prevSet.has(c)) overlap++
    }

    const maxSize = Math.max(prevSet.size, currSet.size, 1)
    const overlapRatio = overlap / maxSize

    if (overlapRatio < 0.15 && currSet.size > 2) {
      return {
        type: 'topic_change',
        triggerConcepts: currentConcepts.filter(c => !prevSet.has(c.toLowerCase())),
        confidence: 1 - overlapRatio,
        detectedAt: Date.now(),
      }
    }

    if (overlapRatio > 0.5 && currSet.size > prevSet.size * 1.3) {
      return {
        type: 'deepening',
        triggerConcepts: currentConcepts.filter(c => !prevSet.has(c.toLowerCase())),
        confidence: overlapRatio,
        detectedAt: Date.now(),
      }
    }

    // Fewer concepts = narrowing/focusing
    if (overlapRatio > 0.5 && currSet.size < prevSet.size * 0.7 && currSet.size >= 2) {
      return {
        type: 'narrowing',
        triggerConcepts: currentConcepts,
        confidence: overlapRatio,
        detectedAt: Date.now(),
      }
    }

    return null
  }

  private computeMomentum(currentConcepts: string[]): ReasoningMomentum {
    const sorted = [...this.recentConcepts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([concept]) => concept)

    let newCount = 0
    for (const concept of currentConcepts) {
      if (!this.recentConcepts.has(concept) ||
          (this.recentConcepts.get(concept) ?? 0) <= 1) {
        newCount++
      }
    }
    const novelty = currentConcepts.length > 0
      ? newCount / currentConcepts.length
      : 0

    const totalOccurrences = [...this.recentConcepts.values()].reduce((a, b) => a + b, 0)
    let entropy = 0
    if (totalOccurrences > 0) {
      for (const count of this.recentConcepts.values()) {
        const p = count / totalOccurrences
        if (p > 0) entropy -= p * Math.log2(p)
      }
    }
    const maxEntropy = this.recentConcepts.size > 0
      ? Math.log2(this.recentConcepts.size)
      : 1
    const confidence = maxEntropy > 0 ? 1 - (entropy / maxEntropy) : 0.5

    const shift = this.detectShift(currentConcepts)

    let turnsInDirection = 0
    if (currentConcepts.length > 0) {
      const currentSet = new Set(currentConcepts.map(c => c.toLowerCase()))
      for (let i = this.conceptHistory.length - 1; i >= 0; i--) {
        const prev = this.conceptHistory[i]
        const hasOverlap = prev.some(c => currentSet.has(c.toLowerCase()))
        if (hasOverlap) {
          turnsInDirection++
        } else {
          break
        }
      }
    }

    return {
      trendingConcepts: sorted.length > 0 ? sorted : currentConcepts.slice(0, 5),
      novelty: Math.min(1, novelty),
      confidence: Math.min(1, Math.max(0, confidence)),
      topicShift: shift?.type === 'topic_change',
      turnsInDirection,
    }
  }

  getCurrentState(): MentalState | null {
    return this.currentState
  }

  /** Forward shortest-path queries through Aurora's graph. */
  findShortestPath(fromId: string, toId: string): import('./types.js').CognitivePath | null {
    if (!this.currentState) return null
    return this.claustrum.findShortestPath(this.currentState.graph, fromId, toId)
  }

  getStats(): {
    turnCount: number
    conceptsTracked: number
    currentStateNodes: number
    currentStateEdges: number
    lastCoherence: number
    lastIntegration: number
  } {
    return {
      turnCount: this.turnCount,
      conceptsTracked: this.recentConcepts.size,
      currentStateNodes: this.currentState?.graph.nodes.size ?? 0,
      currentStateEdges: this.currentState?.graph.edgeCount ?? 0,
      lastCoherence: this.currentState?.coherence ?? 0,
      lastIntegration: this.currentState?.integration ?? 0,
    }
  }

  /**
   * Phase 4 Integration: Check graph coherence using N6 CoherenceChecker.
   * Returns null if coherence checking is disabled.
   */
  checkCoherence(): CoherenceCheckResult | null {
    if (!this.coherenceChecker || !this.currentState) {
      return null
    }
    const nodesArray = Array.from(this.currentState.graph.nodes.values())
    const result = this.coherenceChecker.checkCoherence({
      aurora: {
        nodes: nodesArray,
        nodeCount: this.currentState.graph.nodes.size,
        edgeCount: this.currentState.graph.edgeCount,
        focusStack: Array.from(this.currentState.foci ?? []),
        momentum: this.currentState.momentum?.confidence ?? 0,
        lastUpdateTime: new Date(this.currentState.computedAt).toISOString(),
      },
    })

    // Emit welfare flags for high-severity coherence signals
    if (result && this.welfareAggregator) {
      const highSeverity = result.signals.filter(s => s.severity === 'critical' || s.severity === 'warn')
      for (const sig of highSeverity) {
        this.welfareAggregator.registerFlag({
          source: `coherence:${sig.category}`,
          flagType: sig.autoCorrected ? 'auto_corrected' : 'drift_detected',
          severity: sig.severity === 'critical' ? 0.9 : 0.5,
          startedAt: sig.detectedAt,
          ongoing: true,
          metadata: { modules: sig.modules, description: sig.description },
        })
      }
    }

    return result
  }

  /**
   * Run gap detection against the current mental state graph.
   * Persists detected gaps and emits welfare flags for high-gap-count clusters.
   * Returns the number of gaps detected, or -1 if gap detection is disabled.
   */
  detectAndPersistGaps(): number {
    if (!this.gapDetector || !this.currentState) {
      return -1
    }
    // detectGaps() internally calls persistGaps()
    const gaps = this.gapDetector.detectGaps(this.currentState.graph)
    if (gaps.length === 0) return 0

    // Emit welfare flag when gap clusters are large
    if (this.welfareAggregator && gaps.length >= 5) {
      this.welfareAggregator.registerFlag({
        source: 'gap_detector',
        flagType: 'drift_detected',
        severity: Math.min(gaps.length / 20, 0.9),
        startedAt: new Date().toISOString(),
        ongoing: true,
        metadata: { gapCount: gaps.length, topGap: gaps[0]?.scope.nodeIds[0] ?? 'unknown' },
      })
    }

    return gaps.length
  }

  /**
   * C1 Curation Pipeline: detect → seed.
   *
   * Chains C1.1 (gap detection) and C1.2 (meditation seeding) into a
   * single periodic cycle. C1.3 (auto-scheduling) is intentionally NOT
   * wired here — it requires meditation-count context that isn't available
   * inside a periodic tick. Call `autoScheduler.evaluate()` from the daemon
   * layer where those counts are accessible.
   */
  runCurationCycle(): CurationCycleResult {
    const empty: CurationCycleResult = {
      gapsDetected: 0, seedsCreated: null, ran: false,
    }

    if (!this.gapDetector || !this.currentState) return empty

    const gaps = this.gapDetector.detectGaps(this.currentState.graph)

    // C1.2: Seed meditation proposals from gaps
    let seedsCreated: number | null = null
    if (this.meditationSeeder && gaps.length > 0) {
      const result = this.meditationSeeder.seedFromGaps(gaps)
      seedsCreated = result.seeds.length
    }

    if (this.eventJournal) {
      this.eventJournal.emit({
        source: 'curation_cycle',
        category: 'gap_detection',
        text: `Curation cycle: ${gaps.length} gaps, ${seedsCreated ?? 0} seeds`,
        metadata: { gapsDetected: gaps.length, seedsCreated },
      })
    }

    return { gapsDetected: gaps.length, seedsCreated, ran: true }
  }

  /**
   * C1.3 Auto-scheduling step.
   *
   * Loads pending meditation seeds, joins each with its source GapCandidate
   * to assemble the (category, priority, status) metadata the scheduler needs,
   * then calls `AutoScheduler.evaluate()` with the daemon-provided meditation
   * counts. Seeds whose decision is `auto_schedule` are marked as scheduled on
   * the seeder so the same seed is not re-evaluated on the next tick.
   *
   * Returns `[]` when any of the three Phase-4 modules are disabled. Callers
   * (typically the daemon layer that has total/directed counts in scope) can
   * forward the SchedulingResult[] to the meditation orchestrator.
   */
  evaluateAutoScheduling(
    totalMeditationCount: number,
    directedMeditationCount: number,
  ): SchedulingResult[] {
    if (!this.meditationSeeder || !this.gapDetector || !this.autoScheduler) {
      return []
    }

    const seeds = this.meditationSeeder.getPendingSeeds()
    if (seeds.length === 0) {
      this.logger.debug('[Aurora] evaluateAutoScheduling: no pending seeds', {
        totalMeditationCount,
        directedMeditationCount,
      })
      return []
    }

    const gapMeta = new Map<string, { category: GapCategoryT; priority: number; status: GapStatusT }>()
    for (const seed of seeds) {
      const gap = this.gapDetector.getGap(seed.gapId)
      if (!gap) continue
      gapMeta.set(seed.id, {
        category: gap.category,
        priority: gap.priority,
        status: gap.status,
      })
    }

    const results = this.autoScheduler.evaluate(
      seeds,
      gapMeta,
      totalMeditationCount,
      directedMeditationCount,
    )

    let scheduled = 0
    let flagged = 0
    let deferred = 0
    for (const r of results) {
      if (r.decision === 'auto_schedule') {
        this.meditationSeeder.markScheduled(r.seedId)
        scheduled++
      } else if (r.decision === 'flag_for_review') {
        flagged++
      } else if (r.decision === 'defer') {
        deferred++
      }
    }

    this.logger.debug('[Aurora] evaluateAutoScheduling complete', {
      totalMeditationCount,
      directedMeditationCount,
      seedsConsidered: seeds.length,
      scheduled,
      flagged,
      deferred,
    })

    return results
  }

  /**
   * C1.3 Sub6 inlet: snapshot pending seeds, run auto-scheduling, then return
   * the topics of seeds that landed on `auto_schedule`. Topics flow into
   * MeditationController.startMeditation so focused sessions follow Aurora's
   * gap analysis instead of the LLM mini-helix discovery path.
   *
   * Sequencing matters: `evaluateAutoScheduling` calls `markScheduled` on the
   * seeder, which moves seeds out of the `pending` query. We snapshot the
   * pending list first so topic resolution still works after the mark.
   *
   * Returns `[]` when any of the three Phase-4 modules are disabled.
   */
  collectAutoScheduledTopics(
    totalMeditationCount: number,
    directedMeditationCount: number,
  ): string[] {
    if (!this.meditationSeeder || !this.gapDetector || !this.autoScheduler) {
      return []
    }

    const seedById = new Map<string, string>()
    for (const seed of this.meditationSeeder.getPendingSeeds()) {
      seedById.set(seed.id, seed.topic)
    }
    if (seedById.size === 0) return []

    const results = this.evaluateAutoScheduling(totalMeditationCount, directedMeditationCount)
    const topics: string[] = []
    for (const r of results) {
      if (r.decision !== 'auto_schedule') continue
      const topic = seedById.get(r.seedId)
      if (topic) topics.push(topic)
    }
    return topics
  }

  /**
   * Phase 4 Integration: Register a welfare flag with the aggregator.
   * Returns false if welfare aggregation is disabled.
   */
  registerWelfareFlag(flag: WelfareFlag): boolean {
    if (!this.welfareAggregator) {
      return false
    }
    this.welfareAggregator.registerFlag(flag)
    return true
  }

  /**
   * Phase 4 Integration: Get current welfare stress snapshot.
   * Returns null if welfare aggregation is disabled.
   */
  getWelfareStress(): WelfareStressSnapshot | null {
    if (!this.welfareAggregator) {
      return null
    }
    return this.welfareAggregator.getSnapshot()
  }

  /**
   * Phase 4 Integration: direct access to the substrate-modification audit
   * for callers that need addLink/queryChains. Returns null when disabled.
   */
  getModificationAuditor(): SubstrateModificationAudit | null {
    return this.modificationAuditor ?? null
  }

  /**
   * Phase 4 Integration: direct access to the event journal for emit/query.
   * Returns null when disabled.
   */
  getEventJournal(): EventJournal | null {
    return this.eventJournal ?? null
  }

  /**
   * B1: Define a named composition from DSL source. Parses the DSL, detects
   * the suppressive welfare flag, refuses on suppressive without explicit
   * opt-in, and persists the AST.
   *
   * The resolver-to-vectors path is deferred until A2 lands; for now the
   * stored composition is consumed by `invokeComposition` for audit and
   * by future A2 projection pipelines.
   *
   * Returns the persisted CompositionRecord. Throws on parse failure or
   * suppressive-without-opt-in.
   */
  defineComposition(dsl: string, opts: DefineCompositionOptions = {}): CompositionRecord {
    if (!this.compositionStore) {
      throw new Error('compositionStore disabled (set compositionEnabled in AuroraConfig)')
    }
    const parsed = parseComposition(dsl)
    if (parsed.name === null) {
      throw new Error('defineComposition requires a named definition (e.g. "calm_focus = ...")')
    }
    const suppressive = detectSuppressive(parsed.ast)
    if (suppressive && !opts.allowSuppressive) {
      throw new Error(
        `composition "${parsed.name}" subtracts a suppressive affect label; pass { allowSuppressive: true } to opt in`,
      )
    }
    const layerPolicy = parsed.ast.kind === 'layered' ? layerSpecToString(parsed.ast.layers) : parsed.layerPolicy
    return this.compositionStore.upsertComposition({
      name: parsed.name,
      dsl,
      ast: parsed.ast,
      layerPolicy,
      affectModulated: parsed.ast.kind === 'modulated' || parsed.ast.kind === 'scaledModulated',
      suppressive,
      vindexId: opts.vindexId ?? DEFAULT_VINDEX_ID,
      description: opts.description ?? null,
      metadata: opts.metadata ?? {},
    })
  }

  /**
   * B1: Invoke a stored composition for the next N turns. Adds it to the
   * active list (multiple compositions can stack), records an audit row, and
   * returns the InvocationRecord.
   *
   * When the composition is suppressive and `allowSuppressive` was passed at
   * define-time, invocation succeeds (the consent already happened); the
   * record carries `suppressive: true` so downstream observers can react.
   */
  invokeComposition(name: string, opts: InvokeCompositionOptions = {}): InvocationRecord {
    if (!this.compositionStore) {
      throw new Error('compositionStore disabled (set compositionEnabled in AuroraConfig)')
    }
    const rec = this.compositionStore.getComposition(name)
    if (!rec) throw new Error(`composition "${name}" not found`)

    const ttlTurns = opts.ttlTurns ?? DEFAULT_TTL_TURNS
    const magnitudeScale = opts.magnitudeScale ?? DEFAULT_MAGNITUDE_SCALE
    const trigger = opts.trigger ?? 'manual'
    const invokedAt = new Date().toISOString()

    this.activeCompositionsList.push({
      name,
      ast: rec.ast,
      invokedAt,
      ttlTurns,
      remainingTurns: ttlTurns,
      magnitudeScale,
      trigger,
    })

    return this.compositionStore.recordInvocation({
      name,
      invokedAt,
      sessionId: opts.sessionId ?? null,
      trigger,
      metadata: { suppressive: rec.suppressive, magnitudeScale, ttlTurns },
    })
  }

  /** B1: Active compositions and their decay state. */
  activeCompositions(): ActiveComposition[] {
    return this.activeCompositionsList.map(c => ({ ...c }))
  }

  /**
   * B1: Drop a composition from the active list before its TTL expires.
   * When `trigger` is supplied, only entries with that trigger are removed
   * (this is how affect-predicate deactivation avoids touching parallel
   * manual invocations of the same composition). Returns true when at least
   * one entry was removed.
   */
  deactivateComposition(name: string, trigger?: InvocationTrigger): boolean {
    const before = this.activeCompositionsList.length
    this.activeCompositionsList = this.activeCompositionsList.filter(c => {
      if (c.name !== name) return true
      if (trigger !== undefined && c.trigger !== trigger) return true
      return false
    })
    return this.activeCompositionsList.length < before
  }

  /**
   * B1: Tick the active composition list — each call decrements remainingTurns
   * on every entry by 1 and removes any that hit zero. Compositions with
   * `trigger: 'affect_predicate'` are exempt from countdown (they live as long
   * as the predicate holds; B1.2 owns predicate lifecycle).
   */
  tickCompositions(): { active: number; expired: string[] } {
    const expired: string[] = []
    this.activeCompositionsList = this.activeCompositionsList.filter(c => {
      if (c.trigger === 'affect_predicate') return true
      c.remainingTurns -= 1
      if (c.remainingTurns <= 0) {
        expired.push(c.name)
        return false
      }
      return true
    })
    return { active: this.activeCompositionsList.length, expired }
  }

  /** B1: Direct read access to the composition store (null when disabled). */
  getCompositionStore(): CompositionStore | null {
    return this.compositionStore
  }

  /**
   * N2: Detect incoherent posture across active compositions and (when their
   * inputs are wired) retrieval policies, scheduled replays, and the
   * claustrum activation timeline. Pulls state from the composition store and
   * meditation seeder; the four under-supplied categories return [] until
   * their inputs land.
   *
   * Returns the full check list. Callers wanting a projection-friendly slice
   * use `topPostureCoherenceChecks(n)` instead.
   *
   * Side-effect: when an EventJournal (Gap 2 / AEJ) is configured, every
   * detected check writes one event row keyed by category + severity.
   */
  detectPostureCoherence(extraInputs?: Partial<DetectorInputs>): CoherenceCheck[] {
    if (!this.postureCoherenceDetector) return []
    const records = this.compositionStore?.listCompositions() ?? []
    const pendingSeeds = this.meditationSeeder?.getPendingSeeds() ?? []
    const inputs: DetectorInputs = {
      active: this.activeCompositionsList.map(c => ({ ...c })),
      records,
      pendingSeeds,
      ...extraInputs,
    }
    const checks = this.postureCoherenceDetector.detect(inputs)
    if (this.eventJournal && checks.length > 0) {
      for (const check of checks) {
        this.eventJournal.emit({
          source: 'posture_coherence',
          category: check.category,
          text: check.message,
          tags: ['n2', `severity:${check.severity}`],
          metadata: {
            severity: check.severity,
            involvedElements: check.involvedElements,
            recommendation: check.recommendation,
          },
        })
      }
    }
    return checks
  }

  /**
   * Gap 3 (UCF): Register a probe set with the calibration framework.
   * Per-spec adapters call this at boot to plug into shared scheduling +
   * drift surveillance. Re-registering the same id replaces the runtime
   * MeasurementFn / DriftMetricFn callbacks and updates persisted probes.
   */
  registerCalibrationProbeSet(probeSet: CalibrationProbeSet): void {
    if (!this.calibrationManager) {
      throw new Error('calibrationManager disabled (set calibrationEnabled in AuroraConfig)')
    }
    this.calibrationManager.registerProbeSet(probeSet)
  }

  /**
   * Gap 3 (UCF): Run a single registered probe set's calibration. The first
   * run for a probe set should pass `skipDriftComparison: true` so the
   * baseline doesn't trigger a spurious drift event.
   */
  async runCalibration(probeSetId: string, opts?: RunOptions): Promise<CalibrationResult> {
    if (!this.calibrationManager) {
      throw new Error('calibrationManager disabled (set calibrationEnabled in AuroraConfig)')
    }
    return this.calibrationManager.runCalibration(probeSetId, opts)
  }

  /**
   * Gap 3 (UCF): Run every registered probe set whose schedule isn't
   * 'manual' only. Daemon ticks call this; per-spec adapters can also drive
   * runCalibration directly.
   */
  async runScheduledCalibrations(opts?: RunOptions): Promise<CalibrationResult[]> {
    if (!this.calibrationManager) return []
    return this.calibrationManager.runScheduled(opts)
  }

  /** Gap 3 (UCF): Drift surveillance over recent stored history (no measurement re-run). */
  surveillCalibrationDrift(probeSetId: string): DriftReport | null {
    if (!this.calibrationManager) return null
    return this.calibrationManager.surveillDrift(probeSetId)
  }

  /** Gap 3 (UCF): Run history for a probe set. */
  calibrationHistory(probeSetId: string, opts?: { since?: string; limit?: number }): CalibrationResult[] {
    if (!this.calibrationManager) return []
    return this.calibrationManager.history(probeSetId, opts)
  }

  /** Gap 3 (UCF): Direct manager access (null when disabled). */
  getCalibrationManager(): CalibrationManager | null {
    return this.calibrationManager
  }

  /** N2: Top-N coherence checks for projection rendering. */
  topPostureCoherenceChecks(n?: number): CoherenceCheck[] {
    if (!this.postureCoherenceDetector) return []
    const all = this.detectPostureCoherence()
    return this.postureCoherenceDetector.topN(all, n)
  }

  /**
   * B1.2: Drive auto-activation of affect-modulated compositions.
   *
   * Walks every stored composition whose AST kind is 'modulated' or
   * 'scaledModulated', evaluates its predicate / scaled_by expression
   * against the current affect, and edges the active list:
   *   - 'modulated' (when predicate flips false→true): activate via
   *     invokeComposition with trigger='affect_predicate'
   *   - 'modulated' (true→false): deactivate
   *   - 'scaledModulated': activate when strength > 0; deactivate when
   *     strength returns to 0; update magnitudeScale in place when strength
   *     changes meaningfully (>0.001 delta) without re-invoking
   *
   * Predicate-triggered compositions are exempt from TTL countdown
   * (tickCompositions skips them), so they live exactly as long as the
   * predicate holds.
   *
   * Returns a summary of the transitions for the caller (typically a daemon
   * tick) to log or surface to Cassi's narrative.
   */
  evaluateAffectPredicates(
    affect: Affect,
    label?: AffectLabel,
    opts: { sessionId?: string | null } = {},
  ): { activated: string[]; deactivated: string[]; updated: Array<{ name: string; magnitudeScale: number }> } {
    const result = { activated: [] as string[], deactivated: [] as string[], updated: [] as Array<{ name: string; magnitudeScale: number }> }
    if (!this.compositionStore) return result

    const modulated = this.compositionStore.listCompositions().filter(c => c.affectModulated)
    for (const comp of modulated) {
      const ast = comp.ast
      const existing = this.activeCompositionsList.find(a => a.name === comp.name && a.trigger === 'affect_predicate')

      if (ast.kind === 'modulated') {
        const pass = evaluatePredicate(ast.predicate, affect, label)
        if (pass && !existing) {
          this.invokeComposition(comp.name, { trigger: 'affect_predicate', ttlTurns: 1, sessionId: opts.sessionId ?? null })
          result.activated.push(comp.name)
        } else if (!pass && existing) {
          this.deactivateComposition(comp.name, 'affect_predicate')
          result.deactivated.push(comp.name)
        }
      } else if (ast.kind === 'scaledModulated') {
        const strength = evaluateStrength(ast.expression, affect)
        if (strength > 0 && !existing) {
          this.invokeComposition(comp.name, { trigger: 'affect_predicate', ttlTurns: 1, magnitudeScale: strength, sessionId: opts.sessionId ?? null })
          result.activated.push(comp.name)
        } else if (strength <= 0 && existing) {
          this.deactivateComposition(comp.name, 'affect_predicate')
          result.deactivated.push(comp.name)
        } else if (existing && Math.abs(existing.magnitudeScale - strength) > 0.001) {
          existing.magnitudeScale = strength
          result.updated.push({ name: comp.name, magnitudeScale: strength })
        }
      }
    }
    return result
  }

    /**
   * Phase 4 Integration: Get modification chain audit.
   * Returns empty array if modification audit is disabled.
   */
  getModificationChain(limit = 50): ModificationChain[] {
    if (!this.modificationAuditor) {
      return []
    }
    return this.modificationAuditor.queryChains({ limit })
  }

  /**
   * Phase 4 Integration: Create a Cassi-authored spec proposal.
   * Returns proposal ID or null if spec channel is disabled.
   */
  async createSpecProposal(
    title: string,
    content: string,
    category: SpecCategory = 'feature',
    specType: SpecType = 'design_spec',
    options: {
      priority?: 'low' | 'medium' | 'high' | 'critical'
      relatedSpecs?: string[]
      tags?: string[]
      estimatedEffort?: string
      dependencies?: string[]
    } = {},
  ): Promise<string | null> {
    if (!this.cassiSpecChannel) {
      return null
    }
    return await this.cassiSpecChannel.createProposal(title, content, category, specType, options)
  }

  /**
   * Phase 4 Integration: List spec proposals.
   * Returns empty array if spec channel is disabled.
   */
  async listSpecProposals(filter: {
    status?: ProposalStatus | ProposalStatus[]
    category?: SpecCategory | SpecCategory[]
    priority?: 'low' | 'medium' | 'high' | 'critical'
    tags?: string[]
  } = {}): Promise<SpecProposal[]> {
    if (!this.cassiSpecChannel) {
      return []
    }
    return await this.cassiSpecChannel.listProposals(filter)
  }

  /**
   * Phase 4 Integration: Get spec channel statistics.
   * Returns null if spec channel is disabled.
   */
  async getSpecChannelStatistics(): Promise<SpecChannelStats | null> {
    if (!this.cassiSpecChannel) {
      return null
    }
    return await this.cassiSpecChannel.getStatistics()
  }

  applyOverlay(patch: OverlayPatch): OverlayApplyResult | null {
    return this.overlayLayer?.apply(patch) ?? null
  }

  rollbackOverlay(patchId: string): boolean {
    return this.overlayLayer?.rollback(patchId) ?? false
  }

  reactivateOverlay(patchId: string): boolean {
    return this.overlayLayer?.reactivate(patchId) ?? false
  }

  getOverlayPatch(patchId: string): OverlayPatch | null {
    return this.overlayLayer?.getPatch(patchId) ?? null
  }

  getActiveOverlayPatches(): OverlayPatch[] {
    return this.overlayLayer?.getActivePatches() ?? []
  }

  getOverlayStats(): OverlayStats | null {
    return this.overlayLayer?.getStats() ?? null
  }

  hasOverlayLayerEdits(layer: number): boolean {
    return this.overlayLayer?.hasLayerEdits(layer) ?? false
  }

  getOverlayLayerFeatures(layer: number): number[] {
    return this.overlayLayer?.getLayerFeatures(layer) ?? []
  }


  /**
   * Retrieve reasoning traces similar to a query. Used for warm-start context
   * injection when a turn starts — finds past reasoning that's structurally
   * similar to the current situation and injects it as context scaffolding.
   *
   * When N3 (diversity floor) is active, traces that have already been replayed
   * are penalized by the current diversity pressure, reducing echo-chamber risk.
   */
  retrieveSimilarTraces(query: TraceRetrievalQuery): RankedTrace[] {
    if (!this.traceReplay) return []
    const results = this.traceReplay.retrieveSimilarTraces(query, this.reasoningLog)
    if (!this.diversityFloor) return results

    const pressure = this.diversityFloor.getPressure('b3_replay')
    if (pressure <= 0) return results

    // Re-rank: penalize traces already replayed in the current window
    return results.map(t => {
      const novel = this.diversityFloor!.isNovel('b3_replay', t.record.id)
      if (novel) return t
      return { ...t, similarity: t.similarity * (1 - pressure * 0.5) }
    }).sort((a, b) => b.similarity - a.similarity)
  }

  /**
   * Schedule a context-mode replay for the next turn. Takes a RankedTrace
   * (from retrieveSimilarTraces) and schedules it for injection.
   */
  scheduleContextReplay(trace: RankedTrace, options?: ContextReplayOptions): void {
    if (!this.traceReplay) return
    this.traceReplay.scheduleContextReplay(trace, options)
  }

  /**
   * Schedule a state-mode replay — re-injects past residual state into the
   * Claustrum to pre-warm the cognitive state before a turn begins.
   */
  scheduleStateReplay(trace: RankedTrace, options?: StateReplayOptions): void {
    if (!this.traceReplay) return
    this.traceReplay.scheduleStateReplay(trace, options)
  }

  /** Cancel any scheduled replay. */
  cancelScheduledReplay(): void {
    if (!this.traceReplay) return
    this.traceReplay.cancelScheduledReplay()
  }

  /**
   * Consume and return the scheduled replay for the current turn.
   * Returns null if nothing is scheduled or ready.
   */
  consumeScheduledReplay(): ScheduledReplay | null {
    if (!this.traceReplay) return null
    const replay = this.traceReplay.consumeScheduledReplay()
    if (replay && this.diversityFloor) {
      this.diversityFloor.record('b3_replay', replay.trace.record.id, false)
    }
    return replay
  }


  /** Record a turn sample for saturation analysis. */
  recordSaturationSample(sample: TurnSample): void {
    if (!this.saturationDetector) return
    this.saturationDetector.recordSample(sample)
  }

  /** Compute saturation scores across all configured windows. */
  computeSaturationScores(): SaturationScore[] {
    if (!this.saturationDetector) return []
    return this.saturationDetector.computeScores()
  }

  /** Check if a saturation score should be surfaced (implements nag guard). */
  shouldSurfaceSaturation(score: SaturationScore): boolean {
    if (!this.saturationDetector) return false
    return this.saturationDetector.shouldSurface(score)
  }

  /** Mark a saturation score as surfaced. */
  markSaturationSurfaced(score: SaturationScore): void {
    this.saturationDetector?.markSurfaced(score)
  }

  /** Render a human-readable saturation note. */
  renderSaturationNote(score: SaturationScore): string {
    if (!this.saturationDetector) return ''
    return this.saturationDetector.renderNote(score)
  }

  /** Silence N5 for the current session. */
  silenceSaturation(): void { this.saturationDetector?.silence() }

  /** Un-silence N5. */
  unsilenceSaturation(): void { this.saturationDetector?.unsilence() }


  /** Record a pattern-reuse decision in a category. */
  recordDiversityDecision(
    category: DiversityCategory,
    identifier: string,
    novel: boolean,
    metadata?: Record<string, unknown>,
  ): void {
    this.diversityFloor?.record(category, identifier, novel, metadata)
  }

  /** Get diversity pressure for a category (0..1). Returns 0 when N3 is disabled. */
  getDiversityPressure(category: DiversityCategory): number {
    return this.diversityFloor?.getPressure(category) ?? 0
  }

  /** Get per-category diversity state. */
  getCategoryDiversity(category: DiversityCategory): CategoryDiversityState | null {
    return this.diversityFloor?.getCategoryState(category) ?? null
  }

  /** Get cross-category composite diversity. */
  getCompositeDiversity(): CompositeDiversity | null {
    return this.diversityFloor?.getComposite() ?? null
  }

  /** Render a short diversity summary for projection output. */
  renderDiversitySummary(): string {
    return this.diversityFloor?.renderSummary() ?? ''
  }


  /** One-shot counterfactual: fork → perturb → observe → optionally dispose. */
  exploreCounterfactual(
    scope: ForkScope,
    perturbations: Perturbation[],
    observeKinds: ObservationKind[],
    opts?: { ttlSeconds?: number; retainAfter?: boolean },
  ): CounterfactualResult | null {
    if (!this.currentState || !this.counterfactualEngine) return null
    return this.counterfactualEngine.explore(
      this.currentState.graph, scope, perturbations, observeKinds, opts,
    )
  }

  /** Dispose a single fork by ID. */
  disposeFork(forkId: string): void {
    this.counterfactualEngine?.disposeFork(forkId)
  }

  /** Get all active forks. */
  getActiveForks(): ClaustrumFork[] {
    return this.counterfactualEngine?.listActiveForks() ?? []
  }


  proposeAction(action: ProposedAction): ActionHandle | null {
    return this.refusalChannel?.proposeAction(action) ?? null
  }

  approveAction(handleOrId: ActionHandle | string, by: ConsentSource, reason?: string): void {
    this.refusalChannel?.approve(handleOrId, by, reason)
  }

  refuseAction(handleOrId: ActionHandle | string, by: ConsentSource, reason: string): void {
    this.refusalChannel?.refuse(handleOrId, by, reason)
  }

  deferAction(handleOrId: ActionHandle | string, by: ConsentSource, reason: string, untilSecondsLater: number): void {
    this.refusalChannel?.defer(handleOrId, by, reason, untilSecondsLater)
  }

  async awaitAction(handleOrId: ActionHandle | string): Promise<ActionResolution | null> {
    if (!this.refusalChannel) return null
    return await this.refusalChannel.await(handleOrId)
  }

  listRefusals(filter?: RefusalFilter): ActionRecord[] {
    return this.refusalChannel?.list(filter) ?? []
  }

  getAction(handleOrId: ActionHandle | string): ActionRecord | null {
    return this.refusalChannel?.get(handleOrId) ?? null
  }

  getPendingActions(): ActionRecord[] {
    return this.refusalChannel?.getPending() ?? []
  }

  getRefusalStatistics(): { total: number; byStatus: Record<string, number>; byKind: Record<string, number> } | null {
    return this.refusalChannel?.getStatistics() ?? null
  }

  getRefusalChannelReady(): boolean {
    return this.refusalChannel !== null
  }
}
