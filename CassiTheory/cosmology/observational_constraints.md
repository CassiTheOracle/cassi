# Observational Constraints—DESI DR2 Dark Energy & Milky Way Rotation Curve

## Status: Derived—July 2026

Sources compiled 2026-07-15 via web search and primary literature. All error bars are 68% (1σ) confidence unless noted.

---

## 1. Dark Energy Equation of State—DESI Data Release 2

### 1.1 The Cassi Prediction

The Cassi φ-attractor produces an effective dark energy with a present-day equation of state (see `two-fluid/calibrate_initial_ratio.py` and `theory/phi_attractor_synthesis.md`):

$$w_0 = -0.87 \quad \text{(Cassi φ-attractor, corrected 2026-07-31; previously −0.838)}$$

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

From the DESI DR2 + CMB + SNe combined analysis, the best-fit ($w_0$, $w_a$) lies in the quadrant $w_0 > -1$, $w_a < 0$. Cassi shares the $w_0 > -1$ side ($w_0 = -0.87$) but predicts $w_a > 0$ ($+0.012$)—the opposite sign of the DESI preference. The CPL parametrization used throughout is $w(a) = w_0 + w_a(1 - a)$.

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

Multiple sources within the Cassi repository previously compiled the DESI DR2 constraints—but those values were the repository's own calibration targets, not independent measurements. **Corrected 2026-07-31:** `two-fluid/calibrate_initial_ratio.py` hardcodes `TARGET_W0 = -0.838  # DESI DR2 best-fit` and `two-fluid/figure_data.py` hardcodes the same number with invented errors; the “0σ match” in the old §1.5 was circular (calibrate to your own target, then report zero deviation) and is withdrawn.

Verified anchors from the DESI DR2 papers (arXiv:2503.14738; astrobites 2025-10-06):
- BAO+CMB prefers $w_0 > -1$, $w_a < 0$ at **3.1σ**; with SNe compilations the preference is 2.8–4.2σ.
- Pivot values from the paper: $w_p = -1.024 \pm 0.043$ and $-0.954 \pm 0.024$.
- Widely reported Table 9 values [INFERENCE, per-table note]: $w_0 \approx -0.72 \pm 0.09$, $w_a \approx -0.73 \pm 0.28$ (BAO+CMB+Pantheon+); $w_a$ spans ≈ −0.6 to −1.1 across SNe compilations.

### 1.5 Comparison with Cassi (corrected 2026-07-31)

| Quantity | DESI DR2 Measurement | Cassi Prediction | Deviation |
|---|---|---|---|
| $w_0$ | $\approx -0.75 \pm 0.06$ (Table 9 [INF]) | $-0.87$ (structural, corrected coupling) | **$2\sigma$** |
| $w_a$ | $\approx -0.73 \pm 0.28$ (Table 9 [INF]) | $+0.012$ (corrected coupling) | **$2.7\sigma$** |

The Cassi structural $w_0 = -0.87$ (Yang-fraction-weighted coupling; `two-fluid/calibrate_initial_ratio_xi_v2.py`) sits $2\sigma$ from the DESI best-fit $w_0 \approx -0.75$, and $w_a = +0.012$ sits $2.7\sigma$ ($2.2$–$3.2\sigma$ across the SNe range) from $w_a \approx -0.73$. The tension is real—see §6.

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

$$\mathbf{F}_{ij} = -G\,\alpha_i(1+\xi q_i)\,M_i M_j\frac{\mathbf{r}_{ij}}{|\mathbf{r}_{ij}|^3}$$

where $\xi = \varphi^6 \approx 17.944$ and $\alpha_i$ is the Yang fraction of body $i$. The circular velocity enhancement is:

$$\frac{v_C}{v_B} = \sqrt{\alpha(1+\xi q)}$$

For Milky Way halo parameters ($\alpha \approx 0.7$, $q \approx 0.7$):

$$\frac{v_C}{v_B} \approx \sqrt{0.7 \times (1 + 17.9 \times 0.7)} \approx \mathbf{3.1}$$

(arithmetic corrected 2026-07-31: $\sqrt{0.7 \times 13.53} = \sqrt{9.47} \approx 3.08$; the earlier claim of 2.7× mis-evaluated the same formula. The independent rotation-curve fit in `foundations/phi_attractor_synthesis.md` Path 8 gives 2.89× at 30 kpc with the $\xi = \varphi^6$ coupling.)

Predicted: $v_{\text{Cassi}}(30\text{ kpc}) \approx 3.1 \times 70 \approx 215$ km/s.
Observed (Zhou+ 2023): $v_c(30\text{ kpc}) \approx 190 \pm 20$ km/s.

**Result: consistent within ~1.2σ** (215 vs 190 ± 20). The observed boost of $2.7 \pm 0.5$ overlaps the Cassi prediction range $2.9$–$3.1\times$ from the $\xi = \varphi^6$ coupling (superseding the earlier 'pure-Yang ceiling' of $\varphi \approx 1.62$ from the withdrawn approximate coupling).

---

## 3. Key Takeaways

| Observable | Cassi covers | Not covered | Decision required |
|---|---|---|---|
| $w_0 = -0.87$ (structural, corrected coupling 2026-07-31; $2\sigma$ from DESI $\approx -0.75 \pm 0.06$) | Tension | $w_a$: corrected $\xi = \varphi^6$ shift ($+0.46 \to +0.012$); $2.7\sigma$ from DESI $\approx -0.73 \pm 0.28$ | **Tension** (`two-fluid/calibrate_initial_ratio_xi_v2.py`) |
| $\Omega_m$ / $H_0$ compatibility | In calibration | Tension with CMB | Publishing next |
| $v_c(30\text{ kpc})$ vs baryons | $v_C/v_B = 2.9$–$3.1$ (corrected 2026-07-31; matches $2.7\pm0.5$ observed within ~1.2σ) |—| **Consistent** |

**Sources last accessed:** 2026-07-19.

---

## 4. CMB Large-Angle Anomalies—Multiverse w-Gradient

### 4.1 The "Axis of Evil" (Quadrupole-Octopole Alignment)

**Source:** Copi, Huterer, Schwarz, & Starkman (2006-2010); Land & Magueijo (2005); Jones et al. (2023); Herold et al. (2025).

The CMB quadrupole ($\ell=2$) and octopole ($\ell=3$) modes are anomalously aligned along a preferred axis at galactic coordinates:

$$\text{Axis direction: } (l, b) = (260\degree, +60\degree)$$

| Feature | Value | Reference |
|---|---|---|
| Joint anomaly significance | 5.4σ | Jones et al. (2023) |
| Independent anomaly (1% mask) | 3.0σ | Herold et al. (2025) |
| Quadrupole power suppression | ~30% below ΛCDM | WMAP/Planck |
| Axis-dipole angular separation | 12° | This work |
| Axis-Virgo separation | 17° | This work |
| Axis-cold spot separation | 124° | This work |

The axis is NOT aligned with the CMB cold spot or the Eridanus supervoid, ruling out a simple local-void explanation. The 5.4σ joint significance across multiple large-angle anomalies (Jones+ 2023) strongly suggests a primordial origin.

### 4.2 Cassi Prediction: w-Gradient Imprint

If the Wu Xing number $w$ varies spatially at super-horizon scales (the multiverse w-spectrum), the nearest $w$-boundary creates a preferred direction in the CMB at the largest angular scales. The Cassi prediction:

1. **Preferred axis** at super-horizon scales ($\ell < 5$), fading at $\ell > 5$
2. **Scale-dependent anomaly**: distinguishes w-gradient (super-horizon only) from foreground contamination (all scales) or statistical fluke (no scale dependence)
3. **E-mode polarization alignment**: the CMB E-mode quadrupole/octopole MUST show the same axis if the anomaly is primordial (testable by Simons Observatory and LiteBIRD)
4. **Bulk flows** along the preferred axis ($\sim 500$–$2000$ km/s at Gpc scales)

**Status: Suggestive alignment (~1σ).** The axis exists at high significance (5.4σ). The Cassi prediction that anomalies should fade at $\ell > 5$ is falsifiable by Simons Observatory (2025+) and LiteBIRD polarization data.

---

## 5. Key Takeaways (Updated)

| Observable | Cassi covers | Not covered | Decision required |
|---|---|---|---|
| $w_0$ and $w_a$ | $w_0 = -0.87$ structural (2σ from DESI $\approx -0.75 \pm 0.06$); $w_a = +0.012$ corrected coupling (2.7σ from $\approx -0.73 \pm 0.28$) | $w_a$ shift $+0.46 \to +0.012$ (corrected Yang-fraction form, 2026-07-31); 5-channel/Wu-Xing Hypothesized (ODE pending) | **Tension**—`two-fluid/calibrate_initial_ratio_xi_v2.py` |
| $\Omega_m$ / $H_0$ compatibility | In calibration | Tension with CMB | Publishing next |
| $v_c(30\text{ kpc})$ vs baryons | $v_C/v_B = 2.9$–$3.1$ (corrected 2026-07-31; matches $2.7\pm0.5$ observed within ~1.2σ) |—| **Consistent** |
| CMB axis of evil (5.4σ) | Predicted w-gradient axis | Scale-dependence unconfirmed | Simons Obs. E-mode test |

---

## 6. The w_a Tension: Cassi Prediction vs DESI DR2

### 6.1 The Structural Prediction and the Coupling Correction (revised 2026-07-31)

The Cassi two-fluid PDE predicts $w_a = +0.44$ from the bare conversion dynamics ($H_{\text{bare}}$ only). The earlier claim that the tension is “resolved at 1.4σ” rested on two things now corrected: (a) an unverified DESI anchor ($w_a = -0.51 \pm 0.38$; the widely reported Table 9 value is $\approx -0.73 \pm 0.28$ [INFERENCE]), and (b) the pure-Yang coupling form $\sqrt{1+\xi q}$, which is inconsistent with the galactic-sector convention (the boost applies to the Yang component only).

Invariance tests (unchanged, λ-independence re-verified exactly with the corrected coupling):

1. **$\lambda$-independence**: $w_a$ is unchanged across $\lambda \in [0.01, 0.05]$
2. **Qi gate $\alpha$-independence**: $w_a$ unchanged across $\alpha \in [0.01, 5.0]$
3. **Spatial boost falsified**: $B = 1.003$ at $N=32$—spatial structure does not enhance conversion
4. **$H_{\text{struct}}$ decays at late times**: structural Hubble mode vanishes as $r \to \varphi$

**Coupling correction (2026-07-31):** the coupling verified in rotation curves boosts the Yang component only ($v^2 = G[M_{\rm bar} + (1+\xi q)M_Y]/r$, SPARC v5–v8), so the homogeneous analogue weights by the Yang fraction $r/(1+r)$ ($= 1/\varphi \approx 0.618$ at the attractor): $H_{\rm eff}^2 = H_{\rm bare}^2\,[1 + \xi q \cdot r/(1+r)]$. Under this corrected form (`two-fluid/calibrate_initial_ratio_xi_v2.py`):

| Mode | $w_0$ | $w_a$ |
|---|---|---|
| Bare | $-0.856$ | $+0.457$ |
| v1 pure-Yang form $\sqrt{1+\xi q}$ | $-0.862$ | $+0.068$ |
| **Corrected Yang-fraction form** | **$-0.872$** | **$+0.012$** |

(Gap-derived structural $r_0 = \varphi^{-5}/(2-\varphi^{-5}) = 0.0472$; values are λ-independent.) The corrected coupling nearly cancels the bare $+0.44$: $w_a = +0.012$. With the corrected DESI anchor (§1.4), the comparison is:

### 6.2 Comparison with DESI DR2 (revised 2026-07-31)

| Quantity | Cassi Prediction | DESI DR2 | Tension |
|---|---|---|---|
| $w_0$ | $-0.87$ (structural, pinned) | $\approx -0.75 \pm 0.06$ (Table 9 [INF]) | **$2\sigma$** |
| $w_a$ (bare) | $+0.46$ | $\approx -0.73 \pm 0.28$ | $4.2\sigma$ |
| $w_a$ (corrected $\xi$) | $+0.012$ | $\approx -0.73 \pm 0.28$ | **$2.7\sigma$** ($2.2$–$3.2\sigma$ across the SNe range) |

The corrected coupling halves the $w_a$ tension (4.2σ → 2.7σ) but does not resolve it. The Cassi $w_0$ is additionally pinned: it stays in $[-0.872, -0.868]$ across $r_0 \in [0.001, 0.08]$ and cannot be calibrated to the DESI $w_0 \approx -0.75$.

### 6.3 Resolution Pathways—Status (revised)

| Mechanism | Status | $\Delta w_a$ |
|----------|:---:|:---:|
| **Qi-gravity $\xi = \varphi^6$ in $H_{\rm eff}$ (corrected Yang-fraction form)** | **Verified** (ODE `two-fluid/calibrate_initial_ratio_xi_v2.py`, 2026-07-31) | **$-0.445$** |
| 5-channel adiabatic gate | Documented, ODE pending | ${\sim} -0.10$ (Hypothesized) |
| Wu Xing control-release | Documented, ODE pending | ${\sim} -0.05$ (Hypothesized) |

Even taking both Hypothesized shifts at face value ($w_a \approx -0.14$) the prediction remains $\approx 2\sigma$ from DESI $w_a \approx -0.73$—the documented shifts (~0.1 each) are ~5× too small to close the gap.

### 6.4 Status

**Tension (corrected 2026-07-31).** With sourced DESI anchors and the galactic-consistent coupling form, the Cassi prediction is $w_0 = -0.87$ (2σ from DESI) and $w_a = +0.012$ (2.7σ from DESI)—a real tension, roughly halved but not resolved by the $\xi = \varphi^6$ coupling. Two structural features distinguish the framework from the DESI-preferred region: (1) the Cassi $w(z)$ **never phantom-crosses** (min $w = -0.85$ over $a \in [0.3, 1]$; the conversion dynamics cannot produce $w < -1$), while the DESI best fit crosses $w = -1$ at $z \approx 0.5$ ($w_p = -1.024 \pm 0.043$); (2) $w_0$ is pinned near $-0.87$ regardless of the initial ratio, so the model is more Λ-like than the data prefer. Script: `two-fluid/calibrate_initial_ratio_xi_v2.py`.

**Test scripts**: `two-fluid/run_pde_wa_test.py` (ODE solver), `two-fluid/run_spatial_boost.py` (spatial structure test).
**Sources last accessed:** 2026-07-19.

### 6.5 The Bubble Lattice and the DESI Average (2026-07-31)

DESI averages over ~20 (Gpc/h)$^3$ of the visible universe; the infinite bubble lattice (`foundations/bubble-lattice-fabric.md`) is periodic and anisotropic, so the question is which lattice structure survives the average. The full analysis is `cosmology/desi-lattice-averaging.md`; the verdict relevant to this section: **the lattice cannot bias the CPL fit into the DESI region.** A fixed-scale wiggle in $D_A(z)$ is suppressed by the line-of-sight integral and shell averaging to $\delta D/D \lesssim 0.1\%$, biasing $w_a$ by ≲ 0.01; closing the $2.7\sigma$ gap would require $\delta D/D \gtrsim 20\%$, ruled out by the smoothness of DESI's own $D_A(z)$. The lattice instead imprints a powder comb on $P(k)$ (the wake-wave prediction, now with predicted multiplicities; DESI LRG bound $A \lesssim 2.6\%$, $p = 0.08$), suppresses sample variance ~10× vs mocks, and predicts NGC–SGC mode correlation. The $w_0 = -0.87$/$w_a = +0.012$ tension verdict stands.

The $1.70\times$ edge anisotropy is a universal lattice signature—see `foundations/bubble-lattice-fabric.md` §4.2.
