# Cassi Fluid Mechanics: Conservative Reduction and Thermal Closure

## Status: Derived conditional mechanical and thermal identities / Tested solver controls / Open physical-fluid completion—September 2026

## Abstract

The first-order Cassi matter action supplies a conditional mass-current map, pressure, anisotropic counterflow momentum flux, dispersive gradient stress and conserved energy. The canonical real-density equations separately preserve nonnegativity and dissipate composition imbalance and a relative entropy under smooth common incompressible advection. These results belong to different temporal laws. The conservative matter action supplies no irreversible conversion or positive viscosity, and its common-phase branch excludes smooth transverse shear.

The implemented projected-velocity solver passes the fixed shear, vortex and prescribed-force controls, but its self-sourced force has a nonzero periodic mean for strictly positive density data. An exact native solution accelerates uniformly while its scalar profiles only translate. This excludes a closed constant-inertia internal-stress interpretation and an additive translation-invariant scalar-energy closure for that coupling. The separate expanding force attenuation retains a nonzero mean.

The native-solver schedule passes **246 checks**, including **28 actual native trajectories** and comparisons with independently implemented NumPy RK4 at two three-dimensional grids. The physical-model promotion decision is **REJECT** for those supplied sectors as a closed ordinary-fluid replacement.

A selected constant-density reacting capillary fluid couples the restricted composition energy to rotational velocity and temperature. Its internal stress conserves periodic momentum, its heat equation closes total energy, and its full-affinity reaction produces nonnegative entropy. Homogeneous composition follows canonical gated conversion exactly. The separate thermal schedule passes **395 checks across 27 model trajectories**, with a differentiation-matrix reference evolution and resolved capillary-energy release. These are conditional constitutive results; material normalization, microscopic transport coefficients, a rotational hydrodynamic reduction and arbitrary-data global regularity remain open. No concentration-arrest experiment is run.

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

The logarithmic identity is classical for positive fields and extends through zero by the usual regularized/lower-semicontinuous convention. The reaction sign follows monotonicity of the logarithm. Common advection, incompressibility, equal diffusivity and the stated boundaries are essential hypotheses. Identifying this mathematical functional with physical free energy or entropy requires temperature, standard chemical potentials, conversion energetics and a closed heat budget. Section 7 supplies a selected constant-density thermal model with those explicit constitutive assumptions; its microscopic identification remains open.

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

The physical-fluid program requires a material density and inertia map, an equation of state, rotational transport degrees of freedom, and a justified irreversible reduction. Section 7 declares a thermal/irreversible sector with a closed heat and momentum budget. Deriving viscosity or conversion by eliminating microscopic degrees of freedom would additionally require their state, approximation, dissipation sign and domain of validity. Gauge and scale-boundary forces require their own complete stress ledger.

The original Navier–Stokes investigations retain their separate mathematical scope. A stable finite-grid evolution supplies no concentration-arrest or arbitrary-data regularity theorem.

## 7. Selected reacting capillary and thermal fluid

The composition-gradient energy provides an internal force with an explicit mechanical energy destination. Adding a temperature variable makes the irreversible exchanges calculable. The state is a divergence-free velocity $u$, a composition fraction $0<c<1$ and temperature $T>0$ on a periodic domain. Total physical number density $n_0$ and inertia $\rho_m$ are fixed. Rotational velocity is a supplied hydrodynamic degree of freedom.

### 7.1 Restricted energy and constitutive inputs

At fixed $n_Y=n_0c$ and $n_I=n_0(1-c)$, the amplitude-gradient part of the first-order action becomes

$$
\frac{\hbar^2}{2m}\left(|\nabla\sqrt{n_Y}|^2+|\nabla\sqrt{n_I}|^2\right)
=\frac{\hbar^2n_0}{8mc(1-c)}|\nabla c|^2.
$$

Consequently, the selected composition energy and capillary tensor are

$$
c_*=\frac{\varphi}{1+\varphi},\quad \delta=c-c_*,
\qquad e_c=\frac a2\delta^2+\frac{g(c)}2|\nabla c|^2,
\qquad g(c)=\frac{\gamma}{c(1-c)},\qquad
A=g\nabla c\otimes\nabla c,
$$
$$
a=\lambda_\varphi n_0^2(1+\varphi)^2,\qquad
\gamma=\frac{\hbar^2n_0}{4m},\qquad
\mu=\frac{\delta\int e_c}{\delta c}
=a\delta+\frac{g'}2|\nabla c|^2-\nabla\cdot(g\nabla c).
$$

The variation supplies the gradient force. It does not by itself establish the shared rotational velocity, incompressible limit or irreversible law. The physical dimensions are $[a]=\text{energy}/L^3$, $[\gamma]=\text{energy}/L$, $[\mu]=\text{energy}/L^3$. Both action coefficients $\lambda_\rho,\lambda_\varphi$ retain the units in §1.

Take thermal internal energy $CT$ and entropy density

$$
s=C\log(T/T_*)-b h(c),\qquad
h(c)=c\log\frac c{c_*}+(1-c)\log\frac{1-c}{1-c_*},
$$
$$
h'(c)=\log\frac{c(1-c_*)}{c_*(1-c)},\qquad
r(c)=\frac{h'(c)}{c-c_*},\qquad
r(c_*)=\frac1{c_*(1-c_*)}>0.
$$

Here $C>0$ is the volumetric heat capacity, $b>0$ is the mixing-entropy density coefficient, and $T_*>0$ fixes the thermal entropy reference. The component entropy reference in $h$ is a constitutive choice that fixes the homogeneous equilibrium composition. This logarithmic thermal law is used on $T>0$ and supplies no zero-temperature equation of state.

The corresponding Helmholtz density is $f=e_c+CT-Ts$. It satisfies $\partial_Tf=-s$, $f-T\partial_Tf=e_c+CT$ and $\partial_T\partial_cf=-\partial_cs$. At fixed temperature field, its variational composition derivative is $\mathcal A=\mu+bTh'$. These identities are compatible with constant $a,b,C$.

For reference-normalized populations $Y=\rho_{\rm ref}c$, $I=\rho_{\rm ref}(1-c)$, with dimensionless $\rho_{\rm ref}$, set

$$
\varepsilon=\rho_{\rm ref}(1+\varphi)\delta,\quad
q=\frac{\rho_{\rm ref}^2}{\rho_{\rm ref}^2+\varphi^{-2}+\varepsilon^2},
\quad \kappa=\lambda(1-q).
$$

The selected affinity, mobility and conversion rate are

$$
\boxed{\mathcal A=\mu+bTh',\qquad
M=\frac{(1+\varphi)\kappa}{a+bTr(c)},\qquad R=-M\mathcal A.}
$$

The secant $r$ is positive and continuous, so $M\geq0$ for $\lambda\geq0$; $M=0$ when conversion is disabled. Its dimensions are $L^3/(\text{energy}\times\text{time})$. This mobility is chosen to preserve homogeneous canonical conversion, rather than inferred from microscopic kinetics.

### 7.2 Momentum, energy and entropy balances

Each dissipative loss has an explicit heat destination. With constant coefficients, $S=(\nabla u+\nabla u^{\mathsf T})/2$ and $D_t=\partial_t+u\cdot\nabla$, the equations are

$$
\boxed{\begin{aligned}
\nabla\cdot u&=0,\\
\rho_mD_tu&=-\nabla p+\nabla\cdot(2\eta S)-\nabla\cdot A,\\
D_tc&=R,\\
CD_tT&=k_T\Delta T+2\eta S:S-\mu R.
\end{aligned}}
$$

The positive coefficients $\eta,k_T$ are dynamic viscosity and thermal conductivity; zero values are allowed. Canonical scalar diffusion is set to zero. The composition equation includes the gradient response carried by its variational affinity. This is a selected nonisothermal Navier–Stokes/Allen–Cahn-type closure; its stated identities do not import existence theorems for other members of that model class.

The identity $\mu\nabla c=\nabla e_c-\nabla\cdot A$ fixes the stress sign. For Cauchy stress $\sigma=-pI+2\eta S-A$,

$$
\partial_t(\rho_mu)+\nabla\cdot(\rho_mu\otimes u-\sigma)=0,
\qquad \frac{d}{dt}\int\rho_mu\,dx=0.
$$

Composition gradients are transported covariantly:
$D_t\nabla c=\nabla R-(\nabla u)^{\mathsf T}\nabla c$. Their energy budget is

$$
D_te_c=\mu R+\nabla\cdot(g\nabla c\,R)-A:\nabla u.
$$

The final term cancels capillary work in the kinetic-energy equation. It can be nonzero: for $\gamma>0$, let $\chi=2\sqrt\gamma\arcsin\sqrt c$, so $A=\nabla\chi\otimes\nabla\chi$. With $u=\sin y\,e_x$ and $\chi=\chi_0+\alpha\cos x+\beta\cos(x+y)$ contained in $(0,\pi\sqrt\gamma)$, the normalized periodic mean is exactly $\langle A:S\rangle=\alpha\beta/4$.

For $e=\rho_m|u|^2/2+e_c+CT$, the complete local energy flux is

$$
\boxed{\partial_te+\nabla\cdot
\left(eu-\sigma u-g\nabla c\,R-k_T\nabla T\right)=0.}
$$

Periodic total energy is conserved. The term $g\nabla c\,R$ is part of the energy flux; omitting it loses the local gradient-energy exchange.

The entropy equation is

$$
\boxed{\partial_ts+\nabla\cdot
\left(su-\frac{k_T\nabla T}{T}\right)
=\frac{2\eta S:S+M\mathcal A^2}{T}
+\frac{k_T|\nabla T|^2}{T^2}\geq0.}
$$

Conversion heat $-\mu R$ can have either sign in a nonuniform state. Its combination with the composition entropy change produces the nonnegative term $M\mathcal A^2/T$. Thus pointwise cooling is compatible with the total entropy inequality.

### 7.3 Canonical limit and continuum positivity

Uniform composition follows the canonical gate exactly. Since $\mu=a\delta$ and $h'=r(c)\delta$,

$$
R=-\frac{(1+\varphi)\kappa}{a+bTr}(a+bTr)\delta
=-(1+\varphi)\kappa\delta.
$$

For nonuniform composition, the full affinity changes that law. A controlled local jet at $c=0.7$, $\nabla c=0$, $\Delta c=10$, $T=1$ gives entropy production $-0.0205097895013$ when the local canonical reaction is used without the gradient affinity, against $+0.105361635711$ for the selected reaction. This is a realizable pointwise jet and a sign control, separate from a complete trajectory.

Smooth continuum evolution preserves a strict initial composition interval enlarged only to include $c_*$. Write

$$
c_-=\min(\inf c_0,c_*),\qquad c_+=\max(\sup c_0,c_*).
$$

At a maximum above $c_*$, $\nabla c=0$, $\Delta c\leq0$ and $\mathcal A=a\delta-g\Delta c+bTh'\geq0$, giving $R\leq0$. At a minimum below $c_*$ the signs reverse. Hence $c_-\leq c(x,t)\leq c_+$ while a smooth solution exists with positive temperature.

A quantitative temperature bound closes the positivity argument. Let $H=\max_{[c_-,c_+]}|h'|$, which is finite for $0<c_-\leq c_+<1$. Completing the square gives

$$
\mu(\mu+bTh')=
\left(\mu+\frac{bTh'}2\right)^2-\frac{b^2T^2(h')^2}{4}.
$$

Since $M\leq(1+\varphi)\lambda/a$, the temperature minimum satisfies the comparison inequality $\dot T_{\min}\geq-KT_{\min}^2$, where

$$
K=\frac{(1+\varphi)\lambda b^2H^2}{4aC},
\qquad
\boxed{T_{\min}(t)\geq
\frac{T_{\min}(0)}{1+KT_{\min}(0)t}>0.}
$$

The maximum-principle and comparison argument apply jointly up to any finite smooth-solution time. The square completion and comparison ODE are independently checked in the reconciliation artifact. These continuum bounds provide no positivity theorem for Fourier collocation or explicit RK4, and they do not control all derivatives needed for global smoothness.

### 7.4 Fixed numerical evidence

The executed model is `computations/cassi_fluid_thermodynamics.py`, with CPU float64 Fourier collocation on the $2\pi$ periodic cube and classical RK4. Odd grids avoid Nyquist ambiguity. Velocity advection uses a skew advective/conservative form, and the capillary force is a tensor divergence. The Leray projection retains the zero mode. No floor, density renormalization, mean-force subtraction or post-step smoothing is applied.

The dimensionless coefficients are $\rho_m=\rho_{\rm ref}=a=1$, $\gamma=0.02$, $C=2$, $b=0.2$, $\eta=0.03$, $k_T=0.02$, $\lambda=0.4$. They are **N-class constitutive benchmark inputs**, without empirical calibration or additions to the 47-parameter inventory. The fixed schedule is `computations/cassi-fluid-thermodynamics-prereg.md`.

| Control | Model trajectories | Compared behavior |
|---|---:|---|
| Homogeneous conversion above and below $c_*$ | 6 | Independent canonical scalar ODE and conversion heat |
| Decaying shear | 4 | Exact velocity and spatially varying viscous heating |
| Pure conduction | 4 | Exact temperature decay |
| Uniform golden composition with constant velocity | 4 | Stationary control |
| Coupled three-dimensional flow | 6 | $N=9,15,21$, two timesteps, energy and entropy budgets |
| Capillary release from rest | 2 | Composition energy converted to kinetic energy |
| Galilean-boosted coupled flow | 1 | Translated unboosted solution |
| **Total** | **27** | **395 passing checks, including 12 symbolic identities** |

All controls run to dimensionless time $0.2$. A separate $N=9$ differentiation-matrix/DOP853 evolution agrees with the FFT fine-step endpoint to normalized error $2.05688118885\times10^{-15}$; its RHS discrepancy is $7.20452343617\times10^{-16}$. It uses independent differential operators, pressure projection, mobility evaluation and time integration. It is additional to the 27 model trajectories.

For the finest coupled run, $N=21$, $\Delta t=0.002$:

| Observable | Initial | Final |
|---|---:|---:|
| Mean kinetic energy | $0.005$ | $0.00482310351231332$ |
| Mean composition energy | $0.00134004569043944$ | $0.00117412762058234$ |
| Mean thermal energy | $2$ | $2.00034281455754$ |
| Mean total energy | $2.0063400456904392$ | $2.0063400456904392$ |
| Mean entropy | $-0.00270813248606629$ | $-0.00222868537790490$ |

The maximum recorded total-energy drift is $4.44089209850\times10^{-16}$, and the trapezoidal entropy-balance error has magnitude $5.62572826865\times10^{-11}$. Composition changes by up to $0.00723790081416$ and the generated vertical speed reaches $0.00192653759977$. Absolute entropy depends on its declared reference; its increase is the measured quantity.

With $\eta=k_T=\lambda=0$ and initial rest, the finest capillary control gains kinetic energy $9.02950778978\times10^{-10}$, with $|\Delta K+\Delta E_c|=2.16840434497\times10^{-19}$ and unchanged temperature. The signal exceeds the frozen $10^{-10}$ detection floor. The boosted endpoint has normalized discrepancy $4.52221248898\times10^{-10}$.

All 27 histories retain $0<c<1$, $T>0$, maximum recorded divergence $4.55814271844\times10^{-15}$ and maximum momentum-component drift $8.84230960057\times10^{-17}$. These are short-time, finite-grid measurements. Error at the roundoff floor supports no measured temporal order.

### 7.5 Evidence, reproduction and physical scope

The analytical peer reviews are retained only at the qualified scope in `runs/cassi_fluid_thermodynamics/analytical-review-scope.json`. That artifact identifies the recomputed identities and excludes unsupported dimensional, thermal-integrability, diffusion-rewrite, fixture and asymptotic claims.

The accepted receipt is `runs/cassi_fluid_thermodynamics/verification.json`, schema `cassi.fluid.thermodynamics.verification.v1`. Its adjacent input manifest, six raw source snapshots and `verification.trajectories.npz` retain the executed inputs, initial/final fields, the independent reference endpoint and all 2,127 model-history rows. The array archive SHA-256 is `14c889a2237d13cd53247c4736b5f6cd9c98ab646b0fc7a77774983aa61f4485`.

Independent reconciliation imports neither model nor verifier. It validates all six working/manifest/snapshot identities and the archive hash and keys, reconstructs 54 endpoint records with maximum absolute observable discrepancy $2.08166817117\times10^{-17}$, and checks the recorded energy sums and entropy-production integrals. Its result and the continuum positivity qualifications are in `runs/cassi_fluid_thermodynamics/reconciliation.json`. The separate CLI smoke endpoint is byte-value identical to the finest coupled endpoint and is retained in `runs/cassi_fluid_thermodynamics/cli-smoke.npz`. Raw hashes identify frozen execution bytes; historical validation uses those bytes even when Git transport changes line endings.

From the CassiTheory directory:

```text
python computations/cassi_fluid_thermodynamics.py --n 21 --dt 0.002 --time 0.2
python computations/verify_cassi_fluid_thermodynamics.py --output runs/cassi_fluid_thermodynamics/reproduction/verification.json
```

The verifier refuses existing output, manifest, snapshot and archive paths. The measured classification is **SUPPORTS** for the selected momentum/energy/entropy closure. Physical-fluid replacement, microscopic viscosity and arbitrary-data global regularity remain **UNESTABLISHED**. The native-force result in §§4–6 is unchanged: this model implements a separate variational internal stress and leaves the native density/Poisson solver untouched. Material calibration and a derivation of its rotational and irreversible hydrodynamic assumptions remain the physical correspondence problem.

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
- `computations/cassi-fluid-thermodynamics-prereg.md`—selected constitutive equations, fixed thermal controls and evidence policy.
- `computations/cassi_fluid_thermodynamics.py`—reacting capillary/thermal evolution and CLI.
- `computations/verify_cassi_fluid_thermodynamics.py`—symbolic budgets, 27 model trajectories and independent differentiation-matrix reference.
- G. Planas, [On a non-isothermal incompressible Navier–Stokes–Allen–Cahn system](https://doi.org/10.1007/s00605-021-01564-2)—related model class; the selected closure retains its own assumptions and proof scope.
