# Wake Geometry: How the Waveform Closes Each Rung

## Status: Derived wake geometry (anchors selected by de-resonance + composite closure; mechanical emission step open), Hypothesized closure imprint—August 2026

## Abstract

The primordial string's waveform is assigned a Yang/Yin wake pair: a Yin wake at $\Lambda_I^{(n)} = \ell_n/\varphi$ and a Yang wake at $\Lambda_Y = \varphi\,\Lambda_I = \ell_n$. The composite period closes the next cascade rung ($\Lambda_Y + \Lambda_I = \ell_{n+1}$). For supplied adjacent-rung carriers, the exact beat envelope has alternating demodulated sign at successive antinodes and destructive nodes between them. This is a conditional phase template for the bubbles and voids of the staggered checkerboard; the conversion from wave nodes to physical condensation remains open. Ordinary radial beats have additive spacing, and the live second-order wave law reaches the exact $\varphi$ wavenumber ratio only under a supplied drive frequency. The golden-angle phyllotaxis closure ladder (5, 13, 34, 89, 233, 610, …) is the geometry of bubble closure, with a Hypothesized imprint on the activated rungs. The cosmic depth is not a constant: 292 is the epoch-dependent horizon rung, not a cascade boundary; the derivable quantity is the asymptotic horizon $N_\infty \approx 294.2$ under the verified Yang-fraction-weighted coupling.

## 1. The waveform and its wavelength (Derived)

The wake pair that the expanding string drags through the two-fluid condensate has two wavelengths, and their sum is the wavelength of the next rung—the waveform closes each cascade step by construction.

**(a) The anchors.** The wake pair is the adjacent-rung pair: the string's motion at rung $n$ carries the rung scale as its Yang wake and leaves the previous rung's scale as its Yin wake, and the $1/\varphi$ ratio between them is the cascade's own step, not a fitted number.

The Yang wake is the condensation scale itself—the rung the string occupies:

$$\Lambda_Y = \ell_n$$

(`foundations/bubble-lattice-fabric.md` §1.3). The Yin wake sits one rung below, $\Lambda_I^{(n)} = \ell_{n-1} = \ell_n/\varphi$ (117.9 Mpc at rung 285, `foundations/dimensionful-cascade.md` §6). Two framework principles select that placement, and both are consequences of the two-fluid dynamics:

1. **De-resonance forbids a rational sub-rung scale.** A sub-rung wavelength at a rational fraction of $\ell_n$ (half, third, $\ldots$) would phase-lock the wake pair at periodic crests and concentrate energy at a single scale—the resonance collapse the $\varphi$-attractor exists to avoid (`principles/de-resonance-principle.md` §1). The sub-rung scale must stand in an irrational ratio to the rung, and the cascade's own sub-rung positions $\ell_n/\varphi^k$, $k \ge 1$, are the de-resonant candidates.

2. **Composite closure fixes $k = 1$.** The wake pair's sum is the next rung—the framework's verified composite closure (P43, `two-fluid/run_wake_structural_probes.py`). A pair at $(\ell_n,\ \ell_n/\varphi^k)$ closes only for $k = 1$:

$$\ell_n\left(1 + \varphi^{-k}\right) = \ell_{n+1} = \ell_n\,\varphi \iff \varphi^{-k} = \varphi - 1 = \varphi^{-1} \iff k = 1$$

$$\boxed{\Lambda_I^{(n)} = \ell_{n-1} = \frac{\ell_n}{\varphi}}$$

The $1/\varphi$ is the inter-rung ratio $\ell_{n-1}/\ell_n = \varphi^{-1}$ of the ladder itself, and the anchors are the unique de-resonant placement that closes the rung. Nesting: the Yin wake of rung $n$ is the Yang wake of rung $n-1$ (`cosmology/desi-lattice-averaging.md` §2), so the pair is the adjacent-rung pair and the condensation field $C = \cos(2\pi x/\Lambda_Y)\cos(2\pi y/\Lambda_I)$ is the interference product of two adjacent rungs. The two wakes are the two phases of one string motion: one period at the rung wavelength, one at the sub-rung wavelength.
**Auxiliary wave-model boundary.** The $2\lambda(1-q)$ term in the
second-order dispersion below belongs to the auxiliary asymmetric
second-order wave model implemented in
`computations/wake_anchor_and_suppression.py`. It is not the canonical
first-order density PDE. The canonical conversion block has relaxation
eigenvalue $-\lambda(1+\varphi)(1-q)$ and supplies no oscillatory dispersion
without a separately specified inertial wave closure.

For that auxiliary model, a single-frequency emission from the auxiliary
second-order wave surrogate excites both modes at the same frequency $\omega$;
the emitted wavelength ratio is

$$
\Lambda_\varepsilon =
\frac{\Lambda_Y}{\sqrt{1-2\lambda(1-q)/\omega^2}}
\approx 1.003\,\Lambda_Y \quad (\lambda=0.1)
$$

a 0.25% correction, not a factor $\varphi$. The beat period of the pair,
$2\pi/(k_I-k_Y)=\varphi\ell_n=\ell_{n+1}$ (§2), is the envelope, not the
Yin wavelength ($2\pi/k_I=\ell_n/\varphi$), which is an identity once
$k_I=\varphi k_Y$ is given. Analytic and auxiliary-model 1D probe results
are recorded in `computations/wake_anchor_and_suppression.py` §A. The
mechanical step—how the finite-amplitude, gate-modulated string emits tones
at exactly $\ell_n$ and $\ell_{n-1}$—is open; the ratio is carried by the
selection above, not by the canonical first-order PDE or its relaxation
eigenvalue.

$$
\boxed{\text{Inputs: (i) the cascade ladder } \ell_n = \ell_{\mathrm{Pl}}\varphi^n \text{ (postulate); (ii) the de-resonance principle (irrational sub-rung ratios; itself derived from the wave-physics resonance argument); (iii) the composite closure } \Lambda_Y + \Lambda_I = \ell_{n+1} \text{ (PDE-verified, P43). Tier: Derived conditional on (i)--(iii); the mechanical emission step is open.}}
$$

**(b) The composite closes the rung.** The wake pair's sum is the next rung, by the identity $1 + 1/\varphi = \varphi$:

$$\boxed{\Lambda_Y + \Lambda_I = \ell_n\left(1+\frac{1}{\varphi}\right) = \ell_n\,\varphi = \ell_{n+1}}$$

Verified at rung 285: $191 + 118 = 309$ Mpc $= \ell_{286}$. In wake units
the composite is $\ell_{n+1}/\Lambda_Y = \varphi$ and $\ell_{n+1}/\Lambda_I =
\varphi^2$—the latter is the pitch-tangent identity
$\gamma/\Omega_S = \ell_{n+1}/\Lambda_I$ of `foundations/spiral-dynamics.md`
§2.2 (prediction 50, `predictions/falsifiable-predictions.md` §5).

**(c) The geometric mean sits at the half-step.** The waveform's midpoint,

$$\sqrt{\ell_n\,\ell_{n-1}} = \ell_{n-0.5},$$

is where the measured sound horizon lives: $r_d \leftrightarrow n = 284.46$, documented in `foundations/dimensionful-cascade.md` §6. The wake pair brackets the sound-horizon half-step symmetrically—one period below it at $\ell_{n-1}$, one period above it at $\ell_n$.

## 2. Where the phase wakes meet (Derived)

Given the supplied adjacent-rung carriers, their beat envelope carries a phase-sensitive structural template from one rung to the next. The identity does not supply the carriers or turn its antinodes into condensed matter.

**(a) The interference identity.** Superposing the Yang and Yin periods,

$$\cos\!\left(\frac{2\pi x}{\ell_n}\right) + \cos\!\left(\frac{2\pi\varphi x}{\ell_n}\right) = 2\cos\!\left(\frac{\pi(1+\varphi)x}{\ell_n}\right)\cos\!\left(\frac{\pi(\varphi-1)x}{\ell_n}\right).$$

**(b) Exact phase-lock is impossible.** A common crest requires $x = a\,\ell_n = b\,\ell_n/\varphi$ with integers $a, b$, i.e. $a = b/\varphi$. Since $\varphi$ is irrational, the only integer solution is $a = b = 0$. The de-resonance principle is built into the wave structure itself: the wakes can never resonate with each other, at any point, at any rung.

**(c) The beat envelope.** The slow factor in the identity has period $\varphi\,\ell_n$ because $1/(\varphi-1) = \varphi$:

$$\boxed{\text{Envelope period } \varphi\,\ell_n = \ell_{n+1}:\quad \text{peaks at } x = m\,\ell_{n+1},\ \text{zeros at } x = \left(m+\tfrac{1}{2}\right)\ell_{n+1}}$$

Envelope antinodes are constructive and envelope nodes are destructive. Under the bubble-condensation mapping, they mark candidate bubble and void sites. After carrier demodulation, successive antinodes have signs $(-1)^m$: adjacent layers are anti-correlated and next-nearest layers are correlated. Equal carrier amplitudes give exact nodes; for amplitudes $A_Y,A_I$, the gap contrast is $2A_YA_I/(A_Y^2+A_I^2)$.

**(d) The staggered checkerboard template.** This derives the placement and phase parity of the staggered checkerboard of `foundations/bubble-edge-geometry.md` from supplied adjacent-rung carriers: candidate bubbles at $\ell_{n+1}$ spacing and candidate voids at the half-rungs. The identity contains no coupling magnitude or condensation law.

**(e) The identity does not self-propagate.** A supplied wake pair at rung $n$ has antinodes at the next-rung spacing. A separate emission or constitutive law must launch the carriers and convert their interference profile into the physical state at rung $n+1$.

**(f) The live second-order wave branch has a conditional realization.** In
the default `ham_completion = 0` CassiCosmos wave equation, the channel
variables

$$
\rho=E_Y+E_I,\qquad \epsilon=E_Y-\varphi E_I
$$

obey

$$
\ddot\rho=c^2\nabla^2\rho+S_\rho,
\qquad
\ddot\epsilon=c^2\nabla^2\epsilon-\varphi^2\omega_{0,\mathrm{wave}}^2\epsilon+S_\epsilon.
$$

The imbalance channel has propagation threshold

$$
\Omega_g=\varphi\omega_{0,\mathrm{wave}}.
$$

For harmonic drive above threshold,

$$
k_\rho=\frac{\Omega}{c},
\qquad
k_\epsilon=\frac{\sqrt{\Omega^2-\varphi^2\omega_{0,\mathrm{wave}}^2}}{c}.
$$

Their ratio equals $\varphi$ only at

$$
\boxed{\Omega_*=\varphi^{3/2}\omega_{0,\mathrm{wave}}}.
$$

The independent frequency-domain closure measures sub-gap attenuation
$3.067\times10^{-6}$, tuned ratio $1.618096626$, and generic-frequency ratio
$1.311855471$. Valid time-domain propagating fits agree within
$1.319\times10^{-4}$ and form additively spaced, phase-staggered layers. Both
time-domain sub-gap receipts remain `INCONCLUSIVE` because turn-on transients
contaminate their finite lock-in windows; the closure does not relabel them.
The live source path has no harmonic selector for $\Omega_*$. Uniform phase
staggering is gauge-equivalent to a gapless chain, while declared
coupling-magnitude modulation opens the tested gap. The full evidence and
protocol audit are in
`field-experience/phase-staggered-scale-gap-report.md`.

## 3. Closure levels of the spiral (Derived geometry, Hypothesized imprint)

Bubble closure is not a single event but a ladder of ever-tighter returns of the golden-angle spiral, and the ladder's rungs are the Fibonacci numbers.

**(a) The five arms.** The five-arm spiral at the bubble poles follows from golden-angle phyllotaxis, $2\pi/\varphi^2 = 137.5°$ (`foundations/spin-fibonacci-spiral.md` §1). The five arms are where the pentagon's vertex wakes align.

**(b) The closure ladder.** The convergents of $1/\varphi^2$ are all Fibonacci. After $k$ seeds the pattern returns to within: 5 → 32.5°, 13 → 12.4°, 34 → 4.7°, 89 → 1.8°, 233 → 0.7°, 610 → 0.3°—and it never closes exactly, because $1/\varphi^2$ is irrational. Exact closure would be resonance; de-resonance again forbids it.

$$\boxed{\text{Closure levels: } 5,\, 13,\, 34,\, 89,\, 233,\, 610,\, \ldots}$$

The bubble closes at 5 levels—the pentagon, ≈ 2 turns—and self-replicates to seed-width at 13.

**The seed arm width is determined** (`computations/seed_arm_width.py`). The seed sits at the bubble's birth scale—rung 0, $\ell_{\text{Pl}}$, for the universe bubble—and the five arms there have (a) cross-width $\ell_{\text{Pl}}/\varphi \approx 1.0\times10^{-35}$ m, the arm being the condensation line of the Yin wake ($\Lambda_I = r/\varphi$), and (b) arc spacing $2\pi\ell_{\text{Pl}}/5 \approx 2.0\times10^{-35}$ m, the five arms tiling the azimuth. The ratio $(2\pi/5)\varphi = 2.03 \approx 2$: the arms sit two wake-widths apart—arm + void, the staggered checkerboard in azimuth ($\pi\varphi = 5.083$ vs 5, 1.7%—the framework's near-miss scale). The arc spacing sits $\log_\varphi(2\pi/5) = 0.475$ rungs below Planck, 1.3% from the first half-rung below the cascade bottom—the mirror cascade's first half-step. "Self-replicates to seed-width at 13" is the first step of a ladder-wide invariance: the angular structure returns to the seed-width at every closure level with the Fibonacci-ratio precision ($13/5 = 2.60$ vs $\varphi^2 = 2.618$: 0.7%; $34/13$: 0.1%; $89/34$: 0.01%). At the top of the bubble the same structure holds: the five arms' arc width at rung 285 is $2\pi\ell_{285}/5 = 240$ Mpc $= 1.26\,\ell_{285}$—two Yin wakes ($\Lambda_I = 118$ Mpc) apart—the arms are the bubble's meridian lines.

**(c) Imprint on the activated rungs (Hypothesized).** Two rung hits are exact: $26 = 2 \times 13$—the human window is two closures—and $285 = 5 \times 57$—the Cassi bubble sits on a five-arm closure boundary. Two further coincidences are index-ratio curiosities, $80 \approx 26.5\,(\varphi^2 + \varphi^{-2}) = 3 \times 26.5$ (+0.6%) and $292 \approx 26.5\,\varphi^5$ (+0.6%). Both require the "rung number = level count" reading to mean anything, and both are flagged as curiosities, not claims.

**(d) The cosmic depth.** 292 is not on the closure ladder—the nearest level is 233, a gap of 59—and it is the epoch-dependent horizon rung, not a cascade boundary (`foundations/dimensionful-constants-status.md` §3). What the ladder gives instead is the horizon's half-step structure: $\log_\varphi(R_H/\ell_{\text{Pl}}) = 291.54$ today—within 2.2% of the half-integer 291.5—and $R_H/\ell_{285} = 23.3 \approx \varphi^{6.5}$ (+2.0%), the horizon sitting a half-step above the Cassi bubble. These are epoch observations, not constants.

**(e) The first closure-ladder test (2026-08-03).** Y3 targets rungs 34 and 89 with a mass scan, $n = \log_\varphi(M_{\text{Pl}}/m)$. Rung 89 hits: the J/ψ sits at $n = 88.98$—1.0% off the closure level 89 ($F_{11}$)—and the charmed-hadron family clusters at 89–90 (D$_s$: 89.92, D: 90.03, Λ$_c$: 89.61). Rung 34 has no established anchor: the Peccei-Quinn window top ($\sim 10^{12}$ GeV) is the only candidate, and it is Hypothesized physics. As a conditional cross-check of standard physics—the framework's strong-CP resolution requires no axion, `foundations/strong-cp-derivation.md` §3—IF the standard PQ solution exists in nature, THEN $f_a$ anchors rung 34 at $M_{34} = M_{\text{Pl}}\varphi^{-34} \approx 9.57\times10^{11}$ GeV (the window top) and $m_a = f_\pi m_\pi\sqrt{z}/(1+z)/f_a \approx 6.2$ µeV, $n(m_a) = 159.3$ (5.95 µeV, $n = 159.4$, under the $5.70\,\mu\text{eV}\times(10^{12}\,\text{GeV}/f_a)$ convention). Status: Hypothesized (conditional on standard PQ existing)—$m_a$ carries no $\varphi$-anchor of its own: 0.6–0.7 rungs from the chakra-node rung 160 (4.45 µeV) and 0.1–0.2 rungs from half-rung 159.5 (5.66 µeV), a miss either way, testable by ADMX-class haloscopes in the 4–8 µeV band. The scan's sharpest placement was not a Y3 target: the muon sits at $n = 96.000$—0.01%, limited by $M_{\text{Pl}}$'s own precision from $G$—the cleanest absolute rung placement in the framework's catalog, and a wake-anchored integer rung (not a closure level). The neutrino band (0.008–0.05 eV) occupies $n = 140.6$–$144.3$, just below the human window at 142: a structural observation only—neutrino masses are seesaw compounds, so no rung claim is made.

| Particle | $n = \log_\varphi(M_{\text{Pl}}/m)$ | Nearest structure | Residual |
|---|---|---|---|
| μ | 96.000 | 96 | 0.01% |
| J/ψ | 88.980 | 89 (closure level) | 0.96% |
| D | 90.029 | 90 | 1.4% |
| p | 91.462 | 91.5 | 1.9% |
| n | 91.459 | 91.5 | 2.0% |
| Λ_QCD | 94.543 | 94.5 | 2.1% |
| Z | 81.951 | 82 | 2.4% |
| π | 95.421 | 95.5 | 3.9% |
| π⁰ | 95.491 | 95.5 | 0.45% |
| e | 107.079 | 107 | 3.9% |
| v₀ | 79.889 | 80 | 5.5% |

The π⁰ sits 0.45% from the half-rung 95.5, the adjacent structure to the μ's integer rung 96.000—the pion–muon pair spans 0.509 rungs—and $m_{\pi^0}/m_\mu = 1.2775$ sits 0.43% from $\sqrt\varphi$.

## 4. The asymptotic horizon (Derived, conditional)

The horizon does not grow forever: the expansion law has a strictly positive floor, so the cascade depth saturates at a computable $N_\infty$ ≈ 294, roughly three rungs above today.

**(a) The expansion law.** The homogeneous ODE evolves $r = \langle E_Y\rangle/\langle E_I\rangle$ from $a = 0.01$ with

$$H(r) = \frac{\lambda}{3}\left[\frac{(\varphi - r)(1 + r)}{r} + \varphi^{-2}\right]$$

(The 1/3 is **Derived conditional on the assumed spatial dimension $d = 3$** as the isotropic dimension factor $1/d$—`cosmology/cosmology-from-phi.md` §1; the dimensional identification remains Hypothesized in `foundations/why-three-dimensions.md`; the $\lambda\varphi^{-2}$ rate stays Asserted; the Lagrangian's T₀₀ at equilibrium gives 0 or (g/4)φ², never λφ⁻²/3.)

(`two-fluid/run_hubble_pipeline.py`; the Qi-gravity boost variants in `two-fluid/calibrate_initial_ratio_xi.py` and `two-fluid/calibrate_initial_ratio_xi_v2.py`). The conversion rate $\lambda$ cancels from the $r$-evolution—verified numerically for $\lambda = 0.02, 0.05, 0.1$ in the v2 script—so the trajectory's shape is $\lambda$-independent; the calibration fixes only the overall clock.

**(b) The floor and the boost.** The Qi gate saturates at $q_{\max} = 0.873 < 1$, so the Qi-gravity boost factor $\sqrt{1 + (\varphi^{6}-1)q \cdot f}$ (with $f$ the sourced Yang fraction) never vanishes: every coupling convention retains a strictly positive floor, consistent with the irreducible $(1-q)$ floor $\approx 0.23$ measured in the bubble PDE (`foundations/dimensionful-constants-status.md` §3.4). The horizon saturates at

$$N_\infty = N_{\text{now}} + \log_\varphi\!\left(\frac{H(a{=}1)}{H_\infty}\right),\qquad H_\infty = \frac{\lambda}{3}\,\varphi^{-2}\,\sqrt{1 + (\varphi^{6}-1)q_{\max} f}.$$

**(c) The computed values (verified against the scripts).** The three coupling conventions documented in the repo give different trajectories and different saturations:

| Convention | Script | $r(a{=}1)$ | $H(a{=}1)/H_\infty$ | $N_\infty$ |
|---|---|---|---|---|
| Bare (no boost) | `run_hubble_pipeline.py` | 1.589 | 1.12 | 291.8 |
| ξ-full, $\sqrt{1+\xi q}$ (not Yang-weighted; script convention) | `calibrate_initial_ratio_xi.py` | 0.523 | 7.9 | 295.8 |
| Yang-fraction-weighted (verified) | `calibrate_initial_ratio_xi_v2.py` | 1.013 | 3.7 | **294.2** |

The Yang-fraction-weighted form is the verified convention (SPARC rotation curves; the ξ-full form without the Yang weighting is not). With the structural initial ratio $r_0 = \varphi^{-5}/(2-\varphi^{-5}) = 0.0472$ the trajectory reaches $r(a{=}8) = 1.28$, still approaching the attractor:

$$\boxed{N_\infty \approx 294.2,\qquad N_{\text{now}} = 291.54,\qquad \Delta N \approx 2.7\text{ rungs}}$$

The bare form reaches the attractor already by $a \approx 1$ ($r = 1.59$, $\Delta N = 0.25$); the non-weighted ξ-full form gives the ceiling ($\Delta N = 4.3$).

**(d) The caveat, stated plainly.** The exact value depends on which near-equilibrium form of $H$ is canonical; the three documented forms span $\Delta N = 0.25$–$4.3$ rungs. Today's horizon is at most ~4 rungs from the end of its growth—under the verified convention, ~2.7.

## 5. Predictions

| # | Prediction | Status |
|---|---|---|
| Y1 | The composite wake pair closes each rung: $\Lambda_Y + \Lambda_I = \ell_{n+1}$. Verified at 285 ($191 + 118 = 309$ Mpc $= \ell_{286}$); testable wherever two wake scales are resolvable. | Derived |
| Y2 | For supplied adjacent-rung carriers, the wake envelope has candidate bubble antinodes at $m\,\ell_{n+1}$, candidate void nodes at $(m+\frac{1}{2})\ell_{n+1}$, adjacent demodulated parity $-1$, and next-nearest parity $+1$. The structural locations were PDE-verified 2026-08-06 (`two-fluid/run_wake_structural_probes.py`); the 2026-08-27 phase-gap certificate verifies the exact parity and amplitude-contrast law. Physical condensation at those sites remains Hypothesized. | Derived (supplied-wave structure), PDE-verified; condensation mapping open |
| Y3 | The closure ladder imprints on the cascade. First test (2026-08-03): rung 89 hosts the J/ψ ($n = 88.98$, 1.0%—closure level 89); rung 96 hosts the muon ($n = 96.000$, 0.01%); rung 34: no established hit (PQ-window candidate). Existing hits $26 = 2\times13$ and $285 = 5\times57$. | Hypothesized (partially tested) |

Y1–Y3 are cataloged as predictions 43–45 in `predictions/falsifiable-predictions.md` §5.

## 6. Epistemic Boundaries

The tiers below separate what the geometry proves from what it suggests.

- **Supported by Verified Physics**: the composite closure $\Lambda_Y + \Lambda_I = \ell_{n+1}$ (exact identity on documented anchors; PDE-verified P43); the supplied-carrier envelope period, phase parity, and amplitude-contrast law; the default second-order wave branch's imbalance threshold and frequency-domain attenuation; the closure ladder's Fibonacci structure; the saturation of the horizon (positive floor, $q_{\max} < 1$).
- **Derived conditional on supplied adjacent-rung carriers, the de-resonance principle, and composite closure (P43)**: the $1/\varphi$ anchor ratio; the additively spaced phase-layer template; the unique drive frequency $\Omega_*=\varphi^{3/2}\omega_{0,\mathrm{wave}}$ that makes $k_\rho/k_\epsilon=\varphi$. The canonical first-order density PDE supplies no compact phase or oscillatory dispersion, and the live source path supplies no selector for $\Omega_*$.
- **Plausible Hypothesis (test exists)**: a constitutive map from interference nodes to coupling-magnitude modulation; physical condensation at the structural antinodes; the closure-ladder imprint ($26 = 2\times13$, $285 = 5\times57$; Y3 first test: J/ψ at 88.98, muon at 96.000—catalog hits, mechanism open); the $N_\infty$ value (≈ 294.2 under the verified Yang-weighted coupling; 292–296 across documented forms).
- **Speculative**: the rung-index ratio curiosities ($80 \approx 3\times26.5$, $292 \approx 26.5\,\varphi^5$) under the "rung number = level count" reading.
- **Not Supported**: any claim that the current horizon rung 291.5/292 is a derivable constant—it is an epoch-dependent observation (see `foundations/dimensionful-constants-status.md` §3); exact spiral closure at any finite level ($1/\varphi^2$ is irrational).

## References

- `foundations/dimensionful-cascade.md` §6—wake wavelengths, sound-horizon half-step
- `foundations/bubble-edge-geometry.md`—checkerboard condensation field
- `foundations/spin-fibonacci-spiral.md` §1—golden-angle phyllotaxis, five arms
- `foundations/dimensionful-constants-status.md` §3—292 reclassification, irreducible $(1-q)$ floor
- `two-fluid/run_hubble_pipeline.py`—$H(r)$, pipeline calibration
- `computations/seed_arm_width.py`—the seed arm width: cross-width, arc spacing, self-replication, top-of-bubble
- `two-fluid/calibrate_initial_ratio_xi_v2.py`—Yang-fraction-weighted coupling
- `foundations/wu-xing-cycle-structure.md`—the pentagon gap $g = 1 - \varphi^{-5}$
- `principles/de-resonance-principle.md`—why $\varphi$ forbids resonance
- `cosmology/desi-lattice-averaging.md` §2—nesting: $\Lambda_I^{(n)} = \ell_{n-1}$, the inter-rung comb
- `computations/wake_anchor_and_suppression.py`—§A: eigenmode dispersion, beat/extremum spacings, driven emission
- `field-experience/phase-staggered-scale-gap-report.md`—exact phase parity, additive radial layers, second-order channel threshold, source-selection null, and conditional link-modulated gap
