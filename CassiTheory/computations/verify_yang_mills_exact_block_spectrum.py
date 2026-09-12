#!/usr/bin/env python3
"""Cutoff SU(2) finite-lattice conditional block spectral study (primary).

Protocol: ``computations/yang-mills-exact-block-spectral-prereg.md``.

Assembles the regulated seven-link two-plaquette SU(2) Hamiltonian

    h_x = K + 2 x N_p - x S,   K = -sum_{e,A} (X_e^A)^2,   S = sum_p Tr U_p

in the generalized (unnormalized spin-network) basis with overlap
``S_ij = <psi_i|psi_j>``, diagonalizes ``(H, S)``, and evaluates the
retained conditional block rate on ``B = {0,1,2,3}`` with exterior data
``U_4 = exp(i theta sigma_3/2)``, ``U_5 = U_6 = I``. The scheduled
transport score is a later implementation target of the protocol and is not
computed here, so no score or margin verdict is issued.

Every integral is an exact SU(2) representation contraction: Wigner 3j
symbols, the Clebsch-Gordan series ``D^{j1}D^{j2} = sum_J C C D^J`` for
products of link matrix elements, and Haar orthogonality.  No Monte Carlo
quadrature and no Cartesian group grid is used.

Usage::

    python computations/verify_yang_mills_exact_block_spectrum.py \
        --output runs/yang_mills_exact_block_spectrum/verification.json [--stage dev]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import string
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import sympy as sp
from sympy.physics.wigner import wigner_3j

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-exact-block-spectral-prereg.md"
SOURCE = Path(__file__).resolve()

# --------------------------------------------------------------------------
# Frozen schedule (protocol sections 2 and 3).
# --------------------------------------------------------------------------

CUTOFFS = (1, 2, 3, 4, 5)                                   # doubled spins 2J
COUPLINGS = (Fraction(1, 4), Fraction(1), Fraction(4), Fraction(16))
BOUNDARY_ANGLES = tuple(Fraction(k, 8) for k in range(9))   # theta / pi
TANGENT_ANGLES = (Fraction(1, 4), Fraction(1, 2), Fraction(3, 4))
SCORE_CUTOFF_OFFSETS = (1, 2)                               # J_s = J + 1/2, J + 1
TARGET_RATE = 1.0e-3
COLLAPSE_FACTOR = 4.0
PROJECTED_RESIDUAL_MAX = 1.0e-10
FULL_RESIDUAL_MAX = 1.0e-2
STABILITY_RELATIVE = 1.0e-6
STABILITY_ABSOLUTE = 1.0e-10
CENTERED_SCORE_MAX = 1.0e-9
GALERKIN_POISSON_MAX = 1.0e-8
RANK_TOLERANCE = 1.0e-10

BLOCK_LINKS = (0, 1, 2, 3)
EXTERIOR_LINKS = (4, 5, 6)
ALL_LINKS = tuple(range(7))

LINK_TAILS = (0, 1, 3, 0, 1, 4, 0)
LINK_HEADS = (1, 2, 2, 3, 5, 5, 4)
PLAQUETTES = (
    ((0, +1), (1, +1), (2, -1), (3, -1)),
    ((0, +1), (4, +1), (5, -1), (6, -1)),
)


# --------------------------------------------------------------------------
# Exact SU(2) representation data.
# --------------------------------------------------------------------------


def spin_rational(n2: int) -> sp.Rational:
    return sp.Rational(n2, 2)


def casimir(n2: int) -> float:
    j = n2 / 2.0
    return j * (j + 1.0)


def magnetic_values(n2: int) -> np.ndarray:
    return np.arange(-n2, n2 + 1, 2, dtype=np.int64)


def _wigner_3j_value(n2a: int, n2b: int, n2c: int, ma: int, mb: int, mc: int) -> float:
    """Racah formula for ``3j(j_a j_b j_c; m_a m_b m_c)`` in doubled-spin units.

    Selection rules are applied exactly, so structural zeros stay exactly zero.
    All factorials are of half-integers; ``lnfac2(x) = log((x/2)!)`` takes the
    doubled argument, so every argument below is even by the selection rules.
    """

    if ma + mb + mc != 0 or (n2a + n2b + n2c) % 2:
        return 0.0
    if abs(ma) > n2a or abs(mb) > n2b or abs(mc) > n2c:
        return 0.0
    if n2c > n2a + n2b or n2c < abs(n2a - n2b):
        return 0.0

    def lnfac2(k: int) -> float:
        return math.lgamma(0.5 * k + 1.0)

    t1, t2, t3 = n2a + n2b - n2c, n2a - n2b + n2c, -n2a + n2b + n2c
    # doubled arguments of the two k-dependent factorials
    low = n2c - n2b + ma
    high = n2c - n2a - mb
    k_min = max(0, -(low // 2), -(high // 2))
    k_max = min(t1 // 2, (n2a - ma) // 2, (n2b + mb) // 2)
    if k_max < k_min:
        return 0.0

    log_delta = 0.5 * (lnfac2(t1) + lnfac2(t2) + lnfac2(t3) - lnfac2(n2a + n2b + n2c + 2))
    log_norm = 0.5 * (
        lnfac2(n2a + ma) + lnfac2(n2a - ma) + lnfac2(n2b + mb)
        + lnfac2(n2b - mb) + lnfac2(n2c + mc) + lnfac2(n2c - mc)
    )
    sign = -1.0 if ((n2a - n2b - mc) // 2) % 2 else 1.0

    terms = []
    for k in range(k_min, k_max + 1):
        log_term = -(
            math.lgamma(k + 1.0) + lnfac2(t1 - 2 * k) + lnfac2(n2a - ma - 2 * k)
            + lnfac2(n2b + mb - 2 * k) + lnfac2(low + 2 * k) + lnfac2(high + 2 * k)
        )
        terms.append((1.0 if k % 2 == 0 else -1.0) * math.exp(log_term))
    return sign * math.exp(log_delta + log_norm) * math.fsum(terms)


_W3J: dict[tuple[int, int, int], np.ndarray] = {}
_W3J_SYMPY: dict[tuple[int, int, int], np.ndarray] = {}


def three_j(n2a: int, n2b: int, n2c: int, backend: str = "fast") -> np.ndarray:
    """``3j`` table over the magnetic indices of ``(n2a, n2b, n2c)``.

    ``backend='sympy'`` is the validation oracle (exact rationals, slow).
    """

    cache = _W3J if backend == "fast" else _W3J_SYMPY
    key = (n2a, n2b, n2c)
    cached = cache.get(key)
    if cached is not None:
        return cached
    out = np.zeros((n2a + 1, n2b + 1, n2c + 1), dtype=np.float64)
    if backend == "fast":
        for i, ka in enumerate(magnetic_values(n2a)):
            for j, kb in enumerate(magnetic_values(n2b)):
                kc = -int(ka) - int(kb)
                if abs(kc) > n2c:
                    continue
                out[i, j, (kc + n2c) // 2] = _wigner_3j_value(n2a, n2b, n2c, int(ka), int(kb), kc)
    else:
        ja, jb, jc = (spin_rational(n) for n in key)
        for i, ka in enumerate(magnetic_values(n2a)):
            ma = sp.Rational(int(ka), 2)
            for j, kb in enumerate(magnetic_values(n2b)):
                mb = sp.Rational(int(kb), 2)
                kc = -int(ka) - int(kb)
                if abs(kc) > n2c:
                    continue
                out[i, j, (kc + n2c) // 2] = float(
                    sp.N(wigner_3j(ja, jb, jc, ma, mb, sp.Rational(kc, 2)), 40)
                )
    cache[key] = out
    return out


_CG: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}


def cg_fusion(n2a: int, n2b: int) -> tuple[np.ndarray, np.ndarray]:
    """Clebsch-Gordan tensor over ``((ma),(mb),(M,J))``:

        C^{JM}_{j_a m_a, j_b m_b} = (-1)^{j_a - j_b + M} sqrt(2J+1)
                                    * 3j(j_a j_b J; m_a m_b -M),

    so that ``D^{ja}_{ma na} D^{jb}_{mb nb} =
    sum_{J M M'} C^{JM} C^{JM'} D^J_{M M'}`` with no extra weights.
    """

    key = (n2a, n2b)
    cached = _CG.get(key)
    if cached is not None:
        return cached
    spins = tuple(range(abs(n2a - n2b), n2a + n2b + 1, 2))
    block = (
        np.concatenate([magnetic_values(n) for n in spins])
        if spins
        else np.zeros(0, dtype=np.int64)
    )
    table = np.zeros((n2a + 1, n2b + 1, block.size), dtype=np.float64)
    jblock = np.zeros(block.size, dtype=np.int64)
    offsets: list[int] = []
    offset = 0
    for n2j in spins:
        offsets.append(offset)
        jblock[offset:offset + n2j + 1] = n2j
        offset += n2j + 1
    for i, ka in enumerate(magnetic_values(n2a)):
        for j, kb in enumerate(magnetic_values(n2b)):
            ksum = int(ka) + int(kb)
            exponent = (n2a - n2b + ksum) // 2
            sign = -1.0 if exponent % 2 else 1.0
            for offset, n2j in zip(offsets, spins):
                if abs(ksum) > n2j:
                    continue
                value = three_j(n2a, n2b, n2j)[i, j, (n2j - ksum) // 2]
                if value == 0.0:
                    continue
                table[i, j, offset + (ksum + n2j) // 2] = sign * math.sqrt(n2j + 1) * value
    _CG[key] = (table, jblock)
    return table, jblock


def metric_tensor(n2: int) -> np.ndarray:
    """Invariant bilinear form ``g[m, n] = (-1)^{j-m} delta_{m,-n}``."""

    k = magnetic_values(n2)
    out = np.zeros((k.size, k.size), dtype=np.float64)
    j = spin_rational(n2)
    for i, ka in enumerate(k):
        m = sp.Rational(int(ka), 2)
        out[i, (-int(ka) + n2) // 2] = float(sp.N((-1) ** (j - m), 40))
    return out


def conjugate_sign(n2: int) -> np.ndarray:
    k = magnetic_values(n2)
    return np.exp(1j * np.pi * (k[:, None] - k[None, :]) / 2.0)


def negation_tensor(n2: int) -> np.ndarray:
    k = magnetic_values(n2)
    out = np.zeros((k.size, k.size, k.size, k.size), dtype=np.float64)
    for i, ka in enumerate(k):
        i2 = (-int(ka) + n2) // 2
        for j, kb in enumerate(k):
            j2 = (-int(kb) + n2) // 2
            out[i2, j2, i, j] = 1.0
    return out


_REP_CACHE: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}


def rep_matrices(n2: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cached = _REP_CACHE.get(n2)
    if cached is not None:
        return cached
    j = n2 / 2.0
    m = magnetic_values(n2) / 2.0
    jz = np.diag(m).astype(complex)
    jp = np.zeros((n2 + 1, n2 + 1), dtype=complex)
    for i in range(n2):
        jp[i + 1, i] = math.sqrt((j - m[i]) * (j + m[i] + 1.0))
    jm = jp.conj().T
    jx = 0.5 * (jp + jm)
    jy = (jp - jm) / 2.0j
    _REP_CACHE[n2] = (jx, jy, jz)
    return jx, jy, jz


def generator_matrix(n2: int, component: int) -> np.ndarray:
    """``T^A`` (A = 0,1,2 for x,y,z) in the m-basis of spin ``n2/2``.

    The left generator ``X^A`` acts on link matrix elements as
    ``X^A D^j_{mn}(U) = sum_{m'} (T^A)_{m m'} D^j_{m'n}(U)``.
    """

    return rep_matrices(n2)[component].copy()


def rep_matrix(n2: int, group_element: np.ndarray) -> np.ndarray:
    """``D^j(U)`` for a defining-representation element ``U``."""

    from scipy.linalg import expm

    trace = float(np.real(np.trace(group_element)))
    cos_half = min(1.0, max(-1.0, trace / 2.0))
    angle = 2.0 * math.acos(cos_half)
    if abs(math.sin(angle / 2.0)) < 1e-15:
        return ((-1) ** n2 if cos_half < 0 else 1) * np.eye(n2 + 1, dtype=complex)
    half = math.sin(angle / 2.0)
    axis = np.array(
        [
            group_element[0, 1].imag / half,
            group_element[0, 1].real / half,
            (group_element[0, 0] - group_element[1, 1]).imag / (2.0 * half),
        ]
    )
    jx, jy, jz = rep_matrices(n2)
    return expm(1j * angle * (axis[0] * jx + axis[1] * jy + axis[2] * jz))


def z_rotation_matrix(n2: int, angle: float, derivative: int = 0) -> np.ndarray:
    """``D^j(exp(i angle sigma_3/2)) = diag(exp(i m angle))`` and derivatives."""

    m = magnetic_values(n2) / 2.0
    if derivative == 0:
        return np.diag(np.exp(1j * m * angle)).astype(complex)
    if derivative == 1:
        return np.diag(1j * m * np.exp(1j * m * angle)).astype(complex)
    raise ValueError(derivative)


# --------------------------------------------------------------------------
# Axis labels and tensor networks.
# --------------------------------------------------------------------------


class Label:
    """Tensor axis label carrying a spin decomposition (block index)."""

    __slots__ = ("name", "spins", "offsets", "size")

    def __init__(self, name: str, spins: Sequence[int]) -> None:
        self.name = name
        self.spins = tuple(int(s) for s in spins)
        offsets = []
        total = 0
        for s in self.spins:
            offsets.append(total)
            total += s + 1
        self.offsets = tuple(offsets)
        self.size = total

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Label({self.name})"


def _identity_builder(spin: int) -> np.ndarray:
    return np.eye(spin + 1)


def block_diagonal(label: Label, builder: Callable[[int], np.ndarray]) -> np.ndarray:
    out = np.zeros((label.size, label.size), dtype=complex)
    for spin, offset in zip(label.spins, label.offsets):
        out[offset:offset + spin + 1, offset:offset + spin + 1] = builder(spin)
    return out


def block_negation(label: Label) -> np.ndarray:
    out = np.zeros((label.size, label.size, label.size, label.size), dtype=float)
    for spin, offset in zip(label.spins, label.offsets):
        sl = slice(offset, offset + spin + 1)
        out[sl, sl, sl, sl] = negation_tensor(spin)
    return out


def block_conjugate_sign(label: Label) -> np.ndarray:
    return block_diagonal(label, conjugate_sign)


def block_conjugation(label: Label) -> np.ndarray:
    """Single node implementing ``conj(D^j_{mn}) = (-1)^{m-n} D^j_{-m,-n}``.

    Combining the index negation and the Condon-Shortley sign into one tensor
    keeps every label in exactly two nodes, so pairwise contraction never
    strands a shared index.
    """

    negated = block_negation(label)
    sign = block_conjugate_sign(label)
    return negated * sign[None, None, :, :]


class Network:
    """Symmetric contraction network with a cached contraction plan.

    The node construction order is deterministic for a fixed assembly routine,
    so plans keyed by the axis-name signature are shared across evaluations.
    """

    def __init__(self) -> None:
        self.nodes: list[tuple[np.ndarray, tuple[Label, ...]]] = []
        self._counter = 0

    def fresh(self, tag: str) -> str:
        self._counter += 1
        return f"{tag}{self._counter}"

    def label(self, tag: str, spins: Sequence[int]) -> Label:
        return Label(self.fresh(tag), spins)

    def add(self, array: np.ndarray, axes: Sequence[Label]) -> None:
        array = np.asarray(array)
        expected = tuple(ax.size for ax in axes)
        if array.shape != expected:
            raise ValueError(f"node shape {array.shape} != axes {expected}")
        self.nodes.append((array, tuple(axes)))

    def contract(self, open_axes: Sequence[Label] = ()) -> Any:
        """Contract the network; ``open_axes`` are kept (canonically ordered) instead of summed."""

        open_names = frozenset(ax.name for ax in open_axes)
        ownership: dict[str, tuple[int, int]] = {}
        for _, axes in self.nodes:
            if len({axis.name for axis in axes}) != len(axes):
                raise ValueError("an axis cannot occur twice in one network node")
            for axis in axes:
                count, size = ownership.get(axis.name, (0, axis.size))
                if size != axis.size:
                    raise ValueError(f"inconsistent axis size: {axis.name}")
                ownership[axis.name] = (count + 1, size)
        if any(count != (1 if name in open_names else 2) for name, (count, _) in ownership.items()):
            raise ValueError("every contracted axis must join exactly two nodes")
        result: Any = None
        pieces: list[tuple[np.ndarray, tuple[Label, ...]]] = []
        for component in _components(self.nodes):
            # axis *sizes* are part of the key: identical axis names are reused across
            # spin configurations, and a plan built for small blocks is disastrous for large ones.
            key = (
                tuple(
                    tuple((ax.name, ax.size) for ax in self.nodes[index][1])
                    for index in component
                ),
                tuple((ax.name, ax.size) for ax in open_axes),
            )
            cached = _PLAN_CACHE.get(key)
            if cached is None:
                cached = _build_plan([self.nodes[index] for index in component], open_names)
                _PLAN_CACHE[key] = cached
            steps, final_index, remaining = cached
            store: dict[int, tuple[np.ndarray, tuple[Label, ...]]] = {
                local: (np.asarray(self.nodes[global_index][0]), ())
                for local, global_index in enumerate(component)
            }
            for i, j, out_index, spec, merged_axes in steps:
                left = store.pop(i)
                right = store.pop(j)
                store[out_index] = (
                    np.einsum(spec, left[0], right[0], optimize=True),
                    merged_axes,
                )
            if len(store) != 1:
                raise ValueError("contraction plan left a partial network")
            array = np.asarray(store[final_index][0])
            component_open = tuple(ax for ax in open_axes if ax.name in {b.name for b in remaining})
            if remaining and not component_open:
                raise ValueError("component has uncontracted axes")
            if remaining:
                letters = _letter_map(remaining)
                spec = "".join(letters[ax.name] for ax in remaining) + "->"
                spec += "".join(letters[ax.name] for ax in component_open)
                array = np.einsum(spec, array)
            if open_axes:
                pieces.append((array, component_open))
                continue
            scalar = complex(array.reshape(()))
            result = scalar if result is None else result * scalar
        if open_axes:
            return _combine_pieces(pieces, open_axes)
        return result


def _combine_pieces(
    pieces: Sequence[tuple[np.ndarray, tuple[Label, ...]]],
    open_axes: Sequence[Label],
) -> np.ndarray:
    """Outer-product the per-component tensors into one tensor over ``open_axes``.

    Disjoint components carry disjoint open axes, so the total contraction is an
    outer product ordered exactly as requested.
    """

    position = {ax.name: index for index, ax in enumerate(open_axes)}
    total = np.ones((), dtype=complex)
    slots: list[int] = []
    for array, axes in pieces:
        if not axes:
            total = total * complex(np.asarray(array).reshape(()))
            continue
        order = [position[ax.name] for ax in axes]
        perm = np.argsort(order)
        permuted = np.transpose(array, perm)
        sorted_axes = [axes[index] for index in perm]
        expected = tuple(ax.size for ax in sorted_axes)
        if permuted.shape != expected:
            raise ValueError(f"component tensor shape {permuted.shape} != {expected}")
        total = np.multiply.outer(total, permuted)
        slots.extend(sorted(order))
    if len(slots) != len(open_axes):
        raise ValueError("open axes are not covered by the contracted components")
    return np.transpose(total, np.argsort(slots)).reshape([ax.size for ax in open_axes])


def _components(nodes: Sequence[tuple[np.ndarray, tuple[Label, ...]]]) -> list[list[int]]:
    """Group node indices into connected components sharing at least one axis."""

    parent = list(range(len(nodes)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owners: dict[str, int] = {}
    for index, (_, axes) in enumerate(nodes):
        for ax in axes:
            previous = owners.setdefault(ax.name, index)
            if previous != index:
                a, b = find(previous), find(index)
                if a != b:
                    parent[b] = a
    groups: dict[int, list[int]] = {}
    for index in range(len(nodes)):
        groups.setdefault(find(index), []).append(index)
    return list(groups.values())


_PLAN_CACHE: dict[
    tuple,
    tuple[list[tuple[int, int, int, str, tuple[Label, ...]]], int, tuple[Label, ...]],
] = {}


_ALPHABET = string.ascii_letters


def _letter_map(axes: Sequence[Label]) -> dict[str, str]:
    letters: dict[str, str] = {}
    for ax in axes:
        if ax.name not in letters:
            if len(letters) >= len(_ALPHABET):
                raise ValueError("contraction needs more than 52 distinct axes")
            letters[ax.name] = _ALPHABET[len(letters)]
    return letters


def _plan_step_spec(axes_i: Sequence[Label], axes_j: Sequence[Label]) -> tuple[tuple[Label, ...], str]:
    """Return the kept axes and the einsum spec for one pairwise contraction."""

    names_j = {ax.name for ax in axes_j}
    names_i = {ax.name for ax in axes_i}
    keep_i = [ax for ax in axes_i if ax.name not in names_j]
    keep_j = [ax for ax in axes_j if ax.name not in names_i]
    labels = keep_i + keep_j
    letters = _letter_map(list(axes_i) + list(axes_j))
    spec = "".join(letters[ax.name] for ax in axes_i)
    spec += "," + "".join(letters[ax.name] for ax in axes_j)
    spec += "->" + "".join(letters[ax.name] for ax in labels)
    return tuple(labels), spec


def _build_plan(
    nodes: Sequence[tuple[np.ndarray, tuple[Label, ...]]],
    open_names: frozenset[str] = frozenset(),
) -> tuple[list[tuple[int, int, int, str, tuple[Label, ...]]], int, tuple[Label, ...]]:
    entries = [(index, tuple(axes)) for index, (_, axes) in enumerate(nodes)]
    steps: list[tuple[int, int, int, str, tuple[Label, ...]]] = []
    counter = len(entries)
    while len(entries) > 1:
        best = None
        best_key = None
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                names_i = {ax.name for ax in entries[i][1]}
                if not any(ax.name in names_i for ax in entries[j][1]):
                    continue
                size = _planned_size(entries[i][1], entries[j][1], open_names)
                merged, _ = _plan_step_spec(entries[i][1], entries[j][1])
                key = (size, len(merged))
                if best_key is None or key < best_key:
                    best_key = key
                    best = (i, j)
        if best is None:
            raise ValueError("network is disconnected")
        i, j = best
        merged, spec = _plan_step_spec(entries[i][1], entries[j][1])
        steps.append((entries[i][0], entries[j][0], counter, spec, merged))
        entries = [entry for index, entry in enumerate(entries) if index not in (i, j)]
        entries.append((counter, merged))
        counter += 1
    final_index, remaining = entries[0]
    leftover = [ax for ax in remaining if ax.name not in open_names]
    if leftover:
        raise ValueError(f"uncontracted axes: {[ax.name for ax in leftover]}")
    return steps, final_index, tuple(remaining)


def _planned_size(axes_i: Sequence[Label], axes_j: Sequence[Label], open_names: frozenset[str]) -> int:
    names_i = {ax.name for ax in axes_i}
    names_j = {ax.name for ax in axes_j}
    size = 1
    for ax in axes_i:
        if ax.name not in names_j or ax.name in open_names:
            size *= ax.size
    for ax in axes_j:
        if ax.name not in names_i or ax.name in open_names:
            size *= ax.size
    for ax in axes_i:
        if ax.name in names_j and ax.name not in open_names:
            size *= ax.size
    return size


# --------------------------------------------------------------------------
# Link integration through the Clebsch-Gordan series.
# --------------------------------------------------------------------------


def fusion_node(net: Network, a: Label, b: Label, out: Label, tag: str) -> None:
    table = np.zeros((a.size, b.size, out.size), dtype=np.float64)
    for n2a, off_a in zip(a.spins, a.offsets):
        for n2b, off_b in zip(b.spins, b.offsets):
            cg, jblock = cg_fusion(n2a, n2b)
            for n2j, off_out in zip(out.spins, out.offsets):
                positions = np.where(jblock == n2j)[0]
                if positions.size == 0:
                    continue
                table[off_a:off_a + n2a + 1, off_b:off_b + n2b + 1, off_out:off_out + n2j + 1] = cg[:, :, positions]
    net.add(table, (a, b, out))


def conjugate_factor(net: Network, m_axis: Label, n_axis: Label, tag: str) -> tuple[Label, Label]:
    """Replace a factor by its conjugate: ``conj(D^j_{mn}) = (-1)^{m-n} D^j_{-m,-n}``."""

    m_new = net.label(f"{tag}cM", m_axis.spins)
    n_new = net.label(f"{tag}cN", n_axis.spins)
    net.add(block_conjugation(m_axis), (m_new, n_new, m_axis, n_axis))
    return m_new, n_new


def channel_fusion_node(
    net: Network,
    cur: Label,
    nxt: Label,
    out: Label,
    channel: Label,
    tag: str,
    keys: Sequence[tuple[int, int, int]] | None = None,
) -> None:
    """Fuse ``cur`` with ``nxt`` into ``out``, recording which blocks produced which spin.

    ``keys`` lists ``(cur block index, next block index, output spin)`` triples; the
    ``channel`` axis has one value per key and is shared between the two
    Clebsch-Gordan chains of a link integral.  Sharing the *whole* block choice (not
    just the output spin) is what keeps direct-sum labels block diagonal on both
    chains; a key with no Clebsch-Gordan partner simply leaves a zero slice.
    """

    if keys is None:
        keys = [
            (k, l, n2j)
            for k, n2a in enumerate(cur.spins)
            for l, n2b in enumerate(nxt.spins)
            for n2j in range(abs(n2a - n2b), n2a + n2b + 1, 2)
        ]
    keys = tuple(keys)
    if channel.size != len(keys):
        raise ValueError(f"channel axis size {channel.size} != {len(keys)} block keys")
    table = np.zeros((cur.size, nxt.size, out.size, channel.size), dtype=np.float64)
    for index, (k, l, n2j) in enumerate(keys):
        off_a = cur.offsets[k]
        off_b = nxt.offsets[l]
        n2a = cur.spins[k]
        n2b = nxt.spins[l]
        cg, jblock = cg_fusion(n2a, n2b)
        positions = np.where(jblock == n2j)[0]
        if positions.size == 0:
            continue
        for n2o, off_o in zip(out.spins, out.offsets):
            if n2o != n2j:
                continue
            table[off_a:off_a + n2a + 1, off_b:off_b + n2b + 1,
                  off_o:off_o + n2o + 1, index] = cg[:, :, positions]
    net.add(table, (cur, nxt, out, channel))


def link_integral(net: Network, factors: Sequence[tuple[Label, Label, bool]], tag: str) -> None:
    """Insert ``int dU prod_k F_k(U)``; ``factors`` are ``(m, n, conjugated)``.

    The two Clebsch-Gordan chains of every fusion share one channel axis, so the series
    sums over a common intermediate spin; the vertex tensors and metrics that bracket
    each link in the assembled network carry the factor's block structure.
    """

    plain: list[tuple[Label, Label]] = []
    for index, (m_axis, n_axis, conjugated) in enumerate(factors):
        if conjugated:
            # block_conjugation is block diagonal in all four indices, so the conjugate
            # keeps the factor's representation blocks tied without an extra node
            plain.append(conjugate_factor(net, m_axis, n_axis, f"{tag}f{index}"))
        else:
            plain.append((m_axis, n_axis))

    if len(plain) == 1:
        raise ValueError("single-factor links are not integrated in this study")

    def side_tags(side: str, index: int) -> str:
        return f"{tag}{side}{index}"

    current_m, current_n = plain[0]
    for index in range(1, len(plain)):
        next_m, next_n = plain[index]
        last = index == len(plain) - 1
        if last:
            # the enforced J = 0 output: every block pair gets exactly one channel value,
            # and a pair that cannot fuse to a singlet simply leaves a zero slice
            keys = [
                (k, l, 0)
                for k in range(len(current_m.spins))
                for l in range(len(next_m.spins))
            ]
        else:
            keys = [
                (k, l, n2j)
                for k, n2a in enumerate(current_m.spins)
                for l, n2b in enumerate(next_m.spins)
                for n2j in range(abs(n2a - n2b), n2a + n2b + 1, 2)
            ]
        out_spins: tuple[int, ...] = (0,) if last else tuple(sorted({n2j for _, _, n2j in keys}))
        channel = net.label(f"{tag}J{index}", (0,) * len(keys))
        out_m = net.label(side_tags("m", index), out_spins)
        out_n = net.label(side_tags("n", index), out_spins)
        channel_fusion_node(net, current_m, next_m, out_m, channel, side_tags("m", index), keys)
        channel_fusion_node(net, current_n, next_n, out_n, channel, side_tags("n", index), keys)
        current_m, current_n = out_m, out_n
    # the enforced J = 0 output carries a trivial one-dimensional leg
    net.add(np.ones(1, dtype=float), (current_m,))
    net.add(np.ones(1, dtype=float), (current_n,))


# --------------------------------------------------------------------------
# Basis states and wavefunction copies.
# --------------------------------------------------------------------------


def valid_triple(n2a: int, n2b: int, n2c: int) -> bool:
    if (n2a + n2b + n2c) % 2 != 0:
        return False
    return abs(n2a - n2b) <= n2c <= n2a + n2b


def basis_states(cutoff: int) -> list[tuple[int, int, int]]:
    return [
        (n2a, n2b, n2c)
        for n2a in range(0, cutoff + 1)
        for n2b in range(0, cutoff + 1)
        for n2c in range(0, cutoff + 1)
        if valid_triple(n2a, n2b, n2c)
    ]


def state_leg_spins(state: tuple[int, int, int]) -> dict[int, int]:
    n2a, n2b, n2c = state
    return {0: n2a, 1: n2b, 2: n2b, 3: n2b, 4: n2c, 5: n2c, 6: n2c}


class Copy:
    """Vertex tensors, two-valent chain nodes and per-link factors of one copy."""

    def __init__(self, net: Network, a_spins: Sequence[int], b_spins: Sequence[int], c_spins: Sequence[int], prefix: str) -> None:
        self.net = net
        self.prefix = prefix
        self.overrides: dict[int, Label] = {}
        self.la_m = net.label(f"{prefix}am", a_spins)
        self.la_n = net.label(f"{prefix}an", a_spins)
        self.lb_m = {link: net.label(f"{prefix}b{link}m", b_spins) for link in (1, 2, 3)}
        self.lb_n = {link: net.label(f"{prefix}b{link}n", b_spins) for link in (1, 2, 3)}
        self.lc_m = {link: net.label(f"{prefix}c{link}m", c_spins) for link in (4, 5, 6)}
        self.lc_n = {link: net.label(f"{prefix}c{link}n", c_spins) for link in (4, 5, 6)}

    def add_vertices(self, tensor0: np.ndarray, tensor1: np.ndarray) -> None:
        net = self.net
        net.add(tensor0, (self.la_m, self.lb_m[3], self.lc_m[6]))
        # Link 0 arrives at vertex 1; convert its dual index before the all-outgoing 3j.
        tensor1 = np.einsum("ij,jkl->ikl", block_diagonal(self.la_n, metric_tensor), tensor1)
        net.add(tensor1, (self.la_n, self.lb_m[1], self.lc_m[4]))
        net.add(block_diagonal(self.lb_m[1], metric_tensor), (self.lb_n[1], self.lb_n[2]))
        net.add(block_diagonal(self.lb_m[1], _identity_builder), (self.lb_m[2], self.lb_n[3]))
        net.add(block_diagonal(self.lc_m[4], _identity_builder), (self.lc_m[5], self.lc_n[6]))
        net.add(block_diagonal(self.lc_m[4], metric_tensor), (self.lc_n[4], self.lc_n[5]))

    def add_generator(self, link: int, component: int, conjugated: bool = False) -> None:
        m_axis, _ = self.factors()[link]
        table = np.zeros((m_axis.size, m_axis.size), dtype=complex)
        for spin, offset in zip(m_axis.spins, m_axis.offsets):
            generator = 1j * generator_matrix(spin, component)
            table[offset:offset + spin + 1, offset:offset + spin + 1] = (
                np.conj(generator.T) if conjugated else generator.T
            )
        new_axis = self.net.label(f"{self.prefix}g{link}", m_axis.spins)
        self.net.add(table, (new_axis, m_axis))
        self.overrides[link] = new_axis

    def factors(self) -> dict[int, tuple[Label, Label]]:
        raw = {
            0: (self.la_m, self.la_n),
            1: (self.lb_m[1], self.lb_n[1]),
            2: (self.lb_m[2], self.lb_n[2]),
            3: (self.lb_m[3], self.lb_n[3]),
            4: (self.lc_m[4], self.lc_n[4]),
            5: (self.lc_m[5], self.lc_n[5]),
            6: (self.lc_m[6], self.lc_n[6]),
        }
        return {link: (self.overrides.get(link, pair[0]), pair[1]) for link, pair in raw.items()}


def add_simple_copy(net: Network, state: tuple[int, int, int], prefix: str) -> Copy:
    n2a, n2b, n2c = state
    copy = Copy(net, (n2a,), (n2b,), (n2c,), prefix)
    tensor = three_j(n2a, n2b, n2c)
    copy.add_vertices(tensor, tensor)
    return copy


def omega_block_tensors(
    coefficients: dict[tuple[int, int, int], float],
) -> tuple[np.ndarray, np.ndarray, tuple[int, ...]]:
    """Fold a Ritz vector into block vertex tensors over the declared cutoff."""

    spins = tuple(sorted({n2 for state in coefficients for n2 in state}))
    offsets: list[list[int]] = []
    sizes: list[int] = []
    for _ in range(3):
        running = 0
        local: list[int] = []
        for s in spins:
            local.append(running)
            running += s + 1
        offsets.append(local)
        sizes.append(running)
    tensor0 = np.zeros(tuple(sizes), dtype=np.float64)
    tensor1 = np.zeros(tuple(sizes), dtype=np.float64)
    for (n2a, n2b, n2c), coefficient in coefficients.items():
        if coefficient == 0.0:
            continue
        block = three_j(n2a, n2b, n2c)
        i_a = offsets[0][spins.index(n2a)]
        i_b = offsets[1][spins.index(n2b)]
        i_c = offsets[2][spins.index(n2c)]
        sl = (slice(i_a, i_a + n2a + 1), slice(i_b, i_b + n2b + 1), slice(i_c, i_c + n2c + 1))
        tensor0[sl] = coefficient * block
        tensor1[sl] = block
    return tensor0, tensor1, spins


def add_omega_copy(
    net: Network,
    coefficients: dict[tuple[int, int, int], float],
    prefix: str,
) -> Copy:
    tensor0, tensor1, spins = omega_block_tensors(coefficients)
    copy = Copy(net, spins, spins, spins, prefix)
    copy.add_vertices(tensor0, tensor1)
    return copy


# --------------------------------------------------------------------------
# Generic network assembly: copies, generator insertions, fixed links.
# --------------------------------------------------------------------------


class CopySpec:
    __slots__ = ("kind", "state", "conjugated", "derivative", "generator", "generator_links")

    def __init__(
        self,
        kind: str,
        state: tuple[int, int, int] | None = None,
        conjugated: bool = False,
        derivative: bool = False,
        generator: int | None = None,
        generator_links: Sequence[int] = BLOCK_LINKS,
    ) -> None:
        self.kind = kind
        self.state = state
        self.conjugated = conjugated
        self.derivative = derivative
        self.generator = generator
        self.generator_links = tuple(generator_links)


def assemble_integral(
    coefficients: dict[tuple[int, int, int], float],
    specs: Sequence[CopySpec],
    integrated: Sequence[int],
    fixed: dict[int, tuple[Callable[[int], np.ndarray], Callable[[int], np.ndarray]]] | None,
    loops: Sequence[int] = (),
    label: str = "I",
) -> complex:
    """Contract the product of copies, optional character loops, over links.

    Links in ``integrated`` are Haar-integrated through the Clebsch-Gordan
    series; every remaining link closes with the fixed matrix supplied in
    ``fixed`` (applied block-diagonally for block copies).  The derivative
    flag on a spec applies to link 4.
    """

    net = Network()
    copies: list[tuple[CopySpec, Copy]] = []
    for index, spec in enumerate(specs):
        prefix = f"{label}C{index}"
        if spec.kind == "omega":
            copy = add_omega_copy(net, coefficients, prefix)
        else:
            assert spec.state is not None
            copy = add_simple_copy(net, spec.state, prefix)
        if spec.generator is not None:
            for link in spec.generator_links:
                copy.add_generator(link, spec.generator, conjugated=spec.conjugated)
        copies.append((spec, copy))
    loop_factors: dict[int, list[tuple[Label, Label, bool]]] = {}
    for index, (plaquette, dagger) in enumerate(normalise_loop_specs(loops)):
        tagged = _plaquette_loop_factors(net, plaquette, f"{label}P{plaquette}i{index}", dagger)
        for link, factor in tagged.items():
            loop_factors.setdefault(link, []).append(factor)
    integrated_set = set(integrated)
    for link in ALL_LINKS:
        factors: list[tuple[Label, Label, bool]] = []
        for spec, copy in copies:
            m_axis, n_axis = copy.factors()[link]
            factors.append((m_axis, n_axis, spec.conjugated))
        factors.extend(loop_factors.get(link, ()))
        if link in integrated_set:
            link_integral(net, factors, f"{label}L{link}")
        else:
            assert fixed is not None, "fixed matrices required for exterior links"
            value_table, derivative_table = fixed[link]
            for index, (spec, copy) in enumerate(copies):
                m_axis, n_axis = copy.factors()[link]
                use_derivative = spec.derivative and link == 4
                builder = derivative_table if use_derivative else value_table
                if spec.conjugated:
                    builder = (lambda spin, base=builder: np.conj(base(spin)))
                table = block_diagonal(m_axis, builder)
                net.add(table, (m_axis, n_axis))
            for m_axis, n_axis, conjugated in loop_factors.get(link, ()):
                builder = value_table
                if conjugated:
                    builder = (lambda spin, base=builder: np.conj(base(spin)))
                net.add(block_diagonal(m_axis, builder), (m_axis, n_axis))
    return complex(net.contract())


def _plaquette_loop_factors(
    net: Network,
    plaquette: int,
    tag: str,
    dagger: bool = False,
) -> dict[int, tuple[Label, Label, bool]]:
    """Spin-1/2 factors for ``Tr U_p`` (``dagger`` for ``conj Tr U_p``).

    Returns link -> ``(m, n, conjugated)``; the dagger flips each conjugation
    flag while keeping the index order of the chain.
    """

    loop_labels = [net.label(f"{tag}l{index}", (1,)) for index in range(4)]
    factors: dict[int, tuple[Label, Label, bool]] = {}
    for position, (link, orientation) in enumerate(PLAQUETTES[plaquette]):
        first = loop_labels[position]
        second = loop_labels[(position + 1) % 4]
        if orientation > 0:
            pair = (first, second, False)
        else:
            pair = (second, first, True)
        factors[link] = (pair[0], pair[1], pair[2] != dagger)
    return factors


def normalise_loop_specs(loops: Sequence[Any]) -> list[tuple[int, bool]]:
    """Accept ``0``/``(0, True)``-style loop entries as ``(plaquette, dagger)``."""

    specs: list[tuple[int, bool]] = []
    for entry in loops:
        if isinstance(entry, (tuple, list)):
            plaquette, dagger = entry
            specs.append((int(plaquette), bool(dagger)))
        else:
            specs.append((int(entry), False))
    return specs


def boundary_tables(theta: float) -> dict[int, tuple[Callable[[int], np.ndarray], Callable[[int], np.ndarray]]]:
    """Fixed exterior data: link -> (value table, theta-derivative table)."""

    return {
        4: (
            lambda spin: z_rotation_matrix(spin, theta, 0),
            lambda spin: z_rotation_matrix(spin, theta, 1),
        ),
        5: (lambda spin: np.eye(spin + 1, dtype=complex), lambda spin: np.zeros((spin + 1, spin + 1), dtype=complex)),
        6: (lambda spin: np.eye(spin + 1, dtype=complex), lambda spin: np.zeros((spin + 1, spin + 1), dtype=complex)),
    }


# --------------------------------------------------------------------------
# Full-graph quantities.
# --------------------------------------------------------------------------


def state_norm_squared(state: tuple[int, int, int]) -> float:
    value = assemble_integral(
        {},
        [CopySpec("state", state), CopySpec("state", state, conjugated=True)],
        ALL_LINKS,
        None,
        label="N",
    )
    return float(np.real(value))


def state_overlap(
    left: tuple[int, int, int],
    right: tuple[int, int, int],
    loops: Sequence[int] = (),
) -> complex:
    return assemble_integral(
        {},
        [CopySpec("state", left, conjugated=True), CopySpec("state", right)],
        ALL_LINKS,
        None,
        loops=loops,
        label="Ov",
    )


def evaluate_state(state: tuple[int, int, int], matrices: dict[int, np.ndarray]) -> complex:
    fixed = {
        link: (
            (lambda spin, matrix=matrices[link]: _spin_checked(spin, matrix)),
            (lambda spin: np.zeros((spin + 1, spin + 1), dtype=complex)),
        )
        for link in matrices
    }
    return assemble_integral({}, [CopySpec("state", state)], (), fixed, label="E")


def _spin_checked(spin: int, matrix: np.ndarray) -> np.ndarray:
    if matrix.shape != (spin + 1, spin + 1):
        raise ValueError(f"fixed matrix shape {matrix.shape} does not match spin {spin}")
    return matrix


# --------------------------------------------------------------------------
# Hamiltonian (generalized basis) and Ritz spectrum.
# --------------------------------------------------------------------------


class SpectrumSpace:
    """Unnormalized spin-network basis with overlap, plus shared x-independent data."""

    def __init__(self, cutoff: int) -> None:
        self.cutoff = cutoff
        self.states = basis_states(cutoff)
        self.index = {state: position for position, state in enumerate(self.states)}
        n = len(self.states)
        # Haar orthogonality and normalized trivalent intertwiners.
        self.norms = np.array([1.0 / math.sqrt(math.prod(v + 1 for v in state)) for state in self.states])
        self.kinetic = np.array([sum(casimir(spin) for spin in state_leg_spins(state).values()) for state in self.states])
        self.plaquette_matrix = np.zeros((n, n), dtype=np.float64)
        for i, left in enumerate(self.states):
            for j, right in enumerate(self.states):
                value = 0j
                for plaquette, changed, spectator in ((0, (0, 1), 2), (1, (0, 2), 1)):
                    if left[spectator] == right[spectator] and all(
                        abs(left[axis] - right[axis]) == 1 for axis in changed
                    ):
                        value += state_overlap(left, right, loops=(plaquette,))
                if abs(value.imag) > 1.0e-9:
                    raise ValueError(f"plaquette element imaginary part {value.imag} at {left},{right}")
                self.plaquette_matrix[i, j] = float(np.real(value))
        self.hermiticity_residual = float(np.max(np.abs(self.plaquette_matrix - self.plaquette_matrix.T)))
        if self.hermiticity_residual > 1.0e-10:
            raise ValueError(f"plaquette matrix fails Hermiticity: {self.hermiticity_residual}")

    @property
    def overlap(self) -> np.ndarray:
        return np.diag(self.norms ** 2)

    def hamiltonian(self, coupling: Fraction) -> np.ndarray:
        x = float(coupling)
        matrix = np.diag((self.kinetic + 4.0 * x) * (self.norms ** 2)) - x * self.plaquette_matrix
        return matrix


def ritz_row(
    space: SpectrumSpace,
    coupling: Fraction,
    extended: SpectrumSpace | None,
) -> dict[str, Any]:
    from scipy.linalg import eigh

    matrix = space.hamiltonian(coupling)
    overlap = space.overlap
    values, vectors = eigh(matrix, overlap)
    energy = float(values[0])
    vector = np.array(vectors[:, 0], dtype=np.float64)
    if vector[np.flatnonzero(np.abs(vector) > 1.0e-14)[0]] < 0:
        vector = -vector
    state_norm = math.sqrt(float(vector @ overlap @ vector))
    vector = vector / state_norm
    residual = (matrix - energy * overlap) @ vector
    r_proj = float(np.linalg.norm(residual / space.norms))
    record: dict[str, Any] = {
        "cutoff": space.cutoff,
        "coupling": str(coupling),
        "energy_ground": energy,
        "energy_first_excited": float(values[1]),
        "projected_residual": r_proj,
        "basis_dimension": len(space.states),
        "matrix_sha256": _array_hash(matrix),
        "overlap_sha256": _array_hash(overlap),
        "vector": vector.tolist(),
    }
    if extended is not None:
        index = extended.index
        embedded = np.zeros(len(extended.states))
        for position, state in enumerate(space.states):
            embedded[index[state]] = vector[position]
        ext_matrix = extended.hamiltonian(coupling)
        ext_overlap = extended.overlap
        full_residual = (ext_matrix - energy * ext_overlap) @ embedded
        r_full = float(np.linalg.norm(full_residual / extended.norms))
        record["full_residual"] = r_full
        record["extension_cutoff"] = extended.cutoff
    return record


def _array_hash(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


# --------------------------------------------------------------------------
# Conditional block machinery.
# --------------------------------------------------------------------------


def partition_function(coefficients: dict[tuple[int, int, int], float], theta: float) -> float:
    value = assemble_integral(
        coefficients,
        [CopySpec("omega"), CopySpec("omega", conjugated=True)],
        BLOCK_LINKS,
        boundary_tables(theta),
        label="Z",
    )
    return float(np.real(value))


def conditional_gram_block(
    coefficients: dict[tuple[int, int, int], float],
    theta: float,
    states_A: Sequence[tuple[int, int, int]],
    states_B: Sequence[tuple[int, int, int]],
    generator: int | None = None,
    generator_link: int | None = None,
) -> np.ndarray:
    """``G[i,j] = rho-integral of conj(A_i) B_j`` possibly with two insertions."""

    out = np.zeros((len(states_A), len(states_B)), dtype=complex)
    for i, left in enumerate(states_A):
        for j, right in enumerate(states_B):
            specs = [
                CopySpec("omega"),
                CopySpec("omega", conjugated=True),
                CopySpec(
                    "state",
                    left,
                    conjugated=True,
                    generator=generator,
                    generator_links=(generator_link,) if generator_link is not None else BLOCK_LINKS,
                ),
                CopySpec(
                    "state",
                    right,
                    generator=generator,
                    generator_links=(generator_link,) if generator_link is not None else BLOCK_LINKS,
                ),
            ]
            out[i, j] = assemble_integral(
                coefficients, specs, BLOCK_LINKS, boundary_tables(theta), label="Gb"
            )
    return out


def conditional_matrices(
    coefficients: dict[tuple[int, int, int], float],
    theta: float,
    cutoff: int,
) -> dict[str, Any]:
    """Exact representation-product moments of the declared restricted functions.

    The exterior edges form a forest. Gauge covariance and block Haar
    invariance identify every exterior assignment with the identity assignment.
    The gauge-summed Dirichlet form obeys the same identity. This is an
    integration identity; the Hamiltonian and retained test space are unchanged.
    """
    from yang_mills_conditional_algebra import conditional_data

    states = basis_states(cutoff)
    data = conditional_data(states, coefficients, theta)
    data["states"] = states
    data["restriction_gram"] = np.diag([
        1.0 / math.prod(v + 1 for v in state) for state in states
    ])
    return data


# --------------------------------------------------------------------------
# Retained fibre space and conditional rate.
# --------------------------------------------------------------------------


class FibreSpace:
    """Orthonormal basis of the restriction image minus the constant direction."""

    def __init__(self, gram: np.ndarray, states: Sequence[tuple[int, int, int]]) -> None:
        self.states = list(states)
        self.index = {state: position for position, state in enumerate(self.states)}
        values, vectors = np.linalg.eigh(gram)
        largest = float(np.max(np.abs(values)))
        keep = values > RANK_TOLERANCE * max(largest, 1.0)
        self.gram_eigenvalues = values
        self.gram_eigenvectors = vectors
        self.keep_indices = np.where(keep)[0]
        self.rank = int(len(self.keep_indices))
        self.map_to_vector = vectors[:, keep] / np.sqrt(values[keep])       # v = T y
        self.map_to_coordinates = np.sqrt(values[keep])[:, None] * np.conj(vectors[:, keep]).T  # y = M v
        vacuum = self.index[(0, 0, 0)]
        constant = self.map_to_coordinates[:, vacuum].astype(complex)
        norm = float(np.linalg.norm(constant))
        self.constant_coordinates = constant / norm if norm > 0 else np.zeros(self.rank, dtype=complex)
        projector = np.eye(self.rank, dtype=complex)
        if norm > 0:
            projector = projector - np.outer(self.constant_coordinates, np.conj(self.constant_coordinates))
        self.projector = projector
        u, s, _ = np.linalg.svd(projector, full_matrices=False)
        self.basis = u[:, s > 1.0e-8]
        self.removed_constant_dimension = 1 if norm > 0 else 0

    def to_coordinates(self, raw_vector: np.ndarray) -> np.ndarray:
        coordinates = self.map_to_coordinates @ raw_vector
        if self.removed_constant_dimension:
            coordinates = coordinates - self.constant_coordinates * np.vdot(self.constant_coordinates, coordinates)
        return self.basis.conj().T @ coordinates

    def transform(self, raw_matrix: np.ndarray) -> np.ndarray:
        transformed = self.map_to_vector.conj().T @ raw_matrix @ self.map_to_vector
        transformed = self.projector @ transformed @ self.projector
        return self.basis.conj().T @ transformed @ self.basis


def generalized_rate(dirichlet: np.ndarray, covariance: np.ndarray) -> dict[str, Any]:
    from scipy.linalg import eigh

    values, vectors = eigh(dirichlet, covariance)
    order = int(np.argmin(values))
    vector = vectors[:, order]
    rate = float(np.real(values[order]))
    residual = dirichlet @ vector - rate * (covariance @ vector)
    return {
        "rate": rate,
        "vector": vector,
        "eigenvalues": [float(np.real(v)) for v in values],
        "residual": float(np.linalg.norm(residual)),
    }


# --------------------------------------------------------------------------
# Validation checks recorded in the receipt.
# --------------------------------------------------------------------------


def validation_checks(max_cutoff: int) -> dict[str, Any]:
    """Physical positive controls and an independent exact-coefficient oracle."""
    from scipy.linalg import expm

    rng = np.random.default_rng(20260910)
    elements = []
    for k in range(8):
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        elements.append(expm(1j * (0.3 + 0.2 * k) * sum(
            axis[a] * rep_matrices(1)[a] for a in range(3)
        )))
    checks: dict[str, Any] = {}
    errors: dict[str, float] = {}
    limit = max_cutoff + 1  # includes the omitted-space residual's extension
    worst_oracle = 0.0
    table_count = 0
    for a in range(limit + 1):
        for b in range(limit + 1):
            for c in range(abs(a - b), a + b + 1, 2):
                worst_oracle = max(worst_oracle, float(np.max(np.abs(
                    three_j(a, b, c) - three_j(a, b, c, backend="sympy")
                ))))
                table_count += 1
    errors["wigner_sympy_oracle"] = worst_oracle
    checks["oracle_tables"] = table_count
    checks["oracle_max_output_doubled_spin"] = 2 * limit
    errors["wigner_forbidden_triple"] = max(float(np.max(np.abs(three_j(*s))))
                                            for s in ((1, 1, 1), (0, 1, 3), (2, 2, 6)))

    worst_series = 0.0
    for a, b in ((1, 1), (1, 2), (2, 3), (limit, limit)):
        da, db = rep_matrix(a, elements[0]), rep_matrix(b, elements[0])
        table, jblock = cg_fusion(a, b)
        block_matrix = np.zeros((jblock.size, jblock.size), dtype=complex)
        for c in range(abs(a - b), a + b + 1, 2):
            positions = np.flatnonzero(jblock == c)
            block_matrix[np.ix_(positions, positions)] = rep_matrix(c, elements[0])
        lhs = np.einsum("ab,cd->acbd", da, db)
        rhs = np.einsum("abp,cdq,pq->abcd", table, table, block_matrix, optimize=True)
        worst_series = max(worst_series, float(np.max(np.abs(lhs - rhs))))
    errors["cg_product"] = worst_series
    errors["central_element"] = max(float(np.max(np.abs(
        rep_matrix(s, -np.eye(2)) - (-1) ** s * np.eye(s + 1)
    ))) for s in range(limit + 1))
    errors["conjugation"] = max(float(np.max(np.abs(
        np.conj(rep_matrix(s, elements[0]))
        - conjugate_sign(s) * rep_matrix(s, elements[0])[::-1, ::-1]
    ))) for s in range(limit + 1))

    states = ((1, 1, 0), (1, 0, 1), (2, 1, 1), (2, 2, 2))
    worst_gauge = 0.0
    base_values = []
    for state in states:
        spins = state_leg_spins(state)
        base = {e: rep_matrix(spins[e], elements[e]) for e in ALL_LINKS}
        value = evaluate_state(state, base)
        base_values.append(abs(value))
        for vertex in range(6):
            transformed = {}
            for e, matrix in base.items():
                gauge = rep_matrix(spins[e], elements[7])
                if LINK_TAILS[e] == vertex:
                    matrix = gauge @ matrix
                if LINK_HEADS[e] == vertex:
                    matrix = matrix @ gauge.conj().T
                transformed[e] = matrix
            worst_gauge = max(worst_gauge, abs(evaluate_state(state, transformed) - value))
    errors["all_vertex_gauge"] = float(worst_gauge)
    checks["gauge_control_min_amplitude"] = min(base_values)
    errors["basis_norm"] = max(abs(state_norm_squared(s) - 1.0 / math.prod(v + 1 for v in s))
                               for s in ((0, 0, 0), *states))
    small = basis_states(min(2, max_cutoff))
    errors["orthogonality"] = max(
        abs(state_overlap(left, right))
        for i, left in enumerate(small) for right in small[i + 1:]
    )
    vacuum = (0, 0, 0)
    loop_values = []
    for p, state in ((0, (1, 1, 0)), (1, (1, 0, 1))):
        errors[f"vacuum_loop_p{p}"] = abs(state_overlap(vacuum, vacuum, loops=(p,)))
        errors[f"loop_norm_p{p}"] = abs(
            state_overlap(vacuum, vacuum, loops=((p, True), (p, False))) - 1.0
        )
        values = [state_overlap(left, right, loops=((p, dagger),))
                  for left, right in ((vacuum, state), (state, vacuum)) for dagger in (False, True)]
        errors[f"physical_loop_p{p}"] = max(abs(value + 0.5) for value in values)
        loop_values.append([float(value.real) for value in values])
    checks["physical_loop_values"] = loop_values

    # Superposition and derivatives are evaluated pointwise, without Haar averaging.
    coefficients = {vacuum: 0.7, (1, 1, 0): -0.3, (1, 0, 1): 0.2}
    fixed = {e: (lambda s, e=e: rep_matrix(s, elements[e]),
                 lambda s: np.zeros((s + 1, s + 1))) for e in ALL_LINKS}
    explicit = sum(c * assemble_integral({}, [CopySpec("state", s)], (), fixed)
                   for s, c in coefficients.items())
    errors["omega_linearity"] = abs(
        assemble_integral(coefficients, [CopySpec("omega")], (), fixed) - explicit
    )
    state = (2, 1, 1)
    spins = state_leg_spins(state)
    base = {e: rep_matrix(spins[e], elements[e]) for e in ALL_LINKS}
    step = 1.0e-5
    derivative_error = 0.0
    for component in range(3):
        for conjugated in (False, True):
            analytic = assemble_integral({}, [CopySpec(
                "state", state, conjugated=conjugated, generator=component, generator_links=(0,)
            )], (), fixed)
            plus, minus = dict(base), dict(base)
            generator = generator_matrix(spins[0], component)
            plus[0] = expm(1j * step * generator) @ base[0]
            minus[0] = expm(-1j * step * generator) @ base[0]
            finite = (evaluate_state(state, plus) - evaluate_state(state, minus)) / (2 * step)
            derivative_error = max(derivative_error, abs(analytic - (finite.conjugate() if conjugated else finite)))
    errors["left_generator_finite_difference"] = float(derivative_error)
    checks["errors"] = {name: float(value) for name, value in errors.items()}
    checks["passed"] = min(base_values) > 1.0e-6 and all(value < 1.0e-9 for value in errors.values())
    if not checks["passed"]:
        raise ArithmeticError(f"representation validation failed: {checks}")
    return checks


# --------------------------------------------------------------------------
# Receipt helpers.
# --------------------------------------------------------------------------


def graph_manifest() -> dict[str, Any]:
    return {
        "links": [
            {"index": link, "tail": LINK_TAILS[link], "head": LINK_HEADS[link]}
            for link in ALL_LINKS
        ],
        "plaquettes": [
            [{"link": link, "orientation": orientation} for link, orientation in word]
            for word in PLAQUETTES
        ],
        "block": list(BLOCK_LINKS),
        "exterior": list(EXTERIOR_LINKS),
    }


def schedule_manifest() -> dict[str, Any]:
    return {
        "cutoffs_doubled": list(CUTOFFS),
        "couplings": [str(value) for value in COUPLINGS],
        "boundary_angles_pi": [str(value) for value in BOUNDARY_ANGLES],
        "tangent_angles_pi": [str(value) for value in TANGENT_ANGLES],
        "score_cutoff_offsets": list(SCORE_CUTOFF_OFFSETS),
        "target_rate": TARGET_RATE,
    }


def matrix_record(matrix: np.ndarray) -> dict[str, Any]:
    array = np.ascontiguousarray(matrix)
    if not np.isfinite(array).all():
        raise ArithmeticError("nonfinite matrix in receipt")
    record = {"shape": list(array.shape), "dtype": str(array.dtype), "sha256": _array_hash(array)}
    if np.iscomplexobj(array):
        record.update(real=array.real.tolist(), imag=array.imag.tolist())
    else:
        record["values"] = array.tolist()
    return record


def cutoff_nodal_control() -> dict[str, Any]:
    """Exact sign-change obstruction at doubled cutoff 1 and x=1.

    In the vacuum, (011), symmetric-loop sector, write E0=4-s.
    The positive root obeys 2s^3+15s^2+22s-18=0. For ground-vector
    components (u,v,-w), u/(sqrt(2)w)=1/s and
    2v/(sqrt(2)w)=1/(9/2+s). At identity links the wavefunction is
    u+2v+2sqrt(2)w; replacing only U0 by -I gives u+2v-2sqrt(2)w.
    The latter is strictly negative by the rational interval below.

    For dmu=Omega^2 dU/Z, smooth approximations to sign(Omega) have
    positive limiting variance and energy bounded by a constant times
    integral_{|Omega|<epsilon} |grad_B Omega|^2 dU, which tends to zero.
    Thus this nodal cutoff measure has unrestricted conditional gap zero.
    This control does not classify convergence at any other cutoff.
    """
    low, high = Fraction(23, 40), Fraction(72, 125)
    polynomial = lambda s: 2 * s ** 3 + 15 * s ** 2 + 22 * s - 18
    upper = 1 / low + 1 / (Fraction(9, 2) + low) - 2
    if not polynomial(low) < 0 < polynomial(high) or upper >= 0:
        raise ArithmeticError("exact root isolation or nodal bound failed")
    space = SpectrumSpace(1)
    expected = np.array([[4, 0, 1, 1], [0, 8.5, 0.5, 0.5],
                         [1, 0.5, 7, 0], [1, 0.5, 0, 7]])
    normalized = space.hamiltonian(Fraction(1)) / np.outer(space.norms, space.norms)
    matrix_error = float(np.max(np.abs(normalized - expected)))
    ritz = ritz_row(space, Fraction(1), None)
    signs = np.array([(-1) ** state[0] for state in space.states])
    amplitudes = [float(signs @ ritz["vector"]), float(np.sum(ritz["vector"]))]
    point_error = 0.0
    for position, state in enumerate(space.states):
        spins = state_leg_spins(state)
        matrices = {e: np.eye(spins[e] + 1, dtype=complex) for e in ALL_LINKS}
        point_error = max(point_error, abs(evaluate_state(state, matrices) - signs[position]))
        matrices[0] *= (-1) ** state[0]
        point_error = max(point_error, abs(evaluate_state(state, matrices) - 1.0))
    if matrix_error > 1.0e-10 or point_error > 1.0e-10 or not amplitudes[0] > 0 > amplitudes[1]:
        raise ArithmeticError("nodal witness does not match the assembled basis")
    return {
        "cutoff_doubled": 1, "coupling": "1", "boundary": "identity exterior",
        "ground_shift_positive_root_interval": [str(low), str(high)],
        "polynomial_endpoint_values": [str(polynomial(low)), str(polynomial(high))],
        "scaled_negative_amplitude_upper_bound": str(upper),
        "identity_and_center_amplitudes": amplitudes,
        "exact_matrix_deviation": matrix_error, "center_value_deviation": float(point_error),
        "unrestricted_conditional_gap": 0,
        "scope": "this sign-changing Ritz density; no cutoff-removal or continuum conclusion",
    }


def conditional_row(space: SpectrumSpace, coefficients: dict[tuple[int, int, int], float]) -> dict[str, Any]:
    data = conditional_matrices(coefficients, math.pi / 2.0, space.cutoff)
    fibre = FibreSpace(data["restriction_gram"], space.states)
    covariance = fibre.transform(data["covariance"])
    dirichlet = fibre.transform(data["dirichlet"])
    symmetry = max(float(np.max(np.abs(matrix - matrix.conj().T)))
                   for matrix in (data["gram"], data["covariance"], data["dirichlet"]))
    if symmetry > 1.0e-10 or not np.isfinite(data["partition"]) or data["partition"] <= 0:
        raise ArithmeticError("conditional moment symmetry or normalization failed")
    result = generalized_rate(dirichlet, covariance)
    if result["residual"] > 1.0e-9 or result["rate"] <= 0:
        raise ArithmeticError(f"invalid finite conditional solve: {result}")
    raw_vector = fibre.map_to_vector @ fibre.basis @ result["vector"]
    first = np.flatnonzero(np.abs(raw_vector) > 1.0e-14)[0]
    raw_vector *= np.exp(-1j * np.angle(raw_vector[first]))
    matrices = {
        name: matrix_record(data[name])
        for name in ("restriction_gram", "gram", "covariance", "dirichlet")
    }
    matrices.update(
        restriction_map=matrix_record(fibre.map_to_coordinates),
        retained_basis=matrix_record(fibre.map_to_vector @ fibre.basis),
        retained_covariance=matrix_record(covariance),
        retained_dirichlet=matrix_record(dirichlet),
        minimizing_direction=matrix_record(raw_vector),
    )
    return {
        "partition": float(data["partition"]),
        "rate": result["rate"],
        "eigenvalues": result["eigenvalues"],
        "eigen_residual": result["residual"],
        "hermiticity_residual": symmetry,
        "restriction_rank": fibre.rank,
        "retained_dimension": fibre.basis.shape[1],
        "removed_constant_dimension": fibre.removed_constant_dimension,
        "matrices": matrices,
        "_minimizer": raw_vector,
        "_data": data,
    }


def conditional_validation() -> dict[str, Any]:
    """Cross-check the product algebra against direct seven-link contractions.

    Every scheduled boundary angle is contracted directly against explicit
    boundary matrices, so boundary independence of the conditional moments is
    checked over the whole scheduled slice instead of at sample angles. The
    first angle supplies the reference for the direct spread.
    """
    space = SpectrumSpace(1)
    coefficients = dict(zip(space.states, ritz_row(space, Fraction(1), None)["vector"]))
    selected = [(0, 0, 0), (1, 1, 0), (1, 0, 1)]
    indexes = [space.index[state] for state in selected]
    errors = {"partition": 0.0, "gram": 0.0, "dirichlet": 0.0, "direct_boundary_spread": 0.0}
    reference: tuple[float, np.ndarray, np.ndarray] | None = None
    for fraction in BOUNDARY_ANGLES:
        theta = float(fraction) * math.pi
        data = conditional_matrices(coefficients, theta, 1)
        partition = partition_function(coefficients, theta)
        gram = conditional_gram_block(coefficients, theta, selected, selected) / partition
        dirichlet = np.zeros((len(selected), len(selected)), dtype=complex)
        for link in BLOCK_LINKS:
            for component in range(3):
                dirichlet += conditional_gram_block(
                    coefficients, theta, selected, selected, generator=component, generator_link=link
                ) / partition
        errors["partition"] = max(errors["partition"], abs(partition - data["partition"]))
        errors["gram"] = max(errors["gram"], float(np.max(np.abs(gram - data["gram"][np.ix_(indexes, indexes)]))))
        errors["dirichlet"] = max(errors["dirichlet"], float(np.max(np.abs(
            dirichlet - data["dirichlet"][np.ix_(indexes, indexes)]
        ))))
        if reference is None:
            reference = (partition, gram, dirichlet)
        else:
            errors["direct_boundary_spread"] = max(
                errors["direct_boundary_spread"],
                abs(partition - reference[0]),
                float(np.max(np.abs(gram - reference[1]))),
                float(np.max(np.abs(dirichlet - reference[2]))),
            )
    if max(errors.values()) > 1.0e-9:
        raise ArithmeticError(f"direct conditional reconstruction failed: {errors}")
    return {"angles_pi": [str(fraction) for fraction in BOUNDARY_ANGLES], "errors": errors}


def stable_value(left: float, right: float) -> bool:
    tolerance = STABILITY_ABSOLUTE if abs(right) < 1.0 else STABILITY_RELATIVE * abs(right)
    return abs(left - right) <= tolerance


def qualify_rows(spaces: dict[int, SpectrumSpace], spectrum: dict[str, Any], conditional: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for cutoff in CUTOFFS:
        for coupling in COUPLINGS:
            key = f"J{cutoff}_x{coupling}"
            adjacent = cutoff + 1 if cutoff < CUTOFFS[-1] else cutoff - 1
            adjacent_key = f"J{adjacent}_x{coupling}"
            lower, upper = sorted((cutoff, adjacent))
            low_key, high_key = f"J{lower}_x{coupling}", f"J{upper}_x{coupling}"
            low, high = conditional[low_key], conditional[high_key]
            indexes = [spaces[upper].index[state] for state in spaces[lower].states]
            embedded = np.zeros(len(spaces[upper].states), dtype=complex)
            embedded[indexes] = low["_minimizer"]
            high_data = high["_data"]
            embedded_rate = float(np.real(
                np.vdot(embedded, high_data["dirichlet"] @ embedded)
                / np.vdot(embedded, high_data["covariance"] @ embedded)
            ))
            inclusion_error = float(np.max(np.abs(
                high_data["restriction_gram"][np.ix_(indexes, indexes)] - low["_data"]["restriction_gram"]
            )))
            reasons = []
            current = spectrum[key]
            if current["full_residual"] > FULL_RESIDUAL_MAX:
                reasons.append("full_space_residual")
            if not stable_value(current["energy_ground"], spectrum[adjacent_key]["energy_ground"]):
                reasons.append("ground_energy_cutoff_stability")
            if not stable_value(conditional[key]["rate"], conditional[adjacent_key]["rate"]):
                reasons.append("conditional_rate_cutoff_stability")
            if not stable_value(embedded_rate, high["rate"]):
                reasons.append("embedded_minimizer")
            if inclusion_error > 1.0e-10:
                reasons.append("nested_inclusion")
            # The protocol explicitly classifies a changed restriction rank as inconclusive.
            if low["restriction_rank"] != high["restriction_rank"]:
                reasons.append("restriction_rank_change")
            if cutoff == CUTOFFS[-1] and current["full_residual"] > spectrum[adjacent_key]["full_residual"]:
                reasons.append("endpoint_residual_monotonicity")
            for angle in BOUNDARY_ANGLES:
                classification = "INCONCLUSIVE"
                if not reasons and conditional[key]["rate"] < TARGET_RATE:
                    classification = "WITNESS_CONDITIONAL_COLLAPSE"
                rows.append({
                    "cutoff": cutoff, "coupling": str(coupling), "theta_pi": str(angle),
                    "matrix_key": key, "rate": conditional[key]["rate"],
                    "comparison_cutoff": adjacent, "embedded_rate": embedded_rate,
                    "nested_inclusion_residual": inclusion_error,
                    "qualification_failures": reasons,
                    "rate_qualified": not reasons,
                    "classification": classification,
                })
    return rows


def run_dev(cutoff: int) -> int:
    """Exercise the actual first-target solve without issuing a frozen receipt."""
    checks = validation_checks(cutoff)
    print(json.dumps(checks, indent=2, sort_keys=True))
    print("nodal_cutoff_control", cutoff_nodal_control(), flush=True)
    print("direct_conditional_errors", conditional_validation(), flush=True)
    space, extended = SpectrumSpace(cutoff), SpectrumSpace(cutoff + 1)
    for coupling in COUPLINGS:
        ritz = ritz_row(space, coupling, extended)
        coefficients = dict(zip(space.states, ritz["vector"]))
        row = conditional_row(space, coefficients)
        print(f"cutoff={cutoff} x={coupling} E0={ritz['energy_ground']:.12g} "
              f"r_proj={ritz['projected_residual']:.3e} r_full={ritz['full_residual']:.3e} "
              f"rate={row['rate']:.12g} rank={row['restriction_rank']} "
              f"retained={row['retained_dimension']} Z={row['partition']:.12g}", flush=True)
    print("FIRST_TARGET_SMOKE_PASSED", flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stage", choices=("dev", "full"), default="full")
    parser.add_argument("--max-cutoff", type=int, choices=CUTOFFS, default=5)
    args = parser.parse_args(argv)
    if args.stage == "dev":
        return run_dev(args.max_cutoff)
    if args.output is None or args.max_cutoff != CUTOFFS[-1]:
        parser.error("the full stage requires --output and the complete frozen cutoff schedule")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing receipt: {args.output}")
    helper = SOURCE.with_name("yang_mills_conditional_algebra.py")
    inputs = {path: path.read_bytes() for path in (PROTOCOL, SOURCE, helper)}
    start = time.perf_counter()
    validation = validation_checks(CUTOFFS[-1])
    validation["analytical_nodal_control"] = cutoff_nodal_control()
    validation["direct_conditional_errors"] = conditional_validation()
    spaces: dict[int, SpectrumSpace] = {}
    for cutoff in (*CUTOFFS, CUTOFFS[-1] + 1):
        spaces[cutoff] = SpectrumSpace(cutoff)
        print(f"[space] cutoff={cutoff} dim={len(spaces[cutoff].states)} "
              f"elapsed={time.perf_counter()-start:.2f}s", flush=True)
    spectrum: dict[str, Any] = {}
    conditional: dict[str, Any] = {}
    for cutoff in CUTOFFS:
        space = spaces[cutoff]
        for coupling in COUPLINGS:
            key = f"J{cutoff}_x{coupling}"
            ritz = ritz_row(space, coupling, spaces[cutoff + 1])
            if ritz["projected_residual"] > PROJECTED_RESIDUAL_MAX:
                raise ArithmeticError(f"projected residual failed at {key}")
            if cutoff > CUTOFFS[0] and ritz["energy_ground"] > spectrum[f"J{cutoff-1}_x{coupling}"]["energy_ground"] + 1.0e-10:
                raise ArithmeticError(f"nested Ritz energy increased at {key}")
            coefficients = dict(zip(space.states, ritz["vector"]))
            spectrum[key] = {**ritz, "hamiltonian": matrix_record(space.hamiltonian(coupling))}
            conditional[key] = conditional_row(space, coefficients)
            print(f"[row] {key} E0={ritz['energy_ground']:.12g} "
                  f"full_residual={ritz['full_residual']:.3e} rate={conditional[key]['rate']:.12g} "
                  f"elapsed={time.perf_counter()-start:.2f}s", flush=True)
    rows = qualify_rows(spaces, spectrum, conditional)
    for item in conditional.values():
        del item["_minimizer"], item["_data"]
    operation = {
        "target": "cutoff_Ritz_ground_state_and_conditional_rate",
        "integration": "SU2 Clebsch-Gordan Haar contractions and invariant product algebra",
        "boundary_reduction": "gauge-transitive exterior forest; conditional scalar and Dirichlet moments constant on its orbit",
        "rate_bound_direction": "upper bound on unrestricted conditional gap of the cutoff measure",
        "full_residual_closure": "multiplication by a fundamental plaquette raises each touched doubled spin by at most one",
        "score_and_transport": "outside first implementation target; no score or margin verdict issued",
        "convergence_rule": "literal preregistered rank-change, nested-inclusion, embedded-minimizer and residual rules",
    }
    tables = {
        ",".join(map(str, key)): matrix_record(value)
        for key, value in sorted(_W3J.items())
    }
    record = {
        "schema": "cassi.yang-mills.exact-block-first-target.v1",
        "execution": "PASS",
        "classification": "INCONCLUSIVE",
        "source_sha256": hashlib.sha256(inputs[SOURCE]).hexdigest(),
        "protocol_sha256": hashlib.sha256(inputs[PROTOCOL]).hexdigest(),
        "inputs": {path.relative_to(ROOT).as_posix(): hashlib.sha256(content).hexdigest()
                   for path, content in inputs.items()},
        "graph": graph_manifest(), "schedule": schedule_manifest(), "operations": operation,
        "graph_sha256": hashlib.sha256(json.dumps(graph_manifest(), sort_keys=True).encode()).hexdigest(),
        "schedule_sha256": hashlib.sha256(json.dumps(schedule_manifest(), sort_keys=True).encode()).hexdigest(),
        "operations_sha256": hashlib.sha256(json.dumps(operation, sort_keys=True).encode()).hexdigest(),
        "representation_tables": tables,
        "spaces": {str(c): {"states": [list(state) for state in space.states],
                            "overlap": matrix_record(space.overlap),
                            "kinetic": matrix_record(space.kinetic),
                            "plaquette": matrix_record(space.plaquette_matrix),
                            "hermiticity_residual": space.hermiticity_residual}
                   for c, space in spaces.items()},
        "validation": validation, "spectrum": spectrum, "conditional": conditional, "rows": rows,
        "summary": {"ritz_rows": len(spectrum), "boundary_rows": len(rows),
                    "qualified_boundary_rows": sum(row["rate_qualified"] for row in rows)},
        "open_obligations": ["exact-vacuum fibre rate replacing the nodal Ritz surrogate",
                             "transport score", "cutoff removal", "uniform interacting recovery",
                             "thermodynamic limit", "continuum construction and positive mass gap"],
        "wall_seconds": time.perf_counter() - start,
    }
    if any(path.read_bytes() != content for path, content in inputs.items()):
        raise RuntimeError("input bytes changed during the run; refusing to seal a mixed-source receipt")
    payload = json.dumps(record, indent=2, sort_keys=True, allow_nan=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(payload + "\n")
    print(f"wrote {args.output}: execution PASS; scientific classification INCONCLUSIVE", flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
