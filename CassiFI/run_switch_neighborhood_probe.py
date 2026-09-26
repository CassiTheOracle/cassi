"""Complete one-switch neighborhood of the two width-three all-bases controls.

Every incidence two-switch between the two controls (1,620 cross-component
switches) stays at width at least three, and so does every chain built from
whole controls.  This probe maps the *within-control* neighborhood instead: it
applies every legal degree-preserving switch inside each width-three control
separately, deduplicates the resulting formulas by canonical digest, and decides
each neighbor three ways -- exhaustive census over every ``C(n, nullity)`` free
subset, the complete class search, and, at nullity three, the element-triangle
criterion.  A seeded sample of two-switch random walks extends the map to
distance two.

No hardness claim: the neighborhoods are complete and tiny (n = 12 and n = 15),
and the walks are samples from a fixed seed.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_frame_separation_probe as fsp
import run_frame_search_probe as probe
import run_mixed_schaefer_frame_obstruction as runner
from cubic_kernel_decision import canonical_cubic_formula

OUTPUT = Path("_diag/switch_neighborhood_probe.json")
SCHEMA = "cassifi.switch-neighborhood-probe.v1"
TWO_SWITCH_WALKS = 400
SEED = 20260910


def switch_specs(formula: Sequence[Sequence[int]]) -> list[tuple[int, int, int, int]]:
    """Every legal one-switch incidence exchange inside one formula.

    A switch moves one variable of clause ``left_row`` to ``right_row`` and back,
    which is legal exactly when each clause carries a variable the other lacks.
    """

    specs: list[tuple[int, int, int, int]] = []
    for left_row, right_row in itertools.combinations(range(len(formula)), 2):
        left, right = set(formula[left_row]), set(formula[right_row])
        for variable in sorted(left - right):
            for partner in sorted(right - left):
                specs.append((left_row, right_row, variable, partner))
    return specs


def apply_spec(
    formula: Sequence[Sequence[int]], spec: tuple[int, int, int, int]
) -> tuple[tuple[int, int, int], ...]:
    """Apply one switch and return the canonical formula."""

    left_row, right_row, variable, partner = spec
    clauses = [list(clause) for clause in formula]
    clauses[left_row][clauses[left_row].index(variable)] = partner
    clauses[right_row][clauses[right_row].index(partner)] = variable
    return canonical_cubic_formula(tuple(tuple(sorted(clause)) for clause in clauses))


def canonical_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = canonical_cubic_formula(formula)
    payload = "|".join(",".join(str(value) for value in clause) for clause in canonical)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def evaluate(label: str, formula: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Decide one formula by complete search plus exhaustive census.

    At nullity at most two every instance has width at most two, because a
    column has at most ``nullity`` coordinates in any free basis, so no search is
    needed and the trivial free set is recorded instead.
    """

    canonical = canonical_cubic_formula(formula)
    columns = runner.dual_columns(canonical)
    classes = fsp.classes_of(columns)
    rank = len(columns[0])
    record: dict[str, Any] = {
        "label": label,
        "size": len(canonical),
        "rank": len(canonical) - rank,
        "nullity": rank,
        "classes": len(classes),
        "digest": canonical_digest(canonical),
        "omega": fsp.census_width(canonical),
        "triangle": None,
        "trivial": False,
        "nodes": 0,
        "capped": False,
    }
    if rank == 3:
        record["triangle"] = fsp.element_triangle(classes) is not None
    if rank <= 2:
        record["verdict"] = "frame"
        record["trivial"] = True
        record["free_set"] = [
            probe.element_index_for_class(columns, classes[index]) for index in range(rank)
        ]
        record["width"] = runner.basis_width(columns, record["free_set"])
        return record
    chosen, nodes, capped = probe.frame_search(classes, rank)
    record["nodes"] = nodes
    record["capped"] = capped
    if chosen is None:
        record["verdict"] = "inconclusive" if capped else "no_frame"
        return record
    free = sorted(probe.element_index_for_class(columns, classes[index]) for index in chosen)
    width = runner.basis_width(columns, free)
    if width > 2:
        raise AssertionError(f"{label}: certificate failed width={width}")
    record["verdict"] = "frame"
    record["width"] = width
    record["free_set"] = free
    return record


def histogram(records: Sequence[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        key = str(record[field])
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def compact_record(record: dict[str, Any], include_walks: bool = False) -> dict[str, Any]:
    """Serialize one measured formula without runner-only labels."""

    compact: dict[str, Any] = {
        "digest": record["digest"],
        "size": record["size"],
        "rank": record["rank"],
        "nullity": record["nullity"],
        "classes": record["classes"],
        "omega": record["omega"],
        "triangle": record["triangle"],
        "verdict": record["verdict"],
        "nodes": record["nodes"],
        "capped": record["capped"],
    }
    if include_walks:
        compact["walks"] = record.get("walks", 0)
    if record["verdict"] == "frame":
        compact["free_set"] = record["free_set"]
        compact["width"] = record["width"]
        compact["trivial"] = record["trivial"]
    return compact


def with_switch(record: dict[str, Any]) -> dict[str, Any]:
    """Serialize a neighborhood row while retaining its generating switch."""

    compact = compact_record(record)
    compact["switch"] = record["switch"]
    return compact


def neighborhood(name: str, formula: Sequence[Sequence[int]], cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Complete one-switch neighborhood, evaluated once per distinct formula."""

    base = canonical_cubic_formula(formula)
    specs = switch_specs(base)
    unique: dict[str, tuple[tuple[int, int, int, int], tuple[tuple[int, int, int], ...]]] = {}
    for spec in specs:
        switched = apply_spec(base, spec)
        unique.setdefault(canonical_digest(switched), (spec, switched))

    records = []
    for key in sorted(unique):
        spec, switched = unique[key]
        if key not in cache:
            cache[key] = evaluate(f"{name}/n{len(records):04d}", switched)
        records.append({**cache[key], "switch": list(spec)})

    agreements = sum(
        1
        for record in records
        if record["verdict"] != "inconclusive"
        and (record["verdict"] == "frame") == (record["omega"] <= 2)
    )
    triangle_records = [record for record in records if record["triangle"] is not None]
    triangle_agreements = sum(
        1 for record in triangle_records if record["triangle"] == (record["verdict"] == "frame")
    )
    return {
        "control": name,
        "size": len(base),
        "base": cache.get(canonical_digest(base)) or evaluate(f"{name}/base", base),
        "spec_count": len(specs),
        "neighbor_count": len(unique),
        "neighbors": [with_switch(record) for record in records],
        "omega_histogram": histogram(records, "omega"),
        "verdict_histogram": histogram(records, "verdict"),
        "nodes_total": sum(record["nodes"] for record in records),
        "census_search_agreements": agreements,
        "triangle_checked": len(triangle_records),
        "triangle_agreements": triangle_agreements,
        "frame_neighbors": [
            {
                "switch": record["switch"],
                "free_set": record["free_set"],
                "width": record["width"],
                "trivial": record["trivial"],
                "nodes": record["nodes"],
            }
            for record in records
            if record["verdict"] == "frame"
        ],
        "no_frame_neighbors": [
            {"switch": record["switch"], "nodes": record["nodes"]}
            for record in records
            if record["verdict"] == "no_frame"
        ],
    }


def walk_sample(
    name: str,
    formula: Sequence[Sequence[int]],
    cache: dict[str, dict[str, Any]],
    count: int,
    seed: int,
) -> dict[str, Any]:
    """Seeded sample of two-switch random walks inside one control."""

    base = canonical_cubic_formula(formula)
    rng = random.Random(seed)
    finals: dict[str, dict[str, Any]] = {}
    draws: list[str] = []
    intermediates: list[dict[str, Any]] = []
    for _ in range(count):
        current = base
        step_digests = []
        for _ in range(2):
            specs = switch_specs(current)
            spec = specs[rng.randrange(len(specs))]
            current = apply_spec(current, spec)
            step_digests.append(canonical_digest(current))
        draws.extend(step_digests)
        intermediates.append(cache[step_digests[0]])
        key = step_digests[-1]
        if key not in finals:
            finals[key] = evaluate(f"{name}/w{len(finals):04d}", current)
        finals[key]["walks"] = finals[key].get("walks", 0) + 1

    final_records = [finals[key] for key in sorted(finals)]
    draw_payload = "|".join(draws)
    return {
        "walks": count,
        "unique_finals": len(final_records),
        "finals": [compact_record(record, include_walks=True) for record in final_records],
        "omega_histogram": histogram(final_records, "omega"),
        "verdict_histogram": histogram(final_records, "verdict"),
        "census_search_agreements": sum(
            1
            for record in final_records
            if record["verdict"] != "inconclusive"
            and (record["verdict"] == "frame") == (record["omega"] <= 2)
        ),
        "intermediate_omega_histogram": histogram(intermediates, "omega"),
        "intermediate_width_two": sum(1 for record in intermediates if record["omega"] == 2),
        "nodes_total": sum(record["nodes"] for record in final_records),
        "draw_sequence_sha256": hashlib.sha256(draw_payload.encode("ascii")).hexdigest(),
        "frames": [
            {"free_set": record["free_set"], "nodes": record["nodes"]}
            for record in final_records
            if record["verdict"] == "frame"
        ],
    }


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    cache: dict[str, dict[str, Any]] = {}
    controls = []
    targets = [
        name
        for name in probe.CONTROL_EXPECTATIONS
        if probe.CONTROL_EXPECTATIONS[name] == "no_frame"
    ]
    lookup = dict(fsp.CONTROLS)
    for position, name in enumerate(targets):
        record = neighborhood(name, lookup[name], cache)
        record["walk_seed"] = SEED + 1 + position
        record["walks"] = walk_sample(
            name, lookup[name], cache, TWO_SWITCH_WALKS, record["walk_seed"]
        )
        controls.append(record)
    receipt = {
        "schema": SCHEMA,
        "seed": SEED,
        "walks_per_control": TWO_SWITCH_WALKS,
        "controls": controls,
        "cache_size": len(cache),
        "seconds": round(time.perf_counter() - started, 2),
        "limits": {
            "complete": "every legal one-switch incidence exchange, deduplicated by canonical digest",
            "walks": "seeded samples of two-switch random walks, not exhaustive at distance two",
            "decision": "exhaustive census over all C(n, nullity) free subsets plus the complete class search",
        },
    }
    return receipt


def main() -> None:
    receipt = build_receipt()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for record in receipt["controls"]:
        print(
            f"{record['control']}: neighbours={record['neighbor_count']} "
            f"omega={record['omega_histogram']} walks={record['walks']['omega_histogram']} "
            f"agreements={record['census_search_agreements']}/{record['neighbor_count']} "
            f"+ {record['walks']['census_search_agreements']}/{record['walks']['unique_finals']}"
        )
    print(f"receipt: {OUTPUT} in {receipt['seconds']}s, {receipt['cache_size']} evaluated formulas")


if __name__ == "__main__":
    main()
