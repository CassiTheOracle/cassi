# Observational Constraints—DESI DR2 Dark Energy & Milky Way Rotation Curve

## Status: Calibrated ($w_0$ coupling form, $\xi$ pin—ledger) / Mapped ($\alpha_{\text{halo}}$ nominal, halo $q$—ledger)—August 2026

## Abstract

The Cassi framework is compared against the strongest current cosmological and galactic constraints. The two-fluid dark-energy prediction ($w_0 = -0.87$, $w_a = +0.012$ with the Yang-fraction-weighted coupling) sits at $2\sigma$/$2.7\sigma$ tension with the DESI DR2 best fit ($w_0 \approx -0.75$, $w_a \approx -0.73$) at the Calibrated baseline—a real tension, not a resolution. With the ratified conversion→expansion coupling (Hypothesized—August 2026, zero free constants; `cassi-toe-rewrite-briefs/spiral-gravity/08-conversion-expansion-coupling.md` §C.6), the unstable B2 realization's CPL-fitted shifts are $\Delta w_0 = -0.098$, $\Delta w_a = -0.393$ (bracket $-0.61$…$-0.38$; B2's density blows up—not a stable system, 10 §4); the term's **stable realization** (the C1 Hubble-friction closure—`10-source-stabilization.md`, `12-cosmology-rstar.md`) freezes $\rho$ at $\varphi$ exactly and collapses $r$ to the $r_* \approx 0.9503$ attractor by $z \approx 61$, giving a **pure-Λ DESI-window fit $(w_0, w_a) = (-1, 0)$—4.17σ/2.61σ from DESI** (the B2 $w_a = -0.38$/1.25σ values describe the unstable realization and are superseded for the theory's prediction; $w_0$ is a Calibrated target—ledger §10—and $r_0$ re-tuning is closed negatively under the stable realization, 12 §4.1). The Qi-enhanced rotation-curve prediction $v_C/v_B = \sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)} \approx 3.0$ matches the observed Milky Way boost $2.7 \pm 0.5$ within ~1.2σ—a consistency check against the calibration object ($\xi$ pinned on the MW curve; $\alpha_{\text{halo}} = 0.7$ a hardcoded nominal, Fit-Status Ledger `parameter-inventory.md` §10), not an independent test. The CMB large-angle axis is a measured alignment (12.2° dipole↔quadrupole separation, computed from the data vectors—Calibrated); the triaxial bubble-boundary geometry at cascade step 285 is a candidate mechanism whose orientation is fitted to the measured axis (Hypothesized). The bubble lattice cannot bias the DESI CPL fit (`cosmology/desi-lattice-averaging.md`), and the $\sigma_8$ pipeline is planned in `cosmology/sigma8-computational-plan.md`.

Sources compiled 2026-07-15 via web search and primary literature. All error bars are 68% (1σ) confidence unless noted.

---

## 1. Dark Energy Equation of State—DESI Data Release 2

### 1.1 The Cassi Prediction

The Cassi φ-attractor produces an effective dark energy with a present-day equation of state (see `two-fluid/calibrate_initial_ratio.py` and `foundations/phi_attractor_synthesis.md`):

$$w_0 = -0.87 \quad \text{(Cassi φ-attractor)}$$

This is a parameter-free prediction of the two-fluid PDE conversion mechanism: the cosmic ratio $r = \langle EY\rangle/\langle EI\rangle$ evolves from the gap-derived $r_0 = 0.0472$ ($E_I/E_Y \approx 21$) at $a_0 = 0.01$ toward the φ-attractor, producing the above $w_0$.

### 1.2 DESI DR2 Primary Paper

**Source:** DESI Collaboration, 2025. "DESI DR2 Results II: Measurements of Baryon Acoustic Oscillations and Cosmological Constraints." arXiv:2503.14738.

| Result | Value | Reference |
|---|---|---|
| ΛCDM rejection (DESI BAO + CMB) | **3.1σ** preference for dynamical DE | Abstract |
| ΛCDM rejection (DESI + CMB + SNe) | **2.8–4.2σ** depending on SNe sample | Abstract |
| Best-fit quadrant | $w_0 > -1$, $w_a < 0$ (quintom B) | §V, Fig. 13 |
| Neutrino mass upper limit (ΛCDM) | $\sum m_\nu < 0.064$ eV (95% CL) | Abstract |
| Neutrino mass upper limit ($w_0 w_a$) | $\sum m_\nu < 0.16$ eV (95% CL) | Abstract |

From the DESI DR2 + CMB + SNe combined analysis, the best-fit ($w_0$, $w_a$) lies in the quadrant $w_0 > -1$, $w_a < 0$. Cassi shares the $w_0 > -1$ side ($w_0 = -0.87$); the Calibrated baseline predicts $w_a > 0$ ($+0.012$)—the opposite sign of the DESI preference—but with the ratified conversion→expansion coupling's **stable realization** (the C1 friction closure—10/12) the late-time $r$ freezes at $r_* \approx 0.9503$ (the collapse at $z \approx 61$) and the DESI-window fit is exactly $(w_0, w_a) = (-1, 0)$—4.17σ/2.61σ from DESI; the earlier $w_a \approx -0.38$ (B2; $1.25\sigma$) describes the unstable realization (density blow-up), not the theory's prediction. The CPL parametrization used throughout is $w(a) = w_0 + w_a(1 - a)$.

### 1.3 Independent Analysis Paper

**Source:** Gu, G., Wang, X., Wang, Y. et al., 2025. "Dynamical dark energy in light of the DESI DR2 baryonic acoustic oscillations measurements." Nature Astronomy 9, 1879–1889. doi:10.1038/s41550-025-02669-6.

| Dataset | SNR of $w \neq -1$ | ΛCDM significance |
|---|---|---|
| DESI DR2 BAO only | 2.6σ | ~1.5σ |
| DESI DR2 + Pantheon+ | 3.7σ | >2σ |
| DESI DR2 + Union3 | 4.3σ | >2σ |
| DESI DR2 + DESY5 | 4.5σ | >2σ |

From the non-parametric Bayesian reconstruction of $w(z)$ with a Horndeski-motivated correlation prior. Consistent with the companion DESI DR2 paper—same conclusion of quintom B ($w_0 > -1$, $w_a < 0$).

### 1.4 Composite Constraints from Project

The constraints used here are the published DESI DR2 values below; the two-fluid solver's own constants (e.g. `TARGET_W0` in `two-fluid/calibrate_initial_ratio.py`) are internal calibration targets, not measurements, and play no role in the comparison.

Verified anchors from the DESI DR2 papers (arXiv:2503.14738; astrobites 2025-10-06):
- BAO+CMB prefers $w_0 > -1$, $w_a < 0$ at **3.1σ**; with SNe compilations the preference is 2.8–4.2σ.
- Pivot values from the paper: $w_p = -1.024 \pm 0.043$ and $-0.954 \pm 0.024$.
- Widely reported Table 9 values [INFERENCE, per-table note]: $w_0 \approx -0.72 \pm 0.09$, $w_a \approx -0.73 \pm 0.28$ (BAO+CMB+Pantheon+); $w_a$ spans ≈ −0.6 to −1.1 across SNe compilations.

### 1.5 Comparison with Cassi

| Quantity | DESI DR2 Measurement | Cassi Prediction | Deviation |
|---|---|---|---|
|| $w_0$ | $\approx -0.75 \pm 0.06$ (Table 9 [INF]) | $-0.87$ (Calibrated baseline; $-0.97$ at fixed $r_0$ with the B2 coupling; **$-1.000$ with the stable realization—12**) | **$2\sigma$** baseline; **$3.6\sigma$** (B2, fixed $r_0$); **$4.17\sigma$** (stable realization—12) |
|| $w_a$ | $\approx -0.73 \pm 0.28$ (Table 9 [INF]) | $+0.012$ (baseline); **$-0.38$** (B2, unstable); **$(-1, 0)$ pure-Λ window** (stable realization—12) | **$2.7\sigma$** baseline; **$1.25\sigma$** (B2, unstable); **$2.61\sigma$** (stable realization—12) |

The Cassi structural $w_0 = -0.87$ (Yang-fraction-weighted coupling; `two-fluid/calibrate_initial_ratio_xi_v2.py`) sits $2\sigma$ from the DESI best-fit $w_0 \approx -0.75$, and $w_a = +0.012$ sits $2.7\sigma$ ($2.2$–$3.2\sigma$ across the SNe range) from $w_a \approx -0.73$. With the ratified conversion→expansion coupling (Hypothesized, zero free constants—08 §C.6), the unstable B2 realization's CPL-fitted shifts are $\Delta w_0 = -0.098$, $\Delta w_a = -0.393$ (the term's exact two-field dynamics; bracket $\Delta w_a \in [-0.61, -0.38]$ across routes): $w_a' = -0.38$ ($1.25\sigma$) and $w_0' = -0.97$ at fixed $r_0$ ($3.6\sigma$)—but B2's density blows up (10 §4). The term's stable realization (the C1 friction closure—10/12) instead gives a **pure-Λ window fit $(w_0, w_a) = (-1, 0)$ exactly** (4.17σ/2.61σ from DESI; $w_0$ is a Calibrated target—ledger §10—and $r_0$ re-tuning is closed negatively under the stable realization, 12 §4.1). See §6.

---

## 2. Milky Way Rotation Curve

### 2.1 Eilers et al. (2019)—Primary Reference

**Source:** Eilers, A.-C., Hogg, D. W., Rix, H.-W., & Ness, M. 2019. "The Circular Velocity Curve of the Milky Way from 5 to 25 kpc." ApJ 871, 120. arXiv:1810.09466.

| Quantity | Value | Notes |
|---|---|---|
| $v_c(R_\odot)$ | $229.0 \pm 0.2$ km/s | Formal statistical uncertainty |
| $R_\odot$ | 8.0 kpc (assumed) | Galactocentric distance of the Sun |
| Systematic on $v_c(R_\odot)$ | $\sim 2$–$5\%$ | From distance scale and potential modeling |
| Slope $dv_c/dR$ (5–25 kpc) | $-1.7 \pm 0.1$ km/s/kpc | Statistical; systematic $\pm 0.46$ km/s/kpc |
| Virial mass $M_{\text{vir}}$ | $(7.25 \pm 0.26) \times 10^{11} M_\odot$ | Dark halo mass within virial radius |
| Local DM density | $0.30 \pm 0.03$ GeV/cm³ | At $R_\odot$ |

**Method:** Jeans equation modeling of $\gtrsim 23,000$ luminous red-giant stars with 6D phase-space coordinates from APOGEE + WISE + 2MASS + Gaia. The rotation curve is gently but significantly declining beyond 5 kpc.

The uncertainty at $R > 8$ kpc grows with radius. By $R = 25$ kpc, the fractional uncertainty is roughly $\sim 10\%$ from the combination of statistical scatter and systematic effects.

### 2.2 Keplerian Decline—Jiao et al. (2023)

**Source:** Jiao, Y. et al. 2023. "Detection of the Keplerian decline in the Milky Way rotation curve." A&A 678, A145.

| Quantity | Value |
|---|---|
| Gradient 19.5–26.5 kpc | $\Delta v \approx -30$ km/s |
| Mean gradient 19.5–26.5 kpc | $\sim -4.3$ km/s/kpc |
| $v_c$ at 25 kpc | $\sim 200$ km/s |

This paper finds a **sharper decline** beyond 19 kpc than the Eilers extrapolation would suggest. The measured $\sim 30$ km/s drop over 7 kpc indicates the rotation curve is NOT flat at large radii—consistent with the baryonic contribution falling off.

### 2.3 Zhou et al. (2023/2024)—Extended to 30 kpc

**Source:** Zhou, Y. et al. 2023. "The dark matter profile of the Milky Way inferred from its circular velocity curve." MNRAS 528, 693. 

Extends the rotation curve measurement to $\sim 30$ kpc using Gaia EDR3 + APOGEE data. The circular velocity at 30 kpc is approximately:

$$v_c(30\text{ kpc}) \approx 180 \text{–} 200 \text{ km/s}$$

with uncertainties of $\sim 10 \text{–} 15\%$ ($\approx \pm 20$ km/s). The rotation curve shows a gradual decline, consistent with both the Eilers (2019) and Jiao (2023) results but extending to larger radius.

### 2.4 Newtonian Baseline from Baryons

For comparison with the Cassi mechanism, the expected Newtonian circular velocity from baryonic mass alone (stars + gas, no dark matter) at 30 kpc is:

$$v_{\text{N, bary}}(30\text{ kpc}) \sim 60 \text{–} 80 \text{ km/s}$$

(Estimated from MW baryonic mass distribution models. The exact value depends on the assumed stellar disk + bulge + gas profile and has $\sim 20\%$ uncertainty.)

The observed total circular velocity is therefore a factor of:

$$\frac{v_c(30\text{ kpc})}{v_{\text{N, bary}}(30\text{ kpc})} \approx \frac{190 \pm 20}{70 \pm 15} \approx 2.7 \pm 0.5$$

**Wait—this ratio is larger than the naive 2.0× often quoted for $v(30\text{ kpc})/v(8\text{ kpc})$ because at 30 kpc the Newtonian baryonic contribution has fallen much more steeply than the total rotation curve.**

### 2.5 Summary Table

| Quantity | Value | Uncertainty (1σ) | Source |
|---|---|---|---|
| $v_c(R_\odot)$ | $229.0$ km/s | $\pm 0.2$ stat, $\pm \sim 5\%$ sys | Eilers 2019 |
| $dv_c/dR$ (5–25 kpc) | $-1.7$ km/s/kpc | $\pm 0.1$ | Eilers 2019 |
| $v_c(25\text{ kpc})$ | $\sim 200$ km/s | $\sim \pm 15$ km/s | Eilers 2019 |
| $v_c(30\text{ kpc})$ | $\sim 190$ km/s | $\sim \pm 20$ km/s | Zhou+ 2023 |
| $v_{\text{N,bary}}(30\text{ kpc})$ | $\sim 70$ km/s | $\sim \pm 15$ km/s | MW baryon models |
| DM boost required | $\mathbf{\sim 2.7\pm 0.5}$ | | Ratio of observed to baryonic |

### 2.6 Cassi Rotation Curve Prediction

The Cassi force law (`cassi-physics.md`) uses Qi-enhanced gravity:

$$\mathbf{F}_{ij} = -G\,\alpha_i(1+(\varphi^{6}-1)q_i)\,M_i M_j\frac{\mathbf{r}_{ij}}{|\mathbf{r}_{ij}|^3}$$

where $\xi = \varphi^6 \approx 17.944$ and $\alpha_i$ is the Yang fraction of body $i$. The circular velocity enhancement is:

$$\frac{v_C}{v_B} = \sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)}$$

For Milky Way halo parameters ($\alpha_{\text{halo}} \approx 0.7$, $q \approx 0.7$):

$$\frac{v_C}{v_B} \approx \sqrt{0.7 \times (1 + 16.944 \times 0.7)} = \sqrt{9.00} \approx \mathbf{3.0}$$

($\alpha_{\text{halo}}$ is the halo-regime Yang fraction from the SPARC rotation-curve fits, distinct from the equilibrium value $\alpha_0 = \varphi^{-3}$; the independent fit in `foundations/phi_attractor_synthesis.md` Path 8 gives 2.89× at 30 kpc with the pre-chord $\xi = \varphi^6$ script coupling.)

Predicted: $v_{\text{Cassi}}(30\text{ kpc}) \approx 3.0 \times 70 \approx 210$ km/s.
Observed (Zhou+ 2023): $v_c(30\text{ kpc}) \approx 190 \pm 20$ km/s.

**Result: consistent within ~1.0σ** (210 vs 190 ± 20). The observed boost of $2.7 \pm 0.5$ overlaps the Cassi prediction range $2.8$–$3.0\times$ from the $(\varphi^{6}-1)q$ coupling.

---

## 3. Key Takeaways

| Observable | Cassi covers | Not covered | Decision required |
|---|---|---|---|
| $w_0 = -0.87$ (Calibrated; $2\sigma$ baseline; $3.6\sigma$ at fixed $r_0$ with the B2 coupling; $-1.000$ with the stable realization—12) | Tension ($w_0$; $r_0$ re-tuning closed negatively under the stable realization—12); **$w_a$: $2.7\sigma$ baseline; $1.25\sigma$ (B2, unstable); $2.61\sigma$ (stable realization: pure-Λ window—12)** | $w_a = +0.012$ (baseline) → $-0.38$ (B2, unstable) → **$(w_0, w_a) = (-1, 0)$** (stable realization—12) | **Tension** ($w_0$) / **Tension** ($w_a$; the B2 1.25σ described the unstable realization, 12) |
| $\Omega_m$ / $H_0$ compatibility | Pipeline CMB-inferred $H_0 \approx 65.8$ km/s/Mpc | Tension with CMB | Full $H(z)$ fit pending (C3/T4) |
| $v_c(30\text{ kpc})$ vs baryons | $v_C/v_B = 2.8$–$3.0$ (matches $2.7\pm0.5$ observed within ~0.4σ) |—| **Consistent** |

**Sources last accessed:** 2026-07-19.

---

## 4. CMB Large-Angle Anomalies—Bubble-Boundary Axis

### 4.1 The "Axis of Evil" (Quadrupole-Octopole Alignment)

**Source:** Copi, Huterer, Schwarz, & Starkman (2006-2010); Land & Magueijo (2005); Jones et al. (2023); Herold et al. (2025).

The CMB quadrupole ($\ell=2$) and octopole ($\ell=3$) modes are anomalously aligned along a preferred axis at galactic coordinates:

$$\text{Axis direction: } (l, b) = (260\degree, +60\degree)$$

| Feature | Value | Reference |
|---|---|---|
| Joint anomaly significance | 5.4σ | Jones et al. (2023) |
| Independent anomaly (1% mask) | 3.0σ | Herold et al. (2025) |
| Quadrupole power suppression | ~30% below ΛCDM | WMAP/Planck |
| Axis-dipole angular separation | 12.2° | Computed from measured direction vectors |
| Axis-Virgo separation | 17° | This work |
| Axis-cold spot separation | 124° | This work |

The axis is NOT aligned with the CMB cold spot or the Eridanus supervoid, ruling out a simple local-void explanation. The 5.4σ joint significance across multiple large-angle anomalies (Jones+ 2023) is an a-posteriori statistic—the alignment was discovered in the data, so a look-elsewhere correction across multipoles applies—but the anomaly remains persistent.

### 4.2 Cassi Mechanism (Hypothesized): Bubble-Boundary Triaxial Axis

**Tier: Calibrated (12.2° angle, computed from data) / Hypothesized (boundary mechanism).** The 12.2° dipole↔quadrupole separation is a *measured* property of the CMB: the angle is computed from the measured multipole direction vectors—the CMB dipole at $(l,b) \approx (264\degree, +48\degree)$ and the quadrupole-octopole axis at $(l,b) = (260\degree, +60\degree)$—so the value is calibrated from the data, not predicted (`two-fluid/run_cmb_lowl_pipeline.py`). The framework's candidate mechanism is the triaxial bubble geometry at cascade step 285 (registry C10; `foundations/refined-numeric-predictions.md` §2.3; `foundations/dimensionful-cascade.md` §8.3): adjacent bubbles at identical $w = 5$—all bubbles share the derived Wu Xing number, with no spatial $w$ variation—sit at $\varphi$-spaced chord-lattice intervals, and their shared boundary normal defines a preferred direction at $\ell < 5$. This mechanism is **Hypothesized**: its boundary orientation is chosen to match the measured axis, so it currently explains the direction post-hoc rather than predicting it.

The mechanism's claims:

1. **Preferred axis** at the largest angular scales ($\ell < 5$), fading at $\ell > 5$
2. **Dipole↔quadrupole separation of 12.2°** (measured): the angular separation between the CMB dipole (Yang axis) and the quadrupole-octopole axis (boundary normal); the value follows from the measured vectors, not from the geometry
3. **E-mode polarization alignment**: the CMB E-mode quadrupole/octopole MUST show the same axis if the anomaly is primordial (testable by Simons Observatory and LiteBIRD)
4. **Bulk flows** along the preferred axis ($\sim 500$–$2000$ km/s at Gpc scales)

**Status: measured alignment, mechanism unconfirmed.** The 5.4σ is the data's a-posteriori significance: the alignment was discovered in the data (WMAP; Land & Magueijo 2005), so a look-elsewhere correction across multipoles applies to the claimed significance. The bubble-boundary mechanism is a candidate whose boundary normal is fitted to the measured axis—not yet a prediction. Elevation requires an a priori derivation of the boundary normal from the cascade: the condensation field's orientation at rung 285 (the bubble normal direction relative to the galaxy/CMB frame), computed without taking the measured axis as input. The E-mode polarization test (Simons Observatory, LiteBIRD) is falsifiable and independent of the orientation question.

---

## 5. Key Takeaways (Updated)

| Observable | Cassi covers | Not covered | Decision required |
|---|---|---|---|
| $w_0$ and $w_a$ | $w_0 = -0.87$ (Calibrated; 2σ baseline); $w_a = +0.012$ (baseline) → $-0.38$ (B2, unstable) → **pure-Λ $(-1, 0)$ window (stable realization—10/12)** | $w_0$: $3.6\sigma$ at fixed $r_0$ (B2); $4.17\sigma$ (stable realization); $w_a$: 5-channel/Wu-Xing shifts Hypothesized (ODE pending) | **Tension** ($w_0$) / **Tension** ($w_a$; stable realization—12; the B2 1.25σ described the unstable realization)—`two-fluid/calibrate_initial_ratio_xi_v2.py`, 08 §C.6, 12 |
| $\Omega_m$ / $H_0$ compatibility | Pipeline CMB-inferred $H_0 \approx 65.8$ km/s/Mpc | Tension with CMB | Full $H(z)$ fit pending (C3/T4) |
| $v_c(30\text{ kpc})$ vs baryons | $v_C/v_B = 2.8$–$3.0$ (matches $2.7\pm0.5$ observed within ~0.4σ) |—| **Consistent** |
| CMB axis of evil (5.4σ, a-posteriori) | Bubble-boundary triaxial axis (12.2° alignment; **Calibrated** angle, **Hypothesized** mechanism) | Scale-dependence unconfirmed; boundary orientation fitted to measured axis | Simons Obs. E-mode test |

---

## 6. The w_a Tension: Cassi Prediction vs DESI DR2

### 6.1 The Structural Prediction and the Coupling

The Cassi two-fluid PDE predicts $w_a = +0.44$ from the bare conversion dynamics ($H_{\text{bare}}$ only). The comparison anchor is the widely reported Table 9 DESI value $w_a \approx -0.73 \pm 0.28$ [INFERENCE]. The pure-Yang coupling form $\sqrt{1+(\varphi^{6}-1)q}$ is inconsistent with the galactic-sector convention, where the boost applies to the Yang component only; the Yang-fraction-weighted form is used here (§6.2).

Invariance tests (λ-independence re-verified with the Yang-fraction-weighted coupling):

1. **$\lambda$-independence**: $w_a$ is unchanged across $\lambda \in [0.01, 0.05]$
2. **Qi gate $\alpha$-independence**: $w_a$ unchanged across $\alpha \in [0.01, 5.0]$
3. **Spatial boost falsified**: $B = 1.003$ at $N=32$—spatial structure does not enhance conversion
4. **$H_{\text{struct}}$ decays at late times**: structural Hubble mode vanishes as $r \to \varphi$

**Yang-fraction-weighted coupling.** The coupling verified in rotation curves boosts the Yang component only ($v^2 = G[M_{\rm bar} + (1+(\varphi^{6}-1)q)M_Y]/r$, SPARC v5–v8), so the homogeneous analogue weights by the attractor Yang fraction $\alpha_w = r/(1+r) = \varphi^{-1} \approx 0.618$: $H_{\rm eff}^2 = H_{\rm bare}^2\,[1 + (\varphi^{6}-1)q \cdot \alpha_w]$. Under this form (`two-fluid/calibrate_initial_ratio_xi_v2.py`):

| Mode | $w_0$ | $w_a$ |
|---|---|---|
| Bare | $-0.856$ | $+0.457$ |
| v1 pure-Yang form $\sqrt{1+(\varphi^{6}-1)q}$ | $-0.862$ | $+0.068$ |
| **Yang-fraction-weighted form** | **$-0.872$** | **$+0.012$** |

(Gap-derived structural $r_0 = \varphi^{-5}/(2-\varphi^{-5}) = 0.0472$; values are λ-independent.) The Yang-fraction weighting nearly cancels the bare $+0.44$: $w_a = +0.012$. *(ODE values above were computed with the pre-chord $\xi = \varphi^6$ coefficient; the $(\varphi^{6}-1)$ re-run is pending—flagged, not asserted.)* With the Table 9 DESI anchor (§1.4), the comparison is:

### 6.2 Comparison with DESI DR2

| Quantity | Cassi Prediction | DESI DR2 | Tension |
|---|---|---|---|
| $w_0$ | $-0.87$ (structural, pinned) | $\approx -0.75 \pm 0.06$ (Table 9 [INF]) | **$2\sigma$** |
| $w_a$ (bare) | $+0.46$ | $\approx -0.73 \pm 0.28$ | $4.2\sigma$ |
| $w_a$ (Yang-fraction-weighted) | $+0.012$ | $\approx -0.73 \pm 0.28$ | **$2.7\sigma$** ($2.2$–$3.2\sigma$ across the SNe range) |

The Yang-fraction-weighted coupling halves the $w_a$ tension (4.2σ → 2.7σ) but does not resolve it. With the ratified conversion→expansion coupling, the unstable B2 realization drops the residual $w_a$ tension to $1.25\sigma$ ($w_a' = -0.38$); the term's **stable realization** (the C1 friction closure—10/12) instead freezes $r$ at $r_* \approx 0.9503$ (the collapse at $z \approx 61$) and gives a **pure-Λ window fit $(w_0, w_a) = (-1, 0)$—4.17σ/2.61σ from DESI**—the pure-Λ identified with the frozen coherent-phase energy (16-qi-field.md: per-cell constant under the friction closure ⟹ w ≡ −1 exactly; the coherent phase carries 78% of the expansion rate); the B2 values describe the unstable realization and are superseded for the theory's prediction. The Cassi $w_0$ is additionally pinned: it stays in $[-0.872, -0.868]$ across $r_0 \in [0.001, 0.08]$ (no-source); under the stable realization $w_0 = -1.000$ for every $r_0 \in [0.01, 1.1]$—$r_0$ re-tuning is closed negatively (12 §4.1), not an open calibration adjustment.

### 6.3 Resolution Pathways—Status

| Mechanism | Status | $\Delta w_a$ |
|----------|:---:|:---:|
| **Qi-gravity $\xi = \varphi^6$ in $H_{\rm eff}$ (Yang-fraction-weighted form)** | **Verified** (ODE `two-fluid/calibrate_initial_ratio_xi_v2.py`) | **$-0.445$** |
| **Ratified conversion→expansion coupling** ($V_{\text{new}} = \lambda\tilde{h} + \lambda\varphi^{-2}/d$, zero free constants—08 §A.2) | **Hypothesized—August 2026** (exact two-field dynamics, B2—unstable); **stable realization: C1 friction closure** (10/12) | **$-0.393$** (B2, unstable; bracket $-0.61$…$-0.38$ across routes); stable realization: **pure-Λ window** $(w_0, w_a) = (-1, 0)$ |
| 5-channel adiabatic gate | Documented, ODE pending | ${\sim} -0.10$ (Hypothesized) |
| Wu Xing control-release | Documented, ODE pending | ${\sim} -0.05$ (Hypothesized) |

With the ratified coupling, the unstable B2 realization gives $w_a' = +0.012 - 0.393 = -0.38$: $1.25\sigma$ from DESI $w_a \approx -0.73$ ($0.45\sigma$ on the first-order Route A)—not the theory's prediction, since B2's density blows up (10). The term's **stable realization** (the C1 friction closure—10/12) gives the pure-Λ window fit $(w_0, w_a) = (-1, 0)$—4.17σ/2.61σ from DESI—and $w_0$ is pinned at $-1.000$ for every $r_0 \in [0.01, 1.1]$ ($r_0$ re-tuning closed negatively, 12 §4.1).

### 6.4 Status

**Tension (Calibrated baseline) / tension (stable realization).** With sourced DESI anchors and the galactic-consistent coupling form, the Cassi baseline is $w_0 = -0.87$ (2σ from DESI) and $w_a = +0.012$ (2.7σ from DESI)—a real tension, roughly halved but not resolved by the $\xi = \varphi^6$ coupling. With the ratified conversion→expansion coupling (Hypothesized—August 2026, zero free constants—08 §C.6), the unstable B2 realization's CPL-fitted shifts are $\Delta w_0 = -0.098$, $\Delta w_a = -0.393$ (bracket $-0.61$…$-0.38$): $w_a' = -0.38$ at $1.25\sigma$ (the sign matches the DESI preference) and $w_0' = -0.97$ at fixed $r_0$ ($3.6\sigma$)—but B2's density blows up. The term's **stable realization** (the C1 friction closure—10/12) freezes $r$ at $r_* \approx 0.9503$ (the collapse at $z \approx 61$) and gives a pure-Λ DESI-window fit $(w_0, w_a) = (-1, 0)$ exactly—4.17σ/2.61σ from DESI; the B2 values are superseded for the theory's prediction. $w_0$ is a Calibrated target (ledger §10); under the stable realization $w_0 = -1.000$ for every $r_0 \in [0.01, 1.1]$, so $r_0$ re-tuning is closed negatively (12 §4.1). Two structural features distinguish the framework from the DESI-preferred region: (1) the Cassi $w(z)$ **never phantom-crosses** (min $w = -0.85$ over $a \in [0.3, 1]$; the conversion dynamics cannot produce $w < -1$), while the DESI best fit crosses $w = -1$ at $z \approx 0.5$ ($w_p = -1.024 \pm 0.043$); (2) $w_0$ is pinned near $-0.87$ regardless of the initial ratio ($-1.000$ with the stable realization—12), so the model is more Λ-like than the data prefer. Script: `two-fluid/calibrate_initial_ratio_xi_v2.py`.

**Test scripts**: `two-fluid/run_pde_wa_test.py` (ODE solver), `two-fluid/run_spatial_boost.py` (spatial structure test).
**Sources last accessed:** 2026-07-19.

### 6.5 The Bubble Lattice and the DESI Average

DESI averages over ~20 (Gpc/h)$^3$ of the visible universe; the infinite bubble lattice (`foundations/bubble-lattice-fabric.md`) is periodic and anisotropic, so the question is which lattice structure survives the average. The full analysis is `cosmology/desi-lattice-averaging.md` (§2, §5); the verdict relevant to this section: **the lattice cannot bias the CPL fit into the DESI region.** A fixed-scale wiggle in $D_A(z)$ is suppressed by the line-of-sight integral and shell averaging to $\delta D/D \lesssim 0.1\%$, biasing $w_a$ by ≲ 0.01; closing the remaining $2.61\sigma$ gap (the stable realization's pure-Λ window, 12) would require $\delta D/D \gtrsim 20\%$, ruled out by the smoothness of DESI's own $D_A(z)$. The lattice instead imprints a powder comb on $P(k)$ (the wake-wave prediction, now with predicted multiplicities; DESI LRG bound $A \lesssim 2.6\%$, $p = 0.08$), suppresses sample variance ~10× vs mocks, and predicts NGC–SGC mode correlation. The $w_0 = -0.87$/$w_a = +0.012$ baseline tension verdict stands; the $w_a$ side drops to $1.25\sigma$ with the ratified conversion→expansion coupling (§6.3).

The $1.70\times$ edge anisotropy is a universal lattice signature—see `foundations/bubble-lattice-fabric.md` §4.2.
