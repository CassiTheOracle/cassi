# Sigma-8 Computational Plan: Modified Boltzmann Pipeline for Cassi Qi-Gravity

## Status: Plan—July 2026

## Abstract

This document is the computational plan for promoting the Cassi $\sigma_8$ prediction from Hypothesized to Derived. The mechanism is the density-dependent Qi-gravity coupling $G_{\text{eff}} = (\pi/\rho)(1+(\varphi^{6}-1)q)G_N$ with $\xi = \varphi^6$: voids see near-Newtonian gravity while filament and halo regions see an enhanced $G_{\text{eff}}$, and the cosmic-mean $q$ decreases with time, suppressing late-time growth by roughly $5$–$10\%$ relative to $\Lambda$CDM—matching the observed Planck-vs-weak-lensing $\sigma_8$ deficit. The reconciliation (2026-08-06, `computations/sigma8_reconciliation.py`) bounds this: the pipeline's −43.5% headline is dominated by normalization and resolution, only −9.6% is mechanism-attributable ($G_{\text{eff}} = 0.9044$), and the "~5%" target is Mapped (ledger §10). The plan runs a high-resolution two-fluid PDE, extracts $q(k, a)$ per Fourier mode, integrates it into a modified Boltzmann solver, and validates against rotation curves, cluster masses, and $f\sigma_8$.

---

## 1. Objective

Compute $\sigma_8(z)$ from the Cassi two-fluid framework by integrating the density-dependent Qi-gravity modification $G_{\text{eff}}(k, q)$ into a Boltzmann code. The current epistemic status is **Hypothesized** (qualitative match; quantitative computation pending). The reconciliation (2026-08-06, `computations/sigma8_reconciliation.py`) established that the existing pipeline's −43.5% headline is normalization- and resolution-dominated (P(k) normalization factor 8e-5, nonlinear ICs, N=32 PDE dissipation: δ_rms falls 32% while ΛCDM linear growth rises +21%), leaving −9.6% mechanism-attributable ($G_{\text{eff}} = 0.9044$); the "~5%" $\sigma_8$ suppression is a Mapped target (μ = 0.98 → −5.3% under the plan's scaling), not a derived prediction. Reaching **Derived** requires a resolution- and normalization-controlled computation that isolates the mechanism contribution.

---

## 2. The Core Mechanism

### 2.1 Qi-Gravity Enhancement Formula

The Cassi gravitational constant depends on the local Qi coherence $q$ and the geometric projection factor $\pi/\rho$:

$$\boxed{G_{\text{eff}}(x) = \frac{\pi}{\rho(x)}\left(1 + (\varphi^{6}-1)q(x)\right) G_N, \qquad \xi = \varphi^6 \approx 17.944}$$

where:
- $q \in [0, 1]$ is the Qi coherence quality (derived from the two-fluid Yang/Yin ratio)
- $\pi/\rho$ is the geometric dilution factor from the two-fluid projection onto 3D space; at the $\varphi$-fixed point it is the equilibrium Yang fraction $\alpha_0 = \varphi^{-3} \approx 0.236$
- $\xi = \varphi^6$ is the **derived** coupling (cascade activation at step 6, see `foundations/xi-derivation.md`)

### 2.2 Density Dependence of $q$

The Qi coherence $q$ is a monotonic function of local density. Translating between the large-scale condensation field $C$ (from `foundations/bubble-edge-geometry.md`) and $q$:

$$q(C) = \frac{1 + C}{2}, \qquad C \in [-1, 1]$$

The density traces the condensation field:

$$\rho(C) \approx \rho_0 \cdot \max\!\left(0,\; \frac{C - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)^{\!\nu},\qquad \nu \in [1, 2]$$

Inverting: $C \to q \to G_{\text{eff}}$ gives a mapping from local density to effective gravity.

**Two $q$ formulas—reconciliation note:** A second expression appears in `foundations/phi_attractor_synthesis.md`: $q = 1/(1 + (\rho/\rho_{\text{ref}})^2)$, which gives $q \to 1$ at low density and $q \to 0$ at high density (opposite dependence to the $C$ parameterization). These apply at different scales and are not contradictory:

| Parameterization | Context | Domain | $q$ in high-$\rho$ | $q$ in low-$\rho$ |
|-----------------|---------|--------|-------------------|-------------------|
| $q(C) = (1+C)/2$ | Cosmological LSS, $\sigma_8$ | Condensation field on Gpc/Mpc scales | Clusters: $C>0,\; q>0.5$ | Voids: $C<0,\; q<0.5$ |
| $q = 1/(1+(\rho/\rho_{\text{ref}})^2)$ | Galaxy halo radial profile | Scale of individual virialized halos | Core: $\rho\gg\rho_{\text{ref}},\; q\to 0$ | Outskirts: $\rho\ll\rho_{\text{ref}},\; q\to 1$ |

The **PDE computed $q(x)$** supersedes both analytic parameterizations for the $\sigma_8$ pipeline—it captures the true $q$ from two-fluid dynamics at all cosmic scales simultaneously. The analytic formulas are useful for understanding limiting cases and for designing initial conditions.

### 2.3 Three Regimes of $G_{\text{eff}}$ (Cosmological Context)

| Regime | Density | $C$ (condensation) | $q$ (coherence) | $\pi/\rho$ | $G_{\text{eff}}/G_N$ (approx) |
|--------|---------|--------------------|-----------------|------------|------------------------------|
| Cluster core | Very high | $\to 1$ | $\to 1$ | $\to 0$ | $\sim 1$–$3$ (geometric factor $\pi/\rho$ dilutes the $\xi$ enhancement despite high $q$) |
| Filament / halo outskirts | Moderate | $\sim 0.45$ | $\sim 0.7$ | $\sim 0.6$ | $\sim 8$–$10$ (sweet spot: enough $q$ for enhancement, $\pi/\rho$ not yet suppressed) |
| Void | Low | $\to -1$ | $\to 0$ | $\to 1$ | $\to 1$ (unamplified—no condensation, mean-field gravity) |

The $\sigma_8$ tension arises because low-density regions (voids, filament edges) have $G_{\text{eff}} \approx G_N$, while early-universe structure formation assumed $\Lambda$CDM with $G_{\text{eff}} = G_N$ everywhere. The scale dependence enters because different Fourier modes $k$ sample different distributions of $q$, and $\sigma_8$ at $R = 8\,h^{-1}$Mpc averages over the filament-void network.

### 2.4 $q$ Evolution with Redshift

The PDE simulation shows that the cosmic-mean $q$ **decreases** with time:

- $q \approx 0.43$ at $z \approx 100$ ($a = 0.01$)
- $q \approx 0.40$ at $z \approx 0$ (extrapolated)
- $q \approx 0.38$ at $a = 1.65$ (pipeline endpoint)

This trend—higher $q$ at earlier times—reflects the two-fluid starting in a high-coherence state near the $\varphi$-attractor coming out of inflation, then losing coherence as $Y \to I$ conversion proceeds and structure forms. The $q(z)$ evolution is the key input to the $\sigma_8$ pipeline: if $q$ were constant, there would be no $\sigma_8$ suppression since $\mu(k,a)$ would be time-independent and absorbed into the normalization.

At very early times ($z > 1000$, prior to recombination), the universe is nearly homogeneous and $C \approx 0$, so $q \approx 0.5$ from the condensation-field parameterization. However, the PDE's $q(z)$ shows values above 0.5 in the early post-inflation era, approaching 1 at the $r \gg \varphi$ limit (pure Yang). The pipeline should use PDE-extracted $q(z)$ directly for all epochs.

---

## 3. Analytic Estimate (without Boltzmann Code)

### 3.1 Modified Growth Equation

In the linear regime, the matter overdensity $\delta_m(k, a)$ satisfies:

$$\delta_m'' + \left(2 + \frac{H'}{H}\right)\delta_m' - \frac{3}{2}\,\Omega_m(a)\,\mu(k, a)\,\delta_m = 0$$

where $\mu(k, a) = G_{\text{eff}}(k, a)/G_N$ and primes denote $d/d\ln a$.

For $\Lambda$CDM ($\mu = 1$), the growth factor $D(a) \propto a$ in EdS, and $D(a) \propto a^{\Omega_m^{0.55}}$ in $\Lambda$CDM.

For Cassi ($\mu \neq 1$), growth is enhanced at early times (high $q$) and suppressed at late times (low $q$) relative to a constant-G baseline, because $\mu(a)$ tracks $q(a)$.

### 3.2 Effective $\mu$ from the Pipeline

The existing PDE pipeline (`two-fluid/run_sigma8_pipeline.py`) at $N=32$ gives:

- $q_{\text{initial}} = 0.429$, $q_{\text{final}} = 0.382$ (spatial mean)
- $G_{\text{eff}}/G_{\text{ref}} = 0.904$ (9.6% relative reduction in effective gravity as $q$ drops)

In the matter-dominated era where $D \propto a^p$ with $p = \frac{-1 + \sqrt{1 + 24\mu}}{4}$ for $\mu = G_{\text{eff}}/G_N$:

| $\mu$ (constant approximation) | $p$ | $D(z=0)/D(z=100)$ | $\sigma_8$ ratio vs. $\Lambda$CDM | Suppression |
|-------|-----|-------------------|----------------------------------|-------------|
| 1.000 ($\Lambda$CDM) | 1.000 | 101.0 | 1.000 |—|
| 0.904 (pipeline spatial-mean $\mu$) | 0.941 | 77.6 | 0.768 | **-23.2%** |
| 0.950 (estimated effective $\mu$) | 0.970 | 87.4 | 0.865 | **-13.5%** |
| 0.980 (target, matching observations) | 0.989 | 95.7 | 0.947 | **-5.3%** |

**The target $\mu \approx 0.98$** (a 2% suppression of $G_{\text{eff}}$ on $\sigma_8$ scales relative to the initial condition) would produce the observed $\sim 5\%$ $\sigma_8$ reduction. This is a **Mapped target** (fit-status ledger §10), not a derived value: the reconciliation (2026-08-06, `computations/sigma8_reconciliation.py`) shows the pipeline's −43.5% headline is dominated by normalization and resolution, with −9.6% mechanism-attributable ($G_{\text{eff}} = 0.9044$); the ~5% number enters through the chosen μ, it does not emerge from the dynamics.

### 3.3 Why the Pipeline Overestimates

The existing pipeline ($\Delta\sigma_8 = -0.42$, $-43\%$) overestimates because:

1. **Scale-independent $q$:** Uses the spatial mean of $q$ across all modes. On $\sigma_8$ scales ($R = 8\,h^{-1}$Mpc, $k \sim 0.1$–$1\,h$/Mpc), the volume is dominated by the filament-void network where $q$ is closer to the mean field value, not the extreme core value.

2. **Low resolution ($N=32$):** Only captures the largest modes. The $\sigma_8$ integral receives contributions from $k$ up to $\sim 1\,h$/Mpc, which are under-resolved by a factor of several.

3. **Short evolution ($a_{\text{final}} = 1.65$):** The ratio $q_{\text{final}}/q_{\text{initial}} = 0.89$ represents only a small segment of the full $q(z)$ history. An integration from $a=0.001$ to $a=1.0$ is needed.

### 3.4 Why the Suppression is Scale-Dependent

The suppression is **not uniform** across $k$ because:

- **Large scales ($k \ll k_Y \sim 0.03\,h$/Mpc):** These modes average over many bubbles. The effective $q$ is the cosmic-mean $q$, giving $\mu(k)$ close to the mean value. Growth is enhanced at early times (high $q$) and suppressed at late times, with partial cancellation.

- **Intermediate scales ($k \sim 0.1$–$1\,h$/Mpc, $\sigma_8$ range):** These modes sample within individual bubbles. The $q$ distribution is bimodal—high $q$ in condensing regions, low $q$ in voids. The volume-weighted mean $q$ determines $\mu_{\text{eff}}$, giving a net suppression.

- **Small scales ($k \gg 1\,h$/Mpc):** These modes are inside virialized halos where $q$ is determined by local dynamics. The $q$ is higher, so $G_{\text{eff}}$ is enhanced—but this enters the nonlinear regime where perturbation theory breaks down and N-body is needed.

The net effect on $\sigma_8$ is the integral over all $k$ with the top-hat window $W(kR)$, where $R = 8\,h^{-1}$Mpc. The $k$-dependence of $\mu(k, a)$ is what the Boltzmann code must compute.

### 3.5 Refined Analytic Estimate

Using $q(z)$ from the PDE and integrating the growth equation numerically with $\mu(k,a) = (\pi/\rho(a))(1 + (\varphi^{6}-1)q(a))$, parameterizing the $k$-dependence as a smooth transition between void ($k$ small, $q \to 0$) and cluster ($k$ large, $q \to \langle q\rangle$) regimes, the estimated suppression is:

$$\boxed{\frac{\sigma_8^{\text{Cassi}}}{\sigma_8^{\Lambda\text{CDM}}} \approx 0.90\text{--}0.95 \quad \Rightarrow \quad \Delta\sigma_8/\sigma_8 \approx -5\%\text{ to }-10\%}$$

This estimate is the plan's target band. The reconciliation (2026-08-06, `computations/sigma8_reconciliation.py`) establishes what the current pipeline actually delivers: the −43.5% headline is dominated by the P(k) normalization factor (8e-5), nonlinear initial conditions, and N=32 dissipation (δ_rms falls 32% while ΛCDM linear growth rises +21%); the mechanism-attributable suppression is −9.6% ($G_{\text{eff}} = 0.9044$), and both numbers are normalization-sensitive. The band above is a Mapped target, not a measured suppression.

This matches:
- The qualitative expectation from `predictions/falsifiable-predictions.md` ("slightly lower, ~5%")
- The observed Planck vs. weak-lensing tension ($\sim 5\text{–}9\%$)
- The $f\sigma_8$ suppression seen in BOSS/eBOSS at $z \lesssim 0.5$ ($\sim 1\sigma$)

**To go from this estimate to a Derived prediction requires the full $k$-dependent $\mu(k,a)$ from the PDE-integrated Boltzmann pipeline.**

---

## 4. Computational Pipeline

### 4.1 Overview

```
PDE Simulation       q(k,z) Extraction      Boltzmann Solver         Sigma8
(q(x,t) field)  -->  (q per Fourier mode)--> (modified CLASS)  -->  (σ₈(z))
     |                      |                       |
     |-- q(x) at each a     |-- q(k) = FFT(q(x))    |-- μ(k,a) = (π/ρ)(1+(φ⁶−1)q(k,a))
     |-- ρ(x) at each a     |-- ρ average            |-- Poisson: k²Φ = -4πG·μ·a²ρδ
     |-- resolution N≥64    |-- bin in k             |-- Modified growth + C_ℓ
```

### 4.2 Step 1: High-Resolution PDE Simulation

**What:** Run `two-fluid/cassi_two_fluid_3d_gpu.py` at $N=64$ or $N=128$ with cosmological ICs.

**Parameters:**
- Grid: $N=64$ minimum, $N=128$ target (GPU), $N=32$ minimum (CPU)
- ICs: Eisenstein-Hu transfer function at $z=100$ ($a=0.01$)
- Box size: $L = 256\,h^{-1}$Mpc (to capture $\sigma_8$ scales $k \sim 0.1$–$1\,h$/Mpc)
- Duration: $a_{\text{init}} = 0.01$ to $a_{\text{final}} = 1.0$ ($z=0$)
- Output: Density $\rho(x, a)$ and Qi coherence $q(x, a)$ at $N_a \sim 50$ snapshots

**Outputs:**
- `q_grid_{a}.npy`: $q(x)$ at each scale factor
- `rho_grid_{a}.npy`: $\rho(x)$ at each scale factor

### 4.3 Step 2: $q(k, z)$ Extraction

**What:** Fourier transform the $q(x)$ field to get $q(k)$ per mode.

**Method:**
```python
def extract_qk(q_grid, rho_grid, box_size):
    """
    Extract scale-dependent Qi coherence q(k, a).

    For each scale factor a, compute:
    1. Density-weighted q(k): weighted by ρ(x) to get the
       effective coherence affecting gravitational dynamics
    2. Volume-weighted q(k): to understand the geometric distribution

    Returns:
        q_k: array of shape (N_k, N_a)—q per k-bin per redshift
    """
    # FFT of q(x) * ρ(x) / FFT of ρ(x) for density-weighted q(k)
    q_rho_k = np.fft.rfftn(q_grid * rho_grid) / np.fft.rfftn(rho_grid)
    # Bin in |k|
    q_k_binned = bin_in_k(q_rho_k, box_size)
    return q_k_binned
```

**Critical physics:** The density-weighted $q(k)$ at each $k$ gives the effective coherence for Fourier mode $k$. Low-$k$ modes sample the mean density (including voids), while high-$k$ modes sample high-density clumps.

### 4.4 Step 3: Modified Boltzmann Code (CLASS)

**Option A: Simplified growth-factor approach (fast, approximate)**

Modify the linear growth equation outside CLASS:

```python
def compute_sigma8_cassi(q_k_z, cosmology_params):
    """
    Compute σ₈(z) from modified growth.

    For each k, solve:
    δ'' + (2 + H'/H)δ' - (3/2)Ω_m(a)μ(k,a)δ = 0

    where μ(k,a) = (π/ρ_mean(a))(1 + (φ⁶−1)q(k,a))
    """
    for k_idx in range(N_k):
        for a_idx in range(N_a):
            mu = (pi_over_rho_mean[a_idx]) * (1 + XI * q_k_z[k_idx, a_idx])
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
       mu = (pi_over_rho) * (1.0 + pvec->xi_cassi * q_k(a, k));
       // q_k(a,k) interpolated from PDE snapshots or parameterized
   }
   // Scale-dependent modification
   ps->poisson_equation_factor *= mu;
   ```

3. **Interpolate $q(k, a)$**: Read the binned $q(k)$ from PDE and create a 2D interpolation table $q(k, a)$.

**Option C: CLASS MG parameterization (preferred)**

CLASS has a built-in modified gravity framework (via `Omega_Lambda` and growth parameters, or the `PPF` module). The cleanest approach is to use the PPF parameterization:

```python
# In CLASS, use the MG parameterization:
# G_eff(k, z) / G_N = μ(k, z) = (π/ρ_mean(z)) * (1 + ξ * q_interp(k, z))
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
| $\mu = 1$ limit | Set $\xi = 0$ | $\Lambda$CDM $\sigma_8$ reproduced |
| $\xi = \varphi^6$ | Full Cassi | $\sigma_8$ lower by $\sim 5\%$ |
| $k$-independent $q$ | Set $q(k) = \langle q \rangle$ | Matches existing pipeline within 20% |
| Resolution convergence | $N=32 \to 64 \to 128$ | $\sigma_8$ stabilizes to $\pm 2\%$ |
| Growth rate $f\sigma_8$ | Compare with RSD data | Consistent with DESI/BOSS |

---

## 5. Data Constraints on $q(r, z)$

### 5.1 Galaxy Rotation Curves (Current)

From MW rotation curve analysis (`cosmology/observational_constraints.md` §2.6):

$$v_C/v_B = \sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)} \approx 2.7 \;\Rightarrow\; q_{\text{MW}} = \frac{(2.7^2/0.7) - 1}{16.944} \approx 0.56$$

(The rotation section's own values 2.8–3.0 give $q = 0.60$–$0.70$.)

This constrains $q$ in galaxy halos at $\rho \sim 10^{-2}$–$10^{-3}$ atoms/cm³. It is a local, $z\approx0$ constraint. This $q$ value is consistent with the filament/halo-outskirt regime in Section 2.3.

### 5.2 Galaxy Cluster Masses

For massive clusters ($M \sim 10^{14}$–$10^{15} M_\odot$), the mass discrepancy between X-ray and weak-lensing hydrostatic masses constrains $G_{\text{eff}}$:

$$M_{\text{X-ray}} \propto G^{-1}, \qquad M_{\text{WL}} \propto G$$

The ratio $M_{\text{X-ray}}/M_{\text{WL}} = \mu^{-1}$ gives a direct measurement of $G_{\text{eff}}/G_N$ in cluster outskirts ($\rho \sim 10^{-4}$ atoms/cm³).

### 5.3 Void Profiles (Future, Strongest Test)

Low-density voids ($\rho \lesssim 0.1$ mean density) should have $q \to 0$ and $G_{\text{eff}} \to G_N$. The void ellipticity and outflow velocity profile are sensitive to $G_{\text{eff}}$:

- In $\Lambda$CDM: voids expand isotropically (in the mean), with outflow velocity $\propto H_0 r$
- In Cassi: voids have **weaker gravity** inside, so outflow is faster than $\Lambda$CDM
- Observable: void-galaxy cross-correlation function (VGCF) from DESI/SDSS

### 5.4 Redshift-Space Distortions (RSD)

The growth rate $f(z) = d\ln D/d\ln a$ is measured from RSD. The Cassi prediction for $f\sigma_8(z)$ is:

$$f(z)\sigma_8(z) \approx \Omega_m(z)^{0.55} \sigma_8^{\Lambda\text{CDM}}(z) \cdot \frac{\mu(k_{\text{eff}}, z)^{0.55}}{\mu(k_{\text{eff}}, z_{\text{CMB}})^{0.55}}$$

where $k_{\text{eff}}$ is the effective scale of the RSD measurement ($k \sim 0.1\,h$/Mpc).

Existing data (BOSS/eBOSS) shows a mild ($\sim 1\text{–}2\sigma$) suppression of $f\sigma_8$ at $z \lesssim 0.5$ relative to Planck $\Lambda$CDM—consistent with the Cassi direction.

---

## 6. Parameter Summary

| Parameter | Value | Origin | Status |
|-----------|-------|--------|--------|
| $\xi$ | $\varphi^6 \approx 17.944$ | Derived (cascade activation step 6) | Fixed |
| $q_{\text{CMB}}$ ($z\sim1100$) | $\sim 0.5$ (estimate) | PDE near recombination | Requires extraction |
| $q_{0}$ ($z=0$) | $\sim 0.4$ (interpolated) | PDE at $z=0$ | From pipeline |
| $q_{\text{void}}$ | $\to 0$ | Condensation field geometric limit | Fixed |
| $\langle\pi/\rho\rangle = \alpha_0$ at mean density | $\varphi^{-3} \approx 0.236$ | Derived (equilibrium Yang fraction $\alpha_0$) | Fixed |
| $\mu(k, a)$ | $(\pi/\rho(a))(1 + (\varphi^{6}-1)q(k, a))$ | Composite | **Computed from PDE** |
| $q_{\text{MW halo}}$ | $\sim 0.7$ | Rotation curve fit ($v_C/v_B = 2.7$) | Independent calibration check |

**Zero new free parameters.** All quantities are either derived mathematical constants ($\varphi$, $\xi$) or PDE outputs ($q(k, a)$, $\rho(a)$). The MW rotation curve provides an independent cross-check but is not used as an input to the $\sigma_8$ pipeline.

---

## 7. Timeline and Milestones

### Phase 1: PDE at Higher Resolution (Week 1)
- Run `two-fluid/cassi_two_fluid_3d_gpu.py` at $N=64$ with cosmological ICs
- Output $q(x, a)$ and $\rho(x, a)$ at 50 snapshots from $a=0.01$ to $a=1.0$
- **Deliverable:** `q_grid_{a}.npy`, `rho_grid_{a}.npy`

### Phase 2: $q(k, z)$ Extraction (Week 1-2)
- Fourier transform density-weighted $q(k, a)$
- Bin in $k$ and interpolate in $z$
- **Deliverable:** `q_k_z_interp.npy` (2D interpolation table)

### Phase 3: Modified Growth Solver (Week 2)
- Implement Option A (simplified): solve $\delta'' + \cdots$ for each $k$ with $\mu(k, a)$
- Compare with $\Lambda$CDM and existing pipeline
- **Deliverable:** $\sigma_8(z)$ from modified growth

### Phase 4: Full CLASS Integration (Week 3-4)
- Implement Option B or C
- Modify Poisson equation in CLASS to accept $\mu(k, a)$
- Compute full $C_\ell$ and $\sigma_8$ simultaneously
- **Deliverable:** Cassi-modified $C_\ell^{TT,TE,EE}$ and $\sigma_8(z)$

### Phase 5: Validation and Sensitivity (Week 4-5)
- Resolution convergence test ($N=32, 64, 128$)
- $\mu = 1$ recovery test
- $q(k)$ interpolation sensitivity
- **Deliverable:** Validated $\sigma_8$ with error budget

---

## 8. Code Modifications Required

### 8.1 New Script: `run_sigma8_boltzmann.py`

Located in `two-fluid/`, this script:

1. Loads the PDE $q(k, a)$ interpolation table
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
    // Interpolate mu(k, z) from PDE data
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
char qk_fits_file[1024];  // path to q(k,z) interpolation table
```

**New file:** `source/cassi_mu.c`:

Interpolation routines for $q(k, z)$ and computation of $\mu(k, z)$.

### 8.3 Existing Script Updates

| Script | Change |
|--------|--------|
| `two-fluid/run_sigma8_pipeline.py` | Use for IC generation only; replace $\sigma_8$ computation with Boltzmann integration |
| `two-fluid/run_boltzmann_cassi.py` | Add $\sigma_8$ computation alongside $C_\ell$; accept $q(k,z)$ input |
| `two-fluid/cassi_two_fluid_3d_gpu.py` | Ensure $q(k)$ snapshot output at cosmological resolution |

---

## 9. Success Criteria

The computation reaches **Derived** status when:

1. **Quantitative match:** $\sigma_8^{\text{Cassi}}(z=0)$ is within $1\sigma$ of the combined low-redshift weak-lensing measurements ($\sigma_8 \approx 0.75\text{–}0.78$) given the Planck-calibrated initial conditions.

2. **Consistency with existing tests:** The same $\xi = \varphi^6$ and $q$ evolution reproduces:
   - MW rotation curve boost ($2.8$–$3.0\times$ predicted vs $2.7 \pm 0.5$ observed at 30 kpc)—consistent within ~0.4σ
   - $w_0 = -0.87$ ($2\sigma$ baseline from DESI DR2's $w_0 \approx -0.75 \pm 0.06$ [INFERENCE]; $3.6\sigma$ at fixed $r_0$ with the ratified coupling)
   - $w_a = +0.012$ with $\xi$ correction ($2.7\sigma$ baseline) → $-0.38$ with the ratified conversion→expansion coupling ($1.25\sigma$, B2—unstable; 08 §C.6); the stable realization (friction closure—10/12) gives the pure-Λ window fit $(-1, 0)$ ($2.61\sigma$ in $w_a$)

3. **Residual tension explained:** The $\sim 0.02\text{–}0.06$ gap between Cassi and the lowest $\sigma_8$ measurements is within the systematic uncertainty of $q(k)$ extraction at finite resolution ($N \geq 64$).

---

## 10. Key Equations Summary

| Equation | Description |
|----------|-------------|
| $G_{\text{eff}} = (\pi/\rho)(1 + (\varphi^{6}-1)q) G_N$ | Qi-gravity formula |
| $\xi = \varphi^6 \approx 17.944$ | Derived coupling |
| $q(C) = (1 + C)/2$ | Qi coherence from condensation field (cosmological context) |
| $\delta'' + (2 + H'/H)\delta' - \frac{3}{2}\Omega_m(a)\mu(k,a)\delta = 0$ | Modified growth equation |
| $\mu(k,a) = (\pi/\rho(a))(1 + (\varphi^{6}-1)q(k,a))$ | Scale-dependent modification factor |
| $\sigma_8^2(z) = \int \frac{dk}{k} \Delta^2(k,z) |W(kR)|^2$ | $\sigma_8$ definition |
| $q = 1/(1+(\rho/\rho_{\text{ref}})^2)$ | Galaxy-halo $q$ profile (different context, used only for cross-check) |

---

## References

- `cosmology/cosmology-from-phi.md`—Cassi cosmology overview
- `cosmology/observational_constraints.md`—Rotation curve constraint
- `foundations/xi-derivation.md`—Derivation of $\xi = \varphi^6$
- `foundations/bubble-edge-geometry.md`—$q(C)$ and $G_{\text{eff}}(C)$ profiles
- `foundations/phi_attractor_synthesis.md`—$q = 1/(1+(\rho/\rho_{\text{ref}})^2)$ (galaxy-halo context)
- `foundations/refined-numeric-predictions.md` §2.9—Current $\sigma_8$ pipeline status
- `foundations/refined-numeric-predictions.md` §5.2—Remaining pipeline work
- `open-questions-cassi-answers.md` §T3—$\sigma_8$ tension entry
- `predictions/falsifiable-predictions.md`—$\sigma_8$ in prediction table
- `predictions/cassi_definitions.md`—$G_{\text{eff}}$ formula definitions
- `two-fluid/cassi_two_fluid_3d_gpu.py`—PDE solver
- `two-fluid/run_sigma8_pipeline.py`—Existing $\sigma_8$ pipeline
- `two-fluid/run_boltzmann_cassi.py`—Existing Boltzmann pipeline (phenomenological transfer function)
