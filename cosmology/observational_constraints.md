# Observational Constraints—DESI DR2 Dark Energy & Milky Way Rotation Curve

## Status: Calibrated ($w_0$ coupling form, $\xi$ pin—ledger) / Mapped ($\alpha_{\text{halo}}$ nominal, halo $q$—ledger)—August 2026

## Abstract

This document compares the Cassi framework with DESI DR2 dark-energy constraints and Milky Way rotation-curve measurements. The calibrated two-fluid baseline is $w_0=-0.87$, $w_a=+0.012$ with the Yang-fraction-weighted coupling, a $2\sigma$/$2.7\sigma$ tension with the DESI DR2 anchor ($w_0\approx-0.75$, $w_a\approx-0.73$); it is a calibrated comparison, not a resolved fit (`two-fluid/calibrate_initial_ratio_xi_v2.py`).

The local simultaneous-fit receipt lists a separate conversion→expansion coupling row $(w_0,w_a)=(-0.870,-0.380)$ (`computations/results/hz_full_fit_run.txt`); local synthesis labels this B2. The local realization record describes the corresponding field trial as unstable, with density blow-up without Hubble friction (`foundations/refined-numeric-predictions.md` §2.8; `foundations/spiral-dynamics.md` §1.3), so B2 is a nonviable trial output, not a prediction. A C1 friction closure is a **Hypothesized candidate realization**: the local source record reports $r_*\approx0.9503$ and a conditional pure-$\Lambda$ DESI-window fit $(w_0,w_a)=(-1,0)$, but this repository has no reproducible C1 receipt or local theory-selection proof. The C1 numbers therefore remain conditional on that closure and are not selected or canonical (`foundations/spiral-dynamics.md` §1.3).

DESI measurements and local computational records are cited in place. Error bars are 68% (1σ) confidence unless noted.

---

## 1. Dark Energy Equation of State—DESI Data Release 2

### 1.1 The Calibrated Cassi Baseline

The Cassi $\varphi$-attractor supplies a calibrated dark-energy baseline (see `two-fluid/calibrate_initial_ratio_xi_v2.py` and `foundations/phi_attractor_synthesis.md`):

$$w_0=-0.87,\qquad w_a=+0.012\qquad\text{(calibrated Yang-fraction-weighted baseline).}$$

The ODE uses the gap-derived ratio $r_0=0.0472$ and the Yang-fraction-weighted Qi coupling. These values are calibration outputs, not an independently predicted pair (`two-fluid/calibrate_initial_ratio_xi_v2.py`).

### 1.2 DESI DR2 Primary Paper

**Source:** DESI Collaboration, 2025. "DESI DR2 Results II: Measurements of Baryon Acoustic Oscillations and Cosmological Constraints." arXiv:2503.14738.

| Result | Value | Reference |
|---|---|---|
| $\Lambda$CDM rejection (DESI BAO + CMB) | **3.1σ** preference for dynamical DE | Abstract |
| $\Lambda$CDM rejection (DESI + CMB + SNe) | **2.8–4.2σ** depending on SNe sample | Abstract |
| Best-fit quadrant | $w_0 > -1$, $w_a < 0$ (quintom B) | §V, Fig. 13 |
| Neutrino mass upper limit ($\Lambda$CDM) | $\sum m_\nu < 0.064$ eV (95% CL) | Abstract |
| Neutrino mass upper limit ($w_0 w_a$) | $\sum m_\nu < 0.16$ eV (95% CL) | Abstract |

DESI DR2 mapped 13.1 million galaxies and 1.6 million quasars; the $4.2\sigma$ deviation from $\Lambda$CDM corresponds to about one chance in 30,000 if dark energy were constant (DESI DR2).

From the DESI DR2 + CMB + SNe combined analysis, the best-fit $(w_0,w_a)$ lies in the quadrant $w_0>-1$, $w_a<0$. Cassi shares the $w_0>-1$ side at the calibrated baseline, while its $w_a=+0.012$ has the opposite sign to the DESI preference. The local receipt for the separate coupling row is $(w_0,w_a)=(-0.870,-0.380)$ (`computations/results/hz_full_fit_run.txt`), and local synthesis calls this B2 (`foundations/refined-numeric-predictions.md` §2.8). The field-level source record marks that trial nonviable because the density blows up without Hubble friction (`foundations/spiral-dynamics.md` §1.3); B2 is not the theory's prediction. The C1 friction closure is a Hypothesized candidate realization whose reported $r_*$ and pure-$\Lambda$ fit are conditional on that closure, with no local receipt or selection proof to make it canonical (`foundations/spiral-dynamics.md` §1.3). The CPL parametrization used throughout is $w(a)=w_0+w_a(1-a)$.

### 1.3 Independent Analysis Paper

**Source:** Gu, G., Wang, X., Wang, Y. et al., 2025. "Dynamical dark energy in light of the DESI DR2 baryonic acoustic oscillations measurements." Nature Astronomy 9, 1879–1889. doi:10.1038/s41550-025-02669-6.

| Dataset | SNR of $w \neq -1$ | $\Lambda$CDM significance |
|---|---|---|
| DESI DR2 BAO only | 2.6σ | ~1.5σ |
| DESI DR2 + Pantheon+ | 3.7σ | >2σ |
| DESI DR2 + Union3 | 4.3σ | >2σ |
| DESI DR2 + DESY5 | 4.5σ | >2σ |

From the non-parametric Bayesian reconstruction of $w(z)$ with a Horndeski-motivated correlation prior. Consistent with the companion DESI DR2 paper—same conclusion of quintom B ($w_0>-1$, $w_a<0$).

### 1.4 Composite Constraints from Project

The constraints used here are the published DESI DR2 values below; the two-fluid solver's own constants (e.g. `TARGET_W0` in `two-fluid/calibrate_initial_ratio.py`) are internal calibration targets, not measurements, and play no role in the comparison.

Verified anchors from the DESI DR2 papers (arXiv:2503.14738; astrobites 2025-10-06):
- BAO+CMB prefers $w_0>-1$, $w_a<0$ at **3.1σ**; with SNe compilations the preference is 2.8–4.2σ.
- Pivot values from the paper: $w_p=-1.024\pm0.043$ and $-0.954\pm0.024$.
- Widely reported Table 9 values [INFERENCE, per-table note]: $w_0\approx-0.72\pm0.09$, $w_a\approx-0.73\pm0.28$ (BAO+CMB+Pantheon+); $w_a$ spans ≈−0.6 to −1.1 across SNe compilations.

### 1.5 Comparison with Cassi

| Quantity | DESI DR2 Measurement | Cassi status | Deviation |
|---|---|---|---|
| $w_0$ | $\approx-0.75\pm0.06$ (Table 9 [INFERENCE]) | $-0.87$ calibrated baseline (`two-fluid/calibrate_initial_ratio_xi_v2.py`); $-0.870$ in the local coupling receipt (B2 trial; `computations/results/hz_full_fit_run.txt`); $-1.000$ only as the conditional C1 candidate realization (`foundations/spiral-dynamics.md` §1.3) | $2\sigma$ baseline; conditional C1 value is $4.17\sigma$ |
| $w_a$ | $\approx-0.73\pm0.28$ (Table 9 [INFERENCE]) | $+0.012$ calibrated baseline (`two-fluid/calibrate_initial_ratio_xi_v2.py`); $\approx-0.38$ in the nonviable B2 trial (`computations/results/hz_full_fit_run.txt`); $(w_0,w_a)=(-1,0)$ only as the conditional C1 candidate realization (`foundations/spiral-dynamics.md` §1.3) | $2.7\sigma$ baseline; $1.25\sigma$ B2 trial; $2.61\sigma$ conditional C1 value |

The calibrated structural values are supported by `two-fluid/calibrate_initial_ratio_xi_v2.py` and sit $2\sigma$/$2.7\sigma$ from the DESI anchors. The local receipt's coupling row is a B2 trial output, not a prediction, because the local realization record marks the field dynamics nonviable (`computations/results/hz_full_fit_run.txt`; `foundations/spiral-dynamics.md` §1.3). The local source record reports the C1 friction closure's pure-$\Lambda$ window only conditionally; the repository has no runnable receipt or theory-selection proof for that closure, so the conditional value is not substituted for the calibrated baseline.

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

The measured total circular velocity together with the baryonic model estimate
gives the model-derived comparison ratio

$$
\frac{v_c(30\text{ kpc})}{v_{\text{N, bary}}(30\text{ kpc})}
\approx \frac{190 \pm 20}{70 \pm 15}
\approx 2.7 \pm 0.65,
$$

where $\pm0.65$ is the propagated uncertainty from the independent velocity
inputs; uncertainty in the baryonic baseline model is additional. This ratio
is a comparison input, not a direct observed boost.

### 2.5 Summary Table

| Quantity | Value | Uncertainty (1σ) | Source |
|---|---|---|---|
| $v_c(R_\odot)$ | $229.0$ km/s | $\pm 0.2$ stat, $\pm \sim 5\%$ sys | Eilers 2019 |
| $dv_c/dR$ (5–25 kpc) | $-1.7$ km/s/kpc | $\pm 0.1$ | Eilers 2019 |
| $v_c(25\text{ kpc})$ | $\sim 200$ km/s | $\sim \pm 15$ km/s | Eilers 2019 |
| $v_c(30\text{ kpc})$ | $\sim 190$ km/s | $\sim \pm 20$ km/s | Zhou+ 2023 |
| $v_{\text{N,bary}}(30\text{ kpc})$ | $\sim 70$ km/s | $\sim \pm 15$ km/s | MW baryon models |
| Model-derived velocity ratio | $\mathbf{\sim 2.7}$ | $\sim \pm 0.65$ propagated from the two velocity inputs, plus baryonic-baseline uncertainty | $v_c/v_{\text{N,bary}}$ comparison |

### 2.6 Conditional Attractive-Branch Rotation-Curve Comparison

The canonical field-level force record writes $\mathbf{F}=\Pi\nabla\Phi$; it describes positive $\Pi$ as a Yang/outward mapping (`cassi-physics.md` §12). The point-particle $-\nabla\Phi$ convention is documented separately, but using that sign as the physical Milky Way halo law requires a **Hypothesized attractive sign extension**. The comparison below assumes that branch; it is not a canonical force-law prediction.

Under the assumed attractive branch, the Qi-enhanced two-body expression is:

$$\mathbf{F}_{ij}=-G\,\alpha_{\Pi,i}\left(1+(\varphi^{6}-1)q_i\right)M_iM_j\frac{\mathbf{r}_{ij}}{|\mathbf{r}_{ij}|^3},\qquad \alpha_{\Pi,i}:=\frac{\Pi_i}{M_i},\qquad \xi=\varphi^6.$$

Here $\alpha_{\Pi,i}$ is the signed Yang-imbalance of body $i$. The illustrative
halo comparison makes an additional branch-specific constitutive substitution
$\alpha_{\Pi}\mapsto\alpha_{\text{halo}}:=M_Y/M=r/(1+r)$ and uses a mapped
local/halo-averaged $q_{\text{halo}}$, with $\xi=\varphi^6\approx17.944$:

$$\frac{v_C}{v_B}=\sqrt{\alpha_{\text{halo}}\left(1+(\varphi^{6}-1)q_{\text{halo}}\right)}.$$

For the assumed Milky Way halo component fraction $\alpha_{\text{halo}}\approx0.7$
and mapped local/halo-averaged $q_{\text{halo}}\approx0.7$:

$$\left.\frac{v_C}{v_B}\right|_{\text{conditional attractive branch}}\approx\sqrt{0.7\left(1+16.944\times0.7\right)}=\sqrt{9.00}\approx\mathbf{3.0}.$$

The halo-regime Yang component fraction is distinct from the equilibrium imbalance $\alpha_0=\varphi^{-3}$. An independent Path 8 fit in `foundations/phi_attractor_synthesis.md` reports $2.89\times$ at 30 kpc under the $\xi=\varphi^6$ script coupling; both values inherit the assumed attractive branch and remain Hypothesized.

Conditional branch output: $v_{\text{Cassi}}(30\text{ kpc})\approx3.0\times70\approx210$ km/s. The observed value is $v_c(30\text{ kpc})\approx190\pm20$ km/s (Zhou+ 2023).

**Conditional velocity comparison:** the assumed attractive branch gives $210$ km/s versus the measured $190\pm20$ km/s at 30 kpc (Zhou+ 2023), about $1.0\sigma$. Separately, the dimensionless branch ratio $2.8$–$3.0$ is compared with the model-derived central ratio $\sim2.7$ and its $\sim0.65$ propagated uncertainty, with additional baryonic-baseline uncertainty. The ratio comparison is not the km/s velocity comparison; neither validates the attractive sign extension or promotes it to a canonical Cassi force law.

---

## 3. Key Takeaways

The cosmology hierarchy is fixed throughout this document: the calibrated baseline is the comparison state; B2 is an unstable, nonviable coupling trial; and C1 is a Hypothesized candidate realization whose numerical fit is conditional on assuming that closure.

| Observable | Cassi status | Evidence / comparison | Decision |
|---|---|---|---|
| $w_0,w_a$ | Calibrated baseline $(-0.87,+0.012)$ (`two-fluid/calibrate_initial_ratio_xi_v2.py`); B2 trial $(-0.870,-0.380)$ (`computations/results/hz_full_fit_run.txt`); C1 candidate closure $(-1,0)$ conditional (`foundations/spiral-dynamics.md` §1.3) | Baseline is $2\sigma$/$2.7\sigma$ from DESI; B2 density blows up without friction; C1 fit is conditional | Baseline tension; B2 rejected as unstable/nonviable; C1 not selected |
| $\Omega_m/H_0$ compatibility | CMB-inferred $H_0\approx65.8$ km/s/Mpc in the ODE pipeline (`two-fluid/run_hubble_pipeline.py`; `computations/results/hubble_pipeline_run.txt`) | Full simultaneous fit under calibrated $w(a)$ has $\chi^2\approx25.1$, equal to $\Lambda$CDM (`computations/results/hz_full_fit_run.txt`); no resolution | Tension remains |
| $v_c(30\text{ kpc})$ vs baryons | Conditional attractive branch $v_C/v_B=2.8$–$3.0$ (`cassi-physics.md` §12; `foundations/phi_attractor_synthesis.md`) | The conditional ratio range is compared with the model-derived central ratio $\sim2.7\pm0.65$ from $190\pm20$ and $70\pm15$ km/s, with additional baryonic-baseline uncertainty; this ratio check is separate from the $210$ versus $190\pm20$ km/s velocity comparison in §2.6, and the sign extension remains Hypothesized | Conditional numerical consistency; no canonical force-law claim |

Local source paths are listed in the comparison cells and in the References section.

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
| Axis-dipole angular separation | 12.22° (measured); **12.40° = 2π/φ⁷ (optional Hypothesized geometric closure, 13 seeds; 1.5% match)** | Measured from direction vectors; the physical closure is an optional geometric construction, not a canonical density-phase or PDE-derived output; magnitude formula from `foundations/wake-geometry.md` §3b |
| Axis-Virgo separation | 17° | This work |
| Axis-cold spot separation | 124° | This work |

The axis is NOT aligned with the CMB cold spot or the Eridanus supervoid, ruling out a simple local-void explanation. The 5.4σ joint significance across multiple large-angle anomalies (Jones+ 2023) is an a-posteriori statistic—the alignment was discovered in the data, so a look-elsewhere correction across multipoles applies—but the anomaly remains persistent.

### 4.2 Cassi Mechanism (Hypothesized): Bubble-Boundary Triaxial Axis

**Tier: magnitude 12.40° = 2π/φ⁷ (exact arithmetic; physical closure optional Hypothesized geometric construction, Mapped if selected/fitted under existing provenance) / measured 12.22° (Calibrated; 1.5% match) / axis direction Calibrated (from data) / boundary mechanism Hypothesized.** The measured 12.22° dipole↔quadrupole separation is computed from the measured multipole direction vectors—the CMB dipole at $(l,b) \approx (264\degree, +48\degree)$ and the quadrupole-octopole axis at $(l,b) = (260\degree, +60\degree)$—so its *direction* is calibrated from the data, not predicted (`two-fluid/run_cmb_lowl_pipeline.py`); its *magnitude* is compared with an optional geometric construction: the golden-angle closure residual of the bubble's pole spiral, $2\pi/\varphi^7 = 12.399°$ (`foundations/wake-geometry.md` §3b; `computations/cmb_axis_closure_check.py`), matching the measured 12.22° at 1.5% (claim 2). The framework's candidate mechanism is the triaxial bubble geometry at cascade step 285 (registry C10; `foundations/refined-numeric-predictions.md` §2.3; `foundations/dimensionful-cascade.md` §8.3): adjacent bubbles at identical $w = 5$—all bubbles share the derived Wu Xing number, with no spatial $w$ variation—sit at $\varphi$-spaced chord-lattice intervals, and their shared boundary normal defines a preferred direction at $\ell < 5$. This mechanism is **Hypothesized**: its boundary orientation is chosen to match the measured axis, so it currently explains the direction post-hoc rather than predicting it. The measured separation is itself degenerate with the solar-system frame—the axis lies in the ecliptic plane ($+0.8°$) and the dipole $11.4°$ out of it, so 12.22° is almost entirely the dipole's ecliptic latitude (direction-selector audit: `computations/cmb_axis_direction_selector_check.py`).

The mechanism's claims:

1. **Preferred axis** at the largest angular scales ($\ell < 5$), fading at $\ell > 5$
2. **Dipole↔quadrupole separation: 12.22° measured, magnitude 12.40° = 2π/φ⁷ from the optional golden-angle closure**: the angular separation between the CMB dipole (Yang axis) and the quadrupole-octopole axis (boundary normal) is computed from the measured vectors (direction Calibrated); its magnitude matches the optional Hypothesized geometric closure—the five-arm pole spiral of the Cassi bubble (rung 285, `foundations/bubble-lattice-fabric.md` §4.4) closes after 13 seeds of the golden angle $2\pi/\varphi^2 = 137.5°$ to within exactly $2\pi/\varphi^7 = 12.399°$ (`foundations/wake-geometry.md` §3b; identity $13/\varphi^2 = 5 - 1/\varphi^7$, exact—13 seeds return to 5 full turns minus exactly $2\pi/\varphi^7$). This arithmetic closure is independent of the CMB data; selecting it as the physical angle is an optional Hypothesized geometric construction, Mapped if selected or fitted under existing provenance, and separate from the canonical density-plane angle and PDE dynamics. The measured 12.22° sits 1.5% from it.
3. **E-mode polarization alignment**: the CMB E-mode quadrupole/octopole MUST show the same axis if the anomaly is primordial (testable by Simons Observatory and LiteBIRD)
4. **Bulk flows** along the preferred axis ($\sim 500$–$2000$ km/s at Gpc scales)

**Status: physical closure optional Hypothesized geometric construction (12.40° = 2π/φ⁷; Mapped if selected/fitted under existing provenance), direction calibrated, mechanism unconfirmed.** The arithmetic identity $12.40° = 2\pi/\varphi^7$ is pre-existing and the measured 12.22° remains a 1.5% comparison; treating that identity as the physical pole-spiral angle is an optional geometric construction, separate from the canonical density-plane angle and PDE dynamics. The 5.4σ is the data's a-posteriori significance: the alignment was discovered in the data (WMAP; Land & Magueijo 2005), so a look-elsewhere correction across multipoles applies to the claimed significance. The bubble-boundary mechanism is a candidate whose boundary normal is still fitted to the measured axis—the *direction* is not yet a prediction, and the projection of the pole-spiral closure residual onto the dipole↔quadrupole separation is not derived. The direction-selector audit (2026-08-11, `computations/cmb_axis_direction_selector_check.py`) finds **no two-fluid/bubble-lattice orientation that selects the axis**: the PDE is rotation-invariant, so the absolute orientation of the Frenet-Serret axes (Yang/Yin/string) is set by the primordial string's initial orientation (a calibration, not a derivation); the Milky Way's offset from the bubble centre—which would set the nearest-boundary direction—is likewise a calibration input; and the closure residual $2\pi/\varphi^7$ is an azimuthal angle in the pole-spiral plane whose sky projection is not derived. The same audit quantifies a competing selector the framework does not engage: the measured 12.22° is **degenerate with the ecliptic frame**—the quadrupole-octopole axis sits in the ecliptic plane (ecliptic latitude $+0.8°$), the dipole $11.4°$ out of it, and the 12.22° separation decomposes into an out-of-plane (ecliptic-latitude) component of 12.22° versus an in-plane component of only 0.87°. The axis-of-evil's ecliptic placement is the documented large-angle anomaly (Schwarz+ 2004; Land & Magueijo 2005); if it is a solar-system/foreground selection, the 12.22° target itself is foreground-entangled and the 12.40° closure matches a frame artifact. Elevation therefore requires both (i) an a priori derivation of the boundary normal from the cascade—the condensation field's orientation at rung 285 (the bubble normal direction relative to the galaxy/CMB frame), computed without taking the measured axis as input—and (ii) exclusion of the ecliptic/foreground selection; the E-mode polarization test (Simons Observatory, LiteBIRD) is falsifiable and independent of the orientation question.

---

## 5. Cross-Domain Status

The DESI hierarchy stated in §3 is unchanged: calibrated baseline; unstable, nonviable B2 coupling trial; C1 friction closure as a conditional Hypothesized candidate realization, not a selected realization. This table records the other observables without repeating the cosmology summary.

| Observable | Current status | Open decision | Local source |
|---|---|---|---|
| $\Omega_m/H_0$ compatibility | Pipeline CMB-inferred $H_0\approx65.8$ km/s/Mpc; the calibrated full $H(z)$ fit has $\chi^2\approx25.1$, equal to $\Lambda$CDM | The early-time ODE extrapolation is outside its calibrated range; no Hubble-tension resolution is established | `two-fluid/run_hubble_pipeline.py`; `computations/results/hubble_pipeline_run.txt`; `computations/hz_full_fit.py`; `computations/results/hz_full_fit_run.txt` |
| $v_c(30\text{ kpc})$ vs baryons | Conditional attractive branch $v_C/v_B=2.8$–$3.0$, compared with the model-derived central ratio $\sim2.7\pm0.65$ from $190\pm20$ and $70\pm15$ km/s | The ratio comparison is separate from the §2.6 $210$ versus $190\pm20$ km/s velocity check; the attractive sign extension and halo mapping remain Hypothesized | `cassi-physics.md` §12; `foundations/phi_attractor_synthesis.md` |
| CMB axis of evil | 12.22° measured dipole↔quadrupole separation; 12.40° geometric identity is an optional Hypothesized construction; axis direction is Calibrated from data | Boundary-to-axis mechanism and closure-to-axis projection remain unconfirmed | `two-fluid/run_cmb_lowl_pipeline.py`; `foundations/wake-geometry.md` §3b |

---

## 6. The $w_a$ Tension: Calibrated Baseline vs DESI DR2

### 6.1 The Calibrated Baseline and the Coupling

The local two-fluid solver reports $w_a=+0.457$ for the bare conversion row ($H_{\text{bare}}$ only). The comparison anchor is the widely reported DESI Table 9 value $w_a\approx-0.73\pm0.28$ [INFERENCE]. The pure-Yang coupling form $\sqrt{1+(\varphi^{6}-1)q}$ does not use the galactic-sector convention, where the boost applies to the Yang component only; the Yang-fraction-weighted form is the calibrated comparison (`two-fluid/calibrate_initial_ratio_xi_v2.py`).

The local solver checks report:

1. **$\lambda$ independence:** the fitted $w_a$ is unchanged across $\lambda\in[0.01,0.05]$.
2. **Qi-gate $\alpha$ independence:** the fitted $w_a$ is unchanged across $\alpha\in[0.01,5.0]$.
3. **Spatial-boost null:** $B=1.003$ at $N=32$; spatial structure does not enhance conversion.
4. **Late-time structural decay:** the structural Hubble mode vanishes as $r\to\varphi$.

These checks are the outputs of `two-fluid/run_pde_wa_test.py` and `two-fluid/run_spatial_boost.py`; they do not select an additional conversion→expansion closure.

**Yang-fraction-weighted coupling.** The rotation-curve coupling boosts the Yang component only,

$$v^2=\frac{G[M_{\rm bar}+(1+(\varphi^{6}-1)q)M_Y]}{r},$$

so the homogeneous analogue weights by the attractor Yang fraction $\alpha_w=r/(1+r)=\varphi^{-1}\approx0.618$:

$$H_{\rm eff}^2=H_{\rm bare}^2\left[1+(\varphi^{6}-1)q\,\alpha_w\right].$$

Under this form (`two-fluid/calibrate_initial_ratio_xi_v2.py`):

| Mode | $w_0$ | $w_a$ |
|---|---|---|
| Bare conversion | $-0.856$ | $+0.457$ |
| Pure-Yang form $\sqrt{1+(\varphi^{6}-1)q}$ | $-0.862$ | $+0.068$ |
| **Yang-fraction-weighted baseline** | **$-0.872$** | **$+0.012$** |

The gap-derived structural ratio is $r_0=\varphi^{-5}/(2-\varphi^{-5})=0.0472$; the local solver reports these rows as $\lambda$ independent. The $(\varphi^6-1)$ coefficient re-run remains flagged as pending in the source script. The calibrated Yang-fraction-weighted row, not the bare row, is the baseline used for the DESI comparison.

### 6.2 Comparison with DESI DR2

| Cassi state | $(w_0,w_a)$ | DESI comparison | Classification |
|---|---|---|---|
| Calibrated Yang-fraction-weighted baseline | $(-0.87,+0.012)$ | $2\sigma$ in $w_0$; $2.7\sigma$ in $w_a$ ($2.2$–$3.2\sigma$ across the SNe range) | Calibrated baseline; tension remains |
| B2 conversion→expansion coupling trial | $(-0.870,-0.380)$ in the local simultaneous-fit receipt | $1.25\sigma$ in $w_a$ | Unstable, nonviable trial; density blow-up without friction; not a prediction |
| C1 friction closure | $(-1,0)$ in the local source record | $4.17\sigma$ in $w_0$; $2.61\sigma$ in $w_a$ | Hypothesized candidate realization; numerical fit conditional on the assumed closure |

The local receipt reports the B2 row at $w_a=-0.380$ (`computations/results/hz_full_fit_run.txt`); local synthesis reports a corresponding shift $\Delta w_a=-0.393$ with route range $[-0.61,-0.38]$ (`foundations/refined-numeric-predictions.md` §2.8). The field-level source record marks B2 nonviable because its density blows up without Hubble friction (`foundations/spiral-dynamics.md` §1.3). The C1 row is an exact output of the assumed friction closure in that source record, not evidence that the framework physically selects the closure. No local C1 receipt or theory-selection proof is present.

### 6.3 Resolution Pathways—Status

| Mechanism | Status | Reported $w_a$ effect |
|---|---|---|
| **Qi-gravity $\xi=\varphi^6$ in $H_{\rm eff}$ (Yang-fraction-weighted form)** | **Calibrated solver output** (`two-fluid/calibrate_initial_ratio_xi_v2.py`) | **$\Delta w_a=-0.445$** relative to the bare row |
| **Conversion→expansion candidate extension** ($V_{\text{new}}=\lambda\tilde h+\lambda\varphi^{-2}/d$) | **Hypothesized candidate extension**; B2 is a nonviable trial; C1 is an assumed closure with a conditional solution and no theory-selection proof | B2: $-0.380$ in the receipt and $-0.393$ in local synthesis; C1: conditional pure-$\Lambda$ window $(w_0,w_a)=(-1,0)$ |
| 5-channel adiabatic gate | Hypothesized; ODE pending | ${\sim}-0.10$ |
| Wu Xing control-release | Hypothesized; ODE pending | ${\sim}-0.05$ |

The B2 arithmetic is $w_a'=+0.012-0.393\approx-0.38$, but it is a trial output and not the theory's prediction because the local source record marks the realization nonviable. The C1 values $r_*\approx0.9503$ and $(w_0,w_a)=(-1,0)$ are outputs conditional on assuming the friction closure; they are not a physical selection of that closure.

### 6.4 Status

**Tension (calibrated baseline) / unstable, nonviable B2 trial / Hypothesized C1 candidate realization.** With the sourced DESI anchors and the galactic-consistent coupling form, the calibrated baseline is $w_0=-0.87$ and $w_a=+0.012$, at $2\sigma$ and $2.7\sigma$ from DESI. The $\xi=\varphi^6$ coupling reduces the $w_a$ tension relative to the bare row but does not resolve the DESI comparison. The B2 coupling row is recorded in a local simultaneous-fit receipt and fails the local field-level viability criterion. The C1 friction result is conditional on an assumed closure; no local receipt or theory-selection proof promotes it to a selected or canonical realization.

**Test scripts:** `two-fluid/run_pde_wa_test.py` (ODE solver), `two-fluid/run_spatial_boost.py` (spatial-structure check), `two-fluid/run_hubble_pipeline.py` (ODE-to-$H(z)$ pipeline), and `computations/hz_full_fit.py` (simultaneous fit).

### 6.5 The Bubble Lattice and the DESI Average

DESI averages over about 20 (Gpc/h)$^3$ of the visible universe. The infinite bubble lattice (`foundations/bubble-lattice-fabric.md`) is periodic and anisotropic; the relevant averaging result is that **under the declared averaging model, the lattice does not bias the calibrated CPL fit into the DESI region** (`cosmology/desi-lattice-averaging.md` §2, §5). A fixed-scale wiggle in $D_A(z)$ is suppressed by the line-of-sight integral and shell averaging to $\delta D/D\lesssim0.1\%$, biasing $w_a$ by $\lesssim0.01$. The conditional C1 window is not a baseline gap and is not selected by this averaging result.

The boundary comparison remains conditional: the directional proxy is $R(\theta)=\frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta}{\theta}}$, equal to $1.7072\times$ only at the selected $\theta_{\mathrm{cond}}=0.45$ and variable with $\theta$. No $C=0.45$ edge survives the fixed-step PDE endpoint, and the cosmological boundary receipt is null; any void-edge test requires an independently identified boundary and is not observational support, a universal or zero-parameter claim, or a canonical/PDE output.

## References

- `two-fluid/calibrate_initial_ratio_xi_v2.py`—calibrated Yang-fraction-weighted baseline and solver rows.
- `cassi-physics.md` §12—canonical field-level force sign and conditional attractive mapping.
- `two-fluid/run_pde_wa_test.py`—ODE coupling comparison checks.
- `two-fluid/run_spatial_boost.py`—spatial-boost check.
- `two-fluid/run_hubble_pipeline.py`—ODE-to-$H(z)$ pipeline; `computations/results/hubble_pipeline_run.txt`—pipeline receipt.
- `computations/hz_full_fit.py` and `computations/results/hz_full_fit_run.txt`—reproducible simultaneous-fit receipt, including the B2 trial row.
- `foundations/spiral-dynamics.md` §1.3—conversion→expansion source record and conditional C1 closure.
- `foundations/refined-numeric-predictions.md` §2.8—local synthesis of the B2 trial and conditional C1 result.
- `cosmology/desi-lattice-averaging.md` §2, §5—lattice averaging result.
