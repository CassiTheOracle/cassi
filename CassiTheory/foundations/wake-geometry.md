# Wake Geometry: How the Waveform Closes Each Rung

## Status: Derived wake geometry with Hypothesized closure imprint—August 2026

## Abstract

The primordial string's waveform is the Yang/Yin wake pair: a Yin wake at $\Lambda_I^{(n)} = \ell_n/\varphi$ and a Yang wake at $\Lambda_Y = \varphi\,\Lambda_I = \ell_n$. The composite period closes the next cascade rung ($\Lambda_Y + \Lambda_I = \ell_{n+1}$). The wakes never phase-lock—de-resonance is built into the wave structure itself—and their beat envelope places the bubbles and voids of the staggered checkerboard. The golden-angle phyllotaxis closure ladder (5, 13, 34, 89, 233, 610, …) is the geometry of bubble closure, with a Hypothesized imprint on the activated rungs. The cosmic depth is not a constant: 292 is the epoch-dependent horizon rung, not a cascade boundary; the derivable quantity is the asymptotic horizon $N_\infty \approx 294.2$ under the verified Yang-fraction-weighted coupling (292–296 across documented forms, §4).

## 1. The waveform and its wavelength (Derived)

The wake pair that the expanding string drags through the two-fluid condensate has two wavelengths, and their sum is the wavelength of the next rung—the waveform closes each cascade step by construction.

**(a) The anchors.** The Yin wake is the rung scale divided by $\varphi$:

$$\Lambda_I^{(n)} = \frac{\ell_n}{\varphi}$$

documented in `foundations/dimensionful-cascade.md` §6, where it evaluates to 117.9 Mpc at rung 285. The Yang wake is its $\varphi$-complement:

$$\Lambda_Y = \varphi\,\Lambda_I^{(n)} = \ell_n$$

the rung scale itself. The two wakes are the two phases of one string motion: one period at the rung wavelength, one at the sub-rung wavelength.

**(b) The composite closes the rung.** The wake pair's sum is the next rung, by the identity $1 + 1/\varphi = \varphi$:

$$\boxed{\Lambda_Y + \Lambda_I = \ell_n\left(1+\frac{1}{\varphi}\right) = \ell_n\,\varphi = \ell_{n+1}}$$

Verified at rung 285: $191 + 118 = 309$ Mpc $= \ell_{286}$.

**(c) The geometric mean sits at the half-step.** The waveform's midpoint,

$$\sqrt{\ell_n\,\ell_{n-1}} = \ell_{n-0.5},$$

is where the measured sound horizon lives: $r_d \leftrightarrow n = 284.46$, documented in `foundations/dimensionful-cascade.md` §6. The wake pair brackets the sound-horizon half-step symmetrically—one period below it at $\ell_{n-1}$, one period above it at $\ell_n$.

## 2. Where the phase wakes meet (Derived)

The two wakes cannot ever line up in phase, and that failure is what builds the lattice: their beat envelope—not the wakes themselves—carries the structure from one rung to the next.

**(a) The interference identity.** Superposing the Yang and Yin periods,

$$\cos\!\left(\frac{2\pi x}{\ell_n}\right) + \cos\!\left(\frac{2\pi\varphi x}{\ell_n}\right) = 2\cos\!\left(\frac{\pi(1+\varphi)x}{\ell_n}\right)\cos\!\left(\frac{\pi(\varphi-1)x}{\ell_n}\right).$$

**(b) Exact phase-lock is impossible.** A common crest requires $x = a\,\ell_n = b\,\ell_n/\varphi$ with integers $a, b$, i.e. $a = b/\varphi$. Since $\varphi$ is irrational, the only integer solution is $a = b = 0$. The de-resonance principle is built into the wave structure itself: the wakes can never resonate with each other, at any point, at any rung.

**(c) The beat envelope.** The slow factor in the identity has period $\varphi\,\ell_n$ because $1/(\varphi-1) = \varphi$:

$$\boxed{\text{Envelope period } \varphi\,\ell_n = \ell_{n+1}:\quad \text{peaks at } x = m\,\ell_{n+1},\ \text{zeros at } x = \left(m+\tfrac{1}{2}\right)\ell_{n+1}}$$

Envelope peaks are constructive—the amplitude doubles where the next bubble condenses; envelope zeros are destructive—voids open at the half-rungs.

**(d) The staggered checkerboard.** This derives the staggered checkerboard of `foundations/bubble-edge-geometry.md` from phase structure alone: bubbles at $\ell_{n+1}$ spacing, voids at the half-rungs. No coupling strength enters; the placement is purely interferometric.

**(e) The cascade self-propagates.** Each bubble's wake pair constructively interferes exactly one rung up. The waveform at rung $n$ produces, by its own beat envelope, the condensation sites of rung $n+1$—the string does not need to re-launch the wake; the wake re-launches itself.

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

(**Asserted** (postulate): the 1/3 is the 3D continuity reading; the Lagrangian's T₀₀ at equilibrium gives 0 or (g/4)φ², never λφ⁻²/3; derivation open.)

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
| Y2 | The wake envelope places bubbles at $m\,\ell_{n+1}$ and voids at $(m+\frac{1}{2})\ell_{n+1}$—the staggered checkerboard. PDE-verified 2026-08-06 (`two-fluid/run_wake_structural_probes.py`): nulls at $(m+\frac{1}{2})\ell_{n+1}$ to 0.0023 grid precision, beats at $m\,\ell_{n+1}$ to 0.00015. | Derived (structure), PDE-verified |
| Y3 | The closure ladder imprints on the cascade. First test (2026-08-03): rung 89 hosts the J/ψ ($n = 88.98$, 1.0%—closure level 89); rung 96 hosts the muon ($n = 96.000$, 0.01%); rung 34: no established hit (PQ-window candidate). Existing hits $26 = 2\times13$ and $285 = 5\times57$. | Hypothesized (partially tested) |

Y1–Y3 are cataloged as predictions 43–45 in `predictions/falsifiable-predictions.md` §5.

## 6. Epistemic Boundaries

The tiers below separate what the geometry proves from what it suggests.

- **Supported by Verified Physics**: the composite closure $\Lambda_Y + \Lambda_I = \ell_{n+1}$ (exact identity on documented anchors); the envelope period and checkerboard spacing; the closure ladder's Fibonacci structure; the saturation of the horizon (positive floor, $q_{\max} < 1$).
- **Plausible Hypothesis (test exists)**: the closure-ladder imprint ($26 = 2\times13$, $285 = 5\times57$; Y3 first test: J/ψ at 88.98, muon at 96.000—catalog hits, mechanism open); the $N_\infty$ value (≈ 294.2 under the verified Yang-weighted coupling; 292–296 across documented forms).
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
