# Finite SU(2) Conditional Transport Qualification

## Status: Pre-registered—September 2026

## Abstract

This protocol qualifies the conditional transport diagnostic on the sealed
seven-link SU(2) block calculation. It separates three finite-regulator
questions: whether the scheduled boundary variation changes the conditional
density, whether the density is strictly positive where a logarithmic score is
required, and whether the resulting Galerkin Poisson problem has a finite
cutoff value. The graph's exterior links form a gauge-transitive forest. If
that isometry is verified, the boundary derivative is exactly zero and the
transport quadratic form is structurally zero wherever the logarithmic score is
defined. Such a zero is not evidence for a positive transport margin. A
certified node or an absent positivity certificate leaves the corresponding
row `INCONCLUSIVE`.

The calculation is finite-cutoff evidence. It does not establish an
all-boundary transport estimate, representation-cutoff removal, a
volume-uniform recovery bound, a thermodynamic limit, an
Osterwalder–Schrader construction, or a continuum Yang–Mills mass gap.

## 1. Question and fixed input

For the cutoff Ritz measures from
`computations/yang-mills-exact-block-spectral-prereg.md`, does the scheduled
exterior conjugacy angle produce a nonzero conditional score, and is that
score defined on a strictly positive density?

The graph, Hamiltonian, cutoff schedule, coupling schedule, boundary angles,
and tangent angles are inherited from the exact-block protocol. The sealed
input is
`runs/yang_mills_exact_block_spectrum/verification.json`. Its source and
protocol hashes must match the current exact-block source and
`computations/yang-mills-exact-block-spectral-prereg.md`; a mismatch aborts the
qualification.

The transport receipt binds this protocol, the exact-block source, the
conditional product algebra, the sealed exact-block receipt, and every
materialized score-space matrix. It refuses to overwrite an existing receipt.

## 2. Positivity certificate

A logarithmic score is formed only when the conditional Ritz density has a
strictly positive analytic enclosure. No sampled minimum, floating-point
floor, finite-difference logarithm, or regularization substitutes for that
certificate.

For a basis state psi_s, the two trivalent Wigner-3j tensors are unit
vectors by the orthogonality identity, the invariant link metrics are
orthogonal, and the link representation matrices are unitary. The
Cauchy–Schwarz inequality therefore gives

$$
|\psi_s(U_B,\eta)|\le 1.
$$

The implementation verifies the normalization identities of every
representation table through the largest scheduled score cutoff and records
the resulting enclosure. If the Ritz coefficients are
\(\alpha_s\), then

$$
\Omega_J(U_B,\eta)
\ge |\alpha_{0}|-\sum_{s\ne0}|\alpha_s|
$$

up to the measured representation-table enclosure. A strictly positive lower
bound certifies the row. The analytic \(J=1,x=1\) nodal control remains a
required negative control; it certifies a zero and forces every corresponding
score row to `INCONCLUSIVE`.

## 3. Boundary derivative and score spaces

The conditional product algebra is evaluated on the complete scheduled
boundary-angle set and compared with the independent direct boundary
contraction at doubled cutoff one. The required identity is

$$
\partial_\theta\rho_{B,J}^{\mathrm{Ritz},\eta}=0
$$

because the exterior forest is removed by a gauge isometry. A numerical zero
alone is not promoted to a derivative claim; the receipt records the exact
algebraic identity and the direct reconstruction errors.

For every strictly positive row, use the full block-compatible score spaces
with doubled score cutoffs

$$
J_s=J+\tfrac12,\qquad J_s=J+1,
$$

remove their constant direction, and retain their dimensions and basis map.
The exact boundary identity gives

$$
b_a=\langle\partial_\theta\rho,\phi_a\rangle=0.
$$

The Dirichlet matrix is a Gram matrix,

$$
(D_s)_{ab}=\sum_{e\in B,A}
\langle X_e^A\phi_a,X_e^A\phi_b\rangle_\rho,
$$

so \(D_s\succeq0\) for every certified positive row. The zero solution
\(u=0\) satisfies

$$
D_su=b,
\qquad
\vartheta_{B,J,J_s}^{2,\mathrm{Gal}}=b^*D_s^+b=0.
$$

The primary materializes the score matrices for doubled Ritz cutoffs
through four. For doubled cutoff five, the declared structural-zero shortcut
records the full score-space basis and its dimension, the exact zero right-hand
side, and the Gram-form positive-semidefinite certificate without constructing
the dense matrix. The exact boundary identity and the analytic Gram positivity
are the controlling certificate; no nonzero transport quantity is inferred
from an unmaterialized matrix.

## 4. Fixed schedule and stopping rules

The schedule is:

- doubled Ritz cutoffs \(C\in\{1,2,3,4,5\}\);
- couplings \(x\in\{1/4,1,4,16\}\);
- boundary angles \(\theta/\pi\in\{0,1/8,1/4,3/8,1/2,5/8,3/4,7/8,1\}\);
- interior tangent angles \(\theta/\pi\in\{1/4,1/2,3/4\}\);
- score-cutoff offsets \(J_s-J\in\{1/2,1\}\).

A row is classified as follows:

- `CERTIFIED_POSITIVE_STRUCTURAL_ZERO` when the positivity enclosure passes and
the boundary-isometry identity gives a zero score;
- `INCONCLUSIVE_CERTIFIED_NODE` when the analytic nodal control applies;
- `INCONCLUSIVE_NO_POSITIVITY_CERTIFICATE` when strict positivity is not
certified;
- `FAIL` when the direct boundary reconstruction, representation norm
certificate, score-space construction, or finite residual check fails.

The study classification is `INCONCLUSIVE` whenever any scheduled row is
nodal, lacks a positivity certificate, or has only a structural zero score.
No row may be reported as a positive transport witness from this graph.

A full structural run has a 1,800-second wall-clock bound. The bound includes
the materialized score matrices through doubled cutoff four and the declared
structural-zero shortcut at doubled cutoff five. A timeout is an execution
failure, not a scientific classification; the receipt must not be written.

## 5. Evidence boundary

A passing execution verifies only the finite qualification mechanics and the
negative transport implication of this boundary schedule. The next
transport calculation must use a graph with a nontrivial boundary cycle or a
boundary observable that is not removed by the exterior forest isometry. The
physical Yang–Mills mass-gap problem still requires uniform interacting
vacuum estimates, cutoff removal, thermodynamic and continuum Schwinger
functions, and a positive gauge-invariant spectral gap.

## References

- `computations/yang-mills-exact-block-spectral-prereg.md`—exact seven-link Hamiltonian, cutoff Ritz state, conditional rate, and score definitions.
- `computations/verify_yang_mills_exact_block_spectrum.py`—primary exact representation and direct boundary-contraction implementation.
- `computations/yang_mills_conditional_algebra.py`—finite SU(2) product algebra used for conditional moments.
- `computations/verify_yang_mills_su2_transport_expansion.py`—independent local-chart transport control.
- `foundations/loop-to-bubble-projection-theorem.md` §§9.14, 9.21–9.22—conditional transport and continuum obligations.
