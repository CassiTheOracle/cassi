# Finite-Regulator SU(2) Schwinger-Function Bridge

## Status: Pre-registered—September 2026

## Abstract

This protocol constructs vacuum Euclidean correlators for a finite character-cutoff SU(2) one-plaquette Hamiltonian. The transfer calculation uses the positive ground state of the declared finite Hamiltonian, rather than a projected wavefunction density on the full group. A Python implementation and an independent JavaScript reconstruction bind the same finite matrices, spectra, correlators, and source identities.

The result is a quantum finite-regulator bridge and a test of the correlator pipeline. Its scope ends at the declared one-plaquette character-cutoff model. Character-cutoff removal, multi-plaquette volume growth, the thermodynamic limit, the four-dimensional continuum theory, and a physical Yang–Mills mass gap require separate work.

## 1. Question and scope

For the finite SU(2) character-cutoff Hamiltonian below, can the vacuum state and gauge-invariant Euclidean two-point function be constructed with independent numerical verification?

The Hilbert space is the class-function sector of one SU(2) plaquette. With normalized characters
\[
|j\rangle=\chi_j,
\qquad
j=0,\tfrac12,1,\ldots,J,
\]
Haar orthogonality makes this basis orthonormal. The dimensionless Hamiltonian at lattice spacing \(a=1\) is
\[
H_{g^2}
=
\frac{g^2}{2}C_2
+\frac1{g^2}\bigl(2I-V\bigr),
\qquad
C_2|j\rangle=j(j+1)|j\rangle,
\]
where \(V\) is multiplication by the fundamental character:
\[
\chi_{1/2}\chi_j=\chi_{j+1/2}+\chi_{j-1/2}.
\]
At doubled-spin index \(n=2j\),
\[
V_{nm}=1\quad\text{when }|n-m|=1,
\qquad V_{nm}=0\quad\text{otherwise}.
\]
For a finite cutoff \(N=2J\), the regulator is the finite matrix
\[
H_{N,g^2}=P_NH_{g^2}P_N,
\qquad
O_N=P_NV P_N.
\]
The finite regulator is the declared model. No infinite-character tail estimate is inferred from this protocol.

The Euclidean connected vacuum correlator is
\[
C_{N,g^2}(t)
=\langle 0|O_Ne^{-t(H_{N,g^2}-E_0)}O_N|0\rangle
-\langle0|O_N|0\rangle^2,
\]
with \(|0\rangle\) the normalized lowest eigenvector. In the spectral basis,
\[
C_{N,g^2}(t)
=\sum_{k>0}
\left|\langle k|O_N|0\rangle\right|^2
 e^{-t(E_k-E_0)}.
\]
The effective mass uses \(\Delta t=1/2\):
\[
m_{\mathrm{eff}}(t)
=-\frac1{\Delta t}
\log\frac{C(t+\Delta t)}{C(t)}.
\]

## 2. Frozen schedule

Use doubled-spin cutoffs
\[
N\in\{8,16,24,32\},
\]
and couplings
\[
g^2\in\{\tfrac12,1,2\}.
\]
For each of the twelve \((N,g^2)\) rows, evaluate
\[
t\in\{0,\tfrac12,1,2\},
\qquad
\Delta t=\tfrac12.
\]
The correlator at \(t+\Delta t\) is also retained. The fundamental character is the sole observable.

The primary receipt has exactly eight row checks for every scheduled row, for 96 checks total:

1. Hamiltonian symmetry;
2. observable symmetry;
3. normalized ground-state residual;
4. Perron sign certificate;
5. positive first excitation gap;
6. nonnegative connected correlator at every scheduled time;
7. effective mass not below the finite-matrix spectral gap;
8. the operator bound \(C(0)\le4\).

The independent receipt has exactly 20 checks:

- eight protocol, source, schema, row-count, and primary-integrity checks;
- one complete reconstruction for each of the twelve scheduled rows.

## 3. Finite-regulator positivity and numerical sign certificate

The off-diagonal entries of \(H_{N,g^2}\) are strictly negative on the connected nearest-neighbour character chain. The finite matrix is therefore an irreducible real symmetric Z-matrix. Its lowest eigenvalue is simple and its exact eigenvector has one strict sign after phase choice by the Perron–Frobenius theorem.

Floating-point eigenvectors can underflow in high character components. The numerical receipt therefore certifies the sign structure rather than requiring every subnormal component to be represented as a strictly positive binary64 number. For matrix dimension \(d=N+1\), define
\[
\tau_{\mathrm{sign}}
=256\,\epsilon_{\mathrm{mach}}\,d\,\max\{1,\|H_{N,g^2}\|_\infty\}.
\]
The row passes its numerical Perron sign check when the phase-fixed first coefficient is positive and
\[
\min_n v_n\ge-\tau_{\mathrm{sign}}.
\]
The exact strict positivity is supplied by the irreducible-Z-matrix lemma; \(\tau_{\mathrm{sign}}\) only bounds unresolved floating-point sign noise and is recorded per row.

The finite Hamiltonian is real symmetric. Its spectral decomposition gives a nonnegative connected correlator and
\[
m_{\mathrm{eff}}(t)
\ge E_1-E_0
\]
for every scheduled time at which the correlator is positive. The observable satisfies \(\|O_N\|\le2\), so
\[
0\le C(0)\le \|O_N\|^2\le4.
\]

These are finite-matrix statements. Observed changes with \(N\) are recorded as cutoff diagnostics; no convergence threshold promotes them to a character-cutoff theorem.

## 4. Implementations and receipts

The primary implementation is:

`computations/verify_yang_mills_su2_schwinger_bridge.py`

The independent implementation is:

`computations/verify_yang_mills_su2_schwinger_bridge_independent.mjs`

The primary receipt is:

`runs/yang_mills_su2_schwinger_bridge/verification-v2.json`

The independent receipt is:

`runs/yang_mills_su2_schwinger_bridge/verification-independent-v2.json`

The independent implementation constructs the tridiagonal matrices from the frozen formulas, uses its own symmetric Jacobi eigensolver, recomputes the spectral correlator, and compares only against the primary receipt after checking the protocol and source hashes. It does not import the Python implementation or consume serialized primary matrices.

The primary refuses to overwrite an existing receipt. Both receipts bind the protocol and source files by SHA-256. The independent receipt also binds the primary receipt and asserts all frozen row and check counts.

The primary tolerance for matrix residuals is \(10^{-11}\); the independent comparison tolerance is \(10^{-9}\). The sign tolerance is the formula above, with no fitted or row-specific multiplier.

## 5. Decision rule

`PASS` requires every primary and independent check to pass, with all source hashes and counts matching the frozen protocol.

`FAIL` records any matrix, spectral, positivity, correlator, effective-mass, source-identity, or count failure.

`INCONCLUSIVE` records missing execution or missing bound evidence.

A `PASS` supports the finite character-cutoff vacuum and Schwinger-function construction. It supplies no character-cutoff removal, volume-uniform estimate, thermodynamic limit, continuum reconstruction, or four-dimensional mass-gap theorem.

## 6. Next boundary

A subsequent protocol must supply a controlled route from this finite positive matrix to a sequence of spatial volumes and character cutoffs. It must state either a rigorous truncation-error bound or a new exact finite-regulator definition whose continuum relation is proved separately. The present receipt must remain classified as finite-regulator evidence.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.4–9.9, 9.18–9.23—regulated SU(2) Hamiltonians, exact vacuum measure, and the unresolved continuum boundary.
- `computations/yang-mills-exact-block-spectral-prereg.md`—finite spin-network cutoff conventions and the distinction between cutoff diagnostics and limiting claims.
- Clay Mathematics Institute, *Yang–Mills and Mass Gap*—problem statement and continuum target.
