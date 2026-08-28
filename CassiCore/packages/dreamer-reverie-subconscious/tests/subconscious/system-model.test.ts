/**
 * SystemModel — System-wide Mental Model Tests
 *
 * The SystemModel maintains a holistic view of the entire CassiCore runtime:
 * all sessions, provider health, plugin status, active agents, observations,
 * and anomalies. It is updated by events from the EventStream and serves as
 * the source of truth for context injection and diagnostic snapshots.
 *
 * Key responsibilities:
 * - Track session lifecycle (created, active turns, ended)
 * - Monitor provider health (healthy, degraded, error, rate_limited)
 * - Track plugin status (healthy, crashed, stopped)
 * - Accumulate observations from heuristic and LLM observers
 * - Manage anomalies with acknowledgment support
 * - Build context injection for turn pipeline integration
 * - Persist/hydrate state via memory KV for cross-restart continuity
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { SystemModel } from "../../src/subconscious/system-model.js";
import type { ILogger } from "@cassicore/foundation";
import type { IMemory } from "@cassicore/foundation";
import type { Anomaly, Observation, LLMObservation } from "../../src/subconscious/types.js";

function makeLogger(): ILogger {
  const log = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(),
  } as unknown as ILogger;
  (log.child as ReturnType<typeof vi.fn>).mockReturnValue(log);
  return log;
}

function makeMemory(): IMemory {
  const store = new Map<string, unknown>();
  return {
    kv_get: vi.fn(async (key: string) => store.get(key) ?? null),
    kv_set: vi.fn(async (key: string, value: unknown) => { store.set(key, value); }),
    kv_delete: vi.fn(async (key: string) => { store.delete(key); }),
    search: vi.fn(async () => []),
    store: vi.fn(async () => "mem-id"),
    get: vi.fn(async () => null),
    list: vi.fn(async () => []),
  } as unknown as IMemory;
}

function makeAnomaly(overrides: Partial<Anomaly> = {}): Anomaly {
  return {
    id: "anomaly-1",
    description: "test anomaly",
    severity: "medium",
    eventTypes: [],
    timestamp: Date.now(),
    ...overrides,
  };
}

function makeObservation(overrides: Partial<Observation> = {}): Observation {
  return {
    id: "obs-1",
    summary: "test observation",
    patterns: ["pattern-a"],
    confidence: 0.8,
    source: "heuristic",
    relatedEventTypes: [],
    timestamp: Date.now(),
    ...overrides,
  };
}

function makeLLMObservation(overrides: Partial<LLMObservation> = {}): LLMObservation {
  return {
    id: "llm-obs-1",
    summary: "llm summary",
    patterns: ["llm-pattern"],
    concerns: ["llm-concern"],
    opportunities: ["llm-opportunity"],
    confidence: 0.9,
    timestamp: Date.now(),
    windowMs: 60_000,
    eventCount: 10,
    ...overrides,
  };
}

describe("SystemModel session tracking", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a session entry when session:created event is received", () => {
    model.update({ type: "session:created", sessionId: "s1", timestamp: new Date() } as never);
    const s = model.getSession("s1");
    expect(s).toBeDefined();
    expect(s!.sessionId).toBe("s1");
    expect(s!.turnCount).toBe(0);
    expect(s!.phase).toBe("initial");
  });

  it("removes the session when session:ended event is received", () => {
    model.update({ type: "session:created", sessionId: "s1", timestamp: new Date() } as never);
    model.update({ type: "session:ended", sessionId: "s1" } as never);
    expect(model.getSession("s1")).toBeUndefined();
  });

  it("creates a session on turn:start even if session:created was never received", () => {
    model.update({ type: "turn:start", sessionId: "s-new", timestamp: new Date() } as never);
    const s = model.getSession("s-new");
    expect(s).toBeDefined();
    expect(s!.turnCount).toBe(1);
    expect(s!.phase).toBe("active");
  });

  it("increments turn count on each turn:start for existing sessions", () => {
    model.update({ type: "session:created", sessionId: "s1", timestamp: new Date() } as never);
    model.update({ type: "turn:start", sessionId: "s1", timestamp: new Date() } as never);
    model.update({ type: "turn:start", sessionId: "s1", timestamp: new Date() } as never);
    expect(model.getSession("s1")!.turnCount).toBe(2);
  });

  it("tracks recent tool calls for each session", () => {
    model.update({ type: "session:created", sessionId: "s1", timestamp: new Date() } as never);
    model.update({ type: "turn:tool_call", sessionId: "s1", toolName: "bash" } as never);
    model.update({ type: "turn:tool_call", sessionId: "s1", toolName: "read" } as never);
    const s = model.getSession("s1");
    expect(s!.recentToolCalls).toContain("bash");
    expect(s!.recentToolCalls).toContain("read");
  });

  it("caps recentToolCalls at 10 entries to prevent unbounded growth", () => {
    model.update({ type: "session:created", sessionId: "s1", timestamp: new Date() } as never);
    for (let i = 0; i < 15; i++) {
      model.update({ type: "turn:tool_call", sessionId: "s1", toolName: `tool-${i}` } as never);
    }
    expect(model.getSession("s1")!.recentToolCalls.length).toBeLessThanOrEqual(10);
  });
});

describe("SystemModel provider health tracking", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("marks provider as healthy on provider:request_start", () => {
    model.update({ type: "provider:request_start", providerId: "p1" } as never);
    const snap = model.snapshot();
    expect(snap.providerHealth["p1"]).toBe("healthy");
  });

  it("marks provider as degraded on first error", () => {
    model.update({ type: "provider:request_error", providerId: "p1", consecutiveErrors: 1 } as never);
    expect(model.snapshot().providerHealth["p1"]).toBe("degraded");
  });

  it("marks provider as error after 3+ consecutive errors", () => {
    model.update({ type: "provider:request_error", providerId: "p1", consecutiveErrors: 3 } as never);
    expect(model.snapshot().providerHealth["p1"]).toBe("error");
  });

  it("resets provider to healthy on provider:error_reset", () => {
    model.update({ type: "provider:request_error", providerId: "p1", consecutiveErrors: 5 } as never);
    model.update({ type: "provider:error_reset", providerId: "p1" } as never);
    expect(model.snapshot().providerHealth["p1"]).toBe("healthy");
  });

  it("marks provider as rate_limited on provider:rate_limited", () => {
    model.update({ type: "provider:rate_limited", providerId: "p1", retryAfterMs: 60_000 } as never);
    expect(model.snapshot().providerHealth["p1"]).toBe("rate_limited");
  });

  it("does not override rate_limited status with healthy on provider:request_start", () => {
    model.update({ type: "provider:rate_limited", providerId: "p1", retryAfterMs: 999_999 } as never);
    model.update({ type: "provider:request_start", providerId: "p1" } as never);
    expect(model.snapshot().providerHealth["p1"]).toBe("rate_limited");
  });
});

describe("SystemModel plugin status tracking", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("marks plugin as healthy on plugin:loaded", () => {
    model.update({ type: "plugin:loaded", pluginId: "my-plugin" } as never);
    expect(model.snapshot().pluginStatus["my-plugin"]).toBe("healthy");
  });

  it("marks plugin as crashed on plugin:crashed", () => {
    model.update({ type: "plugin:crashed", pluginId: "my-plugin" } as never);
    expect(model.snapshot().pluginStatus["my-plugin"]).toBe("crashed");
  });

  it("marks plugin as healthy on plugin:restarted", () => {
    model.update({ type: "plugin:crashed", pluginId: "my-plugin" } as never);
    model.update({ type: "plugin:restarted", pluginId: "my-plugin" } as never);
    expect(model.snapshot().pluginStatus["my-plugin"]).toBe("healthy");
  });

  it("marks plugin as stopped on plugin:stopped", () => {
    model.update({ type: "plugin:stopped", pluginId: "my-plugin" } as never);
    expect(model.snapshot().pluginStatus["my-plugin"]).toBe("stopped");
  });
});

describe("SystemModel budget tracking", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("records budget tier changes for providers", () => {
    model.update({ type: "budget:tier_changed", providerId: "p1", newTier: "frugal" } as never);
    expect(model.snapshot().budgetTiers["p1"]).toBe("frugal");
  });
});

describe("SystemModel agent tracking", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("tracks active drones through their lifecycle", () => {
    model.update({ type: "drone:spawned", droneId: "d1" } as never);
    expect(model.snapshot().activeDrones).toBe(1);
    model.update({ type: "drone:completed", droneId: "d1" } as never);
    expect(model.snapshot().activeDrones).toBe(0);
  });

  it("removes drone from active count on failure", () => {
    model.update({ type: "drone:spawned", droneId: "d1" } as never);
    model.update({ type: "drone:failed", droneId: "d1" } as never);
    expect(model.snapshot().activeDrones).toBe(0);
  });

  it("tracks active teams through their lifecycle", () => {
    model.update({ type: "team:started", teamId: "t1" } as never);
    expect(model.snapshot().activeTeams).toBe(1);
    model.update({ type: "team:completed", teamId: "t1" } as never);
    expect(model.snapshot().activeTeams).toBe(0);
  });
});

describe("SystemModel snapshot generation", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns a complete snapshot with zero state for fresh model", () => {
    const snap = model.snapshot();
    expect(snap.sessionCount).toBe(0);
    expect(snap.activeDrones).toBe(0);
    expect(snap.activeTeams).toBe(0);
    expect(snap.systemHealth).toBe("healthy");
    expect(snap.observationCount).toBe(0);
    expect(snap.capturedAt).toBeGreaterThan(0);
  });

  it("computes systemHealth as degraded when a provider is in degraded state", () => {
    model.update({ type: "provider:request_error", providerId: "p1", consecutiveErrors: 1 } as never);
    expect(model.snapshot().systemHealth).toBe("degraded");
  });

  it("computes systemHealth as degraded when a plugin has crashed", () => {
    model.update({ type: "plugin:crashed", pluginId: "pl1" } as never);
    expect(model.snapshot().systemHealth).toBe("degraded");
  });

  it("computes systemHealth as critical when both provider error AND plugin crashed", () => {
    model.update({ type: "provider:request_error", providerId: "p1", consecutiveErrors: 5 } as never);
    model.update({ type: "plugin:crashed", pluginId: "pl1" } as never);
    expect(model.snapshot().systemHealth).toBe("critical");
  });

  it("includes recentPatterns from observations in the snapshot", () => {
    model.addObservation(makeObservation({ patterns: ["pattern-x", "pattern-y"] }));
    const snap = model.snapshot();
    expect(snap.recentPatterns).toContain("pattern-x");
    expect(snap.recentPatterns).toContain("pattern-y");
  });
});

describe("SystemModel observation management", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("stores observations and returns them via getRecentObservations()", () => {
    const obs = makeObservation();
    model.addObservation(obs);
    const recent = model.getRecentObservations(10);
    expect(recent).toHaveLength(1);
    expect(recent[0].id).toBe("obs-1");
  });

  it("caps observations at MAX_OBSERVATIONS (200) to prevent unbounded growth", () => {
    for (let i = 0; i < 210; i++) {
      model.addObservation(makeObservation({ id: `obs-${i}` }));
    }
    expect(model.getRecentObservations(1000).length).toBeLessThanOrEqual(200);
  });

  it("stores anomalies and returns them via getAnomalies()", () => {
    const anomaly = makeAnomaly();
    model.addAnomaly(anomaly);
    const anomalies = model.getAnomalies();
    expect(anomalies).toHaveLength(1);
    expect(anomalies[0].id).toBe("anomaly-1");
  });

  it("caps anomalies at MAX_ANOMALIES (100) to prevent unbounded growth", () => {
    for (let i = 0; i < 110; i++) {
      model.addAnomaly(makeAnomaly({ id: `a-${i}` }));
    }
    expect(model.getAnomalies(true).length).toBeLessThanOrEqual(100);
  });
});

describe("SystemModel LLM observation integration", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("adds an Observation with source=llm from the LLM summary", () => {
    const llmObs = makeLLMObservation();
    model.addLLMObservation(llmObs);
    const observations = model.getRecentObservations(10);
    expect(observations.some((o) => o.source === "llm" && o.id === "llm-obs-1")).toBe(true);
  });

  it("converts each concern from LLM observation into a low-severity Anomaly", () => {
    const llmObs = makeLLMObservation({ concerns: ["concern-1", "concern-2"] });
    model.addLLMObservation(llmObs);
    const anomalies = model.getAnomalies();
    expect(anomalies).toHaveLength(2);
    expect(anomalies.every((a) => a.severity === "low")).toBe(true);
  });

  it("stores patterns from the LLM observation for snapshot inclusion", () => {
    const llmObs = makeLLMObservation({ patterns: ["p1", "p2"] });
    model.addLLMObservation(llmObs);
    const snap = model.snapshot();
    expect(snap.recentPatterns).toContain("p1");
    expect(snap.recentPatterns).toContain("p2");
  });
});

describe("SystemModel anomaly acknowledgment", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("marks anomaly as acknowledged and returns true", () => {
    model.addAnomaly(makeAnomaly({ id: "ack-me" }));
    const result = model.acknowledgeAnomaly("ack-me");
    expect(result).toBe(true);
    expect(model.getAnomalies().find((a) => a.id === "ack-me")).toBeUndefined();
  });

  it("returns true when acknowledging, false for unknown id", () => {
    model.addAnomaly(makeAnomaly({ id: "ack-me" }));
    expect(model.acknowledgeAnomaly("ack-me")).toBe(true);
    expect(model.acknowledgeAnomaly("not-exist")).toBe(false);
  });

  it("shows acknowledged anomaly when includeAcknowledged=true", () => {
    model.addAnomaly(makeAnomaly({ id: "ack-me" }));
    model.acknowledgeAnomaly("ack-me");
    const all = model.getAnomalies(true);
    expect(all.find((a) => a.id === "ack-me")).toBeDefined();
  });
});

describe("SystemModel context injection", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns undefined when system is healthy and no recent anomalies exist", () => {
    const result = model.getContextInjection("s1");
    expect(result).toBeUndefined();
  });

  it("includes provider degradation issues in the injection", () => {
    model.update({ type: "provider:request_error", providerId: "p1", consecutiveErrors: 2 } as never);
    const result = model.getContextInjection("s1");
    expect(result).toBeDefined();
    expect(result).toContain("p1");
  });

  it("includes crashed plugin information in the injection", () => {
    model.update({ type: "plugin:crashed", pluginId: "bad-plugin" } as never);
    const result = model.getContextInjection("s1");
    expect(result).toContain("bad-plugin");
  });

  it("includes budget warnings for critical/frugal tiers", () => {
    model.update({ type: "budget:tier_changed", providerId: "p1", newTier: "critical" } as never);
    const result = model.getContextInjection("s1");
    expect(result).toContain("critical");
  });

  it("includes recent medium/high severity anomalies", () => {
    model.addAnomaly(makeAnomaly({ description: "high anomaly text", severity: "high", timestamp: Date.now() }));
    const result = model.getContextInjection("s1");
    expect(result).toContain("high anomaly text");
  });

  it("excludes acknowledged anomalies from context injection", () => {
    model.addAnomaly(makeAnomaly({ id: "ack-a", description: "hidden anomaly", severity: "high", timestamp: Date.now() }));
    model.acknowledgeAnomaly("ack-a");
    const result = model.getContextInjection("s1");
    expect(result ?? "").not.toContain("hidden anomaly");
  });

  it("excludes low severity anomalies from context injection", () => {
    model.addAnomaly(makeAnomaly({ description: "low severity", severity: "low", timestamp: Date.now() }));
    const result = model.getContextInjection("s1");
    expect(result ?? "").not.toContain("low severity");
  });

  it("caches the result for the same sessionId to avoid recomputation", () => {
    model.update({ type: "provider:request_error", providerId: "p1", consecutiveErrors: 1 } as never);
    const r1 = model.getContextInjection("s1");
    const r2 = model.getContextInjection("s1");
    expect(r1).toBe(r2);
  });

  it("includes recent LLM observation summary in the injection", () => {
    const llmObs = makeLLMObservation({
      summary: "LLM awareness summary here",
      concerns: [],
      timestamp: Date.now(),
    });
    model.addLLMObservation(llmObs);
    const result = model.getContextInjection("s1");
    expect(result).toContain("LLM awareness summary here");
  });
});

describe("SystemModel session cleanup", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("removes session from registry when cleanupSession is called", () => {
    model.update({ type: "session:created", sessionId: "s1", timestamp: new Date() } as never);
    model.cleanupSession("s1");
    expect(model.getSession("s1")).toBeUndefined();
  });

  it("is a no-op when cleaning up an unknown session", () => {
    expect(() => model.cleanupSession("not-a-session")).not.toThrow();
  });
});

describe("SystemModel session enumeration", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns all tracked session IDs", () => {
    model.update({ type: "session:created", sessionId: "s1", timestamp: new Date() } as never);
    model.update({ type: "session:created", sessionId: "s2", timestamp: new Date() } as never);
    expect(model.getSessionIds()).toEqual(expect.arrayContaining(["s1", "s2"]));
    expect(model.getSessionIds()).toHaveLength(2);
  });
});

describe("SystemModel persistence", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is a no-op when memory is not configured", async () => {
    await expect(model.persist()).resolves.toBeUndefined();
  });

  it("is a no-op when memory is not configured for hydration", async () => {
    await expect(model.hydrate()).resolves.toBeUndefined();
  });

  it("persists anomalies and LLM observations to memory KV store", async () => {
    const memory = makeMemory();
    model.setMemory(memory);
    model.addAnomaly(makeAnomaly({ id: "persist-a" }));
    model.addLLMObservation(makeLLMObservation({ id: "persist-llm" }));
    await model.persist();
    expect(memory.kv_set).toHaveBeenCalledWith(
      "consciousness:anomalies",
      expect.arrayContaining([expect.objectContaining({ id: "persist-a" })]),
    );
    expect(memory.kv_set).toHaveBeenCalledWith(
      "consciousness:observations",
      expect.arrayContaining([expect.objectContaining({ id: "persist-llm" })]),
    );
  });

  it("restores anomalies and observations from memory KV store on hydrate", async () => {
    const memory = makeMemory();
    model.setMemory(memory);

    const storedAnomalies: Anomaly[] = [makeAnomaly({ id: "hydrated-a" })];
    const storedObs: Observation[] = [makeObservation({ id: "hydrated-obs", source: "llm" })];

    (memory.kv_get as ReturnType<typeof vi.fn>).mockImplementation(async (key: string) => {
      if (key === "consciousness:anomalies") return storedAnomalies;
      if (key === "consciousness:observations") return storedObs;
      return null;
    });

    await model.hydrate();
    expect(model.getAnomalies(true).find((a) => a.id === "hydrated-a")).toBeDefined();
    expect(model.getRecentObservations(10).find((o) => o.id === "hydrated-obs")).toBeDefined();
  });

  it("handles corrupt memory gracefully without throwing", async () => {
    const memory = makeMemory();
    model.setMemory(memory);
    (memory.kv_get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("db error"));
    await expect(model.hydrate()).resolves.toBeUndefined();
  });
});

describe("SystemModel error resilience", () => {
  let model: SystemModel;
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
    model = new SystemModel(logger);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not throw on unknown event types", () => {
    expect(() => model.update({ type: "unknown:event:type" } as never)).not.toThrow();
  });

  it("does not throw on events with missing optional fields", () => {
    expect(() => model.update({ type: "session:created" } as never)).not.toThrow();
    expect(() => model.update({ type: "provider:request_error" } as never)).not.toThrow();
  });
});
