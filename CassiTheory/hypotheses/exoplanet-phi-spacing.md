# Exoplanet Orbital Spacing from the Wake-Wave Mechanism

## Status: Hypothesized—August 2026

## Abstract

The Titius-Bode relation supplies a loose one-system correspondence rather
than evidence for a universal spacing law. A conditional Cassi reading assigns
the bubble-shell ladder to coherence-coupled disk material, giving successive
disk radii $r_{k+1}/r_k=\varphi^{-1}$. Kepler's law maps that radial template
to the conditional detached-orbit value
$P_{\rm out}/P_{\rm in}=\varphi^{3/2}=2.058171$. The disk-to-orbit
preservation map remains unspecified.

The registered period-ratio classifier has been executed on an explicitly
confirmed NASA Exoplanet Archive sample. Its primary Kepler result is
**INDETERMINATE**: 46 ratios occupy the headline window and the descriptive
folded-window score is $z_{\rm win}=1.087$. The scientific result is
**INCONCLUSIVE** for Cassi because the target window overlaps the registered
2:1 interval across $41.8\%$ of its width and occupies the known excess
immediately wide of the 2:1 mean-motion resonance. The DSHARP disk-gap branch
remains pending an auditable input-and-run receipt.

## Origin Status

**Verdict: coordinate template Hypothesized; tested dynamical realization
REJECT; tier stays Hypothesized.** The disk application uses the bubble-shell
ring coordinates of `foundations/bubble-edge-geometry.md` §3.1. Their radii
follow algebraically once the log-radius phase, pitch convention, doublet's
$\pi$-per-rung advance, pool-cell parities, and nesting depth are supplied.
The physical selection of that coordinate remains Hypothesized. In the disk
application, a condensation wake is compared with the bubble shell:

$$
r_k=R\varphi^{-k},
\qquad
\frac{r_{k+1}}{r_k}=\varphi^{-1}=0.6180.
$$

The application remains Hypothesized for four reasons:

- **Radial-reading inference.** The assignment
  $\alpha=\pi\log_\varphi(r/\ell_n)$ rests on the nested sub-lattice structure
  in `foundations/bubble-lattice-fabric.md` §3.2.
- **Dynamical realization.** The canonical four-arm dynamic probe produces
  **NO RINGS** to $t=40$. The available undriven second-order space-sim
  readback produces **NO RIDGES** beyond a transient shell and one interior
  feature. The driven second-order control forms additively spaced layers,
  gives $k_\rho/k_\epsilon=1.311855471$ at its generic frequency, and leaves a
  phase-only chain gapless. The live source supplies no $\Omega_*$ selector and
  its computed $q$ does not feed back into wave coupling magnitudes. Prediction
  51's tested dynamical realization is therefore `REJECT`; the supplied
  log-radius disk template remains Hypothesized.
- **Disk-gap data.** Prediction 53 has a registered DSHARP design, while the
  parsed table, raw-source hashes, and run receipt are absent. No
  observation-level DSHARP verdict is assigned.
- **Detached-orbit data.** Prediction 54's confirmed-catalog execution returns
  formal classifier verdict **INDETERMINATE** and scientific verdict
  **INCONCLUSIVE**. Its target is degenerate with conventional dynamics near
  the 2:1 resonance; full numbers and source hashes are frozen in
  `experiments/kepler_phi_ratios/kepler-period-ratio-report.md`.

The channel reading in `foundations/qi-as-spatial-spacing-signal.md` §4 assigns
direct sensitivity to coherence-coupled disk gas. Mature planetary orbits gain
a Cassi-specific period-ratio prediction only from a defined disk-to-orbit
transfer and preservation law. The current catalog diagnostic supplies no
evidence for such a law.

The solar-system bookkeeping remains weak. The geometric mean of the six
listed adjacent ratios is 1.66, with the 3.42 Mars/Jupiter jump dominating the
set. The fixed Mercury-to-slot-8 assignment has mean $|\ln a|$ deviation
0.193. A reassignment that maps Uranus to slot 8, Neptune to slot 9, and omits
slot 7 gives 0.088; Titius-Bode gives 0.084 under its stated assignment. These
values do not establish a mechanism.

## 1. The Titius-Bode "Law"

The empirical Titius-Bode relation for solar system semi-major axes:
$$a_n = 0.4 + 0.3 \times 2^n \quad \text{(AU, for $n = -\infty, 0, 1, 2, \ldots$)}$$

The progression factor is 2, but the actual mean spacing ratio of adjacent
planets in our solar system varies: Venus/Earth = 0.723, Earth/Mars = 1.52,
Mars/Jupiter = 3.42 (the asteroid belt occupies this gap), Jupiter/Saturn =
1.83, Saturn/Uranus = 1.97, Uranus/Neptune = 1.56. The geometric mean of these
six ratios is 1.66, within 3% of $\varphi$—but the set is dominated by the
single 3.42 Mars/Jupiter jump, and the ratio convention (inner/outer vs
outer/inner, Mercury included or not) moves the mean between 1.66 and 1.75.
One planetary system cannot select $\varphi$ over the progression factor 2
that Titius-Bode already fits.

The standard interpretation is that orbital resonances (mean-motion resonances
at period ratios like 2:1, 3:2, and 5:3) sculpt planetary spacing through
gravitational interactions. In the Cassi interpretation, these ratios can be
compared with Fibonacci convergents of $\varphi$ as a conditional
de-resonance mapping. Whether their ubiquity follows from a disk Qi field
seeking $\varphi$-equilibrium remains an open dynamical question.

## 2. The Ring Ladder in Protoplanetary Disks

The disk mechanism is the bubble-shell ring ladder (`foundations/bubble-edge-geometry.md`
§3.1). A condensation shell of effective radius $R$ carries interior matter
rings at

$$\boxed{r_k = R\,\varphi^{-k}, \qquad k = 0, 1, 2, \ldots}$$

and void troughs at $R\,\varphi^{-(k+\frac12)}$, so successive matter rings are
separated by the fixed ratio $\varphi^{-1} = 0.6180$ and each matter ring is
trailed inward by its void at $\varphi^{-1/2} = 0.7862$. The ladder is the
doublet's radial phase $\alpha = \pi u$, $u = \log_\varphi(r/\ell_n)$
(phase-quantized, *not* a beat); the negative result—the naive one-dimensional
wake-sum $\cos(2\pi r/\ell_n) + \cos(2\pi\varphi r/\ell_n)$ has zeros at
$\{0.191, 0.573, 0.809, 0.955\}\,\ell_n$, not a $\varphi$-ladder—is documented
in `foundations/bubble-edge-geometry.md` §3.5.

The 2026-08-27 phase-gap campaign verifies that ordinary radial beating and
the driven second-order channel pair produce additive layers. Exact
$\varphi$ wavenumber ratio requires the supplied drive
$\Omega_*=\varphi^{3/2}\omega_{0,\mathrm{wave}}$, and uniform phase
staggering remains gapless. See
`field-experience/phase-staggered-scale-gap-report.md`.

For a conditional disk application, the condensation wake can be compared with
the bubble shell: annular gaps in millimeter observations can be tested against
the $\varphi$-spaced template, with successive gap ratios
$\varphi^{-1}=0.6180$ and interleaved-null ratio $\varphi^{-1/2}=0.7862$. A
disk is not a static bubble shell; a gap is a radial intensity minimum whose
depletion mechanics are set by disk dynamics. The ladder supplies a testable
location template, not a demonstrated gap generator. Whether local density,
planet formation, or another process selects these loci remains open.

The disk reading inherits the radial-reading inference flag of
`foundations/bubble-edge-geometry.md` §3.1. Prediction 51's tested dynamical
realization is `REJECT`; the disk-gap claim remains a statistical,
observational test of the supplied coordinate template rather than a per-disk
scaffolding.

## 3. Conditional Period-Ratio Diagnostic

If adjacent formation radii obey
$a_{\rm out}/a_{\rm in}=\varphi$, Kepler's third law gives

$$
\boxed{
\frac{P_{\rm out}}{P_{\rm in}}
=
\left(\frac{a_{\rm out}}{a_{\rm in}}\right)^{3/2}
=\varphi^{3/2}
=2.058171
}.
$$

This equation is exact arithmetic conditional on the radial premise. The
canonical two-fluid PDE does not currently supply the transfer from a disk
density node to a mature adjacent-planet period ratio.

The Fibonacci convergents of $\varphi$ coincide with several familiar
mean-motion resonances:

| convergent | ratio | resonance |
|---|---:|---|
| $1/1$ | 1.000 | 1:1 |
| $2/1$ | 2.000 | 2:1 |
| $3/2$ | 1.500 | 3:2 |
| $5/3$ | 1.667 | 5:3 |
| $8/5$ | 1.600 | 8:5 |
| $13/8$ | 1.625 | high-order neighborhood |

The registered catalog diagnostic compares a
$\varphi^{3/2}\pm0.05$ window, a $\varphi\pm0.05$ belt, the 3:2 and 2:1
windows, and three distant non-Fibonacci controls. On the confirmed Kepler
sample, the headline score is $z_{\rm win}=1.087$, the $\varphi$-belt score is
$0.904$, the 3:2 score is $2.370$, and the 2:1 score is $0.171$. The
classifier returns **INDETERMINATE**.

The headline interval $[2.008171,2.108171]$ intersects the registered 2:1
interval $[1.95,2.05]$ over $41.8\%$ of its width. Its upper part lies in the
well-established wide-of-2:1 excess produced by ordinary near-resonant
dynamics. Fabrycky et al. document the asymmetric excess wide of first-order
resonances, and Lithwick and Wu derive resonant repulsion under eccentricity
damping. This broad window is therefore unsuitable as a clean
$\varphi$-versus-resonance discriminator.

The period-ratio branch remains a catalog diagnostic. A Cassi-specific test
requires an independently specified transfer amplitude and width plus a
conventional baseline for resonant dynamics, survey selection, and
within-system dependence.

## 4. Solar System Fit

Our solar system's eight planets (treating the asteroid belt as a disrupted
planet at ~2.8 AU) should show a $\varphi$-spaced log-periodic fit:

$$\ln(a_n / \text{AU}) \approx \ln(a_0) + n \cdot \ln\varphi$$

With $a_0 = 0.4$ AU (Mercury): predicted $a_1 = 0.4 \times \varphi = 0.65$ AU
(Venus at 0.72), $a_2 = 0.4 \times \varphi^2 = 1.05$ AU (Earth at 1.00), $a_3
= 0.4 \times \varphi^3 = 1.70$ AU (Mars at 1.52), $a_4 = 0.4 \times \varphi^4 =
2.75$ AU (asteroid belt at 2.1–3.3), $a_5 = 0.4 \times \varphi^5 = 4.45$ AU
(Jupiter at 5.20—worst fit, 17% off), $a_6 = 0.4 \times \varphi^6 = 7.20$ AU
(Saturn at 9.54), $a_7 = 0.4 \times \varphi^7 = 11.6$ AU (Uranus at 19.2), $a_8
= 0.4 \times \varphi^8 \approx 18.8$ AU (Uranus fit here, Neptune at 30.1—worst
outer-planet fit).

The fit is rough—the solar system is one sample. Mean absolute deviation in
$\ln a$ is 0.193 for the fixed Mercury-to-slot-8 assignment (with Saturn 34%
off and slot 7 matching nothing). An assignment that maps Uranus to slot 8,
Neptune to slot 9, and drops slot 7 gives 0.088. Titius-Bode's own mean
$|\ln a|$ deviation is 0.084 under its stated assignment. These values compare
bookkeeping choices and do not establish a mechanism.

## 5. Falsifiable Tests

1. **Confirmed-catalog period-ratio diagnostic.** The registered descriptive
   classifier has been executed on 476 Kepler multi-planet systems. It returns
   **INDETERMINATE** for the primary sample
   ($N_{\varphi^{3/2}}=46$, $z_{\rm win}=1.087$). The mechanism-level verdict
   is **INCONCLUSIVE** because the target occupies the conventional
   wide-of-2:1 region.

2. **Resonance selectivity.** The 3:2 window is elevated
   ($z_{\rm win}=2.370$), while the distant 4:3, 7:3, and 5:2 controls remain
   below the registered threshold. Those controls do not model the
   first-order 2:1 asymmetry. A physical baseline and likelihood comparison
   are required.

3. **Disk-gap $\varphi$ spacing.** Prediction 53 tests successive radial gap
   ratios $\varphi^{-1}=0.6180$ against the interleaved value
   $\varphi^{-1/2}=0.7862$ in resolved disks. Its DSHARP input and immutable
   run receipt are absent, so the observation-level verdict remains pending.

4. **Per-system scope.** The radial and period-ratio claims are population
   hypotheses. Migration, scattering, disk dynamics, and observational
   selection can move individual systems away from any formation template.

## 6. Open Issues

- Planet migration (Type I and Type II) after formation smears the primordial
  $\varphi$-spacing. The observed period ratio distribution convolves
  formation spacing with migration and dynamical instability. Disentangling
  these requires a population synthesis model with $\varphi$-spaced initial
  conditions.
- The solar system's Jupiter (5.2 AU vs. predicted 4.45 AU) is the largest
  deviation. The Grand Tack hypothesis (Jupiter migrated inward to ~1.5 AU then
  back out) could explain this if the formation location was near the predicted
  node.
- The asteroid belt (2.1–3.3 AU) spans approximately one $\varphi$-factor in
  radius—consistent with a disrupted $\varphi$-node, but the disruption
  mechanism (Jupiter's resonance sweeping) must be shown to operate at the
  predicted location.
- **The dynamical realization of the ladder in a disk is open.** The two
  no-ring nulls (Origin Status) apply: the canonical first-order solver does
  not spontaneously form standing rings, and the space-sim wave form shows no
  persistent ridge ladder. A real disk gap is carved by planet-disk
  interaction or other mechanisms; the Cassi ladder is a kinematic template,
  not an established generator of disk substructure.
- **The first-order resonance baseline is mandatory.**
  $\varphi^{3/2}=2.058171$ lies in the observed excess immediately wide of
  2:1. Distant resonance controls cannot separate a $\varphi$ component from
  resonant repulsion or related migration dynamics. A future test must compare
  full, frozen population models across the same selection function.

## 7. The DSHARP Disk-Gap Test (Prediction 53)

### 7.1 Pre-registered design

The ring ladder predicts, in a protoplanetary disk, annular gaps at
$\varphi$-spaced radii with successive (inner/outer) ratio $\varphi^{-1} =
0.6180$ against the interleaved-null ratio $\varphi^{-1/2} = 0.7862$. The
decision tree is pre-registered in the script docstring
(`experiments/dsharp_phi_gaps/stack_phi_gaps.py`, written before any analysis
run):

- **Data:** the 18 single-disk systems of the ALMA DSHARP survey; gap radial
  positions are specified by the survey's annular-substructure table
  (`tab:ringpositions`, Huang et al. 2018, arXiv:1812.04041; the survey is
  Andrews et al. 2018, arXiv:1812.04040).
- **Acquisition specification:** `experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py`
  records the intended download and hash procedure. The raw files and SHA-256 receipt are not
  retained in this checkout.
- **Ratios:** each disk's detected gaps sorted by radius, successive
  (inner/outer) ratios pooled across disks.
- **Windows (fixed):** signal $W_1 = [0.6180 \pm 0.08] = [0.538, 0.698]$;
  null $W_2 = [0.7862 \pm 0.05] = [0.736, 0.836]$.
- **Null:** for each disk, draw the same number of gaps from a log-uniform
  distribution over that disk's observed gap radial span; 1000 realizations.
  $E_1, E_2$ = null mean counts in $W_1, W_2$; $s_1, s_2$ = std.
- **Verdict:** counting $N_1$ pooled ratios in $W_1$ and $N_2$ in $W_2$:
  **SUPPORTS** if $N_1 \ge E_1 + 2s_1$ and $N_2 < E_2 + 2s_2$;
  **SUPPORTS NULL** if $N_2 \ge E_2 + 2s_2$ and $N_1 < E_1 + 2s_1$;
  else **INDETERMINATE**.

### 7.2 Data and provenance

- **Survey:** DSHARP (Andrews et al. 2018, arXiv:1812.04040, 20 targets; 18
  single-disk systems), with annular substructure positions cited from Huang
  et al. 2018 (arXiv:1812.04041), Table `tab:ringpositions`.
- **Repository state:** only `experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py`
  and `experiments/dsharp_phi_gaps/stack_phi_gaps.py` are present. The parsed
  gap table, raw e-print files, SHA-256 receipt, and run JSON are not retained.
  The reported sample counts and numerical results therefore cannot be
  independently reproduced from this checkout.
- **Evidence status:** the DSHARP design remains a registered test. No
  observation-level verdict is assigned until the input and output receipt is
  retained.

### 7.3 Results

No reproducible DSHARP result is available in this checkout. Exact pooled
ratios, window counts, null moments, significances, per-disk classifications,
and detection-power values are not evidence here without the missing input and
run receipts. No detection-power or sensitivity value is assigned. These
quantities require the missing parsed gap input and retained run output.

### 7.4 Verdict and statistical reading

Prediction 53 remains registered and **pending an auditable data-and-results
receipt**. The ring-ladder mechanism remains Hypothesized and conditional on
its dynamical realization in a disk; planet-carving remains the standard
alternative explanation.
---

## 8. The Kepler Period-Ratio Test (Prediction 54)

### 8.1 Protocol and provenance

The primary sample selects `soltype='Published Confirmed'`,
`default_flag=1`, transit discovery, and exact `disc_facility='Kepler'` from
the NASA Exoplanet Archive `ps` table. Hosts require at least two confirmed
planets. Adjacent period ratios are formed after ordering each host by orbital
period, with fixed support $[1,3]$. The raw response retains every predicate
column, and the parser checks each predicate independently.

The fetched Kepler response has SHA-256
`0da130b0641ac369d26fa2751b5ed544eefcb405d8d538d0370b2feb72255aae`;
the K2/TESS response has SHA-256
`61c240a20500e79942a4828f84a12cc3608e9a4c4af9be876f73f08e768b959a`.
The complete receipt is
`experiments/kepler_phi_ratios/kepler-period-ratio-report.md`.

The fixed-width scan supplies a descriptive score

$$
z_{\rm win}=\frac{N(W)-E_{\rm win}}{s_{\rm win}},
$$

where $E_{\rm win}$ and $s_{\rm win}$ describe count variation as the window
center moves across the observed histogram. The registered sweep includes
truncated edge windows. This score is not a repeated-catalog sampling
distribution. The 562 in-support ratios come from 361 hosts; 137 hosts
contribute more than one ratio, with a maximum of six, so pairwise independence
does not hold.

### 8.2 Primary result

The Kepler sample contains 476 systems, 1,212 planets, 736 total adjacent
ratios, and 562 ratios inside $[1,3]$. Its window reference is
$E_{\rm win}=28.1995$ and $s_{\rm win}=16.3697$.

| window | count | $z_{\rm win}$ |
|---|---:|---:|
| $\varphi^{3/2}\pm0.05$ | 46 | 1.087 |
| $\varphi\pm0.05$ | 43 | 0.904 |
| 3:2 | 67 | 2.370 |
| 2:1 | 31 | 0.171 |
| maximum non-Fibonacci control | 23 | -0.318 |

The registered primary classifier returns

$$
\boxed{\text{INDETERMINATE}.}
$$

The K2/TESS cross-check contains 201 systems and 207 in-support adjacent
ratios. Its headline count is 26 with $z_{\rm win}=2.120$, while the 3:2 and
2:1 scores are $2.391$ and $1.849$. This secondary score is descriptive and
does not override the primary verdict.

### 8.3 Resonance confound and diagnostics

The headline interval overlaps the registered 2:1 interval across $41.829\%$
of its width. Twenty-three of the 46 primary headline counts and 17 of the 26
cross-check counts fall in the explicit overlap. The remaining upper segment
occupies the conventionally observed excess wide of 2:1.

A conditional per-system log-uniform reshuffle fixes the observed endpoint
periods and randomizes only interior periods. It gives headline count
$25.078\pm3.502$, placing the observed count at standardized offset $5.975$.
All 298 two-planet systems are unchanged, including 12 headline-window pairs
present in every realization. This is an interior-spacing diagnostic
conditional on observed endpoints, not a generative orbital null or evidence
for a $\varphi$ mechanism.

The synthetic-injection classifier reaches a SUPPORTS fraction of 0.23 at a
4% planted component and 0.99 at 6%. These values measure sensitivity to one
log-normal injection family centered at 2.058 rather than power against a
physical orbital-dynamics null.

### 8.4 Verdict

The formal registered-classifier verdict is **INDETERMINATE**. The scientific
verdict is **INCONCLUSIVE** for Cassi. The current broad target interval fails
as a mechanism discriminator because standard first-order resonance dynamics
populate the same region. No Cassi field effect is inferred from either
catalog.

The detached-orbit branch requires a disk-to-orbit transfer law and a frozen
conventional population model before another catalog execution can be
falsifiable at the mechanism level. Prediction 53's disk-gas channel remains
the direct observational test of the spacing hypothesis.

## References

- `open-questions-cassi-answers.md`—C9 (cosmic web from wake-wave), G5 (3+1 dimensions).
- `predictions/falsifiable-predictions.md`—Predictions 51–54.
- `foundations/bubble-edge-geometry.md` §3.1—the conditional ring law; §§3.5–3.7—the no-ring, additive-wave, and phase-gap boundaries.
- `field-experience/phase-staggered-scale-gap-report.md`—ordinary radial spacing, driven second-order layer control, and phase-only gap null.
- `foundations/bubble-lattice-fabric.md` §3.2–3.3—the nested sub-lattice and radial-reading premise.
- `foundations/qi-as-spatial-spacing-signal.md` §4—the coherence-coupled disk channel and detached matter channel.
- `experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py`—DSHARP acquisition specification.
- `experiments/dsharp_phi_gaps/stack_phi_gaps.py`—registered disk-gap classifier.
- `experiments/kepler_phi_ratios/acquire_kepler_catalog.py`—confirmed-planet TAP acquisition and SHA-256 receipt generation.
- `experiments/kepler_phi_ratios/run_phi_ratios.py`—registered descriptive period-ratio classifier.
- `experiments/kepler_phi_ratios/kepler-period-ratio-report.md`—audited catalog receipt, results, and verdict.
- Andrews et al. 2018, arXiv:1812.04040—DSHARP survey.
- Huang et al. 2018, arXiv:1812.04041—DSHARP annular substructures.
- Fabrycky et al. 2014, arXiv:1202.6328—period-ratio asymmetry wide of first-order resonances.
- Lithwick and Wu 2012, arXiv:1204.2555—resonant repulsion under eccentricity damping.
- Steffen and Hwang 2015, arXiv:1409.3320—Kepler period-ratio distribution.
