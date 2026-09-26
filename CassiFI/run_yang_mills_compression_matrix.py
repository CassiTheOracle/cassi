#!/usr/bin/env python3
"""UFA105: the compression matrix of the finite-obligation map, on the smallest cases.

The map (CassiTheory/computations/yang-mills-uniform-feshbach-obligation-map.md, section
4.4.7) records as its next adjacent-block obligation the general compression matrix

    K_{alpha -> alpha +- e_c}: M^f(alpha) -> M^f(alpha +- e_c),                     (UFA105)

whose *vanishing pattern* decides which sector families can be exact (UFA107).  The map
supplies the source and target spaces (UFA106), the sector-shift support action (UFA104)
and a slice derivation for the diagonal sectors; it does not supply the operator
normalization.  This runner therefore computes an explicitly declared realization of the
obligation and reports which pieces of it are settled and which stay open.

Declared model C1 (rim/fusion-tree realization)
-----------------------------------------------
* Sector alpha = (a,b,c,d): the four corner-pair labels of the refined 2x2 square, rim
  links L1..L8 cyclically with corner pairs (L1,L8)=a, (L2,L3)=b, (L4,L5)=c, (L6,L7)=d.
* Fine basis of M^f(alpha): the map's own labelings (s1,s2,s3,s4,r) with
  s1 in fuse(a,b), s2 in fuse(b,c), s3 in fuse(c,d), s4 in fuse(d,a) and
  r in fuse(s1,s2) cap fuse(s3,s4)  [the (s1,s2)|(s3,s4) pairing of (UFA106)].
* Each basis vector is realized as an exact invariant tensor of the interior fusion tree
  (the four midpoint intertwiners iota(a,b,s1)..iota(d,a,s4) contracted with the centre
  channel r) living in V_{L1} (x) ... (x) V_{L8}: the eight rim legs are kept OPEN.
* The corner-a multiplier is realized as the explicit fundamental insertion at the two
  open rim legs of corner a's pair, with the fundamental indices contracted ("curl"); the
  intertwiners are the exact SU(2) Clebsch-Gordan invariants obtained as the kernel of the
  su(2) action on the tensor product (integer/rational arithmetic throughout).
* Declared Hilbert structure on each rim leg: the unitary one, <e_k,e_k> = 1/C(n,k)
  (validated below by generator Hermiticity).  A corner-epsilon-paired variant is reported.

Status: declared_proxy.  It is a finite, exactly computable realization of the objects
(UFA105) names, not the map's unspecified full Peter-Weyl/lattice normalization.

Three scope statements
----------------------
The label-at-most-two extension is reported three times, in three explicitly separated scopes.
The stored default scope is computed at FRONTIER_DIM, the narrower frontier, because the test
suite rebuilds the whole receipt inside its own wall-clock bound.  A second section
(widened_scope) recomputes the same family at WIDENED_FRONTIER_DIM, the widest frontier the
runner's usual budget allows, and records what the extra time buys.  A third section
(complete_family) computes the family with no block left out at all, at COMPLETE_FRONTIER_DIM,
entered only through the runner's opt-in path and declaring its own measured cost, so the
reading of the family is total while the default path and the test suite stay cheap.  No scope
hides another: each carries its own computed and excluded counts, and the blocks they share are
compared entry for entry and witness row for witness row.  Every block the default scope or the
widened scope leaves out is listed with its exact dimensions, cost units and the rule that
excluded it.

Rank witness
------------
Since the load-bearing structural reading is full-rank saturation (rank = min(shape) for every
computed block), each computed block additionally gets a rank witness: an explicit
min(shape)-sized minor, triangular under a declared ordering rule with a nonzero diagonal in
the declared entries, verified against the block's own entries.  The search is declared and
bounded, so a block without a witness says which kind of negative it is - 'exhausted' (the
search covered the whole space at that minor size, an exact negative inside the declared
entries), 'budget_limited', or 'above_exact_search_size' - and a fraction below one is never
reported as a proof that no witness exists.

Receipt digest
--------------
receipt_sha256 is the sha256 of the canonical JSON of the receipt body with every leaf whose key
is declared in TIMING_KEYS removed (receipt_sha256, runtime_seconds, elapsed_seconds,
measured_seconds, condensation_elapsed_seconds).  Those keys hold the only values this runner
reads from the clock, so the digest is a content digest: two identical runs produce one digest,
which is what lets a reader check a stored receipt against a rebuild.  The receipt states this
declaration in its own digest_convention field, and build_receipt refuses to finish if any other
leaf carries a run-varying value (a float under a clock-named key, or prose carrying a fractional
seconds figure) - the earlier complete-family prose did exactly that and moved the digest between
runs.  The per-frontier and per-shape build seconds recorded in the receipt are declared constants
measured once on the development machine, not clock readings, so they are part of the digested
body.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from fractions import Fraction as F
from itertools import product
from math import comb, gcd
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import numpy as np

REPO = Path(__file__).resolve().parent
SOURCE_DOCUMENT = (
    REPO.parent / "CassiTheory" / "computations" / "yang-mills-uniform-feshbach-obligation-map.md"
)
OUT_PATH = REPO / "_diag" / "yang_mills_compression_matrix.json"

SCHEMA = "cassi.yang_mills.compression_matrix.v1"

# line ranges read from the map (1-based, inclusive) and quoted verbatim in the receipt
QUOTED_RANGES = (
    (2256, 2264, "sector definition: eight boundary links, corner pairs, fuse"),
    (2266, 2271, "UFA103 fundamental plaquette multiplication"),
    (2274, 2285, "UFA104 corner multiplier support action"),
    (2287, 2312, "slice derivation and the UFA105 statement"),
    (2314, 2319, "sector families and label-cutoff counts"),
    (2321, 2333, "UFA106 fine multiplicity space"),
    (2338, 2346, "UFA106 anchor table"),
    (2348, 2354, "fundamental row decomposition and never-zero minimum"),
    (2356, 2364, "UFA107 exactness consequence"),
    (2366, 2379, "candidate diagonal compressions and the recorded obligation"),
    (2381, 2384, "scope of the section"),
)

ANCHOR_TABLE = (
    ((0, 0, 0, 0), 1),
    ((1, 1, 0, 0), 2),
    ((1, 1, 1, 1), 14),
    ((2, 1, 1, 1), 19),
    ((2, 2, 1, 1), 30),
    ((3, 1, 1, 1), 20),
    ((2, 2, 2, 2), 91),
)
CUTOFF_COUNTS = ((1, 16), (2, 81), (3, 256), (4, 625))

SMALLEST_CUTOFF = 1  # labels of size at most one are the smallest cases the map names


# ---------------------------------------------------------------------------
# json / digest helpers (repo convention: run_fractal_lattice_exploration.py:4986-4998)
# ---------------------------------------------------------------------------
TIMING_KEYS = frozenset(
    {
        "elapsed_seconds",
        "runtime_seconds",
        "condensation_elapsed_seconds",
        "measured_seconds",
        "receipt_sha256",
    }
)

# A leaf that names a clock but is not declared in TIMING_KEYS, or prose carrying a fractional
# seconds figure, would make the content digest vary between two identical runs.  Both are
# refused at build time by run_varying_leaves below and asserted in the tests.
WALL_CLOCK_KEY = re.compile(r"(second|seconds|elapsed|runtime|wall)", re.IGNORECASE)
WALL_CLOCK_PROSE = re.compile(r"\d+\.\d+\s*s\b")
FLOAT_TYPES = (float, np.floating)


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, F):
        return str(value)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(k): strip_timing(v) for k, v in value.items() if k not in TIMING_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [strip_timing(v) for v in value]
    return value


def content_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(strip_timing(value)).encode("utf-8")).hexdigest()


def digest_body(value: Any) -> dict:
    """The exact body the content digest is taken over: the receipt without its digest field and
    without every leaf whose key is declared in TIMING_KEYS, stripped recursively."""
    body = strip_timing(value)
    if isinstance(body, Mapping):
        body = {k: v for k, v in body.items() if k != "receipt_sha256"}
    return body


def _leaves(value: Any, path: str = "receipt") -> Iterator[tuple]:
    if isinstance(value, Mapping):
        for k, v in value.items():
            yield from _leaves(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from _leaves(v, f"{path}[{i}]")
    else:
        yield path, value


def run_varying_leaves(value: Any) -> list:
    """Leaves inside the digest body that would change between two identical runs.

    The declared timing keys are stripped by name, so what must not survive inside the body is a
    leaf that carries a clock reading under some other name (a float under a key naming a clock)
    or a clock reading written into prose (a fractional seconds figure in a string).  Both forms
    are run-varying; everything else in the body is either a physical/mathematical quantity or a
    declared constant, including the per-frontier and per-shape build seconds measured once on the
    development machine.
    """
    violations = []
    for path, leaf in _leaves(digest_body(value)):
        key = path.rsplit(".", 1)[-1].rstrip("]").split("[")[0]
        if isinstance(leaf, FLOAT_TYPES) and WALL_CLOCK_KEY.search(key):
            violations.append(
                {
                    "path": path,
                    "value": float(leaf),
                    "why": (
                        "float under a clock-named key that is not in the declared strip set, so "
                        "the digest body would vary between two identical runs"
                    ),
                }
            )
        elif isinstance(leaf, str) and WALL_CLOCK_PROSE.search(leaf):
            violations.append(
                {
                    "path": path,
                    "value": leaf[:120],
                    "why": (
                        "prose carrying a fractional seconds figure, so the digest body would "
                        "vary between two identical runs"
                    ),
                }
            )
    return violations


def digest_convention() -> dict:
    """Declared, digested description of what content-stability means for this receipt."""
    return {
        "digest_field": "receipt_sha256",
        "algorithm": (
            "sha256 hex of canonical_json(body), where body is the receipt without receipt_sha256 "
            "and without every leaf whose key is in stripped_keys, stripped recursively at any depth"
        ),
        "canonical_json": (
            "json.dumps(sort_keys=True, separators=(',', ':'), allow_nan=False) after Fractions "
            "and numpy scalars are flattened to str/float"
        ),
        "stripped_keys": sorted(TIMING_KEYS),
        "stability_rule": (
            "inside the body no leaf may carry a run-varying value: a float under a clock-named "
            "key or a string carrying a fractional seconds figure is refused at build time "
            "(run_varying_leaves) and asserted against the stored artifact in the tests, so two "
            "identical runs produce one digest"
        ),
        "declared_measurements_note": (
            "the per-frontier extension times and the per-shape block times recorded in this "
            "receipt are declared constants measured once on the development machine, not values "
            "read from the clock during the run, so they are part of the digested body; the only "
            "clock readings this receipt makes (its own build seconds and the scopes' elapsed "
            "seconds) are in stripped_keys"
        ),
    }


def assert_finite(value: Any, path: str = "receipt") -> None:
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise AssertionError(f"non-finite float at {path}")
    elif isinstance(value, Mapping):
        for k, v in value.items():
            assert_finite(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            assert_finite(v, f"{path}[{i}]")


# ---------------------------------------------------------------------------
# exact su(2): V_n = homogeneous degree-n polynomials in (x,y), basis x^{n-k} y^k
# ---------------------------------------------------------------------------
def dim(n: int) -> int:
    return n + 1


def as_fraction(value: Any) -> F:
    """Exact conversion that never truncates: Fractions (including 1/2 from metric_inverse) survive."""
    if isinstance(value, F):
        return value
    if isinstance(value, (int, np.integer)):
        return F(int(value))
    return F(value)


def _identity(n: int) -> list[list[F]]:
    return [[F(1) if i == j else F(0) for j in range(dim(n))] for i in range(dim(n))]


def _j3(n: int) -> list[list[F]]:
    return [[F(n, 2) - k if j == k else F(0) for j in range(dim(n))] for k in range(dim(n))]


def _jp(n: int) -> list[list[F]]:
    # J_+ e_a = a e_{a-1}: matrix entry (row k, column a) = k+1 when a == k+1
    return [[F(a) if k == a - 1 else F(0) for a in range(dim(n))] for k in range(dim(n))]


def _jm(n: int) -> list[list[F]]:
    # J_- e_a = (n-a) e_{a+1}: entry (row k, column a) = n-a when k == a+1
    return [[F(n - a) if k == a + 1 else F(0) for a in range(dim(n))] for k in range(dim(n))]


GENERATORS = (("j3", _j3), ("jp", _jp), ("jm", _jm))


def _kron(a: list[list[F]], b: list[list[F]]) -> list[list[F]]:
    ra, ca, rb, cb = len(a), len(a[0]), len(b), len(b[0])
    return [
        [a[i][j] * b[k][l] for j in range(ca) for l in range(cb)]
        for i in range(ra)
        for k in range(rb)
    ]


def _add(a: list[list[F]], b: list[list[F]]) -> list[list[F]]:
    return [[x + y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def total_generator(legs: Sequence[int], slot: int, generator) -> list[list[F]]:
    """generator acting in `slot` of the tensor product of V_{legs[s]}."""
    out: list[list[F]] | None = None
    for s, n in enumerate(legs):
        m = generator(n) if s == slot else _identity(n)
        out = m if out is None else _kron(out, m)
    return out


def _row_reduce(rows: list[list[F]], ncols: int) -> list[list[F]]:
    mat = [r[:] for r in rows if any(x != 0 for x in r)]
    pivots: list[int] = []
    r = 0
    for c in range(ncols):
        p = next((i for i in range(r, len(mat)) if mat[i][c] != 0), None)
        if p is None:
            continue
        mat[r], mat[p] = mat[p], mat[r]
        pv = mat[r][c]
        mat[r] = [x / pv for x in mat[r]]
        for i in range(len(mat)):
            if i != r and mat[i][c] != 0:
                f = mat[i][c]
                mat[i] = [x - f * y for x, y in zip(mat[i], mat[r])]
        pivots.append(c)
        r += 1
        if r == len(mat):
            break
    return mat[:r]


def nullspace(rows: list[list[F]], ncols: int) -> list[list[F]]:
    """Exact rational basis of the right nullspace."""
    mat = _row_reduce(rows, ncols)
    pivots = []
    r = 0
    for c in range(ncols):
        if r < len(mat) and mat[r][c] != 0:
            pivots.append(c)
            r += 1
    free = [c for c in range(ncols) if c not in pivots]
    basis = []
    for f in free:
        v = [F(0)] * ncols
        v[f] = F(1)
        for i, p in enumerate(pivots):
            v[p] = -mat[i][f]
        basis.append(v)
    return basis


_INVARIANT_CACHE: dict[tuple[int, ...], tuple[list[list[F]], int]] = {}


def invariant_space(legs: Sequence[int]) -> list[list[F]]:
    """Exact rational basis of Inv(V_{l1} (x) ... (x) V_{lk}) under the diagonal su(2)."""
    key = tuple(legs)
    if key in _INVARIANT_CACHE:
        basis, _ = _INVARIANT_CACHE[key]
        return basis
    total = 1
    for n in legs:
        total *= dim(n)
    rows: list[list[F]] = []
    for _, gen in GENERATORS:
        acc: list[list[F]] | None = None
        for slot in range(len(legs)):
            m = total_generator(legs, slot, gen)
            acc = m if acc is None else _add(acc, m)
        rows.extend(acc)
    basis = nullspace(rows, total)
    _INVARIANT_CACHE[key] = (basis, total)
    return basis


def _primitive_integers(vector: Sequence[F]) -> list[int]:
    den = 1
    for x in vector:
        den = den * x.denominator // gcd(den, x.denominator)
    ints = [int(x * den) for x in vector]
    g = 0
    for x in ints:
        g = gcd(g, abs(x))
    if g:
        ints = [x // g for x in ints]
    lead = next((x for x in ints if x != 0), 1)
    if lead < 0:
        ints = [-x for x in ints]
    return ints


_INVARIANT_TENSOR_CACHE: dict[tuple[int, ...], tuple[tuple[str, ...], np.ndarray]] = {}


def invariant_tensor(legs: Sequence[int]) -> tuple[tuple[str, ...], np.ndarray]:
    """The unique (up to scale) invariant tensor for `legs`, as a primitive integer array.

    Legs are named ``f0``, ``f1``, ... in the declared order.  Raises if the invariant
    space is not one-dimensional (all call sites below must be unique-channel triples).
    Results are memoized: the same triple recurs in many sectors, and the returned array
    is read-only to every call site (only contracted, never written).
    """
    key = tuple(legs)
    cached = _INVARIANT_TENSOR_CACHE.get(key)
    if cached is not None:
        return cached
    basis = invariant_space(legs)
    if len(basis) != 1:
        raise ValueError(f"invariants({tuple(legs)}) has dimension {len(basis)}, expected 1")
    ints = _primitive_integers(basis[0])
    arr = np.array(ints, dtype=object).reshape([dim(n) for n in legs])
    out = (tuple(f"f{i}" for i in range(len(legs))), arr)
    _INVARIANT_TENSOR_CACHE[key] = out
    return out


def metric(n: int) -> tuple[tuple[str, ...], np.ndarray]:
    return invariant_tensor((n, n))


def metric_inverse(n: int) -> list[list[F]]:
    g = metric(n)[1]
    size = dim(n)
    rows = [
        [F(int(g[i][j])) for j in range(size)] + [F(1) if i == j else F(0) for j in range(size)]
        for i in range(size)
    ]
    for c in range(size):
        p = next(i for i in range(c, size) if rows[i][c] != 0)
        rows[c], rows[p] = rows[p], rows[c]
        pv = rows[c][c]
        rows[c] = [x / pv for x in rows[c]]
        for i in range(size):
            if i != c and rows[i][c] != 0:
                f = rows[i][c]
                rows[i] = [x - f * y for x, y in zip(rows[i], rows[c])]
    return [[rows[i][size + j] for j in range(size)] for i in range(size)]


# ---------------------------------------------------------------------------
# label algebra (UFA103, UFA104, UFA106)
# ---------------------------------------------------------------------------
def fuse(m: int, n: int) -> list[int]:
    return list(range(abs(m - n), m + n + 1, 2))


def corners() -> tuple[str, ...]:
    return ("a", "b", "c", "d")


CORNER_PAIRS = (("L1", "L8"), ("L2", "L3"), ("L4", "L5"), ("L6", "L7"))
# midpoint k joins the two rim links listed, with corner labels alpha[i0], alpha[i1]
MIDPOINTS = (
    (("L1", "L2"), "s1", 0, 1),
    (("L3", "L4"), "s2", 1, 2),
    (("L5", "L6"), "s3", 2, 3),
    (("L7", "L8"), "s4", 3, 0),
)
SPOKES = ("s1", "s2", "s3", "s4")


def rim_labels(alpha: Sequence[int]) -> list[int]:
    a, b, c, d = alpha
    return [a, a, b, b, c, c, d, d]


def fine_basis(alpha: Sequence[int], pairing: str = "12|34") -> list[tuple[int, int, int, int, int]]:
    """The map's fine labelings; `pairing` selects the centre resolution of (UFA106)."""
    a, b, c, d = alpha
    spans = [fuse(a, b), fuse(b, c), fuse(c, d), fuse(d, a)]
    out: list[tuple[int, int, int, int, int]] = []
    for s1, s2, s3, s4 in product(*spans):
        if pairing == "12|34":
            common = sorted(set(fuse(s1, s2)) & set(fuse(s3, s4)))
        elif pairing == "14|23":
            common = sorted(set(fuse(s1, s4)) & set(fuse(s2, s3)))
        else:
            raise ValueError(pairing)
        for r in common:
            out.append((s1, s2, s3, s4, r))
    return out


def fine_dimension(alpha: Sequence[int], pairing: str = "12|34") -> int:
    return len(fine_basis(alpha, pairing))


# ---------------------------------------------------------------------------
# tensor helpers: legs are named; every leg is an upper (source) index
# ---------------------------------------------------------------------------
Tensor = tuple[tuple[str, ...], np.ndarray]


def contract(t1: Tensor, t2: Tensor, leg1: str, leg2: str, bridge: list[list[F]]) -> Tensor:
    """Contract `leg1` of t1 with `leg2` of t2 through the matrix `bridge`.

    The result index is the bridge's second index, so ``bridge = metric_inverse`` gives the
    declared invariant edge contraction and ``bridge = identity`` gives a plain index
    contraction.
    """
    legs1, arr1 = t1
    legs2, arr2 = t2
    i1 = legs1.index(leg1)
    i2 = legs2.index(leg2)
    if arr1.shape[i1] != len(bridge) or arr2.shape[i2] != len(bridge[0]):
        raise ValueError("bridge shape mismatch")
    raised = np.tensordot(arr1, np.array(bridge, dtype=object), axes=(i1, 0))
    legs_raised = [l for k, l in enumerate(legs1) if k != i1] + [leg2]
    moved = np.moveaxis(arr2, i2, -1)
    legs_moved = [l for k, l in enumerate(legs2) if k != i2]
    out = np.tensordot(raised, moved, axes=(-1, -1))
    return tuple(legs_raised[:-1] + legs_moved), out


def self_contract(t: Tensor, leg_a: str, leg_b: str, bridge: list[list[F]]) -> Tensor:
    """Contract two legs of the same tensor through `bridge` (used for the curl)."""
    legs, arr = t
    ia, ib = legs.index(leg_a), legs.index(leg_b)
    keep = [k for k in range(len(legs)) if k not in (ia, ib)]
    out_legs = tuple(legs[k] for k in keep)
    out_shape = tuple(arr.shape[k] for k in keep)
    out = np.zeros(out_shape, dtype=object)
    size = int(np.prod(out_shape)) if out_shape else 1
    for flat in range(size):
        idx = tuple(np.unravel_index(flat, out_shape)) if out_shape else ()
        total = F(0)
        for a in range(arr.shape[ia]):
            for b in range(arr.shape[ib]):
                if bridge[a][b] == 0:
                    continue
                full = [None] * len(legs)
                for pos, k in enumerate(keep):
                    full[k] = idx[pos]
                full[ia] = a
                full[ib] = b
                v = arr[tuple(full)]
                if v != 0:
                    total += as_fraction(v) * bridge[a][b]
        if total != 0:
            out[idx] = total
    return out_legs, out


def leg_dims(legs: Sequence[str], labels: Mapping[str, int]) -> list[int]:
    return [dim(labels[l]) for l in legs]


def flatten(tensor: Tensor, order: Sequence[str], labels: Mapping[str, int]) -> list[F]:
    legs, arr = tensor
    axes = [legs.index(l) for l in order]
    moved = np.transpose(arr, axes)
    return [as_fraction(x) for x in moved.reshape(-1)]


# ---------------------------------------------------------------------------
# the declared model C1
# ---------------------------------------------------------------------------
def centre_tensor(s1: int, s2: int, s3: int, s4: int, r: int, pairing: str = "12|34") -> Tensor:
    if pairing == "12|34":
        left = invariant_tensor((s1, s2, r))
        right = invariant_tensor((s3, s4, r))
        legs_l = ("s1", "s2", "R")
        legs_r = ("s3", "s4", "R")
    else:
        left = invariant_tensor((s1, s4, r))
        right = invariant_tensor((s2, s3, r))
        legs_l = ("s1", "s4", "R")
        legs_r = ("s2", "s3", "R")
    return contract((legs_l, left[1]), (legs_r, right[1]), "R", "R", metric_inverse(r))


def state_tensor(
    alpha: Sequence[int],
    labelling: Sequence[int],
    pairing: str = "12|34",
) -> Tensor:
    """Exact invariant tensor of the interior fusion tree with the eight rim legs open."""
    s1, s2, s3, s4, r = labelling
    labels = dict(zip(("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"), rim_labels(alpha)))
    labels.update({"s1": s1, "s2": s2, "s3": s3, "s4": s4})
    current = centre_tensor(s1, s2, s3, s4, r, pairing)
    for links, spoke, i0, i1 in MIDPOINTS:
        legs, arr = invariant_tensor((alpha[i0], alpha[i1], labels[spoke]))
        t = (links + (spoke,), arr)
        current = contract(t, current, spoke, spoke, metric_inverse(labels[spoke]))
    return current


def state_vector(alpha: Sequence[int], labelling: Sequence[int], pairing: str = "12|34") -> dict:
    labels = dict(zip(("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"), rim_labels(alpha)))
    tensor = state_tensor(alpha, labelling, pairing)
    order = ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8")
    vec = _primitive_integers(flatten(tensor, order, labels))
    return {
        "sector": list(alpha),
        "labelling": list(labelling),
        "leg_dims": [dim(labels[l]) for l in order],
        "vector": vec,
    }


_STATE_SUPPORT_CACHE: dict[tuple, tuple[list[int], dict[int, F]]] = {}
_STATE_SUPPORT_LIMIT = 8192  # declared memory bound: entries, cleared when exceeded


def state_support(
    alpha: Sequence[int], labelling: Sequence[int], pairing: str = "12|34"
) -> tuple[list[int], dict[int, F]]:
    """Flattened rim-leg vector of one basis state, as (leg_dims, nonzero entries).

    The states are mostly zero, so every contraction below works on the nonzero entries.
    The cache is bounded by the declared entry count above and cleared wholesale when it
    is exceeded, which keeps both memory and behaviour deterministic.
    """
    key = (tuple(alpha), tuple(labelling), pairing)
    hit = _STATE_SUPPORT_CACHE.get(key)
    if hit is not None:
        return hit
    entry = state_vector(alpha, labelling, pairing)
    out = (entry["leg_dims"], {i: x for i, x in enumerate(entry["vector"]) if x != 0})
    if len(_STATE_SUPPORT_CACHE) >= _STATE_SUPPORT_LIMIT:
        _STATE_SUPPORT_CACHE.clear()
    _STATE_SUPPORT_CACHE[key] = out
    return out


def flatten_support(
    tensor: Tensor, order: Sequence[str], labels: Mapping[str, int]
) -> dict[int, int]:
    """Nonzero entries of the flattened tensor, without materializing the dense vector.

    The entries are reduced to primitive integers by the same rule the dense path used
    (`_primitive_integers`), so a block's entries do not depend on which path produced
    them.
    """
    legs, arr = tensor
    axes = [legs.index(l) for l in order]
    moved = np.transpose(arr, axes)
    flat = moved.reshape(-1)
    support = {i: as_fraction(x) for i, x in enumerate(flat) if x != 0}
    if not support:
        return {}
    den = 1
    for x in support.values():
        den = den * x.denominator // gcd(den, x.denominator)
    scaled = {i: int(x * den) for i, x in support.items()}
    g = 0
    for x in scaled.values():
        g = gcd(g, abs(x))
    if g:
        scaled = {i: x // g for i, x in scaled.items()}
    lead = scaled[min(scaled)]
    if lead < 0:
        scaled = {i: -x for i, x in scaled.items()}
    return scaled


def insertion_tensor(label: int, direction: int) -> Tensor | None:
    """The one fundamental insertion at a corner leg: invariant in V_{label'} (x) V_1 (x) V_label."""
    target = label + direction
    if target < 0:
        return None
    return invariant_tensor((target, 1, label))


_INSERTION_KERNEL_CACHE: dict[tuple[int, int, int], np.ndarray | None] = {}


def insertion_kernel(label: int, direction: int, bridge: str = "metric") -> np.ndarray | None:
    """The four-index kernel of the corner multiplier, in the declared realization.

    Multiplying the two rim legs of a corner pair by the fundamental matrix element and
    closing the two fundamental indices with the curl is a single bilinear map on that
    pair: ``K4[m1, i1, m2, i2] = sum_{X,Y} ins[m1,X,i1] bridge[X,Y] ins[m2,Y,i2]``.
    Building it once per (label, direction, bridge) replaces the step-by-step contraction
    and is exactly the same operator, entry for entry.
    """
    key = (label, direction, 0 if bridge == "metric" else 1 if bridge == "identity" else 2)
    if key in _INSERTION_KERNEL_CACHE:
        return _INSERTION_KERNEL_CACHE[key]
    ins = insertion_tensor(label, direction)
    if ins is None:
        _INSERTION_KERNEL_CACHE[key] = None
        return None
    arr = np.asarray(ins[1], dtype=object)
    if bridge == "metric":
        eps = np.asarray(metric(1)[1], dtype=object)
    elif bridge == "inverse":
        eps = np.asarray(metric_inverse(1), dtype=object)
    elif bridge == "identity":
        eps = np.asarray([[F(1) if i == j else F(0) for j in range(2)] for i in range(2)], dtype=object)
    else:
        raise ValueError(bridge)
    stepped = np.tensordot(eps, arr, axes=([1], [1]))
    kernel = np.tensordot(arr, stepped, axes=([1], [0]))
    _INSERTION_KERNEL_CACHE[key] = kernel
    return kernel


def apply_insertion(
    alpha: Sequence[int],
    corner: int,
    direction: int,
    state: Tensor,
    pairing: str = "12|34",
    curl: str = "metric",
) -> Tensor | None:
    """Multiply the state by the corner-`corner` fundamental, in the declared realization.

    The two rim legs of the corner pair are each multiplied by the fundamental matrix
    element and the two fundamental indices are closed by the curl; the four-index kernel
    above is that whole operation, so this is one contraction with the same entries the
    step-by-step contraction produced.
    """
    label = alpha[corner]
    target = label + direction
    if target < 0:
        return None
    kernel = insertion_kernel(label, direction, curl)
    if kernel is None:
        return None
    legs, arr = state
    L1, L2 = CORNER_PAIRS[corner]
    pos = (legs.index(L1), legs.index(L2))
    out = np.tensordot(arr, kernel, axes=(pos, (1, 3)))
    out = np.moveaxis(out, (-2, -1), pos)
    new_legs = list(legs)
    new_legs[pos[0]] = f"N_{L1}"
    new_legs[pos[1]] = f"N_{L2}"
    current: Tensor = (tuple(new_legs), out)
    legs_out, arr_out = current
    legs_out = tuple(l[2:] if l.startswith("N_") else l for l in legs_out)
    current = (legs_out, arr_out)
    if len(legs_out) != 8:
        raise AssertionError(f"insertion produced {len(legs_out)} legs, expected 8 rim legs")
    return current


def _apply_insertion_stepwise(
    alpha: Sequence[int],
    corner: int,
    direction: int,
    state: Tensor,
    pairing: str = "12|34",
    curl: str = "metric",
) -> Tensor | None:
    """Multiply the state by the corner-`corner` fundamental, in the declared realization."""
    label = alpha[corner]
    target = label + direction
    if target < 0:
        return None
    ins = insertion_tensor(label, direction)
    if ins is None:
        return None
    legs_state, arr_state = state
    current: Tensor = (legs_state, arr_state)
    fundamentals = []
    for lin, L in enumerate(CORNER_PAIRS[corner]):
        name = f"M_{L}"
        new = f"N_{L}"
        t = ((new, name, f"O_{L}"), ins[1])
        current = contract(t, current, f"O_{L}", L, [[F(1) if i == j else F(0) for j in range(dim(label))] for i in range(dim(label))])
        fundamentals.append(name)
    if curl == "metric":
        bridge = [[as_fraction(x) for x in row] for row in metric(1)[1]]
    elif curl == "inverse":
        bridge = metric_inverse(1)
    elif curl == "identity":
        bridge = [[F(1) if i == j else F(0) for j in range(2)] for i in range(2)]
    else:
        raise ValueError(curl)
    current = self_contract(current, fundamentals[0], fundamentals[1], bridge)
    legs, arr = current
    legs = tuple(l[2:] if l.startswith("N_") else l for l in legs)
    current = (legs, arr)
    if len(legs) != 8:
        raise AssertionError(f"insertion produced {len(legs)} legs, expected 8 rim legs")
    return current


def hilbert_weights(alpha: Sequence[int], leg_dims: Sequence[int]) -> list[F]:
    """Declared unitary structure on each rim leg: <e_k,e_k> = 1/C(n,k)."""
    per_leg = []
    for n, size in zip(rim_labels(alpha), leg_dims):
        assert dim(n) == size
        per_leg.append([F(1, comb(n, k)) for k in range(size)])
    return per_leg


def corner_kernel(alpha: Sequence[int], corner: int, bridge: list[list[F]]) -> list[F]:
    """The corner-pair structure: A_{i,j} -> sum_{i',j'} bridge[i',j'] A_{i',j'}."""
    label = alpha[corner]
    return bridge


def pairing_matrix(
    alpha: Sequence[int],
    leg_dims: Sequence[int],
    structure: str = "unitary",
    pairing: str = "12|34",
) -> np.ndarray:
    """Diagonal weight matrix for the declared Hilbert pairing on the eight rim legs.

    ``unitary``: product of 1/C(n,k).  ``corner-epsilon``: the unitary weights times the
    epsilon contraction of the two rim legs of every corner pair.
    """
    weights = hilbert_weights(alpha, leg_dims)
    shape = tuple(leg_dims)
    out = np.zeros(shape, dtype=object)
    for idx in product(*[range(s) for s in shape]):
        w = F(1)
        for s, k in enumerate(idx):
            w *= weights[s][k]
        out[idx] = w
    if structure == "corner-epsilon":
        # contract the two legs of each corner pair with the metric, leaving one leg per pair
        eps = []
        for corner in range(4):
            label = alpha[corner]
            eps.append([[as_fraction(x) for x in row] for row in metric(label)[1]])
        pair_dims = [dim(alpha[c]) for c in range(4)]
        reduced = np.zeros(tuple(pair_dims), dtype=object)
        for idx in product(*[range(s) for s in shape]):
            val = out[idx]
            if val == 0:
                continue
            factor = F(1)
            keep = []
            for corner in range(4):
                i, j = idx[2 * corner], idx[2 * corner + 1]
                factor *= eps[corner][i][j]
                keep.append(0)
            if factor != 0:
                reduced[tuple(keep)] += val * factor
        return reduced
    return out


# ---------------------------------------------------------------------------
# matrices and linear algebra over Q
# ---------------------------------------------------------------------------
def rank_rational(rows: Sequence[Sequence[F]]) -> int:
    if not rows:
        return 0
    return len(_row_reduce([list(r) for r in rows], len(rows[0])))


def nullity(rows: Sequence[Sequence[F]]) -> int:
    if not rows:
        return 0
    return len(rows[0]) - rank_rational(rows)


def block_matrix(
    beta: Sequence[int],
    alpha: Sequence[int],
    corner: int,
    direction: int,
    pairing: str = "12|34",
    structure: str = "unitary",
    curl: str = "metric",
    leg_order: Sequence[str] = ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"),
    insert_corner: int | None = None,
) -> dict:
    """The declared compression block K: M^f(alpha) -> M^f(alpha +- e_corner)."""
    beta_labelings = fine_basis(beta, pairing)
    alpha_labelings = fine_basis(alpha, pairing)
    if not alpha_labelings:
        return {"defined": False, "reason": "empty source basis"}
    if not beta_labelings:
        return {"defined": False, "reason": "empty target basis"}
    beta_supports = [state_support(beta, lab, pairing) for lab in beta_labelings]
    beta_dims = beta_supports[0][0]
    ambient = int(np.prod(beta_dims))
    labels_beta = dict(zip(("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"), rim_labels(beta)))
    images: list[dict[int, F] | None] = []
    for entry in alpha_labelings:
        tensor = state_tensor(alpha, entry, pairing)
        image = apply_insertion(
            alpha,
            corner if insert_corner is None else insert_corner,
            direction,
            tensor,
            pairing,
            curl,
        )
        if image is None:
            images.append(None)
            continue
        try:
            support = flatten_support(image, leg_order, labels_beta)
        except (ValueError, IndexError):
            images.append(None)
            continue
        images.append(support if len(image[1].reshape(-1)) == ambient else None)
    weight = pairing_matrix(beta, beta_dims, structure, pairing)
    flat_weight = [weight[idx] for idx in product(*[range(s) for s in beta_dims])]
    # sparse supports: the flattened states are mostly zero, so each entry is a merge of
    # the two supports against the (dense but cheap) weights
    weight_support = {i: w for i, w in enumerate(flat_weight) if w != 0}
    matrix: list[list[F]] = []
    for _dims, support in beta_supports:
        row = []
        for image_support in images:
            if image_support is None:
                row.append(F(0))
                continue
            if len(image_support) < len(support):
                small, large = image_support, support
            else:
                small, large = support, image_support
            total = F(0)
            for i, v in small.items():
                w = weight_support.get(i)
                if w is None:
                    continue
                u = large.get(i)
                if u is None:
                    continue
                total += w * F(u) * F(v)
            row.append(total)
        matrix.append(row)
    mismatch = any(image is None for image in images)
    return {
        "defined": True,
        "source_sector": list(alpha),
        "target_sector": list(beta),
        "corner_index": corner,
        "insert_corner": corner if insert_corner is None else insert_corner,
        "direction": direction,
        "leg_order": list(leg_order),
        "dimension_mismatch": mismatch,
        "basis_source": [list(l) for l in alpha_labelings],
        "basis_target": [list(l) for l in beta_labelings],
        "matrix": [[str(x) for x in row] for row in matrix],
        "matrix_shape": [len(matrix), len(matrix[0]) if matrix else 0],
        "rank": rank_rational(matrix),
        "kernel_dimension": nullity(matrix),
        "nonzero_entries": sum(1 for row in matrix for x in row if x != 0),
        "entry_count": sum(len(row) for row in matrix),
        "is_zero": all(x == 0 for row in matrix for x in row),
    }


SIDE_OF = {1: (0, 1), 2: (1, 2), 3: (2, 3), 4: (3, 0)}
SIDE_INDEX_OF = {tuple(sorted(v)): k for k, v in SIDE_OF.items()}


def labelling_image(sigma: Sequence[int], labelling: Sequence[int]) -> tuple[int, int, int, int, int]:
    """Transport a fine labelling along a corner permutation.

    ``sigma`` maps the old corner index to the corner index that receives its label.
    Spoke values travel with their side; the centre channel r is untouched.
    """
    s = {1: labelling[0], 2: labelling[1], 3: labelling[2], 4: labelling[3]}
    new: dict[int, int] = {}
    for k, (i, j) in SIDE_OF.items():
        target = SIDE_INDEX_OF[tuple(sorted((sigma[i], sigma[j])))]
        new[target] = s[k]
    return (new[1], new[2], new[3], new[4], labelling[4])


def sector_image(sigma: Sequence[int], alpha: Sequence[int]) -> tuple[int, ...]:
    out = [0] * 4
    for i in range(4):
        out[sigma[i]] = alpha[i]
    return tuple(out)


def permutation_parity(p: Sequence[int]) -> int:
    seen = [False] * len(p)
    parity = 1
    for i in range(len(p)):
        if seen[i]:
            continue
        j, length = i, 0
        while not seen[j]:
            seen[j] = True
            j = p[j]
            length += 1
        if length % 2 == 0:
            parity = -parity
    return parity


# ---------------------------------------------------------------------------
# controls and checks
# ---------------------------------------------------------------------------
def hermeticity_check() -> dict:
    """The declared inner product must make the generators Hermitian."""
    worst = F(0)
    pairs = 0
    for n in range(0, 5):
        for a in range(dim(n)):
            for b in range(dim(n)):
                for _, gen in GENERATORS:
                    m = gen(n)
                    lhs = F(0)
                    rhs = F(0)
                    for i in range(dim(n)):
                        lhs += m[i][a] * F(1, comb(n, i)) * (F(1) if i == b else F(0))
                    # <J_+ e_a, e_b> vs <e_a, J_- e_b> style pairing for the transposed generator
                    mt = [[m[j][i] for j in range(dim(n))] for i in range(dim(n))]
                    for i in range(dim(n)):
                        lhs += 0
                    lhs = F(0)
                    for i in range(dim(n)):
                        lhs += m[i][a] * F(1, comb(n, i)) * F(1) * (1 if i == b else 0)
                    rhs = F(0)
                    for i in range(dim(n)):
                        rhs += F(1, comb(n, a)) * mt[i][b] * (1 if i == a else 0)
                    pairs += 1
                    worst = max(worst, abs(lhs - rhs))
    return {"pairs": pairs, "worst_residual": str(worst)}


def generator_hermeticity_residual(weights) -> F:
    """max |<J_+ e_a, e_b> - <e_a, J_- e_b>| plus the other generator pairs."""
    worst = F(0)
    for n in range(0, 5):
        jp = _jp(n)
        jm = _jm(n)
        for a in range(dim(n)):
            for b in range(dim(n)):
                lhs = jp[b][a] * weights(n, b) if jp[b][a] != 0 else F(0)
                rhs = jm[a][b] * weights(n, a) if jm[a][b] != 0 else F(0)
                worst = max(worst, abs(lhs - rhs))
                lhs2 = jm[b][a] * weights(n, b) if jm[b][a] != 0 else F(0)
                rhs2 = jp[a][b] * weights(n, a) if jp[a][b] != 0 else F(0)
                worst = max(worst, abs(lhs2 - rhs2))
    return worst


def unitary_weights(n: int, k: int) -> F:
    return F(1, comb(n, k))


def flat_weights(n: int, k: int) -> F:
    return F(1)


def corner_slice_content() -> dict:
    """The map's diagonal-slice derivation, realized locally at the corner pair.

    The corner pair carries the invariant cap in V_a (x) V_a; the multiplier inserts the
    fundamental at both legs and closes it with the curl.  Measure the image content in
    each neighbour a +- 1 by the norm of the projected image along the neighbour's cap.
    """
    rows = []
    for a in range(0, 4):
        cap = [[as_fraction(x) for x in row] for row in metric(a)[1]]
        # contract cap with the two insertions: (a') x (a') tensor
        for direction in (+1, -1):
            target = a + direction
            if target < 0:
                rows.append(
                    {
                        "corner_label": a,
                        "direction": direction,
                        "target_label": None,
                        "content_norm_squared": None,
                        "defined": False,
                    }
                )
                continue
            ins = insertion_tensor(a, direction)
            assert ins is not None
            ins_legs, ins_arr = ins
            # image[i',j'] = sum_{i,j,m,n} cap[i][j] ins[i',m,i] ins[j',n,j] curl[m][n]
            curl = [[as_fraction(x) for x in row] for row in metric(1)[1]]
            image = np.zeros((dim(target), dim(target)), dtype=object)
            for i in range(dim(a)):
                for j in range(dim(a)):
                    if cap[i][j] == 0:
                        continue
                    for ip in range(dim(target)):
                        for m in range(2):
                            v1 = as_fraction(ins_arr[ip][m][i])
                            if v1 == 0:
                                continue
                            for jp in range(dim(target)):
                                for n2 in range(2):
                                    v2 = as_fraction(ins_arr[jp][n2][j])
                                    if v2 == 0 or curl[m][n2] == 0:
                                        continue
                                    image[ip][jp] += cap[i][j] * v1 * v2 * curl[m][n2]
            # project on the neighbour cap and take the declared unitary norm
            proj = F(0)
            norm2 = F(0)
            target_cap = metric(target)[1]
            for ip in range(dim(target)):
                for jp in range(dim(target)):
                    if image[ip][jp] == 0:
                        continue
                    proj += image[ip][jp] * as_fraction(target_cap[ip][jp])
                    norm2 += (image[ip][jp]) ** 2 * unitary_weights(target, ip) * unitary_weights(target, jp)
            rows.append(
                {
                    "corner_label": a,
                    "direction": direction,
                    "target_label": target,
                    "cap_overlap": str(proj),
                    "content_norm_squared": str(norm2),
                    "defined": True,
                    "nonzero": norm2 != 0,
                }
            )
    return {
        "rows": rows,
        "defined_rows": sum(1 for r in rows if r["defined"]),
        "all_defined_neighbours_carry_content": all(r["nonzero"] for r in rows if r["defined"]),
        "note": (
            "local corner-pair realization of the slice derivation at lines 2287-2298; the "
            "map's full all-identity-slice statement also involves the rim structure and is "
            "not claimed here"
        ),
    }


# ---------------------------------------------------------------------------
# receipt assembly
# ---------------------------------------------------------------------------
def read_source_quotes() -> dict:
    raw = SOURCE_DOCUMENT.read_bytes()
    # hash the raw bytes: text-mode reads normalise CRLF on Windows, which would record a
    # digest of bytes that are not the file's
    text = raw.decode("utf-8")
    lines = text.splitlines()
    quotes = []
    for start, end, purpose in QUOTED_RANGES:
        snippet = "\n".join(lines[start - 1 : end])
        quotes.append(
            {
                "lines": [start, end],
                "purpose": purpose,
                "sha256_of_quoted_text": hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
                "text": snippet,
            }
        )
    def slice_lines(start: int, end: int) -> str:
        return "\n".join(lines[start - 1 : end])

    return {
        "document": str(SOURCE_DOCUMENT.relative_to(REPO.parent)),
        "document_sha256_at_read_time": hashlib.sha256(raw).hexdigest(),
        "document_sha256_convention": "sha256 of the file's raw bytes as read at run time",
        "line_count": len(lines),
        "quotes": quotes,
        "named": {
            "demand": slice_lines(2301, 2312),
            "support_action": slice_lines(2274, 2285),
        },
        "verification": "the quoted text is stored verbatim; each block carries its own sha256",
    }


def build_analysis(
    cutoff: int = SMALLEST_CUTOFF,
    frontier_dim: int | None = None,
    pairing: str = "12|34",
) -> dict:
    """The fine data and the adjacent blocks of one label-cutoff family.

    ``frontier_dim`` bounds the *declared* computation: a block whose source or target
    multiplicity exceeds it is recorded as skipped with its exact dimensions rather than
    computed.  Nothing is silently dropped.
    """
    sectors = [tuple(alpha) for alpha in product(range(cutoff + 1), repeat=4)]
    dimensions = {alpha: fine_dimension(alpha, pairing) for alpha in sectors}
    sector_rows = []
    for alpha in sectors:
        sector_rows.append(
            {
                "sector": list(alpha),
                "fine_dimension": dimensions[alpha],
                "fine_labelings": [list(l) for l in fine_basis(alpha, pairing)],
                "neighbours": {
                    "up": [
                        list(tuple(alpha[:c] + (alpha[c] + 1,) + alpha[c + 1 :]))
                        for c in range(4)
                    ],
                    "down": [
                        list(tuple(alpha[:c] + (alpha[c] - 1,) + alpha[c + 1 :]))
                        for c in range(4)
                        if alpha[c] - 1 >= 0
                    ],
                },
            }
        )
    blocks = []
    skipped = []
    for alpha in sectors:
        for corner in range(4):
            for direction in (+1, -1):
                if direction == -1 and alpha[corner] == 0:
                    continue
                target = tuple(
                    alpha[:corner] + (alpha[corner] + direction,) + alpha[corner + 1 :]
                )
                target_dim = dimensions.get(target)
                if target_dim is None:
                    target_dim = fine_dimension(target, pairing)
                source_dim = dimensions[alpha]
                if frontier_dim is not None and max(source_dim, target_dim) > frontier_dim:
                    skipped.append(
                        {
                            "source_sector": list(alpha),
                            "target_sector": list(target),
                            "corner_index": corner,
                            "direction": direction,
                            "source_dimension": source_dim,
                            "target_dimension": target_dim,
                            "cost_units": source_dim * target_dim,
                            "reason": (
                                "source or target multiplicity exceeds the declared frontier "
                                f"{frontier_dim}: max({source_dim}, {target_dim}) = "
                                f"{max(source_dim, target_dim)}"
                            ),
                        }
                    )
                    continue
                blocks.append(
                    block_matrix(target, alpha, corner, direction, pairing=pairing)
                )
    return {
        "cutoff": cutoff,
        "frontier_dim": frontier_dim,
        "pairing": pairing,
        "sectors": sector_rows,
        "blocks": blocks,
        "skipped_blocks": skipped,
    }


def summarise_blocks(blocks: Sequence[dict]) -> dict:
    defined = [b for b in blocks if b.get("defined")]
    return {
        "block_count": len(defined),
        "zero_blocks": [b for b in defined if b["is_zero"]],
        "nonzero_block_count": sum(1 for b in defined if not b["is_zero"]),
        "min_rank": min((b["rank"] for b in defined), default=None),
        "max_rank": max((b["rank"] for b in defined), default=None),
        "max_kernel_dimension": max((b["kernel_dimension"] for b in defined), default=None),
        "full_column_rank_blocks": [
            {
                "source_sector": b["source_sector"],
                "target_sector": b["target_sector"],
                "corner_index": b["corner_index"],
                "direction": b["direction"],
                "rank": b["rank"],
                "source_dimension": b["matrix_shape"][1],
            }
            for b in defined
            if b["matrix_shape"][1] and b["rank"] == b["matrix_shape"][1]
        ],
        "diagonal_blocks": [
            b
            for b in defined
            if len(set(b["source_sector"])) == 1 and b["source_sector"][0] == b["source_sector"][1]
        ],
    }


def trivial_spoke_report(blocks: Sequence[dict]) -> dict:
    out = []
    for b in blocks:
        if not b.get("defined"):
            continue
        alpha = b["source_sector"]
        if len(set(alpha)) != 1:
            continue
        labelings = [tuple(l) for l in b["basis_source"]]
        if (0, 0, 0, 0, 0) not in labelings:
            continue
        index = labelings.index((0, 0, 0, 0, 0))
        column = [row[index] for row in b["matrix"]]
        out.append(
            {
                "source_sector": alpha,
                "target_sector": b["target_sector"],
                "corner_index": b["corner_index"],
                "direction": b["direction"],
                "argument": "trivial-spoke vector (s1,s2,s3,s4,r)=(0,0,0,0,0)",
                "image_column_nonzero": any(F(x) != 0 for x in column),
                "image_column": column,
                "target_basis": [list(l) for l in b["basis_target"]],
            }
        )
    return {
        "rows": out,
        "diagonal_candidate_confirmed": bool(out)
        and all(r["image_column_nonzero"] for r in out),
    }


def vanishing_pattern(blocks: Sequence[dict], skipped: Sequence[dict]) -> dict:
    """Where the compression actually vanishes on the computed family.

    The map's demand (lines 2309-2310) is the *vanishing pattern*: which sector families can
    be exact.  A zero block is the object of interest, so it is reported individually, in a
    deterministic order, with its dimensions and with the reason it is zero when the
    construction supplies one (an insertion whose target sector does not match the shift, or
    an exact cancellation inside the declared realization).
    """
    defined = [b for b in blocks if b.get("defined")]
    zeros = [b for b in defined if b["is_zero"]]
    rows = []
    for b in zeros:
        rows.append(
            {
                "source_sector": b["source_sector"],
                "target_sector": b["target_sector"],
                "corner_index": b["corner_index"],
                "direction": b["direction"],
                "source_dimension": b["matrix_shape"][1],
                "target_dimension": b["matrix_shape"][0],
                "source_fine_dimension": fine_dimension(tuple(b["source_sector"])),
                "target_fine_dimension": fine_dimension(tuple(b["target_sector"])),
                "cost_units": b["matrix_shape"][0] * b["matrix_shape"][1],
                "sample_entries": b["matrix"][0][:6] if b["matrix"] else [],
            }
        )
    return {
        "blocks_computed": len(defined),
        "zero_block_count": len(zeros),
        "nonzero_block_count": len(defined) - len(zeros),
        "first_vanishing_block": rows[0] if rows else None,
        "zero_blocks": rows,
        "answer": (
            "no zero block was found inside the computed family"
            if not rows
            else f"{len(rows)} of {len(defined)} computed blocks vanish"
        ),
        "skipped_block_count": len(skipped),
        "skipped_blocks": list(skipped),
        "largest_computed_dimension_pair": _largest_dimension_pair(blocks),
        "largest_skipped_dimension_pair": _largest_dimension_pair(skipped),
        "skipped_cost_units_total": sum(s.get("cost_units", 0) for s in skipped),
    }


def extension_table(analysis: dict) -> dict:
    """Per-source-sector table of the extension: what was computed, what vanished, what was skipped."""
    blocks = analysis["blocks"]
    skipped = analysis["skipped_blocks"]
    by_source: dict[tuple, dict] = {}
    for row in analysis["sectors"]:
        alpha = tuple(row["sector"])
        by_source[alpha] = {
            "source_sector": list(alpha),
            "fine_dimension": row["fine_dimension"],
            "blocks_computed": [],
            "zero_blocks": [],
            "blocks_skipped": [],
        }
    for b in blocks:
        if not b.get("defined"):
            continue
        entry = by_source[tuple(b["source_sector"])]
        record = {
            "target_sector": b["target_sector"],
            "corner_index": b["corner_index"],
            "direction": b["direction"],
            "target_dimension": b["matrix_shape"][0],
            "shape": b["matrix_shape"],
            "rank": b["rank"],
            "kernel_dimension": b["kernel_dimension"],
            "is_zero": b["is_zero"],
        }
        entry["blocks_computed"].append(record)
        if b["is_zero"]:
            entry["zero_blocks"].append(record)
    for row in skipped:
        by_source[tuple(row["source_sector"])]["blocks_skipped"].append(
            {
                "target_sector": row["target_sector"],
                "corner_index": row["corner_index"],
                "direction": row["direction"],
                "source_dimension": row["source_dimension"],
                "target_dimension": row["target_dimension"],
                "cost_units": row["cost_units"],
                "reason": row["reason"],
            }
        )
    rows = [by_source[key] for key in sorted(by_source)]
    # a source sector with a three in it cannot be lowered at the corner carrying it, so
    # "complete" means every corner-direction pair that exists for that source was computed
    for row in rows:
        alpha = tuple(row["source_sector"])
        expected = sum(1 for c in range(4) for d in (+1, -1) if d == 1 or alpha[c] > 0)
        row["expected_shift_count"] = expected
        row["complete"] = (
            len(row["blocks_computed"]) + len(row["blocks_skipped"]) == expected
        )
    zero_sources = [row["source_sector"] for row in rows if row["zero_blocks"]]
    return {
        "source_sector_count": len(rows),
        "sources_with_a_zero_block": zero_sources,
        "rows": rows,
    }


def _largest_dimension_pair(rows: Sequence[dict]) -> list[int] | None:
    best = None
    for row in rows:
        pair = (
            [row["source_dimension"], row["target_dimension"]]
            if "source_dimension" in row
            else [row["matrix_shape"][1], row["matrix_shape"][0]]
        )
        if best is None or max(pair) > max(best):
            best = pair
    return best


def corner_spectator_reading(blocks: Sequence[dict]) -> dict:
    """Does the rank of a compression depend on which corner is shifted?

    Groups blocks by (source sector, direction) over the four corner indices and reports
    whether the ranks agree.  The count is a measured reading; it is not evidence that the
    corner index is irrelevant to the matrix, only that it is irrelevant to its rank.
    """
    groups: dict[tuple, list[dict]] = {}
    for b in blocks:
        if not b.get("defined"):
            continue
        groups.setdefault((tuple(b["source_sector"]), b["direction"]), []).append(b)
    rows = []
    for (source, direction), group in groups.items():
        by_corner = {b["corner_index"]: b["rank"] for b in group}
        rows.append(
            {
                "source_sector": list(source),
                "direction": direction,
                "corners": sorted(by_corner),
                "ranks": [by_corner[c] for c in sorted(by_corner)],
                "rank_independent_of_corner": len(set(by_corner.values())) == 1,
            }
        )
    complete = [r for r in rows if len(r["corners"]) == 4]
    disagreements = [r for r in complete if not r["rank_independent_of_corner"]]
    by_direction = {}
    for direction in (+1, -1):
        group = [r for r in complete if r["direction"] == direction]
        by_direction[str(direction)] = {
            "complete_groups": len(group),
            "equal_rank_groups": sum(1 for r in group if r["rank_independent_of_corner"]),
            "disagreeing_groups": sum(1 for r in group if not r["rank_independent_of_corner"]),
        }
    used = [b for b in blocks if b.get("defined")]
    disagreeing_blocks = [
        b
        for b in used
        if (tuple(b["source_sector"]), b["corner_index"], b["direction"])
        in {
            (tuple(r["source_sector"]), c, r["direction"])
            for r in disagreements
            for c in r["corners"]
        }
    ]
    return {
        "groups": len(rows),
        "significant_blocks": len(used),
        "full_rank_blocks": sum(
            1 for b in used if b["rank"] == min(b["matrix_shape"]) and b["matrix_shape"][1]
        ),
        "disagreeing_group_blocks": len(disagreeing_blocks),
        "disagreeing_group_blocks_full_rank": sum(
            1
            for b in disagreeing_blocks
            if b["rank"] == min(b["matrix_shape"]) and b["matrix_shape"][1]
        ),
        "groups_with_all_four_corners": len(complete),
        "groups_with_equal_ranks": sum(1 for r in rows if r["rank_independent_of_corner"]),
        "complete_groups_with_equal_ranks": sum(
            1 for r in complete if r["rank_independent_of_corner"]
        ),
        "complete_groups_disagreeing": len(disagreements),
        "first_disagreeing_group": disagreements[0] if disagreements else None,
        "all_groups_equal": bool(rows) and all(r["rank_independent_of_corner"] for r in rows),
        "by_direction": by_direction,
        "reading_caveat": (
            "each corner sends the source sector to a different target sector, so a rank "
            "comparison across corners compares different sector pairs; a disagreement is a "
            "statement about those pairs, not proof that the corner index enters the operator"
        ),
        "rows": rows,
    }


def orthogonality_aggregates(rows: Sequence[dict]) -> dict:
    """Counts for the Gram readings, so every reported aggregate is readable from the receipt."""
    return {
        "blocks_with_gram": len(rows),
        "orthogonal_gram_blocks": sum(1 for g in rows if g["gram_offdiagonal_all_zero"]),
        "rank_deficient_gram_blocks": sum(
            1 for g in rows if g["gram_rank"] < len(g["gram_diagonal"])
        ),
        "note": "gram rows cover the first sixteen defined blocks of the computed family",
    }


def pairing_columns() -> dict:
    """The declared pairing against the map's own alternative, measured side by side.

    For each pairing: the count of the 24 corner permutations that preserve M^f over the
    label-at-most-two sectors, the count for which the fine labelling set transports across
    the cutoff-1 blocks, the size of that transport subgroup, and the dihedral rank
    covariance.  This separates a property of the object from a property of the declaration.
    """
    columns = []
    for pairing in ("12|34", "14|23"):
        analysis = build_analysis(cutoff=SMALLEST_CUTOFF, pairing=pairing)
        blocks = analysis["blocks"]
        invariance = mf_permutation_invariance(cutoff=2, pairing=pairing)
        covariance = relabelling_check(blocks)
        transport = [
            tuple(r["permutation"])
            for r in covariance["rows"]
            if r["applicable"] and r["label_sets_transport"] == r["blocks_tested"]
        ]
        other = "14|23" if pairing == "12|34" else "12|34"
        differing_sectors = 0
        differing_labelings = 0
        for row in analysis["sectors"]:
            alpha = tuple(row["sector"])
            here = {tuple(l) for l in fine_basis(alpha, pairing)}
            there = {tuple(l) for l in fine_basis(alpha, other)}
            if here != there:
                differing_sectors += 1
                differing_labelings += len(here ^ there)
        columns.append(
            {
                "pairing": pairing,
                "centre_resolution": (
                    "r in fuse(s1,s2) & fuse(s3,s4)"
                    if pairing == "12|34"
                    else "r in fuse(s1,s4) & fuse(s2,s3)"
                ),
                "sector_count": len(analysis["sectors"]),
                "sectors_with_full_span": sum(
                    1 for r in analysis["sectors"] if r["fine_dimension"] > 0
                ),
                "anchor_values_match_map": all(
                    fine_dimension(sector, pairing) == value for sector, value in ANCHOR_TABLE
                ),
                "mf_invariant_permutations": sum(
                    1 for r in invariance["rows"] if r["invariant"]
                ),
                "mf_permutations_tested": invariance["permutations"],
                "mf_sectors_tested": invariance["sectors_checked"],
                "label_set_transporting_permutations": len(transport),
                "label_set_transport_subgroup": [list(p) for p in transport],
                "dihedral_rank_covariant_permutations": covariance["dihedral_rank_covariant"],
                "dihedral_permutations": covariance["dihedral_permutations"],
                "blocks_tested": covariance["rows"][0]["blocks_tested"] if covariance["rows"] else 0,
                "labelings_differing_from_other_pairing": differing_labelings,
                "sectors_with_different_labelling_sets": differing_sectors,
                "other_pairing": other,
            }
        )
    for column in columns:
        column["full_column_rank_blocks"] = sum(
            1
            for b in build_analysis(cutoff=SMALLEST_CUTOFF, pairing=column["pairing"])["blocks"]
            if b.get("defined") and b["matrix_shape"][1] and b["rank"] == b["matrix_shape"][1]
        )
    declared = columns[0]
    alternative = columns[1]
    return {
        "columns": columns,
        "mf_invariance_same_under_both_pairings": (
            declared["mf_invariant_permutations"] == alternative["mf_invariant_permutations"]
            and declared["mf_sectors_tested"] == alternative["mf_sectors_tested"]
        ),
        "transport_same_under_both_pairings": (
            declared["label_set_transporting_permutations"]
            == alternative["label_set_transporting_permutations"]
        ),
        "reading": (
            "M^f invariance is measured over the same sector domain (81 sectors, labels at most "
            "two) under both pairings, and the labelling transport over the same block set (the "
            "96 cutoff-1 blocks).  No mechanism is asserted for the transport subgroup: the "
            "measured subgroup is reported and the two pairings are compared field by field."
        ),
    }


def is_dihedral(sigma: Sequence[int]) -> bool:
    """True when the permutation maps the four rim sides to rim sides (the 8 symmetries)."""
    sides = {tuple(sorted(v)) for v in SIDE_OF.values()}
    image = {tuple(sorted((sigma[i], sigma[j]))) for (i, j) in SIDE_OF.values()}
    return len(image) == 4 and image == sides


def relabelling_check(blocks: Sequence[dict]) -> dict:
    """Square symmetries: how the computed blocks behave under corner permutations.

    Three separate readings, because they are not the same question:
      * rank covariance: rank(K) must agree with the transported partner's rank for every
        block (basis-independent, so this can be checked even when the transported labelings
        do not exist in the partner basis);
      * exact entry covariance: only meaningful when the transported fine labelings form the
        partner's basis set, which happens only for the permutations that preserve the
        declared (s1,s2)|(s3,s4) pairing structure;
      * applicability: the sixteen non-dihedral permutations map a rim side to a diagonal
        corner pair, so they cannot be tested on K at all.
    """
    from itertools import permutations

    by_key = {}
    for b in blocks:
        if not b.get("defined"):
            continue
        by_key[(tuple(b["source_sector"]), b["corner_index"], b["direction"])] = b
    results = []
    for sigma in permutations(range(4)):
        row = {
            "permutation": list(sigma),
            "parity": permutation_parity(sigma),
            "applicable": is_dihedral(sigma),
        }
        if not is_dihedral(sigma):
            row["reason"] = (
                "maps a rim side to a diagonal corner pair; the fine labelings carry spoke "
                "values on sides and have no image, so K cannot be transported"
            )
            results.append(row)
            continue
        rank_same = 0
        label_sets_match = 0
        exact = 0
        tested = 0
        missing = 0
        for (alpha, corner, direction), b in by_key.items():
            other = by_key.get((sector_image(sigma, alpha), sigma[corner], direction))
            if other is None:
                missing += 1
                continue
            tested += 1
            if b["rank"] == other["rank"]:
                rank_same += 1
            transported = {labelling_image(sigma, lab) for lab in map(tuple, b["basis_source"])}
            if transported == set(map(tuple, other["basis_source"])):
                label_sets_match += 1
                if _matrices_agree_after_relabelling(b, other, sigma):
                    exact += 1
        row.update(
            {
                "blocks_tested": tested,
                "blocks_missing_partner": missing,
                "rank_agrees": rank_same,
                "rank_covariant": tested > 0 and rank_same == tested,
                "label_sets_transport": label_sets_match,
                "exact_entry_agreement": exact,
            }
        )
        results.append(row)
    dihedral = [r for r in results if r["applicable"]]
    # firing control for the rank reading itself: compare each block with the
    # same-sector opposite-direction block, i.e. with a partner that is not the
    # transported one.  If those ranks never disagreed, the rank covariance above
    # would be a statement about a constant and not about the computed blocks.
    control_pairs = 0
    control_mismatches = 0
    for (alpha, corner, direction), b in by_key.items():
        other = by_key.get((alpha, corner, -direction))
        if other is None:
            continue
        control_pairs += 1
        if other["rank"] != b["rank"]:
            control_mismatches += 1
    return {
        "permutations_tested": len(results),
        "dihedral_permutations": len(dihedral),
        "non_dihedral_permutations": len(results) - len(dihedral),
        "dihedral_rank_covariant": sum(1 for r in dihedral if r["rank_covariant"]),
        "all_dihedral_rank_covariant": all(r["rank_covariant"] for r in dihedral),
        "dihedral_exact_entry_covariant": sum(
            1 for r in dihedral if r["exact_entry_agreement"] == r["blocks_tested"]
        ),
        "dihedral_label_sets_transporting": sum(
            1 for r in dihedral if r["label_sets_transport"] == r["blocks_tested"]
        ),
        "rank_control_pairs": control_pairs,
        "rank_control_wrong_partner_mismatches": control_mismatches,
        "rank_control_fires": control_mismatches > 0,
        "claim_under_test": (
            "the map says the square's rotations and reflections permute the four labels while "
            "leaving M^f invariant (lines 2335-2336); measured separately: M^f invariance over "
            "all 24 permutations, rank covariance of K over the 8 dihedral ones, and exact "
            "entry covariance only where the declared labelling convention transports"
        ),
        "rows": results,
    }


def mf_permutation_invariance(cutoff: int = 2, pairing: str = "12|34") -> dict:
    """M^f must be invariant under every permutation of the four corner labels.

    Measured over every sector with all labels at most `cutoff` (the map's own claim at
    lines 2335-2336), not only over the cutoff-1 family.
    """
    from itertools import permutations

    sectors = [tuple(a) for a in product(range(cutoff + 1), repeat=4)]
    rows = []
    for sigma in permutations(range(4)):
        violations = []
        for alpha in sectors:
            other = sector_image(sigma, alpha)
            if fine_dimension(other, pairing) != fine_dimension(alpha, pairing):
                violations.append({"sector": list(alpha), "image": list(other)})
        rows.append({"permutation": list(sigma), "violations": violations, "invariant": not violations})
    return {
        "cutoff": cutoff,
        "pairing": pairing,
        "sectors_checked": len(sectors),
        "permutations": len(rows),
        "all_invariant": all(r["invariant"] for r in rows),
        "violating_permutations": [r["permutation"] for r in rows if not r["invariant"]],
        "rows": rows,
    }


def _matrices_agree_after_relabelling(b: dict, other: dict, sigma: Sequence[int]) -> bool:
    """Compare K_{alpha->beta} with the transported partner block."""
    if b["matrix_shape"] != other["matrix_shape"]:
        return False
    rows = [tuple(l) for l in b["basis_source"]]
    trows = [tuple(l) for l in b["basis_target"]]
    src = {labelling_image(sigma, lab): i for i, lab in enumerate(tuple(l) for l in other["basis_source"])}
    tgt = {labelling_image(sigma, lab): i for i, lab in enumerate(tuple(l) for l in other["basis_target"])}
    if len(src) != len(other["basis_source"]) or len(tgt) != len(other["basis_target"]):
        return False
    if any(lab not in src for lab in rows) or any(lab not in tgt for lab in trows):
        return False
    for i, lab in enumerate(rows):
        for j, tlab in enumerate(trows):
            # matrix rows index the target basis, columns the source basis
            if F(b["matrix"][j][i]) != F(other["matrix"][tgt[tlab]][src[lab]]):
                return False
    return True


def pairing_variant_check(blocks: Sequence[dict]) -> dict:
    """(UFA106) says the value is independent of the centre pairing choice."""
    out = []
    for b in blocks[:12]:
        if not b.get("defined"):
            continue
        alt = block_matrix(
            b["target_sector"],
            b["source_sector"],
            b["corner_index"],
            b["direction"],
            pairing="14|23",
        )
        out.append(
            {
                "source_sector": b["source_sector"],
                "target_sector": b["target_sector"],
                "corner_index": b["corner_index"],
                "direction": b["direction"],
                "rank_declared_pairing": b["rank"],
                "rank_alternative_pairing": alt.get("rank"),
                "same_rank": b["rank"] == alt.get("rank"),
                "same_zero_status": b["is_zero"] == alt.get("is_zero"),
            }
        )
    return {
        "rows": out,
        "all_ranks_match": all(r["same_rank"] and r["same_zero_status"] for r in out),
    }


def curl_variant_check(blocks: Sequence[dict]) -> dict:
    """The map says the corner value is unchanged by the orientation sign."""
    out = []
    for b in blocks[:12]:
        if not b.get("defined"):
            continue
        alt = block_matrix(
            b["target_sector"],
            b["source_sector"],
            b["corner_index"],
            b["direction"],
            curl="inverse",
        )
        same = b["matrix"] == alt["matrix"]
        negated = all(
            F(x) == -F(y) for row_b, row_a in zip(b["matrix"], alt["matrix"]) for x, y in zip(row_b, row_a)
        )
        out.append(
            {
                "source_sector": b["source_sector"],
                "corner_index": b["corner_index"],
                "direction": b["direction"],
                "identical": same,
                "negated": negated,
                "same_rank": b["rank"] == alt["rank"],
            }
        )
    return {
        "rows": out,
        "all_same_or_negated": all(r["identical"] or r["negated"] for r in out),
    }


def firing_controls() -> dict:
    """Controls that must fire: each deliberately mutates one declared choice."""
    alpha = (1, 1, 1, 1)
    target = (2, 1, 1, 1)
    good = block_matrix(target, alpha, 0, +1)
    no_curl = block_matrix(target, alpha, 0, +1, curl="identity")
    leg_order = block_matrix(target, alpha, 0, +1, leg_order=("L2", "L1", "L3", "L4", "L5", "L6", "L7", "L8"))
    alt_pairing = block_matrix(target, alpha, 0, +1, pairing="14|23")
    # a shift at corner b cannot be compared with the corner-a target: leg dimensions differ
    wrong_pair = block_matrix((1, 1, 1, 1), alpha, 0, +1, insert_corner=1)
    return {
        "declared_rank": good["rank"],
        "declared_shape": good["matrix_shape"],
        "declared_zero": good["is_zero"],
        "no_curl_rank": no_curl["rank"],
        "no_curl_entries_differ": no_curl["matrix"] != good["matrix"],
        "leg_order_rank": leg_order["rank"],
        "leg_order_entries_differ": leg_order["matrix"] != good["matrix"],
        "leg_order_shape": leg_order["matrix_shape"],
        "alt_pairing_rank": alt_pairing["rank"],
        "alt_pairing_entries_differ": alt_pairing["matrix"] != good["matrix"],
        "wrong_pair_target_shape": wrong_pair["matrix_shape"],
        "wrong_pair_dimension_mismatch": wrong_pair["matrix_shape"] != good["matrix_shape"],
        "expected": (
            "each mutation must change at least one measured reading; a mutation that leaves "
            "the declared block untouched would show the block does not depend on that choice"
        ),
    }


# ---------------------------------------------------------------------------
# rank witnesses: an explicit min(shape) minor, triangular in the declared entries
#
# Full-rank saturation (rank = min(shape) for every computed block) is the structural fact
# the vanishing-pattern reading rests on, so each computed block is asked for the minor that
# exhibits it.  The declared search has three arms, in this order:
#   * declared_order: the block's canonical elimination minor (pivot rows and columns of the
#     exact elimination in the stored basis order), rows and columns taken in the declared
#     basis order; a triangular form with nonzero diagonal there is a witness whose
#     determinant is the product of its diagonal entries;
#   * search_greedy: a constructive search over the block's whole support pattern, placing
#     the minor's rows from the last position backwards, so each placed row must vanish on
#     the columns already placed at later positions; two declared orderings;
#   * search_depth_first: the same placement rule searched exhaustively (with memoized
#     failure states) up to a declared node budget, for minor sizes at most
#     WITNESS_EXACT_MAX_K.  When that search exhausts, the negative is exact inside the
#     declared entries: no triangular min(shape) minor exists there, so the block's
#     saturation comes from arithmetic rather than from its support pattern.
# A found witness is verified independently of the search that produced it: the diagonal
# entries are nonzero, the forbidden triangle is zero, and the sample minors are re-ranked
# by exact elimination.
# ---------------------------------------------------------------------------
WITNESS_EXACT_MAX_K = 12  # above this size the exhaustive arm is not run (node cost)
WITNESS_NODE_BUDGET = 4000  # declared cap on the exhaustive arm's states per block


def _row_supports(matrix: Sequence[Sequence[F]]) -> tuple[list[list[int]], list[int], list[int]]:
    """Nonzero columns per row, its column bitmask, and the nonzero-row count per column."""
    nz: list[list[int]] = []
    masks: list[int] = []
    col_counts: list[int] = [0] * (len(matrix[0]) if matrix else 0)
    for row in matrix:
        cols = [j for j, x in enumerate(row) if x != 0]
        mask = 0
        for j in cols:
            mask |= 1 << j
            col_counts[j] += 1
        nz.append(cols)
        masks.append(mask)
    return nz, masks, col_counts


def _elimination_minor(
    matrix: Sequence[Sequence[F]],
) -> tuple[list[int], list[int]]:
    """The pivot rows and columns of the exact elimination in the declared basis order."""
    rows = [list(r) for r in matrix]
    m = len(rows)
    n = len(rows[0]) if m else 0
    orig = list(range(m))
    pivot_rows: list[int] = []
    pivot_cols: list[int] = []
    r = 0
    for c in range(n):
        p = next((i for i in range(r, m) if rows[i][c] != 0), None)
        if p is None:
            continue
        rows[r], rows[p] = rows[p], rows[r]
        orig[r], orig[p] = orig[p], orig[r]
        inv = rows[r][c]
        for i in range(r + 1, m):
            if rows[i][c] != 0:
                factor = rows[i][c] / inv
                src, dst = rows[r], rows[i]
                for j in range(c, n):
                    if src[j] != 0:
                        dst[j] -= factor * src[j]
        pivot_rows.append(orig[r])
        pivot_cols.append(c)
        r += 1
        if r == m:
            break
    return pivot_rows, pivot_cols


def _minor(matrix: Sequence[Sequence[F]], row_order: Sequence[int], col_order: Sequence[int]) -> list[list[F]]:
    return [[matrix[i][j] for j in col_order] for i in row_order]


def _triangle_form(square_matrix: Sequence[Sequence[F]]) -> str | None:
    """'upper'/'lower' when the square matrix is triangular with a nonzero diagonal."""
    k = len(square_matrix)
    if any(square_matrix[i][i] == 0 for i in range(k)):
        return None
    if all(square_matrix[i][j] == 0 for i in range(k) for j in range(i)):
        return "upper"
    if all(square_matrix[i][j] == 0 for i in range(k) for j in range(i + 1, k)):
        return "lower"
    return None


def _verify_witness(
    matrix: Sequence[Sequence[F]],
    row_order: Sequence[int],
    col_order: Sequence[int],
    form: str,
    rank_check: bool = False,
) -> dict:
    """Check a claimed witness from the stored entries, independently of the search."""
    sub = _minor(matrix, row_order, col_order)
    k = len(sub)
    diagonal = [sub[i][i] for i in range(k)]
    if form == "upper":
        forbidden = [(i, j) for i in range(k) for j in range(i)]
    else:
        forbidden = [(i, j) for i in range(k) for j in range(i + 1, k)]
    out = {
        "minor_size": k,
        "diagonal_nonzero": all(x != 0 for x in diagonal),
        "forbidden_entries_zero": all(sub[i][j] == 0 for i, j in forbidden),
        "entries_in_forbidden_triangle": len(forbidden),
        "diagonal_entries_nonzero_count": sum(1 for x in diagonal if x != 0),
        "form": form,
        "determinant_is_a_product_of_nonzero_rationals": all(x != 0 for x in diagonal),
    }
    if rank_check:
        out["rank_by_elimination"] = rank_rational(sub)
        out["rank_equals_minor_size"] = rank_rational(sub) == k
    return out


def _staircase_greedy(
    matrix: Sequence[Sequence[F]], k: int, rule: str
) -> list[tuple[int, int]] | None:
    """Constructive declared search: place the minor's rows from the last position backwards.

    A row placed at position j must vanish on every column already placed at a position
    greater than j, and contributes its own column.  Two declared selection rules:
    ``fewest`` takes the admissible row with the fewest nonzeros outside the placed columns
    and, within it, the admissible column of fewest nonzeros overall; ``stored`` takes the
    first admissible row and its first admissible column, both in the declared basis order.
    """
    m = len(matrix)
    nz, masks, col_counts = _row_supports(matrix)
    used_rows = 0
    placed_cols = 0
    placed: list[tuple[int, int]] = []
    for _ in range(k):
        choice = None
        for r in range(m):
            if used_rows >> r & 1:
                continue
            if masks[r] & placed_cols:
                continue
            candidates = [c for c in nz[r] if not (placed_cols >> c & 1)]
            if not candidates:
                continue
            if rule == "fewest":
                keep = len(candidates)
                c = min(candidates, key=lambda j: (col_counts[j], j))
                key = (keep, r)
            else:
                c = candidates[0]
                key = (r,)
            if choice is None or key < choice[0]:
                choice = (key, r, c)
        if choice is None:
            return None
        _, r, c = choice
        used_rows |= 1 << r
        placed_cols |= 1 << c
        placed.append((r, c))
    return list(reversed(placed))


def _staircase_depth_first(
    matrix: Sequence[Sequence[F]], k: int, node_budget: int
) -> tuple[list[tuple[int, int]] | None, int, bool]:
    """Exhaustive (up to the node budget) search for the same backward placement.

    Returns (witness in position order — first position first | None, states visited,
    exhausted).  Failure states are memoized on (placed rows, placed columns), so an
    exhausted search is a proof that no triangular min(shape) minor exists in the declared
    entries.
    """
    m = len(matrix)
    nz, masks, _ = _row_supports(matrix)
    order = sorted(range(m), key=lambda r: (len(nz[r]), r))
    failed: set[tuple[int, int]] = set()
    nodes = 0
    exhausted = True

    def step(depth: int, used_rows: int, placed_cols: int) -> list[tuple[int, int]] | None:
        nonlocal nodes, exhausted
        if nodes >= node_budget:
            exhausted = False
            return None
        nodes += 1
        if depth == k:
            return []
        key = (used_rows, placed_cols)
        if key in failed:
            return None
        for r in order:
            if used_rows >> r & 1:
                continue
            if masks[r] & placed_cols:
                continue
            for c in nz[r]:
                if placed_cols >> c & 1:
                    continue
                got = step(depth + 1, used_rows | (1 << r), placed_cols | (1 << c))
                if got is not None:
                    return [(r, c)] + got
                if not exhausted:
                    return None
        failed.add(key)
        return None

    found = step(0, 0, 0)
    return (None if found is None else list(reversed(found))), nodes, exhausted


def minor_witness(matrix: Sequence[Sequence[F]]) -> dict:
    """Search one block for a min(shape)-sized minor triangular with a nonzero diagonal."""
    m = len(matrix)
    n = len(matrix[0]) if m else 0
    k = min(m, n)
    if k == 0:
        return {
            "minor_size": 0,
            "canonical_minor_is_invertible_rank_full": False,
            "canonical_minor_rows": [],
            "canonical_minor_cols": [],
            "found": False,
            "arm": None,
            "form": None,
            "order": None,
            "search_status": "empty_block",
            "nodes": 0,
            "certificate_verification": None,
            "certificate_digest": None,
        }
    pivot_rows, pivot_cols = _elimination_minor(matrix)
    canonical_invertible = len(pivot_rows) == k
    base = {
        "minor_size": k,
        "canonical_minor_is_invertible_rank_full": canonical_invertible,
        "canonical_minor_rows": sorted(pivot_rows),
        "canonical_minor_cols": sorted(pivot_cols),
    }
    candidates: list[tuple[str, str, list[int], list[int]]] = []
    # the canonical pivot minor is a witness only when it really has k pivots: for a block
    # that is not saturated the pivot minor is smaller, and an empty square matrix must not
    # be read as a triangular one
    if canonical_invertible:
        rows = sorted(pivot_rows)
        cols = sorted(pivot_cols)
        form = _triangle_form(_minor(matrix, rows, cols))
        if form is not None:
            candidates.append(("declared_order", form, rows, cols))
    for rule in ("fewest", "stored"):
        placed = _staircase_greedy(matrix, k, rule)
        if placed is not None:
            candidates.append(
                (
                    f"search_greedy_{rule}",
                    "lower",
                    [r for r, _ in placed],
                    [c for _, c in placed],
                )
            )
    search_status = "not_needed"
    nodes = 0
    if not candidates:
        if k <= WITNESS_EXACT_MAX_K:
            found, nodes, exhausted = _staircase_depth_first(matrix, k, WITNESS_NODE_BUDGET)
            if found is not None:
                candidates.append(
                    (
                        "search_depth_first",
                        "lower",
                        [r for r, _ in found],
                        [c for _, c in found],
                    )
                )
                search_status = "found_by_depth_first"
            else:
                search_status = "exhausted" if exhausted else "budget_limited"
        else:
            search_status = "above_exact_search_size"
    for arm, form, rows, cols in candidates:
        if len(rows) != k or len(cols) != k or len(set(rows)) != k or len(set(cols)) != k:
            continue
        verification = _verify_witness(matrix, rows, cols, form)
        if not (verification["diagonal_nonzero"] and verification["forbidden_entries_zero"]):
            continue
        return {
            **base,
            "found": True,
            "arm": arm,
            "form": form,
            "order": [rows, cols],
            "search_status": search_status,
            "nodes": nodes,
            "certificate_verification": verification,
            "certificate_digest": _certificate_digest(rows, cols, form),
        }
    return {
        **base,
        "found": False,
        "arm": None,
        "form": None,
        "order": None,
        "search_status": (
            "certificate_failed_verification" if candidates else search_status
        ),
        "nodes": nodes,
        "certificate_verification": None,
        "certificate_digest": None,
    }


def _certificate_digest(rows: Sequence[int], cols: Sequence[int], form: str) -> str:
    payload = {"rows": list(rows), "cols": list(cols), "form": form}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def witness_controls(blocks: Sequence[dict]) -> dict:
    """Controls for the witness reading, selected by rule from the measured family.

    The witnessed block is the first block whose search returns a certificate and the
    negative block is the first whose search exhausts without one, so both follow the
    measurement instead of naming a block that may change with the declared model.
    """
    defined = [b for b in blocks if b.get("defined")]
    witnessed = None
    negative = None
    for b in defined:
        matrix = [[F(x) for x in row] for row in b["matrix"]]
        w = minor_witness(matrix)
        # the tamper controls exchange two certificate rows, so the control block must have a
        # certificate of size at least two
        if witnessed is None and w["found"] and w["minor_size"] >= 2:
            witnessed = (b, matrix, w)
        if negative is None and not w["found"] and w["search_status"] == "exhausted":
            negative = (b, w)
        if witnessed is not None and negative is not None:
            break
    out: dict = {
        "witnessed_block": None,
        "negative_block": None,
        "expected": (
            "a certificate must verify against the stored entries; zeroing a diagonal entry, "
            "exchanging two certificate rows and exchanging two certificate columns must each "
            "break it; and a block whose exhaustive search finds nothing must report no witness"
        ),
    }
    if witnessed is not None:
        b, matrix, w = witnessed
        rows, cols = w["order"]
        verification = _verify_witness(matrix, rows, cols, w["form"], rank_check=True)
        zeroed = [list(r) for r in matrix]
        zeroed[rows[0]][cols[0]] = F(0)
        zeroed_check = _verify_witness(zeroed, rows, cols, w["form"])
        swapped_rows = list(rows)
        swapped_cols = list(cols)
        if len(rows) > 1:
            swapped_rows[0], swapped_rows[1] = swapped_rows[1], swapped_rows[0]
            swapped_cols[0], swapped_cols[1] = swapped_cols[1], swapped_cols[0]
        row_check = _verify_witness(matrix, swapped_rows, cols, w["form"])
        col_check = _verify_witness(matrix, rows, swapped_cols, w["form"])

        def broken(v: dict) -> bool:
            return not (v["diagonal_nonzero"] and v["forbidden_entries_zero"])

        out["witnessed_block"] = {
            "source_sector": b["source_sector"],
            "target_sector": b["target_sector"],
            "corner_index": b["corner_index"],
            "direction": b["direction"],
            "shape": b["matrix_shape"],
            "arm": w["arm"],
            "form": w["form"],
            "certificate_digest": w["certificate_digest"],
            "verification": verification,
            "intact_certificate_verifies": not broken(verification),
            "zeroed_diagonal_breaks_it": broken(zeroed_check),
            "swapped_rows_break_it": broken(row_check),
            "swapped_columns_break_it": broken(col_check),
        }
    if negative is not None:
        b, w = negative
        out["negative_block"] = {
            "source_sector": b["source_sector"],
            "target_sector": b["target_sector"],
            "corner_index": b["corner_index"],
            "direction": b["direction"],
            "shape": b["matrix_shape"],
            "rank": b["rank"],
            "minor_size": w["minor_size"],
            "nodes": w["nodes"],
            "search_status": w["search_status"],
            "canonical_minor_is_invertible_rank_full": w[
                "canonical_minor_is_invertible_rank_full"
            ],
            "reading": (
                "the canonical pivot minor is an invertible min(shape) minor in this block (it "
                "is saturated and the elimination has min(shape) pivots), but no triangular one "
                "exists in its entries: here the saturation is arithmetic rather than a "
                "property of the support pattern"
            ),
        }
    # a support pattern that cannot carry a staircase of size two at all
    dense = [[F(1), F(1)], [F(1), F(1)]]
    dense_search = minor_witness(dense)
    out["dense_2x2_witness_found"] = dense_search["found"]
    out["dense_2x2_search_status"] = dense_search["search_status"]
    out["dense_2x2_arm"] = dense_search["arm"]
    return out


def witness_report(blocks: Sequence[dict]) -> dict:
    """Per-block witness search plus the aggregates the reading needs, all from the receipt."""
    defined = [b for b in blocks if b.get("defined")]
    rows = []
    for b in defined:
        matrix = [[F(x) for x in row] for row in b["matrix"]]
        w = minor_witness(matrix)
        rows.append(
            {
                "source_sector": b["source_sector"],
                "target_sector": b["target_sector"],
                "corner_index": b["corner_index"],
                "direction": b["direction"],
                "shape": b["matrix_shape"],
                "rank": b["rank"],
                "minor_size": w["minor_size"],
                "found": w["found"],
                "arm": w["arm"],
                "form": w["form"],
                "search_status": w["search_status"],
                "nodes": w["nodes"],
                "certificate_verifies": bool(
                    w["certificate_verification"]
                    and w["certificate_verification"]["diagonal_nonzero"]
                    and w["certificate_verification"]["forbidden_entries_zero"]
                ),
                "certificate_digest": w["certificate_digest"],
                "canonical_minor_is_invertible_rank_full": w[
                    "canonical_minor_is_invertible_rank_full"
                ],
                "canonical_minor_rows": w["canonical_minor_rows"],
                "canonical_minor_cols": w["canonical_minor_cols"],
            }
        )
    found = [r for r in rows if r["found"]]
    missing = [r for r in rows if not r["found"]]
    exhausted = [r for r in missing if r["search_status"] == "exhausted"]
    budget_limited = [r for r in missing if r["search_status"] == "budget_limited"]
    above = [r for r in missing if r["search_status"] == "above_exact_search_size"]
    arms = {}
    for row in rows:
        arms[row["arm"] or "none"] = arms.get(row["arm"] or "none", 0) + 1
    by_size: dict[str, dict[str, int]] = {}
    for row in rows:
        slot = by_size.setdefault(str(row["minor_size"]), {"blocks": 0, "witnessed": 0})
        slot["blocks"] += 1
        slot["witnessed"] += 1 if row["found"] else 0
    allowed = sorted({r["canonical_minor_is_invertible_rank_full"] for r in rows})
    return {
        "scope_note": (
            "every row is one computed block; the search is declared and bounded, so a row "
            "with found=false is a statement about the search, not about the block, unless its "
            "search_status is 'exhausted'.  A found witness is checked against the block's own "
            "entries before it is reported (nonzero diagonal, zero forbidden triangle), and the "
            "receipt's examples additionally re-rank their minor by exact elimination."
        ),
        "blocks_searched": len(rows),
        "blocks_with_a_verified_witness": len(found),
        "witness_fraction": f"{len(found)}/{len(rows)}",
        "all_certificates_verified": all(r["certificate_verifies"] for r in found) if found else False,
        "all_blocks_witnessed": len(found) == len(rows) and bool(rows),
        "counterexample_count": len(missing),
        "by_arm": arms,
        "by_minor_size": by_size,
        "by_minor_size_note": (
            "blocks and verified witnesses per min(shape) size of the minor sought: the "
            "smallest sizes carry a witness in every block (a 1x1 minor is any nonzero entry) "
            "while the larger sizes mostly do not, so the declared-order structure is a "
            "small-minor phenomenon and not a uniform one"
        ),
        "by_search_status": {
            "exhausted_without_a_witness": len(exhausted),
            "budget_limited_without_a_witness": len(budget_limited),
            "above_exact_search_size_without_a_witness": len(above),
        },
        "decided_blocks": len(found) + len(exhausted),
        "undecided_blocks": len(budget_limited) + len(above),
        "canonical_minor_invertible_in_every_block": allowed == [True] if rows else False,
        "minor_size_range": [
            min((r["minor_size"] for r in rows), default=None),
            max((r["minor_size"] for r in rows), default=None),
        ],
        "first_block_without_a_witness": missing[0] if missing else None,
        "first_exhausted_negative": exhausted[0] if exhausted else None,
        "witness_examples": _witness_examples(defined),
        "rows": rows,
        "claim_scope": (
            "witness_fraction counts blocks for which a triangular min(shape) minor was found "
            "and verified in the declared entries.  'exhausted_without_a_witness' blocks are an "
            "exact negative inside the declared entries (the search explored its whole space at "
            "that size); 'budget_limited_without_a_witness' and "
            "'above_exact_search_size_without_a_witness' blocks are undecided, so no claim is "
            "made about them.  A fraction below one is therefore not the assertion that no "
            "witness exists for the remaining blocks."
        ),
    }


def _witness_examples(blocks: Sequence[dict], limit: int = 4) -> list[dict]:
    """Full certificates for a declared sample: the smallest blocks, then the largest minor."""
    out: list[dict] = []
    chosen: list[dict] = []
    if not blocks:
        return out
    chosen.append(blocks[0])
    by_k = sorted(blocks, key=lambda b: (min(b["matrix_shape"]), b["source_sector"]))
    chosen.append(by_k[len(by_k) // 2])
    largest = max(blocks, key=lambda b: min(b["matrix_shape"]))
    chosen.append(largest)
    for b in chosen[:limit]:
        matrix = [[F(x) for x in row] for row in b["matrix"]]
        w = minor_witness(matrix)
        record = {
            "source_sector": b["source_sector"],
            "target_sector": b["target_sector"],
            "corner_index": b["corner_index"],
            "direction": b["direction"],
            "shape": b["matrix_shape"],
            "rank": b["rank"],
            "arm": w["arm"],
            "form": w["form"],
            "certificate_digest": w["certificate_digest"],
        }
        if w["found"]:
            rows, cols = w["order"]
            record["witness_rows"] = rows
            record["witness_cols"] = cols
            record["verification"] = _verify_witness(matrix, rows, cols, w["form"], rank_check=True)
        else:
            record["search_status"] = w["search_status"]
            record["canonical_minor_rows"] = w["canonical_minor_rows"]
            record["canonical_minor_cols"] = w["canonical_minor_cols"]
        out.append(record)
    return out


def full_rank_saturation(blocks: Sequence[dict]) -> dict:
    """How many computed blocks attain rank = min(shape), with the rank range."""
    defined = [b for b in blocks if b.get("defined")]
    saturated = [
        b for b in defined if b["matrix_shape"][1] and b["rank"] == min(b["matrix_shape"])
    ]
    deficient = [
        b for b in defined if not (b["matrix_shape"][1] and b["rank"] == min(b["matrix_shape"]))
    ]
    ranks = [b["rank"] for b in defined]
    return {
        "blocks": len(defined),
        "saturated_blocks": len(saturated),
        "deficient_blocks": len(deficient),
        "saturation_holds_for_every_computed_block": bool(defined)
        and len(deficient) == 0,
        "rank_range": [min(ranks), max(ranks)] if ranks else None,
        "kernel_dimension_range": (
            [
                min(b["kernel_dimension"] for b in defined),
                max(b["kernel_dimension"] for b in defined),
            ]
            if defined
            else None
        ),
        "deficient_examples": [
            {
                "source_sector": b["source_sector"],
                "target_sector": b["target_sector"],
                "corner_index": b["corner_index"],
                "direction": b["direction"],
                "shape": b["matrix_shape"],
                "rank": b["rank"],
                "is_zero": b["is_zero"],
            }
            for b in deficient[:8]
        ],
    }


def _block_key(b: Mapping[str, Any]) -> tuple:
    return (tuple(b["source_sector"]), tuple(b["target_sector"]), b["corner_index"], b["direction"])


def _witness_rows_by_key(report: Mapping[str, Any]) -> dict:
    return {_block_key(r): r for r in report.get("rows", [])}


# Declared wall-clock budget of the runner, and the measurements the widened frontier was
# chosen from.  The bound is end to end; the numbers below are extension build times measured
# on the development machine of this receipt (the default scope plus assembly adds about
# FRONTIER_DEFAULT_SCOPE_SECONDS).  The chosen frontier is the largest candidate whose measured
# time keeps the runner inside the bound.  Wall clock is not monotone in the frontier here: the
# 64 candidate measured slower than the 91 candidate under the same exact-rational elimination,
# which is why the decision below is read off the measurements rather than off the cost units.
FRONTIER_BUDGET_SECONDS = 180
FRONTIER_DEFAULT_SCOPE_SECONDS = 35
FRONTIER_BUILD_SECONDS_MEASURED = {
    19: 24.3,
    30: 36.4,
    35: 55.0,
    51: 82.0,
    64: 230.0,
    91: 150.9,
}


def frontier_budget() -> dict:
    """Which frontier the declared runner budget buys, read off the measured build times."""
    extension_budget = FRONTIER_BUDGET_SECONDS - FRONTIER_DEFAULT_SCOPE_SECONDS
    inside = sorted(f for f, s in FRONTIER_BUILD_SECONDS_MEASURED.items() if s <= extension_budget)
    outside = sorted(f for f, s in FRONTIER_BUILD_SECONDS_MEASURED.items() if s > extension_budget)
    return {
        "bound_seconds": FRONTIER_BUDGET_SECONDS,
        "default_scope_and_assembly_seconds": FRONTIER_DEFAULT_SCOPE_SECONDS,
        "extension_budget_seconds": extension_budget,
        "measured_extension_build_seconds_by_frontier": {
            str(k): v for k, v in sorted(FRONTIER_BUILD_SECONDS_MEASURED.items())
        },
        "largest_frontier_inside_the_budget": max(inside) if inside else None,
        "frontiers_outside_the_budget": outside,
        "measurement_scope": (
            "extension build times measured on the development machine of this receipt, with "
            "the declared wall-clock bound covering the whole runner"
        ),
    }


def widened_scope(
    frontier: int, default_blocks: Sequence[dict], default_witness: Mapping[str, Any]
) -> dict:
    """The same label-at-most-two family at a wider declared multiplicity frontier.

    This is an explicitly separated scope.  The stored default scope is computed at
    FRONTIER_DIM and stays there, because the test suite rebuilds it inside its own wall-clock
    bound; this section recomputes the same family at ``frontier`` and records what the wider
    budget buys, block by block, including every block it still excludes with exact dimensions
    and cost units.  Neither scope hides the other: the blocks the two scopes share are
    compared entry for entry and their witness rows compared field by field.
    """
    started = time.perf_counter()
    analysis = build_analysis(cutoff=EXTENDED_CUTOFF, frontier_dim=frontier)
    blocks = analysis["blocks"]
    skipped = analysis["skipped_blocks"]
    defined = {_block_key(b): b for b in blocks if b.get("defined")}
    default_defined = {_block_key(b): b for b in default_blocks if b.get("defined")}
    overlap = sorted(set(defined) & set(default_defined))
    newly = [b for b in blocks if b.get("defined") and _block_key(b) not in default_defined]
    witness = witness_report(blocks)
    wide_rows = _witness_rows_by_key(witness)
    default_rows = _witness_rows_by_key(default_witness)
    table = extension_table(analysis)
    family_total_expected = sum(row["expected_shift_count"] for row in table["rows"])
    return {
        "cutoff": EXTENDED_CUTOFF,
        "frontier_dim": frontier,
        "frontier_rule": (
            "a block is computed iff max(M^f(source), M^f(target)) <= the widened frontier; "
            "every block beyond the rule is listed with its exact dimensions and cost units, and "
            "no block is dropped without a record"
        ),
        "scope_note": (
            "separate declared scope: the stored default scope above is computed at the "
            "narrower frontier and is the one the test suite rebuilds; this section is the "
            "same family recomputed at the wider frontier, and both are reported in full"
        ),
        "frontier_choice": {
            **frontier_budget(),
            "chosen_frontier": frontier,
            "reason": (
                "the widened scope is computed at this frontier because it is the largest "
                "measured candidate that keeps the runner inside the declared bound; the "
                "measurements are per-frontier extension build times, and every block either "
                "scope excludes is recorded with its exact dimensions and cost units, so the "
                "budget is visible rather than silent"
            ),
        },
        "source_family": (
            "labels at most two (81 sectors); targets reach label three, since an up-shift "
            "leaves the family"
        ),
        "summary": summarise_blocks(blocks),
        "full_rank_saturation": full_rank_saturation(blocks),
        "vanishing": vanishing_pattern(blocks, skipped),
        "rank_witness": witness,
        "corner_spectator": corner_spectator_reading(blocks),
        "by_source_sector": table,
        "blocks": blocks,
        "skipped_blocks": skipped,
        "max_source_dimension_reached": max(
            (b["matrix_shape"][1] for b in blocks if b.get("defined")), default=None
        ),
        "max_target_dimension_reached": max(
            (b["matrix_shape"][0] for b in blocks if b.get("defined")), default=None
        ),
        "against_the_stored_default_scope": {
            "stored_default_frontier": FRONTIER_DIM,
            "stored_default_blocks": len(default_defined),
            "widened_blocks": len(defined),
            "newly_computed_blocks": len(newly),
            "newly_computed_cost_units": sum(
                b["matrix_shape"][0] * b["matrix_shape"][1] for b in newly
            ),
            "newly_computed_zero_blocks": sum(1 for b in newly if b["is_zero"]),
            "newly_computed_full_rank_blocks": sum(
                1
                for b in newly
                if b["matrix_shape"][1] and b["rank"] == min(b["matrix_shape"])
            ),
            "newly_computed_largest_dimension_pair": _largest_dimension_pair(newly),
            "blocks_computed_in_both_scopes": len(overlap),
            "every_default_block_recomputed_here": len(overlap) == len(default_defined),
            "overlap_entries_identical": all(
                defined[k]["matrix"] == default_defined[k]["matrix"] for k in overlap
            ),
            "overlap_witness_rows_identical": all(
                wide_rows[k] == default_rows[k] for k in overlap if k in wide_rows and k in default_rows
            )
            and len([k for k in overlap if k in wide_rows and k in default_rows]) == len(overlap),
            "still_excluded_blocks": len(skipped),
            "family_total_reconciles": len(defined) + len(skipped) == family_total_expected,
            "family_total": len(defined) + len(skipped),
        },
        "elapsed_seconds": time.perf_counter() - started,
    }


def _compact_block_row(block: Mapping[str, Any]) -> dict:
    """One block without its matrix: everything the readings need, and nothing bulky."""
    return {
        "source_sector": block["source_sector"],
        "target_sector": block["target_sector"],
        "corner_index": block["corner_index"],
        "direction": block["direction"],
        "matrix_shape": block["matrix_shape"],
        "rank": block["rank"],
        "kernel_dimension": block["kernel_dimension"],
        "is_zero": block["is_zero"],
        "cost_units": block["matrix_shape"][0] * block["matrix_shape"][1],
    }


def complete_family_scope(
    default_blocks: Sequence[dict],
    default_witness: Mapping[str, Any],
    widened: Mapping[str, Any],
) -> dict:
    """The label-at-most-two family with no block left out, as its own declared scope.

    This is the total reading of the obligation's finite family: no frontier, no uncomputed
    block, every block computed by exact rational elimination and none approximated.  It is
    built on demand rather than by the default path, because the largest blocks of the family
    dominate the cost; the section declares this build's measured seconds instead of hiding the
    cost behind a frontier.  The blocks the narrower scopes already carry are recorded here as
    compact rows (their matrices live in those sections, entry for entry identical), and the
    blocks the widened scope cannot reach are stored in full, so no claim in this section rests
    on a block whose exact entries are missing from the receipt.
    """
    started = time.perf_counter()
    analysis = build_analysis(cutoff=EXTENDED_CUTOFF, frontier_dim=COMPLETE_FRONTIER_DIM)
    blocks = analysis["blocks"]
    skipped = analysis["skipped_blocks"]
    defined = {_block_key(b): b for b in blocks if b.get("defined")}
    default_defined = {_block_key(b): b for b in default_blocks if b.get("defined")}
    widened_defined = {_block_key(b): b for b in widened["blocks"] if b.get("defined")}
    witness = witness_report(blocks)
    rows = _witness_rows_by_key(witness)
    default_rows = _witness_rows_by_key(default_witness)
    widened_rows = _witness_rows_by_key(widened["rank_witness"])
    beyond_widened = sorted(
        (b for b in blocks if b.get("defined") and _block_key(b) not in widened_defined),
        key=lambda b: (b["matrix_shape"][0] * b["matrix_shape"][1], _block_key(b)),
    )
    table = extension_table(analysis)
    family_total = sum(row["expected_shift_count"] for row in table["rows"])
    largest = sorted(
        defined.values(),
        key=lambda b: (min(b["matrix_shape"]), b["matrix_shape"][0] * b["matrix_shape"][1]),
        reverse=True,
    )[:8]
    elapsed = time.perf_counter() - started
    return {
        "cutoff": EXTENDED_CUTOFF,
        "frontier_dim": COMPLETE_FRONTIER_DIM,
        "exclusion_policy": (
            "none: every block of the family is computed, so this section holds no uncomputed "
            "record and no bounded or approximated elimination"
        ),
        "scope_note": (
            "separate declared scope built on demand: the stored default scope and the widened "
            "scope above keep their own frontiers and stay the sections the test suite rebuilds; "
            "this one completes the family and declares what completing it costs.  Its blocks "
            "are compact rows except for the blocks the widened scope could not reach, which are "
            "stored with their full matrices"
        ),
        "source_family": (
            "labels at most two (81 sectors); targets reach label three, since an up-shift "
            "leaves the family"
        ),
        "summary": summarise_blocks(blocks),
        "full_rank_saturation": full_rank_saturation(blocks),
        "vanishing": vanishing_pattern(blocks, skipped),
        "rank_witness": witness,
        "corner_spectator": corner_spectator_reading(blocks),
        "by_source_sector": table,
        "blocks": [_compact_block_row(b) for b in blocks if b.get("defined")],
        "blocks_beyond_the_widened_scope": beyond_widened,
        "skipped_blocks": skipped,
        "blocks_computed": len(defined),
        "blocks_uncomputed": len(skipped),
        "family_total": family_total,
        "family_complete": len(defined) + len(skipped) == family_total and not skipped,
        "largest_blocks": [
            {
                "source_sector": b["source_sector"],
                "target_sector": b["target_sector"],
                "corner_index": b["corner_index"],
                "direction": b["direction"],
                "matrix_shape": b["matrix_shape"],
                "rank": b["rank"],
                "kernel_dimension": b["kernel_dimension"],
                "is_zero": b["is_zero"],
                "cost_units": b["matrix_shape"][0] * b["matrix_shape"][1],
            }
            for b in largest
        ],
        "against_the_narrower_scopes": {
            "stored_default_frontier": FRONTIER_DIM,
            "widened_frontier": widened["frontier_dim"],
            "stored_default_blocks": len(default_defined),
            "widened_blocks": len(widened_defined),
            "complete_blocks": len(defined),
            "blocks_in_all_three_scopes": len(set(defined) & set(default_defined) & set(widened_defined)),
            "blocks_computed_beyond_the_widened_scope": len(beyond_widened),
            "cost_units_beyond_the_widened_scope": sum(
                b["matrix_shape"][0] * b["matrix_shape"][1] for b in beyond_widened
            ),
            "zero_blocks_beyond_the_widened_scope": sum(1 for b in beyond_widened if b["is_zero"]),
            "full_rank_blocks_beyond_the_widened_scope": sum(
                1
                for b in beyond_widened
                if b["matrix_shape"][0] and b["rank"] == min(b["matrix_shape"])
            ),
            "largest_dimension_pair_beyond_the_widened_scope": _largest_dimension_pair(
                beyond_widened
            ),
            "overlap_entries_identical_to_the_default": all(
                defined[k]["matrix"] == default_defined[k]["matrix"]
                for k in set(defined) & set(default_defined)
            ),
            "overlap_entries_identical_to_the_widened": all(
                defined[k]["matrix"] == widened_defined[k]["matrix"]
                for k in set(defined) & set(widened_defined)
            ),
            "overlap_witness_rows_identical_to_the_default": all(
                rows[k] == default_rows[k] for k in set(rows) & set(default_rows)
            )
            and len(set(rows) & set(default_rows)) == len(default_rows),
            "overlap_witness_rows_identical_to_the_widened": all(
                rows[k] == widened_rows[k] for k in set(rows) & set(widened_rows)
            )
            and len(set(rows) & set(widened_rows)) == len(widened_rows),
            "family_total_reconciles": len(defined) + len(skipped) == family_total,
        },
        "budget": {
            "runner_bound_seconds": FRONTIER_BUDGET_SECONDS,
            "measured_seconds": elapsed,
            "exceeds_the_runner_bound": elapsed > FRONTIER_BUDGET_SECONDS,
            "reason": (
                "the complete family has no frontier left to hide behind: the blocks whose "
                "larger multiplicity is 120 and 64-51 carry the minutes this scope is declared "
                "to cost, and they are computed exactly rather than approximated.  The default "
                "scope and the test suite never pay for this section; the runner enters it only "
                "through the opt-in path, and the measured seconds above are this build's own"
            ),
            "bounded_or_approximated_blocks": [],
            "measured_largest_block_seconds": dict(COMPLETE_LARGEST_BLOCK_SECONDS_MEASURED),
            "measurement_scope": (
                "per-block wall-clock seconds measured on the development machine of this "
                "receipt for the largest shapes of the family, with exact rational elimination"
            ),
        },
        "elapsed_seconds": elapsed,
    }


def limitations(
    analysis: dict,
    blocks: Sequence[dict],
    extension: dict | None = None,
    widened: dict | None = None,
    complete: dict | None = None,
) -> list[str]:
    frontier = FRONTIER_DIM
    computed = len(extension.get("blocks", [])) if extension else len(blocks)
    skipped = len(extension.get("skipped_blocks", [])) if extension else 0
    family_total = computed + skipped
    rows = [
        "The map states the general compression matrix (UFA105) as its recorded obligation "
        "and supplies source/target spaces, the support action and a slice derivation; it "
        "does not fix the operator normalization.  The matrices below are computed in the "
        "declared model C1 (rim/fusion-tree realization with explicit SU(2) intertwiners) "
        "and are entries of that declared realization, not of an unspecified physical K.",
        "model_status = declared_proxy: the rim legs are kept open (one index per rim link, "
        "the corner pair condition is used only to fix the sector labels as the map does) "
        "and the interior is the four midpoint intertwiners plus the centre channel.",
        "Entries depend on the declared basis normalization (primitive-integer invariants) "
        "and on the declared Hilbert pairing; rank, kernel dimension and the zero/nonzero "
        "pattern of each block are the basis-invariant readings that the map's UFA107 needs.",
        "Asymptotic parts of the obligation (uniform sector ranks, form domains, off-diagonal "
        "bounds in the map's wording) are not addressed.  The finite adjacent blocks are "
        "computed on the labels-at-most-one sources with targets up to label two (the map's "
        "smallest cases) and extended to the label-at-most-two sources under a declared "
        f"multiplicity frontier of {frontier}; the blocks beyond that frontier are listed "
        "individually with their exact dimensions and cost units, so the extension is bounded "
        "by a declared budget rather than by a silent cutoff.",
        "The vanishing pattern is a negative result on the computed family: no zero block was "
        f"found among the {computed} computed blocks inside the declared model, which are all "
        f"the blocks of the label-at-most-two family whose two multiplicities are at most "
        f"{frontier}.  The other {skipped} of the {family_total} blocks of that family are "
        "recorded uncomputed, with their exact dimensions and cost units, rather than assumed "
        "non-vanishing: the negative result does not extend past the frontier.",
        "The all-identity-slice statement of lines 2287-2298 is reproduced only at the local "
        "corner pair (corner_slice_content); the rim-normalized slice statement is open.",
        "No claim is made about the coarse-sector comparison of (UFA97), which the map itself "
        "records as needing a matched coarse-sector identification it does not fix.",
    ]
    if widened is not None:
        wide_frontier = widened["frontier_dim"]
        wide = widened["summary"]["block_count"]
        wide_skipped = len(widened["skipped_blocks"])
        rows.append(
            "The widened scope is a separate declared section, not a replacement for the "
            f"stored one: it recomputes the same label-at-most-two family at the wider declared "
            f"frontier {wide_frontier} and computes {wide} of its {wide + wide_skipped} blocks. "
            f"The {wide_skipped} blocks above that frontier are still recorded with their exact "
            "dimensions and cost units, so the vanishing result remains a finite negative on "
            "computed blocks and is not extended past the wider frontier either."
        )
        rows.append(
            "The rank-witness search is declared and bounded, and its negatives are only as "
            "strong as the search: a block reported without a witness whose search_status is "
            f"'exhausted' has no triangular min(shape) minor in the declared entries (the "
            f"search explored its whole space for minor sizes up to {WITNESS_EXACT_MAX_K}), "
            "while 'budget_limited' and 'above_exact_search_size' rows are undecided.  A found "
            "witness is verified from the block's own entries (nonzero diagonal, zero forbidden "
            "triangle), which exhibits that block's full-rank saturation directly; the blocks "
            "without one leave saturation on the exact rank computation alone.  No claim is made "
            "that a witness exists for the undecided blocks or that none exists outside the "
            "declared entries."
        )
    if complete is not None:
        computed = complete["blocks_computed"]
        total = complete["family_total"]
        rows.append(
            f"The complete family is a third declared scope, built on demand: it computes all "
            f"{computed} of the {total} blocks of the label-at-most-two family, excludes none, "
            "and bounded no elimination.  Its own build seconds are a clock reading and live in "
            "this section's budget field, which the digest strips, so this prose carries no value "
            "that varies between two identical runs; the declared bound it exceeds is "
            f"{complete['budget']['runner_bound_seconds']} s ({complete['budget']['reason']}).  It "
            "is entered only through the opt-in path, so the default scope, the widened scope and "
            "the test suite stay inside their own wall-clock bounds and the receipt declares the "
            "seconds this section costs rather than hiding them."
        )
    return rows


# Declared frontier for the extension beyond the smallest family: a block is computed when
# both its source and target multiplicities are at most this.  It is a declared budget, and
# what it buys is visible in the receipt: with it the extension computes the blocks of the
# label-at-most-two family whose two multiplicities are at most the frontier, and the blocks
# beyond it are listed with their exact dimensions and cost units.  A wider frontier is
# affordable only in steps, since the multiplicity cost grows roughly with the product of the
# two multiplicities, and the test suite rebuilds the whole receipt inside its own wall-clock
# bound.  The value below is the smallest frontier that still contains the blocks where the
# corner-by-corner rank reading disagrees, so the negative result about that property is
# inside the declared scope rather than above it.
FRONTIER_DIM = 19

# Labels at most two: the map's next family after the smallest cases, reached by four
# independent corner shifts out of the truncation family.
EXTENDED_CUTOFF = 2


# Declared frontier of the separate widened scope.  The stored default scope above stays at
# FRONTIER_DIM because the test suite rebuilds the whole receipt inside its own wall-clock
# bound; the widened scope is a second, explicitly separated section of the same receipt,
# computed at this frontier by a runner that is allowed the larger budget.  The value is the
# largest frontier whose measured extension build time keeps the runner inside
# FRONTIER_BUDGET_SECONDS (see FRONTIER_BUILD_SECONDS_MEASURED and frontier_budget above);
# every block it still excludes is recorded with exact dimensions and cost units in the
# widened section.
WIDENED_FRONTIER_DIM = 51

# The complete family: the same label-at-most-two family with no block left out.  Every
# multiplicity that occurs in the family is at most this, so a build at this frontier computes
# all 540 blocks and excludes none.  It is a third declared scope, built on demand by the
# runner's opt-in path (and never by the test fixture), because the largest blocks dominate the
# cost: the seconds below are per-block measurements of the largest shapes, taken on the
# development machine of this receipt with the same exact rational elimination.
COMPLETE_FRONTIER_DIM = 120
COMPLETE_LARGEST_BLOCK_SECONDS_MEASURED = {
    "64x51": 5.4,
    "91x51": 2.7,
    "51x91": 6.1,
    "120x91": 21.9,
}


def build_receipt(include_widened: bool = False, include_complete: bool = False) -> dict:
    started = time.perf_counter()
    quotes = read_source_quotes()
    analysis = build_analysis()
    blocks = analysis["blocks"]
    summary = summarise_blocks(blocks)
    extended = build_analysis(cutoff=EXTENDED_CUTOFF, frontier_dim=FRONTIER_DIM)
    extended_blocks = extended["blocks"]
    extension_witness = witness_report(extended_blocks)
    declared_weights = generator_hermeticity_residual(unitary_weights)
    control_weights = generator_hermeticity_residual(flat_weights)
    receipt = {
        "schema": SCHEMA,
        "obligation": {
            "name": "UFA105",
            "document": quotes["document"],
            "document_sha256_at_read_time": quotes["document_sha256_at_read_time"],
            "quotes": quotes["quotes"],
            "demand_verbatim": quotes["named"]["demand"],
            "demand_lines": [2301, 2312],
            "demand_slice_note": (
                "the slice starts on line 2301, where the preceding sentence ends and the "
                "demand's own sentence begins with the word 'For'; the operative demand is "
                "'For general sectors the compression is a linear map between multiplicity "
                "spaces, K_{alpha->alpha+-e_c}: M^f(alpha) -> M^f(alpha+-e_c) (UFA105), whose "
                "vanishing pattern decides which sector families can be exact'"
            ),
            "support_action_verbatim": quotes["named"]["support_action"],
            "support_action_lines": [2274, 2285],
            "verbatim_convention": (
                "the two named quotes are the document's own lines, character for character "
                "(LaTeX and line breaks included), sliced from the file read at run time"
            ),
        },
        "declared_model": {
            "id": "C1",
            "model_status": "declared_proxy",
            "summary": (
                "sector (a,b,c,d) = corner-pair labels of the refined square; fine basis = "
                "the map's labelings (s1,s2,s3,s4,r); each basis vector realized as the exact "
                "invariant tensor of the interior fusion tree (four midpoint intertwiners "
                "contracted with the centre channel r) with the eight rim legs open; the "
                "corner-a multiplier realized as the explicit fundamental insertion at the two "
                "rim legs of corner a's pair, closed by the curl"
            ),
            "invariant_construction": (
                "Inv(V_l1 (x) ... (x) V_lk) = kernel of the total su(2) generators over Q; "
                "basis vectors reduced to primitive integer entries"
            ),
            "hilbert_structure": "<e_k,e_k> = 1/C(n,k) (unitary); corner-epsilon-paired variant reported",
            "open_beyond_model": (
                "the map's full Peter-Weyl/lattice normalization of the corner plaquette and "
                "the closed-graph contraction of the rim structure"
            ),
        },
        "smallest_cases": {
            "source": "map lines 2314-2319 (cutoffs) and 2338-2346 (anchor table)",
            "cutoff": SMALLEST_CUTOFF,
            "sector_count": len(analysis["sectors"]),
            "sectors": analysis["sectors"],
            "anchor_table_check": [
                {
                    "sector": list(alpha),
                    "map_value": value,
                    "computed": fine_dimension(alpha),
                    "matches": fine_dimension(alpha) == value,
                }
                for alpha, value in ANCHOR_TABLE
            ],
            "cutoff_counts_check": [
                {
                    "cutoff": c,
                    "map_value": value,
                    "computed": (c + 1) ** 4,
                    "matches": (c + 1) ** 4 == value,
                }
                for c, value in CUTOFF_COUNTS
            ],
        },
        "basis_construction": {
            "fuse": "fuse(m,n) = {|m-n|,|m-n|+2,...,m+n} (map line 2264)",
            "pairing": "UFA106 centre resolution (s1,s2)|(s3,s4); alternative 14|23 reported",
            "metric_tensors": {
                str(n): [[str(as_fraction(x)) for x in row] for row in metric(n)[1]]
                for n in range(0, 4)
            },
            "mesh_tensors": {
                ",".join(str(n) for n in legs): [
                    [str(F(int(x))) for x in row] for row in invariant_tensor(legs)[1].reshape(-1, dim(legs[-1]))[: min(4, 1)]
                ]
                for legs in ()
            },
            "explicit_intertwiners": _explicit_intertwiners(),
            "example_state_vectors": _example_states(),
            "state_vector_digests": _state_digests(analysis["sectors"]),
        },
        "compression": {
            "summary": summary,
            "blocks": blocks,
            "trivial_spoke": trivial_spoke_report(blocks),
            "full_rank_saturation": full_rank_saturation(blocks),
            "rank_witness": witness_report(blocks),
        },
        "extension": {
            "cutoff": EXTENDED_CUTOFF,
            "frontier_dim": FRONTIER_DIM,
            "frontier_rule": (
                "a block is computed iff max(M^f(source), M^f(target)) <= FRONTIER_DIM; every "
                "block beyond the rule is listed with its exact dimensions and that reason, and "
                "no block is dropped without a record"
            ),
            "source_family": (
                "labels at most two (81 sectors); targets reach label three, since an up-shift "
                "leaves the family"
            ),
            "summary": summarise_blocks(extended_blocks),
            "full_rank_saturation": full_rank_saturation(extended_blocks),
            "rank_witness": extension_witness,
            "vanishing": vanishing_pattern(extended_blocks, extended["skipped_blocks"]),
            "corner_spectator": corner_spectator_reading(extended_blocks),
            "orthogonality_aggregates": orthogonality_aggregates(
                _orthogonality_readings(extended_blocks)["rows"]
            ),
            "rank_and_kernel": {
                "per_block": [
                    {
                        "source_sector": b["source_sector"],
                        "target_sector": b["target_sector"],
                        "corner_index": b["corner_index"],
                        "direction": b["direction"],
                        "shape": b["matrix_shape"],
                        "rank": b["rank"],
                        "kernel_dimension": b["kernel_dimension"],
                        "is_zero": b["is_zero"],
                    }
                    for b in extended_blocks
                    if b.get("defined")
                ]
            },
            "blocks": extended_blocks,
            "skipped_blocks": extended["skipped_blocks"],
            "by_source_sector": extension_table(extended),
            "max_source_dimension_reached": max(
                (b["matrix_shape"][1] for b in extended_blocks if b.get("defined")), default=None
            ),
            "max_target_dimension_reached": max(
                (b["matrix_shape"][0] for b in extended_blocks if b.get("defined")), default=None
            ),
        },
        "pairing_columns": pairing_columns(),
        "structural_properties": {
            "rank_and_kernel": {
                "per_block": [
                    {
                        "source_sector": b["source_sector"],
                        "target_sector": b["target_sector"],
                        "corner_index": b["corner_index"],
                        "direction": b["direction"],
                        "shape": b["matrix_shape"],
                        "rank": b["rank"],
                        "kernel_dimension": b["kernel_dimension"],
                        "is_zero": b["is_zero"],
                    }
                    for b in blocks
                    if b.get("defined")
                ]
            },
            "symmetry": {
                "compression_covariance": relabelling_check(blocks),
                "mf_permutation_invariance": mf_permutation_invariance(),
                "corner_spectator_smallest_family": corner_spectator_reading(blocks),
            },
            "pairing_choice_independence": pairing_variant_check(blocks),
            "orientation_sign": curl_variant_check(blocks),
            "orthogonality_readings": _orthogonality_readings(blocks),
            "orthogonality_aggregates": orthogonality_aggregates(
                _orthogonality_readings(blocks)["rows"]
            ),
        },
        "checks": {
            "anchor_table": {
                "rows": [
                    {
                        "sector": list(alpha),
                        "map_value": value,
                        "computed": fine_dimension(alpha),
                        "matches": fine_dimension(alpha) == value,
                    }
                    for alpha, value in ANCHOR_TABLE
                ],
                "all_match": all(fine_dimension(alpha) == value for alpha, value in ANCHOR_TABLE),
            },
            "cutoff_counts": {
                "rows": [
                    {
                        "cutoff": c,
                        "map_value": value,
                        "computed": (c + 1) ** 4,
                        "matches": (c + 1) ** 4 == value,
                    }
                    for c, value in CUTOFF_COUNTS
                ],
                "all_match": all((c + 1) ** 4 == value for c, value in CUTOFF_COUNTS),
            },
            "basis_independence": {
                "rows": _basis_rank_rows(analysis["sectors"]),
                "all_full": all(
                    row["span_rank"] == row["fine_dimension"] for row in _basis_rank_rows(analysis["sectors"])
                ),
            },
            "hermiticity": {
                "declared_weights_residual": str(declared_weights),
                "flat_weights_residual": str(control_weights),
                "declared_is_hermitian": declared_weights == 0,
                "flat_weights_fire": control_weights != 0,
            },
            "corner_slice_content": corner_slice_content(),
            "firing_controls": firing_controls(),
            "rank_witness_controls": witness_controls(blocks),
        },
        "closure": _closure_statement(blocks, analysis["sectors"]),
        "limitations": [],
        "runtime_seconds": None,
        "receipt_sha256": None,
    }
    widened = None
    complete = None
    if include_widened or include_complete:
        # the complete scope is read against the widened one, so it always has it
        widened = widened_scope(WIDENED_FRONTIER_DIM, extended_blocks, extension_witness)
        receipt["widened_scope"] = widened
    if include_complete:
        complete = complete_family_scope(extended_blocks, extension_witness, widened)
        receipt["complete_family"] = complete
    receipt["limitations"] = limitations(analysis, blocks, extended, widened, complete)
    receipt["digest_convention"] = digest_convention()
    receipt["runtime_seconds"] = time.perf_counter() - started
    assert_finite(receipt)
    violations = run_varying_leaves(receipt)
    if violations:
        raise AssertionError(
            "run-varying value inside the digest body, refused so the content digest stays "
            f"stable between two identical runs: {violations}"
        )
    receipt["receipt_sha256"] = content_digest(receipt)
    return receipt


def _explicit_intertwiners() -> dict:
    out = {}
    legs_seen = set()
    for alpha in product(range(3), repeat=4):
        for c in (0, 1):
            for s in fuse(alpha[0], alpha[1]):
                legs_seen.add((alpha[0], alpha[1], s))
    for legs in sorted(legs_seen):
        basis = invariant_space(legs)
        if len(basis) != 1:
            continue
        out[",".join(str(n) for n in legs)] = {
            "dimension": len(basis),
            "entries": [str(x) for x in _primitive_integers(basis[0])],
        }
    return out


def _example_states() -> dict:
    out = {}
    for alpha in ((0, 0, 0, 0), (1, 1, 0, 0), (1, 0, 0, 0)):
        for lab in fine_basis(alpha)[:2]:
            key = f"{alpha}|{lab}"
            out[key] = state_vector(alpha, lab)
    return out


def _state_digests(sectors: Sequence[dict]) -> dict:
    out = {}
    for row in sectors:
        alpha = tuple(row["sector"])
        vecs = [state_vector(alpha, lab)["vector"] for lab in fine_basis(alpha)]
        out[str(alpha)] = {
            "dimension": len(vecs),
            "digest": hashlib.sha256(canonical_json(vecs).encode("utf-8")).hexdigest(),
        }
    return out


def _basis_rank_rows(sectors: Sequence[dict]) -> list[dict]:
    rows = []
    for row in sectors:
        alpha = tuple(row["sector"])
        vecs = [state_vector(alpha, lab)["vector"] for lab in fine_basis(alpha)]
        rank = rank_rational(vecs) if vecs else 0
        rows.append(
            {
                "sector": list(alpha),
                "span_rank": rank,
                "fine_dimension": len(vecs),
                "independent": rank == len(vecs),
            }
        )
    return rows


def _orthogonality_readings(blocks: Sequence[dict]) -> dict:
    out = []
    for b in blocks[:16]:
        if not b.get("defined"):
            continue
        rows = b["matrix"]
        gram = [
            [sum(F(rows[i][k]) * F(rows[j][k]) for k in range(len(rows[0]))) for j in range(len(rows))]
            for i in range(len(rows))
        ]
        out.append(
            {
                "source_sector": b["source_sector"],
                "target_sector": b["target_sector"],
                "corner_index": b["corner_index"],
                "direction": b["direction"],
                "gram_diagonal": [str(gram[i][i]) for i in range(len(gram))],
                "gram_rank": rank_rational(gram),
                "gram_offdiagonal_all_zero": all(
                    gram[i][j] == 0 for i in range(len(gram)) for j in range(len(gram)) if i != j
                ),
            }
        )
    return {"rows": out, "note": "Gram of K in the declared primitive-integer bases"}


def _closure_statement(blocks: Sequence[dict], sectors: Sequence[dict]) -> dict:
    defined = [b for b in blocks if b.get("defined")]
    nonzero = [b for b in defined if not b["is_zero"]]
    # UFA107 forcing: every shift out of a retained family must vanish, so a nonzero
    # compression into an unretained sector forces that sector into the family.
    forcing = []
    for row in sectors:
        alpha = tuple(row["sector"])
        for corner in range(4):
            for direction in (+1, -1):
                if direction == -1 and alpha[corner] == 0:
                    continue
                match = [
                    b
                    for b in defined
                    if tuple(b["source_sector"]) == alpha
                    and b["corner_index"] == corner
                    and b["direction"] == direction
                ]
                if not match:
                    continue
                b = match[0]
                forcing.append(
                    {
                        "source_sector": list(alpha),
                        "target_sector": b["target_sector"],
                        "corner_index": corner,
                        "direction": direction,
                        "compression_nonzero": not b["is_zero"],
                        "rank": b["rank"],
                        "forces_target_into_family": not b["is_zero"],
                    }
                )
    return {
        "scope": (
            "the cutoff-1 family (labels at most one, 16 sectors) under the four corner shifts; "
            "targets reach label two"
        ),
        "blocks_defined": len(defined),
        "nonzero_compressions": len(nonzero),
        "every_shift_nonzero": all(b["compression_nonzero"] for b in forcing),
        "forcing_rows": forcing,
        "ufa107_consequence_in_model": (
            "every shift out of every cutoff-1 sector has a nonzero declared compression, so in "
            "model C1 the exactness argument of UFA107 closes the full label cone on these "
            "cases; the map's own caveat that the general matrix is pending means this is a "
            "statement about the declared realization"
        ),
        "open": (
            "asymptotic sectors (uniform ranks, form domains) and the physical normalization of "
            "the corner plaquette"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Write the receipt: default scope + widened scope, and the complete family with --complete.

    The widened scope is built by plain execution; the complete family costs minutes, so it is
    entered only through the explicit flag.  --without-widened stops after the stored default
    scope, which is what the test fixture builds.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    include_complete = "--complete" in argv
    include_widened = include_complete or "--without-widened" not in argv
    receipt = build_receipt(include_widened=include_widened, include_complete=include_complete)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(_jsonable(receipt), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"receipt_sha256 {receipt['receipt_sha256']}")
    print(f"blocks {receipt['compression']['summary']['block_count']}")
    print(
        f"stored default scope: frontier {receipt['extension']['frontier_dim']}, "
        f"{receipt['extension']['summary']['block_count']} computed, "
        f"{len(receipt['extension']['skipped_blocks'])} excluded, "
        f"rank witness {receipt['extension']['rank_witness']['witness_fraction']}"
    )
    if include_widened:
        wide = receipt["widened_scope"]
        print(
            f"widened scope: frontier {wide['frontier_dim']}, "
            f"{wide['summary']['block_count']} computed, "
            f"{len(wide['skipped_blocks'])} excluded, "
            f"zero blocks {wide['vanishing']['zero_block_count']}, "
            f"saturated {wide['full_rank_saturation']['saturated_blocks']}, "
            f"rank range {wide['full_rank_saturation']['rank_range']}, "
            f"rank witness {wide['rank_witness']['witness_fraction']}"
        )
    if include_complete:
        full = receipt["complete_family"]
        print(
            f"complete family: {full['blocks_computed']} of {full['family_total']} computed, "
            f"{full['blocks_uncomputed']} excluded, complete={full['family_complete']}, "
            f"zero blocks {full['vanishing']['zero_block_count']}, "
            f"saturated {full['full_rank_saturation']['saturated_blocks']}, "
            f"rank range {full['full_rank_saturation']['rank_range']}, "
            f"rank witness {full['rank_witness']['witness_fraction']}, "
            f"cost {full['budget']['measured_seconds']:.1f}s"
        )
    print(f"runtime {receipt['runtime_seconds']:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
