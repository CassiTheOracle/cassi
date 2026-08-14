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
import type { ILogger } from '@cassicore/foundation'
import type { Cortex } from '@cassicore/mnemic-field'
import { getDataDir } from '@cassicore/foundation'
import type { PortalBridge } from './vendor/core/intelligence/memory-bridge/portal-bridge.js'
import type { ResonantAffectSignal } from './vendor/core/intelligence/memory-bridge/resonant-affect.js'
import type { DreamDiscovery } from './vendor/core/intelligence/memory-bridge/dream-engine.js'
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
import { Prism } from './prism.js'
import { DiversityFloor } from './diversity-floor.js'
import type { DiversityFloorConfig, DiversityCategory, CategoryDiversityState, CompositeDiversity } from './diversity-floor.js'
import { RefusalChannel } from './refusal-channel.js'
import type { ActionKind, ActionHandle, ActionResolution, ActionRecord, RefusalChannelConfig, ProposedAction, RefusalFilter, ConsentSource } from './refusal-channel.js'
import type { OverlayPatch, OverlayApplyResult, OverlayStats } from './overlay-layer.js'
import { SelfModelKnowledgeProvider } from './self-model-knowledge.js'
import type { SelfModelProbe } from './self-model-knowledge.js'
import { InferenceTraceProvider } from './inference-trace.js'
import type { MnemicField } from '@cassicore/mnemic-field'
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
import { evaluateInvocationRules as evaluateInvocationRulesPure } from './composition/rule-evaluator.js'
import { evaluatePredicate, evaluateStrength } from './composition/predicate.js'
import type { Affect, AffectLabel } from '@cassicore/mnemic-field'
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
  /** B8: Prism — spectral counterfactual accumulation; fed by CounterfactualEngine. */
  private prism: Prism | null = null
  private selfNarrativeRenderer: SelfNarrativeRenderer | null = null

  /** Phase 2 (A2): vector projection scaffolding gate. */
  private vectorProjectionEnabled = false

  /** Phase 2 (B1): Concept-arithmetic composition store + active invocation list. */
  private compositionStore: CompositionStore | null = null
  private activeCompositionsList: ActiveComposition[] = []
  /** B1.3 — set of invocation-rule ids whose trigger was satisfied at last evaluate. */
  private invocationRuleSatisfied = new Set<string>()

  /** Phase 2 (N2): Posture coherence detector. */
  private postureCoherenceDetector: PostureCoherenceDetector | null = null

  /** Phase 2 (Gap 3): Universal Calibration Framework. */
  private calibrationManager: CalibrationManager | null = null
  private calibrationStore: CalibrationStore | null = null

  /** Self-model: Vindex→Mnemic bridge for architectural self-awareness. */
  private selfModelKnowledge: SelfModelKnowledgeProvider | null = null

  /** Multi-token inference trace provider for bridge enrichment. */
  private inferenceTrace: import('./inference-trace.js').InferenceTraceProvider | null = null

  /** Mnemic Field reference for persisting self-model knowledge (Gap 2). */
  private mnemicField: MnemicField | null = null

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
    this.vectorProjectionEnabled = config?.vectorProjectionEnabled ?? AURORA_DEFAULTS.vectorProjectionEnabled
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

    if (phase4Config.prismEnabled) {
      this.prism = new Prism(auroraDbPath, logger)
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

    // Self-model: Vindex→Mnemic bridge
    // Uses modelProvider (LarqlKnowledgeProvider), not knowledgeField (KnowledgeField)
    this._selfModelKnowledgeEnabled = phase4Config.selfModelKnowledgeEnabled ?? false
    if (this._selfModelKnowledgeEnabled && this.modelProvider) {
      this.setupSelfModelBridge(this._selfModelKnowledgeEnabled)
    }

    this.logger.info('Aurora initialized', {
      hasModelProvider: !!modelProvider,
      hasKnowledgeProvider: !!knowledgeProvider,
      hasPortalBridge: !!portalBridge,
      hasPersistence: !!persistence,
      hasSelfModelKnowledge: !!this.selfModelKnowledge,
      hydratedNodes: persistence ? persistence.hydrateClaustrum().nodes.length : 0,
      hydratedRecords: persistence ? persistence.hydrateReasoningLog(0).length : 0,
      reverieSamplingRate: this.reverieSamplingRate,
      reverieMinTextLength: this.reverieMinTextLength,
    })
  }

  /**
   * Wire a model provider after construction. Call when the vindex
   * finishes loading asynchronously (e.g. from deferred startup).
   * Safe to call multiple times — subsequent calls are no-ops if
   * the provider is already set.
   */
  setModelProvider(provider: ModelKnowledgeProvider): void {
    if (this.modelProvider) return  // already wired
    this.modelProvider = provider

    // Re-run self-model bridge setup now that provider is available.
    // Respect the original config — use the stored enabled flag rather than
    // hardcoding true (deferred wiring shouldn't bypass config).
    if (!this.selfModelKnowledge && this._selfModelKnowledgeEnabled) {
      this.setupSelfModelBridge(this._selfModelKnowledgeEnabled)
    }

    this.logger.info('Model provider wired post-construction')
  }

  private _selfModelKnowledgeEnabled = false

  /**
   * Set up the SelfModelKnowledge bridge from the current modelProvider.
   * Extracted from constructor so it can be called lazily when the
   * vindex finishes loading after admin API is already available.
   */
  private setupSelfModelBridge(enabled: boolean): void {
    if (!this.modelProvider) return
    const mph = (this.modelProvider as any).vindexHandle
    const numLayers = mph?.config?.numLayers ?? 30
    const phaseTransition = mph?.config?.phaseTransitionLayers
    const knowledgeBand = phaseTransition
      ? { start: phaseTransition[0] ?? 14, end: phaseTransition[1] ?? 27 }
      : { start: 14, end: 27 }
    const outputBand = { start: (phaseTransition?.[1] ?? 28), end: numLayers - 1 }
    const vindexName = mph?.path?.split('/').pop()?.replace('.vindex', '') ?? 'unknown'

    this.selfModelKnowledge = new SelfModelKnowledgeProvider(
      this.modelProvider as any,
      this.logger,
      { knowledgeBand, outputBand, vindexName },
    )

    // Wire inference trace provider for bridge enrichment
    if (enabled) {
      const mph2 = (this.modelProvider as any).vindexHandle
      if (mph2) {
        this.inferenceTrace = new InferenceTraceProvider({
          logger: this.logger,
          vindexPath: mph2.path,
          numLayers: mph2.config.numLayers,
        })
        const lqp = this.modelProvider as any
        if (lqp.larql && typeof lqp.larql.traceForward === 'function') {
          this.inferenceTrace.setNapiBackend({
            handle: mph2,
            tokenize: (text: string) => lqp.larql.vindexTokenize(mph2, text),
            traceForward: (tokens: number[], start: number, end: number, k: number) =>
              lqp.larql.traceForward(mph2, tokens, start, end, k),
          })
        }
        this.selfModelKnowledge!.setInferenceTraceProvider(this.inferenceTrace)
      }
    }
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

  private seedMemoryFromGraph(graph: UnifiedGraph): void {
    const seeded = new Set<string>()
    for (const [nodeId, node] of graph.nodes) {
      if (node.source !== 'model') continue
      const confidence = node.modelConfidence ?? 0
      if (confidence <= 0) continue

      const label = node.label?.toLowerCase().trim()
      if (!label || label.length < 2 || seeded.has(label)) continue
      seeded.add(label)

      const edges = graph.edges.get(nodeId) ?? []
      const relations = edges
        .filter(e => e.origin === 'model')
        .slice(0, 5)
        .map(e => {
          const target = graph.nodes.get(e.targetId)
          return `${e.edgeType || 'related_to'} ${target?.label || e.targetId}`
        })

      const content = `[vindex] ${node.label}${relations.length > 0 ? ': ' + relations.join(', ') : ''}`
      try {
        (this.cortex as any).signal('association', {
          type: 'association',
          content,
          author: 'aurora:vindex',
          salience: Math.min(0.7, Math.max(0.15, confidence)),
          tags: ['vindex', 'model', label],
        })
      } catch (err) {
        this.logger?.debug?.('seedMemoryFromGraph: cortex.signal failed', { error: String(err) })
      }
    }
  }

  /** Set session ID for reasoning records. */
  setSessionId(sessionId: string): void {
    this.sessionId = sessionId
  }

  /** Wire Mnemic Field for persisting self-model knowledge. */
  setMnemicField(mf: MnemicField): void {
    this.mnemicField = mf
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
    this.prism?.close()
    this.prism = null
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

    // Persist vindex-derived model knowledge as cortical signals so it
    // survives graph rebuilds.  Future observations about the same concept
    // find both a model node AND a memory entry → real resonance forms.
    this.seedMemoryFromGraph(graph)

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

  /**
   * Probe the vindex for model-internal associations about CassiCore
   * architectural concepts. Used by cron-driven self-model refresh cycles.
   *
   * Returns null when the bridge is disabled or knowledge provider unavailable.
   */
  probeSelfModel(): SelfModelProbe | null {
    if (!this.selfModelKnowledge) return null
    try {
      return this.selfModelKnowledge.probe()
    } catch (err) {
      this.logger.warn('probeSelfModel failed', { error: String(err) })
      return null
    }
  }

  /**
   * Ingest the latest self-model probe results into the Mnemic Field.
   * Should be called after probeSelfModel() to persist the knowledge.
   *
   * Requires the Mnemic Field to be accessible. Currently wired through
   * the Cortex signal path; full Mnemic integration via `ingestIntoMnemic`
   * requires the MnemicField reference to be exposed.
   */
  refreshSelfModelKnowledge(): SelfModelProbe | null {
    if (!this.selfModelKnowledge) return null
    try {
      const probe = this.selfModelKnowledge.probe()

      // Gap 2: Persist probe results into Mnemic Field as engrams + synapses
      if (this.mnemicField) {
        try {
          const ingested = this.selfModelKnowledge.ingestIntoMnemic(probe, this.mnemicField)
          this.logger.debug('Self-model knowledge persisted', { ingested })
        } catch (err) {
          this.logger.warn('Failed to persist self-model knowledge', { error: String(err) })
        }
      }

      this.logger.info('Self-model knowledge refreshed', {
        conceptsProbed: probe.concepts.length,
        selfAware: probe.concepts.filter(c => c.selfAware).length,
        bridges: probe.bridges.length,
        persisted: !!this.mnemicField,
      })
      // Wire into self-narrative for I-voice narration
      this.selfNarrativeRenderer?.setSelfModelProbe(probe)
      // Enrich top bridges with multi-token inference traces
      if (this.inferenceTrace && probe.bridges.length > 0) {
        queueMicrotask(() => {
          try {
            const traces = this.selfModelKnowledge?.enrichBridgesWithInference(probe.bridges, 3)
            if (traces) {
              this.logger.info('Inference traces enriched', {
                pairs: traces.traces.length,
                totalMs: traces.totalDurationMs,
              })
              // Gap 3: Persist inference traces as enriched engrams with synapses
              if (this.mnemicField) {
                const traceIds = new Map<string, string>()
                for (const trace of traces.traces) {
                  try {
                    const metadata = this.inferenceTrace!.traceMetadata(trace)
                    const stored = this.mnemicField.store({
                      nodeType: 'pattern',
                      content: JSON.stringify({
                        bridge: `${trace.conceptA}↔${trace.conceptB}`,
                        prompt: trace.prompt,
                        amplificationRatio: trace.amplificationRatio,
                        topFeatures: trace.features
                          .sort((a, b) => Math.abs(b.gate) - Math.abs(a.gate))
                          .slice(0, 5)
                          .map(f => ({ layer: f.layer, gate: f.gate, token: f.topToken })),
                      }),
                      initialPotentiation: 0.5,
                      tags: ['inference-trace', 'vindex-self-model', `bridge:${trace.conceptA}↔${trace.conceptB}`],
                      metadata: { ...metadata, probedAt: traces.probedAt },
                    })
                    traceIds.set(trace.conceptA, stored.id)
                    // Store the second concept too for synapse creation
                    const storedB = this.mnemicField.store({
                      nodeType: 'pattern',
                      content: JSON.stringify({ pairedWith: trace.conceptA, bridge: `${trace.conceptA}↔${trace.conceptB}` }),
                      initialPotentiation: 0.4,
                      tags: ['inference-trace', 'bridge-target'],
                      metadata: { probedAt: traces.probedAt },
                    })
                    traceIds.set(trace.conceptB, storedB.id)
                  } catch (err) {
                    this.logger.debug('Failed to store inference trace engram', { error: String(err) })
                  }
                }
                // Create co_activated synapses between bridged concept pairs
                for (const trace of traces.traces) {
                  const aId = traceIds.get(trace.conceptA)
                  const bId = traceIds.get(trace.conceptB)
                  if (aId && bId) {
                    try {
                      this.mnemicField.connect({
                        sourceId: aId, targetId: bId,
                        edgeType: 'similar_to',
                        weight: trace.amplificationRatio / 5, // normalized to 0-1 range
                        metadata: { source: 'vindex-inference-trace', probedAt: traces.probedAt },
                      })
                    } catch { /* best-effort */ }
                  }
                }
              }
              // Feed traces into self-narrative
              this.selfNarrativeRenderer?.setSelfModelProbe(probe)
            }
          } catch (err) {
            this.logger.debug('Bridge enrichment failed', { error: String(err) })
          }
        })
      }
      return probe
    } catch (err) {
      this.logger.warn('refreshSelfModelKnowledge failed', { error: String(err) })
      return null
    }
  }

  /** Whether the self-model bridge is active. */
  get hasSelfModelKnowledge(): boolean {
    return !!this.selfModelKnowledge
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

    // === C5 Resonance tick (every observation) ===
    try {
      this.logger.info('[resonance] tick at turn ' + this.turnCount, {
        modelNodes: this.currentState ? [...this.currentState.graph.nodes.values()].filter(n => (n.modelConfidence ?? 0) > 0).length : -1,
        hasProvider: !!(this.modelProvider as any)?.runSteeredGeneration,
        hasState: !!this.currentState,
      })
      if (this.currentState) {
        this.runResonanceTick(undefined, 5)
      }
    } catch { /* best-effort */ }

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
  /**
   * C1.4 — `leave_open` workflow. Mark a meditation seed as a
   * productive uncertainty rather than abandoned: it stops appearing
   * in scheduling candidates but surfaces in the projection's
   * "currently held questions" section.
   *
   * Returns `false` when the seeder is disabled.
   */
  markSeedLeftOpen(seedId: string, rationale: string): boolean {
    if (!this.meditationSeeder) return false
    this.meditationSeeder.markLeftOpen(seedId, rationale)
    return true
  }

  /**
   * C1.4 — list seeds in left_open state with their stored rationale.
   * Returns [] when the seeder is disabled.
   */
  listOpenQuestions(): Array<import('./meditation-seeder.js').MeditationSeed & { rationale: string | null }> {
    return this.meditationSeeder?.getOpenQuestions() ?? []
  }

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
      retrievalPolicy: parsed.retrievalPolicy,
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
      retrievalPolicy: rec.retrievalPolicy ?? null,
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
   * B2.2: Resolve the strongest currently-active retrieval policy across
   * all active compositions. Returns `null` when no active composition
   * carries a retrieval policy. Highest-strength wins on ties; mode
   * choice (consonant vs complementary) follows the strongest, not
   * blended.
   *
   * Callers (LarqlKnowledgeProvider) read this once per retrieval pass
   * and pass it to `gateKnnWithPolicy`. Spec §6: "B1 compositions can
   * pair posture and retrieval shape coherently."
   */
  getActiveRetrievalPolicy(): import('./composition/types.js').RetrievalPolicySpec | null {
    let best: import('./composition/types.js').RetrievalPolicySpec | null = null
    for (const c of this.activeCompositionsList) {
      const p = c.retrievalPolicy
      if (!p) continue
      if (!best || p.strength > best.strength) best = p
    }
    return best
  }

  /**
   * B1.3 — invocation-rule registry and edge-triggered evaluation.
   *
   * `defineInvocationRule` upserts a topical-context rule. When the
   * rule's `topicKeywords` start matching active concepts (rising edge),
   * `evaluateInvocationRules` invokes the bound composition with the
   * configured ttlTurns/magnitudeScale. Falling edges don't auto-
   * deactivate — the composition runs through its TTL.
   */
  defineInvocationRule(rule: import('./composition/types.js').InvocationRule): import('./composition/types.js').InvocationRule {
    if (!this.compositionStore) {
      throw new Error('compositionStore disabled (set compositionEnabled in AuroraConfig)')
    }
    return this.compositionStore.upsertInvocationRule(rule)
  }

  listInvocationRules(): import('./composition/types.js').InvocationRule[] {
    if (!this.compositionStore) return []
    return this.compositionStore.listInvocationRules()
  }

  deleteInvocationRule(id: string): boolean {
    if (!this.compositionStore) return false
    return this.compositionStore.deleteInvocationRule(id)
  }

  /**
   * Evaluate every registered rule against the current active-concept
   * set; for each rising edge, invoke the bound composition. Returns
   * the evaluation result so callers can audit fired/unfired/sustained
   * rules.
   *
   * Caller supplies `activeConcepts` — typically derived from the live
   * MentalState's activated nodes' labels.
   */
  /**
   * B1.4 — record a Cassi-authored composition proposal. Returns the
   * persisted proposal (status='pending'). Throws when the spec channel
   * is disabled.
   *
   * The DSL is NOT parsed at proposal time — that defers parse errors
   * to the review step, which lets the caller capture proposals
   * mid-conversation without forcing them to be syntactically perfect
   * first. `reviewCompositionProposal({status:'approved'})` validates
   * + commits via `defineComposition`.
   */
  proposeComposition(opts: {
    dsl: string
    proposedName: string
    rationale: string
    proposer: 'cassi' | 'operator'
    metadata?: Record<string, unknown>
  }): import('./composition/types.js').CompositionProposal {
    if (!this.compositionStore) {
      throw new Error('compositionStore disabled (set compositionEnabled in AuroraConfig)')
    }
    const id = `prop-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    return this.compositionStore.insertCompositionProposal({
      id,
      dsl: opts.dsl,
      proposedName: opts.proposedName,
      rationale: opts.rationale,
      proposer: opts.proposer,
      metadata: opts.metadata ?? {},
    })
  }

  /** B1.4 — list pending (or filtered) composition proposals. */
  listComposedProposals(filter?: { status?: import('./composition/types.js').CompositionProposalStatus }): import('./composition/types.js').CompositionProposal[] {
    if (!this.compositionStore) return []
    return this.compositionStore.listCompositionProposals(filter)
  }

  /**
   * B1.4 — review a proposal. On approval, parses the DSL via
   * `defineComposition` and commits the composition; on rejection or
   * withdrawal, just marks the proposal terminal. Returns the resulting
   * CompositionRecord on approval, or null otherwise.
   *
   * Approval failures (parse errors, suppressive without opt-in) leave
   * the proposal in 'pending' so the proposer can correct + re-submit.
   */
  reviewProposedComposition(opts: {
    id: string
    decision: 'approve' | 'reject' | 'withdraw'
    reviewedBy: 'cassi' | 'operator'
    reviewComment?: string
    allowSuppressive?: boolean
  }): import('./composition/types.js').CompositionRecord | null {
    if (!this.compositionStore) return null
    const proposal = this.compositionStore.getCompositionProposal(opts.id)
    if (!proposal || proposal.status !== 'pending') return null

    if (opts.decision === 'approve') {
      try {
        const rec = this.defineComposition(proposal.dsl, {
          description: proposal.rationale,
          metadata: { ...proposal.metadata, fromProposal: opts.id, proposer: proposal.proposer },
          allowSuppressive: opts.allowSuppressive,
        })
        this.compositionStore.reviewCompositionProposal({
          id: opts.id,
          status: 'approved',
          reviewedBy: opts.reviewedBy,
          reviewComment: opts.reviewComment,
        })
        return rec
      } catch (err) {
        this.logger.warn?.('Composition proposal approval failed at parse/define', {
          proposalId: opts.id,
          error: String(err),
        })
        // Leave proposal in pending so the proposer can revise.
        return null
      }
    }

    const targetStatus = opts.decision === 'reject' ? 'rejected' : 'withdrawn'
    this.compositionStore.reviewCompositionProposal({
      id: opts.id,
      status: targetStatus,
      reviewedBy: opts.reviewedBy,
      reviewComment: opts.reviewComment,
    })
    return null
  }

  /**
   * B1.4 — seed a small set of canonical built-in compositions. Idempotent:
   * skips any name that already exists in the store. Returns the names
   * that were newly seeded.
   *
   * The defaults are intentionally minimal — three canonical postures
   * Cassi can invoke or operators can wire to rules. Real production
   * compositions will be authored over time via `proposeComposition` +
   * approval flow.
   */
  seedBuiltInCompositions(): string[] {
    if (!this.compositionStore) return []
    const seeded: string[] = []
    const builtIns = [
      {
        name: 'careful_focus',
        dsl: 'careful_focus = gate("rigor") + gate("clarity") - gate("haste")',
        description: 'Steady, low-arousal posture for careful analysis.',
      },
      {
        name: 'warm_inquiry',
        dsl: 'warm_inquiry = gate("warmth") + gate("curiosity")',
        description: 'Open, engaged posture for exploratory conversation.',
      },
      {
        name: 'honest_review',
        dsl: 'honest_review = gate("rigor") + gate("clarity") + gate("warmth")',
        description: 'Honest-but-kind posture for code review and critique.',
      },
    ]
    for (const b of builtIns) {
      if (this.compositionStore.getComposition(b.name)) continue
      try {
        this.defineComposition(b.dsl, { description: b.description })
        seeded.push(b.name)
      } catch (err) {
        this.logger.warn?.('Built-in composition seed failed', { name: b.name, error: String(err) })
      }
    }
    return seeded
  }

  evaluateInvocationRules(activeConcepts: ReadonlyArray<string>): import('./composition/types.js').InvocationRuleEvaluation {
    if (!this.compositionStore) return { fired: [], unfired: [], stillSatisfied: [] }
    const rules = this.compositionStore.listInvocationRules()
    const result = evaluateInvocationRulesPure(rules, activeConcepts, this.invocationRuleSatisfied)
    for (const id of result.fired) {
      const rule = rules.find(r => r.id === id)
      if (!rule) continue
      try {
        this.invokeComposition(rule.composition, {
          ttlTurns: rule.ttlTurns,
          magnitudeScale: rule.magnitudeScale,
          trigger: `rule:${rule.id}`,
        })
      } catch (err) {
        this.logger.warn?.('Invocation rule fired but composition invocation failed', {
          ruleId: rule.id,
          composition: rule.composition,
          error: String(err),
        })
      }
    }
    return result
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

  /**
   * A2: Compose a vector projection from the current mental state. The
   * `perLayer` Float32Arrays are placeholders today (cassi-larql N-API
   * doesn't surface raw gate vectors yet); the `contributions` array is
   * meaningful and feeds the A2.4 active-gate annotation rendering.
   *
   * Returns `null` when vector projection is disabled, no current state
   * exists, or no nodes are activated.
   */
  getVectorProjection(
    options?: import('./types.js').VectorProjectionOptions,
    state?: MentalState,
    vectorSource?: import('./projection/vector-projection.js').GateVectorSource,
    baselineNormSource?: import('./projection/vector-projection.js').BaselineNormSource,
  ): import('./types.js').VectorProjection | null {
    if (!this.vectorProjectionEnabled) return null
    const target = state ?? this.currentState
    if (!target) return null
    return this.projector.projectVector(target, options, {
      vindexId: this.knowledgeProvider ? (this.knowledgeProvider as { vindexId?: string }).vindexId ?? null : null,
      targetModelId: null,
    }, vectorSource, baselineNormSource)
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
   * C5 Resonance pipeline — steered generation from mental state.
   *
   * Checks whether the current mental state has model-confident nodes
   * (via the vindex), composes residual-stream steering vectors from
   * those nodes, and runs steered generation. The generated text is
   * then observed back into the graph, closing the loop.
   *
   * Designed to be called from the daemon turn boundary
   * (e.g. `helix-posture-runner.ts` after each `observeReasoning`).
   *
   * Cost: one residual-norm probe prefill + one generation. On GPU
   * this is ~3s per generated token. Short generations (5-10 tokens)
   * keep the cost reasonable. Returns null when there are no model-
   * confident nodes or the vindex isn't loaded.
   */
  runResonanceTick(prompt?: string, maxNewTokens: number = 8): { text: string; contributions: number } | null {
    const prov = this.modelProvider as { runSteeredGeneration?: Function } | null
    if (!prov?.runSteeredGeneration) {
      this.logger.info('[resonance] no steered generation provider')
      return null
    }
    if (!this.currentState) {
      this.logger.info('[resonance] no current state')
      return null
    }

    const modelNodes = [...this.currentState.graph.nodes.values()]
      .filter(n => (n.modelConfidence ?? 0) > 0 && n.label)
    if (modelNodes.length === 0) {
      this.logger.info('[resonance] no model-confident nodes', {
        totalNodes: this.currentState.graph.nodes.size,
      })
      return null
    }

    try {
      const result = (prov.runSteeredGeneration as Function)(
        prompt ?? `Reflecting on ${modelNodes.slice(0, 3).map(n => n.label).join(', ')}`,
        this.currentState,
        maxNewTokens,
        { targetResidualFraction: 0.05, layerSubset: undefined },
      )
      if (!result) return null

      const { generation, projection } = result as { generation: { text: string }; projection: { contributions: Array<{ nodeId: string; label: string }> } }

      // Observe the steered output back into the mental state
      if (generation.text.length > 10) {
        try {
          this.observeReasoning(generation.text)
        } catch { /* silent — observation is best-effort */ }
      }

      this.logger.info('[resonance] steered generation', {
        text: generation.text.slice(0, 80),
        contributingNodes: projection.contributions.length,
        modelNodes: modelNodes.length,
      })

      return { text: generation.text, contributions: projection.contributions.length }
    } catch (err) {
      this.logger.debug('[resonance] pipeline failed', { error: String(err) })
      return null
    }
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

  /**
   * N4.2 — Get a projection-ready summary of pending Cassi-authored
   * proposals (count, welfare-flagged subset, SLA-exceeded list).
   * Returns null when the spec channel is disabled.
   */
  async getSpecChannelProjectionSummary(): Promise<{
    pendingCount: number
    welfareFlaggedPending: number
    slaExceeded: Array<{ id: string; title: string; ageDays: number; isWelfare: boolean }>
  } | null> {
    if (!this.cassiSpecChannel) return null
    return await this.cassiSpecChannel.getProjectionSummary()
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
   * C3.3 — drift surveillance: caller supplies probe descriptors with
   * both base and overlay hits already computed; returns per-probe
   * divergence. Returns [] when overlay is disabled.
   */
  surveyOverlayDrift(probes: ReadonlyArray<import('./overlay-layer.js').DriftProbe>): import('./overlay-layer.js').DriftFinding[] {
    return this.overlayLayer?.surveyDrift(probes) ?? []
  }

  /**
   * C3.3 — propose a reversal candidate against an active patch.
   * Returns null when overlay is disabled.
   */
  proposeOverlayReversal(opts: {
    patchId: string
    reason: import('./overlay-layer.js').ReversalCandidate['reason']
    proposer: import('./overlay-layer.js').ReversalCandidate['proposer']
    rationale: string
    evidence?: Record<string, unknown>
  }): import('./overlay-layer.js').ReversalCandidate | null {
    return this.overlayLayer?.proposeReversalCandidate(opts) ?? null
  }

  /** C3.3 — list pending reversal candidates. */
  listOverlayReversalCandidates(): import('./overlay-layer.js').ReversalCandidate[] {
    return this.overlayLayer?.listReversalCandidates() ?? []
  }

  /** C3.3 — accept (rollback patch + clear) or reject a reversal candidate. */
  acceptOverlayReversal(id: string): boolean {
    return this.overlayLayer?.acceptReversalCandidate(id) ?? false
  }

  rejectOverlayReversal(id: string, reason?: string): boolean {
    return this.overlayLayer?.rejectReversalCandidate(id, reason) ?? false
  }

  /**
   * C3.2 — propose an overlay-patch candidate from a Reverie/observer
   * insight. Returns null when overlay is disabled. Throws when the
   * patch op is outside the Insert/InsertKnn allowlist.
   */
  proposeOverlayCandidate(opts: {
    patch: OverlayPatch
    source: import('./overlay-layer.js').OverlayCandidate['source']
    rationale: string
    confidence: number
    evidence?: Record<string, unknown>
  }): import('./overlay-layer.js').OverlayCandidate | null {
    return this.overlayLayer?.proposeOverlayCandidate(opts) ?? null
  }

  /** C3.2 — list pending proposed-patch candidates, highest confidence first. */
  listOverlayCandidates(): import('./overlay-layer.js').OverlayCandidate[] {
    return this.overlayLayer?.listOverlayCandidates() ?? []
  }

  /** C3.2 — accept a proposed candidate: applies its patch + clears the candidate. */
  acceptOverlayCandidate(id: string): OverlayApplyResult | null {
    return this.overlayLayer?.acceptOverlayCandidate(id) ?? null
  }

  /** C3.2 — reject a proposed candidate without applying. */
  rejectOverlayCandidate(id: string, reason?: string): boolean {
    return this.overlayLayer?.rejectOverlayCandidate(id, reason) ?? false
  }

  /** C3.2 — modify a pending candidate's patch (operator tweak). */
  modifyOverlayCandidate(id: string, patch: OverlayPatch): import('./overlay-layer.js').OverlayCandidate | null {
    return this.overlayLayer?.modifyOverlayCandidate(id, patch) ?? null
  }

  /**
   * B7.4 — counterfactual projection summary (active forks).
   * Returns null when counterfactual exploration is disabled.
   */
  getCounterfactualProjectionSummary(): ReturnType<CounterfactualEngine['getProjectionSummary']> | null {
    return this.counterfactualEngine?.getProjectionSummary() ?? null
  }

  /**
   * B8.P.4 — Prism projection summary (top stark concepts +
   * total-spectrum exposure). Returns null when Prism is disabled.
   */
  getPrismProjectionSummary(opts?: { topN?: number }): ReturnType<Prism['getProjectionSummary']> | null {
    return this.prism?.getProjectionSummary(opts) ?? null
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
    const sig = this.currentState.affect
    const sessionId = this.persistenceSession?.sessionId ?? null
    return this.counterfactualEngine.explore(
      this.currentState.graph,
      scope,
      perturbations,
      observeKinds,
      {
        ...opts,
        baseColor: sig?.label ?? null,
        baseAffect: sig?.affect ?? null,
        recordToPrism: this.prism
          ? (c) => this.prism?.deposit(c, sessionId)
          : undefined,
      },
    )
  }

  /** Read affordance: snapshot the Prism's per-color exposure (P.1). Null when disabled. */
  prismTotalSpectrum(): Map<string, number> | null {
    return this.prism?.totalSpectrum() ?? null
  }

  /** Read affordance: count nodes the Prism has accumulated (P.1). Null when disabled. */
  prismNodeCount(): number | null {
    return this.prism?.nodeCount() ?? null
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

  /** Stub — narrative update from Thalamus (not yet wired to a backing store). */
  async updateFeatureNarrative(_contextText: string): Promise<void> {}
}
