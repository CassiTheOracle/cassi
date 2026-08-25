# Why Observables Sit Between Rungs: The Two-Fluid Phase Mechanism for Fractional Cascade Offsets

## Status: Derived quantization, Hypothesized selection, Empirical catalog (μ/J/ψ placements Mapped—38-state scan, ledger)—August 2026

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
| Lepton tower, heaviest | τ | 9.5 (Yukawa ladder) | +1.2% (v0-pole frame; top-anchored +0.5%, MS-bar-top −4.8%) |
| Hadron tower, lightest | π | 95.5 | 3.9% |
| Confinement boundary | Λ_QCD | 94.5 | 2.1% |
| Baryon tower, lightest | p, n | 91.5 | 1.9–2.0% |
| Quark sector, lightest | d | 102.5 | 0.9% |

Interior stable states sit at integer rungs: μ (96.000), J/ψ (89), D (90), Σ (91), Z (82).

Caveats, stated plainly: the light-quark and Λ_QCD masses are scheme-dependent (MS-bar running masses at 2 GeV), and the u/d pair straddles its special points rather than sitting on them (u at 104.084, d at 102.481, spacing 1.60 rungs—not a special spacing). The electron's half-rung lives on the Yukawa ladder $n = \log_\varphi((v_0/\sqrt2)/m)$—the frame where its mass is generated—while its Compton-ladder placement (107.08, 3.9% off rung 107) is a near-miss rather than a hit. W, H, t and most of the catalog sit at no special point at all.

The void side of the electron's placement is the sharp one: in the lattice frame the electron is the sharpest void (half-integer $k$) reading in the catalog, $e = m_{102}/11.5$ (0.19%)—the $k = 11.5 = 23/2$ sub-lattice void at $n = 107.075$, inside its own Compton cell $[107, 108]$—and the up quark sits on the same void family three rungs up the cascade, $u = m_{99}/11.5$ (0.40%): the two lightest first-generation fermions share the void index. The Yukawa half-rung $n = 26.47 \approx 26.5$ (1.4%) is the same statement in the mass-generation frame. These are individual placements—the catalog is uniform against the same-density null (T9)—and the index $23/2$ carries no structural candidate of its own.

The mechanism applied to the whole catalog reads every residual as a phase lag: $\psi = (0.060 - \delta n)/0.204$, with $\Delta\psi$ from the PDG mass error. The map is statistically structureless (T5): the circular concentration $R = 0.799$ is what the uniform-frac baseline produces (0.774 ± 0.033, $p = 0.22$); a free-$\omega$ phase advance $\psi(n) = \psi_0 + \omega n$ leaves $\omega \approx 0.003$ rad/rung (residual 0.201 vs 0.219 ± 0.033, $p = 0.31$); and no named base angle—$2\pi/\varphi^2$, $3\pi/10$, $2\pi/5$, $\pi/\varphi$, $2\pi\ln\varphi$, $2\pi/\varphi^3$, $2\pi/\varphi^4$—fits better than chance ($p \ge 0.22$). The sharp placements are the states whose $\psi$ lies nearest the coherent crossing $\psi^* = A_0/B_0 = 0.294$ rad ($\delta n = 0$); their band $[0.13, 0.68]$ rad is the selection criterion in phase units, not an independent pattern. The light-quark rows carry scheme-scale $\Delta\psi$ (d: ±1.05 rad, u: ±2.31 rad), so their sharpness is scheme-bound: d's 0.9% holds only within the MS-bar choice. The map's full data table is `experiments/rung_offset_closure/catalog_psi_map.csv`.

The lattice frame (T9) re-expresses the envelope positions as a mass law: $m = m_j/k$ with $k$ a small integer (node) or half-integer (void) and $m_j = M_{\text{Pl}}/\varphi^j$ the rung mass. Against the same-density null the catalog is uniform (mean $s = 0.0147$ vs 0.0154 ± 0.0019, $p = 0.35$; 29/38 within 1% vs 27.2 ± 2.8); the sharpest individual lattice readings are $\mu = m_{96}$ (0.01%), $\Xi^* = m_{89}/2$ (0.13%), J/ψ $= m_{84}/11$ (0.14%), $e = m_{102}/11.5$ (0.19%).

## 4. The mechanism hypothesis

### 4.1 Selection: why sector edges sit at crossings (mode quantization)

The pool-cell quantization (`computations/pooled_zone_modes.py`) supplies the
wave-mechanical form of the boundary-state idea. The energy pool of a state is
the constructive-overlap cell of the rotating wake pair
(`foundations/wake-geometry.md` §2): the two wakes are the two phases of one
string motion, and their overlap—the pool—pulses at the beat period
$\ell_{n+1}/c$, so the state's standing wave must close on the cell bounded by
the envelope zeros (the voids, where the overlap vanishes). The probe standing
patterns that measure this parity are set up from structured initial
conditions (two-bubble / truncated-tower seeds with $V = 0$, d'Alembert-exact
standing waves); the canonical first-order solver does not raise them
spontaneously from smooth no-drive seeds (`two-fluid/run_bubble_ring_dynamic_probe.py`,
no rings in all four arms).

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
catalog statistics of §3 remain the measured baseline: the full 38-state scan
does not cluster at special points, and the identification of the sector edges
with the fundamental sine modes is Hypothesized, not Derived.

The phase-current identity pins the parity class (Derived-conditional on the
cell-closure structure). For the rotating doublet
$\Psi_0 = \sqrt{\rho}\cos\alpha$, $\Psi_1 = \sqrt{\rho}\sin\alpha$ with
$A = \sqrt{\rho}$ the envelope amplitude, the axial current is
$J_z = \rho\,\alpha' = A^2\pi$ per rung (the phase advances $\pi$ per rung
under the $P_\parallel = 2$ convention): a sine envelope gives the current
profile $(0, \pi, 0)$ at wall/half-rung/wall, a cosine envelope
$(\pi, 0, \pi)$. Checkerboard current continuity forces the **sine parity** on
void-bounded cells—the antinode, the maximum inter-scale flow, sits exactly
at the half-rung, matching the sector-edge placements of this section. The
selection of which cells are void-bounded (the sector termination) stays
Hypothesized.

### 4.2 The residual: δn as local phase lag

Within a special-position class, the residual $\delta n$ encodes the phase lag between the wakes at the site. The probe (RO1, run 2026-08-03) measured the relation in the two-bubble standing pattern: the extremum sits at $x_{\max} = \varphi/2 - \psi/(4\pi)$, i.e.

$$\boxed{\delta n(\psi) = 0.060 - 0.204\,\psi \ \text{rungs} \qquad (\psi \text{ in radians, } f=1)}$$

around the coherent point, where $\psi$ is the relative phase between the two bubbles' wakes. Both coefficients are analytic, not fit: the coherent crossing sits at $u = 1 - \log_\varphi 2 = -0.4404$ (0.06 rungs above the naive half-rung), so the intercept is $A_0 = 1.5 - \log_\varphi 2 = 0.0596$; and the slope is the inverse of the self-similar phase advance, $B_0 = 1/\omega_0 = 1/(2\pi\varphi\ln\varphi) = 0.2044$ ($\omega_0 = 4.892$ rad/rung, `foundations/wake-geometry.md` §3b). The measured relation is the linearization of $u(x_{\max}(\psi)) + \tfrac12$ about the coherent crossing (`computations/pooled_zone_modes.py` §1). The catalog's crossing-state residuals then correspond to modest phase lags: the electron's $-0.03$ rungs on the Yukawa ladder maps to $\psi \approx 0.44$ rad (25°), the nucleons' $-0.04$ to $\psi \approx 0.49$ rad, the pion's $-0.08$ to $\psi \approx 0.69$ rad. Amplitude asymmetry moves the crossing at any $\psi$ (probe Panel G): at
$\psi = 0$ the extremum sits at $u = -0.440$ for $f = 1$ and $-0.330$ for
$f = 0.8$; at $\psi = 0.4$ it moves 0.38 rungs across $f = 1.0$–$0.6$
(probe table 3). The $\delta n(\psi)$ linear relation is exact at fixed
$f$; the catalog's phase lags assume the equal-amplitude reading
($f = 1$). The alignment–coherence correspondence (§1) turns sharpness into a coherence meter: the muon's 0.01% marks a near-coherent scale; the W, H, t residuals of ~10% mark strongly de-coherent scales.

### 4.3 The dressed-rung form (Speculative)

A minimal quantitative form: the observable is the dressed state of two adjacent rungs coupled by $V$; the offset is the mixing probability, $\delta n \to \tfrac{1}{2}$ as the inter-rung coupling dominates (boundary states) and $\delta n \to 0$ for isolated rungs. The per-sector coupling $V$ is what the PDE must supply; no independent $V$ exists yet, so this form is a placeholder for the PDE result, not a result.

### 4.4 Channel splitting (Hypothesized)

The pool at the EW-breaking scale may split into $K = 3$ coherence channels. The t/H wake phases differ by $\Delta\psi = 1.627$ rad $= \omega_0/3$ (0.2%): the $2/3$-rung separation is one cell minus one channel ($n_H - n_t = 1 - \Delta\psi/\omega_0 = 1 - \tfrac13 = \tfrac23$). The third channel is empty—$\psi_3 = \psi_H + \omega_0/3 = +2.94$ rad implies frac 0.458, and no EW state sits there (Z 0.951, W 0.213, t 0.624, H 0.291). The K = 5 (Wu Xing) variant, $\omega_0/5 = 0.978$ rad per channel, is tested against the fifths grid: of 40 states (catalog + $v_0$ + GUT scale), 10 sit within 0.03 rungs of a fifth versus 12 expected uniformly—no clustering; the sharpest fifth placement is the low-energy K meson (0.004 rungs), and the GUT scale sits at 0.0302 from the 4/5 slot (borderline). The K = 5 reading is background traffic, not structure. The transition-zone
reading relocates the five-fold: the EW scale is interior to the universe
bubble (rung ~80 of 285), and the five-fold is the pole structure—the top
transition already carries it (the closure ladder starts at 5, the pentagon;
$285 = 5 \times 57$, the Cassi bubble on a five-arm closure boundary), and
the bottom transition (rung 0, where a new bubble starts down the cascade)
hosts the only transition-band probe: the GUT scale at $n = 14.77 =
14 + \tfrac45$ (for $M_{\text{GUT}} = 10^{16}$ GeV, $\log_\varphi(M_{\text{Pl}}/M_{\text{GUT}}) = 14.77$; the $2\times10^{16}$ GeV convention used elsewhere gives $n = 13.33$; resid 0.0302 rungs, 1.5% in scale—borderline; the GUT band
$10^{15.5}$–$10^{16.5}$ GeV spans rungs 12.4–17.2, so the $\tfrac45$ position
lies inside the uncertainty band). The interior fifths null is then the
expected reading, not a failed prediction; the five-fold remains a
transition structure with one borderline probe. The K = 3 reading has exactly one sharp datum (the t/H pair), and the coherent 3-bubble construction fails the probe (T10-F: the composition shifts the crossings, so the pair reads as independent cells, consistent with T4/T5). The channel-split idea survives only as the phase coincidence; the channels are not visible as multi-cell coherence.

## 5. The decisive tests (falsifiable)

**T1—PDE probe (primary).** Run 2026-08-03 (`two-fluid/run_rung_offset_probe.py`): two bubbles at $x = 0$ and $x = \varphi$ emit the wake pair; with $V = 0$ initial conditions the fields are exactly standing (d'Alembert, no dispersion), so the extremum of $|E_Y|$ is the antinode of the initial envelope, measured at times short enough that no wall influence has reached the window (influence arrives at $t = x + x_{\text{sp}}$; every panel measures inside it). Results: (a) at $\lambda = 0$, $\psi = 0$ the extremum sits at $u = -0.440$, exactly the analytic antinode, and the relative phase $\psi$ moves it continuously—$\delta n(\psi) = 0.060 - 0.204\,\psi$ rungs, PDE = analytic to $10^{-3}$ rungs at every scan point; (b) conversion does **not** move the extremum: null in the linear regime ($\lambda \le 0.1$, $t \le 2$) and null under the solver's nonlinear 'single' gate (Panel C: $\lambda \le 0.5$, $\langle 1-q\rangle$ up to 0.33, densities $m = 0.5$–2, amplitudes 0.16–0.64, $t \le 6$). The gate demonstrably sources harmonics of the wakes—the $(1-q)$ field carries power at the doubled wake wave number—but cannot rephase the crossing: the extremum stays pinned at $u = -0.440$, and the $\psi$-curve is unchanged under the gate. The offset $\delta n$ is set by the wake phase difference alone; local conversion dynamics, linear or gated, are not the dial. What sets $\psi$ physically is the open question; the closure-emission reading has been tested and is not supported (T4); (c) the amplitude-ratio scan at finite $\psi$ reproduces the analytic composition exactly ($f = 1.0, 0.8, 0.6$).

**RO2—catalog statistics.** Extend the scan (neutrino masses, future states). The mechanism predicts the sharp-placement count does not grow with $N$: the uniform baseline is the null, and a growing count would confirm clustering.

**T3—sector-edge prediction.** The next discovered lightest state of a new sector should land at a half-rung; interior states at integer rungs.

**T4—closure-phase connection (run 2026-08-03, null).** `experiments/rung_offset_closure/closure_phase_test.py`: if $\psi$ were the phase accumulated by a wake emitted at the last closure level ($\psi = \omega\,(n - c_{\text{last}}) \bmod 2\pi$, closure ladder {5, 13, 34, 89, 233, 610}), then $\delta n$ would track the distance from that closure. The 38-state catalog shows: no monotone relation ($\rho = +0.14$, $p = 0.41$ for $\delta n$; $\rho = +0.03$, $p = 0.86$ for $|\delta n|$); the zero-parameter self-similar phase advance $\omega_0 = 2\pi\varphi\ln\varphi = 4.89$ rad/rung gives mean residual 0.230 vs the 0.250 uniform baseline ($p = 0.21$); and a free-$\omega$ search, with the search accounted for against random catalogs, does not beat chance (best residual 0.188 vs null mean 0.182, $p = 0.73$). The closure-ladder hits themselves (J/ψ at 89, $26 = 2\times13$, $285 = 5\times57$) stand as catalog placements with the mechanism open; the wake-phase reading of $\delta n$ is not supported by the mass catalog.

**T5—full-catalog ψ map (run 2026-08-03, null).** `experiments/rung_offset_closure/catalog_psi_map.py` applies the mechanism to all 38 states: $\psi = (0.060 - \delta n)/0.204$ with $\Delta\psi$ from PDG errors. The correct null is not a uniform circle—the integer/half-integer special grid folds a uniform $\delta n$ into a triangular $\psi$ window $[-0.93, +1.52]$ rad with $R \approx 0.77$—so every test is measured against that baseline. Result: $R = 0.799$ ($p = 0.22$); free-$\omega$ phase advance $\omega = 0.003$ rad/rung, residual 0.201 vs 0.219 ± 0.033 ($p = 0.31$); named base angles $2\pi/\varphi^2$, $3\pi/10$, $2\pi/5$, $\pi/\varphi$, $2\pi\ln\varphi$, $2\pi/\varphi^3$, $2\pi/\varphi^4$ all consistent with chance ($p \ge 0.22$). The ψ map carries no hidden structure: the sharp placements' band $[0.13, 0.68]$ rad around $\psi^* = 0.294$ is the selection criterion in phase units, and the light-quark rows are scheme-unconstrained ($\Delta\psi \ge 0.88$ rad).

**T6—multi-rung wake superposition (run 2026-08-03, verified).** `two-fluid/run_rung_offset_probe_panel_d.py` extends the probe: bubbles at $-\varphi$ (one rung down), $\varphi$ (up one) and $\varphi^2$ (up two) emit the wake pair, and the crossing must respond to the total phasor sum $Z = f_m e^{i(\psi_m + 2\pi\varphi)} + 1 + f_1 e^{i(\psi_1 - 2\pi\varphi)} + f_2 e^{i(\psi_2 - 2\pi\varphi^2)}$ if the cumulative channel is open. PDE = analytic to $10^{-3}$ rungs at every scan point: the far-up wake moves the crossing with its own leverage ($-0.202$ rungs/rad at $f_2 = \varphi^{-1}$—indistinguishable from the near bubble's $-0.204$; $-0.125$ at $f_2 = \varphi^{-2}$), the down-rung wake enters the same sum, gated conversion still cannot rephase the multi-rung crossing, and the two-wake-at-once response deviates from the single-rung linear sum by only $-0.03$ to $-0.07$ rungs at $\psi \le 0.8$. The single-rung curve $\delta n(\psi)$ is the two-bubble truncation of a true field sum; superposition over rungs is exact in the standing idealization. What remains open is the source term: what each bubble emits.

**T7—cumulative structure in the catalog (run 2026-08-03, null).** `experiments/rung_offset_closure/cumulative_phase_test.py` asks whether the offset field carries the cumulative structure the superposition channel allows. (a) Variogram: the circular phase distance between states does not grow with rung separation (Spearman $\rho = +0.02$ vs $0.000 \pm 0.058$ null, $p = 0.34$; binned profile flat at $0.75$–$0.86$ rad)—no random-walk accumulation. (b) Self-consistent mean field with sources $D_m$ = catalog state density at integer rung $m$ (orthogonal to the fractional offsets being predicted): emission phase $\psi_m = \arg\sum_{m'\ne m} D_{m'}\varphi^{-|m-m'|} e^{i(\psi_{m'} + \omega_0(m'-m))}$; the two-sided $\omega_0 = 4.89$ variant does not converge (drift $1.0$) and gives $p = 0.26$; $\omega_0 = 0$ gives $p = 0.65$; the one-sided (wakes from below) variant gives $p = 0.037$, but the per-cell audit shows the predicted phases are a quantized set $\{0, +1, +2, +2.28\}$ with no structural correspondence to the observed profile (e.g., cell 80 predicts $+2.00$ against observed $-0.31$)—a multiple-test artifact among four variants, not a match. No cumulative signature is detectable with state-density sources; the superposition channel is open but the catalog does not yet speak.

**T8—closure-anchored emission phases in the phasor sum (run 2026-08-03, null).** `experiments/rung_offset_closure/closure_superposition_test.py`: the site's crossing responds to the total phasor sum (T6); if each bubble's emission phase is anchored by its last closure, $\psi_r = \omega_0(r - c(r)) \bmod 2\pi$ with the Fibonacci closures, the crossing positions are predicted with zero free parameters. Result: fixed $\omega_0 = 2\pi\varphi\ln\varphi$: mean mod-1 residual 0.230 vs 0.249 ± 0.024 null ($p = 0.21$); free-$\omega$ search-corrected: best $\omega = 5.09$, residual 0.196 vs null 0.193 ± 0.013 ($p = 0.58$); naive amplitudes $\varphi^{-|d|}$ ($p = 0.22$); closures extended with 26, 285 ($p = 0.18$); causal truncation to wakes from rungs $\le n{+}1$ (the crossing forms when the cell-top bubble condenses; wakes from above have not been emitted yet) gives $p = 0.18$ fixed / $p = 0.77$ free; truncation to $\le n$ gives $p = 0.35$ / $p = 0.90$. The sharp placements are not captured either way: J/ψ sits 0.24 rungs and the muon 0.28 rungs from the model's predicted crossings. Closure-anchored emission phases do not drive the sum; every tested source term for $\psi$—single-wake closure phase (T4), closure-anchored emissions in the superposition (T8), state density (T7), global phase rules and base angles (T5)—is null against the catalog, while the response law itself is exact (T6).

**T9—the lattice frame: masses as sub-multiples of rung masses (run 2026-08-03, null).** `experiments/rung_offset_closure/lattice_mass_test.py`: the bubble lattice (`foundations/bubble-lattice-fabric.md` §4.2) is the frame, so the envelope positions translate into a mass law: a condensation at node $k$ of rung $j$ sits at $n = j + \log_\varphi k$, i.e. $m = m_j/k$ with $k$ a small integer (nodes) or half-integer (voids) and $m_j = M_{\text{Pl}}/\varphi^j$ the rung mass. The position set $\{\log_\varphi k \bmod 1\}$ is dense (mean nearest distance $\sim 1/(4\,k_{\max})$), so every null must carry the same positions. Result: mean $s$ at $k_{\max} = 12$ (24 positions) is 0.0147 vs 0.0154 ± 0.0019 ($p = 0.35$); tail counts within 1% are 29/38 vs 27.2 ± 2.8 ($p = 0.33$)—a uniform catalog is as sharp as the real one against this ruler; the $k_{\max}$ scan (2–16) has best $p = 0.029$ at $k_{\max} = 4$, search-corrected $p = 0.23$. Every state receives a sub-2% reading (29/38 within 1%), which is the dense ruler's guarantee, not a signal. The individual sharpest lattice readings: $\mu = m_{96}$ (0.01%), $\Xi^* = m_{89}/2$ (0.13%), J/ψ $= m_{84}/11$ (0.14%), $e = m_{102}/11.5$ (0.19%), $\omega = m_{91}/1.5$ (0.20%), $B_s = m_{87}/1.5$ (0.24%), Δ $= m_{87}/6.5$ (0.28%), $\varphi = m_{89}/3$ (0.30%), Λ$_c = m_{87}/3.5$ (0.35%), $u = m_{99}/11.5$ (0.40%), $H = m_{79}/3$ (0.40%), $\tau = m_{87}/4.5$ (0.44%)—individual placements, within the null's reach. The lattice frame re-expresses the catalog without adding statistical weight: the mass law is a mass-frame restatement of the envelope positions, and the catalog remains uniform against it.

**T11—descent flow (run 2026-08-03, partial).** `two-fluid/run_rung_offset_probe_panel_e.py` tests the descent picture—gravity as gradient descent down the spiral, energy flowing down to form pools—as advective drag on the standing pattern, $\partial E/\partial t = V - u\,\partial E/\partial x$. A slow initial velocity does not drift the pattern (the wave equation has one speed $c = 1$; the IC $(E_0, -vE_0')$ splits into fast movers), so the drag must be modeled as advection. Results: (a) the wave dynamics resist the drag—the crossing at fixed $t$ moves at roughly half the drag speed, and the $|E_Y|^2$ energy deposit stays pinned at the standing crossing ($+0.060 \pm 0.01$ rungs) for $u \le 0.2$: the descent does not reposition the energy pool; (b) the gated conversion deposit (the mass-like pool) does respond, $\Delta\delta n \approx +1.6\,u$ rungs for $u \le 0.1$ (measured $+0.082$ at $u = 0.05$, $+0.159$ at $u = 0.1$; breakdown at $u = 0.2$); (c) the descent is therefore a genuine but second dial for the pool position—$\delta n = 0.060 - 0.204\,\psi + 1.6\,u$—degenerate with the phase from the catalog alone (one observable, two sources); separating them needs an independent $\psi$ measurement. Caveat: first-order upwind transport is dissipative; the pinning/shift picture is robust, the slope to $\pm 0.3$ rungs.

**T12—closure-crossing emission: the flow from the wake emission phase (run 2026-08-03, determined).** `two-fluid/run_rung_offset_probe_panel_f.py` measures the wake emission phase at the closure-crossing event—the crossing pinned at an integer rung, the coherent configuration $\psi = \psi^* = A_0/B_0 = 0.2941$ rad at $\delta n = 0$ (the catalog's closure states: J/ψ at rung 89, μ at rung 96). The emission phase is the lag of the crossing's oscillation relative to the source bubble (Fourier phase at $\omega = 2\pi$ over an integer number of periods). Results: (a) the standing event emits in phase ($\psi_{\text{emit}} = 0$ exactly, flux 0); (b) under descent the emission phase stays small—$\psi_{\text{emit}} \le 0.06$ rad at $u \le 0.2$ for the drifting pattern, $\le 0.11$ rad for the flow-compensated pool—with response $d\psi_{\text{emit}}/du \approx 0.5$–$1.0$ rad per unit $u$, fifteen times below the source-tracking rate $1/B_0 = 7.8$ at which the T11 degeneracy would survive: the reading is definite; (c) the direct flux transport through the pool reads $u_{\text{flux}} = \langle S\rangle/\langle\rho\rangle \approx u/2$—the wave regeneration pushes back at half the imposed drift (the crossing itself drifts at ~3.9 rungs per unit $u$ while the pool's conversion deposit shifts at 1.6 per T11: two distinct objects); (d) the catalog inversion $\delta n = 1.6\,u - B_0\,\psi_{\text{emit}}(u)$—the pool's source phase is the closure phase $\psi^*$ plus the emission lag of the wake that leaves the event—gives **$u(\text{J/ψ}) = -0.012$ to $-0.014$** (a 1.2% up-cascade flow: the pool sits 0.02 rungs above the Fibonacci closure, condensed just inside the closing cell) and **$u(\mu) = -0.0001$ to $+0.0015$** ($|u| \le 0.2\%$: the sharpest catalog state is the stillest pool, the coherent standing pool at its integer rung). The closure pools are near-static: the flow through a closure-crossing event is $\le 1.5\%$ of the wave speed, and the sharpest placements carry no descent. Caveat: the flow-compensated series leaves the first-cell copy for $u \gtrsim 0.1$ (the crossing wraps past the window edge), so the pinning column is valid only at $u \le 0.05$; the emission-phase and flux columns are measured at the fixed closure position and remain valid.

**T13—conversion-driven flux at the closure crossing (run 2026-08-03).** `two-fluid/run_rung_offset_probe_panel_g.py` tests the spiral-dynamics rung-advancement rate $dn/dt \approx (\lambda/2\pi)(1-q)$ (`foundations/spiral-dynamics.md` §2.1) as a local transport at the closure-crossing event ($\psi = \psi^*$, $u = 0$). The probe is flat—the buoyancy force $\mathbf{F} = \Pi\nabla\Phi$ of spiral-dynamics §3 is absent by construction—so only the conversion's own transport is visible. Results: conversion alone does move energy through the crossing, but outward, down the cascade (the expansion/unwinding direction), at $u_{\text{flux}} \approx 0.0001$–$0.001$ (0.01–0.1% of the wave speed)—an order of magnitude below the linearized rate $(\lambda/2\pi)(1-q)\,x^*\ln\varphi \approx 0.006$ at $\lambda = 0.3$—and it shifts the emission phase at the closure to negative values ($\psi_{\text{emit}} \approx -0.12$ to $-0.64$ rad, gated/linear), flipping the sign of the Panel F response at fixed $u$ (gate at $u = 0.05$: $-0.088$ vs $+0.048$ pure wave): the T12 flow reading is the pure-wave channel. Reading: the conversion term is the expansion mechanism (an outward trickle), not the gravitational descent; the inward flow the closure-crossing reading measures must come from the potential gradient, which the standing probes do not contain.

**T10—pooled-zone probe (run 2026-08-04).** `two-fluid/run_pooled_zone_probe.py` tests the mode quantization and the channel-split hypothesis. (E1) Truncated tower—bubbles at $m\varphi$, $m \ge 1$ only (no state below the sector boundary): the terminal-cell $|E_Y|$ extremum sits at $u \approx -1.15$ ($\delta n \approx -0.65$, converged by $M = 4$, PDE = analytic to $3\times10^{-4}$)—not at the log midpoint $-0.5$ nor the real midpoint $-0.44$. The free wakes do not produce the half-rung placement; the confinement the quantization requires is not supplied by the wake pattern, and the boundary conditions of the terminal cell are the open content of the selection claim. (F) The t/H two-cell pattern with the framework amplitudes $[1, 1, \varphi^{-1}]$: the third bubble's composition shifts the t-cell crossing by +0.17 rungs, so the catalog phases produce $(+0.29, -0.16)$ rather than $(+0.124, -0.209)$: the pair is not a single coherent three-bubble pattern—each cell's phase is independent (consistent with T4/T5). (G) Amplitude asymmetry: the crossing moves with $f$ at $\psi = 0$ ($f = 1$: $-0.440$; $f = 0.8$: $-0.330$; $f = 0.618$: $-0.229$) and strongly at $\psi \ne 0$ (probe table 3: 0.38 rungs across $f = 1.0$–$0.6$ at $\psi = 0.4$): the crossing responds to both phase and amplitude, and the $\delta n(\psi)$ relation is exact at fixed $f$ only.

## 6. Epistemic boundaries

- **Derived**: the envelope special positions (§2, probe-verified); the catalog numbers (§3); the $\delta n(\psi)$ phase-lag relation (§4.2, analytic + PDE to $10^{-3}$ rungs, with the exact $A_0$, $B_0$ forms); the crossing's response to amplitude asymmetry (§4.2, $x_{\max}(f,\psi)$ analytic + PDE, T10-G); the multi-rung phasor-sum response (T6, PDE-verified to $10^{-3}$ rungs); the pool-cell quantization (§4.1)—the cell $[n, n+1]$ closes with nodes at the voids, and the two parities $\sin(\pi(u-n))$ / $\cos(\pi(u-n))$ put their antinodes at the half-rung / the integer rungs.
- **Hypothesized**: the alignment–coherence correspondence (§1); sector-edge selection at half-rungs (§4.1)—the identification of the catalog's sector edges with the fundamental sine modes, and the cell placements (the truncated-tower probe, T10-E1, does not produce the half-rung from the free wakes: the terminal-cell boundary conditions are the open content); the catalog mapping onto $\psi$ (§4.2); the lattice sub-multiple mass law $m = m_j/k$ (T9—the mass-frame translation of the envelope positions; the catalog is uniform against the same-density null, so the law's weight rests on individual placements); the descent dial $\Delta\delta n \approx +1.6\,u$ (T11—the mass-like pool responds to the advective flow while the energy pool stays pinned; degenerate with $\psi$ from the catalog alone, resolved at the closure rungs by T12's emission-phase reading: $u(\text{J/ψ}) \approx -0.013$, $u(\mu) \approx 0$, flows $\le 1.5\%$ of the wave speed); the conversion term alone transports energy outward at $\le 0.1\%$ of the wave speed—the unwinding direction, not the descent, which requires the potential gradient (T13); the channel-split reading of the t/H pair (§4.4—the K = 3 phase advance matches to 0.2% but the coherent three-bubble pattern fails T10-F, and K = 5 has no statistical footprint); the open question of what sets $\psi$ at each rung (the gate branch, tested null 2026-08-03, is not the dial; the closure-emission reading, tested null, is not supported—§5 T4).
- **Speculative**: the dressed-rung form (§4.3); the per-sector frame choice (Yukawa vs Compton ladder); the source term of the multi-rung sum (state-density sources show no cumulative structure, T7).
- **Not supported**: any claim that the full mass catalog clusters at special points—the 38-state scan is uniform, and only the muon placement is individually improbable (≈0.8% over the catalog); likewise the full-catalog ψ map is structureless (T5), no cumulative signature appears with state-density sources (T7), closure-anchored emission phases do not drive the phasor sum (T8), and the lattice frame's sub-multiple law adds no clustering beyond the same-density null (T9).

## 7. The Density-Angle Relaxation Bound and the Rung Map

The winding rate of `foundations/cassi-first-principles.md` §2.6 supplies a
parameter-free ceiling on the density-plane angle accumulated by the canonical
conversion. Rung identification is a separate coordinate question. The
canonical fields are densities, $E_Y = \Psi_0^2$ and $E_I = \Psi_1^2$, with
density-plane angle
$\theta_d = \mathrm{atan2}(E_I, E_Y)$. This is distinct from the amplitude
phase $\theta_\Psi = \mathrm{atan2}(\Psi_1,\Psi_0)$. The Stokes double angle
is
$$\Theta_S = \mathrm{atan2}(2\Psi_0\Psi_1, E_Y - E_I)
= 2\theta_\Psi \pmod{2\pi}.$$
The conversion block is rank-one relaxation with eigenvalues $0$ and
$-\lambda(1-q)(1+\varphi)$; its generator therefore differs from an
$SO(2)$ rotation generator. Its exact density-angle rate is set by the local
imbalance $\varepsilon = E_Y - \varphi E_I$:

$$\frac{d\theta_d}{dt} = \lambda(1-q)\,\frac{\rho\,\varepsilon}{E_Y^2 + E_I^2},
\qquad \frac{d\varepsilon}{dt} = -\lambda(1+\varphi)(1-q)\,\varepsilon,
\qquad \frac{d\rho}{dt} = 0$$

with $\rho = E_Y + E_I$ conserved and
$q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$. A state that forms off
the $\varphi$-line ($\varepsilon_0 \neq 0$) changes its density-plane angle
while it relaxes, and because the conversion rate $\lambda$ and the gate
$(1-q)$ cancel in the angle, that accumulation is a function of the
formation imbalance alone—parameter-free, independent of $\lambda$ and of the
gate shape. The rate law is measured in the committed solver
(`two-fluid/run_winding_rate_probe.py`): four arms, all four matching the
formula to per-checkpoint relative error $\le 2.2\times10^{-3}$ with 100%
sign agreement.

The spatial diagnostics use a separate current identity. At amplitude level,
the foundational current is
$$J_\Psi = \Psi_0\nabla\Psi_1-\Psi_1\nabla\Psi_0
= \rho\nabla\theta_\Psi.$$
For the positive-root lift, the density-plane diagnostic is
$$J_d = E_Y\nabla E_I-E_I\nabla E_Y
=(E_Y^2+E_I^2)\nabla\theta_d
=2\sqrt{E_YE_I}\,J_\Psi.$$
These currents have different units, so $J_d$ cannot validate $J_\Psi$
without the conversion factor. A spatial current requires a named projection;
the projected quantity supplies no inter-rung transport interpretation without
a constitutive map. The axial profiles recorded by the probes are such named
spatial projections.

**The boxed identity.** The exact density-angle accumulation while a state
relaxes from $\varepsilon_0$ to the $\varphi$-line is

$$\boxed{\Delta\theta_d = \mathrm{atan}\!\left(\frac{1}{\varphi}\right)
- \mathrm{atan}\!\left(\frac{\rho-\varepsilon_0}{\rho\varphi+\varepsilon_0}
\right), \qquad \delta n_{\mathrm{map}} \equiv
\frac{\Delta\theta_d}{2\pi}}$$

The operation $\delta n_{\mathrm{map}} = \Delta\theta_d/(2\pi)$ is a
Hypothesized coordinate map. It supplies a comparison coordinate for a
cascade rung; the PDE result is the density-angle accumulation
$\Delta\theta_d$. The extremes are at the Yang limit
$\varepsilon_0 \to \rho$ ($+\mathrm{atan}(\varphi^{-1}) \approx 0.554$ rad)
and the Yin limit $\varepsilon_0 \to -\rho\varphi$
($-\mathrm{atan}(\varphi) \approx -1.017$ rad). In the map's rung units,

$$\boxed{|\delta n_{\mathrm{map}}| \le \frac{\mathrm{atan}(\varphi)}{2\pi}
\approx 0.162 \ \text{rungs}}$$

and for small formation imbalances the integral reduces to

$$\Delta\theta_d \approx \frac{\rho\,\varepsilon_0}{(1+\varphi)
\left(E_Y^2 + E_I^2\right)}.$$

The rate law, exact integral, and angular relaxation bound are Derived
density-angle results. The division by $2\pi$ is a Hypothesized coordinate
map, so it supplies a comparison between an angular relaxation result and a
rung label rather than a PDE derivation of that label.

Under this map, relaxation can produce only
$|\delta n_{\mathrm{map}}| \le 0.162$ rungs. Reproducing a particular catalog
offset inside that mapped interval requires the state's formation imbalance
$\varepsilon_0$, a free input unless something structural fixes it. A
half-rung comparison is
$\delta n_{\mathrm{map}} = \tfrac{1}{2} \Longleftrightarrow
\Delta\theta_d = \pi$, which lies about three times beyond the relaxation
bound. The parity mechanism of §4.1 supplies a Hypothesized interpretation for
such a half-step; the map and the angular relaxation result do not promote the
catalog placement to Derived status.

**The classification.** In the table, $\delta n$ denotes the catalog's
measured placement offset. The primordial comparison records
$\delta n_{\mathrm{map}}$ explicitly:

| Row | Measured placement | $\delta n$ | Class | Mechanism | Tier |
|---|---|---|---|---|---|
| proton (p, n) | $n = 91.46$, 0.038 rungs from 91.5 | $+0.46$ | half-step | parity, $P_\parallel = 2$ (§4.1) | Mapped placement; Hypothesized parity reading (0.46 > 0.162 map bound) |
| muon | 96.000 | 0.000 | zero-winding closure | $\varepsilon_0 = 0$: no accumulated density angle | Mapped (reading; $\varepsilon_0 = 0$ has no structural pin) |
| J/ψ | 88.98 | $-0.02$ | within the relaxation bound | per-object formation $\varepsilon_0$ (free fit) | Mapped |
| $m_e$ | 26.5 (Yukawa ladder) | $+0.5$ | half-step | parity (pool-cell fundamental, §4.1) | Mapped placement (fit, `foundations/deriving-remaining-gaps.md` §2); Hypothesized parity reading |
| BAO | 284.5 | $+0.5$ | half-step | parity | Mapped placement; Hypothesized parity reading (exceeds map bound $\sim 3\times$); placement per `foundations/dimensionful-cascade.md` §6 |
| $\Omega_{\text{DM}}/\Omega_b$ | 5.39 vs $\varphi^3 = 4.24$ | $+0.5$ | half-rung offset | none claimed | **Observation**—$5.39 \approx \varphi^{3.5} = 5.388$ (0.03%), not a registered prediction |
| primordial $r_0$ | $r_0 = 0.0472 \Rightarrow \Delta\theta_d = -0.970$ rad | $\delta n_{\mathrm{map}} \approx -0.154$ | relaxation (95% of the Yin bound) | winding, parameter-free | Derived density-angle result; Hypothesized map—null comparison |

Under the Hypothesized map, the half-step rows (proton, $m_e$, BAO) lie
beyond the Derived relaxation bound: a catalog $\delta n = 0.5$ would have
the mapped counterpart $\delta n_{\mathrm{map}} = 0.5$, requiring
$\Delta\theta_d = \pi$, about three times the maximum relaxation can
accumulate. Their parity reading remains Hypothesized, while the catalog
placements remain empirical or Mapped. The sub-bound rows (muon, J/ψ) are
available for comparison with the winding channel, and their reconstruction
requires a formation imbalance.

**Conditions for a stronger claim.** A sub-bound row would have a Derived
density-angle prediction when its formation imbalance $\varepsilon_0$ is
structurally determined rather than fitted. A Derived rung-placement claim
also requires an independently derived coordinate map; the present
$\delta n_{\mathrm{map}}$ operation is Hypothesized. Two structural candidates
exist: the pentagon gap $g = 1 - \varphi^{-5}$
(`foundations/wu-xing-derivation.md` §5.1), the derived fraction of the
primordial Yang–Yin imbalance converted in one pentagon cycle, and the
wake/golden-angle closure geometry of `foundations/wake-geometry.md` §3. What
the existing claims already say about the two sharp sub-bound rows: this
document's §4.1 reads the muon's integer rung as the interior-stable-state
class (bubble parity), and the closure-ladder test Y3 of
`foundations/wake-geometry.md` §3(e) lists the muon at 96.000 (0.01%) as a
rung-96 hit and the J/ψ at 88.98 (1.0% off the closure level 89, $F_{11}$)
with the mechanism open. The zero-winding reading ties to exactly this: the
muon's placement is the coherent reading $\varepsilon_0 = 0$—a state forming
on the $\varphi$-line winds nothing and lands exactly on its rung. That is
consistent with the integer-rung class and the closure hit, while
$\varepsilon_0 = 0$ is read from the datum rather than fixed by a structural
pin, so the row stays Mapped. The J/ψ's $-0.02$ is inside the bound, yet
reconstructing it requires a per-object formation $\varepsilon_0$—a free fit:
Mapped. A gap- or closure-anchored $\varepsilon_0$ (for example a formation
imbalance set by $g$ at the state's birth rung) would supply a Derived
density-angle prediction; the placement would still require the coordinate
map to reach Derived status.

**Primordial comparison (null).** The framework's derived initial condition is
strongly Yin: the primordial ratio
$r_0 = \varphi^{-5}/(2 - \varphi^{-5}) \approx 0.0472$ ($E_Y/E_I$, the Wu Xing
gap's ratio, `foundations/wu-xing-derivation.md` §5.2), Yin-dominated by
$\sim 21:1$. Relaxing from that imbalance gives

$$\Delta\theta_d = -0.970 \ \text{rad}
\quad\Longrightarrow\quad \delta n_{\mathrm{map}} \approx -0.154 \ \text{rungs},$$

95% of the Yin bound ($-1.017$ rad), with zero free parameters. The
$\Delta\theta_d$ value is the Derived density-angle result; its mapped
coordinate is Hypothesized. No cataloged row sits at
$\delta n \approx -0.154$: the primordial comparison is null. The universal
primordial relaxation contributes at most $\pm 0.162$ mapped rungs on top of
per-object formation imbalances and parity positions, and the primordial
imbalance leaves no imprint on the mass catalog. The $\varphi^3$ row of
`predictions/falsifiable-predictions.md` §3 keeps its 21% open tension; the
$\varphi^{3.5}$ reading is an observation about that tension, not a framework
prediction.

## 8. References

- `foundations/wake-geometry.md` §1–3—wake pair, envelope, half-steps, mass-scan catalog
- `foundations/cassi-first-principles.md` §2.6—the winding rate: density-plane rotation, exact relaxation-winding identity, $\pm 0.162$-rung bound
- `principles/de-resonance-principle.md`—why exact alignment is forbidden; correction posture
- `foundations/dimensionful-cascade.md` §6—wake wavelengths, sound-horizon half-step
- `foundations/deriving-remaining-gaps.md` §2—electron mass status (external, class **E**)
- `predictions/falsifiable-predictions.md` §3—$\Omega_{\text{DM}}/\Omega_b$ row ($\varphi^3$ vs observed 5.39, 21% open tension); §5—predictions 43–45 (wake closure, checkerboard, closure ladder)
- `two-fluid/run_rung_offset_probe.py`—T1 probe: two-bubble standing pattern, $\delta n(\psi)$ measurement
- `two-fluid/run_winding_rate_probe.py`—winding-rate probe: four homogeneous arms verify the rate law to $2.2\times10^{-3}$
- `two-fluid/run_pooled_zone_probe.py`—T10: truncated tower, t/H two-cell pattern, channel-split cases, amplitude-asymmetry check
- `computations/pooled_zone_modes.py`—pool-cell quantization: the two parities, antinode positions, catalog reading, the t/H phase-rung
- `experiments/rung_offset_closure/closure_phase_test.py`—T4: closure-phase connection, null result
- `experiments/rung_offset_closure/catalog_psi_map.py`—T5: full-catalog ψ map (CSV: `catalog_psi_map.csv`), null result
- `two-fluid/run_rung_offset_probe_panel_d.py`—T6: multi-rung phasor-sum superposition, verified
- `two-fluid/run_rung_offset_probe_panel_e.py`—T11: descent flow (advective drag), pool pinning + conversion shift
- `two-fluid/run_rung_offset_probe_panel_f.py`—T12: closure-crossing emission phase, flow determination at the closure rungs
- `two-fluid/run_rung_offset_probe_panel_g.py`—T13: conversion-driven flux at the closure crossing, outward unwinding trickle
- `experiments/rung_offset_closure/cumulative_phase_test.py`—T7: variogram + self-consistent mean field, null result
- `experiments/rung_offset_closure/closure_superposition_test.py`—T8: closure-anchored emission phases in the phasor sum, null result
- `experiments/rung_offset_closure/lattice_mass_test.py`—T9: lattice-frame masses $m = m_j/k$, null against the same-density null
