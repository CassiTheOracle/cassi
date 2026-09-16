"""Measure field-owned method selection on paired repeated workloads.

The harness cold-starts every strategy for each declared order permutation.
All strategies receive the same fresh-compiled source and budget request, while
their execution order rotates. The policy's measured checked outcomes are the
only adaptation signal; this module does not fabricate labels or timing
feedback.
"""
from __future__ import annotations

import base64
import argparse
import copy
import hashlib
import random
import json
import time
from pathlib import Path
import zlib
from typing import Any, Mapping, Sequence


from cassi_computation_policy import (
    METHODS,
    PolicyState,
    compile_source,
    initial_policy,
    solve_and_learn,
)

SCHEMA = "cassifi.computation-policy-scenario.v4"
DEFAULT_OUTPUT = Path("_diag/computation_policy_refinement_scenario.json")
PERMUTATION_SEEDS = (20260941, 20260967)
REPETITIONS = 3
BUDGETS = (64, 512, 2000)
COHORTS = ("cold-start", "warm-start", "restart-continuation")
STRATEGIES = ("adaptive", "structural", *METHODS)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _json(value: Any) -> Any:
    """Convert public receipts/states to detached JSON data."""
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _state_dict(policy: PolicyState) -> dict[str, Any]:
    return _json(policy.as_dict())


def _state_sha(policy: PolicyState, state: Mapping[str, Any] | None = None) -> str:
    value = getattr(policy, "state_sha256", "")
    if callable(value):
        value = value()
    if value:
        return str(value)
    if state is None:
        state = _state_dict(policy)
    return _digest(state)


def _compiled_dict(compiled: Any) -> dict[str, Any]:
    if hasattr(compiled, "as_dict"):
        return _json(compiled.as_dict())
    return _json(dict(compiled))




def _rename(source: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    """Relabel all source signals while preserving the source structure."""
    value = copy.deepcopy(dict(source))
    kind = str(value["kind"])
    names: set[str] = set()
    if kind == "circuit":
        names.update(str(name) for name in value["inputs"])
    else:
        names.update(str(name) for name in value["state"])
        names.update(str(name) for name in value["inputs"])
    for gate in value.get("gates", []):
        names.add(str(gate["out"]))
        names.update(str(name) for name in gate.get("args", []))
    for relation in value.get("relations", []):
        names.update(str(name) for name in relation.get("args", []))
    for row in value.get("assertions", []) + value.get("initial", []) + value.get("final", []):
        names.add(str(row[0]))
    for row in value.get("input_assertions", []):
        names.add(str(row[1]))
    for row in value.get("next_state", []):
        names.update((str(row[0]), str(row[1])))
    for clause in value.get("clauses", []):
        for literal in clause:
            names.add(str(literal[0]))
    mapping = {name: f"{prefix}{index:02d}" for index, name in enumerate(sorted(names))}

    def signal(name: Any) -> str:
        return mapping.get(str(name), str(name))

    if kind == "circuit":
        value["inputs"] = [signal(name) for name in value["inputs"]]
    else:
        value["state"] = [signal(name) for name in value["state"]]
        value["inputs"] = [signal(name) for name in value["inputs"]]
    for gate in value.get("gates", []):
        gate["out"] = signal(gate["out"])
        gate["args"] = [signal(name) for name in gate.get("args", [])]
    for relation in value.get("relations", []):
        relation["args"] = [signal(name) for name in relation.get("args", [])]
    for key in ("assertions", "initial", "final"):
        value[key] = [[signal(row[0]), row[1]] for row in value.get(key, [])]
    value["input_assertions"] = [[row[0], signal(row[1]), row[2]] for row in value.get("input_assertions", [])]
    value["next_state"] = [[signal(row[0]), signal(row[1])] for row in value.get("next_state", [])]
    value["clauses"] = [[[signal(literal[0]), literal[1], *literal[2:]] for literal in clause] for clause in value.get("clauses", [])]
    return value


def _parity(size: int, relabeling: int = 0, *, inconsistent: bool = False) -> dict[str, Any]:
    names = [f"x{i}" for i in range(size)]
    source: dict[str, Any] = {
        "kind": "circuit",
        "inputs": names,
        "gates": [],
        "assertions": [["x0", 1], ["x1", 1], ["x2", 0], ["x3", 0], ["x4", 0 if not inconsistent else 1]],
        "relations": [
            {"kind": "xor", "args": ["x0", "x1", "x2"], "rhs": 0},
            {"kind": "xor", "args": ["x2", "x3", "x4"], "rhs": 0},
        ],
        "clauses": [],
    }
    if size > 5:
        source["relations"].append({"kind": "xor", "args": [f"x{i}" for i in range(5, size)], "rhs": 0})
    return _rename(source, f"p{relabeling}_") if relabeling else source


def _wasteful(size: int, relabeling: int = 0) -> dict[str, Any]:
    inputs = [f"i{i}" for i in range(size)]
    gates: list[dict[str, Any]] = []
    pool = list(inputs)
    for index in range(size + 2):
        op = ("and", "or", "xor", "nand")[index % 4]
        gates.append({"op": op, "out": f"g{index}", "args": [pool[-1], pool[-2]]})
        pool.append(f"g{index}")
    source = {
        "kind": "circuit",
        "inputs": inputs,
        "gates": gates,
        "assertions": [[pool[-1], 0]],
        "relations": [],
        "clauses": [[[inputs[0], 1], [inputs[1], 1]], [[inputs[-1], 0], [pool[-1], 1]]],
    }
    return _rename(source, f"w{relabeling}_") if relabeling else source


def _cardinality(size: int, relabeling: int = 0) -> dict[str, Any]:
    names = [f"c{i}" for i in range(size)]
    source = {
        "kind": "circuit",
        "inputs": names,
        "gates": [],
        "assertions": [[names[0], 1], [names[1], 1]],
        "relations": [{"kind": "cardinality", "args": names, "min": 2, "max": size - 1}],
        "clauses": [],
    }
    return _rename(source, f"c{relabeling}_") if relabeling else source


def _transition(horizon: int, relabeling: int = 0) -> dict[str, Any]:
    source = {
        "kind": "transition",
        "state": ["q0", "q1"],
        "inputs": ["u0", "u1"],
        "gates": [
            {"op": "xor", "out": "mix", "args": ["q0", "u0"]},
            {"op": "and", "out": "carry", "args": ["q1", "u1"]},
        ],
        "next_state": [["q0", "mix"], ["q1", "carry"]],
        "horizon": horizon,
        "initial": [["q0", 0], ["q1", 1]],
        "input_assertions": [[0, "u0", 1], [horizon - 1, "u1", 0]],
        "final": [["q0", 1 if horizon % 2 else 0]],
        "relations": [],
        "clauses": [],
    }
    return _rename(source, f"t{relabeling}_") if relabeling else source


def _tseitin(vertices: int, edges: Sequence[tuple[int, int]], relabeling: int = 0, *, inconsistent: bool) -> dict[str, Any]:
    """Cubic-graph XOR system; odd charge is globally inconsistent."""
    edge_names = [f"e{i}" for i in range(len(edges))]
    relations: list[dict[str, Any]] = []
    for vertex in range(vertices):
        incident = [edge_names[index] for index, edge in enumerate(edges) if vertex in edge]
        if len(incident) != 3:
            raise ValueError("Tseitin graph must be cubic")
        relations.append({"kind": "xor", "args": incident, "rhs": 1 if inconsistent and vertex == vertices - 1 else 0})
    source = {
        "kind": "circuit",
        "inputs": edge_names,
        "gates": [],
        "assertions": [],
        "relations": relations,
        "clauses": [],
    }
    return _rename(source, f"z{relabeling}_") if relabeling else source


def _k4(inconsistent: bool, relabeling: int = 0) -> dict[str, Any]:
    return _tseitin(4, tuple((left, right) for left in range(4) for right in range(left + 1, 4)), relabeling, inconsistent=inconsistent)


def _k33(inconsistent: bool, relabeling: int = 0) -> dict[str, Any]:
    edges = tuple((left, 3 + right) for left in range(3) for right in range(3))
    return _tseitin(6, edges, relabeling, inconsistent=inconsistent)


def _prism(vertices: int, inconsistent: bool, relabeling: int = 0) -> dict[str, Any]:
    if vertices % 2:
        raise ValueError("prism requires an even vertex count")
    ring = vertices // 2
    edges = [(index, (index + 1) % ring) for index in range(ring)]
    edges += [(ring + index, ring + (index + 1) % ring) for index in range(ring)]
    edges += [(index, ring + index) for index in range(ring)]
    return _tseitin(vertices, tuple(edges), relabeling, inconsistent=inconsistent)


def _mobius_ladder(vertices: int, inconsistent: bool, relabeling: int = 0) -> dict[str, Any]:
    if vertices % 2:
        raise ValueError("Mobius ladder requires an even vertex count")
    edges = [(index, (index + 1) % vertices) for index in range(vertices)]
    edges += [(index, index + vertices // 2) for index in range(vertices // 2)]
    return _tseitin(vertices, tuple(edges), relabeling, inconsistent=inconsistent)
def _fixed_workload() -> list[dict[str, Any]]:
    """Return the complete split before any policy state is constructed."""
    specs: list[tuple[str, str, str, int, int, Mapping[str, Any]]] = [
        ("train-tseitin-k4-unsat", "tseitin-k4", "train", 4, 0, _k4(True)),
        ("train-tseitin-k33-sat", "tseitin-k33", "train", 6, 0, _k33(False)),
        ("train-tseitin-k33-unsat-relabeled", "tseitin-k33", "train", 6, 1, _k33(True, 1)),
        ("train-wasteful-5", "wasteful", "train", 5, 0, _wasteful(5)),
        ("train-cardinality-5", "cardinality", "train", 5, 0, _cardinality(5)),
        ("train-transition-2", "transition", "train", 2, 0, _transition(2)),
        ("select-tseitin-k4-sat", "tseitin-k4", "selection", 4, 1, _k4(False, 1)),
        ("select-tseitin-k33-unsat", "tseitin-k33", "selection", 6, 2, _k33(True, 2)),
        ("select-parity-7", "parity", "selection", 7, 0, _parity(7)),
        ("select-transition-3", "transition", "selection", 3, 0, _transition(3)),
        ("heldout-tseitin-prism-8-unsat", "tseitin-prism", "heldout", 8, 0, _prism(8, True)),
        ("heldout-tseitin-mobius-10-unsat-relabeled", "tseitin-mobius", "heldout", 10, 1, _mobius_ladder(10, True, 1)),
        ("heldout-tseitin-prism-8-sat-relabeled", "tseitin-prism", "heldout", 8, 2, _prism(8, False, 2)),
        ("heldout-wasteful-8", "wasteful", "heldout", 8, 0, _wasteful(8)),
        ("heldout-cardinality-7-relabeled", "cardinality", "heldout", 7, 2, _cardinality(7, 2)),
        ("heldout-transition-4-relabeled", "transition", "heldout", 4, 1, _transition(4, 1)),
        ("refinement-parity-9-unsat-relabeled", "parity", "refinement", 9, 3, _parity(9, 3, inconsistent=True)),
        ("refinement-cardinality-9-relabeled", "cardinality", "refinement", 9, 3, _cardinality(9, 3)),
        ("refinement-transition-5-relabeled", "transition", "refinement", 5, 2, _transition(5, 2)),
        ("refinement-tseitin-prism-12-sat-relabeled", "tseitin-prism", "refinement", 12, 3, _prism(12, False, 3)),
    ]
    records: list[dict[str, Any]] = []
    for ident, family, split, size, relabeling, source in specs:
        spec = _json(source)
        compiled = compile_source(spec)
        compiled_data = _compiled_dict(compiled)
        records.append(
            {
                "id": ident,
                "family": family,
                "split": split,
                "size": size,
                "relabeling": relabeling,
                "source": spec,
                "source_sha256": _digest(spec),
                "compiled": compiled_data,
                "compiled_sha256": str(compiled_data["sha256"]),
                "structural_summary": _structural_summary(compiled_data),
                "_compiled_object": compiled,
            }
        )
    manifest = [{key: value for key, value in row.items() if not key.startswith("_")} for row in records]
    manifest_hash = _digest(manifest)
    for row in records:
        row["manifest_sha256"] = manifest_hash
    return records


def _structural_summary(compiled: Mapping[str, Any]) -> dict[str, int | str]:
    payload = compiled.get("payload", compiled)
    work = payload.get("work", {})
    relations = payload.get("native_relations", [])
    return {
        "kind": str(payload.get("kind", "")),
        "variables": int(payload.get("variables", 0)),
        "clauses": len(payload.get("clauses", [])),
        "relations": len(relations),
        "gates": int(work.get("gates", 0)),
        "horizon": int(work.get("horizon", 0)),
    }


def structural_selector(compiled: Any) -> str:
    """Declared nonlearned selector; verifier reimplements this formula."""
    summary = _structural_summary(_compiled_dict(compiled))
    if summary["relations"]:
        return "algebraic-1-controller" if int(summary["variables"]) >= 12 else "algebraic-1"
    if summary["kind"] == "transition" or int(summary["gates"]) >= 7:
        return "conflict-controller"
    return "conflict"


def _receipt_work(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    work = receipt.get("resource_ledger", receipt.get("work", {}))
    return work if isinstance(work, Mapping) else {}


def _compact_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Retain proof/state evidence while compressing the large terminal field copy."""
    compact = {
        str(key): _json(value)
        for key, value in receipt.items()
        if str(key) != "terminal_descriptor"
    }
    terminal = receipt.get("terminal_descriptor")
    if not isinstance(terminal, Mapping):
        raise RuntimeError("solver receipt lacks terminal descriptor")
    raw = _canonical(_json(terminal))
    compressed = zlib.compress(raw, level=9)
    compact["terminal_descriptor_archive"] = {
        "codec": "zlib-json-v1",
        "raw_bytes": len(raw),
        "compressed_bytes": len(compressed),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "payload_b64": base64.b64encode(compressed).decode("ascii"),
    }

    return compact

def _request_stream(
    workload: Sequence[Mapping[str, Any]],
    *,
    permutation_index: int,
    seed: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    source_indices = list(range(len(workload)))
    random.Random(seed).shuffle(source_indices)
    base_order = [str(workload[index]["id"]) for index in source_indices]
    requests: list[dict[str, Any]] = []
    ordinal = 0
    for cycle in range(REPETITIONS):
        for position, source_index in enumerate(source_indices):
            rotation = (ordinal + permutation_index) % len(STRATEGIES)
            requests.append(
                {
                    "request_id": f"p{permutation_index}:c{cycle}:s{position}",
                    "ordinal": ordinal,
                    "cycle": cycle,
                    "cohort": COHORTS[cycle],
                    "cycle_position": position,
                    "source_index": source_index,
                    "source_id": str(workload[source_index]["id"]),
                    "source_sha256": str(workload[source_index]["compiled_sha256"]),
                    "budget": BUDGETS[source_index % len(BUDGETS)],
                    "strategy_execution_order": list(STRATEGIES[rotation:] + STRATEGIES[:rotation]),
                }
            )
            ordinal += 1
    return base_order, requests


def _execute_case(
    policy: PolicyState,
    source: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    strategy: str,
) -> tuple[PolicyState, dict[str, Any]]:
    wrapper_started = time.perf_counter_ns()
    compile_started = time.perf_counter_ns()
    compiled = compile_source(source["source"])
    compile_elapsed_ns = time.perf_counter_ns() - compile_started
    if str(_compiled_dict(compiled)["sha256"]) != source["compiled_sha256"]:
        raise RuntimeError(f"fresh compile drifted for {source['id']}")

    requested_method: str | None
    learn = strategy == "adaptive"
    if strategy == "adaptive":
        requested_method = None
    elif strategy == "structural":
        requested_method = structural_selector(compiled)
    else:
        requested_method = strategy

    state_before = _state_dict(policy)
    state_sha256_before = _state_sha(policy, state_before)
    solve_started = time.perf_counter_ns()
    next_policy, raw_receipt = solve_and_learn(
        policy,
        compiled,
        budget=int(request["budget"]),
        learn=learn,
        method=requested_method,
    )
    solve_elapsed_ns = time.perf_counter_ns() - solve_started

    checkpoint_started = time.perf_counter_ns()
    checkpoint_descriptor = _state_dict(next_policy)
    checkpoint_payload = _canonical(checkpoint_descriptor)
    restored = PolicyState.from_dict(json.loads(checkpoint_payload.decode("utf-8")))
    checkpoint_elapsed_ns = time.perf_counter_ns() - checkpoint_started
    wrapper_elapsed_ns = time.perf_counter_ns() - wrapper_started
    state_after = _state_dict(restored)
    state_sha256_after = _state_sha(restored, state_after)
    if checkpoint_descriptor != state_after:
        raise RuntimeError(f"policy checkpoint round-trip drifted for {strategy}")

    receipt = _compact_receipt(raw_receipt)
    selected_method = str(receipt.get("method"))
    if requested_method is not None and selected_method != requested_method:
        raise RuntimeError(
            f"explicit strategy {strategy} selected {selected_method}, expected {requested_method}"
        )
    attributed = compile_elapsed_ns + solve_elapsed_ns + checkpoint_elapsed_ns
    return restored, {
        "request_id": str(request["request_id"]),
        "ordinal": int(request["ordinal"]),
        "cycle": int(request["cycle"]),
        "cohort": str(request["cohort"]),
        "cycle_position": int(request["cycle_position"]),
        "source_id": str(source["id"]),
        "source_sha256": str(source["compiled_sha256"]),
        "budget": int(request["budget"]),
        "strategy": strategy,
        "requested_method": requested_method,
        "selected_method": selected_method,
        "learn": learn,
        "state_sha256_before": state_sha256_before,
        "state_sha256_after": state_sha256_after,
        "state_changed": state_sha256_before != state_sha256_after,
        "checkpoint_descriptor_sha256": hashlib.sha256(checkpoint_payload).hexdigest(),
        "component_elapsed_ns": {
            "compile": int(compile_elapsed_ns),
            "solve_select_audit_learn": int(solve_elapsed_ns),
            "checkpoint_reload": int(checkpoint_elapsed_ns),
            "unattributed_wrapper": int(wrapper_elapsed_ns - attributed),
        },
        "wrapper_elapsed_ns": int(wrapper_elapsed_ns),
        "receipt": receipt,
    }


def _sum_work(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        receipt = row.get("receipt", {})
        work = _receipt_work(receipt if isinstance(receipt, Mapping) else {})
        for key, value in work.items():
            if isinstance(value, bool):
                continue
            try:
                totals[str(key)] = totals.get(str(key), 0) + int(value)
            except (TypeError, ValueError):
                continue
    return totals


def _distribution(values: Sequence[int]) -> dict[str, Any]:
    if not values:
        raise ValueError("distribution requires at least one value")
    ordered = sorted(int(value) for value in values)

    def percentile(percent: int) -> int:
        index = max(0, (percent * len(ordered) + 99) // 100 - 1)
        return ordered[index]

    return {
        "values": [int(value) for value in values],
        "count": len(values),
        "min": ordered[0],
        "p50": percentile(50),
        "p90": percentile(90),
        "p99": percentile(99),
        "max": ordered[-1],
        "mean_floor": sum(ordered) // len(ordered),
    }


def _aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    methods: dict[str, int] = {}
    phases: dict[str, int] = {}
    cumulative: list[dict[str, Any]] = []
    elapsed = 0
    completed = 0
    latencies: list[int] = []
    solver_elapsed: list[int] = []
    for row in rows:
        receipt = row["receipt"]
        status = str(receipt["status"])
        method = str(receipt["method"])
        selection = receipt.get("selection", {})
        phase = str(selection.get("phase", "fixed")) if isinstance(selection, Mapping) else "fixed"
        statuses[status] = statuses.get(status, 0) + 1
        methods[method] = methods.get(method, 0) + 1
        phases[phase] = phases.get(phase, 0) + 1
        latency = int(row["wrapper_elapsed_ns"])
        latencies.append(latency)
        solver_elapsed.append(int(receipt["decision_cost_ns"]))
        elapsed += latency
        if status in {"sat", "unsat"}:
            completed += 1
        cumulative.append(
            {
                "request_id": str(row["request_id"]),
                "ordinal": int(row["ordinal"]),
                "completed": completed,
                "elapsed_ns": elapsed,
            }
        )
    return {
        "requests": len(rows),
        "completed": completed,
        "completion_rate": {"numerator": completed, "denominator": len(rows)},
        "status_counts": dict(sorted(statuses.items())),
        "method_counts": dict(sorted(methods.items())),
        "selection_phase_counts": dict(sorted(phases.items())),
        "elapsed_ns": elapsed,
        "per_request_elapsed_ns": _distribution(latencies),
        "solver_decision_cost_ns": _distribution(solver_elapsed),
        "work": _sum_work(rows),
        "cumulative": cumulative,
    }

def _sliced_aggregates(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    def grouped(
        key_of: Any,
    ) -> dict[str, Any]:
        keys = sorted(
            {
                str(key_of(row))
                for strategy_rows in rows.values()
                for row in strategy_rows
            },
            key=lambda value: tuple(
                int(part) if part.isdigit() else part
                for part in value.split(":")
            ),
        )
        result: dict[str, Any] = {}
        for key in keys:
            members = {
                strategy: [
                    row
                    for row in strategy_rows
                    if str(key_of(row)) == key
                ]
                for strategy, strategy_rows in rows.items()
            }
            result[key] = {
                "strategies": {
                    strategy: _aggregate(strategy_rows)
                    for strategy, strategy_rows in members.items()
                },
                "comparisons": {
                    baseline: _paired_comparison(
                        members["adaptive"],
                        members[baseline],
                        baseline=baseline,
                    )
                    for baseline in STRATEGIES
                    if baseline != "adaptive"
                },
            }
        return result

    return {
        "cohorts": grouped(lambda row: row["cohort"]),
        "budget_classes": grouped(
            lambda row: row["receipt"]["context"]["budget_class"]
        ),
        "structural_contexts": grouped(
            lambda row: row["receipt"]["context"][
                "structural_context_key"
            ]
        ),
        "context_budget_classes": grouped(
            lambda row: (
                f"{row['receipt']['context']['structural_context_key']}:"
                f"{row['receipt']['context']['budget_class']}"
            )
        ),
    }


def _paired_comparison(
    adaptive_rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    *,
    baseline: str,
) -> dict[str, Any]:
    if len(adaptive_rows) != len(baseline_rows):
        raise ValueError(f"paired row count differs for {baseline}")
    prefixes: list[dict[str, Any]] = []
    adaptive_elapsed = 0
    baseline_elapsed = 0
    adaptive_completed = 0
    baseline_completed = 0
    mismatches: list[str] = []
    adaptive_faster_requests = 0
    for adaptive, reference in zip(adaptive_rows, baseline_rows, strict=True):
        if (
            adaptive["request_id"] != reference["request_id"]
            or adaptive["source_sha256"] != reference["source_sha256"]
            or adaptive["budget"] != reference["budget"]
        ):
            raise ValueError(f"paired request identity differs for {baseline}")
        adaptive_status = str(adaptive["receipt"]["status"])
        baseline_status = str(reference["receipt"]["status"])
        if (
            adaptive_status in {"sat", "unsat"}
            and baseline_status in {"sat", "unsat"}
            and adaptive_status != baseline_status
        ):
            mismatches.append(str(adaptive["request_id"]))
        adaptive_elapsed += int(adaptive["wrapper_elapsed_ns"])
        baseline_elapsed += int(reference["wrapper_elapsed_ns"])
        adaptive_completed += int(adaptive_status in {"sat", "unsat"})
        baseline_completed += int(baseline_status in {"sat", "unsat"})
        adaptive_faster_requests += int(
            int(adaptive["wrapper_elapsed_ns"]) <= int(reference["wrapper_elapsed_ns"])
        )
        prefixes.append(
            {
                "request_id": str(adaptive["request_id"]),
                "ordinal": int(adaptive["ordinal"]),
                "adaptive_completed": adaptive_completed,
                "baseline_completed": baseline_completed,
                "adaptive_elapsed_ns": adaptive_elapsed,
                "baseline_elapsed_ns": baseline_elapsed,
                "completion_noninferior": adaptive_completed >= baseline_completed,
                "elapsed_noninferior": adaptive_elapsed <= baseline_elapsed,
            }
        )
    stable_break_even_index: int | None = None
    for index in range(len(prefixes)):
        if all(
            bool(prefix["completion_noninferior"]) and bool(prefix["elapsed_noninferior"])
            for prefix in prefixes[index:]
        ):
            stable_break_even_index = index
            break
    final = prefixes[-1]
    completion_delta = int(final["adaptive_completed"]) - int(final["baseline_completed"])
    elapsed_delta = int(final["adaptive_elapsed_ns"]) - int(final["baseline_elapsed_ns"])
    if completion_delta > 0:
        outcome = "adaptive-completes-more"
    elif completion_delta < 0:
        outcome = "baseline-completes-more"
    elif elapsed_delta < 0:
        outcome = "adaptive-faster-at-equal-completion"
    elif elapsed_delta > 0:
        outcome = "baseline-faster-at-equal-completion"
    else:
        outcome = "equal"
    return {
        "baseline": baseline,
        "requests": len(prefixes),
        "pair_identity_preserved": True,
        "decided_verdict_mismatches": mismatches,
        "completion_delta": completion_delta,
        "elapsed_delta_ns": elapsed_delta,
        "adaptive_faster_or_equal_requests": adaptive_faster_requests,
        "outcome_completion_first": outcome,
        "observed_stable_break_even_ordinal": stable_break_even_index,
        "observed_stable_break_even_request_id": (
            prefixes[stable_break_even_index]["request_id"]
            if stable_break_even_index is not None
            else None
        ),
        "break_even_definition": (
            "first observed prefix after which adaptive maintains at least baseline cumulative "
            "completion and no greater cumulative wrapper elapsed time; no extrapolation"
        ),
        "prefixes": prefixes,
    }


def _run_permutation(
    workload: Sequence[Mapping[str, Any]],
    *,
    permutation_index: int,
    seed: int,
) -> dict[str, Any]:
    base_order, requests = _request_stream(
        workload,
        permutation_index=permutation_index,
        seed=seed,
    )
    policies = {strategy: initial_policy() for strategy in STRATEGIES}
    initial_descriptors = {
        strategy: _state_dict(policy)
        for strategy, policy in policies.items()
    }
    initial_hashes = {
        strategy: _state_sha(policy, initial_descriptors[strategy])
        for strategy, policy in policies.items()
    }
    rows: dict[str, list[dict[str, Any]]] = {
        strategy: [] for strategy in STRATEGIES
    }
    by_id = {str(source["id"]): source for source in workload}
    restart_boundary: dict[str, Any] | None = None
    for request in requests:
        if (
            request["cohort"] == "restart-continuation"
            and restart_boundary is None
        ):
            boundary_rows: dict[str, Any] = {}
            for strategy in STRATEGIES:
                before = _state_dict(policies[strategy])
                before_sha = _state_sha(policies[strategy], before)
                payload = _canonical(before)
                restored = PolicyState.from_dict(
                    json.loads(payload.decode("utf-8"))
                )
                after = _state_dict(restored)
                after_sha = _state_sha(restored, after)
                if before != after or before_sha != after_sha:
                    raise RuntimeError(
                        f"{strategy}: restart boundary changed policy"
                    )
                policies[strategy] = restored
                boundary_rows[strategy] = {
                    "state_sha256_before": before_sha,
                    "state_sha256_after": after_sha,
                    "descriptor_sha256": hashlib.sha256(payload).hexdigest(),
                    "state_preserved": True,
                }
            restart_boundary = {
                "before_request_id": str(request["request_id"]),
                "before_ordinal": int(request["ordinal"]),
                "strategies": boundary_rows,
                "all_states_preserved": True,
            }
        source = by_id[str(request["source_id"])]
        for strategy in request["strategy_execution_order"]:
            policies[strategy], row = _execute_case(
                policies[strategy],
                source,
                request,
                strategy=strategy,
            )
            rows[strategy].append(row)
    if restart_boundary is None:
        raise RuntimeError("restart-continuation boundary was not exercised")
    aggregates = {
        strategy: _aggregate(rows[strategy])
        for strategy in STRATEGIES
    }
    comparisons = {
        baseline: _paired_comparison(rows["adaptive"], rows[baseline], baseline=baseline)
        for baseline in STRATEGIES
        if baseline != "adaptive"
    }
    return {
        "permutation_index": permutation_index,
        "seed": seed,
        "base_order": base_order,
        "requests": requests,
        "cold_start": {
            "state_sha256": initial_hashes["adaptive"],
            "all_strategies_equal": len(set(initial_hashes.values())) == 1,
        },
        "strategies": {
            strategy: {
                "initial_state_sha256": initial_hashes[strategy],
                "rows": rows[strategy],
                "aggregate": aggregates[strategy],
                "final_policy": _state_dict(policies[strategy]),
                "final_state_sha256": _state_sha(policies[strategy], _state_dict(policies[strategy])),
            }
            for strategy in STRATEGIES
        },
        "comparisons": comparisons,
        "restart_boundary": restart_boundary,
        "slices": _sliced_aggregates(rows),
    }


def run_scenario(output: str | Path | None = None) -> dict[str, Any]:
    """Run paired cold-start repeated workloads and optionally write the JSON receipt."""
    preparation_started = time.perf_counter_ns()
    workload = _fixed_workload()
    manifest = [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in workload
    ]
    manifest_hash = _digest(manifest)
    initial = initial_policy()
    initial_descriptor = _state_dict(initial)
    initial_hash = _state_sha(initial, initial_descriptor)
    preparation_elapsed_ns = time.perf_counter_ns() - preparation_started

    runs = [
        _run_permutation(workload, permutation_index=index, seed=seed)
        for index, seed in enumerate(PERMUTATION_SEEDS)
    ]
    pooled_rows = {
        strategy: [
            row
            for run in runs
            for row in run["strategies"][strategy]["rows"]
        ]
        for strategy in STRATEGIES
    }
    pooled_aggregates = {
        strategy: _aggregate(pooled_rows[strategy])
        for strategy in STRATEGIES
    }
    pooled_comparisons = {
        baseline: _paired_comparison(
            pooled_rows["adaptive"],
            pooled_rows[baseline],
            baseline=baseline,
        )
        for baseline in STRATEGIES
        if baseline != "adaptive"
    }
    pooled_slices = _sliced_aggregates(pooled_rows)
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "configuration": {
            "methods": list(METHODS),
            "strategies": list(STRATEGIES),
            "permutation_seeds": list(PERMUTATION_SEEDS),
            "repetitions": REPETITIONS,
            "budgets": list(BUDGETS),
            "cohorts": list(COHORTS),
            "cohort_by_cycle": {
                str(index): cohort
                for index, cohort in enumerate(COHORTS)
            },
            "budget_assignment": "source manifest index modulo three; fixed across repetitions and permutations",
            "selector": (
                "relations=>algebraic-1[-controller for variables>=12]; "
                "transition or gates>=7=>conflict-controller; otherwise conflict"
            ),
            "adaptive_exploration": (
                "declared structural incumbent; one unseen challenger at "
                "context epoch 1 and every 4 thereafter; completion-first "
                "empirical use between challengers; stale reevaluation at 24"
            ),
            "comparison_rule": (
                "paired equal source/order/budget; compare completion first, then full-wrapper "
                "elapsed; retain raw request distributions and observed prefixes"
            ),
            "timed_boundary": (
                "fresh source compile + selection/solve/audit/optional learning + canonical "
                "policy serialization and PolicyState reload"
            ),
            "adaptive_learning": True,
            "baseline_learning": False,
            "strategy_order": "rotated once per request to distribute host-order effects",
            "cold_start_per_permutation": True,
            "restart_boundary": (
                "canonical policy descriptor reload immediately before cycle 2"
            ),
        },
        "workload_manifest_sha256": manifest_hash,
        "workload": manifest,
        "policy": {
            "initial": initial_descriptor,
            "initial_state_sha256": initial_hash,
        },
        "workload_preparation_elapsed_ns": int(preparation_elapsed_ns),
        "runs": runs,
        "aggregate": {
            "strategies": pooled_aggregates,
            "comparisons": pooled_comparisons,
            "slices": pooled_slices,
        },
        "limitations": [
            "This is a finite repeated workload, not a universality or global optimization guarantee.",
            "Wall-clock elapsed_ns is host-dependent; paired completion and exact proof audit are primary.",
            "Only the declared source-order seeds vary workload order; they are not optimization knobs.",
            "Observed break-even is reported only when it occurs in retained prefixes and is never extrapolated.",
            "Fixed and structural baselines retain no observations; every strategy still pays the same policy checkpoint/reload boundary.",
        ],
    }
    report["report_sha256"] = _digest(report)
    if output is not None:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def _print_measurements(report: Mapping[str, Any]) -> None:
    print("computation-policy paired measurements")
    aggregate = report["aggregate"]
    for strategy in STRATEGIES:
        measured = aggregate["strategies"][strategy]
        distribution = measured["per_request_elapsed_ns"]
        print(
            f"aggregate {strategy}:"
            f" requests={measured['requests']}"
            f" completed={measured['completed']}"
            f" elapsed_ns={measured['elapsed_ns']}"
            f" p50_ns={distribution['p50']}"
            f" p90_ns={distribution['p90']}"
            f" p99_ns={distribution['p99']}"
            f" methods={json.dumps(measured['method_counts'], sort_keys=True)}"
        )
    for cohort, sliced in aggregate["slices"]["cohorts"].items():
        adaptive = sliced["strategies"]["adaptive"]
        print(
            f"cohort {cohort}:"
            f" requests={adaptive['requests']}"
            f" completed={adaptive['completed']}"
            f" elapsed_ns={adaptive['elapsed_ns']}"
            f" phases={json.dumps(adaptive['selection_phase_counts'], sort_keys=True)}"
        )
    for run in report["runs"]:
        run_index = run["permutation_index"]
        for baseline, comparison in run["comparisons"].items():
            print(
                f"permutation {run_index} adaptive vs {baseline}:"
                f" outcome={comparison['outcome_completion_first']}"
                f" completion_delta={comparison['completion_delta']}"
                f" elapsed_delta_ns={comparison['elapsed_delta_ns']}"
                f" stable_break_even={comparison['observed_stable_break_even_ordinal']}"
                f" mismatches={len(comparison['decided_verdict_mismatches'])}"
            )
    print(f"report_sha256={report['report_sha256']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    report = run_scenario(args.output)
    _print_measurements(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
