# Cassi Fluid Mechanics: Conservative Reduction and Native-Force Boundary

## Status: Derived conditional conservative reduction and native-force obstruction / Tested solver controls / Open physical-fluid completion—September 2026

## Abstract

The first-order Cassi matter action supplies a conditional mass-current map, pressure, anisotropic counterflow momentum flux, dispersive gradient stress and conserved energy. The canonical real-density equations separately preserve nonnegativity and dissipate composition imbalance and a relative entropy under smooth common incompressible advection. These results belong to different temporal laws. The conservative matter action supplies no irreversible conversion or positive viscosity, and its common-phase branch excludes smooth transverse shear.

The implemented projected-velocity solver passes the fixed shear, vortex and prescribed-force controls, but its self-sourced force has a nonzero periodic mean for strictly positive density data. An exact native solution accelerates uniformly while its scalar profiles only translate. This excludes a closed constant-inertia internal-stress interpretation and an additive translation-invariant scalar-energy closure for that coupling. The separate expanding force attenuation retains a nonzero mean.

The fixed schedule passes **246 checks**, including **28 actual native trajectories** and comparisons with independently implemented NumPy RK4 at two three-dimensional grids. The physical-model promotion decision is **REJECT** for the supplied sectors as a closed ordinary-fluid replacement. Material normalization, rotational transport, thermal closure and a justified positive-viscosity limit remain open. No concentration-arrest experiment is run.

## 1. Three state conventions

A fluid interpretation requires both a conserved quantity and a rule connecting its current to physical momentum. The available Cassi sectors make different assignments.

| Sector | State and time law | Established scope |
|---|---|---|
| Canonical density equations | Two reference-normalized nonnegative real densities, shared advection, optional diffusion, rank-one conversion | Density-sum continuity, positivity and mathematical dissipation under stated hypotheses |
| First-order matter action | Complex doublet with first-order Schrödinger time term, positive spatial stiffness and density potential | Conditional number currents and conservative momentum/energy reduction |
| Source-free charged particle action | Second-order covariant charged-field time kinetics, adjoint and gauge fields, Gauss constraint; a separate neutral carrier | Distinct constrained particle-sector dynamics; first-order population-current formulas do not transfer automatically |

The action in `foundations/interscale-current-soliton.md` normalizes $n=\Psi^\dagger\Psi$ as number density per flat, dimensionless scale measure $d\mathfrak s$. The three-dimensional matter reduction below sets the gauge coupling and scale derivatives to zero and uses a normalized scale slice. Balanced scale-boundary number flux alone would ensure integrated continuity; reducing the full stress and energy also requires the declared scale-independent field ansatz. This ungauged reduction makes no assertion that setting a sourced gauge field to zero solves the coupled nonzero-coupling system.

With one externally supplied mass $m$ per population unit,

$$
[n]=L^{-3},\qquad K_x=\frac{\hbar^2}{m},\qquad \rho_m=mn.
$$

Then $[K_x]=\hbar L^2/T$, $[\lambda_\rho]=[\lambda_\varphi]=\hbar L^3/T$, $[\rho_m]=ML^{-3}$, $[u]=L/T$, and momentum flux has units $ML^{-1}T^{-2}$. Neither $m$ nor the physical reference density is derived here.

For the canonical real-density sector, restore an external reference density $\rho_*$ before giving the gate dimensional fields:

$$
q=\frac{\rho_{\rm phys}^2}
{\rho_{\rm phys}^2+\varphi^{-2}\rho_*^2+\varepsilon_{\rm phys}^2}.
$$

Its conversion coefficient has units $[\lambda]=T^{-1}$ and diffusivity has units $[D]=L^2/T$. The action coefficient $\lambda_\varphi$ and the conversion rate $\lambda$ are independent quantities. If $Y,I$ count species with unequal masses, their equal-and-opposite conversion gives

$$
\partial_t\rho_m\big|_{\rm conv}=(m_I-m_Y)\kappa\varepsilon.
$$

Mass conservation then requires an equal-mass assignment or an additional carrier for the defect. An energy-density interpretation likewise requires specified conversion energetics and heat transport. The 47-parameter inventory and numbered prediction catalog acquire no new material constant or empirical prediction from this study.

## 2. Conservative momentum and stress

### 2.1 Species motion

The complex action has enough phase information to define a conditional mechanical current. On a smooth positive-density region, write $\psi_a=\sqrt{n_a}e^{i\theta_a}$, $a\in\{Y,I\}$, and use

$$
V=\frac{\lambda_\rho}{4}(n-n_0)^2
+\frac{\lambda_\varphi}{2}\varepsilon_n^2,
\qquad n=n_Y+n_I,\qquad \varepsilon_n=n_Y-\varphi n_I.
$$

The reduced Lagrangian density is

$$
\mathcal L=-\hbar\sum_a n_a\partial_t\theta_a
-\sum_a\left[\frac{\hbar^2}{2m}|\nabla\sqrt{n_a}|^2
+\frac m2n_a|v_a|^2\right]-V,
\qquad v_a=\frac{\hbar}{m}\nabla\theta_a.
$$

Variation gives

$$
\partial_tn_a+\nabla\cdot(n_av_a)=0,
\qquad
\hbar\partial_t\theta_a+\frac m2|v_a|^2+\mu_a+Q_a=0,
$$

where

$$
\mu_Y=\frac{\lambda_\rho}{2}(n-n_0)+\lambda_\varphi\varepsilon_n,
\qquad
\mu_I=\frac{\lambda_\rho}{2}(n-n_0)-\varphi\lambda_\varphi\varepsilon_n,
\qquad
Q_a=-\frac{\hbar^2}{2m}\frac{\Delta\sqrt{n_a}}{\sqrt{n_a}}.
$$

The potential is invariant under the two independent component phase symmetries. With closed spatial and scale boundaries, each population integral is conserved. The potential changes chemical potentials and phases without generating canonical density conversion.

### 2.2 Barycentric flux and stress signs

Relative motion contributes an anisotropic momentum flux even when total number current vanishes. Define

$$
u=\frac{n_Yv_Y+n_Iv_I}{n},\qquad
w=v_Y-v_I,\qquad
\rho_{\rm cf}=\frac{mn_Yn_I}{n}.
$$

The displayed $u$ is barycentric velocity; viscosity is denoted by $\nu$ only in the numerical solver sections. The mechanical momentum density and kinetic-energy split are

$$
p_i=\hbar\sum_an_a\partial_i\theta_a=\rho_mu_i,
\qquad
\sum_a\frac m2n_a|v_a|^2
=\frac12\rho_m|u|^2+\frac12\rho_{\rm cf}|w|^2.
$$

The density potential gives

$$
P=\sum_an_a\mu_a-V
=\frac{\lambda_\rho}{4}(n^2-n_0^2)
+\frac{\lambda_\varphi}{2}\varepsilon_n^2,
\qquad
\partial_iP=\sum_an_a\partial_i\mu_a.
$$

For each species,

$$
\Pi^{Q,a}_{ij}=\frac{\hbar^2}{4m}
\left[\frac{(\partial_in_a)(\partial_jn_a)}{n_a}
-\partial_i\partial_jn_a\right],
\qquad
\partial_j\Pi^{Q,a}_{ij}=n_a\partial_iQ_a.
$$

Combining the species equations yields

$$
\boxed{\partial_t(\rho_mu_i)+\partial_jT_{ij}=0,\qquad
T_{ij}=\rho_mu_iu_j+P\delta_{ij}
+\rho_{\rm cf}w_iw_j+\sum_a\Pi^{Q,a}_{ij}.}
$$

Here $T$ is momentum flux. With the Cauchy convention
$\partial_t(\rho_mu_i)+\partial_j(\rho_mu_iu_j)=\partial_j\sigma_{ij}$,

$$
\sigma_{ij}=-P\delta_{ij}-\rho_{\rm cf}w_iw_j-\sum_a\Pi^{Q,a}_{ij}.
$$

The sign distinction fixes the actual force. At imposed golden composition, $\rho_{\rm cf}=mn\varphi^{-3}$; this coefficient does not select the relative velocity or a universal inward force.

### 2.3 Conserved energy and the fluid-limit boundary

The gradient term stores energy and gives dispersion. The Hamiltonian is

$$
\mathcal E=\sum_a\left[\frac m2n_a|v_a|^2
+\frac{\hbar^2}{2m}|\nabla\sqrt{n_a}|^2\right]+V.
$$

One local Noether-flux representative is

$$
J_{\mathcal E,i}=-\frac{\hbar^2}{m}\sum_a
\operatorname{Re}\left[(\partial_t\psi_a)^*\partial_i\psi_a\right],
\qquad \partial_t\mathcal E+\nabla\cdot J_{\mathcal E}=0.
$$

Periodic or decaying data give conserved integrated energy. The first-order action has no thermal variable, positive-viscosity stress or irreversible heat-production term.

An exact proportional-field ansatz $\psi_Y=\sqrt\varphi e^{i\theta_0}\psi_I$ is compatible and invariant with equal stiffness, matching boundary data and smooth nonzero evolution in this ungauged matter branch. Both species have equal chemical potentials, quantum potentials and velocities. Separate population conservation prevents generic relaxation into this ansatz from arbitrary data.

On that branch, longitudinal perturbations about $n=n_0$ have

$$
\boxed{\omega^2=\frac{n_0\lambda_\rho}{2m}k^2
+\frac{\hbar^2}{4m^2}k^4.}
$$

The frequencies are real. The $k^4$ contribution is dispersive and produces no viscous decay rate. Dropping the gradient term in a smooth long-wavelength approximation gives a formal conservative Euler reduction. A controlled singular limit and a positive-viscosity Navier–Stokes limit are separate open requirements.

Smooth phase velocities satisfy $\nabla\times v_a=0$. For variable composition,

$$
\nabla\times u=\nabla(n_Y/n)\times w.
$$

The constant-composition common-phase branch is therefore irrotational. It cannot represent the ordinary smooth transverse shear $u_x=U\sin y$. Gauge curvature, nodal vortices, thermal excitations or additional velocity degrees of freedom require their own mechanical derivation. Positive energy in the complex fields alone establishes no bound for velocity derivatives across density zeros and no general concentration-arrest result.

### 2.4 Gauge and scale-window boundaries

The separate charged particle action has different temporal momenta. Directly gauging the first-order fundamental doublet gives a homogeneous Gauss-source magnitude $\hbar g_Qn_0/2>0$, by the Pauli identity. The source-free completion in `foundations/particle-stationary-action-closure.md` instead uses second-order charged-field kinetics and an explicit Gauss constraint. Its static potential does not supply the canonical irreversible source, and $\int\Psi^\dagger\Psi$ cannot be adopted as its conserved population from the first-order formulas.

The scale-coordinate number current, gauge-source current and spatial-momentum flux through scale are distinct quantities. The mechanical window law requires

$$
\partial_tp_i+\partial_jT_{ij}+\partial_{\mathfrak s}T_{i\mathfrak s}
=f_i^{\rm ext},
\qquad
F_i^{(\mathfrak s)}=\int_V[T_{i\mathfrak s}(\mathfrak s_-)
-T_{i\mathfrak s}(\mathfrak s_+)]\,d^3x.
$$

The scale-independent reduction has no such nonzero scale flux. A constitutive assignment and boundary/return-channel ledger are needed before using the interscale current as a mechanical stress or attenuation mechanism.

## 3. Canonical density positivity and dissipation

The selected density equations control population and composition under their specified transport law. Let $Y=E_Y$, $I=E_I$, $\rho=Y+I$, $\varepsilon=Y-\varphi I$ and $\kappa=\lambda(1-q)\geq0$. With smooth common $u$, $\nabla\cdot u=0$, equal $D\geq0$, and periodic or impermeable/no-flux scalar boundaries,

$$
D_t\rho=D\Delta\rho,\qquad
D_t\varepsilon=D\Delta\varepsilon-(1+\varphi)\kappa\varepsilon.
$$

Thus $\int\rho$ is conserved. At $D=0$, density is materially conserved; advection can still change its value at a fixed Eulerian point. At $Y=0$, the reaction supplies $\kappa\varphi I\geq0$; at $I=0$, it supplies $\kappa Y\geq0$. The coupled maximum principle or characteristic ODE preserves nonnegativity while the stated smooth transport assumptions hold. Strict positivity requires the appropriate nonzero initial populations or positive reaction coupling; $\lambda=0$ permits a channel to remain identically zero.

Integration by parts gives

$$
\boxed{\frac12\frac d{dt}\int\varepsilon^2
=-D\int|\nabla\varepsilon|^2
-(1+\varphi)\int\kappa\varepsilon^2\leq0.}
$$

For constant positive reference populations $Y_*/I_*=\varphi$, the nonnegative relative entropy

$$
\mathcal H=\int\left[
Y\log(Y/Y_*)-Y+Y_*+I\log(I/I_*)-I+I_*\right]
$$

satisfies

$$
\boxed{\mathcal H'=-D\int\left(\frac{|\nabla Y|^2}{Y}
+\frac{|\nabla I|^2}{I}\right)
-\int\kappa(Y-\varphi I)\log\frac{Y}{\varphi I}\leq0.}
$$

The logarithmic identity is classical for positive fields and extends through zero by the usual regularized/lower-semicontinuous convention. The reaction sign follows monotonicity of the logarithm. Temperature, standard chemical potentials, conversion enthalpy and a closed heat budget are still needed to identify this mathematical functional with physical free energy or entropy. Common advection, incompressibility, equal diffusivity and the stated boundaries are essential hypotheses.

### 3.1 Exact implementation correspondence

The base `TwoFluid3DGPU` uses ungated $\kappa=\lambda$. Its default chemotactic drift is additional to the canonical pair; this study sets $\chi=0$. `ExpandingTwoFluid3DGPU` supplies the single canonical gate when `qi_gate=True`, `gate_model='single'`, and `qi_memory=False`. Its default gate is off, and its default `phi_inv2=0.382` is rounded. The fixed controls explicitly pass $\varphi^{-2}=0.38196601125010515$, use a static comoving box and disable all other optional terms. No default or constitutive behavior is changed.

The base RK2 and spectral discretization have no general discrete positivity theorem. The expanding class applies a floor and global mass renormalization after each step. For homogeneous $(Y,I)=(10^{-4},1)$ with zero continuum RHS, a single step gives

$$
(Y,I)=(0.0009991008991008991,\ 0.9991008991008990),
\qquad Y+I=1.0001.
$$

The total is preserved while composition changes. This is a measured discrete intervention, independent of the continuum positivity proof. The corresponding base-solver state remains stationary.

The homogeneous ungated solution has $\varepsilon(t)=\varepsilon_0e^{-\lambda(1+\varphi)t}$. The single-gate reference uses the implicit exact integral in the preregistration. Both match the native endpoints with maximum normalized error $1.0078716822\times10^{-7}$ across eight trajectories, against $2\times10^{-6}$.

## 4. A native-force obstruction

### 4.1 Periodic mean momentum

A periodic divergence of internal stress has zero spatial mean. The base solver violates that necessary condition under its constant-inertia velocity interpretation. With $D=\lambda=\chi=0$, no external density and no dispersion modification, it evolves

$$
\partial_tu=\mathbb P[-(u\cdot\nabla)u+\pi\nabla\Phi]+\nu\Delta u,
\qquad
\Delta\Phi=\rho-\langle\rho\rangle,
\qquad \pi=Y-I.
$$

On the $2\pi$-periodic cube, take

$$
\rho=4+\cos x,\qquad \pi=b\sin x,\qquad
Y=(\rho+\pi)/2,\quad I=(\rho-\pi)/2,
\qquad b=\pm1.
$$

Both species are strictly positive. The potential is $\Phi=-\cos x$, so

$$
\boxed{\mathbb P(\pi\nabla\Phi)=\frac b2e_x.}
$$

All nonzero longitudinal Fourier modes are removed, while the zero mode is retained. The mean force is exactly $b/2$. The fixed $16^3$ and $24^3$ native RHS calculations reproduce both signs, with and without a uniform boost.

At the boosted state $u=e_x$, kinetic work is $b/2$. The scalar RHS is a rigid translation, under which every differentiable translation-invariant functional $\mathcal U[Y,I]$ has zero instantaneous derivative. Therefore no additive energy $K+\mathcal U[Y,I]$ closes this native force under constant inertia. Extra momentum/energy carriers or an explicitly open forcing interpretation would change that assumption. Removing the mean by hand would change the equations and would leave the broader constitutive problem unaddressed.

### 4.2 Actual self-acceleration

The obstruction persists during a smooth native evolution. For $b=1$ and initially zero velocity, the exact solution is

$$
\boxed{u=(t/2,0,0),\quad
\rho=4+\cos(x-t^2/4),\quad
\pi=\sin(x-t^2/4).}
$$

Scalar profiles translate, the mean flow accelerates, and $K=t^2/8$. At $t=0.2$, the fine-step $24^3$ run gives $\langle u_x\rangle=0.1000000006616502$ and $K=0.00500000006616502$, against exact values $0.1$ and $0.005$. Four grid/timestep trajectories agree. This is a globally smooth self-acceleration example of the supplied coupling, with no finite-time singularity claim.

### 4.3 Attenuation leaves the mechanical issue

The static expanding force contains the factor

$$
s_f=\frac{|\pi\nabla\Phi|^2}
{|\pi\nabla\Phi|^2+0.2^2+10^{-10}}.
$$

It suppresses weak forces and approaches one for large force. It supplies no upper bound on force magnitude. For the same positive-density witness, independent one-dimensional quadrature gives mean $0.4438476007255179$ for $b=1$. The native means are $0.44301180705796894$ at $16^3$ and $0.4438718764219250$ at $24^3$; changing $b$ reverses the sign. The rational multiplier creates higher harmonics, so these rows use the separately frozen $10^{-2}$ integration tolerance. Both means remain nonzero.

The bridge implementation in `two-fluid/cassi_bridge_v2.py` instead modulates the potential by a gradient-conditioned factor. Its comments and CLI describe that operation; this study supplies no bridge trajectory or bridge-specific mechanical verdict.

## 5. Fixed solver evidence

### 5.1 Ordinary-flow baselines

The ordinary-flow controls exercise the actual base RHS and RK2 step with constant densities, supplied $\nu=0.2$ and zero native information force. The forced shear adds the declared external force at both stages through a benchmark subclass. Each analytical flow uses $16^3$ and $24^3$ grids, $T=0.2$, and timesteps $0.004,0.002$.

| Control | Native trajectories | Maximum normalized endpoint error | Frozen tolerance |
|---|---:|---:|---:|
| Ungated and single-gated homogeneous conversion | 8 | $1.0079\times10^{-7}$ | $2\times10^{-6}$ |
| Native self-acceleration, velocity endpoint | 4 | $2.6264\times10^{-9}$ | $2\times10^{-6}$ |
| Decaying sinusoidal shear | 4 | $4.1019\times10^{-9}$ | $2\times10^{-6}$ |
| Embedded two-dimensional Taylor–Green vortex | 4 | $3.1547\times10^{-8}$ | $2\times10^{-6}$ |
| Prescribed-force shear from rest | 4 | $2.0510\times10^{-9}$ | $2\times10^{-6}$ |
| Three-dimensional Taylor–Green vortex versus independent RK4 | 4 | $3.7746\times10^{-8}$ | $2\times10^{-5}$ |

The three-dimensional vortex uses $T=0.05$, native timesteps $0.002,0.001$, and independently implemented same-grid NumPy RK4 at timestep $0.00025$. At $24^3$ and native timestep $0.001$, the vertical velocity grows from zero to maximum magnitude $0.01165613965336212$, confirming that the trajectory includes three-dimensional nonlinear evolution. Its reference error is $9.4185\times10^{-9}$ and kinetic energy falls from $0.125$ to $0.11771998922643856$.

The maximum recorded divergence across all trajectories is $4.8743\times10^{-15}$, and the maximum total-density drift is $2.6646\times10^{-15}$. Temporal refinement satisfies the frozen comparisons. The $16^3$/$24^3$ fine-step vortex fields differ by at most $2.3748\times10^{-9}$ on their common $8^3$ sample set. For the ordinary NS controls, the maximum trapezoidal energy-budget residual is $4.7333\times10^{-8}$. The self-accelerating family has the distinct nonzero native-work budget in §4.

These are short-time numerical controls of the inherited NS sector. They establish neither a continuum convergence theorem nor a Cassi derivation of viscosity, turbulence statistics or physical fluid behavior.

### 5.2 Accepted receipt and immutable diagnostics

The accepted receipt is **`runs/cassi_fluid_feasibility/qualified/verification.json`**, schema `cassi.fluid-feasibility.verification.v1`. It records **246/246 checks passing**, including **49 symbolic checks**, **28 native trajectories**, two single-step floor controls and two independent three-dimensional reference evolutions. The adjacent `verification.inputs.json`, `verification.sources/` and `verification.trajectories.npz` belong to this accepted receipt. Raw histories retain time, kinetic energy, enstrophy, divergence, mean velocity, density means/minima, viscous dissipation and prescribed external work; endpoint fields and independent reference fields are retained separately.

| Accepted input or output | Raw SHA-256 |
|---|---|
| Preregistration | `f95d370a269c806c51b4e8c58cc24260b548591244119a0c500ba7e41ee423fe` |
| Executable verifier | `29c04dd3900cdedda0f382e0a65cad468e7a4b155083f720ba33d8bedaff7256` |
| Native density solver | `368e5539e3e1ae9205c543ed413350c8c3aa83c395809012fa44891d0aa6468c` |
| Accepted raw trajectory archive | `a4793da2f7c7fa8bb1b31e31e68f9bc102a3f61ba95f00357cc2204b5c20b9d9` |

The input manifest also hashes the first-order action, second-order completion, scale-stress boundary and canonical density reference. All seven current inputs, manifest entries and source snapshots agree.

The raw hashes identify the execution bytes in `verification.sources/`.
The separate `runs/cassi_fluid_feasibility/qualified/git-provenance.json`
compares all seven inputs with commit `df4dbdcf`: four committed blobs match
the raw receipt hashes, while the native solver, second-order completion and
canonical density reference differ solely by CRLF/LF line endings.
The repository retains its `core.autocrlf=true` transport policy.
Validation of this accepted run uses the preserved raw source snapshots.
A reproduction binds its own checkout bytes in a fresh manifest and source
directory; line-ending normalization never replaces an accepted raw hash.

The root-level **`runs/cassi_fluid_feasibility/verification.json` is an ERROR diagnostic**, excluded from qualification. It records 49 successful symbolic checks and no trajectory; its harness requests an absent lowercase coordinate attribute. It retains its own verifier snapshot and input manifest. The accepted run uses the native uppercase arrays with physical $x$ on the last Fourier axis. Both receipts bind the same preregistration; fixtures, equations, grids, timesteps and tolerances agree. The diagnostic is preserved without replacement.

Two independent read-only analytical reviews confirm the qualified action and density identities. The accepted interpretation restricts strict positivity to the required hypotheses, keeps the two temporal branches separate, and distinguishes scalar translation from pointwise stationarity in the energy obstruction. Numerical receipt/array reconciliation and those scope qualifications are retained in `runs/cassi_fluid_feasibility/qualified/reconciliation.json`.

To reproduce, use a fresh output path from the CassiTheory directory:

```text
python computations/verify_cassi_fluid_feasibility.py --output runs/cassi_fluid_feasibility/reproduction/verification.json
```

Existing output, manifest, source-directory and trajectory paths are refused. No generated receipt is a substitute for the analytical derivations above.

## 6. Feasibility decision

The bounded study establishes a usable conservative mechanical branch and identifies why the supplied sectors cannot yet serve as a closed ordinary-fluid replacement.

| Requirement | Finding | Decision scope |
|---|---|---|
| Current-to-mass-momentum map | $p=mn u$ from the ungauged first-order action with supplied $m$ and normalization | Conditional derivation |
| Mechanical pressure, counterflow and gradient stress | Exact flux and energy laws in §2 | Conditional derivation |
| Canonical density positivity and entropy | Inward reaction and nonnegative mathematical dissipation under §3 hypotheses | Conditional derivation |
| Same conservative action generates canonical conversion | Independent first-order population symmetries supply no irreversible source | Open reduction required |
| Closed native internal force | Nonzero mean force and additive-energy obstruction, reproduced in native RHS and trajectories | **CONTRADICTS** |
| Positive-viscosity NS correspondence | Supplied solver viscosity passes baselines; the action derives dispersion and has no shear-relaxation mechanism | Unestablished |
| Promotion as a closed material-fluid alternative | Required mechanical and thermodynamic correspondence is absent | **REJECT** for the supplied sectors |
| Concentration arrest | Not run under the stopping rule | No claim |

A further physical-fluid program must select the material density and inertia map, an equation of state, rotational transport degrees of freedom, and a thermal/irreversible sector with a closed heat and momentum budget. If degrees of freedom are eliminated to obtain viscosity or conversion, their state, approximation, dissipation sign and domain of validity must be derived. Gauge and scale-boundary forces require their own complete stress ledger.

The present positive results support work on that constitutive problem. They do not justify adding a coherence-dependent damping factor, removing an inconvenient zero mode, or promoting a stable finite-grid evolution into physical concentration arrest. The original Navier–Stokes investigations retain their separate mathematical scope.

## References

- `foundations/interscale-current-soliton.md` §§1–3—first-order complex action, normalization and population currents.
- `foundations/particle-stationary-action-closure.md` §§2–3—Gauss obstruction and separate second-order charged completion.
- `foundations/interscale-stress-attenuation-boundary.md` §§1–2—spatial-momentum flux and scale-window conservation.
- `foundations/cassi-theory-reference.md` §§2.2–2.4—canonical real-density conversion and gate.
- `two-fluid/cassi_two_fluid_3d_gpu.py`—native projected-velocity and scalar implementation.
- `two-fluid/cassi_bridge_v2.py`—distinct gradient-conditioned potential modulation.
- `computations/cassi-fluid-feasibility-prereg.md`—fixed analytical and solver controls, tolerances and stopping rule.
- `computations/verify_cassi_fluid_feasibility.py`—executable symbolic and native-trajectory verification.
- `parameter-inventory.md` §§3.3,6—supplied numerical coefficients and physical-normalization boundary.
- `field-experience/probe-outcome-ledger.md`—accepted classifications and raw-evidence location.
