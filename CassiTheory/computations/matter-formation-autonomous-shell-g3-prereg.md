# Autonomous Incoming-Shell Vacuum-to-Bound-State Formation: G3 Finite-Core Continuation

## Status: Hypothesized conditional finite-core autonomous protocol—September 2026

## Abstract

The smooth prescribed-bag arm qualifies localized vacuum occupation while
leaving the scalar background external. This protocol tests a closed radial
Yukawa action with a finite-energy incoming scalar shell and a fermionic
covariance initialized in the negative-energy vacuum of the initial shell
profile. After the initial data are set, the scalar and covariance evolve
without an external source, damping, clamping, trap, reset, or parameter
change. The calculation measures whether the incoming scalar excitation can
produce and retain a localized particle–hole excitation with convergent
regulated observables.

The result is scoped to the dimensionless spherical $\kappa=-1$ channel. It
records the coupled autonomous boundary and does not assign a physical
particle species, supply all angular channels, or establish continuum
renormalization.

## 1. Action and radial channel

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

Only the spherical $\kappa=-1$ radial channel is retained. The scalar
finite-volume equation is

$$
\dot\sigma=\pi,
\qquad
\dot\pi=\nabla_r^2\sigma-\lambda(\sigma^2-v^2)\sigma-gs_{\rm NO}.
$$

The radial Dirac Hamiltonian is the Hermitian centred finite-box operator

$$
H(\sigma)=
\begin{pmatrix}
 g\sigma&-D-c_{a_c}(r)\\
 D-c_{a_c}(r)&-g\sigma
\end{pmatrix},
\qquad
c_{a_c}(r)=\frac{1}{\sqrt{r^2+a_c^2}}.
$$

The finite-core coefficient $a_c=0.5$ is a declared numerical regulator of the
radial channel. It keeps the finite-box operator defined at the inner cell and
does not represent the unsmoothed point-core limit.

The centred endpoint stencil, spherical cell volumes, face areas, and outer
Dirichlet value $\sigma(R)=v$ are fixed by the radial vacuum-bag protocol.

## 2. Autonomous initial data and covariance

At $t=0$ set

$$
\sigma_0(r)=v-A\exp[-(r-r_s)^2/(2w^2)],
$$

and choose the inward-moving shell velocity

$$
\pi_0(r)=A\frac{r-r_s}{w^2}
\exp[-(r-r_s)^2/(2w^2)].
$$

The fermionic covariance is the negative-energy spectral projector of
$H(\sigma_0)$, not the homogeneous-vacuum projector. Let $U_0$ contain its
$N$ normalized negative-energy columns. The normal-ordered source is

$$
 s_{\rm NO}(r_i)=
\frac{\sum_a(|U_{i a}|^2-|U_{N+i,a}|^2)
-\sum_a(|U_{0,i a}|^2-|U_{0,N+i,a}|^2)}{4\pi r_i^2}.
$$

The occupied modes evolve with

$$
\dot U=-iH(\sigma)U,\qquad U(0)=U_0.
$$

The scalar field and covariance are advanced together. No term after the
initial data supplies energy to the system.

## 3. Grids, archives and independent method

Use the fixed schedule

| grid | $N$ | $\Delta r$ | $\Delta t$ | final time |
|---|---:|---:|---:|---:|
| G0 | 48 | $1/3$ | $0.004$ | $12$ |
| G1 | 72 | $2/9$ | $0.002$ | $12$ |
| G2 | 96 | $1/6$ | $0.001$ | $12$ |

The primary uses fixed-step RK4 with four equal substeps per listed output
interval and stores $\sigma$, $\pi$, and the complete complex occupied-mode
matrix at $t=0,0.1,\ldots,12$. The independent verifier assembles the radial
operator and source separately and uses DOP853 with `rtol=2e-8`,
`atol=2e-10`, and `max_step=0.02` at the same archive times.

The primary and verifier use the same declared initial data but separate
implementations of the evolution and observable reconstruction. Time,
scalar, and scalar-velocity arrays are compared directly. The occupied-mode
matrix is archived for provenance; its phase-dependent entries are compared
through the gauge-invariant occupied covariance projector $P=UU^\dagger$.
All arrays must be finite and shape-consistent.

## 4. Controls and observables

Candidate rows are the three grids. The controls are:

- `static_vacuum` on G1: $\sigma=v$, $\pi=0$, and the homogeneous vacuum;
- `source_off` on G1: the incoming shell and its initial local vacuum, with
  the normal-ordered scalar source omitted;
- `zero_covariance` on G1: the incoming shell with $U=0$ and source disabled.

The static control must retain zero pair number and zero scalar motion. The
zero-covariance control must retain zero covariance norm and zero pair number.
The source-off control is diagnostic and is not a candidate formation row.

At each stored time, diagonalize the instantaneous static radial Hamiltonian.
Define $N_{\rm pair}$ by projection onto its positive-energy subspace. Define
the physical bound subspace by

$$
\mathcal B(t)=\{u_j(t):0<E_j(t)\le E_b\},\qquad E_b=1.5.
$$

The bound occupation is the total occupied covariance in $\mathcal B(t)$;
the matched hole subspace consists of the same number of negative-energy modes
nearest zero. If $\mathcal B(t)$ is empty, bound occupation, hole occupation,
core probability and RMS are defined as zero. Pair and bound-mode core
probabilities are measured inside $r<4$. Pair and bound RMS radii, scalar centre
deficit, covariance norm, and normal-ordered total energy are recorded. Pair
localization and pair RMS are defined as zero when the total pair number is
below $10^{-12}$.

## 5. Qualification and scope

A candidate grid passes when

1. $N_{\rm pair}>0.05$, the bound occupation exceeds $0.10$, and the
   particle–hole gap is below $0.05$;
2. pair and bound-subspace core probabilities exceed $0.50$ and their RMS
   radii are below $5$;
3. late-window pair and bound occupations have standard deviation at most
   $0.25$, and late-window RMS standard deviation is at most $0.75$;
4. the normal-ordered relative energy drift is at most $5\times10^{-3}$;
5. adjacent-grid differences of pair number and bound occupation are below
   $0.25$, core probabilities below $0.15$, and RMS radii below $0.50;
6. the covariance norm, particle–hole identity, source-off diagnostics, and
   independent state and summary comparisons pass; and
7. both controls satisfy their declared zero predicates.

The scientific verdict is `CAPTURED—conditional autonomous radial formation`
when every candidate and control check passes. It is
`DOES NOT EMERGE—conditional autonomous radial formation` when the numerical
contract passes and at least one candidate formation predicate fails. Any
provenance, integration, finiteness, conservation, or reconstruction failure
returns `INCONCLUSIVE`.

A positive verdict remains conditional on the regulated radial channel and the
specified initial scalar excitation. The completion boundary retains the
requirements for continuum removal, all angular sectors, renormalized
backreaction, action selection, and physical particle identification.

## References

- `computations/matter-formation-autonomous-shell-prereg.md`—baseline autonomous radial action and controls.
- `computations/matter-formation-smooth-bag-transition-prereg.md`—prescribed smooth background witness.
- `computations/matter-formation-fermion-vacuum-bag-prereg.md`—radial covariance, normal-ordering and energy conventions.
- `foundations/matter-completion-boundary.md`—completion requirements and current scope.
