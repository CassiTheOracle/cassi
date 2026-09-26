# Autonomous Incoming-Shell Formation: G3 Point-Core Continuation

## Status: Hypothesized conditional point-core protocol—September 2026

## Abstract

The finite-core G3 calculation qualifies a self-consistent spherical formation
trajectory at $a_c=0.5$. This protocol removes that smoothing from the same
finite-volume radial operator and repeats the complete autonomous calculation
with $c_0(r)=1/r$ evaluated at the cell centres. The scalar shell, Yukawa
coupling, covariance preparation, normal ordering, energy ledger, controls,
output schedule and candidate predicates remain fixed.

The calculation tests whether the captured radial observables persist in the
point-core continuation as the three spatial grids approach the continuum.
It remains a spherical $\\kappa=-1$ calculation with a finite box and a
supplied scalar shell. A positive result qualifies a point-core radial
continuation at the tested resolution; it does not select the microscopic
Cassi action or supply angular, renormalization, normalization, or particle
identity closure.

## 1. Fixed action and point-core operator

Use the G3 dimensionless action

$$
\mathcal L=\frac12\partial_\mu\sigma\partial^\mu\sigma
-\frac{\lambda}{4}(\sigma^2-v^2)^2
+\bar\psi(i\gamma^\mu\partial_\mu-g\sigma)\psi,
$$

with

$$
(v,\lambda,g,R,A,r_s,w,T)=(1,\tfrac14,3,16,0.75,4,2,12).
$$

Only the spherical $\kappa=-1$ radial channel is retained. The scalar
finite-volume equation is

$$
\dot\sigma=\pi,
\qquad
\dot\pi=\nabla_r^2\sigma-\lambda(\sigma^2-v^2)\sigma-gs_{\rm NO}.
$$

The radial Hamiltonian is the Hermitian centred finite-box operator

$$
H_0(\sigma)=
\begin{pmatrix}
 g\sigma&-D-1/r\\
 D-1/r&-g\sigma
\end{pmatrix}.
$$

The value $1/r$ is evaluated at each positive cell-centre radius
$r_i=(i+1/2)\Delta r$. The outer scalar value is $\sigma(R)=v$ and the
cell volumes, face areas, endpoint derivative and centred operator are those
of the G3 protocol.

## 2. Autonomous initial data and covariance

At $t=0$ use

$$
\sigma_0(r)=v-A\exp[-(r-r_s)^2/(2w^2)],
$$

and the inward shell velocity

$$
\pi_0(r)=A\frac{r-r_s}{w^2}\exp[-(r-r_s)^2/(2w^2)].
$$

The occupied covariance is the negative-energy spectral projector of
$H_0(\sigma_0)$. Its normal-ordered source is the instantaneous occupied
scalar density minus the initial occupied scalar density, divided by the
spherical cell volume. The occupied modes and scalar field evolve together
from these data under the autonomous equations. No post-initial source,
damping, reset, clamp, trap, or parameter change is permitted.

## 3. Resolution and independent reconstruction

Use the G3 schedule:

| grid | $N$ | $\Delta r$ | listed $\Delta t$ | final time |
|---|---:|---:|---:|---:|
| G0 | 48 | $1/3$ | $0.004$ | $12$ |
| G1 | 72 | $2/9$ | $0.002$ | $12$ |
| G2 | 96 | $1/6$ | $0.001$ | $12$ |

The primary advances each output interval with four equal RK4 substeps and
stores the scalar fields, velocities and complete occupied-mode matrix at
$t=0,0.1,\ldots,12$. The independent verifier reconstructs the same real
first-order system with DOP853 using `rtol=2e-8`, `atol=2e-10` and
`max_step=0.02` at the same archive times. It compares scalar and velocity
arrays directly and compares occupied covariances through the gauge-invariant
projector $P=UU^\dagger$. Every source, archive, summary and diagnostic must
be finite.

## 4. Controls, observables and candidate predicate

The controls are `static_vacuum`, `source_off` and `zero_covariance`, all on
G1, with the same definitions as the G3 finite-core protocol. At each stored
time diagonalize the instantaneous $H_0(\sigma)$. The pair occupation is the
occupied covariance in the positive-energy subspace. The bound subspace is

$$
\mathcal B(t)=\{u_j(t):0<E_j(t)\le1.5\}.
$$

Pair and bound core probabilities use $r<4$; pair and bound RMS radii use the
same cell measure. Values are zero when their corresponding occupation or
bound norm is below $10^{-12}$. The candidate predicate requires the seven
G3 conditions: positive pair and bound occupation, particle–hole agreement,
core localization and RMS bounds, late-window persistence, relative-energy
drift at most $5\times10^{-3}$, centre deficit, adjacent-grid observable
agreement, finite covariance and source diagnostics, independent state and
summary reconstruction, and passing controls.

The scientific verdict is `CAPTURED—conditional autonomous point-core radial
formation` when every candidate and control check passes. It is
`DOES NOT EMERGE—conditional autonomous point-core radial formation` when the
numerical contract passes and a candidate predicate fails. Any provenance,
operator, integration, finiteness, conservation, or reconstruction failure
returns `INCONCLUSIVE`.

## 5. Interpretation boundary

A positive verdict qualifies the point-core radial continuation at the frozen
finite-box schedule. It supplies a regulator-removal data point for the
spherical channel. It does not establish an ultraviolet-renormalized quantum
field theory, a regulator-independent backreaction, all angular channels,
whole-bubble preparation, physical normalization, or particle
spin/statistics/charges and identity. Those conditions remain explicit
requirements of the matter-completion boundary.

## References

- `computations/matter-formation-autonomous-shell-g3-prereg.md`—finite-core G3 action and conditional radial decision rule.
- `computations/matter-formation-autonomous-shell-g3-stability-prereg.md`—G3 numerical comparison schedule and thresholds.
- `foundations/matter-completion-boundary.md`—physical completion requirements.
