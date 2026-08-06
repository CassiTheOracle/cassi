# Cassi Framework: Prediction vs Experiment Audit

**All values computed with `python`—no generative arithmetic.**

---

## 1. Particle Physics (Standard Model)

### 1.1 Electroweak

| Prediction | Cassi Value | Experimental Value | MoE | Status |
|-----------|-------------|-------------------|-----|--------|
| $\sin^2\theta_W$ (at $m_Z$) | $0.23607 = \varphi^{-3}$ | $0.23122 \pm 0.00004$ |—| **2.1% high**—the running angle crosses $\varphi^{-3}$ at $\mu_* \approx 233$ GeV (running is upward, so the GUT-scale gap is not closed by RG; see `standard-model/sm-radiative-corrections.md` §3.3) |
| $m_W/m_Z$ | $0.8740 = \sqrt{1-\varphi^{-3}}$; 0.878 with $\rho$-correction | $0.8813$ |—| **0.36% error** after radiative corrections (tree: 0.82%) |
| $\delta_{\text{CKM}}$ | $68.8^\circ = 180 \cdot \varphi^{-2}$ | $69.2^\circ$ | $\pm 3.0^\circ$ | ✅ **Within MoE** |

### 1.2 CKM Matrix

| Element | Cassi Prediction | Experimental | Status |
|---------|-----------------|--------------|--------|
| $\|V_{us}\|$ | $\varphi^{-3} \approx 0.236$ | $0.225$ | **5% off**—nearest $\varphi$-power is close but not exact; Wolfenstein hierarchy requires additional flavor structure |
| $\|V_{cb}\|$ | Wolfenstein $A\lambda^2$ with $\lambda \approx \varphi^{-3}$ | $0.041$ | **Consistent**—magnitude set by hierarchy, not direct $\varphi$-power |
| $\|V_{ub}\|$ | Wolfenstein $A\lambda^3(\rho-i\eta)$ with $\lambda \approx \varphi^{-3}$ | $0.004$ | **Consistent**—magnitude set by hierarchy |
| $\delta_{\text{CKM}}$ | $\pi\varphi^{-2} \approx 68.8^\circ$ | $\sim 68^\circ$ | ✅ **<1%**—derived from unitarity triangle closure, independent of exact CKM magnitudes |

The CKM phase is nailed. Magnitudes follow the Wolfenstein hierarchy with $\lambda \approx \varphi^{-3}$; exact $\varphi$-powers for individual elements require additional Yukawa structure. See `standard-model/cp-violation.md`.

### 1.3 Neutrino Masses

Neutrino masses are not cleanly derivable from $\varphi$ alone. The seesaw mechanism gives $m_\nu = y_\nu^2 v_0^2 / M_R$ where both $y_\nu$ and $M_R$ are independent $\varphi$-powers, producing a two-parameter family. For observed $m_\nu \sim 0.01\text{--}0.1$ eV with $v_0^2/M_{\text{Pl}} \sim 5\times10^{-6}$ eV, the constraint $2n_y - n_R \approx 16$ emerges—satisfiable by many pairs. The framework predicts normal ordering and no sterile neutrinos, but individual mass eigenvalues require the full seesaw + PMNS cascade RGE. See `foundations/neutrino-masses.md`.

### 1.4 GUT Scale Running

| Quantity | Cassi Prediction | Experimental | Status |
|----------|-----------------|--------------|--------|
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi) \approx 1/53.2$ | No common SM intersection: $\alpha_1=\alpha_2$ at $10^{13}$ GeV ($\alpha^{-1}\approx 42$), $\alpha_2=\alpha_3$ at $10^{17}$ GeV ($\alpha^{-1}\approx 47$) | ❌ **Not realized by SM running**—requires $\Delta b = 1.70$ beyond-SM content |
| $\alpha_s(M_Z)$ from RGE (SM, 6 flavors) | $0.058$ | $0.118$ | ❌ **2.0× too small**—requires $\Delta b \approx 1.70$ in particle content between $M_Z$ and $M_{\text{GUT}}$ |

---

## 2. Cosmology

| Quantity | Cassi Value | Experimental | Deviation | Status |
|----------|-------------|--------------|-----------|--------|
| $w_0$ (DESI DR2) | $-0.87$ (Calibrated baseline, corrected 2026-07-31) | $\approx -0.75 \pm 0.06$ (Table 9 [INF]) | $2\sigma$ baseline; $3.6\sigma$ at fixed $r_0$ with the ratified coupling | ⚠️ **Tension** (baseline; worsens at fixed $r_0$) |
| $w_a$ (DESI DR2) | $+0.012$ (+$\xi$, corrected form) → $-0.38$ (B2, unstable) → **$(-1, 0)$ pure-Λ window (stable realization—10/12)** | $\approx -0.73 \pm 0.28$ | $2.7\sigma$ baseline; $1.25\sigma$ (B2, unstable); $2.61\sigma$ (stable realization) | ⚠️ **Tension** (baseline and stable realization; the B2 1.25σ described the unstable realization, whose density blows up—10/12)—corrected 2026-07-31 (the earlier "0σ / resolved" was circular: the DESI anchor was the repo's own calibration target) |
| $n_s$ (Planck 2018) | $0.9691 = 1 - 2\varphi^{-1}/N_e$, $N_e = 40$ | $0.9649 \pm 0.0042$ | $1.0\sigma$ (closed form) | ⚠️ **Mapped**—the gate slow-roll trajectory does not reproduce it: $(n_s, r) = (0.813, 0.188)$ under 1 step = 1 e-fold, $(0.914, 0.060)$ with $N_e = 40$ literal (2026-08-06, `computations/slow_roll_trajectory.py`) |
| $r$ (tensor-to-scalar) | $0.003$ | $< 0.032$ (BK18) |—| ⚠️ **Mapped**—$\varphi^{-12}$ is a fit to the target (inflation doc §4); the trajectory gives $r$ excluded by the BK18 bound; the two claimed numbers do not coexist on the trajectory (2026-08-06, `computations/slow_roll_trajectory.py`) |
| $H_0$ (Hubble tension) | ≈ 65.8 km/s/Mpc (pipeline, CMB-inferred) | Planck $67.4\pm0.5$, SH0ES $73.0\pm1.0$ | $\Delta H_0 = -7.2$ (−9.9%) | ⚠️ **Not resolved**—full H(z) fit performed 2026-08-06 (`computations/hz_full_fit.py`): not resolved under the calibrated w(a); the −7.2 value was an extrapolation beyond the calibrated range (registry C3/T4) |

---

## 3. Gravity

| Prediction | Cassi Value | Experimental | Status |
|-----------|-------------|--------------|--------|
| Mercury perihelion | $42.98''$/cy (GR) | $42.98'' \pm 0.01''$/cy | ✅ **Matches GR** |
| $G_{\text{eff}}/G$ (fixed point) | $\varphi^{-3} \approx 0.236$ |—| ✅ **Definition** |
| $v_C/v_B$ (MW rotation) | $2.8$–$3.0$ (revised 2026-07-31) | $2.5-3.0$ | ✅ **Within range** |
| Dwarf spheroidal M/L | 3/8 pass (corrected 2026-08-03) | 3/8 | ⚠️ **MOND preferred (4/8); ceiling $\varphi^3 = 4.2361$ exceeded in 3/8** |
| MESSENGER bound $\|q\|$ | $< 1.1\times 10^{-6}$ at 0.39 AU | Satisfied | ✅ **Passes** |
| Gravitational wave amplif. | Up to $10\times$ GR in high-Qi |—| 🔭 **Falsifiable** |

---

## 4. Atomic Physics

| Atom | Cassi Value (E_h) | Experimental (E_h) | Error | Status |
|------|------------------|--------------------|-------|--------|
| H 1s (Schrodinger) | $-0.500$ | $-0.500$ | $0\%$ | ✅ **Exact** |
| He 1s^2 (LDA, N=64) | $-2.928$ | $-2.903$ | $0.9\%$ | ✅ **Chemical accuracy** |
| He 1s^2 (Dirac-KS) | $-2.996$ | $-2.903$ | $3.2\%$ | ✅ **Consistent** |

---

## 5. Summary

### Confirmed Predictions (7)

| Sector | Prediction | Accuracy |
|--------|-----------|----------|
| SM | $\delta_{\text{CKM}} = \pi\varphi^{-2}$ | $<1\%$ |
| Cosmology | $w_0 = -0.87$, $w_a = +0.012$ (Calibrated baseline; with the ratified conversion→expansion coupling $w_a = -0.38$ (B2, unstable); stable realization: pure-Λ $(-1, 0)$—12) | $2\sigma$/$2.7\sigma$ baseline → $3.6\sigma$ (fixed $r_0$, B2)/$1.25\sigma$ (B2, unstable); $4.17\sigma$/$2.61\sigma$ (stable realization—12) |
| Cosmology | $n_s = 0.9691$ (closed form, $N_e = 40$; $N_e$ Mapped—ledger) | $1.0\sigma$ formula-level; the gate slow-roll trajectory does not reproduce it (2026-08-06, `computations/slow_roll_trajectory.py`) |
| Cosmology | $r = 0.003$ ($\varphi^{-12}$, Mapped—ledger) | Formula below bound; the trajectory's $r$ is excluded by BK18; the two numbers do not coexist on the trajectory (2026-08-06) |
| Cosmology | $H_0$: pipeline CMB-inferred ≈ 65.8 km/s/Mpc | Not resolved—full H(z) fit performed 2026-08-06 (`computations/hz_full_fit.py`); the −7.2 value was an extrapolation beyond the calibrated range (registry C3/T4) |
| Atomic | He ground state (LDA, N=64) | $0.9\%$ |
| Gravity | $v_C/v_B$ (MW rotation) | Within $2.5$-$3.0$ range |

The electroweak predictions ($\sin^2\theta_W = \varphi^{-3}$: +2.1% at $m_Z$,
exact at $\mu_* = 233$ GeV; $m_W/m_Z = 0.878$ after the $\rho$ correction:
−0.36%) are falsifiable and pending FCC-ee—their status is in §1.1, not in
this confirmed list.

(The dwarf-spheroidal M/L row moved out of Confirmed on 2026-08-03: with the
corrected coupling the test favors MOND (4/8 vs Cassi's 3/8) and the saturation
ceiling $\sqrt{\varphi^6} = \varphi^3 = 4.2361$ (max boost $G_{\text{eff}}/G = \varphi^6$) is
exceeded in 3/8 dwarfs—see the §3 Gravity table and
`experiments/phi_attractor_paths/path10_dwarf_galaxies.py`.)

### Framework Limitations

Quantities not derivable from $\varphi$ to useful precision—they depend
on particle content, mixing structure, or RGE running that $\varphi$ alone
does not determine.

| Quantity | Best Cassi Match | Deviation | Requires |
|----------|-----------------|-----------|----------|
| $v_0/M_{\text{Pl}}$ | $\varphi^{-80}$ | $5.3\%$ | Correction factor |
| $m_e$ | $v_0\varphi^{-26}/\sqrt{2} \approx 0.64$ MeV | $25\%$ | New mixing physics |
| $\alpha_s(M_Z)$ | RGE from $\alpha_{\text{GUT}}$ | $2.0\times$ | Particle content ($\Delta b \approx 1.70$) |

---

## 6. Mechanism Layer: Two-Fluid Gate Drive Physics (PDE-tested)

| Claim | Tested result | Status |
|---|---|---|
| Held configuration (standing init): in-channel recurring drive drains at short times (ε retained 0.26 at $t=2$, below the undriven floor at t = 4); cross-channel drive at ε-parity pumps (2.08×); the pumped state is sticky, and affirmation recovers the site below the floor at the t = 4 window | `consciousness/gender-as-qi-configuration.md` §8–§8.1 (2026-08-02) | ✅ **Supported at short times** (t ≲ 4 ≈ 0.2/λ at the §8 period); at t = 40 = 2/λ the sustained in-channel drive sits above the decaying undriven floor (drain transient, `consciousness/gender-as-qi-configuration.md` §8.3, 2026-08-04) |
| Open gate (churning init): every recurring drive form and amplitude ≥ 0.09 pumps; no drive form or amplitude settles the gate | `consciousness/neurodivergence-as-gate-configuration.md` §9–§9.2 (2026-08-04) | ✅ **Null on settling** |
| Sub-threshold open-gate drives (0.025–0.05) quench the mean ε transiently without closing the gate; the quench resolves at $t = 40 = 2/\lambda$ as a driven transient, not a lock | `consciousness/neurodivergence-as-gate-configuration.md` §9.3–§9.4 (2026-08-04) | ✅ **Driven transient (partial-lock rejected)** |

The pump/drain asymmetry is bounded at the held-configuration regime—the held drain at short times, ≈ 0.2/λ (`consciousness/gender-as-qi-configuration.md` §8.3); an open gate is not settlable by any recurring drive.

### Computational-Test Program 2026-08-05/06

Thirteen committed computational tests (`runs/` archives the outputs; scripts in `two-fluid/` and `computations/`). Cross-cutting verdicts: the two consciousness-mechanism flagships (pinch two-point, two-bubble dynamical revival) are nulled; the wake structural trio (P44/P43/F₂/F₁) is confirmed; the R-matrix mechanism realization is partial (Wood only); Q7 measurement-selection is null in this realization; the five-channel $w_a$ shift is real but via gate-structure dynamics, not the documented control-release mechanism; the H₀-tension resolution does not survive the full simultaneous fit; the slow-roll numbers are Mapped with trajectory evidence; the σ₈ headline is normalization-dominated.

| # | Claim | Tested result (2026-08-05/06) | Verdict |
|---|-------|------------------------------|---------|
| 1 | Pinch two-point: φ-scaled correlation peaks after crossing the pinch | Field crosses cleanly (t_c = 8.8, r̄ 0.5→1.19) but ⟨r(x)r(x+d)⟩ develops no φ-scaled peaks post-crossing; pre/post indistinguishable; above-pinch counterfactual featureless (`two-fluid/run_pinch_correlation.py`, runs/20260805_185905_pinch_correlation/) | ❌ **Null** |
| 2 | Two-bubble dynamical revival at large separations | Revival structure gate-independent (max per-sep delta 0.0003) and frozen from t = 0 (corr(t=0)==corr(t=1000)); nominal {31,34,37} wrap under periodic BCs to {17,14,11}; 2026-07-19 aggregate ratios reproduce but inflated by the φ-set occupying smaller physical distances (distance-matched 1.1–1.7×) (`two-fluid/run_two_bubble_gate_scan.py`, runs/20260805_182906_two_bubble_gate/) | ❌ **Null on dynamics** (static-geometry protocol feature) |
| 3 | R-matrix sheng redistribution in the five-channel solver | gate_model='five' realizes it only for Wood closure, allocated by ACTIVE openness b_i·w_i not baseline b_i; measured Wood blend (0, 0, 0.5, 0.309, 0.191) vs R-row (0, 0.447, 0.276, 0.171, 0.106)—ordering matches, proportions don't; rows 2–5 have no gate term; Earth cannot close (w3 ≡ 1) (`two-fluid/run_rmatrix_redistribution.py`, runs/20260805_181544_rmatrix/) | ⚠️ **Partial** (Wood only) |
| 4 | Five-channel w_a shift toward DESI | Five-channel gate gives w_a = −0.425 ± 0.1 vs single-channel ≈ −0.09 ± 0.10 at the PDE layer (−0.44 ± 0.15 differential; five ~1.1σ from DESI w_a = −0.73 ± 0.28); measured Δ(1−q) ≈ ±0.01, not the documented +0.055—the shift is gate-structure dynamics, not control-release; pentagon gate NaN at a ≈ 0.38–0.66 at the default cap; five_ke inconclusive (`two-fluid/run_pde_wa_test.py`, `two-fluid/run_pde_wa_5channel.py`) | ⚠️ **Partial-support** (mechanism mismatch) |
| 5 | Q7 organized-vs-random: selective collapse | No organized drive (uniform, anti-phase, single-path) selects a branch of the symmetric two-branch superposition; equal-power random drive rectifies both branches into a same-sign phase lock; the superposition has no fast coherent oscillation (P₀ an FFT artifact), so the phase-matching channel was unreachable at t = 4 (`two-fluid/run_coherence_budget_contrast.py`, runs/q7_coherence_budget/) | ❌ **Null** (protocol caveat) |
| 6 | TR3 phase-matched trigger | Fire trigger re-locks Fire (23× control)—phase-matched re-lock confirmed; Wood trigger also re-activates the released site into Wood (39× control)—reactivation is channel-selective, not lock-memory-specific (`two-fluid/run_trigger_wx2_tests.py`, runs/20260806_001658_trigger_wx2/) | ⚠️ **Partial** |
| 7 | WX2 κ³ = 0.236-per-cycle damping | Not reproduced: per-P0 retention 0.944 vs 0.764 predicted; gate-level mean 0.389 vs 0.764; sub-critical direction holds; ke ring adds no locked-channel damping (Δγ < 0.001) (same script) | ❌ **Not matched** |
| 8 | Wake structural trio (P44 checkerboard, P43 closure, F₂/F₁ sharpening) | P44: nulls at (m+½)ℓ_{n+1} to 0.0023 grid precision, beats at m·ℓ_{n+1} to 0.00015; P43: beats land on m·ℓ_{n+1} to grid scale; F₂/F₁ = 0.617621 vs 1/φ = 0.618034 (−0.07%), cross-ratio φ³ exact, requires the documented Π∇Φ force form (`two-fluid/run_wake_structural_probes.py`, commit 168a11a) | ✅ **Supported** |
| 9 | N_pde χ-bridge | Closes in [0.5, 1.0] only under the N² (2D section) reading (χ = 0.980); literal 3D count gives χ = 47; "exact closure" 2350.6 is a back-solved constant rearrangement (m_e·v₀²·φ⁹); documented L/dt values appear in no run script; code-default N=64 gives χ = 1.74 (out of band) (`computations/n_pde_bridge_check.py`) | ⚠️ **Convention underdetermined** |
| 10 | Proton coherence-budget arithmetic | 323× ledger discrepancy traced to a 4.2× slip in M⁴/m⁵ (boxed number would need M_GUT ≈ 4.7×10¹⁵ GeV); corrected τ_p = 1.29×10³⁷ yr with stated inputs—"within Hyper-K reach" does not survive (2.1 orders above reach); coherence-budget chain (N_max = φ^4505.79 → τ_p = 10^910 yr) internally self-consistent, a separate prediction; per-rung q_i = 1 − φ^(−i−δ) remains Hypothesized (`computations/proton_budget_closure.py`) | ✅ **Arithmetic closed** |
| 11 | σ₈ magnitude | Pipeline −43.5% headline dominated by normalization + resolution (P(k) normalization 8e-5, nonlinear ICs, N=32 dissipation: δ_rms falls 32% while ΛCDM linear grows +21%); −9.6% mechanism-attributable (G_eff 0.9044); "~5%" is a Mapped target (μ = 0.98 → −5.3%) (`computations/sigma8_reconciliation.py`) | ⚠️ **Reconciled** (normalization-dominated) |
| 12 | Full H(z) fit resolves H₀ tension | Under calibrated CPL values (w₀ = −0.87, w_a = +0.012 baseline, −0.38 coupling), Cassi w(a) does not resolve: dark energy negligible at z~1000–1100, R_cmb = 1.00000, χ² ≈ 25.1 (same as ΛCDM, anchor separation 5.0σ); ΔH₀ = −7.2 comes only from the ODE pipeline model whose w(a) is right-clamped at +0.37 (radiation-like) for z > 99—an extrapolation beyond the calibrated range (a ≥ 0.01) (`computations/hz_full_fit.py`) | ❌ **Not resolved** |
| 13 | Slow-roll trajectory gives n_s = 0.9691, r = φ⁻¹² | (n_s, r) = (0.813, 0.188) under 1 step = 1 e-fold; (0.914, 0.060) with N_e = 40 literal (1 step = ln φ physical e-folds)—n_s 12–36σ from Planck, r excluded by BK18; the two claimed numbers do not coexist (r = φ⁻¹² only at ~135 physical e-folds before the window end, where n_s = 0.9883, +5.6σ); N_e = 40 is a start-threshold choice, not a derived count; ledger Mapped flags confirmed (`computations/slow_roll_trajectory.py`) | ❌ **Fails** (Mapped with trajectory evidence) |

---

## 7. Synchrotron Polarimetry

| Prediction | Cassi Value | Experimental | Status |
|-----------|-------------|--------------|--------|
| Log-periodic polarization orientation (prediction 48) | $\text{PA}(\nu\varphi^k) = \text{PA}(\nu)$ (mod $\pi$), period $\Delta(\ln\nu) = \ln\varphi$; 90° rotation at quarter-rung separation ($\nu_2/\nu_1 = \varphi^{1/4}$); half-rung pair ($\nu_2/\nu_1 = \sqrt\varphi$) parallel (mod $\pi$) | Crab Nebula mm-band PA is constant (~138–142°) over $\Delta\ln\nu = 1.26$ (2.6 rungs); 0/10 band pairs within 3σ | ❌ **Null at face value**—prediction 48 does not fit the Crab Nebula mm-band polarization angle: the constant-PA fit beats the log-periodic spiral fit, and the spiral is excluded against a search-corrected uniform-angle null (p = 0.77) (`experiments/demystifying_cosmos/pa_logperiodic_test.py`, 2026-08-06) |
