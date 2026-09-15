# Dynamic Helical Geometry and Vortex-Stretching Depletion

## Status: Pre-registered—September 2026

## Protocol amendment A1—September 2026

This amendment is recorded before the retained 24-run execution. The homochiral mode list uses $(1,1,0)$ as its third wavevector; this is the fixed implementation and replaces the earlier $(1,1,1)$ transcription. The zero-helicity comparison value $P(0)=1/2$ is volume-normalized, while the dynamic verifier uses unnormalized integrals. Two pre-amendment launches were cancelled before receipt generation; their partial states and measurements are excluded from the declared matrix. The receipt binds this amended protocol by SHA-256 and records revision `A1`.

## Abstract

This schedule tests whether coherent helical geometry supplies a dynamically preserved depletion of the Navier–Stokes vortex-stretching term. It evolves the original unforced three-dimensional incompressible equation in a Fourier-Galerkin truncation, with an exact Beltrami heat flow as the preserved-depletion control and non-Beltrami coherent helical fields as stress cases. The stress cases include a shrinking tube radius, a shrinking helical pitch, interacting scales, homochiral mixtures, and opposite-handed structures. The calculation records signed stretching, local alignment, vorticity-direction variation, helicity, and the finite-resolution integrity residuals.

The schedule tests a finite geometric family. Its output is a diagnostic for a proposed sign or depletion mechanism; a conditional direction-coherence estimate and an arbitrary-data regularity theorem require separate analytic bounds.

## 1. Equation and exact budget

Work on the $2\pi$-periodic torus with unnormalized integrals, viscosity $\nu=1/10$, and horizon $T=1/2$:

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad \nabla\cdot u=0,
$$

$$
\omega=\nabla\times u,
\qquad
S=\frac12(\nabla u+\nabla u^{\mathsf T}),
$$

$$
K=\frac12\int|u|^2dx,
\qquad
E=\frac12\int|\omega|^2dx,
\qquad
G=\frac12\int|\nabla\omega|^2dx,
$$

$$
P(t)=\int\omega\cdot S\omega\,dx,
\qquad
E'(t)+2\nu G(t)=P(t).
$$

Every initial field is rescaled after Fourier projection to $K(0)=1$. The Galerkin equation uses the rotational nonlinearity with the Leray projection, an odd product grid $M=6N+1$, and float64 Torch tensors on the installed ROCm device.

The local stretching density has the strain-eigenframe form

$$
\omega\cdot S\omega
=|\omega|^2\sum_{j=1}^3\lambda_j c_j^2,
\qquad
\sum_j\lambda_j=0,
$$

where $c_j$ are the components of the vorticity direction in a strain eigenframe. Direction coherence alone constrains neighboring vorticity directions; it supplies no eigenframe alignment without an additional dynamical estimate for the pressure-generated strain.

## 2. Geometry stressors

A centerline helix

$$
\gamma(\theta)=(a_c\cos\theta,a_c\sin\theta,b\theta)
$$

has tangent curvature and torsion

$$
\kappa=\frac{a_c}{a_c^2+b^2},
\qquad
\tau_g=\frac{b}{a_c^2+b^2}.
$$

For a periodic centerline written as

$$
\gamma_m(z)=(x_c+a_c\cos mz,\ y_c+a_c\sin mz,\ z),
$$

the pitch per turn is $2\pi/|m|$. The tube radius $r$ is the width of the Gaussian vorticity profile around this centerline. A raw tube field is projected to the divergence-free Galerkin subspace before normalization.

For fixed circulation $\Gamma$ and tube length $L$, a core amplitude scales as $|\omega|\sim\Gamma r^{-2}$ and

$$
\|\omega\|_2^2\sim\Gamma^2Lr^{-2}.
$$

The transverse direction gradient and the local strain scale carry inverse powers of $r$, while the centerline direction gradient carries $\kappa$. Consequently, shrinking $r$ or $b$ supplies no geometry-independent coherence constant. The schedule varies these quantities before trajectory execution.

## 3. Initial-data families

The verifier constructs the following eight cases and normalizes each projected field to $K(0)=1$.

1. **Beltrami control.**
   $$
   u_B=(\sin z,\cos z,0),
   \qquad \omega_B=u_B.
   $$
   This is a single curl eigenmode. Its nonlinear term is a pressure gradient, so the trajectory is the exact heat flow and $P(t)=0$ analytically.

2. **Homochiral interacting modes.** Four nonparallel Fourier modes use the positive curl polarization $i k\times h_+(k)=|k|h_+(k)$ at wavevectors $(1,0,0)$, $(0,1,0)$, $(1,1,0)$, and $(2,1,0)$, with fixed unequal amplitudes and phases. Their common curl sign supplies spectral handedness without the single-eigenvalue condition $\omega=\lambda u$.

3. **Opposite-helicity modes.** Equal-energy positive and negative curl modes use wavevectors $(1,0,0)$ and $(0,1,0)$, with two additional fixed modes. The signed helicity is recorded rather than imposed after projection.

4. **Wide helical tube.** A centerline with $a_c=3/4$, $m=1$, and radius $r=1/2$.

5. **Narrow helical tube.** The same centerline with radius $r=1/4$.

6. **Tight-pitch helical tube.** The same centerline radius $a_c=3/4$, tube radius $r=1/4$, and $m=4$, giving pitch $\pi/2$ per turn.

7. **Two-scale interacting tubes.** A wide $a_c=3/4$, $m=1$, $r=1/2$ tube and a separated narrow $a_c=3/8$, $m=4$, $r=1/4$ tube with the same handedness.

8. **Opposite-handed tubes.** Two separated radius-$1/4$ tubes with $a_c=3/4$, $|m|=3$, and centerline windings $m=+3$ and $m=-3$.

The tube vorticity seed is proportional to a Gaussian profile times the centerline tangent. The Leray projection supplies the exact divergence-free initial vorticity in the retained Fourier space. The raw and projected divergence residuals, kinetic normalization, helicity, and Fourier support are retained in the receipt.

## 4. Run matrix

For every case execute a primary run at each $N\in\{16,32\}$:

- product grid $M=6N+1$;
- 1024 equal RK4 steps over $[0,T]$;
- float64 ROCm Torch backend.

For every case at $N=32$, also execute a timestep refinement with 2048 steps at the same grid. The matrix contains 16 primary runs and 8 timestep-refined runs. The exact Beltrami control, all geometry parameters, and all amplitudes are fixed before execution.

The initial state and every RK4 state are evaluated. Checkpoints occur at $t/T\in\{0,1/4,1/2,3/4,1\}$.

## 5. Recorded depletion and geometry observables

At every checkpoint record:

$$
P(t),\quad P_+(t)=\max(P(t),0),\quad E(t),\quad G(t),\quad K(t),
$$

and the positive-stretching integral obtained by composite trapezoidal quadrature on every RK4 step,

$$
I_P(T)=\int_0^T P_+(t)\,dt.
$$

To separate signed spatial cancellation from local alignment, record

$$
A_{\mathrm{abs}}(t)
=\frac{\int|\omega\cdot S\omega|\,dx}
{\int|\omega|\,|S\omega|\,dx},
\qquad
A_{\mathrm{signed}}(t)
=\frac{P(t)}{\int|\omega|\,|S\omega|\,dx},
$$

with a declared zero-denominator marker. Record the vorticity-direction gradient

$$
D_\xi(t)^2
=\frac{\int|\omega|^2|\nabla\xi|^2dx}
{\int|\omega|^2dx},
\qquad
\xi=\frac{\omega}{|\omega|}
$$

on the nonzero-vorticity mask. Record the signed helicity $H=\int u\cdot\omega\,dx$, the absolute curl-weighted energy $C=\sum_{k\ne0}|k||u_k|^2$, and $H/C$ when $C>0$.

## 6. Integrity and decision rules

The finite execution passes its numerical integrity checks only when:

- every recorded scalar is finite;
- projected kinetic normalization error is at most $10^{-10}$;
- Fourier divergence residual is at most $10^{-10}$;
- direct physical-space and spectral stretching agree to relative error at most $10^{-9}$ using denominator $\max(1,\int|\omega\cdot S\omega|dx)$;
- the maximum positive kinetic-energy increment is at most $10^{-9}\max(1,K(0))$;
- the timestep-refined $N=32$ positive-stretching integral changes by at most $10^{-4}$ using denominator $\max(1,|I_P|)$.

The hard sign hypothesis is:

> A coherent helical initial geometry dynamically preserves vortex-stretching depletion, expressed by $P(t)\le0$ throughout the declared smooth finite trajectory.

The Beltrami control receives `PRESERVED` only when its maximum absolute $P$ is at most $10^{-10}$. Any non-Beltrami case with a measured $P(t)>10^{-8}$ receives `CONTRADICTS` for the universal sign hypothesis. If all non-Beltrami cases remain nonpositive, the finite sign test receives `INCONCLUSIVE`; finite nonpositive trajectories do not establish a general inequality.

The alignment ratios and direction-gradient histories are descriptive diagnostics. A monotone or data-controlled depletion estimate requires a separate theorem-level statement and is classified `UNRESOLVED` by this schedule.

## 7. Interpretation boundary

A positive stretching episode in a coherent helical field shows that visual organization and a shared curl sign do not supply a universal sign-definite depletion. A bounded $I_P$ over this matrix supplies a finite observation only. A regularity route requires an initial-data-controlled, cutoff-independent estimate such as

$$
\int_0^T\|\nabla u(t)\|_{L^\infty}\,dt<\infty
$$

or a quantitatively equivalent bound on the direction-coherence coefficient and the nonlocal strain. The Constantin–Fefferman type direction condition is conditional on a spatial coherence modulus; its time integrability and propagation from arbitrary data remain separate proof obligations.

Signed helicity obeys

$$
H'=-2\nu\int\omega\cdot(\nabla\times\omega)\,dx,
$$

and its nonlinear contribution cancels from the helicity budget. The stretching production is cubic in the velocity and has independent triadic signs. Therefore $H=0$ supplies no sign for $P$; the fixed zero-helicity periodic control in `computations/navier-stokes-helical-spread-prereg.md` has volume-normalized $P(0)=1/2$.

The schedule stops after the 24 declared executions. Its output supplies no arbitrary-data continuation theorem, singularity construction, or constitutive identification beyond the original Navier–Stokes equation.

## References

- `turbulence/navier-stokes-stress-geometry.md`—filtered stress geometry, Biot–Savart direction estimate, helical tangent covariance, and local-strain freedom
- `turbulence/navier-stokes-strain-departure.md`—critical spread, Beltrami residual, and cumulative production boundary
- `turbulence/navier-stokes-depletion-dynamics.md`—positive and negative transfer responses and the open cumulative estimate
- `computations/navier-stokes-helical-spread-prereg.md`—exact helical moments, Beltrami control, opposite-helicity mixing, and zero-helicity stretching control
- `computations/verify_navier_stokes_galerkin_long_trajectory.py`—Fourier-Galerkin rotational integrator and ROCm implementation
- P. Constantin and C. Fefferman, “Direction of vorticity and the problem of global regularity for the Navier–Stokes equations,” *Indiana University Mathematics Journal* **42** (1993), 775–789—conditional direction-coherence continuation criterion
- Biferale and Titi, “On the global regularity of a helical-decimated version of the 3D Navier–Stokes equations,” arXiv:1303.1215—one-handed projected model and its distinction from full Navier–Stokes
- D. Buaria, A. Pumir, and E. Bodenschatz, “Self-attenuation of extreme events in Navier–Stokes turbulence,” *Nature Communications* **11** (2020), 5852—measured local strain self-attenuation in a specified turbulent regime
