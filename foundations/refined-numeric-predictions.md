# Refined Numeric Predictions for the 19 Hypothesized Questions

## Status: Active derivation (C10 CMB axis: Calibrated angle / Hypothesized mechanism)—August 2026

## Abstract

The open-questions catalog (`open-questions-cassi-answers.md`) classifies 42
physics questions: 7 Derived, 4 Calibrated, 11 Mapped, 19 Hypothesized, 1
Speculative. Each of the 19
Hypothesized questions has a proposed Cassi mechanism and a testable prediction.
This document refines the **specific numeric predictions** for every question
that admits a cascade-span derivation ($\varphi^{-N}$), and tightens the
mechanistic argument for those whose answer is structural rather than numeric.

The cascade suppression formula (`cascade-suppression-formula.md`) is a
conditional attenuation tool for a declared source rung $m$ and target rung
$n$ under the uniform per-rung input
$d_i^{\mathrm{signal}}\equiv\varphi^{-1}$. Its signal-map interpretation is
Hypothesized; conditional on that input and map, the product algebra is Derived:

$$\text{Conditional product} = \text{Seed} \times \varphi^{-(n-m)}$$

in the signal-propagation regime, or
$\mathcal{D}_{0\to n}^{\mathrm{coherence}}=\varphi^{-n(n+1)/2-\delta(n+1)}$
in the coherence regime for the declared profile
$q_i^{\mathrm{cascade}}=1-\varphi^{-i-\delta}$, $i=0,\ldots,n$. The
rung-indexed $q_i^{\mathrm{cascade}}$ is an auxiliary attenuation profile,
distinct from the canonical local scalar $q$. The $\delta=3$ value is
conditional on the declared $\sigma=\ell_{\mathrm{Pl}}/\varphi^3$
noise-signal input. Where this conditional model applies, one pins the
integer exponent and computes the exact $\varphi$-power. Where the result is a
mechanism, morphology, or status, the document records the proposed mechanism,
its epistemic tier, and the verification needed.

---

## 1. Classification: Cascade-Span vs Structural

Of the registry's 19 Hypothesized questions, 7 admit a cascade-span numeric
refinement (either a specific $\varphi$-power or a number already present in
the derivation), 10 are structural or conditional answers, and the remaining 2
(BH information, $P_\parallel(n)$) are not refined here. Entries now sitting
at Mapped or Calibrated are carried for their refined numbers:

| # | Question | Type | Existing Number | Refinement |
|---|----------|------|----------------|------------|
| C3 | Hubble tension | Cascade-span (needs $w(a)$ pipeline) | $w_0=-0.87$ (2σ) | $\Delta H_0$ from $w(z)$ integration |
| C4 | Inflation | Cascade-span (numbers present) | $n_s=0.9691$, $r = 12/N_e^2 = 0.0075$ ($N_e = 40$ Mapped) | $n_s$ correction form; $r$ is the closed form at the window, not a $\varphi$-power |
| C6 | Horizon problem | **Structural / Hypothesized** |—| Cascade emergence mechanism |
| C7 | Baryon asymmetry | **Mapped exponent / Hypothesized chain** | $\eta\approx\varphi^{-44}$ (Mapped fit) | $6.38\times 10^{-10}$; organized annihilation, Sakharov closure, and endpoint remain Hypothesized/open |
| C9 | Cosmic web | **Structural / Hypothesized** |—| Wake-wave interference morphology |
| C10 | CMB axis | Cascade-span (geometric) | Axis at $(l,b)=(260°,+60°)$ | Alignment angle $12.2°$ (measured; calibrated from data vectors), boundary mechanism Hypothesized |
| Q3 | Neutrino masses | **Mapped cascade-span fit** | $m_3 \approx 0.050$ eV (computed spectrum) | Specific $\Delta_{\nu,k}$ offsets selected in the pipeline |
| Q5 | Three generations | **Conditional Fibonacci count** | $N_{\text{gen}}=3$ under propagation-channel postulate | Mass ratios per sector; canonical PDE does not select the count |
| Q6 | Matter asymmetry | **Mapped exponent / Hypothesized chain** | $\eta\approx\varphi^{-44}$ (same fit as C7) | Same refinement as C7 |
| Q7 | Measurement | **Optional conditional sector** | $P=|\alpha|^2$ under declared detector inputs | Born mapping **Hypothesized/open**; canonical $q$ is a local coherence scalar, not a branch-intensity rule |
| Q10 | Spin | **Optional Hypothesized extension** | $s\in\{0,\frac12,1,2\}$ conditional on compact phase | Form-factor period $\Delta(\ln q)=\ln\varphi$; compact phase/half-angle construction remains open |
| G5 | 3+1 dimensions | **Conditional embedding algebra** | Frenet-Serret triad in selected $d=3$ embedding | Physical $d=3$ selection and SO(2) interpretation Hypothesized/open |
| F3 | Force unification | **Structural / optional sectors** |—| Candidate force-sector map; no unified derivation from the canonical PDE |
| F4 | Theory of Everything | **Structural / optional extension** |—| Extended action proposal; completeness and one-equation TOE remain open |
| F5 | Dimensionful constants | Cascade-span (numbers present) | $\lambda=0.1$ (asserted solver convention; $\lambda=1/(2w)$ at $w=5$—Hypothesized linkage), $N=291.54$ (epoch-dependent) | $c$, $\hbar$, $G$ external; $c = \lambda\ell_{\text{Pl}}/\tau_{\mathrm{PDE}}$ structure conditional on the solver convention, with $\tau_{\mathrm{PDE}}$ the calibrated PDE-to-physical-time conversion |
| T1 | DESI $w_0/w_a$ | Cascade-span (numbers present) | $w_0=-0.87$, $w_a=+0.012$ (baseline); with the ratified coupling: $w_a=-0.38$ (B2, unstable) / **pure-Λ $(-1, 0)$ window (stable realization—10/12)** | CPL $w(z)$ fit; 2σ / 2.7σ baseline → 3.6σ ($w_0$, fixed $r_0$, B2) / 1.25σ ($w_a$, B2, unstable); 4.17σ/2.61σ (stable realization—12) |
| T2 | JWST galaxies | **Structural / Hypothesized** |—| Wake-wave formation timeline |
| T3 | $\sigma_8$ tension | **Cascade-span / Hypothesized** | $\xi=\varphi^6$ | $G_{\text{eff}}(k,q)$ integration |
| T4 | $H_0$ tension | Same as C3 |—| Same refinement as C3 |
| M1 | Hard problem | **Structural / Hypothesized** |—| Qi-gate pinch = self-reference |
| M2 | Mind-brain | **Structural / Hypothesized** |—| Field-as-antenna mechanism |
| M3 | Depth of mind | **Structural / Hypothesized** |—| Cascade has no floor |
| M4 | Altered states | **Structural / Hypothesized** |—| $\sigma_r$ dispersion |
| M5 | Empathy/coupling | **Structural / Hypothesized** |—| Two-bubble $\varphi$-resonance |

---

## 2. Numeric Refinements

### 2.1 C7/Q6—Baryon/Matter Asymmetry: $\eta \approx \varphi^{-44}$

**Current status:** `foundations/baryon-asymmetry.md` records a
Hypothesized candidate chain. Organized annihilation and the Sakharov closure
remain Hypothesized and depend on the declared branch/anti-phase assignment.
The CP candidate is also Hypothesized; the out-of-equilibrium condition and its
freeze-out endpoint are open. The observed ratio is represented by the Mapped
fit $\varphi^{-44}$.

**Mapped numerical fit:** The integer exponent closest to the observed
$\eta_{\text{obs}} = 6.0 \times 10^{-10}$ is:

$$\boxed{\eta \approx \varphi^{-44} \approx 6.38 \times 10^{-10}}$$

within 6.3% of the observed value.

| Exponent $k$ | $\varphi^{-k}$ | Ratio to observed |
|:---:|:---|:---:|
| 43 | $1.03 \times 10^{-9}$ | 1.72× |
| **44** | **$\mathbf{6.38 \times 10^{-10}}$** | **1.06×** |
| 45 | $3.94 \times 10^{-10}$ | 0.66× |
| 46 | $2.44 \times 10^{-10}$ | 0.41× |

The cascade span $N=44$ is the ledgered Mapped fit (nearest-integer
$\varphi$-power to the observed $\eta$; `parameter-inventory.md` §10).
With the corrected GUT anchor $n\approx13.3$, the candidate pinch at
$n=60$ gives a seed-to-pinch span
$$
60-13.3=46.7.
$$
Under uniform $\varphi^{-1}$-per-rung attenuation this candidate gives
$\eta=\varphi^{-46.7}\approx1.8\times10^{-10}$, 3.4 times below the
observed value. The observed ratio requires
$$
N_{\mathrm{req}}=-\frac{\ln(\eta_{\mathrm{obs}})}{\ln\varphi}
\approx44.126.
$$
An endpoint near $n\approx57.43$ for the rounded seed, or
$n\approx57.46$ for the closure seed $n=13.33$, would supply that span,
but no known scale or mechanism selects it. No freeze-out step is set or
derived (`foundations/baryon-asymmetry.md` §4.4).

**Meaning of the Mapped exponent:** The baryon-asymmetry entry represents
$N_{\mathrm{eff}}=44$ as a Mapped fit to the observed dilution. It is a
ledgered exponent, not a selected freeze-out endpoint. The
seed-to-pinch value $46.7$ is the closest mechanism-anchored candidate,
whereas the required $44.126$-rung endpoint remains open.

The physical interpretation therefore remains Hypothesized: organized
annihilation, CP violation, out-of-equilibrium evolution, and photon dilution
form a proposed chain whose thermal endpoint has not been dynamically selected.
The $\varphi^{-44}$ value parameterizes the observed dilution within that
Mapped ledger entry.

**Open closure:** A thermal history connecting the Qi gate and sphaleron rate
to a dynamically selected endpoint is required before the Mapped exponent can
be connected to a freeze-out calculation.

---

### 2.2 Q3—Neutrino Mass Spacings: Fibonacci Ratios over the Compressed Span

**Current status:** `foundations/neutrino-masses.md` records a computed overall
scale and a conditional three-channel Fibonacci construction:
- Overall scale: $m_3 = 0.0502$ eV (computed spectrum,
  `computations/cascade_rge_pmns.py`)
- Three mass eigenstates under the Fibonacci triple-clustering postulate
- Normal ordering ($m_{\nu_1} < m_{\nu_2} < m_{\nu_3}$)
- Compressed $\varphi$-power spacing with the seesaw Yukawa-squared
  structure ($y_\nu^2$ gives a factor-of-2 exponent amplification)

The uniform-spacing hypothesis ($\Delta_\nu = 2$ rungs per step in mass
exponent, giving $m_{\nu_2}/m_{\nu_1} = m_{\nu_3}/m_{\nu_2} \approx \varphi^2
\approx 2.6$) is falsified by the observed $\Delta m^2_{31}/\Delta m^2_{21}
\approx 33$—the data require a steeper hierarchy than uniform $\varphi^2$
spacing.

**Refined Mapped fit: Non-uniform Fibonacci partitioning with $y_\nu^2$
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
cascade RGE + PMNS computation (`computations/cascade_rge_pmns.py`) selects the
ledgered offsets $\Delta_1 = 1.00$ rung and $\Delta_2 = 1.75$ rungs; these
are pipeline selections rather than an independent derivation.

The anomalous dimension extracted from the compression factor is
$\gamma_\nu \approx 0.37 \approx \varphi^{-2}$, consistent with the spectral
gap reading; it does not by itself establish the $\varphi$-RG fixed point.

**Specific prediction retained:**
- $m_{\nu_1} = 0.00356$ eV (from $\Delta m^2_{21}$ constraint)
- $m_{\nu_2} = 0.00931$ eV, $m_{\nu_3} = 0.05019$ eV
- $\Sigma m_\nu = 0.0631$ eV (well below cosmological bound $<0.12$ eV)
- $|m_{\beta\beta}| = 0.0043$–$0.0052$ eV (δ_CP-dependent)
- Normal ordering, no sterile neutrinos
- **$\Delta m^2_{31}/\Delta m^2_{21} \approx 33.82$ (0.2% residual)** —
  the Fibonacci offsets are **selected in the Mapped pipeline**, not independently derived.

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

**Current status:** The inflation sources
(`cosmology/cosmology-from-phi.md` §2.3; `cosmology/inflation-from-cascade.md`)
record:
- $N_e = 40$ e-folds (cascade steps 20–60; Mapped start-threshold window—ledger §10 row 501)
- $n_s = 0.9691$ from the closed form $1 - 2\varphi^{-1}/N_e$, conditional on that window
- $r = 12/N_e^2 = 0.0075$ at $N_e = 40$, conditional on that window
- $\alpha_s = -0.0013$

The algebraic forms are exact once the Mapped window is supplied. The
$n_s$ gate-transparency interpretation
$\delta n_s=2\varphi^{-2}/N_e$ remains asserted rather than a consequence of
the canonical trajectory; $r$ is the closed form at the window, not a
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

**Status of the algebra:** The closed form is exact conditional on the Mapped
window $N_e=40$. The interpretation of the $\varphi^{-2}$ factor as a
gate-transparency effect remains asserted and is not reproduced by the
trajectory.

**Assessment:** The result $0.9691$ sits $+0.0042$ above the Planck
central value—$1.0\sigma$, within the gate closure-width systematic. The
$\delta n_s = 2\varphi^{-2}/N_e$ form is algebraically equivalent to the
closed form, but the gate-transparency origin of the $\varphi^{-2}$ factor is
asserted, not reproduced by the trajectory (`computations/slow_roll_trajectory.py`,
2026-08-06: $(0.813, 0.188)$ under 1 step = 1 e-fold, $(0.914, 0.060)$ at
$N_e = 40$ literal). The "1.0σ" standing is for the closed form with the
Mapped window, not for a derived gate mechanism.

---

### 2.5 Q7—Measurement: conditional Born statistics and open branch mapping

**Current status:** The quantum measurement source
(`foundations/quantum-measurement-derivation.md`) records a single-rung
coherence-budget mechanism. Organized perturbation has
$\mathcal{M}\approx1$, while random environmental perturbation has
$\mathcal{M}\approx0$. Its coherent-field counting algebra is conditional on
a linear quantum sector, a coherent detector mode, gate-mediated first
absorption, and an apparatus-selected outcome basis. The physical Born mapping
and the basis selector remain Hypothesized/open.

The canonical solver state is the real-density pair $E_Y,E_I$ with
$q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$. This $q$ is a local
coherence scalar. It does not define a branch probability and has no exact
proportionality to $|\psi|^2$.

**Conditional detector calculation:** In the added linear quantum sector, let
the detector mode be a coherent state with amplitude
$A(x)=g\psi(x)$. Poisson counting gives
$$
P(n)=\frac{e^{-\lambda(x)}\lambda(x)^n}{n!},\qquad
\lambda(x)=g^2|\psi(x)|^2.
$$
For independent channels, the first-absorption relative rate is
$$
\boxed{P(x)=\frac{\lambda(x)}{\sum_{x'}\lambda(x')}
=\frac{|\psi(x)|^2}{\sum_{x'}|\psi(x')|^2}}.
$$
When detector channels resolve two branches, this reduces to
$$
\boxed{P(\alpha)=\frac{|\alpha|^2}{|\alpha|^2+|\beta|^2}}.
$$
These equations are the conditional coherent-field statistics. The
branch-to-detector identification, phase matching, and outcome-basis choice
are optional sector inputs, so the physical Born mapping remains
Hypothesized/open.

**Open closure:** A complete measurement account must specify which
apparatus-sector construction selects the outcome basis and when
$\mathcal{M}\approx1$ holds for a general interaction. The canonical $q$
diagnostic supplies no such branch or axis selector.

---

### 2.6 Q5—Three Generations: Mass Ratios Per Sector

**Current status:** $N_{\text{gen}} = 3$ is a Mapped structural count under
the Fibonacci decomposition plus the direct-rung propagation-channel postulate:
the recurrence has two predecessor channels and the postulate adds the direct
rung, $2+1=3$. The Fibonacci triple-clustering
$\{n,n-1,n-2\}$ therefore supplies three mass eigenstates within that
conditional construction; the canonical density PDE does not independently
select the generation count.

**Refined predictions per sector:**

| Sector | Span $N$ | $\Delta_1$ | $\Delta_2$ | $m_2/m_1$ (pred) | $m_2/m_1$ (obs) | $m_3/m_2$ (pred) | $m_3/m_2$ (obs) |
|--------|----------|------------|------------|-------------------|------------------|-------------------|------------------|
| Charged leptons | $\sim 72$ | 11 | 6 | $\varphi^{11} \approx 199$ | 207 | $\varphi^6 \approx 18$ | 17 |
| Up-type quarks | $\sim 72$ | 7 | 8 | $\varphi^7 \approx 17$ | 580 | $\varphi^8 \approx 28$ | 136 |
| Down-type quarks | $\sim 72$ | 5 | 5 | $\varphi^5 \approx 11$ | 20 | $\varphi^5 \approx 11$ | 44 |
| Neutrinos | $\sim 12$ | $1.00$ | $1.75$ | $\varphi^{2.00} \approx 2.618$ | $\sim 4.5$ | $\varphi^{3.50} \approx 5.39$ | $\sim 6$ |

**Charged leptons** show the cleanest $\varphi$-power pattern (within 10%).
**Quark sectors** show significant deviations, attributable to RGE running
and CKM mixing between the GUT and EW scales. **Neutrinos** include the
seesaw $y_\nu^2$ amplification factor. The selected Mapped offsets give
$\Delta m^2_{31}/\Delta m^2_{21}\approx33.82$, consistent with the observed
$\sim33.89$ at 0.2% residual; the PMNS conversion is part of the pipeline
described in §2.2.

The conditional construction assigns $N_{\text{gen}}=3$. The sector mass
ratios are not uniform predictions: charged leptons are the closest match,
quarks retain substantial deviations, and the neutrino residual carries the
Mapped pipeline status.

---

### 2.7 Q10—Spin: optional compact-phase and half-angle extension

**Current status:** The canonical solver evolves real densities $E_Y,E_I$
and the associated local coherence scalar $q$. It supplies neither a
compact phase coordinate, a fixed per-rung angular advance, a complex
amplitude, nor a half-angle spinor. The construction in
`foundations/spin-fibonacci-spiral.md` is an optional Hypothesized extension.

**Conditional construction:** If an added compact coordinate $\chi$ is
assigned a Fibonacci pitch and a half-angle lift is declared, then a winding
span can be mapped as
$$
s=\frac{\Delta n}{2},\qquad
\Delta n\in\{1,2,4\}\Longrightarrow s\in\{\tfrac12,1,2\},
$$
with $s=\tfrac32$ treated as a composite assignment. This mapping is not a
canonical spin derivation, and the physical interpretation of the internal
coordinate remains Hypothesized/open.

**Conditional testable prediction:** Particle form factors may carry
log-periodic oscillations at the same period as the cosmological $P(k)$:

$$\boxed{F(q^2) \supset A \cdot \cos\!\left(2\pi \cdot \frac{\ln(q/\Lambda_{\text{QCD}})}{\ln\varphi} + \delta\right)}$$

The conditional period is $\Delta(\ln q)=\ln\varphi\approx0.4812$. The
amplitude $A$, phase $\delta$, detector range, and background treatment
remain additional fit or analysis inputs; this is not a zero-parameter
prediction.

---

### 2.8 C3/T4—Hubble Tension: $\Delta H_0$ from $w(z)$ Pipeline

**Current status:** C3/T4 remains a **Hypothesized** resolution mechanism with a
Calibrated $w_0=-0.87$ input. The ODE pipeline produces a conditional
$H_0$ bias when its high-redshift $w(a)$ continuation is used; the full
simultaneous fit does not resolve the tension, and the early-time extrapolation
requires a radiation-inclusive closure.

**The prediction is a function, not a single number.**

**Pipeline result:** A computational pipeline
(`two-fluid/run_hubble_pipeline.py`) uses the analytic ODE approach
(same as `calibrate_initial_ratio.py`) to compute the full $w(a) \to H(z)$
evolution and the CMB-inferred $H_0$ bias:

- **$w_0 = -0.87$** (ODE output across the stated
  $r_0 \in [0.001, 0.08]$ scan; $w_0$ remains Calibrated rather than
  structurally derived; $-0.868$ to $-0.872$ across the scan; $2\sigma$ from
  DESI $w_0 \approx -0.75 \pm 0.06$ [INFERENCE])
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
probes. The candidate Qi-gravity mechanism is **Hypothesized**:
$\xi=\varphi^6\approx17.944$ is used to make $G_{\text{eff}}$
density-dependent, with reduced growth in low-density regions as the proposed
effect. The $\mu(k,a)$ normalization is a separate **Mapped** ledger entry.

**Pipeline result:** A computational pipeline
(`two-fluid/run_sigma8_pipeline.py`) runs a short PDE simulation with
Eisenstein-Hu ICs, extracts the Qi coherence field $q(x)$, and computes
the Qi-modified power spectrum and $\sigma_8$:

- **$q_{\text{ref}}$ (initial) = $0.300$**, **$q_{\text{final}}$ = $0.405$** (N = 128, operational $r_0 = 1/23$, truth campaign 2026-08-07)
- **$G_{\text{eff}}/G_N$ (final) = $8.27$** (absolute Qi enhancement with $\xi = 17.94$)
- **$G_{\text{eff}}/G_{\text{ref}} = 1.297$**—the mechanism-attributable row **+29.7%** (the deep-Yin window's q rises 0.30 → 0.41; selected $r_0 = 0.0472$, N=128; D-insensitive: Δμ = 0.02 pp across D ∈ {0, 0.001})
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
r₀-dependent: +29.4% at the selected $r_0 = 0.0472$; D-insensitive:
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

### 2.11 G5—3+1 Dimensions: conditional Frenet–Serret algebra

**Current status:** The canonical state is the real-density pair
$E_Y,E_I$, with no ambient spatial dimension selected by the PDE. The
geometric source (`foundations/why-three-dimensions.md`) prescribes a
logarithmic spiral in an added coordinate $\chi$ and then tests a
non-degenerate embedding in $\mathbb{R}^3$. Its Frenet–Serret triad is a
conditional consistency map for that embedding; it does not select the
dimension of space.

**Conditional algebra:** For the selected regular curve in $\mathbb{R}^3$,
$$
\{\mathbf T,\mathbf N,\mathbf B\}
\longmapsto\{\text{string},\text{Yang},\text{Yin}\},
\qquad \mathbf B=\mathbf T\times\mathbf N.
$$
The fixed-point relation
$\xi=\varphi^6=(\pi/\rho)^{-2}$ contains the algebraic exponent
$3\times2$; the ambient identification $d=3$ is a separate
Hypothesized mapping. The canonical density-plane angle is monotonic and does
not supply a periodic phase clock. Compact phase, SO(2)/$U(1)$ interpretation,
and any half-angle lift are optional Hypothesized additions.

**Open:** The internal-to-physical axis map and physical $d=3$ selection
remain open. The W1 anti-phase result supports the paired-wake morphology
branch, not a dimensional or SO(2) derivation.

---

## 3. Structural Answers and Conditional Mechanisms

For these registry entries, the Cassi answer is a mechanism, morphology,
conditional sector, or status rather than a single numeric prediction. Each
entry carries its epistemic tier and the observations that could test it.

### 3.1 C6—Horizon Problem

**Current status:** **Hypothesized** cascade-emergence proposal. The candidate
mechanism treats scale activation as temporal (ratio-driven) when $r(t)$
crosses cascade steps, rather than as spatial light-travel contact. It remains
an unselected causal interpretation of the horizon problem.

**Why it's structural:** The proposal concerns a causal structure, not a
single number. It does not by itself establish the absence of standard
inflationary super-horizon correlations.

**Testable consequence:** The cascade interpretation predicts a CMB signature
that differs from standard inflationary super-horizon freezing; the
bubble-boundary geometry (C10) supplies the current candidate imprint.

**Related numeric input:** $N_e=40$ is a Mapped start-threshold window
carried from the inflation entry. It is a model input for the cascade scenario,
not an independently selected solution of the horizon problem.

---

### 3.2 C9—Cosmic Web Morphology

**Current status:** **Hypothesized** wake-wave morphology. As $r(t)$ evolves
through the cascade, the conversion term is proposed to generate spatial
density perturbations ("wakes") at $\varphi$-scaled intervals. Yang-dominant
wakes and anti-phase conversion are candidate sources of flattened sheets and
paired structures.

**Why it's structural:** The proposed answer is a morphology (sheets,
filaments, voids), not a single number. The test concerns the geometric
pattern rather than a scalar amplitude.

**Testable consequence:** The void size function could show
$\varphi$-periodic modulations in the correlation function $\xi(r)$. The
cosmic-web skeleton (topological classification of sheets/filaments/voids)
could show Yang-axis preferred alignment. Both remain tests against
SDSS/DESI large-scale-structure data.

**Conditional period:** $\Delta(\ln r)=\ln\varphi\approx0.4812$, matching
the period used in the candidate $P(k)$ and form-factor analyses.

---

### 3.3 F3—Force Unification

**Current status:** The canonical two-fluid PDE supplies the real-density
dynamics, shared advection, gated conversion, and the local $q$ diagnostic.
Candidate gravity, gauge, strong, and weak descriptions are optional or
conditional sectors mapped onto that core:
- Gravity: Qi-enhanced Poisson equation ($G_{\text{eff}}$), conditional on the
  gravitational extension
- EM: optional gauge extension of the internal doublet
- Strong: candidate cascade confinement at step 95 (Qi flux tube)
- Weak: candidate symmetry breaking at step 80 (electroweak)

The sector placements and the numerical receipts
$\alpha_{\text{GUT}}=\varphi^{-3}/(4\pi)$ and $\xi=\varphi^6$ retain their
individual Mapped or Calibrated statuses. They do not establish that all four
force laws follow from the canonical PDE or from one common derivation.

**Open computation:** A cross-sector calculation must couple the optional
extensions, reproduce the relevant force observables in their stated regimes,
and pass independent tests. No such unified computation is recorded here.

**Conditional rung placements:**
- Gravity: rungs 80–292 (all scales, Qi-enhanced candidate)
- EM: rung 80 (EW symmetry-breaking candidate)
- Weak: rung 80
- Strong: rung 95 (QCD-confinement candidate)

---

### 3.4 F4—Theory of Everything Status

**Current status:** `foundations/unified-lagrangian.md` records a
Hypothesized extended action organized around the canonical two-fluid core and
$\varphi$. The action lists optional particle, cosmology, gravity, and gauge
sectors; those sectors do not by themselves establish a complete one-equation
theory.

The parameter inventory records 46 parameters in the cited accounting,
including one Fundamental $\varphi$, 24 Derived $\varphi$-power rows, and
dimensionful constants such as $\hbar$ and $c$, alongside numerical and
initial-condition inputs. This accounting is not a claim that the canonical
PDE has one free parameter.

**Open criterion:** A TOE claim would require a single coupled derivation,
well-defined sector limits, and independent cross-pillar tests. Completeness
remains Hypothesized/open.

---

### 3.5 T2—JWST "Impossible" Early Galaxies

**Current status:** **Hypothesized** post-pinch formation mechanism. The
candidate model places the wake-wave and Qi-gravity extensions at
$r>\varphi^{-1}$, $a\approx0.051$, $z\approx19$; it does not establish
that an actual dark-age interval is absent.

**Why it's structural:** The answer is a formation timeline rather than a
single number. The quantitative trajectory remains conditional on the
semi-analytic model and its input sectors.

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

**Physics within the candidate model:** The Qi-gravity extension uses
$\xi=\varphi^6=17.94$ and high coherence ($q\approx0.43$) to amplify the
effective gravitational constant. In that model this accelerates first-halo
collapse by a factor of about 30 at $z=15$; the late-time normalization and
the relation to observed JWST counts remain empirical checks, not a derived
formation history.

**Figure:** `two-fluid/figures/galaxy_mass_function.png`—3-panel:
$dn/d\log M$ at $z=5$–$20$, Cassi/$\Lambda$CDM ratio, and cumulative
number density $n(>M_\star)$ vs $z$.

**Refined conditional pipeline output:** The semi-analytic model places the
earliest galaxies near $z\sim19$ (pinch epoch), with stellar masses growing
as $M_*(z)\propto(1+z)^{-\alpha}$, where
$\alpha=3(1+(\varphi^6-1)q)/(1+z)$ in the model. Its predicted comoving
number density of $M>10^{10}M_\odot/h$ halos at $z=15$ is $31\times$ the
$\Lambda$CDM expectation; this is a conditional falsifiable output for JWST
and Roman observations.
---

### 3.6 M1–M5—Consciousness

**Status:** **Hypothesized** mechanism-level mappings. The consciousness
catalog supplies candidate observables; the decisive two-bubble scan records a
static-geometry protocol feature rather than demonstrated dynamical resonance.
**Candidate mappings:** Consciousness questions are represented by
mechanism-level proposals rather than scalar predictions:
- M1 (hard problem): phenomenal qualities as Qi-fluid patterns
- M2 (mind-brain): brain as antenna, Qi fluid as signal
- M3 (depth): cascade without a floor, so introspection has no bottom
- M4 (altered states): $\sigma_r$ dispersion changes—meditation reduces it,
  psychedelics increase it
- M5 (empathy): field-as-sense; the two-bubble correlation reproduces the
  aggregate $\varphi$/control values 3.83×/3.44×/2.97×, but the decisive scan
  identifies a static-geometry protocol feature rather than demonstrated
  dynamical resonance

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
| **Derived** | 7 | Registry §8 (open-questions-cassi-answers.md); refinements strengthen existing derivations |
| **Calibrated** | 4 | Registry §8 (CMB axis direction C10, dark energy $w_0$ C1, dark matter $\xi$ pin C2, DESI $w_0$/$w_a$ T1) |
| **Mapped** | 11 | Registry §8 (ledgered placements/exponents: inflation C4, baryon asymmetry C7/Q6, hierarchy Q1, strong CP Q2, neutrino offsets Q3, gauge unification Q4, proton-lifetime exponent Q9, galaxy rotation G4, fine-tuning F1, dimensionful-constant exponents F5) |
| **Hypothesized (conditional refinements)** | 19 | Registry §8; §2 records conditional algebra and numerical receipts without changing the registry tier |
| **Speculative** | 1 | golden balance as driven structure (M6) |

A "Derived" label requires the prediction to be a mathematical consequence of
$\varphi$ + PDE with zero freedom. The refinements in §2 record specific
numbers and conditional formulas but do not close the remaining derivation gaps,
including the baryon asymmetry's freeze-out endpoint and the neutrino sector's
full seesaw RGE.

**Questions with recorded $\varphi$-powers or conditional values:**

| Question | Refined $\varphi$-power or conditional value | Status / receipt |
|----------|-----------------------------------------------|------------------|
| C7/Q6 (baryon asymmetry) | $\varphi^{-44}$ | Mapped fit; $6.38 \times 10^{-10}$ (6.3% of obs.); freeze-out endpoint open |
| C4 (inflation $r$) | $12/N_e^2$ at $N_e = 40$ (Mapped window) | 0.0075 (survives BK18; $7.5\sigma$ at CMB-S4) |
| C4 (inflation $n_s$) | $1 - 2\varphi^{-1}/N_e$ (δn_s = 2φ⁻²/N_e) | $0.950 + 0.0191 = 0.9691$; exact conditional on Mapped $N_e$ window |
| C10 (CMB axis) | $12.2°$ alignment (measured) | Calibrated from data vectors; boundary mechanism Hypothesized |
| Q3 (neutrino $\Delta_\nu$) | **$\Delta_1 = 1.00$, $\Delta_2 = 1.75$ rungs (Mapped pipeline selections)** | **$\Delta m^2$ ratio $33.82$ (0.2% residual)** |
| Q10 (spin form factor) | $\Delta(\ln q) = \ln\varphi = 0.4812$ | Optional Hypothesized compact-phase extension; fit inputs remain |
| G5 (dimensions) | 3 in selected $\mathbb{R}^3$ embedding | Conditional Frenet–Serret algebra; physical $d=3$/SO(2) map Hypothesized |

---

## 5. What Remains Open

- **Baryon asymmetry specific exponent.** The $\varphi^{-44}$ is a Mapped fit
  (6.3%), not a derivation. No freeze-out step is set or derived; a thermal
  history through the GUT epoch is required to test whether a dynamically
  selected endpoint can reproduce $N_{\mathrm{eff}}=44$.
- **$n_s$ gate correction.** The closed form
  $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$ is exact conditional on the
  Mapped $N_e=40$ window (1.0σ from Planck). The gate-transparency origin of
  $\delta n_s = 2\varphi^{-2}/N_e$ remains Hypothesized and is not reproduced
  by the trajectory (`computations/ns_gate_correction.py`).
- **Quark mass ratios.** RGE running obscures the bare $\varphi$-power
  hierarchy in the up and down sectors.
- **Gauge coupling running (GUT→EW).** $\alpha_s(M_Z) = 0.0581$ (one-loop SM
  RGE, $M_{\text{GUT}} = 10^{16}$ GeV), 2.0× too small, requiring
  $\Delta b = 1.70$ from beyond-SM particles; the discrete 72-rung φ-RG
  convention value $0.068$/$\Delta b_3 = 1.12$ is convention-dependent and
  not canonical. Cascade RGE predicts a vector-like quark doublet
  $Q(3,2,1/6)+\bar{Q}$ at step ~36 ($\sim 10^{11}$ GeV). See
  `computations/cascade_gut_ew_rge.py`.

- **Neutrino mass eigenvalues.** Individual $m_{\nu_k}$ are computed:
  $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV from the
  cascade RGE + PMNS pipeline (`computations/cascade_rge_pmns.py`). The
  Fibonacci offsets $\Delta_1 = 1.00$, $\Delta_2 = 1.75$ rungs are selected
  Mapped pipeline values with a 0.2% residual on
  $\Delta m^2_{31}/\Delta m^2_{21}$.

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

- **Force-sector integration (F3).** Candidate gravity, gauge, strong, and weak
  sectors remain optional or conditional. Their separate numerical receipts do
  not establish all four force laws from the canonical PDE; a coupled
  cross-sector computation remains open.
- **TOE completeness (F4).** The optional extended action and prediction
  catalog do not establish a one-equation theory or completeness. Independent
  cross-pillar derivations and tests remain open.

---

## 6. References

- `cascade-suppression-formula.md`—universal attenuation law
- `dimensionful-cascade.md`—cascade table (292 = today's horizon rung)
- `baryon-asymmetry.md`—matter-antimatter candidate and Mapped exponent
- `neutrino-masses.md`—seesaw + conditional Fibonacci partitioning
- `three-generations.md`—conditional $N_{\text{gen}} = 3$ construction
- `spin-fibonacci-spiral.md`—optional compact-phase/half-angle extension
- `cosmology/inflation-from-cascade.md`—$N_e = 40$, $n_s$, $r$
- `why-three-dimensions.md`—conditional $\mathbb{R}^3$ Frenet-Serret map
- `unified-lagrangian.md`—optional extended action and sector statuses
- `cosmology/observational_constraints.md`—CMB axis, $\sigma_8$, DESI
- `predictions/falsifiable-predictions.md`—54-entry prediction catalog
- `open-questions-cassi-answers.md`—master catalog
- `bubble-edge-geometry.md`—condensation field geometry, edge steepness ratio
