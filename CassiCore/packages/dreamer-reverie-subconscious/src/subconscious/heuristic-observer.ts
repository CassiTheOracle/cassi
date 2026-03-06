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
 * - Silent intelligence modules (heartbeat monitor)
 * - Tool/agent registration bursts (coalesced into a single observation)
 *
 * All detections respect a per-signal-type cooldown to avoid flooding.
 */

import { v4 as uuidv4 } from "uuid";

import type { Observation, Anomaly } from "./types.js";
import type { RuntimeEvent } from "../../../types/events.js";
import type { ILogger } from "../../../types/interfaces.js";


interface ErrorBurstTracker {
  errors: number[];    // timestamps
  lastAlerted: number;
}

// ─── Heartbeat config ──────────────────────────────────────────────────────
// Modules to monitor, their expected event-type prefix, and the max silence
// window before an anomaly is raised.  Only modules that should emit events
// when the system is active are listed here — passive/on-demand modules are
// intentionally excluded (e.g. self-healer, multi-agent).
const HEARTBEAT_MODULES: ReadonlyArray<{
  name: string
  prefix: string
  silenceThresholdMs: number
}> = [
  { name: 'thinker',    prefix: 'thinker:',    silenceThresholdMs: 30 * 60_000 },
  { name: 'dialectic',  prefix: 'dialectic:',  silenceThresholdMs: 20 * 60_000 },
  { name: 'optimizer',  prefix: 'optimizer:',  silenceThresholdMs: 30 * 60_000 },
  { name: 'reflect',    prefix: 'reflect:',    silenceThresholdMs: 30 * 60_000 },
]

// Warm-up: don't fire heartbeat anomalies until the system has been running
// long enough for modules to emit at least one event.
const HEARTBEAT_WARMUP_MS  = 15 * 60_000  // 15 min
// Re-check interval: minimum time between consecutive heartbeat sweeps.
const HEARTBEAT_COOLDOWN_MS = 10 * 60_000  // 10 min

// ─── Tool registration burst config ───────────────────────────────────────
// Many tools are registered in rapid succession at startup (MCP servers,
// built-ins). Rather than letting this appear as noisy individual signals,
// we coalesce them into a single summary observation.
const TOOL_BURST_WINDOW_MS = 5_000   // group registrations within 5s
const TOOL_BURST_THRESHOLD = 3       // more than N in the window → summarise

export class HeuristicObserver {
  private readonly logger: ILogger;
  private readonly startedAt = Date.now();

  // Provider error tracking
  private readonly providerErrors = new Map<string, ErrorBurstTracker>();
  // Provider rate-limit tracking (active rate-limited providers)
  private readonly rateLimitedProviders = new Set<string>();
  // Plugin crash tracking
  private readonly pluginCrashes = new Map<string, ErrorBurstTracker>();

  // Per-signal-type cooldown (signal key → last-emitted timestamp)
  private readonly signalCooldowns = new Map<string, number>();

  // Turn activity tracking — generates periodic observations about session health
  private turnTimestamps: number[] = [];
  private readonly turnActivityWindowMs = 300_000;   // 5min window
  private readonly turnActivityCheckInterval = 10;    // check every N turns
  private turnsSinceLastCheck = 0;

  // Heartbeat tracking — last time each monitored module emitted any event
  private readonly moduleLastSeen = new Map<string, number>();

  // Tool registration burst tracking
  private toolRegistrationTimestamps: number[] = [];
  private toolRegistrationTimer?: ReturnType<typeof setTimeout>;
  private toolRegistrationNames: string[] = [];

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
      this.updateModuleHeartbeat(event.type);
      this.dispatch(event);
    } catch (err) {
      this.logger.warn("HeuristicObserver.observe error", { type: event.type, error: String(err) });
    }
  }

  /**
   * Periodic heartbeat sweep — call every ~10 minutes from the Subconscious
   * lifecycle timer. Generates anomalies for modules that have been silent
   * longer than their configured threshold.
   *
   * Only fires after the initial warm-up period to avoid false positives at
   * startup before modules have had a chance to emit their first event.
   */
  checkHeartbeats(now = Date.now()): void {
    if (now - this.startedAt < HEARTBEAT_WARMUP_MS) return

    const cooldownKey = "heartbeat:sweep"
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < HEARTBEAT_COOLDOWN_MS) return
    this.signalCooldowns.set(cooldownKey, now)

    for (const mod of HEARTBEAT_MODULES) {
      const lastSeen = this.moduleLastSeen.get(mod.name)
      const silenceMs = now - (lastSeen ?? this.startedAt)

      if (silenceMs > mod.silenceThresholdMs) {
        const silenceMin = Math.round(silenceMs / 60_000)
        const cooldownKey2 = `heartbeat:${mod.name}`
        // Allow re-alerting every 30 minutes per module
        if (now - (this.signalCooldowns.get(cooldownKey2) ?? 0) < 30 * 60_000) continue
        this.signalCooldowns.set(cooldownKey2, now)

        this.pushAnomaly({
          id: uuidv4(),
          description: `Module '${mod.name}' has been silent for ${silenceMin} min — no '${mod.prefix}*' events observed`,
          severity: "low",
          eventTypes: [`${mod.prefix}*`],
          suggestedAction: `Verify that the ${mod.name} module is running and connected to the event bus`,
          timestamp: now,
        })
      }
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
      case "turn:end":
        this.onTurnEnd(event);
        break;
      case "tool:registered":
        this.onToolRegistered(event as RuntimeEvent & { type: "tool:registered"; name: string; server?: string });
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

  /**
   * Track turn activity — generates periodic observations about session throughput,
   * giving the subconscious a baseline awareness of activity patterns.
   */
  private onTurnEnd(event: RuntimeEvent): void {
    const now = Date.now();
    this.turnTimestamps.push(now);
    // Trim to window
    this.turnTimestamps = this.turnTimestamps.filter((t) => t >= now - this.turnActivityWindowMs);
    this.turnsSinceLastCheck += 1;

    if (this.turnsSinceLastCheck < this.turnActivityCheckInterval) return;
    this.turnsSinceLastCheck = 0;

    const cooldownKey = "turn:activity";
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) <= this.signalCooldownMs * 5) return;
    this.signalCooldowns.set(cooldownKey, now);

    const turnsInWindow = this.turnTimestamps.length;
    const windowMinutes = this.turnActivityWindowMs / 60_000;
    const rate = turnsInWindow / windowMinutes;

    const patterns: string[] = ["turn_activity"];
    let confidence = 0.6;

    // Detect unusual activity patterns
    if (rate > 20) {
      patterns.push("high_turn_rate");
      confidence = 0.85;
    } else if (rate < 0.5 && turnsInWindow > 0) {
      patterns.push("low_turn_rate");
      confidence = 0.7;
    }

    const sessionId = (event as any).sessionId;
    this.pushObservation({
      id: uuidv4(),
      summary: `Session activity: ${turnsInWindow} turns in last ${windowMinutes}min (${rate.toFixed(1)}/min)${sessionId ? ` [${sessionId.slice(-8)}]` : ""}`,
      patterns,
      confidence,
      source: "heuristic",
      relatedEventTypes: ["turn:end"],
      timestamp: now,
      sessionId,
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

  /**
   * Update the last-seen timestamp for any monitored module whose event prefix
   * matches the given event type. Called for every observed event.
   */
  private updateModuleHeartbeat(eventType: string): void {
    for (const mod of HEARTBEAT_MODULES) {
      if (eventType.startsWith(mod.prefix)) {
        this.moduleLastSeen.set(mod.name, Date.now())
        break
      }
    }
  }

  /**
   * Coalesce rapid tool:registered events (startup burst) into a single
   * informational observation. Individual registrations are not surfaced
   * as anomalies; only the summary is emitted after the burst window closes.
   */
  private onToolRegistered(event: RuntimeEvent & { type: "tool:registered"; name: string; server?: string }): void {
    const now = Date.now()
    this.toolRegistrationTimestamps.push(now)
    this.toolRegistrationNames.push(event.name)

    // Clear any pending flush timer and reschedule
    if (this.toolRegistrationTimer) {
      clearTimeout(this.toolRegistrationTimer)
    }

    this.toolRegistrationTimer = setTimeout(() => {
      this.toolRegistrationTimer = undefined
      const count = this.toolRegistrationTimestamps.length
      const names = this.toolRegistrationNames.splice(0)
      this.toolRegistrationTimestamps = []

      if (count < TOOL_BURST_THRESHOLD) return  // too few to report

      const servers = [...new Set(names.map(n => n.includes('__') ? n.split('__')[0] : 'built-in'))]
      this.pushObservation({
        id: uuidv4(),
        summary: `${count} tool(s) registered at startup from: ${servers.join(', ')}`,
        patterns: ["tool_registration_burst"],
        confidence: 1.0,
        source: "heuristic",
        relatedEventTypes: ["tool:registered"],
        timestamp: now,
      })
    }, TOOL_BURST_WINDOW_MS)
  }

  private getOrCreate(map: Map<string, ErrorBurstTracker>, key: string): ErrorBurstTracker {
    let tracker = map.get(key);
    if (!tracker) {
      tracker = { errors: [], lastAlerted: 0 };
      map.set(key, tracker);
    }
    return tracker;
  }
}
