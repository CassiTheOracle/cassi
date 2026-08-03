# Why Observables Sit Between Rungs: The Two-Fluid Phase Mechanism for Fractional Cascade Offsets

## Status: Hypothesized mechanism, Empirical catalog—August 2026

## Abstract

No observable sits exactly on a cascade rung. The fractional offsets $\delta n = n - \lfloor n \rfloor$ in $n = \log_\varphi(\text{scale})$ are not noise—they are the dynamical fingerprint of the two-fluid interaction at each scale. Perfect rung alignment would mean the Yang and Yin wakes sit in perfect phase at that scale (coherence $q \to 1$); the de-resonance principle forbids that lock, so every scale inherits a local phase difference $\delta n = \Delta\varphi/2\pi$. The wake envelope (`foundations/wake-geometry.md` §2) supplies the dynamically-distinguished positions—peaks at $u = 1+\log_\varphi m$, zeros at $u = 1+\log_\varphi(m+\tfrac12)$—and the empirical catalog shows the lightest state of each terminated sector sitting at the crossing positions (electron, pion, QCD scale, nucleons, down quark) while interior stable states sit at integer rungs (muon, J/ψ, D, Σ, Z). The full 38-state catalog is statistically uniform in $\delta n$; the PDE probe (run 2026-08-03) verified the phase-lag mechanism $\delta n(\psi) = 0.060 - 0.204\,\psi$ rungs for the two-bubble standing pattern and found linear conversion alone leaves the extremum unmoved. The mechanism's case rests on the sharp individual placements (μ at 96.000, 0.01%) and on the nonlinear gate branch, which remains untested.

---

## 1. The alignment–coherence correspondence (Hypothesized)

Plain-English statement: exact rung alignment means the two fluids are in phase at that scale; every offset is a phase lag, and its size measures how far the local dynamics sit from the coherent limit.

The two-fluid state at scale $\ell_n$ superposes the Yang and Yin wakes. The observable's scale is fixed where the wakes interfere, so define $\Delta\varphi$ as the phase difference between the two wakes at the condensation site. The rung offset is that phase lag in rung units:

$$\delta n = \frac{\Delta\varphi}{2\pi}$$

Perfect alignment, $\delta n = 0$, requires $\Delta\varphi = 0$—the fully coherent limit $q \to 1$. De-resonance forbids exact lock (`foundations/wake-geometry.md` §2(b): the wakes can never share a crest, because $\varphi$ is irrational), so $\delta n \neq 0$ generically. The correction posture of `principles/de-resonance-principle.md` §2 is the same statement in multiplicative form: every quantity is near a $\varphi$-power with $(1 + \delta) = \varphi^{\delta n}$.

The correspondence is directional. The sharpest placements in the catalog mark the scales closest to the coherent limit; the coarsest mark the most strongly de-coherent scales. Whether $\delta n$ correlates with an independent measure of coherence (the Qi-gate opening or conversion rate at that scale) is testable in the PDE (§5, T1).

## 2. What the envelope allows: the special positions (Derived)

The wake envelope of `foundations/wake-geometry.md` §2(c) is the only dynamically-distinguished ruler in the cascade. In real space its peaks sit at $x = m\,\ell_{n+1}$ and its zeros at $x = (m+\tfrac{1}{2})\ell_{n+1}$. Mapped to $\ln$-rung units $u = \log_\varphi(x/\ell_n)$:

$$\boxed{\text{peaks at } u = 1 + \log_\varphi m, \qquad \text{zeros at } u = 1 + \log_\varphi\!\left(m+\tfrac{1}{2}\right)}$$

Only the first peak ($m=1$) is an integer rung; the first zero sits at $u = -0.440$—not at the half-rung $-0.5$. The "half-rung" reading of the envelope is real-space language ($x = \ell_{n+1}/2$); the geometric-mean half-step $u = \pm\tfrac{1}{2}$ of `foundations/wake-geometry.md` §1(c) is a separate object. The probe (`two-fluid/run_rung_offset_probe.py`, Panel A) verifies these positions and confirms that in the coherent limit the interference extremum is pinned at the first-cell crossing $u = -0.440$—0.06 rungs above the half-rung, a 3% displacement that is the natural near-miss scale of the mass catalog.

An observable set by the interference pattern can sit at one of these positions in the coherent limit; the local dynamics then shift it by $\delta n$.

## 3. The empirical catalog (Empirical)

Full PDG scan, $n = \log_\varphi(M_{\text{Pl}}/m)$ with $M_{\text{Pl}} = 1.2209\times10^{19}$ GeV, 38 states, $s$ = distance to the nearest special point (integer or half-integer rung):

| State | $m$ (GeV) | $n$ | $\delta n$ (frac) | $s$ (rungs) | Residual |
|-------|-----------|-----|-------------------|-------------|----------|
| t | 172.69 | 80.624 | 0.624 | 0.124 | 6.2% |
| H | 125.25 | 81.291 | 0.291 | 0.209 | 10.6% |
| Z | 91.19 | 81.951 | 0.951 | 0.049 | 2.4% |
| W | 80.37 | 82.213 | 0.213 | 0.213 | 10.8% |
| Υ | 9.460 | 86.660 | 0.660 | 0.160 | 8.0% |
| B$_c$ | 6.274 | 87.513 | 0.513 | 0.013 | 0.6% |
| Λ$_b$ | 5.620 | 87.742 | 0.742 | 0.242 | 12.3% |
| B$_s$ | 5.367 | 87.838 | 0.838 | 0.162 | 8.1% |
| B | 5.279 | 87.872 | 0.872 | 0.128 | 6.4% |
| b | 4.18 | 88.357 | 0.357 | 0.143 | 7.1% |
| ψ(2S) | 3.686 | 88.618 | 0.618 | 0.118 | 5.9% |
| J/ψ | 3.097 | 88.980 | 0.980 | 0.020 | 1.0% |
| Λ$_c$ | 2.286 | 89.611 | 0.611 | 0.111 | 5.5% |
| D$_s$ | 1.968 | 89.922 | 0.922 | 0.078 | 3.8% |
| D | 1.865 | 90.034 | 0.034 | 0.034 | 1.7% |
| τ | 1.777 | 90.135 | 0.135 | 0.135 | 6.7% |
| Ω | 1.672 | 90.260 | 0.260 | 0.240 | 12.2% |
| Ξ* | 1.532 | 90.443 | 0.443 | 0.057 | 2.8% |
| Σ* | 1.384 | 90.654 | 0.654 | 0.154 | 7.7% |
| Ξ | 1.315 | 90.760 | 0.760 | 0.240 | 12.2% |
| c | 1.27 | 90.833 | 0.833 | 0.167 | 8.4% |
| Δ | 1.232 | 90.896 | 0.896 | 0.104 | 5.1% |
| Σ | 1.193 | 90.963 | 0.963 | 0.037 | 1.8% |
| Λ | 1.116 | 91.102 | 0.102 | 0.102 | 5.0% |
| φ | 1.019 | 91.289 | 0.289 | 0.211 | 10.7% |
| η′ | 0.958 | 91.419 | 0.419 | 0.081 | 4.0% |
| n | 0.940 | 91.459 | 0.459 | 0.041 | 2.0% |
| p | 0.938 | 91.462 | 0.462 | 0.038 | 1.9% |
| ω | 0.783 | 91.838 | 0.838 | 0.162 | 8.1% |
| ρ | 0.775 | 91.858 | 0.858 | 0.142 | 7.1% |
| η | 0.548 | 92.580 | 0.580 | 0.080 | 3.9% |
| K | 0.494 | 92.796 | 0.796 | 0.204 | 10.3% |
| π | 0.1396 | 95.421 | 0.421 | 0.079 | 3.9% |
| μ | 0.1057 | 96.000 | 0.000 | 0.000 | 0.01% |
| s | 0.093 | 96.265 | 0.265 | 0.235 | 12.0% |
| d | 0.0047 | 102.481 | 0.481 | 0.019 | 0.9% |
| u | 0.0022 | 104.084 | 0.084 | 0.084 | 4.1% |
| e | 0.000511 | 107.079 | 0.079 | 0.079 | 3.9% |

The statistics, stated plainly: the mean distance to the nearest special point is $\bar{s} = 0.118$ rungs against 0.125 uniform, and 42% of states sit within 0.10 rungs of a special point against 40% uniform. **The full catalog shows no clustering at $\{0, \tfrac{1}{2}\}$ beyond chance.** The mass-scan highlights of `foundations/wake-geometry.md` §3(e) were selection—the best of ~40 placements.

What remains after the baseline: a small set of individually sharp placements ($s \le 0.05$ rungs, i.e. residuals $\le 2.5\%$):

| State | $n$ | Special point | $s$ | Residual |
|-------|-----|---------------|-----|----------|
| μ | 96.000 | 96 | 0.000 | 0.01% |
| B$_c$ | 87.513 | 87.5 | 0.013 | 0.6% |
| d | 102.481 | 102.5 | 0.019 | 0.9% |
| J/ψ | 88.980 | 89 | 0.020 | 1.0% |
| D | 90.034 | 90 | 0.034 | 1.7% |
| Σ | 90.963 | 91 | 0.037 | 1.8% |
| p | 91.462 | 91.5 | 0.038 | 1.9% |
| n | 91.459 | 91.5 | 0.041 | 2.0% |
| Z | 81.951 | 82 | 0.049 | 2.4% |

A uniform catalog of 38 states yields ~1.5 placements with $s < 0.02$; three are observed (μ, B$_c$, d)—consistent with chance. The muon placement is the only individually improbable event: a single mass within 0.0001 rungs of an integer has probability $2\times10^{-4}$, and over 38 states about 0.8%. Borderline—worth taking seriously, not yet evidence.

The boundary pattern that motivates the mechanism: the lightest state of each terminated sector sits at a half-rung.

| Sector edge | State | Half-rung | Residual |
|-------------|-------|-----------|----------|
| Lepton tower, lightest | e | 26.5 (Yukawa ladder) | 1.4% |
| Lepton tower, heaviest | τ | 9.5 (Yukawa ladder) | 1.5% |
| Hadron tower, lightest | π | 95.5 | 3.9% |
| Confinement boundary | Λ_QCD | 94.5 | 2.1% |
| Baryon tower, lightest | p, n | 91.5 | 1.9–2.0% |
| Quark sector, lightest | d | 102.5 | 0.9% |

Interior stable states sit at integer rungs: μ (96.000), J/ψ (89), D (90), Σ (91), Z (82).

Caveats, stated plainly: the light-quark and Λ_QCD masses are scheme-dependent (MS-bar running masses at 2 GeV), and the u/d pair straddles its special points rather than sitting on them (u at 104.084, d at 102.481, spacing 1.60 rungs—not a special spacing). The electron's half-rung lives on the Yukawa ladder $n = \log_\varphi((v_0/\sqrt2)/m)$—the frame where its mass is generated—while its Compton-ladder placement (107.08, 3.9% off rung 107) is a near-miss rather than a hit. W, H, t and most of the catalog sit at no special point at all.

## 4. The mechanism hypothesis

### 4.1 Selection: why sector edges sit at crossings

A terminated spectrum—the lepton tower ending at e, the hadron tower at π, confinement at Λ_QCD—has a boundary in the cascade: no lighter state exists to continue the $\varphi$-spacing. The boundary acts as a free end for the sector's mode: the wavefunction must close at the boundary, and the lowest mode of a half-open interval sits at the midpoint of its two neighbors—the wake-crossing at $n \pm \tfrac{1}{2}$. This is the wave-mechanical form of the boundary-state idea: the edges of each spectrum are crossing states, the interior states are bubble states. The muon—interior to the lepton tower—is the sharpest bubble placement in the catalog.

### 4.2 The residual: δn as local phase lag

Within a special-position class, the residual $\delta n$ encodes the phase lag between the wakes at the site. The probe (T1, run 2026-08-03) measured the relation in the two-bubble standing pattern: the extremum sits at $x_{\max} = \varphi/2 - \psi/(4\pi)$, i.e.

$$\boxed{\delta n(\psi) = 0.060 - 0.204\,\psi \ \text{rungs} \qquad (\psi \text{ in radians, } f=1)}$$

around the coherent point, where $\psi$ is the relative phase between the two bubbles' wakes. The catalog's crossing-state residuals then correspond to modest phase lags: the electron's $-0.03$ rungs on the Yukawa ladder maps to $\psi \approx 0.44$ rad (25°), the nucleons' $-0.04$ to $\psi \approx 0.49$ rad, the pion's $-0.08$ to $\psi \approx 0.69$ rad. Amplitude asymmetry alone does not move the extremum at $\psi = 0$—the $\varphi$-spacing geometry locks the crossing—while at finite $\psi$ it moves through the phase composition (probe table 3). The alignment–coherence correspondence (§1) turns sharpness into a coherence meter: the muon's 0.01% marks a near-coherent scale; the W, H, t residuals of ~10% mark strongly de-coherent scales.

### 4.3 The dressed-rung form (Speculative)

A minimal quantitative form: the observable is the dressed state of two adjacent rungs coupled by $V$; the offset is the mixing probability, $\delta n \to \tfrac{1}{2}$ as the inter-rung coupling dominates (boundary states) and $\delta n \to 0$ for isolated rungs. The per-sector coupling $V$ is what the PDE must supply; no independent $V$ exists yet, so this form is a placeholder for the PDE result, not a result.

## 5. The decisive tests (falsifiable)

**T1—PDE probe (primary).** Run 2026-08-03 (`two-fluid/run_rung_offset_probe.py`): two bubbles at $x = 0$ and $x = \varphi$ emit the wake pair; with $V = 0$ initial conditions the fields are exactly standing (d'Alembert, no dispersion), so the extremum of $|E_Y|$ is the antinode of the initial envelope, measured cleanly inside the wall round-trip time. Results: (a) at $\lambda = 0$, $\psi = 0$ the extremum sits at $u = -0.440$, exactly the analytic antinode, and the relative phase $\psi$ moves it continuously—$\delta n(\psi) = 0.060 - 0.204\,\psi$ rungs, PDE = analytic to $10^{-3}$ rungs at every scan point; (b) conversion $\lambda$ alone does **not** move the extremum in the linear regime ($\lambda \le 0.1$, $t \le 2$: no shift to $10^{-3}$ rungs)—the phase difference, not the coupling strength, is the $\delta n$ dial in the linear standing-wave regime; (c) the amplitude-ratio scan at finite $\psi$ reproduces the analytic composition exactly ($f = 1.0, 0.8, 0.6$). The nonlinear gate regime ($q < 1$, amplitude-saturating conversion) is the remaining untested branch: it can rephase the wakes where linear conversion cannot.

**T2—catalog statistics.** Extend the scan (neutrino masses, future states). The mechanism predicts the sharp-placement count does not grow with $N$: the uniform baseline is the null, and a growing count would confirm clustering.

**T3—sector-edge prediction.** The next discovered lightest state of a new sector should land at a half-rung; interior states at integer rungs.

## 6. Epistemic boundaries

- **Derived**: the envelope special positions (§2, probe-verified); the catalog numbers (§3); the $\delta n(\psi)$ phase-lag relation (§4.2, analytic + PDE to $10^{-3}$ rungs).
- **Hypothesized**: the alignment–coherence correspondence (§1); sector-edge selection at half-rungs (§4.1); the catalog mapping onto $\psi$ (§4.2); the nonlinear-gate branch of T1 (amplitude-saturating conversion can rephase the wakes where linear conversion cannot).
- **Speculative**: the dressed-rung form (§4.3); the per-sector frame choice (Yukawa vs Compton ladder).
- **Not supported**: any claim that the full mass catalog clusters at special points—the 38-state scan is uniform, and only the muon placement is individually improbable (≈0.8% over the catalog).

## 7. References

- `foundations/wake-geometry.md` §1–3—wake pair, envelope, half-steps, mass-scan catalog
- `principles/de-resonance-principle.md`—why exact alignment is forbidden; correction posture
- `foundations/dimensionful-cascade.md` §6—wake wavelengths, sound-horizon half-step
- `foundations/deriving-remaining-gaps.md` §2—electron mass status (external, class **E**)
- `predictions/falsifiable-predictions.md` §5—predictions 43–45 (wake closure, checkerboard, closure ladder)
- `two-fluid/run_rung_offset_probe.py`—T1 probe: two-bubble standing pattern, $\delta n(\psi)$ measurement
