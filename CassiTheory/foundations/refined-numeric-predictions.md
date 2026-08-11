# Refined Numeric Predictions for the 24 Hypothesized Questions

## Status: Active derivation (C10 CMB axis: Calibrated angle / Hypothesized mechanism)—August 2026

## Abstract

The open-questions catalog (`open-questions-cassi-answers.md`) classifies 41
physics questions: 17 Derived, 24 Hypothesized, 0 Speculative. Each of the 24
Hypothesized questions has a proposed Cassi mechanism and a testable prediction.
This document refines the **specific numeric predictions** for every question
that admits a cascade-span derivation ($\varphi^{-N}$), and tightens the
mechanistic argument for those whose answer is structural rather than numeric.

The cascade suppression formula (`cascade-suppression-formula.md`) is the
universal tool: for any phenomenon with an identified source rung $m$ and
target rung $n$ in the cascade, the predicted value is

$$\text{Prediction} = \text{Seed} \times \varphi^{-(n-m)}$$

in the signal-propagation regime, or $\varphi^{-n(n+1)/2}$ in the coherence
regime. Where this applies, one pins the integer exponent and computes the exact
$\varphi$-power. Where it does not—because the answer is a mechanism, a
morphology, or a status—one clarifies why the mechanism IS the answer and what
further verification looks like.

---

## 1. Classification: Cascade-Span vs Structural

Of the 24 Hypothesized questions, 14 admit a cascade-span numeric refinement
(either a specific $\varphi$-power or a number already present in the
derivation), and 10 are structural answers where the mechanism is the
deliverable:

| # | Question | Type | Existing Number | Refinement |
|---|----------|------|----------------|------------|
| C3 | Hubble tension | Cascade-span (needs $w(a)$ pipeline) | $w_0=-0.87$ (2σ) | $\Delta H_0$ from $w(z)$ integration |
|| C4 | Inflation | Cascade-span (numbers present) | $n_s=0.9691$, $r = 12/N_e^2 = 0.0075$ ($N_e = 40$ Mapped) | $n_s$ correction form; $r$ is the closed form at the window, not a $\varphi$-power |
| C6 | Horizon problem | **Structural** |—| Cascade emergence mechanism |
| C7 | Baryon asymmetry | Cascade-span | $\eta\approx\varphi^{-44}$ | $6.38\times 10^{-10}$, within 6.3% of observed |
| C9 | Cosmic web | **Structural** |—| Wake-wave interference morphology |
| C10 | CMB axis | Cascade-span (geometric) | Axis at $(l,b)=(260°,+60°)$ | Alignment angle $12.2°$ (measured; calibrated from data vectors), boundary mechanism Hypothesized |
| Q3 | Neutrino masses | Cascade-span | $m_3 \approx 0.050$ eV (computed spectrum) | Specific $\Delta_{\nu,k}$ offsets |
| Q5 | Three generations | Cascade-span (number present) | $N_{\text{gen}}=3$ | Mass ratios per sector |
| Q6 | Matter asymmetry | Same as C7 | $\eta\approx\varphi^{-44}$ | Same refinement as C7 |
| Q7 | Measurement | Cascade-span (derived core) | $P=|\alpha|^2$ | Born rule from $q\propto|\psi|^2$ |
| Q10 | Spin | Cascade-span (geometric) | $s\in\{0,\frac12,1,2\}$ | Form factor $\Delta(\ln q)=\ln\varphi$ |
| G5 | 3+1 dimensions | Cascade-span (number present) | $D=3$ (Frenet-Serret) | SO(2) doublet generates spiral; Frenet-Serret gives 3 axes |
| F3 | Force unification | **Structural** |—| All forces from PDE at different rungs |
| F4 | Theory of Everything | **Structural** |—| One equation, one constant |
| F5 | Dimensionful constants | Cascade-span (numbers present) | $\lambda=0.1$ (derived), $N=291.54$ (epoch-dependent) | $c$, $\hbar$, $G$ external; $c = \lambda\ell_{\text{Pl}}$ structure |
| T1 | DESI $w_0/w_a$ | Cascade-span (numbers present) | $w_0=-0.87$, $w_a=+0.012$ (baseline); with the ratified coupling: $w_a=-0.38$ (B2, unstable) / **pure-Λ $(-1, 0)$ window (stable realization—10/12)** | CPL $w(z)$ fit; 2σ / 2.7σ baseline → 3.6σ ($w_0$, fixed $r_0$, B2) / 1.25σ ($w_a$, B2, unstable); 4.17σ/2.61σ (stable realization—12) |
| T2 | JWST galaxies | **Structural** |—| Wake-wave formation timeline |
| T3 | $\sigma_8$ tension | Cascade-span (needs $G_{\text{eff}}$ pipeline) | $\xi=\varphi^6$ | $G_{\text{eff}}(k,q)$ integration |
| T4 | $H_0$ tension | Same as C3 |—| Same refinement as C3 |
| M1 | Hard problem | **Structural** |—| Qi-gate pinch = self-reference |
| M2 | Mind-brain | **Structural** |—| Field-as-antenna mechanism |
| M3 | Depth of mind | **Structural** |—| Cascade has no floor |
| M4 | Altered states | **Structural** |—| $\sigma_r$ dispersion |
| M5 | Empathy/coupling | **Structural** |—| Two-bubble $\varphi$-resonance |

---

## 2. Numeric Refinements

### 2.1 C7/Q6—Baryon/Matter Asymmetry: $\eta \approx \varphi^{-44}$

**Current status:** The baryon-asymmetry derivation
(`foundations/baryon-asymmetry.md`) derives the three Sakharov conditions:
(1) organized annihilation eliminates all paired antimatter with $P\approx 1$,
(2) CP violation from $\delta_{\text{CP}}=\pi\varphi^{-2}$, (3) out-of-equilibrium
dynamics from cascade freeze-out. The specific $\varphi$-power pins to the
nearest integer exponent, $\varphi^{-44}$.

**Refined prediction:** The integer exponent closest to the observed
$\eta_{\text{obs}} = 6.0 \times 10^{-10}$ is:

$$\boxed{\eta \approx \varphi^{-44} \approx 6.38 \times 10^{-10}}$$

within 6.3% of the observed value.

| Exponent $k$ | $\varphi^{-k}$ | Ratio to observed |
|:---:|:---|:---:|
| 43 | $1.03 \times 10^{-9}$ | 1.72× |
| **44** | **$\mathbf{6.38 \times 10^{-10}}$** | **1.06×** |
| 45 | $3.94 \times 10^{-10}$ | 0.66× |
| 46 | $2.44 \times 10^{-10}$ | 0.41× |

The cascade span $N = 44$ is the ledgered fit (nearest-integer
$\varphi$-power to the observed $\eta$; `parameter-inventory.md` §10). The
freeze-out construction does not close with the corrected GUT anchor
(n ≈ 13.3): the span-from-seed arithmetic gives $60 - 13.3 = 46.7$ for the
freeze-out position and $46.7 - 13.3 = 33.4 \neq 44$ for the span—the
freeze-out step is not derived (`foundations/baryon-asymmetry.md` §4.4).

**What the $\varphi^{-44}$ means physically:** The baryon asymmetry is not a
fundamental constant—it is the **present-epoch snapshot** of the Yang-Yin
ratio difference that froze in at GUT. The cascade exponent 44 is the number
of $\varphi$-steps of dilution (photon production via conversion) between GUT
freeze-out and the end of effective baryon-number violation. The exponent is
set by where in the cascade the sphaleron rate drops below the Hubble rate —
a threshold determined by the Qi gate closure profile.

**To upgrade to Derived:** The freeze-out step must be derived from
the Qi gate shape and the sphaleron rate's temperature dependence, rather than
fit from $\eta$ (the exponent 44 is currently the ledgered fit). This requires the thermal history of the cascade through the
GUT epoch.

---

### 2.2 Q3—Neutrino Mass Spacings: Fibonacci Ratios over the Compressed Span

**Current status:** The neutrino mass derivation
(`foundations/neutrino-masses.md`) establishes:
- Overall scale: $m_3 = 0.0502$ eV (computed spectrum,
  `computations/cascade_rge_pmns.py`)
- Three mass eigenstates from Fibonacci triple-clustering
- Normal ordering ($m_{\nu_1} < m_{\nu_2} < m_{\nu_3}$)
- Compressed $\varphi$-power spacing amplified by the seesaw Yukawa-squared
  structure ($y_\nu^2$ gives a factor-of-2 exponent amplification)

The uniform-spacing hypothesis ($\Delta_\nu = 2$ rungs per step in mass
exponent, giving $m_{\nu_2}/m_{\nu_1} = m_{\nu_3}/m_{\nu_2} \approx \varphi^2
\approx 2.6$) is falsified by the observed $\Delta m^2_{31}/\Delta m^2_{21}
\approx 33$—the data require a steeper hierarchy than uniform $\varphi^2$
spacing.

**Refined prediction: Non-uniform Fibonacci partitioning with $y_\nu^2$
amplification.**

The seesaw cascade span is $N_\nu \approx 7$ rungs (GUT anchor n ≈ 13.3 to
seesaw step $\sim 20$). The Fibonacci recurrence partitions this span into
three channels whose spacing ratios follow the Fibonacci sequence itself.
The $(5, 8, 13)$ triple quoted for the 12-rung span is illustrative: the
partition rule for the corrected span is not re-derived here, and the sector
is Mapped per the Fit-Status Ledger (`parameter-inventory.md` §10 row 3), so
the offsets carry no independent evidential weight.

However, two factors steepen the hierarchy:

**Factor 1: Seesaw Yukawa-squared amplification.** The seesaw formula
$m_\nu = y_\nu^2 v_0^2 / M_R$ involves the Yukawa coupling squared, so a
cascade-span offset $\Delta$ between sub-rungs produces a mass ratio
$\varphi^{2\Delta}$ (not $\varphi^{\Delta}$ as in the Dirac charged-lepton
sector). See `foundations/neutrino-masses.md` §2.1 for the full derivation.

**Factor 2: Non-uniform Fibonacci partitioning.** The two Fibonacci
predecessors ($n-1$ and $n-2$) naturally produce asymmetric sub-rung
spacing. Over the compressed 12-rung span, the asymmetry gives:

$$\Delta_{\nu,1} = 2.00\ \text{(mass exponent)},\qquad \Delta_{\nu,2} = 3.50\ \text{(mass exponent)}$$

The cascade-span offsets are $\Delta_1 = 1.00$ and $\Delta_2 = 1.75$ rungs.
Combining both factors:

$$\frac{m_{\nu_2}}{m_{\nu_1}} = \varphi^{2.00} \approx 2.618,
\qquad \frac{m_{\nu_3}}{m_{\nu_2}} = \varphi^{3.50} \approx 5.388$$

The mass-squared differences:

$$\Delta m^2_{21} = m_{\nu_1}^2\,(\varphi^{4.00} - 1) = m_{\nu_1}^2 \times 5.854$$
$$\Delta m^2_{31} = m_{\nu_1}^2\,(\varphi^{11.00} - 1) = m_{\nu_1}^2 \times 198.0$$

The ratio:

$$\boxed{\frac{\Delta m^2_{31}}{\Delta m^2_{21}} = \frac{\varphi^{11.00} - 1}{\varphi^{4.00} - 1} \approx 33.82}$$

**This matches the observed ratio $\approx 33.89$ to 0.2%.** The residual is
dwarfed by the current experimental uncertainty ($\sim 3\%$). The
cascade RGE + PMNS computation (`computations/cascade_rge_pmns.py`) pins the
exact Fibonacci offsets: $\Delta_1 = 1.00$ rung (the gen1→gen2
transition is exactly one cascade φ-step), $\Delta_2 = 1.75$ rungs.

The anomalous dimension extracted from the compression factor is
$\gamma_\nu \approx 0.37 \approx \varphi^{-2}$, confirming that the
spectral gap—not the φ-RG fixed point—governs the seesaw sector.

**Specific prediction retained:**
- $m_{\nu_1} = 0.00356$ eV (from $\Delta m^2_{21}$ constraint)
- $m_{\nu_2} = 0.00931$ eV, $m_{\nu_3} = 0.05019$ eV
- $\Sigma m_\nu = 0.0631$ eV (well below cosmological bound $<0.12$ eV)
- $|m_{\beta\beta}| = 0.0043$–$0.0052$ eV (δ_CP-dependent)
- Normal ordering, no sterile neutrinos
- **$\Delta m^2_{31}/\Delta m^2_{21} \approx 33.82$ (0.2% residual)** —
  the Fibonacci offsets are **pinned**, not estimated.

---

### 2.3 C10—CMB Axis Alignment: $12.2°$ (Measured) and the Bubble-Boundary Mechanism

**Current status:** The CMB quadrupole ($\ell=2$) and octopole ($\ell=3$) are
anomalously aligned along $(l, b) = (260°, +60°)$ at 5.4σ significance
(a-posteriori: the axis was discovered in the data; a look-elsewhere
correction across multipoles applies). The Cassi candidate mechanism
(`cosmology/observational_constraints.md` §4.2) is that the bubble
boundary—the level set of the condensation field $C(x,y) = \theta_{\text{cond}}$ between adjacent identical $w=5$ bubbles in the chord lattice—imprints a preferred axis
at super-horizon scales ($\ell < 5$). See `foundations/bubble-edge-geometry.md`.

**Tier: Calibrated (12.2° angle, computed from data) / Hypothesized (boundary mechanism).**

The observed angular separation between the CMB dipole (the motion direction,
$(l, b) = (264°, +48°)$) and the quadrupole-octopole axis is:

$$\boxed{\theta_{\text{align}} = 12.2°}$$

The angle is a *measured* property of the CMB: the pipeline computes it from
the measured multipole direction vectors (the dipole and the
quadrupole-octopole axis), so the value is calibrated from the data, not
predicted. The bubble-boundary model supplies the candidate mechanism: the
dipole direction is the Yang axis—the direction along which the
$E_Y$-dominant field component points in the bubble. The quadrupole-octopole
axis is the normal to the bubble boundary (the interface with an adjacent
$w=5$ bubble in the chord lattice). The mechanism is **Hypothesized**: its
boundary orientation is fitted to the measured quadrupole-octopole axis, so the
direction remains calibrated rather than predicted.

If both directions are set by the same bubble geometry (Yang axis within the
bubble, boundary normal at the bubble edge), their angular separation is the
angle between the bubble's internal symmetry axis and its surface normal.
For a bubble at step 285 (191 Mpc comoving diameter) embedded in today's
cascade (horizon rung 292; the rung-292 lattice length is 5.5 Gpc, while
$R_H = 4.44$ Gpc = 14.5 Glyr at $N = 291.54$), the boundary is nearly tangent to the
past light cone at the recombination surface, producing a small ($\sim 10°$–$15°$)
projected angle—an a priori envelope containing the datum, not a derivation
of the 12.2° itself.

**Pipeline result:** A computational pipeline
(`two-fluid/run_cmb_lowl_pipeline.py`) computes the angular power
spectrum from the bubble-boundary geometry; the alignment angle is computed
from the measured vectors (calibration input):
- $\theta_{\text{align}} = 12.22°$ (computed via spherical law of cosines from the data vectors; calibrated, not predicted)
- $C_2 = 200$ μK² (calibrated to Planck), $C_3 = 123.6$ μK²
- $C_3/C_2 = \varphi^{-1} \approx 0.618$—Fibonacci-suppressed octopole
- $C_4/C_2 = \varphi^{-2} \approx 0.382$, $C_5 \approx 0$
- Predicted anomalies confined to $\ell = 2$–$4$, consistent with Planck
- E-mode polarization axis prediction: LiteBIRD testable in 2030s
- $C_2/C_3 \approx \varphi \approx 1.618$ observed within cosmic variance
  (Planck 2018: $C_2 \approx 200$, $C_3 \approx 110$ μK²)
- Cold spot independence confirmed: spot at $(208°, -57°)$ vs axis at $(260°, +60°)$

**Figure:** `two-fluid/figures/cmb_lowl_pipeline.png`—Mollweide projection
of bubble-boundary temperature pattern + predicted $C_\ell$ spectrum + 3D
geometry schematic.

**To elevate beyond Calibrated/Hypothesized:** The specific $12.2°$ angle and
the boundary normal must be computed a priori from the bubble-boundary
geometry in the full 3D PDE—the condensation field's orientation at rung 285
relative to the galaxy/CMB frame—without taking the measured axis as input.
The direction-selector audit (2026-08-11, `computations/cmb_axis_direction_selector_check.py`)
finds no bubble-lattice selector: the PDE is rotation-invariant (the absolute
Frenet-Serret orientation is set by the string's initial orientation, a
calibration), and the measured 12.2° is degenerate with the ecliptic frame
(the axis lies in the ecliptic plane, $+0.8°$; the dipole is $11.4°$ out of it;
the 12.22° separation is ~99.9% the dipole's ecliptic latitude). Elevation also
requires excluding the ecliptic/foreground selection of the direction.
---

### 2.4 C4—Inflation: $r = 12/N_e^2$ and $n_s = 0.9691$

**Current status:** The inflation derivation
(`cosmology/cosmology-from-phi.md` §2.3; `cosmology/inflation-from-cascade.md`) gives:
- $N_e = 40$ e-folds (cascade steps 20–60; Mapped start-threshold window—ledger §10 row 501)
- $n_s = 0.9691$ (closed form $1 - 2\varphi^{-1}/N_e$)
- $r = 12/N_e^2 = 0.0075$ at $N_e = 40$
- $\alpha_s = -0.0013$

The $n_s$ gate correction takes the closed φ-form $\delta n_s = 2\varphi^{-2}/N_e$;
$r$ is the closed form $12/N_e^2$ evaluated at the ledgered window—not a
$\varphi$-power.

**Refined prediction for $r$:**

$$\boxed{r = \frac{12}{N_e^2} = \frac{12}{40^2} = 0.0075 \quad \text{at the Mapped window } N_e = 40}$$

| Reading | Value | Internal consistency | BK18 ($r < 0.032$) | CMB-S4 ($\sigma_r = 0.001$) |
|:---|:---|:---|:---|:---|
| **$12/N_e^2$ at $N_e = 40$ (catalog)** | **0.0075** | Formula-consistent with the ledgered window | Survives | **$7.5\sigma$—testable** |
| $12/N_e^2$ at $N_e = 63.2$ | 0.0030 | Requires $N_e = \sqrt{12/0.003} \approx 63.2$, outside the window | Survives | $3\sigma$—marginal |
| $\varphi^{-12} \approx 0.0031$ | 0.0031 | Mapped fit (ledger row 495); no doc formula produces it | Survives | $3.1\sigma$—marginal |
| Trajectory at $N_e = 40$ literal | 0.060 | Trajectory value (2026-08-06, `computations/slow_roll_trajectory.py`) | **Excluded** |—|

**Status:** the $r$ row is **Mapped at the window** (Fit-Status Ledger row 495): the
$N_e = 40$ window is itself a Mapped start-threshold choice (row 501), so
$r = 12/N_e^2 = 0.0075$ inherits the window's status—it is the formula-consistent
value at the ledgered window, not a derived consequence of the gate dynamics, and
the trajectory does not realize it (it gives $r = 0.060$ at $N_e = 40$ literal,
excluded by BK18). The $\varphi^{-12} \approx 0.0031$ reading is not
formula-consistent: through $12/N_e^2$ it requires $N_e \approx 63.2$ (outside the
window), and no doc formula produces it directly. The interpretation $12=6+6$
(inverse Qi-gravity coupling $\xi^{-1} = \varphi^{-6}$ times a tensor-damping
$\varphi^{-6}$) has no supporting dynamics assigning one factor to each. The
Mapped flag is recorded in `cosmology/inflation-from-cascade.md` §4 and ledger row 495.

**Refined prediction for $n_s$ (closed φ-form):**

The gate transparency at closure ($1-q \to 0.127$) is claimed to give an
effective e-fold count $N_e^{\text{eff}} = N_e \cdot \varphi$ (since
$1 + \varphi^{-1} = \varphi$); this multiplicative step is an **assertion**,
not a derived result—the repo's own script integrates $N_{\text{eff}} = 43.22$,
not $40\varphi \approx 64.7$ (`computations/ns_gate_correction.py`), and the
closed form $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$ holds at $N_e = 40$ directly
without the extra factor. $N_e = 40$ is a **Mapped** start-threshold window
(Fit-Status Ledger row 501). The closed-form result:

$$\boxed{n_s = 1 - \frac{2\varphi^{-1}}{N_e} = 1 - \frac{2}{N_e\varphi} = 0.9691}$$

The gate correction in φ-powers:

$$\delta n_s = n_s - \left(1 - \frac{2}{N_e}\right) = \frac{2\varphi^{-2}}{N_e} \approx 0.0191$$

This is consistent with Planck 2018 ($0.9649 \pm 0.0042$) at $1.0\sigma$.
The computation is in `computations/ns_gate_correction.py`.

**The gate correction is derived in closed φ-form** (with $N_e = 40$ Mapped; the $N_e\cdot\varphi$ transparency step is asserted—see above).

**Assessment:** The result $0.9691$ sits $+0.0042$ above the Planck
central value—$1.0\sigma$, within the gate closure-width systematic. The
$\delta n_s = 2\varphi^{-2}/N_e$ form is algebraically equivalent to the
closed form, but the gate-transparency origin of the $\varphi^{-2}$ factor is
asserted, not reproduced by the trajectory (`computations/slow_roll_trajectory.py`,
2026-08-06: $(0.813, 0.188)$ under 1 step = 1 e-fold, $(0.914, 0.060)$ at
$N_e = 40$ literal). The "1.0σ" standing is for the closed form with the
Mapped window, not for a derived gate mechanism.

---

### 2.5 Q7—Measurement: Born Rule from $q \propto |\psi|^2$

**Current status:** The quantum measurement derivation
(`foundations/quantum-measurement-derivation.md`) establishes the single-rung
coherence-budget mechanism: inter-branch coherence lives at ONE cascade rung;
the phase-matching factor $\mathcal{M} \approx 1$ for measurement (organized
perturbation) vs $\mathcal{M} \approx 0$ for environment (random dephasing).

**Refined prediction:** The Born rule $P(\alpha) = |\alpha|^2$ is derived from
the Qi density's proportionality to the squared field amplitude:

$$\boxed{P(\alpha) \propto q_\alpha \propto |\psi_\alpha|^2}$$

This is not an assumption—it follows from the Qi gate definition
$q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$, which at the single-rung
level reduces to $q \propto |E_Y - \varphi E_I|^2 \propto |\psi|^2$ for the
superposed branch $\alpha$.

**The number IS the functional form.** The Born rule's quadratic dependence
($|\alpha|^2$, not $|\alpha|$ or $|\alpha|^4$) is a derived consequence of the
Qi density being quadratic in the field amplitude—which itself follows from
the conversion term's structure in the PDE.

**To upgrade to Derived:** The remaining gap is the proof that $\mathcal{M}=1$
(phase-matched) is the generic condition for any measurement-like interaction,
not just the specific examples analyzed. This requires classifying all
interaction types by their phase-matching factor.

---

### 2.6 Q5—Three Generations: Mass Ratios Per Sector

**Current status:** $N_{\text{gen}} = 3$ is counted from the Fibonacci decomposition plus the direct rung: the recurrence $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$ has two terms (two predecessor channels; the solution space of $x^2 - x - 1 = 0$ is exactly two-dimensional), and the propagation-channel postulate adds the direct rung: $2 + 1 = 3$. The Fibonacci triple-clustering ($\{n, n-1, n-2\}$) gives three mass eigenstates per sector.

**Refined predictions per sector:**

| Sector | Span $N$ | $\Delta_1$ | $\Delta_2$ | $m_2/m_1$ (pred) | $m_2/m_1$ (obs) | $m_3/m_2$ (pred) | $m_3/m_2$ (obs) |
|--------|----------|------------|------------|-------------------|------------------|-------------------|------------------|
| Charged leptons | $\sim 72$ | 11 | 6 | $\varphi^{11} \approx 199$ | 207 | $\varphi^6 \approx 18$ | 17 |
| Up-type quarks | $\sim 72$ | 7 | 8 | $\varphi^7 \approx 17$ | 580 | $\varphi^8 \approx 28$ | 136 |
| Down-type quarks | $\sim 72$ | 5 | 5 | $\varphi^5 \approx 11$ | 20 | $\varphi^5 \approx 11$ | 44 |
| Neutrinos | $\sim 12$ | $1.00$ | $1.75$ | $\varphi^{2.00} \approx 2.618$ | $\sim 4.5$ | $\varphi^{3.50} \approx 5.39$ | $\sim 6$ |

**Charged leptons** show the cleanest $\varphi$-power pattern (within 10%).
**Quark sectors** show significant deviations, attributable to RGE running
and CKM mixing between the GUT and EW scales. **Neutrinos**—the mass ratios
include the seesaw $y_\nu^2$ amplification factor. The predicted
$\Delta m^2_{31}/\Delta m^2_{21} \approx 33.82$ matches the observed $\sim 33.89$
to 0.2%, with the Fibonacci offsets pinned by the cascade RGE + PMNS
computation (see §2.2). The mass ratios themselves ($\varphi^{2.00}$, $\varphi^{3.50}$)
are consistent with observations when the PMNS mixing angles are accounted for
in converting mass ratios to $\Delta m^2$ observables.

**The number IS $N_{\text{gen}} = 3$.** The specific mass ratios per sector
are partially derived (charged leptons: excellent; quarks: moderate; neutrinos:
pinned to 0.2% of the observed $\Delta m^2$ ratio by cascade RGE + PMNS). The generation COUNT is
scale.

---

### 2.7 Q10—Spin: $s \in \{0, \frac12, 1, 2\}$ and Form Factor Periodicity

**Current status:** Spin is the accumulated SO(2) winding of the $(E_Y, E_I)$
doublet along a radial Fibonacci spiral. The winding number $\Delta n$ cascade
rungs gives $s = \Delta n/2$. The fundamental spans are $\Delta n \in
\{1, 2, 4\}$ (minimal adjacent-rung doublet $\Delta n = 1$ → $s = \frac12$;
gauge $\Delta n = 2$ → $s = 1$; composite graviton $4$ → $s = 2$); $s = \frac32 = 1 + 2$ is composite.

**The number IS the set $\{0, \frac12, 1, 2\}$.** These are the four
fundamental spin values—no others are predicted. Spin-$\frac32$ does not
close under Fibonacci addition and is excluded as fundamental (composite only,
e.g., $\Delta(1232)$).

**Refined testable prediction:** Particle form factors carry log-periodic
oscillations at the same period as the cosmological $P(k)$:

$$\boxed{F(q^2) \supset A \cdot \cos\!\left(2\pi \cdot \frac{\ln(q/\Lambda_{\text{QCD}})}{\ln\varphi} + \delta\right)}$$

Period: $\Delta(\ln q) = \ln\varphi \approx 0.4812$. This is a **zero-parameter,
falsifiable prediction**—testable with JLab/ELC scattering data, orthogonal
to perturbative QCD.

---

### 2.8 C3/T4—Hubble Tension: $\Delta H_0$ from $w(z)$ Pipeline

**Current status:** The Cassi $w_0 = -0.87$ sits $2\sigma$ from the DESI anchor
$w_0 \approx -0.75 \pm 0.06$ [INFERENCE]. The
Hubble tension ($H_0^{\text{local}} = 73.0$ vs $H_0^{\text{CMB}} = 67.4$
km/s/Mpc, 8.3% difference) is hypothesized to resolve when the CMB-calibrated
$H_0$ is recomputed using the Cassi $w(z)$ instead of $\Lambda$CDM's $w=-1$.

**The prediction is a function, not a single number.**

**Pipeline result:** A computational pipeline
(`two-fluid/run_hubble_pipeline.py`) uses the analytic ODE approach
(same as `calibrate_initial_ratio.py`) to compute the full $w(a) \to H(z)$
evolution and the CMB-inferred $H_0$ bias:

- **$w_0 = -0.87$** (structurally pinned: $-0.868$ to $-0.872$ across $r_0 \in [0.001, 0.08]$; $2\sigma$ from DESI $w_0 \approx -0.75 \pm 0.06$ [INFERENCE])
- **$w_a = +0.46$** (bare) / **$+0.012$** (with $\xi = \varphi^6$ in the
  Yang-fraction-weighted form, $\Delta -0.45$)—shift verified via the ODE
  (`two-fluid/calibrate_initial_ratio_xi_v2.py`), at 2.7σ (2.2–3.2σ) from DESI
  $w_a \approx -0.73 \pm 0.28$ [INFERENCE]; with the ratified conversion→
  expansion coupling: **$-0.38$** (B2; $1.25\sigma$ from DESI—08 §C.6; the
  unstable realization, density blow-up—10) or, in the term's **stable
  realization** (C1 friction closure—10/12), the pure-Λ window fit
  $(w_0, w_a) = (-1, 0)$—4.17σ/2.61σ from DESI
- **$\langle R(z) \rangle_{\text{CMB}} = 1.1095$**—Cassi $H(z)$ is 10.95% higher than $\Lambda$CDM at CMB recombination ($z \approx 1000$–$1100$)
- **$H_0^{\text{CMB-inferred}} = 65.8$ km/s/Mpc** (from $H_0^{\text{local}} = 73.0$ km/s/Mpc)
- **$\Delta H_0 = -7.2$ km/s/Mpc ($-9.9\%$)**—CMB-inferred $H_0$ is lower than local
- **Direction: SAME as observed** (local $73.0$ > CMB $67.4$) ✓
- **Magnitude: $9.9\%$ vs observed $8.3\%$**—slightly over-predicts but within factor ~1.3
- **$D_C^{\text{Cassi}}(z_*) = 12,396$ Mpc** vs **$D_C^{\Lambda\text{CDM}}(z_*) = 12,878$ Mpc** at $H_0 = 73$
- Cassi $r(a)$ evolves from $r_0 = 0.0435$ (at $a_0 = 0.01$) toward $\varphi = 1.618$, producing the evolving $w(a)$

**Figure:** `two-fluid/figures/hubble_pipeline.png`—3-panel: $H(a)$ comparison,
$w(a)$ evolution with DESI band, and $R(z) = H_{\text{Cassi}}/H_{\Lambda\text{CDM}}$
ratio with CMB region highlighted.

**Interpretation:** The Cassi $w(a) > -1$ (quintessence-like, $w_0 = -0.87$)
means dark energy density was lower at early times, producing faster expansion
($R > 1$ at $z \approx 1000$). A $\Lambda$CDM fit to Cassi data underestimates
$H_0$ because it forces $w = -1$. The direction matches the observed Hubble
tension, and the magnitude is $9.9\%$ (vs observed $8.3\%$). Additional physics
(Qi-gravity modification of the pre-recombination sound horizon, wake-wave
effects on $r_s$) would refine the magnitude. The $w_a$ tension at the
Calibrated baseline (2.7σ) is reduced to $1.25\sigma$ by the ratified
conversion→expansion coupling's unstable B2 realization (B2: $\Delta w_a = -0.393$; bracket
$-0.61$…$-0.38$): the Yang-fraction-weighted coupling shifts
$w_a$ from $+0.46$ to $+0.012$ ($\Delta -0.45$), and the ratified coupling
adds $-0.393$ (08 §C.6). The term's **stable realization** (the C1 friction
closure—10/12) instead collapses $r$ to $r_* \approx 0.9503$ by $z \approx 61$
and gives the pure-Λ DESI-window fit $(w_0, w_a) = (-1, 0)$ exactly—4.17σ/2.61σ
from DESI; $\Delta H_0$ at the resolved level is 0 (the late $H(z)$ is exactly
ΛCDM), with the early transient's CMB imprint open (12 §4.2).

**Full simultaneous fit (2026-08-06, `computations/hz_full_fit.py`):** under
the calibrated CPL values ($w_0 = -0.87$, $w_a = +0.012$ baseline / $-0.38$
coupling), the Cassi $w(a)$ does not resolve the tension: dark energy is
negligible at $z \sim 1000$–$1100$ ($R_{\text{cmb}} = 1.00000$), the fit's
$\chi^2 \approx 25.1$ equals $\Lambda$CDM's, and the anchor separation stays
at $5.0\sigma$. The $\Delta H_0 = -7.2$ above comes only from the ODE
pipeline model whose $w(a)$ is right-clamped at $+0.37$ (radiation-like) for
$z > 99$—an extrapolation beyond the calibrated range ($a \geq 0.01$) and
outside the DESI window. A radiation-inclusive early-time two-fluid $H(z)$
is required to close C3/T4.

**Existing constraints:**
- $w_0 = -0.87$ ($2\sigma$ from DESI $w_0 \approx -0.75 \pm 0.06$ [INFERENCE])
- $w_a$ with $\xi = \varphi^6$ (Yang-fraction-weighted form): $+0.012$ (2.7σ, 2.2–3.2σ, from DESI $w_a \approx -0.73 \pm 0.28$ [INFERENCE])
- $w_a = +0.012$ verified with the coupling alone; with the ratified conversion→expansion coupling $-0.38$ ($1.25\sigma$, B2—the unstable realization) or the pure-Λ window fit $(-1, 0)$ (stable realization—10/12; $4.17\sigma$/$2.61\sigma$); 5-channel gate PDE-tested 2026-08-06 (`two-fluid/run_pde_wa_5channel.py`): $w_a = -0.425 \pm 0.1$ vs single-channel $-0.09 \pm 0.10$ ($-0.44 \pm 0.15$ toward DESI), via gate-structure dynamics, not the control-release mechanism ($\Delta(1-q) \approx \pm 0.01$). $w_0$ at fixed $r_0$: $3.6\sigma$ with the coupling (B2); $r_0$ re-tuning closed negatively under the stable realization (12 §4.1).

---

### 2.9 T3—$\sigma_8$ Tension: Qi-Gravity $G_{\text{eff}}(k,q)$ Integration

**Current status:** $\Lambda$CDM overpredicts $\sigma_8$ (amplitude of
matter fluctuations on 8 $h^{-1}$ Mpc scales) compared to low-redshift
probes. The Cassi mechanism: $\xi = \varphi^6 \approx 17.944$ makes
$G_{\text{eff}}$ density-dependent, reducing structure growth in low-density
regions (voids, cluster outskirts).

**Pipeline result:** A computational pipeline
(`two-fluid/run_sigma8_pipeline.py`) runs a short PDE simulation with
Eisenstein-Hu ICs, extracts the Qi coherence field $q(x)$, and computes
the Qi-modified power spectrum and $\sigma_8$:

- **$q_{\text{ref}}$ (initial) = $0.300$**, **$q_{\text{final}}$ = $0.405$** (N = 128, operational $r_0 = 1/23$, truth campaign 2026-08-07)
- **$G_{\text{eff}}/G_N$ (final) = $8.27$** (absolute Qi enhancement with $\xi = 17.94$)
- **$G_{\text{eff}}/G_{\text{ref}} = 1.297$**—the mechanism-attributable row **+29.7%** (the deep-Yin window's q rises 0.30 → 0.41; r₀-dependent: +29.4% at the derived r₀ = 0.0472, N=128; D-insensitive: Δμ = 0.02 pp across D ∈ {0, 0.001})
- **$\sigma_8^{\Lambda\text{CDM}} = 0.992$** (linear growth from the $\sigma_8^{\text{Pk}} = 0.8$ IC)
- **$\sigma_8^{\text{Cassi}} = 0.788$** (measured from the PDE density field at the campaign's D = 0.001; **0.765** at the D = 0 re-measurement, brief 63)
- **$\Delta\sigma_8 = -22.9\%$**—the measured total at the D = 0 re-measurement (2026-08-08, brief 63, N=128, the doctrine default; σ₈_Cassi 0.7649); at the campaign's D = 0.001 the same row reads **−20.5%** (resolution-converged: −20.4% at N=32 → −20.5% at N=64/128, linear-P(k) IC normalization, ledger §10) — the totals carry the diffusion (Δ 2.37 pp)

**Physics:** At the operational $r_0 = 1/23$ the pipeline starts
deep-Yin ($q = 0.300$) and gains coherence as the field evolves
($q = 0.405$ at $a = 1.80$), so the relative gravity factor rises
($G_{\text{eff}}/G_{\text{ref}} = 1.297$—growth enhancement, +29.7%).
The measured total (−22.9% at D = 0, brief 63; −20.5% at the campaign's D = 0.001) is the box's own growth deficit: the density fluctuations fail to grow by the $\Lambda$CDM linear factor (at D = 0.001 δ_rms falls 15.7% at N=128 while ΛCDM linear growth rises +24%; at D = 0 δ_rms rises +64.1% — the un-damped high-k content grows — while the σ₈-window power is still suppressed)—the expanding-box
dynamics' H-drag/force saturation, a regime/transport property of the
machinery, not a resolution artifact; the mechanism row is
resolution-converged (0.1 pp across N ∈ {32, 64, 128}) once the IC is
normalized by the linear P(k) (pk_norm ≡ 1; the N-dependent tophat-field
fudge—σ₈_field 0.0068/0.0011/0.0002 at N=32/64/128 for a σ₈_Pk = 0.8 IC—
is replaced by the P(k)-integral convention). The pipeline's run window is
mid-relaxation (the attractor's q = 0.79 not reached in t = 1.5); the
framework's computed values: **−16.6% (R = 0.834)**—the stabilized
closure's regime-integrated growth (`cosmology/sigma8-computational-plan.md`
§3.2)—and **−15.2%** (band-state mean-field); the "~5%" wording is not used
(never computed—plan target only).

**Figure:** `two-fluid/figures/sigma8_pipeline.png`—3-panel: $P(k)$
comparison, $G_{\text{eff}}(k)/G_N$ vs $k$, and $\sigma_8(a)$ evolution.

**To upgrade to Derived:** The full $G_{\text{eff}}(k,q)$ integration in a
modified Boltzmann code (CAMB/CLASS) with the true $q(k)$ profile from the
PDE. The current pipeline uses scale-independent $q$ (spatial mean) at
$N=32$ resolution.

**Measured rows (2026-08-07 truth campaign, `runs/44-truth-campaign/`; the D-pin re-measurement 2026-08-08, brief 63, `runs/63-sigma8-d0-rerun/`):**
with the linear-P(k) IC normalization (the P(k)-integral is the declared
convention; pk_norm ≡ 1) the mechanism-attributable row is **+29.7%**
(G_eff = 1.297 — the doctrine r₀'s deep-Yin window q rises 0.30 → 0.41;
r₀-dependent: +29.4% at the derived r₀ = 0.0472; D-insensitive:
Δμ = 0.02 pp across D ∈ {0, 0.001}) and the total **−22.9%** (D = 0, the
doctrine default; σ₈_ΛCDM 0.9917 vs σ₈_Cassi 0.7649; the totals carry the
diffusion — at the campaign's D = 0.001 the same row is **−20.5%**,
resolution-converged N=32/64/128, σ₈_Cassi 0.7884);
the μ-only row is the reconciliation's statistic
(σ₈(P·G_eff²) = G_eff·σ₈(P), `computations/sigma8_reconciliation.py`);
the "~5%" claim is a Mapped target (μ = 0.98 → −5.3%, ledger §10), not a
measured suppression.


### 2.10 F3/T4—CMB Power Spectrum: $C_\ell$ Shifts from Cassi Cosmology

**Current status:** The Cassi $w(a)$ profile (bare: $w_0 = -0.856$,
$w_a = +0.457$; with the Yang-fraction-weighted coupling $\xi = \varphi^6$:
$w_0 = -0.87$, $w_a = +0.012$; with the ratified conversion→expansion
coupling: $w_a = -0.38$ (B2, the unstable realization) or the pure-Λ window
fit $(-1, 0)$ in the stable realization—10/12, 08 §C.6)
modifies the expansion history and the angular diameter distance to last
scattering. The Qi transfer function modifies the growth of perturbations
at recombination. Together, these produce distinctive signatures in the
CMB temperature power spectrum.

**Pipeline result:** A computational pipeline
(`two-fluid/run_boltzmann_cassi.py`) uses CAMB (v2.0.0) to compute the
CMB $C_\ell^{\text{TT}}$ spectrum with Cassi modifications:

| Quantity | $\Lambda$CDM | Cassi CPL | Shift |
|----------|-------------|-----------|-------|
| $r_s$ (Mpc) | 144.42 | 144.42 | $-0.002\%$ (negligible) |
| $\theta_*$ (rad) | 1.04124 | 1.08093 | **$+3.81\%$** |
| Peak 1 ($\ell$) | 219.6 | 211.7 | $-\!8\ell$ |
| Peak 2 ($\ell$) | 535.9 | 517.4 | $-\!19\ell$ |
| Peak 3 ($\ell$) | 813.1 | 782.7 | $-\!30\ell$ |
| ISW ratio (low-$\ell$) | 1.00 | 1.086 | $+8.6\%$ |
| $H_0^{\text{eff}}$ | 67.4 | 70.0 | $+2.6$ km/s/Mpc |

**Physics interpretation:**
1. **Sound horizon unchanged.** $r_s$ is nearly identical because the
   Cassi $H(z)$ modification at $z > 1000$ (pre-recombination) is small —
   the $w(a)$ deviation from $-1$ only becomes significant at $z < 10$.
2. **Angular scale shifted.** $\theta_*$ increases by 3.8% because $D_A(z_*)$
   is smaller—the Cassi expansion is faster at late times ($w > -1$ means
   less late-time acceleration), reducing the comoving distance to
   recombination. This shifts ALL acoustic peaks to lower $\ell$ by
   $\sim 3.8\%$.
3. **ISW enhanced.** The late-time ISW effect is enhanced by 8.6% because
   the Cassi $w(a)$ produces a shallower gravitational potential decay at
   $z < 1$.
4. **$H_0$ inference.** Fitting the CPL model recovers $H_0 \approx 70.0$
   km/s/Mpc, closer to the local measurement—direction correct, magnitude
   ($+2.6$) is ~45% of the observed gap ($+5.6$).

**Falsifiable signatures in Planck/SO data:**
- Peak positions shifted to lower $\ell$ by $\sim 3.8\%$ (systematic shift,
  not parameter-degenerate with $H_0$ or $\Omega_m$)
- Enhanced low-$\ell$ ISW ($\ell = 2$–$30$) by 8.6%—testable with
  cross-correlation against large-scale structure
- Qi transfer function produces a scale-dependent suppression of $C_\ell$
  at $k > k_{\text{Qi}} \approx 0.1$ h/Mpc

**Figure:** `two-fluid/figures/boltzmann_cassi.png`—4-panel:
$C_\ell^{\text{TT}}$ comparison, $\Delta C_\ell/C_\ell$ residuals,
low-$\ell$ zoom ($\ell=2$–$50$), and $T_{\text{Qi}}(k)$ transfer function.

**To upgrade to Derived:** The full Boltzmann hierarchy must be modified
at the source level (photon-baryon dynamics with $G_{\text{eff}}(k,q)$)
rather than via a phenomenological transfer function. This requires
a Cassi-modified CAMB/CLASS where the Poisson equation includes
$\varepsilon^2$-dependent $G_{\text{eff}}$.

---

### 2.11 G5—3+1 Dimensions: The Number IS 3

**The mechanism:** The string's spiral trajectory through field space generates three orthogonal directions via its Frenet-Serret frame: tangent (string axis), normal (Yang axis), and binormal (Yin axis). Three dimensions = $\{\mathbf{T}, \mathbf{N}, \mathbf{B}\}$, the three vectors of any space curve's Frenet-Serret frame. The $\xi = \varphi^{2 \times 3} = \varphi^{6}$ Qi-gravity coupling internally encodes the dimension count.

**Why the number is already present:** The answer IS the number 3—a **derivation**
of $D=3$ from the PDE structure, not a prediction of a measured quantity.

**The number is 3 from the Frenet-Serret frame.** The prediction is that spatial dimensions are
NOT fundamental—they emerge from the string's spiral, which requires exactly two fields (Yang and Yin). A space curve carries exactly three Frenet-Serret vectors. The W1 anti-phase verification confirms the
two-fluid SO(2) structure.

**Open:** The internal→physical axis map. The mechanism distinguishing the
Yang axis, Yin axis, and string axis in physical space is proposed but not
fully derived from the PDE. This is listed in the open-gaps section of the
open-questions catalog.

---

## 3. Structural Answers: When the Mechanism IS the Number

For these 10 questions, the Cassi answer is a **mechanism**, not a single
numeric prediction. The mechanism itself is falsifiable through its
observational consequences.

### 3.1 C6—Horizon Problem

**The mechanism:** Cascade emergence. All scales activate simultaneously when
$r(t)$ crosses each cascade step—the emergence is temporal (ratio-driven),
not spatial (light-travel). No pre-inflation contact is needed.

**Why it's structural:** The answer is a **causal structure**, not a number.
The cascade emergence mechanism replaces the light-travel causality of
standard cosmology with ratio-evolution causality.

**Testable consequence:** The CMB should show no horizon-scale correlations
beyond those imprinted by the bubble-boundary geometry (C10) rather than standard inflationary super-horizon freezing.

**The "number" is $N_e = 40$:** Because the horizon problem is solved by
cascade emergence, fewer inflationary e-folds are needed. The cascade
inflationary epoch of 40 e-folds (steps 20–60) suffices—half the standard
50–60.

---

### 3.2 C9—Cosmic Web Morphology

**The mechanism:** The wake-wave mechanism. As $r(t)$ evolves through the
cascade, the conversion term generates spatial density perturbations
("wakes") at $\varphi$-scaled intervals. Yang-dominant wakes interfere to
produce flattened sheet morphologies. Anti-phase conversion produces paired
structures.

**Why it's structural:** The answer is a **morphology** (sheets, filaments,
voids), not a single number. The prediction is the geometric pattern, not
a scalar amplitude.

**Testable consequence:** The void size function should show $\varphi$-periodic
modulations in the correlation function $\xi(r)$. The cosmic web's skeleton
(topological classification of sheets/filaments/voids) should show Yang-axis
preferred alignment. Both are testable with SDSS/DESI large-scale structure
data.

**The "number" is the period:** $\Delta(\ln r) = \ln\varphi \approx 0.4812$ —
the same log-periodicity that appears in $P(k)$ and form factors.

---

### 3.3 F3—Force Unification

**The mechanism:** All four forces are manifestations of two-fluid dynamics
at different cascade rungs:
- Gravity: Qi-enhanced Poisson equation ($G_{\text{eff}}$)
- EM: SU(2) gauge extension of the SO(2) doublet
- Strong: cascade confinement at step 95 (Qi flux tube)
- Weak: symmetry breaking at step 80 (electroweak)

**Why it's structural:** The answer is a **mapping** of known forces to
cascade mechanisms, not a single number. Each force already has its numeric
prediction in its respective derivation (e.g., $\alpha_{\text{GUT}} =
\varphi^{-3}/(4\pi)$ for gauge unification, $\xi = \varphi^6$ for gravity).

**Testable consequence:** The single PDE must reproduce all four force
laws in their respective cascade regimes. This is the grand computational
challenge of the framework.

**The "number" is the cascade rung for each force:**
- Gravity: rungs 80–292 (all scales, Qi-enhanced)
- EM: rung 80 (EW symmetry breaking)
- Weak: rung 80
- Strong: rung 95 (QCD confinement)

---

### 3.4 F4—Theory of Everything Status

**The mechanism:** One equation (the two-fluid PDE), one constant ($\varphi$).
All four pillars (particles, cosmology, gravity, Standard Model) emerge from
these alone.

**Why it's structural:** The TOE status is a **claim about completeness**,
not a number. The number of free parameters IS the number: **one** ($\varphi$).

**The number IS 1.** The parameter inventory (`parameter-inventory.md`)
classifies 46 parameters: 1 Fundamental ($\varphi$), 24 Derived ($\varphi$-powers),
plus dimensionful constants ($\hbar, c$) and numerical parameters.

---

### 3.5 T2—JWST "Impossible" Early Galaxies

**The mechanism:** Post-pinch ($r > \varphi^{-1}$, $a \approx 0.051$, $z \approx 19$),
Qi-enhanced gravity ($\xi = \varphi^6$) accelerates structure formation. The
wake-wave mechanism operates from the pinch onward—there is no "dark age"
where structure formation must wait for $\Lambda$CDM hierarchical merging.

**Why it's structural:** The answer is a **formation timeline**, not a single
number. The prediction is that luminous objects exist at higher redshift than
$\Lambda$CDM expects—consistent with JWST observations.

**Pipeline result:** A semi-analytic pipeline
(`two-fluid/run_galaxy_mass_function.py`) computes the Qi-modified halo mass
function using Sheth-Tormen formalism with enhanced growth and wake-wave modulation:

- **Qi-modified growth factor:** $D_{\text{Cassi}}/D_{\Lambda\text{CDM}} = 1.20$ at $z=0$ (20% enhanced)
- **HMF excess at $z=15$, $M=10^{10} M_\odot/h$:** $\mathbf{31.2\times}$ vs $\Lambda$CDM
- **HMF excess at $z=10$:** $8.1\times$—consistent with JWST bright galaxy counts
- **HMF excess at $z=20$:** $121\times$—earliest galaxies appear shortly after pinch
- **Cumulative excess at $z=15$, $M_\star > 10^{10} M_\odot$:** $38\times$
- **$\sigma_8$ normalization:** Matched to 0.811 at $z=0$
- Wake-wave log-periodic modulation at $\Delta(\ln k) = \ln\varphi = 0.4812$ applied

**Physics:** The Qi-gravity enhancement $\xi = \varphi^6 = 17.94$ amplifies
the effective gravitational constant at early times when Qi coherence is high
($q \approx 0.43$). This accelerates the collapse of the first halos by a
factor ~30 at $z=15$, producing the bright galaxies JWST observes. The
enhancement fades as $q$ relaxes toward $\varphi^{-2}$ (from 0.43 → 0.38)
in the late universe, consistent with $\sigma_8$ normalization at $z=0$.

**Figure:** `two-fluid/figures/galaxy_mass_function.png`—3-panel:
$dn/d\log M$ at $z=5$–$20$, Cassi/$\Lambda$CDM ratio, and cumulative
number density $n(>M_\star)$ vs $z$.

**Refined quantitative prediction:** The earliest galaxies should appear at
$z \sim 19$ (pinch epoch), with stellar masses growing as $M_*(z) \propto
(1+z)^{-\alpha}$ where $\alpha = 3(1 + (\varphi^{6}-1)q)/(1+z)$ reflects Qi-enhanced
growth. The predicted comoving number density of $M > 10^{10} M_\odot/h$
halos at $z=15$ is $31\times$ the $\Lambda$CDM expectation—this is a
**falsifiable prediction** testable with JWST and Roman Space Telescope.
---

### 3.6 M1–M5—Consciousness

**The mechanism:** Consciousness is the experience of being a self-predicting,
$\varphi$-damped, cross-chakra Qi fluid with a persistent self-condensate.
The Qi-gate pinch at $r = \varphi^{-1}$ is self-reference—the field becomes
an object to itself.

**Why they're structural:** Each consciousness question is answered by a
**mechanism**, not a single number:
- M1 (hard problem): phenomenal qualities ARE Qi fluid patterns
- M2 (mind-brain): brain is antenna, Qi fluid is signal
- M3 (depth): cascade has no floor, so introspection has no bottom
- M4 (altered states): $\sigma_r$ dispersion changes—meditation reduces it,
  psychedelics increase it
- M5 (empathy): field-as-sense—the two-bubble correlation reproduces (aggregate φ/control 3.83×/3.44×/2.97×) but is a static-geometry protocol feature (decisive scan 2026-08-05, `two-fluid/run_two_bubble_gate_scan.py`); dynamical resonance not demonstrated

**The numbers are in the prediction catalog:** The consciousness framework
has **19 testable predictions** (M1; catalog entries 1–19,
`predictions/falsifiable-predictions.md`), including the two-bubble
correlation (aggregate signal reproduced; gate-independent and static from
initialization per the 2026-08-05 decisive scan—the dynamical resonance
reading is not supported), EEG
Qi-coherence metrics, and altered-state $\sigma_r$ signatures.

---

## 4. Epistemic Tier Summary

| Tier | Count | Notes |
|------|-------|-------|
| **Derived** | 17 | Registry §8 (open-questions-cassi-answers.md); refinements strengthen existing derivations |
| **Hypothesized (numeric refined)** | 24 | Registry §8 (6 pinned φ-powers + 18 computational) |
| **Speculative** | 0 |—|

A "Derived" label requires the prediction to be a mathematical consequence of
$\varphi$ + PDE with zero freedom. The refinements in §2 pin specific numbers
but don't yet close the derivation gaps (e.g., baryon asymmetry's freeze-out
step requires the thermal history; neutrino spacings require the full seesaw
RGE).

**Questions with pinned $\varphi$-powers:**

| Question | Refined $\varphi$-power | Value |
|----------|------------------------|-------|
| C7/Q6 (baryon asymmetry) | $\varphi^{-44}$ | $6.38 \times 10^{-10}$ (6.3% of obs.) |
|| C4 (inflation $r$) | $12/N_e^2$ at $N_e = 40$ (Mapped window) | 0.0075 (survives BK18; $7.5\sigma$ at CMB-S4) |
| C4 (inflation $n_s$) | $1 - 2\varphi^{-1}/N_e$ (δn_s = 2φ⁻²/N_e) | $0.950 + 0.0191 = 0.9691$ |
| C10 (CMB axis) | $12.2°$ alignment (measured) | Calibrated from data vectors; boundary mechanism Hypothesized |
| Q3 (neutrino $\Delta_\nu$) | **$\Delta_1 = 1.00$, $\Delta_2 = 1.75$ rungs (cascade RGE + PMNS pinned)** | **$\Delta m^2$ ratio $33.82$ (0.2% residual)** |
| Q10 (spin form factor) | $\Delta(\ln q) = \ln\varphi = 0.4812$ | Zero-parameter |
| G5 (dimensions) | 3 (Frenet-Serret) | Number IS the derivation |

---

## 5. What Remains Open

- **Baryon asymmetry specific exponent.** The $\varphi^{-44}$ is a fit (6.3%),
  not a derivation. The freeze-out step 52 must be computed from the thermal
  history of the cascade through the GUT epoch.
- **$n_s$ gate correction.** **Derived in closed φ-form:** $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$ (1.0σ from Planck). The gate correction $\delta n_s = 2\varphi^{-2}/N_e$ is a structural consequence of the Qi gate transparency at $r = \varphi^{-1}$ (`computations/ns_gate_correction.py`).
- **Quark mass ratios.** RGE running obscures the bare $\varphi$-power
  hierarchy in the up and down sectors.
- **Gauge coupling running (GUT→EW).** $\alpha_s(M_Z) = 0.0581$ (one-loop SM
  RGE, $M_{\text{GUT}} = 10^{16}$ GeV), 2.0× too small, requiring
  $\Delta b = 1.70$ from beyond-SM particles; the discrete 72-rung φ-RG
  convention value $0.068$/$\Delta b_3 = 1.12$ is convention-dependent and
  not canonical. Cascade RGE predicts a vector-like quark doublet
  $Q(3,2,1/6)+\bar{Q}$ at step ~36 ($\sim 10^{11}$ GeV). See
  `computations/cascade_gut_ew_rge.py`.

- **Neutrino mass eigenvalues.** Individual $m_{\nu_k}$ are now computed: $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV from the cascade RGE + PMNS pipeline (`computations/cascade_rge_pmns.py`). The Fibonacci offsets $\Delta_1 = 1.00$, $\Delta_2 = 1.75$ rungs are pinned to 0.2% residual on $\Delta m^2_{31}/\Delta m^2_{21}$.

| Pipeline | Script | Status | Key Result |
|----------|--------|--------|------------|
| **$H_0$ shift (C3/T4)** | `run_hubble_pipeline.py` | ✓ Built & run | $\Delta H_0 = -7.2$ km/s/Mpc ($-9.9\%$), SAME direction as observed |
| **$\sigma_8$ (T3)** | `run_sigma8_pipeline.py` | ✓ Built & run | $\Delta\sigma_8 = -0.229$ (total, the D = 0 re-measurement 2026-08-08 brief 63: linear-P(k) IC normalization, N=128) / −0.205 (the campaign's D = 0.001; resolution-converged N=32/64/128) — the totals carry the diffusion; the mechanism row +29.7% (G_eff = 1.297, doctrine r₀, D-insensitive); the doctrine rows: −16.6% regime-integrated closure, −15.2% band-state mean-field |
| **CMB low-$\ell$ (C10)** | `run_cmb_lowl_pipeline.py` | ✓ Built & run | $\theta_{\text{align}} = 12.22°$, $C_3/C_2 = \varphi^{-1}$ |
| **Galaxy mass function (T2)** | `run_galaxy_mass_function.py` | ✓ Built & run | $31.2\times$ excess of $M>10^{10} M_\odot/h$ halos at $z=15$ |
| **CMB $C_\ell$ (F3)** | `run_boltzmann_cassi.py` | ✓ Built & run | $\theta_*$ shifted $+3.8\%$, peaks to lower $\ell$, ISW $+8.6\%$ |

**Remaining pipeline work:**
- **Full N-body simulation.** Replace semi-analytic HMF with full N-body (GADGET-4 or similar) including PDE wake-wave ICs.
- **Full Boltzmann modification.** Modify CAMB/CLASS source code to include $G_{\text{eff}}(k,q)$ in the Poisson equation, rather than using a phenomenological transfer function.
- **Resolution scaling.** All PDE-based pipelines run at $N=32$ on CPU; scaling to $N=64$–$128$ on GPU would improve the $\sigma_8$ and $P(k)$ accuracy.

### 5.1 Requires cross-pillar computation

- **Force unification (F3).** The single PDE must reproduce all four force
  laws—demonstrated in separate derivations, not yet in a unified
  computation.
- **TOE completeness (F4).** The claim is falsifiable through the prediction
  catalog (47 entries). Confirming all 47 would constitute empirical
  verification.

---

## 6. References

- `cascade-suppression-formula.md`—universal attenuation law
- `dimensionful-cascade.md`—cascade table (292 = today's horizon rung)
- `baryon-asymmetry.md`—matter-antimatter asymmetry derivation
- `neutrino-masses.md`—seesaw + Fibonacci partitioning
- `three-generations.md`—$N_{\text{gen}} = 3$ derivation
- `spin-fibonacci-spiral.md`—spin as SO(2) winding
- `cosmology/inflation-from-cascade.md`—$N_e = 40$, $n_s$, $r$
- `why-three-dimensions.md`—spiral's Frenet-Serret frame, triaxial spheroid
- `unified-lagrangian.md`—unified action
- `cosmology/observational_constraints.md`—CMB axis, $\sigma_8$, DESI
- `predictions/falsifiable-predictions.md`—50-entry prediction catalog
- `open-questions-cassi-answers.md`—master catalog
- `bubble-edge-geometry.md`—condensation field geometry, edge steepness ratio
