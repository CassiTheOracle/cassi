/**
 * LLMObserver — Periodic "inner observer" sweep of the event stream.
 *
 * Runs on a configurable interval (default: every 30s). Receives a structured
 * summary of recent system events from the EventStream, then asks an LLM:
 * "What patterns, risks, or opportunities do you see that heuristics might miss?"
 *
 * The metaphor: the heuristic observer is reflexive awareness; this is
 * self-reflective awareness — the system watching itself think.
 *
 * Design constraints:
 * - Uses the fast/cheap model (MODEL_DEFAULTS.fast) — not the reasoning model
 * - Non-blocking: failures are swallowed and logged, never surface to the main path
 * - JSON-structured output: summary, patterns, concerns, opportunities, confidence
 * - Gracefully degrades when no provider is available (skips sweep)
 */

import { v4 as uuidv4 } from "uuid";

import { MODEL_DEFAULTS } from "../../config/system-settings.js";

import type { EventStream } from "./event-stream.js";
import type { SystemModel } from "./system-model.js";
import type { LLMObservation, LLMObserverConfig, StreamSummary } from "./types.js";
import type { IMemory } from "../../../types/intelligence.js";
import type { ILogger } from "../../../types/interfaces.js";
import type { IProvider, Message } from "../../../types/runtime.js";



export class LLMObserver {
  private readonly logger: ILogger;
  private readonly config: Required<LLMObserverConfig>;
  private provider?: IProvider;
  /** Session indexer memory — used to fetch cross-session historical context */
  private memory?: IMemory;

  private timer?: NodeJS.Timeout;
  private lastSweepAt = 0;
  private sweepInProgress = false;
  /** Event count at last completed sweep — used to skip no-op sweeps */
  private lastSweepEventCount = 0;
  /** Stream reference from last sweep — skip optimization only applies to the same stream */
  private lastSweepStream?: EventStream;

  private readonly observationHistory: LLMObservation[] = [];
  private static readonly MAX_HISTORY = 50;

  constructor(logger: ILogger, config?: Partial<LLMObserverConfig>) {
    this.logger = logger.child?.("llm-observer") ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      intervalMs: config?.intervalMs ?? 30_000,
      windowMs: config?.windowMs ?? 60_000,
      maxRetries: config?.maxRetries ?? 2,
      model: config?.model ?? MODEL_DEFAULTS.fast.model,
    };
  }

  // ─── Lifecycle ─────────────────────────────────────────────────────────────

  setProvider(provider: IProvider): void {
    this.provider = provider;
  }

  /**
   * Wire the memory module so the LLM observer can pull cross-session
   * historical context into each sweep prompt. Call this after construction.
   */
  setMemory(memory: IMemory): void {
    this.memory = memory;
  }

  start(stream: EventStream, systemModel: SystemModel): void {
    if (!this.config.enabled) {
      this.logger.debug("LLMObserver disabled — skipping start");
      return;
    }
    this.stop();
    this.timer = setInterval(() => {
      // Fire-and-forget: sweep errors are handled internally.
      // Feed successful observations back into the system model so they
      // appear as observations/anomalies in the Subconscious stats.
      void this.sweep(stream, systemModel).then((obs) => {
        if (obs) {
          systemModel.addLLMObservation(obs);
        }
      });
    }, this.config.intervalMs);
    this.logger.debug("LLMObserver started", { intervalMs: this.config.intervalMs });
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
  }

  // ─── Sweep ─────────────────────────────────────────────────────────────────

  /**
   * Run one observer sweep. Returns the LLMObservation or null if skipped/failed.
   * Public so the Subconscious can trigger a manual sweep (e.g. at turn start).
   */
  async sweep(stream: EventStream, systemModel: SystemModel): Promise<LLMObservation | null> {
    if (!this.provider) {
      this.logger.debug("LLMObserver: no provider configured, skipping sweep");
      return null;
    }
    if (this.sweepInProgress) {
      this.logger.debug("LLMObserver: previous sweep still in progress, skipping");
      return null;
    }

    const summary = stream.summarize(this.config.windowMs);
    if (summary.totalEvents === 0) {
      return null; // Nothing to observe
    }

    // Skip sweep if the event stream hasn't changed since last sweep.
    // This prevents redundant LLM calls and disk writes when the system is
    // generating only internal housekeeping events (heartbeats, budget warnings).
    // Only applies when watching the same stream (normal daemon loop).
    const currentTotal = stream.totalCount;
    if (stream === this.lastSweepStream && currentTotal === this.lastSweepEventCount && this.lastSweepAt > 0) {
      this.logger.debug("LLMObserver: no new events since last sweep, skipping");
      return null;
    }

    this.sweepInProgress = true;
    this.lastSweepAt = Date.now();

    try {
      // ── Cross-session historical context ──────────────────────────────────
      // Build a query from the most active event types and search the session
      // index for similar moments in past sessions. The top matches are
      // threaded into the LLM prompt so the observer can reference history.
      const crossSessionMatches: Array<{ ref: string; snippet: string; score: number }> = [];
      if (this.memory?.searchIndex && summary.topTypes.length > 0) {
        const query = summary.topTypes
          .slice(0, 3)
          .map((t) => t.type)
          .join(" ");
        try {
          const hits = this.memory.searchIndex(query, { limit: 3 });
          for (const hit of hits) {
            crossSessionMatches.push({
              ref: hit.entry.ref,
              snippet: hit.entry.content.slice(0, 120).replace(/\s+/g, " "),
              score: hit.rank,
            });
          }
        } catch (err) {
          this.logger.debug("LLMObserver: cross-session search failed", { error: String(err) });
        }
      }

      const prompt = this.buildPrompt(summary, systemModel, crossSessionMatches);
      const messages: Message[] = [{ role: "user", content: prompt }];
      const model = this.config.model;

      let rawResponse = "";
      let attempt = 0;

      while (attempt <= this.config.maxRetries) {
        attempt++;
        try {
          // Use streaming if available, fall back to non-streaming
          const result = await (this.provider as unknown as {
            complete(msgs: Message[], opts: Record<string, unknown>): Promise<AsyncIterable<unknown> | { content?: string; text?: string }>;
          }).complete(messages, {
            model,
            stream: true,
            maxTokens: 500,
            temperature: 0.3,
          });

          if (result && Symbol.asyncIterator in Object(result)) {
            const chunks: string[] = [];
            for await (const chunk of result as AsyncIterable<Record<string, unknown>>) {
              const delta = (chunk as { choices?: Array<{ delta?: { content?: string } }> })
                ?.choices?.[0]?.delta?.content
                ?? (chunk as { text?: string })?.text
                ?? "";
              if (delta) chunks.push(delta);
            }
            rawResponse = chunks.join("");
          } else {
            const sync = result as { content?: string; text?: string };
            rawResponse = sync.content ?? sync.text ?? "";
          }
          break; // Success
        } catch (err) {
          if (attempt > this.config.maxRetries) throw err;
          this.logger.debug("LLMObserver sweep retry", { attempt, error: String(err) });
          await new Promise((r) => setTimeout(r, 500 * attempt));
        }
      }

      const observation = this.parseResponse(rawResponse, summary, crossSessionMatches);
      this.observationHistory.push(observation);
      if (this.observationHistory.length > LLMObserver.MAX_HISTORY) {
        this.observationHistory.shift();
      }

      this.logger.debug("LLMObserver sweep complete", {
        patterns: observation.patterns.length,
        concerns: observation.concerns.length,
        opportunities: observation.opportunities.length,
        confidence: observation.confidence,
      });

      this.lastSweepEventCount = stream.totalCount;
      this.lastSweepStream = stream;
      return observation;
    } catch (err) {
      this.logger.warn("LLMObserver sweep failed", { error: String(err) });
      return null;
    } finally {
      this.sweepInProgress = false;
    }
  }

  // ─── Prompt Construction ──────────────────────────────────────────────────

  private buildPrompt(
    summary: StreamSummary,
    systemModel: SystemModel,
    crossSessionMatches: Array<{ ref: string; snippet: string; score: number }> = [],
  ): string {
    const snap = systemModel.snapshot();
    const providerIssues = Object.entries(snap.providerHealth)
      .filter(([, s]) => s !== "healthy")
      .map(([id, s]) => `${id}(${s})`);
    const crashedPlugins = Object.entries(snap.pluginStatus)
      .filter(([, s]) => s === "crashed")
      .map(([id]) => id);

    const lines: string[] = [
      "You are the inner observer of an AI system (CassiCore). Analyze recent system activity and return a JSON object.",
      "",
      "## Event Stream Summary",
      `- Time window: last ${Math.round(summary.windowMs / 1000)}s`,
      `- Total events: ${summary.totalEvents} (${summary.eventsPerSecond.toFixed(1)}/s)`,
      `- Active sessions: ${summary.activeSessions}`,
      "",
      "### Top Event Types",
      ...summary.topTypes.map((t) => `- ${t.type}: ${t.count}`),
      "",
      "### Recent Event Sequence",
      summary.recentSequence.slice(-30).join(" → "),
      "",
      "## Current System State",
      `- Sessions: ${snap.sessionCount}`,
      `- Active drones: ${snap.activeDrones}, teams: ${snap.activeTeams}`,
    ];

    if (providerIssues.length > 0) {
      lines.push(`- Provider issues: ${providerIssues.join(", ")}`);
    }
    if (crashedPlugins.length > 0) {
      lines.push(`- Crashed plugins: ${crashedPlugins.join(", ")}`);
    }
    const budgetWarnings = Object.entries(snap.budgetTiers)
      .filter(([, t]) => t !== "normal")
      .map(([id, t]) => `${id}(${t})`);
    if (budgetWarnings.length > 0) {
      lines.push(`- Budget warnings: ${budgetWarnings.join(", ")}`);
    }
    if (snap.recentPatterns.length > 0) {
      lines.push(`- Recent patterns: ${snap.recentPatterns.slice(-5).join(", ")}`);
    }

    // ── Historical context from session index ─────────────────────────────
    // Include the top cross-session matches so the LLM can reference prior
    // similar situations and avoid treating recurring patterns as new.
    if (crossSessionMatches.length > 0) {
      lines.push(
        "",
        "## Historical Context (from indexed session archive)",
        "Relevant moments from past sessions with similar event patterns:",
      );
      for (const m of crossSessionMatches) {
        lines.push(`- [${m.ref}] "${m.snippet}"`);
      }
    }

    lines.push(
      "",
      "## Respond with JSON only — no explanation, no markdown fence:",
      '{',
      '  "summary": "One sentence describing what is happening in the system right now",',
      '  "patterns": ["Detected behavioral patterns (max 5)"],',
      '  "concerns": ["Concerns or risks (max 3)"],',
      '  "opportunities": ["Improvement opportunities (max 3)"],',
      '  "confidence": 0.8',
      '}',
    );

    return lines.join("\n");
  }

  // ─── Response Parsing ─────────────────────────────────────────────────────

  private parseResponse(
    raw: string,
    summary: StreamSummary,
    crossSessionMatches: Array<{ ref: string; snippet: string; score: number }> = [],
  ): LLMObservation {
    const jsonMatch = raw.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[0]) as {
          summary?: unknown;
          patterns?: unknown;
          concerns?: unknown;
          opportunities?: unknown;
          confidence?: unknown;
        };

        return {
          id: uuidv4(),
          summary: typeof parsed.summary === "string" ? parsed.summary : "Observation recorded",
          patterns: Array.isArray(parsed.patterns)
            ? (parsed.patterns as unknown[]).filter((p): p is string => typeof p === "string").slice(0, 5)
            : [],
          concerns: Array.isArray(parsed.concerns)
            ? (parsed.concerns as unknown[]).filter((c): c is string => typeof c === "string").slice(0, 3)
            : [],
          opportunities: Array.isArray(parsed.opportunities)
            ? (parsed.opportunities as unknown[]).filter((o): o is string => typeof o === "string").slice(0, 3)
            : [],
          confidence: typeof parsed.confidence === "number" ? Math.min(1, Math.max(0, parsed.confidence)) : 0.7,
          timestamp: Date.now(),
          windowMs: summary.windowMs,
          eventCount: summary.totalEvents,
          crossSessionMatches: crossSessionMatches.length > 0 ? crossSessionMatches : undefined,
        };
      } catch {
        // Fall through to fallback
      }
    }

    // Fallback: extract meaningful text from raw response
    const firstLine = raw.trim().split("\n")[0]?.slice(0, 200) ?? "";
    return {
      id: uuidv4(),
      summary: firstLine || "System activity observed",
      patterns: [],
      concerns: [],
      opportunities: [],
      confidence: 0.3,
      timestamp: Date.now(),
      windowMs: summary.windowMs,
      eventCount: summary.totalEvents,
      crossSessionMatches: crossSessionMatches.length > 0 ? crossSessionMatches : undefined,
    };
  }

  // ─── Query ────────────────────────────────────────────────────────────────

  /** Most recent N LLM observations (newest last). */
  getRecentObservations(count = 10): LLMObservation[] {
    return this.observationHistory.slice(-count);
  }

  /** Unix timestamp (ms) of the last completed sweep. */
  get lastSweepTimestamp(): number {
    return this.lastSweepAt;
  }
}
