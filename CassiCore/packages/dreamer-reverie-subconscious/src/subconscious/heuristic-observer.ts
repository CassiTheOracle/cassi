/**
 * HeuristicObserver — Real-time pattern detection on the full event stream.
 *
 * Processes every event as it arrives (synchronously, zero LLM cost) and
 * emits Observations and Anomalies when known patterns are detected.
 *
 * Detects:
 * - Provider error bursts and rate-limit cascades
 * - Plugin crash cycles
 * - Budget pressure (approaching limits)
 * - Drone swarm / team failures
 * - Autonomy agent blocks
 * - Config hot-reload events
 *
 * All detections respect a per-signal-type cooldown to avoid flooding.
 */

import type { ILogger } from "../../../types/interfaces.js";
import type { RuntimeEvent } from "../../../types/events.js";
import type { Observation, Anomaly } from "./types.js";
import { v4 as uuidv4 } from "uuid";

interface ErrorBurstTracker {
  errors: number[];    // timestamps
  lastAlerted: number;
}

export class HeuristicObserver {
  private readonly logger: ILogger;

  // Provider error tracking
  private readonly providerErrors = new Map<string, ErrorBurstTracker>();
  // Provider rate-limit tracking (active rate-limited providers)
  private readonly rateLimitedProviders = new Set<string>();
  // Plugin crash tracking
  private readonly pluginCrashes = new Map<string, ErrorBurstTracker>();

  // Per-signal-type cooldown (signal key → last-emitted timestamp)
  private readonly signalCooldowns = new Map<string, number>();

  // Pending buffers drained by the Subconscious on each turn
  private pendingObservations: Observation[] = [];
  private pendingAnomalies: Anomaly[] = [];

  // ─── Config ─────────────────────────────────────────────────────────────────
  private readonly errorBurstWindowMs = 30_000;    // 30s window for burst detection
  private readonly errorBurstThreshold = 3;         // N errors in window = burst
  private readonly crashCycleWindowMs = 120_000;   // 2min window for crash cycles
  private readonly crashCycleThreshold = 3;         // N crashes in window = cycle
  private readonly signalCooldownMs = 60_000;       // 1min between identical signals

  constructor(logger: ILogger) {
    this.logger = logger.child?.("heuristic-observer") ?? logger;
  }

  // ─── Main Entry Point ──────────────────────────────────────────────────────

  /**
   * Process a single event. Called synchronously for every event ingested
   * by the EventStream. Must never throw — errors are caught internally.
   */
  observe(event: RuntimeEvent): void {
    try {
      this.dispatch(event);
    } catch (err) {
      this.logger.warn("HeuristicObserver.observe error", { type: event.type, error: String(err) });
    }
  }

  private dispatch(event: RuntimeEvent): void {
    switch (event.type) {
      case "provider:request_error":
        this.onProviderError(event as RuntimeEvent & { type: "provider:request_error"; providerId: string; consecutiveErrors?: number });
        break;
      case "provider:rate_limited":
        this.onRateLimited(event as RuntimeEvent & { type: "provider:rate_limited"; providerId: string; retryAfterMs: number });
        break;
      case "provider:error_reset":
        this.onProviderErrorReset(event as RuntimeEvent & { type: "provider:error_reset"; providerId: string });
        break;
      case "provider:request_end":
        this.onProviderRequestEnd(event as RuntimeEvent & { type: "provider:request_end"; providerId: string });
        break;
      case "plugin:crashed":
        this.onPluginCrashed(event as RuntimeEvent & { type: "plugin:crashed"; pluginId: string; error?: string });
        break;
      case "budget:warning":
        this.onBudgetWarning(event as RuntimeEvent & { type: "budget:warning"; tier: string; percentUsed: number; remaining: number; providerId?: string });
        break;
      case "budget:tier_changed":
        this.onBudgetTierChanged(event as RuntimeEvent & { type: "budget:tier_changed"; providerId: string; newTier: string; oldTier: string });
        break;
      case "config:reloaded":
        this.onConfigReloaded();
        break;
      case "autonomy:blocked":
        this.onAutonomyBlocked(event as RuntimeEvent & { type: "autonomy:blocked"; agentId?: string; reason?: string });
        break;
    }
  }

  // ─── Pattern Handlers ──────────────────────────────────────────────────────

  private onProviderError(event: RuntimeEvent & { type: "provider:request_error"; providerId: string; consecutiveErrors?: number }): void {
    const tracker = this.getOrCreate(this.providerErrors, event.providerId);
    const now = Date.now();
    tracker.errors.push(now);
    // Expire old errors outside the burst window
    tracker.errors = tracker.errors.filter((t) => t >= now - this.errorBurstWindowMs);

    if (
      tracker.errors.length >= this.errorBurstThreshold &&
      now - tracker.lastAlerted > this.signalCooldownMs
    ) {
      tracker.lastAlerted = now;
      this.pushAnomaly({
        id: uuidv4(),
        description: `Provider ${event.providerId} has ${tracker.errors.length} errors in the last ${this.errorBurstWindowMs / 1000}s`,
        severity: tracker.errors.length >= 5 ? "high" : "medium",
        eventTypes: ["provider:request_error"],
        suggestedAction: "Check provider health and rate limits",
        timestamp: now,
      });
    }
  }

  private onRateLimited(event: RuntimeEvent & { type: "provider:rate_limited"; providerId: string; retryAfterMs: number }): void {
    this.rateLimitedProviders.add(event.providerId);
    // Auto-clear after retry window
    setTimeout(() => this.rateLimitedProviders.delete(event.providerId), event.retryAfterMs + 5000);

    const cooldownKey = `rate_limited:${event.providerId}`;
    const now = Date.now();
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) > this.signalCooldownMs) {
      this.signalCooldowns.set(cooldownKey, now);
      this.pushObservation({
        id: uuidv4(),
        summary: `Provider ${event.providerId} rate-limited — retry in ${Math.round(event.retryAfterMs / 1000)}s`,
        patterns: ["provider_rate_limited"],
        confidence: 1.0,
        source: "heuristic",
        relatedEventTypes: ["provider:rate_limited"],
        timestamp: now,
      });
    }
  }

  private onProviderErrorReset(event: RuntimeEvent & { type: "provider:error_reset"; providerId: string }): void {
    const tracker = this.providerErrors.get(event.providerId);
    if (tracker) tracker.errors = [];
  }

  private onProviderRequestEnd(event: RuntimeEvent & { type: "provider:request_end"; providerId: string }): void {
    // Provider successfully responded — ensure it is no longer error-flagged
    // (do not touch rate_limited state, that clears on its own timer)
    if (!this.rateLimitedProviders.has(event.providerId)) {
      const tracker = this.providerErrors.get(event.providerId);
      if (tracker) {
        const now = Date.now();
        // Remove errors older than the burst window — success means the storm is over
        tracker.errors = tracker.errors.filter((t) => t >= now - this.errorBurstWindowMs);
      }
    }
  }

  private onPluginCrashed(event: RuntimeEvent & { type: "plugin:crashed"; pluginId: string; error?: string }): void {
    const tracker = this.getOrCreate(this.pluginCrashes, event.pluginId);
    const now = Date.now();
    tracker.errors.push(now);
    tracker.errors = tracker.errors.filter((t) => t >= now - this.crashCycleWindowMs);

    if (
      tracker.errors.length >= this.crashCycleThreshold &&
      now - tracker.lastAlerted > this.signalCooldownMs
    ) {
      tracker.lastAlerted = now;
      this.pushAnomaly({
        id: uuidv4(),
        description: `Plugin ${event.pluginId} crash-cycling: ${tracker.errors.length} crashes in ${this.crashCycleWindowMs / 1000}s`,
        severity: "high",
        eventTypes: ["plugin:crashed"],
        suggestedAction: `Investigate plugin ${event.pluginId} — may require restart or removal`,
        timestamp: now,
      });
    }
  }

  private onBudgetWarning(event: RuntimeEvent & { type: "budget:warning"; tier: string; percentUsed: number; remaining: number; providerId?: string }): void {
    const cooldownKey = `budget:warning:${event.providerId ?? "global"}`;
    const now = Date.now();
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) <= this.signalCooldownMs) return;
    this.signalCooldowns.set(cooldownKey, now);

    const severity = event.tier === "critical" ? "high" : event.tier === "frugal" ? "medium" : "low";
    this.pushAnomaly({
      id: uuidv4(),
      description: `Budget ${event.tier}: ${event.percentUsed.toFixed(1)}% used (${event.remaining} tokens remaining)${event.providerId ? ` [${event.providerId}]` : ""}`,
      severity,
      eventTypes: ["budget:warning"],
      suggestedAction: event.tier === "critical" ? "Reduce token usage immediately" : undefined,
      timestamp: now,
    });
  }

  private onBudgetTierChanged(event: RuntimeEvent & { type: "budget:tier_changed"; providerId: string; newTier: string; oldTier: string }): void {
    if (event.newTier === "normal" && event.oldTier !== "normal") {
      // Budget recovered — positive signal
      this.pushObservation({
        id: uuidv4(),
        summary: `Provider ${event.providerId} budget recovered to normal tier`,
        patterns: ["budget_recovery"],
        confidence: 1.0,
        source: "heuristic",
        relatedEventTypes: ["budget:tier_changed"],
        timestamp: Date.now(),
      });
    }
  }

  private onConfigReloaded(): void {
    const cooldownKey = "config:reloaded";
    const now = Date.now();
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) <= this.signalCooldownMs) return;
    this.signalCooldowns.set(cooldownKey, now);

    this.pushObservation({
      id: uuidv4(),
      summary: "System configuration hot-reloaded",
      patterns: ["config_reloaded"],
      confidence: 1.0,
      source: "heuristic",
      relatedEventTypes: ["config:reloaded"],
      timestamp: now,
    });
  }

  private onAutonomyBlocked(event: RuntimeEvent & { type: "autonomy:blocked"; agentId?: string; reason?: string }): void {
    const agentId = event.agentId ?? "unknown";
    const cooldownKey = `autonomy:blocked:${agentId}`;
    const now = Date.now();
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) <= this.signalCooldownMs) return;
    this.signalCooldowns.set(cooldownKey, now);

    this.pushObservation({
      id: uuidv4(),
      summary: `Autonomy agent ${agentId} blocked${event.reason ? `: ${event.reason}` : ""}`,
      patterns: ["autonomy_blocked"],
      confidence: 1.0,
      source: "heuristic",
      relatedEventTypes: ["autonomy:blocked"],
      timestamp: now,
    });
  }

  // ─── Buffer Management ────────────────────────────────────────────────────

  private pushObservation(obs: Observation): void {
    this.pendingObservations.push(obs);
  }

  private pushAnomaly(anomaly: Anomaly): void {
    this.logger.debug("HeuristicObserver anomaly detected", { description: anomaly.description, severity: anomaly.severity });
    this.pendingAnomalies.push(anomaly);
  }

  /** Drain pending observations and return them (clears the buffer). */
  drainObservations(): Observation[] {
    const obs = this.pendingObservations;
    this.pendingObservations = [];
    return obs;
  }

  /** Drain pending anomalies and return them (clears the buffer). */
  drainAnomalies(): Anomaly[] {
    const anomalies = this.pendingAnomalies;
    this.pendingAnomalies = [];
    return anomalies;
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────

  private getOrCreate(map: Map<string, ErrorBurstTracker>, key: string): ErrorBurstTracker {
    let tracker = map.get(key);
    if (!tracker) {
      tracker = { errors: [], lastAlerted: 0 };
      map.set(key, tracker);
    }
    return tracker;
  }
}
