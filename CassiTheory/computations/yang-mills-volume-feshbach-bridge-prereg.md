# Finite-Volume C=0-to-C=1 Feshbach Bridge

## Status: Pre-registered—September 2026

## Abstract

This screen tests whether the canonical one-step retained construction used on
the seven-link two-plaquette graph remains a finite Feshbach certificate on a
larger spatial graph. The retained sector is the exact $C=0$ gauge-invariant
source space, consisting of the single all-trivial representation state. The
outer sector is the complete $C=1$ source space on each graph. The schedule
contains the seven-link two-plaquette graph and the open $3\times2\times2$
graph at four fixed couplings. This is a finite-volume bridge: it tests one
larger graph and supplies no volume-uniform, lattice-spacing-uniform or
continuum mass-gap theorem.

## 1. Frozen graphs and source spaces

The small graph is the seven-link two-plaquette $SU(2)$ graph implemented by
`computations/verify_yang_mills_exact_block_spectrum.py`. The large graph is the
open $3\times2\times2$ graph with twenty links and eleven signed plaquettes
implemented by
`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`. Its exact
spectator-channel recovery is governed by
`computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md` and
its scientific graph and Hamiltonian are fixed by
`computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md`.

Use the doubled link/character cutoff schedule

$$
C_P=0,\qquad C_Q=1,
\qquad x\in\left\{\tfrac1{64},\tfrac1{16},\tfrac14,1\right\}.
$$

The $C=0$ source list must contain exactly one state: every link has doubled
spin $0$ and every sequential four-valent channel is $0$. The outer dimensions
are frozen as

$$
\begin{array}{c|cc}
\text{graph}&\dim L_0&\dim L_1\\\hline
\text{seven-link two-plaquette}&1&4\\
\text{open }3\times2\times2&1&868
\end{array}
$$

The primary must verify the state-list dimensions, the all-trivial retained
state, nested inclusion and the declared graph/source hashes before forming a
Feshbach row. The $C=0$ state is gauge invariant by the exact source basis
construction; no gauge-breaking coordinate truncation is allowed.

## 2. Normalized outer Hamiltonian and blocks

For each graph and coupling, form the normalized outer Hamiltonian

$$
\widehat H_{G,x}=S^{-1/2}H_{G,1}(x)S^{-1/2},
$$

where $S$ is the diagonal Haar overlap supplied by the corresponding exact
source. Let $E_{0,G,x}$ and $\Omega_{G,x}$ be its lowest eigenvalue and
normalized ground vector. Set

$$
\mathcal K_{G,x}=\Omega_{G,x}^{\perp},
\qquad
\mathcal P_{G,x}=\operatorname{ran}
\bigl((I-|\Omega_{G,x}\rangle\langle\Omega_{G,x}|)L_0\bigr),
\qquad
\mathcal Q_{G,x}=\mathcal K_{G,x}\ominus\mathcal P_{G,x}.
$$

The required ranks are $\dim\mathcal P=1$ and
$\dim\mathcal Q=\dim L_1-2$, namely $2$ on the small graph and $866$ on the
large graph. With orthonormal frames $V_P,V_Q$, define

$$
A=V_P^*(\widehat H_{G,x}-E_0)V_P,
\qquad
B=V_P^*(\widehat H_{G,x}-E_0)V_Q,
\qquad
D=V_Q^*(\widehat H_{G,x}-E_0)V_Q.
$$

Record

$$
\alpha=\lambda_{\min}(A),
\qquad
\delta_Q=\lambda_{\min}(D),
\qquad
\beta=\|B\|_2,
\qquad
\Delta_{G,x}=\lambda_1(\widehat H_{G,x})-E_0.
$$

At the frozen test energy

$$
\lambda_{\mathrm{test}}=\tfrac12\min(\Delta_{G,x},\delta_Q),
$$

evaluate the resolvent bound, self-energy bound and scalar Schur bound

$$
\|(D-\lambda I)^{-1}\|_2\le\frac1{\delta_Q-\lambda},
\qquad
\|B(D-\lambda I)^{-1}B^*\|_2
\le\frac{\beta^2}{\delta_Q-\lambda},
\tag{VFB1}
$$

$$
\Phi(\lambda)=\alpha-\lambda-\frac{\beta^2}{\delta_Q-\lambda}>0.
\tag{VFB2}
$$

When $\Phi(0)>0$, record

$$
\gamma_{\mathrm{Fesh}}=
\frac{\alpha+\delta_Q-
\sqrt{(\alpha-\delta_Q)^2+4\beta^2}}2,
\tag{VFB3}
$$

and the ratios $\gamma_{\mathrm{Fesh}}/\Delta_{G,x}$ and
$\beta^2/(\alpha\delta_Q)$. The direct Feshbach matrix must be positive at
$\lambda_{\mathrm{test}}$, and the measured outer gap must not be smaller than
(VFB3) within $10^{-10}$ absolute tolerance.

## 3. Frozen statistic and decision tree

The primary statistic is the eight-row finite-volume bridge inventory:

- positive-root count over the two graphs and four couplings;
- minimum root and minimum root-to-gap ratio by graph;
- maximum self-energy ratio $\beta^2/(\alpha\delta_Q)$ by graph;
- the dimensionless large-to-small ratios of $\alpha$, $\delta_Q$ and $\beta$ at each coupling.

The verifier checks source dimensions and inclusion, finite Hermitian matrices,
ground residual at most $10^{-11}$, the projected ranks, positive floors and
test domain, (VFB1), the direct Schur comparison, root ordering, the
invalid tail-floor domain and all row/group summaries. The large graph's
production matrix is assembled with the recovered spectator-channel identity;
the edge-only candidate support is never used for the Hamiltonian.

Apply the decision tree in this order:

- Any source, graph, matrix, rank, residual, inequality, domain or summary
  failure is `INCONCLUSIVE`.
- If all controls pass and all eight rows have a positive (VFB3) root,
  classify the finite bridge `SUPPORTS_FINITE_VOLUME_FESHBACH_BRIDGE`.
- If all controls pass but one or more rows lack a positive root, classify
  `NO_POSITIVE_FINITE_VOLUME_BRIDGE`.

The run stops after the complete eight-row schedule. No coupling, graph,
cutoff, retained state or tolerance may be added after a result is inspected.
The independent checker reconstructs the scalar arithmetic, dimensions,
source hashes and grouped summaries from the primary receipt without assembling
either graph's matrices. It is an arithmetic and provenance audit, not a
second matrix calculation.

## 4. Evidence boundary and receipt

Write the primary receipt once to
`runs/yang_mills_volume_feshbach_bridge/verification.json` and the independent
receipt once to
`runs/yang_mills_volume_feshbach_bridge/verification-independent.json`.
Refuse to overwrite either receipt. Bind both receipts to this protocol, the
primary and independent sources, the exact seven-link source, the large-volume
recovery source, both large-volume protocols and the existing recovered
finite-volume receipt used as a provenance control.

The $C=0\to C=1$ rows test a constant-sector retained space on two finite
graphs. A positive result cannot establish a spatial-volume-uniform lower
bound because the retained space is not a volume-adapted local block family.
The lattice-spacing, weak-coupling trajectory, recovery transport, continuum
construction and Yang–Mills mass gap remain unresolved.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §9.34—the uniform lower-form criterion and interacting Feshbach boundary.
- `computations/yang-mills-interacting-feshbach-cutoff6-prereg.md`—finite cutoff-six adjacent retained family on the seven-link graph.
- `computations/verify_yang_mills_exact_block_spectrum.py`—small-graph exact source and normalized Hamiltonian.
- `computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md`—large-graph Hamiltonian and basis convention.
- `computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md`—spectator-channel recovery and finite operator controls.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—large-graph recovered matrix assembly.
