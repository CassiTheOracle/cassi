#!/usr/bin/env python3
"""Compose census cell gadgets by degree-preserving double switches.

Two disjoint cubic cell formulas A and B are joined by two 2-switches. Each
switch trades one incidence edge of A with one incidence edge of B, so every
row and column keeps weight three. The probe enumerates every double switch
between the two gadgets: an unordered pair of A edges against an ordered pair
of B edges, discarding switches that repeat a variable in a row or duplicate a
row. For each composite it computes the width-two class frames of the kernel
matroid (arithmetic modulo the Mersenne prime 2^61 - 1) and records

* the relation the frames induce on the gadgets' own exclusive-pair ports
  (one port per class-level exclusive pair of each gadget): a product of its
  A and B sides, a bijection, a function (one side determines the other) or
  partial (neither side determines the other); whether both sides stay inside
  their gadget's own frame states (intact); and how many classes merge
  variables of both gadgets; and
* the M(K4) cores of the composite's class geometry -- four lines of at least
  three classes meeting pairwise in six distinct classes of rank three -- the
  star centre every frame takes on each core, and, for every pair of cores
  that are stars in all frames, whether their centres are independent
  (product), locked by a bijection, or joined by any other relation.

Gadgets: ``G3`` is the unique census cell formula with three surviving K4
stars, whose frames realise one-in-three on its ports; ``Q13`` is the order-13
cell formula with the smallest formula SHA-256 (four stars, affine parity).
Up to ``EXAMPLE_CAP`` switch sets are stored for every non-product outcome and
every stored row is re-checked -- nullity, frame count and port relation --
with the census runner's exact rational kernel profile.

The chain stage tests whether a bit reader carries a clause bit onward. Its
bases are the G3 x Q13 composites that keep G3 intact (three stars) while the
Q13 side W becomes a two-state function of G3. A second G3 (Y) is attached by
every double switch between a pair of edges in W's rows and an ordered pair of
Y edges, and the frames give the relations between G3, W and Y. A G3-Y
relation that is neither a product nor a bijection would be a bit wire
between two one-in-three clause cores.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path
import time
from typing import Any

import run_cubic_cell_census_probe as census

ROOT = Path(__file__).resolve().parent
DEFAULT_CENSUS = ROOT / "_diag" / "cubic_cell_census_probe.json"
DEFAULT_OUTPUT = ROOT / "_diag" / "cubic_cell_coupling_probe.json"
SCHEMA = "cassifi.cubic-cell-coupling-probe.v1"
P = (1 << 61) - 1
PAIRS = (("G3", "G3"), ("G3", "Q13"), ("Q13", "Q13"))
EXAMPLE_CAP = 16
OTHER_EXAMPLE_CAP = 64
CHAIN_SHAPE = ("function", True, 3, 2, 3)

Formula = tuple[tuple[int, ...], ...]
Edge = tuple[int, int]


# Modular class geometry ------------------------------------------------------


def inverse(a: int) -> int:
    return pow(a, P - 2, P)


def nullspace(formula: Formula, n: int) -> list[list[int]]:
    rows = [[1 if j in row else 0 for j in range(n)] for row in formula]
    pivots: list[int] = []
    r = 0
    for c in range(n):
        pr = next((i for i in range(r, len(rows)) if rows[i][c]), None)
        if pr is None:
            continue
        rows[r], rows[pr] = rows[pr], rows[r]
        scale = inverse(rows[r][c])
        rows[r] = [x * scale % P for x in rows[r]]
        for i in range(len(rows)):
            if i != r and rows[i][c]:
                f = rows[i][c]
                rows[i] = [(x - f * y) % P for x, y in zip(rows[i], rows[r])]
        pivots.append(c)
        r += 1
        if r == len(rows):
            break
    basis = []
    for free in (c for c in range(n) if c not in pivots):
        v = [0] * n
        v[free] = 1
        for i, c in enumerate(pivots):
            v[c] = (-rows[i][free]) % P
        basis.append(v)
    return basis


def normalize(v: tuple[int, ...]) -> tuple[int, ...]:
    scale = inverse(next(x for x in v if x))
    return tuple(x * scale % P for x in v)


def echelon_add(ech: list[tuple[int, list[int]]], v) -> tuple[int, list[int]] | None:
    v = list(v)
    for pc, row in ech:
        if v[pc]:
            f = v[pc]
            v = [(x - f * y) % P for x, y in zip(v, row)]
    pc = next((i for i, x in enumerate(v) if x), None)
    if pc is None:
        return None
    scale = inverse(v[pc])
    return pc, [x * scale % P for x in v]


def rank(vectors) -> int:
    ech: list[tuple[int, list[int]]] = []
    for v in vectors:
        e = echelon_add(ech, v)
        if e is not None:
            ech.append(e)
    return len(ech)


def line_key(a, b) -> tuple[tuple[int, ...], tuple[int, ...]]:
    e0 = echelon_add([], a)
    assert e0 is not None
    e1 = echelon_add([e0], b)
    assert e1 is not None
    (p0, r0), (p1, r1) = sorted([e0, e1])
    if r0[p1]:
        f = r0[p1]
        r0 = [(x - f * y) % P for x, y in zip(r0, r1)]
    return tuple(r0), tuple(r1)


class Geometry:
    """Projective classes, lines and width-two class frames of one formula."""

    def __init__(self, formula: Formula):
        self.formula = formula
        n = len(formula)
        basis = nullspace(formula, n)
        self.k = len(basis)
        columns = [tuple(v[j] for v in basis) for j in range(n)]
        groups: dict[tuple[int, ...], list[int]] = {}
        for j, column in enumerate(columns):
            if any(column):
                groups.setdefault(normalize(column), []).append(j)
        self.vecs = list(groups)
        self.classes = list(groups.values())
        self.class_of = {j: c for c, group in enumerate(self.classes) for j in group}
        m = len(self.vecs)
        lines: dict[Any, set[int]] = {}
        for a, b in itertools.combinations(range(m), 2):
            lines.setdefault(line_key(self.vecs[a], self.vecs[b]), set()).update((a, b))
        self.lines = [frozenset(line) for line in lines.values()]
        self.big_lines = [line for line in self.lines if len(line) >= 3]
        self.lines_at = [[line for line in self.lines if c in line] for c in range(m)]
        self.frames = self._frames()

    def _frames(self) -> list[frozenset[int]]:
        m, k = len(self.vecs), self.k
        if k == 0:
            return [frozenset()]
        out: list[frozenset[int]] = []
        lines_at = self.lines_at

        def coverable(c: int, chosen: set[int], pos: int) -> bool:
            for line in lines_at[c]:
                if sum(1 for x in line if x != c and (x in chosen or x >= pos)) >= 2:
                    return True
            return False

        def dfs(pos: int, chosen: set[int], ech, skipped: list[int]) -> None:
            if len(chosen) == k:
                frame = frozenset(chosen)
                if all(c in frame or any(len(line & frame) >= 2 for line in lines_at[c]) for c in range(m)):
                    out.append(frame)
                return
            if m - pos < k - len(chosen) or not all(coverable(c, chosen, pos) for c in skipped):
                return
            e = echelon_add(ech, self.vecs[pos])
            if e is not None:
                chosen.add(pos)
                dfs(pos + 1, chosen, ech + [e], skipped)
                chosen.discard(pos)
            dfs(pos + 1, chosen, ech, skipped + [pos])

        dfs(0, set(), [], [])
        return out

    def exclusive_class_pairs(self) -> list[tuple[int, int]]:
        if not self.frames:
            return []
        return [
            (a, b)
            for a, b in itertools.combinations(range(len(self.vecs)), 2)
            if {(a in f, b in f) for f in self.frames} == {(True, False), (False, True)}
        ]

    def state(self, frame: frozenset[int], tracked: list[int]) -> tuple[int, ...]:
        return tuple(int(self.class_of.get(j, -1) in frame) for j in tracked)

    def k4_cores(self) -> list[dict[str, Any]]:
        cores = []
        for quad in itertools.combinations(self.big_lines, 4):
            meets = {}
            for a, b in itertools.combinations(range(4), 2):
                common = quad[a] & quad[b]
                if len(common) != 1:
                    break
                meets[(a, b)] = next(iter(common))
            else:
                points = frozenset(meets.values())
                if len(points) == 6 and rank(self.vecs[p] for p in points) == 3:
                    # The star at the K4 vertex opposite triangle t: the meets off t.
                    stars = {
                        t: frozenset(p for (a, b), p in meets.items() if t not in (a, b))
                        for t in range(4)
                    }
                    cores.append({"points": points, "stars": stars})
        return cores


# Composition -------------------------------------------------------------------


def disjoint(a: Formula, b: Formula) -> Formula:
    shift = len(a)
    return tuple(a) + tuple(tuple(v + shift for v in row) for row in b)


def switch(formula: Formula, e1: Edge, e2: Edge) -> Formula | None:
    """Clause c1 trades its variable v1 for v2; clause c2 trades v2 for v1."""
    (c1, v1), (c2, v2) = e1, e2
    rows = [list(row) for row in formula]
    if v1 not in rows[c1] or v2 not in rows[c2] or v2 in rows[c1] or v1 in rows[c2]:
        return None
    rows[c1][rows[c1].index(v1)] = v2
    rows[c2][rows[c2].index(v2)] = v1
    out = tuple(tuple(sorted(row)) for row in rows)
    return out if len(set(out)) == len(out) else None


def ports_of(formula: Formula) -> list[int]:
    """One port variable per class-level exclusive pair: the first class's first member."""
    g = Geometry(formula)
    return [g.classes[a][0] for a, _ in g.exclusive_class_pairs()]


def relation_class(
    relation: frozenset[tuple[int, ...]], width_a: int, own_a: set[tuple[int, ...]], own_b: set[tuple[int, ...]]
) -> tuple[Any, ...]:
    """Kind of a port relation, whether both gadgets keep their own states, and its sizes.

    ``product``: the sides are independent. ``bijection``: each side determines
    the other. ``function``: exactly one side determines the other.
    ``partial``: neither side determines the other and the sides are not
    independent -- the relation a single-bit wire needs."""
    if not relation:
        return ("dead",)
    side_a = {s[:width_a] for s in relation}
    side_b = {s[width_a:] for s in relation}
    if len(relation) == len(side_a) * len(side_b):
        kind = "product"
    elif len(relation) == len(side_a) == len(side_b):
        kind = "bijection"
    elif len(relation) in (len(side_a), len(side_b)):
        kind = "function"
    else:
        kind = "partial"
    return (kind, side_a <= own_a and side_b <= own_b, len(side_a), len(side_b), len(relation))


def core_class(g: Geometry) -> tuple[Any, ...]:
    """Core count, always-star cores, non-star core restrictions, pair relation kinds."""
    cores = g.k4_cores()
    centres = []
    nonstar = 0
    for frame in g.frames:
        row = []
        for core in cores:
            hit = [t for t, star in core["stars"].items() if star <= frame]
            if len(hit) == 1 and len(frame & core["points"]) == 3:
                row.append(hit[0])
            else:
                row.append(None)
                nonstar += 1
        centres.append(tuple(row))
    stable = [i for i in range(len(cores)) if all(row[i] is not None for row in centres)]
    kinds: Counter[str] = Counter()
    for i, j in itertools.combinations(stable, 2):
        rel = {(row[i], row[j]) for row in centres}
        left = {x for x, _ in rel}
        right = {y for _, y in rel}
        if len(rel) == len(left) * len(right):
            kinds["product"] += 1
        elif len(rel) == len(left) == len(right):
            kinds["bijection"] += 1
        else:
            kinds["other"] += 1
    return (len(cores), len(stable), nonstar, kinds["product"], kinds["bijection"], kinds["other"])


def own_states(formula: Formula, ports: list[int]) -> set[tuple[int, ...]]:
    g = Geometry(formula)
    return {g.state(f, ports) for f in g.frames}


def composite_of(a: Formula, b: Formula, switches: list[list[int]]) -> Formula:
    ea1, eb1, ea2, eb2 = (tuple(e) for e in switches)
    first = switch(disjoint(a, b), ea1, eb1)
    assert first is not None
    composite = switch(first, ea2, eb2)
    assert composite is not None
    return composite


def compose_chunk(job):
    a, b, ports_a, ports_b, own_a, own_b, a_pairs = job
    shift = len(a)
    base = disjoint(a, b)
    edges_b = [(c + shift, v + shift) for c, row in enumerate(b) for v in row]
    tracked = list(ports_a) + [p + shift for p in ports_b]
    outcomes: Counter[tuple[Any, ...]] = Counter()
    cores: Counter[tuple[Any, ...]] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {}
    core_examples: dict[str, dict[str, Any]] = {}
    others: list[dict[str, Any]] = []
    for ea1, ea2 in a_pairs:
        for eb1, eb2 in itertools.permutations(edges_b, 2):
            first = switch(base, ea1, eb1)
            if first is None:
                continue
            composite = switch(first, ea2, eb2)
            if composite is None:
                continue
            g = Geometry(composite)
            relation = frozenset(g.state(f, tracked) for f in g.frames)
            kind = relation_class(relation, len(ports_a), own_a, own_b)
            cross = sum(1 for group in g.classes if group[0] < shift <= group[-1])
            outcome = (g.k, len(g.frames), cross, kind)
            outcomes[outcome] += 1
            core = core_class(g) if g.frames else ("dead",)
            cores[core] += 1
            row = {
                "switches": [list(ea1), list(eb1), list(ea2), list(eb2)],
                "nullity": g.k,
                "frames": len(g.frames),
                "cross_classes": cross,
                "relation": sorted(list(s) for s in relation),
                "outcome": repr(outcome),
                "core_class": repr(core),
            }
            cap = 1 if kind[0] in ("dead", "product") else EXAMPLE_CAP
            bucket = examples.setdefault(repr(outcome), [])
            if len(bucket) < cap:
                bucket.append(row)
            core_examples.setdefault(repr(core), row)
            if core != ("dead",) and core[5] and len(others) < OTHER_EXAMPLE_CAP:
                others.append(row)
    return outcomes, cores, examples, core_examples, others


# Receipt ------------------------------------------------------------------------


def load_gadgets(path: Path) -> dict[str, Formula]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    records = receipt["census"]["cell_formulas"]
    three = [r for r in records if r["k4_core"] and len(r["k4_core"]["stars"]) == 3]
    if len(three) != 1:
        raise RuntimeError(f"expected one three-star census cell formula, found {len(three)}")
    q13 = min((r for r in records if len(r["formula"]) == 13), key=lambda r: r["formula_sha256"])

    def zero_based(record: dict[str, Any]) -> Formula:
        return tuple(tuple(sorted(v - 1 for v in row)) for row in record["formula"])

    return {"G3": zero_based(three[0]), "Q13": zero_based(q13)}


def exact_recheck(job) -> bool:
    """Exact rational nullity, class-frame count and port relation of one stored row."""
    a, b, ports_a, ports_b, row = job
    profile = census.kernel_profile(composite_of(a, b, row["switches"]))
    class_of = {j: c for c, group in enumerate(profile["classes"]) for j in group}
    tracked = list(ports_a) + [p + len(a) for p in ports_b]
    relation = sorted(
        {tuple(int(class_of.get(j, -1) in set(frame)) for j in tracked) for frame in profile["class_frames"]}
    )
    return (
        profile["nullity"] == row["nullity"]
        and len(profile["class_frames"]) == row["frames"]
        and [list(s) for s in relation] == row["relation"]
    )


def shape_table(outcomes: Counter[tuple[Any, ...]]) -> list[list[Any]]:
    """Live non-product relation shapes: kind, intact, |A side|, |B side|, |R|, composites."""
    shapes: Counter[tuple[Any, ...]] = Counter()
    for (_, _, _, kind), count in outcomes.items():
        if kind[0] not in ("dead", "product"):
            shapes[kind] += count
    return [[*k, v] for k, v in sorted(shapes.items(), key=lambda kv: (kv[0][0], not kv[0][1], kv[0][2:]))]


def run_pair(name_a: str, name_b: str, gadgets: dict[str, Formula], pool, workers: int) -> dict[str, Any]:
    a, b = gadgets[name_a], gadgets[name_b]
    ports_a, ports_b = ports_of(a), ports_of(b)
    own_a, own_b = own_states(a, ports_a), own_states(b, ports_b)
    edges_a = [(c, v) for c, row in enumerate(a) for v in row]
    a_pairs = list(itertools.combinations(edges_a, 2))
    chunks = [a_pairs[i :: workers * 4] for i in range(workers * 4)]
    started = time.time()
    outcomes: Counter[tuple[Any, ...]] = Counter()
    cores: Counter[tuple[Any, ...]] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {}
    core_examples: dict[str, dict[str, Any]] = {}
    others: list[dict[str, Any]] = []
    jobs = [(a, b, ports_a, ports_b, own_a, own_b, chunk) for chunk in chunks]
    for part in pool.map(compose_chunk, jobs):
        outcomes.update(part[0])
        cores.update(part[1])
        for key, rows in part[2].items():
            bucket = examples.setdefault(key, [])
            cap = 1 if "'dead'" in key or "'product'" in key else EXAMPLE_CAP
            bucket.extend(rows[: cap - len(bucket)])
        for key, row in part[3].items():
            core_examples.setdefault(key, row)
        others.extend(part[4][: OTHER_EXAMPLE_CAP - len(others)])
    stored = [row for rows in examples.values() for row in rows] + list(core_examples.values()) + others
    rechecked = list(pool.map(exact_recheck, [(a, b, ports_a, ports_b, row) for row in stored], chunksize=8))
    total = sum(outcomes.values())
    kinds: Counter[str] = Counter()
    for (_, _, _, kind), count in outcomes.items():
        kinds[kind[0] if kind[0] == "dead" else f"{kind[0]}/{'intact' if kind[1] else 'altered'}"] += count
    result = {
        "gadgets": [name_a, name_b],
        "ports": [ports_a, ports_b],
        "own_states": [sorted(list(s) for s in own_a), sorted(list(s) for s in own_b)],
        "composites": total,
        "live_composites": total - kinds["dead"],
        "relation_kinds": dict(sorted(kinds.items())),
        "relation_shapes": shape_table(outcomes),
        "core_pair_kinds": {
            "product": sum(k[3] * v for k, v in cores.items() if k != ("dead",)),
            "bijection": sum(k[4] * v for k, v in cores.items() if k != ("dead",)),
            "other": sum(k[5] * v for k, v in cores.items() if k != ("dead",)),
        },
        "composites_with_core_bijection": sum(v for k, v in cores.items() if k != ("dead",) and k[4]),
        "composites_with_other_core_relation": sum(v for k, v in cores.items() if k != ("dead",) and k[5]),
        "composites_with_nonstar_core_restriction": sum(v for k, v in cores.items() if k != ("dead",) and k[2]),
        "outcomes": [[repr(k), v] for k, v in sorted(outcomes.items(), key=lambda kv: (-kv[1], repr(kv[0])))],
        "core_classes": [[repr(k), v] for k, v in sorted(cores.items(), key=lambda kv: (-kv[1], repr(kv[0])))],
        "examples": examples,
        "core_examples": core_examples,
        "other_core_examples": others,
        "stored_rows": len(stored),
        "stored_rows_exactly_rechecked": sum(rechecked),
        "seconds": round(time.time() - started, 1),
    }
    print(
        f"{name_a} x {name_b}: {total} composites, kinds {result['relation_kinds']}, "
        f"core pairs {result['core_pair_kinds']}, exact {sum(rechecked)}/{len(stored)}, {result['seconds']} s",
        flush=True,
    )
    return result


# Chain stage ----------------------------------------------------------------------


def chain_bases(pair: dict[str, Any]) -> list[list[list[int]]]:
    """Switch sets of every G3 x Q13 composite in which Q13 becomes a two-state reader of an intact G3."""
    rows = [
        row["switches"]
        for key, bucket in pair["examples"].items()
        if ast.literal_eval(key)[3] == CHAIN_SHAPE
        for row in bucket
    ]
    expected = sum(shape[-1] for shape in pair["relation_shapes"] if tuple(shape[:-1]) == CHAIN_SHAPE)
    if len(rows) != expected:
        raise RuntimeError(f"stored {len(rows)} of {expected} reader composites")
    return rows


def chain_chunk(job):
    x, y, x_pairs, tracked, own_c, own_w = job
    base = disjoint(x, y)
    shift = len(x)
    y_edges = [(c + shift, v + shift) for c, row in enumerate(y) for v in row]
    outcomes: Counter[tuple[Any, ...]] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {}
    for ex1, ex2 in x_pairs:
        for ey1, ey2 in itertools.permutations(y_edges, 2):
            first = switch(base, ex1, ey1)
            if first is None:
                continue
            composite = switch(first, ex2, ey2)
            if composite is None:
                continue
            g = Geometry(composite)
            states = frozenset(g.state(f, tracked) for f in g.frames)
            c_y = relation_class(frozenset(s[:3] + s[6:] for s in states), 3, own_c, own_c)
            c_w = relation_class(frozenset(s[:6] for s in states), 3, own_c, own_w)
            w_y = relation_class(frozenset(s[3:] for s in states), 3, own_w, own_c)
            outcome = (g.k, len(g.frames), c_y, c_w[0], w_y[0])
            outcomes[outcome] += 1
            bucket = examples.setdefault(repr(outcome), [])
            if len(bucket) < (1 if c_y[0] in ("dead", "product") else EXAMPLE_CAP):
                bucket.append(
                    {
                        "switches": [list(ex1), list(ey1), list(ex2), list(ey2)],
                        "nullity": g.k,
                        "frames": len(g.frames),
                        "relation": sorted(list(s) for s in states),
                        "outcome": repr(outcome),
                    }
                )
    return outcomes, examples


def chain_recheck(job) -> bool:
    """Exact rational nullity, class-frame count and G3-W-Y relation of one stored chain row."""
    x, y, tracked, row = job
    ex1, ey1, ex2, ey2 = (tuple(e) for e in row["switches"])
    first = switch(disjoint(x, y), ex1, ey1)
    assert first is not None
    composite = switch(first, ex2, ey2)
    assert composite is not None
    profile = census.kernel_profile(composite)
    class_of = {j: c for c, group in enumerate(profile["classes"]) for j in group}
    relation = sorted(
        {tuple(int(class_of.get(j, -1) in set(frame)) for j in tracked) for frame in profile["class_frames"]}
    )
    return (
        profile["nullity"] == row["nullity"]
        and len(profile["class_frames"]) == row["frames"]
        and [list(s) for s in relation] == row["relation"]
    )


def run_chain(pair: dict[str, Any], gadgets: dict[str, Formula], pool, workers: int) -> dict[str, Any]:
    g3, q13 = gadgets["G3"], gadgets["Q13"]
    ports_c, ports_q = ports_of(g3), ports_of(q13)
    own_c = own_states(g3, ports_c)
    started = time.time()
    bases = []
    for switches in chain_bases(pair):
        x = composite_of(g3, q13, switches)
        ports_w = [p + len(g3) for p in ports_q]
        own_w = own_states(x, ports_w)
        tracked = list(ports_c) + ports_w + [p + len(x) for p in ports_c]
        x_edges = [(c, v) for c in range(len(g3), len(x)) for v in x[c]]
        x_pairs = list(itertools.combinations(x_edges, 2))
        chunks = [x_pairs[i :: workers * 4] for i in range(workers * 4)]
        outcomes: Counter[tuple[Any, ...]] = Counter()
        examples: dict[str, list[dict[str, Any]]] = {}
        for part in pool.map(chain_chunk, [(x, g3, chunk, tracked, own_c, own_w) for chunk in chunks]):
            outcomes.update(part[0])
            for key, rows in part[1].items():
                bucket = examples.setdefault(key, [])
                cap = 1 if ast.literal_eval(key)[2][0] in ("dead", "product") else EXAMPLE_CAP
                bucket.extend(rows[: cap - len(bucket)])
        stored = [row for rows in examples.values() for row in rows]
        rechecked = list(pool.map(chain_recheck, [(x, g3, tracked, row) for row in stored], chunksize=2))
        c_y: Counter[str] = Counter()
        c_w: Counter[str] = Counter()
        w_y: Counter[str] = Counter()
        for (_, _, rel, cw, wy), count in outcomes.items():
            c_y[rel[0] if rel[0] == "dead" else f"{rel[0]}/{'intact' if rel[1] else 'altered'}"] += count
            c_w[cw] += count
            w_y[wy] += count
        total = sum(outcomes.values())
        bases.append(
            {
                "base_switches": switches,
                "reader_states": sorted(list(s) for s in own_w),
                "composites": total,
                "live_composites": total - c_y["dead"],
                "g3_y_kinds": dict(sorted(c_y.items())),
                "g3_w_kinds": dict(sorted(c_w.items())),
                "w_y_kinds": dict(sorted(w_y.items())),
                "outcomes": [[repr(k), v] for k, v in sorted(outcomes.items(), key=lambda kv: (-kv[1], repr(kv[0])))],
                "examples": examples,
                "stored_rows": len(stored),
                "stored_rows_exactly_rechecked": sum(rechecked),
            }
        )
        print(
            f"chain base {switches}: {total} composites, G3-Y {dict(c_y)}, W-Y {dict(w_y)}, "
            f"exact {sum(rechecked)}/{len(stored)}, {round(time.time() - started, 1)} s",
            flush=True,
        )
    return {"bases": bases, "seconds": round(time.time() - started, 1)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--reuse-pairs",
        type=Path,
        help="take the pair stage from an earlier receipt built from the same census receipt",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.time()
    gadgets = load_gadgets(args.census)
    census_sha = hashlib.sha256(args.census.read_bytes()).hexdigest()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        if args.reuse_pairs:
            earlier = json.loads(args.reuse_pairs.read_text(encoding="utf-8"))
            if earlier["census_receipt_sha256"] != census_sha:
                raise RuntimeError("the reused pair stage was built from a different census receipt")
            pairs = earlier["pairs"]
        else:
            pairs = [run_pair(a, b, gadgets, pool, args.workers) for a, b in PAIRS]
        chain = run_chain(next(p for p in pairs if p["gadgets"] == ["G3", "Q13"]), gadgets, pool, args.workers)
    kinds: Counter[str] = Counter()
    for pair in pairs:
        kinds.update(pair["relation_kinds"])
    chain_totals: dict[str, Counter[str]] = {"g3_y_kinds": Counter(), "g3_w_kinds": Counter(), "w_y_kinds": Counter()}
    for base in chain["bases"]:
        for name, totals in chain_totals.items():
            totals.update(base[name])
    receipt = {
        "schema": SCHEMA,
        "census_receipt_sha256": census_sha,
        "modulus": P,
        "gadgets": {
            name: {
                "formula": [[v + 1 for v in row] for row in formula],
                "formula_sha256": census.json_digest([[v + 1 for v in row] for row in formula]),
            }
            for name, formula in gadgets.items()
        },
        "pairs": pairs,
        "chain": chain,
        "assessment": {
            "composites": sum(p["composites"] for p in pairs),
            "live_composites": sum(p["live_composites"] for p in pairs),
            "relation_kinds": dict(sorted(kinds.items())),
            "intact_partial_shapes": {
                "+".join(p["gadgets"]): [s for s in p["relation_shapes"] if s[0] == "partial" and s[1]] for p in pairs
            },
            "composites_with_core_bijection": sum(p["composites_with_core_bijection"] for p in pairs),
            "composites_with_other_core_relation": sum(p["composites_with_other_core_relation"] for p in pairs),
            "composites_with_nonstar_core_restriction": sum(
                p["composites_with_nonstar_core_restriction"] for p in pairs
            ),
            "stored_rows": sum(p["stored_rows"] for p in pairs),
            "stored_rows_exactly_rechecked": sum(p["stored_rows_exactly_rechecked"] for p in pairs),
            "chain_bases": len(chain["bases"]),
            "chain_composites": sum(b["composites"] for b in chain["bases"]),
            "chain_live_composites": sum(b["live_composites"] for b in chain["bases"]),
            **{f"chain_{name}": dict(sorted(totals.items())) for name, totals in chain_totals.items()},
            "chain_stored_rows": sum(b["stored_rows"] for b in chain["bases"]),
            "chain_stored_rows_exactly_rechecked": sum(b["stored_rows_exactly_rechecked"] for b in chain["bases"]),
        },
        "seconds": round(time.time() - started, 1),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(json.dumps(receipt["assessment"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
