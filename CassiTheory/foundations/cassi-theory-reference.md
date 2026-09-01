# The Cassi Framework

## Status: Reference—August 2026

## Abstract

This document compacts the Cassi framework into a single reference: the two-fluid postulate and governing PDEs, the dimensionful cascade and its suppression law, the unified action, and the quantum, particle, gravity, cosmological, turbulence, geometric, and consciousness consequences. Each section condenses a dedicated derivation paper cited inline; dimensionless entries are expressed as $\varphi$-powers with individual Derived, Conditional, Asserted, Calibrated, or Mapped status, and the three external dimensionful constants are $c$, $\hbar$, $G$.

## 1. The Postulate

$$\boxed{\varphi = \frac{1 + \sqrt{5}}{2} \approx 1.618033989}$$

is the universal scale-separation constant. $\varphi$ has continued fraction $[1;1,1,1,\ldots]$, making it the most irrational number—maximally resistant to rational approximation. This arithmetic property motivates a **Hypothesized** de-resonance interpretation, but leaves physical coupling dynamics and multiscale survival unspecified. In the canonical PDE, $\varphi$ is a declared conversion target, and convergence toward that target follows from the stated rank-one solver term and its assumptions. The discrete renormalization-group scale factor $\varphi$ in `foundations/phi-rg-formalism.md` is a separate **Hypothesized** construction.

---

## 2. The Two-Fluid System

### 2.1 Field Variables

The fundamental state is a pair of nonnegative density components:

$$
E_Y\ge0,\qquad E_I\ge0,\qquad \rho=E_Y+E_I,\qquad \pi=E_Y-E_I.
$$

$E_Y$ and $E_I$ are conventionally labeled Yang and Yin. A **Hypothesized**
phenomenological mapping may call them expansive/symmetry-breaking and
contractive/symmetry-restoring; the canonical equations treat both components
as neutral densities.

When component amplitudes are useful, introduce the exact positive-root
coordinate lift

$$
\Psi^{(+)}
=\begin{pmatrix}\Psi_0^{(+)}\\ \Psi_1^{(+)}\end{pmatrix}
=\begin{pmatrix}\sqrt{E_Y}\\ \sqrt{E_I}\end{pmatrix}
\in\mathbb{R}_{\ge0}^{2}.
$$

The lift is an exact coordinate representation of the density state. Compact
phase dynamics and branch-sign interpretations require optional signed or
complex extensions and remain **Hypothesized**. For $\rho>0$, the amplitude-plane
phase diagnostic, density-plane angle, and Stokes double angle are distinct:

$$
\theta_\Psi=\operatorname{atan2}(\Psi_1^{(+)},\Psi_0^{(+)}),\qquad
\theta_d=\operatorname{atan2}(E_I,E_Y),
$$

$$
\Theta_S=\operatorname{atan2}(2\Psi_0^{(+)}\Psi_1^{(+)},E_Y-E_I)
=2\theta_\Psi\pmod{2\pi}.
$$

The foundational spatial phase-current diagnostic of this lift is

$$
\mathbf{J}_\Psi=\Psi_0^{(+)}\nabla\Psi_1^{(+)}
-\Psi_1^{(+)}\nabla\Psi_0^{(+)}
=\rho\,\nabla\theta_\Psi.
$$

The positive-root density-lattice diagnostic is

$$
\mathbf{J}_d=E_Y\nabla E_I-E_I\nabla E_Y
=(E_Y^2+E_I^2)\nabla\theta_d
=2\sqrt{E_YE_I}\,\mathbf{J}_\Psi.
$$

The two diagnostics have different units: $\mathbf{J}_\Psi$ has
density/length units, while $\mathbf{J}_d$ has density$^2$/length units. A
named spatial projection, such as
$J_{\Psi,\parallel}=\hat{\mathbf t}\cdot\mathbf{J}_\Psi$ for a specified unit
direction $\hat{\mathbf t}$, records the chosen positive direction. Physical
current and inter-rung transport interpretations require a separate
constitutive map and remain **Hypothesized**.
### 2.2 Governing PDE


In the energy-density form used by the solvers, with the canonical densities
$E_Y$ and $E_I$, the governing equations are

$$\partial_t E_Y = -(\mathbf{u}\cdot\nabla)E_Y + D\nabla^2 E_Y - \lambda(1-q)(E_Y - \varphi E_I)$$

$$\partial_t E_I = -(\mathbf{u}\cdot\nabla)E_I + D\nabla^2 E_I + \lambda(1-q)(E_Y - \varphi E_I)$$

$\mathbf{u}$ is the shared velocity field. The solver family exposes $D$ as
scalar density diffusion and $\nu$ as velocity viscosity; $\nu$ acts in the
velocity equation, while $D\nabla^2 E_{Y/I}$ is the scalar density diffusion
shown above.
The framework declares $\lambda=0.1$ as the **C-class solver
normalization/timescale convention**. The `TwoFluid3DGPU` constructor
defaults to $\lambda=0.02$; $\lambda=0.1$ is used by that implementation
only when explicitly passed for a named C-class experiment. The relation
$\lambda=1/(2w)$ at $w=5$ is a **Hypothesized** Wu Xing cycle linkage, not a
$\varphi$-derived rate or a determination of its units.
$q$ is the Qi coherence (§2.4), and the gate factor $(1-q)$ is the openness
(§2.5). The displayed gated density pair is the selected canonical/theory
form. The implementation in `two-fluid/cassi_two_fluid_3d_gpu.py` supports the
displayed gated pair through the `ExpandingTwoFluid3DGPU` class only when
`qi_gate=True`; the base `TwoFluid3DGPU` `rhs` method uses the ungated
$-\lambda\varepsilon$ conversion, and the expanding solver defaults to
`qi_gate=False`.
Implementation receipts therefore require the mode parameters
`lambda`, `qi_gate`, `gate_model`, and `qi_memory` to be recorded alongside
any q-gated result.
An optional **Hypothesized** gravity/information-potential closure couples
$\Phi$ to the velocity equation; the resulting $\mathbf{u}$ advects both
density channels. The ungated amplitude form of the conversion appears only
as the $\varphi$-attractor potential of the action (§2.3, §4.1).
Writing $\kappa=\lambda(1-q)$, the conversion-only matrix is

$$
\partial_t
\begin{pmatrix}E_Y\\E_I\end{pmatrix}_{\!\mathrm{conv}}
=\kappa
\begin{pmatrix}-1&\varphi\\1&-\varphi\end{pmatrix}
\begin{pmatrix}E_Y\\E_I\end{pmatrix}.
$$

This rank-one relaxation has eigenvalues $0$ and $-\kappa(1+\varphi)=-\lambda(1-q)(1+\varphi)$. It conserves $\rho=E_Y+E_I$ while generally changing $E_Y^2+E_I^2$, so the canonical conversion is not a norm-preserving $SO(2)$ generator.

### 2.3 $\varphi$-Attractor

$$V_{\text{attr}} = \frac{\lambda}{2}(E_Y-\varphi E_I)^2$$

Fixed point: $E_Y=\varphi E_I$. In the positive-root lift,
$\Psi_0^{(+)}:\Psi_1^{(+)}=\sqrt{\varphi}:1$. At equilibrium:

$$\frac{\pi}{\rho}=\frac{\varphi-1}{\varphi+1}=\varphi^{-3}$$

Under local conversion-only dynamics, the ratio $r=E_Y/E_I$ evolves monotonically toward $\varphi$; advection, diffusion, and optional closures can add spatial dynamics.

### 2.4 Qi Coherence

$$\varepsilon=E_Y-\varphi E_I,\qquad \rho=E_Y+E_I,\qquad q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2}$$
For $\rho>0$, define $s\equiv\pi/\rho\in[-1,1]$. Then

$$
\frac{\varepsilon}{\rho}
=\frac{\varphi^2s-\varphi^{-1}}{2},
\qquad
q(\rho,s)
=\left[
1+\left(\frac{\varphi^2s-\varphi^{-1}}{2}\right)^2
+\frac{\varphi^{-2}}{\rho^2}
\right]^{-1}.
$$

The canonical $q$ therefore depends on both total density and composition. At
$s=\varphi^{-3}$, $q=\rho^2/(\rho^2+\varphi^{-2})$, approaching $0$ as
$\rho\to0$ and $1$ only as $\rho\to\infty$; $q$ is not an independent knob
at fixed finite $(\rho,s)$. In physical energy-density variables, an external
reference density $\rho_*$ gives

$$
q=\frac{\rho_{\mathrm{phys}}^2}
{\rho_{\mathrm{phys}}^2+\varphi^{-2}\rho_*^2+\varepsilon_{\mathrm{phys}}^2},
\qquad \rho_* \text{ external}.
$$

At fixed density, $\varepsilon\to0$ approaches the finite-density equilibrium value $q_{\mathrm{eq}}(\rho)=\rho^2/(\rho^2+\varphi^{-2})<1$. The limit $q\to1$ additionally requires $\rho\gg\varphi^{-1}$. At the fixed point ($\varepsilon=0$; the solver's reference state $E_Y=1$, $E_I=\varphi^{-1}$ gives $\rho=\varphi$), $q_{\mathrm{eq}}=\varphi^{2}/(\varphi^2+\varphi^{-2})\approx0.873$, and the gate openness $(1-q_{\mathrm{eq}})=\varphi^{-2}/(\varphi^2+\varphi^{-2})=\varphi^{-2}/3\approx0.127$.
**Optional positive-root lift bookkeeping.** For $\rho>0$, define
$\mathbf{Q}^{(+)}=(\rho,\mathbf{J}_\Psi^{(+)})$, where

$$
\mathbf{J}_\Psi^{(+)}
=\Psi_0^{(+)}\nabla\Psi_1^{(+)}
-\Psi_1^{(+)}\nabla\Psi_0^{(+)}
=\rho\nabla\theta_\Psi.
$$

This is an exact coordinate/diagnostic lift of the canonical two-density
state, whose independent variables remain $(E_Y,E_I)$ with derived scalar
$q$; it is not an additional field or canonical compact-current pair. For a
specified spatial direction $\hat{\mathbf t}$,
$J_{\Psi,\parallel}^{(+)}=\hat{\mathbf t}\cdot\mathbf{J}_\Psi^{(+)}$ is the
corresponding projection, with sign defined by $\hat{\mathbf t}$. The
density-lattice diagnostic $\mathbf{J}_d$ has different units, as stated in
§2.1. Physical-current and inter-rung-transport interpretations require a
separate constitutive map and remain **Hypothesized**.

**Optional temporal coherence (IIR memory).** When the default-off `qi_memory` closure is enabled, $\bar{\varepsilon}^2(t) = (1-\tau)\,\bar{\varepsilon}^2(t-\Delta t) + \tau\,\varepsilon^2(t)$ replaces the instantaneous deviation in the diagnostic, with $\tau=\varphi^{-1}$ as a solver coefficient convention. The memory carries a history of the field state and can smooth $\varepsilon^2$; neither the closure nor this coefficient is a canonical physical cycle.

**Active q-form inventory.** The coherence $q$ has three active forms:

In the implementation references below, “solver gate” means the optional
`ExpandingTwoFluid3DGPU(qi_gate=True)` path in
`two-fluid/cassi_two_fluid_3d_gpu.py`; the base `TwoFluid3DGPU` `rhs` method
and the expanding solver's `qi_gate=False` default use ungated conversion.
1. **Canonical (this section):** $q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$, numerator the field power $\rho^2$. Used by `cassi-first-principles.md` §2.1, `wa-pentagon-gate.md` §1, `gravity/three-body-analytical.md`, and the two-fluid solver's single gate ($M_{qi} = (E_Y+E_I)^2 = \rho^2$, $\varepsilon^2 = (E_Y-\varphi E_I)^2$; `two-fluid/cassi_two_fluid_3d_gpu.py`, `two-fluid/run_rung_offset_probe.py`, `two-fluid/run_sigma8_pipeline.py`). At $\varepsilon=0$, $q_{\mathrm{eq}}(\rho)=\rho^2/(\rho^2+\varphi^{-2})$. Under the solver's $\rho^2=\varphi^2$ normalization, $q_{\mathrm{eq}}\approx0.873$ and the gate closure is $1-q_{\mathrm{eq}}=\varphi^{-2}/(\varphi^2+\varphi^{-2})\approx0.127$ (`computations/ns_gate_correction.py`); a separate normalization $\rho^2=\varphi^{-6}$ gives $q_{\mathrm{eq}}\approx0.127$. The large-density limit $\rho^2\gg\varphi^{-2}$ gives $q\to1$.
2. **Per-rung specialization:** $q_i = 1 - \varphi^{-i-\delta}$, $\delta = 3$ (`cascade-suppression-formula.md` §1; `proton-coherence-budget.md`; `gravity/quantum-gravity.md` §2.1; `microcascade-mirror.md`; the coherence-budget consumers). Per-rung dephasing $1-q_i = \varphi^{-i-\delta}$, step $1-q_{i+1} = \varphi^{-1}(1-q_i)$. Not pointwise equal to form (1): under the separate $\rho^2=\varphi^{-6}$ normalization, residuals $|q_i-q_{\mathrm{eq}}|$ are $0.64$–$0.85$ over $i=0$–$5$; under the reference/solver $\rho^2=\varphi^2$ normalization, they are $0.019$–$0.109$. The profiles cross at $i^*=\log_\varphi(1/(1-q_{\mathrm{eq}}))-3\approx-2.7$ for the separate normalization and $i^*\approx+1.3$ for the solver normalization. The two are tied by the $\delta=3$ calibration $1-q_0=\varphi^{-\delta}=(\pi/\rho)_{\mathrm{eq}}$ (`gravity/quantum-gravity.md` §2.1), not by an identity; the profile's $i$-dependence is **Hypothesized** (`proton-coherence-budget.md` §8).
3. **Equilibrium simplification ("Qi quality"):** $q = M/(M + \varphi^{-2})$ with $M \equiv \rho^2$ the field power (`unified-lagrangian.md` §1.5/§3.2). Form (1) at $\varepsilon^2 = 0$: identical at the fixed point (residual $<10^{-15}$); the omitted $\varepsilon^2$ is the only discrepancy away from equilibrium. `two-fluid/cassi_bridge_v2.py` `qi_coherence` is form (1) with $\varepsilon^2$ replaced by the temporal-memory deviation $(\rho-\rho_{\text{mem}})^2$ when its optional memory path is enabled; that path is default-off and uses a solver convention rather than a derived physical cycle (cf. the $\bar\varepsilon^2$ IIR memory above).

Distinct-naming consumers (not the coherence $q$): `experiments/phi_attractor_paths/path8_phi_enhanced_rotation.py` uses a density-only halo $q = 1/(1+(\rho/\rho_{\text{ref}})^2)$ (inverted density dependence; documented halo-scale approximation, not the canonical form); `experiments/sparc_qi/sparc_qi_analysis_v9.py` uses $q$ as a halo mass fraction; `speculations/dark-matter-as-qi-coherence.md` and `consciousness/chakras-as-cascade-bubbles.md` use the spatial envelope $q(\mathbf{x}) = (1+B(\mathbf{x}))/2$; `standard-model/sm-from-phi.md` §3.1 uses a distinct $Q = |\Psi|^2|\varepsilon|^2$.
### 2.5 Qi Gate

$$\partial_t E_Y \supset -\lambda(1-q)(E_Y - \varphi E_I),\qquad \partial_t E_I \supset +\lambda(1-q)(E_Y - \varphi E_I)$$
The pair is equal and opposite ($\partial_t E_Y=-\partial_t E_I$), so total
density is conserved exactly in the selected canonical/theory form. In code,
the base solver's `rhs` method in `two-fluid/cassi_two_fluid_3d_gpu.py` is
ungated, and `ExpandingTwoFluid3DGPU` defaults to `qi_gate=False`; the
q-gated rank-one mode is implemented only when `qi_gate=True`, with
`gate_model` and `qi_memory` also affecting the receipt.

The gate *openness* is $(1-q)$: $q\to0$ means the gate is **open**—conversion runs hard and the region churns. At finite density, alignment at $\varepsilon=0$ reaches $q_{\mathrm{eq}}(\rho)$; $q\to1$ additionally requires $\rho\gg\varphi^{-1}$, and the gate is **closed** in that high-density limit—the system rests at $\varphi$-balance. (Sign PDE-tested 2026-07-31 in `consciousness/trauma-as-frozen-gate.md` §10.4.) The gate openness $(1-q)$ supplies the displayed conversion factor. The single-channel $g(q)$ shape used by some applications is an **Asserted input**; it is not derived from the $\varphi$-power structure, and any physical closure using it remains **Hypothesized**.

### 2.6 Density-Plane Relaxation and Conversion-Flow Time

The canonical conversion is a rank-one relaxation in the density variables, not an $SO(2)$ generator. With $\kappa=\lambda(1-q)$, its conversion-only matrix has eigenvalues $0$ and $-\kappa(1+\varphi)=-\lambda(1-q)(1+\varphi)$. It conserves $\rho=E_Y+E_I$ while generally changing $E_Y^2+E_I^2$.

**Conversion-flow time (exact).** The inter-fluid transfer defines $\chi_F$;
for $\lambda>0$, division by the rate supplies $\tau_F$:

$$
d\chi_F
:=\frac{dE_I|_{\mathrm{conv}}}{\varepsilon}
=-\frac{d\varepsilon}{(1+\varphi)\varepsilon}
=\lambda(1-q)\,dt,
$$

so resolved nonzero endpoints on one conversion branch give

$$
\boxed{
\Delta\chi_F
=-\frac{1}{1+\varphi}
\ln\left|\frac{\varepsilon_1}{\varepsilon_0}\right|,
\qquad
\Delta\tau_F:=\frac{\Delta\chi_F}{\lambda}
=\int(1-q)\,dt
}.
$$

$\tau_F$ is an openness-weighted conversion age. It equals coordinate elapsed
time only for $q=0$ throughout the interval; a memory-bearing gate requires
its path history to reconstruct the coordinate duration.

For two regions under the same conversion law,
$d\tau_F(x)/d\tau_F(x_0)=(1-q(x))/(1-q(x_0))$. This relative
conversion-clock identity is **Derived conditional**. Its promotion to a
universal proper-time lapse remains **Hypothesized**. Transport and source
increments require separate accounting; exact equilibrium contains no
readable conversion tick (`foundations/cassi-first-principles.md` §2.6).

**Candidate physical time.** Let $x_\star$ be a reference worldline with
$q_\star<1$. The parameter-free relational candidate is

$$
\boxed{
\frac{d\tau_{\mathrm{phys}}(x)}{d\tau_\star}
=N_q(x\mid x_\star)
:=\frac{1-q(x)}{1-q_\star}
}.
$$

With an external open-gate normalization,
$d\tau_{\mathrm{phys}}=(1-q)dt=d\tau_F$. The $q_\star=0$ case is a
normalization limit; an active canonical conversion reference requires
$\varepsilon_\star\neq0$ and hence $q_\star>0$. The candidate assigns the
entire canonical factor $(1-q)$ to a common clock lapse, so
$d\varepsilon/d\tau_{\mathrm{phys}}
=-(1+\varphi)\lambda\varepsilon$.
The conversion equation itself fixes only
$K(q)N(q)=1-q$; gated kinetics with $K=1-q,\ N=1$ produces the same
conversion trace. The common-lapse assignment is therefore Hypothesized and
is tested only by independently calibrated clock sectors. It defines a
worldline proper-time functional, not a global synchronization coordinate
(`foundations/unified-lagrangian.md` §1.7; CT-2 in
`predictions/falsifiable-predictions.md`).

For the density-plane angle

$$
\theta_d=\operatorname{atan2}(E_I,E_Y),
$$

the exact state-function rate is

$$\frac{d\theta_d}{dt}=\lambda(1-q)\,\frac{\rho\,\varepsilon}{E_Y^2+E_I^2}$$

(`foundations/cassi-first-principles.md` §2.6). The rate vanishes exactly at the $\varphi$-line ($\varepsilon=0$) and is gated by the openness $(1-q)$. Positive $\varepsilon$ gives positive $\theta_d$ drift; calling that direction toward the Yin-named axis uses the density-plane coordinate convention and does not assert a universal spatial transport direction, while negative $\varepsilon$ gives the reverse. Solver-measured: four homogeneous arms ($\lambda=0.05$, $t=4$) match the state-function rate to per-checkpoint relative error $\le2.2\times10^{-3}$ with 100% sign agreement, and the equilibrium arm reads $q_{\mathrm{eq}}\approx0.873$ (4/4 PASS; `two-fluid/run_winding_rate_probe.py`).

**Density-plane relaxation (exact).** Since $d\varepsilon/dt=-\lambda(1+\varphi)(1-q)\varepsilon$, the conversion rate and the gate cancel in $d\theta_d/d\varepsilon$; with $\rho$ conserved, $\theta_d$ is a function of $\varepsilon$ alone:

$$\theta_d=\operatorname{atan}\!\left(\frac{\rho-\varepsilon}{\rho\varphi+\varepsilon}\right).$$

The total density-plane drift accumulated while a state relaxes from $\varepsilon_0$ to equilibrium is

$$\boxed{\Delta\theta_d=\operatorname{atan}\!\left(\frac{1}{\varphi}\right)-\operatorname{atan}\!\left(\frac{\rho-\varepsilon_0}{\rho\varphi+\varepsilon_0}\right)}$$

independent of $\lambda$ and of the gate shape. Its extremes are the Yang limit $\varepsilon_0\to\rho$ ($\Delta\theta_d\to+\operatorname{atan}(\varphi^{-1})\approx0.554$ rad) and the Yin limit $\varepsilon_0\to-\rho\varphi$ ($\Delta\theta_d\to-\operatorname{atan}(\varphi)\approx-1.017$ rad). If one assigns a rung coordinate by the map $\delta n_{\mathrm{map}}\equiv\Delta\theta_d/(2\pi)$, the bound $|\delta n_{\mathrm{map}}|\le\operatorname{atan}(\varphi)/(2\pi)\approx0.162$ is **Hypothesized**, not a PDE-derived rung offset or physical rung flux. For small deviations the integral reduces to $\Delta\theta_d\approx\rho\varepsilon_0/[(1+\varphi)(E_Y^2+E_I^2)]$. Under that same Hypothesized map, a half-rung offset ($\delta n_{\mathrm{map}}=1/2$) would correspond to one full $\pi$-advance of the density-plane angle and exceed the relaxation bound by $\sim3.09\times$; the half-step class is the **parity** structure of `foundations/rung-offset-mechanism.md` §7, not accumulated relaxation.
### 2.7 Classical Limits

| Limit | Condition | Effective Theory |
|-------|-----------|-----------------|
| $q \to 0$ on the $\varphi$-line (dilute attractor: $\varepsilon = 0$, $\rho \to 0$; $q \to 0$ alone is $\rho \to 0$ or large $|\varepsilon|$, not equilibrium—at the reference fixed point $q = q_{\text{eq}} \approx 0.873$) | Optional Qi-gravity extension with $\pi/\rho = \varphi^{-3}$ and boost $\to 1$ | GR with $G_{\text{eff}} = \varphi^{-3}G \approx 0.236\,G$ |
| $q \to 0$ on the $\varphi$-line, $\hbar \to 0$ | Optional Qi-gravity/force closure plus the classical dilute limit | Newtonian gravity |
| Regulated CassiFI Hamiltonian with a self-adjoint configuration-space quantization | Positive CassiFI metric and an adiabatic centre-of-mass band | Linear Schrödinger equation with $G_{ij}=M\delta_{ij}$ |
| $\lambda \to 0$ | Optional pressure/force/source closure with conversion removed | Euler-Poisson system |
| $\xi \to 0$ | Optional Qi-gravity sector switched off | Standard GR |

---

## 3. The Cascade

### 3.1 Proposed Dimensionful Scale Coordinate

Conditional on the external constants and a selected one-step convention, the
framework uses the following proposed scale-coordinate relation:

$$\boxed{\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}},\qquad \ell_{\text{Pl}} = \sqrt{\hbar G/c^3}$$

The recurrence and external anchor define the coordinate algebra; they do not
by themselves derive physical dimensionality or force unification. Named
physical-scale correspondences are **Hypothesized** unless explicitly marked
**Mapped** from data. The table records the current coordinate labels. Today
$n \in [0, \approx 292]$ in this epoch-dependent convention, and
$n = \log_\varphi(\ell / \ell_{\text{Pl}})$.

| $n$ | Coordinate scale (m) | Current label |
|-----|----------------------|---------------|
| 0 | $1.6 \times 10^{-35}$ | Planck length |
| $\approx13.3$ | $\approx1.0 \times 10^{-32}$ | GUT scale ($M_{\text{GUT}}\approx2\times10^{16}$ GeV; **Mapped** coordinate label) |
| 20 | $2.4 \times 10^{-31}$ | Seesaw scale |
| 40 | $3.7 \times 10^{-27}$ | Inflationary scale |
| 80 | $8.0 \times 10^{-19}$ | Electroweak scale |
| 95 | $1.1 \times 10^{-15}$ | QCD confinement |
| 117 | $5.3 \times 10^{-11}$ | Bohr radius |
| 168 | $1.7$ | Human scale |
| 220 | $1.5 \times 10^{11}$ | Astronomical Unit |
| 267 | $9.3 \times 10^{20}$ | Milky Way diameter |
| 284 | $3.6 \times 10^{24}$ | Yin wake of 285 |
| 285 | $5.9 \times 10^{24}$ | Cassi bubble |
| 292 | $1.7 \times 10^{26}$ | Horizon rung today (ℓ₂₉₂ = 5.5 Gpc label; R_H = 4.44 Gpc = 14.5 Glyr) |

### 3.2 Cascade Suppression

Within the proposed cascade-coordinate model, a quantity assigned to coordinate
rung $m$ and evaluated at coordinate rung $n$ has modeled signal attenuation
over the source-to-target span $N=n-m$:

$$\text{Signal:}\quad \mathcal{D}_{m \to n} = \varphi^{-N}$$

For an integer count $N\in\mathbb{Z}_{\ge0}$, define the indexed coherence
product

$$
S_N\equiv\prod_{i=0}^{N-1}(1-q_i),\qquad S_0=1.
$$

With the conditional per-rung profile $1-q_i=\varphi^{-i-\delta}$,

$$
S_N=\varphi^{-\sum_{i=0}^{N-1}(i+\delta)}
    =\varphi^{-N(N-1)/2-\delta N}.
$$

The canonical coherence endpoint convention labels the last supporting rung
$N\in\mathbb{Z}_{\ge0}$, so it includes the endpoint factor:

$$
\text{Coherence:}\quad
\mathcal{D}_{0\to N}
=\prod_{i=0}^{N}(1-q_i)
=\varphi^{-N(N+1)/2-\delta(N+1)}.
$$

For a constant local coherence $q_i\equiv q$ supplied to the count product,
$S_N=(1-q)^N$ and the endpoint convention consequently gives
$\mathcal{D}_{0\to N}=(1-q)^{N+1}$. The declared uniform signal input
$d_i^{\mathrm{signal}}\equiv\varphi^{-1}$ gives
$\prod_{i=m}^{n-1}d_i^{\mathrm{signal}}=\varphi^{-(n-m)}=\varphi^{-N}$.
These are algebraic identities conditional on their stated per-rung inputs;
the physical signal-map interpretation remains **Hypothesized**.

For the fractional mapped endpoint $N_p=91.46$, no indexed product is taken.
The closed quadratic exponent is continued by the explicit coordinate
interpolation

$$
\mathcal{E}_{\mathrm{cont}}(N_p,\delta)
=N_p(N_p+1)/2+\delta(N_p+1),\qquad
\mathcal{D}^{\mathrm{cont}}_{0\to N_p}
=\varphi^{-\mathcal{E}_{\mathrm{cont}}(N_p,\delta)}
=\varphi^{-4505.5758}\approx\varphi^{-4506}.
$$

The discrete product and finite sum are **Derived conditional** on the
profile $1-q_i=\varphi^{-i-\delta}$, with $\delta=3$ from
$\sigma=\ell_{\text{Pl}}/\varphi^3$; the real-coordinate continuation is a
**Mapped/Hypothesized** coordinate convention. Modeled signal attenuation is
linear in span $N$; coherence maintenance is quadratic in depth.

Applications of this coordinate model include hierarchy
($v_0/M_{\text{Pl}}\propto\varphi^{-80}$; see
`principles/v0-hierarchy-problem.md`), strong CP
($\bar{\theta}=\varphi^{-81.4}\times\pi\varphi^{-2}
=\pi\varphi^{-83.4}\approx1.2\times10^{-17}$), neutrino masses
($m_\nu\propto v_0\cdot\varphi^{-12}$), and proton lifetime (coherence:
$\varphi^{-4506}$).

$$\lambda=0.1\quad\text{(declared C-class solver normalization/timescale convention; the `TwoFluid3DGPU` constructor default is $\lambda=0.02$ and uses $0.1$ only when explicitly passed; the linkage }\lambda=1/(2w)\text{ at }w=5\text{ is Hypothesized)}$$

The cycle number $w=5$ is obtained conditionally from two constraints under the proposed cascade-coordinate signal map and its stipulated uniform phase-error/threshold assumptions:

1. **Cascade upper bound:** within that construction, Fibonacci cycles with $F_k \leq k$ hold for $k \in \{1,2,3,4,5\}$ and fail for $k \geq 6$ because the modeled accumulated phase error exceeds the modeled cascade signal.
2. **Geometry lower bound:** within the regular-polygon construction, $\varphi$ appears in polygon ratios only for $n \geq 5$ (diagonal/side $= 2\cos(\pi/5) = \varphi$).

The intersection is unique under those assumptions: $w=5$. Its interpretation as a physical Wu Xing channel count, cycle, or canonical PDE extension remains **Hypothesized**.

Consequences:

$$g = 1 - \varphi^{-5} \quad\text{(primordial gap)}$$

$$r_0 = \frac{\varphi^{-5}}{2 - \varphi^{-5}} \quad\text{(primordial ratio } E_Y/E_I\text{)}$$

$$\lambda=0.1\quad\text{(C-class solver normalization/timescale convention; the linkage }\lambda=1/(2w)\text{ at }w=5\text{ is Hypothesized)}$$

Dimensionless couplings are expressed as $\varphi$-powers, with individual status labels. The framework declares $\lambda=0.1$ as the **C-class solver normalization/timescale convention**; the `TwoFluid3DGPU` constructor defaults to $\lambda=0.02$ and uses $0.1$ only when explicitly passed. The relation $\lambda=1/(2w)$ at $w=5$ is a **Hypothesized** Wu Xing cycle linkage, not a $\varphi$-derived rate. Three external dimensionful constants ($c$, $\hbar$, $G$) set the unit system; $\ell_{\text{Pl}} = \sqrt{\hbar G/c^3}$ is the cascade's sole dimensionful anchor.

| Coefficient | Expression | Value | Meaning |
|------------|-----------|-------|---------|
| $K_{fw}$ | $\varphi^{-1}$ | $0.618$ | Water damps Fire |
| $K_{fm}$ | $\lambda\varphi^2$ | $0.262$ | Fire melts Metal |
| $K_{md}$ | $3\varphi^2$ | $7.85$ | Metal cuts Wood |
| $H_{\text{empty}}$ | $\lambda\varphi^{-2}/3$ |—| Irreducible cosmological baseline—the factor $1/3$ is **Derived conditional** on an assumed isotropic three-dimensional model ($d=3$); the $\lambda\varphi^{-2}$ factor inherits the **C-class** solver normalization/timescale convention, while any physical cosmological-rate interpretation is **Hypothesized** |
| $\kappa_s$ | $\kappa_{s,\mathrm{scale}}=\varphi^{-6}/v_0^2$ | $0.92$ TeV$^{-2}$ (formal $C=1$ candidate) | Coefficient-free arithmetic scale candidate at proposed rung $77=154/2=80-3$, **Derived conditional** on $\delta=3$; the optional projection is dimensionally incomplete and establishes no physical $\kappa_s$ or equilibration scale (`foundations/sector-coupling-derivation.md` §§1–3) |

---

## 4. The Unified Action (optional extension)

The canonical solver is the density-pair system described in §2; the displayed action is an optional amplitude-field/action extension. Its sector identifications and physical mappings are **Hypothesized**; algebraic identities are **Derived conditional** only after the stated ansätze and external conventions are selected.

$$S_{\text{Cassi}} = \int d^4x\sqrt{-g}\,(\mathcal{L}_{\text{TF}} + \mathcal{L}_{\text{D}} + \mathcal{L}_{\text{GR}} + \mathcal{L}_{\text{SM}} + \mathcal{L}_{\text{mix}})$$

Dimensionless couplings are expressed as $\varphi$-powers, with individual status labels. The canonical $\lambda=0.1$ is the **C-class solver normalization/timescale convention**; the relation $\lambda=1/(2w)$ at $w=5$ is a **Hypothesized** Wu Xing cycle linkage, not a $\varphi$-derived rate. Three external dimensionful constants ($c$, $\hbar$, $G$) set the unit system; $\ell_{\text{Pl}} = \sqrt{\hbar G/c^3}$ is the cascade's sole dimensionful anchor.

### 4.1 Two-Fluid Core $\mathcal{L}_{\text{TF}}$ (optional amplitude-field form)

The action's $\Psi_\alpha$ notation denotes an optional amplitude-field
representation; the canonical solver evolves the density pair $E_Y,E_I$ and
uses the positive-root lift for coordinate diagnostics. The scalar
bookkeeping action is

$$
\mathcal{L}_{\text{TF}} =
\frac{1}{2}(\partial_\mu\Psi_\alpha)(\partial^\mu\Psi_\alpha)
-\frac{\kappa_4}{2}(\nabla^2\Psi_\alpha)^2
-\frac{g}{4}|\Psi|^4
-\frac{\lambda}{2}(\Psi_0^2-\varphi\Psi_1^2)^2
+A_B B(x,t)\frac{1}{2}|\Psi|^2.
$$

Terms in this optional amplitude-field ansatz are kinetic, fourth-order
gradient, $\phi^4$, $\varphi$-attractor, and breath modulation
($\omega_I=\varphi^{-1}\omega_Y$; localized to each region's proposed
coordinate rung-clock—**Hypothesized**, 21). The coefficient $\kappa_4$ is
distinct from the canonical solver's velocity viscosity $\nu$.

The regulated quantum action in §5.1 acts on a wavefunctional over the full
CassiFI configuration space. Its derived quantum potential
$Q_G=-\hbar^2\Delta_GR/(2R)$ remains inside that configuration-space action.

### 4.2 Dirac Sector $\mathcal{L}_{\text{D}}$ (optional coupling extension)

This sector is an optional **Hypothesized** fermion-coupling extension. The canonical density pair supplies the $\Psi_\alpha$ coordinate lift; the fermion identification below is an additional ansatz.

$$\mathcal{L}_{\text{D}} = \bar\psi(i\gamma^\mu\partial_\mu - m)\psi - \frac{\varphi^{-1}}{2}(\bar\psi\psi)\cdot M + \bar\psi(\hat{P}_Y\Psi_0^2 + \hat{P}_I\Psi_1^2)\psi$$

For this ansatz, $\hat{P}_Y = (1+\gamma^5)/2$ and $\hat{P}_I = (1-\gamma^5)/2$ are algebraic chiral-projector definitions, while the mapping $\Psi_0^2 = \bar\psi\hat{P}_Y\psi$, $\Psi_1^2 = \bar\psi\hat{P}_I\psi$ is **Hypothesized** and conditional; the canonical density PDE supplies no such fermion mapping.

### 4.3 Gravity Sector $\mathcal{L}_{\text{GR}}$ (optional gravity extension)
This sector is an optional **Hypothesized** gravity extension. Its displayed
relations and fixed-point evaluations are **Derived conditional** on the ansatz
and selected normalization. The Einstein–Hilbert expression below is a formal
frozen-background or locally constant-$G_{\text{eff}}$ ansatz, not a complete
variable-coupling covariant action.

$$\mathcal{L}_{\text{GR}} = \frac{1}{16\pi G_{\text{eff}}}R\sqrt{-g} + \frac{1}{2}T_{\mu\nu}g^{\mu\nu}$$

$$\boxed{G_{\text{eff}} = G \cdot \frac{\pi}{\rho} \cdot (1 + (\varphi^{6}-1)q)},\qquad \xi = \varphi^6 = \varphi^5 + \varphi^4$$

The covariant coefficient $1/G_{\text{eff}}$ is undefined at $\pi=0$ and
changes sign on the Yin-dominant branch $\pi<0$. A restricted positive-
imbalance branch or a new regularized/sign constitutive map is required.
If $F\equiv1/G_{\text{eff}}$ varies in spacetime, metric variation of
$\int\sqrt{-g}\,F R$ adds
$(g_{\mu\nu}\Box-\nabla_\mu\nabla_\nu)F$ and any implicit metric-dependence
terms; a scalar-tensor completion or explicit exchange terms are required for
a variable coupling. The displayed Einstein equation with only
$G_{\text{eff}}T_{\mu\nu}$ and its Bianchi conservation is therefore not
derived here.

The optional Frenet–Serret interpretation reads $\xi=\varphi^6$ as 2 field
components times 3 frame vectors under an assumed three-dimensional
embedding; it is **Hypothesized** and does not derive $d=3$ or $\xi$ from the
canonical density conversion.

At the $\varphi$-fixed point ($\varepsilon=0$, $\pi/\rho=\varphi^{-3}$), the
reference state has $\rho=\varphi$ and
$q_{\mathrm{eq}}=\varphi^2/(\varphi^2+\varphi^{-2})=0.872677996$. Therefore
$G_{\text{eff}}\approx3.726779962\,G$. On the same fixed-composition line,
$q\to0$ as $\rho\to0$ and $G_{\text{eff}}\to\varphi^{-3}G$, while
$q\to1$ only as $\rho\to\infty$ and $G_{\text{eff}}\to\varphi^3G$. These are
branch limits, not global state-space bounds, because $q=q(\rho,s)$ varies
with total density and composition. For the unrestricted-composition
high-density expression
$q_\infty(s)=\left[1+\left((\varphi^2s-\varphi^{-1})/2\right)^2\right]^{-1}$,
$G_{\text{eff}}/G\to s[1+(\varphi^6-1)q_\infty(s)]$ has an interior peak
$\approx9.601$ at $s\approx0.8569$ on the physical interval $0\le s\le1$;
if $s>1$ is formally admitted, it is unbounded, so this value is not a
global ceiling. The $\alpha$-free bracket factor remains separately bounded
by $\varphi^6\approx17.94$ for $0\le q\le1$. The formal $\varphi^6$
endpoint ratio is therefore a bracket bound, not a universal
$G_{\text{eff}}$ or velocity ceiling $\varphi^3$.
The PPN expressions $\beta=1+\mathcal{O}(\xi q^2)$ and
$\gamma=1+\mathcal{O}(\xi q^2)$ remain **Derived conditional** on an
additional metric/sign closure; attractive Newtonian or GR behavior is not
supplied by the displayed constitutive law.

### 4.4 Gauge Sector $\mathcal{L}_{\text{SM}}$ (optional gauge/Higgs extension)
The following gauge-group, coupling, and Higgs identifications are an optional
**Hypothesized** physical extension. Trigonometric and mass identities are
**Derived conditional** on this ansatz and selected external gauge parameters;
the proposed GUT coordinate label is **Mapped** at $n\approx13.3$ for
$M_{\text{GUT}}\approx2\times10^{16}$ GeV.

Gauge group SU(3)$_C \times$ SU(2)$_L \times$ U(1)$_Y$. At the proposed
GUT-labeled coordinate ($n\approx13.3$):

$$\alpha_{\text{GUT}} = \frac{\varphi^{-3}}{4\pi}$$

Weinberg angle at tree level:

$$\boxed{\sin^2\theta_W = \frac{\varphi-1}{\varphi+1} = \varphi^{-3}}$$

Higgs doublet VEV at $\varphi$-equilibrium:

$$\langle\Psi\rangle = \frac{v_0}{\sqrt{\varphi+1}}\begin{pmatrix}\sqrt{\varphi} \\ 1\end{pmatrix}$$

$$m_W = \frac{g v_0}{2},\qquad m_Z = \frac{\sqrt{g^2 + g'^2}\,v_0}{2},\qquad \frac{m_W}{m_Z} = \sqrt{1-\varphi^{-3}}$$

Fermion mass hierarchy ($y_f = y_0 \cdot \varphi^{-n_f}$):

| Generation | $n_f$ | $m_f \propto$ |
|-----------|-------|---------------|
| 3 (top/bottom) | 1 | $\varphi^{-1}$ |
| 2 (charm/strange) | 2 | $\varphi^{-2}$ |
| 1 (up/down) | 3 | $\varphi^{-3}$ |

### 4.5 Mixing Terms $\mathcal{L}_{\text{mix}}$ (optional extension)
This mixing term is an optional **Hypothesized** extension of the action. Any matching of its displayed terms is **Derived conditional** on this ansatz, with no canonical density-PDE transport or fermion-mapping implication.

$$\mathcal{L}_{\text{mix}} = \frac{\xi q}{16\pi G}R\sqrt{-g} + \frac{\kappa_s}{2}\sum_{\pm}\left(\bar\psi\frac{1\pm\gamma^5}{2}\psi - \Psi_{0,1}^2\right)^2 + \left(|D_\mu\Psi|^2 - |\partial_\mu\Psi|^2\right)$$
The Dirac↔two-fluid bracket here is dimensionally incomplete: it subtracts a spinor density of dimension $[M]^3$ from a condensate square of dimension $[M]^2$. No physical $\kappa_s$ or equilibration scale follows without a sourced, ledgered normalization (`foundations/sector-coupling-derivation.md` §1).

---

## 5. Quantum Physics

### 5.1 Regulated Schrödinger Sector

The optional CassiFI quantum sector starts from a finite conservative
configuration $Q^A$ with positive metric $G_{AB}$:

$$
H_{\mathrm{FI}}
=\frac12P_AG^{AB}P_B+U_{\mathrm{FI}}(Q),
\qquad
\hat H_Q=-\frac{\hbar^2}{2}\Delta_G+U_{\mathrm{FI}}(Q).
$$

The normalized wavefunctional obeys

$$
i\hbar\partial_t\Psi[Q,t]=\hat H_Q\Psi[Q,t].
$$

For a centre-of-mass coordinate with $G_{ij}=M\delta_{ij}$, this reduces to

$$
i\hbar\partial_t\psi
=\left[-\frac{\hbar^2}{2M}\nabla^2+V\right]\psi,
\qquad
E=\frac{\hbar^2k^2}{2M},
\qquad
\lambda_{\mathrm{dB}}=\frac{h}{Mv}.
$$

The wavefunctional lives on the full field-configuration space and is
distinct from the positive-root density coordinate
$\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$. Its polar decomposition derives
$Q_G=-\hbar^2\Delta_GR/(2R)$ without a free $\varphi$ exponent. This sector is
**Derived conditional** on the quantum postulates and **Hypothesized** in its
CassiFI physical identification.
The frozen DQ1–DQ9 audit rejects promotion of the physical identification to
Derived. Reverse-Madelung linearization and tensor composition pass under
their declared quantum premises; the canonical lift, Fisher bridge, guidance
and equilibrium selection, physical-sector, interacting-continuum, and
discrimination gates fail (`foundations/quantum-measurement-derivation.md`
§8.1).

The GQ1–GQ7 geometric campaign `ADOPT`s a Hypothesized moment-map/Kähler
projection architecture. A normalized complex Yang/Yin pair places the
$\varphi$ attractor at Bloch latitude
$n_z=\varphi^{-3}=0.236067977500$. Equal projected moduli retain causally
different phases, and the finite $W$-metric complex configuration has
compatible Kähler geometry. The exact symmetry quotient,
microscopic-to-mesoscopic projection, cotangent reconstruction,
physical-sector realization, and Cassi-specific holonomy remain open
(`foundations/quantum-measurement-derivation.md` §8.3).

The QC1–QC9 finite-completion campaign `ADOPT`s a conservative carrier
birth-death-hopping process as **Hypothesized** microphysics and its
carrier-to-mesoscopic projection as **Derived conditional** mathematics. At a
finite regulator its generator is positivity preserving, conserves total
carrier number, projects to the canonical conversion-diffusion drift, and
fixes binomial conversion fluctuations plus the declared transport-noise
kernel. The QF1 complex-field density and carrier-projected density are
independent coordinates in the additive completion; a physical state map
between them remains Open (`foundations/quantum-measurement-derivation.md`
§8.4).

### 5.2 Spin

Spin is assigned through a **Hypothesized** geometric phase convention on a nested Fibonacci spiral, separate from canonical density-plane relaxation. Spiral polar equation:

$$\Theta(r) = \frac{2\pi}{\ln\varphi}\ln\left(\frac{r}{\ell_n}\right)$$

Here $\Theta$ is a geometric phase assigned to a single doublet component (one rung = $2\pi$); the spin convention uses the corresponding doublet phase assignment, $s=\Delta\Theta/4\pi=\Delta n/2$ with $\Delta n$ the rung span (one rung = $2\pi$ single-component geometric phase = $\pi$ assigned doublet phase; two rungs = one full assigned doublet phase cycle—`foundations/spin-fibonacci-spiral.md` §2.1). This fixed per-rung assignment is part of the **Hypothesized** geometric mapping. Quantized: $s\in\{0,\frac12,1,2\}$ (spans $\Delta n\in\{0,1,2,4\}$). No fundamental $s=\frac32$: $\Delta n=3=1+2$ decomposes into the fermion span plus one gauge cycle, so under the minimal-span principle it is composite, not a new fundamental (`foundations/spin-fibonacci-spiral.md` §2.4). Spin-statistics from $(-1)^{2s}$. The optional form-factor extension has log-periodicity $\Delta(\ln q)=\ln\varphi$.

### 5.3 Measurement and Born Frequencies

A regulated composite system uses
$\mathcal H_A\otimes\mathcal H_B$ and therefore supports generic
configuration-space entanglement. Measurement correlates a system state with
disjoint topological apparatus sectors $\Omega_k$. One actual Cassi field
configuration enters one sector, while the total wavefunctional remains
unitary. Conditioning on that realized apparatus configuration gives the
effective post-measurement state.

Record distinguishability is

$$
\gamma_{jk}=\langle A_kE_k|A_jE_j\rangle,
\qquad
\mathcal M_{jk}=1-|\gamma_{jk}|^2.
$$

A coherent phase grating may have $\mathcal M_{jk}\simeq0$ because it exports
no path record; amplification into orthogonal detector records gives
$\mathcal M_{jk}\simeq1$. Under the declared quantum-equilibrium condition,
$\rho_Q=|\Psi|^2$ is equivariant and is the unique normalized density local in
$|\Psi|^2$ that shares the guidance flow. Thus

$$
P(k)=\int_{\Omega_k}|\Psi(Q)|^2d\mu_G
=\langle\Psi|P_k|\Psi\rangle,
$$

which gives $P(k)=|c_k|^2$ for ideal disjoint records. No intrinsic
mass-triggered collapse term is present. The complete derivation is
`foundations/quantum-measurement-derivation.md`.

At finite regulator the carrier reservoir and an apparatus record also define
a completely positive trace-preserving instrument
$\{\mathcal I_k\}$ with
$\sum_k\mathcal I_k$ trace preserving. For the same preparation, controls,
Hamiltonian, and instrument as ordinary quantum mechanics, the regulated
CassiFI branch is operationally equivalent at every finite sequence of
measurements. Its present quantum result is therefore a conditional
construction and compatibility boundary, not a Cassi-specific departure.

---

## 6. Particle Physics

### 6.1 Gauge-Coupling Boundary

At the selected GUT boundary, $\alpha_{\text{GUT}}=\varphi^{-3}/(4\pi)$
is an **Asserted** boundary used to define the SU(3) normalization

$$
g_s^2\equiv4\pi\alpha_{\text{GUT}}.
$$

Separately, the electroweak relative normalization

$$
\left(\frac{g}{g'}\right)^2
=\frac{1-\varphi^{-3}}{\varphi^{-3}}
=2\varphi
$$

is an **Asserted** input. The current action supplies no mechanism tying
either electroweak coupling to $g_s$, and Standard Model running has no
common intersection. These are separate boundary assignments, not a derived
three-coupling unification.

### 6.2 Three Generations

Fibonacci recurrence $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$ partitions each cascade span into sub-rung channels: the decomposition has two terms (two predecessor channels; the recurrence's solution space is 2D, roots $\varphi$, $-1/\varphi$), and the propagation-channel postulate adds the direct rung:

$$N_{\text{gen}} = 2 + 1 = 3$$

(without the postulate the count would be 2; `foundations/three-generations.md` §2.3). No fourth generation. $\varphi$-power spacing from sub-channel widths.

### 6.3 Mass Ratios

Charged leptons: $m_\mu/m_e \approx \varphi^{11}$, $m_\tau/m_\mu \approx \varphi^{6}$.

Quarks: $m_t/v_0 \approx \varphi^{-1}$, $m_c/m_t \approx \varphi^{-2}$.

CKM: $\delta_{\text{CKM}} = \pi\varphi^{-2}$.

Corrections from off-diagonal Yukawa terms and RGE running.

### 6.4 Neutrino Masses

The proposed seesaw assignment places the neutrino mass at cascade step 20 in
the scale-coordinate convention. Overall mass scale:

$$m_\nu \approx v_0 \cdot \varphi^{-12}$$

Fibonacci offsets: $\Delta_1 = 1.00$, $\Delta_2 = 1.75$ rungs. The seesaw's Yukawa-squared structure doubles the exponent: $m_{\nu_{k+1}}/m_{\nu_k} = \varphi^{2\Delta_k}$. Mass-squared difference ratio:

$$\frac{\Delta m^2_{31}}{\Delta m^2_{21}} = \frac{\varphi^{11} - 1}{\varphi^{4} - 1}$$

PMNS angle relations are **Conditional coefficient-free candidates within the
selected conversion-Jacobian ansatz**:
- $\theta_{12} = \arctan(1/\varphi)$
- $\theta_{23} = 45^\circ$ (exact maximal)
- $\theta_{13} = \arctan(\varphi^{-4})$

Pinned spectrum: $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV. Normal ordering.

### 6.5 Strong CP

At the GUT-labeled phase coordinate ($n\approx13.3$),
$\delta_{\text{CP}} = \pi\varphi^{-2}$ (Mapped—ledger). Signal propagation
through $N \approx 81$ coordinate rungs (94.71 − 13.33):

$$\bar{\theta} \approx \varphi^{-81.4} \times \pi\varphi^{-2} = \pi\varphi^{-83.4} \approx 1.2\times10^{-17}$$

### 6.6 Proton stability candidates

The measured proton mass maps to

$$
\mathfrak s_p
=\log_\varphi\!\left(\frac{\hbar}{m_pc\,\ell_{\mathrm{Pl}}}\right)
=91.4616.
$$

The coherence-budget candidate uses the registered reporting coordinate
$N_p^{\mathrm{budget}}=91.46$ and the Hypothesized profile
$1-q_i=\varphi^{-i-\delta}$ with $\delta=3$. Continuing the closed exponent
gives

$$
\mathcal E(N_p^{\mathrm{budget}},3)
=\frac{N_p^{\mathrm{budget}}(N_p^{\mathrm{budget}}+1)}{2}
+3(N_p^{\mathrm{budget}}+1)
=4505.5758,
$$

$$
N_{\mathrm{max}}^{\mathrm{cont}}
=\varphi^{4505.5758}
\approx10^{941.8}\ \text{modeled cycles}.
$$

The product is Derived conditional arithmetic under the independent-step
failure model. The $10^{910}$-year conversion additionally assigns one
transition trial to every Compton cycle; no fluctuation law or matrix element
selects that map.

The distinct scale-circuit candidate has

$$
J_{Y,\mathfrak s}=+\mathcal J_Q,
\qquad
J_{I,\mathfrak s}=-\mathcal J_Q,
\qquad
J_{\mathfrak s}=0,
\qquad
\mathcal I_{\mathfrak s}=g_Q\mathcal J_Q.
$$

At uniform $E_Y/E_I=\varphi$,
$\mathcal J_{Q,m}=K_{\mathfrak s}\rho\Delta_m/
(\hbar\varphi^3\mathfrak s_p)$. Endpoint converters close the circuit, and the
relative current can source a mixed-curvature pinch. The endpoint fields,
scale tension, localized proton solution, particle quantum numbers, and
winding-changing rate remain Hypothesized/Open. Opposite winding sectors
$m$ and $-m$ provide a possible matter/antimatter branch label; their physical
identification and annihilation interaction remain unselected.

### 6.7 Quark Confinement

A saturated-gate flux tube is assigned to the proposed QCD-labeled coordinate
$n=95$: the conversion channel saturates between separated color charges
($q\to0$); the tube's energy is extensive, $E(r)=\mu r$ with
$\mu=\kappa(M_{\text{Pl}}/\varphi^{95})^2=\kappa\Lambda_{\text{QCD}}^2$,
$\kappa=2\pi$ conditional on the **Hypothesized** separate geometric
$2\pi$-per-rung phase convention, not on canonical density-plane drift
($\sigma_{\text{tube}}=0.1836$ GeV$^2$, +2.0% vs measured)—a constant
force, linear potential by extensivity (independent of the gate shape). Flux tube breaking probability $\approx\varphi^{-4506}$ under the stated rounded coherence convention. In the optional effective-channel reading, asymptotic freedom at $n\ll95$ is **Hypothesized** conditional on an application-supplied $g(q)$ closure with $g(q)\to0$; the canonical PDE supplies no physical $n\mapsto q$ map.

---

## 7. Gravity

### 7.1 $\sigma$-Regularization

Gravitational kernel: $1/\sqrt{|r|^2 + \sigma^2}$ with $\sigma = \ell_{\text{Pl}}/\varphi^3$. Large $r$: inverse-square. Small $r$:

$$F \propto -\frac{r}{3\sigma^3} \cdot (1 + (\varphi^{6}-1)q)$$

Eliminates singularities. The $\sigma$-regulator also enters the quantum gravity propagator (§7.2).

### 7.2 Black Holes and Quantum Gravity

$\sigma$-regularized harmonic cores. Exterior metric matches GR. The free propagator is UV-finite:

$$G(k^2) = \frac{e^{-k^2\sigma^2/2}}{k^2+i\epsilon}$$

The Gaussian regulator makes all loop diagrams finite—no renormalization needed. No trans-Planckian modes (dispersion $\omega \to M_{\text{Pl}}$ asymptotically). S-matrix unitary by construction. Coherence capacity $\mathcal{C} \sim M^2/M_{\text{Pl}}^2$ matches Bekenstein-Hawking entropy. No firewall: $\sigma$ caps all mode energies.

### 7.3 Three-Body Problem

Point-particle reduction of the two-fluid PDE gives:

$$\ddot{\mathbf{X}}_j = -G\,\alpha_j\,(1+(\varphi^{6}-1)q_j)\,\sum_{i\neq j} M_i\frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}$$

where $\alpha_j\equiv\pi_j/\rho_j=\Pi_j/M_j$ is the local fractional
imbalance, not the Yang fraction; the local Yang fraction is
$E_{Y,j}/\rho_j=(1+\alpha_j)/2$. At the $\varphi$-fixed point
($\alpha_j=\varphi^{-3}$, $\varepsilon_j=0$), each blob carries
$q_j=q_{\text{eq}}(\rho_j)=\rho_j^2/(\rho_j^2+\varphi^{-2})$. At the
reference density $\rho_j=\varphi$, this is
$q_j=0.872677996$ and
$G_{\text{eff},j}=3.726779962\,G$; the dilute fixed-composition limit
$\rho_j\to0$ gives $q_j\to0$ and
$G_{\text{eff},j}\to\varphi^{-3}G$. The displayed negative sign is a separate
attractive point-particle force convention. The canonical density PDE does not
supply that sign: its optional $+\pi\,\nabla\Phi$ branch is outward for
$\Phi=-GM/r$ and $\pi>0$, so an attractive Newtonian/GR interpretation
requires an additional **Hypothesized** sign/force closure. Off the fixed point,
masses evolve via conversion and $G_{\text{eff}}$ is body-dependent.

---

## 8. Cosmology

### 8.1 Dark Energy

From two-fluid conversion as $r(t) \to \varphi$:

$$w(a) = \frac{P_{\text{DE}}}{\rho_{\text{DE}}} = \frac{\dot{r}/r - 3H(1+r^{-1})}{3H(1+r^{-1})}$$

$$w_0 = -0.87,\qquad w_a = +0.012 \; (+ \xi = \varphi^6,\ \text{Yang-fraction form})$$

With the ratified conversion→expansion coupling (Hypothesized—August 2026,
zero free constants): the unstable B2 realization gives $w_a \approx -0.38$
($1.25\sigma$ from DESI—08 §C.6; $w_0 \approx -0.97$ at fixed $r_0$,
$3.6\sigma$); the term's **stable realization** (the C1 friction closure—
10/12) gives a pure-Λ DESI-window fit $(w_0, w_a) = (-1, 0)$ exactly—
4.17σ/2.61σ from DESI ($r_0$ re-tuning closed negatively).

### 8.2 Inflation

In the proposed scale-coordinate construction, the inflationary interval spans
coordinate steps 20–60. The Qi gate slow-roll drives $N_e=40$ e-folds. Gate
engagement at the proposed coordinate step $\sim60$ ($r=\varphi^{-1}$)
provides graceful exit.

$$n_s = 1 - \frac{2\varphi^{-1}}{N_e},\qquad r = \frac{12}{N_e^2} \approx 0.0075 \quad (N_e = 40)$$

($r$ at the Mapped e-fold window $N_e = 40$—ledger row 495; the $\varphi^{-12} \approx 0.003$ reading requires $N_e = \sqrt{12/0.003} \approx 63.2$, outside the ledgered window).

The $\varphi^{-1}$ correction in $n_s$ comes from the Qi gate's residual transparency at closure ($N_e^{\text{eff}} = N_e \cdot \varphi$).

**Trajectory status (2026-08-06, `computations/slow_roll_trajectory.py`):** the gate slow-roll trajectory does not reproduce these numbers at the CMB-exit anchor—$(n_s, r) = (0.813, 0.188)$ under 1 step = 1 e-fold, $(0.914, 0.060)$ with $N_e = 40$ literal; $N_e = 40$ is a start-threshold choice (Mapped—ledger §10); the two claimed numbers do not coexist on the trajectory, and the trajectory's $r$ is excluded by the BK18 bound.

### 8.3 Baryon Asymmetry

Three candidate ingredients: (1) a particle/antiparticle circuit interaction (§6.6), (2) the Wu Xing freeze-out gap $g = 1 - \varphi^{-5}$, and (3) cascade dilution through photon-producing conversion:

$$\eta \approx \varphi^{-44}$$

The exponent $-44$ is a **ledgered fit** (Fit-Status Ledger row 481,
Mapped). Current candidate spans remain unclosed: the pinch-minus-seed span is
$46.7$, the required exponent is $44.126$ (ledgered as the Mapped integer
exponent $44$), and the separate gate-threshold span is $26.7$. No rate law
or physical coordinate map selects an endpoint connecting these values, so the
construction does not close. The mechanism (Wu Xing gap + candidate circuit
interaction + cascade dilution) is **Hypothesized**, with reconnection dynamics
and event rate open; see `foundations/baryon-asymmetry.md` for the full status.

### 8.4 Dark Matter

**Optional Hypothesized dark-matter sector.** A high-$q$ two-fluid
condensate is modeled as dark (no EM interaction), gravitationally active
($G_{\text{eff}}$ enhanced), stable ($\varphi$-attractor), and collisionless.
Conditional on the Weinberg-angle identification, this sector gives

$$
\frac{\Omega_{\text{DM}}}{\Omega_b}=\varphi^3=4.2361.
$$

The condensate base is **Hypothesized** conditional on that identification;
the component budget excludes a $+1$ baryon-capture term because captured
baryons already belong to the observed $\Omega_b$ denominator. The observed
ratio is $5.39$, leaving a 21% open tension.
### 8.5 Structure Formation

The canonical real-density PDE supplies density variables; the
phase/interference interpretation below is an optional **Hypothesized**
extension. **Wake-wave.** Under this extension, Yang-Yin interference at
$\varphi$-spaced intervals is represented by

$$
\Delta(\ln k)=\ln\varphi.
$$
**Flatness.** $\varphi$-attractor drives $\Omega_{\text{total}} \to 1$.

**Horizon.** In the proposed temporal-emergence rule, scale-coordinate labels
synchronize when $r(t)$ crosses a cascade step; this **Hypothesized** rule does
not assert physical activation of distinct dimensions.

**CMB anomalies.** Adjacent Cassi bubbles at $\varphi$-spaced intervals imprint a preferred axis at $\ell < 5$. Dipole–quadrupole alignment $12.2^\circ$, from bubble triaxial geometry. Scale-dependent (fades for $\ell > 5$).

**$\sigma_8$.** Qi gravity weakens $G_{\text{eff}}$ in low-density voids, reducing large-scale clustering.

### 8.6 Hubble Tension

$w(a)$ evolution shifts $H_0$ relative to the constant-$\Lambda$ extrapolation.
The full $H(z)$ fit was performed 2026-08-06
(`computations/hz_full_fit.py`) but leaves registry C3/T4 unresolved. The
pipeline CMB-inferred value is $H_0\approx65.8$ km/s/Mpc versus the local
$73.0$ km/s/Mpc; no resolved value is claimed.

---

## 9. Turbulence

An optional **Hypothesized** turbulence closure supplies a physical velocity/Navier-Stokes inertial-range interpretation for the shared advection field. Conditional on that closure, a Kolmogorov $-5/3$ spectrum could emerge when conversion is slow compared to eddy turnover; the canonical density PDE alone supplies shared advection but no physical Navier-Stokes closure. Cassi contributions:

**$\varphi$-break scale (conditional).** Under the same optional closure, the wavenumber where conversion and eddy turnover timescales cross:

$$k_\varphi = \varphi^3\sqrt{\lambda^3/\varepsilon_{\text{flux}}}$$

**Scale-dependent gravity (conditional).** Under the same optional closure and supplied $q(k)$ map, $G_{\text{eff}}(k)$ varies by factor $\varphi^6$ across the break: $\varphi^{-3}G$ in the inertial range ($q\to0$ on the $\varphi$-line), $\varphi^{3}G$ in the Qi-active range ($q\to1$, from $\varphi^{-3}(1+(\varphi^{6}-1))=\varphi^3$).

**$\varepsilon$-spectrum (conditional).** Under the same optional closure, $E_\varepsilon(k)\propto k^{-5/3}\cdot f(k/k_\varphi)$ is a Hypothesized inertial-range mapping for the deviation from $\varphi$-equilibrium.

**Qi-quality spectrum (conditional).** Under the same optional closure, $1-q(k)\propto k^{-5/3}$ is a Hypothesized inertial-range mapping.

---

## 10. Geometry and Dimensionality

### 10.1 Fibonacci Spiral

The ratio string $r(t)$ is paired with a separate geometric phase coordinate while advancing along the cascade:

$$\Theta(r)=\frac{2\pi}{\ln\varphi}\ln\left(\frac{r}{\ell_n}\right)$$

An optional geometric convention assigns one full turn per cascade rung in
$\Theta$. If adopted, $\Theta$ advances $2\pi$ per rung and the assigned
doublet phase advances $\pi$ per rung, completing one assigned phase cycle
every two rungs. This numerical pitch is a **Hypothesized** coordinate
mapping, not a value supplied by $\theta_d$ or the canonical conversion. The
geometric coordinate is distinct from $\theta_d$, and the canonical rank-one
conversion supplies no physical inter-rung flux or rung transport law.
Expansion factor per geometric turn: $\varphi$.

### 10.2 Frenet-Serret Frame

A proposed Frenet-Serret frame, conditional on an assumed three-dimensional
embedding, is

$$\boxed{\text{Three spatial directions} = \{\mathbf{T}, \mathbf{N}, \mathbf{B}\}}$$

- $\mathbf{T}$: tangent (string axis, cascade coordinate)
- $\mathbf{N}$: normal (named Yang coordinate direction)
- $\mathbf{B} = \mathbf{T} \times \mathbf{N}$: binormal (named Yin coordinate direction)

The identification of these vectors with physical spatial axes is
**Hypothesized** and conditional on the embedding and a non-degenerate curve.
The proposed geometric reading $\xi=\varphi^{2\times3}$ counts 2 field
components times 3 frame vectors; it does not derive $d=3$ or $\xi$ from the
canonical density conversion. Any directional population or kinetic extension
requires selecting an oriented axis and remains conditional; it does not add
canonical field components or an extra spacetime dimension.

### 10.3 Bubble Geometry

Within the optional geometric model, the Cassi bubble is represented at
coordinate step 285 as a triaxial spheroid bounded between adjacent
coordinate steps. Its Yang-Yin cross-section is elliptical with axis ratio
$\varphi$. The condensation boundary is the level set of
$C(x,y)=\cos(2\pi x/\Lambda_Y)\cos(2\pi y/\Lambda_I)$. At a common boundary
level $\theta_{\mathrm{cond}}$, its directional edge-slope proxy is
$$\boxed{R(\theta_{\mathrm{cond}})\equiv
\frac{|\nabla C|_{\mathrm{axial}}}{|\nabla C|_{\mathrm{diag}}}
=\frac{\sqrt{1+\varphi^2}}{2}
\sqrt{\frac{1+\theta_{\mathrm{cond}}}{\theta_{\mathrm{cond}}}}}.$$
For the phenomenologically selected $\theta_{\mathrm{cond}}=0.45$, $R=1.7072$;
the ratio varies with the selected level. This is a conditional
geometric-proxy benchmark, not a universal or zero-parameter constant, and
the fixed-step PDE diagnostic retains no $C=0.45$ edge. Any physical
cosmological or biological test requires an independently identified boundary
and proxy-to-observable map. Adjacent bubbles use the $m+n$ even sublattice;
voids use the odd sublattice.

The proposed condensation field and bubble lattice are scale-covariant across
the model's coordinate rungs under the stated geometric construction—see
`foundations/bubble-lattice-fabric.md` for the conditional geometric
signatures.

### 10.4 String-Bubble Projective Map

Conditional on the complex CassiFI doublet, the normalized projective state
$[z_Y:z_I]\in\mathbb{CP}^1$ supplies a phase-bearing shell over the canonical
density pair:

$$
(E_Y,E_I)=\rho\left(\cos^2\frac{\vartheta}{2},
\sin^2\frac{\vartheta}{2}\right),
\qquad
\delta=\arg z_I-\arg z_Y .
$$

Its Bloch vector is
$\mathbf n=(\sin\vartheta\cos\delta,\sin\vartheta\sin\delta,
\cos\vartheta)\in S^2$.

For the selected quadratic bubble boundary, set
$A=\sqrt{2(1-\theta_{\mathrm{cond}})}$ and

$$
\mathbf X=D\mathbf n,\qquad
D=\operatorname{diag}\!\left(\frac{A}{\alpha},
\frac{A}{\beta},\frac{A}{\gamma_n}\right),\qquad
\|D^{-1}\mathbf X\|=1.
$$

The relative phase acts on this shell by
$G(\Delta)=D R_z(\Delta)D^{-1}$, an exact one-parameter isometry of the
pullback metric $D^{-2}$. Its orbit at fixed density composition is a latitude
ellipse. At the Cassi fixed ratio $E_Y/E_I=\varphi$, the latitude is fixed by
$\cos\vartheta_\varphi=\varphi^{-3}$, while the canonical conversion law gives
the meridional relaxation of $\vartheta$. Supplying uniform phase motion
generates smooth shell circulation, but no phase equation selects that motion.
Five selected phases give a pentagon, and step-two connectivity gives its
pentagram; neither selection nor locking follows from the canonical
real-density PDE. The geometry, affine group action, and conversion-only
meridional flow are **Derived conditional**. Physical identification of the
projective shell with the condensation boundary, persistent phase circulation,
and spontaneous fivefold locking remain **Hypothesized**. See
`foundations/string-bubble-projective-map.md`.

The shared-support loop completion resolves four nonnegative populations—
Yang and Yin carriers in the two orientations of one closed support—and
projects their complete-loop zero mode exactly to the canonical density law
under a common projected gate and common exterior transport. Tracing the
phase-bearing amplitudes over loop and direction labels gives a positive
$2\times2$ species Gram matrix. Its normalized Bloch vector fills the affine
bubble volume, and its rank-one boundary is the projective shell above.
Equal $\pi$-alternating contributions cancel transverse coherence in even
pairs. The frozen internal generator has an explicit Fourier spectrum whose
nonzero-mode gap controls zero-mode coarse-graining; it fixes no universal
strand-to-bubble spatial ratio. These statements are **Derived conditional**.
The loop-carrier identification, phase dynamics, QF1-to-carrier state map,
and quantum postulates remain independent. See
`foundations/loop-to-bubble-projection-theorem.md`.

### 10.5 Wake-Wave Mechanism

An optional compact-phase/wake construction can pair sheets through an anti-phase assignment ($\Delta\phi=\pi$), producing paired sheets flanking a central void. This is a **Hypothesized** phenomenological extension; the canonical rank-one real-density conversion has no phase or anti-phase structural property.

---

## 11. Consciousness

### 11.1 Pinch Transition

Under an optional **Hypothesized** self-model mapping, $r=\varphi^{-1}$ is treated as a Qi-gate pinch threshold: before, $r<\varphi^{-1}$ corresponds to no self-modeling; after, $r>\varphi^{-1}$ corresponds to the field modeling its own evolution. The canonical PDE supplies density conversion and the $q$ diagnostic, not a self-reference or self-model criterion.

### 11.2 Chakra Cascade

An optional **Hypothesized** geometric model places 13 proposed chakra markers as localized Qi condensates along a named spine at $\varphi^2$-spaced intervals. The crown is at step 166 (2 rungs below the body boundary at 168). Under the **Hypothesized** geometric phase convention, 13 nodes span 26 cascade rungs (2 rungs per assigned doublet phase cycle). Six secondary nodes midway between primaries. Inter-chakra spacing ratio: $\varphi^2$. A $\ln\varphi$ periodic signature in physiological signals is likewise **Hypothesized**.

### 11.3 Mind-Brain

Mind: concentrated post-pinch field dynamics. Brain: antenna for the Qi field. Altered states correspond to spatial ratio dispersion $\sigma_r = \sqrt{\langle(r-\langle r\rangle)^2\rangle}$: waking (moderate), meditation (reduced), psychedelic (increased, sub-pinch excursions).

---
## 12. Derived Constants

| Parameter | Expression | Value | Origin |
|-----------|-----------|-------|--------|
| $\alpha_0$ | $\varphi^{-3} = (\varphi-1)/(\varphi+1)$ | $0.236$ | Fixed-point imbalance (the "Yang fraction" label is Mapped—ledger row 500; the Yang fraction is $\varphi^{-1}$) |
| $\xi$ | $\varphi^6$ | $17.944$ | Imbalance inverse-square $\xi = (\pi/\rho)^{-2}$ (Derived conditional on the quadratic-coupling input; the 2×3-DOF reading is secondary—`xi-derivation.md`; empirical pin Calibrated) |
| $\sin^2\theta_W$ | $\varphi^{-3}$ | $0.236$ | Asserted coupling boundary (the VEV orientation enters the full mass matrix but does not fix the relative gauge coupling; realized at $\mu_* = 233$ GeV—Calibrated, ledger row 490) |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | $1/53$ | Fixed-point imbalance / $4\pi$ (asserted boundary condition) |
| $m_W/m_Z$ | $\sqrt{1-\varphi^{-3}}$ | $0.874$ | From $\sin^2\theta_W$ (inherits its boundary-condition status) |
| $\delta_{\text{CKM}}$ | $\pi\varphi^{-2}$ | $68.7^\circ$ | Mapped selection (4-candidate $\varphi$-search—ledger row 482) |
| $w_0$ | Wu Xing + $\xi$ | $-0.87$ | Calibrated (DESI-anchored—ledger row 496) |
| $w_a$ | $\xi$ in $H(a)$; ratified conversion→expansion coupling | $+0.012$ baseline; $-0.38$ (B2, unstable); **$(-1, 0)$ pure-Λ window (stable realization—10/12)** | Calibrated baseline (ledger row 496); coupling shifts 08 §C.6; 12 |
| $g$ | $1 - \varphi^{-5}$ | $0.910$ | Wu Xing gap |
| $r_0$ | $\varphi^{-5}/(2-\varphi^{-5})$ | $0.047$ | Primordial ratio |
| $\lambda$ | solver normalization/timescale convention | $0.1$ | PDE conversion normalization: $\lambda=0.1$ is **C-class**; the $w=5$ relation $\lambda=1/(2w)$ is a **Hypothesized** Wu Xing cycle linkage, not a $\varphi$-derived rate |
| $n_s$ | $1 - 2\varphi^{-1}/N_e$ | $0.969$ | Inflation gate ($N_e = 40$ Mapped—ledger row 501) |
| $r$ | $12/N_e^2$ | $0.0075$ | Tensor ratio (Mapped value at the $N_e = 40$ window—ledger row 495; the $0.003$ reading requires $N_e = 63.2$) |
| $\eta$ | $\varphi^{-44}$ | $6.4 \times 10^{-10}$ | Baryon asymmetry (exponent **Mapped**—ledger row 481; mechanism Hypothesized) |
| $\sigma$ | $\ell_{\text{Pl}}/\varphi^3$ |—| Regularization scale ($\delta = 3$ Derived conditional on the noise–signal identification + $d = 3$: per-rung dephasing $\varphi^{-\delta}$ equals the equilibrium excess $\varphi^{-3}$—`gravity/quantum-gravity.md` §2.1) |
| $\Omega_{\text{DM}}/\Omega_b$ | $\varphi^3$ | $4.24$ | Qi condensate base, Derived conditional on the Weinberg-angle identification; the $+1$ capture term is excluded by the component budget—ledger row 502 |
| $\bar{\theta}$ | $\pi\varphi^{-83.4}$ | $1.2\times10^{-17}$ | Strong CP |
| $N_{\mathrm{budget},p}$ | $\varphi^{4505.5758}$ | $\sim10^{941.8}$ modeled cycles | Proton coherence budget; Derived conditional arithmetic at $N_p^{\mathrm{budget}}=91.46$, with failure and trial-frequency maps Hypothesized |
| $\hbar\mathcal J_{Q,1}/(K_{\mathfrak s}\rho)$ | $2\pi/(\varphi^3\mathfrak s_p)$ | $0.0162173$ | Planck-to-proton two-rail circuit; Derived conditional on the Mapped endpoint, uniform $\varphi$ composition, $m=1$, and zero endpoint bias |

External constants: $c$, $\hbar$, $G$ define the unit system. $\ell_{\text{Pl}} = \sqrt{\hbar G/c^3}$ is the cascade's sole dimensionful anchor.
