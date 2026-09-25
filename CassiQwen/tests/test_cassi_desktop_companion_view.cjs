"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function element() {
  return {
    dataset: {}, style: {}, children: [], value: "", checked: false, disabled: false,
    get firstChild() { return this.children[0]; },
    textContent: "", classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {}, setAttribute() {}, removeAttribute() {},
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren(...nodes) { this.children = nodes; },
    querySelector() { return element(); },
  };
}

function viewer() {
  const nodes = new Map();
  const get = (selector) => {
    if (!nodes.has(selector)) nodes.set(selector, element());
    return nodes.get(selector);
  };
  const document = {
    visibilityState: "hidden",
    querySelector: get,
    querySelectorAll: () => [],
    createElement: () => element(),
    createElementNS: () => element(),
    createTextNode: (text) => ({ textContent: text }),
    addEventListener() {},
  };
  const window = { matchMedia: () => ({ matches: true }), addEventListener() {}, setInterval: () => 1 };
  const context = vm.createContext({ document, window, URL, Date, Map, Set, BigInt, Number, JSON, AbortController, console });
  const source = fs.readFileSync(path.join(__dirname, "../desktop_companion/app.js"), "utf8");
  vm.runInContext(source, context, { filename: "desktop_companion/app.js" });
  return { context, get, evaluate: (expression) => vm.runInContext(expression, context) };
}

function snapshot(generation, { available = true, status = "working" } = {}) {
  return {
    schema: "cassifi.embodied-field.v1", generation, state_sha256: `owner-${generation}`,
    captured_at_ns: String(BigInt(generation) * 1_000_000_000n),
    circulation: available ? { value: { workspace: { energy: generation, field_ticks: generation * 2 } } } : { status: "unavailable" },
    regions: available ? { items: [{ region_id: "R1", signed_current: generation, stale: false }] } : { status: "unavailable", items: [] },
    working_organization: available ? {
      items: [{ program_ref: { kind: "Program", id: "study", content_version: 1 }, status,
        ...(status === "resting" ? { contribution: "measured result", reopen_condition: "new evidence" } : {}) }],
    } : { status: "unavailable", items: [] },
  };
}

test("distinct admitted states reveal measured change and recorded rest, not duplicate polling", () => {
  const { context, get, evaluate } = viewer();
  context.first = snapshot(1);
  context.second = snapshot(2, { status: "resting" });
  evaluate("admitFieldObservation(first); admitFieldObservation(first); admitFieldObservation(second); renderFieldActivity()");
  assert.match(get("#embodied-activity-note").textContent, /3 shared measured quantities changed/);
  assert.match(get("#embodied-activity-note").textContent, /field ticks 2 → 4/);
  assert.match(get("#embodied-transitions").children[0].textContent, /status working → resting; contribution measured result; reopen condition new evidence/);
  assert.equal(evaluate("state.embodied.observations.length"), 2);
  assert.equal(get("#embodied-activity-trace").children.length, 3);
});

test("missing measurements and disappearing region remain explicitly unknown", () => {
  const { context, get, evaluate } = viewer();
  context.first = snapshot(1);
  context.missing = snapshot(2, { available: false });
  evaluate("admitFieldObservation(first); admitFieldObservation(missing); renderFieldActivity(); state.embodied.selectedRegion = 'R1'; renderRegionInspection(missing)");
  assert.match(get("#embodied-activity-note").textContent, /No finite numerical measurements were returned/);
  assert.match(get("#embodied-region-inspection").children[0].textContent, /not returned by this capture/);
  assert.equal(evaluate("state.embodied.transitions.length"), 0);
});
