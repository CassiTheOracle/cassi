#!/usr/bin/env python3
"""Independent reconstruction of the seven-link SU(2) cutoff Ritz spectrum.

Protocol: ``computations/yang-mills-exact-block-spectral-prereg.md``.

This file is the independent measurement path for the first implementation
target of that protocol (cutoff Ritz ground states and conditional block
rates).  It does not import, read, or reuse the primary program
``verify_yang_mills_exact_block_spectrum.py``, its intermediate matrices, or
the product-algebra helper ``yang_mills_conditional_algebra.py``.  All
representation contractions are re-derived here from the declared
spin-network conventions:

* the graph is ``(0,1),(1,2),(3,2),(0,3),(1,5),(4,5),(0,4)`` with plaquette
  words ``(0,1)(1,1)(2,-1)(3,-1)`` and ``(0,1)(4,1)(5,-1)(6,-1)``; the block
  is ``B = {0,1,2,3}`` and the exterior links are ``4,5,6``;
* a state is a doubled-spin triple ``(a,b,c)`` -- ``a`` on edge 0, ``b`` on
  edges 1,2,3, ``c`` on edges 4,5,6 -- admissible when ``a+b+c`` is even and
  ``|a-b| <= c <= a+b``;
* the v0 (vertex 0) tensor is the plain Wigner 3j ``3j(a/2,b/2,c/2)`` with the
  magnetic ordering ``-j..j``; the v1 (vertex 1) tensor carries the invariant
  metric on the edge-0 leg,
  ``V1[n_a,n_b,n_c] = sum_k eps^{a/2}[n_a,k] 3j(a/2,b/2,c/2; k,n_b,n_c)``;
* the three-link chains of edges 1,2,3 and 4,5,6 are collapsed with the
  declared ``delta``/``metric`` masks to effective path holonomies that carry
  the invariant metric on the v0 leg of the ``b`` and ``c`` paths.  That
  metric is kept explicitly in the plaquette contraction below.

Analytic controls evaluated in :func:`self_check`:

* state norm ``1/[(a+1)(b+1)(c+1)]``;
* ``<(1,1,0)|chi_0|(0,0,0)> = -1/4`` unnormalized (``-1/2`` in the S-metric)
  and ``<(1,0,1)|chi_1|(0,0,0)> = -1/4``;
* the plaquette diagonal vanishes on the fundamental states,
  ``<(1,1,0)|chi_0|(1,1,0)> = 0``;
* Hermiticity of both plaquette matrices and the cutoff-to-cutoff embedding.

Plaquette matrices come from the metric/3j master contraction
``int dU D^{j1}_{m1n1} D^{j2}_{m2n2} conj(D^{j3}_{m3n3}) = (1/d_{j3})
C^{j3 m3}_{j1 m1, j2 m2} C^{j3 n3}_{j1 n1, j2 n2}`` with the v1-leg metric on
the ``b``/``c`` legs.  No Wigner-9j shortcut is used for the plaquette, and no
post-hoc symmetrization is applied.

The conditional product algebra of :func:`conditional_data` follows the
protocol's stated algebra ``psi_i psi_j = sum_r p[i,j,r] psi_r`` with
``p[i,j,r] = d_r * 9j(i,j,r)**2`` (rows indexed by the states, columns by the
three paths).  The identity ``9j((0,0,0), j, j)**2 = 1/d_j`` is checked
numerically.  A direct 3j magnetic contraction of the triple overlap is **not**
implemented here; the conditional rows are instead validated end to end
against the primary's retained-rate reference values.

Usage::

    python computations/verify_yang_mills_exact_block_spectrum_independent.py \
        [--output <fresh path>/independent.json] [--stage dev]

The program never writes a file unless ``--output`` is given.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from sympy import Rational
from sympy.physics.wigner import wigner_3j, wigner_9j

CUTOFFS = (1, 2, 3, 4, 5)
COUPLINGS = (0.25, 1.0, 4.0, 16.0)
THETA_SLICE = tuple(k * math.pi / 8.0 for k in range(9))

GRAPH_EDGES = ((0, 1), (1, 2), (3, 2), (0, 3), (1, 5), (4, 5), (0, 4))
PLAQUETTE_WORDS = (((0, 1), (1, 1), (2, -1), (3, -1)),
                   ((0, 1), (4, 1), (5, -1), (6, -1)))
BLOCK = (0, 1, 2, 3)
EXTERIOR = (4, 5, 6)
# Path letters of the theta network: A = edge 0, B = edges 1,2,3, C = edges 4,5,6.
PATH_A, PATH_B, PATH_C = 0, 1, 2

State = tuple


# ---------------------------------------------------------------------------
# SU(2) representation tables.  Every spin and magnetic label below is doubled
# (``j = n/2``, ``m = M/2``), so all arithmetic stays in integers.
# ---------------------------------------------------------------------------

def _doubled_range(n2: int) -> range:
    return range(-n2, n2 + 1, 2)


@lru_cache(maxsize=None)
def _three_j(j1: int, j2: int, j3: int, m1: int, m2: int, m3: int) -> float:
    """Doubled-label Wigner 3j, standard phase convention."""
    if j1 < 0 or j2 < 0 or j3 < 0:
        return 0.0
    if m1 + m2 + m3 != 0:
        return 0.0
    if abs(j1 - j2) > j3 or j3 > j1 + j2 or (j1 + j2 + j3) % 2:
        return 0.0
    value = wigner_3j(Rational(j1, 2), Rational(j2, 2), Rational(j3, 2),
                      Rational(m1, 2), Rational(m2, 2), Rational(m3, 2))
    return float(value)


@lru_cache(maxsize=None)
def _cg(j1: int, j2: int, j3: int, m1: int, m2: int, m3: int) -> float:
    """Doubled-label ``<j1 m1 j2 m2 | j3 m3>`` from the 3j relation."""
    if m1 + m2 != m3:
        return 0.0
    if abs(j1 - j2) > j3 or j3 > j1 + j2 or (j1 + j2 + j3) % 2:
        return 0.0
    phase = -1.0 if ((j1 - j2 + m3) // 2) % 2 else 1.0
    return phase * math.sqrt(j3 + 1.0) * _three_j(j1, j2, j3, m1, m2, -m3)


@lru_cache(maxsize=None)
def _metric(n2: int, m: int, n: int) -> float:
    """Invariant metric ``eps^{n2/2}_{m n} = (-1)^{j-m} delta_{m,-n}``."""
    if m != -n:
        return 0.0
    return -1.0 if ((n2 - m) // 2) % 2 else 1.0


def _admissible(a: int, b: int, c: int) -> bool:
    return (a + b + c) % 2 == 0 and abs(a - b) <= c <= a + b


def _states(n2: int) -> tuple[State, ...]:
    out = []
    for a in range(n2 + 1):
        for b in range(n2 + 1):
            for c in range(n2 + 1):
                if _admissible(a, b, c):
                    out.append((a, b, c))
    return tuple(out)


def _norm(state: State) -> float:
    a, b, c = state
    return 1.0 / float((a + 1) * (b + 1) * (c + 1))


def _casimir(n2: int) -> float:
    j = 0.5 * n2
    return j * (j + 1.0)


def _k_total(state: State) -> float:
    """Electric Casimir on the seven links: 1 x a, 3 x b, 3 x c."""
    a, b, c = state
    return _casimir(a) + 3.0 * _casimir(b) + 3.0 * _casimir(c)


def _k_block(state: State) -> float:
    """Electric Casimir restricted to the block links B = {0,1,2,3}."""
    a, b, _ = state
    return _casimir(a) + 3.0 * _casimir(b)


@lru_cache(maxsize=None)
def _v0(state: State) -> dict:
    """Plain 3j vertex tensor at vertex 0, keyed by ``(m_a, m_b, m_c)``."""
    a, b, c = state
    out = {}
    for ma in _doubled_range(a):
        for mb in _doubled_range(b):
            mc = -(ma + mb)
            if abs(mc) > c:
                continue
            value = _three_j(a, b, c, ma, mb, mc)
            if value != 0.0:
                out[(ma, mb, mc)] = value
    return out


@lru_cache(maxsize=None)
def _v1(state: State) -> dict:
    """Metric-carrying vertex tensor at vertex 1, keyed by ``(n_a, n_b, n_c)``."""
    a, b, c = state
    out = {}
    for na in _doubled_range(a):
        for nb in _doubled_range(b):
            for nc in _doubled_range(c):
                total = 0.0
                for k in _doubled_range(a):
                    eps = _metric(a, na, k)
                    if eps != 0.0:
                        total += eps * _three_j(a, b, c, k, nb, nc)
                if total != 0.0:
                    out[(na, nb, nc)] = total
    return out


# ---------------------------------------------------------------------------
# Plaquette operators by the metric/3j master contraction.
# ---------------------------------------------------------------------------

def _plaq_element(i: State, r: State, path: int) -> float:
    """``<i|chi_p|r>`` for the plaquette spanning path A and ``path``.

    ``path`` is :data:`PATH_B` (plaquette 0, edges 0,1,2,3) or
    :data:`PATH_C` (plaquette 1, edges 0,4,5,6).  The result is in the
    unnormalized spin-network basis, so the S-metric is
    ``diag(norm(state))``.
    """
    other = 3 - path  # the path not touched by this plaquette
    if abs(i[PATH_A] - r[PATH_A]) != 1:
        return 0.0
    if abs(i[path] - r[path]) != 1:
        return 0.0
    if i[other] != r[other]:
        return 0.0

    prefactor = _norm(i)  # 1 / ((a+1)(b+1)(c+1)) with i[other] == r[other]
    m_total = 0.0
    for mu in (-1, 1):
        for (mi_a, mi_b, mi_c), vi in _v0(i).items():
            mi = (mi_a, mi_b, mi_c)
            for (mr_a, mr_b, mr_c), vr in _v0(r).items():
                mr = (mr_a, mr_b, mr_c)
                if mi[other] != mr[other]:
                    continue
                c_a = _cg(r[PATH_A], 1, i[PATH_A],
                          mr[PATH_A], mu, mi[PATH_A])
                if c_a == 0.0:
                    continue
                leg = 0.0
                for pi in _doubled_range(i[path]):
                    eps_i = _metric(i[path], pi, mi[path])
                    if eps_i == 0.0:
                        continue
                    for pr in _doubled_range(r[path]):
                        eps_r = _metric(r[path], pr, mr[path])
                        if eps_r == 0.0:
                            continue
                        c_q = _cg(r[path], 1, i[path], pr, mu, pi)
                        if c_q != 0.0:
                            leg += eps_i * eps_r * c_q
                if leg != 0.0:
                    m_total += vi * vr * c_a * leg
    if m_total == 0.0:
        return 0.0
    n_total = 0.0
    for nu in (-1, 1):
        for (ni_a, ni_b, ni_c), wi in _v1(i).items():
            ni = (ni_a, ni_b, ni_c)
            for (nr_a, nr_b, nr_c), wr in _v1(r).items():
                nr = (nr_a, nr_b, nr_c)
                if ni[other] != nr[other]:
                    continue
                c_a = _cg(r[PATH_A], 1, i[PATH_A],
                          nr[PATH_A], nu, ni[PATH_A])
                if c_a == 0.0:
                    continue
                c_q = _cg(r[path], 1, i[path], nr[path], nu, ni[path])
                if c_q != 0.0:
                    n_total += wi * wr * c_a * c_q
    # The two loop indices are independent: mu tags the row of the inserted
    # fundamental on path A and the metric leg on the three-link path, nu the
    # two column legs.  The trace sum therefore factorizes.
    return prefactor * m_total * n_total


def _plaq_matrices(n2: int) -> tuple[tuple[State, ...], np.ndarray, np.ndarray]:
    labels = _states(n2)
    size = len(labels)
    chi0 = np.zeros((size, size), dtype=float)
    chi1 = np.zeros((size, size), dtype=float)
    for row, i in enumerate(labels):
        for col, r in enumerate(labels):
            # Every entry is contracted independently; no entry is mirrored.
            chi0[row, col] = _plaq_element(i, r, PATH_B)
            chi1[row, col] = _plaq_element(i, r, PATH_C)
    return labels, chi0, chi1


# ---------------------------------------------------------------------------
# Ritz problem.
# ---------------------------------------------------------------------------

def _hamiltonian(n2: int, x: float) -> tuple[tuple[State, ...], np.ndarray, np.ndarray]:
    labels, chi0, chi1 = _plaq_matrices(n2)
    # <s|h|r> with the non-orthonormal metric <s|r> = S_sr:
    # the electric and constant terms are multiples of the identity operator,
    # so they contribute (K_s + 4x) S_sr, not (K_s + 4x) delta_sr.
    s_metric = np.diag([_norm(s) for s in labels])
    kinetic = np.asarray([_k_total(s) for s in labels], dtype=float)
    h = np.diag((kinetic + 4.0 * x) * np.diag(s_metric)) - x * (chi0 + chi1)
    return labels, h, s_metric


def _ritz(n2: int, x: float) -> dict:
    labels, h, s_metric = _hamiltonian(n2, x)
    scale = np.sqrt(np.diag(s_metric))
    a = h / np.outer(scale, scale)
    a = 0.5 * (a + a.T)
    values, vectors = np.linalg.eigh(a)
    alpha = vectors[:, 0] / scale
    # Fix the phase by the first nonzero Ritz coefficient.
    for value in alpha:
        if abs(value) > 1e-14:
            if value < 0.0:
                alpha = -alpha
            break
    alpha = alpha / math.sqrt(float(alpha @ s_metric @ alpha))

    beta = h @ alpha - values[0] * s_metric @ alpha
    r_projected = math.sqrt(float(beta @ s_metric @ beta))

    # Full residual: embed into the next cutoff space, ending at doubled
    # spin 6 for the scheduled endpoint.
    bigger = _states(n2 + 1)
    index = {s: k for k, s in enumerate(bigger)}
    _, h_big, s_big = _hamiltonian(n2 + 1, x)
    alpha_big = np.zeros(len(bigger), dtype=float)
    for state, coeff in zip(labels, alpha):
        if state in index:
            alpha_big[index[state]] = coeff
    beta_big = h_big @ alpha_big - values[0] * s_big @ alpha_big
    r_full = math.sqrt(float(beta_big @ s_big @ beta_big))
    r_full_euclid = float(np.linalg.norm(beta_big))

    return {
        "cutoff": n2,
        "x": x,
        "states": labels,
        "eigenvalues": values,
        "alpha": alpha,
        "ground_energy": float(values[0]),
        "first_excited": float(values[1]) if len(values) > 1 else None,
        "projected_residual": r_projected,
        "full_residual": r_full,
        "full_residual_euclidean": r_full_euclid,
        "dimension": len(labels),
    }


# ---------------------------------------------------------------------------
# Conditional block data (product algebra of the protocol).
# ---------------------------------------------------------------------------

def _fusion_values(x: int, y: int) -> range:
    return range(abs(x - y), x + y + 1, 2)


@lru_cache(maxsize=None)
def _nine_j(i: State, j: State, r: State) -> float:
    """Wigner 9j with rows ``i, j, r`` and columns the three paths."""
    args = tuple(Rational(value, 2) for row in (i, j, r) for value in row)
    try:
        return float(wigner_9j(*args))
    except ValueError:
        return 0.0


@lru_cache(maxsize=None)
def _product(i: State, j: State) -> tuple:
    out = []
    for a in _fusion_values(i[0], j[0]):
        for b in _fusion_values(i[1], j[1]):
            for c in _fusion_values(i[2], j[2]):
                if not _admissible(a, b, c):
                    continue
                r = (a, b, c)
                nine = _nine_j(i, j, r)
                if nine == 0.0:
                    continue
                out.append((r, float((a + 1) * (b + 1) * (c + 1)) * nine * nine))
    return tuple(out)


def conditional_data(states: Sequence[Sequence[int]],
                     coefficients,
                     theta: float = 0.0) -> dict:
    """Conditional Gram, covariance and block Dirichlet data.

    ``coefficients`` is either a mapping keyed by state label or a sequence
    aligned with ``states``.  The exterior angle ``theta`` is accepted for API
    compatibility and ignored: the exterior forest isometry makes the retained
    block algebra boundary independent, and the returned moment matrices are
    theta independent by construction.
    """
    float(theta)
    labels = tuple(tuple(int(value) for value in state) for state in states)
    if len(set(labels)) != len(labels):
        raise ValueError("states must not contain duplicate labels")
    if isinstance(coefficients, Mapping):
        alpha = np.asarray([float(coefficients.get(s, 0.0)) for s in labels])
    else:
        alpha = np.asarray([float(value) for value in coefficients])
        if alpha.shape != (len(labels),):
            raise ValueError("coefficient sequence must align with states")
    if not np.all(np.isfinite(alpha)):
        raise ValueError("coefficients must be finite real numbers")

    products = {}
    closure = set()
    for i in labels:
        for j in labels:
            terms = _product(i, j)
            products[(i, j)] = terms
            closure.update(r for r, _ in terms)

    q = {r: 0.0 for r in closure}
    for si, i in enumerate(labels):
        if alpha[si] == 0.0:
            continue
        for sj, j in enumerate(labels):
            if alpha[sj] == 0.0:
                continue
            scale = float(alpha[si] * alpha[sj])
            for r, value in products[(i, j)]:
                q[r] += scale * value

    partition = math.fsum(float(value * value * _norm(s))
                          for s, value in zip(labels, alpha))
    if not math.isfinite(partition) or partition <= 1e-15:
        raise ValueError("non-positive or non-finite conditional partition")

    n = np.asarray([_norm(s) for s in labels])
    gram_raw = np.zeros((len(labels), len(labels)))
    dirichlet_raw = np.zeros_like(gram_raw)
    for ri, i in enumerate(labels):
        for ci, j in enumerate(labels):
            ki = _k_block(i)
            kj = _k_block(j)
            g = 0.0
            d = 0.0
            for r, p in products[(i, j)]:
                moment = q.get(r, 0.0) * _norm(r)
                g += p * moment
                d += 0.5 * (ki + kj - _k_block(r)) * p * moment
            gram_raw[ri, ci] = g
            dirichlet_raw[ri, ci] = d

    mean = np.asarray([q.get(s, 0.0) * _norm(s) for s in labels]) / partition
    gram = gram_raw / partition
    return {
        "states": labels,
        "partition": float(partition),
        "restriction_gram": np.diag(n),
        "gram_raw": gram_raw,
        "dirichlet_raw": dirichlet_raw,
        "gram": gram,
        "covariance": gram - np.outer(mean, mean),
        "dirichlet": dirichlet_raw / partition,
        "mean": mean,
        "product_coefficients": products,
        "weight_coefficients": q,
    }


def _generalized_smallest(d_mat: np.ndarray, c_mat: np.ndarray) -> float:
    """Smallest generalized eigenvalue of ``D v = lam C v`` for SPD ``C``."""
    chol = np.linalg.cholesky(c_mat)
    inv = np.linalg.inv(chol)
    reduced = inv @ d_mat @ inv.T
    reduced = 0.5 * (reduced + reduced.T)
    return float(np.linalg.eigvalsh(reduced)[0])


def block_rate(states: Sequence[Sequence[int]], coefficients,
               theta: float = 0.0) -> dict:
    """Retained conditional rate: the constant direction is removed."""
    data = conditional_data(states, coefficients, theta)
    labels = data["states"]
    keep = [k for k, s in enumerate(labels) if s != (0, 0, 0)]
    covariance = np.asarray(data["covariance"], dtype=float)[np.ix_(keep, keep)]
    dirichlet = np.asarray(data["dirichlet"], dtype=float)[np.ix_(keep, keep)]
    rate = _generalized_smallest(dirichlet, covariance)
    return {
        "rate": rate,
        "retained_dimension": len(keep),
        "partition": data["partition"],
        "data": data,
    }


# ---------------------------------------------------------------------------
# Direct boundary contraction at J = 1.
#
# The conditional moments of the boundary slice are re-derived without the
# product algebra: the four block links are exposed as D-matrix index pairs,
# every block Haar integral is evaluated with the exact representation
# integral ``int dU D^{j1}[m1,n1]...D^{j4}[m4,n4]``, and the exterior links
# 4,5,6 carry the fixed diagonal matrices ``eta(theta)``.  Only the J = 1
# four-state space is needed, where every spin is 0 or 1/2.
# ---------------------------------------------------------------------------

# Hermitian generators sigma^A / 2 in the doubled-label order (-1, +1).
GENERATORS = (
    np.array([[0.0, 0.5], [0.5, 0.0]]),
    np.array([[0.0, -0.5j], [0.5j, 0.0]]),
    np.array([[-0.5, 0.0], [0.0, 0.5]]),
)


_FACTOR_CACHE: dict = {}


def _slot(j: int, m: int) -> int:
    return (m + j) // 2


def _exterior_phase(j: int, m: int, theta: float) -> complex:
    """``D^{j}(exp(i theta sigma_3/2))[m,m]`` for doubled labels."""
    return complex(math.cos(0.5 * theta * m), math.sin(0.5 * theta * m))


@lru_cache(maxsize=None)
def _integrate_dmatrices(spec: tuple) -> float:
    """``int dU prod_f D^{j_f}[m_f,n_f]`` for an even number of active factors.

    ``spec`` is a tuple of ``(j, m, n)`` with ``j > 0``; spin-zero factors are
    dropped before the call.
    """
    if not spec:
        return 1.0
    if len(spec) == 2:
        (j1, m1, n1), (j2, m2, n2) = spec
        if j1 != j2:
            return 0.0
        return _cg(j1, j2, 0, m1, m2, 0) * _cg(j1, j2, 0, n1, n2, 0)
    if len(spec) == 4:
        (j1, m1, n1), (j2, m2, n2), (j3, m3, n3), (j4, m4, n4) = spec
        total = 0.0
        for J in range(abs(j1 - j2), j1 + j2 + 1, 2):
            if J < abs(j3 - j4) or J > j3 + j4:
                continue
            left_m = 0.0
            left_n = 0.0
            right_m = 0.0
            right_n = 0.0
            for M in _doubled_range(J):
                a = _cg(j1, j2, J, m1, m2, M)
                b = _cg(j3, j4, J, m3, m4, -M)
                c = _cg(j1, j2, J, n1, n2, M)
                d = _cg(j3, j4, J, n3, n4, -M)
                sign = -1.0 if ((J - M) // 2) % 2 else 1.0
                left_m += sign * a * b
                left_n += sign * c * d
            total += left_m * left_n / (J + 1.0)
        return total
    raise ValueError("direct contraction supports at most four active factors")


def _link_kernel(spins: tuple, conjugates: tuple) -> np.ndarray:
    """``int dU prod_f D^{j_f}[mu_f,nu_f]`` with conjugation flags.

    The array axes are ``(mu_0, nu_0, mu_1, nu_1, ...)``.  Conjugated factors
    are converted with ``conj(D^{j}[m,n]) = (-1)^{m-n}D^{j}[-m,-n]``.
    """
    nf = len(spins)
    shape = []
    for j in spins:
        shape.extend([j + 1, j + 1])
    out = np.zeros(shape, dtype=float)
    active = [k for k, j in enumerate(spins) if j > 0]
    if len(active) % 2:
        return out
    if not active:
        out[tuple(0 for _ in range(2 * nf))] = 1.0
        return out
    ranges = []
    for k in active:
        ranges.extend([list(_doubled_range(spins[k])),
                       list(_doubled_range(spins[k]))])
    for values in itertools.product(*ranges):
        index = [0] * (2 * nf)
        spec = []
        sign = 1.0
        for slot, k in enumerate(active):
            mu = values[2 * slot]
            nu = values[2 * slot + 1]
            if conjugates[k]:
                if ((mu - nu) // 2) % 2:
                    sign = -sign
                mu, nu = -mu, -nu
            index[2 * k] = _slot(spins[k], values[2 * slot])
            index[2 * k + 1] = _slot(spins[k], values[2 * slot + 1])
            spec.append((spins[k], mu, nu))
        value = sign * _integrate_dmatrices(tuple(spec))
        if value:
            out[tuple(index)] += value
    return out


def _direct_factor(state: State, theta: float, conjugate: bool,
                   insert: tuple | None = None) -> np.ndarray:
    """Factor tensor indexed by ``(m_a, n_a, n_b, p1, p2, p_b)``.

    ``insert`` is ``(link, generator)`` and applies one left generator to the
    exposed row index of that link; a conjugated factor carries the conjugated
    generator and the conjugated exterior phase.
    """
    key = (state, round(theta, 12), bool(conjugate), insert)
    cached = _FACTOR_CACHE.get(key)
    if cached is not None:
        return cached
    a, b, c = state
    base = np.zeros((a + 1, a + 1, b + 1, b + 1), dtype=complex)
    for (m_a, m_b, m_c), val0 in _v0(state).items():
        if val0 == 0.0:
            continue
        for (n_a, n_b, n_c), val1 in _v1(state).items():
            if val1 == 0.0:
                continue
            eps_c = _metric(c, n_c, m_c)
            if eps_c == 0.0:
                continue
            phase = _exterior_phase(c, n_c, theta)
            if conjugate:
                phase = phase.conjugate()
            amp = val0 * val1 * eps_c * phase
            if amp == 0.0:
                continue
            for p_b in _doubled_range(b):
                eps_b = _metric(b, p_b, m_b)
                if eps_b == 0.0:
                    continue
                base[_slot(a, m_a), _slot(a, n_a),
                     _slot(b, n_b), _slot(b, p_b)] += amp * eps_b
    tensor = np.zeros((a + 1, a + 1, b + 1, b + 1, b + 1, b + 1), dtype=complex)
    tensor[:, :, :, :, :, :] = base[:, :, :, None, None, :]
    if insert is not None:
        link, generator = insert
        spin = a if link == 0 else b
        if spin == 0:
            tensor = np.zeros_like(tensor)
        else:
            axis = {0: 0, 1: 2, 2: 3, 3: 4}[link]
            matrix = GENERATORS[generator]
            if conjugate:
                matrix = matrix.conjugate()
            moved = np.tensordot(matrix, tensor, axes=([1], [axis]))
            tensor = np.moveaxis(moved, 0, axis)
    _FACTOR_CACHE[key] = tensor
    return tensor
def _direct_moment(factors: Sequence[tuple], theta: float) -> float:
    """Explicit contraction of ``prod_f psi_{s_f}`` with insertions."""
    tensors = [_direct_factor(s, theta, conj, ins) for s, conj, ins in factors]
    nf = len(factors)
    spins_a = tuple(s[0] for s, _, _ in factors)
    spins_b = tuple(s[1] for s, _, _ in factors)
    cons = tuple(conj for _, conj, _ in factors)
    k_a = _link_kernel(spins_a, cons)
    k_b = [_link_kernel(spins_b, cons) for _ in range(3)]
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    chars = [letters[6 * f:6 * f + 6] for f in range(nf)]
    tensor_sub = ["".join(ch) for ch in chars]
    sub_a = "".join(chars[f][0] + chars[f][1] for f in range(nf))
    sub_b1 = "".join(chars[f][2] + chars[f][3] for f in range(nf))
    sub_b2 = "".join(chars[f][3] + chars[f][4] for f in range(nf))
    sub_b3 = "".join(chars[f][4] + chars[f][5] for f in range(nf))
    expr = ",".join(tensor_sub + [sub_a, sub_b1, sub_b2, sub_b3]) + "->"
    value = np.einsum(expr, *tensors, k_a, k_b[0], k_b[1], k_b[2])
    return float(np.real_if_close(value).real)


def direct_conditional_objects(states: Sequence[Sequence[int]],
                               coefficients, theta: float) -> dict:
    """Partition, conditional Gram and Dirichlet form from explicit contraction."""
    labels = tuple(tuple(int(v) for v in s) for s in states)
    coeffs = np.asarray([float(v) for v in coefficients])
    size = len(labels)

    def density(i: int, j: int):
        return coeffs[i] * coeffs[j]

    partition = 0.0
    for i in range(size):
        for j in range(size):
            if density(i, j) == 0.0:
                continue
            partition += density(i, j) * _direct_moment(
                [(labels[i], True, None), (labels[j], False, None)], theta)

    gram = np.zeros((size, size))
    dirichlet = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            g = 0.0
            d = 0.0
            for s in range(size):
                for r in range(size):
                    weight = density(s, r)
                    if weight == 0.0:
                        continue
                    base = [(labels[s], True, None), (labels[r], False, None),
                            (labels[i], True, None), (labels[j], False, None)]
                    g += weight * _direct_moment(base, theta)
                    for link in range(4):
                        for generator in range(3):
                            moved = base[:2] + [
                                (labels[i], True, (link, generator)),
                                (labels[j], False, (link, generator))]
                            d += weight * _direct_moment(moved, theta)
            gram[i, j] = g / partition
            dirichlet[i, j] = d / partition
    return {"partition": partition, "gram": gram, "dirichlet": dirichlet}


def boundary_moment_check() -> dict:
    """Boundary-slice moment check at J = 1, x = 1 over the nine angles."""
    ritz = _ritz(1, 1.0)
    states = ritz["states"]
    coefficients = ritz["alpha"]
    assembled = conditional_data(states, coefficients, 0.0)
    selected = [k for k, s in enumerate(states) if s in ((0, 0, 0), (1, 1, 0), (1, 0, 1))]
    keys = ((0, 0, 0), (1, 1, 0), (1, 0, 1))
    order = [list(states).index(k) for k in keys] if all(
        k in [tuple(s) for s in states] for k in keys) else selected

    partitions = []
    grams = []
    dirichlets = []
    for theta in THETA_SLICE:
        direct = direct_conditional_objects(states, coefficients, theta)
        partitions.append(direct["partition"])
        grams.append(direct["gram"][np.ix_(order, order)])
        dirichlets.append(direct["dirichlet"][np.ix_(order, order)])

    gram_assembled = np.asarray(assembled["gram"])[np.ix_(order, order)]
    dirichlet_assembled = np.asarray(assembled["dirichlet"])[np.ix_(order, order)]
    partition_assembled = float(assembled["partition"])

    def worst(sequence, reference):
        return max(float(np.max(np.abs(np.asarray(item) - reference)))
                   for item in sequence)

    return {
        "cutoff": 1,
        "x": 1.0,
        "angles": list(THETA_SLICE),
        "selected_states": [list(states[k]) for k in order],
        "partition_direct": partitions,
        "partition_assembled": partition_assembled,
        "partition_deviation": max(abs(p - partition_assembled) for p in partitions),
        "gram_deviation": worst(grams, gram_assembled),
        "dirichlet_deviation": worst(dirichlets, dirichlet_assembled),
        "partition_spread": max(abs(p - partitions[0]) for p in partitions),
        "gram_spread": worst(grams, grams[0]),
        "dirichlet_spread": worst(dirichlets, dirichlets[0]),
        "gram_direct_theta0": grams[0].tolist(),
        "gram_assembled": gram_assembled.tolist(),
        "dirichlet_direct_theta0": dirichlets[0].tolist(),
        "dirichlet_assembled": dirichlet_assembled.tolist(),
    }


# ---------------------------------------------------------------------------
# Analytic nodal control at J = 1, x = 1 (theory note §9.23, (YM184)-(YM185)).
# ---------------------------------------------------------------------------

ANALYTIC_H1 = np.asarray([
    [4.0, 0.0, 1.0, 1.0],
    [0.0, 8.5, 0.5, 0.5],
    [1.0, 0.5, 7.0, 0.0],
    [1.0, 0.5, 0.0, 7.0],
])


def _raw_state_value(state: State, flip: float) -> float:
    """Value of the state at block data ``(flip * I, I, I, I)``, exterior I."""
    a, b, c = state
    total = 0.0
    for (m_a, m_b, m_c), val0 in _v0(state).items():
        for (n_a, n_b, n_c), val1 in _v1(state).items():
            if m_a != n_a:
                continue
            total += val0 * val1 * _metric(b, n_b, m_b) * _metric(c, n_c, m_c)
    return float(flip ** a) * total


def _state_wavefunction_z(state: State, link_angles: Sequence[float]) -> complex:
    """Evaluate one state for diagonal links ``exp(i phi sigma3/2)``.

    ``link_angles`` is indexed by the seven graph edges.  This is a direct
    magnetic-index contraction, independent of the conditional product
    algebra, and is sufficient for the two sealed nodal paths (and their
    common-angle surface lines).
    """
    if len(link_angles) != 7:
        raise ValueError("link_angles must contain one angle for each graph link")
    a, b, c = state
    angles = tuple(float(v) for v in link_angles)
    total = 0j
    b_angle = angles[1] + angles[2] + angles[3]
    c_angle = angles[4] + angles[5] + angles[6]
    for (m_a, m_b, m_c), val0 in _v0(state).items():
        for (n_a, n_b, n_c), val1 in _v1(state).items():
            if m_a != n_a:
                continue
            eps_b = _metric(b, n_b, m_b)
            eps_c = _metric(c, n_c, m_c)
            if eps_b == 0.0 or eps_c == 0.0:
                continue
            phase = _exterior_phase(a, m_a, angles[0])
            phase *= _exterior_phase(b, n_b, b_angle)
            phase *= _exterior_phase(c, n_c, c_angle)
            total += val0 * val1 * eps_b * eps_c * phase
    return total


def _ritz_wavefunction_z(cutoff: int, coupling: float,
                         link_angles: Sequence[float]) -> complex:
    """Evaluate the Ritz ground-state wavefunction on diagonal link data."""
    row = _ritz(cutoff, coupling)
    return sum(complex(alpha) * _state_wavefunction_z(state, link_angles)
               for state, alpha in zip(row["states"], row["alpha"]))


def nodal_family_endpoint_check() -> dict:
    """Cross-check the sealed J=1, x=1 path-A endpoint amplitudes."""
    angles = (0.0, math.pi, 2.0 * math.pi)
    values = [
        _ritz_wavefunction_z(1, 1.0, (phi, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        for phi in angles
    ]
    references = (2.0941205312136946, 1.0298732237260577,
                 -0.03437408376157913)
    deviations = [abs(value.real - reference)
                  for value, reference in zip(values, references)]
    return {
        "cutoff": 1,
        "x": 1.0,
        "path": "A",
        "angles": list(angles),
        "amplitudes": [float(value.real) for value in values],
        "imaginary_max": max(abs(value.imag) for value in values),
        "references": list(references),
        "deviations": deviations,
        "max_deviation": max(deviations),
        "tolerance": 1e-9,
        "passed": bool(max(deviations) <= 1e-9
                       and max(abs(value.imag) for value in values) <= 1e-9),
    }


def nodal_control() -> dict:
    """Analytic nodal control at J = 1, x = 1."""
    ritz = _ritz(1, 1.0)
    states = ritz["states"]
    coefficients = np.asarray(ritz["alpha"], dtype=float)
    labels, h, s_metric = _hamiltonian(1, 1.0)
    norm = np.sqrt(np.diag(s_metric))
    normalized = h / np.outer(norm, norm)

    identity_weights = np.asarray(
        [(-1.0) ** s[0] for s in states], dtype=float)
    identity_amplitude = float(identity_weights @ coefficients)
    center_amplitude = float(np.sum(coefficients))

    values_identity = [_raw_state_value(s, 1.0) for s in states]
    values_center = [_raw_state_value(s, -1.0) for s in states]
    scale = float(np.mean([abs(v) for v in values_identity]))
    ratio_deviation = max(
        abs(values_center[k] / values_identity[k] - (-1.0) ** states[k][0])
        for k in range(len(states)))
    basis_deviation = max(
        max(abs(abs(values_identity[k]) / scale - 1.0),
            abs(abs(values_center[k]) / scale - 1.0))
        for k in range(len(states)))

    # analytic root 2 s^3 + 15 s^2 + 22 s - 18 in (23/40, 72/125)
    lo, hi = 0.575, 0.576
    def poly(s):
        return 2.0 * s ** 3 + 15.0 * s ** 2 + 22.0 * s - 18.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if poly(lo) * poly(mid) <= 0.0:
            hi = mid
        else:
            lo = mid
    root = 0.5 * (lo + hi)

    return {
        "cutoff": 1,
        "x": 1.0,
        "states": [list(s) for s in states],
        "normalized_hamiltonian": normalized.tolist(),
        "analytic_hamiltonian": ANALYTIC_H1.tolist(),
        "exact_matrix_deviation": float(np.max(np.abs(normalized - ANALYTIC_H1))),
        "identity_amplitude": identity_amplitude,
        "identity_reference": 2.094120531213694,
        "identity_deviation": abs(identity_amplitude - 2.094120531213694),
        "center_amplitude": center_amplitude,
        "center_reference": -0.03437408376157869,
        "center_deviation": abs(center_amplitude + 0.03437408376157869),
        "center_sign_negative": bool(center_amplitude < 0.0),
        "basis_values_identity": values_identity,
        "basis_values_center": values_center,
        "basis_scale": scale,
        "center_value_deviation": ratio_deviation,
        "basis_unit_deviation": basis_deviation,
        "analytic_root": root,
        "analytic_root_residual": abs(poly(root)),
        "analytic_ground_energy": 4.0 - root,
        "ground_energy": float(ritz["ground_energy"]),
        "ground_energy_deviation": abs(ritz["ground_energy"] - (4.0 - root)),
        "analytic_bound_ok": bool(abs(1.0 / (root * math.sqrt(2.0))) - 1.0 < 1.0),
    }


# ---------------------------------------------------------------------------
# Analytic controls.
# ---------------------------------------------------------------------------

def self_check() -> dict:
    checks: dict[str, object] = {}

    checks["cg_spin_half_triplet"] = _cg(1, 1, 2, 1, -1, 0)
    checks["cg_spin_half_singlet"] = _cg(1, 1, 0, 1, -1, 0)
    checks["cg_one_half_coupling"] = _cg(2, 1, 1, 0, 1, 1)

    vacuum = (0, 0, 0)
    fundamental_b = (1, 1, 0)
    fundamental_c = (1, 0, 1)
    checks["chi0_fundamental_vacuum"] = _plaq_element(fundamental_b, vacuum, PATH_B)
    checks["chi1_fundamental_vacuum"] = _plaq_element(fundamental_c, vacuum, PATH_C)
    checks["chi0_fundamental_diagonal"] = _plaq_element(fundamental_b, fundamental_b, PATH_B)
    checks["chi1_fundamental_diagonal"] = _plaq_element(fundamental_c, fundamental_c, PATH_C)
    checks["chi0_vacuum_fundamental_symmetry"] = (
        _plaq_element(vacuum, fundamental_b, PATH_B)
        - _plaq_element(fundamental_b, vacuum, PATH_B))

    labels, chi0, chi1 = _plaq_matrices(2)
    checks["chi_hermiticity_0"] = float(np.max(np.abs(chi0 - chi0.T)))
    checks["chi_hermiticity_1"] = float(np.max(np.abs(chi1 - chi1.T)))
    checks["norm_table_ok"] = all(
        abs(sum(value * value for value in _v0(s).values()) - 1.0) < 1e-12
        and abs(sum(value * value for value in _v1(s).values()) - 1.0) < 1e-12
        for s in _states(3))

    nine_ok = True
    for j in ((1, 1, 0), (1, 0, 1), (2, 2, 0), (1, 1, 2)):
        nine = _nine_j(vacuum, j, j)
        nine_ok = nine_ok and abs(nine * nine - _norm(j)) < 1e-12
        for r in _states(3):
            if r == j:
                continue
            if abs(_nine_j(vacuum, j, r)) > 1e-12:
                nine_ok = nine_ok and False
    checks["ninej_vacuum_identity_ok"] = nine_ok
    checks["nodal_family_endpoint"] = nodal_family_endpoint_check()
    return checks


# ---------------------------------------------------------------------------
# Schedule.
# ---------------------------------------------------------------------------

def schedule(stage: str = "full") -> dict:
    cutoffs = CUTOFFS if stage != "dev" else (1,)
    rows = []
    for n2 in cutoffs:
        for x in COUPLINGS:
            row = _ritz(n2, x)
            rate = block_rate(row["states"], row["alpha"], 0.0)
            labels = rate["data"]["states"]
            weights = rate["data"]["weight_coefficients"]
            rows.append({
                "cutoff": n2,
                "x": x,
                "dimension": row["dimension"],
                "ground_energy": row["ground_energy"],
                "first_excited": row["first_excited"],
                "projected_residual": row["projected_residual"],
                "full_residual": row["full_residual"],
                "full_residual_euclidean": row["full_residual_euclidean"],
                "conditional_rate": rate["rate"],
                "retained_dimension": rate["retained_dimension"],
                "partition": rate["partition"],
                "density_sign_changing": bool(min(weights.values() or [0.0]) < 0.0),
                "ritz_coefficients": {
                    str(s): float(a) for s, a in zip(labels, row["alpha"]) if a != 0.0},
            })
    return {
        "cutoffs": list(cutoffs),
        "couplings": list(COUPLINGS),
        "rows": rows,
        "self_check": self_check(),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--stage", default="full", choices=("full", "dev"))
    args = parser.parse_args(list(argv) if argv is not None else None)

    payload = schedule(args.stage)
    text = json.dumps(payload, indent=2, sort_keys=False, default=float)
    if args.output is not None:
        path = args.output.expanduser().resolve()
        if path.exists():
            print(f"refusing to overwrite {path}", file=sys.stderr)
            return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
