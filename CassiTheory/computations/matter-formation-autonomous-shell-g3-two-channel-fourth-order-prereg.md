# Autonomous Incoming-Shell Formation: G3 Two-Channel Fourth-Order Spatial Continuation

## Status: Hypothesized conditional two-channel protocol—September 2026

## Abstract

This calculation tests the leading two spherical Dirac sectors with an
energy-preserving fourth-order spatial derivative. The finite-core action,
scalar shell, degeneracy-weighted normal-ordered source, vacuum covariance,
controls, G3 grid schedule, observables and decision rule are fixed. Only the
spatial Dirac derivative representation changes: its skew-symmetric stencil
retains the Hermitian Hamiltonian and removes the nearest-neighbour spatial
operator as the limiting explanation for angular-sector disagreement.

The two sectors are $\kappa=-1,+1$, each with magnetic degeneracy two. A
positive result qualifies the declared finite-box fourth-order discretization;
it does not establish all-$\kappa$ stability, regulator removal or a physical
particle theory.

## 1. Action and operator

Use

$$
\mathcal L=\frac12\partial_\mu\sigma\partial^\mu\sigma
-\frac{\lambda}{4}(\sigma^2-v^2)^2
+\bar\psi(i\gamma^\mu\partial_\mu-g\sigma)\psi
$$

with

$$
(v,\lambda,g,R,A,r_s,w,a_c,T)=(1,\tfrac14,3,16,0.75,4,2,0.5,12).
$$

For $\kappa\in\{-1,+1\}$,

$$
H_\kappa(\sigma)=
\begin{pmatrix}
 g\sigma&-D_4+\kappa c_{a_c}(r)\\
 D_4+\kappa c_{a_c}(r)&-g\sigma
\end{pmatrix},
\qquad
c_{a_c}(r)=\frac1{\sqrt{r^2+a_c^2}}.
$$

The derivative $D_4$ is the real skew-symmetric finite matrix with

$$
(D_4)_{i,i+1}=\frac{2}{3\Delta r},
\qquad
(D_4)_{i,i+2}=-\frac{1}{12\Delta r},
\qquad
(D_4)_{j,i}=-(D_4)_{i,j},
$$

when the indices lie in the grid; entries outside the finite interval are
zero. This is the fourth-order centred derivative in the interior with a
skew-symmetric truncation at the boundaries. The scalar Laplacian remains the
finite-volume face-flux operator used by the G3 protocol.

Each channel has $d_\kappa=2$. Evolve the occupied matrices by

$$
\dot U_\kappa=-iH_\kappa(\sigma)U_\kappa
$$

and use the degeneracy-weighted normal-ordered density sum in the scalar
acceleration. No damping, reset, clamp, trap or external source is allowed.

## 2. Initial data and controls

Use

$$
\sigma_0(r)=v-Ae^{-(r-r_s)^2/(2w^2)},
\qquad
\pi_0(r)=A\frac{r-r_s}{w^2}e^{-(r-r_s)^2/(2w^2)}.
$$

Prepare the product of both channel negative-energy vacuum projectors. Use
`static_vacuum`, `source_off` and `zero_covariance` controls exactly as in
`computations/matter-formation-autonomous-shell-g3-two-channel-v2-prereg.md`.

## 3. Grid, time and verification

Use G0 $(N,\Delta t)=(48,0.004)$, G1 $(72,0.002)$ and G2
$(96,0.001)$ with $\Delta r=16/N$, final time $12$ and stored samples every
$0.1$. The primary uses RK4 with eight equal substeps per listed interval.
The independent verifier uses DOP853 with `rtol=2e-8`, `atol=2e-10` and
`max_step=0.02`, reconstructing the real first-order system without importing
the primary.

Direct state thresholds are $2\times10^{-5}$ for $\sigma$, $5\times10^{-5}$
for $\pi$, $3\times10^{-5}$ for each covariance projector entry and
$2\times10^{-4}$ for summary values. All payloads must be finite. The bound
window is $0<E\le1.5$, core radius is $r<4$, and zero quantities use the
$10^{-12}$ convention.

## 4. Decision rule and scope

Candidate formation, persistence, pair–hole, bound-subspace, energy, control,
state, summary and adjacent-grid predicates are applied after summing both
channels with degeneracy two. A fully qualified positive result is
`CAPTURED—conditional autonomous two-channel fourth-order spherical formation`.
A numerically qualified candidate failure is
`DOES NOT EMERGE—conditional autonomous two-channel fourth-order spherical
formation`. Any source, operator, integration, conservation, finiteness or
reconstruction failure is `INCONCLUSIVE`.

This calculation does not establish $|\kappa|>1$ stability, nonspherical scalar
coupling, regulator-independent renormalized backreaction, physical units,
particle identity, spin, statistics or charge.

## References

- `computations/matter-formation-autonomous-shell-g3-two-channel-v2-prereg.md`—finite-core two-channel action, controls and observables.
- `computations/matter-formation-autonomous-shell-g3-prereg.md`—single-channel G3 candidate thresholds.
- `foundations/matter-completion-boundary.md`—physical completion requirements.
