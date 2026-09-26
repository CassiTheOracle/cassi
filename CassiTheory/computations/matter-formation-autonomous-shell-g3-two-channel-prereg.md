# Autonomous Incoming-Shell Formation: G3 Two-Channel Angular Continuation

## Status: Hypothesized conditional two-channel protocol—September 2026

## Abstract

The finite-core G3 trajectory qualifies one spherical $\kappa=-1$ radial
channel. This protocol adds the degenerate $\kappa=+1$ channel and evolves the
lowest two spherical Dirac sectors with their full normal-ordered backreaction.
The scalar shell, action coefficients, finite core, covariance preparation,
energy ledger, controls, output schedule and candidate predicates stay fixed.

The calculation measures whether the radial capture survives the leading
opposite-parity channel when both $j=1/2$ sectors contribute to the scalar
source. The background remains spherically symmetric, so the two channels
are dynamically decoupled and their covariances provide a controlled angular
sector extension. A positive result qualifies this two-channel finite-core
model; it does not establish all-$\kappa$ stability or a continuum particle
theory.

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

For $\kappa\in\{-1,+1\}$ use the centred Hermitian radial operator

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

Each channel has magnetic degeneracy $d_\kappa=2$. The scalar equation uses
the sum of normal-ordered channel densities:

$$
\dot\sigma=\pi,
\qquad
\dot\pi=\nabla_r^2\sigma-\lambda(\sigma^2-v^2)\sigma
-g\sum_{\kappa=\pm1}d_\kappa s_{{\rm NO},\kappa}.
$$

The occupied matrix $U_\kappa$ contains the negative-energy eigenvectors of
$H_\kappa(\sigma_0)$ and evolves by $\dot U_\kappa=-iH_\kappa(\sigma)U_\kappa$.
The normal-ordered density subtracts the corresponding initial projector in
each channel before applying its degeneracy.

## 2. Initial data and controls

Use the inward scalar shell

$$
\sigma_0(r)=v-Ae^{-(r-r_s)^2/(2w^2)},
\qquad
\pi_0(r)=A\frac{r-r_s}{w^2}e^{-(r-r_s)^2/(2w^2)}.
$$

The candidate covariance is the product of the two channel vacuum
projectors. The controls are:

- `static_vacuum`: homogeneous scalar and both channel negative-energy vacua;
- `source_off`: the shell and both local channel vacua, with the scalar
  normal-ordered source disabled;
- `zero_covariance`: the shell with both occupied matrices zero and source
  disabled.

No post-initial energy source, damping, reset, clamp, trap or parameter
change is permitted.

## 3. Numerical schedule and independent method

Use the G3 schedule:

| grid | $N$ | $\Delta r$ | listed $\Delta t$ | final time |
|---|---:|---:|---:|---:|
| G0 | 48 | $1/3$ | $0.004$ | $12$ |
| G1 | 72 | $2/9$ | $0.002$ | $12$ |
| G2 | 96 | $1/6$ | $0.001$ | $12$ |

The primary uses fixed-step RK4 with four equal substeps per listed output
interval and stores the scalar arrays, velocities and both complete occupied
matrices at $t=0,0.1,\ldots,12$. The independent verifier reconstructs the
real first-order system with DOP853 using `rtol=2e-8`, `atol=2e-10` and
`max_step=0.02`. Scalar and velocity arrays are compared directly. Each
channel's occupied covariance projector $P_\kappa=U_\kappa U_\kappa^\dagger$
is compared independently. All arrays and summary values must be finite.

## 4. Observables and decision rule

At each stored time diagonalize both instantaneous channel Hamiltonians. Sum
pair occupation, hole occupation, pair density, and bound density with the
magnetic degeneracies. The bound subspace in each channel is

$$
\mathcal B_\kappa(t)=\{u_j(t):0<E_{\kappa j}(t)\le1.5\}.
$$

The matched negative-energy hole subspace has the same dimension in each
channel. Pair and bound core probabilities use $r<4$ and their RMS radii use
the spherical cell measure. Zero occupations and empty bound windows use the
same $10^{-12}$ conventions as the G3 action protocol.

A candidate grid passes the G3 formation, persistence, energy, adjacent-grid,
finite-payload, particle–hole, control, state-reconstruction and
summary-reconstruction predicates after the channel sums are applied. The
scientific verdict is `CAPTURED—conditional autonomous two-channel spherical
formation` when every candidate and control check passes. It is
`DOES NOT EMERGE—conditional autonomous two-channel spherical formation` when
the numerical contract passes and a candidate predicate fails. Any source,
operator, integration, conservation, finiteness or reconstruction failure
returns `INCONCLUSIVE`.

## 5. Interpretation boundary

A positive verdict qualifies the finite-core $\kappa=\pm1$ channel sum at the
frozen finite-box schedule. The calculation does not cover $|\kappa|>1$,
non-spherical scalar perturbations, regulator removal, renormalized quantum
backreaction, whole-bubble preparation, physical normalization, or particle
spin/statistics/charge identification. Those requirements remain part of the
matter-completion boundary.

## References

- `computations/matter-formation-autonomous-shell-g3-prereg.md`—single-channel G3 action and candidate thresholds.
- `computations/matter-formation-autonomous-shell-g3-stability-prereg.md`—single-channel numerical comparison contract.
- `foundations/matter-completion-boundary.md`—physical completion requirements.
