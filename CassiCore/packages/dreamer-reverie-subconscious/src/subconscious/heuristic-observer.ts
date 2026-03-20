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
  { name: 'error-learner', prefix: 'error-learner:', silenceThresholdMs: 30 * 60_000 },
]

// Warm-up: don't fire heartbeat anomalies until the system has been running
// long enough for modules to emit at least one event.
const HEARTBEAT_WARMUP_MS  = 15 * 60_000  // 15 min
// Re-check interval: minimum time between consecutive heartbeat sweeps.
const HEARTBEAT_COOLDOWN_MS = 10 * 60_000  // 10 min

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

  private readonly errorBurstWindowMs = 30_000;    // 30s window for burst detection
  private readonly errorBurstThreshold = 3;         // N errors in window = burst
  private readonly crashCycleWindowMs = 120_000;   // 2min window for crash cycles
  private readonly crashCycleThreshold = 3;         // N crashes in window = cycle
  private readonly signalCooldownMs = 60_000;       // 1min between identical signals

  constructor(logger: ILogger) {
    this.logger = logger.child?.("heuristic-observer") ?? logger;
  }


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
      case "job:completed":
      case "job:failed":
      case "job:cancelled":
      case "job:timeout":
        this.onJobFinished(event as any);
        break;

      case "trust:score-updated":
        this.onTrustScoreUpdated(event as RuntimeEvent & { type: "trust:score-updated"; domain: string; oldScore: number; newScore: number; delta: number; reason: string });
        break;
      case "trust:decay-applied":
        this.onTrustDecayApplied(event as RuntimeEvent & { type: "trust:decay-applied"; domain: string; oldScore: number; newScore: number; decayFactor: number });
        break;
      case "trust:outcome-recorded":
        this.onTrustOutcomeRecorded(event as RuntimeEvent & { type: "trust:outcome-recorded"; domain: string; action: string; success: boolean; consequenceAccuracy: number });
        break;

      case "permission:escalated":
        this.onPermissionEscalated(event as RuntimeEvent & { type: "permission:escalated"; sessionId: string; toolName: string; reason: string; riskLevel: string });
        break;
      case "permission:decision":
        this.onPermissionDecision(event as RuntimeEvent & { type: "permission:decision"; sessionId: string; toolName: string; decision: string; riskScore: number });
        break;

      case "thinker:insight-applied":
      case "thinker:inject-insight":
        this.onThinkerInsight(event as RuntimeEvent & { type: string; insight: string; sessionId?: string });
        break;
      case "thinker:early-warning":
        this.onThinkerEarlyWarning(event as RuntimeEvent & { type: "thinker:early-warning"; warning: string; sessionId?: string });
        break;

      case "dialectic:signal":
        this.onDialecticSignal(event as RuntimeEvent & { type: "dialectic:signal"; signalType: string; content: string; confidence: number; sessionId?: string });
        break;
      case "dialectic:convergence":
        this.onDialecticConvergence(event as RuntimeEvent & { type: "dialectic:convergence"; converged: boolean; sessionId?: string });
        break;

      // Augment internal heartbeat tracking with direct module health status
      // from the intelligence loop. This is a richer signal than inferring
      // activity from event prefixes alone.
      case "intelligence:heartbeat":
        this.onIntelligenceHeartbeat(event as RuntimeEvent & { type: "intelligence:heartbeat"; moduleStatuses: Array<{ name: string; healthy: boolean; lastActivity?: number }> });
        break;
    }
  }


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


  private onJobFinished(event: { type: string; jobId: string; label: string; exitCode?: number; duration: number; summary: string }): void {
    const now = Date.now()
    const cooldownKey = `job:${event.jobId}`
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < 5000) return
    this.signalCooldowns.set(cooldownKey, now)

    const durationSec = (event.duration / 1000).toFixed(1)
    const isFailure = event.type === 'job:failed' || event.type === 'job:timeout'
    const statusLabel = event.type === 'job:completed' ? 'completed'
      : event.type === 'job:cancelled' ? 'cancelled'
      : event.type === 'job:timeout' ? 'timed out'
      : 'failed'

    if (isFailure) {
      this.pushAnomaly({
        id: uuidv4(),
        description: `Background job "${event.label}" ${statusLabel} after ${durationSec}s (exit ${event.exitCode ?? '?'}): ${event.summary.slice(0, 200)}`,
        severity: event.type === 'job:timeout' ? 'medium' : 'high',
        eventTypes: [event.type],
        suggestedAction: `Check job output for errors. Job ID: ${event.jobId}`,
        timestamp: now,
      })
    }

    // Always push an observation so the intelligence layer knows about job completion
    this.pushObservation({
      id: uuidv4(),
      summary: `Background job "${event.label}" ${statusLabel} in ${durationSec}s${event.exitCode !== undefined ? ` (exit ${event.exitCode})` : ''}: ${event.summary.slice(0, 150)}`,
      patterns: [`job_${statusLabel.replace(' ', '_')}`],
      confidence: 1.0,
      source: 'heuristic',
      relatedEventTypes: [event.type],
      timestamp: now,
    })
  }


  private onTrustScoreUpdated(event: RuntimeEvent & { type: "trust:score-updated"; domain: string; oldScore: number; newScore: number; delta: number; reason: string }): void {
    const now = Date.now()
    const drop = event.oldScore - event.newScore
    // Significant drop (>0.15) warrants an anomaly; smaller changes get an observation
    if (drop >= 0.15) {
      const cooldownKey = `trust:drop:${event.domain}`
      if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < this.signalCooldownMs) return
      this.signalCooldowns.set(cooldownKey, now)
      this.pushAnomaly({
        id: uuidv4(),
        description: `Trust score for '${event.domain}' dropped significantly: ${event.oldScore.toFixed(2)} → ${event.newScore.toFixed(2)} (Δ${event.delta.toFixed(2)}). Reason: ${event.reason}`,
        severity: drop >= 0.3 ? "high" : "medium",
        eventTypes: ["trust:score-updated"],
        suggestedAction: `Investigate recent actions in domain '${event.domain}' that may have caused trust erosion`,
        timestamp: now,
      })
    } else if (Math.abs(event.delta) >= 0.05) {
      const cooldownKey = `trust:change:${event.domain}`
      if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < this.signalCooldownMs * 2) return
      this.signalCooldowns.set(cooldownKey, now)
      const direction = event.delta >= 0 ? "improved" : "declined"
      this.pushObservation({
        id: uuidv4(),
        summary: `Trust score for '${event.domain}' ${direction}: ${event.oldScore.toFixed(2)} → ${event.newScore.toFixed(2)}. ${event.reason}`,
        patterns: [event.delta >= 0 ? "trust_improvement" : "trust_decline"],
        confidence: 0.9,
        source: "heuristic",
        relatedEventTypes: ["trust:score-updated"],
        timestamp: now,
      })
    }
  }

  private onTrustDecayApplied(event: RuntimeEvent & { type: "trust:decay-applied"; domain: string; oldScore: number; newScore: number; decayFactor: number }): void {
    // Only surface decay if it results in a meaningful drop — routine decay is noise
    const drop = event.oldScore - event.newScore
    if (drop < 0.1) return
    const now = Date.now()
    const cooldownKey = `trust:decay:${event.domain}`
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < 10 * 60_000) return
    this.signalCooldowns.set(cooldownKey, now)
    this.pushObservation({
      id: uuidv4(),
      summary: `Trust decay applied to '${event.domain}': ${event.oldScore.toFixed(2)} → ${event.newScore.toFixed(2)} (factor ${event.decayFactor.toFixed(3)})`,
      patterns: ["trust_decay"],
      confidence: 1.0,
      source: "heuristic",
      relatedEventTypes: ["trust:decay-applied"],
      timestamp: now,
    })
  }

  private onTrustOutcomeRecorded(event: RuntimeEvent & { type: "trust:outcome-recorded"; domain: string; action: string; success: boolean; consequenceAccuracy: number }): void {
    // Only surface notable outcomes: failures or poor consequence accuracy
    if (event.success && event.consequenceAccuracy >= 0.7) return
    const now = Date.now()
    const cooldownKey = `trust:outcome:${event.domain}`
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < this.signalCooldownMs) return
    this.signalCooldowns.set(cooldownKey, now)
    const issue = !event.success
      ? `action failed`
      : `consequence prediction accuracy low (${(event.consequenceAccuracy * 100).toFixed(0)}%)`
    this.pushObservation({
      id: uuidv4(),
      summary: `Trust outcome in '${event.domain}': ${issue} — action: ${event.action.slice(0, 80)}`,
      patterns: ["trust_outcome_issue"],
      confidence: 0.85,
      source: "heuristic",
      relatedEventTypes: ["trust:outcome-recorded"],
      timestamp: now,
    })
  }


  private onPermissionEscalated(event: RuntimeEvent & { type: "permission:escalated"; sessionId: string; toolName: string; reason: string; riskLevel: string }): void {
    const now = Date.now()
    const cooldownKey = `permission:escalated:${event.toolName}`
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < this.signalCooldownMs) return
    this.signalCooldowns.set(cooldownKey, now)
    this.pushAnomaly({
      id: uuidv4(),
      description: `Permission escalated for '${event.toolName}' [risk: ${event.riskLevel}]: ${event.reason}`,
      severity: event.riskLevel === "critical" || event.riskLevel === "high" ? "high" : "medium",
      eventTypes: ["permission:escalated"],
      suggestedAction: `Review tool '${event.toolName}' permission policy and risk profile`,
      timestamp: now,
    })
  }

  private onPermissionDecision(event: RuntimeEvent & { type: "permission:decision"; sessionId: string; toolName: string; decision: string; riskScore: number }): void {
    // Only observe denials and high-risk allows — routine allows are noise
    if (event.decision === "allow" && event.riskScore < 0.7) return
    const now = Date.now()
    const cooldownKey = `permission:decision:${event.toolName}:${event.decision}`
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < this.signalCooldownMs) return
    this.signalCooldowns.set(cooldownKey, now)
    const label = event.decision === "deny"
      ? `denied (risk ${event.riskScore.toFixed(2)})`
      : `allowed at elevated risk (${event.riskScore.toFixed(2)})`
    this.pushObservation({
      id: uuidv4(),
      summary: `Permission ${label} for '${event.toolName}'`,
      patterns: [event.decision === "deny" ? "permission_denied" : "high_risk_permission_allowed"],
      confidence: 0.95,
      source: "heuristic",
      relatedEventTypes: ["permission:decision"],
      timestamp: now,
      sessionId: event.sessionId,
    })
  }


  private onThinkerInsight(event: RuntimeEvent & { type: string; insight: string; sessionId?: string }): void {
    // Surface Thinker insights as observations so the Subconscious knows what
    // the Thinker decided — closes the one-way gap (was: Subconscious→Thinker only)
    const now = Date.now()
    const cooldownKey = `thinker:insight`
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < 30_000) return
    this.signalCooldowns.set(cooldownKey, now)
    this.pushObservation({
      id: uuidv4(),
      summary: `Thinker insight applied: ${event.insight.slice(0, 200)}`,
      patterns: ["thinker_insight"],
      confidence: 0.9,
      source: "heuristic",
      relatedEventTypes: [event.type],
      timestamp: now,
      sessionId: event.sessionId,
    })
  }

  private onThinkerEarlyWarning(event: RuntimeEvent & { type: "thinker:early-warning"; warning: string; sessionId?: string }): void {
    const now = Date.now()
    // Early warnings are important — surface immediately as anomalies
    this.pushAnomaly({
      id: uuidv4(),
      description: `Thinker early warning: ${event.warning.slice(0, 300)}`,
      severity: "medium",
      eventTypes: ["thinker:early-warning"],
      suggestedAction: "Review Thinker warning and consider preemptive action",
      timestamp: now,
    })
  }


  private onDialecticSignal(event: RuntimeEvent & { type: "dialectic:signal"; signalType: string; content: string; confidence: number; sessionId?: string }): void {
    // High-confidence dialectic signals are meaningful cognitive outputs — track them
    if (event.confidence < 0.6) return
    const now = Date.now()
    const cooldownKey = `dialectic:signal:${event.signalType}`
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < 20_000) return
    this.signalCooldowns.set(cooldownKey, now)
    this.pushObservation({
      id: uuidv4(),
      summary: `Dialectic signal [${event.signalType}, confidence ${(event.confidence * 100).toFixed(0)}%]: ${event.content.slice(0, 200)}`,
      patterns: ["dialectic_signal", `dialectic_${event.signalType}`],
      confidence: event.confidence,
      source: "heuristic",
      relatedEventTypes: ["dialectic:signal"],
      timestamp: now,
      sessionId: event.sessionId,
    })
  }

  private onDialecticConvergence(event: RuntimeEvent & { type: "dialectic:convergence"; converged: boolean; sessionId?: string }): void {
    // Only note convergence, not divergence — divergence is the normal state
    if (!event.converged) return
    const now = Date.now()
    const cooldownKey = `dialectic:convergence`
    if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < 15_000) return
    this.signalCooldowns.set(cooldownKey, now)
    this.pushObservation({
      id: uuidv4(),
      summary: "Dialectic converged — Yang/Yin reached agreement",
      patterns: ["dialectic_convergence"],
      confidence: 0.85,
      source: "heuristic",
      relatedEventTypes: ["dialectic:convergence"],
      timestamp: now,
      sessionId: event.sessionId,
    })
  }


  private onIntelligenceHeartbeat(event: RuntimeEvent & { type: "intelligence:heartbeat"; moduleStatuses: Array<{ name: string; healthy: boolean; lastActivity?: number }> }): void {
    const now = Date.now()
    // Sync module last-seen timestamps from the heartbeat's authoritative data.
    // This augments the prefix-based tracking in updateModuleHeartbeat() — the
    // intelligence loop has direct visibility that we don't.
    for (const status of event.moduleStatuses) {
      const lastActivity = status.lastActivity ?? (status.healthy ? now : undefined)
      if (lastActivity !== undefined) {
        const current = this.moduleLastSeen.get(status.name)
        if (current === undefined || lastActivity > current) {
          this.moduleLastSeen.set(status.name, lastActivity)
        }
      }

      // Unhealthy module that checkHeartbeats() wouldn't catch (e.g. not in HEARTBEAT_MODULES)
      if (!status.healthy) {
        const cooldownKey = `heartbeat:unhealthy:${status.name}`
        if (now - (this.signalCooldowns.get(cooldownKey) ?? 0) < 5 * 60_000) continue
        this.signalCooldowns.set(cooldownKey, now)
        this.pushAnomaly({
          id: uuidv4(),
          description: `Intelligence heartbeat reports module '${status.name}' as unhealthy`,
          severity: "medium",
          eventTypes: ["intelligence:heartbeat"],
          suggestedAction: `Check module '${status.name}' status and logs`,
          timestamp: now,
        })
      }
    }
  }

  private getOrCreate(map: Map<string, ErrorBurstTracker>, key: string): ErrorBurstTracker {    let tracker = map.get(key);
    if (!tracker) {
      tracker = { errors: [], lastAlerted: 0 };
      map.set(key, tracker);
    }
    return tracker;
  }
}
