# Loop-Carrying Exterior Conditional Fibre Study

## Status: Pre-registered—September 2026

## Abstract

The seven-link cutoff study of
`computations/yang-mills-exact-block-spectral-prereg.md` closes with an
orbit identity: every block-integrated conditional moment is a function of
the gauge orbit of the exterior data, and a tree exterior has a single
orbit, so that graph cannot probe boundary dependence at all. This study
replaces the tree exterior by a closed plaquette attached to the block at a
single vertex, so the exterior orbit space is one conjugacy class of
$SU(2)$. It then measures the block-conditional partition, Gram, Dirichlet
and retained fibre rate as functions of the exterior loop holonomy at fixed
couplings and character cutoffs. The target is finite-lattice evidence about
the boundary dependence of the fibre rate that enters (YM29), (YM151) and
(YM170). Graph, truncation, coupling schedule, boundary family, tolerances
and stopping rule are fixed here before implementation. Surviving rows
supply cutoff-qualified evidence only; uniform boundary control, cutoff
removal, the thermodynamic limit and the continuum mass gap remain separate
analytical obligations.

## 1. Question and scope

For a block of four links and an exterior carrying one closed plaquette, does
the block-conditional measure of the cutoff-projected Ritz ground state
depend on the exterior loop holonomy, and is its retained conditional
Poincare rate bounded below uniformly over the holonomy domain at fixed
coupling?

Two outcomes are informative. A measurable holonomy dependence shows that
the orbit reduction is nondegenerate and fixes the domain over which the
fibre-rate obligation must be quantified. A holonomy-independent result at
every cutoff extends the tree-exterior collapse to a one-loop exterior for
the declared test space. Neither outcome supplies a cutoff-uniform or
continuum statement.

## 2. Graph and Hamiltonian

Use eight links and seven vertices. The block plaquette is

\[
p_A=(0,1)(1,2)(3,2)(0,3),
\]

with block links $0,1,2,3$. The exterior plaquette is

\[
p_B=(0,4)(4,5)(6,5)(0,6),
\]

with exterior links $4,5,6,7$. The two plaquettes share exactly the vertex
$0$ and no link, so the exterior links form one closed loop attached to the
block at a single vertex and the exterior gauge orbit space is
$\{\text{conjugacy classes of }SU(2)\}$.

The regulated dimensionless Hamiltonian is

\[
h_x=K+2xN_p-xS,
\qquad
K=-\sum_{e,A}(X_e^A)^2,
\qquad
S=\sum_{p}\operatorname{Tr}U_p,
\qquad
N_p=2,
\]

with the same conventions, Haar normalization and plaquette orientation
rules as the seven-link study.

## 3. Truncation and basis

Truncate each link to doubled spins $2j\le J$ with

\[
J\in\{1,2,3\},
\]

and use gauge-invariant spin-network states of the eight-link graph with the
declared trivalent intertwiner convention of the seven-link study. The
Ritz vector is the lowest eigenvector of the truncated Hamiltonian matrix,
computed by the same dense symmetric eigensolver, and the endpoint residual
uses the cutoff-$J+1$ extension.

## 4. Boundary family

Fix the exterior data in the gauge-fixed representative

\[
U_4=U_5=U_6=I,
\qquad
U_7=e^{i\theta\sigma_3/2},
\qquad
\theta=\frac{k\pi}{8},\ k=0,\ldots,8,
\]

so the exterior plaquette holonomy runs over a full conjugacy-class slice
from the identity to the antipode. The block links remain integrated.

## 5. Observables

For each scheduled $(J,x,\theta)$ with

\[
x\in\left\{\tfrac14,1,4,16\right\},
\]

measure:

1. the conditional partition $Z(\theta)$, the restricted Gram matrix, the
   covariance, and the Dirichlet form on the same retained test space as the
   seven-link study, all divided by $Z(\theta)$;
2. the retained conditional Poincare rate $\lambda_{\mathrm{ret}}(\theta)$,
   the removed constant direction, and the restriction rank;
3. the full-space and projected residuals, and the nested-inclusion residual
   against the previous cutoff;
4. the analytic control that the eight-link vertex contractions reproduce
   the declared normalization, by exact Haar/Clebsch-Gordan contraction with
   no Monte Carlo sampling.

## 6. Decision tree and thresholds

Freeze the following before execution.

| Rule | Threshold | Verdict |
|---|---|---|
| Orbit nondegeneracy | $\max_\theta|\log Z(\theta)|\le10^{-8}$ at every cutoff | `NULL_ORBIT_COLLAPSE` |
| Orbit nondegeneracy | the same quantity exceeds $10^{-8}$ at some cutoff | `SUPPORTS_BOUNDARY_SENSITIVITY` |
| Fibre uniformity | $\min_\theta\lambda_{\mathrm{ret}}/\max_\theta\lambda_{\mathrm{ret}}\ge\tfrac12$ at the largest converged cutoff for every $x$ | `SUPPORTS_UNIFORM_RETAINED_FIBRE` |
| Fibre non-uniformity | the same ratio is below $\tfrac14$ at some $x$ | `INCONSISTENT_RETAINED_FIBRE` |
| Collapse witness | $\lambda_{\mathrm{ret}}<10^{-3}$ at a scheduled row | `CONDITIONAL_COLLAPSE_WITNESS` |
| Qualification | full-space residual $>10^{-2}$, or a rank change against the previous cutoff | row is `INCONCLUSIVE`, reported literally |

A row whose cutoff-$J$ full-space residual exceeds the bound is reported as
executed and carries no rate verdict. No threshold may be relaxed after
execution, and no row is averaged over $\theta$ to produce a rate claim.

## 7. Stopping rule and evidence boundary

One execution of the full schedule, single run, no re-run after inspection.
The receipt must bind this protocol, the source
`computations/verify_yang_mills_bowtie_fibre.py`, any shared algebra module
it imports, the schedule, the graph and the measured tables by SHA-256, and
must refuse to overwrite an existing receipt. The receipt records the
classification of every scheduled row plus the summary counts.

## 8. Obligations unchanged

This study does not supply the exact-vacuum fibre rate, the transport score,
cutoff removal, uniform interacting recovery, the thermodynamic limit or the
continuum construction. It measures the boundary dependence of a
cutoff-projected retained rate on the smallest graph whose exterior carries a
loop.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.14, 9.21–9.23—conditional block rate, transport score, orbit identity and continuum obligations.
- `computations/yang-mills-exact-block-spectral-prereg.md`—seven-link graph, truncation, coupling schedule and qualification rules.
- `computations/verify_yang_mills_exact_block_spectrum.py`—tree-exterior primary receipt and analytic nodal control.
- `computations/yang_mills_conditional_algebra.py`—shared representation, Haar-contraction and conditional-moment conventions.
