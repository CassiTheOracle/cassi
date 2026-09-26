# Sigma-8 Computational Plan: Modified Boltzmann Pipeline for Cassi Qi-Gravity

## Status: Plan—August 2026

## Abstract

This document is the computational plan for promoting the Cassi $\sigma_8$ prediction from Hypothesized to Derived. The mechanism is the density-dependent Qi-gravity coupling $G_{\text{eff}} = (\pi/\rho)(1+(\varphi^{6}-1)q_{\mathrm{solver}})G_N$ with $\xi = \varphi^6$: voids may see near-Newtonian gravity while filament and halo regions see an enhanced $G_{\text{eff}}$; the stabilized closure's full regime-integrated computation gives a $\approx16\%$ late-time suppression (§3.2), while the observed deficit is $\approx5\%$. The $\mu$ normalization is Mapped; the plan's "target" rows are fit targets, not computations. The geometric condensation fields $C$ and $B$ enter only through the separate, Hypothesized/open proxy-to-$q_{\mathrm{solver}}$ map in §2.2. The truth campaign (2026-08-07, `runs/44-truth-campaign/`) measured the pipeline's rows at the doctrine IC with the linear-P(k) normalization (pk_norm $\equiv 1$): the total **−22.9%** at the D = 0 re-measurement (2026-08-08, brief 63; the totals carry the diffusion — at the campaign's D = 0.001 the same row is −20.5%, resolution-converged N = 32/64/128; $\sigma_8{}_\Lambda$ 0.9917 vs $\sigma_8{}_\mathrm{Cassi}$ 0.7649/0.7884 at $a_f = 1.80$; see §3.2); those are pipeline outcomes, not a completed cosmological prediction.

The displayed $G_{\text{eff}}$ is a coupling magnitude. The canonical
$+\pi[1+(\varphi^6-1)q]\nabla\Phi$ force is outward for positive $\pi$; the
attractive sign used by the Boltzmann growth equation is a separate
Hypothesized sign-changing branch.

---

## 1. Objective

Compute $\sigma_8(z)$ from the Cassi two-fluid framework by integrating the density-dependent Qi-gravity modification into a Boltzmann code; the modification uses canonical local $q_{\mathrm{solver}}$ and requires a validated scale-dependent $q_{\mathrm{eff}}(k,a)$. The current epistemic status is **Hypothesized** (qualitative match; quantitative computation pending). The truth campaign (2026-08-07, `runs/44-truth-campaign/`) measured the pipeline's rows at the doctrine IC with the linear-P(k) normalization (pk_norm ≡ 1): the total **−22.9%** at the D = 0 re-measurement (2026-08-08, brief 63; the totals carry the diffusion — at the campaign's D = 0.001 the same row is −20.5%, resolution-converged N = 32/64/128; σ₈_ΛCDM 0.9917 vs σ₈_Cassi 0.7649/0.7884 at a_f = 1.80) and the mechanism-attributable **+29.7%** (D-insensitive, Δμ 0.02 pp; $G_{\text{eff}} = 1.297$ — the deep-Yin window's $q_{\mathrm{solver}}$ rises 0.30 → 0.41, growth enhancement; r₀-dependent: +29.4% at the derived $r_0 = 0.0472$); the doctrine (2026-08-07) replaces the "~5%" target with the computed rows: −16.6% (closure, regime-integrated, R = 0.834) and −15.2% (band-state mean-field) under the P-A relative-μ reading at the derived $r_0 = 0.0472$ (§3.2); the μ normalization remains Mapped. Reaching **Derived** requires a resolution- and normalization-controlled computation that isolates the mechanism contribution.

---

## 2. The Core Mechanism

### 2.1 Qi-Gravity Enhancement Formula

The $G_{\text{eff}}$ equation uses the canonical two-fluid coherence, not a geometric condensation field:

$$\boxed{G_{\text{eff}}(x) = \frac{\pi(x)}{\rho(x)}\left(1 + (\varphi^{6}-1)q_{\mathrm{solver}}(x)\right) G_N, \qquad \xi = \varphi^6 \approx 17.944}$$

where:
- $q_{\mathrm{solver}} \in [0, 1]$ is the canonical local coherence computed from the two-fluid densities, with
  $$q_{\mathrm{solver}} = \frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2}, \qquad \rho = E_Y+E_I,\qquad \varepsilon = E_Y-\varphi E_I.$$
  This is the quantity implemented by `two-fluid/run_sigma8_pipeline.py` and by the canonical single-gate path in `two-fluid/cassi_two_fluid_3d_gpu.py`.
- $\pi/\rho$ is the fractional density imbalance from the two-fluid projection onto 3D space; at the $\varphi$-fixed point it is the imbalance $\alpha_0 = (\varphi-1)/(\varphi+1) = \varphi^{-3} \approx 0.236$, while the Yang component fraction is $E_Y/\rho=\varphi^{-1}$
- $\xi = \varphi^6$ is the **derived** coupling (imbalance inverse-square $\xi = (\pi/\rho)^{-2}$, `foundations/xi-derivation.md` §2; "cascade activation at step 6" is a shorthand rung label, not a derivation)

### 2.2 Geometric Condensation Proxies and Canonical $q_{\mathrm{solver}}$

The large-scale condensation field is a geometric coordinate, not the canonical solver coherence. The source geometry defines the transverse interference field

$$C(x,y) = \cos\!\left(\frac{2\pi x}{\Lambda_Y}\right)\cos\!\left(\frac{2\pi y}{\Lambda_I}\right), \qquad \Lambda_Y = \varphi\,\Lambda_I,\qquad C \in [-1,1]$$

in `foundations/bubble-edge-geometry.md`. Its 3D extension is

$$B(x,y,z) = C(x,y)\cos(\gamma_n z), \qquad B \in [-1,1]$$

in `foundations/bubble-lattice-fabric.md`; $B$ and $C$ therefore share the transverse factor, with $B=C$ only where $\cos(\gamma_n z)=1$, and are not identical fields for general $z$. For this computational plan, the geometric condensation proxy is the explicit squared ansatz

$$q_{\mathrm{proxy}}^{C}(x,y) \equiv \frac{(1+C(x,y))^2}{2}, \qquad 0 \leq q_{\mathrm{proxy}}^{C} \leq 2,$$

with $q_{\mathrm{proxy}}^{C}=0$ at $C=-1$, $q_{\mathrm{proxy}}^{C}=1/2$ at $C=0$, and $q_{\mathrm{proxy}}^{C}=2$ at $C=1$. If the 3D field is used instead, the corresponding geometric quantity is

$$q_{\mathrm{proxy}}^{B}(x,y,z) \equiv \frac{(1+B(x,y,z))^2}{2}, \qquad 0 \leq q_{\mathrm{proxy}}^{B} \leq 2.$$

These are unnormalized geometric proxies, not bounded coherence variables. The linear interpolation $(1+C)/2\in[0,1]$ is a distinct normalized geometric candidate and is not silently identified with the squared ansatz. No derivation in the canonical two-fluid equations turns either geometric field into $q_{\mathrm{solver}}$.

The density trace associated with the geometric field is a separate conditional profile:

$$\rho_{\mathrm{proxy}}(C) \approx \rho_0 \cdot \max\!\left(0,\; \frac{C - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)^{\!\nu},\qquad \nu \in [1, 2].$$

It is not the canonical $\rho=E_Y+E_I$ until a separate density constitutive map is measured or derived. The only permitted route from the geometric construction to gravity is therefore the conditional mapping

$$q_{\mathrm{solver}}=\mathcal{M}_{\mathrm{proxy}\to q}\!\left(q_{\mathrm{proxy}}^{C/B}\right)\in[0,1]\;\Longrightarrow\;G_{\mathrm{eff}} \text{ through the boxed equation above}.$$

The map $q_{\mathrm{proxy}}\to q_{\mathrm{solver}}\to G_{\mathrm{eff}}$ is **Hypothesized/open**; its required bounded constitutive map has domain $\mathcal{M}_{\mathrm{proxy}\to q}:[0,2]\to[0,1]$. The displayed geometric ansatz does not supply that map, and a geometric proxy must not be fed directly into the growth equation, the canonical conversion gate, or $G_{\mathrm{eff}}$.

**Two noncanonical proxy parameterizations—scale labels:** A second density-only halo expression appears in `foundations/phi_attractor_synthesis.md`:
$q_{\mathrm{halo,proxy}} = 1/(1 + (\rho/\rho_{\text{ref}})^2)$, which gives $q_{\mathrm{halo,proxy}} \to 1$ at low density and $q_{\mathrm{halo,proxy}} \to 0$ at high density. These are application-scale proxies, not alternate definitions of $q_{\mathrm{solver}}$:

| Parameterization | Context | Domain | Proxy in high-$\rho$ | Proxy in low-$\rho$ |
|-----------------|---------|--------|----------------------|---------------------|
| $q_{\mathrm{proxy}}^{C} = (1+C)^2/2$ | Cosmological LSS, $\sigma_8$ | Transverse condensation field on Gpc/Mpc scales | Clusters: $C>0,\;q_{\mathrm{proxy}}^{C}>0.5$ (up to 2) | Voids: $C<0,\;q_{\mathrm{proxy}}^{C}<0.5$ (down to 0) |
| $q_{\mathrm{halo,proxy}} = 1/(1+(\rho/\rho_{\text{ref}})^2)$ | Galaxy halo radial profile | Scale of individual virialized halos | Core: $\rho\gg\rho_{\text{ref}},\;q_{\mathrm{halo,proxy}}\to 0$ | Outskirts: $\rho\ll\rho_{\text{ref}},\;q_{\mathrm{halo,proxy}}\to 1$ |

When the PDE supplies $E_Y,E_I$, the pipeline computes $q_{\mathrm{solver}}(x)$ directly from the canonical formula above. That measurement neither validates nor replaces the geometric proxy. If only $C$ or $B$ is available, the proxy-to-$q_{\mathrm{solver}}$ map remains an open constitutive input.

### 2.3 Three Regimes of $G_{\text{eff}}$ (Cosmological Context)

| Regime | Density | $C$ (transverse geometry) | $q_{\mathrm{proxy}}^{C}$ (geometric) | $q_{\mathrm{solver}}$ (canonical) | $\pi/\rho$ | $G_{\text{eff}}/G_N$ (conditional magnitude) |
|--------|---------|---------------------------|--------------------------------------|------------------------------------|------------|-------------------------------------|
| Cluster core | Very high | $\to 1$ | $\to 2$ | Must be measured; not set by the proxy | $\to 0$ | No magnitude follows from the geometric proxy; evaluate the local $(\pi/\rho,q_{\mathrm{solver}})$ state |
| Filament / halo outskirts | Moderate | $\sim 0.45$ | $\sim 1.05$ | Must be measured; not set by the proxy | $\sim 0.6$ | No fixed range follows from the proxy; evaluate the local $(\pi/\rho,q_{\mathrm{solver}})$ state |
| Void | Low | $\to -1$ | $\to 0$ | Must be measured; not set by the proxy | $\to 1$ | $\to 1$ only when the local state independently gives $q_{\mathrm{solver}}\to0$ and $\pi/\rho\to1$ |

These rows are conditional regime descriptions, not a global bound. On the fixed-composition $\varphi$-attractor branch, holding $\pi/\rho=\varphi^{-3}$ while density carries $q_{\mathrm{solver}}$ from the dilute limit toward $1$ gives the branch-specific range $\varphi^{-3}\to\varphi^3$; off that branch, the coupled local $(\pi/\rho,q_{\mathrm{solver}})$ state requires its own constitutive domain.

The $\sigma_8$ tension arises because low-density regions (voids, filament edges) may have $G_{\text{eff}} \approx G_N$ under the measured canonical $q_{\mathrm{solver}}$ and density, while early-universe structure formation assumed $\Lambda$CDM with $G_{\text{eff}} = G_N$ everywhere. The scale dependence enters because different Fourier modes $k$ sample different distributions of $q_{\mathrm{solver}}$, and $\sigma_8$ at $R = 8\,h^{-1}$Mpc averages over the filament-void network.

### 2.4 $q_{\mathrm{solver}}$ Evolution with Redshift

The pipeline simulation at the operational $r_0 = 1/23$ (the doctrine IC; the non-doctrinal orphan is $r_0 = 1/3$, 27 §2) shows the cosmic-mean canonical $q_{\mathrm{solver}}$ **increasing** with time from a deep-Yin start (truth campaign 2026-08-07, N = 128):

- $q_{\mathrm{solver}} \approx 0.30$ at $a = 1.0$ ($z \approx 0$; pipeline IC)
- $q_{\mathrm{solver}} \approx 0.41$ at $a = 1.80$ (pipeline endpoint)

These are the doctrine-IC pipeline values: the operational $r_0 = 1/23$ and the derived $r_0 = 0.0472$ are indistinguishable for $\sigma_8$ (0.3 pp at N = 128 — 27 §2.2, verified 2026-08-07); the pipeline's run window is mid-relaxation—the stabilized closure's attractor ($q_{\mathrm{solver}} = 0.79$ at $r_* = 0.9503$; `cassi-psychology.md` §12) is the framework's settled state, reached beyond the pipeline's window, with a different $\mu$ history (the computed rows of §3.2). The $q_{\mathrm{solver}}(z)$ evolution is the key input to the $\sigma_8$ pipeline: if $q_{\mathrm{solver}}$ were constant, there would be no $\sigma_8$ shift since $\mu(k,a)$ would be time-independent and absorbed into the normalization.

At very early times ($z > 1000$, prior to recombination), the universe is nearly homogeneous and $C \approx 0$, so the explicit geometric plan ansatz gives $q_{\mathrm{proxy}}^{C} \approx 0.5$. This does not determine $q_{\mathrm{solver}}$. The PDE's canonical $q_{\mathrm{solver}}(z)$ shows values above 0.5 in the early post-inflation era; a pure-Yang composition ($r \gg \varphi$) does not by itself imply $q_{\mathrm{solver}}\to1$, because that limit requires $\varepsilon\to0$ together with high density. The pipeline should use PDE-extracted $q_{\mathrm{solver}}(z)$ directly for all epochs; a $C$- or $B$-based proxy requires the open constitutive map in §2.2.

---

## 3. Analytic Estimate (without Boltzmann Code)

### 3.1 Modified Growth Equation

In the linear regime, the matter overdensity $\delta_m(k, a)$ satisfies:

$$\delta_m'' + \left(2 + \frac{H'}{H}\right)\delta_m' - \frac{3}{2}\,\Omega_m(a)\,\mu(k, a)\,\delta_m = 0$$

where $\mu(k, a) = G_{\text{eff}}(k, a)/G_N$ and primes denote $d/d\ln a$.
The minus sign in this growth equation is the standard attractive-growth
branch. The canonical PDE force convention has the opposite outward sign for
positive $\pi$, so this cosmological growth path remains conditional on the
separate Hypothesized sign-changing extension.

For $\Lambda$CDM ($\mu = 1$), the growth factor is $D(a) \propto a$ in EdS; in $\Lambda$CDM the growth rate is approximated by $f=d\ln D/d\ln a \approx \Omega_m(a)^{0.55}$, so $D(a)$ is not generally a single power law.

For Cassi ($\mu\neq1$), the growth response follows the measured $q_{\mathrm{solver}}(a)$ through $\mu(k,a)$. In this doctrine run, both $q_{\mathrm{solver}}$ and $\mu$ increase over the simulated window; there is no generic early-enhanced/late-suppressed rule. The total $\sigma_8$ outcome also includes diffusion and other pipeline terms, so it cannot be inferred from the $q_{\mathrm{solver}}$ trend alone.

### 3.2 Effective $\mu$ from the Pipeline

The PDE pipeline (`two-fluid/run_sigma8_pipeline.py`) at the operational $r_0 = 1/23$ with the linear-P(k) IC normalization (the truth campaign 2026-08-07, N = 32/64/128) gives:

- $q_{\mathrm{solver,initial}} = 0.300$, $q_{\mathrm{solver,final}} = 0.405$ (spatial mean, N = 128)
- $G_{\text{eff}}/G_{\text{ref}} = 1.297$ (the deep-Yin window's $q_{\mathrm{solver}}$ rises — the mechanism-attributable row +29.7%; r₀-dependent: +29.4% at the derived $r_0 = 0.0472$)
- the measured total $\Delta\sigma_8 = -22.9\%$ at the D = 0 re-measurement (2026-08-08, brief 63; σ₈_Cassi 0.7649); at the campaign's D = 0.001 the same row is **−20.5%** (resolution-converged; σ₈_ΛCDM 0.9917 vs σ₈_Cassi 0.7884 at a_f = 1.80) — the totals carry the diffusion

The mechanism row is resolution-converged to 0.1 pp across N ∈ {32, 64, 128}; the framework's computed $\sigma_8$ rows are the band-state mean-field and the regime-integrated closure below.

In the matter-dominated era where $D \propto a^p$ with $p = \frac{-1 + \sqrt{1 + 24\mu}}{4}$ for $\mu = G_{\text{eff}}/G_N$:

| $\mu$ (constant approximation) | $p$ | $D(z=0)/D(z=100)$ | $\sigma_8$ ratio vs. $\Lambda$CDM | Suppression |
|-------|-----|-------------------|----------------------------------|-------------|
| 1.000 ($\Lambda$CDM) | 1.000 | 101.0 | 1.000 |—|
| 1.297 (pipeline spatial-mean $\mu$, doctrine $r_0 = 1/23$, N=128 campaign) | 1.167 | 218.3 | 2.162 | **+116.2%** |
| 0.950 (estimated effective $\mu$) | 0.970 | 87.4 | 0.865 | **-13.5%** |
| 0.980 (target, matching observations) | 0.989 | 95.7 | 0.947 | **-5.3%** |

The 0.950/0.980 rows are estimated/target rows—**NOT predictions**; the computed rows: $\mu = 1.297 \to +116.2\%$ (the EdS power-law reading of the pipeline's measured spatial-mean $\mu$ at the doctrine $r_0 = 1/23$ — the campaign's μ-only statistic, the reconciliation's row σ₈(P·G_eff²) = G_eff·σ₈(P), is +29.7%; the EdS power law overstates sign-changing μ histories, 45), $\mu = 0.9414 \to -15.2\%$ (band-state mean-field), and the regime-integrated closure **−16.6% (R = 0.834)** under the P-A relative-μ reading at the derived $r_0 = 0.0472$; the measured total (density field vs ΛCDM linear growth) is **−22.9%** at D = 0 (brief 63) and **−20.5%** at the campaign's D = 0.001 (resolution-converged N=32/64/128, linear-P(k) IC normalization; the totals carry the diffusion); the $\mu = 0.980$ row is a fit target, not a computation.

**The $\mu = 0.98$ row is a fit target, not a computation**—no framework computation yields $\mu = 0.98$; the stabilized closure's window mean is $\mu \approx 0.94$, whose regime-integrated growth gives −16.6% (R = 0.834, §3.2). The observed weak-lensing deficit is ≈5%; the "~5%" σ8 wording conflated that deficit with a prediction. The measured rows (2026-08-07 truth campaign, linear-P(k) IC normalization, N = 32/64/128; D-pin re-measurement 2026-08-08, brief 63): the total **−22.9%** (D = 0, the doctrine default) / **−20.5%** (D = 0.001 campaign — the totals carry the diffusion) and the mechanism-attributable **+29.7%** (D-insensitive; $G_{\text{eff}} = 1.297$ — the doctrine r₀'s deep-Yin window $q_{\mathrm{solver}}$ rises 0.30 → 0.41; r₀-dependent: +29.4% at the derived r₀ = 0.0472); the ~5% number enters through the chosen μ, it does not emerge from the dynamics.

### 3.3 What the Measured Total Is

The pipeline's measured total is **−22.9%** at the D = 0 re-measurement (2026-08-08, brief 63, N=128, the doctrine default; σ₈_Cassi 0.7649) and **−20.5%** at the campaign's D = 0.001 (resolution-converged at N = 32/64/128 with the linear-P(k) IC normalization) — the totals carry the diffusion (Δ 2.37 pp). Both are the sum of the mechanism row (+29.7%, D-insensitive: the deep-Yin window's rising $q_{\mathrm{solver}}$ enhances growth) and the box's own growth deficit (at D = 0.001 δ_rms falls 15.7% at N=128 while ΛCDM linear growth rises +24% — the density fluctuations fail to grow by the linear factor; at D = 0 δ_rms rises +64.1% — the un-damped high-k content grows — while the σ₈-window power is still suppressed relative to ΛCDM linear growth; the expanding-box dynamics' H-drag/force saturation, a regime/transport property of the machinery, not a resolution artifact). The structural notes:

1. **Scale-independent $q_{\mathrm{solver}}$:** The mechanism row uses the spatial mean of the canonical $q_{\mathrm{solver}}$ across all modes. On $\sigma_8$ scales ($R = 8\,h^{-1}$Mpc, $k \sim 0.1$–$1\,h$/Mpc), the volume is dominated by the filament-void network where $q_{\mathrm{solver}}$ is closer to the mean field value, not the extreme core value.

2. **Resolution:** The mechanism row is converged to 0.1 pp across N ∈ {32, 64, 128}; the absolute σ₈ levels are convention-dependent (the linear-P(k) integral is the convention), the percentage ratios are convention-robust.

3. **Run window ($a_{\text{final}} = 1.80$):** The window is mid-relaxation—$q_{\mathrm{solver}}$ rises 0.30 → 0.41, the attractor's 0.79 not reached in the pipeline's $t = 1.5$ window—so +29.7% is the pipeline's run-window reading; the full z-window integration is 20/27's machinery, fed by the converged N=128 $\mu(t)$ histories.

### 3.4 Why the Suppression is Scale-Dependent

The suppression is **not uniform** across $k$ because:

- **Large scales ($k \ll k_Y \sim 0.03\,h$/Mpc):** These modes average over many bubbles. The effective $q_{\mathrm{solver}}$ is the cosmic-mean canonical value, giving $\mu(k)$ close to the mean value. A separately **Hypothesized** scale-dependent $q_{\mathrm{solver}}(k,a)$ trajectory with high $q_{\mathrm{solver}}$ at early times and low $q_{\mathrm{solver}}$ at late times could enhance then suppress growth, with partial cancellation; this is not the trajectory measured by the doctrine run, where $q_{\mathrm{solver}}$ and $\mu$ rise over the simulated window.

- **Intermediate scales ($k \sim 0.1$–$1\,h$/Mpc, $\sigma_8$ range):** These modes sample within individual bubbles. The canonical $q_{\mathrm{solver}}$ distribution is bimodal—high $q_{\mathrm{solver}}$ in condensing regions, low $q_{\mathrm{solver}}$ in voids. The volume-weighted mean $q_{\mathrm{solver}}$ determines $\mu_{\text{eff}}$, giving a net suppression. A geometric $q_{\mathrm{proxy}}^{C/B}$ distribution cannot be used here without the open constitutive map in §2.2.

- **Small scales ($k \gg 1\,h$/Mpc):** These modes are inside virialized halos where $q_{\mathrm{solver}}$ is determined by local dynamics. The $q_{\mathrm{solver}}$ is higher, so $G_{\mathrm{eff}}$ is enhanced—but this enters the nonlinear regime where perturbation theory breaks down and N-body is needed.

The net effect on $\sigma_8$ is the integral over all $k$ with the top-hat window $W(kR)$, where $R = 8\,h^{-1}$Mpc. The $k$-dependence of $\mu(k, a)$ is what the Boltzmann code must compute.

### 3.5 Refined Analytic Estimate

Using $q_{\mathrm{solver}}(z)$ from the PDE and integrating the growth equation numerically with $\mu(k,a) = (\pi/\rho(a))(1 + (\varphi^{6}-1)q_{\mathrm{solver}}(a))$, parameterizing the $k$-dependence as a smooth transition between void ($k$ small, $q_{\mathrm{solver}} \to 0$) and cluster ($k$ large, $q_{\mathrm{solver}} \to \langle q_{\mathrm{solver}}\rangle$) regimes, the estimated suppression is:

$$\boxed{\frac{\sigma_8^{\text{Cassi}}}{\sigma_8^{\Lambda\text{CDM}}} \approx 0.90\text{--}0.95 \quad \Rightarrow \quad \Delta\sigma_8/\sigma_8 \approx -5\%\text{ to }-10\%}$$

This boxed band is an estimate, not a computation—the computed values are the regime-integrated −16.6% (R = 0.834, §3.2), the band-state mean-field −15.2%, and the pipeline's measured rows (2026-08-07 truth campaign, linear-P(k) IC normalization; D-pin re-measurement 2026-08-08, brief 63): the total **−22.9%** (D = 0) / **−20.5%** (D = 0.001 — the totals carry the diffusion) and the mechanism-attributable **+29.7%** (D-insensitive; $G_{\text{eff}} = 1.297$, doctrine r₀, resolution-converged N=64/128). The band above is a Mapped target, not a measured suppression.

This matches:
- The computed $\sigma_8$ values of §3.2: −16.6% (R = 0.834, regime-integrated), −15.2% (band-state mean-field), −20.5%/−22.9% (the pipeline's measured total at D = 0.001/D = 0)
- The observed Planck vs. weak-lensing tension ($\sim 5\text{–}9\%$)
- The $f\sigma_8$ suppression seen in BOSS/eBOSS at $z \lesssim 0.5$ ($\sim 1\sigma$)

**To go from this estimate to a Derived prediction requires the full $k$-dependent $\mu(k,a)$ from the PDE-integrated Boltzmann pipeline.**

---

## 4. Computational Pipeline

### 4.1 Overview

```
PDE Simulation       q_eff(k,z) Estimator (open)   Boltzmann Solver         Sigma8
(q_solver(x,t); C/B   --> (cross/auto spectra) --> (validated bounded q_eff) --> (modified CLASS) --> (σ₈(z))
 optional diagnostic)
     |                         |                       |
     |-- q_solver(x) at each a |-- S_qρ(k), S_ρρ(k)   |-- μ(k,a) = (π/ρ)(1+(φ⁶−1)q_eff(k,a))
     |-- ρ(x) at each a        |-- shell/bin + checks   |-- Poisson: k²Φ = -4πG·μ·a²ρδ
     |-- C/B kept separate     |-- threshold/regularize |-- Modified growth + C_ℓ
     |-- resolution N≥64       |                         |
```

The PDE supplies the canonical $q_{\mathrm{solver}}(x,a)\in[0,1]$ computed from $E_Y,E_I$. A scale-dependent $q_{\mathrm{eff}}(k,a)$ is a derived effective quantity, not a Fourier coefficient and not automatically bounded. It may enter the growth equation or CLASS only after a shell/bin estimator, denominator threshold or regularization, and validation establish a bounded $q_{\mathrm{eff}}\in[0,1]$. The geometric $C$/$B$ proxies are optional diagnostics and are not substituted into this path. If a run supplies only a geometric proxy, the separate $\mathcal{M}_{\mathrm{proxy}\to q}$ map in §2.2 must be measured or derived before any bounded effective table can be constructed; that constitutive step is Hypothesized/open.

### 4.2 Step 1: High-Resolution PDE Simulation

**What:** Run `two-fluid/cassi_two_fluid_3d_gpu.py` at $N=64$ or $N=128$ with cosmological ICs.

**Parameters:**
- Grid: $N=64$ minimum, $N=128$ target (GPU), $N=32$ minimum (CPU)
- ICs: Eisenstein-Hu transfer function at $z=100$ ($a=0.01$)
- Box size: $L = 256\,h^{-1}$Mpc (to capture $\sigma_8$ scales $k \sim 0.1$–$1\,h$/Mpc)
- Duration: $a_{\text{init}} = 0.01$ to $a_{\text{final}} = 1.0$ ($z=0$)
- Output: canonical $q_{\mathrm{solver}}(x, a)$, density $\rho(x, a)$, and optional geometric $C/B$ diagnostics at $N_a \sim 50$ snapshots

**Outputs:**
- `q_solver_grid_{a}.npy`: canonical $q_{\mathrm{solver}}(x)$ at each scale factor
- `rho_grid_{a}.npy`: canonical $\rho(x)$ at each scale factor
- `q_proxy_grid_{a}.npy` (optional): geometric $q_{\mathrm{proxy}}^{C/B}$, never a replacement for the canonical grid

### 4.3 Step 2: Scale-Dependent Effective-Coherence Estimator (Open)

**What:** Construct a scale-dependent $q_{\mathrm{eff}}(k,z)$ candidate from the canonical real-space $q_{\mathrm{solver}}(x,z)$ and $\rho(x,z)$. A Fourier coefficient of the bounded local field is not itself a bounded canonical coherence.

**Illustrative cross-spectrum diagnostic, not a production estimator:**
```python
def form_qrho_cross_spectra(q_solver_grid, rho_grid, box_size):
    """
    Form diagnostic density-weighted cross/auto spectra.

    The returned shell diagnostics are not q_eff(k) and must not be
    passed directly to the growth equation or CLASS.
    """
    qrho_k = np.fft.rfftn(q_solver_grid * rho_grid)
    rho_k = np.fft.rfftn(rho_grid)
    cross_qrho = qrho_k * np.conj(rho_k)
    auto_rho = rho_k * np.conj(rho_k)
    return bin_in_k(cross_qrho, auto_rho, box_size)
```

The diagnostic requires a separately specified shell/bin estimator, Fourier mean and window convention, and denominator threshold or regularization before any ratio is considered. The candidate can be complex or undefined/noisy in shells with weak density power and has no automatic $[0,1]$ bound. Validation must compare any proposed bounded $q_{\mathrm{eff}}(k,z)$ against the real-space canonical field, volume- and density-weighted means, resolution changes, and independent closure checks. The cross-spectrum output is not an admissible direct $q_{\mathrm{solver}}(k)$ extraction. A geometric $q_{\mathrm{proxy}}^{C/B}(k)$ remains diagnostic-only and requires the open proxy-to-$q_{\mathrm{solver}}$ map before any constitutive use.

### 4.4 Step 3: Modified Boltzmann Code (CLASS)

**Option A: Simplified growth-factor approach (fast, approximate)**

Modify the linear growth equation outside CLASS:

```python
def compute_sigma8_cassi(q_eff_k_z, cosmology_params):
    """
    Compute σ₈(z) from modified growth using a validated bounded
    effective-coherence table q_eff(k, z), not raw Fourier coefficients.

    For each k, solve:
    δ'' + (2 + H'/H)δ' - (3/2)Ω_m(a)μ(k,a)δ = 0

    where μ(k,a) = (π/ρ_mean(a))
                       (1 + (φ⁶−1)q_eff(k,a)).
    A geometric q_proxy(C/B) cannot be passed as q_eff here.
    """
    for k_idx in range(N_k):
        for a_idx in range(N_a):
            mu = (pi_over_rho_mean[a_idx]) * (
                1 + (XI - 1.0) * q_eff_k_z[k_idx, a_idx]
            )
            # Modified growth
            growth_factor[k_idx, a_idx] = solve_growth_eq(mu, cosmology)
    # P(k,z) = D(k,z)² × P(k, z_init)
    P_k_z = (growth_factor[:, -1] / growth_factor[:, 0])**2 * P_k_init
    # Integrate σ₈²
    sigma8_sq = integrate_tophat(P_k_z, R=8.0)
    return np.sqrt(sigma8_sq)
```

**Option B: Full CLASS modification (accurate, recommended)**

Modify CLASS source code (`source/perturbations.c` or similar) to implement $\mu(k, a)$:

1. **Add parameter** `mu_cassi` to `struct parameters`:
   ```c
   // In include/parameters.h
   double mu_cassi;  // 1 = ΛCDM, else Cassi modification
   double xi_cassi;  // ξ = φ⁶ ≈ 17.944
   ```

2. **Modify Poisson equation** (in `perturbations.c` or equivalent):
   ```c
   // Standard: k²Φ = -4πGa²(ρ_mδ_m + ρ_rδ_r + ...)
   // Cassi:    k²Φ = -4πG·μ(k,a)·a²ρ_mδ_m - 4πGa²ρ_rδ_r + ...
   
   double mu = 1.0;
   if (pvec->mu_cassi > 0) {
       mu = (pi_over_rho) * (1.0 + (pvec->xi_cassi - 1.0) * q_eff_k(a, k));
       // q_eff_k(a,k) is a validated bounded effective-coherence table
       // constructed only after the open estimator in §4.3 is validated
   }
   // Scale-dependent modification
   ps->poisson_equation_factor *= mu;
   ```

3. **Interpolate validated $q_{\mathrm{eff}}(k, a)$**: Read the shell/bin candidate diagnostics and construct a bounded effective-coherence table only after the estimator, denominator treatment, and validation in §4.3 are specified. A $q_{\mathrm{proxy}}^{C/B}$ table cannot be used without the separately measured $\mathcal{M}_{\mathrm{proxy}\to q}$ map.

**Option C: CLASS MG parameterization (preferred)**

CLASS has a built-in modified gravity framework (via `Omega_Lambda` and growth parameters, or the `PPF` module). The cleanest approach is to use the PPF parameterization:

```python
# In CLASS, use the MG parameterization:
# G_eff(k, z) / G_N = μ(k, z) = (π/ρ_mean(z)) * (1 + (ξ - 1) * q_eff_interp(k, z))
# 
# The PPF module accepts μ(k, z) as a function of k and z.
# See CLASS documentation on mu(k,z) and gamma(k,z) functions.
```

However, for full control, modifying the source is safer since the Cassi $\mu(k, a)$ has specific $k$ and $z$ dependence not captured by standard MG templates.

### 4.5 Step 4: $\sigma_8$ Computation

$$\sigma_8^2(z) = \int_0^\infty \frac{dk}{k}\, \Delta^2(k, z)\, |W(kR)|^2$$

where:
- $\Delta^2(k, z) = \frac{k^3 P(k, z)}{2\pi^2}$ is the dimensionless power spectrum
- $W(kR) = 3j_1(kR)/(kR)$ is the top-hat window function
- $R = 8\,h^{-1}$Mpc

The output is $\sigma_8(z)$ for direct comparison with:
- Planck CMB: $\sigma_8 = 0.811 \pm 0.006$ (extrapolated to $z=0$)
- KiDS-1000: $\sigma_8 = 0.759^{+0.026}_{-0.021}$
- DES-Y3: $\sigma_8 = 0.733 \pm 0.023$ (combined with $S_8$)
- DESI: $\sigma_8$ from galaxy clustering + lensing

### 4.6 Validation Chain

| Check | Method | Expected |
|-------|--------|----------|
| $\mu = 1$ limit | Disable the Cassi modification or set the effective $\mu(k,a)$ table identically to $1$ | $\Lambda$CDM $\sigma_8$ reproduced |
| $\xi = \varphi^6$ | Full Cassi | the measured rows of §3.2: total −22.9% (D=0) / −20.5% (D=0.001), mechanism +29.7% |
| $k$-independent $q_{\mathrm{solver}}$ | Set $q_{\mathrm{solver}}(k) = \langle q_{\mathrm{solver}} \rangle$ | Matches existing pipeline within 20% |
| Resolution convergence | $N=32 \to 64 \to 128$ | $\sigma_8$ stabilizes to $\pm 2\%$ |
| Growth rate $f\sigma_8$ | Compare with RSD data | Consistent with DESI/BOSS |

---

## 5. Data Constraints on $q_{\mathrm{solver}}(r, z)$

### 5.1 Galaxy Rotation Curves (Current)

From MW rotation curve analysis (`cosmology/observational_constraints.md` §2.6):

$$v_C/v_B = \sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q_{\mathrm{solver}})} \approx 2.7 \;\Rightarrow\; q_{\mathrm{solver,MW}} = \frac{(2.7^2/0.7) - 1}{16.944} \approx 0.56$$

The ratio $2.7$ is the central value of the model-derived comparison
$190\pm20$ km/s divided by $70\pm15$ km/s; its propagated uncertainty is
approximately $\pm0.65$, with additional baryonic-baseline uncertainty. The
rotation section's conditional branch values $2.8$–$3.0$ therefore provide a
comparison range rather than a direct observed boost.

This constrains the canonical $q_{\mathrm{solver}}$ in galaxy halos at $\rho \sim 10^{-2}$–$10^{-3}$ atoms/cm³. It is a local, $z\approx0$ constraint. This value is consistent with the filament/halo-outskirt regime in Section 2.3, but it is not inferred from $q_{\mathrm{proxy}}^{C/B}$.

### 5.2 Galaxy Cluster Masses

For massive clusters ($M \sim 10^{14}$–$10^{15} M_\odot$), X-ray hydrostatic and weak-lensing mass comparisons could constrain a modified gravitational response, but only after an explicit forward model for both observables. Hydrostatic mass inference has a $G^{-1}$ dependence under specified equilibrium assumptions; the weak-lensing response depends on the metric potentials and the lensing calibration, so the Cassi two-fluid equations do not establish $M_{\text{WL}}\propto G$.

Consequently, $M_{\text{X-ray}}/M_{\text{WL}}=\mu^{-1}$ is not a direct Cassi measurement. A cluster constraint remains a future conditional test requiring the hydrostatic, lensing, baryonic, and screening model to be specified.

### 5.3 Void Profiles (Future, Strongest Test)

Low-density voids ($\rho \lesssim 0.1$ mean density) may approach a low-$q_{\mathrm{solver}}$ state. The limit $G_{\text{eff}}\to G_N$ additionally requires a local state with $\pi/\rho\to1$ and the attractive sign extension; low $q_{\mathrm{solver}}$ alone does not establish that limit. The geometric $C\to-1$ limit gives only $q_{\mathrm{proxy}}^{C}\to0$ and does not fix either canonical factor without the open map in §2.2.

The void ellipticity and outflow velocity profile are sensitive to $G_{\text{eff}}$:

- In $\Lambda$CDM: voids expand isotropically (in the mean), with outflow velocity $\propto H_0 r$.
- Under a separately specified attractive branch with $\mu<1$ in voids, weaker gravity would give a conditional faster-outflow signature; this is not a canonical Cassi result.
- Observable: void-galaxy cross-correlation function (VGCF) from DESI/SDSS.

### 5.4 Redshift-Space Distortions (RSD)

The growth rate $f(z) = d\ln D/d\ln a$ is measured from RSD. Under a quasi-static effective-$\mu$ approximation with slowly varying $\mu$, a candidate diagnostic is:

$$f(z)\sigma_8(z) \approx \Omega_m(z)^{0.55} \sigma_8^{\Lambda\text{CDM}}(z) \cdot \frac{\mu(k_{\text{eff}}, z)^{0.55}}{\mu(k_{\text{eff}}, z_{\text{CMB}})^{0.55}}$$

where $k_{\text{eff}}$ is the effective scale of the RSD measurement ($k \sim 0.1\,h$/Mpc). This approximation is not a Cassi prediction; a time- and scale-dependent $\mu$ requires integrating the growth equation.

Existing data (BOSS/eBOSS) shows a mild ($\sim 1$–$2\sigma$) suppression of $f\sigma_8$ at $z \lesssim 0.5$ relative to Planck $\Lambda$CDM. It is a comparison target for the conditional growth model.

---

## 6. Parameter Summary

| Parameter | Value | Origin | Status |
|-----------|-------|--------|--------|
| $\xi$ | $\varphi^6 \approx 17.944$ | Derived (imbalance inverse-square; "cascade activation step 6" is a shorthand rung label) | Fixed |
| $q_{\mathrm{solver,CMB}}$ ($z\sim1100$) | Not fixed; requires a canonical PDE state at recombination | The geometric $C\approx0$ value gives only $q_{\mathrm{proxy}}^{C}\approx0.5$ and does not determine $q_{\mathrm{solver}}$ | Hypothesized/open |
| $q_{\mathrm{solver,end}}$ | $0.41$ (pipeline endpoint, $a = 1.80$; doctrine $r_0 = 1/23$, N=128 campaign) | PDE at $a = 1.80$ (2026-08-07) | From pipeline |
| $r_0$ (growth-window IC) | $0.0472$ derived ($\varphi^{-5}/(2-\varphi^{-5})$, `foundations/wu-xing-derivation.md`); $1/23$ operational (DESI-anchored); the pipeline's $1/3$ non-doctrinal | Wu Xing derivation / DESI calibration | Derived / Calibrated |
| $q_{\mathrm{proxy,void}}^{C}$ | $\to 0$ as $C\to-1$ (range $[0,2]$) | Explicit squared geometric plan ansatz | Hypothesized/open; not canonical |
| $q_{\mathrm{solver,void}}$ | Must be measured; not fixed by $C/B$ | Canonical PDE state | Hypothesized/open |
| $\langle\pi/\rho\rangle = \alpha_0$ at mean density | $\varphi^{-3} \approx 0.236$ | Derived (fixed-point density imbalance; Yang component fraction $E_Y/\rho=\varphi^{-1}$) | Fixed |
| $\mu(k, a)$ | $(\pi/\rho(a))(1 + (\varphi^{6}-1)q_{\mathrm{eff}}(k, a))$ | Composite after a validated bounded effective-coherence estimator | **Hypothesized/open** |
| $q_{\mathrm{solver,MW\ halo}}$ | $\sim 0.56$ | Conditional rotation-curve comparison using the model-derived central ratio $v_C/v_B\sim2.7\pm0.65$; baryonic-baseline uncertainty additional | Hypothesized conditional |
| $\mathcal{M}_{\mathrm{proxy}\to q}$ | $q_{\mathrm{proxy}}^{C/B}\to q_{\mathrm{solver}}\in[0,1]$ | Separate constitutive measurement or derivation | **Hypothesized/open** |

**No additional fit in the direct PDE route.** The derived constants ($\varphi$, $\xi$), canonical fields ($q_{\mathrm{solver}}(x,a)$, $\rho(a)$), and the separately validated $q_{\mathrm{eff}}(k,a)$ estimator are kept separate from the uncalibrated geometric map. Introducing a proxy route requires registering that map and its uncertainty before it can feed the $\sigma_8$ computation.

## 7. Timeline and Milestones

### Phase 1: PDE at Higher Resolution (Week 1)
- Run `two-fluid/cassi_two_fluid_3d_gpu.py` at $N=64$ with cosmological ICs
- Output canonical $q_{\mathrm{solver}}(x, a)$ and $\rho(x, a)$ at 50 snapshots from $a=0.01$ to $a=1.0$
- **Deliverable:** `q_solver_grid_{a}.npy`, `rho_grid_{a}.npy`

### Phase 2: Scale-Dependent $q_{\mathrm{eff}}(k, z)$ Estimator (Week 1-2)
- Form density-weighted cross/auto spectra from canonical $q_{\mathrm{solver}}(x, a)$ and $\rho(x, a)$; do not divide Fourier modes directly
- Specify shell/bin averaging, denominator threshold or regularization, and validation gates before constructing a bounded $q_{\mathrm{eff}}(k, z)$ table
- **Deliverable:** `q_eff_k_z_interp.npy` only after validation (cross/auto diagnostics retained; geometric proxies remain diagnostic-only)

### Phase 3: Modified Growth Solver (Week 2)
- Implement Option A (simplified): solve $\delta'' + \cdots$ for each $k$ with $\mu(k, a)$
- Compare with $\Lambda$CDM and existing pipeline
- Measure sensitivity to the validated $q_{\mathrm{eff}}(k)$ interpolation; a geometric $q_{\mathrm{proxy}}^{C/B}$ input is a separate open-map sensitivity
- **Deliverable:** $\sigma_8(z)$ from modified growth

### Phase 4: Full CLASS Integration (Week 3-4)
- Implement Option B or C
- Modify Poisson equation in CLASS to accept $\mu(k, a)$
- Compute full $C_\ell$ and $\sigma_8$ simultaneously
- **Deliverable:** Cassi-modified $C_\ell^{TT,TE,EE}$ and $\sigma_8(z)$

### Phase 5: Validation and Sensitivity (Week 4-5)
- Resolution convergence test ($N=32, 64, 128$)
- $\mu = 1$ recovery test
- Validated $q_{\mathrm{eff}}(k)$ interpolation sensitivity
- **Deliverable:** Validated $\sigma_8$ with error budget

---

## 8. Code Modifications Required

### 8.1 New Script: `run_sigma8_boltzmann.py`

Located in `two-fluid/`, this script:

1. Loads the validated bounded $q_{\mathrm{eff}}(k, a)$ interpolation table produced by the estimator in §4.3
2. Modifies CLASS via the Python wrapper (or calls a modified CLASS binary)
3. Computes $P(k, z)$ and $\sigma_8(z)$
4. Produces diagnostic plots:
   - $\mu(k, z)$ vs $k$ and $z$
   - $P(k)^{\text{Cassi}} / P(k)^{\Lambda\text{CDM}}$ vs $k$
   - $\sigma_8(z)$ for both models
   - $f\sigma_8(z)$ vs RSD data

### 8.2 CLASS Source Modification (`external/class/`)

**File:** `source/perturbations.c` (or equivalent in the CLASS version used)

Add Cassi-specific Poisson modification:

```c
// Near line ~950 (Poisson equation evaluation):
if (ppt->has_cassi_mu && pba->index_md_scalars) {
    // Interpolate validated bounded q_eff(k, z) from the estimator output
    double mu = cassi_mu_interp(k, z, pba);
    // Apply scale-dependent modification:
    // k²Φ = -4πG·μ·a²ρ_mδ_m - 4πGa²ρ_rδ_r
    psi -= (mu - 1.0) * source_psi_matter_only;
}
```

**File:** `include/parameters.h` or equivalent:

```c
// Cassi μ(k,z) parameters
int has_cassi_mu;
double xi_cassi;  // φ⁶
char qeff_fits_file[1024];  // validated bounded q_eff(k,z) interpolation table
```

**New file:** `source/cassi_mu.c`:

Interpolation routines for validated bounded $q_{\mathrm{eff}}(k, z)$ and computation of $\mu(k, z)$. A geometric proxy is admissible only after applying the separately registered $\mathcal{M}_{\mathrm{proxy}\to q}$ map and passing the §4.3 estimator validation.

### 8.3 Existing Script Updates

| Script | Change |
|--------|--------|
| `two-fluid/run_sigma8_pipeline.py` | Use for IC generation and canonical real-space $q_{\mathrm{solver}}$ snapshots; form cross/auto diagnostics and construct validated $q_{\mathrm{eff}}(k,z)$ only after §4.3 |
| `two-fluid/run_boltzmann_cassi.py` | Add $\sigma_8$ computation alongside $C_\ell$; accept validated bounded $q_{\mathrm{eff}}(k,z)$ input |
| `two-fluid/cassi_two_fluid_3d_gpu.py` | Ensure canonical real-space $q_{\mathrm{solver}}(x)$ snapshot output at cosmological resolution; keep $C/B$ diagnostics separate |

---

## 9. Success Criteria

The computation reaches **Derived** status when:

1. **Quantitative match:** $\sigma_8^{\text{Cassi}}(z=0)$ is within $1\sigma$ of the combined low-redshift weak-lensing measurements ($\sigma_8 \approx 0.75\text{–}0.78$) given the Planck-calibrated initial conditions.

2. **Consistency checks:** Existing comparisons include:
   - MW rotation curve boost ($2.8$–$3.0\times$ predicted vs the model-derived central ratio $2.7\pm0.65$ from $190\pm20$ and $70\pm15$ km/s, with additional baryonic-baseline uncertainty)
   - $w_0 = -0.87$ ($2\sigma$ baseline from DESI DR2's $w_0 \approx -0.75 \pm 0.06$ [INFERENCE]; $3.6\sigma$ at fixed $r_0$ with the calibrated Yang-fraction-weighted coupling)
   - $w_a = +0.012$ for the calibrated baseline ($2.7\sigma$); the nonviable B2 trial gives $-0.38$ ($1.25\sigma$), while the conditional C1 friction closure gives the pure-$\Lambda$ window fit $(-1, 0)$ ($2.61\sigma$ in $w_a$)

3. **Residual tension explained:** The $\sim 0.02\text{–}0.06$ gap between Cassi and the lowest $\sigma_8$ measurements is a future comparison target; its systematic uncertainty can be assessed only after the $q_{\mathrm{eff}}(k)$ estimator is validated at finite resolution ($N \geq 64$). A geometric proxy cannot be counted as extraction evidence without $\mathcal{M}_{\mathrm{proxy}\to q}$.

---

## 10. Key Equations Summary

| Equation | Description |
|----------|-------------|
| $G_{\text{eff}} = (\pi/\rho)(1 + (\varphi^{6}-1)q_{\mathrm{solver}}) G_N$ | Qi-gravity formula using canonical solver coherence |
| $\xi = \varphi^6 \approx 17.944$ | Derived coupling |
| $q_{\mathrm{solver}} = \rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)\in[0,1]$ | Canonical two-fluid coherence from $E_Y,E_I$ |
| $q_{\mathrm{proxy}}^{C} = (1+C)^2/2\in[0,2]$ | Explicit squared geometric plan ansatz; not canonical $q_{\mathrm{solver}}$ |
| $q_{\mathrm{proxy}}^{B} = (1+B)^2/2\in[0,2]$ | 3D geometric proxy; not canonical $q_{\mathrm{solver}}$ |
| $q_{\mathrm{solver}}=\mathcal{M}_{\mathrm{proxy}\to q}(q_{\mathrm{proxy}}^{C/B})\in[0,1]$ | Hypothesized/open constitutive mapping required before $G_{\mathrm{eff}}$ |
| $\mu(k,a) = (\pi/\rho(a))(1 + (\varphi^{6}-1)q_{\mathrm{eff}}(k,a))$ | Scale-dependent modification, conditional on a validated bounded $q_{\mathrm{eff}}$ estimator |
| $\sigma_8^2(z) = \int \frac{dk}{k} \Delta^2(k,z) |W(kR)|^2$ | $\sigma_8$ definition |
| $q_{\mathrm{halo,proxy}} = 1/(1+(\rho/\rho_{\text{ref}})^2)$ | Galaxy-halo density proxy (separate context; cross-check only) |

---

## References

- `cosmology/cosmology-from-phi.md`—Cassi cosmology overview
- `cosmology/observational_constraints.md`—Rotation curve constraint
- `foundations/xi-derivation.md`—Derivation of $\xi = \varphi^6$
- `foundations/bubble-edge-geometry.md`—$C$ geometric field and the $q_{\mathrm{proxy}}^{C}$ plan ansatz; any $G_{\text{eff}}$ use is conditional on $\mathcal{M}_{\mathrm{proxy}\to q}$
- `foundations/bubble-lattice-fabric.md`—3D $B$ extension and its separate geometric proxy
- `foundations/phi_attractor_synthesis.md`—$q_{\mathrm{halo,proxy}} = 1/(1+(\rho/\rho_{\text{ref}})^2)$ (galaxy-halo context)
- `foundations/refined-numeric-predictions.md` §2.9—Current $\sigma_8$ pipeline status
- `foundations/refined-numeric-predictions.md` §5.2—Remaining pipeline work
- `open-questions-cassi-answers.md` §T3—$\sigma_8$ tension entry
- `predictions/falsifiable-predictions.md`—$\sigma_8$ in prediction table
- `predictions/cassi_definitions.md`—$G_{\text{eff}}$ formula definitions
- `two-fluid/cassi_two_fluid_3d_gpu.py`—PDE solver
- `two-fluid/run_sigma8_pipeline.py`—Existing $\sigma_8$ pipeline
- `two-fluid/run_boltzmann_cassi.py`—Existing Boltzmann pipeline (phenomenological transfer function)
