"""Independent verifier for the paired computation-policy report.

This module imports neither the scenario runner nor the production selector. It
rebuilds the source corpus and paired request stream, reconstructs policy
selection and every bounded field update, restores terminal solver states,
audits result evidence, recomputes distributions/comparisons, and proves key
checks fire with re-signed mutations.
"""
from __future__ import annotations
import base64
import copy
import struct

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
import zlib
from typing import Any, Mapping, Sequence, cast

from cassi_computation_policy import METHODS, compile_source
from cassi_constraint_field import ConstraintField
from run_relation_augmentation_comparison import audit_rows
from verify_constraint_field import circuit_accepts, simulate_transition
from verify_hybrid_inference import audit_proof as audit_hybrid_proof
from verify_p_vs_np_clause_field_probe import audit_proof as audit_resolution_proof

SCHEMA = "cassifi.computation-policy-scenario.v4"
PERMUTATION_SEEDS = (20260941, 20260967)
REPETITIONS = 3
BUDGETS = (64, 512, 2000)
COHORTS = ("cold-start", "warm-start", "restart-continuation")
STRATEGIES = ("adaptive", "structural", *METHODS)
POLICY_SCHEMA = "cassifi.computation-policy.v4"
POLICY_LAYOUT = "computation-policy-refined-nine-plane-v4"
POLICY_SHAPE = (9, 320, 6)
POLICY_FIELD_BYTES = 138_240
EVIDENCE_PLANES = (
    "long_support",
    "long_completion",
    "long_elapsed_ns",
    "long_work",
    "recent_support",
    "recent_completion",
    "recent_elapsed_ns",
)
PLANES = (
    *EVIDENCE_PLANES,
    "context_epoch",
    "last_observed_epoch",
)
PLANE_INDEX = {name: index for index, name in enumerate(PLANES)}
BUDGET_CUTOFFS = (64, 512, 4096)
RECENT_LIMIT = 32
LONG_LIMIT = 4096
EXPLORATION_INTERVAL = 4
REEVALUATION_PERIOD = 24
RECENT_DECAY_PERIOD = 16
EPOCH_LIMIT = 1_000_000
OBSERVED_ELAPSED_CAP_NS = 1_000_000_000_000
OBSERVED_WORK_CAP = 1_000_000_000
FEATURE_NAMES = (
    "transition_shape",
    "variable_bucket",
    "clause_bucket",
    "width_bucket",
    "density_bucket",
    "unit_bucket",
    "binary_bucket",
    "relation_bucket",
    "gate_bucket",
    "horizon_bucket",
    "native_xor",
    "native_cardinality",
    "pinned_density_bucket",
    "budget_class",
    "complexity_refinement",
)


class VerificationError(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _rename(source: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    value = json.loads(json.dumps(source))
    kind = str(value["kind"])
    names: set[str] = set()
    names.update(str(name) for name in value.get("inputs", []))
    names.update(str(name) for name in value.get("state", []))
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
        "kind": "circuit", "inputs": names, "gates": [],
        "assertions": [["x0", 1], ["x1", 1], ["x2", 0], ["x3", 0], ["x4", 0 if not inconsistent else 1]],
        "relations": [
            {"kind": "xor", "args": ["x0", "x1", "x2"], "rhs": 0},
            {"kind": "xor", "args": ["x2", "x3", "x4"], "rhs": 0},
        ], "clauses": [],
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
        "kind": "circuit", "inputs": inputs, "gates": gates,
        "assertions": [[pool[-1], 0]], "relations": [],
        "clauses": [[[inputs[0], 1], [inputs[1], 1]], [[inputs[-1], 0], [pool[-1], 1]]],
    }
    return _rename(source, f"w{relabeling}_") if relabeling else source


def _cardinality(size: int, relabeling: int = 0) -> dict[str, Any]:
    names = [f"c{i}" for i in range(size)]
    source = {
        "kind": "circuit", "inputs": names, "gates": [],
        "assertions": [[names[0], 1], [names[1], 1]],
        "relations": [{"kind": "cardinality", "args": names, "min": 2, "max": size - 1}], "clauses": [],
    }
    return _rename(source, f"c{relabeling}_") if relabeling else source


def _transition(horizon: int, relabeling: int = 0) -> dict[str, Any]:
    source = {
        "kind": "transition", "state": ["q0", "q1"], "inputs": ["u0", "u1"],
        "gates": [
            {"op": "xor", "out": "mix", "args": ["q0", "u0"]},
            {"op": "and", "out": "carry", "args": ["q1", "u1"]},
        ], "next_state": [["q0", "mix"], ["q1", "carry"]], "horizon": horizon,
        "initial": [["q0", 0], ["q1", 1]],
        "input_assertions": [[0, "u0", 1], [horizon - 1, "u1", 0]],
        "final": [["q0", 1 if horizon % 2 else 0]], "relations": [], "clauses": [],
    }
    return _rename(source, f"t{relabeling}_") if relabeling else source

def _tseitin(vertices: int, edges: Sequence[tuple[int, int]], relabeling: int = 0, *, inconsistent: bool) -> dict[str, Any]:
    edge_names = [f"e{i}" for i in range(len(edges))]
    relations: list[dict[str, Any]] = []
    for vertex in range(vertices):
        incident = [edge_names[index] for index, edge in enumerate(edges) if vertex in edge]
        if len(incident) != 3:
            raise ValueError("Tseitin graph must be cubic")
        relations.append({"kind": "xor", "args": incident, "rhs": 1 if inconsistent and vertex == vertices - 1 else 0})
    source = {"kind": "circuit", "inputs": edge_names, "gates": [], "assertions": [], "relations": relations, "clauses": []}
    return _rename(source, f"z{relabeling}_") if relabeling else source


def _k4(inconsistent: bool, relabeling: int = 0) -> dict[str, Any]:
    edges = tuple((left, right) for left in range(4) for right in range(left + 1, 4))
    return _tseitin(4, edges, relabeling, inconsistent=inconsistent)


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


def _workload() -> list[dict[str, Any]]:
    rows: list[tuple[str, str, str, int, int, Mapping[str, Any]]] = [
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
    rows_out: list[dict[str, Any]] = []
    for ident, family, split, size, relabeling, source in rows:
        spec = _json(source)
        compiled = _json(compile_source(spec).as_dict())
        rows_out.append({
            "id": ident, "family": family, "split": split, "size": size, "relabeling": relabeling,
            "source": spec, "source_sha256": _digest(spec), "compiled": compiled,
            "compiled_sha256": str(compiled["sha256"]), "structural_summary": _structural_summary(compiled),
        })
    manifest_hash = _digest(rows_out)
    for row in rows_out:
        row["manifest_sha256"] = manifest_hash
    return rows_out


def _structural_summary(compiled: Mapping[str, Any]) -> dict[str, int | str]:
    work = compiled.get("work", {})
    return {
        "kind": str(compiled.get("kind", "")), "variables": int(compiled.get("variables", 0)),
        "clauses": len(compiled.get("clauses", [])), "relations": len(compiled.get("native_relations", [])),
        "gates": int(work.get("gates", 0)), "horizon": int(work.get("horizon", 0)),
    }


def structural_selector(compiled: Mapping[str, Any]) -> str:
    summary = _structural_summary(compiled)
    if summary["relations"]:
        return "algebraic-1-controller" if int(summary["variables"]) >= 12 else "algebraic-1"
    if summary["kind"] == "transition" or int(summary["gates"]) >= 7:
        return "conflict-controller"
    return "conflict"


def _field_index(plane: str, context: int, method: int) -> int:
    return (PLANE_INDEX[plane] * POLICY_SHAPE[1] + context) * POLICY_SHAPE[2] + method


def _field_bytes(field: Sequence[int]) -> bytes:
    return struct.pack(f"={len(field)}d", *field)


def _field_sha(field: Sequence[int]) -> str:
    digest = hashlib.sha256()
    digest.update(
        _canonical(
            {
                "layout": POLICY_LAYOUT,
                "shape": list(POLICY_SHAPE),
                "dtype": "float64",
            }
        )
    )
    digest.update(_field_bytes(field))
    return digest.hexdigest()


def _descriptor(field: Sequence[int]) -> dict[str, Any]:
    raw = _field_bytes(field)
    return {
        "schema": POLICY_SCHEMA,
        "layout": POLICY_LAYOUT,
        "shape": list(POLICY_SHAPE),
        "dtype": "float64",
        "field_b64": base64.b64encode(raw).decode("ascii"),
        "state_sha256": _field_sha(field),
    }


def _decode_policy(value: Any) -> list[int]:
    required = {"schema", "layout", "shape", "dtype", "field_b64", "state_sha256"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise VerificationError("policy descriptor keys are invalid")
    require(value["schema"] == POLICY_SCHEMA, "policy schema mismatch")
    require(value["layout"] == POLICY_LAYOUT, "policy layout mismatch")
    require(value["shape"] == list(POLICY_SHAPE), "policy shape mismatch")
    require(value["dtype"] == "float64", "policy dtype mismatch")
    encoded = value["field_b64"]
    if not isinstance(encoded, str):
        raise VerificationError("policy field encoding is not text")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise VerificationError("policy field base64 is invalid") from exc
    require(base64.b64encode(raw).decode("ascii") == encoded, "policy field base64 is noncanonical")
    require(len(raw) == POLICY_FIELD_BYTES, "policy field byte count mismatch")
    count = POLICY_SHAPE[0] * POLICY_SHAPE[1] * POLICY_SHAPE[2]
    unpacked = struct.unpack(f"={count}d", raw)
    field: list[int] = []
    for item in unpacked:
        require(math.isfinite(item) and item >= 0 and item.is_integer(), "policy cell is not an exact nonnegative integer")
        field.append(int(item))
    require(value["state_sha256"] == _field_sha(field), "policy state digest mismatch")
    for context in range(POLICY_SHAPE[1]):
        context_epoch = field[
            _field_index("context_epoch", context, 0)
        ]
        require(
            context_epoch <= EPOCH_LIMIT,
            "context epoch exceeds bound",
        )
        for method in range(1, POLICY_SHAPE[2]):
            require(
                field[_field_index("context_epoch", context, method)] == 0,
                "context epoch uses noncanonical method cell",
            )
        for method in range(POLICY_SHAPE[2]):
            long_support = field[_field_index("long_support", context, method)]
            long_completion = field[_field_index("long_completion", context, method)]
            long_elapsed = field[_field_index("long_elapsed_ns", context, method)]
            long_work = field[_field_index("long_work", context, method)]
            recent_support = field[_field_index("recent_support", context, method)]
            recent_completion = field[_field_index("recent_completion", context, method)]
            recent_elapsed = field[_field_index("recent_elapsed_ns", context, method)]
            last_observed = field[
                _field_index("last_observed_epoch", context, method)
            ]
            require(
                last_observed <= context_epoch,
                "method observation epoch exceeds context epoch",
            )
            require(
                (long_support == 0) == (last_observed == 0),
                "method support and observation epoch disagree",
            )
            require(long_completion <= long_support, "long completion exceeds support")
            require(recent_completion <= recent_support, "recent completion exceeds support")
            require(long_support <= LONG_LIMIT, "long window exceeds bound")
            require(recent_support <= RECENT_LIMIT, "recent window exceeds bound")
            if long_support == 0:
                require(long_elapsed == 0 and long_work == 0, "unsupported long cell carries cost")
            else:
                require(
                    long_support <= long_elapsed <= long_support * OBSERVED_ELAPSED_CAP_NS,
                    "long elapsed total violates observation bounds",
                )
                require(
                    long_work <= long_support * OBSERVED_WORK_CAP,
                    "long work total violates observation bounds",
                )
            if recent_support == 0:
                require(recent_elapsed == 0, "unsupported recent cell carries cost")
            else:
                require(
                    recent_support <= recent_elapsed <= recent_support * OBSERVED_ELAPSED_CAP_NS,
                    "recent elapsed total violates observation bounds",
                )
    return field


def _receipt_work(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    work = receipt.get("resource_ledger", receipt.get("work", {}))
    return work if isinstance(work, Mapping) else {}


def _sum_work(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        receipt = row.get("receipt")
        if not isinstance(receipt, Mapping):
            raise VerificationError("aggregate row lacks receipt")
        for key, value in _receipt_work(receipt).items():
            if isinstance(value, bool) or isinstance(value, Mapping):
                continue
            if not isinstance(value, int):
                raise VerificationError(f"aggregate work {key} is not integer")
            totals[str(key)] = totals.get(str(key), 0) + value
    return totals


def _bucket(value: int, cutoffs: Sequence[int]) -> int:
    for index, cutoff in enumerate(cutoffs):
        if value <= cutoff:
            return index
    return len(cutoffs)


def _context(compiled: Mapping[str, Any], budget: int) -> dict[str, Any]:
    clauses = compiled["clauses"]
    variables = int(compiled["variables"])
    clause_count = len(clauses)
    max_width = max((len(row) for row in clauses), default=0)
    literal_count = sum(len(row) for row in clauses)
    unit_count = sum(len(row) == 1 for row in clauses)
    binary_count = sum(len(row) == 2 for row in clauses)
    work = compiled["work"]
    native_relations = compiled["native_relations"]
    native_xor = int(any(row.get("kind") == "xor" for row in native_relations))
    native_cardinality = int(any(row.get("kind") == "cardinality" for row in native_relations))
    pinned_density_bucket = min(3, (unit_count * 4) // max(1, variables))
    detailed = (
        int(compiled.get("kind") == "transition"),
        _bucket(variables, (1, 2, 4, 8, 16, 32, 64)),
        _bucket(clause_count, (0, 1, 2, 4, 8, 16, 32, 64, 128, 256)),
        _bucket(max_width, (0, 1, 2, 3, 4, 8, 16, 32)),
        _bucket(literal_count, (0, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)),
        _bucket(unit_count, (0, 1, 2, 4, 8, 16, 32, 64)),
        _bucket(binary_count, (0, 1, 2, 4, 8, 16, 32, 64, 128)),
        _bucket(int(work.get("relation_clauses", 0)), (0, 1, 2, 4, 8, 16, 32)),
        _bucket(int(work.get("gate_clauses", 0)), (0, 1, 2, 4, 8, 16, 32, 64)),
        _bucket(int(work.get("horizon", 0)), (0, 1, 2, 4, 8, 16, 32, 64)),
    )
    complexity_refinement = int(
        variables > 4 or clause_count > 8 or max_width > 3
        or int(work.get("horizon", 0)) > 2
    )
    budget_class = 1 + _bucket(budget, BUDGET_CUTOFFS)
    feature_values = (
        *detailed,
        native_xor,
        native_cardinality,
        pinned_density_bucket,
        budget_class,
        complexity_refinement,
    )
    structural_key = (
        ((detailed[0] * 2 + native_xor) * 2 + native_cardinality) * 4
        + pinned_density_bucket
    ) * 2 + complexity_refinement
    key = structural_key * 5 + budget_class
    return {
        "schema": "cassifi.computation-context.v3",
        "features": {
            name: int(value)
            for name, value in zip(FEATURE_NAMES, feature_values, strict=True)
        },
        "feature_vector": [int(value) for value in feature_values],
        "structural_context_key": int(structural_key),
        "budget_class": int(budget_class),
        "budget_cutoffs": list(BUDGET_CUTOFFS),
        "context_key": int(key),
    }


def _field_value(field: Sequence[int], plane: str, context: int, method: int) -> int:
    return int(field[_field_index(plane, context, method)])


def _rate_compare(
    numerator_left: int,
    denominator_left: int,
    numerator_right: int,
    denominator_right: int,
) -> int:
    if denominator_left == 0 or denominator_right == 0:
        return (denominator_left > 0) - (denominator_right > 0)
    left = numerator_left * denominator_right
    right = numerator_right * denominator_left
    return (left > right) - (left < right)


def _selection_better(
    field: Sequence[int],
    context: int,
    left: int,
    right: int,
) -> bool:
    long_s_l = _field_value(field, "long_support", context, left)
    long_s_r = _field_value(field, "long_support", context, right)
    long_c_l = _field_value(field, "long_completion", context, left)
    long_c_r = _field_value(field, "long_completion", context, right)
    recent_s_l = _field_value(field, "recent_support", context, left)
    recent_s_r = _field_value(field, "recent_support", context, right)
    recent_c_l = _field_value(field, "recent_completion", context, left)
    recent_c_r = _field_value(field, "recent_completion", context, right)
    for completed_left, support_left, completed_right, support_right in (
        (recent_c_l, recent_s_l, recent_c_r, recent_s_r),
        (long_c_l, long_s_l, long_c_r, long_s_r),
    ):
        comparison = _rate_compare(
            max(0, completed_left - 1),
            support_left,
            max(0, completed_right - 1),
            support_right,
        )
        if comparison:
            return comparison > 0
        comparison = _rate_compare(
            completed_left,
            support_left,
            completed_right,
            support_right,
        )
        if comparison:
            return comparison > 0
    for plane, support_left, support_right in (
        ("recent_elapsed_ns", recent_s_l, recent_s_r),
        ("long_elapsed_ns", long_s_l, long_s_r),
    ):
        if support_left and support_right:
            comparison = _rate_compare(
                _field_value(field, plane, context, right),
                support_right,
                _field_value(field, plane, context, left),
                support_left,
            )
            if comparison:
                return comparison > 0
    if long_s_l and long_s_r:
        comparison = _rate_compare(
            _field_value(field, "long_work", context, right),
            long_s_r,
            _field_value(field, "long_work", context, left),
            long_s_l,
        )
        if comparison:
            return comparison > 0
    if recent_s_l != recent_s_r:
        return recent_s_l > recent_s_r
    if long_s_l != long_s_r:
        return long_s_l > long_s_r
    return left < right


def _selection_index(field: Sequence[int], context: int, candidates: Sequence[int]) -> int:
    selected = int(candidates[0])
    for candidate_value in candidates[1:]:
        candidate = int(candidate_value)
        if _selection_better(field, context, candidate, selected):
            selected = candidate
    return selected


def _evidence_rows(
    field: Sequence[int],
    context: int,
) -> list[dict[str, Any]]:
    return [
        {
            "method": method,
            **{
                plane: _field_value(
                    field, plane, context, method_index
                )
                for plane in EVIDENCE_PLANES
            },
            "last_observed_epoch": _field_value(
                field,
                "last_observed_epoch",
                context,
                method_index,
            ),
        }
        for method_index, method in enumerate(METHODS)
    ]


def _next_unseen_epoch(epoch: int) -> int:
    if epoch <= 1:
        return 1
    remainder = epoch % EXPLORATION_INTERVAL
    return (
        epoch
        if remainder == 0
        else epoch + EXPLORATION_INTERVAL - remainder
    )



def _support_vector(field: Sequence[int], context: int) -> list[int]:
    return [
        _field_value(field, "long_support", context, index)
        for index in range(len(METHODS))
    ]


def _related_evidence_keys(context: Mapping[str, Any]) -> tuple[int, ...]:
    structural = int(context["structural_context_key"])
    budget_class = int(context["budget_class"])
    sibling = structural ^ 1
    keys = (
        sibling * 5 + budget_class,
        structural * 5,
        sibling * 5,
    )
    require(
        all(0 <= key < POLICY_SHAPE[1] for key in keys),
        "refined policy context is out of bounds",
    )
    return keys

def _first_supported_context(
    field: Sequence[int],
    contexts: Sequence[int],
    candidates: Sequence[int],
) -> int | None:
    for context in contexts:
        if any(
            _field_value(field, "long_support", context, candidate) > 0
            for candidate in candidates
        ):
            return int(context)
    return None

def _selection_payload(
    field: Sequence[int],
    context: Mapping[str, Any],
    *,
    selected: int,
    incumbent: int,
    evidence_key: int,
    phase: str,
    exploration_reason: str | None,
    comparisons: int,
    field_cells_read: int,
) -> dict[str, Any]:
    context_key = int(context["context_key"])
    supports = [
        _field_value(field, "long_support", context_key, index)
        for index in range(len(METHODS))
    ]
    epoch = _field_value(field, "context_epoch", context_key, 0)
    last_observed = [
        _field_value(
            field, "last_observed_epoch", context_key, index
        )
        for index in range(len(METHODS))
    ]
    unseen = [
        index for index, support in enumerate(supports) if support == 0
    ]
    return {
        "schema": "cassifi.computation-selection.v4",
        "method": METHODS[selected],
        "context": dict(context),
        "phase": phase,
        "exploration_reason": exploration_reason,
        "observation_context_key": context_key,
        "evidence_context_key": evidence_key,
        "structural_incumbent": METHODS[incumbent],
        "context_epoch": epoch,
        "exploration_interval": EXPLORATION_INTERVAL,
        "exploration_complete": not unseen,
        "unseen_methods": [METHODS[index] for index in unseen],
        "next_unseen_exploration_epoch": (
            None if not unseen else _next_unseen_epoch(epoch)
        ),
        "reevaluation_period": REEVALUATION_PERIOD,
        "recent_decay_period": RECENT_DECAY_PERIOD,
        "observed_support": supports,
        "checked_completion": [
            _field_value(
                field, "long_completion", context_key, index
            )
            for index in range(len(METHODS))
        ],
        "last_observed_epoch": last_observed,
        "method_age": [
            None
            if support == 0
            else epoch - last_observed[index]
            for index, support in enumerate(supports)
        ],
        "evidence": _evidence_rows(field, evidence_key),
        "work": {
            "field_cells_read": field_cells_read,
            "feature_cells_read": len(context["feature_vector"]),
            "candidate_comparisons": comparisons,
            "operations": 1 if phase != "fixed" else 0,
        },
    }


def _adaptive_selection(
    field: Sequence[int],
    context: Mapping[str, Any],
    compiled: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    context_key = int(context["context_key"])
    supports = _support_vector(field, context_key)
    total_support = sum(supports)
    epoch = _field_value(field, "context_epoch", context_key, 0)
    last_observed = [
        _field_value(
            field, "last_observed_epoch", context_key, index
        )
        for index in range(len(METHODS))
    ]
    unseen = [
        index for index, support in enumerate(supports) if support == 0
    ]
    incumbent = METHODS.index(structural_selector(compiled))
    evidence_key = context_key
    comparisons = 0
    reason: str | None = None
    related_keys = _related_evidence_keys(context)
    related_key = _first_supported_context(
        field, related_keys, tuple(range(len(METHODS)))
    )
    if total_support == 0 and related_key is not None:
        evidence_key = related_key
        related_supports = _support_vector(field, evidence_key)
        observed = tuple(
            index
            for index, support in enumerate(related_supports)
            if support > 0
        )
        selected = _selection_index(field, evidence_key, observed)
        comparisons = max(0, len(observed) - 1)
        phase = (
            "refined-sibling-prior"
            if evidence_key == related_keys[0]
            else "structural-prior"
        )
        reason = "evidence-driven-context-refinement"
    elif total_support == 0:
        selected = incumbent
        phase = "cold-start"
        reason = "declared-structural-incumbent"
    elif unseen and epoch == _next_unseen_epoch(epoch):
        exploration_key = _first_supported_context(
            field, related_keys, unseen
        )
        if exploration_key is not None:
            supported_unseen = tuple(
                candidate
                for candidate in unseen
                if _field_value(
                    field, "long_support", exploration_key, candidate
                )
                > 0
            )
            selected = _selection_index(
                field, exploration_key, supported_unseen
            )
            evidence_key = exploration_key
            comparisons = max(0, len(supported_unseen) - 1)
            reason = "related-evidence-completion-cost"
        else:
            challenger_order = tuple(
                (incumbent + offset) % len(METHODS)
                for offset in range(1, len(METHODS) + 1)
            )
            selected = next(
                candidate
                for candidate in challenger_order
                if candidate in unseen
            )
            reason = "scheduled-unseen-challenger"
        phase = "explore"
    elif (
        not unseen
        and epoch > 0
        and epoch % REEVALUATION_PERIOD == 0
    ):
        selected = min(
            range(len(METHODS)),
            key=lambda index: (
                last_observed[index],
                supports[index],
                index,
            ),
        )
        phase = "reevaluate"
        reason = "stale-method-reevaluation"
    else:
        observed = tuple(
            index
            for index, support in enumerate(supports)
            if support > 0
        )
        selected = _selection_index(field, context_key, observed)
        comparisons = max(0, len(observed) - 1)
        phase = "empirical"
    payload = _selection_payload(
        field,
        context,
        selected=selected,
        incumbent=incumbent,
        evidence_key=evidence_key,
        phase=phase,
        exploration_reason=reason,
        comparisons=comparisons,
        field_cells_read=(
            len(PLANES)
            * len(METHODS)
            * (2 if evidence_key != context_key else 1)
        ),
    )
    return METHODS[selected], payload


def _fixed_selection(
    method: str,
    context: Mapping[str, Any],
    field: Sequence[int],
    compiled: Mapping[str, Any],
) -> dict[str, Any]:
    selected = METHODS.index(method)
    return _selection_payload(
        field,
        context,
        selected=selected,
        incumbent=METHODS.index(structural_selector(compiled)),
        evidence_key=int(context["context_key"]),
        phase="fixed",
        exploration_reason=None,
        comparisons=0,
        field_cells_read=0,
    )


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
                    "strategy_execution_order": list(
                        STRATEGIES[rotation:] + STRATEGIES[:rotation]
                    ),
                }
            )
            ordinal += 1
    return base_order, requests


def _distribution(values: Sequence[int]) -> dict[str, Any]:
    ordered = sorted(int(value) for value in values)
    require(bool(ordered), "distribution is empty")

    def percentile(percent: int) -> int:
        return ordered[max(0, (percent * len(ordered) + 99) // 100 - 1)]

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
    decision_costs: list[int] = []
    for row in rows:
        receipt = cast(Mapping[str, Any], row["receipt"])
        status = str(receipt["status"])
        method = str(receipt["method"])
        selection = cast(Mapping[str, Any], receipt["selection"])
        phase = str(selection["phase"])
        statuses[status] = statuses.get(status, 0) + 1
        methods[method] = methods.get(method, 0) + 1
        phases[phase] = phases.get(phase, 0) + 1
        latency = int(row["wrapper_elapsed_ns"])
        latencies.append(latency)
        decision_costs.append(int(receipt["decision_cost_ns"]))
        elapsed += latency
        completed += int(status in {"sat", "unsat"})
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
        "solver_decision_cost_ns": _distribution(decision_costs),
        "work": _sum_work(rows),
        "cumulative": cumulative,
    }

def _sliced_aggregates(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    def grouped(key_of: Any) -> dict[str, Any]:
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
    require(len(adaptive_rows) == len(baseline_rows), f"{baseline}: paired count mismatch")
    prefixes: list[dict[str, Any]] = []
    adaptive_elapsed = baseline_elapsed = 0
    adaptive_completed = baseline_completed = 0
    mismatches: list[str] = []
    adaptive_faster_requests = 0
    for adaptive, reference in zip(adaptive_rows, baseline_rows, strict=True):
        require(
            adaptive["request_id"] == reference["request_id"]
            and adaptive["source_sha256"] == reference["source_sha256"]
            and adaptive["budget"] == reference["budget"],
            f"{baseline}: paired identity mismatch",
        )
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
    stable: int | None = None
    for index in range(len(prefixes)):
        if all(
            bool(prefix["completion_noninferior"]) and bool(prefix["elapsed_noninferior"])
            for prefix in prefixes[index:]
        ):
            stable = index
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
        "observed_stable_break_even_ordinal": stable,
        "observed_stable_break_even_request_id": (
            prefixes[stable]["request_id"] if stable is not None else None
        ),
        "break_even_definition": (
            "first observed prefix after which adaptive maintains at least baseline cumulative "
            "completion and no greater cumulative wrapper elapsed time; no extrapolation"
        ),
        "prefixes": prefixes,
    }

def _audit(source: Mapping[str, Any], receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    """Audit solver evidence with source replay and independent certificate checkers."""
    nested = receipt.get("result")
    if not isinstance(nested, Mapping):
        raise VerificationError("policy receipt lacks retained constraint result evidence")
    result = cast(Mapping[str, Any], nested)
    compiled = source["compiled"]
    declared = source["source"]
    require(result.get("compiled") == compiled, f"{source['id']}: result is not source-bound")
    hybrid = result.get("hybrid_proof")
    hybrid_checked = None
    if hybrid is not None:
        if not isinstance(hybrid, Mapping):
            raise VerificationError(f"{source['id']}: hybrid proof malformed")
        hybrid_checked = audit_hybrid_proof(compiled["clauses"], hybrid, variables=int(compiled["variables"]))
    if result.get("augmentations"):
        require(hybrid_checked is not None, f"{source['id']}: augmentation lacks a verified derivation")
        augmented = audit_rows(result, result["profile"])
        require(augmented["mismatch_count"] == 0 and augmented["not_entailed_count"] == 0,
                f"{source['id']}: augmentation is not entailed by its verified proof line")
    backend = result.get("backend_clauses")
    if backend is not None:
        expected_backend = compiled["clauses"] + [row["clause"] for row in result.get("augmentations", [])]
        require([sorted(row) for row in backend] == [sorted(row) for row in expected_backend],
                f"{source['id']}: backend contains unauthenticated premises")
    status = str(result.get("status"))
    if status == "sat":
        assignment_value = result.get("assignment")
        witness_value = result.get("witness")
        if not isinstance(assignment_value, list):
            raise VerificationError(f"{source['id']}: SAT assignment missing")
        if not isinstance(witness_value, Mapping):
            raise VerificationError(f"{source['id']}: SAT witness missing")
        assignment = cast(list[Any], assignment_value)
        witness = cast(Mapping[str, Any], witness_value)
        variables = int(compiled["variables"])
        if len(assignment) != variables:
            raise VerificationError(f"{source['id']}: SAT assignment length mismatch")
        bits: list[int] = []
        for value in assignment:
            require(type(value) is int and value in (-1, 1), f"{source['id']}: SAT assignment polarity invalid")
            bits.append(int(value == 1))
        witness_signals_value = compiled.get("witness_signals")
        if not isinstance(witness_signals_value, list):
            raise VerificationError(f"{source['id']}: compiled witness signals missing")
        witness_signals = cast(list[list[Any]], witness_signals_value)
        expected_witness = {
            str(label): bits[int(identifier) - 1]
            for label, identifier in witness_signals
        }
        require(dict(witness) == expected_witness, f"{source['id']}: SAT witness is not bound to assignment")
        kind = str(declared.get("kind"))
        declared = declared.get("source", declared)
        if kind == "circuit":
            inputs = [str(name) for name in declared.get("inputs", [])]
            scope = {name: int(expected_witness[name]) for name in inputs}
            try:
                accepted = circuit_accepts(declared, scope)
            except Exception as exc:  # noqa: BLE001 - independent evaluator failure
                raise VerificationError(f"{source['id']}: circuit witness replay failed: {exc}") from exc
            require(accepted, f"{source['id']}: SAT witness violates the declared circuit")
        elif kind == "transition":
            state_names = [str(name) for name in declared.get("state", [])]
            input_names = [str(name) for name in declared.get("inputs", [])]
            horizon = int(declared["horizon"])
            initial = {name: int(expected_witness[f"{name}@0"]) for name in state_names}
            trace = [
                {name: int(expected_witness[f"{name}@{time}"]) for name in input_names}
                for time in range(horizon)
            ]
            try:
                problems = simulate_transition(declared, initial, trace)
            except Exception as exc:  # noqa: BLE001 - independent evaluator failure
                raise VerificationError(f"{source['id']}: transition witness replay failed: {exc}") from exc
            require(not problems, f"{source['id']}: SAT witness violates transition source: {problems}")
        else:
            raise VerificationError(f"{source['id']}: unsupported source kind")
    elif status == "unsat":
        clauses_value = compiled.get("clauses")
        if not isinstance(clauses_value, list):
            raise VerificationError(f"{source['id']}: compiled clauses missing")
        clauses = cast(list[list[Any]], clauses_value)
        certificates = 0
        resolution_value = result.get("resolution_proof")
        if resolution_value is not None:
            backend_value = result.get("backend_clauses")
            learned_value = result.get("learned_clauses")
            profile_value = result.get("profile")
            if not isinstance(backend_value, list) or not isinstance(learned_value, list) or not isinstance(profile_value, Mapping):
                raise VerificationError(f"{source['id']}: resolution evidence incomplete")
            backend = cast(list[list[Any]], backend_value)
            learned = cast(list[list[int]], learned_value)
            profile = cast(Mapping[str, Any], profile_value)
            resolution = cast(Mapping[str, Any], resolution_value) if isinstance(resolution_value, Mapping) else None
            if resolution is None:
                raise VerificationError(f"{source['id']}: resolution proof malformed")
            original = [tuple(int(literal) for literal in clause) for clause in clauses]
            retained = [tuple(int(literal) for literal in clause) for clause in backend]
            require(retained[: len(original)] == original, f"{source['id']}: backend clauses do not preserve source")
            try:
                audit_resolution_proof(
                    retained,
                    learned,
                    resolution,
                    variables=int(compiled["variables"]),
                    status="unsat",
                    expected_conflicts=len(resolution.get("conflict_derivations", [])),
                    max_learned_clauses=int(profile["max_learned_clauses"]),
                )
            except Exception as exc:  # noqa: BLE001 - independent checker failure
                raise VerificationError(f"{source['id']}: resolution certificate audit failed: {exc}") from exc
            certificates += 1
        if hybrid_checked is not None and hybrid_checked.get("status") == "unsat":
            if not isinstance(hybrid, Mapping):
                raise VerificationError(f"{source['id']}: missing hybrid proof")
            require(hybrid.get("root_line") is not None, f"{source['id']}: missing hybrid refutation root")
            certificates += 1
        require(certificates > 0, f"{source['id']}: UNSAT result lacks an independent certificate")
    elif status == "exhausted":
        require(result.get("witness") is None, f"{source['id']}: exhausted result carries a witness")
        require(result.get("resolution_proof") is None and result.get("hybrid_proof") is None, f"{source['id']}: exhausted result carries a certificate")
    else:
        raise VerificationError(f"{source['id']}: invalid result status")
    return {"checked": True, "status": status, "auditor": "independent-source-and-certificate-auditors"}

def _restore_terminal_descriptor(
    receipt: Mapping[str, Any],
    source: Mapping[str, Any],
) -> None:
    archive = receipt.get("terminal_descriptor_archive")
    required = {"codec", "raw_bytes", "compressed_bytes", "sha256", "payload_b64"}
    if not isinstance(archive, Mapping) or set(archive) != required:
        raise VerificationError(f"{source['id']}: terminal descriptor archive is malformed")
    require(archive["codec"] == "zlib-json-v1", f"{source['id']}: terminal archive codec mismatch")
    encoded = archive["payload_b64"]
    if not isinstance(encoded, str):
        raise VerificationError(f"{source['id']}: terminal archive payload is not text")
    try:
        compressed = base64.b64decode(encoded, validate=True)
        require(
            base64.b64encode(compressed).decode("ascii") == encoded,
            f"{source['id']}: terminal archive base64 is noncanonical",
        )
        require(
            len(compressed) == archive["compressed_bytes"],
            f"{source['id']}: terminal compressed byte count mismatch",
        )
        raw = zlib.decompress(compressed)
    except (ValueError, TypeError, zlib.error) as exc:
        raise VerificationError(f"{source['id']}: terminal archive cannot be decoded") from exc
    require(len(raw) == archive["raw_bytes"], f"{source['id']}: terminal raw byte count mismatch")
    require(
        hashlib.sha256(raw).hexdigest() == archive["sha256"],
        f"{source['id']}: terminal archive digest mismatch",
    )
    try:
        descriptor = json.loads(raw.decode("utf-8"))
        require(_canonical(descriptor) == raw, f"{source['id']}: terminal JSON is noncanonical")
        restored_field, restored = ConstraintField.from_descriptor(descriptor)
        restored_result = restored_field.result(restored)
    except (UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        raise VerificationError(f"{source['id']}: terminal descriptor is invalid") from exc
    nested = cast(Mapping[str, Any], receipt["result"])
    diagnostic = (
        {"assignment", "witness", "resolution_proof", "hybrid_proof"}
        if receipt["status"] == "exhausted"
        else set()
    )
    require(
        {key: value for key, value in restored_result.items() if key not in diagnostic}
        == {key: value for key, value in nested.items() if key not in diagnostic},
        f"{source['id']}: retained result does not follow terminal field",
    )
    require(
        receipt["state_sha256"] == restored_field.state_sha256(restored),
        f"{source['id']}: terminal field digest mismatch",
    )
    require(
        receipt["field_bytes"]
        == restored.nbytes
        <= receipt["peak_field_bytes"]
        <= receipt["max_field_bytes"],
        f"{source['id']}: terminal field capacity ledger mismatch",
    )


def _compress_window(
    field: list[int],
    *,
    context: int,
    method_index: int,
    planes: Sequence[str],
) -> None:
    for plane in planes:
        coordinate = _field_index(plane, context, method_index)
        field[coordinate] //= 2
    prefix = "long" if "long_support" in planes else "recent"
    support = _field_value(
        field, f"{prefix}_support", context, method_index
    )
    completion_name = f"{prefix}_completion"
    if completion_name in planes:
        coordinate = _field_index(
            completion_name, context, method_index
        )
        field[coordinate] = min(support, field[coordinate])
    elapsed_name = f"{prefix}_elapsed_ns"
    if elapsed_name in planes:
        coordinate = _field_index(
            elapsed_name, context, method_index
        )
        elapsed = field[coordinate]
        field[coordinate] = (
            0
            if support == 0
            else min(
                max(support, elapsed),
                support * OBSERVED_ELAPSED_CAP_NS,
            )
        )
    if prefix == "long" and "long_work" in planes:
        coordinate = _field_index(
            "long_work", context, method_index
        )
        retained_work = field[coordinate]
        field[coordinate] = (
            0
            if support == 0
            else min(
                retained_work,
                support * OBSERVED_WORK_CAP,
            )
        )


def _record_observation(
    field: Sequence[int],
    *,
    context: int,
    method_index: int,
    elapsed_ns: int,
    work: int,
    status: str,
) -> tuple[list[int], dict[str, Any]]:
    next_field = list(field)
    retained_elapsed = max(
        1, min(elapsed_ns, OBSERVED_ELAPSED_CAP_NS)
    )
    retained_work = min(work, OBSERVED_WORK_CAP)
    completed = int(status in {"sat", "unsat"})
    epoch_coordinate = _field_index(
        "context_epoch", context, 0
    )
    epoch_before = next_field[epoch_coordinate]
    epoch_compressed = epoch_before >= EPOCH_LIMIT
    if epoch_compressed:
        next_field[epoch_coordinate] = epoch_before // 2
        for candidate in range(len(METHODS)):
            coordinate = _field_index(
                "last_observed_epoch", context, candidate
            )
            next_field[coordinate] //= 2
    epoch_base = next_field[epoch_coordinate]
    epoch_after = epoch_base + 1
    recent_synchronized_decay = (
        epoch_after % RECENT_DECAY_PERIOD == 0
        or any(
            _field_value(
                next_field,
                "recent_support",
                context,
                candidate,
            )
            >= RECENT_LIMIT
            for candidate in range(len(METHODS))
        )
    )
    if recent_synchronized_decay:
        for candidate in range(len(METHODS)):
            _compress_window(
                next_field,
                context=context,
                method_index=candidate,
                planes=(
                    "recent_support",
                    "recent_completion",
                    "recent_elapsed_ns",
                ),
            )
    long_decayed = (
        _field_value(
            next_field,
            "long_support",
            context,
            method_index,
        )
        >= LONG_LIMIT
    )
    if long_decayed:
        _compress_window(
            next_field,
            context=context,
            method_index=method_index,
            planes=(
                "long_support",
                "long_completion",
                "long_elapsed_ns",
                "long_work",
            ),
        )
    before = {
        plane: _field_value(
            next_field, plane, context, method_index
        )
        for plane in EVIDENCE_PLANES
    }
    before["last_observed_epoch"] = _field_value(
        next_field,
        "last_observed_epoch",
        context,
        method_index,
    )
    increments = {
        "long_support": 1,
        "long_completion": completed,
        "long_elapsed_ns": retained_elapsed,
        "long_work": retained_work,
        "recent_support": 1,
        "recent_completion": completed,
        "recent_elapsed_ns": retained_elapsed,
    }
    for plane, increment in increments.items():
        next_field[
            _field_index(plane, context, method_index)
        ] += increment
    next_field[epoch_coordinate] = epoch_after
    next_field[
        _field_index(
            "last_observed_epoch", context, method_index
        )
    ] = epoch_after
    after = {
        plane: _field_value(
            next_field, plane, context, method_index
        )
        for plane in EVIDENCE_PLANES
    }
    after["last_observed_epoch"] = epoch_after
    return next_field, {
        "schema": "cassifi.computation-observation.v3",
        "context_key": context,
        "method": METHODS[method_index],
        "status": status,
        "elapsed_ns_observed": elapsed_ns,
        "elapsed_ns_retained": retained_elapsed,
        "work_observed": work,
        "work_retained": retained_work,
        "elapsed_clipped": elapsed_ns != retained_elapsed,
        "work_clipped": work != retained_work,
        "long_decayed": bool(long_decayed),
        "recent_synchronized_decay": bool(
            recent_synchronized_decay
        ),
        "recent_decay_period": RECENT_DECAY_PERIOD,
        "context_epoch_before": epoch_before,
        "context_epoch_compressed": bool(epoch_compressed),
        "context_epoch_after": epoch_after,
        "before": before,
        "increments": increments,
        "after": after,
    }


def _check_row(
    row: Mapping[str, Any],
    source: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    strategy: str,
    field: Sequence[int],
) -> list[int]:
    label = f"{request['request_id']}/{strategy}"
    for key in (
        "request_id",
        "ordinal",
        "cycle",
        "cohort",
        "cycle_position",
        "budget",
    ):
        require(
            row.get(key) == request[key],
            f"{label}: row {key} mismatch",
        )
    require(row.get("source_id") == source["id"], f"{label}: source id mismatch")
    require(
        row.get("source_sha256") == source["compiled_sha256"] == request["source_sha256"],
        f"{label}: source digest mismatch",
    )
    require(row.get("strategy") == strategy, f"{label}: strategy mismatch")
    adaptive = strategy == "adaptive"
    expected_requested = (
        None
        if adaptive
        else structural_selector(source["compiled"])
        if strategy == "structural"
        else strategy
    )
    require(
        row.get("requested_method") == expected_requested,
        f"{label}: requested method mismatch",
    )
    require(row.get("learn") is adaptive, f"{label}: learning flag mismatch")

    raw_receipt = row.get("receipt")
    if not isinstance(raw_receipt, Mapping):
        raise VerificationError(f"{label}: receipt missing")
    receipt = cast(Mapping[str, Any], raw_receipt)
    require(
        receipt.get("schema") == "cassifi.computation-policy-receipt.v4",
        f"{label}: receipt schema mismatch",
    )
    require(
        "terminal_descriptor" not in receipt,
        f"{label}: uncompressed terminal descriptor unexpectedly retained",
    )
    nested_value = receipt.get("result")
    if not isinstance(nested_value, Mapping):
        raise VerificationError(f"{label}: nested result missing")
    nested = cast(Mapping[str, Any], nested_value)
    require(
        nested.get("schema") == "cassifi.constraint-result.v1",
        f"{label}: nested result schema mismatch",
    )
    require(nested.get("compiled") == source["compiled"], f"{label}: result source mismatch")
    require(nested.get("status") == receipt.get("status"), f"{label}: result status mismatch")
    require(receipt.get("source_sha256") == source["compiled_sha256"], f"{label}: receipt source mismatch")
    status = str(receipt.get("status"))
    require(status in {"sat", "unsat", "exhausted"}, f"{label}: invalid status")

    context = _context(source["compiled"], int(request["budget"]))
    require(receipt.get("context") == context, f"{label}: context receipt mismatch")
    if adaptive:
        expected_method, expected_selection = _adaptive_selection(
            field,
            context,
            cast(Mapping[str, Any], source["compiled"]),
        )
    else:
        expected_method = str(expected_requested)
        expected_selection = _fixed_selection(
            expected_method,
            context,
            field,
            cast(Mapping[str, Any], source["compiled"]),
        )
    require(row.get("selected_method") == expected_method, f"{label}: selected method row mismatch")
    require(receipt.get("method") == expected_method, f"{label}: executed method mismatch")
    require(receipt.get("selection") == expected_selection, f"{label}: selection receipt mismatch")
    require(
        receipt.get("selection_work") == expected_selection["work"],
        f"{label}: selection work mismatch",
    )
    require(receipt.get("policy_migrated") is False, f"{label}: unexpected policy migration")
    require(receipt.get("migration") is None, f"{label}: unexpected migration receipt")
    require(
        receipt.get("policy_schema_before") == POLICY_SCHEMA
        and receipt.get("policy_schema_after") == POLICY_SCHEMA,
        f"{label}: policy schema boundary mismatch",
    )

    before_sha = _field_sha(field)
    require(row.get("state_sha256_before") == before_sha, f"{label}: row before digest mismatch")
    require(
        receipt.get("policy_state_sha256_before") == before_sha,
        f"{label}: receipt before digest mismatch",
    )
    timing_values = (
        receipt.get("elapsed_ns"),
        receipt.get("decision_cost_ns"),
        receipt.get("learning_elapsed_ns"),
        receipt.get("total_elapsed_ns"),
    )
    if not all(type(value) is int and value >= 0 for value in timing_values):
        raise VerificationError(f"{label}: receipt timing is invalid")
    elapsed, decision, learning, total = cast(tuple[int, int, int, int], timing_values)
    require(
        elapsed == total and decision <= total and learning <= total,
        f"{label}: timing conservation mismatch",
    )
    wrapper_value = row.get("wrapper_elapsed_ns")
    if type(wrapper_value) is not int:
        raise VerificationError(f"{label}: wrapper timing is invalid")
    wrapper = cast(int, wrapper_value)
    require(wrapper >= total, f"{label}: wrapper omitted solve cost")
    components = row.get("component_elapsed_ns")
    expected_component_keys = {
        "compile",
        "solve_select_audit_learn",
        "checkpoint_reload",
        "unattributed_wrapper",
    }
    if not isinstance(components, Mapping) or set(components) != expected_component_keys:
        raise VerificationError(f"{label}: wrapper components malformed")
    require(
        all(type(value) is int and value >= 0 for value in components.values()),
        f"{label}: negative wrapper component",
    )
    require(sum(components.values()) == wrapper, f"{label}: wrapper timing does not conserve")
    require(
        components["solve_select_audit_learn"] >= total,
        f"{label}: solve component omitted receipt work",
    )

    budget_value = receipt.get("budget")
    if not isinstance(budget_value, Mapping):
        raise VerificationError(f"{label}: budget ledger missing")
    budget = cast(Mapping[str, Any], budget_value)
    declared_budget = int(request["budget"])
    selector_used = int(expected_selection["work"]["operations"])
    available = declared_budget - selector_used
    expected_hybrid = available // 2 if expected_method.startswith("algebraic") else 0
    expected_search = available - expected_hybrid if expected_method.startswith("algebraic") else available
    require(
        budget.get("declared") == declared_budget
        and budget.get("selector") == selector_used
        and budget.get("hybrid") == expected_hybrid
        and budget.get("search") == expected_search,
        f"{label}: reserved budget mismatch",
    )
    raw_work = nested.get("work")
    if not isinstance(raw_work, Mapping):
        raise VerificationError(f"{label}: terminal work ledger missing")
    hybrid_used = int(
        cast(Mapping[str, Any], raw_work.get("hybrid") or {})
        .get("resource_ledger", {})
        .get("transitions", 0)
    )
    search_used = int(cast(Mapping[str, Any], raw_work.get("search") or {}).get("transitions", 0))
    controller = raw_work.get("controller")
    if not isinstance(controller, Mapping):
        raise VerificationError(f"{label}: controller work ledger missing")
    controller_used = int(controller.get("ticks", 0))
    used = selector_used + hybrid_used + search_used + controller_used
    require(
        budget.get("used") == used
        and receipt.get("budget_used") == used
        and budget.get("remaining") == declared_budget - used
        and receipt.get("budget_remaining") == declared_budget - used,
        f"{label}: budget conservation mismatch",
    )
    require(0 <= used <= declared_budget, f"{label}: budget overrun")
    expected_flat: dict[str, Any] = {
        "selector_operations": selector_used,
        "hybrid_transitions": hybrid_used,
        "search_transitions": search_used,
        "backend_transitions": search_used,
        "controller_ticks": controller_used,
        "transitions": hybrid_used + search_used,
    }
    for key in ("compile", "prepass", "hybrid", "search", "controller"):
        if raw_work.get(key) is not None:
            expected_flat[key] = raw_work[key]
    for key in ("journal_bytes", "augmentations"):
        if key in raw_work:
            expected_flat[key] = raw_work[key]
    require(receipt.get("work") == raw_work, f"{label}: raw work mismatch")
    require(receipt.get("resource_ledger") == expected_flat, f"{label}: flattened work mismatch")
    for key, value in expected_flat.items():
        if isinstance(value, Mapping):
            continue
        require(type(value) is int and value >= 0, f"{label}: invalid work counter {key}")

    require(
        receipt.get("policy_field_bytes") == POLICY_FIELD_BYTES
        and receipt.get("retained_field_bytes") == POLICY_FIELD_BYTES,
        f"{label}: policy field byte ledger mismatch",
    )
    require(
        receipt.get("peak_workspace_bytes")
        == POLICY_FIELD_BYTES + int(receipt["peak_field_bytes"]),
        f"{label}: peak workspace ledger mismatch",
    )
    if status == "sat":
        require(receipt.get("witness") == nested.get("witness"), f"{label}: SAT witness mismatch")
        require(receipt.get("proof") is None, f"{label}: SAT carries a proof")
    elif status == "unsat":
        expected_proof = nested.get("resolution_proof") or nested.get("hybrid_proof")
        require(receipt.get("proof") == expected_proof, f"{label}: UNSAT proof mismatch")
        require(receipt.get("witness") is None, f"{label}: UNSAT carries a witness")
    else:
        require(
            receipt.get("witness") is None and receipt.get("proof") is None,
            f"{label}: exhaustion carries decided evidence",
        )
    evidence = (
        nested.get("resolution_proof") or nested.get("hybrid_proof")
        if status == "unsat"
        else None
    )
    expected_proof_bytes = len(_canonical(evidence)) if isinstance(evidence, Mapping) else 0
    require(receipt.get("proof_bytes") == expected_proof_bytes, f"{label}: proof byte ledger mismatch")
    audit = receipt.get("audit")
    require(
        isinstance(audit, Mapping)
        and receipt.get("audit_result") == audit
        and audit.get("checked") is True
        and audit.get("status") == status,
        f"{label}: production audit receipt mismatch",
    )
    _restore_terminal_descriptor(receipt, source)
    _audit(source, receipt)

    if adaptive:
        next_field, expected_observation = _record_observation(
            field,
            context=int(context["context_key"]),
            method_index=METHODS.index(expected_method),
            elapsed_ns=int(decision),
            work=used,
            status=status,
        )
        require(receipt.get("observation") == expected_observation, f"{label}: observation update mismatch")
    else:
        next_field = list(field)
        require(receipt.get("observation") is None, f"{label}: baseline wrote an observation")
        require(learning == 0, f"{label}: baseline charged learning time")
    after_sha = _field_sha(next_field)
    require(row.get("state_sha256_after") == after_sha, f"{label}: row after digest mismatch")
    require(
        receipt.get("policy_state_sha256_after") == after_sha,
        f"{label}: receipt after digest mismatch",
    )
    require(
        row.get("state_changed") is (before_sha != after_sha),
        f"{label}: state change flag mismatch",
    )
    checkpoint = _descriptor(next_field)
    require(
        row.get("checkpoint_descriptor_sha256")
        == hashlib.sha256(_canonical(checkpoint)).hexdigest(),
        f"{label}: checkpoint descriptor digest mismatch",
    )
    return next_field


def verify_report(report: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(report, (str, Path)):
        report = json.loads(Path(report).read_text(encoding="utf-8"))
    if not isinstance(report, Mapping):
        raise VerificationError("report must be a mapping")
    report_map = cast(Mapping[str, Any], report)
    require(report_map.get("schema") == SCHEMA, "report schema mismatch")
    report_hash = report_map.get("report_sha256")
    unsigned = {key: value for key, value in report_map.items() if key != "report_sha256"}
    require(
        isinstance(report_hash, str) and report_hash == _digest(unsigned),
        "report self-digest mismatch",
    )

    workload = _workload()
    require(report_map.get("workload") == workload, "workload manifest/source data mismatch")
    require(
        report_map.get("workload_manifest_sha256") == _digest(workload),
        "workload manifest digest mismatch",
    )
    by_id = {str(row["id"]): row for row in workload}
    require(len(by_id) == len(workload), "workload source ids are not unique")
    for source in workload:
        compiled = _json(compile_source(source["source"]).as_dict())
        require(compiled == source["compiled"], f"{source['id']}: fresh compile payload drifted")
        require(
            str(compiled["sha256"]) == source["compiled_sha256"],
            f"{source['id']}: fresh compile digest drifted",
        )
        require(
            source["source_sha256"] == _digest(source["source"]),
            f"{source['id']}: source digest mismatch",
        )

    config = report_map.get("configuration")
    if not isinstance(config, Mapping):
        raise VerificationError("configuration block missing")
    require(tuple(config.get("methods", ())) == tuple(METHODS), "method order mismatch")
    require(tuple(config.get("strategies", ())) == tuple(STRATEGIES), "strategy order mismatch")
    require(
        tuple(config.get("permutation_seeds", ())) == PERMUTATION_SEEDS,
        "permutation seeds mismatch",
    )
    require(config.get("repetitions") == REPETITIONS, "repetition count mismatch")
    require(tuple(config.get("budgets", ())) == BUDGETS, "budget classes mismatch")
    require(
        tuple(config.get("cohorts", ())) == COHORTS,
        "cohort order mismatch",
    )
    require(
        config.get("cohort_by_cycle")
        == {
            str(index): cohort
            for index, cohort in enumerate(COHORTS)
        },
        "cohort cycle mapping mismatch",
    )
    require(config.get("adaptive_learning") is True, "adaptive learning disabled")
    require(config.get("baseline_learning") is False, "baseline learning enabled")
    require(config.get("cold_start_per_permutation") is True, "cold-start boundary missing")
    preparation = report_map.get("workload_preparation_elapsed_ns")
    require(type(preparation) is int and preparation >= 0, "preparation timing invalid")

    policy = report_map.get("policy")
    if not isinstance(policy, Mapping):
        raise VerificationError("policy block missing")
    initial_field = _decode_policy(policy.get("initial"))
    require(all(value == 0 for value in initial_field), "initial policy is not zero")
    initial_sha = _field_sha(initial_field)
    require(policy.get("initial_state_sha256") == initial_sha, "initial policy digest mismatch")

    runs_value = report_map.get("runs")
    if not isinstance(runs_value, list) or len(runs_value) != len(PERMUTATION_SEEDS):
        raise VerificationError("permutation runs missing")
    runs = cast(list[Mapping[str, Any]], runs_value)
    pooled_rows: dict[str, list[Mapping[str, Any]]] = {
        strategy: [] for strategy in STRATEGIES
    }
    evidence_rows = 0
    for permutation_index, (run, seed) in enumerate(zip(runs, PERMUTATION_SEEDS, strict=True)):
        require(run.get("permutation_index") == permutation_index, "permutation index mismatch")
        require(run.get("seed") == seed, "permutation seed mismatch")
        base_order, requests = _request_stream(
            workload,
            permutation_index=permutation_index,
            seed=seed,
        )
        require(run.get("base_order") == base_order, "base source permutation mismatch")
        require(run.get("requests") == requests, "paired request stream mismatch")
        cold = run.get("cold_start")
        if not isinstance(cold, Mapping):
            raise VerificationError("cold-start run block missing")
        require(cold.get("state_sha256") == initial_sha, "cold-start digest mismatch")
        require(cold.get("all_strategies_equal") is True, "strategies did not cold-start equally")
        restart_boundary = run.get("restart_boundary")
        if not isinstance(restart_boundary, Mapping):
            raise VerificationError("restart boundary block missing")
        restart_ordinal = len(workload) * 2
        require(
            restart_boundary.get("before_ordinal")
            == restart_ordinal,
            "restart boundary ordinal mismatch",
        )
        require(
            restart_boundary.get("before_request_id")
            == requests[restart_ordinal]["request_id"],
            "restart boundary request mismatch",
        )
        require(
            restart_boundary.get("all_states_preserved") is True,
            "restart boundary did not preserve all states",
        )
        restart_strategies = restart_boundary.get("strategies")
        if (
            not isinstance(restart_strategies, Mapping)
            or set(restart_strategies) != set(STRATEGIES)
        ):
            raise VerificationError(
                "restart boundary strategy set mismatch"
            )

        strategies_value = run.get("strategies")
        if not isinstance(strategies_value, Mapping) or set(strategies_value) != set(STRATEGIES):
            raise VerificationError("run strategy set mismatch")
        checked_rows: dict[str, list[Mapping[str, Any]]] = {}
        for strategy in STRATEGIES:
            block_value = strategies_value.get(strategy)
            if not isinstance(block_value, Mapping):
                raise VerificationError(f"{strategy}: strategy block missing")
            block = cast(Mapping[str, Any], block_value)
            require(block.get("initial_state_sha256") == initial_sha, f"{strategy}: initial digest mismatch")
            rows_value = block.get("rows")
            if not isinstance(rows_value, list) or len(rows_value) != len(requests):
                raise VerificationError(f"{strategy}: request rows missing")
            rows = cast(list[Mapping[str, Any]], rows_value)
            field = list(initial_field)
            restart_record = cast(
                Mapping[str, Any],
                restart_strategies[strategy],
            )
            for row, request in zip(rows, requests, strict=True):
                if int(request["ordinal"]) == restart_ordinal:
                    boundary_sha = _field_sha(field)
                    require(
                        restart_record.get("state_sha256_before")
                        == boundary_sha
                        and restart_record.get(
                            "state_sha256_after"
                        )
                        == boundary_sha,
                        f"{strategy}: restart state digest mismatch",
                    )
                    require(
                        restart_record.get("descriptor_sha256")
                        == hashlib.sha256(
                            _canonical(_descriptor(field))
                        ).hexdigest(),
                        f"{strategy}: restart descriptor digest mismatch",
                    )
                    require(
                        restart_record.get("state_preserved")
                        is True,
                        f"{strategy}: restart preservation flag missing",
                    )
                source = by_id[str(request["source_id"])]
                field = _check_row(
                    row,
                    source,
                    request,
                    strategy=strategy,
                    field=field,
                )
                evidence_rows += 1
            final_field = _decode_policy(block.get("final_policy"))
            require(final_field == field, f"{strategy}: final policy does not follow row updates")
            require(block.get("final_state_sha256") == _field_sha(field), f"{strategy}: final digest mismatch")
            require(block.get("aggregate") == _aggregate(rows), f"{strategy}: run aggregate mismatch")
            checked_rows[strategy] = rows
            pooled_rows[strategy].extend(rows)
        comparisons = run.get("comparisons")
        if not isinstance(comparisons, Mapping):
            raise VerificationError("run comparison block missing")
        expected_comparisons = {
            baseline: _paired_comparison(
                checked_rows["adaptive"],
                checked_rows[baseline],
                baseline=baseline,
            )
            for baseline in STRATEGIES
            if baseline != "adaptive"
        }
        require(comparisons == expected_comparisons, "run paired comparisons mismatch")
        require(
            run.get("slices") == _sliced_aggregates(checked_rows),
            "run sliced aggregates mismatch",
        )

    aggregate = report_map.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise VerificationError("pooled aggregate missing")
    expected_strategies = {
        strategy: _aggregate(pooled_rows[strategy])
        for strategy in STRATEGIES
    }
    expected_comparisons = {
        baseline: _paired_comparison(
            pooled_rows["adaptive"],
            pooled_rows[baseline],
            baseline=baseline,
        )
        for baseline in STRATEGIES
        if baseline != "adaptive"
    }
    require(aggregate.get("strategies") == expected_strategies, "pooled strategy aggregate mismatch")
    require(aggregate.get("comparisons") == expected_comparisons, "pooled comparisons mismatch")
    require(
        aggregate.get("slices")
        == _sliced_aggregates(pooled_rows),
        "pooled sliced aggregates mismatch",
    )
    return {
        "status": "verified",
        "schema": SCHEMA,
        "sources": len(workload),
        "permutations": len(runs),
        "requests_per_strategy": len(pooled_rows["adaptive"]),
        "strategies": list(STRATEGIES),
        "evidence_rows_checked": evidence_rows,
        "terminal_fields_reconstructed": evidence_rows,
        "policy_transitions_reconstructed": evidence_rows,
        "paired_aggregates_recomputed": True,
        "sliced_aggregates_recomputed": True,
        "restart_boundaries_reconstructed": len(runs),
    }


def _resign(report: dict[str, Any]) -> None:
    report["report_sha256"] = _digest(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )


def verify_mutation_rejections(report: Mapping[str, Any]) -> list[str]:
    """Prove major verifier layers fire after a mutation is re-signed."""
    cases: list[tuple[str, Any]] = [
        ("schema", lambda value: value.__setitem__("schema", "mutated")),
        (
            "request-budget",
            lambda value: value["runs"][0]["requests"][0].__setitem__(
                "budget", value["runs"][0]["requests"][0]["budget"] + 1
            ),
        ),
        (
            "selected-method",
            lambda value: value["runs"][0]["strategies"]["adaptive"]["rows"][0].__setitem__(
                "selected_method", "algebraic-2-controller"
            ),
        ),
        (
            "terminal-field",
            lambda value: value["runs"][0]["strategies"]["adaptive"]["rows"][0]["receipt"][
                "terminal_descriptor_archive"
            ].__setitem__(
                "payload_b64",
                (
                    "A"
                    if value["runs"][0]["strategies"]["adaptive"]["rows"][0]["receipt"][
                        "terminal_descriptor_archive"
                    ]["payload_b64"][0]
                    != "A"
                    else "B"
                )
                + value["runs"][0]["strategies"]["adaptive"]["rows"][0]["receipt"][
                    "terminal_descriptor_archive"
                ]["payload_b64"][1:],
            ),
        ),
        (
            "pooled-aggregate",
            lambda value: value["aggregate"]["strategies"]["adaptive"].__setitem__(
                "completed",
                value["aggregate"]["strategies"]["adaptive"]["completed"] + 1,
            ),
        ),
    ]
    rejected: list[str] = []
    for name, mutate in cases:
        altered = copy.deepcopy(dict(report))
        mutate(altered)
        _resign(altered)
        try:
            verify_report(altered)
        except (VerificationError, ValueError, TypeError, KeyError):
            rejected.append(name)
        else:
            raise VerificationError(f"mutation was accepted: {name}")
    return rejected


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--skip-mutation-checks",
        action="store_true",
        help="verify the receipt without the five re-signed negative controls",
    )
    args = parser.parse_args(argv)
    try:
        raw = json.loads(args.report.read_text(encoding="utf-8"))
        result = verify_report(raw)
        if not args.skip_mutation_checks:
            result["mutation_rejections"] = verify_mutation_rejections(raw)
    except (VerificationError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
