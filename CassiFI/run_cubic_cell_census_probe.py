#!/usr/bin/env python3
"""Census nondegenerate exclusive pairs in connected cubic exact-one formulas.

For every census order ``n``, nauty's ``genbg`` (run in WSL) lists each
connected simple bipartite graph with ``n`` variable vertices and ``n`` clause
vertices, all of degree three and with pairwise-distinct clause
neighbourhoods, once per isomorphism class that preserves the two sides.
A formula reaches the exact analysis only when its GF(2) and GF(p) nullities
are at least three.  Both modular nullities bound the rational nullity from
above, so the screen drops no target.

The exact analysis groups the rational kernel columns into projective classes.
Every width-two frame is a class frame -- ``k`` independent classes whose
pairwise spans cover every class -- with one representative column chosen per
class.  An exclusive pair meets every frame in exactly one element, with both
one-element states present.  It is a cell when its two kernel columns are
projectively independent and its primal incidence columns differ; every other
exclusive pair is dual-parallel or a primal twin, the two degeneracy forms of
Results AA-AD.

Every formula carrying a cell is profiled: exact-one solution count, class
geometry, its M(K4) core when the frames are K4 stars (``k4_core``), the
Boolean relation its frames induce on the classes of all class-level
exclusive pairs with that relation's Schaefer closure tags, the production
width-two basis census of ``run_cubic_admissible_cell_probe`` (which must
equal the class-frame expansion), and the production Result V admissibility
verdict of every cell.  An optional targeted stage grows the cell formulas of
the last census order by the Result AD matching extension.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
import subprocess
import time
from typing import Any, Iterable, Iterator

import run_cubic_admissible_cell_probe as production

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "_diag" / "cubic_cell_census_probe.json"
DEFAULT_SLICE_DIR = ROOT / "_diag" / "cubic_cell_census"
SCHEMA = "cassifi.cubic-cell-census-probe.v1"
SLICE_SCHEMA = "cassifi.cubic-cell-census-slice.v1"
WSL = ("wsl", "-d", "Ubuntu-24.04", "-e")
GENBG = ("nauty-genbg", "-c", "-z", "-q", "-d3:3", "-D3:3")
LABELG = ("nauty-labelg", "-q")
PRIME = 2_147_483_647
TARGET_NULLITY = 3

Formula = tuple[tuple[int, ...], ...]
Pair = tuple[int, int]


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def json_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def one_based(formula: Formula) -> Formula:
    return tuple(tuple(v + 1 for v in row) for row in formula)


# Graph encodings ------------------------------------------------------------


def formula_from_graph6(text: str, n: int) -> Formula:
    """Clause rows of a genbg graph: variables 0..n-1, clauses n..2n-1."""
    data = text.strip()
    size = ord(data[0]) - 63
    if size != 2 * n:
        raise ValueError(f"graph6 {data!r} has {size} vertices, expected {2 * n}")
    bits = [(ord(ch) - 63) >> shift & 1 for ch in data[1:] for shift in range(5, -1, -1)]
    rows: list[list[int]] = [[] for _ in range(n)]
    index = 0
    for j in range(1, size):
        for i in range(j):
            if bits[index]:
                if not i < n <= j:
                    raise ValueError(f"graph6 {data!r} is not variable/clause bipartite")
                rows[j - n].append(i)
            index += 1
    if any(len(row) != 3 for row in rows):
        raise ValueError(f"graph6 {data!r} is not cubic")
    return tuple(sorted(tuple(sorted(row)) for row in rows))


def graph6_of(formula: Formula) -> str:
    n = len(formula)
    size = 2 * n
    edges = {(v, n + c) for c, row in enumerate(formula) for v in row}
    bits = [1 if (i, j) in edges else 0 for j in range(1, size) for i in range(j)]
    bits += [0] * (-len(bits) % 6)
    body = "".join(
        chr(63 + int("".join(map(str, bits[i : i + 6])), 2)) for i in range(0, len(bits), 6)
    )
    return chr(size + 63) + body


def canonical_labels(formulas: list[Formula]) -> list[str]:
    """Side-preserving canonical graph6 labels from nauty labelg."""
    if not formulas:
        return []
    n = len(formulas[0])
    payload = "".join(graph6_of(f) + "\n" for f in formulas).encode("ascii")
    command = [*WSL, *LABELG, "-f" + "a" * n + "b" * n]
    # Binary pipes: a Windows text pipe would send CRLF, which labelg rejects.
    done = subprocess.run(command, input=payload, capture_output=True, check=True)
    labels = [line for line in done.stdout.decode("ascii").splitlines() if line.strip()]
    if len(labels) != len(formulas):
        raise RuntimeError(f"labelg returned {len(labels)} labels for {len(formulas)} graphs")
    return labels


# Exact and modular linear algebra -------------------------------------------


def rank_gf2(formula: Formula, n: int) -> int:
    rows = [sum(1 << v for v in row) for row in formula]
    rank = 0
    for bit in range(n):
        pivot = next((i for i in range(rank, len(rows)) if rows[i] >> bit & 1), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(len(rows)):
            if i != rank and rows[i] >> bit & 1:
                rows[i] ^= rows[rank]
        rank += 1
    return rank


def rank_mod_prime(formula: Formula, n: int, prime: int = PRIME) -> int:
    rows = [[1 if j in row else 0 for j in range(n)] for row in formula]
    rank = 0
    for col in range(n):
        pivot = next((i for i in range(rank, len(rows)) if rows[i][col] % prime), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        inverse = pow(rows[rank][col], prime - 2, prime)
        rows[rank] = [x * inverse % prime for x in rows[rank]]
        for i in range(len(rows)):
            if i != rank and rows[i][col]:
                factor = rows[i][col]
                rows[i] = [(x - factor * y) % prime for x, y in zip(rows[i], rows[rank])]
        rank += 1
    return rank


def rank_exact(vectors: Iterable[Iterable[int]]) -> int:
    rows = [[Fraction(x) for x in vector] for vector in vectors]
    rank = 0
    width = len(rows[0]) if rows else 0
    for col in range(width):
        pivot = next((i for i in range(rank, len(rows)) if rows[i][col]), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(rank + 1, len(rows)):
            if rows[i][col]:
                factor = rows[i][col] / rows[rank][col]
                rows[i] = [x - factor * y for x, y in zip(rows[i], rows[rank])]
        rank += 1
    return rank


def kernel_basis(formula: Formula, n: int) -> list[list[int]]:
    """Primitive integer basis of the rational kernel of the incidence matrix."""
    rows = [[Fraction(1 if j in row else 0) for j in range(n)] for row in formula]
    pivots: list[int] = []
    rank = 0
    for col in range(n):
        pivot = next((i for i in range(rank, len(rows)) if rows[i][col]), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        inverse = 1 / rows[rank][col]
        rows[rank] = [x * inverse for x in rows[rank]]
        for i in range(len(rows)):
            if i != rank and rows[i][col]:
                factor = rows[i][col]
                rows[i] = [x - factor * y for x, y in zip(rows[i], rows[rank])]
        pivots.append(col)
        rank += 1
    pivot_set = set(pivots)
    basis = []
    for free in (c for c in range(n) if c not in pivot_set):
        vector = [Fraction(0)] * n
        vector[free] = Fraction(1)
        for i, col in enumerate(pivots):
            vector[col] = -rows[i][free]
        scale = math.lcm(*(x.denominator for x in vector))
        integers = [int(x * scale) for x in vector]
        divisor = math.gcd(*integers)
        basis.append([x // divisor for x in integers])
    return basis


# Frames, exclusive pairs and cells ------------------------------------------


def kernel_profile(formula: Formula) -> dict[str, Any]:
    """Exact class frames, exclusive pairs and cells of one formula."""
    n = len(formula)
    basis = kernel_basis(formula, n)
    k = len(basis)
    columns = [tuple(vector[j] for vector in basis) for j in range(n)]
    classes: dict[tuple[Fraction, ...], list[int]] = {}
    loops = []
    for j, column in enumerate(columns):
        if not any(column):
            loops.append(j)
            continue
        lead = next(x for x in column if x)
        classes.setdefault(tuple(Fraction(x, lead) for x in column), []).append(j)
    members = list(classes.values())
    vectors = [columns[group[0]] for group in members]
    m = len(members)
    span_masks: dict[Pair, int] = {}
    for a, b in itertools.combinations(range(m), 2):
        mask = (1 << a) | (1 << b)
        for c in range(m):
            if c != a and c != b and rank_exact((vectors[a], vectors[b], vectors[c])) == 2:
                mask |= 1 << c
        span_masks[(a, b)] = mask
    full = (1 << m) - 1
    if k == 0:
        frames: list[tuple[int, ...]] = [()]
    elif k == 1:
        frames = [(0,)]
    else:
        frames = []
        for subset in itertools.combinations(range(m), k):
            cover = 0
            for pair in itertools.combinations(subset, 2):
                cover |= span_masks[pair]
            if cover == full and rank_exact(vectors[c] for c in subset) == k:
                frames.append(subset)
    frame_sets = [set(frame) for frame in frames]
    sizes = [len(group) for group in members]
    class_of = {j: c for c, group in enumerate(members) for j in group}
    class_exclusive = [
        (a, b)
        for a, b in itertools.combinations(range(m), 2)
        if frames and {(a in s, b in s) for s in frame_sets} == {(True, False), (False, True)}
    ]
    exclusive = [
        tuple(sorted((members[a][0], members[b][0])))
        for a, b in class_exclusive
        if sizes[a] == 1 and sizes[b] == 1
    ]
    in_every_frame = set.intersection(*frame_sets) if frames else set()
    exclusive += [tuple(members[c]) for c in in_every_frame if sizes[c] == 2]
    exclusive.sort()
    incidence = [frozenset(c for c, row in enumerate(formula) if j in row) for j in range(n)]
    dual_parallel = [pair for pair in exclusive if class_of[pair[0]] == class_of[pair[1]]]
    primal_twins = [pair for pair in exclusive if incidence[pair[0]] == incidence[pair[1]]]
    cells = [pair for pair in exclusive if pair not in dual_parallel and pair not in primal_twins]
    lines = sorted(
        {mask for mask in span_masks.values() if bin(mask).count("1") >= 3}
    )
    return {
        "nullity": k,
        "loops": loops,
        "classes": members,
        "lines": [[c for c in range(m) if mask >> c & 1] for mask in lines],
        "class_frames": [list(frame) for frame in frames],
        "frames": sum(math.prod(sizes[c] for c in frame) for frame in frames),
        "class_exclusive": [list(pair) for pair in class_exclusive],
        "exclusive": [list(pair) for pair in exclusive],
        "dual_parallel": [list(pair) for pair in dual_parallel],
        "primal_twins": [list(pair) for pair in primal_twins],
        "cells": [list(pair) for pair in cells],
    }


# Relation, geometry and solutions of cell formulas --------------------------


def closed_under(relation: list[tuple[int, ...]], operation, arity: int) -> bool:
    members = set(relation)
    return all(
        tuple(operation(*column) for column in zip(*rows)) in members
        for rows in itertools.product(relation, repeat=arity)
    )


def schaefer_tags(relation: list[tuple[int, ...]]) -> list[str]:
    width = len(relation[0]) if relation else 0
    tags = []
    if (0,) * width in relation:
        tags.append("zero_valid")
    if (1,) * width in relation:
        tags.append("one_valid")
    if closed_under(relation, lambda a, b, c: a ^ b ^ c, 3):
        tags.append("affine")
    if closed_under(relation, lambda a, b, c: (a & b) | (b & c) | (a & c), 3):
        tags.append("bijunctive")
    if closed_under(relation, lambda a, b: a & b, 2):
        tags.append("horn")
    if closed_under(relation, lambda a, b: a | b, 2):
        tags.append("dual_horn")
    return tags


def k4_core(profile: dict[str, Any]) -> dict[str, Any] | None:
    """The M(K4) core of a nullity-three class geometry.

    Four lines of at least three classes meet pairwise in six distinct classes
    and together hold every class. The six meets are the edges of K4, the four
    lines its triangles, and the K4 stars are the triangles of meets left by
    omitting one line. A class beyond the six marks its line; a star omitting
    a marked line leaves that class uncovered, so the predicted frames are the
    stars omitting an unmarked line. Opposite K4 edges are the meets of
    complementary line pairs."""
    if profile["nullity"] != 3:
        return None
    lines = [frozenset(line) for line in profile["lines"]]
    everything = set(range(len(profile["classes"])))
    for quad in itertools.combinations(lines, 4):
        meets = {}
        for a, b in itertools.combinations(range(4), 2):
            common = quad[a] & quad[b]
            if len(common) != 1:
                break
            meets[(a, b)] = next(iter(common))
        else:
            covered = set().union(*quad)
            if len(set(meets.values())) != 6 or covered != everything:
                continue
            extra = sorted(covered - set(meets.values()))
            class_of = {j: c for c, group in enumerate(profile["classes"]) for j in group}
            opposite = {
                frozenset((meets[pair], meets[tuple(sorted(set(range(4)) - set(pair)))]))
                for pair in itertools.combinations(range(4), 2)
            }
            marked = [i for i in range(4) if quad[i] & set(extra)]
            stars = sorted(
                sorted(meets[pair] for pair in itertools.combinations([i for i in range(4) if i != omit], 2))
                for omit in range(4)
                if omit not in marked
            )
            return {
                "lines": [sorted(line) for line in quad],
                "extra_classes": extra,
                "marked_lines": marked,
                "other_lines": len(lines) - 4,
                "stars": stars,
                "frames_are_unmarked_stars": stars == sorted(sorted(f) for f in profile["class_frames"]),
                "cells_are_opposite_edges": all(
                    frozenset((class_of[p], class_of[q])) in opposite for p, q in profile["cells"]
                ),
            }
    return None


def exact_one_solutions(formula: Formula) -> int:
    n = len(formula)
    occurs: list[list[int]] = [[] for _ in range(n)]
    for c, row in enumerate(formula):
        for v in row:
            occurs[v].append(c)
    count = 0
    value = [-1] * n
    satisfied = [False] * len(formula)

    def search(c: int) -> None:
        nonlocal count
        while c < len(formula) and satisfied[c]:
            c += 1
        if c == len(formula):
            count += 1
            return
        for chosen in formula[c]:
            if value[chosen] == 0:
                continue
            trail = []
            ok = True
            for v in formula[c]:
                want = 1 if v == chosen else 0
                if value[v] == -1:
                    value[v] = want
                    trail.append(v)
                elif value[v] != want:
                    ok = False
                    break
            if ok:
                touched = []
                for v in trail:
                    if value[v] == 1:
                        for d in occurs[v]:
                            if satisfied[d]:
                                ok = False
                            else:
                                satisfied[d] = True
                                touched.append(d)
                if ok:
                    for v in trail:
                        if value[v] == 1:
                            for d in occurs[v]:
                                for u in formula[d]:
                                    if u != v and value[u] == 1:
                                        ok = False
                    if ok:
                        search(c + 1)
                for d in touched:
                    satisfied[d] = False
            for v in trail:
                value[v] = -1

    search(0)
    return count


def cell_record(label: str, formula: Formula, profile: dict[str, Any]) -> dict[str, Any]:
    """Relation, geometry, solutions and production certificates of a cell formula."""
    n = len(formula)
    frames = [set(frame) for frame in profile["class_frames"]]
    ports = sorted({c for pair in profile["class_exclusive"] for c in pair})
    relation = sorted({tuple(int(c in frame) for c in ports) for frame in frames})
    core = k4_core(profile)
    parity = None
    if core is not None and core["frames_are_unmarked_stars"] and len(core["stars"]) == 4:
        pairs = profile["class_exclusive"]
        parity = sorted({sum(int(a in frame) for a, _ in pairs) % 2 for frame in frames})
    formula_one = one_based(formula)
    census = production.enumerate_width_two_bases(formula_one)
    if census["status"] != "exact":
        raise RuntimeError(f"production census inexact for {label}: {census['status']}")
    members = profile["classes"]
    expanded = sorted(
        tuple(sorted(j + 1 for j in choice))
        for frame in profile["class_frames"]
        for choice in itertools.product(*(members[c] for c in frame))
    )
    produced = sorted(tuple(basis) for basis in census["width_two_bases"])
    graph = production.build_basis_exchange_graph(census["width_two_bases"], n)
    verdicts = []
    for p, q in profile["cells"]:
        verdict = production.classify_admissible_pair(formula_one, graph, (p + 1, q + 1))
        verdicts.append(
            {
                "ports": [p + 1, q + 1],
                "admissible": verdict["admissible"],
                "reasons": verdict["rejection_reasons"],
            }
        )
    return {
        "label": label,
        "formula": [list(row) for row in formula_one],
        "formula_sha256": json_digest([list(row) for row in formula_one]),
        "nullity": profile["nullity"],
        "loops": [j + 1 for j in profile["loops"]],
        "classes": [[j + 1 for j in group] for group in members],
        "lines": profile["lines"],
        "class_frames": profile["class_frames"],
        "frames": profile["frames"],
        "class_exclusive": profile["class_exclusive"],
        "cells": [[p + 1, q + 1] for p, q in profile["cells"]],
        "relation_ports": ports,
        "relation": [list(row) for row in relation],
        "schaefer": schaefer_tags(relation),
        "k4_core": core,
        "parity": parity,
        "exact_one_solutions": exact_one_solutions(formula),
        "production_frames_agree": expanded == produced,
        "production_frames": len(produced),
        "exchange_graph_connected": graph["connected"],
        "exchange_graph_components": graph["component_count"],
        "admissibility": verdicts,
    }


# Complete census --------------------------------------------------------------


def target_summary(label: str, profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": label,
        "nullity": profile["nullity"],
        "classes": len(profile["classes"]),
        "loops": len(profile["loops"]),
        "frames": profile["frames"],
        "exclusive": len(profile["exclusive"]),
        "dual_parallel": len(profile["dual_parallel"]),
        "primal_twins": len(profile["primal_twins"]),
        "cells": profile["cells"],
    }


def census_slice(n: int, res: int, mod: int, path: str) -> dict[str, Any]:
    """One genbg residue class of order n, cached on disk."""
    target = Path(path)
    command = [*WSL, *GENBG, str(n), str(n)] + ([f"{res}/{mod}"] if mod > 1 else [])
    if target.exists():
        cached = json.loads(target.read_text(encoding="utf-8"))
        if cached.get("schema") == SLICE_SCHEMA and cached.get("command") == command:
            return cached
    started = time.time()
    stats: Counter[str] = Counter()
    targets = []
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True, bufsize=1 << 20) as proc:
        assert proc.stdout is not None
        for text in proc.stdout:
            if not text.strip():
                continue
            formula = formula_from_graph6(text, n)
            stats["formulas"] += 1
            if n - rank_gf2(formula, n) < TARGET_NULLITY:
                continue
            stats["gf2_pass"] += 1
            if n - rank_mod_prime(formula, n) < TARGET_NULLITY:
                continue
            stats["modp_pass"] += 1
            profile = kernel_profile(formula)
            if profile["nullity"] >= TARGET_NULLITY:
                targets.append(target_summary(text.strip(), profile))
    if proc.returncode:
        raise RuntimeError(f"{command} exited with {proc.returncode}")
    result = {
        "schema": SLICE_SCHEMA,
        "order": n,
        "res": res,
        "mod": mod,
        "command": command,
        "stats": dict(stats),
        "targets": targets,
        "seconds": round(time.time() - started, 2),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result), encoding="utf-8")
    return result


def slice_count(n: int, slices: int, large_slices: int) -> int:
    if n <= 11:
        return 1
    return large_slices if n >= 14 else slices


def order_summary(n: int, parts: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stats: Counter[str] = Counter()
    targets = []
    for part in sorted(parts, key=lambda p: p["res"]):
        stats.update(part["stats"])
        targets.extend(part["targets"])
    nullity = Counter(t["nullity"] for t in targets)
    summary = {
        "order": n,
        "slices": len(parts),
        "formulas": stats["formulas"],
        "gf2_pass": stats["gf2_pass"],
        "modp_pass": stats["modp_pass"],
        "targets": len(targets),
        "nullity_histogram": {str(k): nullity[k] for k in sorted(nullity)},
        "exclusive_pairs": sum(t["exclusive"] for t in targets),
        "dual_parallel_pairs": sum(t["dual_parallel"] for t in targets),
        "primal_twin_pairs": sum(t["primal_twins"] for t in targets),
        "cells": sum(len(t["cells"]) for t in targets),
        "cell_formulas": sum(1 for t in targets if t["cells"]),
        "slice_seconds": round(sum(p["seconds"] for p in parts), 2),
    }
    return summary, [t for t in targets if t["cells"]]


# Targeted extension -----------------------------------------------------------


def extension_children(formula: Formula) -> Iterator[Formula]:
    """Result AD step: incidence edges (c_i, v_i) with distinct clauses and
    variables move onto a new variable, and {v_1, v_2, v_3} becomes a clause."""
    n = len(formula)
    rows = set(formula)
    for i, j, k in itertools.combinations(range(n), 3):
        for a in formula[i]:
            for b in formula[j]:
                if b == a:
                    continue
                for c in formula[k]:
                    if c == a or c == b:
                        continue
                    new = tuple(sorted((a, b, c)))
                    if new in rows:
                        continue
                    child = list(formula)
                    child[i] = tuple(sorted(n if v == a else v for v in formula[i]))
                    child[j] = tuple(sorted(n if v == b else v for v in formula[j]))
                    child[k] = tuple(sorted(n if v == c else v for v in formula[k]))
                    child.append(new)
                    if len(set(child)) == len(child):
                        yield tuple(sorted(child))


def screened_profile(formula: Formula) -> dict[str, Any] | None:
    n = len(formula)
    if n - rank_gf2(formula, n) < TARGET_NULLITY:
        return None
    if n - rank_mod_prime(formula, n) < TARGET_NULLITY:
        return None
    profile = kernel_profile(formula)
    return profile if profile["nullity"] >= TARGET_NULLITY else None


def extension_chunk(chunk: list[tuple[str, Formula]]) -> list[tuple[str, Formula, dict[str, Any]]]:
    out = []
    for label, formula in chunk:
        profile = screened_profile(formula)
        if profile is not None:
            out.append((label, formula, profile))
    return out


def extend(
    frontier: list[Formula], levels: int, pool: ProcessPoolExecutor, workers: int
) -> list[dict[str, Any]]:
    stages = []
    for _ in range(levels):
        if not frontier:
            break
        started = time.time()
        raw = 0
        children: set[Formula] = set()
        for formula in frontier:
            for child in extension_children(formula):
                raw += 1
                children.add(child)
        ordered = sorted(children)
        unique: dict[str, Formula] = {}
        for label, child in zip(canonical_labels(ordered), ordered):
            unique.setdefault(label, child)
        items = sorted(unique.items())
        size = max(1, len(items) // (workers * 4) + 1)
        chunks = [items[i : i + size] for i in range(0, len(items), size)]
        targets = [row for part in pool.map(extension_chunk, chunks) for row in part]
        carriers = [(label, formula, profile) for label, formula, profile in targets if profile["cells"]]
        records = [cell_record(label, formula, profile) for label, formula, profile in carriers]
        stages.append(
            {
                "order": len(ordered[0]) if ordered else None,
                "parents": len(frontier),
                "raw_children": raw,
                "distinct_children": len(ordered),
                "isomorphism_classes": len(items),
                "targets": len(targets),
                "cells": sum(len(profile["cells"]) for _, _, profile in carriers),
                "cell_formulas": records,
                "seconds": round(time.time() - started, 2),
            }
        )
        frontier = [formula for _, formula, _ in carriers]
    return stages


# Receipt ------------------------------------------------------------------------


def k4_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Cell formulas whose frames are unmarked K4 stars, and their cells that are opposite K4 edges."""
    star = [r for r in records if r["k4_core"] is not None and r["k4_core"]["frames_are_unmarked_stars"]]
    return {
        "k4_star_cell_formulas": len(star),
        "k4_opposite_edge_cell_formulas": sum(1 for r in star if r["k4_core"]["cells_are_opposite_edges"]),
    }


def relation_type(record: dict[str, Any]) -> str:
    core = record["k4_core"]
    if core is not None and core["frames_are_unmarked_stars"]:
        shape = f"k4_{len(core['stars'])}_stars"
    else:
        shape = f"{len(record['class_frames'])}_frames"
    return f"{shape}:{'+'.join(record['schaefer'])}"


def assessment(orders: list[dict[str, Any]], cell_records: list[dict[str, Any]]) -> dict[str, Any]:
    closed_through = None
    for summary in sorted(orders, key=lambda s: s["order"]):
        if summary["cells"]:
            break
        closed_through = summary["order"]
    first = next((s["order"] for s in sorted(orders, key=lambda s: s["order"]) if s["cells"]), None)
    verdicts = [v for record in cell_records for v in record["admissibility"]]
    return {
        "degeneracy_closure_holds_through_order": closed_through,
        "first_cell_order": first,
        "cell_formulas_profiled": len(cell_records),
        "all_relations_affine": all("affine" in r["schaefer"] for r in cell_records),
        "relation_types": dict(sorted(Counter(relation_type(r) for r in cell_records).items())),
        **k4_counts(cell_records),
        "production_frames_agree": all(r["production_frames_agree"] for r in cell_records),
        "admissible_cells": sum(1 for v in verdicts if v["admissible"]),
        "rejection_reasons": dict(
            sorted(Counter("+".join(v["reasons"]) for v in verdicts if not v["admissible"]).items())
        ),
    }


def parse_orders(text: str) -> list[int]:
    orders: set[int] = set()
    for part in text.split(","):
        if "-" in part:
            low, high = part.split("-")
            orders.update(range(int(low), int(high) + 1))
        else:
            orders.add(int(part))
    return sorted(orders)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--orders", default="6-13", help="census orders, e.g. 6-13 or 6-12,14")
    parser.add_argument("--extend-levels", type=int, default=0)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--slices", type=int, default=16, help="genbg slices for orders 12-13")
    parser.add_argument("--large-slices", type=int, default=64, help="genbg slices from order 14")
    parser.add_argument("--slice-dir", type=Path, default=DEFAULT_SLICE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    orders = parse_orders(args.orders)
    started = time.time()
    version = subprocess.run(
        [*WSL, "dpkg-query", "-W", "-f", "${Version}", "nauty"], capture_output=True, text=True
    ).stdout.strip()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs = {}
        for n in sorted(orders, reverse=True):
            mod = slice_count(n, args.slices, args.large_slices)
            for res in range(mod):
                path = args.slice_dir / f"n{n}_{res}of{mod}.json"
                jobs[(n, res)] = pool.submit(census_slice, n, res, mod, str(path))
        summaries = []
        cell_records = []
        for n in orders:
            parts = [jobs[(n, res)].result() for res in range(slice_count(n, args.slices, args.large_slices))]
            summary, carriers = order_summary(n, parts)
            records = []
            for carrier in carriers:
                formula = formula_from_graph6(carrier["label"], n)
                records.append(cell_record(carrier["label"], formula, kernel_profile(formula)))
            summary["cell_formulas"] = len(records)
            summaries.append(summary)
            cell_records.extend(records)
            print(
                f"order {n}: {summary['formulas']} formulas, {summary['targets']} targets, "
                f"{summary['exclusive_pairs']} exclusive pairs, {summary['cells']} cells "
                f"in {len(records)} formulas",
                flush=True,
            )
        top = max(orders)
        frontier = [tuple(tuple(v - 1 for v in row) for row in r["formula"]) for r in cell_records if len(r["formula"]) == top]
        stages = extend(frontier, args.extend_levels, pool, args.workers)
    for stage in stages:
        print(
            f"extension order {stage['order']}: {stage['isomorphism_classes']} classes, "
            f"{stage['targets']} targets, {stage['cells']} cells in {len(stage['cell_formulas'])} formulas",
            flush=True,
        )
    extension_records = [r for stage in stages for r in stage["cell_formulas"]]
    receipt = {
        "schema": SCHEMA,
        "generator": {
            "genbg": [*WSL, *GENBG],
            "labelg": [*WSL, *LABELG],
            "nauty_version": version,
            "screen_prime": PRIME,
            "target_nullity": TARGET_NULLITY,
        },
        "census": {"orders": summaries, "cell_formulas": cell_records},
        "extension": {
            "step": "Result AD matching extension from the cell formulas of the top census order",
            "stages": stages,
        },
        "assessment": {
            "census": assessment(summaries, cell_records),
            "extension_relation_types": dict(
                sorted(Counter(relation_type(r) for r in extension_records).items())
            ),
            "extension_all_relations_affine": all("affine" in r["schaefer"] for r in extension_records),
            "extension_k4": k4_counts(extension_records),
            "extension_admissible_cells": sum(
                1 for r in extension_records for v in r["admissibility"] if v["admissible"]
            ),
        },
        "seconds": round(time.time() - started, 2),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(json.dumps(receipt["assessment"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
