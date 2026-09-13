# Finite-Volume SU(2) Quantum Schwinger-Function Generator in Two Dimensions

## Status: Invalidated normalization—September 2026

The active specification is
`computations/yang-mills-su2-quantum-schwinger-2d-prereg-v2.md`. This retained
defect record imports the double-divided Wilson transfer eigenvalue from the
unversioned two-dimensional protocol. Its v1 receipts carry no active evidence
claim.

## Abstract

This protocol defines a finite-volume quantum Schwinger-function generator for the SU(2) Wilson transfer matrix in two Euclidean dimensions. The transfer spectrum is built from the exact positive character coefficients of the Wilson plaquette weight. The primary Python source and an independent JavaScript source reconstruct the same finite transfer Hamiltonian, gauge-invariant character observables, vacuum correlators, and effective masses.

The study is separate from the pre-registered larger-volume Hamiltonian target. It does not read, write, or claim a receipt for that target. Its scope is the declared finite two-dimensional transfer model. Character-cutoff removal, spatial-volume growth beyond the frozen schedule, Osterwalder–Schrader reconstruction in four dimensions, and a physical Yang–Mills mass gap remain separate obligations.

## 1. Model and finite quantum transfer matrix

Use normalized SU(2) characters indexed by the doubled spin
\[
n=2j+1=1,2,3,\ldots.
\]
For Wilson coupling \(\beta>0\), define
\[
w_\beta(U)=\exp\!\left(\frac{\beta}{2}\operatorname{Tr}U\right)
=\sum_{j\ge0}c_j(\beta)\chi_j(U),
\qquad
c_j(\beta)=\frac{2}{\beta}I_{2j+1}(\beta).
\]
Write \(n=2j+1\) and
\[
r_n(\beta):=\frac{c_j(\beta)}{n}
=\frac{2I_n(\beta)}{\beta n}.
\]

For a spatial circle of length \(L_s\), the finite character-cutoff transfer matrix is diagonal in the character basis:
\[
T_{N,L_s,\beta}=\operatorname{diag}\bigl(r_1(\beta)^{L_s},
 r_2(\beta)^{L_s},\ldots,r_N(\beta)^{L_s}\bigr).
\]
The normalized finite transfer Hamiltonian is
\[
H_{N,L_s,\beta}:=-\log\!\left(\frac{T_{N,L_s,\beta}}
{r_1(\beta)^{L_s}}\right),
\qquad
E_n=L_s\log\frac{r_1(\beta)}{r_n(\beta)}.
\]
Thus \(E_1=0\), and a strictly decreasing positive sequence \(r_n\) gives a unique vacuum and positive finite-regulator gaps.

## 2. Gauge-invariant observables and Schwinger functions

For doubled-spin channel \(k\in\{1,2,3\}\), let \(O_k\) be multiplication by \(\chi_{k/2}\) projected to the retained character space. Its matrix entries are the SU(2) fusion rule
\[
(O_k)_{mn}=1
\quad\Longleftrightarrow\quad
m-1\in\{|k-(n-1)|,|k-(n-1)|+2,\ldots,k+n-1\},
\quad 1\le m\le N,
\]
and are zero otherwise. The vacuum vector is \(|0\rangle=e_1\). For every scheduled cutoff \(N\ge8\),
\[
O_k|0\rangle=e_{k+1},
\qquad
\langle0|O_k|0\rangle=0.
\]

The connected Euclidean vacuum correlator is
\[
C_{k,N,L_s,\beta}(t)
:=\langle0|O_k e^{-tH_{N,L_s,\beta}}O_k|0\rangle
-\langle0|O_k|0\rangle^2
=\exp\!\left(-tE_{k+1}\right).
\]
The declared time increment is \(\delta t=1/2\), and the effective mass is
\[
m_{\mathrm{eff},k}(t)
:=-\frac1{\delta t}
\log\frac{C_k(t+\delta t)}{C_k(t)}
=E_{k+1}.
\]
The semigroup check is
\[
C_k(t+\delta t)=C_k(t)\exp(-\delta tE_{k+1}).
\]
These are finite transfer-matrix identities, not continuum statements.

## 3. Frozen schedule

Use
\[
\beta\in\{1,2,4\},
\qquad
L_s\in\{1,2,4\},
\qquad
N\in\{8,16,24,32\},
\]
with channels
\[
k\in\{1,2,3\},
\qquad
 t\in\{0,\tfrac12,1,2,4\},
\qquad
\delta t=\tfrac12.
\]
There are \(3\times3\times4=36\) parameter rows. Every row contains all three channels and all five scheduled times plus the corresponding \(t+\delta t\) values.

Each row has exactly eleven checks:

1. all retained Wilson coefficients and transfer eigenvalues are finite and positive;
2. the finite diagonal transfer matrix is symmetric;
3. the transfer eigenvalues are strictly decreasing in \(n\);
4. the normalized ground energy is zero and every retained excited energy is positive;
5. every declared fusion observable is finite and symmetric;
6. each vacuum orbit satisfies \(O_k|0\rangle=e_{k+1}\);
7. every scheduled connected correlator is finite and nonnegative;
8. every effective mass equals the declared spectral energy;
9. every semigroup ratio equals \(\exp(-\delta tE_{k+1})\);
10. every fusion operator obeys \(\|O_k\|\le k+1\);
11. the complete row payload contains no non-finite value.

The primary receipt therefore contains exactly 396 row checks and six top-level checks. Its top-level checks record the protocol/source identities, schedule cardinality, row count, finite payload, row-check aggregate, and verdict.

The independent receipt contains eight of its own top-level identity/count checks and one complete independent reconstruction for each of the 36 rows. It must recompute the Wilson coefficients from an independent positive Bessel-series implementation; it may not import the Python source, read serialized primary matrices, or treat primary numerical values as its model definition.

## 4. Independent coefficient construction

The primary uses the installed modified-Bessel implementation. The independent source evaluates
\[
I_n(\beta)=\sum_{q=0}^{\infty}
\frac{(\beta/2)^{2q+n}}{q!\,\Gamma(q+n+1)}
\]
with a positive-term stopping rule and verifies that the final omitted term is below its declared numerical tolerance. The two implementations then reconstruct \(r_n\), \(E_n\), the fusion matrices, and all scheduled correlators independently.

No fitted tail, extrapolated cutoff, stochastic sampling error, or continuum estimate is part of this protocol.

## 5. Implementations and receipts

The primary implementation is:

`computations/verify_yang_mills_su2_quantum_schwinger_2d.py`

The independent implementation is:

`computations/verify_yang_mills_su2_quantum_schwinger_2d_independent.mjs`

The primary receipt is:

`runs/yang_mills_su2_quantum_schwinger_2d/verification-v1.json`

The independent receipt is:

`runs/yang_mills_su2_quantum_schwinger_2d/verification-independent-v1.json`

Both receipts bind this protocol and their source files by SHA-256. The independent receipt also binds the primary receipt and reports its own reconstructed row metrics. The primary refuses to overwrite an existing receipt.

## 6. Decision rule and scope

`PASS` requires every primary row and top-level check to pass, every independent reconstruction to agree within the declared tolerance, all source/protocol hashes to match, and all frozen counts to match.

`FAIL` records any coefficient, transfer, fusion, vacuum-orbit, correlator, effective-mass, semigroup, finiteness, source-identity, or count failure.

`INCONCLUSIVE` records missing execution or missing finite-value evidence.

A `PASS` supports the finite-volume two-dimensional quantum Schwinger-function generator for the declared Wilson transfer model. It supplies no character-cutoff removal, uniform spatial-volume estimate, thermodynamic limit, four-dimensional continuum construction, or regulator-independent Yang–Mills mass gap.

## References

- `computations/yang-mills-su2-wilson-2d-prereg.md`—finite-volume SU(2) Wilson character expansion and tail control.
- `computations/yang-mills-su2-schwinger-prereg-v2.md`—finite one-plaquette Hamiltonian correlator bridge.
- `computations/yang-mills-exact-block-spectral-prereg.md`—finite spin-network Hamiltonian conventions.
- `foundations/loop-to-bubble-projection-theorem.md` §§9.13–9.21—regulated vacuum measure and the unresolved continuum boundary.
- Clay Mathematics Institute, *Yang–Mills and Mass Gap*—continuum target.
