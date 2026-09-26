# Volume-Adapted Reserved-Plaquette Feshbach Family

## Status: Pre-registered—September 2026

## Abstract

This screen tests a volume-adapted retained family that grows with the number
of local plaquettes while reserving one plaquette as a nonempty exterior test
sector. The retained space contains the vacuum and the fundamental plaquette
actions for every plaquette except the lexicographically final plaquette in
the frozen source ordering. The schedule uses the seven-link two-plaquette
graph and the open $3\times2\times2$ graph at four fixed couplings. The
reserved plaquette keeps the discarded Feshbach sector nonempty on the small
graph, where retaining every local action exhausts the projected space.

## 1. Frozen source spaces and retained family

Use the exact source and recovered large-volume Hamiltonian fixed by
`computations/verify_yang_mills_exact_block_spectrum.py` and
`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`. The outer
source spaces have dimensions $4$ and $868$. The plaquette order is the source
order in `exact.PLAQUETTES` for the seven-link graph and `large.PLAQUETTES` for
the open graph. Let $p_*$ be the final plaquette in that order.

With $S$ the diagonal Haar overlap, $e_0$ the normalized all-trivial vacuum
coordinate and

$$
 u_p=S^{-1/2}W_pS^{-1/2}e_0,
$$

define the retained source family

$$
 L_R=\operatorname{span}\{e_0,u_p:p\ne p_*\}.
 \tag{VAF2-1}
$$

The reserved plaquette is never inserted into $L_R$. No vector is selected
from a spectrum. The family is gauge invariant and local because each column
is a fundamental Wilson-loop action on the vacuum. Numerical rank uses the
frozen singular-value threshold $10^{-10}$ relative to the largest singular
value. The retained source column counts are $2$ on the small graph and $11$
on the large graph before rank reduction.

## 2. Projected Feshbach blocks

For each graph and coupling, form the normalized Hamiltonian
$\widehat H_{G,x}$, its lowest eigenpair $(E_0,\Omega)$ and measured outer
gap $\Delta_{G,x}$. Project (VAF2-1) into $\Omega^\perp$ and orthonormalize it
to obtain $V_P$. Define $V_Q$ as the orthonormal complement of
$\{\Omega\}\cup\operatorname{ran}V_P$. The Feshbach blocks are

$$
 A=V_P^*(\widehat H_{G,x}-E_0)V_P,
 \quad
 B=V_P^*(\widehat H_{G,x}-E_0)V_Q,
 \quad
 D=V_Q^*(\widehat H_{G,x}-E_0)V_Q.
$$

A zero-dimensional $\mathcal Q$ is a rank/domain failure. In that case the
row records its source and projected ranks, leaves all Feshbach-derived
quantities undefined, and the run classifies `INCONCLUSIVE`.

For nonempty $\mathcal Q$, record

$$
 \alpha=\lambda_{\min}(A),
 \qquad
 \delta_Q=\lambda_{\min}(D),
 \qquad
 \beta=\|B\|_2.
$$

At $\lambda_{\rm test}=\frac12\min(\Delta_{G,x},\delta_Q)$, evaluate the
resolvent, self-energy matrix and direct Schur matrix. Require the bounds

$$
 \|(D-\lambda I)^{-1}\|_2\le\frac1{\delta_Q-\lambda},
 \qquad
 \|B(D-\lambda I)^{-1}B^*\|_2
 \le\frac{\beta^2}{\delta_Q-\lambda}.
 \tag{VAF2-2}
$$

Use

$$
 \Phi(\lambda)=\alpha-\lambda-\frac{\beta^2}{\delta_Q-\lambda}
 \tag{VAF2-3}
$$

and, when $\Phi(0)>0$,

$$
 \gamma_{\rm Fesh}=
 \frac{\alpha+\delta_Q-
 \sqrt{(\alpha-\delta_Q)^2+4\beta^2}}2.
 \tag{VAF2-4}
$$

The measured gap must be at least (VAF2-4) within $10^{-10}$ absolute
tolerance. The tail-floor domain is recorded as undefined when the smallest
discarded eigenvalue is the floor itself.

## 3. Statistic and decision tree

The primary statistic is the eight-row inventory containing the retained and
projected ranks, $\alpha$, $\delta_Q$, $\beta$, direct resolvent and
self-energy norms, positive-root count, root-to-gap ratios, the
self-energy ratio $\beta^2/(\alpha\delta_Q)$, and the large-to-small ratios
of $\alpha$, $\delta_Q$ and $\beta$.

Any source, rank, finite-matrix, residual, inequality, Schur, root, domain or
summary failure is `INCONCLUSIVE`. If all controls pass and all eight rows
have a positive (VAF2-4) root, classify
`SUPPORTS_FINITE_VOLUME_RESERVED_PLAQUETTE_FAMILY`. If controls pass but one
or more roots are absent, classify `NO_POSITIVE_RESERVED_PLAQUETTE_FAMILY`.

The screen stops after the fixed eight-row schedule. No graph, coupling,
plaquette, vector, rank threshold or tolerance is added after inspection.
The independent checker reconstructs the scalar bounds, root formulas, ranks,
row schedule, grouped ratios and source bindings from the primary receipt
without assembling either graph matrix.

A positive result establishes a finite reserved-plaquette bridge only. It does
not establish a volume-uniform bound, lattice-spacing limit, continuum
construction or Yang–Mills mass gap.

## 4. Evidence boundary and receipt

Write the primary receipt once to
`runs/yang_mills_volume_adapted_feshbach_v2/verification.json` and the
independent receipt once to
`runs/yang_mills_volume_adapted_feshbach_v2/verification-independent.json`.
Refuse to overwrite either receipt. Bind both receipts to this protocol, the
primary and independent sources, the v1 volume-adapted source and receipts,
the constant-sector volume-bridge source, the exact seven-link source, the
large-volume source, both large-volume protocols and the recovered large-volume
receipt.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §9.34 and §9.35—the lower-form criterion and finite-volume bridge boundary.
- `computations/yang-mills-volume-adapted-feshbach-prereg.md`—vacuum-plus-all-plaquettes family and its rank/domain boundary.
- `computations/verify_yang_mills_volume_adapted_feshbach.py`—v1 source and recorded rank/domain outcome.
- `computations/verify_yang_mills_volume_feshbach_bridge.py`—reusable exact finite-volume source and matrix helpers.
- `computations/verify_yang_mills_exact_block_spectrum.py`—seven-link exact source and plaquette ordering.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—open $3\times2\times2$ recovered source and plaquette ordering.
