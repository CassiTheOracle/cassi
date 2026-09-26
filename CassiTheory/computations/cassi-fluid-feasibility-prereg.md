# Cassi Fluid Feasibility: Fixed Mechanical and Solver Controls

## Status: Preregistered—September 2026

## Abstract

This schedule assesses whether the supplied Cassi sectors support a closed material-fluid interpretation. It separates the canonical real-density conversion, an ungauged matter reduction of the conservative complex-field action, the source-free second-order charged action, and the implemented projected-velocity solver. Fixed analytical controls and actual solver evolutions test conservation, conversion, and the inherited Navier–Stokes sector. No new mechanical term is inserted and no concentration-arrest experiment is authorized by this schedule.

## 1. Sources and conventions

The source authorities are `foundations/interscale-current-soliton.md` §§1–3, `foundations/particle-stationary-action-closure.md` §§2–3, `foundations/interscale-stress-attenuation-boundary.md` §§1–2 and 5, `foundations/cassi-theory-reference.md` §§2.2–2.4, and `two-fluid/cassi_two_fluid_3d_gpu.py`. The executable is `computations/verify_cassi_fluid_feasibility.py`. All are captured as raw bytes before execution and checked again before the receipt is accepted.

Physical mass density is denoted by $\rho_m$. The real-density solver uses reference-normalized $Y=E_Y$, $I=E_I$, $\rho=Y+I$, $\pi=Y-I$, and $\varepsilon=Y-\varphi I$. The complex action uses number density per dimensionless scale coordinate. Its mathematical three-dimensional matter reduction sets scale derivatives and the gauge coupling to zero; it supplies no claim about solving the coupled gauge equations at nonzero coupling. The carrier-mass assignment $K_x=\hbar^2/m_c$ is conditional and externally normalized. $T_{ij}$ is momentum flux; $\sigma_{ij}$ is total Cauchy stress.

The actual solver controls use the periodic cube $[0,2\pi)^3$, normalized spatial means, CPU float64/complex128 and one Torch computational thread. Coordinate arrays follow the solver's Fourier multipliers, with $x$ along the last array axis. No random data, external dataset, grid search or parameter fit is used.

## 2. Fixed analytical controls

### 2.1 Conservative action reduction

Use

$$
V(Y,I)=\frac{\lambda_\rho}{4}(Y+I-\rho_0)^2
+\frac{\lambda_\varphi}{2}(Y-\varphi I)^2,
\qquad \mu_a=\partial_{n_a}V.
$$

Check symbolically:

1. $P=Y\mu_Y+I\mu_I-V=\lambda_\rho(\rho^2-\rho_0^2)/4+\lambda_\varphi\varepsilon^2/2$.
2. $\nabla P=Y\nabla\mu_Y+I\nabla\mu_I$ and positivity of the potential Hessian for positive coefficients.
3. For an arbitrary smooth positive scalar density $n$, the quantum momentum flux
   $T^Q_{ij}=K_x[(\partial_i n)(\partial_j n)/n-\partial_i\partial_jn]/4$
   obeys $\partial_jT^Q_{ij}=n\partial_i Q$, with
   $Q=-K_x\Delta\sqrt n/(2\sqrt n)$.
4. The two-species kinetic momentum flux and energy split into barycentric and counterflow terms with coefficient $m_cYI/\rho$.
5. On the positive, common-phase, golden-composition branch, the relative chemical potential vanishes, the pressure reduces to the density term and the longitudinal dispersion is
   $\omega^2=\rho_0\lambda_\rho k^2/(2m_c)+\hbar^2k^4/(4m_c^2)$.
   There is no positive viscosity parameter in this reduction. A smooth common phase gives zero local vorticity. These statements establish a conditional dispersive matter reduction only.
6. For a general complex doublet, the Pauli identity $(\Psi^\dagger\sigma^a\Psi)^2=(\Psi^\dagger\Psi)^2$ checks the nonzero homogeneous Gauss source in the separately gauged first-order completion.

No claim of a physical entropy law, material equation of state, emergent viscosity, general three-dimensional rotational representation, or continuum regularity follows from these algebraic checks.
All symbolic checks retain their positive-density and coefficient assumptions. The numerical runtime explicitly sets Torch's default floating dtype to float64 before constructing Fourier grids, so wave numbers and fields use the same precision.

### 2.2 Canonical conversion and scalar dissipation

For common incompressible advection, equal $D\geq0$, no chemotactic drift, and $\kappa=\lambda(1-q)\geq0$, verify the density-sum cancellation, the two inward reaction directions at $Y=0$ and $I=0$, and

$$
\frac{d}{dt}\frac12\int\varepsilon^2
=-D\int|\nabla\varepsilon|^2
-(1+\varphi)\int\kappa\varepsilon^2.
$$

For fixed positive references with $Y_*/I_*=\varphi$, check the reaction contribution to

$$
\mathcal H=\int\left[Y\log(Y/Y_*)-Y+Y_*+I\log(I/I_*)-I+I_*\right]
$$

as $-\int\kappa(Y-\varphi I)\log[Y/(\varphi I)]\leq0$. Diffusion contributes $-D\int(|\nabla Y|^2/Y+|\nabla I|^2/I)$. The integral and positivity arguments are analytical continuum statements, distinct from a discretization guarantee and from a physically calibrated entropy.

Homogeneous reaction states are $(Y_0,I_0)=(2,1),(1,2)$ with $\lambda=0.3$, $D=\chi=0$, $\nu=0.2$, $T=0.2$, $N=8$, and $\Delta t=0.004,0.002$. The base solver is compared against its exact ungated exponential. The expanding class uses a static box, `hubble_mode='friedmann'`, `H0=0`, `a0=1`, `hyper_nu=0`, `cs2=0`, `qi_memory=False`, `wu_xing=False`, `gate_model='single'`, `phi_inv2=PHI**(-2)`, and `qi_gate=True`; its reference is the implicit exact relation

$$
\lambda(1+\varphi)t=\log\frac{|\varepsilon_0|}{|\varepsilon|}
+\frac{\rho^2}{c}\log\frac{|\varepsilon_0|/\sqrt{c+\varepsilon_0^2}}
{|\varepsilon|/\sqrt{c+\varepsilon^2}},\qquad c=\varphi^{-2}.
$$

The same two states and the boundary states $(0,1),(1,0)$ are checked at the instantaneous RHS in the base and static expanding classes, with expanding gating both off and on. A homogeneous $(10^{-4},1)$ state at $\lambda=D=0$, $u=0$ is advanced once with $\Delta t=0.01$ in both classes. Its exact continuum derivative is zero; the expanding floor-and-renormalization operation is recorded separately, with its analytically computed change of composition and conservation of the density sum.

### 2.3 Internal-force and energy obstruction

Take the strictly positive fields

$$
\rho=4+\cos x,\qquad \pi=b\sin x,\qquad
Y=(\rho+\pi)/2,\quad I=(\rho-\pi)/2,\qquad b\in\{-1,1\}.
$$

Set $\lambda=D=\chi=0$, `rho_ext=None`, `alpha_disp=None`, and use grids $N=16,24$. The base solver has $\Delta\Phi=\rho-\langle\rho\rangle$, $\Phi=-\cos x$, and $\langle\pi\nabla\Phi\rangle=(b/2,0,0)$. Test the full native RHS including its zero Fourier mode at $u=0$ and $u=(1,0,0)$. At the boosted state, the scalars initially undergo a rigid translation while kinetic work is $b/2$. Every translation-invariant scalar-only energy functional has zero instantaneous change under that translation. This excludes an additive closed energy $K+\mathcal U[Y,I]$ for this native coupling under constant inertia, and excludes a periodic internal-stress divergence representation with no additional momentum carrier.

For the static expanding class with all optional terms off except its native force attenuation, use the same fields at $u=0$ and compare its mean force against independent one-dimensional quadrature of

$$
\frac{b\sin^6x}{\sin^4x+0.2^2+10^{-10}}.
$$

The attenuation is positive and tends to one at large force; it does not impose a force-magnitude bound. Native quadrature agreement is measured at the stated grids and is distinct from exact finite-mode algebra because this rational multiplier creates higher harmonics.

One base-solver time evolution for $b=1$, $u_0=0$, $N=16,24$, $T=0.2$, $\Delta t=0.004,0.002$ is compared against the exact native continuum solution

$$
u_x(t)=t/2,\quad u_y=u_z=0,\qquad
\rho=4+\cos(x-t^2/4),\quad\pi=\sin(x-t^2/4).
$$

Here the displayed $u_x$ is velocity; the viscosity remains $\nu=0.2$ and has no effect on spatially uniform velocity. This control diagnoses self-acceleration in the supplied model. It is not a physical-fluid prediction or a singularity example.

## 3. Inherited Navier–Stokes flow controls

Use the base solver with $Y=\varphi$, $I=1$, $D=\lambda=\chi=0$, `rho_ext=None`, `alpha_disp=None`, and $\nu=0.2$. Uniform scalars keep the native information force exactly zero. These controls qualify only the implemented NS sector. They do not require or establish a Cassi material closure.

The three analytical controls use $N=16,24$, $T=0.2$, and $\Delta t=0.004,0.002$:

- Shear: $u=(e^{-\nu t}\sin y,0,0)$.
- Embedded two-dimensional Taylor–Green vortex: $u=e^{-2\nu t}(\sin x\cos y,-\cos x\sin y,0)$.
- Prescribed smooth forcing $f=(0.1\sin y,0,0)$ from rest: $u_x=[0.1(1-e^{-\nu t})/\nu]\sin y$. A named benchmark subclass adds this prescribed external force to the actual native RHS at both stages of the native RK2 integrator. This wrapper is distinct from the native self-sourced force.

For genuine three-dimensional nonlinear transfer, evolve $u_0=(\sin x\cos y\cos z,-\cos x\sin y\cos z,0)$ at $N=16,24$, $T=0.05$, and $\Delta t=0.002,0.001$. Compare with independently implemented NumPy projected, two-thirds-dealiased RK4 at $\Delta t=0.00025$ on each same grid. Compare the two native fine-step grids at their shared grid-independent velocity, energy and enstrophy observables through the independent reference; no long-time turbulence or mesh-convergence theorem is claimed. Record actual velocity change, vertical velocity, divergence and energy budget. The initial vortex-stretching density is nonzero even where its spatial integral cancels.

## 4. Decisions, tolerances and stopping rule

- Exact SymPy identities must reduce to zero; algebraic inequalities retain their stated hypotheses.
- Finite-mode/RHS residuals use maximum error divided by $\max(1,\max|\mathrm{reference}|)$, tolerance $10^{-10}$.
- The rational attenuated-force mean uses relative/absolute tolerance $10^{-2}$ at the two prescribed grids; high-resolution independent quadrature uses 16,384 equispaced points. This looser tolerance is restricted to that rational spatial integration.
- Analytical flow endpoints and homogeneous reaction endpoints use $2\times10^{-6}$. Density-sum and solenoidal residuals use $10^{-10}$.
- Three-dimensional same-grid NumPy-reference endpoint error uses $2\times10^{-5}$. The native temporal refinement must reduce error when the coarse error exceeds $10^{-10}$. Analytical decay/refinement controls must reduce error by at least a factor of three when the coarse error exceeds $10^{-10}$.
- No runtime floor is permitted to be hidden in the continuum positivity claim. The single floor-control row is classified as a discrete intervention.
- Verification status `PASS` means the frozen identities, native comparisons and stated error checks succeed. It can coexist with `REJECT` for physical-model promotion.
- The closed native internal-force claim is `CONTRADICTS` if the nonzero mean agrees with the analytic witness; otherwise the comparison is `INCONCLUSIVE` and any numerical mismatch makes verification fail.
- Physical-model promotion is `ADOPT` only with a derived current-to-mass-momentum map, closed mechanical and thermodynamic budgets, a justified positive-viscosity NS limit, and qualified benchmarks. Missing source mechanisms or the fixed native momentum/energy obstruction require `REJECT` for promotion of the supplied sectors as a closed ordinary-fluid alternative. This verdict does not exclude future Cassi completions.
- Concentration-arrest studies are not run under this schedule, regardless of baseline performance. New fixtures, time profiles, grids, constitutive terms or tolerance changes require a separate preregistration; no tuning through a failed result.

The script writes a fresh `runs/cassi_fluid_feasibility/verification.json`, adjacent `verification.inputs.json` and `verification.sources/`, and a separate raw trajectory archive. Existing paths are refused. Input bytes are frozen before the first calculation. Results, failures, exact settings, code/library versions and analytical limitations are retained. Generated paths are indexed in `BROKEN_REFS.md` during integration.

## References

- `foundations/interscale-current-soliton.md`—conditional conservative complex-field action and number currents.
- `foundations/particle-stationary-action-closure.md`—distinct temporal completion and Gauss constraint.
- `foundations/interscale-stress-attenuation-boundary.md`—momentum-window conservation and open material identification.
- `foundations/cassi-theory-reference.md`—canonical real-density law and solver correspondence.
- `two-fluid/cassi_two_fluid_3d_gpu.py`—actual projected-velocity and density implementation.
