# Collective Plaquette Feshbach Family

## Status: Pre-registered—September 2026

## Abstract

This screen separates the uniform plaquette mode from local fluctuations. The
retained source space contains the all-trivial vacuum and the unnormalized sum
of every fundamental plaquette action on the exact cutoff-one source basis.
The construction is gauge invariant and fixed before the spectral calculation;
its global collective character is part of the evidence boundary. The schedule
uses the seven-link two-plaquette graph and the open $3\times2\times2$ graph at
four fixed couplings. The test asks whether a normalized collective mode has a
volume-stable Feshbach coupling while the local fluctuation sector remains in
$\mathcal Q$.

## 1. Frozen source spaces and collective retained family

Use the exact source and recovered large-volume Hamiltonian fixed by
`computations/verify_yang_mills_exact_block_spectrum.py` and
`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`. The outer
source dimensions are $4$ and $868$. With $S$ the diagonal Haar overlap, $e_0$
the normalized all-trivial vacuum coordinate and

$$
 u_p=S^{-1/2}W_pS^{-1/2}e_0,
$$

define the collective column

$$
 u_{\rm coll}=\sum_{p\in\mathcal P_G}u_p,
 \qquad
 L_R=\operatorname{span}\{e_0,u_{\rm coll}\}.
 \tag{VCF1}
$$

The arithmetic sum, rather than a fitted or volume-dependent weight, is
frozen. Orthonormalization uses singular-value threshold $10^{-10}$ relative
to the largest singular value. The retained source rank and singular values
are recorded on both graphs. A zero-dimensional $\mathcal Q$ is a rank/domain
failure; the row records its ranks, leaves Feshbach-derived quantities
undefined and classifies the run `INCONCLUSIVE`.

## 2. Projected Feshbach blocks

For each graph and coupling, form the normalized Hamiltonian
$\widehat H_{G,x}$, its lowest eigenpair $(E_0,\Omega)$ and measured outer
gap $\Delta_{G,x}$. Project (VCF1) into $\Omega^\perp$ and orthonormalize it
to obtain $V_P$. Define $V_Q$ as the orthonormal complement of
$\{\Omega\}\cup\operatorname{ran}V_P$. The blocks are

$$
 A=V_P^*(\widehat H_{G,x}-E_0)V_P,
 \quad
 B=V_P^*(\widehat H_{G,x}-E_0)V_Q,
 \quad
 D=V_Q^*(\widehat H_{G,x}-E_0)V_Q.
$$

For nonempty $\mathcal Q$, record

$$
 \alpha=\lambda_{\min}(A),
 \qquad
 \delta_Q=\lambda_{\min}(D),
 \qquad
 \beta=\|B\|_2,
$$

and evaluate the resolvent and self-energy bounds at
$\lambda_{\rm test}=\frac12\min(\Delta_{G,x},\delta_Q)$:

$$
 \|(D-\lambda I)^{-1}\|_2\le\frac1{\delta_Q-\lambda},
 \qquad
 \|B(D-\lambda I)^{-1}B^*\|_2
 \le\frac{\beta^2}{\delta_Q-\lambda}.
 \tag{VCF2}
$$

Use

$$
 \Phi(\lambda)=\alpha-\lambda-\frac{\beta^2}{\delta_Q-\lambda}
 \tag{VCF3}
$$

and, when $\Phi(0)>0$,

$$
 \gamma_{\rm Fesh}=
 \frac{\alpha+\delta_Q-
 \sqrt{(\alpha-\delta_Q)^2+4\beta^2}}2.
 \tag{VCF4}
$$

Require a positive direct Schur matrix at the test energy and a measured gap
at least (VCF4) within $10^{-10}$ absolute tolerance. Record the tail-floor
domain as undefined when the smallest discarded eigenvalue is the floor.

## 3. Statistic and decision tree

The primary statistic is the eight-row inventory of retained and projected
ranks, $\alpha$, $\delta_Q$, $\beta$, resolvent and self-energy norms,
positive-root count, root-to-gap ratios, $\beta^2/(\alpha\delta_Q)$ and the
large-to-small ratios of $\alpha$, $\delta_Q$ and $\beta$.

Any source, rank, finite-matrix, residual, inequality, Schur, root, domain or
summary failure is `INCONCLUSIVE`. If all controls pass and all eight rows
have a positive (VCF4) root, classify
`SUPPORTS_FINITE_VOLUME_COLLECTIVE_PLAQUETTE_FAMILY`. If controls pass but one
or more roots are absent, classify `NO_POSITIVE_COLLECTIVE_PLAQUETTE_FAMILY`.

The schedule is fixed at
$x\in\{1/64,1/16,1/4,1\}$. No graph, coupling, vector, weight, rank threshold
or tolerance is added after inspection. The independent checker reconstructs
the scalar bounds, roots, ranks, row schedule, grouped ratios and source
bindings without assembling either graph matrix.

A positive result concerns a global collective retained mode. It supplies no
local volume-uniform theorem by itself, and lattice-spacing, recovery,
continuum and Yang–Mills mass-gap bounds remain open.

## 4. Evidence boundary and receipt

Write the primary receipt once to
`runs/yang_mills_volume_collective_feshbach/verification.json` and the
independent receipt once to
`runs/yang_mills_volume_collective_feshbach/verification-independent.json`.
Refuse to overwrite either receipt. Bind both receipts to this protocol, the
primary and independent sources, the all-local-action source and receipts, the
constant-sector volume-bridge source, the exact seven-link source, the
large-volume source, both large-volume protocols and the recovered large-volume
receipt.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §9.35–§9.37—the finite-volume bridge and retained-family boundaries.
- `computations/yang-mills-volume-adapted-feshbach-prereg.md`—all-local-action source construction and rank boundary.
- `computations/verify_yang_mills_volume_adapted_feshbach.py`—reusable source assembly and Feshbach arithmetic.
- `computations/verify_yang_mills_volume_feshbach_bridge.py`—reusable exact finite-volume matrix helpers.
- `computations/verify_yang_mills_exact_block_spectrum.py`—seven-link exact source and plaquette ordering.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—open $3\times2\times2$ recovered source and plaquette ordering.
