/**
 * SystemModel — System-wide mental model of the CassiCore runtime.
 *
 * Replaces the per-session MentalModel with a holistic view of the entire
 * system: all sessions, all providers, all plugins, all agents.
 *
 * Updated by:
 * - HeuristicObserver (real-time, from event dispatch)
 * - LLMObserver (periodic sweeps)
 * - Direct event observation in the Subconscious.onEvent() hook
 *
 * Consumed by:
 * - Subconscious.getContextInjection() — builds context for turn pipeline
 * - LLMObserver.buildPrompt() — gives the LLM a system state snapshot
 * - Admin API / MCP gateway — surfaces awareness to tooling
 */

import { v4 as uuidv4 } from "uuid";

import type {
  SessionState,
  SystemModelSnapshot,
  Observation,
  Anomaly,
  LLMObservation,
} from "./types.js";
import type { RuntimeEvent } from "../../../types/events.js";
import type { IMemory } from "../../../types/intelligence.js";
import type { ILogger } from "../../../types/interfaces.js";


type ProviderHealthStatus = "healthy" | "degraded" | "error" | "rate_limited";
type PluginHealthStatus = "healthy" | "crashed" | "stopped";

export class SystemModel {
  private readonly logger: ILogger;
  private memory?: IMemory;

  // ─── Session Registry ─────────────────────────────────────────────────────
  private readonly sessions = new Map<string, SessionState>();

  // ─── System Health ────────────────────────────────────────────────────────
  private readonly providerHealth = new Map<string, ProviderHealthStatus>();
  private readonly pluginStatus = new Map<string, PluginHealthStatus>();
  private readonly budgetTiers = new Map<string, string>();

  // ─── Agent Tracking ───────────────────────────────────────────────────────
  private readonly activeDrones = new Set<string>();
  private readonly activeTeams = new Set<string>();

  // ─── Observation History ──────────────────────────────────────────────────
  private observations: Observation[] = [];
  private anomalies: Anomaly[] = [];
  private static readonly MAX_OBSERVATIONS = 200;
  private static readonly MAX_ANOMALIES = 100;

  // ─── Context Injection Cache ──────────────────────────────────────────────
  // Keyed by sessionId (or "__global" for session-less callers)
  private readonly contextCache = new Map<string, string>();

  constructor(logger: ILogger) {
    this.logger = logger.child?.("system-model") ?? logger;
  }

  // ─── Dependencies ──────────────────────────────────────────────────────────

  setMemory(memory: IMemory): void {
    this.memory = memory;
  }

  // ─── Event Handler ────────────────────────────────────────────────────────

  /**
   * Process a runtime event to update the system model.
   * Called for every event ingested by the EventStream.
   */
  update(event: RuntimeEvent): void {
    try {
      this.applyEvent(event);
    } catch (err) {
      this.logger.warn("SystemModel.update error", { type: event.type, error: String(err) });
    }
  }

  private applyEvent(event: RuntimeEvent): void {
    // Cast to string so all case branches remain reachable even if not in the union yet
    const t = event.type as string;
    const e = event as Record<string, unknown>;

    switch (t) {
      // ── Sessions ──────────────────────────────────────────────────────────
      case "session:created": {
        const sessionId = e.sessionId as string;
        if (sessionId) {
          const ts = (e.timestamp as Date | undefined)?.getTime() ?? Date.now();
          this.sessions.set(sessionId, {
            sessionId,
            startedAt: ts,
            lastActivityAt: ts,
            turnCount: 0,
            tokenCount: 0,
            phase: "initial",
            recentToolCalls: [],
          });
        }
        break;
      }
      case "session:ended": {
        const sessionId = e.sessionId as string;
        if (sessionId) {
          this.sessions.delete(sessionId);
          this.contextCache.delete(sessionId);
        }
        break;
      }
      case "turn:start": {
        const sessionId = e.sessionId as string;
        if (sessionId) {
          const ts = (e.timestamp as Date | undefined)?.getTime() ?? Date.now();
          // Upsert: session may not have been formally created via session:created
          const existing = this.sessions.get(sessionId);
          if (existing) {
            existing.lastActivityAt = ts;
            existing.turnCount++;
            existing.phase = "active";
          } else {
            this.sessions.set(sessionId, {
              sessionId,
              startedAt: ts,
              lastActivityAt: ts,
              turnCount: 1,
              tokenCount: 0,
              phase: "active",
              recentToolCalls: [],
            });
          }
          this.contextCache.delete(sessionId);
        }
        break;
      }
      case "turn:end": {
        const sessionId = e.sessionId as string;
        if (sessionId) this.contextCache.delete(sessionId);
        break;
      }
      case "turn:tool_call": {
        const sessionId = e.sessionId as string;
        const session = sessionId ? this.sessions.get(sessionId) : undefined;
        if (session) {
          const toolName = (e.toolName ?? e.tool) as string | undefined;
          if (toolName) {
            session.recentToolCalls = [...session.recentToolCalls.slice(-9), toolName];
          }
        }
        break;
      }

      // ── Providers ─────────────────────────────────────────────────────────
      case "provider:request_start": {
        const pid = e.providerId as string;
        if (pid && this.providerHealth.get(pid) !== "rate_limited") {
          this.providerHealth.set(pid, "healthy");
        }
        break;
      }
      case "provider:request_error": {
        const pid = e.providerId as string;
        if (pid) {
          const consecutive = (e.consecutiveErrors as number) ?? 1;
          this.providerHealth.set(pid, consecutive >= 3 ? "error" : "degraded");
          this.invalidateContextCacheAll();
        }
        break;
      }
      case "provider:error_reset": {
        const pid = e.providerId as string;
        if (pid) {
          this.providerHealth.set(pid, "healthy");
          this.invalidateContextCacheAll();
        }
        break;
      }
      case "provider:rate_limited": {
        const pid = e.providerId as string;
        if (pid) {
          this.providerHealth.set(pid, "rate_limited");
          const retryAfterMs = (e.retryAfterMs as number) ?? 60_000;
          setTimeout(() => {
            if (this.providerHealth.get(pid) === "rate_limited") {
              this.providerHealth.set(pid, "healthy");
              this.invalidateContextCacheAll();
            }
          }, retryAfterMs + 5000);
          this.invalidateContextCacheAll();
        }
        break;
      }
      case "provider:request_end": {
        const pid = e.providerId as string;
        if (pid && this.providerHealth.get(pid) !== "rate_limited") {
          this.providerHealth.set(pid, "healthy");
        }
        break;
      }

      // ── Plugins ───────────────────────────────────────────────────────────
      case "plugin:loaded": {
        const pid = e.pluginId as string;
        if (pid) this.pluginStatus.set(pid, "healthy");
        break;
      }
      case "plugin:crashed": {
        const pid = e.pluginId as string;
        if (pid) {
          this.pluginStatus.set(pid, "crashed");
          this.invalidateContextCacheAll();
        }
        break;
      }
      case "plugin:restarted": {
        const pid = e.pluginId as string;
        if (pid) this.pluginStatus.set(pid, "healthy");
        break;
      }
      case "plugin:stopped": {
        const pid = e.pluginId as string;
        if (pid) this.pluginStatus.set(pid, "stopped");
        break;
      }

      // ── Budget ────────────────────────────────────────────────────────────
      case "budget:tier_changed": {
        const pid = e.providerId as string;
        const newTier = e.newTier as string;
        if (pid && newTier) {
          this.budgetTiers.set(pid, newTier);
          if (newTier !== "normal") this.invalidateContextCacheAll();
        }
        break;
      }

      // ── Drones ────────────────────────────────────────────────────────────
      case "drone:spawned": {
        const did = e.droneId as string;
        if (did) this.activeDrones.add(did);
        break;
      }
      case "drone:completed":
      case "drone:failed":
      case "drone:cancelled":
      case "drone:timed_out": {
        const did = e.droneId as string;
        if (did) this.activeDrones.delete(did);
        break;
      }

      // ── Teams ─────────────────────────────────────────────────────────────
      case "team:started": {
        const tid = e.teamId as string;
        if (tid) this.activeTeams.add(tid);
        break;
      }
      case "team:completed":
      case "team:failed":
      case "team:cancelled": {
        const tid = e.teamId as string;
        if (tid) this.activeTeams.delete(tid);
        break;
      }
    }
  }

  // ─── Observation Integration ──────────────────────────────────────────────

  /** Add a heuristic observation to the model. */
  addObservation(obs: Observation): void {
    // Deduplication: skip if an identical summary was added within the last 2 minutes.
    // Prevents the same LLM sweep output from flooding the observation log when the
    // system is idle and no new events have occurred since the previous sweep.
    const deupWindowMs = 2 * 60 * 1000;
    const cutoff = Date.now() - deupWindowMs;
    const isDuplicate = this.observations
      .slice(-10)
      .some((o) => o.timestamp >= cutoff && o.summary === obs.summary);
    if (isDuplicate) return;

    this.observations.push(obs);
    if (this.observations.length > SystemModel.MAX_OBSERVATIONS) {
      this.observations.shift();
    }
    this.invalidateContextCacheAll();
  }

  /** Add a heuristic anomaly to the model. */
  addAnomaly(anomaly: Anomaly): void {
    // Annotate with the best cross-session ref if the index is available and the
    // anomaly doesn't already carry one. Synchronous — no latency impact.
    let annotated = anomaly;
    if (this.memory?.searchIndex && !anomaly.sessionRef) {
      try {
        const hits = this.memory.searchIndex(anomaly.description, { limit: 1 });
        if (hits.length > 0) {
          annotated = { ...anomaly, sessionRef: hits[0].entry.ref };
        }
      } catch {
        // Best-effort — silently skip if index is unavailable
      }
    }

    this.anomalies.push(annotated);
    if (this.anomalies.length > SystemModel.MAX_ANOMALIES) {
      this.anomalies.shift();
    }
    this.invalidateContextCacheAll();
  }

  /**
   * Integrate results from an LLM observer sweep.
   * Converts patterns → Observations and concerns → Anomalies.
   * Cross-session matches from the sweep are forwarded as sessionRef annotations.
   */
  addLLMObservation(llmObs: LLMObservation): void {
    // The sweep may have found historical context — attach the top ref so the
    // observation is citable and contextually grounded.
    const sessionRef = llmObs.crossSessionMatches?.[0]?.ref;

    // Main summary as an observation
    this.addObservation({
      id: llmObs.id,
      summary: llmObs.summary,
      patterns: llmObs.patterns,
      confidence: llmObs.confidence,
      source: "llm",
      relatedEventTypes: [],
      timestamp: llmObs.timestamp,
      sessionRef,
    });

    // Each concern becomes a low-severity anomaly
    for (const concern of llmObs.concerns) {
      this.addAnomaly({
        id: uuidv4(),
        description: concern,
        severity: "low",
        eventTypes: [],
        timestamp: llmObs.timestamp,
        sessionRef,
      });
    }
  }

  // ─── Context Injection ────────────────────────────────────────────────────

  /**
   * Build a context injection string for a session.
   * Surfaces active system issues, recent anomalies, and the latest LLM awareness.
   * Returns undefined if there is nothing significant to inject.
   */
  getContextInjection(sessionId: string): string | undefined {
    const cached = this.contextCache.get(sessionId);
    if (cached !== undefined) return cached || undefined;

    const parts: string[] = [];
    const now = Date.now();
    const recentCutoff = now - 5 * 60 * 1000; // last 5 minutes

    // System health problems
    const degraded = Array.from(this.providerHealth.entries())
      .filter(([, s]) => s !== "healthy")
      .map(([id, s]) => `${id}(${s})`);
    if (degraded.length > 0) {
      parts.push(`[System] Provider issues: ${degraded.join(", ")}`);
    }

    const crashed = Array.from(this.pluginStatus.entries())
      .filter(([, s]) => s === "crashed")
      .map(([id]) => id);
    if (crashed.length > 0) {
      parts.push(`[System] Crashed plugins: ${crashed.join(", ")}`);
    }

    const budgetWarnings = Array.from(this.budgetTiers.entries())
      .filter(([, t]) => t === "critical" || t === "frugal")
      .map(([id, t]) => `${id}(${t})`);
    if (budgetWarnings.length > 0) {
      parts.push(`[System] Budget warning: ${budgetWarnings.join(", ")}`);
    }

    // Recent high/medium anomalies
    const recentAnomalies = this.anomalies
      .filter((a) => a.timestamp >= recentCutoff && !a.acknowledged && (a.severity === "high" || a.severity === "medium"))
      .slice(-3);
    if (recentAnomalies.length > 0) {
      parts.push(`[Observations] ${recentAnomalies.map((a) => a.description).join("; ")}`);
    }

    // Latest LLM awareness summary
    const latestLLM = this.observations
      .filter((o) => o.source === "llm")
      .slice(-1)[0];
    if (latestLLM && latestLLM.timestamp >= recentCutoff) {
      parts.push(`[Awareness] ${latestLLM.summary}`);
    }

    // ── Cross-session historical context ──────────────────────────────────
    // When there is something noteworthy (anomalies or provider issues), search
    // the session index for similar historical moments and include the top refs.
    // This is synchronous and best-effort — silently skipped if unavailable.
    if (this.memory?.searchIndex && (recentAnomalies.length > 0 || degraded.length > 0)) {
      const query = recentAnomalies[0]?.description ?? degraded.join(" ");
      try {
        const hits = this.memory.searchIndex(query, { limit: 2 });
        if (hits.length > 0) {
          const refs = hits
            .map((h) => `${h.entry.ref}: "${h.entry.content.slice(0, 80).replace(/\s+/g, " ")}"`)
            .join("; ");
          parts.push(`[History] ${refs}`);
        }
      } catch {
        // Best-effort — never block context injection
      }
    }

    const result = parts.join("\n");
    this.contextCache.set(sessionId, result);
    return result || undefined;
  }

  // ─── Anomaly Management ───────────────────────────────────────────────────

  /** Acknowledge (dismiss) an anomaly by ID. Returns true if found. */
  acknowledgeAnomaly(anomalyId: string): boolean {
    const anomaly = this.anomalies.find((a) => a.id === anomalyId);
    if (anomaly) {
      anomaly.acknowledged = true;
      this.invalidateContextCacheAll();
      return true;
    }
    return false;
  }

  // ─── Queries ──────────────────────────────────────────────────────────────

  snapshot(): SystemModelSnapshot {
    const recentPatterns = this.observations
      .slice(-20)
      .flatMap((o) => o.patterns)
      .slice(-10);

    const systemHealth = this.computeSystemHealth();

    return {
      capturedAt: Date.now(),
      sessionCount: this.sessions.size,
      providerHealth: Object.fromEntries(this.providerHealth) as Record<string, ProviderHealthStatus>,
      pluginStatus: Object.fromEntries(this.pluginStatus) as Record<string, PluginHealthStatus>,
      budgetTiers: Object.fromEntries(this.budgetTiers),
      activeDrones: this.activeDrones.size,
      activeTeams: this.activeTeams.size,
      recentPatterns: [...new Set(recentPatterns)],
      observationCount: this.observations.length,
      systemHealth,
    };
  }

  private computeSystemHealth(): "healthy" | "degraded" | "critical" {
    const hasError = Array.from(this.providerHealth.values()).includes("error");
    const hasCrashed = Array.from(this.pluginStatus.values()).includes("crashed");
    const hasCriticalBudget = Array.from(this.budgetTiers.values()).includes("critical");

    if (hasError && hasCrashed) return "critical";
    if (hasError || hasCrashed || hasCriticalBudget) return "degraded";

    const hasDegraded = Array.from(this.providerHealth.values()).some(
      (s) => s === "degraded" || s === "rate_limited",
    );
    return hasDegraded ? "degraded" : "healthy";
  }

  getSession(sessionId: string): SessionState | undefined {
    return this.sessions.get(sessionId);
  }

  getSessionIds(): string[] {
    return Array.from(this.sessions.keys());
  }

  getRecentObservations(count = 20): Observation[] {
    return this.observations.slice(-count);
  }

  getAnomalies(includeAcknowledged = false): Anomaly[] {
    if (includeAcknowledged) return [...this.anomalies];
    return this.anomalies.filter((a) => !a.acknowledged);
  }

  // ─── Session Cleanup ──────────────────────────────────────────────────────

  cleanupSession(sessionId: string): void {
    this.sessions.delete(sessionId);
    this.contextCache.delete(sessionId);
  }

  /**
   * Reconcile the model against the live session manager state.
   *
   * Called once on daemon startup after the intelligence layer is connected to
   * the event bus. Fills in sessions (and optionally drones) that were created
   * before the Subconscious was wired and therefore never triggered a
   * `session:created` / `drone:spawned` event visible to the model.
   *
   * Only upserts — never removes existing model state so in-flight activity
   * observed from events is not disturbed.
   */
  reconcile(opts: {
    sessions?: Array<{ sessionId: string; startedAt: number; lastActivityAt?: number; turnCount?: number }>
    droneIds?: string[]
  }): void {
    let sessionsSynced = 0
    for (const s of opts.sessions ?? []) {
      if (!this.sessions.has(s.sessionId)) {
        this.sessions.set(s.sessionId, {
          sessionId:      s.sessionId,
          startedAt:      s.startedAt,
          lastActivityAt: s.lastActivityAt ?? s.startedAt,
          turnCount:      s.turnCount ?? 0,
          tokenCount:     0,
          phase:          'active',
          recentToolCalls: [],
        })
        sessionsSynced++
      }
    }

    let dronesSynced = 0
    for (const did of opts.droneIds ?? []) {
      if (!this.activeDrones.has(did)) {
        this.activeDrones.add(did)
        dronesSynced++
      }
    }

    if (sessionsSynced > 0 || dronesSynced > 0) {
      this.invalidateContextCacheAll()
      this.logger.info('SystemModel reconciled with live runtime state', {
        sessionsSynced, dronesSynced,
        totalSessions: this.sessions.size,
        totalDrones:   this.activeDrones.size,
      })
    }
  }

  // ─── Persistence ──────────────────────────────────────────────────────────

  /** Persist state to the memory KV store for cross-restart continuity. */
  async persist(): Promise<void> {
    if (!this.memory) return;
    try {
      await this.memory.kv_set("consciousness:anomalies", this.anomalies.slice(-50));
      await this.memory.kv_set(
        "consciousness:observations",
        this.observations.filter((o) => o.source === "llm").slice(-20),
      );
      this.logger.debug("SystemModel persisted");
    } catch (err) {
      this.logger.warn("SystemModel persist failed", { error: String(err) });
    }
  }

  /** Hydrate state from the memory KV store on startup. */
  async hydrate(): Promise<void> {
    if (!this.memory) return;
    try {
      const anomalies = await this.memory.kv_get<Anomaly[]>("consciousness:anomalies");
      if (Array.isArray(anomalies)) this.anomalies = anomalies;

      const observations = await this.memory.kv_get<Observation[]>("consciousness:observations");
      if (Array.isArray(observations)) this.observations = observations;

      this.logger.debug("SystemModel hydrated", {
        anomalies: this.anomalies.length,
        observations: this.observations.length,
      });
    } catch (err) {
      this.logger.warn("SystemModel hydrate failed", { error: String(err) });
    }
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────

  private invalidateContextCacheAll(): void {
    this.contextCache.clear();
  }
}
