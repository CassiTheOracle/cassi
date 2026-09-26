/**
 * LLMObserver — Periodic Reflective Awareness Tests
 *
 * The LLMObserver runs periodic "sweeps" (default every 30s) that analyze
 * recent event stream activity through an LLM. Unlike the HeuristicObserver
 * which is reactive and rule-based, the LLMObserver is reflective — it asks
 * "what patterns, risks, or opportunities do I see that heuristics might miss?"
 *
 * Key behaviors:
 * - Gracefully degrades when no provider is configured (skips sweep)
 * - Builds a structured prompt from EventStream summary and SystemModel state
 * - Includes cross-session historical context from memory index
 * - Parses JSON response into patterns, concerns, opportunities, confidence
 * - Falls back gracefully on malformed responses
 * - Prevents concurrent sweeps with sweepInProgress guard
 * - Accumulates observation history for diagnostic queries
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { LLMObserver } from "../../src/subconscious/llm-observer.js";
import { EventStream } from "../../src/subconscious/event-stream.js";
import { SystemModel } from "../../src/subconscious/system-model.js";
import type { ILogger } from "@cassicore/foundation";
import type { IProvider } from "@cassicore/foundation";

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

import type { RuntimeEvent } from "@cassicore/foundation";

function makeBus() {
  const listeners: Array<(e: RuntimeEvent) => void> = [];
  return {
    onAll: vi.fn((h: (e: RuntimeEvent) => void) => {
      listeners.push(h);
      return () => listeners.splice(listeners.indexOf(h), 1);
    }),
    emit: (e: RuntimeEvent) => listeners.forEach((h) => h(e)),
  };
}

function makeStream(totalEvents = 5): EventStream {
  const stream = new EventStream(makeLogger());
  const bus = makeBus();
  stream.connect(bus as never);
  for (let i = 0; i < totalEvents; i++) {
    bus.emit({ type: "turn:start", sessionId: `s${i}`, timestamp: new Date() } as never);
  }
  return stream;
}

function makeSystemModel(): SystemModel {
  return new SystemModel(makeLogger());
}

/** Build a mock IProvider whose complete() returns a valid JSON LLM response */
function makeProvider(responseJson?: object): IProvider {
  const json = JSON.stringify(
    responseJson ?? {
      summary: "System is running normally",
      patterns: ["high turn volume"],
      concerns: ["provider latency increasing"],
      opportunities: ["cache responses"],
      confidence: 0.85,
    },
  );
  return {
    complete: vi.fn().mockResolvedValue({ content: json }),
  } as unknown as IProvider;
}

/** Build a mock IProvider that throws on complete() */
function makeFailingProvider(): IProvider {
  return {
    complete: vi.fn().mockRejectedValue(new Error("network error")),
  } as unknown as IProvider;
}

describe("LLMObserver graceful degradation", () => {
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("when no provider is configured", () => {
    it("returns null from sweep() without throwing", async () => {
      const observer = new LLMObserver(logger);
      const result = await observer.sweep(makeStream(), makeSystemModel());
      expect(result).toBeNull();
    });

    it("logs a debug message explaining why sweep was skipped", async () => {
      const observer = new LLMObserver(logger);
      await observer.sweep(makeStream(), makeSystemModel());
      expect(logger.debug).toHaveBeenCalledWith(
        expect.stringContaining("no provider"),
      );
    });
  });
});

describe("LLMObserver empty stream handling", () => {
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns null when the event stream has no events to analyze", async () => {
    const observer = new LLMObserver(logger);
    const provider = makeProvider();
    observer.setProvider(provider);
    const emptyStream = new EventStream(makeLogger());
    const result = await observer.sweep(emptyStream, makeSystemModel());
    expect(result).toBeNull();
  });
});

describe("LLMObserver successful sweep", () => {
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns an LLMObservation with parsed summary, patterns, concerns, and opportunities", async () => {
    const observer = new LLMObserver(logger);
    observer.setProvider(makeProvider());
    const result = await observer.sweep(makeStream(), makeSystemModel());
    expect(result).not.toBeNull();
    expect(result!.summary).toBe("System is running normally");
    expect(result!.patterns).toContain("high turn volume");
    expect(result!.concerns).toContain("provider latency increasing");
    expect(result!.opportunities).toContain("cache responses");
    expect(result!.confidence).toBeCloseTo(0.85);
  });

  it("includes windowMs and eventCount metadata on the observation", async () => {
    const observer = new LLMObserver(logger, { windowMs: 60_000 });
    observer.setProvider(makeProvider());
    const result = await observer.sweep(makeStream(3), makeSystemModel());
    expect(result!.windowMs).toBe(60_000);
    expect(result!.eventCount).toBeGreaterThan(0);
  });

  it("sets timestamp on the observation to track when sweep completed", async () => {
    const observer = new LLMObserver(logger);
    observer.setProvider(makeProvider());
    const before = Date.now();
    const result = await observer.sweep(makeStream(), makeSystemModel());
    expect(result!.timestamp).toBeGreaterThanOrEqual(before);
  });

  it("updates lastSweepTimestamp after a sweep completes", async () => {
    const observer = new LLMObserver(logger);
    observer.setProvider(makeProvider());
    expect(observer.lastSweepTimestamp).toBe(0);
    await observer.sweep(makeStream(), makeSystemModel());
    expect(observer.lastSweepTimestamp).toBeGreaterThan(0);
  });
});

describe("LLMObserver response parsing fallback", () => {
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns a low-confidence fallback when response is not valid JSON", async () => {
    const observer = new LLMObserver(logger);
    observer.setProvider({
      complete: vi.fn().mockResolvedValue({ content: "Some plain text response" }),
    } as unknown as IProvider);
    const result = await observer.sweep(makeStream(), makeSystemModel());
    expect(result).not.toBeNull();
    expect(result!.confidence).toBe(0.3);
    expect(result!.patterns).toEqual([]);
    expect(result!.summary).toBeTruthy();
  });

  it("handles partial JSON gracefully by extracting available fields", async () => {
    const observer = new LLMObserver(logger);
    observer.setProvider({
      complete: vi.fn().mockResolvedValue({
        content: '{"summary": "partial", "patterns": ["x"]}',
      }),
    } as unknown as IProvider);
    const result = await observer.sweep(makeStream(), makeSystemModel());
    expect(result).not.toBeNull();
    expect(result!.summary).toBe("partial");
    expect(result!.patterns).toContain("x");
    expect(result!.concerns).toEqual([]);
  });

  it("returns null when provider throws and retries are exhausted", async () => {
    const observer = new LLMObserver(logger, { maxRetries: 0 });
    observer.setProvider(makeFailingProvider());
    const result = await observer.sweep(makeStream(), makeSystemModel());
    expect(result).toBeNull();
  });
});

describe("LLMObserver observation history", () => {
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns empty array before any sweeps have been performed", () => {
    const observer = new LLMObserver(logger);
    expect(observer.getRecentObservations()).toEqual([]);
  });

  it("suppresses near-duplicate observations across overlapping sweeps", async () => {
    const observer = new LLMObserver(logger);
    observer.setProvider(makeProvider());
    await observer.sweep(makeStream(), makeSystemModel());
    await observer.sweep(makeStream(), makeSystemModel());
    expect(observer.getRecentObservations()).toHaveLength(1);
  });

  it("respects the count parameter when returning distinct recent observations", async () => {
    const observer = new LLMObserver(logger);
    let i = 0;
    observer.setProvider({
      complete: vi.fn().mockImplementation(async () => ({
        content: JSON.stringify({
          summary: `summary-${i++}`,
          patterns: [`pattern-${i}`],
          concerns: [`concern-${i}`],
          opportunities: [`opportunity-${i}`],
          confidence: 0.85,
        }),
      })),
    } as unknown as IProvider);
    for (let j = 0; j < 5; j++) {
      await observer.sweep(makeStream(), makeSystemModel());
    }
    expect(observer.getRecentObservations(3)).toHaveLength(3);
  });
});

describe("LLMObserver disabled mode", () => {
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not start the interval timer when enabled=false", () => {
    const setIntervalSpy = vi.spyOn(globalThis, "setInterval");
    const observer = new LLMObserver(logger, { enabled: false });
    observer.start(makeStream(), makeSystemModel());
    expect(setIntervalSpy).not.toHaveBeenCalled();
  });
});

describe("LLMObserver lifecycle", () => {
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("clears the interval timer when stop() is called", () => {
    const clearIntervalSpy = vi.spyOn(globalThis, "clearInterval");
    const observer = new LLMObserver(logger, { intervalMs: 99_999 });
    observer.setProvider(makeProvider());
    observer.start(makeStream(), makeSystemModel());
    observer.stop();
    expect(clearIntervalSpy).toHaveBeenCalled();
  });

  it("is safe to call stop() when the observer was never started", () => {
    const observer = new LLMObserver(logger);
    expect(() => observer.stop()).not.toThrow();
  });

  it("clears the previous timer when start() is called multiple times", () => {
    const clearIntervalSpy = vi.spyOn(globalThis, "clearInterval");
    const observer = new LLMObserver(logger, { intervalMs: 99_999 });
    observer.setProvider(makeProvider());
    const stream = makeStream();
    const model = makeSystemModel();
    observer.start(stream, model);
    observer.start(stream, model);
    expect(clearIntervalSpy).toHaveBeenCalled();
    observer.stop();
  });
});

describe("LLMObserver sweep concurrency guard", () => {
  let logger: ILogger;

  beforeEach(() => {
    logger = makeLogger();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns null when a sweep is already in progress to prevent overlapping calls", async () => {
    const observer = new LLMObserver(logger);
    let resolveComplete!: (v: unknown) => void;
    const pendingPromise = new Promise((r) => { resolveComplete = r; });
    observer.setProvider({
      complete: vi.fn().mockReturnValue(pendingPromise),
    } as unknown as IProvider);

    const stream = makeStream();
    const model = makeSystemModel();
    const firstSweep = observer.sweep(stream, model);
    const secondResult = await observer.sweep(stream, model);
    expect(secondResult).toBeNull();

    resolveComplete({ content: '{"summary": "done", "patterns": [], "concerns": [], "opportunities": [], "confidence": 0.5}' });
    await firstSweep;
  });
});
