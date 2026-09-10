# Neutrino Masses from Fibonacci Cascade Partitioning of the Seesaw

## Status: Hypothesized mechanism / Mapped offsets / Calibrated resolved-flavour two-singlet leptogenesis comparison / Tested rank and CP-selection boundary—September 2026

## Abstract

Neutrino masses use the same Fibonacci triple-clustering that gives three
generations of charged fermions (`foundations/three-generations.md`), applied
to a selected **12-rung coordinate span** from the fit-start coordinate $n=8$
to the seesaw scale at $n=20$. The physical ladder anchor for the GUT scale is
$n_{\text{GUT}} \approx 13.3$, so the dimensional interval to the seesaw is
about seven rungs; the 12-rung span is a mapped convention used by the offset
fit. The coordinate span compresses the Fibonacci sub-rung spacing by a factor
of $\approx 6$ relative to the charged-lepton construction, giving a compact
description of the sub-eV spectrum. The three mass eigenstates follow
$\varphi$-power spacing amplified by the seesaw's Yukawa-squared structure:

$$\frac{m_{\nu_2}}{m_{\nu_1}} \approx \varphi^{2\Delta_1}, \qquad \frac{m_{\nu_3}}{m_{\nu_2}} \approx \varphi^{2\Delta_2}$$

where $\Delta_1$ and $\Delta_2$ are the cascade-span offsets between
Fibonacci sub-rungs. The observed oscillation data ($\Delta m^2_{21} \approx
7.5 \times 10^{-5}\ \text{eV}^2$, $\Delta m^2_{31} \approx 2.5 \times
10^{-3}\ \text{eV}^2$) are consistent with this amplified spacing and a
lightest neutrino mass of $m_{\nu_1} \sim 0.003$ eV.

---
## 1. The seesaw scale in the cascade

The seesaw mechanism in standard physics introduces a heavy right-handed
neutrino at a high scale $M_R$ to explain the smallness of observed neutrino
masses: $m_\nu \approx v_0^2/M_R$.

In the Cassi cascade, the seesaw scale is **cascade step 20**—between the
GUT scale (n ≈ 13.3 for $M_{\text{GUT}} \approx 2\times10^{16}$ GeV) and the electroweak scale (step 80):

$$M_R \approx \ell_{\text{Pl}}^{-1} \cdot \varphi^{-20} \approx 10^{14}\ \text{GeV}$$

The cascade notation used by the offset construction is a conditional
suppression-scale ansatz:

$$m_\nu^{(\text{scale})} = v_0 \cdot \varphi^{-N_\nu}$$

where $N_\nu$ is the selected coordinate span from the fit-start Yukawa
seed to the seesaw scale. The computation uses $N_\nu=12$ for coordinates
$n=8\rightarrow20$; the physical dimensional interval from the mapped GUT
anchor $n_{\text{GUT}}\approx13.3$ to $n_{\text{seesaw}}=20$ is about seven
cascade rungs. The sector is Mapped per the Fit-Status Ledger
(`parameter-inventory.md` §10 row 3): the offsets are grid-fit against the
observed ratio, so the coordinate span is a convention within a fitted sector,
not an independent derivation.

The step-20 value does not select a heavy-neutrino texture. In the fixed
two-singlet benchmark used for the empirical cosmological history,
$z=\pi/4+i/2$ and $M_2/M_1=10$ require the calibrated
$M_1=5.774318838589164\times10^{10}\ {\rm GeV}$ to reproduce
$|\eta_B|$ in the resolved $\{e+\mu,\tau\}$ regime. This is a
texture-dependent empirical calibration rather than a derivation of the
general seesaw scale
(`computations/matter-formation-continuum-report.md` §§83–84).

The selected-coordinate expression $v_0\,\varphi^{-12}$ is a scale
diagnostic; it does not set the absolute spectrum. The absolute spectrum is
fixed by the cascade RGE + PMNS computation (`computations/cascade_rge_pmns.py`),
which pins

$$m_1 = 0.00356\ \text{eV}, \qquad m_2 = 0.00931\ \text{eV}, \qquad m_3 = 0.05019\ \text{eV}, \qquad \Sigma m_\nu = 0.0631\ \text{eV}$$

in normal ordering, with Fibonacci offsets $\Delta_1 = 1.00$ and $\Delta_2 =
1.75$ rungs (§4). The spectrum is consistent with cosmological bounds
($\Sigma m_\nu < 0.12$–$0.6$ eV depending on dataset) and KATRIN's
$\beta$-decay endpoint limit.

The single-seed Yukawa evaluation $m_\nu = y_\nu^2 v_0^2/M_R$ in the companion computation is a scale diagnostic and does not reproduce these fitted absolute masses at the stated $\gamma_\nu$ trajectories. The displayed spectrum is therefore normalized by the selected oscillation mass-squared differences and the mapped offsets; the seesaw expression supplies the mass-ratio structure, not an independently derived absolute normalization.

A separate thermal-leptogenesis benchmark uses the measured normal-ordering
splittings with $m_1=0$, a frozen complex Casas–Ibarra coordinate
$z=\pi/4+i/2$ and $M_2/M_1=10$. Calibrating its baryon-asymmetry magnitude
gives $M_1=5.774318838589164\times10^{10}\ {\rm GeV}$. Independent Radau
integration reproduces the mass to $1.49\times10^{-12}$ relative and the
yield to $1.18\times10^{-12}$ relative.

The two-singlet light-neutrino mass matrix has rank at most two, so one
light mass is exactly zero. It cannot simultaneously realize the separate
Mapped spectrum with $m_1=0.00356\ {\rm eV}$. A unified Cassi completion must
therefore supply a third mass-generating degree of freedom, revise the Mapped
absolute spectrum, or replace the minimal two-singlet baryogenesis action.
The exact CP-conjugate textures also produce opposite baryon signs; registered
Cassi data select neither branch.

---

## 2. Fibonacci partitioning of the compressed span

The three-generations mechanism (`three-generations.md` §2) applies the
Fibonacci recurrence $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$ to partition
the cascade span $N$ into three sub-rung channels. For charged leptons,
$N_{\text{lep}} \approx 72$ rungs, and the Fibonacci sub-rung offsets are
$\Delta_1 \approx 11$, $\Delta_2 \approx 6$, giving the steep hierarchy
($m_\tau/m_\mu \approx \varphi^6 \approx 18$, $m_\mu/m_e \approx \varphi^{11} \approx 200$).

For neutrinos, the same Fibonacci partitioning is applied over the **selected
mapped coordinate span** $N_\nu\approx12$ (coordinates $n=8\rightarrow20$). The
physical dimensional interval from the mapped GUT anchor $n\approx13.3$ to
the seesaw scale is about seven rungs; the two spans must not be conflated. The
Fibonacci sub-rung offsets in the selected coordinate construction are
proportionally compressed:

$$\Delta_{\nu} \approx \Delta_{\text{lep}} \times \frac{N_\nu}{N_{\text{lep}}} \approx 11 \times \frac{12}{72} \approx 2$$

### 2.1 The seesaw Yukawa-squared amplification

A crucial structural difference distinguishes neutrinos from charged leptons.
For charged leptons (Dirac fermions), mass is directly proportional to the
Yukawa coupling: $m_l = y_l \, v_0$, so a cascade-span offset $\Delta$
between sub-rungs produces a mass ratio $m_{k+1}/m_k = \varphi^{\Delta}$.

For neutrinos, the seesaw formula introduces the Yukawa coupling **squared**:

$$m_{\nu_k} = \frac{y_{\nu_k}^2 \, v_0^2}{M_R}$$

The cascade suppression acts on each Yukawa coupling individually. If two
sub-rungs have Yukawa seeds at cascade-span offsets $\Delta_1$ and $\Delta_2$,
their masses are:

$$m_{\nu_1} \propto (y_{\text{GUT}} \cdot \varphi^{-N_{\text{base}}})^2
= y_{\text{GUT}}^2 \cdot \varphi^{-2N_{\text{base}}}$$
$$m_{\nu_2} \propto y_{\text{GUT}}^2 \cdot \varphi^{-2(N_{\text{base}} - \Delta_1)}
= m_{\nu_1} \cdot \varphi^{2\Delta_1}$$
$$m_{\nu_3} \propto y_{\text{GUT}}^2 \cdot \varphi^{-2(N_{\text{base}} - \Delta_1 - \Delta_2)}
= m_{\nu_1} \cdot \varphi^{2(\Delta_1 + \Delta_2)}$$

The mass ratios are therefore:

$$\boxed{\frac{m_{\nu_2}}{m_{\nu_1}} = \varphi^{2\Delta_1}, \qquad
\frac{m_{\nu_3}}{m_{\nu_2}} = \varphi^{2\Delta_2}}$$

The exponent doubles because the seesaw mass is quadratic in each Yukawa
seed: a one-rung shift in $y$ becomes a two-rung shift in $m_\nu$.

For the uniform-spacing case ($\Delta_1 = \Delta_2 = 1$ rung):

$$\frac{m_{\nu_2}}{m_{\nu_1}} \approx \varphi^2 \approx 2.62, \qquad
\frac{m_{\nu_3}}{m_{\nu_2}} \approx \varphi^2 \approx 2.62$$

This is the result cited in the Abstract of `three-generations.md`—the
compressed span's uniform Fibonacci triple $(5,8,13)$ gives near-equal
spacing of $\sim \varphi^2$.

---

## 3. Comparison with oscillation data

Neutrino oscillation experiments measure mass-squared differences, not absolute
masses. The Cassi prediction for the ratios constrains the spectrum:

**Normal ordering** ($m_{\nu_1} < m_{\nu_2} < m_{\nu_3}$):

$$m_{\nu_2} = \varphi^{2\Delta_1} \cdot m_{\nu_1}$$
$$m_{\nu_3} = \varphi^{2(\Delta_1+\Delta_2)} \cdot m_{\nu_1}$$

**Inverted ordering** ($m_{\nu_3} < m_{\nu_1} < m_{\nu_2}$): not compatible
with the Fibonacci triple ordering (strictly $\nu_1 < \nu_2 < \nu_3$). The
framework predicts **normal ordering**.

| Observable | Cassi (uniform $\Delta=1$) | Measured value |
|---|---|---|
| $\Delta m^2_{21}$ | $(\varphi^4 - 1)\,m_{\nu_1}^2 \approx 5.85\,m_{\nu_1}^2$ | $7.5 \times 10^{-5}\ \text{eV}^2$ |
| $\Delta m^2_{31}$ | $(\varphi^8 - 1)\,m_{\nu_1}^2 \approx 46.0\,m_{\nu_1}^2$ | $2.5 \times 10^{-3}\ \text{eV}^2$ |
| $\Delta m^2_{31}/\Delta m^2_{21}$ | $\varphi^4 \approx 6.85$ | $33$ |

The uniform-spacing ratio prediction ($6.85$) is falsified by measurement
($33$). The data require $\Delta_1 \neq \Delta_2$—**non-uniform Fibonacci
partitioning**, exactly as charged leptons have $\Delta_1 = 11 \neq \Delta_2 = 6$.

---

## 4. Non-uniform Fibonacci partitioning—pinned by cascade RGE + PMNS

The Fibonacci recurrence does not require uniform sub-rung spacing. The two
Fibonacci predecessors ($n-1$ and $n-2$) naturally produce **asymmetric**
partitioning: the step from $n$ to $n-1$ is one rung, and from $n$ to $n-2$
is two rungs—a 2:1 ratio in cascade offset.

The full cascade RGE + PMNS computation (`computations/cascade_rge_pmns.py`,
July 2026) uses the selected mapped coordinate span $n=8\rightarrow20$ to pin
the offset construction. The canonical dimensional anchors place the physical
GUT scale at $n\approx13.3$ and the seesaw at step 20, an interval of about
seven rungs. The computation matches the predicted
$\Delta m^2_{31}/\Delta m^2_{21}$ ratio to the NuFIT 5.3 observed value
$33.89$. The scan over quarter-rung increments yields:

$$\boxed{\Delta_1 = 1.00\ \text{rungs},\qquad \Delta_2 = 1.75\ \text{rungs}}$$

The mass-exponent offsets are $2\Delta_1 = 2.00$ and $2\Delta_2 = 3.50$:

$$\frac{m_{\nu_2}}{m_{\nu_1}} = \varphi^{2\Delta_1} = \varphi^{2.00} \approx 2.618, \qquad
\frac{m_{\nu_3}}{m_{\nu_2}} = \varphi^{2\Delta_2} = \varphi^{3.50} \approx 5.388$$

This gives $m_{\nu_3}/m_{\nu_1} = \varphi^{5.50} \approx 14.04$.

The mass-squared differences are:

$$\Delta m^2_{21} = m_{\nu_1}^2\,(\varphi^{4.00} - 1) = m_{\nu_1}^2 \times 5.854$$
$$\Delta m^2_{31} = m_{\nu_1}^2\,(\varphi^{11.00} - 1) = m_{\nu_1}^2 \times 198.0$$

The ratio:

$$\boxed{\frac{\Delta m^2_{31}}{\Delta m^2_{21}} = \frac{\varphi^{11.00} - 1}{\varphi^{4.00} - 1} \approx \frac{198.0}{5.854} \approx 33.82}$$

**This matches the observed ratio $\approx 33.89$ to 0.2%.** The residual is
dwarfed by the current experimental uncertainty ($\sim 3\%$ on the ratio).

### 4.1 The pinned offsets are clean φ-powers

The striking result is that $\Delta_1 = 1.00$ is an **exact integer rung**—
the Fibonacci offset from generation 1 to generation 2 is precisely one
cascade φ-step. And $\Delta_2 = 1.75 = 7/4$ rungs is a rational fraction
with denominator 4, corresponding to the Fibonacci spiral's quarter-rung
subdivision (the same structure that produces spin-½).

The ratio of the fitted offsets to the raw Fibonacci offsets supplies a
post-hoc mapped compression factor, with an average near
$\bar\kappa_{\mathrm{fit}} \approx 0.37$, close numerically to
$\varphi^{-2} \approx 0.382$. This is a comparison of the selected
coordinate fit. It does not establish a spectral gap, a fixed point, or an
RG mechanism for the seesaw sector.

### 4.2 The pinned offsets in mass-exponent space

In mass-exponent space the pinned offsets are $2\Delta_1 = 2.00$ and
$2\Delta_2 = 3.50$: the first Fibonacci sub-rung sits exactly one full
cascade φ-step from the lightest generation, the second at three and a half
steps ($\Delta_2 = 7/4$ rungs, the quarter-rung subdivision of the
Fibonacci spiral).

**The cascade RGE + PMNS computation pins the Fibonacci offsets to**
**$\Delta_1 = 1.00$, $\Delta_2 = 1.75$ rungs, matching the observed**
**$\Delta m^2_{31}/\Delta m^2_{21} \approx 33.89$ to 0.2%.**

---

## 5. Predictions

| # | Prediction | Status |
|---|---|---|
| N1 | **Normal mass ordering**: $m_{\nu_1} < m_{\nu_2} < m_{\nu_3}$ from Fibonacci triple ordering | Falsifiable with JUNO/DUNE |
| N2 | **Lightest neutrino mass** $m_{\nu_1} \approx 0.00356$ eV from $\Delta m^2_{21}$ and $\Delta_1 = 1.00$ rung | Testable with KATRIN/COSM$\nu$ |
| N3 | **No sterile neutrinos** at cascade-accessible scales—the Fibonacci triple saturates at 3 generations | Testable with SBN/Daya Bay |
| N4 | **Pinned mass spectrum**: $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV, $\Sigma m_\nu = 0.0631$ eV, $|m_{\beta\beta}| = 0.0043$–$0.0052$ eV | Computed (July 2026); see `computations/cascade_rge_pmns.py` |

---

## 6. Epistemic boundaries

### Structural mechanism (Hypothesized)

- Three mass eigenstates from Fibonacci triple-clustering (same mechanism as Q5)
- Normal ordering from Fibonacci triple monotonicity
- No sterile neutrinos beyond the three Fibonacci sub-rungs
- **$y_\nu^2$ amplification of the $\varphi$-exponent** (factor of 2 from seesaw product structure)

### Mapped / conditional quantities

- The selected-coordinate suppression diagnostic $v_0\,\varphi^{-12}$
- **Pinned Fibonacci offsets**: $\Delta_1 = 1.00$, $\Delta_2 = 1.75$ rungs from cascade RGE + PMNS
- **$\Delta m^2_{31}/\Delta m^2_{21} \approx 33.82$** (0.2% residual to observed $33.89$)
- **Post-hoc mapped compression comparison**:
  $\bar\kappa_{\mathrm{fit}} \approx 0.37 \approx \varphi^{-2}$; this
  numerical proximity carries no spectral-gap or RG interpretation.
- **Resolved-flavour thermal-leptogenesis mass**:
  $M_1=5.774318838589164\times10^{10}\ {\rm GeV}$ is Calibrated to the
  observed $|\eta_B|$ inside the supplied $z=\pi/4+i/2$,
  $M_2/M_1=10$ texture. Its rank-two light matrix has $m_1=0$ and therefore
  cannot equal the separate Mapped three-nonzero-mass spectrum.

### Hypothesized (testable)

- Full mass spectrum: $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV, $\\Sigma m_\\nu = 0.0631$ eV
- $|m_{\\beta\\beta}| = 0.0043$–$0.0052$ eV (0νββ, δ_CP-dependent)
- $m_\\beta = 0.0092$ eV (KATRIN endpoint effective mass)

---

## 7. References

- `foundations/three-generations.md`—Fibonacci triple-clustering, $N_{\text{gen}}=3$
- `foundations/cascade-suppression-formula.md`—cascade attenuation factor
- `foundations/dimensionful-cascade.md`—seesaw at step 20
- `foundations/refined-numeric-predictions.md` §2.2—unified numeric predictions
- `open-questions-cassi-answers.md`—Q3 (neutrino masses), Q5 (three generations)
- `computations/cascade_rge_pmns.py`—full cascade RGE + PMNS, pinned offsets
- `computations/qcd-cosmological-matter-completion-prereg.md`—fixed two-singlet texture and no-fit seesaw-scale comparison
- `computations/matter-formation-continuum-report.md` §83—calibrated leptogenesis result and scope
- `computations/qcd-whole-bubble-cp-selection-prereg.md`—frozen resolved-flavour, rank, initial-state and CP-selection protocol
- `computations/qcd_whole_bubble_cp_selection.py`—primary calibration, conjugate pair and real-coordinate scan
- `computations/verify_qcd_whole_bubble_cp_selection.py`—independent Radau and matrix reconstruction
