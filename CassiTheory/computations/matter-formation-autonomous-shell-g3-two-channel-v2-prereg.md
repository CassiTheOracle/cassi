# Autonomous Incoming-Shell Formation: G3 Two-Channel Precision Continuation

## Status: Hypothesized conditional two-channel protocol—September 2026

## Abstract

This protocol evolves the degenerate $\kappa=-1$ and $\kappa=+1$ spherical
Dirac sectors with their full normal-ordered scalar backreaction. It retains
the G3 finite-core action, shell, vacuum preparation, controls, observables,
energy ledger, candidate predicates and grid schedule while using a temporal
step small enough for direct independent state reconstruction.

The calculation tests whether the radial capture survives the leading
opposite-parity $j=1/2$ channel. The background is spherically symmetric, so
these two angular sectors evolve independently while contributing to one
scalar source. A positive result qualifies this finite-core two-channel model;
it does not establish all-$\kappa$ stability or a continuum particle theory.

## 1. Action, channels and source

Use

$$
\mathcal L=\frac12\partial_\mu\sigma\partial^\mu\sigma
-\frac{\lambda}{4}(\sigma^2-v^2)^2
+\bar\psi(i\gamma^\mu\partial_\mu-g\sigma)\psi,
$$

with

$$
(v,\lambda,g,R,A,r_s,w,a_c,T)=(1,\tfrac14,3,16,0.75,4,2,0.5,12).
$$

For $\kappa\in\{-1,+1\}$ use

$$
H_\kappa(\sigma)=
\begin{pmatrix}
 g\sigma&-D+\kappa c_{a_c}(r)\\
 D+\kappa c_{a_c}(r)&-g\sigma
\end{pmatrix},
\qquad
c_{a_c}(r)=\frac1{\sqrt{r^2+a_c^2}},
\qquad a_c=0.5.
$$

Each channel has magnetic degeneracy $d_\kappa=2$. With $U_\kappa$ the
negative-energy occupied matrix prepared from $H_\kappa(\sigma_0)$, evolve

$$
\dot U_\kappa=-iH_\kappa(\sigma)U_\kappa,
$$

and source the scalar equation with the degeneracy-weighted normal-ordered
sum

$$
\dot\sigma=\pi,
\qquad
\dot\pi=\nabla_r^2\sigma-\lambda(\sigma^2-v^2)\sigma
-g\sum_{\kappa=\pm1}d_\kappa s_{{\rm NO},\kappa}.
$$

## 2. Initial data and controls

Use

$$
\sigma_0(r)=v-Ae^{-(r-r_s)^2/(2w^2)},
\qquad
\pi_0(r)=A\frac{r-r_s}{w^2}e^{-(r-r_s)^2/(2w^2)}.
$$

The candidate covariance is the product of both channel vacuum projectors.
Controls are:

- `static_vacuum`: homogeneous scalar and both channel negative-energy vacua;
- `source_off`: shell and both local channel vacua with scalar source disabled;
- `zero_covariance`: shell with both occupied matrices zero and source disabled.

No post-initial energy source, damping, reset, clamp, trap or parameter change
is allowed.

## 3. Grid and time integration

Use:

| grid | $N$ | $\Delta r$ | listed $\Delta t$ | final time |
|---|---:|---:|---:|---:|
| G0 | 48 | $1/3$ | $0.004$ | $12$ |
| G1 | 72 | $2/9$ | $0.002$ | $12$ |
| G2 | 96 | $1/6$ | $0.001$ | $12$ |

The primary uses fixed-step RK4 with **eight equal substeps** per listed
interval and stores scalar arrays, velocities and both complete occupied
matrices at $t=0,0.1,\ldots,12$. The independent verifier reconstructs the
real first-order system with DOP853 using `rtol=2e-8`, `atol=2e-10` and
`max_step=0.02`.

Direct state reconstruction thresholds are $2\times10^{-5}$ for $\sigma$,
$5\times10^{-5}$ for $\pi$, and $3\times10^{-5}$ for each covariance
projector's maximum absolute entry error. Summary reconstruction uses
$2\times10^{-4}$. Every payload must be finite. These numerical tolerances
are verification thresholds, not physical acceptance thresholds.

## 4. Observables and decision rule

At every stored time diagonalize both instantaneous Hamiltonians. Sum pair
occupation, hole occupation, pair density and bound density with the magnetic
degeneracies. The bound subspace is

$$
\mathcal B_\kappa(t)=\{u_j(t):0<E_{\kappa j}(t)\le1.5\}.
$$

Use $r<4$ for core probabilities and the spherical cell measure for RMS
radii. Zero occupations and empty bound windows use the $10^{-12}$ convention.

A candidate grid must pass formation, persistence, energy, adjacent-grid,
finite-payload, particle–hole, control, state-reconstruction and
summary-reconstruction predicates after channel sums. The scientific verdict
is `CAPTURED—conditional autonomous two-channel spherical formation` when all
candidate and control checks pass. It is `DOES NOT EMERGE—conditional
autonomous two-channel spherical formation` when the numerical contract passes
and a candidate predicate fails. A source, operator, integration,
conservation, finiteness or reconstruction failure returns `INCONCLUSIVE`.

## 5. Interpretation boundary

A positive verdict qualifies the finite-box spherical $\kappa=\pm1$ channel
sum. The calculation does not cover $|\kappa|>1$, non-spherical scalar
perturbations, regulator removal, renormalized quantum backreaction,
whole-bubble preparation, physical normalization, or particle
spin/statistics/charge identification.

## References

- `computations/matter-formation-autonomous-shell-g3-prereg.md`—single-channel G3 action and candidate thresholds.
- `computations/matter-formation-autonomous-shell-g3-stability-prereg.md`—single-channel numerical comparison contract.
- `computations/matter-formation-autonomous-shell-g3-two-channel-prereg.md`—two-channel action and observable definitions.
- `foundations/matter-completion-boundary.md`—physical completion requirements.
