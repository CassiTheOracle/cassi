# Cutoff-Six Interacting Feshbach Family Screen

## Status: Pre-registered—September 2026

## Abstract

This screen extends the nested interacting Feshbach calculation to outer
source cutoff $c_Q=6$ on the existing seven-link two-plaquette $SU(2)$ graph.
The schedule contains every nested pair
$1\le c_P<c_Q\le6$ at the four declared couplings. The adjacent pairs
$c_P=c_Q-1$ form the primary one-step growth family: at each outer cutoff,
the retained space is the complete gauge-invariant source space immediately
below it. The remaining nested pairs are scheduled diagnostics of retained-
space dependence. The result is a finite cutoff screen. It does not assert a
bound uniform in lattice spacing, spatial volume, coupling trajectory or the
continuum limit.

## 1. Fixed graph and source spaces

Use the seven-link graph, plaquette words, exact representation contractions
and generalized Hamiltonian implemented by
`computations/verify_yang_mills_exact_block_spectrum.py`. The source cutoff is
the doubled-spin maximum used by `SpectrumSpace(cutoff)`. The frozen source
dimensions are

$$
\dim L_1,\ldots,\dim L_6=(4,11,23,42,69,106).
$$

For every outer cutoff $c_Q\in\{2,3,4,5,6\}$ and every inner cutoff
$c_P\in\{1,\ldots,c_Q-1\}$, use the normalized Hamiltonian

$$
\widehat H_x=S^{-1/2}H_xS^{-1/2},
\qquad x\in\left\{\tfrac14,1,4,16\right\}.
$$

The coordinate space $L_{c_P}$ is spanned by all source states at the inner
cutoff. These states are exact gauge-invariant spin-network states, so the
nested coordinate spaces are the declared finite-graph gauge-compatible
family. Let $E_0$ and $\Omega$ be the lowest eigenvalue and normalized
ground vector of the outer-cutoff matrix. Define

$$
\mathcal K=\Omega^\perp,
\qquad
\mathcal P_{c_P,c_Q}=\operatorname{ran}
\bigl((I-|\Omega\rangle\langle\Omega|)L_{c_P}\bigr),
\qquad
\mathcal Q_{c_P,c_Q}=\mathcal K\ominus\mathcal P_{c_P,c_Q}.
$$

The expected ranks are

$$
\dim\mathcal P_{c_P,c_Q}=\dim L_{c_P},
\qquad
\dim\mathcal Q_{c_P,c_Q}=\dim L_{c_Q}-1-\dim L_{c_P}.
$$

Use orthonormal frames $V_P,V_Q$ and shifted blocks

$$
A=V_P^*(\widehat H_x-E_0)V_P,
\qquad
B=V_P^*(\widehat H_x-E_0)V_Q,
\qquad
D=V_Q^*(\widehat H_x-E_0)V_Q.
$$

## 2. Frozen statistic and finite certificate

For each row record

$$
\alpha=\lambda_{\min}(A),
\qquad
\delta_Q=\lambda_{\min}(D),
\qquad
\beta=\|B\|_2,
$$

and evaluate the resolvent and Schur inequalities at

$$
\lambda_{\mathrm{test}}
=\tfrac12\min(\Delta_{c_Q,x},\delta_Q),
$$

where $\Delta_{c_Q,x}$ is the first excited eigenvalue above $E_0$ of the
outer-cutoff matrix. The controls are

$$
\|(D-\lambda I)^{-1}\|_2
\le {1\over\delta_Q-\lambda},
\tag{S1}
$$

$$
\|B(D-\lambda I)^{-1}B^*\|_2
\le {\beta^2\over\delta_Q-\lambda},
\tag{S2}
$$

and

$$
\Phi(\lambda)=\alpha-\lambda-{\beta^2\over\delta_Q-\lambda}>0.
\tag{S3}
$$

When $\Phi(0)>0$, record the sufficient finite root

$$
\gamma_{\mathrm{Fesh}}
=\frac{\alpha+\delta_Q-
\sqrt{(\alpha-\delta_Q)^2+4\beta^2}}{2},
\tag{S4}
$$

along with $\gamma_{\mathrm{Fesh}}/\Delta_{c_Q,x}$ and
$\beta^2/(\alpha\delta_Q)$. The direct Feshbach matrix must be positive at
$\lambda_{\mathrm{test}}$, and its minimum eigenvalue must be no smaller than
$\Phi(\lambda_{\mathrm{test}})$ within the declared numerical tolerance.

The primary statistic is the adjacent-family minimum

$$
\Gamma_{\mathrm{adj}}=
\min_{\substack{2\le c_Q\le6\\x\in\{1/4,1,4,16\}}}
\gamma_{\mathrm{Fesh}}(c_Q-1,c_Q,x),
$$

when every adjacent row has a positive root. Also record the adjacent-family
minimum root-to-gap ratio and maximum self-energy ratio. The ten non-adjacent
rows are part of the fixed schedule and are reported separately; their root
status cannot be omitted or replaced by an adaptive choice.

## 3. Execution checks and decision tree

The primary verifier must check:

1. all fifteen nested pairs and all four couplings are present, giving $60$
   rows, with dimensions $4,11,23,42,69,106$;
2. every nested state set is included in its outer source space;
3. every normalized outer Hamiltonian is finite and Hermitian, and its ground
   residual is at most $10^{-11}$;
4. every post-ground-projection rank equals the declared $\mathcal P/\mathcal Q$
   dimension;
5. $\Delta_{c_Q,x}>0$, $\alpha>0$, $\delta_Q>0$ and
   $0\le\lambda_{\mathrm{test}}<\delta_Q$;
6. (S1) and (S2) hold to relative tolerance $10^{-10}$;
7. the direct Feshbach matrix is positive and satisfies the (S3) lower-bound
   comparison within $10^{-10}$ absolute tolerance;
8. every positive (S4) root is no larger than the measured outer gap within
   $10^{-10}$ absolute tolerance;
9. the tail-floor control marks $\lambda=\delta_Q$ as outside the resolvent
   domain without evaluating an inverse there;
10. the row schedule and grouped family statistics reproduce the frozen counts.

Apply the decision tree in this order:

- If any execution, source, rank, residual, inequality, domain or schedule
  control fails, classify the run `INCONCLUSIVE`.
- If all controls pass and all twenty adjacent rows have positive (S4) roots,
  classify the finite primary family `SUPPORTS_FINITE_ADJACENT_FAMILY`.
- If all controls pass but at least one adjacent row has no positive root,
  classify it `NO_POSITIVE_ADJACENT_FAMILY_CERTIFICATE`.
- Report the non-adjacent rows as retained-space diagnostics under the same
  finite-control status. No diagnostic row changes the adjacent-family
  classification.

The primary run is stopped after the complete sixty-row schedule. No coupling,
cutoff or retained pair may be added after inspecting a result. No repeated
trial, threshold tuning or post hoc schedule selection is permitted.

The independent checker reconstructs the scalar arithmetic in (S1)--(S4),
the dimensions and row schedule, the family summaries and all source hashes
from the primary receipt without assembling the $SU(2)$ matrices. Its result
is an arithmetic and provenance audit, not a second matrix calculation.

## 4. Evidence boundary and receipt

Write the primary receipt once to
`runs/yang_mills_interacting_feshbach_cutoff6/verification.json` and the
independent receipt once to
`runs/yang_mills_interacting_feshbach_cutoff6/verification-independent.json`.
Refuse to overwrite either receipt. Bind both receipts to this protocol, the
primary and independent sources, the exact-block source, and the predecessor
cutoff-family source and receipt. Record finite dimensionless values on the
fixed graph.

The screen reaches outer cutoff $6$ on one finite graph. It supplies no
constant uniform in lattice spacing, spatial volume, weak-coupling trajectory
or continuum recovery, and it supplies no Yang–Mills mass-gap theorem. A
positive adjacent-family result would identify a finite growth pattern for the
next analytic task: bounding $\alpha$, $\delta_Q$ and $\beta$ uniformly for a
gauge-compatible family on growing graphs and along the physical scaling
trajectory.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §9.34—uniform lower-form criterion and interacting Feshbach boundary.
- `computations/yang-mills-interacting-feshbach-cutoff-screen-prereg.md`—all-pair cutoff screen through outer cutoff $5$.
- `computations/verify_yang_mills_exact_block_spectrum.py`—exact seven-link Hamiltonian and nested gauge-invariant source spaces.
- `computations/yang-mills-exact-block-spectral-prereg.md`—cutoff and coupling conventions.
