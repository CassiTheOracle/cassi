# Nested-Cutoff Interacting Feshbach Screen

## Status: Pre-registered—September 2026

## Abstract

This screen measures the interacting discarded-sector resolvent and Feshbach
self-energy across nested spin-network cutoffs on the existing seven-link
two-plaquette $SU(2)$ Hamiltonian. It extends the fixed pair
$(c_P,c_Q)=(1,3)$ calculation to every nested pair with
$1\le c_P<c_Q\le5$ and the four declared couplings. The output is a finite
cutoff-family screen: it records whether the Schur certificate survives the
scheduled enlargement of the retained and full spaces, while the regulator-,
volume- and continuum-uniform lower bound remain separate obligations.

## 1. Fixed graph and nested spaces

Use the seven-link graph, plaquette words, exact representation contractions
and generalized Hamiltonian implemented by
`computations/verify_yang_mills_exact_block_spectrum.py`. The source cutoff is
the doubled-spin maximum used by `SpectrumSpace(cutoff)`. The scheduled basis
dimensions are $4,11,23,42,69$ at cutoffs $1,2,3,4,5$.

For each outer cutoff $c_Q\in\{2,3,4,5\}$ and each inner cutoff
$c_P\in\{1,\ldots,c_Q-1\}$, construct the normalized Hamiltonian

$$
\widehat H_x=S^{-1/2}H_xS^{-1/2},
\qquad x\in\left\{\tfrac14,1,4,16\right\}.
$$

Let $E_0$ and $\Omega$ be the lowest eigenvalue and normalized eigenvector of
the outer-cutoff matrix. Work in the vacuum-orthogonal space
$\mathcal K=\Omega^\perp$. Let $L_{c_P}$ be the coordinate subspace spanned
by the nested inner-cutoff states. Its projected image defines

$$
\mathcal P_{c_P,c_Q}
:=\operatorname{ran}\bigl((I-|\Omega\rangle\langle\Omega|)L_{c_P}\bigr),
\qquad
\mathcal Q_{c_P,c_Q}:=\mathcal K\ominus\mathcal P_{c_P,c_Q}.
$$

Use orthonormal frames $V_P,V_Q$ and the shifted blocks

$$
A=V_P^*(\widehat H_x-E_0)V_P,
\qquad
B=V_P^*(\widehat H_x-E_0)V_Q,
\qquad
D=V_Q^*(\widehat H_x-E_0)V_Q.
$$

The expected ranks are
$\dim\mathcal P=\dim L_{c_P}$ and
$\dim\mathcal Q=\dim L_{c_Q}-1-\dim L_{c_P}$.

## 2. Finite Feshbach certificate

Set

$$
\alpha=\lambda_{\min}(A),
\qquad
\delta_Q=\lambda_{\min}(D),
\qquad
\beta=\|B\|_2.
$$

At the scheduled test energy

$$
\lambda_{\mathrm{test}}=\frac12\min(\Delta_{c_Q,x},\delta_Q),
$$

where $\Delta_{c_Q,x}$ is the lowest positive eigenvalue of the outer
matrix after removal of $\Omega$, evaluate

$$
\left\|(D-\lambda I)^{-1}\right\|_2
\le \frac1{\delta_Q-\lambda},
\tag{CF1}
$$

and

$$
\left\|B(D-\lambda I)^{-1}B^*\right\|_2
\le \frac{\beta^2}{\delta_Q-\lambda}.
\tag{CF2}
$$

The sufficient scalar Schur bound is

$$
\Phi(\lambda)=\alpha-\lambda-
\frac{\beta^2}{\delta_Q-\lambda}>0.
\tag{CF3}
$$

When $\Phi(0)>0$, record

$$
\gamma_{\mathrm{Fesh}}
=\frac{\alpha+\delta_Q-
\sqrt{(\alpha-\delta_Q)^2+4\beta^2}}{2}.
\tag{CF4}
$$

The measured outer-cutoff gap must be no smaller than (CF4) within the
specified numerical tolerance whenever the positive root exists. Record the
ratio $\beta^2/(\alpha\delta_Q)$, the root-to-gap ratio and the minimum root
for each coupling after grouping all scheduled inner/outer pairs.

## 3. Frozen schedule and executable checks

The primary schedule contains the ten nested cutoff pairs

$$
(c_P,c_Q)\in
\{(1,2),(1,3),(2,3),(1,4),(2,4),(3,4),
(1,5),(2,5),(3,5),(4,5)\}
$$

at every $x\in\{1/4,1,4,16\}$, for $40$ rows total. The verifier checks:

1. every scheduled pair has the declared source dimensions and nested-state
   inclusion;
2. the normalized outer Hamiltonian is finite and Hermitian, and the ground
   residual is at most $10^{-11}$;
3. the post-ground-projection ranks equal the declared $\mathcal P/\mathcal Q$
   dimensions;
4. $\alpha>0$ and $\delta_Q>0$;
5. (CF1) and (CF2) hold at $\lambda_{\mathrm{test}}$ to relative tolerance
   $10^{-10}$;
6. the direct Feshbach matrix is positive and its minimum eigenvalue is no
   smaller than $\Phi(\lambda_{\mathrm{test}})$ within $10^{-10}$ absolute
   tolerance;
7. every positive (CF4) root is below the measured outer-cutoff gap within
   $10^{-10}$ absolute tolerance;
8. the tail-floor control records $\lambda=\delta_Q$ as an invalid resolvent
   point without evaluating an inverse there;
9. the family summary reproduces the row count, pair schedule and grouped
   minimum root-to-gap statistics.

The primary classification is `SUPPORTS_FINITE_CUTOFF_FESHBACH_FAMILY` only
when all $40$ rows have positive (CF4) roots and every check passes. If the
finite identities and controls pass while one or more rows lack a positive
root, classify `NO_POSITIVE_FAMILY_CERTIFICATE`. Any source, rank, residual,
inequality, domain or summary failure is `INCONCLUSIVE`.

The independent checker reconstructs (CF1)--(CF4), the row dimensions,
source hashes, schedule and family summaries from the primary receipt without
assembling the $SU(2)$ matrices. Its classification is
`ARITHMETIC_AND_BINDING_AUDIT_ONLY` and its scope records that matrix
reassembly is not performed.

## 4. Evidence boundary and receipt

Write the primary receipt once to
`runs/yang_mills_interacting_feshbach_cutoff/verification.json`; refuse to
overwrite an existing file. Write the independent receipt once to
`runs/yang_mills_interacting_feshbach_cutoff/verification-independent.json`.
Bind both receipts to this protocol, the primary verifier, the exact-block
source and the appropriate predecessor receipt/source. Record all values as
finite, dimensionless quantities on the fixed graph.

The ten-pair schedule tests a finite outer cutoff of at most $5$. It supplies
no constant uniform in lattice spacing, spatial volume, coupling trajectory
or continuum recovery, and it supplies no mass-gap theorem. The next analytic
step after a positive screen is an interacting family estimate whose
constants remain controlled as the graph, outer cutoff and physical scaling
are enlarged.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.19.2 and 9.34—boundary-sector Feshbach operator and uniform lower-form criterion.
- `computations/yang-mills-interacting-feshbach-prereg.md`—fixed $(c_P,c_Q)=(1,3)$ finite certificate.
- `computations/verify_yang_mills_exact_block_spectrum.py`—exact seven-link Hamiltonian and nested source spaces.
- `computations/yang-mills-exact-block-spectral-prereg.md`—cutoff and coupling conventions.
