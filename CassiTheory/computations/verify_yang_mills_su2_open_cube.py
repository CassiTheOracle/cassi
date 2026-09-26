#!/usr/bin/env python3
"""Exact bounded open-cube SU(2) basis and Wilson-support pilot.

The frozen protocol is ``computations/yang-mills-su2-open-cube-prereg.md``.
The representation and Haar-contraction primitives are reused from the exact
finite-block verifier; this file supplies the distinct cube graph, its signed
cyclic plaquette words, the gauge-invariant basis enumeration, and the finite
operator receipt.

Usage::

    python computations/verify_yang_mills_su2_open_cube.py \
        --output runs/yang_mills_su2_open_cube/verification.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import itertools
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

try:
    _exact_block = importlib.import_module("verify_yang_mills_exact_block_spectrum")
except ModuleNotFoundError:
    _exact_block = importlib.import_module("computations.verify_yang_mills_exact_block_spectrum")
Network = _exact_block.Network
link_integral = _exact_block.link_integral
metric_tensor = _exact_block.metric_tensor
three_j = _exact_block.three_j
valid_triple = _exact_block.valid_triple

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-su2-open-cube-prereg.md"
SOURCE = Path(__file__).resolve()
HELPER = SOURCE.with_name("verify_yang_mills_exact_block_spectrum.py")
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_su2_open_cube" / "verification.json"
CUTOFFS = (1, 2)
NONZERO_TOLERANCE = 1.0e-12
MATRIX_TOLERANCE = 1.0e-10
FORBIDDEN_SAMPLE_SIZE = 128

# Vertices are binary xyz coordinates encoded as 4*x + 2*y + z.
VERTICES = tuple(range(8))
TAILS = (0, 0, 0, 4, 4, 2, 2, 6, 1, 1, 5, 3)
HEADS = (4, 2, 1, 6, 5, 6, 3, 7, 5, 3, 7, 7)

# The order of incident edges is fixed by edge ID.  The orientation of an
# incoming edge is handled by the SU(2) invariant metric before its index enters
# the all-outgoing trivalent 3j tensor.
INCIDENT_EDGES: tuple[tuple[int, ...], ...] = tuple(
    tuple(e for e in range(12) if TAILS[e] == vertex or HEADS[e] == vertex)
    for vertex in VERTICES
)

PLAQUETTES: tuple[tuple[tuple[int, int], ...], ...] = (
    ((0, +1), (3, +1), (5, -1), (1, -1)),
    ((8, +1), (10, +1), (11, -1), (9, -1)),
    ((2, +1), (8, +1), (4, -1), (0, -1)),
    ((6, +1), (11, +1), (7, -1), (5, -1)),
    ((1, +1), (6, +1), (9, -1), (2, -1)),
    ((3, +1), (7, +1), (10, -1), (4, -1)),
)
PLAQUETTE_NAMES = ("xy_z0", "xy_z1", "zx_y0", "zx_y1", "yz_x0", "yz_x1")
EXPECTED_DIMENSIONS = {1: 32, 2: 1013}
EXPECTED_CANDIDATES_PER_PLAQUETTE = {1: 32, 2: 2388}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, passed: bool, **detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **detail}


def endpoint(vertex: int, edge: int, orientation: int) -> int:
    if orientation > 0:
        return HEADS[edge] if vertex == TAILS[edge] else -1
    return TAILS[edge] if vertex == HEADS[edge] else -1


def closed_word(word: Sequence[tuple[int, int]]) -> bool:
    if not word:
        return False
    first_edge, first_orientation = word[0]
    start = TAILS[first_edge] if first_orientation > 0 else HEADS[first_edge]
    current = start
    for edge, orientation in word:
        next_vertex = endpoint(current, edge, orientation)
        if next_vertex < 0:
            return False
        current = next_vertex
    return current == start


def word_labels(word: Sequence[tuple[int, int]]) -> tuple[int, ...]:
    return tuple(edge for edge, _ in word)


def enumerate_basis(cutoff: int) -> list[tuple[int, ...]]:
    """Enumerate all edge labels satisfying every trivalent Gauss constraint."""

    states: list[tuple[int, ...]] = []
    for state in itertools.product(range(cutoff + 1), repeat=12):
        if all(valid_triple(*(state[e] for e in edges)) for edges in INCIDENT_EDGES):
            states.append(tuple(int(value) for value in state))
    return states


class CubeCopy:
    """One unnormalized trivalent spin-network copy in a tensor network."""

    def __init__(self, net: Network, state: tuple[int, ...], prefix: str) -> None:
        self.net = net
        self.state = state
        self.m = {edge: net.label(f"{prefix}m{edge}", (state[edge],)) for edge in range(12)}
        self.n = {edge: net.label(f"{prefix}n{edge}", (state[edge],)) for edge in range(12)}
        self._add_vertices(prefix)

    def _add_vertices(self, prefix: str) -> None:
        for vertex, edges in enumerate(INCIDENT_EDGES):
            axes = []
            for edge in edges:
                if TAILS[edge] == vertex:
                    axes.append(self.m[edge])
                    continue
                converted = self.net.label(f"{prefix}v{vertex}e{edge}", (self.state[edge],))
                self.net.add(metric_tensor(self.state[edge]), (converted, self.n[edge]))
                axes.append(converted)
            tensor = three_j(*(self.state[edge] for edge in edges))
            self.net.add(tensor, tuple(axes))

    def factors(self) -> dict[int, tuple[Any, Any]]:
        return {edge: (self.m[edge], self.n[edge]) for edge in range(12)}


def cube_loop_factors(
    net: Network,
    word: Sequence[tuple[int, int]],
    tag: str,
    dagger: bool = False,
) -> dict[int, tuple[Any, Any, bool]]:
    """Return fundamental link factors for a signed cyclic Wilson word."""

    loop_labels = [net.label(f"{tag}l{index}", (1,)) for index in range(4)]
    factors: dict[int, tuple[Any, Any, bool]] = {}
    for position, (link, orientation) in enumerate(word):
        first = loop_labels[position]
        second = loop_labels[(position + 1) % 4]
        if orientation > 0:
            pair = (first, second, False)
        else:
            pair = (second, first, True)
        factors[link] = (pair[0], pair[1], pair[2] != dagger)
    return factors


def matrix_element(
    left: tuple[int, ...],
    right: tuple[int, ...],
    word: Sequence[tuple[int, int]],
    dagger: bool = False,
) -> complex:
    """Evaluate ``<left|chi_{1/2}(U_word)|right>`` by Haar contraction."""

    net = Network()
    bra = CubeCopy(net, left, "bra")
    ket = CubeCopy(net, right, "ket")
    loop_factors = cube_loop_factors(net, word, "loop", dagger=dagger)
    for edge in range(12):
        factors = [
            (bra.m[edge], bra.n[edge], True),
            (ket.m[edge], ket.n[edge], False),
        ]
        if edge in loop_factors:
            factors.append(loop_factors[edge])
        link_integral(net, factors, f"link{edge}")
    return complex(net.contract())


def candidate_targets(state: tuple[int, ...], word: Sequence[tuple[int, int]], cutoff: int) -> list[tuple[int, ...]]:
    """Enumerate the exact CG selection-rule support for one ket state."""

    targets: set[tuple[int, ...]] = set()
    links = word_labels(word)
    for signs in itertools.product((-1, +1), repeat=4):
        target = list(state)
        for edge, sign in zip(links, signs):
            target[edge] += sign
        if any(value < 0 or value > cutoff for value in target):
            continue
        if not all(valid_triple(*(target[e] for e in edges)) for edges in INCIDENT_EDGES):
            continue
        targets.add(tuple(target))
    return sorted(targets)


def matrix_hash(entries: Sequence[tuple[int, int, complex]]) -> str:
    payload = bytearray()
    for row, column, value in entries:
        payload.extend(np.asarray((row, column), dtype=np.int64).tobytes())
        payload.extend(np.asarray((value.real, value.imag), dtype=np.float64).tobytes())
    return hashlib.sha256(payload).hexdigest()


def reverse_word(word: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    return tuple((edge, -orientation) for edge, orientation in reversed(word))


def evaluate_plaquette(
    states: Sequence[tuple[int, ...]],
    index: dict[tuple[int, ...], int],
    word: Sequence[tuple[int, int]],
    cutoff: int,
) -> dict[str, Any]:
    values: dict[tuple[int, int], complex] = {}
    for column, right in enumerate(states):
        for left in candidate_targets(right, word, cutoff):
            row = index[left]
            values[(row, column)] = matrix_element(left, right, word)

    entries = [(row, column, value) for (row, column), value in sorted(values.items())]
    finite = all(np.isfinite(value.real) and np.isfinite(value.imag) for _, _, value in entries)
    hermiticity = max(
        (abs(value - np.conj(values.get((column, row), 0j))) for (row, column), value in values.items()),
        default=0.0,
    )
    magnitudes = [abs(value) for _, _, value in entries if abs(value) > NONZERO_TOLERANCE]
    zero_allowed = [
        [row, column]
        for (row, column), value in sorted(values.items())
        if abs(value) <= NONZERO_TOLERANCE
    ]
    candidate_keys = set(values)
    forbidden_sample: list[tuple[int, int]] = []
    for row in range(len(states)):
        for column in range(len(states)):
            if (row, column) in candidate_keys:
                continue
            forbidden_sample.append((row, column))
            if len(forbidden_sample) == FORBIDDEN_SAMPLE_SIZE:
                break
        if len(forbidden_sample) == FORBIDDEN_SAMPLE_SIZE:
            break
    forbidden_values = [
        matrix_element(states[row], states[column], word)
        for row, column in forbidden_sample
    ]
    forbidden_max = max((abs(value) for value in forbidden_values), default=0.0)

    dagger_word = reverse_word(word)
    dagger_candidates = {
        (index[left], column)
        for column, right in enumerate(states)
        for left in candidate_targets(right, dagger_word, cutoff)
    }
    dagger_keys = sorted(values)[: min(64, len(values))]
    dagger_values = {
        key: matrix_element(states[key[0]], states[key[1]], dagger_word)
        for key in dagger_keys
    }
    dagger_residual = max(
        (
            abs(dagger_values[key] - np.conj(values[(key[1], key[0])]))
            for key in dagger_keys
        ),
        default=0.0,
    )
    candidate_count = len(values)
    forbidden_count = len(states) * len(states) - candidate_count
    return {
        "name": PLAQUETTE_NAMES[PLAQUETTES.index(tuple(word))],
        "word": [[edge, sign] for edge, sign in word],
        "dagger_word": [[edge, sign] for edge, sign in dagger_word],
        "candidate_entries": candidate_count,
        "dagger_candidate_entries": len(dagger_candidates),
        "dagger_support_matches": dagger_candidates == set(values),
        "forbidden_entries": forbidden_count,
        "forbidden_sample_count": len(forbidden_sample),
        "forbidden_sample_zero": forbidden_max <= NONZERO_TOLERANCE,
        "maximum_forbidden_sample_magnitude": float(forbidden_max),
        "finite": finite,
        "nonzero_entries": len(magnitudes),
        "zero_allowed_entries": zero_allowed,
        "minimum_nonzero_magnitude": min(magnitudes) if magnitudes else None,
        "maximum_hermiticity_residual": float(hermiticity),
        "dagger_sample_count": len(dagger_keys),
        "maximum_dagger_residual": float(dagger_residual),
        "matrix_sha256": matrix_hash(entries),
        "entries": [[row, column, value.real, value.imag] for row, column, value in entries],
        "dagger_entries": [
            [row, column, dagger_values[(row, column)].real, dagger_values[(row, column)].imag]
            for row, column in dagger_keys
        ],
    }


def run(output: Path) -> dict[str, Any]:
    closure = [closed_word(word) for word in PLAQUETTES]
    if not all(closure):
        raise ArithmeticError(f"non-closing plaquette word: {closure}")

    rows: list[dict[str, Any]] = []
    basis_summary: dict[str, Any] = {}
    for cutoff in CUTOFFS:
        states = enumerate_basis(cutoff)
        index = {state: position for position, state in enumerate(states)}
        plaquette_rows = [evaluate_plaquette(states, index, word, cutoff) for word in PLAQUETTES]
        basis_summary[str(cutoff)] = {
            "dimension": len(states),
            "expected_dimension": EXPECTED_DIMENSIONS[cutoff],
            "state_sha256": hashlib.sha256(
                json.dumps(states, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        }
        rows.append(
            {
                "cutoff": cutoff,
                "dimension": len(states),
                "plaquettes": plaquette_rows,
            }
        )

    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.exists()),
        check("source_path", SOURCE.relative_to(ROOT).as_posix() == "computations/verify_yang_mills_su2_open_cube.py"),
        check("helper_path", HELPER.exists()),
        check("all_words_close", all(closure), closure=closure),
        check("word_count", len(PLAQUETTES) == 6, count=len(PLAQUETTES)),
    ]
    for row in rows:
        cutoff = row["cutoff"]
        expected_dimension = EXPECTED_DIMENSIONS[cutoff]
        expected_candidates = EXPECTED_CANDIDATES_PER_PLAQUETTE[cutoff]
        dimension = row["dimension"]
        checks.extend(
            [
                check(
                    f"basis_dimension_C{cutoff}",
                    dimension == expected_dimension,
                    observed=dimension,
                    expected=expected_dimension,
                ),
                check(
                    f"basis_states_unique_C{cutoff}",
                    len({tuple(item) for item in enumerate_basis(cutoff)}) == dimension,
                    dimension=dimension,
                ),
            ]
        )
        for plaquette in row["plaquettes"]:
            name = plaquette["name"]
            checks.extend(
                [
                    check(
                        f"candidate_count_C{cutoff}_{name}",
                        plaquette["candidate_entries"] == expected_candidates,
                        observed=plaquette["candidate_entries"],
                        expected=expected_candidates,
                    ),
                    check(
                        f"finite_C{cutoff}_{name}",
                        plaquette["finite"],
                    ),
                    check(
                        f"hermitian_C{cutoff}_{name}",
                        plaquette["maximum_hermiticity_residual"] <= MATRIX_TOLERANCE,
                        residual=plaquette["maximum_hermiticity_residual"],
                    ),
                    check(
                        f"dagger_C{cutoff}_{name}",
                        plaquette["dagger_support_matches"]
                        and plaquette["dagger_candidate_entries"] == plaquette["candidate_entries"]
                        and plaquette["dagger_sample_count"]
                        == min(64, plaquette["candidate_entries"])
                        and plaquette["maximum_dagger_residual"] <= MATRIX_TOLERANCE,
                        support_matches=plaquette["dagger_support_matches"],
                        sample_count=plaquette["dagger_sample_count"],
                        residual=plaquette["maximum_dagger_residual"],
                    ),
                    check(
                        f"forbidden_sample_zero_C{cutoff}_{name}",
                        plaquette["forbidden_sample_count"]
                        == min(
                            FORBIDDEN_SAMPLE_SIZE,
                            dimension * dimension - plaquette["candidate_entries"],
                        )
                        and plaquette["forbidden_sample_zero"],
                        sample_count=plaquette["forbidden_sample_count"],
                        maximum_magnitude=plaquette["maximum_forbidden_sample_magnitude"],
                    ),
                ]
            )

    all_checks_pass = all(item["passed"] for item in checks)
    all_allowed_nonzero = all(
        plaquette["nonzero_entries"] == plaquette["candidate_entries"]
        for row in rows
        for plaquette in row["plaquettes"]
    )
    classification = "SUPPORTS_FINITE_OPEN_CUBE_OPERATOR" if all_allowed_nonzero else "CANCELLATION_PRESENT"
    record: dict[str, Any] = {
        "schema": "yang_mills_su2_open_cube_v1",
        "status": "PASS" if all_checks_pass else "FAIL",
        "classification": classification if all_checks_pass else "FAIL",
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "helper": str(HELPER.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256(PROTOCOL),
        "source_sha256": sha256(SOURCE),
        "helper_sha256": sha256(HELPER),
        "nonzero_tolerance": NONZERO_TOLERANCE,
        "matrix_tolerance": MATRIX_TOLERANCE,
        "forbidden_sample_size": FORBIDDEN_SAMPLE_SIZE,
        "vertices": list(VERTICES),
        "tails": list(TAILS),
        "heads": list(HEADS),
        "plaquettes": [
            {"name": name, "word": [[edge, sign] for edge, sign in word]}
            for name, word in zip(PLAQUETTE_NAMES, PLAQUETTES)
        ],
        "basis": basis_summary,
        "rows": rows,
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "scope": "finite open 2x2x2 cube SU(2) spin-network basis and fundamental Wilson support",
        "continuum_claim": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    record = run(args.output)
    print(
        f"status={record['status']} classification={record['classification']} "
        f"checks={record['checks_passed']}/{record['checks_total']}"
    )
    for row in record["rows"]:
        counts = [item["nonzero_entries"] for item in row["plaquettes"]]
        print(f"C={row['cutoff']} dimension={row['dimension']} nonzero_per_plaquette={counts}")


if __name__ == "__main__":
    main()
