/**
 * Subconscious — Conscious Observer Architecture (v5)
 *
 * The Subconscious is the stream-of-consciousness layer of CassiCore.
 * It observes ALL system events (not just turn-level ones) through a
 * universal tap on the EventBus, maintaining a system-wide mental model
 * of everything happening across the runtime.
 *
 * Architecture:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │  EventBus.onAll()  →  EventStream (ring buffer)                 │
 * │      ↓                                                          │
 * │  HeuristicObserver (sync, per-event)  +  LLMObserver (30s)     │
 * │      ↓                    ↓                                     │
 * │                     SystemModel                                 │
 * │                         ↓                                       │
 * │  getContextInjection()  →  TurnPipeline injection               │
 * │                         ↓                                       │
 * │  consciousness:* events emitted back onto EventBus              │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Emits events:
 * - consciousness:observation — heuristic or LLM observation produced
 * - consciousness:anomaly     — anomaly detected and added to model
 *
 * Backward compatibility:
 * The public API maintains shims for all 19 consumer call sites so that
 * Phase 3 consumer migration can proceed incrementally.
 */

import { EventStream } from "./event-stream.js";
import { HeuristicObserver } from "./heuristic-observer.js";
import { LLMObserver } from "./llm-observer.js";
import { SystemModel } from "./system-model.js";
import { DEFAULT_SUBCONSCIOUS_CONFIG } from "./types.js";

import type {
  SubconsciousConfig,
  Observation,
  Anomaly,
  SystemModelSnapshot,
} from "./types.js";
import type { IMemory } from "@cassicore/foundation";
import type { ILogger, IEventBus } from "@cassicore/foundation";
import type { IProvider } from "@cassicore/foundation";
import type { SessionDigestStore } from "../../vendor/core/intelligence/session-digest.js";
import type { ModuleSessionRegistry } from "../../vendor/core/intelligence/module-session-registry.js";
import type { CorticalField } from "../../vendor/core/intelligence/cortex/index.js";

export type { SubconsciousConfig } from "./types.js";

export class Subconscious {
  readonly name = "subconscious" as const;
  readonly priority: number;

  private readonly logger: ILogger;
  private readonly config: Required<SubconsciousConfig>;

  private readonly eventStream: EventStream;
  private readonly heuristicObserver: HeuristicObserver;
  private readonly llmObserver: LLMObserver;
  private readonly systemModel: SystemModel;

  private eventBus?: IEventBus;
  private digestStore?: SessionDigestStore;
  private memory?: IMemory;
  private cortex?: CorticalField;
  /** Callback to retrieve live session IDs from the SessionManager for periodic reconciliation. */
  private liveSessionGetter?: () => Array<{ sessionId: string; startedAt: number; lastActivityAt?: number; turnCount?: number }>;

  /** Drains heuristic buffers and integrates into the system model every turn event */
  private drainTimer?: NodeJS.Timeout;
  private persistTimer?: NodeJS.Timeout;
  /** Heartbeat monitor timer — detects silent intelligence modules */
  private heartbeatTimer?: NodeJS.Timeout;
  /** Unsubscribe function for the bus.onAll listener */
  private unsubAll?: () => void;
  /** Re-entrancy guard — prevents drainHeuristicBuffers → emit → onAll → drain cascade */
  private draining = false;

  constructor(logger: ILogger, config?: Partial<SubconsciousConfig>) {
    this.logger = logger.child?.("subconscious") ?? logger;

    this.config = {
      ...DEFAULT_SUBCONSCIOUS_CONFIG,
      ...config,
      llmObserver: {
        ...DEFAULT_SUBCONSCIOUS_CONFIG.llmObserver,
        ...(config?.llmObserver ?? {}),
        ...((config as any)?.model && !(config?.llmObserver as any)?.model
          ? { model: (config as any).model }
          : {}),
      },
    };

    this.priority = this.config.priority;

    this.eventStream = new EventStream(this.logger, {
      maxBufferSize: this.config.eventBufferSize,
    });
    this.heuristicObserver = new HeuristicObserver(this.logger);
    this.llmObserver = new LLMObserver(this.logger, this.config.llmObserver);
    this.systemModel = new SystemModel(this.logger);

    if (this.config.enabled) {
      this.logger.info("Subconscious: v5 conscious-observer architecture initialized");
    } else {
      this.logger.info("Subconscious: disabled");
    }
  }


  setMemory(memory: IMemory): void {
    this.memory = memory;
    this.systemModel.setMemory(memory);
    // Wire memory to the LLM observer so each sweep can search the session
    // index for cross-session historical context.
    this.llmObserver.setMemory(memory);
    this.logger.info("Subconscious: memory wired");
    void this.systemModel.hydrate();
  }

  setCortex(cortex: CorticalField): void {
    this.cortex = cortex
    this.llmObserver.setCortex(cortex)
  }

  setProvider(provider: IProvider): void {
    this.llmObserver.setProvider(provider);
    this.logger.info("Subconscious: provider wired", { provider: provider.id });
  }

  setModuleRegistry(registry: ModuleSessionRegistry): void {
    this.llmObserver.setModuleRegistry(registry)
  }

  setDigestStore(store: SessionDigestStore): void {
    this.digestStore = store;
    this.logger.info("Subconscious: SessionDigestStore wired");
  }

  /**
   * Provide a callback that returns the current live sessions from the
   * SessionManager. Used by the periodic reconcile to detect and prune
   * stale sessions without importing SessionManager directly.
   */
  setLiveSessionGetter(
    getter: () => Array<{ sessionId: string; startedAt: number; lastActivityAt?: number; turnCount?: number }>,
  ): void {
    this.liveSessionGetter = getter;
    this.logger.info("Subconscious: live session getter wired");
  }

  /**
   * Connect to the EventBus — wires the EventStream to observe all events
   * and sets up the heuristic drain loop.
   */
  onEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.logger.info("Subconscious: event bus wired");

    // Skip heavy event processing when disabled — prevents event cascade
    if (!this.config.enabled) {
      this.logger.info("Subconscious: skipping onAll subscription (disabled)");
      return;
    }

    this.eventStream.connect(bus);

    // Also wire the HeuristicObserver to see every event directly
    // (so it can run synchronously without going through the ring buffer)
    this.unsubAll = bus.onAll((event) => {
      this.heuristicObserver.observe(event);
      this.systemModel.update(event);

      // Drain heuristic buffers after each event (lock-free, drain-pattern)
      this.drainHeuristicBuffers();
    });

    // WHY: do NOT call this.start() here — the daemon calls startModule()
    // separately. Calling start() from both onEventBus() and startModule()
    // creates duplicate timers and double LLM sweeps.
  }

  /** Alias for backward compat with daemon wiring */
  connect(bus: IEventBus): void {
    this.onEventBus(bus);
  }


  private _started = false;

  start(): void {
    if (!this.config.enabled) return;
    if (this._started) return;
    this._started = true;

    this.llmObserver.start(this.eventStream, this.systemModel, (obs) => {
      // When the sweep finds cross-session correlations, emit them as an event
      // so other modules can consume the historical context signal.
      if (obs.crossSessionMatches && obs.crossSessionMatches.length > 0) {
        const query = obs.patterns.slice(0, 3).join(" ");
        this.emitEvent("consciousness:cross-session-correlation", {
          refs: obs.crossSessionMatches.map((m) => m.ref),
          query,
          topScore: obs.crossSessionMatches[0].score,
          timestamp: new Date(obs.timestamp),
        });
      }
    });

    this.persistTimer = setInterval(() => {
      void this.systemModel.persist();
    }, this.config.persistenceIntervalMs);
    try { (this.persistTimer as NodeJS.Timeout & { unref?: () => void }).unref?.(); } catch {}

    // Periodic heartbeat sweep — detects intelligence modules that have gone silent.
    // Runs every 10 minutes (after an initial 15-minute warm-up enforced inside
    // HeuristicObserver.checkHeartbeats itself).
    // Also performs bidirectional session reconciliation to prune stale sessions
    // that accumulated from missed session:ended events or daemon-level pruning.
    this.heartbeatTimer = setInterval(() => {
      this.heuristicObserver.checkHeartbeats();
      this.drainHeuristicBuffers();
      // Periodic session reconcile — bidirectional sync with live SessionManager
      this.periodicReconcile();
    }, 10 * 60_000);
    try { (this.heartbeatTimer as NodeJS.Timeout & { unref?: () => void }).unref?.(); } catch {}

    this.logger.info("Subconscious: started", {
      llmObserverEnabled: this.config.llmObserver.enabled,
      persistenceIntervalMs: this.config.persistenceIntervalMs,
    });
  }

  stop(): void {
    this.llmObserver.stop();
    if (this.unsubAll) {
      this.unsubAll();
      this.unsubAll = undefined;
    }
    if (this.persistTimer) {
      clearInterval(this.persistTimer);
      this.persistTimer = undefined;
    }
    if (this.drainTimer) {
      clearInterval(this.drainTimer);
      this.drainTimer = undefined;
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = undefined;
    }
    this.eventStream.disconnect();
    this.logger.info("Subconscious: stopped");
  }

  async cleanup(): Promise<void> {
    this.stop();
    await this.systemModel.persist();
    this.logger.info("Subconscious: cleanup complete");
  }


  /**
   * Build context injection for a turn pipeline call.
   *
   * This is the primary output of the subconscious: a concise string
   * summarizing system state, active anomalies, and recent LLM awareness
   * that gets injected into the turn prompt.
   *
   * Returns undefined when there is nothing significant to inject.
   */
  getContextInjection(sessionId: string): string | undefined {
    if (!this.config.enabled) return undefined;
    return this.systemModel.getContextInjection(sessionId);
  }


  /**
   * Snapshot of the full system model — for admin API, MCP gateway, and CLI.
   */
  snapshot(): SystemModelSnapshot {
    return this.systemModel.snapshot();
  }

  /**
   * Recent observations from heuristic + LLM observers.
   */
  getRecentObservations(count = 20): Observation[] {
    return this.systemModel.getRecentObservations(count);
  }

  /**
   * All active (unacknowledged) anomalies, optionally including acknowledged ones.
   */
  getAnomalies(includeAcknowledged = false): Anomaly[] {
    return this.systemModel.getAnomalies(includeAcknowledged);
  }

  /**
   * Acknowledge (dismiss) an anomaly by ID. Returns true if found.
   */
  acknowledgeAnomaly(anomalyId: string): boolean {
    return this.systemModel.acknowledgeAnomaly(anomalyId);
  }

  /**
   * Session IDs currently tracked in the system model.
   */
  getSessionIds(): string[] {
    return this.systemModel.getSessionIds();
  }

  /**
   * Reconcile the SystemModel with live runtime state gathered after startup.
   * Fills in sessions/drones that were created before the Subconscious was
   * connected to the event bus and therefore never appeared via events.
   */
  reconcile(opts: {
    sessions?: Array<{ sessionId: string; startedAt: number; lastActivityAt?: number; turnCount?: number }>
    droneIds?: string[]
  }): void {
    this.systemModel.reconcile(opts)
  }

  /**
   * LLM observer history (for diagnostics).
   */
  getLLMObservations(count = 10) {
    return this.llmObserver.getRecentObservations(count);
  }

  /**
   * Full-text search across indexed session history for content related to
   * the given query. Returns compact SessionRef-annotated results from the
   * session index so callers (Thinker, Dialectic, etc.) can retrieve precise
   * historical context without loading entire sessions.
   *
   * Returns an empty array when the session index is unavailable.
   */
  searchObservations(query: string, limit = 10) {
    if (!this.memory?.searchIndex) return [];
    try {
      return this.memory.searchIndex(query, { limit });
    } catch (err) {
      this.logger.debug("Subconscious.searchObservations failed", { error: String(err) });
      return [];
    }
  }

  /**
   * Event stream statistics (for diagnostics).
   */
  getEventStreamStats() {
    return {
      totalEvents: this.eventStream.totalCount,
      activeSessions: this.eventStream.activeSessions.length,
      eventRate: this.eventStream.getRate(60),
      typeCounts: Object.fromEntries(this.eventStream.getTypeCounts()),
    };
  }

  /**
   * Combined observer pipeline stats — event stream + heuristic + LLM observer.
   * Used by the /intelligence/subconscious/stream admin endpoint and cassi_consciousness tool.
   */
  getObserverStats(windowSecs = 60) {
    const windowMs = windowSecs * 1_000;
    const summary = this.eventStream.summarize(windowMs);
    const allObs = this.systemModel.getRecentObservations(200);
    const heuristicObs = allObs.filter((o) => o.source === "heuristic");
    const llmObs = allObs.filter((o) => o.source === "llm");
    const recentLLM = this.llmObserver.getRecentObservations(5);
    const lastSweep = this.llmObserver.lastSweepTimestamp;

    return {
      // Stream
      windowSecs,
      totalEvents: summary.totalEvents,
      eventsPerSecond: summary.eventsPerSecond,
      activeSessions: summary.activeSessions,
      topEventTypes: summary.topTypes,
      recentSequence: summary.recentSequence.slice(-20),
      // Observers
      heuristicObservationCount: heuristicObs.length,
      llmObservationCount: llmObs.length,
      lastLLMSweepAt: lastSweep,
      lastLLMSweepAgo: lastSweep > 0 ? Date.now() - lastSweep : null,
      // Recent LLM insights
      recentLLMObservations: recentLLM.map((o) => ({
        id: o.id,
        summary: o.summary,
        patterns: o.patterns,
        concerns: o.concerns,
        opportunities: o.opportunities,
        confidence: o.confidence,
        timestamp: o.timestamp,
        eventCount: o.eventCount,
      })),
    };
  }

  /**
   * Clean up state for a session that has ended.
   */
  cleanupSession(sessionId: string): void {
    this.systemModel.cleanupSession(sessionId);
    this.eventStream.cleanupSession(sessionId);
    this.logger.debug("Subconscious: session cleaned up", { sessionId });
  }

  /**
   * Periodic bidirectional session reconciliation.
   * Pulls live sessions from the getter, syncs the SystemModel and
   * EventStream, removing stale entries and adding missing ones.
   */
  private periodicReconcile(): void {
    if (!this.liveSessionGetter) return;
    try {
      const liveSessions = this.liveSessionGetter();
      const liveIds = new Set(liveSessions.map((s) => s.sessionId));

      // Bidirectional reconcile on SystemModel (adds missing + removes stale)
      this.systemModel.reconcile({ sessions: liveSessions });

      // Prune stale entries from EventStream session index
      this.eventStream.pruneStaleSessions(liveIds);
    } catch (err) {
      this.logger.warn("Subconscious: periodic reconcile failed", { error: String(err) });
    }
  }

  private drainHeuristicBuffers(): void {
    // Re-entrancy guard: emitEvent() inside this method can trigger onAll → drain again
    if (this.draining) return;
    this.draining = true;
    try {
    const observations = this.heuristicObserver.drainObservations();
    const anomalies = this.heuristicObserver.drainAnomalies();

    for (const obs of observations) {
      this.systemModel.addObservation(obs);
      this.emitEvent("consciousness:observation", { observation: obs });

      if (this.cortex) {
        try {
          this.cortex.signal('sensory', {
            type: 'perception',
            content: obs.summary,
            author: 'subconscious',
            sessionId: obs.sessionId,
            salience: obs.confidence,
            tags: obs.patterns,
          })
        } catch { /* cortex signal is fire-and-forget */ }
      }

      // Emit legacy subconscious:learning so Thinker / AI Scientist continue
      // to receive structured observations without needing changes to their
      // event subscriptions in this migration phase.
      this.emitEvent("subconscious:learning", {
        learning: {
          summary: obs.summary,
          confidence: obs.confidence,
          patterns: obs.patterns,
          timestamp: obs.timestamp,
        },
      });

      // Also bridge as subconscious:pattern so Dialectic can pick it up
      for (const pattern of obs.patterns) {
        this.emitEvent("subconscious:pattern", {
          sessionId: obs.sessionId,
          pattern: { pattern, confidence: obs.confidence, evidence: [] },
        });
      }
    }

    for (const anomaly of anomalies) {
      this.systemModel.addAnomaly(anomaly);
      this.emitEvent("consciousness:anomaly", { anomaly });

      if (this.cortex) {
        try {
          this.cortex.signal('limbic', {
            type: 'anomaly',
            content: anomaly.description,
            author: 'subconscious',
            sessionId: anomaly.sessionId,
            salience: anomaly.severity === 'high' ? 0.8 : anomaly.severity === 'medium' ? 0.6 : 0.4,
            valence: -0.4,
            tags: [anomaly.severity],
          })
        } catch { /* cortex signal is fire-and-forget */ }
      }

      // Emit legacy subconscious:anomaly so Thinker / Dialectic / AI Scientist
      // keep receiving anomaly notifications during Phase 3 migration.
      this.emitEvent("subconscious:anomaly", {
        sessionId: anomaly.sessionId,
        anomaly: {
          summary: anomaly.description,
          reason: anomaly.description,
          category: anomaly.severity,
          severity: anomaly.severity,
          evidence: anomaly.suggestedAction,
        },
      });
    }
     } finally {
      this.draining = false;
    }
  }

  private emitEvent(type: string, payload: Record<string, unknown>): void {
    try {
      (this.eventBus as unknown as { emit?: (e: Record<string, unknown>) => void })
        ?.emit?.({ type, ...payload });
    } catch (err) {
      this.logger.debug("Subconscious: failed to emit event", { type, error: String(err) });
    }
  }
}

/**
 * @dep callers: subconscious-memory-integration.test.ts (tests/subconscious-memory-integration.test.ts), subconscious.test.ts (tests/subconscious.test.ts), createIntelligence (core/intelligence/index.ts), run (scripts/smoke-subconscious.ts)
 * @dep module: Intelligence
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

export const createSubconscious = (logger: ILogger, config?: Partial<SubconsciousConfig>): Subconscious =>
  new Subconscious(logger, config);
