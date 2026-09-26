# Finite-Volume SU(2) Wilson Schwinger Bridge in Two Dimensions

## Status: Invalidated normalization—September 2026

The active specification is
`computations/yang-mills-su2-wilson-2d-prereg-v2.md`. In this retained defect
record, the quantity \(2I_n(\beta)/\beta\) is written as the coefficient
multiplying \(\chi_n\) and then divided by \(n\) during gluing. Normalized Haar
orthogonality instead gives the direct coefficient \(2nI_n(\beta)/\beta\) and
the once-divided gluing eigenvalue \(2I_n(\beta)/\beta\). The unversioned
receipts carry no active evidence claim.

## Abstract

This protocol constructs a gauge-projected SU(2) Wilson transfer matrix on a periodic two-dimensional lattice by character expansion. The spatial length, temporal length, character cutoff, and coupling schedule are fixed before implementation. The primary uses modified Bessel functions; the independent implementation evaluates the same coefficients from their positive series and reconstructs the transfer spectrum, correlator, and tail bound without importing the primary source.

The calculation is a finite-volume two-dimensional benchmark for the quantum Schwinger-function layer. It supplies an exact character-expansion tail bound for the declared two-dimensional Wilson model. The four-dimensional Yang–Mills construction, its thermodynamic limit, and its physical mass gap require a separate transfer matrix with nontrivial spatial gauge degrees of freedom.

## 1. Model and gauge projection

Use normalized Haar measure on SU(2), irreducible characters \(\chi_j\), and representation dimension
\[
d_j=2j+1=:n,
\qquad n=1,2,3,\ldots.
\]
For a plaquette angle \(\theta\),
\[
\operatorname{Tr}U=2\cos\theta,
\qquad
w_\beta(U)=\exp\left(\frac\beta2\operatorname{Tr}U\right)=e^{\beta\cos\theta}.
\]
The normalized character expansion is
\[
w_\beta(U)=\sum_{j\ge0}c_j(\beta)\chi_j(U),
\qquad
c_j(\beta)=\frac{2}{\beta}I_{2j+1}(\beta),
\]
where \(I_n\) is the modified Bessel function of the first kind. Gluing a plaquette strip and integrating every internal link projects onto the gauge-invariant character sector. The transfer eigenvalue for representation index \(n\) on one spatial plaquette is
\[
r_n(\beta)=\frac{c_j(\beta)}{d_j}
=\frac{2I_n(\beta)}{\beta n}.
\]

For spatial length \(L_s\) and temporal length \(L_t\), the gauge-projected transfer eigenvalues and torus partition function are
\[
\Lambda_n=r_n^{L_s},
\qquad
Z_{L_s,L_t}(\beta)=\sum_{n\ge1}r_n(\beta)^{A},
\qquad
A=L_sL_t.
\]
The finite character regulator retains \(n\le N\):
\[
Z_{N,L_s,L_t}(\beta)=\sum_{n=1}^{N}r_n(\beta)^A.
\]

## 2. Gauge-invariant Schwinger observable

Use the fundamental Wilson character
\[
O=\chi_{1/2}.
\]
Character fusion gives
\[
\chi_{1/2}\chi_j=\chi_{j+1/2}+\chi_{j-1/2},
\]
so \(O\) maps the vacuum character \(\chi_0\) to \(\chi_{1/2}\) with matrix element one. The normalized vacuum-subtracted Euclidean correlator at integer temporal separation \(t\ge0\) is therefore
\[
C_{L_s,\beta}(t)
=\left(\frac{r_2(\beta)}{r_1(\beta)}\right)^{L_st}.
\]
For every declared cutoff \(N\ge2\), the finite-regulator correlator has this same value because the observable orbit from the vacuum lies inside the retained character sector. Its effective mass in lattice time units is
\[
m_{\mathrm{eff}}(L_s,\beta)
=-\log\frac{C(t+1)}{C(t)}
=L_s\log\frac{r_1(\beta)}{r_2(\beta)}.
\]
The value is independent of \(t\), which is an exact transfer-matrix identity for this two-dimensional benchmark.

## 3. Frozen schedule

\[
\beta\in\{1,2,4\},
\qquad
L_s,L_t\in\{1,2,4\},
\qquad
N\in\{8,16,24,32\},
\qquad
t\in\{0,1,2,4\}.
\]
The primary has 108 rows, the Cartesian product of the three couplings, nine
\((L_s,L_t)\) pairs and four character cutoffs. Each row evaluates the
correlator at the four declared temporal separations. Each row checks:

1. positivity of every scheduled \(I_n(\beta)\) coefficient;
2. strict decrease of \(r_n\) over the retained indices;
3. the transfer-eigenvalue formula;
4. the exact character-fusion correlator at all four declared \(t\) values;
5. the effective-mass identity for the corresponding one-step ratios;
6. the positive character-tail bound;
7. the finite partition function and tail-bound ordering;
8. the fixed gauge-projected area identity \(A=L_sL_t\).

The two time-dependent predicates are aggregate row checks over the four
declared \(t\) values; the time schedule changes the recorded values, not the
row or total-check count. The primary therefore has exactly 864 row checks
plus 12 schedule and source-integrity checks, for 876 checks.

The independent receipt has exactly 120 checks:

- 12 protocol, source, schema, schedule, and primary-integrity checks;
- one complete reconstruction for each of the 108 rows.

## 4. Certified character tail

For \(n\ge1\), the positive Bessel series gives
\[
I_n(\beta)
=\sum_{k=0}^{\infty}
\frac{(\beta/2)^{2k+n}}{k!\,\Gamma(k+n+1)}
\le
\frac{(\beta/2)^n}{n!}e^{\beta^2/4}.
\]
Consequently,
\[
r_n(\beta)
\le
q_n(\beta):=
\frac{2e^{\beta^2/4}}{\beta n}
\frac{(\beta/2)^n}{n!}.
\]
For the schedule \(\beta\le4\) and \(n\ge N+1\ge9\), the ratio satisfies
\[
\frac{q_{n+1}}{q_n}
=\frac{\beta n}{2(n+1)^2}
\le
\rho_{N,\beta}:=
\frac{\beta(N+1)}{2(N+2)^2}<1.
\]
The omitted partition weight has the certified bound
\[
0\le R_{N,A}(\beta)
:=\sum_{n>N}r_n(\beta)^A
\le
\frac{q_{N+1}(\beta)^A}{1-\rho_{N,\beta}^{A}}.
\]
The receipt records \(R_{N,A}\), \(Z_{N,L_s,L_t}\), and the relative bound
\[
R_{N,A}/Z_{N,L_s,L_t}.
\]
It also records the natural logarithms of the bound and relative bound, so
strict positivity remains visible when a binary64 power underflows. Its scope
is the declared two-dimensional Wilson model; four-dimensional transfer
matrices and interacting exact vacua require separate estimates.

## 5. Implementations and receipts

The primary implementation is:

`computations/verify_yang_mills_su2_wilson_2d.py`

The independent implementation is:

`computations/verify_yang_mills_su2_wilson_2d_independent.mjs`

The primary receipt is:

`runs/yang_mills_su2_wilson_2d/verification.json`

The independent receipt is:

`runs/yang_mills_su2_wilson_2d/verification-independent.json`

The primary evaluates \(I_n\) with the installed numerical library and binds the protocol and source hashes. The independent implementation evaluates the positive Bessel series with its own termination rule and reconstructs every scheduled row, including the tail bound. It does not import the primary implementation or read primary matrices.

The primary refuses to overwrite an existing receipt. The independent receipt binds the protocol, both source files and the primary receipt by SHA-256. Primary matrix and scalar tolerance is \(10^{-11}\); independent scalar comparison tolerance is \(10^{-9}\). The Bessel-series remainder is bounded by the first omitted term and the declared geometric ratio; it is never fitted to the primary output.

## 6. Decision rule and scope

`PASS` requires all 876 primary checks and all 120 independent checks to pass, with source identities and frozen counts matching the protocol.

`FAIL` records any coefficient, fusion, transfer, correlator, effective-mass, tail-bound, source-identity or count failure.

`INCONCLUSIVE` records missing execution or missing tail-bound data.

A `PASS` establishes a gauge-projected finite-volume two-dimensional Wilson benchmark with a certified character tail. It supplies a construction component for the quantum Schwinger-function pipeline. Spatial degrees of freedom in four-dimensional Yang–Mills, the four-dimensional thermodynamic limit, OS reconstruction and a nonzero physical mass gap remain separate obligations.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.4–9.9, 9.18–9.23—regulated SU(2) Hamiltonians, exact vacuum measure and the continuum boundary.
- `computations/yang-mills-su2-schwinger-prereg-v2.md`—finite one-plaquette vacuum correlator construction.
- Clay Mathematics Institute, *Yang–Mills and Mass Gap*—continuum target.
