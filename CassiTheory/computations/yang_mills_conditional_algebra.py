"""Finite SU(2) product algebra for the conditional block matrices.

The seven-link network collapses, after integrating the exterior forest
(1--5--4--0), to the three-strand theta network.  Haar changes of variables
that send the exterior links to the identity act unitarily on the four block
links, so all quantities returned here are independent of ``theta``.  This is
an isometry of the conditional fibre, not a gauge fixing of the Hamiltonian.

A state is labelled by doubled spins ``(a,b,c)`` and uses the literal
trivalent intertwiner convention of the experiment.  Its unweighted norm is

    n_(a,b,c) = 1 / ((a+1)(b+1)(c+1)).

For two states ``i,j`` and a fused admissible label ``r=(A,B,C)``, the product
coefficient is obtained by the standard CG/9j recoupling identity

    psi_i psi_j = sum_r p[i,j,r] psi_r,
    p[i,j,r] = (A+1)(B+1)(C+1)
                * { a_i b_i c_i ; a_j b_j c_j ; A B C }^2.

The positive square removes phase choices in the 9j recoupling.  Consequently
``int psi_i psi_j psi_r = 9j^2`` and the moment of a product weight is
``M_r = q_r n_r``.  For a real Ritz vector ``omega=sum_s alpha_s psi_s``:

    q_r = sum_s,t alpha_s alpha_t p[s,t,r],
    G_ij = sum_r p[i,j,r] q_r n_r,
    D_ij = 1/2 sum_r (kB_i+kB_j-kB_r) p[i,j,r] q_r n_r,

where ``kB_(a,b,c)=C(a/2)+3 C(b/2)``. The partition is
``Z=int omega^2=sum_s alpha_s^2 n_s=q_(0,0,0)``. The returned ``gram`` and
``dirichlet`` are divided by Z. The covariance subtracts the outer product
of the normalized means ``mean_i=q_i n_i/Z``.

The implementation keeps all matrices Hermitian up to roundoff and does not
symmetrize them before returning them.  In particular, the product-rule
formula gives zero Dirichlet entries whenever both arguments are the constant
state ``(0,0,0)`` (whose Casimir is zero and whose sole product coefficient is
one).
"""

from __future__ import annotations

import math
from functools import lru_cache
from fractions import Fraction
from typing import Mapping, Sequence

import numpy as np
from sympy import Rational
from sympy.physics.wigner import wigner_9j

State = tuple[int, int, int]


def _state(value: Sequence[int]) -> State:
    if len(value) != 3:
        raise ValueError(f"state must have three doubled spins, got {value!r}")
    out = tuple(int(x) for x in value)
    if any(x < 0 for x in out):
        raise ValueError(f"doubled spins must be non-negative, got {out!r}")
    a, b, c = out
    if (a + b + c) & 1 or not (abs(a - b) <= c <= a + b):
        raise ValueError(f"inadmissible triangle/parity state {out!r}")
    return out


def _fusion_values(x: int, y: int) -> range:
    """Doubled-spin labels in ``x/2 tensor y/2``."""
    return range(abs(x - y), x + y + 1, 2)


def _admissible(a: int, b: int, c: int) -> bool:
    return (a + b + c) % 2 == 0 and abs(a - b) <= c <= a + b


def _dim(state: State) -> float:
    a, b, c = state
    return float((a + 1) * (b + 1) * (c + 1))


def _norm(state: State) -> float:
    return 1.0 / _dim(state)


def _casimir(n2: int) -> float:
    j = 0.5 * n2
    return j * (j + 1.0)


def _k_block(state: State) -> float:
    a, b, _ = state
    return _casimir(a) + 3.0 * _casimir(b)


@lru_cache(maxsize=None)
def _nine_j(i: State, j: State, r: State) -> float:
    """Numerical standard Wigner 9j, with doubled labels at the interface."""
    args = tuple(Rational(x, 2) for row in (i, j, r) for x in row)
    return float(wigner_9j(*args).evalf(30))


@lru_cache(maxsize=None)
def _product(i: State, j: State) -> tuple[tuple[State, float], ...]:
    """Return all nonzero CG/9j product coefficients for ``psi_i psi_j``."""
    out: list[tuple[State, float]] = []
    for a in _fusion_values(i[0], j[0]):
        for b in _fusion_values(i[1], j[1]):
            for c in _fusion_values(i[2], j[2]):
                if not _admissible(a, b, c):
                    continue
                r = (a, b, c)
                nine = _nine_j(i, j, r)
                if nine == 0.0:
                    continue
                # The dimensional prefactor is d_r.  With i=(0,0,0),
                # {0,0,0;j;j}=1/sqrt(d_j), hence p[0,j,j]=1.
                out.append((r, _dim(r) * nine * nine))
    return tuple(out)


def _coefficient_map(states: Sequence[State], coefficients: Sequence[float]) -> dict[State, float]:
    result: dict[State, float] = {}
    for state, coeff in zip(states, coefficients):
        result[state] = result.get(state, 0.0) + float(coeff)
    return result


def conditional_data(
    states: Sequence[Sequence[int]],
    coefficients: Mapping[Sequence[int], float] | Sequence[float],
    theta: float,
) -> dict[str, object]:
    """Compute exact conditional Gram, covariance, and block Dirichlet data.

    Parameters
    ----------
    states:
        Ordered labels ``(a,b,c)`` in doubled-spin units.  Every label must
        satisfy the triangle and even-parity rules.
    coefficients:
        Real Ritz coefficients, either a mapping keyed by state labels or a
        sequence aligned with ``states``.  The wavefunction is linear in these
        values; they are not squared before forming products.
    theta:
        Exterior conjugacy angle.  The forest gauge-isometry makes the exact
        result theta-independent; it is accepted explicitly for API
        compatibility and converted to float to reject nonnumeric values.

    Returns
    -------
    dict
        ``states`` (normalized tuple labels), positive ``partition``, raw
        diagonal ``restriction_gram``, unnormalized weighted ``gram_raw`` and
        ``dirichlet_raw``, and normalized ``gram``, ``covariance``, and
        ``dirichlet``.  The primary consumes the latter three plus partition.
    """
    theta = float(theta)  # explicit no-op: exterior forest isometry
    labels = tuple(_state(s) for s in states)
    if len(set(labels)) != len(labels):
        raise ValueError("states must not contain duplicate labels")
    if isinstance(coefficients, Mapping):
        alpha = np.asarray([float(coefficients.get(s, coefficients.get(tuple(s), 0.0))) for s in labels], dtype=float)
    else:
        alpha = np.asarray(list(coefficients), dtype=float)
        if alpha.shape != (len(labels),):
            raise ValueError("coefficient sequence must align with states")
    if not np.all(np.isfinite(alpha)):
        raise ValueError("coefficients must be finite real numbers")

    # Product tables for all input pairs.  The fused labels are the complete
    # intermediate basis; no product is silently projected back to `states`.
    products: dict[tuple[State, State], tuple[tuple[State, float], ...]] = {}
    closure: set[State] = set()
    for i in labels:
        for j in labels:
            terms = _product(i, j)
            products[(i, j)] = terms
            closure.update(r for r, value in terms if value != 0.0)

    # q is the coefficient vector of omega^2 in the complete fused basis.
    q: dict[State, float] = {r: 0.0 for r in closure}
    for si, i in enumerate(labels):
        if alpha[si] == 0.0:
            continue
        for sj, j in enumerate(labels):
            if alpha[sj] == 0.0:
                continue
            scale = float(alpha[si] * alpha[sj])
            for r, value in products[(i, j)]:
                q[r] = q.get(r, 0.0) + scale * value

    partition = math.fsum(float(value * value * _norm(s)) for s, value in zip(labels, alpha))
    if not math.isfinite(partition) or partition <= 1.0e-15:
        raise ValueError(f"non-positive or non-finite conditional partition {partition!r}")

    n = np.asarray([_norm(s) for s in labels], dtype=float)
    raw_restriction = np.diag(n).astype(complex)
    gram_raw = np.zeros((len(labels), len(labels)), dtype=complex)
    dirichlet_raw = np.zeros_like(gram_raw)
    for ii, i in enumerate(labels):
        ki = _k_block(i)
        for jj, j in enumerate(labels):
            kj = _k_block(j)
            terms = products[(i, j)]
            g = 0.0
            d = 0.0
            for r, p in terms:
                moment = q.get(r, 0.0) * _norm(r)
                g += p * moment
                d += 0.5 * (ki + kj - _k_block(r)) * p * moment
            gram_raw[ii, jj] = g
            dirichlet_raw[ii, jj] = d

    # E[conj(psi_i)] = q_i n_i / Z.  q_i is zero when the input state does
    # not occur in the complete product expansion.
    mean_raw = np.asarray([q.get(s, 0.0) * _norm(s) for s in labels], dtype=complex)
    gram = gram_raw / partition
    mean = mean_raw / partition
    covariance = gram - np.outer(np.conj(mean), mean)
    dirichlet = dirichlet_raw / partition

    return {
        "states": labels,
        "partition": float(partition),
        "restriction_gram": raw_restriction,
        "gram_raw": gram_raw,
        "dirichlet_raw": dirichlet_raw,
        "gram": gram,
        "covariance": covariance,
        "dirichlet": dirichlet,
        "mean": mean,
        "product_coefficients": products,
        "weight_coefficients": q,
    }


__all__ = ["conditional_data"]
