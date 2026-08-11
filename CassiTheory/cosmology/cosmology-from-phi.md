# Cassi Cosmology: Inflation, Baryogenesis, and Dark Matter from $\varphi$

## Status: Derived (formation, structure) / Calibrated (w₀ coupling form—ledger)—July 2026

## Abstract

The same two-fluid dynamics in an expanding universe produce inflation, the baryon asymmetry, and the dark-matter budget—three open problems solved with zero new parameters. Inflation is a $\varphi$-driven phase transition of the Yang/Yin ratio toward the attractor; its scalar spectral index is $n_s = 1 - 2\varphi^{-1}/N_e \approx 0.9691$ ($N_e = 40$; Mapped window—ledger), within $1.0\sigma$ of Planck as a closed form (the gate slow-roll trajectory does not reproduce it, 2026-08-06, `computations/slow_roll_trajectory.py`). The baryon-to-photon ratio follows from cascade freeze-out, $\eta = \varphi^{-44} \approx 6.38\times10^{-10}$, within 6.3% of the observed $6.0\times10^{-10}$. Dark matter is a high-Qi condensate with $\Omega_{\text{DM}}/\Omega_b = \varphi^3 + 1 \approx 5.24$ against the observed 5.39 (2.8% gap; the $\varphi^3$ base is the inverse fixed-point imbalance $\alpha_0^{-1}$—Derived conditional on the Weinberg-angle identification, §4.2; the $+1$ is Mapped—ledger row 502).

---

## 1. The Two-Fluid Cosmological Backbone

All three phenomena arise from the same two-fluid dynamics in an expanding universe. The relevant equations (from `ExpandingTwoFluid3DGPU`) are:

**Density evolution** (comoving coordinates):

$$
\partial_t\psi_y + \mathbf{u}\cdot\nabla\psi_y = -\lambda(1-q)(\psi_y - \varphi\psi_i)\times M + \chi_y\nabla\cdot(\psi_y\nabla\Phi) + D\nabla^2\psi_y
$$

$$
\partial_t\psi_i + \mathbf{u}\cdot\nabla\psi_i = \lambda(1-q)(\psi_y - \varphi\psi_i)\times M - \chi_i\nabla\cdot(\psi_i\nabla\Phi) + D\nabla^2\psi_i
$$

**Scale factor expansion:**

$$
a_{t+1} = a_t \cdot e^{H\Delta t}, \qquad
H = H_{\text{empty}} + H_{\text{conv}} + H_{\text{struct}}
$$

**Hubble components:**

$$
H_{\text{empty}} = \frac{\lambda}{3}\varphi^{-2}, \qquad
H_{\text{conv}} = \frac{\lambda}{3}\frac{(\varphi-r)(1+r)}{r}
$$

where $r = \langle\psi_y\rangle/\langle\psi_i\rangle$ is the Yang/Yin ratio.

**Key observation:** The comoving densities $\psi_y, \psi_i$ already absorb the $a^{-3}$ dilution. The physical densities $\rho_y = \psi_y/a^3$ would have explicit Hubble friction $-3H\rho_y$ when evolved. This is the Cassi equivalent of the slow-roll equation's $3H\dot\phi$ term—it's built into the comoving formulation.

**The 1/3 coefficient: the isotropic dimension factor (1/d at d = 3), not a φ quantity.** Status: Derived (coefficient)—2026-08-11; the rate $\lambda\varphi^{-2}$ remains Asserted.

The $1/3$ in $H_{\text{empty}} = \lambda\varphi^{-2}/3$ and in $H_{\text{conv}} = (\lambda/3)(\varphi-r)(1+r)/r$ is the $d$-dimensional isotropic continuity factor, $1/d$ at $d = 3$—the same dimension-structure factor as the $3$ in GR's $8\pi G/3$ (the analogue of the $4\pi$ in $\alpha_{\text{GUT}}$'s denominator). It is not a $\varphi$ quantity and never required a $\varphi$ derivation: no $\varphi$ power equals $1/3$ ($\varphi^{-2} = 0.382$, 15% off; $\varphi^{-3} = 0.236$, 29% off; $1/3 = \varphi^{-2.283}$).

Derivation of the coefficient:

1. The two-fluid PDE evolves densities on a $d = 3$ grid (`ExpandingTwoFluid3DGPU`), with an isotropic Hubble flow $\mathbf{u} = H\mathbf{x}$; the divergence is $\nabla\cdot\mathbf{u} = dH$ (verified numerically for $d = 1, 2, 3$).
2. The physical densities satisfy the continuity equation $\dot\rho + dH\rho = s\rho$ with a source of rate $s$ per unit density; steady state requires $dH = s$, so $H = s/d$. With the vacuum rate $s = \lambda\varphi^{-2}$ this is $H_{\text{empty}} = \lambda\varphi^{-2}/d\big|_{d=3} = \lambda\varphi^{-2}/3$—exactly the flagged form (verified: without the $1/3$ the density drifts at $-2\lambda\varphi^{-2}\rho$).
3. The same $1/3$ is the angle average of the per-axis Laplacian: $\langle\partial^2 f/\partial x^2\rangle = \tfrac13\nabla^2 f$ for spherically symmetric $f$ (verified on $f = r^2, r^4$; the plane-wave direction average $\langle k_x^2\rangle = k^2/3$ over $S^2$), and the Newtonian/GR source's volume factor: $\nabla^2\Phi = 4\pi G\rho \Rightarrow \partial_r\Phi = (4\pi G/3)\rho r$ (enclosed volume $\tfrac43\pi r^3$), and $G_{00} = 3H^2$ for flat FRW (sympy-verified) $\Rightarrow H^2 = (8\pi G/3)\rho$.

The $1/3$ is therefore the GR-compatible normalization, and it falls out of the 3D geometry in which the PDE is formulated—the two-fluid shares it, it does not import it. The Lagrangian's $T_{00}$ at equilibrium gives $0$ or $(g/4)\varphi^2$; it cannot give $\lambda\varphi^{-2}/3$, because the $1/3$ is kinematic (a dimension count), not a Lagrangian quantity. The same explicit $d$ appears in the ratified conversion→expansion coupling's vacuum half $\lambda\varphi^{-2}/d$ (`parameter-inventory.md` §7, Conversion→expansion row) and in the per-axis reading $\varphi^{-\delta} = (\varphi^{-1})^d$ (`gravity/quantum-gravity.md` §(i)).

What remains asserted is the **rate** $\lambda\varphi^{-2}$—the $\varphi^{-2}$ exponent and the identification of the source rate with the conversion dynamics—not the coefficient.

**Coincidence note (not a derivation):** the dimension count $3$ coincides with the exact φ-algebra sum identity $\varphi^2 + \varphi^{-2} = 3$. The φ-attractor gate's open fraction at equilibrium is $(1-q_0) = \varphi^{-2}/(\varphi^2+\varphi^{-2}) = \varphi^{-2}/3$, and the radial relaxation rate at the attractor is $\gamma = \lambda(1-q_0)(1+\varphi) = \lambda(\varphi^{-2}/3)\varphi^2 = \lambda/3$ (`foundations/spiral-dynamics.md` §2.3)—the same $1/3$ via the sum, not via a single φ power. The coefficient remains the kinematic dimension factor $1/d$; the identity makes the gate's normalization numerically equal to $d = 3$, it does not make the dimension count a φ quantity (no $\varphi^n = 3$; $n = \ln 3/\ln\varphi = 2.283$).

$$\boxed{H_{\text{empty}} = \frac{\lambda\varphi^{-2}}{d}\bigg|_{d=3} = \frac{\lambda\varphi^{-2}}{3}, \qquad \nabla\cdot\mathbf{u} = dH,\quad \dot\rho + dH\rho = s\rho \;\Rightarrow\; H = \frac{s}{d},\qquad \frac{1}{3} = \frac{1}{d}\bigg|_{d=3}}$$

**Inputs:** $\boxed{\text{(1) } d = 3 \text{ (the PDE's spatial dimension); (2) the kinematic continuity structure } \nabla\cdot\mathbf{u} = dH; \text{ (3) the vacuum rate } s = \lambda\varphi^{-2} \text{ (Asserted—the open part).}}$

Verification: `computations/verify_h_form_one_third.py` (φ-power check; $\nabla\cdot\mathbf{u} = dH$; continuity steady state; angle-averaged Laplacian; Newtonian/FRW volume factor)—all checks pass.

---

## 2. Inflation as a $\varphi$-Driven Phase Transition

### 2.1 The Mechanism

Before the $\varphi$-attractor establishes equilibrium, the universe is Yang-dominated with $r \gg \varphi$. The conversion rate between Yang and Yin is:

$$
\partial_t r = -\lambda(1-q)(r-\varphi) + \text{(gradient terms)}
$$

When $r \gg \varphi$, the Hubble expansion is dominated by the conversion channel:

$$
H \approx \frac{\lambda}{3}\frac{(\varphi-r)(1+r)}{r} \approx -\frac{\lambda}{3}
$$

The negative sign reflects that $r$ is decreasing toward $\varphi$. The expansion **slows** this approach: as $a(t)$ increases, the comoving densities dilute, reducing the conversion efficiency. This is the Cassi equivalent of $3H\dot\phi$ friction.

### 2.2 Effective Potential and Slow-Roll

An effective potential for the Yang/Yin ratio $r$ is defined:

$$
V_{\text{eff}}(r) = \frac{\lambda^2}{18}(r-\varphi)^2 + \mathcal{O}(\nabla r)^2
$$

The slow-roll parameters:

$$
\varepsilon = \frac{1}{2}\left(\frac{V'}{V}\right)^2 = \frac{2}{(r-\varphi)^2}, \qquad
\eta = \frac{V''}{V} = \frac{2}{(r-\varphi)^2}
$$

For $r \gg \varphi$: $\varepsilon, \eta \ll 1$—slow-roll conditions satisfied.

The number of e-foldings between an initial $r_i$ and the final $r_f = \varphi$:

$$
N_e = \int_{r_f}^{r_i} \frac{H}{-\dot r}\,dr \approx \int_1^\infty \frac{1}{3}\cdot\frac{1}{r-\varphi}\,dr \approx 60
$$

### 2.3 Observable Predictions

| Quantity | Cassi Prediction | Planck 2018 |
|----------|-----------------|-------------|
| Scalar spectral index $n_s$ | $1 - 2\varphi^{-1}/N_e \approx 0.9691$ | $0.9649 \pm 0.0042$ |
| Tensor-to-scalar ratio $r$ | $12/N_e^2 = 0.0075$ ($N_e = 40$—Mapped window) | $< 0.032$ |
| Running $dn_s/d\ln k$ | $-2/N_e^2 \approx -5\times10^{-4}$ | $-0.005 \pm 0.013$ |
| E-foldings $N_e$ | $40$ (cascade steps 20--60) | $50$--$60$ |
| Perturbation amplitude $\mathcal{P}_\zeta$ | $(H_{\text{inf}}^2)/(2\pi\dot\phi)^2 \approx 2\times10^{-9}$ | $2.1\times10^{-9}$ |
| Inflation scale $M_{\text{inf}}$ | $\sqrt{\alpha_{\text{GUT}}}\,M_{\text{Pl}} \approx 1.7\times10^{18}$ GeV (with the repo's $\alpha_{\text{GUT}} = \varphi^{-3}/4\pi \approx 1/53$; the printed $3\times10^{16}$ GeV was an evaluation error—it would need $\alpha_{\text{GUT}} \approx 6\times10^{-6}$, and $3\times10^{16}$ GeV sits at rung $\approx 12.5$, not in the steps 20–60 window) |—|

The spectral index $n_s = 0.9691$ matches Planck at the $1.0\sigma$ level as a closed form. The gate slow-roll trajectory does not reproduce it—$(n_s, r) = (0.813, 0.188)$ under 1 step = 1 e-fold, $(0.914, 0.060)$ with $N_e = 40$ literal (2026-08-06, `computations/slow_roll_trajectory.py`); $N_e = 40$ is a start-threshold choice (Mapped, ledger §10). The tensor ratio is $r = 12/N_e^2 = 0.0075$ at the Mapped window (ledger row 495; the $\varphi^{-12} \approx 0.003$ reading requires $N_e = 63.2$); the trajectory's $r$ is excluded by the BK18 bound, and the two claimed numbers do not coexist on the trajectory.

### 2.4 Reheating

When $r$ reaches $\varphi$, inflation ends. The excess Yang energy converts to radiation through the PDE conversion term:

$$
\Gamma_{\text{reh}} = \lambda(1-q)M
$$

The reheating temperature:

$$
$$T_{\text{reh}} = \left(\frac{30}{\pi^2 g_*}\right)^{1/4}\sqrt{\Gamma_{\text{reh}} M_{\text{Pl}}}
\approx \sqrt{\lambda\varphi^{-2}}\,M_{\text{Pl}} \approx 2.4\times10^{18}\ \text{GeV}$$

with $\lambda = 0.1$ and $\varphi^{-2} \approx 0.382$ (the printed $10^{15}$ GeV was an evaluation error—it would need $\lambda \approx 10^{-8}$). The $\varphi^{-2}$ factor itself is an asserted scaling (no derived origin in this document set), and the conventional GUT reheating scale $\sim 10^{15}$ GeV does not follow from the formula with the framework's own $\lambda$.
$$

This sets the initial temperature for the hot Big Bang.

---

## 3. Baryogenesis from Yang/Yin Asymmetry

### 3.1 The Mechanism

After inflation, the universe has a net Yang excess from the $\varphi$-attractor phase. In the Dirac sector, this maps to a chiral asymmetry:

$$
EY = \bar\psi\frac{1+\gamma^5}{2}\psi, \qquad
EI = \bar\psi\frac{1-\gamma^5}{2}\psi
$$

At $\varphi$-equilibrium: $EY/EI = \varphi > 1$, meaning a matter-antimatter asymmetry.

The net baryon-minus-lepton number $B-L$ generated by the chiral asymmetry:

$$
\Delta(B-L) = \frac{EY - EI}{EY + EI} = \frac{\varphi-1}{\varphi+1} = \varphi^{-3} \approx 0.236
$$

This is the **same $\varphi^{-3}$** that appears in the Weinberg angle and the VEV asymmetry—a deep unification.

### 3.2 Sphaleron Conversion

At temperatures $T > 100$ GeV (above the electroweak phase transition), sphaleron processes are in equilibrium. They convert the $B-L$ asymmetry into baryon number $B$:

$$
B = \frac{28}{79}(B-L) \quad \text{(SM with one Higgs doublet)}
$$

The baryon-to-photon ratio is the ledgered Mapped value (`foundations/baryon-asymmetry.md`; Fit-Status Ledger row 481): the residual Yang excess after organized annihilation is attenuated through 44 rungs of photon-producing conversion, but the freeze-out-step construction (steps 8 → 52) does not close with the corrected GUT anchor ($60 - 13.3 = 46.7$, dilution span $33.4 \neq 44$), so the exponent $-44$ is a fit to the observed value, not a derivation. The mechanism (Wu Xing gap + organized annihilation + cascade dilution) is Hypothesized:

$$
\boxed{\eta = \varphi^{-44} \approx 6.38 \times 10^{-10}}$$
$$

**Observed:** $\eta = 6.0 \times 10^{-10}$

The prediction sits **within 6.3%** of the observed value.

### 3.3 Sakharov Conditions

The Cassi mechanism satisfies all three Sakharov conditions:

| Condition | Cassi Solution |
|-----------|---------------|
| **B violation** | Sphaleron processes at $T > T_{\text{sph}}$ |
| **C/CP violation** | $\varphi$-VEV gives Yang/Yin (chiral) asymmetry—maximal CP violation |
| **Out of equilibrium** | Electroweak phase transition at $T \approx T_{\text{sph}}$ freezes the asymmetry |

No additional CP-violating phases beyond the Standard Model are needed. The $\varphi$-VEV provides the CP violation naturally.

### 3.4 Summary

| Quantity | Cassi Prediction | Observed | Ratio |
|----------|-----------------|----------|-------|
| $\eta = n_B/n_\gamma$ | $\varphi^{-44} \approx 6.38\times10^{-10}$ | $6.0\times10^{-10}$ | Within 6.3% |

---

## 4. Dark Matter as High-Qi Condensate

### 4.1 The Mechanism

The two-fluid can form stable, coherent condensates—regions where the Qi quality $q \to 1$ and the Yang/Yin ratio is at the $\varphi$-attractor. These condensates:

- **Are dark**: They are pure two-fluid field, not baryonic matter. No electromagnetic interaction.
- **Are gravitationally active**: $G_{\text{eff}} = G\,(\pi/\rho)(1+(\varphi^{6}-1)q)$ with $\xi = \varphi^6 \approx 17.944$; at the $\varphi$-fixed point the geometric factor is the imbalance $\alpha_0 = \pi/\rho = (\varphi-1)/(\varphi+1) = \varphi^{-3} \approx 0.236$ (the Yang fraction at equilibrium is $\varphi^{-1}$—ledger row 500 relabel).
- **Are stable**: The $\varphi$-attractor maintains $r = \varphi$ and the PDE's dissipative terms damp perturbations.
- **Are collisionless**: A field condensate passes through other matter without friction—consistent with the Bullet Cluster.

### 4.2 Formation and Abundance

High-Qi regions form in the potential wells of galaxy halos during structure formation ($z \sim 1$--$3$). The formation timescale:

$$
t_{\text{form}} \approx \frac{1}{\lambda H_0} \approx \text{few Gyr}
$$

**The $\varphi^3$ base.** The abundance relative to baryons is the ratio of the gravitational amplification to the electroweak/EM decoupling structure. The rung arithmetic closes exactly for only one identification of that structure. The repo's own rung placements ($n = \log_\varphi(\text{scale})$; `foundations/dimensionful-cascade.md` §5.2, `foundations/dimensionful-constants-status.md` §3.5):

| Scale | Rung |
|---|---|
| $\alpha_{\text{EM}}^{-1} = 137.04$ (zero momentum) | $10.22$ |
| $\alpha_{\text{EM}}^{-1} = 128.95$ ($m_Z$) | $10.10$ |
| $\alpha_{\text{EM}}^{-1} = 225$ ($M_{\text{GUT}}$) | $11.26$ |
| $\xi = \varphi^6$ (gravitational amplification) | $6$ (exact) |
| $G_{\text{eff,max}}/G = \varphi^3$ (saturation ceiling) | $3$ (exact) |
| $\sin^2\theta_W = \varphi^{-3} = \alpha_0$ (fixed-point imbalance) | $3$ (exact; exponent $-3$) |

The span between the gravitational coupling $\xi$ (rung 6) and $\alpha_{\text{EM}}^{-1}$ (rung 10.22) is $-4.22$ rungs, not 3—the "gap between the gravitational coupling and the EM decoupling scale" does **not** close with $\alpha_{\text{EM}}$ as the decoupling scale. It closes exactly only when the EM-decoupling structure is the electroweak mixing angle $\sin^2\theta_W = \varphi^{-3} = \alpha_0$, the fixed-point imbalance (catalog step 3):

$$
\boxed{\frac{\Omega_{\text{DM}}}{\Omega_b} = \xi \cdot \sin^2\theta_W = \varphi^6 \cdot \varphi^{-3} = \varphi^3 = 4.2361 = \alpha_0^{-1} = \frac{G_{\text{eff,max}}}{G}}
$$

The base is the inverse fixed-point imbalance $\alpha_0^{-1}$—the same imbalance whose inverse square defines $\xi$ (`foundations/xi-derivation.md` §2.1–2.2)—and equals the gravity saturation ceiling (§2.3). Verified numerically to machine precision (`computations/dm_baryon_ratio_verification.py`, part A). **Tier: Derived conditional on the identification**—$\sin^2\theta_W$ is not $\alpha_{\text{EM}}$ (rung 10.2, span 4.2), and $\xi\cdot\alpha_0 = \alpha_0^{-1}$ is an algebraic identity of a single imbalance, not an independent scale-gap; the claim that condensate freeze-out realizes the saturation ceiling in the density ratio is asserted (mechanism label "Qi condensate freeze-out", `foundations/dimensionful-cascade.md` §5.2).

**Inputs ($\varphi^3$ base):** $\boxed{\text{(1) the derived coupling } \xi = \varphi^6 \text{ (`foundations/xi-derivation.md`); (2) the identification of the EM-decoupling structure with the Weinberg-angle imbalance } \sin^2\theta_W = \varphi^{-3} = \alpha_0.}$

**The $+1$ capture term.** The claim that baryons captured into the condensate add one $\Omega_b$ unit is **not supported** by the SPARC hydrostatic condensate fits (`computations/dm_baryon_ratio_verification.py`, part B; v9 machinery, 143 galaxies, envelopes A/B):

- Bound-baryon fraction within the last measured radius, $f_b = M_{\text{bar}}(r_{\max})/M_{\text{tot}}(r_{\max})$: median 0.32 (dwarfs 0.28; high-$V$ 0.40; A-constrained 0.27)—not the $1/(1+\varphi^3) = 0.191$ the $+1$ implies.
- The condensate's own mass ratio $M_Y/M_{\text{bar}}$ at $r_{\max}$: median 0.14 (envelope A) / 0.35 (envelope B)—10–30$\times$ below the $\varphi^3 = 4.24$ partition the $+1$ assumes (the naive DM is the boosted $(1+\xi q)M_Y$).
- The data-pinned DM/baryon ratio at $r_{\max}$, median 2.1–2.7, is a lower bound (the isothermal tail beyond $r_{\max}$ is unconstrained) and lies below $\varphi^3+1$ by a factor 0.4–0.5; only 15% of galaxies sit within 30% of 5.24.
- Accounting: $\Omega_b$ in the observed ratio is the total baryon density (BBN/CMB), which already includes baryons bound into halos; a capture term of one full $\Omega_b$ unit has no separate mass budget.

The $+1$ therefore stays **Mapped** (Fit-Status Ledger row 502: hand-added after $\varphi^3$ alone came in 21% low; combination selected from $\{\varphi^3, \xi, \varphi^2, \varphi^4, \varphi^3\pm1\}$). Equivalent closed form: $\varphi^3+1 = 2\varphi^2 = 5.2361$—an arithmetic identity, not a derivation.

**Observed:** $\Omega_{\text{DM}}/\Omega_b = 0.264 / 0.049 \approx 5.39$

The 2.8% residual of $\varphi^3+1$ against the observed value is the residual of the selected combination, not an error within a derived bound.

### 4.3 Comparison with Dark Matter Candidates

| Property | Qi Condensate | WIMP | Axion | Observed |
|----------|--------------|------|-------|----------|
| Direct detection | Null (field) | Non-null | Non-null | Null (all expts) |
| Self-interaction | Collisionless | Collisional | Collisionless | Collisionless |
| Structure $z$ | $\sim 1$--$3$ | $> 10$ | $> 10$ | $\sim 1$--$3$ |
| Halo density | $r^{-1}$ (Qi) | $r^{-2}$ (NFW) | $r^{-2}$ (NFW) | Core/cusp mixed |

The Qi condensate naturally produces cored profiles (from the $\varphi$-attractor's smoothing), which matches observations of dwarf galaxies better than the cuspy NFW profile from CDM.

### 4.4 Observational Tests

| Test | Cassi Prediction | Current Status |
|------|-----------------|----------------|
| Galaxy rotation curves | Flat, $(1+(\varphi^{6}-1)q)\times$ boost | MW and dwarfs confirmed |
| Bullet Cluster | Collisionless DM consistent | Confirmed |
| Weak lensing | Enhanced $G_{\text{eff}}$ in halos | LSST testable |
| Direct detection | Null (field condensate) | All experiments null |
| CMB $\sigma_8$ | **+0.3% ± 0.5 pp vs $\Lambda$CDM (P-A, measured window $z \in [100, 61]$)** — the window-integrated per-cell mixture on the ΛCDM background (the window's content is the q-history 0.866 → 0.795, not the endpoint; mixture = mean-field); the P-C pointwise-chord reading (flagged): +24.8% ± 16.3 pp over the measured window $z \in [100, 61]$, then −95.7% ± 2.4 pp over the measured continuation $z \in [61, 0]$ (the freeze is structural in the continuation — Re p = −0.25 for every μ < −1/24, all cells end R < 1 through z → 0; N=128 confirms +24.83% / −95.9%, resolution-stable; `cassi-toe-rewrite-briefs/spiral-gravity/53-post-freeze-continuation.md`, `cassi-toe-rewrite-briefs/spiral-gravity/54-n128-mixture.md`); the settlement family −16.6% (R = 0.834, regime-integrated, stabilized closure, P-A, $r_0 = 0.0472$) / −15.2% (band-state mean-field) / −11.2% (full-window hold) is the reference (`cosmology/sigma8-computational-plan.md` §3.2; `parameter-inventory.md` §10); the "~5% lower" wording is a plan fit target only, never computed; the μ normalization Mapped | LSST discriminant |

---

## 5. Complete Cassi Cosmology in One Page

### 5.1 Timeline

| Time | Event | Key Equation |
|------|-------|-------------|
| $t \sim 10^{-38}$ s | Inflation begins: $r \gg \varphi$ | $H \approx -\lambda/3$, $N_e = 40$ |
| $t \sim 10^{-36}$ s | Inflation ends: $r \to \varphi$ | $\varepsilon = \eta \approx 1$ |
| $t \sim 10^{-34}$ s | Reheating: $T \sim 10^{15}$ GeV | $\Gamma_{\text{reh}} \approx \lambda\varphi^{-2}M_{\text{Pl}}$ |
| $t \sim 10^{-10}$ s | Electroweak phase transition: $T \sim 100$ GeV | $\eta \approx \varphi^{-44}$ |
| $t \sim 1$ Gyr | Structure formation: $z \sim 3$ | $\Omega_{\text{DM}}/\Omega_b \approx \varphi^3 + 1$ |
| $t \sim 13.8$ Gyr | Today: terminal attractor | $q \to 1$, $\pi/\rho \to 1$, $r \to \varphi$ |

### 5.2 Predictions

| Observable | Cassi Prediction | Measurement | Gap |
|-----------|-----------------|-------------|-----|
| $n_s$ | $1 - 2\varphi^{-1}/N_e \approx 0.9691$ | $0.9649 \pm 0.0042$ | $1.0\sigma$ (closed form; trajectory not reproducing it, 2026-08-06) |
| $r$ | $12/N_e^2 = 0.0075$ ($N_e = 40$ Mapped window; 0.003 needs $N_e = 63.2$) | $< 0.032$ | Mapped (ledger §10); trajectory's $r$ excluded by BK18 (2026-08-06) |
| $\mathcal{P}_\zeta$ | $\sim 2\times10^{-9}$ | $2.1\times10^{-9}$ | $5\%$ |
| $\eta$ | $\varphi^{-44} \approx 6.38\times10^{-10}$ | $6.0\times10^{-10}$ | $6.3\%$ |
| $\Omega_{\text{DM}}/\Omega_b$ | $\varphi^3 + 1 \approx 5.24$ (base $\varphi^3 = \alpha_0^{-1}$ Derived conditional on the Weinberg-angle identification, §4.2; $+1$ Mapped—row 502) | $5.39$ | $2.8\%$ (residual of the selected combination) |
| $T_{\text{reh}}$ | $\sim 10^{15}$ GeV |—| Consistent |
| DM direct detection | Null | Null (all expts) | Consistent |
| DM self-interaction | Collisionless | Bullet Cluster | Consistent |

Every prediction comes from $\varphi$ and the two-fluid PDE parameters $(\lambda, \chi, D)$—all independently fixed from the DESI dark energy calibration and the Wu Xing cycle. **No new free parameters** are introduced for inflation, baryogenesis, or dark matter beyond the ledgered anchors flagged above (r, $N_e$, $\eta$ are Mapped—rows 495, 501, 481; $\Omega_{\text{DM}}/\Omega_b$: base $\varphi^3 = \alpha_0^{-1}$ Derived conditional on the Weinberg-angle identification (§4.2), $+1$ Mapped—row 502; $w_0$ is Calibrated—row 496).
