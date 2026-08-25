# Cassi Cosmology: Inflation, Baryogenesis, and Dark Matter from $\varphi$

## Status: Derived formation and structure / Hypothesized inflation and baryogenesis mechanisms / Mapped inflation and baryogenesis observables / Calibrated w₀ coupling form—August 2026

## Abstract

The same two-fluid dynamics organize inflation, baryogenesis, and dark matter; their expanding-universe interpretation uses a separate Hubble closure. In the framework triad, Yang and Yin are the doublet components, while Qi is represented by local spatial diagnostics. For a positive-root amplitude lift, $\mathbf{J}_\Psi=\Psi_0\nabla\Psi_1-\Psi_1\nabla\Psi_0=\rho\nabla\theta_\Psi$ and $\mathbf{J}_d=E_Y\nabla E_I-E_I\nabla E_Y=(E_Y^2+E_I^2)\nabla\theta_d$; a named spatial projection is required before assigning direction or sign, and any inter-rung transport requires a separate Hypothesized constitutive law. Inflation is a Hypothesized gate-driven phase transition of the canonical ratio $r=E_Y/E_I$: the intended trajectory starts low and Yin-dominated, rises toward the fixed point $r=\varphi$, and crosses the declared inflation-ending threshold $r=\varphi^{-1}$ before reaching that attractor. Canonical conversion conserves total density and does not itself determine a Hubble law; the inflation construction's positive $H\propto\lambda(1-q)$ input and gate-based exit are Hypothesized. The particle/chiral interpretation used for baryogenesis is also Hypothesized and requires a particle/gauge extension; conditional on that map, the density-ratio algebra gives the $\varphi^{-3}$ imbalance and the observed $\eta=\varphi^{-44}$ remains Mapped with its freeze-out endpoint open. The scalar spectral index is $n_s = 1 - 2\varphi^{-1}/N_e \approx 0.9691$ ($N_e = 40$; Mapped window—ledger), within $1.0\sigma$ of Planck as a closed form (the gate trajectory does not reproduce it, `computations/slow_roll_trajectory.py`). The dark-matter base $\Omega_{\text{DM}}/\Omega_b = \varphi^3 \approx 4.24$ is Derived conditional on the Weinberg-angle identification and leaves a 21% open tension against the observed ratio; the component budget rejects the $+1$ capture term as a double count.

---

## 1. The Two-Fluid Cosmological Backbone

The three phenomena use the same two-fluid dynamics; an expanding-universe interpretation requires a separate Hubble closure. The canonical homogeneous conversion block is:

**Canonical conversion in real two-fluid densities:**

$$
\partial_t E_Y \supset -\lambda(1-q)(E_Y-\varphi E_I)
$$

$$
\partial_t E_I \supset +\lambda(1-q)(E_Y-\varphi E_I).
$$
The equal-and-opposite conversion pair conserves the total real density:

$$
(\partial_t E_Y+\partial_t E_I)_{\mathrm{conv}}=0.
$$

**Conditional comoving solver form:** If $\psi_y,\psi_i$ are chosen as comoving representations proportional to $E_Y,E_I$, a solver may add

$$
\partial_t\psi_y + \mathbf{u}\cdot\nabla\psi_y = -\lambda(1-q)(\psi_y - \varphi\psi_i) + \chi_y\nabla\cdot(\psi_y\nabla\Phi) + D\nabla^2\psi_y
$$

$$
\partial_t\psi_i + \mathbf{u}\cdot\nabla\psi_i = \lambda(1-q)(\psi_y - \varphi\psi_i) - \chi_i\nabla\cdot(\psi_i\nabla\Phi) + D\nabla^2\psi_i.
$$

The advection, gradient, diffusion, and source terms in this comoving form are Hypothesized or conditional closures; only the $E_Y,E_I$ conversion pair above is canonical.

**Hypothesized scale-factor closure:** When the comoving representation is embedded in an expanding model,

$$
a_{t+1} = a_t \cdot e^{H\Delta t}.
$$

Canonical conversion therefore conserves total density and does not by itself determine $H$. A separate conversion→expansion extension is Hypothesized and uses the current source normalization

$$
V_{\mathrm{new}}:=\lambda\,\widetilde h(E_Y,E_I)+\frac{\lambda\varphi^{-2}}{d},
$$

with $d=3$ for the assumed spatial dimension; it is not implemented in the canonical solver. The inflation construction uses only the scoped input $H\propto\lambda(1-q)$ under a chosen amplitude normalization, with no proportionality coefficient fixed here.

A positive vacuum contribution is parameterized separately:

$$
H_{\text{empty}} = \frac{\lambda}{3}\varphi^{-2}.
$$

Here the canonical ratio is $r=E_Y/E_I$, with $E_Y$ and $E_I$ the homogeneous or averaged two-fluid densities.

**Key observation:** The comoving densities $\psi_y, \psi_i$ already absorb the $a^{-3}$ dilution. The physical densities $\rho_y = \psi_y/a^3$ would have explicit Hubble friction $-3H\rho_y$ when evolved once a Hubble closure is supplied. This is the Cassi analogue of the slow-roll equation's $3H\dot\phi$ bookkeeping; it does not derive $H$ from canonical conversion.

**The $1/3$ coefficient: the isotropic dimension factor (1/d at the assumed d = 3), not a φ quantity.** Status: Derived conditional on the assumed spatial dimension d = 3 (coefficient)—2026-08-11; the rate $\lambda\varphi^{-2}$ remains Asserted.

The $1/3$ in $H_{\text{empty}} = \lambda\varphi^{-2}/3$ is the $d$-dimensional isotropic continuity factor, $1/d$ at $d = 3$—the same dimension-structure factor as the $3$ in GR's $8\pi G/3$ (the analogue of the $4\pi$ in $\alpha_{\text{GUT}}$'s denominator). It is not a $\varphi$ quantity and never required a $\varphi$ derivation: no $\varphi$ power equals $1/3$ ($\varphi^{-2} = 0.382$, 15% off; $\varphi^{-3} = 0.236$, 29% off; $1/3 = \varphi^{-2.283}$).

Derivation of the coefficient:

1. The two-fluid PDE evolves densities on the assumed $d = 3$ grid (`ExpandingTwoFluid3DGPU`), with an isotropic Hubble flow $\mathbf{u} = H\mathbf{x}$; the divergence is $\nabla\cdot\mathbf{u} = dH$ (verified numerically for $d = 1, 2, 3$).
2. The physical densities satisfy the continuity equation $\dot\rho + dH\rho = s\rho$ with a source of rate $s$ per unit density; steady state requires $dH = s$, so $H = s/d$. With the vacuum rate $s = \lambda\varphi^{-2}$ this is $H_{\text{empty}} = \lambda\varphi^{-2}/d\big|_{d=3} = \lambda\varphi^{-2}/3$—exactly the flagged form at the assumed $d=3$ (verified: without the $1/3$ the density drifts at $-2\lambda\varphi^{-2}\rho$).
3. The same $1/3$ is the angle average of the per-axis Laplacian: $\langle\partial^2 f/\partial x^2\rangle = \tfrac13\nabla^2 f$ for spherically symmetric $f$ (verified on $f = r^2, r^4$; the plane-wave direction average $\langle k_x^2\rangle = k^2/3$ over $S^2$), and the Newtonian/GR source's volume factor: $\nabla^2\Phi = 4\pi G\rho \Rightarrow \partial_r\Phi = (4\pi G/3)\rho r$ (enclosed volume $\tfrac43\pi r^3$), and $G_{00} = 3H^2$ for flat FRW (sympy-verified) $\Rightarrow H^2 = (8\pi G/3)\rho$.

The $1/3$ is therefore the GR-compatible normalization once the assumed $d=3$ geometry is supplied; the two-fluid continuity calculation shares this kinematic factor but does not determine $d$. The dimensional identification is Hypothesized in `foundations/why-three-dimensions.md`. The Lagrangian's $T_{00}$ at equilibrium gives $0$ or $(g/4)\varphi^2$; it cannot give $\lambda\varphi^{-2}/3$, because the $1/3$ is kinematic (a dimension count), not a Lagrangian quantity. The same explicit $d$ appears in the ratified conversion→expansion coupling's vacuum half $\lambda\varphi^{-2}/d$ (`parameter-inventory.md` §7, Conversion→expansion row) and in the per-axis reading $\varphi^{-\delta} = (\varphi^{-1})^d$ (`gravity/quantum-gravity.md` §(i)).

What remains asserted is the **positive vacuum source rate** $\lambda\varphi^{-2}$; the canonical conversion block does not derive this source or an expansion law.

**Coincidence note (not a derivation):** the dimension count $3$ coincides with the exact $\varphi$-algebra sum identity $\varphi^2 + \varphi^{-2} = 3$. At the $\varphi$-fixed point, $\varepsilon=E_Y-\varphi E_I=0$; under the reference normalization $E_Y=1$, $E_I=\varphi^{-1}$, and $\rho=E_Y+E_I=\varphi$, the canonical gate $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$ gives $(1-q_0)=\varphi^{-2}/(\varphi^2+\varphi^{-2})=\varphi^{-2}/3$. This gate fraction is normalization-dependent, not universal; $q\to1$ only in the large-density limit. Under the same reference normalization, the radial relaxation rate at the attractor is $\gamma=\lambda(1-q_0)(1+\varphi)=\lambda(\varphi^{-2}/3)\varphi^2=\lambda/3$ (`foundations/spiral-dynamics.md` §2.3)—the same $1/3$ via the sum, not via a single $\varphi$ power. The coefficient remains the kinematic dimension factor $1/d$; the identity makes the gate's normalization numerically equal to $d=3$, it does not make the dimension count a $\varphi$ quantity (no $\varphi^n=3$; $n=\ln 3/\ln\varphi=2.283$).

$$\boxed{H_{\text{empty}} = \frac{\lambda\varphi^{-2}}{d}\bigg|_{d=3} = \frac{\lambda\varphi^{-2}}{3}, \qquad \nabla\cdot\mathbf{u} = dH,\quad \dot\rho + dH\rho = s\rho \;\Rightarrow\; H = \frac{s}{d},\qquad \frac{1}{3} = \frac{1}{d}\bigg|_{d=3}}$$

**Inputs:** $\boxed{\text{(1) } d = 3 \text{ (the assumed PDE spatial dimension); (2) the kinematic continuity structure } \nabla\cdot\mathbf{u} = dH; \text{ (3) the vacuum rate } s = \lambda\varphi^{-2} \text{ (Asserted—the open part).}}$

Verification: `computations/verify_h_form_one_third.py` (φ-power check; $\nabla\cdot\mathbf{u} = dH$; continuity steady state; angle-averaged Laplacian; Newtonian/FRW volume factor)—all checks pass.

---

## 2. Inflation as a $\varphi$-Driven Phase Transition

### 2.1 The Mechanism

The canonical ratio is $r=E_Y/E_I$. For the homogeneous conversion block, writing $\kappa=\lambda(1-q)$ gives

$$
\left.\partial_t r\right|_{\mathrm{conv}}=\kappa(\varphi-r)(1+r)=\lambda(1-q)(\varphi-r)(1+r).
$$

The conversion terms are equal and opposite, so they conserve the total density while moving the ratio toward $r=\varphi$. Along the intended inflationary trajectory the initial state is low-$r$ and Yin-dominated, with $r<\varphi^{-1}<\varphi$; the conversion contribution therefore drives $r$ upward. Gradient, transport, and source terms can add to the ratio dynamics.

The live Hypothesized inflation construction chooses an amplitude normalization in this low-$r$ regime for which $(1-q)\approx1$. It takes $H\propto\lambda(1-q)>0$ as a nearly constant slow-roll input, rather than deriving a Hubble law from canonical conversion. As the gate closes, this Hypothesized input decreases and supplies the graceful-exit mechanism.

The declared inflation-ending threshold is

$$
r_{\mathrm{exit}}=\varphi^{-1}
$$

at approximately cascade step $60$. This threshold is distinct from the canonical density-conversion fixed point $r=\varphi$, which is the later attractor approached if conversion continues.

### 2.2 Gate Closure and E-Folds

No canonical inflaton field or ratio-only slow-roll potential is supplied by the two-density equations. The Hypothesized construction instead treats $H\propto\lambda(1-q)$ as the slow-roll input under the chosen low-$r$ normalization, with gate closure at $r_{\mathrm{exit}}=\varphi^{-1}$ providing the exit.

For an increasing trajectory from an initial low-ratio state $r_i$ to the declared exit,

$$
N_e=\int_{t_i}^{t_{\mathrm{exit}}}H\,dt=\int_{r_i}^{r_{\mathrm{exit}}}\frac{H(r)}{\partial_t r}\,dr,\qquad r_i<r_{\mathrm{exit}}=\varphi^{-1},\quad \partial_t r>0.
$$

The canonical equations provide the conversion contribution to $\partial_t r$ but do not provide $H(r)$; the gate openness also depends on the amplitude normalization. This integral is therefore not evaluated as a parameter-free prediction. The Mapped e-fold count is the cascade window from steps $20$ to $60$,

$$
N_e^{\mathrm{cascade}}=\frac{\ln(\ell_{60}/\ell_{20})}{\ln\varphi}=40,
$$

and the closed-form inflation observables use this window.

### 2.3 Observable Predictions

| Quantity | Cassi Prediction | Planck 2018 |
|----------|-----------------|-------------|
| Scalar spectral index $n_s$ | $1 - 2\varphi^{-1}/N_e \approx 0.9691$ | $0.9649 \pm 0.0042$ |
| Tensor-to-scalar ratio $r_T$ | $12/N_e^2 = 0.0075$ ($N_e = 40$—Mapped window) | $< 0.032$ |
| Running $dn_s/d\ln k$ | $-2\varphi^{-1}/N_e^2 \approx -7.7\times10^{-4}$ under the same Hypothesized gate-correction ansatz (consistent at about $0.6\sigma$; too small for current detection) | $-0.0045 \pm 0.0067$ |
| E-foldings $N_e$ | $40$ (cascade steps 20--60; Mapped window; exit threshold at step $\sim60$) | $50$--$60$ |
| Perturbation amplitude $\mathcal{P}_\zeta$ | $\sim2\times10^{-9}$ only as a Hypothesized wake-wave normalization; no canonical inflaton amplitude formula | $2.1\times10^{-9}$ |
| Inflation scale $M_{\text{inf}}$ | $\sqrt{\alpha_{\text{GUT}}}\,M_{\text{Pl}} \approx 1.7\times10^{18}$ GeV for the repo input $\alpha_{\text{GUT}} = \varphi^{-3}/4\pi \approx 1/53$; this scale is conditional on that selected coupling, while the steps 20–60 window independently supplies the Mapped e-fold count |—|

The closed-form spectral index $n_s = 0.9691$ is a Mapped wake-wave/cascade-spacing result and lies within $1.0\sigma$ of Planck. The gate trajectory does not reproduce it—$(n_s, r_T) = (0.813, 0.188)$ under 1 step = 1 e-fold, $(0.914, 0.060)$ with $N_e = 40$ literal (2026-08-06, `computations/slow_roll_trajectory.py`); $N_e = 40$ is the Mapped cascade-window choice. The tensor-to-scalar ratio is $r_T = 12/N_e^2 = 0.0075$ at that window (ledger row 495; the $\varphi^{-12} \approx 0.003$ reading requires $N_e = 63.2$); the trajectory's $r_T$ is excluded by the BK18 bound, and the closed-form values do not coexist with that trajectory.

### 2.4 Exit and Reheating

Inflation ends when the gate reaches the declared threshold $r_{\mathrm{exit}}=\varphi^{-1}$, at approximately cascade step $60$. The gate begins closing there and the Hypothesized $H\propto\lambda(1-q)$ input decreases, supplying a graceful exit. The canonical fixed point $r=\varphi$ is a separate later density-conversion attractor.

The canonical conversion pair is equal and opposite and conserves total density; it does not specify a radiation channel, a decay rate, or thermalization. No canonical $\Gamma_{\mathrm{reh}}$ or $T_{\mathrm{reh}}$ prediction follows from the two-fluid equations. Reheating and the initial hot-Big-Bang temperature therefore require an additional Hypothesized decay/thermalization model.

---

## 3. Baryogenesis from Yang/Yin Asymmetry

### 3.1 The Mechanism

After inflation, the two-fluid state can carry a Yang/Yin density imbalance. Identifying the real density components with Dirac bilinears

$$
E_Y = \bar\psi\frac{1+\gamma^5}{2}\psi, \qquad
E_I = \bar\psi\frac{1-\gamma^5}{2}\psi
$$

is a Hypothesized particle/chiral map, not a consequence of the canonical two-density PDE. It requires an explicit particle and gauge-sector extension that defines the relevant charges and currents.

Conditional on that map, the $\varphi$-equilibrium ratio is $E_Y/E_I=\varphi>1$, which would represent a chiral imbalance. The normalized density-ratio algebra is

$$
\Delta_{\mathrm{map}}(B-L):=\frac{E_Y-E_I}{E_Y+E_I}=\frac{\varphi-1}{\varphi+1}=\varphi^{-3}\approx0.236.
$$

The $\varphi^{-3}$ identity is exact conditional algebra. Identifying it with a baryon-minus-lepton asymmetry, a Weinberg-angle relation, or a VEV asymmetry remains Hypothesized and requires the same particle/gauge extension.

### 3.2 Sphaleron Conversion

If the particle/gauge extension supplies the Standard Model electroweak charges and a well-defined $B-L$ current, sphaleron processes at temperatures $T>100\ \mathrm{GeV}$ can convert that asymmetry into baryon number:

$$
B=\frac{28}{79}(B-L)\quad\text{(SM with one Higgs doublet)}.
$$

Conditional on this extension, the baryon-to-photon ratio is the ledgered Mapped value (`foundations/baryon-asymmetry.md`; Fit-Status Ledger row 481): the residual Yang excess after organized annihilation is attenuated through 44 rungs of photon-producing conversion, but the freeze-out-step construction (steps 8 → 52) does not close with the GUT anchor ($60 - 13.3 = 46.7$), and the available dilution span is $33.4 \neq 44$, so the exponent $-44$ is a fit to the observed value, not a derivation. The mechanism (Wu Xing gap + organized annihilation + cascade dilution) is Hypothesized.

$$
\boxed{\eta = \varphi^{-44} \approx 6.38 \times 10^{-10}}
$$

**Observed:** $\eta = 6.0 \times 10^{-10}$

The prediction sits **within 6.3%** of the observed value.

### 3.3 Sakharov Conditions

The following table records requirements for a possible particle/gauge extension; the canonical two-density PDE does not establish these conditions by itself.

| Condition | Conditional Cassi interpretation |
|-----------|----------------------------------|
| **B violation** | Sphaleron processes at $T>T_{\text{sph}}$ after the required electroweak extension is supplied (Hypothesized) |
| **C/CP violation** | The mapped Yang/Yin chiral imbalance is a Hypothesized candidate; canonical density dynamics do not establish a CP-violating phase |
| **Out of equilibrium** | An electroweak phase transition and freeze-out at $T\approx T_{\text{sph}}$ require an explicit rate and particle-sector model (Hypothesized) |

The canonical fields therefore do not by themselves satisfy the Sakharov conditions, and no conclusion about additional CP-violating phases follows until the particle/gauge extension is specified.

### 3.4 Summary

| Quantity | Cassi Prediction | Observed | Ratio |
|----------|-----------------|----------|-------|
| $\eta = n_B/n_\gamma$ | $\varphi^{-44} \approx 6.38\times10^{-10}$ (Mapped conditional on the particle/gauge map; endpoint open) | $6.0\times10^{-10}$ | Within 6.3% |

---

## 4. Dark Matter as High-Qi Condensate

### 4.1 The Mechanism

The framework considers possible coherent condensates—regions where the Qi
quality is high, with $q\to1$ only in the large-density saturation limit, and
the Yang/Yin ratio at the $\varphi$-attractor. Their formation and localized
profile remain Hypothesized:

- **Dark:** They are pure two-fluid field, not baryonic matter. No electromagnetic interaction.
- **Gravitationally active:** $G_{\text{eff}} = G\,(\pi/\rho)(1+(\varphi^{6}-1)q)$ with $\xi = \varphi^6 \approx 17.944$; this scalar is a coupling magnitude. At the $\varphi$-fixed point the geometric factor is the imbalance $\alpha_0 = \pi/\rho = (\varphi-1)/(\varphi+1) = \varphi^{-3} \approx 0.236$ (the Yang fraction at equilibrium is $\varphi^{-1}$—ledger row 500 relabel). Under the canonical $+\pi[1+(\varphi^6-1)q]\nabla\Phi$ convention with $\Phi=-G\sum_iM_i/|\mathbf{x}-\mathbf{X}_i|$, positive $\pi$ gives outward acceleration; an attractive halo or rotation-curve interpretation requires a separate Hypothesized sign-changing branch.
- **Homogeneous fixed point:** The conversion block has a restoring $r=\varphi$ fixed point when $1-q>0$; localized condensate stability is not established by the canonical equations.
- **Collisionless only under an extension:** A field-condensate realization could pass through other matter without friction, but the canonical two-density equations do not establish a particle-scattering or Bullet-Cluster response; this comparison remains Hypothesized.

### 4.2 Formation and Abundance

High-Qi regions are discussed in the potential wells of galaxy halos during
structure formation ($z \sim 1$--$3$). The present closure supplies no
calibration from the solver parameter $\lambda$ to physical time: $\lambda$ is
retained in solver-time units while $H_0$ is a physical rate, so
$1/(\lambda H_0)$ is not a dimensionally defined formation time. A physical
$t_{\text{form}}$ requires an explicit time-calibration input.

**The $\varphi^3$ base.** The abundance relative to baryons is the ratio of the gravitational amplification to the electroweak/EM decoupling structure. The rung arithmetic closes exactly for only one identification of that structure. The repo's own rung placements ($n = \log_\varphi(\text{scale})$; `foundations/dimensionful-cascade.md` §5.2, `foundations/dimensionful-constants-status.md` §3.5):

| Scale | Rung |
|---|---|
| $\alpha_{\text{EM}}^{-1} = 137.04$ (zero momentum) | $10.22$ |
| $\alpha_{\text{EM}}^{-1} = 128.95$ ($m_Z$) | $10.10$ |
| $\alpha_{\text{EM}}^{-1} = 225$ ($M_{\text{GUT}}$) | $11.26$ |
| $\xi = \varphi^6$ (gravitational amplification) | $6$ (exact) |
| $\left.G_{\text{eff}}/G\right|_{\alpha=\alpha_0,\,q\to1} = \varphi^3$ (fixed-composition $\varphi$-attractor branch) | $3$ (exact) |
| $\sin^2\theta_W = \varphi^{-3} = \alpha_0$ (fixed-point imbalance) | $3$ (exact; exponent $-3$) |

The span from the gravitational coupling $\xi$ (rung 6) to $\alpha_{\text{EM}}^{-1}$ (rung 10.22) is $4.22$ rungs, not 3—the "gap between the gravitational coupling and the EM decoupling scale" does **not** close with $\alpha_{\text{EM}}$ as the decoupling scale. It closes exactly only when the EM-decoupling structure is the electroweak mixing angle $\sin^2\theta_W = \varphi^{-3} = \alpha_0$, the fixed-point imbalance (catalog step 3). On this fixed-composition $\varphi$-attractor branch, $\alpha=\pi/\rho=\alpha_0$ is held fixed while density drives $q\to1$; this is a branch-specific saturation value, not a global maximum over canonical states. Off the attractor, the coupled $(\pi/\rho,q)$ dependence requires a specified constitutive domain.

$$
\boxed{\frac{\Omega_{\text{DM}}}{\Omega_b} = \xi \cdot \sin^2\theta_W = \varphi^6 \cdot \varphi^{-3} = \varphi^3 = 4.2361 = \alpha_0^{-1} = \left.\frac{G_{\text{eff}}}{G}\right|_{\alpha=\alpha_0,\,q\to1}}
$$

The base is the inverse fixed-point imbalance $\alpha_0^{-1}$—the same imbalance whose inverse square defines $\xi$ (`foundations/xi-derivation.md` §2.1–2.2)—and equals the fixed-composition branch value above. Verified numerically to machine precision (`computations/dm_baryon_ratio_verification.py`, part A). **Tier: Derived conditional on the identification**—$\sin^2\theta_W$ is not $\alpha_{\text{EM}}$ (rung 10.22, span 4.22), and $\xi\cdot\alpha_0 = \alpha_0^{-1}$ is an algebraic identity of a single imbalance, not an independent scale-gap; the claim that condensate freeze-out realizes this branch value in the density ratio is asserted (mechanism label "Qi condensate freeze-out", `foundations/dimensionful-cascade.md` §5.2).

**Inputs ($\varphi^3$ base):** $\boxed{\text{(1) the derived coupling } \xi = \varphi^6 \text{ (`foundations/xi-derivation.md`); (2) the identification of the EM-decoupling structure with the Weinberg-angle imbalance } \sin^2\theta_W = \varphi^{-3} = \alpha_0.}$

**The capture construction is excluded.** The framework has three reservoirs, and only two are distinct:

$$
\Omega_{b,\text{total}} = \Omega_{b,\text{primordial}} = \Omega_{b,\text{free}} + \Omega_{b,\text{captured}}, \qquad \Omega_{\text{DM}} = \Omega_{\text{Qi}} = \Omega_c \ \text{(non-baryonic condensate)}
$$

The observed ratio is $\Omega_c/\Omega_b$: its numerator is baryon-free **by construction** ($\Omega_c = \Omega_m - \Omega_b$), and its denominator is the BBN/CMB-pinned **total** baryon density, which already contains every baryon captured into halos. A "$+1$ capture term" therefore has no distinct mass budget—added to the numerator it double-counts the $\Omega_b$ already in the denominator, and as a capture fraction it would require $f_{\text{cap}} = 1.00$ (all baryons captured), 5–10$\times$ the external cosmic census bracket $f_{\text{cap}} \approx 0.10$–$0.20$ (stars + ISM + halo/ICM gas; Fukugita et al. 1998; Shull et al. 2012—flagged external, not framework-derived). The component budget (`computations/dm_baryon_component_budget.py`) and the SPARC cross-check (`computations/dm_baryon_ratio_verification.py`) fix the prediction at the condensate base; Fit-Status Ledger row 502 records the $+1$ as a calibration artifact, excluded from the predicted value.

$$
\boxed{\frac{\Omega_{\text{DM}}}{\Omega_b} = \varphi^3 = 4.2361} \qquad \text{observed: } \frac{\Omega_{\text{DM}}}{\Omega_b} = \frac{0.264}{0.049} \approx 5.39 \quad (-21\%)
$$

The observed ratio is $\Omega_c/\Omega_b = 0.264/0.049 \approx 5.39$ (Planck 2018 $\Omega_c h^2/\Omega_b h^2 = 0.11933/0.02242 = 5.32$). The 21% residual is an open tension; the base is Derived conditional on the Weinberg-angle identification (§4.2), and the $+1$ capture construction is excluded by the component budget.

### 4.3 Comparison with Dark Matter Candidates

| Property | Qi Condensate | WIMP | Axion | Observed |
|----------|--------------|------|-------|----------|
| Direct detection | Null (field) | Non-null | Non-null | Null (all expts) |
| Self-interaction | Collisionless | Collisional | Collisionless | Collisionless |
| Structure $z$ | Hypothesized condensate-formation window $\sim 1$–$3$ | $> 10$ | $> 10$ | $\sim 1$–$3$ |
| Halo density | Hypothesized smoothing profile; target is a cored/core-cusp comparison | $r^{-2}$ (NFW) | $r^{-2}$ (NFW) | Core/cusp mixed |

The condensate's profile shape and formation window are Hypothesized extensions of the canonical two-fluid equations. A cored profile is a comparison target for dwarf-galaxy data; no preference over NFW is established by the present closure.

### 4.4 Observational Tests

| Test | Conditional model comparison | Current empirical status |
|------|------------------------------|--------------------------|
| Galaxy rotation curves | Hypothesized attractive branch: flat curve with $(1+(\varphi^{6}-1)q)\times$ boost | Milky Way and dwarf curves are comparison targets; the attractive sign and $q$-to-force constitutive map remain open |
| Bullet Cluster | A Hypothesized field-condensate extension would behave collisionlessly | The observation supports collisionless gravitating structure but does not discriminate this extension |
| Weak lensing | Conditional enhancement of $G_{\text{eff}}$ in halos | LSST comparison target; the required constitutive map remains open |
| Direct detection | A Hypothesized field condensate has no particle-scattering channel | Particle searches report null results; their connection to this field extension remains model-dependent |
| CMB $\sigma_8$ | **+0.3% ± 0.5 pp vs $\Lambda$CDM (P-A, measured window $z \in [100, 61]$)** — the window-integrated per-cell mixture on the ΛCDM background (the window's content is the q-history 0.866 → 0.795, not the endpoint; mixture = mean-field); the P-C pointwise-chord reading (flagged): +24.8% ± 16.3 pp over the measured window $z \in [100, 61]$, then −95.7% ± 2.4 pp over the measured continuation $z \in [61, 0]$ (the freeze is structural in the continuation — Re p = −0.25 for every μ < −1/24, all cells end R < 1 through z → 0; N=128 confirms +24.83% / −95.9%, resolution-stable; `cassi-toe-rewrite-briefs/spiral-gravity/53-post-freeze-continuation.md`, `cassi-toe-rewrite-briefs/spiral-gravity/54-n128-mixture.md`); the settlement family −16.6% (R = 0.834, regime-integrated, stabilized closure, P-A, $r_0 = 0.0472$) / −15.2% (band-state mean-field) / −11.2% (full-window hold) is the reference (`cosmology/sigma8-computational-plan.md` §3.2; `parameter-inventory.md` §10); the "~5% lower" wording is a plan fit target only, never computed; the μ normalization Mapped | LSST discriminant |

---

## 5. Complete Cassi Cosmology in One Page

### 5.1 Timeline

| Time | Event | Key Equation |
|------|-------|-------------|
| Candidate early-universe epoch (physical $t$ not fixed by the canonical closure) | Inflation begins: low-$r$ Yin-dominated state with $r<\varphi^{-1}$ | $H\propto\lambda(1-q)>0$ (Hypothesized), $N_e=40$ |
| Candidate exit epoch (physical $t$ not fixed by the canonical closure) | Inflation ends: $r$ crosses $\varphi^{-1}$ | Gate closure and graceful exit (Hypothesized); fixed point $r=\varphi$ is later |
| Candidate reheating stage (physical $t$ and $T_{\mathrm{reh}}$ not fixed) | Reheating | Requires an additional Hypothesized decay/thermalization model |
| External electroweak thermal-history anchor ($t\sim10^{-10}$ s; not a Cassi time calibration) | Electroweak phase transition: $T \sim 100$ GeV | $\eta \approx \varphi^{-44}$ (Mapped conditional on the particle/gauge map; freeze-out endpoint open) |
| $z \sim 1$--$3$ | Structure formation | $\Omega_{\text{DM}}/\Omega_b = \varphi^3$ (condensate freeze-out) |
| External current-epoch anchor ($t\sim13.8$ Gyr; not a Cassi time calibration) | Today: approach to the canonical attractor, conditional on conversion-dominated evolution | $q \to q_{\mathrm{eq}}(\rho)<1$ at finite density ($q\to1$ only as $\rho\to\infty$), $\pi/\rho \to \varphi^{-3}\approx0.236$, $r \to \varphi$ |

### 5.2 Predictions

| Observable | Cassi Prediction | Measurement | Gap |
|-----------|-----------------|-------------|-----|
| $n_s$ | $1 - 2\varphi^{-1}/N_e \approx 0.9691$ (Mapped closed form; gate trajectory does not reproduce it) | $0.9649 \pm 0.0042$ | $1.0\sigma$ |
| $r_T$ | $12/N_e^2 = 0.0075$ ($N_e = 40$ Mapped window; 0.003 needs $N_e = 63.2$) | $< 0.032$ | Mapped (ledger §10); gate trajectory's $r_T$ excluded by BK18 (2026-08-06) |
| $\mathcal{P}_\zeta$ | $\sim2\times10^{-9}$ only as a Hypothesized wake-wave normalization; no canonical inflaton amplitude formula | $2.1\times10^{-9}$ | Hypothesized |
| $\eta$ | $\varphi^{-44} \approx 6.38\times10^{-10}$ (Mapped conditional on the particle/gauge map; endpoint open) | $6.0\times10^{-10}$ | 6.3% numerical proximity; no rate-based freeze-out closure |
| $\Omega_{\text{DM}}/\Omega_b$ | $\varphi^3 \approx 4.24$ (base $\varphi^3 = \alpha_0^{-1}$ Derived conditional on the Weinberg-angle identification, §4.2) | $5.39$ | 21% (open tension) |
| $T_{\text{reh}}$ | Not fixed by canonical conversion; additional Hypothesized decay/thermalization model required |—| Open |
| DM direct detection | Null | Null (all expts) | Consistent |
| DM self-interaction | Collisionless | Bullet Cluster | Consistent |

Every prediction comes from $\varphi$ and the two-fluid PDE parameters $(\lambda, \chi, D)$ together with the ledgered anchors. Canonical conversion conserves total density and does not supply a Hubble or reheating law. The inflationary gate mechanism, exit threshold $r_{\mathrm{exit}}=\varphi^{-1}$, and conversion→expansion interpretation are Hypothesized; the canonical fixed point remains $r=\varphi$. The particle/chiral interpretation of the Yang/Yin imbalance and the Sakharov mechanism are also Hypothesized and require a particle/gauge extension. The closed-form $n_s$, $r_T$, and $N_e$ values are Mapped observables or window choices, while $\eta$ remains Mapped conditional on that extension (rows 495, 501, 481). The dark-matter base is Derived conditional on the Weinberg-angle identification (§4.2), its 21% residual remains open, and $w_0$ is Calibrated (row 496).

## References

- `cosmology/inflation-from-cascade.md`—canonical low-$r$ inflation trajectory, gate threshold $r=\varphi^{-1}$, fixed point $r=\varphi$, and Mapped observables.
- `foundations/cassi-theory-reference.md`—canonical two-fluid conversion equations and total-density conservation.
- `foundations/spiral-dynamics.md`—Hypothesized conversion→expansion source normalization.
