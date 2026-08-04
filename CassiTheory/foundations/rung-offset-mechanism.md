# Why Observables Sit Between Rungs: The Two-Fluid Phase Mechanism for Fractional Cascade Offsets

## Status: Derived quantization, Hypothesized selection, Empirical catalog—August 2026

## Abstract

No observable sits exactly on a cascade rung. The fractional offsets $\delta n = n - \lfloor n \rfloor$ in $n = \log_\varphi(\text{scale})$ are not noise—they are the dynamical fingerprint of the two-fluid interaction at each scale. Perfect rung alignment would mean the Yang and Yin wakes sit in perfect phase at that scale (coherence $q \to 1$); the de-resonance principle forbids that lock, so every scale inherits a local phase difference $\delta n = \Delta\varphi/2\pi$. The wake envelope (`foundations/wake-geometry.md` §2) supplies the dynamically-distinguished positions—peaks at $u = 1+\log_\varphi m$, zeros at $u = 1+\log_\varphi(m+\tfrac12)$—and the empirical catalog shows the lightest state of each terminated sector sitting at the crossing positions (electron, pion, QCD scale, nucleons, down quark) while interior stable states sit at integer rungs (muon, J/ψ, D, Σ, Z). The full 38-state catalog is statistically uniform in $\delta n$; the PDE probe (run 2026-08-03) verified the phase-lag mechanism $\delta n(\psi) = 0.060 - 0.204\,\psi$ rungs for the two-bubble standing pattern and found that conversion—linear or gated—leaves the extremum unmoved (the gate sources wake harmonics but cannot rephase the crossing). The mechanism's case rests on the sharp individual placements (μ at 96.000, 0.01%) and on the open question of what sets the wake phase $\psi$ at each rung—the closure-emission reading was tested against the 38-state catalog and is not supported (§5 T4).

---

## 1. The alignment–coherence correspondence (Hypothesized)

Plain-English statement: exact rung alignment means the two fluids are in phase at that scale; every offset is a phase lag, and its size measures how far the local dynamics sit from the coherent limit.

The two-fluid state at scale $\ell_n$ superposes the Yang and Yin wakes. The observable's scale is fixed where the wakes interfere, so define $\Delta\varphi$ as the phase difference between the two wakes at the condensation site. The rung offset is that phase lag in rung units:

$$\delta n = \frac{\Delta\varphi}{2\pi}$$

Perfect alignment, $\delta n = 0$, requires $\Delta\varphi = 0$—the fully coherent limit $q \to 1$. De-resonance forbids exact lock (`foundations/wake-geometry.md` §2(b): the wakes can never share a crest, because $\varphi$ is irrational), so $\delta n \neq 0$ generically. The correction posture of `principles/de-resonance-principle.md` §2 is the same statement in multiplicative form: every quantity is near a $\varphi$-power with $(1 + \delta) = \varphi^{\delta n}$.

The correspondence is directional. The sharpest placements in the catalog mark the scales closest to the coherent limit; the coarsest mark the most strongly de-coherent scales. Whether $\delta n$ correlates with an independent measure of coherence (the Qi-gate opening or conversion rate at that scale) is testable in the PDE (§5, RO1).

## 2. What the envelope allows: the special positions (Derived)

The wake envelope of `foundations/wake-geometry.md` §2(c) is the only dynamically-distinguished ruler in the cascade. In real space its peaks sit at $x = m\,\ell_{n+1}$ and its zeros at $x = (m+\tfrac{1}{2})\ell_{n+1}$. Mapped to $\ln$-rung units $u = \log_\varphi(x/\ell_n)$:

$$\boxed{\text{peaks at } u = 1 + \log_\varphi m, \qquad \text{zeros at } u = 1 + \log_\varphi\!\left(m+\tfrac{1}{2}\right)}$$

Only the first peak ($m=1$) is an integer rung; the first zero sits at $u = -0.440$—not at the half-rung $-0.5$. The "half-rung" reading of the envelope is real-space language ($x = \ell_{n+1}/2$); the geometric-mean half-step $u = \pm\tfrac{1}{2}$ of `foundations/wake-geometry.md` §1(c) is a separate object. The probe (`two-fluid/run_rung_offset_probe.py`, Panel A) verifies these positions and confirms that in the coherent limit the interference extremum is pinned at the first-cell crossing $u = -0.440$—0.06 rungs above the half-rung, a 3% displacement that is the natural near-miss scale of the mass catalog.

An observable set by the interference pattern can sit at one of these positions in the coherent limit; the local dynamics then shift it by $\delta n$. The two-bubble curve of §4.2 is the truncation of a true field sum: the probe verifies (Panel D, `two-fluid/run_rung_offset_probe_panel_d.py`) that wakes from bubbles two rungs up and one rung down enter the same phasor composition with the framework amplitudes $\varphi^{-|d|}$, PDE = analytic to $10^{-3}$ rungs, so the crossing is a multi-rung response (§5 T6).

## 3. The empirical catalog (Empirical)

Full PDG scan, $n = \log_\varphi(M_{\text{Pl}}/m)$ with $M_{\text{Pl}} = 1.2209\times10^{19}$ GeV, 38 states, $s$ = distance to the nearest special point (integer or half-integer rung). The $\psi$ and $\Delta\psi$ columns apply the mechanism of §4.2 to every state: $\psi = (0.060 - \delta n)/0.204$ with $\delta n$ the signed residual, $\Delta\psi$ from the PDG mass error (0.00 means $< 0.005$):

| State | $m$ (GeV) | $n$ | $\delta n$ (frac) | $s$ (rungs) | Residual | $\psi$ (rad) | $\Delta\psi$ |
|-------|-----------|-----|-------------------|-------------|----------|--------------|--------------|
| t | 172.69 | 80.624 | 0.624 | 0.124 | 6.2% | −0.31 | 0.02 |
| H | 125.25 | 81.291 | 0.291 | 0.209 | 10.6% | 1.32 | 0.01 |
| Z | 91.19 | 81.951 | 0.951 | 0.049 | 2.4% | 0.53 | 0.00 |
| W | 80.37 | 82.213 | 0.213 | 0.213 | 10.8% | −0.75 | 0.00 |
| Υ | 9.460 | 86.660 | 0.660 | 0.160 | 8.0% | −0.49 | 0.00 |
| B$_c$ | 6.274 | 87.513 | 0.513 | 0.013 | 0.6% | 0.23 | 0.00 |
| Λ$_b$ | 5.620 | 87.742 | 0.742 | 0.242 | 12.3% | −0.89 | 0.00 |
| B$_s$ | 5.367 | 87.838 | 0.838 | 0.162 | 8.1% | 1.09 | 0.00 |
| B | 5.279 | 87.872 | 0.872 | 0.128 | 6.4% | 0.92 | 0.00 |
| b | 4.18 | 88.357 | 0.357 | 0.143 | 7.1% | 1.00 | 0.07 |
| ψ(2S) | 3.686 | 88.618 | 0.618 | 0.118 | 5.9% | −0.29 | 0.00 |
| J/ψ | 3.097 | 88.980 | 0.980 | 0.020 | 1.0% | 0.39 | 0.00 |
| Λ$_c$ | 2.286 | 89.611 | 0.611 | 0.111 | 5.5% | −0.25 | 0.00 |
| D$_s$ | 1.968 | 89.922 | 0.922 | 0.078 | 3.8% | 0.68 | 0.00 |
| D | 1.865 | 90.034 | 0.034 | 0.034 | 1.7% | 0.13 | 0.00 |
| τ | 1.777 | 90.135 | 0.135 | 0.135 | 6.7% | −0.37 | 0.00 |
| Ω | 1.672 | 90.260 | 0.260 | 0.240 | 12.2% | 1.47 | 0.00 |
| Ξ* | 1.532 | 90.443 | 0.443 | 0.057 | 2.8% | 0.57 | 0.01 |
| Σ* | 1.384 | 90.654 | 0.654 | 0.154 | 7.7% | −0.46 | 0.01 |
| Ξ | 1.315 | 90.760 | 0.760 | 0.240 | 12.2% | 1.47 | 0.00 |
| c | 1.27 | 90.833 | 0.833 | 0.167 | 8.4% | 1.12 | 0.16 |
| Δ | 1.232 | 90.896 | 0.896 | 0.104 | 5.1% | 0.81 | 0.02 |
| Σ | 1.193 | 90.963 | 0.963 | 0.037 | 1.8% | 0.47 | 0.00 |
| Λ | 1.116 | 91.102 | 0.102 | 0.102 | 5.0% | −0.20 | 0.00 |
| φ | 1.019 | 91.289 | 0.289 | 0.211 | 10.7% | 1.33 | 0.00 |
| η′ | 0.958 | 91.419 | 0.419 | 0.081 | 4.0% | 0.69 | 0.00 |
| n | 0.940 | 91.459 | 0.459 | 0.041 | 2.0% | 0.50 | 0.00 |
| p | 0.938 | 91.462 | 0.462 | 0.038 | 1.9% | 0.48 | 0.00 |
| ω | 0.783 | 91.838 | 0.838 | 0.162 | 8.1% | 1.09 | 0.00 |
| ρ | 0.775 | 91.858 | 0.858 | 0.142 | 7.1% | 0.99 | 0.00 |
| η | 0.548 | 92.580 | 0.580 | 0.080 | 3.9% | −0.10 | 0.00 |
| K | 0.494 | 92.796 | 0.796 | 0.204 | 10.3% | 1.29 | 0.00 |
| π | 0.1396 | 95.421 | 0.421 | 0.079 | 3.9% | 0.68 | 0.00 |
| μ | 0.1057 | 96.000 | 0.000 | 0.000 | 0.01% | 0.30 | 0.00 |
| s | 0.093 | 96.265 | 0.265 | 0.235 | 12.0% | 1.45 | 0.88 |
| d | 0.0047 | 102.481 | 0.481 | 0.019 | 0.9% | 0.38 | 1.05 |
| u | 0.0022 | 104.084 | 0.084 | 0.084 | 4.1% | −0.12 | 2.31 |
| e | 0.000511 | 107.079 | 0.079 | 0.079 | 3.9% | −0.09 | 0.00 |

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

The mechanism applied to the whole catalog reads every residual as a phase lag: $\psi = (0.060 - \delta n)/0.204$, with $\Delta\psi$ from the PDG mass error. The map is statistically structureless (T5): the circular concentration $R = 0.799$ is what the uniform-frac baseline produces (0.774 ± 0.033, $p = 0.22$); a free-$\omega$ phase advance $\psi(n) = \psi_0 + \omega n$ leaves $\omega \approx 0.003$ rad/rung (residual 0.201 vs 0.219 ± 0.033, $p = 0.31$); and no named base angle—$2\pi/\varphi^2$, $3\pi/10$, $2\pi/5$, $\pi/\varphi$, $2\pi\ln\varphi$, $2\pi/\varphi^3$, $2\pi/\varphi^4$—fits better than chance ($p \ge 0.22$). The sharp placements are the states whose $\psi$ lies nearest the coherent crossing $\psi^* = A_0/B_0 = 0.294$ rad ($\delta n = 0$); their band $[0.13, 0.68]$ rad is the selection criterion in phase units, not an independent pattern. The light-quark rows carry scheme-scale $\Delta\psi$ (d: ±1.05 rad, u: ±2.31 rad), so their sharpness is scheme-bound: d's 0.9% holds only within the MS-bar choice. The map's full data table is `experiments/rung_offset_closure/catalog_psi_map.csv`.

## 4. The mechanism hypothesis

### 4.1 Selection: why sector edges sit at crossings (mode quantization)

The pool-cell quantization (`computations/pooled_zone_modes.py`) supplies the
wave-mechanical form of the boundary-state idea. The energy pool of a state is
the constructive-overlap cell of the rotating wake pair
(`foundations/wake-geometry.md` §2): the two wakes are the two phases of one
string motion, and their overlap—the pool—pulses at the beat period
$\ell_{n+1}/c$, so the state's standing wave must close on the cell bounded by
the envelope zeros (the voids, where the overlap vanishes).

The cell $[n, n+1]$ in rung space closes with nodes at both ends, and the two
wake phases select the two parity classes:

$$\psi_1(u) = \sin\!\big(\pi(u-n)\big):\ \text{nodes at } n, n{+}1;\ \text{antinode at } n + \tfrac{1}{2} \qquad \text{(Yin, crossing)}$$
$$\psi_2(u) = \cos\!\big(\pi(u-n)\big):\ \text{antinodes at the integer rungs} \qquad \text{(Yang, bubble)}$$

The half-rung is not a free position: it is the antinode of the fundamental
mode of the terminal cell—the only mode with a single antinode at the
midpoint; $\sin(m\pi(u-n))$ with $m \ge 2$ puts antinodes at $n + k/m$.
A terminated sector—the lepton tower ending at $e$, the hadron tower at $\pi$,
confinement at $\Lambda_{\text{QCD}}$—leaves its lightest cell half-open: no
state exists beyond to continue the $\varphi$-spacing, so the state is the
fundamental of its cell and sits at the crossing $n \pm \tfrac{1}{2}$.
Interior stable states, sustained by the wake's self-launching
(`wake-geometry.md` §2(e)), are the bubble parity at integer rungs. The
catalog reading (pipeline §3): sector edges at 26.5 ($e$), 9.5 ($\tau$), 8.5
($b$), 95.5 ($\pi$), 91.5 ($p,n$), 102.5 ($d$), 94.5 ($\Lambda_{\text{QCD}}$),
mean |residual| 0.038 rungs; interior stable states at integer rungs ($\mu$
96.000, J/$\psi$ 89, $D$ 90, $\Sigma$ 91, $Z$ 82).

The quantization is silent on two things, and both are open: the absolute
placement of each cell (why the electron's cell is [26, 27] and not [25, 26])—
the empirical content of the ladder; and the frame choice—the muon is the dual
citizen, 96.000 on the Compton ladder and 15.39 on the Yukawa ladder. The
catalog statistics of §3 remain the honest baseline: the full 38-state scan
does not cluster at special points, and the identification of the sector edges
with the fundamental sine modes is Hypothesized, not Derived.

### 4.2 The residual: δn as local phase lag

Within a special-position class, the residual $\delta n$ encodes the phase lag between the wakes at the site. The probe (RO1, run 2026-08-03) measured the relation in the two-bubble standing pattern: the extremum sits at $x_{\max} = \varphi/2 - \psi/(4\pi)$, i.e.

$$\boxed{\delta n(\psi) = 0.060 - 0.204\,\psi \ \text{rungs} \qquad (\psi \text{ in radians, } f=1)}$$

around the coherent point, where $\psi$ is the relative phase between the two bubbles' wakes. Both coefficients are analytic, not fit: the coherent crossing sits at $u = 1 - \log_\varphi 2 = -0.4404$ (0.06 rungs above the naive half-rung), so the intercept is $A_0 = 1.5 - \log_\varphi 2 = 0.0596$; and the slope is the inverse of the self-similar phase advance, $B_0 = 1/\omega_0 = 1/(2\pi\varphi\ln\varphi) = 0.2044$ ($\omega_0 = 4.892$ rad/rung, `foundations/wake-geometry.md` §3b). The measured relation is the linearization of $u(x_{\max}(\psi)) + \tfrac12$ about the coherent crossing (`computations/pooled_zone_modes.py` §1). The catalog's crossing-state residuals then correspond to modest phase lags: the electron's $-0.03$ rungs on the Yukawa ladder maps to $\psi \approx 0.44$ rad (25°), the nucleons' $-0.04$ to $\psi \approx 0.49$ rad, the pion's $-0.08$ to $\psi \approx 0.69$ rad. Amplitude asymmetry alone does not move the extremum at $\psi = 0$—the $\varphi$-spacing geometry locks the crossing—while at finite $\psi$ it moves through the phase composition (probe table 3). The alignment–coherence correspondence (§1) turns sharpness into a coherence meter: the muon's 0.01% marks a near-coherent scale; the W, H, t residuals of ~10% mark strongly de-coherent scales.

### 4.3 The dressed-rung form (Speculative)

A minimal quantitative form: the observable is the dressed state of two adjacent rungs coupled by $V$; the offset is the mixing probability, $\delta n \to \tfrac{1}{2}$ as the inter-rung coupling dominates (boundary states) and $\delta n \to 0$ for isolated rungs. The per-sector coupling $V$ is what the PDE must supply; no independent $V$ exists yet, so this form is a placeholder for the PDE result, not a result.

## 5. The decisive tests (falsifiable)

**T1—PDE probe (primary).** Run 2026-08-03 (`two-fluid/run_rung_offset_probe.py`): two bubbles at $x = 0$ and $x = \varphi$ emit the wake pair; with $V = 0$ initial conditions the fields are exactly standing (d'Alembert, no dispersion), so the extremum of $|E_Y|$ is the antinode of the initial envelope, measured at times short enough that no wall influence has reached the window (influence arrives at $t = x + x_{\text{sp}}$; every panel measures inside it). Results: (a) at $\lambda = 0$, $\psi = 0$ the extremum sits at $u = -0.440$, exactly the analytic antinode, and the relative phase $\psi$ moves it continuously—$\delta n(\psi) = 0.060 - 0.204\,\psi$ rungs, PDE = analytic to $10^{-3}$ rungs at every scan point; (b) conversion does **not** move the extremum: null in the linear regime ($\lambda \le 0.1$, $t \le 2$) and null under the solver's nonlinear 'single' gate (Panel C: $\lambda \le 0.5$, $\langle 1-q\rangle$ up to 0.33, densities $m = 0.5$–2, amplitudes 0.16–0.64, $t \le 6$). The gate demonstrably sources harmonics of the wakes—the $(1-q)$ field carries power at the doubled wake wave number—but cannot rephase the crossing: the extremum stays pinned at $u = -0.440$, and the $\psi$-curve is unchanged under the gate. The offset $\delta n$ is set by the wake phase difference alone; local conversion dynamics, linear or gated, are not the dial. What sets $\psi$ physically is the open question; the closure-emission reading has been tested and is not supported (T4); (c) the amplitude-ratio scan at finite $\psi$ reproduces the analytic composition exactly ($f = 1.0, 0.8, 0.6$).

**RO2—catalog statistics.** Extend the scan (neutrino masses, future states). The mechanism predicts the sharp-placement count does not grow with $N$: the uniform baseline is the null, and a growing count would confirm clustering.

**T3—sector-edge prediction.** The next discovered lightest state of a new sector should land at a half-rung; interior states at integer rungs.

**T4—closure-phase connection (run 2026-08-03, null).** `experiments/rung_offset_closure/closure_phase_test.py`: if $\psi$ were the phase accumulated by a wake emitted at the last closure level ($\psi = \omega\,(n - c_{\text{last}}) \bmod 2\pi$, closure ladder {5, 13, 34, 89, 233, 610}), then $\delta n$ would track the distance from that closure. The 38-state catalog shows: no monotone relation ($\rho = +0.14$, $p = 0.41$ for $\delta n$; $\rho = +0.03$, $p = 0.86$ for $|\delta n|$); the zero-parameter self-similar phase advance $\omega_0 = 2\pi\varphi\ln\varphi = 4.89$ rad/rung gives mean residual 0.230 vs the 0.250 uniform baseline ($p = 0.21$); and a free-$\omega$ search, with the search accounted for against random catalogs, does not beat chance (best residual 0.188 vs null mean 0.182, $p = 0.73$). The closure-ladder hits themselves (J/ψ at 89, $26 = 2\times13$, $285 = 5\times57$) stand as catalog placements with the mechanism open; the wake-phase reading of $\delta n$ is not supported by the mass catalog.

**T5—full-catalog ψ map (run 2026-08-03, null).** `experiments/rung_offset_closure/catalog_psi_map.py` applies the mechanism to all 38 states: $\psi = (0.060 - \delta n)/0.204$ with $\Delta\psi$ from PDG errors. The correct null is not a uniform circle—the integer/half-integer special grid folds a uniform $\delta n$ into a triangular $\psi$ window $[-0.93, +1.52]$ rad with $R \approx 0.77$—so every test is measured against that baseline. Result: $R = 0.799$ ($p = 0.22$); free-$\omega$ phase advance $\omega = 0.003$ rad/rung, residual 0.201 vs 0.219 ± 0.033 ($p = 0.31$); named base angles $2\pi/\varphi^2$, $3\pi/10$, $2\pi/5$, $\pi/\varphi$, $2\pi\ln\varphi$, $2\pi/\varphi^3$, $2\pi/\varphi^4$ all consistent with chance ($p \ge 0.22$). The ψ map carries no hidden structure: the sharp placements' band $[0.13, 0.68]$ rad around $\psi^* = 0.294$ is the selection criterion in phase units, and the light-quark rows are scheme-unconstrained ($\Delta\psi \ge 0.88$ rad).

**T6—multi-rung wake superposition (run 2026-08-03, verified).** `two-fluid/run_rung_offset_probe_panel_d.py` extends the probe: bubbles at $-\varphi$ (one rung down), $\varphi$ (up one) and $\varphi^2$ (up two) emit the wake pair, and the crossing must respond to the total phasor sum $Z = f_m e^{i(\psi_m + 2\pi\varphi)} + 1 + f_1 e^{i(\psi_1 - 2\pi\varphi)} + f_2 e^{i(\psi_2 - 2\pi\varphi^2)}$ if the cumulative channel is open. PDE = analytic to $10^{-3}$ rungs at every scan point: the far-up wake moves the crossing with its own leverage ($-0.202$ rungs/rad at $f_2 = \varphi^{-1}$—indistinguishable from the near bubble's $-0.204$; $-0.125$ at $f_2 = \varphi^{-2}$), the down-rung wake enters the same sum, gated conversion still cannot rephase the multi-rung crossing, and the two-wake-at-once response deviates from the single-rung linear sum by only $-0.03$ to $-0.07$ rungs at $\psi \le 0.8$. The single-rung curve $\delta n(\psi)$ is the two-bubble truncation of a true field sum; superposition over rungs is exact in the standing idealization. What remains open is the source term: what each bubble emits.

**T7—cumulative structure in the catalog (run 2026-08-03, null).** `experiments/rung_offset_closure/cumulative_phase_test.py` asks whether the offset field carries the cumulative structure the superposition channel allows. (a) Variogram: the circular phase distance between states does not grow with rung separation (Spearman $\rho = +0.02$ vs $0.000 \pm 0.058$ null, $p = 0.34$; binned profile flat at $0.75$–$0.86$ rad)—no random-walk accumulation. (b) Self-consistent mean field with sources $D_m$ = catalog state density at integer rung $m$ (orthogonal to the fractional offsets being predicted): emission phase $\psi_m = \arg\sum_{m'\ne m} D_{m'}\varphi^{-|m-m'|} e^{i(\psi_{m'} + \omega_0(m'-m))}$; the two-sided $\omega_0 = 4.89$ variant does not converge (drift $1.0$) and gives $p = 0.26$; $\omega_0 = 0$ gives $p = 0.65$; the one-sided (wakes from below) variant gives $p = 0.037$, but the per-cell audit shows the predicted phases are a quantized set $\{0, +1, +2, +2.28\}$ with no structural correspondence to the observed profile (e.g., cell 80 predicts $+2.00$ against observed $-0.31$)—a multiple-test artifact among four variants, not a match. No cumulative signature is detectable with state-density sources; the superposition channel is open but the catalog does not yet speak.

## 6. Epistemic boundaries

- **Derived**: the envelope special positions (§2, probe-verified); the catalog numbers (§3); the $\delta n(\psi)$ phase-lag relation (§4.2, analytic + PDE to $10^{-3}$ rungs, with the exact $A_0$, $B_0$ forms); the multi-rung phasor-sum response (T6, PDE-verified to $10^{-3}$ rungs); the pool-cell quantization (§4.1)—the cell $[n, n+1]$ closes with nodes at the voids, and the two parities $\sin(\pi(u-n))$ / $\cos(\pi(u-n))$ put their antinodes at the half-rung / the integer rungs.
- **Hypothesized**: the alignment–coherence correspondence (§1); sector-edge selection at half-rungs (§4.1)—the identification of the catalog's sector edges with the fundamental sine modes, and the cell placements; the catalog mapping onto $\psi$ (§4.2); the open question of what sets $\psi$ at each rung (the gate branch, tested null 2026-08-03, is not the dial; the closure-emission reading, tested null, is not supported—§5 T4).
- **Speculative**: the dressed-rung form (§4.3); the per-sector frame choice (Yukawa vs Compton ladder); the source term of the multi-rung sum (state-density sources show no cumulative structure, T7).
- **Not supported**: any claim that the full mass catalog clusters at special points—the 38-state scan is uniform, and only the muon placement is individually improbable (≈0.8% over the catalog); likewise the full-catalog ψ map is structureless (T5), and no cumulative signature appears with state-density sources (T7).

## 7. References

- `foundations/wake-geometry.md` §1–3—wake pair, envelope, half-steps, mass-scan catalog
- `principles/de-resonance-principle.md`—why exact alignment is forbidden; correction posture
- `foundations/dimensionful-cascade.md` §6—wake wavelengths, sound-horizon half-step
- `foundations/deriving-remaining-gaps.md` §2—electron mass status (external, class **E**)
- `predictions/falsifiable-predictions.md` §5—predictions 43–45 (wake closure, checkerboard, closure ladder)
- `two-fluid/run_rung_offset_probe.py`—T1 probe: two-bubble standing pattern, $\delta n(\psi)$ measurement
- `computations/pooled_zone_modes.py`—pool-cell quantization: the two parities, antinode positions, catalog reading, the t/H phase-rung
- `experiments/rung_offset_closure/closure_phase_test.py`—T4: closure-phase connection, null result
- `experiments/rung_offset_closure/catalog_psi_map.py`—T5: full-catalog ψ map (CSV: `catalog_psi_map.csv`), null result
- `two-fluid/run_rung_offset_probe_panel_d.py`—T6: multi-rung phasor-sum superposition, verified
- `experiments/rung_offset_closure/cumulative_phase_test.py`—T7: variogram + self-consistent mean field, null result
