# Cassi Fluid Thermodynamics: Fixed Capillary and Thermal Controls

## Status: Preregistered—September 2026

## Abstract

This schedule tests a selected incompressible, constant-total-density reacting capillary fluid. The composition energy is the fixed-density restriction of the ungauged first-order matter action. Independent rotational velocity, thermal entropy, viscosity and conductivity are constitutive assumptions. The model conserves total energy and produces entropy under smooth periodic evolution if its mechanical, reaction and heat terms satisfy the identities below. The native Poisson-density solver and its qualified evidence remain separate. No physical calibration, microscopic viscosity derivation, variable-density completion or concentration-arrest experiment is included.

## 1. Fixed equations and assumptions

Use $c=Y/\rho_{\rm ref}$, $I=\rho_{\rm ref}(1-c)$, $c_*=\varphi/(1+\varphi)$, $\delta=c-c_*$, constant inertia $\rho_m$, $0<c<1$ and $T>0$. The canonical gate uses reference-normalized populations:

$$
\varepsilon=\rho_{\rm ref}(1+\varphi)\delta,\quad
q=\frac{\rho_{\rm ref}^2}{\rho_{\rm ref}^2+\varphi^{-2}+\varepsilon^2},\quad
\kappa=\lambda(1-q).
$$

The selected internal composition energy, variational chemical potential and capillary tensor are

$$
e_c=\frac a2\delta^2+\frac{g(c)}2|\nabla c|^2,\qquad
g(c)=\frac{\gamma}{c(1-c)},\qquad
\mu=a\delta+\frac{g'}2|\nabla c|^2-\nabla\cdot(g\nabla c),\qquad
A_{ij}=g\partial_i c\partial_j c.
$$

With physical number density $n_0$, the restricted action supplies $a=\lambda_\varphi n_0^2(1+\varphi)^2$ and $\gamma=\hbar^2n_0/(4m)$. The number-density normalization, reference-density map and shared rotational velocity are supplied. The numerical coefficients below are dimensionless benchmark choices.

Take thermal energy $CT$ and entropy $s=C\log(T/T_*)-b h(c)$, where

$$
h(c)=c\log(c/c_*)+(1-c)\log[(1-c)/(1-c_*)],\quad
h'=\log\frac{c(1-c_*)}{c_*(1-c)},\quad
r(c)=\frac{h'}{c-c_*},\quad r(c_*)=\frac1{c_*(1-c_*)}.
$$

The affinity, positive mobility and reaction are

$$
\mathcal A=\mu+bTh',\qquad
M=\frac{(1+\varphi)\kappa}{a+bTr(c)},\qquad R=-M\mathcal A.
$$

The equations are

$$
\nabla\cdot u=0,\qquad
\rho_m D_tu=-\nabla p+\nabla\cdot(2\eta S)-\nabla\cdot A,
$$
$$
D_tc=R,\qquad
CD_tT=k_T\Delta T+2\eta S:S-\mu R.
$$

Here $a,C,b,\rho_m,\rho_{\rm ref}>0$ and $\gamma,\eta,k_T,\lambda\geq0$. At homogeneous composition, $R=-(1+\varphi)\kappa\delta$ exactly. Spatial composition gradients change that reaction through the full affinity. Canonical scalar diffusion is set to zero. This constitutes a selected nonisothermal Navier–Stokes/Allen–Cahn-type closure.

## 2. Analytical controls

The analytical statements concern smooth periodic fields and are distinct from their finite-grid checks.

1. Recover the exact Fisher gradient coefficient from the two amplitude-gradient terms and derive $\mu$ by variation.
2. Establish $\mu\nabla c=\nabla e_c-\nabla\cdot A$ and local total-energy flux including $g\nabla c\,R$. For a nonzero commutator witness, use $\chi=2\sqrt\gamma\arcsin\sqrt c$, so $A=\nabla\chi\otimes\nabla\chi$. With $u=\sin y\,e_x$ and $\chi=\chi_0+\alpha\cos x+\beta\cos(x+y)$ in $0<\chi<\pi\sqrt\gamma$, require the exact normalized mean $\langle A:S\rangle=\alpha\beta/4$. The perpendicular profile $c=c(z)$ gives zero and is not a nonzero witness.
3. Establish conservation of spatial momentum and $\int(\rho_m|u|^2/2+e_c+CT)$.
4. Establish the entropy equation
   $$
   \partial_ts+\nabla\cdot\left(su-\frac{k_T\nabla T}{T}\right)
   =\frac{2\eta S:S+M\mathcal A^2}{T}+\frac{k_T|\nabla T|^2}{T^2}\geq0.
   $$
5. Prove the homogeneous canonical reduction, continuous positive mobility at $c_*$, and invariant composition interval $[\min(c_{\min,0},c_*),\max(c_{\max,0},c_*)]$ while the solution and positive temperature stay smooth. Qualify temperature positivity through its reaction-heating equation. No global smoothness theorem is inferred.
6. Use a positive-temperature pointwise composition minimum $c=0.7$, $\nabla c=0$, $\Delta c=10$, $T=1$ with the default coefficients to compare entropy production from the full-affinity reaction against the local canonical reaction. This is a local jet realizable in smooth positive fields, not a complete PDE trajectory.
7. At homogeneous off-equilibrium composition and at shear, deleting reaction or viscous heating must leave the corresponding nonzero total-energy loss. These are deliberately altered controls, separate from the implemented equations.

## 3. Fixed numerical method and coefficients

The executable model is `computations/cassi_fluid_thermodynamics.py`; the verifier is `computations/verify_cassi_fluid_thermodynamics.py`. Use CPU float64/complex128 on the $2\pi$ periodic cube, odd grids $N=9,15,21$, Fourier collocation and classical RK4. Odd grids avoid Nyquist derivative ambiguity. Velocity convection is the equal-weight advective/conservative skew form. Capillary force is a tensor divergence; its zero mode is retained by the Leray projection. Scalar convection is $u\cdot\nabla$. No floor, renormalization, mean-force subtraction or post-step smoothing is permitted.

Default benchmark values are $\rho_m=\rho_{\rm ref}=a=1$, $\gamma=0.02$, $C=2$, $b=0.2$, $\eta=0.03$, $k_T=0.02$, $\lambda=0.4$. The entropy reference temperature is one. These are numerical constitutive inputs without empirical fitting or a change to the 47-parameter inventory.

### 3.1 Exact temporal controls

Use $N=9,15$, $\Delta t=0.004,0.002$ and final time $0.2$ for each of four controls:

- Homogeneous conversion, $u=0,c_0=0.8,T_0=1$. Compare $c(t)$ with an independent scalar adaptive ODE and $T(t)=1+a[(c_0-c_*)^2-(c(t)-c_*)^2]/(2C)$. Repeat from $c_0=0.3$ at $N=9$ with both steps. The scalar reference evaluates the canonical gate directly, without the mobility implementation.
- Shear and viscous heating, $u=(\sin y,0,0),c=c_*,T_0=1$. The velocity is $u_x=e^{-\nu t}\sin y$, $\nu=\eta/\rho_m$. The mean temperature rise is $\rho_m(1-e^{-2\nu t})/(4C)$ and its cosine-$2y$ amplitude is $[\eta/(2C)](e^{-2\nu t}-e^{-4k_Tt/C})/(4k_T/C-2\nu)$.
- Pure conduction, $u=0,c=c_*,T_0=1+0.1\cos x\cos y\cos z$. Compare with $T=1+0.1e^{-3k_Tt/C}\cos x\cos y\cos z$.
- Golden-composition stationary control, $u=(0.3,-0.2,0.1),c=c_*,T=1$.

This gives 18 exact-reference trajectories. Normalized endpoint error must be at most $10^{-8}$. Temporal refinement must improve error by a factor of at least eight when the coarse error exceeds $10^{-11}$; errors below that floor are reported without an order claim.

### 3.2 Coupled three-dimensional controls

Use every combination of $N=9,15,21$ and $\Delta t=0.004,0.002$ through time $0.2$ for

$$
u_0=0.2(\sin x\cos y\cos z,-\cos x\sin y\cos z,0),
$$
$$
c_0=c_*+0.06(\cos x+0.5\cos2y+0.25\sin z),\quad
T_0=1+0.05\sin(x+y)+0.03\cos z.
$$

Record full initial/final fields and per-step energy components, entropy, entropy production, momentum, divergence and extrema. Require a nonzero generated vertical velocity above $10^{-8}$, a composition change above $10^{-6}$, and entropy increase above $10^{-7}$ on the finest run. Compare finest-step $N=15,21$ energy components and entropy within $10^{-5}$. The two timestep endpoints on each grid must differ by at most $10^{-7}$. Require total-energy drift at most $10^{-7}$ on $N=21$ and trapezoidal entropy-balance error at most $10^{-7}$. Spatial defects on the coarse grid are recorded independently of temporal error; no finite-grid exact-conservation theorem is claimed.

Add a conservative capillary-release trajectory at $N=15,21$, $\Delta t=0.002$, time $0.2$, with the same composition, $u_0=0,T_0=1$ and $\eta=k_T=\lambda=0$. Kinetic energy must increase by more than $10^{-10}$, while temperature stays unchanged within $10^{-12}$. At $N=21$, require $|\Delta K+\Delta E_c|\leq10^{-12}+0.01\Delta K$ as well as total-energy drift below $10^{-7}$. The detection floor lies below the leading constant-$g(c_*)$ estimate of approximately $9\times10^{-10}$ from the unequal-frequency mode pairs; this estimate fixes the floor before execution.

Add a Galilean-boosted finest coupled trajectory, $U=(0.3,-0.2,0.1)$, and compare against a Fourier translation of the unboosted final fields by $-Ut$, adding $U$ back to velocity. Normalized discrepancy must be at most $10^{-6}$.

This gives nine coupled/capillary/boost trajectories and 27 native trajectories in total. Every trajectory must remain finite with $0<c<1,T>0$, maximum velocity divergence below $10^{-10}$ and momentum drift below $10^{-10}$. Sampled composition must stay in its declared continuum interval to $10^{-10}$: $[c_*-0.105,c_*+0.105]$ for the spatially varying controls and the interval between $c_0$ and $c_*$ for homogeneous controls. A sampled initial extremum is insufficient to bound a translated continuous profile.

### 3.3 Independent numerical reconstruction

- At each coupled initial field, compare a centered finite-difference derivative of the discrete total energy and entropy along the actual RHS with the separately contracted variational derivatives; perturbation $10^{-6}$, absolute tolerance $10^{-7}$. These check the implementation's state-dependent energy and entropy, not source strings.
- Independently implement periodic differentiation matrices from a direct trigonometric sum, full tensor stress, gate/mobility and heat terms on $N=9$. Compare its RHS with the FFT RHS within $10^{-10}$, and evolve it with SciPy DOP853 at relative/absolute tolerance $10^{-11}$ through time $0.2$. The native fine-step endpoint must agree within $10^{-8}$. This is one separate reference trajectory and uses no native differential operators or native RHS.
- Reconstruct stored kinetic, composition, thermal energy and entropy from raw endpoint arrays independently of the solver diagnostics. Compare to recorded values within $10^{-11}$.

## 4. Decisions and immutable evidence

All symbolic equalities must simplify to zero; numerical tolerances are fixed above. Check status is `PASS` only if every scheduled check succeeds. The selected closure receives `SUPPORTS` for the declared analytical/numerical budget claim only with successful controls. A mismatched identity receives `CONTRADICTS`; inconclusive discretization evidence remains `INCONCLUSIVE`. Physical-fluid replacement, microscopic viscosity and arbitrary-data global regularity remain `UNESTABLISHED` regardless of numerical status.

Capture the protocol, model, verifier, canonical reference and action source as immutable raw-byte snapshots before calculation. Refuse existing receipt, source-snapshot, input-manifest and array paths. Retain failures and source identities. Any change to equations, controls or tolerances after execution requires a separate qualification and retains the original result. An implementation repair may rerun the same protocol with new source snapshots and a fresh output path; it must be disclosed in reconciliation. Do not retune coefficients to pass.

## References

- `turbulence/cassi-fluid-feasibility.md`—conditional mechanical reduction and native-force boundary.
- `foundations/interscale-current-soliton.md`—first-order action and gradient energy.
- `foundations/cassi-theory-reference.md`—canonical conversion and gate.
- `computations/cassi_fluid_thermodynamics.py`—selected thermal fluid evolution.
- `computations/verify_cassi_fluid_thermodynamics.py`—fixed analytical and numerical controls.
- G. Planas, [On a non-isothermal incompressible Navier–Stokes–Allen–Cahn system](https://doi.org/10.1007/s00605-021-01564-2)—established model class; its existence theorems are separate from this selected system.
