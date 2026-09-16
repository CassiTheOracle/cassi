import { describe, expect, test } from "bun:test";

import { allArmTasksPassed, pairComparisons } from "../scripts/compare-providers.js";

const providers = ["openai-codex/gpt-5.6-sol", "opencode-go/qwen3.8-flash"];
const scenarios = ["harbor-relay", "quartz-batcher"];

describe("provider comparison receipt", () => {
  test("preserves execution failures without dereferencing missing metrics", () => {
    const results = providers.flatMap(provider => scenarios.flatMap(scenario => ([
      {
        provider,
        scenario,
        arm: "stock",
        taskSuccess: false,
        executionError: "stock failed",
      },
      {
        provider,
        scenario,
        arm: "cassipi",
        taskSuccess: false,
        executionError: "cassipi failed",
      },
    ])));

    const comparisons = pairComparisons(results) as Array<Record<string, unknown>>;
    expect(comparisons).toHaveLength(4);
    for (const comparison of comparisons) {
      expect(comparison.stockExecutionError).toBe("stock failed");
      expect(comparison.cassipiExecutionError).toBe("cassipi failed");
      expect(comparison.tokenRatioCassiPiToStock).toBeNull();
      expect(comparison.costRatioCassiPiToStock).toBeNull();
      expect(comparison.sessionStateRatioCassiPiToStock).toBeNull();
      expect(comparison.cassipiFieldStateBytes).toBeNull();
    }
  });

  test("gates behavior on CassiPi arms while retaining stock failures", () => {
    const results = providers.flatMap(provider => scenarios.flatMap(scenario => ([
      {
        provider,
        scenario,
        arm: "stock",
        taskSuccess: false,
      },
      {
        provider,
        scenario,
        arm: "cassipi",
        taskSuccess: true,
      },
    ])));

    expect(allArmTasksPassed(results, "cassipi")).toBeTrue();
    expect(allArmTasksPassed(results, "stock")).toBeFalse();
    expect(allArmTasksPassed([
      ...results.slice(0, -1),
      { ...results.at(-1), executionError: "provider failed" },
    ], "cassipi")).toBeFalse();
  });
});
